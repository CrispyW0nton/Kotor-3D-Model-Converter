"""Simple vertex and edge connect operations."""

from __future__ import annotations

from .mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge


def connect_selected(mesh, state: MeshSelectionState, options: MeshOperationOptions | None = None) -> MeshOperationResult:
    options = options or MeshOperationOptions()
    if state.mode is MeshSelectionMode.VERTEX:
        return _connect_vertices(mesh, state)
    if state.mode is MeshSelectionMode.EDGE:
        return _connect_edges(mesh, state, options)
    return MeshOperationResult.fail("Connect works in Vertex or Edge mode.")


def _connect_vertices(mesh, state: MeshSelectionState) -> MeshOperationResult:
    selected = sorted(state.selected_vertices)
    if len(selected) != 2:
        return MeshOperationResult.fail("Vertex Connect requires exactly two selected vertices in this pass.")
    a, b = selected
    topology = MeshTopology.build_from_mesh(mesh)
    if normalize_edge(a, b) in topology.edges:
        return MeshOperationResult.fail("Selected vertices are already connected by an edge.")
    shared_faces = set(topology.get_faces_for_vertex(a)).intersection(topology.get_faces_for_vertex(b))
    if not shared_faces:
        return MeshOperationResult.fail("Selected vertices must share a face boundary to connect safely.")
    # In triangle-only meshes there is no ngon to split; record the virtual edge
    # for selection/ring workflows without altering the render face buffer.
    custom = set(getattr(mesh, "_gr_connect_edges", set()) or set())
    custom.add(normalize_edge(a, b))
    setattr(mesh, "_gr_connect_edges", custom)
    state.selected_edges = {normalize_edge(a, b)}
    state.mode = MeshSelectionMode.EDGE
    return MeshOperationResult.ok("Connected vertices with an editable support edge.", changed_mesh_ids=[_mesh_id(mesh)], selection_changed=True)


def _connect_edges(mesh, state: MeshSelectionState, options: MeshOperationOptions) -> MeshOperationResult:
    edges = sorted({normalize_edge(*edge) for edge in state.selected_edges})
    if len(edges) < 2:
        return MeshOperationResult.fail("Edge Connect requires at least two selected edges.")
    topology = MeshTopology.build_from_mesh(mesh)
    if not set(edges).issubset(topology.edges):
        return MeshOperationResult.fail("Selected edges are no longer valid.")
    new_edges = set(getattr(mesh, "_gr_connect_edges", set()) or set())
    for first, second in zip(edges, edges[1:]):
        mid_a = _midpoint_vertex(mesh, first)
        mid_b = _midpoint_vertex(mesh, second)
        new_edges.add(normalize_edge(mid_a, mid_b))
    setattr(mesh, "_gr_connect_edges", new_edges)
    return MeshOperationResult.ok(
        "Connected selected edges with support edges. Full ring-cut geometry is reserved for the quad/ngon pass.",
        changed_mesh_ids=[_mesh_id(mesh)],
        selection_changed=True,
        warnings=["Connect Segments/Pinch/Slide are stored in the operation model; this first pass creates one support connection."],
    )


def _midpoint_vertex(mesh, edge: tuple[int, int]) -> int:
    vertices = list(getattr(mesh, "vertices", []) or [])
    a, b = edge
    pa, pb = vertices[a], vertices[b]
    midpoint = ((pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5, (pa[2] + pb[2]) * 0.5)
    vertices.append(midpoint)
    mesh.vertices = vertices
    for attr, default in (("uvs", (0.0, 0.0)), ("uvs_lm", (0.0, 0.0)), ("normals", (0.0, 0.0, 1.0))):
        values = list(getattr(mesh, attr, []) or [])
        if values:
            if len(values) > max(a, b):
                va, vb = values[a], values[b]
                try:
                    values.append(tuple((float(va[i]) + float(vb[i])) * 0.5 for i in range(len(va))))
                except Exception:
                    values.append(default)
            else:
                values.append(default)
            setattr(mesh, attr, values)
    return len(vertices) - 1


def _mesh_id(mesh) -> str:
    return str(getattr(mesh, "name", id(mesh)))
