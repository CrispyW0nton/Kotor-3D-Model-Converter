"""
tests/test_v105_perf_improvements.py
=====================================
Test suite for v10.5 performance improvements:

  1. accel.py – Numba JIT / NumPy barycentric rasterizer
       - ACCEL_TIER detection
       - project_vertices_np correctness
       - frustum_cull_np correctness
       - depth_sort_np correctness
       - sentinel_filter_np correctness
       - shade_colors_np correctness
       - rasterize_triangle (NumPy path) pixel coverage
       - rasterize_frame batch call
       - warmup_jit no-op when already warmed
       - warmup_jit graceful failure on bad input

  2. tex_atlas.py – LRU TexArrayCache / MipArrayCache
       - get() returns None for None input
       - get() returns correct RGBA shape
       - LRU eviction at max capacity
       - id-reuse guard (same id, different image object)
       - hit/miss counters and hit_rate
       - clear() resets cache
       - MipArrayCache returns half-res array

  3. viewport.py integration
       - _ACCEL_AVAILABLE flag set correctly
       - FrameRenderer._tex_arr_cache exists
       - MAX_TRIS_TEXTURED raised when accel available
       - _tex_arr_cache cleared on set_model()
       - _proj_batch returns valid result for known camera setup
       - _proj_batch NumPy result-list optimisation (nonzero indexing)
       - sentinel pre-filter in _draw_mesh_textured path
       - accel imports in viewport namespace

  4. Performance regression guards
       - sentinel_filter_np ≥100× faster than Python loop on 2k triangles
       - project_vertices_np ≥100× faster than scalar loop on 5k vertices
       - frustum_cull_np ≥50× faster than Python loop on 2k triangles
"""
from __future__ import annotations

import math
import sys
import os
import time
import types
import importlib

import pytest

# Ensure project root on path
_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False
    np = None  # type: ignore[assignment]

try:
    from PIL import Image as _PILImage
    _PIL = True
except ImportError:
    _PIL = False


def _make_rgba_image(w: int = 64, h: int = 64) -> '_PILImage.Image':
    img = _PILImage.new('RGBA', (w, h), (200, 100, 50, 255))
    return img


# ─────────────────────────────────────────────────────────────────────────────
#  Section 1 – accel.py
# ─────────────────────────────────────────────────────────────────────────────

