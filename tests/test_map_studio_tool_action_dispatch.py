from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


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
    assert audit.command_backed_actions >= 82
    assert audit.mutating_command_actions >= 74
    assert audit.query_command_actions >= 8
    assert audit.studio_workspace_actions == 0
    assert audit.workflow_focus_actions == 0
    assert statuses["cube"].contract_kind == "command_mutates_kmap"
    assert statuses["cube"].command_method == "add_authored_room_primitive"
    assert statuses["cube"].mutates_kmap is True
    assert statuses["primitive"].contract_kind == "command_mutates_kmap"
    assert statuses["primitive"].command_method == "add_authored_room_primitive"
    assert statuses["create_room"].contract_kind == "command_mutates_kmap"
    assert statuses["create_room"].command_method == "create_authored_room_preset_module"
    assert statuses["corridor"].contract_kind == "command_mutates_kmap"
    assert statuses["corridor"].command_method == "create_authored_room_preset_module"
    assert statuses["terrain_patch"].contract_kind == "command_mutates_kmap"
    assert statuses["terrain_patch"].command_method == "create_authored_room_preset_module"
    assert statuses["universal_transform"].contract_kind == "command_query"
    assert statuses["universal_transform"].command_method == "map_studio_universal_transform_overlay"
    assert statuses["center_pivot"].contract_kind == "command_mutates_kmap"
    assert statuses["center_pivot"].command_method == "center_authored_room_primitive_pivot"
    assert statuses["freeze_transform"].contract_kind == "command_mutates_kmap"
    assert statuses["freeze_transform"].command_method == "freeze_authored_room_primitive_transform"
    assert statuses["object_grid_snap"].contract_kind == "command_mutates_kmap"
    assert statuses["object_grid_snap"].command_method == "grid_snap_authored_room_primitive"
    assert statuses["object_vertex_snap"].contract_kind == "command_mutates_kmap"
    assert statuses["object_vertex_snap"].command_method == "snap_authored_room_primitive_pivot_to_vertex"
    assert statuses["placeable"].contract_kind == "command_mutates_kmap"
    assert statuses["placeable"].command_method == "add_authored_gameplay_placement"
    assert statuses["entry_point"].contract_kind == "command_mutates_kmap"
    assert statuses["entry_point"].command_method == "set_authored_module_entry_point"
    assert statuses["light"].contract_kind == "command_mutates_kmap"
    assert statuses["light"].command_method == "add_authored_room_light"
    assert statuses["light"].mutates_kmap is True
    assert statuses["script"].contract_kind == "command_mutates_kmap"
    assert statuses["script"].command_method == "set_authored_script_hook"
    assert statuses["script"].mutates_kmap is True
    assert statuses["opening"].contract_kind == "command_mutates_kmap"
    assert statuses["opening"].command_method == "set_authored_floor_plan_wall_opening"
    assert statuses["cut"].contract_kind == "command_mutates_kmap"
    assert statuses["cut"].command_method == "axis_split_authored_floor_plan_room"
    assert statuses["boolean"].contract_kind == "command_mutates_kmap"
    assert statuses["boolean"].command_method == "rectangular_cut_authored_floor_plan_room"
    assert statuses["boolean_a_minus_b"].contract_kind == "command_mutates_kmap"
    assert statuses["boolean_a_minus_b"].command_method == "boolean_difference_authored_floor_plan_rooms"
    assert statuses["opening_marker"].contract_kind == "command_mutates_kmap"
    assert statuses["opening_marker"].command_method == "add_authored_floor_plan_opening_transition_marker"
    assert statuses["fill_hole"].contract_kind == "command_mutates_kmap"
    assert statuses["fill_hole"].command_method == "fill_authored_floor_plan_face"
    assert statuses["bridge"].contract_kind == "command_mutates_kmap"
    assert statuses["bridge"].command_method == "bridge_authored_floor_plan_edges"
    assert statuses["combine"].contract_kind == "command_mutates_kmap"
    assert statuses["combine"].command_method == "merge_authored_floor_plan_rooms"
    assert statuses["separate"].contract_kind == "command_mutates_kmap"
    assert statuses["separate"].command_method == "separate_authored_room_primitive"
    assert statuses["extrude"].contract_kind == "command_mutates_kmap"
    assert statuses["extrude"].command_method == "edge_extrude_authored_floor_plan_room"
    assert statuses["bevel"].contract_kind == "command_mutates_kmap"
    assert statuses["bevel"].command_method == "bevel_authored_floor_plan_room"
    assert statuses["inset"].contract_kind == "command_mutates_kmap"
    assert statuses["inset"].command_method == "inset_authored_floor_plan_room"
    assert statuses["sculpt_raise"].contract_kind == "command_mutates_kmap"
    assert statuses["sculpt_raise"].command_method == "apply_authored_terrain_brush_stroke"
    assert statuses["shrink_wrap"].contract_kind == "command_mutates_kmap"
    assert statuses["shrink_wrap"].command_method == "shrink_wrap_authored_room_primitive_to_terrain"
    assert statuses["mirror_z"].contract_kind == "command_mutates_kmap"
    assert statuses["mirror_z"].command_method == "mirror_z_authored_terrain_heightfield"
    assert statuses["bend_tool"].contract_kind == "command_mutates_kmap"
    assert statuses["bend_tool"].command_method == "bend_authored_terrain_heightfield"
    assert statuses["lattice"].contract_kind == "command_mutates_kmap"
    assert statuses["lattice"].command_method == "lattice_authored_terrain_heightfield"
    assert statuses["terrain"].contract_kind == "command_query"
    assert statuses["terrain"].command_method == "authored_terrain_status"
    assert statuses["walkmesh"].contract_kind == "command_query"
    assert statuses["walkmesh"].command_method == "authored_walkmesh_status"
    assert statuses["validate"].contract_kind == "command_query"
    assert statuses["validate"].command_method == "validate"
    assert statuses["validate"].mutates_kmap is False
    assert statuses["stage_module"].contract_kind == "command_query"
    assert statuses["stage_module"].command_method == "stage_authored_module"
    assert statuses["stage_module"].mutates_kmap is False
    assert statuses["install_module"].contract_kind == "command_query"
    assert statuses["install_module"].command_method == "stage_authored_module"
    assert statuses["install_module"].mutates_kmap is False
    assert statuses["launch_handoff"].contract_kind == "command_query"
    assert statuses["launch_handoff"].command_method == "map_studio_launch_handoff"
    assert statuses["launch_handoff"].mutates_kmap is False
    assert statuses["record_proof"].contract_kind == "command_query"
    assert statuses["record_proof"].command_method == "map_studio_game_proof_recording_handoff"
    assert statuses["record_proof"].mutates_kmap is False
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
    from src.core.modules.map_studio_modeling_tools import (
        available_map_studio_tool_belt_actions,
        available_map_studio_modeling_tools,
        map_studio_tool_command_search,
    )

    cube = resolve_map_studio_tool_belt_action("cube")
    tool_by_key = {tool.key: tool for tool in available_map_studio_modeling_tools()}
    tool_belt_actions = available_map_studio_tool_belt_actions()
    tool_belt_action_keys = [action.key for action in tool_belt_actions]

    assert len(tool_belt_action_keys) == len(set(tool_belt_action_keys))
    assert "triangulate" in tool_belt_action_keys
    assert "triangulate_face" in tool_belt_action_keys

    assert cube.enabled is True
    assert cube.command_method == "add_authored_room_primitive"
    assert cube.command_kwargs["primitive_kind"] == "cube"
    assert cube.mutates_kmap is True
    assert cube.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "game proof" in cube.readiness_impact
    assert cube.capability_stage == "previewable"
    assert "KMAP" in cube.resource_impacts
    assert "WOK" in cube.resource_impacts
    assert "affected resources" in cube.readiness_summary

    starter_room = resolve_map_studio_tool_belt_action(
        "create_room",
        MapStudioToolActionContext(module_root="grroom42"),
    )

    assert starter_room.enabled is True
    assert starter_room.command_method == "create_authored_room_preset_module"
    assert starter_room.command_kwargs == {"preset_id": "rectangular_dev_room", "module_root": "grroom42"}
    assert starter_room.mutates_kmap is True
    assert "rectangular_dev_room" in starter_room.authoring_context

    corridor = resolve_map_studio_tool_belt_action("corridor")

    assert corridor.enabled is True
    assert corridor.command_method == "create_authored_room_preset_module"
    assert corridor.command_kwargs == {"preset_id": "wide_hall", "module_root": "grhall"}
    assert corridor.mutates_kmap is True

    terrain_patch = resolve_map_studio_tool_belt_action("terrain_patch")

    assert terrain_patch.enabled is True
    assert terrain_patch.command_method == "create_authored_room_preset_module"
    assert terrain_patch.command_kwargs == {"preset_id": "terrain_heightfield", "module_root": "grterrain"}
    assert terrain_patch.mutates_kmap is True

    terrain_status_route = resolve_map_studio_tool_belt_action("terrain")

    assert terrain_status_route.enabled is True
    assert terrain_status_route.command_method == "authored_terrain_status"
    assert terrain_status_route.mutates_kmap is False
    assert terrain_status_route.stale_outputs == ()
    assert "walkability overlay counts" in terrain_status_route.authoring_context

    walkmesh_status_route = resolve_map_studio_tool_belt_action("walkmesh")

    assert walkmesh_status_route.enabled is True
    assert walkmesh_status_route.command_method == "authored_walkmesh_status"
    assert walkmesh_status_route.mutates_kmap is False
    assert walkmesh_status_route.stale_outputs == ()
    assert "generated WOK walkability" in walkmesh_status_route.authoring_context

    validate_route = resolve_map_studio_tool_belt_action("validate")

    assert validate_route.enabled is True
    assert validate_route.command_method == "validate"
    assert validate_route.mutates_kmap is False
    assert validate_route.stale_outputs == ()
    assert "KMAP/authored-module readiness checks" in validate_route.authoring_context

    stage_missing = resolve_map_studio_tool_belt_action("stage_module")

    assert stage_missing.enabled is False
    assert "output directory" in stage_missing.disabled_reason
    assert stage_missing.capability_stage == "export_candidate"
    assert "ExportJob" in stage_missing.resource_impacts
    assert ".mod" in stage_missing.resource_impacts

    stage_ready = resolve_map_studio_tool_belt_action(
        "stage_module",
        MapStudioToolActionContext(export_output_dir=".pytest_tmp_stage", export_dry_run=True),
    )

    assert stage_ready.enabled is True
    assert stage_ready.command_method == "stage_authored_module"
    assert stage_ready.command_kwargs == {
        "output_dir": ".pytest_tmp_stage",
        "dry_run": True,
        "overwrite": False,
    }
    assert stage_ready.mutates_kmap is False
    assert stage_ready.stale_outputs == ()
    assert "export candidate" in stage_ready.authoring_context
    assert stage_ready.capability_stage == "export_candidate"
    assert "ExportJob" in stage_ready.resource_impacts
    assert ".mod" in stage_ready.resource_impacts
    assert "export candidate" in stage_ready.readiness_summary

    install_missing_output = resolve_map_studio_tool_belt_action("install_module")

    assert install_missing_output.enabled is False
    assert "staging output directory" in install_missing_output.disabled_reason

    install_missing_modules = resolve_map_studio_tool_belt_action(
        "install_module",
        MapStudioToolActionContext(export_output_dir=".pytest_tmp_stage", export_dry_run=True),
    )

    assert install_missing_modules.enabled is False
    assert "KOTOR Modules folder" in install_missing_modules.disabled_reason

    install_ready = resolve_map_studio_tool_belt_action(
        "install_module",
        MapStudioToolActionContext(
            export_output_dir=".pytest_tmp_stage",
            export_dry_run=True,
            export_overwrite=True,
            export_game_modules_dir=".pytest_tmp_modules",
        ),
    )

    assert install_ready.enabled is True
    assert install_ready.command_method == "stage_authored_module"
    assert install_ready.command_kwargs == {
        "output_dir": ".pytest_tmp_stage",
        "dry_run": True,
        "overwrite": True,
        "game_modules_dir": ".pytest_tmp_modules",
    }
    assert install_ready.mutates_kmap is False
    assert install_ready.stale_outputs == ()
    assert "manual warp-test checklist" in install_ready.authoring_context

    launch_handoff = resolve_map_studio_tool_belt_action("launch_handoff")

    assert launch_handoff.enabled is True
    assert launch_handoff.command_method == "map_studio_launch_handoff"
    assert launch_handoff.command_kwargs == {}
    assert launch_handoff.mutates_kmap is False
    assert launch_handoff.stale_outputs == ()
    assert "staged proof manifest" in launch_handoff.authoring_context
    assert launch_handoff.capability_stage == "installed_for_game_test_handoff"
    assert "not game-tested proof" in launch_handoff.readiness_summary

    record_proof = resolve_map_studio_tool_belt_action("record_proof")

    assert record_proof.enabled is True
    assert record_proof.command_method == "map_studio_game_proof_recording_handoff"
    assert record_proof.command_kwargs == {}
    assert record_proof.mutates_kmap is False
    assert record_proof.stale_outputs == ()
    assert "screenshot or video evidence" in record_proof.authoring_context
    assert record_proof.capability_stage == "game_tested_evidence_handoff"
    assert "accepted in-game evidence" in record_proof.readiness_summary

    selected_primitive = resolve_map_studio_tool_belt_action(
        "primitive",
        MapStudioToolActionContext(
            room_resref="room_a",
            primitive_kind="cylinder",
            primitive_name="room_a_cyl_01",
        ),
    )

    assert selected_primitive.enabled is True
    assert selected_primitive.command_method == "add_authored_room_primitive"
    assert selected_primitive.command_kwargs == {
        "primitive_kind": "cylinder",
        "room_resref": "room_a",
        "primitive_name": "room_a_cyl_01",
    }
    assert selected_primitive.mutates_kmap is True

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

    center_pivot_missing = resolve_map_studio_tool_belt_action("center_pivot")

    assert center_pivot_missing.enabled is False
    assert "selected authored room primitive" in center_pivot_missing.disabled_reason

    center_pivot_ready = resolve_map_studio_tool_belt_action(
        "center_pivot",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_cube"),
    )

    assert center_pivot_ready.enabled is True
    assert center_pivot_ready.command_method == "center_authored_room_primitive_pivot"
    assert center_pivot_ready.command_kwargs == {"room_resref": "room_a", "primitive_name": "room_a_cube"}
    assert center_pivot_ready.mutates_kmap is True
    assert "primitive-local space" in center_pivot_ready.authoring_context

    freeze_missing = resolve_map_studio_tool_belt_action("freeze_transform")

    assert freeze_missing.enabled is False
    assert "selected authored room primitive" in freeze_missing.disabled_reason

    freeze_ready = resolve_map_studio_tool_belt_action(
        "freeze_transform",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_cube"),
    )

    assert freeze_ready.enabled is True
    assert freeze_ready.command_method == "freeze_authored_room_primitive_transform"
    assert freeze_ready.command_kwargs == {"room_resref": "room_a", "primitive_name": "room_a_cube"}
    assert freeze_ready.mutates_kmap is True
    assert "reset transform intent to identity" in freeze_ready.authoring_context

    object_snap_missing = resolve_map_studio_tool_belt_action("object_grid_snap")

    assert object_snap_missing.enabled is False
    assert "selected authored room primitive" in object_snap_missing.disabled_reason

    object_snap_ready = resolve_map_studio_tool_belt_action(
        "object_grid_snap",
        MapStudioToolActionContext(
            room_resref="room_a",
            primitive_name="room_a_cube",
            grid_size=0.25,
            snap_axes=("x", "y"),
        ),
    )

    assert object_snap_ready.enabled is True
    assert object_snap_ready.command_method == "grid_snap_authored_room_primitive"
    assert object_snap_ready.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_cube",
        "grid_size": 0.25,
        "axes": ("x", "y"),
    }
    assert object_snap_ready.mutates_kmap is True
    assert "KMAP-world space" in object_snap_ready.authoring_context

    object_vertex_snap_missing = resolve_map_studio_tool_belt_action("object_vertex_snap")

    assert object_vertex_snap_missing.enabled is False
    assert "selected authored room primitive" in object_vertex_snap_missing.disabled_reason

    object_vertex_snap_auto = resolve_map_studio_tool_belt_action(
        "object_vertex_snap",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_cube"),
    )

    assert object_vertex_snap_auto.enabled is True
    assert object_vertex_snap_auto.command_method == "snap_authored_room_primitive_pivot_to_vertex"
    assert object_vertex_snap_auto.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_cube",
        "target_primitive_name": "",
        "target_vertex_index": None,
    }
    assert object_vertex_snap_auto.mutates_kmap is True
    assert "core chooses the nearest candidate" in object_vertex_snap_auto.authoring_context

    object_vertex_snap_ready = resolve_map_studio_tool_belt_action(
        "object_vertex_snap",
        MapStudioToolActionContext(
            room_resref="room_a",
            primitive_name="room_a_cube",
            target_primitive_name="room_a_wall",
            target_vertex_index=3,
        ),
    )

    assert object_vertex_snap_ready.enabled is True
    assert object_vertex_snap_ready.command_method == "snap_authored_room_primitive_pivot_to_vertex"
    assert object_vertex_snap_ready.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_cube",
        "target_primitive_name": "room_a_wall",
        "target_vertex_index": 3,
    }
    assert object_vertex_snap_ready.mutates_kmap is True
    assert "authored-room composition mesh space" in object_vertex_snap_ready.authoring_context

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
    assert terrain_raise.command_method == "apply_authored_terrain_brush_stroke"
    assert terrain_raise.command_kwargs == {
        "brush": "raise",
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

    light_route = resolve_map_studio_tool_belt_action(
        "light",
        MapStudioToolActionContext(
            light_room_resref="room_a",
            light_name="belt_key_light",
            light_position=(1.0, 2.0, 2.25),
            light_color=(0.8, 0.7, 0.6),
            light_radius=9.5,
            light_intensity=1.4,
            light_type="spot",
        ),
    )

    assert light_route.enabled is True
    assert light_route.command_method == "add_authored_room_light"
    assert light_route.command_kwargs == {
        "room_resref": "room_a",
        "name": "belt_key_light",
        "position": (1.0, 2.0, 2.25),
        "color": (0.8, 0.7, 0.6),
        "radius": 9.5,
        "intensity": 1.4,
        "light_type": "spot",
    }
    assert light_route.mutates_kmap is True
    assert "room-light intent" in light_route.authoring_context

    script_route = resolve_map_studio_tool_belt_action(
        "script",
        MapStudioToolActionContext(
            script_scope="area",
            script_field_name="OnEnter",
            script_resref="gr_onenter",
        ),
    )

    assert script_route.enabled is True
    assert script_route.command_method == "set_authored_script_hook"
    assert script_route.command_kwargs == {
        "scope": "area",
        "field_name": "OnEnter",
        "script_resref": "gr_onenter",
    }
    assert script_route.mutates_kmap is True
    assert "ARE/IFO script-hook resrefs" in script_route.authoring_context

    clear_script_route = resolve_map_studio_tool_belt_action(
        "script",
        MapStudioToolActionContext(script_scope="module", script_field_name="OnModLoad"),
    )

    assert clear_script_route.enabled is True
    assert clear_script_route.command_method == "remove_authored_script_hook"
    assert clear_script_route.command_kwargs == {
        "scope": "module",
        "field_name": "OnModLoad",
    }
    assert clear_script_route.mutates_kmap is True

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
    assert opening_route.command_method == "set_authored_floor_plan_wall_opening"
    assert opening_route.command_kwargs == {
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
    assert opening_marker_route.command_method == "add_authored_floor_plan_opening_transition_marker"
    assert opening_marker_route.command_kwargs == {
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

    grid_snap = resolve_map_studio_tool_belt_action("grid_snap")

    assert grid_snap.enabled is False
    assert "at least one selected" in grid_snap.disabled_reason
    assert grid_snap.command_method == ""

    ready_grid_snap = resolve_map_studio_tool_belt_action(
        "grid_snap",
        MapStudioToolActionContext(
            room_resref="room_a",
            point_indices=(1, 2),
            metadata={"grid_size": 0.25, "axes": ("x", "y", "z")},
        ),
    )

    assert ready_grid_snap.enabled is True
    assert ready_grid_snap.focus_snap_mode == "grid"
    assert ready_grid_snap.command_method == "grid_snap_authored_floor_plan_vertices"
    assert ready_grid_snap.command_kwargs == {
        "room_resref": "room_a",
        "point_indices": (1, 2),
        "grid_size": 0.25,
        "axes": ("x", "y", "z"),
    }
    assert ready_grid_snap.mutates_kmap is True
    assert "without welding topology" in ready_grid_snap.authoring_context

    level_snap = resolve_map_studio_tool_belt_action(
        "transform_snap_level",
        MapStudioToolActionContext(
            room_resref="room_a",
            point_indices=(1, 2),
            target_point_index=3,
            axis="y",
            metadata={"level_policy": "average"},
        ),
    )

    assert level_snap.enabled is True
    assert level_snap.focus_snap_mode == "level"
    assert level_snap.command_method == "transform_snap_authored_floor_plan_vertices"
    assert level_snap.command_kwargs == {
        "room_resref": "room_a",
        "point_indices": (1, 2),
        "axis": "y",
        "target_point_index": 3,
        "value": None,
        "level_policy": "average",
    }
    assert level_snap.mutates_kmap is True
    assert "hold-J command path" in level_snap.authoring_context

    object_level_snap = resolve_map_studio_tool_belt_action(
        "transform_snap_level",
        MapStudioToolActionContext(
            room_resref="room_a",
            primitive_name="room_a_cube",
            axis="z",
            target_primitive_name="room_a_wall",
            target_vertex_index=2,
        ),
    )

    assert object_level_snap.enabled is True
    assert object_level_snap.focus_component_mode == "object"
    assert object_level_snap.focus_snap_mode == "level"
    assert object_level_snap.command_method == "transform_snap_authored_room_primitive_level"
    assert object_level_snap.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_cube",
        "axis": "z",
        "target_primitive_name": "room_a_wall",
        "target_vertex_index": 2,
        "value": None,
    }
    assert object_level_snap.mutates_kmap is True
    assert "nearest primitive vertex candidate" in object_level_snap.authoring_context

    extrude = resolve_map_studio_tool_belt_action(
        "extrude",
        MapStudioToolActionContext(room_resref="room_a", operation_distance=0.75, operation_edge_index=2),
    )

    assert extrude.enabled is True
    assert extrude.command_method == "edge_extrude_authored_floor_plan_room"
    assert extrude.command_kwargs == {
        "room_resref": "room_a",
        "distance": 0.75,
        "edge_index": 2,
    }

    bevel = resolve_map_studio_tool_belt_action(
        "bevel",
        MapStudioToolActionContext(room_resref="room_a", operation_distance=0.2),
    )

    assert bevel.enabled is True
    assert bevel.command_method == "bevel_authored_floor_plan_room"
    assert bevel.command_kwargs == {
        "room_resref": "room_a",
        "distance": 0.2,
    }
    assert bevel.mutates_kmap is True

    inset = resolve_map_studio_tool_belt_action(
        "inset",
        MapStudioToolActionContext(room_resref="room_a", operation_distance=0.25),
    )

    assert inset.enabled is True
    assert inset.command_method == "inset_authored_floor_plan_room"
    assert inset.command_kwargs == {
        "room_resref": "room_a",
        "distance": 0.25,
    }
    assert inset.mutates_kmap is True
    assert "KOTOR room/export boundaries" in inset.authoring_context

    boolean = resolve_map_studio_tool_belt_action(
        "boolean",
        MapStudioToolActionContext(room_resref="room_a", cut_center=(1.0, 2.0), cut_size=(3.0, 4.0)),
    )

    assert boolean.enabled is True
    assert boolean.command_method == "rectangular_cut_authored_floor_plan_room"
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
    assert boolean_a_minus_b.command_method == "boolean_difference_authored_floor_plan_rooms"
    assert boolean_a_minus_b.command_kwargs == {
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

    cut = resolve_map_studio_tool_belt_action(
        "cut",
        MapStudioToolActionContext(room_resref="room_a", axis="x", cut_center=(1.25, 2.5)),
    )

    assert cut.enabled is True
    assert cut.command_method == "axis_split_authored_floor_plan_room"
    assert cut.command_kwargs == {
        "room_resref": "room_a",
        "axis": "x",
        "coordinate": 1.25,
    }
    assert cut.mutates_kmap is True

    slice_y = resolve_map_studio_tool_belt_action(
        "cut_slice_insert_edges",
        MapStudioToolActionContext(room_resref="room_a", axis="y", cut_center=(1.0, 2.0)),
    )

    assert slice_y.enabled is True
    assert slice_y.command_method == "axis_split_authored_floor_plan_room"
    assert slice_y.command_kwargs == {
        "room_resref": "room_a",
        "axis": "y",
        "coordinate": 2.0,
    }

    edge_loop = resolve_map_studio_tool_belt_action(
        "insert_edge_loop",
        MapStudioToolActionContext(room_resref="room_a", axis="x", cut_center=(1.25, 2.5)),
    )

    assert edge_loop.enabled is True
    assert edge_loop.command_method == "axis_split_authored_floor_plan_room"
    assert edge_loop.command_kwargs == {
        "room_resref": "room_a",
        "axis": "x",
        "coordinate": 1.25,
    }
    assert "KOTOR room/export boundaries" in edge_loop.authoring_context

    fill_missing = resolve_map_studio_tool_belt_action("fill_hole")

    assert fill_missing.enabled is False
    assert "selected loop" in fill_missing.disabled_reason

    fill = resolve_map_studio_tool_belt_action(
        "fill_hole",
        MapStudioToolActionContext(room_resref="room_a", point_indices=(0, 1, 2, 3)),
    )

    assert fill.enabled is True
    assert fill.command_method == "fill_authored_floor_plan_face"
    assert fill.command_kwargs == {"room_resref": "room_a", "point_indices": (0, 1, 2, 3)}
    assert "MDL/WOK export-ready" in fill.authoring_context

    triangulate = resolve_map_studio_tool_belt_action(
        "triangulate",
        MapStudioToolActionContext(room_resref="room_a"),
    )

    assert triangulate.enabled is True
    assert triangulate.command_method == "triangulate_authored_floor_plan_face"
    assert triangulate.command_kwargs == {"room_resref": "room_a"}
    assert "deterministic floor-plan fan triangles" in triangulate.authoring_context

    triangulate_face = resolve_map_studio_tool_belt_action(
        "triangulate_face",
        MapStudioToolActionContext(room_resref="room_a"),
    )

    assert triangulate_face.enabled is True
    assert triangulate_face.command_method == "triangulate_authored_floor_plan_face"
    assert triangulate_face.command_kwargs == {"room_resref": "room_a"}
    assert "deterministic floor-plan fan triangles" in triangulate_face.authoring_context

    bridge_missing = resolve_map_studio_tool_belt_action("bridge")

    assert bridge_missing.enabled is False
    assert "two selected room edges" in bridge_missing.disabled_reason

    bridge = resolve_map_studio_tool_belt_action(
        "bridge",
        MapStudioToolActionContext(
            first_room_resref="room_a",
            first_edge_index=0,
            second_room_resref="room_b",
            second_edge_index=1,
            result_room_resref="room_bridge",
        ),
    )

    assert bridge.enabled is True
    assert bridge.command_method == "bridge_authored_floor_plan_edges"
    assert bridge.command_kwargs == {
        "first_room_resref": "room_a",
        "first_edge_index": 0,
        "second_room_resref": "room_b",
        "second_edge_index": 1,
        "result_room_resref": "room_bridge",
    }
    assert "connector room" in bridge.authoring_context

    combine_missing = resolve_map_studio_tool_belt_action("combine")

    assert combine_missing.enabled is False
    assert "two compatible floor-plan rooms" in combine_missing.disabled_reason

    combine = resolve_map_studio_tool_belt_action(
        "combine",
        MapStudioToolActionContext(
            first_room_resref="room_a",
            second_room_resref="room_b",
            result_room_resref="room_ab",
        ),
    )

    assert combine.enabled is True
    assert combine.command_method == "merge_authored_floor_plan_rooms"
    assert combine.command_kwargs == {
        "first_room_resref": "room_a",
        "second_room_resref": "room_b",
        "result_room_resref": "room_ab",
    }
    assert "export boundary" in combine.authoring_context

    separate_missing = resolve_map_studio_tool_belt_action("separate")

    assert separate_missing.enabled is False
    assert "primitive selection" in separate_missing.disabled_reason

    separate = resolve_map_studio_tool_belt_action(
        "separate",
        MapStudioToolActionContext(room_resref="room_a", primitive_name="room_a_wall", result_room_resref="room_wall"),
    )

    assert separate.enabled is True
    assert separate.command_method == "separate_authored_room_primitive"
    assert separate.command_kwargs == {
        "room_resref": "room_a",
        "primitive_name": "room_a_wall",
        "result_room_resref": "room_wall",
    }
    assert "DCC UV/texturing handoff" in separate.authoring_context

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
    assert mirror_z.command_method == "mirror_z_authored_terrain_heightfield"
    assert mirror_z.command_kwargs == {"room_resref": "terrain01", "center_height": 0.25}
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
    assert bend.command_method == "bend_authored_terrain_heightfield"
    assert bend.command_kwargs == {
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
    assert lattice.command_method == "lattice_authored_terrain_heightfield"
    assert lattice.command_kwargs == {
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
    assert shrink_wrap.command_method == "shrink_wrap_authored_placements_to_terrain"
    assert shrink_wrap.command_kwargs == {"room_resref": "terrain01"}
    assert shrink_wrap.mutates_kmap is True
    assert "gameplay placements" in shrink_wrap.authoring_context
    assert "arbitrary mesh/walkmesh shrink-wrap remains planned" in shrink_wrap.authoring_context

    search_all = map_studio_tool_command_search("", limit=0)
    search_walkmesh = map_studio_tool_command_search("walkmesh", limit=5)
    search_v = map_studio_tool_command_search("snap vtx", limit=3)
    search_grid = map_studio_tool_command_search("grid snap", limit=3)
    search_triangulate_face = map_studio_tool_command_search("triangulate face", limit=3)
    search_export_candidate = map_studio_tool_command_search("export candidate", limit=0)
    search_game_evidence = map_studio_tool_command_search("game evidence", limit=0)

    assert len(search_all) >= 83
    assert search_walkmesh
    assert search_walkmesh[0].key == "walkmesh"
    assert search_walkmesh[0].display_label == "WOK Paint [walkmesh]"
    assert any(result.key == "vertex_snap" for result in search_v)
    assert any(result.key == "grid_snap" for result in search_grid)
    assert any(result.key == "triangulate_face" for result in search_triangulate_face)
    cube_search = next(result for result in search_all if result.key == "cube")
    stage_search = next(result for result in search_all if result.key == "stage_module")
    proof_search = next(result for result in search_all if result.key == "record_proof")
    assert cube_search.capability_stage == "previewable"
    assert "KMAP" in cube_search.resource_impacts
    assert "WOK" in cube_search.resource_impacts
    assert "game proof" in cube_search.readiness_summary
    assert stage_search.capability_stage == "export_candidate"
    assert "ExportJob" in stage_search.resource_impacts
    assert ".mod" in stage_search.resource_impacts
    assert proof_search.capability_stage == "game_tested_evidence_handoff"
    assert "accepted in-game evidence" in proof_search.readiness_summary
    assert any(result.key == "stage_module" for result in search_export_candidate)
    assert any(result.key == "record_proof" for result in search_game_evidence)
    assert all(result.implemented for result in search_all)


def test_t2606_tool_action_dispatch_executes_headless_command_and_records_undo(tmp_path) -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grbelt01", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grbelt01")
    assert controller.command_history.undo_label == "Create authored module grbelt01"

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
        "primitive",
        MapStudioToolActionContext(primitive_kind="wall", primitive_name="belt_wall"),
    )

    generic_after = controller.authored_room_primitive_transforms()
    assert len(generic_after) == before_count + 1
    assert generic_after[-1].primitive_type == "wall"
    assert generic_after[-1].primitive_name == "belt_wall"
    assert controller.command_history.undo_label == "Add wall primitive"

    controller.undo_map_studio_command()

    assert len(controller.authored_room_primitive_transforms()) == before_count

    execute_map_studio_tool_belt_action(
        controller,
        "corridor",
        MapStudioToolActionContext(module_root="grbelt_hall"),
    )

    assert controller.project.name == "grbelt_hall"
    hall_payload = controller.project.extra_sections["authored_module"]
    assert hall_payload["rooms"][0]["primitive"]["metadata"]["preset_id"] == "wide_hall"
    assert controller.command_history.undo_label == "Create authored module grbelt_hall"

    controller.undo_map_studio_command()

    assert controller.project.name == "grbelt01"

    execute_map_studio_tool_belt_action(controller, "terrain_patch")

    assert controller.project.name == "grterrain"
    terrain_payload = controller.project.extra_sections["authored_module"]
    assert terrain_payload["rooms"][0]["primitive"]["metadata"]["preset_id"] == "terrain_heightfield"
    assert controller.command_history.undo_label == "Create authored module grterrain"

    terrain_status = execute_map_studio_tool_belt_action(controller, "terrain")

    assert terrain_status["ready"] is True
    assert terrain_status["terrain_room_count"] == 1
    assert terrain_status["walkable_triangle_count"] > 0
    assert terrain_status["capability_stage"] == "previewable_status_query"
    assert controller.command_history.undo_label == "Create authored module grterrain"

    walkmesh_status = execute_map_studio_tool_belt_action(controller, "walkmesh")

    assert walkmesh_status.ready is True
    assert walkmesh_status.terrain_room_count == 1
    assert walkmesh_status.walkable_triangle_count > 0
    assert "Walkmesh:" in walkmesh_status.summary
    assert controller.command_history.undo_label == "Create authored module grterrain"

    validation_issues = execute_map_studio_tool_belt_action(controller, "validate")

    assert isinstance(validation_issues, list)
    assert controller.command_history.undo_label == "Create authored module grterrain"

    launch_missing = execute_map_studio_tool_belt_action(controller, "launch_handoff")

    assert launch_missing.ready is False
    assert "Stage or install" in " ".join(launch_missing.blocking_messages)
    assert launch_missing.warp_command == "warp grterrain"
    assert controller.command_history.undo_label == "Create authored module grterrain"

    proof_missing = execute_map_studio_tool_belt_action(controller, "record_proof")

    assert proof_missing.ready is False
    assert "proof manifest" in " ".join(proof_missing.blocking_messages)
    assert proof_missing.warp_command == "warp grterrain"
    assert proof_missing.required_checks[-1] == "Screenshot or video evidence is attached"
    assert controller.command_history.undo_label == "Create authored module grterrain"

    stage_result = execute_map_studio_tool_belt_action(
        controller,
        "stage_module",
        MapStudioToolActionContext(export_output_dir=str(tmp_path), export_dry_run=True),
    )

    assert stage_result.ok is True
    assert stage_result.code == "dry_run"
    assert stage_result.export_result is not None
    assert stage_result.export_result.ok is True
    assert stage_result.export_result.code == "export_candidate"
    assert stage_result.export_result.module_path.endswith(".mod")
    assert "game-tested" not in stage_result.message.lower()
    assert controller.command_history.undo_label == "Create authored module grterrain"

    launch_ready = execute_map_studio_tool_belt_action(controller, "launch_handoff")

    assert launch_ready.ready is True
    assert launch_ready.module_root == "grterrain"
    assert launch_ready.game == "K1"
    assert launch_ready.warp_command == "warp grterrain"
    assert launch_ready.proof_manifest_path == stage_result.proof_manifest_path
    assert launch_ready.launch_helper_command == stage_result.launch_helper_command
    assert launch_ready.capability_stage == "installed_for_game_test_handoff"
    assert "screenshot or video proof" in launch_ready.next_action
    assert controller.command_history.undo_label == "Create authored module grterrain"

    proof_ready = execute_map_studio_tool_belt_action(controller, "record_proof")

    assert proof_ready.ready is True
    assert proof_ready.module_root == "grterrain"
    assert proof_ready.game == "K1"
    assert proof_ready.warp_command == "warp grterrain"
    assert proof_ready.proof_manifest_path == stage_result.proof_manifest_path
    assert proof_ready.capability_stage == "installed_for_game_test_recording_handoff"
    assert "screenshot or video evidence" in proof_ready.summary
    assert controller.command_history.undo_label == "Create authored module grterrain"

    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    install_result = execute_map_studio_tool_belt_action(
        controller,
        "install_module",
        MapStudioToolActionContext(
            export_output_dir=str(tmp_path),
            export_dry_run=True,
            export_game_modules_dir=str(modules_dir),
        ),
    )

    assert install_result.ok is True
    assert install_result.code == "dry_run"
    assert install_result.resolved_modules_dir == str(modules_dir)
    assert install_result.installed_module_path == ""
    assert any("Dry run:" in warning for warning in install_result.warnings)
    assert controller.command_history.undo_label == "Create authored module grterrain"

    controller.undo_map_studio_command()

    assert controller.project.name == "grbelt01"

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlight01")
    light_room_resref = controller.authored_floor_plan_room_choices()[0].room_resref
    execute_map_studio_tool_belt_action(
        controller,
        "light",
        MapStudioToolActionContext(
            light_room_resref=light_room_resref,
            light_name="belt_key_light",
            light_position=(1.0, 1.5, 2.25),
            light_color=(1.0, 0.9, 0.7),
            light_radius=7.0,
            light_intensity=1.25,
            light_type="point",
        ),
    )

    light_rows = controller.authored_room_lights()
    assert light_rows[-1].name == "belt_key_light"
    assert light_rows[-1].room_resref == light_room_resref
    assert light_rows[-1].position == (1.0, 1.5, 2.25)
    assert light_rows[-1].color == (1.0, 0.9, 0.7)
    assert light_rows[-1].radius == 7.0
    assert light_rows[-1].intensity == 1.25
    assert controller.command_history.undo_label == "Add room light belt_key_light"

    controller.undo_map_studio_command()

    assert all(row.name != "belt_key_light" for row in controller.authored_room_lights())

    script_update = execute_map_studio_tool_belt_action(
        controller,
        "script",
        MapStudioToolActionContext(
            script_scope="area",
            script_field_name="OnEnter",
            script_resref="gr_onenter",
        ),
    )

    assert script_update.scope == "area"
    assert script_update.field_name == "OnEnter"
    assert script_update.script_resref == "gr_onenter"
    assert controller.authored_script_hooks()["area"]["OnEnter"] == "gr_onenter"
    assert controller.command_history.undo_label == "Set area script OnEnter"

    clear_script_update = execute_map_studio_tool_belt_action(
        controller,
        "script",
        MapStudioToolActionContext(
            script_scope="area",
            script_field_name="OnEnter",
        ),
    )

    assert clear_script_update.removed is True
    assert "OnEnter" not in controller.authored_script_hooks()["area"]
    assert controller.command_history.undo_label == "Clear area script OnEnter"

    controller.undo_map_studio_command()

    assert controller.authored_script_hooks()["area"]["OnEnter"] == "gr_onenter"

    controller.undo_map_studio_command()

    assert "OnEnter" not in controller.authored_script_hooks()["area"]

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
    assert controller.command_history.undo_label == "Set wall opening south_door"

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
    assert controller.command_history.undo_label == "Add opening marker south_exit_trigger"

    controller.undo_map_studio_command()

    restored_marker_payload = controller.project.extra_sections["authored_module"]
    assert all(row.get("tag") != "south_exit_trigger" for row in restored_marker_payload["placements"]["triggers"])
    assert controller.command_history.undo_label == "Set wall opening south_door"

    controller.undo_map_studio_command()

    restored_opening_payload = controller.project.extra_sections["authored_module"]
    assert restored_opening_payload["rooms"][0]["primitive"].get("openings", []) == []

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
    assert controller.command_history.undo_label == f"Bevel {room_before.room_resref}"

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grinset01")
    inset_room = controller.authored_floor_plan_room_choices()[0]
    execute_map_studio_tool_belt_action(
        controller,
        "inset",
        MapStudioToolActionContext(room_resref=inset_room.room_resref, operation_distance=0.2),
    )
    inset_payload = controller.project.extra_sections["authored_module"]
    inset_primitive = inset_payload["rooms"][0]["primitive"]

    assert inset_primitive["metadata"]["operation"] == "inset"
    assert inset_primitive["metadata"]["inset_distance"] == 0.2
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == f"Inset {inset_room.room_resref}"

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

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grfill01")
    fill_room = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "fill_hole",
        MapStudioToolActionContext(room_resref=fill_room.room_resref, point_indices=(0, 1, 2, 3)),
    )

    fill_payload = controller.project.extra_sections["authored_module"]
    fill_primitive = fill_payload["rooms"][0]["primitive"]

    assert fill_primitive["metadata"]["last_operation"] == "fill_floor_plan_face"
    assert fill_primitive["metadata"]["filled_face_indices"] == [0, 1, 2, 3]
    assert fill_payload["rooms"][0]["metadata"]["last_operation"] == "fill_floor_plan_face"
    assert controller.command_history.undo_label == f"Fill {fill_room.room_resref} floor-plan face"

    controller.undo_map_studio_command()

    restored_fill_payload = controller.project.extra_sections["authored_module"]
    assert "filled_face_indices" not in restored_fill_payload["rooms"][0]["primitive"]["metadata"]

    execute_map_studio_tool_belt_action(
        controller,
        "triangulate",
        MapStudioToolActionContext(room_resref=fill_room.room_resref),
    )

    triangulated_payload = controller.project.extra_sections["authored_module"]
    triangulated_metadata = triangulated_payload["rooms"][0]["primitive"]["metadata"]

    assert triangulated_metadata["last_operation"] == "triangulate_floor_plan_face"
    assert triangulated_metadata["triangulated_faces"] == [[0, 1, 2], [0, 2, 3]]
    assert controller.command_history.undo_label == f"Triangulate {fill_room.room_resref} floor-plan face"

    controller.undo_map_studio_command()

    restored_triangulate_payload = controller.project.extra_sections["authored_module"]
    assert "triangulated_faces" not in restored_triangulate_payload["rooms"][0]["primitive"]["metadata"]

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grbrdg1")
    bridge_payload = controller.project.extra_sections["authored_module"]
    bridge_base = bridge_payload["rooms"][0]
    bridge_second = copy.deepcopy(bridge_base)
    bridge_second["room_resref"] = "grbrdg1_room02"
    bridge_second["primitive"]["room_resref"] = "grbrdg1_room02"
    bridge_second["primitive"]["points"] = [
        [8.0, -5.0],
        [18.0, -5.0],
        [18.0, 5.0],
        [8.0, 5.0],
    ]
    bridge_base["visible_rooms"] = ["grbrdg1_room01", "grbrdg1_room02"]
    bridge_second["visible_rooms"] = ["grbrdg1_room01", "grbrdg1_room02"]
    bridge_payload["rooms"] = [bridge_base, bridge_second]
    controller.project.extra_sections["authored_module"] = bridge_payload

    execute_map_studio_tool_belt_action(
        controller,
        "bridge",
        MapStudioToolActionContext(
            first_room_resref="grbrdg1_room01",
            first_edge_index=0,
            second_room_resref="grbrdg1_room02",
            second_edge_index=1,
            result_room_resref="grbridge",
        ),
    )

    bridged_payload = controller.project.extra_sections["authored_module"]
    bridged_room = bridged_payload["rooms"][-1]

    assert len(bridged_payload["rooms"]) == 3
    assert bridged_room["room_resref"] == "grbridge"
    assert bridged_room["primitive"]["metadata"]["operation"] == "bridge_edges"
    assert bridged_room["primitive"]["metadata"]["first_room_resref"] == "grbrdg1_room01"
    assert bridged_room["primitive"]["metadata"]["second_room_resref"] == "grbrdg1_room02"
    assert controller.command_history.undo_label == "Bridge grbrdg1_room01:0 to grbrdg1_room02:1"

    controller.undo_map_studio_command()

    restored_bridge_payload = controller.project.extra_sections["authored_module"]
    assert [room["room_resref"] for room in restored_bridge_payload["rooms"]] == ["grbrdg1_room01", "grbrdg1_room02"]

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grcomb1")
    combine_payload = controller.project.extra_sections["authored_module"]
    combine_base = combine_payload["rooms"][0]
    combine_base["primitive"]["points"] = [
        [-5.0, -5.0],
        [0.0, -5.0],
        [0.0, 5.0],
        [-5.0, 5.0],
    ]
    combine_second = copy.deepcopy(combine_base)
    combine_second["room_resref"] = "grcomb1_room02"
    combine_second["primitive"]["room_resref"] = "grcomb1_room02"
    combine_second["primitive"]["points"] = [
        [0.0, -5.0],
        [5.0, -5.0],
        [5.0, 5.0],
        [0.0, 5.0],
    ]
    combine_base["visible_rooms"] = ["grcomb1_room01", "grcomb1_room02"]
    combine_second["visible_rooms"] = ["grcomb1_room01", "grcomb1_room02"]
    combine_payload["rooms"] = [combine_base, combine_second]
    controller.project.extra_sections["authored_module"] = combine_payload

    execute_map_studio_tool_belt_action(
        controller,
        "combine",
        MapStudioToolActionContext(
            first_room_resref="grcomb1_room01",
            second_room_resref="grcomb1_room02",
            result_room_resref="grcombout",
        ),
    )

    combined_payload = controller.project.extra_sections["authored_module"]
    combined_room = combined_payload["rooms"][0]

    assert len(combined_payload["rooms"]) == 1
    assert combined_room["room_resref"] == "grcombout"
    assert combined_room["primitive"]["metadata"]["operation"] == "rectangular_union"
    assert combined_room["primitive"]["metadata"]["source_room_resrefs"] == ["grcomb1_room01", "grcomb1_room02"]
    assert controller.command_history.undo_label == "Merge grcomb1_room01 and grcomb1_room02"

    controller.undo_map_studio_command()

    restored_combine_payload = controller.project.extra_sections["authored_module"]
    assert [room["room_resref"] for room in restored_combine_payload["rooms"]] == ["grcomb1_room01", "grcomb1_room02"]

    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grsep01")
    separate_source_rows = controller.authored_room_primitive_transforms()
    separate_source = separate_source_rows[0]
    separate_source_count = len(separate_source_rows)

    execute_map_studio_tool_belt_action(
        controller,
        "separate",
        MapStudioToolActionContext(
            room_resref=separate_source.room_resref,
            primitive_name=separate_source.primitive_name,
            result_room_resref="grsepwall",
        ),
    )

    separated_payload = controller.project.extra_sections["authored_module"]

    assert len(separated_payload["rooms"]) == 2
    assert separated_payload["rooms"][1]["room_resref"] == "grsepwall"
    assert separated_payload["rooms"][1]["metadata"]["last_operation"] == "separate_composition_primitive"
    assert separated_payload["rooms"][1]["metadata"]["separated_primitive"] == separate_source.primitive_name
    assert len(controller.authored_room_primitive_transforms()) == separate_source_count
    assert controller.command_history.undo_label == f"Separate primitive {separate_source.primitive_name}"

    controller.undo_map_studio_command()

    restored_separate_payload = controller.project.extra_sections["authored_module"]
    assert len(restored_separate_payload["rooms"]) == 1
    assert len(controller.authored_room_primitive_transforms()) == separate_source_count

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grcutcmd")

    execute_map_studio_tool_belt_action(
        controller,
        "boolean",
        MapStudioToolActionContext(
            room_resref="grcutcmd_room01",
            cut_center=(0.0, 0.0),
            cut_size=(2.0, 1.0),
        ),
    )

    cut_payload = controller.project.extra_sections["authored_module"]
    cut_rooms = controller.authored_floor_plan_room_choices()

    assert len(cut_rooms) == 4
    assert {room.room_resref for room in cut_rooms} == {"grcutcmd_room_l1", "grcutcmd_room_r2", "grcutcmd_room_b3", "grcutcmd_room_t4"}
    assert cut_payload["rooms"][0]["primitive"]["metadata"]["operation"] == "rectangular_cut_difference"
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Rectangular cut grcutcmd_room01"

    controller.undo_map_studio_command()

    assert [room.room_resref for room in controller.authored_floor_plan_room_choices()] == ["grcutcmd_room01"]

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="gredge01")
    room_before_split = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "cut",
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
    assert controller.command_history.undo_label == "Axis split gredge01_room01 on x"

    controller.undo_map_studio_command()

    restored_rooms = controller.authored_floor_plan_room_choices()
    assert len(restored_rooms) == 1
    assert restored_rooms[0].room_resref == room_before_split.room_resref

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grextrd1")
    extrude_room = controller.authored_floor_plan_room_choices()[0]

    execute_map_studio_tool_belt_action(
        controller,
        "extrude",
        MapStudioToolActionContext(
            room_resref=extrude_room.room_resref,
            operation_edge_index=0,
            operation_distance=0.75,
        ),
    )

    extruded_payload = controller.project.extra_sections["authored_module"]
    extruded_primitive = extruded_payload["rooms"][0]["primitive"]

    assert len(extruded_primitive["points"]) == 6
    assert extruded_primitive["metadata"]["operation"] == "edge_extrude"
    assert extruded_primitive["metadata"]["edge_index"] == 0
    assert extruded_primitive["metadata"]["edge_extrude_distance"] == 0.75
    assert controller.command_history.undo_label == "Extrude edge 0 on grextrd1_room01"

    controller.undo_map_studio_command()

    restored_extrude_payload = controller.project.extra_sections["authored_module"]
    assert len(restored_extrude_payload["rooms"][0]["primitive"]["points"]) == 4

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
    assert controller.command_history.undo_label == "Boolean difference grbool01_room01 - grbool01_cut"

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
    assert controller.command_history.undo_label == f"Shrink wrap placements {terrain_room.room_resref}"

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
    assert controller.command_history.undo_label == "Apply terrain brush raise"

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
    assert controller.command_history.undo_label == f"Mirror Z terrain {mirror_room.room_resref}"

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
    assert controller.command_history.undo_label == f"Bend terrain {bend_room.room_resref}"

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
    assert controller.command_history.undo_label == f"Lattice terrain {lattice_room.room_resref}"

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


def test_t2606_center_pivot_preserves_visible_primitive_bounds() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grpivot01", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grpivot01")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="pivot_cube"),
    )
    cube = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
        translation=(1.0, 2.0, 0.0),
        rotation_degrees_z=30.0,
        scale=(2.0, 1.0, 2.0),
        pivot=(0.0, 0.0, 0.0),
    )

    before = controller.map_studio_universal_transform_overlay(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
    )

    execute_map_studio_tool_belt_action(
        controller,
        "center_pivot",
        MapStudioToolActionContext(room_resref=cube.room_resref, primitive_name=cube.primitive_name),
    )

    after_rows = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }
    centered = after_rows["pivot_cube"]
    assert centered.pivot == (0.0, 0.0, 0.5)
    assert centered.translation == (1.0, 2.0, 0.5)
    assert controller.command_history.undo_label == "Center pivot pivot_cube"

    after = controller.map_studio_universal_transform_overlay(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
    )
    assert tuple(round(value, 6) for value in after.bounds_min) == tuple(round(value, 6) for value in before.bounds_min)
    assert tuple(round(value, 6) for value in after.bounds_max) == tuple(round(value, 6) for value in before.bounds_max)
    assert tuple(round(value, 6) for value in after.center) == tuple(round(value, 6) for value in before.center)
    payload = controller.project.extra_sections["authored_module"]
    room_payload = payload["rooms"][0]
    assert room_payload["primitive"]["metadata"]["last_operation"] == "center_primitive_pivot"
    assert room_payload["primitive"]["metadata"]["center_pivot_space"] == "primitive_local_preserve_world_geometry"

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }["pivot_cube"]
    assert restored.pivot == (0.0, 0.0, 0.0)
    assert restored.translation == (1.0, 2.0, 0.0)


