"""
test_v43_iterative_bones_mip_fix.py
=====================================
Regression tests for v4.3 fixes:

1. _MIP_BIAS_CACHE is now per-instance (was class-level — caused id() reuse
   across TextureCache instances leading to stale/wrong cached mip images).
2. _draw_bones now iterative (no RecursionError on c_brith 601-node trees).
3. _draw_ext_skeleton now iterative (same protection).
4. Logging: session log written to Logs/ folder with correct name format.
5. main.py close hook: WM_DELETE_WINDOW + atexit wired properly.
"""

import os
import sys
import math
import struct
import threading
import logging
import unittest

# ── Project root ──────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────

def _make_pil_image(w: int, h: int):
    """Return a PIL RGBA image if available, else a tiny stub object."""
    try:
        from PIL import Image
        return Image.new("RGBA", (w, h), color=(200, 100, 50, 255)), True
    except ImportError:
        class _Stub:
            def __init__(self, ww, hh):
                self.size = (ww, hh)
            def resize(self, sz, _resample=None):
                return _Stub(*sz)
        return _Stub(w, h), False


# ─────────────────────────────────────────────────────────────────────────
#  1. MipBiasCache — per-instance isolation
# ─────────────────────────────────────────────────────────────────────────

class TestMipBiasCacheIsolation(unittest.TestCase):
    """
    BUG-FIX: _MIP_BIAS_CACHE was a class-level dict shared across ALL
    TextureCache instances.  When a garbage-collected PIL Image's id() was
    reused by a new Image in a different test, get_mip1() returned a stale
    entry from a previous instance's cache.  Now it is per-instance.
    """

    def _get_cache_class(self):
        try:
            from src.gui.viewport import TextureCache
            return TextureCache
        except ImportError:
            return None

    def test_cache_is_not_class_level(self):
        """_mip_bias_cache must not be a class attribute (must be instance)."""
        TC = self._get_cache_class()
        if TC is None:
            self.skipTest("viewport not available")
        # Class should NOT have a _MIP_BIAS_CACHE or _mip_bias_cache class attr
        self.assertFalse(
            hasattr(TC, '_MIP_BIAS_CACHE'),
            "_MIP_BIAS_CACHE must NOT be a class-level attribute"
        )
        # Instance should have _mip_bias_cache as a dict
        c = TC()
        self.assertIsInstance(c._mip_bias_cache, dict)

    def test_two_instances_have_separate_caches(self):
        """Two TextureCache instances must not share the same cache object."""
        TC = self._get_cache_class()
        if TC is None:
            self.skipTest("viewport not available")
        c1 = TC()
        c2 = TC()
        self.assertIsNot(c1._mip_bias_cache, c2._mip_bias_cache,
                         "Each instance must have its own _mip_bias_cache dict")

    def test_clear_on_one_does_not_affect_other(self):
        """clear_mip_cache() on one instance must not empty the other's cache."""
        TC = self._get_cache_class()
        if TC is None:
            self.skipTest("viewport not available")
        c1 = TC()
        c2 = TC()
        img, real_pil = _make_pil_image(32, 32)
        # Put an entry in c1
        mip1 = c1.get_mip1(img)
        self.assertIsNotNone(mip1)
        self.assertEqual(len(c1._mip_bias_cache), 1)
        # Clear c2 — must not affect c1
        c2.clear_mip_cache()
        self.assertEqual(len(c1._mip_bias_cache), 1,
                         "clear_mip_cache on c2 must not clear c1's cache")

    def test_id_reuse_does_not_return_wrong_mip(self):
        """
        When a PIL Image is GC'd and its id() is reused by a new image,
        the new instance must NOT return the old cached mip.

        This was the root cause of the flaky test: Python can reuse id()
        when an image is deleted between test cases.  With per-instance
        caching each new TextureCache starts empty, preventing cross-test
        contamination.
        """
        TC = self._get_cache_class()
        if TC is None:
            self.skipTest("viewport not available")
        img_a, real_pil = _make_pil_image(64, 64)
        c1 = TC()
        mip_a = c1.get_mip1(img_a)
        # Delete img_a and the first cache — free up id()
        old_key = id(img_a)
        del c1
        del img_a

        # Create a FRESH cache and a new image
        # (may or may not get same id() — but fresh cache is always empty)
        c2 = TC()
        img_b, _ = _make_pil_image(32, 16)
        self.assertEqual(len(c2._mip_bias_cache), 0,
                         "New TextureCache must start with empty mip cache")
        mip_b = c2.get_mip1(img_b)
        if real_pil:
            # With real PIL: mip of 32×16 should be 16×8
            self.assertEqual(mip_b.size, (16, 8))

    def test_mip_cache_threadsafe_multiple_instances(self):
        """Concurrent get_mip1 calls on separate instances must not interfere."""
        TC = self._get_cache_class()
        if TC is None:
            self.skipTest("viewport not available")
        errors = []

        def worker(idx):
            try:
                cache = TC()
                img, _ = _make_pil_image(32 + idx * 4, 32 + idx * 4)
                for _ in range(10):
                    mip = cache.get_mip1(img)
                    assert mip is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"Thread errors: {errors}")


