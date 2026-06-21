"""
KotOR Game Resource Browser
Reads KEY/BIF/ERF/RIM/MOD archives to extract MDL, MDX, TPC, TGA, 2DA files.
Works directly on any KotOR 1 or KotOR 2 installation folder.

CONFIRMED resource type IDs from chitin.key analysis:
  - models.bif:   0x07D2 (MDL model files), 0x0BC0 (MDX vertex data)
  - textures.bif: 0x0003 (TGA textures)
  - items.bif:    0x07D2 (TPC textures – same type as MDL, differentiated by BIF name)
  - 2da.bif:      0x07E1 (2DA tables)
  - scripts.bif:  0x07D9 (UTC), 0x07DA (UTI)
  - templates.bif: 0x07E9 (FAC), 0x07EB (WOK), 0x07ED (TLK), 0x07EE (JRL), etc.

NOTE: MDL and TPC share type ID 0x07D2. Disambiguation is done via source BIF name.
The _resources dict uses (resref_lower, res_type) tuple keys.
"""

import struct, os, logging, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Resource Type IDs (CONFIRMED from KotOR 1 chitin.key analysis) ───────────
# Type 0x07D2 is used for BOTH MDL models AND TPC textures in different BIFs.
RES_TGA   = 0x0003   # 3    - TGA/lightmap texture
RES_WAV   = 0x0004   # 4    - WAV audio
RES_MDL   = 0x07D2   # 2002 - Binary MDL model (CONFIRMED: models.bif)
RES_TPC   = 0x07D2   # 2002 - TPC texture (SAME type as MDL; items/party/player BIFs)
RES_UTC   = 0x07D9   # 2009 - Creature template (GFF)
RES_UTI   = 0x07DA   # 2010 - Item template (GFF)
RES_UTS   = 0x07DC   # 2012 - Sound template (GFF)
RES_UTE   = 0x07DD   # 2013 - Encounter template (GFF)
RES_UTD   = 0x07DE   # 2014 - Door template (GFF)
RES_UTP   = 0x07DF   # 2015 - Placeable template (GFF)
RES_DLG   = 0x07E0   # 2016 - Dialog (GFF)
RES_2DA   = 0x07E1   # 2017 - 2DA table (CONFIRMED: 2da.bif)
RES_UTM   = 0x07E5   # 2021 - Merchant store (GFF)
RES_IFO   = 0x07E6   # 2022 - Module info (GFF) / lightmap area IFO
RES_ARE   = 0x07E7   # 2023 - Area (GFF)
RES_FAC   = 0x07E9   # 2025 - Faction (GFF)
RES_BIC   = 0x07EA   # 2026 - Character/save (GFF)
RES_WOK   = 0x07EB   # 2027 - Walkmesh
RES_TLK   = 0x07ED   # 2029 - Talk table
RES_JRL   = 0x07EE   # 2030 - Journal (GFF)
RES_UTR   = 0x07F0   # 2032 - Random encounter (GFF)
RES_NCS   = 0x07F8   # 2040 - Compiled NWScript
RES_NDB   = 0x07FA   # 2042 - Script debug
RES_PTT   = 0x07FC   # 2044 - Plot template (GFF)
RES_SSF   = 0x07FF   # 2047 - Sound set
RES_ERF   = 0x0BB8   # 3000 - ERF/module archive
RES_RIM   = 0x0BB9   # 3001 - RIM module
RES_MDX   = 0x0BC0   # 3008 - MDX vertex data (CONFIRMED: models.bif)
RES_MDX_K  = 0x0805  # 2053 - MDX alternate (seen in models.bif)
RES_ANIM   = 0x0804  # 2052 - Animation (seen in models.bif)
RES_TPC_ERF = 0x0BBF # 3007 - TPC texture stored in ERF/texture-pack archives

# Legacy aliases kept for backward compatibility
RES_TXI = 1448
RES_LYT = 3000
RES_VIS = 3001

# Extension map – used for display only; resource lookup uses (resref, type) tuples
RES_EXT_MAP = {
    RES_TGA:  '.tga',    # 0x0003
    RES_WAV:  '.wav',    # 0x0004
    # Note: 0x07D2 is both MDL and TPC – we distinguish by context
    0x07D2:   '.mdl',    # default for 0x07D2 (overridden for TPC by source BIF)
    RES_MDX:  '.mdx',    # 0x0BC0
    RES_2DA:  '.2da',    # 0x07E1
    RES_UTC:  '.utc',    # 0x07D9
    RES_UTI:  '.uti',    # 0x07DA
    RES_UTS:  '.uts',    # 0x07DC
    RES_UTE:  '.ute',    # 0x07DD
    RES_UTD:  '.utd',    # 0x07DE
    RES_UTP:  '.utp',    # 0x07DF
    RES_DLG:  '.dlg',    # 0x07E0
    RES_UTM:  '.utm',    # 0x07E5
    RES_IFO:  '.ifo',    # 0x07E6
    RES_ARE:  '.are',    # 0x07E7
    RES_FAC:  '.fac',    # 0x07E9
    RES_BIC:  '.bic',    # 0x07EA
    RES_WOK:  '.wok',    # 0x07EB
    RES_TLK:  '.tlk',    # 0x07ED
    RES_JRL:  '.jrl',    # 0x07EE
    RES_UTR:  '.utr',    # 0x07F0
    RES_NCS:  '.ncs',    # 0x07F8
    RES_NDB:  '.ndb',    # 0x07FA
    RES_PTT:  '.ptt',    # 0x07FC
    RES_SSF:  '.ssf',    # 0x07FF
    RES_ERF:  '.erf',    # 0x0BB8
    RES_RIM:  '.rim',    # 0x0BB9
    RES_MDX:  '.mdx',    # 0x0BC0
    RES_ANIM: '.anim',   # 0x0804
    RES_MDX_K:'.mdx2',   # 0x0805
    RES_TXI:  '.txi',    # 1448
}

# Human-readable type names for UI display
RES_TYPE_NAMES = {
    RES_TGA:  'TGA Texture',
    0x07D2:   'MDL / TPC',
    RES_MDX:  'MDX Vertex Data',
    RES_2DA:  '2DA Table',
    RES_UTC:  'Creature (UTC)',
    RES_UTI:  'Item (UTI)',
    RES_UTS:  'Sound (UTS)',
    RES_UTD:  'Door (UTD)',
    RES_UTP:  'Placeable (UTP)',
    RES_DLG:  'Dialog (DLG)',
    RES_UTM:  'Merchant (UTM)',
    RES_IFO:  'Module Info (IFO)',
    RES_ARE:  'Area (ARE)',
    RES_FAC:  'Faction (FAC)',
    RES_WOK:  'Walkmesh (WOK)',
    RES_TLK:  'Talk Table (TLK)',
    RES_JRL:  'Journal (JRL)',
    RES_NCS:  'Script (NCS)',
    RES_SSF:  'Sound Set (SSF)',
    RES_WAV:  'Audio (WAV)',
}


def res_ext(res_type: int) -> str:
    """Get file extension for a resource type."""
    return RES_EXT_MAP.get(res_type, f'.0x{res_type:04x}')


def res_name(res_type: int) -> str:
    """Get human-readable name for a resource type."""
    return RES_TYPE_NAMES.get(res_type, f'0x{res_type:04X}')


