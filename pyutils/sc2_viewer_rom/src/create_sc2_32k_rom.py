"""Create a 32 KiB MSX ROM that alternates two SCREEN2 images.

This script takes two `.sc2` files (raw SCREEN2 VRAM dumps), trims the sprite
regions, and embeds them into a simple 32 KiB ROM. On boot the ROM switches to
SCREEN2, copies the first image to VRAM, waits for a key press, shows the second
image, and keeps alternating indefinitely on each key press.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

ROM_SIZE = 0x8000  # 32 KiB
ROM_BASE = 0x4000
HEADER_SIGNATURE = b"AB"

IMAGE_LENGTH = 0x3780  # Trimmed SCREEN2 size
VRAM_SIZE = 0x4000  # Full SCREEN2 VRAM dump size (16 KiB)
SC2_HEADER_SIZE = 7  # Optional header seen in some .sc2 files

CHGMOD = 0x005F
CHGCLR = 0x0062
LDIRVM = 0x005C
CHGET = 0x009F
FORCLR = 0xF3E9
BAKCLR = 0xF3EA
BDRCLR = 0xF3EB


def int_from_str(value: str) -> int:
    """Parse an integer that may be expressed in decimal or hex."""

    return int(value, 0)


def sc2_to_trimmed(sc2_bytes: bytes) -> bytes:
    """Trim SCREEN2 data to the preserved regions.

    The returned data is always 0x3780 bytes consisting of:
    - 0000h–1AFFh (pattern generator + name table; sprite attributes removed)
    - 1B80h–37FFh (color table; sprite pattern removed)

    Accepted input sizes:
    - 0x4000 + 7 : skip the first 7-byte header then trim
    - 0x4000     : trim directly
    - 0x3780     : already trimmed
    Any other size raises ValueError.
    """

    length = len(sc2_bytes)

    if length == IMAGE_LENGTH:
        return sc2_bytes

    if length == VRAM_SIZE + SC2_HEADER_SIZE:
        sc2_bytes = sc2_bytes[SC2_HEADER_SIZE:]
        length = len(sc2_bytes)

    if length == VRAM_SIZE:
        return sc2_bytes[:0x1B00] + sc2_bytes[0x1B80:0x3800]

    raise ValueError(
        "Invalid SC2 size: expected 0x4000 (+7 header) or 0x3780 bytes"
    )


def build_loader(
    image0_addr: int,
    image1_addr: int,
    image_length: int,
    background_color: int,
    border_color: int,
) -> bytes:
    """Build the Z80 loader that swaps two SCREEN2 images on key press."""

    if image_length != IMAGE_LENGTH:
        raise ValueError("image_length must be 0x3780 bytes")

    def copy_image_block_org(base_addr: int) -> Tuple[int, ...]:
        """Copy trimmed SCREEN2 data back to its original VRAM layout."""

        return (
            # Pattern generator + name table (0x0000-0x1AFF)
            0x21,
            base_addr & 0xFF,
            (base_addr >> 8) & 0xFF,  # LD HL,image_base
            0x11,
            0x00,
            0x00,  # LD DE,0000h
            0x01,
            0x00,
            0x1B,  # LD BC,1B00h
            0xCD,
            LDIRVM & 0xFF,
            (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM
            # Gap between name table and color table (0x1B80-0x1FFF)
            0x21,
            (base_addr + 0x1B00) & 0xFF,
            ((base_addr + 0x1B00) >> 8) & 0xFF,  # LD HL,image_base+1B00h
            0x11,
            0x80,
            0x1B,  # LD DE,1B80h
            0x01,
            0x80,
            0x04,  # LD BC,0480h
            0xCD,
            LDIRVM & 0xFF,
            (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM
            # Color table (0x2000-0x37FF)
            0x21,
            (base_addr + 0x1F80) & 0xFF,
            ((base_addr + 0x1F80) >> 8) & 0xFF,  # LD HL,image_base+1F80h
            0x11,
            0x00,
            0x20,  # LD DE,2000h
            0x01,
            0x00,
            0x18,  # LD BC,1800h
            0xCD,
            LDIRVM & 0xFF,
            (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM
        )

    def copy_image_block(base_addr: int) -> Tuple[int, ...]:
        """Trimmed SCREEN2 (0x3780) を VRAM に戻す。

        ROM:
          [0x0000〜0x1AFF]   → VRAM 0000〜1AFF (0x1B00)
          [0x1B00〜0x377F]   → VRAM 1B80〜37FF (0x1C80)
        """

        return (
            # 1st block: 0000h–1AFFh (0x1B00 bytes)
            0x21,
            base_addr & 0xFF,
            (base_addr >> 8) & 0xFF,  # LD HL,image_base
            0x11,
            0x00,
            0x00,  # LD DE,0000h
            0x01,
            0x00,
            0x1B,  # LD BC,1B00h
            0xCD,
            LDIRVM & 0xFF,
            (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM

            # 2nd block: 残り全部 (0x1C80 bytes) → VRAM 1B80h–37FFh
            0x21,
            (base_addr + 0x1B00) & 0xFF,
            ((base_addr + 0x1B00) >> 8) & 0xFF,  # LD HL,image_base+1B00h
            0x11,
            0x80,
            0x1B,  # LD DE,1B80h
            0x01,
            0x80,
            0x1C,  # LD BC,1C80h
            0xCD,
            LDIRVM & 0xFF,
            (LDIRVM >> 8) & 0xFF,  # CALL LDIRVM
        )

    code: Iterable[int] = (
        # Set SCREEN2
        0x3E,
        0x02,  # LD A,2
        0xCD,
        CHGMOD & 0xFF,
        (CHGMOD >> 8) & 0xFF,  # CALL CHGMOD
        # Set colors
        0x3E,
        0x0F,  # LD A,0Fh (white)
        0x32,
        FORCLR & 0xFF,
        (FORCLR >> 8) & 0xFF,  # LD (FORCLR),A
        0x3E,
        background_color & 0x0F,  # LD A,background
        0x32,
        BAKCLR & 0xFF,
        (BAKCLR >> 8) & 0xFF,  # LD (BAKCLR),A
        0x3E,
        border_color & 0x0F,  # LD A,border
        0x32,
        BDRCLR & 0xFF,
        (BDRCLR >> 8) & 0xFF,  # LD (BDRCLR),A
        0xCD,
        CHGCLR & 0xFF,
        (CHGCLR >> 8) & 0xFF,  # CALL CHGCLR
        # Show image0 initially
        *copy_image_block(image0_addr),
        # Main loop
        0xCD,
        CHGET & 0xFF,
        (CHGET >> 8) & 0xFF,  # CALL CHGET (wait for key)
        *copy_image_block(image1_addr),
        0xCD,
        CHGET & 0xFF,
        (CHGET >> 8) & 0xFF,  # CALL CHGET (wait for key)
        *copy_image_block(image0_addr),
        0x18,
        0xB0,  # JR -80 (= back to first CHGET)
    )

    return bytes(code)


def build_rom(
    image0_bytes: bytes,
    image1_bytes: bytes,
    fill_byte: int,
    background_color: int,
    border_color: int,
) -> bytes:
    """Build a 32 KiB ROM image that alternates two SCREEN2 images."""

    if not 0 <= fill_byte <= 0xFF:
        raise ValueError("fill_byte must fit in a byte")
    if not 0 <= background_color <= 0x0F:
        raise ValueError("background_color must be between 0 and 15")
    if not 0 <= border_color <= 0x0F:
        raise ValueError("border_color must be between 0 and 15")
    if len(image0_bytes) != IMAGE_LENGTH or len(image1_bytes) != IMAGE_LENGTH:
        raise ValueError("Both images must be exactly 0x3780 bytes after trimming")

    rom = bytearray([fill_byte] * ROM_SIZE)

    entry_address = ROM_BASE + 0x10
    code_offset = entry_address - ROM_BASE

    loader_placeholder = build_loader(0, 0, IMAGE_LENGTH, background_color, border_color)
    image0_offset = (code_offset + len(loader_placeholder) + 0x0F) & ~0x0F
    image1_offset = (image0_offset + IMAGE_LENGTH + 0x0F) & ~0x0F

    image0_addr = ROM_BASE + image0_offset
    image1_addr = ROM_BASE + image1_offset

    loader = build_loader(image0_addr, image1_addr, IMAGE_LENGTH, background_color, border_color)

    end_of_images = image1_offset + IMAGE_LENGTH
    if end_of_images > ROM_SIZE:
        raise ValueError("Images and loader do not fit in 32 KiB ROM")

    # Header
    rom[0:2] = HEADER_SIGNATURE
    rom[2] = entry_address & 0xFF
    rom[3] = (entry_address >> 8) & 0xFF
    rom[4] = 0x00
    rom[5] = 0x00
    rom[6] = 0x00

    # Body
    rom[code_offset : code_offset + len(loader)] = loader
    rom[image0_offset : image0_offset + IMAGE_LENGTH] = image0_bytes
    rom[image1_offset : image1_offset + IMAGE_LENGTH] = image1_bytes

    return bytes(rom)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Embed two SCREEN2 (.sc2) files into a 32 KiB non-MegaROM MSX ROM "
            "that alternates the images on key press."
        )
    )
    parser.add_argument(
        "image0",
        type=Path,
        help="Path to the first .sc2 file (displayed first)",
    )
    parser.add_argument(
        "image1",
        type=Path,
        nargs="?",
        help=(
            "Path to the second .sc2 file (displayed after key press). "
            "If omitted, the first image is reused."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output ROM path (defaults to image0 name with .rom extension)",
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

    if not args.image0.is_file():
        raise SystemExit(f"Input file not found: {args.image0}")

    image1_path = args.image1 or args.image0

    if not image1_path.is_file():
        raise SystemExit(f"Input file not found: {image1_path}")

    image0_bytes = sc2_to_trimmed(args.image0.read_bytes())
    image1_bytes = sc2_to_trimmed(image1_path.read_bytes())

    rom_bytes = build_rom(
        image0_bytes,
        image1_bytes,
        args.fill_byte,
        args.background_color,
        args.border_color,
    )

    output_path = args.output
    if output_path is None:
        output_path = args.image0.with_suffix(".rom")

    output_path.write_bytes(rom_bytes)
    print(f"Wrote {len(rom_bytes)} bytes to {output_path}")


if __name__ == "__main__":
    main()
