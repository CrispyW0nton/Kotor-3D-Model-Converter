from __future__ import annotations

from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_repo() / path).read_text(encoding="utf-8")


def test_t2660_viewport_has_map_studio_marker_overlay_hooks() -> None:
    widget_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/viewport_widget.py"
    )
    scene_models_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/scene_models.py"
    )
    overlay_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )
    pipeline_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "authored_gameplay_marker_geometry=None" in source
        assert "self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)" in source
        assert "set_map_studio_marker_geometry" in source
        assert "clear_map_studio_marker_geometry" in source
        assert "footprint(s)" in source
        assert "guide line(s)" in source


def test_t2662_marker_overlay_builds_screen_hit_zones() -> None:
    widget_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/viewport_widget.py"
    )
    overlay_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )

    assert "self._map_studio_marker_hit_zones: list[dict[str, object]] = []" in widget_source
    assert "def map_studio_marker_at_screen" in overlay_source
    assert "def _add_map_studio_marker_hit_zone" in overlay_source
    assert "kind == \"rect\"" in overlay_source
    assert "kind == \"circle\"" in overlay_source
    assert "kind == \"line\"" in overlay_source
    assert "_map_studio_distance_to_segment" in overlay_source
    assert "self._map_studio_marker_hit_zones = []" in overlay_source
    assert "placement_id" in overlay_source


def test_t2662_module_editor_panel_selects_authored_marker_from_viewport_click() -> None:
    panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )

    for source in (panel_source, mirrored_panel_source):
        assert "self._marker_pick_filter_ids: set[int] = set()" in source
        assert "self._install_marker_pick_filters()" in source
        assert "def _is_marker_pick_event_source" in source
        assert "def _marker_at_event" in source
        assert "map_studio_marker_at_screen" in source
        assert "self.itemSelected.emit(placement_id)" in source
        assert "return True" in source
