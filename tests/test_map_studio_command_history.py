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


def _first_terrain_height(controller, row: int, column: int) -> float:
    payload = controller.project.extra_sections["authored_module"]
    return float(payload["rooms"][0]["primitive"]["heights"][row][column])


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
    controller.command_history.clear()

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


def test_t2606_terrain_sculpt_preview_is_side_effect_free_until_stroke_commit() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grtrn01", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grtrn01")
    room_resref = controller.project.extra_sections["authored_module"]["rooms"][0]["room_resref"]
    controller.command_history.clear()

    assert _first_terrain_height(controller, 2, 2) == 0.35
    frame = controller.prepare_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((2, 2),),
        delta=1.0,
        radius=0,
    )

    assert frame.operation == "brush_stroke:raise"
    assert _first_terrain_height(controller, 2, 2) == 0.35
    assert controller.can_undo_map_studio_command() is False

    result = controller.apply_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((2, 2),),
        delta=1.0,
        radius=0,
    )

    assert result.applied is True
    assert _first_terrain_height(controller, 2, 2) == 1.35
    assert controller.can_undo_map_studio_command() is False

    controller.commit_map_studio_terrain_sculpt_stroke(brush="raise", room_resref=room_resref)

    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Sculpt terrain raise on grtrn01_room01"

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert _first_terrain_height(controller, 2, 2) == 0.35


def test_t2606_gameplay_placement_edits_are_undoable_kmap_commands() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grgitcmd", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grgitcmd")
    added = controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="bench_a",
        position=(1.0, 1.0, 0.0),
    )
    controller.command_history.clear()
    placement_id = next(row.placement_id for row in controller.authored_gameplay_placements() if row.tag == "bench_a")

    controller.set_authored_gameplay_placement_transform(
        placement_id,
        position=(2.0, 3.0, 0.0),
        bearing=45.0,
    )
    payload = controller.project.extra_sections["authored_module"]
    assert payload["placements"]["placeables"][-1]["position"] == [2.0, 3.0, 0.0]
    assert controller.command_history.undo_label == "Move placeable placement bench_a"
    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["position"] == [1.0, 1.0, 0.0]
    controller.redo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["bearing"] == 45.0

    controller.command_history.clear()
    renamed = controller.rename_authored_gameplay_placement(placement_id, tag="bench_renamed")
    assert renamed.tag == "bench_renamed"
    assert controller.command_history.undo_label == "Rename placeable placement bench_renamed"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["tag"] == "bench_a"

    controller.command_history.clear()
    duplicated = controller.duplicate_authored_gameplay_placement(placement_id)
    assert duplicated.tag == "bench_a_copy"
    placeable_count = len(controller.project.extra_sections["authored_module"]["placements"]["placeables"])
    assert placeable_count >= 3
    assert controller.command_history.undo_label == "Duplicate placeable placement bench_a_copy"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["placements"]["placeables"]) == placeable_count - 1

    controller.command_history.clear()
    removed = controller.remove_authored_gameplay_placement(placement_id)
    assert removed.tag == "bench_a"
    removed_count = len(controller.project.extra_sections["authored_module"]["placements"]["placeables"])
    assert removed_count == placeable_count - 2
    assert controller.command_history.undo_label == "Remove placeable placement bench_a"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["placements"]["placeables"]) == removed_count + 1
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["tag"] == "bench_a"


def test_t2606_room_light_edits_are_undoable_kmap_commands() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grlightcmd", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlightcmd")
    controller.add_authored_room_light(name="key_light", position=(0.0, 0.0, 2.25))
    controller.command_history.clear()
    light_id = controller.authored_room_lights()[-1].light_id

    controller.set_authored_room_light_transform(light_id, position=(1.0, 2.0, 3.0))
    payload = controller.project.extra_sections["authored_module"]
    assert payload["lights"][-1]["position"] == [1.0, 2.0, 3.0]
    assert controller.command_history.undo_label == "Move room light key_light"
    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["position"] == [0.0, 0.0, 2.25]

    controller.command_history.clear()
    controller.set_authored_room_light_properties(
        light_id,
        color=(0.25, 0.5, 1.0),
        radius=12.5,
        intensity=1.75,
        light_type="spot",
    )
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["light_type"] == "spot"
    assert controller.command_history.undo_label == "Edit room light key_light"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["light_type"] == "point"

    controller.command_history.clear()
    renamed = controller.rename_authored_room_light(light_id, name="warm_key")
    assert renamed.light.name == "warm_key"
    assert controller.command_history.undo_label == "Rename room light warm_key"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["name"] == "key_light"

    controller.command_history.clear()
    duplicated = controller.duplicate_authored_room_light(light_id)
    assert duplicated.light.name == "key_light_copy"
    light_count = len(controller.project.extra_sections["authored_module"]["lights"])
    assert light_count >= 2
    assert controller.command_history.undo_label == "Duplicate room light key_light_copy"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["lights"]) == light_count - 1

    controller.command_history.clear()
    removed = controller.remove_authored_room_light(light_id)
    assert removed.light.name == "key_light"
    removed_count = len(controller.project.extra_sections["authored_module"]["lights"])
    assert removed_count == light_count - 2
    assert controller.command_history.undo_label == "Remove room light key_light"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["lights"]) == removed_count + 1
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["name"] == "key_light"


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


def test_t2606_map_studio_topology_and_terrain_commands_have_action_keys() -> None:
    scene_controller = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py")
    tools_controller = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py")

    expected_action_keys = (
        "map_studio.terrain.sculpt_stroke",
        "map_studio.floor_plan.merge_rooms",
        "map_studio.floor_plan.bridge_edges",
        "map_studio.floor_plan.set_extrusion",
        "map_studio.floor_plan.triangulate_face",
        "map_studio.floor_plan.split_face",
        "map_studio.floor_plan.cleanup_normals",
        "map_studio.floor_plan.mirror_vertices",
        "map_studio.primitive.set_dimensions",
        "map_studio.primitive.set_style",
        "map_studio.primitive.remove",
        "map_studio.primitive.separate",
        "map_studio.room.set_style",
        "map_studio.gameplay.move_placement",
        "map_studio.gameplay.rename_placement",
        "map_studio.gameplay.duplicate_placement",
        "map_studio.gameplay.remove_placement",
        "map_studio.gameplay.edit_camera",
        "map_studio.gameplay.set_transition",
        "map_studio.lighting.move_room_light",
        "map_studio.lighting.edit_room_light",
        "map_studio.lighting.rename_room_light",
        "map_studio.lighting.duplicate_room_light",
        "map_studio.lighting.remove_room_light",
    )

    for source in (scene_controller, tools_controller):
        for action_key in expected_action_keys:
            assert f'action_key="{action_key}"' in source

        prepare_body = source.split("def prepare_map_studio_terrain_sculpt_frame", 1)[1].split(
            "def apply_map_studio_terrain_sculpt_frame", 1
        )[0]
        assert "_capture_map_studio_command_state" not in prepare_body
