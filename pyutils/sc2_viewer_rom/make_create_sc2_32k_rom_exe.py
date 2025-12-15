"""Utilities to bundle create_sc2_32k_rom into a single-file executable with Nuitka."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_executable(output_dir: Path) -> None:
    """Compile ``create_sc2_32k_rom.py`` into a one-file executable via Nuitka."""
    script_dir = Path(__file__).resolve().parent
    target = script_dir / "src" / "create_sc2_32k_rom.py"
    if not target.exists():
        raise FileNotFoundError(f"Cannot find source script: {target}")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--remove-output",
        "--assume-yes-for-downloads",
        f"--output-dir={output_dir}",
        str(target),
    ]

    print("Running Nuitka:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a standalone executable for create_sc2_32k_rom using Nuitka",
    )
    default_output = Path(__file__).resolve().parent / "dist"
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Directory for the generated executable (default: {default_output})",
    )
    args = parser.parse_args()

    build_executable(args.output_dir)


if __name__ == "__main__":
    main()
