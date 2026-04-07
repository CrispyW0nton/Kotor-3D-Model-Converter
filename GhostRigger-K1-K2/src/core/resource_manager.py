"""
resource_manager.py — Unified KotOR Resource Manager
=====================================================
Single source of truth for all KotOR 1 & 2 resource access.

Architecture
------------
Rebuilt from ground up taking the best ideas from:
  • KotorBlender: header-only ERF/BIF parsing, lazy seek-on-demand reads
  • PyKotor:     Installation abstraction, module ERF support, override priority

Design principles
-----------------
1. Index-only init (< 150 ms): reads only file headers and key tables,
   never loads actual resource data during startup.
2. Lazy seek reads (< 2 ms): each get() does a single lseek + read.
3. Priority chain (matches KotOR engine):
      Override/ > TexturePacks ERF > module ERF > BIF (via chitin.key)
4. Module support: any .mod/.rim/.erf in modules/ is auto-indexed.
5. Single unified API: one get(name, type) call handles everything.
6. Thread-safe: all index lookups use read-only dicts (no locks needed
   after init); file reads use per-call open() for safety.

Resource type constants (NWN / KotOR standard)
----------------------------------------------
MDL  = 2002   .mdl  binary model geometry
MDX  = 3008   .mdx  binary model vertex data
TPC  = 3007   .tpc  TPC compressed texture
TGA  = 3       .tga  TGA/TPC texture (KotOR stores TPC with .tga extension)
TXI  = 2014   .txi  texture parameters
UTC  = 2023   .utc  creature template
ARE  = 2012   .are  area data
IFO  = 2013   .ifo  module info
DLG  = 2029   .dlg  dialog tree
LYT  = 3005   .lyt  area layout
VIS  = 3006   .vis  area visibility
2DA  = 2017   .2da  two-dimensional array
GIT  = 2015   .git  area instance template
NSS  = 2009   .nss  NWScript source
NCS  = 2010   .ncs  NWScript compiled
SSF  = 2015   .ssf  sound set file
"""

from __future__ import annotations

import os
import struct
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# ── Resource type constants ──────────────────────────────────────────────────

RES_BMP  = 1
RES_TGA  = 3
RES_WAV  = 4
RES_PLT  = 6
RES_INI  = 7
RES_TXT  = 10
RES_MDL  = 2002
RES_NSS  = 2009
RES_NCS  = 2010
RES_MDX  = 3008
RES_TXI  = 2014
RES_ARE  = 2012
RES_IFO  = 2013
RES_UTC  = 2023
RES_UTP  = 2044
RES_UTD  = 2038
RES_DLG  = 2029
RES_TPC  = 3007
RES_LYT  = 3005
RES_VIS  = 3006
RES_2DA  = 2017
RES_GIT  = 2015
RES_MOD  = 3011  # module reference
RES_WOK  = 3003  # walkmesh

# Extension ↔ type tables
EXT_TO_TYPE: Dict[str, int] = {
    'mdl': RES_MDL, 'mdx': RES_MDX,
    'tpc': RES_TPC, 'tga': RES_TGA, 'txi': RES_TXI,
    'utc': RES_UTC, 'utp': RES_UTP, 'utd': RES_UTD,
    'are': RES_ARE, 'ifo': RES_IFO, 'dlg': RES_DLG,
    'lyt': RES_LYT, 'vis': RES_VIS, '2da': RES_2DA,
    'git': RES_GIT, 'wok': RES_WOK,
    'wav': RES_WAV, 'mp3': RES_WAV,
    'bmp': RES_BMP, 'ini': RES_INI, 'txt': RES_TXT,
    'nss': RES_NSS, 'ncs': RES_NCS,
}
TYPE_TO_EXT: Dict[int, str] = {v: k for k, v in EXT_TO_TYPE.items()}


def _key(name: str, res_type: int) -> str:
    """Canonical lookup key: lowercase name + type."""
    return f"{name.lower()}:{res_type}"


# ── Low-level archive readers ────────────────────────────────────────────────

class _BifIndex:
    """
    Reads only the variable-resource table from a BIFF V1 file.
    Table: entry_count × 16 bytes (ID[4], Offset[4], FileSize[4], ResType[4]).
    Actual data is read on demand via seek+read.
    """
    __slots__ = ('path', '_table')  # _table: dict[var_idx → (offset, size)]

    def __init__(self, path: str):
        self.path = path
        self._table: Dict[int, Tuple[int, int]] = {}
        try:
            with open(path, 'rb') as fh:
                hdr = fh.read(20)
                var_count = struct.unpack_from('<I', hdr, 8)[0]
                raw = fh.read(var_count * 16)
            for i in range(var_count):
                b = i * 16
                offset   = struct.unpack_from('<I', raw, b + 4)[0]
                filesize = struct.unpack_from('<I', raw, b + 8)[0]
                self._table[i] = (offset, filesize)
        except Exception as exc:
            log.warning(f"BIF index failed {path}: {exc}")

    def read(self, var_idx: int) -> Optional[bytes]:
        slot = self._table.get(var_idx)
        if slot is None:
            return None
        offset, size = slot
        try:
            with open(self.path, 'rb') as fh:
                fh.seek(offset)
                return fh.read(size)
        except Exception as exc:
            log.warning(f"BIF read error {self.path}[{var_idx}]: {exc}")
            return None


