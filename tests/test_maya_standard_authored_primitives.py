from __future__ import annotations

import math
import sys
from pathlib import Path


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


def _assert_corner_complete_mesh(mesh) -> None:
    assert mesh.faces
    assert len(mesh.vertices) == len(mesh.normals) == len(mesh.uvs)
    for normal in mesh.normals:
        assert math.isclose(math.sqrt(sum(component * component for component in normal)), 1.0, abs_tol=1.0e-7)
    for face in mesh.faces:
        assert len(set(face)) == 3
        a, b, c = face
        p0, p1, p2 = (mesh.vertices[index] for index in face)
        edge1 = tuple(p1[index] - p0[index] for index in range(3))
        edge2 = tuple(p2[index] - p0[index] for index in range(3))
        cross = (
            edge1[1] * edge2[2] - edge1[2] * edge2[1],
            edge1[2] * edge2[0] - edge1[0] * edge2[2],
            edge1[0] * edge2[1] - edge1[1] * edge2[0],
        )
        assert sum(component * component for component in cross) > 1.0e-14
        average_normal = tuple(sum(mesh.normals[index][axis] for index in face) for axis in range(3))
        assert sum(cross[axis] * average_normal[axis] for axis in range(3)) > 0.0

        uv0, uv1, uv2 = (mesh.uvs[index] for index in face)
        uv_area = (
            (uv1[0] - uv0[0]) * (uv2[1] - uv0[1])
            - (uv1[1] - uv0[1]) * (uv2[0] - uv0[0])
        )
        assert abs(uv_area) > 1.0e-12
    assert all(0.0 <= value <= 1.0 for uv in mesh.uvs for value in uv)


def test_maya_standard_sphere_cone_torus_build_deterministic_corner_complete_meshes() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import (
        ConePrimitive,
        SpherePrimitive,
        TorusPrimitive,
        build_cone_mesh,
        build_sphere_mesh,
        build_torus_mesh,
    )

    sphere = build_sphere_mesh(
        SpherePrimitive(name="polySphere1", radius=1.25, subdivisions_axis=8, subdivisions_height=6)
    )
    cone = build_cone_mesh(
        ConePrimitive(
            name="polyCone1",
            radius=0.75,
            height=2.0,
            subdivisions_axis=8,
            subdivisions_height=3,
            subdivisions_caps=2,
        )
    )
    torus = build_torus_mesh(
        TorusPrimitive(
            name="polyTorus1",
            radius=1.5,
            section_radius=0.35,
            subdivisions_axis=8,
            subdivisions_height=6,
        )
    )

    assert len(sphere.faces) == 80
    assert len(cone.faces) == 64
    assert len(torus.faces) == 96
    assert sphere.metadata == {
        "primitive": "sphere",
        "subdivisions_axis": 8,
        "subdivisions_height": 6,
    }
    assert cone.metadata["subdivisions_caps"] == 2
    assert torus.metadata["primitive"] == "torus"
    for mesh in (sphere, cone, torus):
        _assert_corner_complete_mesh(mesh)

    # Rebuilding the same history parameters must preserve exact topology and
    # attribute ordering so KMAP edits and MDL preview caches stay stable.
    assert sphere == build_sphere_mesh(
        SpherePrimitive(name="polySphere1", radius=1.25, subdivisions_axis=8, subdivisions_height=6)
    )


def test_maya_standard_cube_and_wall_use_outward_hard_normals_and_face_uvs() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import (
        CubePrimitive,
        WallPrimitive,
        build_cube_mesh,
        build_wall_mesh,
    )

    cube = build_cube_mesh(CubePrimitive(name="pCube1", size=(2.0, 3.0, 4.0), center=(0.0, 0.0, 2.0)))
    wall = build_wall_mesh(WallPrimitive(name="pWall1", width=4.0, height=3.0, thickness=0.2))

    for mesh in (cube, wall):
        assert len(mesh.vertices) == 24
        assert len(mesh.faces) == 12
        assert mesh.metadata["hard_face_normals"] is True
        assert mesh.metadata["uv_layout"] == "per_face_0_1"
        _assert_corner_complete_mesh(mesh)


