"""ASCII16 メガロムで SCREEN 8 を初期化し、スペースキーでバンクを切り替えて
VRAM 転送する最小サンプル。

- 起動時: SCREEN 8 へ切り替え、バンク1を page2(0x8000–0xBFFF) に割り当て。
  16 KiB 分を ROM(0x8000) から直接 VRAM 0 へ転送。
- スペースキー押下: page2 を 1→2→3→1… の順で切り替え、ROM→VRAM 転送。

Bank 構成 (16 KiB 単位):
    0: ROM ヘッダ + メインコード (entry = 0x4010、page1 固定)
    1: 画像データ 赤一色
    2: 画像データ 緑一色
    3: 画像データ 青一色

出力 ROM: dist/ascii16_screen8_demo.rom
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from mmsxxasmhelper.core import CALL, Block, CP, Func, INC, JR, JR_NZ, JR_Z, LD
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        enaslt_macro,
        place_msx_rom_header_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from mmsxxasmhelper.core import CALL, Block, CP, Func, INC, JR, JR_NZ, JR_Z, LD
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        enaslt_macro,
        place_msx_rom_header_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes


ASCII16_PAGE2_REG = 0x7000  # 0x8000–0xBFFF を切替
CURRENT_BANK_ADDR = 0xC000  # 表示バンク番号の保存先 (RAM)
PAGE_SIZE = 0x4000  # 16 KiB
VRAM_DEST = 0x0000
BANK_DATA_RED = 1
BANK_DATA_GREEN = 2
BANK_DATA_BLUE = 3
COLOR_RED = 0xE0
COLOR_GREEN = 0x1C
COLOR_BLUE = 0x03


def build_boot_bank() -> bytes:
    """バンク0: ROM ヘッダ＋SCREEN8 初期化とバンク切替ループ。"""

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    # ---- ルーチン定義 ----
    def load_and_show(block: Block) -> None:
        # C = 表示したいデータバンク番号 (page2)
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)

        block.emit(0xC5)  # PUSH BC (C を退避)

        # ROM page2(0x8000) -> VRAM 0 へコピー（LDIRVM）
        LD.HL_n16(block, 0x8000)
        LD.DE_n16(block, VRAM_DEST)
        LD.BC_n16(block, PAGE_SIZE)
        # BIOS LDIRVM は HL=RAM, DE=VRAM, BC=サイズ
        CALL(block, LDIRVM)

        block.emit(0xC1)  # POP BC (C を復帰)

        block.emit(0xC9)  # RET

    LOAD_AND_SHOW = Func("load_and_show", load_and_show)

    # ---- メイン ----
    b.label("main")

    # ブート直後にスタックポインタを安全な領域へ退避
    store_stack_pointer_macro(b)

    # ENASLOT を呼び出してバンクアクセスを有効化
    enaslt_macro(b)

    # SCREEN 8 初期化
    LD.A_n8(b, 8)
    CALL(b, CHGMOD)

    # 初期バンク = BANK_DATA_RED を RAM に保存
    LD.A_n8(b, BANK_DATA_RED)
    LD.mn16_A(b, CURRENT_BANK_ADDR)
    LD.rr(b, "C", "A")
    LOAD_AND_SHOW.call(b)

    b.label("main_loop")
    # キー入力待ち (CHSNSで有無確認 → CHGET)
    CALL(b, 0x009C)  # CHSNS
    CP.n8(b, 0)
    JR_Z(b, "main_loop")

    CALL(b, 0x009F)  # CHGET
    CP.n8(b, 0x20)
    JR_NZ(b, "main_loop")

    # 次のバンク番号を 1->2->3->1 の順で決定
    LD.A_mn16(b, CURRENT_BANK_ADDR)
    CP.n8(b, BANK_DATA_BLUE)
    JR_NZ(b, "next_bank_increment")

    LD.A_n8(b, BANK_DATA_RED)
    JR(b, "store_bank")

    b.label("next_bank_increment")
    INC.A(b)

    b.label("store_bank")
    LD.mn16_A(b, CURRENT_BANK_ADDR)

    LD.rr(b, "C", "A")

    LOAD_AND_SHOW.call(b)
    JR(b, "main_loop")

    LOAD_AND_SHOW.define(b)

    return bytes(pad_bytes(list(b.finalize(origin=0x4000)), PAGE_SIZE, 0x00))


def build_data_bank(pattern: bytes) -> bytes:
    """16 KiB にパディングしたデータバンクを返す。"""

    if len(pattern) > PAGE_SIZE:
        raise ValueError("pattern must be <= 16 KiB")
    return bytes(pad_bytes(list(pattern), PAGE_SIZE, 0x00))


def generate_color_patterns() -> tuple[bytes, bytes, bytes]:
    """赤・緑・青の単色データを用意する。"""

    pat_red = bytes([COLOR_RED] * PAGE_SIZE)
    pat_green = bytes([COLOR_GREEN] * PAGE_SIZE)
    pat_blue = bytes([COLOR_BLUE] * PAGE_SIZE)
    return pat_red, pat_green, pat_blue


def build_ascii16_rom() -> bytes:
    bank0 = build_boot_bank()
    pat_red, pat_green, pat_blue = generate_color_patterns()
    bank1 = build_data_bank(pat_red)
    bank2 = build_data_bank(pat_green)
    bank3 = build_data_bank(pat_blue)
    return bank0 + bank1 + bank2 + bank3


def main() -> None:
    rom = build_ascii16_rom()
    out_dir = Path(__file__).resolve().parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ascii16_screen8_demo[ASCII16].rom"
    if out_path.exists():
        out_path.unlink()
    out_path.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out_path}")


if __name__ == "__main__":
    main()
