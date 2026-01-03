from pathlib import Path
import sys

# Make assembler helper importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

from mmsxxasmhelper.core import Block, NOP  # noqa: E402
from mmsxxasmhelper import utils  # noqa: E402


def test_embed_debug_string_macro_skips_embedded_bytes():
    b = Block()

    utils.embed_debug_string_macro(b, "HERE")
    NOP(b)

    rom = b.finalize()

    # JP should skip past the embedded string
    jump_target = int.from_bytes(rom[1:3], byteorder="little")
    assert jump_target == 3 + len("HERE")

    # The string bytes should be present immediately after the JP
    assert rom[3:3 + len("HERE")] == b"HERE"

    # Execution resumes at the instruction after the embedded string
    assert rom[jump_target] == 0x00  # NOP opcode
