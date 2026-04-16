#!/usr/bin/env python3
"""Phase D12-R — K2 Texture Availability Audit REOPENED (Full K2 Library).

This script:
1. Verifies the complete K2 library (chitin.key, BIFs, TexturePacks)
2. Audits K2 TexturePack ERF contents (TPA/TPB/TPC/GUI)
3. Re-runs texture resolution for c_zakkeg, c_hssiss, c_cannok
4. Renders K2 assets with full texture data
5. Confirms K1 regression suite (c_jawa, c_bantha, c_kraytdragon, n_commf, m02aa_01a)
6. Produces per-asset evidence and classification report

Outputs to screenshots/d12_reopened/
"""

import json
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.core.resource_manager import (
    ResourceManager, resolve_model_textures, audit_model_textures,
    RES_TPC, RES_TGA, RES_MDL, tpc_info, _identify_texture_source
)
from src.gui.gpu_renderer import GpuRenderer, render_model_autoframe

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Configuration ──────────────────────────────────────────────────────────
K1_DIR = 'game_data/swkotor'
K2_DIR = 'game_data/swkotor2/Knights of the Old Republic II'
OUT_DIR = 'screenshots/d12_reopened'

K2_ASSETS = ['c_zakkeg', 'c_hssiss', 'c_cannok', 'c_bantha', 'c_brith']
K1_ASSETS = ['c_jawa', 'c_bantha', 'c_kraytdragon', 'n_commf', 'm02aa_01a']


def verify_k2_library(k2_dir):
    """Verify K2 game library completeness."""
    result = {'chitin_key': False, 'bifs': {}, 'texturepacks': {}, 'issues': []}

    # Check chitin.key
    key_path = os.path.join(k2_dir, 'chitin.key')
    if os.path.isfile(key_path):
        result['chitin_key'] = True
        result['chitin_key_size'] = os.path.getsize(key_path)

        # Parse chitin.key BIF table
        with open(key_path, 'rb') as fh:
            raw = fh.read()
        bif_count = struct.unpack_from('<I', raw, 8)[0]
        key_count = struct.unpack_from('<I', raw, 12)[0]
        off_bifs = struct.unpack_from('<I', raw, 16)[0]
        result['bif_count_in_key'] = bif_count
        result['key_count'] = key_count

        for i in range(bif_count):
            base = off_bifs + i * 12
            name_off = struct.unpack_from('<I', raw, base + 4)[0]
            name_sz = struct.unpack_from('<H', raw, base + 8)[0]
            raw_name = raw[name_off:name_off + name_sz].split(b'\x00', 1)[0]
            name_str = raw_name.decode('ascii', 'replace').replace('\\', '/')
            bif_path = os.path.join(k2_dir, name_str)
            exists = os.path.isfile(bif_path)
            if not exists:
                # Case-insensitive check
                parent = os.path.dirname(bif_path)
                basename = os.path.basename(bif_path)
                if os.path.isdir(parent):
                    for f in os.listdir(parent):
                        if f.lower() == basename.lower():
                            exists = True
                            bif_path = os.path.join(parent, f)
                            break
            result['bifs'][name_str] = {
                'index': i,
                'exists': exists,
                'size': os.path.getsize(bif_path) if exists else 0
            }
    else:
        result['issues'].append('chitin.key not found')

    # Check TexturePacks
    tp_dir = os.path.join(k2_dir, 'TexturePacks')
    if not os.path.isdir(tp_dir):
        # Case-insensitive
        for d in os.listdir(k2_dir):
            if d.lower() == 'texturepacks' and os.path.isdir(os.path.join(k2_dir, d)):
                tp_dir = os.path.join(k2_dir, d)
                break
    if os.path.isdir(tp_dir):
        result['texturepacks_dir'] = True
        for fname in sorted(os.listdir(tp_dir)):
            if fname.lower().endswith('.erf'):
                fpath = os.path.join(tp_dir, fname)
                result['texturepacks'][fname] = os.path.getsize(fpath)
    else:
        result['texturepacks_dir'] = False
        result['issues'].append('TexturePacks/ directory not found')

    return result


def audit_texturepack_contents(rm):
    """Audit K2 TexturePack ERF contents."""
    k2 = rm.get_k2()
    if not k2:
        return {}
    result = {}
    for erf in k2._tex_erfs:
        name = os.path.basename(erf.path)
        total = len(erf._index)
        tpc = sum(1 for k in erf._index if k.endswith(':3007'))
        tga = sum(1 for k in erf._index if k.endswith(':3'))
        result[name] = {'total': total, 'tpc': tpc, 'tga': tga}
    return result


