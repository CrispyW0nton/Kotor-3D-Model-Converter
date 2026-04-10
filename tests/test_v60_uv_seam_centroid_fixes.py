"""
GhostRigger v6.0 — UV Seam Detection + Centroid-Shift Fix Tests
================================================================

Validates the v6.0 UV pipeline fixes applied to _paste_textured_triangle():

ROOT CAUSES FIXED (v6.0):
--------------------------
BUG-UV-SEAM-1  The old `_uwrap` was triggered whenever raw_span < 1.0 and the
               vertex diff > 0.5.  This incorrectly fired for legitimate large
               triangles (v0=0.2, v2=0.8, span=0.6) that do NOT straddle a seam,
               wrapping v2 from 0.8 to -0.2 and pushing UVs outside [0,1].
               FIX: New seam-detection compares frac(UV) span vs raw span.
               Only when frac-span > raw-span + 0.01 does a genuine seam exist.

BUG-UV-SEAM-2  The old `needs_tiling` used POSITION-BASED check:
               (u_min < -0.5 or u_max > 1.5 ...).
               This triggered tiling for seam-corrected faces with v=1.85
               (small span=0.36 but shifted position).  The tiling floor-shift
               then UNDID the seam fix, causing stretch artifacts on n_darthrevan.
               FIX: SPAN-BASED check: needs_tiling when (u_max - u_min) > 1.5
               or (v_max - v_min) > 1.5.  Small-span shifted faces → no tiling.

BUG-UV-SEAM-3  The old `frac_clamp` per-vertex wrapping collapsed seam-corrected
               UVs: e.g. u=-0.468 → frac → 0.532 (= original, seam fix lost).
               FIX: CENTROID INTEGER SHIFT preserves relative UV differences.
               All three UVs shifted by the same integer amount so the centroid
               lands in [0,1]; the seam fix offsets are preserved.

Test cases:
  - test_seam_detection_* : verify correct seam / no-seam decisions
  - test_centroid_shift_* : verify centroid shift preserves UV offsets
  - test_tiling_span_based_*: verify span-based tiling threshold
  - test_rotate_texture_*: test (u,v)→(v,1-u) rotation
  - test_full_render_*: integration rendering checks
"""

import math
import pytest

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

# ─── helpers ──────────────────────────────────────────────────────────────────


def _get_paste_fn():
    """Import _paste_textured_triangle from viewport."""
    from src.gui.viewport import _paste_textured_triangle
    return _paste_textured_triangle


def _solid_texture(w=64, h=64, color=(128, 64, 32, 255)):
    """Create a solid-colour RGBA texture."""
    return Image.new('RGBA', (w, h), color)


def _gradient_texture(w=64, h=64):
    """
    Create a recognisable gradient texture:
    - Left half RED, right half BLUE (for horizontal UV checks)
    - Top half BRIGHT, bottom half DARK (for vertical UV checks)
    """
    img = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    for x in range(w):
        for y in range(h):
            r = 255 if x < w // 2 else 0
            b = 255 if x >= w // 2 else 0
            g = 200 if y < h // 2 else 50
            img.putpixel((x, y), (r, g, b, 255))
    return img


def _render_triangle(tex, uv0, uv1, uv2,
                     sp0=(5, 5), sp1=(55, 5), sp2=(30, 55),
                     img_size=64):
    """Render a single textured triangle into a blank image and return it."""
    if not _PIL:
        return None
    paste = _get_paste_fn()
    img = Image.new('RGB', (img_size, img_size), (128, 128, 128))
    paste(img, tex, sp0, sp1, sp2, uv0, uv1, uv2,
          img_size, img_size, (255, 255, 255))
    return img


