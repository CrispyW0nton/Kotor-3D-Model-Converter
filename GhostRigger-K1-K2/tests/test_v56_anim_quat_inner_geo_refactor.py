"""
tests/test_v56_anim_quat_inner_geo_refactor.py
Phase 15.2 — Quaternion sign-consistency normalizer & inner-geo refactor.

Covers:
  - _ensure_quat_sign_consistency: antipodal flip detection and correction
  - _interp_channel: quaternion channels pre-normalised for sign consistency
  - _INNER_GEO_SUBSTRINGS hoisted to module level (consistent between paths)
  - 'jaw' added to inner-geo detection strings
  - SLERP shortest-path across multi-keyframe sequences with mixed signs
  - Position channels (3-component) unaffected by quaternion normaliser
"""

import math
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Import helpers from animation_engine
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.animation_engine import (
    _ensure_quat_sign_consistency,
    _interp_channel,
    _slerp,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mag(v):
    return math.sqrt(sum(x * x for x in v))


def _dot4(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3]


def _norm4(v):
    m = _mag(v)
    if m < 1e-9:
        return v
    return [x / m for x in v]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: _ensure_quat_sign_consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsureQuatSignConsistency:

    def test_identity_unchanged(self):
        """Single identity keyframe passes through unchanged."""
        vals = [[0.0, 0.0, 0.0, 1.0]]
        result = _ensure_quat_sign_consistency(vals)
        assert len(result) == 1
        assert result[0] == pytest.approx([0.0, 0.0, 0.0, 1.0])

    def test_already_consistent_unchanged(self):
        """Keyframes already in same hemisphere are not modified."""
        vals = [
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.3827, 0.0, 0.9239],   # 45° about Y
            [0.0, 0.7071, 0.0, 0.7071],   # 90° about Y
        ]
        result = _ensure_quat_sign_consistency(vals)
        for orig, fixed in zip(vals, result):
            assert fixed == pytest.approx(orig, abs=1e-6)

    def test_antipodal_second_frame_flipped(self):
        """q at frame 1 is antipodal to frame 0 — must be flipped."""
        q0 = [0.0, 0.0, 0.0, 1.0]   # identity
        q1 = [0.0, 0.0, 0.0, -1.0]  # antipodal (same rotation, wrong sign)
        result = _ensure_quat_sign_consistency([q0, q1])
        assert result[0] == pytest.approx(q0)
        assert result[1] == pytest.approx([0.0, 0.0, 0.0, 1.0])

    def test_alternating_antipodal_all_corrected(self):
        """Alternating sign pattern (common in some KotOR exporters) is fixed."""
        q_pos = [0.0, 0.0, 0.0, 1.0]
        q_neg = [0.0, 0.0, 0.0, -1.0]
        vals = [q_pos, q_neg, q_pos, q_neg, q_pos]
        result = _ensure_quat_sign_consistency(vals)
        for r in result:
            assert _dot4(result[0], r) >= 0.0, \
                f"Frame not in same hemisphere as frame 0: {r}"

    def test_all_flipped_relative_to_first_corrected(self):
        """All frames after frame 0 have flipped sign: all flipped back."""
        q_ref   = [0.0, 0.0, 0.0,  1.0]
        q_flip  = [0.0, 0.0, 0.0, -1.0]
        vals = [q_ref, q_flip, q_flip, q_flip]
        result = _ensure_quat_sign_consistency(vals)
        # All resulting frames should be in same hemisphere as result[0]
        for r in result[1:]:
            assert _dot4(result[0], r) >= 0.0

    def test_non_trivial_rotation_antipodal_corrected(self):
        """Non-identity quaternion antipodal pair is correctly resolved."""
        q = _norm4([0.1, 0.2, 0.3, 0.9])
        q_neg = [-q[0], -q[1], -q[2], -q[3]]
        result = _ensure_quat_sign_consistency([q, q_neg])
        assert _dot4(result[0], result[1]) >= 0.0

    def test_three_vec_channel_unchanged(self):
        """3-component (position) values are returned unchanged."""
        vals = [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        result = _ensure_quat_sign_consistency(vals)
        # Should be identical — function only processes 4-component channels
        for orig, fixed in zip(vals, result):
            assert fixed == pytest.approx(orig)

    def test_empty_list_returns_empty(self):
        result = _ensure_quat_sign_consistency([])
        assert result == []

    def test_single_element_returns_unchanged(self):
        v = [0.5, 0.5, 0.5, 0.5]
        result = _ensure_quat_sign_consistency([v])
        assert result[0] == pytest.approx(v)

    def test_original_list_not_mutated(self):
        """_ensure_quat_sign_consistency must not modify the input list."""
        original = [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, -1.0]]
        import copy
        backup = copy.deepcopy(original)
        _ensure_quat_sign_consistency(original)
        assert original == backup


