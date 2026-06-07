"""Selection mode shortcut metadata."""

from __future__ import annotations

from .mesh_edit_types import MeshSelectionMode


MESH_SELECTION_SHORTCUTS = {
    "1": MeshSelectionMode.VERTEX,
    "2": MeshSelectionMode.EDGE,
    "3": MeshSelectionMode.BORDER,
    "4": MeshSelectionMode.POLYGON,
    "5": MeshSelectionMode.ELEMENT,
}


MODE_ORDER = (
    MeshSelectionMode.OBJECT,
    MeshSelectionMode.VERTEX,
    MeshSelectionMode.EDGE,
    MeshSelectionMode.BORDER,
    MeshSelectionMode.FACE,
    MeshSelectionMode.POLYGON,
    MeshSelectionMode.ELEMENT,
)
