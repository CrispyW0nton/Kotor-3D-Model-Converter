from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
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


def test_t2611_compiles_rectangle_floor_plan_to_room_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    primitive = FloorPlanRoomPrimitive(
        room_resref="grdev_poly",
        points=((-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)),
        wall_height=2.5,
        floor_surface_id="metal",
        material=PrimitiveMaterial(texture="CM_Baremetal"),
    )

    geometry = compile_floor_plan_room_geometry(primitive)

    assert geometry.room_resref == "grdev_poly"
    assert geometry.room_mesh.name == "grdev_poly_floor"
    assert geometry.room_mesh.texture == "CM_Baremetal"
    assert geometry.room_mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert geometry.room_mesh.metadata["surface_id"] == 10
    assert geometry.wok.walkable_face_count() == 2
    assert [face.surface for face in geometry.wok.faces] == [10, 10]
    assert len(geometry.helper_meshes) == 4
    assert geometry.helper_meshes[0].metadata["primitive"] == "floor_plan_wall"
    assert geometry.metadata["primitive"] == "floor_plan_extrusion"
    assert geometry.metadata["wall_count"] == 4
    assert geometry.metadata["polygon_area"] == 8.0


def test_t2611_clockwise_floor_plan_is_normalized_for_wok_and_mesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry, polygon_signed_area

    primitive = FloorPlanRoomPrimitive(
        room_resref="clockwise",
        points=((-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)),
    )

    geometry = compile_floor_plan_room_geometry(primitive)

    assert polygon_signed_area(primitive.points) < 0.0
    assert polygon_signed_area(tuple((x, y) for x, y, _ in geometry.room_mesh.vertices)) > 0.0
    assert geometry.room_mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert geometry.wok.faces[0].adj3 == 1
    assert geometry.wok.faces[1].adj1 == 0


def test_t2611_invalid_floor_plan_blocks_before_geometry_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, validate_floor_plan_room_primitive

    too_few = validate_floor_plan_room_primitive(FloorPlanRoomPrimitive(room_resref="bad", points=((0.0, 0.0), (1.0, 0.0))))
    duplicate = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(room_resref="bad", points=((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (0.0, 1.0)))
    )
    concave = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad",
            points=((0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)),
        )
    )

    assert not too_few.ok
    assert any("at least three" in issue for issue in too_few.blocking_issues)
    assert not duplicate.ok
    assert any("duplicate" in issue for issue in duplicate.blocking_issues)
    assert not concave.ok
    assert any("convex" in issue for issue in concave.blocking_issues)


def test_t2613_floor_plan_doorway_opening_splits_wall_panels() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening, compile_floor_plan_room_geometry

    primitive = FloorPlanRoomPrimitive(
        room_resref="door_room",
        points=((-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)),
        wall_height=3.0,
        openings=(FloorPlanWallOpening(name="door_a", edge_index=0, center_fraction=0.5, width=1.0, height=2.0),),
    )

    geometry = compile_floor_plan_room_geometry(primitive)
    wall_names = [mesh.name for mesh in geometry.helper_meshes]
    opening_panels = [mesh for mesh in geometry.helper_meshes if mesh.metadata.get("opening_name") == "door_a"]

    assert geometry.metadata["opening_count"] == 1
    assert geometry.metadata["wall_count"] == 6
    assert wall_names[:3] == ["door_room_wall_01_left", "door_room_wall_01_lintel", "door_room_wall_01_right"]
    assert len(opening_panels) == 3
    assert {mesh.metadata["wall_panel"] for mesh in opening_panels} == {"opening_left", "opening_lintel", "opening_right"}
    lintel = next(mesh for mesh in opening_panels if mesh.metadata["wall_panel"] == "opening_lintel")
    assert min(vertex[2] for vertex in lintel.vertices) == 2.0
    assert max(vertex[2] for vertex in lintel.vertices) == 3.0
    assert geometry.wok.walkable_face_count() == 2


def test_t2613_invalid_floor_plan_opening_blocks_before_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening, validate_floor_plan_room_primitive

    oversized = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad_opening",
            points=((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),
            openings=(FloorPlanWallOpening(name="too_wide", edge_index=0, width=4.0, height=1.0),),
        )
    )
    too_tall = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad_opening",
            points=((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),
            openings=(FloorPlanWallOpening(name="too_tall", edge_index=0, width=1.0, height=3.0),),
        )
    )

    assert not oversized.ok
    assert any("does not fit within wall edge" in issue for issue in oversized.blocking_issues)
    assert not too_tall.ok
    assert any("must leave wall geometry above it" in issue for issue in too_tall.blocking_issues)