def test_t2606_freeze_transform_bakes_supported_primitive_without_moving_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grfreeze01", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grfreeze01")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="freeze_cube"),
    )
    cube = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
        translation=(1.0, 2.0, 3.0),
        rotation_degrees_z=0.0,
        scale=(2.0, 3.0, 4.0),
        pivot=(0.0, 0.0, 0.0),
    )

    before = controller.map_studio_universal_transform_overlay(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
    )

    execute_map_studio_tool_belt_action(
        controller,
        "freeze_transform",
        MapStudioToolActionContext(room_resref=cube.room_resref, primitive_name=cube.primitive_name),
    )

    after = controller.map_studio_universal_transform_overlay(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
    )
    assert tuple(round(value, 6) for value in after.bounds_min) == tuple(round(value, 6) for value in before.bounds_min)
    assert tuple(round(value, 6) for value in after.bounds_max) == tuple(round(value, 6) for value in before.bounds_max)
    assert tuple(round(value, 6) for value in after.center) == tuple(round(value, 6) for value in before.center)

    frozen = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }["freeze_cube"]
    assert frozen.translation == (0.0, 0.0, 0.0)
    assert frozen.rotation_degrees_z == 0.0
    assert frozen.scale == (1.0, 1.0, 1.0)
    assert frozen.pivot == (0.0, 0.0, 0.0)
    assert controller.command_history.undo_label == "Freeze transform freeze_cube"

    payload = controller.project.extra_sections["authored_module"]
    room_payload = payload["rooms"][0]
    primitive_payload = next(
        item for item in room_payload["primitive"]["primitives"] if item.get("instance_name") == "freeze_cube"
    )
    assert primitive_payload["type"] == "cube"
    assert primitive_payload["size"] == [2.0, 3.0, 4.0]
    assert primitive_payload["center"] == [1.0, 2.0, 5.0]
    assert primitive_payload["transform"] == {
        "translation": [0.0, 0.0, 0.0],
        "rotation_degrees_z": 0.0,
        "scale": [1.0, 1.0, 1.0],
        "pivot": [0.0, 0.0, 0.0],
    }
    assert room_payload["primitive"]["metadata"]["freeze_transform_space"] == "primitive_local_parametric_unrotated"
    assert room_payload["primitive"]["metadata"]["frozen_transform"]["translation"] == [1.0, 2.0, 3.0]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }["freeze_cube"]
    assert restored.translation == (1.0, 2.0, 3.0)
    assert restored.scale == (2.0, 3.0, 4.0)


