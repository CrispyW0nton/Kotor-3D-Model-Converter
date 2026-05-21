"""Facade for editable-poly style mesh operations."""

from __future__ import annotations

from .mesh_border import cap_selected_borders
from .mesh_bridge import bridge_selected
from .mesh_connect import connect_selected
from .mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from .mesh_history import MeshHistory
from .mesh_preservation import filter_face_attributes
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge
from .mesh_weld import target_weld_edge, target_weld_vertex, weld_selected_vertices


def delete_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    faces_to_delete: set[int] = set()
    topology = MeshTopology.build_from_mesh(mesh)
    if state.mode is MeshSelectionMode.VERTEX:
        vertices = set(state.selected_vertices)
        faces_to_delete = {fi for fi, face in enumerate(topology.faces) if vertices.intersection(face)}
    elif state.mode is MeshSelectionMode.EDGE:
        edges = {normalize_edge(*edge) for edge in state.selected_edges}
        faces_to_delete = {fi for edge in edges for fi in topology.get_faces_for_edge(edge)}
    elif state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
        faces_to_delete = set(state.selected_faces or state.selected_polygons)
    elif state.mode is MeshSelectionMode.ELEMENT:
        for idx in state.selected_elements:
            if 0 <= idx < len(topology.connected_elements):
                faces_to_delete.update(topology.connected_elements[idx])
    elif state.mode is MeshSelectionMode.BORDER:
        return MeshOperationResult.fail("Border Delete can create ambiguous holes; delete adjacent faces or use Cap Border after face deletion.")
    else:
        return MeshOperationResult.fail("Select sub-objects before using Delete.")
    if not faces_to_delete:
        return MeshOperationResult.fail("Nothing selected to delete.")
    kept = [i for i in range(len(topology.faces)) if i not in faces_to_delete]
    mesh.faces = [topology.faces[i] for i in kept]
    filter_face_attributes(mesh, kept)
    state.clear_subobject_selection()
    warnings = []
    if options.remove_isolated_vertices:
        removed = remove_isolated_vertices(mesh)
        if removed.success:
            warnings.extend(removed.warnings)
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()
    return MeshOperationResult.ok("Deleted selected sub-objects.", changed_mesh_ids=[_mesh_id(mesh)], selection_changed=True, topology_changed=True, warnings=warnings)


def remove_isolated_vertices(mesh) -> MeshOperationResult:
    faces = [tuple(map(int, face[:3])) for face in (getattr(mesh, "faces", []) or [])]
    used = sorted({vi for face in faces for vi in face})
    if len(used) == len(getattr(mesh, "vertices", []) or []):
        return MeshOperationResult.ok("No isolated vertices found.")
    remap = {old: new for new, old in enumerate(used)}
    mesh.vertices = [getattr(mesh, "vertices")[i] for i in used]
    mesh.faces = [tuple(remap[vi] for vi in face) for face in faces]
    for attr in ("normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3", "skin_data"):
        values = list(getattr(mesh, attr, []) or [])
        if values and len(values) >= max(used, default=-1) + 1:
            setattr(mesh, attr, [values[i] for i in used])
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()
    return MeshOperationResult.ok("Removed isolated vertices.", changed_mesh_ids=[_mesh_id(mesh)], topology_changed=True)


def flip_normals(mesh, state: MeshSelectionState | None = None) -> MeshOperationResult:
    faces = list(getattr(mesh, "faces", []) or [])
    indices = _selected_face_indices(mesh, state)
    if not indices:
        indices = set(range(len(faces)))
    for fi in indices:
        if 0 <= fi < len(faces):
            a, b, c = faces[fi]
            faces[fi] = (a, c, b)
    mesh.faces = faces
    if hasattr(mesh, "normals") and getattr(mesh, "normals", None):
        mesh.normals = [(-float(n[0]), -float(n[1]), -float(n[2])) for n in mesh.normals]
    return MeshOperationResult.ok("Flipped normals.", changed_mesh_ids=[_mesh_id(mesh)], topology_changed=True)


def recalculate_normals(mesh, state: MeshSelectionState | None = None) -> MeshOperationResult:
    topology = MeshTopology.build_from_mesh(mesh)
    mesh.normals = list(topology.vertex_normals)
    return MeshOperationResult.ok("Recalculated vertex normals.", changed_mesh_ids=[_mesh_id(mesh)], topology_changed=False)


def detach_selection(mesh, state: MeshSelectionState, *, as_clone: bool = False):
    import copy

    topology = MeshTopology.build_from_mesh(mesh)
    selected_faces = _selected_face_indices(mesh, state)
    if not selected_faces:
        return MeshOperationResult.fail("Detach Selection works with selected faces, polygons, or elements."), None
    detached = copy.deepcopy(mesh)
    detached.name = f"{getattr(mesh, 'name', 'mesh')}_detached"
    used = sorted({vi for fi in selected_faces for vi in topology.faces[fi]})
    remap = {old: new for new, old in enumerate(used)}
    detached.vertices = [mesh.vertices[i] for i in used]
    detached.faces = [tuple(remap[vi] for vi in topology.faces[fi]) for fi in sorted(selected_faces)]
    for attr in ("normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3", "skin_data"):
        values = list(getattr(mesh, attr, []) or [])
        if values and len(values) >= max(used, default=-1) + 1:
            setattr(detached, attr, [values[i] for i in used])
    for attr in ("face_mats", "face_uvs"):
        values = list(getattr(mesh, attr, []) or [])
        if values:
            setattr(detached, attr, [values[i] for i in sorted(selected_faces) if i < len(values)])
    if not as_clone:
        kept = [i for i in range(len(topology.faces)) if i not in selected_faces]
        mesh.faces = [topology.faces[i] for i in kept]
        filter_face_attributes(mesh, kept)
    for node in (mesh, detached):
        if hasattr(node, "compute_bounds"):
            node.compute_bounds()
    return MeshOperationResult.ok("Detached selection.", changed_mesh_ids=[_mesh_id(mesh), _mesh_id(detached)], selection_changed=True, topology_changed=True), detached


def _selected_face_indices(mesh, state: MeshSelectionState | None) -> set[int]:
    if state is None:
        return set()
    if state.mode is MeshSelectionMode.FACE:
        return set(state.selected_faces)
    if state.mode is MeshSelectionMode.POLYGON:
        return set(state.selected_polygons or state.selected_faces)
    if state.mode is MeshSelectionMode.ELEMENT:
        topology = MeshTopology.build_from_mesh(mesh)
        faces = set()
        for idx in state.selected_elements:
            if 0 <= idx < len(topology.connected_elements):
                faces.update(topology.connected_elements[idx])
        return faces
    return set()


def _mesh_id(mesh) -> str:
    return str(getattr(mesh, "name", id(mesh)))


__all__ = [
    "MeshHistory",
    "cap_selected_borders",
    "bridge_selected",
    "connect_selected",
    "delete_selected",
    "detach_selection",
    "flip_normals",
    "recalculate_normals",
    "remove_isolated_vertices",
    "target_weld_edge",
    "target_weld_vertex",
    "weld_selected_vertices",
]
