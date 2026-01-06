import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, dump_regs, register_dump_target


def test_dump_regs_default_sequence():
    b = Block()
    register_dump_target("dump8", 0x4000, 8)
    dump_regs(b, "dump8")

    assert b.finalize() == bytes(
        [
            0xE5,  # PUSH HL
            0xD5,  # PUSH DE
            0xC5,  # PUSH BC
            0xF5,  # PUSH AF
            0x21,
            0x00,
            0x00,  # LD HL,0
            0x39,  # ADD HL,SP
            0x11,
            0x00,
            0x40,  # LD DE,0x4000
            0x23,
            0x7E,
            0x12,
            0x13,
            0x2B,
            0x7E,
            0x12,
            0x13,
            0x23,
            0x23,
            0x23,
            0x7E,
            0x12,
            0x13,
            0x2B,
            0x7E,
            0x12,
            0x13,
            0x23,
            0x23,
            0x23,
            0x7E,
            0x12,
            0x13,
            0x2B,
            0x7E,
            0x12,
            0x13,
            0x23,
            0x23,
            0x23,
            0x7E,
            0x12,
            0x13,
            0x2B,
            0x7E,
            0x12,
            0x13,
            0xF1,  # POP AF
            0xC1,  # POP BC
            0xD1,  # POP DE
            0xE1,  # POP HL
        ]
    )


def test_dump_regs_padding_and_selection():
    b = Block()
    register_dump_target("dump6", 0x1234, 6)
    dump_regs(b, "dump6", af=False, bc=True, de=False, hl=False)

    assert b.finalize() == bytes(
        [
            0xF5,  # PUSH AF (preserve)
            0xD5,  # PUSH DE (preserve)
            0xE5,  # PUSH HL (preserve)
            0xC5,  # PUSH BC (selected)
            0x21,
            0x00,
            0x00,  # LD HL,0
            0x39,  # ADD HL,SP
            0x11,
            0x34,
            0x12,  # LD DE,0x1234
            0x23,
            0x7E,
            0x12,
            0x13,
            0x2B,
            0x7E,
            0x12,
            0x13,
            0xAF,  # XOR A -> A=0
            0x12,
            0x13,
            0x12,
            0x13,
            0x12,
            0x13,
            0x12,
            0x13,  # 4×(LD (DE),A / INC DE)
            0xC1,  # POP BC
            0xE1,  # POP HL
            0xD1,  # POP DE
            0xF1,  # POP AF
        ]
    )


def test_dump_regs_rejects_overflow():
    b = Block()
    register_dump_target("dump8", 0x0000, 8)
    with pytest.raises(ValueError):
        dump_regs(b, "dump8", ix=True, iy=True)


def test_dump_regs_rejects_over_capacity():
    b = Block()
    register_dump_target("dump2", 0x2000, 2)

    with pytest.raises(ValueError):
        dump_regs(b, "dump2", af=False, bc=True, de=True, hl=False)