def test_t2606_freeze_transform_rejects_rotated_parametric_primitive() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grfreezerot", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grfreezerot")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="rotated_cube"),
    )
    cube = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
        translation=(1.0, 2.0, 0.0),
        rotation_degrees_z=15.0,
        scale=(2.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.5),
    )
    before_payload = copy.deepcopy(controller.project.extra_sections["authored_module"])

    with pytest.raises(ValueError, match="supports unrotated authored primitives only"):
        execute_map_studio_tool_belt_action(
            controller,
            "freeze_transform",
            MapStudioToolActionContext(room_resref=cube.room_resref, primitive_name=cube.primitive_name),
        )

    assert controller.project.extra_sections["authored_module"] == before_payload


def test_t2606_object_grid_snap_moves_primitive_pivot_to_grid() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grobjsnap", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grobjsnap")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="snap_cube"),
    )
    cube = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=cube.room_resref,
        primitive_name=cube.primitive_name,
        translation=(1.12, 2.37, 0.49),
        rotation_degrees_z=20.0,
        scale=(1.5, 1.0, 2.0),
        pivot=(0.0, 0.0, 0.5),
    )

    execute_map_studio_tool_belt_action(
        controller,
        "object_grid_snap",
        MapStudioToolActionContext(
            room_resref=cube.room_resref,
            primitive_name=cube.primitive_name,
            grid_size=0.25,
            snap_axes=("x", "y", "z"),
        ),
    )

    snapped = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }["snap_cube"]
    assert snapped.translation == (1.0, 2.25, 0.5)
    assert snapped.rotation_degrees_z == 20.0
    assert snapped.scale == (1.5, 1.0, 2.0)
    assert snapped.pivot == (0.0, 0.0, 0.5)
    assert controller.command_history.undo_label == "Object grid snap snap_cube"

    payload = controller.project.extra_sections["authored_module"]
    room_payload = payload["rooms"][0]
    metadata = room_payload["primitive"]["metadata"]
    assert metadata["last_operation"] == "object_grid_snap_primitive"
    assert metadata["object_grid_snap_coordinate_space"] == "kmap_world_pivot"
    assert metadata["object_grid_snap_size"] == 0.25
    assert metadata["object_grid_snap_axes"] == ["x", "y", "z"]
    assert metadata["old_translation"] == [1.12, 2.37, 0.49]
    assert metadata["new_translation"] == [1.0, 2.25, 0.5]
    assert metadata["snapped_world_pivot"] == [1.0, 2.25, 1.0]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == cube.room_resref
    }["snap_cube"]
    assert restored.translation == (1.12, 2.37, 0.49)


