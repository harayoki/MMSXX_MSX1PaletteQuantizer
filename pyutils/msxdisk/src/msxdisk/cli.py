"""Command line entry point for msxdisk tools."""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from msxdisk import DiskOverflowError, create_disk_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MSX disk image utilities")
    parser.add_argument(
        "output",
        type=Path,
        help="Path to write the generated disk image",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Files or directories to place into the disk image",
    )
    parser.add_argument(
        "--ignore-ext",
        dest="ignore_ext",
        nargs="*",
        default=[],
        help="File extensions to skip (e.g. .tmp .bak)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Fill until full instead of erroring when capacity is exceeded",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        with warnings.catch_warnings(record=True) as caught:
            create_disk_image(
                output_path=args.output,
                inputs=args.inputs,
                ignore_extensions=args.ignore_ext,
                allow_partial=args.allow_partial,
            )
            for warning in caught:
                print(f"Warning: {warning.message}")
    except DiskOverflowError as exc:
        raise SystemExit(f"Failed to create disk image: {exc}") from exc


if __name__ == "__main__":
    main()
