"""Generated-topology edit operations for selected mesh faces."""

from __future__ import annotations

import math

from .mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from .mesh_operations import _mesh_id, _selected_face_indices, delete_selected, recalculate_normals
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge


def extrude_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None, *, distance: float = 0.25) -> MeshOperationResult:
    if _has_skin(mesh):
        return MeshOperationResult.fail("Extrusion is disabled for skinned meshes until generated skin weights are supported.")
    selected = _selected_face_indices(mesh, state)
    if not selected:
        return MeshOperationResult.fail("Extrude requires selected faces, polygons, or elements.")
    topology = MeshTopology.build_from_mesh(mesh)
    offset = float(distance)
    vertices = list(getattr(mesh, "vertices", []) or [])
    faces = list(getattr(mesh, "faces", []) or [])
    face_mats = list(getattr(mesh, "face_mats", []) or [])
    uvs = list(getattr(mesh, "uvs", []) or [])
    boundary = _boundary_edges(topology, selected)
    remap: dict[int, int] = {}
    avg_normal = _average_normal(topology, selected)
    for vi in sorted({vi for fi in selected for vi in topology.faces[fi]}):
        vx, vy, vz = vertices[vi]
        remap[vi] = len(vertices)
        vertices.append((vx + avg_normal[0] * offset, vy + avg_normal[1] * offset, vz + avg_normal[2] * offset))
        if vi < len(uvs):
            uvs.append(uvs[vi])
    new_faces = [tuple(remap[vi] for vi in topology.faces[fi]) for fi in sorted(selected)]
    side_faces = []
    for a, b in sorted(boundary):
        side_faces.append((a, b, remap[b]))
        side_faces.append((a, remap[b], remap[a]))
    remaining_faces = [(fi, face) for fi, face in enumerate(faces) if fi not in selected]
    inherited = _face_material(mesh, next(iter(selected)), face_mats)
    faces = [face for _fi, face in remaining_faces]
    face_mats = [_face_material(mesh, fi, face_mats) for fi, _face in remaining_faces]
    faces.extend(new_faces)
    faces.extend(side_faces)
    face_mats.extend([inherited] * (len(new_faces) + len(side_faces)))
    mesh.vertices = vertices
    mesh.faces = faces
    if uvs:
        mesh.uvs = uvs
    if face_mats:
        mesh.face_mats = face_mats
    _finish(mesh)
    state.selected_faces = set(range(len(remaining_faces), len(remaining_faces) + len(new_faces)))
    state.mode = MeshSelectionMode.FACE
    return MeshOperationResult.ok("Extruded selected faces.", changed_mesh_ids=[_mesh_id(mesh)], selection_changed=True, topology_changed=True)


