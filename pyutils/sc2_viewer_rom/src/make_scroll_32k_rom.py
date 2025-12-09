#!/usr/bin/env python3
"""
MSX1 用・2画面縦スクロールエンジン ROM ビルダー（1枚目表示版）

現状:
- .sc2 2枚を読み込む
- 1枚目 .sc2 を SCREEN2 用 VRAM 0x4000 バイトに復元して ROM に埋め込む
- Z80 側は:
    - SCREEN2 に切り替え (CHGMOD 2)
    - SC2_IMAGE0 → VRAM へ 16KB コピー (LDIRVM)
    - 無限ループ

RowPackage 仕様はこのファイル内に残しておくが、
今のステップではまだ使っていない（後でスクロール実装に使う前提）。

usage:
    python make_scroll_rom.py imageA.sc2 imageB.sc2 -o out.rom
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from mmsxxasmhelper.core import *


# --- ROM / SCREEN2 関連定数 -----------------------------------------------

ROM_SIZE = 0x8000      # 32KB
ROM_BASE = 0x4000

VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7
IMAGE_LENGTH = 0x3780  # トリム後 (0000–1AFF + 1B80–37FF)

# BIOS コールアドレス（MSX1 標準）
CHGMOD = 0x005F
LDIRVM = 0x005C

# SCREEN2 VRAM レイアウト
PATTERN_BASE = 0x0000
NAME_BASE    = 0x1800
COLOR_BASE   = 0x2000

# RowPackage レイアウト（仕様として保持しておく）
ROW_NAME_SIZE    = 32
ROW_TILE_COUNT   = 32
ROW_TILE_BYTES   = 16                  # pattern[8] + color[8]
ROW_PACKAGE_SIZE = ROW_NAME_SIZE + ROW_TILE_COUNT * ROW_TILE_BYTES  # 544
TOTAL_ROWS       = 48                  # 2画面 × 24行


# --- ROM ヘッダ定義（msxrom_boot と同じ形） -------------------------------

# 0x4000 に配置されるヘッダ:
#   "AB" + [entry_lo, entry_hi] + padding ... (合計16バイト)
# entry = 0x4010 → [0x10,0x40]
const_bytes(
    "MSX_ROM_HEADER",
    *pad_bytes(str_bytes("AB") + [0x10, 0x40], 16, 0x00),
)


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


# --- Z80 コード（1枚目を表示するだけのエンジン） --------------------------

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

    # VRAM 全体に 1枚目の画像を転送:
    #   HL = SC2_IMAGE0
    #   DE = 0000h
    #   BC = 4000h
    #   CALL LDIRVM
    #
    # LD HL,SC2_IMAGE0
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
    debug_trap(b)  # DEBUG=True なら HALT が入る
    jp(b, "MainLoop")

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

    # 今は 1枚目だけ使う
    sc2_full0 = trimmed_to_full_vram(image0_trimmed)

    # （将来用）RowPackage 生成したければここで呼べる:
    # rows0 = build_row_packages(image0_trimmed)
    # rows1 = build_row_packages(image1_trimmed)
    # all_rows = rows0 + rows1

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
        description="MSX1 SCREEN2 1枚目表示 ROM ビルダー（スクロール前段階）"
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
    img1 = sc2_to_trimmed(args.image1.read_bytes())

    rom = build_rom(img0, img1, fill_byte=args.fill_byte)

    out = args.output
    if out is None:
        name = f"{args.image0.stem}_scroll_{args.image1.stem}"
        out = args.image0.with_name(name).with_suffix(".rom")

    out.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out}")


if __name__ == "__main__":
    main()
