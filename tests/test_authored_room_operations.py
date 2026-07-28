from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2651_controller_bevel_converts_rectangular_dev_room_to_floor_plan() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.apply_authored_room_operation(operation="bevel", distance=0.25)

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "floor_plan"
    assert len(primitive["points"]) == 8
    assert primitive["metadata"]["operation"] == "bevel"
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2910_controller_updates_floor_plan_extrusion_settings() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grextrude")

    result = controller.set_authored_floor_plan_extrusion(
        room_resref="grextrude_room01",
        z=0.5,
        wall_height=4.25,
        include_walls=False,
        floor_surface_id="4",
    )

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    choices = controller.authored_floor_plan_room_choices()
    assert primitive["type"] == "floor_plan"
    assert primitive["z"] == 0.5
    assert primitive["wall_height"] == 4.25
    assert primitive["include_walls"] is False
    assert primitive["floor_surface_id"] == 4
    assert primitive["metadata"]["last_operation"] == "floor_plan_extrusion_settings"
    assert choices[0].wall_height == 4.25
    assert choices[0].include_walls is False
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2604_controller_updates_module_entry_point_for_ifo_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grentry")

    result = controller.set_authored_module_entry_point(
        area_resref="grentry",
        position=(1.25, -2.5, 0.125),
        facing=math.pi,
    )

    entry = controller.authored_module_entry_point()
    payload = controller.project.extra_sections["authored_module"]
    assert entry is not None
    assert entry.area_resref == "grentry"
    assert entry.position == (1.25, -2.5, 0.125)
    assert entry.facing == math.pi
    assert payload["placements"]["entry_point"]["area_resref"] == "grentry"
    assert payload["placements"]["entry_point"]["position"] == [1.25, -2.5, 0.125]
    assert payload["placements"]["entry_point"]["facing"] == math.pi
    assert payload["game_tested"] is False
    assert result.readiness is not None


def test_t2909_controller_preserves_room_hint_without_writing_room_as_ifo_area() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grentry")

    controller.set_authored_module_entry_point(
        area_resref="grentry_room01",
        position=(0.5, 0.75, 0.125),
        facing=0.25,
    )

    entry = controller.authored_module_entry_point()
    payload = controller.project.extra_sections["authored_module"]
    assert entry.area_resref == "grentry"
    assert payload["placements"]["entry_point"]["area_resref"] == "grentry"
    assert payload["placements"]["metadata"]["entry_room_resref"] == "grentry_room01"
    assert payload["extra"]["entry_room_resref"] == "grentry_room01"
    assert payload["extra"]["last_entry_point_update"]["requested_area_resref"] == "grentry_room01"


def test_t2908_controller_deletes_and_undoes_player_start_without_rehydrating_marker() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grentrydel")

    row = controller.authored_module_entry_point_preview_row()
    assert row is not None
    assert row.placement_id == "entry_point"
    assert row.model_resref == "pmbam"
    assert row.head_model_resref == "pmhc01"

    result = controller.clear_authored_module_entry_point()
    payload = controller.project.extra_sections["authored_module"]
    assert payload["placements"]["entry_point"]["area_resref"] == ""
    assert controller.authored_module_entry_point().area_resref == ""
    assert controller.authored_module_entry_point_preview_row() is None
    assert all(marker.placement_id != "entry_point" for marker in controller.authored_gameplay_fallback_preview_markers())
    assert result.readiness.can_export_candidate is False

    controller.undo_map_studio_command()
    assert controller.authored_module_entry_point().area_resref == "grentrydel"
    assert controller.authored_module_entry_point_preview_row() is not None


def test_t2911_walkmesh_surface_assignment_preserves_room_texture() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grwokui")
    controller.apply_authored_room_style(texture="CM_CustomFloor", floor_surface="metal", room_resref="grwokui_room01")

    result = controller.set_authored_room_walkmesh_surface(room_resref="grwokui_room01", floor_surface="non_walk")

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    choices = controller.authored_walkmesh_room_surface_choices()
    assert primitive["material"]["texture"] == "CM_CustomFloor"
    assert primitive["floor_surface_id"] == 7
    assert choices[0].texture == "CM_CustomFloor"
    assert choices[0].floor_surface_id == 7
    assert choices[0].walkable is False
    assert result.readiness is not None


def test_t2651_rectangular_cut_splits_current_room_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcut01",
        game="K1",
    )
    cut = apply_authored_floor_plan_operation(
        project,
        "rectangular_cut",
        center=(0.0, 0.0),
        size=(2.0, 1.0),
        room_resref_prefix="grcutpiece",
    )
    build = build_authored_module(cut)

    assert len(cut.rooms) == 4
    assert {room.metadata["cut_piece_role"] for room in cut.rooms} == {"left", "right", "bottom", "top"}
    assert all(room.visible_rooms == tuple(room.normalised_resref() for room in cut.rooms) for room in cut.rooms)
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 4
    assert ("grcut01", "lyt") in build.resources
    assert ("grcut01", "vis") in build.resources
    assert all((room.normalised_resref(), "wok") in build.resources for room in cut.rooms)
    assert all((room.normalised_resref(), "mdl") in build.resources for room in cut.rooms)
    assert all((room.normalised_resref(), "mdx") in build.resources for room in cut.rooms)


def test_t2601_axis_split_creates_two_exportable_floor_plan_rooms() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsplit01",
        game="K1",
    )
    split = apply_authored_floor_plan_operation(
        project,
        "axis_split",
        axis="x",
        coordinate=0.0,
        room_resref_prefix="grsplitpiece",
    )
    build = build_authored_module(split)

    assert len(split.rooms) == 2
    assert {room.metadata["split_piece_role"] for room in split.rooms} == {"left", "right"}
    assert all(room.metadata["split_axis"] == "x" for room in split.rooms)
    assert all(room.visible_rooms == tuple(room.normalised_resref() for room in split.rooms) for room in split.rooms)
    assert split.placements.metadata["placement_repaired_after_axis_split"] is True
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 2
    assert ("grsplit01", "lyt") in build.resources
    assert ("grsplit01", "vis") in build.resources
    assert all((room.normalised_resref(), "wok") in build.resources for room in split.rooms)
    assert all((room.normalised_resref(), "mdl") in build.resources for room in split.rooms)
    assert all((room.normalised_resref(), "mdx") in build.resources for room in split.rooms)


def test_t2601_wall_opening_authoring_compiles_doorway_panels() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="gropen01",
        game="K1",
    )
    opened = apply_authored_floor_plan_operation(
        project,
        "wall_opening",
        name="south_door",
        edge_index=0,
        center_fraction=0.5,
        width=1.5,
        height=2.0,
        bottom=0.0,
    )
    room = opened.rooms[0]
    geometry = compile_floor_plan_room_geometry(room.primitive)
    build = build_authored_module(opened)
    readiness = build_authored_module_readiness(opened)

    assert room.metadata["last_opening_name"] == "south_door"
    assert len(room.primitive.openings) == 1
    assert readiness.can_preview is True
    assert readiness.geometry_validation.opening_count == 1
    assert readiness.metadata["geometry_validation"]["opening_count"] == 1
    assert readiness.doorway_transition.opening_count == 1
    assert readiness.doorway_transition.transition_marker_count == 1
    assert readiness.doorway_transition.ready is False
    assert "transition destination" in " ".join(readiness.doorway_transition.warnings)
    assert readiness.metadata["doorway_transition"]["opening_count"] == 1
    assert geometry.metadata["opening_count"] == 1
    assert any(mesh.metadata.get("opening_name") == "south_door" for mesh in geometry.helper_meshes)
    assert any(mesh.metadata.get("wall_panel") == "opening_lintel" for mesh in geometry.helper_meshes)
    assert not build.blocking_issues
    assert ("gropen01", "lyt") in build.resources
    assert (room.normalised_resref(), "wok") in build.resources
    assert (room.normalised_resref(), "mdl") in build.resources
    assert (room.normalised_resref(), "mdx") in build.resources


def test_t2601_wall_opening_can_create_linked_transition_marker() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="gropen02",
        game="K1",
    )
    opened = apply_authored_floor_plan_operation(
        project,
        "wall_opening",
        name="south_door",
        edge_index=0,
        center_fraction=0.5,
        width=1.5,
        height=2.0,
        bottom=0.0,
    )
    marked = apply_authored_floor_plan_operation(
        opened,
        "opening_transition_marker",
        room_resref=opened.rooms[0].room_resref,
        opening_name="south_door",
        marker_kind="trigger",
        template_resref="trg_exit",
        tag="south_exit_trigger",
        linked_to="wp_dest",
        linked_to_module="grnext01",
        linked_to_flags=2,
        transition_destination=2,
    )
    trigger = marked.placements.triggers[-1]
    readiness = build_authored_module_readiness(marked)
    marker_metadata = marked.extra["last_opening_transition_marker"]

    assert trigger.tag == "south_exit_trigger"
    assert trigger.template_resref == "trg_exit"
    assert trigger.position == (0.0, -5.0, 0.0)
    assert trigger.linked_to == "wp_dest"
    assert trigger.linked_to_module == "grnext01"
    assert trigger.linked_to_flags == 2
    assert trigger.transition_destination == 2
    assert marker_metadata["opening_name"] == "south_door"
    assert marker_metadata["marker_kind"] == "trigger"
    assert marker_metadata["position"] == [0.0, -5.0, 0.0]
    assert marker_metadata["linked_to_flags"] == 2
    assert marker_metadata["transition_destination"] == 2
    assert readiness.doorway_transition.opening_count == 1
    assert readiness.doorway_transition.transition_reference_count == 1
    assert readiness.doorway_transition.linked_transition_count == 1
    assert readiness.doorway_transition.ready is True


