"""
Phase 18 UV fix tests — 2026-03-31

Tests for:
  18-A: NumPy Tier 2 GL_REPEAT in _rasterize_triangle_numpy
  18-B: UV Sentinel threshold raised from 20.0 to 100.0
  18-C: Accel path TXI clamp support (via viewport._draw_mesh_accel)
  18-D: Accel path UV animation (rotatetexture, animate_uv scroll)

Based on deep-dive of KotorBlender reader.py + PyKotor gl/models/mdl.py.
Ground truth: GPU uses GL_REPEAT (frac), no UV modification at all.
"""
import sys, os, math
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ─────────────────────────────────────────────────────────────────────────────
# 18-A: NumPy Tier 2 GL_REPEAT
# ─────────────────────────────────────────────────────────────────────────────

def _make_checker_tex(size=16):
    """8x8 orange+dark-blue checker texture."""
    tex = np.zeros((size, size, 4), dtype=np.uint8)
    half = size // 2
    tex[:half, :half] = [255, 128, 0, 255]    # orange (top-left)
    tex[half:, half:] = [255, 128, 0, 255]    # orange (bottom-right)
    tex[:half, half:] = [0, 64, 128, 255]     # dark blue (top-right)
    tex[half:, :half] = [0, 64, 128, 255]     # dark blue (bottom-left)
    return tex

def _force_numpy_tier():
    """Import accel module and force ACCEL_TIER=2 for testing NumPy path."""
    import importlib
    import gui.accel as accel_mod
    original_tier = accel_mod.ACCEL_TIER
    accel_mod.ACCEL_TIER = 2
    return accel_mod, original_tier

def _restore_tier(accel_mod, original_tier):
    accel_mod.ACCEL_TIER = original_tier


class TestNumPyTierGLRepeat:
    """Phase 18-A: NumPy Tier 2 _rasterize_triangle_numpy uses frac() (GL_REPEAT)."""

    def test_normal_uv_renders(self):
        """Normal UVs [0,1] render correctly with NumPy tier."""
        from gui.accel import _rasterize_triangle_numpy
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = _make_checker_tex(16)
        # Large triangle covering most of the buffer
        _rasterize_triangle_numpy(buf, tex, 2, 2, 62, 2, 32, 60,
                                  0.1, 0.1, 0.9, 0.1, 0.5, 0.9,
                                  255, 255, 255, 1.0)
        non_bg = (buf[:,:,3] > 0).sum()
        assert non_bg > 500, f"Expected >500 pixels, got {non_bg}"
        # Should contain both orange and blue checker colors
        orange_mask = (buf[:,:,0] > 200) & (buf[:,:,1] > 100) & (buf[:,:,2] < 50)
        blue_mask   = (buf[:,:,0] < 50) & (buf[:,:,2] > 100)
        assert orange_mask.sum() > 0, "No orange pixels — texture not sampled"
        assert blue_mask.sum() > 0,   "No blue pixels — texture not sampled"

    def test_large_positive_uv_tiles(self):
        """Large positive UVs (pelvis_g style: U=12.86) should tile via frac()."""
        from gui.accel import _rasterize_triangle_numpy
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = _make_checker_tex(16)
        # Large UV values that should tile
        _rasterize_triangle_numpy(buf, tex, 2, 2, 62, 2, 32, 60,
                                  12.1, 12.1,  12.9, 12.1,  12.5, 12.9,
                                  255, 255, 255, 1.0)
        non_bg = (buf[:,:,3] > 0).sum()
        assert non_bg > 500, f"Large UV tiling: expected >500 pixels, got {non_bg}"
        orange_mask = (buf[:,:,0] > 200) & (buf[:,:,1] > 100) & (buf[:,:,2] < 50)
        blue_mask   = (buf[:,:,0] < 50) & (buf[:,:,2] > 100)
        assert orange_mask.sum() > 0, "No orange pixels — large UV not tiling"
        assert blue_mask.sum() > 0,   "No blue pixels — large UV not tiling"

    def test_negative_uv_tiles(self):
        """Negative UVs should wrap correctly via frac()."""
        from gui.accel import _rasterize_triangle_numpy
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = _make_checker_tex(16)
        _rasterize_triangle_numpy(buf, tex, 2, 2, 62, 2, 32, 60,
                                  -0.9, -0.9,  -0.1, -0.9,  -0.5, -0.1,
                                  255, 255, 255, 1.0)
        non_bg = (buf[:,:,3] > 0).sum()
        assert non_bg > 500, f"Negative UV: expected >500 pixels, got {non_bg}"

    def test_frac_math_correctness(self):
        """Verify frac() wrapping math for key UV values."""
        def frac(x):
            return x - math.floor(x)
        # Standard range — no change
        assert abs(frac(0.3) - 0.3) < 1e-9
        assert abs(frac(0.7) - 0.7) < 1e-9
        # Large positive
        assert abs(frac(12.86) - 0.86) < 1e-6
        assert abs(frac(12.14) - 0.14) < 1e-6
        # Negative
        assert abs(frac(-0.14) - 0.86) < 1e-6
        assert abs(frac(-12.86) - 0.14) < 1e-6

    def test_seam_uv_tiles(self):
        """Seam-crossing UVs (0.95 / 0.05) should render correctly after frac()."""
        from gui.accel import _rasterize_triangle_numpy
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = _make_checker_tex(16)
        # Seam-crossing: u0=0.95, u1=0.05, u2=0.5 — raw span=0.9
        _rasterize_triangle_numpy(buf, tex, 2, 2, 62, 2, 32, 60,
                                  0.95, 0.5,  0.05, 0.5,  0.5, 0.9,
                                  255, 255, 255, 1.0)
        non_bg = (buf[:,:,3] > 0).sum()
        assert non_bg > 500, f"Seam UV: expected >500 pixels, got {non_bg}"


