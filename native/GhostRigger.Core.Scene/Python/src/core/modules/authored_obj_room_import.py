"""Map Studio authoring bridge from an OBJ document to an editable room.

Core.IO owns parsing OBJ/MTL files.  This Scene-owned bridge applies explicit
authoring policy: source units, source-up to KOTOR Z-up conversion, room-local
origin placement, MDL u16 mesh-node partitioning, material ResRefs, and the
reviewed floor intent required by the walkmesh generator.
"""

from __future__ import annotations

import hashlib
import math
import re
import struct
from collections import Counter, deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from src.io.obj_room_document import ObjRoomDocument, ObjRoomSurface

from .authored_imported_mesh import (
    MDL_MAX_VERTICES_PER_SURFACE,
    ROOM_TRIANGLE_WARNING_BUDGET,
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    prepare_imported_mesh_walkmesh_generation_intent,
)
from .authored_module_project import authored_resref_blocking_issue, normalise_resref
from .authored_walkmesh_audit import EMPIRICAL_STOCK_WOK_FACE_MAX, audit_authored_wok
from .module_format import WOKData, WOKFace


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


_UNIT_SCALE_TO_METERS = {
    "millimeters": 0.001,
    "centimeters": 0.01,
    "meters": 1.0,
    "kilometers": 1000.0,
    "inches": 0.0254,
    "feet": 0.3048,
}


@dataclass(frozen=True)
class ObjRoomAuthoringOptions:
    """Explicit, KMAP-persistent decisions for importing one OBJ room."""

    room_resref: str
    game: str = "K2"
    source_units: str = "auto"
    source_up_axis: str = "y"
    scale_override: float | None = None
    center_xy: bool = True
    # Preserve authored vertical levels.  A cave's lowest bound can be a cap,
    # pit, or basement rather than the entry floor; entry placement is chosen
    # from the reviewed WOK later.
    ground_to_zero: bool = False
    included_materials: tuple[str, ...] = ()
    walkmesh_materials: tuple[str, ...] = ()
    fallback_texture_resref: str = "default"
    max_vertices_per_surface: int = 60_000
    # The IO tessellator already rejects exact zero-area triangles.  Do not use
    # an absolute metre-space threshold here: detailed props can contain valid
    # sub-millimetre faces after a centimeter-to-meter conversion.
    degenerate_area_epsilon: float = 0.0


@dataclass(frozen=True)
class ObjRoomAuthoringReport:
    source_path: str
    source_sha256: str
    source_units: str
    meters_per_source_unit: float
    source_up_axis: str
    axis_mapping: str
    translation: Vec3
    bounds_min: Vec3
    bounds_max: Vec3
    surface_count: int
    split_surface_count: int
    triangle_count: int
    skipped_degenerate_triangles: int
    texture_sources: tuple[tuple[str, str, str], ...]
    missing_texture_materials: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjWalkmeshCandidateComponent:
    """One edge-connected, up-facing floor candidate requiring user review."""

    component_id: str
    face_refs: tuple[tuple[int, int], ...]
    triangle_count: int
    area: float
    bounds_min: Vec3
    bounds_max: Vec3
    surface_names: tuple[str, ...]
    material_names: tuple[str, ...]
    recommended: bool
    recommendation: str


def obj_room_meters_per_unit(document: ObjRoomDocument, options: ObjRoomAuthoringOptions) -> tuple[str, float]:
    """Resolve source units without guessing when the OBJ has no evidence."""

    if options.scale_override is not None:
        scale = float(options.scale_override)
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("OBJ room scale override must be a finite positive meters-per-unit value.")
        return "custom", scale
    requested = str(options.source_units or "auto").strip().lower()
    units = str(document.units_hint or "").strip().lower() if requested == "auto" else requested
    if units not in _UNIT_SCALE_TO_METERS:
        if requested == "auto":
            raise ValueError(
                "The OBJ does not declare source units. Choose millimeters, centimeters, meters, inches, or feet "
                "before importing; Map Studio will not guess character scale."
            )
        raise ValueError(f"Unsupported OBJ room source units: {options.source_units!r}.")
    return units, float(_UNIT_SCALE_TO_METERS[units])


def _axis_transform(point: Vec3, *, up_axis: str, scale: float) -> Vec3:
    axis = str(up_axis or "y").strip().lower()
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    if axis in {"y", "maya", "maya_y", "maya_y_up"}:
        # Maya OBJ: X right, Y up, -Z forward -> KOTOR: X right, Y forward, Z up.
        return (scale * x, scale * -z, scale * y)
    if axis in {"z", "kotor", "z_up"}:
        return (scale * x, scale * y, scale * z)
    raise ValueError("OBJ room source up axis must be Y (Maya) or Z (KOTOR-ready).")


def _axis_mapping_label(up_axis: str) -> str:
    return "(x, y, z) -> (x, -z, y)" if str(up_axis).strip().lower() not in {"z", "kotor", "z_up"} else "identity"


def _transform_normal(normal: Vec3, *, up_axis: str) -> Vec3:
    transformed = _axis_transform(normal, up_axis=up_axis, scale=1.0)
    length = math.sqrt(sum(value * value for value in transformed))
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return tuple(value / length for value in transformed)


def _triangle_area_squared(vertices: tuple[Vec3, ...], face: Face) -> float:
    a, b, c = (vertices[int(index)] for index in face)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    return sum(value * value for value in cross) * 0.25


def _translated_surface(
    surface: ObjRoomSurface,
    *,
    scale: float,
    up_axis: str,
    translation: Vec3,
    texture: str,
    diffuse: Vec3,
    ambient: Vec3,
    area_epsilon: float,
) -> tuple[ImportedMeshSurface, int]:
    vertices = tuple(
        tuple(_axis_transform(vertex, up_axis=up_axis, scale=scale)[axis] + translation[axis] for axis in range(3))
        for vertex in surface.vertices
    )
    accepted_faces: list[Face] = []
    skipped = 0
    threshold = max(0.0, float(area_epsilon))
    for face in surface.faces:
        if _triangle_area_squared(vertices, face) <= threshold:
            skipped += 1
            continue
        accepted_faces.append(tuple(int(value) for value in face))
    return (
        ImportedMeshSurface(
            name=str(surface.name or "obj_surface")[:32],
            texture=str(texture or "")[:16],
            vertices=vertices,
            faces=tuple(accepted_faces),
            uvs=tuple(surface.uvs) if len(surface.uvs) == len(surface.vertices) else (),
            normals=(
                tuple(_transform_normal(normal, up_axis=up_axis) for normal in surface.normals)
                if len(surface.normals) == len(surface.vertices)
                else ()
            ),
            diffuse=tuple(float(value) for value in diffuse),
            ambient=tuple(float(value) for value in ambient),
            texture_names=(str(texture or "")[:16],) if str(texture or "") else (),
            tex_count=1,
        ),
        skipped,
    )


