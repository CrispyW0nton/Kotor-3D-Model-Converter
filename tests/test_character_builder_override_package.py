from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.core.characters.character_override_package import (
    CharacterBuilderOverridePackageRequest,
    package_character_override_candidate,
)
from src.core.characters.character_validation_report import (
    CHARACTER_BUILDER_MANUAL_CHECKLIST,
    build_character_game_test_evidence,
)


def _hash_bytes(data: bytes) -> dict[str, int | str]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _test_output_hashes() -> dict[str, dict[str, int | str]]:
    return {
        "mdl": _hash_bytes(b"mdl"),
        "mdx": _hash_bytes(b"mdx"),
    }


def _write_source_export(
    tmp_path: Path,
    *,
    verified: bool = True,
    game: str = "K1",
    capability_stage: str | None = None,
    game_test_evidence: dict | None = None,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    mdl = tmp_path / "bendak.mdl"
    mdx = tmp_path / "bendak.mdx"
    mdl.write_bytes(b"mdl")
    mdx.write_bytes(b"mdx")
    output_hashes = _test_output_hashes()
    stage = capability_stage or ("export_candidate" if verified else "blocked")
    game_tested = stage == "game_tested"
    evidence_complete = bool(game_test_evidence)
    payload = {
        "schema": "ghostrigger.character_export_validation.v1",
        "status": "verified" if verified else "reload_failed",
        "verified": verified,
        "capability": {
            "stage": stage,
            "game_tested": game_tested and evidence_complete,
            "game_test_requested": game_tested,
            "game_test_evidence_complete": evidence_complete,
            "game_test_status": (
                "manual_checklist_passed"
                if game_tested and evidence_complete else
                "game_test_evidence_incomplete"
                if game_tested else
                "not_game_tested"
            ),
        },
        "game": game,
        "resref": "bendak",
        "outputs": {
            "mdl": str(mdl),
            "mdx": str(mdx),
        },
        "output_hashes": output_hashes,
        "character_builder_evidence_gates": {
            "schema": {
                "name": "ghostrigger.character_builder_evidence_gates.v1",
            },
            "fit": {
                "stage": "needs_review",
                "paired_landmark_alignment": {
                    "present": True,
                    "method": "paired_skeleton_landmark_similarity",
                    "pair_count": 3,
                    "paired_roles": ["pelvis", "head", "left"],
                    "rms_error": 0.42,
                    "max_error": 0.55,
                    "applied_scale": 0.8,
                    "solved_scale": 0.79,
                },
                "warning_issue_codes": [
                    "character.export.auto_fit_paired_landmarks_need_review",
                ],
            },
            "bind": {"stage": "passed"},
            "weight": {"stage": "donor_transfer_first_pass"},
            "animation": {"stage": "passed"},
            "material": {"stage": "needs_review"},
            "engine": {
                "stage": "partial_reverse_engineering",
                "pending_ghidra_count": 2,
            },
        },
        "manual_in_game_checklist": [
            "Load as player character without crash",
            "Idle/pause animation plays correctly",
        ],
        "metadata": {
            "character_builder_workflow": {
                "native_skeleton_is_authority": True,
                "imported_mesh_role": "payload_guest",
                "final_dag_source": "selected_kotor_base",
                "rig_state": {
                    "state": "native_template_final",
                    "native_base_resref": "n_mandalorian",
                    "native_base_game": game,
                    "imported_payload_name": "bendak",
                },
                "bind": {
                    "status": "bound_to_native_kotor_skeleton",
                    "native_base": {
                        "source_resref": "n_mandalorian",
                        "dag_authority": "native_kotor_base",
                    },
                    "imported_payload": {
                        "mesh_role": "payload_guest",
                        "mesh_names": ["Bendak"],
                    },
                },
            },
        },
        "game_test_evidence": dict(game_test_evidence or {}),
    }
    mdl.with_name("bendak_validation_report.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return mdl


def test_character_override_package_copies_verified_pair_under_target_resref(tmp_path: Path) -> None:
    source_mdl = _write_source_export(tmp_path / "source")
    out_dir = tmp_path / "package"

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=out_dir,
            target_resref="n_mandalorian03",
            game="K1",
        )
    )

    assert result.succeeded is True
    assert (out_dir / "n_mandalorian03.mdl").read_bytes() == b"mdl"
    assert (out_dir / "n_mandalorian03.mdx").read_bytes() == b"mdx"
    manifest_path = out_dir / "n_mandalorian03_override_manifest.json"
    readme_path = out_dir / "n_mandalorian03_override_readme.txt"
    assert result.export_job_result.manifest_path == manifest_path
    assert manifest_path.exists()
    assert readme_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.character_override_package.v1"
    assert manifest["target_resref"] == "n_mandalorian03"
    assert manifest["game"] == "K1"
    assert manifest["capability"]["stage"] == "export_candidate"
    assert manifest["capability"]["game_tested"] is False
    assert manifest["game_test_evidence"] == {}
    assert manifest["source_export"]["output_hashes"] == _test_output_hashes()
    assert manifest["package_output_hashes"]["artifacts"] == _test_output_hashes()
    gates = manifest["character_builder_evidence_gates"]
    assert gates["fit"]["stage"] == "needs_review"
    assert gates["fit"]["paired_landmark_alignment"]["pair_count"] == 3
    assert gates["engine"]["stage"] == "partial_reverse_engineering"
    assert manifest["character_builder_workflow"]["native_skeleton_is_authority"] is True
    assert manifest["character_builder_workflow"]["imported_mesh_role"] == "payload_guest"
    readme = readme_path.read_text(encoding="utf-8")
    assert "Evidence gates: fit=needs_review" in readme
    assert "Fit paired landmarks: 3 pairs, rms=0.42, max=0.55" in readme
    assert "Engine evidence: partial_reverse_engineering (pending Ghidra: 2)" in readme
    assert "Do not overwrite a live game install" in readme


