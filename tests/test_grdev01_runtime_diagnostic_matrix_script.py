from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "grdev01_runtime_diagnostic_matrix.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("grdev01_runtime_diagnostic_matrix_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_t2601_runtime_matrix_identifies_active_installed_package(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    active = game_root / "Modules" / "grdev01.mod"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"MOD V1.0\x00\x00\x00\x00" + b"active package")
    artifact = tmp_path / "artifact" / "grdev01.mod"
    artifact.parent.mkdir()
    artifact.write_bytes(active.read_bytes())
    monkeypatch.setattr(
        module,
        "DIAGNOSTIC_VARIANTS",
        (
            module.DIAGNOSTIC_VARIANTS[0],
            {
                "id": "ghostrigger_stock_area_mod",
                "label": "GhostRigger-built stock-area MOD baseline",
                "path_kind": "artifact",
                "relative_path": str(artifact),
                "proves": "test",
                "expected_header": "MOD V1.0",
            },
            module.DIAGNOSTIC_VARIANTS[2],
            module.DIAGNOSTIC_VARIANTS[3],
            module.DIAGNOSTIC_VARIANTS[4],
            module.DIAGNOSTIC_VARIANTS[-1],
        ),
    )

    matrix = module.build_matrix(game_root)

    assert matrix["ok"] is True
    assert matrix["active_installed"]["exists"] is True
    assert matrix["active_installed"]["header"].startswith("MOD V1.0")
    assert matrix["variants"][1]["is_active_install"] is True


