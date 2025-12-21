"""Create an ASCII16 MegaROM that flips through multiple SCREEN2 images."""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

from mmsxxasmhelper.core import ADD, AND, Block, CALL, CP, DB, DEC, DW, Func, INC, JR, JR_C, JR_NC, JR_NZ, JR_Z, LD, OR, OUT, XOR
from mmsxxasmhelper.msxutils import (
    CHGMOD,
    LDIRVM,
    enaslt_macro,
    place_msx_rom_header_macro,
    set_msx2_palette_default_macro,
    store_stack_pointer_macro,
)
from mmsxxasmhelper.utils import JIFFY_ADDR, pad_bytes

PAGE_SIZE = 0x4000
MAX_ROM_SIZE = 0x400000
MAX_BANKS = MAX_ROM_SIZE // PAGE_SIZE
VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7
TRIMMED_SC2_SIZE = 0x3780

ASCII16_PAGE2_REG = 0x7000
CURRENT_INDEX_ADDR = 0xC000
AUTO_INTERVAL_ADDR = 0xC001
AUTO_INTERVAL_PREV_ADDR = 0xC003
AUTO_COUNTDOWN_ADDR = 0xC005
LAST_JIFFY_ADDR = 0xC007
AUTO_SPEED_INDEX_ADDR = 0xC009
AUTO_SPEED_PREV_ADDR = 0xC00A
AUTO_INDICATOR_FLAG_ADDR = 0xC00B
INSTRUCTION_TICK_TOTAL_ADDR = 0xC00C
INSTRUCTION_LAST_JIFFY_ADDR = 0xC00E
INSTRUCTION_LINE_BUFFER_ADDR = 0xC010
AUTO_INDICATOR_TIMEOUT_ADDR = 0xC026
AUTO_INDICATOR_LAST_JIFFY_ADDR = 0xC028

CHSNS = 0x009C
CHGET = 0x009F
CHPUT = 0x00A2
CHGCLR = 0x0062
FORCLR = 0xF3E9
BAKCLR = 0xF3EA
BDRCLR = 0xF3EB
SNSMAT = 0x0141

SPRITE_ATTR_TABLE_ADDR = 0x1B00
SPRITE_PATTERN_TABLE_ADDR = 0x3800
SPRITE_ATTR_TABLE_SIZE = 0x80
SPRITE_PATTERN_TABLE_SIZE = 0x800
SPEED_INDICATOR_PATTERN_ID = 0x00
SPEED_INDICATOR_COLOR = 0x0F
SPEED_INDICATOR_X = 0xF8
SPEED_INDICATOR_Y_BOTTOM = 0xB8
SPEED_INDICATOR_Y_STEP = 0x08

KEY_SPACE = 0x20
KEY_UP = 0x1E
KEY_DOWN = 0x1F
KEY_ESC = 0x1B

KEYBOARD_ROW_SHIFT = 0x06
KEYBOARD_SHIFT_MASK = 0x01

INSTRUCTION_TEXT_STATIC = (
    "MMSXX SC2 VIEWER\r\n"
    "\r\n"
    "SPACE: NEXT + PAUSE\r\n"
    "SHIFT+SPACE: PREV\r\n"
    "DOWN: NEXT\r\n"
    "UP: PREV\r\n"
    "SHIFT+DOWN: FASTER\r\n"
    "SHIFT+UP: SLOWER\r\n"
    "ESC: FIRST\r\n"
    "\r\n"
)

INSTRUCTION_TEXT_WAIT = "PRESS ANY KEY\r\n"

INSTRUCTION_AUTO_LINE_TEMPLATE = "AUTO START IN 00 Sec."
INSTRUCTION_AUTO_DIGIT_OFFSET = 14
INSTRUCTION_LINE_LENGTH = len(INSTRUCTION_AUTO_LINE_TEMPLATE) + 1

INSTRUCTION_BG_COLOR = 0x04

JIFFY_PER_SECOND = 60
AUTO_INDICATOR_TIMEOUT_TICKS = 5 * JIFFY_PER_SECOND

PSG_REG_PORT = 0xA0
PSG_DATA_PORT = 0xA1
PSG_MIXER_VALUE = 0xFE
SOUND_DURATION_TICKS = 9
SOUND_VOLUME = 0x0A
SOUND_HIGH_FINE = 0x10
SOUND_HIGH_COARSE = 0x00
SOUND_LOW_FINE = 0x80
SOUND_LOW_COARSE = 0x00

INSTRUCTION_SECONDS_TEXT = [f"{value:02d}" for value in range(0, 31)]

AUTO_SPEED_SECONDS = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]
DEFAULT_AUTO_SPEED_LEVEL = 4


def int_from_str(value: str) -> int:
    return int(value, 0)


def seconds_to_jiffies(seconds: float) -> int:
    if seconds < 0:
        raise ValueError("Seconds value must be zero or greater")
    ticks = int(round(seconds * JIFFY_PER_SECOND))
    return min(ticks, 0xFFFF)


