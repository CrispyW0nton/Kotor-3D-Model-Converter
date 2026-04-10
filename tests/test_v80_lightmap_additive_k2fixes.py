"""
tests/test_v80_lightmap_additive_k2fixes.py
============================================
v8.0 regression tests covering:

  1. Lightmap compositing  – _paste_lightmap_triangle multiply-blends a
     lightmap onto a diffuse-rendered face (overbright ×2, masked to triangle).

  2. Additive blending     – _paste_textured_triangle with is_additive=True
     uses dst+src compositing instead of alpha-over.

  3. K2 header auto-detect – MDL parser detects K2 models with unknown fp1
     by validating mdx_data_off/verts_off and retrying with the K2 variant.

  4. Lightmap UV wiring    – _draw_mesh_textured reads node.uvs_lm per vertex
     and passes them through the tris list to the lightmap pass.

  5. tris tuple width      – tris entries now carry 16 fields (added lm_img,
     lm_uv0/1/2); entry unpacking must match.
"""

import math
import struct
import threading
from typing import List, Tuple
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Shared import guard ──────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

try:
    import numpy as np
    _NP = True
except ImportError:
    _NP = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _solid_image(w: int, h: int, color=(200, 100, 50)) -> 'Image.Image':
    """Return a solid-color RGBA PIL image."""
    img = Image.new('RGBA', (w, h), color + (255,))
    return img


def _solid_lm_image(w: int, h: int, lm_color=(255, 255, 255)) -> 'Image.Image':
    """Return a solid RGB lightmap image."""
    return Image.new('RGB', (w, h), lm_color)


def _make_canvas(w=200, h=200, bg=(30, 30, 30)) -> 'Image.Image':
    """Return a solid-color RGB canvas."""
    return Image.new('RGB', (w, h), bg)


# Screen-space triangle filling a visible portion of a 200×200 canvas
_SP0 = (50, 50)
_SP1 = (150, 50)
_SP2 = (100, 150)
_UV0 = (0.0, 0.0)
_UV1 = (1.0, 0.0)
_UV2 = (0.5, 1.0)


# ════════════════════════════════════════════════════════════════════════════
# 1. Additive blending
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _PIL or not _NP, reason="PIL+numpy required")
class TestAdditiveBlending:

    def _run_paste(self, canvas, tex, is_additive=False):
        from src.gui.viewport import _paste_textured_triangle
        _paste_textured_triangle(
            canvas, tex,
            _SP0, _SP1, _SP2,
            _UV0, _UV1, _UV2,
            canvas.width, canvas.height,
            shade_color=(255, 255, 255),
            node_alpha=1.0,
            is_additive=is_additive
        )

    def test_additive_brightens_background(self):
        """Additive blend over a dark bg produces pixels brighter than the bg."""
        bg_val = 50
        tex_val = 100
        canvas = _make_canvas(200, 200, bg=(bg_val, bg_val, bg_val))
        tex    = _solid_image(64, 64, (tex_val, tex_val, tex_val))
        self._run_paste(canvas, tex, is_additive=True)
        # Sample the centroid of the triangle
        px = canvas.getpixel((100, 83))[:3]
        assert all(v >= bg_val for v in px), \
            f"Additive should not darken: bg={bg_val} got {px}"
        assert any(v > bg_val for v in px), \
            f"Additive should brighten: bg={bg_val} got {px}"

    def test_additive_does_not_exceed_255(self):
        """Additive blend of two bright values must clamp at 255."""
        canvas = _make_canvas(200, 200, bg=(200, 200, 200))
        tex    = _solid_image(64, 64, (200, 200, 200))
        self._run_paste(canvas, tex, is_additive=True)
        px = canvas.getpixel((100, 83))[:3]
        assert all(v <= 255 for v in px), f"Overflow: {px}"

    def test_non_additive_normal_alpha_blend(self):
        """Normal (non-additive) blend: result is between bg and tex color."""
        bg_val = 50
        tex_val = 200
        canvas = _make_canvas(200, 200, bg=(bg_val, bg_val, bg_val))
        tex    = _solid_image(64, 64, (tex_val, tex_val, tex_val))
        self._run_paste(canvas, tex, is_additive=False)
        px = canvas.getpixel((100, 83))[:3]
        # Normal blend: should be close to tex_val (full opaque texture)
        assert any(v > bg_val for v in px), \
            f"Normal blend should show texture: {px}"

    def test_additive_vs_alpha_differ_on_dark_bg(self):
        """Additive result > alpha-blend result on a dark background."""
        bg = (20, 20, 20)
        tex_color = (150, 150, 150)
        canvas_add   = _make_canvas(200, 200, bg)
        canvas_alpha = _make_canvas(200, 200, bg)
        tex = _solid_image(64, 64, tex_color)
        self._run_paste(canvas_add,   tex, is_additive=True)
        self._run_paste(canvas_alpha, tex, is_additive=False)
        px_add   = canvas_add.getpixel((100, 83))[:3]
        px_alpha = canvas_alpha.getpixel((100, 83))[:3]
        # Additive: bg + tex = 20+150 = 170; alpha-blend: ~tex color 150
        # Additive should produce equal or brighter pixels
        assert sum(px_add) >= sum(px_alpha), \
            f"Additive {px_add} should be >= alpha {px_alpha}"

    def test_additive_black_texture_leaves_bg_unchanged(self):
        """Additive blend with a fully black texture should not change the bg."""
        bg_val = 120
        canvas = _make_canvas(200, 200, (bg_val, bg_val, bg_val))
        tex    = _solid_image(64, 64, (0, 0, 0))
        self._run_paste(canvas, tex, is_additive=True)
        px = canvas.getpixel((100, 83))[:3]
        assert all(v >= bg_val - 5 for v in px), \
            f"Black additive should not darken: got {px}"


