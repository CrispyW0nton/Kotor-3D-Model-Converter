"""
Tests for Phase 12.1 — Override Folder Resource Layer
(src/core/override_layer.py)
=====================================================
Covers:
  * OverrideLayer construction and auto_scan
  * scan() — indexes files, returns count
  * has() — lookup by resref + ext
  * get() — returns bytes or None
  * get_path() — returns Path or None
  * list_by_ext() — filtered resref list
  * list_all() — all entries sorted
  * badge() — '[Override]' or ''
  * summary() — human-readable string
  * get_model() / get_model_mdx() / get_texture() helpers
  * send_to_override() — writes file + updates index
  * delete_override() — removes file + updates index
  * get_or_fallback() — override-first + library fallback
  * Edge cases: missing dir, empty dir, hidden files, case-insensitivity
  * is_available when dir is absent

References:
  PyKotor/extract/installation.py → Installation.load_override()
  GhostRigger Roadmap Phase 12.1
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.override_layer import OverrideLayer, OverrideEntry


# ─────────────────────────────  Helpers  ─────────────────────────────────────

def _make_override_dir(tmpdir: str, files: dict) -> str:
    """
    Create a fake KotOR installation directory with Override/ populated.
    files: {filename: bytes_content}
    Returns the game_dir path.
    """
    game_dir = os.path.join(tmpdir, 'KotOR')
    ov_dir   = os.path.join(game_dir, 'Override')
    os.makedirs(ov_dir, exist_ok=True)
    for fname, content in files.items():
        with open(os.path.join(ov_dir, fname), 'wb') as f:
            f.write(content)
    return game_dir


class _FakeLibrary:
    """Minimal library stub for get_or_fallback tests."""
    def __init__(self, items: dict):
        self._items = items   # {(resref_lower, ext_lower): bytes}

    def get(self, resref: str, ext: str) -> bytes | None:
        return self._items.get((resref.lower(), ext.lower()))


# ─────────────────────────────  Test classes  ────────────────────────────────

class TestOverrideLayerConstruction(unittest.TestCase):
    """Construction, is_available, auto_scan."""

    def test_no_override_dir_is_not_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = os.path.join(tmp, 'FakeGame')
            os.makedirs(game_dir)
            ol = OverrideLayer(game_dir)
            self.assertFalse(ol.is_available)

    def test_with_override_dir_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir)
            self.assertTrue(ol.is_available)

    def test_entry_count_zero_before_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00' * 16})
            ol = OverrideLayer(game_dir)
            self.assertEqual(ol.entry_count, 0)

    def test_auto_scan_indexes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'pfh0.mdl': b'\x00' * 16,
                'pfh0.mdx': b'\xff' * 8,
            })
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertEqual(ol.entry_count, 2)

    def test_game_dir_property(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir)
            self.assertEqual(str(ol.game_dir), game_dir)

    def test_override_dir_property(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir)
            self.assertEqual(ol.override_dir, Path(game_dir) / 'Override')


class TestScan(unittest.TestCase):
    """scan() method."""

    def test_scan_returns_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'a.mdl': b'\x00',
                'b.tpc': b'\x01',
                'c.2da': b'\x02',
            })
            ol = OverrideLayer(game_dir)
            count = ol.scan()
            self.assertEqual(count, 3)

    def test_scan_populates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00' * 4})
            ol = OverrideLayer(game_dir)
            ol.scan()
            self.assertTrue(ol.has('pfh0', 'mdl'))

    def test_scan_empty_dir_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir)
            self.assertEqual(ol.scan(), 0)

    def test_scan_no_override_dir_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = os.path.join(tmp, 'NoGame')
            os.makedirs(game_dir)
            ol = OverrideLayer(game_dir)
            self.assertEqual(ol.scan(), 0)
            self.assertEqual(ol.entry_count, 0)

    def test_rescan_clears_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'a.mdl': b'\x00'})
            ol = OverrideLayer(game_dir)
            ol.scan()
            self.assertEqual(ol.entry_count, 1)
            # Add file and re-scan
            ov_dir = os.path.join(game_dir, 'Override')
            open(os.path.join(ov_dir, 'b.mdl'), 'wb').write(b'\x01')
            ol.scan()
            self.assertEqual(ol.entry_count, 2)

    def test_scan_skips_hidden_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'valid.mdl': b'\x00',
                '.hidden': b'\x01',
            })
            ol = OverrideLayer(game_dir)
            ol.scan()
            self.assertEqual(ol.entry_count, 1)
            self.assertTrue(ol.has('valid', 'mdl'))

    def test_scan_resref_lowercased(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'PFH0.MDL': b'\x00'})
            ol = OverrideLayer(game_dir)
            ol.scan()
            self.assertTrue(ol.has('pfh0', 'mdl'))


class TestHas(unittest.TestCase):
    """has() lookup."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.game_dir = _make_override_dir(self.tmp.name, {
            'pfh0.mdl': b'\xDE\xAD\xBE\xEF',
            'n_sithp.tpc': b'\x01\x02',
        })
        self.ol = OverrideLayer(self.game_dir, auto_scan=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_has_existing_mdl(self):
        self.assertTrue(self.ol.has('pfh0', 'mdl'))

    def test_has_existing_tpc(self):
        self.assertTrue(self.ol.has('n_sithp', 'tpc'))

    def test_has_missing_resref(self):
        self.assertFalse(self.ol.has('nonexistent', 'mdl'))

    def test_has_wrong_ext(self):
        self.assertFalse(self.ol.has('pfh0', 'tpc'))

    def test_has_case_insensitive_resref(self):
        self.assertTrue(self.ol.has('PFH0', 'MDL'))

    def test_has_case_insensitive_ext(self):
        self.assertTrue(self.ol.has('pfh0', 'MDL'))


class TestGet(unittest.TestCase):
    """get() — returns bytes or None."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.content = b'\xDE\xAD\xBE\xEF' * 10
        self.game_dir = _make_override_dir(self.tmp.name, {
            'pfh0.mdl': self.content,
        })
        self.ol = OverrideLayer(self.game_dir, auto_scan=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_returns_bytes(self):
        data = self.ol.get('pfh0', 'mdl')
        self.assertEqual(data, self.content)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.ol.get('missing', 'mdl'))

    def test_get_wrong_ext_returns_none(self):
        self.assertIsNone(self.ol.get('pfh0', 'mdx'))

    def test_get_case_insensitive(self):
        data = self.ol.get('PFH0', 'MDL')
        self.assertEqual(data, self.content)


class TestGetPath(unittest.TestCase):
    """get_path() — returns Path or None."""

    def test_get_path_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            p = ol.get_path('pfh0', 'mdl')
            self.assertIsNotNone(p)
            self.assertTrue(p.exists())

    def test_get_path_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertIsNone(ol.get_path('nope', 'mdl'))


class TestListByExt(unittest.TestCase):
    """list_by_ext() — filtered resref list."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.game_dir = _make_override_dir(self.tmp.name, {
            'pfh0.mdl': b'\x00',
            'pfh1.mdl': b'\x01',
            'n_sith.tpc': b'\x02',
        })
        self.ol = OverrideLayer(self.game_dir, auto_scan=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_by_mdl(self):
        mdls = self.ol.list_by_ext('mdl')
        self.assertIn('pfh0', mdls)
        self.assertIn('pfh1', mdls)
        self.assertNotIn('n_sith', mdls)

    def test_list_by_tpc(self):
        tpcs = self.ol.list_by_ext('tpc')
        self.assertIn('n_sith', tpcs)
        self.assertNotIn('pfh0', tpcs)

    def test_list_empty_ext(self):
        self.assertEqual(self.ol.list_by_ext('xyz'), [])

    def test_list_sorted(self):
        mdls = self.ol.list_by_ext('mdl')
        self.assertEqual(mdls, sorted(mdls))


class TestListAll(unittest.TestCase):
    """list_all() — all entries."""

    def test_list_all_returns_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'a.mdl': b'\x00',
                'b.tpc': b'\x01',
                'c.2da': b'\x02',
            })
            ol = OverrideLayer(game_dir, auto_scan=True)
            entries = ol.list_all()
            self.assertEqual(len(entries), 3)
            resrefs = {e.resref for e in entries}
            self.assertIn('a', resrefs)
            self.assertIn('b', resrefs)
            self.assertIn('c', resrefs)

    def test_list_all_sorted_by_ext_then_resref(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'z.mdl': b'\x00',
                'a.mdl': b'\x00',
                'm.tpc': b'\x00',
            })
            ol = OverrideLayer(game_dir, auto_scan=True)
            entries = ol.list_all()
            exts = [e.ext for e in entries]
            # 2da/mdl comes before tpc alphabetically
            self.assertLessEqual(exts[0], exts[-1])


