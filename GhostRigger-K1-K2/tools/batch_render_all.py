#!/usr/bin/env python3
"""
GhostRigger Batch Render & Audit v2.0
======================================
Renders every KotOR 1 & 2 model (all 5,764) to PNG thumbnails and produces
a comprehensive audit report.

Usage:
  # Full run (all 5764 models, renders)
  python3 tools/batch_render_all.py

  # No-render structural audit only (fast, ~60s)
  python3 tools/batch_render_all.py --no-render

  # Specific category
  python3 tools/batch_render_all.py --category creatures

  # Single model
  python3 tools/batch_render_all.py --filter c_bantha

  # K1 only
  python3 tools/batch_render_all.py --game K1

  # Cap number
  python3 tools/batch_render_all.py --max 200

  # Render size (default 256)
  python3 tools/batch_render_all.py --render-size 128
"""

import sys, os, json, time, math, re, argparse, traceback, gc
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import GameLibrary, RES_MDL, RES_MDX, RES_TPC, RES_TGA
from src.core.mdl_parser import MDLBinaryParser

K1_DIR  = "game_data/k1_extracted"
K2_DIR  = "game_data/k2_extracted"
OUT_DIR = Path("audit_output/batch_render")

UV_ATLAS_WARN  = 20.0
UV_ATLAS_ERROR = 100.0
UV_CORRUPT     = 1e10

WALKMESH_RE     = re.compile(r'^(walk|WALK|wm_|Walkmesh)', re.IGNORECASE)
SKIN_SEGMENT_RE = re.compile(
    r'(_(g|geo|Geo)\d*$|_g\d+$|pelvis|lshin|rshin|lfoot|rfoot|lthigh|rthigh'
    r'|torso|Torso|chest|Chest|larm|rarm|LArm|RArm|forearm|bicep|Forearm)',
    re.IGNORECASE
)


def categorize(resref):
    """Map a model resref to one of the standard batch-render categories.

    K1 modules start with 'm' followed by a 2-digit area code (e.g. m12aa, m26mg).
    K2 modules use a 3-digit numeric area code followed by a location abbreviation
    (e.g. 101per, 211tel, 510ond, 371nar, 003ebo).  Both are mapped to 'modules'.
    """
    r = resref.lower()
    if r.startswith('c_'):             return 'creatures'
    if r.startswith('n_'):             return 'npcs'
    if r.startswith('plc_'):           return 'placeables'
    if r.startswith(('door', 'dor_')): return 'doors'
    if r.startswith('w_'):             return 'weapons'
    if r.startswith(('i_', 'item_')):  return 'items'
    if r.startswith(('p_', 'pmb', 'pmf', 'pmh', 'pmc', 'po_',
                      'pfb', 'pfh', 'pff', 'pfc')): return 'pc_models'
    if r.startswith(('s_male', 's_female', 's_human')): return 'supermodels'
    if r.startswith('v_'):             return 'vfx'
    # K1 modules: m + 2-digit area code (m12aa, m26mg, m03mg…)
    if r.startswith('m') and len(r) >= 4 and r[1:3].isdigit():
        return 'modules'
    # K2 modules: 3-digit area code + location abbreviation (101per, 211tel, 003ebo…)
    if len(r) >= 5 and r[:3].isdigit() and r[3:5].isalpha():
        return 'modules'
    # K1 module area prefixes not starting with m
    if r.startswith(('lev_', 'kas_', 'dan_', 'tat_', 'kor_', 'man_',
                     'bek_', 'und_', 'endar', 'fsh_', 'sth_', 'ebk_',
                     'pol_', 'per_')):
        return 'modules'
    return 'other'


RENDER_PRIORITY = {
    'creatures': 0, 'npcs': 1, 'pc_models': 2, 'supermodels': 3,
    'placeables': 4, 'doors': 5, 'weapons': 6, 'items': 7,
    'vfx': 8, 'modules': 9, 'other': 10,
}


def classify_uv(name, is_skin, umax, vmax):
    mx = max(umax, vmax)
    if mx > UV_CORRUPT:             return 'CORRUPT_UV'
    if WALKMESH_RE.match(name):     return None
    if is_skin and SKIN_SEGMENT_RE.search(name): return None
    if mx <= UV_ATLAS_WARN:         return None
    if mx <= UV_ATLAS_ERROR:        return 'WARN_ATLAS'
    return 'ERROR_UV'


def iter_nodes(root):
    if root is None:
        return
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        for c in getattr(n, 'children', []):
            stack.append(c)


