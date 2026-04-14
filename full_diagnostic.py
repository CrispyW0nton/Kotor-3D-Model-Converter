#!/usr/bin/env python3
"""
full_diagnostic.py — Complete end-to-end diagnostic for m02aa_01a
=================================================================
1. Test KotorInstallation API for texture loading (diffuse + lightmap)
2. Test direct BIF/ERF extraction
3. Load model through GhostRigger pipeline
4. Dump per-node material table (≥15 nodes)
5. Render with GhostRigger renderer using real textures
6. Identify divergences
"""

import sys, os, struct, io, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')

# ─────────────────────────────────────────────────────────────────────────────
# Part 1: Test KotorInstallation API
# ─────────────────────────────────────────────────────────────────────────────

def test_kotor_installation():
    """Test what KotorInstallation returns for each texture."""
    print("\n" + "=" * 90)
    print("  PART 1: KotorInstallation API texture loading test")
    print("=" * 90)
    
    try:
        from src.core.kotor_install import KotorInstallation
        install = KotorInstallation(GAME_DIR)
    except Exception as e:
        print(f"  KotorInstallation init FAILED: {e}")
        return None
    
    # All textures needed by m02aa_01a
    diffuse_names = [
        'lts_trim01', 'lts_pwall01i', 'lts_nwall04i', 'lts_lite08',
        'lts_bwall04i', 'lts_pwall04', 'lts_rwall01', 'lmi_bed01',
        'lts_nwall02', 'lts_gwall01', 'lts_bwall02i', 'lts_glass01', 'lts_nums',
    ]
    lm_names = [
        'm02aa_01a_lm0', 'm02aa_01a_lm1', 'm02aa_01a_lm2',
        'm02aa_01a_lm3', 'm02aa_01a_lm4', 'm02aa_01a_lm5',
    ]
    
    results = {}
    print(f"\n  {'Name':24s} {'get_texture()':>14s} {'TPC(3007)':>10s} {'TGA(3)':>10s} {'TXI':>6s}")
    print(f"  {'─'*24} {'─'*14} {'─'*10} {'─'*10} {'─'*6}")
    
    for name in diffuse_names + lm_names:
        tex_raw = install.get_texture(name)
        tex_sz = len(tex_raw) if tex_raw else 0
        
        # Also test specific types
        tpc_raw = install.get(name, 3007)  # RES_TPC
        tga_raw = install.get(name, 3)     # RES_TGA
        txi_raw = install.get_txi(name)
        
        tpc_sz = len(tpc_raw) if tpc_raw else 0
        tga_sz = len(tga_raw) if tga_raw else 0
        
        status = "OK" if tex_sz > 100 else ("SMALL" if tex_sz > 0 else "MISS")
        if name.startswith('m02aa_01a_lm'):
            # Lightmaps - check if we're getting TGA from BIF
            if tex_sz < 100 and tga_sz > 100:
                status = "BUG-TPC-FIRST"  # get_texture tries TPC first, misses TGA
            elif tex_sz > 100 and tga_sz > 100:
                status = "OK(TGA)"
        
        results[name] = {
            'tex_sz': tex_sz, 'tpc_sz': tpc_sz, 'tga_sz': tga_sz,
            'txi': txi_raw[:30] if txi_raw else '', 'status': status
        }
        
        kind = "diffuse" if name in diffuse_names else "lightmap"
        print(f"  {name:24s} {tex_sz:>14d} {tpc_sz:>10d} {tga_sz:>10d} {len(txi_raw):>6d}  [{status}] ({kind})")
    
    return install, results


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: Direct BIF/ERF extraction (bypass KotorInstallation)
# ─────────────────────────────────────────────────────────────────────────────

def extract_from_erf(erf_path, target_names):
    """Extract TPC resources from ERF V1.0."""
    results = {}
    with open(erf_path, 'rb') as f:
        f.read(8)  # magic
        f.read(4)  # lang_count
        f.read(4)  # loc_str_size
        entry_count, = struct.unpack('<I', f.read(4))
        f.read(4)  # off_loc_str
        off_key_list, = struct.unpack('<I', f.read(4))
        off_res_list, = struct.unpack('<I', f.read(4))
        
        for i in range(entry_count):
            f.seek(off_key_list + i * 24)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_id, res_type = struct.unpack('<IH', f.read(6))
            if resref in target_names:
                f.seek(off_res_list + i * 8)
                data_offset, data_size = struct.unpack('<II', f.read(8))
                f.seek(data_offset)
                raw = f.read(data_size)
                if resref not in results or len(raw) > len(results[resref]):
                    results[resref] = raw
    return results