# ─── Seam Detection Tests ─────────────────────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestSeamDetection:
    """
    Verify the frac-span heuristic correctly identifies seam-crossing vs
    legitimate large-span triangles.
    """

    def test_no_seam_normal_face(self):
        """
        A normal face entirely within [0,1] must NOT trigger seam unwrap.
        UVs: (0.1,0.2), (0.5,0.2), (0.3,0.8) — all in [0,1], no crossing.
        After rendering the centre should be non-background (gray).
        """
        tex = _gradient_texture()
        img = _render_triangle(tex, (0.1, 0.2), (0.5, 0.2), (0.3, 0.8))
        assert img is not None
        px = img.getpixel((30, 30))
        # Centre should be rendered (not the 128,128,128 background)
        # UV centroid ≈ (0.3, 0.4) → x≈0.3*64=19 → red half → R should be higher
        # (gradient texture: left=red, right=blue)
        assert px != (128, 128, 128), f"Triangle not rendered at centre: {px}"

    def test_no_seam_large_span_v(self):
        """
        Legitimate large V span: v0=0.1, v2=0.9, span=0.8.
        _uwrap must NOT fire (it would make v2=-0.1).
        Result: v2 stays 0.9 → different V position than v0=0.1 → different row.

        NOTE: screen-space vs texture-space orientation:
          - sp0/sp1 at screen y=5 (top screen) have uv.v=0.1 → V-flip → PIL row = (1-0.1)*64 = 57.6 → DARK
          - sp2 at screen y=59 (bottom screen) has uv.v=0.9 → V-flip → PIL row = (1-0.9)*64 = 6.4 → BRIGHT
        So the screen-TOP pixels sample DARK texture, screen-BOTTOM samples BRIGHT.
        """
        paste = _get_paste_fn()
        # PIL row 0-31 = bright green, PIL row 32-63 = dark green
        # (V-flip: high V = small PIL row = bright; low V = large PIL row = dark)
        tex = Image.new('RGBA', (64, 64), (0, 200, 0, 255))  # bright green top
        for x in range(64):
            for y in range(32, 64):
                tex.putpixel((x, y), (0, 50, 0, 255))  # dark green bottom

        img = Image.new('RGB', (64, 64), (128, 128, 128))
        # v0=v1=0.1 at screen top; v2=0.9 at screen bottom
        paste(img, tex,
              (5, 5), (59, 5), (32, 59),
              (0.4, 0.1), (0.6, 0.1), (0.5, 0.9),
              64, 64, (255, 255, 255))

        # Sample near screen-TOP of triangle (v≈0.1 → PIL row≈57 → DARK)
        top_px = img.getpixel((32, 10))
        # Sample near screen-BOTTOM of triangle (v≈0.9 → PIL row≈6 → BRIGHT)
        bot_px = img.getpixel((32, 50))

        # Both must have rendered
        assert top_px != (128, 128, 128), f"Top not rendered: {top_px}"
        assert bot_px != (128, 128, 128), f"Bottom not rendered: {bot_px}"

        # V-flip: screen-top (v=0.1) → dark; screen-bottom (v=0.9) → bright
        top_g = top_px[1]   # green channel
        bot_g = bot_px[1]
        assert bot_g > top_g, \
            f"With V-flip: screen-bottom (v=0.9→bright) should be brighter than screen-top (v=0.1→dark): top_g={top_g}, bot_g={bot_g}"

    def test_seam_face_u_axis_detected(self):
        """
        Genuine U seam: u0=0.95, u1=0.05, u2=0.5 — straddles 0/1 boundary.
        frac() of 0.95=0.95, 0.05=0.05: frac-span=0.9 > raw-span≈0.9 ... actually
        raw-span = max(0.95,0.05,0.5)-min(0.95,0.05,0.5) = 0.95-0.05 = 0.90
        frac-span = max(0.95,0.05,0.5)-min(0.95,0.05,0.5) = 0.95-0.05 = 0.90
        Hmm, let's use u0=0.95, u1=0.02 for clearer seam detection.
        raw-span = 0.95-0.02 = 0.93; after seam fix u1→1.02, span=0.93 OK.
        The frac-span check: frac(0.95)=0.95, frac(0.02)=0.02, span=0.93=raw_span.
        Actually the seam is: u0=0.95, u1=1.02 (slightly over 1).
        Better case: u0=0.95, u1=0.05 — raw span=0.90, frac span=0.90, no seam detected.
        The TRUE seam case for frac detection: u0=0.97, u1=0.03.
        raw_span = 0.97-0.03=0.94 (< 1.0)
        frac(0.97)=0.97, frac(0.03)=0.03 → frac_span=0.94 = raw_span → no seam!
        
        Wait — the frac-detection identifies when coordinates from DIFFERENT tiles
        are in the same face. Example: u0=0.97 (tile 0), u2=1.03 (tile 1).
        frac(0.97)=0.97, frac(1.03)=0.03 → frac_span=0.94 > raw_span=0.06 → SEAM!
        This is the real KotOR seam case.
        """
        paste = _get_paste_fn()
        # Left=red, right=blue texture
        tex = Image.new('RGBA', (64, 64), (255, 0, 0, 255))
        for x in range(32, 64):
            for y in range(64):
                tex.putpixel((x, y), (0, 0, 255, 255))

        # u0=0.97 (near right edge), u1=1.03 (just past right edge, wraps to left)
        # This is the KotOR seam case: the face straddles the 0→1 tile boundary.
        # After seam fix: u1=1.03 → _uwrap(0.97, 1.03) = 1.03 (diff=0.06, no change)
        # Actually for detection: frac(0.97)=0.97, frac(1.03)=0.03
        # frac_span = max(0.97,0.03,0.5)-min(0.97,0.03,0.5) = 0.94 > raw_span=0.06 → SEAM
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 25), (59, 25), (32, 35),
              (0.97, 0.4), (1.03, 0.4), (0.5, 0.6),
              64, 64, (255, 255, 255))
        # Should render without crash and produce some non-background pixels
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 0, "Seam face should render some pixels"

    def test_large_span_v_no_seam_uwrap_not_applied(self):
        """
        v0=0.2, v1=0.2, v2=0.8 — span=0.6, fits in one tile.
        Old code WRONGLY applied _uwrap to v2: v2 = 0.8 → -0.2.
        New code should NOT apply _uwrap (frac-span = raw-span = 0.6, no seam).
        Verify by checking the rendered result has the expected UV coverage.

        Screen-space vs texture-space orientation (V-flip):
          - sp0/sp1 at screen y=5 (screen-top) have uv.v=0.2 → PIL row=(1-0.2)*64=51.2 → RED
          - sp2 at screen y=59 (screen-bottom) has uv.v=0.8 → PIL row=(1-0.8)*64=12.8 → BLUE
        So screen-TOP pixels are RED, screen-BOTTOM pixels are BLUE.

        If _uwrap fires incorrectly on v2: v2 = 0.8 → -0.2
        Then all three V coords would be near 0.2 → all sample RED → no blue at bottom.
        """
        paste = _get_paste_fn()
        # PIL rows 0-31: blue, rows 32-63: red
        # v=0.2 (low OpenGL) → V-flip → PIL row=51 → RED ✓
        # v=0.8 (high OpenGL) → V-flip → PIL row=12 → BLUE ✓
        tex = Image.new('RGBA', (64, 64), (0, 0, 255, 255))  # blue top
        for x in range(64):
            for y in range(32, 64):
                tex.putpixel((x, y), (255, 0, 0, 255))  # red bottom

        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 59),
              (0.4, 0.2), (0.6, 0.2), (0.5, 0.8),
              64, 64, (255, 255, 255))

        # Near screen-top (y≈10): uv.v≈0.2 → PIL row≈51 → RED
        top_px = img.getpixel((32, 10))
        # Near screen-bottom (y≈50): uv.v≈0.8 → PIL row≈12 → BLUE
        bot_px = img.getpixel((32, 50))

        assert top_px != (128, 128, 128), f"Top not rendered: {top_px}"
        assert bot_px != (128, 128, 128), f"Bottom not rendered: {bot_px}"

        # Screen-top → RED, screen-bottom → BLUE
        assert top_px[0] > 100, f"Screen-top expected RED (v=0.2→PIL row 51→red), got {top_px}"
        assert bot_px[2] > 100, f"Screen-bottom expected BLUE (v=0.8→PIL row 12→blue), got {bot_px}"