@dataclass
class ResourceEntry:
    resref:   str   = ""
    res_type: int   = 0
    size:     int   = 0
    # source
    source_file: str = ""   # absolute path to BIF/ERF/RIM
    offset:      int = 0    # byte offset within source_file
    bif_name:    str = ""   # original BIF name (for MDL/TPC disambiguation)
    # or inline data
    data:        Optional[bytes] = None

    @property
    def is_model(self) -> bool:
        """True if this is an MDL binary model file."""
        if self.res_type != 0x07D2:
            return False
        # MDL models come from models.bif, party.bif, or player.bif
        bn = self.bif_name.lower()
        return ('models' in bn or 'party' in bn or 'player' in bn
                or bn == '' or not bn)

    @property
    def is_texture(self) -> bool:
        """True if this is a TPC/TGA texture."""
        if self.res_type == RES_TGA:
            return True
        # RES_TPC_ERF (0x0BBF) = TPC in ERF/TexturePack archive
        if self.res_type == 0x0BBF:
            return True
        if self.res_type == 0x07D2:
            # TPC textures come from items.bif, textures.bif, swpc_tex* etc.
            # Also allow any BIF that doesn't look like a model BIF.
            bn = self.bif_name.lower()
            if ('models' in bn or 'party' in bn or 'player' in bn):
                return False   # these are MDL model BIFs, not textures
            # Everything else with type 0x07D2 that is NOT a model BIF is a texture
            return True
        return False

    @property
    def ext(self) -> str:
        """File extension based on type and source."""
        if self.res_type == 0x07D2:
            return '.mdl' if self.is_model else '.tpc'
        return RES_EXT_MAP.get(self.res_type, f'.0x{self.res_type:04x}')

    @property
    def filename(self) -> str:
        return f"{self.resref}{self.ext}"

    def read(self) -> bytes:
        if self.data is not None:
            return self.data
        with open(self.source_file, 'rb') as f:
            f.seek(self.offset)
            return f.read(self.size)


# ── KEY/BIF reader ─────────────────────────────────────────────────────────

class KEYBIFReader:
    """
    Reads KEY + BIF archives (main KotOR data files).
    KEY file lists all resources; BIF files hold the actual data.

    Resource lookup uses (resref_lower, res_type) tuples as keys to properly
    handle the case where MDL (0x07D2) and TPC (0x07D2) share the same type ID.
    """

    def __init__(self, game_dir: str):
        self.game_dir = Path(game_dir)
        # Primary index: (resref_lower, res_type) → ResourceEntry
        self._resources: Dict[Tuple[str, int], ResourceEntry] = {}
        # Secondary index for fast type queries
        self._by_type: Dict[int, List[ResourceEntry]] = {}
        # For MDL/TPC disambiguation: track source BIF
        self._mdl072_by_resref: Dict[str, List[ResourceEntry]] = {}

    def load(self):
        """Scan game_dir for chitin.key and load all BIF entries."""
        key_path = self.game_dir / 'chitin.key'
        if not key_path.exists():
            for p in [self.game_dir/'data'/'chitin.key',
                      self.game_dir/'override'/'chitin.key']:
                if p.exists():
                    key_path = p
                    break
        if not key_path.exists():
            log.warning(f"chitin.key not found in {self.game_dir}")
            return

        with open(str(key_path), 'rb') as f:
            data = f.read()

        sig = data[:4]
        if sig not in (b'KEY ', b'KEY\x20'):
            log.error("Not a valid KEY file")
            return

        bif_count   = struct.unpack_from('<I', data, 8)[0]
        key_count   = struct.unpack_from('<I', data, 12)[0]
        bif_off     = struct.unpack_from('<I', data, 16)[0]
        key_off     = struct.unpack_from('<I', data, 20)[0]

        # ── Case-insensitive path resolver for Linux ──────────────────────
        # KotOR KEY files on disk (especially K2/TSL) often store BIF paths in
        # lowercase (e.g. "data\models.bif") but the actual file on a case-sensitive
        # Linux filesystem may have a different case (e.g. "data/Models.bif").
        # We build a case-insensitive directory cache to resolve this transparently.
        _dir_cache: Dict[str, Dict[str, str]] = {}   # dir_lower → {filename_lower: real_path}

        def _resolve_path_ci(base_dir: Path, rel_path: str) -> str:
            """
            Resolve a relative path case-insensitively on Linux.
            Returns the real absolute path if found, otherwise the uncorrected path.
            """
            parts = rel_path.replace('\\', '/').split('/')
            current = base_dir
            for part in parts:
                part_lower = part.lower()
                cur_str = str(current)
                if cur_str not in _dir_cache:
                    try:
                        _dir_cache[cur_str] = {
                            e.name.lower(): str(e)
                            for e in current.iterdir()
                            if current.is_dir()
                        }
                    except Exception:
                        _dir_cache[cur_str] = {}
                real_entry = _dir_cache.get(cur_str, {}).get(part_lower)
                if real_entry:
                    current = Path(real_entry)
                else:
                    # Not found – return best-effort uncorrected path
                    current = current / part
            return str(current)

        # Read BIF file entries
        bif_paths: List[str] = []
        bif_names: List[str] = []   # short BIF names for disambiguation
        o = bif_off
        for i in range(bif_count):
            file_size = struct.unpack_from('<I', data, o)[0]; o += 4
            fname_off = struct.unpack_from('<I', data, o)[0]; o += 4
            fname_len = struct.unpack_from('<H', data, o)[0]; o += 2
            drives    = struct.unpack_from('<H', data, o)[0]; o += 2
            bif_name  = data[fname_off:fname_off+fname_len].rstrip(b'\x00').decode('ascii', 'replace')
            bif_short = Path(bif_name).stem.lower()  # e.g. "models", "textures", "items"
            # Use case-insensitive resolver for Linux compatibility
            full_path = _resolve_path_ci(self.game_dir, bif_name)
            bif_paths.append(full_path)
            bif_names.append(bif_short)

        # Parse BIF var-table caches to avoid re-opening files repeatedly
        bif_tables: Dict[str, List[Tuple[int, int]]] = {}  # bif_path → [(offset, size), ...]

        def get_bif_entry(bif_path: str, slot: int) -> Tuple[int, int]:
            """Get (offset, size) for a slot in a BIF file."""
            if bif_path not in bif_tables:
                bif_tables[bif_path] = []
                try:
                    with open(bif_path, 'rb') as f:
                        hdr = f.read(20)
                    if len(hdr) < 20:
                        return 0, 0
                    var_count = struct.unpack_from('<I', hdr, 8)[0]
                    var_off   = struct.unpack_from('<I', hdr, 16)[0]
                    with open(bif_path, 'rb') as f:
                        f.seek(var_off)
                        raw = f.read(var_count * 16)
                    entries = []
                    for j in range(var_count):
                        if j * 16 + 16 > len(raw):
                            break
                        off_j  = struct.unpack_from('<I', raw, j*16 + 4)[0]
                        size_j = struct.unpack_from('<I', raw, j*16 + 8)[0]
                        entries.append((off_j, size_j))
                    bif_tables[bif_path] = entries
                except Exception as ex:
                    log.debug(f"BIF read error {bif_path}: {ex}")
                    return 0, 0
            entries = bif_tables.get(bif_path, [])
            if slot < len(entries):
                return entries[slot]
            return 0, 0

        # Read resource key entries
        o = key_off
        for i in range(key_count):
            resref   = data[o:o+16].rstrip(b'\x00').decode('ascii', 'replace'); o += 16
            res_type = struct.unpack_from('<H', data, o)[0]; o += 2
            res_id   = struct.unpack_from('<I', data, o)[0]; o += 4
            bif_idx  = (res_id >> 20) & 0xFFF
            bif_slot = res_id & 0xFFFFF

            if bif_idx >= len(bif_paths):
                continue

            bif_path  = bif_paths[bif_idx]
            bif_short = bif_names[bif_idx]
            resref_l  = resref.lower()

            offset, size = 0, 0
            if os.path.exists(bif_path):
                try:
                    offset, size = get_bif_entry(bif_path, bif_slot)
                except Exception as ex:
                    log.debug(f"BIF entry error {bif_path}:{bif_slot}: {ex}")

            entry = ResourceEntry(
                resref=resref_l,
                res_type=res_type,
                size=size,
                source_file=bif_path,
                offset=offset,
                bif_name=bif_short,
            )

            # Store in primary index: use (resref, type) but for 0x07D2 we need
            # to distinguish MDL vs TPC. Use bif_short as part of secondary key.
            primary_key = (resref_l, res_type)

            # For type 0x07D2, we track all entries separately
            if res_type == 0x07D2:
                if resref_l not in self._mdl072_by_resref:
                    self._mdl072_by_resref[resref_l] = []
                self._mdl072_by_resref[resref_l].append(entry)
                # In primary dict, use a disambiguation key
                primary_key = (resref_l, res_type, bif_short)
            else:
                self._resources[primary_key] = entry

            # By-type index
            if res_type not in self._by_type:
                self._by_type[res_type] = []
            self._by_type[res_type].append(entry)

        # For 0x07D2 entries, determine if they're MDL or TPC based on BIF source
        # and store in _resources with appropriate ext-based keys too
        for resref_l, entries_072 in self._mdl072_by_resref.items():
            for e in entries_072:
                bn = e.bif_name
                if ('models' in bn or 'party' in bn or 'player' in bn):
                    # This is an MDL
                    self._resources[(resref_l, 0x07D2, 'mdl')] = e
                else:
                    # This is a TPC
                    self._resources[(resref_l, 0x07D2, 'tpc')] = e

        total = len(self._by_type.get(0x07D2, [])) + sum(
            len(v) for k, v in self._by_type.items() if k != 0x07D2)
        log.info(f"KEY loaded: {len(self._by_type)} types, "
                 f"{sum(len(v) for v in self._by_type.values())} resources total")

    def get(self, resref: str, res_type: int) -> Optional[ResourceEntry]:
        """Get a resource entry by name and type."""
        resref_l = resref.lower()

        if res_type == RES_MDL:
            # For MDL (0x07D2), look for model entry first
            e = self._resources.get((resref_l, 0x07D2, 'mdl'))
            if e:
                return e
            # Fall back: check all 0x07D2 entries for this resref
            for e2 in self._mdl072_by_resref.get(resref_l, []):
                if e2.is_model:
                    return e2
            return None

        if res_type == RES_TPC:
            # For TPC (0x07D2), look for texture entry
            e = self._resources.get((resref_l, 0x07D2, 'tpc'))
            if e:
                return e
            # Fall back
            for e2 in self._mdl072_by_resref.get(resref_l, []):
                if e2.is_texture:
                    return e2
            return None

        return self._resources.get((resref_l, res_type))

    def list_type(self, res_type: int) -> List[ResourceEntry]:
        """List all entries of a given type."""
        if res_type == RES_MDL:
            # Return only MDL model entries (not TPC textures)
            result = []
            for entries in self._mdl072_by_resref.values():
                for e in entries:
                    if e.is_model:
                        result.append(e)
            return result

        if res_type == RES_TPC:
            # Return only TPC texture entries
            result = []
            for entries in self._mdl072_by_resref.values():
                for e in entries:
                    if e.is_texture:
                        result.append(e)
            return result

        return list(self._by_type.get(res_type, []))

    def list_all_types(self) -> Dict[int, int]:
        """Return dict of {res_type: count}."""
        return {t: len(v) for t, v in self._by_type.items()}

    def list_all_resources(self) -> List[ResourceEntry]:
        """Return all resource entries."""
        return [e for entries in self._by_type.values() for e in entries]


