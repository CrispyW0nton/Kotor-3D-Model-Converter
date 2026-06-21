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


def test_t2606_tool_action_dispatch_resolves_command_and_disabled_context() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        resolve_map_studio_tool_belt_action,
    )

    cube = resolve_map_studio_tool_belt_action("cube")

    assert cube.enabled is True
    assert cube.command_method == "add_authored_room_primitive"
    assert cube.command_kwargs["primitive_kind"] == "cube"
    assert cube.mutates_kmap is True
    assert cube.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "game proof" in cube.readiness_impact

    snap = resolve_map_studio_tool_belt_action("vertex_snap")

    assert snap.enabled is False
    assert "source point and a target point" in snap.disabled_reason
    assert snap.command_method == ""

    ready_snap = resolve_map_studio_tool_belt_action(
        "vertex_snap",
        MapStudioToolActionContext(
            room_resref="room_a",
            point_index=0,
            target_point_index=1,
            target_room_resref="room_b",
        ),
    )

    assert ready_snap.enabled is True
    assert ready_snap.command_method == "snap_authored_floor_plan_vertex"
    assert ready_snap.command_kwargs["target_room_resref"] == "room_b"

    extrude = resolve_map_studio_tool_belt_action(
        "extrude",
        MapStudioToolActionContext(room_resref="room_a", operation_distance=0.75, operation_edge_index=2),
    )

    assert extrude.enabled is True
    assert extrude.command_method == "apply_authored_room_operation"
    assert extrude.command_kwargs == {
        "operation": "edge_extrude",
        "room_resref": "room_a",
        "distance": 0.75,
        "edge_index": 2,
    }

    boolean = resolve_map_studio_tool_belt_action(
        "boolean",
        MapStudioToolActionContext(room_resref="room_a", cut_center=(1.0, 2.0), cut_size=(3.0, 4.0)),
    )

    assert boolean.enabled is True
    assert boolean.command_method == "apply_authored_room_operation"
    assert boolean.command_kwargs["operation"] == "rectangular_cut"
    assert boolean.command_kwargs["center"] == (1.0, 2.0)
    assert boolean.command_kwargs["size"] == (3.0, 4.0)

    slice_y = resolve_map_studio_tool_belt_action(
        "cut_slice_insert_edges",
        MapStudioToolActionContext(room_resref="room_a", axis="y", cut_center=(1.0, 2.0)),
    )

    assert slice_y.enabled is True
    assert slice_y.command_method == "apply_authored_room_operation"
    assert slice_y.command_kwargs == {
        "operation": "axis_split",
        "room_resref": "room_a",
        "axis": "y",
        "coordinate": 2.0,
    }

    edge_loop = resolve_map_studio_tool_belt_action(
        "insert_edge_loop",
        MapStudioToolActionContext(room_resref="room_a", axis="x", cut_center=(1.25, 2.5)),
    )

    assert edge_loop.enabled is True
    assert edge_loop.command_method == "apply_authored_room_operation"
    assert edge_loop.command_kwargs == {
        "operation": "axis_split",
        "room_resref": "room_a",
        "axis": "x",
        "coordinate": 1.25,
    }
    assert "KOTOR room/export boundaries" in edge_loop.authoring_context

    duplicate_missing = resolve_map_studio_tool_belt_action("duplicate_special")

    assert duplicate_missing.enabled is False
    assert "primitive selection" in duplicate_missing.disabled_reason

    duplicate = resolve_map_studio_tool_belt_action(
        "duplicate_special",
        MapStudioToolActionContext(
            room_resref="room_a",
            primitive_name="room_a_cube",
            duplicate_count=3,
            duplicate_translation_offset=(0.5, 0.25, 0.0),
            duplicate_rotation_offset_degrees_z=15.0,
            duplicate_scale_multiplier=(1.0, 1.0, 1.2),
        ),
    )

    assert duplicate.enabled is True
    assert duplicate.command_method == "duplicate_authored_room_primitive"
    assert duplicate.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_cube",
        "duplicate_count": 3,
        "translation_offset": (0.5, 0.25, 0.0),
        "rotation_offset_degrees_z": 15.0,
        "scale_multiplier": (1.0, 1.0, 1.2),
    }
    assert duplicate.mutates_kmap is True

    soften = resolve_map_studio_tool_belt_action(
        "soften_edges",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_wall", metadata={"edge_indices": (1, 2)}),
    )

    assert soften.enabled is True
    assert soften.command_method == "set_authored_room_edge_normal_policy"
    assert soften.command_kwargs == {
        "room_resref": "room_a",
        "policy": "soft",
        "primitive_name": "room_a_wall",
        "edge_indices": (1, 2),
    }
    assert soften.mutates_kmap is True
    assert "WOK traversal remains validated separately" in soften.authoring_context

    harden = resolve_map_studio_tool_belt_action(
        "harden_edges",
        MapStudioToolActionContext(room_resref="room_a"),
    )

    assert harden.enabled is True
    assert harden.command_method == "set_authored_room_edge_normal_policy"
    assert harden.command_kwargs["policy"] == "hard"


