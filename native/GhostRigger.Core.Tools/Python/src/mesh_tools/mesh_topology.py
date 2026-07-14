"""Compatibility façade for GhostRigger's shared topology engine.

Reusable connectivity belongs to ``GhostRigger.Core.Math``.  The public
``mesh_tools.mesh_topology`` import remains stable for existing Mesh Tools
callers while Map Studio, Character Studio, and validation can consume the
same format-agnostic half-edge implementation.
"""

import importlib
import sys


# Desktop payloads use ``src.core`` while focused package tests and older
# scripts may have already loaded ``core`` from the package root.  Re-importing
# the same source under both names creates distinct class objects and breaks
# isinstance/identity contracts.  Reuse whichever canonical module is already
# resident; otherwise prefer the desktop ``src.core`` route.
_shared = (
    sys.modules.get("src.core.geometry.mesh_topology")
    or sys.modules.get("core.geometry.mesh_topology")
    or importlib.import_module("src.core.geometry.mesh_topology")
)

CompactedMesh = _shared.CompactedMesh
Edge = _shared.Edge
Face = _shared.Face
HalfEdge = _shared.HalfEdge
IndexRemap = _shared.IndexRemap
MeshTopology = _shared.MeshTopology
TopologyAudit = _shared.TopologyAudit
TopologyChangeSet = _shared.TopologyChangeSet
TopologyComponent = _shared.TopologyComponent
Vector3 = _shared.Vector3
compact_indexed_mesh = _shared.compact_indexed_mesh
face_edges = _shared.face_edges
normalize_edge = _shared.normalize_edge


__all__ = [
    "CompactedMesh",
    "Edge",
    "Face",
    "HalfEdge",
    "IndexRemap",
    "MeshTopology",
    "TopologyAudit",
    "TopologyChangeSet",
    "TopologyComponent",
    "Vector3",
    "compact_indexed_mesh",
    "face_edges",
    "normalize_edge",
]