def test_maya_cube_and_plane_subdivisions_generate_deterministic_topology_without_inflating_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import (
        CubePrimitive,
        FloorPrimitive,
        build_cube_mesh,
        build_floor_mesh,
        build_floor_wok,
    )

    plane_primitive = FloorPrimitive(
        name="polyPlane1",
        width=6.0,
        depth=4.0,
        subdivisions_width=3,
        subdivisions_depth=2,
    )
    cube_primitive = CubePrimitive(
        name="polyCube1",
        size=(2.0, 3.0, 4.0),
        center=(0.0, 0.0, 2.0),
        subdivisions_x=2,
        subdivisions_y=3,
        subdivisions_z=4,
    )
    plane = build_floor_mesh(plane_primitive)
    cube = build_cube_mesh(cube_primitive)
    wok = build_floor_wok(plane_primitive)

    assert len(plane.vertices) == 12
    assert len(plane.faces) == 12
    assert len(cube.vertices) == 94
    assert len(cube.faces) == 104
    assert plane.metadata["subdivisions_width"] == 3
    assert plane.metadata["subdivisions_depth"] == 2
    assert cube.metadata["subdivisions_x"] == 2
    assert cube.metadata["subdivisions_y"] == 3
    assert cube.metadata["subdivisions_z"] == 4
    _assert_corner_complete_mesh(plane)
    _assert_corner_complete_mesh(cube)
    assert len(wok.verts) == 4
    assert len(wok.faces) == 2
    assert wok.walkable_face_count() == 2
    assert cube == build_cube_mesh(cube_primitive)


def test_maya_standard_primitives_compile_edit_and_round_trip_through_kmap() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import compile_authored_room_spec, create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_operations import (
        authored_room_composition_primitives,
        set_authored_room_composition_primitive_dimensions,
    )
    from src.core.modules.authored_room_primitives import ConePrimitive, FloorPrimitive, SpherePrimitive, TorusPrimitive

    composition = AuthoredRoomComposition(
        room_resref="mayaprim_room01",
        floor=FloorPrimitive(name="mayaprim_floor", width=8.0, depth=8.0),
        primitives=(
            SpherePrimitive(name="polySphere1", radius=0.75, subdivisions_axis=12, subdivisions_height=8),
            ConePrimitive(
                name="polyCone1",
                radius=0.5,
                height=1.5,
                subdivisions_axis=10,
                subdivisions_height=2,
                subdivisions_caps=2,
            ),
            TorusPrimitive(
                name="polyTorus1",
                radius=1.25,
                section_radius=0.2,
                subdivisions_axis=12,
                subdivisions_height=8,
            ),
        ),
    )
    project = create_composition_room_project(
        module_root="mayaprim",
        game="K2",
        display_name="Maya Primitive Parity",
        composition=composition,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="mayaprim")),
    )

    project = set_authored_room_composition_primitive_dimensions(
        project,
        room_resref="mayaprim_room01",
        primitive_name="polyTorus1",
        dimensions={
            "radius": 1.5,
            "section_radius": 0.3,
            "subdivisions_axis": 16,
            "subdivisions_height": 10,
        },
    )
    payload = authored_project_to_kmap_payload(project)
    restored = authored_project_from_kmap_payload(payload)
    geometry = compile_authored_room_spec(restored.rooms[0])
    validation = validate_authored_room_composition(restored.rooms[0].primitive)
    rows = {row.primitive_name: row for row in authored_room_composition_primitives(restored)}

    recipes = payload["rooms"][0]["primitive"]["primitives"]
    assert [recipe["type"] for recipe in recipes] == ["sphere", "cone", "torus"]
    assert recipes[0]["subdivisions_axis"] == 12
    assert recipes[1]["subdivisions_caps"] == 2
    assert recipes[2]["radius"] == 1.5
    assert recipes[2]["section_radius"] == 0.3
    assert validation.ok is True
    assert {mesh.name for mesh in geometry.helper_meshes} == {"polySphere1", "polyCone1", "polyTorus1"}
    assert geometry.metadata["primitive_count"] == 3
    assert tuple(dimension.key for dimension in rows["polySphere1"].dimensions) == (
        "radius",
        "subdivisions_axis",
        "subdivisions_height",
    )
    torus_dimensions = {dimension.key: dimension.value for dimension in rows["polyTorus1"].dimensions}
    assert torus_dimensions == {
        "radius": 1.5,
        "section_radius": 0.3,
        "subdivisions_axis": 16.0,
        "subdivisions_height": 10.0,
    }


