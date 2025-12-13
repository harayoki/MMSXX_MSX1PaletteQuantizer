"""Minimal FAT12 writer utilities used for MSX disk images.

This module is intentionally self contained to avoid external dependencies
while still exposing a small, pyfatfs-inspired surface that covers our use
case: adding files to a pre-formatted FAT12 720 KiB image.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


EOC = 0xFFF
BPS_720K = 512
TOTAL_SECTORS_720K = 1440


@dataclass
class BootParams:
    """Boot sector parameters used to navigate the FAT image."""

    bytes_per_sector: int
    sectors_per_cluster: int
    reserved_sectors: int
    fat_count: int
    root_entries: int
    sectors_per_fat: int
    total_sectors: int
    media_descriptor: int

    @property
    def root_dir_sectors(self) -> int:
        return (self.root_entries * 32 + self.bytes_per_sector - 1) // self.bytes_per_sector

    @property
    def data_start_sector(self) -> int:
        return self.reserved_sectors + self.fat_count * self.sectors_per_fat + self.root_dir_sectors

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    @property
    def cluster_count(self) -> int:
        data_sectors = self.total_sectors - self.data_start_sector
        return data_sectors // self.sectors_per_cluster


class Fat12Image:
    """Very small FAT12 helper that mirrors the parts of pyfatfs we need."""

    def __init__(self, image: bytearray):
        self.image = image
        self.params = self._parse_boot_sector()
        self.fat = self._load_primary_fat()

    def _parse_boot_sector(self) -> BootParams:
        bs = self.image
        bytes_per_sector = int.from_bytes(bs[11:13], "little")
        sectors_per_cluster = bs[13]
        reserved = int.from_bytes(bs[14:16], "little")
        fat_count = bs[16]
        root_entries = int.from_bytes(bs[17:19], "little")
        total_sectors = int.from_bytes(bs[19:21], "little")
        sectors_per_fat = int.from_bytes(bs[22:24], "little")
        media_descriptor = bs[21]
        return BootParams(
            bytes_per_sector=bytes_per_sector,
            sectors_per_cluster=sectors_per_cluster,
            reserved_sectors=reserved,
            fat_count=fat_count,
            root_entries=root_entries,
            sectors_per_fat=sectors_per_fat,
            total_sectors=total_sectors,
            media_descriptor=media_descriptor,
        )

    def _load_primary_fat(self) -> bytearray:
        start = self.params.bytes_per_sector * self.params.reserved_sectors
        end = start + self.params.sectors_per_fat * self.params.bytes_per_sector
        return bytearray(self.image[start:end])

    def _fat_entry_offset(self, cluster: int) -> int:
        return (cluster * 3) // 2

    def get_fat_entry(self, cluster: int) -> int:
        offset = self._fat_entry_offset(cluster)
        if cluster % 2 == 0:
            value = self.fat[offset] | ((self.fat[offset + 1] & 0x0F) << 8)
        else:
            value = ((self.fat[offset] & 0xF0) >> 4) | (self.fat[offset + 1] << 4)
        return value

    def set_fat_entry(self, cluster: int, value: int) -> None:
        offset = self._fat_entry_offset(cluster)
        if cluster % 2 == 0:
            self.fat[offset] = value & 0xFF
            self.fat[offset + 1] = (self.fat[offset + 1] & 0xF0) | ((value >> 8) & 0x0F)
        else:
            self.fat[offset] = (self.fat[offset] & 0x0F) | ((value << 4) & 0xF0)
            self.fat[offset + 1] = (value >> 4) & 0xFF

    def _sync_fats(self) -> None:
        fat_start = self.params.bytes_per_sector * self.params.reserved_sectors
        fat_bytes = bytes(self.fat)
        for idx in range(self.params.fat_count):
            start = fat_start + idx * self.params.sectors_per_fat * self.params.bytes_per_sector
            end = start + len(self.fat)
            self.image[start:end] = fat_bytes

    def free_clusters(self) -> Iterator[int]:
        for cluster in range(2, self.params.cluster_count + 2):
            if self.get_fat_entry(cluster) == 0:
                yield cluster

    def allocate_chain(self, cluster_count: int) -> List[int]:
        chain = []
        for cluster in self.free_clusters():
            chain.append(cluster)
            if len(chain) >= cluster_count:
                break
        if len(chain) < cluster_count:
            return []
        for current, nxt in zip(chain, chain[1:]):
            self.set_fat_entry(current, nxt)
        if chain:
            self.set_fat_entry(chain[-1], EOC)
        return chain

    def write_cluster_chain(self, chain: Sequence[int], data: bytes) -> None:
        cluster_size = self.params.cluster_size
        for idx, cluster in enumerate(chain):
            start_sector = self.params.data_start_sector + (cluster - 2) * self.params.sectors_per_cluster
            start = start_sector * self.params.bytes_per_sector
            end = start + cluster_size
            chunk = data[idx * cluster_size : (idx + 1) * cluster_size]
            padded = chunk.ljust(cluster_size, b"\x00")
            self.image[start:end] = padded

    def _root_dir_offset(self) -> int:
        return (
            self.params.bytes_per_sector
            * (
                self.params.reserved_sectors
                + self.params.fat_count * self.params.sectors_per_fat
            )
        )

    def write_root_entry(self, slot: int, name: bytes, ext: bytes, start_cluster: int, size: int) -> None:
        entry = bytearray(32)
        entry[0:8] = name.ljust(8, b" ")[:8]
        entry[8:11] = ext.ljust(3, b" ")[:3]
        entry[11] = 0x20  # archive attribute
        entry[26:28] = start_cluster.to_bytes(2, "little")
        entry[28:32] = size.to_bytes(4, "little")
        root_start = self._root_dir_offset()
        pos = root_start + slot * 32
        self.image[pos : pos + 32] = entry

    def available_root_slots(self) -> Iterator[int]:
        root_start = self._root_dir_offset()
        for slot in range(self.params.root_entries):
            offset = root_start + slot * 32
            first_byte = self.image[offset]
            if first_byte in (0x00, 0xE5):
                yield slot

    def flush(self) -> None:
        self._sync_fats()


def create_blank_2dd_image() -> bytes:
    """Create a blank FAT12 2DD (720 KiB) disk image in memory.

    The layout mirrors a standard MSX/DOS 720 KiB disk:
    * 512 bytes per sector
    * 2 sectors per cluster
    * 1 reserved sector
    * 2 FATs, 3 sectors each
    * 112 root directory entries
    * 1,440 total sectors (720 KiB)
    """

    image = bytearray(BPS_720K * TOTAL_SECTORS_720K)
    # Boot sector
    image[0:3] = b"\xEB\x3C\x90"
    image[3:11] = b"MSXDOS  "
    image[11:13] = (BPS_720K).to_bytes(2, "little")
    image[13] = 2  # sectors per cluster
    image[14:16] = (1).to_bytes(2, "little")
    image[16] = 2  # FAT count
    image[17:19] = (112).to_bytes(2, "little")
    image[19:21] = (TOTAL_SECTORS_720K).to_bytes(2, "little")
    image[21] = 0xF9  # media descriptor for 720K
    image[22:24] = (3).to_bytes(2, "little")  # sectors per FAT
    image[24:26] = (9).to_bytes(2, "little")  # sectors per track
    image[26:28] = (2).to_bytes(2, "little")  # number of heads
    image[28:36] = b"\x00" * 8  # hidden sectors + large total sectors
    image[36] = 0x00  # drive number
    image[38] = 0x29  # extended boot signature
    image[39:43] = (0x12345678).to_bytes(4, "little")  # volume serial
    image[43:54] = b"MSXDOS DISK"
    image[54:62] = b"FAT12   "
    image[510:512] = b"\x55\xAA"

    # Initialize FATs
    params = BootParams(
        bytes_per_sector=BPS_720K,
        sectors_per_cluster=2,
        reserved_sectors=1,
        fat_count=2,
        root_entries=112,
        sectors_per_fat=3,
        total_sectors=TOTAL_SECTORS_720K,
        media_descriptor=0xF9,
    )
    fat_start = params.bytes_per_sector * params.reserved_sectors
    fat_size = params.sectors_per_fat * params.bytes_per_sector
    fat_template = bytearray(fat_size)
    fat_template[0:3] = bytes([params.media_descriptor, 0xFF, 0xFF])

    for idx in range(params.fat_count):
        start = fat_start + idx * fat_size
        image[start : start + fat_size] = fat_template

    # Root directory and data area are already zeroed by default.
    return bytes(image)


def split_83_name(path: Path) -> tuple[bytes, bytes]:
    name = path.stem.upper()
    ext = path.suffix[1:].upper()
    return name.encode("ascii", "ignore"), ext.encode("ascii", "ignore")


def iter_files(paths: Sequence[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                yield child
        elif path.is_file():
            yield path


def filter_extensions(files: Iterable[Path], ignored_exts: set[str]) -> Iterator[Path]:
    for file in files:
        if file.suffix.lower() in ignored_exts:
            continue
        yield file