def test_t2679_controller_unions_adjacent_floor_plan_rooms_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grunion",
        game="K1",
    )
    material = PrimitiveMaterial(texture="default", metadata={"source": "test"})
    first_primitive = FloorPlanRoomPrimitive(
        room_resref="grunion_room01",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    second_primitive = FloorPlanRoomPrimitive(
        room_resref="grunion_room02",
        points=((5.0, -5.0), (10.0, -5.0), (10.0, 5.0), (5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    first_room = replace(
        base.rooms[0],
        room_resref="grunion_room01",
        primitive=first_primitive,
        composition=None,
        metadata={"primitive": "floor_plan_extrusion"},
    )
    second_room = AuthoredRoomSpec(
        room_resref="grunion_room02",
        primitive=second_primitive,
        visible_rooms=(),
        metadata={"primitive": "floor_plan_extrusion"},
    )
    visible = ("grunion_room01", "grunion_room02")
    project = replace(
        base,
        rooms=(
            replace(first_room, visible_rooms=visible),
            replace(second_room, visible_rooms=visible),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    choices = controller.authored_floor_plan_room_choices()
    result = controller.merge_authored_floor_plan_rooms(
        first_room_resref="grunion_room01",
        second_room_resref="grunion_room02",
        result_room_resref="grunion_merged",
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)

    assert [choice.room_resref for choice in choices] == ["grunion_room01", "grunion_room02"]
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert len(authored.rooms) == 1
    assert authored.rooms[0].room_resref == "grunion_merged"
    assert authored.rooms[0].visible_rooms == ("grunion_merged",)
    assert authored.rooms[0].metadata["last_operation"] == "rectangular_union"
    assert authored.rooms[0].metadata["merged_room_resrefs"] == ["grunion_room01", "grunion_room02"]
    assert tuple(authored.rooms[0].primitive.points) == ((-5.0, -5.0), (10.0, -5.0), (10.0, 5.0), (-5.0, 5.0))
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    export_objects = result.readiness.metadata["export_object_boundaries"] if result.readiness is not None else []
    merged_boundary = next(item for item in export_objects if item["export_resref"] == "grunion_merged")
    assert merged_boundary["source_operation"] == "rectangular_union"
    assert merged_boundary["source_room_resrefs"] == ["grunion_room01", "grunion_room02"]
    assert merged_boundary["resource_boundary_policy"] == "one_room_mdl_mdx_wok"
    assert merged_boundary["owns_walkmesh"] is True
    assert merged_boundary["dcc_handoff_status"] == "ready_for_external_uv"
    assert "MDL/MDX/WOK resref triplet" in merged_boundary["dcc_handoff_reason"]
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 1
    assert ("grunion_merged", "mdl") in build.resources
    assert ("grunion_merged", "mdx") in build.resources
    assert ("grunion_merged", "wok") in build.resources


def test_t2651_room_operation_requires_authored_module_payload() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="empty", game="K1")

    with pytest.raises(ValueError, match="No authored Map Studio module"):
        controller.apply_authored_room_operation(operation="inset", distance=0.25)


def test_t2665_controller_moves_authored_room_outline_point() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="doorway_blockout", module_root="grpoint")

    result = controller.move_authored_room_outline_point(
        room_resref="grpoint_room01",
        point_index=1,
        world_position=(6.5, -4.0, 0.0),
    )

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "floor_plan"
    assert primitive["points"][1] == [6.5, -4.0]
    assert primitive["metadata"]["last_vertex_edit"] == 1
    assert payload["rooms"][0]["metadata"]["last_operation"] == "move_floor_plan_point"


def test_t2908_controller_snaps_floor_plan_vertex_to_cross_room_vertex() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsnapv",
        game="K1",
    )
    material = PrimitiveMaterial(texture="default", metadata={"source": "test"})
    first_primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapv_room01",
        points=((-5.0, -5.0), (4.0, -5.0), (4.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    second_primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapv_room02",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    visible = ("grsnapv_room01", "grsnapv_room02")
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grsnapv_room01",
                primitive=first_primitive,
                composition=None,
                visible_rooms=visible,
                metadata={"primitive": "floor_plan_extrusion"},
            ),
            AuthoredRoomSpec(
                room_resref="grsnapv_room02",
                primitive=second_primitive,
                composition=None,
                position=(10.0, 0.0, 0.0),
                visible_rooms=visible,
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.snap_authored_floor_plan_vertex(
        room_resref="grsnapv_room01",
        point_index=1,
        target_point_index=0,
        target_room_resref="grsnapv_room02",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)

    assert tuple(authored.rooms[0].primitive.points)[1] == (5.0, -5.0)
    assert authored.rooms[0].metadata["last_operation"] == "snap_floor_plan_vertex"
    assert authored.rooms[0].metadata["snap_target_room"] == "grsnapv_room02"
    audit = authored.rooms[0].metadata["last_component_edit_audit"]
    assert audit["operation"] == "snap_floor_plan_vertex"
    assert audit["geometry_changed"] is True
    assert audit["topology_changed"] is False
    assert audit["walkmesh_review_required"] is True
    assert audit["game_proof_stale"] is True
    assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert audit["next_action"] == "Review WOK/walkability, regenerate affected runtime resources, then verify in game."
    assert "Review WOK surface intent before exporting the module." in audit["validation_messages"]
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.can_export_candidate is False
    assert result.readiness.export_status == "Stale runtime resources"
    assert result.readiness.component_edit.ready is False
    assert result.readiness.component_edit.status == "Needs WOK/export review"
    assert result.readiness.component_edit.latest_room_resref == "grsnapv_room01"
    assert result.readiness.component_edit.latest_operation == "snap_floor_plan_vertex"
    assert result.readiness.component_edit.walkmesh_review_required is True
    assert result.readiness.component_edit.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert (
        result.readiness.metadata["component_edit"]["next_action"]
        == "Review WOK/walkability, regenerate affected runtime resources, then verify in game."
    )
    assert result.readiness.metadata["component_edit"]["latest_operation"] == "snap_floor_plan_vertex"
    assert any(
        item.name == "Component edit audit" and item.ready is False
        for item in result.readiness.toolchain
    )
    assert not build.blocking_issues


def test_t2601_controller_lists_floor_plan_vertex_snap_candidates_without_mutating() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsnapq",
        game="K1",
    )
    material = PrimitiveMaterial(texture="default", metadata={"source": "test"})
    first_primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapq_room01",
        points=((-5.0, -5.0), (4.0, -5.0), (4.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    second_primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapq_room02",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=material,
        include_walls=True,
        metadata={"source": "test"},
    )
    visible = ("grsnapq_room01", "grsnapq_room02")
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grsnapq_room01",
                primitive=first_primitive,
                composition=None,
                visible_rooms=visible,
                metadata={"primitive": "floor_plan_extrusion"},
            ),
            AuthoredRoomSpec(
                room_resref="grsnapq_room02",
                primitive=second_primitive,
                composition=None,
                position=(10.0, 0.0, 0.0),
                visible_rooms=visible,
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)
    original_payload = controller.project.extra_sections["authored_module"]

    candidates = controller.authored_floor_plan_vertex_snap_candidates(
        room_resref="grsnapq_room01",
        point_index=1,
        limit=3,
    )

    assert [item.room_resref for item in candidates] == ["grsnapq_room02", "grsnapq_room01", "grsnapq_room01"]
    assert [item.point_index for item in candidates] == [0, 0, 2]
    assert candidates[0].world_position == (5.0, -5.0, 0.0)
    assert candidates[0].distance == 1.0
    assert candidates[0].same_room is False
    assert candidates[0].label == "grsnapq_room02 point 0 (1.000 m)"

    cross_only = controller.authored_floor_plan_vertex_snap_candidates(
        room_resref="grsnapq_room01",
        point_index=1,
        include_same_room=False,
        limit=2,
    )
    same_only = controller.authored_floor_plan_vertex_snap_candidates(
        room_resref="grsnapq_room01",
        point_index=1,
        include_cross_room=False,
        limit=1,
    )
    too_far = controller.authored_floor_plan_vertex_snap_candidates(
        room_resref="grsnapq_room01",
        point_index=1,
        max_distance=0.5,
    )

    assert [item.room_resref for item in cross_only] == ["grsnapq_room02", "grsnapq_room02"]
    assert same_only[0].room_resref == "grsnapq_room01"
    assert same_only[0].same_room is True
    assert too_far == ()
    assert controller.project.extra_sections["authored_module"] == original_payload
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert tuple(authored.rooms[0].primitive.points)[1] == (4.0, -5.0)


def test_t2908_controller_welds_floor_plan_vertices_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grweldv",
        game="K1",
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grweldv_room01",
        points=((-5.0, -5.0), (0.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grweldv_room01",
                primitive=primitive,
                composition=None,
                visible_rooms=("grweldv_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.weld_authored_floor_plan_vertices(
        room_resref="grweldv_room01",
        point_indices=(1, 2),
        target_point_index=2,
        position_policy="target",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)

    assert tuple(authored.rooms[0].primitive.points) == ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))
    assert authored.rooms[0].metadata["last_operation"] == "weld_floor_plan_vertices"
    assert authored.rooms[0].metadata["welded_vertices"] == [1, 2]
    audit = authored.rooms[0].metadata["last_component_edit_audit"]
    assert audit["operation"] == "weld_vertices"
    assert audit["geometry_changed"] is True
    assert audit["topology_changed"] is True
    assert audit["walkmesh_review_required"] is True
    assert audit["metadata"]["removed_vertex_count"] == 1
    assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert audit["next_action"] == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."
    assert "Re-run MDL/MDX/WOK generation and inspect LYT/VIS/PTH readiness before packaging." in audit["validation_messages"]
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.can_export_candidate is False
    assert result.readiness.export_status == "Stale runtime resources"
    assert result.readiness.component_edit.ready is False
    assert result.readiness.component_edit.latest_room_resref == "grweldv_room01"
    assert result.readiness.component_edit.latest_operation == "weld_vertices"
    assert result.readiness.component_edit.topology_changed is True
    assert result.readiness.component_edit.risky_edit_count == 1
    assert result.readiness.component_edit.next_action == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."
    assert "Re-run MDL/MDX/WOK generation and inspect LYT/VIS/PTH readiness before packaging." in result.readiness.warnings
    assert not build.blocking_issues


def test_t2908_controller_fills_triangulates_and_cleans_floor_plan_faces() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, polygon_signed_area
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grface")

    fill_result = controller.fill_authored_floor_plan_face(
        room_resref="grface_room01",
        point_indices=(0, 1, 2, 3),
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["last_operation"] == "fill_floor_plan_face"
    assert primitive.metadata["filled_face_indices"] == [0, 1, 2, 3]
    assert fill_result.readiness is not None
    assert fill_result.readiness.component_edit.latest_operation == "fill_face"
    assert fill_result.readiness.component_edit.topology_changed is True
    assert not build_authored_module(authored).blocking_issues

    triangulate_result = controller.triangulate_authored_floor_plan_face(room_resref="grface_room01")
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["last_operation"] == "triangulate_floor_plan_face"
    assert primitive.metadata["triangulated_faces"] == [[0, 1, 2], [0, 2, 3]]
    assert triangulate_result.readiness is not None
    assert triangulate_result.readiness.component_edit.latest_operation == "triangulate_faces"
    assert triangulate_result.readiness.component_edit.topology_changed is True
    assert not build_authored_module(authored).blocking_issues

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grnorm",
        game="K1",
    )
    clockwise = FloorPlanRoomPrimitive(
        room_resref="grnorm_room01",
        points=((-5.0, -5.0), (-5.0, 5.0), (5.0, 5.0), (5.0, -5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(replace(base.rooms[0], room_resref="grnorm_room01", primitive=clockwise),),
    )
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    normal_result = controller.cleanup_authored_floor_plan_normals(room_resref="grnorm_room01")
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["last_operation"] == "cleanup_floor_plan_normals"
    assert primitive.metadata["normal_cleanup_flipped_faces"] == 1
    assert polygon_signed_area(tuple(primitive.points)) > 0
    assert normal_result.readiness is not None
    assert normal_result.readiness.component_edit.latest_operation == "cleanup_face_normals"
    assert normal_result.readiness.component_edit.walkmesh_review_required is True
    assert not build_authored_module(authored).blocking_issues


def test_t2601_controller_records_selected_vertex_floor_plan_face_split() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grknife")

    result = controller.split_authored_floor_plan_face(
        room_resref="grknife_room01",
        point_indices=(0, 2),
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    audit = authored.rooms[0].metadata["last_component_edit_audit"]

    assert primitive.metadata["last_operation"] == "split_floor_plan_face"
    assert primitive.metadata["split_face_indices"] == [0, 2]
    assert primitive.metadata["split_faces"] == [[0, 1, 2], [2, 3, 0]]
    assert authored.rooms[0].metadata["last_operation"] == "split_floor_plan_face"
    assert audit["operation"] == "split_face_with_edge"
    assert audit["topology_changed"] is True
    assert audit["walkmesh_review_required"] is True
    assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert result.readiness is not None
    assert result.readiness.component_edit.ready is False
    assert result.readiness.component_edit.latest_operation == "split_face_with_edge"
    assert result.readiness.component_edit.topology_changed is True
    impacts = {row["resource"]: row for row in result.readiness.component_edit.resource_impacts}
    assert impacts["WOK"]["why_stale"] == "Walkmesh may no longer match the edited floor or openings."
    assert impacts["PTH"]["fix"] == "Rebuild PTH after walkmesh and entry/transition checks pass."
    assert impacts[".mod"]["fix"] == "Re-stage the .mod and record fresh in-game proof."
    assert result.readiness.metadata["component_edit"]["resource_impacts"][-1]["resource"] == ".mod"
    assert not build_authored_module(authored).blocking_issues


def test_t2908_controller_flattens_floor_plan_vertices_for_clean_wall_alignment() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grflatv",
        game="K1",
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grflatv_room01",
        points=((-5.0, -5.0), (4.8, -5.0), (5.2, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grflatv_room01",
                primitive=primitive,
                composition=None,
                visible_rooms=("grflatv_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.flatten_authored_floor_plan_vertices(
        room_resref="grflatv_room01",
        point_indices=(1, 2),
        axis="x",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)
    points = tuple(authored.rooms[0].primitive.points)

    assert points[1] == (5.0, -5.0)
    assert points[2] == (5.0, 5.0)
    assert authored.rooms[0].metadata["last_operation"] == "flatten_floor_plan_vertices"
    assert authored.rooms[0].metadata["flatten_axis"] == "x"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues


def test_t2606_controller_transform_level_snap_records_distinct_kmap_metadata() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsnapj",
        game="K1",
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapj_room01",
        points=((-5.0, -5.0), (4.5, -5.0), (5.5, 5.0), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grsnapj_room01",
                primitive=primitive,
                composition=None,
                visible_rooms=("grsnapj_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.transform_snap_authored_floor_plan_vertices(
        room_resref="grsnapj_room01",
        point_indices=(1, 2),
        axis="x",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)
    primitive = authored.rooms[0].primitive
    points = tuple(primitive.points)

    assert points[1] == (5.0, -5.0)
    assert points[2] == (5.0, 5.0)
    assert authored.rooms[0].metadata["last_operation"] == "transform_snap_floor_plan_vertices"
    assert authored.rooms[0].metadata["transform_snap_axis"] == "x"
    assert primitive.metadata["source"] == "map_studio:floor_plan_transform_level_snap"
    assert primitive.metadata["last_component_edit_audit"]["operation"] == "transform_snap_vertices_to_level"
    assert controller.command_history.undo_label == "Transform snap grsnapj_room01 vertices on x"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues


def test_t2606_controller_grid_snaps_floor_plan_vertices_without_welding() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsnapg",
        game="K1",
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grsnapg_room01",
        points=((-5.0, -5.0), (4.92, -4.96), (5.08, 5.07), (-5.0, 5.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grsnapg_room01",
                primitive=primitive,
                composition=None,
                visible_rooms=("grsnapg_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.grid_snap_authored_floor_plan_vertices(
        room_resref="grsnapg_room01",
        point_indices=(1, 2),
        grid_size=0.1,
        axes=("x", "y", "z"),
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)
    primitive = authored.rooms[0].primitive
    points = tuple((round(x, 3), round(y, 3)) for x, y in primitive.points)
    audit = primitive.metadata["last_component_edit_audit"]

    assert points == ((-5.0, -5.0), (4.9, -5.0), (5.1, 5.1), (-5.0, 5.0))
    assert authored.rooms[0].metadata["last_operation"] == "grid_snap_floor_plan_vertices"
    assert authored.rooms[0].metadata["grid_snap_vertices"] == [1, 2]
    assert authored.rooms[0].metadata["grid_snap_size"] == 0.1
    assert authored.rooms[0].metadata["grid_snap_axes"] == ["x", "y"]
    assert primitive.metadata["source"] == "map_studio:floor_plan_grid_snap"
    assert audit["operation"] == "snap_vertices_to_grid"
    assert audit["topology_changed"] is False
    assert audit["geometry_changed"] is True
    assert audit["walkmesh_review_required"] is True
    assert controller.command_history.undo_label == "Grid snap grsnapg_room01 vertices"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.can_export_candidate is False
    assert result.readiness.component_edit.latest_operation == "snap_vertices_to_grid"
    assert result.readiness.component_edit.topology_changed is False
    assert not build.blocking_issues


def test_t2908_controller_mirrors_floor_plan_footprint_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, polygon_signed_area
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grmirror",
        game="K1",
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grmirror_room01",
        points=((-6.0, -4.0), (2.0, -4.0), (4.0, 4.0), (-6.0, 4.0)),
        wall_height=3.0,
        floor_surface_id=4,
        material=PrimitiveMaterial(texture="default", metadata={"source": "test"}),
        include_walls=True,
        metadata={"source": "test"},
    )
    project = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grmirror_room01",
                primitive=primitive,
                composition=None,
                visible_rooms=("grmirror_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)

    result = controller.mirror_authored_floor_plan_vertices(room_resref="grmirror_room01", axis="x")
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = build_authored_module(authored)
    points = tuple(authored.rooms[0].primitive.points)

    assert points == ((3.0, 4.0), (-7.0, 4.0), (-5.0, -4.0), (3.0, -4.0))
    assert polygon_signed_area(points) > 0.0
    assert authored.rooms[0].metadata["last_operation"] == "mirror_floor_plan_vertices"
    assert authored.rooms[0].metadata["mirror_axis"] == "x"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues
    assert ("grmirror_room01", "mdl") in build.resources
    assert ("grmirror_room01", "wok") in build.resources


def test_t2908_controller_extrudes_floor_plan_edge_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grexedge")

    result = controller.apply_authored_room_operation(
        operation="edge_extrude",
        edge_index=0,
        distance=2.0,
        room_resref="grexedge_room01",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    build = build_authored_module(authored)

    assert tuple(primitive.points) == ((-5.0, -5.0), (-5.0, -7.0), (5.0, -7.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))
    assert primitive.metadata["operation"] == "edge_extrude"
    assert primitive.metadata["edge_index"] == 0
    assert primitive.metadata["edge_extrude_distance"] == 2.0
    assert authored.rooms[0].metadata["last_operation"] == "edge_extrude"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues
    assert ("grexedge_room01", "mdl") in build.resources
    assert ("grexedge_room01", "wok") in build.resources
    assert controller.project.dirty is True
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2908_controller_bridges_floor_plan_room_edges_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grbridge", game="K1")
    rectangle = ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))
    first_primitive = FloorPlanRoomPrimitive(room_resref="grbridge_a", points=rectangle)
    second_primitive = FloorPlanRoomPrimitive(room_resref="grbridge_b", points=rectangle)
    first_room = replace(
        base.rooms[0],
        room_resref="grbridge_a",
        primitive=first_primitive,
        composition=None,
        position=(0.0, 0.0, 0.0),
        visible_rooms=("grbridge_a", "grbridge_b"),
        metadata={"primitive": "floor_plan_extrusion"},
    )
    second_room = replace(
        base.rooms[0],
        room_resref="grbridge_b",
        primitive=second_primitive,
        composition=None,
        position=(14.0, 0.0, 0.0),
        visible_rooms=("grbridge_a", "grbridge_b"),
        metadata={"primitive": "floor_plan_extrusion"},
    )
    authored = replace(base, rooms=(first_room, second_room))
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)

    result = controller.bridge_authored_floor_plan_edges(
        first_room_resref="grbridge_a",
        first_edge_index=1,
        second_room_resref="grbridge_b",
        second_edge_index=3,
        result_room_resref="grbridge_link",
    )
    updated = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    bridge_room = next(room for room in updated.rooms if room.room_resref == "grbridge_link")
    bridge = bridge_room.primitive
    build = build_authored_module(updated)

    assert tuple(bridge.points) == ((5.0, -5.0), (5.0, 5.0), (9.0, 5.0), (9.0, -5.0))
    assert bridge.metadata["operation"] == "bridge_edges"
    assert bridge.metadata["first_room_resref"] == "grbridge_a"
    assert bridge.metadata["second_room_resref"] == "grbridge_b"
    assert bridge_room.metadata["last_operation"] == "bridge_edges"
    audit = bridge_room.metadata["last_component_edit_audit"]
    assert audit["operation"] == "bridge_edges"
    assert audit["component_kind"] == "floor_plan_edge"
    assert audit["topology_changed"] is True
    assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert bridge.metadata["last_component_edit_audit"] == audit
    assert tuple(bridge_room.visible_rooms) == ("grbridge_a", "grbridge_b", "grbridge_link")
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.component_edit.latest_room_resref == "grbridge_link"
    assert result.readiness.component_edit.latest_operation == "bridge_edges"
    assert result.readiness.component_edit.topology_changed is True
    assert not build.blocking_issues
    assert ("grbridge_a", "mdl") in build.resources
    assert ("grbridge_b", "mdl") in build.resources
    assert ("grbridge_link", "mdl") in build.resources
    assert ("grbridge_link", "wok") in build.resources
    assert controller.project.dirty is True


def test_t2908_controller_cleans_floor_plan_vertices_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grclean", game="K1")
    messy = FloorPlanRoomPrimitive(
        room_resref="grclean_room01",
        points=((-5.0, -5.0), (0.0, -5.0), (5.0, -5.0), (5.0, 5.0), (5.0, 5.0), (-5.0, 5.0), (-5.0, -5.0)),
    )
    room = replace(
        base.rooms[0],
        room_resref="grclean_room01",
        primitive=messy,
        composition=None,
        visible_rooms=("grclean_room01",),
        metadata={"primitive": "floor_plan_extrusion"},
    )
    authored = replace(base, rooms=(room,))
    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)

    result = controller.cleanup_authored_floor_plan_vertices(room_resref="grclean_room01", tolerance=0.001)
    updated = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = updated.rooms[0].primitive
    build = build_authored_module(updated)

    assert tuple(primitive.points) == ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))
    assert primitive.metadata["last_operation"] == "cleanup_floor_plan_vertices"
    assert primitive.metadata["cleanup_removed_point_count"] == 3
    assert updated.rooms[0].metadata["cleanup_removed_point_count"] == 3
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues
    assert ("grclean_room01", "mdl") in build.resources
    assert ("grclean_room01", "wok") in build.resources
    assert controller.project.dirty is True


def test_t2911_floor_plan_geometry_readiness_blocks_invalid_footprints_until_cleanup() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    base = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grgeo", game="K1")
    bad = FloorPlanRoomPrimitive(
        room_resref="grgeo_room01",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
    )
    authored = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grgeo_room01",
                primitive=bad,
                composition=None,
                visible_rooms=("grgeo_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )

    readiness = build_authored_module_readiness(authored)

    assert readiness.can_preview is False
    assert readiness.geometry_validation.ready is False
    assert readiness.geometry_validation.blocking_issue_count >= 1
    assert "duplicate points or zero-length edges" in " ".join(readiness.geometry_validation.blocking_messages)
    assert readiness.metadata["geometry_validation"]["ready"] is False
    assert any(status.name == "Floor-plan validation" and status.ready is False for status in readiness.toolchain)

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)

    result = controller.cleanup_authored_floor_plan_vertices(room_resref="grgeo_room01", tolerance=0.001)
    updated = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.geometry_validation.ready is True
    assert result.readiness.geometry_validation.blocking_issue_count == 0
    assert tuple(updated.rooms[0].primitive.points) == ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))


def test_t2911_floor_plan_geometry_readiness_warns_for_clockwise_winding() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    base = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grwind", game="K1")
    clockwise = FloorPlanRoomPrimitive(
        room_resref="grwind_room01",
        points=((-5.0, -5.0), (-5.0, 5.0), (5.0, 5.0), (5.0, -5.0)),
    )
    authored = replace(
        base,
        rooms=(
            replace(
                base.rooms[0],
                room_resref="grwind_room01",
                primitive=clockwise,
                composition=None,
                visible_rooms=("grwind_room01",),
                metadata={"primitive": "floor_plan_extrusion"},
            ),
        ),
    )

    readiness = build_authored_module_readiness(authored)

    assert readiness.can_preview is True
    assert readiness.geometry_validation.ready is True
    assert readiness.geometry_validation.warning_count >= 1
    assert "Cleanup Face Normals" in " ".join(readiness.geometry_validation.warnings)
    assert any(status.name == "Floor-plan validation" and status.status.startswith("Warnings") for status in readiness.toolchain)


def test_t2908_controller_persists_map_studio_tool_belt_preferences_in_kmap(tmp_path) -> None:
    _install_native_payload_paths()

    from src.core.level import KMapSerializer
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="beltprefs", game="K1")
    default_preferences = controller.map_studio_tool_belt_preferences()
    assert default_preferences.preset_key == "blockout"
    assert default_preferences.custom_action_keys == ()

    saved_preferences = controller.set_map_studio_tool_belt_preferences(
        preset_key="custom",
        custom_action_keys=("terrain", "bridge", "bridge", "missing", "validate"),
    )
    assert saved_preferences.preset_key == "custom"
    assert saved_preferences.custom_action_keys == ("terrain", "bridge", "validate")
    assert controller.project.extra_sections["map_studio_tool_belt"] == {
        "preset_key": "custom",
        "custom_action_keys": ["terrain", "bridge", "validate"],
    }

    path = tmp_path / "beltprefs.kmap"
    controller.save_project(path)
    reopened = ModuleEditorController()
    reopened.open_project(path)
    reopened_preferences = reopened.map_studio_tool_belt_preferences()
    raw = KMapSerializer.to_dict(reopened.project)

    assert reopened_preferences.preset_key == "custom"
    assert reopened_preferences.custom_action_keys == ("terrain", "bridge", "validate")
    assert raw["map_studio_tool_belt"]["custom_action_keys"] == ["terrain", "bridge", "validate"]


def test_t2908_controller_persists_map_studio_active_selection_in_kmap(tmp_path) -> None:
    _install_native_payload_paths()

    from src.core.level import KMapSerializer
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="selection", game="K1")

    selection = controller.set_map_studio_active_selection(
        component_mode="object",
        workspace_key="geometry",
        tool_key="select",
        room_resref="selection_room01",
        primitive_name="selection_room01_cube",
    )

    assert selection["selection_kind"] == "composition_primitive"
    assert controller.project.extra_sections["map_studio_active_selection"]["primitive_name"] == "selection_room01_cube"
    assert controller.command_history.undo_label == "Select selection_room01_cube"
    assert controller.command_history.undo_stack[-1].stale_outputs == ()

    path = tmp_path / "selection.kmap"
    controller.save_project(path)
    reopened = ModuleEditorController()
    reopened.open_project(path)
    raw = KMapSerializer.to_dict(reopened.project)

    assert reopened.map_studio_active_selection()["room_resref"] == "selection_room01"
    assert raw["map_studio_active_selection"]["component_mode"] == "object"
    assert raw["map_studio_active_selection"]["tool_key"] == "select"

    controller.undo_map_studio_command()

    assert controller.map_studio_active_selection() == {}


def test_t2668_controller_creates_elevation_composition_room_preset() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")

    result = controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grelev01")
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)

    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "composition"
    assert primitive["room_resref"] == "grelev01_room01"
    assert {item["type"] for item in primitive["primitives"]} >= {"wall", "ramp", "stairs", "arch"}
    assert len([item for item in primitive["primitives"] if item["type"] == "wall"]) == 4
    assert controller.project.name == "grelev01"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 1
    assert ("grelev01_room01", "mdl") in build.resources
    assert ("grelev01_room01", "wok") in build.resources
    assert build.module.room_geometry["grelev01_room01"].metadata["walkmesh_primitive_count"] == 2
    assert build.module.room_geometry["grelev01_room01"].wok.walkable_face_count() == 6


def test_t2908_controller_edits_terrain_heightfield_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr")

    choices = controller.authored_terrain_room_choices()
    result = controller.apply_authored_terrain_operation(
        operation="set_height",
        room_resref="grterr_room01",
        row_index=2,
        column_index=2,
        height=0.8,
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    geometry = build.module.room_geometry["grterr_room01"]

    assert [choice.room_resref for choice in choices] == ["grterr_room01"]
    assert choices[0].row_count == 5
    assert choices[0].column_count == 5
    assert choices[0].walkable_triangle_count > 0
    assert choices[0].non_walk_triangle_count == 0
    assert "walk / 0 blocked" in choices[0].label
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert payload["rooms"][0]["primitive"]["type"] == "terrain_heightfield"
    assert payload["rooms"][0]["primitive"]["heights"][2][2] == 0.8
    assert payload["rooms"][0]["metadata"]["last_operation"] == "terrain_set_height"
    assert not build.blocking_issues
    assert geometry.room_mesh.metadata["height_max"] == 0.8
    assert geometry.wok.walkable_face_count() > 0


def test_t2908_controller_smooths_and_flattens_terrain_heightfield() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr")
    controller.apply_authored_terrain_operation(
        operation="raise",
        room_resref="grterr_room01",
        row_index=2,
        column_index=2,
        delta=0.4,
        radius=1,
    )
    controller.apply_authored_terrain_operation(
        operation="smooth",
        room_resref="grterr_room01",
        iterations=1,
        strength=0.5,
    )
    result = controller.apply_authored_terrain_operation(
        operation="flatten",
        room_resref="grterr_room01",
        height=0.1,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    heights = authored.rooms[0].primitive.heights

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert all(value == 0.1 for row in heights for value in row)
    assert authored.rooms[0].primitive.metadata["last_operation"] == "flatten"


def test_t2603_controller_applies_local_terrain_brush_stroke_with_dirty_region() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grbrush")
    before = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    before_heights = before.rooms[0].primitive.heights

    result = controller.apply_authored_terrain_operation(
        operation="brush_stroke:raise",
        room_resref="grbrush_room01",
        row_index=2,
        column_index=2,
        delta=0.5,
        radius=1,
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    terrain = authored.rooms[0].primitive
    build = build_authored_module(authored)
    dirty = terrain.metadata["last_dirty_region"]

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert terrain.metadata["last_operation"] == "terrain_brush_stroke"
    assert terrain.metadata["last_brush"] == "raise"
    assert terrain.metadata["dirty_region_only"] is True
    assert terrain.metadata["defer_full_rebuild_until_stroke_end"] is True
    assert dirty == {
        "min_row": 1,
        "max_row": 3,
        "min_column": 1,
        "max_column": 3,
        "changed_sample_count": 5,
    }
    brush_performance = terrain.metadata["last_brush_performance"]
    assert brush_performance["within_budget"] is True
    assert brush_performance["budget_ms"] == 8.0
    assert brush_performance["affected_sample_count"] == 5
    assert brush_performance["dirty_region"] == dirty
    assert "defer full MDL/WOK rebuild" in brush_performance["rebuild_policy"]
    assert terrain.heights[2][2] == before_heights[2][2] + 0.5
    assert terrain.heights[0][0] == before_heights[0][0]
    assert payload["rooms"][0]["metadata"]["last_operation"] == "terrain_brush_stroke"
    assert not build.blocking_issues


def test_t2603_controller_applies_terrace_and_noise_terrain_brushes() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grnatural")
    controller.apply_authored_terrain_operation(
        operation="shape_preset:ramp",
        room_resref="grnatural_room01",
        height=0.9,
    )

    controller.apply_authored_terrain_operation(
        operation="brush_stroke:terrace",
        room_resref="grnatural_room01",
        row_index=2,
        column_index=2,
        height=0.25,
        radius=2,
        strength=1.0,
    )
    terraced = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    terraced_terrain = terraced.rooms[0].primitive
    terraced_heights = terraced_terrain.heights

    assert terraced_terrain.metadata["last_operation"] == "terrain_brush_stroke"
    assert terraced_terrain.metadata["last_brush"] == "terrace"
    assert terraced_terrain.metadata["dirty_region_only"] is True
    assert "last_brush_slope_report" in terraced_terrain.metadata

    controller.apply_authored_terrain_operation(
        operation="brush_stroke:noise",
        room_resref="grnatural_room01",
        row_index=2,
        column_index=2,
        delta=0.05,
        radius=2,
        strength=0.75,
    )
    noised = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    noised_terrain = noised.rooms[0].primitive
    slope_report = noised_terrain.metadata["last_brush_slope_report"]

    assert noised_terrain.metadata["last_brush"] == "noise"
    assert noised_terrain.metadata["last_operation"] == "terrain_brush_stroke"
    assert noised_terrain.metadata["last_dirty_region"]["changed_sample_count"] >= 5
    assert noised_terrain.heights != terraced_heights
    assert slope_report["walkable_triangle_count"] + slope_report["non_walk_triangle_count"] > 0
    assert isinstance(slope_report["warnings"], list)


def test_t2603_controller_applies_plateau_ramp_pinch_and_erode_terrain_brushes() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grsculpt")
    controller.apply_authored_terrain_operation(
        operation="shape_preset:ramp",
        room_resref="grsculpt_room01",
        height=0.8,
    )

    controller.apply_authored_terrain_operation(
        operation="brush_stroke:plateau",
        room_resref="grsculpt_room01",
        row_index=2,
        column_index=2,
        radius=1,
        strength=1.0,
    )
    plateau = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    plateau_terrain = plateau.rooms[0].primitive
    assert plateau_terrain.metadata["last_brush"] == "plateau"
    assert plateau_terrain.metadata["dirty_region_only"] is True

    controller.apply_authored_terrain_operation(
        operation="brush_stroke:ramp",
        room_resref="grsculpt_room01",
        points=((0, 0, 1.0), (4, 4, 1.0)),
        delta=0.6,
        height=1.25,
        radius=1,
        strength=1.0,
    )
    ramped = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    ramped_terrain = ramped.rooms[0].primitive
    assert ramped_terrain.metadata["last_brush"] == "ramp"
    assert ramped_terrain.heights[-1][-1] > plateau_terrain.heights[0][0]

    controller.apply_authored_terrain_operation(
        operation="brush_stroke:slope",
        room_resref="grsculpt_room01",
        points=((0, 4, 1.0), (2, 2, 1.0), (4, 0, 1.0)),
        height=0.9,
        radius=0,
        strength=1.0,
        symmetry_axis="column",
    )
    sloped = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    sloped_terrain = sloped.rooms[0].primitive
    assert sloped_terrain.metadata["last_brush"] == "slope"
    assert sloped_terrain.metadata["last_brush_symmetry_axis"] == "column"
    assert sloped_terrain.metadata["last_input_stroke_point_count"] == 3
    assert sloped_terrain.metadata["last_dirty_region"]["changed_sample_count"] == 5
    assert sloped_terrain.metadata["last_brush_slope_report"]["walkable_triangle_count"] > 0

    controller.apply_authored_terrain_operation(
        operation="set_height",
        room_resref="grsculpt_room01",
        row_index=2,
        column_index=2,
        height=2.0,
    )
    before_pinch = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"]).rooms[0].primitive
    controller.apply_authored_terrain_operation(
        operation="brush_stroke:pinch",
        room_resref="grsculpt_room01",
        row_index=2,
        column_index=2,
        radius=1,
        strength=0.75,
    )
    pinched = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    pinched_terrain = pinched.rooms[0].primitive
    assert pinched_terrain.metadata["last_brush"] == "pinch"
    assert pinched_terrain.heights[1][2] > before_pinch.heights[1][2]

    before_erode_center = pinched_terrain.heights[2][2]
    controller.apply_authored_terrain_operation(
        operation="brush_stroke:erode",
        room_resref="grsculpt_room01",
        row_index=2,
        column_index=2,
        delta=0.05,
        radius=1,
        strength=1.0,
    )
    eroded = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    eroded_terrain = eroded.rooms[0].primitive
    assert eroded_terrain.metadata["last_brush"] == "erode"
    assert eroded_terrain.heights[2][2] < before_erode_center
    assert eroded_terrain.metadata["last_brush_performance"]["within_budget"] is True


def test_t2603_controller_prepares_and_applies_live_terrain_sculpt_frame_without_full_rebuild() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grlive")
    before = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    before_heights = before.rooms[0].primitive.heights

    frame = controller.prepare_map_studio_terrain_sculpt_frame(
        room_resref="grlive_room01",
        brush="raise",
        points=((1, 1), (1, 1, 0.8), (2, 2), (3, 3), (4, 4)),
        delta=0.25,
        radius=1,
        max_points_per_frame=3,
        budget_ms=8.0,
    )

    assert frame.raw_sample_count == 5
    assert frame.applied_sample_count == 3
    assert frame.coalesced_sample_count == 2
    assert frame.should_apply_live is True
    assert frame.defer_full_rebuild is True
    assert frame.performance.within_budget is True
    assert frame.operation == "brush_stroke:raise"
    assert len(frame.operation_kwargs["points"]) == 3
    assert "Coalesced 5 raw pointer sample" in " ".join(frame.warnings)

    result = controller.apply_map_studio_terrain_sculpt_frame(
        room_resref="grlive_room01",
        brush="raise",
        points=((1, 1), (1, 1, 0.8), (2, 2), (3, 3), (4, 4)),
        delta=0.25,
        radius=1,
        max_points_per_frame=3,
        budget_ms=8.0,
    )
    # Live frames mutate only the stroke-owned flat buffer.  KMAP remains
    # byte-for-byte untouched until release/commit.
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    terrain = authored.rooms[0].primitive

    assert result.applied is True
    assert result.full_rebuild_deferred is True
    assert "KMAP serialization remain deferred" in result.message
    assert result.project_serialized is False
    assert result.dirty_height_patch
    assert terrain.heights == before_heights

    def _unexpected_readiness_rebuild():
        raise AssertionError("terrain stroke commit must not run full authored-module readiness")

    controller.authored_module_readiness = _unexpected_readiness_rebuild
    commit = controller.commit_map_studio_terrain_sculpt_stroke(brush="raise", room_resref="grlive_room01")
    assert commit is not None
    assert commit.serialization_count == 1
    assert commit.decode_count == 1
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    terrain = authored.rooms[0].primitive

    assert terrain.metadata["last_operation"] == "terrain_brush_stroke"
    assert terrain.metadata["dirty_region_only"] is True
    assert terrain.metadata["defer_full_rebuild_until_stroke_end"] is True
    assert terrain.metadata["last_brush_performance"]["within_budget"] is True
    assert any(
        terrain.heights[row_index][column_index] > before_heights[row_index][column_index]
        for row_index in range(len(terrain.heights))
        for column_index in range(len(terrain.heights[row_index]))
    )
    assert payload["rooms"][0]["metadata"]["last_operation"] == "terrain_brush_stroke"


def test_t2603_terrain_brush_audit_flags_over_budget_strokes_for_coalescing() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, audit_terrain_brush_stroke_interaction

    heights = tuple(tuple(0.0 for _column in range(64)) for _row in range(64))
    terrain = TerrainHeightfieldPrimitive(room_resref="grperf", heights=heights, width=64.0, depth=64.0)
    audit = audit_terrain_brush_stroke_interaction(
        terrain,
        brush="smooth",
        radius=12,
        iterations=4,
        points=((32, 32), (33, 33), (34, 34)),
        budget_ms=1.0,
    )

    assert audit.within_budget is False
    assert audit.affected_sample_count > 100
    assert audit.dirty_region.min_row < 32
    assert audit.dirty_region.max_row > 34
    assert "coalesce input samples" in " ".join(audit.warnings)


def test_t2907_controller_applies_terrain_shape_preset_and_repairs_ground_markers() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_terrain_builder import sample_terrain_height
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr")

    result = controller.apply_authored_terrain_operation(
        operation="shape_preset:ramp",
        room_resref="grterr_room01",
        height=0.6,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    terrain = authored.rooms[0].primitive
    entry = authored.placements.entry_point.position
    build = build_authored_module(authored)

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert terrain.metadata["last_shape_preset_id"] == "ramp"
    assert terrain.heights[0][0] < terrain.heights[-1][0]
    assert entry[2] == sample_terrain_height(terrain, x=entry[0], y=entry[1])
    assert not build.blocking_issues


def test_t2907_terrain_room_choices_report_blocked_slope_status() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr")
    controller.apply_authored_terrain_operation(
        operation="set_height",
        room_resref="grterr_room01",
        row_index=2,
        column_index=2,
        height=4.0,
    )

    choices = controller.authored_terrain_room_choices()

    assert len(choices) == 1
    assert choices[0].walkable_triangle_count + choices[0].non_walk_triangle_count == 32
    assert choices[0].non_walk_triangle_count > 0
    assert choices[0].max_slope_degrees > 35.0
    assert "blocked" in choices[0].label


def test_t2670_controller_sets_composition_primitive_transform_and_preserves_exportable_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grprim")

    readiness = controller.set_authored_room_primitive_transform(
        room_resref="grprim_room01",
        primitive_name="grprim_room01_ramp",
        translation=(1.0, 2.0, 0.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
    )
    payload = controller.project.extra_sections["authored_module"]
    primitive_payload = payload["rooms"][0]["primitive"]
    ramp_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grprim_room01_ramp")
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    wok = build.module.room_geometry["grprim_room01"].wok

    assert readiness.readiness is not None
    assert readiness.readiness.can_preview is True
    assert controller.project.dirty is True
    assert primitive_payload["type"] == "composition"
    assert ramp_payload["transform"]["translation"] == [1.0, 2.0, 0.0]
    assert not build.blocking_issues
    assert wok.verts[4] == (0.0, 0.25, 0.0)
    assert wok.walkable_face_count() == 6


def test_t2670_transforming_missing_composition_primitive_fails_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_operations import set_authored_room_composition_primitive_transform
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grprim",
        game="K1",
    )

    with pytest.raises(ValueError, match="no primitive named 'missing_ramp'"):
        set_authored_room_composition_primitive_transform(
            project,
            room_resref="grprim_room01",
            primitive_name="missing_ramp",
            translation=(0.0, 0.0, 0.0),
        )


def test_t2677_controller_moves_composition_primitive_by_viewport_delta() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grdrag")

    result = controller.move_authored_room_primitive(
        room_resref="grdrag_room01",
        primitive_name="grdrag_room01_ramp",
        world_delta=(0.5, -1.0, 0.0),
    )
    payload = controller.project.extra_sections["authored_module"]
    primitive_payload = payload["rooms"][0]["primitive"]
    ramp_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grdrag_room01_ramp")
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    wok = build.module.room_geometry["grdrag_room01"].wok

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert ramp_payload["transform"]["translation"] == [-2.25, -0.5, 0.0]
    assert wok.verts[4] == (-3.25, -2.25, 0.0)
    assert controller.project.dirty is True
    assert not build.blocking_issues


def test_t2671_controller_lists_composition_primitives_for_builder_tab() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grui")

    rows = controller.authored_room_primitive_transforms()
    ramp = next(row for row in rows if row.primitive_name == "grui_room01_ramp")

    assert len(rows) >= 7
    assert ramp.room_resref == "grui_room01"
    assert ramp.primitive_type == "ramp"
    assert ramp.translation == (-2.75, 0.5, 0.0)
    assert ramp.scale == (1.0, 1.0, 1.0)


def test_t2672_controller_adds_composition_primitive_for_builder_tab() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="gradd")

    result = controller.add_authored_room_primitive(
        primitive_kind="cube",
        primitive_name="gradd_room01_crate",
        translation=(1.0, 1.5, 0.0),
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    primitive_payload = payload["rooms"][0]["primitive"]
    cube_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "gradd_room01_crate")

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert cube_payload["type"] == "cube"
    assert cube_payload["transform"]["translation"] == [1.0, 1.5, 0.0]
    assert controller.project.dirty is True
    assert not build.blocking_issues
    assert ("gradd_room01", "mdl") in build.resources


def test_t2908_controller_adds_plane_composition_primitive_and_generates_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grplane")

    result = controller.add_authored_room_primitive(
        primitive_kind="plane",
        primitive_name="grplane_room01_platform",
        translation=(2.0, 0.0, 0.25),
        floor_surface=4,
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    primitive_payload = payload["rooms"][0]["primitive"]
    plane_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grplane_room01_platform")
    plane_row = next(row for row in controller.authored_room_primitive_transforms() if row.primitive_name == "grplane_room01_platform")
    wok = build.module.room_geometry["grplane_room01"].wok

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert plane_payload["type"] == "plane"
    assert plane_payload["width"] == 3.0
    assert plane_payload["depth"] == 3.0
    assert plane_payload["surface_id"] == 4
    assert plane_payload["transform"]["translation"] == [2.0, 0.0, 0.25]
    assert plane_row.primitive_type == "plane"
    assert plane_row.supports_walkmesh_surface is True
    assert {dimension.key for dimension in plane_row.dimensions} == {
        "width",
        "depth",
        "subdivisions_width",
        "subdivisions_depth",
    }
    assert {property_row.key for property_row in plane_row.properties} >= {
        "width",
        "depth",
        "subdivisions_width",
        "subdivisions_depth",
        "axis_x",
        "axis_y",
        "axis_z",
        "height_baseline",
        "create_uvs",
    }
    assert len(wok.faces) >= 4
    assert build.module.room_geometry["grplane_room01"].metadata["walkmesh_primitive_count"] >= 3
    assert not build.blocking_issues


def test_t2908_controller_adds_door_frame_and_arch_as_separate_primitives() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grdoor")

    result = controller.add_authored_room_primitive(
        primitive_kind="door_frame",
        primitive_name="grdoor_room01_frame",
        translation=(0.0, 4.0, 0.0),
    )
    arch_result = controller.add_authored_room_primitive(
        primitive_kind="arch",
        primitive_name="grdoor_room01_curved_entry",
        translation=(0.0, -4.0, 0.0),
    )
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    primitive_payload = payload["rooms"][0]["primitive"]
    frame_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grdoor_room01_frame")
    arch_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grdoor_room01_curved_entry")
    frame_row = next(row for row in controller.authored_room_primitive_transforms() if row.primitive_name == "grdoor_room01_frame")
    arch_row = next(row for row in controller.authored_room_primitive_transforms() if row.primitive_name == "grdoor_room01_curved_entry")

    assert result.readiness is not None
    assert arch_result.readiness is not None
    assert frame_payload["type"] == "door_frame"
    assert frame_payload["transform"]["translation"] == [0.0, 4.0, 0.0]
    assert frame_row.primitive_type == "door_frame"
    assert frame_row.supports_walkmesh_surface is False
    assert {dimension.key for dimension in frame_row.dimensions} == {"width", "height", "jamb_width", "lintel_height", "depth"}
    assert arch_payload["type"] == "arch"
    assert arch_payload["transform"]["translation"] == [0.0, -4.0, 0.0]
    assert arch_row.primitive_type == "arch"
    assert {dimension.key for dimension in arch_row.dimensions} == {"width", "height", "frame_thickness", "depth", "segments"}
    assert not build.blocking_issues
    assert ("grdoor_room01", "mdl") in build.resources


def test_t2673_controller_edits_composition_primitive_dimensions() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grdim")

    result = controller.set_authored_room_primitive_dimensions(
        room_resref="grdim_room01",
        primitive_name="grdim_room01_ramp",
        dimensions={"width": 3.0, "length": 5.0, "height": 2.0},
    )
    payload = controller.project.extra_sections["authored_module"]
    primitive_payload = payload["rooms"][0]["primitive"]
    ramp_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grdim_room01_ramp")
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    wok = build.module.room_geometry["grdim_room01"].wok

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert ramp_payload["width"] == 3.0
    assert ramp_payload["length"] == 5.0
    assert ramp_payload["height"] == 2.0
    assert wok.verts[4] == (-4.25, -2.0, 0.0)
    assert not build.blocking_issues


def test_t2673_rejects_unknown_primitive_dimension_key() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_operations import set_authored_room_composition_primitive_dimensions
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grdim",
        game="K1",
    )

    with pytest.raises(ValueError, match="does not support dimension"):
        set_authored_room_composition_primitive_dimensions(
            project,
            room_resref="grdim_room01",
            primitive_name="grdim_room01_ramp",
            dimensions={"radius": 2.0},
        )


def test_t2674_controller_removes_composition_primitive_for_builder_tab() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grrem")

    result = controller.remove_authored_room_primitive(
        room_resref="grrem_room01",
        primitive_name="grrem_room01_ramp",
    )
    payload = controller.project.extra_sections["authored_module"]
    primitive_payload = payload["rooms"][0]["primitive"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    wok = build.module.room_geometry["grrem_room01"].wok

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert all(item["name"] != "grrem_room01_ramp" for item in primitive_payload["primitives"])
    assert wok.walkable_face_count() == 4
    assert not build.blocking_issues


def test_t2601_controller_separates_composition_primitive_into_exportable_room() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grsep")

    result = controller.separate_authored_room_primitive(
        room_resref="grsep_room01",
        primitive_name="grsep_room01_ramp",
        result_room_resref="grsep_ramp",
    )

    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    source_room = next(room for room in payload["rooms"] if room["room_resref"] == "grsep_room01")
    separated_room = next(room for room in payload["rooms"] if room["room_resref"] == "grsep_ramp")
    source_primitives = source_room["primitive"]["primitives"]
    separated_primitives = separated_room["primitive"]["primitives"]
    primitive_rows = controller.authored_room_primitive_transforms()
    export_objects = controller.map_studio_export_object_boundaries()
    readiness = result.readiness
    readiness_export_objects = readiness.metadata["export_object_boundaries"] if readiness is not None else []

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert len(payload["rooms"]) == 2
    assert all(item["name"] != "grsep_room01_ramp" for item in source_primitives)
    assert [item["name"] for item in separated_primitives] == ["grsep_room01_ramp"]
    assert separated_room["primitive"]["metadata"]["separated_from_room"] == "grsep_room01"
    assert separated_room["visible_rooms"] == ["grsep_room01", "grsep_ramp"]
    assert any(row.room_resref == "grsep_ramp" and row.primitive_name == "grsep_room01_ramp" for row in primitive_rows)
    assert len(export_objects) == 2
    separated_boundary = next(boundary for boundary in export_objects if boundary.export_resref == "grsep_ramp")
    readiness_boundary = next(boundary for boundary in readiness_export_objects if boundary["export_resref"] == "grsep_ramp")
    assert separated_boundary.object_kind == "separated_primitive_object"
    assert separated_boundary.source_operation == "separate_composition_primitive"
    assert separated_boundary.source_room_resrefs == ("grsep_room01",)
    assert separated_boundary.owns_walkmesh is True
    assert separated_boundary.dcc_handoff_status == "ready_for_external_uv"
    assert "Separated object can be UV/textured externally" in separated_boundary.dcc_handoff_reason
    assert readiness_boundary["uv_handoff_recommended"] is True
    assert readiness_boundary["resource_boundary_policy"] == "one_room_mdl_mdx_wok"
    assert readiness_boundary["owns_walkmesh"] is True
    assert readiness_boundary["dcc_handoff_status"] == "ready_for_external_uv"
    assert readiness_boundary["source_operation"] == "separate_composition_primitive"
    assert readiness_boundary["source_room_resrefs"] == ["grsep_room01"]
    assert ("grsep_room01", "mdl") in build.resources
    assert ("grsep_ramp", "mdl") in build.resources
    assert not build.blocking_issues


def test_t2674_removing_missing_composition_primitive_fails_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_operations import remove_authored_room_composition_primitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grrem",
        game="K1",
    )

    with pytest.raises(ValueError, match="no primitive named 'missing_cube'"):
        remove_authored_room_composition_primitive(
            project,
            room_resref="grrem_room01",
            primitive_name="missing_cube",
        )


def test_t2676_controller_styles_composition_primitive_material_and_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grstylep")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["stale.mod"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.set_authored_room_primitive_style(
        room_resref="grstylep_room01",
        primitive_name="grstylep_room01_ramp",
        texture="LME_Floor01.tga",
        surface_id="metal",
    )
    updated = controller.project.extra_sections["authored_module"]
    primitive_payload = updated["rooms"][0]["primitive"]
    ramp_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grstylep_room01_ramp")
    authored = authored_project_from_kmap_payload(updated)
    build = build_authored_module(authored)
    geometry = build.module.room_geometry["grstylep_room01"]
    ramp_mesh = next(mesh for mesh in geometry.helper_meshes if mesh.name == "grstylep_room01_ramp")

    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert ramp_payload["material"]["texture"] == "LME_Floor01"
    assert ramp_payload["surface_id"] == 10
    assert ramp_mesh.texture == "LME_Floor01"
    assert 10 in {face.surface for face in geometry.wok.faces}
    assert not build.blocking_issues


def test_t2676_visual_composition_primitive_rejects_walkmesh_surface() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_operations import set_authored_room_composition_primitive_style
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grstylep",
        game="K1",
    )

    with pytest.raises(ValueError, match="does not contribute walkmesh faces"):
        set_authored_room_composition_primitive_style(
            project,
            room_resref="grstylep_room01",
            primitive_name="grstylep_room01_arch",
            texture="CM_Baremetal",
            surface_id="metal",
        )


def test_t2651_builder_tab_exposes_room_operation_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioRoomOperationComboBox" in source
    assert "mapStudioApplyRoomOperationButton" in source
    assert "roomOperationRequested" in source
    assert "self.builder_tab.roomOperationRequested.connect(self.apply_authored_room_operation)" in window_source
    assert "self.controller.apply_authored_room_operation" in window_source


def test_t2908_builder_tab_exposes_terrain_heightfield_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    native_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    for panel_source in (source, native_source):
        assert "terrainOperationRequested" in panel_source
        assert "mapStudioTerrainRoomComboBox" in panel_source
        assert "mapStudioTerrainShapePresetComboBox" in panel_source
        assert "mapStudioApplyTerrainShapePresetButton" in panel_source
        assert "walkable_triangle_count" in panel_source
        assert "non_walk_triangle_count" in panel_source
        assert "Blocked triangles export as NON_WALK" in panel_source
        assert "mapStudioTerrainRowSpinBox" in panel_source
        assert "mapStudioSetTerrainHeightButton" in panel_source
        assert "mapStudioSmoothTerrainButton" in panel_source
        assert "def set_terrain_shape_presets" in panel_source
        assert "def set_terrain_room_choices" in panel_source
        assert "self.builder_tab.set_terrain_shape_presets(self.controller.available_authored_terrain_shape_presets())" in window_source
        assert "self.builder_tab.terrainOperationRequested.connect(self.apply_authored_terrain_operation)" in window_source
    assert "self.controller.apply_authored_terrain_operation" in window_source
    assert "self.builder_tab.set_terrain_room_choices(authored_terrain_rooms)" in window_source


def test_t2679_builder_tab_exposes_rectangular_union_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    native_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    for panel_source in (source, native_source):
        assert "roomRectangularUnionRequested" in panel_source
        assert "floorPlanUnionFirstRoomComboBox" in panel_source
        assert "floorPlanUnionSecondRoomComboBox" in panel_source
        assert "floorPlanUnionResultRoomLineEdit" in panel_source
        assert "mapStudioApplyRectangularUnionButton" in panel_source
        assert "def set_floor_plan_room_choices" in panel_source
        assert "def _emit_rectangular_union" in panel_source
    assert "self.builder_tab.roomRectangularUnionRequested.connect(self.merge_authored_floor_plan_rooms)" in window_source
    assert "self.controller.merge_authored_floor_plan_rooms" in window_source
    assert "self.builder_tab.set_floor_plan_room_choices(authored_floor_plan_rooms)" in window_source


def test_t2910_builder_tab_exposes_floor_plan_extrusion_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.GUI.Boundary.Panels"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    native_source = (
        repo
        / "native"
        / "GhostRigger.Tools.Workflow.ModuleMeshes"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Windows.Editor.Level"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    for panel_source in (source, native_source):
        assert "floorPlanExtrusionRequested" in panel_source
        assert "mapStudioFloorPlanExtrusionRoomComboBox" in panel_source
        assert "mapStudioFloorPlanWallHeightSpinBox" in panel_source
        assert "mapStudioFloorPlanFloorZSpinBox" in panel_source
        assert "mapStudioFloorPlanIncludeWallsCheckBox" in panel_source
        assert "mapStudioFloorPlanSurfaceComboBox" in panel_source
        assert "mapStudioApplyFloorPlanExtrusionButton" in panel_source
        assert "def _emit_floor_plan_extrusion" in panel_source
        assert "wall_height" in panel_source
        assert "include_walls" in panel_source
    assert "self.builder_tab.floorPlanExtrusionRequested.connect(self.apply_authored_floor_plan_extrusion)" in window_source
    assert "self.controller.set_authored_floor_plan_extrusion" in window_source


def test_t2671_builder_tab_exposes_composition_primitive_transform_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "roomPrimitiveTransformRequested" in source
    assert "mapStudioRoomPrimitiveTransformComboBox" in source
    assert "mapStudioApplyPrimitiveTransformButton" in source
    assert "def set_room_primitives" in source
    assert "def _emit_primitive_transform" in source
    assert "self.builder_tab.roomPrimitiveTransformRequested.connect(self.apply_authored_room_primitive_transform)" in window_source
    assert "self.controller.set_authored_room_primitive_transform" in window_source
    assert "self.builder_tab.set_room_primitives(authored_room_primitives)" in window_source


def test_t2672_builder_tab_exposes_add_composition_primitive_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "roomPrimitiveAddRequested" in source
    assert "mapStudioCompositionPrimitiveKindComboBox" in source
    assert "mapStudioAddCompositionPrimitiveButton" in source
    assert "def set_composition_primitive_kinds" in source
    assert "self.builder_tab.set_composition_primitive_kinds(self.controller.available_authored_composition_primitive_kinds())" in window_source
    assert "self.builder_tab.roomPrimitiveAddRequested.connect(self.add_authored_room_primitive)" in window_source
    assert "self.controller.add_authored_room_primitive" in window_source


def test_t2673_builder_tab_exposes_primitive_dimension_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "roomPrimitiveDimensionsRequested" in source
    assert "roomPrimitiveDimensionsPreviewRequested" in source
    assert "roomPrimitiveDimensionsPreviewCancelled" in source
    assert "Primitive Construction History" in source
    assert "for index in range(5)" not in source
    assert "def _rebuild_primitive_property_controls" in source
    assert 'kind == "bool"' in source
    assert 'kind == "vector3"' in source
    assert 'kind == "choice"' in source
    assert "mapStudioPrimitiveDimension{index + 1}SpinBox" in source
    assert "mapStudioApplyPrimitiveDimensionsButton" in source
    assert "def _emit_primitive_dimensions" in source
    assert "self.builder_tab.roomPrimitiveDimensionsRequested.connect(self.apply_authored_room_primitive_dimensions)" in window_source
    assert "self.controller.set_authored_room_primitive_dimensions" in window_source


def test_t2674_builder_tab_exposes_remove_composition_primitive_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "roomPrimitiveRemoveRequested" in source
    assert "roomPrimitiveSeparateRequested" in source
    assert "mapStudioRemoveCompositionPrimitiveButton" in source
    assert "mapStudioSeparateCompositionPrimitiveButton" in source
    assert "mapStudioSeparatePrimitiveResultRoomLineEdit" in source
    assert "def _emit_remove_composition_primitive" in source
    assert "def _emit_separate_composition_primitive" in source
    assert "self.builder_tab.roomPrimitiveRemoveRequested.connect(self.remove_authored_room_primitive)" in window_source
    assert "self.builder_tab.roomPrimitiveSeparateRequested.connect(self.separate_authored_room_primitive)" in window_source
    assert "self.controller.remove_authored_room_primitive" in window_source
    assert "self.controller.separate_authored_room_primitive" in window_source


def test_t2676_builder_tab_exposes_primitive_style_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "roomPrimitiveStyleRequested" in source
    assert "mapStudioPrimitiveTextureLineEdit" in source
    assert "mapStudioPrimitiveSurfaceComboBox" in source
    assert "mapStudioApplyPrimitiveStyleButton" in source
    assert "def _emit_primitive_style" in source
    assert "self.builder_tab.roomPrimitiveStyleRequested.connect(self.apply_authored_room_primitive_style)" in window_source
    assert "self.controller.set_authored_room_primitive_style" in window_source


def _t2601_two_cube_batch_transform_project():
    _install_native_payload_paths()
    from src.core.modules.authored_room_operations import add_authored_room_composition_primitive
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="composition_starter_room",
        module_root="grbatch",
        game="K1",
    )
    project = add_authored_room_composition_primitive(
        project,
        primitive_kind="cube",
        room_resref="grbatch_room01",
        primitive_name="left_cube",
        translation=(-1.0, 0.0, 0.0),
        rotation_degrees_z=10.0,
        scale=(1.0, 2.0, 1.0),
    )
    return add_authored_room_composition_primitive(
        project,
        primitive_kind="cube",
        room_resref="grbatch_room01",
        primitive_name="right_cube",
        translation=(1.0, 0.0, 0.0),
        rotation_degrees_z=-20.0,
        scale=(0.5, 1.0, 2.0),
    )


def _t2601_batch_transform_rows(project):
    from src.core.modules.authored_room_operations import authored_room_composition_primitives

    return {row.primitive_name: row for row in authored_room_composition_primitives(project)}


def test_t2601_batch_translate_moves_complete_object_selection_by_one_world_delta() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_room_operations import transform_authored_room_composition_primitives

    updated = transform_authored_room_composition_primitives(
        _t2601_two_cube_batch_transform_project(),
        selections=(
            {"room_resref": "grbatch_room01", "primitive_name": "left_cube"},
            ("grbatch_room01", "right_cube"),
        ),
        mode="translate",
        world_delta=(2.0, -3.0, 4.0),
    )
    rows = _t2601_batch_transform_rows(updated)

    assert rows["left_cube"].translation == (1.0, -3.0, 4.0)
    assert rows["right_cube"].translation == (3.0, -3.0, 4.0)
    assert rows["left_cube"].rotation_degrees_z == 10.0
    assert rows["right_cube"].rotation_degrees_z == -20.0
    assert rows["grbatch_room01_floor"].translation == (0.0, 0.0, 0.0)
    assert updated.extra["batch_transform_mode"] == "translate"
    assert updated.extra["batch_transform_count"] == 2


def test_t2601_batch_rotate_orbits_pivots_and_retains_object_rotation_offsets() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_room_operations import transform_authored_room_composition_primitives

    updated = transform_authored_room_composition_primitives(
        _t2601_two_cube_batch_transform_project(),
        selections=(("grbatch_room01", "left_cube"), ("grbatch_room01", "right_cube")),
        mode="rotate",
        rotation_delta_degrees_z=90.0,
        world_pivot=(0.0, 0.0, 0.0),
    )
    rows = _t2601_batch_transform_rows(updated)

    assert tuple(round(value, 9) for value in rows["left_cube"].translation) == (0.0, -1.0, 0.0)
    assert tuple(round(value, 9) for value in rows["right_cube"].translation) == (0.0, 1.0, 0.0)
    assert rows["left_cube"].rotation_degrees_z == 100.0
    assert rows["right_cube"].rotation_degrees_z == 70.0
    assert rows["left_cube"].scale == (1.0, 2.0, 1.0)
    assert rows["right_cube"].scale == (0.5, 1.0, 2.0)


def test_t2601_batch_scale_orbits_pivots_and_multiplies_each_object_scale() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_room_operations import transform_authored_room_composition_primitives

    updated = transform_authored_room_composition_primitives(
        _t2601_two_cube_batch_transform_project(),
        selections=(("grbatch_room01", "left_cube"), ("grbatch_room01", "right_cube")),
        mode="scale",
        scale_multiplier=(2.0, 3.0, 4.0),
        world_pivot=(0.0, 0.0, 0.0),
    )
    rows = _t2601_batch_transform_rows(updated)

    assert rows["left_cube"].translation == (-2.0, 0.0, 0.0)
    assert rows["right_cube"].translation == (2.0, 0.0, 0.0)
    assert rows["left_cube"].scale == (2.0, 6.0, 4.0)
    assert rows["right_cube"].scale == (1.0, 3.0, 8.0)
    assert rows["left_cube"].rotation_degrees_z == 10.0
    assert rows["right_cube"].rotation_degrees_z == -20.0


def test_t2601_controller_batch_transform_records_one_undo_and_restores_selection() -> None:
    _install_native_payload_paths()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grbatch", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="composition_starter_room",
        module_root="grbatch",
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        room_resref="grbatch_room01",
        primitive_name="left_cube",
        translation=(-1.0, 0.0, 0.0),
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        room_resref="grbatch_room01",
        primitive_name="right_cube",
        translation=(1.0, 0.0, 0.0),
    )
    controller.command_history.clear()
    controller.model.selected_ids = ["primitive:left_cube", "primitive:right_cube"]

    controller.transform_authored_room_primitives(
        selections=(("grbatch_room01", "left_cube"), ("grbatch_room01", "right_cube")),
        mode="translate",
        world_delta=(0.5, 1.5, 2.5),
        world_pivot=(0.0, 0.0, 0.0),
    )

    assert len(controller.command_history.undo_stack) == 1
    record = controller.command_history.undo_stack[-1]
    assert record.action_key == "map_studio.primitive.batch_transform"
    assert record.label == "Move 2 primitives"
    assert record.metadata["selection_count"] == 2
    moved = {row.primitive_name: row for row in controller.authored_room_primitive_transforms()}
    assert moved["left_cube"].translation == (-0.5, 1.5, 2.5)
    assert moved["right_cube"].translation == (1.5, 1.5, 2.5)

    undo = controller.undo_map_studio_command()

    assert undo is not None
    assert undo.record.action_key == "map_studio.primitive.batch_transform"
    assert controller.model.selected_ids == ["primitive:left_cube", "primitive:right_cube"]
    restored = {row.primitive_name: row for row in controller.authored_room_primitive_transforms()}
    assert restored["left_cube"].translation == (-1.0, 0.0, 0.0)
    assert restored["right_cube"].translation == (1.0, 0.0, 0.0)


def test_t2907_pascal_concave_room_compiles_floor_ceiling_and_walkmesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRoomPrimitive,
        compile_floor_plan_room_geometry,
        validate_floor_plan_room_primitive,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    primitive = FloorPlanRoomPrimitive(
        room_resref="grpascal_l",
        points=((0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (2.0, 2.0), (2.0, 6.0), (0.0, 6.0)),
        z=1.0,
        wall_height=3.5,
        material=PrimitiveMaterial(texture="floor_tex"),
        wall_material=PrimitiveMaterial(texture="wall_tex"),
        ceiling_material=PrimitiveMaterial(texture="ceil_tex"),
        include_walls=True,
        include_ceiling=True,
    )

    validation = validate_floor_plan_room_primitive(primitive)
    geometry = compile_floor_plan_room_geometry(primitive)

    assert validation.ok is True
    assert len(geometry.room_mesh.faces) == 4
    assert len(geometry.wok.faces) == 4
    assert geometry.room_mesh.texture == "floor_tex"
    assert geometry.metadata["wall_count"] == 6
    assert geometry.metadata["has_ceiling"] is True
    assert geometry.helper_meshes[-1].texture == "ceil_tex"
    assert geometry.helper_meshes[-1].normals[0] == (0.0, 0.0, -1.0)


def test_t2907_pascal_room_rejects_crossing_wall_loop() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, validate_floor_plan_room_primitive

    primitive = FloorPlanRoomPrimitive(
        room_resref="grpascal_x",
        points=((0.0, 0.0), (4.0, 4.0), (0.0, 4.0), (4.0, 0.0)),
    )
    validation = validate_floor_plan_room_primitive(primitive)

    assert validation.ok is False
    assert any("cannot cross or overlap" in message for message in validation.blocking_issues)


def test_t2907_pascal_room_kmap_roundtrip_preserves_surface_materials_and_level() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject
    from src.core.modules.map_studio_pascal_building import add_pascal_building_room, pascal_building_levels

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grpascal", game="K1"),
        rooms=(),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grpascal")),
    )
    project, room_resref = add_pascal_building_room(
        project,
        points=((0.0, 0.0), (5.0, 0.0), (5.0, 3.0), (0.0, 3.0)),
        floor_z=3.0,
        wall_height=3.25,
        level_index=1,
        level_name="Upper Floor",
        floor_texture="floor_tex",
        wall_texture="wall_tex",
        ceiling_texture="ceil_tex",
    )
    restored = authored_project_from_kmap_payload(authored_project_to_kmap_payload(project))
    primitive = restored.rooms[0].primitive
    levels = pascal_building_levels(restored)

    assert room_resref == "grpascalr001"
    assert primitive.material.texture == "floor_tex"
    assert primitive.wall_material.texture == "wall_tex"
    assert primitive.ceiling_material.texture == "ceil_tex"
    assert primitive.include_ceiling is True
    assert levels[0].level_index == 1
    assert levels[0].name == "Upper Floor"
    assert levels[0].floor_z == 3.0
    assert levels[0].floor_to_floor_height == 3.25
    assert restored.placements.entry_point.position == (2.5, 1.5, 3.05)


def test_t2907_pascal_empty_levels_persist_and_collect_rooms_without_changing_elevation() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.map_studio_pascal_building import pascal_building_levels
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grlevels", game="K2")
    controller.add_map_studio_building_level(
        level_index=1,
        name="Upper Deck",
        floor_z=3.5,
        floor_to_floor_height=3.5,
    )
    empty_levels = controller.map_studio_building_levels()

    assert [(level.level_index, level.floor_z) for level in empty_levels] == [(0, 0.0), (1, 3.5)]
    assert empty_levels[1].name == "Upper Deck"
    assert empty_levels[1].floor_to_floor_height == 3.5
    assert empty_levels[1].room_resrefs == ()
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.building.level.create"

    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)),
        floor_z=3.5,
        wall_height=3.25,
        level_index=1,
        level_name="Upper Deck",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    restored = authored_project_from_kmap_payload(authored_project_to_kmap_payload(authored))
    restored_levels = pascal_building_levels(restored)

    assert restored.rooms[0].primitive.z == 3.5
    assert restored.extra["pascal_building_levels"][1]["floor_z"] == 3.5
    assert restored_levels[1].room_resrefs == (room_resref,)
    assert restored_levels[1].floor_to_floor_height == 3.5
    assert [record.action_key for record in controller.command_history.undo_stack] == [
        "map_studio.building.level.create",
        "map_studio.building.room.create",
    ]