def audit_model_struct(resref, game, mdl_bytes, mdx_bytes):
    import numpy as np
    result = {
        'resref': resref, 'game': game, 'category': categorize(resref),
        'parse_ok': False, 'parse_error': None, 'health': 'FAIL',
        'node_count': 0, 'mesh_count': 0, 'skin_count': 0, 'tri_count': 0,
        'zero_vert': [], 'dup_names': [], 'uv_issues': [], 'geo_issues': [],
        'textures': [], 'supermodel': '', 'txi_nodes': 0,
    }
    try:
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        model  = parser.parse()
    except Exception as e:
        result['parse_error'] = str(e)[:200]
        return result

    result['parse_ok'] = True
    result['supermodel'] = (getattr(model, 'supermodel', '') or '').strip()
    names = []
    for node in iter_nodes(getattr(model, 'root_node', None)):
        nname = getattr(node, 'name', '') or ''
        names.append(nname)
        result['node_count'] += 1
        flags   = getattr(node, 'flags', 0)
        is_mesh = bool(flags & 0x0020)
        is_skin = bool(flags & 0x0040)
        if not (is_mesh or is_skin):
            continue
        verts = getattr(node, 'vertices', getattr(node, 'verts', []))
        faces = getattr(node, 'faces', [])
        uvs   = getattr(node, 'uvs', [])
        if is_skin: result['skin_count'] += 1
        result['mesh_count'] += 1
        result['tri_count']  += len(faces)
        if len(verts) == 0:
            result['zero_vert'].append(nname)
        tex = getattr(node, 'bitmap', getattr(node, 'texture', '')) or ''
        if tex:
            result['textures'].append(tex.lower())
        blend = int(getattr(node, 'txi_blending', getattr(node, 'txi_blend', 0)))
        alpha = float(getattr(node, 'txi_alpha_test', 0.0))
        if blend or alpha > 0:
            result['txi_nodes'] += 1
        if uvs:
            try:
                uv_arr = np.array(uvs, dtype=np.float32)
                umax   = float(np.nanmax(np.abs(uv_arr[:, 0])))
                vmax   = float(np.nanmax(np.abs(uv_arr[:, 1])))
                issue  = classify_uv(nname, is_skin, umax, vmax)
                if issue:
                    result['uv_issues'].append({
                        'node': nname, 'type': issue,
                        'umax': round(umax, 2), 'vmax': round(vmax, 2),
                        'is_skin': is_skin,
                    })
            except Exception:
                pass

    result['textures'] = sorted(set(result['textures']))
    nc = Counter(names)
    result['dup_names'] = [n for n, c in nc.items() if c > 1]
    has_corrupt = any(i['type'] == 'CORRUPT_UV' for i in result['uv_issues'])
    has_error   = any(i['type'] == 'ERROR_UV'   for i in result['uv_issues'])
    if result['parse_error']:
        result['health'] = 'FAIL'
    elif has_corrupt or has_error or result['zero_vert']:
        result['health'] = 'WARN'
    else:
        result['health'] = 'OK'
    return result


def load_tex_pil(raw):
    if not raw:
        return None
    try:
        from src.gui.viewport import _load_tpc_bytes, _is_tpc_data
        if _is_tpc_data(raw):
            return _load_tpc_bytes(raw)
    except Exception:
        pass
    try:
        import io
        from PIL import Image
        return Image.open(io.BytesIO(raw)).convert('RGBA')
    except Exception:
        pass
    return None


def build_tex_cache(lib, textures, game, max_tex=8):
    cache = {}
    for tname in textures[:max_tex]:
        if not tname:
            continue
        try:
            raw = lib.get_texture_data(tname, game)
            if raw:
                img = load_tex_pil(raw)
                if img:
                    cache[tname.lower()] = img
        except Exception:
            pass
    return cache


_renderer = None

def get_renderer():
    global _renderer
    if _renderer is None:
        try:
            from src.gui.gpu_renderer import GpuRenderer
            _renderer = GpuRenderer()
        except Exception as e:
            print(f"  [WARN] GpuRenderer init: {e}")
    return _renderer


def reset_renderer():
    """Free GPU renderer and collected memory."""
    global _renderer
    _renderer = None
    gc.collect()


