"""
GhostRigger-K1-K2 – v10.4 Audit Fixes Test Suite
===================================================
Tests that validate the targeted fixes introduced in v10.4:

  FIX-1  FrameRenderer._lq_tex_mode initialised in __init__ (no getattr fallback)
  FIX-2  FrameRenderer.set_model() resets _lq_tex_mode to False
  FIX-3  TextureCache.get_mip1() thread-safety via dict snapshot
  FIX-4  TextureCache.clear_mip_cache() replaces dict object (not .clear())
  FIX-5  ViewportWidget._fast_drag_enabled always defined; _drag_pan/_drag_lmb use it directly
  FIX-6  ViewportWidget FPS counter uses wall-clock time (not render_ms sum)
  FIX-7  Watchdog uses module-level _time_mod (no per-tick `import time`)
  FIX-8  _draw_mesh_textured reads self._lq_tex_mode directly (attribute lookup)

Run with:  pytest tests/test_v104_audit_fixes.py -v
"""

import os
import sys
import time
import threading
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Pre-import real PIL (matches conftest strategy) ──────────────────────────
try:
    import PIL.Image
    import PIL.ImageDraw
    import PIL.ImageTk
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_tiny_model():
    """Build a minimal KotorModel with one triangle so renders are non-trivial."""
    from src.core.model_data import KotorModel, ModelNode, NodeFlags
    model = KotorModel()
    model.name = "test_model"
    root = ModelNode()
    root.name = "test_root"
    root.flags = NodeFlags.MESH
    root.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    root.faces = [(0, 1, 2)]
    root.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    root.normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1)]
    root.diffuse = (0.8, 0.8, 0.8)
    model.root_node = root
    return model


def _make_camera():
    from src.gui.viewport import ArcBallCamera
    return ArcBallCamera()


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-1  FrameRenderer._lq_tex_mode initialised in __init__
# ─────────────────────────────────────────────────────────────────────────────

