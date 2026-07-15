from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _composition_project():
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition
    from src.core.modules.authored_room_primitives import (
        ConePrimitive,
        CubePrimitive,
        CylinderPrimitive,
        FloorPrimitive,
        SpherePrimitive,
        TorusPrimitive,
    )

    composition = AuthoredRoomComposition(
        room_resref="recipe_room",
        floor=FloorPrimitive(name="polyPlane1"),
        primitives=(
            CubePrimitive(name="polyCube1"),
            CylinderPrimitive(name="polyCylinder1"),
            SpherePrimitive(name="polySphere1"),
            ConePrimitive(name="polyCone1"),
            TorusPrimitive(name="polyTorus1"),
        ),
    )
    return create_composition_room_project(
        module_root="recipe",
        game="K2",
        display_name="Primitive Recipe",
        composition=composition,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="recipe")),
    )


def test_typed_recipe_schema_exposes_maya_inputs_defaults_and_stable_identity() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_operations import authored_room_composition_primitives

    project = _composition_project()
    rows = {row.primitive_name: row for row in authored_room_composition_primitives(project)}

    expected_keys = {
        "polyPlane1": {"width", "depth", "subdivisions_width", "subdivisions_depth", "axis_x", "axis_y", "axis_z", "height_baseline", "create_uvs"},
        "polyCube1": {"size_x", "size_y", "size_z", "subdivisions_x", "subdivisions_y", "subdivisions_z", "axis_x", "axis_y", "axis_z", "height_baseline", "create_uvs"},
        "polyCylinder1": {"radius", "height", "subdivisions_axis", "subdivisions_height", "subdivisions_caps", "axis_x", "axis_y", "axis_z", "height_baseline", "round_cap", "round_cap_height_compensation", "create_uvs"},
        "polySphere1": {"radius", "subdivisions_axis", "subdivisions_height", "axis_x", "axis_y", "axis_z", "height_baseline", "create_uvs"},
        "polyCone1": {"radius", "height", "subdivisions_axis", "subdivisions_height", "subdivisions_caps", "axis_x", "axis_y", "axis_z", "height_baseline", "round_cap", "create_uvs"},
        "polyTorus1": {"radius", "section_radius", "subdivisions_axis", "subdivisions_height", "twist", "axis_x", "axis_y", "axis_z", "height_baseline", "create_uvs"},
    }
    for name, keys in expected_keys.items():
        row = rows[name]
        properties = {item.key: item for item in row.properties}
        assert set(properties) == keys
        assert row.construction_kind
        assert row.construction_schema_version == 1
        assert row.construction_node_id
        assert all(item.has_default for item in properties.values())
        assert properties["axis_z"].default == 1.0
        assert properties["height_baseline"].minimum == -1.0
        assert properties["height_baseline"].maximum == 1.0

    cube_uvs = {label: value for label, value in {item.key: item for item in rows["polyCube1"].properties}["create_uvs"].choices}
    assert cube_uvs["None"] == 0
    assert cube_uvs["Normalize Collectively"] == 3
    assert "shares one deterministic UV layout" in {item.key: item for item in rows["polyCube1"].properties}["create_uvs"].implementation_note

    repeated = {row.primitive_name: row.construction_node_id for row in authored_room_composition_primitives(project)}
    assert repeated == {name: row.construction_node_id for name, row in rows.items()}


def test_recipe_edits_normalize_axis_validate_ranges_and_round_trip_kmap() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_operations import authored_room_composition_primitives, set_authored_room_composition_primitive_dimensions

    project = _composition_project()
    original_id = {row.primitive_name: row.construction_node_id for row in authored_room_composition_primitives(project)}["polyTorus1"]
    project = set_authored_room_composition_primitive_dimensions(
        project,
        room_resref="recipe_room",
        primitive_name="polyTorus1",
        dimensions={
            "radius": 2.0,
            "section_radius": 0.4,
            "subdivisions_axis": 16,
            "subdivisions_height": 8,
            "twist": 90.0,
            "axis_x": 0.0,
            "axis_y": 4.0,
            "axis_z": 0.0,
            "height_baseline": -1.0,
            "create_uvs": False,
        },
    )
    payload = authored_project_to_kmap_payload(project)
    recipe = payload["rooms"][0]["primitive"]["primitives"][-1]
    assert recipe["axis"] == [0.0, 1.0, 0.0]
    assert recipe["twist"] == 90.0
    assert recipe["height_baseline"] == -1.0
    assert recipe["create_uvs"] is False
    assert recipe["construction_schema_version"] == 1
    assert recipe["construction_node_id"] == original_id

    restored = authored_project_from_kmap_payload(payload)
    restored_row = {row.primitive_name: row for row in authored_room_composition_primitives(restored)}["polyTorus1"]
    assert restored_row.construction_node_id == original_id
    restored_values = {item.key: item.value for item in restored_row.properties}
    assert restored_values["axis_y"] == 1.0
    assert restored_values["twist"] == 90.0
    assert restored_values["create_uvs"] is False

    with pytest.raises(ValueError, match="non-zero"):
        set_authored_room_composition_primitive_dimensions(
            project,
            room_resref="recipe_room",
            primitive_name="polyTorus1",
            dimensions={"axis_x": 0.0, "axis_y": 0.0, "axis_z": 0.0},
        )
    with pytest.raises(ValueError, match="between 0.0 and 360.0"):
        set_authored_room_composition_primitive_dimensions(
            project,
            room_resref="recipe_room",
            primitive_name="polyTorus1",
            dimensions={"twist": 361.0},
        )


