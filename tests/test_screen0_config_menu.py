from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pyutils/mmsxxasmhelper/src"))

import mmsxxasmhelper.core as core
import mmsxxasmhelper.msxutils as msxutils
import mmsxxasmhelper.config_scene as config_scene


def test_build_screen0_config_menu_generates_bytes(monkeypatch):
    monkeypatch.setattr(core, "_created_funcs_by_group", {}, raising=False)

    entries = [
        config_scene.Screen0ConfigEntry("MODE", ["MSX1", "MSX2"], 0xC200),
        config_scene.Screen0ConfigEntry("SPEED", ["SLOW", "FAST"], 0xC201),
    ]

    update_input = msxutils.build_update_input_func()
    init_func, loop_func, table_func = config_scene.build_screen0_config_menu(
        entries, update_input_func=update_input
    )

    block = core.Block()
    core.define_created_funcs(block)

    binary = block.finalize(0x8000)
    assert isinstance(binary, bytes)
    assert init_func.name in block.labels
    assert loop_func.name in block.labels
    assert table_func.name in block.labels
    assert b"MSX1" in binary
    assert len(binary) > 0