class _ErfIndex:
    """
    Reads only the key + resource lists from an ERF/MOD/RIM/SAV file.
    ERF V1 layout:
      Header  160 bytes
        [16]: entry_count  uint32
        [24]: off_keys     uint32  (key list offset)
        [28]: off_res      uint32  (resource list offset)
      Key list:  entry_count × 24 bytes
        resref[16]  resID[4]  resType[2]  unused[2]
      Resource list:  entry_count × 8 bytes
        offset[4]  size[4]
    No resource data is read at index time.
    """
    __slots__ = ('path', '_index')  # _index: dict[key → (offset, size)]

    def __init__(self, path: str):
        self.path = path
        self._index: Dict[str, Tuple[int, int]] = {}
        try:
            with open(path, 'rb') as fh:
                hdr = fh.read(160)
            entry_count = struct.unpack_from('<I', hdr, 16)[0]
            off_keys    = struct.unpack_from('<I', hdr, 24)[0]
            off_res     = struct.unpack_from('<I', hdr, 28)[0]
            if entry_count == 0:
                return
            with open(path, 'rb') as fh:
                fh.seek(off_keys)
                key_raw = fh.read(entry_count * 24)
                fh.seek(off_res)
                res_raw = fh.read(entry_count * 8)
            for i in range(entry_count):
                kb = i * 24
                rb = i * 8
                resref   = key_raw[kb:kb+16].split(b'\x00', 1)[0].decode('ascii', 'replace').lower()
                res_type = struct.unpack_from('<H', key_raw, kb + 20)[0]
                offset   = struct.unpack_from('<I', res_raw, rb)[0]
                size     = struct.unpack_from('<I', res_raw, rb + 4)[0]
                k = _key(resref, res_type)
                self._index[k] = (offset, size)
        except Exception as exc:
            log.warning(f"ERF index failed {path}: {exc}")

    def read(self, name: str, res_type: int) -> Optional[bytes]:
        slot = self._index.get(_key(name, res_type))
        if slot is None:
            return None
        offset, size = slot
        try:
            with open(self.path, 'rb') as fh:
                fh.seek(offset)
                return fh.read(size)
        except Exception as exc:
            log.warning(f"ERF read {self.path} {name}: {exc}")
            return None

    def list_type(self, res_type: int) -> List[str]:
        suffix = f':{res_type}'
        return [k[:-(len(suffix))] for k in self._index if k.endswith(suffix)]

    def has(self, name: str, res_type: int) -> bool:
        return _key(name, res_type) in self._index


# ── ResourceManager ──────────────────────────────────────────────────────────

