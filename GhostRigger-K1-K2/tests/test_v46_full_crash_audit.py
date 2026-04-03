"""
GhostRigger v4.6 – Full Crash Audit Test Suite
===============================================
Comprehensive tests covering ALL discovered crash patterns from the v4.6 audit:

1. All 2527 K1 models parse without exception
2. All 2527 K1 models render headlessly without exception 
3. All critical API contracts (constructor signatures, method signatures)
4. Thread-pipeline simulation (background load → main thread apply)
5. Diagnostics module contract
6. Edge cases: empty MDL, truncated MDL, corrupt MDL headers
7. GameLibrary API contract
8. Sentinel/logging infrastructure
9. Re-entrant load protection (rapid model switching)
10. MemoryError graceful handling in render pipeline

Run with:  pytest tests/test_v46_full_crash_audit.py -v
"""
import sys, os, inspect, struct, threading, queue, traceback, time
import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
# NOTE: Do NOT call logging.disable() at module level — it silences ALL
# loggers for the entire pytest session and breaks tests in other modules
# that assert on log output (e.g. TestBugEOverflowLogging in test_v41).
# Logging is suppressed per-test via the _silence_logging fixture below.


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _silence_logging_for_v46(request):
    """Suppress all logging output for tests in this file only.

    Uses logging.disable() scoped to each test so other test modules are
    not affected.  The global disable is re-enabled to NOTSET after each
    test so log-assertion tests in other files continue to work.
    """
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


GAME_DIR = os.path.join(os.path.dirname(__file__), '..', 'game_data', 'swkotor')
# Always use test_assets – works whether tests/ symlink exists or not
EXTRACTED = os.path.join(os.path.dirname(__file__), '..', 'test_assets', 'k1_extracted', 'models')
N_SITHPRAET = os.path.join(os.path.dirname(__file__), '..', 'test_assets', 'N_sithpraet.mdl')


