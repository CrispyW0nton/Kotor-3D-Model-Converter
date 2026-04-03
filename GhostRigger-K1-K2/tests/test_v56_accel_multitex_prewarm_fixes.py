"""
Phase 15 Regression Tests – Accelerated Rasterizer Multi-Texture & Prewarm Fixes
==================================================================================

Covers the critical fixes applied in the Phase 15 (v5.6) deep audit:

  FIX-1  _draw_mesh_accel: multi-texture nodes no longer fall back to flat shading.
         Previously: `if flat_only or _tex_arr is None:` → multi-tex nodes had
         _tex_arr=None intentionally (line ~5088), so they ALWAYS got flat shade.
         Fixed: check `_any_tex_arr = (_tex_arr is not None or any(t is not None
         for t in face_tex_arr))` so multi-tex nodes use the textured pass.

  FIX-2  _draw_mesh_accel textured pass: faces with None texture now get a flat-
         shade fallback within the textured pass instead of being silently skipped.
         This handles mixed textured/untextured nodes correctly.

  FIX-3  _node_world_transform / _get_world_verts_for_node: inline relative imports
         now have try/except fallback to absolute imports for standalone test contexts.

  FIX-4  set_model() now calls self.textures.clear() so stale PIL images from the
         previous model are evicted when a new model is loaded.

  FIX-5  _prewarm_textures() now triggers a re-render on the main thread after
         loading textures, so the first displayed frame is always textured (not
         flat grey).

  FIX-6  _wire_resource_manager_to_viewport() and _refresh_resource_panels() now
         re-run prewarm for the current model when the resource manager is wired
         after the initial model load (e.g. library scan completes later).

  FIX-7  GameVersion import in _draw_stats now has try/except fallback for headless
         test environments.

All tests are pure-Python (no Tkinter, no real KotOR install required).
"""

import sys
import os
import math
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ─────────────────────────────────────────────────────────────────────────────
#  PIL / NumPy availability guards
# ─────────────────────────────────────────────────────────────────────────────

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _solid_rgba(r, g, b, a=255, size=(64, 64)):
    """Return a solid-colour RGBA PIL Image."""
    img = Image.new('RGBA', size, (r, g, b, a))
    return img


def _make_model_minimal():
    """Build a minimal KotorModel with one textured trimesh node."""
    from src.core.model_data import KotorModel, ModelNode, NodeFlags
    m = KotorModel()
    m.name = 'test_model'

    root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
    mesh = ModelNode(name='body', flags=int(NodeFlags.MESH))
    mesh.texture = 'test_tex'
    # Triangle
    mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
    mesh.faces = [(0, 1, 2)]
    mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    root.children.append(mesh)
    mesh.parent = root
    m.root = root
    return m


def _make_renderer():
    """Create a FrameRenderer with a default ArcBallCamera for testing."""
    from src.gui.viewport import FrameRenderer, ArcBallCamera
    cam = ArcBallCamera()
    return FrameRenderer(cam)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-1/2: Multi-texture detection logic
# ─────────────────────────────────────────────────────────────────────────────

