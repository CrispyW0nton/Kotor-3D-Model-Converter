"""
kotor_install.py — Fast KotOR Installation Resource Loader
===========================================================
Rebuilds the resource-access layer from scratch using direct binary
parsing of KEY/BIF/ERF files.

Design goals
------------
- Index the entire installation in < 100 ms (read only headers/indices).
- Fetch any individual resource in < 20 ms (a single seek + read).
- No dependency on pykotor's slow ``read_erf()`` path.
- Work with K1 and K2 game data directories that have the standard layout:
    <game_dir>/
        chitin.key          ← key file mapping resrefs to BIF entries
        data/
            models.bif      ← raw model data (MDL 2002, MDX 3008)
            ...
        TexturePacks/
            swpc_tex_tpa.erf  ← high-quality textures (TPC 3007)
            swpc_tex_tpb.erf
            swpc_tex_tpc.erf
            swpc_tex_gui.erf
        modules/
            *.mod / *.rim    ← area modules (for future use)
        Override/
            *                ← override files (highest priority)

Resource type constants (NWN / KotOR)
--------------------------------------
RES_MDL  = 2002   .mdl  model geometry
RES_MDX  = 3008   .mdx  model vertex data
RES_TPC  = 3007   .tpc  TPC texture (binary)
RES_TGA  = 3 (or 3002)  .tga  TGA texture
RES_TXI  = 2014   .txi  texture parameters
RES_UTC  = 2023   .utc  creature template
RES_ARE  = 2012   .are  area
RES_GFF  = 2037   .gff
"""

from __future__ import annotations

import os
import struct
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Resource-type integer constants ─────────────────────────────────────────
RES_BMP  = 1
RES_TGA  = 3
RES_WAV  = 4
RES_PLT  = 6
RES_INI  = 7
RES_TXT  = 10
RES_MDL  = 2002
RES_NSS  = 2009   # NB: 2009 is NSS script source; MDX is 3008
RES_MDX  = 3008
RES_TXI  = 2014
RES_ARE  = 2012
RES_IFO  = 2013
RES_UTC  = 2023
RES_DLG  = 2029
RES_TPC  = 3007
RES_LYT  = 3005
RES_VIS  = 3006
RES_2DA  = 2017
RES_GIT  = 2015

# Extension ↔ type mapping (lowercase)
EXT_TO_TYPE: Dict[str, int] = {
    'mdl': RES_MDL, 'mdx': RES_MDX,
    'tpc': RES_TPC, 'tga': RES_TGA, 'txi': RES_TXI,
    'utc': RES_UTC, 'are': RES_ARE, 'ifo': RES_IFO,
    'dlg': RES_DLG, 'lyt': RES_LYT, 'vis': RES_VIS,
    '2da': RES_2DA, 'git': RES_GIT,
}
TYPE_TO_EXT: Dict[int, str] = {v: k for k, v in EXT_TO_TYPE.items()}


def _res_key(name: str, res_type: int) -> str:
    """Canonical lookup key: lowercase name + type int."""
    return f"{name.lower()}:{res_type}"


# ── Fast BIF reader ──────────────────────────────────────────────────────────

class _BifIndex:
    """
    Reads and caches the variable-resource table from a BIF file.
    The table is 16 bytes/entry (ID, Offset, FileSize, ResType).
    Only the table is read at init time; actual data is fetched on demand.
    """
    __slots__ = ('path', '_entries')  # entries: dict[var_idx → (offset, size)]

    def __init__(self, path: str, expected_entries: int):
        self.path = path
        self._entries: Dict[int, Tuple[int, int]] = {}
        try:
            with open(path, 'rb') as f:
                # BIFF V1 header: type[4] ver[4] var_count[4] fixed_count[4] flags[4]
                hdr = f.read(20)
                var_count = struct.unpack_from('<I', hdr, 8)[0]
                # Variable resource table immediately after header
                table = f.read(var_count * 16)
            for i in range(var_count):
                base = i * 16
                offset   = struct.unpack_from('<I', table, base + 4)[0]
                filesize = struct.unpack_from('<I', table, base + 8)[0]
                self._entries[i] = (offset, filesize)
        except Exception as e:
            log.warning(f"BIF index failed for {path}: {e}")

    def read(self, var_idx: int) -> Optional[bytes]:
        entry = self._entries.get(var_idx)
        if entry is None:
            return None
        offset, size = entry
        try:
            with open(self.path, 'rb') as f:
                f.seek(offset)
                return f.read(size)
        except Exception as e:
            log.warning(f"BIF read error {self.path}[{var_idx}]: {e}")
            return None