def test_t2606_object_vertex_snap_moves_primitive_pivot_to_target_vertex() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grobjvtx", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grobjvtx")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="source_cube"),
    )
    source = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=source.room_resref,
        primitive_name=source.primitive_name,
        translation=(0.25, 0.5, 0.75),
        rotation_degrees_z=15.0,
        scale=(1.25, 1.5, 1.0),
        pivot=(0.0, 0.0, 0.5),
    )
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="target_cube"),
    )
    target = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=target.room_resref,
        primitive_name=target.primitive_name,
        translation=(2.0, 3.0, 1.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )

    execute_map_studio_tool_belt_action(
        controller,
        "object_vertex_snap",
        MapStudioToolActionContext(
            room_resref=source.room_resref,
            primitive_name=source.primitive_name,
            target_primitive_name=target.primitive_name,
            target_vertex_index=6,
        ),
    )

    snapped = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert snapped.translation == (2.5, 3.5, 1.5)
    assert snapped.rotation_degrees_z == 15.0
    assert snapped.scale == (1.25, 1.5, 1.0)
    assert snapped.pivot == (0.0, 0.0, 0.5)
    assert controller.command_history.undo_label == "Object vertex snap source_cube"

    payload = controller.project.extra_sections["authored_module"]
    metadata = payload["rooms"][0]["primitive"]["metadata"]
    assert metadata["last_operation"] == "object_vertex_snap_primitive"
    assert metadata["object_vertex_snap_coordinate_space"] == "authored_room_composition_mesh_space"
    assert metadata["target_primitive"] == "target_cube"
    assert metadata["target_vertex_index"] == 6
    assert metadata["target_vertex"] == [2.5, 3.5, 2.0]
    assert metadata["old_translation"] == [0.25, 0.5, 0.75]
    assert metadata["new_translation"] == [2.5, 3.5, 1.5]
    assert metadata["snapped_pivot"] == [2.5, 3.5, 2.0]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert restored.translation == (0.25, 0.5, 0.75)


