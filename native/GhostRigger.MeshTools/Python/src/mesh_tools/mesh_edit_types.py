"""Shared mesh editing types used by UI and headless operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MeshSelectionMode(Enum):
    """Sub-object levels exposed to artists in the Mesh Tools dock.

    Object selects whole mesh nodes. Vertex/Edge/Border/Face select raw
    topology. Polygon is a logical surface layer; when no polygon grouping
    metadata exists it intentionally falls back to raw face indices. Element
    selects connected mesh islands inside one editable mesh.
    """

    OBJECT = "object"
    VERTEX = "vertex"
    EDGE = "edge"
    BORDER = "border"
    FACE = "face"
    POLYGON = "polygon"
    ELEMENT = "element"

    @property
    def label(self) -> str:
        return self.value.title()


@dataclass(slots=True)
class MeshOperationResult:
    success: bool
    message: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    changed_mesh_ids: list[str] = field(default_factory=list)
    selection_changed: bool = False
    topology_changed: bool = False

    @classmethod
    def ok(
        cls,
        message: str,
        *,
        changed_mesh_ids: list[str] | None = None,
        selection_changed: bool = False,
        topology_changed: bool = False,
        warnings: list[str] | None = None,
    ) -> "MeshOperationResult":
        return cls(
            True,
            message,
            warnings=list(warnings or []),
            changed_mesh_ids=list(changed_mesh_ids or []),
            selection_changed=selection_changed,
            topology_changed=topology_changed,
        )

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> "MeshOperationResult":
        return cls(False, message, warnings=list(warnings or []), errors=list(errors or [message]))


@dataclass(slots=True)
class MeshValidationReport:
    has_errors: bool = False
    has_warnings: bool = False
    non_manifold_edges: list[tuple[int, int]] = field(default_factory=list)
    border_edges: list[tuple[int, int]] = field(default_factory=list)
    isolated_vertices: list[int] = field(default_factory=list)
    degenerate_faces: list[int] = field(default_factory=list)
    inverted_faces: list[int] = field(default_factory=list)
    duplicate_vertices: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def finalize(self) -> "MeshValidationReport":
        self.has_errors = bool(self.non_manifold_edges or self.degenerate_faces)
        self.has_warnings = bool(
            self.border_edges
            or self.isolated_vertices
            or self.inverted_faces
            or self.duplicate_vertices
            or self.notes
        )
        return self


@dataclass(slots=True)
class MeshOperationOptions:
    weld_threshold: float = 0.001
    bridge_segments: int = 1
    bridge_twist: int = 0
    bridge_smooth: bool = False
    connect_segments: int = 1
    connect_pinch: float = 0.0
    connect_slide: float = 0.0
    preserve_uvs: bool = True
    preserve_materials: bool = True
    preserve_normals: bool = True
    preserve_aurora_metadata: bool = True
    remove_isolated_vertices: bool = True
    allow_degenerate_cleanup: bool = True
