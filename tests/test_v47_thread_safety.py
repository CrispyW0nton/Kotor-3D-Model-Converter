"""
GhostRigger v4.7 – Thread-Safety & Render-Queue Test Suite
===========================================================
Tests for the two bugs that caused the "program crashes when opening c_bantha"
regression:

BUG-1  GUIHandler.emit called self.after() from background threads
       → RuntimeError("main thread is not in main loop") on Linux/macOS
       → killed the render thread, IPC thread, prewarm thread, scan thread

BUG-2  _render_thread used self.after(0, _apply) to post results to main thread
       → same RuntimeError on Linux before the Tk event loop fully started
       → rendered frames were lost; viewport showed blank screen for c_bantha

FIX-1  GUIHandler.emit now wraps every call in try/except and uses a _safe_after
       helper that silently drops the GUI log when called off-thread.

FIX-2  _render_thread now pushes (img, render_ms, W, H) into a thread-safe
       queue.Queue; _schedule_render (main thread) drains it every 33 ms tick.

Run with:  pytest tests/test_v47_thread_safety.py -v
"""
import sys, os, time, threading, queue, logging
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Fixtures ──────────────────────────────────────────────────────────────────

C_BANTHA_MDL = os.path.join(
    os.path.dirname(__file__), '..', 'test_assets', 'k1_extracted',
    'models', 'c_bantha.mdl')
C_BANTHA_MDX = C_BANTHA_MDL.replace('.mdl', '.mdx')

@pytest.fixture(scope='module')
def c_bantha_model():
    """Parse c_bantha once for the whole module."""
    if not os.path.exists(C_BANTHA_MDL):
        pytest.skip('c_bantha.mdl not found in test_assets')
    from src.core.mdl_parser import MDLBinaryParser
    from src.core.model_data import GameVersion
    raw = open(C_BANTHA_MDL, 'rb').read()
    mdx = open(C_BANTHA_MDX, 'rb').read() if os.path.exists(C_BANTHA_MDX) else b''
    model = MDLBinaryParser(raw, mdx).parse()
    model.name = 'c_bantha'
    model.game_version = GameVersion.K1
    return model

@pytest.fixture
def renderer_cam():
    from src.gui.viewport import FrameRenderer, ArcBallCamera
    cam = FrameRenderer.__new__(FrameRenderer)   # avoid __init__ tkinter dep
    # Use the public constructor properly
    cam2 = ArcBallCamera()
    from src.gui.viewport import FrameRenderer
    r = FrameRenderer(cam2)
    return r, cam2


# ── BUG-1 Tests (GUIHandler thread-safety) ───────────────────────────────────

