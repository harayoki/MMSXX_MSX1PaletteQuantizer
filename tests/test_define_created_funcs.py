from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

import mmsxxasmhelper.core as core
import pytest


def _func_body(value: int):
    def _body(block: core.Block) -> None:
        block.emit(value)

    return _body


def test_define_created_funcs_excludes_by_name_and_reference(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    func_a = core.Func("FUNC_A", _func_body(0x00))
    func_b = core.Func("FUNC_B", _func_body(0x01))
    core.Func("FUNC_SKIP", _func_body(0x02))

    block = core.Block()

    core.define_created_funcs(block, core.DEFAULT_FUNC_GROUP_NAME, "FUNC_SKIP", func_a)

    assert "FUNC_A" not in block.labels
    assert "FUNC_SKIP" not in block.labels
    assert block.labels[func_b.name] == 0
    assert bytes(block.code) == bytes([0x01, 0xC9])


def test_finalize_errors_when_func_not_defined(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    core.Func("UNDEFINED_FUNC", _func_body(0x00))

    block = core.Block()

    with pytest.raises(ValueError, match="undefined func\(s\): UNDEFINED_FUNC"):
        block.finalize()


def test_finalize_checks_only_default_group_when_unspecified(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    core.Func("UNDEFINED_OTHER_GROUP", _func_body(0x00), group="other")

    block = core.Block()

    # group="other" の func は対象外なのでエラーにならない
    block.finalize()


def test_finalize_checks_specified_groups(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    core.Func("UNDEFINED_DEFAULT", _func_body(0x00))
    core.Func("UNDEFINED_GROUP", _func_body(0x01), group="grp")

    block = core.Block()

    with pytest.raises(ValueError, match="UNDEFINED_GROUP"):
        block.finalize(0, ["grp"])

    with pytest.raises(ValueError, match="UNDEFINED_DEFAULT, UNDEFINED_GROUP"):
        block.finalize(0, [core.DEFAULT_FUNC_GROUP_NAME, "grp"])


def test_finalize_allows_defined_funcs(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    func = core.Func("DEFINED_FUNC", _func_body(0x10))

    block = core.Block()
    func.define(block)

    assert block.finalize() == bytes([0x10, 0xC9])
