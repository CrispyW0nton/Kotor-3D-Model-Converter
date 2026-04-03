"""
test_v95_resource_manager.py — ResourceManager unit + integration tests
========================================================================
Tests the new unified ResourceManager (src/core/resource_manager.py)
including:
  • Module imports clean
  • _ErfIndex / _BifIndex  parsing against real ERF/BIF data when present
  • ResourceManager singleton  (get_manager / reset_manager)
  • ResourceManager.set_k1_dir / set_k2_dir  with real game data when present
  • Priority chain  (Override > module ERF > tex ERF > BIF)
  • Texture decode helpers  (_is_tpc, _decode_tpc, _decode_texture)
  • ResourceManager.stats()  structure
  • TextureCache.set_resource_manager  integration

All tests that need game data are marked with pytest.mark.skipif
and skipped gracefully when game data is unavailable (CI-safe).
"""

from __future__ import annotations

import io
import os
import struct
import sys
import tempfile
import threading
import types
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from core.resource_manager import (
    ResourceManager,
    _BifIndex,
    _ErfIndex,
    _GameInstall,
    _build_dds,
    _decode_texture,
    _decode_tpc,
    _dxt_decode,
    _is_tpc,
    _key,
    get_manager,
    reset_manager,
    RES_MDL,
    RES_MDX,
    RES_TGA,
    RES_TPC,
    RES_TXI,
    EXT_TO_TYPE,
    TYPE_TO_EXT,
)

# ---------------------------------------------------------------------------
# Helpers for synthetic archives
# ---------------------------------------------------------------------------

def _make_erf(entries: dict) -> bytes:
    """
    Build a minimal ERF V1 binary with the given entries.
    entries: { (resref, res_type): data_bytes }
    """
    n = len(entries)
    # Header: 160 bytes
    hdr = bytearray(160)
    # FileType='ERF ' FileVersion='V1.0'
    hdr[0:4]  = b'ERF '
    hdr[4:8]  = b'V1.0'
    struct.pack_into('<I', hdr, 16, n)      # entry_count
    off_keys = 160                           # key list right after header
    off_res  = off_keys + n * 24
    data_start = off_res + n * 8
    struct.pack_into('<I', hdr, 24, off_keys)
    struct.pack_into('<I', hdr, 28, off_res)

    key_raw  = bytearray(n * 24)
    res_raw  = bytearray(n * 8)
    data_raw = bytearray()

    for i, ((resref, rtype), data) in enumerate(entries.items()):
        kb = i * 24
        rb = i * 8
        # resref[16], resID[4], resType[2], unused[2]
        r_bytes = resref.lower().encode('ascii')[:16].ljust(16, b'\x00')
        key_raw[kb:kb+16] = r_bytes
        struct.pack_into('<I', key_raw, kb + 16, i)       # resID
        struct.pack_into('<H', key_raw, kb + 20, rtype)   # resType

        offset = data_start + len(data_raw)
        size   = len(data)
        struct.pack_into('<I', res_raw, rb,     offset)
        struct.pack_into('<I', res_raw, rb + 4, size)
        data_raw += data

    return bytes(hdr) + bytes(key_raw) + bytes(res_raw) + bytes(data_raw)


def _make_bif(entries: list) -> bytes:
    """
    Build a minimal BIFF V1 binary with the given entries.
    entries: list of data_bytes in order.
    """
    n = len(entries)
    # Header: 20 bytes — FileType[4] FileVersion[4] VarResCount[4] FixedResCount[4] OffVarRes[4]
    hdr = bytearray(20)
    hdr[0:8] = b'BIFFV1  '
    struct.pack_into('<I', hdr, 8,  n)   # var_count
    struct.pack_into('<I', hdr, 12, 0)   # fixed_count
    struct.pack_into('<I', hdr, 16, 20)  # off_var_res (table right after header)
    # Variable resource table: n × 16 bytes
    # ID[4] Offset[4] FileSize[4] ResType[4]
    table_size = n * 16
    data_offset = 20 + table_size
    table = bytearray(table_size)
    data_raw = bytearray()
    for i, data in enumerate(entries):
        b = i * 16
        struct.pack_into('<I', table, b,      i)                         # ID
        struct.pack_into('<I', table, b + 4,  data_offset + len(data_raw))  # offset
        struct.pack_into('<I', table, b + 8,  len(data))                 # filesize
        struct.pack_into('<I', table, b + 12, 0)                         # restype (ignored here)
        data_raw += data
    return bytes(hdr) + bytes(table) + bytes(data_raw)