def _compact_surface_chunk(
    surface: ImportedMeshSurface,
    faces: list[Face],
    *,
    suffix: str,
) -> ImportedMeshSurface:
    used = sorted({int(index) for face in faces for index in face})
    remap = {source: target for target, source in enumerate(used)}
    return replace(
        surface,
        name=f"{str(surface.name or 'obj')[:27]}_{suffix}"[:32],
        vertices=tuple(surface.vertices[index] for index in used),
        faces=tuple(tuple(remap[int(index)] for index in face) for face in faces),
        uvs=tuple(surface.uvs[index] for index in used) if len(surface.uvs) == len(surface.vertices) else (),
        normals=(
            tuple(surface.normals[index] for index in used)
            if len(surface.normals) == len(surface.vertices)
            else ()
        ),
        uvs_lm=tuple(surface.uvs_lm[index] for index in used) if len(surface.uvs_lm) == len(surface.vertices) else (),
        face_mats=tuple(surface.face_mats[index] for index in range(len(faces))) if len(surface.face_mats) == len(faces) else (),
    )


def split_imported_surface_for_mdl(
    surface: ImportedMeshSurface,
    *,
    max_vertices: int,
) -> tuple[ImportedMeshSurface, ...]:
    """Partition one material surface into deterministic u16-safe face runs."""

    limit = int(max_vertices)
    if limit <= 2 or limit > MDL_MAX_VERTICES_PER_SURFACE:
        raise ValueError(
            f"OBJ room surface split limit must be 3..{MDL_MAX_VERTICES_PER_SURFACE} vertices."
        )
    if len(surface.vertices) <= limit:
        return (surface,)
    chunks: list[ImportedMeshSurface] = []
    faces: list[Face] = []
    used: set[int] = set()
    for face in surface.faces:
        additions = {int(index) for index in face} - used
        if faces and len(used) + len(additions) > limit:
            chunks.append(_compact_surface_chunk(surface, faces, suffix=f"{len(chunks) + 1:02d}"))
            faces = []
            used = set()
        faces.append(tuple(int(index) for index in face))
        used.update(int(index) for index in face)
    if faces:
        chunks.append(_compact_surface_chunk(surface, faces, suffix=f"{len(chunks) + 1:02d}"))
    return tuple(chunks)


def _welded_point_key(point: Vec3, epsilon: float) -> tuple[int, int, int]:
    scale = 1.0 / max(1.0e-9, float(epsilon))
    return tuple(int(round(float(value) * scale)) for value in point)


def _welded_edge_key(a: Vec3, b: Vec3, epsilon: float):
    first = _welded_point_key(a, epsilon)
    second = _welded_point_key(b, epsilon)
    return (first, second) if first <= second else (second, first)


def _face_geometry(surface: ImportedMeshSurface, face_index: int) -> tuple[Vec3, Vec3, Vec3, Vec3, float]:
    face = surface.faces[int(face_index)]
    a, b, c = (surface.vertices[int(index)] for index in face)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    length = math.sqrt(sum(value * value for value in cross))
    normal = tuple(value / length for value in cross) if length > 1.0e-12 else (0.0, 0.0, 0.0)
    return a, b, c, normal, length * 0.5


def analyze_obj_walkmesh_candidate_components(
    primitive: ImportedMeshRoomPrimitive,
    *,
    slope_max_degrees: float = 45.0,
    weld_epsilon: float = 1.0e-4,
) -> tuple[ObjWalkmeshCandidateComponent, ...]:
    """Find edge-connected up-facing candidates for explicit WOK review.

    The result intentionally includes suspicious caps and helper planes.  The
    ``recommended`` flag is a conservative UX starting point, never permission
    to export: the user still sees and confirms the component list.
    """

    threshold = math.cos(math.radians(max(1.0, min(89.0, float(slope_max_degrees)))))
    records: list[dict[str, Any]] = []
    edge_to_faces: dict[Any, list[int]] = {}
    material_names = tuple(dict(primitive.metadata or {}).get("obj_surface_materials") or ())
    for surface_index, surface in enumerate(primitive.surfaces):
        if bool(surface.backdrop or surface.background_geometry) or not bool(surface.render):
            continue
        for face_index in range(len(surface.faces)):
            a, b, c, normal, area = _face_geometry(surface, face_index)
            if area <= 1.0e-12 or normal[2] < threshold:
                continue
            record_index = len(records)
            records.append(
                {
                    "surface_index": surface_index,
                    "face_index": face_index,
                    "corners": (a, b, c),
                    "area": area,
                }
            )
            for left, right in ((a, b), (b, c), (c, a)):
                edge_to_faces.setdefault(_welded_edge_key(left, right, weld_epsilon), []).append(record_index)
    if not records:
        return ()

    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            if root_a > root_b:
                root_a, root_b = root_b, root_a
            parent[root_b] = root_a

    for adjacent in edge_to_faces.values():
        if len(adjacent) < 2:
            continue
        first = adjacent[0]
        for other in adjacent[1:]:
            union(first, other)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for index, record in enumerate(records):
        grouped.setdefault(find(index), []).append(record)
    ordered = sorted(
        grouped.values(),
        key=lambda rows: (
            -sum(float(row["area"]) for row in rows),
            int(rows[0]["surface_index"]),
            int(rows[0]["face_index"]),
        ),
    )
    components: list[ObjWalkmeshCandidateComponent] = []
    for ordinal, rows in enumerate(ordered, start=1):
        corners = [corner for row in rows for corner in row["corners"]]
        area = sum(float(row["area"]) for row in rows)
        count = len(rows)
        surface_indices = sorted({int(row["surface_index"]) for row in rows})
        surfaces = tuple(str(primitive.surfaces[index].name or f"surface_{index}") for index in surface_indices)
        materials = tuple(
            dict.fromkeys(
                str(material_names[index] if index < len(material_names) else primitive.surfaces[index].texture or "")
                for index in surface_indices
            )
        )
        average_area = area / max(1, count)
        textured = any(
            str(primitive.surfaces[index].texture or "").strip().lower() not in {"", "default"}
            for index in surface_indices
        )
        recommended = bool(count >= 64 and area >= 10.0 and average_area <= 1.0 and textured)
        if recommended:
            recommendation = "Likely authored terrain/floor: substantial, detailed, textured component."
        elif count <= 4 and area >= 20.0:
            recommendation = "Excluded by default: very large low-detail plane, likely a helper/cap."
        elif not textured:
            recommendation = "Excluded by default: untextured component; classify it explicitly."
        elif area < 1.0:
            recommendation = "Excluded by default: small ledge/detail component."
        else:
            recommendation = "Review manually before including in collision."
        components.append(
            ObjWalkmeshCandidateComponent(
                component_id=f"floor_{ordinal:04d}",
                face_refs=tuple(
                    (int(row["surface_index"]), int(row["face_index"]))
                    for row in rows
                ),
                triangle_count=count,
                area=float(area),
                bounds_min=tuple(min(corner[axis] for corner in corners) for axis in range(3)),
                bounds_max=tuple(max(corner[axis] for corner in corners) for axis in range(3)),
                surface_names=surfaces,
                material_names=materials,
                recommended=recommended,
                recommendation=recommendation,
            )
        )
    return tuple(components)


