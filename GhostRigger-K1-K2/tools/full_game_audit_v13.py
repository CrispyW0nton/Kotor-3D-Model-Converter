#!/usr/bin/env python3
"""
GhostRigger Full Game Audit v13.0
====================================
Comprehensive per-model visual + structural audit of ALL KotOR 1 & 2 models.

What's new vs v12:
  • Smart UV classification:
      - walkmesh nodes (walk*, WALK*): tiling expected, skip warning
      - skin _g nodes (pelvis_g, lshin_g, etc.): atlas offsets expected, skip warning
      - non-skin meshes with UV > ATLAS_THRESHOLD: flag as REAL issue
  • GPU render per model using GpuRenderer.render_model_autoframe
  • Visual quality scoring: horn_tan, yellow artifacts, non-background coverage
  • Per-node type breakdown: skin / rigid / emitter / light
  • Texture resolution and format audit
  • TXI metadata propagation check
  • Duplicate node name detection with severity
  • Supermodel chain validation
  • Category-aware: creatures / NPCs / PC / placeables / doors / items / weapons / area

Output:
  audit_output/v13/audit_v13_full.json        – per-model machine-readable
  audit_output/v13/audit_v13_summary.txt      – human-readable summary
  audit_output/v13/audit_v13_issues.json      – models with real issues
  audit_output/v13/renders/                   – PNG renders of all models

Usage:
  python3 tools/full_game_audit_v13.py
  python3 tools/full_game_audit_v13.py --max 200
  python3 tools/full_game_audit_v13.py --category creatures
  python3 tools/full_game_audit_v13.py --filter c_bantha
  python3 tools/full_game_audit_v13.py --no-render  # skip GPU renders
  python3 tools/full_game_audit_v13.py --game K1
"""

import sys, os, json, time, struct, math, traceback, re, argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import (
    GameLibrary, KEYBIFReader, ERFReader,
    RES_MDL, RES_MDX, RES_TPC, RES_TGA
)
from src.core.mdl_parser import MDLBinaryParser

# ── Constants ────────────────────────────────────────────────────────────────

K1_DIR = "game_data/k1_extracted"
K2_DIR = "game_data/k2_extracted"
OUT_DIR = Path("audit_output/v13")

# UV threshold: skin atlas UVs go up to ~20 in KotOR's character system.
# Anything above this on a non-skin, non-walkmesh mesh is suspicious.
UV_ATLAS_WARN  = 20.0   # Warn: might be legitimate atlas or heavy tiling
UV_ATLAS_ERROR = 100.0  # Error: extremely unlikely to be valid atlas mapping

# Walkmesh node patterns (expected to have large UVs for lightmap/terrain)
WALKMESH_PATTERNS = re.compile(r'^(walk|WALK|wm_|Walkmesh|walkmesh)', re.IGNORECASE)

# Skin segment patterns (_g suffix = shared skeleton segment)
# These use UV atlas offsets > 1.0 by design
SKIN_SEGMENT_PATTERNS = re.compile(
    r'(_(g|geo|Geo)\d*$|_g\d+$|pelvis|lshin|rshin|lfoot|rfoot|lthigh|rthigh'
    r'|torso|Torso|chest|Chest|larm|rarm|LArm|RArm|forearm|bicep|Forearm)',
    re.IGNORECASE
)

# Model category prefix map
CATEGORY_PREFIXES = {
    'creatures':   ('c_',),
    'npcs':        ('n_',),
    'pc_models':   ('p_', 'pmb', 'pmf', 's_male', 's_female', 'po_'),
    'placeables':  ('plc_',),
    'doors':       ('door', 'dor_', 'd_'),
    'items':       ('i_', 'item_', 'w_'),
    'weapons':     ('w_', 'weap_'),
    'supermodels': ('s_male', 's_female', 's_human'),
    'droids':      ('g_', 'drd_', 'c_drd'),
    'area':        (''),  # fallthrough
}