class ResourceManager:
    """
    Unified KotOR installation resource manager.

    Handles K1, K2, or both simultaneously.  Each installation is indexed
    independently; resource lookup checks the correct installation based on
    game tag, with cross-game fallback.

    Lookup priority per game (matches KotOR engine):
      1. Override/ loose files  (pre-loaded into memory for instant access)
      2. module ERFs (*.mod / *.rim / *.erf in modules/)
      3. TexturePacks ERFs       (for TPC/TGA only, TPA > TPB > TPC > GUI)
      4. chitin.key / BIF        (base game data)

    Thread safety
    -------------
    All dicts are populated once at init and never modified afterwards.
    Reads are concurrent-safe (no locks needed for dict lookups or file reads).
    """

    def __init__(self):
        self._k1: Optional[_GameInstall] = None
        self._k2: Optional[_GameInstall] = None
        self._lock = threading.Lock()  # protects lazy init only

    # ── Setup ────────────────────────────────────────────────────────────

    def set_k1_dir(self, path: str) -> bool:
        """Index a KotOR 1 installation directory. Returns True on success."""
        if not path or not os.path.isdir(path):
            return False
        try:
            inst = _GameInstall(path, 'K1')
            with self._lock:
                self._k1 = inst
            log.info(f"ResourceManager: K1 indexed {path!r} — "
                     f"{len(inst._key_map)} key entries, "
                     f"{len(inst._tex_erfs)} tex ERFs, "
                     f"{len(inst._mod_erfs)} module ERFs, "
                     f"{len(inst._override)} override files")
            return True
        except Exception as exc:
            log.error(f"ResourceManager: K1 index failed {path!r}: {exc}", exc_info=True)
            return False

    def set_k2_dir(self, path: str) -> bool:
        """Index a KotOR 2 installation directory. Returns True on success."""
        if not path or not os.path.isdir(path):
            return False
        try:
            inst = _GameInstall(path, 'K2')
            with self._lock:
                self._k2 = inst
            log.info(f"ResourceManager: K2 indexed {path!r} — "
                     f"{len(inst._key_map)} key entries, "
                     f"{len(inst._tex_erfs)} tex ERFs, "
                     f"{len(inst._mod_erfs)} module ERFs, "
                     f"{len(inst._override)} override files")
            return True
        except Exception as exc:
            log.error(f"ResourceManager: K2 index failed {path!r}: {exc}", exc_info=True)
            return False

    def get_k1(self) -> Optional['_GameInstall']:
        return self._k1

    def get_k2(self) -> Optional['_GameInstall']:
        return self._k2

    def is_ready(self) -> bool:
        """True if at least one installation is indexed."""
        return self._k1 is not None or self._k2 is not None

    # ── Resource access ──────────────────────────────────────────────────

    def get(self, name: str, res_type: int, game: str = 'K1') -> Optional[bytes]:
        """
        Fetch raw resource bytes.

        game: 'K1', 'K2', or 'auto' (tries game-tagged install first,
              then the other one as fallback).
        """
        inst = self._k1 if game == 'K1' else self._k2
        if inst is not None:
            data = inst.get(name, res_type)
            if data is not None:
                return data
        # Fallback: try the other installation
        other = self._k2 if game == 'K1' else self._k1
        if other is not None:
            data = other.get(name, res_type)
            if data is not None:
                return data
        return None

    def get_mdl(self, name: str, game: str = 'K1') -> Optional[bytes]:
        return self.get(name, RES_MDL, game)

    def get_mdx(self, name: str, game: str = 'K1') -> Optional[bytes]:
        return self.get(name, RES_MDX, game)

    def get_texture(self, name: str, game: str = 'K1') -> Optional[bytes]:
        """Load texture: TPC first, then TGA."""
        data = self.get(name, RES_TPC, game)
        if data is not None:
            return data
        return self.get(name, RES_TGA, game)

    def get_txi(self, name: str, game: str = 'K1') -> str:
        """Return TXI string for texture name (empty string if absent)."""
        raw = self.get(name, RES_TXI, game)
        if raw:
            try:
                return raw.decode('ascii', 'replace')
            except Exception:
                return ''
        return ''

    # ── Model listing ────────────────────────────────────────────────────

    def list_models(self, game: str = 'all') -> List[Tuple[str, str]]:
        """
        List all model resrefs as (resref, game_tag) tuples.
        game: 'K1', 'K2', or 'all'.
        """
        out: List[Tuple[str, str]] = []
        if game in ('K1', 'all') and self._k1:
            for r in self._k1.list_resrefs(RES_MDL):
                out.append((r, 'K1'))
        if game in ('K2', 'all') and self._k2:
            for r in self._k2.list_resrefs(RES_MDL):
                out.append((r, 'K2'))
        return out

    def list_textures(self, game: str = 'all') -> List[Tuple[str, str]]:
        """List all texture resrefs as (resref, game_tag) tuples."""
        out: List[Tuple[str, str]] = []
        if game in ('K1', 'all') and self._k1:
            for r in self._k1.list_resrefs(RES_TPC):
                out.append((r, 'K1'))
        if game in ('K2', 'all') and self._k2:
            for r in self._k2.list_resrefs(RES_TPC):
                out.append((r, 'K2'))
        return out

    def has_textures(self, game: str = 'all') -> bool:
        """Quick check: does any installation have texture data?

        Checks both TexturePacks ERF files AND BIF key_map entries (TPC/TGA).
        Most KotOR installations store textures in BIF archives via chitin.key —
        having TexturePacks ERFs is the exception, not the rule.  Previously this
        only checked _tex_erfs, which returned False for many valid installations,
        causing show_texture to never auto-enable.
        """
        # Check TexturePacks ERFs first (fast, common on modded installs)
        if game in ('K1', 'all') and self._k1:
            if self._k1._tex_erfs:
                return True
            # Also check BIF key_map for TPC (3007) or TGA (3) entries
            for k in self._k1._key_map:
                if k.endswith(f':{RES_TPC}') or k.endswith(f':{RES_TGA}'):
                    return True
        if game in ('K2', 'all') and self._k2:
            if self._k2._tex_erfs:
                return True
            for k in self._k2._key_map:
                if k.endswith(f':{RES_TPC}') or k.endswith(f':{RES_TGA}'):
                    return True
        return False

    # ── High-level loaders ───────────────────────────────────────────────

    def load_model(self, name: str, game: str = 'K1'):
        """
        Load and parse a model by resref name.
        Returns a KotorModel on success, None on failure.
        """
        mdl = self.get_mdl(name, game)
        if mdl is None:
            log.warning(f"ResourceManager.load_model: '{name}' not found in {game}")
            return None
        mdx = self.get_mdx(name, game) or b''
        try:
            from .mdl_parser import MDLBinaryParser
            parser = MDLBinaryParser(mdl, mdx)
            model = parser.parse()
            return model
        except Exception as exc:
            log.error(f"ResourceManager.load_model: parse failed for '{name}': {exc}",
                      exc_info=True)
            return None

    def load_texture_image(self, name: str, game: str = 'K1',
                           max_size: int = 512) -> Optional[object]:
        """
        Load a texture as a PIL Image (RGBA).
        Returns None if not found or not decodable.
        Applies resize to max_size if needed.
        """
        raw = self.get_texture(name, game)
        if raw is None:
            return None
        try:
            img = _decode_texture(raw)
            if img is None:
                return None
            if max_size and (img.width > max_size or img.height > max_size):
                img.thumbnail((max_size, max_size))
            return img
        except Exception as exc:
            log.debug(f"ResourceManager.load_texture_image: '{name}' decode failed: {exc}")
            return None

    def game_dir(self, game: str) -> Optional[str]:
        """Return the game directory for 'K1' or 'K2', or None if not set."""
        inst = self._k1 if game == 'K1' else self._k2
        return inst.game_dir if inst else None

    def stats(self) -> Dict[str, object]:
        """Return a dict of statistics for diagnostics."""
        result = {}
        for tag, inst in [('K1', self._k1), ('K2', self._k2)]:
            if inst:
                result[tag] = {
                    'dir': inst.game_dir,
                    'key_entries': len(inst._key_map),
                    'tex_erfs': len(inst._tex_erfs),
                    'mod_erfs': len(inst._mod_erfs),
                    'override': len(inst._override),
                }
            else:
                result[tag] = None
        return result