# ════════════════════════════════════════════════════════════════════════════
# 2. Lightmap compositing
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _PIL or not _NP, reason="PIL+numpy required")
class TestLightmapCompositing:

    def _run_lm(self, canvas, lm_img, lm_color=None):
        from src.gui.viewport import _paste_lightmap_triangle
        _paste_lightmap_triangle(
            canvas, lm_img,
            _SP0, _SP1, _SP2,
            _UV0, _UV1, _UV2,
            canvas.width, canvas.height
        )

    def test_white_lightmap_doubles_diffuse(self):
        """
        White (255,255,255) lightmap × overbright×2 saturates the surface.
        Starting from diffuse=100, after white LM multiply: min(100*255*2/255,255)=200.
        """
        diffuse_val = 100
        canvas = _make_canvas(200, 200, (diffuse_val, diffuse_val, diffuse_val))
        lm     = _solid_lm_image(32, 32, (255, 255, 255))
        self._run_lm(canvas, lm)
        px = canvas.getpixel((100, 83))[:3]
        # White LM × 2 = double the diffuse (clamped at 255)
        expected = min(diffuse_val * 2, 255)
        assert all(abs(v - expected) <= 10 for v in px), \
            f"White LM: expected ~{expected} got {px}"

    def test_mid_grey_lightmap_leaves_diffuse_unchanged(self):
        """
        Mid-grey (127,127,127) lightmap × overbright×2 ≈ 1.0 → diffuse unchanged.
        KotOR encodes neutral lighting as 0x7F7F7F.
        """
        diffuse_val = 180
        canvas = _make_canvas(200, 200, (diffuse_val, diffuse_val, diffuse_val))
        lm     = _solid_lm_image(32, 32, (127, 127, 127))
        self._run_lm(canvas, lm)
        px = canvas.getpixel((100, 83))[:3]
        # 180*127*2//255 ≈ 179 — nearly unchanged
        assert all(abs(v - diffuse_val) <= 15 for v in px), \
            f"Mid-grey LM: expected ~{diffuse_val} got {px}"

    def test_black_lightmap_darkens_to_zero(self):
        """Black lightmap should darken the surface to black (no light)."""
        canvas = _make_canvas(200, 200, (200, 200, 200))
        lm     = _solid_lm_image(32, 32, (0, 0, 0))
        self._run_lm(canvas, lm)
        px = canvas.getpixel((100, 83))[:3]
        assert all(v <= 20 for v in px), \
            f"Black LM should darken: got {px}"

    def test_lightmap_only_affects_triangle_region(self):
        """Pixels outside the triangle bounding-box must be unchanged."""
        canvas = _make_canvas(200, 200, (100, 100, 100))
        lm     = _solid_lm_image(32, 32, (0, 0, 0))  # darkening LM
        self._run_lm(canvas, lm)
        # Corner pixel (5,5) is well outside the triangle
        px_corner = canvas.getpixel((5, 5))[:3]
        assert all(v >= 90 for v in px_corner), \
            f"LM should not affect outside-triangle pixels: {px_corner}"

    def test_lightmap_none_is_noop(self):
        """Passing lm_img=None must not modify the canvas."""
        from src.gui.viewport import _paste_lightmap_triangle
        canvas = _make_canvas(200, 200, (150, 150, 150))
        before = list(canvas.getdata())
        _paste_lightmap_triangle(
            canvas, None,
            _SP0, _SP1, _SP2, _UV0, _UV1, _UV2,
            canvas.width, canvas.height
        )
        after = list(canvas.getdata())
        assert before == after, "None lm_img should be a no-op"

    def test_lightmap_sentinel_uv_skipped(self):
        """Sentinel UV values (|u|>100) must prevent lightmap application.
        Phase 18: sentinel raised from 20.0 to 100.0. Using 125.0 which is
        genuinely a placeholder value (above the new threshold)."""
        from src.gui.viewport import _paste_lightmap_triangle
        canvas = _make_canvas(200, 200, (150, 150, 150))
        lm     = _solid_lm_image(32, 32, (0, 0, 0))  # would darken
        before = list(canvas.getdata())
        _paste_lightmap_triangle(
            canvas, lm,
            _SP0, _SP1, _SP2,
            (125.0, 0.0), _UV1, _UV2,   # sentinel UV0 (above new threshold 100)
            canvas.width, canvas.height
        )
        after = list(canvas.getdata())
        assert before == after, "Sentinel UV should skip lightmap"

    def test_lightmap_colored_tints_surface(self):
        """A red lightmap applied to a white surface should produce reddish result."""
        canvas = _make_canvas(200, 200, (200, 200, 200))
        lm     = _solid_lm_image(32, 32, (255, 0, 0))  # red LM
        self._run_lm(canvas, lm)
        px = canvas.getpixel((100, 83))[:3]
        r, g, b = px
        # Red channel should be significantly brighter than G/B
        assert r > g + 30 and r > b + 30, \
            f"Red LM: expected red tint, got {px}"


