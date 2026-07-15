"""Connected logical polygon cages for Map Studio construction primitives.

The authored room exporters intentionally keep their existing triangle-corner
representation because Odyssey MDL needs independent UV and hard-normal
corners.  Modeling tools need a different representation: one shared position
index per logical polygon vertex, n-gon caps, deterministic component identity,
and face-corner channels.  This module is that headless construction-history
evaluation boundary.

The topology formulas follow the clean-room Maya 2025.3 primitive audit in
``Saved/Audits/maya_modeling_parity_20260714``.  No Autodesk implementation or
asset is used here.
"""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Any, Callable, Sequence

from src.core.geometry.polygon_mesh_operations import AttributeChannel, IndexedPolygonMesh

from .authored_room_composition import PlacedRoomPrimitive, PrimitiveTransform
from .authored_room_geometry import Vec2, Vec3
from .authored_room_primitives import (
    ConePrimitive,
    CubePrimitive,
    CylinderPrimitive,
    FloorPrimitive,
    SpherePrimitive,
    TorusPrimitive,
    normalise_primitive_axis,
    primitive_construction_node_id,
)


MayaConstructionPrimitive = (
    FloorPrimitive | CubePrimitive | CylinderPrimitive | SpherePrimitive | ConePrimitive | TorusPrimitive
)
MayaConstructionPrimitiveInstance = MayaConstructionPrimitive | PlacedRoomPrimitive


def _construction_kind(primitive: MayaConstructionPrimitive) -> str:
    if isinstance(primitive, FloorPrimitive):
        return "plane"
    if isinstance(primitive, CubePrimitive):
        return "cube"
    if isinstance(primitive, CylinderPrimitive):
        return "cylinder"
    if isinstance(primitive, SpherePrimitive):
        return "sphere"
    if isinstance(primitive, ConePrimitive):
        return "cone"
    if isinstance(primitive, TorusPrimitive):
        return "torus"
    raise TypeError(f"Unsupported Maya construction primitive {type(primitive).__name__}.")


def _transform_manifest(transform: PrimitiveTransform) -> dict[str, Any]:
    return {
        "translation": tuple(float(value) for value in transform.translation),
        "rotation_degrees_z": float(transform.rotation_degrees_z),
        "scale": tuple(float(value) for value in transform.scale),
        "pivot": tuple(float(value) for value in transform.pivot),
    }


def _transform_point(point: Vec3, transform: PrimitiveTransform) -> Vec3:
    px, py, pz = (float(value) for value in transform.pivot)
    sx, sy, sz = (float(value) for value in transform.scale)
    tx, ty, tz = (float(value) for value in transform.translation)
    x = (float(point[0]) - px) * sx
    y = (float(point[1]) - py) * sy
    z = (float(point[2]) - pz) * sz
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (
        x * cos_a - y * sin_a + px + tx,
        x * sin_a + y * cos_a + py + ty,
        z + pz + tz,
    )


def _transform_normal(normal: Vec3, transform: PrimitiveTransform) -> Vec3:
    sx, sy, sz = (float(value) for value in transform.scale)
    epsilon = 1.0e-12
    nx = float(normal[0]) / sx if abs(sx) > epsilon else 0.0
    ny = float(normal[1]) / sy if abs(sy) > epsilon else 0.0
    nz = float(normal[2]) / sz if abs(sz) > epsilon else 0.0
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return _normalized((nx * cos_a - ny * sin_a, nx * sin_a + ny * cos_a, nz))


def _transform_cage_stage(mesh: IndexedPolygonMesh, transform: PrimitiveTransform) -> IndexedPolygonMesh:
    corner_channels = dict(mesh.corner_channels)
    normals = corner_channels.get("normal")
    if normals is not None:
        corner_channels["normal"] = AttributeChannel.build(
            tuple(
                tuple(_transform_normal(tuple(value), transform) for value in row)
                for row in normals.values
            ),
            semantic="normal",
            default=(0.0, 0.0, 1.0),
        )
    return IndexedPolygonMesh.build(
        tuple(_transform_point(tuple(vertex), transform) for vertex in mesh.vertices),
        mesh.faces,
        vertex_channels=mesh.vertex_channels,
        face_channels=mesh.face_channels,
        corner_channels=corner_channels,
        metadata=mesh.metadata,
    )


def _rotate_from_z(vector: Vec3, axis: Vec3) -> Vec3:
    """Rotate a local-Z vector onto a normalized target axis."""

    target = normalise_primitive_axis(axis)
    x, y, z = (float(vector[0]), float(vector[1]), float(vector[2]))
    cosine = max(-1.0, min(1.0, target[2]))
    if cosine >= 1.0 - 1.0e-12:
        return (x, y, z)
    if cosine <= -1.0 + 1.0e-12:
        return (x, -y, -z)
    vx, vy = -target[1], target[0]
    sine_squared = vx * vx + vy * vy
    cross = (vy * z, -vx * z, vx * y - vy * x)
    dot = vx * x + vy * y
    factor = (1.0 - cosine) / sine_squared
    return (
        x * cosine + cross[0] + vx * dot * factor,
        y * cosine + cross[1] + vy * dot * factor,
        z * cosine + cross[2],
    )