def sc2_to_vram(sc2_bytes: bytes) -> bytes:
    length = len(sc2_bytes)

    if length == VRAM_SIZE:
        return sc2_bytes

    if length == VRAM_SIZE + SC2_HEADER_SIZE:
        return sc2_bytes[SC2_HEADER_SIZE:]

    if length == TRIMMED_SC2_SIZE:
        vram = bytearray(VRAM_SIZE)
        vram[0x0000:0x1B00] = sc2_bytes[:0x1B00]
        vram[0x1B80:0x3800] = sc2_bytes[0x1B00:]
        return bytes(vram)

    if length == TRIMMED_SC2_SIZE + SC2_HEADER_SIZE:
        return sc2_to_vram(sc2_bytes[SC2_HEADER_SIZE:])

    raise ValueError(
        "Invalid SC2 size: expected 0x4000 (+7 header) or 0x3780 bytes"
    )


def build_boot_bank(
    image_count: int,
    show_instructions: bool,
    background_color: int,
    speed_tick_levels: list[int],
    initial_speed_level: int,
    start_paused: bool,
    enable_speed_indicator: bool,
    instruction_autostart_seconds: int,
    copy_sprite_tables: bool,
) -> bytes:
    if not 1 <= image_count <= 0xFF:
        raise ValueError("image_count must be between 1 and 255")
    if not speed_tick_levels:
        raise ValueError("speed_tick_levels must not be empty")
    if not 0 <= initial_speed_level < len(speed_tick_levels):
        raise ValueError("initial_speed_level out of range")
    if not 0 <= instruction_autostart_seconds <= 30:
        raise ValueError("instruction_autostart_seconds must be between 0 and 30")
    for value in speed_tick_levels:
        if not 0 < value <= 0xFFFF:
            raise ValueError("speed_tick_levels values must be between 1 and 65535")

    speed_level_count = len(speed_tick_levels)

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    def load_and_show(block: Block) -> None:
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)
        LD.HL_n16(block, 0x8000)
        if copy_sprite_tables:
            LD.DE_n16(block, 0x0000)
            LD.BC_n16(block, VRAM_SIZE)
            CALL(block, LDIRVM)
        else:
            LD.DE_n16(block, 0x0000)
            LD.BC_n16(block, SPRITE_ATTR_TABLE_ADDR)
            CALL(block, LDIRVM)
            LD.HL_n16(
                block,
                0x8000 + SPRITE_ATTR_TABLE_ADDR + SPRITE_ATTR_TABLE_SIZE,
            )
            LD.DE_n16(block, SPRITE_ATTR_TABLE_ADDR + SPRITE_ATTR_TABLE_SIZE)
            LD.BC_n16(
                block,
                SPRITE_PATTERN_TABLE_ADDR
                - (SPRITE_ATTR_TABLE_ADDR + SPRITE_ATTR_TABLE_SIZE),
            )
            CALL(block, LDIRVM)
        LOAD_SPEED_PATTERN.call(block)
        UPDATE_SPEED_INDICATOR.call(block)

    LOAD_AND_SHOW = Func("load_and_show", load_and_show)

    def psg_write(block: Block, register: int, value: int) -> None:
        LD.A_n8(block, register & 0xFF)
        OUT(block, PSG_REG_PORT)
        LD.A_n8(block, value & 0xFF)
        OUT(block, PSG_DATA_PORT)

    def wait_sound_duration(block: Block) -> None:
        LD.B_n8(block, SOUND_DURATION_TICKS)
        LD.HL_mn16(block, JIFFY_ADDR)
        LD.D_H(block)
        LD.E_L(block)

        block.label("sound_wait_loop")
        LD.HL_mn16(block, JIFFY_ADDR)
        LD.A_L(block)
        CP.E(block)
        JR_NZ(block, "sound_wait_tick")
        LD.A_H(block)
        CP.D(block)
        JR_Z(block, "sound_wait_loop")

        block.label("sound_wait_tick")
        LD.D_H(block)
        LD.E_L(block)
        DEC.B(block)
        JR_NZ(block, "sound_wait_loop")

    WAIT_SOUND_DURATION = Func("wait_sound_duration", wait_sound_duration)

    def play_tone(block: Block, fine: int, coarse: int) -> None:
        psg_write(block, 7, PSG_MIXER_VALUE)
        psg_write(block, 0, fine)
        psg_write(block, 1, coarse)
        psg_write(block, 8, SOUND_VOLUME)
        WAIT_SOUND_DURATION.call(block)
        psg_write(block, 8, 0)

    def play_speed_up_sound(block: Block) -> None:
        play_tone(block, SOUND_HIGH_FINE, SOUND_HIGH_COARSE)

    PLAY_SPEED_UP_SOUND = Func("play_speed_up_sound", play_speed_up_sound)

    def play_slow_down_sound(block: Block) -> None:
        play_tone(block, SOUND_LOW_FINE, SOUND_LOW_COARSE)

    PLAY_SLOW_DOWN_SOUND = Func("play_slow_down_sound", play_slow_down_sound)

    def print_string(block: Block) -> None:
        block.label("print_string_loop")
        LD.rr(block, "A", "mHL")
        OR.A(block)
        JR_Z(block, "print_string_end")
        CALL(block, CHPUT)
        INC.HL(block)
        JR(block, "print_string_loop")
        block.label("print_string_end")

    PRINT_STRING = Func("print_string", print_string)

    def update_instruction_countdown(block: Block) -> None:
        LD.HL_mn16(block, INSTRUCTION_TICK_TOTAL_ADDR)
        LD.BC_n16(block, JIFFY_PER_SECOND)
        LD.D_n8(block, 0)

        block.label("instr_seconds_loop")
        XOR.A(block)
        block.emit(0xED, 0x42)  # SBC HL,BC
        JR_C(block, "instr_seconds_done")
        INC.D(block)
        JR(block, "instr_seconds_loop")

        block.label("instr_seconds_done")
        ADD.HL_BC(block)
        LD.A_D(block)

        LD.HL_label(block, "INSTR_SECONDS_TABLE")
        LD.E_A(block)
        LD.D_n8(block, 0)
        ADD.HL_DE(block)
        ADD.HL_DE(block)
        LD.DE_n16(block, INSTRUCTION_LINE_BUFFER_ADDR + INSTRUCTION_AUTO_DIGIT_OFFSET)
        LD.A_mHL(block)
        LD.mDE_A(block)
        INC.DE(block)
        INC.HL(block)
        LD.A_mHL(block)
        LD.mDE_A(block)
        block.label("instr_update_end")

    UPDATE_INSTRUCTION_COUNTDOWN = Func("update_instruction_countdown", update_instruction_countdown)

    def print_instruction_line(block: Block) -> None:
        LD.A_n8(block, 0x0D)
        CALL(block, CHPUT)
        LD.HL_n16(block, INSTRUCTION_LINE_BUFFER_ADDR)
        PRINT_STRING.call(block)

    PRINT_INSTRUCTION_LINE = Func("print_instruction_line", print_instruction_line)

    attr_bytes_per_level = speed_level_count * 4

    def update_speed_indicator(block: Block) -> None:
        LD.A_mn16(block, AUTO_INDICATOR_FLAG_ADDR)
        OR.A(block)
        JR_Z(block, "update_speed_indicator_end")
        LOAD_SPEED_PATTERN.call(block)

        LD.HL_mn16(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "update_speed_indicator_use_hidden")

        LD.HL_mn16(block, AUTO_INTERVAL_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "update_speed_indicator_use_hidden")

        LD.A_mn16(block, AUTO_SPEED_INDEX_ADDR)
        LD.L_A(block)
        LD.H_n8(block, 0)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        ADD.HL_HL(block)
        LD.DE_label(block, "SPEED_ATTR_TABLE")
        ADD.HL_DE(block)
        JR(block, "update_speed_indicator_copy")

        block.label("update_speed_indicator_use_hidden")
        LD.HL_label(block, "SPEED_ATTR_HIDDEN")

        block.label("update_speed_indicator_copy")
        LD.DE_n16(block, SPRITE_ATTR_TABLE_ADDR)
        LD.BC_n16(block, attr_bytes_per_level)
        CALL(block, LDIRVM)

        block.label("update_speed_indicator_end")

    UPDATE_SPEED_INDICATOR = Func("update_speed_indicator", update_speed_indicator)

    def load_speed_pattern(block: Block) -> None:
        LD.A_mn16(block, AUTO_INDICATOR_FLAG_ADDR)
        OR.A(block)
        JR_Z(block, "load_speed_pattern_end")
        LD.HL_label(block, "SPEED_PATTERN")
        LD.DE_n16(block, SPRITE_PATTERN_TABLE_ADDR + (SPEED_INDICATOR_PATTERN_ID * 8))
        LD.BC_n16(block, 8)
        CALL(block, LDIRVM)
        block.label("load_speed_pattern_end")

    LOAD_SPEED_PATTERN = Func("load_speed_pattern", load_speed_pattern)

    def reset_auto_timer(block: Block) -> None:
        LD.HL_mn16(block, AUTO_INTERVAL_ADDR)
        LD.mn16_HL(block, AUTO_COUNTDOWN_ADDR)
        LD.HL_mn16(block, JIFFY_ADDR)
        LD.mn16_HL(block, LAST_JIFFY_ADDR)

    RESET_AUTO_TIMER = Func("reset_auto_timer", reset_auto_timer)

    def set_auto_interval(block: Block) -> None:
        LD.mn16_HL(block, AUTO_INTERVAL_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "set_auto_interval_skip_prev")
        LD.mn16_HL(block, AUTO_INTERVAL_PREV_ADDR)
        LD.A_mn16(block, AUTO_SPEED_INDEX_ADDR)
        LD.mn16_A(block, AUTO_SPEED_PREV_ADDR)
        block.label("set_auto_interval_skip_prev")
        RESET_AUTO_TIMER.call(block)
        UPDATE_SPEED_INDICATOR.call(block)

    SET_AUTO_INTERVAL = Func("set_auto_interval", set_auto_interval)

    def set_speed_level(block: Block) -> None:
        LD.mn16_A(block, AUTO_SPEED_INDEX_ADDR)
        LD.HL_label(block, "AUTO_SPEED_TICKS_TABLE")
        LD.E_A(block)
        LD.D_n8(block, 0)
        ADD.HL_DE(block)
        ADD.HL_DE(block)
        LD.E_mHL(block)
        INC.HL(block)
        LD.D_mHL(block)
        LD.rr(block, "H", "D")
        LD.rr(block, "L", "E")
        SET_AUTO_INTERVAL.call(block)
        SHOW_SPEED_INDICATOR.call(block)

    SET_SPEED_LEVEL = Func("set_speed_level", set_speed_level)

    def show_speed_indicator(block: Block) -> None:
        LD.A_mn16(block, AUTO_INDICATOR_FLAG_ADDR)
        OR.A(block)
        JR_Z(block, "show_speed_indicator_end")
        LD.HL_n16(block, AUTO_INDICATOR_TIMEOUT_TICKS)
        LD.mn16_HL(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        LD.HL_mn16(block, JIFFY_ADDR)
        LD.mn16_HL(block, AUTO_INDICATOR_LAST_JIFFY_ADDR)
        UPDATE_SPEED_INDICATOR.call(block)

        block.label("show_speed_indicator_end")

    SHOW_SPEED_INDICATOR = Func("show_speed_indicator", show_speed_indicator)

    def next_image(block: Block) -> None:
        LD.A_mn16(block, CURRENT_INDEX_ADDR)
        INC.A(block)
        CP.n8(block, image_count)
        JR_C(block, "store_index_next")
        XOR.A(block)
        block.label("store_index_next")
        LD.mn16_A(block, CURRENT_INDEX_ADDR)
        LD.rr(block, "C", "A")
        INC.C(block)
        LOAD_AND_SHOW.call(block)
        RESET_AUTO_TIMER.call(block)

    NEXT_IMAGE = Func("next_image", next_image)

    def prev_image(block: Block) -> None:
        LD.A_mn16(block, CURRENT_INDEX_ADDR)
        OR.A(block)
        JR_NZ(block, "dec_index")
        LD.A_n8(block, (image_count - 1) & 0xFF)
        JR(block, "store_index_prev")
        block.label("dec_index")
        DEC.A(block)
        block.label("store_index_prev")
        LD.mn16_A(block, CURRENT_INDEX_ADDR)
        LD.rr(block, "C", "A")
        INC.C(block)
        LOAD_AND_SHOW.call(block)
        RESET_AUTO_TIMER.call(block)

    PREV_IMAGE = Func("prev_image", prev_image)

    def reset_image(block: Block) -> None:
        XOR.A(block)
        LD.mn16_A(block, CURRENT_INDEX_ADDR)
        LD.C_n8(block, 1)
        LOAD_AND_SHOW.call(block)
        RESET_AUTO_TIMER.call(block)

    RESET_IMAGE = Func("reset_image", reset_image)

    def handle_auto_advance(block: Block) -> None:
        LD.HL_mn16(block, AUTO_INTERVAL_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "auto_end")

        LD.HL_mn16(block, LAST_JIFFY_ADDR)
        LD.D_H(block)
        LD.E_L(block)

        LD.HL_mn16(block, JIFFY_ADDR)
        LD.B_H(block)
        LD.C_L(block)

        LD.A_L(block)
        CP.E(block)
        JR_NZ(block, "auto_tick_changed")
        LD.A_H(block)
        CP.D(block)
        JR_NZ(block, "auto_tick_changed")
        JR(block, "auto_end")

        block.label("auto_tick_changed")
        XOR.A(block)
        block.emit(0xED, 0x52)  # SBC HL,DE
        LD.D_H(block)
        LD.E_L(block)

        LD.H_B(block)
        LD.L_C(block)
        LD.mn16_HL(block, LAST_JIFFY_ADDR)

        LD.HL_mn16(block, AUTO_COUNTDOWN_ADDR)
        XOR.A(block)
        block.emit(0xED, 0x52)  # SBC HL,DE
        JR_C(block, "auto_trigger")
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "auto_trigger")
        LD.mn16_HL(block, AUTO_COUNTDOWN_ADDR)
        JR(block, "auto_end")

        block.label("auto_trigger")
        NEXT_IMAGE.call(block)

        block.label("auto_end")

    HANDLE_AUTO = Func("handle_auto_advance", handle_auto_advance)

    def handle_indicator_timeout(block: Block) -> None:
        LD.A_mn16(block, AUTO_INDICATOR_FLAG_ADDR)
        OR.A(block)
        JR_Z(block, "indicator_end")

        LD.HL_mn16(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "indicator_end")

        LD.HL_mn16(block, AUTO_INDICATOR_LAST_JIFFY_ADDR)
        LD.D_H(block)
        LD.E_L(block)

        LD.HL_mn16(block, JIFFY_ADDR)
        LD.B_H(block)
        LD.C_L(block)

        LD.A_L(block)
        CP.E(block)
        JR_NZ(block, "indicator_tick_changed")
        LD.A_H(block)
        CP.D(block)
        JR_NZ(block, "indicator_tick_changed")
        JR(block, "indicator_end")

        block.label("indicator_tick_changed")
        XOR.A(block)
        block.emit(0xED, 0x52)  # SBC HL,DE
        LD.D_H(block)
        LD.E_L(block)

        LD.H_B(block)
        LD.L_C(block)
        LD.mn16_HL(block, AUTO_INDICATOR_LAST_JIFFY_ADDR)

        LD.HL_mn16(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        XOR.A(block)
        block.emit(0xED, 0x52)  # SBC HL,DE
        JR_C(block, "indicator_timeout")
        LD.A_H(block)
        OR.L(block)
        JR_Z(block, "indicator_timeout")
        LD.mn16_HL(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        JR(block, "indicator_end")

        block.label("indicator_timeout")
        LD.HL_n16(block, 0)
        LD.mn16_HL(block, AUTO_INDICATOR_TIMEOUT_ADDR)
        UPDATE_SPEED_INDICATOR.call(block)

        block.label("indicator_end")

    HANDLE_INDICATOR_TIMEOUT = Func("handle_indicator_timeout", handle_indicator_timeout)

    def speed_up(block: Block) -> None:
        LD.A_mn16(block, AUTO_INTERVAL_ADDR)
        OR.A(block)
        JR_NZ(block, "speed_up_use_current")
        LD.A_mn16(block, AUTO_SPEED_PREV_ADDR)
        JR(block, "speed_up_have_index")

        block.label("speed_up_use_current")
        LD.A_mn16(block, AUTO_SPEED_INDEX_ADDR)

        block.label("speed_up_have_index")
        OR.A(block)
        JR_Z(block, "speed_up_apply")
        DEC.A(block)

        block.label("speed_up_apply")
        SET_SPEED_LEVEL.call(block)
        NEXT_IMAGE.call(block)
        PLAY_SPEED_UP_SOUND.call(block)

    SPEED_UP = Func("speed_up", speed_up)

    def slow_down(block: Block) -> None:
        LD.A_mn16(block, AUTO_INTERVAL_ADDR)
        OR.A(block)
        JR_NZ(block, "slow_down_use_current")
        LD.A_mn16(block, AUTO_SPEED_PREV_ADDR)
        JR(block, "slow_down_have_index")

        block.label("slow_down_use_current")
        LD.A_mn16(block, AUTO_SPEED_INDEX_ADDR)

        block.label("slow_down_have_index")
        CP.n8(block, speed_level_count - 1)
        JR_NC(block, "slow_down_apply")
        INC.A(block)

        block.label("slow_down_apply")
        SET_SPEED_LEVEL.call(block)
        NEXT_IMAGE.call(block)
        PLAY_SLOW_DOWN_SOUND.call(block)

    SLOW_DOWN = Func("slow_down", slow_down)

    b.label("main")
    store_stack_pointer_macro(b)
    enaslt_macro(b)

    if show_instructions:
        LD.A_n8(b, 0)
        CALL(b, CHGMOD)
        LD.A_n8(b, 0x0F)
        LD.mn16_A(b, FORCLR)
        LD.A_n8(b, INSTRUCTION_BG_COLOR)
        LD.mn16_A(b, BAKCLR)
        LD.mn16_A(b, BDRCLR)
        CALL(b, CHGCLR)

        LD.HL_label(b, "INSTR_TEXT_STATIC")
        PRINT_STRING.call(b)

        if instruction_autostart_seconds > 0:
            LD.HL_n16(b, instruction_autostart_seconds * JIFFY_PER_SECOND)
            LD.mn16_HL(b, INSTRUCTION_TICK_TOTAL_ADDR)
            LD.HL_mn16(b, JIFFY_ADDR)
            LD.mn16_HL(b, INSTRUCTION_LAST_JIFFY_ADDR)

            LD.HL_label(b, "INSTR_AUTO_TEMPLATE")
            LD.DE_n16(b, INSTRUCTION_LINE_BUFFER_ADDR)
            LD.BC_n16(b, INSTRUCTION_LINE_LENGTH)
            b.emit(0xED, 0xB0)  # LDIR

            UPDATE_INSTRUCTION_COUNTDOWN.call(b)
            PRINT_INSTRUCTION_LINE.call(b)

            b.label("instruction_wait_loop")
            CALL(b, CHSNS)
            CP.n8(b, 0)
            JR_NZ(b, "instruction_wait_key")

            LD.HL_mn16(b, INSTRUCTION_LAST_JIFFY_ADDR)
            LD.D_H(b)
            LD.E_L(b)

            LD.HL_mn16(b, JIFFY_ADDR)
            LD.B_H(b)
            LD.C_L(b)

            LD.A_L(b)
            CP.E(b)
            JR_NZ(b, "instruction_tick_changed")
            LD.A_H(b)
            CP.D(b)
            JR_NZ(b, "instruction_tick_changed")
            JR(b, "instruction_wait_loop")

            b.label("instruction_tick_changed")
            XOR.A(b)
            b.emit(0xED, 0x52)  # SBC HL,DE
            LD.D_H(b)
            LD.E_L(b)

            LD.H_B(b)
            LD.L_C(b)
            LD.mn16_HL(b, INSTRUCTION_LAST_JIFFY_ADDR)

            LD.HL_mn16(b, INSTRUCTION_TICK_TOTAL_ADDR)
            XOR.A(b)
            b.emit(0xED, 0x52)  # SBC HL,DE
            JR_C(b, "instruction_start_auto")
            LD.A_H(b)
            OR.L(b)
            JR_Z(b, "instruction_start_auto")
            LD.mn16_HL(b, INSTRUCTION_TICK_TOTAL_ADDR)
            UPDATE_INSTRUCTION_COUNTDOWN.call(b)
            PRINT_INSTRUCTION_LINE.call(b)
            JR(b, "instruction_wait_loop")

            b.label("instruction_wait_key")
            CALL(b, CHGET)
            JR(b, "instruction_end")

            b.label("instruction_start_auto")
            b.label("instruction_end")
        else:
            LD.HL_label(b, "INSTR_TEXT_WAIT")
            PRINT_STRING.call(b)
            CALL(b, CHGET)

    LD.A_n8(b, 2)
    CALL(b, CHGMOD)
    set_msx2_palette_default_macro(b)
    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, background_color & 0x0F)
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    LD.A_n8(b, 1 if enable_speed_indicator else 0)
    LD.mn16_A(b, AUTO_INDICATOR_FLAG_ADDR)
    LD.A_n8(b, initial_speed_level & 0xFF)
    LD.mn16_A(b, AUTO_SPEED_INDEX_ADDR)
    LD.mn16_A(b, AUTO_SPEED_PREV_ADDR)
    LD.HL_n16(b, speed_tick_levels[initial_speed_level])
    LD.mn16_HL(b, AUTO_INTERVAL_PREV_ADDR)
    LD.HL_n16(b, 0)
    LD.mn16_HL(b, AUTO_INDICATOR_TIMEOUT_ADDR)

    if start_paused:
        LD.HL_n16(b, 0)
        SET_AUTO_INTERVAL.call(b)
    else:
        LD.A_n8(b, initial_speed_level & 0xFF)
        SET_SPEED_LEVEL.call(b)
        SHOW_SPEED_INDICATOR.call(b)

    LD.A_n8(b, 0)
    LD.mn16_A(b, CURRENT_INDEX_ADDR)
    LD.C_n8(b, 1)
    LOAD_AND_SHOW.call(b)
    RESET_AUTO_TIMER.call(b)

    b.label("main_loop")
    HANDLE_INDICATOR_TIMEOUT.call(b)
    CALL(b, CHSNS)
    CP.n8(b, 0)
    JR_Z(b, "main_loop_auto")

    CALL(b, CHGET)
    LD.B_A(b)
    LD.A_n8(b, KEYBOARD_ROW_SHIFT)
    CALL(b, SNSMAT)
    LD.D_A(b)
    LD.A_B(b)

    CP.n8(b, KEY_SPACE)
    JR_Z(b, "key_space")
    CP.n8(b, KEY_DOWN)
    JR_Z(b, "key_down")
    CP.n8(b, KEY_UP)
    JR_Z(b, "key_up")
    CP.n8(b, KEY_ESC)
    JR_Z(b, "key_reset")
    JR(b, "main_loop")

    b.label("key_down")
    LD.A_D(b)
    AND.n8(b, KEYBOARD_SHIFT_MASK)
    JR_NZ(b, "key_next")
    SLOW_DOWN.call(b)
    JR(b, "main_loop")

    b.label("key_up")
    LD.A_D(b)
    AND.n8(b, KEYBOARD_SHIFT_MASK)
    JR_NZ(b, "key_prev")
    SPEED_UP.call(b)
    JR(b, "main_loop")

    b.label("key_space")
    LD.A_D(b)
    AND.n8(b, KEYBOARD_SHIFT_MASK)
    JR_Z(b, "key_space_next")
    LD.B_n8(b, 1)
    JR(b, "key_space_pause_start")

    b.label("key_space_next")
    LD.B_n8(b, 0)

    b.label("key_space_pause_start")
    LD.HL_mn16(b, AUTO_INTERVAL_ADDR)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "key_space_pause_set")
    LD.mn16_HL(b, AUTO_INTERVAL_PREV_ADDR)
    LD.A_mn16(b, AUTO_SPEED_INDEX_ADDR)
    LD.mn16_A(b, AUTO_SPEED_PREV_ADDR)
    b.label("key_space_pause_set")
    LD.HL_n16(b, 0)
    SET_AUTO_INTERVAL.call(b)
    LD.A_B(b)
    OR.A(b)
    JR_Z(b, "key_space_do_next")
    PREV_IMAGE.call(b)
    JR(b, "main_loop")

    b.label("key_space_do_next")
    NEXT_IMAGE.call(b)
    JR(b, "main_loop")

    b.label("key_next")
    NEXT_IMAGE.call(b)
    JR(b, "main_loop")

    b.label("key_prev")
    PREV_IMAGE.call(b)
    JR(b, "main_loop")

    b.label("key_reset")
    RESET_IMAGE.call(b)
    JR(b, "main_loop")

    b.label("main_loop_auto")
    HANDLE_AUTO.call(b)
    JR(b, "main_loop")

    LOAD_AND_SHOW.define(b)
    PRINT_STRING.define(b)
    UPDATE_SPEED_INDICATOR.define(b)
    LOAD_SPEED_PATTERN.define(b)
    RESET_AUTO_TIMER.define(b)
    SET_AUTO_INTERVAL.define(b)
    SET_SPEED_LEVEL.define(b)
    SHOW_SPEED_INDICATOR.define(b)
    NEXT_IMAGE.define(b)
    PREV_IMAGE.define(b)
    RESET_IMAGE.define(b)
    HANDLE_AUTO.define(b)
    HANDLE_INDICATOR_TIMEOUT.define(b)
    SPEED_UP.define(b)
    SLOW_DOWN.define(b)
    WAIT_SOUND_DURATION.define(b)
    PLAY_SPEED_UP_SOUND.define(b)
    PLAY_SLOW_DOWN_SOUND.define(b)
    UPDATE_INSTRUCTION_COUNTDOWN.define(b)
    PRINT_INSTRUCTION_LINE.define(b)

    b.label("INSTR_TEXT_STATIC")
    DB(b, *INSTRUCTION_TEXT_STATIC.encode("ascii"), 0x00)
    b.label("INSTR_TEXT_WAIT")
    DB(b, *INSTRUCTION_TEXT_WAIT.encode("ascii"), 0x00)
    b.label("INSTR_AUTO_TEMPLATE")
    DB(b, *INSTRUCTION_AUTO_LINE_TEMPLATE.encode("ascii"), 0x00)
    b.label("INSTR_SECONDS_TABLE")
    DB(b, *"".join(INSTRUCTION_SECONDS_TEXT).encode("ascii"))

    b.label("AUTO_SPEED_TICKS_TABLE")
    DW(b, *speed_tick_levels)

    speed_attr_data: list[int] = []
    for level in range(speed_level_count):
        visible_marks = speed_level_count - level
        for idx in range(speed_level_count):
            if idx < visible_marks:
                y = (SPEED_INDICATOR_Y_BOTTOM - (idx * SPEED_INDICATOR_Y_STEP)) & 0xFF
            else:
                y = 0xD0
            speed_attr_data.extend(
                [y, SPEED_INDICATOR_X, SPEED_INDICATOR_PATTERN_ID, SPEED_INDICATOR_COLOR]
            )

    b.label("SPEED_ATTR_TABLE")
    DB(b, *speed_attr_data)

    b.label("SPEED_ATTR_HIDDEN")
    hidden_attr_data: list[int] = []
    for _ in range(speed_level_count):
        hidden_attr_data.extend([0xD0, SPEED_INDICATOR_X, SPEED_INDICATOR_PATTERN_ID, SPEED_INDICATOR_COLOR])
    DB(b, *hidden_attr_data)

    b.label("SPEED_PATTERN")
    speed_pattern = [
        0x18,
        0x3C,
        0x7E,
        0xFF,
        0x66,
        0x42,
        0x00,
        0x00,
    ]
    DB(b, *speed_pattern)

    return bytes(pad_bytes(list(b.finalize(origin=0x4000)), PAGE_SIZE, 0x00))