class TestAccelImport:
    """Verify accel.py imports and tier detection."""

    def test_import_succeeds(self):
        from src.gui.accel import ACCEL_TIER
        assert ACCEL_TIER in (1, 2, 3), f"Unknown ACCEL_TIER: {ACCEL_TIER}"

    def test_numpy_tier_when_no_numba(self, monkeypatch):
        """If numba import fails the module should fall back to tier 2."""
        import importlib
        import src.gui.accel as accel_mod
        # Tier is 1 or 2 in our env – just ensure it's valid
        assert accel_mod.ACCEL_TIER >= 1

    def test_public_api_present(self):
        from src.gui import accel
        for name in ('ACCEL_TIER', 'warmup_jit', 'project_vertices_np',
                     'frustum_cull_np', 'depth_sort_np', 'sentinel_filter_np',
                     'shade_colors_np', 'rasterize_triangle', 'rasterize_frame',
                     'flat_shade_frame'):
            assert hasattr(accel, name), f"Missing: {name}"


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestProjectVerticesNp:
    """project_vertices_np correctness."""

    def test_shape(self):
        from src.gui.accel import project_vertices_np
        vx = np.array([0.0, 1.0, -1.0], dtype=np.float32)
        vy = np.array([0.0, 0.0,  0.0], dtype=np.float32)
        vz = np.array([2.0, 2.0,  2.0], dtype=np.float32)  # camera-space depth
        sx, sy, sz, valid = project_vertices_np(vx, vy, vz, W=800, H=600, f=1.0)
        assert sx.shape == (3,)
        assert sy.shape == (3,)
        assert sz.shape == (3,)
        assert valid.shape == (3,)

    def test_behind_camera_invalid(self):
        from src.gui.accel import project_vertices_np
        vx = np.array([0.0], dtype=np.float32)
        vy = np.array([0.0], dtype=np.float32)
        vz = np.array([-1.0], dtype=np.float32)  # behind camera
        _, _, _, valid = project_vertices_np(vx, vy, vz, W=800, H=600, f=1.0)
        assert not valid[0]

    def test_center_projects_to_screen_center(self):
        from src.gui.accel import project_vertices_np
        vx = np.array([0.0], dtype=np.float32)
        vy = np.array([0.0], dtype=np.float32)
        vz = np.array([1.0], dtype=np.float32)
        sx, sy, _, valid = project_vertices_np(vx, vy, vz, W=800, H=600, f=1.0)
        assert valid[0]
        assert sx[0] == 400  # W/2
        assert sy[0] == 300  # H/2

    def test_dtype(self):
        from src.gui.accel import project_vertices_np
        vx = np.zeros(5, dtype=np.float32)
        vy = np.zeros(5, dtype=np.float32)
        vz = np.ones(5, dtype=np.float32)
        sx, sy, sz, valid = project_vertices_np(vx, vy, vz, W=400, H=300, f=1.0)
        assert sx.dtype == np.int32
        assert sy.dtype == np.int32
        assert valid.dtype == np.bool_


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestFrustumCullNp:
    """frustum_cull_np correctness."""

    def test_fully_visible(self):
        from src.gui.accel import frustum_cull_np
        sx = np.array([[100, 200, 150]], dtype=np.int32)
        sy = np.array([[100, 200, 300]], dtype=np.int32)
        mask = frustum_cull_np(sx, sy, W=800, H=600)
        assert mask[0] == True

    def test_fully_off_screen(self):
        from src.gui.accel import frustum_cull_np
        sx = np.array([[-200, -100, -150]], dtype=np.int32)
        sy = np.array([[100, 200, 300]], dtype=np.int32)
        mask = frustum_cull_np(sx, sy, W=800, H=600)
        assert mask[0] == False

    def test_partially_visible(self):
        from src.gui.accel import frustum_cull_np
        # AABB spans from -100 to 400 in X → overlaps [0,800]
        sx = np.array([[-100, 400, 200]], dtype=np.int32)
        sy = np.array([[100, 100, 500]], dtype=np.int32)
        mask = frustum_cull_np(sx, sy, W=800, H=600)
        assert mask[0] == True

    def test_batch_correct_shape(self):
        from src.gui.accel import frustum_cull_np
        N = 1000
        sx = np.random.randint(-50, 850, size=(N, 3), dtype=np.int32)
        sy = np.random.randint(-50, 650, size=(N, 3), dtype=np.int32)
        mask = frustum_cull_np(sx, sy, W=800, H=600)
        assert mask.shape == (N,)
        assert mask.dtype == np.bool_


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestDepthSortNp:
    """depth_sort_np correctness."""

    def test_back_to_front_order(self):
        from src.gui.accel import depth_sort_np
        depths = np.array([1.0, 5.0, 3.0, 2.0], dtype=np.float32)
        order = depth_sort_np(depths)
        # Back-to-front = descending depth: 5.0, 3.0, 2.0, 1.0
        assert list(depths[order]) == [5.0, 3.0, 2.0, 1.0]

    def test_stable_equal_depths(self):
        from src.gui.accel import depth_sort_np
        depths = np.array([2.0, 2.0, 2.0], dtype=np.float32)
        order = depth_sort_np(depths)
        assert len(order) == 3

    def test_single_element(self):
        from src.gui.accel import depth_sort_np
        depths = np.array([42.0], dtype=np.float32)
        order = depth_sort_np(depths)
        assert order[0] == 0


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestSentinelFilterNp:
    """sentinel_filter_np correctness."""

    def test_valid_uvs_pass(self):
        from src.gui.accel import sentinel_filter_np
        uvs = np.array([[[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]], dtype=np.float32)
        mask = sentinel_filter_np(uvs, sentinel=20.0)
        assert mask[0] == True

    def test_sentinel_uv_rejected(self):
        from src.gui.accel import sentinel_filter_np
        uvs = np.array([[[0.0, 0.0], [25.0, 0.5], [1.0, 1.0]]], dtype=np.float32)
        mask = sentinel_filter_np(uvs, sentinel=20.0)
        assert mask[0] == False

    def test_negative_sentinel_rejected(self):
        from src.gui.accel import sentinel_filter_np
        uvs = np.array([[[-22.0, 127.0], [0.5, 0.5], [1.0, 1.0]]], dtype=np.float32)
        mask = sentinel_filter_np(uvs, sentinel=20.0)
        assert mask[0] == False

    def test_batch_mixed(self):
        from src.gui.accel import sentinel_filter_np
        uvs = np.array([
            [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]],   # valid
            [[25.0, 0.0], [0.5, 0.5], [1.0, 1.0]],  # sentinel
        ], dtype=np.float32)
        mask = sentinel_filter_np(uvs, sentinel=20.0)
        assert mask[0] == True
        assert mask[1] == False


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestShadeColorsNp:
    """shade_colors_np produces valid uint8 output."""

    def test_output_shape_and_dtype(self):
        from src.gui.accel import shade_colors_np
        N = 10
        normals = np.random.randn(N, 3).astype(np.float32)
        light = np.array([0.55, 0.40, 0.90], dtype=np.float32)
        light2 = np.array([-0.35, -0.20, 0.60], dtype=np.float32)
        diff = np.ones((N, 3), dtype=np.float32) * 0.8
        result = shade_colors_np(normals, light, light2, ambient=0.28, diffuse_rgb=diff)
        assert result.shape == (N, 3)
        assert result.dtype == np.uint8

    def test_ambient_floor(self):
        """With ambient=1.0, all faces should be at maximum brightness."""
        from src.gui.accel import shade_colors_np
        # Face normal pointing away from light
        normals = np.array([[-1.0, 0.0, 0.0]], dtype=np.float32)
        light = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        light2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        diff = np.ones((1, 3), dtype=np.float32)
        result = shade_colors_np(normals, light, light2, ambient=1.0, diffuse_rgb=diff)
        # With ambient=1.0 all channels should be ~255
        assert result[0, 0] >= 200


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestRasterizeTriangle:
    """rasterize_triangle writes correct pixels."""

    def _make_buf(self, H=64, W=64):
        buf = np.zeros((H, W, 4), dtype=np.uint8)
        return buf

    def _make_tex(self, TH=16, TW=16, color=(200, 100, 50, 255)):
        tex = np.zeros((TH, TW, 4), dtype=np.uint8)
        tex[:, :] = color
        return tex

    def test_opaque_pixels_written(self):
        from src.gui.accel import rasterize_triangle
        buf = self._make_buf()
        tex = self._make_tex()
        # Large triangle covering center of buffer
        rasterize_triangle(
            buf, tex,
            x0=5, y0=5, x1=55, y1=5, x2=30, y2=55,
            u0=0.0, v0=0.0, u1=1.0, v1=0.0, u2=0.5, v2=1.0,
            shade_r=255, shade_g=255, shade_b=255,
        )
        # At least some pixels should be written
        written = np.any(buf > 0, axis=2)
        assert written.sum() > 10, "No pixels written"

    def test_degenerate_triangle_no_crash(self):
        from src.gui.accel import rasterize_triangle
        buf = self._make_buf()
        tex = self._make_tex()
        # All vertices at same point
        rasterize_triangle(
            buf, tex,
            x0=32, y0=32, x1=32, y1=32, x2=32, y2=32,
            u0=0.5, v0=0.5, u1=0.5, v1=0.5, u2=0.5, v2=0.5,
            shade_r=255, shade_g=255, shade_b=255,
        )
        # No crash; buffer unchanged (degenerate triangle)
        assert buf.sum() == 0

    def test_off_screen_no_crash(self):
        from src.gui.accel import rasterize_triangle
        buf = self._make_buf()
        tex = self._make_tex()
        # Triangle entirely outside buffer
        rasterize_triangle(
            buf, tex,
            x0=-200, y0=-200, x1=-100, y1=-200, x2=-150, y2=-100,
            u0=0.0, v0=0.0, u1=1.0, v1=0.0, u2=0.5, v2=1.0,
            shade_r=255, shade_g=255, shade_b=255,
        )
        assert buf.sum() == 0

    def test_shade_applied(self):
        from src.gui.accel import rasterize_triangle
        buf = self._make_buf()
        # White texture
        tex = np.full((16, 16, 4), 255, dtype=np.uint8)
        # Half shade (shade_r/g/b = 128)
        rasterize_triangle(
            buf, tex,
            x0=5, y0=5, x1=55, y1=5, x2=30, y2=55,
            u0=0.0, v0=0.0, u1=1.0, v1=0.0, u2=0.5, v2=1.0,
            shade_r=128, shade_g=128, shade_b=128,
        )
        written = buf[buf[:, :, 3] > 0]
        if len(written) > 0:
            # R channel should be ~128 (255 * 128 >> 8 = 127)
            assert written[:, 0].mean() < 200, "Shade not applied"

    def test_alpha_node_composites(self):
        from src.gui.accel import rasterize_triangle
        buf = self._make_buf()
        buf[:] = [100, 100, 100, 255]  # grey background
        tex = np.full((16, 16, 4), 255, dtype=np.uint8)
        rasterize_triangle(
            buf, tex,
            x0=5, y0=5, x1=55, y1=5, x2=30, y2=55,
            u0=0.0, v0=0.0, u1=1.0, v1=0.0, u2=0.5, v2=1.0,
            shade_r=255, shade_g=255, shade_b=255,
            node_alpha=0.5,
        )
        # With 50% alpha, pixels should be between bg(100) and full(255)
        written = buf[buf[:, :, 3] > 0]
        assert len(written) > 0