def extract_from_bif_via_key(key_path, game_dir, target_names):
    """Extract resources from BIF files via chitin.key. Returns LARGEST entry per name."""
    results = {}
    with open(key_path, 'rb') as f:
        f.read(4)  # magic
        f.read(4)  # version
        bif_count, = struct.unpack('<I', f.read(4))
        key_count, = struct.unpack('<I', f.read(4))
        off_file_table, = struct.unpack('<I', f.read(4))
        off_key_table, = struct.unpack('<I', f.read(4))
        
        bif_files = []
        for i in range(bif_count):
            f.seek(off_file_table + i * 12)
            bif_size, = struct.unpack('<I', f.read(4))
            name_offset, = struct.unpack('<I', f.read(4))
            name_size, = struct.unpack('<H', f.read(2))
            f.read(2)
            pos = f.tell()
            f.seek(name_offset)
            bif_name = f.read(name_size).rstrip(b'\x00').decode('ascii', errors='replace')
            bif_name = bif_name.replace('\\', '/')
            bif_files.append(bif_name)
            f.seek(pos)
        
        for i in range(key_count):
            f.seek(off_key_table + i * 22)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_type, = struct.unpack('<H', f.read(2))
            res_id, = struct.unpack('<I', f.read(4))
            
            if resref in target_names:
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(game_dir, bif_files[bif_idx].replace('/', os.sep))
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(4)  # magic
                            bf.read(4)  # version
                            var_res_count, = struct.unpack('<I', bf.read(4))
                            fix_res_count, = struct.unpack('<I', bf.read(4))
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            entry_id, = struct.unpack('<I', bf.read(4))
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            entry_type, = struct.unpack('<I', bf.read(4))
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            # Only keep the largest version (TGA>TXI)
                            if resref not in results or len(raw) > len(results[resref]):
                                results[resref] = raw
    return results


def decode_texture(raw_bytes, name=''):
    """Decode TPC/TGA texture data to a PIL Image."""
    from PIL import Image
    
    # Try TGA first (lightmaps)
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        return img.convert('RGBA')
    except Exception:
        pass
    
    # Try viewport's TPC loader (handles DXT, flip, alpha)
    try:
        from src.gui.viewport import _load_tpc_bytes
        img = _load_tpc_bytes(raw_bytes)
        if img:
            return img
    except Exception:
        pass
    
    # Fallback: PyKotor TPC reader
    try:
        from pykotor.resource.formats.tpc import read_tpc
        tpc = read_tpc(raw_bytes)
        pil_img = tpc.convert(tpc.format, 0)
        if hasattr(pil_img, 'size'):
            return pil_img.convert('RGBA')
    except Exception:
        pass
    
    return None


def direct_extract_all():
    """Extract all needed textures directly from game archives."""
    print("\n" + "=" * 90)
    print("  PART 2: Direct BIF/ERF texture extraction")
    print("=" * 90)
    
    erf_path = os.path.join(GAME_DIR, 'TexturePacks', 'swpc_tex_tpa.erf')
    key_path = os.path.join(GAME_DIR, 'chitin.key')
    
    diffuse_names = {
        'lts_trim01', 'lts_pwall01i', 'lts_nwall04i', 'lts_lite08',
        'lts_bwall04i', 'lts_pwall04', 'lts_rwall01', 'lmi_bed01',
        'lts_nwall02', 'lts_gwall01', 'lts_bwall02i', 'lts_glass01', 'lts_nums',
    }
    lm_names = {
        'm02aa_01a_lm0', 'm02aa_01a_lm1', 'm02aa_01a_lm2',
        'm02aa_01a_lm3', 'm02aa_01a_lm4', 'm02aa_01a_lm5',
    }
    
    # Extract from ERF
    raw_diffuse = extract_from_erf(erf_path, diffuse_names)
    # Extract from BIF (for lightmaps)
    raw_lm = extract_from_bif_via_key(key_path, GAME_DIR, lm_names)
    
    # Decode all
    textures = {}
    all_raw = {**raw_diffuse, **raw_lm}
    
    print(f"\n  {'Name':24s} {'Raw bytes':>10s} {'Decoded':>10s} {'Size':>12s}")
    print(f"  {'─'*24} {'─'*10} {'─'*10} {'─'*12}")
    
    for name in sorted(all_raw.keys()):
        raw = all_raw[name]
        img = decode_texture(raw, name)
        if img:
            textures[name] = img
            print(f"  {name:24s} {len(raw):>10d} {'OK':>10s} {str(img.size):>12s}")
        else:
            print(f"  {name:24s} {len(raw):>10d} {'FAIL':>10s} {'':>12s}")
    
    print(f"\n  Total decoded: {len(textures)} / {len(all_raw)}")
    return textures


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: Load model + per-node dump
# ─────────────────────────────────────────────────────────────────────────────

