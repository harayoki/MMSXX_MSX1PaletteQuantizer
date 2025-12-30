"""SCREEN 0 コンフィグ画面ビルダーの使用例。

`build_screen0_config_menu` で生成した初期化関数とループ関数を
ROM から呼び出し、ESC で確定した後に選択されたインデックスを
SCREEN 0 テキストとして表示する。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from mmsxxasmhelper.core import CALL, DB, LD, OR, RET, Block, Func
from mmsxxasmhelper.msxutils import (
    BAKCLR,
    BDRCLR,
    FORCLR,
    CHGCLR,
    INITXT,
    enaslt_macro,
    place_msx_rom_header_macro,
    store_stack_pointer_macro,
    build_update_input_func,
)
from mmsxxasmhelper.config_scene import Screen0ConfigEntry, build_screen0_config_menu
from mmsxxasmhelper.utils import loop_infinite_macro, pad_bytes


CHPUT = 0x00A2
PAGE_SIZE = 0x4000


def build_config_scene_rom() -> bytes:
    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    # 汎用入力更新関数とコンフィグ画面の生成
    update_input = build_update_input_func()
    init_func, loop_func, table_func = build_screen0_config_menu(
        [
            Screen0ConfigEntry("MODE", ["MSX1", "MSX2"], 0xC200),
            Screen0ConfigEntry("SOUND", ["ON", "OFF"], 0xC201),
            Screen0ConfigEntry("DIFFICULTY", ["EASY", "NORMAL", "HARD"], 0xC202),
        ],
        update_input_func=update_input,
        work_base_addr=0xC220,
        screen0_name_base=0x1800,
        sprite_pattern_addr=0x3800,
        sprite_attribute_addr=0x1B00,
    )

    # 0x00 終端文字列を CHPUT で描画
    def print_string(block: Block) -> None:
        loop_label = "PRINT_STRING_LOOP"
        end_label = "PRINT_STRING_END"
        block.label(loop_label)
        LD.A_mHL(block)
        OR.A(block)
        JR_Z(block, end_label)
        CALL(block, CHPUT)
        INC.HL(block)
        JR(block, loop_label)
        block.label(end_label)
        RET(block)

    PRINT_STRING = Func("PRINT_STRING", print_string)

    # コンフィグ選択値を 1 桁の数字で表示
    def print_value(block: Block, *, title: str, addr: int) -> None:
        LD.A_n8(block, ord(title[0]))
        CALL(block, CHPUT)
        LD.A_n8(block, ord(title[1]))
        CALL(block, CHPUT)
        LD.A_n8(block, ord("="))
        CALL(block, CHPUT)

        LD.A_mn16(block, addr)
        ADD.A_n8(block, ord("0"))
        CALL(block, CHPUT)

        LD.A_n8(block, ord("\r"))
        CALL(block, CHPUT)
        LD.A_n8(block, ord("\n"))
        CALL(block, CHPUT)

    PRINT_VALUE_MODE = Func("PRINT_VALUE_MODE", lambda blk: print_value(blk, title="MO", addr=0xC200))
    PRINT_VALUE_SOUND = Func("PRINT_VALUE_SOUND", lambda blk: print_value(blk, title="SO", addr=0xC201))
    PRINT_VALUE_DIFF = Func("PRINT_VALUE_DIFF", lambda blk: print_value(blk, title="DI", addr=0xC202))

    # 各関数・テーブルを配置
    update_input.define(b)
    init_func.define(b)
    loop_func.define(b)
    table_func.define(b)
    PRINT_STRING.define(b)
    PRINT_VALUE_MODE.define(b)
    PRINT_VALUE_SOUND.define(b)
    PRINT_VALUE_DIFF.define(b)

    # メインルーチン
    b.label("main")
    store_stack_pointer_macro(b)
    enaslt_macro(b)

    # SCREEN 0 の初期化と色設定
    CALL(b, INITXT)
    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, 0x04)
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    # 初期値クリア
    for addr in (0xC200, 0xC201, 0xC202):
        LD.A_n8(b, 0)
        LD.mn16_A(b, addr)

    # CONFIG 画面を実行
    init_func.call(b)
    loop_func.call(b)

    # ESC で抜けた後に選択値を表示
    CALL(b, INITXT)
    LD.HL_label(b, "CONFIG_DONE")
    PRINT_STRING.call(b)

    PRINT_VALUE_MODE.call(b)
    PRINT_VALUE_SOUND.call(b)
    PRINT_VALUE_DIFF.call(b)

    loop_infinite_macro(b)

    # ---- データ領域 ----
    b.label("CONFIG_DONE")
    DB(b, *"CONFIG EXITED (ESC)\r\n".encode("ascii"), 0x00)

    rom = b.finalize(origin=0x4000)
    return bytes(pad_bytes(list(rom), PAGE_SIZE, 0x00))


def main() -> None:
    rom = build_config_scene_rom()
    dist_dir = Path(__file__).resolve().parent / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_path = dist_dir / "config_scene_screen0.rom"
    out_path.write_bytes(rom)
    print(f"Wrote {len(rom)} bytes to {out_path}")


if __name__ == "__main__":
    main()
