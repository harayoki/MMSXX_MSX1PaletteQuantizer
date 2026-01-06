from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, LDD, LDI  # noqa: E402


def test_ldi_and_ldd_emit_correct_opcodes():
    b = Block()

    LDI(b)
    LDD(b)

    assert b.finalize() == bytes(
        [
            0xED,
            0xA0,  # LDI
            0xED,
            0xA8,  # LDD
        ]
    )