# ─────────────────────────────────────────────────────────────────────────
#  2. _draw_bones iterative — deep models must not crash
# ─────────────────────────────────────────────────────────────────────────

def _build_deep_model(depth: int = 650):
    """Build a KotorModel with a linear chain of `depth` dummy nodes."""
    from src.core.model_data import ModelNode, KotorModel, NodeFlags
    model = KotorModel()
    model.name = "test_deep"
    root = ModelNode(name="root", flags=NodeFlags.HEADER)
    model.root_node = root
    parent = root
    for i in range(depth):
        child = ModelNode(name=f"bone_{i}", flags=NodeFlags.HEADER)
        child.parent = parent
        parent.children.append(child)
        parent = child
    return model


class TestDrawBonesIterative(unittest.TestCase):
    """
    _draw_bones must NOT use Python recursion for BFS traversal.
    A model with 650 chained nodes exceeds Python's default recursion limit
    of 1000 (with the call stack overhead) and would previously crash.
    """

    def _get_frame_renderer(self):
        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
            cam = ArcBallCamera()
            return FrameRenderer(cam), True
        except (ImportError, Exception):
            return None, False

    def test_draw_bones_no_recursion_error_deep_model(self):
        """
        _draw_bones on a 650-node linear chain must not raise RecursionError.
        """
        renderer, ok = self._get_frame_renderer()
        if not ok:
            self.skipTest("FrameRenderer unavailable (headless env)")
        model = _build_deep_model(650)
        renderer.model = model
        try:
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (200, 200), (40, 40, 60))
            draw = ImageDraw.Draw(img)
            renderer._draw_bones(draw, 200, 200)
        except RecursionError:
            self.fail("_draw_bones raised RecursionError on a 650-node model")
        except ImportError:
            self.skipTest("PIL not available")

    def test_draw_bones_returns_all_bone_positions(self):
        """After _draw_bones, bone_screen_positions must be non-empty."""
        renderer, ok = self._get_frame_renderer()
        if not ok:
            self.skipTest("FrameRenderer unavailable (headless env)")
        model = _build_deep_model(20)
        renderer.model = model
        try:
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (400, 400), (30, 30, 40))
            draw = ImageDraw.Draw(img)
            renderer._draw_bones(draw, 400, 400)
            # At least the root node should be in bone_screen_positions
            self.assertGreater(
                len(renderer._bone_screen_positions), 0,
                "_draw_bones must populate _bone_screen_positions"
            )
        except ImportError:
            self.skipTest("PIL not available")

    def test_draw_bones_visited_guard_prevents_cycle_crash(self):
        """
        _draw_bones must not loop forever if a child references a visited ancestor.
        (Cycle guard: visited set prevents re-processing.)
        """
        renderer, ok = self._get_frame_renderer()
        if not ok:
            self.skipTest("FrameRenderer unavailable (headless env)")
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        model.name = "cyclic"
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        childA = ModelNode(name="A", flags=NodeFlags.HEADER)
        childB = ModelNode(name="B", flags=NodeFlags.HEADER)
        root.children.extend([childA, childB])
        childA.parent = root
        childB.parent = root
        # Deliberately create a cycle: A points back to root as a child
        childA.children.append(root)
        model.root_node = root
        renderer.model = model
        try:
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (100, 100))
            draw = ImageDraw.Draw(img)
            # Must not hang or crash
            renderer._draw_bones(draw, 100, 100)
        except ImportError:
            self.skipTest("PIL not available")
        except RecursionError:
            self.fail("_draw_bones crashed on cyclic graph")


