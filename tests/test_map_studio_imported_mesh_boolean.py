"""Focused Scene adapter tests for closed-solid Map Studio Difference A-B."""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
for rel in reversed(
    (
        "native/GhostRigger.Core.Math/Python/src",
        "native/GhostRigger.Core.Scene/Python/src",
        ".",
    )
):
    path = str((ROOT / rel).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)

from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    boolean_difference_imported_mesh_surfaces,
    imported_mesh_primitive_from_payload,
    imported_mesh_primitive_payload,
)


_CUBE_FACES = (
    (0, 2, 1), (0, 3, 2),
    (4, 5, 6), (4, 6, 7),
    (0, 1, 5), (0, 5, 4),
    (3, 7, 6), (3, 6, 2),
    (0, 4, 7), (0, 7, 3),
    (1, 2, 6), (1, 6, 5),
)


def _cube_surface(name: str, texture: str, size: float, material: int) -> ImportedMeshSurface:
    half = size * 0.5
    vertices = tuple(
        (x * half, y * half, z * half)
        for x, y, z in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        )
    )
    normals = tuple(
        tuple(value / math.sqrt(3.0) for value in (x, y, z))
        for x, y, z in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        )
    )
    return ImportedMeshSurface(
        name=name,
        texture=texture,
        vertices=vertices,
        faces=_CUBE_FACES,
        uvs=tuple(((x / size) + 0.5, (z / size) + 0.5) for x, _y, z in vertices),
        normals=normals,
        lightmap=f"{texture}lm",
        texture_names=(texture, f"{texture}lm"),
        tex_count=2,
        uvs_lm=tuple(((x / size) + 0.5, (y / size) + 0.5) for x, y, _z in vertices),
        face_mats=(material,) * len(_CUBE_FACES),
    )


def test_closed_imported_surface_difference_preserves_material_nodes_and_round_trips_kmap() -> None:
    pytest.importorskip("manifold3d")
    primitive = ImportedMeshRoomPrimitive(
        room_resref="gr_bool",
        game="K2",
        surfaces=(
            _cube_surface("target", "target_tex", 2.0, 4),
            _cube_surface("cutter", "cutter_tex", 1.0, 9),
        ),
    )

    result = boolean_difference_imported_mesh_surfaces(primitive, "render", "imported_srf_1")
    edit = result.metadata["last_topology_edit"]

    assert primitive.surfaces[0].name == "target"
    assert edit["operation"] == "boolean_difference_closed_solids"
    assert edit["output_volume"] == pytest.approx(7.0)
    assert edit["topology_contract"] == "closed_oriented_two_manifold_only"
    assert edit["lightmap_policy"] == "stale_requires_bake"
    assert {surface.texture for surface in result.surfaces} == {"target_tex", "cutter_tex"}
    assert all(surface.lightmap == "" for surface in result.surfaces)
    assert all(len(surface.vertices) == len(surface.uvs) == len(surface.normals) for surface in result.surfaces)
    assert all(len(surface.faces) == len(surface.face_mats) for surface in result.surfaces)

    payload = imported_mesh_primitive_payload(result)
    restored = imported_mesh_primitive_from_payload(payload, "gr_bool")
    assert imported_mesh_primitive_payload(restored) == payload
    assert restored.metadata == result.metadata


def test_open_imported_surface_difference_is_refused_without_mutating_source() -> None:
    target = _cube_surface("target", "target_tex", 2.0, 4)
    closed_cutter = _cube_surface("cutter", "cutter_tex", 1.0, 9)
    open_cutter = replace(closed_cutter, faces=closed_cutter.faces[:-1], face_mats=closed_cutter.face_mats[:-1])
    primitive = ImportedMeshRoomPrimitive(room_resref="gr_bool", surfaces=(target, open_cutter))

    with pytest.raises(ValueError, match="closed|border|watertight|manifold"):
        boolean_difference_imported_mesh_surfaces(primitive, "render", "imported_srf_1")

    assert primitive.surfaces == (target, open_cutter)