def _make_chitin_key(bif_names: list, key_entries: list) -> bytes:
    """
    Build a minimal chitin.key.
    bif_names: list of str
    key_entries: list of (resref, rtype, bif_idx, var_idx)
    """
    # Header: 64 bytes
    # FileType[4] FileVersion[4] BIFCount[4] KeyCount[4] OffBIFTable[4] OffKeyTable[4] ...
    n_bif  = len(bif_names)
    n_keys = len(key_entries)

    # BIF table: n_bif × 12 bytes (file_size[4], name_offset[4], name_size[2], drives[2])
    # Names stored immediately after BIF table
    off_bifs = 64
    bif_table_size = n_bif * 12
    name_data = bytearray()
    name_offsets = []
    for name in bif_names:
        name_bytes = name.encode('ascii') + b'\x00'
        name_offsets.append(off_bifs + bif_table_size + len(name_data))
        name_data += name_bytes

    off_keys = off_bifs + bif_table_size + len(name_data)
    # Key entries: n_keys × 22 bytes (resref[16] type[2] id[4])
    key_data = bytearray()
    for (resref, rtype, bif_idx, var_idx) in key_entries:
        r_bytes = resref.lower().encode('ascii')[:16].ljust(16, b'\x00')
        res_id  = ((bif_idx & 0xFFF) << 20) | (var_idx & 0xFFFFF)
        row = bytearray(22)
        row[0:16] = r_bytes
        struct.pack_into('<H', row, 16, rtype)
        struct.pack_into('<I', row, 18, res_id)
        key_data += row

    hdr = bytearray(64)
    hdr[0:8] = b'KEY V1  '
    struct.pack_into('<I', hdr, 8,  n_bif)
    struct.pack_into('<I', hdr, 12, n_keys)
    struct.pack_into('<I', hdr, 16, off_bifs)
    struct.pack_into('<I', hdr, 20, off_keys)

    bif_table = bytearray(bif_table_size)
    for i, name in enumerate(bif_names):
        b = i * 12
        struct.pack_into('<I', bif_table, b, 0)                # file_size (unused)
        struct.pack_into('<I', bif_table, b + 4, name_offsets[i])
        struct.pack_into('<H', bif_table, b + 8, len(name))

    return (bytes(hdr) + bytes(bif_table) + bytes(name_data) + bytes(key_data))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
K1_DIR = REPO_ROOT / 'tests' / 'k1_extracted'
HAS_K1 = (K1_DIR / 'chitin.key').exists()


# ===========================================================================
# 1. Module-level API tests
# ===========================================================================

class TestModuleAPI:
    def test_key_function_lowercase(self):
        assert _key('C_Bantha', RES_MDL) == f'c_bantha:{RES_MDL}'

    def test_key_different_types_differ(self):
        assert _key('foo', RES_MDL) != _key('foo', RES_TPC)

    def test_ext_to_type_coverage(self):
        assert EXT_TO_TYPE['mdl'] == RES_MDL
        assert EXT_TO_TYPE['tpc'] == RES_TPC
        assert EXT_TO_TYPE['tga'] == RES_TGA
        assert EXT_TO_TYPE['txi'] == RES_TXI

    def test_type_to_ext_roundtrip(self):
        # TYPE_TO_EXT is built from EXT_TO_TYPE so at minimum MDL round-trips
        assert TYPE_TO_EXT[RES_MDL] == 'mdl'

    def test_get_manager_returns_singleton(self):
        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2

    def test_reset_manager_returns_new(self):
        old = get_manager()
        new = reset_manager()
        assert new is not old
        assert get_manager() is new


# ===========================================================================
# 2. _ErfIndex tests
# ===========================================================================