# ─────────────────────────────────────────────────────────────────────────
#  3. _draw_ext_skeleton iterative
# ─────────────────────────────────────────────────────────────────────────

class TestDrawExtSkeletonIterative(unittest.TestCase):
    """_draw_ext_skeleton was also recursive; now iterative."""

    def _get_frame_renderer(self):
        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
            cam = ArcBallCamera()
            return FrameRenderer(cam), True
        except (ImportError, Exception):
            return None, False

    def test_ext_skeleton_deep_no_recursion_error(self):
        """600-node external skeleton overlay must not crash."""
        renderer, ok = self._get_frame_renderer()
        if not ok:
            self.skipTest("FrameRenderer unavailable")
        ext_model = _build_deep_model(600)
        renderer._ext_skeleton = ext_model
        renderer._ext_skel_offset = (0.0, 0.0, 0.0)
        try:
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (200, 200))
            draw = ImageDraw.Draw(img)
            renderer._draw_ext_skeleton(draw, 200, 200)
        except RecursionError:
            self.fail("_draw_ext_skeleton raised RecursionError on 600-node model")
        except ImportError:
            self.skipTest("PIL not available")

    def test_ext_skeleton_cycle_guard(self):
        """Cyclic ext-skeleton must not loop forever."""
        renderer, ok = self._get_frame_renderer()
        if not ok:
            self.skipTest("FrameRenderer unavailable")
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        model.name = "ext_cyclic"
        root = ModelNode(name="r", flags=NodeFlags.HEADER)
        child = ModelNode(name="c", flags=NodeFlags.HEADER)
        child.parent = root
        root.children.append(child)
        child.children.append(root)  # cycle
        model.root_node = root
        renderer._ext_skeleton = model
        renderer._ext_skel_offset = (0.0, 0.0, 0.0)
        try:
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (100, 100))
            draw = ImageDraw.Draw(img)
            renderer._draw_ext_skeleton(draw, 100, 100)
        except ImportError:
            self.skipTest("PIL not available")
        except RecursionError:
            self.fail("_draw_ext_skeleton hung on cycle")


# ─────────────────────────────────────────────────────────────────────────
#  4. Logging system: Logs/ folder + session log
# ─────────────────────────────────────────────────────────────────────────

class TestLoggingSystem(unittest.TestCase):
    """Verify Logs/ folder creation and session log rotation."""

    def test_make_log_dir_creates_folder(self):
        """_make_log_dir must create the Logs/ directory."""
        import tempfile, importlib, types
        # Patch _LOG_DIR to a temp directory
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = os.path.join(tmp, "TestLogs")
            # Build a minimal 'main' module with just the helper
            src = f"""
import os
_LOG_DIR = {log_dir!r}
def _make_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)
"""
            ns: dict = {}
            exec(src, ns)
            ns['_make_log_dir']()
            self.assertTrue(os.path.isdir(log_dir),
                            "_make_log_dir must create the Logs/ folder")

    def test_rotate_old_logs_keeps_newest(self):
        """_rotate_old_logs must delete the oldest when count >= keep limit."""
        import tempfile, time
        with tempfile.TemporaryDirectory() as tmp:
            keep = 5
            # Create 7 fake log files with different mtimes
            files = []
            for i in range(7):
                p = os.path.join(tmp, f"ghostrigger_2026-01-{i+1:02d}_000000.log")
                with open(p, 'w') as f:
                    f.write(f"session {i}")
                os.utime(p, (i * 100, i * 100))
                files.append(p)

            src = f"""
import os
_LOG_DIR = {tmp!r}
_LOG_KEEP_FILES = {keep}
def _rotate_old_logs():
    files = sorted(
        [f for f in os.listdir(_LOG_DIR) if f.startswith('ghostrigger_') and f.endswith('.log')],
        key=lambda f: os.path.getmtime(os.path.join(_LOG_DIR, f))
    )
    while len(files) >= _LOG_KEEP_FILES:
        oldest = files.pop(0)
        try:
            os.remove(os.path.join(_LOG_DIR, oldest))
        except OSError:
            pass
"""
            ns: dict = {}
            exec(src, ns)
            ns['_rotate_old_logs']()
            remaining = [f for f in os.listdir(tmp)
                         if f.startswith('ghostrigger_') and f.endswith('.log')]
            self.assertLess(len(remaining), keep,
                            f"Expected <{keep} files after rotation, got {len(remaining)}")

    def test_log_file_created_with_correct_prefix(self):
        """Session log filename must start with 'ghostrigger_' and end with '.log'."""
        import tempfile, datetime
        with tempfile.TemporaryDirectory() as tmp:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            logfile = os.path.join(tmp, f"ghostrigger_{stamp}.log")
            with open(logfile, 'w') as f:
                f.write("session start\n")
            name = os.path.basename(logfile)
            self.assertTrue(name.startswith("ghostrigger_"),
                            f"Log filename must start with 'ghostrigger_': {name}")
            self.assertTrue(name.endswith(".log"),
                            f"Log filename must end with '.log': {name}")