# ── Fast ERF reader ──────────────────────────────────────────────────────────

class _ErfIndex:
    """
    Reads only the key list and resource list from an ERF/MOD/RIM.
    Actual resource data is fetched by seeking on demand.

    ERF V1.0 layout:
      Header  160 bytes
      Localized string list
      Key list  (entry_count × 24 bytes): resref[16] resID[4] resType[2] unused[2]
      Resource list (entry_count × 8 bytes): offset[4] size[4]
    """
    __slots__ = ('path', '_index')  # index: dict[key → (offset, size)]

    def __init__(self, path: str):
        self.path = path
        self._index: Dict[str, Tuple[int, int]] = {}
        try:
            with open(path, 'rb') as f:
                hdr = f.read(160)
            entry_count = struct.unpack_from('<I', hdr, 16)[0]
            off_keys    = struct.unpack_from('<I', hdr, 24)[0]
            off_res     = struct.unpack_from('<I', hdr, 28)[0]

            with open(path, 'rb') as f:
                f.seek(off_keys)
                key_data = f.read(entry_count * 24)
                f.seek(off_res)
                res_data = f.read(entry_count * 8)

            for i in range(entry_count):
                kb = i * 24
                rb = i * 8
                resref   = key_data[kb:kb+16].rstrip(b'\x00').decode('ascii', 'replace').lower()
                res_type = struct.unpack_from('<H', key_data, kb + 20)[0]
                offset   = struct.unpack_from('<I', res_data, rb)[0]
                size     = struct.unpack_from('<I', res_data, rb + 4)[0]
                k = _res_key(resref, res_type)
                self._index[k] = (offset, size)
        except Exception as e:
            log.warning(f"ERF index failed for {path}: {e}")

    def read(self, name: str, res_type: int) -> Optional[bytes]:
        entry = self._index.get(_res_key(name, res_type))
        if entry is None:
            return None
        offset, size = entry
        try:
            with open(self.path, 'rb') as f:
                f.seek(offset)
                return f.read(size)
        except Exception as e:
            log.warning(f"ERF read error {self.path} {name}: {e}")
            return None

    def list_resrefs(self, res_type: int) -> List[str]:
        suffix = f':{res_type}'
        return [k[:-len(suffix)] for k in self._index if k.endswith(suffix)]


# ── Main installation class ──────────────────────────────────────────────────