def test_t2601_runtime_matrix_warns_when_active_package_is_exact_rim(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    active = game_root / "Modules" / "grdev01.mod"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")

    matrix = module.build_matrix(game_root)

    assert matrix["ok"] is True
    assert matrix["active_installed"]["header"].startswith("RIM V1.0")
    assert any("RIM-style diagnostic" in warning for warning in matrix["warnings"])


def test_t2601_runtime_matrix_includes_renamed_root_bridge_variants(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    active = game_root / "Modules" / "grdev01.rim"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")

    matrix = module.build_matrix(game_root, tmp_path / "outcomes")
    variant_ids = {item["id"] for item in matrix["variants"]}

    assert "renamed_root_minimal_git" in variant_ids
    assert "renamed_root_minimal_git_placeable" in variant_ids
    assert "renamed_root_scriptless_dual_minimal_git" in variant_ids
    assert "renamed_root_scriptless_dual_minimal_git_placeable" in variant_ids
    assert any("renamed-root-minimal" in action for action in matrix["next_actions"])
    assert any("renamed-root-minimal-placeable" in action for action in matrix["next_actions"])
    assert any("renamed-root-scriptless-dual-minimal" in action for action in matrix["next_actions"])


def test_t2601_runtime_matrix_can_treat_grdev01_rim_as_active(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    active = game_root / "Modules" / "grdev01.rim"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")

    matrix = module.build_matrix(game_root)

    assert matrix["ok"] is True
    assert matrix["active_installed"]["path"].endswith("grdev01.rim")
    assert matrix["active_installed"]["header"].startswith("RIM V1.0")


def test_t2601_runtime_matrix_uses_outcomes_without_confusing_mod_and_rim(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    rim_bytes = b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package"
    old_mod = modules_dir / "grdev01.mod"
    active_rim = modules_dir / "grdev01.rim"
    active_rim.write_bytes(rim_bytes)

    outcomes_dir = tmp_path / "outcomes"
    outcomes_dir.mkdir()
    outcomes_dir.joinpath("20260618_184910_active_installed.json").write_text(
        json.dumps(
            {
                "kind": "grdev01_runtime_diagnostic_outcome",
                "generated_at": "2026-06-19T01:49:10Z",
                "variant_id": "active_installed",
                "outcome": "crashed",
                "notes": "RIM bytes installed as grdev01.mod crashed.",
                "active_package": {
                    "path": str(old_mod),
                    "sha256": module._sha256(active_rim),
                    "header": module._header(active_rim),
                    "size": len(rim_bytes),
                },
                "recommended_next": "Install exact-rim-file next.",
            }
        ),
        encoding="utf-8",
    )

    matrix = module.build_matrix(game_root, outcomes_dir)

    assert matrix["ok"] is True
    assert matrix["outcome_summary"]["records_checked"] == 1
    assert matrix["outcome_summary"]["latest_by_variant"]["active_installed"]["outcome"] == "crashed"
    assert matrix["outcome_summary"]["latest_for_active_package"] is None
    assert "no recorded in-game outcome" in matrix["outcome_summary"]["recommended_next_from_outcomes"]
    assert "no recorded in-game outcome" in matrix["next_actions"][0]


def test_t2601_runtime_matrix_reports_latest_outcome_for_current_active_package(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    active = game_root / "Modules" / "grdev01.rim"
    active.parent.mkdir(parents=True)
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")

    outcomes_dir = tmp_path / "outcomes"
    outcomes_dir.mkdir()
    outcomes_dir.joinpath("20260618_190000_active_installed.json").write_text(
        json.dumps(
            {
                "kind": "grdev01_runtime_diagnostic_outcome",
                "generated_at": "2026-06-19T02:00:00Z",
                "variant_id": "active_installed",
                "outcome": "loaded",
                "active_package": {
                    "path": str(active),
                    "sha256": module._sha256(active),
                    "header": module._header(active),
                    "size": active.stat().st_size,
                    "companions": [
                        {
                            "name": "grdev01_s.rim",
                            "installed_path": str(game_root / "Modules" / "grdev01_s.rim"),
                            "installed_exists": False,
                            "installed_sha256": "",
                            "installed_header": "",
                        }
                    ],
                },
                "recommended_next": "Install the authored no-marker generated-room candidate next.",
            }
        ),
        encoding="utf-8",
    )

    matrix = module.build_matrix(game_root, outcomes_dir)

    assert matrix["outcome_summary"]["latest_for_active_package"]["outcome"] == "loaded"
    assert matrix["next_actions"][0] == "Install the authored no-marker generated-room candidate next."


def test_t2601_runtime_matrix_requires_matching_static_sidecar_for_rim_pair_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    active = modules_dir / "grdev01.rim"
    active_static = modules_dir / "grdev01_s.rim"
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")
    active_static.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock static rim package")
    artifact = tmp_path / "artifact" / "grdev01.rim"
    artifact_static = tmp_path / "artifact" / "grdev01_s.rim"
    artifact.parent.mkdir()
    artifact.write_bytes(active.read_bytes())
    artifact_static.write_bytes(active_static.read_bytes())
    monkeypatch.setattr(
        module,
        "DIAGNOSTIC_VARIANTS",
        (
            module.DIAGNOSTIC_VARIANTS[0],
            module.DIAGNOSTIC_VARIANTS[1],
            module.DIAGNOSTIC_VARIANTS[2],
            module.DIAGNOSTIC_VARIANTS[3],
            {
                "id": "exact_stock_rim_pair",
                "label": "pair",
                "path_kind": "artifact",
                "relative_path": str(artifact),
                "companion_relative_paths": str(artifact_static),
                "installed_companion_names": "grdev01_s.rim",
                "proves": "test",
                "expected_header": "RIM V1.0",
                "expected_active_filename": "grdev01.rim",
            },
            module.DIAGNOSTIC_VARIANTS[-1],
        ),
    )

    matrix = module.build_matrix(game_root, tmp_path / "outcomes")
    pair = next(item for item in matrix["variants"] if item["id"] == "exact_stock_rim_pair")
    root_only = next(item for item in matrix["variants"] if item["id"] == "exact_stock_rim_custom_filename")

    assert pair["is_active_install"] is True
    assert root_only["is_active_install"] is False
    assert pair["companions"][0]["installed_exists"] is True
    assert pair["companions"][0]["artifact_sha256"] == pair["companions"][0]["installed_sha256"]

    active_static.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"different static rim")
    matrix = module.build_matrix(game_root, tmp_path / "outcomes")
    pair = next(item for item in matrix["variants"] if item["id"] == "exact_stock_rim_pair")
    assert pair["is_active_install"] is False


def test_t2601_runtime_matrix_does_not_apply_root_only_outcome_to_rim_pair(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    active = modules_dir / "grdev01.rim"
    active_static = modules_dir / "grdev01_s.rim"
    active.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock rim package")
    active_static.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock static rim package")

    outcomes_dir = tmp_path / "outcomes"
    outcomes_dir.mkdir()
    outcomes_dir.joinpath("20260618_200000_active_installed.json").write_text(
        json.dumps(
            {
                "kind": "grdev01_runtime_diagnostic_outcome",
                "generated_at": "2026-06-19T03:00:00Z",
                "variant_id": "active_installed",
                "outcome": "crashed",
                "active_package": {
                    "path": str(active),
                    "sha256": module._sha256(active),
                    "header": module._header(active),
                    "size": active.stat().st_size,
                    "companions": [
                        {
                            "name": "grdev01_s.rim",
                            "installed_path": str(active_static),
                            "installed_exists": False,
                            "installed_sha256": "",
                            "installed_header": "",
                        }
                    ],
                },
                "recommended_next": "Install exact-rim-pair next.",
            }
        ),
        encoding="utf-8",
    )

    matrix = module.build_matrix(game_root, outcomes_dir)

    assert matrix["outcome_summary"]["latest_by_variant"]["active_installed"]["outcome"] == "crashed"
    assert matrix["outcome_summary"]["latest_for_active_package"] is None
    assert "no recorded in-game outcome" in matrix["next_actions"][0]
