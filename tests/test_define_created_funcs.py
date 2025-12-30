from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

import mmsxxasmhelper.core as core


def _func_body(value: int):
    def _body(block: core.Block) -> None:
        block.emit(value)

    return _body


def test_define_created_funcs_excludes_by_name_and_reference(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs", [], raising=False)

    func_a = core.Func("FUNC_A", _func_body(0x00))
    func_b = core.Func("FUNC_B", _func_body(0x01))
    core.Func("FUNC_SKIP", _func_body(0x02))

    block = core.Block()

    core.define_created_funcs(block, "FUNC_SKIP", func_a)

    assert "FUNC_A" not in block.labels
    assert "FUNC_SKIP" not in block.labels
    assert block.labels[func_b.name] == 0
    assert bytes(block.code) == bytes([0x01, 0xC9])