class KotorInstallation:
    """
    Fast, lazy-loading KotOR installation reader.

    Indexes the entire game in < 100 ms; each resource fetch is < 20 ms.
    Handles: KEY/BIF (models, scripts, 2DAs), ERF TexturePacks, Override/.

    Usage
    -----
    install = KotorInstallation('path/to/k1')
    mdl_bytes = install.get(name='c_bantha', res_type=RES_MDL)
    mdx_bytes = install.get('c_bantha', RES_MDX)
    tpc_bytes = install.get('c_bantha01', RES_TPC)
    model_list = install.list_models()
    """

    def __init__(self, game_dir: str):
        import time
        self.game_dir = os.path.normpath(game_dir)
        self._bif_index: Dict[int, _BifIndex] = {}       # bif_file_idx → _BifIndex
        self._key_map: Dict[str, Tuple[int, int]] = {}   # _res_key → (bif_idx, var_idx)
        self._erf_list: List[_ErfIndex] = []             # texture ERFs, priority order
        self._override: Dict[str, bytes] = {}            # Override/ files (pre-loaded)

        t0 = time.time()
        self._index_key()
        self._index_texture_erfs()
        self._index_override()
        t1 = time.time()
        log.info(f"KotorInstallation indexed {self.game_dir!r} in {t1-t0:.3f}s "
                 f"({len(self._key_map)} key entries, "
                 f"{len(self._erf_list)} texture ERFs)")

    # ── Indexing ─────────────────────────────────────────────────────────

    def _index_key(self):
        """Parse chitin.key and index all BIF entries."""
        key_path = os.path.join(self.game_dir, 'chitin.key')
        if not os.path.isfile(key_path):
            log.warning(f"chitin.key not found at {key_path}")
            return

        with open(key_path, 'rb') as f:
            raw = f.read()

        bif_count = struct.unpack_from('<I', raw, 8)[0]
        key_count = struct.unpack_from('<I', raw, 12)[0]
        off_bifs  = struct.unpack_from('<I', raw, 16)[0]
        off_keys  = struct.unpack_from('<I', raw, 20)[0]

        # Read BIF filenames
        bif_names: List[str] = []
        for i in range(bif_count):
            base = off_bifs + i * 12
            name_off  = struct.unpack_from('<I', raw, base + 4)[0]
            name_sz   = struct.unpack_from('<H', raw, base + 8)[0]
            raw_name  = raw[name_off:name_off + name_sz].rstrip(b'\x00').decode('ascii', 'replace')
            # Normalize Windows backslash paths
            norm = raw_name.replace('\\', os.sep)
            bif_names.append(norm)

        # Read key entries (22 bytes each: resref[16] type[2] id[4])
        key_raw = raw[off_keys: off_keys + key_count * 22]
        for i in range(key_count):
            base     = i * 22
            resref   = key_raw[base:base+16].rstrip(b'\x00').decode('ascii', 'replace').lower()
            res_type = struct.unpack_from('<H', key_raw, base + 16)[0]
            res_id   = struct.unpack_from('<I', key_raw, base + 18)[0]
            bif_idx  = (res_id >> 20) & 0xFFF
            var_idx  = res_id & 0xFFFFF
            self._key_map[_res_key(resref, res_type)] = (bif_idx, var_idx)

        # Lazy-create BIF index objects (don't open files yet)
        for i, name in enumerate(bif_names):
            full = os.path.join(self.game_dir, name)
            if os.path.isfile(full):
                self._bif_index[i] = _BifIndex(full, 0)
            else:
                # Try case-insensitive match
                found = self._find_case_insensitive(name)
                if found:
                    self._bif_index[i] = _BifIndex(found, 0)

    def _find_case_insensitive(self, rel_path: str) -> Optional[str]:
        """Try to find a file case-insensitively (for Linux)."""
        parts = rel_path.replace('\\', '/').split('/')
        current = self.game_dir
        for part in parts:
            if not os.path.isdir(current):
                return None
            try:
                entries = {e.lower(): e for e in os.listdir(current)}
                real = entries.get(part.lower())
                if real is None:
                    return None
                current = os.path.join(current, real)
            except OSError:
                return None
        return current if os.path.isfile(current) else None

    def _index_texture_erfs(self):
        """Index texture pack ERFs in priority order: TPA > TPB > TPC > GUI."""
        tp_dir = os.path.join(self.game_dir, 'TexturePacks')
        if not os.path.isdir(tp_dir):
            # Try lowercase
            tp_dir = os.path.join(self.game_dir, 'texturepacks')
        if not os.path.isdir(tp_dir):
            log.debug(f"No TexturePacks dir found in {self.game_dir}")
            return

        # Priority: tpa > tpb > tpc > gui
        priority = ['tpa', 'tpb', 'tpc', 'gui']
        erf_files = sorted(
            [f for f in os.listdir(tp_dir) if f.lower().endswith('.erf')],
            key=lambda f: next(
                (i for i, p in enumerate(priority) if p in f.lower()), 99
            )
        )
        for fname in erf_files:
            path = os.path.join(tp_dir, fname)
            log.debug(f"Indexing texture ERF: {fname}")
            self._erf_list.append(_ErfIndex(path))

    def _index_override(self):
        """Pre-load small Override/ files into memory."""
        ovr_dir = os.path.join(self.game_dir, 'Override')
        if not os.path.isdir(ovr_dir):
            return
        try:
            for fname in os.listdir(ovr_dir):
                path = os.path.join(ovr_dir, fname)
                if not os.path.isfile(path):
                    continue
                try:
                    base, ext = os.path.splitext(fname.lower())
                    res_type = EXT_TO_TYPE.get(ext.lstrip('.'))
                    if res_type is None:
                        continue
                    with open(path, 'rb') as f:
                        data = f.read()
                    self._override[_res_key(base, res_type)] = data
                except Exception:
                    pass
        except OSError:
            pass

    # ── Resource access ──────────────────────────────────────────────────

    def get(self, name: str, res_type: int) -> Optional[bytes]:
        """
        Fetch raw resource bytes by name + type.

        Priority order (matches KotOR engine):
          1. Override/
          2. ERF texture packs (TPA first)
          3. KEY/BIF archive
        """
        k = _res_key(name, res_type)

        # 1. Override
        data = self._override.get(k)
        if data is not None:
            return data

        # 2. ERF texture packs (for TPC/TGA textures)
        if res_type in (RES_TPC, RES_TGA, RES_TXI):
            for erf in self._erf_list:
                data = erf.read(name, res_type)
                if data is not None:
                    return data

        # 3. KEY/BIF
        entry = self._key_map.get(k)
        if entry is not None:
            bif_idx, var_idx = entry
            bif = self._bif_index.get(bif_idx)
            if bif:
                return bif.read(var_idx)

        return None

    def get_mdl(self, name: str) -> Optional[bytes]:
        return self.get(name, RES_MDL)

    def get_mdx(self, name: str) -> Optional[bytes]:
        return self.get(name, RES_MDX)

    def get_texture(self, name: str) -> Optional[bytes]:
        """Load texture: tries TPC then TGA."""
        data = self.get(name, RES_TPC)
        if data is not None:
            return data
        return self.get(name, RES_TGA)

    def get_txi(self, name: str) -> str:
        """Load TXI string for a texture name (empty string if none)."""
        data = self.get(name, RES_TXI)
        if data:
            try:
                return data.decode('ascii', 'replace')
            except Exception:
                return ''
        return ''

    # ── Listing ──────────────────────────────────────────────────────────

    def list_resrefs(self, res_type: int) -> List[str]:
        """List all resource names of a given type across all sources."""
        suffix = f':{res_type}'
        out = set()
        # KEY/BIF
        for k in self._key_map:
            if k.endswith(suffix):
                out.add(k[:-len(suffix)])
        # ERF texture packs
        for erf in self._erf_list:
            out.update(erf.list_resrefs(res_type))
        # Override
        for k in self._override:
            if k.endswith(suffix):
                out.add(k[:-len(suffix)])
        return sorted(out)

    def list_models(self) -> List[str]:
        return self.list_resrefs(RES_MDL)

    def list_textures(self) -> List[str]:
        return self.list_resrefs(RES_TPC)

    def has_resource(self, name: str, res_type: int) -> bool:
        k = _res_key(name, res_type)
        if k in self._override:
            return True
        if res_type in (RES_TPC, RES_TGA, RES_TXI):
            for erf in self._erf_list:
                if k in erf._index:
                    return True
        return k in self._key_map

    # ── Parsing convenience ──────────────────────────────────────────────

    def load_model(self, name: str):
        """
        Parse a model by name using PyKotor (kotor_loader).
        Returns a KotorModel or None.
        """
        mdl = self.get_mdl(name)
        if mdl is None:
            log.warning(f"Model not found: {name!r}")
            return None
        mdx = self.get_mdx(name) or b''
        try:
            from .kotor_loader import load_model_from_bytes
            return load_model_from_bytes(mdl, mdx)
        except Exception as e:
            log.error(f"Failed to parse model {name!r}: {e}", exc_info=True)
            return None

    def load_texture_image(self, name: str):
        """
        Load a texture as a PIL Image (RGBA).
        Returns None if not found or not decodable.
        """
        data = self.get_texture(name)
        if data is None:
            return None
        try:
            from src.gui.qt_lib.viewports.frame_renderer import _load_tpc_bytes
            img = _load_tpc_bytes(data)
            if img is None:
                # Fallback: try PIL direct (TGA)
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert('RGBA')
            return img
        except Exception as e:
            log.debug(f"Texture load error {name!r}: {e}")
            return None
