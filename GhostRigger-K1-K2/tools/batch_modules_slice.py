#!/usr/bin/env python3
"""
batch_modules_slice.py
======================
Render exactly the resrefs listed in --resref-file for the given --game.
Called by module_render_orchestrator.py as isolated subprocesses.

Each invocation:
  - Scans its GameLibrary (metadata only, ~1 MB RSS)
  - Renders only the requested resrefs
  - Saves PNGs to audit_output/batch_render/renders/
  - Exits, freeing all GPU memory

Exit code 0 on success, 1 on fatal error.
"""

import sys, os, gc, time, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.resources.game_library import GameLibrary
from tools.batch_render_all import (
    categorize, audit_model_struct,
    build_tex_cache, try_render, flush_gpu_cache, reset_renderer,
    score_image, OUT_DIR, K1_DIR, K2_DIR
)

RENDERS_DIR = OUT_DIR / "renders"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resref-file", required=True,
                    help="File with one resref per line")
    ap.add_argument("--game", choices=["K1", "K2", "both"], default="both")
    ap.add_argument("--k1", default=K1_DIR)
    ap.add_argument("--k2", default=K2_DIR)
    ap.add_argument("--render-size", type=int, default=128)
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    # Load resref list
    resref_path = Path(args.resref_file)
    if not resref_path.exists():
        print(f"ERROR: resref file not found: {resref_path}", file=sys.stderr)
        sys.exit(1)

    resrefs = [r.strip() for r in resref_path.read_text().splitlines() if r.strip()]
    if not resrefs:
        print("Batch slice done – empty list. OK=0 WARN=0 FAIL=0  Rendered=0")
        return

    RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    # Scan library
    lib = GameLibrary()
    if args.game in ("K1", "both") and os.path.isdir(args.k1):
        lib.set_k1_dir(args.k1)
    if args.game in ("K2", "both") and os.path.isdir(args.k2):
        lib.set_k2_dir(args.k2)
    lib.scan()

    # Build lookup: resref -> entry
    entry_map = {m.resref: m for m in lib.models}

    rsize = args.render_size
    ok = warn = fail = rend_ok = rend_fail = 0
    FLUSH_INTERVAL = 10  # aggressively flush every 10 models in a slice

    t_start = time.time()

    for idx, resref in enumerate(resrefs):
        if idx > 0 and idx % FLUSH_INTERVAL == 0:
            reset_renderer()
            flush_gpu_cache()
            gc.collect()

        entry = entry_map.get(resref)
        if entry is None:
            print(f"  [MISS] {resref} not found in library", file=sys.stderr)
            fail += 1
            continue

        game = entry.game

        # Load MDL bytes
        try:
            mdl_bytes, mdx_bytes = lib.get_model_data(entry)
            if not mdl_bytes:
                raise ValueError("empty MDL")
            mdx_bytes = mdx_bytes or b""
        except Exception as e:
            print(f"  [LOAD ERR] {resref}: {e}", file=sys.stderr)
            fail += 1
            continue

        # Audit
        r = audit_model_struct(resref, game, mdl_bytes, mdx_bytes)

        if r["health"] == "OK":
            ok += 1
        elif r["health"] == "WARN":
            warn += 1
        else:
            fail += 1

        # Render
        if not args.no_render:
            try:
                tex_cache = build_tex_cache(lib, r.get("textures", []), game)
                views = try_render(resref, game, mdl_bytes, mdx_bytes,
                                   tex_cache, size=rsize)
                if views:
                    for vname, img in views.items():
                        if img:
                            fp = RENDERS_DIR / f"{game}_{resref}_{vname}.png"
                            img.save(str(fp))
                    if "front" in views and views["front"]:
                        rend_ok += 1
                    else:
                        rend_fail += 1
                else:
                    rend_fail += 1
            except Exception as e:
                print(f"  [RENDER ERR] {resref}: {e}", file=sys.stderr)
                rend_fail += 1

    elapsed = time.time() - t_start

    # Print summary line (parsed by orchestrator)
    print(
        f"Batch slice done – {len(resrefs)} models in {elapsed:.1f}s"
        f"  OK={ok} WARN={warn} FAIL={fail}  Rendered={rend_ok}"
    )

    # Cleanup GPU
    try:
        reset_renderer()
        flush_gpu_cache()
        gc.collect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
