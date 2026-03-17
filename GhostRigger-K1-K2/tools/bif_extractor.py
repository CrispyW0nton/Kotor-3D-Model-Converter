"""
BIF / ERF extractor for KotOR 1 k1Data.
Reads chitin.key → models.bif, swpc_tex_tpa.erf, swpc_tex_tpb.erf
and extracts .mdl/.mdx pairs and .tga/.tpc textures to a staging directory.

Usage:
    python bif_extractor.py --k1data /path/to/k1Data --out /path/to/out [--models NAME ...]
"""

import struct, os, sys, argparse, logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# ─────────────────── KEY / BIF structures ────────────────────────────────────
# chitin.key layout:
#   0  FileType (4) "KEY "
#   4  FileVersion (4) "V1  "
#   8  BIFCount (u32)
#  12  KeyCount (u32)
#  16  OffsetToFileTable (u32)
#  20  OffsetToKeyTable (u32)
#   ...
# BIF table entry (12 bytes):
#   0  FileSize (u32)
#   4  FilenameOffset (u32)
#   8  FilenameSize (u16)
#  10  Drives (u16)
# Key table entry (22 bytes):
#   0  ResRef (16 bytes, null-padded)
#  16  ResType (u16)
#  18  ResID (u32) – high 20 bits = BIF index, low 12 bits = resource index

# BIF file layout:
#   0  FileType (4) "BIFF"
#   4  FileVersion (4) "V1  "
#   8  VarResCount (u32)
#  12  FixedResCount (u32)
#  16  VariableTableOffset (u32)
# Entry (16 bytes):
#   0  ID (u32) – low 20 bits = index
#   4  Offset (u32)
#   8  FileSize (u32)
#  12  ResourceType (u32)

# ERF layout:
#   0  FileType (4) "ERF "
#   4  FileVersion (4) "V1.0"
#   8  LanguageCount (u32)
#  12  LocalizedStringSize (u32)
#  16  EntryCount (u32)
#  20  OffsetToLocalizedString (u32)
#  24  OffsetToKeyList (u32)
#  28  OffsetToResourceList (u32)
#   ...
# Key entry (24 bytes):
#   0  ResRef (16) null-padded
#  16  ResourceID (u32)
#  20  ResourceType (u16)
#  22  Reserved (u16)
# Resource entry (8 bytes):
#   0  OffsetToResource (u32)
#   4  ResourceSize (u32)

RES_MDL  = 2002
RES_MDX  = 3008   # KotOR 1 MDX resource type (was incorrectly 2003; confirmed from chitin.key inspection)
RES_TGA  = 3003
RES_TPC  = 3007

EXT_MAP = {
    RES_MDL: '.mdl',
    RES_MDX: '.mdx',
    RES_TGA: '.tga',
    RES_TPC: '.tpc',
    1: '.bmp', 3: '.tga', 2002: '.mdl', 3008: '.mdx',
    2010: '.wok', 2012: '.mdl', 2013: '.mdx',
}

def _rstrip(b: bytes) -> str:
    return b.rstrip(b'\x00').decode('ascii', errors='replace').strip()

def _ru32(d, o): return struct.unpack_from('<I', d, o)[0]
def _ru16(d, o): return struct.unpack_from('<H', d, o)[0]


class ChitinKey:
    def __init__(self, path: str):
        with open(path, 'rb') as f:
            data = f.read()
        sig = data[:8]
        log.info(f"KEY sig={sig!r}")

        bif_count  = _ru32(data, 8)
        key_count  = _ru32(data, 12)
        bif_off    = _ru32(data, 16)
        key_off    = _ru32(data, 20)

        log.info(f"  BIFs={bif_count}  Keys={key_count}")

        # Parse BIF filename table
        self.bif_filenames: List[str] = []
        o = bif_off
        for i in range(bif_count):
            file_size  = _ru32(data, o)
            fname_off  = _ru32(data, o+4)
            fname_size = _ru16(data, o+8)
            o += 12
            name = data[fname_off:fname_off+fname_size].decode('ascii','replace').strip('\x00')
            self.bif_filenames.append(name.replace('\\','/'))

        # Parse key entries → {resref_lower: (bif_idx, res_idx, res_type)}
        self.keys: Dict[str, Tuple[int,int,int]] = {}
        o = key_off
        for i in range(key_count):
            resref   = _rstrip(data[o:o+16]).lower()
            res_type = _ru16(data, o+16)
            res_id   = _ru32(data, o+18)
            bif_idx  = (res_id >> 20) & 0xFFF
            res_idx  = res_id & 0xFFFFF
            o += 22
            # Store all entries; key = "resref.restype" to handle duplicates
            k = f"{resref}:{res_type}"
            self.keys[k] = (bif_idx, res_idx, res_type)

        log.info(f"  Loaded {len(self.keys)} key entries")


