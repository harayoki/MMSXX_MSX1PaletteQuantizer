# Simple SC2 Converter (WIP)

A small utility to convert PNG images into MSX Screen 2 (`.sc2`) binaries or palette-constrained PNG previews.
The C++ version is planned to be made available as a Python module.

The dithering and pre-MSX1 image processing were reimplemented in Python based on the C++ version, but the Python
implementation is slower and not planned to receive further updates. Use the C++ CLI for general-purpose conversion;
this Python version mainly exists so other Python utilities can turn already-processed PNGs into SC2 data using simple
RGB-distance mapping.

The converter applies a lightweight line-based dithering step before the 8-dot two-color reduction, favoring palette
pairs that mix cleanly and avoiding harsh complementary blends. Dithering can be disabled with `--no-dither` if you
prefer straight nearest-color mapping. For more advanced tuning, use the parent MMSXX_MSX1PaletteQuantizer (CLI / for
After Effects / for Photoshop:WIP) or any other tools.

* Accepts PNG files or folders (non-recursive) containing PNGs.
* Ensures inputs are `256x192` pixels by default and supports optional resizing, cropping, or padding.
* Uses the MSX1 basic palette by default, with switches for the MSX2 palette and per-color overrides.
* Outputs 16 KiB SC2 data with a 7-byte BSAVE header by default (can be disabled).
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
* `--format {png,sc2}`: Choose palette-constrained PNG or Screen 2 (`.sc2`) output.
* `--no-header`: Write raw 16 KiB VRAM data without the BSAVE header.
* `--force`, `-f`: Overwrite existing files without prompting.
* `--oversize {error,shrink,crop}`: How to handle inputs larger than `256x192` (default: `error`).
* `--undersize {error,pad}`: How to handle inputs smaller than `256x192` (default: `error`).
* `--background COLOR`: Background fill color for padding (e.g., `0,0,0` or `#000000`).
* `--no-dither`: Disable palette dithering prior to the 8-dot two-color enforcement.
* `--msx2-palette`: Use the MSX2 basic palette instead of MSX1 for conversion calculations.
* `--paletteN R G B`: Override palette entry N (1–15). Example: `--palette2 62 184 73`.
* `--gamma`, `--contrast`, `--hue-shift`: Optional pre-processing applied before the MSX1 mapping to help the palette's tonal response match the source.
* `--posterize-colors`: Posterize the source image before conversion to reduce color jitter or fine-tune how colors adhere to the palette.

Use `--help` to see the full list, including the palette values shown in the help text.

Tip: Adjusting gamma, contrast, or hue *before* MSX1 mapping can better align the source material with the palette's tonal and color response, often yielding more faithful results. Posterization primarily reduces color jitter in the source but can also help fine-tune how tones snap to palette entries.

## Module usage

```python
from simple_sc2_converter import (
    ConvertOptions,
    convert_png_to_msx_png,
    convert_png_to_sc2,
)

opts = ConvertOptions()
opts.oversize_mode = "shrink"
sc2_bytes = convert_png_to_sc2("input.png", options=opts)

preview_png = convert_png_to_msx_png("input.png", options=opts)
preview_png.save("output.png")

with open("output.sc2", "wb") as f:
    f.write(sc2_bytes)
```

---

## Simple SC2 Converter (日本語)

C++版を元にPythonへディザ処理とMSX1変換前の画像処理を移植しましたが、速度はC++より遅いため、通常の変換はC++版のCLIを使用してください。このPython版は、他のPythonユーティリティがディザ処理済みのPNGをSC2形式へ単純なRGB距離で変換する用途を想定しています。
C++版の処理をpythonモジュール化する予定はあります。

* 入力: PNGファイル、またはPNGを含むフォルダー（再帰しない）。
* 既定で画像サイズを `256x192` に揃え、リサイズ・クロップ・パディングに対応。
* 既定はMSX1基本パレット。MSX2パレットへの切り替えや色単位の上書きも可能。
* 出力はBSAVEヘッダー付き16KiBのSC2データ（ヘッダー無しも可）。
* CLIとしてもPythonモジュールとしても利用可能。

### インストール

```bash
pip install ./pyutils/simple_sc2_converter
```

### CLIの使い方

```bash
python -m simple_sc2_converter -o output_dir input.png [more_inputs_or_folders]
```

主なオプション:

* `-o`, `--output-dir`: 出力先ディレクトリ（必須）。
* `--prefix`, `--suffix`: 出力ファイル名のプレフィックス／サフィックス。
* `--format {png,sc2}`: パレット制約付きPNG、またはScreen 2 (`.sc2`) を選択。
* `--no-header`: BSAVEヘッダー無しで16KiBのVRAMデータを書き出す。
* `--force`, `-f`: 既存ファイルを確認なしで上書き。
* `--oversize {error,shrink,crop}`: `256x192` より大きい入力の扱い（既定: `error`）。
* `--undersize {error,pad}`: `256x192` より小さい入力の扱い（既定: `error`）。
* `--background COLOR`: パディング時の背景色（例: `0,0,0` や `#000000`）。
* `--no-dither`: 8ドット2色制約前のディザ処理を無効化。
* `--msx2-palette`: 変換計算にMSX2基本パレットを使用。
* `--paletteN R G B`: パレットの各色を上書き。例: `--palette2 62 184 73`。
* `--gamma`, `--contrast`, `--hue-shift`: MSX1マッピング前の前処理。元画像のトーンをパレットに合わせるために利用。
* `--posterize-colors`: 変換前にポスタライズして色のばらつきを抑制。

`--help` で詳細なオプションとパレット値を確認できます。
