from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
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


def test_t2603_rectangular_room_composition_compiles_to_floor_walls_and_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import (
        compile_authored_room_composition,
        create_rectangular_room_composition,
        validate_authored_room_composition,
    )
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    composition = create_rectangular_room_composition(
        RectangularRoomPrimitive(
            room_resref="grdev01_room01",
            width=10.0,
            depth=8.0,
            wall_height=3.25,
            floor_surface_id=4,
            texture="metal_floor",
            include_doorway_marker=True,
        )
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.room_resref == "grdev01_room01"
    assert geometry.room_mesh.name == "grdev01_room01_mesh"
    assert geometry.room_mesh.texture == "metal_floor"
    assert geometry.room_mesh.metadata["primitive"] == "floor"
    assert geometry.wok.walkable_face_count() == 4
    assert geometry.metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive_count"] == 4
    assert geometry.metadata["compiled_mesh_count"] == 6
    helper_names = {mesh.name for mesh in geometry.helper_meshes}
    assert {
        "grdev01_room01_wall_n",
        "grdev01_room01_wall_s",
        "grdev01_room01_wall_e",
        "grdev01_room01_wall_w",
        "grdev01_room01_door_marker",
    } <= helper_names


def test_t2603_composition_validation_rejects_duplicate_primitive_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, WallPrimitive

    composition = AuthoredRoomComposition(
        room_resref="badroom",
        floor=FloorPrimitive(name="duplicate"),
        primitives=(WallPrimitive(name="duplicate"),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "Duplicate authored room primitive name: duplicate" in validation.blocking_issues


def test_t2604_composition_validation_rejects_non_walk_floor_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="blocked",
        floor=FloorPrimitive(name="blocked_floor", surface_id="non_walk"),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "blocked floor surface 7 (NON_WALK) is not walkable." in validation.blocking_issues


def test_t2620_composition_adds_walkable_ramp_faces_to_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, compile_authored_room_composition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive

    composition = AuthoredRoomComposition(
        room_resref="ramp_room",
        floor=FloorPrimitive(name="ramp_room_floor", width=8.0, depth=8.0, surface_id="stone"),
        primitives=(
            RampPrimitive(
                name="ramp_room_ramp",
                width=2.0,
                length=3.0,
                height=1.0,
                # The low edge sits on the north floor boundary.  The ramp
                # extends outward, so it shares a real seam instead of
                # overlapping the floor's interior walkmesh.
                center=(0.0, 5.5, 0.0),
                surface_id="metal",
            ),
        ),
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.metadata["walkmesh_primitive_count"] == 1
    assert geometry.wok.walkable_face_count() == 6
    assert len(geometry.wok.verts) == 8
    assert [face.surface for face in geometry.wok.faces] == [4, 4, 4, 4, 10, 10]
    assert geometry.wok.verts[4:] == [(-1.0, 4.0, 0.0), (1.0, 4.0, 0.0), (1.0, 7.0, 1.0), (-1.0, 7.0, 1.0)]
    assert _walkable_component_count(geometry.wok) == 1
    from src.core.modules.module_format import WOKData

    assert _walkable_component_count(WOKData.from_bytes(geometry.wok.to_bytes())) == 1


def test_t2620_composition_blocks_unsnapped_walkmesh_primitive() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive

    composition = AuthoredRoomComposition(
        room_resref="unsnapped_ramp",
        floor=FloorPrimitive(name="unsnapped_floor", width=8.0, depth=8.0),
        # This low edge touches the south boundary but the ramp points inward
        # and overlaps the floor.  Equal coordinates must not create a seam.
        primitives=(RampPrimitive(name="floating_ramp", length=3.0, center=(0.0, -2.5, 0.0)),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert any(
        "Walkmesh primitive floating_ramp is disconnected from the room floor" in issue
        and "will not bridge open space" in issue
        for issue in validation.blocking_issues
    )


def test_t2620_composition_preserves_explicitly_reviewed_walkmesh_islands() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, compile_authored_room_composition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive
    from src.core.modules.module_format import WOKData

    composition = AuthoredRoomComposition(
        room_resref="reviewed_island",
        floor=FloorPrimitive(name="reviewed_floor", width=8.0, depth=8.0),
        primitives=(RampPrimitive(name="reviewed_ramp", center=(0.0, 0.0, 0.0)),),
        metadata={"allow_disconnected_walkmesh_islands": True},
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert any("explicitly preserves 2 disconnected walkmesh islands" in warning for warning in validation.warnings)
    assert _walkable_component_count(geometry.wok) == 2
    assert _walkable_component_count(WOKData.from_bytes(geometry.wok.to_bytes())) == 2


def test_t2620_wok_seam_split_preserves_surface_transition_and_winding() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import _append_wok
    from src.core.modules.module_format import WOKData, WOKFace

    base = WOKData(
        verts=[(-4.0, -4.0, 0.0), (4.0, -4.0, 0.0), (4.0, 4.0, 0.0), (-4.0, 4.0, 0.0)],
        faces=[
            WOKFace(0, 1, 2, surface=4),
            WOKFace(0, 2, 3, surface=4, trans2=37),
        ],
    )
    ramp = WOKData(
        verts=[(-1.0, 4.0, 0.0), (1.0, 4.0, 0.0), (1.0, 7.0, 1.0), (-1.0, 7.0, 1.0)],
        faces=[WOKFace(0, 1, 2, surface=10, trans1=53), WOKFace(0, 2, 3, surface=10)],
    )

    _append_wok(base, ramp)

    assert [face.surface for face in base.faces] == [4, 4, 4, 4, 10, 10]
    assert [base.faces[index].trans1 for index in (1, 2, 3)] == [37, -1, 37]
    assert base.faces[4].trans1 == -1
    seam_owners: list[tuple[int, int]] = []
    for face_index, face in enumerate(base.faces):
        triangle = (face.v1, face.v2, face.v3)
        for edge_index in range(3):
            directed = (triangle[edge_index], triangle[(edge_index + 1) % 3])
            if set(directed) == {4, 5}:
                seam_owners.append(directed)
        a, b, c = (base.verts[index] for index in triangle)
        signed_area_xy = (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (
            float(b[1]) - float(a[1])
        ) * (float(c[0]) - float(a[0]))
        assert signed_area_xy > 0.0
    assert seam_owners == [(5, 4), (4, 5)]
    assert base.to_bytes().startswith(b"BWM V1.0")


def test_t2620_composition_rejects_non_walkable_ramp_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive

    composition = AuthoredRoomComposition(
        room_resref="bad_ramp",
        floor=FloorPrimitive(name="bad_ramp_floor"),
        primitives=(RampPrimitive(name="bad_ramp_path", surface_id="non_walk"),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "bad_ramp_path ramp surface 7 (NON_WALK) is not walkable." in validation.blocking_issues


def test_t2624_composition_adds_walkable_stair_faces_to_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform, compile_authored_room_composition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, StairsPrimitive

    composition = AuthoredRoomComposition(
        room_resref="stair_room",
        floor=FloorPrimitive(name="stair_room_floor", width=8.0, depth=8.0, surface_id="stone"),
        primitives=(
            PlacedRoomPrimitive(
                primitive=StairsPrimitive(
                    name="stair_room_steps",
                    width=2.0,
                    depth=3.0,
                    height=1.25,
                    steps=5,
                    surface_id="metal",
                ),
                transform=PrimitiveTransform(translation=(0.0, 5.5, 0.0)),
            ),
        ),
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.metadata["walkmesh_primitive_count"] == 1
    assert geometry.wok.walkable_face_count() == 6
    assert len(geometry.wok.verts) == 8
    assert [face.surface for face in geometry.wok.faces] == [4, 4, 4, 4, 10, 10]
    assert geometry.wok.verts[4:] == [(-1.0, 4.0, 0.0), (1.0, 4.0, 0.0), (1.0, 7.0, 1.25), (-1.0, 7.0, 1.25)]
    assert _walkable_component_count(geometry.wok) == 1
    assert geometry.wok.to_bytes().startswith(b"BWM V1.0")
    assert geometry.helper_meshes[0].metadata["primitive"] == "stairs"
    assert geometry.helper_meshes[0].metadata["steps"] == 5


def test_t2624_composition_rejects_invalid_stairs_walkmesh_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, StairsPrimitive

    composition = AuthoredRoomComposition(
        room_resref="bad_stairs",
        floor=FloorPrimitive(name="bad_stairs_floor"),
        primitives=(StairsPrimitive(name="bad_stairs_path", surface_id="non_walk"),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "bad_stairs_path stairs surface 7 (NON_WALK) is not walkable." in validation.blocking_issues


def test_t2624_composition_adds_rectangular_door_frame_without_wok_faces() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, compile_authored_room_composition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import DoorFramePrimitive, FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="door_room",
        floor=FloorPrimitive(name="door_room_floor", width=8.0, depth=8.0),
        primitives=(
            DoorFramePrimitive(
                name="door_room_frame",
                width=2.4,
                height=3.2,
                jamb_width=0.25,
                lintel_height=0.3,
                depth=0.35,
            ),
        ),
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.metadata["walkmesh_primitive_count"] == 0
    assert geometry.wok.walkable_face_count() == 2
    frame_mesh = geometry.helper_meshes[0]
    assert frame_mesh.name == "door_room_frame"
    assert frame_mesh.metadata["primitive"] == "door_frame"
    assert frame_mesh.metadata["opening_width"] == 1.9
    assert round(frame_mesh.metadata["opening_height"], 6) == 2.9
    assert len(frame_mesh.vertices) == 24
    assert len(frame_mesh.faces) == 36


def test_t2624_composition_rejects_collapsed_door_frame_opening() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import DoorFramePrimitive, FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="bad_door_frame",
        floor=FloorPrimitive(name="bad_door_frame_floor"),
        primitives=(DoorFramePrimitive(name="bad_door_frame", width=1.0, jamb_width=0.5),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "Door frame primitive bad_door_frame must leave a positive doorway opening width." in validation.blocking_issues


def test_t2637_composition_transforms_placed_ramp_mesh_and_wok_together() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import (
        AuthoredRoomComposition,
        PlacedRoomPrimitive,
        PrimitiveTransform,
        compile_authored_room_composition,
        validate_authored_room_composition,
    )
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive

    composition = AuthoredRoomComposition(
        room_resref="move_ramp",
        floor=FloorPrimitive(name="move_ramp_floor", width=8.0, depth=8.0, z=0.5),
        primitives=(
            PlacedRoomPrimitive(
                primitive=RampPrimitive(
                    name="move_ramp_slope",
                    width=2.0,
                    length=2.0,
                    height=1.0,
                    surface_id="metal",
                ),
                transform=PrimitiveTransform(
                    translation=(5.0, 0.0, 0.5),
                    rotation_degrees_z=-90.0,
                ),
            ),
        ),
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.metadata["transformed_primitive_count"] == 1
    assert geometry.metadata["walkmesh_primitive_count"] == 1
    ramp_mesh = geometry.helper_meshes[0]
    assert ramp_mesh.name == "move_ramp_slope"
    assert ramp_mesh.metadata["transform"]["translation"] == [5.0, 0.0, 0.5]
    assert ramp_mesh.metadata["transform"]["rotation_degrees_z"] == -90.0
    assert _rounded_points(ramp_mesh.vertices[:4]) == [
        (4.0, 1.0, 0.5),
        (4.0, -1.0, 0.5),
        (6.0, -1.0, 1.5),
        (6.0, 1.0, 1.5),
    ]
    assert {(4.0, 1.0, 0.5), (4.0, -1.0, 0.5), (6.0, -1.0, 1.5), (6.0, 1.0, 1.5)} <= set(
        _rounded_points(geometry.wok.verts)
    )
    assert [face.surface for face in geometry.wok.faces] == [4, 4, 4, 4, 10, 10]
    assert _walkable_component_count(geometry.wok) == 1


def test_t2637_composition_rejects_invalid_placed_primitive_scale() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import (
        AuthoredRoomComposition,
        PlacedRoomPrimitive,
        PrimitiveTransform,
        validate_authored_room_composition,
    )
    from src.core.modules.authored_room_primitives import FloorPrimitive, RampPrimitive

    composition = AuthoredRoomComposition(
        room_resref="bad_scale",
        floor=FloorPrimitive(name="bad_scale_floor"),
        primitives=(
            PlacedRoomPrimitive(
                primitive=RampPrimitive(name="bad_scale_ramp"),
                transform=PrimitiveTransform(scale=(0.0, 1.0, 1.0)),
            ),
        ),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "Placed primitive bad_scale_ramp must have positive transform scale." in validation.blocking_issues


def test_t2637_non_uniform_placed_scale_uses_inverse_transpose_normals() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import PrimitiveTransform, transform_primitive_mesh
    from src.core.modules.authored_room_geometry import PrimitiveMesh

    mesh = PrimitiveMesh(
        name="normal_probe",
        vertices=((0.0, 0.0, 0.0),),
        faces=(),
        normals=((2.0 ** -0.5, 0.0, 2.0 ** -0.5),),
    )

    transformed = transform_primitive_mesh(
        mesh,
        PrimitiveTransform(scale=(2.0, 1.0, 0.5), rotation_degrees_z=90.0),
    )

    assert transformed.normals[0] == pytest.approx((0.0, 0.242535625, 0.9701425), abs=1.0e-7)


def test_t2622_composition_compiles_arch_primitive_as_helper_mesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, compile_authored_room_composition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import ArchPrimitive, FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="arch_room",
        floor=FloorPrimitive(name="arch_room_floor"),
        primitives=(ArchPrimitive(name="arch_room_entry", width=2.5, height=3.0, frame_thickness=0.3, depth=0.35),),
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.metadata["primitive_count"] == 1
    assert geometry.metadata["walkmesh_primitive_count"] == 0
    assert geometry.wok.walkable_face_count() == 2
    assert len(geometry.helper_meshes) == 1
    assert geometry.helper_meshes[0].name == "arch_room_entry"
    assert geometry.helper_meshes[0].metadata["primitive"] == "arch"


def test_t2622_composition_rejects_invalid_arch_dimensions() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import ArchPrimitive, FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="bad_arch",
        floor=FloorPrimitive(name="bad_arch_floor"),
        primitives=(ArchPrimitive(name="bad_arch_entry", width=0.0),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "Arch primitive bad_arch_entry must have positive width, height, depth, and frame thickness." in validation.blocking_issues


def _rounded_points(points: object) -> list[tuple[float, float, float]]:
    return [
        (round(float(point[0]), 6), round(float(point[1]), 6), round(float(point[2]), 6))
        for point in points
    ]


def _walkable_component_count(wok: object) -> int:
    from src.core.modules.module_format import WALKABLE_IDS

    wok.rebuild_adjacencies()
    remaining = {index for index, face in enumerate(wok.faces) if face.surface in WALKABLE_IDS}
    components = 0
    while remaining:
        components += 1
        pending = [remaining.pop()]
        while pending:
            face = wok.faces[pending.pop()]
            for adjacent in (face.adj1, face.adj2, face.adj3):
                if adjacent in remaining:
                    remaining.remove(adjacent)
                    pending.append(adjacent)
    return components
