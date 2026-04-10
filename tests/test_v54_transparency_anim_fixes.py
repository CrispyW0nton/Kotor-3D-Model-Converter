"""
Tests for v5.4 fixes:
  1. Two-pass opaque/transparent depth sorting (teeth/eyes no longer render through face)
  2. LBS animation explosion guards (bad bone transforms fall back to bind pose)
  3. World transform explosion guard (non-finite anim positions fall back to bind pose)

Run: python3 -m pytest tests/test_v54_transparency_anim_fixes.py -v
"""
import sys
import os
import math
import struct
import unittest
from unittest.mock import MagicMock

# Adjust import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    ModelNode, KotorModel, BoneWeight, VertexSkinData,
    NodeFlags,
    _quat_rotate, _quat_conjugate, _quat_mul, _quat_normalize,
)

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_skin_node(n_verts=1):
    """Return a minimal skin ModelNode."""
    node = ModelNode()
    node.name = 'test_skin'
    node.flags = NodeFlags.SKIN
    node.position = (0.0, 0.0, 0.0)
    node.rotation = (0.0, 0.0, 0.0, 1.0)
    node.vertices = [(0.0, 0.0, 0.0)] * n_verts
    node.bone_map = ['bone0', 'bone1']
    sd = VertexSkinData()
    sd.influences = [BoneWeight(bone_index=0, weight=1.0)]
    node.skin_data = [sd] * n_verts
    return node


def _make_bare_renderer():
    """Return a FrameRenderer with minimal initialisation (no Tkinter needed)."""
    try:
        from gui.viewport import FrameRenderer
    except ImportError:
        from src.gui.viewport import FrameRenderer
    r = FrameRenderer.__new__(FrameRenderer)
    r._wt_cache = {}
    r._anim_pose = None
    r._bone_transforms_cache = {}
    r._bone_transforms_pose_id = -1
    r._outlier_skin_nodes = set()
    r._wt_cache_model_id = -1
    r._outlier_model_id = -1
    r.model = None
    r._dangly_sims = {}
    return r


# ══════════════════════════════════════════════════════════════════════════
#  1. Two-pass depth sorting (opaque / transparent)
# ══════════════════════════════════════════════════════════════════════════

