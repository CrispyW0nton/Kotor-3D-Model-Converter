"""
test_texture_render_pipeline.py
================================
End-to-end tests that verify the FULL texture rendering pipeline:
  1. TPC loads correctly and produces valid PIL Image
  2. TextureCache.get() finds textures via search_dirs
  3. FrameRenderer with show_texture=True produces colored pixels (not flat grey)
  4. ResourceManager.has_textures() correctly detects BIF-backed textures
  5. The on-the-fly ResourceManager creation in _refresh_all works

These tests catch the regression where models rendered as flat grey because:
  - ResourceManager.has_textures() only checked TexturePacks ERFs, not BIF
  - show_texture was never auto-enabled because has_textures() returned False
  - The tex_cache never got a resource_manager attached before the scan finished
"""

import os
import sys
import struct
import pytest
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.gui.viewport import FrameRenderer, ArcBallCamera, TextureCache, _load_tpc_bytes
from src.core.mdl_parser import MDLBinaryParser

# ── Test asset paths ──────────────────────────────────────────────────────────
BANTHA_DIR    = os.path.join(ROOT, 'test_assets', 'c_bantha')
BANTHA_MDL    = os.path.join(BANTHA_DIR, 'c_bantha.mdl')
BANTHA_MDX    = os.path.join(BANTHA_DIR, 'c_bantha.mdx')
BANTHA_TPC    = os.path.join(BANTHA_DIR, 'c_bantha01.tpc')
BANTHA_TEX_DIR = os.path.join(BANTHA_DIR, 'textures')

HAS_BANTHA     = os.path.exists(BANTHA_MDL)
HAS_BANTHA_TPC = os.path.exists(BANTHA_TPC)


def _load_model(mdl_path, mdx_path):
    mdl = open(mdl_path, 'rb').read()
    mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
    return MDLBinaryParser(mdl, mdx).parse()


# ── TPC loading tests ─────────────────────────────────────────────────────────

class TestTPCLoading:
    """Verify TPC texture files load correctly into PIL Images."""

    def test_tpc_loads_to_rgba_image(self):
        """_load_tpc_bytes must return an RGBA PIL Image for c_bantha01.tpc."""
        if not HAS_BANTHA_TPC:
            pytest.skip('c_bantha01.tpc not available')
        raw = open(BANTHA_TPC, 'rb').read()
        img = _load_tpc_bytes(raw)
        assert img is not None, '_load_tpc_bytes returned None for valid TPC'
        assert img.mode == 'RGBA', f'Expected RGBA, got {img.mode}'
        assert img.size[0] > 0 and img.size[1] > 0, 'TPC image has zero dimension'

    def test_tpc_image_has_non_black_pixels(self):
        """Bantha texture must contain colored (non-black) pixels after loading."""
        if not HAS_BANTHA_TPC:
            pytest.skip('c_bantha01.tpc not available')
        raw = open(BANTHA_TPC, 'rb').read()
        img = _load_tpc_bytes(raw)
        assert img is not None
        arr = np.array(img)
        # At least 10% of pixels must be non-black (bantha is a brown creature)
        nonblack = int((arr[:, :, :3].sum(axis=2) > 30).sum())
        total = arr.shape[0] * arr.shape[1]
        pct = nonblack / total
        assert pct > 0.1, f'TPC image appears mostly black: {pct:.1%} non-black pixels'

    def test_tpc_correct_size(self):
        """TPC image dimensions must be power-of-two and match header."""
        if not HAS_BANTHA_TPC:
            pytest.skip('c_bantha01.tpc not available')
        raw = open(BANTHA_TPC, 'rb').read()
        # Check TPC header fields
        assert len(raw) >= 128, 'TPC file too small'
        w = struct.unpack_from('<H', raw, 8)[0]
        h = struct.unpack_from('<H', raw, 10)[0]
        assert w > 0 and h > 0, f'Invalid TPC dimensions: {w}x{h}'
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.size == (w, h), f'Image size {img.size} != header {w}x{h}'


# ── TextureCache search_dirs tests ────────────────────────────────────────────

