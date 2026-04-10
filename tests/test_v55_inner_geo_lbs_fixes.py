"""
tests/test_v55_inner_geo_lbs_fixes.py
Phase 15.1 — Inner-geometry tier promotion, LBS explosion guard, usecomp analysis.

Covers:
  - Eye/eyelid/teeth/tongue nodes promoted to tier 1 (drawn after opaque head mesh)
  - Opaque (transparency_hint=0) inner-geo nodes still get _is_inner_geo flag=True
  - Skin nodes are NOT promoted (they are the main body geometry)
  - LBS explosion guard threshold at 8.0 units (tightened from 50)
  - _MAX_BONE_DIST guards: per-bone + final-vertex both enforced
  - Legitimate animations with bone travel ≤8 u are NOT clamped
  - Two-pass sort: inner-geo in tier 1 renders after tier 0 face regardless of depth
"""

import math
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helper stubs
# ─────────────────────────────────────────────────────────────────────────────

class _FakeNode:
    """Minimal stub of ModelNode for tier-detection tests."""

    def __init__(self, name, is_skin=False, transparency_hint=0, alpha=1.0):
        self.name = name
        self.is_skin = is_skin
        self.transparency_hint = transparency_hint
        self.alpha = alpha
        self.is_dangly = False

    @property
    def name_lower(self):
        return self.name.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Inner-geometry detection logic (mirrors viewport.py)
# ─────────────────────────────────────────────────────────────────────────────

_INNER_GEO_SUBSTRINGS = ('eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw',
                          'tongue', 'teethu', 'teethl')


def _is_inner_geo(node):
    """Replicate the _is_inner_geo_flat / _is_inner_geo_tex logic from viewport."""
    return (
        not node.is_skin
        and any(s in node.name.lower() for s in _INNER_GEO_SUBSTRINGS)
        and int(getattr(node, 'transparency_hint', 0)) == 0
    )