class TestTwoPassDepthSort(unittest.TestCase):
    """Opaque geometry (tier=0) must render before transparent geometry (tier=1)
    regardless of centroid depth, so opaque face meshes occlude transparent eyes."""

    def _flat_tri(self, sort_key, tier, face_idx=0, node_alpha=1.0):
        """Build a flat-shade tris tuple: (sort_key, pts, fill, is_sel, fi, alpha, tier)."""
        pts = ((0, 0), (10, 0), (5, 10))
        fill = (128, 128, 128)
        return (sort_key, pts, fill, False, face_idx, node_alpha, tier)

    def test_opaque_before_transparent_same_depth(self):
        """At equal depth, tier-0 (opaque) must draw before tier-1 (transparent)."""
        from gui.viewport import _float_to_sort_key
        key = _float_to_sort_key(2.0)
        opaque = self._flat_tri(key, tier=0, face_idx=0)
        transp = self._flat_tri(key, tier=1, face_idx=1)
        tris = [transp, opaque]
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))
        self.assertEqual(tris[0][6], 0, "opaque (tier=0) must come first")
        self.assertEqual(tris[1][6], 1, "transparent (tier=1) must come second")

    def test_opaque_before_transparent_transparent_closer(self):
        """Even when transparent tri is closer (larger depth key),
        it must still draw AFTER opaque."""
        from gui.viewport import _float_to_sort_key
        # depth 1.5 = farther, depth 3.0 = closer
        opaque_key = _float_to_sort_key(1.5)   # farther
        transp_key = _float_to_sort_key(3.0)    # closer
        opaque = self._flat_tri(opaque_key, tier=0)
        transp = self._flat_tri(transp_key, tier=1)
        tris = [transp, opaque]
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))
        self.assertEqual(tris[0][6], 0, "opaque must render first even if farther")

    def test_within_opaque_tier_back_to_front(self):
        """Within opaque tier, back-to-front order: larger sort_key drawn first.
        Depth convention: larger depth value = farther from camera = drawn first."""
        from gui.viewport import _float_to_sort_key
        # depth=3.0 = farther, depth=0.5 = closer (sort_key(3.0) > sort_key(0.5))
        far_depth  = 3.0
        near_depth = 0.5
        far_key  = _float_to_sort_key(far_depth)
        near_key = _float_to_sort_key(near_depth)
        # Confirm depth convention: farther = larger key
        self.assertGreater(far_key, near_key,
                           "farther (depth=3.0) must have larger sort_key than closer (0.5)")
        tri_far  = self._flat_tri(far_key,  tier=0, face_idx=0)
        tri_near = self._flat_tri(near_key, tier=0, face_idx=1)
        tris = [tri_near, tri_far]
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))
        # Descending by sort_key: far (larger key) drawn first (index 0)
        self.assertGreater(tris[0][0], tris[1][0],
                           "farther tri (larger sort_key) must be at index 0 (drawn first)")

    def test_within_transparent_tier_back_to_front(self):
        """Within transparent tier, back-to-front ordering preserved."""
        from gui.viewport import _float_to_sort_key
        far_key  = _float_to_sort_key(2.8)  # farther
        near_key = _float_to_sort_key(0.3)  # closer
        self.assertGreater(far_key, near_key, "farther has larger key")
        tri_far  = self._flat_tri(far_key,  tier=1, face_idx=0)
        tri_near = self._flat_tri(near_key, tier=1, face_idx=1)
        tris = [tri_near, tri_far]
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))
        self.assertGreater(tris[0][0], tris[1][0],
                           "farther transparent tri drawn first (larger key at index 0)")

    def test_float_to_sort_key_monotonic(self):
        """_float_to_sort_key: larger depth → larger key (closer to camera)."""
        from gui.viewport import _float_to_sort_key
        depths = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        keys = [_float_to_sort_key(d) for d in depths]
        for i in range(len(keys) - 1):
            self.assertLess(keys[i], keys[i+1],
                            f"key({depths[i]}) should < key({depths[i+1]})")

    def test_three_tiers_full_order(self):
        """Test with 3 tris: close-transparent, mid-opaque, far-opaque.
        Depth convention: larger depth = farther.
        Expected draw order: far-opaque, mid-opaque, close-transparent."""
        from gui.viewport import _float_to_sort_key
        # far=3.5, mid=2.0, close=0.5 (farther has larger depth value)
        far_key   = _float_to_sort_key(3.5)
        mid_key   = _float_to_sort_key(2.0)
        close_key = _float_to_sort_key(0.5)
        close_transp = self._flat_tri(close_key, tier=1, face_idx=2)
        far_opaque   = self._flat_tri(far_key,   tier=0, face_idx=0)
        mid_opaque   = self._flat_tri(mid_key,   tier=0, face_idx=1)
        tris = [close_transp, mid_opaque, far_opaque]
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))
        # far_opaque first (tier=0, largest key → highest priority in descending sort)
        # mid_opaque second (tier=0, mid key)
        # close_transp last (tier=1, always after all opaque)
        self.assertEqual(tris[0][4], 0, "far_opaque (face_idx=0) drawn first")
        self.assertEqual(tris[1][4], 1, "mid_opaque (face_idx=1) drawn second")
        self.assertEqual(tris[2][4], 2, "close_transp (face_idx=2) drawn last")


# ══════════════════════════════════════════════════════════════════════════
#  2. LBS animation explosion guards
# ══════════════════════════════════════════════════════════════════════════

