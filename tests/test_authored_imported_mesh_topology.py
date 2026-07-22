"""Attribute/remap regressions for Map Studio's shared topology path."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for source in (
    ROOT / "native" / "GhostRigger.Core.Math" / "Python" / "src",
    ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from core.geometry.mesh_topology import MeshTopology  # noqa: E402
from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    append_imported_mesh_quad,
    bevel_imported_mesh_edge,
    delete_imported_mesh_faces,
    extrude_imported_mesh_faces,
    inset_imported_mesh_faces,
    make_hole_in_imported_mesh_face,
    move_imported_mesh_faces,
    resolve_imported_mesh_face_target,
    split_imported_mesh_edge,
    split_imported_mesh_face,
    validate_imported_mesh_room_primitive,
)
import core.modules.authored_imported_mesh as authored_imported_mesh  # noqa: E402


def _lightmapped_cube() -> ImportedMeshRoomPrimitive:
    vertices = (
        (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0),
        (0.0, 0.0, 3.0), (4.0, 0.0, 3.0), (4.0, 4.0, 3.0), (0.0, 4.0, 3.0),
    )
    faces = (
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    )
    uvs = tuple((float(index) + 0.125, float(index) + 0.625) for index in range(len(vertices)))
    uvs_lm = tuple((0.05 + (index * 0.1), 0.95 - (index * 0.1)) for index in range(len(vertices)))
    surface = ImportedMeshSurface(
        name="cube",
        texture="lda_wall01",
        vertices=vertices,
        faces=faces,
        uvs=uvs,
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        lightmap="lda_wall01lm",
        texture_names=("lda_wall01", "lda_wall01lm"),
        tex_count=2,
        uvs_lm=uvs_lm,
    )
    return ImportedMeshRoomPrimitive(room_resref="grtopo", surfaces=(surface,), game="K2")


def _assert_channels_aligned(primitive: ImportedMeshRoomPrimitive) -> None:
    for surface in primitive.surfaces:
        assert len(surface.uvs) == len(surface.vertices)
        assert len(surface.normals) == len(surface.vertices)
        assert len(surface.uvs_lm) == len(surface.vertices)
        if surface.face_mats:
            assert len(surface.face_mats) == len(surface.faces)


def test_repeated_validation_reuses_same_immutable_primitive_topology(monkeypatch) -> None:
    primitive = _lightmapped_cube()
    authored_imported_mesh._IMPORTED_MESH_VALIDATION_CACHE.pop(id(primitive), None)
    topology_type = authored_imported_mesh.MeshTopology
    original_build = topology_type.build.__func__
    build_calls = 0

    def counted_build(cls, *args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return original_build(cls, *args, **kwargs)

    monkeypatch.setattr(topology_type, "build", classmethod(counted_build))

    first = validate_imported_mesh_room_primitive(primitive)
    second = validate_imported_mesh_room_primitive(primitive)

    assert first is second
    assert build_calls == len(primitive.surfaces)


def test_many_disconnected_raw_seam_boundaries_keep_deterministic_order() -> None:
    """Heap-backed chain starts retain the historical minimum-edge order."""

    island_count = 4_096
    vertices = tuple(
        point
        for island in range(island_count)
        for point in (
            (float(island * 2), 0.0, 0.0),
            (float(island * 2 + 1), 0.0, 0.0),
            (float(island * 2), 1.0, 0.0),
        )
    )
    faces = tuple(
        (base, base + 1, base + 2)
        for base in range(0, island_count * 3, 3)
    )

    topology = authored_imported_mesh.MeshTopology.build(vertices, faces)

    assert len(topology.border_loops) == island_count
    assert topology.border_loops[0] == [0, 1, 2, 0]
    last = (island_count - 1) * 3
    assert topology.border_loops[-1] == [last, last + 1, last + 2, last]


def test_generated_topology_preserves_face_material_slots() -> None:
    primitive = _lightmapped_cube()
    source_mats = (7, 7, 9, 9, 5, 5, 3, 3, 1, 1, 4, 4)
    primitive = replace(
        primitive,
        surfaces=(replace(primitive.surfaces[0], face_mats=source_mats),),
    )

    extruded = extrude_imported_mesh_faces(primitive, "render", (0,), 0.5).surfaces[0]
    inset = inset_imported_mesh_faces(primitive, "render", (0,), 0.25).surfaces[0]
    bevelled = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.25).surfaces[0]

    assert len(extruded.face_mats) == len(extruded.faces)
    assert extruded.face_mats[:11] == source_mats[1:]
    assert set(extruded.face_mats[11:]) == {7}
    assert len(inset.face_mats) == len(inset.faces)
    assert inset.face_mats[:11] == source_mats[1:]
    assert set(inset.face_mats[11:]) == {7}
    assert bevelled.face_mats[: len(source_mats)] == source_mats
    assert set(bevelled.face_mats[len(source_mats):]) == {7}


def test_face_target_scope_distinguishes_material_region_texture_and_room_island() -> None:
    primitive = _lightmapped_cube()
    source_mats = (7, 7, 9, 9, 7, 9, 3, 9, 1, 1, 7, 4)
    primitive = replace(
        primitive,
        surfaces=(replace(primitive.surfaces[0], face_mats=source_mats),),
    )

    assert resolve_imported_mesh_face_target(primitive, "render", 0, "Single Face") == (0,)
    assert resolve_imported_mesh_face_target(primitive, "render", 0, "Material Region") == (0, 1)
    assert resolve_imported_mesh_face_target(primitive, "render", 0, "Same Texture Faces") == (0, 1, 4, 10)
    assert resolve_imported_mesh_face_target(primitive, "render", 0, "Room Island") == tuple(range(12))


def test_face_move_keeps_uv_and_material_seam_copies_welded() -> None:
    surface = ImportedMeshSurface(
        name="seamed_quad",
        texture="lda_floor01",
        vertices=(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),  # UV/material seam copy of raw vertex 0.
            (1.0, 1.0, 0.0),  # UV/material seam copy of raw vertex 2.
            (0.0, 1.0, 0.0),
        ),
        faces=((0, 1, 2), (3, 4, 5)),
        face_mats=(3, 7),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.25, 0.0), (0.75, 1.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 6,
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grseam", surfaces=(surface,))

    moved = move_imported_mesh_faces(primitive, "render", (0,), (0.0, 0.0, 2.0)).surfaces[0]

    assert moved.vertices[0] == moved.vertices[3] == (0.0, 0.0, 2.0)
    assert moved.vertices[2] == moved.vertices[4] == (1.0, 1.0, 2.0)
    assert moved.vertices[5] == (0.0, 1.0, 0.0)
    assert moved.uvs == surface.uvs
    assert moved.face_mats == surface.face_mats


def test_compacting_and_generated_edits_keep_lightmap_uvs_aligned() -> None:
    primitive = _lightmapped_cube()
    edits = (
        delete_imported_mesh_faces(primitive, "render", (2,)),
        extrude_imported_mesh_faces(primitive, "render", (0,), 0.5),
        inset_imported_mesh_faces(primitive, "render", (0,), 0.25),
        split_imported_mesh_edge(primitive, "render", 0, (0, 2)),
        split_imported_mesh_face(primitive, "render", 0),
        bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.25),
    )
    for edited in edits:
        _assert_channels_aligned(edited)


def test_multi_segment_bevel_preserves_unrelated_attributes_and_is_manifold() -> None:
    primitive = _lightmapped_cube()
    original = primitive.surfaces[0]
    bevelled = bevel_imported_mesh_edge(
        primitive,
        "render",
        0,
        (0, 1),
        0.35,
        segments=4,
        profile=1.0,
        smoothing_angle_degrees=180.0,
        uv_mode="preserve",
    )
    surface = bevelled.surfaces[0]

    _assert_channels_aligned(bevelled)
    # Ceiling face 2 is unrelated to the selected floor/wall edge and keeps
    # its exact topology and artist-authored UV/lightmap coordinates.
    assert surface.faces[2] == original.faces[2]
    assert tuple(surface.uvs[index] for index in surface.faces[2]) == tuple(
        original.uvs[index] for index in original.faces[2]
    )
    assert tuple(surface.uvs_lm[index] for index in surface.faces[2]) == tuple(
        original.uvs_lm[index] for index in original.faces[2]
    )
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    operator = bevelled.metadata["last_topology_edit"]
    assert operator["segments"] == 4
    assert operator["profile"] == 1.0
    assert operator["uv_mode"] == "preserve"
    assert operator["walkmesh_policy"] == "requires_review"


def test_bevel_profile_changes_the_generated_track_without_accumulation() -> None:
    primitive = _lightmapped_cube()
    linear = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.3, segments=4, profile=0.0)
    rounded = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.3, segments=4, profile=1.0)
    assert linear.surfaces[0].vertices != rounded.surfaces[0].vertices
    # Both evaluations start from the same immutable source topology.
    assert primitive.surfaces[0].faces == _lightmapped_cube().surfaces[0].faces


def test_bevel_miter_modes_and_smoothing_change_real_mesh_channels() -> None:
    primitive = _lightmapped_cube()
    sharp = bevel_imported_mesh_edge(
        primitive,
        "render",
        0,
        (0, 1),
        0.3,
        segments=3,
        miter="sharp",
        smoothing_angle_degrees=180.0,
    )
    patch = bevel_imported_mesh_edge(
        primitive,
        "render",
        0,
        (0, 1),
        0.3,
        segments=3,
        miter="patch",
        smoothing_angle_degrees=180.0,
    )
    hard = bevel_imported_mesh_edge(
        primitive,
        "render",
        0,
        (0, 1),
        0.3,
        segments=3,
        miter="sharp",
        smoothing_angle_degrees=0.0,
    )

    assert sharp.surfaces[0].vertices != patch.surfaces[0].vertices
    assert sharp.metadata["last_topology_edit"]["resolved_miter"] == "sharp"
    assert patch.metadata["last_topology_edit"]["resolved_miter"] == "patch"
    assert sharp.metadata["last_topology_edit"]["smooth_strip"] is True
    assert hard.metadata["last_topology_edit"]["smooth_strip"] is False
    assert len(hard.surfaces[0].vertices) > len(sharp.surfaces[0].vertices)
    for edited in (sharp, patch, hard):
        _assert_channels_aligned(edited)
        audit = MeshTopology.build(edited.surfaces[0].vertices, edited.surfaces[0].faces).validate_manifold_state()
        assert not audit.degenerate_faces
        assert not audit.non_manifold_edges


def test_bevel_uv_modes_change_generated_uvs_without_touching_source_uvs() -> None:
    primitive = _lightmapped_cube()
    preserved = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.3, segments=2, uv_mode="preserve")
    tiled = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.3, segments=2, uv_mode="tiled")
    none = bevel_imported_mesh_edge(primitive, "render", 0, (0, 1), 0.3, segments=2, uv_mode="none")

    assert preserved.surfaces[0].uvs != tiled.surfaces[0].uvs
    generated_start = none.metadata["last_topology_edit"]["generated_face_start"]
    generated_indices = {
        index
        for face in none.surfaces[0].faces[generated_start:]
        for index in face
    }
    assert generated_indices
    assert all(none.surfaces[0].uvs[index] == (0.0, 0.0) for index in generated_indices)
    assert primitive.surfaces[0].uvs == _lightmapped_cube().surfaces[0].uvs


def test_region_extrude_welds_connectivity_across_uv_seam_copies() -> None:
    surface = ImportedMeshSurface(
        name="seamed_quad",
        texture="lda_floor01",
        vertices=(
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0),
            (0.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0),
        ),
        faces=((0, 1, 2), (3, 4, 5)),
        uvs=((0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)),
        normals=((0, 0, 1),) * 6,
        uvs_lm=((0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grseam", surfaces=(surface,))
    result = extrude_imported_mesh_faces(primitive, "render", (0, 1), 1.0)
    # 2 caps + four geometric boundary edges * two triangles. The duplicated
    # diagonal is internal and must not create two extra side walls.
    assert len(result.surfaces[0].faces) == 10
    _assert_channels_aligned(result)


def test_validation_rejects_misaligned_lightmap_uv_channel() -> None:
    primitive = _lightmapped_cube()
    broken = replace(
        primitive,
        surfaces=(replace(primitive.surfaces[0], uvs_lm=primitive.surfaces[0].uvs_lm[:-1]),),
    )
    validation = validate_imported_mesh_room_primitive(broken)
    assert not validation.ok
    assert any("lightmap UV count" in issue for issue in validation.blocking_issues)


def _lightmapped_triangle() -> ImportedMeshRoomPrimitive:
    surface = ImportedMeshSurface(
        name="triangle",
        texture="lda_floor01",
        vertices=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        faces=((0, 1, 2),),
        face_mats=(7,),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
        lightmap="lda_floor01lm",
        texture_names=("lda_floor01", "lda_floor01lm"),
        tex_count=2,
        uvs_lm=((0.1, 0.1), (0.9, 0.1), (0.1, 0.9)),
    )
    return ImportedMeshRoomPrimitive(room_resref="grhole", surfaces=(surface,), game="K2")


def _triangle_area(a, b, c) -> float:
    ab = tuple(b[index] - a[index] for index in range(3))
    ac = tuple(c[index] - a[index] for index in range(3))
    cross = (
        (ab[1] * ac[2]) - (ab[2] * ac[1]),
        (ab[2] * ac[0]) - (ab[0] * ac[2]),
        (ab[0] * ac[1]) - (ab[1] * ac[0]),
    )
    return 0.5 * sum(value * value for value in cross) ** 0.5


def test_make_hole_triangulates_a_strict_internal_cutter_and_interpolates_channels() -> None:
    primitive = _lightmapped_triangle()
    cutter = ((2.0, 2.0, 0.0), (3.0, 2.0, 0.0), (3.0, 3.0, 0.0), (2.0, 3.0, 0.0))

    edited = make_hole_in_imported_mesh_face(primitive, "render", 0, cutter)
    repeated = make_hole_in_imported_mesh_face(primitive, "render", 0, cutter)
    surface = edited.surfaces[0]
    topology = MeshTopology.build(surface.vertices, surface.faces)
    audit = topology.validate_manifold_state()

    assert len(surface.faces) == 7  # four-point hole in one triangular outer boundary
    assert surface.faces == repeated.surfaces[0].faces
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges
    assert len(audit.border_edges) == 7  # three outer edges plus four intentional hole edges
    assert surface.face_mats == (7,) * 7
    assert sum(
        _triangle_area(*(surface.vertices[index] for index in face))
        for face in surface.faces
    ) == 49.0
    inserted = surface.vertices.index((2.0, 2.0, 0.0))
    assert surface.uvs[inserted] == (0.2, 0.2)
    assert all(abs(value - 0.26) < 1.0e-9 for value in surface.uvs_lm[inserted])
    assert surface.normals[inserted] == (0.0, 0.0, 1.0)
    assert edited.metadata["last_topology_edit"]["operation"] == "make_hole"
    assert edited.metadata["last_topology_edit"]["scope_limit"] == "strictly_inside_one_triangle"
    assert edited.metadata["last_topology_edit"]["walkmesh_policy"] == "requires_review"
    _assert_channels_aligned(edited)


def test_make_hole_uses_and_removes_the_second_selected_face_like_maya() -> None:
    primitive = _lightmapped_triangle()
    surface = primitive.surfaces[0]
    with_cutter_face = replace(
        surface,
        vertices=surface.vertices + ((2.0, 2.0, 0.0), (3.0, 2.0, 0.0), (2.0, 3.0, 0.0)),
        faces=surface.faces + ((3, 4, 5),),
        face_mats=(7, 11),
        uvs=surface.uvs + ((0.2, 0.2), (0.3, 0.2), (0.2, 0.3)),
        normals=surface.normals + ((0.0, 0.0, 1.0),) * 3,
        uvs_lm=surface.uvs_lm + ((0.26, 0.26), (0.34, 0.26), (0.26, 0.34)),
    )
    primitive = replace(primitive, surfaces=(with_cutter_face,))

    edited = make_hole_in_imported_mesh_face(
        primitive,
        "render",
        0,
        cutter_face_index=1,
    )
    result = edited.surfaces[0]
    audit = MeshTopology.build(result.vertices, result.faces).validate_manifold_state()

    assert len(result.faces) == 6
    assert result.face_mats == (7,) * 6
    assert len(audit.border_edges) == 6
    assert sum(
        _triangle_area(*(result.vertices[index] for index in face))
        for face in result.faces
    ) == 49.5
    assert edited.metadata["last_topology_edit"]["cutter_face"] == 1
    assert edited.metadata["last_topology_edit"]["cutter_face_removed"] is True
    _assert_channels_aligned(edited)


def test_make_hole_rejects_cross_triangle_boundary_and_self_intersecting_cutters() -> None:
    primitive = _lightmapped_triangle()
    for cutter, expected in (
        (
            ((0.0, 2.0, 0.0), (1.0, 2.0, 0.0), (1.0, 3.0, 0.0)),
            "strictly inside one selected triangle",
        ),
        (
            ((2.0, 2.0, 0.0), (4.0, 4.0, 0.0), (2.0, 4.0, 0.0), (4.0, 2.0, 0.0)),
            "self-intersecting",
        ),
    ):
        try:
            make_hole_in_imported_mesh_face(primitive, "render", 0, cutter)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("an unsafe Make Hole cutter must be rejected explicitly")


def test_make_hole_supports_a_concave_cutter_without_filling_its_notch() -> None:
    primitive = _lightmapped_triangle()
    cutter = (
        (2.0, 2.0, 0.0),
        (4.0, 2.0, 0.0),
        (4.0, 4.0, 0.0),
        (3.0, 3.0, 0.0),
        (2.0, 4.0, 0.0),
    )

    edited = make_hole_in_imported_mesh_face(primitive, "render", 0, cutter)
    surface = edited.surfaces[0]
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()

    assert len(surface.faces) == 8
    assert len(audit.border_edges) == 8
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges
    assert sum(
        _triangle_area(*(surface.vertices[index] for index in face))
        for face in surface.faces
    ) == 47.0  # outer 50m^2 minus the concave cutter's 3m^2


def test_quad_draw_appends_two_wound_triangles_with_real_channels() -> None:
    primitive = _lightmapped_triangle()
    points = ((2.0, 2.0, 1.0), (3.0, 2.0, 1.0), (3.0, 3.0, 1.0), (2.0, 3.0, 1.0))

    edited = append_imported_mesh_quad(
        primitive,
        "render",
        points,
        material=11,
        normal_hint=(0.0, 0.0, -1.0),
    )
    surface = edited.surfaces[0]
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()

    assert len(surface.faces) == 3
    assert surface.face_mats == (7, 11, 11)
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    for face in surface.faces[-2:]:
        assert _triangle_area(*(surface.vertices[index] for index in face)) == 0.5
        a, b, c = (surface.vertices[index] for index in face)
        cross_z = ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))
        assert cross_z < 0.0
        assert all(surface.normals[index] == (0.0, 0.0, -1.0) for index in face)
    assert edited.metadata["last_topology_edit"]["operation"] == "quad_draw_append"
    assert edited.metadata["last_topology_edit"]["created_surface"] is False
    assert edited.metadata["last_topology_edit"]["lightmap_uv_policy"] == "planar_placeholder_requires_bake"
    assert edited.metadata["last_topology_edit"]["walkmesh_policy"] == "requires_review"
    _assert_channels_aligned(edited)


def test_quad_draw_auto_welds_neighboring_quads_into_one_connected_strip() -> None:
    primitive = _lightmapped_triangle()
    first = append_imported_mesh_quad(
        primitive,
        "imported_srf_1",
        ((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0)),
        texture="lda_floor01",
    )
    second = append_imported_mesh_quad(
        first,
        "imported_srf_1",
        ((1.0, 0.0, 1.0), (2.0, 0.0, 1.0), (2.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
        texture="lda_floor01",
        auto_weld=True,
        weld_tolerance=1.0e-5,
    )
    surface = second.surfaces[1]
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()

    assert len(surface.vertices) == 6
    assert len(surface.faces) == 4
    assert len(audit.border_edges) == 6
    assert not audit.non_manifold_edges
    assert second.metadata["last_topology_edit"]["reused_vertex_count"] == 2


def test_quad_draw_creates_a_new_retopology_surface_when_role_is_absent() -> None:
    primitive = _lightmapped_triangle()
    points = ((20.0, 0.0, 0.0), (22.0, 0.0, 0.0), (22.0, 2.0, 0.0), (20.0, 2.0, 0.0))

    edited = append_imported_mesh_quad(
        primitive,
        "retopo",
        points,
        material=5,
        texture="plc_concrete",
        lightmap="plc_concretelm",
    )
    retopo = edited.surfaces[1]

    assert len(edited.surfaces) == 2
    assert retopo.name == "retopo"
    assert retopo.texture == "plc_concrete"
    assert retopo.lightmap == "plc_concretelm"
    assert retopo.face_mats == (5, 5)
    assert len(retopo.faces) == 2
    assert len(retopo.uvs_lm) == 4
    assert edited.metadata["last_topology_edit"]["created_surface"] is True
    assert edited.metadata["last_topology_edit"]["requested_mesh_role"] == "retopo"
    assert edited.metadata["last_topology_edit"]["mesh_role"] == "imported_srf_1"
    _assert_channels_aligned(edited)


def test_quad_draw_rejects_bow_tie_and_non_planar_points() -> None:
    primitive = _lightmapped_triangle()
    for points, expected in (
        (
            ((2.0, 2.0, 1.0), (3.0, 3.0, 1.0), (2.0, 3.0, 1.0), (3.0, 2.0, 1.0)),
            "no stable plane",
        ),
        (
            ((2.0, 2.0, 1.0), (3.0, 2.0, 1.0), (3.0, 3.0, 1.5), (2.0, 3.0, 1.0)),
            "not planar",
        ),
    ):
        try:
            append_imported_mesh_quad(primitive, "render", points)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("an invalid Quad Draw polygon must be rejected")
