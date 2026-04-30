"""Full MCP-driven scan over all manifest models (no pytest collection overhead).

Heavy module/layout models (*m* prefixes, e.g. M01aa_01a) can take multiple minutes each
(~4+ minutes for pipeline compare alone); long gaps between progress lines are normal.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KOTORMCP_ROOT = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\KotorMCP")
PYKOTOR_ROOT = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor")

PYTHONPATHS = [
    KOTORMCP_ROOT / "src",
    PYKOTOR_ROOT / "Libraries" / "PyKotor" / "src",
    PYKOTOR_ROOT / "Libraries" / "PyKotorGL" / "src",
    PYKOTOR_ROOT / "Libraries" / "Utility" / "src",
    ROOT,
]
for p in PYTHONPATHS:
    sys.path.insert(0, str(p))

os.environ.setdefault("K1_PATH", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
os.environ.setdefault(
    "K2_PATH",
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
)


MANIFEST_PATH = ROOT / "exports" / "scan_manifest.json"
RESULTS_PATH = ROOT / "exports" / "full_scan_results.json"
FLUSH_INTERVAL = 100
PROGRESS_INTERVAL = 50


def category_match(resref: str, cat: str) -> bool:
    rl = resref.lower()
    if cat == "all":
        return True
    if cat == "creatures":
        return rl.startswith("c_")
    if cat == "players":
        return rl.startswith("p")
    if cat == "npcs":
        return rl.startswith("n_")
    if cat == "modules":
        return rl.startswith("m")
    return True


def load_manifest_pairs(game: str, category: str) -> list[tuple[str, str]]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    if game in ("k1", "all"):
        for r in data.get("k1", {}).get("models", []):
            if category_match(r, category):
                pairs.append(("k1", r))
    if game in ("k2", "all"):
        for r in data.get("k2", {}).get("models", []):
            if category_match(r, category):
                pairs.append(("k2", r))
    return pairs


def load_done_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    keys: set[str] = set()
    for row in data.get("results", []):
        g = row.get("game", "")
        r = row.get("resref", "")
        if g and r:
            keys.add(f"{g}:{r}".lower())
    return keys


def save_results(payload: dict[str, Any]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_one_scan(
    game: str,
    resref: str,
    _timeout_s: float,
    ghostrigger_tools: Any,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    discrepancies: list[Any] = []
    errors: list[str] = []
    pipeline_match = False
    texture_status = "SKIP"
    skinning_status = "SKIP"
    has_skin = False
    missing_nodes: list[str] = []
    extra_nodes: list[str] = []
    node_count_pk = None
    node_count_gr = None

    def work() -> None:
        nonlocal pipeline_match, texture_status, skinning_status, has_skin, discrepancies
        nonlocal missing_nodes, extra_nodes, node_count_pk, node_count_gr
        cmp_ = ghostrigger_tools.compare_model_pipelines(game, resref)
        pipeline_match = bool(cmp_.get("match"))
        discrepancies = list(cmp_.get("discrepancies", []))
        missing_nodes = list(cmp_.get("missing_in_ghostrigger", []) or [])
        extra_nodes = list(cmp_.get("extra_in_ghostrigger", []) or [])
        node_count_pk = cmp_.get("node_count_pykotor")
        node_count_gr = cmp_.get("node_count_ghostrigger")

        tex = ghostrigger_tools.validate_textures(game, resref)
        if tex.get("all_loadable"):
            texture_status = "OK"
        elif not tex.get("all_found"):
            texture_status = "MISSING"
        else:
            texture_status = "ERROR"

        skin = ghostrigger_tools.inspect_skinning(game, resref)
        nodes = skin.get("skin_nodes") or []
        has_skin = len(nodes) > 0
        if not has_skin:
            skinning_status = "OK"
            return
        oob = sum(int(n.get("out_of_range_indices", 0) or 0) for n in nodes)
        bad_weight = False
        for n in nodes:
            wmin, wmax = n.get("weight_sum_range") or [0.0, 0.0]
            if wmin < 0.99 or wmax > 1.01:
                bad_weight = True
                break
        if oob > 0:
            skinning_status = "OOB"
        elif bad_weight:
            skinning_status = "WEIGHT"
        else:
            skinning_status = "OK"

    # Run synchronously on the main thread. A ThreadPoolExecutor + future.result(timeout=...)
    # deadlock was observed mid-scan (~model 451) alongside PyKotor/GhostRigger loaders: the
    # worker never completed and the timeout never fired. Hard timeouts need a subprocess/worker.
    try:
        work()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")

    duration_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "game": game,
        "resref": resref,
        "pipeline_match": pipeline_match,
        "texture_status": texture_status,
        "skinning_status": skinning_status,
        "has_skin": has_skin,
        "node_count_pykotor": node_count_pk,
        "node_count_ghostrigger": node_count_gr,
        "missing_in_ghostrigger": missing_nodes,
        "extra_in_ghostrigger": extra_nodes,
        "discrepancies": discrepancies,
        "errors": errors,
        "duration_ms": duration_ms,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    pipe_err_n = sum(1 for r in results if r.get("errors"))
    pipe_match = sum(
        (1 for r in results if r.get("pipeline_match") is True and not r.get("errors")),
    )
    pipe_mis = sum(
        (1 for r in results if not r.get("pipeline_match") and not r.get("errors")),
    )

    tex_ok = sum(1 for r in results if r.get("texture_status") == "OK")
    tex_miss = sum(1 for r in results if r.get("texture_status") == "MISSING")
    tex_err = sum(1 for r in results if r.get("texture_status") == "ERROR")

    skin_models = [r for r in results if r.get("has_skin")]
    skin_y = len(skin_models)
    skin_ok = sum(1 for r in skin_models if r.get("skinning_status") == "OK")
    skin_oob = sum(1 for r in skin_models if r.get("skinning_status") == "OOB")
    skin_wt = sum(1 for r in skin_models if r.get("skinning_status") == "WEIGHT")

    return {
        "total": total,
        "pipeline_match": pipe_match,
        "pipeline_mismatch": pipe_mis,
        "pipeline_error": pipe_err_n,
        "texture_ok": tex_ok,
        "texture_missing": tex_miss,
        "texture_error": tex_err,
        "skin_models": skin_y,
        "skinning_ok": skin_ok,
        "skinning_oob": skin_oob,
        "skinning_weight": skin_wt,
    }


def print_summary_table(s: dict[str, Any]) -> None:
    total = max(s["total"], 1)
    pm = s["pipeline_match"]
    pmm = s["pipeline_mismatch"]
    pe = s["pipeline_error"]
    dash = "\u2500" * 43
    dbl = "\u2550" * 43
    date_s = time.strftime("%Y-%m-%d")

    print()
    print(f"    {dbl}")
    print(f"    FULL SCAN RESULTS - {date_s}")
    print(f"    {dbl}")
    print(f"    Total models:     {s['total']:,}")
    print(
        f"    Pipeline MATCH:   {pm:,} ({100.0 * pm / total:.1f}%)",
    )
    print(f"    Pipeline MISMATCH:{pmm:>9,} ({100.0 * pmm / total:.1f}%)")
    print(f"    Pipeline ERROR:    {pe:>9,} ({100.0 * pe / total:.1f}%)")
    print(f"    {dash}")
    print(f"    Texture OK:       {s['texture_ok']:,}")
    print(f"    Texture MISSING:  {s['texture_missing']:,}")
    print(f"    Texture ERROR:    {s['texture_error']:,}")
    print(f"    {dash}")
    sy = max(s["skin_models"], 1)
    print(
        f"    Skinning OK:      {s['skinning_ok']:,} "
        f"(of {s['skin_models']:,} skin models)",
    )
    print(f"    Skinning OOB:     {s['skinning_oob']:,}")
    print(f"    Skinning WEIGHT:  {s['skinning_weight']:,}")
    print(f"    {dbl}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=("k1", "k2", "all"), default="all")
    parser.add_argument(
        "--category",
        choices=("creatures", "players", "npcs", "modules", "all"),
        default="all",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--diag",
        action="store_true",
        help="Print when each model scan starts (use to locate stalls)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Hard per-model timeout (disabled; loaders run synchronously - use Ctrl+C)",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=0,
        help="Scan at most N models from this run's remainder (after --resume filters); "
        "0 means no limit",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, force=True)
    logging.getLogger("src").setLevel(logging.WARNING)
    logging.getLogger("pykotor").setLevel(logging.WARNING)

    from kotormcp.tools import ghostrigger_tools as grt_mod

    pairs = load_manifest_pairs(args.game, args.category)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_total = int(manifest.get("total", len(pairs)))

    done: set[str] = set()
    existing_results: list[dict[str, Any]] = []
    if args.resume and RESULTS_PATH.exists():
        done = load_done_keys(RESULTS_PATH)
        try:
            existing_results = list(
                json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("results", []),
            )
        except json.JSONDecodeError:
            existing_results = []
    elif RESULTS_PATH.exists():
        RESULTS_PATH.unlink()

    to_run = [(g, r) for g, r in pairs if f"{g}:{r}".lower() not in done]
    if args.max_models > 0:
        to_run = to_run[: args.max_models]
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    payload: dict[str, Any] = {
        "generated": started,
        "manifest_total": manifest_total,
        "filtered_total": len(pairs),
        "filter_game": args.game,
        "filter_category": args.category,
        "resume": args.resume,
        "results": existing_results[:] if args.resume else [],
    }

    n_total = len(pairs)
    n_done_before = len(done)
    processed_this_run = 0

    for game, resref in to_run:
        processed_this_run += 1
        rl = resref.lower()
        if rl.startswith("m"):
            print(
                f"[module] Starting {game}:{resref} (large levels can take several minutes)...",
                flush=True,
            )
        if args.diag:
            print(
                f">> start {processed_this_run}/{len(to_run)} {game}:{resref}",
                flush=True,
            )
        row = run_one_scan(game, resref, args.timeout, grt_mod)
        payload["results"].append(row)

        pipe_label = (
            "ERROR"
            if row["errors"]
            else ("MATCH" if row["pipeline_match"] else "MISMATCH")
        )
        if processed_this_run % PROGRESS_INTERVAL == 0 or processed_this_run == len(to_run):
            elapsed = row["duration_ms"] / 1000.0
            cur = n_done_before + processed_this_run
            print(
                f"[{cur}/{n_total}] {game}:{resref} - "
                f"{pipe_label} ({elapsed:.2f}s)",
                flush=True,
            )

        if processed_this_run % FLUSH_INTERVAL == 0:
            payload["summary"] = summarize(payload["results"])
            payload["last_resref"] = f"{game}:{resref}"
            save_results(payload)

    payload["summary"] = summarize(payload["results"])
    save_results(payload)
    print_summary_table(payload["summary"])


if __name__ == "__main__":
    main()
