from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, JP_PE, JP_PO  # noqa: E402


def test_jp_po_and_jp_pe_emit_correct_opcodes():
    b = Block()

    JP_PO(b, "dest_po")
    JP_PE(b, "dest_pe")

    b.label("dest_po")
    JP_PO(b, "dest_pe")
    b.label("dest_pe")

    assert b.finalize() == bytes(
        [
            0xE2,
            0x06,
            0x00,  # JP PO,dest_po
            0xEA,
            0x09,
            0x00,  # JP PE,dest_pe
            0xE2,
            0x09,
            0x00,  # JP PO,dest_pe (after dest_po label)
        ]
    )
