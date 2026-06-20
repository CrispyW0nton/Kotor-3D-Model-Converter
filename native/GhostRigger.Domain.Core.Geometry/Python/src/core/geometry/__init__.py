"""Core model data structures and geometry utilities."""

from .component_editing import (
    ComponentEditResult,
    ComponentMesh,
    cleanup_degenerate_faces,
    component_mesh,
    flatten_vertices,
    snap_vertex_to_vertex,
    snap_vertices_to_grid,
    triangulate_faces,
    weld_vertices,
)

__all__ = [
    "ComponentEditResult",
    "ComponentMesh",
    "cleanup_degenerate_faces",
    "component_mesh",
    "flatten_vertices",
    "snap_vertex_to_vertex",
    "snap_vertices_to_grid",
    "triangulate_faces",
    "weld_vertices",
]