def test_maya_cap_topology_oracles_round_caps_and_floor_wok_axis_match() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import (
        ConePrimitive,
        CylinderPrimitive,
        FloorPrimitive,
        build_cone_mesh,
        build_cylinder_mesh,
        build_floor_mesh,
        build_floor_wok,
        primitive_logical_topology,
    )

    cylinder0 = CylinderPrimitive(name="c0", radius=1.0, height=2.0, segments=8, subdivisions_caps=0, center=(0.0, 0.0, 0.0))
    cylinder1 = CylinderPrimitive(name="c1", radius=1.0, height=2.0, segments=8, subdivisions_caps=1, center=(0.0, 0.0, 0.0))
    cone0 = ConePrimitive(name="k0", radius=1.0, height=2.0, subdivisions_axis=8, subdivisions_caps=0, center=(0.0, 0.0, 0.0))
    assert primitive_logical_topology(cylinder0) == {"vertices": 16, "edges": 24, "faces": 10, "triangles": 28}
    assert primitive_logical_topology(cylinder1) == {"vertices": 18, "edges": 40, "faces": 24, "triangles": 32}
    assert primitive_logical_topology(cone0) == {"vertices": 9, "edges": 16, "faces": 9, "triangles": 14}
    assert len(build_cylinder_mesh(cylinder0).faces) == 28
    assert len(build_cylinder_mesh(cylinder1).faces) == 32
    assert len(build_cone_mesh(cone0).faces) == 14

    rounded = build_cylinder_mesh(CylinderPrimitive(name="rounded", radius=1.0, height=2.0, segments=8, subdivisions_caps=0, round_cap=True, center=(0.0, 0.0, 0.0)))
    compensated = build_cylinder_mesh(CylinderPrimitive(name="compensated", radius=1.0, height=2.0, segments=8, subdivisions_caps=0, round_cap=True, round_cap_height_compensation=True, center=(0.0, 0.0, 0.0)))
    assert (min(point[2] for point in rounded.vertices), max(point[2] for point in rounded.vertices)) == pytest.approx((-2.0, 2.0))
    assert (min(point[2] for point in compensated.vertices), max(point[2] for point in compensated.vertices)) == pytest.approx((-1.0, 1.0))
    assert len(rounded.faces) == len(compensated.faces) == 28

    plane = FloorPrimitive(name="axis_plane", width=4.0, depth=2.0, axis=(1.0, 0.0, 0.0))
    render = build_floor_mesh(plane)
    wok = build_floor_wok(plane)
    render_positions = {tuple(round(value, 7) for value in point) for point in render.vertices}
    wok_positions = {tuple(round(value, 7) for value in point) for point in wok.verts}
    assert render_positions == wok_positions
    assert {round(point[0], 7) for point in wok.verts} == {0.0}
    assert len(wok.faces) == 2


def test_legacy_cone_missing_cap_field_migrates_without_silent_topology_change() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_room_composition import PlacedRoomPrimitive

    def decode(recipe: dict):
        project = authored_project_from_kmap_payload(
            {
                "module_root": "legacy",
                "game": "K2",
                "rooms": [
                    {
                        "room_resref": "legacy_room",
                        "primitive": {
                            "type": "composition",
                            "room_resref": "legacy_room",
                            "floor": {"type": "floor", "name": "legacy_floor"},
                            "primitives": [recipe],
                        },
                    }
                ],
            }
        )
        primitive = project.rooms[0].primitive.primitives[0]
        return primitive.primitive if isinstance(primitive, PlacedRoomPrimitive) else primitive

    legacy = decode({"type": "cone", "name": "legacy_cone"})
    retained = decode({"type": "cone", "name": "new_cone", "recipe_version": 1})
    legacy_again = decode({"type": "cone", "name": "legacy_cone"})
    assert legacy.subdivisions_caps == 1
    assert retained.subdivisions_caps == 0
    assert legacy.construction_node_id == legacy_again.construction_node_id
    assert legacy.construction_node_id


