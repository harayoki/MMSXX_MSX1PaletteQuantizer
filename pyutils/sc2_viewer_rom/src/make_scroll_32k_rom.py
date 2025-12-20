#!/usr/bin/env python3
"""
MSX1 用・2画面縦スクロールエンジン（8ドット単位）ROM ビルダー仕様。
MSX1 で 2枚の SCREEN2 画像を持ち、カーソル上下で 8ドット＝1キャラ行単位でスクロール
ネームテーブル パターンジェネレータ カラーテーブル を ROM から VRAM に反映する
8ドットスクロールエンジンを構築する。

ASCII16 の MegaROM として、バンク0にエンジンと初期化コードを、以降のバンクに
RowPackage を配置する。mmsxxasmhelper のマクロを利用してスロット有効化、スタック
レジスタ退避、MSX2 のデフォルトパレット初期化などをまとめて行う。

ROM 内部構造
スクロール処理で1行にアクセスしやすいデータ構造をあらかじめ作っておく。
RowPackage:
1 logical 行（SCREEN2 の 1行）を以下の構造で ROM に保存する：
    pattern[1] ; パターンジェネレータ（1バイト）x 32文字
    color[1] ; カラーテーブル（1バイト）x 32文字
    32 バイト + 32 バイト = 64 バイト
    合計 64 バイト
必要ない物
    ネームテーブル（1行 32文字）… 動的に決定できる
    スプライト属性テーブル
    スプライトパターンジェネレータ

画像は 2 枚（各 24 行）なので：
image1 RowPackage[ 0] ~ RowPackage[23]
image1 RowPackage[24] ~ RowPackage[47]
64 × 48 = 3072 バイト → 32KB ROM に十分余裕をもって収まる。

＊SCREEN2 VRAM 仕様
Pattern Generator : 0000h–17FFh
Name Table : 1800h–1AFFh
Color Table : 2000h–37FFh

＊スクロール位置を指定した全面書き換え
top_row(0~24)の値を見て2画面分のRowPackage全体必要な部分を決定。
ネームテーブルは機械的に埋めて、パターンジェネレータとカラーテーブルは
RowPackageから該当部分を取り出してVRAMに書き込む。

＊手抜きなスクロール処理

差分は考えずスクロール位置を指定した全面書き換えを行う。
まずはこれで実装を行い画面のみだれやパフォーマンスが許容できるか確認する。

＊まじめなスクロール処理

まずVRAM領域が3分割で荒れている事は考えずに知世を記す。

＞カラーテーブル・パターンジェネレータ
▼ 下スクロール top_row++（最大 24）
現在の一番上の行に対応するテーブルを次にスクロールして出てくる内容[top_row+23]で書き換える

▲ 上スクロール top_row--（最小 0）
現在の一番下の行に対応するテーブルを次にスクロールして出てくる内容[top_row]で書き換える

＞ネームテーブル
▼ 下スクロール ネームテーブル行を上へ1行詰める
 見えなくなる一番上の行内容をを一番下の行に移動する
▲ 上スクロール（scroll up）  ネームテーブル行を下へ1行詰める
　見えなくなる一番下の行内容をを一番↑の行に移動する

以上で基本的な考え方はいいのだが、実際には VRAM 領域が縦に3分割して
8行ずつになっているため、8行単位で処理を行う必要がある。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

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

PAGE_SIZE = 0x4000
ROM_BASE = 0x4000

ASCII16_PAGE2_REG = 0x7000
DATA_BANK_ADDR = 0x8000

VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7

# VDP / SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE = 0x1800
COLOR_BASE = 0x2000

# MSX RAM での作業領域
WORK_RAM_BASE = 0xC000

ROW_COUNT = 24


def int_from_str(value: str) -> int:
    return int(value, 0)


def sc2_to_vram(sc2_bytes: bytes) -> bytes:
    length = len(sc2_bytes)
    if length == VRAM_SIZE + SC2_HEADER_SIZE:
        sc2_bytes = sc2_bytes[SC2_HEADER_SIZE:]
        length = len(sc2_bytes)
    if length != VRAM_SIZE:
        raise ValueError("SC2 image must be 0x4000 bytes (optionally +7 header)")

    vram = bytearray(sc2_bytes)
    vram[0x3800:0x4000] = b"\x00" * 0x800
    return bytes(vram)


def build_row_packages(image_bytes: bytes) -> bytes:
    """
    1画面のバイト列から RowPackage[24] を生成。
    RowPackage:
        pattern * 32
        color   * 32
    """
    if len(image_bytes) != VRAM_SIZE:
        raise ValueError("image must be 0x4000 bytes after normalization")

    pattern_gen = image_bytes[:0x1800]
    color_table = image_bytes[0x2000:0x3800]

    rows: list[bytes] = []
    for row in range(ROW_COUNT):
        pattern_line = pattern_gen[row * 32 : (row + 1) * 32]
        color_line = color_table[row * 32 : (row + 1) * 32]
        rows.append(pattern_line + color_line)

    return b"".join(rows)


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


def build_draw_page_func() -> Func:
    def draw_page(block: Block) -> None:
        # C = data bank number
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)

        LD.HL_n16(block, DATA_BANK_ADDR)
        LD.DE_n16(block, PATTERN_BASE)
        LD.IY_n16(block, COLOR_BASE)
        LD.A_n8(block, ROW_COUNT)

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


DRAW_PAGE_CALL = build_draw_page_func()


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


def build(image0: bytes, image1: bytes, fill_byte: int = 0xFF) -> bytes:
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")

    packages = [build_row_packages(image0), build_row_packages(image1)]

    banks = [
        build_boot_bank(range(1, len(packages) + 1), fill_byte),
    ]
    for pkg in packages:
        banks.append(build_data_bank(pkg, fill_byte))

    return b"".join(banks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MSX1 SCREEN2 1枚目表示 ROM ビルダー（スクロール前段階＋色＆パレット）"
    )
    parser.add_argument("image0", type=Path, help="1枚目 .sc2 (上側 / まず表示する画像)")
    parser.add_argument("image1", type=Path, help="2枚目 .sc2 (今は未使用)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="出力 ROM ファイル名（未指定なら自動命名）",
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

    if not args.image0.is_file():
        raise SystemExit(f"not found: {args.image0}")
    if not args.image1.is_file():
        raise SystemExit(f"not found: {args.image1}")

    img0 = sc2_to_vram(args.image0.read_bytes())
    img1 = sc2_to_vram(args.image1.read_bytes())

    rom = build(img0, img1, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        name = f"{args.image0.stem}_scroll_{args.image1.stem}[ASCII16]"
        out = args.image0.with_name(name).with_suffix(".rom")

    try:
        out.write_bytes(rom)
    except Exception as exc:  # pragma: no cover - CLI error path
        raise SystemExit(f"ERROR! failed to write ROM file: {exc}") from exc
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