def apply_obj_walkmesh_component_review(
    primitive: ImportedMeshRoomPrimitive,
    components: tuple[ObjWalkmeshCandidateComponent, ...],
    *,
    selected_component_ids: tuple[str, ...],
    reason: str,
) -> ImportedMeshRoomPrimitive:
    """Persist an explicit component review as face-level WOK intent."""

    selected_ids = {str(value) for value in tuple(selected_component_ids or ()) if str(value)}
    if not selected_ids:
        raise ValueError("Select at least one reviewed floor component before generating a walkmesh.")
    available = {component.component_id: component for component in components}
    missing = sorted(selected_ids - set(available))
    if missing:
        raise ValueError("Unknown or stale OBJ floor component selection: " + ", ".join(missing))
    faces: dict[int, list[int]] = {}
    selected_rows: list[dict[str, Any]] = []
    for component_id in sorted(selected_ids):
        component = available[component_id]
        for surface_index, face_index in component.face_refs:
            faces.setdefault(int(surface_index), []).append(int(face_index))
        selected_rows.append(
            {
                "component_id": component.component_id,
                "triangle_count": component.triangle_count,
                "area": component.area,
                "bounds_min": list(component.bounds_min),
                "bounds_max": list(component.bounds_max),
                "surface_names": list(component.surface_names),
                "material_names": list(component.material_names),
            }
        )
    reviewed = prepare_imported_mesh_walkmesh_generation_intent(
        primitive,
        surface_faces={index: tuple(sorted(set(indices))) for index, indices in faces.items()},
        reason=str(reason or "").strip(),
    )
    metadata = dict(reviewed.metadata or {})
    metadata["obj_walkmesh_component_review"] = {
        "version": 1,
        "slope_source": "up_facing_component_analysis",
        "selected_components": selected_rows,
    }
    return replace(reviewed, metadata=metadata)


def _triangle_is_walkable(a: Vec3, b: Vec3, c: Vec3, minimum_normal_z: float) -> bool:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return length > 1.0e-10 and nz / length >= minimum_normal_z


@dataclass(frozen=True)
class _WalkmeshTopologySignature:
    """Index-topology facts that an authored simplification may not change."""

    face_component_count: int
    boundary_edge_count: int
    boundary_group_count: int
    boundary_degree_histogram: tuple[tuple[int, int], ...]
    euler_characteristic: int
    non_manifold_edge_count: int
    orientation_conflict_count: int
    duplicate_face_count: int
    invalid_face_count: int
    degenerate_face_count: int
    steep_face_count: int

    def report(self) -> dict[str, Any]:
        return {
            "face_component_count": self.face_component_count,
            "boundary_edge_count": self.boundary_edge_count,
            "boundary_group_count": self.boundary_group_count,
            "boundary_degree_histogram": {
                str(degree): count for degree, count in self.boundary_degree_histogram
            },
            "euler_characteristic": self.euler_characteristic,
            "non_manifold_edge_count": self.non_manifold_edge_count,
            "orientation_conflict_count": self.orientation_conflict_count,
            "duplicate_face_count": self.duplicate_face_count,
            "invalid_face_count": self.invalid_face_count,
            "degenerate_face_count": self.degenerate_face_count,
            "steep_face_count": self.steep_face_count,
        }


@dataclass
class _WalkmeshSimplificationPlan:
    component: ObjWalkmeshCandidateComponent
    points: Any
    faces: Any
    source_signature: _WalkmeshTopologySignature
    boundary_fingerprint: tuple[Any, ...]
    protected_boundary_vertex_count: int
    accepted_collapses: Any
    rejected_collapse_count: int
    minimum_points: Any
    minimum_faces: Any


def _indexed_component_mesh(
    primitive: ImportedMeshRoomPrimitive,
    component: ObjWalkmeshCandidateComponent,
    *,
    weld_epsilon: float,
) -> tuple[Any, Any]:
    """Build collision indices from one reviewed render component.

    OBJ vertices are split at UV/normal seams.  The reviewed component finder
    already uses position-aware edge connectivity, so its collision copy must
    perform the same deterministic weld.  Components are processed separately;
    this never welds an upper floor to geometry below it.
    """

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - NumPy is a core dependency.
        raise RuntimeError("OBJ walkmesh generation requires NumPy 2.0 or newer.") from exc

    points: list[Vec3] = []
    indices_by_key: dict[tuple[int, int, int], int] = {}
    faces: list[Face] = []
    for surface_index, face_index in component.face_refs:
        surface = primitive.surfaces[int(surface_index)]
        source_face = surface.faces[int(face_index)]
        triangle: list[int] = []
        for source_index in source_face:
            point = tuple(float(value) for value in surface.vertices[int(source_index)])
            key = _welded_point_key(point, weld_epsilon)
            target_index = indices_by_key.get(key)
            if target_index is None:
                target_index = len(points)
                indices_by_key[key] = target_index
                points.append(point)
            triangle.append(target_index)
        faces.append(tuple(triangle))
    return np.asarray(points, dtype=np.float64), np.asarray(faces, dtype=np.int32)


