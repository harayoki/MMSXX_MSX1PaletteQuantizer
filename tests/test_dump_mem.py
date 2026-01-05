import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, dump_mem, register_dump_target


def test_dump_mem_full_length_default_padding():
    b = Block()
    register_dump_target("mem4", 0x3000, 4)

    dump_mem(b, "mem4", 0x2222)

    assert b.finalize() == bytes(
        [
            0xF5,  # PUSH AF
            0xC5,  # PUSH BC
            0xD5,  # PUSH DE
            0xE5,  # PUSH HL
            0x21,
            0x22,
            0x22,  # LD HL,0x2222
            0x11,
            0x00,
            0x30,  # LD DE,0x3000
            0x01,
            0x04,
            0x00,  # LD BC,4
            0xED,
            0xB0,  # LDIR
            0xE1,  # POP HL
            0xD1,  # POP DE
            0xC1,  # POP BC
            0xF1,  # POP AF
        ]
    )


def test_dump_mem_partial_with_zero_padding():
    b = Block()
    register_dump_target("mem6", 0x4000, 6)

    dump_mem(b, "mem6", 0x1000, length=2)

    assert b.finalize() == bytes(
        [
            0xF5,  # PUSH AF
            0xC5,  # PUSH BC
            0xD5,  # PUSH DE
            0xE5,  # PUSH HL
            0x21,
            0x00,
            0x10,  # LD HL,0x1000
            0x11,
            0x00,
            0x40,  # LD DE,0x4000
            0x01,
            0x02,
            0x00,  # LD BC,2
            0xED,
            0xB0,  # LDIR
            0xAF,  # XOR A -> 0 padding
            0x12,
            0x13,
            0x12,
            0x13,
            0x12,
            0x13,
            0x12,
            0x13,  # pad remaining 4 bytes
            0xE1,  # POP HL
            0xD1,  # POP DE
            0xC1,  # POP BC
            0xF1,  # POP AF
        ]
    )


def test_dump_mem_partial_with_custom_padding():
    b = Block()
    register_dump_target("mem5", 0x4100, 5)

    dump_mem(b, "mem5", 0x2000, length=3, padding_byte=0xFF)

    assert b.finalize() == bytes(
        [
            0xF5,  # PUSH AF
            0xC5,  # PUSH BC
            0xD5,  # PUSH DE
            0xE5,  # PUSH HL
            0x21,
            0x00,
            0x20,  # LD HL,0x2000
            0x11,
            0x00,
            0x41,  # LD DE,0x4100
            0x01,
            0x03,
            0x00,  # LD BC,3
            0xED,
            0xB0,  # LDIR
            0x3E,
            0xFF,  # LD A,0xFF for padding
            0x12,
            0x13,
            0x12,
            0x13,  # pad remaining 2 bytes
            0xE1,  # POP HL
            0xD1,  # POP DE
            0xC1,  # POP BC
            0xF1,  # POP AF
        ]
    )


def test_dump_mem_rejects_over_capacity():
    b = Block()
    register_dump_target("mem3", 0x4200, 3)

    with pytest.raises(ValueError):
        dump_mem(b, "mem3", 0x5000, length=4)


def test_dump_mem_rejects_invalid_padding_byte():
    b = Block()
    register_dump_target("mem2", 0x4300, 2)

    with pytest.raises(ValueError):
        dump_mem(b, "mem2", 0x6000, padding_byte=0x1FF)