def load_model_and_dump():
    """Load model through GhostRigger and produce per-node material table."""
    print("\n" + "=" * 90)
    print("  PART 3: GhostRigger model load + per-node material state")
    print("=" * 90)
    
    from src.core.kotor_loader import load_model_from_bytes
    
    mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
    mdx_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdx')
    
    with open(mdl_path, 'rb') as f:
        mdl = f.read()
    with open(mdx_path, 'rb') as f:
        mdx = f.read()
    
    model = load_model_from_bytes(mdl, mdx)
    if not model:
        print("  FAILED to load model!")
        return None, []
    
    print(f"  Model: {model.name}")
    print(f"  Classification: {model.classification} (type={model.model_type})")
    
    # Also load via PyKotor raw for comparison
    from pykotor.resource.formats.mdl.mdl_auto import read_mdl as pk_read_mdl
    pk_mdl = pk_read_mdl(mdl, source_ext=mdx)
    
    # Build pk raw lookup
    pk_raw = {}
    def _walk_pk(node):
        mesh = getattr(node, 'mesh', None)
        if mesh is not None:
            pk_raw[node.name] = {
                'tex1': str(getattr(mesh, 'texture_1', '') or '').strip().lower(),
                'tex2': str(getattr(mesh, 'texture_2', '') or '').strip().lower(),
                'has_lm': bool(getattr(mesh, 'has_lightmap', False)),
                'n_uv1': len(mesh.vertex_uv1) if hasattr(mesh, 'vertex_uv1') and mesh.vertex_uv1 else 0,
                'n_uv2': len(getattr(mesh, 'vertex_uv2', None) or []) if not isinstance(getattr(mesh, 'vertex_uv2', None), (bool, str)) else 0,
                'n_faces': len(mesh.faces) if mesh.faces else 0,
                'raw_mats': sorted(set(int(getattr(f, 'material', 0) or 0) for f in (mesh.faces or []))),
            }
        for c in (node.children or []):
            _walk_pk(c)
    _walk_pk(pk_mdl.root)
    
    # Now dump GhostRigger nodes
    mesh_nodes = [n for n in model.all_nodes() if getattr(n, 'is_mesh', False)]
    print(f"  Mesh nodes: {len(mesh_nodes)}")
    
    node_table = []
    for n in mesh_nodes:
        tex = str(getattr(n, 'texture', '') or '').strip().lower()
        lm = str(getattr(n, 'lightmap', '') or '').strip().lower()
        tex_names = getattr(n, 'texture_names', [])
        tc = int(getattr(n, 'tex_count', 1))
        has_lm = bool(getattr(n, 'has_lightmap', False))
        uvs = getattr(n, 'uvs', [])
        uvs_lm = getattr(n, 'uvs_lm', [])
        faces = getattr(n, 'faces', [])
        face_mats = getattr(n, 'face_mats', [])
        face_uvs = getattr(n, 'face_uvs', [])
        
        # Check face_uvs vs faces (explicit tvert vs vertex-index)
        has_fuv_diff = False
        if face_uvs and faces:
            for fv, fu in zip(faces[:50], face_uvs[:50]):
                if fv != fu:
                    has_fuv_diff = True
                    break
        
        unique_fm = sorted(set(face_mats)) if face_mats else []
        fm_counts = {}
        for m in face_mats:
            fm_counts[m] = fm_counts.get(m, 0) + 1
        
        # Determine render path
        if tc <= 1:
            render_path = 'single-tex'
        elif has_lm:
            render_path = 'LM-composite'
        else:
            render_path = 'multi-mat-split'
        
        # Sampler bindings
        s0_tex = tex if tex else '(none)'
        s0_uv = 'UV0'
        s0_wrap = 'REPEAT'
        if has_lm and lm:
            s1_tex = lm
            s1_uv = 'UV1(LM)'
            s1_wrap = 'CLAMP'
        elif tc > 1 and not has_lm:
            s1_tex = tex_names[1] if len(tex_names) > 1 else '(none)'
            s1_uv = 'UV0(face)'
            s1_wrap = 'REPEAT'
        else:
            s1_tex = '(none)'
            s1_uv = 'N/A'
            s1_wrap = 'N/A'
        
        # Raw PyKotor data
        pk = pk_raw.get(n.name, {})
        
        row = {
            'name': n.name,
            'texture_1': tex,
            'texture_2': lm,
            'texture_names': tex_names,
            'tex_count': tc,
            'has_lightmap_raw': pk.get('has_lm', '?'),
            'has_lightmap_gr': has_lm,
            'slot1_role': 'lightmap' if has_lm and lm else ('diffuse2' if tc > 1 else 'N/A'),
            'n_uvs': len(uvs),
            'n_uvs_lm': len(uvs_lm),
            'n_faces': len(faces),
            'unique_face_mats': unique_fm,
            'face_counts_per_slot': fm_counts,
            'pk_raw_mats': pk.get('raw_mats', []),
            'tvert_diff': has_fuv_diff,
            'render_path': render_path,
            's0': {'tex': s0_tex, 'uv': s0_uv, 'wrap': s0_wrap},
            's1': {'tex': s1_tex, 'uv': s1_uv, 'wrap': s1_wrap},
        }
        node_table.append(row)
    
    # Print detailed table for first 20
    print(f"\n  PER-NODE MATERIAL TABLE (first 20 of {len(node_table)} mesh nodes):")
    print(f"  {'─'*86}")
    
    for i, row in enumerate(node_table[:20]):
        print(f"\n  [{i+1:2d}] {row['name']}")
        print(f"      texture_1 (diffuse)  : {row['texture_1']!r}")
        print(f"      texture_2 (slot-2)   : {row['texture_2']!r}")
        print(f"      texture_names[]      : {row['texture_names']}")
        print(f"      tex_count            : {row['tex_count']}")
        print(f"      has_lightmap (raw PK): {row['has_lightmap_raw']}")
        print(f"      has_lightmap (GR)    : {row['has_lightmap_gr']}")
        print(f"      inferred slot-1 role : {row['slot1_role']}")
        print(f"      uvs count            : {row['n_uvs']}")
        print(f"      uvs_lm count         : {row['n_uvs_lm']}")
        print(f"      face count           : {row['n_faces']}")
        print(f"      unique face_mats     : {row['unique_face_mats']}")
        print(f"      face counts/slot     : {row['face_counts_per_slot']}")
        print(f"      pk raw face_mats     : {row['pk_raw_mats']}")
        print(f"      tvert != vertex-idx  : {row['tvert_diff']}")
        print(f"      render path          : {row['render_path']}")
        print(f"      sampler 0            : tex={row['s0']['tex']!r}  uv={row['s0']['uv']}  wrap={row['s0']['wrap']}")
        print(f"      sampler 1            : tex={row['s1']['tex']!r}  uv={row['s1']['uv']}  wrap={row['s1']['wrap']}")
    
    return model, node_table