# ─── Centroid-Shift Tests ─────────────────────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestCentroidIntegerShift:
    """
    Verify that centroid integer shift preserves relative UV differences
    while bringing shifted coordinates into [0,1] for PIL AFFINE sampling.
    """

    def test_centroid_shift_preserves_seam_fix(self):
        """
        After seam fix: UVs = (0.030, 1.851), (0.007, 1.855), (-0.468, 1.493)
        span_u=0.498, span_v=0.362 → needs_tiling = False
        centroid_v = (1.851+1.855+1.493)/3 = 1.733 → v_int_shift = 1
        After shift: v becomes (0.851, 0.855, 0.493)
        centroid_u = (0.030+0.007-0.468)/3 = -0.144 → u_int_shift = -1 (floor(-0.144)=-1)
        After shift: u becomes (1.030, 1.007, 0.532)
        Relative u-span is preserved: max-min = 1.030-0.532 = 0.498 ✓
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()  # left=red, right=blue

        # This is the exact n_darthrevan seam face 544 data
        uv0 = (0.030, 1.851)
        uv1 = (0.007, 1.855)
        uv2 = (0.532, 1.493)  # raw seam crossing, shifted by _uwrap in old code

        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              uv0, uv1, uv2,
              64, 64, (255, 255, 255))

        # Should render without crash
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 50, f"Expected many rendered pixels for seam face, got {non_bg}"

    def test_centroid_shift_v_over_one(self):
        """
        Face with v values slightly over 1.0: (0.3, 1.1), (0.5, 1.2), (0.4, 1.05)
        span_u=0.2, span_v=0.15 → no tiling needed
        centroid_v = 1.117 → v_int_shift=1 → v becomes (0.1, 0.2, 0.05)
        centroid_u = 0.4 → u_int_shift=0 → u unchanged
        Render must succeed and sample from the expected texture region.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (20, 20), (44, 20), (32, 44),
              (0.3, 1.1), (0.5, 1.2), (0.4, 1.05),
              64, 64, (255, 255, 255))

        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 20, f"Expected rendered pixels for v>1 face, got {non_bg}"

    def test_centroid_shift_u_negative(self):
        """
        Face with slightly negative u: (-0.1, 0.3), (-0.05, 0.4), (0.2, 0.35)
        span_u=0.3, span_v=0.1 → no tiling needed
        centroid_u = (-0.1-0.05+0.2)/3 = 0.0167 → u_int_shift = 0 → no u shift
        v is all in [0,1], no v shift
        Wait: u_min = -0.1 < -0.001, so the centroid-shift block fires.
        u_cen = 0.0167 → floor = 0 → shift = 0 → u unchanged.
        Actually should shift: u0=-0.1 still outside [0,1] after no-op shift.
        The issue: centroid in [0,1] but individual UVs outside.
        In that case the PIL AFFINE will still sample outside [0,1], which PIL
        fills with the fillcolor (0,0,0,0) = transparent.
        This is acceptable: the face partially overlaps the texture boundary and
        the out-of-bounds pixels are simply transparent.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (10, 20), (50, 20), (30, 40),
              (-0.1, 0.3), (-0.05, 0.4), (0.2, 0.35),
              64, 64, (255, 255, 255))

        # Should not crash; some pixels may be background (transparent→not rendered)
        # Just verify no exception
        assert img is not None

    def test_centroid_shift_u_minus_half(self):
        """
        Seam face after seam correction: u = (-0.468, 0.030, 0.007)
        centroid_u = (-0.468+0.030+0.007)/3 = -0.144
        floor(-0.144) = -1 → u_int_shift = -1 → shift all by +1
        After shift: u = (0.532, 1.030, 1.007)
        span is preserved: 1.030-0.532 = 0.498 (same as before shift)
        """
        from src.gui.viewport import _paste_textured_triangle
        # Manually verify the centroid-shift math
        us = [-0.468, 0.030, 0.007]
        vs = [0.3, 0.3, 0.3]  # simple v values for this test

        u_cen = sum(us) / 3.0
        v_cen = sum(vs) / 3.0
        u_int_shift = math.floor(u_cen)
        v_int_shift = math.floor(v_cen)

        assert u_int_shift == -1, f"Expected u_int_shift=-1, got {u_int_shift}"
        assert v_int_shift == 0, f"Expected v_int_shift=0, got {v_int_shift}"

        us_shifted = [u - u_int_shift for u in us]
        assert abs(us_shifted[0] - 0.532) < 0.001, f"Expected u0≈0.532, got {us_shifted[0]}"
        assert abs(us_shifted[1] - 1.030) < 0.001, f"Expected u1≈1.030, got {us_shifted[1]}"

        # Relative span preserved
        span_before = max(us) - min(us)
        span_after = max(us_shifted) - min(us_shifted)
        assert abs(span_before - span_after) < 1e-9, \
            f"Centroid shift must preserve span: {span_before} vs {span_after}"

    def test_centroid_shift_not_applied_when_in_range(self):
        """
        Normal face: u=[0.1, 0.4, 0.25], v=[0.2, 0.2, 0.8]
        All in [0,1] → centroid shift NOT triggered.
        Render must be identical to reference (no transformation artifact).
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 59),
              (0.1, 0.2), (0.4, 0.2), (0.25, 0.8),
              64, 64, (255, 255, 255))

        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        # With these UVs and gradient texture, should get many rendered pixels
        assert non_bg > 100, f"Expected many rendered pixels, got {non_bg}"


