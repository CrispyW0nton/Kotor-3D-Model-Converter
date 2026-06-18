from __future__ import annotations

from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_repo() / path).read_text(encoding="utf-8")


def test_t2661_viewport_table_edits_authored_placement_transforms() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "from src.core.level import KMapProject, LevelTransform" in source
        assert "self.scene_table.itemChanged.connect(self._table_item_changed)" in source
        assert "editable_authored_columns = {2, 3, 4, 6}" in source
        assert 'str(item_id).startswith("authored:")' in source
        assert "def _table_item_changed" in source
        assert "self.transformEdited.emit(" in source
        assert "LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0))" in source
        assert 'replace("rad", "")' in source


def test_t2661_module_editor_routes_viewport_table_edits_through_controller() -> None:
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    )

    assert "self.viewport_panel.transformEdited.connect(self._set_transform)" in window_source
    assert "self.controller.set_authored_gameplay_placement_transform(" in window_source
    assert 'item_id.startswith("authored:")' in window_source
