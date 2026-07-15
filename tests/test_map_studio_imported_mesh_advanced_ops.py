"""Focused contracts for Map Studio's baked Maya-style mesh operators."""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for source in (
    ROOT / "native" / "GhostRigger.Core.Math" / "Python" / "src",
    ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    bend_imported_mesh_vertices,
    bridge_imported_mesh_border_edges,
    imported_mesh_primitive_from_payload,
    imported_mesh_primitive_payload,
    lattice_deform_imported_mesh_vertices,
    mirror_imported_mesh_geometry,
    shrink_wrap_imported_mesh_vertices,
    wrap_deform_imported_mesh_vertices,
)


def _surface(
    vertices: tuple[tuple[float, float, float], ...],
    faces: tuple[tuple[int, int, int], ...],
    *,
    name: str = "mesh",
    face_mats: tuple[int, ...] | None = None,
    normal: tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> ImportedMeshSurface:
    return ImportedMeshSurface(
        name=name,
        texture="lda_floor01",
        vertices=vertices,
        faces=faces,
        face_mats=face_mats if face_mats is not None else tuple(7 for _ in faces),
        uvs=tuple((index * 0.125, index * 0.25) for index in range(len(vertices))),
        normals=tuple(normal for _ in vertices),
        lightmap="lda_floor01lm",
        uvs_lm=tuple((0.05 + index * 0.05, 0.95 - index * 0.05) for index in range(len(vertices))),
    )


def _primitive(surface: ImportedMeshSurface) -> ImportedMeshRoomPrimitive:
    return ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(surface,), game="K2")


def _assert_aligned(surface: ImportedMeshSurface) -> None:
    assert len(surface.uvs) == len(surface.vertices)
    assert len(surface.normals) == len(surface.vertices)
    assert len(surface.uvs_lm) == len(surface.vertices)
    assert len(surface.face_mats) == len(surface.faces)


def test_mirror_replace_reverses_winding_and_reflects_normals_without_losing_channels() -> None:
    source = _surface(
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        ((0, 1, 2),),
        face_mats=(11,),
    )
    result = mirror_imported_mesh_geometry(_primitive(source), axis="x", center=0.0, duplicate=False)
    mirrored = result.surfaces[0]

    assert mirrored.vertices == ((-1.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-1.0, 1.0, 0.0))
    assert mirrored.faces == ((0, 2, 1),)
    assert mirrored.normals == ((-1.0, 0.0, 0.0),) * 3
    assert mirrored.uvs == source.uvs
    assert mirrored.uvs_lm == source.uvs_lm
    assert mirrored.face_mats == (11,)
    assert result.metadata["last_topology_edit"]["walkmesh_policy"] == "requires_review"


def test_mirror_duplicate_merges_only_vertices_on_the_explicit_plane() -> None:
    source = _surface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        normal=(0.0, 0.0, 1.0),
    )
    mirrored = mirror_imported_mesh_geometry(
        _primitive(source), axis="x", center=0.0, duplicate=True, merge_seam_tolerance=1.0e-6
    ).surfaces[0]

    assert len(mirrored.vertices) == 4
    assert len(mirrored.faces) == 2
    assert (-1.0, 0.0, 0.0) in mirrored.vertices
    _assert_aligned(mirrored)


def test_bridge_border_edges_adds_a_material_preserving_deterministic_quad() -> None:
    source = _surface(
        (
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
        ),
        ((0, 1, 2), (3, 4, 5)),
        face_mats=(13, 17),
    )
    result = bridge_imported_mesh_border_edges(_primitive(source), "render", (0, 1), (3, 4))
    bridged = result.surfaces[0]

    assert len(bridged.vertices) == 10
    assert len(bridged.faces) == 4
    assert bridged.face_mats == (13, 17, 13, 13)
    assert result.metadata["last_topology_edit"]["generated_face_count"] == 2
    _assert_aligned(bridged)


def test_bridge_divisions_taper_and_twist_create_real_channel_complete_strip() -> None:
    source = _surface(
        (
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (3.0, 1.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
        ),
        ((0, 1, 2), (3, 4, 5)),
        face_mats=(13, 17),
    )

    result = bridge_imported_mesh_border_edges(
        _primitive(source),
        "render",
        (0, 1),
        (3, 4),
        divisions=3,
        taper=0.35,
        twist_degrees=25.0,
        smooth=False,
    )
    bridged = result.surfaces[0]
    edit = result.metadata["last_topology_edit"]

    assert len(bridged.vertices) == len(source.vertices) + 10
    assert len(bridged.faces) == len(source.faces) + 8
    assert bridged.face_mats[-8:] == (13,) * 8
    assert edit["divisions"] == 3
    assert edit["taper"] == 0.35
    assert edit["twist_degrees"] == 25.0
    assert edit["smooth"] is False
    # The envelope preserves both selected border rows exactly while the
    # intermediate rows are genuinely deformed rather than metadata-only.
    assert bridged.vertices[-10:-8] == ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0))
    assert set(bridged.vertices[-2:]) == {(3.0, 0.0, 0.0), (3.0, 1.0, 0.0)}
    assert any(abs(point[2]) > 1.0e-6 for point in bridged.vertices[-8:-2])
    _assert_aligned(bridged)