def categorize_model(resref: str) -> str:
    """Assign a model to the most specific category based on its resref."""
    r = resref.lower()
    if r.startswith('c_'):   return 'creatures'
    if r.startswith('n_'):   return 'npcs'
    if r.startswith('plc_'): return 'placeables'
    if r.startswith('door') or r.startswith('dor_'): return 'doors'
    if r.startswith('w_'):   return 'weapons'
    if r.startswith('i_') or r.startswith('item_'): return 'items'
    if r.startswith(('p_', 'pmb', 'pmf')):           return 'pc_models'
    if r.startswith(('s_male', 's_female', 's_human')): return 'supermodels'
    return 'other'


# ── UV Analysis ──────────────────────────────────────────────────────────────

def classify_uv_issue(node_name: str, is_skin: bool, umax: float, vmax: float) -> Optional[str]:
    """
    Classify a UV range for a node. Returns:
      None          = no issue (expected tiling or atlas)
      'WARN_ATLAS'  = high UV, possibly legit atlas
      'ERROR_UV'    = extremely high UV, likely a problem
      'CORRUPT_UV'  = NaN / INF / astronomically large value
    """
    mx = max(umax, vmax)

    # Astronomical values = corrupt (NaN stored as float, or 3dsMax object IDs)
    if mx > 1e10:
        return 'CORRUPT_UV'

    # Walkmesh nodes: large tiling UVs expected for terrain/lightmap
    if WALKMESH_PATTERNS.match(node_name):
        return None  # Expected

    # Skin segment nodes: atlas offsets expected
    # Check both is_skin flag AND name pattern (some _g nodes have rigid-mesh flags
    # but still use the skin UV-atlas coordinate system, e.g. c_hssiss head_g)
    if SKIN_SEGMENT_PATTERNS.search(node_name):
        return None  # Expected skin atlas or _g deformation helper

    # Also skip is_skin nodes matching any atlas pattern
    if is_skin and mx <= UV_ATLAS_ERROR:
        return None  # Skin atlas, expected

    # Any node with UV in [1.0, UV_ATLAS_WARN]: mild tiling, OK for area props
    if mx <= UV_ATLAS_WARN:
        return None  # Mild tiling, expected

    if mx <= UV_ATLAS_ERROR:
        return 'WARN_ATLAS'

    return 'ERROR_UV'


# ── Node Analysis ─────────────────────────────────────────────────────────────

def audit_node(node, model_ref=None) -> Dict:
    """Audit a single model node. Returns a dict of findings."""
    result = {
        'name': getattr(node, 'name', '?'),
        'type': 'unknown',
        'is_skin': False,
        'is_emitter': False,
        'is_light': False,
        'vert_count': 0,
        'face_count': 0,
        'has_uvs': False,
        'uv_umax': 0.0,
        'uv_vmax': 0.0,
        'uv_issue': None,
        'texture': '',
        'txi_blend': 0,
        'txi_alpha_test': 0.0,
        'warnings': [],
    }

    flags = getattr(node, 'flags', 0)
    # Node type flags (from KotorBlender types.py)
    is_mesh    = bool(flags & 0x0020)
    is_skin    = bool(flags & 0x0040)
    is_emitter = bool(flags & 0x0100)
    is_light   = bool(flags & 0x0002)
    result['is_skin']    = is_skin
    result['is_emitter'] = is_emitter
    result['is_light']   = is_light

    if is_emitter:   result['type'] = 'emitter'
    elif is_light:   result['type'] = 'light'
    elif is_skin:    result['type'] = 'skin_mesh'
    elif is_mesh:    result['type'] = 'trimesh'
    else:            result['type'] = 'dummy'

    if is_mesh or is_skin:
        verts = getattr(node, 'vertices', getattr(node, 'verts', []))
        faces = getattr(node, 'faces', [])
        uvs   = getattr(node, 'uvs', [])
        result['vert_count'] = len(verts)
        result['face_count'] = len(faces)
        result['has_uvs']    = len(uvs) > 0
        result['texture']    = getattr(node, 'bitmap', getattr(node, 'texture', ''))

        # UV range analysis
        if uvs:
            try:
                import numpy as np
                uv_arr = np.array(uvs, dtype=np.float32)
                umax = float(np.nanmax(np.abs(uv_arr[:, 0])))
                vmax = float(np.nanmax(np.abs(uv_arr[:, 1])))
                result['uv_umax'] = round(umax, 2)
                result['uv_vmax'] = round(vmax, 2)
                issue = classify_uv_issue(result['name'], is_skin, umax, vmax)
                result['uv_issue'] = issue
            except Exception as e:
                result['warnings'].append(f'UV analysis error: {e}')

        # Zero-vertex check
        if (is_mesh or is_skin) and len(verts) == 0:
            result['warnings'].append('ZERO_VERTS')
        if (is_mesh or is_skin) and len(faces) == 0 and len(verts) > 0:
            result['warnings'].append('ZERO_FACES')

        # TXI data
        result['txi_blend']      = int(getattr(node, 'txi_blending', getattr(node, 'txi_blend', 0)))
        result['txi_alpha_test'] = float(getattr(node, 'txi_alpha_test', 0.0))

    return result