# ── Per-game installation ────────────────────────────────────────────────────

class _GameInstall:
    """
    Internal class: indexes one KotOR installation (K1 or K2).

    Priority chain for get():
      1. _override dict  (pre-loaded loose Override/ files, instant)
      2. _mod_erfs list  (module ERFs, lazy seek)
      3. _tex_erfs list  (TexturePacks ERFs for TPC/TGA, lazy seek)
      4. _bif_index dict (BIF files via chitin.key, lazy seek)
    """

    def __init__(self, game_dir: str, tag: str):
        import time
        self.game_dir = os.path.normpath(game_dir)
        self.tag = tag

        self._key_map: Dict[str, Tuple[int, int]] = {}    # _key → (bif_idx, var_idx)
        self._bif_index: Dict[int, _BifIndex] = {}        # bif_file_idx → _BifIndex
        self._tex_erfs: List[_ErfIndex] = []              # TexturePacks ERFs, TPA first
        self._mod_erfs: List[_ErfIndex] = []              # modules/ ERFs
        self._override: Dict[str, bytes] = {}             # Override/ loose files

        t0 = time.perf_counter()
        self._index_chitin()
        self._index_texture_packs()
        self._index_modules()
        self._load_override()
        elapsed = (time.perf_counter() - t0) * 1000
        log.debug(f"_GameInstall {tag} indexed {game_dir!r} in {elapsed:.0f}ms")

    # ── Indexing ──────────────────────────────────────────────────────────

    def _index_chitin(self):
        """Parse chitin.key → build _key_map and lazy-init _bif_index."""
        key_path = self._find_file('chitin.key')
        if not key_path:
            log.warning(f"_GameInstall {self.tag}: chitin.key not found in {self.game_dir!r}")
            return
        try:
            with open(key_path, 'rb') as fh:
                raw = fh.read()
        except OSError as exc:
            log.warning(f"_GameInstall: chitin.key read error: {exc}")
            return

        bif_count = struct.unpack_from('<I', raw, 8)[0]
        key_count = struct.unpack_from('<I', raw, 12)[0]
        off_bifs  = struct.unpack_from('<I', raw, 16)[0]
        off_keys  = struct.unpack_from('<I', raw, 20)[0]

        # Build BIF filename list
        bif_names: List[str] = []
        for i in range(bif_count):
            base = off_bifs + i * 12
            name_off = struct.unpack_from('<I', raw, base + 4)[0]
            name_sz  = struct.unpack_from('<H', raw, base + 8)[0]
            raw_name = raw[name_off:name_off + name_sz].split(b'\x00', 1)[0]
            name_str = raw_name.decode('ascii', 'replace').replace('\\', os.sep)
            bif_names.append(name_str)

        # Parse key entries: 22 bytes each — resref[16] type[2] id[4]
        key_raw = raw[off_keys: off_keys + key_count * 22]
        for i in range(key_count):
            b       = i * 22
            resref  = key_raw[b:b+16].split(b'\x00', 1)[0].decode('ascii', 'replace').lower()
            rtype   = struct.unpack_from('<H', key_raw, b + 16)[0]
            res_id  = struct.unpack_from('<I', key_raw, b + 18)[0]
            bif_idx = (res_id >> 20) & 0xFFF
            var_idx = res_id & 0xFFFFF
            self._key_map[_key(resref, rtype)] = (bif_idx, var_idx)

        # Lazy-init BIF readers
        for idx, name in enumerate(bif_names):
            full = os.path.join(self.game_dir, name)
            if os.path.isfile(full):
                self._bif_index[idx] = _BifIndex(full)
            else:
                found = self._find_file_ci(name)
                if found:
                    self._bif_index[idx] = _BifIndex(found)
                else:
                    log.debug(f"_GameInstall {self.tag}: BIF not found: {name}")

    def _index_texture_packs(self):
        """Index TexturePacks/ ERFs in priority order: TPA > TPB > TPC > GUI."""
        tp_dir = self._find_dir('TexturePacks') or self._find_dir('texturepacks')
        if not tp_dir:
            return
        priority_order = ['tpa', 'tpb', 'tpc', 'gui']
        try:
            erf_files = sorted(
                [f for f in os.listdir(tp_dir) if f.lower().endswith('.erf')],
                key=lambda f: next(
                    (i for i, p in enumerate(priority_order) if p in f.lower()), 99
                )
            )
        except OSError:
            return
        for fname in erf_files:
            path = os.path.join(tp_dir, fname)
            idx = _ErfIndex(path)
            if idx._index:
                self._tex_erfs.append(idx)
                log.debug(f"_GameInstall {self.tag}: tex ERF {fname} "
                          f"({len(idx._index)} entries)")

    def _index_modules(self):
        """Index module ERFs (*.mod, *.rim, *.erf) in modules/."""
        mod_dir = self._find_dir('modules') or self._find_dir('Modules')
        if not mod_dir:
            return
        try:
            files = os.listdir(mod_dir)
        except OSError:
            return
        for fname in sorted(files):
            if fname.lower().endswith(('.mod', '.rim', '.erf')):
                path = os.path.join(mod_dir, fname)
                idx = _ErfIndex(path)
                if idx._index:
                    self._mod_erfs.append(idx)
        log.debug(f"_GameInstall {self.tag}: {len(self._mod_erfs)} module ERFs")

    def _load_override(self):
        """Pre-load Override/ loose files into memory (fast path for overrides)."""
        ovr_dir = self._find_dir('Override') or self._find_dir('override')
        if not ovr_dir:
            return
        loaded = 0
        try:
            for fname in os.listdir(ovr_dir):
                path = os.path.join(ovr_dir, fname)
                if not os.path.isfile(path):
                    continue
                base, ext = os.path.splitext(fname.lower())
                rtype = EXT_TO_TYPE.get(ext.lstrip('.'))
                if rtype is None:
                    continue
                try:
                    with open(path, 'rb') as fh:
                        self._override[_key(base, rtype)] = fh.read()
                    loaded += 1
                except OSError:
                    pass
        except OSError:
            pass
        if loaded:
            log.debug(f"_GameInstall {self.tag}: {loaded} Override files loaded")

    # ── Resource access ───────────────────────────────────────────────────

    def get(self, name: str, res_type: int) -> Optional[bytes]:
        """
        Fetch raw resource bytes by name + type.
        Priority: Override > modules ERF > TexturePacks ERF > BIF.
        """
        k = _key(name, res_type)

        # 1. Override
        data = self._override.get(k)
        if data is not None:
            return data

        # 2. Module ERFs (area-specific resources)
        for erf in self._mod_erfs:
            if erf.has(name, res_type):
                data = erf.read(name, res_type)
                if data is not None:
                    return data

        # 3. TexturePacks ERFs (for TPC/TGA/TXI only — texture-specific)
        if res_type in (RES_TPC, RES_TGA, RES_TXI):
            for erf in self._tex_erfs:
                data = erf.read(name, res_type)
                if data is not None:
                    return data

        # 4. BIF via chitin.key
        slot = self._key_map.get(k)
        if slot is not None:
            bif_idx, var_idx = slot
            bif = self._bif_index.get(bif_idx)
            if bif is not None:
                return bif.read(var_idx)

        return None

    def has(self, name: str, res_type: int) -> bool:
        k = _key(name, res_type)
        if k in self._override:
            return True
        for erf in self._mod_erfs:
            if erf.has(name, res_type):
                return True
        if res_type in (RES_TPC, RES_TGA, RES_TXI):
            for erf in self._tex_erfs:
                if erf.has(name, res_type):
                    return True
        return k in self._key_map

    def list_resrefs(self, res_type: int) -> List[str]:
        """List all known resource names of given type (sorted, deduped)."""
        out: Set[str] = set()
        suffix = f':{res_type}'
        for k in self._override:
            if k.endswith(suffix):
                out.add(k[:-(len(suffix))])
        for erf in self._mod_erfs:
            for r in erf.list_type(res_type):
                out.add(r)
        for erf in self._tex_erfs:
            for r in erf.list_type(res_type):
                out.add(r)
        for k in self._key_map:
            if k.endswith(suffix):
                out.add(k[:-(len(suffix))])
        return sorted(out)

    # ── Path helpers ──────────────────────────────────────────────────────

    def _find_file(self, name: str) -> Optional[str]:
        """Find a file directly under game_dir, case-insensitively."""
        exact = os.path.join(self.game_dir, name)
        if os.path.isfile(exact):
            return exact
        try:
            entries = {e.lower(): e for e in os.listdir(self.game_dir)}
            real = entries.get(name.lower())
            if real:
                return os.path.join(self.game_dir, real)
        except OSError:
            pass
        return None

    def _find_dir(self, name: str) -> Optional[str]:
        """Find a subdirectory under game_dir, case-insensitively."""
        exact = os.path.join(self.game_dir, name)
        if os.path.isdir(exact):
            return exact
        try:
            entries = {e.lower(): e for e in os.listdir(self.game_dir)}
            real = entries.get(name.lower())
            if real:
                candidate = os.path.join(self.game_dir, real)
                if os.path.isdir(candidate):
                    return candidate
        except OSError:
            pass
        return None

    def _find_file_ci(self, rel_path: str) -> Optional[str]:
        """Find a file via case-insensitive multi-component path walk."""
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


