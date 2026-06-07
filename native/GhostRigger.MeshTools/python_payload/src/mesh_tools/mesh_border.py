"""Border detection and capping helpers."""

from __future__ import annotations

from .mesh_edit_types import MeshOperationOptions, MeshOperationResult
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology


def cap_selected_borders(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    topology = MeshTopology.build_from_mesh(mesh)
    if not state.selected_borders:
        return MeshOperationResult.fail("Select one border loop to cap.")
    if len(state.selected_borders) != 1:
        return MeshOperationResult.fail("Cap Border supports one selected border loop in this pass.")
    border_idx = next(iter(state.selected_borders))
    if not isinstance(border_idx, int) or border_idx < 0 or border_idx >= len(topology.border_loops):
        return MeshOperationResult.fail("Selected border is no longer valid.")
    loop = list(topology.border_loops[border_idx])
    if len(loop) < 3:
        return MeshOperationResult.fail("Border is too small to cap.")
    if loop[0] != loop[-1]:
        return MeshOperationResult.fail("Border is not closed; open chains cannot be capped safely yet.")
    verts = loop[:-1]
    if len(verts) < 3:
        return MeshOperationResult.fail("Border is too small to cap.")
    new_faces = []
    anchor = verts[0]
    for i in range(1, len(verts) - 1):
        new_faces.append((anchor, verts[i], verts[i + 1]))
    start = len(getattr(mesh, "faces", []) or [])
    mesh.faces = list(getattr(mesh, "faces", []) or []) + new_faces
    if options.preserve_materials:
        mat = _default_material_for_cap(mesh, topology, border_idx)
        mesh.face_mats = list(getattr(mesh, "face_mats", []) or []) + [mat] * len(new_faces)
    state.mode = state.mode
    state.selected_faces = set(range(start, start + len(new_faces)))
    state.selected_borders.clear()
    _refresh_mesh(mesh)
    return MeshOperationResult.ok(
        f"Capped border with {len(new_faces)} triangle face(s).",
        changed_mesh_ids=[_mesh_id(mesh)],
        selection_changed=True,
        topology_changed=True,
    )


def _default_material_for_cap(mesh, topology: MeshTopology, border_idx: int) -> int:
    face_mats = getattr(mesh, "face_mats", []) or []
    loop = topology.border_loops[border_idx]
    adjacent_faces = set()
    for i in range(len(loop) - 1):
        adjacent_faces.update(topology.get_faces_for_edge((loop[i], loop[i + 1])))
    for fi in adjacent_faces:
        if fi < len(face_mats):
            return int(face_mats[fi])
    return 0


def _refresh_mesh(mesh) -> None:
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()


def _mesh_id(mesh) -> str:
    return str(getattr(mesh, "name", id(mesh)))
