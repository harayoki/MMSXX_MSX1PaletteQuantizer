# CLI Guide (English)

The CLI tool `msx1pq_cli` converts PNG images into MSX1/2-style graphics that follow the TMS9918 display rules. Use it for batch processing or automation without opening After Effects or Premiere Pro.

## Build

Build the Visual Studio project with `msbuild`:

```bash
msbuild platform\\Win\\MSX1PaletteQuantizer_CLI.vcxproj /p:Configuration=Release /p:Platform=x64
```

The compiled binary will be placed at `platform\\Win\\x64\\msx1pq_cli.exe`.

## Usage

```bash
./bin/msx1pq_cli --input <file|dir> --output <dir> [options]
```

- Accepts a single PNG file or an entire directory of PNG files.
- Creates the output directory if it does not exist.
- Asks before overwriting existing files unless `--force` is provided.

### Key options (mirrors the `--help` output)

| Option | Description |
| --- | --- |
| `--input, -i <file\|dir>` | Input PNG file or directory to process. |
| `--output, -o <dir>` | Destination directory for converted PNG files. |
| `--out-prefix <string>` | Prefix added to every output file name. |
| `--out-suffix <string>` | Suffix inserted before the output file extension. |
| `--out-sc5` | Save as SCREEN5 `.sc5` binary instead of PNG. |
| `--out-sc2` | Save as SCREEN2 `.sc2` binary instead of PNG (requires `--8dot` set to anything other than `none`). |
| `--color-system <msx1\|msx2>` | Choose MSX1 (15 colors) or MSX2 palette. Default: `msx1`. |
| `--dither` / `--no-dither` | Enable or disable dithering. Default: enabled. |
| `--dark-dither` / `--no-dark-dither` | Use dedicated dark-area patterns or skip them. Default: enabled. |
| `--no-preprocess` | Skip all preprocessing tweaks (posterize, saturation, gamma, highlight, hue, LUT). |
| `--8dot <none\|fast\|basic\|best\|best-attr\|best-trans>` | Pick the 8-dot/2-color algorithm. Default: `best`. |
| `--distance <rgb|hsb>` | Color distance mode for palette selection. Default: `hsb`. |
| `--weight-h`, `--weight-s`, `--weight-b` | Weights (0–1) for hue, saturation, and brightness when `hsb` distance is selected. |
| `--pre-posterize <0-255>` | Posterize before processing (default: `16`; skipped if `<=1`). |
| `--pre-sat <0-10>` | Boost saturation before quantizing. Default: `1.0`. |
| `--pre-gamma <0-10>` | Darken midtones before quantizing. Default: `1.0`. |
| `--pre-highlight <0-10>` | Brighten highlights before quantizing. Default: `1.0`. |
| `--pre-hue <-180-180>` | Rotate hue before quantizing. Default: `0.0`. |
| `--pre-lut <file>` | Apply an RGB LUT (256-row table) or a `.cube` 3D LUT before processing. |
| `--palette92` | Replace colors with the nearest from the 92-color palette (dithering disabled). |
| `-f, --force` | Overwrite outputs without confirmation. |
| `-v, --version` | Show version information. |
| `-h, --help` | Show help in the detected locale (Japanese if available). |
| `--help-ja`, `--help-en` | Force Japanese or English help text. |

Notes:
- `--out-sc2` and `--out-sc5` cannot be used together. When either is specified the output extension changes to `.sc2` or `.sc5` respectively.
- SCREEN2 export needs the 8-dot/2-color processing enabled (any `--8dot` value other than `none`).

### Examples

Process one file into `dist/`:

```bash
./bin/msx1pq_cli -i input.png -o dist
```

Batch convert all PNGs in `assets/frames` with MSX2 colors and no dithering:

```bash
./bin/msx1pq_cli --input assets/frames --output dist --color-system msx2 --no-dither --force
```

Apply stronger saturation and the "best-attr" 8-dot algorithm:

```bash
./bin/msx1pq_cli -i shot.png -o dist --pre-sat 1.4 --8dot best-attr
```

Write a SCREEN2 binary for MSX emulators:

```bash
./bin/msx1pq_cli -i input.png -o dist --out-sc2
```
