#!/usr/bin/env python3
"""
MSX1 用・2画面縦スクロールエンジン ROM ビルダー（1枚目表示＋色＆パレットマクロ付き）

現状:
- .sc2 2枚を読み込む
- 1枚目 .sc2 を SCREEN2 用 VRAM 0x4000 バイトに復元して ROM に埋め込み
- 起動時:
    - SCREEN2 に切り替え (CHGMOD 2)
    - 前景=白 / 背景=黒 / 枠=黒 に設定（MSX1/2 共通）  ← マクロ
    - MSX2 以上ならパレットを設定                       ← マクロ
    - SC2_IMAGE0 → VRAM へ 16KB コピー (LDIRVM)
    - 無限ループ
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from mmsxxasmhelper.core import *


# --- ROM / SCREEN2 / BIOS 定数 --------------------------------------------

ROM_SIZE = 0x8000      # 32KB
ROM_BASE = 0x4000

VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7
IMAGE_LENGTH = 0x3780  # トリム後 (0000–1AFF + 1B80–37FF)

# BIOS コールアドレス
CHGMOD = 0x005F
CHGCLR = 0x0062
LDIRVM = 0x005C

# カラー関連システム変数 (MSX1/2 共通)
FORCLR = 0xF3E9  # 前景色
BAKCLR = 0xF3EA  # 背景色
BDRCLR = 0xF3EB  # 枠色

# MSX バージョン (メインROM 002Dh)
# 0=MSX1 / 1=MSX2 / 2=MSX2+ / 3=turboR
MSXVER = 0x002D  # :contentReference[oaicite:1]{index=1}

# VDP / SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE    = 0x1800
COLOR_BASE   = 0x2000

# RowPackage レイアウト（将来のスクロール用に保持）
ROW_NAME_SIZE    = 32
ROW_TILE_COUNT   = 32
ROW_TILE_BYTES   = 16                  # pattern[8] + color[8]
ROW_PACKAGE_SIZE = ROW_NAME_SIZE + ROW_TILE_COUNT * ROW_TILE_BYTES  # 544
TOTAL_ROWS       = 48                  # 2画面 × 24行

MSXVER   = 0x002D   # 0=MSX1, 1=MSX2, 2=2+, 3=turboR

# --- ROM ヘッダ定義（msxrom_boot と同じ形） -------------------------------

# 0x4000 に配置されるヘッダ:
#   "AB" + [entry_lo, entry_hi] + padding ... (合計16バイト)
# entry = 0x4010 → [0x10,0x40]
const_bytes(
    "MSX_ROM_HEADER",
    *pad_bytes(str_bytes("AB") + [0x10, 0x40], 16, 0x00),
)


# --- MSX2 用デフォルトパレット定義 ---------------------------------------

# COLOR=(n,R,G,B)
# 1バイト目: 0R2 R1 R0 B2 B1 B0
# 2バイト目: 0000 G2 G1 G0
# R,G,B は 0–7
_MSX2_PALETTE_BYTES: List[int] = []
for idx, (R, G, B) in enumerate([
    (0, 0, 0),  # 0
    (0, 0, 0),  # 1
    (2, 5, 2),  # 2
    (3, 5, 3),  # 3
    (2, 2, 6),  # 4
    (3, 3, 6),  # 5
    (5, 2, 2),  # 6
    (2, 6, 6),  # 7
    (6, 2, 2),  # 8
    (7, 3, 3),  # 9
    (5, 5, 2),  # 10
    (6, 5, 3),  # 11
    (1, 4, 1),  # 12
    (5, 3, 5),  # 13
    (5, 5, 5),  # 14
    (7, 7, 7),  # 15
]):
    b1 = ((R & 7) << 4) | (B & 7)
    b2 = (G & 7)
    _MSX2_PALETTE_BYTES.extend([b1, b2])

# 他ファイルでもコピペで使いやすいように const_bytes にも登録しておく
const_bytes("MSX2_PALETTE_DEFAULT", *_MSX2_PALETTE_BYTES)


# --- .sc2 トリム処理 ------------------------------------------------------

def sc2_to_trimmed(sc2_bytes: bytes) -> bytes:
    """
    SCREEN2 VRAM ダンプを 0x3780 バイトにトリム。

    元 VRAM:
        0000h–37FFh (16KB)

    トリム形式:
        0000h–1AFFh + 1B80h–37FFh  → 合計 0x3780
    """
    length = len(sc2_bytes)

    # すでにトリム済み
    if length == IMAGE_LENGTH:
        return sc2_bytes

    # 7バイトヘッダ付き 0x4000 + 7
    if length == VRAM_SIZE + SC2_HEADER_SIZE:
        sc2_bytes = sc2_bytes[SC2_HEADER_SIZE:]
        length = len(sc2_bytes)

    # 素の 0x4000
    if length == VRAM_SIZE:
        # 0000–1AFF
        part1 = sc2_bytes[:0x1B00]
        # 1B80–37FF
        part2 = sc2_bytes[0x1B80:0x3800]
        return part1 + part2

    raise ValueError(
        f"Invalid SC2 size: {length:#x}, expected 0x3780 or 0x4000(+7)"
    )


def trimmed_to_full_vram(trimmed: bytes) -> bytes:
    """
    トリム済み 0x3780 バイトから、フル VRAM 0x4000 バイトに戻す。

    トリム形式:
        0000–1AFF   → VRAM 0000–1AFF
        1B00–377F   → VRAM 1B80–37FF
    それ以外の VRAM 領域は 0 クリア。
    """
    if len(trimmed) != IMAGE_LENGTH:
        raise ValueError("trimmed image must be 0x3780 bytes")

    vram = bytearray([0x00] * VRAM_SIZE)

    # 0000–1AFF
    vram[0x0000:0x1B00] = trimmed[0x0000:0x1B00]
    # 1B80–37FF
    vram[0x1B80:0x3800] = trimmed[0x1B00:0x3780]

    return bytes(vram)


def vram_to_trimmed_offset(addr: int) -> int:
    """
    VRAM アドレス 0x0000–0x37FF を、
    トリム済み 0x3780 バッファ上のオフセットに変換。
    （RowPackage 用に残しておく）
    """
    if addr < 0x1B00:
        return addr
    # 1B80–37FF が 1B00–35FF に詰められている
    return addr - 0x80


# --- RowPackage 生成（将来のスクロール用にそのまま保持） -------------------

def build_row_packages(image_bytes: bytes) -> List[bytes]:
    """
    トリム済み 1画面 (0x3780) から RowPackage[24] を生成。

    RowPackage:
        name[32]
        tiles[32] each { pattern[8], color[8] }
    """
    if len(image_bytes) != IMAGE_LENGTH:
        raise ValueError("trimmed image must be 0x3780 bytes")

    rows: List[bytes] = []

    for row in range(24):
        bank = row // 8  # 0,1,2 (SCREEN2 の 8行単位バンク)

        # NameTable 1行分（パターン番号32個）
        name_vram = NAME_BASE + row * 32
        name_off = vram_to_trimmed_offset(name_vram)
        name_row = image_bytes[name_off:name_off + 32]
        if len(name_row) != 32:
            raise ValueError("unexpected name row slice length")

        tile_bytes = bytearray()

        for col in range(32):
            p = name_row[col]

            pat_base_bank = PATTERN_BASE + bank * 0x800
            col_base_bank = COLOR_BASE + bank * 0x800

            pat_addr = pat_base_bank + p * 8
            col_addr = col_base_bank + p * 8

            pat_off = vram_to_trimmed_offset(pat_addr)
            col_off = vram_to_trimmed_offset(col_addr)

            pattern = image_bytes[pat_off:pat_off + 8]
            color   = image_bytes[col_off:col_off + 8]

            if len(pattern) != 8 or len(color) != 8:
                raise ValueError("unexpected pattern/color slice length")

            tile_bytes.extend(pattern)
            tile_bytes.extend(color)

        if len(tile_bytes) != ROW_TILE_COUNT * ROW_TILE_BYTES:
            raise ValueError("tile_bytes size mismatch")

        row_pkg = bytes(name_row) + bytes(tile_bytes)
        if len(row_pkg) != ROW_PACKAGE_SIZE:
            raise ValueError("RowPackage size mismatch")

        rows.append(row_pkg)

    return rows


# --- マクロ：背景＆周辺を黒にする（MSX1/2 共通） ---------------------------

def macro_set_black_screen_colors(b: Block) -> None:
    """
    前景=白(15), 背景=黒(0), 枠=黒(0) にして CHGCLR を呼ぶ。
    他の ROM でもコピペしやすいよう、ラベルは使わずインラインのみ。
    """
    # FORCLR = 15 (白)
    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)

    # BAKCLR = 0 (黒)
    LD.A_n8(b, 0x00)
    LD.mn16_A(b, BAKCLR)

    # BDRCLR = 0 (黒)
    LD.A_n8(b, 0x00)
    LD.mn16_A(b, BDRCLR)

    # CALL CHGCLR
    b.emit(0xCD, CHGCLR & 0xFF, (CHGCLR >> 8) & 0xFF)


# --- マクロ：MSX2 以上ならパレットを設定 -----------------------------------


MSXVER = 0x002D  # すでにどこかに書いてあるならそれを使う

def macro_set_msx2_palette_default(b: Block) -> None:
    """
    MSX2 以上なら MSX2_PALETTE_DEFAULT を設定するマクロ。
    インライン展開前提なので RET は絶対に使わない。
    """

    # --- MSX バージョン確認 ---
    # A = (MSXVER)
    LD.A_mn16(b, MSXVER)
    b.emit(0xFE, 0x00)   # CP 0

    # Z(=MSX1) のときはパレット処理を丸ごと飛ばす
    jz(b, "MSX2_PAL_SKIP")

    # --- ここから MSX2 以上用のパレット書き込み ---

    # R#16 に color index 0 をセット
    # OUT 99h,0
    LD.A_n8(b, 0x00)
    b.emit(0xD3, 0x99)

    # OUT 99h,80h+16  ; レジスタ16指定
    LD.A_n8(b, 0x80 + 16)
    b.emit(0xD3, 0x99)

    # HL = PALETTE_DATA
    pos2 = b.emit(0x21, 0x00, 0x00)  # LD HL,nn
    b.add_abs16_fixup(pos2 + 1, "PALETTE_DATA")

    # B = 32 (16色×2バイト)
    LD.B_n8(b, 32)

    b.label("MSX2_PAL_LOOP")
    b.emit(0x7E)        # LD A,(HL)
    b.emit(0xD3, 0x9A)  # OUT (9Ah),A
    b.emit(0x23)        # INC HL
    disp = (b.labels["MSX2_PAL_LOOP"] - (b.pc + 1)) & 0xFF
    b.emit(0x10, disp)  # DJNZ MSX2_PAL_LOOP

    # --- スキップ先ラベル ---
    b.label("MSX2_PAL_SKIP")



# --- Z80 コード（1枚目を表示するエンジン） --------------------------------

def build_engine_show_image0(sc2_full_vram: bytes) -> bytes:
    """
    1枚目のフル VRAM 画像を ROM に埋め込み、
    起動時にそれを VRAM にコピーして表示するコードを組み立てる。
    """
    if len(sc2_full_vram) != VRAM_SIZE:
        raise ValueError("sc2_full_vram must be 0x4000 bytes")

    b = Block()

    # エントリラベル（ROM_HEADER もここに置く）
    b.label("start")

    # ROM ヘッダ配置（MSX がここを 0x4000 とみなす）
    db(b, *DATA8["MSX_ROM_HEADER"])

    # ----- ここから 0x4010: 実際に実行されるコード -----

    # SCREEN 2 に変更: LD A,2 / CALL 005Fh (CHGMOD)
    LD.A_n8(b, 2)
    b.emit(0xCD, CHGMOD & 0xFF, (CHGMOD >> 8) & 0xFF)  # CALL CHGMOD

    # 色: 前景=白 / 背景=黒 / 枠=黒
    macro_set_black_screen_colors(b)

    # MSX2 以上ならパレット設定
    # macro_set_msx2_palette_default(b)  #B 現状真っ黒になってしまうバグあり

    # VRAM 全体に 1枚目の画像を転送:
    #   HL = SC2_IMAGE0
    #   DE = 0000h
    #   BC = 4000h
    #   CALL LDIRVM
    #
    # LD HL,SC2_IMAGE0
    # LD.HL_n8(b, 0x00, 0x00)  # ダミー、fixup 後で埋める
    pos = b.emit(0x21, 0x00, 0x00)          # LD HL,nn
    b.add_abs16_fixup(pos + 1, "SC2_IMAGE0")

    # LD DE,0000h
    LD.DE_n16(b, 0x0000)

    # LD BC,4000h
    LD.BC_n16(b, 0x4000)

    # CALL 005Ch (LDIRVM)
    b.emit(0xCD, LDIRVM & 0xFF, (LDIRVM >> 8) & 0xFF)

    # 以降は無限ループ
    b.label("MainLoop")
    debug_trap(b)  # DEBUG=True なら HALT
    jp(b, "MainLoop")

    # ----- パレットデータ本体 (MSX2 用) -----
    b.label("PALETTE_DATA")
    db_from_bytes(b, "MSX2_PALETTE_DEFAULT")

    # ----- VRAM イメージデータ本体 -----

    b.label("SC2_IMAGE0")
    db(b, *sc2_full_vram)

    # origin=0x4000 で fixup 解決
    return b.finalize(origin=ROM_BASE)


# --- ROM 全体構築 ---------------------------------------------------------

def build_rom(
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

    sc2_full0 = trimmed_to_full_vram(image0_trimmed)

    engine = build_engine_show_image0(sc2_full0)

    if len(engine) > ROM_SIZE:
        raise ValueError(
            f"engine+data too large ({len(engine)} bytes) for 32KB ROM"
        )

    rom = bytearray([fill_byte] * ROM_SIZE)
    rom[: len(engine)] = engine
    return bytes(rom)


# --- CLI ------------------------------------------------------------------

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

    img0 = sc2_to_trimmed(args.image0.read_bytes())
    img1 = sc2_to_trimmed(args.image1.read_bytes())  # 今は読むだけ

    rom = build_rom(img0, img1, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        name = f"{args.image0.stem}_scroll_{args.image1.stem}"
        out = args.image0.with_name(name).with_suffix(".rom")

    out.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