def test_bend_is_bounded_static_and_keeps_vertex_channels_aligned() -> None:
    source = _surface(
        ((0.0, -1.0, 0.0), (2.0, -1.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
    )
    result = bend_imported_mesh_vertices(
        _primitive(source), "render", axis="x", curvature_degrees=90.0, lower_bound=0.0, upper_bound=2.0
    )
    bent = result.surfaces[0]

    assert bent.vertices != source.vertices
    assert bent.uvs == source.uvs
    assert bent.uvs_lm == source.uvs_lm
    assert all(math.isclose(math.sqrt(sum(value * value for value in normal)), 1.0) for normal in bent.normals)
    assert result.metadata["last_topology_edit"]["normal_policy"] == "analytic_jacobian_inverse_transpose"
    _assert_aligned(bent)


def test_uniform_lattice_delta_moves_geometry_rigidly_and_preserves_attributes() -> None:
    vertices = (
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
    )
    source = _surface(vertices, ((0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6)))
    result = lattice_deform_imported_mesh_vertices(
        _primitive(source),
        "render",
        control_deltas=((0.0, 0.0, 2.0),) * 8,
        bounds_min=(0.0, 0.0, 0.0),
        bounds_max=(1.0, 1.0, 1.0),
    )
    deformed = result.surfaces[0]

    assert deformed.vertices == tuple((x, y, z + 2.0) for x, y, z in source.vertices)
    assert deformed.uvs == source.uvs
    assert deformed.uvs_lm == source.uvs_lm
    assert deformed.normals == source.normals
    assert result.metadata["last_topology_edit"]["interpolation"] == "trilinear_2x2x2"
    _assert_aligned(deformed)


def test_lattice_pads_a_flat_plane_instead_of_rejecting_common_map_geometry() -> None:
    source = _surface(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)), ((0, 1, 2),))
    result = lattice_deform_imported_mesh_vertices(
        _primitive(source),
        "render",
        control_deltas=((0.0, 0.0, 0.25),) * 8,
    )

    assert all(math.isclose(vertex[2], 0.25) for vertex in result.surfaces[0].vertices)
    assert result.metadata["last_topology_edit"]["padded_flat_axes"] == ["z"]


def test_shrink_wrap_projects_to_nearest_triangle_and_can_align_normals() -> None:
    source = _surface(((0.25, 0.25, 0.0), (1.0, 0.25, 0.0), (0.25, 1.0, 0.0)), ((0, 1, 2),))
    target = ImportedMeshSurface(
        name="live_ground",
        texture="ground",
        vertices=((0.0, 0.0, 2.0), (2.0, 0.0, 2.0), (0.0, 2.0, 2.0)),
        faces=((0, 1, 2),),
        normals=((0.0, 0.0, 1.0),) * 3,
    )
    result = shrink_wrap_imported_mesh_vertices(
        _primitive(source), "render", target, projection="nearest_triangle", align_normals=True
    )
    wrapped = result.surfaces[0]

    assert all(math.isclose(vertex[2], 2.0) for vertex in wrapped.vertices)
    assert wrapped.normals == ((0.0, 0.0, 1.0),) * 3
    assert wrapped.uvs == source.uvs
    assert wrapped.uvs_lm == source.uvs_lm
    _assert_aligned(wrapped)


def test_wrap_bakes_driver_vertex_deltas_without_persisting_a_dependency() -> None:
    source = _surface(((0.25, 0.25, 0.0), (1.0, 0.25, 0.0), (0.25, 1.0, 0.0)), ((0, 1, 2),))
    driver_base = ImportedMeshSurface(
        name="driver_base",
        texture="driver",
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        faces=((0, 1, 2),),
    )
    driver_deformed = ImportedMeshSurface(
        name="driver_deformed",
        texture="driver",
        vertices=((0.0, 0.0, 1.5), (2.0, 0.0, 1.5), (0.0, 2.0, 1.5)),
        faces=((0, 1, 2),),
    )
    result = wrap_deform_imported_mesh_vertices(
        _primitive(source), "render", driver_base, driver_deformed, nearest_count=3
    )
    wrapped = result.surfaces[0]

    assert all(math.isclose(vertex[2], 1.5) for vertex in wrapped.vertices)
    assert wrapped.uvs == source.uvs
    assert wrapped.uvs_lm == source.uvs_lm
    assert result.metadata["last_topology_edit"]["dependency_policy"] == "baked_no_live_driver_graph"
    _assert_aligned(wrapped)

    restored = imported_mesh_primitive_from_payload(imported_mesh_primitive_payload(result), result.room_resref)
    assert restored.metadata["last_topology_edit"] == result.metadata["last_topology_edit"]
    assert restored.surfaces[0].faces == result.surfaces[0].faces
