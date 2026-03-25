#!/usr/bin/env python3
"""
merge_results.py
================
Merges the full structural audit (results_full.json) with the actual
render status (scanned from renders/ directory) to produce a single
authoritative results_merged.json plus a clean text summary.

Usage:
    python3 tools/merge_results.py
    python3 tools/merge_results.py --out audit_output/my_results/
"""

import sys, os, json, argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.batch_render_all import OUT_DIR, categorize


def main():
    ap = argparse.ArgumentParser(description="Merge audit + render results")
    ap.add_argument("--audit", default=str(OUT_DIR / "results_full.json"),
                    help="Path to full audit JSON (default: results_full.json)")
    ap.add_argument("--renders", default=str(OUT_DIR / "renders"),
                    help="Path to renders directory")
    ap.add_argument("--out", default=str(OUT_DIR),
                    help="Output directory")
    args = ap.parse_args()

    audit_path   = Path(args.audit)
    renders_dir  = Path(args.renders)
    out_dir      = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load audit ────────────────────────────────────────────────────────────
    if not audit_path.exists():
        print(f"ERROR: audit file not found: {audit_path}")
        sys.exit(1)

    print(f"Loading audit: {audit_path} …", flush=True)
    with open(audit_path) as f:
        records = json.load(f)
    print(f"  {len(records)} records loaded", flush=True)

    # ── Scan renders ──────────────────────────────────────────────────────────
    rendered_front = set()
    rendered_back  = set()
    if renders_dir.exists():
        for fn in renders_dir.iterdir():
            name = fn.name
            if name.endswith("_front.png"):
                rendered_front.add(name[:-len("_front.png")])
            elif name.endswith("_back.png"):
                rendered_back.add(name[:-len("_back.png")])
    print(f"  {len(rendered_front)} front renders found", flush=True)

    # ── Merge ─────────────────────────────────────────────────────────────────
    for r in records:
        key = f"{r['game']}_{r['resref']}"
        r["render_front"] = (key in rendered_front)
        r["render_back"]  = (key in rendered_back)
        r["render_ok"]    = r["render_front"]  # front view = success signal

    # ── Statistics ────────────────────────────────────────────────────────────
    total   = len(records)
    ok      = sum(1 for r in records if r["health"] == "OK")
    warn    = sum(1 for r in records if r["health"] == "WARN")
    fail    = sum(1 for r in records if r["health"] == "FAIL")
    rend_ok = sum(1 for r in records if r["render_ok"])
    rend_no = total - rend_ok

    # Per-category breakdown
    cat_stats = defaultdict(lambda: {"total": 0, "ok": 0, "warn": 0,
                                      "fail": 0, "rendered": 0, "tris": 0})
    for r in records:
        # Always re-categorize from the resref using current rules (ignores stale
        # "category" field that may have been written with old prefix rules).
        cat = categorize(r["resref"])
        s   = cat_stats[cat]
        s["total"]    += 1
        s["tris"]     += r.get("tri_count", 0)
        s["rendered"] += 1 if r["render_ok"] else 0
        h = r.get("health", "?")
        if h == "OK":   s["ok"]   += 1
        elif h == "WARN": s["warn"] += 1
        else:           s["fail"] += 1

    # ── Save merged JSON ──────────────────────────────────────────────────────
    merged_path = out_dir / "results_merged.json"
    with open(merged_path, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"\nMerged JSON: {merged_path} ({total} records)")

    # ── Write summary ─────────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 70)
    lines.append("GhostRigger – Full Audit + Render Summary")
    lines.append("=" * 70)
    lines.append(f"  Total models  : {total:,}")
    lines.append(f"  Parse OK      : {ok:,}  ({100*ok/total:.1f}%)")
    lines.append(f"  Parse WARN    : {warn:,}  ({100*warn/total:.1f}%)")
    lines.append(f"  Parse FAIL    : {fail:,}")
    lines.append(f"  Rendered      : {rend_ok:,}  ({100*rend_ok/total:.1f}%)")
    lines.append(f"  Not rendered  : {rend_no:,}")
    lines.append("")

    # Category table
    col_w = max(len(c) for c in cat_stats) + 2
    lines.append(f"  {'Category':{col_w}} {'Total':>7} {'OK':>6} {'WARN':>6} "
                 f"{'FAIL':>5} {'Rend':>6} {'Tris':>12}")
    lines.append("  " + "-" * (col_w + 50))
    for cat in sorted(cat_stats, key=lambda c: -cat_stats[c]["total"]):
        s = cat_stats[cat]
        lines.append(
            f"  {cat:{col_w}} {s['total']:>7,} {s['ok']:>6,} {s['warn']:>6,}"
            f" {s['fail']:>5,} {s['rendered']:>6,} {s['tris']:>12,}"
        )
    lines.append("")

    # UV issue summary
    uv_counts = defaultdict(int)
    for r in records:
        for issue in r.get("uv_issues", []):
            itype = issue.get("type", "?")
            uv_counts[itype] += 1
    if uv_counts:
        lines.append("  UV Issues:")
        for itype, cnt in sorted(uv_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    {itype:20s} {cnt:,}")
        lines.append("")

    summary = "\n".join(lines)
    summary_path = out_dir / "summary_merged.txt"
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"Summary     : {summary_path}")
    print()
    print(summary)


if __name__ == "__main__":
    main()