def test_t2907_controller_builds_room_and_door_as_two_undoable_actions() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grhouse", game="K2")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (4.0, 0.0), (4.0, 5.0), (0.0, 5.0)),
        wall_height=3.0,
        level_name="Ground Floor",
    )
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=1.25,
        height=2.2,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    opening = authored.rooms[0].primitive.openings[0]

    assert room_resref == "grhouser001"
    assert opening.edge_index == 0
    assert opening.metadata["opening_kind"] == "door"
    assert [record.action_key for record in controller.command_history.undo_stack] == [
        "map_studio.building.room.create",
        "map_studio.building.door.create",
    ]
    assert controller.available_map_studio_building_styles()[0]["style_id"] == "plcaa_graybox"
    assert controller.map_studio_building_levels()[0].name == "Ground Floor"


def test_t2907_pascal_opening_preview_matches_commit_and_allows_multiple_windows() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import build_floor_plan_wall_meshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="gropenings", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.2,
    )
    left = controller.preview_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="window",
        center_fraction=0.25,
        width=1.2,
        height=1.0,
        bottom=1.0,
    )
    assert left["valid"] is True
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="window",
        center_fraction=left["center_fraction"],
        width=left["width"],
        height=left["height"],
        bottom=left["bottom"],
    )
    right = controller.preview_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="window",
        center_fraction=0.75,
        width=1.2,
        height=1.0,
        bottom=1.0,
    )
    assert right["valid"] is True
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="window",
        center_fraction=right["center_fraction"],
        width=right["width"],
        height=right["height"],
        bottom=right["bottom"],
    )
    overlap = controller.preview_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.25,
        width=1.25,
        height=2.2,
        bottom=0.0,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive

    assert overlap["valid"] is False
    assert "overlaps" in overlap["reason"]
    assert len(primitive.openings) == 2
    assert [opening.center_fraction for opening in primitive.openings] == [0.25, 0.75]
    assert all(mesh.faces for mesh in build_floor_plan_wall_meshes(primitive))
    assert any("_panel_" in mesh.name for mesh in build_floor_plan_wall_meshes(primitive))
    assert [record.action_key for record in controller.command_history.undo_stack] == [
        "map_studio.building.room.create",
        "map_studio.building.window.create",
        "map_studio.building.window.create",
    ]