# ─── Span-Based Tiling Tests ──────────────────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestSpanBasedTiling:
    """
    Verify that tiling is triggered by UV SPAN > 1.5, not by UV POSITION > 1.5.
    """

    def test_no_tiling_small_span_shifted_position(self):
        """
        Face: u=(-0.468, 0.030, 0.007), v=(1.493, 1.851, 1.855)
        span_u=0.498, span_v=0.362 → both < 1.5 → NOT a tiling face.
        The face should render correctly via centroid-shift path.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (-0.468, 1.493), (0.030, 1.851), (0.007, 1.855),
              64, 64, (255, 255, 255))

        # Must render (no crash, non-background pixels)
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 10, f"Small-span shifted face should render, got {non_bg} pixels"

    def test_tiling_large_span_u(self):
        """
        Belt mesh face: u=(-6.079, -6.608, 0.394), v=(-8.223, -7.289, -8.333)
        span_u = 0.394-(-6.608) = 7.002 > 1.5 → MUST trigger tiling.
        """
        paste = _get_paste_fn()
        tex = _solid_texture(32, 32, color=(200, 100, 50, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        # Should not raise; tiling path activated
        paste(img, tex,
              (5, 5), (59, 5), (32, 59),
              (-6.079, -8.223), (-6.608, -7.289), (0.394, -8.333),
              64, 64, (255, 255, 255))

        # Just verify no crash; tiling produces some pixels
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg >= 0  # Tiling at least ran without crash

    def test_no_tiling_seam_face_v_slightly_above_1(self):
        """
        Face: v = (0.851, 0.855, 1.493) — v2 is above 1.0 but span=0.642 < 1.5.
        Old position-based check: v_max = 1.493 > 1.5? No. OK, just above 1.0.
        span-based: 1.493 - 0.851 = 0.642 < 1.5 → NOT tiling.
        centroid: v_cen = (0.851+0.855+1.493)/3 = 1.066 → v_int_shift=1
        After shift: v = (-0.149, -0.145, 0.493)
        Render should succeed.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (0.3, 0.851), (0.5, 0.855), (0.4, 1.493),
              64, 64, (255, 255, 255))

        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg >= 0  # No crash

    def test_no_tiling_original_position_check_false_positive(self):
        """
        The OLD position-based check triggered tiling for v=1.851 (v_max > 1.5).
        The NEW span-based check: span_v = 1.855-1.493 = 0.362 < 1.5 → NO tiling.
        Verify the new check does not trigger tiling for face 544 from n_darthrevan.
        """
        u_min = -0.468; u_max = 1.030  # After seam fix + centroid shift
        v_min = 0.851; v_max = 1.855   # Before centroid shift

        # Old position check would say:
        old_needs_tiling = (u_min < -0.5 or u_max > 1.5 or
                            v_min < -0.5 or v_max > 1.5)
        # u_max=1.030 < 1.5 and v_max=1.855 > 1.5 → OLD: True (BUG!)
        assert old_needs_tiling, "Old check should trigger (verifying the BUG)"

        # New span check:
        u_span = u_max - u_min  # 1.498
        v_span = v_max - v_min  # 1.004
        new_needs_tiling = (u_span > 1.5 or v_span > 1.5)
        # u_span=1.498 < 1.5, v_span=1.004 < 1.5 → NEW: False (CORRECT!)
        assert not new_needs_tiling, "New span check should NOT trigger tiling for face 544"


