from __future__ import annotations

from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_repo() / path).read_text(encoding="utf-8")


def test_t2663_module_editor_panel_drags_authored_markers() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "self._marker_drag: dict[str, object] | None = None" in source
        assert "def _begin_marker_drag" in source
        assert "def _update_marker_drag" in source
        assert "def _finish_marker_drag" in source
        assert "QtCore.QEvent.MouseMove" in source
        assert "QtCore.QEvent.MouseButtonRelease" in source
        assert "buttons & QtCore.Qt.LeftButton" in source
        assert "self.transformEdited.emit" in source
        assert "LevelTransform(position=position" in source


def test_t2663_marker_drag_uses_camera_projected_floor_delta() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "def _screen_delta_to_floor_delta" in source
        assert "project = getattr(renderer, \"_proj\", None)" in source
        assert "base = project(x, y, z, w, h)" in source
        assert "x_axis = project(x + 1.0, y, z, w, h)" in source
        assert "y_axis = project(x, y + 1.0, z, w, h)" in source
        assert "determinant = ax * by - ay * bx" in source
        assert "def _fallback_screen_delta_to_floor_delta" in source
        assert "def _clamp_floor_delta" in source


def test_t2666_marker_and_room_point_drags_honor_map_studio_snap_grid() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert 'self.snap_box.setObjectName("mapStudioViewportSnapCheckBox")' in source
        assert "def _snap_map_studio_position" in source
        assert "def _map_studio_grid_spacing" in source
        assert 'getattr(settings, "minor_grid_spacing", 10.0)' in source
        assert "return self._snap_map_studio_position(" in source
        assert "pending = self._snap_map_studio_position(" in source
        assert "round(float(position[0]) / spacing) * spacing" in source
        assert "round(float(position[1]) / spacing) * spacing" in source