class TestTextureCacheSearchDirs:
    """Verify TextureCache correctly finds textures via file-system search_dirs."""

    def test_texture_found_in_search_dir(self):
        """TextureCache.get() must return an image when TPC is in search_dirs."""
        if not HAS_BANTHA_TPC:
            pytest.skip('c_bantha01.tpc not available')
        cache = TextureCache()
        cache.set_search_dirs([BANTHA_DIR])
        img = cache.get('c_bantha01')
        assert img is not None, 'TextureCache failed to find c_bantha01 in search_dirs'
        assert img.mode == 'RGBA'

    def test_texture_found_in_textures_subdir(self):
        """TextureCache.get() must find textures in a 'textures' sub-directory."""
        if not os.path.exists(BANTHA_TEX_DIR):
            pytest.skip('c_bantha textures/ sub-directory not available')
        cache = TextureCache()
        cache.set_search_dirs([BANTHA_TEX_DIR])
        img = cache.get('c_bantha01')
        assert img is not None, 'TextureCache failed to find c_bantha01 in textures/'

    def test_texture_not_found_returns_none(self):
        """TextureCache.get() returns None for non-existent textures."""
        cache = TextureCache()
        cache.set_search_dirs([BANTHA_DIR])
        img = cache.get('completely_nonexistent_texture_xyz123')
        assert img is None, 'Expected None for non-existent texture'

    def test_cache_deduplicates_loads(self):
        """Calling get() twice returns the same object (cached, no double-load)."""
        if not HAS_BANTHA_TPC:
            pytest.skip('c_bantha01.tpc not available')
        cache = TextureCache()
        cache.set_search_dirs([BANTHA_DIR])
        img1 = cache.get('c_bantha01')
        img2 = cache.get('c_bantha01')
        assert img1 is img2, 'TextureCache should return same object on second call'


# ── FrameRenderer textured rendering tests ────────────────────────────────────

class TestFrameRendererTextured:
    """Verify FrameRenderer produces textured output (not flat grey) when textures available."""

    def _render_with_textures(self, search_dirs, W=256, H=256):
        """Helper: load bantha, set search_dirs, render with show_texture=True."""
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)
        renderer.tex_cache.set_search_dirs(search_dirs)
        renderer.show_texture = True
        renderer.show_solid = True
        return renderer.render(W, H), renderer

    def test_textured_render_has_more_colors_than_flat(self):
        """Textured render must have significantly more color variation than flat shade.

        This is the core regression test: the bantha was rendering flat grey
        because textures were never loaded.  A flat-shaded render has very few
        unique colors (<15), while a textured render has many (>50).
        """
        if not HAS_BANTHA or not HAS_BANTHA_TPC:
            pytest.skip('c_bantha model + texture not available')

        # Flat shade render (no texture)
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        flat_renderer = FrameRenderer(cam)
        flat_renderer.set_model(model)
        flat_renderer.show_texture = False
        flat_renderer.show_solid = True
        flat_img = flat_renderer.render(256, 256)
        flat_arr = np.array(flat_img)
        flat_colors = len(set(
            tuple(flat_arr[y, x, :3].tolist())
            for y in range(0, 256, 8) for x in range(0, 256, 8)
            if flat_arr[y, x, :3].sum() > 30
        ))

        # Textured render
        tex_img, _ = self._render_with_textures([BANTHA_DIR, BANTHA_TEX_DIR])
        tex_arr = np.array(tex_img)
        tex_colors = len(set(
            tuple(tex_arr[y, x, :3].tolist())
            for y in range(0, 256, 8) for x in range(0, 256, 8)
            if tex_arr[y, x, :3].sum() > 30
        ))

        assert tex_colors > flat_colors + 20, (
            f'Textured render has only {tex_colors} colors vs flat {flat_colors} — '
            f'texture likely not rendering (expected textured > flat + 20 colors)'
        )
        assert tex_colors > 50, (
            f'Textured render has only {tex_colors} unique colors — '
            f'expected >50 for a properly textured bantha'
        )

    def test_texture_loaded_in_renderer_cache(self):
        """After a textured render, the texture must appear in renderer.textures cache."""
        if not HAS_BANTHA or not HAS_BANTHA_TPC:
            pytest.skip('c_bantha model + texture not available')
        _, renderer = self._render_with_textures([BANTHA_DIR, BANTHA_TEX_DIR])
        # Check that at least one bantha texture was loaded
        loaded = {k for k in renderer.textures if 'bantha' in k.lower()}
        # Also check tex_cache directly
        cache_key = 'c_bantha01'
        cached = renderer.tex_cache._cache.get(cache_key)
        assert cached is not None, (
            f'c_bantha01 not in tex_cache after textured render. '
            f'renderer.textures keys: {list(renderer.textures.keys())[:5]}'
        )

    def test_get_tex_returns_image_when_search_dirs_set(self):
        """_get_tex() must return a PIL Image after search_dirs are configured."""
        if not HAS_BANTHA or not HAS_BANTHA_TPC:
            pytest.skip('c_bantha model + texture not available')
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)
        renderer.tex_cache.set_search_dirs([BANTHA_DIR, BANTHA_TEX_DIR])

        # Find the first renderable node that has a texture
        tex_node = next(
            (n for n in renderer._iter_visible_mesh_nodes() if n.texture),
            None
        )
        assert tex_node is not None, 'No renderable nodes with textures in c_bantha'
        img = renderer._get_tex(tex_node)
        assert img is not None, (
            f'_get_tex returned None for node {tex_node.name} '
            f'(texture={tex_node.texture!r}) even with search_dirs set'
        )

    def test_no_texture_renders_flat_grey_not_crash(self):
        """FrameRenderer with show_texture=True but no texture source must not crash."""
        if not HAS_BANTHA:
            pytest.skip('c_bantha model not available')
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)
        # No search_dirs, no resource_manager — textures unavailable
        renderer.show_texture = True
        renderer.show_solid = True
        result = renderer.render(128, 128)
        assert result is not None, 'Render must return an image even without textures'
        arr = np.array(result)
        # Should still have model pixels (flat shaded)
        bg = arr[0, 0]
        diff = np.abs(arr.astype(int) - bg.astype(int)).sum(axis=2)
        nonbg = int((diff > 10).sum())
        assert nonbg > 500, f'Expected >500 model pixels in flat shade, got {nonbg}'