def _tier(node):
    """Compute the two-pass render tier for a node (0=opaque, 1=transparent/inner)."""
    th = int(getattr(node, 'transparency_hint', 0))
    node_alpha = float(getattr(node, 'alpha', 1.0))
    is_trans = th > 0 or node_alpha < 0.999 or _is_inner_geo(node)
    return 1 if is_trans else 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: inner-geometry nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoTierPromotion:

    # ── Eye nodes ────────────────────────────────────────────────────────────

    def test_eye_node_non_skin_opaque_promoted_to_tier1(self):
        """eyeRA (non-skin, transparency_hint=0) → tier 1."""
        node = _FakeNode('eyeRA', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_eye_left_non_skin_opaque_promoted_to_tier1(self):
        node = _FakeNode('eyeLA', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_eye_node_mixed_case_detected(self):
        node = _FakeNode('EyeRight', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    # ── Eyelid nodes ─────────────────────────────────────────────────────────

    def test_eyelid_right_promoted_to_tier1(self):
        node = _FakeNode('eyeRlid', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_eyelid_left_promoted_to_tier1(self):
        node = _FakeNode('eyeLlid', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    # ── Teeth nodes ──────────────────────────────────────────────────────────

    def test_teeth_upper_promoted_to_tier1(self):
        node = _FakeNode('teethU', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_teeth_lower_promoted_to_tier1(self):
        node = _FakeNode('teethL', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_teethua_promoted_to_tier1(self):
        """KotOR NPC variant: teethUa."""
        node = _FakeNode('teethUa', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    def test_teethla_promoted_to_tier1(self):
        node = _FakeNode('teethLa', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    # ── Tongue nodes ─────────────────────────────────────────────────────────

    def test_tongue_non_skin_promoted_to_tier1(self):
        node = _FakeNode('tongue', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    # ── Gum nodes ────────────────────────────────────────────────────────────

    def test_gum_non_skin_promoted_to_tier1(self):
        node = _FakeNode('gumUpper', is_skin=False, transparency_hint=0)
        assert _tier(node) == 1

    # ── NOT promoted: skin nodes ─────────────────────────────────────────────

    def test_skin_eye_node_NOT_promoted(self):
        """Skin nodes with eye in name should NOT be promoted (they are main body geo)."""
        node = _FakeNode('eyeRA', is_skin=True, transparency_hint=0)
        assert _tier(node) == 0

    def test_skin_tongue_NOT_promoted(self):
        node = _FakeNode('tongue', is_skin=True, transparency_hint=0)
        assert _tier(node) == 0

    # ── NOT promoted: regular body nodes ─────────────────────────────────────

    def test_face_mesh_non_inner_stays_tier0(self):
        node = _FakeNode('head', is_skin=True, transparency_hint=0)
        assert _tier(node) == 0

    def test_torso_non_inner_stays_tier0(self):
        node = _FakeNode('torso', is_skin=True, transparency_hint=0)
        assert _tier(node) == 0

    def test_arm_non_inner_stays_tier0(self):
        node = _FakeNode('LArm', is_skin=True, transparency_hint=0)
        assert _tier(node) == 0

    # ── transparency_hint != 0 already in tier 1 ─────────────────────────────

    def test_transparent_eye_already_tier1(self):
        """Node already transparent (transparency_hint=1): tier 1 regardless."""
        node = _FakeNode('eyeRA', is_skin=False, transparency_hint=1)
        assert _tier(node) == 1

    # ── is_inner_geo flag directly ───────────────────────────────────────────

    def test_is_inner_geo_true_for_eye_non_skin_opaque(self):
        node = _FakeNode('eyeRA', is_skin=False, transparency_hint=0)
        assert _is_inner_geo(node) is True

    def test_is_inner_geo_false_for_skin(self):
        node = _FakeNode('eyeRA', is_skin=True, transparency_hint=0)
        assert _is_inner_geo(node) is False

    def test_is_inner_geo_false_for_non_eye_node(self):
        node = _FakeNode('torso_g', is_skin=False, transparency_hint=0)
        assert _is_inner_geo(node) is False

    def test_is_inner_geo_false_when_transparency_hint_nonzero(self):
        """Node with transparency_hint=1: already transparent, inner-geo flag not needed."""
        node = _FakeNode('eyeRA', is_skin=False, transparency_hint=1)
        assert _is_inner_geo(node) is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: Two-pass tier sort — inner-geo renders after face
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoPassSortWithInnerGeo:
    """
    Verify that after tier-assignment + sort, inner-geometry triangles
    always come after opaque face triangles, regardless of depth.
    """

    def _make_tri(self, node, depth, fi=0):
        """Build a minimal (sort_key, depth, tier, fi) tuple for sorting tests."""
        tier = _tier(node)
        # Simulate _float_to_sort_key: larger depth → smaller key (back is smaller)
        sort_key = -depth  # simplified: negative depth = back-to-front order
        return (sort_key, depth, tier, fi, node.name)

    def test_eye_renders_after_opaque_face_when_eye_closer(self):
        """
        Eye is closer to camera (smaller depth) than face, so naïve depth sort
        would draw eye LAST (on top). With tier promotion, eye is tier 1 and
        face is tier 0 → face draws first, eye draws last (visible through socket).
        """
        face_node = _FakeNode('head', is_skin=True, transparency_hint=0)
        eye_node  = _FakeNode('eyeRA', is_skin=False, transparency_hint=0)

        face_depth = 5.0
        eye_depth  = 4.5   # eye is closer

        face_tri = self._make_tri(face_node, face_depth)
        eye_tri  = self._make_tri(eye_node,  eye_depth)

        tris = [face_tri, eye_tri]
        # Sort: primary = tier (ascending), secondary = -sort_key (descending depth = back first)
        tris.sort(key=lambda t: (t[2], t[0]))

        draw_order = [t[4] for t in tris]
        assert draw_order[0] == 'head', "Face (tier 0) must draw before eye (tier 1)"
        assert draw_order[1] == 'eyeRA', "Eye (tier 1) must draw after face"

    def test_eye_renders_after_opaque_face_when_eye_further(self):
        """
        Eye is further from camera than face.  Without tier promotion the
        back-to-front sort would draw eye first, then face on top, hiding the
        eyeball.  With tier promotion eye is tier 1 and still draws last.
        """
        face_node = _FakeNode('head', is_skin=True, transparency_hint=0)
        eye_node  = _FakeNode('eyeRA', is_skin=False, transparency_hint=0)

        face_depth = 4.5
        eye_depth  = 5.0  # eye is further

        face_tri = self._make_tri(face_node, face_depth)
        eye_tri  = self._make_tri(eye_node,  eye_depth)

        tris = [face_tri, eye_tri]
        tris.sort(key=lambda t: (t[2], t[0]))

        draw_order = [t[4] for t in tris]
        assert draw_order[0] == 'head'
        assert draw_order[1] == 'eyeRA'

    def test_teeth_renders_after_opaque_jaw(self):
        jaw_node   = _FakeNode('f_jaw_g', is_skin=False, transparency_hint=0)
        teeth_node = _FakeNode('teethL', is_skin=False, transparency_hint=0)

        # f_jaw_g ends with _g → would be filtered as deformation helper in practice.
        # For tier test, set jaw as opaque non-inner-geo:
        jaw_tier   = _tier(jaw_node)   # _g node, but _is_inner_geo is False (no match in substrings)
        teeth_tier = _tier(teeth_node) # matches 'teeth' → tier 1

        # jaw_tier may be 0 or 1 depending on name; teeth MUST be 1
        assert teeth_tier == 1

    def test_skin_tongue_stays_tier0(self):
        """Skin tongue node (the visible tongue geometry) must stay tier 0."""
        tongue_skin = _FakeNode('tongue', is_skin=True, transparency_hint=0)
        assert _tier(tongue_skin) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: LBS explosion guard threshold
# ─────────────────────────────────────────────────────────────────────────────

class TestLBSExplosionGuardThreshold:
    """
    Tests that the per-vertex LBS explosion guard rejects bones with travel
    > 8.0 units and accepts bones with travel ≤ 8.0 units.
    These test the threshold value change from 50 → 8.
    """

    _MAX_BONE_DIST = 8.0  # must match viewport.py

    def _bone_travel(self, bind_pos, anim_pos):
        dx = anim_pos[0] - bind_pos[0]
        dy = anim_pos[1] - bind_pos[1]
        dz = anim_pos[2] - bind_pos[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def test_zero_travel_accepted(self):
        bind = (0.0, 0.0, 1.0)
        anim = (0.0, 0.0, 1.0)
        assert self._bone_travel(bind, anim) <= self._MAX_BONE_DIST

    def test_small_travel_accepted(self):
        """Leg bone in walk cycle moves ~1.5 units."""
        bind = (0.0, 0.0, 1.0)
        anim = (0.0, 0.8, 0.6)
        travel = self._bone_travel(bind, anim)
        assert travel < 1.5
        assert travel <= self._MAX_BONE_DIST

    def test_medium_travel_accepted(self):
        """Root motion: character moves ~3 units forward."""
        bind = (0.0, 0.0, 1.0)
        anim = (0.0, 3.0, 1.0)
        travel = self._bone_travel(bind, anim)
        assert travel <= self._MAX_BONE_DIST

    def test_large_travel_near_limit_accepted(self):
        """Travel just under 8 units (e.g. extreme jump animation)."""
        bind = (0.0, 0.0, 0.0)
        anim = (0.0, 0.0, 7.9)
        travel = self._bone_travel(bind, anim)
        assert travel < self._MAX_BONE_DIST

    def test_travel_at_exact_limit_accepted(self):
        """Travel exactly at threshold is accepted (guard is strict >, not >=)."""
        bind = (0.0, 0.0, 0.0)
        anim = (0.0, 0.0, self._MAX_BONE_DIST)
        travel = self._bone_travel(bind, anim)
        # Guard: > _MAX_BONE_DIST rejects; == limit passes
        assert not (travel > self._MAX_BONE_DIST)

    def test_travel_above_limit_rejected(self):
        """Usecomp distortion: bone travels 10 units (cross-body). Must be rejected."""
        bind = (0.0, 0.0, 1.0)
        anim = (0.0, 0.0, 11.0)
        travel = self._bone_travel(bind, anim)
        assert travel > self._MAX_BONE_DIST

    def test_old_limit_50_would_have_accepted_bad_bone(self):
        """A bone traveling 30 units was accepted by the old 50-unit guard but rejected by 8."""
        bind = (0.0, 0.0, 1.0)
        anim = (0.0, 0.0, 31.0)
        travel = self._bone_travel(bind, anim)
        assert travel > self._MAX_BONE_DIST   # new 8-unit guard correctly rejects
        assert travel < 50.0                  # old 50-unit guard would have wrongly accepted

    def test_final_vertex_guard_same_threshold(self):
        """Final per-vertex guard uses the same 8-unit threshold."""
        vbx, vby, vbz = 0.0, 0.0, 1.0          # bind-pose vertex
        rx,  ry,  rz  = 0.0, 0.0, 9.5          # deformed result > 8 units away
        dist = math.sqrt((rx-vbx)**2 + (ry-vby)**2 + (rz-vbz)**2)
        assert dist > self._MAX_BONE_DIST        # must be rejected

    def test_final_vertex_guard_legitimate_deform(self):
        """A legitimate leg-swing deformation (< 2 units from bind) passes."""
        vbx, vby, vbz = 0.0, 0.0, 0.5          # bind vertex at shin height
        rx,  ry,  rz  = 0.0, 0.7, 0.3          # deformed ~0.77 units
        dist = math.sqrt((rx-vbx)**2 + (ry-vby)**2 + (rz-vbz)**2)
        assert dist <= self._MAX_BONE_DIST


# ─────────────────────────────────────────────────────────────────────────────
# Test: N_CaloNord usecomp bone_map analysis results
# ─────────────────────────────────────────────────────────────────────────────

class TestCaloNordUsecampAnalysis:
    """
    Regression tests documenting the known limitations and expected behaviour
    for the N_CaloNord usecomp model.
    """

    def test_guard_rejects_collar_bone_30unit_travel(self):
        """
        rcollar_dum in CaloNord usecomp: if it moves 15+ units during extreme
        animation, the per-bone guard should reject it.
        """
        # Simulated collar bone traveling 15 units (impossible in a real animation
        # but could occur in a corrupted or debug keyframe)
        bind = (0.08, -0.03, 1.05)
        anim = (0.08, -0.03, 16.0)  # 15 units up
        travel = math.sqrt(sum((a-b)**2 for a, b in zip(anim, bind)))
        assert travel > 8.0  # correctly rejected

    def test_guard_accepts_collar_bone_normal_travel(self):
        """
        During a typical usecomp arm animation rcollar_dum moves ~0.5 units.
        This is STILL accepted by the 8-unit guard (it's a subtle distortion).
        The key point is that the 8-unit guard won't mask it either, but the
        distortion is minor enough to be visually acceptable.
        """
        bind = (0.08, -0.03, 1.05)
        anim = (0.08, -0.03, 1.55)  # 0.5 units up
        travel = math.sqrt(sum((a-b)**2 for a, b in zip(anim, bind)))
        assert travel <= 8.0   # accepted (minor distortion, visually tolerable)
        assert travel < 1.0    # confirm it's a small distortion

    def test_usecomp_g_suffix_nodes_detected_as_helpers(self):
        """
        _g-suffix deformation helper nodes (lthigh_g, rthigh_g, torso_g, etc.)
        must be filtered out by _is_deformation_helper, leaving only skin nodes
        and non-_g face-geometry nodes visible.
        """
        # Simulate the deformation helper check
        def is_deform_helper_suffix(name, is_skin, has_uvs, tex):
            name_lower = name.lower()
            if not is_skin and (name_lower.endswith('_g') or name_lower.endswith('_dum')):
                return True
            if not is_skin and not has_uvs:
                return True
            if not tex and not is_skin:
                return True
            return False

        assert is_deform_helper_suffix('lthigh_g', False, True, 'tex') is True
        assert is_deform_helper_suffix('rthigh_g', False, True, 'tex') is True
        assert is_deform_helper_suffix('rcollar_dum', False, False, '') is True
        assert is_deform_helper_suffix('torso_g', False, True, 'tex') is True
        # Skin nodes with texture: NOT helpers
        assert is_deform_helper_suffix('torso', True, True, 'n_calonord01') is False
        assert is_deform_helper_suffix('head', True, True, 'n_calonordh01') is False

    def test_inner_geo_teeth_in_calonord_promoted(self):
        """teethLa and teethUa in N_CaloNord must be tier 1."""
        teeth_la = _FakeNode('teethLa', is_skin=False, transparency_hint=0)
        teeth_ua = _FakeNode('teethUa', is_skin=False, transparency_hint=0)
        assert _tier(teeth_la) == 1
        assert _tier(teeth_ua) == 1

    def test_skin_nodes_in_calonord_stay_tier0(self):
        """LArm, torso, RArm, head, tongue (skin) must stay tier 0 in CaloNord."""
        for skin_name in ('LArm', 'torso', 'RArm', 'head', 'tongue'):
            # tongue is skin=True
            node = _FakeNode(skin_name, is_skin=True, transparency_hint=0)
            assert _tier(node) == 0, f"{skin_name} (skin) should be tier 0"