def test_t2907_exterior_building_compiles_gable_roof_and_roundtrips() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grexterior", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.0,
        building_kind="exterior",
        roof_type="gable",
        roof_pitch_degrees=35.0,
        roof_overhang=0.35,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    restored = authored_project_from_kmap_payload(authored_project_to_kmap_payload(authored))
    primitive = restored.rooms[0].primitive
    geometry = compile_floor_plan_room_geometry(primitive)
    roofs = tuple(mesh for mesh in geometry.helper_meshes if "_roof_" in mesh.name)

    assert room_resref == "grexteriorr001"
    assert primitive.metadata["building_kind"] == "exterior"
    assert primitive.metadata["building_roof_type"] == "gable"
    assert primitive.metadata["building_roof_pitch_degrees"] == 35.0
    assert primitive.metadata["building_roof_overhang"] == 0.35
    assert geometry.metadata["has_roof"] is True
    assert geometry.metadata["roof_type"] == "gable"
    assert len(roofs) == 4
    assert sum(len(mesh.faces) for mesh in roofs) == 6
    assert all(any(abs(component) > 1.0e-6 for component in mesh.normals[0]) for mesh in roofs)
    assert all(mesh.texture for mesh in roofs)
    assert controller.command_history.undo_stack[-1].metadata["roof_type"] == "gable"

    controller.add_map_studio_building_room(
        points=((10.0, 0.0), (16.0, 0.0), (17.0, 3.0), (14.0, 6.0), (10.0, 4.0)),
        wall_height=3.0,
        building_kind="exterior",
        roof_type="hip",
        roof_pitch_degrees=25.0,
        roof_overhang=0.2,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    hip_geometry = compile_floor_plan_room_geometry(authored.rooms[1].primitive)
    hip_roofs = tuple(mesh for mesh in hip_geometry.helper_meshes if "_roof_hip_" in mesh.name)
    assert len(hip_roofs) == 5
    assert hip_geometry.metadata["roof_type"] == "hip"
    assert controller.command_history.undo_stack[-1].metadata["roof_type"] == "hip"


def test_t2907_pascal_graph_planarizes_t_junction_and_preserves_window() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grjunction", game="K2")
    first_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0)),
    )
    controller.set_map_studio_building_opening(
        room_resref=first_resref,
        edge_index=2,
        opening_kind="window",
        center_fraction=0.125,
        width=0.8,
        height=1.0,
        bottom=1.0,
    )
    controller.add_map_studio_building_room(
        points=((3.0, 4.0), (5.0, 4.0), (5.0, 7.0), (3.0, 7.0)),
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    restored = authored_project_from_kmap_payload(authored_project_to_kmap_payload(authored))
    first = restored.rooms[0].primitive
    opening = first.openings[0]
    graph = restored.extra["pascal_wall_graph"]
    edge_start = first.points[opening.edge_index]
    edge_end = first.points[(opening.edge_index + 1) % len(first.points)]
    opening_world_x = edge_start[0] + (edge_end[0] - edge_start[0]) * opening.center_fraction

    assert len(first.points) == 6
    assert opening.name == "window_edge_2_001"
    assert opening.edge_index == 2
    assert math.isclose(opening_world_x, 7.0, abs_tol=1.0e-7)
    assert opening.metadata["pascal_split_from_edge_index"] == 2
    assert graph["schema_version"] == 1
    assert graph["face_count"] == 2
    assert graph["inserted_vertex_count"] == 2
    assert len(graph["junction_vertex_ids"]) == 2
    assert any(len(wall["room_edges"]) == 2 for wall in graph["walls"])
    assert any(wall["openings"] for wall in graph["walls"])
    assert compile_floor_plan_room_geometry(first).metadata["opening_count"] == 1
    assert [record.action_key for record in controller.command_history.undo_stack] == [
        "map_studio.building.room.create",
        "map_studio.building.window.create",
        "map_studio.building.room.create",
    ]


def test_t2907_vanilla_building_style_catalog_learns_surface_roles_and_roundtrips(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _install_native_payload_paths()

    from src.core.modules import map_studio_terrain_kit
    from src.core.modules.map_studio_pascal_building import (
        scan_vanilla_pascal_building_styles,
        vanilla_pascal_building_styles,
        write_vanilla_pascal_style_catalog,
    )

    def surface(name: str, texture: str, normal_z: float, triangles: int):
        return SimpleNamespace(
            name=name,
            texture=texture,
            texture_names=(texture,),
            normals=((0.0, 0.0, normal_z),) * 3,
            faces=((0, 1, 2),) * triangles,
            render=True,
            children=(),
        )

    root = SimpleNamespace(
        name="room_root",
        texture="",
        texture_names=(),
        normals=(),
        faces=(),
        render=False,
        children=(
            surface("main_floor", "dan_floor", 1.0, 8),
            surface("main_wall", "dan_wall", 0.0, 12),
            surface("main_ceiling", "dan_ceil", -1.0, 6),
        ),
    )
    manager = SimpleNamespace(load_model_strict=lambda *_args, **_kwargs: SimpleNamespace(root_node=root))
    monkeypatch.setattr(
        map_studio_terrain_kit,
        "_base_game_lyt_rooms",
        lambda *_args, **_kwargs: {"danm13aa_01": "m13aa"},
    )

    styles = scan_vanilla_pascal_building_styles(manager, games=("K1",))
    target = write_vanilla_pascal_style_catalog(styles, tmp_path / "styles.json")
    vanilla_pascal_building_styles.cache_clear()
    restored = vanilla_pascal_building_styles(str(target))

    assert len(restored) == 1
    assert restored[0].game == "K1"
    assert restored[0].floor_texture == "dan_floor"
    assert restored[0].wall_texture == "dan_wall"
    assert restored[0].ceiling_texture == "dan_ceil"
    assert restored[0].source_module == "m13aa"


def test_t2907_environment_kit_catalog_indexes_both_games_with_real_provenance_and_magnets() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import vanilla_environment_kit_collections

    collections = vanilla_environment_kit_collections()
    pieces = tuple(piece for collection in collections for piece in collection.pieces)
    terrain = tuple(piece for piece in pieces if piece.role == "terrain")
    room_tiles = tuple(piece for piece in pieces if piece.role in {"room_tile", "exterior_tile"})

    assert len(collections) >= 200
    assert {collection.game for collection in collections} == {"K1", "K2"}
    assert len(pieces) >= 9_000
    assert len(terrain) >= 6_500
    assert len(room_tiles) >= 2_600
    assert all(piece.module_resref and piece.model_resref for piece in pieces)
    assert all(piece.terrain_asset_id and piece.surface_index >= 0 for piece in terrain)
    assert all(len(piece.magnets) == 4 for piece in terrain)
    assert any(piece.magnets for piece in room_tiles)


def test_t2907_environment_kit_styles_are_searchable_by_familiar_world_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        environment_kit_collection_rows,
        kotor_module_world_label,
    )
    from src.core.modules.map_studio_pascal_building import available_pascal_building_styles

    assert kotor_module_world_label("K1", "m13aa") == "Dantooine"
    assert kotor_module_world_label("K1", "m17aa") == "Tatooine"
    assert kotor_module_world_label("K2", "201tel") == "Telos"
    assert kotor_module_world_label("K2", "401dxn") == "Dxun"
    assert kotor_module_world_label("K2", "601dan") == "Dantooine"

    k1_rows = environment_kit_collection_rows(game="K1")
    k2_rows = environment_kit_collection_rows(game="K2")
    assert any(row["world_label"] == "Dantooine" and "Dantooine" in row["label"] for row in k1_rows)
    assert any(row["world_label"] == "Dxun" and "Dxun" in row["label"] for row in k2_rows)

    k2_styles = available_pascal_building_styles("K2")
    assert any(style.style_id == "kit:k2_201tel" and "Telos" in style.label for style in k2_styles)
    assert any(style.style_id == "kit:k2_401dxn" and "Dxun" in style.label for style in k2_styles)


def test_t2907_pascal_builds_multiple_planet_interior_and_exterior_styles(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grstyles", game="K2")
    cases = (
        ("kit:k2_201tel", "interior", "none", "tel_hcl1", "tel_hjk", "tel_hcl1"),
        ("kit:k2_301nar", "interior", "none", "nar_wl07", "nar_wl01", "nar_lt01"),
        ("kit:k2_401dxn", "exterior", "hip", "dxn_grs5", "dxn_flora1", "dxn_flora1"),
        ("kit:k2_601dan", "exterior", "gable", "dan_grass07", "dan_bark04", "dan_unwal07"),
    )
    for index, (style_id, kind, roof, _floor, _wall, _ceiling) in enumerate(cases):
        x = float(index * 8)
        controller.add_map_studio_building_room(
            points=((x, 0.0), (x + 6.0, 0.0), (x + 6.0, 4.0), (x, 4.0)),
            style_id=style_id,
            building_kind=kind,
            roof_type=roof,
        )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == 4
    for room, (style_id, kind, roof, floor, wall, ceiling) in zip(authored.rooms, cases):
        primitive = room.primitive
        assert primitive.metadata["style_id"] == style_id
        assert primitive.metadata["building_kind"] == kind
        assert primitive.metadata["building_roof_type"] == roof
        assert primitive.material.texture == floor
        assert primitive.wall_material.texture == wall
        assert primitive.ceiling_material.texture == ceiling

    export = controller.export_authored_module(tmp_path / "multistyle_export")
    assert export.ok is True
    assert Path(export.module_path).is_file()
    assert export.package_verification is not None
    assert export.package_verification.ok is True
    assert export.package_verification.parsed_gff == (
        "grstyles.are",
        "grstyles.git",
        "module.ifo",
        "grstyles.pth",
    )
    assert export.package_verification.parsed_wok == tuple(
        f"grstylesr{index:03d}.wok" for index in range(1, 5)
    )
    assert export.package_verification.model_pairs == tuple(
        f"grstylesr{index:03d}.mdl/.mdx" for index in range(1, 5)
    )
    assert len(export.resources) == 18
    assert not export.blocking_issues


def test_t2909_endar_and_taris_architecture_kits_change_room_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grarchkit", game="K1")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}

    assert styles["architecture:k1_endar_spire"]["architecture_profile"] == "endar_spire"
    assert styles["architecture:k1_endar_spire"]["architecture_shell_profile"] == "endar_corridor"
    assert styles["architecture:k1_endar_spire"]["recommended_wall_height_m"] == 3.655
    assert styles["architecture:k1_taris_apartments"]["architecture_profile"] == "taris_apartments"
    assert styles["architecture:k1_taris_apartments"]["architecture_shell_profile"] == "taris_apartment"
    assert styles["architecture:k1_taris_apartments"]["recommended_wall_height_m"] == 2.55
    assert styles["architecture:k1_taris_apartments"]["recommended_floor_to_floor_m"] == 3.075
    assert styles["architecture:k1_taris_apartments"]["recommended_door_width_m"] == 3.0
    assert styles["architecture:k1_taris_apartments"]["recommended_door_height_m"] == 2.396
    assert styles["architecture:k1_endar_spire"]["evidence_rooms"] == (
        "m01aa_01a",
        "m01aa_06a",
        "m01aa_08a",
        "m01ab_09a",
        "k2:151har02",
        "k2:152har36",
    )

    endar_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    taris_resref = controller.add_map_studio_building_room(
        points=((10.0, 0.0), (18.0, 0.0), (18.0, 5.0), (10.0, 5.0)),
        wall_height=3.0,
        style_id="architecture:k1_taris_apartments",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    endar = next(room for room in authored.rooms if room.room_resref == endar_resref)
    taris = next(room for room in authored.rooms if room.room_resref == taris_resref)
    endar_geometry = compile_floor_plan_room_geometry(endar.primitive)
    taris_geometry = compile_floor_plan_room_geometry(taris.primitive)
    endar_roles = {mesh.metadata.get("architecture_role") for mesh in endar_geometry.helper_meshes}
    taris_roles = {mesh.metadata.get("architecture_role") for mesh in taris_geometry.helper_meshes}
    endar_textures = {mesh.texture for mesh in endar_geometry.helper_meshes}
    taris_textures = {mesh.texture for mesh in taris_geometry.helper_meshes}

    assert endar_geometry.metadata["architecture_profile"] == "endar_spire"
    assert endar_geometry.metadata["architecture_mesh_count"] >= 80
    assert {"faceted_ceiling_cove", "arched_rib", "red_inset_panel", "integrated_light"} <= endar_roles
    assert {"lhr_red02", "lhr_trim01", "lhr_lit01", "lhr_wall06"} <= endar_textures
    assert taris_geometry.metadata["architecture_profile"] == "taris_apartments"
    assert taris_geometry.metadata["architecture_mesh_count"] >= 70
    assert {"apartment_recess", "utility_rail", "structural_rib", "integrated_light"} <= taris_roles
    assert {"lts_pwall04", "lts_trim01", "lts_lite08", "lts_gwall01"} <= taris_textures
    assert "faceted_ceiling_cove" not in taris_roles


def test_t2909_shadowlands_builds_open_air_organic_root_walls_and_exports(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_metadata import authored_area_metadata, build_authored_are_gff
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.map_studio_environment_kits import environment_kit_piece, environment_kit_piece_rows
    from src.core.modules.map_studio_terrain_kit import terrain_kit_asset_rows
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grshadow", game="K1")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    style = styles["architecture:k1_shadowlands"]
    assert style["architecture_profile"] == "shadowlands"
    assert style["architecture_shell_profile"] == "shadowlands_root_wall"
    assert style["environment_kind"] == "exterior"
    assert style["recommended_wall_height_m"] == 6.0
    assert style["recommended_floor_to_floor_m"] == 8.0
    assert {"m24aa_02a", "m24aa_16a", "m25aa_01a", "m25aa_12a"} <= set(style["evidence_rooms"])

    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (14.0, 0.0), (15.0, 7.0), (9.0, 12.0), (1.0, 10.0)),
        wall_height=style["recommended_wall_height_m"],
        style_id=style["style_id"],
        include_ceiling=True,
        building_kind="interior",
        roof_type="hip",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["building_kind"] == "exterior"
    assert primitive.metadata["building_roof_type"] == "none"
    assert primitive.include_ceiling is False
    assert controller.map_studio_building_style_context() == {
        "style_id": "architecture:k1_shadowlands",
        "environment_kind": "exterior",
        "room_resref": room_resref,
    }

    geometry = compile_floor_plan_room_geometry(primitive)
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
    textures = {mesh.texture for mesh in geometry.helper_meshes}
    assert geometry.metadata["architecture_shell_profile"] == "shadowlands_root_wall"
    assert geometry.metadata["architecture_mesh_count"] >= 60
    assert geometry.metadata["wall_count"] == 0
    assert geometry.metadata["has_ceiling"] is False
    assert geometry.metadata["has_roof"] is False
    assert {
        "earthen_toe",
        "dirt_mound_slope",
        "weathered_dirt_ridge",
        "mossy_berm_crown",
        "exposed_root_run",
    } <= roles
    assert {"lka_bark06", "lka_mud02"} <= textures
    assert "lka_plant02" not in textures
    dirt_roles = {"earthen_toe", "dirt_mound_slope", "weathered_dirt_ridge", "mossy_berm_crown"}
    dirt_meshes = [mesh for mesh in geometry.helper_meshes if mesh.metadata.get("architecture_role") in dirt_roles]
    assert dirt_meshes
    # Terrain UVs are world-projected on each facet's dominant axis. Horizontal
    # ground keeps XY, while steep banks use YZ/XZ so the mud climbs by height
    # instead of stretching one narrow plan-view strip over the whole wall.
    for mesh in dirt_meshes:
        for vertex, normal, uv in zip(mesh.vertices, mesh.normals, mesh.uvs):
            abs_normal = tuple(abs(float(value)) for value in normal)
            if abs_normal[2] >= abs_normal[0] and abs_normal[2] >= abs_normal[1]:
                expected = (float(vertex[0]) * 0.30, float(vertex[1]) * 0.30)
            elif abs_normal[0] >= abs_normal[1]:
                expected = (float(vertex[1]) * 0.30, float(vertex[2]) * 0.30)
            else:
                expected = (float(vertex[0]) * 0.30, float(vertex[2]) * 0.30)
            assert math.isclose(float(uv[0]), expected[0], abs_tol=1.0e-6)
            assert math.isclose(float(uv[1]), expected[1], abs_tol=1.0e-6)
    # The toe has to begin on the exact floor outline.  A positive initial
    # berm offset leaves a genuine open slit at the wall/floor edge which is
    # especially obvious when the exterior lighting is dark.
    floor_outline = {(round(float(x), 6), round(float(y), 6)) for x, y in primitive.points}
    toe_outline = {
        (round(float(vertex[0]), 6), round(float(vertex[1]), 6))
        for mesh in dirt_meshes
        if mesh.metadata.get("architecture_role") == "earthen_toe"
        for vertex in mesh.vertices
        if math.isclose(float(vertex[2]), float(primitive.z), abs_tol=1.0e-7)
    }
    assert floor_outline <= toe_outline
    area = authored_area_metadata(authored.metadata)
    assert area.sun_fog_on is True
    assert area.fog_color == (46, 36, 33)
    assert area.fog_near == 0.0 and area.fog_far == 70.0
    assert area.grass_texture == "lka_grass"
    assert area.grass_density == 5.0
    assert area.grass_quad_size == 0.8
    shadowlands_are = build_authored_are_gff(authored.metadata, area, room_resrefs=(room_resref,))
    assert str(shadowlands_are.root.get("Grass_TexName")) == "lka_grass"
    assert shadowlands_are.root.get_single("Grass_Density") == 5.0
    assert shadowlands_are.root.get_single("Grass_QuadSize") == 0.8
    assert shadowlands_are.root.get_uint8("SunFogOn") == 1
    assert shadowlands_are.root.get_single("SunFogFar") == 70.0
    preview_model = build_authored_module_preview_model(authored).model
    assert preview_model is not None
    preview_state = preview_model._gr_map_studio_world_lighting_preview
    assert preview_state["fog_previewed"] is True
    assert preview_state["fog_color_rgb"] == [round(channel / 255.0, 7) for channel in (46, 36, 33)]
    assert preview_state["fog_preview_color_rgb"] == [0.2, 0.24, 0.27]
    assert preview_state["fog_far"] == 70.0
    assert preview_state["fog_preview_far"] == pytest.approx(21.0)
    assert preview_state["fog_preview_calibration"] == "shadowlands_mist_lens"
    assert preview_state["grass_previewed"] is True
    grass_nodes = [
        node
        for node in preview_model.all_nodes()
        if bool(getattr(node, "_gr_map_studio_editor_preview_only", False))
    ]
    assert len(grass_nodes) == 1
    assert str(getattr(grass_nodes[0], "_gr_map_studio_mesh_role", "")) == "shadowlands_grass_preview"
    assert tuple(getattr(grass_nodes[0], "selfillum", ())) == (0.055, 0.075, 0.035)
    south_vertices = [
        vertex
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("edge_index") == 0
        for vertex in mesh.vertices
    ]
    assert min(float(vertex[1]) for vertex in south_vertices) <= -1.8
    assert len({round(float(vertex[1]), 3) for vertex in south_vertices}) >= 8
    assert geometry.wok.verts and geometry.wok.faces

    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=4.0,
        height=3.25,
        bottom=0.0,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    opened = compile_floor_plan_room_geometry(authored.rooms[0].primitive)
    assert any(mesh.metadata.get("architecture_role") == "shadowlands_cave_portal_lip" for mesh in opened.helper_meshes)
    assert any(mesh.metadata.get("surface_role") == "terrain_corner_weld" for mesh in opened.helper_meshes)
    cave_meshes = [
        mesh
        for mesh in opened.helper_meshes
        if mesh.metadata.get("edge_index") == 0 and mesh.metadata.get("cave_portal_profile")
    ]
    assert cave_meshes
    # The cavity narrows as it rises toward an earthen arch; it is not a
    # rectangular boolean cut wearing a separate doorway ornament.
    lower_spans = [
        (min(float(vertex[0]) for vertex in mesh.vertices), max(float(vertex[0]) for vertex in mesh.vertices))
        for mesh in cave_meshes
        if max(float(vertex[2]) for vertex in mesh.vertices) <= 2.2
    ]
    upper_spans = [
        (min(float(vertex[0]) for vertex in mesh.vertices), max(float(vertex[0]) for vertex in mesh.vertices))
        for mesh in cave_meshes
        if min(float(vertex[2]) for vertex in mesh.vertices) >= 2.2
    ]
    assert lower_spans and upper_spans
    blocking_roles = {
        "earthen_toe",
        "dirt_mound_slope",
        "weathered_dirt_ridge",
        "exposed_root_run",
    }
    for mesh in opened.helper_meshes:
        if mesh.metadata.get("edge_index") != 0 or mesh.metadata.get("architecture_role") not in blocking_roles:
            continue
        xs = [float(vertex[0]) for vertex in mesh.vertices]
        zs = [float(vertex[2]) for vertex in mesh.vertices]
        # The rounded shoulder intentionally occupies the rectangular
        # corners near the arch apex, but the player corridor at the centre
        # stays unobstructed all the way from the ground to the cave crown.
        assert not (min(xs) < 7.0 - 1.0e-6 and max(xs) > 7.0 + 1.0e-6 and min(zs) < 3.25 and max(zs) > 0.0), mesh.name

    room_rows = [
        row
        for row in environment_kit_piece_rows(game="K1")
        if row["building_style_id"] == "architecture:k1_shadowlands"
    ]
    terrain_rows = [
        row
        for row in terrain_kit_asset_rows(game="K1")
        if row.get("building_style_id") == "architecture:k1_shadowlands"
    ]
    assert {row["module_resref"] for row in room_rows} == {"m24aa", "m25aa"}
    assert {row["module_resref"] for row in terrain_rows} == {"m24aa", "m25aa"}
    assert {"Roots & Tree Trunks", "Canopy & Foliage", "Terrain Forms"} <= {
        row["category"] for row in terrain_rows
    }
    staged_roots = [row for row in terrain_rows if row["category"] == "Roots & Tree Trunks"]
    assert staged_roots
    assert "vanilla_k1_m25aa_01a_007" not in {row["asset_id"] for row in staged_roots}
    assert all(int(row["triangle_count"]) >= 24 for row in staged_roots)
    assert all(0.10 <= float(row["suggested_scale"]) <= 1.0 for row in staged_roots)
    assert all("staging" in str(row["staging_role"]).lower() for row in staged_roots)

    export = controller.export_authored_module(tmp_path / "shadowlands_export")
    assert export.ok is True
    assert export.package_verification is not None and export.package_verification.ok is True
    assert export.package_verification.model_pairs == (f"{room_resref}.mdl/.mdx",)
    assert export.package_verification.parsed_wok == (f"{room_resref}.wok",)


def test_t2911_shadowlands_stock_rooms_snap_to_generated_organic_wok(tmp_path: Path) -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Shadowlands stock-room seam proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    for label, piece_id in (
        ("upper", "k1_m24aa_m24aa_02a"),
        ("lower", "k1_m25aa_m25aa_01a"),
    ):
        controller = ModuleEditorController()
        controller.new_project(name=f"grshadow{label}", game="K1")
        authored_room = controller.add_map_studio_building_room(
            points=((0.0, 0.0), (24.0, 0.0), (24.0, 20.0), (0.0, 20.0)),
            wall_height=6.0,
            style_id="architecture:k1_shadowlands",
        )
        preview = controller.preview_authored_terrain_kit_placement(
            asset_id=piece_id,
            position=(12.0, 20.0, 0.0),
        )
        assert preview["magnet_snapped"] is True
        assert preview["target_is_authored_wall"] is True
        assert preview["target_room_resref"] == authored_room
        assert preview["target_edge_index"] == 2
        assert preview["opening_width"] == pytest.approx(4.0)
        assert preview["opening_height"] == pytest.approx(3.25)

        stock_room = controller.add_authored_environment_kit_piece(
            piece_id=piece_id,
            position=(12.0, 20.0, 0.0),
            resource_manager=resources,
        )
        authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
        build = compile_authored_room_connection_walkmeshes(authored)
        assert build.ready is True, build.blocking_issues
        assert len(build.portals) == 1
        portal = build.portals[0]
        assert portal.midpoint_gap <= 2.0e-5

        stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)
        generated = next(room for room in authored.rooms if room.normalised_resref() == authored_room)
        stock_portal = stock.primitive.metadata["walkmesh_portals"][0]
        trim = stock.primitive.metadata["environment_kit_connection_trim"]
        assert trim["operation"] == "portal_half_space_trim"
        assert int(trim["render_faces_after"]) < int(trim["render_faces_before"])
        assert int(trim["wok_faces_after"]) > 0
        assert trim["wok_shared_vertex_policy"] == "preserved-imported-raw-indices"
        assert trim["wok_visual_clip_excluded"] is True
        assert int(trim["wok_vertices_after"]) < int(trim["wok_faces_after"]) * 3
        # Render trimming must never rewrite the stock WOK's raw-index
        # topology: the exact retail threshold edge is required to stitch the
        # generated reciprocal room transition.
        assert any(
            int(getattr(face, edge_name)) >= 0
            for face in stock.primitive.wok.faces
            for edge_name in ("adj1", "adj2", "adj3")
        )
        exterior_closure = stock.primitive.metadata["environment_kit_exterior_closure"]
        assert exterior_closure["operation"] == "organic_boundary_mound"
        assert exterior_closure["visual_only"] is True
        assert exterior_closure["shared_indexed_vertices"] is True
        assert int(exterior_closure["profile_ring_count"]) == 5
        assert exterior_closure["uv_projection"] == "local_vertical_meter_projection"
        assert int(exterior_closure["sealed_boundary_edges"]) > 0
        assert int(exterior_closure["skipped_portal_edges"]) > 0
        closure_surfaces = [
            surface
            for surface in stock.primitive.surfaces
            if surface.name.endswith("_shadowlands_exterior_closure")
        ]
        assert len(closure_surfaces) == 1
        assert closure_surfaces[0].texture == "lka_mud02"
        assert closure_surfaces[0].faces
        # Reload compacts coincident/degenerate triangles at tight organic
        # corners, so the persisted closure may contain fewer than the 20
        # pre-compaction candidate faces generated per exposed edge.
        assert (
            int(exterior_closure["sealed_boundary_edges"]) * 12
            <= len(closure_surfaces[0].faces)
            <= int(exterior_closure["sealed_boundary_edges"]) * 20
        )
        assert int(exterior_closure["top_cap_faces"]) == int(exterior_closure["sealed_boundary_edges"]) * 4
        assert len(closure_surfaces[0].vertices) <= len(closure_surfaces[0].faces) * 3
        for face in closure_surfaces[0].faces:
            face_uvs = [closure_surfaces[0].uvs[int(index)] for index in face]
            assert max(float(uv[0]) for uv in face_uvs) - min(float(uv[0]) for uv in face_uvs) <= 3.25
            assert max(float(uv[1]) for uv in face_uvs) - min(float(uv[1]) for uv in face_uvs) <= 2.25
        closure_z_values = [float(vertex[2]) for vertex in closure_surfaces[0].vertices]
        assert max(closure_z_values) - min(closure_z_values) >= float(exterior_closure["bank_height_m"]) - 0.05
        assert stock.primitive.metadata["source_walkmesh_boundary_count"] > 0
        assert generated.primitive.openings[0].width == pytest.approx(float(stock_portal["width_m"]))
        generated_geometry = compile_authored_room_spec(generated)
        cave_connectors = [
            mesh
            for mesh in generated_geometry.helper_meshes
            if mesh.metadata.get("architecture_role") == "shadowlands_cave_connector"
        ]
        assert cave_connectors
        assert {mesh.metadata.get("connected_room_resref") for mesh in cave_connectors} == {stock_room}
        assert all(float(mesh.metadata.get("connector_depth_m", 0.0)) >= 1.65 for mesh in cave_connectors)
        assert all(float(mesh.metadata.get("connector_overlap_m", 0.0)) >= 0.55 for mesh in cave_connectors)
        assert {mesh.metadata.get("connector_direction") for mesh in cave_connectors} == {"authored_clearing_interior"}
        assert min(float(vertex[2]) for mesh in cave_connectors for vertex in mesh.vertices) == pytest.approx(0.0)
        room_order = {room.normalised_resref(): index for index, room in enumerate(authored.rooms)}
        source_face = build.room_woks[portal.source_room_resref].faces[portal.source_face_index]
        target_face = build.room_woks[portal.target_room_resref].faces[portal.target_face_index]
        assert getattr(source_face, ("trans1", "trans2", "trans3")[portal.source_local_edge]) == room_order[
            portal.target_room_resref
        ]
        assert getattr(target_face, ("trans1", "trans2", "trans3")[portal.target_local_edge]) == room_order[
            portal.source_room_resref
        ]

        if label == "upper":
            # m24aa's doorway is the important fallback case: the retail LYT
            # has a hook, while its WOK threshold carries no old transition.
            assert int(stock_portal["source_transition_target"]) == -1
            export = controller.export_authored_module(tmp_path / "shadowlands_upper_connection")
            assert export.ok is True
            assert export.package_verification is not None and export.package_verification.ok is True
            assert set(export.package_verification.parsed_wok) == {
                f"{authored_room}.wok",
                f"{stock_room}.wok",
            }
            combined = combine_authored_module_walkmesh(authored)
            session = MapStudioPIESession(combined.wok, game="K1", spawn_position=(12.0, 18.0, 0.0))
            assert session.validation.ok is True
            for _index in range(300):
                session.set_move_input(1.0, 0.0, camera_azimuth_degrees=-90.0, run=True)
                session.advance(1.0 / 30.0)
            assert session.state.position[1] > 20.5


def test_t2909_environment_closure_preserves_existing_vanilla_walls() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.map_studio_environment_kits import (
        generated_environment_kit_boundary_magnets,
        seal_environment_kit_exterior_bounds,
    )
    from src.core.modules.module_format import WOKData, WOKFace

    # A square walkable floor with a real stock wall on only its east edge.
    # The repair pass must leave that wall alone and close only the other
    # three exposed perimeter edges.
    wall = ImportedMeshSurface(
        name="vanilla_east_wall",
        texture="lka_bark01",
        vertices=((4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (4.0, 4.0, 3.0), (4.0, 0.0, 3.0)),
        faces=((0, 1, 2), (0, 2, 3)),
    )
    wok = WOKData(
        name="stock",
        verts=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0)],
        faces=[
            WOKFace(0, 1, 2, 1, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, 1, adj1=0, adj2=-1, adj3=-1),
        ],
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="stock",
        surfaces=(wall,),
        wok=wok,
    )

    sealed = seal_environment_kit_exterior_bounds(primitive)
    closure = sealed.metadata["environment_kit_exterior_closure"]

    assert closure["wall_generation_policy"] == "exposed_wok_boundary_only"
    assert closure["preserved_stock_wall_edges"] == 1
    assert closure["sealed_boundary_edges"] == 3
    assert sealed.surfaces[0] is wall
    assert sum(surface.name == "vanilla_east_wall" for surface in sealed.surfaces) == 1
    generated = generated_environment_kit_boundary_magnets(primitive, opening_width=4.0)
    assert generated
    assert all(abs(float(magnet.local_position[0]) - 4.0) > 0.25 for magnet in generated)

    portal_sealed = seal_environment_kit_exterior_bounds(
        primitive,
        portal_midpoint=(2.0, 0.0, 0.0),
        portal_start=(0.0, 0.0, 0.0),
        portal_end=(4.0, 0.0, 0.0),
        portal_width=4.0,
    )
    portal_closure = portal_sealed.metadata["environment_kit_exterior_closure"]
    assert portal_closure["portal_exclusion_policy"] == "exact_collinear_wok_edge_overlap"
    assert portal_closure["skipped_portal_edges"] == 1
    assert portal_closure["preserved_stock_wall_edges"] == 1
    assert portal_closure["sealed_boundary_edges"] == 2


def test_t2909_reviewed_socketless_village_room_generates_connected_wok() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for generated-connector proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grgenerated", game="K1")
    authored_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (24.0, 0.0), (24.0, 20.0), (0.0, 20.0)),
        wall_height=6.0,
        style_id="architecture:k1_shadowlands",
    )
    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m23aa_m23aa_04a",
        position=(12.0, 20.0, 0.0),
        target_room_resref=authored_room,
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)
    assert max(abs(float(stock.position[0])), abs(float(stock.position[1]))) < 60.0
    assert stock.primitive.wok is not None and len(stock.primitive.wok.faces) > 0
    assert stock.primitive.metadata["wok_auto_generated"]["structural_validation"] == "passed"
    assert stock.primitive.metadata["environment_kit_generated_rebase"]["policy"].startswith(
        "walkmesh_center_xy"
    )
    assert stock.primitive.metadata["walkmesh_portals"]
    assert stock.primitive.metadata["environment_kit_exterior_closure"]["wall_generation_policy"] == (
        "exposed_wok_boundary_only"
    )
    assert stock.primitive.metadata["environment_kit_exterior_closure"]["portal_exclusion_policy"] == (
        "exact_collinear_wok_edge_overlap"
    )
    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True, build.blocking_issues
    assert len(build.portals) == 1
    assert build.portals[0].midpoint_gap <= 2.0e-5


def test_t2911_dathomir_fallen_order_assets_are_optional_terrain_kit_entries() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.map_studio_terrain_kit import (
        build_terrain_kit_primitive,
        terrain_kit_asset_path,
        terrain_kit_asset_rows,
    )

    root = Path(
        r"C:\Users\NewAdmin\Documents\KotorMods\ModdersResourceFiles\FallenOrder\Dathomir\Converted\Models\Models"
    )
    if not root.is_dir():
        pytest.skip("The local Fallen Order Dathomir extraction is not available on this machine.")

    rows = {row["asset_id"]: row for row in terrain_kit_asset_rows(game="K1")}
    assert {"dathomir_scarlet_plant", "dathomir_terrarium_flower", "dathomir_planet_skybox"} <= set(rows)
    assert rows["dathomir_scarlet_plant"]["category"] == "Foliage"
    assert rows["dathomir_terrarium_flower"]["category"] == "Foliage"
    assert rows["dathomir_planet_skybox"]["category"] == "Vistas & Horizons"
    assert rows["dathomir_planet_skybox"]["building_style_id"] == "environment:dathomir"
    assert Path(rows["dathomir_scarlet_plant"]["asset_path"]).is_file()
    assert terrain_kit_asset_path("dathomir_scarlet_plant").is_file()

    primitive = build_terrain_kit_primitive("dathomir_scarlet_plant", "grdath01", game="K1")
    assert primitive.metadata["terrain_kit_asset_id"] == "dathomir_scarlet_plant"
    assert primitive.metadata["terrain_kit_visual_only"] is True
    assert primitive.surfaces
    assert primitive.wok is not None and not primitive.wok.faces


def test_t2909_taris_apartment_sweeps_measured_structural_cross_section(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grtariscontour", game="K1")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    style = styles["architecture:k1_taris_apartments"]
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=style["recommended_wall_height_m"],
        style_id=style["style_id"],
        include_ceiling=True,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["architecture_shell_profile"] == "taris_apartment"

    geometry = compile_floor_plan_room_geometry(primitive)
    assert geometry.metadata["architecture_shell_profile"] == "taris_apartment"
    assert geometry.metadata["wall_count"] == 0
    assert geometry.metadata["has_ceiling"] is True
    assert geometry.wok.verts
    assert geometry.wok.faces
    shell = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("primitive") == "floor_plan_profiled_shell"
    )
    assert shell
    assert not any(mesh.metadata.get("primitive") == "floor_plan_ceiling" for mesh in geometry.helper_meshes)
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in shell}
    assert {
        "taris_floor_edge",
        "taris_lower_service_plinth",
        "taris_wall_panel_zone",
        "integrated_light",
        "taris_utility_light_return",
        "taris_upper_wall_panel",
        "taris_upper_shoulder",
        "taris_ceiling_cove",
        "recessed_ceiling_transition",
        "structural_rib",
        "recessed_ceiling",
    } <= roles

    measured_stations = (0.187, 0.450, 1.350, 1.500, 1.650, 1.950, 2.100, 2.396, 2.550)
    all_z = {round(float(vertex[2]), 3) for mesh in shell for vertex in mesh.vertices}
    assert set(measured_stations) <= all_z
    ceiling = next(mesh for mesh in shell if mesh.metadata.get("architecture_role") == "recessed_ceiling")
    ceiling_x = [float(vertex[0]) for vertex in ceiling.vertices]
    ceiling_y = [float(vertex[1]) for vertex in ceiling.vertices]
    assert min(ceiling_x) >= 0.31 and max(ceiling_x) <= 7.69
    assert min(ceiling_y) >= 0.31 and max(ceiling_y) <= 4.69

    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=style["recommended_door_width_m"],
        height=style["recommended_door_height_m"],
        bottom=0.0,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    opened_geometry = compile_floor_plan_room_geometry(authored.rooms[0].primitive)
    for mesh in opened_geometry.helper_meshes:
        if (
            mesh.metadata.get("primitive") != "floor_plan_profiled_shell"
            or mesh.metadata.get("edge_index") != 0
        ):
            continue
        xs = [float(vertex[0]) for vertex in mesh.vertices]
        zs = [float(vertex[2]) for vertex in mesh.vertices]
        overlaps_opening_x = min(xs) < 5.5 - 1.0e-6 and max(xs) > 2.5 + 1.0e-6
        overlaps_opening_z = min(zs) < 2.396 - 1.0e-6 and max(zs) > 0.0 + 1.0e-6
        assert not (overlaps_opening_x and overlaps_opening_z), mesh.name

    export = controller.export_authored_module(tmp_path / "taris_contour_export")
    assert export.ok is True
    assert export.package_verification is not None
    assert export.package_verification.ok is True
    assert export.package_verification.model_pairs == (f"{room_resref}.mdl/.mdx",)
    assert export.package_verification.parsed_wok == (f"{room_resref}.wok",)


def test_t2909_endar_corridor_sweeps_structural_cross_section(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grcontour", game="K1")
    controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
        include_ceiling=True,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    primitive = authored.rooms[0].primitive
    assert primitive.metadata["architecture_shell_profile"] == "endar_corridor"

    geometry = compile_floor_plan_room_geometry(primitive)
    assert geometry.metadata["architecture_shell_profile"] == "endar_corridor"
    assert geometry.metadata["wall_count"] == 0  # The rectangular shell is replaced, not decorated over.
    assert geometry.metadata["has_ceiling"] is True
    shell = tuple(
        mesh for mesh in geometry.helper_meshes
        if mesh.metadata.get("primitive") == "floor_plan_profiled_shell"
    )
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in shell}
    assert {
        "raised_floor_edge",
        "red_inset_panel",
        "integrated_light",
        "canted_upper_bulkhead",
        "arched_shoulder",
        "ceiling_light_coffer",
        "faceted_ceiling_cove",
        "arched_rib",
        "recessed_ceiling",
    } <= roles

    south_cant = next(
        mesh for mesh in shell
        if mesh.metadata.get("edge_index") == 0
        and mesh.metadata.get("architecture_role") == "canted_upper_bulkhead"
    )
    ys = [float(vertex[1]) for vertex in south_cant.vertices]
    zs = [float(vertex[2]) for vertex in south_cant.vertices]
    assert max(ys) - min(ys) >= 0.20
    assert max(zs) - min(zs) >= 0.65
    assert abs(float(south_cant.normals[0][1])) > 0.5
    assert abs(float(south_cant.normals[0][2])) > 0.1

    ceiling = next(mesh for mesh in shell if mesh.metadata.get("architecture_role") == "recessed_ceiling")
    ceiling_x = [float(vertex[0]) for vertex in ceiling.vertices]
    ceiling_y = [float(vertex[1]) for vertex in ceiling.vertices]
    assert min(ceiling_x) > 1.0 and max(ceiling_x) < 7.0
    assert min(ceiling_y) > 1.0 and max(ceiling_y) < 4.0

    for mesh in shell:
        for a, b, c in mesh.faces:
            pa, pb, pc = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
            ab = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            ac = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            cross = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            assert math.sqrt(sum(component * component for component in cross)) > 1.0e-8, mesh.name

    export = controller.export_authored_module(tmp_path / "endar_contour_export")
    assert export.ok is True
    assert export.package_verification is not None
    assert export.package_verification.ok is True
    assert export.package_verification.model_pairs == ("grcontourr001.mdl/.mdx",)
    assert export.package_verification.parsed_wok == ("grcontourr001.wok",)


def test_t2909_architecture_dressing_respects_door_opening() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grarchdoor", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=1.4,
        height=2.2,
        bottom=0.0,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    geometry = compile_floor_plan_room_geometry(authored.rooms[0].primitive)
    blocking_roles = {
        "skirting",
        "wall_bay",
        "raised_floor_edge",
        "red_inset_panel",
        "lower_bulkhead_return",
        "integrated_light",
        "mid_bulkhead",
        "canted_upper_bulkhead",
        "arched_rib",
        "structural_rib",
    }
    for mesh in geometry.helper_meshes:
        if mesh.metadata.get("edge_index") != 0 or mesh.metadata.get("architecture_role") not in blocking_roles:
            continue
        xs = [float(vertex[0]) for vertex in mesh.vertices]
        zs = [float(vertex[2]) for vertex in mesh.vertices]
        overlaps_door_x = min(xs) < 4.7 - 1.0e-6 and max(xs) > 3.3 + 1.0e-6
        overlaps_door_z = min(zs) < 2.2 and max(zs) > 0.0
        assert not (overlaps_door_x and overlaps_door_z), mesh.name


