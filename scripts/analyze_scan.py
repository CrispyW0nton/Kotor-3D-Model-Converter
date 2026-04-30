"""Categorize full_scan_results.json failures for Phase 4 triage."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN = ROOT / "exports" / "full_scan_results.json"
DEFAULT_OUT = ROOT / "exports" / "failure_analysis.json"


def categorize_row(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (category_tags, discrepancy_strings)."""
    game = row.get("game", "")
    resref = row.get("resref", "")
    errs = row.get("errors") or []
    disc_raw = row.get("discrepancies") or []
    tags: list[str] = []

    discrepancies: list[str] = []

    missing = row.get("missing_in_ghostrigger") or []
    extra = row.get("extra_in_ghostrigger") or []
    n_pk = row.get("node_count_pykotor")
    n_gr = row.get("node_count_ghostrigger")

    if errs:
        tags.append("load_error")
        for e in errs:
            discrepancies.append(f"error: {e}")

    if missing or extra:
        tags.append("node_count_mismatch")
        if missing:
            discrepancies.append(f"missing_in_ghostrigger ({len(missing)}): " + ",".join(missing[:12]))
        if extra:
            discrepancies.append(f"extra_in_ghostrigger ({len(extra)}): " + ",".join(extra[:12]))
        if n_pk is not None and n_gr is not None:
            discrepancies.append(f"node_count pykotor={n_pk} ghostrigger={n_gr}")

    for d in disc_raw:
        if not isinstance(d, dict):
            continue
        fld = str(d.get("field", "") or "").lower()
        node = str(d.get("node", "") or "")
        pv = d.get("pykotor")
        gv = d.get("ghostrigger")
        discrepancies.append(f"{node}.{d.get('field')}: pykotor={pv} ghostrigger={gv}")
        if fld in ("vertex_count", "face_count"):
            tags.append("vertex_count_mismatch")
        if fld == "orientation":
            sev = str(d.get("severity", "") or "").upper()
            if sev == "MEDIUM":
                tags.append("quaternion_false_positive")
        if fld == "bone_map":
            tags.append("bone_map_mismatch")

    if row.get("texture_status") == "MISSING":
        tags.append("texture_missing")

    if row.get("has_skin"):
        ss = row.get("skinning_status")
        if ss == "OOB":
            tags.append("skinning_oob")
        elif ss == "WEIGHT":
            tags.append("skinning_weight")

    if game == "k2" and "vertex_count_mismatch" in tags:
        tags.append("k2_specific")

    tags = list(dict.fromkeys(tags))

    return tags, discrepancies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SCAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = list(data.get("results") or [])
    summary = data.get("summary") or {}

    total = len(rows)
    pipe_match = sum(1 for r in rows if r.get("pipeline_match") and not r.get("errors"))
    pipe_mis = sum(1 for r in rows if not r.get("pipeline_match") and not r.get("errors"))
    pipe_err = sum(1 for r in rows if r.get("errors"))
    tex_ok = sum(1 for r in rows if r.get("texture_status") == "OK")
    tex_miss = sum(1 for r in rows if r.get("texture_status") == "MISSING")

    skin_rows = [r for r in rows if r.get("has_skin")]
    skin_ok = sum(1 for r in skin_rows if r.get("skinning_status") == "OK")
    skin_issues = sum(1 for r in skin_rows if r.get("skinning_status") not in ("OK",))

    buckets: dict[str, list[str]] = defaultdict(list)
    details: list[dict[str, Any]] = []

    for row in rows:
        if row.get("pipeline_match") and not row.get("errors"):
            ts = row.get("texture_status")
            sk_ok = True
            if row.get("has_skin") and row.get("skinning_status") != "OK":
                sk_ok = False
            if ts == "OK" and sk_ok:
                continue

        cats, dq = categorize_row(row)
        if not cats:
            cats = ["uncategorized_issue"]
        key_out = f"{row.get('game')}:{row.get('resref')}"
        for c in cats:
            if key_out not in buckets[c]:
                buckets[c].append(key_out)

        primary = cats[0] if cats else "unknown"
        details.append(
            {
                "resref": row.get("resref"),
                "game": row.get("game"),
                "category": primary,
                "categories": cats,
                "discrepancies": dq[:32],
                "errors": row.get("errors") or [],
            },
        )

    out_payload = {
        "summary": {
            "total": total,
            "pipeline_match": pipe_match,
            "pipeline_mismatch": pipe_mis,
            "pipeline_error": pipe_err,
            "texture_ok": tex_ok,
            "texture_missing": tex_miss,
            "skinning_ok": skin_ok,
            "skinning_issues": skin_issues,
        },
        "failures_by_category": dict(sorted((k, v) for k, v in buckets.items())),
        "failure_details": details,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out_payload, indent=2) + "\n", encoding="utf-8")

    print("Failure analysis summary")
    print("=" * 50)
    for k, v in out_payload["summary"].items():
        print(f"  {k}: {v}")
    print("\nfailures_by_category:")
    for k, v in out_payload["failures_by_category"].items():
        print(f"  {k}: {len(v)} models")
    print(f"\nWritten {args.output}")


if __name__ == "__main__":
    main()