class BIFFile:
    def __init__(self, path: str):
        self.path = path
        self._index: Dict[int, Tuple[int,int,int]] = {}  # res_idx → (offset, size, type)
        self._loaded = False

    def _load_index(self):
        if self._loaded: return
        with open(self.path, 'rb') as f:
            hdr = f.read(20)
        sig = hdr[:8]
        if b'BIFF' not in sig:
            log.warning(f"BIF {self.path}: unexpected sig {sig!r}")
        vres_count = _ru32(hdr, 8)
        fixed_count= _ru32(hdr, 12)
        var_table_off = _ru32(hdr, 16)

        with open(self.path, 'rb') as f:
            f.seek(var_table_off)
            for i in range(vres_count):
                entry = f.read(16)
                if len(entry) < 16: break
                res_id   = _ru32(entry, 0)
                offset   = _ru32(entry, 4)
                size     = _ru32(entry, 8)
                res_type = _ru32(entry, 12)
                idx = res_id & 0xFFFFF
                self._index[idx] = (offset, size, res_type)
        self._loaded = True
        log.debug(f"  BIF index: {len(self._index)} entries from {self.path}")

    def extract(self, res_idx: int) -> Optional[bytes]:
        self._load_index()
        if res_idx not in self._index:
            return None
        offset, size, _ = self._index[res_idx]
        with open(self.path, 'rb') as f:
            f.seek(offset)
            return f.read(size)


class ERFFile:
    """Reads ERF / MOD / SAV archives (swpc_tex_tpa.erf etc.)"""
    def __init__(self, path: str):
        self.path = path
        self._index: Dict[str, Tuple[int,int,int]] = {}  # name_lower → (offset, size, type)
        self._loaded = False

    def _load_index(self):
        if self._loaded: return
        with open(self.path, 'rb') as f:
            hdr = f.read(160)
        sig = hdr[:8]
        lang_count     = _ru32(hdr,  8)
        loc_str_size   = _ru32(hdr, 12)
        entry_count    = _ru32(hdr, 16)
        off_loc_str    = _ru32(hdr, 20)
        off_key_list   = _ru32(hdr, 24)
        off_res_list   = _ru32(hdr, 28)

        with open(self.path, 'rb') as f:
            # Key list
            f.seek(off_key_list)
            keys = []
            for i in range(entry_count):
                entry = f.read(24)
                if len(entry) < 24: break
                resref   = _rstrip(entry[:16]).lower()
                res_id   = _ru32(entry, 16)
                res_type = _ru16(entry, 20)
                keys.append((resref, res_id, res_type))

            # Resource list
            f.seek(off_res_list)
            resources = []
            for i in range(entry_count):
                entry = f.read(8)
                if len(entry) < 8: break
                offset = _ru32(entry, 0)
                size   = _ru32(entry, 4)
                resources.append((offset, size))

        for (resref, res_id, res_type), (offset, size) in zip(keys, resources):
            k = f"{resref}:{res_type}"
            self._index[k] = (offset, size, res_type)

        self._loaded = True
        log.debug(f"  ERF index: {len(self._index)} entries from {self.path}")

    def extract(self, resref: str, res_type: int) -> Optional[bytes]:
        self._load_index()
        k = f"{resref.lower()}:{res_type}"
        if k not in self._index:
            return None
        offset, size, _ = self._index[k]
        with open(self.path, 'rb') as f:
            f.seek(offset)
            return f.read(size)

    def list_all(self) -> List[Tuple[str,int]]:
        self._load_index()
        result = []
        for k in self._index:
            parts = k.rsplit(':', 1)
            if len(parts) == 2:
                result.append((parts[0], int(parts[1])))
        return result