def test_t2909_endar_door_is_authentic_working_resource_and_next_room_is_preserved(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from pykotor.resource.generics.utd import read_utd
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grendardoor", game="K1")
    first_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    controller.set_map_studio_building_opening(
        room_resref=first_resref,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=1.25,
        height=2.2,
        bottom=0.0,
    )
    second_resref = controller.add_map_studio_building_room(
        points=((0.0, 5.0), (8.0, 5.0), (8.0, 10.0), (0.0, 10.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert {room.normalised_resref() for room in authored.rooms} == {first_resref, second_resref}
    first = next(room for room in authored.rooms if room.normalised_resref() == first_resref)
    opening = first.primitive.openings[0]
    assert math.isclose(opening.width, 6.16, abs_tol=1.0e-7)
    assert math.isclose(opening.height, 3.01, abs_tol=1.0e-7)
    assert opening.metadata["door_model_resref"] == "dor_lhr01"
    assert opening.metadata["door_appearance_id"] == 48
    assert opening.metadata["door_placement_id"].startswith("authored:door:")
    assert len(authored.placements.doors) == 1
    door = authored.placements.doors[0]
    assert door.template_resref == "gr_enddoor"
    assert math.isclose(door.position[0], 4.0, abs_tol=1.0e-7)
    assert math.isclose(door.position[1], 5.0, abs_tol=1.0e-7)

    geometry = compile_floor_plan_room_geometry(first.primitive)
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
    assert {
        "endar_door_frame",
        "endar_door_frame_light",
        "endar_door_transition_infill",
        "endar_door_transition_reveal",
    } <= roles
    transition_meshes = [
        mesh
        for mesh in geometry.helper_meshes
        if str(mesh.metadata.get("architecture_role") or "").startswith("endar_door_transition_")
    ]
    assert len(transition_meshes) == 7
    assert all(mesh.faces and mesh.vertices for mesh in transition_meshes)
    for room in authored.rooms:
        compiled = compile_floor_plan_room_geometry(room.primitive)
        assert compiled.room_mesh.faces
    preview = build_authored_module_preview_model(authored)
    assert preview.room_count == 2
    assert preview.model is not None

    resources = controller.authored_project_extra_resources()
    assert [(resref, restype) for resref, restype, _data in resources].count(("gr_enddoor", "utd")) == 1
    template = read_utd(next(data for resref, restype, data in resources if (resref, restype) == ("gr_enddoor", "utd")))
    assert template.appearance_id == 48
    assert template.static is False
    assert template.locked is False
    assert template.key_required is False

    export = controller.export_authored_module(tmp_path / "endar_door_export")
    assert export.ok is True
    assert export.package_verification is not None and export.package_verification.ok is True
    assert any(summary.resref == "gr_enddoor" and summary.restype == "utd" for summary in export.resources)


def test_t2909_whole_room_drag_snaps_to_drawn_door_and_pie_crosses_seam() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_layout import authored_room_connection_hooks
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdoorsnap", game="K1")
    target_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 6.0), (0.0, 6.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    controller.set_map_studio_building_opening(
        room_resref=target_room,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=1.25,
        height=2.2,
        bottom=0.0,
    )
    source_room = controller.add_map_studio_building_room(
        points=((12.0, 0.0), (20.0, 0.0), (20.0, 6.0), (12.0, 6.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=source_room,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=100.0,
    )
    preview = controller.preview_authored_room_drag_snap(
        source_room_resref=source_room,
        world_delta=broad["world_delta"],
    )
    assert preview["magnet_snapped"] is True
    assert preview["auto_cut_source"] is True
    assert preview["target_room_resref"] == target_room
    assert preview["source_edge_index"] == 0

    update = controller.connect_authored_room_drag_snap(preview)
    connected = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert update.source_hook.room_resref == source_room
    assert {room.normalised_resref() for room in connected.rooms} == {target_room, source_room}
    assert len(connected.placements.doors) == 1
    hooks = authored_room_connection_hooks(connected)
    assert len(hooks) == 2
    assert all(hook.connected_room_resref for hook in hooks)
    assert math.dist(hooks[0].position, hooks[1].position) <= 1.0e-7
    assert math.isclose(
        hooks[0].outward[0] * hooks[1].outward[0] + hooks[0].outward[1] * hooks[1].outward[1],
        -1.0,
        abs_tol=1.0e-7,
    )
    source = next(room for room in connected.rooms if room.normalised_resref() == source_room)
    source_opening = source.primitive.openings[0]
    assert source_opening.metadata["shared_connection_door"] is True
    assert source_opening.metadata["shared_door_placement_id"].startswith("authored:door:")
    assert connected.extra["last_room_connection"]["walkmesh_auto_generated"] is True
    assert connected.extra["last_room_connection"]["walkmesh_portal_validated"] is True
    assert set(connected.extra["last_room_connection"]["walkable_face_counts"]) == {target_room, source_room}
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.rooms.drag_snap_opening"

    walkmesh_build = compile_authored_room_connection_walkmeshes(connected)
    assert walkmesh_build.ready is True
    assert len(walkmesh_build.portals) == 1
    portal = walkmesh_build.portals[0]
    assert portal.midpoint_gap <= 1.0e-7
    room_order = {room.normalised_resref(): index for index, room in enumerate(connected.rooms)}
    source_face = walkmesh_build.room_woks[portal.source_room_resref].faces[portal.source_face_index]
    target_face = walkmesh_build.room_woks[portal.target_room_resref].faces[portal.target_face_index]
    assert getattr(source_face, ("trans1", "trans2", "trans3")[portal.source_local_edge]) == room_order[portal.target_room_resref]
    assert getattr(target_face, ("trans1", "trans2", "trans3")[portal.target_local_edge]) == room_order[portal.source_room_resref]

    registry = build_pie_entity_registry(connected)
    door_entity = registry.of_kind("door")[0]
    assert math.isclose(door_entity.facing, math.pi * 0.5, abs_tol=1.0e-7)
    assert math.isclose(float(door_entity.metadata["doorway_opening_width"]), 6.16, abs_tol=1.0e-7)
    combined = combine_authored_module_walkmesh(connected)
    session = MapStudioPIESession(combined.wok, game="K1", spawn_position=(4.0, 4.0, 0.0))
    session.entity_registry = registry
    assert session.validation.ok is True
    events = []
    for _index in range(240):
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=-90.0, run=True)
        events.extend(session.advance(1.0 / 30.0).events)
    assert "door_opened" in {event.kind for event in events}
    assert session.state.position[1] > 6.5


def test_t2909_vanilla_room_drag_magnets_to_every_authored_room_side() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import environment_kit_piece
    from src.core.modules.module_editor_controller import ModuleEditorController

    piece_id = "k1_m01aa_m01aa_08c"
    piece = environment_kit_piece(piece_id)
    assert piece is not None and len(piece.magnets) == 1
    hook = piece.magnets[0]
    hx, hy, hz = (float(value) for value in hook.local_position)

    controller = ModuleEditorController()
    controller.new_project(name="grwallsnap", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 6.5), (0.0, 6.5)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    # A content-browser drag is cursor-anchored: users point at the wall and
    # the room's hidden module origin must not affect whether its real LYT
    # doorway hook can engage the target.
    targets = (
        (0, (4.0, 0.0, 1.8)),
        (1, (8.0, 3.25, 1.8)),
        (2, (4.0, 6.5, 1.8)),
        (3, (0.0, 3.25, 1.8)),
    )
    for expected_edge, position in targets:
        preview = controller.preview_authored_terrain_kit_placement(
            asset_id=piece_id,
            position=position,
            rotation_degrees_z=0.0,
            scale=1.0,
        )
        assert preview["magnet_snapped"] is True
        assert preview["target_is_authored_wall"] is True
        assert preview["target_room_resref"] == room_resref
        assert preview["target_edge_index"] == expected_edge
        assert math.isclose(preview["opening_width"], 6.16, abs_tol=1.0e-7)
        assert math.isclose(preview["opening_height"], 3.01, abs_tol=1.0e-7)

        yaw = math.radians(float(preview["rotation_degrees_z"]))
        cosine, sine = math.cos(yaw), math.sin(yaw)
        snapped_hook = (
            float(preview["position"][0]) + (hx * cosine) - (hy * sine),
            float(preview["position"][1]) + (hx * sine) + (hy * cosine),
            float(preview["position"][2]) + hz,
        )
        start = ((0.0, 0.0), (8.0, 0.0), (8.0, 6.5), (0.0, 6.5))[expected_edge]
        end = ((8.0, 0.0), (8.0, 6.5), (0.0, 6.5), (0.0, 0.0))[expected_edge]
        fraction = float(preview["target_center_fraction"])
        expected = (
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
            0.0,
        )
        assert math.dist(snapped_hook, expected) <= 1.0e-6


def test_t2910_taris_apartment_vanilla_room_uses_the_same_wall_snap_contract() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import environment_kit_piece
    from src.core.modules.module_editor_controller import ModuleEditorController

    piece_id = "k1_m02aa_m02aa_01a"
    piece = environment_kit_piece(piece_id)
    assert piece is not None and piece.collection_id == "k1_m02aa" and piece.magnets

    controller = ModuleEditorController()
    controller.new_project(name="grtarissnap", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)),
        wall_height=2.55,
        style_id="architecture:k1_taris_apartments",
    )
    preview = controller.preview_authored_terrain_kit_placement(
        asset_id=piece_id,
        position=(20.0, 30.0, 0.0),
        rotation_degrees_z=0.0,
        scale=1.0,
    )

    assert preview["magnet_snapped"] is True
    assert preview["target_is_authored_wall"] is True
    assert preview["target_room_resref"] == room_resref
    assert preview["target_edge_index"] == 2
    assert preview["source_magnet_id"] == "door_03"
    assert math.isclose(preview["opening_width"], 4.5, abs_tol=1.0e-7)
    assert math.isclose(preview["opening_height"], 2.396, abs_tol=1.0e-7)

    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=1.8,
        height=2.2,
        bottom=0.0,
    )
    from pykotor.resource.generics.utd import read_utd

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.placements.doors) == 1
    assert authored.placements.doors[0].template_resref == "gr_tardoor"
    resources = controller.authored_project_extra_resources()
    template = read_utd(next(data for resref, restype, data in resources if (resref, restype) == ("gr_tardoor", "utd")))
    assert template.appearance_id == 20
    assert template.static is False


def test_t2909_endars_room_drop_inside_authored_room_auto_selects_a_free_wall() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Endar room-drop proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grendauto", game="K1")
    authored_room = controller.add_map_studio_building_room(
        points=((-6.0, 0.0), (6.0, 0.0), (6.0, 11.0), (-6.0, 11.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    # This is the workflow from the reported warning: the creator drops the
    # vanilla room on the authored room, not precisely within four metres of
    # one edge. Ghost Studio must select a viable wall before occupancy audit.
    preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m01aa_m01aa_08c",
        position=(0.0, 5.5, 0.0),
    )
    assert preview["magnet_snapped"] is True
    assert preview["target_is_authored_wall"] is True
    assert preview["target_room_resref"] == authored_room
    assert 0 <= int(preview["target_edge_index"]) <= 3

    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m01aa_m01aa_08c",
        position=(0.0, 5.5, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert stock_room != authored_room
    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True, build.blocking_issues
    assert len(build.portals) == 1
    assert build.portals[0].midpoint_gap <= 1.0e-5


def test_t2909_harbinger_reuses_measured_republic_warship_contour() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grharbinger", game="K2")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    harbinger = styles["architecture:k2_harbinger"]
    assert harbinger["architecture_profile"] == "harbinger"
    assert harbinger["architecture_shell_profile"] == "harbinger_corridor"
    assert harbinger["recommended_wall_height_m"] == 3.655
    assert "151har02" in harbinger["evidence_rooms"]

    controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)),
        wall_height=harbinger["recommended_wall_height_m"],
        style_id="architecture:k2_harbinger",
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    geometry = compile_floor_plan_room_geometry(authored.rooms[0].primitive)
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
    textures = {mesh.texture for mesh in geometry.helper_meshes}
    assert geometry.metadata["architecture_shell_profile"] == "harbinger_corridor"
    assert {"raised_floor_edge", "canted_upper_bulkhead", "arched_rib", "recessed_ceiling"} <= roles
    assert {"har_wl01", "har_tr02", "har_lt01", "har_wl09"} <= textures


def test_t2909_republic_warship_dressing_rows_are_portable_and_typed() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        environment_kit_drag_payload,
        environment_kit_piece_rows,
    )

    k1 = tuple(
        row
        for row in environment_kit_piece_rows(game="K1")
        if row["role"] == "dressing" and row["collection_id"] == "k1_endar_spire_dressing"
    )
    k2 = tuple(
        row
        for row in environment_kit_piece_rows(game="K2")
        if row["role"] == "dressing" and row["collection_id"] == "k2_harbinger_dressing"
    )
    assert {row["class_id"] for row in k1} == {
        "dressing:bridge_console",
        "dressing:wall_control",
        "dressing:observation_port",
        "dressing:wall_light",
    }
    assert {row["class_id"] for row in k2} == {row["class_id"] for row in k1}
    port = next(row for row in k1 if row["class_id"] == "dressing:observation_port")
    assert port["anchor_mode"] == "wall"
    assert port["has_backdrop"] is True
    payload = environment_kit_drag_payload(port["piece_id"])
    assert payload["anchor_mode"] == "wall"
    assert payload["snap_to_magnets"] is False
    console = next(row for row in k1 if row["class_id"] == "dressing:bridge_console")
    assert console["dimensions_m"] == (5.51, 2.25, 0.97)
    assert console["building_style_id"] == "architecture:k1_endar_spire"


def test_t2909_building_styles_group_complete_vanilla_room_collections() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import environment_kit_piece_rows

    rows = environment_kit_piece_rows(game="K1")
    endar = tuple(row for row in rows if row["building_style_id"] == "architecture:k1_endar_spire")
    assert {row["module_resref"] for row in endar} >= {"m01aa", "m01ab"}
    assert any(row["role"] == "dressing" for row in endar)
    assert any(row["role"] == "room_tile" and row["magnet_count"] > 0 for row in endar)

    taris = tuple(row for row in rows if row["building_style_id"] == "architecture:k1_taris_apartments")
    assert {row["module_resref"] for row in taris} >= {"m02aa", "m02ad"}

    korriban = tuple(row for row in rows if row["building_style_id"] == "architecture:k1_korriban_tombs")
    assert {row["module_resref"] for row in korriban} >= {"m37aa", "m38aa", "m38ab", "m39aa"}
    assert any(row["role"] in {"room_tile", "exterior_tile"} and row["magnet_count"] > 0 for row in korriban)
    assert {
        "room_tile:straight",
        "room_tile:bend",
        "room_tile:t_junction",
        "room_tile:four_way_hub",
        "room_tile:cross",
        "room_tile:dead_end",
        "room_tile:chamber",
    } <= {
        row["class_id"]
        for row in korriban
        if row["role"] == "room_tile"
    }
    assert {
        "dressing:tomb_relief",
        "dressing:tomb_buttress",
        "dressing:tomb_ceiling_rock",
        "dressing:tomb_rubble",
        "dressing:tomb_sarcophagus",
        "dressing:tomb_offerings",
        "dressing:tomb_floor_dais",
        "dressing:tomb_vault_pier",
        "dressing:tomb_vault_ring",
        "dressing:tomb_ritual_dais",
        "dressing:tomb_monument_pylon",
        "dressing:tomb_monument_rock",
    } <= {row["class_id"] for row in korriban if row["role"] == "dressing"}

    caves = tuple(row for row in rows if row["building_style_id"] == "architecture:k1_korriban_caves")
    assert {row["module_resref"] for row in caves} == {"m34aa"}
    assert sum(row["role"] in {"room_tile", "exterior_tile"} for row in caves) >= 13
    assert any(row["magnet_count"] >= 2 for row in caves if row["role"] in {"room_tile", "exterior_tile"})
    assert {
        "dressing:cave_cliff",
        "dressing:cave_web",
        "dressing:cave_water",
        "dressing:cave_rock_ridge",
        "dressing:cave_rock_shelf",
        "dressing:cave_web_curtain",
        "dressing:cave_water_large",
    } <= {
        row["class_id"] for row in caves if row["role"] == "dressing"
    }

    k2_rows = environment_kit_piece_rows(game="K2")
    secret_tomb = tuple(
        row for row in k2_rows if row["building_style_id"] == "architecture:k2_korriban_tombs"
    )
    assert {row["module_resref"] for row in secret_tomb} == {"711kor"}
    assert sum(row["role"] in {"room_tile", "exterior_tile"} for row in secret_tomb) >= 21
    assert all(
        row["magnet_count"] > 0
        for row in secret_tomb
        if row["role"] in {"room_tile", "exterior_tile"}
    )
    k2_caves = tuple(
        row for row in k2_rows if row["building_style_id"] == "architecture:k2_korriban_caves"
    )
    assert {row["module_resref"] for row in k2_caves} == {"710kor"}
    assert sum(row["role"] in {"room_tile", "exterior_tile"} for row in k2_caves) >= 12


def test_t2909_korriban_profiles_use_measured_vaults_and_organic_caves() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRoomPrimitive,
        FloorPlanWallOpening,
        compile_floor_plan_room_geometry,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.map_studio_pascal_building import available_pascal_building_styles

    styles = {style.style_id: style for style in available_pascal_building_styles()}
    assert styles["architecture:k1_korriban_tombs"].recommended_wall_height_m == 3.9
    assert styles["architecture:k2_korriban_tombs"].architecture_shell_profile == "korriban_tomb_ruined"
    assert styles["architecture:k1_korriban_caves"].source_room == "m34aa_01a"
    assert styles["architecture:k2_korriban_caves"].source_room == "710korb"

    def geometry(style_id: str, *, connected: bool = False):
        style = styles[style_id]
        opening = (
            FloorPlanWallOpening(
                name="cave_link",
                edge_index=1,
                center_fraction=0.5,
                width=style.recommended_door_width_m,
                height=style.recommended_door_height_m,
                metadata={
                    **({"connected_room_resref": "vanilla_room"} if connected else {}),
                    **(
                        {
                            "door_model_resref": "dor_lko04",
                            "door_aperture_width_m": 5.25,
                            "door_aperture_height_m": 3.75,
                            "door_outer_width_m": 6.802,
                            "door_outer_height_m": 3.9,
                        }
                        if "korriban_tombs" in style_id
                        else {}
                    ),
                },
            ),
        )
        return compile_floor_plan_room_geometry(
            FloorPlanRoomPrimitive(
                room_resref="grkorriban",
                points=((0.0, 0.0), (14.0, 0.0), (14.0, 10.0), (0.0, 10.0)),
                wall_height=style.recommended_wall_height_m,
                material=PrimitiveMaterial(texture=style.floor_texture),
                wall_material=PrimitiveMaterial(texture=style.wall_texture),
                ceiling_material=PrimitiveMaterial(texture=style.ceiling_texture),
                include_ceiling=True,
                openings=opening,
                metadata={
                    "architecture_profile": style.architecture_profile,
                    "architecture_shell_profile": style.architecture_shell_profile,
                    "architecture_accent_textures": style.accent_textures,
                    "architecture_evidence_rooms": style.evidence_rooms,
                },
            )
        )

    k1_tomb = geometry("architecture:k1_korriban_tombs", connected=True)
    k2_tomb = geometry("architecture:k2_korriban_tombs", connected=True)
    k1_cave = geometry("architecture:k1_korriban_caves", connected=True)
    roles_k1 = {str(mesh.metadata.get("architecture_role") or "") for mesh in k1_tomb.helper_meshes}
    roles_k2 = {str(mesh.metadata.get("architecture_role") or "") for mesh in k2_tomb.helper_meshes}
    cave_roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in k1_cave.helper_meshes}
    assert {
        "sith_relief_base",
        "sith_relief_wall",
        "upper_tomb_step",
        "sith_tomb_section_rib",
        "beveled_sith_relief_ledge",
        "beveled_sith_relief_ledge_cap",
        "korriban_door_frame_outer",
        "korriban_door_frame_middle",
        "korriban_door_frame_inner",
        "korriban_door_transition_reveal",
    } <= roles_k1
    assert {
        "broken_vault_shoulder",
        "eroded_sith_crown",
        "ruined_sith_tomb_pilaster",
        "broken_sith_relief_ledge_cap",
    } <= roles_k2
    assert {
        "shyrack_cliff_wall",
        "canted_rock_shoulders",
        "faceted_cave_ceiling",
        "korriban_cave_portal_rock_mound",
        "korriban_cave_portal_throat",
        "korriban_cave_portal_floor_shoulder",
        "korriban_cave_portal_threshold",
    } <= cave_roles
    assert 3.9 <= max(vertex[2] for mesh in k1_tomb.helper_meshes for vertex in mesh.vertices) < 4.0
    assert max(uv[0] for mesh in k1_tomb.helper_meshes for uv in mesh.uvs) > 2.0
    relief_caps = tuple(
        mesh
        for mesh in k1_tomb.helper_meshes
        if str(mesh.metadata.get("architecture_role") or "") == "beveled_sith_relief_ledge_cap"
    )
    assert relief_caps
    assert {str(mesh.metadata.get("relief_cap") or "") for mesh in relief_caps} == {
        "lower",
        "upper",
        "start",
        "end",
    }
    assert all(
        len({mesh.vertices[index] for index in face}) == 3
        for mesh in relief_caps
        for face in mesh.faces
    )
    assert max(vertex[2] for mesh in k1_cave.helper_meshes for vertex in mesh.vertices) >= 6.25
    assert all(
        len({mesh.vertices[index] for index in face}) == 3
        for mesh in k1_cave.helper_meshes
        for face in mesh.faces
    )


def test_t2909_supplied_module_transitions_preserve_uvs_and_build_shadowlands_tree_tunnel() -> None:
    _install_native_payload_paths()

    from types import SimpleNamespace

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRoomPrimitive,
        FloorPlanWallOpening,
        compile_floor_plan_room_geometry,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.map_studio_terrain_kit import (
        build_module_transition_shell_meshes,
        module_transition_fit_contract,
        module_transition_asset_for_profiles,
        terrain_kit_asset,
        terrain_kit_asset_path,
        terrain_kit_asset_rows,
        terrain_kit_runtime_resources,
    )

    expected_faces = {
        "korriban_cave_entrance": (6624, "gr_korrentr"),
        "shyrack_cave_entrance": (6273, "gr_shyrentr"),
        "shadowlands_module_transition": (4795, "gr_shadwarm"),
    }
    expected_yaw = {
        "korriban_cave_entrance": 180.0,
        "shyrack_cave_entrance": 90.0,
        "shadowlands_module_transition": 90.0,
    }
    rows = {
        row["asset_id"]: row
        for row in terrain_kit_asset_rows(game="K1")
        if row["asset_id"] in expected_faces
    }
    assert set(rows) == set(expected_faces)
    assert {row["category"] for row in rows.values()} == {"Module Transitions"}

    for asset_id, (face_count, texture) in expected_faces.items():
        asset = terrain_kit_asset(asset_id)
        assert terrain_kit_asset_path(asset).is_file()
        shells = build_module_transition_shell_meshes(
            asset_id,
            room_resref="grtransition",
            edge_index=0,
            opening_name="module_link",
            center=(0.0, 0.0, 0.0),
            tangent=(1.0, 0.0),
            inward_normal=(0.0, 1.0),
            opening_width=5.25,
            connected_room_resref="vanilla_room",
            game="K1",
        )
        assert shells
        assert 0 < sum(len(mesh.faces) for mesh in shells) <= face_count
        assert {mesh.texture for mesh in shells} == {texture}
        assert all(len(mesh.uvs) == len(mesh.vertices) for mesh in shells)
        assert all(len(mesh.normals) == len(mesh.vertices) for mesh in shells)
        assert all(mesh.metadata["uv0_preserved"] is True for mesh in shells)
        expected_policy = (
            "measured_host_recess_preserve_source_opening"
            if asset_id == "shadowlands_module_transition"
            else "detail_preserving_host_recess_minus_actor_clearance"
        )
        assert {
            mesh.metadata["geometry_trim_policy"] for mesh in shells
        } == {expected_policy}
        assert all(mesh.metadata["host_surface_overlap_trimmed"] is True for mesh in shells)
        assert all(mesh.metadata["host_wall_recess_required"] is True for mesh in shells)
        assert {
            bool(mesh.metadata["source_opening_preserved"]) for mesh in shells
        } == {asset_id == "shadowlands_module_transition"}
        if asset_id != "shadowlands_module_transition":
            for mesh in shells:
                clearance_half = float(mesh.metadata["player_clearance_half_width_m"])
                clearance_height = float(mesh.metadata["player_clearance_height_m"])
                clearance_depth = float(mesh.metadata["transition_length_m"]) * 0.5
                for face in mesh.faces:
                    centroid = tuple(
                        sum(float(mesh.vertices[int(index)][axis]) for index in face) / 3.0
                        for axis in range(3)
                    )
                    assert not (
                        abs(centroid[0]) < clearance_half - 1.0e-4
                        and abs(centroid[1]) < clearance_depth - 1.0e-4
                        and -0.07 < centroid[2] < clearance_height - 1.0e-4
                    )
        assert len({mesh.metadata["uniform_scale"] for mesh in shells}) == 1
        assert {mesh.metadata["source_yaw_degrees"] for mesh in shells} == {
            expected_yaw[asset_id]
        }
        fit = module_transition_fit_contract(asset_id, 5.25, 2.60, "K1")
        assert {
            round(float(mesh.metadata["host_opening_width_m"]), 6)
            for mesh in shells
        } == {round(fit.host_opening_width_m, 6)}
        if asset_id == "shadowlands_module_transition":
            output_x = [
                float(vertex[0])
                for mesh in shells
                for vertex in mesh.vertices
            ]
            assert max(output_x) - min(output_x) >= fit.source_width_m - 0.02
            assert fit.actor_clearance_width_m >= 3.40
            assert fit.uniform_scale == 6.30
            assert 0.40 <= fit.ground_embed_m <= 0.50
            assert min(
                float(vertex[2])
                for mesh in shells
                for vertex in mesh.vertices
            ) <= -fit.ground_embed_m + 0.01
            assert {
                round(float(mesh.metadata["ground_embed_m"]), 6)
                for mesh in shells
            } == {round(fit.ground_embed_m, 6)}

    tiled = build_module_transition_shell_meshes(
        "shadowlands_module_transition",
        room_resref="grtransition",
        edge_index=0,
        opening_name="long_module_link",
        center=(0.0, 0.0, 0.0),
        tangent=(1.0, 0.0),
        inward_normal=(0.0, 1.0),
        opening_width=5.25,
        connected_room_resref="vanilla_room",
        opening_height=3.25,
        transition_length_m=13.0,
        game="K1",
    )
    assert tiled
    tile_counts = {int(mesh.metadata["transition_tile_count"]) for mesh in tiled}
    assert len(tile_counts) == 1
    tile_count = tile_counts.pop()
    assert tile_count >= 3
    assert {mesh.metadata["transition_tile_index"] for mesh in tiled} == set(
        range(tile_count)
    )

    assert module_transition_asset_for_profiles(
        "korriban_tombs",
        "korriban_caves_k1",
    ) == "korriban_cave_entrance"
    assert module_transition_asset_for_profiles(
        "korriban_caves_k1",
        "korriban_tombs",
    ) == "shyrack_cave_entrance"
    assert module_transition_asset_for_profiles(
        "shadowlands",
        "shadowlands",
    ) == "shadowlands_module_transition"

    opening = FloorPlanWallOpening(
        name="forest_link",
        edge_index=1,
        center_fraction=0.5,
        width=4.0,
        height=3.25,
        bottom=0.0,
        metadata={
            "connected_room_resref": "m25aa_01a",
            "module_transition_asset_id": "shadowlands_module_transition",
            "module_transition_floor_required": True,
        },
    )
    primitive = FloorPlanRoomPrimitive(
        room_resref="grshadowlink",
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 14.0), (0.0, 14.0)),
        wall_height=6.0,
        material=PrimitiveMaterial(texture="lka_mud02"),
        wall_material=PrimitiveMaterial(texture="lka_mud02"),
        include_ceiling=False,
        openings=(opening,),
        metadata={
            "architecture_profile": "shadowlands",
            "architecture_shell_profile": "shadowlands_root_wall",
            "architecture_accent_textures": ("lka_bark06", "lka_plant02"),
        },
    )
    geometry = compile_floor_plan_room_geometry(primitive)
    roles = [str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes]
    shell_meshes = [
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("module_transition_asset_id") == "shadowlands_module_transition"
    ]
    assert shell_meshes
    assert {mesh.texture for mesh in shell_meshes} == {"gr_shadwarm"}
    # The supplied tree shell is the transition.  The former procedural tube,
    # threshold overlay, and panorama cards occupied the same space and were
    # the visible clipping/striping reported from PIE.
    assert roles.count("shadowlands_transition_floor") == 0
    assert roles.count("shadowlands_jungle_panorama_card") == 0
    assert roles.count("shadowlands_cave_connector") == 0
    fit = module_transition_fit_contract(
        "shadowlands_module_transition",
        opening.width,
        opening.height,
        "K1",
    )
    assert fit.host_opening_width_m > opening.width + 1.0
    assert fit.actor_clearance_width_m >= 3.40
    portal_center = float(opening.center_fraction) * 14.0
    for mesh in geometry.helper_meshes:
        if mesh in shell_meshes or int(mesh.metadata.get("edge_index", -1)) != 1:
            continue
        if mesh.metadata.get("surface_role") != "terrain_wall":
            continue
        for face in mesh.faces:
            centroid = tuple(
                sum(float(mesh.vertices[int(index)][axis]) for index in face) / 3.0
                for axis in range(3)
            )
            # The enlarged root plinth is intentionally buried below the
            # authored floor.  Underground berm faces may overlap that hidden
            # foundation; the visible wall recess must remain completely clear.
            if -1.0e-4 <= centroid[2] < fit.host_opening_height_m - 1.0e-4:
                assert abs(centroid[1] - portal_center) >= (
                    fit.host_opening_width_m * 0.5 - 1.0e-4
                )
    assert geometry.wok.walkable_face_count() > 0

    project = SimpleNamespace(
        rooms=(SimpleNamespace(metadata={}, primitive=primitive),),
    )
    resources = terrain_kit_runtime_resources(project)
    assert [(resref, extension) for resref, extension, _data in resources] == [
        ("gr_shadwarm", "tga")
    ]
    assert len(resources[0][2]) > 1024


def test_t2909_korriban_reliquary_chamber_is_tall_tiled_and_walkable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grkorrchamber", game="K1")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    style = styles["architecture:k1_korriban_tombs"]
    archetypes = {
        row["archetype_id"]: row
        for row in tuple(style["architecture_archetypes"])
    }

    assert set(archetypes) == {"corridor", "chamber", "junction", "burial", "monumental"}
    assert archetypes["corridor"]["shell_profile"] == "korriban_tomb"
    assert archetypes["corridor"]["recommended_wall_height_m"] == pytest.approx(3.90)
    assert archetypes["chamber"]["shell_profile"] == "korriban_tomb_chamber"
    assert archetypes["chamber"]["recommended_wall_height_m"] == pytest.approx(10.35)
    assert archetypes["chamber"]["recommended_floor_to_floor_m"] == pytest.approx(11.10)
    assert {
        "m37aa_12",
        "m38aa_08",
        "m38aa_11",
        "m39aa_07",
    } <= set(archetypes["chamber"]["evidence_rooms"])
    assert archetypes["junction"]["shell_profile"] == "korriban_tomb_junction"
    assert archetypes["junction"]["recommended_wall_height_m"] == pytest.approx(10.24)
    assert {"m38aa_06", "m38aa_08", "m39aa_16"} <= set(archetypes["junction"]["evidence_rooms"])
    assert archetypes["burial"]["shell_profile"] == "korriban_tomb_burial"
    assert archetypes["burial"]["recommended_wall_height_m"] == pytest.approx(10.28)
    assert {"m37aa_12", "m38aa_11", "m39aa_13"} <= set(archetypes["burial"]["evidence_rooms"])
    assert archetypes["monumental"]["shell_profile"] == "korriban_tomb_monumental"
    assert archetypes["monumental"]["recommended_wall_height_m"] == pytest.approx(22.08)
    assert archetypes["monumental"]["evidence_rooms"] == ("m39aa_07",)
    assert len(style["evidence_rooms"]) >= 23

    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 15.0), (0.0, 15.0)),
        wall_height=10.35,
        style_id=style["style_id"],
        architecture_archetype="chamber",
        include_ceiling=True,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == 1
    room = authored.rooms[0]
    assert room.room_resref == room_resref
    assert room.primitive.metadata["architecture_archetype"] == "chamber"
    assert room.primitive.metadata["architecture_shell_profile"] == "korriban_tomb_chamber"
    assert room.metadata["architecture_archetype"] == "chamber"

    geometry = compile_floor_plan_room_geometry(room.primitive)
    roles = {
        str(mesh.metadata.get("architecture_role") or "")
        for mesh in geometry.helper_meshes
    }
    assert {
        "chamber_relief_wall",
        "chamber_corbel_course",
        "chamber_vault_shoulder",
        "sith_chamber_relief_pilaster",
        "sith_chamber_corner_buttress",
        "sith_chamber_vault_capital",
        "beveled_sith_chamber_relief_ledge",
        "beveled_sith_chamber_relief_ledge_cap",
        "reliquary_vault_ceiling",
    } <= roles
    assert geometry.metadata["architecture_shell_profile"] == "korriban_tomb_chamber"
    assert geometry.metadata["has_ceiling"] is True
    assert geometry.wok.walkable_face_count() > 0
    assert controller.project.extra_sections["authored_module"]["extra"]["last_walkmesh_build"][
        "walkable_face_counts"
    ][room_resref] > 0
    assert max(
        float(vertex[2])
        for mesh in geometry.helper_meshes
        for vertex in mesh.vertices
    ) == pytest.approx(10.35)

    uv_spans = [
        max(max(value[0] for value in mesh.uvs) - min(value[0] for value in mesh.uvs),
            max(value[1] for value in mesh.uvs) - min(value[1] for value in mesh.uvs))
        for mesh in geometry.helper_meshes
        if mesh.uvs
    ]
    assert max(uv_spans) > 4.0

    def doubled_triangle_area(mesh, face) -> float:
        first, second, third = (mesh.vertices[index] for index in face)
        ab = tuple(second[index] - first[index] for index in range(3))
        ac = tuple(third[index] - first[index] for index in range(3))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        return sum(value * value for value in cross) ** 0.5

    assert all(
        doubled_triangle_area(mesh, face) > 1.0e-8
        for mesh in geometry.helper_meshes
        for face in mesh.faces
    )
    command = controller.command_history.undo_stack[-1]
    assert command.metadata["architecture_archetype"] == "chamber"
    assert command.metadata["architecture_shell_profile"] == "korriban_tomb_chamber"
    assert command.metadata["walkmesh_auto_generated"] is True

    with pytest.raises(ValueError, match="at least 9 m wide"):
        controller.add_map_studio_building_room(
            points=((22.0, 0.0), (30.0, 0.0), (30.0, 8.0), (22.0, 8.0)),
            wall_height=10.35,
            style_id=style["style_id"],
            architecture_archetype="chamber",
        )
    with pytest.raises(ValueError, match="at least 9.75 m"):
        controller.add_map_studio_building_room(
            points=((22.0, 0.0), (34.0, 0.0), (34.0, 12.0), (22.0, 12.0)),
            wall_height=8.0,
            style_id=style["style_id"],
            architecture_archetype="chamber",
        )