def _normalized(value: Sequence[float]) -> Vec3:
    length = math.sqrt(sum(float(component) * float(component) for component in value[:3]))
    if length <= 1.0e-15:
        return (0.0, 0.0, 1.0)
    return tuple(float(component) / length for component in value[:3])  # type: ignore[return-value]


def _oriented_point(
    point: Vec3,
    *,
    center: Vec3,
    axis: Vec3,
    height_baseline: float,
    baseline_extent: float,
) -> Vec3:
    resolved_axis = normalise_primitive_axis(axis)
    baseline = max(-1.0, min(1.0, float(height_baseline)))
    shift = -baseline * max(0.0, float(baseline_extent)) * 0.5
    delta = tuple(float(point[index]) - float(center[index]) for index in range(3))
    rotated = _rotate_from_z(delta, resolved_axis)
    return tuple(
        float(center[index]) + resolved_axis[index] * shift + rotated[index]
        for index in range(3)
    )  # type: ignore[return-value]


def _finish_cage(
    *,
    primitive_name: str,
    primitive_type: str,
    vertices: list[Vec3],
    faces: list[tuple[int, ...]],
    vertex_ids: list[str],
    face_ids: list[str],
    corner_normals: list[tuple[Vec3, ...]],
    corner_uvs: list[tuple[Vec2, ...]] | None,
    center: Vec3,
    axis: Vec3,
    height_baseline: float,
    baseline_extent: float,
    texture: str,
    construction_node_id: str,
    metadata: dict[str, Any],
) -> IndexedPolygonMesh:
    if len(vertices) != len(vertex_ids):
        raise ValueError("Logical primitive vertex provenance is not aligned.")
    if not (len(faces) == len(face_ids) == len(corner_normals)):
        raise ValueError("Logical primitive face provenance/normals are not aligned.")
    if corner_uvs is not None and len(corner_uvs) != len(faces):
        raise ValueError("Logical primitive UV rows are not aligned with faces.")

    resolved_axis = normalise_primitive_axis(axis)
    oriented_vertices = tuple(
        _oriented_point(
            point,
            center=center,
            axis=resolved_axis,
            height_baseline=height_baseline,
            baseline_extent=baseline_extent,
        )
        for point in vertices
    )
    oriented_normals = tuple(
        tuple(_normalized(_rotate_from_z(normal, resolved_axis)) for normal in row)
        for row in corner_normals
    )
    node_id = str(construction_node_id or "").strip() or primitive_construction_node_id(
        room_resref="",
        primitive_type=primitive_type,
        name=primitive_name,
    )
    namespace = f"construction:{node_id}"
    scoped_vertex_ids = tuple(f"{namespace}/vertex:{value}" for value in vertex_ids)
    scoped_face_ids = tuple(f"{namespace}/face:{value}" for value in face_ids)
    corner_ids = tuple(
        tuple(
            f"{scoped_face_ids[face_index]}/corner:{corner_index}/vertex:{scoped_vertex_ids[vertex_index]}"
            for corner_index, vertex_index in enumerate(face)
        )
        for face_index, face in enumerate(faces)
    )
    corner_channels: dict[str, AttributeChannel] = {
        "normal": AttributeChannel.build(oriented_normals, semantic="normal", default=(0.0, 0.0, 1.0)),
        "provenance.corner_id": AttributeChannel.build(corner_ids, semantic="attribute", default=""),
    }
    if corner_uvs is not None:
        corner_channels["uv0"] = AttributeChannel.build(
            tuple(corner_uvs), semantic="attribute", default=(0.0, 0.0)
        )

    payload_metadata = {
        "logical_polygon_cage": True,
        "export_triangulation_required": True,
        "topology_contract": "maya_2025_polygon_primitive",
        "primitive": primitive_type,
        "primitive_name": str(primitive_name),
        "construction_node_id": node_id,
        "component_identity_namespace": namespace,
        "axis": resolved_axis,
        "height_baseline": max(-1.0, min(1.0, float(height_baseline))),
        "uv2_policy": "not_generated",
        **metadata,
    }
    return IndexedPolygonMesh.build(
        oriented_vertices,
        faces,
        vertex_channels={
            "provenance.vertex_id": AttributeChannel.build(
                scoped_vertex_ids, semantic="attribute", default=""
            )
        },
        face_channels={
            "provenance.face_id": AttributeChannel.build(
                scoped_face_ids, semantic="attribute", default=""
            ),
            "material.texture": AttributeChannel.build(
                (str(texture),) * len(faces), semantic="attribute", default="default"
            ),
        },
        corner_channels=corner_channels,
        metadata=payload_metadata,
    )