def _walkmesh_topology_signature(
    points: Any,
    faces: Any,
    *,
    minimum_normal_z: float,
) -> tuple[_WalkmeshTopologySignature, set[int], tuple[Any, ...]]:
    """Return exact indexed topology plus a directed geometric boundary key."""

    point_count = int(len(points))
    owners: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    invalid_faces = 0
    degenerate_faces = 0
    steep_faces = 0
    canonical_faces: Counter[tuple[int, int, int]] = Counter()
    used_vertices: set[int] = set()
    valid_face_indices: list[int] = []
    for face_index, row in enumerate(faces):
        triangle = tuple(int(value) for value in row)
        if len(triangle) != 3 or any(index < 0 or index >= point_count for index in triangle):
            invalid_faces += 1
            continue
        if len(set(triangle)) < 3:
            degenerate_faces += 1
            continue
        a, b, c = (tuple(float(value) for value in points[index]) for index in triangle)
        if not all(math.isfinite(value) for point in (a, b, c) for value in point):
            invalid_faces += 1
            continue
        area_squared = _triangle_area_squared((a, b, c), (0, 1, 2))
        if area_squared <= 1.0e-12:
            degenerate_faces += 1
            continue
        if not _triangle_is_walkable(a, b, c, minimum_normal_z):
            steep_faces += 1
        canonical_faces[tuple(sorted(triangle))] += 1
        used_vertices.update(triangle)
        valid_face_indices.append(face_index)
        for local_edge in range(3):
            left = triangle[local_edge]
            right = triangle[(local_edge + 1) % 3]
            key = (left, right) if left <= right else (right, left)
            owners.setdefault(key, []).append((face_index, left, right))

    duplicate_faces = sum(max(0, count - 1) for count in canonical_faces.values())
    non_manifold_edges = sum(1 for rows in owners.values() if len(rows) > 2)
    orientation_conflicts = sum(
        1
        for rows in owners.values()
        if len(rows) == 2 and rows[0][1:] == rows[1][1:]
    )
    face_neighbors: dict[int, set[int]] = {index: set() for index in valid_face_indices}
    for rows in owners.values():
        if len(rows) == 2:
            first, second = rows[0][0], rows[1][0]
            face_neighbors[first].add(second)
            face_neighbors[second].add(first)
    remaining_faces = set(valid_face_indices)
    component_count = 0
    while remaining_faces:
        component_count += 1
        queue = deque((remaining_faces.pop(),))
        while queue:
            face_index = queue.popleft()
            for neighbor in face_neighbors.get(face_index, ()):
                if neighbor in remaining_faces:
                    remaining_faces.remove(neighbor)
                    queue.append(neighbor)

    boundary_rows = [rows[0] for rows in owners.values() if len(rows) == 1]
    boundary_vertices = {vertex for _, left, right in boundary_rows for vertex in (left, right)}
    boundary_graph: dict[int, set[int]] = {}
    for _, left, right in boundary_rows:
        boundary_graph.setdefault(left, set()).add(right)
        boundary_graph.setdefault(right, set()).add(left)
    remaining_boundary = set(boundary_graph)
    boundary_groups = 0
    while remaining_boundary:
        boundary_groups += 1
        queue = deque((remaining_boundary.pop(),))
        while queue:
            vertex = queue.popleft()
            for neighbor in boundary_graph.get(vertex, ()):
                if neighbor in remaining_boundary:
                    remaining_boundary.remove(neighbor)
                    queue.append(neighbor)
    degree_histogram = tuple(sorted(Counter(len(rows) for rows in boundary_graph.values()).items()))

    # Preserve exact directed boundary geometry, not merely the number of
    # loops.  This keeps every outer rim, hole, island, pinch, and its winding.
    boundary_geometry = Counter()
    for _, left, right in boundary_rows:
        start = _welded_point_key(tuple(float(value) for value in points[left]), 1.0e-4)
        end = _welded_point_key(tuple(float(value) for value in points[right]), 1.0e-4)
        boundary_geometry[(start, end)] += 1
    boundary_fingerprint = tuple(sorted(boundary_geometry.items()))
    signature = _WalkmeshTopologySignature(
        face_component_count=component_count,
        boundary_edge_count=len(boundary_rows),
        boundary_group_count=boundary_groups,
        boundary_degree_histogram=degree_histogram,
        euler_characteristic=len(used_vertices) - len(owners) + len(valid_face_indices),
        non_manifold_edge_count=non_manifold_edges,
        orientation_conflict_count=orientation_conflicts,
        duplicate_face_count=duplicate_faces,
        invalid_face_count=invalid_faces,
        degenerate_face_count=degenerate_faces,
        steep_face_count=steep_faces,
    )
    return signature, boundary_vertices, boundary_fingerprint


def _topology_matches_source(
    source_signature: _WalkmeshTopologySignature,
    source_boundary: tuple[Any, ...],
    points: Any,
    faces: Any,
    *,
    minimum_normal_z: float,
) -> bool:
    signature, _, boundary = _walkmesh_topology_signature(
        points,
        faces,
        minimum_normal_z=minimum_normal_z,
    )
    return bool(signature == source_signature and boundary == source_boundary)


def _structural_topology_matches_source(
    source_signature: _WalkmeshTopologySignature,
    source_boundary: tuple[Any, ...],
    points: Any,
    faces: Any,
    *,
    minimum_normal_z: float,
) -> bool:
    """Compare topology while deferring slope repair to its batched pass."""

    signature, _, boundary = _walkmesh_topology_signature(
        points,
        faces,
        minimum_normal_z=minimum_normal_z,
    )
    return bool(
        replace(signature, steep_face_count=source_signature.steep_face_count) == source_signature
        and boundary == source_boundary
    )


def _replay_walkmesh_collapses(
    points: Any,
    faces: Any,
    collapses: Any,
    simplifier: Any,
) -> tuple[Any, Any, Any]:
    import numpy as np

    if not len(collapses):
        return points.copy(), faces.copy(), np.arange(len(points), dtype=np.int32)

    output_points, output_faces, mapping = simplifier.replay_simplification(
        np.asarray(points, dtype=np.float32),
        np.asarray(faces, dtype=np.int32),
        np.ascontiguousarray(collapses, dtype=np.int32),
    )
    return output_points, output_faces, mapping


def _first_invalid_collapse_index(
    points: Any,
    faces: Any,
    collapses: Any,
    simplifier: Any,
    *,
    source_signature: _WalkmeshTopologySignature,
    source_boundary: tuple[Any, ...],
    minimum_normal_z: float,
) -> int:
    """Locate the first irreversible topology/geometry-changing collapse."""

    low = 0  # The empty prefix is the validated source mesh.
    high = len(collapses)  # The caller established that this prefix is invalid.
    while high - low > 1:
        middle = (low + high) // 2
        output_points, output_faces, _ = _replay_walkmesh_collapses(
            points,
            faces,
            collapses[:middle],
            simplifier,
        )
        if _structural_topology_matches_source(
            source_signature,
            source_boundary,
            output_points,
            output_faces,
            minimum_normal_z=minimum_normal_z,
        ):
            low = middle
        else:
            high = middle
    return max(0, high - 1)


def _steep_walkmesh_faces(points: Any, faces: Any, minimum_normal_z: float) -> tuple[tuple[int, int, int], ...]:
    rows: list[tuple[int, int, int]] = []
    for row in faces:
        triangle = tuple(int(value) for value in row)
        a, b, c = (tuple(float(value) for value in points[index]) for index in triangle)
        if not _triangle_is_walkable(a, b, c, minimum_normal_z):
            rows.append(triangle)
    return tuple(rows)


