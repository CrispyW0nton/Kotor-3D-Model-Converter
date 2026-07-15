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
    bevel_imported_mesh_edge,
    delete_imported_mesh_faces,
    extrude_imported_mesh_faces,
    inset_imported_mesh_faces,
    move_imported_mesh_faces,
    resolve_imported_mesh_face_target,
    split_imported_mesh_edge,
    split_imported_mesh_face,
    validate_imported_mesh_room_primitive,
)


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