# ── Texture decoding helper ──────────────────────────────────────────────────

# Cache the PyKotor bridge import to avoid repeated ImportError overhead
_pykotor_tpc_to_pil = None
_pykotor_bridge_checked = False


def _get_pykotor_tpc_fn():
    """Lazily import pykotor_tpc_to_pil; returns None if unavailable."""
    global _pykotor_tpc_to_pil, _pykotor_bridge_checked
    if _pykotor_bridge_checked:
        return _pykotor_tpc_to_pil
    _pykotor_bridge_checked = True
    try:
        from .pykotor_bridge import pykotor_tpc_to_pil as _fn
        _pykotor_tpc_to_pil = _fn
    except Exception:
        _pykotor_tpc_to_pil = None
    return _pykotor_tpc_to_pil


def _decode_texture(raw: bytes) -> Optional[object]:
    """
    Decode raw texture bytes (TPC or TGA) to a PIL RGBA Image.

    Routing (priority order):
      1. PyKotor bridge  — handles DXT1/DXT3/DXT5, cubemaps, TXI extraction,
                           V-flip correction.  Used whenever PyKotor is
                           available AND the data looks like a TPC file.
      2. _decode_tpc     — legacy pure-Python software decoder (fallback when
                           PyKotor is unavailable or the bridge call fails).
      3. PIL direct      — TGA / PNG / DDS passthrough (for non-TPC textures).

    PyKotor migration status: ~100% migrated for TPC files.  The legacy
    _decode_tpc path is kept as a safety net but is no longer the primary route.

    Returns None if PIL is unavailable or all decoders fail.
    """
    try:
        from PIL import Image
        import io as _io
    except ImportError:
        return None

    if not raw:
        return None

    # ── Primary: PyKotor bridge (handles all TPC variants, V-flip, TXI) ──
    if _is_tpc(raw):
        pk_fn = _get_pykotor_tpc_fn()
        if pk_fn is not None:
            try:
                img = pk_fn(raw)
                if img is not None:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    return img
            except Exception as _bridge_err:
                log.debug("_decode_texture: PyKotor bridge failed (%s), falling back", _bridge_err)

        # ── Secondary: legacy pure-Python decoder ─────────────────────────
        # Only reached when PyKotor is unavailable or threw an unexpected error.
        try:
            img = _decode_tpc(raw)
            if img is not None:
                return img
        except Exception as _legacy_err:
            log.debug("_decode_texture: legacy _decode_tpc failed (%s)", _legacy_err)

    # ── Tertiary: PIL direct (TGA, PNG, DDS, BMP, etc.) ───────────────────
    try:
        img = Image.open(_io.BytesIO(raw)).convert('RGBA')
        return img
    except Exception:
        return None