def _build_walkmesh_simplification_plan(
    primitive: ImportedMeshRoomPrimitive,
    component: ObjWalkmeshCandidateComponent,
    simplifier: Any,
    *,
    minimum_normal_z: float,
    weld_epsilon: float = 1.0e-4,
) -> _WalkmeshSimplificationPlan:
    """Build a boundary-locked QEM plan and remove unsafe collapses."""

    import numpy as np

    points, faces = _indexed_component_mesh(
        primitive,
        component,
        weld_epsilon=weld_epsilon,
    )
    source_signature, boundary_vertices, boundary = _walkmesh_topology_signature(
        points,
        faces,
        minimum_normal_z=minimum_normal_z,
    )
    unsafe_source = (
        source_signature.invalid_face_count
        + source_signature.degenerate_face_count
        + source_signature.non_manifold_edge_count
        + source_signature.orientation_conflict_count
        + source_signature.duplicate_face_count
        + source_signature.steep_face_count
    )
    if unsafe_source:
        raise ValueError(
            f"Reviewed OBJ floor component {component.component_id} is not safe walkmesh input: "
            f"{source_signature.report()}. Repair/review its collision topology before simplification."
        )
    if len(faces) <= 2:
        collapses = np.empty((0, 2), dtype=np.int32)
        minimum_points, minimum_faces = points.copy(), faces.copy()
        rejected = 0
    else:
        _, _, history = simplifier.simplify(
            points,
            faces,
            target_count=2,
            agg=5.0,
            return_collapses=True,
        )
        collapses = np.asarray(
            [
                pair
                for pair in history
                if int(pair[0]) not in boundary_vertices and int(pair[1]) not in boundary_vertices
            ],
            dtype=np.int32,
        ).reshape((-1, 2))
        rejected = int(len(history) - len(collapses))
        # QEM knows shape, but not Odyssey's exact boundary/perimeter contract.
        # Topological loss is irreversible along an edge-collapse stream, so a
        # binary search locates the first offending collapse.  In practice this
        # is a tiny set (often zero) and avoids a per-collapse O(F) replay.
        for _ in range(64):
            minimum_points, minimum_faces, _ = _replay_walkmesh_collapses(
                points,
                faces,
                collapses,
                simplifier,
            )
            if _structural_topology_matches_source(
                source_signature,
                boundary,
                minimum_points,
                minimum_faces,
                minimum_normal_z=minimum_normal_z,
            ):
                break
            if not len(collapses):
                raise ValueError(
                    f"OBJ floor component {component.component_id} could not preserve its source topology."
                )
            unsafe_index = _first_invalid_collapse_index(
                points,
                faces,
                collapses,
                simplifier,
                source_signature=source_signature,
                source_boundary=boundary,
                minimum_normal_z=minimum_normal_z,
            )
            collapses = np.delete(collapses, unsafe_index, axis=0)
            rejected += 1
        else:
            raise ValueError(
                f"OBJ floor component {component.component_id} required more than 64 topology-changing QEM collapse "
                "rejections. Split/repair the room rather than emitting uncertain collision."
            )

        # Slope failures are not monotonic: a later collapse can remove a bad
        # triangle, so binary-searching each failure is both slow and wrong.
        # Use replay's original->output mapping to find the latest collapse in
        # every unsafe output-vertex cluster, reject those collapses together,
        # and re-evaluate.  Dathomir's 13k-face floor converges in a handful of
        # batched replays instead of thousands of full signature scans.
        for _ in range(64):
            minimum_points, minimum_faces, mapping = _replay_walkmesh_collapses(
                points,
                faces,
                collapses,
                simplifier,
            )
            steep_faces = _steep_walkmesh_faces(minimum_points, minimum_faces, minimum_normal_z)
            if not steep_faces:
                if not _topology_matches_source(
                    source_signature,
                    boundary,
                    minimum_points,
                    minimum_faces,
                    minimum_normal_z=minimum_normal_z,
                ):
                    raise ValueError(
                        f"OBJ floor component {component.component_id} changed topology during slope repair."
                    )
                break
            unsafe_output_vertices = {index for triangle in steep_faces for index in triangle}
            latest_by_output: dict[int, int] = {}
            for collapse_index, pair in enumerate(collapses):
                for source_index in (int(pair[0]), int(pair[1])):
                    output_index = int(mapping[source_index])
                    if output_index in unsafe_output_vertices:
                        latest_by_output[output_index] = collapse_index
            remove_indices = {
                max(latest_by_output[index] for index in triangle if index in latest_by_output)
                for triangle in steep_faces
                if any(index in latest_by_output for index in triangle)
            }
            if not remove_indices:
                raise ValueError(
                    f"OBJ floor component {component.component_id} produced an unsafe slope that could not be "
                    "traced to a QEM collapse. Repair the reviewed source surface."
                )
            collapses = np.delete(collapses, sorted(remove_indices), axis=0)
            rejected += len(remove_indices)
        else:
            raise ValueError(
                f"OBJ floor component {component.component_id} did not converge after 64 batched slope repairs."
            )
    return _WalkmeshSimplificationPlan(
        component=component,
        points=points,
        faces=faces,
        source_signature=source_signature,
        boundary_fingerprint=boundary,
        protected_boundary_vertex_count=len(boundary_vertices),
        accepted_collapses=collapses,
        rejected_collapse_count=rejected,
        minimum_points=minimum_points,
        minimum_faces=minimum_faces,
    )


def _allocate_walkmesh_component_budgets(
    plans: tuple[_WalkmeshSimplificationPlan, ...],
    total_budget: int,
) -> tuple[int, ...]:
    """Allocate remaining quality without starving a small floor level."""

    minimums = [len(plan.minimum_faces) for plan in plans]
    sources = [len(plan.faces) for plan in plans]
    minimum_total = sum(minimums)
    if minimum_total > total_budget:
        detail = ", ".join(
            f"{plan.component.component_id} needs at least {minimums[index]}"
            for index, plan in enumerate(plans)
        )
        raise ValueError(
            f"The reviewed floor boundaries require at least {minimum_total} faces, above the requested "
            f"{total_budget}-face KOTOR budget ({detail}). Split the room or simplify its reviewed boundary "
            "in Map Studio; holes/levels will not be erased automatically."
        )
    targets = list(minimums)
    remaining = min(int(total_budget - minimum_total), sum(sources) - minimum_total)
    capacities = [source - minimum for source, minimum in zip(sources, minimums)]
    while remaining > 0 and any(capacity > 0 for capacity in capacities):
        total_capacity = sum(capacities)
        grants = [min(capacity, int(remaining * capacity / total_capacity)) for capacity in capacities]
        if not any(grants):
            grants[max(range(len(capacities)), key=lambda index: capacities[index])] = 1
        granted = min(remaining, sum(grants))
        if sum(grants) > granted:
            overflow = sum(grants) - granted
            for index in reversed(range(len(grants))):
                take = min(overflow, grants[index])
                grants[index] -= take
                overflow -= take
                if not overflow:
                    break
        for index, grant in enumerate(grants):
            targets[index] += grant
            capacities[index] -= grant
        remaining -= sum(grants)
    return tuple(targets)