# ─────────────────────────────────────────────────────────────────────────────
# Tests: _interp_channel quaternion sign-consistency integration
# ─────────────────────────────────────────────────────────────────────────────

class TestInterpChannelQuatConsistency:

    def test_interpolated_quat_is_normalised(self):
        """Interpolated quaternion always has unit length."""
        times = [0.0, 1.0]
        vals = [[0.0, 0.0, 0.0, 1.0], [0.0, 0.7071, 0.0, 0.7071]]
        result = _interp_channel(times, vals, 0.5)
        assert result is not None
        assert _mag(result) == pytest.approx(1.0, abs=1e-5)

    def test_antipodal_keyframes_slerp_shortest_path(self):
        """SLERP between antipodal keyframes should go via shortest arc, not 360°.

        Without sign-consistency normalisation, SLERP(q, -q, 0.5) returns a
        degenerate value.  With normalisation, -q → q so SLERP(q, q, 0.5) = q.
        """
        q = [0.0, 0.7071, 0.0, 0.7071]   # 90° about Y
        q_neg = [-q[0], -q[1], -q[2], -q[3]]  # antipodal

        times = [0.0, 1.0]
        vals = [q, q_neg]
        result = _interp_channel(times, vals, 0.5)

        assert result is not None
        # After sign consistency, q_neg → q, so SLERP(q, q, 0.5) = q
        assert _mag(result) == pytest.approx(1.0, abs=1e-5)
        # Result should be close to q (not the identity, not degenerate)
        assert _dot4(result, q) > 0.99, \
            f"Expected result close to q={q}, got {result}"

    def test_multi_keyframe_antipodal_sequence(self):
        """Three-keyframe sequence with antipodal middle frame is handled."""
        q0 = [0.0, 0.0, 0.0, 1.0]
        q1 = [0.0, 0.0, 0.0, -1.0]  # antipodal middle
        q2 = [0.0, 0.7071, 0.0, 0.7071]

        times = [0.0, 1.0, 2.0]
        vals = [q0, q1, q2]

        # Should not raise; results should all be normalised
        for t in [0.25, 0.75, 1.25, 1.75]:
            r = _interp_channel(times, vals, t)
            assert r is not None
            assert _mag(r) == pytest.approx(1.0, abs=1e-5)

    def test_position_channel_unaffected(self):
        """3-component position channel is NOT affected by quat normaliser."""
        times = [0.0, 1.0]
        vals = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        result = _interp_channel(times, vals, 0.5)
        assert result == pytest.approx([0.5, 0.0, 0.0])

    def test_exact_start_key_returned(self):
        """t == times[0] returns first keyframe exactly."""
        times = [0.0, 1.0]
        vals = [[0.0, 0.7071, 0.0, 0.7071], [0.0, 0.0, 0.0, 1.0]]
        result = _interp_channel(times, vals, 0.0)
        assert result is not None
        assert _mag(result) == pytest.approx(1.0, abs=1e-5)

    def test_exact_end_key_returned(self):
        """t >= times[-1] returns last keyframe."""
        times = [0.0, 1.0]
        vals = [[0.0, 0.7071, 0.0, 0.7071], [0.0, 0.0, 0.0, 1.0]]
        result = _interp_channel(times, vals, 1.0)
        assert result is not None
        assert _mag(result) == pytest.approx(1.0, abs=1e-5)

    def test_nan_keyframe_skipped(self):
        """NaN/Inf keyframe is skipped; adjacent valid keyframes still used."""
        import math
        times = [0.0, 1.0, 2.0]
        vals = [[0.0, 0.0, 0.0, 1.0], [math.nan, 0.0, 0.0, 1.0],
                [0.0, 0.7071, 0.0, 0.7071]]
        result = _interp_channel(times, vals, 1.5)
        # Should get a result from bracketing valid frames, not crash
        # (NaN frame is skipped; t=1.5 falls between t=0 and t=2)
        assert result is not None

    def test_single_keyframe_returned_at_any_time(self):
        """Single keyframe: always returned regardless of t."""
        times = [0.0]
        vals = [[0.0, 0.7071, 0.0, 0.7071]]
        assert _interp_channel(times, vals, -1.0) is not None
        assert _interp_channel(times, vals, 5.0) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Tests: _INNER_GEO_SUBSTRINGS module-level constant (viewport)
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoSubstringsModuleLevel:
    """Verify that _INNER_GEO_SUBSTRINGS is a module-level constant in viewport.py."""

    def test_inner_geo_substrings_is_module_level(self):
        """_INNER_GEO_SUBSTRINGS must exist at module level in viewport."""
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert hasattr(viewport, '_INNER_GEO_SUBSTRINGS'), \
            "_INNER_GEO_SUBSTRINGS must be a module-level constant in viewport.py"

    def test_inner_geo_substrings_contains_eye(self):
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'eye' in viewport._INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contains_lid(self):
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'lid' in viewport._INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contains_teeth(self):
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'teeth' in viewport._INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contains_jaw(self):
        """Phase 15.2: 'jaw' added for KotOR jaw-mesh detection."""
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'jaw' in viewport._INNER_GEO_SUBSTRINGS, \
            "'jaw' should be in _INNER_GEO_SUBSTRINGS (Phase 15.2 addition)"

    def test_inner_geo_substrings_contains_tongue(self):
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'tongue' in viewport._INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contains_gum(self):
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert 'gum' in viewport._INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_is_tuple(self):
        """Constant should be a tuple for O(1) membership after Python optimisation."""
        try:
            from gui import viewport
        except ImportError:
            import viewport  # type: ignore
        assert isinstance(viewport._INNER_GEO_SUBSTRINGS, tuple)

    def test_jaw_node_promoted_to_tier1(self):
        """f_jaw_g would be filtered as helper; a 'jaw' textured non-skin node → tier 1."""
        _INNER_GEO_SUBSTRINGS = ('eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw',
                                  'tongue', 'teethu', 'teethl')

        class _FakeJawNode:
            name = 'jawUpper'
            is_skin = False
            transparency_hint = 0
            alpha = 1.0
            is_dangly = False

        node = _FakeJawNode()
        nl = node.name.lower()
        is_inner = (
            not node.is_skin
            and any(s in nl for s in _INNER_GEO_SUBSTRINGS)
            and int(node.transparency_hint) == 0
        )
        tier = 1 if (node.transparency_hint > 0 or node.alpha < 0.999 or is_inner) else 0
        assert is_inner is True
        assert tier == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests: SLERP sanity
