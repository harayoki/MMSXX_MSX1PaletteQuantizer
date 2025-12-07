import pytest

import msxasmhelper


def test_ld_a_n():
    assert msxasmhelper.LD_A_n(0x55) == bytes([0x3E, 0x55])


def test_jp_nn_and_relative():
    assert msxasmhelper.JP_nn(0x1234) == bytes([0xC3, 0x34, 0x12])
    assert msxasmhelper.JR_e(-2) == bytes([0x18, 0xFE])


def test_assemble_direct_call():
    assert msxasmhelper.assemble("LD HL,nn", nn=0xC000) == bytes([0x21, 0x00, 0xC0])


def test_invalid_signed_offset():
    with pytest.raises(ValueError):
        msxasmhelper.JR_e(-129)


def test_operand_mismatch():
    with pytest.raises(KeyError):
        msxasmhelper.assemble("LD A,n")
    with pytest.raises(KeyError):
        msxasmhelper.assemble("LD A,n", n=0x01, extra=1)


def test_available_mnemonics_lists_dynamic_one():
    assert "LD A,n" in msxasmhelper.available_mnemonics()