def test_t2606_object_vertex_snap_auto_selects_nearest_target_vertex() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grobjvtxauto", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grobjvtxauto")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="source_cube"),
    )
    source = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=source.room_resref,
        primitive_name=source.primitive_name,
        translation=(0.0, 0.0, 0.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.5),
    )
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="near_cube"),
    )
    near = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=near.room_resref,
        primitive_name=near.primitive_name,
        translation=(1.0, 0.0, 0.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="far_cube"),
    )
    far = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=far.room_resref,
        primitive_name=far.primitive_name,
        translation=(5.0, 0.0, 0.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )

    candidates = controller.authored_room_primitive_vertex_snap_candidates(
        room_resref=source.room_resref,
        primitive_name=source.primitive_name,
        max_results=2,
    )
    assert candidates[0].primitive_name == "near_cube"
    assert candidates[0].vertex_index == 0
    assert candidates[0].composition_position == (0.5, -0.5, 0.0)

    execute_map_studio_tool_belt_action(
        controller,
        "object_vertex_snap",
        MapStudioToolActionContext(room_resref=source.room_resref, primitive_name=source.primitive_name),
    )

    snapped = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert snapped.translation == (0.5, -0.5, -0.5)

    payload = controller.project.extra_sections["authored_module"]
    metadata = payload["rooms"][0]["primitive"]["metadata"]
    assert metadata["target_primitive"] == "near_cube"
    assert metadata["target_vertex_index"] == 0
    assert metadata["target_vertex"] == [0.5, -0.5, 0.0]
    assert metadata["new_translation"] == [0.5, -0.5, -0.5]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert restored.translation == (0.0, 0.0, 0.0)