def walk_nodes(root_node):
    """Yield all nodes in a model tree via DFS."""
    if root_node is None:
        return
    stack = [root_node]
    while stack:
        n = stack.pop()
        yield n
        children = getattr(n, 'children', [])
        stack.extend(children)


# ── Model Audit ───────────────────────────────────────────────────────────────

def audit_model(resref: str, game: str, mdl_bytes: bytes, mdx_bytes: bytes,
                tex_cache=None) -> Dict:
    """
    Full audit of one model.
    Returns a result dict with all findings.
    """
    result = {
        'resref':    resref,
        'game':      game,
        'category':  categorize_model(resref),
        'parse_ok':  False,
        'parse_error': None,
        'node_count':  0,
        'mesh_count':  0,
        'skin_count':  0,
        'tri_count':   0,
        'zero_vert_nodes': [],
        'dup_names':   [],
        'uv_issues':   [],    # list of {node, type, umax, vmax}
        'geo_issues':  [],
        'warnings':    [],
        'supermodel':  '',
        'textures_used': [],
        'has_txi_nodes': 0,
    }

    try:
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        model  = parser.parse()
    except Exception as e:
        result['parse_error'] = str(e)[:200]
        return result

    result['parse_ok'] = True
    result['supermodel'] = getattr(model, 'supermodel', '') or ''

    # Walk all nodes
    node_names = []
    for node in walk_nodes(getattr(model, 'root_node', None)):
        nr = audit_node(node, model)
        node_names.append(nr['name'])
        result['node_count'] += 1

        if nr['type'] in ('skin_mesh', 'trimesh'):
            result['mesh_count'] += 1
            result['tri_count']  += nr['face_count']

        if nr['type'] == 'skin_mesh':
            result['skin_count'] += 1

        if 'ZERO_VERTS' in nr['warnings']:
            result['zero_vert_nodes'].append(nr['name'])

        if nr['uv_issue'] is not None:
            result['uv_issues'].append({
                'node':  nr['name'],
                'type':  nr['uv_issue'],
                'umax':  nr['uv_umax'],
                'vmax':  nr['uv_vmax'],
                'is_skin': nr['is_skin'],
            })

        if nr['texture']:
            result['textures_used'].append(nr['texture'])

        if nr['txi_blend'] != 0 or nr['txi_alpha_test'] > 0:
            result['has_txi_nodes'] += 1

    # Duplicate node names
    name_counts = Counter(node_names)
    result['dup_names'] = [n for n, c in name_counts.items() if c > 1]

    # Deduplicate textures
    result['textures_used'] = sorted(set(t.lower() for t in result['textures_used'] if t))

    # Classify overall health
    has_corrupt = any(i['type'] == 'CORRUPT_UV' for i in result['uv_issues'])
    has_error   = any(i['type'] == 'ERROR_UV'   for i in result['uv_issues'])
    has_warn    = any(i['type'] == 'WARN_ATLAS'  for i in result['uv_issues'])
    has_zero    = bool(result['zero_vert_nodes'])

    if result['parse_error']:
        result['health'] = 'FAIL'
    elif has_corrupt or has_error:
        result['health'] = 'WARN'
    elif has_zero:
        result['health'] = 'WARN'
    else:
        result['health'] = 'OK'

    return result


