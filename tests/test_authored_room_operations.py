from __future__ import annotations

import sys
from pathlib import Path


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
        facing=180.0,
    )

    entry = controller.authored_module_entry_point()
    payload = controller.project.extra_sections["authored_module"]
    assert entry is not None
    assert entry.area_resref == "grentry"
    assert entry.position == (1.25, -2.5, 0.125)
    assert entry.facing == 180.0
    assert payload["placements"]["entry_point"]["area_resref"] == "grentry"
    assert payload["placements"]["entry_point"]["position"] == [1.25, -2.5, 0.125]
    assert payload["placements"]["entry_point"]["facing"] == 180.0
    assert payload["game_tested"] is False
    assert result.readiness is not None


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
    assert trigger.transition_destination == 2
    assert marker_metadata["opening_name"] == "south_door"
    assert marker_metadata["marker_kind"] == "trigger"
    assert marker_metadata["position"] == [0.0, -5.0, 0.0]
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
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    terrain = authored.rooms[0].primitive

    assert result.applied is True
    assert result.full_rebuild_deferred is True
    assert "full MDL/WOK rebuild deferred" in result.message
    assert controller.project.dirty is True
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
    assert {dimension.key for dimension in plane_row.dimensions} == {"width", "depth"}
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
