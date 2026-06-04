"""Character Builder export validation report artifacts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    merge_validation_reports,
    validation_report_to_dict,
)

from .kotor_constants import CHARACTER_EXPORT_EVIDENCE


CHARACTER_BUILDER_MANUAL_CHECKLIST: tuple[str, ...] = (
    "Load as player character without crash",
    "Idle/pause animation plays correctly",
    "Walk/run animations with proper foot contact",
    "Dialog animation (tlknorm) works",
    "One-handed weapon rhand socket attachment",
    "Two-handed weapon both hand sockets",
    "Head model headhook attachment",
    "Lightsaber LightsaberHook functionality",
    "Dialog camerahook positioning",
    "DeflectHook animation behavior",
    "Supermodel animation inheritance",
    "Loading in both KOTOR 1 and KOTOR 2",
)

CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA = "ghostrigger.character_game_test.v1"
REQUIRED_CHARACTER_BUILDER_GAME_TEST_GAMES: tuple[str, ...] = ("K1", "K2")

CAPABILITY_STAGE_BLOCKED = "blocked"
CAPABILITY_STAGE_EXPORT_CANDIDATE = "export_candidate"
CAPABILITY_STAGE_GAME_TESTED = "game_tested"

_GAME_READY_GATE_ACCEPTED_STAGES: dict[str, frozenset[str]] = {
    "fit": frozenset({"passed"}),
    "bind": frozenset({"passed"}),
    "weight": frozenset({"trusted_donor_transfer"}),
    "animation": frozenset({"passed"}),
    "material": frozenset({"passed"}),
    "engine": frozenset({"passed"}),
}

_FIT_EVIDENCE_CODES = frozenset({
    "character.export.missing_auto_fit_evidence",
    "character.export.incomplete_auto_fit_evidence",
    "character.export.invalid_auto_fit_scale",
    "character.export.invalid_auto_fit_translation",
    "character.export.missing_auto_fit_confidence",
    "character.export.low_auto_fit_confidence",
    "character.export.fallback_auto_fit_used",
    "character.export.auto_fit_landmark_sources_not_recorded",
    "character.export.auto_fit_source_landmarks_need_review",
    "character.export.auto_fit_imported_skeleton_guides_not_recorded",
    "character.export.auto_fit_paired_landmarks_need_review",
    "character.export.auto_fit_toe_forward_needs_review",
    "character.export.auto_fit_contract_mismatch",
})

_BIND_EVIDENCE_CODES = frozenset({
    "character.export.no_model",
    "character.export.missing_native_snapshot",
    "character.export.snapshot_failed",
    "character.export.not_native_template_final_rig",
    "character.export.missing_bind_provenance",
    "character.export.bind_provenance_mismatch",
    "character.export.render_replacement_count_mismatch",
    "character.export.render_replacement_count_malformed",
    "character.export.invalid_native_render_replacement_evidence",
    "character.export.missing_native_render_replacement_evidence",
    "character.export.native_snapshot_game_unknown",
    "character.export.native_snapshot_game_mismatch",
    "character.export.no_native_source",
    "character.export.supermodel_added",
    "character.export.supermodel_mismatch",
    "character.export.supermodel_case_changed",
    "character.export.node_case_changed",
    "character.export.node_path_changed",
    "character.export.node_path_missing",
    "character.export.node_missing",
    "character.export.required_socket_missing",
    "character.export.non_native_skeleton_node",
})

_WEIGHT_EVIDENCE_CODES = frozenset({
    "character.export.missing_skin_binding_evidence",
    "character.export.fallback_skin_binding",
    "character.export.donor_skin_binding_landmarks_incomplete",
    "character.export.no_skin_payload",
    "character.export.empty_skin_geometry",
    "character.export.empty_bonemap",
    "character.export.skin_row_count_mismatch",
    "character.export.no_skin_rows",
    "character.export.qbone_mismatch",
    "character.export.tbone_mismatch",
    "character.export.bonemap_empty_target",
    "character.export.bonemap_target_case_changed",
    "character.export.bonemap_target_missing",
    "character.export.bonemap_native_target_case_changed",
    "character.export.bonemap_target_not_native",
    "character.export.vertex_unweighted",
    "character.export.vertex_too_many_influences",
    "character.export.vertex_weight_nonfinite",
    "character.export.vertex_weight_negative",
    "character.export.vertex_bone_index_out_of_range",
    "character.export.vertex_weight_zero_sum",
    "character.export.vertex_weight_sum",
})

_GEOMETRY_EVIDENCE_CODES = frozenset({
    "character.export.vertex_malformed",
    "character.export.vertex_nonfinite",
    "character.export.normal_nonfinite",
    "character.export.face_malformed",
    "character.export.face_index_nonfinite",
    "character.export.face_index_noninteger",
    "character.export.face_index_out_of_range",
})

_MATERIAL_EVIDENCE_CODES = frozenset({
    "character.export.payload_texture_missing",
    "character.export.payload_uvs_missing",
    "character.export.payload_uv_count_mismatch",
    "character.export.payload_face_uv_count_mismatch",
    "character.export.payload_face_uv_malformed",
    "character.export.payload_face_uv_index_out_of_range",
})

_ANIMATION_EVIDENCE_CODES = frozenset({
    "character.export.missing_animation_library_evidence",
    "character.export.empty_animation_library_evidence",
    "character.export.animation_library_preview_incomplete",
})


def build_character_game_test_evidence(
    *,
    tested_games: tuple[str, ...] | list[str],
    checklist_results: dict[str, bool] | list[dict[str, Any]],
    per_game_checklist_results: dict[str, Any] | None = None,
    tested_output_hashes: dict[str, Any] | None = None,
    tester: str = "",
    notes: str = "",
    artifacts: tuple[str, ...] | list[str] = (),
    per_game_artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-friendly in-game evidence record for Character Builder.

    This helper intentionally records only manual/visual game-test facts.  It
    does not run the game, and it does not promote a candidate by itself.
    """

    games = _normalize_games(tested_games)
    checklist = _normalize_checklist_results(checklist_results)
    per_game_checklists = _normalize_per_game_checklist_results(
        per_game_checklist_results
    )
    if checklist:
        for game in games:
            per_game_checklists.setdefault(game, dict(checklist))
    per_game_checklists = {
        game: per_game_checklists.get(game, {})
        for game in games
        if game
    }
    per_game_artifact_payload = _normalize_per_game_artifacts(per_game_artifacts)

    return {
        "schema": CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA,
        "status": "passed",
        "tested_games": games,
        "checklist_results": _summarize_game_checklists(
            per_game_checklists,
            fallback=checklist,
        ),
        "per_game_checklist_results": per_game_checklists,
        "tested_output_hashes": _normalize_output_hashes(tested_output_hashes),
        "tester": str(tester or ""),
        "notes": str(notes or ""),
        "artifacts": [str(item or "") for item in artifacts if str(item or "").strip()],
        "per_game_artifacts": per_game_artifact_payload,
    }


