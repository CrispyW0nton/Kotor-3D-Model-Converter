from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[1]
DISPLAY_PYTHON = REPO / "native/GhostRigger.Core.GUI.Display/Python"
DISPLAY_TOOLBAR = DISPLAY_PYTHON / "src/gui/panels/module_editor/module_editor_toolbar.py"
TOOLS_TOOLBAR = REPO / "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_toolbar.py"
TOOLS_WINDOW = REPO / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"


def _load_toolbar_class():
    display_path = str(DISPLAY_PYTHON)
    if display_path not in sys.path:
        sys.path.insert(0, display_path)
    spec = importlib.util.spec_from_file_location("_ghoststudio_pie_toolbar_test", DISPLAY_TOOLBAR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ModuleEditorToolbar


def _opaque_average_rgb(icon) -> tuple[float, float, float]:
    image = icon.pixmap(24, 24).toImage()
    samples: list[tuple[int, int, int]] = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() >= 32:
                samples.append((color.red(), color.green(), color.blue()))
    assert samples
    count = float(len(samples))
    return (
        sum(sample[0] for sample in samples) / count,
        sum(sample[1] for sample in samples) / count,
        sum(sample[2] for sample in samples) / count,
    )


def test_t3008_map_studio_pie_button_visibly_round_trips_play_and_stop() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    toolbar = _load_toolbar_class()()
    try:
        class _Theme:
            @staticmethod
            def color(token: str, default: str | None = None) -> str:
                return {"success": "#20B95A", "error": "#D63B43"}.get(token, default or "#000000")

        toolbar.apply_ghost_theme(_Theme())
        button = toolbar.buttons["simulate"]
        assert button.objectName() == "mapStudioToolbarActionButton_simulate"
        assert button.isHidden() is False
        assert button.isCheckable() is True
        assert button.text() == "Play"
        assert button.property("mapStudioPIEState") == "editing"
        assert button.accessibleName() == "Play in Editor"
        assert "not KOTOR engine proof" in button.toolTip()
        assert button.toolButtonStyle() == QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        play_rgb = _opaque_average_rgb(button.icon())
        assert play_rgb[1] > play_rgb[0] and play_rgb[1] > play_rgb[2]

        emitted: list[str] = []
        toolbar.actionRequested.connect(emitted.append)
        button.click()
        app.processEvents()
        assert emitted == ["simulate"]

        toolbar.set_simulation_active(True)
        assert emitted == ["simulate"]
        assert button.isChecked() is True
        assert button.text() == "Stop"
        assert button.property("mapStudioPIEState") == "playing"
        assert button.accessibleName() == "Stop Play in Editor"
        stop_rgb = _opaque_average_rgb(button.icon())
        assert stop_rgb[0] > stop_rgb[1] and stop_rgb[0] > stop_rgb[2]

        toolbar.set_simulation_active(False)
        assert button.isChecked() is False
        assert button.text() == "Play"
        assert button.property("mapStudioPIEState") == "editing"

        toolbar.apply_ghost_layout(
            SimpleNamespace(
                toolbar=lambda _toolbar_id: SimpleNamespace(
                    height=36,
                    icon_size=22,
                    button_mode="iconOnly",
                )
            )
        )
        assert button.toolButtonStyle() == QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.icon().isNull() is False
    finally:
        toolbar.deleteLater()


def test_t3008_pie_toolbar_payload_copies_and_window_state_contract_stay_synchronized() -> None:
    assert DISPLAY_TOOLBAR.read_bytes() == TOOLS_TOOLBAR.read_bytes()

    source = TOOLS_WINDOW.read_text(encoding="utf-8")
    assert 'QtGui.QAction("Play in Editor", self)' in source
    assert 'self.simulate_action.setObjectName("mapStudioSimulateAction")' in source
    assert 'self.simulate_action.setShortcut(QtGui.QKeySequence("Alt+P"))' in source
    assert "def _set_map_studio_pie_command_active" in source
    assert source.count("self._set_map_studio_pie_command_active(False)") == 5
    assert source.count("self._set_map_studio_pie_command_active(True)") == 1
    assert "self.simulate_action.setChecked(False)\n            self.toolbar.set_simulation_active(False)" not in source
