"""Editable-poly style mesh editing backend for GhostRigger."""

from pathlib import Path

_ROOT = next((parent for parent in Path(__file__).resolve().parents if (parent / "native").exists()), Path(__file__).resolve().parents[2])
_PACKAGE_PAYLOAD = _ROOT / "native" / "GhostRigger.Core.Tools" / "Python" / "src" / "mesh_tools"
if _PACKAGE_PAYLOAD.exists():
    __path__.append(str(_PACKAGE_PAYLOAD))  # type: ignore[name-defined]

from .mesh_edit_types import MeshOperationResult, MeshSelectionMode, MeshValidationReport
from .mesh_selection_state import MeshSelectionState
from .mesh_topology import MeshTopology, normalize_edge

__all__ = [
    "MeshOperationResult",
    "MeshSelectionMode",
    "MeshSelectionState",
    "MeshTopology",
    "MeshValidationReport",
    "normalize_edge",
]