def tpc_info(raw: bytes) -> Optional[Dict[str, Any]]:
    """Return a dict of TPC header fields, or None if *raw* is not a TPC file.

    Useful for diagnostics and migration testing.  Fields returned:
      ``data_size``, ``alpha_test``, ``width``, ``height``,
      ``encoding``, ``num_mips``, ``is_compressed``,
      ``format`` (human-readable string: 'DXT1', 'DXT5', 'Grey', 'RGB', 'RGBA').
    """
    if not _is_tpc(raw):
        return None
    data_size = struct.unpack_from('<I', raw, 0)[0]
    alpha_test = struct.unpack_from('<f', raw, 4)[0]
    width  = struct.unpack_from('<H', raw, 8)[0]
    height = struct.unpack_from('<H', raw, 10)[0]
    encoding = raw[12]
    num_mips = raw[13]
    compressed = data_size > 0
    fmt_map = {1: 'Grey', 2: ('DXT1' if compressed else 'RGB'),
               4: ('DXT5' if compressed else 'RGBA'), 12: 'RGBA'}
    return {
        'data_size':   data_size,
        'alpha_test':  alpha_test,
        'width':       width,
        'height':      height,
        'encoding':    encoding,
        'num_mips':    num_mips,
        'is_compressed': compressed,
        'format':      fmt_map.get(encoding, f'unknown({encoding})'),
    }


