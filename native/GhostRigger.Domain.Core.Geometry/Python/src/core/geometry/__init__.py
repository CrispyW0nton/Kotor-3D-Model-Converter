"""Core model data structures and geometry utilities."""

from .component_editing import (
    ComponentEditAudit,
    ComponentEditResult,
    ComponentMesh,
    audit_component_edit_result,
    bridge_edges,
    cleanup_degenerate_faces,
    cleanup_face_normals,
    component_mesh,
    fill_face,
    flatten_vertices,
    mirror_vertices,
    snap_vertex_to_vertex,
    snap_vertices_to_grid,
    triangulate_faces,
    weld_vertices,
)

__all__ = [
    "ComponentEditAudit",
    "ComponentEditResult",
    "ComponentMesh",
    "audit_component_edit_result",
    "bridge_edges",
    "cleanup_degenerate_faces",
    "cleanup_face_normals",
    "component_mesh",
    "fill_face",
    "flatten_vertices",
    "mirror_vertices",
    "snap_vertex_to_vertex",
    "snap_vertices_to_grid",
    "triangulate_faces",
    "weld_vertices",
]
