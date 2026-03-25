#!/usr/bin/env python3
"""
GhostRigger Batch Visual Audit
================================
Renders every loadable KotOR model and produces a visual quality report.
Detects: missing textures (pink), untextured (white/flat), rendering errors,
         yellow artifacts, and model coverage issues.

Usage:
  python3 tools/batch_visual_audit.py                          # all models
  python3 tools/batch_visual_audit.py --category creatures
  python3 tools/batch_visual_audit.py --filter c_bantha
  python3 tools/batch_visual_audit.py --max 100
  python3 tools/batch_visual_audit.py --size 512               # render size
"""

import sys, os, time, json, argparse, traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import GameLibrary
from src.core.mdl_parser import MDLBinaryParser
from src.gui.gpu_renderer import render_model_autoframe

import numpy as np
from PIL import Image

# ── Config ───────────────────────────────────────────────────────────────────
K1_DIR  = "game_data/k1_extracted"
K2_DIR  = "game_data/k2_extracted"
OUT_DIR = Path("audit_output/visual_audit")

CATEGORY_PREFIXES = {
    'creatures':  ('c_',),
    'npcs':       ('n_',),
    'pc_models':  ('p_', 'pmb', 'pmf'),
    'placeables': ('plc_',),
    'doors':      ('door', 'dor_'),
    'weapons':    ('w_',),
    'items':      ('i_',),
    'supermodels':('s_male', 's_female', 's_human'),
}

def categorize(resref: str) -> str:
    r = resref.lower()
    for cat, prefixes in CATEGORY_PREFIXES.items():
        if any(r.startswith(p) for p in prefixes):
            return cat
    return 'other'


def load_textures(model, game: str, lib: GameLibrary) -> Dict[str, bytes]:
    """Load all textures referenced by a model."""
    textures = {}
    for node in model.all_nodes():
        for attr in ['bitmap', 'texture', 'texture0', 'texture1', 'bump_map']:
            val = getattr(node, attr, None)
            if val and val.strip().lower() not in ('null', '', 'none'):
                name = val.strip().lower()
                if name not in textures:
                    data = lib.get_texture_data(name, game)
                    if data:
                        textures[name] = data
    return textures


