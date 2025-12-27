#!/usr/bin/env python3
"""
MSX1 縦スクロール ROM ビルダー。

縦長の PNG画像 を １枚（今後複数枚に機能拡張予定）受け取り 以下の手順で ROM を生成する:

1. 入力 PNG を左端を基準で横256pxにトリミング。足りない場合は右側を背景色でパディング。
2. 縦は 8px 単位になるように下側へ背景色でパディング。
3. `msx1pq_cli`（PATH もしくは引数で指定）を用いて MSX1 ルール準拠の PNG を生成。
    ※ 美しくするための前処理や加工は行われず機械的に変換する。
    質の高い画像にしたい場合はあらかじめmsx1pq_cliや他のツールで対応しておく。
4. パターンジェネレータとカラーテーブルを隙間なく連結し、バンク境界をまたいで
   ASCII16 MegaROM のデータバンクに格納。
5. プログラム領域の直後に各画像 6 バイトのヘッダ（開始バンク、行数、色データ開始
   バンクとアドレス）を 3 バイトずつの情報として並べ、最後に 4 バイトの終端情報を
   付与。
6. ビューアーとともにROMデータとして出力。

実装中
・ヘッダテーブルの行数とカラーデータ開始情報を読み取り1画面分を描画

NEXT
RAMからVRAMコピーなどを用いて（実際のアルゴリズムは未定）速さを考慮しつつ
1行単位でスクロールできるように

NEXT
・複数枚画像をROMに埋め込めるように
・複数枚画像をはグループ化可能 グループごとに縦に連結した1枚の画像として扱う
・スペースで次の画像に SHIFT＋スペースで前の画像に
・上下でスクロール
・オートスクロールモード搭載 最後の行まで達したら次の画像の一番上に
・簡易BGMルーチン搭載
・デフォルトの挙動はコマンドラインOPTION指定できまる
・ESCを押すと管理画面（SCRENN0）に切り替わり設定を替えられる。彩度ESCで復帰。
・再生画像番号指定、オートスクロール＆その速度指定、BGM ONOFFなど

※ 管理画面の機能はライブラリ化して他のツール・ゲームでも使えるようにする
項目がテキストで並び 上下で選択項目切り替え 左右で項目設定切り替え など



"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Sequence, List

from mmsxxasmhelper.core import (
    ADD,
    Block,
    CALL,
    CP,
    DEC,
    Func,
    INC,
    JP,
    JR,
    JR_C,
    JR_NC,
    JR_NZ,
    JR_Z,
    DJNZ,
    LD,
    OR,
    POP,
    PUSH,
    XOR,
    DB,
    DW,
    NOP,
)
from mmsxxasmhelper.msxutils import (
    CHGCLR,
    CHGMOD,
    FORCLR,
    BAKCLR,
    BDRCLR,
    LDIRVM,
    enaslt_macro,
    place_msx_rom_header_macro,
    restore_stack_pointer_macro,
    set_msx2_palette_default_macro,
    store_stack_pointer_macro,
    ldirvm_macro,
)
from mmsxxasmhelper.utils import pad_bytes, loop_infinite_macro, debug_trap, set_debug, print_bytes
from PIL import Image
from simple_sc2_converter.converter import BASIC_COLORS_MSX1, parse_color

PAGE_SIZE = 0x4000
ROM_BASE = 0x4000

ASCII16_PAGE2_REG = 0x7000
DATA_BANK_ADDR = 0x8000

# VDP / SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE = 0x1800
COLOR_BASE = 0x2000

# MSX RAM での作業領域
WORK_RAM_BASE = 0xC000
PATTERN_RAM_BASE = WORK_RAM_BASE
PATTERN_RAM_SIZE = 0x1800
COLOR_RAM_BASE = WORK_RAM_BASE
COLOR_RAM_SIZE = 0x1800
TARGET_WIDTH = 256
SCREEN_TILE_ROWS = 24
IMAGE_HEADER_ENTRY_SIZE = 6
IMAGE_HEADER_END_SIZE = 4

CHSNS = 0x009C
CHGET = 0x009F

CURRENT_IMAGE_ADDR = WORK_RAM_BASE + PATTERN_RAM_SIZE
CURRENT_IMAGE_START_BANK_ADDR = CURRENT_IMAGE_ADDR + 1
CURRENT_IMAGE_ROW_COUNT_ADDR = CURRENT_IMAGE_START_BANK_ADDR + 1
CURRENT_IMAGE_COLOR_BANK_ADDR = CURRENT_IMAGE_ROW_COUNT_ADDR + 2
CURRENT_IMAGE_COLOR_ADDRESS_ADDR = CURRENT_IMAGE_COLOR_BANK_ADDR + 1


@dataclass
class ImageEntry:
    start_bank: int
    tile_rows: int
    color_bank: int
    color_address: int


@dataclass
class ImageData:
    pattern: bytes
    color: bytes
    tile_rows: int


def int_from_str(value: str) -> int:
    return int(value, 0)


@contextmanager
def open_workdir(path: Path | None):
    if path is None:
        with TemporaryDirectory() as tmp:
            yield Path(tmp)
    else:
        path.mkdir(parents=True, exist_ok=True)
        yield path


def prepare_image(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    """Crop/pad the input to 256px width and multiple-of-8 height."""

    img = image.convert("RGB")
    width, height = img.size

    cropped_width = min(width, TARGET_WIDTH)
    cropped = img.crop((0, 0, cropped_width, height))

    new_height = ((height + 7) // 8) * 8
    canvas = Image.new("RGB", (TARGET_WIDTH, new_height), background)
    canvas.paste(cropped, (0, 0))
    return canvas


def find_msx1pq_cli(path: Path | None) -> Path:
    if path is not None:
        if path.is_file():
            return path
        raise SystemExit(f"msx1pq_cli not found: {path}")

    resolved = shutil.which("msx1pq_cli")
    if not resolved:
        raise SystemExit("msx1pq_cli not found in PATH. Provide --msx1pq-cli.")
    return Path(resolved)


def run_msx1pq_cli(cli: Path, prepared_png: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_suffix = "_quantized"
    cmd = [
        str(cli),
        "-i",
        str(prepared_png),
        "-o",
        str(output_dir),
        "--no-preprocess",
        "--out-suffix",
        out_suffix,
        "--force",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            "msx1pq_cli failed:\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    out_path = output_dir / f"{prepared_png.stem}{out_suffix}{prepared_png.suffix}"
    if not out_path.is_file():
        raise SystemExit(f"Expected output not found: {out_path}")
    return out_path


def nearest_palette_index(rgb: Sequence[int]) -> int:
    """Return the closest MSX1 palette index (0-based) for an RGB triple."""
    r, g, b = rgb
    best_idx = 0
    best_dist = float("inf")
    for idx, (pr, pg, pb) in enumerate(BASIC_COLORS_MSX1):
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    return best_idx


def palette_distance(idx_a: int, idx_b: int) -> int:
    ra, ga, ba = BASIC_COLORS_MSX1[idx_a]
    rb, gb, bb = BASIC_COLORS_MSX1[idx_b]
    return (ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2


def restrict_two_colors(indices: list[int]) -> list[int]:
    """Ensure a block uses at most two colors.

    `msx1pq_cli` で 8dot 2 色ルールが守られている前提だが、念のため
    3 色以上のブロックを 2 色に丸める安全弁を入れておく。
    """

    unique = set(indices)
    if len(unique) <= 2:
        return indices

    raise ValueError(f"{unique} colors in 8 dots.")

    counts = Counter(indices)
    allowed = [color for color, _ in counts.most_common(2)]

    remapped: list[int] = []
    for idx in indices:
        if idx in allowed:
            remapped.append(idx)
            continue
        remapped.append(min(allowed, key=lambda candidate: palette_distance(idx, candidate)))

    return remapped


def build_image_data_from_image(image: Image.Image) -> ImageData:
    """Convert a quantized image into pattern/color bytes."""

    width, height = image.size
    if width != TARGET_WIDTH:
        raise ValueError(f"Width must be {TARGET_WIDTH}, got {width}")
    if height % 8 > 0:
        raise ValueError(f"Height must be 8x size, got {height}")

    palette_indices = \
        [nearest_palette_index(rgb) for rgb in image.convert("RGB").getdata()]  # 左上から右へ走査
    patterns: list[bytes] = []
    colors: list[bytes] = []

    for yy in range(int(height / 8)):
        pattern_line = bytearray()  # パターンジェネレータ
        color_line = bytearray()  # カラーテーブル
        for xx in range(int(width / 8)):
            for y in range(8):
                base = (yy * 8 + y) * width + xx * 8
                block = palette_indices[base : base + 8]
                block = restrict_two_colors(block)
                color_min = min(block)
                color_max = max(block)
                fg_color = color_max + 1  # MSX palette code (1-15)
                bg_color = color_min + 1

                pattern_byte = 0
                for idx in block:
                    pattern_byte <<= 1
                    if idx == color_max:
                        pattern_byte |= 0x01
                pattern_line.append(pattern_byte & 0xFF)
                dat = (fg_color & 0x0F) << 4 | (bg_color & 0x0F)
                color_line.append(dat)
        patterns.append(bytes(pattern_line))
        colors.append(bytes(color_line))

    tile_rows = height // 8
    return ImageData(pattern=b"".join(patterns), color=b"".join(colors), tile_rows=tile_rows)


def build_init_name_table_func() -> Func:
    def init_name_table_call(block: Block) -> None:
        # 最初に 0~255 のパターンをRAMに用意
        LD.HL_n16(block, WORK_RAM_BASE)
        LD.A_n8(block, 0)
        block.label("CREATE_NAME_TABLE_LOOP")
        LD.mHL_A(block)
        INC.HL(block)
        INC.A(block)
        JR_NZ(block, "CREATE_NAME_TABLE_LOOP")

        # ネームテーブルの初期化x3
        LD.HL_n16(block, WORK_RAM_BASE)
        LD.DE_n16(block, NAME_BASE)
        LD.BC_n16(block, 0x0200)
        CALL(block, LDIRVM)

        LD.HL_n16(block, WORK_RAM_BASE)
        LD.DE_n16(block, NAME_BASE + 0x100)
        LD.BC_n16(block, 0x0200)
        CALL(block, LDIRVM)

        LD.HL_n16(block, WORK_RAM_BASE)
        LD.DE_n16(block, NAME_BASE + 0x200)
        LD.BC_n16(block, 0x0200)
        CALL(block, LDIRVM)

    return Func("init_name_table_call", init_name_table_call)


INIT_NAME_TABLE_CALL = build_init_name_table_func()


def build_boot_bank(
    image_entries: Sequence[ImageEntry],
    header_bytes: Sequence[int],
    fill_byte: int,
) -> bytes:
    if not image_entries:
        raise ValueError("image_entries must not be empty")

    set_debug(True)

    if any(entry.start_bank < 1 or entry.start_bank > 0xFF for entry in image_entries):
        raise ValueError("start_bank must fit in 1 byte and be >= 1")

    b = Block()

    place_msx_rom_header_macro(b, entry_point=ROM_BASE + 0x10)

    b.label("start")
    store_stack_pointer_macro(b)
    enaslt_macro(b)

    LD.A_n8(b, 2)
    CALL(b, CHGMOD)
    set_msx2_palette_default_macro(b)

    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, 0x00)
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    INIT_NAME_TABLE_CALL.call(b)

    LD.A_n8(b, 0)
    LD.mn16_A(b, CURRENT_IMAGE_ADDR)

    # 1枚目のみを表示。ヘッダ先頭の行数やカラーデータ先頭位置は
    # 今後スペースキーで次の画像に進む際に使う想定。
    LD.HL_label(b, "IMAGE_HEADER_TABLE")
    LD.A_mHL(b)
    LD.mn16_A(b, CURRENT_IMAGE_START_BANK_ADDR)
    LD.mn16_A(b, ASCII16_PAGE2_REG)

    INC.HL(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    LD.HL_n16(b, CURRENT_IMAGE_ROW_COUNT_ADDR)
    LD.mHL_E(b)
    INC.HL(b)
    LD.mHL_D(b)

    INC.HL(b)
    LD.A_mHL(b)
    LD.mn16_A(b, CURRENT_IMAGE_COLOR_BANK_ADDR)

    INC.HL(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)
    LD.HL_n16(b, CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
    LD.mHL_E(b)
    INC.HL(b)
    LD.mHL_D(b)

    # パターン／カラーバッファをゼロクリアして、画像より下の領域を黒で埋める。
    XOR.A(b)
    LD.HL_n16(b, PATTERN_RAM_BASE)
    LD.DE_n16(b, PATTERN_RAM_BASE + 1)
    LD.BC_n16(b, PATTERN_RAM_SIZE - 1)
    LD.mHL_A(b)
    b.emit(0xED, 0xB0)  # LDIR

    LD.HL_n16(b, COLOR_RAM_BASE)
    LD.DE_n16(b, COLOR_RAM_BASE + 1)
    LD.BC_n16(b, COLOR_RAM_SIZE - 1)
    LD.mHL_A(b)
    b.emit(0xED, 0xB0)  # LDIR

    # 画像のタイル行数（行数は 8 ドット単位）。SCREEN2 表示領域 24 行を上限に
    # コピーサイズを決める。
    LD.A_mn16(b, CURRENT_IMAGE_ROW_COUNT_ADDR)
    CP.n8(b, SCREEN_TILE_ROWS)
    JR_NC(b, "ROW_COUNT_OK")
    LD.A_n8(b, SCREEN_TILE_ROWS)
    b.label("ROW_COUNT_OK")
    LD.B_A(b)
    LD.C_n8(b, 0x00)

    # パターン（画面24タイル分）
    LD.HL_n16(b, DATA_BANK_ADDR)
    LD.DE_n16(b, PATTERN_RAM_BASE)
    b.emit(0xED, 0xB0)  # LDIR

    ldirvm_macro(b, source_HL=PATTERN_RAM_BASE, dest_DE=PATTERN_BASE, length_BC=PATTERN_RAM_SIZE)

    # カラー
    LD.A_mn16(b, CURRENT_IMAGE_COLOR_BANK_ADDR)
    LD.mn16_A(b, ASCII16_PAGE2_REG)

    # 色データも表示領域分だけ読み出す。
    LD.A_mn16(b, CURRENT_IMAGE_ROW_COUNT_ADDR)
    CP.n8(b, SCREEN_TILE_ROWS)
    JR_NC(b, "ROW_COUNT_OK_COLOR")
    LD.A_n8(b, SCREEN_TILE_ROWS)
    b.label("ROW_COUNT_OK_COLOR")
    LD.B_A(b)
    LD.C_n8(b, 0x00)

    LD.HL_mn16(b, CURRENT_IMAGE_COLOR_ADDRESS_ADDR)
    LD.DE_n16(b, COLOR_RAM_BASE)
    b.emit(0xED, 0xB0)  # LDIR

    ldirvm_macro(b, source_HL=COLOR_RAM_BASE, dest_DE=COLOR_BASE, length_BC=COLOR_RAM_SIZE)

    loop_infinite_macro(b)

    restore_stack_pointer_macro(b)

    INIT_NAME_TABLE_CALL.define(b)

    b.label("IMAGE_HEADER_TABLE")
    DB(b, *header_bytes)

    return bytes(pad_bytes(list(b.finalize(origin=ROM_BASE)), PAGE_SIZE, fill_byte))


def pack_image_into_banks(image: ImageData, fill_byte: int) -> tuple[list[bytes], int]:
    if image.tile_rows <= 0 or image.tile_rows > 0xFFFF:
        raise ValueError("tile_rows must fit in 2 bytes and be positive")

    expected_length = image.tile_rows * 256
    if len(image.pattern) != expected_length:
        raise ValueError("pattern data length mismatch")
    if len(image.color) != expected_length:
        raise ValueError("color data length mismatch")

    payload = bytearray()
    payload.extend(image.pattern)
    payload.extend(image.color)

    total_size = ((len(payload) + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
    padded = bytes(pad_bytes(list(payload), total_size, fill_byte))
    pattern_size = len(image.pattern)
    return [padded[i : i + PAGE_SIZE] for i in range(0, len(padded), PAGE_SIZE)], pattern_size


def build(images: Sequence[ImageData], fill_byte: int = 0xFF) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")
    if not images:
        raise ValueError("images must not be empty")

    image_entries: list[ImageEntry] = []
    data_banks: list[bytes] = []
    next_bank = 1
    header_bytes: list[int] = []

    for i, image in enumerate(images):
        print(f"* packing image #{i} tiles:{image.tile_rows}")

        start_bank = next_bank
        banks, pattern_size = pack_image_into_banks(image, fill_byte)
        color_bank = start_bank + pattern_size // PAGE_SIZE
        color_address = DATA_BANK_ADDR + (pattern_size % PAGE_SIZE)
        if color_bank > 0xFF:
            raise ValueError("color_bank must fit in 1 byte")
        if not DATA_BANK_ADDR <= color_address < DATA_BANK_ADDR + PAGE_SIZE:
            raise ValueError("color_address must stay within a single bank")
        image_entries.append(
            ImageEntry(
                start_bank=start_bank,
                tile_rows=image.tile_rows,
                color_bank=color_bank,
                color_address=color_address,
            )
        )
        data_banks.extend(banks)
        pattern_address = DATA_BANK_ADDR
        print(
            "  pattern generator: "
            f"bank={start_bank} address=0x{pattern_address:04X}"
        )
        print(
            "  color table: "
            f"bank={color_bank} address=0x{color_address:04X}"
        )
        next_bank += len(banks)

        header_bytes.extend(
            [
                start_bank,
                image.tile_rows & 0xFF,
                (image.tile_rows >> 8) & 0xFF,
                # カラーテーブルのバンク＆アドレス情報は パターンジェネレータ側から計算できるが
                # デバッグなどのやりやすさを考え、埋め込んでおく。将来的になくしてもいい。
                # 255 枚 * 6 byte =　1.494.. k Bytes : 現状
                # 255 枚 * 3 byte =　0.747.. k Bytes : 省けるバイト数 1kない 現状のブートバンクは余裕があるので許容
                color_bank & 0xFF,
                color_address & 0xFF,
                (color_address >> 8) & 0xFF,
            ]
        )

    if next_bank > 0x100:
        raise ValueError("Total bank count exceeds 255, which is unsupported")

    header_bytes.extend([0xFF] * IMAGE_HEADER_END_SIZE)

    expected_header_length = (
        len(image_entries) * IMAGE_HEADER_ENTRY_SIZE + IMAGE_HEADER_END_SIZE
    )
    if len(header_bytes) != expected_header_length:
        raise AssertionError("header_bytes length mismatch")

    banks = [build_boot_bank(image_entries, header_bytes, fill_byte)]
    banks.extend(data_banks)
    return b"".join(banks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="縦長 PNG から SCREEN2 縦スクロール ROM を生成するツール"
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        metavar="PNG",
        type=Path,
        nargs="+",
        action="append",
        required=True,
        help="入力 PNG。複数指定すると縦に連結。-i を複数回指定すると別画像として扱う。",
    )
    parser.add_argument(
        "--use-debug-image",
        action="store_true"
    )
    parser.add_argument(
        "--debug-image-index",
        type=int,
        default=0,
        help="--use-debug-image 時に埋め込む番号",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="出力 ROM ファイル名（未指定なら自動命名）",
    )
    parser.add_argument(
        "--background",
        type=str,
        default="#000000",
        help="右側／下側のパディングに使う色 (例: #000000 や 0,0,0)",
    )
    parser.add_argument(
        "--msx1pq-cli",
        type=Path,
        help="msx1pq_cli 実行ファイルのパス（未指定なら PATH を検索）",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        help="中間ファイルを書き出すワークフォルダ（未指定なら一時フォルダ）",
    )
    parser.add_argument(
        "--fill-byte",
        type=int_from_str,
        default=0xFF,
        help="未使用領域の埋め値 (default: 0xFF)",
    )
    return parser.parse_args()


def concatenate_images_vertically(images: Sequence[Image.Image]) -> Image.Image:
    height = sum(img.height for img in images)
    canvas = Image.new("RGB", (TARGET_WIDTH, height))

    y = 0
    for img in images:
        canvas.paste(img, (0, y))
        y += img.height

    return canvas


def _embed_label(data: bytearray, label: str) -> None:
    label_bytes = label.encode("ascii")
    length = len(data)
    for idx, value in enumerate(label_bytes):
        if idx >= length:
            break
        data[idx] = value


def _fill_with_story(data: bytearray, story: str, start: int = 0) -> None:
    story_bytes = story.encode("ascii")
    if not story_bytes:
        return

    for idx in range(start, len(data)):
        data[idx] = story_bytes[(idx - start) % len(story_bytes)]


def create_debug_image_data_list(debug_image_index: int) -> List[ImageData]:
    pattern = bytearray()
    for i in range(PATTERN_RAM_SIZE):
        line_block = (i // 8) % 4
        if line_block == 0:
            pattern.append(0xFF)
        elif line_block == 1:
            pattern.append(0x00)
        elif line_block == 2:
            pattern.append(0xAA)
        else:
            pattern.append(0x55)

    color = bytearray()
    for i in range(COLOR_RAM_SIZE):
        fg = (i // 8) % 15 + 1
        bg = (i // 64) % 16
        if fg == bg:
            bg = (bg + 1) % 16
        color.append((fg << 4) | bg)

    if debug_image_index > 0:
        pattern_label = f"PATTERN[{debug_image_index}] SCROLL VIEWER DEBUG"
        color_label = f"color[{debug_image_index}] scroll viewer debug"
        _embed_label(pattern, pattern_label)
        _embed_label(color, color_label)

        if debug_image_index > 1:
            story = "scroll viewer debug story fills the screen with test data. "
            pattern_story = story.upper()
            _fill_with_story(pattern, pattern_story, start=len(pattern_label))
            _fill_with_story(color, story, start=len(color_label))

    return [ImageData(pattern=bytes(pattern), color=bytes(color), tile_rows=SCREEN_TILE_ROWS)]


def main() -> None:
    args = parse_args()

    background = parse_color(args.background)
    msx1pq_cli = find_msx1pq_cli(args.msx1pq_cli)

    input_groups: list[list[Path]] = [list(group) for group in args.input]
    prepared_images: list[tuple[str, Image.Image]] = []
    image_data_list: list[ImageData] = []
    rom: bytes

    if args.use_debug_image:
        image_data_list = create_debug_image_data_list(args.debug_image_index)
    else:
        for group in input_groups:
            if not group:
                raise SystemExit("Empty input group is not allowed")

            loaded_images: list[Image.Image] = []
            for path in group:
                if not path.is_file():
                    raise SystemExit(f"not found: {path}")
                loaded_images.append(prepare_image(Image.open(path), background))

            merged = loaded_images[0] if len(loaded_images) == 1 else concatenate_images_vertically(loaded_images)
            group_name = "-".join(path.stem for path in group)
            prepared_images.append((group_name, merged))

        with open_workdir(args.workdir) as workdir:
            for idx, (group_name, image) in enumerate(prepared_images):
                prepared_path = workdir / f"{idx:02d}_{group_name}_prepared.png"
                image.save(prepared_path)
                # print(f"prepared iamge #{idx} {prepared_path} created")

                quantized_path = run_msx1pq_cli(msx1pq_cli, prepared_path, workdir)
                os.unlink(prepared_path)
                quantized_image = Image.open(quantized_path)
                print(f"* quantized iamge #{idx} {quantized_path} created")
                image_data = build_image_data_from_image(quantized_image)
                image_data_list.append(image_data)

    if not image_data_list:
        raise SystemExit("No images were prepared")

    rom = build(image_data_list, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        if len(prepared_images) == 1:
            name = f"{prepared_images[0][0]}_scroll[{image_data_list[0].tile_rows * 8}px][ASCII16]"
        elif prepared_images:
            name = f"{prepared_images[0][0]}_scroll{len(prepared_images)}imgs[ASCII16]"
        else:
            name = f"debug_scroll{args.debug_image_index}[ASCII16]"
        out = Path.cwd() / f"{name}.rom"

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(f"ERROR! failed to write ROM file: {exc}") from exc
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