def test_t2606_tool_action_dispatch_executes_headless_command_and_records_undo() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grbelt01", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grbelt01")

    before_count = len(controller.authored_room_primitive_transforms())

    execute_map_studio_tool_belt_action(controller, "cube")

    after = controller.authored_room_primitive_transforms()
    assert len(after) == before_count + 1
    assert after[-1].primitive_type == "cube"
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Add cube primitive"

    undo = controller.undo_map_studio_command()

    assert undo is not None
    assert len(controller.authored_room_primitive_transforms()) == before_count

    controller.create_authored_room_preset_module(preset_id="octagonal_room", module_root="grbevel01")
    room_before = controller.authored_floor_plan_room_choices()[0]
    execute_map_studio_tool_belt_action(
        controller,
        "bevel",
        MapStudioToolActionContext(room_resref=room_before.room_resref, operation_distance=0.1),
    )
    room_after = controller.authored_floor_plan_room_choices()[0]

    assert room_after.point_count > room_before.point_count
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Apply room operation bevel"

    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grdupsp")
    primitive_before = controller.authored_room_primitive_transforms()[0]
    count_before = len(controller.authored_room_primitive_transforms())

    execute_map_studio_tool_belt_action(
        controller,
        "duplicate_special",
        MapStudioToolActionContext(
            room_resref=primitive_before.room_resref,
            primitive_name=primitive_before.primitive_name,
            duplicate_count=2,
            duplicate_translation_offset=(0.5, 0.0, 0.0),
        ),
    )

    duplicated = controller.authored_room_primitive_transforms()
    duplicate_names = {item.primitive_name for item in duplicated}
    first_duplicate = next(item for item in duplicated if item.primitive_name == f"{primitive_before.primitive_name}_dup_01"[:32])
    second_duplicate = next(item for item in duplicated if item.primitive_name == f"{primitive_before.primitive_name}_dup_02"[:32])

    assert len(duplicated) == count_before + 2
    assert f"{primitive_before.primitive_name}_dup_01"[:32] in duplicate_names
    assert f"{primitive_before.primitive_name}_dup_02"[:32] in duplicate_names
    assert first_duplicate.primitive_type == primitive_before.primitive_type
    assert first_duplicate.translation[0] == primitive_before.translation[0] + 0.5
    assert second_duplicate.translation[0] == primitive_before.translation[0] + 1.0
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == f"Duplicate primitive {primitive_before.primitive_name}"

    controller.undo_map_studio_command()

    assert len(controller.authored_room_primitive_transforms()) == count_before

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="gredge01")
    room_before_split = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "insert_edge_loop",
        MapStudioToolActionContext(
            room_resref=room_before_split.room_resref,
            axis="x",
            cut_center=(0.0, 0.0),
        ),
    )

    split_rooms = controller.authored_floor_plan_room_choices()

    assert len(split_rooms) == 2
    assert {room.room_resref for room in split_rooms} == {"gredge01_room_l1", "gredge01_room_r2"}
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Apply room operation axis_split"

    controller.undo_map_studio_command()

    restored_rooms = controller.authored_floor_plan_room_choices()
    assert len(restored_rooms) == 1
    assert restored_rooms[0].room_resref == room_before_split.room_resref

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grnorm01")
    room_for_normals = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "soften_edges",
        MapStudioToolActionContext(room_resref=room_for_normals.room_resref, metadata={"edge_indices": (0, 1)}),
    )

    authored_payload = controller.project.extra_sections["authored_module"]
    room_payload = authored_payload["rooms"][0]
    primitive_metadata = room_payload["primitive"]["metadata"]

    assert primitive_metadata["edge_normal_policy"] == "soft"
    assert primitive_metadata["edge_normal_policy_operation"] == "soften_edges"
    assert primitive_metadata["edge_normal_policy_scope"] == "selected_edges"
    assert primitive_metadata["edge_normal_policy_edges"] == [0, 1]
    assert room_payload["metadata"]["edge_normal_policy"] == "soft"
    assert controller.command_history.undo_label == "Soften edges"

    controller.undo_map_studio_command()

    restored_payload = controller.project.extra_sections["authored_module"]
    restored_metadata = restored_payload["rooms"][0]["primitive"]["metadata"]
    assert "edge_normal_policy" not in restored_metadata

    execute_map_studio_tool_belt_action(
        controller,
        "harden_edges",
        MapStudioToolActionContext(room_resref=room_for_normals.room_resref),
    )

    hard_payload = controller.project.extra_sections["authored_module"]
    hard_metadata = hard_payload["rooms"][0]["primitive"]["metadata"]
    assert hard_metadata["edge_normal_policy"] == "hard"
    assert hard_metadata["edge_normal_policy_operation"] == "harden_edges"
    assert controller.command_history.undo_label == "Harden edges"


def test_t2606_level_editor_routes_tool_belt_actions_through_core_dispatcher() -> None:
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    scene_dispatcher = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    tools_dispatcher = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    scene_catalog = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_modeling_tools.py")
    tools_catalog = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_modeling_tools.py")

    assert "from src.core.modules.map_studio_tool_action_dispatch import" in window_source
    assert "resolve_map_studio_tool_belt_action(key, route_context)" in window_source
    assert "execute_map_studio_tool_belt_action(self.controller, action_key, context)" in window_source
    assert '"duplicate_special",' in window_source
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in scene_catalog
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in tools_catalog

    for source in (scene_dispatcher, tools_dispatcher):
        assert "class MapStudioToolActionContext" in source
        assert "class MapStudioToolActionRoute" in source
        assert "def resolve_map_studio_tool_belt_action" in source
        assert "def execute_map_studio_tool_belt_action" in source
        assert 'command_method="add_authored_room_primitive"' in source
        assert 'command_method="snap_authored_floor_plan_vertex"' in source
        assert 'command_method="apply_authored_room_operation"' in source
        assert 'command_method="duplicate_authored_room_primitive"' in source
        assert 'command_method="set_authored_room_edge_normal_policy"' in source
        assert '"insert_edge_loop"' in source
