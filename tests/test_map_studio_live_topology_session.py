"""Focused parity and drag-budget tests for prepared Map Studio topology."""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest


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
    bevel_imported_mesh_edge,
    extrude_imported_mesh_edge,
    extrude_imported_mesh_faces,
)
from core.modules.map_studio_live_topology_session import MapStudioLiveTopologySession  # noqa: E402


def _lightmapped_cube() -> ImportedMeshRoomPrimitive:
    vertices = (
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 4.0, 0.0),
        (0.0, 4.0, 0.0),
        (0.0, 0.0, 3.0),
        (4.0, 0.0, 3.0),
        (4.0, 4.0, 3.0),
        (0.0, 4.0, 3.0),
    )
    faces = (
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (1, 5, 6),
        (1, 6, 2),
        (2, 6, 7),
        (2, 7, 3),
        (3, 7, 4),
        (3, 4, 0),
    )
    surface = ImportedMeshSurface(
        name="cube",
        texture="lda_wall01",
        vertices=vertices,
        faces=faces,
        face_mats=(7, 7, 9, 9, 5, 5, 3, 3, 1, 1, 4, 4),
        uvs=tuple((0.125 + index, 0.625 + index) for index in range(len(vertices))),
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        lightmap="lda_wall01lm",
        texture_names=("lda_wall01", "lda_wall01lm"),
        tex_count=2,
        uvs_lm=tuple((0.05 + index * 0.1, 0.95 - index * 0.1) for index in range(len(vertices))),
    )
    return ImportedMeshRoomPrimitive(room_resref="grlive", surfaces=(surface,), game="K2")


def _assert_channel_close(actual: tuple, expected: tuple, *, tolerance: float = 1.0e-6) -> None:
    assert len(actual) == len(expected)
    for actual_row, expected_row in zip(actual, expected):
        assert tuple(actual_row) == pytest.approx(tuple(expected_row), abs=tolerance)


def _assert_surface_close(actual: ImportedMeshSurface, expected: ImportedMeshSurface) -> None:
    assert actual.faces == expected.faces
    assert actual.face_mats == expected.face_mats
    _assert_channel_close(actual.vertices, expected.vertices)
    _assert_channel_close(actual.uvs, expected.uvs)
    _assert_channel_close(actual.uvs_lm, expected.uvs_lm)
    _assert_channel_close(actual.normals, expected.normals)


@pytest.mark.parametrize("distance", (0.17, 0.73, -0.17, -0.73))
def test_prepared_face_extrude_matches_authoritative_operator(distance: float) -> None:
    source = _lightmapped_cube()
    session = MapStudioLiveTopologySession.prepare_face_extrude(
        source,
        "render",
        (0,),
        tile_size=1.75,
        direction=(0.0, 0.0, 3.0),
        reference_distance=0.8,
    )

    evaluated = session.evaluate(distance)
    authoritative = extrude_imported_mesh_faces(
        source,
        "render",
        (0,),
        distance,
        tile_size=1.75,
        direction=(0.0, 0.0, 1.0),
    )

    assert session.source is source
    assert session.evaluate(0.0) is source
    assert session.prepared_sample_count == 2
    assert session.identity.direction == (0.0, 0.0, 1.0)
    _assert_surface_close(evaluated.surfaces[0], authoritative.surfaces[0])
    assert source == _lightmapped_cube(), "preparing/evaluating must not mutate the immutable source"


@pytest.mark.parametrize("distance", (0.11, 0.64, -0.11, -0.64))
def test_prepared_edge_extrude_matches_authoritative_operator_and_preserves_channels(
    distance: float,
) -> None:
    source = _lightmapped_cube()
    source_snapshot = _lightmapped_cube()
    direction = (0.0, 0.6, 0.8)
    session = MapStudioLiveTopologySession.prepare_edge_extrude(
        source,
        "render",
        0,
        (0, 1),
        direction=(0.0, 3.0, 4.0),
        tile_size=1.25,
        reference_distance=0.8,
    )

    evaluated = session.evaluate(distance)
    authoritative = extrude_imported_mesh_edge(
        source,
        "render",
        0,
        (0, 1),
        tuple(component * distance for component in direction),
        tile_size=1.25,
    )

    assert session.source is source
    assert session.evaluate(0.0) is source
    assert session.prepared_sample_count == 2
    assert session.identity.operation == "edge_extrude"
    assert session.identity.direction == pytest.approx(direction)
    _assert_surface_close(evaluated.surfaces[0], authoritative.surfaces[0])
    assert evaluated.surfaces[0].faces is session.evaluate(distance * 0.5).surfaces[0].faces
    assert evaluated.surfaces[0].face_mats is session.evaluate(distance * 0.5).surfaces[0].face_mats
    assert evaluated.surfaces[0].uvs_lm is session.evaluate(distance * 0.5).surfaces[0].uvs_lm
    assert source == source_snapshot, "preparing/evaluating must not mutate source mesh or channels"


@pytest.mark.parametrize("distance", (0.4, -0.4))
def test_prepared_parallel_edge_extrude_preserves_authoritative_fallback_normal(distance: float) -> None:
    source = _lightmapped_cube()
    session = MapStudioLiveTopologySession.prepare_edge_extrude(
        source,
        "render",
        0,
        (0, 1),
        direction=(1.0, 0.0, 0.0),
    )
    evaluated = session.evaluate(distance)
    authoritative = extrude_imported_mesh_edge(
        source,
        "render",
        0,
        (0, 1),
        (distance, 0.0, 0.0),
    )
    _assert_surface_close(evaluated.surfaces[0], authoritative.surfaces[0])


