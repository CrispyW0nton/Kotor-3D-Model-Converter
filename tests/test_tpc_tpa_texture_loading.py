"""
Tests for TPC/TPA texture loading fixes (v10.6)

Bug reports addressed:
  1. TPA/TPC textures not loading → models rendered as flat grey
  2. ERF priority order: swpc_tex_tpa.erf (high-quality 512×512) was being
     superseded by swpc_tex_tpc.erf (low-quality 128×128) because reversed()
     ERF iteration searched lower-quality packs first.
  3. Forward-digit append fallback: MDL nodes store bare texture names (e.g.
     "c_drexl") but TPA archives store them suffixed ("c_drexl01").  The old
     code only stripped digits from the *searched* name, never appended them.
  4. main_window.py incorrectly tried to add swpc_tex_tpa.erf as a search
     directory (it is a file, not a directory → silently ignored → textures
     never loaded via file-system path).
"""

import sys, os, struct, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Optional

# ── Module path setup ────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))

GAME_DATA = ROOT / 'game_data'
K1_DIR    = GAME_DATA / 'k1_extracted'
K2_DIR    = GAME_DATA / 'k2_extracted'
HAS_K1    = K1_DIR.is_dir()
HAS_K2    = K2_DIR.is_dir()
HAS_BOTH  = HAS_K1 and HAS_K2

