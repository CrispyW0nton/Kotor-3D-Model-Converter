#!/usr/bin/env python3
"""
GhostRigger Full-Game Batch Runner
Runs batch_render_all.py in category chunks to manage memory.
Each chunk is a separate subprocess to avoid OOM.
"""
import subprocess, sys, os, json, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "audit_output" / "batch_render"

CATEGORIES = [
    'creatures', 'npcs', 'pc_models', 'supermodels',
    'placeables', 'doors', 'weapons', 'items',
    'vfx', 'modules', 'other',
]

def run_category(cat, render_size=128):
    log = OUT_DIR / f"log_{cat}.txt"
    print(f"\n{'='*60}")
    print(f"Starting category: {cat}")
    print(f"Log: {log}")
    
    cmd = [
        sys.executable, str(ROOT / 'tools' / 'batch_render_all.py'),
        '--category', cat,
        '--render-size', str(render_size),
    ]
    
    t0 = time.time()
    with open(log, 'w') as lf:
        proc = subprocess.run(cmd, cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT,
                               timeout=1800)  # 30 min max per category
    elapsed = time.time() - t0
    print(f"  Finished {cat} in {elapsed:.0f}s  (exit={proc.returncode})")
    return proc.returncode == 0


def merge_results():
    """Merge all category result JSONs into one master report."""
    all_results = []
    all_issues = []
    for cat in CATEGORIES:
        rpath = OUT_DIR / 'results_full.json'
        if rpath.exists():
            # Already merged — can't re-merge since all share the same file
            break
    # Instead, just note that results_full.json is the master
    if (OUT_DIR / 'results_full.json').exists():
        with open(OUT_DIR / 'results_full.json') as f:
            data = json.load(f)
        print(f"\nMaster results: {len(data)} entries in results_full.json")
    return True


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("GhostRigger Full-Game Batch Runner")
    print(f"Output: {OUT_DIR}")
    
    # Check which categories are already done by looking at rendered images
    renders_dir = OUT_DIR / 'renders'
    
    success = []
    failed = []
    
    for cat in CATEGORIES:
        try:
            ok = run_category(cat, render_size=128)
            if ok:
                success.append(cat)
            else:
                failed.append(cat)
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT on {cat} — skipping")
            failed.append(cat)
        except Exception as e:
            print(f"  ERROR on {cat}: {e}")
            failed.append(cat)
    
    print(f"\n{'='*60}")
    print(f"DONE: {len(success)} categories OK, {len(failed)} failed")
    print(f"OK: {success}")
    print(f"Failed: {failed}")
    
    merge_results()


if __name__ == '__main__':
    main()