def flush_gpu_cache():
    """Clear GPU mesh + texture cache and run GC to free memory between batches."""
    global _renderer
    if _renderer is not None:
        try:
            # Clear mesh cache
            if hasattr(_renderer, '_mesh_cache'):
                for mesh in list(_renderer._mesh_cache.values()):
                    try: mesh.release()
                    except Exception: pass
                _renderer._mesh_cache.clear()
            # Clear texture cache
            if hasattr(_renderer, '_tex_cache') and _renderer._tex_cache is not None:
                try: _renderer._tex_cache.clear()
                except Exception: pass
            # Clear world-transform cache
            if hasattr(_renderer, '_wt_cache'):
                _renderer._wt_cache.clear()
        except Exception:
            pass
    gc.collect()


def try_render(resref, game, mdl_bytes, mdx_bytes, tex_cache, size=256, views=None):
    if views is None:
        views = ['front', 'back']
    try:
        from src.gui.gpu_renderer import render_model_autoframe
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        model  = parser.parse()
        rend   = get_renderer()
        return render_model_autoframe(
            model, W=size, H=size,
            textures=tex_cache, views=views, renderer=rend,
        ) or None
    except Exception:
        return None


def score_image(img):
    """Score a rendered image for non-background coverage and artifact pixels.

    Background detection uses the renderer's actual background color (18, 18, 40)
    with a small tolerance to capture anti-aliased edge pixels.

    Artifact detection uses tight criteria AND excludes 2-pixel edge zones:
      yellow_artifact : near-pure #FFFF00 yellow (R>220, G>210, B<40, |R-G|<20)
                        Grenades and force-field placeables can legitimately be this
                        colour; only flag interior pixels (not silhouette edges).
      pink_artifact   : near-pure magenta (R>220, G<40, B>220)
                        MSAA/sub-pixel fringe at geometry edges naturally produces
                        these values when a bright model meets the dark background.
                        Only flag pixels that are NOT adjacent to background (interior
                        magenta blobs = real shader bugs, not edge AA).

    Edge exclusion: pixels within 2px of background are silhouette edges and are
    excluded from artifact counting to prevent MSAA fringe false positives.
    """
    try:
        import numpy as np
        try:
            from scipy.ndimage import binary_dilation
            _have_scipy = True
        except ImportError:
            _have_scipy = False

        arr   = np.array(img.convert('RGB'), dtype=np.uint8)
        h, w  = arr.shape[:2]
        total = h * w
        # BG detection: renderer clears to (18,18,40); accept ±10 tolerance
        bg = ((arr[:,:,0] < 28) & (arr[:,:,1] < 28) & (arr[:,:,2] < 55) &
              (arr[:,:,2].astype(np.int16) > arr[:,:,0].astype(np.int16) - 5))
        non_bg = int((~bg).sum())

        # Edge zone: pixels within 2 pixels of background (silhouette edges)
        if _have_scipy:
            bg_dilated  = binary_dilation(bg, iterations=2)
            edge_zone   = bg_dilated & ~bg     # model pixels adjacent to BG
        else:
            edge_zone = np.zeros_like(bg)      # fallback: no edge exclusion

        r = arr[:,:,0].astype(np.int16)
        g = arr[:,:,1].astype(np.int16)
        b = arr[:,:,2].astype(np.int16)
        # Interior pixels only (exclude silhouette edges)
        interior = ~bg & ~edge_zone

        # True yellow ARTIFACT: near-pure #FFFF00 (R>220, G>210, B<40, |R-G|<20)
        # Interior only to exclude grenade muzzle-flash edge fringe.
        yellow = (r > 220) & (g > 210) & (b < 40) & (np.abs(r - g) < 20) & interior
        # True magenta ARTIFACT: near-pure #FF00FF (R>220, G<40, B>220), interior only.
        # All MSAA edge fringes are excluded; remaining magenta = real shader bugs.
        pink   = (r > 220) & (g < 40) & (b > 220) & interior

        return {'non_bg': non_bg, 'non_bg_frac': round(non_bg/max(total,1), 3),
                'yellow': int(yellow.sum()), 'pink': int(pink.sum())}
    except Exception:
        return {'non_bg': 0, 'non_bg_frac': 0.0, 'yellow': 0, 'pink': 0}


