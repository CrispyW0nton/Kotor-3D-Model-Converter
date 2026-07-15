"""Deterministic closed-solid polygon Boolean operations.

This module is the renderer-, scene-, and Qt-free geometry owner for Map
Studio's genuine polygon Boolean work.  It calls :mod:`manifold3d` directly;
``trimesh.boolean`` is deliberately not used because its engine selection and
attribute round-trip are not a stable authoring contract.

The public operation accepts immutable :class:`IndexedPolygonMesh` values and
never mutates either operand.  Invalid/open/non-manifold inputs return a
diagnostic result without a replacement mesh.  Vertex and corner numeric
channels are carried through Manifold's interpolated vertex-property stream;
face channels (including material IDs) are restored from Manifold face
provenance.  The result is canonicalized so repeated operations produce the
same indexed representation, not merely the same visible surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
import math
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence

from .mesh_topology import MeshTopology
from .polygon_mesh_operations import AttributeChannel, IndexedPolygonMesh


_BACKEND_NAME = "manifold3d"
_NORMAL_NAMES = ("normal", "normals", "vertex_normal", "vertex_normals")


@dataclass(frozen=True, slots=True)
class SolidBooleanIssue:
    """One stable, user-presentable validation or backend diagnostic."""

    severity: str
    code: str
    message: str
    operand: str = ""


@dataclass(frozen=True, slots=True)
class SolidBooleanDiagnostics:
    """Complete proof record for one attempted solid Difference A - B."""

    backend: str = _BACKEND_NAME
    backend_version: str = "unavailable"
    issues: tuple[SolidBooleanIssue, ...] = ()
    input_vertices: tuple[int, int] = (0, 0)
    input_triangles: tuple[int, int] = (0, 0)
    output_vertices: int = 0
    output_triangles: int = 0
    output_volume: float = 0.0
    preserved_vertex_channels: tuple[str, ...] = ()
    preserved_face_channels: tuple[str, ...] = ()
    dropped_channels: tuple[str, ...] = ()

    @property
    def errors(self) -> tuple[SolidBooleanIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[SolidBooleanIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


@dataclass(frozen=True, slots=True)
class SolidBooleanResult:
    """A replacement mesh plus truthful diagnostics, or a rejected edit."""

    mesh: IndexedPolygonMesh | None
    diagnostics: SolidBooleanDiagnostics

    @property
    def ok(self) -> bool:
        return self.mesh is not None and not self.diagnostics.errors


@dataclass(frozen=True, slots=True)
class _PropertySpec:
    name: str
    width: int
    semantic: str
    default: tuple[float, ...]
    offset: int

    @property
    def is_normal(self) -> bool:
        return self.semantic == "normal" or self.name.casefold() in _NORMAL_NAMES


@dataclass(frozen=True, slots=True)
class _PreparedOperand:
    manifold: Any
    topology: MeshTopology
    global_face_offset: int


def manifold3d_available() -> bool:
    """Return whether the direct closed-solid backend can be imported."""

    try:
        _import_manifold3d()
    except (ImportError, OSError):
        return False
    return True


def difference_closed_solid_meshes(
    minuend: IndexedPolygonMesh,
    subtrahend: IndexedPolygonMesh,
    *,
    weld_tolerance: float = 1.0e-6,
    max_output_triangles: int = 65_535,
    canonical_precision: int = 9,
) -> SolidBooleanResult:
    """Return the deterministic closed-solid difference ``minuend - subtrahend``.

    Both operands must be finite, consistently wound, closed oriented triangle
    manifolds in the same coordinate space.  Border edges, non-manifold edges,
    duplicate faces, isolated vertices, zero volume, or inward winding are
    rejected before the native backend runs.  The returned mesh is always a
    new value; on every failure ``mesh`` is ``None`` and both inputs remain
    untouched.
    """

    issues: list[SolidBooleanIssue] = []
    dropped_channels: list[str] = []
    tolerance = max(0.0, float(weld_tolerance))
    triangle_limit = max(1, int(max_output_triangles))
    precision = max(0, min(15, int(canonical_precision)))
    inputs = (minuend, subtrahend)
    input_vertices = tuple(len(mesh.vertices) for mesh in inputs)
    input_triangles = tuple(len(mesh.faces) for mesh in inputs)

    topologies: list[MeshTopology | None] = []
    for label, mesh in zip(("A", "B"), inputs):
        topology = _validate_operand(mesh, label=label, tolerance=tolerance, issues=issues)
        topologies.append(topology)
    if any(issue.severity == "error" for issue in issues):
        return _result(
            None,
            issues,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
        )

    try:
        backend = _import_manifold3d()
    except (ImportError, OSError) as exc:
        issues.append(
            SolidBooleanIssue(
                "error",
                "backend_unavailable",
                "Closed-solid Difference requires manifold3d>=3.5.2. "
                f"Install GhostRigger's mesh dependencies before using this tool ({exc}).",
            )
        )
        return _result(
            None,
            issues,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
        )

    backend_version = _backend_version()
    property_specs = _collect_property_specs(inputs, issues, dropped_channels)
    if any(issue.severity == "error" for issue in issues):
        return _result(
            None,
            issues,
            backend_version=backend_version,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            dropped_channels=dropped_channels,
        )

    try:
        first_id = int(backend.Manifold.reserve_ids(2))
        prepared_a = _prepare_operand(
            backend,
            minuend,
            topologies[0],
            property_specs,
            original_id=first_id,
            global_face_offset=0,
            tolerance=tolerance,
        )
        prepared_b = _prepare_operand(
            backend,
            subtrahend,
            topologies[1],
            property_specs,
            original_id=first_id + 1,
            global_face_offset=len(minuend.faces),
            tolerance=tolerance,
        )
    except Exception as exc:  # native boundary: convert to an atomic diagnostic
        issues.append(
            SolidBooleanIssue(
                "error",
                "backend_input_exception",
                f"The closed-solid backend rejected the prepared operands: {type(exc).__name__}: {exc}",
            )
        )
        return _result(
            None,
            issues,
            backend_version=backend_version,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            dropped_channels=dropped_channels,
        )

    for label, prepared in (("A", prepared_a), ("B", prepared_b)):
        status = prepared.manifold.status()
        if _status_name(status) != "NoError":
            issues.append(
                SolidBooleanIssue(
                    "error",
                    "backend_input_invalid",
                    f"Manifold rejected operand {label} with status {_status_name(status)}.",
                    label,
                )
            )
    if any(issue.severity == "error" for issue in issues):
        return _result(
            None,
            issues,
            backend_version=backend_version,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            dropped_channels=dropped_channels,
        )

    try:
        product = prepared_a.manifold - prepared_b.manifold
        status = product.status()
        if _status_name(status) != "NoError":
            issues.append(
                SolidBooleanIssue(
                    "error",
                    "backend_operation_failed",
                    f"Difference A - B failed with Manifold status {_status_name(status)}.",
                )
            )
            return _result(
                None,
                issues,
                backend_version=backend_version,
                input_vertices=input_vertices,
                input_triangles=input_triangles,
                dropped_channels=dropped_channels,
            )
        output_triangle_count = int(product.num_tri())
        if output_triangle_count > triangle_limit:
            issues.append(
                SolidBooleanIssue(
                    "error",
                    "output_triangle_limit",
                    f"Difference would create {output_triangle_count:,} triangles; "
                    f"the configured limit is {triangle_limit:,}.",
                )
            )
            return _result(
                None,
                issues,
                backend_version=backend_version,
                input_vertices=input_vertices,
                input_triangles=input_triangles,
                output_triangles=output_triangle_count,
                output_volume=float(product.volume()),
                dropped_channels=dropped_channels,
            )

        normal_offset = next(
            (spec.offset for spec in property_specs if spec.is_normal and spec.width == 3),
            -1,
        )
        native_mesh = product.to_mesh(normal_offset)
        output_mesh = _restore_output_mesh(
            native_mesh,
            inputs,
            property_specs,
            issues,
            precision=precision,
            backend_version=backend_version,
        )
    except Exception as exc:  # native boundary: no partial scene replacement
        issues.append(
            SolidBooleanIssue(
                "error",
                "backend_output_exception",
                f"Difference output could not be restored safely: {type(exc).__name__}: {exc}",
            )
        )
        return _result(
            None,
            issues,
            backend_version=backend_version,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            dropped_channels=dropped_channels,
        )

    output_audit = MeshTopology.build(
        output_mesh.vertices,
        output_mesh.faces,
        weld_tolerance=tolerance,
    ).validate_manifold_state()
    if output_mesh.faces and (
        output_audit.invalid_faces
        or output_audit.non_manifold_edges
        or output_audit.border_edges
        or output_audit.degenerate_faces
        or output_audit.inconsistent_winding_edges
        or output_audit.duplicate_faces
    ):
        issues.append(
            SolidBooleanIssue(
                "error",
                "output_not_closed_manifold",
                "The native result failed GhostRigger's closed-manifold audit; no replacement mesh was returned.",
            )
        )
        return _result(
            None,
            issues,
            backend_version=backend_version,
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            output_vertices=len(output_mesh.vertices),
            output_triangles=len(output_mesh.faces),
            output_volume=float(product.volume()),
            dropped_channels=dropped_channels,
        )

    return _result(
        output_mesh,
        issues,
        backend_version=backend_version,
        input_vertices=input_vertices,
        input_triangles=input_triangles,
        output_vertices=len(output_mesh.vertices),
        output_triangles=len(output_mesh.faces),
        output_volume=float(product.volume()),
        preserved_vertex_channels=tuple(output_mesh.vertex_channels),
        preserved_face_channels=tuple(output_mesh.face_channels),
        dropped_channels=dropped_channels,
    )


def _validate_operand(
    mesh: IndexedPolygonMesh,
    *,
    label: str,
    tolerance: float,
    issues: list[SolidBooleanIssue],
) -> MeshTopology | None:
    try:
        mesh.validate()
    except Exception as exc:
        issues.append(
            SolidBooleanIssue(
                "error",
                "malformed_mesh",
                f"Operand {label} is structurally invalid: {type(exc).__name__}: {exc}",
                label,
            )
        )
        return None
    if not mesh.vertices or not mesh.faces:
        issues.append(
            SolidBooleanIssue(
                "error",
                "empty_operand",
                f"Operand {label} must contain a closed triangle solid.",
                label,
            )
        )
        return None
    non_triangles = tuple(index for index, face in enumerate(mesh.faces) if len(face) != 3)
    if non_triangles:
        issues.append(
            SolidBooleanIssue(
                "error",
                "triangle_mesh_required",
                f"Operand {label} contains {len(non_triangles)} non-triangle face(s). "
                "Triangulate explicitly before the solid Boolean so UV/corner provenance remains unambiguous.",
                label,
            )
        )
        return None
    if any(not math.isfinite(component) for vertex in mesh.vertices for component in vertex):
        issues.append(
            SolidBooleanIssue(
                "error",
                "non_finite_vertex",
                f"Operand {label} contains NaN or infinite vertex coordinates.",
                label,
            )
        )
        return None

    topology = MeshTopology.build(mesh.vertices, mesh.faces, weld_tolerance=tolerance)
    audit = topology.validate_manifold_state()
    checks = (
        (audit.invalid_faces, "invalid_faces", "invalid face(s)"),
        (audit.non_manifold_edges, "non_manifold_edges", "non-manifold edge(s)"),
        (audit.border_edges, "open_boundary", "open border edge(s)"),
        (audit.degenerate_faces, "degenerate_faces", "degenerate face(s)"),
        (audit.inconsistent_winding_edges, "inconsistent_winding", "inconsistently wound edge(s)"),
        (audit.duplicate_faces, "duplicate_faces", "duplicate face(s)"),
        (audit.isolated_vertices, "isolated_vertices", "isolated vertex/vertices"),
    )
    for values, code, noun in checks:
        if values:
            issues.append(
                SolidBooleanIssue(
                    "error",
                    code,
                    f"Operand {label} has {len(values)} {noun}; Difference accepts only closed oriented solids.",
                    label,
                )
            )
    signed_volume = _signed_volume(mesh.vertices, mesh.faces)
    volume_epsilon = max(1.0e-15, tolerance * tolerance * tolerance)
    if abs(signed_volume) <= volume_epsilon:
        issues.append(
            SolidBooleanIssue(
                "error",
                "zero_volume",
                f"Operand {label} has no reliable enclosed volume.",
                label,
            )
        )
    elif signed_volume < 0.0:
        issues.append(
            SolidBooleanIssue(
                "error",
                "inward_winding",
                f"Operand {label} is inward-wound. Use Reverse before Difference A - B.",
                label,
            )
        )
    return topology


def _collect_property_specs(
    meshes: Sequence[IndexedPolygonMesh],
    issues: list[SolidBooleanIssue],
    dropped: list[str],
) -> tuple[_PropertySpec, ...]:
    names = sorted(
        {
            str(name)
            for mesh in meshes
            for name in (*mesh.vertex_channels.keys(), *mesh.corner_channels.keys())
        },
        key=lambda name: (0 if name.casefold() in _NORMAL_NAMES else 1, name.casefold(), name),
    )
    specs: list[_PropertySpec] = []
    offset = 0
    for name in names:
        channels = [
            channel
            for mesh in meshes
            for channel in (mesh.corner_channels.get(name), mesh.vertex_channels.get(name))
            if channel is not None
        ]
        widths = {_channel_width(channel, corner=_channel_is_corner(meshes, name, channel)) for channel in channels}
        if None in widths or len(widths) != 1:
            dropped.append(name)
            issues.append(
                SolidBooleanIssue(
                    "warning",
                    "attribute_channel_dropped",
                    f"Numeric channel {name!r} has inconsistent or non-numeric values and was not transferred.",
                )
            )
            continue
        width = int(next(iter(widths)))
        if width < 1 or width > 16:
            dropped.append(name)
            issues.append(
                SolidBooleanIssue(
                    "warning",
                    "attribute_channel_dropped",
                    f"Numeric channel {name!r} has unsupported width {width} and was not transferred.",
                )
            )
            continue
        semantic = _channel_semantic(name, channels)
        default = _numeric_tuple(channels[0].default, width, fallback=0.0)
        specs.append(_PropertySpec(name, width, semantic, default, offset))
        offset += width
    return tuple(specs)


def _prepare_operand(
    backend: Any,
    mesh: IndexedPolygonMesh,
    topology: MeshTopology,
    specs: Sequence[_PropertySpec],
    *,
    original_id: int,
    global_face_offset: int,
    tolerance: float,
) -> _PreparedOperand:
    import numpy as np

    properties: list[list[float]] = []
    triangles: list[tuple[int, int, int]] = []
    merge_from: list[int] = []
    merge_to: list[int] = []
    first_by_geometric_vertex: dict[int, int] = {}
    for face_index, face in enumerate(mesh.faces):
        triangle: list[int] = []
        for corner, raw_vertex in enumerate(face):
            output_vertex = len(properties)
            triangle.append(output_vertex)
            row = [float(value) for value in mesh.vertices[raw_vertex]]
            for spec in specs:
                value = _source_property_value(
                    mesh,
                    topology,
                    spec,
                    face_index=face_index,
                    corner=corner,
                    raw_vertex=raw_vertex,
                )
                row.extend(value)
            properties.append(row)
            geometric_vertex = topology.raw_to_geometric_vertex[raw_vertex]
            canonical = first_by_geometric_vertex.get(geometric_vertex)
            if canonical is None:
                first_by_geometric_vertex[geometric_vertex] = output_vertex
            else:
                merge_from.append(output_vertex)
                merge_to.append(canonical)
        triangles.append(tuple(triangle))

    face_ids = np.arange(
        global_face_offset,
        global_face_offset + len(triangles),
        dtype=np.uint32,
    )
    native_mesh = backend.Mesh(
        np.ascontiguousarray(properties, dtype=np.float32),
        np.ascontiguousarray(triangles, dtype=np.uint32),
        merge_from_vert=np.ascontiguousarray(merge_from, dtype=np.uint32),
        merge_to_vert=np.ascontiguousarray(merge_to, dtype=np.uint32),
        run_index=np.asarray((0, len(triangles) * 3), dtype=np.uint32),
        run_original_id=np.asarray((original_id,), dtype=np.uint32),
        face_id=face_ids,
        tolerance=float(tolerance),
    )
    return _PreparedOperand(
        manifold=backend.Manifold(native_mesh),
        topology=topology,
        global_face_offset=global_face_offset,
    )


def _restore_output_mesh(
    native_mesh: Any,
    inputs: Sequence[IndexedPolygonMesh],
    specs: Sequence[_PropertySpec],
    issues: list[SolidBooleanIssue],
    *,
    precision: int,
    backend_version: str,
) -> IndexedPolygonMesh:
    rows = tuple(tuple(_clean_float(value) for value in row) for row in native_mesh.vert_properties.tolist())
    triangles = tuple(tuple(int(value) for value in face) for face in native_mesh.tri_verts.tolist())
    face_ids = tuple(int(value) for value in native_mesh.face_id)
    property_width = sum(spec.width for spec in specs)
    if rows and any(len(row) != 3 + property_width for row in rows):
        raise ValueError("manifold3d returned a vertex-property width that differs from the input schema")
    if len(face_ids) != len(triangles):
        raise ValueError("manifold3d returned face provenance with the wrong length")

    source_refs: list[tuple[int, int] | None] = []
    a_faces = len(inputs[0].faces)
    total_faces = a_faces + len(inputs[1].faces)
    missing_provenance = 0
    for face_id in face_ids:
        if 0 <= face_id < a_faces:
            source_refs.append((0, face_id))
        elif a_faces <= face_id < total_faces:
            source_refs.append((1, face_id - a_faces))
        else:
            source_refs.append(None)
            missing_provenance += 1
    if missing_provenance:
        issues.append(
            SolidBooleanIssue(
                "warning",
                "face_provenance_missing",
                f"{missing_provenance} output triangle(s) lacked source-face provenance; defaults were used.",
            )
        )

    # Deduplicate only fully identical position+property records.  This keeps
    # hard-normal/UV seams distinct while removing backend-order ambiguity for
    # redundant identical vertices.
    unique_rows = sorted(
        set(rows),
        key=lambda row: (tuple(round(value, precision) for value in row), row),
    )
    row_to_vertex = {row: index for index, row in enumerate(unique_rows)}
    old_to_new = tuple(row_to_vertex[row] for row in rows)
    remapped_faces = [tuple(old_to_new[index] for index in face) for face in triangles]
    remapped_faces = [_rotate_triangle(face) for face in remapped_faces]
    face_order = sorted(
        range(len(remapped_faces)),
        key=lambda index: (
            remapped_faces[index],
            source_refs[index] if source_refs[index] is not None else (2, -1),
        ),
    )
    faces = tuple(remapped_faces[index] for index in face_order)
    ordered_refs = tuple(source_refs[index] for index in face_order)

    vertex_channels: dict[str, AttributeChannel] = {}
    for spec in specs:
        values: list[Any] = []
        start = 3 + spec.offset
        for row in unique_rows:
            value = tuple(row[start : start + spec.width])
            if spec.is_normal and spec.width == 3:
                value = _normalized(value)
            values.append(value[0] if spec.width == 1 else value)
        vertex_channels[spec.name] = AttributeChannel.build(
            values,
            semantic=spec.semantic,
            default=spec.default[0] if spec.width == 1 else spec.default,
        )

    face_channels = _restore_face_channels(inputs, ordered_refs)
    face_channels["boolean_source_operand"] = AttributeChannel.build(
        ("A" if ref and ref[0] == 0 else "B" if ref else "unknown" for ref in ordered_refs),
        semantic="attribute",
        default="unknown",
    )
    face_channels["boolean_source_face"] = AttributeChannel.build(
        (ref[1] if ref else -1 for ref in ordered_refs),
        semantic="attribute",
        default=-1,
    )
    metadata = {
        "operation": "closed_solid_difference_a_minus_b",
        "backend": _BACKEND_NAME,
        "backend_version": backend_version,
        "source_a": str(inputs[0].metadata.get("source_id") or "A"),
        "source_b": str(inputs[1].metadata.get("source_id") or "B"),
        "attributes": "manifold_interpolated_vertex_properties_and_face_provenance",
        "deterministic_canonicalization": 1,
    }
    return IndexedPolygonMesh.build(
        (row[:3] for row in unique_rows),
        faces,
        vertex_channels=vertex_channels,
        face_channels=face_channels,
        metadata=metadata,
    )


def _restore_face_channels(
    inputs: Sequence[IndexedPolygonMesh],
    refs: Sequence[tuple[int, int] | None],
) -> dict[str, AttributeChannel]:
    names = sorted({name for mesh in inputs for name in mesh.face_channels})
    restored: dict[str, AttributeChannel] = {}
    for name in names:
        templates = [mesh.face_channels[name] for mesh in inputs if name in mesh.face_channels]
        template = templates[0]
        values: list[Any] = []
        for ref in refs:
            if ref is None:
                values.append(template.default)
                continue
            operand, source_face = ref
            channel = inputs[operand].face_channels.get(name)
            values.append(channel.values[source_face] if channel is not None else template.default)
        restored[name] = AttributeChannel.build(
            values,
            semantic=template.semantic,
            default=template.default,
        )
    return restored


def _source_property_value(
    mesh: IndexedPolygonMesh,
    topology: MeshTopology,
    spec: _PropertySpec,
    *,
    face_index: int,
    corner: int,
    raw_vertex: int,
) -> tuple[float, ...]:
    corner_channel = mesh.corner_channels.get(spec.name)
    vertex_channel = mesh.vertex_channels.get(spec.name)
    if corner_channel is not None:
        value = corner_channel.values[face_index][corner]
    elif vertex_channel is not None:
        value = vertex_channel.values[raw_vertex]
    elif spec.is_normal and spec.width == 3:
        value = topology.face_normals[face_index]
    else:
        value = spec.default
    numeric = _numeric_tuple(value, spec.width, fallback=0.0)
    return _normalized(numeric) if spec.is_normal and spec.width == 3 else numeric


def _channel_width(channel: AttributeChannel, *, corner: bool) -> int | None:
    values: Iterable[Any]
    if corner:
        values = (value for row in channel.values for value in row)
    else:
        values = channel.values
    width: int | None = None
    for value in values:
        current = _numeric_width(value)
        if current is None:
            return None
        if width is None:
            width = current
        elif width != current:
            return None
    if width is None:
        width = _numeric_width(channel.default)
    return width


def _channel_is_corner(
    meshes: Sequence[IndexedPolygonMesh],
    name: str,
    channel: AttributeChannel,
) -> bool:
    return any(mesh.corner_channels.get(name) is channel for mesh in meshes)


def _channel_semantic(name: str, channels: Sequence[AttributeChannel]) -> str:
    if name.casefold() in _NORMAL_NAMES:
        return "normal"
    for channel in channels:
        semantic = str(channel.semantic or "auto").casefold()
        if semantic != "auto":
            return semantic
    return "attribute"


def _numeric_width(value: Any) -> int | None:
    if isinstance(value, Real) and not isinstance(value, bool):
        return 1 if math.isfinite(float(value)) else None
    if isinstance(value, (str, bytes, bytearray)) or value is None:
        return None
    try:
        row = tuple(value)
    except TypeError:
        return None
    if not row or not all(isinstance(item, Real) and math.isfinite(float(item)) for item in row):
        return None
    return len(row)


def _numeric_tuple(value: Any, width: int, *, fallback: float) -> tuple[float, ...]:
    if width == 1 and isinstance(value, Real) and not isinstance(value, bool):
        candidate = (float(value),)
    else:
        try:
            candidate = tuple(float(item) for item in value)
        except (TypeError, ValueError):
            candidate = ()
    if len(candidate) != width or not all(math.isfinite(item) for item in candidate):
        return tuple(float(fallback) for _ in range(width))
    return candidate


def _normalized(value: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(component) * float(component) for component in value[:3]))
    if length <= 1.0e-18:
        return (0.0, 0.0, 1.0)
    return tuple(float(component) / length for component in value[:3])  # type: ignore[return-value]


def _signed_volume(vertices: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]) -> float:
    volume = 0.0
    for face in faces:
        p0, p1, p2 = (vertices[int(index)] for index in face)
        cross = (
            (p1[1] * p2[2]) - (p1[2] * p2[1]),
            (p1[2] * p2[0]) - (p1[0] * p2[2]),
            (p1[0] * p2[1]) - (p1[1] * p2[0]),
        )
        volume += (p0[0] * cross[0]) + (p0[1] * cross[1]) + (p0[2] * cross[2])
    return volume / 6.0


def _rotate_triangle(face: Sequence[int]) -> tuple[int, int, int]:
    row = tuple(int(value) for value in face)
    start = row.index(min(row))
    return row[start:] + row[:start]  # type: ignore[return-value]


def _clean_float(value: Any) -> float:
    result = float(value)
    return 0.0 if result == 0.0 else result


def _status_name(status: Any) -> str:
    return str(getattr(status, "name", status)).rsplit(".", 1)[-1]


def _backend_version() -> str:
    try:
        return str(importlib_metadata.version(_BACKEND_NAME))
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def _import_manifold3d() -> Any:
    import manifold3d

    return manifold3d


def _result(
    mesh: IndexedPolygonMesh | None,
    issues: Sequence[SolidBooleanIssue],
    *,
    backend_version: str = "unavailable",
    input_vertices: tuple[int, int] = (0, 0),
    input_triangles: tuple[int, int] = (0, 0),
    output_vertices: int = 0,
    output_triangles: int = 0,
    output_volume: float = 0.0,
    preserved_vertex_channels: tuple[str, ...] = (),
    preserved_face_channels: tuple[str, ...] = (),
    dropped_channels: Sequence[str] = (),
) -> SolidBooleanResult:
    return SolidBooleanResult(
        mesh=mesh,
        diagnostics=SolidBooleanDiagnostics(
            backend_version=backend_version,
            issues=tuple(issues),
            input_vertices=input_vertices,
            input_triangles=input_triangles,
            output_vertices=int(output_vertices),
            output_triangles=int(output_triangles),
            output_volume=float(output_volume),
            preserved_vertex_channels=tuple(preserved_vertex_channels),
            preserved_face_channels=tuple(preserved_face_channels),
            dropped_channels=tuple(dict.fromkeys(str(name) for name in dropped_channels)),
        ),
    )


__all__ = [
    "SolidBooleanDiagnostics",
    "SolidBooleanIssue",
    "SolidBooleanResult",
    "difference_closed_solid_meshes",
    "manifold3d_available",
]