def build_plane_polygon_cage(primitive: FloorPrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected quad plane from a retained floor recipe."""

    width = max(0.01, float(primitive.width))
    depth = max(0.01, float(primitive.depth))
    u_count = max(1, int(primitive.subdivisions_width))
    v_count = max(1, int(primitive.subdivisions_depth))
    center: Vec3 = (0.0, 0.0, float(primitive.z))
    vertices: list[Vec3] = []
    vertex_ids: list[str] = []
    for row in range(v_count + 1):
        y = -depth * 0.5 + depth * row / v_count
        for column in range(u_count + 1):
            x = -width * 0.5 + width * column / u_count
            vertices.append((x, y, center[2]))
            vertex_ids.append(f"plane:grid:{column}/{u_count}:{row}/{v_count}")

    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    uv_mode = max(0, min(2, int(primitive.create_uvs)))
    stride = u_count + 1
    longest = max(width, depth)
    for row in range(v_count):
        for column in range(u_count):
            a = row * stride + column
            b = a + 1
            d = (row + 1) * stride + column
            c = d + 1
            faces.append((a, b, c, d))
            face_ids.append(f"plane:cell:{column}:{row}")
            normals.append(((0.0, 0.0, 1.0),) * 4)
            if uv_mode == 1:
                uv_rows.append(
                    (
                        (column * width / u_count, row * depth / v_count),
                        ((column + 1) * width / u_count, row * depth / v_count),
                        ((column + 1) * width / u_count, (row + 1) * depth / v_count),
                        (column * width / u_count, (row + 1) * depth / v_count),
                    )
                )
            elif uv_mode == 2:
                uv_rows.append(
                    (
                        (column * width / u_count / longest, row * depth / v_count / longest),
                        ((column + 1) * width / u_count / longest, row * depth / v_count / longest),
                        ((column + 1) * width / u_count / longest, (row + 1) * depth / v_count / longest),
                        (column * width / u_count / longest, (row + 1) * depth / v_count / longest),
                    )
                )
    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="plane",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if uv_mode else None,
        center=center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=0.0,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_width": u_count,
            "subdivisions_height": v_count,
            "create_uvs": uv_mode,
            "uv_policy": ("none", "unnormalized", "preserve_aspect")[uv_mode],
        },
    )


def build_cube_polygon_cage(primitive: CubePrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected closed quad cube with Maya's surface-only grid."""

    size_x, size_y, size_z = (max(0.01, float(value)) for value in primitive.size)
    sub_x = max(1, int(primitive.subdivisions_x))
    sub_y = max(1, int(primitive.subdivisions_y))
    sub_z = max(1, int(primitive.subdivisions_z))
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = []
    vertex_ids: list[str] = []
    index_by_grid: dict[tuple[int, int, int], int] = {}
    for z_index in range(sub_z + 1):
        for y_index in range(sub_y + 1):
            for x_index in range(sub_x + 1):
                if not (
                    x_index in (0, sub_x)
                    or y_index in (0, sub_y)
                    or z_index in (0, sub_z)
                ):
                    continue
                index_by_grid[(x_index, y_index, z_index)] = len(vertices)
                vertices.append(
                    (
                        cx - size_x * 0.5 + size_x * x_index / sub_x,
                        cy - size_y * 0.5 + size_y * y_index / sub_y,
                        cz - size_z * 0.5 + size_z * z_index / sub_z,
                    )
                )
                vertex_ids.append(
                    f"cube:grid:{x_index}/{sub_x}:{y_index}/{sub_y}:{z_index}/{sub_z}"
                )

    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    uv_mode = max(0, min(4, int(primitive.create_uvs)))

    def add_face(
        grid_corners: tuple[tuple[int, int, int], ...],
        *,
        face_id: str,
        normal: Vec3,
    ) -> None:
        faces.append(tuple(index_by_grid[value] for value in grid_corners))
        face_ids.append(face_id)
        normals.append((normal,) * 4)
        if uv_mode:
            uv_rows.append(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))

    for y_index in range(sub_y):
        for x_index in range(sub_x):
            add_face(
                (
                    (x_index, y_index + 1, 0),
                    (x_index + 1, y_index + 1, 0),
                    (x_index + 1, y_index, 0),
                    (x_index, y_index, 0),
                ),
                face_id=f"cube:-z:{x_index}:{y_index}",
                normal=(0.0, 0.0, -1.0),
            )
            add_face(
                (
                    (x_index, y_index, sub_z),
                    (x_index + 1, y_index, sub_z),
                    (x_index + 1, y_index + 1, sub_z),
                    (x_index, y_index + 1, sub_z),
                ),
                face_id=f"cube:+z:{x_index}:{y_index}",
                normal=(0.0, 0.0, 1.0),
            )
    for z_index in range(sub_z):
        for x_index in range(sub_x):
            add_face(
                (
                    (x_index, 0, z_index),
                    (x_index + 1, 0, z_index),
                    (x_index + 1, 0, z_index + 1),
                    (x_index, 0, z_index + 1),
                ),
                face_id=f"cube:-y:{x_index}:{z_index}",
                normal=(0.0, -1.0, 0.0),
            )
            add_face(
                (
                    (x_index, sub_y, z_index),
                    (x_index, sub_y, z_index + 1),
                    (x_index + 1, sub_y, z_index + 1),
                    (x_index + 1, sub_y, z_index),
                ),
                face_id=f"cube:+y:{x_index}:{z_index}",
                normal=(0.0, 1.0, 0.0),
            )
    for z_index in range(sub_z):
        for y_index in range(sub_y):
            add_face(
                (
                    (0, y_index, z_index),
                    (0, y_index, z_index + 1),
                    (0, y_index + 1, z_index + 1),
                    (0, y_index + 1, z_index),
                ),
                face_id=f"cube:-x:{y_index}:{z_index}",
                normal=(-1.0, 0.0, 0.0),
            )
            add_face(
                (
                    (sub_x, y_index, z_index),
                    (sub_x, y_index + 1, z_index),
                    (sub_x, y_index + 1, z_index + 1),
                    (sub_x, y_index, z_index + 1),
                ),
                face_id=f"cube:+x:{y_index}:{z_index}",
                normal=(1.0, 0.0, 0.0),
            )

    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="cube",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if uv_mode else None,
        center=primitive.center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=size_z,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_x": sub_x,
            "subdivisions_y": sub_y,
            "subdivisions_z": sub_z,
            "create_uvs": uv_mode,
            "uv_policy": ("none", "unnormalized", "per_face", "collective", "collective_preserve_aspect")[uv_mode],
        },
    )