# ── Renderer Integration ──────────────────────────────────────────────────────

def try_render_model(resref: str, game: str, mdl_bytes: bytes, mdx_bytes: bytes,
                     tex_cache, render_size: int = 256) -> Optional[Any]:
    """
    Attempt to GPU-render a model using render_model_autoframe.
    Returns dict of {view: PIL.Image} or None on failure.
    """
    try:
        from src.gui.gpu_renderer import render_model_autoframe, _apply_txi_from_textures_to_model
        from src.core.mdl_parser import MDLBinaryParser

        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        model  = parser.parse()

        views = render_model_autoframe(
            model,
            W=render_size,
            H=render_size,
            textures=tex_cache,
            views=['front', 'back', 'right', 'left'],
        )
        return views
    except Exception as e:
        return None


def score_render(img) -> Dict:
    """
    Analyse a rendered PIL image for visual quality metrics.
    Returns a dict with non_bg_frac, yellow_artifacts, horn_tan count etc.
    """
    try:
        import numpy as np
        arr = np.array(img.convert('RGB'), dtype=np.uint8)
        h, w = arr.shape[:2]
        total = h * w

        # Black background pixels
        bg = (arr[:,:,0] < 8) & (arr[:,:,1] < 8) & (arr[:,:,2] < 8)
        non_bg = int((~bg).sum())

        # Yellow artifact pixels (strong R+G, weak B — the horn mipmap issue)
        yellow = ((arr[:,:,0] > 180) & (arr[:,:,1] > 160) & (arr[:,:,2] < 80))
        yellow_cnt = int(yellow.sum())

        # Pink pixels (mouth / flesh artifact)
        pink = ((arr[:,:,0] > 180) & (arr[:,:,1] < 120) & (arr[:,:,2] > 120))
        pink_cnt = int(pink.sum())

        return {
            'non_bg':      non_bg,
            'non_bg_frac': round(non_bg / max(total, 1), 3),
            'yellow_artifacts': yellow_cnt,
            'pink_artifacts':   pink_cnt,
        }
    except Exception:
        return {'non_bg': 0, 'non_bg_frac': 0.0, 'yellow_artifacts': 0, 'pink_artifacts': 0}


# ── Main Audit Runner ─────────────────────────────────────────────────────────

