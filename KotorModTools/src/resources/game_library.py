"""
KotOR Game Resource Browser
Reads KEY/BIF/ERF/RIM/MOD archives to extract MDL, MDX, TPC, TGA files.
Works directly on any KotOR 1 or KotOR 2 installation folder.
"""

import struct, os, logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Resource Type IDs ───────────────────────────────────────────────────────
RES_MDL = 2002
RES_MDX = 2003
RES_TPC = 3007
RES_TGA = 3000
RES_TXI = 1448
RES_2DA = 2017
RES_LYT = 3000
RES_VIS = 3001
RES_IFO = 9999   # .ifo (area info)

RES_EXT_MAP = {
    RES_MDL: '.mdl', RES_MDX: '.mdx', RES_TPC: '.tpc',
    RES_TGA: '.tga', RES_TXI: '.txi', RES_2DA: '.2da',
}

@dataclass
class ResourceEntry:
    resref:   str   = ""
    res_type: int   = 0
    size:     int   = 0
    # source
    source_file: str = ""   # absolute path to BIF/ERF/RIM
    offset:      int = 0    # byte offset within source_file
    # or inline data
    data:        Optional[bytes] = None

    @property
    def filename(self) -> str:
        ext = RES_EXT_MAP.get(self.res_type, f'.{self.res_type}')
        return f"{self.resref}{ext}"

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
    """

    def __init__(self, game_dir: str):
        self.game_dir = Path(game_dir)
        self._resources: Dict[str, ResourceEntry] = {}   # key = "resref.ext"

    def load(self):
        """Scan game_dir for chitin.key and load all BIF entries"""
        key_path = self.game_dir / 'chitin.key'
        if not key_path.exists():
            # Try data subdirectory
            for p in [self.game_dir/'data'/'chitin.key',
                      self.game_dir/'override'/'chitin.key']:
                if p.exists(): key_path = p; break
        if not key_path.exists():
            log.warning(f"chitin.key not found in {self.game_dir}")
            return

        with open(str(key_path), 'rb') as f:
            data = f.read()

        sig = data[:4]
        if sig not in (b'KEY ', b'KEY\x20'):
            log.error("Not a valid KEY file")
            return

        ver         = data[4:8]
        bif_count   = struct.unpack_from('<I', data, 8)[0]
        key_count   = struct.unpack_from('<I', data, 12)[0]
        bif_off     = struct.unpack_from('<I', data, 16)[0]
        key_off     = struct.unpack_from('<I', data, 20)[0]

        # Read BIF file entries
        bif_paths: List[str] = []
        o = bif_off
        for i in range(bif_count):
            file_size = struct.unpack_from('<I', data, o)[0]; o+=4
            fname_off = struct.unpack_from('<I', data, o)[0]; o+=4
            fname_len = struct.unpack_from('<H', data, o)[0]; o+=2
            drives    = struct.unpack_from('<H', data, o)[0]; o+=2
            bif_name  = data[fname_off:fname_off+fname_len].rstrip(b'\x00').decode('ascii','replace')
            bif_name  = bif_name.replace('\\', os.sep).replace('/', os.sep)
            bif_paths.append(str(self.game_dir / bif_name))

        # Read resource key entries
        o = key_off
        for i in range(key_count):
            resref   = data[o:o+16].rstrip(b'\x00').decode('ascii','replace'); o+=16
            res_type = struct.unpack_from('<H', data, o)[0]; o+=2
            res_id   = struct.unpack_from('<I', data, o)[0]; o+=4
            bif_idx  = (res_id >> 20) & 0xFFF
            bif_slot = res_id & 0xFFFFF

            if bif_idx >= len(bif_paths):
                continue
            bif_file = bif_paths[bif_idx]

            entry = ResourceEntry(
                resref=resref, res_type=res_type,
                source_file=bif_file, offset=0, size=0
            )
            # Get actual offset from BIF
            if os.path.exists(bif_file):
                try:
                    off, sz = self._get_bif_entry(bif_file, bif_slot, res_type)
                    entry.offset = off
                    entry.size   = sz
                except Exception as e:
                    log.debug(f"BIF entry error {bif_file}:{bif_slot}: {e}")

            key = f"{resref.lower()}.{RES_EXT_MAP.get(res_type,'bin')[1:]}"
            self._resources[key] = entry

        log.info(f"KEY loaded: {len(self._resources)} resources from {bif_count} BIFs")

    def _get_bif_entry(self, bif_path: str, slot: int, res_type: int) -> Tuple[int,int]:
        with open(bif_path, 'rb') as f:
            header = f.read(20)
        sig      = header[:4]
        if sig not in (b'BIFF', b'BIFF'):
            return 0, 0
        var_count = struct.unpack_from('<I', header, 8)[0]
        fix_count = struct.unpack_from('<I', header, 12)[0]
        var_off   = struct.unpack_from('<I', header, 16)[0]

        with open(bif_path, 'rb') as f:
            f.seek(var_off + slot * 16)
            entry_data = f.read(16)
        if len(entry_data) < 16:
            return 0, 0
        res_id  = struct.unpack_from('<I', entry_data, 0)[0]
        offset  = struct.unpack_from('<I', entry_data, 4)[0]
        file_sz = struct.unpack_from('<I', entry_data, 8)[0]
        rtype   = struct.unpack_from('<I', entry_data,12)[0]
        return offset, file_sz

    def get(self, resref: str, res_type: int) -> Optional[ResourceEntry]:
        ext = RES_EXT_MAP.get(res_type,'bin')[1:]
        key = f"{resref.lower()}.{ext}"
        return self._resources.get(key)

    def list_type(self, res_type: int) -> List[ResourceEntry]:
        ext = RES_EXT_MAP.get(res_type,'bin')[1:]
        return [e for k,e in self._resources.items() if k.endswith('.'+ext)]


# ── ERF/RIM/MOD reader ──────────────────────────────────────────────────────

class ERFReader:
    """
    Reads ERF / RIM / MOD archives.
    ERF V1.0 format – used for modules, textures packs, etc.
    """

    def __init__(self, erf_path: str):
        self.path = erf_path
        self._resources: Dict[str, ResourceEntry] = {}

    def load(self):
        with open(self.path, 'rb') as f:
            data = f.read()

        sig = data[:4].decode('ascii','replace')
        ver = data[4:8].decode('ascii','replace')

        if sig not in ('ERF ', 'MOD ', 'RIM ', 'SAV '):
            log.error(f"Not a valid ERF/RIM: {self.path}")
            return

        if ver.startswith('V1'):
            self._load_v1(data)
        else:
            log.warning(f"Unsupported ERF version {ver}")

    def _load_v1(self, data: bytes):
        lang_count  = struct.unpack_from('<I', data, 8)[0]
        lang_size   = struct.unpack_from('<I', data,12)[0]
        entry_count = struct.unpack_from('<I', data,16)[0]
        locstr_off  = struct.unpack_from('<I', data,20)[0]
        keylist_off = struct.unpack_from('<I', data,24)[0]
        reslist_off = struct.unpack_from('<I', data,28)[0]

        for i in range(entry_count):
            ko = keylist_off + i*24
            resref   = data[ko:ko+16].rstrip(b'\x00').decode('ascii','replace')
            res_id   = struct.unpack_from('<I', data, ko+16)[0]
            res_type = struct.unpack_from('<H', data, ko+20)[0]

            ro = reslist_off + i*8
            offset   = struct.unpack_from('<I', data, ro)[0]
            size     = struct.unpack_from('<I', data, ro+4)[0]

            ext = RES_EXT_MAP.get(res_type,'bin')[1:]
            entry = ResourceEntry(
                resref=resref, res_type=res_type,
                source_file=self.path, offset=offset, size=size
            )
            self._resources[f"{resref.lower()}.{ext}"] = entry

    def get(self, resref: str, res_type: int) -> Optional[ResourceEntry]:
        ext = RES_EXT_MAP.get(res_type,'bin')[1:]
        return self._resources.get(f"{resref.lower()}.{ext}")

    def list_type(self, res_type: int) -> List[ResourceEntry]:
        ext = RES_EXT_MAP.get(res_type,'bin')[1:]
        return [e for k,e in self._resources.items() if k.endswith('.'+ext)]

    def list_all(self) -> List[ResourceEntry]:
        return list(self._resources.values())


# ── High-level Game Library ──────────────────────────────────────────────────

@dataclass
class ModelLibraryEntry:
    resref:   str
    game:     str   # "K1" or "K2"
    source:   str   # archive path
    res_type: int   = RES_MDL
    has_mdx:  bool  = False
    has_texture: bool = False


class GameLibrary:
    """
    High-level interface: scans a KotOR installation and provides
    a browseable list of all models and textures.
    """

    def __init__(self):
        self.k1_dir: str = ""
        self.k2_dir: str = ""
        self._k1_key:  Optional[KEYBIFReader] = None
        self._k2_key:  Optional[KEYBIFReader] = None
        self._k1_erfs: List[ERFReader] = []
        self._k2_erfs: List[ERFReader] = []
        self.models:   List[ModelLibraryEntry] = []
        self.textures: List[str] = []

    def set_k1_dir(self, d: str):
        self.k1_dir = d

    def set_k2_dir(self, d: str):
        self.k2_dir = d

    def scan(self, progress_cb=None):
        self.models   = []
        self.textures = []

        if self.k1_dir and os.path.isdir(self.k1_dir):
            self._scan_game(self.k1_dir, "K1", progress_cb)
        if self.k2_dir and os.path.isdir(self.k2_dir):
            self._scan_game(self.k2_dir, "K2", progress_cb)

    def _scan_game(self, game_dir: str, tag: str, progress_cb):
        log.info(f"Scanning {tag}: {game_dir}")
        gd = Path(game_dir)

        # KEY/BIF
        key = KEYBIFReader(game_dir)
        try:
            key.load()
            if tag == "K1": self._k1_key = key
            else:           self._k2_key = key
            for e in key.list_type(RES_MDL):
                self.models.append(ModelLibraryEntry(
                    resref=e.resref, game=tag, source=e.source_file))
            for e in key.list_type(RES_TPC):
                self.textures.append(e.resref.lower())
        except Exception as ex:
            log.debug(f"KEY scan error: {ex}")

        # ERFs in modules/
        for sub in ['modules', 'data', 'streamtextures', 'texturepacks']:
            sub_dir = gd / sub
            if not sub_dir.is_dir(): continue
            for erf_file in sub_dir.glob('*.{erf,rim,mod}'):
                try:
                    er = ERFReader(str(erf_file))
                    er.load()
                    for e in er.list_type(RES_MDL):
                        self.models.append(ModelLibraryEntry(
                            resref=e.resref, game=tag, source=str(erf_file)))
                except Exception: pass

        # Override folder (loose files)
        override = gd / 'override'
        if override.is_dir():
            for f in override.glob('*.mdl'):
                self.models.append(ModelLibraryEntry(
                    resref=f.stem, game=tag, source=str(f)))

        log.info(f"  {tag}: found {len([m for m in self.models if m.game==tag])} models")
        if progress_cb: progress_cb(f"Scanned {tag}: {len(self.models)} models")

    def get_model_data(self, entry: ModelLibraryEntry) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Returns (mdl_bytes, mdx_bytes) or (None, None)"""
        mdl_data = None; mdx_data = None

        src = Path(entry.source)
        if src.is_file() and src.suffix.lower() == '.mdl':
            # Loose file
            mdl_data = src.read_bytes()
            mdx = src.with_suffix('.mdx')
            if mdx.exists(): mdx_data = mdx.read_bytes()
            return mdl_data, mdx_data

        # Try KEY readers
        reader = self._k1_key if entry.game=="K1" else self._k2_key
        if reader:
            e_mdl = reader.get(entry.resref, RES_MDL)
            e_mdx = reader.get(entry.resref, RES_MDX)
            if e_mdl:
                try: mdl_data = e_mdl.read()
                except: pass
            if e_mdx:
                try: mdx_data = e_mdx.read()
                except: pass
            if mdl_data: return mdl_data, mdx_data or b''

        # Try ERF
        try:
            er = ERFReader(entry.source)
            er.load()
            e_mdl = er.get(entry.resref, RES_MDL)
            e_mdx = er.get(entry.resref, RES_MDX)
            if e_mdl: mdl_data = e_mdl.read()
            if e_mdx: mdx_data = e_mdx.read()
        except Exception as e:
            log.error(f"ERF read error: {e}")

        return mdl_data, mdx_data or b''

    def get_texture_data(self, resref: str, game: str = "K1") -> Optional[bytes]:
        reader = self._k1_key if game=="K1" else self._k2_key
        if reader:
            for rt in [RES_TPC, RES_TGA]:
                e = reader.get(resref, rt)
                if e:
                    try: return e.read()
                    except: pass
        return None

    def extract_to_folder(self, entry: ModelLibraryEntry, out_dir: str) -> List[str]:
        """Extract MDL+MDX to folder, return list of written files"""
        os.makedirs(out_dir, exist_ok=True)
        mdl, mdx = self.get_model_data(entry)
        written = []
        if mdl:
            p = os.path.join(out_dir, f"{entry.resref}.mdl")
            with open(p,'wb') as f: f.write(mdl)
            written.append(p)
        if mdx:
            p = os.path.join(out_dir, f"{entry.resref}.mdx")
            with open(p,'wb') as f: f.write(mdx)
            written.append(p)
        return written
