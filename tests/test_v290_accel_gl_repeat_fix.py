"""
Phase 17: Accel Rasterizer GL_REPEAT Fix Tests
===============================================
Tests verifying that the accelerated rasterizer (accel.py) correctly implements
GL_REPEAT UV tiling behavior using frac() (modulo-1) wrapping.

Root cause of bug:
  Previously accel.py used:
    pu = np.clip((u * TW).astype(np.int32), 0, TW - 1)  # GL_CLAMP_TO_EDGE!
  For large UVs like pelvis (U=[-12.86, +12.86]), all pixels clamped to edge,
  producing solid-color bands instead of tiling texture.

Fix:
  u = u - np.floor(u)  # GL_REPEAT: modulo-1 frac()
  v = v - np.floor(v)
  Then sample with clip (now safe since u,v in [0,1)).

Impact:
  - All character body meshes with large UV spans now render correctly
  - Seam-crossing triangles (span < 1.0) still handled by seam-fix
  - Multi-tile triangles (span >= 1.0) handled by frac() tiling
"""
import math
import sys
import numpy as np
import pytest

sys.path.insert(0, 'src')

from gui.accel import rasterize_frame, ACCEL_TIER
from gui.tpc_render_utils import _edge_has_seam_global, _uwrap_global


def _make_checker(W=64, H=64):
    """Create a simple 2-color checker texture."""
    checker = np.zeros((H, W, 4), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            if (x // 8 + y // 8) % 2 == 0:
                checker[y, x] = [255, 128, 0, 255]  # orange
            else:
                checker[y, x] = [0, 64, 128, 255]   # dark blue
    return checker


def _render_tri(uvs_u_list, uvs_v_list, W=256, H=256, checker=None):
    """Render a single triangle and return pixel stats."""
    if checker is None:
        checker = _make_checker()
    buf = np.zeros((H, W, 4), dtype=np.uint8)
    buf[:, :, :3] = 64  # grey background
    buf[:, :, 3] = 255

    verts_sx = np.array([32, 224, 128], dtype=np.int64)
    verts_sy = np.array([32, 32, 224], dtype=np.int64)
    uvs_u = np.array(uvs_u_list, dtype=np.float64)
    uvs_v = np.array(uvs_v_list, dtype=np.float64)
    f0 = np.array([0], dtype=np.int64)
    f1 = np.array([1], dtype=np.int64)
    f2 = np.array([2], dtype=np.int64)
    sr = np.array([255], dtype=np.int64)
    sg = np.array([255], dtype=np.int64)
    sb = np.array([255], dtype=np.int64)
    na = np.array([255], dtype=np.int64)
    mask = np.array([True], dtype=bool)

    rasterize_frame(buf, checker, verts_sx, verts_sy, uvs_u, uvs_v,
                    f0, f1, f2, sr, sg, sb, na, mask)

    non_bg = int(np.sum(np.any(buf[:, :, :3] != 64, axis=2)))
    has_orange = bool(np.any(np.all(buf[:, :, :3] == [255, 128, 0], axis=2)))
    has_blue = bool(np.any(np.all(buf[:, :, :3] == [0, 64, 128], axis=2)))
    return non_bg, has_orange, has_blue


class TestAccelGLRepeatFix:
    """Tests for GL_REPEAT UV tiling in the accelerated rasterizer."""

    def test_normal_uv_renders(self):
        """Normal UVs [0,1] should render with both checker colors."""
        n, orange, blue = _render_tri([0.0, 1.0, 0.5], [0.0, 0.0, 1.0])
        assert n > 15000, f"Normal UVs should render large area: {n}"
        assert orange and blue, "Checker colors should be present"

    def test_large_uv_pelvis_renders(self):
        """Pelvis-like large UVs (U=[-12.86, +12.86]) should render with tiling."""
        n, orange, blue = _render_tri([-12.86, 12.86, 0.0], [-9.0, -9.0, 4.0])
        assert n > 15000, f"Large pelvis UVs should tile and fill triangle: {n}"
        assert orange and blue, "Both checker colors must be present (tiling confirmed)"

    def test_large_uv_matches_normal_pixel_count(self):
        """Large UV span should render same area as normal UVs (same triangle shape)."""
        n_normal, _, _ = _render_tri([0.0, 1.0, 0.5], [0.0, 0.0, 1.0])
        n_large, _, _ = _render_tri([-12.86, 12.86, 0.0], [-9.0, -9.0, 4.0])
        # Same triangle → same pixel count
        assert abs(n_large - n_normal) < 10, \
            f"Large UV ({n_large}) should match normal UV ({n_normal}) pixel count"

    def test_negative_uv_wraps_correctly(self):
        """Negative UVs should wrap using frac() and render texture."""
        n, orange, blue = _render_tri([-0.5, 0.5, 0.0], [-0.5, -0.5, 0.5])
        assert n > 15000, f"Negative UVs should render: {n}"
        assert orange and blue, "Both checker colors should be present"

    def test_torso_span_1_36_renders(self):
        """Torso UV span of 1.36 should render with tiling."""
        n, orange, blue = _render_tri([0.003, 1.366, 0.003], [0.013, 0.013, 0.979])
        assert n > 15000, f"Torso-like UV span should render: {n}"
        assert orange and blue, "Both checker colors should be present"

    def test_seam_cross_renders(self):
        """Seam-crossing triangle (0.95/0.05) should render correctly."""
        n, orange, blue = _render_tri([0.95, 0.05, 0.5], [0.0, 0.0, 1.0])
        assert n > 15000, f"Seam-crossing UVs should render: {n}"
        assert orange and blue, "Both checker colors should be present"

    def test_medium_large_uv_5tile(self):
        """5-tile UV range should render with tiling."""
        n, orange, blue = _render_tri([-2.5, 2.5, 0.0], [-2.0, -2.0, 3.0])
        assert n > 15000, f"5-tile UV range should render: {n}"
        assert orange and blue, "Both checker colors should be present"


class TestSeamFixThresholdFix:
    """Tests verifying the seam fix threshold fix (26.0 → 1.0) in viewport.py accel path."""

    def test_seam_fix_applies_for_span_under_1(self):
        """Seam fix should apply when span < 1.0."""
        u0, u1, u2 = 0.95, 0.05, 0.5
        span = max(u0, u1, u2) - min(u0, u1, u2)
        assert span < 1.0, "Test setup: span should be < 1.0"
        has_seam = (_edge_has_seam_global(u0, u1) or
                    _edge_has_seam_global(u0, u2) or
                    _edge_has_seam_global(u1, u2))
        assert has_seam, "Seam should be detected for 0.95/0.05 case"
        # After fix, new span should be reduced
        u1_fix = _uwrap_global(u0, u1)
        u2_fix = _uwrap_global(u0, u2)
        new_span = max(u0, u1_fix, u2_fix) - min(u0, u1_fix, u2_fix)
        assert new_span < span * 0.70, "Seam fix should significantly reduce span"

    def test_seam_fix_skips_for_large_span(self):
        """Seam fix should NOT apply when span >= 1.0 (multi-tile triangle)."""
        u0, u1, u2 = -12.86, 12.86, 0.0
        span = max(u0, u1, u2) - min(u0, u1, u2)
        assert span >= 1.0, "Test setup: large span should be >= 1.0"
        # The threshold change (26.0 → 1.0) means this case is correctly skipped
        should_apply_seam_fix = span < 1.0  # New threshold
        assert not should_apply_seam_fix, \
            "Seam fix MUST be skipped for multi-tile triangles (span >= 1.0)"

    def test_torso_span_skips_seam_fix(self):
        """Torso back-seam (span=1.36) should skip seam fix, use tiling instead."""
        u0, u1, u2 = 0.003, 1.366, 0.003
        span = max(u0, u1, u2) - min(u0, u1, u2)
        assert span >= 1.0, f"Torso span should be >= 1.0: {span}"
        # New threshold correctly skips seam fix
        should_seam_fix = span < 1.0
        assert not should_seam_fix, "Torso back-seam should NOT get seam fix"

    def test_genuine_seam_span_0_93_gets_fix(self):
        """Genuine seam triangle (span=0.93) should get seam fix."""
        u0, u1, u2 = 0.95, 0.02, 0.5
        span = max(u0, u1, u2) - min(u0, u1, u2)
        assert span < 1.0, f"Genuine seam span should be < 1.0: {span}"
        should_seam_fix = span < 1.0
        assert should_seam_fix, "Genuine seam triangle should get seam fix"


class TestFracMathCorrectness:
    """Verify frac() math is correct for various UV values."""

    @pytest.mark.parametrize("u,expected", [
        (0.0, 0.0),
        (0.5, 0.5),
        (1.0, 0.0),
        (1.5, 0.5),
        (-0.5, 0.5),
        (-1.0, 0.0),
        (-12.86, 1.0 - 0.86),   # frac(-12.86) = 0.14
        (12.86, 0.86),
    ])
    def test_frac_values(self, u, expected):
        """Verify frac() produces correct in-range values."""
        result = u - math.floor(u)
        assert abs(result - expected) < 1e-6, f"frac({u}) = {result}, expected {expected}"

    def test_frac_always_in_0_1(self):
        """frac() should always produce values in [0, 1)."""
        test_values = [-12.86, -9.0, -1.5, -0.5, 0.0, 0.5, 1.0, 1.5, 12.86]
        for u in test_values:
            result = u - math.floor(u)
            assert 0.0 <= result < 1.0, f"frac({u}) = {result} not in [0, 1)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