# ── ERF/RIM/MOD reader ──────────────────────────────────────────────────────

class ERFReader:
    """
    Reads ERF / RIM / MOD archives.
    ERF V1.0 format – used for modules, texture packs, etc.
    """

    def __init__(self, erf_path: str):
        self.path = erf_path
        self._resources: Dict[Tuple[str, int], ResourceEntry] = {}
        self._by_type: Dict[int, List[ResourceEntry]] = {}

    def load(self):
        try:
            # Read only the header (160 bytes) to get key/resource list offsets,
            # then read only the key+resource tables (NOT the full file data).
            # This avoids reading the entire ERF file (e.g. 382 MB for TPA),
            # reducing scan time from ~3.5 s to <100 ms.
            with open(self.path, 'rb') as f:
                hdr = f.read(160)
            if len(hdr) < 32:
                return
            sig = hdr[:4].decode('ascii', 'replace').rstrip()
            ver = hdr[4:8].decode('ascii', 'replace').rstrip()
        except Exception as ex:
            log.warning(f"ERF open error {self.path}: {ex}")
            return

        if sig not in ('ERF', 'MOD', 'RIM', 'SAV'):
            log.debug(f"Not a valid ERF/RIM: {self.path}")
            return

        if ver.startswith('V1'):
            try:
                entry_count = struct.unpack_from('<I', hdr, 16)[0]
                keylist_off = struct.unpack_from('<I', hdr, 24)[0]
                reslist_off = struct.unpack_from('<I', hdr, 28)[0]

                with open(self.path, 'rb') as f:
                    f.seek(keylist_off)
                    key_data = f.read(entry_count * 24)
                    f.seek(reslist_off)
                    res_data = f.read(entry_count * 8)

                self._load_v1_from_tables(key_data, res_data, entry_count)
            except Exception as ex:
                log.warning(f"ERF index-read error {self.path}: {ex}")
        else:
            log.warning(f"Unsupported ERF version {ver!r}")

    def _load_v1_from_tables(self, key_data: bytes, res_data: bytes, entry_count: int):
        erf_name = Path(self.path).stem.lower()

        for i in range(entry_count):
            ko = i * 24
            ro = i * 8
            if ko + 22 > len(key_data) or ro + 8 > len(res_data):
                break
            resref   = key_data[ko:ko+16].rstrip(b'\x00').decode('ascii', 'replace').lower()
            res_type = struct.unpack_from('<H', key_data, ko+20)[0]
            offset   = struct.unpack_from('<I', res_data, ro)[0]
            size     = struct.unpack_from('<I', res_data, ro+4)[0]

            entry = ResourceEntry(
                resref=resref, res_type=res_type,
                source_file=self.path, offset=offset, size=size,
                bif_name=erf_name,
            )
            key = (resref, res_type)
            self._resources[key] = entry
            if res_type not in self._by_type:
                self._by_type[res_type] = []
            self._by_type[res_type].append(entry)

    def _load_v1(self, data: bytes):
        """Legacy full-data parser (kept for backward compat only)."""
        entry_count = struct.unpack_from('<I', data, 16)[0]
        keylist_off = struct.unpack_from('<I', data, 24)[0]
        reslist_off = struct.unpack_from('<I', data, 28)[0]

        key_data = data[keylist_off:keylist_off + entry_count * 24]
        res_data = data[reslist_off:reslist_off + entry_count * 8]
        self._load_v1_from_tables(key_data, res_data, entry_count)

    def get(self, resref: str, res_type: int) -> Optional[ResourceEntry]:
        return self._resources.get((resref.lower(), res_type))

    def list_type(self, res_type: int) -> List[ResourceEntry]:
        return list(self._by_type.get(res_type, []))

    def list_all(self) -> List[ResourceEntry]:
        return list(self._resources.values())


# ── High-level Game Library ──────────────────────────────────────────────────