def test_character_override_package_blocks_unverified_source_export(tmp_path: Path) -> None:
    source_mdl = _write_source_export(tmp_path / "source", verified=False)
    out_dir = tmp_path / "package"

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=out_dir,
            target_resref="n_mandalorian03",
            game="K1",
        )
    )

    assert result.succeeded is False
    assert not (out_dir / "n_mandalorian03.mdl").exists()
    codes = {issue.code for issue in result.export_job_result.validation_report.issues}
    assert "character.override_package.export_not_verified" in codes
    assert "character.override_package.capability_stage_invalid" in codes


def test_character_override_package_rejects_unsafe_target_resref(tmp_path: Path) -> None:
    source_mdl = _write_source_export(tmp_path / "source")

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=tmp_path / "package",
            target_resref="bad/name",
            game="K1",
        )
    )

    assert result.succeeded is False
    codes = {issue.code for issue in result.export_job_result.validation_report.issues}
    assert "character.override_package.resref_unsafe" in codes


def test_character_override_package_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source_mdl = _write_source_export(tmp_path / "source")
    source_mdl.write_bytes(b"different mdl bytes")

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=tmp_path / "package",
            target_resref="n_mandalorian03",
            game="K1",
        )
    )

    assert result.succeeded is False
    assert not (tmp_path / "package" / "n_mandalorian03.mdl").exists()
    codes = {issue.code for issue in result.export_job_result.validation_report.issues}
    assert "character.override_package.output_hash_mismatch" in codes


def test_character_override_package_rejects_incomplete_game_test_claim(tmp_path: Path) -> None:
    source_mdl = _write_source_export(
        tmp_path / "source",
        capability_stage="game_tested",
        game_test_evidence={},
    )

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=tmp_path / "package",
            target_resref="n_mandalorian03",
            game="K1",
        )
    )

    assert result.succeeded is False
    codes = {issue.code for issue in result.export_job_result.validation_report.issues}
    assert "character.override_package.game_test_evidence_incomplete" in codes


def test_character_override_package_preserves_complete_game_test_evidence(tmp_path: Path) -> None:
    output_hashes = _test_output_hashes()
    evidence = build_character_game_test_evidence(
        tested_games=["K1", "K2"],
        checklist_results={item: True for item in CHARACTER_BUILDER_MANUAL_CHECKLIST},
        tested_output_hashes=output_hashes,
        tester="manual qa",
        artifacts=["k1.png", "k2.png"],
    )
    source_mdl = _write_source_export(
        tmp_path / "source",
        capability_stage="game_tested",
        game_test_evidence=evidence,
    )

    result = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=source_mdl,
            output_dir=tmp_path / "package",
            target_resref="n_mandalorian03",
            game="K1",
        )
    )

    assert result.succeeded is True
    manifest = result.manifest
    assert manifest["capability"]["stage"] == "game_tested"
    assert manifest["capability"]["game_tested"] is True
    assert manifest["game_test_evidence"]["tester"] == "manual qa"
    assert manifest["game_test_evidence"]["checklist_results"][
        "Loading in both KOTOR 1 and KOTOR 2"
    ] is True
    assert manifest["game_test_evidence"]["per_game_checklist_results"]["K1"][
        "Load as player character without crash"
    ] is True
    assert manifest["game_test_evidence"]["per_game_checklist_results"]["K2"][
        "Loading in both KOTOR 1 and KOTOR 2"
    ] is True
    assert manifest["game_test_evidence"]["tested_output_hashes"] == output_hashes