class TestErfIndex:
    def test_parse_synthetic_erf(self, tmp_path):
        entries = {
            ('foo_mdl', RES_MDL): b'\xab\xcd\xef',
            ('bar_tex', RES_TPC): b'\x01\x02\x03\x04',
        }
        erf_path = tmp_path / 'test.erf'
        erf_path.write_bytes(_make_erf(entries))

        idx = _ErfIndex(str(erf_path))
        assert idx.has('foo_mdl', RES_MDL)
        assert idx.has('bar_tex', RES_TPC)
        assert not idx.has('nonexistent', RES_MDL)

    def test_read_returns_correct_data(self, tmp_path):
        entries = {
            ('hello', RES_TGA): b'HELLO WORLD',
            ('world', RES_TXI): b'bumpmap 1\nblending additive',
        }
        erf_path = tmp_path / 'data.erf'
        erf_path.write_bytes(_make_erf(entries))

        idx = _ErfIndex(str(erf_path))
        assert idx.read('hello', RES_TGA) == b'HELLO WORLD'
        assert idx.read('world', RES_TXI) == b'bumpmap 1\nblending additive'
        assert idx.read('missing', RES_TGA) is None

    def test_list_type(self, tmp_path):
        entries = {
            ('mdl_a', RES_MDL): b'a',
            ('mdl_b', RES_MDL): b'b',
            ('tex_c', RES_TPC): b'c',
        }
        erf_path = tmp_path / 'list.erf'
        erf_path.write_bytes(_make_erf(entries))

        idx = _ErfIndex(str(erf_path))
        models = idx.list_type(RES_MDL)
        assert sorted(models) == ['mdl_a', 'mdl_b']
        textures = idx.list_type(RES_TPC)
        assert textures == ['tex_c']

    def test_case_insensitive_lookup(self, tmp_path):
        entries = {('MyModel', RES_MDL): b'data'}
        erf_path = tmp_path / 'case.erf'
        erf_path.write_bytes(_make_erf(entries))

        idx = _ErfIndex(str(erf_path))
        assert idx.has('mymodel', RES_MDL)
        assert idx.has('MYMODEL', RES_MDL)
        assert idx.read('MyModel', RES_MDL) == b'data'

    def test_empty_erf(self, tmp_path):
        entries = {}
        erf_path = tmp_path / 'empty.erf'
        erf_path.write_bytes(_make_erf(entries))

        idx = _ErfIndex(str(erf_path))
        assert len(idx._index) == 0
        assert idx.list_type(RES_MDL) == []

    def test_corrupted_file_doesnt_crash(self, tmp_path):
        bad_path = tmp_path / 'bad.erf'
        bad_path.write_bytes(b'\x00' * 16)

        idx = _ErfIndex(str(bad_path))
        # Should not raise; _index should be empty
        assert len(idx._index) == 0


# ===========================================================================
# 3. _BifIndex tests
# ===========================================================================

class TestBifIndex:
    def test_parse_synthetic_bif(self, tmp_path):
        entries = [b'MDL DATA 0', b'MDL DATA 1', b'TPC DATA 2']
        bif_path = tmp_path / 'models.bif'
        bif_path.write_bytes(_make_bif(entries))

        idx = _BifIndex(str(bif_path))
        assert idx.read(0) == b'MDL DATA 0'
        assert idx.read(1) == b'MDL DATA 1'
        assert idx.read(2) == b'TPC DATA 2'
        assert idx.read(99) is None

    def test_corrupted_bif_doesnt_crash(self, tmp_path):
        bad_path = tmp_path / 'bad.bif'
        bad_path.write_bytes(b'\xff' * 4)

        idx = _BifIndex(str(bad_path))
        assert len(idx._table) == 0


# ===========================================================================
# 4. ResourceManager basic API
# ===========================================================================

class TestResourceManagerBasic:
    def test_empty_manager_not_ready(self):
        mgr = ResourceManager()
        assert not mgr.is_ready()

    def test_set_invalid_dir_returns_false(self):
        mgr = ResourceManager()
        assert not mgr.set_k1_dir('/nonexistent/path/xyz')
        assert not mgr.set_k2_dir('')

    def test_get_returns_none_when_empty(self):
        mgr = ResourceManager()
        assert mgr.get('c_bantha', RES_MDL) is None
        assert mgr.get_mdl('anything') is None
        assert mgr.get_texture('foo') is None
        assert mgr.get_txi('bar') == ''

    def test_list_models_empty(self):
        mgr = ResourceManager()
        assert mgr.list_models() == []
        assert mgr.list_textures() == []

    def test_has_textures_false_when_empty(self):
        mgr = ResourceManager()
        assert not mgr.has_textures()

    def test_stats_structure(self):
        mgr = ResourceManager()
        s = mgr.stats()
        assert 'K1' in s
        assert 'K2' in s
        assert s['K1'] is None
        assert s['K2'] is None

    def test_game_dir_none_when_empty(self):
        mgr = ResourceManager()
        assert mgr.game_dir('K1') is None
        assert mgr.game_dir('K2') is None


