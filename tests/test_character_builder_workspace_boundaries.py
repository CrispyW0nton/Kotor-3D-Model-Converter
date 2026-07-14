from __future__ import annotations

import inspect

from PySide6 import QtWidgets

from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel


def test_character_builder_disables_module_mesh_properties_tab() -> None:
    source = inspect.getsource(QtCharacterBuilderWindow._build_central)
    assert "QtPropertiesPanel(self, module_browser_enabled=False)" in source

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel(module_browser_enabled=False)
    try:
        names = [panel.tabs.tabText(index) for index in range(panel.tabs.count())]
        assert names == ["General"]
        assert panel.module_tab is None
    finally:
        panel.close()