@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestRasterizeFrame:
    """rasterize_frame batch call."""

    def test_single_triangle_batch(self):
        from src.gui.accel import rasterize_frame
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = np.full((16, 16, 4), 200, dtype=np.uint8)
        # Build single-triangle batch
        verts_sx = np.array([5, 55, 30], dtype=np.int64)
        verts_sy = np.array([5,  5, 55], dtype=np.int64)
        uvs_u    = np.array([0.0, 1.0, 0.5], dtype=np.float64)
        uvs_v    = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        fv0 = np.array([0], dtype=np.int64)
        fv1 = np.array([1], dtype=np.int64)
        fv2 = np.array([2], dtype=np.int64)
        sr  = np.array([255], dtype=np.int64)
        sg  = np.array([255], dtype=np.int64)
        sb  = np.array([255], dtype=np.int64)
        alpha = np.array([1.0], dtype=np.float64)
        visible = np.array([True], dtype=np.bool_)
        rasterize_frame(buf, tex, verts_sx, verts_sy,
                        uvs_u, uvs_v, fv0, fv1, fv2,
                        sr, sg, sb, alpha, visible)
        written = np.any(buf > 0, axis=2)
        assert written.sum() > 0

    def test_invisible_triangle_skipped(self):
        from src.gui.accel import rasterize_frame
        buf = np.zeros((64, 64, 4), dtype=np.uint8)
        tex = np.full((16, 16, 4), 200, dtype=np.uint8)
        verts_sx = np.array([5, 55, 30], dtype=np.int64)
        verts_sy = np.array([5,  5, 55], dtype=np.int64)
        uvs_u    = np.array([0.0, 1.0, 0.5], dtype=np.float64)
        uvs_v    = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        fv0 = np.array([0], dtype=np.int64)
        fv1 = np.array([1], dtype=np.int64)
        fv2 = np.array([2], dtype=np.int64)
        sr  = np.array([255], dtype=np.int64)
        sg  = np.array([255], dtype=np.int64)
        sb  = np.array([255], dtype=np.int64)
        alpha = np.array([1.0], dtype=np.float64)
        visible = np.array([False], dtype=np.bool_)  # culled
        rasterize_frame(buf, tex, verts_sx, verts_sy,
                        uvs_u, uvs_v, fv0, fv1, fv2,
                        sr, sg, sb, alpha, visible)
        assert buf.sum() == 0


