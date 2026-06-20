"""Headless component-editing primitives for Map Studio geometry.

These helpers are intentionally small and format-agnostic.  They operate on a
plain vertex/face mesh so Map Studio can share the same core behavior between
room geometry, terrain patches, and future walkmesh component editing without
putting modeling policy in Qt widgets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence


Vector3 = tuple[float, float, float]
Face = tuple[int, ...]


@dataclass(frozen=True)
class ComponentMesh:
    """Minimal editable mesh representation for Map Studio component tools."""

    vertices: tuple[Vector3, ...]
    faces: tuple[Face, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentEditResult:
    """Result returned by one component-edit operation."""

    mesh: ComponentMesh
    changed_vertex_count: int = 0
    removed_face_count: int = 0
    warnings: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentEditAudit:
    """KOTOR-aware export/readiness impact summary for one component edit."""

    operation: str
    component_kind: str
    geometry_changed: bool
    topology_changed: bool
    walkmesh_review_required: bool
    export_candidate_stale: bool
    game_proof_stale: bool
    stale_outputs: tuple[str, ...] = ()
    next_action: str = ""
    validation_messages: tuple[str, ...] = ()
    summary: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


def _finite_vertex(value: Sequence[float]) -> Vector3:
    if len(value) < 3:
        raise ValueError("Vertex must contain at least three coordinates.")
    vertex = (float(value[0]), float(value[1]), float(value[2]))
    if not all(math.isfinite(coord) for coord in vertex):
        raise ValueError(f"Vertex contains non-finite coordinates: {value!r}")
    return vertex


def component_mesh(
    vertices: Iterable[Sequence[float]],
    faces: Iterable[Sequence[int]] = (),
    *,
    metadata: dict[str, object] | None = None,
) -> ComponentMesh:
    """Build a validated component mesh from generic vertex/face data."""

    verts = tuple(_finite_vertex(vertex) for vertex in vertices)
    face_rows: list[Face] = []
    for face in faces or ():
        row = tuple(int(index) for index in face)
        if len(row) < 3:
            raise ValueError(f"Face must contain at least three vertices: {face!r}")
        for index in row:
            if index < 0 or index >= len(verts):
                raise ValueError(f"Face index {index} is outside vertex range 0..{len(verts) - 1}.")
        face_rows.append(row)
    return ComponentMesh(vertices=verts, faces=tuple(face_rows), metadata=dict(metadata or {}))


def _validate_indices(vertex_count: int, indices: Iterable[int]) -> tuple[int, ...]:
    result = tuple(int(index) for index in indices)
    for index in result:
        if index < 0 or index >= vertex_count:
            raise ValueError(f"Vertex index {index} is outside vertex range 0..{vertex_count - 1}.")
    return result


def _replace_vertices(mesh: ComponentMesh, replacements: dict[int, Vector3]) -> ComponentMesh:
    vertices = tuple(replacements.get(index, vertex) for index, vertex in enumerate(mesh.vertices))
    return ComponentMesh(vertices=vertices, faces=mesh.faces, metadata=dict(mesh.metadata))


def _sub(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    )


def _dot(a: Vector3, b: Vector3) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _length(value: Vector3) -> float:
    return math.sqrt(_dot(value, value))


def _normalise(value: Vector3, *, label: str = "vector") -> Vector3:
    length = _length(value)
    if length <= 1.0e-9:
        raise ValueError(f"{label} cannot be zero-length.")
    return (value[0] / length, value[1] / length, value[2] / length)


def _face_normal(mesh: ComponentMesh, face: Face) -> Vector3:
    unique: list[int] = []
    for index in face:
        if index not in unique:
            unique.append(index)
        if len(unique) >= 3:
            break
    if len(unique) < 3:
        return (0.0, 0.0, 0.0)
    a, b, c = (mesh.vertices[index] for index in unique[:3])
    return _cross(_sub(b, a), _sub(c, a))


def fill_face(mesh: ComponentMesh, indices: Iterable[int]) -> ComponentEditResult:
    """Create one face from an ordered vertex loop.

    Map Studio uses this for a KOTOR-safe "fill" command: close a room detail,
    terrain hole, or future walkmesh face from explicit selected vertices
    instead of allowing arbitrary hidden triangulation in the UI layer.
    """

    face = tuple(dict.fromkeys(_validate_indices(len(mesh.vertices), indices)))
    if len(face) < 3:
        raise ValueError("Fill face requires at least three unique vertices.")
    existing_sets = {frozenset(row) for row in mesh.faces}
    if frozenset(face) in existing_sets:
        return ComponentEditResult(mesh=mesh, warnings=("A face already uses the selected vertex set.",))
    filled = ComponentMesh(vertices=mesh.vertices, faces=tuple(mesh.faces + (face,)), metadata=dict(mesh.metadata))
    return ComponentEditResult(
        mesh=filled,
        metadata={"operation": "fill_face", "face_vertex_count": len(face), "added_face_count": 1},
    )


def bridge_edges(
    mesh: ComponentMesh,
    first_edge: Sequence[int],
    second_edge: Sequence[int],
    *,
    flip_second: bool = True,
) -> ComponentEditResult:
    """Create a quad face between two explicit border edges.

    Map Studio keeps this operation conservative because bridged corridors,
    doorway frames, and terrain seams affect both visible room geometry and the
    generated WOK. The helper creates one auditable quad and leaves triangulation
    to the explicit triangulate/cleanup step.
    """

    first = tuple(int(index) for index in first_edge)
    second = tuple(int(index) for index in second_edge)
    if len(first) != 2 or len(second) != 2:
        raise ValueError("Bridge edges requires exactly two vertices per edge.")
    _validate_indices(len(mesh.vertices), first + second)
    if first[0] == first[1] or second[0] == second[1]:
        raise ValueError("Bridge edges cannot use zero-length edges.")
    if len(set(first + second)) < 4:
        raise ValueError("Bridge edges requires two separate edges with four unique vertices.")
    second_order = tuple(reversed(second)) if flip_second else second
    face = tuple(first + second_order)
    existing_sets = {frozenset(row) for row in mesh.faces}
    if frozenset(face) in existing_sets:
        return ComponentEditResult(mesh=mesh, warnings=("A face already bridges the selected edge vertices.",))
    bridged = ComponentMesh(vertices=mesh.vertices, faces=tuple(mesh.faces + (face,)), metadata=dict(mesh.metadata))
    return ComponentEditResult(
        mesh=bridged,
        metadata={
            "operation": "bridge_edges",
            "added_face_count": 1,
            "face_vertex_count": 4,
            "first_edge": first,
            "second_edge": second,
            "flip_second": bool(flip_second),
        },
    )


def extrude_face(
    mesh: ComponentMesh,
    face_index: int,
    *,
    distance: float,
    direction: Sequence[float] | None = None,
    keep_source_face: bool = False,
) -> ComponentEditResult:
    """Extrude one face into side walls and a cap face.

    This first-pass Map Studio extrusion is intentionally explicit and
    deterministic. It creates new vertices and faces, rejects degenerate input,
    and leaves bevels, triangulation, and normal cleanup as separate auditable
    operations before MDL/WOK export.
    """

    if distance <= 0.0:
        raise ValueError("Face extrusion distance must be positive.")
    index = int(face_index)
    if index < 0 or index >= len(mesh.faces):
        raise ValueError(f"Face extrusion references missing face {face_index}.")
    face = tuple(mesh.faces[index])
    if len(set(face)) < 3:
        raise ValueError("Face extrusion requires a face with at least three unique vertices.")
    if direction is None:
        extrude_axis = _normalise(_face_normal(mesh, face), label="Face extrusion normal")
    else:
        extrude_axis = _normalise(_finite_vertex(direction), label="Face extrusion direction")
    offset = tuple(coord * float(distance) for coord in extrude_axis)
    vertices = list(mesh.vertices)
    new_indices: list[int] = []
    for vertex_index in face:
        vertex = mesh.vertices[vertex_index]
        new_indices.append(len(vertices))
        vertices.append((vertex[0] + offset[0], vertex[1] + offset[1], vertex[2] + offset[2]))

    faces = list(mesh.faces)
    removed_faces = 0
    if not keep_source_face:
        faces.pop(index)
        removed_faces = 1
    side_faces: list[Face] = []
    for offset_index, vertex_index in enumerate(face):
        next_offset = (offset_index + 1) % len(face)
        side_faces.append((vertex_index, face[next_offset], new_indices[next_offset], new_indices[offset_index]))
    cap_face = tuple(new_indices)
    faces.extend(side_faces)
    faces.append(cap_face)
    return ComponentEditResult(
        mesh=ComponentMesh(vertices=tuple(vertices), faces=tuple(faces), metadata=dict(mesh.metadata)),
        removed_face_count=removed_faces,
        metadata={
            "operation": "extrude_face",
            "face_index": index,
            "distance": float(distance),
            "direction": extrude_axis,
            "keep_source_face": bool(keep_source_face),
            "added_vertex_count": len(new_indices),
            "added_face_count": len(side_faces) + 1,
            "removed_source_face": removed_faces,
        },
    )


def cleanup_face_normals(
    mesh: ComponentMesh,
    *,
    reference_axis: str = "z",
    positive: bool = True,
) -> ComponentEditResult:
    """Orient face winding consistently against a reference axis.

    This is intentionally conservative: it does not recalculate vertex normals
    or smooth groups. It only flips face index order when the face normal points
    opposite the requested axis, which is enough for Map Studio's first-pass
    room/WOK cleanup before deterministic export.
    """

    axis_key = str(reference_axis or "z").lower()
    axis_vector = {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }.get(axis_key)
    if axis_vector is None:
        raise ValueError("reference_axis must be one of 'x', 'y', or 'z'.")
    sign = 1.0 if positive else -1.0
    updated: list[Face] = []
    flipped = 0
    skipped = 0
    for face in mesh.faces:
        facing = _dot(_face_normal(mesh, face), axis_vector)
        if abs(facing) <= 1.0e-9:
            skipped += 1
            updated.append(face)
            continue
        if (facing * sign) < 0.0:
            updated.append(tuple(reversed(face)))
            flipped += 1
        else:
            updated.append(face)
    warnings: list[str] = []
    if skipped:
        warnings.append(f"Skipped {skipped} zero-area or axis-parallel face(s) during normal cleanup.")
    return ComponentEditResult(
        mesh=ComponentMesh(vertices=mesh.vertices, faces=tuple(updated), metadata=dict(mesh.metadata)),
        warnings=tuple(warnings),
        metadata={
            "operation": "cleanup_face_normals",
            "reference_axis": axis_key,
            "positive": bool(positive),
            "flipped_face_count": flipped,
            "skipped_face_count": skipped,
        },
    )


def snap_vertex_to_vertex(mesh: ComponentMesh, source_index: int, target_index: int) -> ComponentEditResult:
    """Move one vertex exactly onto another vertex.

    This is the headless equivalent of a Maya-style point snap and is suitable
    for Map Studio's future hold-V vertex snap gesture.
    """

    source, target = _validate_indices(len(mesh.vertices), (source_index, target_index))
    if source == target:
        return ComponentEditResult(mesh=mesh, warnings=("Source and target vertex are the same.",))
    snapped = _replace_vertices(mesh, {source: mesh.vertices[target]})
    return ComponentEditResult(
        mesh=snapped,
        changed_vertex_count=1,
        metadata={"operation": "snap_vertex_to_vertex", "source_index": source, "target_index": target},
    )


def _metadata_int(metadata: dict[str, object], key: str) -> int:
    try:
        return int(metadata.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def audit_component_edit_result(
    result: ComponentEditResult,
    *,
    component_kind: str = "room",
    affects_walkmesh: bool = True,
) -> ComponentEditAudit:
    """Classify one component edit for Map Studio readiness/export messaging.

    The geometry helpers intentionally stay file-format agnostic, but Map
    Studio still needs every edit to explain its KOTOR consequences. This audit
    is the shared bridge: UI panels can show it, readiness checks can reference
    it, and export gates can treat stale MDL/MDX/WOK/PTH proof explicitly.
    """

    metadata = dict(result.metadata or {})
    operation = str(metadata.get("operation") or "component_edit")
    added_faces = _metadata_int(metadata, "added_face_count")
    triangulated_faces = _metadata_int(metadata, "triangulated_face_count")
    added_vertices = _metadata_int(metadata, "added_vertex_count")
    removed_vertices = _metadata_int(metadata, "removed_vertex_count")
    flipped_faces = _metadata_int(metadata, "flipped_face_count")
    skipped_faces = _metadata_int(metadata, "skipped_face_count")
    topology_changed = any(
        value > 0
        for value in (
            added_faces,
            added_vertices,
            result.removed_face_count,
            triangulated_faces,
            removed_vertices,
        )
    )
    geometry_changed = any(
        value > 0
        for value in (
            result.changed_vertex_count,
            result.removed_face_count,
            added_faces,
            added_vertices,
            triangulated_faces,
            removed_vertices,
            flipped_faces,
        )
    )
    kind = str(component_kind or "room").strip().lower() or "room"
    walkmesh_review_required = bool(geometry_changed and affects_walkmesh)
    messages: list[str] = list(result.warnings)
    if geometry_changed:
        messages.append("Previous staged exports and recorded game proof are stale.")
    if topology_changed:
        messages.append("Re-run MDL/MDX/WOK generation and inspect LYT/VIS/PTH readiness before packaging.")
    elif result.changed_vertex_count:
        messages.append("Re-run WOK/walkability preview if this edit affects traversal or doorway seams.")
    if walkmesh_review_required:
        messages.append("Review WOK surface intent before exporting the module.")
    if skipped_faces:
        messages.append("Some faces could not be normal-audited; inspect normals before export.")
    stale_outputs: tuple[str, ...] = ()
    next_action = "No export action required."
    if geometry_changed:
        if affects_walkmesh:
            stale_outputs = ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
        else:
            stale_outputs = ("MDL", "MDX", ".mod")
        if topology_changed:
            next_action = "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."
        elif walkmesh_review_required:
            next_action = "Review WOK/walkability, regenerate affected runtime resources, then verify in game."
        else:
            next_action = "Regenerate affected runtime resources before export."
    change_bits: list[str] = []
    if result.changed_vertex_count:
        change_bits.append(f"{result.changed_vertex_count} vertex change(s)")
    if added_vertices:
        change_bits.append(f"{added_vertices} added vertex(s)")
    if added_faces:
        change_bits.append(f"{added_faces} added face(s)")
    if result.removed_face_count:
        change_bits.append(f"{result.removed_face_count} removed face(s)")
    if triangulated_faces:
        change_bits.append(f"{triangulated_faces} triangulated face set(s)")
    if flipped_faces:
        change_bits.append(f"{flipped_faces} flipped face(s)")
    if not change_bits:
        change_bits.append("no geometry changes")
    summary = f"{operation} on {kind}: {', '.join(change_bits)}."
    return ComponentEditAudit(
        operation=operation,
        component_kind=kind,
        geometry_changed=geometry_changed,
        topology_changed=topology_changed,
        walkmesh_review_required=walkmesh_review_required,
        export_candidate_stale=geometry_changed,
        game_proof_stale=geometry_changed,
        stale_outputs=stale_outputs,
        next_action=next_action,
        validation_messages=tuple(dict.fromkeys(messages)),
        summary=summary,
        metadata={
            "changed_vertex_count": result.changed_vertex_count,
            "removed_face_count": result.removed_face_count,
            "added_face_count": added_faces,
            "added_vertex_count": added_vertices,
            "triangulated_face_count": triangulated_faces,
            "removed_vertex_count": removed_vertices,
            "flipped_face_count": flipped_faces,
            "affects_walkmesh": bool(affects_walkmesh),
        },
    )


def snap_vertices_to_grid(
    mesh: ComponentMesh,
    indices: Iterable[int],
    *,
    grid_size: float,
    axes: tuple[str, ...] = ("x", "y", "z"),
) -> ComponentEditResult:
    """Snap selected vertices to the Map Studio grid on the requested axes."""

    if grid_size <= 0:
        raise ValueError("grid_size must be greater than zero.")
    selected = set(_validate_indices(len(mesh.vertices), indices))
    axes_set = {axis.lower() for axis in axes}
    axis_index = {"x": 0, "y": 1, "z": 2}
    active_axes = tuple(axis_index[axis] for axis in axes_set if axis in axis_index)
    replacements: dict[int, Vector3] = {}
    for index in selected:
        coords = list(mesh.vertices[index])
        for axis in active_axes:
            coords[axis] = round(coords[axis] / grid_size) * grid_size
        replacements[index] = (float(coords[0]), float(coords[1]), float(coords[2]))
    return ComponentEditResult(
        mesh=_replace_vertices(mesh, replacements),
        changed_vertex_count=len(replacements),
        metadata={"operation": "snap_vertices_to_grid", "grid_size": float(grid_size), "axes": tuple(sorted(axes_set))},
    )


def flatten_vertices(
    mesh: ComponentMesh,
    indices: Iterable[int],
    *,
    axis: str = "z",
    value: float | None = None,
) -> ComponentEditResult:
    """Flatten selected vertices along one axis.

    If ``value`` is omitted, Map Studio flattens to the selected vertices'
    average coordinate on that axis.
    """

    selected = _validate_indices(len(mesh.vertices), indices)
    if not selected:
        return ComponentEditResult(mesh=mesh, warnings=("No vertices selected for flatten.",))
    axis_key = axis.lower()
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis_key)
    if axis_index is None:
        raise ValueError("axis must be one of 'x', 'y', or 'z'.")
    flatten_value = float(value) if value is not None else sum(mesh.vertices[index][axis_index] for index in selected) / len(selected)
    replacements: dict[int, Vector3] = {}
    for index in selected:
        coords = list(mesh.vertices[index])
        coords[axis_index] = flatten_value
        replacements[index] = (float(coords[0]), float(coords[1]), float(coords[2]))
    return ComponentEditResult(
        mesh=_replace_vertices(mesh, replacements),
        changed_vertex_count=len(replacements),
        metadata={"operation": "flatten_vertices", "axis": axis_key, "value": flatten_value},
    )


def mirror_vertices(
    mesh: ComponentMesh,
    indices: Iterable[int] = (),
    *,
    axis: str = "x",
    center: float | None = None,
) -> ComponentEditResult:
    """Mirror selected vertices across a coordinate centerline.

    ``axis`` names the coordinate being mirrored. For example, ``axis="x"``
    mirrors left/right X positions around the selected vertices' average X
    coordinate when ``center`` is omitted.
    """

    selected = tuple(dict.fromkeys(_validate_indices(len(mesh.vertices), indices or range(len(mesh.vertices)))))
    if not selected:
        return ComponentEditResult(mesh=mesh, warnings=("No vertices selected for mirror.",))
    axis_key = axis.lower()
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis_key)
    if axis_index is None:
        raise ValueError("axis must be one of 'x', 'y', or 'z'.")
    mirror_center = float(center) if center is not None else sum(mesh.vertices[index][axis_index] for index in selected) / len(selected)
    replacements: dict[int, Vector3] = {}
    for index in selected:
        coords = list(mesh.vertices[index])
        coords[axis_index] = (2.0 * mirror_center) - coords[axis_index]
        replacements[index] = (float(coords[0]), float(coords[1]), float(coords[2]))
    return ComponentEditResult(
        mesh=_replace_vertices(mesh, replacements),
        changed_vertex_count=len(replacements),
        metadata={"operation": "mirror_vertices", "axis": axis_key, "center": mirror_center},
    )


def cleanup_degenerate_faces(mesh: ComponentMesh) -> ComponentEditResult:
    """Remove faces that collapse to fewer than three unique vertices."""

    cleaned: list[Face] = []
    removed = 0
    for face in mesh.faces:
        if len(set(face)) < 3:
            removed += 1
            continue
        cleaned.append(face)
    if removed <= 0:
        return ComponentEditResult(mesh=mesh, metadata={"operation": "cleanup_degenerate_faces"})
    return ComponentEditResult(
        mesh=ComponentMesh(vertices=mesh.vertices, faces=tuple(cleaned), metadata=dict(mesh.metadata)),
        removed_face_count=removed,
        warnings=(f"Removed {removed} degenerate face(s).",),
        metadata={"operation": "cleanup_degenerate_faces"},
    )


def triangulate_faces(mesh: ComponentMesh) -> ComponentEditResult:
    """Fan-triangulate n-gon faces while leaving triangles unchanged."""

    triangles: list[Face] = []
    changed = 0
    for face in mesh.faces:
        if len(face) == 3:
            triangles.append(face)
            continue
        changed += 1
        first = face[0]
        for offset in range(1, len(face) - 1):
            triangles.append((first, face[offset], face[offset + 1]))
    return ComponentEditResult(
        mesh=ComponentMesh(vertices=mesh.vertices, faces=tuple(triangles), metadata=dict(mesh.metadata)),
        metadata={"operation": "triangulate_faces", "triangulated_face_count": changed},
    )


def weld_vertices(
    mesh: ComponentMesh,
    indices: Iterable[int],
    *,
    target_index: int | None = None,
    position_policy: str = "target",
    cleanup_faces: bool = True,
) -> ComponentEditResult:
    """Merge selected vertices into a single target vertex.

    ``position_policy`` may be ``target`` to keep the target vertex position or
    ``center`` to place the merged vertex at the average selected position.
    The returned mesh compacts removed vertices and remaps faces.
    """

    selected = tuple(dict.fromkeys(_validate_indices(len(mesh.vertices), indices)))
    if len(selected) < 2:
        return ComponentEditResult(mesh=mesh, warnings=("Select at least two vertices to weld.",))
    target = int(target_index if target_index is not None else selected[0])
    _validate_indices(len(mesh.vertices), (target,))
    if target not in selected:
        selected = (target, *selected)
    selected_set = set(selected)
    if position_policy == "center":
        merged_position = tuple(
            sum(mesh.vertices[index][axis] for index in selected_set) / len(selected_set)
            for axis in range(3)
        )
    elif position_policy == "target":
        merged_position = mesh.vertices[target]
    else:
        raise ValueError("position_policy must be 'target' or 'center'.")

    old_to_new: dict[int, int] = {}
    new_vertices: list[Vector3] = []
    for old_index, vertex in enumerate(mesh.vertices):
        if old_index in selected_set and old_index != target:
            continue
        old_to_new[old_index] = len(new_vertices)
        new_vertices.append(merged_position if old_index == target else vertex)
    for old_index in selected_set:
        old_to_new[old_index] = old_to_new[target]

    new_faces: list[Face] = []
    removed = 0
    for face in mesh.faces:
        remapped = tuple(old_to_new[index] for index in face)
        if cleanup_faces and len(set(remapped)) < 3:
            removed += 1
            continue
        new_faces.append(remapped)
    warnings: list[str] = []
    if removed:
        warnings.append(f"Removed {removed} degenerate face(s) after weld.")
    return ComponentEditResult(
        mesh=ComponentMesh(vertices=tuple(new_vertices), faces=tuple(new_faces), metadata=dict(mesh.metadata)),
        changed_vertex_count=len(selected_set),
        removed_face_count=removed,
        warnings=tuple(warnings),
        metadata={
            "operation": "weld_vertices",
            "target_index": target,
            "position_policy": position_policy,
            "removed_vertex_count": len(selected_set) - 1,
        },
    )


__all__ = [
    "ComponentEditAudit",
    "ComponentEditResult",
    "ComponentMesh",
    "Face",
    "Vector3",
    "audit_component_edit_result",
    "bridge_edges",
    "cleanup_degenerate_faces",
    "cleanup_face_normals",
    "component_mesh",
    "extrude_face",
    "fill_face",
    "flatten_vertices",
    "mirror_vertices",
    "snap_vertex_to_vertex",
    "snap_vertices_to_grid",
    "triangulate_faces",
    "weld_vertices",
]