def save_contact_sheet(items, out_path, thumb=64, cols=20):
    try:
        from PIL import Image, ImageDraw
        if not items:
            return
        rows = math.ceil(len(items) / cols)
        sheet = Image.new('RGB', (cols*thumb, rows*(thumb+14)), (20,20,20))
        draw  = ImageDraw.Draw(sheet)
        for i, (label, img) in enumerate(items):
            x = (i % cols) * thumb
            y = (i // cols) * (thumb + 14)
            if img is not None:
                th = img.convert('RGB').resize((thumb,thumb), Image.LANCZOS)
                sheet.paste(th, (x, y))
            draw.text((x+2, y+thumb+1), label[:12], fill=(200,200,200))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(str(out_path))
    except Exception as e:
        print(f"  [WARN] sheet failed: {e}")


def run(args):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renders_dir = OUT_DIR / 'renders'
    sheets_dir  = OUT_DIR / 'sheets'
    if not args.no_render:
        renders_dir.mkdir(parents=True, exist_ok=True)
        sheets_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("GhostRigger Batch Render & Audit v2.0")
    print("=" * 70)

    lib = GameLibrary()
    k1_dir = args.k1 or K1_DIR
    k2_dir = args.k2 or K2_DIR
    if args.game in ('K1', 'both') and os.path.isdir(k1_dir):
        lib.set_k1_dir(k1_dir)
        print(f"K1: {k1_dir}")
    if args.game in ('K2', 'both') and os.path.isdir(k2_dir):
        lib.set_k2_dir(k2_dir)
        print(f"K2: {k2_dir}")

    lib.scan()
    all_models = lib.models[:]
    print(f"Total models: {len(all_models)}")

    if args.filter:
        all_models = [m for m in all_models if args.filter.lower() in m.resref.lower()]
        print(f"Filter '{args.filter}': {len(all_models)}")
    if args.category:
        all_models = [m for m in all_models if categorize(m.resref) == args.category]
        print(f"Category '{args.category}': {len(all_models)}")

    all_models.sort(key=lambda m: RENDER_PRIORITY.get(categorize(m.resref), 10))
    if args.max and len(all_models) > args.max:
        all_models = all_models[:args.max]
        print(f"Capped at {args.max}")

    # Resume: skip models whose front-view render already exists
    if not args.no_render:
        skip_set = set()
        renders_dir_check = OUT_DIR / 'renders'
        if renders_dir_check.exists():
            for f in renders_dir_check.iterdir():
                if f.name.endswith('_front.png'):
                    # filename format: {GAME}_{resref}_front.png
                    # e.g. K1_c_bantha_front.png → game=K1, resref=c_bantha
                    name = f.name[:-len('_front.png')]   # strip _front.png → K1_c_bantha
                    if name.startswith('K1_'):
                        skip_set.add(('K1', name[3:]))
                    elif name.startswith('K2_'):
                        skip_set.add(('K2', name[3:]))
        if skip_set:
            before = len(all_models)
            all_models = [m for m in all_models
                          if (m.game, m.resref) not in skip_set]
            print(f"Resume: skipping {before - len(all_models)} already rendered, {len(all_models)} remaining")

    print(f"\nAuditing {len(all_models)} models...\n")

    results  = []
    issues   = []
    cat_stats = defaultdict(lambda: {
        'total':0,'ok':0,'warn':0,'fail':0,'tri_count':0,
        'render_ok':0,'render_fail':0,'yellow_total':0,'pink_total':0,
    })
    sheet_images = defaultdict(list)
    total_start = time.time()
    rsize = args.render_size

    # Memory management: reinitialise renderer every N models to prevent GPU
    # memory accumulation from texture caches and mesh buffers.
    # With 987MB RAM limit, a fresh renderer + textures costs ~80MB; we flush
    # every 150 models so peak usage stays under ~350MB.
    RENDERER_RESET_INTERVAL = 150

    for idx, entry in enumerate(all_models):
        # Periodic GPU cache flush + GC to stay within 987MB RAM limit
        if idx > 0 and idx % RENDERER_RESET_INTERVAL == 0:
            flush_gpu_cache()
            print(f"  [MEM] Flushed GPU cache at model {idx}", flush=True)

        resref = entry.resref
        game   = entry.game
        cat    = categorize(resref)
        t0     = time.time()

        if idx % 50 == 0:
            el  = time.time() - total_start
            pct = 100.0 * idx / max(len(all_models), 1)
            eta = (el / max(idx,1)) * (len(all_models) - idx)
            print(f"  [{idx:5d}/{len(all_models)}] {pct:5.1f}%  {resref:<28} ({game})"
                  f"  el={el:5.0f}s  ETA={eta:5.0f}s", flush=True)

        # Periodic renderer reset to free GPU texture cache + mesh buffer memory
        if not args.no_render and idx > 0 and idx % RENDERER_RESET_INTERVAL == 0:
            reset_renderer()
            print(f"  [mem-flush at idx={idx}]", flush=True)

        try:
            mdl_bytes, mdx_bytes = lib.get_model_data(entry)
            if not mdl_bytes:
                raise ValueError("MDL empty")
            mdx_bytes = mdx_bytes or b''
        except Exception as e:
            r = {'resref':resref,'game':game,'category':cat,
                 'parse_ok':False,'parse_error':f'load:{e}',
                 'health':'FAIL','tri_count':0}
            results.append(r); issues.append(r)
            cat_stats[cat]['fail'] += 1
            cat_stats[cat]['total'] += 1
            continue

        r = audit_model_struct(resref, game, mdl_bytes, mdx_bytes)
        r['audit_ms'] = round((time.time()-t0)*1000,1)
        r['render_ok'] = False
        r['render_scores'] = {}
        r['render_error'] = None

        do_render = (not args.no_render and r['parse_ok'] and r['mesh_count'] > 0)
        if do_render:
            try:
                tc = build_tex_cache(lib, r.get('textures',[]), game)
                vlist = ['front','back'] if cat not in ('modules','other','vfx') else ['front']
                vo = try_render(resref, game, mdl_bytes, mdx_bytes, tc, rsize, vlist)
                if vo:
                    r['render_ok'] = True
                    cat_stats[cat]['render_ok'] += 1
                    front_img = None
                    for vname, img in vo.items():
                        sc = score_image(img)
                        r['render_scores'][vname] = sc
                        cat_stats[cat]['yellow_total'] += sc.get('yellow',0)
                        cat_stats[cat]['pink_total']   += sc.get('pink',0)
                        try:
                            img.save(str(renders_dir / f"{game}_{resref}_{vname}.png"))
                        except Exception:
                            pass
                        if vname == 'front':
                            front_img = img
                    sheet_images[cat].append((resref[:12], front_img))
                else:
                    cat_stats[cat]['render_fail'] += 1
                    r['render_error'] = 'none_returned'
                # Free PIL images and clear GPU caches to prevent OOM
                del tc
                rend = get_renderer()
                if rend is not None and hasattr(rend, 'clear_caches'):
                    rend.clear_caches()
            except Exception as e:
                cat_stats[cat]['render_fail'] += 1
                r['render_error'] = str(e)[:120]

        results.append(r)
        cat_stats[cat]['total'] += 1
        cat_stats[cat]['tri_count'] += r.get('tri_count',0)
        if r['health'] == 'OK':
            cat_stats[cat]['ok'] += 1
        elif r['health'] == 'WARN':
            cat_stats[cat]['warn'] += 1; issues.append(r)
        else:
            cat_stats[cat]['fail'] += 1; issues.append(r)

        # Checkpoint save every 200 models
        if (idx + 1) % 200 == 0:
            result_stem_cp = args.category if args.category else 'full'
            with open(OUT_DIR/f'results_{result_stem_cp}.json','w') as f:
                json.dump(results, f, indent=2, default=str)
            with open(OUT_DIR/f'issues_{result_stem_cp}.json','w') as f:
                json.dump(issues, f, indent=2, default=str)
            print(f"  [checkpoint saved: {idx+1} models]", flush=True)
        
        # Periodic memory cleanup
        if (idx + 1) % 50 == 0:
            gc.collect()

    elapsed = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"Complete: {len(results)} models in {elapsed:.1f}s")

    if not args.no_render:
        print("Building contact sheets...")
        for cat, items in sheet_images.items():
            if items:
                p = sheets_dir / f"{cat}.png"
                save_contact_sheet(items, p)
                print(f"  {p}  ({len(items)} models)")

    # Choose output filename: per-category or full
    result_stem = args.category if args.category else 'full'
    result_path = OUT_DIR / f'results_{result_stem}.json'
    issues_path = OUT_DIR / f'issues_{result_stem}.json'

    with open(result_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    with open(issues_path, 'w') as f:
        json.dump(issues, f, indent=2, default=str)
    print(f"Results: {result_path}")
    print(f"Issues ({len(issues)}): {issues_path}")

    lines = []
    lines.append("=" * 70)
    lines.append("GhostRigger Batch Render & Audit v2.0")
    lines.append(f"Date : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Models : {len(results)}  Time : {elapsed:.1f}s  ({elapsed/max(len(results),1)*1000:.1f} ms/model)")
    lines.append("=" * 70)
    lines.append("")

    total_ok   = sum(1 for r in results if r.get('health')=='OK')
    total_warn = sum(1 for r in results if r.get('health')=='WARN')
    total_fail = sum(1 for r in results if r.get('health')=='FAIL')
    total_tris = sum(r.get('tri_count',0) for r in results)
    total_rend = sum(1 for r in results if r.get('render_ok'))
    lines.append(f"Overall : OK={total_ok}  WARN={total_warn}  FAIL={total_fail}")
    lines.append(f"Triangles total : {total_tris:,}")
    lines.append(f"Models rendered : {total_rend}")
    lines.append("")

    hdr = f"{'Category':<16} {'Total':>6} {'OK':>6} {'WARN':>6} {'FAIL':>6} {'Tris':>10} {'Rendered':>9} {'Yellow':>8} {'Pink':>8}"
    lines.append(hdr); lines.append("-"*len(hdr))
    for cat in sorted(cat_stats, key=lambda c: RENDER_PRIORITY.get(c,10)):
        s = cat_stats[cat]
        lines.append(f"{cat:<16} {s['total']:>6} {s['ok']:>6} {s['warn']:>6} {s['fail']:>6} "
                     f"{s['tri_count']:>10,} {s['render_ok']:>9} {s['yellow_total']:>8} {s['pink_total']:>8}")
    lines.append("")

    uv_types = Counter()
    for r in results:
        for ui in r.get('uv_issues',[]):
            uv_types[ui['type']] += 1
    if uv_types:
        lines.append("UV Issue Types:")
        for t,c in uv_types.most_common():
            lines.append(f"  {t}: {c}")
        lines.append("")

    error_models = [r for r in results
                    if any(ui['type']=='ERROR_UV' for ui in r.get('uv_issues',[]))]
    if error_models:
        lines.append(f"Models with ERROR_UV ({len(error_models)}):")
        for r in sorted(error_models, key=lambda x: max(
            (max(ui['umax'],ui['vmax']) for ui in x.get('uv_issues',[])), default=0
        ), reverse=True)[:30]:
            iss = '; '.join(f"{ui['node']}(U={ui['umax']},V={ui['vmax']})"
                            for ui in r.get('uv_issues',[]) if ui['type']=='ERROR_UV')
            lines.append(f"  {r['game']} {r['resref']}: {iss}")
        lines.append("")

    corrupt = [r for r in results
               if any(ui['type']=='CORRUPT_UV' for ui in r.get('uv_issues',[]))]
    if corrupt:
        lines.append(f"Models with CORRUPT_UV ({len(corrupt)}):")
        for r in corrupt[:20]:
            lines.append(f"  {r['game']} {r['resref']}")
        lines.append("")

    if total_rend:
        black = [r for r in results
                 if r.get('render_ok') and
                    all(v.get('non_bg_frac',1.0)<0.02
                        for v in r.get('render_scores',{}).values())]
        if black:
            lines.append(f"Black/Empty Renders ({len(black)}):")
            for r in black[:20]:
                lines.append(f"  {r['game']} {r['resref']}")
            lines.append("")
        hi_y = sorted(
            [(r, sum(v.get('yellow',0) for v in r.get('render_scores',{}).values()))
             for r in results if r.get('render_ok')],
            key=lambda x:-x[1]
        )
        hi_y = [(r,y) for r,y in hi_y if y>500]
        if hi_y:
            lines.append(f"High-Yellow Models (>{500}px, top 20):")
            for r,y in hi_y[:20]:
                lines.append(f"  {r['game']} {r['resref']}: {y} yellow px")
            lines.append("")

    summary = '\n'.join(lines)
    sf = OUT_DIR / f'summary_{result_stem}.txt'
    with open(sf,'w') as f:
        f.write(summary)
    print(f"Summary: {sf}\n")
    print(summary)


def main():
    ap = argparse.ArgumentParser(description='GhostRigger Batch Render & Audit v2.0')
    ap.add_argument('--k1',          default=None)
    ap.add_argument('--k2',          default=None)
    ap.add_argument('--game',        default='both', choices=['K1','K2','both'])
    ap.add_argument('--max',         default=None, type=int)
    ap.add_argument('--filter',      default=None)
    ap.add_argument('--category',    default=None,
                    choices=['creatures','npcs','pc_models','placeables',
                             'doors','weapons','items','vfx','modules',
                             'supermodels','other'])
    ap.add_argument('--no-render',   action='store_true')
    ap.add_argument('--render-size', default=256, type=int)
    ap.add_argument('--resume',      action='store_true',
                    help='Skip models whose renders already exist (auto-enabled when renders dir is non-empty)')
    args = ap.parse_args()
    run(args)


if __name__ == '__main__':
    main()
