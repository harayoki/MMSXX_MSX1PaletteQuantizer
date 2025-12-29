from itertools import count
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

import mmsxxasmhelper.core as core


def test_unique_label_increments(monkeypatch):
    monkeypatch.setattr(core, "_label_counter", count(), raising=False)

    first = core.unique_label()
    second = core.unique_label()

    assert first == "__L0"
    assert second == "__L1"
    assert first != second


def test_unique_label_with_custom_prefix(monkeypatch):
    monkeypatch.setattr(core, "_label_counter", count(), raising=False)

    assert core.unique_label("__MACRO__") == "__MACRO__0"
