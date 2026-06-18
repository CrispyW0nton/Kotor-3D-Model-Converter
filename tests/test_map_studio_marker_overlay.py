from __future__ import annotations

from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_repo() / path).read_text(encoding="utf-8")


def test_t2660_viewport_has_map_studio_marker_overlay_hooks() -> None:
    widget_source = _read(
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

    assert "self._map_studio_marker_geometry = None" in widget_source
    assert "def set_map_studio_marker_geometry" in scene_models_source
    assert "def clear_map_studio_marker_geometry" in scene_models_source
    assert "def _draw_map_studio_placement_markers" in overlay_source
    assert "footprints" in overlay_source
    assert "guide" in overlay_source
    assert "self._draw_map_studio_placement_markers(draw, w, h)" in pipeline_source
    assert pipeline_source.index("self._draw_map_studio_placement_markers(draw, w, h)") < pipeline_source.index(
        "self._draw_wgpu_helper_markers(draw, w, h)"
    )


def test_t2660_module_editor_panel_sends_marker_geometry_to_viewport() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "authored_gameplay_marker_geometry=None" in source
        assert "self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)" in source
        assert "set_map_studio_marker_geometry" in source
        assert "clear_map_studio_marker_geometry" in source
        assert "footprint(s)" in source
        assert "guide line(s)" in source
