"""Command line entry point for msxdisk tools."""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from msxdisk import DiskOverflowError, create_disk_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MSX disk image utilities")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help="Path to write the generated disk image",
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        nargs="+",
        default=[],
        type=Path,
        help="Files or directories to place into the disk image (can be provided multiple times)",
    )
    parser.add_argument(
        "--format-input",
        action="append",
        nargs=3,
        metavar=("TEMPLATE", "DISK_NAME", "VARS_JSON"),
        default=[],
        help=(
            "Template path, target file name inside the disk image, and JSON string "
            "with variables to expand"
        ),
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


def render_template(template_path: Path, variables_json: str) -> str:
    try:
        variables = json.loads(variables_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for --format-input: {exc}") from exc

    if not isinstance(variables, dict):
        raise SystemExit("Variables for --format-input must be a JSON object")

    template_text = template_path.read_text()
    try:
        return template_text.format(**variables)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Failed to render template {template_path}: {exc}") from exc


def main() -> None:
    args = parse_args()
    input_paths = [path for group in args.input for path in group]

    with TemporaryDirectory() as temp_dir:
        formatted_inputs: list[Path] = []
        for template_path, disk_name, variables_json in args.format_input:
            rendered = render_template(Path(template_path), variables_json)
            output_path = Path(temp_dir) / disk_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered)
            formatted_inputs.append(output_path)

        all_inputs = input_paths + formatted_inputs

        try:
            with warnings.catch_warnings(record=True) as caught:
                create_disk_image(
                    output_path=args.output,
                    inputs=all_inputs,
                    ignore_extensions=args.ignore_ext,
                    allow_partial=args.allow_partial,
                )
                for warning in caught:
                    print(f"Warning: {warning.message}")
        except DiskOverflowError as exc:
            raise SystemExit(f"Failed to create disk image: {exc}") from exc


if __name__ == "__main__":
    main()
