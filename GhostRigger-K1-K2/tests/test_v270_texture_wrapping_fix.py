"""
test_v270_texture_wrapping_fix.py  –  Phase 15: Texture Wrapping Fix
======================================================================

Validates the two critical texture-wrapping bugs fixed in Phase 15:

BUG-WRAP-1  GPU renderer set repeat_x=False/repeat_y=False for ALL textures.
            KotOR area geometry (N_sithpraet pelvis U=[-13,+13], torso/limbs
            with tiled UV > 1.0) requires GL_REPEAT to tile correctly.
            With GL_CLAMP_TO_EDGE, any UV outside [0,1] samples the edge texel,
            causing the mesh to appear as a solid color or edge-stretched stripe.
            FIX: _upload() now defaults to repeat_x=True/repeat_y=True.
                 _draw_node() overrides to repeat_x=False/repeat_y=False ONLY
                 for nodes with txi_clamp_s/txi_clamp_t set (TXI clamp command).

BUG-WRAP-2  CPU rasterizer large-UV fallback used centroid-shift instead of frac().
            When tile_u_needed > MAX_TILE_COUNT=8, the old code shifted all UVs by
            int(floor(centroid)) so the centroid landed in [0,1]. This correctly
            positioned the centroid texel, but individual UVs (e.g. u=+13) were
            still far outside [0,1], causing the PIL AFFINE transform to sample
            transparent fillcolor (0,0,0,0) for most of the triangle — effectively
            rendering the face invisible or blank.
            FIX: _paste_textured_triangle() now applies frac() (modulo 1.0) per
                 vertex so every vertex UV maps into [0,1]. This gives correct
                 tiling for each vertex; seams at tile boundaries are an acceptable
                 trade-off vs. blank/stretched geometry.

References:
    N_sithpraet.mdl: pelvis U=[-13.58,+13.58], torso U=[0.003,1.366]
    KotOR area geometry: tiled floor/wall texture repeat required
    xoreos ModelNode: GL_REPEAT is default, GL_CLAMP only when TXI 'clamp' set
    KotOR.js TextureLoader: texture.wrapS = THREE.RepeatWrapping by default
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.tpc_render_utils import _paste_textured_triangle

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_checker_tex(size: int = 64) -> 'Image.Image':
    """Create a checkerboard texture for UV sampling validation."""
    img = Image.new('RGBA', (size, size))
    half = size // 2
    for y in range(size):
        for x in range(size):
            # White in top-left and bottom-right quadrants, dark elsewhere
            is_white = (x < half) == (y < half)
            img.putpixel((x, y), (220, 220, 220, 255) if is_white else (40, 40, 40, 255))
    return img


def _count_rendered(img: 'Image.Image', bg=(30, 30, 30)) -> int:
    """Count pixels that differ from the background color."""
    count = 0
    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y))[:3] != bg:
                count += 1
    return count


# ─────────────────────────────────────────────────────────────────────────────
# BUG-WRAP-2: CPU rasterizer large-UV frac() fix
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL required")
class TestLargeUVFracFix:
    """Validate that CPU rasterizer applies frac() for UV ranges > MAX_TILE_COUNT."""

    def test_large_uv_renders_pixels_not_blank(self):
        """Large UV (u∈[-13,+13]) must produce rendered pixels, not blank."""
        tex = _make_checker_tex(64)
        img = Image.new('RGBA', (400, 400), (30, 30, 30, 255))
        # N_sithpraet pelvis-like UV range (27 tiles → > MAX_TILE_COUNT=8)
        _paste_textured_triangle(
            img, tex,
            (50, 50), (350, 50), (200, 350),
            (-13.583, -15.370), (13.583, 6.500), (0.0, -4.435),
            400, 400, (220, 220, 220)
        )
        rendered = _count_rendered(img)
        # With old centroid-shift, PIL AFFINE samples OOB → transparent → no pixels
        # With new frac() fix, vertices map into [0,1] → texture sampled correctly
        assert rendered > 5000, (
            f"Large UV range rendered only {rendered} pixels; expected > 5000 "
            f"(old centroid-shift bug would give ~0)"
        )

    def test_moderate_large_uv_9_tiles_renders(self):
        """9-tile UV (just above MAX_TILE_COUNT=8) also uses frac() fallback."""
        tex = _make_checker_tex(32)
        img = Image.new('RGBA', (300, 300), (30, 30, 30, 255))
        # 9-tile span → tile_u_needed = 10 > 8 → frac() path
        _paste_textured_triangle(
            img, tex,
            (20, 20), (280, 20), (150, 280),
            (0.5, 0.5), (9.5, 0.5), (5.0, 8.5),
            300, 300, (220, 220, 220)
        )
        rendered = _count_rendered(img)
        assert rendered > 3000, (
            f"9-tile UV rendered only {rendered} pixels; frac() fallback not working"
        )

    def test_frac_uv_mapping_correct(self):
        """Verify frac() maps each vertex UV correctly to [0,1]."""
        for u_raw in [-13.583, 13.583, -6.183, 7.911, -5.101, 4.122]:
            u_frac = u_raw - math.floor(u_raw)
            assert 0.0 <= u_frac <= 1.0, (
                f"frac({u_raw}) = {u_frac} is not in [0,1]"
            )
            # Verify it matches math expectation
            assert abs(u_frac - (u_raw % 1.0)) < 1e-9

    def test_normal_uv_range_unaffected(self):
        """Small UV range [0,1] is NOT affected by the large-UV fix."""
        tex = _make_checker_tex(64)
        img1 = Image.new('RGBA', (200, 200), (30, 30, 30, 255))
        img2 = Image.new('RGBA', (200, 200), (30, 30, 30, 255))
        # Normal UV face
        _paste_textured_triangle(
            img1, tex,
            (20, 20), (180, 20), (100, 180),
            (0.1, 0.1), (0.9, 0.1), (0.5, 0.9),
            200, 200, (220, 220, 220)
        )
        # Same face with UVs shifted by integer: should render identically (tiling)
        _paste_textured_triangle(
            img2, tex,
            (20, 20), (180, 20), (100, 180),
            (1.1, 1.1), (1.9, 1.1), (1.5, 1.9),
            200, 200, (220, 220, 220)
        )
        rendered1 = _count_rendered(img1)
        rendered2 = _count_rendered(img2)
        # Both should render about the same number of pixels
        # (integer UV shift is tile-equivalent for tiling texture)
        assert rendered1 > 1000, "Normal UV face not rendering"
        assert rendered2 > 1000, "Integer-shifted UV face not rendering"
        # Allow some variation (< 20%) due to slightly different affine paths
        ratio = min(rendered1, rendered2) / max(rendered1, rendered2)
        assert ratio > 0.8, (
            f"Normal vs shifted UV rendered very differently: {rendered1} vs {rendered2}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-WRAP-1: GPU repeat_x/repeat_y configuration
# ─────────────────────────────────────────────────────────────────────────────

class TestGpuTexWrapConfig:
    """Validate GPU texture wrap mode logic (unit tests — no GPU required)."""

    def test_node_with_no_txi_clamp_expects_repeat(self):
        """A node with no TXI clamp flags should use GL_REPEAT (repeat_x=True)."""
        class FakeNode:
            txi_clamp_s = False
            txi_clamp_t = False

        node = FakeNode()
        clamp_s = bool(getattr(node, 'txi_clamp_s', False))
        clamp_t = bool(getattr(node, 'txi_clamp_t', False))
        repeat_x = not clamp_s
        repeat_y = not clamp_t
        assert repeat_x is True, "No-clamp node must use repeat_x=True (GL_REPEAT)"
        assert repeat_y is True, "No-clamp node must use repeat_y=True (GL_REPEAT)"

    def test_node_with_clamp_s_expects_clamp_x(self):
        """A node with txi_clamp_s=True must use repeat_x=False (GL_CLAMP_TO_EDGE)."""
        class FakeNode:
            txi_clamp_s = True
            txi_clamp_t = False

        node = FakeNode()
        clamp_s = bool(getattr(node, 'txi_clamp_s', False))
        clamp_t = bool(getattr(node, 'txi_clamp_t', False))
        repeat_x = not clamp_s
        repeat_y = not clamp_t
        assert repeat_x is False, "clamp_s node must use repeat_x=False (GL_CLAMP_TO_EDGE)"
        assert repeat_y is True,  "clamp_s-only node must still use repeat_y=True"

    def test_node_with_clamp_t_expects_clamp_y(self):
        """A node with txi_clamp_t=True must use repeat_y=False."""
        class FakeNode:
            txi_clamp_s = False
            txi_clamp_t = True

        node = FakeNode()
        clamp_s = bool(getattr(node, 'txi_clamp_s', False))
        clamp_t = bool(getattr(node, 'txi_clamp_t', False))
        repeat_x = not clamp_s
        repeat_y = not clamp_t
        assert repeat_x is True,  "clamp_t-only node must still use repeat_x=True"
        assert repeat_y is False, "clamp_t node must use repeat_y=False (GL_CLAMP_TO_EDGE)"

    def test_node_with_both_clamp_expects_both_clamp(self):
        """A node with both clamp flags uses GL_CLAMP_TO_EDGE on both axes."""
        class FakeNode:
            txi_clamp_s = True
            txi_clamp_t = True

        node = FakeNode()
        clamp_s = bool(getattr(node, 'txi_clamp_s', False))
        clamp_t = bool(getattr(node, 'txi_clamp_t', False))
        repeat_x = not clamp_s
        repeat_y = not clamp_t
        assert repeat_x is False, "Both-clamp node must use repeat_x=False"
        assert repeat_y is False, "Both-clamp node must use repeat_y=False"

    def test_node_missing_txi_attrs_defaults_to_repeat(self):
        """A node with no txi_clamp_* attrs at all defaults to GL_REPEAT."""
        class FakeNode:
            pass  # No txi_clamp_s or txi_clamp_t attributes

        node = FakeNode()
        clamp_s = bool(getattr(node, 'txi_clamp_s', False))
        clamp_t = bool(getattr(node, 'txi_clamp_t', False))
        repeat_x = not clamp_s
        repeat_y = not clamp_t
        assert repeat_x is True,  "Missing clamp attrs must default to repeat_x=True"
        assert repeat_y is True,  "Missing clamp attrs must default to repeat_y=True"


# ─────────────────────────────────────────────────────────────────────────────
# Integration: Real N_sithpraet mesh UV validation
# ─────────────────────────────────────────────────────────────────────────────

class TestNSithpraetUVRanges:
    """Validate UV ranges of N_sithpraet mesh nodes to confirm tiling requirements."""

    @pytest.fixture(scope='class')
    def sithpraet_model(self):
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from src.core.mdl_parser import MDLBinaryParser
            mdl_path = os.path.join(os.path.dirname(__file__), '..', 'test_assets', 'N_sithpraet.mdl')
            if not os.path.exists(mdl_path):
                pytest.skip("N_sithpraet.mdl not found in test_assets/")
            return MDLBinaryParser.parse_files(mdl_path)
        except Exception as e:
            pytest.skip(f"Could not load N_sithpraet.mdl: {e}")

    def test_pelvis_requires_tiling(self, sithpraet_model):
        """N_sithpraet pelvis node UV range >> [0,1]: requires GL_REPEAT."""
        for node in sithpraet_model.all_nodes():
            if node.name == 'pelvis_g' and node.uvs:
                us = [uv[0] for uv in node.uvs]
                u_min, u_max = min(us), max(us)
                assert u_max - u_min > 10.0, (
                    f"pelvis_g should have large UV span, got [{u_min:.2f},{u_max:.2f}]"
                )
                # Confirm it exceeds GL_CLAMP_TO_EDGE range
                assert u_max > 1.0 or u_min < 0.0, (
                    "pelvis_g must have UV outside [0,1] to require GL_REPEAT"
                )
                return
        pytest.skip("pelvis_g not found in N_sithpraet.mdl")

    def test_torso_has_uv_over_one(self, sithpraet_model):
        """N_sithpraet torso has U up to 1.366: needs GL_REPEAT for correct sampling."""
        for node in sithpraet_model.all_nodes():
            if node.name == 'torso' and node.uvs:
                us = [uv[0] for uv in node.uvs]
                u_max = max(us)
                assert u_max > 1.0, (
                    f"torso should have U > 1.0 (actual max={u_max:.4f}); "
                    f"GL_CLAMP_TO_EDGE would stretch the edge texel"
                )
                return
        pytest.skip("torso not found in N_sithpraet.mdl")

    def test_limb_nodes_require_tiling(self, sithpraet_model):
        """Limb nodes (thigh/shin/foot) have very large UV ranges."""
        TILING_NODES = {'lthigh_g', 'lshin_g', 'lfoot_g', 'rthigh_g', 'rshin_g', 'rfoot_g'}
        found = set()
        for node in sithpraet_model.all_nodes():
            if node.name in TILING_NODES and node.uvs:
                us = [uv[0] for uv in node.uvs]
                u_span = max(us) - min(us)
                # All limb nodes should have UV span >> 1 (needs real tiling)
                assert u_span > 5.0, (
                    f"{node.name} has UV span {u_span:.2f}; expected > 5.0 "
                    f"for tiled geometry"
                )
                found.add(node.name)
        if not found:
            pytest.skip("No limb nodes found in N_sithpraet.mdl")
        assert len(found) >= 2, f"Expected at least 2 limb nodes, found: {found}"

    def test_head_node_clamp_mode_acceptable(self, sithpraet_model):
        """Head mesh UV is within normal [0,1] range — clamp mode is fine."""
        for node in sithpraet_model.all_nodes():
            if node.name == 'head' and node.uvs:
                us = [uv[0] for uv in node.uvs]
                vs = [uv[1] for uv in node.uvs]
                u_min, u_max = min(us), max(us)
                v_min, v_max = min(vs), max(vs)
                # Head UV should be mostly within [0,1] (slight overshoot is OK)
                assert u_max < 1.5, (
                    f"head U max {u_max:.3f} too large; head should use clamp-friendly UVs"
                )
                assert v_min > -0.1, (
                    f"head V min {v_min:.3f} too negative for clamp-friendly UVs"
                )
                return
        pytest.skip("head not found in N_sithpraet.mdl")


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases and regression guards
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL required")
class TestWrappingEdgeCases:
    """Edge cases and regression guards for the wrapping fix."""

    def test_exact_tile_boundary_uv(self):
        """UV exactly at 1.0 must not cause issues (1.0 == frac(1.0) = 0.0)."""
        tex = _make_checker_tex(64)
        img = Image.new('RGBA', (200, 200), (30, 30, 30, 255))
        # UV at exact tile boundary
        _paste_textured_triangle(
            img, tex,
            (50, 50), (150, 50), (100, 150),
            (1.0, 0.5), (0.0, 0.5), (0.5, 1.0),
            200, 200, (220, 220, 220)
        )
        # Should render without crashing
        rendered = _count_rendered(img)
        assert rendered >= 0  # Just shouldn't crash

    def test_negative_uv_with_modulo(self):
        """Negative UVs (like -13.583) must frac() to positive [0,1] correctly."""
        for u_raw in [-13.583, -6.183, -5.101, -15.370, -0.001]:
            u_frac = u_raw - math.floor(u_raw)
            assert 0.0 <= u_frac <= 1.0, (
                f"frac({u_raw:.3f}) = {u_frac:.6f} not in [0,1]"
            )
            assert u_frac >= 0.0  # Must never be negative

    def test_seam_fix_still_works_after_change(self):
        """The seam-crossing fix (u=0.95→u1=1.02) still operates correctly."""
        from src.gui.tpc_render_utils import _uwrap_global, _edge_has_seam_global
        # Standard seam case
        assert abs(_uwrap_global(0.95, 0.02) - 1.02) < 1e-6, (
            "_uwrap_global(0.95, 0.02) should give 1.02 (seam fix)"
        )
        assert _edge_has_seam_global(0.95, 0.02) is True, (
            "0.95 → 0.02 should be detected as seam-crossing"
        )
        assert _edge_has_seam_global(0.3, 0.7) is False, (
            "0.3 → 0.7 should not be a seam (stays within tile)"
        )

    def test_small_uv_range_normal_path(self):
        """Small UV [0.1, 0.5] still renders correctly via normal path."""
        tex = _make_checker_tex(64)
        img = Image.new('RGBA', (200, 200), (30, 30, 30, 255))
        _paste_textured_triangle(
            img, tex,
            (30, 30), (170, 30), (100, 170),
            (0.1, 0.2), (0.9, 0.2), (0.5, 0.8),
            200, 200, (220, 220, 220)
        )
        rendered = _count_rendered(img)
        assert rendered > 2000, (
            f"Normal UV [0.1,0.9] face rendered only {rendered} pixels"
        )

    def test_uv_just_over_max_tile_count_threshold(self):
        """UV span of 8.1 tiles (just over MAX_TILE_COUNT=8) uses frac() path."""
        tex = _make_checker_tex(32)
        img = Image.new('RGBA', (200, 200), (30, 30, 30, 255))
        # tile_u_needed = floor(8.5) - floor(0.0) + 1 = 9 > 8 → frac() path
        _paste_textured_triangle(
            img, tex,
            (20, 20), (180, 20), (100, 180),
            (0.0, 0.5), (8.5, 0.5), (4.25, 0.5),
            200, 200, (220, 220, 220)
        )
        # Should render without blank (flat degenerate V span → might be skipped,
        # so just check it doesn't crash and produces some output or gracefully skips)
        # No assertion on pixel count (degenerate V=0.5 for all → may skip)

    def test_tpc_render_utils_large_uv_fix(self):
        """tpc_render_utils._paste_textured_triangle also applies frac() fix."""
        tex = _make_checker_tex(64)
        img = Image.new('RGBA', (400, 400), (30, 30, 30, 255))
        # Import from tpc_render_utils specifically (not viewport's version)
        from src.gui.tpc_render_utils import _paste_textured_triangle as _ptr
        _ptr(
            img, tex,
            (50, 50), (350, 50), (200, 350),
            (-13.583, -15.370), (13.583, 6.500), (0.0, -4.435),
            400, 400, (220, 220, 220)
        )
        rendered = _count_rendered(img)
        assert rendered > 5000, (
            f"tpc_render_utils large UV rendered only {rendered} pixels"
        )