def build_rom(
    images: list[bytes],
    show_instructions: bool,
    background_color: int,
    speed_tick_levels: list[int],
    initial_speed_level: int,
    start_paused: bool,
    enable_speed_indicator: bool,
    instruction_autostart_seconds: int,
    copy_sprite_tables: bool,
) -> bytes:
    max_images = MAX_BANKS - 1
    image_count = len(images)
    if image_count > max_images:
        warnings.warn(
            (
                "Too many images for a 4 MiB ASCII16 MegaROM; "
                "only the first %d of %d will be embedded"
            )
            % (max_images, image_count),
            RuntimeWarning,
        )
        images = images[:max_images]
        image_count = len(images)
    if not 0 <= background_color <= 0x0F:
        raise ValueError("background_color must be between 0 and 15")

    bank0 = build_boot_bank(
        image_count,
        show_instructions,
        background_color,
        speed_tick_levels,
        initial_speed_level,
        start_paused,
        enable_speed_indicator,
        instruction_autostart_seconds,
        copy_sprite_tables,
    )
    banks = [bank0]

    for idx, image in enumerate(images, start=1):
        if len(image) != VRAM_SIZE:
            raise ValueError(f"Image {idx} must be {VRAM_SIZE} bytes after conversion")
        banks.append(bytes(pad_bytes(list(image), PAGE_SIZE, 0x00)))

    return b"".join(banks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed SC2 images into an ASCII16 MegaROM with key navigation."
    )
    parser.add_argument(
        "images",
        nargs="+",
        type=Path,
        help="Input .sc2 files or directories containing .sc2 files (max 255)",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output ROM path")
    inst_group = parser.add_mutually_exclusive_group()
    inst_group.add_argument(
        "-inst",
        "--with-instructions",
        dest="with_instructions",
        action="store_true",
        help="Show a SCREEN0 usage message before the first image (default)",
    )
    inst_group.add_argument(
        "-noinst",
        "--no-instructions",
        dest="with_instructions",
        action="store_false",
        help="Skip the SCREEN0 usage message",
    )
    parser.add_argument(
        "-bg", "--background-color",
        type=int_from_str,
        default=0,
        help="SCREEN2 background color value (0-15, default: 0)",
    )
    parser.add_argument(
        "--auto-interval",
        type=float,
        default=AUTO_SPEED_SECONDS[DEFAULT_AUTO_SPEED_LEVEL],
        help=(
            "Seconds per automatic page advance. "
            "Value is rounded to the nearest of the 8 fixed speed steps; "
            "use 0 to pause on startup."
        ),
    )
    parser.add_argument(
        "--auto-speed-level",
        type=int,
        choices=range(1, len(AUTO_SPEED_SECONDS) + 1),
        help="Initial auto speed level (1=fastest, 8=slowest). Overrides --auto-interval when set.",
    )
    parser.add_argument(
        "--speed-indicator",
        dest="speed_indicator",
        action="store_true",
        help="Show a compact speed indicator using sprites in the bottom-right corner",
    )
    parser.add_argument(
        "--no-speed-indicator",
        dest="speed_indicator",
        action="store_false",
        help="Hide the speed indicator (default)",
    )
    parser.add_argument(
        "--instruction-autostart",
        type=int,
        default=5,
        help="Seconds before auto-starting from the instruction screen (0 waits for key, max 30, default: 3).",
    )
    parser.add_argument(
        "--instruction-wait-key",
        dest="instruction_autostart",
        action="store_const",
        const=0,
        help="Disable auto-start and wait for a key press on the instruction screen.",
    )
    parser.add_argument(
        "--copy-sprite-vram",
        dest="copy_sprite_vram",
        action="store_true",
        help=(
            "Copy sprite attribute/pattern data from each page when loading. "
            "Disabled by default to preserve sprite-based indicators."
        ),
    )
    parser.set_defaults(with_instructions=True, speed_indicator=False, copy_sprite_vram=False)
    return parser.parse_args()


def resolve_output_path(output_path: Path | None, first_input: Path) -> Path:
    if output_path is None:
        output_path = first_input.with_suffix(".rom")

    if output_path.suffix == "":
        output_path = output_path.with_suffix(".rom")

    stem = output_path.stem
    if "[ASCII16]" not in stem:
        output_path = output_path.with_name(stem + "[ASCII16]" + output_path.suffix)

    return output_path


def collect_sc2_paths(inputs: list[Path]) -> list[Path]:
    sc2_paths: list[Path] = []
    for entry in inputs:
        if entry.is_dir():
            sc2_paths.extend(sorted(entry.rglob("*.sc2")))
        else:
            sc2_paths.append(entry)

    sc2_paths = [path for path in sc2_paths if path.is_file()]
    return sc2_paths


def main() -> None:
    args = parse_args()

    sc2_paths = collect_sc2_paths(args.images)
    if not sc2_paths:
        raise SystemExit("No .sc2 files found in the provided inputs.")

    for path in sc2_paths:
        if not path.is_file():
            raise SystemExit(f"Input file not found: {path}")

    image_bytes = [sc2_to_vram(path.read_bytes()) for path in sc2_paths]

    if args.auto_interval < 0:
        raise SystemExit("--auto-interval must be zero or greater")
    if not 0 <= args.instruction_autostart <= 30:
        raise SystemExit("--instruction-autostart must be between 0 and 30")

    speed_tick_levels = [max(1, seconds_to_jiffies(sec)) for sec in AUTO_SPEED_SECONDS]
    start_paused = False
    initial_speed_level = DEFAULT_AUTO_SPEED_LEVEL

    if args.auto_speed_level is not None:
        initial_speed_level = args.auto_speed_level - 1

    if args.auto_interval == 0:
        start_paused = True
    elif args.auto_speed_level is None:
        target_ticks = seconds_to_jiffies(args.auto_interval)
        initial_speed_level = min(
            range(len(speed_tick_levels)),
            key=lambda idx: abs(speed_tick_levels[idx] - target_ticks),
        )

    rom_bytes = build_rom(
        image_bytes,
        args.with_instructions,
        args.background_color,
        speed_tick_levels,
        initial_speed_level,
        start_paused,
        args.speed_indicator,
        args.instruction_autostart,
        args.copy_sprite_vram,
    )
    out_path = resolve_output_path(args.output, sc2_paths[0])
    out_path.write_bytes(rom_bytes)
    print(f"Wrote {len(rom_bytes)} bytes to {out_path}")


if __name__ == "__main__":
    main()
