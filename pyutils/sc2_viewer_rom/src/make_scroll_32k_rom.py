#!/usr/bin/env python3
"""
MSX1 用・2画面縦スクロールエンジン（8ドット単位）ROM ビルダー仕様
MSX1 で 2枚の SCREEN2 画像を持ち、 カーソル上下で 8ドット＝1キャラ行単位でスクロール
ネームテーブル パターンジェネレータ カラーテーブル を ROM から VRAM に反映する
8ドットスクロールエンジンを構築する

ROM 内部構造
スクロール処理で1行にアクセスしやすいデータ構造をあらかじめ作っておく。
RowPackage:
1 logical 行（SCREEN2 の 1行）を以下の構造で ROM に保存する：
    pattern[8] ; パターンジェネレータ（8バイト）x 32文字
    color[8] ; カラーテーブル（8バイト）x 32文字
    32 バイト + (8 + 8) バイト × 32 = 512
    合計 512 バイト
必要ない物
    ネームテーブル（1行 32文字）… 動的に決定できる
    スプライト属性テーブル
    スプライトパターンジェネレータ

画像は 2 枚（各 24 行）なので：
image1 RowPackage[ 0] ~ RowPackage[23]
image1 RowPackage[24] ~ RowPackage[47]
512 × 48 = 21504 バイト（21KB） → 32KB ROM に 11kB余裕をもって収まる。

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
from typing import List

from mmsxxasmhelper.core import *
from mmsxxasmhelper.msxutils import (
    ldirvm_macro,
    place_msx_rom_header_macro,
    set_msx2_palette_default_macro,
    set_screen_mode_macro,
    set_screen_colors_macro,
)
from mmsxxasmhelper.utils import (
    loop_infinite_macro, debug_trap, set_debug
)

ROM_SIZE = 0x8000      # 32KB
ROM_BASE = 0x4000

VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7

# VDP / SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE    = 0x1800
COLOR_BASE   = 0x2000

# MSX RAM での作業領域
WORK_RAM_BASE = 0xC000


def validate_sc2_bytes(sc2_bytes: bytes) -> bytes:
    """
    SCREEN2 VRAM データの正規化
    """
    length = len(sc2_bytes)
    # 7バイトヘッダ付き 0x4000 + 7
    if length == VRAM_SIZE + SC2_HEADER_SIZE:
        sc2_bytes = sc2_bytes[SC2_HEADER_SIZE:]
        length = len(sc2_bytes)
    assert length == VRAM_SIZE, f"Invalid SC2 size: {length:#x}"  # must be 16k
    # ねんのためスプライト定義と属性テーブルを0クリア
    vram = bytearray(sc2_bytes)
    for addr in range(0x3800, 0x4000):
        vram[addr] = 0x00
    return bytes(vram)


# def trimmed_to_full_vram(trimmed: bytes) -> bytes:
#     """
#     トリム済み 0x3780 バイトから、フル VRAM 0x4000 バイトに戻す。
#     → この関数は開発時以外必要ない
#     トリム形式:
#         0000–1AFF   → VRAM 0000–1AFF
#         1B00–377F   → VRAM 1B80–37FF
#     それ以外の VRAM 領域は 0 クリア。
#     """
#     if len(trimmed) != IMAGE_LENGTH:
#         raise ValueError("trimmed image must be 0x3780 bytes")
#     vram = bytearray([0x00] * VRAM_SIZE)
#     # 0000–1AFF
#     vram[0x0000:0x1B00] = trimmed[0x0000:0x1B00]
#     # 1B80–37FF
#     vram[0x1B80:0x3800] = trimmed[0x1B00:0x3780]
#     return bytes(vram)

def vram_to_trimmed_offset(addr: int) -> int:
    """
    VRAM アドレス 0x0000–0x37FF を、
    トリム済み 0x3780 バッファ上のオフセットに変換。
    → この関数は最終的に使わなくなる？
    """
    if addr < 0x1B00:
        return addr
    # 1B80–37FF が 1B00–35FF に詰められている
    return addr - 0x80