def _is_tpc(raw: bytes) -> bool:
    """Heuristic: is this a KotOR TPC file?

    Checks the 128-byte TPC header for valid encoding ID, non-zero power-of-two
    dimensions, and consistent data_size / encoding pairing.  Also rejects data
    that starts with PNG/JPEG/BMP/DDS magic bytes since those cannot be TPC.
    """
    if len(raw) < 128:
        return False

    # Fast-reject: known non-TPC magic bytes
    # PNG: 0x89 50 4E 47 | JPEG: FF D8 FF | BMP: 42 4D | DDS: 44 44 53 20
    if raw[:4] in (b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1',
                   b'DDS ', b'BM\x00\x00'):
        return False

    # TPC header layout (all little-endian):
    #   offset 0  : uint32 data_size   — 0 for uncompressed, >0 for DXT
    #   offset 4  : float  alpha_test
    #   offset 8  : uint16 width
    #   offset 10 : uint16 height
    #   offset 12 : uint8  encoding   (1=Grey, 2=RGB/DXT1, 4=RGBA/DXT5, 12=RGBA)
    #   offset 13 : uint8  num_mips
    data_size = struct.unpack_from('<I', raw, 0)[0]
    width     = struct.unpack_from('<H', raw, 8)[0]
    height    = struct.unpack_from('<H', raw, 10)[0]
    encoding  = raw[12]
    num_mips  = raw[13]

    # Valid encoding IDs
    if encoding not in (1, 2, 4, 12):
        return False

    # Dimensions must be non-zero and power-of-two ≤ 4096
    if width == 0 or height == 0 or width > 4096 or height > 4096:
        return False
    if (width & (width - 1)) != 0 or (height & (height - 1)) != 0:
        return False

    # For compressed formats (data_size > 0) only encoding 2 (DXT1) or 4 (DXT5)
    # are valid.  Encoding 1 (Grey) or 12 (RGBA) are always uncompressed.
    if data_size > 0 and encoding not in (2, 4):
        return False

    # Sanity: num_mips should be between 1 and 13 (log2(4096)+1)
    if num_mips == 0 or num_mips > 13:
        return False

    # Total file size lower-bound check
    if data_size > 0:
        if len(raw) < 128 + data_size:
            return False
    else:
        min_pixels = width * height
        bytes_per_px = {1: 1, 2: 3, 4: 4, 12: 4}.get(encoding, 4)
        if len(raw) < 128 + min_pixels * bytes_per_px:
            return False

    return True


def _decode_tpc(raw: bytes) -> Optional[object]:
    """
    Decode a KotOR TPC file to a PIL RGBA Image.
    Supports: DXT1 (enc=2), DXT5 (enc=4), uncompressed Grey/RGB/RGBA (enc=1/2/4 with data_size=0).
    """
    try:
        from PIL import Image
        import io as _io
    except ImportError:
        return None

    data_size = struct.unpack_from('<I', raw, 0)[0]
    width     = struct.unpack_from('<H', raw, 8)[0]
    height    = struct.unpack_from('<H', raw, 10)[0]
    encoding  = raw[12]
    num_mips  = raw[13]

    compressed = (data_size > 0)
    pixel_data = raw[128:]

    if compressed:
        # DXT1 (RGB, no alpha) = enc 2, DXT5 (RGBA) = enc 4
        dxt_type = 'DXT1' if encoding == 2 else 'DXT5'
        try:
            img = Image.frombytes('RGBA', (width, height), pixel_data[:data_size],
                                  'bcn', (1 if dxt_type == 'DXT1' else 3))
            return img.convert('RGBA')
        except Exception:
            pass
        # Fallback: try imageio or squish
        try:
            import struct as _struct
            # Build a minimal DDS file and let PIL decode it
            dds = _build_dds(width, height, data_size, dxt_type, pixel_data)
            img = Image.open(_io.BytesIO(dds))
            return img.convert('RGBA')
        except Exception:
            pass
        # Last resort: use our own software DXT decoder
        try:
            pixels = _dxt_decode(pixel_data, width, height, encoding == 4)
            img = Image.frombytes('RGBA', (width, height), bytes(pixels))
            return img
        except Exception:
            return None
    else:
        # Uncompressed
        if encoding == 1:  # Greyscale
            n = width * height
            rgba = bytearray(n * 4)
            for i in range(n):
                v = pixel_data[i]
                rgba[i*4:i*4+4] = bytes([v, v, v, 255])
            return Image.frombytes('RGBA', (width, height), bytes(rgba))
        elif encoding == 2:  # RGB
            n = width * height
            if len(pixel_data) < n * 3:
                return None
            rgba = bytearray(n * 4)
            for i in range(n):
                rgba[i*4]   = pixel_data[i*3]
                rgba[i*4+1] = pixel_data[i*3+1]
                rgba[i*4+2] = pixel_data[i*3+2]
                rgba[i*4+3] = 255
            return Image.frombytes('RGBA', (width, height), bytes(rgba))
        elif encoding in (4, 12):  # RGBA
            n = width * height
            if len(pixel_data) < n * 4:
                return None
            return Image.frombytes('RGBA', (width, height), pixel_data[:n*4])
        return None