def test_t2909_korriban_junction_burial_and_monumental_contours_are_distinct_and_walkable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grkorrforms", game="K1")
    style = next(
        row
        for row in controller.available_map_studio_building_styles()
        if row["style_id"] == "architecture:k1_korriban_tombs"
    )
    cases = (
        (
            "junction",
            "korriban_tomb_junction",
            ((0.0, 0.0), (18.0, 0.0), (18.0, 15.0), (0.0, 15.0)),
            10.24,
            {
                "junction_cross_vault_keystone",
                "junction_cross_vault_cap",
                "sith_junction_cross_pier",
                "sith_junction_vault_capital",
                "beveled_junction_relief_ledge",
                "junction_vault_ceiling",
            },
        ),
        (
            "burial",
            "korriban_tomb_burial",
            ((24.0, 0.0), (39.0, 0.0), (39.0, 12.0), (24.0, 12.0)),
            10.28,
            {
                "burial_niche_back",
                "burial_niche_jamb",
                "burial_niche_lintel",
                "burial_sarcophagus_plinth",
                "beveled_burial_relief_ledge",
                "burial_vault_ceiling",
            },
        ),
        (
            "monumental",
            "korriban_tomb_monumental",
            ((48.0, 0.0), (90.0, 0.0), (90.0, 31.5), (48.0, 31.5)),
            22.08,
            {
                "monumental_tomb_pylon",
                "monumental_corbel_capital",
                "sith_monumental_corner_pylon",
                "sith_monumental_vault_capital",
                "beveled_monumental_relief_ledge",
                "monumental_vault_ceiling",
            },
        ),
    )
    expected_resrefs: list[str] = []
    generated_walkmesh_counts: dict[str, int] = {}
    for archetype, shell_profile, points, height, required_roles in cases:
        room_resref = controller.add_map_studio_building_room(
            points=points,
            wall_height=height,
            style_id=style["style_id"],
            architecture_archetype=archetype,
            include_ceiling=True,
        )
        expected_resrefs.append(room_resref)
        last_walkmesh_build = controller.project.extra_sections["authored_module"]["extra"][
            "last_walkmesh_build"
        ]
        assert last_walkmesh_build["room_resrefs"] == [room_resref]
        generated_walkmesh_counts[room_resref] = last_walkmesh_build["walkable_face_counts"][room_resref]
        authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
        room = next(item for item in authored.rooms if item.room_resref == room_resref)
        geometry = compile_floor_plan_room_geometry(room.primitive)
        roles = {
            str(mesh.metadata.get("architecture_role") or "")
            for mesh in geometry.helper_meshes
        }

        assert room.metadata["architecture_archetype"] == archetype
        assert room.primitive.metadata["architecture_archetype"] == archetype
        assert room.primitive.metadata["architecture_shell_profile"] == shell_profile
        assert geometry.metadata["architecture_shell_profile"] == shell_profile
        assert geometry.metadata["has_ceiling"] is True
        assert required_roles <= roles
        assert geometry.wok.walkable_face_count() > 0
        floor_u_span = max(value[0] for value in geometry.room_mesh.uvs) - min(
            value[0] for value in geometry.room_mesh.uvs
        )
        floor_v_span = max(value[1] for value in geometry.room_mesh.uvs) - min(
            value[1] for value in geometry.room_mesh.uvs
        )
        world_width = max(point[0] for point in points) - min(point[0] for point in points)
        world_depth = max(point[1] for point in points) - min(point[1] for point in points)
        assert geometry.room_mesh.metadata["uv_projection"] == "world_xy_tiled"
        assert geometry.room_mesh.metadata["texture_stretching_prevented"] is True
        assert world_width / floor_u_span == pytest.approx(3.0)
        assert world_depth / floor_v_span == pytest.approx(3.0)
        assert max(
            float(vertex[2])
            for mesh in geometry.helper_meshes
            for vertex in mesh.vertices
        ) == pytest.approx(height)
        assert max(
            max(
                max(value[0] for value in mesh.uvs) - min(value[0] for value in mesh.uvs),
                max(value[1] for value in mesh.uvs) - min(value[1] for value in mesh.uvs),
            )
            for mesh in geometry.helper_meshes
            if mesh.uvs
        ) > 4.0
        assert all(
            len({mesh.vertices[index] for index in face}) == 3
            for mesh in geometry.helper_meshes
            for face in mesh.faces
        )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == 3
    assert {room.room_resref for room in authored.rooms} == set(expected_resrefs)
    assert all(generated_walkmesh_counts[room_resref] > 0 for room_resref in expected_resrefs)

    with pytest.raises(ValueError, match="at least 18 m wide"):
        controller.add_map_studio_building_room(
            points=((96.0, 0.0), (111.0, 0.0), (111.0, 15.0), (96.0, 15.0)),
            wall_height=22.08,
            style_id=style["style_id"],
            architecture_archetype="monumental",
        )
    with pytest.raises(ValueError, match="at least 20 m"):
        controller.add_map_studio_building_room(
            points=((96.0, 0.0), (120.0, 0.0), (120.0, 24.0), (96.0, 24.0)),
            wall_height=18.0,
            style_id=style["style_id"],
            architecture_archetype="monumental",
        )


def test_t2909_korriban_bridge_uses_stock_doors_and_two_reciprocal_wok_portals() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from pykotor.resource.generics.utd import read_utd

    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_operations import bridge_authored_floor_plan_edges
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.map_studio_pascal_building import pascal_architecture_runtime_resources

    base = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grkbridge",
        game="K1",
    )
    metadata = {
        "source": "map_studio:pascal_building",
        "architecture_profile": "korriban_tombs",
        "architecture_shell_profile": "korriban_tomb",
    }
    primitive = FloorPlanRoomPrimitive(
        room_resref="grk_a",
        points=((-8.0, -6.0), (8.0, -6.0), (8.0, 6.0), (-8.0, 6.0)),
        wall_height=3.9,
        material=PrimitiveMaterial(texture="lko_flr01"),
        wall_material=PrimitiveMaterial(texture="lko_wal07"),
        ceiling_material=PrimitiveMaterial(texture="lko_wal07"),
        include_ceiling=True,
        metadata=metadata,
    )
    first = replace(
        base.rooms[0],
        room_resref="grk_a",
        primitive=primitive,
        composition=None,
        position=(0.0, 0.0, 0.0),
        visible_rooms=(),
        metadata={"primitive": "floor_plan_extrusion"},
    )
    second = replace(
        first,
        room_resref="grk_b",
        primitive=replace(primitive, room_resref="grk_b"),
        position=(24.0, 0.0, 0.0),
    )
    project = bridge_authored_floor_plan_edges(
        replace(base, rooms=(first, second), lights=()),
        first_room_resref="grk_a",
        first_edge_index=1,
        second_room_resref="grk_b",
        second_edge_index=3,
        result_room_resref="grk_link",
    )

    bridge = next(room for room in project.rooms if room.room_resref == "grk_link")
    walkmesh = compile_authored_room_connection_walkmeshes(project)
    assert bridge.primitive.metadata["architecture_profile"] == "korriban_tombs"
    assert bridge.primitive.wall_height == 3.9
    assert tuple(bridge.primitive.points) == (
        (8.0, -3.401),
        (8.0, 3.401),
        (16.0, 3.401),
        (16.0, -3.401),
    )
    assert {opening.name for opening in bridge.primitive.openings} == {
        "bridge_door_first",
        "bridge_door_second",
    }
    assert len(project.placements.doors) == 2
    assert {door.template_resref for door in project.placements.doors} == {"gr_korrdoor"}
    assert walkmesh.ready is True
    assert len(walkmesh.portals) == 2
    assert all(portal.midpoint_gap <= 1.0e-8 for portal in walkmesh.portals)
    resources = pascal_architecture_runtime_resources(project)
    door_bytes = next(data for resref, restype, data in resources if (resref, restype) == ("gr_korrdoor", "utd"))
    door = read_utd(door_bytes)
    assert door.appearance_id == 40
    assert door.static is False


def test_t2909_shyrack_rooms_use_wok_transition_magnets() -> None:
    _install_native_payload_paths()

    import math

    from src.core.modules.map_studio_environment_kits import environment_kit_piece

    for piece_id in ("k1_m34aa_m34aa_01a", "k2_710kor_710korb"):
        piece = environment_kit_piece(piece_id)
        assert piece is not None
        assert len(piece.magnets) >= 2
        assert all(magnet.source == "wok_transition_edge_group" for magnet in piece.magnets)
        assert all(
            math.isclose(magnet.snap_facing_radians, magnet.yaw_radians, abs_tol=1.0e-9)
            for magnet in piece.magnets
        )


def test_t2909_shyrack_measured_dressing_previews_places_and_preserves_uvs() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Shyrack dressing proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grshyrdress", game="K1")
    specs = (
        ("k1_korriban_caves_rock_ridge", (0.0, 0.0, 0.0), "m34aa_05a", "lko_rock5", 65),
        ("k1_korriban_caves_rock_shelf", (20.0, 0.0, 0.0), "m34aa_06a", "lko_rock5", 59),
        ("k1_korriban_caves_web_curtain", (40.0, 0.0, 2.5), "m34aa_07b", "lko_web", 3),
        ("k1_korriban_caves_large_water_sheet", (60.0, 0.0, 0.0), "m34aa_03a", "lko_water01", 2),
    )
    placed: list[str] = []
    for piece_id, position, source_room, texture, triangle_count in specs:
        assert controller.map_studio_environment_kit_preview_model(
            piece_id,
            resource_manager=resources,
        ) is not None
        room_resref = controller.add_authored_environment_kit_piece(
            piece_id=piece_id,
            position=position,
            resource_manager=resources,
        )
        placed.append(room_resref)
        authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
        room = next(candidate for candidate in authored.rooms if candidate.normalised_resref() == room_resref)
        primitive = room.primitive
        assert room.metadata["environment_kit_source_module"] == "m34aa"
        assert room.metadata["environment_kit_source_room"] == source_room
        assert primitive.metadata["visual_only"] is True
        assert isinstance(primitive.metadata["source_lightmaps_removed_for_relighting"], bool)
        assert sum(len(surface.faces) for surface in primitive.surfaces) == triangle_count
        assert {surface.texture for surface in primitive.surfaces} == {texture}
        assert all(len(surface.vertices) == len(surface.uvs) for surface in primitive.surfaces)
        assert all(not surface.lightmap and not surface.uvs_lm for surface in primitive.surfaces)
        assert primitive.wok is not None and primitive.wok.faces == []

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == len(specs)
    assert len(set(placed)) == len(specs)


def test_t2909_architecture_corpus_rebuild_preserves_other_profile_rows(tmp_path: Path) -> None:
    import json

    from scripts.build_kotor_architecture_corpus import _preserved_manifest_rows

    retained_sequence = tmp_path / "endar_spire" / "m01aa_01a.mesh.txt"
    retained_sequence.parent.mkdir(parents=True)
    retained_sequence.write_text("# retained\n", encoding="utf-8")
    rebuilt_sequence = tmp_path / "korriban_caves_k1" / "m34aa_01a.mesh.txt"
    rebuilt_sequence.parent.mkdir(parents=True)
    rebuilt_sequence.write_text("# replaced\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "rooms": [
                    {
                        "profile": "endar_spire",
                        "room_resref": "m01aa_01a",
                        "sequence_path": "endar_spire/m01aa_01a.mesh.txt",
                    },
                    {
                        "profile": "korriban_caves_k1",
                        "room_resref": "m34aa_01a",
                        "sequence_path": "korriban_caves_k1/m34aa_01a.mesh.txt",
                    },
                    {
                        "profile": "taris_apartments",
                        "room_resref": "missing",
                        "sequence_path": "taris_apartments/missing.mesh.txt",
                    },
                    {
                        "profile": "invalid",
                        "room_resref": "escape",
                        "sequence_path": "../outside.mesh.txt",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = _preserved_manifest_rows(
        tmp_path,
        rebuilt_profiles={"korriban_caves_k1"},
    )

    assert rows == [
        {
            "profile": "endar_spire",
            "room_resref": "m01aa_01a",
            "sequence_path": "endar_spire/m01aa_01a.mesh.txt",
        }
    ]


def test_t2909_shyrack_generated_room_snaps_to_stock_cavern_and_traverses(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Shyrack mixed-room proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grshyrlego", game="K1")
    generated_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (24.0, 0.0), (24.0, 18.0), (0.0, 18.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_caves",
        include_ceiling=True,
    )
    preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m34aa_m34aa_01a",
        position=(12.0, 18.0, 0.0),
    )
    assert preview["magnet_snapped"] is True
    assert preview["target_is_authored_wall"] is True
    assert preview["target_room_resref"] == generated_room
    assert preview["target_edge_index"] == 2
    assert preview["opening_width"] == pytest.approx(5.0)
    assert preview["opening_height"] == pytest.approx(4.15)

    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m34aa_m34aa_01a",
        position=(12.0, 18.0, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == 2
    generated = next(room for room in authored.rooms if room.normalised_resref() == generated_room)
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)

    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True, build.blocking_issues
    assert len(build.portals) == 1
    portal = build.portals[0]
    assert portal.midpoint_gap <= 1.0e-5
    assert portal.source_midpoint == pytest.approx((12.0, 18.0, 0.0), abs=1.0e-5)
    assert portal.target_midpoint == pytest.approx((12.0, 18.0, 0.0), abs=1.0e-5)

    assert stock.metadata["environment_kit_source_module"] == "m34aa"
    assert stock.metadata["environment_kit_source_room"] == "m34aa_01a"
    trim = stock.primitive.metadata["environment_kit_connection_trim"]
    assert trim["operation"] == "portal_half_space_trim"
    assert 0 < int(trim["render_faces_after"]) <= int(trim["render_faces_before"])
    assert trim["wok_shared_vertex_policy"] == "preserved-imported-raw-indices"
    assert trim["wok_visual_clip_excluded"] is True
    assert stock.primitive.wok is not None and len(stock.primitive.wok.faces) > 0
    assert all(
        not surface.uvs or len(surface.uvs) == len(surface.vertices)
        for surface in stock.primitive.surfaces
    )
    assert max(
        max(abs(float(value)) for uv in surface.uvs for value in uv)
        for surface in stock.primitive.surfaces
        if surface.uvs
    ) > 1.0

    opening = generated.primitive.openings[0]
    assert 1.60 < opening.width < 2.0
    assert opening.height == pytest.approx(4.15)
    assert opening.metadata["walkmesh_portal_source"] == "environment_kit_stock_threshold"
    assert authored.placements.doors == ()

    geometry = compile_authored_room_spec(generated)
    connectors = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("architecture_role") == "korriban_cave_connector"
    )
    assert connectors
    assert {mesh.metadata.get("connected_room_resref") for mesh in connectors} == {stock_room}
    assert min(float(vertex[2]) for mesh in connectors for vertex in mesh.vertices) == pytest.approx(0.0)
    assert all(
        len({mesh.vertices[index] for index in face}) == 3
        for mesh in geometry.helper_meshes
        for face in mesh.faces
    )

    projected = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("surface_role") in {"cave_wall", "cave_ceiling"}
    )
    assert projected
    for mesh in projected:
        for face in mesh.faces:
            normal = mesh.normals[int(face[0])]
            abs_normal = tuple(abs(float(component)) for component in normal)
            for vertex_index in face:
                vertex = mesh.vertices[int(vertex_index)]
                uv = mesh.uvs[int(vertex_index)]
                if abs_normal[2] >= abs_normal[0] and abs_normal[2] >= abs_normal[1]:
                    expected = (float(vertex[0]) * 0.30, float(vertex[1]) * 0.30)
                elif abs_normal[0] >= abs_normal[1]:
                    expected = (float(vertex[1]) * 0.30, float(vertex[2]) * 0.30)
                else:
                    expected = (float(vertex[0]) * 0.30, float(vertex[2]) * 0.30)
                assert uv == pytest.approx(expected)

    combined = combine_authored_module_walkmesh(authored)
    assert not combined.blocking_issues
    session = MapStudioPIESession(
        combined.wok,
        game="K1",
        spawn_position=(12.0, 16.0, 0.05),
    )
    assert session.validation.ok is True
    for _index in range(360):
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=-90.0, run=True)
        session.advance(1.0 / 30.0)
    assert session.state.position[1] > 24.0

    export = controller.export_authored_module(tmp_path / "shyrack_connection")
    assert export.ok is True
    assert export.package_verification is not None and export.package_verification.ok is True
    assert set(export.package_verification.parsed_wok) == {
        f"{generated_room}.wok",
        f"{stock_room}.wok",
    }


def test_t2909_tomb_to_concave_shyrack_to_vanilla_tomb_chain(tmp_path: Path) -> None:
    _install_native_payload_paths()

    import statistics

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the cross-style Shyrack proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grshyrchain", game="K1")
    tomb_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 14.0), (0.0, 14.0)),
        wall_height=3.9,
        style_id="architecture:k1_korriban_tombs",
    )
    controller.set_map_studio_building_opening(
        room_resref=tomb_room,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=5.25,
        height=3.75,
        bottom=0.0,
    )
    cave_room = controller.add_map_studio_building_room(
        points=((-3.0, 16.0), (21.0, 16.0), (21.0, 34.0), (-3.0, 34.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_caves",
        include_ceiling=True,
    )
    controller.set_map_studio_building_opening(
        room_resref=cave_room,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=5.25,
        height=3.75,
        bottom=0.0,
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=cave_room,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=100.0,
    )
    preview = controller.preview_authored_room_drag_snap(
        source_room_resref=cave_room,
        world_delta=broad["world_delta"],
    )
    assert preview["magnet_snapped"] is True
    assert preview["source_edge_index"] == 0
    assert preview["target_room_resref"] == tomb_room
    assert preview["auto_cut_source"] is False
    controller.connect_authored_room_drag_snap(preview)

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    cave_before_stock = next(room for room in authored.rooms if room.normalised_resref() == cave_room)
    cave_points = tuple(cave_before_stock.primitive.points)
    cave_origin = tuple(float(value) for value in cave_before_stock.position)
    north_start = cave_points[2]
    north_end = cave_points[3]
    north_midpoint = (
        cave_origin[0] + (float(north_start[0]) + float(north_end[0])) * 0.5,
        cave_origin[1] + (float(north_start[1]) + float(north_end[1])) * 0.5,
        cave_origin[2],
    )
    stock_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m38aa_m38aa_02",
        position=north_midpoint,
    )
    assert stock_preview["magnet_snapped"] is True
    assert stock_preview["target_is_authored_wall"] is True
    assert stock_preview["target_room_resref"] == cave_room
    assert stock_preview["target_edge_index"] == 2
    stock_tomb = controller.add_authored_environment_kit_piece(
        piece_id="k1_m38aa_m38aa_02",
        position=north_midpoint,
        resource_manager=resources,
    )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert {room.normalised_resref() for room in authored.rooms} == {
        tomb_room,
        cave_room,
        stock_tomb,
    }
    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True, build.blocking_issues
    assert len(build.portals) == 2
    assert all(portal.midpoint_gap <= 1.0e-5 for portal in build.portals)
    assert {
        frozenset((portal.source_room_resref, portal.target_room_resref))
        for portal in build.portals
    } == {
        frozenset((tomb_room, cave_room)),
        frozenset((cave_room, stock_tomb)),
    }

    cave = next(room for room in authored.rooms if room.normalised_resref() == cave_room)
    tomb = next(room for room in authored.rooms if room.normalised_resref() == tomb_room)
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_tomb)
    assert stock.metadata["environment_kit_source_module"] == "m38aa"
    assert stock.metadata["environment_kit_source_room"] == "m38aa_02"
    cave_openings = tuple(cave.primitive.openings)
    assert len(cave_openings) == 2
    tomb_opening = next(
        opening
        for opening in tomb.primitive.openings
        if str(dict(opening.metadata or {}).get("connected_room_resref") or "").strip().lower()
        == cave_room
    )
    assert tomb_opening.metadata["module_transition_asset_id"] == "korriban_cave_entrance"
    cave_tomb_opening = next(
        opening
        for opening in cave_openings
        if str(dict(opening.metadata or {}).get("connected_room_resref") or "").strip().lower()
        == tomb_room
    )
    assert "module_transition_asset_id" not in cave_tomb_opening.metadata
    stock_opening = next(
        opening
        for opening in cave_openings
        if str(dict(opening.metadata or {}).get("connected_room_resref") or "").strip().lower()
        == stock_tomb
    )
    assert stock_opening.metadata["module_transition_asset_id"] == "shyrack_cave_entrance"
    assert stock_opening.metadata["open_module_transition"] is True
    assert stock_opening.metadata["cave_archway_transition"] is True
    assert stock_opening.metadata["suppress_door_actor"] is True
    assert bool(stock_opening.metadata.get("shared_connection_door", False)) is False
    assert "cross_style_transition" not in stock_opening.metadata
    assert "door_model_resref" not in stock_opening.metadata
    assert "cross_style_transition_actor" not in stock_opening.metadata
    assert len(authored.placements.doors) == 0

    geometry = compile_authored_room_spec(cave)
    roles = [
        str(mesh.metadata.get("architecture_role") or "")
        for mesh in geometry.helper_meshes
    ]
    assert roles.count("shyrack_stalactite") >= 2
    assert roles.count("shyrack_stalagmite") >= 2
    ceiling = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("architecture_role") == "faceted_cave_ceiling"
    )
    assert len(ceiling) >= 16
    assert {
        str(mesh.metadata.get("ceiling_region") or "")
        for mesh in ceiling
    } == {"concave_outer_pocket", "irregular_inner_vault"}
    assert not any(
        str(mesh.metadata.get("architecture_role") or "").startswith("korriban_door_frame_")
        for mesh in geometry.helper_meshes
    )

    # Measure the actual top edge of each wall contour band against authored
    # edge 1.  Multiple decreases prove the shell is re-entrant rather than a
    # monotonic inward berm with noisy triangulation.
    edge_start = cave.primitive.points[1]
    edge_end = cave.primitive.points[2]
    dx = float(edge_end[0]) - float(edge_start[0])
    dy = float(edge_end[1]) - float(edge_start[1])
    edge_length = math.hypot(dx, dy)
    band_depths: dict[int, list[float]] = {}
    for mesh in geometry.helper_meshes:
        if mesh.metadata.get("surface_role") != "cave_wall":
            continue
        if int(mesh.metadata.get("edge_index", -1)) != 1:
            continue
        band = int(mesh.metadata["contour_band"])
        top_z = max(float(vertex[2]) for vertex in mesh.vertices)
        for vertex in mesh.vertices:
            if math.isclose(float(vertex[2]), top_z, abs_tol=1.0e-7):
                inward = (
                    dx * (float(vertex[1]) - float(edge_start[1]))
                    - dy * (float(vertex[0]) - float(edge_start[0]))
                ) / edge_length
                band_depths.setdefault(band, []).append(inward)
    ordered_depths = [
        statistics.median(band_depths[index])
        for index in sorted(band_depths)
    ]
    assert sum(
        following < previous - 0.05
        for previous, following in zip(ordered_depths, ordered_depths[1:])
    ) >= 2

    textured_organic = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("surface_role") in {
            "cave_wall",
            "cave_ceiling",
            "cave_formation",
        }
    )
    assert textured_organic
    assert all(len(mesh.vertices) == len(mesh.uvs) for mesh in textured_organic)
    assert max(
        max(abs(float(value)) for uv in mesh.uvs for value in uv)
        for mesh in textured_organic
        if mesh.uvs
    ) > 1.0
    assert all(
        len({mesh.vertices[index] for index in face}) == 3
        for mesh in geometry.helper_meshes
        for face in mesh.faces
    )

    combined = combine_authored_module_walkmesh(authored)
    assert not combined.blocking_issues
    session = MapStudioPIESession(
        combined.wok,
        game="K1",
        spawn_position=(9.0, 12.0, 0.05),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    assert session.validation.ok is True
    events = []
    for _index in range(720):
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=-90.0, run=True)
        events.extend(session.advance(1.0 / 30.0).events)
    assert "door_opened" not in {event.kind for event in events}
    assert session.state.position[1] > north_midpoint[1] + 0.5

    controller.save_project(tmp_path / "grshyrchain.kmap")
    export = controller.export_authored_module(tmp_path / "shyrack_tomb_chain")
    assert export.ok is True
    assert export.package_verification is not None and export.package_verification.ok is True
    assert set(export.package_verification.parsed_wok) == {
        f"{tomb_room}.wok",
        f"{cave_room}.wok",
        f"{stock_tomb}.wok",
    }


def test_t2909_korriban_tomb_room_snaps_through_measured_frame_and_reciprocal_wok() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Korriban mixed-room proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grkorrmix", game="K1")
    generated_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (20.0, 0.0), (20.0, 14.0), (0.0, 14.0)),
        wall_height=3.9,
        style_id="architecture:k1_korriban_tombs",
    )
    preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m38aa_m38aa_02",
        position=(10.0, 14.0, 0.0),
    )
    assert preview["magnet_snapped"] is True
    assert preview["target_is_authored_wall"] is True
    assert preview["target_room_resref"] == generated_room
    assert preview["target_edge_index"] == 2
    assert preview["opening_width"] == pytest.approx(5.25)
    assert preview["opening_height"] == pytest.approx(3.75)

    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m38aa_m38aa_02",
        position=(10.0, 14.0, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True, build.blocking_issues
    assert len(build.portals) == 1
    portal = build.portals[0]
    assert portal.midpoint_gap <= 1.0e-8
    assert portal.source_midpoint == pytest.approx((10.0, 14.0, 0.0))
    assert portal.target_midpoint == pytest.approx((10.0, 14.0, 0.0))

    generated = next(room for room in authored.rooms if room.normalised_resref() == generated_room)
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)
    assert stock.metadata["environment_kit_source_module"] == "m38aa"
    assert stock.metadata["environment_kit_source_room"] == "m38aa_02"
    assert stock.primitive.wok is not None and len(stock.primitive.wok.faces) == 122
    opening = generated.primitive.openings[0]
    # The render aperture follows DOR_LKO04's authored 5.25 m clearance while
    # the reciprocal WOK edge remains the exact 5.100006 m retail threshold.
    assert opening.width == pytest.approx(5.25)
    generated_wok = build.room_woks[generated_room]
    generated_face_index = (
        portal.source_face_index
        if portal.source_room_resref == generated_room
        else portal.target_face_index
    )
    generated_local_edge = (
        portal.source_local_edge
        if portal.source_room_resref == generated_room
        else portal.target_local_edge
    )
    generated_face = generated_wok.faces[generated_face_index]
    generated_vertices = generated_wok.verts
    generated_edge = (
        (generated_vertices[generated_face.v1], generated_vertices[generated_face.v2]),
        (generated_vertices[generated_face.v2], generated_vertices[generated_face.v3]),
        (generated_vertices[generated_face.v3], generated_vertices[generated_face.v1]),
    )[generated_local_edge]
    assert math.dist(generated_edge[0], generated_edge[1]) == pytest.approx(5.100006103515625)
    assert opening.metadata["door_model_resref"] == "dor_lko04"
    assert opening.metadata["door_outer_width_m"] == pytest.approx(6.802)
    assert opening.metadata["door_outer_height_m"] == pytest.approx(3.9)
    assert {door.template_resref for door in authored.placements.doors} == {"gr_korrdoor"}

    geometry = compile_authored_room_spec(generated)
    frame_meshes = tuple(
        mesh
        for mesh in geometry.helper_meshes
        if str(mesh.metadata.get("architecture_role") or "").startswith("korriban_door_")
    )
    assert frame_meshes
    assert {
        "korriban_door_frame_outer",
        "korriban_door_frame_middle",
        "korriban_door_frame_inner",
        "korriban_door_transition_reveal",
    } <= {str(mesh.metadata.get("architecture_role") or "") for mesh in frame_meshes}
    assert {"left", "right", "lintel", "threshold"} <= {
        str(mesh.metadata.get("door_frame_part") or "") for mesh in frame_meshes
    }
    assert all(
        len({mesh.vertices[index] for index in face}) == 3
        for mesh in frame_meshes
        for face in mesh.faces
    )
    # Stock tomb textures repeat in world metres across the deep jamb/reveal;
    # a 0..1 remap per part would be visible stretching.
    assert max(
        max(float(uv[0]), float(uv[1]))
        for mesh in frame_meshes
        for uv in mesh.uvs
    ) > 1.0


def test_t2909_korriban_stock_room_drag_uses_cursor_and_builds_second_reciprocal_portal() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_imported_mesh import build_imported_mesh_primitive_from_stock_model
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.map_studio_environment_kits import environment_kit_piece
    from src.core.modules.map_studio_stock_content_preview import load_stock_kotor_model
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Korriban stock-room snap proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grkorrlego", game="K1")
    controller.add_map_studio_building_room(
        points=((0.0, 0.0), (20.0, 0.0), (20.0, 14.0), (0.0, 14.0)),
        wall_height=3.9,
        style_id="architecture:k1_korriban_tombs",
    )
    hub_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m39aa_m39aa_16",
        position=(10.0, 14.0, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    hub = next(room for room in authored.rooms if room.normalised_resref() == hub_room)
    hub_piece = environment_kit_piece("k1_m39aa_m39aa_16")
    assert hub_piece is not None
    hub_yaw = math.radians(float(dict(hub.metadata)["environment_kit_rotation_degrees_z"]))
    cosine = math.cos(hub_yaw)
    sine = math.sin(hub_yaw)
    target_magnet = next(magnet for magnet in hub_piece.magnets if magnet.magnet_id == "wok_portal_011")
    cursor_position = (
        float(hub.position[0])
        + float(target_magnet.local_position[0]) * cosine
        - float(target_magnet.local_position[1]) * sine,
        float(hub.position[1])
        + float(target_magnet.local_position[0]) * sine
        + float(target_magnet.local_position[1]) * cosine,
        float(hub.position[2]) + float(target_magnet.local_position[2]),
    )

    preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m38aa_m38aa_05",
        position=cursor_position,
    )
    assert preview["magnet_snapped"] is True
    assert preview["target_is_authored_wall"] is False
    assert preview["target_room_resref"] == hub_room
    assert preview["target_magnet_id"] == "wok_portal_011"
    assert preview["cursor_distance"] == pytest.approx(0.0, abs=1.0e-7)

    bend_room = controller.add_authored_environment_kit_piece(
        piece_id="k1_m38aa_m38aa_05",
        position=cursor_position,
        resource_manager=resources,
    )
    connected = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = compile_authored_room_connection_walkmeshes(connected)
    assert build.ready is True, build.blocking_issues
    assert len(connected.rooms) == 3
    assert {room.normalised_resref() for room in connected.rooms} >= {hub_room, bend_room}
    assert len(build.portals) == 2
    assert max(portal.midpoint_gap for portal in build.portals) <= 1.0e-6
    assert len(connected.placements.doors) == 2
    assert {door.template_resref for door in connected.placements.doors} == {"gr_korrdoor"}

    # The room transform belongs to object/world space; vanilla diffuse UVs
    # remain in UV space and must survive the drag/snap/KMAP round trip exactly.
    source_model = load_stock_kotor_model(resources, "m38aa_05", "K1")
    assert source_model is not None
    source_primitive = build_imported_mesh_primitive_from_stock_model(
        source_model,
        room_resref="source_m38aa_05",
        source_model="m38aa_05",
        game="K1",
    )
    bend = next(room for room in connected.rooms if room.normalised_resref() == bend_room)
    assert len(bend.primitive.surfaces) == len(source_primitive.surfaces)
    assert tuple(
        (surface.name, surface.texture, tuple(surface.uvs))
        for surface in bend.primitive.surfaces
    ) == tuple(
        (surface.name, surface.texture, tuple(surface.uvs))
        for surface in source_primitive.surfaces
    )