class TestBadge(unittest.TestCase):
    """badge() — '[Override]' or ''."""

    def test_badge_overridden(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertEqual(ol.badge('pfh0', 'mdl'), '[Override]')

    def test_badge_not_overridden(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertEqual(ol.badge('pfh0', 'mdl'), '')


class TestSummary(unittest.TestCase):
    """summary() — human-readable string."""

    def test_summary_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir)
            self.assertIn('not yet scanned', ol.summary())

    def test_summary_no_override_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = os.path.join(tmp, 'NoGame')
            os.makedirs(game_dir)
            ol = OverrideLayer(game_dir)
            ol.scan()
            self.assertIn('no Override/', ol.summary())

    def test_summary_with_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'pfh0.mdl': b'\x00',
                'pfh0.mdx': b'\x00',
                'tex01.tpc': b'\x00',
            })
            ol = OverrideLayer(game_dir, auto_scan=True)
            s = ol.summary()
            self.assertIn('3 files', s)
            self.assertIn('.mdl', s)
            self.assertIn('.mdx', s)
            self.assertIn('.tpc', s)


class TestModelHelpers(unittest.TestCase):
    """get_model() / get_model_mdx() / get_texture() helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mdl_bytes = b'\x00\x01\x02\x03'
        self.mdx_bytes = b'\x04\x05\x06\x07'
        self.tpc_bytes = b'\x08\x09\x0A\x0B'
        self.tga_bytes = b'\x0C\x0D\x0E\x0F'
        self.game_dir = _make_override_dir(self.tmp.name, {
            'pfh0.mdl': self.mdl_bytes,
            'pfh0.mdx': self.mdx_bytes,
            'cmbtglovs.tpc': self.tpc_bytes,
            'cmbthands.tga': self.tga_bytes,
        })
        self.ol = OverrideLayer(self.game_dir, auto_scan=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_model(self):
        self.assertEqual(self.ol.get_model('pfh0'), self.mdl_bytes)

    def test_get_model_none_for_missing(self):
        self.assertIsNone(self.ol.get_model('missing'))

    def test_get_model_mdx(self):
        self.assertEqual(self.ol.get_model_mdx('pfh0'), self.mdx_bytes)

    def test_get_texture_prefers_tpc(self):
        data = self.ol.get_texture('cmbtglovs')
        self.assertEqual(data, self.tpc_bytes)

    def test_get_texture_falls_back_to_tga(self):
        data = self.ol.get_texture('cmbthands')
        self.assertEqual(data, self.tga_bytes)

    def test_get_texture_none_for_missing(self):
        self.assertIsNone(self.ol.get_texture('missingtex'))


class TestSendToOverride(unittest.TestCase):
    """send_to_override() — writes file and updates index."""

    def test_send_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            data = b'\xDE\xAD'
            dest = ol.send_to_override('mynpc', 'mdl', data)
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes(), data)

    def test_send_updates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            ol.send_to_override('mynpc', 'mdl', b'\x00')
            self.assertTrue(ol.has('mynpc', 'mdl'))

    def test_send_creates_override_dir_if_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = os.path.join(tmp, 'NewGame')
            os.makedirs(game_dir)
            ol = OverrideLayer(game_dir)
            ol.send_to_override('test', 'mdl', b'\x00')
            self.assertTrue((Path(game_dir) / 'Override' / 'test.mdl').exists())

    def test_send_filename_is_lowercase(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            dest = ol.send_to_override('MyModel', 'MDL', b'\x00')
            self.assertEqual(dest.name, 'mymodel.mdl')

    def test_send_get_returns_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            payload = b'\x01\x02\x03\x04'
            ol.send_to_override('newfile', 'mdl', payload)
            self.assertEqual(ol.get('newfile', 'mdl'), payload)


class TestDeleteOverride(unittest.TestCase):
    """delete_override() — removes file and updates index."""

    def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            result = ol.delete_override('pfh0', 'mdl')
            self.assertTrue(result)
            p = Path(game_dir) / 'Override' / 'pfh0.mdl'
            self.assertFalse(p.exists())

    def test_delete_updates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            ol.delete_override('pfh0', 'mdl')
            self.assertFalse(ol.has('pfh0', 'mdl'))

    def test_delete_missing_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertFalse(ol.delete_override('nope', 'mdl'))


class TestGetOrFallback(unittest.TestCase):
    """get_or_fallback() — override-first + library fallback."""

    def test_override_wins_over_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            override_data = b'\xAA\xBB'
            library_data  = b'\xCC\xDD'
            game_dir = _make_override_dir(tmp, {'pfh0.mdl': override_data})
            ol = OverrideLayer(game_dir, auto_scan=True)
            lib = _FakeLibrary({('pfh0', 'mdl'): library_data})
            result = ol.get_or_fallback('pfh0', 'mdl', lib)
            self.assertEqual(result, override_data)

    def test_fallback_to_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            library_data = b'\xCC\xDD'
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            lib = _FakeLibrary({('pfh0', 'mdl'): library_data})
            result = ol.get_or_fallback('pfh0', 'mdl', lib)
            self.assertEqual(result, library_data)

    def test_both_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {})
            ol = OverrideLayer(game_dir, auto_scan=True)
            lib = _FakeLibrary({})
            self.assertIsNone(ol.get_or_fallback('nope', 'mdl', lib))


class TestOverrideEntryDataclass(unittest.TestCase):
    """OverrideEntry dataclass."""

    def test_entry_attributes(self):
        p = Path('/fake/Override/pfh0.mdl')
        e = OverrideEntry(resref='pfh0', ext='mdl', path=p)
        self.assertEqual(e.resref, 'pfh0')
        self.assertEqual(e.ext, 'mdl')
        self.assertEqual(e.path, p)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_files_with_dots_in_name(self):
        """Files like 'a.b.mdl' → resref='a.b', ext='mdl'."""
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'a.b.mdl': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            # stem of 'a.b.mdl' is 'a.b', suffix is '.mdl'
            self.assertTrue(ol.has('a.b', 'mdl'))

    def test_file_with_no_extension(self):
        """Files with no extension get empty string ext."""
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {'noext': b'\x00'})
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertTrue(ol.has('noext', ''))

    def test_many_files(self):
        """Index should handle many files efficiently."""
        with tempfile.TemporaryDirectory() as tmp:
            files = {f'model{i:04d}.mdl': bytes([i % 256]) for i in range(200)}
            game_dir = _make_override_dir(tmp, files)
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertEqual(ol.entry_count, 200)
            self.assertTrue(ol.has('model0000', 'mdl'))
            self.assertTrue(ol.has('model0199', 'mdl'))

    def test_mixed_file_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = _make_override_dir(tmp, {
                'pfh0.mdl': b'\x00',
                'pfh0.mdx': b'\x00',
                'pfh0.tpc': b'\x00',
                'pfh0.2da': b'\x00',
            })
            ol = OverrideLayer(game_dir, auto_scan=True)
            self.assertEqual(ol.entry_count, 4)
            for ext in ['mdl', 'mdx', 'tpc', '2da']:
                self.assertTrue(ol.has('pfh0', ext))


if __name__ == '__main__':
    unittest.main()