def _build_dds(width: int, height: int, data_size: int,
               dxt_type: str, pixel_data: bytes) -> bytes:
    """Build a minimal DDS file header + data for PIL to decode."""
    fourcc = b'DXT1' if dxt_type == 'DXT1' else b'DXT5'
    # DDS header (128 bytes)
    header = bytearray(128)
    header[0:4]   = b'DDS '
    struct.pack_into('<I', header, 4,  124)    # header size
    struct.pack_into('<I', header, 8,  0x1007) # DDSD_CAPS|DDSD_HEIGHT|DDSD_WIDTH|DDSD_PIXELFORMAT
    struct.pack_into('<I', header, 12, height)
    struct.pack_into('<I', header, 16, width)
    struct.pack_into('<I', header, 20, data_size)  # pitch or linear size
    struct.pack_into('<I', header, 76, 32)     # pixel format size
    struct.pack_into('<I', header, 80, 4)      # DDPF_FOURCC
    header[84:88] = fourcc
    struct.pack_into('<I', header, 108, 0x1000) # DDSCAPS_TEXTURE
    return bytes(header) + pixel_data[:data_size]


def _dxt_decode(data: bytes, width: int, height: int, has_alpha: bool) -> bytearray:
    """
    Pure Python DXT1/DXT5 decoder.
    Ported from KotorBlender's tpc/reader.py decompress_dxt15_block.
    Returns flat RGBA bytearray of width*height*4 bytes.
    """
    out = bytearray(width * height * 4)
    block_size = 16 if has_alpha else 8
    num_bx = (width + 3) // 4
    num_by = (height + 3) // 4
    data_idx = 0

    for by in range(num_by):
        for bx in range(num_bx):
            blk = data[data_idx: data_idx + block_size]
            data_idx += block_size

            if has_alpha:
                # DXT5: 8 bytes alpha + 8 bytes color
                a0, a1 = blk[0], blk[1]
                ac = struct.unpack_from('<Q', blk, 2)[0]
                c0, c1 = struct.unpack_from('<HH', blk, 8)
                cc = struct.unpack_from('<I', blk, 12)[0]
            else:
                # DXT1: 8 bytes color only
                a0 = a1 = 255
                ac = 0
                c0, c1 = struct.unpack_from('<HH', blk, 0)
                cc = struct.unpack_from('<I', blk, 4)[0]

            # Expand 565 colors
            r0 = ((c0 >> 11) * 255 + 16) // 32
            g0 = (((c0 >> 5) & 63) * 255 + 32) // 64
            b0 = ((c0 & 31) * 255 + 16) // 32
            r1 = ((c1 >> 11) * 255 + 16) // 32
            g1 = (((c1 >> 5) & 63) * 255 + 32) // 64
            b1 = ((c1 & 31) * 255 + 16) // 32

            for py in range(4):
                for px in range(4):
                    pixel_x = bx * 4 + px
                    pixel_y = by * 4 + py
                    if pixel_x >= width or pixel_y >= height:
                        continue

                    # Color
                    ci = (cc >> (2 * (py * 4 + px))) & 3
                    if has_alpha or c0 > c1:
                        if   ci == 0: r, g, b = r0, g0, b0
                        elif ci == 1: r, g, b = r1, g1, b1
                        elif ci == 2: r, g, b = (2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3
                        else:         r, g, b = (r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3
                    else:
                        if   ci == 0: r, g, b = r0, g0, b0
                        elif ci == 1: r, g, b = r1, g1, b1
                        elif ci == 2: r, g, b = (r0+r1)//2, (g0+g1)//2, (b0+b1)//2
                        else:         r, g, b = 0, 0, 0

                    # Alpha
                    if has_alpha:
                        ai = (ac >> (3 * (py * 4 + px))) & 7
                        if   ai == 0: a = a0
                        elif ai == 1: a = a1
                        elif a0 > a1:
                            a = ((8 - ai) * a0 + (ai - 1) * a1) // 7
                        elif ai == 6: a = 0
                        elif ai == 7: a = 255
                        else:
                            a = ((6 - ai) * a0 + (ai - 1) * a1) // 5
                    else:
                        a = 255

                    off = (pixel_y * width + pixel_x) * 4
                    out[off]   = r
                    out[off+1] = g
                    out[off+2] = b
                    out[off+3] = a

    return out


# ── Module-level singleton ───────────────────────────────────────────────────

# Global singleton — created once, shared by all components
_manager: Optional[ResourceManager] = None
_manager_lock = threading.Lock()


def get_manager() -> ResourceManager:
    """Get (or create) the global ResourceManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ResourceManager()
    return _manager


def reset_manager() -> ResourceManager:
    """Reset the global singleton (useful for testing)."""
    global _manager
    with _manager_lock:
        _manager = ResourceManager()
    return _manager
