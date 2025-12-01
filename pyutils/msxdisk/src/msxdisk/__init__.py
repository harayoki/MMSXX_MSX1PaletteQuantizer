"""MSX disk image utilities package."""
from pathlib import Path
from typing import Iterable, Sequence

from .builder import DiskBuilder, DiskOverflowError, build_disk_image

__all__ = [
    "DiskBuilder",
    "DiskOverflowError",
    "build_disk_image",
]


def create_disk_image(
    output_path: str | Path,
    inputs: Sequence[str | Path] | None = None,
    ignore_extensions: Iterable[str] | None = None,
    allow_partial: bool = False,
) -> Path:
    """Create a 2DD 720 KiB MSX disk image from provided files.

    Args:
        output_path: Destination path for the disk image.
        inputs: Optional iterable of file or directory paths to include.
        ignore_extensions: File extensions (including the leading dot) to skip.
        allow_partial: If True, fill the disk with as much data as possible and
            emit warnings when files are truncated or skipped. If False,
            exceeding the disk capacity raises an error.
    """

    output = Path(output_path)
    resolved_inputs = [Path(p) for p in (inputs or [])]
    return build_disk_image(
        output=output,
        inputs=resolved_inputs,
        ignore_extensions=ignore_extensions,
        allow_partial=allow_partial,
    )
