from __future__ import annotations

import copy
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


def test_t2606_tool_contract_audit_classifies_visible_tool_belt_actions() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_contract_audit import audit_map_studio_tool_belt_contract
    from src.core.modules.module_editor_controller import ModuleEditorController

    audit = audit_map_studio_tool_belt_contract()
    statuses = {status.action_key: status for status in audit.statuses}

    assert audit.capability_stage == "previewable_tool_contract_audit"
    assert audit.has_blockers is False
    assert audit.blocking_messages == ()
    assert audit.total_actions >= 80
    assert audit.implemented_actions == audit.total_actions
    assert audit.command_backed_actions >= 67
    assert audit.mutating_command_actions >= 66
    assert audit.query_command_actions >= 1
    assert audit.workflow_focus_actions <= 10
    assert statuses["cube"].contract_kind == "command_mutates_kmap"
    assert statuses["cube"].command_method == "add_authored_room_primitive"
    assert statuses["cube"].mutates_kmap is True
    assert statuses["universal_transform"].contract_kind == "command_query"
    assert statuses["universal_transform"].command_method == "map_studio_universal_transform_overlay"
    assert statuses["placeable"].contract_kind == "command_mutates_kmap"
    assert statuses["placeable"].command_method == "add_authored_gameplay_placement"
    assert statuses["entry_point"].contract_kind == "command_mutates_kmap"
    assert statuses["entry_point"].command_method == "set_authored_module_entry_point"
    assert statuses["opening"].contract_kind == "command_mutates_kmap"
    assert statuses["opening"].command_method == "apply_authored_room_operation"
    assert statuses["opening_marker"].contract_kind == "command_mutates_kmap"
    assert statuses["opening_marker"].command_method == "apply_authored_room_operation"
    assert statuses["sculpt_raise"].contract_kind == "command_mutates_kmap"
    assert statuses["sculpt_raise"].command_method == "apply_authored_terrain_operation"
    assert statuses["terrain"].contract_kind == "workflow_focus"
    assert statuses["stage_module"].contract_kind == "studio_workspace"
    assert all(status.in_any_preset for status in audit.statuses)

    controller_audit = ModuleEditorController().map_studio_tool_belt_contract_audit()
    assert controller_audit.total_actions == audit.total_actions
    assert controller_audit.blocking_messages == ()