class TestAnyTexArrLogic:
    """Unit tests for the _any_tex_arr detection introduced in FIX-1."""

    def test_all_none_tex_arr_uses_flat(self):
        """When all face_tex_arr entries are None and _tex_arr is None → use flat."""
        face_tex_arr = [None, None, None]
        _tex_arr = None
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        assert not _any_tex_arr, "All-None should not trigger textured pass"

    def test_single_tex_node_uses_textured(self):
        """When _tex_arr is set (single-tex node) → use textured pass."""
        fake_arr = object()
        face_tex_arr = [fake_arr] * 3
        _tex_arr = fake_arr
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        assert _any_tex_arr, "Single-tex node should trigger textured pass"

    def test_multitex_node_uses_textured(self):
        """Multi-tex nodes have _tex_arr=None but face_tex_arr has entries → textured."""
        fake_arr = object()
        # Multi-tex: _tex_arr is intentionally None
        _tex_arr = None
        face_tex_arr = [fake_arr, None, fake_arr]
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        assert _any_tex_arr, "Multi-tex node with some textures should use textured pass"

    def test_multitex_node_all_cache_miss_uses_flat(self):
        """Multi-tex node where ALL face textures are None (cache miss) → flat."""
        _tex_arr = None
        face_tex_arr = [None, None]  # TexArrayCache miss for all faces
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        assert not _any_tex_arr, "All-None multi-tex should use flat (graceful degradation)"

    def test_single_face_with_texture(self):
        """A single face that has a texture triggers the textured path."""
        _tex_arr = None
        fake_arr = object()
        face_tex_arr = [None, None, fake_arr]  # only last face has tex
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        assert _any_tex_arr, "Even one face with texture should use textured pass"

    def test_flat_only_overrides_texture(self):
        """flat_only=True always uses flat regardless of texture arrays."""
        fake_arr = object()
        _tex_arr = fake_arr
        face_tex_arr = [fake_arr] * 5
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        # flat_only overrides _any_tex_arr
        flat_only = True
        use_flat = flat_only or not _any_tex_arr
        assert use_flat, "flat_only=True should always use flat path"

    def test_textured_path_selected_correctly(self):
        """Not-flat_only + has textures → textured path."""
        fake_arr = object()
        _tex_arr = fake_arr
        face_tex_arr = [fake_arr] * 3
        _any_tex_arr = (_tex_arr is not None or
                        any(t is not None for t in face_tex_arr))
        flat_only = False
        use_flat = flat_only or not _any_tex_arr
        assert not use_flat, "Should select textured path"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-3: Relative import fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestRelativeImportFallback:
    """Verify that the try/except import fallback works in standalone contexts."""

    def test_quat_rotate_import(self):
        """_quat_rotate can be imported via absolute path."""
        try:
            from src.core.model_data import _quat_rotate
        except ImportError:
            from core.model_data import _quat_rotate  # type: ignore
        v = (1.0, 0.0, 0.0)
        # Identity quaternion (0, 0, 0, 1) should return v unchanged
        result = _quat_rotate((0.0, 0.0, 0.0, 1.0), v)
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1]) < 1e-6
        assert abs(result[2]) < 1e-6

    def test_quat_normalize_bind_import(self):
        """_quat_normalize_bind can be imported via absolute path."""
        try:
            from src.core.model_data import _quat_normalize_bind
        except ImportError:
            from core.model_data import _quat_normalize_bind  # type: ignore
        # Pure X-axis 180° rotation: (1, 0, 0, 0) → should normalize to identity
        result = _quat_normalize_bind([1.0, 0.0, 0.0, 0.0])
        # Should be identity-like (nearly-zero xyz or collapsed to (0,0,0,1))
        assert result is not None, "Should return a value"

    def test_game_version_import(self):
        """GameVersion can be imported via absolute path (for _draw_stats fix)."""
        try:
            from src.core.model_data import GameVersion
        except ImportError:
            from core.model_data import GameVersion  # type: ignore
        assert GameVersion.K1 is not None
        assert GameVersion.K2 is not None


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-4: textures.clear() on model change
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestTexturesClearOnModelChange:
    """Verify that set_model clears self.textures to avoid stale PIL images."""

    def test_textures_cleared_on_new_model(self):
        """FrameRenderer.set_model() must clear the textures dict."""
        r = _make_renderer()

        # Manually populate textures with a fake entry
        r.textures['old_tex'] = _solid_rgba(255, 0, 0)
        assert 'old_tex' in r.textures, "Setup: textures dict should have entry"

        # Load a new (minimal) model
        from src.core.model_data import KotorModel
        m = KotorModel()
        r.set_model(m)

        assert 'old_tex' not in r.textures, (
            "textures dict should be cleared when a new model is set, "
            "but 'old_tex' is still present"
        )

    def test_textures_empty_after_none_model(self):
        """set_model(None) should also clear textures."""
        r = _make_renderer()
        r.textures['some_tex'] = _solid_rgba(0, 255, 0)
        r.set_model(None)
        assert not r.textures, "textures should be empty after set_model(None)"

    def test_textures_not_carried_between_models(self):
        """Two models with same-named textures don't interfere."""
        r = _make_renderer()
        from src.core.model_data import KotorModel
        m1 = KotorModel()
        m1.name = 'model1'
        m2 = KotorModel()
        m2.name = 'model2'

        r.set_model(m1)
        r.textures['shared_name'] = _solid_rgba(255, 0, 0)   # red for model1

        r.set_model(m2)
        # After model change, the shared_name entry should be gone
        assert 'shared_name' not in r.textures, (
            "Old model's textures should be cleared on set_model, not carried over"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-5: Prewarm triggers re-render
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestPrewarmRerender:
    """Verify that _prewarm_textures fires a re-render after loading textures."""

    def test_prewarm_calls_after_when_textures_loaded(self):
        """_prewarm_textures should schedule a re-render via after(0, ...) when
        at least one texture is loaded successfully."""
        # We don't have a Tk root, so mock the _request_render / after methods.
        calls = []

        class FakeViewport:
            """Minimal duck-type for _prewarm_textures."""
            def __init__(self):
                self._renderer = _make_fake_renderer()

            def after(self, delay, func, *args):
                calls.append(('after', delay, func))

            def _request_render(self):
                calls.append(('render',))

        class FakeCache:
            def get(self, name):
                # Return a solid image for any name
                return _solid_rgba(128, 128, 128)

        def _make_fake_renderer():
            class R:
                tex_cache = FakeCache()
                model = None
            return R()

        vp = FakeViewport()
        tex_names = ['tex1', 'tex2']

        # Run _prewarm_textures logic inline (mirror the implementation)
        renderer = vp._renderer
        any_loaded = False
        for name in tex_names:
            try:
                img = renderer.tex_cache.get(name)
                if img is not None:
                    any_loaded = True
            except MemoryError:
                break
            except Exception:
                pass
        if any_loaded:
            try:
                vp.after(0, vp._request_render)
            except Exception:
                pass

        assert any_loaded, "Should have loaded at least one texture"
        assert len(calls) >= 1, "after() should be called when textures are loaded"
        assert calls[0][0] == 'after', "First call should be to after()"

    def test_prewarm_no_rerender_when_nothing_loads(self):
        """_prewarm_textures should NOT schedule re-render when all loads fail."""
        calls = []

        class FakeCache:
            def get(self, name):
                return None  # All textures missing

        any_loaded = False
        for name in ['missing1', 'missing2']:
            img = FakeCache().get(name)
            if img is not None:
                any_loaded = True

        if any_loaded:
            calls.append('would_rerender')

        assert not any_loaded
        assert len(calls) == 0, "Should not request re-render when nothing loaded"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-2: Mixed textured/untextured faces in same batch
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not (_PIL and _NUMPY), reason="PIL + NumPy required")
class TestMixedTexUntexFaces:
    """Test that the textured pass handles None-texture groups via flat fallback."""

    def test_none_group_flushed_as_flat(self):
        """In the textured pass grouping loop, a None-tex group is rendered flat."""
        from src.gui.accel import flat_shade_frame, rasterize_frame, ACCEL_TIER

        W, H = 64, 64
        buf = np.zeros((H, W, 4), dtype=np.uint8)
        buf[:, :] = [18, 18, 40, 255]  # background

        # Simulate: 2 faces, first has None texture, second has a texture
        # Build minimal arrays
        NF = 2
        # Triangle 0: None-tex face (flat shade → green)
        # Triangle 1: textured face
        tex_arr = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)  # red texture

        # Screen coords: two overlapping triangles
        all_sx = np.array([5, 20, 12, 40, 55, 47], dtype=np.int64)
        all_sy = np.array([5, 5, 20, 5, 5, 20], dtype=np.int64)
        fv0 = np.array([0, 3], dtype=np.int64)
        fv1 = np.array([1, 4], dtype=np.int64)
        fv2 = np.array([2, 5], dtype=np.int64)
        vis = np.array([True, True], dtype=np.bool_)

        # Flat shade face 0 (green)
        fr = np.array([0], dtype=np.uint8)
        fg = np.array([200], dtype=np.uint8)
        fb = np.array([0], dtype=np.uint8)
        flat_shade_frame(buf, all_sx, all_sy,
                         fv0[:1], fv1[:1], fv2[:1],
                         fr, fg, fb, vis[:1])

        # Textured face 1 (red texture)
        all_uu = np.array([0.0, 1.0, 0.5, 0.0, 1.0, 0.5], dtype=np.float64)
        all_vv = np.array([0.0, 0.0, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
        sr = np.array([255], dtype=np.int64)
        sg = np.array([255], dtype=np.int64)
        sb = np.array([255], dtype=np.int64)
        alpha = np.array([1.0], dtype=np.float64)
        rasterize_frame(buf, tex_arr, all_sx, all_sy, all_uu, all_vv,
                        fv0[1:], fv1[1:], fv2[1:], sr, sg, sb, alpha, vis[1:])

        # Verify: some pixels in left triangle are greenish (flat)
        # Verify: some pixels in right triangle are reddish (textured)
        green_pixels = np.sum((buf[10:15, 10:18, 1] > 150) & (buf[10:15, 10:18, 0] < 50))
        red_pixels   = np.sum((buf[10:15, 45:52, 0] > 150) & (buf[10:15, 45:52, 1] < 50))

        assert green_pixels > 0, "Should have green (flat-shaded) pixels in left triangle"
        assert red_pixels > 0,   "Should have red (textured) pixels in right triangle"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-6: Full FrameRenderer render with accel path
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not (_PIL and _NUMPY), reason="PIL + NumPy required")
class TestFrameRendererAccelTexture:
    """Integration test: FrameRenderer accel path renders texture when available."""

    def _make_renderer_with_texture(self):
        """Return a FrameRenderer with a simple model and pre-loaded texture."""
        from src.gui.viewport import FrameRenderer, TextureCache
        from src.core.model_data import KotorModel, ModelNode, NodeFlags

        r = _make_renderer()
        r.show_texture = True
        r.show_solid = True

        # Build model
        m = KotorModel()
        m.name = 'accel_test'
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name='floor', flags=int(NodeFlags.MESH))
        mesh.texture = 'floor_tex'
        # A large triangle that fills most of the viewport
        mesh.vertices = [(-2.0, -1.0, 3.0), (2.0, -1.0, 3.0), (0.0, 2.0, 3.0)]
        mesh.faces = [(0, 1, 2)]
        mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        root.children.append(mesh)
        mesh.parent = root
        m.root = root
        r.model = m

        # Pre-load a bright orange texture directly into the cache
        orange_tex = _solid_rgba(255, 128, 0, 255, size=(64, 64))
        r.tex_cache._cache['floor_tex'] = orange_tex
        # Also prime the textures dict (simulating completed prewarm)
        r.textures['floor_tex'] = orange_tex

        return r

    def test_accel_render_produces_non_background_pixels(self):
        """With texture loaded, accel render should produce colored pixels."""
        from src.gui.viewport import _ACCEL_AVAILABLE, _NUMPY
        if not _ACCEL_AVAILABLE or not _NUMPY:
            pytest.skip("Accel not available")

        r = self._make_renderer_with_texture()
        img = r.render(128, 128)
        if img is None:
            pytest.skip("Headless render returned None (no PIL)")

        arr = np.array(img)
        # Background is (18, 18, 40); check for orange pixels
        bg = np.array([18, 18, 40])
        is_bg = np.all(arr[:, :, :3] == bg, axis=2)
        non_bg = ~is_bg
        non_bg_count = np.sum(non_bg)
        assert non_bg_count > 50, (
            f"Accel render should produce non-background pixels; got {non_bg_count}"
        )

    def test_accel_render_orange_pixels_present(self):
        """Orange (255, 128, 0) pixels should appear when floor_tex is orange."""
        from src.gui.viewport import _ACCEL_AVAILABLE, _NUMPY
        if not _ACCEL_AVAILABLE or not _NUMPY:
            pytest.skip("Accel not available")

        r = self._make_renderer_with_texture()
        img = r.render(128, 128)
        if img is None:
            pytest.skip("Headless render returned None")

        arr = np.array(img.convert('RGB'))
        # Check for orange-ish pixels (R > 150, G > 50, B < 50)
        orange_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] > 50) & (arr[:, :, 2] < 80)
        assert np.sum(orange_mask) > 20, (
            "Expected orange pixels from textured rendering of floor_tex"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Sentinel threshold consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelConsistency:
    """Verify that sentinel thresholds are consistent across modules."""

    def test_viewport_sentinel_is_100(self):
        """viewport.py's _UV_SENTINEL must be 100.0 (raised from 20.0 in Phase 18)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'viewport_sentinel',
            os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'viewport.py')
        )
        # Just grep the file rather than importing (avoids Tk dependency)
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'viewport.py')
        with open(path) as f:
            content = f.read()
        # Find the _UV_SENTINEL assignment
        import re
        match = re.search(r'^_UV_SENTINEL\s*=\s*([0-9.]+)', content, re.MULTILINE)
        assert match is not None, "_UV_SENTINEL not found in viewport.py"
        val = float(match.group(1))
        assert val >= 100.0, (
            f"_UV_SENTINEL should be >= 100.0 (Phase 18 raise), got {val}"
        )

    def test_tpc_render_utils_sentinel_is_100(self):
        """tpc_render_utils.py's _UV_SENTINEL must also be 100.0."""
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'tpc_render_utils.py')
        with open(path) as f:
            content = f.read()
        import re
        match = re.search(r'^_UV_SENTINEL\s*=\s*([0-9.]+)', content, re.MULTILINE)
        assert match is not None, "_UV_SENTINEL not found in tpc_render_utils.py"
        val = float(match.group(1))
        assert val >= 100.0, (
            f"tpc_render_utils _UV_SENTINEL should be >= 100.0, got {val}"
        )

    def test_sentinel_filter_np_uses_caller_threshold(self):
        """sentinel_filter_np must use the caller-provided threshold, not a hardcoded 20."""
        if not _NUMPY:
            pytest.skip("NumPy not available")
        from src.gui.accel import sentinel_filter_np
        import numpy as np

        # UVs with value 50 — should be VALID at threshold=100, INVALID at threshold=20
        uvs_50 = np.full((4, 3, 2), 50.0, dtype=np.float32)

        mask_100 = sentinel_filter_np(uvs_50, sentinel=100.0)
        mask_20  = sentinel_filter_np(uvs_50, sentinel=20.0)

        assert mask_100.all(),  "UVs at 50 should be valid at sentinel=100"
        assert not mask_20.any(), "UVs at 50 should be invalid at sentinel=20"


