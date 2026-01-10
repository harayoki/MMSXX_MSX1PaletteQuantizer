from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import BIT, Block  # noqa: E402


def test_bit_r_emits_cb_prefixed_opcode():
    b = Block()

    BIT.r(b, 0, "B")
    BIT.r(b, 7, "A")
    BIT.r(b, 3, "mHL")

    assert b.finalize() == bytes(
        [
            0xCB, 0x40,  # BIT 0,B
            0xCB, 0x7F,  # BIT 7,A
            0xCB, 0x5E,  # BIT 3,(HL)
        ]
    )


def test_bit_ix_iy_displacement_variants():
    b = Block()

    BIT.mIXd(b, 2, 0x12)
    BIT.mIYd(b, 6, -1)

    assert b.finalize() == bytes(
        [
            0xDD, 0xCB, 0x12, 0x56,  # BIT 2,(IX+0x12)
            0xFD, 0xCB, 0xFF, 0x76,  # BIT 6,(IY-1)
        ]
    )