def _replay_to_face_budget(
    plan: _WalkmeshSimplificationPlan,
    face_budget: int,
    simplifier: Any,
    *,
    minimum_normal_z: float,
) -> tuple[Any, Any, int]:
    if len(plan.faces) <= face_budget or not len(plan.accepted_collapses):
        return plan.points.copy(), plan.faces.copy(), 0
    low = 0
    high = len(plan.accepted_collapses)
    while low < high:
        middle = (low + high) // 2
        output_points, output_faces, _ = _replay_walkmesh_collapses(
            plan.points,
            plan.faces,
            plan.accepted_collapses[: middle + 1],
            simplifier,
        )
        if len(output_faces) <= face_budget:
            high = middle
        else:
            low = middle + 1
    applied = min(len(plan.accepted_collapses), low + 1)
    output_points, output_faces, _ = _replay_walkmesh_collapses(
        plan.points,
        plan.faces,
        plan.accepted_collapses[:applied],
        simplifier,
    )
    if len(output_faces) > face_budget:
        raise ValueError(
            f"Boundary-constrained simplification of {plan.component.component_id} could not meet its "
            f"{face_budget}-face allocation without changing walkmesh topology."
        )
    if not _topology_matches_source(
        plan.source_signature,
        plan.boundary_fingerprint,
        output_points,
        output_faces,
        minimum_normal_z=minimum_normal_z,
    ):
        # An intermediate prefix can transiently create a steep face that a
        # later safe collapse removes.  The fully repaired minimum is already
        # proven and is preferable to either emitting it or another slow scan.
        output_points = plan.minimum_points.copy()
        output_faces = plan.minimum_faces.copy()
        applied = len(plan.accepted_collapses)
    return output_points, output_faces, applied


def generate_adaptive_obj_walkmesh(
    primitive: ImportedMeshRoomPrimitive,
    components: tuple[ObjWalkmeshCandidateComponent, ...],
    *,
    selected_component_ids: tuple[str, ...],
    target_face_budget: int = 1_800,
    slope_max_degrees: float = 45.0,
    minimum_cell_size: float = 0.15,
    maximum_cell_size: float = 4.0,
) -> tuple[ImportedMeshRoomPrimitive, dict[str, Any]]:
    """Create a boundary-constrained, topology-preserving floor-only WOK.

    Each reviewed component is simplified independently.  All source boundary
    vertices are locked, so holes, islands, stacked levels, pinches, and exact
    perimeter winding survive.  Unsafe QEM collapses are removed and the final
    BWM is independently re-read.  ``minimum_cell_size`` and
    ``maximum_cell_size`` remain accepted for KMAP/API compatibility with the
    retired raster prototype, but do not control this topology-safe path.
    """

    selected = {str(value) for value in tuple(selected_component_ids or ()) if str(value)}
    selected_components = tuple(component for component in components if component.component_id in selected)
    if not selected_components or len(selected_components) != len(selected):
        raise ValueError("Adaptive walkmesh generation requires current reviewed floor component IDs.")
    budget = int(target_face_budget)
    if budget < 2 or budget > 4_096:
        raise ValueError(
            "Adaptive OBJ walkmesh target must be 2..4096 faces. The studied vanilla maximum is 2136; "
            "higher budgets are an explicit extended-envelope candidate that still requires retail proof."
        )
    minimum_normal_z = math.cos(math.radians(max(1.0, min(89.0, float(slope_max_degrees)))))
    try:
        import fast_simplification as simplifier
    except ImportError as exc:
        raise RuntimeError(
            "Topology-safe OBJ walkmesh reduction requires fast-simplification>=0.1.13. "
            "Install the Map Studio mesh-processing dependency; the retired raster fallback is intentionally "
            "not used because it can erase holes and fragment floor levels."
        ) from exc

    plans = tuple(
        _build_walkmesh_simplification_plan(
            primitive,
            component,
            simplifier,
            minimum_normal_z=minimum_normal_z,
        )
        for component in selected_components
    )
    allocations = _allocate_walkmesh_component_budgets(plans, budget)

    vertices: list[Vec3] = []
    faces: list[WOKFace] = []
    component_reports: list[dict[str, Any]] = []
    for plan, allocation in zip(plans, allocations):
        output_points, output_faces, applied_collapses = _replay_to_face_budget(
            plan,
            allocation,
            simplifier,
            minimum_normal_z=minimum_normal_z,
        )
        vertex_offset = len(vertices)
        vertices.extend(tuple(float(value) for value in point) for point in output_points)
        first_face = len(faces)
        faces.extend(
            WOKFace(
                vertex_offset + int(row[0]),
                vertex_offset + int(row[1]),
                vertex_offset + int(row[2]),
                4,
                -1,
                -1,
                -1,
            )
            for row in output_faces
        )
        output_signature, _, _ = _walkmesh_topology_signature(
            output_points,
            output_faces,
            minimum_normal_z=minimum_normal_z,
        )
        component_reports.append(
            {
                "component_id": plan.component.component_id,
                "source_faces": len(plan.faces),
                "source_vertices": len(plan.points),
                "protected_boundary_vertices": plan.protected_boundary_vertex_count,
                "minimum_topology_preserving_faces": len(plan.minimum_faces),
                "allocated_face_budget": allocation,
                "generated_faces": len(faces) - first_face,
                "generated_vertices": len(output_points),
                "applied_qem_collapses": applied_collapses,
                "rejected_qem_collapses": plan.rejected_collapse_count,
                "source_topology": plan.source_signature.report(),
                "output_topology": output_signature.report(),
                "topology_preserved": output_signature == plan.source_signature,
            }
        )

    if not faces:
        raise ValueError("Adaptive OBJ walkmesh produced no walkable faces; review floor components and scale.")
    if len(faces) > budget:
        raise ValueError(
            f"Adaptive OBJ walkmesh produced {len(faces)} faces, above the requested {budget}-face budget; "
            "increase cell size or split the room."
        )
    wok = WOKData(name=str(primitive.room_resref or ""), verts=vertices, faces=faces)
    wok.rebuild_adjacencies()
    audit = audit_authored_wok(str(primitive.room_resref or ""), wok)
    expected_components = sum(plan.source_signature.face_component_count for plan in plans)
    if (
        audit.invalid_face_count
        or audit.non_manifold_edge_count
        or audit.degenerate_face_count
        or audit.walkable_component_count != expected_components
    ):
        raise ValueError(
            "Adaptive OBJ walkmesh failed topology validation: "
            f"{audit.invalid_face_count} invalid face(s), {audit.non_manifold_edge_count} non-manifold edge(s), "
            f"{audit.degenerate_face_count} degenerate face(s), and {audit.walkable_component_count}/"
            f"{expected_components} expected connected floor component(s)."
        )
    raw = wok.to_bytes()
    if len(raw) < 136 or raw[:8] != b"BWM V1.0":
        raise ValueError("Adaptive OBJ walkmesh writer did not emit a complete BWM V1.0 resource.")
    counts = struct.unpack_from("<16I", raw, 72)
    serialized_vertices = int(counts[0])
    serialized_faces = int(counts[2])
    serialized_aabb = int(counts[7])
    serialized_aabb_root = int(counts[9])
    serialized_adjacencies = int(counts[10])
    serialized_boundaries = int(counts[12])
    serialized_perimeters = int(counts[14])
    if serialized_faces != len(faces) or serialized_vertices != len(vertices):
        raise ValueError("Adaptive OBJ walkmesh serialized counts do not match the authored collision mesh.")
    if serialized_aabb != 2 * len(faces) - 1 or serialized_aabb_root != 0:
        raise ValueError("Adaptive OBJ walkmesh does not contain the complete KOTOR AABB tree.")
    if serialized_adjacencies != len(faces):
        raise ValueError("Adaptive OBJ walkmesh does not serialize the complete walkable adjacency domain.")
    if serialized_boundaries != audit.open_edge_count:
        raise ValueError(
            "Adaptive OBJ walkmesh serialized boundary rows do not cover every indexed perimeter edge."
        )
    if serialized_perimeters < max(1, expected_components) or serialized_boundaries < serialized_perimeters:
        raise ValueError("Adaptive OBJ walkmesh does not serialize every walkable perimeter/island loop.")
    readback = WOKData.from_bytes(raw)
    if len(readback.faces) != len(faces):
        raise ValueError("Adaptive OBJ walkmesh readback lost collision faces.")
    readback_signature, _, _ = _walkmesh_topology_signature(
        readback.verts,
        tuple((face.v1, face.v2, face.v3) for face in readback.faces),
        minimum_normal_z=minimum_normal_z,
    )
    authored_signature, _, _ = _walkmesh_topology_signature(
        vertices,
        tuple((face.v1, face.v2, face.v3) for face in faces),
        minimum_normal_z=minimum_normal_z,
    )
    if readback_signature != authored_signature:
        raise ValueError("Adaptive OBJ walkmesh readback changed indexed topology or walkable slope state.")

    metadata = dict(primitive.metadata or {})
    metadata["wok_coordinate_space"] = "room_local"
    metadata["obj_adaptive_walkmesh"] = {
        "version": 1,
        "selected_component_ids": sorted(selected),
        "target_face_budget": budget,
        "simplifier": "boundary_constrained_qem",
        "slope_max_degrees": float(slope_max_degrees),
        "boundary_policy": "lock_all_directed_boundary_vertices_and_reject_topology_changes",
        "component_reports": component_reports,
        "serialized_face_count": serialized_faces,
        "serialized_aabb_count": serialized_aabb,
        "serialized_perimeter_loop_count": serialized_perimeters,
        "empirical_vanilla_face_max": EMPIRICAL_STOCK_WOK_FACE_MAX,
        "vanilla_envelope_exceeded": serialized_faces > EMPIRICAL_STOCK_WOK_FACE_MAX,
        "structural_warnings": list(audit.warnings),
    }
    updated = replace(primitive, wok=wok, metadata=metadata)
    report = {
        "source_face_count": sum(component.triangle_count for component in selected_components),
        "generated_face_count": len(faces),
        "generated_vertex_count": len(vertices),
        "target_face_budget": budget,
        "simplifier": "boundary_constrained_qem",
        "minimum_topology_preserving_face_count": sum(len(plan.minimum_faces) for plan in plans),
        "component_face_allocations": allocations,
        "walkable_component_count": audit.walkable_component_count,
        "disconnected_component_count": audit.disconnected_component_count,
        "serialized_aabb_count": serialized_aabb,
        "serialized_boundary_edge_count": serialized_boundaries,
        "serialized_perimeter_loop_count": serialized_perimeters,
        "empirical_vanilla_face_max": EMPIRICAL_STOCK_WOK_FACE_MAX,
        "vanilla_envelope_exceeded": serialized_faces > EMPIRICAL_STOCK_WOK_FACE_MAX,
        "structural_validation": "passed",
        "warnings": tuple(audit.warnings),
        "component_reports": component_reports,
    }
    return updated, report