def render_asset(name, game, rm, renderer, out_dir):
    """Render asset and return status dict."""
    t0 = time.perf_counter()
    asset_dir = os.path.join(out_dir, f'{game}_{name}')
    os.makedirs(asset_dir, exist_ok=True)

    result = {
        'asset': name, 'game': game, 'status': 'FAIL',
        'textures_found': 0, 'textures_missing': 0,
        'texture_details': {}, 'missing_list': [],
        'mesh_count': 0, 'renders': [], 'reason': '',
    }

    model = rm.load_model(name, game)
    if model is None:
        result['reason'] = 'model_not_found'
        return result

    audit = audit_model_textures(model, rm, game)
    result['mesh_count'] = audit['mesh_count']
    result['textures_found'] = audit['textures_found_count']
    result['textures_missing'] = audit['textures_missing_count']
    result['texture_details'] = audit['textures_found']
    result['missing_list'] = audit['textures_missing']
    result['textures_expected'] = audit['textures_expected']

    textures = resolve_model_textures(model, rm, game)

    try:
        views = render_model_autoframe(
            model, W=512, H=512, textures=textures,
            views=['front', 'diag'], renderer=renderer
        )
        for view_name, img in views.items():
            path = os.path.join(asset_dir, f'{view_name}.png')
            img.save(path)
            result['renders'].append(view_name)
    except Exception as e:
        result['reason'] = f'render_error: {e}'

    if result['textures_missing'] > 0:
        result['status'] = 'PARTIAL'
        result['reason'] = f'{result["textures_missing"]} textures missing'
    elif len(result['renders']) >= 1:
        result['status'] = 'PASS'
        result['reason'] = 'all textures found, renders OK'
    else:
        result['reason'] = result.get('reason') or 'no renders produced'

    result['time_ms'] = round((time.perf_counter() - t0) * 1000)

    # Save per-asset audit
    with open(os.path.join(asset_dir, 'texture_audit.json'), 'w') as f:
        json.dump(audit, f, indent=2, default=str)

    return result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {'phase': 'D12-R', 'date': '2026-04-16', 'assets': {}}

    print("=" * 70)
    print("Phase D12-R: K2 Texture Availability Audit REOPENED")
    print("=" * 70)

    # Step 1: Verify library
    print("\n--- Step 1: Verify K2 Library ---")
    lib = verify_k2_library(K2_DIR)
    report['k2_library'] = lib
    bifs_found = sum(1 for v in lib['bifs'].values() if v['exists'])
    bifs_total = len(lib['bifs'])
    tpacks = len(lib['texturepacks'])
    print(f"  chitin.key: {'PRESENT' if lib['chitin_key'] else 'MISSING'}")
    print(f"  BIF files: {bifs_found}/{bifs_total} present")
    for name, info in lib['bifs'].items():
        status = 'PRESENT' if info['exists'] else 'MISSING'
        print(f"    [{info['index']}] {name}: {status} ({info['size']:,} bytes)")
    print(f"  TexturePacks: {tpacks} ERFs")
    for name, size in lib['texturepacks'].items():
        print(f"    {name}: {size:,} bytes")

    with open(os.path.join(OUT_DIR, 'k2_library_verification.json'), 'w') as f:
        json.dump(lib, f, indent=2, default=str)

    # Step 2: Setup ResourceManager
    print("\n--- Step 2: Setup ResourceManager ---")
    rm = ResourceManager()
    rm.set_k1_dir(K1_DIR)
    rm.set_k2_dir(K2_DIR)
    stats = rm.stats()
    print(f"  K1: {stats['K1']}")
    print(f"  K2: {stats['K2']}")
    report['rm_stats'] = stats

    # Step 3: TexturePack audit
    print("\n--- Step 3: K2 TexturePack Audit ---")
    tp_audit = audit_texturepack_contents(rm)
    report['texturepack_audit'] = tp_audit
    for name, info in tp_audit.items():
        print(f"  {name}: {info['total']} total, {info['tpc']} TPC, {info['tga']} TGA")

    # Step 4: Target texture resolution
    print("\n--- Step 4: Target Texture Resolution ---")
    targets = ['c_zakkeg', 'c_zakkeg01', 'c_hssiss', 'c_hssiss01',
               'c_cannok', 'c_cannok01', 'c_cann01',
               'c_bantha01', 'c_banthh01', 'c_brith01']
    tex_resolution = {}
    for tex in targets:
        data = rm.get_texture(tex, 'K2')
        source = _identify_texture_source(tex, rm, 'K2') if data else 'NOT_FOUND'
        tex_resolution[tex] = {
            'found': data is not None,
            'size': len(data) if data else 0,
            'source': source,
        }
        status_str = f"{len(data):,} bytes from {source}" if data else "NOT_FOUND"
        print(f"  {tex:20s}: {status_str}")
    report['texture_resolution'] = tex_resolution

    # Step 5: K2 live renders
    print("\n--- Step 5: K2 Live Validation ---")
    renderer = GpuRenderer()
    for name in K2_ASSETS:
        result = render_asset(name, 'K2', rm, renderer, OUT_DIR)
        report['assets'][f'K2_{name}'] = result
        ch = '✓' if result['status'] == 'PASS' else ('◐' if result['status'] == 'PARTIAL' else '✗')
        tx = f"{result['textures_found']}/{result['textures_found']+result['textures_missing']}"
        print(f"  [{result['game']}] {name}: {ch} {result['status']} — tex={tx}")

    # Step 6: K1 regression
    print("\n--- Step 6: K1 Regression ---")
    for name in K1_ASSETS:
        result = render_asset(name, 'K1', rm, renderer, OUT_DIR)
        report['assets'][f'K1_{name}'] = result
        ch = '✓' if result['status'] == 'PASS' else ('◐' if result['status'] == 'PARTIAL' else '✗')
        tx = f"{result['textures_found']}/{result['textures_found']+result['textures_missing']}"
        print(f"  [{result['game']}] {name}: {ch} {result['status']} — tex={tx}")

    # Summary
    k2_p = sum(1 for k, v in report['assets'].items() if k.startswith('K2_') and v['status'] == 'PASS')
    k2_t = sum(1 for k, v in report['assets'].items() if k.startswith('K2_') and v['status'] == 'PARTIAL')
    k2_f = sum(1 for k, v in report['assets'].items() if k.startswith('K2_') and v['status'] == 'FAIL')
    k1_p = sum(1 for k, v in report['assets'].items() if k.startswith('K1_') and v['status'] == 'PASS')
    k1_t = sum(1 for k, v in report['assets'].items() if k.startswith('K1_') and v['status'] == 'PARTIAL')
    k1_f = sum(1 for k, v in report['assets'].items() if k.startswith('K1_') and v['status'] == 'FAIL')

    report['summary'] = {
        'k2_pass': k2_p, 'k2_partial': k2_t, 'k2_fail': k2_f,
        'k1_pass': k1_p, 'k1_partial': k1_t, 'k1_fail': k1_f,
        'total_pass': k2_p + k1_p,
        'total_partial': k2_t + k1_t,
        'total_fail': k2_f + k1_f,
        'overall': 'PASS' if k2_f == 0 and k1_f == 0 else 'FAIL',
    }

    print("\n" + "=" * 70)
    print(f"K2: {k2_p} PASS, {k2_t} PARTIAL, {k2_f} FAIL (of {len(K2_ASSETS)})")
    print(f"K1: {k1_p} PASS, {k1_t} PARTIAL, {k1_f} FAIL (of {len(K1_ASSETS)})")
    print(f"Overall: {report['summary']['overall']}")
    print("=" * 70)

    # Write report
    report_path = os.path.join(OUT_DIR, 'phase_d12_reopened_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport: {report_path}")

    # Create composite
    if HAS_PIL:
        create_composite(OUT_DIR, K2_ASSETS, K1_ASSETS)


def create_composite(out_dir, k2_names, k1_names):
    """Create composite verification image."""
    TILE = 256
    cols = max(len(k2_names), len(k1_names))
    W = cols * TILE
    H = 2 * TILE + 50
    canvas = Image.new('RGBA', (W, H), (30, 30, 30, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((W // 2 - 80, 2), "D12-R Composite (Full K2 Library)", fill='white')
    draw.text((10, 20), "K2 (TexturePacks loaded):", fill=(100, 255, 100))
    draw.text((10, H // 2 + 10), "K1 (regression locked):", fill=(100, 200, 255))

    for i, name in enumerate(k2_names):
        path = os.path.join(out_dir, f'K2_{name}', 'front.png')
        if os.path.exists(path):
            img = Image.open(path).resize((TILE, TILE))
            canvas.paste(img, (i * TILE, 35))
        draw.text((i * TILE + 5, 35 + TILE - 15), name, fill='white')

    for i, name in enumerate(k1_names):
        path = os.path.join(out_dir, f'K1_{name}', 'front.png')
        if os.path.exists(path):
            img = Image.open(path).resize((TILE, TILE))
            canvas.paste(img, (i * TILE, TILE + 45))
        draw.text((i * TILE + 5, TILE + 45 + TILE - 15), name, fill='white')

    out = os.path.join(out_dir, 'composite_d12_reopened.png')
    canvas.save(out)
    print(f"Composite: {out}")


if __name__ == '__main__':
    main()