# ─────────────────────────────────────────────────────────────────────────────
# Part 4: Render with GhostRigger GPU renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_with_textures(model, textures):
    """Render using GhostRigger's GPU renderer with real game textures."""
    print("\n" + "=" * 90)
    print("  PART 4: GPU render with real textures")
    print("=" * 90)
    
    try:
        from src.gui.gpu_renderer import render_model_autoframe
        views = ['diag', 'front', 'top']
        t0 = time.time()
        imgs = render_model_autoframe(model, W=1024, H=1024,
                                       textures=textures, views=views)
        t1 = time.time()
        print(f"  Render time: {t1-t0:.2f}s")
        for view, img in imgs.items():
            fname = f'real_m02aa_{view}.png'
            img.save(fname)
            sz = os.path.getsize(fname)
            print(f"  Saved {fname} ({img.size}, {sz:,} bytes)")
        return imgs
    except Exception as e:
        print(f"  Render FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Part 5: KotorInstallation texture resolution test
# ─────────────────────────────────────────────────────────────────────────────

def test_installation_texture_decode(install):
    """Test that textures loaded via KotorInstallation actually decode."""
    print("\n" + "=" * 90)
    print("  PART 5: KotorInstallation texture decode test")
    print("=" * 90)
    
    if install is None:
        print("  SKIPPED (no installation)")
        return {}
    
    all_names = [
        'lts_trim01', 'lts_pwall01i', 'lts_nwall04i', 'lts_lite08',
        'lts_bwall04i', 'lts_pwall04', 'lts_rwall01', 'lmi_bed01',
        'lts_nwall02', 'lts_gwall01', 'lts_bwall02i', 'lts_glass01', 'lts_nums',
        'm02aa_01a_lm0', 'm02aa_01a_lm1', 'm02aa_01a_lm2',
        'm02aa_01a_lm3', 'm02aa_01a_lm4', 'm02aa_01a_lm5',
    ]
    
    decoded = {}
    print(f"\n  {'Name':24s} {'Raw':>8s} {'Decode':>8s} {'Size':>12s} {'Status':>8s}")
    print(f"  {'─'*24} {'─'*8} {'─'*8} {'─'*12} {'─'*8}")
    
    for name in all_names:
        raw = install.get_texture(name)
        raw_sz = len(raw) if raw else 0
        if raw:
            img = decode_texture(raw, name)
            if img:
                decoded[name] = img
                print(f"  {name:24s} {raw_sz:>8d} {'OK':>8s} {str(img.size):>12s} {'✓':>8s}")
            else:
                print(f"  {name:24s} {raw_sz:>8d} {'FAIL':>8s} {'':>12s} {'✗':>8s}")
        else:
            print(f"  {name:24s} {'MISS':>8s} {'':>8s} {'':>12s} {'✗':>8s}")
    
    print(f"\n  Decoded via KotorInstallation: {len(decoded)}/{len(all_names)}")
    return decoded


# ─────────────────────────────────────────────────────────────────────────────
# Part 6: Identify the bug — compare KotorInstallation vs direct extraction
# ─────────────────────────────────────────────────────────────────────────────

def identify_bug(install, direct_textures, install_textures):
    """Identify why GhostRigger's live build shows wrong materials."""
    print("\n" + "=" * 90)
    print("  PART 6: BUG IDENTIFICATION — KotorInstallation vs Direct Extract")
    print("=" * 90)
    
    all_names = list(set(list(direct_textures.keys()) + list(install_textures.keys())))
    all_names.sort()
    
    bugs_found = []
    
    for name in all_names:
        direct = direct_textures.get(name)
        via_install = install_textures.get(name)
        
        d_ok = direct is not None
        i_ok = via_install is not None
        
        if d_ok and not i_ok:
            bugs_found.append(f"  BUG: '{name}' loads via direct extract ({direct.size}) but NOT via KotorInstallation")
        elif d_ok and i_ok:
            if direct.size != via_install.size:
                bugs_found.append(f"  DIFF: '{name}' size mismatch: direct={direct.size} vs install={via_install.size}")
        elif not d_ok and i_ok:
            bugs_found.append(f"  NOTE: '{name}' loads via KotorInstallation ({via_install.size}) but NOT via direct extract")
    
    if bugs_found:
        print(f"\n  Found {len(bugs_found)} issues:")
        for b in bugs_found:
            print(b)
    else:
        print("\n  No divergences found between direct and KotorInstallation paths.")
    
    # Now check specifically: what does KotorInstallation return for lightmaps?
    print("\n  Lightmap-specific analysis:")
    lm_names = ['m02aa_01a_lm0', 'm02aa_01a_lm1', 'm02aa_01a_lm2',
                 'm02aa_01a_lm3', 'm02aa_01a_lm4', 'm02aa_01a_lm5']
    
    if install:
        for name in lm_names:
            tpc = install.get(name, 3007)
            tga = install.get(name, 3)
            tex = install.get_texture(name)
            print(f"    {name}: TPC={len(tpc) if tpc else 0}  TGA={len(tga) if tga else 0}  "
                  f"get_texture={len(tex) if tex else 0} bytes  "
                  f"→ {'TPC wins' if (tpc and len(tpc) >= len(tga or b'')) else 'TGA wins' if tga else 'NONE'}")
    
    return bugs_found


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("  FULL DIAGNOSTIC: m02aa_01a (Taris Apartments) — GhostRigger Material Pipeline")
    print("  " + time.strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 90)
    
    # Part 1: Test KotorInstallation
    result = test_kotor_installation()
    install = result[0] if result else None
    
    # Part 2: Direct extract
    direct_textures = direct_extract_all()
    
    # Part 3: Load model + node table
    model, node_table = load_model_and_dump()
    
    # Part 4: Render with direct-extracted textures
    if model and direct_textures:
        render_with_textures(model, direct_textures)
    
    # Part 5: Test install texture decode
    install_textures = test_installation_texture_decode(install) if install else {}
    
    # Part 6: Bug identification
    bugs = identify_bug(install, direct_textures, install_textures)
    
    # Summary
    print("\n" + "=" * 90)
    print("  SUMMARY")
    print("=" * 90)
    print(f"  Direct-extracted textures: {len(direct_textures)}")
    print(f"  KotorInstall textures:     {len(install_textures)}")
    print(f"  Mesh nodes:                {len(node_table)}")
    print(f"  Bugs found:                {len(bugs)}")
    
    # Write node table to JSON for further analysis
    with open('node_table_m02aa.json', 'w') as f:
        json.dump(node_table, f, indent=2, default=str)
    print(f"  Node table saved to node_table_m02aa.json")


if __name__ == '__main__':
    main()
