"""Tiered MCP-driven model scan (no pytest collection overhead).

The default fast tier fully validates non-module models. Module/layout models
(*m* prefixes, e.g. M01aa_01a) use a separate lightweight load-and-node-count
tier because full per-node comparison can take several minutes per model.
"""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG_PATH = ROOT / ".cursor" / "mcp.json"
PYTHONPATHS = [ROOT / "src", ROOT]
if MCP_CONFIG_PATH.exists():
    _mcp_data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    _mcp_env = _mcp_data.get("mcpServers", {}).get("kotormcp", {}).get("env", {})
    if _mcp_env.get("K1_PATH"):
        os.environ.setdefault("K1_PATH", str(_mcp_env["K1_PATH"]))
    if _mcp_env.get("K2_PATH"):
        os.environ.setdefault("K2_PATH", str(_mcp_env["K2_PATH"]))
    PYTHONPATHS.extend(Path(p) for p in str(_mcp_env.get("PYTHONPATH", "")).split(";") if p)
for p in PYTHONPATHS:
    if p.exists():
        sys.path.insert(0, str(p))

os.environ.setdefault("K1_PATH", r"h:\steam\steamapps\common\swkotor")
os.environ.setdefault(
    "K2_PATH",
    r"h:\steam\steamapps\common\Knights of the Old Republic II",
)


MANIFEST_PATH = ROOT / "exports" / "scan_manifest.json"
LEGACY_RESULTS_PATH = ROOT / "exports" / "full_scan_results.json"
RESULTS_BY_TIER = {
    "fast": ROOT / "exports" / "full_scan_results_fast.json",
    "modules": ROOT / "exports" / "full_scan_results_modules.json",
    "full": ROOT / "exports" / "full_scan_results.json",
}
FLUSH_INTERVAL = 100
PROGRESS_INTERVAL = 50
MODULE_AREA_RE = re.compile(r"^\d{3}[a-z]", re.IGNORECASE)


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


def tier_match(resref: str, tier: str) -> bool:
    is_module = is_module_geometry_resref(resref)
    if tier == "fast":
        return not is_module
    if tier == "modules":
        return is_module
    return True


def is_module_geometry_resref(resref: str) -> bool:
    rl = resref.lower()
    return rl.startswith("m") or bool(MODULE_AREA_RE.match(rl))


def result_path_for_tier(tier: str) -> Path:
    return RESULTS_BY_TIER[tier]


def load_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("results", []))
    except json.JSONDecodeError:
        return []


def normalize_seed_row(row: dict[str, Any], tier: str) -> dict[str, Any]:
    seeded = dict(row)
    if "validation_mode" not in seeded:
        # Legacy full_scan_results.json rows came from the original full comparison,
        # even if they are now routed into the modules tier for result-file grouping.
        seeded["validation_mode"] = "full_compare"
    return seeded


def load_done_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for row in load_results(path):
        g = row.get("game", "")
        r = row.get("resref", "")
        if g and r:
            keys.add(f"{g}:{r}".lower())
    return keys