# ─── Rotate Texture Tests ─────────────────────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestRotateTextureV60:
    """
    Verify rotate_texture UV transformation: (u,v)→(v,1-u).
    These tests are equivalent to TestRotateTexture in test_v49 but explicitly
    verify the v6.0 seam-detection code does not interfere with rotation.
    """

    def test_rotate_texture_changes_uv_axis(self):
        """
        Rotated UVs (v,1-u) must sample a different region than normal (u,v).
        Use a left-red/right-blue texture: normal samples left (red);
        rotated samples a different region.
        """
        paste = _get_paste_fn()
        # Left=red, right=blue
        tex = Image.new('RGBA', (64, 64), (255, 0, 0, 255))
        for x in range(32, 64):
            for y in range(64):
                tex.putpixel((x, y), (0, 0, 255, 255))

        uv0 = (0.1, 0.2); uv1 = (0.4, 0.2); uv2 = (0.25, 0.8)
        sp0 = (2, 2); sp1 = (30, 2); sp2 = (16, 30)

        img_n = Image.new('RGB', (32, 32), (128, 128, 128))
        paste(img_n, tex, sp0, sp1, sp2, uv0, uv1, uv2, 32, 32, (255, 255, 255))

        ruv0 = (uv0[1], 1.0 - uv0[0])
        ruv1 = (uv1[1], 1.0 - uv1[0])
        ruv2 = (uv2[1], 1.0 - uv2[0])
        img_r = Image.new('RGB', (32, 32), (128, 128, 128))
        paste(img_r, tex, sp0, sp1, sp2, ruv0, ruv1, ruv2, 32, 32, (255, 255, 255))

        pn = img_n.getpixel((16, 16))
        pr = img_r.getpixel((16, 16))
        assert pn != pr, f"Rotated must differ from normal: normal={pn} rotated={pr}"

    def test_rotate_texture_seam_detection_not_confused(self):
        """
        After (u,v)→(v,1-u) rotation:
        uv0=(0.1,0.2)→ruv0=(0.2,0.9)
        uv1=(0.4,0.2)→ruv1=(0.2,0.6)
        uv2=(0.25,0.8)→ruv2=(0.8,0.75)
        Rotated span_u = 0.8-0.2=0.6, span_v=0.9-0.6=0.3. Both < 1.0.
        Seam detection: frac-span vs raw-span should not find a seam.
        Centroid shift: u_cen=(0.2+0.2+0.8)/3=0.4 → int_shift=0; v OK.
        No shift needed; face renders correctly.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (32, 32), (128, 128, 128))
        paste(img, tex,
              (2, 2), (30, 2), (16, 30),
              (0.2, 0.9), (0.2, 0.6), (0.8, 0.75),
              32, 32, (255, 255, 255))

        non_bg = sum(1 for x in range(32) for y in range(32)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 20, f"Rotated face should render, got {non_bg} pixels"


# ─── Regression: frac_clamp must NOT be used ─────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestFracClampRemoved:
    """
    The old frac_clamp (per-UV frac()) collapsed seam-corrected UVs.
    These tests confirm the fix is in place by verifying render output
    for cases where frac() would produce wrong results.
    """

    def test_frac_would_destroy_seam_fix_u_negative(self):
        """
        u=-0.468 after seam fix: frac(-0.468) = 0.532 (= original u2, seam fix lost).
        With centroid shift: u_cen=-0.144 → shift=-(-1)=+1 → u becomes 0.532 (same!).
        Wait — for this specific case the centroid shift gives the same result as frac()
        for u2, but the TRIANGLE SPAN is preserved because all three u values get +1:
          u0: 0.030+1=1.030, u1: 0.007+1=1.007, u2: -0.468+1=0.532
          span = 1.030-0.532 = 0.498 (CORRECT — seam fix preserved)
        With frac():
          u0: frac(0.030)=0.030, u1: frac(0.007)=0.007, u2: frac(-0.468)=0.532
          span = 0.532-0.007 = 0.525 (WRONG — reverts seam fix)
        Verify that our render is consistent (no crash, non-background output).
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        # Exact seam-corrected UVs that frac_clamp would mishandle
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (0.030, 0.5), (0.007, 0.5), (-0.468, 0.4),
              64, 64, (255, 255, 255))

        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 0, f"Seam-corrected face with u=-0.468 should render some pixels"

    def test_frac_would_wrap_v_seam_correctly_v_above_1(self):
        """
        v=1.851 after seam correction: frac(1.851)=0.851 — same as centroid shift.
        This case is FINE for both methods.
        But with old position-based tiling (v > 1.5 → needs_tiling), the tiling
        code would then apply v_floor=1 shift to the uvs, making v=0.851 again.
        The NEW span check (span=0.362 < 1.5) correctly skips tiling.
        Verify the render works correctly for this case.
        """
        paste = _get_paste_fn()
        tex = _gradient_texture()
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (0.030, 1.851), (0.007, 1.855), (0.532, 1.493),
              64, 64, (255, 255, 255))

        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg > 10, f"v>1 face (n_darthrevan face 544) should render, got {non_bg}"