def test_t2606_object_transform_level_snap_aligns_primitive_pivot_axis() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grobjlvl", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grobjlvl")
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="source_cube"),
    )
    source = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=source.room_resref,
        primitive_name=source.primitive_name,
        translation=(0.25, 0.5, 0.75),
        rotation_degrees_z=25.0,
        scale=(1.25, 1.5, 1.0),
        pivot=(0.0, 0.0, 0.5),
    )
    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="target_cube"),
    )
    target = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=target.room_resref,
        primitive_name=target.primitive_name,
        translation=(2.0, 3.0, 1.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )

    execute_map_studio_tool_belt_action(
        controller,
        "transform_snap_level",
        MapStudioToolActionContext(
            room_resref=source.room_resref,
            primitive_name=source.primitive_name,
            axis="z",
            target_primitive_name=target.primitive_name,
            target_vertex_index=6,
        ),
    )

    snapped = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert snapped.translation == (0.25, 0.5, 1.5)
    assert snapped.rotation_degrees_z == 25.0
    assert snapped.scale == (1.25, 1.5, 1.0)
    assert snapped.pivot == (0.0, 0.0, 0.5)
    assert controller.command_history.undo_label == "Object transform snap source_cube on z"

    payload = controller.project.extra_sections["authored_module"]
    metadata = payload["rooms"][0]["primitive"]["metadata"]
    assert metadata["last_operation"] == "object_transform_snap_level"
    assert metadata["object_transform_snap_coordinate_space"] == "authored_room_composition_mesh_space"
    assert metadata["object_transform_snap_axis"] == "z"
    assert metadata["object_transform_snap_value"] == 2.0
    assert metadata["object_transform_snap_old_pivot_level"] == 1.25
    assert metadata["target_primitive"] == "target_cube"
    assert metadata["target_vertex_index"] == 6
    assert metadata["old_translation"] == [0.25, 0.5, 0.75]
    assert metadata["new_translation"] == [0.25, 0.5, 1.5]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert restored.translation == (0.25, 0.5, 0.75)


