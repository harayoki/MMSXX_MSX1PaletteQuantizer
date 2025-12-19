"""MSX2 以降向け SCREEN 2 パレットランダム変更サンプル。

SCREEN 2 を初期化し、画面上に色インデックス 1–15 を示す矩形を配置する。
メインループでは疑似乱数でパレットを組み立て、約 30 フレームごとに
VDP のパレットレジスタへ書き込んで色をランダムに変化させる。

出力 ROM: dist/screen2_palette_random.rom
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from mmsxxasmhelper.core import (
        ADD,
        AND,
        Block,
        DB,
        Func,
        INC,
        JP,
        JP_NZ,
        LD,
        OUT,
        OR,
        DEC,
        XOR,
    )
    from mmsxxasmhelper.msxutils import (
        VDP_CTRL,
        VDP_DATA,
        VDP_PAL,
        enaslt_macro,
        init_screen2_macro,
        ldirvm_macro,
        place_msx_rom_header_macro,
        set_msx2_palette_default_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from mmsxxasmhelper.core import (
        ADD,
        AND,
        Block,
        DB,
        Func,
        INC,
        JP,
        JP_NZ,
        LD,
        OUT,
        OR,
        DEC,
        XOR,
    )
    from mmsxxasmhelper.msxutils import (
        VDP_CTRL,
        VDP_DATA,
        VDP_PAL,
        enaslt_macro,
        init_screen2_macro,
        ldirvm_macro,
        place_msx_rom_header_macro,
        set_msx2_palette_default_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes


ROM_PAGE_SIZE = 0x4000
PATTERN_TABLE_ADDR = 0x0000
COLOR_TABLE_ADDR = 0x2000
NAME_TABLE_ADDR = 0x1800
PALETTE_REGISTER = 16
JIFFY_ADDR = 0xFC9E
PALETTE_BUFFER_ADDR = 0xC100
RNG_STATE_ADDR = 0xC200


def _build_name_table_data() -> bytes:
    """矩形配置済みのネームテーブルデータを生成する。"""

    width = 32
    height = 24
    rect_w = 4
    rect_h = 4
    margin_x = 2
    margin_y = 2
    spacing = 1

    table = [0] * (width * height)
    color_index = 1

    for row in range(3):
        for col in range(5):
            start_x = margin_x + col * (rect_w + spacing)
            start_y = margin_y + row * (rect_h + spacing)

            for dy in range(rect_h):
                for dx in range(rect_w):
                    y = start_y + dy
                    x = start_x + dx
                    table[y * width + x] = color_index

            color_index += 1

    return bytes(table)


def _build_pattern_data() -> bytes:
    """1 タイル 1 色のパターンデータを 16 色分生成する。"""

    pattern = bytearray()
    for _ in range(16):
        pattern.extend([0xFF] * 8)
    return bytes(pattern)


def _build_color_data() -> bytes:
    """各タイルに対応する色テーブルを生成する。"""

    color_data = bytearray()
    for color in range(16):
        packed = (color << 4) | color
        color_data.extend([packed] * 8)
    return bytes(color_data)


def _build_palette_random_rom() -> bytes:
    name_table = _build_name_table_data()
    pattern_data = _build_pattern_data()
    color_data = _build_color_data()

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    # ルーチン定義 ------------------------------------------------------
    def rng_next(block: Block) -> None:
        """8bit LCG: state = state * 5 + 1."""

        LD.A_mn16(block, RNG_STATE_ADDR)
        LD.rr(block, "B", "A")
        ADD.A_A(block)
        ADD.A_A(block)
        ADD.A_B(block)
        INC.A(block)
        LD.mn16_A(block, RNG_STATE_ADDR)
        block.emit(0xC9)  # RET

    RNG_NEXT = Func("rng_next", rng_next)

    def randomize_palette(block: Block) -> None:
        # HL = PALETTE_BUFFER
        LD.HL_n16(block, PALETTE_BUFFER_ADDR)

        # エントリ0は黒で固定
        LD.mHL_n8(block, 0x00)
        INC.HL(block)
        LD.mHL_n8(block, 0x00)
        INC.HL(block)

        # 残り 15 色を生成
        LD.B_n8(block, 15)
        block.label("__PALETTE_LOOP__")

        RNG_NEXT.call(block)
        AND.n8(block, 0x07)
        LD.rr(block, "D", "A")  # R

        RNG_NEXT.call(block)
        AND.n8(block, 0x07)
        LD.rr(block, "E", "A")  # G

        RNG_NEXT.call(block)
        AND.n8(block, 0x07)
        LD.rr(block, "C", "A")  # B

        # 1 バイト目: R << 4 | B << 1
        LD.rr(block, "A", "D")
        block.emit(0x07, 0x07, 0x07, 0x07)  # RLCA x4
        LD.rr(block, "H", "A")
        LD.rr(block, "A", "C")
        ADD.A_A(block)
        AND.n8(block, 0x0E)
        OR.H(block)
        LD.mHL_A(block)
        INC.HL(block)

        # 2 バイト目: G
        LD.rr(block, "A", "E")
        LD.mHL_A(block)
        INC.HL(block)

        DEC.B(block)
        JP_NZ(block, "__PALETTE_LOOP__")

        block.emit(0xC9)  # RET test

        # VDP パレットレジスタへ転送 (index 0 から 32 バイト)
        OUT(block, VDP_CTRL, 0x00)
        OUT(block, VDP_CTRL, 0x80 + PALETTE_REGISTER)
        LD.HL_n16(block, PALETTE_BUFFER_ADDR)
        LD.B_n8(block, 32)
        block.label("__PALETTE_OUT__")
        block.emit(0x7E)        # LD A,(HL)
        block.emit(0xD3, VDP_PAL)  # OUT (9Ah),A
        block.emit(0x23)        # INC HL
        disp = (block.labels["__PALETTE_OUT__"] - (block.pc + 1)) & 0xFF
        block.emit(0x10, disp)  # DJNZ __PALETTE_OUT__

        block.emit(0xC9)  # RET

    RANDOMIZE_PALETTE = Func("randomize_palette", randomize_palette)

    # メインコード ------------------------------------------------------
    b.label("main")

    store_stack_pointer_macro(b)
    enaslt_macro(b)

    # SCREEN 2 初期化とデフォルトパレット設定（MSX2 以上のみ）
    init_screen2_macro(b)
    # set_msx2_palette_default_macro(b)  # MSX2以降で画面が真っ黒になる

    # パターン・カラーテーブル配置 (SCREEN 2 の 3 バンクへ複製)
    for dest in (PATTERN_TABLE_ADDR, 0x0800, 0x1000):
        pos = b.emit(0x21, 0x00, 0x00)  # LD HL,0x0000
        b.add_abs16_fixup(pos + 1, "PATTERN_DATA")
        ldirvm_macro(b, dest=dest, length=len(pattern_data))

    for dest in (COLOR_TABLE_ADDR, 0x2800, 0x3000):
        pos = b.emit(0x21, 0x00, 0x00)  # LD HL,0x0000
        b.add_abs16_fixup(pos + 1, "COLOR_DATA")
        ldirvm_macro(b, dest=dest, length=len(color_data))

    pos = b.emit(0x21, 0x00, 0x00)  # LD HL,0x0000
    b.add_abs16_fixup(pos + 1, "NAME_TABLE")
    ldirvm_macro(b, dest=NAME_TABLE_ADDR, length=len(name_table))

    # RNG シード: JIFFY の 2 バイトを XOR
    LD.A_mn16(b, JIFFY_ADDR)
    LD.rr(b, "D", "A")
    LD.A_mn16(b, JIFFY_ADDR + 1)
    XOR.D(b)
    LD.mn16_A(b, RNG_STATE_ADDR)

    b.label("main_loop")
    RANDOMIZE_PALETTE.call(b)  # MSX2 以降でここで画面が真っ黒になる

    # 約 30 フレーム待機 (HALT で VBLANK 待ち合わせ)
    LD.B_n8(b, 30)
    b.label("__WAIT_LOOP__")
    b.emit(0x76)  # HALT
    DEC.B(b)
    JP_NZ(b, "__WAIT_LOOP__")

    JP(b, "main_loop")

    # 関数定義
    RNG_NEXT.define(b)
    RANDOMIZE_PALETTE.define(b)

    # データ配置 --------------------------------------------------------
    b.label("PATTERN_DATA")
    DB(b, *pattern_data)

    b.label("COLOR_DATA")
    DB(b, *color_data)

    b.label("NAME_TABLE")
    DB(b, *name_table)

    return bytes(pad_bytes(list(b.finalize(origin=0x4000)), ROM_PAGE_SIZE, 0x00))


def main() -> None:
    rom = _build_palette_random_rom()
    out_dir = Path(__file__).resolve().parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "screen2_palette_random.rom"
    if out_path.exists():
        out_path.unlink()
    out_path.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out_path}")


if __name__ == "__main__":
    main()