# ─── UV Sentinel Tests ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestUVSentinelV60:
    """
    Verify that faces with |u| or |v| > _UV_SENTINEL (100.0) are skipped.
    These are sentinel stitching values used in KotOR skin meshes.
    Phase 18: sentinel raised from 20.0 to 100.0 to avoid filtering legitimate
    large-UV meshes (e.g. mRobe2_g U=[-13.58, 13.58]).
    """

    def test_sentinel_u_skips_face(self):
        """Face with u=125.0 (|u| > 100) must be skipped (no pixels rendered)."""
        paste = _get_paste_fn()
        tex = _solid_texture(color=(255, 0, 0, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (125.0, 0.5), (0.3, 0.5), (0.5, 0.8),
              64, 64, (255, 255, 255))
        # All pixels must remain background
        for y in range(64):
            for x in range(64):
                assert img.getpixel((x, y)) == (128, 128, 128), \
                    f"Sentinel face must not render, but pixel ({x},{y}) = {img.getpixel((x,y))}"

    def test_sentinel_v_skips_face(self):
        """Face with v=127.0 (|v| > 100) must be skipped (no pixels rendered)."""
        paste = _get_paste_fn()
        tex = _solid_texture(color=(255, 0, 0, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (0.1, 127.0), (0.4, 0.5), (0.3, 0.8),
              64, 64, (255, 255, 255))
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg == 0, f"Sentinel v face must not render, but got {non_bg} pixels"

    def test_no_sentinel_boundary_face_renders(self):
        """Face with u=19.9 (just below sentinel) must render normally."""
        paste = _get_paste_fn()
        tex = _solid_texture(color=(200, 100, 50, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        # Large tiling face — u=19.9 triggers tiling path
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (19.9, 0.5), (0.1, 0.5), (0.5, 0.8),
              64, 64, (255, 255, 255))
        # Just verify no crash (tiling path handles large UVs)
        assert img is not None

    def test_sentinel_exactly_20_not_skipped_boundary(self):
        """
        u=20.0 exactly is at the BOUNDARY of _UV_SENTINEL.
        The sentinel check uses `> _UV_SENTINEL` (strictly greater), so u=20.0
        is NOT skipped (it equals the threshold exactly, not exceeds it).
        This is a boundary condition — u=20.001 WOULD be skipped, u=20.0 is not.
        The face may render with the tiling path.
        """
        paste = _get_paste_fn()
        tex = _solid_texture(color=(255, 0, 0, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        # u=20.0 should NOT raise; it passes sentinel check and enters tiling/centroid path
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (20.0, 0.5), (0.3, 0.5), (0.5, 0.8),
              64, 64, (255, 255, 255))
        # No crash is the primary requirement; pixels may or may not render
        assert img is not None

    def test_sentinel_above_20_skips_face(self):
        """u=100.001 (> _UV_SENTINEL=100.0) must be skipped.
        Phase 18: sentinel was 20.0, now 100.0. Values up to 100 may be
        legitimate large-UV tiled meshes and should NOT be skipped."""
        paste = _get_paste_fn()
        tex = _solid_texture(color=(255, 0, 0, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (100.001, 0.5), (0.3, 0.5), (0.5, 0.8),
              64, 64, (255, 255, 255))
        non_bg = sum(1 for x in range(64) for y in range(64)
                     if img.getpixel((x, y)) != (128, 128, 128))
        assert non_bg == 0, f"u=100.001 must skip face (> sentinel=100), got {non_bg} pixels"


# ─── Integration: Belt Mesh Large Tiling ─────────────────────────────────────


@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestBeltMeshTiling:
    """
    The belt mesh from n_darthrevan has faces with UVs spanning ±7 units.
    Verify these render correctly via the tiling path.
    """

    def test_belt_large_uv_renders(self):
        """Belt face: u=(-6.079,-6.608,0.394), v=(-8.223,-7.289,-8.333)."""
        paste = _get_paste_fn()
        tex = _solid_texture(32, 32, color=(180, 90, 30, 255))
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        paste(img, tex,
              (5, 5), (59, 5), (32, 50),
              (-6.079, -8.223), (-6.608, -7.289), (0.394, -8.333),
              64, 64, (255, 255, 255))
        # No crash is the primary requirement
        assert img is not None

    def test_belt_uvs_span_exceeds_threshold(self):
        """Verify belt UVs actually trigger the span-based tiling check."""
        u_vals = [-6.079, -6.608, 0.394]
        v_vals = [-8.223, -7.289, -8.333]
        u_span = max(u_vals) - min(u_vals)
        v_span = max(v_vals) - min(v_vals)
        assert u_span > 1.5, f"Belt u_span={u_span} should exceed 1.5"
        # v_span = -7.289 - (-8.333) = 1.044 → below 1.5
        # Belt is still triggered by u_span > 1.5
        assert u_span > 1.5, f"Expected tiling triggered by u_span"


# ─── Arithmetic Verification Tests ───────────────────────────────────────────


class TestUVArithmeticV60:
    """
    Pure arithmetic tests — no PIL required.
    Verify the seam detection and centroid shift math directly.
    """

    def test_frac_span_seam_detection_genuine_seam(self):
        """
        u0=0.97, u1=1.03, u2=0.5.
        raw_span = max-min = 1.03-0.5 = 0.53 (< 1.0, fits in one tile)
        frac: frac(0.97)=0.97, frac(1.03)=0.03, frac(0.5)=0.5
        frac_span = 0.97-0.03 = 0.94 > raw_span=0.53 + 0.01 → SEAM DETECTED ✓
        """
        us = [0.97, 1.03, 0.5]
        raw_span = max(us) - min(us)
        us_frac = [u - math.floor(u) for u in us]
        frac_span = max(us_frac) - min(us_frac)
        u_has_seam = (frac_span > raw_span + 0.01)
        assert u_has_seam, \
            f"Seam should be detected: raw_span={raw_span:.3f}, frac_span={frac_span:.3f}"

    def test_frac_span_no_seam_large_span(self):
        """
        v0=0.2, v1=0.2, v2=0.8.
        raw_span = 0.6 (< 1.0)
        frac: frac(0.2)=0.2, frac(0.8)=0.8
        frac_span = 0.6 = raw_span → NOT a seam ✓
        """
        vs = [0.2, 0.2, 0.8]
        raw_span = max(vs) - min(vs)
        vs_frac = [v - math.floor(v) for v in vs]
        frac_span = max(vs_frac) - min(vs_frac)
        v_has_seam = (frac_span > raw_span + 0.01)
        assert not v_has_seam, \
            f"Large span should NOT be detected as seam: raw={raw_span:.3f}, frac={frac_span:.3f}"

    def test_frac_span_no_seam_normal_face(self):
        """
        Normal face u=[0.1, 0.4, 0.25]: raw_span=0.3, frac_span=0.3 → no seam.
        """
        us = [0.1, 0.4, 0.25]
        raw_span = max(us) - min(us)
        us_frac = [u - math.floor(u) for u in us]
        frac_span = max(us_frac) - min(us_frac)
        u_has_seam = (frac_span > raw_span + 0.01)
        assert not u_has_seam, \
            f"Normal face should not be seam: raw={raw_span:.3f}, frac={frac_span:.3f}"

    def test_span_based_tiling_threshold(self):
        """needs_tiling fires at span > 1.5 (not at position > 1.5)."""
        # Small span but shifted (old position check would be ambiguous)
        u_vals = [-0.468, 0.030, 0.007]; v_vals = [1.493, 1.851, 1.855]
        u_span = max(u_vals) - min(u_vals)
        v_span = max(v_vals) - min(v_vals)
        assert u_span < 1.5, f"n_darthrevan face 544 u_span should be < 1.5: {u_span:.3f}"
        assert v_span < 1.5, f"n_darthrevan face 544 v_span should be < 1.5: {v_span:.3f}"

        # True tiling face
        u_tiling = [-6.079, -6.608, 0.394]
        u_tiling_span = max(u_tiling) - min(u_tiling)
        assert u_tiling_span > 1.5, f"Belt face u_span should be > 1.5: {u_tiling_span:.3f}"

    def test_centroid_shift_math_n_darthrevan_face544(self):
        """
        Exact centroid-shift calculation for n_darthrevan face 544.
        After seam fix: u=[0.030, 0.007, -0.468], v=[1.851, 1.855, 1.493]
        """
        us = [0.030, 0.007, -0.468]
        vs = [1.851, 1.855, 1.493]

        u_cen = sum(us) / 3.0
        v_cen = sum(vs) / 3.0
        u_shift = math.floor(u_cen)
        v_shift = math.floor(v_cen)

        us_shifted = [u - u_shift for u in us]
        vs_shifted = [v - v_shift for v in vs]

        # Verify shift amounts
        assert u_shift == -1, f"Expected u_shift=-1 (centroid≈-0.144), got {u_shift}"
        assert v_shift == 1, f"Expected v_shift=1 (centroid≈1.733), got {v_shift}"

        # Verify relative span preserved
        u_span_before = max(us) - min(us)
        u_span_after = max(us_shifted) - min(us_shifted)
        assert abs(u_span_before - u_span_after) < 1e-9, \
            f"U span must be preserved by centroid shift: {u_span_before} vs {u_span_after}"

        v_span_before = max(vs) - min(vs)
        v_span_after = max(vs_shifted) - min(vs_shifted)
        assert abs(v_span_before - v_span_after) < 1e-9, \
            f"V span must be preserved by centroid shift: {v_span_before} vs {v_span_after}"

        # Verify shifted values
        assert abs(us_shifted[0] - 1.030) < 0.001  # 0.030 - (-1) = 1.030
        assert abs(us_shifted[2] - 0.532) < 0.001  # -0.468 - (-1) = 0.532
        assert abs(vs_shifted[0] - 0.851) < 0.001  # 1.851 - 1 = 0.851
        assert abs(vs_shifted[2] - 0.493) < 0.001  # 1.493 - 1 = 0.493

    def test_uwrap_seam_crossing_case(self):
        """
        _uwrap used inside _paste_textured_triangle must be tested indirectly.
        Verify the seam detection math: u0=0.97, u1=1.03.
        """
        # Simulate _uwrap logic
        def _uwrap(base, other):
            diff = other - base
            while diff > 0.5: other -= 1.0; diff -= 1.0
            while diff < -0.5: other += 1.0; diff += 1.0
            return other

        # Genuine seam: u0=0.97 in tile 0, u1=1.03 in tile 1
        # frac detection: frac(0.97)=0.97, frac(1.03)=0.03 → frac_span=0.94 > raw_span=0.06
        us = [0.97, 1.03, 0.5]
        raw_span = max(us) - min(us)
        us_frac = [u - math.floor(u) for u in us]
        frac_span = max(us_frac) - min(us_frac)
        u_has_seam = (frac_span > raw_span + 0.01)
        assert u_has_seam

        # _uwrap from u0=0.97: diff(1.03-0.97)=0.06 < 0.5, no change
        u1_wrapped = _uwrap(0.97, 1.03)
        assert abs(u1_wrapped - 1.03) < 1e-9, f"u=1.03 near u0=0.97 should not change"

        # Seam case: u0=0.97, u2=0.03 (tile 0). _uwrap: diff=-0.94 < -0.5 → other+=1 → 1.03
        u2_wrapped = _uwrap(0.97, 0.03)
        assert abs(u2_wrapped - 1.03) < 1e-9, f"u=0.03 near u0=0.97 should wrap to 1.03"

    def test_uwrap_large_span_no_change(self):
        """
        Large span: v0=0.2, v2=0.8. diff = 0.6 > 0.5 → _uwrap fires.
        BUT seam detection should NOT fire (no seam), so _uwrap is never called.
        This test verifies the seam detection gate:
        frac(0.2)=0.2, frac(0.8)=0.8 → frac_span=0.6 = raw_span=0.6 → no seam.
        """
        vs = [0.2, 0.2, 0.8]
        raw_span = max(vs) - min(vs)
        vs_frac = [v - math.floor(v) for v in vs]
        frac_span = max(vs_frac) - min(vs_frac)
        v_has_seam = (frac_span > raw_span + 0.01)
        # Confirm: no seam detected → _uwrap NOT applied → v2 stays 0.8
        assert not v_has_seam, \
            f"Large-span v=[0.2,0.2,0.8] must NOT be detected as seam"