def build_row_packages(image_bytes: bytes) -> bytes:
    """
    1画面のバイト列から RowPackage[24] を生成。@
    RowPackage:
        pattern * 32
        color   * 32
    """
    if len(image_bytes) != VRAM_SIZE:
        raise ValueError("trimmed image must be 0x3780 bytes")

    """
    ＊SCREEN2 VRAM 仕様
    Pattern Generator : 0000h–17FFh
    Name Table : 1800h–1AFFh
    Color Table : 2000h–37FFh
    """
    pattern_gen = image_bytes[:0x1800]
    color_table = image_bytes[0x2000:0x3800]  # カラーテーブル

    rows: List[bytes] = []
    for row in range(24):
        bank = row // 8  # 0,1,2 (SCREEN2 の 8行単位バンク)

        pattern_line = pattern_gen[row * 32:(row + 1) * 32]
        pattern_line_as_str = " ".join(f"{b:02X}" for b in pattern_line)
        print(f"#{row} pattern_line({((bank * 0x800) + (row % 8) * 32):04X}) {pattern_line_as_str}")
        color_line   = color_table[row * 32:(row + 1) * 32]
        color_line_as_str = " ".join(f"{b:02X}" for b in color_line)
        print(f"#{row} color_line({((bank * 0x800) + (row % 8) * 32):04X}) {color_line_as_str}")

        pkg: bytes = pattern_line + color_line  # 64 bytes
        rows.append(pkg)

    return b"".join(rows)


def init_name_table_call(b: Block) -> None:

    # 最初に 0~255 のパターンをRAMに用意
    # HL = WORK_RAM_BASE
    LD.HL_n16(b, WORK_RAM_BASE)
    # A = 0~255
    LD.A_n8(b, 0)
    b.label("CREATE_NAME_TABLE_LOOP")
    # (HL) = A
    LD.mHL_A(b)
    # HL++
    INC.HL(b)
    # A++
    INC.A(b)
    # 256回ループ
    JP_Z(b, "CREATE_NAME_TABLE_LOOP")

    # ネームテーブルの初期化x3
    ldirvm_macro(b, source=WORK_RAM_BASE, dest=NAME_BASE        , length=0x0200)
    ldirvm_macro(b, source=WORK_RAM_BASE, dest=NAME_BASE + 0x100, length=0x0200)
    ldirvm_macro(b, source=WORK_RAM_BASE, dest=NAME_BASE + 0x200, length=0x0200)


INIT_NAME_TABLE_CALL = Func("init_name_table_call", init_name_table_call)


def draw_page_call(b: Block) -> None:
    """
    1ページ分の RowPackage データを VRAM に転送する関数
    """
    start_addr = "PACKED_DATA"

    # HL = RowPackage 先頭
    pos = b.emit(0x21, 0x00, 0x00)  # LD HL,start_addr
    b.add_abs16_fixup(pos + 1, start_addr)

    # DE = PATTERN_BASE / IY = COLOR_BASE
    LD.DE_n16(b, PATTERN_BASE)
    LD.IY_n16(b, COLOR_BASE)

    # A = 24 行分処理
    LD.A_n8(b, 24)

    b.label("DRAW_PAGE_LOOP")

    # パターン 32バイトコピー BCレジスタ破壊
    ldirvm_macro(b, length=31)

    # 次のパターン出力先を退避
    b.emit(0xD5)  # PUSH DE

    # カラーの出力先 (IY) を DE にセット
    b.emit(0xFD, 0xE5)  # PUSH IY
    b.emit(0xD1)        # POP DE

    # 1行分転送 BCレジスタ破壊
    ldirvm_macro(b, length=32)

    # IY += 32 (次行のカラー位置)
    LD.BC_n16(b, 32)
    b.emit(0xFD, 0x09)  # ADD IY,BC

    # 次行のパターン出力先を復帰
    b.emit(0xD1)  # POP DE

    # 24行処理するまでループ
    b.emit(0x3D)  # DEC A
    JP_Z(b, "DRAW_PAGE_LOOP")


