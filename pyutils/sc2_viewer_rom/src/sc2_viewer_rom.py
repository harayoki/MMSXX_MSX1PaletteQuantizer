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
SC2_HEADER_SIZE = 7
ROM_SIZE = BANK_SIZE * 2
HEADER_SIZE = 16
INIT_ADDR = 0x4010
SCREEN = 0x8

BOOT_CODE_ARR = []
# Z80 bootstrap code placed at 0x4010 (bank 0 start is treated as 0x4000).
# Assembly (origin 0x4010):
#   F3           di                  ; 割り込みOFF
#   31 80 F3     ld   sp,0f380h
#   3E 02        ld   a,2            ; SCREEN2
#   CD 5F 00     call 005Fh          ; CHGMOD BIOS
BOOT_CODE_ARR += [
    0xF3,

    0x31,
    0x80,
    0xF3,

    0x3E,
    SCREEN,

    0xCD,
    0x5F,
    0x00,
]

#   3E 01        ld a,1
#   32 00 70     ld (7000h),a
BOOT_CODE_ARR += [
    0x3E,
    0x01,

    0x32,
    0x00,
    0x70,
]

#   21 00 80     ld   hl,8000h       ; source in bank1
#   11 00 00     ld   de,0000h       ; VRAM dest
#   01 00 40     ld   bc,4000h       ; 16KB length
#   CD 5C 00     call 005Ch          ; LDIRVM
BOOT_CODE_ARR += [
    0x21,
    0x00,
    0x80,  # source in bank1

    0x11,
    0x00,
    0x00,

    0x01,
    0x00,
    0x40,  # 16KB length

    0xCD,
    0x5C,
    0x00,
]

#   18 FE        jr   $              ; infinite loop 2バイト前に戻る
BOOT_CODE_ARR += [
    0x18,
    0xFE,
]

BOOT_CODE = bytes(BOOT_CODE_ARR)

# 参考 BIOSコール https://msxjpn.jimdofree.com/bios-%E3%82%B3%E3%83%BC%E3%83%AB/
# 参考 メガロム初期化 https://qiita.com/kazuki-ryo/items/29666d7819fc8a5335aa

def build_header() -> bytes:
    """Build the 16-byte MSX cartridge header for an INIT at INIT_ADDR."""
    init_le = INIT_ADDR.to_bytes(2, "little")
    return bytes([0x41, 0x42]) + init_le + init_le + (b"\x00" * (HEADER_SIZE - 6))


def build_bank0() -> bytes:
    """Construct bank0 with header, bootstrap, and 0xFF padding."""
    header = build_header()
    payload = header + BOOT_CODE
    if len(payload) > BANK_SIZE:
        print("Boot code exceeds bank size", file=sys.stderr)
        sys.exit(1)
    padding = bytes([0xff]) * (BANK_SIZE - len(payload))
    return payload + padding


def build_rom(sc2_data: bytes) -> bytes:
    """Build the 32KB ASCII16 ROM image from SC2 data."""
    if len(sc2_data) != BANK_SIZE:
        raise ValueError("SC2 payload must be exactly 16KB")
    bank0 = build_bank0()
    bank1 = sc2_data
    # bank1 = bytes([0x80]) * BANK_SIZE  # for testing
    rom = bank0 + bank1
    if len(rom) != ROM_SIZE:
        raise ValueError("Generated ROM size mismatch")
    return rom


def validate_sc2(path: Path) -> bytes:
    """Read and validate the SC2 file length."""
    if not path.exists():
        print(f"Input file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = path.read_bytes()
    if len(data) == BANK_SIZE + SC2_HEADER_SIZE:
        data = data[SC2_HEADER_SIZE:]
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
    # for webMSX compatibility, append [ASCII16] to output filename
    # https://github.com/ppeccin/webmsx?tab=readme-ov-file#media-loading
    args.output = args.output.parent / (args.output.stem + "[ASCII16].rom")
    # args.output = args.output.parent / (args.output.stem + "[Normal].rom")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom_image)
    print(f"Wrote ROM image to: {args.output}")


if __name__ == "__main__":
    main()
