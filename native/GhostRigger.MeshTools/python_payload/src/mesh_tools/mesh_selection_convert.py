"""Conversion rules between artist-facing sub-object selection modes."""

from __future__ import annotations

from .mesh_edit_types import MeshOperationResult, MeshSelectionMode
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge


def convert_selection(state: MeshSelectionState, topology: MeshTopology, target_mode: MeshSelectionMode) -> MeshOperationResult:
    source = state.mode
    if target_mode is source:
        return MeshOperationResult.ok(f"Already in {target_mode.label} mode.", selection_changed=False)
    vertices: set[int] = set()
    edges: set[tuple[int, int]] = set()
    faces: set[int] = set()
    polygons: set[int] = set()
    borders: set[int] = set()
    elements: set[int] = set()

    if source is MeshSelectionMode.VERTEX:
        vertices = set(state.selected_vertices)
        edges = {edge for edge in topology.edges if edge[0] in vertices and edge[1] in vertices}
        faces = {fi for fi, face in enumerate(topology.faces) if any(vi in vertices for vi in face)}
    elif source is MeshSelectionMode.EDGE:
        edges = {normalize_edge(*edge) for edge in state.selected_edges}
        vertices = {vi for edge in edges for vi in edge}
        faces = {fi for edge in edges for fi in topology.get_faces_for_edge(edge)}
        borders = {idx for idx, loop in enumerate(topology.border_loops) if _loop_has_selected_edge(loop, edges)}
    elif source is MeshSelectionMode.BORDER:
        for idx in state.selected_borders:
            if isinstance(idx, int) and 0 <= idx < len(topology.border_loops):
                loop = topology.border_loops[idx]
                vertices.update(loop)
                edges.update(normalize_edge(loop[i], loop[i + 1]) for i in range(len(loop) - 1))
        faces = {fi for edge in edges for fi in topology.get_faces_for_edge(edge)}
        borders = set(x for x in state.selected_borders if isinstance(x, int))
    elif source in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
        faces = set(state.selected_faces or state.selected_polygons)
        polygons = set(faces)
        for fi in faces:
            if 0 <= fi < len(topology.faces):
                vertices.update(topology.faces[fi])
                edges.update(topology.get_edges_for_face(fi))
    elif source is MeshSelectionMode.ELEMENT:
        elements = set(state.selected_elements)
        for idx in elements:
            if 0 <= idx < len(topology.connected_elements):
                faces.update(topology.connected_elements[idx])
        polygons = set(faces)
        for fi in faces:
            vertices.update(topology.faces[fi])
            edges.update(topology.get_edges_for_face(fi))

    if target_mode is MeshSelectionMode.VERTEX:
        state.clear_subobject_selection()
        state.selected_vertices = vertices
    elif target_mode is MeshSelectionMode.EDGE:
        state.clear_subobject_selection()
        state.selected_edges = edges
    elif target_mode is MeshSelectionMode.BORDER:
        state.clear_subobject_selection()
        state.selected_borders = borders or {
            idx for idx, loop in enumerate(topology.border_loops) if _loop_has_selected_edge(loop, edges)
        }
    elif target_mode is MeshSelectionMode.FACE:
        state.clear_subobject_selection()
        state.selected_faces = faces
    elif target_mode is MeshSelectionMode.POLYGON:
        state.clear_subobject_selection()
        state.selected_polygons = polygons or faces
        if state.selected_polygons:
            state.status_message = "Polygon Mode is using individual faces for this triangulated mesh."
    elif target_mode is MeshSelectionMode.ELEMENT:
        selected_elements = set(elements)
        for idx, element_faces in enumerate(topology.connected_elements):
            if faces.intersection(element_faces):
                selected_elements.add(idx)
        state.clear_subobject_selection()
        state.selected_elements = selected_elements
    state.mode = target_mode
    return MeshOperationResult.ok(f"Converted {source.label} selection to {target_mode.label}.", selection_changed=True)


def _loop_has_selected_edge(loop: list[int], edges: set[tuple[int, int]]) -> bool:
    return any(normalize_edge(loop[i], loop[i + 1]) in edges for i in range(len(loop) - 1))
