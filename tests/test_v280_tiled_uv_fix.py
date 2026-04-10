"""
tests/test_v280_tiled_uv_fix.py — Phase 16 tests: Tiled UV coordinate fix

ROOT CAUSE (Phase 16):
  When the tiling path creates a tiled texture of size tw_t = src_w * tile_u,
  the UV-to-pixel conversion was:
    tu = u_shifted * tw   (where tw = tw_t after 'tex_img = tiled; tw, th = tw_t, th_t')

  But u_shifted is in the range [0, tile_u], NOT [0, 1].
  So tu = u_shifted * src_w * tile_u — which is tile_u times too large.

  CORRECT formula:
    tu = u_shifted * src_w   (single-tile pixel width)

  This bug caused:
  - 8-tile UV spans (torso_g type): only ~8% coverage (PIL AFFINE maps coords outside
    the texture bounds → transparent fill)
  - 2-7 tile spans: proportionally worse rendering

  FIX: Track _tile_src_w = src_w after the tiling block and use it for tu conversion.
  Same fix applied in both tpc_render_utils.py and viewport.py.

Tests verify:
  1. Large UV spans (2-8 tiles) render with full coverage
  2. Non-tiled path (UV ≤ 1.0 span) unchanged
  3. Frac fallback (>8 tiles) still works
  4. Seam-crossing faces with OOB UVs still render
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from gui.tpc_render_utils import _paste_textured_triangle


def make_checker(size=64, cs=8):
    """Make a checker texture for testing."""
    if not PIL_AVAILABLE:
        return None
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            arr[y,x] = [200,100,50,255] if (x//cs+y//cs)%2==0 else [50,100,200,255]
    return Image.fromarray(arr)


def render_tri(uv0, uv1, uv2, W=256, H=256):
    """Render a triangle and return (pixel_count, image)."""
    if not PIL_AVAILABLE:
        return 0, None
    checker = make_checker(64, 8)
    canvas = Image.new('RGBA', (W, H), (30, 30, 30, 255))
    sp0, sp1, sp2 = (50, 50), (200, 50), (128, 200)
    _paste_textured_triangle(
        canvas, checker, sp0, sp1, sp2, uv0, uv1, uv2, W, H,
        shade_color=(255, 255, 255), node_alpha=1.0, is_additive=False,
        skip_seam_fix=False, skip_seam_u=False, skip_seam_v=False,
    )
    arr = np.array(canvas)
    bg = np.array([30, 30, 30])
    non_bg = np.any(arr[:,:,:3] != bg, axis=2)
    return int(non_bg.sum()), canvas


@pytest.mark.skipif(not PIL_AVAILABLE, reason='PIL not available')
class TestTiledUVFix:
    """Phase 16 tiled UV coordinate fix tests."""

    def test_normal_uv_baseline(self):
        """Normal UVs [0,1] should render with full triangle coverage."""
        cnt, _ = render_tri((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))
        # Triangle area in 256x256 canvas ~ 22400 px
        assert cnt > 18000, f'Normal UVs: expected >18000 px, got {cnt}'

    def test_2tile_span_renders(self):
        """2-tile UV span should render fully (not blank)."""
        # span_u = 2.0, span_v = 2.0
        cnt, _ = render_tri((-0.5, -0.5), (1.5, -0.5), (0.5, 1.5))
        assert cnt > 18000, f'2-tile span: expected >18000 px, got {cnt}'

    def test_3tile_span_renders(self):
        """3-tile UV span should render fully."""
        cnt, _ = render_tri((-1.0, -1.0), (2.0, -1.0), (0.5, 2.0))
        assert cnt > 18000, f'3-tile span: expected >18000 px, got {cnt}'

    def test_7tile_span_renders(self):
        """7-tile UV span (was broken: 1847 px → now ~22400 px)."""
        cnt, _ = render_tri((-3.5, -2.5), (3.5, -2.5), (0.0, 4.0))
        assert cnt > 18000, (
            f'7-tile span: expected >18000 px, got {cnt}. '
            f'This was the primary Phase 16 bug (tu=u*tw_t was tile_u times too large).'
        )

    def test_8tile_span_renders(self):
        """8-tile UV span (maximum tiled budget) should render fully.

        Note: avoid exact integer UV boundaries (e.g. -4.0, 4.0) because
        frac(-4.0)=0.0 and frac(4.0)=0.0 both map to 0.0, making the triangle
        degenerate (all U collapse to same value).  Use non-integer boundaries.
        """
        # tile_u = floor(3.9) - floor(-3.9) + 1 = 3 - (-4) + 1 = 8
        cnt, _ = render_tri((-3.9, -2.9), (3.9, -2.9), (0.0, 4.9))
        assert cnt > 18000, f'8-tile span: expected >18000 px, got {cnt}'

    def test_extreme_uv_frac_fallback(self):
        """UVs spanning >8 tiles use frac() fallback (still renders something)."""
        # pelvis_g-style: U=[-13.5, +13.5]
        cnt, _ = render_tri((-9.5, -8.7), (-11.8, 4.4), (-0.25, -8.7))
        assert cnt > 18000, f'Extreme UV frac: expected >18000 px, got {cnt}'

    def test_seam_face_oob_renders(self):
        """Back-seam face with u=[0.003, 1.366, 0.003] should render (2-tile)."""
        cnt, _ = render_tri((0.003, 0.5), (1.366, 0.5), (0.7, 0.9))
        assert cnt > 18000, f'Seam face OOB: expected >18000 px, got {cnt}'

    def test_centroid_shift_single_tile_oob(self):
        """Single-tile face shifted outside [0,1] uses centroid shift."""
        cnt, _ = render_tri((1.3, 0.5), (1.4, 0.3), (1.2, 0.8))
        assert cnt > 18000, f'Centroid shift OOB: expected >18000 px, got {cnt}'

    def test_7tile_vs_normal_similar_coverage(self):
        """7-tile UV renders approximately same pixel count as normal UVs."""
        normal_cnt, _ = render_tri((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))
        tiled_cnt, _ = render_tri((-3.5, -2.5), (3.5, -2.5), (0.0, 4.0))
        # Should be within 20% of each other (tiling fills same screen area)
        ratio = tiled_cnt / max(normal_cnt, 1)
        assert 0.80 <= ratio <= 1.20, (
            f'7-tile coverage should be ~same as normal: '
            f'normal={normal_cnt}, tiled={tiled_cnt}, ratio={ratio:.2f}'
        )

    def test_tile_count_boundary_exactly_8(self):
        """Test UV span that requires exactly 8×8 tiles (max budget boundary)."""
        # Exactly tile_u=8, tile_v=8
        cnt, _ = render_tri((-3.5, -2.5), (3.5, -2.5), (0.0, 4.0))
        assert cnt > 15000, f'Exactly 8-tile boundary: {cnt} pixels'

    def test_no_regression_normal_uvs(self):
        """Normal UV path (no tiling) should not be affected by the fix."""
        cnt1, _ = render_tri((0.2, 0.3), (0.8, 0.2), (0.5, 0.9))
        cnt2, _ = render_tri((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))
        # Both should give good coverage
        assert cnt1 > 15000, f'Normal UV interior: {cnt1}'
        assert cnt2 > 15000, f'Normal UV full tile: {cnt2}'

    def test_negative_uv_start(self):
        """Faces starting at large negative UV values should render."""
        cnt, _ = render_tri((-7.5, -6.0), (-6.0, -6.0), (-6.7, -4.5))
        assert cnt > 15000, f'Negative UV start: {cnt}'

    def test_positive_large_uv(self):
        """Large positive UV values (no negative start) should tile correctly."""
        cnt, _ = render_tri((5.5, 4.0), (7.5, 4.0), (6.5, 6.5))
        assert cnt > 15000, f'Positive large UV: {cnt}'


@pytest.mark.skipif(not PIL_AVAILABLE, reason='PIL not available')
class TestTiledUVMathVerification:
    """Verify the math of the tiled UV coordinate conversion."""

    def test_tu_calculation_correctness(self):
        """
        Verify tu = u_shifted * src_w (not u_shifted * tw_t).

        After tiling:
          u_shifted = original_u - u_floor  (in range [0, tile_u])
          src_w = thumbnail side length (single tile)
          tw_t = src_w * tile_u (full tiled image width)

        WRONG: tu = u_shifted * tw_t = u_shifted * src_w * tile_u
               → tile_u times too large → PIL AFFINE samples far outside texture
        RIGHT: tu = u_shifted * src_w
               → maps [0, tile_u] → [0, tw_t] correctly

        We verify by checking that a 7-tile UV face renders with good coverage
        (>18000 pixels in a 256x256 canvas with a ~22000-pixel triangle area).
        """
        u0, u1, u2 = -3.5, 3.5, 0.0
        v0, v1, v2 = -2.5, -2.5, 4.0

        # Verify the bug scenario:
        # u_floor = floor(-3.5) = -4, tile_u = floor(3.5) - (-4) + 1 = 8
        # src_w = 64 (from 64x64 checker texture, MAX_TILE_SRC_PX=128)
        # tw_t = 64 * 8 = 512
        # u0_shifted = -3.5 - (-4) = 0.5
        # WRONG: tu0 = 0.5 * 512 = 256 (center of 512px image) - OK for u0
        # u1_shifted = 3.5 - (-4) = 7.5
        # WRONG: tu1 = 7.5 * 512 = 3840  >> tw_t=512 → PIL fills with (0,0,0,0)
        # RIGHT: tu1 = 7.5 * 64 = 480  < tw_t=512 → samples correctly

        u1_shifted = u1 - math.floor(min(u0, u1, u2))  # 3.5 - (-4) = 7.5
        src_w = 64  # checker texture size

        wrong_tu1 = u1_shifted * (src_w * 8)  # 7.5 * 512 = 3840
        right_tu1 = u1_shifted * src_w         # 7.5 * 64 = 480

        assert wrong_tu1 > 512, f'Bug scenario: wrong_tu1={wrong_tu1} should exceed tiled_w'
        assert right_tu1 < 512, f'Fixed: right_tu1={right_tu1} should be within tiled_w'

        # Now verify the actual renderer uses the fixed formula
        cnt, _ = render_tri((u0, v0), (u1, v1), (u2, v2))
        assert cnt > 18000, (
            f'Math verification: 7-tile UV should render {cnt} > 18000 pixels. '
            f'If this fails, the tu=u*src_w fix is not applied correctly.'
        )
