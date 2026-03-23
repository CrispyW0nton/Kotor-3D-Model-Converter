#!/usr/bin/env python3
"""
GhostRigger Full Visual Audit (subprocess mode)
=================================================
Audits every creature, NPC, and PC model by spawning lean_render_check.py
subprocesses, avoiding memory accumulation from the GPU renderer.

Results are saved to audit_output/visual_audit/full_visual_report.json + txt.

Usage:
  python3 tools/full_visual_audit.py
  python3 tools/full_visual_audit.py --category creatures npcs pc_models
  python3 tools/full_visual_audit.py --max 100
  python3 tools/full_visual_audit.py --save-renders    # also save PNGs
"""
import sys, os, json, time, subprocess, argparse
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.resources.game_library import GameLibrary

K1_DIR  = "game_data/k1_extracted"
K2_DIR  = "game_data/k2_extracted"
OUT_DIR = Path("audit_output/visual_audit")
LEAN    = Path(__file__).parent / "lean_render_check.py"

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

def categorize(resref):
    r = resref.lower()
    for cat, prefixes in CATEGORY_PREFIXES.items():
        if any(r.startswith(p) for p in prefixes):
            return cat
    return 'other'


def run_one(resref, game, size=128, out_png=None, timeout=30):
    """Run lean_render_check.py in subprocess and return parsed JSON result."""
    cmd = [sys.executable, str(LEAN), resref, game, str(size)]
    if out_png:
        cmd.append(str(out_png))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent)
        )
        if proc.stdout.strip():
            return json.loads(proc.stdout.strip())
        else:
            return {'resref': resref, 'game': game, 'ok': False,
                    'error': f'NO_OUTPUT: {proc.stderr[:80]}'}
    except subprocess.TimeoutExpired:
        return {'resref': resref, 'game': game, 'ok': False, 'error': 'TIMEOUT'}
    except Exception as e:
        return {'resref': resref, 'game': game, 'ok': False, 'error': str(e)[:80]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=None)
    ap.add_argument('--category', nargs='+', default=['creatures', 'npcs', 'pc_models'])
    ap.add_argument('--game', choices=['K1','K2'], default=None)
    ap.add_argument('--size', type=int, default=128)
    ap.add_argument('--save-renders', action='store_true')
    ap.add_argument('--filter', type=str, default=None)
    args = ap.parse_args()
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renders_dir = OUT_DIR / 'renders' if args.save_renders else None
    if renders_dir:
        renders_dir.mkdir(parents=True, exist_ok=True)
    
    print("GhostRigger Full Visual Audit (subprocess mode)")
    print("=" * 65)
    
    lib = GameLibrary()
    lib.scan(K1_DIR, K2_DIR)
    
    # Build model list
    all_cats = set(args.category)
    models = []
    for entry in lib.models:
        cat = categorize(entry.resref)
        if cat in all_cats:
            if args.game and entry.game != args.game:
                continue
            if args.filter and args.filter.lower() not in entry.resref.lower():
                continue
            models.append(entry)
    
    models = sorted(models, key=lambda m: (categorize(m.resref), m.game, m.resref))
    if args.max:
        models = models[:args.max]
    
    print(f"Models to audit: {len(models)}")
    print(f"Categories: {args.category}")
    print(f"Render size: {args.size}x{args.size}")
    print()
    
    results = []
    ok = warn = fail = 0
    t0 = time.time()
    
    for i, entry in enumerate(models):
        out_png = None
        if renders_dir:
            out_png = renders_dir / f"{entry.game}_{entry.resref}_front.png"
        
        r = run_one(entry.resref, entry.game, args.size, out_png)
        r['category'] = categorize(entry.resref)
        
        if r.get('ok'):
            r['status'] = 'ok'
            ok += 1
        elif r.get('error') in ('NOT_FOUND', 'NO_MDL_DATA', 'PARSE_FAILED', 'NO_RENDER', 'TIMEOUT'):
            r['status'] = 'fail'
            fail += 1
        elif r.get('score') and r['score'].get('issues'):
            r['status'] = 'warn'
            warn += 1
        else:
            r['status'] = 'error'
            fail += 1
        
        results.append(r)
        
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(models) - i - 1) / rate
            print(f"  [{i+1}/{len(models)}] OK={ok} WARN={warn} FAIL={fail} — {elapsed:.0f}s ETA {eta:.0f}s")
    
    elapsed = time.time() - t0
    
    # Save results
    results_path = OUT_DIR / 'full_visual_report.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Build summary
    issue_models = [r for r in results if r['status'] != 'ok']
    cats = Counter(r['category'] for r in results)
    cat_ok = Counter(r['category'] for r in results if r['status'] == 'ok')
    
    lines = [
        "=" * 70,
        "GhostRigger Full Visual Audit — Summary",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Models: {len(results)}  Time: {elapsed:.1f}s",
        "=" * 70,
        "",
        f"Overall: OK={ok}  WARN={warn}  FAIL={fail}",
        f"Visual pass rate: {100*ok/max(len(results),1):.1f}%",
        "",
        f"{'Category':<20} {'Total':>7} {'OK':>6} {'Issues':>8}",
        "-" * 50,
    ]
    for cat in sorted(cats):
        lines.append(f"  {cat:<18} {cats[cat]:>7} {cat_ok[cat]:>6} {cats[cat]-cat_ok[cat]:>8}")
    lines.append("")
    
    if issue_models:
        lines.append(f"Models with visual issues ({len(issue_models)}):")
        for r in sorted(issue_models, key=lambda x: x.get('resref', '')):
            err = r.get('error', '')
            if r.get('score') and r['score'].get('issues'):
                err = ' | '.join(r['score']['issues'])
            lines.append(f"  {r['game']} {r['resref']}: [{r['status'].upper()}] {err}")
    else:
        lines.append("✓ No visual issues detected across all audited models!")
    
    summary = '\n'.join(lines)
    summary_path = OUT_DIR / 'full_visual_summary.txt'
    with open(summary_path, 'w') as f:
        f.write(summary)
    
    print(f"\n{'='*65}")
    print(summary)
    print(f"\nResults: {results_path}")
    print(f"Summary: {summary_path}")


if __name__ == '__main__':
    main()
