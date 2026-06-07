"""Current editable mesh selection state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .mesh_edit_types import MeshSelectionMode
from .mesh_topology import normalize_edge


@dataclass
class MeshSelectionState:
    active_mesh_id: str | None = None
    selected_mesh_ids: set[str] = field(default_factory=set)
    mode: MeshSelectionMode = MeshSelectionMode.OBJECT
    selected_vertices: set[int] = field(default_factory=set)
    selected_edges: set[tuple[int, int]] = field(default_factory=set)
    selected_faces: set[int] = field(default_factory=set)
    selected_polygons: set[int] = field(default_factory=set)
    selected_borders: set[int] | set[tuple[int, ...]] = field(default_factory=set)
    selected_elements: set[int] = field(default_factory=set)
    status_message: str = ""

    def clear_subobject_selection(self) -> None:
        self.selected_vertices.clear()
        self.selected_edges.clear()
        self.selected_faces.clear()
        self.selected_polygons.clear()
        self.selected_borders.clear()
        self.selected_elements.clear()

    def set_mode(self, mode: MeshSelectionMode) -> None:
        if self.mode is not mode:
            self.mode = mode
            self.clear_subobject_selection()

    def set_edges(self, edges) -> None:
        self.selected_edges = {normalize_edge(int(a), int(b)) for a, b in edges}

    def counts(self) -> dict[str, int]:
        return {
            "meshes": len(self.selected_mesh_ids),
            "vertices": len(self.selected_vertices),
            "edges": len(self.selected_edges),
            "borders": len(self.selected_borders),
            "faces": len(self.selected_faces),
            "polygons": len(self.selected_polygons),
            "elements": len(self.selected_elements),
        }