def _material_texture_rows(
    document: ObjRoomDocument,
    mapping: dict[str, str],
    fallback: str,
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    used = {surface.material_name for surface in document.surfaces}
    for material in document.materials:
        if material.name not in used:
            continue
        rows.append(
            (
                material.name,
                str(mapping.get(material.name) or fallback or "")[:16],
                str(material.diffuse_texture_path or ""),
            )
        )
    return tuple(rows)


def build_obj_room_primitive(
    document: ObjRoomDocument,
    options: ObjRoomAuthoringOptions,
    *,
    material_texture_resrefs: dict[str, str] | None = None,
) -> tuple[ImportedMeshRoomPrimitive, ObjRoomAuthoringReport]:
    """Build one editable, u16-safe room primitive from parsed OBJ data."""

    issue = authored_resref_blocking_issue("OBJ room", options.room_resref)
    if issue:
        raise ValueError(issue)
    game = str(options.game or "K2").strip().upper()
    if game not in {"K1", "K2"}:
        raise ValueError("OBJ room target game must be K1 or K2.")
    units, scale = obj_room_meters_per_unit(document, options)
    up_axis = str(options.source_up_axis or "y").strip().lower()

    transformed_corners = tuple(
        _axis_transform(corner, up_axis=up_axis, scale=scale)
        for corner in (
            document.bounds_min,
            document.bounds_max,
            (document.bounds_min[0], document.bounds_min[1], document.bounds_max[2]),
            (document.bounds_min[0], document.bounds_max[1], document.bounds_min[2]),
            (document.bounds_max[0], document.bounds_min[1], document.bounds_min[2]),
            (document.bounds_min[0], document.bounds_max[1], document.bounds_max[2]),
            (document.bounds_max[0], document.bounds_min[1], document.bounds_max[2]),
            (document.bounds_max[0], document.bounds_max[1], document.bounds_min[2]),
        )
    )
    raw_min = tuple(min(point[axis] for point in transformed_corners) for axis in range(3))
    raw_max = tuple(max(point[axis] for point in transformed_corners) for axis in range(3))
    translation = [0.0, 0.0, 0.0]
    if options.center_xy:
        translation[0] = -0.5 * (raw_min[0] + raw_max[0])
        translation[1] = -0.5 * (raw_min[1] + raw_max[1])
    if options.ground_to_zero:
        translation[2] = -raw_min[2]
    translation_tuple = tuple(float(value) for value in translation)
    bounds_min = tuple(raw_min[axis] + translation_tuple[axis] for axis in range(3))
    bounds_max = tuple(raw_max[axis] + translation_tuple[axis] for axis in range(3))

    included = {str(value) for value in tuple(options.included_materials or ()) if str(value)}
    selected_sources = tuple(
        surface for surface in document.surfaces if not included or surface.material_name in included
    )
    if not selected_sources:
        raise ValueError("OBJ room import selection contains no material surfaces.")
    texture_mapping = dict(material_texture_resrefs or {})
    material_by_name = {material.name: material for material in document.materials}
    imported_surfaces: list[ImportedMeshSurface] = []
    output_material_names: list[str] = []
    source_to_output_indices: dict[str, list[int]] = {}
    skipped_degenerate = 0
    for source_surface in selected_sources:
        material = material_by_name.get(source_surface.material_name)
        texture = str(
            texture_mapping.get(source_surface.material_name)
            or options.fallback_texture_resref
            or ""
        )
        has_diffuse_image = bool(material is not None and material.diffuse_texture and material.texture_exists)
        converted, skipped = _translated_surface(
            source_surface,
            scale=scale,
            up_axis=up_axis,
            translation=translation_tuple,
            texture=texture,
            # Maya's Stingray/standardSurface MTL export commonly writes Kd/Ka
            # black while the base-color map carries all visible color.  KOTOR
            # multiplies the texture by these channels, so use neutral white
            # for a resolved image instead of importing an accidentally black
            # room.
            diffuse=(1.0, 1.0, 1.0) if has_diffuse_image else (
                tuple(material.diffuse) if material is not None else (0.8, 0.8, 0.8)
            ),
            ambient=(1.0, 1.0, 1.0) if has_diffuse_image else (
                tuple(material.ambient) if material is not None else (0.2, 0.2, 0.2)
            ),
            area_epsilon=float(options.degenerate_area_epsilon),
        )
        skipped_degenerate += skipped
        if not converted.faces:
            continue
        chunks = split_imported_surface_for_mdl(
            converted,
            max_vertices=int(options.max_vertices_per_surface),
        )
        for chunk in chunks:
            source_to_output_indices.setdefault(source_surface.material_name, []).append(len(imported_surfaces))
            imported_surfaces.append(chunk)
            output_material_names.append(source_surface.material_name)
    if not imported_surfaces:
        raise ValueError("OBJ room import produced no non-degenerate triangle surfaces.")

    texture_rows = _material_texture_rows(document, texture_mapping, options.fallback_texture_resref)
    missing_texture_materials = tuple(
        material.name
        for material in document.materials
        if material.name in {surface.material_name for surface in selected_sources}
        and (not material.diffuse_texture or not material.texture_exists)
    )
    warnings = list(document.warnings)
    total_triangles = sum(len(surface.faces) for surface in imported_surfaces)
    if total_triangles > ROOM_TRIANGLE_WARNING_BUDGET:
        warnings.append(
            f"Imported OBJ room contains {total_triangles} render triangles, above Map Studio's "
            f"{ROOM_TRIANGLE_WARNING_BUDGET}-triangle room guidance; split it into spatial rooms or create LOD geometry "
            "before retail proof."
        )
    if skipped_degenerate:
        warnings.append(f"Removed {skipped_degenerate} zero-area triangle(s) after KOTOR-space conversion.")
    if missing_texture_materials:
        warnings.append(
            "Used material(s) without a resolved diffuse image will use the selected fallback texture: "
            + ", ".join(missing_texture_materials)
        )

    source_path = Path(document.source_path)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    room_resref = normalise_resref(options.room_resref)
    primitive = ImportedMeshRoomPrimitive(
        room_resref=room_resref,
        surfaces=tuple(imported_surfaces),
        source_model=source_path.stem,
        game=game,
        wok=None,
        metadata={
            "source": "map_studio:obj_room_import",
            "imported_from": str(source_path),
            "source_sha256": source_hash,
            "source_units": units,
            "meters_per_source_unit": scale,
            "source_up_axis": up_axis,
            "axis_mapping": _axis_mapping_label(up_axis),
            "room_local_translation": list(translation_tuple),
            "source_bounds_min": list(document.bounds_min),
            "source_bounds_max": list(document.bounds_max),
            "room_bounds_min": list(bounds_min),
            "room_bounds_max": list(bounds_max),
            "source_materials": [surface.material_name for surface in selected_sources],
            "obj_surface_materials": list(output_material_names),
            "material_texture_resrefs": dict(texture_mapping),
            "mdl_surface_vertex_limit": int(options.max_vertices_per_surface),
            "degenerate_triangles_removed": skipped_degenerate,
        },
    )

    walkmesh_materials = {
        str(value) for value in tuple(options.walkmesh_materials or ()) if str(value)
    }
    if walkmesh_materials:
        reviewed_indices = {
            output_index: None
            for material_name in walkmesh_materials
            for output_index in source_to_output_indices.get(material_name, ())
        }
        if not reviewed_indices:
            raise ValueError("OBJ walkmesh material selection does not match any imported surface.")
        primitive = prepare_imported_mesh_walkmesh_generation_intent(
            primitive,
            surface_faces=reviewed_indices,
            reason=(
                "Confirmed in the OBJ room import review: selected materials are floor-candidate geometry; "
                "Map Studio must still apply slope, topology, island, perimeter, and serialization gates."
            ),
        )

    report = ObjRoomAuthoringReport(
        source_path=str(source_path),
        source_sha256=source_hash,
        source_units=units,
        meters_per_source_unit=scale,
        source_up_axis=up_axis,
        axis_mapping=_axis_mapping_label(up_axis),
        translation=translation_tuple,
        bounds_min=tuple(float(value) for value in bounds_min),
        bounds_max=tuple(float(value) for value in bounds_max),
        surface_count=len(selected_sources),
        split_surface_count=len(imported_surfaces),
        triangle_count=total_triangles,
        skipped_degenerate_triangles=skipped_degenerate,
        texture_sources=texture_rows,
        missing_texture_materials=missing_texture_materials,
        warnings=tuple(dict.fromkeys(warnings)),
        metadata={
            "material_output_surface_indices": {
                name: tuple(indices) for name, indices in source_to_output_indices.items()
            }
        },
    )
    return primitive, report


def suggested_obj_texture_resref(material_name: str, texture_path: str, *, used: set[str] | None = None) -> str:
    """Return a deterministic <=16-character texture ResRef for an OBJ material."""

    source = Path(str(texture_path or "")).stem or str(material_name or "texture").rsplit(":", 1)[-1]
    base = re.sub(r"[^0-9A-Za-z_]+", "_", source).strip("_").lower() or "texture"
    base = base[:16]
    reserved = {str(value).lower() for value in (used or set())}
    if base not in reserved:
        return base
    for ordinal in range(2, 10_000):
        suffix = f"_{ordinal}"
        candidate = f"{base[: 16 - len(suffix)]}{suffix}"
        if candidate not in reserved:
            return candidate
    raise ValueError(f"Could not allocate a unique KOTOR texture ResRef for {source!r}.")


__all__ = [
    "ObjRoomAuthoringOptions",
    "ObjRoomAuthoringReport",
    "ObjWalkmeshCandidateComponent",
    "analyze_obj_walkmesh_candidate_components",
    "apply_obj_walkmesh_component_review",
    "build_obj_room_primitive",
    "generate_adaptive_obj_walkmesh",
    "obj_room_meters_per_unit",
    "split_imported_surface_for_mdl",
    "suggested_obj_texture_resref",
]
