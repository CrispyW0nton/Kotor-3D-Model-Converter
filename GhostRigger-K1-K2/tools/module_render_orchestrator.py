#!/usr/bin/env python3
"""
Module Render Orchestrator (Memory-safe, 2-phase)
==================================================
Phase 1  Scan GameLibrary → write TODO list to disk → unload library.
Phase 2  Loop over TODO list in BATCH_SIZE chunks, spawning an isolated
         batch_modules_slice.py subprocess per chunk.  Each subprocess
         owns its own library scan + GPU context, exits cleanly, and
         frees all memory before the next one starts.

With 987 MB RAM / no swap:
  - Phase 1 uses ~90 MB (metadata scan only)
  - Phase 2 orchestrator loop: ~10 MB (pure Python, no library)
  - Each slice subprocess: ~300–400 MB peak, then exits

Usage:
    python3 tools/module_render_orchestrator.py
    python3 tools/module_render_orchestrator.py --game K1
    python3 tools/module_render_orchestrator.py --batch-size 20
    python3 tools/module_render_orchestrator.py --render-size 128 --dry-run
    python3 tools/module_render_orchestrator.py --phase 2   # skip re-scan
"""

import sys, os, gc, json, time, subprocess, argparse, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ─── constants (loaded lazily to avoid heavy imports in phase-2) ──────────────
TODO_FILE  = ROOT / "logs" / "_module_todo.txt"
LOG_FILE   = ROOT / "logs" / "module_orchestrator.log"

def _get_constants():
    from tools.batch_render_all import categorize, K1_DIR, K2_DIR, OUT_DIR
    return categorize, K1_DIR, K2_DIR, OUT_DIR


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: scan library, write TODO list, then free everything
# ─────────────────────────────────────────────────────────────────────────────

def phase1_build_todo(args):
    """Scan GameLibrary and write remaining modules to TODO_FILE."""
    categorize, K1_DIR, K2_DIR, OUT_DIR = _get_constants()
    from src.resources.game_library import GameLibrary

    RENDERS_DIR = OUT_DIR / "renders"

    print("Phase 1: scanning library…", flush=True)
    lib = GameLibrary()
    if args.game in ("K1", "both") and os.path.isdir(args.k1):
        lib.set_k1_dir(args.k1);  print(f"  K1: {args.k1}")
    if args.game in ("K2", "both") and os.path.isdir(args.k2):
        lib.set_k2_dir(args.k2);  print(f"  K2: {args.k2}")
    lib.scan()

    # Build skip set from existing front renders
    skip = set()
    if RENDERS_DIR.exists():
        for f in RENDERS_DIR.iterdir():
            if f.name.endswith("_front.png"):
                name = f.name[:-len("_front.png")]
                if   name.startswith("K1_"): skip.add(("K1", name[3:]))
                elif name.startswith("K2_"): skip.add(("K2", name[3:]))

    # Collect remaining modules
    remaining = []
    for m in lib.models:
        if categorize(m.resref) != "modules":
            continue
        if args.game != "both" and m.game != args.game:
            continue
        if (m.game, m.resref) not in skip:
            remaining.append(f"{m.game}\t{m.resref}")

    remaining.sort()

    if args.max and len(remaining) > args.max:
        remaining = remaining[:args.max]

    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODO_FILE.write_text("\n".join(remaining))

    print(f"  Already rendered : {len(skip)}")
    print(f"  Remaining modules: {len(remaining)}")
    print(f"  TODO file        : {TODO_FILE}", flush=True)

    # Explicitly free library from memory before phase 2
    del lib
    gc.collect()

    return len(remaining)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: read TODO list, spawn subprocesses in batches
# ─────────────────────────────────────────────────────────────────────────────

