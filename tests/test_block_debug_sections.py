from pathlib import Path
import sys

import pytest

# Make assembler helper importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block  # noqa: E402


def test_ifdebug_skips_emits_when_debug_disabled():
    block = Block()

    block.emit(0xAA)
    block.ifdebug()
    block.emit(0xBB, 0xCC)
    block.label("debug_only")
    block.add_abs16_fixup(block.emit(0x00, 0x00), "after")
    block.endifdebug()
    block.emit(0xDD)
    block.label("after")

    assert block.finalize(origin=0x1000) == bytes([0xAA, 0xDD])
    assert block.labels == {"after": 2}


def test_ifdebug_processes_emits_when_debug_enabled():
    block = Block(debug=True)

    block.emit(0xAA)
    block.ifdebug()
    placeholder_pos = block.emit(0x00, 0x00)
    block.add_abs16_fixup(placeholder_pos, "after")
    block.endifdebug()
    block.emit(0xDD)
    block.label("after")

    assert block.finalize(origin=0x2000) == bytes([0xAA, 0x04, 0x20, 0xDD])
    assert block.labels == {"after": 4}


def test_endifdebug_without_ifdebug_errors():
    block = Block()

    with pytest.raises(ValueError):
        block.endifdebug()


def test_finalize_detects_unclosed_debug_sections():
    block = Block()

    block.ifdebug()

    with pytest.raises(ValueError):
        block.finalize()