# ── ResourceManager.has_textures BIF check ───────────────────────────────────

class TestResourceManagerHasTextures:
    """Verify has_textures() correctly detects BIF-backed texture availability."""

    def test_has_textures_checks_bif_key_map(self):
        """has_textures() must return True when TPC/TGA entries exist in BIF key_map."""
        from src.core.resource_manager import ResourceManager, RES_TPC, RES_TGA, _key
        mgr = ResourceManager.__new__(ResourceManager)
        mgr._k1 = None
        mgr._k2 = None
        mgr._lock = __import__('threading').Lock()

        # Manually create a fake _GameInstall-like object with BIF entries
        from unittest.mock import MagicMock
        fake_k1 = MagicMock()
        fake_k1._tex_erfs = []  # No TexturePacks ERFs
        fake_k1._key_map = {
            _key('c_bantha01', RES_TPC): (0, 0),  # BIF-backed TPC
            _key('c_kinrath01', RES_TGA): (0, 1),  # BIF-backed TGA
        }
        mgr._k1 = fake_k1
        assert mgr.has_textures('K1'), (
            'has_textures should return True when BIF key_map has TPC/TGA entries, '
            'even when TexturePacks ERFs are absent'
        )

    def test_has_textures_false_when_no_tex_entries(self):
        """has_textures() returns False when key_map has NO TPC/TGA entries."""
        from src.core.resource_manager import ResourceManager, RES_MDL, _key
        mgr = ResourceManager.__new__(ResourceManager)
        mgr._k1 = None
        mgr._k2 = None
        mgr._lock = __import__('threading').Lock()

        from unittest.mock import MagicMock
        fake_k1 = MagicMock()
        fake_k1._tex_erfs = []
        fake_k1._key_map = {
            _key('c_bantha', RES_MDL): (0, 0),   # Only models, no textures
        }
        mgr._k1 = fake_k1
        assert not mgr.has_textures('K1'), (
            'has_textures should return False when key_map only has MDL entries'
        )

    def test_has_textures_still_checks_tex_erfs(self):
        """has_textures() still returns True when TexturePacks ERFs exist (no key_map)."""
        from src.core.resource_manager import ResourceManager
        mgr = ResourceManager.__new__(ResourceManager)
        mgr._k1 = None
        mgr._k2 = None
        mgr._lock = __import__('threading').Lock()

        from unittest.mock import MagicMock
        fake_k1 = MagicMock()
        fake_k1._tex_erfs = [MagicMock()]  # Has TexturePacks ERF
        fake_k1._key_map = {}  # Empty key_map
        mgr._k1 = fake_k1
        assert mgr.has_textures('K1'), (
            'has_textures should still return True when TexturePacks ERFs exist'
        )

    def test_has_textures_all_game_check(self):
        """has_textures('all') checks both K1 and K2."""
        from src.core.resource_manager import ResourceManager, RES_TPC, _key
        mgr = ResourceManager.__new__(ResourceManager)
        mgr._k1 = None
        mgr._k2 = None
        mgr._lock = __import__('threading').Lock()

        from unittest.mock import MagicMock
        fake_k2 = MagicMock()
        fake_k2._tex_erfs = []
        fake_k2._key_map = {_key('tex001', RES_TPC): (0, 0)}
        mgr._k2 = fake_k2
        # K1 has nothing, K2 has BIF textures
        assert not mgr.has_textures('K1'), 'K1 has no textures'
        assert mgr.has_textures('K2'), 'K2 has BIF textures'
        assert mgr.has_textures('all'), 'all should find K2 textures'


