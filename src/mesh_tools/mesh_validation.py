"""Validation helpers for editable mesh operations."""

from __future__ import annotations

from .mesh_edit_types import MeshValidationReport
from .mesh_topology import MeshTopology


def validate_mesh(mesh) -> MeshValidationReport:
    return MeshTopology.build_from_mesh(mesh).validate_manifold_state()