# ===========================================================================
# 5. ResourceManager with synthetic game directory
# ===========================================================================

class TestResourceManagerSynthetic:
    """Tests using a minimal hand-crafted game directory (no real game needed)."""

    @pytest.fixture
    def fake_game_dir(self, tmp_path):
        """
        Create a minimal synthetic KotOR installation:
          chitin.key  → references models.bif
          data/models.bif  → contains one MDL and one MDX
          TexturePacks/textures_tpa.erf  → contains one TPC
          Override/foo.txi  → loose override file
        """
        gdir = tmp_path / 'fake_k1'
        gdir.mkdir()

        mdl_data = b'FAKE_MDL_DATA_' + b'\x00' * 20
        mdx_data = b'FAKE_MDX_DATA_' + b'\x00' * 20

        # BIF: [mdl_data, mdx_data]
        bif_data = _make_bif([mdl_data, mdx_data])
        data_dir = gdir / 'data'
        data_dir.mkdir()
        (data_dir / 'models.bif').write_bytes(bif_data)

        # chitin.key: maps 'testmdl.mdl' → bif 0 var 0, 'testmdl.mdx' → bif 0 var 1
        key_data = _make_chitin_key(
            ['data/models.bif'],
            [
                ('testmdl', RES_MDL, 0, 0),
                ('testmdl', RES_MDX, 0, 1),
            ]
        )
        (gdir / 'chitin.key').write_bytes(key_data)

        # TexturePacks ERF with one TPC
        # Minimal TPC: 128-byte header, RGB uncompressed (enc=2, data_size=0), 1×1 pixel
        tpc_header = bytearray(128)
        struct.pack_into('<I', tpc_header, 0,  0)     # data_size=0 (uncompressed)
        struct.pack_into('<H', tpc_header, 8,  1)     # width=1
        struct.pack_into('<H', tpc_header, 10, 1)     # height=1
        tpc_header[12] = 2  # encoding=RGB
        tpc_header[13] = 1  # num_mips=1
        tpc_data = bytes(tpc_header) + bytes([255, 0, 255])  # 1×1 magenta pixel
        tp_dir = gdir / 'TexturePacks'
        tp_dir.mkdir()
        tex_erf_data = _make_erf({('fake_tex', RES_TPC): tpc_data})
        (tp_dir / 'textures_tpa.erf').write_bytes(tex_erf_data)

        # Override: loose .txi file
        ovr_dir = gdir / 'Override'
        ovr_dir.mkdir()
        (ovr_dir / 'foo.txi').write_bytes(b'bumpmap 1\n')

        return str(gdir)

    def test_set_k1_dir_success(self, fake_game_dir):
        mgr = ResourceManager()
        ok = mgr.set_k1_dir(fake_game_dir)
        assert ok
        assert mgr.is_ready()

    def test_get_mdl_from_bif(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        mdl = mgr.get_mdl('testmdl', 'K1')
        assert mdl is not None
        assert mdl.startswith(b'FAKE_MDL_DATA_')

    def test_get_mdx_from_bif(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        mdx = mgr.get_mdx('testmdl', 'K1')
        assert mdx is not None
        assert mdx.startswith(b'FAKE_MDX_DATA_')

    def test_get_texture_from_erf(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        raw = mgr.get_texture('fake_tex', 'K1')
        assert raw is not None
        assert len(raw) > 128  # at least TPC header + pixel

    def test_override_file_loaded(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        txi = mgr.get_txi('foo', 'K1')
        assert 'bumpmap' in txi

    def test_list_models_returns_testmdl(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        models = mgr.list_models('K1')
        resrefs = [r for r, _ in models]
        assert 'testmdl' in resrefs

    def test_has_textures_true(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        assert mgr.has_textures('K1')

    def test_stats_populated(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        s = mgr.stats()
        assert s['K1'] is not None
        assert s['K1']['tex_erfs'] >= 1

    def test_missing_resource_returns_none(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        assert mgr.get_mdl('nonexistent_model', 'K1') is None

    def test_cross_game_fallback(self, fake_game_dir):
        """If K2 not set but K1 is, auto-fallback should find K1 resources."""
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        # Direct K2 lookup should fail (no K2 dir set)
        direct_k2 = mgr._k2
        assert direct_k2 is None
        # But get() with game='K2' should fall back to K1
        mdl = mgr.get_mdl('testmdl', 'K2')
        assert mdl is not None  # fallback to K1

    def test_get_k1_returns_install(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        inst = mgr.get_k1()
        assert inst is not None
        assert inst.game_dir == os.path.normpath(fake_game_dir)

    def test_game_dir_accessor(self, fake_game_dir):
        mgr = ResourceManager()
        mgr.set_k1_dir(fake_game_dir)
        assert mgr.game_dir('K1') == os.path.normpath(fake_game_dir)
        assert mgr.game_dir('K2') is None


# ===========================================================================
# 6. Override priority chain
# ===========================================================================

class TestOverridePriority:
    """Override files must win over BIF data."""

    @pytest.fixture
    def game_with_override(self, tmp_path):
        gdir = tmp_path / 'override_test'
        gdir.mkdir()

        bif_data = _make_bif([b'BIF_VERSION'])
        (gdir / 'data').mkdir()
        (gdir / 'data' / 'models.bif').write_bytes(bif_data)

        key = _make_chitin_key(['data/models.bif'], [('mymdl', RES_MDL, 0, 0)])
        (gdir / 'chitin.key').write_bytes(key)

        ovr = gdir / 'Override'
        ovr.mkdir()
        (ovr / 'mymdl.mdl').write_bytes(b'OVERRIDE_VERSION')

        return str(gdir)

    def test_override_wins_over_bif(self, game_with_override):
        mgr = ResourceManager()
        mgr.set_k1_dir(game_with_override)
        data = mgr.get_mdl('mymdl', 'K1')
        assert data == b'OVERRIDE_VERSION', \
            f"Expected override data, got {data!r}"


# ===========================================================================
# 7. Texture decode helpers
# ===========================================================================

class TestTextureDecodeHelpers:
    def _make_tpc_uncompressed_rgb(self, w: int, h: int) -> bytes:
        """Build a minimal uncompressed RGB TPC."""
        hdr = bytearray(128)
        struct.pack_into('<I', hdr, 0,  0)     # data_size=0
        struct.pack_into('<H', hdr, 8,  w)
        struct.pack_into('<H', hdr, 10, h)
        hdr[12] = 2   # RGB
        hdr[13] = 1   # 1 mip
        pixel_data = bytes([100, 150, 200] * w * h)
        return bytes(hdr) + pixel_data

    def test_is_tpc_valid_rgb(self):
        data = self._make_tpc_uncompressed_rgb(4, 4)
        assert _is_tpc(data)

    def test_is_tpc_rejects_short_data(self):
        assert not _is_tpc(b'\x00' * 10)

    def test_is_tpc_rejects_bad_encoding(self):
        data = bytearray(self._make_tpc_uncompressed_rgb(4, 4))
        data[12] = 99  # bad encoding
        assert not _is_tpc(bytes(data))

    def test_is_tpc_rejects_zero_dimensions(self):
        data = bytearray(self._make_tpc_uncompressed_rgb(4, 4))
        struct.pack_into('<H', data, 8, 0)  # width=0
        assert not _is_tpc(bytes(data))

    def test_decode_tpc_rgb_1x1(self):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        data = self._make_tpc_uncompressed_rgb(1, 1)
        img = _decode_tpc(data)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (1, 1)
        r, g, b, a = img.getpixel((0, 0))
        assert r == 100
        assert g == 150
        assert b == 200
        assert a == 255

    def test_decode_tpc_greyscale_2x2(self):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        hdr = bytearray(128)
        struct.pack_into('<I', hdr, 0,  0)
        struct.pack_into('<H', hdr, 8,  2)
        struct.pack_into('<H', hdr, 10, 2)
        hdr[12] = 1   # greyscale
        hdr[13] = 1
        pixel_data = bytes([128, 64, 192, 255])  # 4 grey pixels
        raw = bytes(hdr) + pixel_data
        img = _decode_tpc(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (2, 2)

    def test_decode_texture_with_tga_fallback(self, tmp_path):
        """_decode_texture should fall back to PIL for a plain PNG."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        # Create a 2×2 red PNG in memory
        img_pil = Image.new('RGBA', (2, 2), (255, 0, 0, 255))
        buf = io.BytesIO()
        img_pil.save(buf, format='PNG')
        raw = buf.getvalue()
        result = _decode_texture(raw)
        assert result is not None
        assert result.mode == 'RGBA'

    def test_decode_texture_tpc_path(self):
        """_decode_texture should recognize and decode TPC data."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not installed")
        raw = self._make_tpc_uncompressed_rgb(2, 2)
        result = _decode_texture(raw)
        assert result is not None
        assert result.size == (2, 2)

    def test_decode_texture_empty_returns_none(self):
        assert _decode_texture(b'') is None

    def test_build_dds_has_correct_magic(self):
        dds = _build_dds(4, 4, 8, 'DXT1', b'\x00' * 8)
        assert dds[:4] == b'DDS '
        assert dds[84:88] == b'DXT1'

    def test_dxt_decode_1x1_dxt1(self):
        """Smoke test: decode a 1×1 DXT1 block without crashing."""
        # A minimal valid DXT1 block (8 bytes)
        # color0 = RGB565(255,0,0) = 0xF800, color1 = 0x0000, all pixels ci=0
        block = struct.pack('<HHI', 0xF800, 0x0000, 0x00000000)
        result = _dxt_decode(block, 4, 4, False)
        # Should produce 4×4×4 = 64 bytes
        assert len(result) == 64


# ===========================================================================
# 8. Real game data tests (skipped when not available)
# ===========================================================================

@pytest.mark.skipif(not HAS_K1, reason="K1 game data not available at tests/k1_extracted")
class TestWithRealK1Data:
    """Integration tests against the real K1 installation in tests/k1_extracted."""

    @pytest.fixture(scope='class')
    def mgr(self):
        m = ResourceManager()
        ok = m.set_k1_dir(str(K1_DIR))
        assert ok, "ResourceManager failed to index K1 data"
        return m

    def test_index_has_models(self, mgr):
        models = mgr.list_models('K1')
        assert len(models) > 100, f"Expected >100 models, got {len(models)}"

    def test_can_load_c_bantha(self, mgr):
        mdl = mgr.get_mdl('c_bantha', 'K1')
        assert mdl is not None
        assert len(mdl) > 1000

    def test_c_bantha_mdx_present(self, mgr):
        mdx = mgr.get_mdx('c_bantha', 'K1')
        assert mdx is not None
        assert len(mdx) > 100

    def test_texture_loading_speed(self, mgr):
        """Texture fetch must be <5 ms (was >500 ms with GameLibrary)."""
        import time
        raw = None
        # Try to find a texture name that actually exists
        for resref in ['c_bantha01', 'cmdrobe01', 'p_hk47_01']:
            raw = mgr.get_texture(resref, 'K1')
            if raw is not None:
                break
        if raw is None:
            pytest.skip("No test texture found")
        # Now time it
        name = 'c_bantha01'
        t0 = time.perf_counter()
        for _ in range(10):
            mgr.get_texture(name, 'K1')
        elapsed_ms = (time.perf_counter() - t0) * 100  # per-call average
        assert elapsed_ms < 5.0, \
            f"Texture fetch too slow: {elapsed_ms:.2f} ms (limit 5 ms)"

    def test_model_loading_with_parser(self, mgr):
        model = mgr.load_model('c_bantha', 'K1')
        assert model is not None
        assert model.node_count() > 0

    def test_stats_populated_correctly(self, mgr):
        s = mgr.stats()
        assert s['K1'] is not None
        k1 = s['K1']
        assert k1['key_entries'] > 1000
        assert k1['tex_erfs'] >= 1

    def test_list_models_speed(self, mgr):
        """list_models() must be <50 ms."""
        import time
        t0 = time.perf_counter()
        models = mgr.list_models('K1')
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 50, \
            f"list_models too slow: {elapsed_ms:.1f} ms"
        assert len(models) > 100


# ===========================================================================
# 9. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_reads_dont_crash(self):
        """Multiple threads reading from a ResourceManager must not deadlock."""
        import time
        mgr = ResourceManager()
        errors = []

        def _reader(i):
            try:
                mgr.get('nonexistent', RES_MDL)
                mgr.list_models()
                mgr.stats()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_reader, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not errors, f"Thread errors: {errors}"

    def test_set_dir_while_reading(self, tmp_path):
        """set_k1_dir during concurrent reads must not corrupt state."""
        # Build a minimal fake game dir
        gdir = tmp_path / 'g'
        gdir.mkdir()
        bif = _make_bif([b'hello'])
        (gdir / 'data').mkdir()
        (gdir / 'data' / 'm.bif').write_bytes(bif)
        key = _make_chitin_key(['data/m.bif'], [('a', RES_MDL, 0, 0)])
        (gdir / 'chitin.key').write_bytes(key)

        mgr = ResourceManager()
        errors = []

        def _read():
            for _ in range(50):
                try:
                    mgr.get('a', RES_MDL)
                    mgr.list_models()
                except Exception as e:
                    errors.append(e)

        def _write():
            import time
            time.sleep(0.01)
            try:
                mgr.set_k1_dir(str(gdir))
            except Exception as e:
                errors.append(e)

        readers = [threading.Thread(target=_read) for _ in range(5)]
        writer  = threading.Thread(target=_write)
        for t in readers:
            t.start()
        writer.start()
        for t in readers:
            t.join(timeout=5)
        writer.join(timeout=5)
        assert not errors, f"Concurrency errors: {errors}"


# ===========================================================================
# 10. TextureCache integration
# ===========================================================================

class TestTextureCacheIntegration:
    """Verify set_resource_manager wires into TextureCache correctly."""

    def test_set_resource_manager_present_in_texture_cache(self):
        """TextureCache should accept set_resource_manager without error."""
        # We can't easily instantiate ViewportWidget without a Tk display,
        # but we CAN import the TextureCache class and test it in isolation.
        import ast, sys
        # Verify the method exists in viewport.py source without importing Tk
        with open(str(REPO_ROOT / 'src' / 'gui' / 'viewport.py')) as f:
            source = f.read()
        tree = ast.parse(source)

        # Find all method definitions named set_resource_manager
        methods = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == 'set_resource_manager'
        ]
        assert len(methods) >= 2, \
            "Expected set_resource_manager in both TextureCache and ViewportWidget"

    def test_resource_manager_used_in_load_method(self):
        """_load() in TextureCache should reference _resource_manager."""
        with open(str(REPO_ROOT / 'src' / 'gui' / 'viewport.py')) as f:
            source = f.read()
        # Check that _resource_manager is used in the _load method
        assert 'resource_manager' in source
        assert 'resource_manager.get_texture' in source

    def test_main_window_imports_resource_manager(self):
        """main_window.py should import ResourceManager."""
        with open(str(REPO_ROOT / 'src' / 'gui' / 'main_window.py')) as f:
            source = f.read()
        assert 'from ..core.resource_manager import ResourceManager' in source

    def test_scan_uses_resource_manager(self):
        """_scan() in main_window.py should use ResourceManager for fast index."""
        with open(str(REPO_ROOT / 'src' / 'gui' / 'main_window.py')) as f:
            source = f.read()
        assert 'ResourceManager()' in source
        assert 'mgr.set_k1_dir' in source
        assert 'mgr.set_k2_dir' in source

    def test_on_library_load_prefers_resource_manager(self):
        """_on_library_load should prefer ResourceManager over legacy paths."""
        with open(str(REPO_ROOT / 'src' / 'gui' / 'main_window.py')) as f:
            source = f.read()
        # Check that _on_library_load uses set_resource_manager
        assert 'set_resource_manager' in source
        # Check that the new logic is present
        assert 'mgr.is_ready()' in source