from resources.game_library import (
    GameLibrary, ERFReader,
    RES_TPC_ERF, RES_TGA, RES_TPC,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tpc_header(raw: bytes) -> dict:
    """Parse KotOR TPC header fields."""
    if not raw or len(raw) < 128:
        return {}
    return {
        'data_sz': struct.unpack_from('<I', raw, 0)[0],
        'width':   struct.unpack_from('<H', raw, 8)[0],
        'height':  struct.unpack_from('<H', raw, 10)[0],
        'layers':  raw[12],
        'mips':    raw[13],
        'enc':     raw[14],
    }


def _expected_dxt1_sz(w: int, h: int) -> int:
    bx = max(1, (w + 3) // 4)
    by = max(1, (h + 3) // 4)
    return bx * by * 8


def _expected_dxt5_sz(w: int, h: int) -> int:
    bx = max(1, (w + 3) // 4)
    by = max(1, (h + 3) // 4)
    return bx * by * 16


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: ERF priority logic (no game data required)
# ─────────────────────────────────────────────────────────────────────────────

class TestERFPriorityLogic(unittest.TestCase):
    """Test that _search_erfs_for prefers TPA over TPB/TPC."""

    def _make_mock_erf(self, path: str, resref: str, data: bytes) -> ERFReader:
        """Create a mock ERFReader that returns `data` for `resref`."""
        er = MagicMock(spec=ERFReader)
        er.path = path
        def mock_get(name, rt):
            if name.lower() == resref.lower() and rt == RES_TPC_ERF:
                entry = MagicMock()
                entry.read.return_value = data
                return entry
            return None
        er.get.side_effect = mock_get
        return er

    def test_tpa_wins_over_tpc_quality(self):
        """When TPA, TPB and TPC all have the same texture, TPA should win."""
        gl = GameLibrary()
        tpa_data = b'\x00' * 128 + b'\xAA' * 131072  # 512×512 DXT1
        tpb_data = b'\x00' * 128 + b'\xBB' * 32768   # 256×256 DXT1
        tpc_data = b'\x00' * 128 + b'\xCC' * 8192    # 128×128 DXT1

        # Simulate the ERF order as it appears after scanning:
        # gui(0), tpa(1), tpb(2), tpc(3), lips_mod(4..N)
        gl._k2_erfs = [
            self._make_mock_erf('path/swpc_tex_gui.erf', 'c_test01', b'\x00' * 100),
            self._make_mock_erf('path/swpc_tex_tpa.erf', 'c_test01', tpa_data),
            self._make_mock_erf('path/swpc_tex_tpb.erf', 'c_test01', tpb_data),
            self._make_mock_erf('path/swpc_tex_tpc.erf', 'c_test01', tpc_data),
            self._make_mock_erf('path/some_module.mod', 'c_test01', b'\x00' * 50),
        ]
        gl._k1_erfs = []
        gl.k1_dir = ''
        gl.k2_dir = '/fake/k2'

        # Patch internal to only test ERF search (no KEY lookup)
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_test01', 'K2')

        # TPA data starts with 0xAA pattern after 128-byte header
        self.assertIsNotNone(raw, "Texture should be found")
        self.assertEqual(raw, tpa_data, "TPA (highest quality) should win over TPB/TPC")

    def test_tpb_wins_over_tpc_when_no_tpa(self):
        """When only TPB and TPC have the texture, TPB should win."""
        gl = GameLibrary()
        tpb_data = b'\x00' * 128 + b'\xBB' * 32768
        tpc_data = b'\x00' * 128 + b'\xCC' * 8192

        gl._k2_erfs = [
            self._make_mock_erf('path/swpc_tex_tpb.erf', 'c_test01', tpb_data),
            self._make_mock_erf('path/swpc_tex_tpc.erf', 'c_test01', tpc_data),
        ]
        gl._k1_erfs = []
        gl.k1_dir = ''
        gl.k2_dir = '/fake/k2'

        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_test01', 'K2')

        self.assertEqual(raw, tpb_data, "TPB should win over TPC")

    def test_tpc_used_as_fallback(self):
        """When only TPC has the texture, it should still be returned."""
        gl = GameLibrary()
        tpc_data = b'\x00' * 128 + b'\xCC' * 8192

        gl._k2_erfs = [
            self._make_mock_erf('path/swpc_tex_tpc.erf', 'c_test01', tpc_data),
        ]
        gl._k1_erfs = []
        gl.k1_dir = ''
        gl.k2_dir = '/fake/k2'

        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_test01', 'K2')

        self.assertEqual(raw, tpc_data)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: Forward-digit append fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestForwardDigitFallback(unittest.TestCase):
    """Test that bare names like 'c_drexl' find 'c_drexl01' in archives."""

    def _make_mock_gl(self, resref_in_erf: str, data: bytes) -> GameLibrary:
        """Create a GameLibrary with one K2 ERF containing a single texture."""
        gl = GameLibrary()
        er = MagicMock(spec=ERFReader)
        er.path = 'path/swpc_tex_tpa.erf'
        def mock_get(name, rt):
            if name.lower() == resref_in_erf.lower() and rt == RES_TPC_ERF:
                entry = MagicMock()
                entry.read.return_value = data
                return entry
            return None
        er.get.side_effect = mock_get
        gl._k2_erfs = [er]
        gl._k1_erfs = []
        gl.k1_dir = ''
        gl.k2_dir = '/fake/k2'
        return gl

    def test_bare_name_finds_01_suffix(self):
        """'c_drexl' should find 'c_drexl01' via digit-append fallback."""
        data = b'\xAA' * 200
        gl = self._make_mock_gl('c_drexl01', data)
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_drexl', 'K2')
        self.assertEqual(raw, data, "Bare name 'c_drexl' should find 'c_drexl01'")

    def test_bare_name_finds_02_suffix(self):
        """'c_rancor' should find 'c_rancor02' if 01 is missing."""
        data = b'\xBB' * 200
        gl = self._make_mock_gl('c_rancor02', data)
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_rancor', 'K2')
        self.assertEqual(raw, data, "Bare name should find '02' suffix")

    def test_suffixed_name_not_double_suffixed(self):
        """'c_drexl01' should NOT try 'c_drexl0101'."""
        data = b'\xCC' * 200
        gl = self._make_mock_gl('c_drexl01', data)
        # Mock an ERF that ONLY has 'c_drexl01', not 'c_drexl0101'
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_drexl01', 'K2')
        # Should find c_drexl01 directly
        self.assertEqual(raw, data)

    def test_exact_match_takes_priority(self):
        """When exact name matches, digit-append should NOT be invoked."""
        exact_data  = b'\xDD' * 200
        suffix_data = b'\xEE' * 200
        gl = GameLibrary()
        er = MagicMock(spec=ERFReader)
        er.path = 'path/swpc_tex_tpa.erf'
        def mock_get(name, rt):
            if rt != RES_TPC_ERF:
                return None
            if name.lower() == 'c_drexl01':
                entry = MagicMock(); entry.read.return_value = suffix_data; return entry
            if name.lower() == 'c_drexl':
                entry = MagicMock(); entry.read.return_value = exact_data; return entry
            return None
        er.get.side_effect = mock_get
        gl._k2_erfs = [er]
        gl._k1_erfs = []
        gl.k1_dir = ''
        gl.k2_dir = '/fake/k2'
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_drexl', 'K2')
        self.assertEqual(raw, exact_data, "Exact match should win over digit-append")

    def test_strip_digits_fallback_still_works(self):
        """'c_drexl01' → strip digits → 'c_drexl' fallback still works."""
        data = b'\xFF' * 200
        gl = self._make_mock_gl('c_drexl', data)
        with patch.object(gl, '_k2_key', None):
            raw = gl.get_texture_data('c_drexl01', 'K2')
        self.assertEqual(raw, data, "Strip-digit fallback should still work")


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests (require actual game data)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipUnless(HAS_BOTH, "Requires both K1 and K2 game data")
class TestTPALoadingIntegration(unittest.TestCase):
    """Integration tests using real game data archives."""

    @classmethod
    def setUpClass(cls):
        cls.gl = GameLibrary()
        cls.gl.scan(str(K1_DIR), k2_dir=str(K2_DIR))

    def _assert_tpa_quality(self, raw: bytes, name: str, min_size: int = 40000):
        """Assert the returned texture bytes look like TPA (≥ min_size bytes)."""
        self.assertIsNotNone(raw, f"Texture '{name}' not found")
        self.assertGreaterEqual(
            len(raw), min_size,
            f"Texture '{name}' returned only {len(raw)} bytes — expected TPA quality "
            f"(≥ {min_size}). Possible regression: low-quality TPC returned instead of TPA."
        )

    def _assert_valid_tpc_header(self, raw: bytes, name: str):
        """Assert raw bytes have a valid KotOR TPC header."""
        hdr = _tpc_header(raw)
        self.assertTrue(hdr, f"Could not parse TPC header for '{name}'")
        self.assertGreater(hdr['width'],  0, f"'{name}' TPC width=0")
        self.assertGreater(hdr['height'], 0, f"'{name}' TPC height=0")
        self.assertIn(hdr['enc'], (0, 1, 2, 4, 10, 12, 13, 14),
                      f"'{name}' unknown TPC encoding {hdr['enc']}")

    # ── Bug regression: c_drexl01 must return TPA (174,923 bytes) ──────────

    def test_c_drexl01_tpa_priority(self):
        """c_drexl01 from K2 must return TPA (512×512 ≈ 174,923 bytes)."""
        raw = self.gl.get_texture_data('c_drexl01', 'K2')
        self._assert_tpa_quality(raw, 'c_drexl01', min_size=100000)
        hdr = _tpc_header(raw)
        self.assertEqual(hdr['width'],  512, "TPA c_drexl01 should be 512px wide")
        self.assertEqual(hdr['height'], 512, "TPA c_drexl01 should be 512px tall")

    def test_c_drexl_bare_name_forward_fallback(self):
        """Bare name 'c_drexl' must find 'c_drexl01' via digit-append fallback."""
        raw = self.gl.get_texture_data('c_drexl', 'K2')
        self._assert_tpa_quality(raw, 'c_drexl', min_size=100000)

    # ── K1 creatures ─────────────────────────────────────────────────────────

    def test_k1_rancor_tpa_quality(self):
        """c_rancor01 (K1) should return 512×512 TPA texture."""
        raw = self.gl.get_texture_data('c_rancor01', 'K1')
        self._assert_tpa_quality(raw, 'c_rancor01', min_size=100000)
        self._assert_valid_tpc_header(raw, 'c_rancor01')

    def test_k1_kinrath_tpa_quality(self):
        """c_kinrath01 (K1) should return 512×512 TPA texture."""
        raw = self.gl.get_texture_data('c_kinrath01', 'K1')
        self._assert_tpa_quality(raw, 'c_kinrath01', min_size=100000)

    def test_k1_bantha_tpa_quality(self):
        """c_bantha01 (K1) should return 512×512 TPA texture."""
        raw = self.gl.get_texture_data('c_bantha01', 'K1')
        self._assert_tpa_quality(raw, 'c_bantha01', min_size=100000)

    def test_k1_kraytdragon_tpa_quality(self):
        """c_kraytdragon01 (K1) should return 1024×1024 TPA texture."""
        raw = self.gl.get_texture_data('c_kraytdragon01', 'K1')
        self._assert_tpa_quality(raw, 'c_kraytdragon01', min_size=500000)
        hdr = _tpc_header(raw)
        self.assertEqual(hdr['width'], 1024, "kraytdragon TPA should be 1024px wide")

    def test_k1_hutt_tpa_quality(self):
        """c_hutt01 (K1) should return DXT5 TPA texture."""
        raw = self.gl.get_texture_data('c_hutt01', 'K1')
        self._assert_tpa_quality(raw, 'c_hutt01', min_size=100000)
        hdr = _tpc_header(raw)
        # enc=0 with layers >= 3 → DXT5
        self.assertIn(hdr['enc'], (0, 4, 14), f"Hutt should be DXT5-encoded, got {hdr['enc']}")

    # ── K2 creatures ─────────────────────────────────────────────────────────

    def test_k2_bantha_tpa_quality(self):
        """c_bantha01 (K2) should also be findable."""
        raw = self.gl.get_texture_data('c_bantha01', 'K2')
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw), 40000)

    def test_k2_gammorean_tpa_quality(self):
        """c_gammorean01 (K2) should return TPA texture."""
        raw = self.gl.get_texture_data('c_gammorean01', 'K2')
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw), 40000)

    # ── TPC decode sanity ────────────────────────────────────────────────────

    def test_tpa_tpc_header_valid_for_multiple_creatures(self):
        """All tested creature textures must have valid TPC headers."""
        names = [
            ('c_rancor01', 'K1'), ('c_bantha01', 'K1'), ('c_kinrath01', 'K1'),
            ('c_drexl01', 'K2'), ('c_gammorean01', 'K2'),
        ]
        for name, game in names:
            with self.subTest(name=name, game=game):
                raw = self.gl.get_texture_data(name, game)
                if raw:
                    self._assert_valid_tpc_header(raw, name)

    def test_tpa_wins_over_tpb_tpc_for_k1_rancor(self):
        """TPA (512×512) must win over TPB (256×256) and TPC (128×128)."""
        raw = self.gl.get_texture_data('c_rancor01', 'K1')
        self.assertIsNotNone(raw)
        hdr = _tpc_header(raw)
        # TPA is always the largest — at least 256×256
        self.assertGreaterEqual(hdr['width'], 256,
            f"Expected TPA (≥256px), got {hdr['width']}px — "
            "TPC/TPB may be winning over TPA (priority bug)")

    # ── Cross-game fallback still works ──────────────────────────────────────

    def test_cross_game_fallback_k2_finds_k1_texture(self):
        """A K1-only texture requested with K2 tag should still be found."""
        # c_kraytdragon01 exists in K1 TPA but may not be in K2
        raw_k1 = self.gl.get_texture_data('c_kraytdragon01', 'K1')
        raw_k2 = self.gl.get_texture_data('c_kraytdragon01', 'K2')
        if raw_k1:
            self.assertIsNotNone(raw_k2,
                "Cross-game fallback should find K1 texture when requested as K2")

    # ── ERF scan ordering ────────────────────────────────────────────────────

    def test_k1_texturepacks_loaded(self):
        """K1 TexturePack ERFs should be present in k1_erfs."""
        tpa_erfs = [er for er in self.gl._k1_erfs if 'swpc_tex_tpa' in er.path.lower()]
        self.assertTrue(len(tpa_erfs) > 0, "K1 swpc_tex_tpa.erf not loaded")

    def test_k2_texturepacks_loaded(self):
        """K2 TexturePack ERFs should be present in k2_erfs."""
        tpa_erfs = [er for er in self.gl._k2_erfs if 'swpc_tex_tpa' in er.path.lower()]
        self.assertTrue(len(tpa_erfs) > 0, "K2 swpc_tex_tpa.erf not loaded")

    def test_k1_tpa_index_higher_than_tpc(self):
        """K1 TPA ERF must have a higher list index than TPC ERF (priority order)."""
        tpa_idx = next((i for i, er in enumerate(self.gl._k1_erfs)
                        if 'swpc_tex_tpa' in er.path.lower()), None)
        tpc_idx = next((i for i, er in enumerate(self.gl._k1_erfs)
                        if 'swpc_tex_tpc.erf' in er.path.lower()), None)
        if tpa_idx is not None and tpc_idx is not None:
            self.assertGreater(tpa_idx, tpc_idx,
                "TPA should be at higher list index than TPC (quality sort)")


# ─────────────────────────────────────────────────────────────────────────────
# TPC decode tests using synthetic data
# ─────────────────────────────────────────────────────────────────────────────

class TestTPCDecodeLogic(unittest.TestCase):
    """Test TPC decode logic on synthetic TPC data (no game data required)."""

    def _make_tpc_header(self, data_sz, w, h, layers, mips, enc) -> bytes:
        hdr = bytearray(128)
        struct.pack_into('<I', hdr, 0, data_sz)
        struct.pack_into('<H', hdr, 8, w)
        struct.pack_into('<H', hdr, 10, h)
        hdr[12] = layers
        hdr[13] = mips
        hdr[14] = enc
        # bytes 15-127 remain zero (reserved) → passes pykotor_tpc test
        return bytes(hdr)

    def _import_is_tpc(self):
        """Import _is_tpc_data from viewport module functions."""
        # Parse just the function from the source to avoid tkinter dep
        import re
        src_path = ROOT / 'src' / 'gui' / 'viewport.py'
        src = src_path.read_text()
        # Find the relevant functions and exec them in a namespace
        ns = {'struct': struct, 'Optional': Optional,
              '__name__': '__not_main__'}
        m = re.search(r'(def _is_tpc_data.*?)(?=\ndef [^_]|\nclass )',
                      src, re.DOTALL)
        if m:
            exec(m.group(1), ns)
        return ns.get('_is_tpc_data')

    def test_dxt1_128x128_is_detected(self):
        """128×128 DXT1 TPC (from swpc_tex_tpc.erf) should be detected."""
        _is_tpc_data = self._import_is_tpc()
        if not _is_tpc_data:
            self.skipTest("Could not import _is_tpc_data")
        w, h = 128, 128
        dxt1_sz = (w//4) * (h//4) * 8   # 8192
        hdr = self._make_tpc_header(dxt1_sz, w, h, 2, 8, 0)
        raw = hdr + bytes(dxt1_sz)
        self.assertTrue(_is_tpc_data(raw), "128×128 DXT1 TPC should be detected")

    def test_dxt1_512x512_is_detected(self):
        """512×512 DXT1 TPC (from swpc_tex_tpa.erf) should be detected."""
        _is_tpc_data = self._import_is_tpc()
        if not _is_tpc_data:
            self.skipTest("Could not import _is_tpc_data")
        w, h = 512, 512
        dxt1_sz = (w//4) * (h//4) * 8   # 131072
        hdr = self._make_tpc_header(dxt1_sz, w, h, 2, 10, 0)
        raw = hdr + bytes(dxt1_sz)
        self.assertTrue(_is_tpc_data(raw), "512×512 DXT1 TPC should be detected")

    def test_dxt5_512x512_is_detected(self):
        """512×512 DXT5 TPC should be detected (enc=0, layers=3)."""
        _is_tpc_data = self._import_is_tpc()
        if not _is_tpc_data:
            self.skipTest("Could not import _is_tpc_data")
        w, h = 512, 512
        dxt5_sz = (w//4) * (h//4) * 16  # 262144
        hdr = self._make_tpc_header(dxt5_sz, w, h, 3, 10, 0)
        raw = hdr + bytes(dxt5_sz)
        self.assertTrue(_is_tpc_data(raw), "512×512 DXT5 TPC should be detected")

    def test_random_bytes_not_tpc(self):
        """Random bytes with non-zero reserved section should not pass TPC detection."""
        _is_tpc_data = self._import_is_tpc()
        if not _is_tpc_data:
            self.skipTest("Could not import _is_tpc_data")
        import random; random.seed(42)
        garbage = bytes(random.randint(1, 255) for _ in range(256))
        self.assertFalse(_is_tpc_data(garbage), "Random bytes should not be TPC")


if __name__ == '__main__':
    unittest.main(verbosity=2)
