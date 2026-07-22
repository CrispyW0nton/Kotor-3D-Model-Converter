from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_t2907_pascal_builds_multiple_planet_interior_and_exterior_styles() -> None:
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
    assert all(row["role"] in {"room_tile", "exterior_tile"} for row in rows)
    assert all(":" in row["class_id"] for row in rows)
    assert all(row["collection_id"] and row["collection_label"] for row in rows)

    payload = environment_kit_drag_payload(rows[0]["piece_id"], rotation_degrees_z=45.0, scale=1.25)
    assert payload["schema"] == ENVIRONMENT_KIT_PAYLOAD_SCHEMA
    assert payload["piece_id"] == rows[0]["piece_id"]
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