class K1DataExtractor:
    """High-level extractor: chitin.key + models.bif + texture ERFs."""

    def __init__(self, k1data_dir: str):
        self.k1data = Path(k1data_dir)
        self.key = ChitinKey(str(self.k1data / 'chitin.key'))

        # Map BIF filename (normalized) → BIFFile
        self.bifs: Dict[str, BIFFile] = {}
        for fname in self.key.bif_filenames:
            # fname is like "data\models.bif" → normalize
            basename = Path(fname).name.lower()
            full = self.k1data / basename
            if full.exists():
                self.bifs[basename] = BIFFile(str(full))
                log.info(f"  Registered BIF: {basename}")

        # ERF texture archives (high-res = tpa, medium = tpb, etc.)
        self.erfs: List[ERFFile] = []
        for erf_name in ['swpc_tex_tpa.erf', 'swpc_tex_tpb.erf', 'swpc_tex_tpc.erf', 'swpc_tex_gui.erf']:
            p = self.k1data / erf_name
            if p.exists():
                self.erfs.append(ERFFile(str(p)))
                log.info(f"  Registered ERF: {erf_name}")

    def list_models(self) -> List[str]:
        """Return all MDL resource names from chitin.key."""
        names = []
        for k in self.key.keys:
            resref, res_type_str = k.rsplit(':', 1)
            if int(res_type_str) == RES_MDL:
                names.append(resref)
        return sorted(names)

    def extract_model(self, name: str) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Extract (mdl_bytes, mdx_bytes) for a given resource name."""
        mdl = self._extract_res(name, RES_MDL)
        mdx = self._extract_res(name, RES_MDX)
        return mdl, mdx

    def extract_texture(self, name: str) -> Tuple[Optional[bytes], str]:
        """
        Try to extract texture by name. Returns (data, extension).
        KotOR1 ERFs store textures as TPC data but under TGA resource type.
        We detect the actual format from the data header.
        Checks ERFs (highest quality = tpa) then BIF textures.bif.
        """
        name_lower = name.lower()

        # Try TGA from ERFs first (swpc_tex_tpa has highest quality)
        for erf in self.erfs:
            data = erf.extract(name_lower, RES_TGA)
            if data:
                ext = self._detect_texture_ext(data)
                return data, ext

        # Try TPC from ERFs
        for erf in self.erfs:
            data = erf.extract(name_lower, RES_TPC)
            if data:
                return data, '.tpc'

        # Try from chitin.key / BIFs
        for res_type, default_ext in [(RES_TGA, '.tga'), (RES_TPC, '.tpc')]:
            data = self._extract_res(name_lower, res_type)
            if data:
                ext = self._detect_texture_ext(data) if res_type == RES_TGA else '.tpc'
                return data, ext

        return None, ''

    def _detect_texture_ext(self, data: bytes) -> str:
        """
        Detect whether bytes are a TPC or TGA file.
        KotOR ERFs store TPC data under RES_TGA (3003) resource type IDs.
        TPC detection: data_sz at [0] matches DXT1/DXT5/uncompressed, enc at [12] in {1,2,4}
        """
        if len(data) < 16:
            return '.tga'
        # TPC: check data_sz vs width/height DXT match
        data_sz = struct.unpack_from('<I', data, 0)[0]
        w       = struct.unpack_from('<H', data, 8)[0]
        h       = struct.unpack_from('<H', data, 10)[0]
        enc     = data[12]
        if w > 0 and h > 0 and enc in (1, 2, 4):
            dxt1_sz = max(8,  (max(1,w//4))*(max(1,h//4))*8)
            dxt5_sz = max(16, (max(1,w//4))*(max(1,h//4))*16)
            if data_sz in (dxt1_sz, dxt5_sz, w*h, w*h*3, w*h*4):
                return '.tpc'
        # Standard TGA: img_type at byte 2 must be in {0,1,2,3,9,10,11}
        if data[2] in (0, 1, 2, 3, 9, 10, 11):
            return '.tga'
        return '.tpc'

    def _extract_res(self, name: str, res_type: int) -> Optional[bytes]:
        k = f"{name.lower()}:{res_type}"
        if k not in self.key.keys:
            return None
        bif_idx, res_idx, _ = self.key.keys[k]
        if bif_idx >= len(self.key.bif_filenames):
            return None
        bif_name = Path(self.key.bif_filenames[bif_idx]).name.lower()
        bif = self.bifs.get(bif_name)
        if bif is None:
            return None
        return bif.extract(res_idx)


def extract_batch(k1data_dir: str, out_dir: str, model_names: List[str]):
    """Extract MDL/MDX + textures for a list of models."""
    out = Path(out_dir)
    (out / 'models').mkdir(parents=True, exist_ok=True)
    (out / 'textures').mkdir(parents=True, exist_ok=True)

    ex = K1DataExtractor(k1data_dir)

    for name in model_names:
        mdl, mdx = ex.extract_model(name)
        if mdl:
            p = out / 'models' / f"{name}.mdl"
            p.write_bytes(mdl)
            log.info(f"  Extracted {name}.mdl ({len(mdl):,} bytes)")
        else:
            log.warning(f"  NOT FOUND: {name}.mdl")

        if mdx:
            p = out / 'models' / f"{name}.mdx"
            p.write_bytes(mdx)
            log.info(f"  Extracted {name}.mdx ({len(mdx):,} bytes)")

    # Now extract textures referenced in the MDL ASCII (if any)
    # Try to find all texture names from the extracted MDLs
    tex_names = set()
    for name in model_names:
        mdl_path = out / 'models' / f"{name}.mdl"
        if mdl_path.exists():
            # Quick scan for texture names in binary MDL
            data = mdl_path.read_bytes()
            tex_names.update(_scan_texture_names(data))

    log.info(f"  Found {len(tex_names)} texture refs: {sorted(tex_names)[:20]}")
    for tex in sorted(tex_names):
        if not tex or len(tex) < 2: continue
        data, ext = ex.extract_texture(tex)
        if data:
            # Don't overwrite already-extracted files
            p_tga = out / 'textures' / f"{tex}.tga"
            p_tpc = out / 'textures' / f"{tex}.tpc"
            if p_tga.exists() or p_tpc.exists():
                log.debug(f"  Skipping (already exists): {tex}")
                continue
            p = out / 'textures' / f"{tex}{ext}"
            p.write_bytes(data)
            log.info(f"  Extracted texture {tex}{ext} ({len(data):,} bytes)")
        else:
            log.warning(f"  Texture NOT FOUND: {tex}")


def _scan_texture_names(data: bytes) -> List[str]:
    """Scan binary MDL for plausible 32-byte texture name slots."""
    names = []
    # Texture names appear in 32-byte null-padded slots in mesh nodes
    # Search all 32-byte aligned null-terminated ASCII strings
    i = 0
    while i < len(data) - 32:
        # Look for printable ASCII run of 3+ chars followed by nulls, within 32 bytes
        if 32 < data[i] < 127:  # printable start
            end = i
            while end < i+32 and 32 <= data[end] < 127:
                end += 1
            length = end - i
            if 3 <= length <= 31:
                # Check if rest of 32-byte slot is nulls
                rest = data[end:i+32]
                if all(b == 0 for b in rest) and rest:
                    name = data[i:end].decode('ascii', 'replace').strip()
                    if name and not any(c in name for c in '.,!@#$%^&*()'):
                        names.append(name.lower())
                    i = i + 32
                    continue
        i += 1
    return list(set(names))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract KotOR BIF/ERF resources')
    parser.add_argument('--k1data', required=True)
    parser.add_argument('--out', required=False, default='./extracted')
    parser.add_argument('--models', nargs='*', help='Model names to extract (no extension)')
    parser.add_argument('--list', action='store_true', help='List all model names')
    args = parser.parse_args()

    ex = K1DataExtractor(args.k1data)

    if args.list:
        models = ex.list_models()
        print(f"\nTotal MDL resources: {len(models)}")
        for m in models[:200]:
            print(f"  {m}")
        if len(models) > 200:
            print(f"  ... and {len(models)-200} more")
        sys.exit(0)

    if args.models:
        extract_batch(args.k1data, args.out, args.models)
    else:
        # Default: extract a representative test set
        test_models = [
            'c_bantha', 'p_bastila_ba', 'p_carth_ba', 'p_hk47_ba',
            'n_sithpraet', 'c_kath', 'p_malak_ba', 'n_jedimaster',
            'p_trask_ba', 'c_rancor', 'n_darkjedi01',
        ]
        extract_batch(args.k1data, args.out, test_models)