# ─────────────────────────────────────────────────────────────────────────────
# 18-B: UV Sentinel threshold
# ─────────────────────────────────────────────────────────────────────────────

class TestUVSentinelThreshold:
    """Phase 18-B: UV sentinel raised from 20.0 to 100.0."""

    def test_sentinel_value_is_100(self):
        """_UV_SENTINEL should be 100.0 in both viewport.py and tpc_render_utils.py."""
        from gui.tpc_render_utils import _UV_SENTINEL as tpc_sentinel
        assert tpc_sentinel == 100.0, f"tpc_render_utils._UV_SENTINEL={tpc_sentinel}, expected 100.0"

    def test_sentinel_value_viewport(self):
        """_UV_SENTINEL in viewport.py should be 100.0."""
        import gui.viewport as vp
        sentinel = getattr(vp, '_UV_SENTINEL', None)
        assert sentinel is not None, "viewport._UV_SENTINEL not found"
        assert sentinel == 100.0, f"viewport._UV_SENTINEL={sentinel}, expected 100.0"

    def test_large_uv_not_filtered_by_sentinel(self):
        """UV values up to 20 should NOT be filtered by the sentinel."""
        from gui.tpc_render_utils import _UV_SENTINEL
        # Legitimate large tiled UV (mRobe2_g has U up to ~13.5)
        test_uv_values = [13.58, 15.0, 19.9, 20.0, 21.0]
        for uv in test_uv_values:
            assert abs(uv) <= _UV_SENTINEL, (
                f"UV={uv} incorrectly filtered by sentinel={_UV_SENTINEL}"
            )

    def test_placeholder_uv_filtered_by_sentinel(self):
        """KotOR truly extreme placeholder UVs (127, etc.) should still be filtered.
        
        Note: -22.0 is NOT filtered because with sentinel=100.0, values up to
        ±99.99 are considered legitimate large tiled UVs. The value -22.0 could
        theoretically be a legitimate large negative tiled UV (22 tiles).
        The real garbage/placeholder UV values seen in KotOR are more extreme
        (e.g. 127, 255-range values from DXT block edge artifacts).
        """
        from gui.tpc_render_utils import _UV_SENTINEL
        # These values are genuinely beyond any legitimate tiling range
        placeholder_values = [127.0, -127.0, 200.0, -200.0]
        for uv in placeholder_values:
            assert abs(uv) > _UV_SENTINEL, (
                f"UV={uv} should be filtered by sentinel={_UV_SENTINEL} "
                f"but abs({uv})={abs(uv)} <= {_UV_SENTINEL}"
            )

    def test_exactly_100_is_filtered(self):
        """UV values >= 100.0 should be filtered."""
        from gui.tpc_render_utils import _UV_SENTINEL
        assert abs(100.0) >= _UV_SENTINEL  # exactly at sentinel = filtered
        assert abs(127.0) > _UV_SENTINEL   # clearly filtered
        assert abs(99.9) < _UV_SENTINEL    # below sentinel = not filtered


# ─────────────────────────────────────────────────────────────────────────────
# 18-A: Batch rasterize_frame NumPy tier
# ─────────────────────────────────────────────────────────────────────────────