def test_maya_cube_plane_subdivision_history_edits_and_kmap_defaults_round_trip() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition
    from src.core.modules.authored_room_operations import (
        authored_room_composition_primitives,
        set_authored_room_composition_primitive_dimensions,
    )
    from src.core.modules.authored_room_primitives import CubePrimitive, FloorPrimitive

    project = create_composition_room_project(
        module_root="mayasubd",
        game="K2",
        display_name="Maya Subdivision History",
        composition=AuthoredRoomComposition(
            room_resref="mayasubd_room01",
            floor=FloorPrimitive(
                name="polyPlane1",
                width=8.0,
                depth=6.0,
                subdivisions_width=2,
                subdivisions_depth=3,
            ),
            primitives=(
                CubePrimitive(
                    name="polyCube1",
                    subdivisions_x=2,
                    subdivisions_y=3,
                    subdivisions_z=4,
                ),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="mayasubd")),
    )
    project = set_authored_room_composition_primitive_dimensions(
        project,
        room_resref="mayasubd_room01",
        primitive_name="polyPlane1",
        dimensions={"subdivisions_width": 4, "subdivisions_depth": 5},
    )
    project = set_authored_room_composition_primitive_dimensions(
        project,
        room_resref="mayasubd_room01",
        primitive_name="polyCube1",
        dimensions={"subdivisions_x": 5, "subdivisions_y": 6, "subdivisions_z": 7},
    )

    payload = authored_project_to_kmap_payload(project)
    restored = authored_project_from_kmap_payload(payload)
    rows = {row.primitive_name: row for row in authored_room_composition_primitives(restored)}
    floor_payload = payload["rooms"][0]["primitive"]["floor"]
    cube_payload = payload["rooms"][0]["primitive"]["primitives"][0]

    assert floor_payload["subdivisions_width"] == 4
    assert floor_payload["subdivisions_depth"] == 5
    assert cube_payload["subdivisions_x"] == 5
    assert cube_payload["subdivisions_y"] == 6
    assert cube_payload["subdivisions_z"] == 7
    assert [dimension.key for dimension in rows["polyPlane1"].dimensions][-2:] == [
        "subdivisions_width",
        "subdivisions_depth",
    ]
    assert [dimension.key for dimension in rows["polyCube1"].dimensions][-3:] == [
        "subdivisions_x",
        "subdivisions_y",
        "subdivisions_z",
    ]

    legacy_payload = authored_project_to_kmap_payload(project)
    legacy_floor = legacy_payload["rooms"][0]["primitive"]["floor"]
    legacy_cube = legacy_payload["rooms"][0]["primitive"]["primitives"][0]
    legacy_floor.pop("subdivisions_width")
    legacy_floor.pop("subdivisions_depth")
    legacy_cube.pop("subdivisions_x")
    legacy_cube.pop("subdivisions_y")
    legacy_cube.pop("subdivisions_z")
    legacy_restored = authored_project_from_kmap_payload(legacy_payload)
    legacy_composition = legacy_restored.rooms[0].primitive
    assert legacy_composition.floor.subdivisions_width == 1
    assert legacy_composition.floor.subdivisions_depth == 1
    legacy_cube_primitive = legacy_composition.primitives[0]
    assert legacy_cube_primitive.subdivisions_x == 1
    assert legacy_cube_primitive.subdivisions_y == 1
    assert legacy_cube_primitive.subdivisions_z == 1


def test_maya_standard_primitive_actions_route_to_real_creation_commands_and_toolbar() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_modeling_tools import available_map_studio_tool_belt_actions
    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
        resolve_map_studio_tool_belt_action,
    )

    action_index = {action.key: action for action in available_map_studio_tool_belt_actions()}
    calls: list[dict[str, object]] = []

    class _RecordingController:
        def add_authored_room_primitive(self, **kwargs):
            calls.append(kwargs)
            return kwargs

    for key in ("sphere", "cone", "torus"):
        assert action_index[key].implemented is True
        context = MapStudioToolActionContext(
            room_resref="mayaprim_room01",
            primitive_name=f"{key}_created",
        )
        route = resolve_map_studio_tool_belt_action(key, context)
        assert route.enabled is True
        assert route.command_method == "add_authored_room_primitive"
        assert route.primitive_kind == key
        result = execute_map_studio_tool_belt_action(_RecordingController(), key, context)
        assert result["primitive_kind"] == key

    assert [call["primitive_kind"] for call in calls] == ["sphere", "cone", "torus"]

    repo = Path(__file__).resolve().parents[1]
    toolbar_source = (
        repo
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_toolbar.py"
    ).read_text(encoding="utf-8")
    for key, label in (("sphere", "Sphere"), ("cone", "Cone"), ("torus", "Torus")):
        assert f'(\"{key}\", \"{label}\"' in toolbar_source


def test_maya_standard_primitive_validation_rejects_invalid_history_settings() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import CubePrimitive, FloorPrimitive, SpherePrimitive, TorusPrimitive

    invalid = AuthoredRoomComposition(
        room_resref="bad_primitives",
        floor=FloorPrimitive(name="floor", subdivisions_width=0, subdivisions_depth=0),
        primitives=(
            CubePrimitive(name="badCube", subdivisions_x=0, subdivisions_y=1, subdivisions_z=1),
            SpherePrimitive(name="badSphere", radius=0.0, subdivisions_axis=2, subdivisions_height=1),
            TorusPrimitive(name="badTorus", radius=0.25, section_radius=0.5),
        ),
    )
    validation = validate_authored_room_composition(invalid)

    assert validation.ok is False
    assert any("floor subdivisions" in issue for issue in validation.blocking_issues)
    assert any("Cube primitive badCube subdivisions" in issue for issue in validation.blocking_issues)
    assert any("Sphere primitive badSphere" in issue for issue in validation.blocking_issues)
    assert any("Torus primitive badTorus" in issue for issue in validation.blocking_issues)