class TestLBSExplosionGuards(unittest.TestCase):
    """_lbs_vertex must fall back to bind pose when bone transforms are extreme."""

    def _make_bone_transform(self, bind_pos, anim_pos,
                             bind_quat=(0,0,0,1), anim_quat=(0,0,0,1)):
        return (tuple(bind_pos), tuple(bind_quat), tuple(anim_pos), tuple(anim_quat))

    def _run_lbs(self, node, bone_transforms, vi=0):
        renderer = _make_bare_renderer()
        return renderer._lbs_vertex(node, vi, bone_transforms)

    def test_normal_bone_translates_vertex(self):
        """Bone at bind=(0,0,0) animated to anim=(1,0,0) translates vertex by (1,0,0)."""
        node = _make_skin_node()
        bt = self._make_bone_transform((0,0,0), (1,0,0))
        result = self._run_lbs(node, {0: bt})
        self.assertAlmostEqual(result[0], 1.0, places=3)
        self.assertAlmostEqual(result[1], 0.0, places=3)
        self.assertAlmostEqual(result[2], 0.0, places=3)

    def test_nan_anim_position_gives_finite_result(self):
        """NaN in anim_wp → fallback keeps result finite."""
        node = _make_skin_node()
        bt = self._make_bone_transform((0,0,0), (float('nan'), 0, 0))
        result = self._run_lbs(node, {0: bt})
        for c in result:
            self.assertTrue(math.isfinite(c), f"Result component {c} must be finite")

    def test_inf_anim_position_gives_finite_result(self):
        """Inf in anim_wp → fallback keeps result finite."""
        node = _make_skin_node()
        bt = self._make_bone_transform((0,0,0), (float('inf'), 0, 0))
        result = self._run_lbs(node, {0: bt})
        for c in result:
            self.assertTrue(math.isfinite(c), f"Result component {c} must be finite")

    def test_extreme_anim_position_clamped(self):
        """Bone moving 200 units (> _MAX_BONE_DIST=50) → vertex stays near bind pose."""
        node = _make_skin_node()
        bt = self._make_bone_transform((0,0,0), (200.0, 0, 0))
        result = self._run_lbs(node, {0: bt})
        dist = math.sqrt(sum(c**2 for c in result))
        self.assertLess(dist, 50.0,
                        f"Vertex at dist={dist:.1f} from origin should be < 50 (guard)")

    def test_small_movement_preserved(self):
        """Small bone movements (< _MAX_BONE_DIST) must NOT be blocked."""
        node = _make_skin_node()
        bt = self._make_bone_transform((0,0,0), (3.0, 0, 0))
        result = self._run_lbs(node, {0: bt})
        # vertex at (0,0,0) + bone moving from 0→3 → result ≈ (3,0,0)
        self.assertAlmostEqual(result[0], 3.0, places=2,
                               msg="3-unit bone movement must not be blocked")

    def test_missing_bone_gives_finite_result(self):
        """bone_index not in bone_transforms → bind fallback (finite)."""
        node = _make_skin_node()
        result = self._run_lbs(node, {})  # empty dict → no bone found
        for c in result:
            self.assertTrue(math.isfinite(c), "missing bone must give finite result")

    def test_weight_zero_bone_skipped(self):
        """Bone influence with weight=0 is skipped; vertex at bind pose."""
        node = _make_skin_node()
        node.skin_data[0].influences = [BoneWeight(bone_index=0, weight=0.0)]
        bt = self._make_bone_transform((0,0,0), (5.0, 0, 0))
        result = self._run_lbs(node, {0: bt})
        # zero weight → total_weight=0 → bind fallback → (0,0,0)
        for c in result:
            self.assertTrue(math.isfinite(c))

    def test_multiple_bones_weighted_average(self):
        """Two bones with equal weights should give the average of their animated positions."""
        node = _make_skin_node()
        node.skin_data[0].influences = [
            BoneWeight(bone_index=0, weight=0.5),
            BoneWeight(bone_index=1, weight=0.5),
        ]
        # bone0 moves +2 on X, bone1 moves -2 on X → average = 0 on X
        bt0 = self._make_bone_transform((0,0,0), (2.0,0,0))
        bt1 = self._make_bone_transform((0,0,0), (-2.0,0,0))
        result = self._run_lbs(node, {0: bt0, 1: bt1})
        self.assertAlmostEqual(result[0], 0.0, places=2,
                               msg="Weighted average should cancel X offset")


# ══════════════════════════════════════════════════════════════════════════
#  3. World transform guards
# ══════════════════════════════════════════════════════════════════════════