def _ring_vertex(center: Vec3, radius: float, z: float, column: int, count: int) -> Vec3:
    angle = math.tau * column / count
    return (
        float(center[0]) + radius * math.cos(angle),
        float(center[1]) + radius * math.sin(angle),
        z,
    )


def _radial_normal(column: int, count: int, z_component: float = 0.0) -> Vec3:
    angle = math.tau * column / count
    return _normalized((math.cos(angle), math.sin(angle), z_component))


def _disk_uv(point: Vec3, center: Vec3, radius: float) -> Vec2:
    return (
        0.5 + (float(point[0]) - float(center[0])) / (2.0 * radius),
        0.5 + (float(point[1]) - float(center[1])) / (2.0 * radius),
    )


def build_cylinder_polygon_cage(primitive: CylinderPrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected cylinder with shared side/cap rim positions.

    Maya's zero-subdivision round cap changes bounds without adding topology.
    A polygon cage cannot represent a curved hemisphere without added vertices;
    that case preserves Maya's counts and evaluated extent but is necessarily a
    straight low-resolution silhouette.  One or more cap subdivisions produce
    an actual rounded profile.
    """

    axis_count = max(3, int(primitive.segments))
    height_count = max(1, int(primitive.subdivisions_height))
    cap_count = max(0, int(primitive.subdivisions_caps))
    radius = max(0.01, float(primitive.radius))
    requested_height = max(0.01, float(primitive.height))
    round_cap = bool(primitive.round_cap)
    compensated = round_cap and bool(primitive.round_cap_height_compensation)
    cap_depth = radius if round_cap else 0.0
    if compensated:
        cap_depth = min(radius, max(0.0, requested_height * 0.5 - 0.005))
        body_half = max(0.005, requested_height * 0.5 - cap_depth)
        evaluated_height = requested_height
    else:
        body_half = requested_height * 0.5
        evaluated_height = requested_height + cap_depth * 2.0
    side_half = body_half + cap_depth if round_cap and cap_count == 0 else body_half
    cx, cy, cz = primitive.center

    vertices: list[Vec3] = []
    vertex_ids: list[str] = []
    side_rings: list[list[int]] = []
    for row in range(height_count + 1):
        z = cz - side_half + side_half * 2.0 * row / height_count
        ring: list[int] = []
        for column in range(axis_count):
            ring.append(len(vertices))
            vertices.append(_ring_vertex(primitive.center, radius, z, column, axis_count))
            vertex_ids.append(f"cylinder:side:{row}/{height_count}:{column}/{axis_count}")
        side_rings.append(ring)

    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    uv_mode = max(0, min(3, int(primitive.create_uvs)))
    for row in range(height_count):
        for column in range(axis_count):
            next_column = (column + 1) % axis_count
            faces.append(
                (
                    side_rings[row][column],
                    side_rings[row][next_column],
                    side_rings[row + 1][next_column],
                    side_rings[row + 1][column],
                )
            )
            face_ids.append(f"cylinder:side:{row}:{column}")
            normals.append(
                (
                    _radial_normal(column, axis_count),
                    _radial_normal(next_column, axis_count),
                    _radial_normal(next_column, axis_count),
                    _radial_normal(column, axis_count),
                )
            )
            if uv_mode:
                u0 = column / axis_count
                u1 = (column + 1) / axis_count
                v0 = row / height_count
                v1 = (row + 1) / height_count
                uv_rows.append(((u0, v0), (u1, v0), (u1, v1), (u0, v1)))

    for sign, label, rim in (
        (-1.0, "bottom", side_rings[0]),
        (1.0, "top", side_rings[-1]),
    ):
        cap_normal: dict[int, Vec3] = {index: (0.0, 0.0, sign) for index in rim}
        if round_cap and cap_count:
            cap_normal = {
                index: _radial_normal(column, axis_count)
                for column, index in enumerate(rim)
            }
        if cap_count == 0:
            face = tuple(reversed(rim)) if sign < 0.0 else tuple(rim)
            faces.append(face)
            face_ids.append(f"cylinder:cap:{label}:ngon")
            normals.append(((0.0, 0.0, sign),) * len(face))
            if uv_mode:
                uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))
            continue

        rings: list[list[int]] = [rim]
        for ring_index in range(1, cap_count):
            profile = math.pi * 0.5 * (1.0 - ring_index / cap_count)
            ring_radius = radius * (math.sin(profile) if round_cap else 1.0 - ring_index / cap_count)
            z = cz + sign * (
                body_half + (cap_depth * math.cos(profile) if round_cap else 0.0)
            )
            ring: list[int] = []
            for column in range(axis_count):
                index = len(vertices)
                ring.append(index)
                vertices.append(_ring_vertex(primitive.center, ring_radius, z, column, axis_count))
                vertex_ids.append(
                    f"cylinder:cap:{label}:ring:{ring_index}/{cap_count}:{column}/{axis_count}"
                )
                cap_normal[index] = (
                    _radial_normal(column, axis_count, sign * math.cos(profile) / max(math.sin(profile), 1.0e-12))
                    if round_cap
                    else (0.0, 0.0, sign)
                )
            rings.append(ring)
        center_index = len(vertices)
        center_z = cz + sign * (body_half + (cap_depth if round_cap else 0.0))
        vertices.append((cx, cy, center_z))
        vertex_ids.append(f"cylinder:cap:{label}:center")
        cap_normal[center_index] = (0.0, 0.0, sign)

        for band_index in range(len(rings) - 1):
            outer = rings[band_index]
            inner = rings[band_index + 1]
            for column in range(axis_count):
                next_column = (column + 1) % axis_count
                if sign > 0.0:
                    face = (outer[column], outer[next_column], inner[next_column], inner[column])
                else:
                    face = (outer[column], inner[column], inner[next_column], outer[next_column])
                faces.append(face)
                face_ids.append(f"cylinder:cap:{label}:band:{band_index}:{column}")
                normals.append(tuple(cap_normal[index] for index in face))
                if uv_mode:
                    uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))
        last_ring = rings[-1]
        for column in range(axis_count):
            next_column = (column + 1) % axis_count
            face = (
                (last_ring[column], last_ring[next_column], center_index)
                if sign > 0.0
                else (last_ring[column], center_index, last_ring[next_column])
            )
            faces.append(face)
            face_ids.append(f"cylinder:cap:{label}:fan:{column}")
            normals.append(tuple(cap_normal[index] for index in face))
            if uv_mode:
                uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))

    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="cylinder",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if uv_mode else None,
        center=primitive.center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=evaluated_height,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_axis": axis_count,
            "subdivisions_height": height_count,
            "subdivisions_caps": cap_count,
            "create_uvs": uv_mode,
            "round_cap": round_cap,
            "round_cap_height_compensation": compensated,
            "round_cap_zero_subdivision_approximation": bool(round_cap and cap_count == 0),
        },
    )


def build_sphere_polygon_cage(primitive: SpherePrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected pole-and-ring sphere with n-gon-aware channels."""

    axis_count = max(3, int(primitive.subdivisions_axis))
    height_count = max(3, int(primitive.subdivisions_height))
    radius = max(0.01, float(primitive.radius))
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = [(cx, cy, cz + radius)]
    vertex_ids: list[str] = ["sphere:pole:north"]
    rings: list[list[int]] = []
    for row in range(1, height_count):
        phi = math.pi * row / height_count
        ring_radius = radius * math.sin(phi)
        z = cz + radius * math.cos(phi)
        ring: list[int] = []
        for column in range(axis_count):
            ring.append(len(vertices))
            vertices.append(_ring_vertex(primitive.center, ring_radius, z, column, axis_count))
            vertex_ids.append(f"sphere:ring:{row}/{height_count}:{column}/{axis_count}")
        rings.append(ring)
    south_index = len(vertices)
    vertices.append((cx, cy, cz - radius))
    vertex_ids.append("sphere:pole:south")

    def vertex_normal(index: int) -> Vec3:
        point = vertices[index]
        return _normalized((point[0] - cx, point[1] - cy, point[2] - cz))

    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    uv_mode = max(0, min(2, int(primitive.create_uvs)))
    first_ring = rings[0]
    last_ring = rings[-1]
    for column in range(axis_count):
        next_column = (column + 1) % axis_count
        face = (0, first_ring[column], first_ring[next_column])
        faces.append(face)
        face_ids.append(f"sphere:cap:north:{column}")
        normals.append(tuple(vertex_normal(index) for index in face))
        if uv_mode:
            u0, u1 = column / axis_count, (column + 1) / axis_count
            pole_u = 0.5 if uv_mode == 1 else (u0 + u1) * 0.5
            uv_rows.append(((pole_u, 0.0), (u0, 1.0 / height_count), (u1, 1.0 / height_count)))
    for band in range(len(rings) - 1):
        upper = rings[band]
        lower = rings[band + 1]
        row = band + 1
        for column in range(axis_count):
            next_column = (column + 1) % axis_count
            face = (upper[column], lower[column], lower[next_column], upper[next_column])
            faces.append(face)
            face_ids.append(f"sphere:band:{row}:{column}")
            normals.append(tuple(vertex_normal(index) for index in face))
            if uv_mode:
                u0, u1 = column / axis_count, (column + 1) / axis_count
                v0, v1 = row / height_count, (row + 1) / height_count
                uv_rows.append(((u0, v0), (u0, v1), (u1, v1), (u1, v0)))
    for column in range(axis_count):
        next_column = (column + 1) % axis_count
        face = (south_index, last_ring[next_column], last_ring[column])
        faces.append(face)
        face_ids.append(f"sphere:cap:south:{column}")
        normals.append(tuple(vertex_normal(index) for index in face))
        if uv_mode:
            u0, u1 = column / axis_count, (column + 1) / axis_count
            pole_u = 0.5 if uv_mode == 1 else (u0 + u1) * 0.5
            uv_rows.append(((pole_u, 1.0), (u1, (height_count - 1) / height_count), (u0, (height_count - 1) / height_count)))

    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="sphere",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if uv_mode else None,
        center=primitive.center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=radius * 2.0,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_axis": axis_count,
            "subdivisions_height": height_count,
            "create_uvs": uv_mode,
            "uv_policy": ("none", "pinched_poles", "sawtooth_poles")[uv_mode],
        },
    )


