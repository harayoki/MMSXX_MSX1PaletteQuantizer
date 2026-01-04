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
    assert jump_target == 3 + 1 + len("HERE") + 1

    # The string bytes should be present immediately after the JP
    assert rom[4:4 + len("HERE")] == b"HERE"

    # Execution resumes at the instruction after the embedded string
    assert rom[3] == 0x00  # NOP opcode before the string
    assert rom[jump_target] == 0x00  # NOP opcode after the string


def test_embed_debug_string_macro_reports_locations(capsys):
    b = Block()

    utils.embed_debug_string_macro(b, "HERE")
    utils.embed_debug_string_macro(b, "THERE")
    NOP(b)

    b.finalize(origin=0x4000)

    output = capsys.readouterr().out.splitlines()

    assert output[0] == "Embedded debug strings:"
    assert "4004 ~ 4007 (+0004 ~ +0007): HERE" in output[1]
    assert "400D ~ 4011 (+000D ~ +0011): THERE" in output[2]
