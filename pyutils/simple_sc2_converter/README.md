# Simple SC2 Converter

A small utility to convert PNG images into MSX Screen 2 (`.sc2`) or Screen 4 (`.sc4`) binaries.

* Accepts PNG files or folders (non-recursive) containing PNGs.
* Ensures inputs are `256x192` pixels by default and supports optional resizing, cropping, or padding.
* Uses the MSX1 basic palette by default, with switches for the MSX2 palette and per-color overrides.
* Outputs 16 KiB SC2/SC4 data with a 7-byte BSAVE header by default (can be disabled).
* Can be used as a CLI tool or imported as a Python module that returns the binary data for a single file.

## Installation

From the repository root:

```bash
pip install ./pyutils/simple_sc2_converter
```

PyPI packages are not published for this tool; install from the repository source.

## CLI usage

```bash
python -m simple_sc2_converter -o output_dir input.png [more_inputs_or_folders]
```

Key options:

* `-o`, `--output-dir`: Required output directory.
* `--prefix`, `--suffix`: Customize the output filename.
* `--format {sc2,sc4}`: Choose Screen 2 (`.sc2`) or Screen 4 (`.sc4`) output.
* `--no-header`: Write raw 16 KiB VRAM data without the BSAVE header.
* `--force`, `-f`: Overwrite existing files without prompting.
* `--oversize {error,shrink,crop}`: How to handle inputs larger than `256x192` (default: `error`).
* `--undersize {error,pad}`: How to handle inputs smaller than `256x192` (default: `error`).
* `--background COLOR`: Background fill color for padding (e.g., `0,0,0` or `#000000`).
* `--msx2-palette`: Use the MSX2 basic palette instead of MSX1 for conversion calculations.
* `--paletteN R G B`: Override palette entry N (1–15). Example: `--palette2 62 184 73`.

Use `--help` to see the full list, including the palette values shown in the help text.

## Module usage

```python
from simple_sc2_converter import ConvertOptions, convert_png_to_sc2, convert_png_to_sc4

opts = ConvertOptions()
opts.oversize_mode = "shrink"
sc2_bytes = convert_png_to_sc2("input.png", options=opts)

sc4_bytes = convert_png_to_sc4("input.png", options=opts)

with open("output.sc2", "wb") as f:
    f.write(sc2_bytes)
```

