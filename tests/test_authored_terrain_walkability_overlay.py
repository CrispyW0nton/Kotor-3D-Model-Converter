from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    payloads = (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    )
    for rel in payloads:
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        import src.core as core_package

        core_paths = getattr(core_package, "__path__", None)
        if core_paths is not None:
            existing = {str(item) for item in core_paths}
            for rel in payloads:
                core_dir = (repo / rel / "src" / "core").resolve()
                if core_dir.exists() and str(core_dir) not in existing:
                    core_paths.append(str(core_dir))
                    existing.add(str(core_dir))
    except Exception:
        pass


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")


def test_t2907_terrain_walkability_overlay_marks_steep_faces_non_walk() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_operations import apply_authored_terrain_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_terrain_walkability_overlay import authored_terrain_walkability_overlay_for_project

    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grterr",
        game="K1",
    )
    steep = apply_authored_terrain_operation(
        project,
        "set_height",
        row_index=1,
        column_index=1,
        height=5.0,
    )

    overlay = authored_terrain_walkability_overlay_for_project(steep)
    blocked = [triangle for triangle in overlay.triangles if not triangle.walkable]

    assert overlay.triangles
    assert overlay.walkable_triangle_count > 0
    assert overlay.non_walk_triangle_count == len(blocked)
    assert overlay.non_walk_triangle_count > 0
    assert overlay.max_slope_degrees > 35.0
    assert all(len(triangle.points) == 3 for triangle in overlay.triangles)
    assert any(triangle.surface_id == 7 for triangle in blocked)
    assert any("Slope" in triangle.reason for triangle in blocked)


def test_t2907_module_editor_controller_exposes_terrain_walkability_overlay() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr")
    controller.apply_authored_terrain_operation(
        operation="set_height",
        row_index=1,
        column_index=1,
        height=5.0,
    )

    overlay = controller.authored_terrain_walkability_overlay()

    assert overlay.triangles
    assert overlay.walkable_triangle_count > 0
    assert overlay.non_walk_triangle_count > 0
    assert any(not triangle.walkable and triangle.reason for triangle in overlay.triangles)


def test_t2907_map_studio_viewport_draws_terrain_walkability_overlay() -> None:
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
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    mirrored_panel_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/module_editor_controller.py"
    )

    assert "_map_studio_terrain_walkability_overlay = None" in viewport_source
    assert "_map_studio_terrain_brush_cursor = None" in viewport_source
    assert "def set_map_studio_terrain_walkability_overlay" in scene_models_source
    assert "def clear_map_studio_terrain_walkability_overlay" in scene_models_source
    assert "def set_map_studio_terrain_brush_cursor" in scene_models_source
    assert "def clear_map_studio_terrain_brush_cursor" in scene_models_source
    assert "def _draw_map_studio_terrain_walkability" in overlay_source
    assert "def _draw_map_studio_terrain_brush_cursor" in overlay_source
    assert "terrain walkability" in panel_source
    assert "terrain walkability" in mirrored_panel_source
    assert "mapStudioViewportTerrainBrushCheckBox" in panel_source
    assert "def _set_terrain_brush_cursor" in panel_source
    assert "mapStudioViewportTerrainBrushCheckBox" in mirrored_panel_source
    assert "def _set_terrain_brush_cursor" in mirrored_panel_source
    assert "authored_terrain_walkability_overlay = self.controller.authored_terrain_walkability_overlay()" in window_source
    assert "def authored_terrain_walkability_overlay(self)" in controller_source
    assert pipeline_source.index("self._draw_map_studio_terrain_walkability") < pipeline_source.index(
        "self._draw_map_studio_room_outlines"
    )
    assert pipeline_source.index("self._draw_map_studio_terrain_walkability") < pipeline_source.index(
        "self._draw_map_studio_terrain_brush_cursor"
    )
    assert pipeline_source.index("self._draw_map_studio_terrain_brush_cursor") < pipeline_source.index(
        "self._draw_map_studio_room_outlines"
    )
