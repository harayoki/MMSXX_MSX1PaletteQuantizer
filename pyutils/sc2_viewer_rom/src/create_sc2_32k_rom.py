"""Create a 32 KiB (non-MegaROM) MSX ROM that shows a SCREEN2 image.

This script takes an `.sc2` file (raw SCREEN2 VRAM dump) and embeds it into a
simple 32 KiB ROM. On boot the ROM switches to SCREEN2, copies the VRAM data to
address 0, and halts so the image stays on screen.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

ROM_SIZE = 0x8000  # 32 KiB
VRAM_SIZE = 0x4000  # SCREEN2 VRAM dump size (16 KiB)
SC2_HEADER_SIZE = 7  # Optional header seen in some .sc2 files
ROM_BASE = 0x4000
HEADER_SIGNATURE = b"AB"
CHGMOD = 0x005F
CHGCLR = 0x0062
LDIRVM = 0x005C


def int_from_str(value: str) -> int:
    """Parse an integer that may be expressed in decimal or hex."""

    return int(value, 0)


def build_loader(
    sc2_address: int, image_length: int, background_color: int, border_color: int
) -> bytes:
    """Build the Z80 loader that switches to SCREEN2 and copies VRAM data.

    The loader uses BIOS calls only, so it works on plain MSX1 hardware.
    """

    if image_length > VRAM_SIZE:
        raise ValueError("SC2 data exceeds SCREEN2 VRAM size")

    code: Iterable[int] = (
        0x3E,
        0x02,  # LD A,2          ; SCREEN2
        0xCD,
        CHGMOD & 0xFF,
        (CHGMOD >> 8) & 0xFF,  # CALL CHGMOD
        0x06,
        0x0F,  # LD B,0Fh        ; foreground (white)
        0x0E,
        background_color & 0x0F,  # LD C,background
        0x16,
        border_color & 0x0F,  # LD D,border
        0xCD,
        CHGCLR & 0xFF,
        (CHGCLR >> 8) & 0xFF,  # CALL CHGCLR
        0x21,
        sc2_address & 0xFF,
        (sc2_address >> 8) & 0xFF,  # LD HL,sc2_data
        0x11,
        0x00,
        0x00,  # LD DE,0000h     ; VRAM destination
        0x01,
        image_length & 0xFF,
        (image_length >> 8) & 0xFF,  # LD BC,data_length
        0xCD,
        LDIRVM & 0xFF,
        (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM
        0x18,
        0xFE,  # JR $            ; hang to keep the image
    )
    return bytes(code)


def sanitize_sc2_data(sc2_bytes: bytes) -> bytes:
    """Strip optional 7-byte .sc2 header if present and validate size."""

    if len(sc2_bytes) == VRAM_SIZE + SC2_HEADER_SIZE:
        return sc2_bytes[SC2_HEADER_SIZE:]

    if len(sc2_bytes) > VRAM_SIZE:
        raise ValueError("SC2 data must be 16 KiB or smaller")

    return sc2_bytes


def build_rom(
    sc2_bytes: bytes, fill_byte: int, background_color: int, border_color: int
) -> bytes:
    """Build a 32 KiB ROM image that displays the provided SC2 data."""

    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must fit in a byte")
    if not 0 <= background_color <= 0x0F:
        raise ValueError("background_color must be between 0 and 15")
    if not 0 <= border_color <= 0x0F:
        raise ValueError("border_color must be between 0 and 15")

    rom = bytearray([fill_byte] * ROM_SIZE)

    entry_address = ROM_BASE + 0x10
    code_offset = entry_address - ROM_BASE

    # Reserve space for the loader and align SC2 data on a 16-byte boundary.
    # The header occupies the first 16 bytes, so we start code at 0x4010.
    loader_placeholder = build_loader(0, 0, background_color, border_color)
    data_offset = (code_offset + len(loader_placeholder) + 0x0F) & ~0x0F
    sc2_address = ROM_BASE + data_offset

    loader = build_loader(sc2_address, len(sc2_bytes), background_color, border_color)

    # Header
    rom[0:2] = HEADER_SIGNATURE
    rom[2] = entry_address & 0xFF
    rom[3] = (entry_address >> 8) & 0xFF
    rom[4] = 0x00
    rom[5] = 0x00
    rom[6] = 0x00

    # Body
    rom[code_offset : code_offset + len(loader)] = loader
    rom[data_offset : data_offset + len(sc2_bytes)] = sc2_bytes

    return bytes(rom)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Embed a SCREEN2 (.sc2) file into a 32 KiB non-MegaROM MSX ROM."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source .sc2 file (raw SCREEN2 VRAM dump)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output ROM path (defaults to input name with .rom extension)",
    )
    parser.add_argument(
        "--fill-byte",
        type=int_from_str,
        default=0xFF,
        help="Byte value used to pad unused ROM space (default: 0xFF)",
    )
    parser.add_argument(
        "--background-color",
        type=int_from_str,
        default=0,
        help="SCREEN2 background color value (0-15, default: 0)",
    )
    parser.add_argument(
        "--border-color",
        type=int_from_str,
        default=0,
        help="VDP border color value (0-15, default: 0)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sc2_path = args.input
    if not sc2_path.is_file():
        raise SystemExit(f"Input file not found: {sc2_path}")

    sc2_bytes = sanitize_sc2_data(sc2_path.read_bytes())
    rom_bytes = build_rom(
        sc2_bytes, args.fill_byte, args.background_color, args.border_color
    )

    output_path = args.output
    if output_path is None:
        output_path = sc2_path.with_suffix(".rom")

    output_path.write_bytes(rom_bytes)
    print(f"Wrote {len(rom_bytes)} bytes to {output_path}")


if __name__ == "__main__":
    main()
