"""Vertex and compatible border-edge weld operations."""

from __future__ import annotations

from collections import defaultdict
import math

from .mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from .mesh_preservation import filter_face_attributes
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge


def weld_selected_vertices(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    if state.mode is not MeshSelectionMode.VERTEX:
        return MeshOperationResult.fail("Weld works in Vertex mode.")
    selected = sorted(int(v) for v in state.selected_vertices)
    if len(selected) < 2:
        return MeshOperationResult.fail("Select at least two vertices to weld.")
    vertices = [tuple(map(float, v[:3])) for v in (getattr(mesh, "vertices", []) or [])]
    if any(v < 0 or v >= len(vertices) for v in selected):
        return MeshOperationResult.fail("Selected vertices are no longer valid.")
    threshold = max(0.0, float(options.weld_threshold))
    groups = _cluster_vertices(vertices, selected, threshold)
    if not any(len(group) > 1 for group in groups):
        return MeshOperationResult.fail("No selected vertices are within the Weld Threshold.")
    return _collapse_groups(mesh, state, groups, options, "Weld Vertices")


def target_weld_vertex(mesh, state: MeshSelectionState, source_vertex: int, target_vertex: int, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    if state.mode is not MeshSelectionMode.VERTEX:
        return MeshOperationResult.fail("Target Weld works in Vertex mode.")
    vertices = getattr(mesh, "vertices", []) or []
    source_vertex = int(source_vertex)
    target_vertex = int(target_vertex)
    if source_vertex == target_vertex:
        return MeshOperationResult.fail("Source and target vertex are the same.")
    if source_vertex < 0 or source_vertex >= len(vertices) or target_vertex < 0 or target_vertex >= len(vertices):
        return MeshOperationResult.fail("Target Weld vertex index is out of range.")
    return _collapse_groups(mesh, state, [[target_vertex, source_vertex]], options, "Target Weld Vertex", target_vertex=target_vertex)


def target_weld_edge(mesh, edge_a, edge_b, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    topology = MeshTopology.build_from_mesh(mesh)
    a = normalize_edge(*edge_a)
    b = normalize_edge(*edge_b)
    if a not in topology.border_edges or b not in topology.border_edges:
        return MeshOperationResult.fail("Target edge weld requires two open border edges.")
    groups = [[a[0], b[0]], [a[1], b[1]]]
    state = MeshSelectionState(mode=MeshSelectionMode.VERTEX, selected_vertices={a[0], a[1], b[0], b[1]})
    return _collapse_groups(mesh, state, groups, options, "Target Weld Edge")


def _cluster_vertices(vertices, selected: list[int], threshold: float) -> list[list[int]]:
    parent = {vi: vi for vi in selected}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, a in enumerate(selected):
        for b in selected[i + 1 :]:
            if _distance(vertices[a], vertices[b]) <= threshold:
                union(a, b)
    groups: dict[int, list[int]] = defaultdict(list)
    for vi in selected:
        groups[find(vi)].append(vi)
    return list(groups.values())


def _collapse_groups(mesh, state: MeshSelectionState, groups: list[list[int]], options: MeshOperationOptions, label: str, *, target_vertex: int | None = None) -> MeshOperationResult:
    old_vertices = [tuple(map(float, v[:3])) for v in (getattr(mesh, "vertices", []) or [])]
    group_for: dict[int, int] = {}
    new_positions: dict[int, tuple[float, float, float]] = {}
    for group in groups:
        if len(group) < 2:
            continue
        keep = target_vertex if target_vertex in group else min(group)
        group_for.update({vi: keep for vi in group})
        if target_vertex in group:
            new_positions[keep] = old_vertices[target_vertex]
        else:
            inv = 1.0 / len(group)
            new_positions[keep] = (
                sum(old_vertices[vi][0] for vi in group) * inv,
                sum(old_vertices[vi][1] for vi in group) * inv,
                sum(old_vertices[vi][2] for vi in group) * inv,
            )
    for keep, pos in new_positions.items():
        old_vertices[keep] = pos
    remap = {i: group_for.get(i, i) for i in range(len(old_vertices))}
    faces = [tuple(remap[int(v)] for v in face[:3]) for face in (getattr(mesh, "faces", []) or [])]
    kept_faces = [idx for idx, face in enumerate(faces) if len(set(face)) == 3]
    if len(kept_faces) != len(faces) and not options.allow_degenerate_cleanup:
        return MeshOperationResult.fail("Weld would create degenerate faces. Enable degenerate cleanup to continue.")
    faces = [faces[i] for i in kept_faces]
    selected_keep = target_vertex if target_vertex is not None else min(new_positions) if new_positions else None
    used = sorted({vi for face in faces for vi in face})
    if selected_keep is not None and selected_keep not in used:
        used.append(selected_keep)
        used.sort()
    compact = {old: new for new, old in enumerate(used)}
    mesh.vertices = [old_vertices[old] for old in used]
    mesh.faces = [tuple(compact[vi] for vi in face) for face in faces]
    filter_face_attributes(mesh, kept_faces)
    _compact_vertex_attributes(mesh, used)
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()
    state.selected_vertices = {compact[selected_keep]} if selected_keep in compact else set()
    warnings = []
    if len(kept_faces) != len(getattr(mesh, "faces", [])):
        warnings.append("Degenerate faces were removed during weld cleanup.")
    return MeshOperationResult.ok(
        label,
        changed_mesh_ids=[str(getattr(mesh, "name", id(mesh)))],
        selection_changed=True,
        topology_changed=True,
        warnings=warnings,
    )


def _compact_vertex_attributes(mesh, used: list[int]) -> None:
    for attr in ("normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3", "skin_data"):
        values = list(getattr(mesh, attr, []) or [])
        if values and len(values) >= max(used, default=-1) + 1:
            setattr(mesh, attr, [values[i] for i in used])


def _distance(a, b) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))