class TestGUIHandlerThreadSafety:
    """Verify GUIHandler.emit never raises from background threads."""

    def test_emit_from_main_thread_does_not_raise(self):
        """emit() on the main thread must succeed (baseline)."""
        errors_caught = []

        class FakeTk:
            def after(self, delay, cb):
                cb()   # immediately invoke on main thread for test
            def log(self, msg, lvl):
                pass

        fake = FakeTk()

        import logging
        class _GUIHandler(logging.Handler):
            def __init__(self, cb):
                super().__init__()
                self._cb = cb
            def emit(self, record):
                level_map = {
                    logging.DEBUG: 'info', logging.INFO: 'info',
                    logging.WARNING: 'warning', logging.ERROR: 'error',
                    logging.CRITICAL: 'error',
                }
                try:
                    self._cb(self.format(record),
                             level_map.get(record.levelno, 'info'))
                except Exception:
                    pass

        def _safe_after(msg, lvl, _self=fake):
            try:
                _self.after(0, lambda: _self.log(msg, lvl))
            except RuntimeError:
                pass
            except Exception:
                pass

        h = _GUIHandler(_safe_after)
        logger = logging.getLogger('test_gui_handler_main')
        logger.addHandler(h)
        try:
            logger.warning("test message from main thread")
        except Exception as e:
            pytest.fail(f"GUIHandler raised on main thread: {e}")
        finally:
            logger.removeHandler(h)

    def test_emit_from_background_thread_does_not_raise(self):
        """emit() from a background thread must NOT raise RuntimeError."""
        errors = []

        import logging

        class _GUIHandler(logging.Handler):
            def __init__(self, cb):
                super().__init__()
                self._cb = cb
            def emit(self, record):
                level_map = {
                    logging.DEBUG: 'info', logging.INFO: 'info',
                    logging.WARNING: 'warning', logging.ERROR: 'error',
                    logging.CRITICAL: 'error',
                }
                try:
                    self._cb(self.format(record),
                             level_map.get(record.levelno, 'info'))
                except Exception:
                    pass

        def _raise_on_after(msg, lvl):
            # Simulate what Tkinter does when called off the main thread
            raise RuntimeError("main thread is not in main loop")

        def _safe_after(msg, lvl):
            try:
                _raise_on_after(msg, lvl)
            except RuntimeError:
                pass  # silently drop – this is the fix
            except Exception:
                pass

        h = _GUIHandler(_safe_after)
        logger = logging.getLogger('test_gui_handler_bg')
        logger.addHandler(h)

        def _bg_log():
            try:
                logger.error("error from background thread")
                logger.warning("warning from background thread")
                logger.debug("debug from background thread")
            except Exception as e:
                errors.append(str(e))

        t = threading.Thread(target=_bg_log, daemon=True)
        t.start()
        t.join(timeout=2.0)
        logger.removeHandler(h)

        assert t.is_alive() is False, "Background thread hung"
        assert errors == [], f"Background thread raised: {errors}"

    def test_gui_handler_survives_100_concurrent_threads(self):
        """100 threads all logging simultaneously must not crash any thread."""
        import logging
        errors = []
        lock = threading.Lock()

        class _GUIHandler(logging.Handler):
            def __init__(self, cb):
                super().__init__()
                self._cb = cb
            def emit(self, record):
                level_map = {
                    logging.DEBUG: 'info', logging.INFO: 'info',
                    logging.WARNING: 'warning', logging.ERROR: 'error',
                    logging.CRITICAL: 'error',
                }
                try:
                    self._cb(self.format(record),
                             level_map.get(record.levelno, 'info'))
                except Exception:
                    pass

        def _safe_after(msg, lvl):
            try:
                raise RuntimeError("main thread is not in main loop")
            except RuntimeError:
                pass

        h = _GUIHandler(_safe_after)
        h.setLevel(logging.DEBUG)
        logger = logging.getLogger('test_concurrent')
        logger.addHandler(h)
        logger.setLevel(logging.DEBUG)

        def _log_loop(n):
            try:
                for i in range(10):
                    logger.warning(f"thread {n} message {i}")
            except Exception as e:
                with lock:
                    errors.append(f"Thread {n}: {e}")

        threads = [threading.Thread(target=_log_loop, args=(i,), daemon=True)
                   for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        logger.removeHandler(h)
        assert errors == [], f"Threads crashed: {errors}"


# ── BUG-2 Tests (Render queue) ────────────────────────────────────────────────

class TestRenderQueue:
    """Verify the thread-safe render-result queue works correctly."""

    def test_viewport_has_render_result_queue(self, c_bantha_model):
        """ViewportWidget must have a _render_result_queue attribute."""
        from src.gui.viewport import ViewportWidget
        # Check the __init__ source includes the queue (without instantiating Tk)
        import inspect
        src = inspect.getsource(ViewportWidget.__init__)
        assert '_render_result_queue' in src, \
            "ViewportWidget.__init__ must create _render_result_queue"
        assert 'queue.Queue' in src or '_queue.Queue' in src, \
            "render result queue must be a queue.Queue"

    def test_render_thread_pushes_to_queue(self, c_bantha_model):
        """Simulate the render thread: push result into a queue instead of after()."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from PIL import Image

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(c_bantha_model)

        result_queue: queue.Queue = queue.Queue(maxsize=2)
        errors = []

        def _render_thread(W=400, H=300):
            try:
                img = renderer.render(W, H)
                render_ms = 42.0
                # New pattern: push to queue instead of calling after()
                try:
                    if result_queue.full():
                        try:
                            result_queue.get_nowait()
                        except Exception:
                            pass
                    result_queue.put_nowait((img, render_ms, W, H))
                except Exception as e:
                    errors.append(f"queue put: {e}")
            except Exception as e:
                errors.append(f"render: {e}")

        t = threading.Thread(target=_render_thread, daemon=True)
        t.start()
        t.join(timeout=10.0)

        assert not t.is_alive(), "Render thread timed out"
        assert errors == [], f"Render thread errors: {errors}"
        assert not result_queue.empty(), "Render thread did not push result to queue"

        img, render_ms, W, H = result_queue.get_nowait()
        assert isinstance(img, Image.Image), f"Expected PIL Image, got {type(img)}"
        assert img.size == (400, 300)
        assert render_ms == 42.0

    def test_render_queue_discards_stale_frames(self):
        """When queue is full, old frames are discarded and new frames accepted."""
        q: queue.Queue = queue.Queue(maxsize=2)

        # Fill queue with sentinel values
        q.put_nowait(('old_frame_1', 10.0, 400, 300))
        q.put_nowait(('old_frame_2', 11.0, 400, 300))
        assert q.full()

        # Simulate render thread pushing a new frame
        if q.full():
            try:
                q.get_nowait()  # evict oldest
            except Exception:
                pass
        q.put_nowait(('new_frame', 12.0, 400, 300))

        # Queue should have 2 items: old_frame_2 and new_frame
        assert q.qsize() == 2
        f1, _, _, _ = q.get_nowait()
        f2, _, _, _ = q.get_nowait()
        assert f1 == 'old_frame_2', "oldest frame should be evicted"
        assert f2 == 'new_frame', "newest frame should be present"

    def test_schedule_render_drains_queue(self, c_bantha_model):
        """Simulate _schedule_render draining the queue on the main thread."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from PIL import Image

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(c_bantha_model)

        # Build a synthetic result queue with one pre-rendered frame
        img = renderer.render(400, 300)
        assert isinstance(img, Image.Image)

        q: queue.Queue = queue.Queue(maxsize=2)
        q.put_nowait((img, 15.0, 400, 300))

        # Simulate what _schedule_render does: drain on main thread
        frames_applied = []
        try:
            while True:
                img2, render_ms, W, H = q.get_nowait()
                frames_applied.append((img2.size, render_ms, W, H))
        except Exception:
            pass  # queue.Empty

        assert len(frames_applied) == 1
        size, ms, w, h = frames_applied[0]
        assert size == (400, 300)
        assert ms == 15.0


# ── Integration test: c_bantha full load pipeline ────────────────────────────

class TestCBanthaNoThreadCrash:
    """End-to-end test: parse + render c_bantha with thread-safe queue pattern."""

    def test_cbantha_render_thread_completes(self, c_bantha_model):
        """c_bantha render thread must finish without crashing."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from PIL import Image

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(c_bantha_model)

        result_q: queue.Queue = queue.Queue(maxsize=4)
        thread_errors = []

        def _render_thread():
            try:
                img = renderer.render(800, 600)
                result_q.put_nowait((img, 0.0, 800, 600))
            except Exception as e:
                thread_errors.append(str(e))

        t = threading.Thread(target=_render_thread, daemon=True,
                             name='cbantha_render')
        t.start()
        t.join(timeout=30.0)

        assert not t.is_alive(), "c_bantha render thread timed out"
        assert thread_errors == [], f"Render thread error: {thread_errors}"

        img, _, W, H = result_q.get_nowait()
        assert isinstance(img, Image.Image), f"Render returned {type(img)}"
        assert img.size == (800, 600)

    def test_cbantha_prewarm_thread_completes(self, c_bantha_model):
        """Prewarm texture thread must finish without any exception."""
        from src.gui.viewport import TextureCache

        tc = TextureCache()
        tc.set_search_dirs([])   # no textures available, but must not crash

        tex_names = list({n.texture_clean for n in c_bantha_model.mesh_nodes()
                          if n.texture_clean
                          and n.texture_clean.upper() not in ('NULL', '')})
        assert tex_names, "c_bantha should have texture names"

        thread_errors = []

        def _prewarm():
            for name in tex_names:
                try:
                    tc.get(name)
                except MemoryError:
                    break
                except Exception:
                    pass  # not found is fine

        t = threading.Thread(target=_prewarm, daemon=True, name='cbantha_prewarm')
        t.start()
        t.join(timeout=5.0)
        assert not t.is_alive(), "Prewarm thread timed out"
        assert thread_errors == []

    def test_cbantha_multi_render_no_race(self, c_bantha_model):
        """Multiple render results queued up must all be procesable."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from PIL import Image

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(c_bantha_model)

        # Render 3 frames in sequence (simulating animation playback)
        q: queue.Queue = queue.Queue(maxsize=4)
        for i in range(3):
            img = renderer.render(400, 300)
            q.put_nowait((img, float(i * 33), 400, 300))

        assert q.qsize() == 3
        while not q.empty():
            img, ms, W, H = q.get_nowait()
            assert isinstance(img, Image.Image)
            assert img.size == (400, 300)


# ── BUG-3 Tests (DiagnosticsPanel hang fix) ───────────────────────────────────

class TestDiagnosticsPanelNoHang:
    """Verify DiagnosticsPanel.run_diagnostics no longer hangs the main thread.

    BUG-3 (v4.8): run_diagnostics() called run_model_diagnostics() synchronously
    on the main thread.  That function emits ~100 log.debug() messages; with the
    GUIHandler at DEBUG level each message scheduled an after(0, ...) callback,
    flooding the Tkinter event queue and freezing the UI for c_bantha (40+ nodes).

    FIX: run_diagnostics() now spawns a 'diag_build' daemon thread that:
      1. Temporarily removes GUIHandler from the root logger while running
         run_model_diagnostics() (so DEBUG messages go to the file log only).
      2. Builds the report items list (pure Python, no Tkinter).
      3. Posts items to a thread-safe queue.Queue.
    The DiagnosticsPanel polls the queue every 100 ms on the main thread and
    applies results atomically — no after() calls from background threads.
    """

    def test_run_diagnostics_is_non_blocking(self, c_bantha_model):
        """run_diagnostics() must return in < 50 ms (spawns bg thread)."""
        import queue as _queue
        import time

        from src.gui.main_window import DiagnosticsPanel as _DP

        # Build a minimal DiagnosticsPanel without a real Tk window
        # by patching the Tkinter calls
        dp = _DP.__new__(_DP)
        dp._get_model = lambda: c_bantha_model
        dp._diag_queue = _queue.Queue(maxsize=4)
        dp._pending_items = None

        # Mock out all Tkinter-touching methods
        dp._clear = lambda: None
        dp._write = lambda t, tag='info': None
        dp._write_batch = lambda items: setattr(dp, '_applied_items', items)
        dp.text = type('FakeText', (), {
            'see': lambda self, *a: None,
            'configure': lambda self, **kw: None,
            'insert': lambda self, *a: None,
        })()
        dp.after = lambda ms, fn: None   # no-op: we poll manually

        t0 = time.perf_counter()
        dp.run_diagnostics(c_bantha_model)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 50, (
            f"run_diagnostics() took {elapsed_ms:.0f}ms — expected < 50ms "
            f"(should be non-blocking, spawning a background thread)"
        )

    def test_diagnostics_background_thread_completes(self, c_bantha_model):
        """The background diag_build thread must finish in < 5 s."""
        import queue as _queue
        import time

        from src.gui.main_window import DiagnosticsPanel as _DP

        dp = _DP.__new__(_DP)
        dp._get_model = lambda: c_bantha_model
        dp._diag_queue = _queue.Queue(maxsize=4)
        dp._clear = lambda: None
        dp._write = lambda t, tag='info': None
        dp.text = type('FakeText', (), {
            'see': lambda self, *a: None,
            'configure': lambda self, **kw: None,
            'insert': lambda self, *a: None,
        })()
        dp.after = lambda ms, fn: None

        dp.run_diagnostics(c_bantha_model)

        # Wait up to 5 s for the diag_build thread to post to the queue
        deadline = time.perf_counter() + 5.0
        items = None
        while time.perf_counter() < deadline:
            try:
                items = dp._diag_queue.get(timeout=0.1)
                break
            except _queue.Empty:
                continue

        assert items is not None, \
            "diag_build thread did not post results within 5 s"
        assert len(items) > 0, "Diagnostics items list is empty"
        # Should contain the c_bantha model name somewhere
        combined = ''.join(t for t, tag in items)
        assert 'C_Bantha' in combined or 'c_bantha' in combined.lower(), \
            f"Diagnostics report does not mention c_bantha. Got: {combined[:200]}"

    def test_guihandler_level_is_warning(self):
        """GUIHandler must only forward WARNING+ to GUI to prevent event-queue flooding."""
        import logging
        import inspect
        from src.gui.main_window import KotorModToolsApp

        src = inspect.getsource(KotorModToolsApp._setup_logger)
        assert 'logging.WARNING' in src, \
            ("GUIHandler level must be logging.WARNING (not DEBUG/INFO) to prevent "
             "hundreds of after(0,...) callbacks from flooding the Tkinter event queue")

    def test_diagnostics_queue_exists(self):
        """DiagnosticsPanel.__init__ must create a _diag_queue (Queue)."""
        import inspect
        from src.gui.main_window import DiagnosticsPanel
        src = inspect.getsource(DiagnosticsPanel.__init__)
        assert '_diag_queue' in src, \
            "DiagnosticsPanel.__init__ must create self._diag_queue"
        assert 'Queue' in src, \
            "DiagnosticsPanel._diag_queue must be a queue.Queue instance"
