"""Create an ASCII16 MegaROM that flips through multiple SCREEN2 images."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from mmsxxasmhelper.core import Block, CALL, CP, DB, DEC, Func, INC, JR, JR_C, JR_NZ, JR_Z, LD, OR, XOR
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        enaslt_macro,
        place_msx_rom_header_macro,
        set_msx2_palette_default_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "mmsxxasmhelper" / "src"))
    from mmsxxasmhelper.core import Block, CALL, CP, DB, DEC, Func, INC, JR, JR_C, JR_NZ, JR_Z, LD, OR, XOR
    from mmsxxasmhelper.msxutils import (
        CHGMOD,
        LDIRVM,
        enaslt_macro,
        place_msx_rom_header_macro,
        set_msx2_palette_default_macro,
        store_stack_pointer_macro,
    )
    from mmsxxasmhelper.utils import pad_bytes

PAGE_SIZE = 0x4000
MAX_ROM_SIZE = 0x400000
MAX_BANKS = MAX_ROM_SIZE // PAGE_SIZE
VRAM_SIZE = 0x4000
SC2_HEADER_SIZE = 7
TRIMMED_SC2_SIZE = 0x3780

ASCII16_PAGE2_REG = 0x7000
CURRENT_INDEX_ADDR = 0xC000

CHSNS = 0x009C
CHGET = 0x009F
CHPUT = 0x00A2
CHGCLR = 0x0062
FORCLR = 0xF3E9
BAKCLR = 0xF3EA
BDRCLR = 0xF3EB

KEY_SPACE = 0x20
KEY_UP = 0x1E
KEY_DOWN = 0x1F
KEY_ESC = 0x1B

INSTRUCTION_TEXT = (
    "MMSXX SC2 VIEWER\r\n"
    "\r\n"
    "SPACE/DOWN: NEXT\r\n"
    "UP: PREV\r\n"
    "ESC: FIRST\r\n"
    "\r\n"
    "PRESS ANY KEY\r\n"
)

INSTRUCTION_BG_COLOR = 0x04


def int_from_str(value: str) -> int:
    return int(value, 0)


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
) -> bytes:
    if not 1 <= image_count <= 0xFF:
        raise ValueError("image_count must be between 1 and 255")

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

    b.label("main_loop")
    CALL(b, CHSNS)
    CP.n8(b, 0)
    JR_Z(b, "main_loop")

    CALL(b, CHGET)
    CP.n8(b, KEY_SPACE)
    JR_Z(b, "key_next")
    CP.n8(b, KEY_DOWN)
    JR_Z(b, "key_next")
    CP.n8(b, KEY_UP)
    JR_Z(b, "key_prev")
    CP.n8(b, KEY_ESC)
    JR_Z(b, "key_reset")
    JR(b, "main_loop")

    b.label("key_next")
    LD.A_mn16(b, CURRENT_INDEX_ADDR)
    INC.A(b)
    CP.n8(b, image_count)
    JR_C(b, "store_index")
    XOR.A(b)
    b.label("store_index")
    LD.mn16_A(b, CURRENT_INDEX_ADDR)
    LD.rr(b, "C", "A")
    INC.C(b)
    LOAD_AND_SHOW.call(b)
    JR(b, "main_loop")

    b.label("key_prev")
    LD.A_mn16(b, CURRENT_INDEX_ADDR)
    OR.A(b)
    JR_NZ(b, "dec_index")
    LD.A_n8(b, (image_count - 1) & 0xFF)
    JR(b, "store_index_prev")
    b.label("dec_index")
    DEC.A(b)
    b.label("store_index_prev")
    LD.mn16_A(b, CURRENT_INDEX_ADDR)
    LD.rr(b, "C", "A")
    INC.C(b)
    LOAD_AND_SHOW.call(b)
    JR(b, "main_loop")

    b.label("key_reset")
    XOR.A(b)
    LD.mn16_A(b, CURRENT_INDEX_ADDR)
    LD.C_n8(b, 1)
    LOAD_AND_SHOW.call(b)
    JR(b, "main_loop")

    LOAD_AND_SHOW.define(b)
    PRINT_STRING.define(b)
    b.label("INSTR_TEXT")
    DB(b, *INSTRUCTION_TEXT.encode("ascii"), 0x00)

    return bytes(pad_bytes(list(b.finalize(origin=0x4000)), PAGE_SIZE, 0x00))


def build_rom(
    images: list[bytes],
    show_instructions: bool,
    background_color: int,
) -> bytes:
    image_count = len(images)
    if image_count + 1 > MAX_BANKS:
        raise ValueError("Too many images for a 4 MiB ASCII16 MegaROM")
    if not 0 <= background_color <= 0x0F:
        raise ValueError("background_color must be between 0 and 15")

    bank0 = build_boot_bank(image_count, show_instructions, background_color)
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
    parser.add_argument(
        "-inst", "--with-instructions",
        action="store_true",
        help="Show a SCREEN0 usage message before the first image",
    )
    parser.add_argument(
        "-bg", "--background-color",
        type=int_from_str,
        default=0,
        help="SCREEN2 background color value (0-15, default: 0)",
    )
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

    rom_bytes = build_rom(
        image_bytes,
        args.with_instructions,
        args.background_color,
    )
    out_path = resolve_output_path(args.output, sc2_paths[0])
    out_path.write_bytes(rom_bytes)
    print(f"Wrote {len(rom_bytes)} bytes to {out_path}")


if __name__ == "__main__":
    main()
