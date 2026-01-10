"""Sanity checks for debug image label embedding.

This test focuses on the debug image generation path of
``pyutils/sc2_viewer_rom/src/create_scroll_megarom.py``.  The module depends
on optional third-party packages (Pillow and simple_sc2_converter) that are not
required for the label-packing logic.  The fixtures below stub those modules so
that we can import and exercise the builder without installing extra
dependencies.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _import_create_scroll_megarom(monkeypatch):
    """Import the ROM builder with minimal stubs for optional dependencies."""

    # Ensure the repository root is importable when tests run from the tests directory.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))

    # The assembler helper lives in the repository; make it importable.
    monkeypatch.syspath_prepend("pyutils/mmsxxasmhelper/src")

    # Stub Pillow
    pil = types.ModuleType("PIL")
    pil.Image = object
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil)

    # Stub simple_sc2_converter
    converter = types.SimpleNamespace(BASIC_COLORS_MSX1=None, parse_color=lambda value: value)
    ssc = types.ModuleType("simple_sc2_converter")
    ssc.converter = converter
    monkeypatch.setitem(sys.modules, "simple_sc2_converter", ssc)
    monkeypatch.setitem(sys.modules, "simple_sc2_converter.converter", converter)

    return importlib.import_module("pyutils.sc2_viewer_rom.src.create_scroll_megarom")


def test_debug_labels_include_lowercase(monkeypatch):
    mod = _import_create_scroll_megarom(monkeypatch)

    rom = mod.build(mod.create_debug_image_data_list(2))

    pattern_pos = rom.find(b"PATTERN[2] SCROLL VIEWER DEBUG")

    # Pattern label should be present near the start of the pattern bank
    assert pattern_pos >= mod.PAGE_SIZE

    # Color label is lower-case and lives at the beginning of the color bank
    color_pos = rom.find(b"color[2] scroll viewer debug")
    expected_color_pos = pattern_pos + mod.PATTERN_RAM_SIZE
    assert color_pos == expected_color_pos