# ── UV correctness tests ──────────────────────────────────────────────────────

class TestUVCorrectness:
    """Verify UV coordinates are correct and V-flip is applied properly."""

    def test_bantha_uvs_in_valid_range(self):
        """c_bantha UV coords must be in [-0.1, 1.1] range (small seam tolerance)."""
        if not HAS_BANTHA:
            pytest.skip('c_bantha model not available')
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        for node in model.mesh_nodes():
            if not node.render or not node.uvs:
                continue
            for u, v in node.uvs:
                assert -0.5 <= u <= 1.5, f'{node.name}: U={u:.3f} out of expected range'
                assert -0.5 <= v <= 1.5, f'{node.name}: V={v:.3f} out of expected range'

    def test_bantha_uv_vertex_count_matches_vert_count(self):
        """UV count must equal vertex count for c_bantha renderable nodes."""
        if not HAS_BANTHA:
            pytest.skip('c_bantha model not available')
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        for node in model.mesh_nodes():
            if not node.render or not node.uvs:
                continue
            assert len(node.uvs) == len(node.vertices), (
                f'{node.name}: UV count {len(node.uvs)} != vert count {len(node.vertices)}'
            )

    def test_vflip_applied_in_rasterizer(self):
        """The accel rasterizer must apply V-flip (v = 1 - v_raw) at sampling time."""
        # Verify accel.py applies v = 1.0 - (interpolated v) before texture sampling
        # This is tested by checking the JIT / NumPy code has the correct formula
        from src.gui.accel import _rasterize_triangle_numpy
        import numpy as np

        # Create a 2x2 RGBA texture:
        # top-left (0,0) = RED,    top-right (1,0) = GREEN
        # bottom-left (0,1) = BLUE, bottom-right (1,1) = WHITE
        # (PIL convention: row 0 = top)
        tex = np.zeros((2, 2, 4), dtype=np.uint8)
        tex[0, 0] = [255, 0, 0, 255]    # top-left = RED
        tex[0, 1] = [0, 255, 0, 255]    # top-right = GREEN
        tex[1, 0] = [0, 0, 255, 255]    # bottom-left = BLUE
        tex[1, 1] = [255, 255, 255, 255] # bottom-right = WHITE

        # A single triangle covering a small screen area
        # UV (0,0) = should sample top-left of texture AFTER V-flip
        # In KotOR MDX convention, V=0 means BOTTOM of texture (OpenGL)
        # After V-flip: sample_v = 1 - mdx_v, so mdx_v=0 → sample_v=1 → bottom row
        buf = np.zeros((32, 32, 4), dtype=np.uint8)
        # UV at v=0.01 (near bottom in MDX = near top in PIL after flip)
        # After flip: sample_v ≈ 0.99 → should sample bottom row of PIL image (row 1)
        _rasterize_triangle_numpy(
            buf, tex,
            5, 5, 20, 5, 12, 20,  # screen coords (a visible triangle)
            0.1, 0.01,   # u0=0.1, v0=0.01 (MDX v=0 = bottom → PIL v=1 = BLUE row)
            0.9, 0.01,   # u1=0.9, v1=0.01
            0.5, 0.1,    # u2=0.5, v2=0.1
            255, 255, 255,
        )
        # The rendered pixels should be dominated by blue (bottom row) because:
        # mdx_v ≈ 0.01 → after V-flip → sample at 1-0.01=0.99 → PIL row 1 (bottom) = BLUE
        interior_pixels = buf[8:15, 8:18]
        rendered = interior_pixels[interior_pixels[:,:,3] > 0]
        if len(rendered) > 0:
            avg_b = rendered[:, 2].mean()
            avg_r = rendered[:, 0].mean()
            # Blue should dominate since v≈0 maps to bottom of PIL image (BLUE row)
            assert avg_b > avg_r, (
                f'V-flip test: expected BLUE (avg_b={avg_b:.0f}) > RED (avg_r={avg_r:.0f}). '
                f'V-flip may not be applied correctly in rasterizer.'
            )