@dataclass
class ModelLibraryEntry:
    resref:      str
    game:        str          # "K1" or "K2"
    source:      str          # archive path
    res_type:    int   = RES_MDL
    has_mdx:     bool  = False
    has_texture: bool  = False
    # Extended metadata (populated by deep scan)
    node_count:  int   = 0
    mesh_count:  int   = 0
    tex_count:   int   = 0
    has_skin:    bool  = False
    model_class: str   = ""   # character/tile/door/effect
    description: str   = ""   # human-readable summary

    @property
    def display_label(self) -> str:
        parts = [self.resref]
        if self.mesh_count:  parts.append(f"{self.mesh_count}m")
        if self.has_skin:    parts.append("skin")
        if self.model_class: parts.append(self.model_class[:4])
        return '  '.join(parts)

    @property
    def display_label_rich(self) -> str:
        """Extended label that includes area name for module models.

        Supports K1 warp-code style (end_m01aa, tar_m02aa, danm13, etc.),
        K1 m## style (m12aa_01a), and K2 numeric style (101per_01a).
        """
        r = self.resref.lower()
        # K2 module: 3-digit numeric area code prefix
        if len(r) >= 5 and r[:3].isdigit() and r[3:5].isalpha():
            area_key = r[:3]
            _K2_SHORT = {
                '001':'Ebon Hawk','002':'Ebon Hawk','003':'Ebon Hawk',
                '004':'Ebon Hawk','005':'Ebon Hawk',
                '101':'Peragus','102':'Peragus','103':'Peragus','104':'Peragus',
                '105':'Peragus','106':'Peragus','107':'Peragus',
                '151':'Harbinger','152':'Harbinger','153':'Harbinger','154':'Harbinger',
                '201':'Telos CS','202':'Telos CS','203':'Telos CS','204':'Telos CS',
                '205':'Telos CS','207':'Telos CS','208':'Telos MB','209':'Telos CZ',
                '211':'Telos Swoop','220':'Telos Suburban','221':'Telos Suburban',
                '222':'Telos Entmt','231':'Telos RZ','232':'Telos UG',
                '233':'Telos Czerka','235':'Telos Shuttle',
                '261':'Polar Plateau','262':'Atris Academy',
                '298':'HK Factory','299':'HK Plant',
                '301':'Nar Shadd','302':'Nar Shadd','303':'Nar Shadd',
                '304':'Jekk Jekk Tarr','305':'Nar Shadd Tunnels','306':'Nar Shadd',
                '307':'Nar Shadd','350':'Nar Shadd',
                '351':'Goto Yacht','352':'Goto Cutscene','371':'Nar Swoop',
                '401':'Dxun Landing','402':'Dxun Jungle','403':'Dxun Ruins',
                '404':'Dxun Cache','410':'Dxun Tomb','411':'Sith Tomb','421':'Dxun Turret',
                '501':'Onderon Port','502':'Onderon Merchant','503':'Onderon Cantina',
                '504':'Sky Ramp','505':'Onderon Turret','506':'Royal Palace',
                '510':'Onderon Swoop','511':'Onderon Invasion','512':'Onderon West',
                '601':'Dantooine Plains','602':'Khoonda','603':'Dantooine Cuts',
                '604':'Crystal Cave','605':'Enclave Courtyard','610':'Enclave Sublevel',
                '650':'Jedi Enclave',
                '701':'Valley Dark Lords','702':'Sith Academy',
                '710':'Shyrack Cave','711':'Secret Tomb',
                '851':'Ravager','852':'Ravager Bridge','853':'Ravager Cuts',
                '901':'Malachor Surf','902':'Malachor Depths',
                '903':'Trayus Academy','904':'Trayus Core',
                '905':'Trayus Crescent','906':'Trayus Proving','907':'Kreia Cuts',
                '950':'Coruscant Cuts','952':'Coruscant JT','953':'Coruscant JTC',
                '954':'Coruscant Landing',
            }
            area_name = _K2_SHORT.get(area_key, f'K2-{area_key}')
            return f"{self.resref}  [{area_name}]"
        # K1 warp-code style: location_mNN (end_m01aa, tar_m02aa, danm13, etc.)
        _K1_WARP_PREFIXES = {
            'end_': 'Endar Spire', 'tar_': 'Taris', 'danm': 'Dantooine',
            'tat_': 'Tatooine', 'kas_': 'Kashyyyk', 'manm': 'Manaan',
            'korr_': 'Korriban', 'lev_': 'Leviathan', 'unk_': 'Unknown World',
            'sta_': 'Star Forge', 'ebo_': 'Ebon Hawk', 'liv_': 'Yavin Station',
            'stunt_': 'Stunt/Cutscene',
        }
        for pfx, loc_name in _K1_WARP_PREFIXES.items():
            if r.startswith(pfx):
                return f"{self.resref}  [{loc_name}]"
        # K1 module: m + 2-digit area code
        if r.startswith('m') and len(r) >= 3 and r[1:3].isdigit():
            area_key = r[1:3]
            # FIX-K1-AREA-LABEL: Corrected KotOR I m## area code mappings.
            # m01 = Endar Spire (end_m01aa Command Module, end_m01ab Starboard)
            # m02 = Taris Upper City (tar_m02aa–af), NOT Endar Spire.
            #   Previously both '01' and '02' were labeled 'Endar Spire' — wrong.
            #   The Endar Spire has only 2 modules (m01aa/m01ab) which both use
            #   the 'm01' prefix.  m02aa through m02af are all Taris Upper City.
            # Source: DeadlyStream KotOR I Warp Code List + community module maps.
            _K1_SHORT = {
                '01':'Endar Spire','02':'Taris Upper City','03':'Taris Lower City',
                '04':'Taris Undercity','05':'Taris Sewers','08':'Davik Estate',
                '09':'Sith Base','10':'Vulkar Base','11':'Hidden Bek',
                '12':'Ebon Hawk','13':'Jedi Enclave','14':'Dantooine',
                '15':'Dantooine Ruins','16':'Sandral Estate','17':'Anchorhead',
                '18':'Dune Sea','19':'Tatooine Temple','20':'Sand People Enclave',
                '22':'Czerka Port','23':'Rwookrrorro','24':'Upper Shadowlands',
                '25':'Lower Shadowlands','26':'Ahto City','27':'Manaan Sith Base',
                '28':'Hrakert Station','33':'Dreshdae','34':'Shyrack Caves',
                '35':'Sith Academy','36':'Valley Dark Lords',
                '37':'Tomb Ajunta Pall','38':'Tombs Marka/Tulak','39':'Tomb Naga Sadow',
                '40':'Leviathan','41':'Unknown World','42':'Unknown World',
                '43':'Rakatan Temple','44':'Star Forge','45':'Yavin Station',
                '47':'Cutscene/Stunt',
            }
            area_name = _K1_SHORT.get(area_key, f'K1-m{area_key}')
            return f"{self.resref}  [{area_name}]"
        return self.display_label


