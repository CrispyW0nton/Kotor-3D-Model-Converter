from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Modules/Python",
        "native/GhostRigger.Core.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Walkmesh/Python",
        "native/GhostRigger.Core.Geometry/Python",
        "native/GhostRigger.Core.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2602_builds_floor_mesh_and_walkmesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import FloorPrimitive, PrimitiveMaterial, build_floor_mesh, build_floor_wok

    primitive = FloorPrimitive(
        name="floor_a",
        width=6.0,
        depth=4.0,
        surface_id=4,
        material=PrimitiveMaterial(texture="metal_floor"),
    )

    mesh = build_floor_mesh(primitive)
    wok = build_floor_wok(primitive)

    assert mesh.name == "floor_a"
    assert mesh.texture == "metal_floor"
    assert mesh.metadata["primitive"] == "floor"
    assert mesh.metadata["surface_id"] == 4
    assert mesh.vertices == ((-3.0, -2.0, 0.0), (3.0, -2.0, 0.0), (3.0, 2.0, 0.0), (-3.0, 2.0, 0.0))
    assert mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert wok.walkable_face_count() == 2
    assert [face.surface for face in wok.faces] == [4, 4]


def test_t2604_floor_primitive_accepts_named_walkmesh_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import FloorPrimitive, build_floor_mesh, build_floor_wok

    primitive = FloorPrimitive(name="metal_floor", width=2.0, depth=2.0, surface_id="metal")

    mesh = build_floor_mesh(primitive)
    wok = build_floor_wok(primitive)

    assert mesh.metadata["surface_id"] == 10
    assert mesh.metadata["surface_name"] == "METAL"
    assert [face.surface for face in wok.faces] == [10, 10]


def test_t2602_builds_wall_cube_ramp_and_stairs_meshes() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import (
        ArchPrimitive,
        CubePrimitive,
        RampPrimitive,
        StairsPrimitive,
        WallPrimitive,
        build_arch_mesh,
        build_cube_mesh,
        build_ramp_mesh,
        build_ramp_wok,
        build_stairs_mesh,
        build_stairs_wok,
        build_wall_mesh,
    )

    arch = build_arch_mesh(ArchPrimitive(name="door_arch", width=2.0, height=3.0, frame_thickness=0.25, depth=0.4, segments=8))
    wall = build_wall_mesh(WallPrimitive(name="wall_y", axis="y", width=5.0, height=2.5, thickness=0.25))
    cube = build_cube_mesh(CubePrimitive(name="crate", size=(1.0, 2.0, 3.0), center=(0.0, 0.0, 1.5)))
    ramp_primitive = RampPrimitive(name="ramp", width=2.0, length=4.0, height=1.25, center=(1.0, 2.0, 0.25), surface_id="metal")
    ramp = build_ramp_mesh(ramp_primitive)
    ramp_wok = build_ramp_wok(ramp_primitive)
    stairs_primitive = StairsPrimitive(name="stairs", width=2.0, depth=4.0, height=1.0, steps=4, surface_id="stone")
    stairs = build_stairs_mesh(stairs_primitive)
    stairs_wok = build_stairs_wok(stairs_primitive)

    assert arch.metadata["primitive"] == "arch"
    assert arch.metadata["segments"] == 8
    assert arch.metadata["opening_width"] == 1.5
    assert arch.metadata["opening_height"] == 2.0
    assert len(arch.vertices) == 52
    assert len(arch.faces) == 92
    assert min(vertex[2] for vertex in arch.vertices) == 0.0
    assert max(vertex[2] for vertex in arch.vertices) == 3.0
    assert wall.metadata["primitive"] == "wall"
    assert len(wall.vertices) == 8
    assert len(wall.faces) == 12
    assert cube.metadata["primitive"] == "cube"
    assert min(vertex[2] for vertex in cube.vertices) == 0.0
    assert max(vertex[2] for vertex in cube.vertices) == 3.0
    assert ramp.metadata["primitive"] == "ramp"
    assert ramp.metadata["surface_id"] == 10
    assert min(vertex[0] for vertex in ramp.vertices) == 0.0
    assert max(vertex[2] for vertex in ramp.vertices) == 1.5
    assert ramp_wok.walkable_face_count() == 2
    assert [face.surface for face in ramp_wok.faces] == [10, 10]
    assert ramp_wok.verts == list(ramp.vertices[:4])
    assert stairs.metadata["primitive"] == "stairs"
    assert stairs.metadata["steps"] == 4
    assert stairs.metadata["surface_id"] == 4
    assert len(stairs.faces) == 48
    assert stairs_wok.walkable_face_count() == 2
    assert stairs_wok.verts == [(-1.0, -2.0, 0.0), (1.0, -2.0, 0.0), (1.0, 2.0, 1.0), (-1.0, 2.0, 1.0)]
    assert [face.surface for face in stairs_wok.faces] == [4, 4]


def test_t2602_builds_segmented_cylinder_mesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_primitives import CylinderPrimitive, build_cylinder_mesh

    cylinder = build_cylinder_mesh(CylinderPrimitive(name="column", radius=0.5, height=2.0, segments=8))
    clamped = build_cylinder_mesh(CylinderPrimitive(name="lowpoly", segments=1))

    assert cylinder.metadata["primitive"] == "cylinder"
    assert cylinder.metadata["segments"] == 8
    assert len(cylinder.vertices) == 18
    assert len(cylinder.faces) == 32
    assert min(vertex[2] for vertex in cylinder.vertices) == -0.5
    assert max(vertex[2] for vertex in cylinder.vertices) == 1.5
    assert clamped.metadata["segments"] == 3
    assert len(clamped.faces) == 12