def character_game_test_evidence_passed(
    evidence: Any,
    expected_output_hashes: dict[str, Any] | None = None,
    *,
    require_output_hashes: bool = False,
) -> bool:
    """Return True when evidence proves the full K1/K2 in-game checklist."""

    return not character_game_test_evidence_missing(
        evidence,
        expected_output_hashes,
        require_output_hashes=require_output_hashes,
    )


def character_game_test_evidence_missing(
    evidence: Any,
    expected_output_hashes: dict[str, Any] | None = None,
    *,
    require_output_hashes: bool = False,
) -> dict[str, Any]:
    """Return missing/failed proof facts for Character Builder game testing."""

    missing: dict[str, Any] = {}
    if not isinstance(evidence, dict):
        return {"evidence": "not_a_mapping"}
    if evidence.get("schema") != CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA:
        missing["schema"] = {
            "expected": CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA,
            "actual": evidence.get("schema"),
        }
    if str(evidence.get("status") or "").strip().lower() != "passed":
        missing["status"] = {
            "expected": "passed",
            "actual": evidence.get("status"),
        }
    tested_games = {
        _normalize_game(game)
        for game in list(evidence.get("tested_games") or [])
        if str(game or "").strip()
    }
    missing_games = [
        game for game in REQUIRED_CHARACTER_BUILDER_GAME_TEST_GAMES
        if game not in tested_games
    ]
    if missing_games:
        missing["missing_games"] = missing_games

    per_game = _normalize_per_game_checklist_results(
        evidence.get("per_game_checklist_results")
    )
    missing_per_game: list[str] = []
    failed_by_game: dict[str, list[str]] = {}
    for game in REQUIRED_CHARACTER_BUILDER_GAME_TEST_GAMES:
        checklist = per_game.get(game)
        if not checklist:
            missing_per_game.append(game)
            continue
        failed = [
            item for item in CHARACTER_BUILDER_MANUAL_CHECKLIST
            if not bool(checklist.get(item))
        ]
        if failed:
            failed_by_game[game] = failed
    if missing_per_game:
        missing["missing_per_game_checklists"] = missing_per_game
    if failed_by_game:
        missing["failed_checklist_items_by_game"] = failed_by_game

    expected_hashes = _normalize_output_hashes(expected_output_hashes)
    if require_output_hashes and not expected_hashes:
        missing["expected_output_hashes"] = "missing"
    if expected_hashes:
        tested_hashes = _normalize_output_hashes(evidence.get("tested_output_hashes"))
        missing_hashes = [
            key for key in expected_hashes
            if key not in tested_hashes
        ]
        mismatched: dict[str, dict[str, Any]] = {}
        for key, expected in expected_hashes.items():
            actual = tested_hashes.get(key)
            if actual is None:
                continue
            if (
                actual.get("sha256") != expected.get("sha256")
                or actual.get("size") != expected.get("size")
            ):
                mismatched[key] = {
                    "expected": expected,
                    "actual": actual,
                }
        if missing_hashes:
            missing["missing_tested_output_hashes"] = missing_hashes
        if mismatched:
            missing["mismatched_tested_output_hashes"] = mismatched
    return missing