class GameLibrary:
    """
    High-level interface: scans a KotOR installation and provides
    a browseable list of all models, textures, and 2DA tables.

    Features:
      - Correct MDL type ID (0x07D2) – confirmed from chitin.key analysis
      - Full 2DA library support via TwoDACache
      - Complete resource type coverage (UTC, UTI, DLG, ARE, FAC, WOK, etc.)
      - Deep-scan MDL headers for metadata (node counts, classification)
      - Deduplication: later override entries win over BIF entries
      - TLK dialog string lookup
    """

    def __init__(self):
        self.k1_dir:   str = ""
        self.k2_dir:   str = ""
        self._k1_key:  Optional[KEYBIFReader] = None
        self._k2_key:  Optional[KEYBIFReader] = None
        self._k1_erfs: List[ERFReader] = []
        self._k2_erfs: List[ERFReader] = []
        self.models:   List[ModelLibraryEntry] = []
        self.textures: List[str] = []
        self._model_index: Dict[str, ModelLibraryEntry] = {}  # resref.lower() → entry
        # 2DA cache (loaded on demand)
        self._2da_cache: Dict[str, object] = {}    # name_lower → 2DA
        # TLK readers
        self._k1_tlk: Optional[object] = None
        self._k2_tlk: Optional[object] = None

    def set_k1_dir(self, d: str):
        self.k1_dir = d
        self._k1_key = None
        self._k1_erfs = []
        self._k1_tlk = None
        self._2da_cache.clear()

    def set_k2_dir(self, d: str):
        self.k2_dir = d
        self._k2_key = None
        self._k2_erfs = []
        self._k2_tlk = None
        self._2da_cache.clear()

    def scan(self, game_dir: str = None, k2_dir: str = None,
             progress_cb=None, deep_scan: bool = False,
             auto_detect: bool = True):
        """
        Scan game directories.

        Parameters
        ----------
        game_dir : str, optional
            Convenience shortcut: if given, sets k1_dir to this directory
            before scanning.  Equivalent to calling set_k1_dir(game_dir)
            followed by scan().
        k2_dir : str, optional
            Convenience shortcut: if given, also sets k2_dir before scanning.
        deep_scan : bool
            If True, read each MDL header for node-count / classification
            metadata (slower but richer display in the library panel).
        progress_cb : callable, optional
            Called with a status string at regular intervals.
        auto_detect : bool
            If True (default) and no k1_dir / k2_dir are set, attempt to
            auto-detect KotOR installations via game_detector.  Saves found
            paths to ~/.ghostrigger/config.json for future sessions.
        """
        if game_dir is not None:
            # Only override k1_dir if it hasn't been explicitly set already,
            # or if game_dir actually looks like a KotOR installation directory
            # (contains chitin.key or data/models.bif).  This prevents the
            # common test pattern of:
            #   lib.set_k1_dir(k1_dir); lib.set_k2_dir(k2_dir); lib.scan(parent_dir)
            # from accidentally replacing the already-set k1_dir with the parent.
            from pathlib import Path as _Path
            _gd = _Path(game_dir)
            _looks_like_kotor = (
                (_gd / 'chitin.key').exists() or
                (_gd / 'data' / 'models.bif').exists() or
                (_gd / 'data' / 'Models.bif').exists()
            )
            if _looks_like_kotor or not self.k1_dir:
                self.set_k1_dir(game_dir)
        if k2_dir is not None:
            self.set_k2_dir(k2_dir)

        # ── Auto-detect installation paths when none are set ──────────────────
        if auto_detect and not self.k1_dir and not self.k2_dir:
            try:
                from .game_detector import detect_kotor_dirs, save_config
                detected_k1, detected_k2 = detect_kotor_dirs()
                if detected_k1:
                    self.set_k1_dir(detected_k1)
                    log.info(f"Auto-detected KotOR 1: {detected_k1}")
                if detected_k2:
                    self.set_k2_dir(detected_k2)
                    log.info(f"Auto-detected KotOR 2: {detected_k2}")
                if detected_k1 or detected_k2:
                    save_config(detected_k1, detected_k2)
                    if progress_cb:
                        parts = []
                        if detected_k1: parts.append(f"K1: {Path(detected_k1).name}")
                        if detected_k2: parts.append(f"K2: {Path(detected_k2).name}")
                        progress_cb("Auto-detected: " + ", ".join(parts))
            except Exception as _e:
                log.debug(f"Auto-detect failed: {_e}")

        self.models   = []
        self.textures = []
        self._model_index = {}
        self._2da_cache.clear()

        # ── Auto-detect actual game version from MDL fp1 signature ────────────
        # Directories may be mis-labelled (e.g. game_data/kotor1/ physically
        # containing K2 assets, and vice-versa).  Detect and swap upfront so
        # that all subsequent KEY/BIF/ERF attribution uses the correct tag.
        if self.k1_dir and self.k2_dir and os.path.isdir(self.k1_dir) and os.path.isdir(self.k2_dir):
            detected_k1 = self._detect_game_tag(self.k1_dir)
            detected_k2 = self._detect_game_tag(self.k2_dir)
            if detected_k1 == "K2" and detected_k2 == "K1":
                log.warning(
                    "K1/K2 directories appear to be swapped (detected K2 in "
                    f"'{self.k1_dir}' and K1 in '{self.k2_dir}'). "
                    "Swapping internally."
                )
                self.k1_dir, self.k2_dir = self.k2_dir, self.k1_dir
                self._k1_key, self._k2_key = self._k2_key, self._k1_key
                self._k1_erfs, self._k2_erfs = self._k2_erfs, self._k1_erfs
                self._k1_tlk, self._k2_tlk = self._k2_tlk, self._k1_tlk
        elif self.k1_dir and os.path.isdir(self.k1_dir):
            detected = self._detect_game_tag(self.k1_dir)
            if detected == "K2":
                log.warning(
                    f"Directory '{self.k1_dir}' labelled K1 but contains K2 "
                    "models — reassigning to k2_dir."
                )
                self.k2_dir = self.k1_dir
                self.k1_dir = ""
        elif self.k2_dir and os.path.isdir(self.k2_dir):
            detected = self._detect_game_tag(self.k2_dir)
            if detected == "K1":
                log.warning(
                    f"Directory '{self.k2_dir}' labelled K2 but contains K1 "
                    "models — reassigning to k1_dir."
                )
                self.k1_dir = self.k2_dir
                self.k2_dir = ""

        if self.k1_dir and os.path.isdir(self.k1_dir):
            self._scan_game(self.k1_dir, "K1", progress_cb, deep_scan)
        if self.k2_dir and os.path.isdir(self.k2_dir):
            self._scan_game(self.k2_dir, "K2", progress_cb, deep_scan)

    @staticmethod
    def _detect_game_tag(game_dir: str) -> str:
        """Auto-detect whether a directory contains KotOR 1 or KotOR 2 models.

        Reads the geometry function-pointer 1 (fp1) from the first MDL entry in
        the game's models BIF.  The fp1 value is a compile-time constant unique
        to each game build:
            K1 : 4273776 or 4273392
            K2 : 4285200 or 4284816
        Falls back to "K1" when the BIF cannot be read or fp1 is unrecognised.
        """
        K1_FP1 = {4273776, 4273392}
        K2_FP1 = {4285200, 4284816}
        BASE   = 12   # MDL file header is 12 bytes; geometry section starts at offset 12

        gd = Path(game_dir)
        # Locate the models BIF (case-insensitive)
        bif_path = None
        for candidate in ['data/Models.bif', 'data/models.bif']:
            p = gd / candidate
            if p.exists():
                bif_path = p
                break
        if bif_path is None:
            return "K1"

        try:
            key = KEYBIFReader(str(gd))
            key.load()
            mdl_entries = key.list_type(RES_MDL)
            if not mdl_entries:
                return "K1"
            # Grab the raw bytes of the first MDL and read fp1
            first = mdl_entries[0]
            entry = key.get(first.resref, RES_MDL)
            raw = entry.read() if entry is not None else None
            if raw and len(raw) > BASE + 8:
                fp1 = struct.unpack_from('<I', raw, BASE)[0]
                if fp1 in K2_FP1:
                    return "K2"
                if fp1 in K1_FP1:
                    return "K1"
        except Exception as ex:
            log.debug(f"_detect_game_tag failed for {game_dir}: {ex}")

        return "K1"

    def _scan_game(self, game_dir: str, tag: str, progress_cb, deep_scan: bool):
        log.info(f"Scanning {tag}: {game_dir}")
        gd = Path(game_dir)
        seen: Dict[str, int] = {}   # resref.lower() → index in self.models

        def add_entry(e: ModelLibraryEntry):
            k = e.resref.lower()
            if k in seen:
                self.models[seen[k]] = e
            else:
                seen[k] = len(self.models)
                self.models.append(e)
            self._model_index[k] = e

        # ── KEY/BIF ───────────────────────────────────────────────────
        key = KEYBIFReader(game_dir)
        try:
            key.load()
            if tag == "K1":
                self._k1_key = key
            else:
                self._k2_key = key

            mdl_entries = key.list_type(RES_MDL)
            log.info(f"  {tag}: KEY found {len(mdl_entries)} MDL models")

            for e in mdl_entries:
                has_mdx = key.get(e.resref, RES_MDX) is not None
                entry = ModelLibraryEntry(
                    resref=e.resref, game=tag, source=e.source_file,
                    has_mdx=has_mdx)
                add_entry(entry)

            tpc_entries = key.list_type(RES_TPC)
            tga_entries = key.list_type(RES_TGA)
            log.info(f"  {tag}: KEY found {len(tpc_entries)} TPC + "
                     f"{len(tga_entries)} TGA textures")

            seen_tex = set(self.textures)
            for e in tpc_entries:
                t = e.resref.lower()
                if t not in seen_tex:
                    self.textures.append(t)
                    seen_tex.add(t)
            for e in tga_entries:
                t = e.resref.lower()
                if t not in seen_tex:
                    self.textures.append(t)
                    seen_tex.add(t)

        except Exception as ex:
            log.error(f"KEY scan error: {ex}")
            import traceback; traceback.print_exc()

        # ── ERFs (modules, streamtextures, texturepacks) ──────────────
        seen_tex = set(self.textures)
        for sub in ['modules', 'data', 'streamtextures', 'texturepacks',
                    'TexturePacks', 'lips', 'rims']:
            sub_dir = gd / sub
            if not sub_dir.is_dir():
                continue
            try:
                found_erfs = (list(sub_dir.glob('*.erf')) +
                              list(sub_dir.glob('*.rim')) +
                              list(sub_dir.glob('*.mod')) +
                              list(sub_dir.glob('*.ERF')) +
                              list(sub_dir.glob('*.RIM')))
            except Exception:
                found_erfs = []
            # Sort TexturePack ERFs so quality order is preserved:
            # swpc_tex_gui → swpc_tex_tpc → swpc_tex_tpb → swpc_tex_tpa
            # (ascending = tpa last = highest index = highest priority in
            #  _search_erfs_for's quality-sorted pass).
            def _tp_sort_key(p):
                n = str(p).lower()
                if 'swpc_tex_tpa' in n: return 3   # last = highest priority
                if 'swpc_tex_tpb' in n: return 2
                if 'swpc_tex_tpc' in n: return 1
                if 'swpc_tex_gui' in n: return 0
                return -1  # non-texpack ERFs come first
            found_erfs = sorted(found_erfs, key=_tp_sort_key)
            for erf_file in found_erfs:
                try:
                    er = ERFReader(str(erf_file))
                    er.load()
                    if tag == "K1":
                        self._k1_erfs.append(er)
                    else:
                        self._k2_erfs.append(er)
                    for e in er.list_type(RES_MDL):
                        has_mdx = er.get(e.resref, RES_MDX) is not None
                        entry = ModelLibraryEntry(
                            resref=e.resref, game=tag, source=str(erf_file),
                            has_mdx=has_mdx)
                        add_entry(entry)
                    for rt in [RES_TPC, RES_TPC_ERF, RES_TGA]:
                        for e in er.list_type(rt):
                            t = e.resref.lower()
                            if t not in seen_tex:
                                self.textures.append(t)
                                seen_tex.add(t)
                except Exception:
                    pass

        # ── Override folder (loose files win over everything) ──────────
        override = gd / 'Override'
        if not override.is_dir():
            override = gd / 'override'
        if override.is_dir():
            for f in override.glob('*.mdl'):
                entry = ModelLibraryEntry(
                    resref=f.stem, game=tag, source=str(f),
                    has_mdx=(f.with_suffix('.mdx')).exists())
                add_entry(entry)
            for f in list(override.glob('*.tga')) + list(override.glob('*.tpc')):
                t = f.stem.lower()
                if t not in seen_tex:
                    self.textures.append(t)
                    seen_tex.add(t)

        # ── Loose MDL files in models/ subdirectory ───────────────────
        models_dir = gd / 'models'
        if models_dir.is_dir():
            for f in models_dir.glob('*.mdl'):
                entry = ModelLibraryEntry(
                    resref=f.stem, game=tag, source=str(f),
                    has_mdx=(f.with_suffix('.mdx')).exists())
                add_entry(entry)
            for f in list(models_dir.glob('*.tga')) + list(models_dir.glob('*.tpc')):
                t = f.stem.lower()
                if t not in seen_tex:
                    self.textures.append(t)
                    seen_tex.add(t)

        # ── Loose MDL files directly in game_dir ─────────────────────
        for f in gd.glob('*.mdl'):
            entry = ModelLibraryEntry(
                resref=f.stem, game=tag, source=str(f),
                has_mdx=(f.with_suffix('.mdx')).exists())
            add_entry(entry)

        # ── Deep scan ─────────────────────────────────────────────────
        if deep_scan:
            tag_models = [e for e in self.models if e.game == tag]
            total = len(tag_models)
            for i, entry in enumerate(tag_models):
                if progress_cb and i % 50 == 0:
                    progress_cb(f"Deep scanning {tag}: {i}/{total}")
                try:
                    mdl_data, _ = self.get_model_data(entry)
                    if mdl_data and len(mdl_data) > 100:
                        self._read_mdl_metadata(entry, mdl_data)
                except Exception:
                    pass

        count = sum(1 for m in self.models if m.game == tag)
        log.info(f"  {tag}: TOTAL {count} models, {len(self.textures)} textures")
        if progress_cb:
            progress_cb(f"Scanned {tag}: {count} models")

    def _read_mdl_metadata(self, entry: ModelLibraryEntry, mdl_data: bytes):
        """Read minimal MDL header to fill entry metadata."""
        try:
            if len(mdl_data) < 200:
                return
            model_type = mdl_data[96]
            cls_map = {0: 'effect', 1: 'effects', 2: 'misc', 4: 'character', 8: 'door', 32: 'item', 64: 'character'}
            entry.model_class = cls_map.get(model_type & 0xFF, '')
            skin_marker = b'\x40\x00\x00\x00'
            entry.has_skin = skin_marker in mdl_data[:min(len(mdl_data), 8192)]
        except Exception:
            pass

    # ── 2DA support ────────────────────────────────────────────────────

    def get_2da(self, name: str, game: str = "K1") -> Optional[object]:
        """
        Get a parsed 2DA table by name.
        Cached after first load. Returns a 2DA instance or None.
        """
        from .game_library import KEYBIFReader  # avoid circular

        key_name = f"{game}:{name.lower()}"
        if key_name in self._2da_cache:
            return self._2da_cache[key_name]

        raw = self._get_2da_raw(name, game)
        if raw is None:
            return None

        try:
            from ..core.twoda import TwoDA
            tda = TwoDA.from_bytes(raw, name=name.lower())
            self._2da_cache[key_name] = tda
            return tda
        except Exception as ex:
            log.warning(f"2DA parse error {name!r}: {ex}")
            return None

    def _get_2da_raw(self, name: str, game: str) -> Optional[bytes]:
        """Fetch raw bytes for a 2DA resource."""
        reader = self._k1_key if game == "K1" else self._k2_key
        if reader:
            e = reader.get(name.lower(), RES_2DA)
            if e:
                try:
                    return e.read()
                except Exception as ex:
                    log.debug(f"2DA read error {name}: {ex}")

        # Check Override folder for loose .2da files
        gdir = self.k1_dir if game == "K1" else self.k2_dir
        if gdir:
            for sub in ['Override', 'override']:
                override = Path(gdir) / sub
                for fname in [f"{name}.2da", f"{name.upper()}.2DA",
                              f"{name.lower()}.2da"]:
                    p = override / fname
                    if p.exists():
                        return p.read_bytes()
        return None

    def list_2da_names(self, game: str = "K1") -> List[str]:
        """List all available 2DA resource names."""
        reader = self._k1_key if game == "K1" else self._k2_key
        if reader:
            entries = reader.list_type(RES_2DA)
            return sorted(e.resref.lower() for e in entries)
        return []

    # ── Resource listing helpers ────────────────────────────────────────

    def list_resources(self, res_type: int, game: str = "K1") -> List[ResourceEntry]:
        """List all resources of a given type."""
        reader = self._k1_key if game == "K1" else self._k2_key
        if reader:
            return reader.list_type(res_type)
        return []

    def get_resource_data(self, resref: str, res_type: int,
                          game: str = "K1") -> Optional[bytes]:
        """Generic resource data fetcher."""
        reader = self._k1_key if game == "K1" else self._k2_key
        if reader:
            e = reader.get(resref, res_type)
            if e:
                try:
                    return e.read()
                except Exception:
                    pass

        # Try ERFs
        erfs = self._k1_erfs if game == "K1" else self._k2_erfs
        for er in reversed(erfs):
            e = er.get(resref, res_type)
            if e:
                try:
                    return e.read()
                except Exception:
                    pass
        return None

    # ── Query helpers ────────────────────────────────────────────────────

    def search(self, query: str, game: str = "All") -> List[ModelLibraryEntry]:
        """Search models by name. Case-insensitive substring match."""
        q = query.lower().strip()
        return [e for e in self.models
                if (game == "All" or e.game == game) and q in e.resref.lower()]

    def list_models_by_class(self, cls: str, game: str = "All") -> List[ModelLibraryEntry]:
        """Filter models by classification.

        ``cls='All'`` is a special wildcard that returns every model regardless
        of its classification (many K2 models have an empty model_class).
        Any other value is matched case-insensitively against ``entry.model_class``.
        """
        cls_lower = cls.lower()
        if cls_lower == "all":
            # Wildcard — return all models for the requested game
            return [e for e in self.models
                    if (game == "All" or e.game == game)]
        return [e for e in self.models
                if (game == "All" or e.game == game)
                and e.model_class.lower() == cls_lower]

    def list_textures(self, game: str = "All") -> List[str]:
        """Return all known texture names."""
        return list(self.textures)

    # ── TLK dialog string lookup ─────────────────────────────────────────

    def get_tlk_string(self, strref: int, game: str = "K1") -> str:
        """Look up a dialog string from the game's TLK file."""
        tlk = self._k1_tlk if game == "K1" else self._k2_tlk

        if tlk is None:
            gdir = self.k1_dir if game == "K1" else self.k2_dir
            if gdir:
                tlk_path = Path(gdir) / 'dialog.tlk'
                if tlk_path.exists():
                    try:
                        from ..core.game_library_ext import TLKReader
                        t = TLKReader(str(tlk_path))
                        t.load()
                        if game == "K1":
                            self._k1_tlk = t
                        else:
                            self._k2_tlk = t
                        tlk = t
                    except Exception as ex:
                        log.warning(f"TLK load error: {ex}")

        if tlk:
            return tlk.get(strref, '')
        return ''

    # ── Texture data fetching ────────────────────────────────────────────

    def get_texture_data(self, resref: str, game: str = "K1") -> Optional[bytes]:
        """
        Find texture bytes: Override folder first, then ERF texture packs, then KEY/BIF.
        Returns raw bytes (may be TPC or TGA depending on source).

        Lookup order (highest priority first):
          0. Override/ folder loose .tpc / .tga files (KotOR engine override priority)
          1. ERF/TexturePack archives for `game` – type 0x0BBF (TPC in ERF) or 0x07D2 or 0x0003
          2. KEY/BIF archives for `game` – TPC (0x07D2 from items/party/player BIFs) or TGA
          3. Retry with trailing-digit-stripped name (e.g. "c_bantha01" -> "c_bantha")
          4. If both K1 and K2 dirs are present, also search the OTHER game's archives
             so creatures from one game can always find their textures regardless of
             which game_tag the TextureCache was configured with.
        """
        name_lower = resref.lower()

        def _search_override_for(gametag: str, name: str) -> Optional[bytes]:
            """Check Override/ folder for loose texture files (highest priority)."""
            gdir = self.k1_dir if gametag == "K1" else self.k2_dir
            if not gdir:
                return None
            gd = Path(gdir)
            for override_sub in ('Override', 'override'):
                override = gd / override_sub
                if not override.is_dir():
                    continue
                # Check .tpc first (binary TPC), then .tga (may be TPC or TGA)
                for ext in ('.tpc', '.TPC', '.tga', '.TGA'):
                    p = override / (name + ext)
                    if p.exists():
                        try:
                            return p.read_bytes()
                        except Exception:
                            pass
            return None

        def _search_erfs_for(gametag: str, name: str) -> Optional[bytes]:
            erfs = self._k1_erfs if gametag == "K1" else self._k2_erfs
            # TexturePack priority: swpc_tex_tpa.erf (highest quality) must win
            # over swpc_tex_tpb.erf and swpc_tex_tpc.erf (lower quality).
            # We partition ERFs into TexturePack buckets and search in quality
            # order: TPA → TPB → TPC → other ERFs.
            # Within each bucket we still search in reverse load order so that
            # later-added overrides win, matching the original intent of reversed().
            def _erf_quality(er_path: str) -> int:
                p = er_path.lower()
                # Lower number = searched first (higher priority)
                if 'swpc_tex_tpa' in p: return 0   # highest quality
                if 'swpc_tex_tpb' in p: return 1
                if 'swpc_tex_tpc' in p: return 2
                if 'swpc_tex_gui' in p: return 3   # GUI atlas, low prio for creatures
                # Non-TexturePack ERFs: searched after texture packs
                return 4
            sorted_erfs = sorted(erfs, key=lambda er: _erf_quality(er.path))
            for er in sorted_erfs:
                for rt in [RES_TPC_ERF, RES_TGA, 0x07D2]:
                    e = er.get(name, rt)
                    if e:
                        try:
                            raw = e.read()
                            # Skip empty entries – some RIM files contain 0-byte
                            # placeholder entries for textures that are actually
                            # stored in the TexturePacks ERFs.  An empty read()
                            # must NOT block the search from finding the real data.
                            if raw:
                                return raw
                        except Exception:
                            pass
            return None

        def _search_key_for(gametag: str, name: str) -> Optional[bytes]:
            reader = self._k1_key if gametag == "K1" else self._k2_key
            if reader:
                for rt in [RES_TPC, RES_TGA]:
                    e = reader.get(name, rt)
                    if e and e.is_texture:
                        try:
                            return e.read()
                        except Exception:
                            pass
            return None

        def _search_game(gametag: str, name: str) -> Optional[bytes]:
            raw = _search_erfs_for(gametag, name)
            if raw:
                return raw
            return _search_key_for(gametag, name)

        # 0. Check Override folder first (highest priority – KotOR engine rule)
        raw = _search_override_for(game, name_lower)
        if raw:
            return raw

        # 1 + 2. Try exact name in ERF / KEY for the requested game
        raw = _search_game(game, name_lower)
        if raw:
            return raw

        # 3a. Fallback: strip trailing digits (e.g. "c_bantha01" -> "c_bantha")
        #     Handles the case where the archive stores a bare name but MDL says "01".
        stripped = name_lower.rstrip('0123456789')
        if stripped and stripped != name_lower:
            raw = _search_game(game, stripped)
            if raw:
                return raw

        # 3b. Forward-digit append fallback: try name + "01", "02" … "05"
        #     KotOR texture packs (swpc_tex_tpa.erf) store entries as "c_drexl01",
        #     "c_rancor01" etc. even when the MDL node's texture field contains the
        #     bare name "c_drexl".  The strip-digits fallback (3a) only helps the
        #     reverse direction; this covers the bare-name → suffixed-entry case.
        if not stripped or stripped == name_lower:
            # Only try this when the name has NO trailing digits already
            # (i.e. it IS the bare name).  Avoids redundant lookups for names
            # that already have a suffix (those are handled by 3a above).
            for suffix in ('01', '02', '03', '04', '05'):
                candidate = name_lower + suffix
                raw = _search_game(game, candidate)
                if raw:
                    return raw

        # 4. Cross-game fallback: if both K1+K2 dirs are present and primary game
        #    didn't find it, try the OTHER game's archives.
        #    This ensures c_bantha (K1 creature) textures are found even when
        #    game_tag was set to "K2" for a dual-install setup.
        other = "K2" if game == "K1" else "K1"
        other_dir = self.k2_dir if other == "K2" else self.k1_dir
        if other_dir:
            # Check other game's Override folder first
            raw = _search_override_for(other, name_lower)
            if raw:
                return raw
            raw = _search_game(other, name_lower)
            if raw:
                return raw
            if stripped and stripped != name_lower:
                raw = _search_game(other, stripped)
                if raw:
                    return raw
            # Also try digit-append in cross-game search
            if not stripped or stripped == name_lower:
                for suffix in ('01', '02', '03', '04', '05'):
                    candidate = name_lower + suffix
                    raw = _search_game(other, candidate)
                    if raw:
                        return raw

        return None

    # ── Model data fetching ──────────────────────────────────────────────

    def get_model_data(self, entry: ModelLibraryEntry) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Returns (mdl_bytes, mdx_bytes)."""
        mdl_data = None
        mdx_data = None

        src = Path(entry.source)
        if src.is_file() and src.suffix.lower() == '.mdl':
            mdl_data = src.read_bytes()
            mdx = src.with_suffix('.mdx')
            if mdx.exists():
                mdx_data = mdx.read_bytes()
            return mdl_data, mdx_data

        reader = self._k1_key if entry.game == "K1" else self._k2_key
        if reader:
            e_mdl = reader.get(entry.resref, RES_MDL)
            e_mdx = reader.get(entry.resref, RES_MDX)
            if e_mdl:
                try:
                    mdl_data = e_mdl.read()
                except Exception:
                    pass
            if e_mdx:
                try:
                    mdx_data = e_mdx.read()
                except Exception:
                    pass
            if mdl_data:
                return mdl_data, mdx_data or b''

        try:
            er = ERFReader(entry.source)
            er.load()
            e_mdl = er.get(entry.resref, RES_MDL)
            e_mdx = er.get(entry.resref, RES_MDX)
            if e_mdl:
                mdl_data = e_mdl.read()
            if e_mdx:
                mdx_data = e_mdx.read()
        except Exception as ex:
            log.error(f"ERF read error: {ex}")

        return mdl_data, mdx_data or b''

    def extract_to_folder(self, entry: ModelLibraryEntry, out_dir: str,
                           include_textures: bool = True) -> List[str]:
        """Extract MDL+MDX (and optionally textures) to a folder."""
        os.makedirs(out_dir, exist_ok=True)
        mdl, mdx = self.get_model_data(entry)
        written = []
        if mdl:
            p = os.path.join(out_dir, f"{entry.resref}.mdl")
            with open(p, 'wb') as f:
                f.write(mdl)
            written.append(p)
        if mdx:
            p = os.path.join(out_dir, f"{entry.resref}.mdx")
            with open(p, 'wb') as f:
                f.write(mdx)
            written.append(p)

        if include_textures and mdl:
            tex_names = self._scan_texture_names(mdl)
            tex_dir = os.path.join(out_dir, 'textures')
            os.makedirs(tex_dir, exist_ok=True)
            for tname in tex_names:
                tdata = self.get_texture_data(tname, entry.game)
                if tdata:
                    ext = self._detect_texture_ext(tdata)
                    tp = os.path.join(tex_dir, f"{tname}{ext}")
                    with open(tp, 'wb') as f:
                        f.write(tdata)
                    written.append(tp)

        return written

    def _scan_texture_names(self, mdl_data: bytes) -> List[str]:
        """Scan binary MDL for texture name fields using the binary parser."""
        try:
            from src.core.game.kotor_loader import load_model_from_bytes
            model = load_model_from_bytes(mdl_data, b'')
            names = []
            seen  = set()
            for node in model.all_nodes():
                for attr in ('texture', 'lightmap', 'bump_map'):
                    t = getattr(node, attr, '')
                    if t and t.lower() not in ('null', '', 'black') and t.lower() not in seen:
                        names.append(t)
                        seen.add(t.lower())
            return names
        except Exception:
            pass
        # Fallback: raw byte scan
        names = []
        seen  = set()
        for i in range(0, len(mdl_data) - 32, 4):
            chunk = mdl_data[i:i+32]
            if not chunk or not (65 <= chunk[0] <= 122):
                continue
            s = chunk.split(b'\x00')[0].decode('ascii', 'replace')
            if (3 <= len(s) <= 32
                    and re.match(r'^[a-zA-Z0-9_]+$', s)
                    and s.lower() not in seen
                    and not s.startswith('NULL')):
                names.append(s)
                seen.add(s.lower())
                if len(names) > 64:
                    break
        return names

    def _detect_texture_ext(self, data: bytes) -> str:
        """Detect whether texture data is TPC or TGA.

        Uses two methods in sequence, mirroring PyKotor's detect_tpc() logic:
          1. PyKotor zero-byte test: if bytes[15..100] are all zero → TPC.
             (TPC has a 128-byte reserved header region; TGA files have
              non-zero data at these positions.)
          2. Our encoding+dimension check (handles enc=10 DXT1, enc=2/4 dual-mode).
        """
        if len(data) < 16:
            return '.bin'
        try:
            # ── Method 1: PyKotor zero-byte test (most reliable) ──────────────
            if len(data) >= 100 and all(b == 0 for b in data[15:100]):
                return '.tpc'

            # ── Method 2: Encoding + dimension heuristic ─────────────────────
            data_sz, = struct.unpack_from('<I', data, 0)
            w,       = struct.unpack_from('<H', data, 8)
            h,       = struct.unpack_from('<H', data, 10)
            enc      = data[12]
            # Include enc=10 (DXT1 explicit) that was previously missing
            if 0 < w <= 4096 and 0 < h <= 4096 and enc in (1, 2, 4, 10, 12, 13, 14):
                bx = max(1, (w+3)//4)
                by = max(1, (h+3)//4)
                if data_sz in (bx*by*8, bx*by*16, w*h, w*h*3, w*h*4, 0):
                    return '.tpc'
        except Exception:
            pass
        return '.tga'
