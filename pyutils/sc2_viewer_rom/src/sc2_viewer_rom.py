"""Convert a 16KB SCREEN2 dump into a simple MSX1 ASCII16 ROM image.

This script packs a provided .sc2 VRAM dump into bank 1 of an ASCII16
megaROM and places a small Z80 bootstrap in bank 0 that switches to SCREEN2,
maps in bank 1, copies the VRAM data, and loops forever showing the image.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BANK_SIZE = 0x4000
ROM_SIZE = BANK_SIZE * 2
HEADER_SIZE = 16
INIT_ADDR = 0x4010

# Z80 bootstrap code placed at 0x4010 (bank 0 start is treated as 0x4000).
#
# Assembly (origin 0x4010):
#   3E 02        ld   a,2            ; SCREEN2
#   CD 5F 00     call 005Fh          ; CHGMOD BIOS
#   3E 01        ld   a,1            ; select bank 1
#   32 00 60     ld   (6000h),a      ; ASCII16 bank switch
#   32 00 70     ld   (7000h),a
#   21 00 40     ld   hl,4000h       ; source in bank1
#   11 00 00     ld   de,0000h       ; VRAM dest
#   01 00 40     ld   bc,4000h       ; 16KB length
#   CD 5C 00     call 005Ch          ; LDIRVM
#   18 FE        jr   $              ; infinite loop
BOOT_CODE = bytes(
    [
        0x3E,
        0x02,
        0xCD,
        0x5F,
        0x00,
        0x3E,
        0x01,
        0x32,
        0x00,
        0x60,
        0x32,
        0x00,
        0x70,
        0x21,
        0x00,
        0x40,
        0x11,
        0x00,
        0x00,
        0x01,
        0x00,
        0x40,
        0xCD,
        0x5C,
        0x00,
        0x18,
        0xFE,
    ]
)


def build_header() -> bytes:
    """Build the 16-byte MSX cartridge header for an INIT at INIT_ADDR."""
    init_le = INIT_ADDR.to_bytes(2, "little")
    return bytes([0x41, 0x42]) + init_le + (b"\x00" * (HEADER_SIZE - 4))


def build_bank0() -> bytes:
    """Construct bank0 with header, bootstrap, and 0xFF padding."""
    header = build_header()
    payload = header + BOOT_CODE
    if len(payload) > BANK_SIZE:
        print("Boot code exceeds bank size", file=sys.stderr)
        sys.exit(1)
    padding = bytes([0xFF]) * (BANK_SIZE - len(payload))
    return payload + padding


def build_rom(sc2_data: bytes) -> bytes:
    """Build the 32KB ROM image from SC2 data."""
    bank0 = build_bank0()
    bank1 = sc2_data
    return bank0 + bank1


def validate_sc2(path: Path) -> bytes:
    """Read and validate the SC2 file length."""
    if not path.exists():
        print(f"Input file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = path.read_bytes()
    if len(data) != BANK_SIZE:
        print(
            f"Invalid SC2 size: {len(data)} bytes (expected {BANK_SIZE})",
            file=sys.stderr,
        )
        sys.exit(1)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a 16KB SCREEN2 dump into an MSX1 ASCII16 ROM"
    )
    parser.add_argument("input", type=Path, help="Input .sc2 file (16KB)")
    parser.add_argument("output", type=Path, help="Output ROM path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sc2_data = validate_sc2(args.input)
    rom_image = build_rom(sc2_data)
    args.output.write_bytes(rom_image)

    # Basic verification example for manual testing:
    #   dummy = bytes([i % 256 for i in range(BANK_SIZE)])
    #   Path("dummy.sc2").write_bytes(dummy)
    #   Path("dummy.rom").write_bytes(build_rom(dummy))
    #   rom = Path("dummy.rom").read_bytes()
    #   assert len(rom) == ROM_SIZE
    #   assert rom[:HEADER_SIZE] == build_header()  # header present
    #   assert set(rom[len(build_header()) + len(BOOT_CODE) : BANK_SIZE]) == {0xFF}
    #   assert rom[BANK_SIZE:] == dummy


if __name__ == "__main__":
    main()
