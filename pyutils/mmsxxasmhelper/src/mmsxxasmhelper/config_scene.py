"""SCREEN 0 汎用コンフィグ画面の生成ユーティリティ。

`build_screen0_config_menu` の呼び出し例::

    from mmsxxasmhelper.core import Block
    from mmsxxasmhelper.msxutils import build_update_input_func
    from mmsxxasmhelper.config_scene import (
        Screen0ConfigEntry,
        build_screen0_config_menu,
    )

    block = Block()
    update_input = build_update_input_func()
    init_func, loop_func, table_func = build_screen0_config_menu(
        [
            Screen0ConfigEntry("MODE", ["MSX1", "MSX2"], 0xC200),
            Screen0ConfigEntry("SPEED", ["SLOW", "FAST"], 0xC201),
        ],
        update_input_func=update_input,
    )

    # 必要な順序でコードを配置する
    init_func.emit(block)
    loop_func.emit(block)
    table_func.emit(block)

ゲーム側では `init_func` で VRAM へ UI を構築し、
メインループから `loop_func` を呼び続けるだけで
カーソル移動と左右選択、ESC 抜けが機能する。
オプション値は各項目の ``store_addr`` に 0 起点のインデックスが保持される。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mmsxxasmhelper.core import *
from mmsxxasmhelper.utils import *

from .msxutils import (
    CHPUT,
    INITXT,
    INPUT_KEY_BIT,
    build_set_vram_write_func,
    set_screen_colors_macro,
    set_text_cursor_macro,
    write_text_with_cursor_macro,
)

__all__ = ["Screen0ConfigEntry", "build_screen0_config_menu"]


@dataclass(frozen=True)
class Screen0ConfigEntry:
    """SCREEN 0 用のコンフィグ項目定義。"""

    name: str
    options: Sequence[str]
    store_addr: int


def build_screen0_config_menu(
    entries: Sequence[Screen0ConfigEntry] | dict[str, dict[str, object]],
    *,
    update_input_func: Func,
    group: str = DEFAULT_FUNC_GROUP_NAME,
    input_hold_addr: int = 0xC100,
    input_trg_addr: int = 0xC101,
    work_base_addr: int = 0xC110,
    screen0_name_base: int = 0x1800,
    sprite_pattern_addr: int = 0x3800,
    sprite_attribute_addr: int | None = None,
    title_lines: Sequence[str] | None = None,
    title_row: int = 0,
    title_centered: bool = True,
    header_lines: Sequence[str] | None = None,
    header_row: int | None = None,
    header_col: int = 2,
    top_row: int = 4,
    label_col: int = 2,
    option_col: int = 12,
    option_field_padding: int = 1,
    triangle_color: int = 15,
) -> tuple[Func, Func, Func]:
    """辞書定義から SCREEN 0 のコンフィグ画面を生成する。"""

    def _normalize_entries(
        raw_entries: Sequence[Screen0ConfigEntry] | dict[str, dict[str, object]]
    ) -> list[Screen0ConfigEntry]:
        if isinstance(raw_entries, dict):
            normalized: list[Screen0ConfigEntry] = []
            for key, value in raw_entries.items():
                options = value.get("options") if isinstance(value, dict) else None
                addr = value.get("addr") if isinstance(value, dict) else None
                if options is None or addr is None:
                    raise ValueError(
                        "dict 定義は {'<name>': {'options': [...], 'addr': 0xC200}} の形式にしてください"
                    )
                normalized.append(
                    Screen0ConfigEntry(
                        name=str(key),
                        options=[str(opt) for opt in options],
                        store_addr=int(addr),
                    )
                )
            return normalized
        return list(raw_entries)

    config_entries = _normalize_entries(entries)
    if not config_entries:
        raise ValueError("entries が空です")

    name_table_bytes = 40 * 24
    name_table_end = screen0_name_base + name_table_bytes
    if sprite_attribute_addr is None:
        sprite_attribute_addr = (name_table_end + 0x7F) & ~0x7F  # 次の 0x80 境界にアライン
    attribute_table_size = 0x80  # 32 sprites × 4 bytes
    overlaps_name_table = not (
        sprite_attribute_addr + attribute_table_size <= screen0_name_base
        or sprite_attribute_addr >= name_table_end
    )
    if overlaps_name_table:
        raise ValueError(
            "sprite_attribute_addr が SCREEN 0 のネームテーブル領域と重なっています"
        )

    entry_count = len(config_entries)
    option_field_widths = [
        (max(len(opt) for opt in entry.options)) + (option_field_padding * 2)
        for entry in config_entries
    ]

    title_lines = title_lines or ["", "HELP & SETTING", ""]
    title_height = len(title_lines)
    if header_row is None:
        header_row = title_row + title_height

    header_height = len(header_lines or [])
    if header_height:
        header_bottom_row = header_row + header_height - 1
        if top_row <= header_bottom_row:
            top_row = header_bottom_row + 2  # 1 行空けて <SETTING> を表示
    elif title_height:
        title_bottom_row = title_row + title_height - 1
        if top_row <= title_bottom_row:
            top_row = title_bottom_row + 2

    entry_row_base = top_row + 3
    if entry_row_base + entry_count > 24:
        raise ValueError(
            "表示行が SCREEN 0 の 24 行を超えています。top_row や項目数を調整してください"
        )

    CURRENT_ENTRY_ADDR = work_base_addr
    BLINK_STATE_ADDR = work_base_addr + 1
    DRAW_OPT_JT_LABEL = unique_label("__DRAW_OPT_JT__")
    ENTRY_VALUE_ADDR_LABEL = unique_label("__ENTRY_VALUE_ADDR__")
    ENTRY_OPTION_COUNT_LABEL = unique_label("__ENTRY_OPTION_COUNT__")
    ENTRY_OPTION_WIDTH_LABEL = unique_label("__ENTRY_OPTION_WIDTH__")
    OPT_PTR_TABLE_LABEL = unique_label("__OPT_PTR_TABLE__")
    OPTION_POINTER_LABELS = [unique_label("__OPT_PTR__") for _ in config_entries]

    TRIANGLE_PATTERN_LEFT = [
        0b00011000,
        0b00011000,
        0b00011000,
        0b00011000,
        0b00011000,
        0b00011000,
        0b00011000,
        0b00011000,
    ]
    TRIANGLE_PATTERN_RIGHT = [
        0b00011000,
        0b00110000,
        0b01100000,
        0b11000000,
        0b01100000,
        0b00110000,
        0b00011000,
        0b00001100,
    ]

    SET_VRAM_WRITE_FUNC = build_set_vram_write_func(group=group)

    def _emit_write_text(block: Block, col: int, row: int, text: str) -> None:
        write_text_with_cursor_macro(block, text, col, row)

    def _emit_draw_option(
        block: Block, entry: Screen0ConfigEntry, entry_index: int, option_width: int
    ) -> None:
        LD.A_n8(block, entry_index)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)

        row = entry_row_base + entry_index

        LD.HL_n16(block, entry.store_addr)
        LD.A_mHL(block)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, OPT_PTR_TABLE_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        PUSH.DE(block)  # 文字列ポインタを退避

        vram_addr = screen0_name_base + (row * 40) + option_col
        LD.HL_n16(block, vram_addr)
        SET_VRAM_WRITE_FUNC.call(block)

        POP.HL(block)  # 文字列ポインタを復帰
        LD.B_n8(block, option_width)

        write_loop = unique_label("__OPT_WRITE_LOOP__")
        padding_loop = unique_label("__OPT_PADDING_LOOP__")
        padding_exec_loop = unique_label("__OPT_PADDING_EXEC__")
        left_padding_loop = unique_label("__OPT_LEFT_PADDING__")

        if option_field_padding:
            LD.D_n8(block, option_field_padding)
            block.label(left_padding_loop)
            LD.A_n8(block, ord(" "))
            OUT(block, 0x98)
            DEC.D(block)
            DEC.B(block)
            JR_NZ(block, left_padding_loop)

        block.label(write_loop)
        LD.A_mHL(block)
        OR.A(block)
        JR_Z(block, padding_loop)
        OUT(block, 0x98)
        INC.HL(block)
        DJNZ(block, write_loop)
        RET(block)

        block.label(padding_loop)
        LD.A_n8(block, 0x20)
        block.label(padding_exec_loop)
        OUT(block, 0x98)
        DJNZ(block, padding_exec_loop)
        RET(block)

    def _emit_option_pointer_table(
        block: Block, entry: Screen0ConfigEntry, label_name: str
    ) -> None:
        block.label(label_name)
        for opt in entry.options:
            opt_label = unique_label("__OPT_STR__")
            pos = block.emit(0, 0)
            block.add_abs16_fixup(pos, opt_label)
            block.label(opt_label)
            DB(block, *(ord(ch) & 0xFF for ch in opt), 0x00)

    draw_option_funcs: list[Func] = []
    for idx, entry in enumerate(config_entries):
        option_width = option_field_widths[idx]
        draw_option_funcs.append(
            Func(
                f"DRAW_OPTION_{idx}",
                lambda b, e=entry, i=idx, w=option_width: _emit_draw_option(
                    b, e, i, w
                ),
                group=group,
            )
        )

    def draw_option_dispatch(block: Block) -> None:
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, DRAW_OPT_JT_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        PUSH.DE(block)
        POP.HL(block)
        JP_mHL(block)

    DRAW_OPTION_DISPATCH = Func(
        "DRAW_OPTION_FOR_CURRENT", draw_option_dispatch, group=group
    )

    def update_triangle_sprites(block: Block) -> None:
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)

        LD.DE_label(block, ENTRY_OPTION_COUNT_LABEL)
        ADD.HL_DE(block)
        LD.B_mHL(block)

        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        LD.DE_label(block, ENTRY_VALUE_ADDR_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        PUSH.DE(block)
        POP.HL(block)
        LD.A_mHL(block)
        LD.C_A(block)

        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        LD.DE_n16(block, (entry_row_base * 8) + 6)
        ADD.HL_DE(block)
        LD.A_L(block)
        LD.D_A(block)

        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        LD.DE_label(block, ENTRY_OPTION_WIDTH_LABEL)
        ADD.HL_DE(block)
        LD.A_mHL(block)
        LD.E_A(block)

        LD.L_C(block)

        LD.HL_n16(block, sprite_attribute_addr)
        PUSH.BC(block)
        SET_VRAM_WRITE_FUNC.call(block)
        POP.BC(block)
        LD.C_n8(block, 0x98)

        LEFT_VISIBLE = unique_label("__LEFT_VISIBLE__")
        LEFT_HIDDEN = unique_label("__LEFT_HIDDEN__")
        RIGHT_VISIBLE = unique_label("__RIGHT_VISIBLE__")
        RIGHT_HIDDEN = unique_label("__RIGHT_HIDDEN__")

        LD.A_L(block)
        block.label(LEFT_VISIBLE)
        OR.A(block)
        JR_Z(block, LEFT_HIDDEN)
        LD.A_mn16(block, BLINK_STATE_ADDR)
        BIT.n8_A(block, 0)
        JR_NZ(block, LEFT_HIDDEN)
        LD.A_D(block)
        OUT_C.A(block)
        LD.A_n8(block, (option_col - 1) * 8)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        LD.A_n8(block, triangle_color & 0x0F)
        OUT_C.A(block)
        JR(block, RIGHT_VISIBLE)

        block.label(LEFT_HIDDEN)
        LD.A_n8(block, 0xD0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)

        block.label(RIGHT_VISIBLE)
        LD.A_B(block)
        DEC.A(block)
        CP.C(block)
        JR_Z(block, RIGHT_HIDDEN)
        JP_M(block, RIGHT_HIDDEN)
        LD.A_mn16(block, BLINK_STATE_ADDR)
        BIT.n8_A(block, 0)
        JR_Z(block, RIGHT_HIDDEN)
        LD.A_D(block)
        OUT_C.A(block)
        LD.A_E(block)
        ADD.A_n8(block, option_col - 1)
        ADD.A_A(block)
        ADD.A_A(block)
        ADD.A_A(block)
        OUT_C.A(block)
        LD.A_n8(block, 1)
        OUT_C.A(block)
        LD.A_n8(block, triangle_color & 0x0F)
        OUT_C.A(block)
        RET(block)

        block.label(RIGHT_HIDDEN)
        LD.A_n8(block, 0xD0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        LD.A_n8(block, 0)
        OUT_C.A(block)
        RET(block)

    UPDATE_TRIANGLE_FUNC = Func(
        "UPDATE_TRIANGLE_SPRITES", update_triangle_sprites, group=group
    )

    def adjust_option(block: Block, delta: int) -> None:
        adjust_end = unique_label("__ADJUST_END__")
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        LD.E_A(block)
        LD.D_n8(block, 0)

        LD.A_E(block)
        ADD.A_A(block)
        LD.E_A(block)
        LD.HL_label(block, ENTRY_VALUE_ADDR_LABEL)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)

        LD.A_E(block)
        LD.L_A(block)
        LD.H_n8(block, 0)
        LD.DE_label(block, ENTRY_OPTION_COUNT_LABEL)
        ADD.HL_DE(block)
        LD.B_mHL(block)

        LD.A_mDE(block)
        if delta > 0:
            DEC.B(block)  # 最大インデックス
            CP.B(block)
            JR_NC(block, adjust_end)
            INC.A(block)
        else:
            OR.A(block)
            JR_Z(block, adjust_end)
            DEC.A(block)
        LD.mDE_A(block)
        LD.A_E(block)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        DRAW_OPTION_DISPATCH.call(block)
        UPDATE_TRIANGLE_FUNC.call(block)
        block.label(adjust_end)
        RET(block)

    ADJUST_OPTION_PLUS = Func(
        "ADJUST_OPTION_PLUS", lambda b: adjust_option(b, +1), group=group
    )
    ADJUST_OPTION_MINUS = Func(
        "ADJUST_OPTION_MINUS", lambda b: adjust_option(b, -1), group=group
    )

    def init_config_screen(block: Block) -> None:
        CALL(block, INITXT)
        set_screen_colors_macro(block, 15, 0, 0, current_screen_mode=0)

        # スプライトのテーブルアドレスを明示的に設定する
        OUT_A(block, 0x99, (sprite_attribute_addr >> 7) & 0xFF)  # R#5
        OUT_A(block, 0x99, 0x80 + 5)
        OUT_A(block, 0x99, (sprite_pattern_addr >> 11) & 0xFF)  # R#6
        OUT_A(block, 0x99, 0x80 + 6)

        # ネームテーブル（$1800〜$1BFF）をスペース（0x20）で埋める
        # （文字描画前に必ず初期化しておく）
        LD.HL_n16(block, screen0_name_base)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.BC_n16(block, 40 * 24)  # SCREEN 0 全体
        LD.A_n8(block, 0x20)  # スペース
        fill_loop = unique_label("__FILL_SCREEN__")
        block.label(fill_loop)
        OUT(block, 0x98)
        DEC.BC(block)
        LD.A_B(block)
        OR.C(block)
        JR_NZ(block, fill_loop)

        LD.HL_n16(block, sprite_pattern_addr)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.C_n8(block, 0x98)
        for b in TRIANGLE_PATTERN_LEFT + TRIANGLE_PATTERN_RIGHT:
            LD.A_n8(block, b)
            OUT_C.A(block)

        LD.HL_n16(block, sprite_attribute_addr)
        SET_VRAM_WRITE_FUNC.call(block)
        LD.C_n8(block, 0x98)
        for _ in range(32):
            LD.A_n8(block, 0xD0)
            OUT_C.A(block)
            LD.A_n8(block, 0)
            OUT_C.A(block)

        if title_lines:
            for idx, line in enumerate(title_lines):
                if not line:
                    continue
                if title_centered:
                    col = max((40 - len(line)) // 2, 0)
                else:
                    col = header_col
                _emit_write_text(block, col, title_row + idx, line)

        for idx, line in enumerate(header_lines or []):
            _emit_write_text(block, header_col, header_row + idx, line)

        _emit_write_text(block, label_col, top_row, "<SETTING>")
        _emit_write_text(block, label_col, top_row + 1, "Up/Down: select  Left/Right: change")

        for idx, entry in enumerate(config_entries):
            _emit_write_text(block, label_col, entry_row_base + idx, f"{entry.name}:")
            draw_option_funcs[idx].call(block)

        LD.A_n8(block, 0)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        LD.mn16_A(block, BLINK_STATE_ADDR)
        UPDATE_TRIANGLE_FUNC.call(block)
        RET(block)

    def run_config_loop(block: Block) -> None:
        loop_label = unique_label("__CONFIG_LOOP__")
        block.label(loop_label)
        HALT(block)
        update_input_func.call(block)

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_ESC)
        RET_NZ(block)

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_UP)
        skip_up = unique_label("__SKIP_UP__")
        JR_Z(block, skip_up)
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        OR.A(block)
        JR_Z(block, skip_up)
        DEC.A(block)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        DRAW_OPTION_DISPATCH.call(block)
        UPDATE_TRIANGLE_FUNC.call(block)
        block.label(skip_up)

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_DOWN)
        skip_down = unique_label("__SKIP_DOWN__")
        JR_Z(block, skip_down)
        LD.A_mn16(block, CURRENT_ENTRY_ADDR)
        INC.A(block)
        CP.n8(block, entry_count)
        JR_NC(block, skip_down)
        LD.mn16_A(block, CURRENT_ENTRY_ADDR)
        DRAW_OPTION_DISPATCH.call(block)
        UPDATE_TRIANGLE_FUNC.call(block)
        block.label(skip_down)

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_LEFT)
        skip_left = unique_label("__SKIP_LEFT__")
        JR_Z(block, skip_left)
        ADJUST_OPTION_MINUS.call(block)
        block.label(skip_left)

        LD.A_mn16(block, input_trg_addr)
        BIT.n8_A(block, INPUT_KEY_BIT.L_RIGHT)
        skip_right = unique_label("__SKIP_RIGHT__")
        JR_Z(block, skip_right)
        ADJUST_OPTION_PLUS.call(block)
        block.label(skip_right)

        LD.A_mn16(block, BLINK_STATE_ADDR)
        LD.B_n8(block, 1)
        XOR.B(block)
        LD.mn16_A(block, BLINK_STATE_ADDR)
        UPDATE_TRIANGLE_FUNC.call(block)

        JP(block, loop_label)

    def emit_tables(block: Block) -> None:
        block.label(DRAW_OPT_JT_LABEL)
        for func in draw_option_funcs:
            pos = block.emit(0, 0)
            block.add_abs16_fixup(pos, func.name)
        block.label(ENTRY_VALUE_ADDR_LABEL)
        for entry in config_entries:
            DW(block, entry.store_addr & 0xFFFF)
        block.label(ENTRY_OPTION_COUNT_LABEL)
        for entry in config_entries:
            DB(block, len(entry.options) & 0xFF)
        block.label(ENTRY_OPTION_WIDTH_LABEL)
        for width in option_field_widths:
            DB(block, width & 0xFF)
        block.label(OPT_PTR_TABLE_LABEL)
        for idx, entry in enumerate(config_entries):
            _emit_option_pointer_table(block, entry, OPTION_POINTER_LABELS[idx])

    INIT_FUNC = Func("CONFIG_SCREEN0_INIT", init_config_screen, group=group)
    RUN_LOOP_FUNC = Func("CONFIG_SCREEN0_LOOP", run_config_loop, group=group)
    TABLE_FUNC = Func(
        "CONFIG_SCREEN0_TABLES",
        emit_tables,
        no_auto_ret=True,
        group=group,
    )

    return INIT_FUNC, RUN_LOOP_FUNC, TABLE_FUNC