def test_duplicate_special_clones_recipe_with_fresh_stable_round_trip_identity() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_composition import PlacedRoomPrimitive
    from src.core.modules.authored_room_operations import (
        authored_room_composition_primitives,
        duplicate_authored_room_composition_primitive,
        set_authored_room_composition_primitive_dimensions,
    )

    project = duplicate_authored_room_composition_primitive(
        _composition_project(),
        room_resref="recipe_room",
        primitive_name="polyCube1",
        duplicate_count=2,
        translation_offset=(1.0, 0.0, 0.0),
    )
    composition = project.rooms[0].primitive
    duplicate_names = tuple(composition.metadata["last_duplicate_special_names"])
    assert len(duplicate_names) == 2

    rows = {row.primitive_name: row for row in authored_room_composition_primitives(project)}
    identity_by_name = {
        name: rows[name].construction_node_id
        for name in ("polyCube1",) + duplicate_names
    }
    assert all(identity_by_name.values())
    assert len(set(identity_by_name.values())) == 3

    source_base = next(item for item in composition.primitives if getattr(item, "name", "") == "polyCube1")
    duplicate_bases = [
        item.primitive
        for item in composition.primitives
        if isinstance(item, PlacedRoomPrimitive) and item.name in duplicate_names
    ]
    assert all(base is not source_base for base in duplicate_bases)
    assert [base.name for base in duplicate_bases] == list(duplicate_names)

    payload = authored_project_to_kmap_payload(project)
    restored = authored_project_from_kmap_payload(payload)
    restored_ids = {
        row.primitive_name: row.construction_node_id
        for row in authored_room_composition_primitives(restored)
        if row.primitive_name in identity_by_name
    }
    assert restored_ids == identity_by_name

    edited = set_authored_room_composition_primitive_dimensions(
        restored,
        room_resref="recipe_room",
        primitive_name=duplicate_names[0],
        dimensions={"size_x": 4.0},
    )
    edited_rows = {row.primitive_name: row for row in authored_room_composition_primitives(edited)}
    assert {item.key: item.value for item in edited_rows[duplicate_names[0]].properties}["size_x"] == 4.0
    assert {item.key: item.value for item in edited_rows["polyCube1"].properties}["size_x"] == 1.0


def test_production_topology_counts_vertex_snap_and_legacy_fallback_use_correct_domains() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        authored_room_composition_primitive_universal_transform,
        authored_room_composition_primitive_vertex_snap_candidates,
        set_authored_room_edge_normal_policy,
        snap_authored_room_composition_primitive_pivot_to_vertex,
    )
    from src.core.modules.authored_room_primitives import CubePrimitive, CylinderPrimitive, FloorPrimitive, WallPrimitive

    composition = AuthoredRoomComposition(
        room_resref="topology_room",
        floor=FloorPrimitive(name="floor"),
        primitives=(
            CubePrimitive(name="cube"),
            CylinderPrimitive(name="cylinder", segments=8),
            WallPrimitive(name="legacy_wall"),
        ),
    )
    project = create_composition_room_project(
        module_root="topology",
        game="K2",
        display_name="Topology",
        composition=composition,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="topology")),
    )

    cube = authored_room_composition_primitive_universal_transform(
        project,
        room_resref="topology_room",
        primitive_name="cube",
    )
    cylinder = authored_room_composition_primitive_universal_transform(
        project,
        room_resref="topology_room",
        primitive_name="cylinder",
    )
    assert (cube.vertex_count, cube.metadata["logical_edge_count"], cube.face_count) == (8, 12, 6)
    assert (cylinder.vertex_count, cylinder.metadata["logical_edge_count"], cylinder.face_count) == (16, 24, 10)
    assert cube.metadata["topology_count_source"] == "retained_construction_cage"

    candidates = authored_room_composition_primitive_vertex_snap_candidates(
        project,
        room_resref="topology_room",
        primitive_name="cylinder",
        target_primitive_name="cube",
        max_results=64,
    )
    assert len(candidates) == 8
    assert {candidate.vertex_index for candidate in candidates} == set(range(8))
    snap_authored_room_composition_primitive_pivot_to_vertex(
        project,
        room_resref="topology_room",
        primitive_name="cylinder",
        target_primitive_name="cube",
        target_vertex_index=7,
    )
    with pytest.raises(ValueError, match="outside 0..7"):
        snap_authored_room_composition_primitive_pivot_to_vertex(
            project,
            room_resref="topology_room",
            primitive_name="cylinder",
            target_primitive_name="cube",
            target_vertex_index=8,
        )
    set_authored_room_edge_normal_policy(
        project,
        room_resref="topology_room",
        primitive_name="cube",
        policy="soft",
        edge_indices=[11],
    )
    with pytest.raises(ValueError, match="outside Primitive cube's editable edge range 0..11"):
        set_authored_room_edge_normal_policy(
            project,
            room_resref="topology_room",
            primitive_name="cube",
            policy="soft",
            edge_indices=[12],
        )

    wall = authored_room_composition_primitive_universal_transform(
        project,
        room_resref="topology_room",
        primitive_name="legacy_wall",
    )
    wall_mesh = primitive_to_mesh(composition.primitives[-1])
    assert wall.metadata["topology_count_source"] == "legacy_render_mesh_fallback"
    assert (wall.vertex_count, wall.face_count) == (len(wall_mesh.vertices), len(wall_mesh.faces))