class TestLqTexModeInit:
    """_lq_tex_mode must be declared in __init__, not rely on getattr fallback."""

    def test_lq_tex_mode_is_false_after_init(self):
        from src.gui.viewport import FrameRenderer
        cam = _make_camera()
        r = FrameRenderer(cam)
        # Attribute must exist and be False
        assert hasattr(r, '_lq_tex_mode'), \
            "_lq_tex_mode not defined in FrameRenderer.__init__"
        assert r._lq_tex_mode is False, \
            f"Expected False, got {r._lq_tex_mode!r}"

    def test_lq_tex_mode_is_bool_type(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        assert isinstance(r._lq_tex_mode, bool), \
            f"_lq_tex_mode should be bool, got {type(r._lq_tex_mode)}"

    def test_lq_tex_mode_can_be_toggled(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        r._lq_tex_mode = True
        assert r._lq_tex_mode is True
        r._lq_tex_mode = False
        assert r._lq_tex_mode is False


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-2  FrameRenderer.set_model() resets _lq_tex_mode
# ─────────────────────────────────────────────────────────────────────────────

class TestLqTexModeResetOnModelChange:
    """set_model() must clear _lq_tex_mode so no stale LQ survives model reload."""

    def test_set_model_resets_lq_tex_mode(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        r._lq_tex_mode = True   # simulate post-drag state
        r.set_model(None)
        assert r._lq_tex_mode is False, \
            "set_model(None) must reset _lq_tex_mode to False"

    def test_set_model_with_real_model_resets_lq_tex_mode(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        r._lq_tex_mode = True
        model = _make_tiny_model()
        r.set_model(model)
        assert r._lq_tex_mode is False, \
            "set_model(model) must reset _lq_tex_mode to False"

    def test_repeated_set_model_keeps_lq_false(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        for _ in range(3):
            r._lq_tex_mode = True
            r.set_model(None)
            assert r._lq_tex_mode is False


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-3 & FIX-4  TextureCache.get_mip1() thread safety + clear_mip_cache()
# ─────────────────────────────────────────────────────────────────────────────

class TestMipCacheThreadSafety:
    """
    clear_mip_cache() must replace the dict object (not call .clear() in-place)
    so that concurrent render-thread reads of the old dict snapshot stay valid.
    """

    @pytest.mark.skipif(not pytest.importorskip("PIL", reason="PIL not available"),
                        reason="PIL not installed")
    def test_clear_mip_cache_replaces_dict(self):
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        old_id = id(tc._mip_bias_cache)
        tc.clear_mip_cache()
        new_id = id(tc._mip_bias_cache)
        assert old_id != new_id, \
            "clear_mip_cache() must create a new dict, not .clear() in-place"

    def test_clear_mip_cache_replaces_dict_no_pil(self):
        """Dict-replacement invariant must hold even without PIL."""
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        old_id = id(tc._mip_bias_cache)
        tc.clear_mip_cache()
        assert id(tc._mip_bias_cache) != old_id

    def test_get_mip1_no_crash_with_none(self):
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        result = tc.get_mip1(None)
        assert result is None

    def test_concurrent_clear_and_get_mip1(self):
        """
        Simultaneous clear_mip_cache() and get_mip1() calls must not raise.
        This simulates the main-thread/render-thread race.
        """
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")

        from src.gui.viewport import TextureCache

        tc = TextureCache()
        img = Image.new('RGBA', (16, 16), (255, 0, 0, 255))

        errors = []
        iterations = 200

        def reader():
            for _ in range(iterations):
                try:
                    tc.get_mip1(img)
                except Exception as exc:
                    errors.append(f"reader: {exc}")
                    break

        def clearer():
            for _ in range(iterations // 4):
                try:
                    tc.clear_mip_cache()
                    time.sleep(0.0001)
                except Exception as exc:
                    errors.append(f"clearer: {exc}")
                    break

        t_r = threading.Thread(target=reader)
        t_c = threading.Thread(target=clearer)
        t_r.start(); t_c.start()
        t_r.join(timeout=5.0); t_c.join(timeout=5.0)

        assert not errors, f"Race condition errors: {errors}"

    def test_get_mip1_returns_half_size(self):
        """get_mip1 must return half the original dimensions."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        from src.gui.viewport import TextureCache

        tc = TextureCache()
        img = Image.new('RGBA', (64, 32), (100, 200, 50, 255))
        mip = tc.get_mip1(img)
        assert mip is not None
        assert mip.size == (32, 16), f"Expected (32, 16), got {mip.size}"

    def test_get_mip1_is_cached(self):
        """Second get_mip1() call with same image must return same object."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        from src.gui.viewport import TextureCache

        tc = TextureCache()
        img = Image.new('RGBA', (32, 32))
        mip1 = tc.get_mip1(img)
        mip2 = tc.get_mip1(img)
        assert mip1 is mip2, "get_mip1 should return cached result on second call"

    def test_get_mip1_cache_cleared_after_clear(self):
        """After clear_mip_cache() the next get_mip1 must build a fresh mip."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        from src.gui.viewport import TextureCache

        tc = TextureCache()
        img = Image.new('RGBA', (32, 32))
        mip1 = tc.get_mip1(img)
        tc.clear_mip_cache()
        mip2 = tc.get_mip1(img)
        # After clear, new dict → new mip object
        assert mip1 is not mip2


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-5  ViewportWidget._fast_drag_enabled always defined
# ─────────────────────────────────────────────────────────────────────────────

class TestFastDragEnabledAttribute:
    """_fast_drag_enabled must be explicitly set in __init__ and default to False.

    Verified by source-code inspection so the tests run headlessly without
    a Tk display.  The attribute is always set at __init__ time via
    _build_toolbar(), which __init__ calls unconditionally.
    """

    def _get_viewport_source(self):
        import inspect, importlib
        vp = importlib.import_module('src.gui.viewport')
        return inspect.getsource(vp)

    def test_fast_drag_enabled_defined_in_init(self):
        """Attribute must be assigned in viewport.py (in __init__ or _build_toolbar)."""
        src = self._get_viewport_source()
        assert '_fast_drag_enabled' in src, \
            "_fast_drag_enabled not found in viewport.py"
        # Verify default value is False — look for type-annotated assignment
        assert '_fast_drag_enabled: bool = False' in src, \
            "_fast_drag_enabled must be type-annotated and initialised to False in viewport.py"

    def test_fast_drag_enabled_is_bool(self):
        """Default assignment must be the literal bool False with type annotation."""
        src = self._get_viewport_source()
        import re
        # Look for lines that declare the attribute as bool with default False
        matches = re.findall(
            r'_fast_drag_enabled\s*(?::\s*bool)?\s*=\s*(False|True)',
            src
        )
        assert matches, "_fast_drag_enabled must be assigned True or False in viewport.py"
        assert 'False' in matches, \
            f"Expected 'False' initial assignment, found: {matches}"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-6  FPS counter uses wall-clock time
# ─────────────────────────────────────────────────────────────────────────────

class TestFpsCounterWallClock:
    """ViewportWidget must initialise _fps_last_wall and use wall-clock delta.

    Verified by source-code inspection to run headlessly without Tk.
    """

    def _get_viewport_source(self):
        import inspect, importlib
        vp = importlib.import_module('src.gui.viewport')
        return inspect.getsource(vp)

    def test_fps_last_wall_exists_after_init(self):
        """_fps_last_wall must be assigned in ViewportWidget source."""
        src = self._get_viewport_source()
        assert '_fps_last_wall' in src, \
            "_fps_last_wall not in viewport.py – FPS counter won't use wall-clock"
        # Ensure it's set to a perf_counter call (wall clock) not 0
        assert 'perf_counter' in src, \
            "time.perf_counter() should be used for wall-clock FPS"

    def test_fps_accum_initialized_to_zero(self):
        """_fps_accum / _fps_frames / _fps_display must be assigned 0 in source."""
        src = self._get_viewport_source()
        assert '_fps_accum' in src, "_fps_accum not found in viewport.py"
        assert '_fps_frames' in src, "_fps_frames not found in viewport.py"
        assert '_fps_display' in src, "_fps_display not found in viewport.py"
        import re
        # Find assignments of these attrs — they should be 0 initially
        accum_vals = re.findall(r'_fps_accum\s*=\s*([\d.]+)', src)
        assert accum_vals and float(accum_vals[0]) == 0.0, \
            f"_fps_accum should be initialised to 0, found: {accum_vals}"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-7  Watchdog uses module-level _time_mod (no per-tick import)
# ─────────────────────────────────────────────────────────────────────────────

class TestWatchdogTimeModule:
    """Verify module-level _time_mod is available (no per-tick import time)."""

    def test_time_mod_available_at_module_level(self):
        import src.gui.viewport as vp_mod
        assert hasattr(vp_mod, '_time_mod'), \
            "_time_mod not imported at module level in viewport.py"

    def test_time_mod_is_time_module(self):
        import src.gui.viewport as vp_mod
        import time as _t
        assert vp_mod._time_mod is _t, \
            "_time_mod should be the standard 'time' module"

    def test_no_lazy_import_time_in_schedule_render(self):
        """
        _schedule_render should NOT contain an executable 'import time' statement.
        Comments may reference 'import time' for documentation; we only check for
        actual import statements (not inside comment lines starting with #).
        """
        import inspect
        from src.gui.viewport import ViewportWidget
        src_code = inspect.getsource(ViewportWidget._schedule_render)
        # Check non-comment lines only
        non_comment_lines = [
            line for line in src_code.splitlines()
            if not line.lstrip().startswith('#')
        ]
        for line in non_comment_lines:
            assert 'import time' not in line, \
                f"_schedule_render still has inline 'import time' on line: {line!r}"

    def test_no_lazy_import_time_in_do_render(self):
        """_do_render should not contain inline 'import time'."""
        import inspect
        from src.gui.viewport import ViewportWidget
        src_code = inspect.getsource(ViewportWidget._do_render)
        assert 'import time' not in src_code, \
            "_do_render still has inline 'import time' — fix not applied"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-8  _draw_mesh_textured reads _lq_tex_mode as direct attribute
# ─────────────────────────────────────────────────────────────────────────────

class TestDrawMeshTexturedLqAccess:
    """_draw_mesh_textured must access _lq_tex_mode as self._lq_tex_mode, not getattr."""

    def test_no_getattr_lq_tex_mode_in_draw_mesh_textured(self):
        import inspect
        from src.gui.viewport import FrameRenderer
        src_code = inspect.getsource(FrameRenderer._draw_mesh_textured)
        # Should not use getattr for _lq_tex_mode anymore
        assert "getattr(self, '_lq_tex_mode'" not in src_code, \
            "_draw_mesh_textured still uses getattr for _lq_tex_mode – FIX-1 not applied"

    def test_lq_tex_mode_direct_read_present(self):
        """Confirm self._lq_tex_mode is still referenced in the method."""
        import inspect
        from src.gui.viewport import FrameRenderer
        src_code = inspect.getsource(FrameRenderer._draw_mesh_textured)
        assert '_lq_tex_mode' in src_code, \
            "_lq_tex_mode reference missing from _draw_mesh_textured entirely"


# ─────────────────────────────────────────────────────────────────────────────
#  Regression: UV seam guard still works post-refactor
# ─────────────────────────────────────────────────────────────────────────────

class TestUVSeamGuardRegression:
    """Ensure v10.3 seam guard logic still passes after v10.4 attribute changes."""

    def test_uv_sentinel_guard_value(self):
        from src.gui.viewport import _UV_SENTINEL
        # Phase 18: raised from 20.0 to 100.0 to avoid filtering legitimate
        # large-UV meshes (mRobe2_g U=[-13.58, 13.58], etc.)
        assert _UV_SENTINEL == 100.0, f"Expected 100.0 (Phase 18 update), got {_UV_SENTINEL}"

    def test_uwrap_global_within_half(self):
        from src.gui.viewport import _uwrap_global
        result = _uwrap_global(0.9, 0.05)
        # Should wrap 0.05 to 1.05 (within +0.5 of 0.9)
        assert abs(result - 1.05) < 1e-9, f"Expected 1.05, got {result}"

    def test_uwrap_global_no_wrap_needed(self):
        from src.gui.viewport import _uwrap_global
        result = _uwrap_global(0.3, 0.5)
        assert abs(result - 0.5) < 1e-9  # already within ±0.5

    def test_edge_has_seam_detects_seam(self):
        from src.gui.viewport import _edge_has_seam_global
        # 0.95 → 0.05 is a seam (raw dist=0.90, wrap dist≈0.10)
        assert _edge_has_seam_global(0.95, 0.05) is True

    def test_edge_has_seam_no_seam(self):
        from src.gui.viewport import _edge_has_seam_global
        # 0.3 → 0.7 is not a seam (raw dist=0.4, no wrapping shortens it)
        assert _edge_has_seam_global(0.3, 0.7) is False

    def test_vflip_nontiled(self):
        from src.gui.viewport import _vflip_nontiled
        # KotOR MDX UVs use OpenGL convention (V=0=bottom).
        # PIL images are top-down (row 0=top).
        # Flip formula: tv = (1.0 - v) * th
        # v=0 (GL bottom) → (1-0)*256 = 256.0  (bottom of PIL image)
        assert _vflip_nontiled(0.0, 256.0) == 256.0
        # v=1 (GL top) → (1-1)*256 = 0.0  (top of PIL image = row 0)
        assert _vflip_nontiled(1.0, 256.0) == 0.0
        # midpoint
        assert abs(_vflip_nontiled(0.5, 256.0) - 128.0) < 1e-9

    def test_vflip_tiled(self):
        from src.gui.viewport import _vflip_tiled
        # Tiled path uses same GL V=0=bottom convention.
        # tv = (tile_v - v) * src_h
        # tile_v=1, src_h=256, v=0: (1-0)*256 = 256.0
        assert _vflip_tiled(0.0, 1.0, 256.0) == 256.0
        # v=1: (1-1)*256 = 0.0
        assert _vflip_tiled(1.0, 1.0, 256.0) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Integration: FrameRenderer lq lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestLqTexModeLifecycle:
    """Full lifecycle: init → set → model change → verify reset."""

    def test_lq_lifecycle_init_set_reset(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())

        # 1. After init: False
        assert r._lq_tex_mode is False

        # 2. Simulate drag-release: set True
        r._lq_tex_mode = True
        assert r._lq_tex_mode is True

        # 3. Load new model: should reset to False
        r.set_model(_make_tiny_model())
        assert r._lq_tex_mode is False, \
            "Model load must reset _lq_tex_mode to prevent stale LQ render"

    def test_lq_lifecycle_none_model_reset(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        r._lq_tex_mode = True
        r.set_model(None)
        assert r._lq_tex_mode is False

    def test_lq_lifecycle_multiple_model_loads(self):
        from src.gui.viewport import FrameRenderer
        r = FrameRenderer(_make_camera())
        for _ in range(5):
            r._lq_tex_mode = True
            r.set_model(_make_tiny_model())
            assert r._lq_tex_mode is False, \
                "Repeated model loads must each reset _lq_tex_mode"


# ─────────────────────────────────────────────────────────────────────────────
#  Render-queue bounded test (no blocking)
# ─────────────────────────────────────────────────────────────────────────────

class TestRenderQueueBounded:
    """Render result queue must be bounded (maxsize=2) to prevent memory growth.

    Verified by source-code inspection — no Tk display required.
    """

    def test_render_queue_maxsize(self):
        """Queue(maxsize=2) must appear in ViewportWidget source."""
        import inspect, importlib
        vp = importlib.import_module('src.gui.viewport')
        src = inspect.getsource(vp)
        # The queue must be constructed with maxsize=2 (or Queue(2))
        import re
        # Match Queue(maxsize=2) or Queue(2)
        matches = re.findall(r'Queue\s*\(\s*(?:maxsize\s*=\s*)?(\d+)\s*\)', src)
        assert any(int(m) == 2 for m in matches), (
            f"Expected Queue(maxsize=2) in viewport.py, found Queue sizes: {matches}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Float sort key (UE5 depth sort)
# ─────────────────────────────────────────────────────────────────────────────

class TestFloatSortKey:
    """_float_to_sort_key must preserve depth ordering."""

    def test_positive_depths_sort_ascending(self):
        from src.gui.viewport import _float_to_sort_key
        depths = [0.5, 1.0, 2.0, 10.0, 100.0]
        keys = [_float_to_sort_key(d) for d in depths]
        assert keys == sorted(keys), \
            "Positive depths must produce ascending sort keys"

    def test_negative_before_positive(self):
        from src.gui.viewport import _float_to_sort_key
        k_neg = _float_to_sort_key(-1.0)
        k_pos = _float_to_sort_key(1.0)
        assert k_neg < k_pos, "Negative depth key must be < positive depth key"

    def test_zero_key(self):
        from src.gui.viewport import _float_to_sort_key
        # Should not raise
        k = _float_to_sort_key(0.0)
        assert isinstance(k, int)

    def test_integer_return_type(self):
        from src.gui.viewport import _float_to_sort_key
        assert isinstance(_float_to_sort_key(5.0), int)
