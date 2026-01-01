from io import StringIO
from pathlib import Path
import sys

import pytest

# Make assembler helper importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, JR, NOP  # noqa: E402
from mmsxxasmhelper import utils  # noqa: E402


@pytest.fixture(autouse=True)
def restore_debug_flag():
    # Ensure DEBUG flag is reset after each test to avoid cross-test pollution.
    yield
    utils.set_debug(True)


def test_debug_print_labels_outputs_addresses():
    b = Block()
    b.label("start")
    NOP(b)
    NOP(b)
    b.label("loop")
    JR(b, "loop")

    b.finalize(origin=0x4000)

    buffer = StringIO()
    utils.debug_print_labels(b, origin=0x4000, stream=buffer)

    assert buffer.getvalue().splitlines() == [
        "4000: start",
        "4002: loop",
    ]


def test_debug_print_labels_outputs_offsets():
    b = Block()
    b.label("zero")
    NOP(b)
    b.label("one")

    b.finalize(origin=0x1234)

    buffer = StringIO()
    utils.debug_print_labels(b, origin=0x1234, stream=buffer, include_offset=True)

    assert buffer.getvalue().splitlines() == [
        "1234 (+0000): zero",
        "1235 (+0001): one",
    ]


def test_debug_print_labels_respects_debug_flag():
    utils.set_debug(False)

    b = Block()
    b.label("no_output")

    b.finalize()

    buffer = StringIO()
    utils.debug_print_labels(b, origin=0x8000, stream=buffer)

    assert buffer.getvalue() == ""
