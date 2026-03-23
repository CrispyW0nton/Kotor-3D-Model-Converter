#!/usr/bin/env python3
"""
Batch Render & Audit: Module/Area Models (Memory-safe)
======================================================
Processes KotOR 1 & 2 module geometry models in batches of 100,
rendering each to a 128×128 PNG thumbnail.  Skips already-rendered
models (resume support).

Usage:
    python3 tools/batch_modules.py              # both games
    python3 tools/batch_modules.py --game K1    # K1 only
    python3 tools/batch_modules.py --game K2    # K2 only
    python3 tools/batch_modules.py --no-render  # audit only, no GPU
    python3 tools/batch_modules.py --max 200    # limit count
"""

import sys, os, gc, json, time, math, argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import GameLibrary
from tools.batch_render_all import (
    categorize, audit_model_struct,
    build_tex_cache, try_render, flush_gpu_cache, reset_renderer,
    score_image, save_contact_sheet, RENDER_PRIORITY, OUT_DIR,
    K1_DIR, K2_DIR
)

# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Batch render KotOR module models")
    ap.add_argument('--game', choices=['K1','K2','both'], default='both')
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--k1', default=K1_DIR)
    ap.add_argument('--k2', default=K2_DIR)
    ap.add_argument('--render-size', type=int, default=128)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renders_dir = OUT_DIR / 'renders'
    sheets_dir  = OUT_DIR / 'sheets'
    if not args.no_render:
        renders_dir.mkdir(parents=True, exist_ok=True)
        sheets_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("GhostRigger Module Batch Renderer")
    print("=" * 70)

    # ── Scan ──────────────────────────────────────────────────────────────────
    lib = GameLibrary()
    if args.game in ('K1','both') and os.path.isdir(args.k1):
        lib.set_k1_dir(args.k1); print(f"K1: {args.k1}")
    if args.game in ('K2','both') and os.path.isdir(args.k2):
        lib.set_k2_dir(args.k2); print(f"K2: {args.k2}")
    lib.scan()

    all_mods = [m for m in lib.models if categorize(m.resref) == 'modules']
    all_mods.sort(key=lambda m: m.resref)
    print(f"Module models found: {len(all_mods)}")

    # ── Resume support ────────────────────────────────────────────────────────
    if not args.no_render and renders_dir.exists():
        skip = set()
        for f in renders_dir.iterdir():
            if f.name.endswith('_front.png'):
                name = f.name[:-len('_front.png')]
                if name.startswith('K1_'):   skip.add(('K1', name[3:]))
                elif name.startswith('K2_'): skip.add(('K2', name[3:]))
        before = len(all_mods)
        all_mods = [m for m in all_mods if (m.game, m.resref) not in skip]
        if skip:
            print(f"Resume: skip={before-len(all_mods)}, remaining={len(all_mods)}")

    if args.max and len(all_mods) > args.max:
        all_mods = all_mods[:args.max]
        print(f"Capped at {args.max}")

    print(f"\nProcessing {len(all_mods)} module models...\n")

    # ── Process ───────────────────────────────────────────────────────────────
    results  = []
    sheet_items = []
    ok = warn = fail = rend_ok = rend_fail = 0
    total_tris = yellow_total = pink_total = 0
    rsize = args.render_size
    FLUSH_INTERVAL = 50   # flush GPU every N models (tight for 987 MB RAM limit)

    t_start = time.time()

    for idx, entry in enumerate(all_mods):
        resref = entry.resref
        game   = entry.game

        if idx % FLUSH_INTERVAL == 0 and idx > 0:
            reset_renderer()    # full renderer teardown+rebuild for memory
            flush_gpu_cache()
            gc.collect()
            print(f"  [MEM] Renderer reset at idx={idx}", flush=True)

        if idx % 50 == 0:
            el  = time.time() - t_start
            pct = 100.0 * idx / max(len(all_mods), 1)
            eta = (el / max(idx, 1)) * (len(all_mods) - idx)
            print(f"  [{idx:5d}/{len(all_mods)}] {pct:5.1f}%  {resref:<30} ({game})"
                  f"  el={el:.0f}s  ETA={eta:.0f}s", flush=True)

        t0 = time.time()

        # ── Load MDL ──────────────────────────────────────────────────────────
        try:
            mdl_bytes, mdx_bytes = lib.get_model_data(entry)
            if not mdl_bytes:
                raise ValueError("MDL empty")
            mdx_bytes = mdx_bytes or b''
        except Exception as e:
            r = {'resref': resref, 'game': game, 'category': 'modules',
                 'parse_ok': False, 'parse_error': f'load:{e}',
                 'health': 'FAIL', 'tri_count': 0,
                 'render_ok': False, 'render_scores': {}}
            results.append(r); fail += 1; rend_fail += 1
            continue

        # ── Audit ─────────────────────────────────────────────────────────────
        r = audit_model_struct(resref, game, mdl_bytes, mdx_bytes)
        r['audit_ms'] = round((time.time() - t0) * 1000, 1)
        r['render_ok'] = False
        r['render_scores'] = {}

        if r['health'] == 'OK':    ok   += 1
        elif r['health'] == 'WARN': warn += 1
        else:                       fail += 1
        total_tris += r.get('tri_count', 0)

        # ── Render ────────────────────────────────────────────────────────────
        if not args.no_render:
            tex_cache = None
            try:
                tex_cache = build_tex_cache(lib, r.get('textures', []), game)
                views = try_render(resref, game, mdl_bytes, mdx_bytes,
                                   tex_cache, size=rsize)
                if views:
                    for vname, img in views.items():
                        if img:
                            fp = renders_dir / f"{game}_{resref}_{vname}.png"
                            img.save(str(fp))
                    if 'front' in views and views['front']:
                        score = score_image(views['front'])
                        r['render_scores']['front'] = score
                        yellow_total += score['yellow']
                        pink_total   += score['pink']
                        sheet_items.append((f"{game[:1]}{resref[:9]}", views['front']))
                    r['render_ok'] = True
                    rend_ok += 1
                else:
                    rend_fail += 1
            except Exception as e:
                r['render_error'] = str(e)
                rend_fail += 1
            finally:
                # Free texture cache and model bytes immediately after render
                tex_cache = None
                gc.collect()

            # renderer already reset above if at FLUSH_INTERVAL

        # Free model bytes after processing
        del mdl_bytes, mdx_bytes
        results.append(r)

    elapsed = time.time() - t_start

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"Module Batch Complete: {len(results)} models in {elapsed:.1f}s")
    print(f"  OK={ok}  WARN={warn}  FAIL={fail}")
    print(f"  Rendered={rend_ok}  RenderFail={rend_fail}")
    print(f"  Total triangles: {total_tris:,}")
    print(f"  Artifact pixels: yellow={yellow_total}  pink={pink_total}")

    # ── Save results ──────────────────────────────────────────────────────────
    out_json = OUT_DIR / 'results_modules.json'
    with open(out_json, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults: {out_json}")

    # ── Contact sheet ─────────────────────────────────────────────────────────
    if sheet_items and not args.no_render:
        sheet_p = sheets_dir / 'modules.png'
        save_contact_sheet(sheet_items, sheet_p, thumb=64, cols=30)
        print(f"Contact sheet: {sheet_p}  ({len(sheet_items)} models)")

    return results


if __name__ == '__main__':
    main()
