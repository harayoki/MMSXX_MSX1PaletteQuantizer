#!/usr/bin/env python3
"""
MSX1 縦スクロール ROM ビルダー。

これまで 2 枚の `.sc2` を受け取っていたが、代わりに縦長の PNG を 1 枚受け取り、
以下の手順で ROM を生成する:

1. 入力 PNG を左上基準で横 256px にトリミング。足りない場合は右側を背景色でパディング。
2. 縦は 8px 単位になるように下側へパディング（背景色指定可 / 既定は黒）。
3. C++ 製 `msx1pq_cli`（PATH もしくは引数で指定）で前処理なしのまま MSX1 ルール準拠の
   パレット PNG を生成。
4. 8 ドット幅内 2 色ルールに従うラインデータ（パターン + 色: 各 32byte/行）へ変換し、
   ASCII16 MegaROM のデータバンクに格納。

RowPackage:
    pattern[1] ; パターンジェネレータ（1バイト）x 32 文字
    color[1]   ; カラーテーブル（1バイト）x 32 文字
    合計 64 バイト / 1 ライン

VRAM のパターンジェネレータ / カラーテーブル全面を書き換える前提のシンプルな ROM を
構築する。スクロール処理自体は別途マシン語側で行う想定。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Sequence
from tempfile import TemporaryDirectory

from mmsxxasmhelper.core import ADD, Block, CALL, DEC, Func, INC, JR, JR_NZ, LD, POP, PUSH
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


def prepare_image(path: Path, background: tuple[int, int, int]) -> Image.Image:
    """Crop/pad the input to 256px width and multiple-of-8 height."""

    img = Image.open(path).convert("RGB")
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


def build_draw_page_func(row_count: int) -> Func:
    def draw_page(block: Block) -> None:
        # C = data bank number
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)

        LD.HL_n16(block, DATA_BANK_ADDR)
        LD.DE_n16(block, PATTERN_BASE)
        LD.IY_n16(block, COLOR_BASE)
        LD.A_n8(block, row_count)

        block.label("DRAW_PAGE_LOOP")
        LD.BC_n16(block, 32)
        CALL(block, LDIRVM)

        PUSH.DE(block)
        PUSH.IY(block)
        POP.DE(block)

        LD.BC_n16(block, 32)
        CALL(block, LDIRVM)

        LD.BC_n16(block, 32)
        ADD.IY_BC(block)
        POP.DE(block)

        DEC.A(block)
        JR_NZ(block, "DRAW_PAGE_LOOP")

    return Func("draw_page_call", draw_page)


DRAW_PAGE_CALL = build_draw_page_func(VISIBLE_ROWS)


def build_boot_bank(data_banks: Iterable[int], fill_byte: int) -> bytes:
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

    for bank_index in data_banks:
        LD.C_n8(b, bank_index)
        DRAW_PAGE_CALL.call(b)
        break

    loop_start = "main_loop"
    b.label(loop_start)
    JR(b, loop_start)

    restore_stack_pointer_macro(b)

    INIT_NAME_TABLE_CALL.define(b)
    DRAW_PAGE_CALL.define(b)

    return bytes(pad_bytes(list(b.finalize(origin=ROM_BASE)), PAGE_SIZE, fill_byte))


def build_data_bank(row_packages: bytes, fill_byte: int) -> bytes:
    return bytes(pad_bytes(list(row_packages), PAGE_SIZE, fill_byte))


def build(row_packages: bytes, fill_byte: int = 0xFF) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")
    if not row_packages:
        raise ValueError("row_packages must not be empty")

    data_banks: list[bytes] = []
    for offset in range(0, len(row_packages), PAGE_SIZE):
        chunk = row_packages[offset : offset + PAGE_SIZE]
        data_banks.append(build_data_bank(chunk, fill_byte))

    banks = [build_boot_bank(range(1, len(data_banks) + 1), fill_byte)]
    banks.extend(data_banks)
    return b"".join(banks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="縦長 PNG から SCREEN2 縦スクロール ROM を生成するツール"
    )
    parser.add_argument("input", type=Path, help="縦長 PNG（横256pxトリミング／右パディング）")
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


def main() -> None:
    args = parse_args()

    if not args.input.is_file():
        raise SystemExit(f"not found: {args.input}")

    background = parse_color(args.background)
    msx1pq_cli = find_msx1pq_cli(args.msx1pq_cli)

    with open_workdir(args.workdir) as workdir:
        prepared = workdir / f"{args.input.stem}_prepared.png"
        prepared_image = prepare_image(args.input, background)
        prepared_image.save(prepared)

        quantized_path = run_msx1pq_cli(msx1pq_cli, prepared, workdir)
        quantized_image = Image.open(quantized_path)
        row_packages, row_count = build_row_packages_from_image(quantized_image)

        if row_count % 8 != 0:
            raise SystemExit("Internal error: quantized image height must be 8-dot aligned")

        rom = build(row_packages, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        name = f"{args.input.stem}_scroll[{row_count}px][ASCII16]"
        out = args.input.with_name(name).with_suffix(".rom")

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(f"ERROR! failed to write ROM file: {exc}") from exc
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