def test_t2909_dressing_clip_preserves_channels_and_centers_wall_anchor() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
        extract_imported_mesh_room_bounds,
    )

    primitive = ImportedMeshRoomPrimitive(
        room_resref="retailroom",
        source_model="retailroom",
        game="K1",
        surfaces=(
            ImportedMeshSurface(
                name="Object10",
                texture="lhr_panl02",
                lightmap="retail_lm",
                vertices=(
                    (0.0, 2.0, 1.0),
                    (1.0, 2.0, 1.0),
                    (0.0, 2.0, 2.0),
                    (10.0, 2.0, 1.0),
                    (11.0, 2.0, 1.0),
                    (10.0, 2.0, 2.0),
                ),
                faces=((0, 1, 2), (3, 4, 5)),
                uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
                normals=((0.0, -1.0, 0.0),) * 6,
                uvs_lm=((0.0, 0.0),) * 6,
            ),
        ),
    )
    clipped = extract_imported_mesh_room_bounds(
        primitive,
        bounds=(-0.1, 1.9, 0.9, 1.1, 2.1, 2.1),
        room_resref="grdetail",
        surface_names=("object10",),
        anchor_mode="wall",
    )
    surface = clipped.surfaces[0]
    assert len(surface.faces) == 1
    assert len(surface.vertices) == len(surface.uvs) == len(surface.normals) == 3
    assert surface.lightmap == "" and surface.uvs_lm == ()
    assert min(vertex[0] for vertex in surface.vertices) == pytest.approx(-0.5)
    assert max(vertex[0] for vertex in surface.vertices) == pytest.approx(0.5)
    assert min(vertex[2] for vertex in surface.vertices) == pytest.approx(-0.5)
    assert max(vertex[2] for vertex in surface.vertices) == pytest.approx(0.5)
    assert clipped.wok is not None and clipped.wok.faces == []


def test_t2909_korriban_measured_dressing_previews_places_and_batch_deletes() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Korriban dressing proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))

    controller = ModuleEditorController()
    controller.new_project(name="grkorrdress", game="K1")
    base_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (42.0, 0.0), (42.0, 31.5), (0.0, 31.5)),
        wall_height=22.08,
        style_id="architecture:k1_korriban_tombs",
        architecture_archetype="monumental_tomb_hall",
    )
    specs = (
        ("k1_korriban_tombs_sarcophagus", (6.0, 6.0, 0.0), "", "m37aa", "m37aa_12"),
        ("k1_korriban_tombs_offering_stones", (13.0, 6.0, 0.0), "", "m37aa", "m37aa_12"),
        ("k1_korriban_tombs_floor_dais", (21.0, 15.75, 0.0), "", "m37aa", "m37aa_12"),
        ("k1_korriban_tombs_vault_pier", (0.2, 15.75, 5.0), base_room, "m37aa", "m37aa_12"),
        ("k1_korriban_tombs_vault_ring", (21.0, 15.75, 20.0), "", "m37aa", "m37aa_12"),
        ("k1_korriban_tombs_ritual_dais", (31.0, 7.0, 0.0), "", "m39aa", "m39aa_07"),
        ("k1_korriban_tombs_monument_pylon", (36.0, 22.0, 0.0), "", "m39aa", "m39aa_07"),
        ("k1_korriban_tombs_monument_rock", (9.0, 25.0, 0.0), "", "m39aa", "m39aa_07"),
    )
    placed: dict[str, str] = {}
    for piece_id, position, target_room, source_module, source_room in specs:
        assert controller.map_studio_environment_kit_preview_model(
            piece_id,
            resource_manager=resources,
        ) is not None
        placed[piece_id] = controller.add_authored_environment_kit_piece(
            piece_id=piece_id,
            position=position,
            target_room_resref=target_room,
            resource_manager=resources,
        )
        authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
        room = next(candidate for candidate in authored.rooms if candidate.normalised_resref() == placed[piece_id])
        primitive = room.primitive
        assert room.metadata["environment_kit_role"] == "dressing"
        assert room.metadata["environment_kit_source_module"] == source_module
        assert room.metadata["environment_kit_source_room"] == source_room
        assert primitive.surfaces
        assert all(surface.faces for surface in primitive.surfaces)
        assert all(len(surface.uvs) == len(surface.vertices) for surface in primitive.surfaces)
        assert all(not surface.lightmap and not surface.uvs_lm for surface in primitive.surfaces)
        assert primitive.wok is not None and not primitive.wok.faces
        assert primitive.metadata["visual_only"] is True

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == 1 + len(specs)
    assert len(set(placed.values())) == len(specs)
    wall_piece = next(
        room
        for room in authored.rooms
        if room.normalised_resref() == placed["k1_korriban_tombs_vault_pier"]
    )
    assert wall_piece.metadata["environment_kit_wall_aligned"] is True
    assert wall_piece.position[0] == pytest.approx(0.015)

    deleted_ids = (
        placed["k1_korriban_tombs_sarcophagus"],
        placed["k1_korriban_tombs_vault_pier"],
    )
    deleted, message = controller.delete_map_studio_rooms(deleted_ids)
    assert deleted, message
    after_delete = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert not ({room.normalised_resref() for room in after_delete.rooms} & set(deleted_ids))
    assert len(after_delete.rooms) == len(authored.rooms) - len(deleted_ids)

    assert controller.undo_map_studio_command() is not None
    restored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert {room.normalised_resref() for room in restored.rooms} >= set(deleted_ids)


def test_t2909_architecture_model_serializer_emits_labeled_obj_sequence() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_pascal_building import serialize_architecture_model_text

    floor = SimpleNamespace(
        name="main_floor",
        texture="lhr_flr01",
        texture_names=("lhr_flr01",),
        lightmap="",
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        faces=((0, 1, 2),),
        face_mats=(0,),
        normals=((0.0, 0.0, 1.0),) * 3,
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        uvs_lm=(),
        flags=0,
        render=True,
        children=(),
        world_transform=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    wall = SimpleNamespace(
        **{
            **floor.__dict__,
            "name": "bulkhead_wall",
            "texture": "lhr_wall01",
            "texture_names": ("lhr_wall01",),
            "vertices": ((0.0, 0.0, 0.0), (0.0, 0.0, 2.5), (2.0, 0.0, 0.0)),
            "normals": ((0.0, -1.0, 0.0),) * 3,
        }
    )
    root = SimpleNamespace(
        name="root",
        vertices=(),
        faces=(),
        flags=0,
        render=False,
        children=(floor, wall),
        controllers=(),
    )
    model = SimpleNamespace(root_node=root, animations=())

    sequence, summary = serialize_architecture_model_text(
        model,
        game="K1",
        module_resref="m01aa",
        room_resref="m01aa_test",
        profile="endar_spire",
    )

    assert "# ghostrigger-kotor-architecture-sequence/v1" in sequence
    assert "# semantic_role floor" in sequence
    assert "# semantic_role wall" in sequence
    assert "usemtl lhr_flr01" in sequence
    assert "usemtl lhr_wall01" in sequence
    assert "v 2.000000 0.000000 0.000000" in sequence
    assert "f 1/1/1 2/2/2 3/3/3" in sequence
    assert summary["surface_count"] == 2
    assert summary["triangle_count"] == 2
    assert summary["role_counts"] == {"floor": 1, "wall": 1}


def test_t2907_environment_kit_nearest_snap_aligns_compatible_edge_magnets() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        EnvironmentKitPiece,
        nearest_environment_kit_snap,
    )
    from src.core.modules.map_studio_environment_kits import _terrain_edge_magnets

    source = EnvironmentKitPiece(
        piece_id="source_cliff",
        collection_id="k1_test",
        label="Source cliff",
        game="K1",
        module_resref="m13aa",
        room_resref="m13aa_01",
        role="terrain",
        class_id="terrain:cliff",
        model_resref="m13aa_01",
        dimensions_m=(2.0, 2.0, 1.0),
        magnets=_terrain_edge_magnets((2.0, 2.0, 1.0)),
    )
    target = EnvironmentKitPiece(
        piece_id="target_cliff",
        collection_id="k1_test",
        label="Target cliff",
        game="K1",
        module_resref="m13aa",
        room_resref="m13aa_02",
        role="terrain",
        class_id="terrain:cliff",
        model_resref="m13aa_02",
        dimensions_m=(2.0, 2.0, 1.0),
        magnets=_terrain_edge_magnets((2.0, 2.0, 1.0)),
    )

    snap = nearest_environment_kit_snap(
        source,
        proposed_position=(0.15, 0.05, 0.0),
        proposed_yaw=0.0,
        source_scale=1.0,
        targets=((target, (2.0, 0.0, 0.0), 0.0, 1.0, "grtk0001"),),
        max_distance=0.5,
    )

    assert snap is not None
    assert snap.source_magnet_id == "east"
    assert snap.target_magnet_id == "west"
    assert snap.target_piece_id == "target_cliff"
    assert snap.target_room_resref == "grtk0001"
    assert math.isclose(snap.position[0], 0.0, abs_tol=1.0e-6)
    assert math.isclose(snap.position[1], 0.0, abs_tol=1.0e-6)
    assert math.isclose(snap.yaw_radians % (math.pi * 2.0), 0.0, abs_tol=1.0e-6)


def test_t2907_environment_kit_classifies_room_doorway_topology() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        EnvironmentKitMagnet,
        _doorway_archetype,
        _yaw_quaternion,
    )

    def doorway(name: str, yaw: float) -> EnvironmentKitMagnet:
        return EnvironmentKitMagnet(
            magnet_id=name,
            kind="doorway",
            magnet_class="doorway",
            local_position=(0.0, 0.0, 0.0),
            local_orientation=_yaw_quaternion(yaw),
            source="test",
        )

    assert _doorway_archetype(()) == "chamber"
    assert _doorway_archetype((doorway("end", 0.0),)) == "dead_end"
    assert _doorway_archetype((doorway("a", 0.0), doorway("b", math.pi))) == "straight"
    assert _doorway_archetype((doorway("a", 0.0), doorway("b", math.pi * 0.5))) == "corner"
    assert _doorway_archetype(tuple(doorway(str(index), index * math.pi * 0.5) for index in range(4))) == "cross"


def test_t2907_environment_piece_browser_rows_and_drag_payload_are_typed() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        ENVIRONMENT_KIT_PAYLOAD_SCHEMA,
        environment_kit_drag_payload,
        environment_kit_piece_rows,
    )

    rows = environment_kit_piece_rows(game="K1")
    assert len(rows) >= 1_000
    assert all(row["game"] == "K1" for row in rows)
    assert all(row["role"] in {"room_tile", "exterior_tile", "dressing"} for row in rows)
    assert all(":" in row["class_id"] for row in rows)
    assert all(row["collection_id"] and row["collection_label"] for row in rows)

    room_row = next(row for row in rows if row["role"] in {"room_tile", "exterior_tile"})
    payload = environment_kit_drag_payload(room_row["piece_id"], rotation_degrees_z=45.0, scale=1.25)
    assert payload["schema"] == ENVIRONMENT_KIT_PAYLOAD_SCHEMA
    assert payload["piece_id"] == room_row["piece_id"]
    assert payload["snap_to_magnets"] is True
    assert payload["rotation_degrees_z"] == 45.0
    assert payload["scale"] == 1.25


def test_t2907_terrain_kit_transform_keeps_render_mesh_and_wok_aligned() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.map_studio_terrain_kit import transform_terrain_kit_primitive
    from src.core.modules.module_format import WOKData, WOKFace

    primitive = ImportedMeshRoomPrimitive(
        room_resref="terrain_piece",
        surfaces=(
            ImportedMeshSurface(
                name="terrain",
                texture="ground",
                vertices=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)),
                faces=((0, 1, 2),),
                normals=((1.0, 0.0, 0.0),) * 3,
            ),
        ),
        wok=WOKData(
            name="terrain_piece",
            verts=[(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)],
            faces=[WOKFace(0, 1, 2, 4)],
            raw=b"stale stock bytes",
            relative_hook1=(1.0, 0.0, 0.0),
        ),
    )

    transformed = transform_terrain_kit_primitive(primitive, rotation_degrees_z=90.0, scale=2.0)

    assert transformed.surfaces[0].vertices[0] == pytest.approx((0.0, 2.0, 0.0))
    assert transformed.wok is not None
    assert transformed.wok.verts[0] == pytest.approx((0.0, 2.0, 0.0))
    assert transformed.wok.relative_hook1 == pytest.approx((0.0, 2.0, 0.0))
    assert transformed.wok.raw is None


def test_t2907_controller_places_environment_piece_with_unique_room_and_provenance(monkeypatch) -> None:
    _install_native_payload_paths()

    from src.core.modules import module_editor_controller as controller_module
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.map_studio_environment_kits import environment_kit_piece_rows
    from src.core.modules.module_editor_controller import ModuleEditorController
    from src.core.modules.module_format import WOKData, WOKFace

    source = environment_kit_piece_rows(game="K1")[0]
    primitive = ImportedMeshRoomPrimitive(
        room_resref="source_room",
        source_model=str(source["room_resref"]),
        game="K1",
        surfaces=(
            ImportedMeshSurface(
                name="floor",
                texture="metal_floor",
                lightmap="old_lightmap",
                uvs_lm=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
                vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
                faces=((0, 1, 2),),
                normals=((0.0, 0.0, 1.0),) * 3,
            ),
        ),
        wok=WOKData(
            name="source_room",
            verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
            faces=[WOKFace(0, 1, 2, 4)],
            raw=b"source wok",
        ),
    )
    monkeypatch.setattr(controller_module, "load_stock_kotor_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        controller_module,
        "build_imported_mesh_primitive_from_stock_model",
        lambda *_args, **_kwargs: primitive,
    )

    controller = ModuleEditorController()
    controller.new_project(name="kit_test", game="K1")
    monkeypatch.setattr(controller, "_stock_room_wok_bytes", lambda *_args, **_kwargs: None)
    room_resref = controller.add_authored_environment_kit_piece(
        piece_id=str(source["piece_id"]),
        position=(3.0, 4.0, 0.5),
        rotation_degrees_z=90.0,
        scale=2.0,
        resource_manager=object(),
    )

    assert room_resref == "grkit0001"
    payload = controller.project.extra_sections["authored_module"]
    room = payload["rooms"][0]
    assert room["room_resref"] == "grkit0001"
    assert room["position"] == [3.0, 4.0, 0.5]
    assert room["metadata"]["environment_kit_piece_id"] == source["piece_id"]
    assert room["metadata"]["environment_kit_collection_id"] == source["collection_id"]
    assert room["metadata"]["environment_kit_rotation_degrees_z"] == 90.0
    assert room["metadata"]["environment_kit_scale"] == 2.0
    assert room["primitive"]["surfaces"][0]["lightmap"] == ""
    assert "raw" not in room["primitive"]["wok"]


def test_t2907_maya_multi_move_includes_player_start_as_one_authored_object() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="selection_proof", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="grselect",
    )
    entry_before = controller.authored_module_entry_point()
    controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="Bench A",
        position=(1.0, 2.0, 0.0),
    )
    controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="Bench B",
        position=(4.0, 5.0, 0.0),
    )
    rows_before = {row.placement_id: row for row in controller.authored_gameplay_placements()}
    ids = tuple(rows_before)

    moved = controller.translate_authored_gameplay_placements(
        ("entry_point", *ids),
        world_delta=(2.0, -1.0, 0.5),
    )

    assert moved == ("entry_point", *ids)
    entry_after = controller.authored_module_entry_point()
    assert entry_after.position == tuple(
        entry_before.position[index] + (2.0, -1.0, 0.5)[index] for index in range(3)
    )
    rows_after = {row.placement_id: row for row in controller.authored_gameplay_placements()}
    for placement_id in ids:
        assert rows_after[placement_id].position == tuple(
            rows_before[placement_id].position[index] + (2.0, -1.0, 0.5)[index]
            for index in range(3)
        )
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.gameplay.move_placements"


def test_t2907_selected_authored_objects_delete_in_one_undo_transaction() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="delete_proof", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="elevation_test_room",
        module_root="grdelete",
    )
    rows_before = controller.authored_room_primitive_transforms()
    assert len(rows_before) >= 2
    removable = [row for row in rows_before if "floor" not in row.primitive_name.lower()]
    selected = tuple((row.room_resref, row.primitive_name) for row in removable[:2])
    assert len(selected) == 2

    removed = controller.remove_authored_room_primitives(selected)

    assert removed == selected
    remaining = {
        (row.room_resref, row.primitive_name)
        for row in controller.authored_room_primitive_transforms()
    }
    assert not remaining.intersection(selected)
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.primitive.remove_many"


def test_t2907_mixed_kit_player_and_placeable_selection_moves_and_deletes_atomically() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="mixed_selection", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="composition_starter_room",
        module_root="grmixed",
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        room_resref="grmixed_room01",
        primitive_name="terrain_rock",
        translation=(1.0, 2.0, 0.0),
    )
    controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="Bench",
        position=(4.0, 5.0, 0.0),
    )
    primitive = ("grmixed_room01", "terrain_rock")
    entry_before = controller.authored_module_entry_point()
    placement_before = next(row for row in controller.authored_gameplay_placements() if row.tag == "Bench")
    placement_id = placement_before.placement_id
    controller.command_history.clear()

    moved_primitives, moved_placements = controller.translate_map_studio_scene_objects(
        primitive_selections=(primitive,),
        placement_ids=("entry_point", placement_id),
        world_delta=(2.0, -1.0, 0.5),
    )

    assert moved_primitives == (primitive,)
    assert moved_placements == ("entry_point", placement_id)
    primitive_after = next(
        row for row in controller.authored_room_primitive_transforms() if row.primitive_name == "terrain_rock"
    )
    assert primitive_after.translation == (3.0, 1.0, 0.5)
    assert controller.authored_module_entry_point().position == tuple(
        entry_before.position[index] + (2.0, -1.0, 0.5)[index] for index in range(3)
    )
    placement_after = next(row for row in controller.authored_gameplay_placements() if row.placement_id == placement_id)
    assert placement_after.position == tuple(
        placement_before.position[index] + (2.0, -1.0, 0.5)[index] for index in range(3)
    )
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.scene.move_objects"
    controller.undo_map_studio_command()

    removed_primitives, removed_placements = controller.remove_map_studio_scene_objects(
        primitive_selections=(primitive,),
        placement_ids=("entry_point", placement_id),
    )

    assert removed_primitives == (primitive,)
    assert removed_placements == ("entry_point", placement_id)
    assert not any(row.primitive_name == "terrain_rock" for row in controller.authored_room_primitive_transforms())
    assert controller.authored_module_entry_point_preview_row() is None
    assert not any(row.placement_id == placement_id for row in controller.authored_gameplay_placements())
    assert controller.command_history.undo_stack[-1].action_key == "map_studio.scene.remove_objects"
    controller.undo_map_studio_command()
    assert any(row.primitive_name == "terrain_rock" for row in controller.authored_room_primitive_transforms())
    assert controller.authored_module_entry_point_preview_row() is not None
    assert any(row.placement_id == placement_id for row in controller.authored_gameplay_placements())


def test_t2909_complete_authored_rooms_move_and_delete_as_scene_objects() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="roomselect", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="composition_starter_room",
        module_root="grrooms",
    )
    room_resref = controller.authored_room_resrefs()[0]
    before = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"]).rooms[0].position

    moved_primitives, moved_objects = controller.translate_map_studio_scene_objects(
        room_resrefs=(room_resref,),
        world_delta=(2.5, -1.0, 0.25),
    )
    assert moved_primitives == ()
    assert moved_objects == (f"authored_room:{room_resref}",)
    moved_room = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"]).rooms[0]
    assert moved_room.position == tuple(before[index] + (2.5, -1.0, 0.25)[index] for index in range(3))

    controller.undo_map_studio_command()
    removed_primitives, removed_objects = controller.remove_map_studio_scene_objects(room_resrefs=(room_resref,))
    assert removed_primitives == ()
    assert removed_objects == (f"authored_room:{room_resref}",)
    assert controller.authored_room_resrefs() == ()
    controller.undo_map_studio_command()
    assert controller.authored_room_resrefs() == (room_resref,)


def test_t2909_whole_room_move_keeps_its_working_door_attached() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grroomdoor", game="K1")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (8.0, 0.0), (8.0, 6.0), (0.0, 6.0)),
        wall_height=3.655,
        style_id="architecture:k1_endar_spire",
    )
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=1.25,
        height=2.2,
        bottom=0.0,
    )
    before = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    door_id = before.rooms[0].primitive.openings[0].metadata["door_placement_id"]
    door_position = before.placements.doors[0].position

    _primitives, moved = controller.translate_map_studio_scene_objects(
        room_resrefs=(room_resref,),
        world_delta=(2.0, -1.0, 0.25),
    )

    after = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert moved == (door_id, f"authored_room:{room_resref}")
    assert after.rooms[0].position == (2.0, -1.0, 0.25)
    assert after.placements.doors[0].position == tuple(
        float(door_position[index]) + (2.0, -1.0, 0.25)[index] for index in range(3)
    )


def test_t2909_telos_citadel_style_exposes_measured_contours_and_repeat_safe_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grtelosstyle", game="K2")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    style = styles["architecture:k2_telos_citadel"]

    archetypes = {row["archetype_id"]: row for row in style["architecture_archetypes"]}
    assert style["architecture_profile"] == "telos_citadel"
    assert style["recommended_door_width_m"] == pytest.approx(3.48)
    assert style["recommended_door_height_m"] == pytest.approx(3.029)
    assert set(archetypes) == {"residential", "civic", "concourse"}
    assert archetypes["residential"]["shell_profile"] == "telos_citadel_residential"
    assert archetypes["residential"]["recommended_wall_height_m"] == pytest.approx(3.985)
    assert archetypes["civic"]["shell_profile"] == "telos_citadel_civic"
    assert archetypes["civic"]["recommended_wall_height_m"] == pytest.approx(5.995)
    assert archetypes["concourse"]["shell_profile"] == "telos_citadel_concourse"
    assert archetypes["concourse"]["recommended_wall_height_m"] == pytest.approx(6.739)

    room_resrefs = []
    for index, archetype_id in enumerate(("residential", "civic", "concourse")):
        height = float(archetypes[archetype_id]["recommended_wall_height_m"])
        x0 = float(index * 18)
        room_resrefs.append(
            controller.add_map_studio_building_room(
                points=((x0, 0.0), (x0 + 12.0, 0.0), (x0 + 12.0, 8.0), (x0, 8.0)),
                wall_height=height,
                style_id="architecture:k2_telos_citadel",
                architecture_archetype=archetype_id,
            )
        )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    expected_profiles = {
        room_resrefs[0]: "telos_citadel_residential",
        room_resrefs[1]: "telos_citadel_civic",
        room_resrefs[2]: "telos_citadel_concourse",
    }
    required_roles = {
        "telos_citadel_residential": {"citadel_canted_ceiling_shoulder", "citadel_recessed_ceiling_transition"},
        "telos_citadel_civic": {"citadel_civic_canted_crown", "citadel_civic_ceiling_coffer"},
        "telos_citadel_concourse": {"citadel_concourse_upper_return", "citadel_concourse_ceiling_coffer"},
    }
    for room in authored.rooms:
        geometry = compile_floor_plan_room_geometry(room.primitive)
        profile = expected_profiles[room.normalised_resref()]
        roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
        assert geometry.metadata["architecture_shell_profile"] == profile
        assert required_roles[profile] <= roles
        assert geometry.room_mesh.faces
        assert geometry.wok.faces
        assert all(len(mesh.uvs) == len(mesh.vertices) for mesh in geometry.helper_meshes)
        assert {"tel_fl01", "tel_fl05", "tel_lt02", "tel_tr04", "tel_wl03"} <= {
            mesh.texture for mesh in geometry.helper_meshes
        }


def test_t2909_telos_citadel_browser_separates_props_and_unifies_vanilla_rooms() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        environment_kit_collection_rows,
        environment_kit_piece_rows,
    )

    collections = tuple(
        row
        for row in environment_kit_collection_rows(game="K2")
        if row["building_style_id"] == "architecture:k2_telos_citadel"
    )
    collection_ids = {row["collection_id"] for row in collections}
    assert {
        "k2_201tel",
        "k2_202tel",
        "k2_203tel",
        "k2_204tel",
        "k2_207tel",
        "k2_220tel",
        "k2_221tel",
        "k2_222tel",
        "k2_telos_citadel_dressing",
    } <= collection_ids

    rows = tuple(
        row
        for row in environment_kit_piece_rows(game="K2")
        if row["building_style_id"] == "architecture:k2_telos_citadel"
    )
    vanilla_rooms = tuple(row for row in rows if row["role"] in {"room_tile", "exterior_tile"})
    dressing = tuple(row for row in rows if row["collection_id"] == "k2_telos_citadel_dressing")
    assert len(vanilla_rooms) >= 90
    assert len(dressing) == 9
    assert all(row["role"] == "dressing" for row in dressing)
    assert all(str(row["class_id"]).startswith("dressing:") for row in dressing)
    assert all(row["anchor_mode"] in {"floor", "wall"} for row in dressing)
    assert {
        "k2_telos_citadel_directory_wide",
        "k2_telos_citadel_wall_monitor",
        "k2_telos_citadel_corridor_bench",
        "k2_telos_citadel_doorway_pier",
        "k2_telos_citadel_cantina_terminal",
        "k2_telos_citadel_civic_light_band",
    } <= {row["piece_id"] for row in dressing}
    assert any(row["magnet_count"] > 0 for row in vanilla_rooms)


def test_t2909_telos_citadel_door_uses_stock_tel14_and_solid_reveal() -> None:
    _install_native_payload_paths()

    from pykotor.resource.generics.utd import read_utd
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.map_studio_pascal_building import pascal_architecture_runtime_resources
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grteldoor", game="K2")
    room_resref = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)),
        wall_height=3.985,
        style_id="architecture:k2_telos_citadel",
        architecture_archetype="residential",
    )
    controller.set_map_studio_building_opening(
        room_resref=room_resref,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=2.0,
        height=2.2,
        bottom=0.0,
    )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    room = authored.rooms[0]
    opening = room.primitive.openings[0]
    assert opening.width == pytest.approx(3.48)
    assert opening.height == pytest.approx(3.029)
    assert opening.metadata["door_model_resref"] == "dor_tel14"
    assert opening.metadata["door_appearance_id"] == 117
    assert opening.metadata["door_outer_width_m"] == pytest.approx(3.92)
    assert opening.metadata["door_outer_height_m"] == pytest.approx(3.31)
    assert len(authored.placements.doors) == 1
    assert authored.placements.doors[0].template_resref == "gr_teldoor"

    geometry = compile_floor_plan_room_geometry(room.primitive)
    roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
    assert {"telos_citadel_door_frame", "telos_door_light"} <= roles
    reveal_parts = {
        str(mesh.metadata.get("door_frame_part") or "")
        for mesh in geometry.helper_meshes
        if mesh.metadata.get("sealed_transition_reveal")
    }
    assert {"left", "right", "lintel", "threshold"} <= reveal_parts

    resources = pascal_architecture_runtime_resources(authored)
    door_bytes = next(data for resref, restype, data in resources if (resref, restype) == ("gr_teldoor", "utd"))
    door = read_utd(door_bytes)
    assert door.appearance_id == 117
    assert door.static is False
    assert door.locked is False


def test_t2909_telos_citadel_individual_prop_recipes_extract_real_uv_meshes() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.map_studio_environment_kits import environment_kit_piece_rows
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K2 retail corpus is required for the Telos dressing proof.")
    resources = ResourceManager()
    assert resources.set_k2_dir(str(game_dir))

    rows = environment_kit_piece_rows(
        game="K2",
        collection_id="k2_telos_citadel_dressing",
    )
    assert len(rows) == 9
    controller = ModuleEditorController()
    controller.new_project(name="grtelprops", game="K2")
    placed = []
    for index, row in enumerate(rows):
        assert controller.map_studio_environment_kit_preview_model(
            row["piece_id"],
            resource_manager=resources,
        ) is not None
        placed.append(
            controller.add_authored_environment_kit_piece(
                piece_id=row["piece_id"],
                position=(float(index * 12), 0.0, 0.0),
                resource_manager=resources,
            )
        )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    placed_rooms = tuple(room for room in authored.rooms if room.normalised_resref() in set(placed))
    assert len(placed_rooms) == 9
    for room in placed_rooms:
        primitive = room.primitive
        assert primitive.surfaces
        assert all(surface.faces for surface in primitive.surfaces)
        assert all(len(surface.uvs) == len(surface.vertices) for surface in primitive.surfaces)
        assert primitive.wok is not None and not primitive.wok.faces
        assert primitive.metadata["visual_only"] is True


def test_t2909_onderon_styles_expose_distinct_area_contours_and_tiled_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="gronderon", game="K2")
    styles = {row["style_id"]: row for row in controller.available_map_studio_building_styles()}
    expected = {
        "architecture:k2_onderon_city": (
            "onderon_city",
            "exterior",
            {"merchant_courtyard", "western_square", "spaceport"},
        ),
        "architecture:k2_onderon_cantina": (
            "onderon_cantina",
            "interior",
            {"cantina_gallery", "cantina_lounge"},
        ),
        "architecture:k2_onderon_sky_ramp": (
            "onderon_sky_ramp",
            "exterior",
            {"ramp_court", "tower_terrace"},
        ),
        "architecture:k2_onderon_palace": (
            "onderon_palace",
            "interior",
            {"palace_gallery", "state_hall", "museum"},
        ),
    }
    for style_id, (profile, kind, archetype_ids) in expected.items():
        row = styles[style_id]
        assert row["architecture_profile"] == profile
        assert row["environment_kind"] == kind
        assert {value["archetype_id"] for value in row["architecture_archetypes"]} == archetype_ids
        assert len(tuple(row["evidence_rooms"])) >= 5

    room_resrefs = []
    cases = (
        ("architecture:k2_onderon_city", "merchant_courtyard", 8.50, False),
        ("architecture:k2_onderon_cantina", "cantina_gallery", 7.70, True),
        ("architecture:k2_onderon_sky_ramp", "ramp_court", 12.70, False),
        ("architecture:k2_onderon_palace", "palace_gallery", 6.00, True),
    )
    for index, (style_id, archetype, height, ceiling) in enumerate(cases):
        x0 = float(index * 24)
        room_resrefs.append(
            controller.add_map_studio_building_room(
                points=((x0, 0.0), (x0 + 18.0, 0.0), (x0 + 18.0, 14.0), (x0, 14.0)),
                wall_height=height,
                style_id=style_id,
                architecture_archetype=archetype,
                include_ceiling=ceiling,
                building_kind="interior" if ceiling else "exterior",
            )
        )

    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    expected_roles = {
        "onderon_city": {"iziz_battered_stone_dado", "iziz_stepped_parapet_crown"},
        "onderon_cantina": {"cantina_recessed_booth_field", "cantina_ceiling_coffer"},
        "onderon_sky_ramp": {"sky_ramp_fortified_base", "sky_ramp_stepped_parapet"},
        "onderon_palace": {"palace_recessed_relief_panel", "palace_coffered_vault"},
    }
    for room in authored.rooms:
        geometry = compile_floor_plan_room_geometry(room.primitive)
        profile = str(room.primitive.metadata["architecture_profile"])
        roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
        assert expected_roles[profile] <= roles
        assert "onderon_beveled_relief_bay" in roles
        assert geometry.room_mesh.faces
        assert geometry.wok.faces
        assert all(len(mesh.uvs) == len(mesh.vertices) for mesh in geometry.helper_meshes)
        assert all(
            max((abs(value) for uv in mesh.uvs for value in uv), default=0.0) < 10000.0
            for mesh in geometry.helper_meshes
        )