def score_render(img: Image.Image) -> Dict:
    """Score a rendered image for visual quality issues."""
    arr = np.array(img.convert('RGBA'))
    alpha = arr[:, :, 3]
    fg_mask = alpha > 10
    total_pixels = arr.shape[0] * arr.shape[1]
    fg_count = int(fg_mask.sum())
    
    if fg_count == 0:
        return {
            'coverage_pct': 0.0,
            'yellow_pct': 0.0,
            'pink_pct': 0.0,
            'white_pct': 0.0,
            'ok': False,
            'issues': ['EMPTY_RENDER'],
        }
    
    fg = arr[fg_mask].astype(float)
    r, g, b = fg[:, 0], fg[:, 1], fg[:, 2]
    
    # Yellow: high R+G, low B
    yellow = ((r > 160) & (g > 160) & (b < 80) & ((r + g) > 2.5 * b.clip(1)))
    yellow_pct = float(100 * yellow.sum() / fg_count)
    
    # Pink/magenta: high R+B, low G (missing texture fallback)
    pink = ((r > 180) & (b > 180) & (g < 100))
    pink_pct = float(100 * pink.sum() / fg_count)
    
    # Flat white/bright: avg > 220 on all channels
    white = ((r > 220) & (g > 220) & (b > 220))
    white_pct = float(100 * white.sum() / fg_count)
    
    coverage_pct = float(100 * fg_count / total_pixels)
    
    issues = []
    if yellow_pct > 5.0:   issues.append(f'YELLOW:{yellow_pct:.1f}%')
    if pink_pct > 5.0:     issues.append(f'PINK:{pink_pct:.1f}%')
    if white_pct > 30.0:   issues.append(f'WHITE:{white_pct:.1f}%')
    if coverage_pct < 1.0: issues.append(f'LOW_COV:{coverage_pct:.2f}%')
    
    return {
        'coverage_pct': coverage_pct,
        'yellow_pct': yellow_pct,
        'pink_pct': pink_pct,
        'white_pct': white_pct,
        'ok': len(issues) == 0,
        'issues': issues,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max',      type=int, default=None,    help='Limit models')
    ap.add_argument('--filter',   type=str, default=None,    help='Substring filter on resref')
    ap.add_argument('--category', type=str, default=None,    help='Category filter')
    ap.add_argument('--game',     choices=['K1','K2'], default=None)
    ap.add_argument('--size',     type=int, default=256,     help='Render size (WxH)')
    ap.add_argument('--no-save',  action='store_true',       help='Skip saving PNGs')
    args = ap.parse_args()
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renders_dir = OUT_DIR / 'renders'
    if not args.no_save:
        renders_dir.mkdir(parents=True, exist_ok=True)
    
    print("GhostRigger Batch Visual Audit")
    print("=" * 60)
    
    lib = GameLibrary()
    lib.scan(K1_DIR, K2_DIR)
    
    models = lib.models
    if args.game:
        models = [m for m in models if m.game == args.game]
    if args.filter:
        models = [m for m in models if args.filter.lower() in m.resref.lower()]
    if args.category:
        prefixes = CATEGORY_PREFIXES.get(args.category, ())
        models = [m for m in models if any(m.resref.lower().startswith(p) for p in prefixes)]
    if args.max:
        models = models[:args.max]
    
    models = sorted(models, key=lambda m: (categorize(m.resref), m.game, m.resref))
    print(f"Auditing {len(models)} models at {args.size}x{args.size}px...")
    
    results = []
    ok = warn = fail = error_count = 0
    t0 = time.time()
    
    for i, entry in enumerate(models):
        result = {
            'resref': entry.resref,
            'game': entry.game,
            'category': categorize(entry.resref),
            'status': 'error',
            'render_score': None,
            'tex_count': 0,
            'error': None,
        }
        
        try:
            mdl_bytes, mdx_bytes = lib.get_model_data(entry)
            if not mdl_bytes:
                result['error'] = 'NO_MDL_DATA'
                result['status'] = 'fail'
                fail += 1
                results.append(result)
                continue
            
            parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
            model = parser.parse()
            if model is None:
                result['error'] = 'PARSE_FAILED'
                result['status'] = 'fail'
                fail += 1
                results.append(result)
                continue
            
            textures = load_textures(model, entry.game, lib)
            result['tex_count'] = len(textures)
            
            W = H = args.size
            renders = render_model_autoframe(
                model, W=W, H=H,
                textures=textures,
                views=['front']
            )
            
            if not renders:
                result['error'] = 'NO_RENDER_OUTPUT'
                result['status'] = 'fail'
                fail += 1
                results.append(result)
                continue
            
            # Score the render
            front_img = renders.get('front', list(renders.values())[0])
            score = score_render(front_img)
            result['render_score'] = score
            
            if not args.no_save:
                fn = renders_dir / f"{entry.game}_{entry.resref}_front.png"
                front_img.save(str(fn))
            
            if score['ok']:
                result['status'] = 'ok'
                ok += 1
            elif score['issues']:
                result['status'] = 'warn'
                result['error'] = ' | '.join(score['issues'])
                warn += 1
            else:
                result['status'] = 'ok'
                ok += 1
        
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)[:120]
            error_count += 1
        
        results.append(result)
        
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(models) - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{len(models)}] ok={ok} warn={warn} fail={fail} err={error_count}"
                  f" — {elapsed:.0f}s, ETA {eta:.0f}s")
    
    elapsed = time.time() - t0
    
    # Save results
    results_path = OUT_DIR / 'visual_audit_results.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate summary
    warn_models = [r for r in results if r['status'] in ('warn', 'fail', 'error')]
    
    summary_lines = [
        "=" * 70,
        "GhostRigger Batch Visual Audit — Summary",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Models: {len(results)}  Time: {elapsed:.1f}s",
        "=" * 70,
        "",
        f"Overall: OK={ok}  WARN={warn}  FAIL={fail}  ERROR={error_count}",
        f"Pass rate: {100*ok/max(len(results),1):.1f}%",
        "",
    ]
    
    # Category breakdown
    from collections import Counter
    cats = Counter(r['category'] for r in results)
    cat_ok = Counter(r['category'] for r in results if r['status'] == 'ok')
    summary_lines.append(f"{'Category':<20} {'Total':>7} {'OK':>6} {'Issues':>8}")
    summary_lines.append("-" * 50)
    for cat in sorted(cats):
        summary_lines.append(f"  {cat:<18} {cats[cat]:>7} {cat_ok[cat]:>6} {cats[cat]-cat_ok[cat]:>8}")
    summary_lines.append("")
    
    # Issue models
    if warn_models:
        summary_lines.append(f"Models with visual issues ({len(warn_models)}):")
        for r in sorted(warn_models, key=lambda x: x['resref']):
            summary_lines.append(f"  {r['game']} {r['resref']}: [{r['status'].upper()}] {r['error']}")
    else:
        summary_lines.append("No visual issues detected!")
    
    summary_text = '\n'.join(summary_lines)
    
    summary_path = OUT_DIR / 'visual_audit_summary.txt'
    with open(summary_path, 'w') as f:
        f.write(summary_text)
    
    print(f"\n{'='*60}")
    print(summary_text)
    print(f"\nResults: {results_path}")
    print(f"Summary: {summary_path}")


if __name__ == '__main__':
    main()
