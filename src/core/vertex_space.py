"""
vertex_space.py — Per-Node Vertex Coordinate Space Contract
============================================================
Phase D20-M (reset).  Every node gets a vertex_space classification at
load time.  All code that transforms vertices (VBO builder, bounds
calculators, viewport) reads this ONE field instead of re-deriving the
answer with centroid heuristics.

The classification uses ONLY node flags and model metadata — never
centroid magnitude, vertex counts, or node-name substrings.

References:
  xoreos  model_kotor.cpp readMesh/readSkin — vertices stored node-local
  KotOR.js OdysseyModelNodeMesh.ts           — raw MDX read, no transform
  KotOR.js OdysseyModel3D.ts NodeMeshBuilder — THREE.js matrixWorld
"""

from enum import IntEnum
import logging

log = logging.getLogger(__name__)


class VertexSpace(IntEnum):
    """Per-node vertex coordinate space.

    NODE_LOCAL (0)
        Vertices are in the node's local coordinate system.
        To get world coordinates: apply world_transform() = parent-chain
        rotation + translation.  This is the DEFAULT for every KotOR MDL
        node — MESH, SKIN, DANGLY, SABER, everything.
        Citation: xoreos readMesh (raw MDX read, no transform);
                  KotOR.js OdysseyModelNodeMesh (raw push to array).

    WORLD (1)
        Vertices are already in model-root space.  Do NOT apply
        world_transform.
        This value is NEVER set by the loader for standard KotOR MDL
        data.  It exists only as an escape hatch for externally-imported
        OBJ/FBX meshes that may have been pre-transformed.

    AABB_WALK (2)
        Walkmesh / collision node.  Not rendered — skip in all rendering
        and bounds code.  Set for nodes with kNodeFlagHasAABB (0x0200).
    """
    NODE_LOCAL = 0
    WORLD      = 1
    AABB_WALK  = 2


def compute_vertex_space(node, model) -> VertexSpace:
    """Classify a node's vertex space from MDL flags and model metadata.

    Rules (no centroid checks, no name-suffix checks, no thresholds):

    1. AABB nodes (flag 0x0200) → AABB_WALK (not rendered)
    2. Imported nodes (_imported=True) → WORLD (already pre-transformed)
    3. Everything else → NODE_LOCAL

    That's it.  Both MESH and SKIN nodes store vertices in node-local
    space per the xoreos and KotOR.js reference implementations.
    The historical GhostRigger "SkinSpace.WORLD" concept (skin verts
    are already world-space) is WRONG — it was a workaround for a bug
    where skin nodes' parent-chain transform was identity, making
    local == world a coincidence, not a property of the data format.
    """
    flags = getattr(node, 'flags', 0) or 0

    # Rule 1: AABB walkmesh
    AABB_FLAG = 0x0200
    if flags & AABB_FLAG:
        return VertexSpace.AABB_WALK

    # Rule 2: externally imported geometry
    if getattr(node, '_imported', False):
        return VertexSpace.WORLD

    # Rule 3: all KotOR MDL nodes — node-local
    return VertexSpace.NODE_LOCAL