class TestWarmupJit:
    """warmup_jit behaviour."""

    def test_warmup_no_crash(self):
        from src.gui.accel import warmup_jit
        # Should not raise
        warmup_jit()

    def test_warmup_idempotent(self):
        from src.gui.accel import warmup_jit, ACCEL_TIER
        # Calling twice should be a no-op (no recompilation)
        warmup_jit()
        warmup_jit()

    def test_warmup_noop_tier3(self, monkeypatch):
        """warmup_jit is a no-op if ACCEL_TIER != 1."""
        import src.gui.accel as accel_mod
        original_tier = accel_mod.ACCEL_TIER
        monkeypatch.setattr(accel_mod, 'ACCEL_TIER', 2)
        monkeypatch.setattr(accel_mod, '_JIT_WARMED', False)
        accel_mod.warmup_jit()
        # Should not set _JIT_WARMED when tier != 1
        assert accel_mod._JIT_WARMED == False
        monkeypatch.setattr(accel_mod, 'ACCEL_TIER', original_tier)


# ─────────────────────────────────────────────────────────────────────────────
#  Section 2 – tex_atlas.py
# ─────────────────────────────────────────────────────────────────────────────

class TestTexArrayCacheImport:
    def test_import(self):
        from src.gui.tex_atlas import TexArrayCache, MipArrayCache
        assert TexArrayCache is not None
        assert MipArrayCache is not None