def test_t2909_onderon_door_families_generate_solid_reveals_and_runtime_utds() -> None:
    _install_native_payload_paths()

    from pykotor.resource.generics.utd import read_utd
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_floorplan import compile_floor_plan_room_geometry
    from src.core.modules.map_studio_pascal_building import pascal_architecture_runtime_resources
    from src.core.modules.module_editor_controller import ModuleEditorController

    cases = (
        ("architecture:k2_onderon_city", "merchant_courtyard", 8.50, "dor_ond06", 108, "gr_onddoor"),
        ("architecture:k2_onderon_cantina", "cantina_gallery", 7.70, "dor_ond01", 95, "gr_ondcdoor"),
        ("architecture:k2_onderon_sky_ramp", "ramp_court", 12.70, "dor_ond02", 96, "gr_ondsdoor"),
        ("architecture:k2_onderon_palace", "palace_gallery", 6.00, "dor_ond03", 105, "gr_ondpdoor"),
    )
    for index, (style_id, archetype, height, model, appearance, template) in enumerate(cases):
        controller = ModuleEditorController()
        controller.new_project(name=f"grondoor{index}", game="K2")
        room_resref = controller.add_map_studio_building_room(
            points=((0.0, 0.0), (16.0, 0.0), (16.0, 12.0), (0.0, 12.0)),
            wall_height=height,
            style_id=style_id,
            architecture_archetype=archetype,
            include_ceiling="city" not in style_id and "sky_ramp" not in style_id,
        )
        controller.set_map_studio_building_opening(
            room_resref=room_resref,
            edge_index=2,
            opening_kind="door",
            center_fraction=0.5,
            width=2.0,
            height=2.2,
            bottom=0.0,
        )
        authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
        opening = authored.rooms[0].primitive.openings[0]
        assert opening.metadata["door_model_resref"] == model
        assert opening.metadata["door_appearance_id"] == appearance
        assert authored.placements.doors[0].template_resref == template
        geometry = compile_floor_plan_room_geometry(authored.rooms[0].primitive)
        reveal_parts = {
            str(mesh.metadata.get("door_frame_part") or "")
            for mesh in geometry.helper_meshes
            if mesh.metadata.get("sealed_transition_reveal")
        }
        assert {"left", "right", "lintel"} <= reveal_parts
        assert "threshold" not in reveal_parts
        assert opening.height == pytest.approx(2.989 if model == "dor_ond06" else 2.925)
        assert opening.metadata["door_outer_height_m"] == pytest.approx(
            2.989 if model == "dor_ond06" else 2.925
        )
        roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
        assert "onderon_door_portal" in roles
        assert "onderon_door_structural_return" in roles
        structural_returns = [
            mesh
            for mesh in geometry.helper_meshes
            if mesh.metadata.get("architecture_role") == "onderon_door_structural_return"
        ]
        assert structural_returns
        assert all(mesh.metadata.get("closed_geometry") for mesh in structural_returns)
        assert all(float(mesh.metadata.get("door_wall_depth_m") or 0.0) >= 0.98 for mesh in structural_returns)
        resources = pascal_architecture_runtime_resources(authored)
        payload = next(data for resref, restype, data in resources if (resref, restype) == (template, "utd"))
        assert read_utd(payload).appearance_id == appearance


def test_t2909_established_kits_expose_purposeful_archetypes_with_clean_uv_topology() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.map_studio_pascal_building import available_pascal_building_styles

    styles = {style.style_id: style for style in available_pascal_building_styles(game="K1")}
    expected = {
        "architecture:k1_endar_spire": {
            "corridor": "endar_corridor",
            "command_deck": "endar_command_deck",
            "crew_quarters": "endar_crew_quarters",
        },
        "architecture:k1_taris_apartments": {
            "apartment": "taris_apartment",
            "corridor": "taris_residential_corridor",
            "living_suite": "taris_living_suite",
        },
        "architecture:k1_shadowlands": {
            "clearing": "shadowlands_root_wall",
            "root_passage": "shadowlands_root_passage",
            "ancient_grove": "shadowlands_ancient_grove",
        },
        "architecture:k1_korriban_caves": {
            "passage": "korriban_cave",
            "grotto": "korriban_cave_grotto",
            "nest": "korriban_cave_nest",
        },
    }
    required_roles = {
        "endar_command_deck": {"command_console_plinth", "command_deck_pylon"},
        "endar_crew_quarters": {"quarters_service_recess", "quarters_compartment_rib"},
        "taris_residential_corridor": {"taris_corridor_panel_field", "taris_corridor_door_station"},
        "taris_living_suite": {"taris_suite_service_recess", "taris_suite_divider"},
        "shadowlands_root_passage": {"root_passage_steep_bank", "root_passage_crown"},
        "shadowlands_ancient_grove": {"grove_broad_mound", "grove_root_recess"},
        "korriban_cave_grotto": {"grotto_deep_rock_pocket", "grotto_rock_shelf"},
        "korriban_cave_nest": {"nest_eroded_alcove", "nest_pointed_shoulders"},
    }
    for style_id, archetype_contract in expected.items():
        style = styles[style_id]
        archetypes = {archetype.archetype_id: archetype for archetype in style.architecture_archetypes}
        assert {key: value.shell_profile for key, value in archetypes.items()} == archetype_contract
        for archetype in archetypes.values():
            size = 12.0 if archetype.recommended_wall_height_m >= 8.0 else 8.0
            geometry = compile_floor_plan_room_geometry(
                FloorPlanRoomPrimitive(
                    room_resref="grquality",
                    points=((0.0, 0.0), (size, 0.0), (size, size), (0.0, size)),
                    wall_height=archetype.recommended_wall_height_m,
                    material=PrimitiveMaterial(texture=style.floor_texture),
                    wall_material=PrimitiveMaterial(texture=style.wall_texture),
                    ceiling_material=PrimitiveMaterial(texture=style.ceiling_texture),
                    include_ceiling=style.architecture_profile != "shadowlands",
                    metadata={
                        "architecture_profile": style.architecture_profile,
                        "architecture_shell_profile": archetype.shell_profile,
                        "architecture_accent_textures": style.accent_textures,
                        "architecture_evidence_rooms": archetype.evidence_rooms,
                    },
                )
            )
            assert geometry.metadata["architecture_shell_profile"] == archetype.shell_profile
            roles = {str(mesh.metadata.get("architecture_role") or "") for mesh in geometry.helper_meshes}
            assert required_roles.get(archetype.shell_profile, set()) <= roles
            assert all(len(mesh.uvs) == len(mesh.vertices) for mesh in geometry.helper_meshes)
            for mesh in geometry.helper_meshes:
                for a, b, c in mesh.faces:
                    pa, pb, pc = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
                    ab = tuple(pb[index] - pa[index] for index in range(3))
                    ac = tuple(pc[index] - pa[index] for index in range(3))
                    cross = (
                        ab[1] * ac[2] - ab[2] * ac[1],
                        ab[2] * ac[0] - ab[0] * ac[2],
                        ab[0] * ac[1] - ab[1] * ac[0],
                    )
                    assert sum(component * component for component in cross) > 1.0e-14, mesh.name


def test_t2909_established_door_families_generate_closed_structural_returns() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRoomPrimitive,
        FloorPlanWallOpening,
        compile_floor_plan_room_geometry,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial
    from src.core.modules.map_studio_pascal_building import (
        available_pascal_building_styles,
        pascal_architecture_door_spec,
    )

    styles = {style.style_id: style for style in available_pascal_building_styles(game="K1")}
    cases = (
        ("architecture:k1_endar_spire", "corridor", "endar_door_structural_return", "dor_lhr01"),
        ("architecture:k1_taris_apartments", "apartment", "taris_door_structural_return", "dor_lts02"),
        ("architecture:k1_korriban_tombs", "corridor", "korriban_door_structural_return", "dor_lko04"),
    )
    for style_id, archetype_id, structural_role, model_resref in cases:
        style = styles[style_id]
        archetype = next(value for value in style.architecture_archetypes if value.archetype_id == archetype_id)
        spec = pascal_architecture_door_spec("K1", style.architecture_profile)
        assert spec is not None
        opening = FloorPlanWallOpening(
            name="quality_door",
            edge_index=2,
            center_fraction=0.5,
            width=float(spec["opening_width_m"]),
            height=float(spec["opening_height_m"]),
            metadata={
                "door_model_resref": model_resref,
                "door_outer_width_m": float(spec["frame_width_m"]),
                "door_outer_height_m": float(spec["frame_height_m"]),
            },
        )
        geometry = compile_floor_plan_room_geometry(
            FloorPlanRoomPrimitive(
                room_resref="grqualitydoor",
                points=((0.0, 0.0), (14.0, 0.0), (14.0, 10.0), (0.0, 10.0)),
                wall_height=archetype.recommended_wall_height_m,
                material=PrimitiveMaterial(texture=style.floor_texture),
                wall_material=PrimitiveMaterial(texture=style.wall_texture),
                ceiling_material=PrimitiveMaterial(texture=style.ceiling_texture),
                openings=(opening,),
                metadata={
                    "architecture_profile": style.architecture_profile,
                    "architecture_shell_profile": archetype.shell_profile,
                    "architecture_accent_textures": style.accent_textures,
                },
            )
        )
        structural = tuple(
            mesh
            for mesh in geometry.helper_meshes
            if mesh.metadata.get("architecture_role") == structural_role
        )
        assert len(structural) == 18
        assert all(mesh.metadata.get("closed_geometry") for mesh in structural)
        assert all(float(mesh.metadata.get("door_wall_depth_m") or 0.0) >= 0.52 for mesh in structural)
        reveal_parts = {
            str(mesh.metadata.get("door_frame_part") or "")
            for mesh in geometry.helper_meshes
            if mesh.metadata.get("sealed_transition_reveal")
        }
        assert reveal_parts >= {"left", "right", "lintel"}
        assert "threshold" not in reveal_parts
        if style_id == "architecture:k1_endar_spire":
            assert float(spec["frame_width_m"]) == pytest.approx(8.40)
            assert float(spec["frame_height_m"]) == pytest.approx(3.60)
            assert {
                "upper_left_diagonal",
                "upper_right_diagonal",
                "lower_left_diagonal",
                "lower_right_diagonal",
            } <= reveal_parts
            bulkhead = tuple(
                mesh
                for mesh in geometry.helper_meshes
                if mesh.metadata.get("architecture_role") == "endar_door_bulkhead_backing"
            )
            assert bulkhead
            assert {mesh.texture for mesh in bulkhead} == {"lhr_wall01"}
            assert all(mesh.metadata.get("bulkhead_surface_family") == "lhr_wall01" for mesh in bulkhead)
            assert all(mesh.metadata.get("visible_aperture_profile") == "chamfered_octagon" for mesh in bulkhead)


def test_t2909_build_style_list_contains_only_verified_pascal_kits() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_pascal_building import available_pascal_building_styles

    k1 = available_pascal_building_styles("K1")
    k2 = available_pascal_building_styles("K2")
    assert {style.style_id for style in k1} == {
        "plcaa_graybox",
        "architecture:k1_endar_spire",
        "architecture:k1_taris_apartments",
        "architecture:k1_shadowlands",
        "architecture:k1_korriban_tombs",
        "architecture:k1_korriban_caves",
    }
    assert {style.style_id for style in k2} == {
        "plcaa_graybox",
        "architecture:k2_harbinger",
        "architecture:k2_telos_citadel",
        "architecture:k2_onderon_city",
        "architecture:k2_onderon_cantina",
        "architecture:k2_onderon_sky_ramp",
        "architecture:k2_onderon_palace",
        "architecture:k2_korriban_tombs",
        "architecture:k2_korriban_caves",
    }
    assert not any(style.style_id.startswith(("kit:", "vanilla_")) for style in (*k1, *k2))


def test_t2909_reviewed_socketless_room_uses_generated_connector_only() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        environment_kit_drag_payload,
        environment_kit_piece,
        environment_kit_piece_rows,
    )

    generated = environment_kit_piece("k1_m23aa_m23aa_04a")
    assert generated is not None
    assert generated.role in {"room_tile", "exterior_tile"}
    assert generated.magnets == ()
    assert generated.placement_quality == "generated_connector"
    generated_payload = environment_kit_drag_payload(generated)
    assert generated_payload["generated_connector"] is True

    unreviewed = environment_kit_piece("k1_m24aa_m24aa_04a")
    assert unreviewed is not None
    assert unreviewed.magnets == ()
    assert unreviewed.placement_quality == "needs_review"
    with pytest.raises(ValueError, match="no verified retail doorway socket"):
        environment_kit_drag_payload(unreviewed)

    rows = {row["piece_id"]: row for row in environment_kit_piece_rows(game="K1")}
    assert rows["k1_m23aa_m23aa_04a"]["placement_ready"] is True
    assert rows["k1_m24aa_m24aa_04a"]["placement_ready"] is False
    assert rows["k1_m24aa_m24aa_02a"]["placement_ready"] is True
    assert rows["k1_m24aa_m24aa_02a"]["magnet_count"] == 1


def test_t2909_taris_and_shadowlands_browsers_include_verified_retail_dressing() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import environment_kit_piece, environment_kit_piece_rows

    rows = environment_kit_piece_rows(game="K1")
    taris = tuple(
        row
        for row in rows
        if row["building_style_id"] == "architecture:k1_taris_apartments"
        and row["role"] == "dressing"
    )
    shadowlands = tuple(
        row
        for row in rows
        if row["building_style_id"] == "architecture:k1_shadowlands"
        and row["role"] == "dressing"
    )
    taris_buildings = tuple(
        row
        for row in rows
        if row["building_style_id"] == "architecture:k1_taris_apartments"
        and row["role"] == "room_tile"
        and row["module_resref"] in {"m02ab", "m02ac"}
    )
    shadowlands_rooms = tuple(
        row
        for row in rows
        if row["building_style_id"] == "architecture:k1_shadowlands"
        and row["role"] == "room_tile"
        and row["module_resref"] == "m25ab"
    )
    assert {row["class_id"] for row in taris} == {
        "dressing:apartment_light_bay",
        "dressing:apartment_service_divider",
        "dressing:apartment_number_plate",
    }
    assert {row["class_id"] for row in shadowlands} == {
        "dressing:ancient_tree_trunk",
        "dressing:ancient_root_arch",
        "dressing:ancient_root_cluster",
        "dressing:fallen_tree_trunk",
    }
    assert all(row["placement_quality"] == "verified" for row in taris + shadowlands)
    assert all(environment_kit_piece(row["piece_id"]).source_surface_names for row in taris + shadowlands)
    assert all(row["building_style_id"] for row in taris + shadowlands)
    assert taris_buildings, "Upper City exterior buildings must appear in the Taris kit shelf."
    assert shadowlands_rooms, "The cut Shadowlands geometry must remain available as organic building stock."


def test_t2909_shadowlands_vanilla_room_sockets_follow_retail_wok_transitions() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_environment_kits import scan_vanilla_environment_kits

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the Shadowlands socket proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))
    collections = scan_vanilla_environment_kits(
        resources,
        games=("K1",),
        module_resrefs=("m25aa",),
    )
    shadowlands = next(collection for collection in collections if collection.collection_id == "k1_m25aa")
    bend = next(piece for piece in shadowlands.pieces if piece.room_resref == "m25aa_11a")

    assert len(bend.magnets) == 3
    assert all(magnet.source == "wok_transition_edge_group" for magnet in bend.magnets)
    assert len({tuple(round(value, 4) for value in magnet.local_position) for magnet in bend.magnets}) == 3


def test_t2909_taris_and_shadowlands_dressing_extracts_installed_retail_geometry() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K1 retail corpus is required for the environment dressing proof.")
    resources = ResourceManager()
    assert resources.set_k1_dir(str(game_dir))
    for texture_resref in (
        "lhr_space01",
        "lhr_space02",
        "lts_sky0001",
        "lts_sky0002",
        "lts_sky0003",
        "lts_sky0004",
        "lts_sky0005",
        "lka_tree05",
        "lko_sky01",
        "lko_sky02",
        "lko_sky03",
        "lko_sky04",
        "lko_sky05",
    ):
        assert resources.get_texture(texture_resref, "K1"), texture_resref
    controller = ModuleEditorController()
    controller.new_project(name="grkitdress", game="K1")
    piece_ids = (
        "k1_taris_apartments_illuminated_wall_bay",
        "k1_taris_apartments_service_divider",
        "k1_taris_apartments_number_plate",
        "k1_shadowlands_ancient_trunk",
        "k1_shadowlands_ancient_root_arch",
        "k1_shadowlands_root_cluster",
        "k1_shadowlands_broken_trunk",
    )
    placed: list[str] = []
    for index, piece_id in enumerate(piece_ids):
        assert controller.map_studio_environment_kit_preview_model(
            piece_id,
            resource_manager=resources,
        ) is not None
        placed.append(
            controller.add_authored_environment_kit_piece(
                piece_id=piece_id,
                position=(float(index * 100), 0.0, 0.0),
                resource_manager=resources,
            )
        )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert len(authored.rooms) == len(piece_ids)
    assert {room.normalised_resref() for room in authored.rooms} == set(placed)
    for room in authored.rooms:
        primitive = room.primitive
        assert primitive.surfaces
        assert all(surface.faces for surface in primitive.surfaces)
        assert all(len(surface.uvs) == len(surface.vertices) for surface in primitive.surfaces)
        assert primitive.wok is not None and not primitive.wok.faces
        assert primitive.metadata["visual_only"] is True


def test_t2909_onderon_browser_standardizes_rooms_buildings_and_small_props() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_environment_kits import (
        environment_kit_builder_style_id,
        environment_kit_collection_rows,
        environment_kit_piece_rows,
    )

    assert environment_kit_builder_style_id("K2", "501ond") == "architecture:k2_onderon_city"
    assert environment_kit_builder_style_id("K2", "503ond") == "architecture:k2_onderon_cantina"
    assert environment_kit_builder_style_id("K2", "504ond") == "architecture:k2_onderon_sky_ramp"
    assert environment_kit_builder_style_id("K2", "506ond") == "architecture:k2_onderon_palace"

    collections = {
        row["collection_id"]: row
        for row in environment_kit_collection_rows(game="K2")
        if str(row["collection_id"]).startswith("k2_onderon_")
    }
    assert {
        "k2_onderon_city_environment",
        "k2_onderon_cantina_environment",
        "k2_onderon_sky_ramp_environment",
        "k2_onderon_palace_environment",
    } <= set(collections)
    rows = tuple(
        row
        for row in environment_kit_piece_rows(game="K2")
        if str(row["collection_id"]).startswith("k2_onderon_")
    )
    buildings = tuple(row for row in rows if str(row["class_id"]).startswith("building:"))
    props = tuple(row for row in rows if str(row["class_id"]).startswith("dressing:"))
    assert len(buildings) >= 8
    assert len(props) >= 8
    assert all(row["role"] == "dressing" for row in rows)
    assert any("external building" in tuple(row["tags"]) for row in buildings)
    assert {"floor", "wall"} <= {row["anchor_mode"] for row in props}


def test_t2909_onderon_curated_assets_extract_from_installed_k2_with_original_uvs() -> None:
    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K2 retail corpus is required for the Onderon environment-piece proof.")
    resources = ResourceManager()
    assert resources.set_k2_dir(str(game_dir))
    controller = ModuleEditorController()
    controller.new_project(name="grondetail", game="K2")
    proof_pieces = (
        "k2_onderon_city_environment_market_pavilion",
        "k2_onderon_city_environment_cantina_sign",
        "k2_onderon_cantina_environment_cantina_chair",
        "k2_onderon_palace_environment_royal_statue",
    )
    placed = []
    for index, piece_id in enumerate(proof_pieces):
        assert controller.map_studio_environment_kit_preview_model(
            piece_id,
            resource_manager=resources,
        ) is not None
        placed.append(
            controller.add_authored_environment_kit_piece(
                piece_id=piece_id,
                position=(float(index * 50), 0.0, 0.0),
                resource_manager=resources,
            )
        )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    placed_rooms = tuple(room for room in authored.rooms if room.normalised_resref() in set(placed))
    assert len(placed_rooms) == len(proof_pieces)
    for room in placed_rooms:
        primitive = room.primitive
        assert primitive.surfaces
        assert all(surface.faces for surface in primitive.surfaces)
        assert all(len(surface.uvs) == len(surface.vertices) for surface in primitive.surfaces)
        assert primitive.wok is not None and not primitive.wok.faces
        assert primitive.metadata["visual_only"] is True


def test_t2909_onderon_palace_stock_room_faces_outward_and_keeps_walkmesh() -> None:
    """The two threshold-aligned rotations must choose the room body outside the authored wall."""

    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K2 retail corpus is required for the Onderon palace snap proof.")
    resources = ResourceManager()
    assert resources.set_k2_dir(str(game_dir))
    controller = ModuleEditorController()
    controller.new_project(name="gronorient", game="K2")
    authored_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 14.0), (0.0, 14.0)),
        wall_height=6.0,
        style_id="architecture:k2_onderon_palace",
        architecture_archetype="palace_gallery",
        include_ceiling=True,
    )
    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k2_506ond_506ondo",
        position=(9.0, 14.0, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)
    trim = dict(stock.primitive.metadata["environment_kit_connection_trim"])
    assert trim["render_faces_before"] > 0
    assert trim["render_faces_after"] > 0
    build = compile_authored_room_connection_walkmeshes(authored)
    assert build.ready is True
    assert len(build.portals) == 1
    assert build.portals[0].midpoint_gap <= 1.0e-5
    assert {build.portals[0].source_room_resref, build.portals[0].target_room_resref} == {
        authored_room,
        stock_room,
    }


def test_t2909_onderon_cantina_snap_uses_the_door_adjacent_walkmesh_side() -> None:
    """Off-centre render decoration must not flip the stock room through its doorway."""

    _install_native_payload_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_layout import authored_room_connection_hooks
    from src.core.modules.authored_module_walkmesh import combine_authored_module_walkmesh
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    game_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not (game_dir / "chitin.key").is_file():
        pytest.skip("The installed K2 retail corpus is required for the Onderon Cantina snap proof.")
    resources = ResourceManager()
    assert resources.set_k2_dir(str(game_dir))
    controller = ModuleEditorController()
    controller.new_project(name="groncantwalk", game="K2")
    authored_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (22.0, 0.0), (22.0, 16.0), (0.0, 16.0)),
        wall_height=7.2,
        style_id="architecture:k2_onderon_cantina",
        architecture_archetype="cantina_gallery",
        include_ceiling=True,
    )
    stock_room = controller.add_authored_environment_kit_piece(
        piece_id="k2_503ond_503onde",
        position=(11.0, 16.0, 0.0),
        resource_manager=resources,
    )
    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    hook = next(
        item
        for item in authored_room_connection_hooks(authored)
        if item.room_resref == authored_room and item.connected_room_resref == stock_room
    )
    stock = next(room for room in authored.rooms if room.normalised_resref() == stock_room)
    source_magnet = str(stock.metadata["environment_kit_source_magnet_id"])
    source_portal = next(
        row
        for row in stock.primitive.metadata["walkmesh_portals"]
        if str(row["magnet_id"]) == source_magnet
    )
    face = stock.primitive.wok.faces[int(source_portal["source_face_index"])]
    adjacent_vertices = tuple(
        stock.primitive.wok.verts[index]
        for index in (face.v1, face.v2, face.v3)
    )
    adjacent_center = (
        float(stock.position[0])
        + sum(float(vertex[0]) for vertex in adjacent_vertices) / 3.0,
        float(stock.position[1])
        + sum(float(vertex[1]) for vertex in adjacent_vertices) / 3.0,
    )
    adjacent_side = (
        (adjacent_center[0] - float(hook.position[0])) * float(hook.outward[0])
        + (adjacent_center[1] - float(hook.position[1])) * float(hook.outward[1])
    )
    assert adjacent_side > 0.05

    combined = combine_authored_module_walkmesh(authored)
    assert not combined.blocking_issues
    session = MapStudioPIESession(
        combined.wok,
        game="K2",
        spawn_position=(
            float(hook.position[0]) - float(hook.outward[0]) * 1.5,
            float(hook.position[1]) - float(hook.outward[1]) * 1.5,
            float(hook.position[2]) + 0.05,
        ),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    camera_azimuth = math.degrees(
        math.atan2(-float(hook.outward[1]), -float(hook.outward[0]))
    )
    session.set_move_input(1.0, 0.0, camera_azimuth_degrees=camera_azimuth, run=True)
    crossed = False
    for _index in range(1200):
        session.advance(1.0 / 30.0)
        distance = (
            (float(session.state.position[0]) - float(hook.position[0]))
            * float(hook.outward[0])
            + (float(session.state.position[1]) - float(hook.position[1]))
            * float(hook.outward[1])
        )
        if distance > 1.0:
            crossed = True
            break
    assert crossed


def test_t2909_onderon_vanilla_sky_presets_author_a_visual_only_dome() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_skybox import available_kotor_skybox_presets
    from src.core.modules.module_editor_controller import ModuleEditorController

    presets = {preset.preset_id: preset for preset in available_kotor_skybox_presets("K2")}
    iziz = presets["k2_onderon_iziz_daylight"]
    assert iziz.source_module == "502ond"
    assert iziz.source_room == "502ondd"
    assert {texture for _face, texture in iziz.textures.ordered_items()} == {
        "ond_sky1",
        "ond_sky2",
        "ond_sky3",
        "ond_sky4",
        "ond_sky5",
    }

    controller = ModuleEditorController()
    controller.new_project(name="gronsky", game="K2")
    room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 14.0), (0.0, 14.0)),
        wall_height=8.5,
        style_id="architecture:k2_onderon_city",
        architecture_archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
    )
    sky, _message = controller.create_authored_five_face_skybox(
        room_resref="gronskydome",
        north_texture=iziz.textures.north,
        east_texture=iziz.textures.east,
        south_texture=iziz.textures.south,
        west_texture=iziz.textures.west,
        top_texture=iziz.textures.top,
        half_extent=iziz.half_extent,
        bottom_z=iziz.bottom_z,
        top_z=iziz.top_z,
        visible_rooms=(room,),
        authoring_metadata={
            "skybox_preset_id": iziz.preset_id,
            "skybox_source_module": iziz.source_module,
            "skybox_source_room": iziz.source_room,
        },
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    sky_room = next(candidate for candidate in authored.rooms if candidate.normalised_resref() == sky.normalised_resref())
    assert sky_room.primitive.wok is not None and not sky_room.primitive.wok.faces
    assert sky_room.metadata["skybox_preset_id"] == "k2_onderon_iziz_daylight"
    assert all(surface.backdrop for surface in sky_room.primitive.surfaces)


def test_t2909_established_kits_offer_style_aware_retail_sky_presets() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_skybox import available_kotor_skybox_presets

    expectations = {
        "architecture:k1_endar_spire": (
            "k1_endar_spire_starfield",
            {"lhr_space01", "lhr_space02"},
        ),
        "architecture:k1_taris_apartments": (
            "k1_taris_upper_city",
            {
                "lts_sky0001",
                "lts_sky0002",
                "lts_sky0003",
                "lts_sky0004",
                "lts_sky0005",
            },
        ),
        "architecture:k1_shadowlands": (
            "k1_shadowlands_canopy",
            {"lka_tree05"},
        ),
        "architecture:k1_korriban_tombs": (
            "k1_korriban_valley",
            {
                "lko_sky01",
                "lko_sky02",
                "lko_sky03",
                "lko_sky04",
                "lko_sky05",
            },
        ),
        "architecture:k1_korriban_caves": (
            "k1_korriban_valley",
            {
                "lko_sky01",
                "lko_sky02",
                "lko_sky03",
                "lko_sky04",
                "lko_sky05",
            },
        ),
    }
    for style_id, (preset_id, textures) in expectations.items():
        presets = available_kotor_skybox_presets("K1", style_id)
        assert presets and presets[0].preset_id == preset_id
        assert style_id in presets[0].building_style_ids
        assert {texture for _face, texture in presets[0].textures.ordered_items()} == textures


def test_t2909_environment_room_occupancy_rejects_crossing_walkable_volume() -> None:
    """Solid kit rooms cannot silently intersect an unrelated authored room."""

    _install_native_payload_paths()

    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.map_studio_environment_kits import (
        audit_environment_kit_room_occupancy,
    )

    candidate = FloorPlanRoomPrimitive(
        room_resref="grcandidate",
        points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
    )
    occupied = AuthoredRoomSpec(
        room_resref="groccupied",
        primitive=FloorPlanRoomPrimitive(
            room_resref="groccupied",
            points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
        ),
        position=(3.0, 0.0, 0.0),
    )

    blocked = audit_environment_kit_room_occupancy(
        candidate,
        position=(0.0, 0.0, 0.0),
        rooms=(occupied,),
    )
    assert blocked["ok"] is False
    assert blocked["policy"] == "retail_wok_overlap_rejected"
    assert blocked["conflicts"][0]["room_resref"] == "groccupied"
    assert blocked["conflicts"][0]["overlap_area_m2"] >= 0.04

    clear = audit_environment_kit_room_occupancy(
        candidate,
        position=(-5.0, 0.0, 0.0),
        rooms=(occupied,),
    )
    ignored = audit_environment_kit_room_occupancy(
        candidate,
        position=(0.0, 0.0, 0.0),
        rooms=(occupied,),
        ignored_room_resrefs=("groccupied",),
    )
    assert clear["ok"] is True
    assert ignored["ok"] is True


def test_t2909_environment_render_overlap_is_trimmed_to_existing_room_boundary() -> None:
    """A stock render shell cannot continue through an already-authored room."""

    _install_native_payload_paths()

    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
    )
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.map_studio_environment_kits import (
        trim_environment_kit_room_volume_overlap,
    )

    surface = ImportedMeshSurface(
        name="crossing_wall",
        texture="ond_wall",
        vertices=((-1.0, 1.0, 0.0), (3.0, 1.0, 0.0), (-1.0, 3.0, 0.0)),
        faces=((0, 1, 2),),
        face_mats=(4,),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
        uvs_lm=((0.1, 0.1), (0.9, 0.1), (0.1, 0.9)),
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="grcandidate",
        surfaces=(surface,),
    )
    occupied = AuthoredRoomSpec(
        room_resref="groccupied",
        primitive=FloorPlanRoomPrimitive(
            room_resref="groccupied",
            points=((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
        ),
    )

    trimmed = trim_environment_kit_room_volume_overlap(
        primitive,
        position=(0.0, 0.0, 0.0),
        rooms=(occupied,),
    )
    assert trimmed.surfaces
    result = trimmed.surfaces[0]
    assert len(result.uvs) == len(result.vertices)
    assert len(result.normals) == len(result.vertices)
    assert len(result.uvs_lm) == len(result.vertices)
    assert set(result.face_mats) == {4}
    for face in result.faces:
        centroid = tuple(
            sum(float(result.vertices[index][axis]) for index in face) / 3.0
            for axis in range(2)
        )
        assert not (
            0.002 < centroid[0] < 1.998
            and 0.002 < centroid[1] < 1.998
        )
    audit = trimmed.metadata["environment_kit_room_volume_trim"]
    assert audit["rooms"] == ["groccupied"]
    assert audit["uv_policy"] == "interpolated_without_rescaling"
