#!/usr/bin/env python3
"""
MSX1 縦スクロール ROM ビルダー。

縦長の PNG画像 を １枚（今後複数枚に機能拡張予定）受け取り 以下の手順で ROM を生成する:

1. 入力 PNG を左端を基準で横256pxにトリミング。足りない場合は右側を背景色でパディング。
2. 縦は 8px 単位になるように下側へ背景色でパディング。
3. `msx1pq_cli`（PATH もしくは引数で指定）を用いて MSX1 ルール準拠の PNG を生成。
    ※ 美しくするための前処理や加工は行われず機械的に変換する。
    質の高い画像にしたい場合はあらかじめmsx1pq_cliや他のツールで対応しておく。
4. １ラインデータ（パターン + 色: 各 32byte/行）ごとの可変長データ（RowPackage）に加工して
   ASCII16 MegaROM のデータバンクに格納。
5. ビューアーとともにROMデータとして出力。

RowPackage:
    pattern[1] ; パターンジェネレータ（1バイト）x 32 文字
    color[1]   ; カラーテーブル（1バイト）x 32 文字
    合計 64 バイト / 1 ライン

実装中
・RowPackageを並べたデータを1画面文表示
・指定位置から全画面書き換え

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
import shutil
import subprocess
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Sequence

from mmsxxasmhelper.core import (
    ADD,
    Block,
    CALL,
    CP,
    DEC,
    Func,
    INC,
    JR,
    JR_C,
    JR_NC,
    JR_NZ,
    JR_Z,
    LD,
    OR,
    POP,
    PUSH,
    XOR,
    DB,
    DW,
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
)
from mmsxxasmhelper.utils import pad_bytes
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
TARGET_WIDTH = 256
VISIBLE_ROWS = 24
ROW_BYTES = 64
ROWS_PER_BANK = PAGE_SIZE // ROW_BYTES

CHSNS = 0x009C
CHGET = 0x009F

KEY_SPACE = 0x20
KEY_UP = 0x1E
KEY_DOWN = 0x1F

CURRENT_IMAGE_ADDR = WORK_RAM_BASE
SCROLL_OFFSET_ADDR = WORK_RAM_BASE + 1


@dataclass
class ImageEntry:
    start_bank: int
    row_count: int


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
    out_suffix = "_msx"
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

    counts = Counter(indices)
    allowed = [color for color, _ in counts.most_common(2)]

    remapped: list[int] = []
    for idx in indices:
        if idx in allowed:
            remapped.append(idx)
            continue
        remapped.append(min(allowed, key=lambda candidate: palette_distance(idx, candidate)))

    return remapped


def build_row_packages_from_image(image: Image.Image) -> tuple[bytes, int]:
    """Convert a quantized image into RowPackage bytes and return (bytes, row_count)."""

    width, height = image.size
    if width != TARGET_WIDTH:
        raise ValueError(f"Width must be {TARGET_WIDTH}, got {width}")

    palette_indices = [nearest_palette_index(rgb) for rgb in image.convert("RGB").getdata()]

    rows: list[bytes] = []
    for y in range(height):
        base = y * width
        pattern_line = bytearray()
        color_line = bytearray()

        for tx in range(32):
            start = base + tx * 8
            block = palette_indices[start : start + 8]
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
            color_line.append(((fg_color & 0x0F) << 4) | (bg_color & 0x0F))

        rows.append(bytes(pattern_line + color_line))

    return b"".join(rows), height


def build_init_name_table_func() -> Func:
    def init_name_table_call(block: Block) -> None:
        # 最初に 0~255 のパターンをRAMに用意
        LD.HL_n16(block, WORK_RAM_BASE)
        LD.A_n8(block, 0)
        block.label("CREATE_NAME_TABLE_LOOP")
        LD.mHL_A(block)
        LD.mHL_n8(block, 0)
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


def build_boot_bank(image_entries: Sequence[ImageEntry], fill_byte: int) -> bytes:
    if not image_entries:
        raise ValueError("image_entries must not be empty")

    start_banks = [entry.start_bank for entry in image_entries]
    row_counts = [entry.row_count for entry in image_entries]

    if any(bank < 1 or bank > 0xFF for bank in start_banks):
        raise ValueError("start_bank must fit in 1 byte and be >= 1")
    if any(count <= 0 or count > 0xFFFF for count in row_counts):
        raise ValueError("row_count must fit in 2 bytes and be positive")

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
    LD.HL_n16(b, 0)
    LD.mn16_HL(b, SCROLL_OFFSET_ADDR)

    b.label("DRAW_CURRENT_IMAGE")
    LD.A_mn16(b, CURRENT_IMAGE_ADDR)
    LD.E_A(b)  # E = index

    LD.HL_label(b, "IMAGE_START_BANK_TABLE")
    LD.D_n8(b, 0)
    ADD.HL_DE(b)
    LD.A_mHL(b)
    LD.D_A(b)  # D = start bank

    LD.DE_n16(b, PATTERN_BASE)
    LD.IY_n16(b, COLOR_BASE)

    LD.HL_mn16(b, SCROLL_OFFSET_ADDR)
    LD.B_H(b)
    LD.C_L(b)  # BC = current offset (rows)

    LD.A_n8(b, VISIBLE_ROWS)
    b.label("DRAW_ROW_LOOP")
    LD.A_B(b)
    ADD.A_D(b)
    LD.mn16_A(b, ASCII16_PAGE2_REG)

    LD.L_C(b)
    LD.H_n8(b, 0)
    for _ in range(6):
        ADD.HL_HL(b)
    LD.DE_n16(b, DATA_BANK_ADDR)
    ADD.HL_DE(b)

    PUSH.BC(b)
    LD.BC_n16(b, 32)
    CALL(b, LDIRVM)

    PUSH.DE(b)
    PUSH.IY(b)
    POP.DE(b)

    LD.BC_n16(b, 32)
    CALL(b, LDIRVM)

    LD.BC_n16(b, 32)
    ADD.IY_BC(b)
    POP.DE(b)

    POP.BC(b)
    INC.BC(b)
    DEC.A(b)
    JR_NZ(b, "DRAW_ROW_LOOP")

    JR(b, "MAIN_LOOP")

    b.label("MAIN_LOOP")
    CALL(b, CHSNS)
    CP.n8(b, 0)
    JR_Z(b, "MAIN_LOOP")

    CALL(b, CHGET)
    CP.n8(b, KEY_SPACE)
    JR_Z(b, "HANDLE_NEXT_IMAGE")
    CP.n8(b, KEY_UP)
    JR_Z(b, "HANDLE_SCROLL_UP")
    CP.n8(b, KEY_DOWN)
    JR_Z(b, "HANDLE_SCROLL_DOWN")
    JR(b, "MAIN_LOOP")

    b.label("HANDLE_NEXT_IMAGE")
    LD.A_mn16(b, CURRENT_IMAGE_ADDR)
    INC.A(b)
    CP.n8(b, len(image_entries))
    JR_C(b, "STORE_IMAGE_INDEX")
    LD.A_n8(b, 0)

    b.label("STORE_IMAGE_INDEX")
    LD.mn16_A(b, CURRENT_IMAGE_ADDR)
    LD.HL_n16(b, 0)
    LD.mn16_HL(b, SCROLL_OFFSET_ADDR)
    JR(b, "DRAW_CURRENT_IMAGE")

    b.label("HANDLE_SCROLL_UP")
    LD.HL_mn16(b, SCROLL_OFFSET_ADDR)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "MAIN_LOOP")
    DEC.HL(b)
    LD.mn16_HL(b, SCROLL_OFFSET_ADDR)
    JR(b, "DRAW_CURRENT_IMAGE")

    b.label("HANDLE_SCROLL_DOWN")
    # Load row count for current image
    LD.A_mn16(b, CURRENT_IMAGE_ADDR)
    LD.E_A(b)
    LD.HL_label(b, "IMAGE_ROW_COUNT_TABLE")
    LD.D_n8(b, 0)
    ADD.HL_DE(b)
    ADD.HL_DE(b)
    LD.E_mHL(b)
    INC.HL(b)
    LD.D_mHL(b)

    LD.A_D(b)
    OR.E(b)
    JR_Z(b, "MAIN_LOOP")

    LD.H_D(b)
    LD.L_E(b)
    LD.DE_n16(b, VISIBLE_ROWS)
    XOR.A(b)
    b.emit(0xED, 0x52)  # SBC HL,DE
    JR_C(b, "MAIN_LOOP")
    JR_Z(b, "MAIN_LOOP")

    LD.HL_mn16(b, SCROLL_OFFSET_ADDR)
    LD.D_H(b)
    LD.E_L(b)
    INC.DE(b)
    XOR.A(b)
    b.emit(0xED, 0x52)  # SBC HL,DE (HL = max_offset - candidate)
    JR_C(b, "MAIN_LOOP")

    LD.HL_n16(b, SCROLL_OFFSET_ADDR)
    LD.A_E(b)
    LD.mHL_A(b)
    INC.HL(b)
    LD.A_D(b)
    LD.mHL_A(b)
    JR(b, "DRAW_CURRENT_IMAGE")

    restore_stack_pointer_macro(b)

    INIT_NAME_TABLE_CALL.define(b)

    b.label("IMAGE_START_BANK_TABLE")
    DB(b, *start_banks)

    b.label("IMAGE_ROW_COUNT_TABLE")
    for count in row_counts:
        DW(b, count)

    return bytes(pad_bytes(list(b.finalize(origin=ROM_BASE)), PAGE_SIZE, fill_byte))


def split_row_packages_into_banks(row_packages: bytes, fill_byte: int) -> list[bytes]:
    if len(row_packages) % ROW_BYTES != 0:
        raise ValueError("row_packages length must be a multiple of ROW_BYTES")

    banks: list[bytes] = []
    current = bytearray()

    for offset in range(0, len(row_packages), ROW_BYTES):
        row = row_packages[offset : offset + ROW_BYTES]
        if len(current) + len(row) > PAGE_SIZE:
            banks.append(bytes(pad_bytes(list(current), PAGE_SIZE, fill_byte)))
            current = bytearray()
        current.extend(row)

    banks.append(bytes(pad_bytes(list(current), PAGE_SIZE, fill_byte)))
    return banks


def build(image_row_packages: Sequence[bytes], fill_byte: int = 0xFF) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")
    if not image_row_packages:
        raise ValueError("image_row_packages must not be empty")

    image_entries: list[ImageEntry] = []
    data_banks: list[bytes] = []
    next_bank = 1

    for package in image_row_packages:
        if not package:
            raise ValueError("row_packages must not be empty")

        banks = split_row_packages_into_banks(package, fill_byte)
        image_entries.append(ImageEntry(start_bank=next_bank, row_count=len(package) // ROW_BYTES))
        data_banks.extend(banks)
        next_bank += len(banks)

    if next_bank > 0x100:
        raise ValueError("Total bank count exceeds 255, which is unsupported")

    banks = [build_boot_bank(image_entries, fill_byte)]
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


def main() -> None:
    args = parse_args()

    background = parse_color(args.background)
    msx1pq_cli = find_msx1pq_cli(args.msx1pq_cli)

    input_groups: list[list[Path]] = [list(group) for group in args.input]
    prepared_images: list[tuple[str, Image.Image]] = []

    for group in input_groups:
        if not group:
            raise SystemExit("Empty input group is not allowed")

        loaded_images: list[Image.Image] = []
        for path in group:
            if not path.is_file():
                raise SystemExit(f"not found: {path}")
            loaded_images.append(prepare_image(Image.open(path), background))

        merged = loaded_images[0] if len(loaded_images) == 1 else concatenate_images_vertically(loaded_images)
        group_name = "+".join(path.stem for path in group)
        prepared_images.append((group_name, merged))

    row_packages_list: list[bytes] = []
    row_counts: list[int] = []

    with open_workdir(args.workdir) as workdir:
        for idx, (group_name, image) in enumerate(prepared_images):
            prepared_path = workdir / f"{idx:02d}_{group_name}_prepared.png"
            image.save(prepared_path)

            quantized_path = run_msx1pq_cli(msx1pq_cli, prepared_path, workdir)
            quantized_image = Image.open(quantized_path)
            row_packages, row_count = build_row_packages_from_image(quantized_image)

            if row_count % 8 != 0:
                raise SystemExit("Internal error: quantized image height must be 8-dot aligned")

            row_packages_list.append(row_packages)
            row_counts.append(row_count)

        rom = build(row_packages_list, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        if len(prepared_images) == 1:
            name = f"{prepared_images[0][0]}_scroll[{row_counts[0]}px][ASCII16]"
        else:
            name = f"{prepared_images[0][0]}_scroll{len(prepared_images)}imgs[ASCII16]"
        out = Path.cwd() / f"{name}.rom"

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(f"ERROR! failed to write ROM file: {exc}") from exc
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