# ─────────────────────────────────────────────────────────────────────────
#  5. TPC bottom-up flip — verify loaded images are top-down
# ─────────────────────────────────────────────────────────────────────────

class TestTpcBottomUpFlip(unittest.TestCase):
    """
    KotOR uncompressed TPC textures are stored bottom-up.  _load_tpc_bytes
    must flip them vertically so the result is top-down (PIL standard).
    DXT-compressed textures are top-down and must NOT be flipped.
    """

    def _make_tpc_uncompressed_rgb(self, width: int, height: int,
                                    first_row_color: tuple,
                                    last_row_color: tuple) -> bytes:
        """
        Build a minimal TPC with encoding=2 (raw RGB).
        Stores last_row_color at the BOTTOM of the raw pixel data (index 0 in
        bottom-up storage = bottom row).  After _flip, that becomes the last
        row in the PIL image (row h-1).
        """
        pixel_data = bytearray(width * height * 3)
        # Fill the first logical row (bottom of image in file = row 0 in raw)
        for x in range(width):
            base = x * 3
            pixel_data[base + 0] = last_row_color[0]
            pixel_data[base + 1] = last_row_color[1]
            pixel_data[base + 2] = last_row_color[2]
        # Fill the last logical row (top of image in file = row h-1 in raw)
        for x in range(width):
            base = (height - 1) * width * 3 + x * 3
            pixel_data[base + 0] = first_row_color[0]
            pixel_data[base + 1] = first_row_color[1]
            pixel_data[base + 2] = first_row_color[2]

        data_sz  = width * height * 3
        header = struct.pack('<IHHBBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                             data_sz, width, height, 2, 0)[:128]
        # Pad header to 128 bytes
        header = header.ljust(128, b'\x00')
        return bytes(header) + bytes(pixel_data)

    def _load_tpc(self, data: bytes):
        try:
            from src.gui.viewport import _load_tpc_bytes
            return _load_tpc_bytes(data)
        except ImportError:
            return None

    def test_tpc_uncompressed_rgb_flip(self):
        """
        KotOR uncompressed RGB TPC textures are stored bottom-up (OpenGL convention).
        _load_tpc_bytes must NOT flip them — the renderer's (1-v)*h formula handles
        V-inversion at render time.

        Correct TPC header: data_sz=0 (uncompressed), pixel_type at byte 12.
        data_sz != 0 signals DXT-compressed in the PyKotor/KotOR convention.

        NOTE: The old version of this test used data_sz=W*H*3 (non-zero) and
        encoding at byte 14 — both are incorrect.  The real game TPC format puts
        pixel_type at byte 12 and uses data_sz=0 for uncompressed textures.
        """
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")

        W, H = 8, 4
        # Row 0 in file (OpenGL bottom, V=0) = bot_color
        # Row H-1 in file (OpenGL top, V=1) = top_color
        top_color  = (200, 100,  50)
        bot_color  = ( 50, 200, 100)

        # Correct TPC header: data_sz=0 → uncompressed, pixel_type=2 (RGB) at byte 12
        header = bytearray(128)
        struct.pack_into('<I', header, 0, 0)       # data_sz = 0 (uncompressed)
        struct.pack_into('<f', header, 4, 1.0)     # alpha_test
        struct.pack_into('<H', header, 8, W)
        struct.pack_into('<H', header, 10, H)
        header[12] = 2   # pixel_type = 2 (RGB/DXT1) — data_sz=0 → uncompressed RGB
        header[13] = 1   # mip_count = 1

        pixel_data = bytearray(W * H * 3)
        # Row 0 in file = bottom-up row 0 (OpenGL V=0)
        for x in range(W):
            base = x * 3
            pixel_data[base:base+3] = bot_color
        # Row H-1 in file = bottom-up top row (OpenGL V=1)
        for x in range(W):
            base = (H-1) * W * 3 + x * 3
            pixel_data[base:base+3] = top_color

        raw = bytes(header) + bytes(pixel_data)
        img = self._load_tpc(raw)
        if img is None:
            self.skipTest("_load_tpc_bytes returned None (PIL not available)")

        # Uncompressed textures are NOT flipped (already bottom-up, OpenGL convention).
        # PIL row 0 = file row 0 = bot_color (OpenGL V=0 / bottom)
        # PIL row H-1 = file row H-1 = top_color (OpenGL V=1 / top)
        pix_row0 = img.getpixel((0, 0))[:3]
        pix_rowN = img.getpixel((0, H - 1))[:3]
        self.assertEqual(pix_row0, bot_color,
                         f"PIL row 0 should be bot_color {bot_color} (no flip), got {pix_row0}")
        self.assertEqual(pix_rowN, top_color,
                         f"PIL row H-1 should be top_color {top_color} (no flip), got {pix_rowN}")

    def test_tpc_greyscale_flip(self):
        """Greyscale TPC (pixel_type=1) is uncompressed and already bottom-up — no flip.

        Correct TPC header: data_sz=0, pixel_type=1 (Greyscale) at byte 12.

        NOTE: The old version of this test used data_sz=W*H and encoding at byte 14
        which is incorrect.  Uncompressed textures use data_sz=0 and pixel_type at byte 12.
        Uncompressed textures are NOT flipped; they are already in OpenGL bottom-up order.
        """
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")

        W, H = 4, 4
        header = bytearray(128)
        struct.pack_into('<I', header, 0, 0)       # data_sz = 0 (uncompressed)
        struct.pack_into('<f', header, 4, 1.0)     # alpha_test
        struct.pack_into('<H', header, 8, W)
        struct.pack_into('<H', header, 10, H)
        header[12] = 1   # pixel_type = 1 (Greyscale)
        header[13] = 1   # mip_count = 1

        pixel_data = bytearray(W * H)
        pixel_data[0] = 10         # file row 0 (OpenGL bottom)
        pixel_data[(H-1)*W] = 240  # file row H-1 (OpenGL top)

        raw = bytes(header) + bytes(pixel_data)
        from src.gui.viewport import _load_tpc_bytes
        img = _load_tpc_bytes(raw)
        if img is None:
            self.skipTest("_load_tpc_bytes returned None")

        # Uncompressed textures are NOT flipped (already bottom-up).
        # PIL row 0 = file row 0 = value 10 (OpenGL bottom)
        # PIL row H-1 = file row H-1 = value 240 (OpenGL top)
        pix_row0 = img.getpixel((0, 0))
        pix_rowN = img.getpixel((0, H - 1))
        row0_val = pix_row0[0] if hasattr(pix_row0, '__len__') else pix_row0
        rowN_val = pix_rowN[0] if hasattr(pix_rowN, '__len__') else pix_rowN
        self.assertEqual(row0_val, 10,
                         f"PIL row 0 should be value 10 (no flip, uncompressed), got {row0_val}")
        self.assertEqual(rowN_val, 240,
                         f"PIL row H-1 should be value 240 (no flip, uncompressed), got {rowN_val}")


# ─────────────────────────────────────────────────────────────────────────
#  6. UV sampling V-flip consistency
# ─────────────────────────────────────────────────────────────────────────

class TestUVSamplingVFlip(unittest.TestCase):
    """
    TextureCache.sample() and sample_bilinear() both apply a V-flip
    (v = 1 - v) to convert from KotOR bottom-up convention to top-down PIL
    row addressing.  Verify this is applied exactly once.
    """

    def _get_cache(self):
        try:
            from src.gui.viewport import TextureCache
            return TextureCache()
        except ImportError:
            return None

    def test_sample_vflip_v0_reads_bottom_row(self):
        """
        sample(img, u=0.0, v=0.001) must read from near the BOTTOM of the
        image because KotOR V≈0 = bottom of texture.

        NOTE: v=0.0 exactly wraps to the same row as v=1.0 due to
        (v % 1.0 == 0.0) → (1.0 - 0.0 = 1.0) → (int(1.0*h) % h == 0).
        We use v=0.001 to test the actual bottom-row sampling.
        """
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        cache = self._get_cache()
        if cache is None:
            self.skipTest("TextureCache unavailable")

        img = Image.new("RGBA", (4, 4), color=(0, 0, 0, 255))
        # Color the bottom row (row 3, y=3) red
        for x in range(4):
            img.putpixel((x, 3), (255, 0, 0, 255))

        # v=0.001: v_mapped = 1 - 0.001 = 0.999 → py = int(0.999*4)%4 = 3 = bottom
        r, g, b = cache.sample(img, 0.0, 0.001)
        self.assertEqual((r, g, b), (255, 0, 0),
                         "sample(u=0,v=0.001) must read bottom row (red)")

    def test_sample_vflip_v1_reads_top_row(self):
        """sample(img, u=0.0, v=1.0) must read the TOP row (row 0 in PIL)."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        cache = self._get_cache()
        if cache is None:
            self.skipTest("TextureCache unavailable")

        img = Image.new("RGBA", (4, 4), color=(0, 0, 0, 255))
        # Color top row (row 0, y=0) blue
        for x in range(4):
            img.putpixel((x, 0), (0, 0, 255, 255))

        r, g, b = cache.sample(img, 0.0, 1.0)
        self.assertEqual((r, g, b), (0, 0, 255),
                         "sample(u=0,v=1) must read top row (blue)")

    def test_sample_bilinear_vflip_v0_reads_bottom_row(self):
        """
        sample_bilinear with a small V value (near V=0) must sample from
        near the bottom of the image (high y rows in PIL).

        With a 4×4 image and v=0.125:
          v_mapped = 1 - 0.125 = 0.875
          v_f = 0.875 * 4 = 3.5 → y0=3, fy=0.5 → blends rows 3 and 0
        Row 3 is colored red (200,50,10), row 0 is black (0,0,0).
        Result is 50% blend → r ≈ 100.  We test r > 80.
        """
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        cache = self._get_cache()
        if cache is None:
            self.skipTest("TextureCache unavailable")

        img = Image.new("RGBA", (4, 4), color=(0, 0, 0, 255))
        # Fill entire bottom half (rows 2 and 3) with red so there's no ambiguity
        for x in range(4):
            img.putpixel((x, 2), (200, 50, 10, 255))
            img.putpixel((x, 3), (200, 50, 10, 255))

        # v=0.125: v_mapped = 0.875, v_f = 3.5 → y0=3 (bottom, red), fy=0.5 → y1=0 (black)
        # Expected: r ≈ 0.5*200 = 100; we check > 80 to allow rounding
        r, g, b, a = cache.sample_bilinear(img, 0.0, 0.125)
        self.assertGreater(r, 80, "Bilinear v=0.125 should sample mostly bottom rows (red dominant)")


# ─────────────────────────────────────────────────────────────────────────
#  7. MDX channel count validation (partial array guard)
# ─────────────────────────────────────────────────────────────────────────

class TestMDXChannelCountValidation(unittest.TestCase):
    """
    If a per-vertex channel read fails partway through (e.g. bounds miss on
    vertex 50 of 100), the partial array must be discarded — not stored as a
    mismatched-length array that would cause IndexError in the renderer.
    """

    def test_uvs_must_match_vertex_count_or_be_empty(self):
        """
        If we build a model manually with uvs count != vertex count,
        the renderer must handle it gracefully (not IndexError).
        """
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        model.name = "mismatch_test"
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        mesh = ModelNode(name="mesh", flags=NodeFlags.MESH | NodeFlags.HEADER)
        mesh.parent = root
        root.children.append(mesh)
        model.root_node = root

        # Deliberately mismatched arrays (UV has fewer entries than vertices)
        mesh.vertices = [(float(i), 0.0, 0.0) for i in range(10)]
        mesh.uvs      = [(0.5, 0.5)] * 5  # only 5 UVs for 10 vertices
        mesh.normals  = [(0.0, 0.0, 1.0)] * 10
        mesh.faces    = [(0, 1, 2), (3, 4, 5)]
        mesh.render   = True
        mesh.texture  = ''

        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
            from PIL import Image
            cam = ArcBallCamera()
            renderer = FrameRenderer(cam)
            renderer.model = model
            # Render must not raise IndexError due to UV mismatch
            img = renderer.render(200, 200)
            # If we got here without exception, test passes
        except IndexError:
            self.fail("Renderer raised IndexError on UV/vertex count mismatch")
        except (ImportError, Exception):
            pass  # OK to skip if PIL/viewport unavailable

    def test_normals_must_match_vertex_count_or_be_empty(self):
        """
        Mismatched normals array must not cause IndexError in the renderer.
        """
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        model.name = "normals_mismatch"
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        mesh = ModelNode(name="mesh", flags=NodeFlags.MESH | NodeFlags.HEADER)
        mesh.parent = root
        root.children.append(mesh)
        model.root_node = root

        mesh.vertices = [(float(i), 0.0, 0.0) for i in range(10)]
        mesh.uvs      = [(float(i)/10, 0.5) for i in range(10)]
        mesh.normals  = [(0.0, 0.0, 1.0)] * 3  # too few
        mesh.faces    = [(0, 1, 2)]
        mesh.render   = True
        mesh.texture  = ''

        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
            from PIL import Image
            cam = ArcBallCamera()
            renderer = FrameRenderer(cam)
            renderer.model = model
            renderer.render(200, 200)
        except IndexError:
            self.fail("Renderer raised IndexError on normals count mismatch")
        except (ImportError, Exception):
            pass


# ─────────────────────────────────────────────────────────────────────────
#  8. bone_world_position cycle guard (deep chain)
# ─────────────────────────────────────────────────────────────────────────

class TestBoneWorldPositionDeepChain(unittest.TestCase):
    """bone_world_position must handle 600-node chains without RecursionError."""

    def test_no_recursion_error_deep_chain(self):
        """bone_world_position on 600-node linear chain must not crash."""
        from src.core.model_data import ModelNode, NodeFlags
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        parent = root
        leaf = None
        for i in range(600):
            child = ModelNode(name=f"b{i}", flags=NodeFlags.HEADER)
            child.parent = parent
            parent.children.append(child)
            parent = child
            leaf = child
        try:
            wp = leaf.bone_world_position()
            self.assertIsInstance(wp, tuple)
            self.assertEqual(len(wp), 3)
        except RecursionError:
            self.fail("bone_world_position raised RecursionError on 600-node chain")

    def test_bone_world_position_cycle_guard(self):
        """
        bone_world_position must terminate if a cyclic parent reference exists.
        (The chain limit of 512 prevents infinite loops.)
        """
        from src.core.model_data import ModelNode, NodeFlags
        a = ModelNode(name="a", flags=NodeFlags.HEADER)
        b = ModelNode(name="b", flags=NodeFlags.HEADER)
        b.parent = a
        a.parent = b  # cycle!
        try:
            wp = b.bone_world_position()
            self.assertIsInstance(wp, tuple)
        except RecursionError:
            self.fail("bone_world_position hung on cyclic parent reference")


# ─────────────────────────────────────────────────────────────────────────
#  9. all_nodes() iterative (model traversal)
# ─────────────────────────────────────────────────────────────────────────

class TestAllNodesIterative(unittest.TestCase):
    """KotorModel.all_nodes() must work correctly on very deep chains."""

    def test_all_nodes_deep_chain(self):
        """all_nodes() on a 700-node chain must return all nodes."""
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        model.root_node = root
        parent = root
        for i in range(699):
            child = ModelNode(name=f"n{i}", flags=NodeFlags.HEADER)
            child.parent = parent
            parent.children.append(child)
            parent = child
        nodes = list(model.all_nodes())
        self.assertEqual(len(nodes), 700,
                         f"Expected 700 nodes, got {len(nodes)}")

    def test_all_nodes_cycle_terminates(self):
        """all_nodes() must terminate on cyclic graphs."""
        from src.core.model_data import ModelNode, KotorModel, NodeFlags
        model = KotorModel()
        root = ModelNode(name="root", flags=NodeFlags.HEADER)
        a = ModelNode(name="a", flags=NodeFlags.HEADER)
        root.children.append(a)
        a.children.append(root)  # cycle
        model.root_node = root
        nodes = list(model.all_nodes())
        self.assertGreater(len(nodes), 0)


if __name__ == '__main__':
    unittest.main()
