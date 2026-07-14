"""Terrain patch create -> paint -> export loop (Map Studio terrain painting)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _install_roots() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_create_terrain_patch_then_paint_and_undo() -> None:
    _install_roots()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grterr01", game="K1")

    resref = controller.create_terrain_patch(shape_preset_id="gentle_mound", resolution=9)
    assert resref == "grterr01_terrain"

    # The new patch is a real, paintable terrain room.
    choices = controller.authored_terrain_room_choices()
    assert any(str(getattr(ch, "room_resref", "")) == resref for ch in choices)

    # Painting mutates it and records an undo checkpoint.
    controller.apply_authored_terrain_brush_stroke(
        brush="raise", room_resref=resref, points=((4, 4, 1.0),), delta=0.5, radius=2, strength=0.8
    )
    assert controller.can_undo_map_studio_command()
    controller.undo_map_studio_command()

    # A second patch in the same module gets a unique resref.
    second = controller.create_terrain_patch(resolution=5)
    assert second != resref
    assert second.startswith("grterr01_terrain")


def test_live_sculpt_segment_fills_fast_pointer_gaps_and_defers_ramps() -> None:
    _install_roots()
    from src.core.modules.map_studio_terrain_sculpt_session import (
        interpolate_terrain_sculpt_segment,
        terrain_sculpt_brush_is_deferred,
    )

    points = interpolate_terrain_sculpt_segment((2, 1, 0.25), (2, 6, 1.0), include_start=True)
    assert [(point.row_index, point.column_index) for point in points] == [
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
        (2, 5),
        (2, 6),
    ]
    assert points[0].strength == 0.25
    assert points[-1].strength == 1.0
    assert terrain_sculpt_brush_is_deferred("ramp") is True
    assert terrain_sculpt_brush_is_deferred("slope") is True
    assert terrain_sculpt_brush_is_deferred("raise") is False


def test_terrain_patch_exports_as_module(tmp_path) -> None:
    _install_roots()
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grterr02", game="K1")
    # Flat keeps the floor at Z=0 so the module entry point sits on it; a
    # raised preset would (correctly) fail entry-point-on-floor validation.
    controller.create_terrain_patch(shape_preset_id="flat", resolution=9)

    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload, fallback_name="grterr02", fallback_game="K1")
    result = export_authored_module_project(
        AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path))
    )
    kinds = {(entry.resref, entry.restype) for entry in result.resources}
    # A terrain room exports its walkmesh + room model + module files like any
    # authored room, so it can be packaged as a playable .mod.
    assert any(restype == "wok" for _resref, restype in kinds)
    assert any(restype == "mdl" for _resref, restype in kinds)
    assert any(restype == "lyt" for _resref, restype in kinds)
    assert any(restype == "are" for _resref, restype in kinds)


def test_live_terrain_stroke_commit_is_one_step_undoable_and_redoable() -> None:
    _install_roots()
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grterr03", game="K1")
    room_resref = controller.create_terrain_patch(resolution=9)
    before_payload = controller.project.extra_sections["authored_module"]
    before = authored_project_from_kmap_payload(before_payload).rooms[0].primitive.heights

    frame = controller.apply_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((4, 4, 1.0),),
        delta=0.5,
        radius=2,
        force=True,
    )
    assert frame.applied is True
    commit = controller.commit_map_studio_terrain_sculpt_stroke(
        brush="raise",
        room_resref=room_resref,
    )
    assert commit is not None
    after = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights
    assert after != before

    assert controller.undo_map_studio_command() is not None
    undone = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights
    assert undone == before
    assert controller.redo_map_studio_command() is not None
    redone = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights
    assert redone == after


def test_terrain_release_keeps_resident_mesh_and_defers_serialized_overlay() -> None:
    _install_roots()
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    calls: dict[str, object] = {}

    class Controller:
        def commit_map_studio_terrain_sculpt_stroke(self, **kwargs):
            calls["commit"] = dict(kwargs)
            return SimpleNamespace(frame_count=1)

        def authored_terrain_walkability_overlay(self):
            raise AssertionError("mouse release must not synchronously serialize the terrain WOK overlay")

    class ViewportPanel:
        def set_terrain_walkability_overlay(self, overlay):
            calls["overlay"] = overlay

    def refresh(message: str, **kwargs) -> None:
        calls["refresh"] = (message, dict(kwargs))

    target = SimpleNamespace(
        controller=Controller(),
        viewport_panel=ViewportPanel(),
        _refresh_map_studio_geometry_change=refresh,
        _sync_map_studio_terrain_brush_context=lambda: calls.setdefault("context_synced", True),
        _log=lambda message: calls.setdefault("log", message),
    )
    ModuleEditorWindow.commit_map_studio_viewport_terrain_brush_stroke(
        target,
        "raise",
        "grterr04_terrain",
    )

    assert calls["commit"] == {"brush": "raise", "room_resref": "grterr04_terrain"}
    assert calls["overlay"] is None
    message, refresh_kwargs = calls["refresh"]
    assert "background" in message
    assert refresh_kwargs == {
        "rebuild_viewport_model": False,
        "refresh_scene_tree": False,
        "validation_delay_ms": 250,
    }
    assert calls["context_synced"] is True
    assert target._last_map_studio_terrain_release_ms >= 0.0


def test_deferred_geometry_worker_returns_fresh_terrain_overlay(monkeypatch) -> None:
    _install_roots()
    import src.gui.windows.module_editor_window as window_module

    overlay = object()
    terrain_choices = (object(),)

    class Controller:
        def authored_module_readiness(self):
            return SimpleNamespace(readiness="ready")

        def authored_terrain_walkability_overlay(self):
            return overlay

        def validate(self, readiness_result=None):
            return ("issue",)

        def authored_walkmesh_status(self):
            return "walkmesh"

        def authored_walkmesh_room_surface_choices(self):
            return ("surface",)

        def authored_terrain_room_choices(self):
            return terrain_choices

    monkeypatch.setattr(
        window_module,
        "KMapSerializer",
        SimpleNamespace(from_dict=lambda payload: payload),
    )
    monkeypatch.setattr(window_module, "ModuleEditorModel", lambda project: project)
    monkeypatch.setattr(window_module, "ModuleEditorController", lambda model: Controller())

    result = window_module._build_map_studio_geometry_validation_snapshot({"name": "terrain"})
    assert result["terrain_walkability_overlay"] is overlay
    assert result["terrain_room_choices"] is terrain_choices
    assert result["walkmesh_status"] == "walkmesh"
    assert result["elapsed_ms"] >= 0.0
