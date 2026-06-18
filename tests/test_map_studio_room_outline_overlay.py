from __future__ import annotations

from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (_repo() / rel).read_text(encoding="utf-8")


def test_t2664_viewport_exposes_room_outline_overlay_state_and_draw_path() -> None:
    viewport_source = _read(
        "native/GhostRigger.GUI.Boundary.Viewports/Python/src/gui/viewports/viewport_core/widgets/viewport_widget.py"
    )
    scene_models_source = _read(
        "native/GhostRigger.GUI.Boundary.Viewports/Python/src/gui/viewports/viewport_core/widgets/scene_models.py"
    )
    overlay_source = _read(
        "native/GhostRigger.GUI.Boundary.Viewports/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )
    pipeline_source = _read(
        "native/GhostRigger.GUI.Boundary.Viewports/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
    )

    assert "_map_studio_room_outline_geometry = None" in viewport_source
    assert "_map_studio_room_outline_hit_zones" in viewport_source
    assert "_map_studio_room_primitive_hit_zones" in viewport_source
    assert "def set_map_studio_room_outline_geometry" in scene_models_source
    assert "def clear_map_studio_room_outline_geometry" in scene_models_source
    assert "def _draw_map_studio_room_outlines" in overlay_source
    assert "def _draw_map_studio_room_primitive_handles" in overlay_source
    assert "def _draw_map_studio_dashed_line" in overlay_source
    assert "def map_studio_room_outline_point_at_screen" in overlay_source
    assert "def map_studio_room_primitive_at_screen" in overlay_source
    assert "def _add_map_studio_room_outline_hit_zone" in overlay_source
    assert "def _add_map_studio_room_primitive_hit_zone" in overlay_source
    assert "world_point=point" in overlay_source
    assert "primitive_handles" in overlay_source
    assert 'role == "wall_height"' in overlay_source
    assert 'role == "opening"' in overlay_source
    assert pipeline_source.index("self._draw_map_studio_room_outlines") < pipeline_source.index(
        "self._draw_map_studio_placement_markers"
    )


def test_t2664_module_editor_passes_room_outline_geometry_to_viewport_panel() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    native_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/module_editor_controller.py"
    )

    for source in (panel_source, native_panel_source):
        assert "authored_room_outline_geometry=None" in source
        assert "roomOutlinePointEdited" in source
        assert "roomPrimitiveMoved" in source
        assert "_room_outline_point_drag" in source
        assert "_room_primitive_drag" in source
        assert "def _room_outline_point_at_event" in source
        assert "def _room_primitive_at_event" in source
        assert "def _finish_room_outline_point_drag" in source
        assert "def _finish_room_primitive_drag" in source
        assert "self._sync_room_outline_overlay(authored_room_outline_geometry)" in source
        assert "def _sync_room_outline_overlay" in source
        assert "set_map_studio_room_outline_geometry" in source
        assert "clear_map_studio_room_outline_geometry" in source
        assert "room outline polygon(s)" in source
        assert "wall/opening guide(s)" in source
        assert "primitive handle(s)" in source

    assert "def authored_room_outline_geometry(self)" in controller_source
    assert "def move_authored_room_outline_point(self" in controller_source
    assert "def move_authored_room_primitive(self" in controller_source
    assert "authored_room_outline_geometry_for_project(authored)" in controller_source
    assert "authored_room_outline_geometry = self.controller.authored_room_outline_geometry()" in window_source
    assert "authored_room_outline_geometry," in window_source
    assert "roomOutlinePointEdited.connect(self._set_authored_room_outline_point)" in window_source
    assert "roomPrimitiveMoved.connect(self._move_authored_room_primitive)" in window_source
    assert "self.controller.move_authored_room_outline_point" in window_source
    assert "self.controller.move_authored_room_primitive" in window_source