def inset_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None, *, amount: float = 0.1) -> MeshOperationResult:
    if _has_skin(mesh):
        return MeshOperationResult.fail("Inset is disabled for skinned meshes until generated skin weights are supported.")
    selected = _selected_face_indices(mesh, state)
    if not selected:
        return MeshOperationResult.fail("Inset requires selected faces, polygons, or elements.")
    vertices = list(getattr(mesh, "vertices", []) or [])
    faces = list(getattr(mesh, "faces", []) or [])
    face_mats = list(getattr(mesh, "face_mats", []) or [])
    uvs = list(getattr(mesh, "uvs", []) or [])
    amount = max(0.0, min(0.95, float(amount)))
    replacements: dict[int, list[tuple[int, int, int]]] = {}
    for fi in sorted(selected):
        if fi < 0 or fi >= len(faces):
            continue
        face = tuple(faces[fi])
        points = [vertices[vi] for vi in face]
        center = tuple(sum(p[i] for p in points) / 3.0 for i in range(3))
        inner = []
        for vi in face:
            p = vertices[vi]
            inner_index = len(vertices)
            vertices.append(tuple(p[i] + (center[i] - p[i]) * amount for i in range(3)))
            if vi < len(uvs):
                uv = uvs[vi]
                uvs.append((uv[0] + 0.0, uv[1] + 0.0))
            inner.append(inner_index)
        replacements[fi] = [
            (inner[0], inner[1], inner[2]),
            (face[0], face[1], inner[1]), (face[0], inner[1], inner[0]),
            (face[1], face[2], inner[2]), (face[1], inner[2], inner[1]),
            (face[2], face[0], inner[0]), (face[2], inner[0], inner[2]),
        ]
    new_faces: list[tuple[int, int, int]] = []
    new_mats: list[int] = []
    for fi, face in enumerate(faces):
        mat = _face_material(mesh, fi, face_mats)
        if fi in replacements:
            new_faces.extend(replacements[fi])
            new_mats.extend([mat] * len(replacements[fi]))
        else:
            new_faces.append(face)
            new_mats.append(mat)
    mesh.vertices = vertices
    mesh.faces = new_faces
    if uvs:
        mesh.uvs = uvs
    mesh.face_mats = new_mats
    _finish(mesh)
    return MeshOperationResult.ok("Inset selected faces.", changed_mesh_ids=[_mesh_id(mesh)], selection_changed=True, topology_changed=True)


def bevel_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None, *, amount: float = 0.08, segments: int = 1) -> MeshOperationResult:
    result = inset_selected(mesh, state, options, amount=amount)
    if result.success:
        result.message = "Bevelled selected faces with one generated support loop."
        if int(segments) > 1:
            result.warnings.append("Multi-segment bevel is not available yet; generated one support loop.")
    return result


def boolean_union_selected(meshes: list) -> tuple[MeshOperationResult, object | None]:
    from .mesh_attach import attach_selected_meshes

    if len(meshes or []) < 2:
        return MeshOperationResult.fail("Boolean Union requires at least two selected mesh objects."), None
    return attach_selected_meshes(list(meshes))


def boolean_difference_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    selected = _selected_face_indices(mesh, state)
    if selected:
        return delete_selected(mesh, state, options)
    return MeshOperationResult.fail(
        "Boolean Difference needs selected cutter geometry. Face selections can be deleted safely; arbitrary solid booleans are not enabled yet.",
        warnings=["No geometry was changed."],
    )


def boolean_cut_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    return MeshOperationResult.fail(
        "Boolean Cut is exposed for IPC/UI routing, but arbitrary topology cutting is not enabled without a robust solver.",
        warnings=["Use Inset, Bevel, Delete, or Map Studio rectangular floor-plan cuts for supported topology edits."],
    )


def _boundary_edges(topology: MeshTopology, selected: set[int]) -> set[tuple[int, int]]:
    counts: dict[tuple[int, int], int] = {}
    for fi in selected:
        for edge in topology.get_edges_for_face(fi):
            counts[normalize_edge(*edge)] = counts.get(normalize_edge(*edge), 0) + 1
    return {edge for edge, count in counts.items() if count == 1}


def _average_normal(topology: MeshTopology, selected: set[int]) -> tuple[float, float, float]:
    n = [0.0, 0.0, 0.0]
    for fi in selected:
        if 0 <= fi < len(topology.face_normals):
            normal = topology.face_normals[fi]
            n[0] += normal[0]
            n[1] += normal[1]
            n[2] += normal[2]
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    return (0.0, 0.0, 1.0) if length <= 1.0e-9 else (n[0] / length, n[1] / length, n[2] / length)


def _face_material(mesh, face_index: int, face_mats: list[int]) -> int:
    return int(face_mats[face_index]) if 0 <= face_index < len(face_mats) else 0


def _has_skin(mesh) -> bool:
    return bool(getattr(mesh, "is_skin", False) or getattr(mesh, "skin_data", None) or getattr(mesh, "bone_map", None))


def _finish(mesh) -> None:
    recalculate_normals(mesh)
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()