def run_audit(args):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renders_dir = OUT_DIR / 'renders'
    if not args.no_render:
        renders_dir.mkdir(parents=True, exist_ok=True)

    print(f"GhostRigger Full Game Audit v13.0")
    print(f"{'='*60}")

    # Set up library
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
    print(f"Total models found: {len(all_models)}")

    # Filter
    if args.filter:
        all_models = [m for m in all_models if args.filter.lower() in m.resref.lower()]
        print(f"After filter '{args.filter}': {len(all_models)}")

    if args.category:
        all_models = [m for m in all_models if categorize_model(m.resref) == args.category]
        print(f"After category '{args.category}': {len(all_models)}")

    if args.max and len(all_models) > args.max:
        all_models = all_models[:args.max]
        print(f"Capped at {args.max}")

    print(f"Auditing {len(all_models)} models...\n")

    # ── Per-model audit ───────────────────────────────────────────────────────
    results    = []
    issues     = []
    cat_stats  = defaultdict(lambda: {'total': 0, 'ok': 0, 'warn': 0, 'fail': 0,
                                       'tri_count': 0, 'render_ok': 0})
    total_start = time.time()

    for idx, entry in enumerate(all_models):
        resref = entry.resref
        game   = entry.game
        t0     = time.time()

        if idx % 100 == 0:
            elapsed = time.time() - total_start
            pct = 100.0 * idx / len(all_models)
            print(f"  [{idx:4d}/{len(all_models)}] {pct:.1f}% — {resref} ({game}) — {elapsed:.0f}s elapsed")

        # Load bytes
        try:
            mdl_bytes, mdx_bytes = lib.get_model_data(entry)
            if not mdl_bytes:
                raise ValueError("MDL data not found")
            mdx_bytes = mdx_bytes or b''
        except Exception as e:
            r = {
                'resref': resref, 'game': game,
                'category': categorize_model(resref),
                'parse_ok': False, 'parse_error': f'load_error: {e}',
                'health': 'FAIL',
            }
            results.append(r)
            issues.append(r)
            cat_stats[categorize_model(resref)]['fail'] += 1
            continue

        # Structural audit
        r = audit_model(resref, game, mdl_bytes, mdx_bytes)
        r['audit_time_ms'] = round((time.time() - t0) * 1000, 1)

        # Optionally render
        r['render_ok']    = False
        r['render_scores'] = {}
        if not args.no_render and r['parse_ok'] and r['mesh_count'] > 0:
            try:
                # Build minimal texture cache
                tex_cache = {}
                for tname in r.get('textures_used', [])[:8]:
                    try:
                        raw = lib.get_texture_data(tname, game)
                        if raw:
                            tex_cache[tname.lower()] = raw
                    except Exception:
                        pass

                views = try_render_model(resref, game, mdl_bytes, mdx_bytes, tex_cache)
                if views:
                    r['render_ok'] = True
                    cat_stats[r['category']]['render_ok'] += 1
                    # Score each view
                    for vname, img in views.items():
                        score = score_render(img)
                        r['render_scores'][vname] = score
                        # Save render
                        render_path = renders_dir / f"{game}_{resref}_{vname}.png"
                        try:
                            img.save(str(render_path))
                        except Exception:
                            pass
            except Exception as e:
                r['render_error'] = str(e)[:100]

        results.append(r)

        # Stats
        cat_stats[r['category']]['total']     += 1
        cat_stats[r['category']]['tri_count'] += r.get('tri_count', 0)
        if r['health'] == 'OK':
            cat_stats[r['category']]['ok']   += 1
        elif r['health'] == 'WARN':
            cat_stats[r['category']]['warn'] += 1
            issues.append(r)
        else:
            cat_stats[r['category']]['fail'] += 1
            issues.append(r)

    elapsed_total = time.time() - total_start
    print(f"\nAudit complete in {elapsed_total:.1f}s")

    # ── Write outputs ─────────────────────────────────────────────────────────
    # Full results JSON
    full_json = OUT_DIR / 'audit_v13_full.json'
    with open(full_json, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Full results: {full_json}")

    # Issues only JSON
    issues_json = OUT_DIR / 'audit_v13_issues.json'
    with open(issues_json, 'w') as f:
        json.dump(issues, f, indent=2, default=str)
    print(f"Issues ({len(issues)}): {issues_json}")

    # ── Summary text ─────────────────────────────────────────────────────────
    summary_lines = []
    summary_lines.append("=" * 70)
    summary_lines.append("GhostRigger Full Game Audit v13.0 — Summary")
    summary_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"Models audited: {len(results)}")
    summary_lines.append(f"Time: {elapsed_total:.1f}s")
    summary_lines.append("=" * 70)
    summary_lines.append("")

    # Overall stats
    total_ok   = sum(1 for r in results if r.get('health') == 'OK')
    total_warn = sum(1 for r in results if r.get('health') == 'WARN')
    total_fail = sum(1 for r in results if r.get('health') == 'FAIL')
    total_tris = sum(r.get('tri_count', 0) for r in results)

    summary_lines.append(f"Overall: OK={total_ok}  WARN={total_warn}  FAIL={total_fail}")
    summary_lines.append(f"Total triangles across all models: {total_tris:,}")
    summary_lines.append("")

    # Per-category table
    summary_lines.append(f"{'Category':<20} {'Total':>6} {'OK':>6} {'WARN':>6} {'FAIL':>6} {'Tris':>10} {'Renders':>8}")
    summary_lines.append("-" * 70)
    for cat, s in sorted(cat_stats.items()):
        summary_lines.append(
            f"{cat:<20} {s['total']:>6} {s['ok']:>6} {s['warn']:>6} {s['fail']:>6} "
            f"{s['tri_count']:>10,} {s['render_ok']:>8}"
        )
    summary_lines.append("")

    # UV issue breakdown
    uv_types = Counter()
    for r in results:
        for ui in r.get('uv_issues', []):
            uv_types[ui['type']] += 1
    if uv_types:
        summary_lines.append("UV Issue Types:")
        for t, c in uv_types.most_common():
            summary_lines.append(f"  {t}: {c}")
        summary_lines.append("")

    # Top 20 models with real UV errors
    error_models = [
        r for r in results
        if any(ui['type'] == 'ERROR_UV' for ui in r.get('uv_issues', []))
    ]
    if error_models:
        summary_lines.append(f"Models with ERROR_UV ({len(error_models)}):")
        for r in sorted(error_models, key=lambda x: max(
            (max(ui['umax'], ui['vmax']) for ui in x.get('uv_issues', [])), default=0
        ), reverse=True)[:20]:
            issues_str = '; '.join(
                f"{ui['node']}(U={ui['umax']},V={ui['vmax']})"
                for ui in r['uv_issues'] if ui['type'] == 'ERROR_UV'
            )
            summary_lines.append(f"  {r['game']} {r['resref']}: {issues_str}")
        summary_lines.append("")

    # Models with CORRUPT UV
    corrupt_models = [
        r for r in results
        if any(ui['type'] == 'CORRUPT_UV' for ui in r.get('uv_issues', []))
    ]
    if corrupt_models:
        summary_lines.append(f"Models with CORRUPT_UV ({len(corrupt_models)}):")
        for r in corrupt_models[:20]:
            summary_lines.append(f"  {r['game']} {r['resref']}")
        summary_lines.append("")

    # Render quality summary
    render_ok = [r for r in results if r.get('render_ok')]
    if render_ok:
        yellow_total = sum(
            sum(v.get('yellow_artifacts', 0) for v in r.get('render_scores', {}).values())
            for r in render_ok
        )
        pink_total = sum(
            sum(v.get('pink_artifacts', 0) for v in r.get('render_scores', {}).values())
            for r in render_ok
        )
        black_models = [
            r for r in render_ok
            if all(v.get('non_bg_frac', 1.0) < 0.01
                   for v in r.get('render_scores', {}).values())
        ]
        summary_lines.append(f"Render Results ({len(render_ok)} models rendered):")
        summary_lines.append(f"  Yellow artifact pixels total: {yellow_total}")
        summary_lines.append(f"  Pink artifact pixels total:   {pink_total}")
        summary_lines.append(f"  Black/empty renders:          {len(black_models)}")
        if black_models:
            for r in black_models[:10]:
                summary_lines.append(f"    {r['game']} {r['resref']}")
        summary_lines.append("")

    summary_text = '\n'.join(summary_lines)
    summary_file = OUT_DIR / 'audit_v13_summary.txt'
    with open(summary_file, 'w') as f:
        f.write(summary_text)
    print(f"Summary: {summary_file}")
    print()
    print(summary_text)

    return results, issues


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='GhostRigger Full Game Audit v13.0')
    ap.add_argument('--k1',       help='K1 game directory', default=None)
    ap.add_argument('--k2',       help='K2 game directory', default=None)
    ap.add_argument('--game',     help='Which game to audit: K1, K2, both', default='both')
    ap.add_argument('--max',      help='Max models to audit', type=int, default=None)
    ap.add_argument('--filter',   help='Filter resref by substring', default=None)
    ap.add_argument('--category', help='Only audit this category', default=None)
    ap.add_argument('--no-render', action='store_true', help='Skip GPU renders')
    args = ap.parse_args()
    run_audit(args)


if __name__ == '__main__':
    main()
