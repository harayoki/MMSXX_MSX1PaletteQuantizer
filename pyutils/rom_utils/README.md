# ROM Utilities

## create_sc2_32k_rom.py

`create_sc2_32k_rom.py` packs a SCREEN2 (`.sc2`) VRAM dump into a 32 KiB MSX ROM
(non-MegaROM). The generated ROM switches to SCREEN2, copies the bundled image to
VRAM, and waits so the picture remains on screen.

The script accepts `.sc2` files that include the optional 7-byte header; the
header is stripped automatically before building the ROM.

### Usage

```bash
python create_sc2_32k_rom.py input.sc2 -o output.rom
```

- The script accepts decimal or hexadecimal values for `--fill-byte` (default
  `0xFF`) to control the padding used in unused ROM space.
- If `-o/--output` is omitted, the ROM is written next to the source image with a
  `.rom` extension.