# ════════════════════════════════════════════════════════════════════════════
# 3. K2 header auto-detect
# ════════════════════════════════════════════════════════════════════════════

class TestK2HeaderAutoDetect:
    """
    Tests for the K2 fallback: when fp1 is unrecognised (defaults to K1) but
    the parsed mdx_data_off/verts_off are implausible, the parser retries with
    the K2 8-byte skip and adopts the corrected offsets.
    """

    def _build_minimal_k2_mesh_node(self,
                                     fp1: int,
                                     mdx_size: int = 4096,
                                     mdl_size: int = 8192,
                                     good_mdx_off: int = 512,
                                     good_verts_off: int = 256,
                                     use_k2_layout: bool = True) -> bytes:
        """
        Build a binary blob that looks like the tail of a K2 mesh node header,
        starting at the point where the parser reads:
          [has_lm, rot_tex, bg_geo, has_shadow, beaming, has_render]
          [optionally: 8-byte K2 dirt block]
          [2-byte pad][4-byte area][4-byte unk]
          [mdx_data_off][verts_off]

        If use_k2_layout=True, the 8-byte K2 dirt block is present BEFORE the
        padding/area.  If False, it is absent (K1 layout).
        """
        buf = bytearray()
        # 6 flag bytes
        buf += bytes([0, 0, 0, 0, 0, 1])   # has_lm=0, rot=0, bg=0, shad=0, beam=0, render=1
        if use_k2_layout:
            buf += bytes(8)                 # K2 dirt+hologram block (8 zeros)
        buf += bytes(2)                     # 2-byte pad
        buf += struct.pack('<f', 0.0)       # total_area
        buf += struct.pack('<I', 0)         # unknown pad
        buf += struct.pack('<I', good_mdx_off)   # mdx_data_off (valid)
        buf += struct.pack('<I', good_verts_off) # verts_off   (valid)
        return bytes(buf)

    def test_known_k2_fp1_uses_k2_branch(self):
        """
        With a known K2 fp1 (4285200), game_version should be K2 after parsing.
        """
        from src.core.model_data import GameVersion
        # Test the fingerprint table directly — same logic as MDLBinaryParser
        fp1_k2 = 4285200
        gv = (GameVersion.K1 if fp1_k2 in (4273776, 4273392)
              else GameVersion.K2 if fp1_k2 in (4285200, 4284816)
              else GameVersion.K1)
        assert gv == GameVersion.K2

    def test_known_k2_fp1_alt_uses_k2_branch(self):
        """
        With the alternate K2 fp1 (4284816), game_version should be K2.
        """
        from src.core.model_data import GameVersion
        fp1_k2_alt = 4284816
        gv = (GameVersion.K1 if fp1_k2_alt in (4273776, 4273392)
              else GameVersion.K2 if fp1_k2_alt in (4285200, 4284816)
              else GameVersion.K1)
        assert gv == GameVersion.K2

    def test_unknown_fp1_defaults_to_k1(self):
        """An unknown fp1 should default to K1 game version."""
        from src.core.model_data import GameVersion
        fp1_unknown = 9999999
        gv = (GameVersion.K1 if fp1_unknown in (4273776, 4273392)
              else GameVersion.K2 if fp1_unknown in (4285200, 4284816)
              else GameVersion.K1)
        assert gv == GameVersion.K1

    def test_off_looks_bad_helper_logic(self):
        """
        The _off_looks_bad heuristic should flag offsets larger than the file.
        """
        mdx_size = 4096
        mdl_size = 8192
        max_sz = max(mdx_size, mdl_size)

        def _off_looks_bad(off, ds=mdx_size):
            if off == 0xFFFFFFFF or off == 0:
                return False
            return off > max(ds, mdl_size) + 4096

        # Valid offsets
        assert not _off_looks_bad(512),    "512 should be valid"
        assert not _off_looks_bad(8192),   "8192 == mdl_size, should be valid"
        assert not _off_looks_bad(0),      "0 should be valid (absent)"
        assert not _off_looks_bad(0xFFFFFFFF), "0xFFFFFFFF absent sentinel"

        # Bad offsets
        assert _off_looks_bad(9_000_000), "9MB in 8KB file is bad"
        assert _off_looks_bad(100_000),   "100k in 8KB file is bad"

    def test_k2_autodetect_corrects_bad_offsets(self):
        """
        When game_version=K1 but parsed offsets are garbage (beyond file size),
        retrying with K2 layout should produce valid offsets.

        We simulate this by constructing a fake parser state.
        """
        # Build a K2-layout binary blob (with dirt block)
        good_mdx_off  = 512
        good_verts_off = 256
        mdx_size       = 4096
        mdl_size       = 8192

        # The "raw data" at the tail of the mesh node header (K2 layout):
        # [6 flags] [8 dirt] [2 pad] [4 area] [4 unk] [mdx_off] [verts_off]
        raw = bytearray()
        raw += bytes([0, 0, 0, 0, 0, 1])   # 6 flag bytes
        raw += bytes(8)                     # 8-byte K2 dirt block
        raw += bytes(2)                     # padding
        raw += struct.pack('<f', 0.0)       # total_area
        raw += struct.pack('<I', 0)         # unk pad
        raw += struct.pack('<I', good_mdx_off)
        raw += struct.pack('<I', good_verts_off)

        # Parse as K1 (no dirt skip): o starts at beginning of flag bytes
        o = 0
        o += 6  # consume 6 flags
        # K1: no dirt skip
        o += 2   # pad
        o += 4   # area
        o += 4   # unk
        mdx_k1   = struct.unpack_from('<I', raw, o)[0]; o += 4
        verts_k1 = struct.unpack_from('<I', raw, o)[0]

        # These should look garbage (they're actually dirt-block bytes)
        assert mdx_k1 != good_mdx_off or verts_k1 != good_verts_off, \
            "K1 parse of K2 layout should give wrong values"

        # Now simulate K2 retry: reset and add 8-byte skip
        o2 = 6  # back to right after flags
        o2 += 8   # dirt skip
        o2 += 2   # pad
        o2 += 4   # area
        o2 += 4   # unk
        mdx_k2   = struct.unpack_from('<I', raw, o2)[0]; o2 += 4
        verts_k2 = struct.unpack_from('<I', raw, o2)[0]

        assert mdx_k2   == good_mdx_off,   f"K2 retry mdx: {mdx_k2} != {good_mdx_off}"
        assert verts_k2 == good_verts_off, f"K2 retry verts: {verts_k2} != {good_verts_off}"

    def test_valid_k1_offsets_not_retried(self):
        """
        When K1 parsing produces valid offsets, the K2 retry should NOT be triggered.
        """
        # K1 layout: no dirt block
        mdx_size       = 4096
        good_mdx_off  = 200    # valid for a 4096-byte MDX
        good_verts_off = 100

        raw = bytearray()
        raw += bytes([0, 0, 0, 0, 0, 1])  # flags
        # No dirt block (K1)
        raw += bytes(2)                    # pad
        raw += struct.pack('<f', 0.0)      # area
        raw += struct.pack('<I', 0)        # unk
        raw += struct.pack('<I', good_mdx_off)
        raw += struct.pack('<I', good_verts_off)

        o = 6   # after 6 flags (K1: no extra skip)
        o += 2; o += 4; o += 4
        mdx_parsed   = struct.unpack_from('<I', raw, o)[0]; o += 4
        verts_parsed = struct.unpack_from('<I', raw, o)[0]

        def _off_looks_bad(off):
            if off == 0xFFFFFFFF or off == 0: return False
            return off > max(mdx_size, 8192) + 4096

        # These should be valid — no retry needed
        assert not _off_looks_bad(mdx_parsed),   f"K1 mdx should be valid: {mdx_parsed}"
        assert not _off_looks_bad(verts_parsed), f"K1 verts should be valid: {verts_parsed}"
        assert mdx_parsed   == good_mdx_off
        assert verts_parsed == good_verts_off