@pytest.mark.parametrize("width", (0.08, 0.31, -0.31))
def test_prepared_edge_bevel_matches_authoritative_operator(width: float) -> None:
    source = _lightmapped_cube()
    session = MapStudioLiveTopologySession.prepare_edge_bevel(
        source,
        "render",
        0,
        (0, 1),
        segments=3,
        profile=0.8,
        miter="patch",
        smoothing_angle_degrees=45.0,
        uv_mode="tiled",
    )
    evaluated = session.evaluate(width)
    authoritative = bevel_imported_mesh_edge(
        source,
        "render",
        0,
        (0, 1),
        width,
        segments=3,
        profile=0.8,
        miter="patch",
        smoothing_angle_degrees=45.0,
        uv_mode="tiled",
    )

    _assert_surface_close(evaluated.surfaces[0], authoritative.surfaces[0])
    assert evaluated.metadata["last_topology_edit"]["width"] == pytest.approx(abs(width))
    assert session.identity.bevel is not None
    assert session.identity.bevel.segments == 3
    assert session.identity.bevel.profile == pytest.approx(0.8)


def test_prepared_bevel_clamps_or_raises_at_discovered_safe_width() -> None:
    source = _lightmapped_cube()
    clamped = MapStudioLiveTopologySession.prepare_edge_bevel(
        source,
        "render",
        0,
        (0, 1),
        segments=2,
        clamp_overlap=True,
    )
    maximum = float(clamped.maximum_value or 0.0)
    assert maximum > 0.0
    evaluated = clamped.evaluate(maximum * 10.0)
    assert evaluated.metadata["last_topology_edit"]["width"] == pytest.approx(maximum)

    strict = MapStudioLiveTopologySession.prepare_edge_bevel(
        source,
        "render",
        0,
        (0, 1),
        segments=999,
        profile=5.0,
        smoothing_angle_degrees=500.0,
        clamp_overlap=False,
    )
    assert strict.identity.bevel is not None
    assert strict.identity.bevel.segments == 64
    assert strict.identity.bevel.profile == 1.0
    assert strict.identity.bevel.smoothing_angle_degrees == 180.0
    with pytest.raises(ValueError, match="maximum safe width"):
        strict.evaluate(float(strict.maximum_value or 0.0) * 1.1)


def _grid_65() -> ImportedMeshRoomPrimitive:
    resolution = 65
    vertices = tuple(
        (float(x), float(y), 0.0)
        for y in range(resolution)
        for x in range(resolution)
    )
    faces: list[tuple[int, int, int]] = []
    for y in range(resolution - 1):
        for x in range(resolution - 1):
            a = (y * resolution) + x
            b = a + 1
            d = ((y + 1) * resolution) + x
            c = d + 1
            faces.extend(((a, b, c), (a, c, d)))
    surface = ImportedMeshSurface(
        name="grid65",
        texture="gr_terrain",
        vertices=vertices,
        faces=tuple(faces),
        face_mats=tuple(index % 2 for index in range(len(faces))),
        uvs=tuple((row[0] / 64.0, row[1] / 64.0) for row in vertices),
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        lightmap="gr_terrainlm",
        texture_names=("gr_terrain", "gr_terrainlm"),
        tex_count=2,
        uvs_lm=tuple((row[0] / 64.0, row[1] / 64.0) for row in vertices),
    )
    return ImportedMeshRoomPrimitive(room_resref="grid65", surfaces=(surface,), game="K2")


def test_prepared_65x65_drag_evaluation_stays_inside_four_millisecond_cpu_budget() -> None:
    session = MapStudioLiveTopologySession.prepare_face_extrude(
        _grid_65(),
        "render",
        (0,),
        reference_distance=0.75,
    )
    for value in (0.1, 0.2, 0.3):
        session.evaluate(value)

    values = tuple(0.05 + ((index % 50) * 0.01) for index in range(200))
    started = time.perf_counter()
    result = None
    for value in values:
        result = session.evaluate(value)
    average_ms = ((time.perf_counter() - started) * 1000.0) / len(values)

    assert result is not None
    assert result.surfaces[0].faces is session.evaluate(0.2).surfaces[0].faces
    print(f"prepared 65x65 face-extrude evaluation: {average_ms:.3f} ms/frame")
    assert average_ms < 4.0


def test_prepared_65x65_edge_extrude_stays_inside_four_millisecond_cpu_budget() -> None:
    source = _grid_65()
    session = MapStudioLiveTopologySession.prepare_edge_extrude(
        source,
        "render",
        0,
        (0, 1),
        direction=(0.0, 0.0, 1.0),
        reference_distance=0.75,
    )
    for value in (0.1, -0.2, 0.3):
        session.evaluate(value)

    values = tuple((-1.0 if index % 2 else 1.0) * (0.05 + ((index % 50) * 0.01)) for index in range(200))
    started = time.perf_counter()
    result = None
    for value in values:
        result = session.evaluate(value)
    average_ms = ((time.perf_counter() - started) * 1000.0) / len(values)

    assert result is not None
    second = session.evaluate(0.2)
    assert result.surfaces[0].faces is second.surfaces[0].faces
    assert result.surfaces[0].face_mats is second.surfaces[0].face_mats
    assert result.surfaces[0].uvs_lm is second.surfaces[0].uvs_lm
    assert source == _grid_65()
    print(f"prepared 65x65 edge-extrude evaluation: {average_ms:.3f} ms/frame")
    assert average_ms < 4.0
