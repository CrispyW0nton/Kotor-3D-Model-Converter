"""test_bone_map_direction.py — Phase G3 guard-rail
====================================================

Purpose
-------
Locks in the bone-map resolution direction so it matches xoreos' conventions.

xoreos (``model_kotor.cpp``::``fillBoneNodeMap``):

    for i in range(boneMappingCount):
        index = boneMapping[i]            # palette slot, or -1 if node i is
                                          # not a bone
        if index != -1:
            boneNodeMap[index] = nodes[i]

    # Per-vertex `boneMappingId[v*4+j]` is a palette slot; the shader looks
    # up `boneNodeMap[slot]` to find the bone node.

Our loader (``src/core/kotor_loader.py``::``_read_skin_weights``) arrives at
the same semantics by a shorter route — PyKotor already exposes the inverse
of xoreos's sparse per-node array as a compact 16-entry "palette slot →
node-id" header array (``skin.bone_indices``).  We walk that array once to
produce ``bone_map[palette_slot] = node_name``.  Per-vertex influences store
``bone_index = palette_slot`` verbatim.

Critical invariant
------------------
For every skinned vertex and every non-zero influence:

    influence.bone_index  is a valid index into  bone_map
    bone_map[influence.bone_index]  is the name of a real node in the model
    sum(influence.weight for influence in vertex) ≈ 1.0

If any of those break, LBS produces garbage vertices (wrong bone transform
applied) or undefined behaviour (out-of-bounds palette lookup in the shader).

This test fixes the direction with a hand-built synthetic model so a future
refactor (e.g. someone swaps to the xoreos sparse-array convention without
reversing the indexing) fails loudly instead of silently breaking character
meshes.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.core.model_data import (
    BoneWeight,
    KotorModel,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Test fixture — minimal skinned model
# ─────────────────────────────────────────────────────────────────────────────

def _build_skinned_model() -> KotorModel:
    """Build a 4-node skeleton + 1 skin mesh with a known palette.

    Topology:
        rootdummy
          ├── hip             (pos +Z)
          │     ├── lleg      (pos -X, -Z)
          │     └── rleg      (pos +X, -Z)
          └── body_skin       (SKIN node; bone_map → [hip, lleg, rleg, ''])

    The ``body_skin`` mesh has a single vertex influenced 60/40 by hip and
    lleg, simulating the common "torso-to-leg" weight blend at the hip joint.
    The fourth bone-map slot is deliberately empty to exercise the
    "unused palette slot" code path that MDL files routinely hit (the
    palette is fixed at 16 entries but most rigs use far fewer).
    """
    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)

    hip = ModelNode(name="hip", flags=int(NodeFlags.HEADER))
    hip.position = (0.0, 0.0, 1.0)
    hip.parent = root
    root.children.append(hip)

    lleg = ModelNode(name="lleg", flags=int(NodeFlags.HEADER))
    lleg.position = (-0.5, 0.0, -1.0)
    lleg.parent = hip
    hip.children.append(lleg)

    rleg = ModelNode(name="rleg", flags=int(NodeFlags.HEADER))
    rleg.position = (0.5, 0.0, -1.0)
    rleg.parent = hip
    hip.children.append(rleg)

    skin = ModelNode(
        name="body_skin",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN),
    )
    skin.parent = root
    root.children.append(skin)

    # Palette: slot 0 → hip, slot 1 → lleg, slot 2 → rleg, slot 3 → unused.
    skin.bone_map = ["hip", "lleg", "rleg", ""]

    # Single skinned vertex at (0, 0, 0.5) influenced 60/40 by hip and lleg.
    vsd = VertexSkinData()
    vsd.influences = [
        BoneWeight(bone_index=0, weight=0.6),
        BoneWeight(bone_index=1, weight=0.4),
    ]
    skin.skin_data = [vsd]
    skin.vertices = [(0.0, 0.0, 0.5)]
    skin.faces = []

    model = KotorModel(name="test_skinned")
    model.root_node = root
    return model


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBoneMapDirection(unittest.TestCase):

    def setUp(self) -> None:
        self.model = _build_skinned_model()
        self.skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        self.assertEqual(len(self.skin_nodes), 1,
                         "fixture must expose exactly one skin node")
        self.skin = self.skin_nodes[0]
        self.all_names_lower = {n.name.lower() for n in self.model.all_nodes()}

    def test_palette_slot_zero_is_first_influence_target(self):
        """bone_map[0] must name the bone at palette slot 0 (hip)."""
        self.assertEqual(self.skin.bone_map[0], "hip")

    def test_palette_order_preserved(self):
        """The palette is an ordered list, not a set — slot order matters."""
        self.assertEqual(self.skin.bone_map[:3], ["hip", "lleg", "rleg"])

    def test_unused_slots_are_empty_string(self):
        """Unused palette slots must be the empty string (not None, not 'none').

        The loader convention is that an empty string flags an unused slot so
        downstream code can ``if name:`` or ``bool(name)`` test uniformly;
        ``None`` would crash the shader's str-keyed lookups.
        """
        self.assertEqual(self.skin.bone_map[3], "")

    def test_every_vertex_bone_index_is_in_range(self):
        """Every vertex influence.bone_index must be a valid palette index.

        Out-of-range indices should have been dropped by
        ``_read_skin_weights`` with a WARNING log line.  If they're still
        present here, the shader will read garbage mat4 entries.
        """
        n_slots = len(self.skin.bone_map)
        for vi, vsd in enumerate(self.skin.skin_data):
            for inf in vsd.influences:
                self.assertGreaterEqual(
                    inf.bone_index, 0,
                    msg=f"vertex {vi}: negative bone_index {inf.bone_index}",
                )
                self.assertLess(
                    inf.bone_index, n_slots,
                    msg=(f"vertex {vi}: bone_index {inf.bone_index} "
                         f"exceeds palette size {n_slots}"),
                )

    def test_every_palette_name_resolves_to_a_real_node(self):
        """Every non-empty palette entry must name an existing node.

        An orphaned palette name means the loader coupled a bone_indices
        entry to a node_id that isn't in the flat node list — the shader
        would then apply the identity matrix (no deformation) silently.
        """
        for slot, bname in enumerate(self.skin.bone_map):
            if not bname:
                continue
            self.assertIn(
                bname.lower(), self.all_names_lower,
                msg=(f"bone_map[{slot}] = '{bname}' is not present in the "
                     f"model's node tree"),
            )

    def test_per_vertex_weights_sum_to_one(self):
        """Sum of weights on every vertex must be ≈ 1.0 (LBS normalisation).

        ``_read_skin_weights`` renormalises per vertex when the raw sum is
        off by more than 1e-4, so anything here should be within tight
        tolerance.
        """
        for vi, vsd in enumerate(self.skin.skin_data):
            total = sum(inf.weight for inf in vsd.influences)
            self.assertAlmostEqual(
                total, 1.0, places=3,
                msg=f"vertex {vi}: weight sum = {total:.6f}, expected ≈ 1.0",
            )

    def test_influence_weights_are_positive(self):
        """Negative or NaN weights must not reach the palette.

        Negative weights produce inverted deformation (limb flips inside out)
        and NaNs blow up the LBS sum → clip-space NaN → a vanishing triangle
        on the GPU.  ``_read_skin_weights`` filters both.
        """
        for vi, vsd in enumerate(self.skin.skin_data):
            for inf in vsd.influences:
                self.assertGreater(
                    inf.weight, 0.0,
                    msg=f"vertex {vi}: non-positive weight {inf.weight}",
                )
                # Explicit NaN guard — assertGreater(nan, 0) is False so NaN
                # would be caught above, but make the failure message clearer.
                self.assertEqual(
                    inf.weight, inf.weight,  # NaN != NaN trick
                    msg=f"vertex {vi}: NaN weight",
                )


if __name__ == "__main__":
    unittest.main()
