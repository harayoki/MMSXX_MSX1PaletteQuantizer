"""Command line interface for the simple SC2 converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List

from .converter import (
    BASIC_COLORS_MSX1,
    BASIC_COLORS_MSX2,
    ConvertOptions,
    ConversionError,
    convert_png_to_sc2,
    format_palette_text,
    parse_color,
)


def iter_pngs(paths: Iterable[str]) -> List[Path]:
    results: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            if path.suffix.lower() != ".png":
                raise ConversionError(f"Unsupported file type (expected .png): {path}")
            results.append(path)
        elif path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.is_file() and entry.suffix.lower() == ".png":
                    results.append(entry)
        else:
            raise ConversionError(f"Input path does not exist: {path}")
    if not results:
        raise ConversionError("No PNG files were found in the provided inputs.")
    return results


def build_parser() -> argparse.ArgumentParser:
    palette_text = format_palette_text(BASIC_COLORS_MSX1)
    palette_text_msx2 = format_palette_text(BASIC_COLORS_MSX2)

    parser = argparse.ArgumentParser(
        description=(
            "Convert PNG files into MSX Screen 2 (.sc2) binaries.\n"
            "Default palette: MSX1 basic colors. Use --msx2-palette for MSX2 palette.\n"
            f"MSX1 palette: {palette_text}\nMSX2 palette: {palette_text_msx2}"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        help="PNG files or folders containing PNGs (non-recursive)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Destination directory for .sc2 files",
    )
    parser.add_argument("--prefix", default="", help="Optional prefix for output filenames")
    parser.add_argument("--suffix", default="", help="Optional suffix for output filenames")
    parser.add_argument(
        "--oversize",
        choices=["error", "shrink", "crop"],
        default="error",
        help="How to handle images larger than 256x212",
    )
    parser.add_argument(
        "--undersize",
        choices=["error", "pad"],
        default="error",
        help="How to handle images smaller than 256x212",
    )
    parser.add_argument(
        "--background",
        default="0,0,0",
        help="Background color for padding (e.g., 0,0,0 or #000000)",
    )
    parser.add_argument(
        "--msx2-palette",
        action="store_true",
        help="Use MSX2 basic palette instead of MSX1",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Write raw VRAM data without the 7-byte BSAVE header",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )

    for idx in range(1, 16):
        parser.add_argument(
            f"--palette{idx}",
            nargs=3,
            type=int,
            metavar=("R", "G", "B"),
            help=f"Override palette entry {idx} (values 0-255)",
        )

    return parser


def collect_overrides(namespace: argparse.Namespace) -> Dict[int, tuple[int, int, int]]:
    overrides: Dict[int, tuple[int, int, int]] = {}
    for idx in range(1, 16):
        value = getattr(namespace, f"palette{idx}")
        if value is not None:
            r, g, b = value
            for component in value:
                if component < 0 or component > 255:
                    raise ConversionError(f"Palette{idx} values must be between 0 and 255")
            overrides[idx] = (r, g, b)
    return overrides


def ensure_unique_names(paths: List[Path], prefix: str, suffix: str) -> List[str]:
    names: List[str] = []
    seen = set()
    for path in paths:
        name = f"{prefix}{path.stem}{suffix}.sc2"
        if name in seen:
            raise ConversionError(f"Duplicate output name would occur: {name}")
        seen.add(name)
        names.append(name)
    return names


def write_outputs(inputs: List[Path], names: List[str], options: ConvertOptions, output_dir: Path, force: bool) -> None:
    conflicts = []
    for name in names:
        target = output_dir / name
        if target.exists() and not force:
            conflicts.append(str(target))
    if conflicts:
        raise ConversionError(
            "Output files already exist (use --force to overwrite):\n" + "\n".join(conflicts)
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    for src, name in zip(inputs, names):
        data = convert_png_to_sc2(src, options)
        target = output_dir / name
        target.write_bytes(data)
        print(f"wrote {target}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        options = ConvertOptions()
        options.oversize_mode = args.oversize
        options.undersize_mode = args.undersize
        options.background_color = parse_color(args.background)
        options.use_msx2_palette = args.msx2_palette
        options.include_header = not args.no_header
        options.palette_overrides = collect_overrides(args)

        inputs = iter_pngs(args.inputs)
        output_dir = Path(args.output_dir)
        names = ensure_unique_names(inputs, args.prefix, args.suffix)
        write_outputs(inputs, names, options, output_dir, args.force)
        return 0
    except ConversionError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