def _normalize_games(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in list(values or []):
        game = _normalize_game(value)
        if not game or game in seen:
            continue
        seen.add(game)
        result.append(game)
    return result


def _normalize_game(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"1", "KOTOR1", "KOTOR 1", "KNIGHTS OF THE OLD REPUBLIC"}:
        return "K1"
    if text in {"2", "KOTOR2", "KOTOR 2", "TSL", "THE SITH LORDS"}:
        return "K2"
    return text


def _normalize_checklist_results(value: Any) -> dict[str, bool]:
    if isinstance(value, dict):
        return {str(key): bool(item) for key, item in value.items()}
    results: dict[str, bool] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            key = str(item.get("item") or item.get("name") or "").strip()
            if key:
                results[key] = bool(item.get("passed"))
    return results


def _normalize_per_game_checklist_results(value: Any) -> dict[str, dict[str, bool]]:
    if not isinstance(value, dict):
        return {}
    results: dict[str, dict[str, bool]] = {}
    for game, checklist in value.items():
        normalized_game = _normalize_game(game)
        if not normalized_game:
            continue
        normalized_checklist = _normalize_checklist_results(checklist)
        if normalized_checklist:
            results[normalized_game] = normalized_checklist
    return results


def _normalize_per_game_artifacts(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    results: dict[str, list[str]] = {}
    for game, artifacts in value.items():
        normalized_game = _normalize_game(game)
        if not normalized_game:
            continue
        if isinstance(artifacts, (str, bytes)):
            raw_items = [artifacts]
        else:
            raw_items = list(artifacts or [])
        normalized_items = [
            str(item or "") for item in raw_items
            if str(item or "").strip()
        ]
        if normalized_items:
            results[normalized_game] = normalized_items
    return results


def _normalize_output_hashes(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        artifact = str(key or "").strip().lower()
        digest = str(item.get("sha256") or "").strip().lower()
        if not artifact or not digest:
            continue
        payload: dict[str, Any] = {"sha256": digest}
        try:
            payload["size"] = int(item.get("size"))
        except (TypeError, ValueError, OverflowError):
            pass
        result[artifact] = payload
    return result


def _summarize_game_checklists(
    per_game: dict[str, dict[str, bool]],
    *,
    fallback: dict[str, bool],
) -> dict[str, bool]:
    if not per_game:
        return dict(fallback)
    summary: dict[str, bool] = {}
    for item in CHARACTER_BUILDER_MANUAL_CHECKLIST:
        values = [
            bool(checklist.get(item))
            for checklist in per_game.values()
        ]
        summary[item] = bool(values and all(values))
    for item, passed in fallback.items():
        summary.setdefault(item, bool(passed))
    return summary


def character_builder_evidence_gates(
    workflow: dict[str, Any],
    preflight_report: ValidationReport,
) -> dict[str, dict[str, Any]]:
    """Summarize Character Builder proof as separate export gates."""

    workflow = workflow if isinstance(workflow, dict) else {}
    issues = list(getattr(preflight_report, "issues", []) or [])
    fit_report = _mapping(workflow.get("fit_report"))
    bind = _mapping(workflow.get("bind"))
    rig_state = _mapping(workflow.get("rig_state"))
    native_snapshot = _mapping(workflow.get("native_snapshot"))
    skin_binding = _mapping(bind.get("skin_binding"))
    motion_assignment = _mapping(workflow.get("motion_assignment"))
    animation_library = _mapping(workflow.get("animation_library"))

    fit_codes = _gate_issue_codes(issues, _FIT_EVIDENCE_CODES)
    bind_codes = _gate_issue_codes(issues, _BIND_EVIDENCE_CODES)
    weight_codes = _gate_issue_codes(
        issues,
        _WEIGHT_EVIDENCE_CODES | _GEOMETRY_EVIDENCE_CODES,
    )
    animation_codes = _gate_issue_codes(issues, _ANIMATION_EVIDENCE_CODES)
    material_codes = _gate_issue_codes(issues, _MATERIAL_EVIDENCE_CODES)

    fit_confidence = _safe_float(
        fit_report.get(
            "confidence",
            _mapping(fit_report.get("auto_fit_report")).get("confidence"),
        )
    )
    fit_landmark_sources = _fit_landmark_source_summary(fit_report)
    fit_landmark_alignment = _fit_landmark_alignment_summary(fit_report)
    fit_toe_forward = _fit_toe_forward_summary(fit_report)
    fit_imported_armature = _fit_imported_armature_summary(fit_report)
    fit_stage = _gate_stage(
        fit_codes,
        present=bool(fit_report),
        warning_label="needs_review",
    )
    fit = {
        "stage": fit_stage,
        "present": bool(fit_report),
        "policy": str(fit_report.get("fit_policy") or ""),
        "confidence": fit_confidence,
        "fallback_used": bool(fit_report.get(
            "fallback_used",
            _mapping(fit_report.get("auto_fit_report")).get("fallback_used", False),
        )),
        "source_landmark_domain": fit_landmark_sources["source_landmark_domain"],
        "source_landmark_sources": fit_landmark_sources["source_landmark_sources"],
        "source_landmark_source_counts": fit_landmark_sources["source_landmark_source_counts"],
        "source_skeleton_landmark_roles": fit_landmark_sources["source_skeleton_landmark_roles"],
        "source_mesh_payload_landmark_roles": fit_landmark_sources["source_mesh_payload_landmark_roles"],
        "source_uses_imported_skeleton_landmarks": fit_landmark_sources["source_uses_imported_skeleton_landmarks"],
        "source_imported_armature_guide_count": fit_imported_armature["guide_joint_count"],
        "source_imported_armature_scene_guide_count": fit_imported_armature["scene_guide_joint_count"],
        "source_imported_armature_names": fit_imported_armature["armature_names"],
        "paired_landmark_alignment": fit_landmark_alignment,
        "toe_forward_alignment": fit_toe_forward,
        "fit_transform_present": bool(_mapping(fit_report.get("fit_transform"))),
        "blocking_issue_codes": fit_codes["blocking"],
        "warning_issue_codes": fit_codes["warning"],
    }

    bind_present = bool(bind) or bool(rig_state) or bool(native_snapshot)
    bind = {
        "stage": _gate_stage(bind_codes, present=bind_present),
        "present": bind_present,
        "rig_state": str(rig_state.get("state") or ""),
        "dag_authority": str(
            rig_state.get("dag_authority")
            or _mapping(bind.get("native_base")).get("dag_authority")
            or ""
        ),
        "native_model": str(native_snapshot.get("model_name") or ""),
        "native_game": str(native_snapshot.get("game") or ""),
        "native_dag_fingerprint": str(native_snapshot.get("dag_fingerprint") or ""),
        "bind_status": str(bind.get("status") or ""),
        "blocking_issue_codes": bind_codes["blocking"],
        "warning_issue_codes": bind_codes["warning"],
    }

    weighting_method = str(skin_binding.get("weighting_method") or "")
    quality_stage = str(skin_binding.get("quality_stage") or "")
    donor_weight_transfer = bool(skin_binding.get("donor_weight_transfer"))
    weight_stage = _weight_gate_stage(
        weight_codes,
        skin_binding_present=bool(skin_binding),
        donor_weight_transfer=donor_weight_transfer,
        quality_stage=quality_stage,
        weighting_method=weighting_method,
    )
    weight = {
        "stage": weight_stage,
        "present": bool(skin_binding),
        "weighting_method": weighting_method,
        "quality_stage": quality_stage,
        "donor_weight_transfer": donor_weight_transfer,
        "mesh_report_count": len(list(skin_binding.get("mesh_reports") or [])),
        "blocking_issue_codes": weight_codes["blocking"],
        "warning_issue_codes": weight_codes["warning"],
    }

    available_count = _safe_int(animation_library.get("available_count"))
    required_missing = [
        str(item or "")
        for item in list(animation_library.get("required_preview_missing") or [])
        if str(item or "").strip()
    ]
    diagnostics = [
        str(item or "")
        for item in list(animation_library.get("diagnostics") or [])
        if str(item or "").strip()
    ]
    animation = {
        "stage": _animation_gate_stage(
            animation_codes,
            present=bool(animation_library),
            available_count=available_count,
            required_preview_missing=required_missing,
            diagnostics=diagnostics,
        ),
        "present": bool(animation_library),
        "motion_source": str(
            animation_library.get("motion_source")
            or motion_assignment.get("source")
            or ""
        ),
        "assigned_supermodel": str(
            animation_library.get("selected_supermodel")
            or motion_assignment.get("supermodel")
            or ""
        ),
        "effective_supermodel": str(animation_library.get("effective_supermodel") or ""),
        "resolved_supermodel": str(animation_library.get("resolved_supermodel") or ""),
        "game": str(animation_library.get("game") or ""),
        "available_count": available_count,
        "sample_animation_names": [
            str(item or "")
            for item in list(animation_library.get("sample_animation_names") or [])
            if str(item or "").strip()
        ][:16],
        "required_preview_available": [
            str(item or "")
            for item in list(animation_library.get("required_preview_available") or [])
            if str(item or "").strip()
        ],
        "required_preview_missing": required_missing,
        "diagnostics": diagnostics,
        "blocking_issue_codes": animation_codes["blocking"],
        "warning_issue_codes": animation_codes["warning"],
    }

    material = {
        "stage": _gate_stage(
            material_codes,
            present=bool(skin_binding),
            warning_label="needs_review",
        ),
        "present": bool(skin_binding),
        "blocking_issue_codes": material_codes["blocking"],
        "warning_issue_codes": material_codes["warning"],
    }

    engine = _engine_evidence_gate()

    return {
        "schema": {
            "name": "ghostrigger.character_builder_evidence_gates.v1",
            "meaning": (
                "Fit, bind, weight, animation, material readiness, and engine "
                "reverse-engineering evidence are separate Character Builder proof "
                "gates. A character can pass one gate while another remains "
                "fallback-quality, review-needed, partial, or blocked."
            ),
        },
        "fit": fit,
        "bind": bind,
        "weight": weight,
        "animation": animation,
        "material": material,
        "engine": engine,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _engine_evidence_gate() -> dict[str, Any]:
    evidence = CHARACTER_EXPORT_EVIDENCE
    pending = [
        str(item or "")
        for item in list(evidence.get("pending_ghidra") or [])
        if str(item or "").strip()
    ]
    verified_sources = [
        str(item or "")
        for item in list(evidence.get("verified_sources") or [])
        if str(item or "").strip()
    ]
    native_contract = [
        str(item or "")
        for item in list(evidence.get("verified_native_contract") or [])
        if str(item or "").strip()
    ]
    string_refs = list(evidence.get("engine_string_refs") or [])
    function_evidence = list(evidence.get("function_disassembly_evidence") or [])
    stage = "partial_reverse_engineering" if pending else "passed"
    return {
        "stage": stage,
        "findings_doc": str(evidence.get("findings_doc") or ""),
        "status": str(evidence.get("status") or ""),
        "engine_string_evidence_status": str(
            evidence.get("engine_string_evidence_status") or ""
        ),
        "verified_fixture": str(evidence.get("verified_fixture") or ""),
        "verified_sources": verified_sources,
        "verified_source_count": len(verified_sources),
        "verified_native_contract": native_contract,
        "engine_string_ref_count": len(string_refs),
        "function_disassembly_evidence_count": len(function_evidence),
        "pending_ghidra": pending,
        "pending_ghidra_count": len(pending),
        "blocking_issue_codes": [],
        "warning_issue_codes": (
            ["character.export.engine_reverse_engineering_pending"]
            if pending else
            []
        ),
    }


def _character_builder_game_ready_status(
    *,
    verified: bool,
    game_test_requested: bool,
    game_evidence_complete: bool,
    evidence_gates: dict[str, Any],
) -> dict[str, Any]:
    """Return strict game-ready status separate from export/game-test stages."""

    actual: dict[str, str] = {}
    blockers: list[str] = []
    required = {
        gate: sorted(stages)
        for gate, stages in _GAME_READY_GATE_ACCEPTED_STAGES.items()
    }
    if not verified:
        blockers.append("export=not_verified")
    if not game_test_requested:
        blockers.append("game_test=not_requested")
    if not game_evidence_complete:
        blockers.append("game_test=evidence_incomplete")

    for gate, accepted in _GAME_READY_GATE_ACCEPTED_STAGES.items():
        stage = _evidence_gate_stage(evidence_gates, gate)
        actual[gate] = stage
        if stage not in accepted:
            blockers.append(f"{gate}={stage}")

    return {
        "game_ready": not blockers,
        "blockers": blockers,
        "required_gate_stages": required,
        "actual_gate_stages": actual,
    }


def _fit_landmark_source_summary(fit_report: dict[str, Any]) -> dict[str, Any]:
    source_frame = _mapping(fit_report.get("source_frame"))
    raw_sources = _mapping(source_frame.get("landmark_sources"))
    sources: dict[str, str] = {
        str(role or ""): str(source or "")
        for role, source in raw_sources.items()
        if str(role or "").strip()
    }
    counts: dict[str, int] = {}
    for source in sources.values():
        key = source or "unknown"
        counts[key] = counts.get(key, 0) + 1
    skeleton_roles = sorted(
        role for role, source in sources.items()
        if source in {"imported_skeleton", "skeleton_node"}
    )
    mesh_roles = sorted(
        role for role, source in sources.items()
        if source == "mesh_payload"
    )
    if not sources:
        domain = "not_recorded"
    elif skeleton_roles and not mesh_roles:
        domain = "skeleton_landmarks"
    elif skeleton_roles and mesh_roles:
        domain = "mixed_skeleton_and_mesh_landmarks"
    elif mesh_roles:
        domain = "mesh_payload_landmarks"
    else:
        domain = "non_mesh_landmarks"
    return {
        "source_landmark_domain": domain,
        "source_landmark_sources": sources,
        "source_landmark_source_counts": counts,
        "source_skeleton_landmark_roles": skeleton_roles,
        "source_mesh_payload_landmark_roles": mesh_roles,
        "source_uses_imported_skeleton_landmarks": any(
            source == "imported_skeleton" for source in sources.values()
        ),
    }


def _fit_imported_armature_summary(fit_report: dict[str, Any]) -> dict[str, Any]:
    imported = _mapping(fit_report.get("source_imported_armature"))
    return {
        "guide_joint_count": _safe_int(imported.get("guide_joint_count")),
        "scene_guide_joint_count": _safe_int(imported.get("scene_guide_joint_count")),
        "armature_names": [
            str(name or "")
            for name in list(imported.get("armature_names") or [])
            if str(name or "").strip()
        ],
    }


def _fit_landmark_alignment_summary(fit_report: dict[str, Any]) -> dict[str, Any]:
    fit_transform = _mapping(fit_report.get("fit_transform"))
    alignment = _mapping(fit_transform.get("landmark_alignment"))
    pair_count = _safe_int(alignment.get("pair_count")) if alignment else 0
    return {
        "present": bool(alignment),
        "method": str(alignment.get("method") or ""),
        "pair_count": int(pair_count or 0),
        "paired_roles": [
            str(role or "")
            for role in list(alignment.get("paired_roles") or [])
            if str(role or "").strip()
        ],
        "rms_error": _safe_float(alignment.get("rms_error")),
        "max_error": _safe_float(alignment.get("max_error")),
        "worst_pair_role": str(alignment.get("worst_pair_role") or ""),
        "pair_errors": [
            item for item in list(alignment.get("pair_errors") or [])
            if isinstance(item, dict)
        ],
        "applied_scale": _safe_float(alignment.get("applied_scale")),
        "solved_scale": _safe_float(alignment.get("solved_scale")),
        "applied_scale_basis": str(alignment.get("applied_scale_basis") or ""),
        "translation_basis": str(alignment.get("translation_basis") or ""),
        "error_basis": str(alignment.get("error_basis") or ""),
    }


def _fit_toe_forward_summary(fit_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": _fit_toe_forward_frame_summary(
            _mapping(fit_report.get("source_frame"))
        ),
        "target": _fit_toe_forward_frame_summary(
            _mapping(fit_report.get("target_frame"))
        ),
    }


def _fit_toe_forward_frame_summary(frame: dict[str, Any]) -> dict[str, Any]:
    landmarks = _mapping(frame.get("landmarks"))
    required_roles = ("left_foot", "right_foot", "left_toe", "right_toe")
    has_toe_landmarks = all(bool(landmarks.get(role)) for role in required_roles)
    return {
        "has_toe_landmarks": bool(has_toe_landmarks),
        "toe_forward_alignment": _safe_float(frame.get("toe_forward_alignment")),
        "landmarks": {
            role: str(landmarks.get(role) or "")
            for role in required_roles
            if str(landmarks.get(role) or "").strip()
        },
    }


def _toe_forward_text_summary(toe_forward: dict[str, Any]) -> str:
    parts: list[str] = []
    for label in ("source", "target"):
        frame = _mapping(toe_forward.get(label))
        has_landmarks = bool(frame.get("has_toe_landmarks"))
        alignment = _safe_float(frame.get("toe_forward_alignment"))
        if alignment is None:
            if has_landmarks:
                parts.append(f"{label}=not_recorded")
            continue
        suffix = "" if has_landmarks else " (no toe landmarks)"
        parts.append(f"{label}={alignment:.3f}{suffix}")
    return ", ".join(parts)


def _gate_issue_codes(
    issues: list[ValidationIssue],
    relevant_codes: frozenset[str],
) -> dict[str, list[str]]:
    blocking: list[str] = []
    warning: list[str] = []
    for issue in issues:
        code = str(getattr(issue, "code", "") or "")
        if code not in relevant_codes:
            continue
        severity = getattr(issue, "severity", "")
        if severity == ValidationSeverity.BLOCKING:
            blocking.append(code)
        else:
            warning.append(code)
    return {
        "blocking": sorted(set(blocking)),
        "warning": sorted(set(warning)),
    }


def _gate_stage(
    codes: dict[str, list[str]],
    *,
    present: bool,
    warning_label: str = "warning",
) -> str:
    if codes.get("blocking"):
        return "blocked"
    if not present:
        return "missing"
    if codes.get("warning"):
        return warning_label
    return "passed"


def _weight_gate_stage(
    codes: dict[str, list[str]],
    *,
    skin_binding_present: bool,
    donor_weight_transfer: bool,
    quality_stage: str,
    weighting_method: str,
) -> str:
    if codes.get("blocking"):
        return "blocked"
    if not skin_binding_present:
        return "missing"
    if (
        "character.export.donor_skin_binding_landmarks_incomplete"
        in set(codes.get("warning") or [])
    ):
        return "donor_transfer_landmarks_incomplete"
    if (
        weighting_method == "nearest_kotor_bone_segment"
        or quality_stage in {"fallback_first_pass", "donor_transfer_partial"}
        or not donor_weight_transfer
        or codes.get("warning")
    ):
        return quality_stage or "fallback_first_pass"
    return "trusted_donor_transfer"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _animation_gate_stage(
    codes: dict[str, list[str]],
    *,
    present: bool,
    available_count: int,
    required_preview_missing: list[str],
    diagnostics: list[str],
) -> str:
    if codes.get("blocking"):
        return "blocked"
    if not present:
        return "missing"
    if available_count <= 0:
        return "empty"
    if diagnostics:
        return "resolved_with_diagnostics"
    if required_preview_missing:
        return "preview_incomplete"
    if codes.get("warning"):
        return "warning"
    return "passed"


def _evidence_gate_stage(
    gates: dict[str, Any],
    key: str,
) -> str:
    gate = gates.get(key)
    if not isinstance(gate, dict):
        return "missing"
    return str(gate.get("stage") or "missing")


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(result):
        return None
    return result


@dataclass(frozen=True)
class CharacterBuilderValidationReport:
    """Machine-readable and human-readable Character Builder export proof."""

    status: str
    verified: bool
    job_id: str
    export_kind: str
    game: str
    resref: str
    outputs: dict[str, str]
    preflight_report: ValidationReport
    reload_report: ValidationReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    output_hashes: dict[str, Any] = field(default_factory=dict)
    game_tested: bool = False
    game_test_evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def merged_report(self) -> ValidationReport:
        return merge_validation_reports(
            self.preflight_report,
            self.reload_report or ValidationReport(source="character.export_transaction.verify"),
        )

    @property
    def capability_stage(self) -> str:
        """Return the strongest proven Character Builder export stage."""

        if self.game_tested and character_game_test_evidence_passed(
            self.game_test_evidence,
            _normalize_output_hashes(self.output_hashes),
            require_output_hashes=True,
        ):
            return CAPABILITY_STAGE_GAME_TESTED
        if self.verified:
            return CAPABILITY_STAGE_EXPORT_CANDIDATE
        return CAPABILITY_STAGE_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        merged = self.merged_report
        normalized_output_hashes = _normalize_output_hashes(self.output_hashes)
        workflow = dict(self.metadata.get("character_builder_workflow") or {})
        evidence_gates = character_builder_evidence_gates(
            workflow,
            self.preflight_report,
        )
        game_evidence_complete = character_game_test_evidence_passed(
            self.game_test_evidence,
            normalized_output_hashes,
            require_output_hashes=bool(self.game_tested),
        )
        game_ready = _character_builder_game_ready_status(
            verified=bool(self.verified),
            game_test_requested=bool(self.game_tested),
            game_evidence_complete=bool(game_evidence_complete),
            evidence_gates=evidence_gates,
        )
        game_evidence_missing = (
            character_game_test_evidence_missing(
                self.game_test_evidence,
                normalized_output_hashes,
                require_output_hashes=bool(self.game_tested),
            )
            if self.game_tested or self.game_test_evidence else
            {}
        )
        data = {
            "schema": "ghostrigger.character_export_validation.v1",
            "status": self.status,
            "verified": bool(self.verified),
            "capability": {
                "stage": self.capability_stage,
                "game_tested": bool(self.game_tested and game_evidence_complete),
                "game_test_requested": bool(self.game_tested),
                "game_test_evidence_complete": bool(game_evidence_complete),
                "game_test_status": (
                    "manual_checklist_passed"
                    if self.game_tested and game_evidence_complete else
                    "game_test_evidence_incomplete"
                    if self.game_tested else
                    "not_game_tested"
                ),
                "game_ready": bool(game_ready["game_ready"]),
                "game_ready_blockers": list(game_ready["blockers"]),
                "game_ready_required_gate_stages": dict(game_ready["required_gate_stages"]),
                "game_ready_actual_gate_stages": dict(game_ready["actual_gate_stages"]),
                "honesty_note": (
                    "GhostRigger verification proves staged export and reload "
                    "preflight only. Treat this as an export candidate until "
                    "the manual in-game checklist passes in KOTOR; treat it as "
                    "game-ready only when all Character Builder evidence gates "
                    "are clean too."
                ),
            },
            "job_id": self.job_id,
            "export_kind": self.export_kind,
            "game": self.game,
            "resref": self.resref,
            "outputs": dict(self.outputs),
            "output_hashes": normalized_output_hashes,
            "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
            "manual_in_game_checklist": list(CHARACTER_BUILDER_MANUAL_CHECKLIST),
            "game_test_evidence": dict(self.game_test_evidence or {}),
            "game_test_evidence_missing": dict(game_evidence_missing or {}),
            "character_builder_evidence_gates": evidence_gates,
            "preflight_report": validation_report_to_dict(self.preflight_report),
            "reload_report": validation_report_to_dict(self.reload_report)
            if self.reload_report is not None else None,
            "summary": {
                "issue_count": len(merged.issues),
                "blocking_count": len(merged.blocking_issues),
                "export_allowed": not merged.has_blocking,
            },
            "metadata": dict(self.metadata),
        }
        json.dumps(data)
        return data

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_text(self) -> str:
        payload = self.to_dict()
        lines = [
            "GhostRigger Character Builder Export Validation",
            f"Status: {payload.get('status')}",
            f"Verified: {payload.get('verified')}",
            f"Capability stage: {payload.get('capability', {}).get('stage')}",
            f"Game tested: {payload.get('capability', {}).get('game_tested')}",
            f"Game ready: {payload.get('capability', {}).get('game_ready')}",
            f"Game: {payload.get('game')}",
            f"Resref: {payload.get('resref')}",
            "",
            "Outputs:",
        ]
        for key, value in dict(payload.get("outputs") or {}).items():
            lines.append(f"- {key}: {value}")

        capability = dict(payload.get("capability") or {})
        ready_blockers = [
            str(item or "")
            for item in list(capability.get("game_ready_blockers") or [])
            if str(item or "").strip()
        ]
        if ready_blockers:
            lines.extend(["", "Game-ready blockers:"])
            for item in ready_blockers:
                lines.append(f"- {item}")

        evidence_gates = dict(payload.get("character_builder_evidence_gates") or {})
        workflow = dict(payload.get("metadata", {}).get("character_builder_workflow") or {})
        if workflow:
            rig_state = dict(workflow.get("rig_state") or {})
            fit_report = dict(workflow.get("fit_report") or {})
            fit_transform = dict(fit_report.get("fit_transform") or {})
            native_snapshot = dict(workflow.get("native_snapshot") or {})
            lines.extend(["", "Character Builder workflow evidence:"])
            lines.append(
                f"- Final DAG source: {workflow.get('final_dag_source')}"
            )
            lines.append(
                f"- Rig state: {rig_state.get('state')} "
                f"({rig_state.get('dag_authority')})"
            )
            if native_snapshot:
                lines.append(
                    f"- Native snapshot: {native_snapshot.get('game')} "
                    f"{native_snapshot.get('model_name')} "
                    f"supermodel {native_snapshot.get('supermodel')}"
                )
            if fit_report:
                lines.append(
                    f"- Auto-fit policy: {fit_report.get('fit_policy')} "
                    f"confidence {fit_report.get('confidence')}"
                )
            if fit_transform:
                lines.append(
                    f"- Fit transform: scale {fit_transform.get('scale')} "
                    f"translation {fit_transform.get('translation')}"
                )
            if evidence_gates:
                lines.append(
                    "- Evidence gates: "
                    f"fit={_evidence_gate_stage(evidence_gates, 'fit')}, "
                    f"bind={_evidence_gate_stage(evidence_gates, 'bind')}, "
                    f"weight={_evidence_gate_stage(evidence_gates, 'weight')}, "
                    f"animation={_evidence_gate_stage(evidence_gates, 'animation')}, "
                    f"material={_evidence_gate_stage(evidence_gates, 'material')}, "
                    f"engine={_evidence_gate_stage(evidence_gates, 'engine')}"
                )
                fit_gate = dict(evidence_gates.get("fit") or {})
                source_domain = str(fit_gate.get("source_landmark_domain") or "")
                if source_domain:
                    source_counts = dict(fit_gate.get("source_landmark_source_counts") or {})
                    count_text = ", ".join(
                        f"{key}={source_counts[key]}"
                        for key in sorted(source_counts)
                    )
                    lines.append(
                        "- Fit landmark sources: "
                        f"{source_domain}"
                        + (f" ({count_text})" if count_text else "")
                    )
                paired = dict(fit_gate.get("paired_landmark_alignment") or {})
                if paired.get("present"):
                    worst = str(paired.get("worst_pair_role") or "").strip()
                    lines.append(
                        "- Fit paired landmarks: "
                        f"{paired.get('pair_count')} pairs, "
                        f"rms={paired.get('rms_error')}, "
                        f"max={paired.get('max_error')}"
                        + (f", worst={worst}" if worst else "")
                    )
                toe_forward = dict(fit_gate.get("toe_forward_alignment") or {})
                toe_text = _toe_forward_text_summary(toe_forward)
                if toe_text:
                    lines.append(f"- Fit toe-forward: {toe_text}")
                engine_gate = dict(evidence_gates.get("engine") or {})
                if engine_gate:
                    lines.append(
                        "- Engine evidence: "
                        f"{engine_gate.get('status')} "
                        f"(pending Ghidra: {engine_gate.get('pending_ghidra_count')})"
                    )
            animation_library = dict(workflow.get("animation_library") or {})
            if animation_library:
                lines.append(
                    "- Animation library: "
                    f"{animation_library.get('available_count', 0)} clip(s), "
                    f"source={animation_library.get('motion_source')}, "
                    f"supermodel={animation_library.get('effective_supermodel')}"
                )
        elif evidence_gates:
            lines.extend(["", "Character Builder evidence gates:"])
            lines.append(
                "- Evidence gates: "
                f"engine={_evidence_gate_stage(evidence_gates, 'engine')}"
            )
            engine_gate = dict(evidence_gates.get("engine") or {})
            if engine_gate:
                lines.append(
                    "- Engine evidence: "
                    f"{engine_gate.get('status')} "
                    f"(pending Ghidra: {engine_gate.get('pending_ghidra_count')})"
                )

        lines.extend(["", "Issues:"])
        issue_count = 0
        reports = [
            ("preflight", payload.get("preflight_report")),
            ("reload", payload.get("reload_report")),
        ]
        for report_name, report in reports:
            if not isinstance(report, dict):
                continue
            for issue in list(report.get("issues") or []):
                issue_count += 1
                lines.append(
                    f"- [{report_name}] {issue.get('severity')} "
                    f"{issue.get('code')}: {issue.get('message')}"
                )
                fix_hint = str(issue.get("fix_hint") or "").strip()
                if fix_hint:
                    lines.append(f"  Fix: {fix_hint}")
                navigation = _format_navigation(issue.get("navigation"))
                if navigation:
                    lines.append(f"  Navigate: {navigation}")
                details = _format_issue_details(issue.get("details"))
                if details:
                    lines.append(f"  Details: {details}")
        if issue_count == 0:
            lines.append("- none")

        evidence_missing = payload.get("game_test_evidence_missing")
        if isinstance(evidence_missing, dict) and evidence_missing:
            lines.extend(["", "Game-test evidence gaps:"])
            details = _format_issue_details(evidence_missing)
            lines.append(details or str(evidence_missing))

        lines.extend(["", "Manual in-game checklist:"])
        for index, item in enumerate(CHARACTER_BUILDER_MANUAL_CHECKLIST, start=1):
            lines.append(f"{index}. {item}")
        return "\n".join(lines) + "\n"


def validation_report_paths(mdl_path: str | Path) -> tuple[Path, Path]:
    """Return the JSON and text report paths for a Character Builder MDL."""

    path = Path(mdl_path)
    return (
        path.with_name(f"{path.stem}_validation_report.json"),
        path.with_name(f"{path.stem}_validation_report.txt"),
    )


def _format_navigation(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    for key in ("route", "field_path", "node_name", "object_id", "camera_angle"):
        item = value.get(key)
        if item not in (None, ""):
            parts.append(f"{key}={item}")
    if value.get("time_seconds") is not None:
        parts.append(f"time_seconds={value.get('time_seconds')}")
    return ", ".join(parts)


def _format_issue_details(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    skipped = {"engine_evidence"}
    parts: list[str] = []
    for key in sorted(value):
        if key in skipped:
            continue
        item = value.get(key)
        if item in (None, "", [], {}):
            continue
        parts.append(f"{key}={_compact_detail_value(item)}")
        if len(parts) >= 6:
            remaining = len([k for k in value if k not in skipped]) - len(parts)
            if remaining > 0:
                parts.append(f"... {remaining} more")
            break
    return "; ".join(parts)


def _compact_detail_value(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{key}: {_compact_detail_value(item)}"
            for key, item in list(value.items())[:4]
        ) + ("..." if len(value) > 4 else "") + "}"
    if isinstance(value, (list, tuple)):
        items = list(value)
        text = ", ".join(_compact_detail_value(item) for item in items[:6])
        if len(items) > 6:
            text += ", ..."
        return "[" + text + "]"
    return str(value)