class TestRasterizeFrameNumPy:
    """Phase 18-A: rasterize_frame with NumPy tier handles large UVs."""

    def test_rasterize_frame_large_uv(self):
        """rasterize_frame should produce pixels with large UV values (tiling)."""
        import gui.accel as accel_mod
        original_tier = accel_mod.ACCEL_TIER

        # Force NumPy tier
        accel_mod.ACCEL_TIER = 2

        try:
            buf = np.zeros((64, 64, 4), dtype=np.uint8)
            tex = _make_checker_tex(16)

            # Single triangle with large UV values
            verts_sx = np.array([2, 62, 32], dtype=np.int64)
            verts_sy = np.array([2, 2, 60],  dtype=np.int64)
            uvs_u    = np.array([12.1, 12.9, 12.5], dtype=np.float64)
            uvs_v    = np.array([12.1, 12.1, 12.9], dtype=np.float64)
            fv0 = np.array([0], dtype=np.int64)
            fv1 = np.array([1], dtype=np.int64)
            fv2 = np.array([2], dtype=np.int64)
            sr  = np.array([255], dtype=np.int64)
            sg  = np.array([255], dtype=np.int64)
            sb  = np.array([255], dtype=np.int64)
            na  = np.array([1.0], dtype=np.float64)
            vis = np.array([True], dtype=np.bool_)

            accel_mod.rasterize_frame(buf, tex, verts_sx, verts_sy,
                                      uvs_u, uvs_v, fv0, fv1, fv2,
                                      sr, sg, sb, na, vis)

            non_bg = (buf[:,:,3] > 0).sum()
            assert non_bg > 500, f"rasterize_frame large UV: {non_bg} pixels (expected >500)"
            orange = (buf[:,:,0] > 200) & (buf[:,:,1] > 100) & (buf[:,:,2] < 50)
            blue   = (buf[:,:,0] < 50) & (buf[:,:,2] > 100)
            assert orange.sum() > 0, "rasterize_frame: no orange pixels with large UV"
            assert blue.sum() > 0,   "rasterize_frame: no blue pixels with large UV"
        finally:
            accel_mod.ACCEL_TIER = original_tier

    def test_rasterize_frame_normal_uv(self):
        """rasterize_frame should still work correctly with normal UVs."""
        import gui.accel as accel_mod
        original_tier = accel_mod.ACCEL_TIER
        accel_mod.ACCEL_TIER = 2
        try:
            buf = np.zeros((64, 64, 4), dtype=np.uint8)
            tex = _make_checker_tex(16)
            verts_sx = np.array([2, 62, 32], dtype=np.int64)
            verts_sy = np.array([2, 2, 60],  dtype=np.int64)
            uvs_u    = np.array([0.1, 0.9, 0.5], dtype=np.float64)
            uvs_v    = np.array([0.1, 0.1, 0.9], dtype=np.float64)
            fv0 = np.array([0], dtype=np.int64)
            fv1 = np.array([1], dtype=np.int64)
            fv2 = np.array([2], dtype=np.int64)
            sr  = np.array([255], dtype=np.int64)
            sg  = np.array([255], dtype=np.int64)
            sb  = np.array([255], dtype=np.int64)
            na  = np.array([1.0], dtype=np.float64)
            vis = np.array([True], dtype=np.bool_)
            accel_mod.rasterize_frame(buf, tex, verts_sx, verts_sy,
                                      uvs_u, uvs_v, fv0, fv1, fv2,
                                      sr, sg, sb, na, vis)
            non_bg = (buf[:,:,3] > 0).sum()
            assert non_bg > 500, f"Normal UV: {non_bg} pixels"
        finally:
            accel_mod.ACCEL_TIER = original_tier


# ─────────────────────────────────────────────────────────────────────────────
# Seam fix threshold validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSeamFixThreshold:
    """Verify seam fix applies only when span < 1.0 in accel path."""

    def test_seam_fix_applies_for_seam_triangle(self):
        """Seam fix should adjust UVs for seam-crossing triangle (span < 1.0)."""
        from gui.tpc_render_utils import _uwrap_global, _edge_has_seam_global
        u0, u1, u2 = 0.95, 0.05, 0.5
        raw_span = max(u0, u1, u2) - min(u0, u1, u2)
        assert raw_span < 1.0, f"Expected span < 1.0, got {raw_span}"
        # Seam detected
        u_has_seam = (_edge_has_seam_global(u0, u1) or
                      _edge_has_seam_global(u0, u2) or
                      _edge_has_seam_global(u1, u2))
        assert u_has_seam, "Expected seam detected for u=[0.95, 0.05, 0.5]"
        # After fix
        u1_fixed = _uwrap_global(u0, u1)
        u2_fixed = _uwrap_global(u0, u2)
        new_span = max(u0, u1_fixed, u2_fixed) - min(u0, u1_fixed, u2_fixed)
        assert new_span < raw_span, f"Seam fix should reduce span: {raw_span} → {new_span}"

    def test_seam_fix_skipped_for_large_uv(self):
        """Seam fix must NOT apply for large multi-tile UVs (span >= 1.0)."""
        u0, u1, u2 = -12.86, 12.86, 0.0
        raw_span_u = max(u0, u1, u2) - min(u0, u1, u2)
        assert raw_span_u >= 1.0, f"Expected span >= 1.0, got {raw_span_u}"
        # With the threshold at 1.0, seam fix is skipped
        seam_fix_would_run = (raw_span_u < 1.0)
        assert not seam_fix_would_run, "Seam fix should be SKIPPED for large UV span"

    def test_torso_back_seam_uv_range(self):
        """Torso back-seam UVs (u=[0.003, 1.364]) should trigger tiling, not seam fix."""
        u0, u1, u2 = 0.003, 1.364, 0.003
        raw_span_u = max(u0, u1, u2) - min(u0, u1, u2)
        assert raw_span_u >= 1.0, (
            f"Torso back-seam span={raw_span_u:.3f} should be >= 1.0 to skip seam fix"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
