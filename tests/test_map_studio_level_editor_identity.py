from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_t2600_module_editor_icon_opens_map_studio_level_editor() -> None:
    """The existing main-screen Module Editor action is the Map Studio entry point."""

    chrome_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/window_chrome.py"
    )
    resource_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/resource_panels.py"
    )
    integration_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/"
        "integration/tool_integration_registry.py"
    )

    assert 'QtGui.QAction(self._icon("modular"), "Open Map Studio Level Editor", self)' in chrome_source
    assert "self.modules_action.triggered.connect(self._open_module_editor_window)" in chrome_source
    assert "The Module Editor icon opens this unified Map Studio workspace" in resource_source
    assert "Module Editor icon opens the existing Level Editor as Map Studio" in integration_source


def test_t2600_level_editor_window_is_branded_as_map_studio_without_new_surface() -> None:
    """Map Studio remains the existing Level Editor window and KMAP workflow."""

    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    assert "class ModuleEditorWindow(QtWidgets.QMainWindow)" in window_source
    assert 'self.setWindowTitle("GhostRigger Map Studio - Level Editor")' in window_source
    assert "GhostRigger Map Studio - Level Editor - {self.project.name}" in window_source
    assert "Map Studio is GhostRigger's Level Editor opened from the Module Editor icon" in window_source
    assert "mapStudioLevelEditorScopeLabel" in window_source
    assert "KMAP terrain, rooms, walkmesh, placements, validation, staged export, install handoff, and game proof" in window_source
    assert "Map Studio Level Editor ready." in window_source
    assert "self.controller = ModuleEditorController()" in window_source