def build_cone_polygon_cage(primitive: ConePrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected cone with shared apex and optional cap rings."""

    axis_count = max(3, int(primitive.subdivisions_axis))
    height_count = max(1, int(primitive.subdivisions_height))
    cap_count = max(0, int(primitive.subdivisions_caps))
    radius = max(0.01, float(primitive.radius))
    height = max(0.01, float(primitive.height))
    round_cap = bool(primitive.round_cap)
    cx, cy, cz = primitive.center
    body_bottom = cz - height * 0.5
    apex_z = cz + height * 0.5
    cap_depth = radius if round_cap else 0.0
    side_bottom = body_bottom - cap_depth if round_cap and cap_count == 0 else body_bottom
    side_height = apex_z - side_bottom

    vertices: list[Vec3] = []
    vertex_ids: list[str] = []
    rings: list[list[int]] = []
    for row in range(height_count):
        fraction = row / height_count
        ring_radius = radius * (1.0 - fraction)
        z = side_bottom + side_height * fraction
        ring: list[int] = []
        for column in range(axis_count):
            ring.append(len(vertices))
            vertices.append(_ring_vertex(primitive.center, ring_radius, z, column, axis_count))
            vertex_ids.append(f"cone:side:{row}/{height_count}:{column}/{axis_count}")
        rings.append(ring)
    apex_index = len(vertices)
    vertices.append((cx, cy, apex_z))
    vertex_ids.append("cone:apex")

    slant = max(1.0e-12, math.sqrt(side_height * side_height + radius * radius))
    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    uv_mode = max(0, min(3, int(primitive.create_uvs)))

    def side_normal(column: int) -> Vec3:
        angle = math.tau * column / axis_count
        return (
            math.cos(angle) * side_height / slant,
            math.sin(angle) * side_height / slant,
            radius / slant,
        )

    for row in range(height_count - 1):
        lower, upper = rings[row], rings[row + 1]
        for column in range(axis_count):
            next_column = (column + 1) % axis_count
            face = (lower[column], lower[next_column], upper[next_column], upper[column])
            faces.append(face)
            face_ids.append(f"cone:side:{row}:{column}")
            normals.append(
                (
                    side_normal(column),
                    side_normal(next_column),
                    side_normal(next_column),
                    side_normal(column),
                )
            )
            if uv_mode:
                u0, u1 = column / axis_count, (column + 1) / axis_count
                v0, v1 = row / height_count, (row + 1) / height_count
                uv_rows.append(((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
    last_ring = rings[-1]
    for column in range(axis_count):
        next_column = (column + 1) % axis_count
        face = (last_ring[column], last_ring[next_column], apex_index)
        faces.append(face)
        face_ids.append(f"cone:side:apex:{column}")
        normals.append(
            (
                side_normal(column),
                side_normal(next_column),
                side_normal(column),
            )
        )
        if uv_mode:
            u0, u1 = column / axis_count, (column + 1) / axis_count
            uv_rows.append(((u0, (height_count - 1) / height_count), (u1, (height_count - 1) / height_count), ((u0 + u1) * 0.5, 1.0)))

    base_rim = rings[0]
    cap_normal: dict[int, Vec3] = {index: (0.0, 0.0, -1.0) for index in base_rim}
    if round_cap and cap_count:
        cap_normal = {
            index: _radial_normal(column, axis_count)
            for column, index in enumerate(base_rim)
        }
    if cap_count == 0:
        face = tuple(reversed(base_rim))
        faces.append(face)
        face_ids.append("cone:cap:bottom:ngon")
        normals.append(((0.0, 0.0, -1.0),) * len(face))
        if uv_mode:
            uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))
    else:
        cap_rings: list[list[int]] = [base_rim]
        for ring_index in range(1, cap_count):
            profile = math.pi * 0.5 * (1.0 - ring_index / cap_count)
            ring_radius = radius * (math.sin(profile) if round_cap else 1.0 - ring_index / cap_count)
            z = body_bottom - (cap_depth * math.cos(profile) if round_cap else 0.0)
            ring: list[int] = []
            for column in range(axis_count):
                index = len(vertices)
                ring.append(index)
                vertices.append(_ring_vertex(primitive.center, ring_radius, z, column, axis_count))
                vertex_ids.append(
                    f"cone:cap:bottom:ring:{ring_index}/{cap_count}:{column}/{axis_count}"
                )
                cap_normal[index] = (
                    _radial_normal(column, axis_count, -math.cos(profile) / max(math.sin(profile), 1.0e-12))
                    if round_cap
                    else (0.0, 0.0, -1.0)
                )
            cap_rings.append(ring)
        cap_center = len(vertices)
        vertices.append((cx, cy, body_bottom - cap_depth))
        vertex_ids.append("cone:cap:bottom:center")
        cap_normal[cap_center] = (0.0, 0.0, -1.0)
        for band_index in range(len(cap_rings) - 1):
            outer, inner = cap_rings[band_index], cap_rings[band_index + 1]
            for column in range(axis_count):
                next_column = (column + 1) % axis_count
                face = (outer[column], inner[column], inner[next_column], outer[next_column])
                faces.append(face)
                face_ids.append(f"cone:cap:bottom:band:{band_index}:{column}")
                normals.append(tuple(cap_normal[index] for index in face))
                if uv_mode:
                    uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))
        inner = cap_rings[-1]
        for column in range(axis_count):
            next_column = (column + 1) % axis_count
            face = (inner[column], cap_center, inner[next_column])
            faces.append(face)
            face_ids.append(f"cone:cap:bottom:fan:{column}")
            normals.append(tuple(cap_normal[index] for index in face))
            if uv_mode:
                uv_rows.append(tuple(_disk_uv(vertices[index], primitive.center, radius) for index in face))

    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="cone",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if uv_mode else None,
        center=primitive.center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=height + cap_depth,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_axis": axis_count,
            "subdivisions_height": height_count,
            "subdivisions_caps": cap_count,
            "create_uvs": uv_mode,
            "round_cap": round_cap,
            "round_cap_zero_subdivision_approximation": bool(round_cap and cap_count == 0),
        },
    )


def build_torus_polygon_cage(primitive: TorusPrimitive) -> IndexedPolygonMesh:
    """Evaluate a connected periodic quad torus with retained twist."""

    axis_count = max(3, int(primitive.subdivisions_axis))
    height_count = max(3, int(primitive.subdivisions_height))
    radius = max(0.01, float(primitive.radius))
    section_radius = max(0.01, float(primitive.section_radius))
    twist = max(0.0, min(360.0, float(primitive.twist)))
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = []
    vertex_ids: list[str] = []
    vertex_normals: list[Vec3] = []
    for axis_index in range(axis_count):
        u = axis_index / axis_count
        theta = math.tau * u
        for height_index in range(height_count):
            v = height_index / height_count
            phi = math.tau * v + math.radians(twist) * u
            cos_theta, sin_theta = math.cos(theta), math.sin(theta)
            cos_phi, sin_phi = math.cos(phi), math.sin(phi)
            ring_radius = radius + section_radius * cos_phi
            vertices.append(
                (
                    cx + ring_radius * cos_theta,
                    cy + ring_radius * sin_theta,
                    cz + section_radius * sin_phi,
                )
            )
            vertex_normals.append((cos_phi * cos_theta, cos_phi * sin_theta, sin_phi))
            vertex_ids.append(
                f"torus:ring:{axis_index}/{axis_count}:{height_index}/{height_count}"
            )

    def index(axis_index: int, height_index: int) -> int:
        return (axis_index % axis_count) * height_count + (height_index % height_count)

    faces: list[tuple[int, ...]] = []
    face_ids: list[str] = []
    normals: list[tuple[Vec3, ...]] = []
    uv_rows: list[tuple[Vec2, ...]] = []
    create_uvs = bool(primitive.create_uvs)
    for axis_index in range(axis_count):
        for height_index in range(height_count):
            face = (
                index(axis_index, height_index),
                index(axis_index + 1, height_index),
                index(axis_index + 1, height_index + 1),
                index(axis_index, height_index + 1),
            )
            faces.append(face)
            face_ids.append(f"torus:cell:{axis_index}:{height_index}")
            normals.append(tuple(vertex_normals[value] for value in face))
            if create_uvs:
                u0, u1 = axis_index / axis_count, (axis_index + 1) / axis_count
                v0, v1 = height_index / height_count, (height_index + 1) / height_count
                uv_rows.append(((u0, v0), (u1, v0), (u1, v1), (u0, v1)))

    return _finish_cage(
        primitive_name=primitive.name,
        primitive_type="torus",
        vertices=vertices,
        faces=faces,
        vertex_ids=vertex_ids,
        face_ids=face_ids,
        corner_normals=normals,
        corner_uvs=uv_rows if create_uvs else None,
        center=primitive.center,
        axis=primitive.axis,
        height_baseline=primitive.height_baseline,
        baseline_extent=section_radius * 2.0,
        texture=primitive.material.texture,
        construction_node_id=primitive.construction_node_id,
        metadata={
            "subdivisions_axis": axis_count,
            "subdivisions_height": height_count,
            "create_uvs": create_uvs,
            "twist": twist,
        },
    )


def build_authored_primitive_polygon_cage(
    primitive: MayaConstructionPrimitiveInstance,
    *,
    room_resref: str = "",
) -> IndexedPolygonMesh:
    """Evaluate one retained construction recipe in editable component space.

    Placed primitives retain the same construction-node identity while their
    frozen downstream stages and current editable transform are evaluated in
    the same order as :func:`primitive_to_mesh`. Unsupported legacy recipes
    raise ``TypeError`` so callers can deliberately retain their old mesh
    fallback without changing imported-mesh or export triangulation behavior.
    """

    placed = primitive if isinstance(primitive, PlacedRoomPrimitive) else None
    base = placed.primitive if placed is not None else primitive
    if not isinstance(base, (FloorPrimitive, CubePrimitive, CylinderPrimitive, SpherePrimitive, ConePrimitive, TorusPrimitive)):
        raise TypeError(f"Unsupported Maya construction primitive {type(base).__name__}.")
    kind = _construction_kind(base)
    instance_name = str(
        (placed.name if placed is not None else "")
        or getattr(base, "name", "")
        or ""
    ).strip()
    node_id = str(getattr(base, "construction_node_id", "") or "").strip() or primitive_construction_node_id(
        room_resref=room_resref,
        primitive_type=kind,
        name=instance_name,
    )
    evaluated_base = replace(base, name=instance_name, construction_node_id=node_id)

    builders: tuple[tuple[type[Any], Callable[[Any], IndexedPolygonMesh]], ...] = (
        (FloorPrimitive, build_plane_polygon_cage),
        (CubePrimitive, build_cube_polygon_cage),
        (CylinderPrimitive, build_cylinder_polygon_cage),
        (SpherePrimitive, build_sphere_polygon_cage),
        (ConePrimitive, build_cone_polygon_cage),
        (TorusPrimitive, build_torus_polygon_cage),
    )
    for primitive_type, builder in builders:
        if not isinstance(evaluated_base, primitive_type):
            continue
        cage = builder(evaluated_base)
        stages = (
            tuple(placed.evaluation_transforms or ()) + (placed.transform,)
            if placed is not None
            else ()
        )
        for stage in stages:
            cage = _transform_cage_stage(cage, stage)
        if placed is None:
            return cage
        return IndexedPolygonMesh.build(
            cage.vertices,
            cage.faces,
            vertex_channels=cage.vertex_channels,
            face_channels=cage.face_channels,
            corner_channels=cage.corner_channels,
            metadata={
                **dict(cage.metadata),
                "primitive_name": instance_name,
                "construction_node_id": node_id,
                "evaluation_transform_stages": tuple(
                    _transform_manifest(stage) for stage in tuple(placed.evaluation_transforms or ())
                ),
                "editable_transform": _transform_manifest(placed.transform),
                "transform_stage_count": len(stages),
                "construction_recipe_preserved_through_freeze": bool(placed.evaluation_transforms),
            },
        )
    raise TypeError(f"Unsupported Maya construction primitive {type(base).__name__}.")


def logical_topology_counts(mesh: IndexedPolygonMesh) -> tuple[int, int, int]:
    """Return deterministic logical vertex/edge/face counts for an inspector."""

    edges = {
        tuple(sorted((face[index], face[(index + 1) % len(face)])))
        for face in mesh.faces
        for index in range(len(face))
    }
    return len(mesh.vertices), len(edges), len(mesh.faces)


__all__ = [
    "MayaConstructionPrimitive",
    "MayaConstructionPrimitiveInstance",
    "build_authored_primitive_polygon_cage",
    "build_cone_polygon_cage",
    "build_cube_polygon_cage",
    "build_cylinder_polygon_cage",
    "build_plane_polygon_cage",
    "build_sphere_polygon_cage",
    "build_torus_polygon_cage",
    "logical_topology_counts",
]