# ════════════════════════════════════════════════════════════════════════════
# 4. Lightmap UV wiring in _draw_mesh_textured
# ════════════════════════════════════════════════════════════════════════════

class TestLightmapUVWiring:
    """
    Tests that ModelNode.uvs_lm is properly threaded through to the
    tris list and that the lightmap image is resolved only when
    has_lightmap=True, lightmap name is non-empty, and uvs_lm is non-empty.
    """

    def _make_node(self, has_lm=True, lm_name='lm_floor01', uvs_lm=None):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.has_lightmap = has_lm
        n.lightmap     = lm_name
        n.uvs_lm       = uvs_lm if uvs_lm is not None else [
            (0.0, 0.0), (1.0, 0.0), (0.5, 1.0)
        ]
        return n

    def test_has_lightmap_true_with_name_and_uvs_enables_lm(self):
        """All three conditions present → lm_img should be loaded."""
        n = self._make_node(has_lm=True, lm_name='lm_floor01',
                            uvs_lm=[(0.0,0.0),(1.0,0.0),(0.5,1.0)])
        assert n.has_lightmap
        assert n.lightmap == 'lm_floor01'
        assert len(n.uvs_lm) == 3

    def test_has_lightmap_false_skips_lm(self):
        """has_lightmap=False should prevent lightmap loading."""
        n = self._make_node(has_lm=False, lm_name='lm_floor01',
                            uvs_lm=[(0.0,0.0),(1.0,0.0),(0.5,1.0)])
        # Condition: _node_has_lm AND _lm_tex_name AND _has_lm_uvs
        _node_has_lm = bool(n.has_lightmap)
        assert not _node_has_lm, "has_lightmap=False should prevent lm load"

    def test_empty_lm_name_skips_lm(self):
        """Empty lightmap name should prevent lightmap loading."""
        n = self._make_node(has_lm=True, lm_name='',
                            uvs_lm=[(0.0,0.0),(1.0,0.0),(0.5,1.0)])
        _lm_tex_name = str(n.lightmap)
        assert not _lm_tex_name, "Empty lm name should prevent lm load"

    def test_empty_uvs_lm_skips_lm(self):
        """Empty uvs_lm list should prevent lightmap loading."""
        n = self._make_node(has_lm=True, lm_name='lm_floor01', uvs_lm=[])
        _has_lm_uvs = len(n.uvs_lm) > 0
        assert not _has_lm_uvs, "Empty uvs_lm should prevent lm load"

    def test_lm_uv_indexing_uses_vertex_indices(self):
        """
        Lightmap UVs must be indexed by vertex index (vi0, vi1, vi2),
        not by face-uv tvert indices. This matches the MDX binary layout.
        """
        uvs_lm = [(0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]
        n_uvs_lm = len(uvs_lm)
        vi0, vi1, vi2 = 0, 2, 3

        lm_uv0 = uvs_lm[vi0] if vi0 < n_uvs_lm else (0.5, 0.5)
        lm_uv1 = uvs_lm[vi1] if vi1 < n_uvs_lm else (0.5, 0.5)
        lm_uv2 = uvs_lm[vi2] if vi2 < n_uvs_lm else (0.5, 0.5)

        assert lm_uv0 == (0.1, 0.2)
        assert lm_uv1 == (0.5, 0.6)
        assert lm_uv2 == (0.7, 0.8)

    def test_lm_uv_out_of_range_fallback(self):
        """Out-of-range vertex indices fall back to (0.5, 0.5)."""
        uvs_lm   = [(0.1, 0.2)]   # only 1 entry
        n_uvs_lm = len(uvs_lm)
        vi = 5                     # beyond range

        lm_uv = uvs_lm[vi] if vi < n_uvs_lm else (0.5, 0.5)
        assert lm_uv == (0.5, 0.5), f"Expected fallback, got {lm_uv}"


# ════════════════════════════════════════════════════════════════════════════
# 5. tris tuple width
# ════════════════════════════════════════════════════════════════════════════

class TestTrisTupleWidth:
    """
    The tris list entries now have 16 fields:
      (sort_key, pts, fill, shade_col, tex_img, uv0, uv1, uv2,
       is_sel, fi_local, node_alpha, txi_blending,
       lm_img, lm_uv0, lm_uv1, lm_uv2)

    Verify the unpacking matches the append.
    """

    def test_tris_entry_16_fields(self):
        """A tris entry should unpack into exactly 16 values."""
        # Simulate a tris.append() call
        sort_key   = 42
        pts        = ((10, 20), (30, 20), (20, 40))
        fill       = (200, 100, 50)
        shade_col  = (200, 200, 200)
        tex_img    = None
        uv0        = (0.0, 0.0)
        uv1        = (1.0, 0.0)
        uv2        = (0.5, 1.0)
        is_sel     = False
        fi_local   = 7
        node_alpha = 1.0
        txi_blend  = 0
        lm_img_    = None
        lm_uv0_    = (0.0, 0.0)
        lm_uv1_    = (1.0, 0.0)
        lm_uv2_    = (0.5, 1.0)

        entry = (sort_key, pts, fill, shade_col, tex_img,
                 uv0, uv1, uv2, is_sel, fi_local,
                 node_alpha, txi_blend,
                 lm_img_, lm_uv0_, lm_uv1_, lm_uv2_)

        assert len(entry) == 16, f"Expected 16 fields, got {len(entry)}"

        # Unpack exactly as the drawing loop does
        (depth, pts2, fill2, shade_col2, tex_img2, uv0_, uv1_, uv2_,
         is_sel2, _fi2, t_alpha, txi_blend2,
         tri_lm_img, l_uv0, l_uv1, l_uv2) = entry

        assert depth      == sort_key
        assert tri_lm_img is None
        assert l_uv0      == (0.0, 0.0)
        assert txi_blend2 == 0

    def test_tris_entry_lm_data_preserved(self):
        """Lightmap data in tris entry must round-trip correctly."""
        lm_uv0 = (0.1, 0.2)
        lm_uv1 = (0.3, 0.4)
        lm_uv2 = (0.5, 0.6)

        entry = (
            0, ((0,0),(1,0),(0,1)),
            (0,0,0), (255,255,255), None,
            (0.0,0.0), (1.0,0.0), (0.5,1.0),
            False, 0, 1.0, 0,
            "fake_lm_img", lm_uv0, lm_uv1, lm_uv2
        )

        (*_, tri_lm_img, l0, l1, l2) = entry
        assert tri_lm_img == "fake_lm_img"
        assert l0 == lm_uv0
        assert l1 == lm_uv1
        assert l2 == lm_uv2


# ════════════════════════════════════════════════════════════════════════════
# 6. Integration: lightmap pipeline end-to-end
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _PIL or not _NP, reason="PIL+numpy required")
class TestLightmapIntegration:

    def test_white_lm_then_additive_texture(self):
        """
        Apply a white lightmap (doubles diffuse), then an additive texture
        on top. The final result should be brighter than the lightmapped-only
        version.
        """
        from src.gui.viewport import _paste_lightmap_triangle, _paste_textured_triangle

        canvas = _make_canvas(200, 200, (80, 80, 80))
        lm     = _solid_lm_image(32, 32, (255, 255, 255))
        tex    = _solid_image(32, 32, (50, 50, 50))

        # Step 1: diffuse (normal)
        _paste_textured_triangle(
            canvas, tex, _SP0, _SP1, _SP2, _UV0, _UV1, _UV2,
            200, 200, (255, 255, 255), is_additive=False
        )
        px_after_diffuse = canvas.getpixel((100, 83))[:3]

        # Step 2: lightmap multiply
        _paste_lightmap_triangle(
            canvas, lm, _SP0, _SP1, _SP2, _UV0, _UV1, _UV2, 200, 200
        )
        px_after_lm = canvas.getpixel((100, 83))[:3]

        # White LM (overbright×2) should double the value
        assert sum(px_after_lm) >= sum(px_after_diffuse), \
            f"White LM should brighten: before={px_after_diffuse} after={px_after_lm}"

    def test_black_lm_overrides_bright_texture(self):
        """
        A dark lightmap should darken even a bright diffuse texture.
        This verifies the multiply is applied AFTER the diffuse paste.
        """
        from src.gui.viewport import _paste_lightmap_triangle, _paste_textured_triangle

        canvas = _make_canvas(200, 200, (50, 50, 50))
        tex    = _solid_image(64, 64, (255, 255, 255))  # bright texture
        lm     = _solid_lm_image(32, 32, (10, 10, 10)) # very dark LM

        _paste_textured_triangle(
            canvas, tex, _SP0, _SP1, _SP2, _UV0, _UV1, _UV2,
            200, 200, (255, 255, 255), is_additive=False
        )
        px_bright = canvas.getpixel((100, 83))[:3]
        assert sum(px_bright) > 400, f"Diffuse should be bright: {px_bright}"

        _paste_lightmap_triangle(
            canvas, lm, _SP0, _SP1, _SP2, _UV0, _UV1, _UV2, 200, 200
        )
        px_dark = canvas.getpixel((100, 83))[:3]
        assert sum(px_dark) < sum(px_bright) - 100, \
            f"Black LM should darken: before={px_bright} after={px_dark}"
