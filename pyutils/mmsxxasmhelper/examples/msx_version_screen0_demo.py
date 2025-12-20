"""MSX ROM that boots, detects the MSX generation, and prints it on SCREEN 0.

MSX1 / MSX2 / MSX2+ / turboR およびその他を判定して表示する最小サンプル。
16 KiB ROM を生成し、``dist/msx_version_screen0.rom`` に出力する。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from mmsxxasmhelper.core import CALL, CP, DB, Block, Func, INC, JR, JR_Z, LD, OR
from mmsxxasmhelper.msxutils import (
    BAKCLR,
    BDRCLR,
    FORCLR,
    CHGCLR,
    enaslt_macro,
    get_msxver_macro,
    place_msx_rom_header_macro,
    store_stack_pointer_macro,
)
from mmsxxasmhelper.utils import pad_bytes, loop_infinite_macro


INITXT = 0x006C
CHPUT = 0x00A2
CHGET = 0x009F
PAGE_SIZE = 0x4000


def build_msx_version_rom() -> bytes:
    """組み立てた ROM バイト列を返す。"""

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    def print_string(block: Block) -> None:
        """HL を先頭にした 0x00 終端文字列を CHPUT で表示。"""

        block.label("print_string_loop")
        LD.rr(block, "A", "mHL")
        OR.A(block)  # ZF=1 なら終端
        JR_Z(block, "print_string_end")
        CALL(block, CHPUT)
        INC.HL(block)
        JR(block, "print_string_loop")
        block.label("print_string_end")

    PRINT_STRING = Func("print_string", print_string)

    b.label("main")

    # スタックポインタ退避＋スロット有効化
    store_stack_pointer_macro(b)
    enaslt_macro(b)

    # SCREEN 0 を初期化して見やすい色をセット
    CALL(b, INITXT)
    LD.A_n8(b, 0x0F)  # 白
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, 0x01)  # 青
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    # 見出しの表示
    LD.HL_label(b, "HEADER_TEXT")
    PRINT_STRING.call(b)

    LD.HL_label(b, "LABEL_TEXT")
    PRINT_STRING.call(b)

    # MSX バージョン判定
    get_msxver_macro(b)
    CP.n8(b, 0)
    JR_Z(b, "print_msx1")
    CP.n8(b, 1)
    JR_Z(b, "print_msx2")
    CP.n8(b, 2)
    JR_Z(b, "print_msx2_plus")
    CP.n8(b, 3)
    JR_Z(b, "print_turbor")
    JR(b, "print_other")

    b.label("print_msx1")
    LD.HL_label(b, "MSX1_TEXT")
    PRINT_STRING.call(b)
    JR(b, "end")

    b.label("print_msx2")
    LD.HL_label(b, "MSX2_TEXT")
    PRINT_STRING.call(b)
    JR(b, "end")

    b.label("print_msx2_plus")
    LD.HL_label(b, "MSX2_PLUS_TEXT")
    PRINT_STRING.call(b)
    JR(b, "end")

    b.label("print_turbor")
    LD.HL_label(b, "TURBOR_TEXT")
    PRINT_STRING.call(b)
    JR(b, "end")

    b.label("print_other")
    LD.HL_label(b, "OTHER_TEXT")
    PRINT_STRING.call(b)

    b.label("end")
    loop_infinite_macro(b)

    PRINT_STRING.define(b)

    # ---- データ領域 ----
    b.label("HEADER_TEXT")
    DB(b, *"MSX VERSION CHECK\r\n\r\n".encode("ascii"), 0x00)

    b.label("LABEL_TEXT")
    DB(b, *"DETECTED: ".encode("ascii"), 0x00)

    b.label("MSX1_TEXT")
    DB(b, *"MSX1\r\n".encode("ascii"), 0x00)

    b.label("MSX2_TEXT")
    DB(b, *"MSX2\r\n".encode("ascii"), 0x00)

    b.label("MSX2_PLUS_TEXT")
    DB(b, *"MSX2+\r\n".encode("ascii"), 0x00)

    b.label("TURBOR_TEXT")
    DB(b, *"TURBO R\r\n".encode("ascii"), 0x00)

    b.label("OTHER_TEXT")
    DB(b, *"OTHER\r\n".encode("ascii"), 0x00)

    rom = b.finalize(origin=0x4000)
    return bytes(pad_bytes(list(rom), PAGE_SIZE, 0x00))


def main() -> None:
    rom = build_msx_version_rom()
    dist_dir = Path(__file__).resolve().parent / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_path = dist_dir / "msx_version_screen0.rom"
    out_path.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out_path}")


if __name__ == "__main__":
    main()
