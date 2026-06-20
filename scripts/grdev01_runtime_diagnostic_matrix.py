"""Report the ordered grdev01 runtime diagnostic matrix.

This script is intentionally read-only.  It does not install packages or mark
anything game-tested.  Its job is to prevent the grdev01 smoke test from
turning into guesswork by showing:

* which `Modules/grdev01.mod` is currently installed,
* which staged diagnostic packages are available,
* what each package is meant to prove, and
* which in-game test should be run next.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
DEFAULT_OUTCOMES_DIR = ROOT / "artifacts" / "map_studio" / "grdev01_runtime_outcomes"


DIAGNOSTIC_VARIANTS = (
    {
        "id": "active_installed",
        "label": "Currently installed grdev01 package",
        "path_kind": "installed",
        "relative_path": "",
        "proves": "Whatever grdev01 package is active in the KOTOR Modules folder is the next live warp target.",
        "expected_header": "",
        "expected_active_filename": "",
    },
    {
        "id": "ghostrigger_stock_area_mod",
        "label": "GhostRigger-built stock-area MOD baseline",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_stock_area_clone_runtime_baseline/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a GhostRigger-built MOD archive containing stock m02aa roots and rooms.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "exact_stock_rim_rename",
        "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.mod",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.mod",
        "proves": "KOTOR can load the stock RIM bytes through the custom grdev01 filename.",
        "expected_header": "RIM V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "exact_stock_rim_custom_filename",
        "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.rim",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.rim",
        "proves": "KOTOR can load the stock RIM bytes through a custom grdev01.rim filename when no grdev01.mod is present.",
        "expected_header": "RIM V1.0",
        "expected_active_filename": "grdev01.rim",
        "absent_installed_companion_names": "grdev01_s.rim",
    },
    {
        "id": "exact_stock_rim_pair",
        "label": "Byte-for-byte stock tar_m02aa RIM pair renamed to grdev01.rim and grdev01_s.rim",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.rim",
        "companion_relative_paths": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01_s.rim",
        "installed_companion_names": "grdev01_s.rim",
        "proves": "KOTOR can load the stock root/static RIM pair through custom grdev01 filenames.",
        "expected_header": "RIM V1.0",
        "expected_active_filename": "grdev01.rim",
    },
    {
        "id": "renamed_root_minimal_git",
        "label": "Renamed grdev01 root MOD using stock rooms and stripped stock GIT runtime lists",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_minimal_git/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a grdev01-root MOD with stock room geometry when dynamic stock GIT lists are stripped.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "renamed_root_minimal_git_placeable",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, and one plc_bench test placeable",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_minimal_git_placeable/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a grdev01-root MOD with stock room geometry and one safe authored placeable.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "renamed_root_scriptless_minimal_git",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, and no stock event scripts",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_scriptless_minimal_git/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a grdev01-root MOD with stock room geometry after stock area/module event scripts are cleared.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "renamed_root_scriptless_minimal_git_placeable",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, no stock event scripts, and one plc_bench test placeable",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_scriptless_minimal_git_placeable/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a scriptless grdev01-root stock-room MOD with one safe authored placeable.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "renamed_root_scriptless_dual_minimal_git",
        "label": "Dual-root scriptless MOD using grdev01 and stock m02aa roots with stripped GIT lists",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_dual_root_scriptless_minimal_git/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a scriptless MOD when both custom grdev01 and stock m02aa root resources are present.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "renamed_root_scriptless_dual_minimal_git_placeable",
        "label": "Dual-root scriptless MOD using grdev01 and stock m02aa roots with one plc_bench test placeable",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_dual_root_scriptless_minimal_git_placeable/install/Modules/grdev01.mod",
        "proves": "KOTOR can load a dual-root scriptless stock-room MOD with one safe authored placeable.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
    {
        "id": "authored_no_marker_candidate",
        "label": "Generated authored room without doorway marker",
        "path_kind": "artifact",
        "relative_path": "artifacts/map_studio/grdev01_authored_smoke_no_marker_candidate/install/Modules/grdev01.mod",
        "proves": "GhostRigger's generated MDL/MDX/WOK/ARE/GIT/IFO package can load once the container/root handoff is proven.",
        "expected_header": "MOD V1.0",
        "expected_active_filename": "grdev01.mod",
    },
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=DEFAULT_GAME_ROOT,
        help="KOTOR install root whose Modules/grdev01.mod is considered active.",
    )
    parser.add_argument(
        "--outcomes-dir",
        type=Path,
        default=DEFAULT_OUTCOMES_DIR,
        help="Directory containing recorded grdev01 runtime outcome JSON files.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable matrix.")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _header(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()[:16]
    return data.decode("ascii", errors="replace").rstrip("\x00")


def _active_installed_path(game_root_dir: Path) -> Path:
    modules_dir = game_root_dir / "Modules"
    mod_path = modules_dir / "grdev01.mod"
    rim_path = modules_dir / "grdev01.rim"
    if mod_path.exists():
        return mod_path
    if rim_path.exists():
        return rim_path
    return mod_path


def _variant_path(variant: dict[str, str], game_root_dir: Path) -> Path:
    if variant["path_kind"] == "installed":
        return _active_installed_path(game_root_dir)
    return ROOT / variant["relative_path"]


def _variant_companions(variant: dict[str, str], game_root_dir: Path) -> list[tuple[Path, Path]]:
    relative_paths = [item.strip() for item in variant.get("companion_relative_paths", "").split(",") if item.strip()]
    installed_names = [item.strip() for item in variant.get("installed_companion_names", "").split(",") if item.strip()]
    artifact_paths = [ROOT / item for item in relative_paths]
    installed_paths = [game_root_dir / "Modules" / item for item in installed_names]
    return list(zip(artifact_paths, installed_paths))


def _variant_absent_companions(variant: dict[str, str], game_root_dir: Path) -> list[Path]:
    installed_names = [item.strip() for item in variant.get("absent_installed_companion_names", "").split(",") if item.strip()]
    return [game_root_dir / "Modules" / item for item in installed_names]


def _active_companions(active_path: Path, game_root_dir: Path) -> list[dict[str, Any]]:
    if active_path.name.lower() != "grdev01.rim":
        return []
    static_path = game_root_dir / "Modules" / "grdev01_s.rim"
    installed_exists = static_path.exists()
    return [
        {
            "name": "grdev01_s.rim",
            "installed_path": str(static_path),
            "installed_exists": installed_exists,
            "installed_sha256": _sha256(static_path) if installed_exists else "",
            "installed_header": _header(static_path) if installed_exists else "",
        }
    ]


def _load_outcome_records(outcomes_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not outcomes_dir.exists():
        return records, warnings
    for path in sorted(outcomes_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive for hand-edited artifacts
            warnings.append(f"Could not read runtime outcome record {path}: {exc}")
            continue
        if not isinstance(data, dict):
            warnings.append(f"Ignoring runtime outcome record with non-object JSON: {path}")
            continue
        if data.get("kind") != "grdev01_runtime_diagnostic_outcome":
            continue
        data = dict(data)
        data["_record_path"] = str(path)
        records.append(data)
    records.sort(key=lambda item: str(item.get("generated_at", "")), reverse=True)
    return records, warnings


def _compact_outcome_record(record: dict[str, Any]) -> dict[str, Any]:
    active_package = record.get("active_package", {})
    if not isinstance(active_package, dict):
        active_package = {}
    return {
        "record_path": record.get("_record_path", ""),
        "generated_at": record.get("generated_at", ""),
        "variant_id": record.get("variant_id", ""),
        "outcome": record.get("outcome", ""),
        "notes": record.get("notes", ""),
        "recommended_next": record.get("recommended_next", ""),
        "active_package": {
            "path": active_package.get("path", ""),
            "sha256": active_package.get("sha256", ""),
            "header": active_package.get("header", ""),
            "size": active_package.get("size", 0),
            "companions": active_package.get("companions", []),
        },
    }


def _companion_key(companion: dict[str, Any]) -> tuple[str, bool, str, str]:
    path = str(
        companion.get("installed_path")
        or companion.get("path")
        or companion.get("artifact_path")
        or companion.get("name")
        or ""
    )
    name = Path(path).name.lower() if path else str(companion.get("name", "")).lower()
    exists = bool(companion.get("installed_exists", companion.get("exists", False)))
    sha = str(companion.get("installed_sha256", companion.get("sha256", "")))
    header = str(companion.get("installed_header", companion.get("header", "")))
    return (name, exists, sha if exists else "", header if exists else "")


def _package_key(package: dict[str, Any]) -> tuple[str, str, str, tuple[tuple[str, bool, str, str], ...]]:
    path = Path(str(package.get("path", ""))).name.lower()
    return (
        path,
        str(package.get("sha256", "")),
        str(package.get("header", "")),
        tuple(sorted(_companion_key(item) for item in package.get("companions", []) if isinstance(item, dict))),
    )


def _build_outcome_summary(active: dict[str, Any], outcomes_dir: Path) -> tuple[dict[str, Any], list[str]]:
    records, warnings = _load_outcome_records(outcomes_dir)
    latest_by_variant: dict[str, dict[str, Any]] = {}
    for record in records:
        variant_id = str(record.get("variant_id", ""))
        if variant_id and variant_id not in latest_by_variant:
            latest_by_variant[variant_id] = _compact_outcome_record(record)

    active_key = _package_key(active)
    latest_for_active: dict[str, Any] | None = None
    for record in records:
        active_package = record.get("active_package", {})
        if isinstance(active_package, dict) and _package_key(active_package) == active_key:
            latest_for_active = _compact_outcome_record(record)
            break

    recommended_next = ""
    if not active.get("exists"):
        recommended_next = "Install a grdev01 diagnostic package before running `warp grdev01`."
    elif latest_for_active:
        recommendation = str(latest_for_active.get("recommended_next", ""))
        outcome = str(latest_for_active.get("outcome", ""))
        if outcome == "loaded":
            recommended_next = recommendation or "Proceed to the next diagnostic package."
        elif outcome in {"crashed", "infinite_load"}:
            recommended_next = recommendation or "Do not retest the same package unchanged; inspect the failure before proceeding."
        elif outcome == "not_tested":
            recommended_next = "Run `warp grdev01` against the current active package."
    else:
        recommended_next = "Current active package has no recorded in-game outcome yet. Run `warp grdev01` and record the result."

    return (
        {
            "outcomes_dir": str(outcomes_dir),
            "records_checked": len(records),
            "latest_by_variant": latest_by_variant,
            "latest_for_active_package": latest_for_active,
            "recommended_next_from_outcomes": recommended_next,
        },
        warnings,
    )


def build_matrix(
    game_root_dir: Path = DEFAULT_GAME_ROOT,
    outcomes_dir: Path = DEFAULT_OUTCOMES_DIR,
) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    installed_hash = ""
    installed_filename = ""
    for variant in DIAGNOSTIC_VARIANTS:
        path = _variant_path(variant, game_root_dir)
        exists = path.exists()
        sha = _sha256(path) if exists else ""
        header = _header(path) if exists else ""
        companions: list[dict[str, Any]] = []
        companion_active = True
        absent_companion_active = True
        for artifact_path, installed_path in _variant_companions(variant, game_root_dir):
            artifact_exists = artifact_path.exists()
            installed_exists = installed_path.exists()
            artifact_sha = _sha256(artifact_path) if artifact_exists else ""
            installed_sha = _sha256(installed_path) if installed_exists else ""
            companion_active = companion_active and bool(artifact_sha and installed_sha and artifact_sha == installed_sha)
            companions.append(
                {
                    "artifact_path": str(artifact_path),
                    "installed_path": str(installed_path),
                    "artifact_exists": artifact_exists,
                    "installed_exists": installed_exists,
                    "artifact_sha256": artifact_sha,
                    "installed_sha256": installed_sha,
                    "artifact_header": _header(artifact_path) if artifact_exists else "",
                    "installed_header": _header(installed_path) if installed_exists else "",
                }
            )
        for absent_path in _variant_absent_companions(variant, game_root_dir):
            absent_exists = absent_path.exists()
            absent_companion_active = absent_companion_active and not absent_exists
            companions.append(
                {
                    "name": absent_path.name,
                    "installed_path": str(absent_path),
                    "installed_exists": absent_exists,
                    "must_be_absent": True,
                    "installed_sha256": _sha256(absent_path) if absent_exists else "",
                    "installed_header": _header(absent_path) if absent_exists else "",
                }
            )
        if variant["id"] == "active_installed":
            companions = _active_companions(path, game_root_dir)
        if variant["id"] == "active_installed":
            installed_hash = sha
            installed_filename = path.name.lower() if exists else ""
        variants.append(
            {
                "id": variant["id"],
                "label": variant["label"],
                "path": str(path),
                "exists": exists,
                "size": path.stat().st_size if exists else 0,
                "sha256": sha,
                "header": header,
                "expected_header": variant["expected_header"],
                "is_active_install": bool(
                    installed_hash
                    and sha == installed_hash
                    and (variant["id"] == "active_installed" or companion_active)
                    and absent_companion_active
                    and (
                        variant["id"] == "active_installed"
                        or not variant.get("expected_active_filename")
                        or installed_filename == variant["expected_active_filename"].lower()
                    )
                ),
                "proves": variant["proves"],
                "companions": companions,
            }
        )

    staged = {item["id"]: item for item in variants}
    active = staged["active_installed"]
    next_actions = [
        "Run `warp grdev01` against the currently installed package first.",
        "If the GhostRigger-built stock-area MOD crashes, install `exact-rim` and test `warp grdev01` again.",
        "If `exact-rim` crashes, install `exact-rim-file` so the stock bytes use a real grdev01.rim filename and test again.",
        "If root-only `exact-rim-file` crashes, install `exact-rim-pair` so grdev01.rim has its stock grdev01_s.rim sidecar and test again.",
        "If the stock RIM pair loads, install `renamed-root-minimal` to test a grdev01-root MOD with stock room geometry and stripped GIT lists.",
        "If `renamed-root-minimal` crashes, install `renamed-root-scriptless-minimal` to test the same stock-room MOD without stock event scripts.",
        "If `renamed-root-minimal` loads, install `renamed-root-minimal-placeable` to test one safe authored plc_bench placement.",
        "If `renamed-root-scriptless-minimal` loads, install `renamed-root-scriptless-placeable` to test one safe authored plc_bench placement without stock event scripts.",
        "If `renamed-root-scriptless-minimal` crashes, install `renamed-root-scriptless-dual-minimal` to test whether the engine needs both grdev01 and stock m02aa root resources present.",
        "If `renamed-root-scriptless-dual-minimal` loads, install `renamed-root-scriptless-dual-placeable` to test one safe authored plc_bench placement while both root sets are present.",
        "Only install the authored no-marker candidate after a stock/container diagnostic loads in-game.",
    ]
    warnings: list[str] = []
    if not active["exists"]:
        warnings.append("No active Modules/grdev01.mod is installed.")
    if active["exists"] and active["header"].startswith("RIM V1.0"):
        warnings.append(f"The active package is a RIM-style diagnostic ({Path(active['path']).name}), not the GhostRigger-built MOD baseline.")
    if "exact_stock_rim_rename" in staged and not staged["exact_stock_rim_rename"]["exists"]:
        warnings.append("The exact stock RIM-to-MOD rename package is not staged yet.")
    if "exact_stock_rim_custom_filename" in staged and not staged["exact_stock_rim_custom_filename"]["exists"]:
        warnings.append("The exact stock RIM filename package is not staged yet.")
    if "exact_stock_rim_pair" in staged and (
        not staged["exact_stock_rim_pair"]["exists"] or not staged["exact_stock_rim_pair"].get("companions")
    ):
        warnings.append("The exact stock RIM-pair package is not fully staged yet.")
    if "renamed_root_minimal_git" in staged and not staged["renamed_root_minimal_git"]["exists"]:
        warnings.append("The renamed-root minimal-GIT diagnostic package is not staged yet.")
    if "renamed_root_minimal_git_placeable" in staged and not staged["renamed_root_minimal_git_placeable"]["exists"]:
        warnings.append("The renamed-root minimal-GIT test-placeable diagnostic package is not staged yet.")
    if "renamed_root_scriptless_minimal_git" in staged and not staged["renamed_root_scriptless_minimal_git"]["exists"]:
        warnings.append("The renamed-root scriptless minimal-GIT diagnostic package is not staged yet.")
    if (
        "renamed_root_scriptless_minimal_git_placeable" in staged
        and not staged["renamed_root_scriptless_minimal_git_placeable"]["exists"]
    ):
        warnings.append("The renamed-root scriptless minimal-GIT test-placeable diagnostic package is not staged yet.")
    if "renamed_root_scriptless_dual_minimal_git" in staged and not staged["renamed_root_scriptless_dual_minimal_git"]["exists"]:
        warnings.append("The dual-root scriptless minimal-GIT diagnostic package is not staged yet.")
    if (
        "renamed_root_scriptless_dual_minimal_git_placeable" in staged
        and not staged["renamed_root_scriptless_dual_minimal_git_placeable"]["exists"]
    ):
        warnings.append("The dual-root scriptless minimal-GIT test-placeable diagnostic package is not staged yet.")
    if "authored_no_marker_candidate" in staged and not staged["authored_no_marker_candidate"]["exists"]:
        warnings.append("The authored no-marker generated package is not staged yet.")
    outcome_summary, outcome_warnings = _build_outcome_summary(active, outcomes_dir)
    warnings.extend(outcome_warnings)
    outcome_recommendation = outcome_summary.get("recommended_next_from_outcomes", "")
    if outcome_recommendation:
        next_actions.insert(0, str(outcome_recommendation))

    return {
        "ok": bool(active["exists"]),
        "game_root_dir": str(game_root_dir),
        "outcomes_dir": str(outcomes_dir),
        "active_installed": active,
        "variants": variants,
        "outcome_summary": outcome_summary,
        "next_actions": next_actions,
        "warnings": warnings,
    }


def _print_human(matrix: dict[str, Any]) -> None:
    print("grdev01 runtime diagnostic matrix")
    print(f"Game root: {matrix['game_root_dir']}")
    print(f"Outcomes: {matrix['outcomes_dir']}")
    print("")
    for variant in matrix["variants"]:
        status = "present" if variant["exists"] else "missing"
        active = " ACTIVE" if variant["is_active_install"] else ""
        print(f"- {variant['id']}: {status}{active}")
        print(f"  {variant['label']}")
        print(f"  Path: {variant['path']}")
        if variant["exists"]:
            print(f"  Header: {variant['header']}")
            print(f"  Size: {variant['size']}")
            print(f"  SHA256: {variant['sha256']}")
        print(f"  Proves: {variant['proves']}")
    if matrix["warnings"]:
        print("")
        print("Warnings:")
        for warning in matrix["warnings"]:
            print(f"- {warning}")
    outcome_summary = matrix.get("outcome_summary", {})
    latest_for_active = outcome_summary.get("latest_for_active_package")
    print("")
    print("Recorded outcomes:")
    print(f"- Records checked: {outcome_summary.get('records_checked', 0)}")
    if latest_for_active:
        print(
            "- Current active package latest result: "
            f"{latest_for_active.get('outcome')} ({latest_for_active.get('generated_at')})"
        )
    else:
        print("- Current active package latest result: not recorded")
    print("")
    print("Next actions:")
    for action in matrix["next_actions"]:
        print(f"- {action}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    matrix = build_matrix(args.game_root_dir, args.outcomes_dir)
    if args.json:
        print(json.dumps(matrix, indent=2))
    else:
        _print_human(matrix)
    return 0 if matrix["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
