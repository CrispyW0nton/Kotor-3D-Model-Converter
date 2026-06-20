from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
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
    assert controller.project.dirty is True
    assert result.readiness is not None
    assert result.readiness.can_preview is True


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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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

    assert "roomPrimitiveRemoveRequested" in source
    assert "mapStudioRemoveCompositionPrimitiveButton" in source
    assert "def _emit_remove_composition_primitive" in source
    assert "self.builder_tab.roomPrimitiveRemoveRequested.connect(self.remove_authored_room_primitive)" in window_source
    assert "self.controller.remove_authored_room_primitive" in window_source


def test_t2676_builder_tab_exposes_primitive_style_controls() -> None:
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

    assert "roomPrimitiveStyleRequested" in source
    assert "mapStudioPrimitiveTextureLineEdit" in source
    assert "mapStudioPrimitiveSurfaceComboBox" in source
    assert "mapStudioApplyPrimitiveStyleButton" in source
    assert "def _emit_primitive_style" in source
    assert "self.builder_tab.roomPrimitiveStyleRequested.connect(self.apply_authored_room_primitive_style)" in window_source
    assert "self.controller.set_authored_room_primitive_style" in window_source
