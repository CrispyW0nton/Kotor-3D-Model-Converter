"""Record the observed in-game outcome for a grdev01 runtime diagnostic.

This does not mark Map Studio game-tested.  It records crash-isolation evidence
for the currently active or selected diagnostic variant so the next step can be
chosen from facts instead of memory.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTCOMES = ("loaded", "crashed", "infinite_load", "not_tested")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="active_installed", help="Diagnostic variant id being recorded.")
    parser.add_argument("--outcome", choices=OUTCOMES, required=True, help="Observed KOTOR result after `warp grdev01`.")
    parser.add_argument("--notes", default="", help="Optional human notes about the result.")
    parser.add_argument("--evidence", type=Path, default=None, help="Optional screenshot/video/log path.")
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        help="KOTOR install root used to identify the active package.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON. Defaults to artifacts/map_studio/grdev01_runtime_outcomes/<timestamp>_<variant>.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _load_matrix(game_root_dir: Path) -> dict[str, Any]:
    import importlib.util

    matrix_script = ROOT / "scripts" / "grdev01_runtime_diagnostic_matrix.py"
    spec = importlib.util.spec_from_file_location("grdev01_runtime_diagnostic_matrix_for_outcome", matrix_script)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    matrix = module.build_matrix(game_root_dir)
    return matrix if isinstance(matrix, dict) else {}


def _default_output_path(variant: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_variant = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in variant)
    return ROOT / "artifacts" / "map_studio" / "grdev01_runtime_outcomes" / f"{timestamp}_{safe_variant}.json"


def _variant_from_matrix(matrix: dict[str, Any], variant_id: str) -> dict[str, Any]:
    for variant in matrix.get("variants", []):
        if variant.get("id") == variant_id:
            return variant
    if variant_id == "active_installed":
        return matrix.get("active_installed", {})
    return {}


def record_outcome(
    *,
    variant_id: str,
    outcome: str,
    game_root_dir: Path,
    output_path: Path | None = None,
    notes: str = "",
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    matrix = _load_matrix(game_root_dir)
    variant = _variant_from_matrix(matrix, variant_id)
    output = output_path or _default_output_path(variant_id)
    evidence_text = str(evidence_path) if evidence_path is not None else ""
    evidence_exists = bool(evidence_path and evidence_path.exists())
    blocking: list[str] = []
    warnings: list[str] = []
    if not matrix:
        blocking.append("Could not load grdev01 runtime diagnostic matrix.")
    if not variant:
        blocking.append(f"Unknown diagnostic variant id: {variant_id}")
    if evidence_path is not None and not evidence_exists:
        warnings.append(f"Evidence path does not exist yet: {evidence_path}")

    recommended_next = ""
    active_path = str(variant.get("path", ""))
    active_header = str(variant.get("header", ""))
    active_is_rim_mod = active_path.lower().endswith("grdev01.mod") and active_header.startswith("RIM V1.0")
    active_is_rim_file = active_path.lower().endswith("grdev01.rim") and active_header.startswith("RIM V1.0")
    active_has_static_rim_sidecar = any(
        isinstance(companion, dict)
        and str(companion.get("name") or Path(str(companion.get("installed_path", ""))).name).lower() == "grdev01_s.rim"
        and bool(companion.get("installed_exists"))
        for companion in variant.get("companions", [])
    )
    if outcome in {"crashed", "infinite_load"} and (
        variant_id == "exact_stock_rim_rename" or (variant_id == "active_installed" and active_is_rim_mod)
    ):
        recommended_next = (
            "Install `exact-rim-file` with scripts/install_grdev01_runtime_variant.py and test `warp grdev01` again."
        )
    elif outcome in {"crashed", "infinite_load"} and (
        variant_id == "exact_stock_rim_custom_filename"
        or (variant_id == "active_installed" and active_is_rim_file and not active_has_static_rim_sidecar)
    ):
        recommended_next = (
            "Install `exact-rim-pair` with scripts/install_grdev01_runtime_variant.py so grdev01.rim has its stock grdev01_s.rim sidecar, then test `warp grdev01` again."
        )
    elif outcome in {"crashed", "infinite_load"} and (
        variant_id == "exact_stock_rim_pair"
        or (variant_id == "active_installed" and active_is_rim_file and active_has_static_rim_sidecar)
    ):
        recommended_next = (
            "Install `renamed-root-minimal` with scripts/install_grdev01_runtime_variant.py to test a grdev01-root MOD with stock room geometry and stripped GIT lists."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_minimal_git":
        recommended_next = (
            "Install `renamed-root-scriptless-minimal` with scripts/install_grdev01_runtime_variant.py "
            "to test the same stock-room MOD after clearing stock Taris module/area event scripts."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_minimal_git_placeable":
        recommended_next = (
            "The no-placeable renamed-root diagnostic should be compared before generated geometry; if it loaded, investigate authored GIT placement/template handling."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_scriptless_minimal_git":
        recommended_next = (
            "Install `renamed-root-scriptless-dual-minimal` with scripts/install_grdev01_runtime_variant.py "
            "to test whether the engine needs both grdev01 and stock m02aa root resources present."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_scriptless_minimal_git_placeable":
        recommended_next = (
            "The scriptless no-placeable diagnostic should be compared first; if it loaded, investigate authored GIT placement/template handling."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_scriptless_dual_minimal_git":
        recommended_next = (
            "The dual-root scriptless stock-room MOD still failed. Investigate custom module filename/root handoff, "
            "IFO/ARE root names, and MOD-vs-RIM container behavior before generated geometry."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id == "renamed_root_scriptless_dual_minimal_git_placeable":
        recommended_next = (
            "The dual-root scriptless no-placeable diagnostic should be compared first; if it loaded, investigate authored GIT placement/template handling."
        )
    elif outcome in {"crashed", "infinite_load"} and variant_id in {"active_installed", "ghostrigger_stock_area_mod"}:
        recommended_next = (
            "Install `exact-rim` with scripts/install_grdev01_runtime_variant.py and test `warp grdev01` again."
        )
    elif outcome == "loaded" and (
        variant_id == "exact_stock_rim_pair"
        or (variant_id == "active_installed" and active_is_rim_file and active_has_static_rim_sidecar)
    ):
        recommended_next = (
            "Install `renamed-root-minimal` next to test a grdev01-root MOD with stock room geometry and stripped GIT lists."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_minimal_git":
        recommended_next = (
            "Install `renamed-root-minimal-placeable` next to verify one safe authored plc_bench placement in the custom-root stock room."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_minimal_git_placeable":
        recommended_next = (
            "Install the authored no-marker generated-room candidate next, then test floor, walkmesh, and placeable proof."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_scriptless_minimal_git":
        recommended_next = (
            "Install `renamed-root-scriptless-placeable` next to verify one safe authored plc_bench placement in the scriptless custom-root stock room."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_scriptless_minimal_git_placeable":
        recommended_next = (
            "Install the authored no-marker generated-room candidate next, then test floor, walkmesh, and placeable proof."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_scriptless_dual_minimal_git":
        recommended_next = (
            "Install `renamed-root-scriptless-dual-placeable` next to verify one safe authored plc_bench placement while both root sets are present."
        )
    elif outcome == "loaded" and variant_id == "renamed_root_scriptless_dual_minimal_git_placeable":
        recommended_next = (
            "Install the authored no-marker generated-room candidate next, then test floor, walkmesh, and placeable proof."
        )
    elif outcome == "loaded" and variant_id in {
        "active_installed",
        "ghostrigger_stock_area_mod",
        "exact_stock_rim_rename",
        "exact_stock_rim_custom_filename",
    }:
        recommended_next = (
            "Install the authored no-marker generated-room candidate next, then test floor, walkmesh, and placeable proof."
        )
    elif outcome == "loaded" and variant_id == "authored_no_marker_candidate":
        recommended_next = "Capture full smoke proof with floor, walkmesh, and test placeable evidence."
    elif outcome == "not_tested":
        recommended_next = "Run `warp grdev01` before choosing the next diagnostic package."

    record = {
        "kind": "grdev01_runtime_diagnostic_outcome",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "variant_id": variant_id,
        "outcome": outcome,
        "notes": notes,
        "evidence_path": evidence_text,
        "evidence_exists": evidence_exists,
        "active_package": variant,
        "matrix_next_actions": matrix.get("next_actions", []),
        "recommended_next": recommended_next,
        "warnings": warnings,
        "blocking_issues": blocking,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "ok": not blocking,
        "code": "recorded" if not blocking else "blocked",
        "output_path": str(output),
        "variant_id": variant_id,
        "outcome": outcome,
        "recommended_next": recommended_next,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _print_human(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 runtime outcome: {status} ({summary['code']})")
    print(f"Variant: {summary['variant_id']}")
    print(f"Outcome: {summary['outcome']}")
    print(f"Record: {summary['output_path']}")
    if summary["recommended_next"]:
        print(f"Recommended next: {summary['recommended_next']}")
    if summary["warnings"]:
        print("")
        print("Warnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")
    if summary["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = record_outcome(
        variant_id=str(args.variant),
        outcome=str(args.outcome),
        game_root_dir=args.game_root_dir,
        output_path=args.output,
        notes=str(args.notes),
        evidence_path=args.evidence,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
