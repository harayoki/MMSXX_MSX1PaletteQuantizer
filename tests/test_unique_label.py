from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

import mmsxxasmhelper.core as core


def test_unique_label_increments(monkeypatch):
    monkeypatch.setattr(core, "_label_counters", {}, raising=False)

    first = core.unique_label()
    second = core.unique_label()

    assert first == "__L"
    assert second == "__L-1"
    assert first != second


def test_unique_label_with_custom_prefix(monkeypatch):
    monkeypatch.setattr(core, "_label_counters", {}, raising=False)

    assert core.unique_label("__MACRO__") == "__MACRO__"
    assert core.unique_label("__MACRO__") == "__MACRO__-1"


def test_unique_label_isolated_per_prefix(monkeypatch):
    monkeypatch.setattr(core, "_label_counters", {}, raising=False)

    first_prefix_a = core.unique_label("LABEL_A")
    first_prefix_b = core.unique_label("LABEL_B")
    second_prefix_a = core.unique_label("LABEL_A")

    assert first_prefix_a == "LABEL_A"
    assert first_prefix_b == "LABEL_B"
    assert second_prefix_a == "LABEL_A-1"