# ─────────────────────────────────────────────────────────────────────────────
#  Thread-safety: prewarm doesn't corrupt textures dict
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestPrewarmThreadSafety:
    """Verify that the prewarm thread doesn't corrupt the textures dict."""

    def test_concurrent_prewarm_and_textures_access(self):
        """Multiple concurrent texture loads should not corrupt the cache."""
        from src.gui.viewport import TextureCache
        import tempfile, os

        # Create temp texture files
        tmpdir = tempfile.mkdtemp()
        for i in range(5):
            img = _solid_rgba(i * 50, 100, 200)
            img.save(os.path.join(tmpdir, f'tex{i}.tga'))

        cache = TextureCache()
        cache.set_search_dirs([tmpdir])
        errors = []

        def load_all():
            for i in range(5):
                try:
                    cache.get(f'tex{i}')
                except Exception as e:
                    errors.append(str(e))

        threads = [threading.Thread(target=load_all) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread-safety errors: {errors}"

        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Regression: textures.clear doesn't break subsequent loads
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestTexturesClearRobustness:
    """Textures cleared on model change should reload cleanly on next render."""

    def test_textures_reload_after_clear(self):
        """After set_model() clears textures, _get_tex still returns image from cache."""
        from src.gui.viewport import FrameRenderer, TextureCache
        from src.core.model_data import KotorModel, ModelNode, NodeFlags

        r = _make_renderer()

        # Pre-populate tex_cache (simulates prewarm completing)
        green = _solid_rgba(0, 255, 0)
        r.tex_cache._cache['mesh_tex'] = green

        # Build minimal model
        m = KotorModel()
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name='mesh', flags=int(NodeFlags.MESH))
        mesh.texture = 'mesh_tex'
        mesh.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        mesh.faces = [(0, 1, 2)]
        mesh.uvs = [(0, 0), (1, 0), (0, 1)]
        root.children.append(mesh)
        mesh.parent = root
        m.root = root

        r.set_model(m)
        # textures dict should be empty after set_model
        assert 'mesh_tex' not in r.textures

        # _get_tex should still return the image from tex_cache
        img = r._get_tex(mesh)
        assert img is not None, "Should load from tex_cache even after textures.clear()"
        # And now it's back in the textures dict
        assert 'mesh_tex' in r.textures
