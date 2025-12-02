"""Disk image builder that writes files onto a 2DD 720 KiB FAT12 image."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable, Sequence

from .fat12 import (
    Fat12Image,
    create_blank_2dd_image,
    filter_extensions,
    iter_files,
    split_83_name,
)


class DiskOverflowError(RuntimeError):
    """Raised when files do not fit within the target disk image."""


class DiskBuilder:
    """Build an MSX 2DD (720 KiB) disk image from local files."""

    def __init__(self, blank_image: bytes | bytearray):
        self.image = bytearray(blank_image)
        self.fs = Fat12Image(self.image)

    @classmethod
    def from_default_blank(cls) -> "DiskBuilder":
        return cls(create_blank_2dd_image())

    def add_files(
        self,
        inputs: Sequence[Path],
        ignore_extensions: Iterable[str] | None = None,
        allow_partial: bool = False,
    ) -> None:
        ignore_set = {ext.lower() for ext in (ignore_extensions or [])}
        files = list(filter_extensions(iter_files(inputs), ignore_set))
        root_slots = self.fs.available_root_slots()
        used_names: set[bytes] = set()

        for file_path in files:
            name, ext = split_83_name(file_path)
            key = name + b"." + ext
            if key in used_names:
                raise DiskOverflowError(f"Duplicate file name in 8.3 format: {file_path}")
            used_names.add(key)

            data = file_path.read_bytes()
            cluster_size = self.fs.params.cluster_size
            needed_clusters = 0 if not data else (len(data) + cluster_size - 1) // cluster_size
            chain = self.fs.allocate_chain(needed_clusters)

            if needed_clusters and not chain:
                if allow_partial:
                    max_clusters = len(list(self.fs.free_clusters()))
                    max_bytes = max_clusters * cluster_size
                    if max_bytes == 0:
                        warnings.warn(
                            f"{file_path} skipped; disk is full",
                            RuntimeWarning,
                            stacklevel=1,
                        )
                        continue
                    data = data[:max_bytes]
                    needed_clusters = (len(data) + cluster_size - 1) // cluster_size
                    chain = self.fs.allocate_chain(needed_clusters)
                    warnings.warn(
                        f"{file_path} truncated to fit remaining space",
                        RuntimeWarning,
                        stacklevel=1,
                    )
                else:
                    raise DiskOverflowError(
                        f"Not enough space to store {file_path} ({len(data)} bytes)"
                    )

            if chain:
                self.fs.write_cluster_chain(chain, data)
                start_cluster = chain[0]
            else:
                start_cluster = 0

            try:
                slot = next(root_slots)
            except StopIteration as exc:
                raise DiskOverflowError("No free directory entries remain") from exc

            self.fs.write_root_entry(slot, name, ext, start_cluster, len(data))

        self.fs.flush()

    def write(self, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(self.image)


def build_disk_image(
    output: Path,
    inputs: Sequence[Path],
    ignore_extensions: Iterable[str] | None = None,
    allow_partial: bool = False,
) -> Path:
    builder = DiskBuilder.from_default_blank()
    builder.add_files(inputs, ignore_extensions=ignore_extensions, allow_partial=allow_partial)
    builder.write(output)
    return output
