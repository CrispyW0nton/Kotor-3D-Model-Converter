"""Bridge compatible border edges or loops."""

from __future__ import annotations

from .mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge


def bridge_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    topology = MeshTopology.build_from_mesh(mesh)
    loops: list[list[int]] = []
    if state.mode is MeshSelectionMode.BORDER:
        for idx in state.selected_borders:
            if isinstance(idx, int) and 0 <= idx < len(topology.border_loops):
                loops.append(_strip_closing_vertex(topology.border_loops[idx]))
    elif state.mode is MeshSelectionMode.EDGE:
        selected = {normalize_edge(*edge) for edge in state.selected_edges}
        if not selected:
            return MeshOperationResult.fail("Select two border edges or two matching border loops to bridge.")
        if not selected.issubset(topology.border_edges):
            return MeshOperationResult.fail("Bridge requires selected edges to be open border edges.")
        for edge in selected:
            idx = topology.border_index_for_edge(edge)
            if idx is not None:
                candidate = _strip_closing_vertex(topology.border_loops[idx])
                if candidate not in loops:
                    loops.append(candidate)
    else:
        return MeshOperationResult.fail("Bridge works in Border or Edge mode.")
    if len(loops) != 2:
        return MeshOperationResult.fail("Bridge requires exactly two selected borders or compatible border edge chains.")
    a, b = loops
    if len(a) != len(b):
        return MeshOperationResult.fail("Selected borders do not match. Future resampling support can handle different counts.")
    if len(a) < 2:
        return MeshOperationResult.fail("Selected borders are too small to bridge.")
    twist = int(options.bridge_twist) % len(b)
    b = b[twist:] + b[:twist]
    new_faces = []
    for i in range(len(a)):
        a0, a1 = a[i], a[(i + 1) % len(a)]
        b0, b1 = b[i], b[(i + 1) % len(b)]
        # GhostRigger's current mesh format is triangle-based, so bridge quads
        # are triangulated consistently here. Quad/ngon storage can expand this.
        new_faces.append((a0, a1, b1))
        new_faces.append((a0, b1, b0))
    start = len(getattr(mesh, "faces", []) or [])
    mesh.faces = list(getattr(mesh, "faces", []) or []) + new_faces
    if options.preserve_materials and hasattr(mesh, "face_mats"):
        mesh.face_mats = list(getattr(mesh, "face_mats", []) or []) + [0] * len(new_faces)
    if hasattr(mesh, "compute_bounds"):
        mesh.compute_bounds()
    state.selected_faces = set(range(start, start + len(new_faces)))
    state.selected_borders.clear()
    state.mode = MeshSelectionMode.FACE
    return MeshOperationResult.ok(
        f"Bridged borders with {len(new_faces)} triangle face(s).",
        changed_mesh_ids=[str(getattr(mesh, "name", id(mesh)))],
        selection_changed=True,
        topology_changed=True,
    )


def _strip_closing_vertex(loop: list[int]) -> list[int]:
    if len(loop) > 1 and loop[0] == loop[-1]:
        return list(loop[:-1])
    return list(loop)
