from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.utils import MemAddrAllocator


def test_add_with_various_initial_values() -> None:
    allocator = MemAddrAllocator(0x8000)

    allocator.add("BUFFER", 4, initial_value=[0x01, 0x02, 0x00, 0x00])
    allocator.add("CHARS", 3, initial_value=["A", "B", "C"])
    allocator.add("WORD", 2, initial_value=0x1234)
    allocator.add("BYTES", initial_value=b"\xAA\xBB")

    assert allocator.get("BUFFER") == 0x8000
    assert allocator.get("CHARS") == 0x8004
    assert allocator.get("WORD") == 0x8007
    assert allocator.get("BYTES") == 0x8009
    assert allocator.total_size == 11

    expected = bytes(
        [0x01, 0x02, 0x00, 0x00]  # BUFFER (4 bytes)
        + list(b"ABC")  # CHARS
        + [0x34, 0x12]  # WORD (little endian)
        + [0xAA, 0xBB]  # BYTES
    )
    assert allocator.initial_bytes[: allocator.total_size] == expected


def test_write_initial_values_fills_target_buffer() -> None:
    allocator = MemAddrAllocator(0xC000)

    allocator.add("WORD", 2, initial_value=0xBEEF)
    allocator.add("BUFFER", 3)
    allocator.add("BYTE", 1, initial_value=b"\x7F")

    target = bytearray(allocator.total_size)
    allocator.write_initial_values(target)

    assert target == bytes([0xEF, 0xBE, 0x00, 0x00, 0x00, 0x7F])


def test_add_rejects_invalid_16bit_size() -> None:
    allocator = MemAddrAllocator(0x1000)

    # size=1 に 16bit を設定しようとするとエラー
    with pytest.raises(ValueError):
        allocator.add("INVALID", 1, initial_value=0x1234)


def test_add_requires_length_information() -> None:
    allocator = MemAddrAllocator(0x4000)

    with pytest.raises(ValueError):
        allocator.add("NO_LENGTH")


def test_add_raises_on_size_value_mismatch() -> None:
    allocator = MemAddrAllocator(0x5000)

    with pytest.raises(ValueError):
        allocator.add("TOO_SHORT", 3, initial_value=[0x01, 0x02])


def test_add_allows_size_inference_from_initial_value() -> None:
    allocator = MemAddrAllocator(0x6000)

    addr = allocator.add("AUTO", initial_value=[0x10, 0x20, 0x30])

    assert addr == 0x6000
    assert allocator.total_size == 3
    assert allocator.initial_bytes[: allocator.total_size] == bytes([0x10, 0x20, 0x30])


def test_add_fills_zeros_when_no_initial_value() -> None:
    allocator = MemAddrAllocator(0x7000)

    allocator.add("ZEROES", 4)

    assert allocator.initial_bytes[: allocator.total_size] == bytes([0x00] * 4)