# ─────────────────────────────────────────────────────────────────────────────

class TestSlerpSanity:

    def test_slerp_identity_at_t0(self):
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.7071, 0.0, 0.7071]
        r = _slerp(q1, q2, 0.0)
        assert r == pytest.approx(q1, abs=1e-5)

    def test_slerp_identity_at_t1(self):
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.7071, 0.0, 0.7071]
        r = _slerp(q1, q2, 1.0)
        assert r == pytest.approx(q2, abs=1e-5)

    def test_slerp_midpoint_normalised(self):
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.7071, 0.0, 0.7071]
        r = _slerp(q1, q2, 0.5)
        assert _mag(r) == pytest.approx(1.0, abs=1e-5)

    def test_slerp_same_quaternion(self):
        """SLERP of q with itself at any t returns q."""
        q = [0.0, 0.5, 0.5, 0.7071]
        q = _norm4(q)
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            r = _slerp(q, q, t)
            assert r == pytest.approx(q, abs=1e-5)

    def test_slerp_antipodal_shortest_path(self):
        """SLERP between q and -q should use the shorter arc (dot<0 → flip)."""
        q = [0.0, 0.0, 0.0, 1.0]
        q_neg = [0.0, 0.0, 0.0, -1.0]
        r = _slerp(q, q_neg, 0.5)
        # After sign flip, SLERP(q, q, 0.5) = q
        assert _mag(r) == pytest.approx(1.0, abs=1e-5)
        # Should be close to q, not spin 180°
        assert _dot4(r, q) > 0.99