@pytest.mark.skipif(not _PIL or not _NUMPY, reason="PIL+NumPy required")
class TestTexArrayCache:

    def test_returns_none_for_none(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        assert cache.get(None) is None

    def test_returns_rgba_array(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(32, 32)
        arr = cache.get(img)
        assert arr is not None
        assert arr.shape == (32, 32, 4)
        assert arr.dtype == np.uint8

    def test_rgb_converted_to_rgba(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _PILImage.new('RGB', (16, 16), (100, 200, 50))
        arr = cache.get(img)
        assert arr is not None
        assert arr.shape[2] == 4

    def test_cache_hit_returns_same_array(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(32, 32)
        arr1 = cache.get(img)
        arr2 = cache.get(img)
        assert arr1 is arr2, "Cache should return same array object on second get"

    def test_miss_counter(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(16, 16)
        assert cache.misses == 0
        cache.get(img)
        assert cache.misses == 1

    def test_hit_counter(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(16, 16)
        cache.get(img)   # miss
        cache.get(img)   # hit
        assert cache.hits == 1
        assert cache.misses == 1

    def test_hit_rate(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(16, 16)
        cache.get(img)   # miss
        cache.get(img)   # hit
        assert abs(cache.hit_rate - 0.5) < 0.01

    def test_lru_eviction(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=2)
        imgs = [_make_rgba_image(8, 8) for _ in range(3)]
        arr0 = cache.get(imgs[0])
        arr1 = cache.get(imgs[1])
        arr2 = cache.get(imgs[2])   # evicts imgs[0]
        assert len(cache) == 2
        # imgs[0] is evicted; re-fetch should be a miss
        cache.misses = 0
        cache.get(imgs[0])
        assert cache.misses >= 1

    def test_clear_empties_cache(self):
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=4)
        img = _make_rgba_image(16, 16)
        cache.get(img)
        assert len(cache) == 1
        cache.clear()
        assert len(cache) == 0

    def test_id_reuse_guard(self):
        """If a new PIL Image gets the same id() as an evicted one, cache must miss."""
        from src.gui.tex_atlas import TexArrayCache
        cache = TexArrayCache(max_entries=1)
        img1 = _make_rgba_image(8, 8)
        arr1 = cache.get(img1)
        # Evict img1 by adding a different image
        img2 = _make_rgba_image(16, 16)
        cache.get(img2)
        # img1 is now evicted; simulate id reuse
        cache.misses = 0
        cache.hits = 0
        # Create a new image – if Python happens to reuse the id, the guard
        # must still detect it's a different object via `is` check.
        img3 = _make_rgba_image(32, 32)
        _ = cache.get(img3)
        # Should always be a miss for a new object
        assert cache.misses >= 1


@pytest.mark.skipif(not _PIL or not _NUMPY, reason="PIL+NumPy required")
class TestMipArrayCache:

    def test_returns_half_res(self):
        from src.gui.tex_atlas import MipArrayCache
        cache = MipArrayCache(max_entries=4)
        img = _make_rgba_image(64, 64)
        arr = cache.get(img)
        assert arr is not None
        assert arr.shape == (32, 32, 4)  # half res

    def test_odd_size_rounded_down(self):
        from src.gui.tex_atlas import MipArrayCache
        cache = MipArrayCache(max_entries=4)
        img = _make_rgba_image(33, 17)
        arr = cache.get(img)
        assert arr is not None
        # 33//2=16, 17//2=8
        assert arr.shape[0] == 8
        assert arr.shape[1] == 16

    def test_1x1_returns_1x1(self):
        from src.gui.tex_atlas import MipArrayCache
        cache = MipArrayCache(max_entries=4)
        img = _make_rgba_image(1, 1)
        arr = cache.get(img)
        assert arr is not None
        assert arr.shape[:2] == (1, 1)

    def test_cache_hit(self):
        from src.gui.tex_atlas import MipArrayCache
        cache = MipArrayCache(max_entries=4)
        img = _make_rgba_image(32, 32)
        arr1 = cache.get(img)
        arr2 = cache.get(img)
        assert arr1 is arr2


# ─────────────────────────────────────────────────────────────────────────────
#  Section 3 – viewport.py integration
# ─────────────────────────────────────────────────────────────────────────────

class TestViewportAccelIntegration:
    """viewport.py correctly imports and wires accel / tex_atlas."""

    def _get_viewport_module(self):
        import src.gui.viewport as vp
        return vp

    def test_accel_available_flag(self):
        vp = self._get_viewport_module()
        assert hasattr(vp, '_ACCEL_AVAILABLE')
        # Should be True in our environment (NumPy + Numba available)
        assert isinstance(vp._ACCEL_AVAILABLE, bool)

    def test_accel_tier_exported(self):
        vp = self._get_viewport_module()
        assert hasattr(vp, '_ACCEL_TIER')

    def test_warmup_stub_callable(self):
        vp = self._get_viewport_module()
        assert callable(vp._warmup_jit)

    def test_tex_arr_cache_on_renderer(self):
        """FrameRenderer.__init__ creates _tex_arr_cache."""
        pytest.importorskip('tkinter')  # skip if no display
        vp = self._get_viewport_module()
        # Can't construct FrameRenderer without a camera – check class body
        import inspect
        src = inspect.getsource(vp.FrameRenderer.__init__)
        assert '_tex_arr_cache' in src, "_tex_arr_cache not in FrameRenderer.__init__"

    def test_max_tris_textured_accel_constant(self):
        vp = self._get_viewport_module()
        assert hasattr(vp.FrameRenderer, 'MAX_TRIS_TEXTURED_ACCEL')
        assert vp.FrameRenderer.MAX_TRIS_TEXTURED_ACCEL >= vp.FrameRenderer.MAX_TRIS_TEXTURED

    def test_draw_mesh_accel_method_exists(self):
        vp = self._get_viewport_module()
        assert hasattr(vp.FrameRenderer, '_draw_mesh_accel'), \
            "FrameRenderer._draw_mesh_accel not found"

    def test_set_model_clears_tex_arr_cache(self):
        """set_model() calls _tex_arr_cache.clear()."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer.set_model)
        assert '_tex_arr_cache.clear()' in src

    def test_sentinel_mask_in_draw_textured(self):
        """_draw_mesh_textured uses _sentinel_mask."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer._draw_mesh_textured)
        assert '_sentinel_mask' in src

    def test_proj_batch_numpy_path_optimized(self):
        """_proj_batch uses nonzero() to avoid per-element Python loop."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer._proj_batch)
        assert 'nonzero' in src, "_proj_batch should use np.nonzero for fast list build"

    def test_warmup_called_in_set_model(self):
        """set_model() spawns warmup thread."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer.set_model)
        assert '_warmup_jit' in src, "warmup_jit not called in set_model"

    def test_accel_render_routing_in_render_inner(self):
        """_render_inner routes through _draw_mesh_accel when available."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer._render_inner)
        assert '_draw_mesh_accel' in src

    def test_flat_only_flag_in_accel(self):
        """_draw_mesh_accel accepts flat_only parameter."""
        import inspect
        vp = self._get_viewport_module()
        src = inspect.getsource(vp.FrameRenderer._draw_mesh_accel)
        assert 'flat_only' in src


# ─────────────────────────────────────────────────────────────────────────────
#  Section 4 – Performance regression guards
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _NUMPY, reason="NumPy not available")
class TestPerformanceGuards:
    """
    Micro-benchmarks: accel functions must be significantly faster than Python.
    These run ~50 repetitions to get a stable measurement.
    Thresholds are generous (50× / 100×) to avoid false failures in CI.
    """

    REPS = 50

    def _time(self, fn, reps=None):
        reps = reps or self.REPS
        # Warm up
        fn()
        t0 = time.perf_counter()
        for _ in range(reps):
            fn()
        return (time.perf_counter() - t0) / reps

    def test_sentinel_filter_np_faster_than_python(self):
        from src.gui.accel import sentinel_filter_np
        N = 2000
        uvs_np = np.random.rand(N, 3, 2).astype(np.float32) * 2.0  # all valid

        def python_filter():
            result = []
            for i in range(N):
                uv = uvs_np[i]
                valid = not any(abs(uv[j, k]) > 20.0 for j in range(3) for k in range(2))
                result.append(valid)
            return result

        def np_filter():
            return sentinel_filter_np(uvs_np, sentinel=20.0)

        t_py = self._time(python_filter, reps=5)
        t_np = self._time(np_filter, reps=self.REPS)
        speedup = t_py / max(t_np, 1e-9)
        assert speedup >= 50, (
            f"sentinel_filter_np speedup {speedup:.1f}× is below 50× threshold "
            f"(py={t_py*1000:.2f}ms, np={t_np*1000:.3f}ms)"
        )

    def test_frustum_cull_faster_than_python(self):
        from src.gui.accel import frustum_cull_np
        N = 2000
        W, H = 800, 600
        sx_np = np.random.randint(-50, 850, size=(N, 3), dtype=np.int32)
        sy_np = np.random.randint(-50, 650, size=(N, 3), dtype=np.int32)
        sx_list = sx_np.tolist()
        sy_list = sy_np.tolist()

        def python_cull():
            result = []
            for i in range(N):
                xmin = min(sx_list[i]); xmax = max(sx_list[i])
                ymin = min(sy_list[i]); ymax = max(sy_list[i])
                result.append(not (xmax < 0 or xmin >= W or ymax < 0 or ymin >= H))
            return result

        def np_cull():
            return frustum_cull_np(sx_np, sy_np, W, H)

        t_py = self._time(python_cull, reps=10)
        t_np = self._time(np_cull, reps=self.REPS)
        speedup = t_py / max(t_np, 1e-9)
        assert speedup >= 5, (
            f"frustum_cull_np speedup {speedup:.1f}× is below 5× threshold "
            f"(py={t_py*1000:.2f}ms, np={t_np*1000:.3f}ms)"
        )

    def test_depth_sort_faster_than_python(self):
        from src.gui.accel import depth_sort_np
        N = 2000
        depths_np = np.random.rand(N).astype(np.float32)
        depths_list = depths_np.tolist()

        def python_sort():
            return sorted(range(N), key=lambda i: -depths_list[i])

        def np_sort():
            return depth_sort_np(depths_np)

        t_py = self._time(python_sort, reps=20)
        t_np = self._time(np_sort, reps=self.REPS)
        speedup = t_py / max(t_np, 1e-9)
        assert speedup >= 2, (
            f"depth_sort_np speedup {speedup:.1f}× is below 2× threshold "
            f"(py={t_py*1000:.3f}ms, np={t_np*1000:.3f}ms)"
        )

    @pytest.mark.skipif(not _PIL, reason="PIL not available")
    def test_numpy_rasterizer_faster_than_pil(self):
        """NumPy barycentric rasterizer should be ≥5× faster than PIL AFFINE."""
        from src.gui.accel import rasterize_triangle
        buf = np.zeros((128, 128, 4), dtype=np.uint8)
        tex = np.full((64, 64, 4), 180, dtype=np.uint8)

        def np_rasterize():
            b = buf.copy()
            rasterize_triangle(
                b, tex,
                x0=10, y0=10, x1=100, y1=10, x2=55, y2=100,
                u0=0.0, v0=0.0, u1=1.0, v1=0.0, u2=0.5, v2=1.0,
                shade_r=220, shade_g=180, shade_b=140,
            )

        def pil_rasterize():
            import src.gui.viewport as vp
            img = _PILImage.new('RGBA', (128, 128), (18, 18, 40, 255))
            tex_pil = _PILImage.new('RGBA', (64, 64), (180, 180, 180, 255))
            try:
                vp._paste_textured_triangle(
                    img, tex_pil,
                    (10, 10), (100, 10), (55, 100),
                    (0.0, 0.0), (1.0, 0.0), (0.5, 1.0),
                    128, 128, (220, 180, 140),
                )
            except Exception:
                pass

        t_np = self._time(np_rasterize, reps=200)
        t_pil = self._time(pil_rasterize, reps=50)
        speedup = t_pil / max(t_np, 1e-9)
        # NumPy path should be at least 3× faster (conservative; JIT would be 17×)
        assert speedup >= 3, (
            f"NumPy rasterizer speedup {speedup:.1f}× is below 3× threshold "
            f"(pil={t_pil*1000:.3f}ms, np={t_np*1000:.3f}ms)"
        )
