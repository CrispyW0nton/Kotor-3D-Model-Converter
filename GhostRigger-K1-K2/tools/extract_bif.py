#!/usr/bin/env python3
"""
BIF Extractor for KotOR game data.
Extracts MDL, MDX, and TPC files from BIF archives.
Model names are read from the MDL binary header (offset 20, 32 chars).
"""
import struct, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'game_data' / 'data'
OUT_MODELS   = ROOT / 'game_data' / 'extracted' / 'models'
OUT_TEXTURES = ROOT / 'game_data' / 'extracted' / 'textures'

OUT_MODELS.mkdir(parents=True, exist_ok=True)
OUT_TEXTURES.mkdir(parents=True, exist_ok=True)

# KotOR resource type IDs
TYPE_MDL = 2002
TYPE_MDX = 3008   # actually 0xBC0
TYPE_TGA = 2056
TYPE_TPC = 2064

def read_bif_entries(bif_path):
    """Read all variable-resource entries from a BIF file."""
    with open(bif_path, 'rb') as f:
        hdr = f.read(20)
        vres_c = struct.unpack_from('<I', hdr, 8)[0]
        vres_o = struct.unpack_from('<I', hdr, 16)[0]
        f.seek(vres_o)
        entries = []
        for i in range(vres_c):
            d = f.read(16)
            if len(d) < 16: break
            res_id, offset, size, res_type = struct.unpack_from('<IIII', d)
            entries.append({'idx': i, 'id': res_id, 'offset': offset,
                            'size': size, 'type': res_type})
    return entries

def read_mdl_name(bif_path, offset):
    """Read the model resref name from MDL binary header at offset 20."""
    with open(bif_path, 'rb') as f:
        f.seek(offset + 20)
        name_bytes = f.read(32)
    name = name_bytes.split(b'\x00')[0].decode('latin-1', errors='replace').strip()
    return name.lower()

def extract_bif_resource(bif_path, offset, size, out_path):
    """Extract one resource to disk."""
    with open(bif_path, 'rb') as f:
        f.seek(offset)
        data = f.read(size)
    with open(out_path, 'wb') as f:
        f.write(data)

def extract_models():
    """Extract all MDL+MDX pairs from models.bif."""
    bif_path = DATA / 'models.bif'
    if not bif_path.exists():
        print(f"models.bif not found: {bif_path}"); return

    print(f"Reading models.bif ({bif_path.stat().st_size//1024//1024}MB)...")
    entries = read_bif_entries(bif_path)

    mdl_entries = [e for e in entries if e['type'] == TYPE_MDL]
    mdx_entries = [e for e in entries if e['type'] == TYPE_MDX]

    print(f"  MDL entries: {len(mdl_entries)}")
    print(f"  MDX entries: {len(mdx_entries)}")

    # Build name→entry index for MDL
    # MDX entries are matched 1-to-1 with MDL by index position
    name_counts = {}
    mdl_named = []
    for i, e in enumerate(mdl_entries):
        name = read_mdl_name(str(bif_path), e['offset'])
        if not name or name == 'null':
            name = f'unknown_{i:04d}'
        # Handle duplicate names
        if name in name_counts:
            name_counts[name] += 1
            unique_name = f"{name}_{name_counts[name]:02d}"
        else:
            name_counts[name] = 0
            unique_name = name
        mdl_named.append((unique_name, e, mdx_entries[i] if i < len(mdx_entries) else None))

    print(f"\nExtracting {len(mdl_named)} MDL/MDX pairs...")
    extracted = 0
    skipped   = 0

    for name, mdl_e, mdx_e in mdl_named:
        mdl_out = OUT_MODELS / f"{name}.mdl"
        mdx_out = OUT_MODELS / f"{name}.mdx"

        # Skip if already extracted
        if mdl_out.exists() and mdx_out.exists():
            skipped += 1
            continue

        try:
            extract_bif_resource(str(bif_path), mdl_e['offset'], mdl_e['size'], str(mdl_out))
            if mdx_e:
                extract_bif_resource(str(bif_path), mdx_e['offset'], mdx_e['size'], str(mdx_out))
            else:
                mdx_out.write_bytes(b'')  # empty MDX
            extracted += 1
            if extracted % 100 == 0:
                print(f"  Extracted {extracted}/{len(mdl_named)}...")
        except Exception as ex:
            print(f"  ERROR extracting {name}: {ex}")

    print(f"\nDone: {extracted} extracted, {skipped} already existed")
    print(f"Output: {OUT_MODELS}")

    # Build name index
    index_path = OUT_MODELS / '_index.txt'
    with open(index_path, 'w') as f:
        for name, mdl_e, mdx_e in mdl_named:
            f.write(f"{name}\n")
    print(f"Index: {index_path}")

def extract_textures():
    """Extract TPC textures from textures.bif and any lightmap BIFs."""
    # Main texture BIF
    for bif_name in ['textures.bif', 'items.bif', 'player.bif']:
        bif_path = DATA / bif_name
        if not bif_path.exists(): continue
        print(f"\nReading {bif_name}...")
        entries = read_bif_entries(str(bif_path))
        tpc_entries = [e for e in entries if e['type'] in (TYPE_TPC, TYPE_TGA, 2022, 3)]
        print(f"  Texture entries: {len(tpc_entries)}")
        for i, e in enumerate(tpc_entries):
            out_path = OUT_TEXTURES / f"tex_{bif_name.replace('.bif','')}_{i:04d}.tpc"
            if not out_path.exists():
                try:
                    extract_bif_resource(str(bif_path), e['offset'], e['size'], str(out_path))
                except Exception as ex:
                    print(f"  ERROR: {ex}")

    # Also check models.bif for embedded TPC textures
    bif_path = DATA / 'models.bif'
    print(f"\nScanning models.bif for TPC textures...")
    entries = read_bif_entries(str(bif_path))
    tpc_entries = [e for e in entries if e['type'] in (TYPE_TPC, TYPE_TGA)]
    print(f"  TPC/TGA entries in models.bif: {len(tpc_entries)}")

if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode in ('all', 'models'):
        extract_models()
    if mode in ('all', 'textures'):
        extract_textures()