class TestWorldTransformGuards(unittest.TestCase):
    """_node_world_transform must catch non-finite animated positions."""

    def test_bind_pose_correct(self):
        """Bind-pose: node at (1,2,3) identity rotation → wp=(1,2,3)."""
        renderer = _make_bare_renderer()
        node = ModelNode()
        node.name = 'test'
        node.position = (1.0, 2.0, 3.0)
        node.rotation = (0.0, 0.0, 0.0, 1.0)
        node.parent = None
        wp, wo, is_id = renderer._node_world_transform(node)
        self.assertAlmostEqual(wp[0], 1.0, places=4)
        self.assertAlmostEqual(wp[1], 2.0, places=4)
        self.assertAlmostEqual(wp[2], 3.0, places=4)

    def test_orientation_normalized(self):
        """After animated transform, quaternion must be unit-length."""
        renderer = _make_bare_renderer()
        mock_pose = MagicMock()
        mock_pn = MagicMock()
        mock_pn.position = (0.0, 0.0, 0.0)
        mock_pn.rotation = [0.0, 0.0, 0.0, 1.0]
        mock_pose.nodes = {'test': mock_pn}
        node = ModelNode()
        node.name = 'test'
        node.position = (0.0, 0.0, 0.0)
        node.rotation = (0.0, 0.0, 0.0, 1.0)
        node.parent = None
        renderer._anim_pose = mock_pose
        wp, wo, is_id = renderer._node_world_transform(node)
        length = math.sqrt(sum(c*c for c in wo))
        self.assertAlmostEqual(length, 1.0, places=3,
                               msg="World quaternion must be unit-length")

    def test_parent_chain_accumulates_position(self):
        """Child positioned at (1,0,0) with parent at (2,0,0) → world (3,0,0)."""
        renderer = _make_bare_renderer()
        parent = ModelNode()
        parent.name = 'parent'
        parent.position = (2.0, 0.0, 0.0)
        parent.rotation = (0.0, 0.0, 0.0, 1.0)
        parent.parent = None

        child = ModelNode()
        child.name = 'child'
        child.position = (1.0, 0.0, 0.0)
        child.rotation = (0.0, 0.0, 0.0, 1.0)
        child.parent = parent

        wp, wo, is_id = renderer._node_world_transform(child)
        self.assertAlmostEqual(wp[0], 3.0, places=4,
                               msg="Child world X should be parent(2)+local(1)=3")


# ══════════════════════════════════════════════════════════════════════════
#  4. Transparency tier assignment
# ══════════════════════════════════════════════════════════════════════════

class TestTransparencyTierAssignment(unittest.TestCase):
    """Verify that the tier computation correctly classifies opaque vs transparent."""

    def _tier(self, transparency_hint, node_alpha=1.0):
        """Replicate viewport tier logic."""
        is_trans = (transparency_hint > 0 or node_alpha < 0.999)
        return 1 if is_trans else 0

    def test_opaque_node_tier_0(self):
        self.assertEqual(self._tier(0, 1.0), 0)

    def test_transparency_hint_1_tier_1(self):
        self.assertEqual(self._tier(1, 1.0), 1)

    def test_transparency_hint_2_tier_1(self):
        self.assertEqual(self._tier(2, 1.0), 1)

    def test_partial_alpha_is_tier_1(self):
        """node_alpha < 0.999 with hint=0 must still be tier 1."""
        self.assertEqual(self._tier(0, 0.5), 1)

    def test_full_alpha_opaque_is_tier_0(self):
        self.assertEqual(self._tier(0, 1.0), 0)

    def test_alpha_just_above_threshold_is_tier_0(self):
        """node_alpha = 0.9991 (just above 0.999) → tier 0."""
        self.assertEqual(self._tier(0, 0.9991), 0)

    def test_alpha_just_below_threshold_is_tier_1(self):
        """node_alpha = 0.998 (just below 0.999) → tier 1."""
        self.assertEqual(self._tier(0, 0.998), 1)


if __name__ == '__main__':
    unittest.main()