def test_t2606_tool_action_dispatch_resolves_command_and_disabled_context() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        resolve_map_studio_tool_belt_action,
    )
    from src.core.modules.map_studio_modeling_tools import available_map_studio_modeling_tools

    cube = resolve_map_studio_tool_belt_action("cube")
    tool_by_key = {tool.key: tool for tool in available_map_studio_modeling_tools()}

    assert cube.enabled is True
    assert cube.command_method == "add_authored_room_primitive"
    assert cube.command_kwargs["primitive_kind"] == "cube"
    assert cube.mutates_kmap is True
    assert cube.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "game proof" in cube.readiness_impact

    universal_missing = resolve_map_studio_tool_belt_action("universal_transform")

    assert universal_missing.enabled is False
    assert "selected authored room primitive" in universal_missing.disabled_reason

    universal_ready = resolve_map_studio_tool_belt_action(
        "universal_transform",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_cube"),
    )

    assert universal_ready.enabled is True
    assert universal_ready.command_method == "map_studio_universal_transform_overlay"
    assert universal_ready.command_kwargs == {"room_resref": "room_a", "primitive_name": "room_a_cube"}
    assert universal_ready.mutates_kmap is False
    assert universal_ready.stale_outputs == ()
    assert "transform handles" in universal_ready.authoring_context

    placeable_route = resolve_map_studio_tool_belt_action(
        "placeable",
        MapStudioToolActionContext(
            placement_kind="placeable",
            placement_template_resref="plc_bench",
            placement_tag="map_bench",
            placement_position=(2.0, 1.0, 0.0),
            placement_bearing=90.0,
        ),
    )

    assert placeable_route.enabled is True
    assert placeable_route.command_method == "add_authored_gameplay_placement"
    assert placeable_route.command_kwargs == {
        "kind": "placeable",
        "template_resref": "plc_bench",
        "tag": "map_bench",
        "position": (2.0, 1.0, 0.0),
        "bearing": 90.0,
    }
    assert placeable_route.mutates_kmap is True
    assert "authored GIT/IFO state" in placeable_route.authoring_context

    terrain_raise = resolve_map_studio_tool_belt_action(
        "sculpt_raise",
        MapStudioToolActionContext(
            room_resref="terrain01",
            terrain_row_index=1,
            terrain_column_index=2,
            terrain_delta=0.25,
            terrain_radius=1,
            terrain_height=0.5,
            terrain_iterations=2,
            terrain_strength=0.75,
        ),
    )

    assert terrain_raise.enabled is True
    assert terrain_raise.command_method == "apply_authored_terrain_operation"
    assert terrain_raise.command_kwargs == {
        "operation": "brush_stroke:raise",
        "room_resref": "terrain01",
        "row_index": 1,
        "column_index": 2,
        "points": ((1, 2, 1.0),),
        "delta": 0.25,
        "radius": 1,
        "height": 0.5,
        "iterations": 2,
        "strength": 0.75,
        "preserve_boundary": True,
    }
    assert terrain_raise.mutates_kmap is True
    assert terrain_raise.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "dirty-region scoped heightfield stroke" in terrain_raise.authoring_context

    terrain_missing = resolve_map_studio_tool_belt_action("sculpt_lower")

    assert terrain_missing.enabled is False
    assert "selected authored terrain room" in terrain_missing.disabled_reason

    creature_route = resolve_map_studio_tool_belt_action(
        "creature",
        MapStudioToolActionContext(
            placement_kind="placeable",
            placement_template_resref="plc_bench",
            placement_position=(0.0, 0.0, 0.0),
        ),
    )

    assert creature_route.command_method == "add_authored_gameplay_placement"
    assert creature_route.command_kwargs["kind"] == "creature"
    assert creature_route.command_kwargs["template_resref"] == "c_drdmkone"

    entry_point_route = resolve_map_studio_tool_belt_action(
        "entry_point",
        MapStudioToolActionContext(
            entry_area_resref="grentry01",
            entry_position=(0.5, -2.0, 0.0),
            entry_facing=180.0,
        ),
    )

    assert entry_point_route.enabled is True
    assert entry_point_route.command_method == "set_authored_module_entry_point"
    assert entry_point_route.command_kwargs == {
        "area_resref": "grentry01",
        "position": (0.5, -2.0, 0.0),
        "facing": 180.0,
    }
    assert entry_point_route.mutates_kmap is True
    assert "IFO player start" in entry_point_route.authoring_context

    opening_missing = resolve_map_studio_tool_belt_action("opening")

    assert opening_missing.enabled is False
    assert "selected authored floor-plan room" in opening_missing.disabled_reason

    opening_route = resolve_map_studio_tool_belt_action(
        "opening",
        MapStudioToolActionContext(
            room_resref="room_a",
            wall_opening_name="south_door",
            wall_opening_edge_index=0,
            wall_opening_center_fraction=0.5,
            wall_opening_width=1.5,
            wall_opening_height=2.0,
            wall_opening_bottom=0.0,
        ),
    )

    assert opening_route.enabled is True
    assert opening_route.command_method == "apply_authored_room_operation"
    assert opening_route.command_kwargs == {
        "operation": "wall_opening",
        "room_resref": "room_a",
        "name": "south_door",
        "edge_index": 0,
        "center_fraction": 0.5,
        "width": 1.5,
        "height": 2.0,
        "bottom": 0.0,
    }
    assert opening_route.mutates_kmap is True
    assert "cut a named doorway/window opening" in opening_route.authoring_context

    opening_marker_missing = resolve_map_studio_tool_belt_action("opening_marker")

    assert opening_marker_missing.enabled is False
    assert "authored wall opening selected" in opening_marker_missing.disabled_reason

    opening_marker_route = resolve_map_studio_tool_belt_action(
        "opening_marker",
        MapStudioToolActionContext(
            room_resref="room_a",
            opening_name="south_door",
            opening_marker_kind="trigger",
            opening_marker_template_resref="trg_exit",
            opening_marker_tag="south_exit_trigger",
            opening_marker_linked_to="wp_dest",
            opening_marker_linked_to_module="grnext01",
            opening_marker_transition_destination=2,
        ),
    )

    assert opening_marker_route.enabled is True
    assert opening_marker_route.command_method == "apply_authored_room_operation"
    assert opening_marker_route.command_kwargs == {
        "operation": "opening_transition_marker",
        "room_resref": "room_a",
        "opening_name": "south_door",
        "marker_kind": "trigger",
        "template_resref": "trg_exit",
        "tag": "south_exit_trigger",
        "linked_to": "wp_dest",
        "linked_to_module": "grnext01",
        "transition_destination": 2,
    }
    assert opening_marker_route.mutates_kmap is True
    assert "KOTOR door, trigger, or waypoint transition data" in opening_marker_route.authoring_context

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

    boolean_diff_missing = resolve_map_studio_tool_belt_action("boolean_a_minus_b")

    assert boolean_diff_missing.enabled is False
    assert "two selected rectangular floor-plan rooms" in boolean_diff_missing.disabled_reason

    boolean_a_minus_b = resolve_map_studio_tool_belt_action(
        "boolean_a_minus_b",
        MapStudioToolActionContext(
            first_room_resref="room_a",
            second_room_resref="room_b",
            result_room_resref="bool_out",
        ),
    )

    assert boolean_a_minus_b.enabled is True
    assert boolean_a_minus_b.command_method == "apply_authored_room_operation"
    assert boolean_a_minus_b.command_kwargs == {
        "operation": "boolean_difference",
        "first_room_resref": "room_a",
        "second_room_resref": "room_b",
        "result_room_resref": "bool_out",
    }
    assert "consume the cutter operand" in boolean_a_minus_b.authoring_context

    boolean_b_minus_a = resolve_map_studio_tool_belt_action(
        "boolean_b_minus_a",
        MapStudioToolActionContext(first_room_resref="room_a", second_room_resref="room_b"),
    )

    assert boolean_b_minus_a.enabled is True
    assert boolean_b_minus_a.command_kwargs["first_room_resref"] == "room_b"
    assert boolean_b_minus_a.command_kwargs["second_room_resref"] == "room_a"

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
    assert tool_by_key["soften_edges"].implemented is True
    assert tool_by_key["harden_edges"].implemented is True

    mirror_z = resolve_map_studio_tool_belt_action(
        "mirror_z",
        MapStudioToolActionContext(room_resref="terrain01", metadata={"center_height": 0.25}),
    )

    assert mirror_z.enabled is True
    assert mirror_z.command_method == "apply_authored_terrain_operation"
    assert mirror_z.command_kwargs == {"operation": "mirror_z", "room_resref": "terrain01", "center_height": 0.25}
    assert mirror_z.mutates_kmap is True
    assert "horizontal Z plane" in mirror_z.authoring_context
    assert "Arbitrary mesh/component Z mirroring remains planned" in mirror_z.authoring_context
    assert tool_by_key["mirror_z"].implemented is True

    bend = resolve_map_studio_tool_belt_action(
        "bend_tool",
        MapStudioToolActionContext(
            room_resref="terrain01",
            axis="y",
            operation_distance=0.4,
            metadata={"center": 0.0, "span": 4.0},
        ),
    )

    assert bend.enabled is True
    assert bend.command_method == "apply_authored_terrain_operation"
    assert bend.command_kwargs == {
        "operation": "bend",
        "room_resref": "terrain01",
        "axis": "y",
        "amplitude": 0.4,
        "center": 0.0,
        "span": 4.0,
    }
    assert bend.mutates_kmap is True
    assert "height profile" in bend.authoring_context
    assert "Arbitrary mesh/component bending remains planned" in bend.authoring_context
    assert tool_by_key["bend_tool"].implemented is True

    lattice = resolve_map_studio_tool_belt_action(
        "lattice",
        MapStudioToolActionContext(
            room_resref="terrain01",
            operation_distance=0.3,
            metadata={
                "control_deltas": ((0.0, 0.0), (0.0, 0.6)),
                "strength": 0.5,
            },
        ),
    )

    assert lattice.enabled is True
    assert lattice.command_method == "apply_authored_terrain_operation"
    assert lattice.command_kwargs == {
        "operation": "lattice",
        "room_resref": "terrain01",
        "strength": 0.5,
        "control_deltas": ((0.0, 0.0), (0.0, 0.6)),
    }
    assert lattice.mutates_kmap is True
    assert "heightfield control cage" in lattice.authoring_context
    assert "Arbitrary mesh/object lattice deformation remains planned" in lattice.authoring_context
    assert tool_by_key["lattice"].implemented is True

    curve = resolve_map_studio_tool_belt_action(
        "curve_tool",
        MapStudioToolActionContext(
            room_resref="room_a",
            operation_distance=0.5,
            metadata={
                "curve_name": "main_path",
                "curve_purpose": "pth_planning",
                "points": ((0.0, 0.0, 0.0), (1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
            },
        ),
    )

    assert curve.enabled is True
    assert curve.command_method == "add_authored_curve_guide"
    assert curve.command_kwargs == {
        "name": "main_path",
        "points": ((0.0, 0.0, 0.0), (1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
        "purpose": "pth_planning",
        "room_resref": "room_a",
        "coordinate_space": "kmap_world",
        "metadata": {"source_action": "curve_tool"},
    }
    assert curve.mutates_kmap is True
    assert "previewable guide data" in curve.authoring_context
    assert tool_by_key["curve_tool"].implemented is True

    shrink_wrap = resolve_map_studio_tool_belt_action(
        "shrink_wrap",
        MapStudioToolActionContext(room_resref="terrain01"),
    )

    assert shrink_wrap.enabled is True
    assert shrink_wrap.command_method == "apply_authored_terrain_operation"
    assert shrink_wrap.command_kwargs == {"operation": "shrink_wrap", "room_resref": "terrain01"}
    assert shrink_wrap.mutates_kmap is True
    assert "gameplay placements" in shrink_wrap.authoring_context
    assert "arbitrary mesh/walkmesh shrink-wrap remains planned" in shrink_wrap.authoring_context


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

    universal = execute_map_studio_tool_belt_action(
        controller,
        "universal_transform",
        MapStudioToolActionContext(
            room_resref=after[-1].room_resref,
            primitive_name=after[-1].primitive_name,
        ),
    )

    assert universal.primitive_name == after[-1].primitive_name
    assert universal.primitive_type == "cube"
    assert universal.coordinate_space == "kmap_world"
    assert universal.dimensions == (1.0, 1.0, 1.0)
    assert universal.center == (0.0, 0.0, 0.5)
    assert len(universal.corner_points) == 8
    assert len(universal.edge_lines) == 12
    assert {label.key for label in universal.dimension_labels} == {"width", "depth", "height"}
    assert {handle.key for handle in universal.handles} >= {"center", "axis_x", "axis_y", "axis_z"}
    assert universal.metadata["source"] == "map_studio:universal_transform_overlay"
    assert universal.metadata["capability_stage"] == "previewable_overlay"
    assert universal.vertex_count == 8
    assert universal.face_count == 12
    assert universal.committed_edit_stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "validation" in universal.readiness_impact
    assert controller.command_history.undo_label == "Add cube primitive"

    undo = controller.undo_map_studio_command()

    assert undo is not None
    assert len(controller.authored_room_primitive_transforms()) == before_count

    execute_map_studio_tool_belt_action(
        controller,
        "placeable",
        MapStudioToolActionContext(
            placement_kind="placeable",
            placement_template_resref="plc_bench",
            placement_tag="belt_bench",
            placement_position=(1.25, 1.5, 0.0),
            placement_bearing=45.0,
        ),
    )

    placement_payload = controller.project.extra_sections["authored_module"]["placements"]
    assert placement_payload["placeables"][-1]["template_resref"] == "plc_bench"
    assert placement_payload["placeables"][-1]["tag"] == "belt_bench"
    assert placement_payload["placeables"][-1]["position"] == [1.25, 1.5, 0.0]
    assert controller.command_history.undo_label == "Add placeable placement belt_bench"

    controller.undo_map_studio_command()

    restored_placement_payload = controller.project.extra_sections["authored_module"]["placements"]
    assert all(row.get("tag") != "belt_bench" for row in restored_placement_payload["placeables"])

    execute_map_studio_tool_belt_action(
        controller,
        "entry_point",
        MapStudioToolActionContext(
            entry_area_resref="grbelt01",
            entry_position=(0.0, -1.75, 0.0),
            entry_facing=90.0,
        ),
    )

    entry_payload = controller.project.extra_sections["authored_module"]["placements"]["entry_point"]
    assert entry_payload["area_resref"] == "grbelt01"
    assert entry_payload["position"] == [0.0, -1.75, 0.0]
    assert entry_payload["facing"] == 90.0
    assert controller.command_history.undo_label == "Set entry point grbelt01"

    controller.undo_map_studio_command()

    restored_entry = controller.project.extra_sections["authored_module"]["placements"]["entry_point"]
    assert restored_entry["position"] != [0.0, -1.75, 0.0]

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="gropmk01")
    opening_room = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "opening",
        MapStudioToolActionContext(
            room_resref=opening_room.room_resref,
            wall_opening_name="south_door",
            wall_opening_edge_index=0,
            wall_opening_center_fraction=0.5,
            wall_opening_width=1.5,
            wall_opening_height=2.0,
            wall_opening_bottom=0.0,
        ),
    )

    opening_payload = controller.project.extra_sections["authored_module"]
    opening_primitive = opening_payload["rooms"][0]["primitive"]
    assert opening_primitive["openings"][-1]["name"] == "south_door"
    assert opening_primitive["openings"][-1]["edge_index"] == 0
    assert opening_primitive["metadata"]["last_operation"] == "set_wall_opening"
    assert controller.command_history.undo_label == "Apply room operation wall_opening"

    execute_map_studio_tool_belt_action(
        controller,
        "opening_marker",
        MapStudioToolActionContext(
            room_resref=opening_room.room_resref,
            opening_name="south_door",
            opening_marker_kind="trigger",
            opening_marker_template_resref="trg_exit",
            opening_marker_tag="south_exit_trigger",
            opening_marker_linked_to="wp_dest",
            opening_marker_linked_to_module="grnext01",
            opening_marker_transition_destination=2,
        ),
    )

    marker_payload = controller.project.extra_sections["authored_module"]
    marker_trigger = marker_payload["placements"]["triggers"][-1]
    marker_metadata = marker_payload["extra"]["last_opening_transition_marker"]

    assert marker_trigger["template_resref"] == "trg_exit"
    assert marker_trigger["tag"] == "south_exit_trigger"
    assert marker_trigger["linked_to"] == "wp_dest"
    assert marker_trigger["linked_to_module"] == "grnext01"
    assert marker_trigger["transition_destination"] == 2
    assert marker_metadata["opening_name"] == "south_door"
    assert marker_metadata["marker_kind"] == "trigger"
    assert marker_metadata["transition_destination"] == 2
    assert controller.command_history.undo_label == "Apply room operation opening_transition_marker"

    controller.undo_map_studio_command()

    restored_marker_payload = controller.project.extra_sections["authored_module"]
    assert all(row.get("tag") != "south_exit_trigger" for row in restored_marker_payload["placements"]["triggers"])

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

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grbool01")
    boolean_payload = controller.project.extra_sections["authored_module"]
    base_room = boolean_payload["rooms"][0]
    cutter_room = copy.deepcopy(base_room)
    cutter_room["room_resref"] = "grbool01_cut"
    cutter_room["primitive"]["room_resref"] = "grbool01_cut"
    cutter_room["primitive"]["points"] = [
        [-1.0, -1.0],
        [1.0, -1.0],
        [1.0, 1.0],
        [-1.0, 1.0],
    ]
    cutter_room["primitive"]["metadata"] = {
        **dict(cutter_room["primitive"].get("metadata", {})),
        "source": "test:boolean_cutter",
        "shape": "rectangle_cutter",
    }
    cutter_room["metadata"] = {
        **dict(cutter_room.get("metadata", {})),
        "source": "test:boolean_cutter",
        "primitive": "floor_plan_extrusion",
    }
    boolean_payload["rooms"] = [base_room, cutter_room]
    for room in boolean_payload["rooms"]:
        room["visible_rooms"] = ["grbool01_room01", "grbool01_cut"]
    controller.project.extra_sections["authored_module"] = boolean_payload

    execute_map_studio_tool_belt_action(
        controller,
        "boolean_a_minus_b",
        MapStudioToolActionContext(
            first_room_resref="grbool01_room01",
            second_room_resref="grbool01_cut",
            result_room_resref="grboolout",
        ),
    )

    boolean_rooms = controller.authored_floor_plan_room_choices()
    boolean_room_names = {room.room_resref for room in boolean_rooms}
    boolean_payload_after = controller.project.extra_sections["authored_module"]

    assert len(boolean_rooms) == 4
    assert boolean_room_names == {"grboolout_l1", "grboolout_r2", "grboolout_b3", "grboolout_t4"}
    assert "grbool01_cut" not in boolean_room_names
    assert boolean_payload_after["rooms"][0]["primitive"]["metadata"]["operation"] == "boolean_difference"
    assert boolean_payload_after["rooms"][0]["primitive"]["metadata"]["boolean_cutter_consumed"] is True
    assert boolean_payload_after["rooms"][0]["primitive"]["metadata"]["boolean_cutter_room_resref"] == "grbool01_cut"
    assert controller.command_history.undo_label == "Apply room operation boolean_difference"

    controller.undo_map_studio_command()

    restored_boolean_rooms = controller.authored_floor_plan_room_choices()
    assert {room.room_resref for room in restored_boolean_rooms} == {"grbool01_room01", "grbool01_cut"}

    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grwrap01")
    terrain_room = controller.authored_terrain_room_choices()[0]
    terrain_payload = controller.project.extra_sections["authored_module"]
    entry_position = list(terrain_payload["placements"]["entry_point"]["position"])
    placeable_position = list(terrain_payload["placements"]["placeables"][0]["position"])
    waypoint_position = list(terrain_payload["placements"]["waypoints"][0]["position"])
    terrain_payload["placements"]["entry_point"]["position"] = [entry_position[0], entry_position[1], 9.0]
    terrain_payload["placements"]["placeables"][0]["position"] = [placeable_position[0], placeable_position[1], -7.0]
    terrain_payload["placements"]["waypoints"][0]["position"] = [waypoint_position[0], waypoint_position[1], 8.0]
    controller.project.extra_sections["authored_module"] = terrain_payload

    execute_map_studio_tool_belt_action(
        controller,
        "shrink_wrap",
        MapStudioToolActionContext(room_resref=terrain_room.room_resref),
    )

    wrapped_payload = controller.project.extra_sections["authored_module"]
    wrapped_placements = wrapped_payload["placements"]
    wrapped_room = wrapped_payload["rooms"][0]

    assert wrapped_placements["entry_point"]["position"] == entry_position
    assert wrapped_placements["placeables"][0]["position"] == placeable_position
    assert wrapped_placements["waypoints"][0]["position"] == waypoint_position
    assert wrapped_placements["metadata"]["terrain_height_repaired_after_operation"] == "terrain_shrink_wrap"
    assert wrapped_room["primitive"]["metadata"]["last_operation"] == "terrain_shrink_wrap"
    assert wrapped_room["primitive"]["metadata"]["shrink_wrap_target"] == "authored_gameplay_placements"
    assert wrapped_room["metadata"]["shrink_wrap_surface"] == "terrain_heightfield"
    assert controller.command_history.undo_label == "Apply terrain operation shrink_wrap"

    controller.undo_map_studio_command()

    restored_terrain_payload = controller.project.extra_sections["authored_module"]
    restored_placements = restored_terrain_payload["placements"]
    assert restored_placements["entry_point"]["position"][2] == 9.0
    assert restored_placements["placeables"][0]["position"][2] == -7.0
    assert restored_placements["waypoints"][0]["position"][2] == 8.0

    source_terrain_heights = copy.deepcopy(restored_terrain_payload["rooms"][0]["primitive"]["heights"])

    execute_map_studio_tool_belt_action(
        controller,
        "sculpt_raise",
        MapStudioToolActionContext(
            room_resref=terrain_room.room_resref,
            terrain_row_index=1,
            terrain_column_index=1,
            terrain_delta=0.25,
            terrain_radius=0,
            terrain_points=((1, 1, 1.0),),
        ),
    )

    brushed_payload = controller.project.extra_sections["authored_module"]
    brushed_room = brushed_payload["rooms"][0]
    brushed_heights = brushed_room["primitive"]["heights"]

    assert round(float(brushed_heights[1][1]), 6) == round(float(source_terrain_heights[1][1]) + 0.25, 6)
    assert brushed_room["primitive"]["metadata"]["last_brush"] == "raise"
    assert brushed_room["primitive"]["metadata"]["last_dirty_region"]["changed_sample_count"] == 1
    assert brushed_room["primitive"]["metadata"]["dirty_region_only"] is True
    assert brushed_room["primitive"]["metadata"]["source"] == "map_studio:terrain_brush_stroke"
    assert brushed_room["metadata"]["last_operation"] == "terrain_brush_stroke"
    assert controller.command_history.undo_label == "Apply terrain operation brush_stroke:raise"

    controller.undo_map_studio_command()

    restored_brush_payload = controller.project.extra_sections["authored_module"]
    assert restored_brush_payload["rooms"][0]["primitive"]["heights"] == source_terrain_heights

    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grmirz01")
    mirror_room = controller.authored_terrain_room_choices()[0]
    mirror_payload = controller.project.extra_sections["authored_module"]
    mirror_heights = [list(row) for row in mirror_payload["rooms"][0]["primitive"]["heights"]]
    mirror_heights[0][0] = 0.0
    mirror_heights[2][2] = 0.6
    mirror_payload["rooms"][0]["primitive"]["heights"] = mirror_heights
    controller.project.extra_sections["authored_module"] = mirror_payload

    execute_map_studio_tool_belt_action(
        controller,
        "mirror_z",
        MapStudioToolActionContext(room_resref=mirror_room.room_resref, metadata={"center_height": 0.3}),
    )

    mirrored_payload = controller.project.extra_sections["authored_module"]
    mirrored_room = mirrored_payload["rooms"][0]
    mirrored_heights = mirrored_room["primitive"]["heights"]

    assert mirrored_heights[0][0] == 0.6
    assert mirrored_heights[2][2] == 0.0
    assert mirrored_room["primitive"]["metadata"]["last_operation"] == "mirror_z"
    assert mirrored_room["primitive"]["metadata"]["mirror_axis"] == "z"
    assert mirrored_room["primitive"]["metadata"]["mirror_center_height"] == 0.3
    assert mirrored_room["metadata"]["last_operation"] == "terrain_mirror_z"
    assert mirrored_payload["placements"]["metadata"]["terrain_height_repaired_after_operation"] == "terrain_mirror_z"
    assert controller.command_history.undo_label == "Apply terrain operation mirror_z"

    controller.undo_map_studio_command()

    restored_mirror_payload = controller.project.extra_sections["authored_module"]
    restored_heights = restored_mirror_payload["rooms"][0]["primitive"]["heights"]
    assert restored_heights[0][0] == 0.0
    assert restored_heights[2][2] == 0.6

    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grbend01")
    bend_room = controller.authored_terrain_room_choices()[0]
    bend_payload = controller.project.extra_sections["authored_module"]
    source_bend_heights = [[0.0 for _column in row] for row in bend_payload["rooms"][0]["primitive"]["heights"]]
    bend_payload["rooms"][0]["primitive"]["heights"] = copy.deepcopy(source_bend_heights)
    controller.project.extra_sections["authored_module"] = bend_payload

    execute_map_studio_tool_belt_action(
        controller,
        "bend_tool",
        MapStudioToolActionContext(room_resref=bend_room.room_resref, axis="x", operation_distance=0.4),
    )

    bent_payload = controller.project.extra_sections["authored_module"]
    bent_room = bent_payload["rooms"][0]
    bent_heights = bent_room["primitive"]["heights"]
    bent_values = [round(float(value), 6) for row in bent_heights for value in row]

    assert max(bent_values) == 0.4
    assert round(float(bent_heights[0][0]), 6) == 0.0
    assert round(float(bent_heights[-1][-1]), 6) == 0.0
    assert bent_room["primitive"]["metadata"]["last_operation"] == "bend"
    assert bent_room["primitive"]["metadata"]["bend_axis"] == "x"
    assert bent_room["primitive"]["metadata"]["bend_amplitude"] == 0.4
    assert bent_room["primitive"]["metadata"]["source"] == "map_studio:terrain_bend"
    assert "bend_slope_report" in bent_room["primitive"]["metadata"]
    assert bent_room["metadata"]["last_operation"] == "terrain_bend"
    assert bent_payload["placements"]["metadata"]["terrain_height_repaired_after_operation"] == "terrain_bend"
    assert controller.command_history.undo_label == "Apply terrain operation bend"

    controller.undo_map_studio_command()

    restored_bend_payload = controller.project.extra_sections["authored_module"]
    assert restored_bend_payload["rooms"][0]["primitive"]["heights"] == source_bend_heights

    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grlattice")
    lattice_room = controller.authored_terrain_room_choices()[0]
    lattice_payload = controller.project.extra_sections["authored_module"]
    source_lattice_heights = [[0.0 for _column in row] for row in lattice_payload["rooms"][0]["primitive"]["heights"]]
    lattice_payload["rooms"][0]["primitive"]["heights"] = copy.deepcopy(source_lattice_heights)
    controller.project.extra_sections["authored_module"] = lattice_payload

    execute_map_studio_tool_belt_action(
        controller,
        "lattice",
        MapStudioToolActionContext(
            room_resref=lattice_room.room_resref,
            metadata={
                "control_deltas": ((0.0, 0.0), (0.0, 0.6)),
                "strength": 0.5,
            },
        ),
    )

    latticed_payload = controller.project.extra_sections["authored_module"]
    latticed_room = latticed_payload["rooms"][0]
    latticed_heights = latticed_room["primitive"]["heights"]
    latticed_values = [round(float(value), 6) for row in latticed_heights for value in row]

    assert max(latticed_values) == 0.3
    assert round(float(latticed_heights[0][0]), 6) == 0.0
    assert round(float(latticed_heights[-1][-1]), 6) == 0.3
    assert latticed_room["primitive"]["metadata"]["last_operation"] == "lattice"
    assert latticed_room["primitive"]["metadata"]["lattice_mode"] == "terrain_heightfield_control_cage"
    assert latticed_room["primitive"]["metadata"]["lattice_control_rows"] == 2
    assert latticed_room["primitive"]["metadata"]["lattice_control_columns"] == 2
    assert latticed_room["primitive"]["metadata"]["lattice_strength"] == 0.5
    assert latticed_room["primitive"]["metadata"]["source"] == "map_studio:terrain_lattice"
    assert latticed_room["primitive"]["metadata"]["arbitrary_mesh_lattice"] == "planned"
    assert "lattice_slope_report" in latticed_room["primitive"]["metadata"]
    assert latticed_room["metadata"]["last_operation"] == "terrain_lattice"
    assert latticed_payload["placements"]["metadata"]["terrain_height_repaired_after_operation"] == "terrain_lattice"
    assert controller.command_history.undo_label == "Apply terrain operation lattice"

    controller.undo_map_studio_command()

    restored_lattice_payload = controller.project.extra_sections["authored_module"]
    assert restored_lattice_payload["rooms"][0]["primitive"]["heights"] == source_lattice_heights

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grcurve01")
    curve_room = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "curve_tool",
        MapStudioToolActionContext(
            room_resref=curve_room.room_resref,
            metadata={
                "curve_name": "main_path",
                "curve_purpose": "terrain_ridge",
                "points": ((0.0, 0.0, 0.0), (1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
            },
        ),
    )

    curve_payload = controller.project.extra_sections["authored_module"]
    curve_guides = curve_payload["extra"]["map_studio_curve_guides"]
    curve_guide = curve_guides[0]

    assert len(curve_guides) == 1
    assert curve_payload["extra"]["last_curve_guide"] == "main_path"
    assert curve_payload["extra"]["last_map_studio_operation"] == "curve_guide"
    assert curve_guide["name"] == "main_path"
    assert curve_guide["purpose"] == "terrain_ridge"
    assert curve_guide["room_resref"] == curve_room.room_resref
    assert curve_guide["coordinate_space"] == "kmap_world"
    assert curve_guide["points"] == [[0.0, 0.0, 0.0], [1.0, 0.5, 0.0], [2.0, 0.5, 0.0]]
    assert curve_guide["metadata"]["source"] == "map_studio:curve_tool"
    assert curve_guide["metadata"]["export_state"] == "guide_only_not_runtime_geometry"
    assert controller.authored_curve_guides()[0].name == "main_path"
    assert controller.command_history.undo_label == "Add curve guide main_path"

    controller.undo_map_studio_command()

    restored_curve_payload = controller.project.extra_sections["authored_module"]
    assert "map_studio_curve_guides" not in restored_curve_payload.get("extra", {})


def test_t2606_level_editor_routes_tool_belt_actions_through_core_dispatcher() -> None:
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    scene_dispatcher = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    tools_dispatcher = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    scene_overlay = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_universal_transform_overlay.py")
    tools_overlay = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_universal_transform_overlay.py")
    scene_tool_audit = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_tool_contract_audit.py")
    tools_tool_audit = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_tool_contract_audit.py")
    scene_controller = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py")
    tools_controller = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py")
    viewport_panel = _read("native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py")
    viewport_scene_models = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/scene_models.py")
    viewport_overlay_layers = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py")
    viewport_rendering = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py")
    scene_catalog = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_modeling_tools.py")
    tools_catalog = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_modeling_tools.py")

    assert "from src.core.modules.map_studio_tool_action_dispatch import" in window_source
    assert "resolve_map_studio_tool_belt_action(key, route_context)" in window_source
    assert "execute_map_studio_tool_belt_action(self.controller, action_key, context)" in window_source
    assert "set_universal_transform_overlay" in window_source
    assert '"duplicate_special",' in window_source
    assert '"shrink_wrap",' in window_source
    assert '"opening_marker",' in window_source
    assert '"mirror_z",' in window_source
    assert '"bend_tool",' in window_source
    assert '"curve_tool",' in window_source
    assert '"lattice",' in window_source
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
        assert 'command_method="apply_authored_terrain_operation"' in source
        assert 'command_method="add_authored_curve_guide"' in source
        assert '"operation": "bend"' in source
        assert '"operation": "lattice"' in source
        assert '"curve_tool"' in source
        assert '"boolean_a_minus_b"' in source
        assert '"boolean_b_minus_a"' in source
        assert '"insert_edge_loop"' in source
        assert '"operation": "wall_opening"' in source
        assert '"operation": "opening_transition_marker"' in source
        assert 'command_method="map_studio_universal_transform_overlay"' in source

    for source in (scene_overlay, tools_overlay):
        assert "class MapStudioUniversalTransformOverlay" in source
        assert "class MapStudioUniversalTransformHandle" in source
        assert "class MapStudioUniversalTransformDimensionLabel" in source
        assert "def build_map_studio_universal_transform_overlay" in source
        assert "previewable_overlay" in source

    for source in (scene_tool_audit, tools_tool_audit):
        assert "class MapStudioToolContractAudit" in source
        assert "class MapStudioToolContractStatus" in source
        assert "def audit_map_studio_tool_belt_contract" in source
        assert "previewable_tool_contract_audit" in source
        assert "command_or_workflow_classification" in source

    for source in (scene_controller, tools_controller):
        assert "audit_map_studio_tool_belt_contract" in source
        assert "def map_studio_tool_belt_contract_audit" in source

    assert "def set_universal_transform_overlay" in viewport_panel
    assert "def _sync_universal_transform_overlay" in viewport_panel
    assert "def set_map_studio_universal_transform_overlay" in viewport_scene_models
    assert "def clear_map_studio_universal_transform_overlay" in viewport_scene_models
    assert "def _draw_map_studio_universal_transform_overlay" in viewport_overlay_layers
    assert "self._draw_map_studio_universal_transform_overlay(draw, w, h)" in viewport_rendering
