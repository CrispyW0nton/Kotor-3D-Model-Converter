from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record_grdev01_runtime_diagnostic_outcome.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("record_grdev01_runtime_diagnostic_outcome_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_matrix() -> dict:
    return {
        "next_actions": ["Run `warp grdev01`."],
        "active_installed": {
            "id": "active_installed",
            "header": "MOD V1.0",
            "path": "C:/KOTOR/Modules/grdev01.mod",
            "sha256": "activehash",
            "exists": True,
        },
        "variants": [
            {
                "id": "active_installed",
                "header": "MOD V1.0",
                "path": "C:/KOTOR/Modules/grdev01.mod",
                "sha256": "activehash",
                "exists": True,
            },
            {
                "id": "authored_no_marker_candidate",
                "header": "MOD V1.0",
                "sha256": "authoredhash",
                "exists": True,
            },
        ],
    }


def test_t2601_runtime_outcome_records_crash_and_recommends_exact_rim(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: _fake_matrix())

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="crashed",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
        notes="KOTOR crashed after warp.",
    )
    record = json.loads((tmp_path / "outcome.json").read_text(encoding="utf-8"))

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `exact-rim`")
    assert record["active_package"]["sha256"] == "activehash"
    assert record["outcome"] == "crashed"
    assert record["notes"] == "KOTOR crashed after warp."


def test_t2601_runtime_outcome_recommends_rim_file_after_rim_mod_crash(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["active_installed"]["header"] = "RIM V1.0"
    matrix["variants"][0]["header"] = "RIM V1.0"
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="crashed",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `exact-rim-file`")


def test_t2601_runtime_outcome_recommends_rim_pair_after_root_only_rim_file_crash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["active_installed"]["header"] = "RIM V1.0"
    matrix["active_installed"]["path"] = "C:/KOTOR/Modules/grdev01.rim"
    matrix["variants"][0]["header"] = "RIM V1.0"
    matrix["variants"][0]["path"] = "C:/KOTOR/Modules/grdev01.rim"
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="crashed",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `exact-rim-pair`")


def test_t2601_runtime_outcome_does_not_recommend_rim_pair_when_sidecar_already_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["active_installed"]["header"] = "RIM V1.0"
    matrix["active_installed"]["path"] = "C:/KOTOR/Modules/grdev01.rim"
    matrix["active_installed"]["companions"] = [
        {
            "name": "grdev01_s.rim",
            "installed_path": "C:/KOTOR/Modules/grdev01_s.rim",
            "installed_exists": True,
            "installed_sha256": "statichash",
            "installed_header": "RIM V1.0",
        }
    ]
    matrix["variants"][0] = dict(matrix["active_installed"])
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="crashed",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `renamed-root-minimal`")


def test_t2601_runtime_outcome_loaded_rim_pair_recommends_renamed_root_minimal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["active_installed"]["header"] = "RIM V1.0"
    matrix["active_installed"]["path"] = "C:/KOTOR/Modules/grdev01.rim"
    matrix["active_installed"]["companions"] = [
        {
            "name": "grdev01_s.rim",
            "installed_path": "C:/KOTOR/Modules/grdev01_s.rim",
            "installed_exists": True,
            "installed_sha256": "statichash",
            "installed_header": "RIM V1.0",
        }
    ]
    matrix["variants"][0] = dict(matrix["active_installed"])
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `renamed-root-minimal`")


def test_t2601_runtime_outcome_loaded_renamed_root_minimal_recommends_placeable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["variants"].append(
        {
            "id": "renamed_root_minimal_git",
            "header": "MOD V1.0",
            "path": "C:/KOTOR/Modules/grdev01.mod",
            "sha256": "renamedhash",
            "exists": True,
        }
    )
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="renamed_root_minimal_git",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `renamed-root-minimal-placeable`")


def test_t2601_runtime_outcome_loaded_renamed_root_placeable_recommends_authored(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["variants"].append(
        {
            "id": "renamed_root_minimal_git_placeable",
            "header": "MOD V1.0",
            "path": "C:/KOTOR/Modules/grdev01.mod",
            "sha256": "placeablehash",
            "exists": True,
        }
    )
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="renamed_root_minimal_git_placeable",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert "authored no-marker" in summary["recommended_next"]


def test_t2601_runtime_outcome_crashed_scriptless_recommends_dual_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["variants"].append(
        {
            "id": "renamed_root_scriptless_minimal_git",
            "header": "MOD V1.0",
            "path": "C:/KOTOR/Modules/grdev01.mod",
            "sha256": "scriptlesshash",
            "exists": True,
        }
    )
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="renamed_root_scriptless_minimal_git",
        outcome="crashed",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `renamed-root-scriptless-dual-minimal`")


def test_t2601_runtime_outcome_loaded_scriptless_dual_recommends_dual_placeable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    matrix = _fake_matrix()
    matrix["variants"].append(
        {
            "id": "renamed_root_scriptless_dual_minimal_git",
            "header": "MOD V1.0",
            "path": "C:/KOTOR/Modules/grdev01.mod",
            "sha256": "dualhash",
            "exists": True,
        }
    )
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: matrix)

    summary = module.record_outcome(
        variant_id="renamed_root_scriptless_dual_minimal_git",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert summary["recommended_next"].startswith("Install `renamed-root-scriptless-dual-placeable`")


def test_t2601_runtime_outcome_records_loaded_authored_candidate_next(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: _fake_matrix())

    summary = module.record_outcome(
        variant_id="active_installed",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is True
    assert "authored no-marker" in summary["recommended_next"]


def test_t2601_runtime_outcome_blocks_unknown_variant(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setattr(module, "_load_matrix", lambda _game_root: _fake_matrix())

    summary = module.record_outcome(
        variant_id="missing_variant",
        outcome="loaded",
        game_root_dir=tmp_path,
        output_path=tmp_path / "outcome.json",
    )

    assert summary["ok"] is False
    assert any("Unknown diagnostic variant" in issue for issue in summary["blocking_issues"])
