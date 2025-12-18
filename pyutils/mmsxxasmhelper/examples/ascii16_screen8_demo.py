"""ASCII16 メガロムで SCREEN 8 を初期化し、スペースキーでバンクを切り替えて
VRAM 転送する最小サンプル。

- 起動時: SCREEN 8 へ切り替え、バンク2を page2(0x8000–0xBFFF) に割り当て。
  16 KiB 分を ROM(0x8000) から直接 VRAM 0 へ転送。
- スペースキー押下: 切り替え前のバンクを一度転送してから page2 を 3↔2 でトグルし、
  再度 ROM→VRAM 転送。

Bank 構成 (16 KiB 単位):
    0: ROM ヘッダ + メインコード (entry = 0x4010、page1 固定)
    1: 予備 (未使用)
    2: 画像データ例1 (16 KiB 擬似パターン)
    3: 画像データ例2 (16 KiB 擬似パターン)

出力 ROM: dist/ascii16_screen8_demo.rom
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from mmsxxasmhelper.core import CALL, Block, CP, Func, JR, JR_NZ, JR_Z, LD, XOR
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        place_msx_rom_header_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from mmsxxasmhelper.core import CALL, Block, CP, Func, JR, JR_NZ, JR_Z, LD, XOR
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        place_msx_rom_header_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes


ASCII16_PAGE2_REG = 0x7000  # 0x8000–0xBFFF を切替
PAGE_SIZE = 0x4000  # 16 KiB
VRAM_DEST = 0x0000
BANK_DATA_0 = 2
BANK_DATA_1 = 3


def build_boot_bank() -> bytes:
    """バンク0: ROM ヘッダ＋SCREEN8 初期化とバンク切替ループ。"""

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    # ---- ルーチン定義 ----
    def load_and_show(block: Block) -> None:
        # C = 表示したいデータバンク番号 (page2)
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)

        # ROM page2(0x8000) -> VRAM 0 へコピー（LDIRVM）
        LD.HL_n16(block, 0x8000)
        LD.DE_n16(block, VRAM_DEST)
        LD.BC_n16(block, PAGE_SIZE)
        # BIOS LDIRVM は HL=RAM, DE=VRAM, BC=サイズ
        CALL(block, LDIRVM)

        block.emit(0xC9)  # RET

    LOAD_AND_SHOW = Func("load_and_show", load_and_show)

    # ---- メイン ----
    b.label("main")

    # ブート直後にスタックポインタを安全な領域へ退避
    store_stack_pointer_macro(b)

    # SCREEN 8 初期化
    LD.A_n8(b, 8)
    CALL(b, CHGMOD)

    # 初期バンク = BANK_DATA_0
    LD.C_n8(b, BANK_DATA_0)
    LOAD_AND_SHOW.call(b)

    b.label("main_loop")
    # キー入力待ち (CHSNSで有無確認 → CHGET)
    CALL(b, 0x009C)  # CHSNS
    CP.n8(b, 0)
    JR_Z(b, "main_loop")

    CALL(b, 0x009F)  # CHGET
    CP.n8(b, 0x20)
    JR_NZ(b, "main_loop")

    # 切り替え前のバンクももう一度表示
    LOAD_AND_SHOW.call(b)

    # C の下位1bitをXORして 2<->3 を切替
    LD.A_C(b)
    XOR.n8(b, 0x01)
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


def generate_patterns() -> tuple[bytes, bytes]:
    """画面差分が分かりやすい 2 種類のダミーパターンを作る。"""

    pat0 = bytes((i & 0xFF) for i in range(PAGE_SIZE))
    pat1 = bytes(((i >> 2) ^ 0xAA) & 0xFF for i in range(PAGE_SIZE))
    return pat0, pat1


def build_ascii16_rom() -> bytes:
    bank0 = build_boot_bank()
    bank1 = bytes(pad_bytes([], PAGE_SIZE, 0xFF))  # page2=1 は未使用だが番号合わせで確保
    pat0, pat1 = generate_patterns()
    bank2 = build_data_bank(pat0)
    bank3 = build_data_bank(pat1)
    return bank0 + bank1 + bank2 + bank3


def main() -> None:
    rom = build_ascii16_rom()
    out_dir = Path(__file__).resolve().parents[2] / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ascii16_screen8_demo.rom"
    out_path.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out_path}")


if __name__ == "__main__":
    main()