def test_t2606_object_shrink_wrap_drops_primitive_bottom_to_terrain() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
        resolve_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grobjwrap", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grobjwrap")
    terrain_project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grobjwrp",
        game="K1",
    )
    terrain_payload = authored_project_to_kmap_payload(terrain_project)
    terrain_room = copy.deepcopy(terrain_payload["rooms"][0])
    terrain_room["room_resref"] = "grobjterrain"
    terrain_room["primitive"]["room_resref"] = "grobjterrain"
    payload = controller.project.extra_sections["authored_module"]
    payload["rooms"].append(terrain_room)
    controller.project.extra_sections["authored_module"] = payload

    execute_map_studio_tool_belt_action(
        controller,
        "primitive",
        MapStudioToolActionContext(primitive_kind="cube", primitive_name="source_cube"),
    )
    source = controller.authored_room_primitive_transforms()[-1]
    controller.set_authored_room_primitive_transform(
        room_resref=source.room_resref,
        primitive_name=source.primitive_name,
        translation=(0.0, 0.0, 2.0),
        rotation_degrees_z=35.0,
        scale=(1.0, 1.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )

    route = resolve_map_studio_tool_belt_action(
        "shrink_wrap",
        MapStudioToolActionContext(
            room_resref=source.room_resref,
            primitive_name=source.primitive_name,
            target_room_resref="grobjterrain",
        ),
    )
    assert route.enabled is True
    assert route.command_method == "shrink_wrap_authored_room_primitive_to_terrain"
    assert route.command_kwargs == {
        "room_resref": source.room_resref,
        "primitive_name": source.primitive_name,
        "terrain_room_resref": "grobjterrain",
    }
    assert "lowest transformed vertex" in route.authoring_context

    execute_map_studio_tool_belt_action(
        controller,
        "shrink_wrap",
        MapStudioToolActionContext(
            room_resref=source.room_resref,
            primitive_name=source.primitive_name,
            target_room_resref="grobjterrain",
        ),
    )

    wrapped = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert tuple(round(value, 6) for value in wrapped.translation) == (0.0, 0.0, 0.35)
    assert wrapped.rotation_degrees_z == 35.0
    assert wrapped.scale == (1.0, 1.0, 1.0)
    assert wrapped.pivot == (0.0, 0.0, 0.0)
    assert controller.command_history.undo_label == "Object shrink wrap source_cube to terrain"

    payload = controller.project.extra_sections["authored_module"]
    composition_metadata = payload["rooms"][0]["primitive"]["metadata"]
    assert composition_metadata["last_operation"] == "object_shrink_wrap_to_terrain"
    assert composition_metadata["object_shrink_wrap_coordinate_space"] == "authored_room_composition_mesh_space"
    assert composition_metadata["terrain_room_resref"] == "grobjterrain"
    assert composition_metadata["old_bottom_z"] == 2.0
    assert round(float(composition_metadata["target_surface_z"]), 6) == 0.35
    assert [round(float(value), 6) for value in composition_metadata["new_translation"]] == [0.0, 0.0, 0.35]

    controller.undo_map_studio_command()
    restored = {
        row.primitive_name: row
        for row in controller.authored_room_primitive_transforms()
        if row.room_resref == source.room_resref
    }["source_cube"]
    assert restored.translation == (0.0, 0.0, 2.0)


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
    assert "mapStudioVertexSnapShortcut" in window_source
    assert "mapStudioTransformLevelSnapShortcut" in window_source
    assert '"grid_snap",' in window_source
    assert 'QtGui.QKeySequence("V")' in window_source
    assert 'QtGui.QKeySequence("J")' in window_source
    assert "QtCore.Qt.WidgetWithChildrenShortcut" in window_source
    assert 'self._activate_map_studio_modifier_shortcut("vertex_snap")' in window_source
    assert 'self._activate_map_studio_modifier_shortcut("transform_snap_level")' in window_source
    assert "def _activate_map_studio_modifier_shortcut" in window_source
    assert "set_universal_transform_overlay" in window_source
    assert '"duplicate_special",' in window_source
    assert '"shrink_wrap",' in window_source
    assert '"create_room",' in window_source
    assert '"corridor",' in window_source
    assert '"terrain_patch",' in window_source
    assert '"terrain",' in window_source
    assert '"walkmesh",' in window_source
    assert '"validate",' in window_source
    assert '"primitive",' in window_source
    assert '"cut",' in window_source
    assert '"opening_marker",' in window_source
    assert '"mirror_z",' in window_source
    assert '"bend_tool",' in window_source
    assert '"curve_tool",' in window_source
    assert '"lattice",' in window_source
    assert '"light",' in window_source
    assert "roomLightRoomLineEdit" in window_source
    assert "roomLightNameLineEdit" in window_source
    assert "roomLightTypeComboBox" in window_source
    assert "light_room_resref=light_room" in window_source
    assert "light_position=(" in window_source
    assert "light_color=(" in window_source
    assert "scriptHookScopeComboBox" in window_source
    assert "scriptHookFieldComboBox" in window_source
    assert "scriptHookResrefLineEdit" in window_source
    assert '"script",' in window_source
    assert "script_scope=script_scope" in window_source
    assert "script_field_name=script_field" in window_source
    assert "script_resref=script_resref" in window_source
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in scene_catalog
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in tools_catalog
    assert "class MapStudioToolCapabilitySummary" in scene_catalog
    assert "class MapStudioToolCapabilitySummary" in tools_catalog
    assert "def map_studio_tool_capability_summary" in scene_catalog
    assert "def map_studio_tool_capability_summary" in tools_catalog
    assert '"center_pivot"' in scene_catalog
    assert '"center_pivot"' in tools_catalog
    assert '"freeze_transform"' in scene_catalog
    assert '"freeze_transform"' in tools_catalog
    assert '"object_grid_snap"' in scene_catalog
    assert '"object_grid_snap"' in tools_catalog
    assert '"object_vertex_snap"' in scene_catalog
    assert '"object_vertex_snap"' in tools_catalog

    for source in (scene_dispatcher, tools_dispatcher):
        assert "class MapStudioToolActionContext" in source
        assert "class MapStudioToolActionRoute" in source
        assert "map_studio_tool_capability_summary" in source
        assert "capability_stage: str" in source
        assert "resource_impacts: tuple[str, ...]" in source
        assert "readiness_summary: str" in source
        assert "def resolve_map_studio_tool_belt_action" in source
        assert "def execute_map_studio_tool_belt_action" in source
        assert 'if key == "validate":' in source
        assert 'command_method="validate"' in source
        assert 'command_method="add_authored_room_primitive"' in source
        assert 'command_method="create_authored_room_preset_module"' in source
        assert 'command_method="snap_authored_floor_plan_vertex"' in source
        assert 'command_method="grid_snap_authored_floor_plan_vertices"' in source
        assert 'command_method="transform_snap_authored_floor_plan_vertices"' in source
        assert 'command_method="transform_snap_authored_room_primitive_level"' in source
        assert 'if key == "light":' in source
        assert "light_room_resref" in source
        assert 'command_method="add_authored_room_light"' in source
        assert 'if key == "script":' in source
        assert "script_field_name" in source
        assert 'command_method = "set_authored_script_hook" if script_resref else "remove_authored_script_hook"' in source
        assert 'command_method="set_authored_floor_plan_wall_opening"' in source
        assert 'command_method="add_authored_floor_plan_opening_transition_marker"' in source
        assert 'command_method="edge_extrude_authored_floor_plan_room"' in source
        assert 'command_method="bevel_authored_floor_plan_room"' in source
        assert 'command_method="inset_authored_floor_plan_room"' in source
        assert 'command_method="rectangular_cut_authored_floor_plan_room"' in source
        assert 'command_method="axis_split_authored_floor_plan_room"' in source
        assert 'command_method="boolean_difference_authored_floor_plan_rooms"' in source
        assert 'command_method="fill_authored_floor_plan_face"' in source
        assert 'command_method="triangulate_authored_floor_plan_face"' in source
        assert 'command_method="bridge_authored_floor_plan_edges"' in source
        assert 'command_method="merge_authored_floor_plan_rooms"' in source
        assert 'command_method="separate_authored_room_primitive"' in source
        assert 'command_method="duplicate_authored_room_primitive"' in source
        assert 'command_method="center_authored_room_primitive_pivot"' in source
        assert 'command_method="freeze_authored_room_primitive_transform"' in source
        assert 'command_method="grid_snap_authored_room_primitive"' in source
        assert 'command_method="snap_authored_room_primitive_pivot_to_vertex"' in source
        assert 'command_method="set_authored_room_edge_normal_policy"' in source
        assert 'command_method="apply_authored_terrain_brush_stroke"' in source
        assert 'command_method="shrink_wrap_authored_placements_to_terrain"' in source
        assert 'command_method="mirror_z_authored_terrain_heightfield"' in source
        assert 'command_method="authored_terrain_status"' in source
        assert 'command_method="authored_walkmesh_status"' in source
        assert 'command_method="add_authored_curve_guide"' in source
        assert 'command_method="bend_authored_terrain_heightfield"' in source
        assert 'command_method="lattice_authored_terrain_heightfield"' in source
        assert '"curve_tool"' in source
        assert '"boolean_a_minus_b"' in source
        assert '"boolean_b_minus_a"' in source
        assert '"insert_edge_loop"' in source
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
        assert "def center_authored_room_primitive_pivot" in source
        assert "def freeze_authored_room_primitive_transform" in source
        assert "freeze_authored_room_composition_primitive_transform" in source
        assert "def grid_snap_authored_room_primitive" in source
        assert "grid_snap_authored_room_composition_primitive" in source
        assert "def authored_room_primitive_vertex_snap_candidates" in source
        assert "authored_room_composition_primitive_vertex_snap_candidates" in source
        assert "def snap_authored_room_primitive_pivot_to_vertex" in source
        assert "snap_authored_room_composition_primitive_pivot_to_vertex" in source
        assert "def transform_snap_authored_room_primitive_level" in source
        assert "transform_snap_authored_room_composition_primitive_level" in source
        assert "def authored_terrain_status" in source
        assert "previewable_status_query" in source

    assert "def set_universal_transform_overlay" in viewport_panel
    assert "def _sync_universal_transform_overlay" in viewport_panel
    assert "def set_map_studio_universal_transform_overlay" in viewport_scene_models
    assert "def clear_map_studio_universal_transform_overlay" in viewport_scene_models
    assert "def _draw_map_studio_universal_transform_overlay" in viewport_overlay_layers
    assert "self._draw_map_studio_universal_transform_overlay(draw, w, h)" in viewport_rendering
