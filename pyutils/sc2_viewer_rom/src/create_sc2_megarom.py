"""Create an ASCII16 MegaROM that flips through multiple SCREEN2 images."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from mmsxxasmhelper.core import ADD, AND, Block, CALL, CP, DB, DEC, Func, INC, JR, JR_C, JR_NZ, JR_Z, LD, OR, XOR
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        enaslt_macro,
        place_msx_rom_header_macro,
        set_msx2_palette_default_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import JIFFY_ADDR, pad_bytes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "mmsxxasmhelper" / "src"))
    from mmsxxasmhelper.core import ADD, AND, Block, CALL, CP, DB, DEC, Func, INC, JR, JR_C, JR_NZ, JR_Z, LD, OR, XOR
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

CHSNS = 0x009C
CHGET = 0x009F
CHPUT = 0x00A2
CHGCLR = 0x0062
FORCLR = 0xF3E9
BAKCLR = 0xF3EA
BDRCLR = 0xF3EB
SNSMAT = 0x0141

KEY_SPACE = 0x20
KEY_UP = 0x1E
KEY_DOWN = 0x1F
KEY_ESC = 0x1B

KEYBOARD_ROW_SHIFT = 0x06
KEYBOARD_SHIFT_MASK = 0x01

INSTRUCTION_TEXT = (
    "MMSXX SC2 VIEWER\r\n"
    "\r\n"
    "SPACE: NEXT + PAUSE\r\n"
    "DOWN: NEXT\r\n"
    "UP: PREV\r\n"
    "SHIFT+UD: SPD\r\n"
    "ESC: FIRST\r\n"
    "\r\n"
    "PRESS ANY KEY\r\n"
)

INSTRUCTION_BG_COLOR = 0x04

JIFFY_PER_SECOND = 60


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
    auto_interval_ticks: int,
    auto_step_ticks: int,
    auto_min_ticks: int,
    auto_max_ticks: int,
    auto_resume_ticks: int,
) -> bytes:
    if not 1 <= image_count <= 0xFF:
        raise ValueError("image_count must be between 1 and 255")
    for name, value in {
        "auto_interval_ticks": auto_interval_ticks,
        "auto_step_ticks": auto_step_ticks,
        "auto_min_ticks": auto_min_ticks,
        "auto_max_ticks": auto_max_ticks,
        "auto_resume_ticks": auto_resume_ticks,
    }.items():
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"{name} must fit in 16 bits")
    if auto_step_ticks <= 0:
        raise ValueError("auto_step_ticks must be positive")
    if auto_min_ticks <= 0:
        raise ValueError("auto_min_ticks must be positive")
    if auto_min_ticks > auto_max_ticks:
        raise ValueError("auto_min_ticks must be less than or equal to auto_max_ticks")

    b = Block()
    place_msx_rom_header_macro(b, entry_point=0x4010)

    def load_and_show(block: Block) -> None:
        LD.A_C(block)
        LD.mn16_A(block, ASCII16_PAGE2_REG)
        LD.HL_n16(block, 0x8000)
        LD.DE_n16(block, 0x0000)
        LD.BC_n16(block, VRAM_SIZE)
        CALL(block, LDIRVM)

    LOAD_AND_SHOW = Func("load_and_show", load_and_show)

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
        block.label("set_auto_interval_skip_prev")
        RESET_AUTO_TIMER.call(block)

    SET_AUTO_INTERVAL = Func("set_auto_interval", set_auto_interval)

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

    def speed_up(block: Block) -> None:
        LD.HL_mn16(block, AUTO_INTERVAL_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_NZ(block, "speed_up_have_interval")
        LD.HL_mn16(block, AUTO_INTERVAL_PREV_ADDR)
        block.label("speed_up_have_interval")

        LD.DE_n16(block, auto_step_ticks)
        XOR.A(block)
        block.emit(0xED, 0x52)  # SBC HL,DE
        JR_C(block, "speed_up_set_min")

        LD.A_H(block)
        CP.n8(block, (auto_min_ticks >> 8) & 0xFF)
        JR_C(block, "speed_up_set_min")
        JR_Z(block, "speed_up_check_low")
        JR(block, "speed_up_apply")

        block.label("speed_up_check_low")
        LD.A_L(block)
        CP.n8(block, auto_min_ticks & 0xFF)
        JR_C(block, "speed_up_set_min")
        JR(block, "speed_up_apply")

        block.label("speed_up_set_min")
        LD.HL_n16(block, auto_min_ticks)

        block.label("speed_up_apply")
        SET_AUTO_INTERVAL.call(block)

    SPEED_UP = Func("speed_up", speed_up)

    def slow_down(block: Block) -> None:
        LD.HL_mn16(block, AUTO_INTERVAL_ADDR)
        LD.A_H(block)
        OR.L(block)
        JR_NZ(block, "slow_down_have_interval")
        LD.HL_mn16(block, AUTO_INTERVAL_PREV_ADDR)
        block.label("slow_down_have_interval")

        LD.DE_n16(block, auto_step_ticks)
        ADD.HL_DE(block)

        LD.A_H(block)
        CP.n8(block, (auto_max_ticks >> 8) & 0xFF)
        JR_C(block, "slow_down_apply")
        JR_Z(block, "slow_down_check_low")
        JR(block, "slow_down_set_max")

        block.label("slow_down_check_low")
        LD.A_L(block)
        CP.n8(block, auto_max_ticks & 0xFF)
        JR_C(block, "slow_down_apply")

        block.label("slow_down_set_max")
        LD.HL_n16(block, auto_max_ticks)

        block.label("slow_down_apply")
        SET_AUTO_INTERVAL.call(block)

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
        LD.HL_label(b, "INSTR_TEXT")
        PRINT_STRING.call(b)
        CALL(b, CHGET)

    LD.HL_n16(b, auto_resume_ticks)
    LD.mn16_HL(b, AUTO_INTERVAL_PREV_ADDR)
    LD.HL_n16(b, auto_interval_ticks)
    SET_AUTO_INTERVAL.call(b)

    LD.A_n8(b, 2)
    CALL(b, CHGMOD)
    # set_msx2_palette_default_macro(b)　うまく動いていない
    LD.A_n8(b, 0x0F)
    LD.mn16_A(b, FORCLR)
    LD.A_n8(b, background_color & 0x0F)
    LD.mn16_A(b, BAKCLR)
    LD.mn16_A(b, BDRCLR)
    CALL(b, CHGCLR)

    LD.A_n8(b, 0)
    LD.mn16_A(b, CURRENT_INDEX_ADDR)
    LD.C_n8(b, 1)
    LOAD_AND_SHOW.call(b)
    RESET_AUTO_TIMER.call(b)

    b.label("main_loop")
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
    LD.HL_mn16(b, AUTO_INTERVAL_ADDR)
    LD.A_H(b)
    OR.L(b)
    JR_Z(b, "key_space_pause_set")
    LD.mn16_HL(b, AUTO_INTERVAL_PREV_ADDR)
    b.label("key_space_pause_set")
    LD.HL_n16(b, 0)
    SET_AUTO_INTERVAL.call(b)
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
    RESET_AUTO_TIMER.define(b)
    SET_AUTO_INTERVAL.define(b)
    NEXT_IMAGE.define(b)
    PREV_IMAGE.define(b)
    RESET_IMAGE.define(b)
    HANDLE_AUTO.define(b)
    SPEED_UP.define(b)
    SLOW_DOWN.define(b)
    b.label("INSTR_TEXT")
    DB(b, *INSTRUCTION_TEXT.encode("ascii"), 0x00)

    return bytes(pad_bytes(list(b.finalize(origin=0x4000)), PAGE_SIZE, 0x00))


def build_rom(
    images: list[bytes],
    show_instructions: bool,
    background_color: int,
    auto_interval_ticks: int,
    auto_step_ticks: int,
    auto_min_ticks: int,
    auto_max_ticks: int,
    auto_resume_ticks: int,
) -> bytes:
    image_count = len(images)
    if image_count + 1 > MAX_BANKS:
        raise ValueError("Too many images for a 4 MiB ASCII16 MegaROM")
    if not 0 <= background_color <= 0x0F:
        raise ValueError("background_color must be between 0 and 15")

    bank0 = build_boot_bank(
        image_count,
        show_instructions,
        background_color,
        auto_interval_ticks,
        auto_step_ticks,
        auto_min_ticks,
        auto_max_ticks,
        auto_resume_ticks,
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
        default=2.0,
        help="Seconds per automatic page advance (0 to disable, default: 2.0)",
    )
    parser.add_argument(
        "--auto-step",
        type=float,
        default=0.2,
        help="Seconds to add/subtract per SHIFT+cursor speed adjustment (default: 0.2)",
    )
    parser.add_argument(
        "--min-auto-interval",
        type=float,
        default=0.2,
        help="Minimum seconds allowed for auto advance when adjusting (default: 0.2)",
    )
    parser.add_argument(
        "--max-auto-interval",
        type=float,
        default=10.0,
        help="Maximum seconds allowed for auto advance when adjusting (default: 10.0)",
    )
    parser.set_defaults(with_instructions=True)
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

    if args.auto_step <= 0:
        raise SystemExit("--auto-step must be greater than 0")
    if args.min_auto_interval <= 0:
        raise SystemExit("--min-auto-interval must be greater than 0")
    if args.max_auto_interval <= 0:
        raise SystemExit("--max-auto-interval must be greater than 0")
    if args.min_auto_interval > args.max_auto_interval:
        raise SystemExit("--min-auto-interval cannot exceed --max-auto-interval")
    if args.auto_interval < 0:
        raise SystemExit("--auto-interval must be zero or greater")

    auto_step_ticks = max(1, seconds_to_jiffies(args.auto_step))
    auto_min_ticks = max(1, seconds_to_jiffies(args.min_auto_interval))
    auto_max_ticks = max(auto_min_ticks, seconds_to_jiffies(args.max_auto_interval))
    auto_interval_ticks = seconds_to_jiffies(args.auto_interval)
    if 0 < auto_interval_ticks < auto_min_ticks:
        auto_interval_ticks = auto_min_ticks
    if auto_interval_ticks > auto_max_ticks:
        auto_interval_ticks = auto_max_ticks
    auto_resume_ticks = auto_interval_ticks if auto_interval_ticks > 0 else auto_min_ticks

    rom_bytes = build_rom(
        image_bytes,
        args.with_instructions,
        args.background_color,
        auto_interval_ticks,
        auto_step_ticks,
        auto_min_ticks,
        auto_max_ticks,
        auto_resume_ticks,
    )
    out_path = resolve_output_path(args.output, sc2_paths[0])
    out_path.write_bytes(rom_bytes)
    print(f"Wrote {len(rom_bytes)} bytes to {out_path}")


if __name__ == "__main__":
    main()