def phase2_render(args):
    """Read TODO_FILE and dispatch batches to batch_modules_slice.py."""
    from tools.batch_render_all import OUT_DIR, K1_DIR, K2_DIR
    RENDERS_DIR = OUT_DIR / "renders"
    SHEETS_DIR  = OUT_DIR / "sheets"
    RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR = ROOT / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not TODO_FILE.exists():
        print("ERROR: TODO file not found. Run phase 1 first.", file=sys.stderr)
        sys.exit(1)

    lines = [l.strip() for l in TODO_FILE.read_text().splitlines() if l.strip()]
    if not lines:
        print("Nothing to do – all modules already rendered!")
        return

    # Parse lines: "GAME\tresref"
    todo = []
    for line in lines:
        if "\t" in line:
            game, resref = line.split("\t", 1)
            todo.append((resref.strip(), game.strip()))
        else:
            todo.append((line.strip(), "both"))

    total = len(todo)
    batch_size = args.batch_size
    batches = [todo[i : i + batch_size] for i in range(0, total, batch_size)]

    print(f"\nPhase 2: rendering {total} modules in {len(batches)} batches "
          f"(batch_size={batch_size})…\n", flush=True)

    t_start = time.time()
    total_processed = total_rendered = total_failed = 0
    slice_script = ROOT / "tools" / "batch_modules_slice.py"

    for b_idx, batch in enumerate(batches):
        # Re-check which are already done (in case a previous slice rendered some)
        pending = []
        for resref, game in batch:
            key = f"{game}_{resref}_front.png"
            if not (RENDERS_DIR / key).exists():
                pending.append((resref, game))

        if not pending:
            el = time.time() - t_start
            done = (b_idx + 1) * batch_size
            pct  = 100.0 * done / total
            print(f"  Batch {b_idx+1:4d}/{len(batches)}  [{done:4d}/{total}] "
                  f"{pct:5.1f}%  el={el:.0f}s  [all already rendered, skip]", flush=True)
            continue

        # Split by game
        k1_batch = [r for r, g in pending if g == "K1"]
        k2_batch = [r for r, g in pending if g == "K2"]
        both_batch = [r for r, g in pending if g == "both"]

        el = time.time() - t_start
        done = b_idx * batch_size
        pct  = 100.0 * done / total
        eta  = (el / max(done, 1)) * (total - done) if done else 0
        print(
            f"  Batch {b_idx+1:4d}/{len(batches)}"
            f"  [{done:4d}/{total}] {pct:5.1f}%"
            f"  el={el:.0f}s  ETA={eta:.0f}s"
            f"  ({len(k1_batch)}×K1  {len(k2_batch)}×K2"
            + (f"  {len(both_batch)}×both" if both_batch else "") + ")",
            flush=True
        )

        def run_slice(resrefs, game_flag, retry=True):
            if not resrefs:
                return 0, 0
            tmp = LOG_DIR / f"_orch_slice_{os.getpid()}_{b_idx}_{game_flag}.txt"
            tmp.write_text("\n".join(resrefs))
            cmd = [
                sys.executable, str(slice_script),
                "--resref-file", str(tmp),
                "--game", game_flag,
                "--k1", args.k1,
                "--k2", args.k2,
                "--render-size", str(args.render_size),
            ]
            if args.dry_run:
                cmd.append("--no-render")

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=240
                )
            except subprocess.TimeoutExpired:
                print(f"    [TIMEOUT] slice {game_flag} batch {b_idx+1}", flush=True)
                tmp.unlink(missing_ok=True)
                return 0, 0

            tmp.unlink(missing_ok=True)

            # OOM kill (exit -9 or 137) → retry once with smaller sub-batches
            if result.returncode in (-9, -15, 137) and retry:
                print(f"    [OOM] slice {game_flag} batch {b_idx+1} killed – "
                      f"retrying {len(resrefs)} models in 2 halves…", flush=True)
                time.sleep(3)  # brief pause for memory to settle
                half = max(1, len(resrefs) // 2)
                n1, r1 = run_slice(resrefs[:half],   game_flag, retry=False)
                n2, r2 = run_slice(resrefs[half:],   game_flag, retry=False)
                return n1 + n2, r1 + r2

            proc_n = rend_n = 0
            for line in result.stdout.splitlines():
                if "Batch slice done" in line:
                    m = re.search(
                        r"OK=(\d+)\s+WARN=(\d+)\s+FAIL=(\d+)\s+Rendered=(\d+)", line
                    )
                    if m:
                        proc_n = int(m.group(1)) + int(m.group(2)) + int(m.group(3))
                        rend_n = int(m.group(4))

            if result.returncode not in (0, None):
                err_log = LOG_DIR / f"_slice_err_{b_idx}_{game_flag}.log"
                err_log.write_text(
                    (result.stderr or "")[-4000:]
                )
                print(f"    [WARN] slice exited {result.returncode}. "
                      f"Log: {err_log}", flush=True)

            return proc_n, rend_n

        n1, r1 = run_slice(k1_batch, "K1")
        n2, r2 = run_slice(k2_batch, "K2")
        nb, rb = run_slice(both_batch, "both")

        total_processed += n1 + n2 + nb
        total_rendered  += r1 + r2 + rb

    elapsed = time.time() - t_start
    front_count = sum(1 for f in RENDERS_DIR.iterdir()
                      if f.name.endswith("_front.png")
                      and "_" in f.name)

    print(f"\n{'=' * 70}")
    print(f"Orchestrator complete: {total} modules queued, {elapsed:.1f}s")
    print(f"  Processed : {total_processed}")
    print(f"  Rendered  : {total_rendered}")
    print(f"  Total front renders in dir: {front_count}")
    print(f"  ms/model  : {1000*elapsed/max(total, 1):.0f}")

    if not args.dry_run:
        _rebuild_module_sheet(OUT_DIR, RENDERS_DIR, SHEETS_DIR)


def _rebuild_module_sheet(OUT_DIR, RENDERS_DIR, SHEETS_DIR):
    """Rebuild the modules contact sheet – streaming, no FD leaks."""
    import math
    from tools.batch_render_all import categorize
    from PIL import Image, ImageDraw

    THUMB = 64
    COLS  = 30
    LABEL_H = 14

    # Collect file paths only (don't open yet)
    paths = []
    for f in sorted(RENDERS_DIR.iterdir()):
        if not f.name.endswith("_front.png"):
            continue
        name   = f.name[:-len("_front.png")]
        resref = name[3:] if name.startswith(("K1_", "K2_")) else name
        if categorize(resref) != "modules":
            continue
        paths.append((name[:12], f))

    if not paths:
        print("  No module renders found for contact sheet.")
        return

    rows  = math.ceil(len(paths) / COLS)
    sheet = Image.new("RGB", (COLS * THUMB, rows * (THUMB + LABEL_H)), (20, 20, 20))
    draw  = ImageDraw.Draw(sheet)

    for i, (label, fpath) in enumerate(paths):
        x = (i % COLS) * THUMB
        y = (i // COLS) * (THUMB + LABEL_H)
        try:
            with Image.open(fpath) as img:
                th = img.convert("RGB").resize((THUMB, THUMB), Image.LANCZOS)
                sheet.paste(th, (x, y))
        except Exception:
            pass
        draw.text((x + 2, y + THUMB + 1), label, fill=(200, 200, 200))

    sheet_p = SHEETS_DIR / "modules.png"
    sheet_p.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(sheet_p))
    print(f"Contact sheet: {sheet_p} ({len(paths)} models)")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Memory-safe module render orchestrator (2-phase)"
    )
    ap.add_argument("--game", choices=["K1", "K2", "both"], default="both")
    ap.add_argument("--k1",   default=None)
    ap.add_argument("--k2",   default=None)
    ap.add_argument("--batch-size", type=int, default=15,
                    help="Models per subprocess batch (default 15)")
    ap.add_argument("--render-size", type=int, default=128)
    ap.add_argument("--dry-run", action="store_true",
                    help="Audit only, no GPU rendering")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--phase", type=int, choices=[1, 2], default=0,
                    help="Run only phase 1 (scan) or phase 2 (render). "
                         "Default 0 = both.")
    args = ap.parse_args()

    # Resolve default dirs after imports
    from tools.batch_render_all import K1_DIR, K2_DIR
    if args.k1 is None: args.k1 = K1_DIR
    if args.k2 is None: args.k2 = K2_DIR

    print("=" * 70)
    print("GhostRigger Module Render Orchestrator (2-phase)")
    print(f"  game={args.game}  batch_size={args.batch_size}"
          f"  render_size={args.render_size}"
          + ("  [DRY RUN]" if args.dry_run else ""))
    print("=" * 70, flush=True)

    if args.phase in (0, 1):
        n = phase1_build_todo(args)
        if n == 0:
            print("All modules already rendered – nothing to do!")
            return
        if args.phase == 0:
            # Re-exec this script as phase 2 only, shedding all Phase 1 memory
            # Build the same argv but replace/add --phase 2
            new_argv = [sys.executable, str(Path(__file__))]
            new_argv += ["--game", args.game,
                         "--k1", args.k1, "--k2", args.k2,
                         "--batch-size", str(args.batch_size),
                         "--render-size", str(args.render_size),
                         "--phase", "2"]
            if args.dry_run:
                new_argv.append("--dry-run")
            if args.max:
                new_argv += ["--max", str(args.max)]
            print(f"\nPhase 1 complete – re-exec as phase 2 to free library memory…",
                  flush=True)
            os.execv(sys.executable, new_argv)
            # execv replaces current process – no return

    if args.phase in (0, 2):
        phase2_render(args)


if __name__ == "__main__":
    main()