DRAW_PAGE_CALL = Func("draw_page_call", draw_page_call)


def build_rom(packed_data: bytes) -> bytes:
    """
    ROMに書き込むコードを組み立てる。
    """

    set_debug(True)

    b = Block()

    # エントリラベル（ROM_HEADER もここに置く）
    b.label("start")

    # ROM ヘッダ配置（MSX がここを 0x4000 とみなす）
    place_msx_rom_header_macro(b)

    # ----- ここから 0x4010: 実際に実行されるコード -----

    # SCREEN 2 に変更: LD A,2 / CALL 005Fh (CHGMOD)
    set_screen_mode_macro(b, 2)

    # 色: 前景=白 / 背景=黒 / 枠=黒
    set_screen_colors_macro(b, 0x0F, 0x00, 0x00)

    # MSX2 以上ならパレット設定
    # 真っ黒になってしまうバグがあるので現状何もしないコードになっている
    # set_msx2_palette_default_macro(b)

    # ネームテーブル初期化
    INIT_NAME_TABLE_CALL.call(b)

    # DEBUG=True なら HALT
    debug_trap(b)

    # 1枚目の絵を出す
    # PACKED_DATA の先頭 (1 枚目) を描画
    # DRAW_PAGE_CALL.call(b)

    loop_infinite_macro(b)

    # DEBUG=True なら HALT
    debug_trap(b)

    # 以降は無限ループ
    b.label("FinalLoop")
    JP(b, "FinalLoop")

    # ----- サブルーチンの定義 -----
    INIT_NAME_TABLE_CALL.define(b)
    DRAW_PAGE_CALL.define(b)

    # ----- VRAM イメージデータ本体 -----
    b.label("PACKED_DATA")
    DB(b, *packed_data)

    # origin=0x4000 で fixup 解決
    return b.finalize(origin=ROM_BASE)


def build(
    image0_trimmed: bytes,
    image1_trimmed: bytes,
    fill_byte: int = 0xFF,
) -> bytes:
    """
    1枚目: フル VRAM に復元して ROM に埋め込み、起動時に表示。
    2枚目: 今は未使用（将来 RowPackage 等で使う前提で残してある引数）。
    """
    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must be 0..255")

    pack1 = build_row_packages(image0_trimmed)
    pack2 = build_row_packages(image1_trimmed)

    engine = build_rom(pack1 + pack2)

    if len(engine) > ROM_SIZE:
        raise ValueError(
            f"engine+data too large ({len(engine)} bytes) for 32KB ROM"
        )

    rom = bytearray([fill_byte] * ROM_SIZE)
    rom[: len(engine)] = engine
    return bytes(rom)


def int_from_str(v: str) -> int:
    return int(v, 0)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MSX1 SCREEN2 1枚目表示 ROM ビルダー（スクロール前段階＋色＆パレット）"
    )
    p.add_argument("image0", type=Path, help="1枚目 .sc2 (上側 / まず表示する画像)")
    p.add_argument("image1", type=Path, help="2枚目 .sc2 (今は未使用)")
    p.add_argument(
        "-o", "--output", type=Path,
        help="出力 ROM ファイル名（未指定なら自動命名）",
    )
    p.add_argument(
        "--fill-byte", type=int_from_str, default=0xFF,
        help="未使用領域の埋め値 (default: 0xFF)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.image0.is_file():
        raise SystemExit(f"not found: {args.image0}")
    if not args.image1.is_file():
        raise SystemExit(f"not found: {args.image1}")

    img0 = validate_sc2_bytes(args.image0.read_bytes())
    img1 = validate_sc2_bytes(args.image1.read_bytes())

    rom = build(img0, img1, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        name = f"{args.image0.stem}_scroll_{args.image1.stem}"
        out = args.image0.with_name(name).with_suffix(".rom")

    out.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
