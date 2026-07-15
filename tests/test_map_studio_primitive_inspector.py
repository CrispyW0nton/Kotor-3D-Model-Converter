from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace


def _install_gui_payload_path() -> None:
    repo = Path(__file__).resolve().parents[1]
    payload = str(
        (repo / "native" / "GhostRigger.Core.GUI.Display" / "Python" / "src").resolve()
    )
    if payload not in sys.path:
        sys.path.insert(0, payload)


def test_unbounded_primitive_axis_editor_accepts_zero_and_negative_values() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_gui_payload_path()

    from PySide6 import QtWidgets
    from gui.panels.module_editor.builder_tab import BuilderTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = BuilderTab()
    payload = tab._primitive_property_payload(
        SimpleNamespace(
            key="axis_x",
            label="Axis X",
            value=0.0,
            value_type="float",
            minimum=None,
            maximum=None,
            soft_minimum=-1.0,
            soft_maximum=1.0,
            step=0.1,
            implementation_note="Signed Maya-style construction axis.",
        )
    )
    editor = tab._make_primitive_numeric_editor(payload, 0)

    assert editor.minimum() < -1.0
    assert editor.maximum() > 1.0
    editor.setValue(0.0)
    assert editor.value() == 0.0
    editor.setValue(-1.0)
    assert editor.value() == -1.0
    assert payload["description"] == "Signed Maya-style construction axis."

    editor.deleteLater()
    tab.deleteLater()
    app.processEvents()
