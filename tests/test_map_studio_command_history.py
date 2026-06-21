from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    for rel in reversed(
        (
            "native/GhostRigger.Core.Scene/Python",
            "native/GhostRigger.Core.Rendering/Python",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Game/Python",
            "native/GhostRigger.Core.Resources/Python",
            ".",
        )
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _first_floor_plan_point(controller) -> tuple[float, float]:
    payload = controller.project.extra_sections["authored_module"]
    point = payload["rooms"][0]["primitive"]["points"][0]
    return (float(point[0]), float(point[1]))


def test_t2606_command_history_restores_serialized_kmap_project_state() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.map_studio_command_history import MapStudioCommandHistory

    history = MapStudioCommandHistory(max_depth=4)
    project = new_kmap_project(name="grcmd01", game="K1", author="Shaolin")
    before = history.capture(project, selected_ids=("room-a",), active_module_id="mod-a", active_room_id="room-a")

    project.extra_sections["authored_module"] = {"module_root": "grcmd01", "rooms": []}
    project.name = "grcmd02"
    project.dirty = True
    after = history.capture(project, selected_ids=("room-b",), active_module_id="mod-b", active_room_id="room-b")

    record = history.record(
        action_key="map_studio.test",
        label="Test command",
        before=before,
        after=after,
        stale_outputs=("MDL", "WOK", ".mod"),
        readiness_impact="Export proof is stale.",
    )

    assert record is not None
    assert history.can_undo is True
    assert history.undo_label == "Test command"

    undo = history.undo()
    assert undo is not None
    assert undo.project.name == "grcmd01"
    assert undo.project.dirty is True
    assert undo.selected_ids == ("room-a",)
    assert undo.active_module_id == "mod-a"
    assert "MDL, WOK, .mod" in undo.message
    assert history.can_redo is True

    redo = history.redo()
    assert redo is not None
    assert redo.project.name == "grcmd02"
    assert redo.project.extra_sections["authored_module"]["module_root"] == "grcmd01"
    assert redo.selected_ids == ("room-b",)
    assert redo.active_room_id == "room-b"


def test_t2606_noop_commands_are_not_recorded() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.map_studio_command_history import MapStudioCommandHistory

    history = MapStudioCommandHistory()
    project = new_kmap_project(name="grnoop", game="K2")
    snapshot = history.capture(project)

    record = history.record(
        action_key="map_studio.noop",
        label="No-op",
        before=snapshot,
        after=snapshot,
    )

    assert record is None
    assert history.can_undo is False
    assert history.can_redo is False


def test_t2606_floor_plan_vertex_move_is_undoable_through_controller() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grcmd01", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grcmd01")
    room_resref = controller.authored_floor_plan_room_choices()[0].room_resref

    assert _first_floor_plan_point(controller) == (-5.0, -5.0)
    assert controller.can_undo_map_studio_command() is False

    controller.move_authored_room_outline_point(
        room_resref=room_resref,
        point_index=0,
        world_position=(0.5, 0.5, 0.0),
    )

    assert _first_floor_plan_point(controller) == (0.5, 0.5)
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Move grcmd01_room01 outline point 0"

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert _first_floor_plan_point(controller) == (-5.0, -5.0)
    assert controller.can_redo_map_studio_command() is True
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message

    redo = controller.redo_map_studio_command()
    assert redo is not None
    assert _first_floor_plan_point(controller) == (0.5, 0.5)


def test_t2606_level_editor_wires_undo_redo_actions_to_map_studio_command_spine() -> None:
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    scene_controller = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py")
    tools_controller = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py")

    assert "self.undo_action.triggered.connect(self.undo_map_studio_command)" in window_source
    assert "self.redo_action.triggered.connect(self.redo_map_studio_command)" in window_source
    assert "def _update_map_studio_undo_redo_actions" in window_source
    assert "self.undo_action.setText(f\"Undo {undo_label}\" if undo_label else \"Undo\")" in window_source
    assert "self.redo_action.setText(f\"Redo {redo_label}\" if redo_label else \"Redo\")" in window_source

    for source in (scene_controller, tools_controller):
        assert "from .map_studio_command_history import MapStudioCommandHistory" in source
        assert "self.command_history = MapStudioCommandHistory()" in source
        assert "def undo_map_studio_command" in source
        assert "def redo_map_studio_command" in source
        assert "MAP_STUDIO_MODELING_STALE_OUTPUTS" in source
        assert "Map Studio validation, export, install handoff, and game proof are stale." in source