def save_results(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_full_scan_direct(
    game: str,
    resref: str,
    ghostrigger_tools: Any,
    validation_mode: str,
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

    try:
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
        else:
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
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")

    duration_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "game": game,
        "resref": resref,
        "validation_mode": validation_mode,
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


def run_module_scan_direct(
    game: str,
    resref: str,
    ghostrigger_tools: Any,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    errors: list[str] = []
    discrepancies: list[Any] = []
    pipeline_match = False
    has_skin = False
    node_count_pk = None
    node_count_gr = None

    try:
        raw = ghostrigger_tools.inspect_mdl(game, resref)
        gr = ghostrigger_tools.inspect_mdl_ghostrigger(game, resref)
        node_count_pk = raw.get("node_count")
        node_count_gr = gr.get("node_count")
        has_skin = bool(gr.get("skin_nodes"))
        pipeline_match = node_count_pk == node_count_gr
        if not pipeline_match:
            discrepancies.append(
                {
                    "field": "node_count",
                    "pykotor": node_count_pk,
                    "ghostrigger": node_count_gr,
                },
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "game": game,
        "resref": resref,
        "validation_mode": "module_light",
        "pipeline_match": pipeline_match,
        "texture_status": "SKIP" if not errors else "ERROR",
        "skinning_status": "SKIP" if not errors else "ERROR",
        "has_skin": has_skin,
        "node_count_pykotor": node_count_pk,
        "node_count_ghostrigger": node_count_gr,
        "missing_in_ghostrigger": [],
        "extra_in_ghostrigger": [],
        "discrepancies": discrepancies,
        "errors": errors,
        "duration_ms": duration_ms,
    }


def run_one_scan_direct(game: str, resref: str, tier: str, ghostrigger_tools: Any) -> dict[str, Any]:
    if tier == "modules":
        return run_module_scan_direct(game, resref, ghostrigger_tools)
    return run_full_scan_direct(game, resref, ghostrigger_tools, "full_compare")


def timeout_row(game: str, resref: str, tier: str, timeout_s: float, message: str) -> dict[str, Any]:
    return {
        "game": game,
        "resref": resref,
        "validation_mode": "module_light" if tier == "modules" else "full_compare",
        "pipeline_match": False,
        "texture_status": "ERROR",
        "skinning_status": "ERROR",
        "has_skin": False,
        "node_count_pykotor": None,
        "node_count_ghostrigger": None,
        "missing_in_ghostrigger": [],
        "extra_in_ghostrigger": [],
        "discrepancies": [],
        "errors": [message],
        "duration_ms": int(timeout_s * 1000),
        "timed_out": True,
    }


def _scan_one_model_worker(game: str, resref: str, tier: str, result_queue: Any) -> None:
    logging.basicConfig(level=logging.WARNING, force=True)
    logging.getLogger("src").setLevel(logging.WARNING)
    logging.getLogger("pykotor").setLevel(logging.WARNING)
    try:
        from kotormcp.tools import ghostrigger_tools as grt_mod

        result_queue.put(run_one_scan_direct(game, resref, tier, grt_mod))
    except Exception as exc:  # noqa: BLE001
        result_queue.put(timeout_row(game, resref, tier, 0.0, f"{type(exc).__name__}: {exc}"))


def run_one_scan(
    game: str,
    resref: str,
    tier: str,
    timeout_s: float,
    ghostrigger_tools: Any,
) -> dict[str, Any]:
    # Non-module fast-tier models reuse the current process so KotorMCP/PyKotor caches
    # stay warm. Full/module tiers use subprocess isolation because module geometry can
    # run for minutes or hang in native/resource loading paths.
    if tier == "fast":
        return run_one_scan_direct(game, resref, tier, ghostrigger_tools)

    result_queue: multiprocessing.Queue[Any] = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_scan_one_model_worker,
        args=(game, resref, tier, result_queue),
    )
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return timeout_row(game, resref, tier, timeout_s, f"TIMEOUT after {timeout_s:g}s")
    if result_queue.empty():
        return timeout_row(game, resref, tier, timeout_s, "Worker produced no result")
    return result_queue.get()


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

    skin_models = [
        r
        for r in results
        if r.get("has_skin") and r.get("skinning_status") != "SKIP"
    ]
    skin_y = len(skin_models)
    skin_ok = sum(1 for r in skin_models if r.get("skinning_status") == "OK")
    skin_oob = sum(1 for r in skin_models if r.get("skinning_status") == "OOB")
    skin_wt = sum(1 for r in skin_models if r.get("skinning_status") == "WEIGHT")
    full_validated = sum(1 for r in results if r.get("validation_mode") == "full_compare")
    module_validated = sum(1 for r in results if r.get("validation_mode") == "module_light")

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
        "full_validated": full_validated,
        "module_light_validated": module_validated,
    }


def print_summary_table(s: dict[str, Any]) -> None:
    total = max(s["total"], 1)
    pm = s["pipeline_match"]
    pmm = s["pipeline_mismatch"]
    pe = s["pipeline_error"]
    dash = "-" * 43
    dbl = "=" * 43
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
    print(f"    Full-compare models: {s.get('full_validated', 0):,}")
    print(f"    Module-light models: {s.get('module_light_validated', 0):,}")
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
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=("k1", "k2", "all"), default="all")
    parser.add_argument("--tier", choices=("fast", "modules", "full"), default="fast")
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
        default=60.0,
        help="Hard per-model timeout in seconds for isolated full/modules scans",
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

    results_path = result_path_for_tier(args.tier)
    pairs = [
        (g, r)
        for g, r in load_manifest_pairs(args.game, args.category)
        if tier_match(r, args.tier)
    ]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_total = int(manifest.get("total", len(pairs)))

    done: set[str] = set()
    existing_results: list[dict[str, Any]] = []
    if args.resume:
        if results_path.exists():
            existing_results = [
                normalize_seed_row(r, args.tier)
                for r in load_results(results_path)
                if tier_match(str(r.get("resref", "")), args.tier)
            ]
        elif LEGACY_RESULTS_PATH.exists() and results_path != LEGACY_RESULTS_PATH:
            existing_results = [
                normalize_seed_row(r, args.tier)
                for r in load_results(LEGACY_RESULTS_PATH)
                if tier_match(str(r.get("resref", "")), args.tier)
            ]
        done = {f"{r.get('game')}:{r.get('resref')}".lower() for r in existing_results}
    elif results_path.exists():
        results_path.unlink()

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
        "tier": args.tier,
        "resume": args.resume,
        "results": existing_results[:] if args.resume else [],
    }
    if args.resume and existing_results:
        payload["summary"] = summarize(payload["results"])
        if not results_path.exists():
            payload["seeded_from"] = str(LEGACY_RESULTS_PATH)
        else:
            payload["pruned_to_current_tier"] = True
        save_results(results_path, payload)

    n_total = len(pairs)
    n_done_before = len(done)
    processed_this_run = 0

    for game, resref in to_run:
        processed_this_run += 1
        if args.tier == "modules":
            print(
                f"[module] Starting {game}:{resref} (lightweight load + node count)...",
                flush=True,
            )
        if args.diag:
            print(
                f">> start {processed_this_run}/{len(to_run)} {game}:{resref}",
                flush=True,
            )
        row = run_one_scan(game, resref, args.tier, args.timeout, grt_mod)
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
            save_results(results_path, payload)

    payload["summary"] = summarize(payload["results"])
    if payload["results"]:
        last = payload["results"][-1]
        payload["last_resref"] = f"{last.get('game')}:{last.get('resref')}"
    save_results(results_path, payload)
    print_summary_table(payload["summary"])


if __name__ == "__main__":
    main()