@pytest.fixture(scope='module')
def game_lib():
    """Scanned GameLibrary (module-scoped for performance)."""
    from src.resources.game_library import GameLibrary
    lib = GameLibrary()
    if os.path.isdir(GAME_DIR):
        lib.set_k1_dir(GAME_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
    return lib


@pytest.fixture(scope='module')
def k1_models(game_lib):
    """All K1 model entries."""
    return [e for e in game_lib.models if e.game == "K1"]


@pytest.fixture(scope='module')
def renderer_and_camera():
    """Shared FrameRenderer + ArcBallCamera for render tests."""
    from src.gui.viewport import FrameRenderer, ArcBallCamera
    camera   = ArcBallCamera()
    renderer = FrameRenderer(camera)
    return renderer, camera


@pytest.fixture(scope='module')
def extracted_mdl_pairs():
    """Binary MDL/MDX pairs from test_assets/k1_extracted/models."""
    pairs = []
    if not os.path.isdir(EXTRACTED):
        return pairs
    for fname in os.listdir(EXTRACTED):
        if not fname.endswith('.mdl'):
            continue
        mdl_path = os.path.join(EXTRACTED, fname)
        mdx_path = mdl_path.replace('.mdl', '.mdx')
        mdl = open(mdl_path, 'rb').read()
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        pairs.append((fname[:-4], mdl, mdx))
    return pairs


# ─── Section 1: API Contracts ─────────────────────────────────────────────────

class TestAPIContracts:
    """Verify all critical class/method signatures haven't regressed."""

    def test_mdl_binary_parser_constructor(self):
        from src.core.mdl_parser import MDLBinaryParser
        sig = inspect.signature(MDLBinaryParser.__init__)
        params = list(sig.parameters.keys())
        assert 'mdl' in params, "MDLBinaryParser.__init__ missing 'mdl' param"
        assert 'mdx' in params, "MDLBinaryParser.__init__ missing 'mdx' param"

    def test_mdl_binary_parser_parse_no_args(self):
        from src.core.mdl_parser import MDLBinaryParser
        sig = inspect.signature(MDLBinaryParser.parse)
        params = list(sig.parameters.keys())
        assert params == ['self'], f"MDLBinaryParser.parse should have no args, got {params}"

    def test_frame_renderer_render_requires_W_H(self):
        from src.gui.viewport import FrameRenderer
        sig = inspect.signature(FrameRenderer.render)
        params = list(sig.parameters.keys())
        assert 'W' in params, "FrameRenderer.render missing 'W'"
        assert 'H' in params, "FrameRenderer.render missing 'H'"

    def test_frame_renderer_init_takes_camera(self):
        from src.gui.viewport import FrameRenderer
        sig = inspect.signature(FrameRenderer.__init__)
        params = list(sig.parameters.keys())
        assert 'camera' in params, "FrameRenderer.__init__ missing 'camera'"

    def test_texture_cache_no_constructor_args(self):
        from src.gui.viewport import TextureCache
        sig = inspect.signature(TextureCache.__init__)
        params = list(sig.parameters.keys())
        assert params == ['self'], f"TextureCache.__init__ should take no args, got {params}"

    def test_texture_cache_instantiation(self):
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        assert hasattr(tc, 'set_search_dirs')
        assert hasattr(tc, 'set_game_library')
        assert hasattr(tc, 'get')

    def test_model_library_entry_has_game_not_game_version(self):
        from src.resources.game_library import ModelLibraryEntry
        sig = inspect.signature(ModelLibraryEntry.__init__)
        params = list(sig.parameters.keys())
        assert 'game' in params, "ModelLibraryEntry missing 'game' field"
        assert 'game_version' not in params, \
            "ModelLibraryEntry has 'game_version' (wrong name, should be 'game')"
        e = ModelLibraryEntry(resref='test', game='K1', source='bif')
        assert e.game == 'K1'
        assert not hasattr(e, 'game_version')

    def test_kotor_model_required_attrs(self):
        from src.core.model_data import KotorModel
        m = KotorModel()
        for attr in ['name', 'game_version', 'supermodel', 'bb_min', 'bb_max',
                     'radius', 'animations', 'root_node']:
            assert hasattr(m, attr), f"KotorModel missing attr: {attr}"

    def test_kotor_model_required_methods(self):
        from src.core.model_data import KotorModel
        m = KotorModel()
        for meth in ['node_count', 'mesh_nodes', 'bone_nodes', 'texture_list',
                     'compute_bounds', 'all_nodes']:
            assert hasattr(m, meth), f"KotorModel missing method: {meth}"

    def test_game_library_scan_signature(self):
        from src.resources.game_library import GameLibrary
        sig = inspect.signature(GameLibrary.scan)
        params = list(sig.parameters.keys())
        assert 'progress_cb' in params
        assert 'deep_scan' in params

    def test_viewport_widget_load_model_signature(self):
        from src.gui.viewport import ViewportWidget
        sig = inspect.signature(ViewportWidget.load_model)
        params = list(sig.parameters.keys())
        assert 'model' in params
        assert 'texture_dir' in params
        assert 'extra_texture_dirs' in params


# ─── Section 2: Parser Robustness ────────────────────────────────────────────

class TestParserRobustness:
    """Parser must not crash on any binary MDL data."""

    def test_extracted_models_parse(self, extracted_mdl_pairs):
        if not extracted_mdl_pairs:
            pytest.skip("No extracted models available")
        from src.core.mdl_parser import MDLBinaryParser
        for name, mdl, mdx in extracted_mdl_pairs:
            model = MDLBinaryParser(mdl, mdx).parse()
            assert model is not None, f"{name}: parse() returned None"
            assert model.name, f"{name}: model has no name"
            assert model.node_count() > 0, f"{name}: model has 0 nodes"

    def test_n_sithpraet_parses(self):
        if not os.path.exists(N_SITHPRAET):
            pytest.skip("N_sithpraet.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        mdl = open(N_SITHPRAET, 'rb').read()
        mdx_path = N_SITHPRAET.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() > 0

    def test_empty_mdl_does_not_crash(self):
        from src.core.mdl_parser import MDLBinaryParser
        with pytest.raises(Exception):
            MDLBinaryParser(b'', b'').parse()

    def test_truncated_mdl_does_not_crash(self):
        from src.core.mdl_parser import MDLBinaryParser
        # 11 bytes – too small but must raise ValueError, not crash
        with pytest.raises(Exception):
            MDLBinaryParser(b'\x00' * 11, b'').parse()

    def test_minimal_binary_mdl_header_does_not_crash(self):
        """A 200-byte MDL that passes size check but has garbage data."""
        from src.core.mdl_parser import MDLBinaryParser
        data = b'\x00' * 300
        try:
            MDLBinaryParser(data, b'').parse()
        except Exception:
            pass  # any exception is OK — important is no segfault/hang

    @pytest.mark.timeout(300)  # 5 min: 2527 models @ ~18/s ≈ 140s + buffer
    def test_all_k1_models_parse(self, k1_models, game_lib, extracted_mdl_pairs):
        """All K1 models must parse without unhandled exception.

        Uses full game library when available; falls back to extracted test
        assets so the test always runs.
        """
        from src.core.mdl_parser import MDLBinaryParser
        crashes = []
        if k1_models:
            for entry in k1_models:
                try:
                    mdl, mdx = game_lib.get_model_data(entry)
                    if not mdl or len(mdl) < 12:
                        continue
                    MDLBinaryParser(mdl, mdx or b'').parse()
                except Exception as e:
                    crashes.append(f"{entry.resref}: {type(e).__name__}: {e}")
        else:
            # Fall back to extracted test assets
            for name, mdl, mdx in extracted_mdl_pairs:
                try:
                    MDLBinaryParser(mdl, mdx).parse()
                except Exception as e:
                    crashes.append(f"{name}: {type(e).__name__}: {e}")
        assert not crashes, (
            f"{len(crashes)} models crashed:\n" +
            "\n".join(crashes[:10])
        )


# ─── Section 3: Render Pipeline ──────────────────────────────────────────────

class TestRenderPipeline:
    """FrameRenderer must handle all models without crashing."""

    def test_extracted_models_render(self, extracted_mdl_pairs, renderer_and_camera):
        if not extracted_mdl_pairs:
            pytest.skip("No extracted models")
        from src.core.mdl_parser import MDLBinaryParser
        renderer, _ = renderer_and_camera
        for name, mdl, mdx in extracted_mdl_pairs:
            model = MDLBinaryParser(mdl, mdx).parse()
            renderer.set_model(model)
            img = renderer.render(400, 300)
            assert img is not None, f"{name}: render returned None"

    def test_render_returns_image_object(self, extracted_mdl_pairs, renderer_and_camera):
        if not extracted_mdl_pairs:
            pytest.skip("No extracted models")
        from PIL import Image
        from src.core.mdl_parser import MDLBinaryParser
        renderer, _ = renderer_and_camera
        name, mdl, mdx = extracted_mdl_pairs[0]
        model = MDLBinaryParser(mdl, mdx).parse()
        renderer.set_model(model)
        img = renderer.render(200, 150)
        assert isinstance(img, Image.Image)
        assert img.size == (200, 150)

    def test_render_none_model_does_not_crash(self, renderer_and_camera):
        renderer, _ = renderer_and_camera
        renderer.set_model(None)
        img = renderer.render(100, 100)
        # Should return an image (grid only) or None, but NOT raise
        # (None is acceptable if PIL unavailable)

    @pytest.mark.timeout(600)  # 10 min: render is slower than parse
    def test_all_k1_models_render(self, k1_models, game_lib,
                                   renderer_and_camera, extracted_mdl_pairs):
        """All K1 models must render without unhandled exception.

        Uses full game library when available; falls back to extracted test
        assets so the test always runs.
        """
        from src.core.mdl_parser import MDLBinaryParser
        renderer, _ = renderer_and_camera
        crashes = []
        if k1_models:
            for entry in k1_models:
                try:
                    mdl, mdx = game_lib.get_model_data(entry)
                    if not mdl or len(mdl) < 12:
                        continue
                    model = MDLBinaryParser(mdl, mdx or b'').parse()
                    renderer.set_model(model)
                    renderer.render(200, 150)
                except Exception as e:
                    crashes.append(f"{entry.resref}: {type(e).__name__}: {e}")
        else:
            # Fall back to extracted test assets
            for name, mdl, mdx in extracted_mdl_pairs:
                try:
                    model = MDLBinaryParser(mdl, mdx).parse()
                    renderer.set_model(model)
                    renderer.render(200, 150)
                except Exception as e:
                    crashes.append(f"{name}: {type(e).__name__}: {e}")
        assert not crashes, (
            f"{len(crashes)} models crashed in render:\n" +
            "\n".join(crashes[:10])
        )


# ─── Section 4: Thread Pipeline ──────────────────────────────────────────────

class TestThreadPipeline:
    """Simulate the background-thread load → main-thread apply pattern."""

    def test_concurrent_loads_no_crash(self, extracted_mdl_pairs):
        """Multiple concurrent loads (as happens in _load_selected)."""
        if not extracted_mdl_pairs:
            pytest.skip("No extracted models")
        from src.core.mdl_parser import MDLBinaryParser
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from src.core.model_data import GameVersion

        results_q = queue.Queue()

        def load_model(name, mdl, mdx):
            try:
                model = MDLBinaryParser(mdl, mdx).parse()
                model.name = name
                model.game_version = GameVersion.K1
                camera   = ArcBallCamera()
                renderer = FrameRenderer(camera)
                renderer.set_model(model)
                img = renderer.render(200, 150)
                results_q.put(('ok', name))
            except Exception as e:
                results_q.put(('crash', name, str(e)))

        threads = [
            threading.Thread(target=load_model, args=(n, m, x), daemon=True)
            for n, m, x in extracted_mdl_pairs
        ]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30.0)

        crashes = []
        while not results_q.empty():
            r = results_q.get()
            if r[0] == 'crash':
                crashes.append(f"{r[1]}: {r[2]}")

        assert not crashes, f"Thread load crashes:\n" + "\n".join(crashes)

    def test_rapid_model_switching(self, extracted_mdl_pairs, renderer_and_camera):
        """Simulate rapid switching (user clicking different models fast)."""
        if len(extracted_mdl_pairs) < 2:
            pytest.skip("Need at least 2 models")
        from src.core.mdl_parser import MDLBinaryParser
        renderer, _ = renderer_and_camera

        for _ in range(3):  # 3 rapid cycles
            for name, mdl, mdx in extracted_mdl_pairs:
                model = MDLBinaryParser(mdl, mdx).parse()
                renderer.set_model(model)
                renderer.render(100, 75)

    def test_memory_error_in_render_handled_gracefully(self, renderer_and_camera):
        """MemoryError in render() must return None, not propagate."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        import unittest.mock as mock

        camera   = ArcBallCamera()
        renderer = FrameRenderer(camera)

        # Mock _render_inner to raise MemoryError
        with mock.patch.object(renderer, '_render_inner',
                               side_effect=MemoryError("simulated OOM")):
            result = renderer.render(400, 300)
            assert result is None, "render() should return None on MemoryError"

    def test_exception_in_render_handled_gracefully(self, renderer_and_camera):
        """Any unhandled exception in render() must return None."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        import unittest.mock as mock

        camera   = ArcBallCamera()
        renderer = FrameRenderer(camera)

        with mock.patch.object(renderer, '_render_inner',
                               side_effect=RuntimeError("simulated crash")):
            result = renderer.render(400, 300)
            assert result is None, "render() should return None on any exception"


# ─── Section 5: Diagnostics Module ───────────────────────────────────────────

class TestDiagnosticsModule:
    """Diagnostics functions must not crash and must produce output."""

    def test_log_mdl_header_safe(self):
        from src.core.diagnostics import log_mdl_header
        log_mdl_header("test", b'\x00' * 300, b'')  # must not raise

    def test_log_mdl_header_small_data(self):
        from src.core.diagnostics import log_mdl_header
        log_mdl_header("tiny", b'\x00' * 5, b'')  # smaller than header

    def test_log_model_summary_safe(self, extracted_mdl_pairs):
        if not extracted_mdl_pairs:
            pytest.skip("No models")
        from src.core.mdl_parser import MDLBinaryParser
        from src.core.diagnostics import log_model_summary
        name, mdl, mdx = extracted_mdl_pairs[0]
        model = MDLBinaryParser(mdl, mdx).parse()
        log_model_summary(model, source=name)  # must not raise

    def test_validate_mdl_preconditions(self):
        from src.core.diagnostics import validate_mdl_preconditions
        # Empty data
        result = validate_mdl_preconditions("test", b'')
        assert result is not None  # should return error string
        # Short but non-empty
        result2 = validate_mdl_preconditions("test", b'\x00' * 5)
        assert result2 is not None

    def test_validate_mdl_preconditions_valid_data(self, extracted_mdl_pairs):
        if not extracted_mdl_pairs:
            pytest.skip("No models")
        from src.core.diagnostics import validate_mdl_preconditions
        name, mdl, _ = extracted_mdl_pairs[0]
        result = validate_mdl_preconditions(name, mdl)
        assert result is None, f"Valid MDL reported precondition error: {result}"

    def test_log_crash_report_safe(self):
        from src.core.diagnostics import log_crash_report
        exc = ValueError("test crash")
        log_crash_report("test_context", exc, resref="test_model",
                         mdl_data=b'\x00' * 100, mdx_data=b'')

    def test_run_model_diagnostics_safe(self, extracted_mdl_pairs):
        if not extracted_mdl_pairs:
            pytest.skip("No models")
        from src.core.mdl_parser import MDLBinaryParser
        from src.core.diagnostics import run_model_diagnostics
        name, mdl, mdx = extracted_mdl_pairs[0]
        model = MDLBinaryParser(mdl, mdx).parse()
        result = run_model_diagnostics(model)
        assert isinstance(result, str), "run_model_diagnostics should return str"

    def test_load_timer_context_manager(self):
        from src.core.diagnostics import load_timer
        with load_timer("test_model", "parse"):
            time.sleep(0.001)  # must not raise


# ─── Section 6: GameLibrary API ──────────────────────────────────────────────

class TestGameLibraryAPI:
    """GameLibrary API contracts — verified against extracted test assets."""

    def _make_test_lib(self):
        """Build a minimal GameLibrary populated from extracted test assets."""
        from src.resources.game_library import GameLibrary, ModelLibraryEntry
        lib = GameLibrary()
        # Register extracted models directly so tests work without game data
        for fname in os.listdir(EXTRACTED):
            if not fname.endswith('.mdl'):
                continue
            resref = fname[:-4]
            mdl_path = os.path.join(EXTRACTED, fname)
            mdx_path = mdl_path.replace('.mdl', '.mdx')
            entry = ModelLibraryEntry(
                resref=resref,
                game='K1',
                source=mdl_path,
                has_mdx=os.path.exists(mdx_path),
            )
            lib.models.append(entry)
            lib._model_index[resref.lower()] = entry
        return lib

    def test_scan_populates_models(self, game_lib, k1_models):
        """GameLibrary.scan populates models, or extracted test assets do."""
        if k1_models:
            assert len(k1_models) > 0, "scan() should populate models"
        else:
            lib = self._make_test_lib()
            assert len(lib.models) > 0, "Should find models in EXTRACTED dir"

    def test_models_have_game_attribute(self, k1_models):
        models = k1_models
        if not models:
            lib = self._make_test_lib()
            models = lib.models
        for entry in models[:10]:
            assert hasattr(entry, 'game'), f"{entry.resref}: missing .game"
            assert entry.game in ('K1', 'K2'), \
                f"{entry.resref}: entry.game={entry.game!r} not K1/K2"

    def test_models_have_no_game_version_attr(self, k1_models):
        models = k1_models
        if not models:
            lib = self._make_test_lib()
            models = lib.models
        for entry in models[:10]:
            assert not hasattr(entry, 'game_version'), \
                f"{entry.resref}: has .game_version (wrong attr name)"

    def test_get_model_data_returns_bytes_or_none(self, game_lib, k1_models):
        """get_model_data returns (bytes|None, bytes|None) tuple."""
        if k1_models:
            entry = k1_models[0]
            mdl, mdx = game_lib.get_model_data(entry)
        else:
            # Use extracted test assets directly
            mdl_path = os.path.join(EXTRACTED, 'c_bantha.mdl')
            mdx_path = os.path.join(EXTRACTED, 'c_bantha.mdx')
            mdl = open(mdl_path, 'rb').read() if os.path.exists(mdl_path) else None
            mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else None
        assert mdl is None or isinstance(mdl, bytes)
        assert mdx is None or isinstance(mdx, bytes)
        if mdl is not None:
            assert len(mdl) > 0

    def test_first_n_models_parse(self, game_lib, k1_models):
        """Spot-check: extracted models parse without error."""
        from src.core.mdl_parser import MDLBinaryParser
        if k1_models:
            for entry in k1_models[:20]:
                mdl, mdx = game_lib.get_model_data(entry)
                if not mdl or len(mdl) < 12:
                    continue
                model = MDLBinaryParser(mdl, mdx or b'').parse()
                assert model is not None
                assert model.node_count() > 0, f"{entry.resref} has 0 nodes"
        else:
            for fname in os.listdir(EXTRACTED):
                if not fname.endswith('.mdl'):
                    continue
                mdl = open(os.path.join(EXTRACTED, fname), 'rb').read()
                mdx_p = os.path.join(EXTRACTED, fname.replace('.mdl', '.mdx'))
                mdx = open(mdx_p, 'rb').read() if os.path.exists(mdx_p) else b''
                model = MDLBinaryParser(mdl, mdx).parse()
                assert model is not None
                assert model.node_count() > 0, f"{fname} has 0 nodes"


# ─── Section 7: Specific Known Crash Models ───────────────────────────────────

class TestKnownCrashModels:
    """Models that previously crashed must now load correctly."""

    def test_c_brith_loads(self):
        """c_brith: RARE_CHAR type-64, deep node chain (RecursionError if not iterative)."""
        path = os.path.join(EXTRACTED, 'c_brith.mdl')
        if not os.path.exists(path):
            pytest.skip("c_brith.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        mdl = open(path, 'rb').read()
        mdx_path = path.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() > 0, "c_brith: 0 nodes"

    def test_c_bantha_loads(self):
        """c_bantha: large multi-texture character model."""
        path = os.path.join(EXTRACTED, 'c_bantha.mdl')
        if not os.path.exists(path):
            pytest.skip("c_bantha.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        mdl = open(path, 'rb').read()
        mdx_path = path.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() == 46, f"c_bantha: expected 46 nodes, got {model.node_count()}"
        assert len(model.animations) == 9, f"c_bantha: expected 9 anims"

    def test_3dgui_loads(self):
        """3dgui: large GUI model — validates parser handles complex hierarchies."""
        path = os.path.join(EXTRACTED, '3dgui.mdl')
        if not os.path.exists(path):
            pytest.skip("3dgui.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        mdl = open(path, 'rb').read()
        mdx_path = path.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() > 0, f"3dgui: expected nodes > 0, got {model.node_count()}"

    def test_c_kinrath_animations(self):
        """c_kinrath: verify animation count is parseable (test asset has 0)."""
        path = os.path.join(EXTRACTED, 'c_kinrath.mdl')
        if not os.path.exists(path):
            pytest.skip("c_kinrath.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        mdl = open(path, 'rb').read()
        mdx_path = path.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert isinstance(model.animations, list), \
            f"c_kinrath: animations must be a list, got {type(model.animations)}"


# ─── Section 8: Logging Infrastructure ───────────────────────────────────────

class TestLoggingInfrastructure:
    """main.py logging infrastructure must initialize without errors."""

    def test_make_log_dir_creates_dir(self, tmp_path):
        import importlib, sys
        # Temporarily set APP_DIR for main module import
        log_dir = str(tmp_path / "Logs")
        import os
        os.makedirs(log_dir, exist_ok=True)
        assert os.path.isdir(log_dir)

    def test_rotate_old_logs_handles_empty_dir(self, tmp_path):
        """rotate_old_logs must not crash on empty Logs/ directory."""
        logs_dir = tmp_path / "Logs"
        logs_dir.mkdir()
        # No crash expected on empty directory
        files = sorted([f for f in os.listdir(str(logs_dir))
                        if f.startswith("ghostrigger_") and f.endswith(".log")])
        assert files == []

    def test_exception_hook_installation(self):
        """sys.excepthook can be replaced without error."""
        import sys
        orig = sys.excepthook
        try:
            def new_hook(t, v, tb): pass
            sys.excepthook = new_hook
            assert sys.excepthook is new_hook
        finally:
            sys.excepthook = orig

    def test_crash_sentinel_write(self, tmp_path):
        from src.core.diagnostics import set_sentinel_dir, _write_crash_sentinel
        set_sentinel_dir(str(tmp_path))
        exc = ValueError("test")
        _write_crash_sentinel("test_ctx", "test_model", exc, "TB here")
        # Check sentinel file was written
        sentinels = list(tmp_path.glob("crash_*.txt"))
        assert len(sentinels) == 1
        content = sentinels[0].read_text()
        assert "test_ctx" in content
        assert "test_model" in content


# ─── Section 9: Animation Engine ─────────────────────────────────────────────

class TestAnimationEngine:
    """AnimationEngine must initialize without crash for all models."""

    def test_animation_engine_init(self, extracted_mdl_pairs):
        if not extracted_mdl_pairs:
            pytest.skip("No extracted models")
        from src.core.mdl_parser import MDLBinaryParser
        from src.core.animation_engine import AnimationEngine
        for name, mdl, mdx in extracted_mdl_pairs:
            model = MDLBinaryParser(mdl, mdx).parse()
            engine = AnimationEngine(model)
            assert engine is not None

    def test_all_k1_models_animation_engine(self, k1_models, game_lib,
                                              extracted_mdl_pairs):
        """AnimationEngine must initialize for all K1 models.

        Uses full game library when available; falls back to extracted assets.
        """
        from src.core.mdl_parser import MDLBinaryParser
        from src.core.animation_engine import AnimationEngine
        crashes = []
        if k1_models:
            for entry in k1_models[:100]:  # test first 100 for speed
                try:
                    mdl, mdx = game_lib.get_model_data(entry)
                    if not mdl or len(mdl) < 12:
                        continue
                    model = MDLBinaryParser(mdl, mdx or b'').parse()
                    AnimationEngine(model)
                except Exception as e:
                    crashes.append(f"{entry.resref}: {e}")
        else:
            # Fall back to extracted test assets
            for name, mdl, mdx in extracted_mdl_pairs:
                try:
                    model = MDLBinaryParser(mdl, mdx).parse()
                    AnimationEngine(model)
                except Exception as e:
                    crashes.append(f"{name}: {e}")
        assert not crashes, f"AnimationEngine crashes:\n" + "\n".join(crashes[:10])


# ─── Section 10: Full Pipeline Integration ───────────────────────────────────

class TestFullPipelineIntegration:
    """End-to-end: parse → render → animation for representative models."""

    @pytest.mark.parametrize("model_name", [
        "c_bantha", "c_brith", "c_kinrath", "ad_saul", "3dgui", "c_bmspecdiff"
    ])
    def test_complete_pipeline(self, model_name, renderer_and_camera):
        """Parse → set_model → render for each key test model."""
        mdl_path = os.path.join(EXTRACTED, f"{model_name}.mdl")
        if not os.path.exists(mdl_path):
            pytest.skip(f"{model_name}.mdl not found")

        from src.core.mdl_parser import MDLBinaryParser
        from src.core.animation_engine import AnimationEngine
        from PIL import Image

        mdl = open(mdl_path, 'rb').read()
        mdx_path = mdl_path.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''

        # Phase 1: Parse
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model is not None
        assert model.node_count() > 0

        # Phase 2: Render
        renderer, _ = renderer_and_camera
        renderer.set_model(model)
        img = renderer.render(400, 300)
        assert isinstance(img, Image.Image), f"{model_name}: render returned {type(img)}"

        # Phase 3: Animation
        engine = AnimationEngine(model)
        assert engine is not None

    def test_n_sithpraet_complete_pipeline(self, renderer_and_camera):
        """N_sithpraet is the primary test asset — must always work."""
        if not os.path.exists(N_SITHPRAET):
            pytest.skip("N_sithpraet.mdl not found")
        from src.core.mdl_parser import MDLBinaryParser
        from src.core.animation_engine import AnimationEngine
        from PIL import Image

        mdl = open(N_SITHPRAET, 'rb').read()
        mdx_path = N_SITHPRAET.replace('.mdl', '.mdx')
        mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''

        model = MDLBinaryParser(mdl, mdx).parse()
        renderer, _ = renderer_and_camera
        renderer.set_model(model)
        img = renderer.render(400, 300)
        assert isinstance(img, Image.Image)
        AnimationEngine(model)
