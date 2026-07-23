"""Character Builder MDL export preflight checks.

The Character Builder is not allowed to treat an imported FBX mesh as the
authority for a KOTOR character.  The selected native base model owns the
runtime DAG contract: exact node names, parent paths, socket hooks, deform
helpers, supermodel inheritance, and skin payload requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .kotor_constants import (
    CHARACTER_EXPORT_EVIDENCE,
    ENGINE_VERIFIED_SOCKET_STRING_REFS,
    KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS,
    KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX,
    KOTOR_SKIN_WEIGHT_SUM_TOLERANCE,
)
from .character_rig_state import (
    MESH_ROLE_PAYLOAD_GUEST,
    RIG_DAG_AUTHORITY_NATIVE_KOTOR,
    RIG_STATE_NATIVE_TEMPLATE_FINAL,
    get_character_rig_state,
    is_native_template_final_rig,
)
from .native_skeleton import (
    KOTOR_NATIVE_RESREF_MAX_LEN,
    NativeNodeSnapshot,
    NativeSkeletonSnapshot,
    capture_native_skeleton_snapshot,
    native_skeleton_fingerprint,
    normalize_model_path_to_native_snapshot,
)


_NULL_SUPERMODELS = {"", "NULL", "NONE"}
_STRUCTURAL_ROLES = {"socket", "helper", "deform_helper"}
_REPLACEABLE_RENDER_ROLES = {"mesh", "skin_mesh"}
_DONOR_WEIGHT_REQUIRED_FIT_LANDMARKS = frozenset({
    "head",
    "pelvis",
    "side_pair",
    "left_foot",
    "right_foot",
})
_SKELETON_FIT_LANDMARK_SOURCES = frozenset({
    "imported_skeleton",
    "skeleton_node",
})
_PAIRED_LANDMARK_ALIGNMENT_METHOD = "paired_skeleton_landmark_similarity"
_AUTO_FIT_ROTATION_BASES = frozenset({
    "bone_landmark_basis",
    "paired_skeleton_similarity",
})


@dataclass(frozen=True)
class CharacterExportPreflightOptions:
    """Tunable checks for Character Builder MDL/MDX export readiness."""

    export_game: str | None = None
    require_source_mdl: bool = True
    require_native_snapshot: bool = True
    require_native_snapshot_game_match: bool = True
    require_supermodel: bool = True
    require_skin_payload: bool = True
    require_native_bone_map_targets: bool = True
    require_no_non_native_skeleton_nodes: bool = True
    require_required_sockets: bool = True
    require_native_template_final_rig: bool = True
    require_native_render_replacement_evidence: bool = True
    require_auto_fit_evidence: bool = True
    allow_fallback_auto_fit: bool = False
    min_auto_fit_confidence: float = 0.60
    min_auto_fit_paired_landmarks: int = 4
    max_auto_fit_landmark_rms_error: float = 0.15
    max_auto_fit_landmark_pair_error: float = 0.16
    min_auto_fit_toe_forward_alignment: float = 0.50
    min_auto_fit_toe_forward_required_guide_count: int = 8
    strict_parent_paths: bool = True
    required_socket_categories: tuple[str, ...] = (
        "head",
        "right_hand",
        "left_hand",
    )
    recommended_socket_categories: tuple[str, ...] = (
        "lightsaber",
        "combat_helper",
        "camera",
        "headgear",
    )


@dataclass(frozen=True)
class CharacterExportPreflightResult:
    """Result returned by :func:`preflight_character_mdl_export`."""

    report: ValidationReport
    native_snapshot: NativeSkeletonSnapshot | None = None

    @property
    def export_allowed(self) -> bool:
        return not self.report.has_blocking


def preflight_character_mdl_export(
    model: Any,
    *,
    native_snapshot: NativeSkeletonSnapshot | None = None,
    options: CharacterExportPreflightOptions | None = None,
) -> CharacterExportPreflightResult:
    """Validate that a Character Builder model is ready for MDL/MDX export.

    This does not write files.  It verifies the export contract that the engine
    depends on before a future binary writer tries to create a game candidate.
    """

    opts = options or CharacterExportPreflightOptions()
    report = ValidationReport(source="character.export_preflight")

    if model is None:
        report.add(_issue(
            "blocking",
            "character.export.no_model",
            "Character export requires a model.",
            fix_hint="Choose a base KOTOR model and import a custom mesh before exporting.",
        ))
        return CharacterExportPreflightResult(report=report, native_snapshot=None)

    if native_snapshot is None:
        native_snapshot = getattr(model, "_gr_native_skeleton_snapshot", None)

    if native_snapshot is None and opts.require_native_snapshot:
        report.add(_issue(
            "blocking",
            "character.export.missing_native_snapshot",
            "Character export requires a native KOTOR skeleton snapshot.",
            fix_hint="Choose a base KOTOR MDL from the game library before building the character rig.",
        ))
    elif native_snapshot is None:
        try:
            native_snapshot = capture_native_skeleton_snapshot(model)
        except Exception as exc:  # pragma: no cover - defensive only
            report.add(_issue(
                "error",
                "character.export.snapshot_failed",
                f"Could not capture a native skeleton snapshot: {exc}",
            ))

    _validate_resref(model, report)
    _validate_character_rig_state(model, native_snapshot, opts, report)

    if native_snapshot is not None:
        _validate_native_snapshot_game(native_snapshot, opts, report)
        _validate_source_provenance(native_snapshot, opts, report)
        _validate_supermodel(model, native_snapshot, opts, report)
        _validate_native_dag(model, native_snapshot, opts, report)
        _validate_no_non_native_skeleton_nodes(model, native_snapshot, opts, report)
        _validate_socket_categories(model, native_snapshot, opts, report)

    _validate_auto_fit_evidence(model, opts, report)

    if opts.require_skin_payload:
        _validate_skin_payload(model, native_snapshot, opts, report)

    return CharacterExportPreflightResult(report=report, native_snapshot=native_snapshot)


def _validate_character_rig_state(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_native_template_final_rig:
        return
    state = get_character_rig_state(model)
    if is_native_template_final_rig(model):
        _validate_native_template_rig_provenance(
            model,
            state,
            native_snapshot,
            opts,
            report,
        )
        return
    state_data = state.to_dict() if state is not None else None
    report.add(_issue(
        "blocking",
        "character.export.not_native_template_final_rig",
        (
            "Character export requires the final native KOTOR template rig state. "
            "Imported or temporary skeletons cannot be exported as game-ready MDL/MDX."
        ),
        fix_hint="Use Build KOTOR Skeleton from the selected native base before exporting.",
        details={
            "expected_state": RIG_STATE_NATIVE_TEMPLATE_FINAL,
            "actual_state": state_data,
        },
    ))


def _validate_native_template_rig_provenance(
    model: Any,
    state: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    state_data = state.to_dict() if state is not None and hasattr(state, "to_dict") else {}
    payload_mesh_names = [
        str(name or "")
        for name in getattr(state, "payload_mesh_names", ()) or ()
        if str(name or "").strip()
    ]
    missing_state = [
        key
        for key, value in (
            ("native_base_resref", getattr(state, "native_base_resref", "")),
            ("native_base_model_name", getattr(state, "native_base_model_name", "")),
            ("native_base_game", getattr(state, "native_base_game", "")),
            ("imported_payload_name", getattr(state, "imported_payload_name", "")),
        )
        if not str(value or "").strip()
    ]
    if not payload_mesh_names:
        missing_state.append("payload_mesh_names")

    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    bind = metadata.get("character_builder_bind")
    bind = bind if isinstance(bind, dict) else {}
    native_base = bind.get("native_base")
    native_base = native_base if isinstance(native_base, dict) else {}
    imported_payload = bind.get("imported_payload")
    imported_payload = imported_payload if isinstance(imported_payload, dict) else {}
    bind_mesh_names = [
        str(name or "")
        for name in imported_payload.get("mesh_names", []) or []
        if str(name or "").strip()
    ]
    missing_bind = []
    if bind.get("status") != "bound_to_native_kotor_skeleton":
        missing_bind.append("character_builder_bind.status")
    if not str(native_base.get("source_resref") or "").strip():
        missing_bind.append("character_builder_bind.native_base.source_resref")
    if not str(native_base.get("model_name") or "").strip():
        missing_bind.append("character_builder_bind.native_base.model_name")
    if not str(native_base.get("game") or "").strip():
        missing_bind.append("character_builder_bind.native_base.game")
    if native_base.get("dag_authority") != RIG_DAG_AUTHORITY_NATIVE_KOTOR:
        missing_bind.append("character_builder_bind.native_base.dag_authority")
    if not str(native_base.get("dag_fingerprint") or "").strip():
        missing_bind.append("character_builder_bind.native_base.dag_fingerprint")
    if str(native_base.get("dag_fingerprint_algorithm") or "") != "sha256":
        missing_bind.append(
            "character_builder_bind.native_base.dag_fingerprint_algorithm"
        )
    if not str(imported_payload.get("model_name") or "").strip():
        missing_bind.append("character_builder_bind.imported_payload.model_name")
    if imported_payload.get("mesh_role") != MESH_ROLE_PAYLOAD_GUEST:
        missing_bind.append("character_builder_bind.imported_payload.mesh_role")
    if not bind_mesh_names:
        missing_bind.append("character_builder_bind.imported_payload.mesh_names")

    if missing_state or missing_bind:
        report.add(_issue(
            "blocking",
            "character.export.missing_bind_provenance",
            (
                "Character Builder export requires explicit native-base and "
                "imported-payload bind provenance."
            ),
            fix_hint=(
                "Rebuild the KOTOR skeleton from a selected native base model "
                "after importing the custom mesh, then export again."
            ),
            details={
                "missing_rig_state_fields": missing_state,
                "missing_bind_fields": missing_bind,
                "actual_state": state_data,
                "bind": bind,
            },
        ))
        return

    mismatches: dict[str, dict[str, Any]] = {}
    if _casefold(native_base.get("source_resref")) != _casefold(getattr(state, "native_base_resref", "")):
        mismatches["native_base_resref"] = {
            "rig_state": getattr(state, "native_base_resref", ""),
            "bind": native_base.get("source_resref"),
        }
    if str(native_base.get("model_name") or "") != str(getattr(state, "native_base_model_name", "") or ""):
        mismatches["native_base_model_name"] = {
            "rig_state": getattr(state, "native_base_model_name", ""),
            "bind": native_base.get("model_name"),
        }
    if _normalize_kotor_game(native_base.get("game")) != _normalize_kotor_game(getattr(state, "native_base_game", "")):
        mismatches["native_base_game"] = {
            "rig_state": getattr(state, "native_base_game", ""),
            "bind": native_base.get("game"),
        }
    if str(imported_payload.get("model_name") or "") != str(getattr(state, "imported_payload_name", "") or ""):
        mismatches["imported_payload_name"] = {
            "rig_state": getattr(state, "imported_payload_name", ""),
            "bind": imported_payload.get("model_name"),
        }
    if bind_mesh_names != payload_mesh_names:
        mismatches["payload_mesh_names"] = {
            "rig_state": payload_mesh_names,
            "bind": bind_mesh_names,
        }

    if native_snapshot is not None:
        snapshot_fingerprint = native_skeleton_fingerprint(native_snapshot)
        if str(native_base.get("dag_fingerprint") or "") != snapshot_fingerprint:
            mismatches["native_snapshot_dag_fingerprint"] = {
                "bind": native_base.get("dag_fingerprint"),
                "native_snapshot": snapshot_fingerprint,
                "algorithm": "sha256",
            }
        snapshot_metadata = dict(native_snapshot.metadata or {})
        snapshot_resref = str(
            snapshot_metadata.get("source_resref")
            or native_snapshot.model_name
            or ""
        )
        snapshot_game = str(
            snapshot_metadata.get("source_game")
            or native_snapshot.game
            or ""
        )
        if snapshot_resref and _casefold(snapshot_resref) != _casefold(getattr(state, "native_base_resref", "")):
            mismatches["native_snapshot_source_resref"] = {
                "rig_state": getattr(state, "native_base_resref", ""),
                "native_snapshot": snapshot_resref,
            }
        if snapshot_game and _normalize_kotor_game(snapshot_game) != _normalize_kotor_game(getattr(state, "native_base_game", "")):
            mismatches["native_snapshot_game"] = {
                "rig_state": getattr(state, "native_base_game", ""),
                "native_snapshot": snapshot_game,
            }

    if not mismatches:
        _validate_skin_binding_evidence(
            bind,
            metadata.get("kotor_fit_report"),
            report,
        )
        if opts.require_native_render_replacement_evidence:
            _validate_native_render_replacement_evidence(
                model,
                native_snapshot,
                native_base,
                report,
            )
        return

    report.add(_issue(
        "blocking",
        "character.export.bind_provenance_mismatch",
        (
            "Character Builder bind provenance disagrees about which native "
            "base skeleton or imported payload owns this export candidate."
        ),
        fix_hint=(
            "Rebuild the KOTOR skeleton from the selected native base model so "
            "rig state, bind metadata, and native snapshot evidence agree."
        ),
        details={
            "mismatches": mismatches,
            "actual_state": state_data,
            "bind": bind,
            "native_snapshot": (
                {
                    "model_name": native_snapshot.model_name,
                    "game": native_snapshot.game,
                    "metadata": dict(native_snapshot.metadata or {}),
                }
                if native_snapshot is not None else
                None
            ),
        },
    ))

    if opts.require_native_render_replacement_evidence:
        _validate_native_render_replacement_evidence(
            model,
            native_snapshot,
            native_base,
            report,
        )


def _validate_skin_binding_evidence(
    bind: dict[str, Any],
    fit_report: Any,
    report: ValidationReport,
) -> None:
    skin_binding = bind.get("skin_binding")
    if not isinstance(skin_binding, dict):
        report.add(_issue(
            "warning",
            "character.export.missing_skin_binding_evidence",
            "Character export has no explicit skin-binding quality evidence.",
            fix_hint=(
                "Rebuild the KOTOR skeleton so Character Builder records whether "
                "weights came from fallback nearest-bone skinning or donor/native-template transfer."
            ),
        ))
        return

    weighting_method = str(skin_binding.get("weighting_method") or "")
    quality_stage = str(skin_binding.get("quality_stage") or "")
    donor_weight_transfer = bool(skin_binding.get("donor_weight_transfer"))
    source_skin_remap = bool(skin_binding.get("source_skin_remap"))
    source_hand_refinement = bool(skin_binding.get("source_hand_refinement"))
    mesh_reports = list(skin_binding.get("mesh_reports") or [])
    if donor_weight_transfer:
        landmark_gaps = _donor_weight_fit_landmark_gaps(fit_report)
        # T2518: the correspondence fit (trace v2, T2511) registers the whole
        # imported surface onto the donor surface — it neither uses nor records
        # role landmarks, so "incomplete landmark evidence" is vacuous noise
        # for that policy rather than a review signal.
        if _fit_policy_is_correspondence(fit_report):
            landmark_gaps = {}
        if landmark_gaps:
            report.add(_issue(
                "warning",
                "character.export.donor_skin_binding_landmarks_incomplete",
                (
                    "Character Builder donor weight transfer does not have "
                    "complete fit landmark evidence."
                ),
                fix_hint=(
                    "Re-run Auto-Fit with visible head, pelvis, shoulder/side, "
                    "and both foot landmarks before treating donor weights as "
                    "trusted deformation evidence."
                ),
                details={
                    "weighting_method": weighting_method,
                    "quality_stage": quality_stage,
                    "donor_weight_transfer": donor_weight_transfer,
                    **landmark_gaps,
                },
            ))
    if (
        weighting_method == "nearest_kotor_bone_segment"
        or quality_stage == "fallback_first_pass"
        or quality_stage == "donor_transfer_partial"
        or quality_stage == "source_skin_remap_partial"
        or (not donor_weight_transfer and not source_skin_remap)
    ):
        report.add(_issue(
            "warning",
            "character.export.fallback_skin_binding",
            (
                "Character Builder is using fallback, partial, or unproven skin "
                "weights. This is exportable but not launch-quality deformation "
                "evidence."
            ),
            fix_hint=(
                "Use imported source skin remap or native-template/donor weight "
                "transfer and preview inherited animations before treating this "
                "character as game-ready."
            ),
            details={
                "weighting_method": weighting_method,
                "quality_stage": quality_stage,
                "donor_weight_transfer": donor_weight_transfer,
                "source_skin_remap": source_skin_remap,
                "source_hand_refinement": source_hand_refinement,
                "mesh_reports": mesh_reports,
            },
        ))


def _fit_policy_is_correspondence(fit_report: Any) -> bool:
    """True when the fit came from the T2511 correspondence dispatch path."""
    fit = fit_report if isinstance(fit_report, dict) else {}
    return (
        str(fit.get("fit_policy") or "").strip()
        == "correspondence_surface_registration"
    )


def _donor_weight_fit_landmark_gaps(fit_report: Any) -> dict[str, Any]:
    fit = fit_report if isinstance(fit_report, dict) else {}
    auto_fit = fit.get("auto_fit_report")
    auto_fit = auto_fit if isinstance(auto_fit, dict) else {}
    labels = [
        str(label or "")
        for label in (
            list(fit.get("used_landmarks") or [])
            + list(auto_fit.get("used_landmarks") or [])
        )
        if str(label or "").strip()
    ]
    roles_by_prefix: dict[str, set[str]] = {"source": set(), "target": set()}
    for label in labels:
        prefix, role = _parse_fit_landmark_label(label)
        if prefix in roles_by_prefix and role:
            roles_by_prefix[prefix].add(role)

    required = set(_DONOR_WEIGHT_REQUIRED_FIT_LANDMARKS)
    source_missing = sorted(required - roles_by_prefix["source"])
    target_missing = sorted(required - roles_by_prefix["target"])
    if not source_missing and not target_missing:
        return {}
    return {
        "required_landmarks": sorted(required),
        "source_landmarks": sorted(roles_by_prefix["source"]),
        "target_landmarks": sorted(roles_by_prefix["target"]),
        "missing_source_landmarks": source_missing,
        "missing_target_landmarks": target_missing,
        "used_landmarks": sorted(set(labels)),
    }


def _parse_fit_landmark_label(label: str) -> tuple[str, str]:
    text = str(label or "").strip()
    if ":" not in text:
        return "", ""
    prefix, rest = text.split(":", 1)
    role = rest.split("=", 1)[0].strip()
    return prefix.strip().lower(), role.lower()


def _validate_auto_fit_evidence(
    model: Any,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    """Validate that an imported payload was fitted before native binding."""

    if not opts.require_auto_fit_evidence or not is_native_template_final_rig(model):
        return

    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    fit_report = metadata.get("kotor_fit_report")
    if not isinstance(fit_report, dict):
        report.add(_issue(
            "blocking",
            "character.export.missing_auto_fit_evidence",
            "Character export requires recorded auto-fit evidence.",
            fix_hint=(
                "Run Auto-Fit or confirm a manual fit against the selected KOTOR "
                "base skeleton before building and exporting the character."
            ),
        ))
        return

    fit_policy = str(fit_report.get("fit_policy") or "").strip()
    fit_transform = fit_report.get("fit_transform")
    fit_transform = fit_transform if isinstance(fit_transform, dict) else {}
    contract = fit_report.get("kotor_contract")
    contract = contract if isinstance(contract, dict) else {}
    auto_fit_report = fit_report.get("auto_fit_report")
    auto_fit_report = auto_fit_report if isinstance(auto_fit_report, dict) else {}

    missing_fields: list[str] = []
    if not fit_policy:
        missing_fields.append("fit_policy")
    if not fit_transform:
        missing_fields.append("fit_transform")
    if not contract:
        missing_fields.append("kotor_contract")

    if missing_fields:
        report.add(_issue(
            "blocking",
            "character.export.incomplete_auto_fit_evidence",
            "Character auto-fit evidence is incomplete.",
            fix_hint=(
                "Re-run Auto-Fit so the report records fit policy, transform, "
                "and KOTOR native-DAG contract evidence."
            ),
            details={"missing_fields": missing_fields, "fit_report": fit_report},
        ))

    scale = _safe_float(fit_transform.get("scale"))
    if scale is None or not math.isfinite(scale) or scale <= 0.0:
        report.add(_issue(
            "blocking",
            "character.export.invalid_auto_fit_scale",
            "Character auto-fit evidence has an invalid scale.",
            fix_hint="Re-run Auto-Fit; the fitted mesh scale must be finite and positive.",
            details={"scale": fit_transform.get("scale")},
        ))

    try:
        translation = _numeric_components(fit_transform.get("translation", ()))
    except (TypeError, ValueError, OverflowError):
        translation = []
    if len(translation) != 3 or not _all_finite(translation):
        report.add(_issue(
            "blocking",
            "character.export.invalid_auto_fit_translation",
            "Character auto-fit evidence has an invalid translation.",
            fix_hint="Re-run Auto-Fit; the fitted mesh translation must be a finite XYZ vector.",
            details={
                "translation": fit_transform.get("translation"),
                "component_count": len(translation),
            },
        ))

    confidence = _safe_float(
        fit_report.get("confidence", auto_fit_report.get("confidence"))
    )
    if confidence is None or not math.isfinite(confidence):
        report.add(_issue(
            "blocking",
            "character.export.missing_auto_fit_confidence",
            "Character auto-fit evidence has no finite confidence score.",
            fix_hint="Re-run Auto-Fit or confirm a manual fit so confidence is recorded.",
        ))
    elif confidence < float(opts.min_auto_fit_confidence):
        report.add(_issue(
            "blocking",
            "character.export.low_auto_fit_confidence",
            (
                f"Character auto-fit confidence {confidence:.3f} is below the "
                f"required {float(opts.min_auto_fit_confidence):.3f} threshold."
            ),
            fix_hint=(
                "Improve the mesh fit with landmarks or manual axis/ground "
                "overrides before exporting."
            ),
            details={
                "confidence": confidence,
                "required_confidence": float(opts.min_auto_fit_confidence),
                "fit_policy": fit_policy,
            },
        ))

    _validate_auto_fit_transform_matrices(
        fit_transform=fit_transform,
        scale=scale,
        report=report,
    )

    fallback_used = bool(
        fit_report.get("fallback_used", auto_fit_report.get("fallback_used", False))
    )
    if fallback_used and not opts.allow_fallback_auto_fit:
        report.add(_issue(
            "blocking",
            "character.export.fallback_auto_fit_used",
            "Character export cannot rely on fallback bounds-only auto-fit evidence.",
            fix_hint=(
                "Use bone landmarks or an explicit manual axis/ground override "
                "so the imported mesh is fitted to the KOTOR skeleton intentionally."
            ),
            details={"fit_policy": fit_policy, "fit_report": fit_report},
        ))

    landmark_sources = _auto_fit_source_landmark_sources(fit_report)
    # T2518: correspondence-fit results (fit_policy
    # "correspondence_surface_registration", trace v2/T2511) register the whole
    # imported surface onto the donor surface; role landmarks are neither used
    # nor recorded, so the landmark-source advisories below would fire on every
    # correspondence export as unfixable noise.  Skip them for that policy —
    # the correspondence trace carries its own evidence (surface confidence,
    # falsifier reports).
    if fit_policy == "correspondence_surface_registration":
        pass
    elif not landmark_sources:
        report.add(_issue(
            "warning",
            "character.export.auto_fit_landmark_sources_not_recorded",
            "Character auto-fit evidence does not record which source landmarks drove orientation and scale.",
            fix_hint=(
                "Re-run Auto-Fit with the current Character Builder so the report "
                "records whether imported skeleton or mesh payload landmarks drove the fit."
            ),
            details={
                "fit_policy": fit_policy,
                "source_landmark_domain": "not_recorded",
            },
        ))
    else:
        non_skeleton_sources = {
            role: source
            for role, source in landmark_sources.items()
            if source not in _SKELETON_FIT_LANDMARK_SOURCES
        }
        if non_skeleton_sources:
            counts: dict[str, int] = {}
            for source in landmark_sources.values():
                counts[source] = counts.get(source, 0) + 1
            report.add(_issue(
                "warning",
                "character.export.auto_fit_source_landmarks_need_review",
                (
                    "Character auto-fit was not fully driven by imported skeleton "
                    "or armature landmarks."
                ),
                fix_hint=(
                    "For rigged FBX imports, re-run Auto-Fit so the imported "
                    "skeleton drives orientation and scale. If this is a mesh-only "
                    "import, manually review the fit before treating it as "
                    "launch-quality evidence."
                ),
                details={
                    "fit_policy": fit_policy,
                    "source_landmark_sources": dict(landmark_sources),
                    "source_landmark_source_counts": counts,
                    "non_skeleton_sources": non_skeleton_sources,
                    "accepted_skeleton_sources": sorted(_SKELETON_FIT_LANDMARK_SOURCES),
                },
            ))
        imported_skeleton_roles = sorted(
            role for role, source in landmark_sources.items()
            if source == "imported_skeleton"
        )
        if imported_skeleton_roles:
            imported_guide_evidence = _auto_fit_imported_skeleton_guide_evidence(
                fit_report
            )
            guide_count = _safe_int(imported_guide_evidence.get("guide_joint_count")) or 0
            scene_count = _safe_int(imported_guide_evidence.get("scene_guide_joint_count")) or 0
            if guide_count <= 0 and scene_count <= 0:
                report.add(_issue(
                    "warning",
                    "character.export.auto_fit_imported_skeleton_guides_not_recorded",
                    (
                        "Character auto-fit used imported skeleton landmarks but "
                        "does not preserve the imported guide inventory."
                    ),
                    fix_hint=(
                        "Re-run Auto-Fit with the current Character Builder so the "
                        "fit report records the imported FBX armature or skeleton "
                        "guide count before the native KOTOR rig strips temporary "
                        "guide nodes."
                    ),
                    details={
                        "fit_policy": fit_policy,
                        "imported_skeleton_roles": imported_skeleton_roles,
                        "source_imported_armature": dict(imported_guide_evidence),
                    },
                ))

    _validate_paired_landmark_alignment(
        fit_policy=fit_policy,
        fit_transform=fit_transform,
        opts=opts,
        report=report,
    )
    _validate_toe_forward_alignment(
        fit_policy=fit_policy,
        fit_report=fit_report,
        opts=opts,
        report=report,
    )

    contract_mismatches: dict[str, Any] = {}
    if contract.get("native_skeleton_is_authority") is not True:
        contract_mismatches["native_skeleton_is_authority"] = contract.get(
            "native_skeleton_is_authority"
        )
    if contract.get("imported_mesh_role") != MESH_ROLE_PAYLOAD_GUEST:
        contract_mismatches["imported_mesh_role"] = contract.get("imported_mesh_role")
    if contract.get("final_dag_source") != "selected_kotor_base":
        contract_mismatches["final_dag_source"] = contract.get("final_dag_source")
    if contract_mismatches:
        report.add(_issue(
            "blocking",
            "character.export.auto_fit_contract_mismatch",
            "Character auto-fit evidence does not preserve the native KOTOR DAG contract.",
            fix_hint=(
                "Re-run Auto-Fit and Build KOTOR Skeleton from the selected native "
                "base model; the imported mesh must remain a payload guest."
            ),
            details={"mismatches": contract_mismatches, "kotor_contract": contract},
        ))


def _validate_paired_landmark_alignment(
    *,
    fit_policy: str,
    fit_transform: dict[str, Any],
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if fit_policy != "bone_landmark_basis":
        return

    alignment = fit_transform.get("landmark_alignment")
    alignment = alignment if isinstance(alignment, dict) else {}
    if not alignment:
        report.add(_issue(
            "warning",
            "character.export.auto_fit_paired_landmarks_need_review",
            "Character auto-fit evidence does not include paired skeleton-landmark alignment quality.",
            fix_hint=(
                "Re-run Auto-Fit with the current Character Builder so source and "
                "KOTOR skeleton landmark pairs are recorded and scored."
            ),
            details={
                "reason": "not_recorded",
                "fit_policy": fit_policy,
                "required_pair_count": int(opts.min_auto_fit_paired_landmarks),
                "max_rms_error": float(opts.max_auto_fit_landmark_rms_error),
                "max_pair_error": float(opts.max_auto_fit_landmark_pair_error),
            },
        ))
        return

    method = str(alignment.get("method") or "")
    pair_count = _safe_int(alignment.get("pair_count"))
    rms_error = _safe_float(alignment.get("rms_error"))
    max_error = _safe_float(alignment.get("max_error"))
    rotation_basis = str(alignment.get("rotation_basis") or "")
    similarity_accepted = alignment.get("similarity_transform_accepted")
    reasons: list[str] = []
    if method != _PAIRED_LANDMARK_ALIGNMENT_METHOD:
        reasons.append("unexpected_method")
    if pair_count is None or pair_count < int(opts.min_auto_fit_paired_landmarks):
        reasons.append("too_few_pairs")
    if rms_error is None or not math.isfinite(rms_error):
        reasons.append("missing_rms_error")
    elif rms_error > float(opts.max_auto_fit_landmark_rms_error):
        reasons.append("high_rms_error")
    if max_error is None or not math.isfinite(max_error):
        reasons.append("missing_max_error")
    elif max_error > float(opts.max_auto_fit_landmark_pair_error):
        reasons.append("high_max_error")
    if not isinstance(similarity_accepted, bool):
        reasons.append("missing_similarity_transform_acceptance")
    if not rotation_basis:
        reasons.append("missing_rotation_basis")
    elif rotation_basis not in _AUTO_FIT_ROTATION_BASES:
        reasons.append("unexpected_rotation_basis")
    if (
        isinstance(similarity_accepted, bool)
        and rotation_basis in _AUTO_FIT_ROTATION_BASES
        and (
            (similarity_accepted and rotation_basis != "paired_skeleton_similarity")
            or (not similarity_accepted and rotation_basis == "paired_skeleton_similarity")
        )
    ):
        reasons.append("rotation_acceptance_mismatch")

    if not reasons:
        return

    report.add(_issue(
        "warning",
        "character.export.auto_fit_paired_landmarks_need_review",
        "Character auto-fit paired skeleton-landmark alignment needs review.",
        fix_hint=(
            "Review the fitted source/target landmarks before treating this "
            "character as launch-quality. Re-run Auto-Fit or adjust the imported "
            "mesh/skeleton if the source does not align with the KOTOR base."
        ),
        details={
            "reason": ",".join(reasons),
            "reasons": reasons,
            "method": method,
            "pair_count": pair_count,
            "paired_roles": list(alignment.get("paired_roles") or []),
            "required_pair_count": int(opts.min_auto_fit_paired_landmarks),
            "rms_error": rms_error,
            "max_error": max_error,
            "max_rms_error": float(opts.max_auto_fit_landmark_rms_error),
            "max_pair_error": float(opts.max_auto_fit_landmark_pair_error),
            "worst_pair_role": str(alignment.get("worst_pair_role") or ""),
            "pair_errors": list(alignment.get("pair_errors") or []),
            "applied_scale": _safe_float(alignment.get("applied_scale")),
            "solved_scale": _safe_float(alignment.get("solved_scale")),
            "applied_scale_basis": str(alignment.get("applied_scale_basis") or ""),
            "similarity_transform_accepted": similarity_accepted,
            "rotation_basis": rotation_basis,
            "accepted_rotation_bases": sorted(_AUTO_FIT_ROTATION_BASES),
        },
    ))


def _validate_auto_fit_transform_matrices(
    *,
    fit_transform: dict[str, Any],
    scale: float | None,
    report: ValidationReport,
) -> None:
    rotation, rotation_reason = _auto_fit_matrix3(
        fit_transform.get("rotation_matrix")
    )
    linear, linear_reason = _auto_fit_matrix3(
        fit_transform.get("linear_matrix")
    )
    reasons: list[str] = []
    if rotation_reason:
        reasons.append(f"rotation_matrix_{rotation_reason}")
    if linear_reason:
        reasons.append(f"linear_matrix_{linear_reason}")

    rotation_det: float | None = None
    linear_det: float | None = None
    max_linear_delta: float | None = None
    if rotation is not None:
        rotation_det = _matrix3_determinant(rotation)
        if not math.isfinite(rotation_det) or rotation_det <= 0.0:
            reasons.append("rotation_matrix_reflected_or_degenerate")
        orthonormal_error = _rotation_orthonormal_error(rotation)
        if orthonormal_error > 0.05:
            reasons.append("rotation_matrix_not_orthonormal")
    else:
        orthonormal_error = None
    if linear is not None:
        linear_det = _matrix3_determinant(linear)
        if not math.isfinite(linear_det) or linear_det <= 0.0:
            reasons.append("linear_matrix_reflected_or_degenerate")
    if rotation is not None and linear is not None and scale is not None:
        max_linear_delta = _max_scaled_matrix_delta(rotation, linear, scale)
        if max_linear_delta > 1.0e-4:
            reasons.append("linear_matrix_scale_mismatch")

    if not reasons:
        return

    report.add(_issue(
        "warning",
        "character.export.auto_fit_transform_matrix_needs_review",
        "Character auto-fit transform matrix evidence needs review.",
        fix_hint=(
            "Re-run Auto-Fit with the current Character Builder so the report "
            "records a finite, non-reflected rotation matrix and a linear matrix "
            "that matches the recorded scale."
        ),
        details={
            "reasons": sorted(set(reasons)),
            "scale": scale,
            "rotation_determinant": rotation_det,
            "linear_determinant": linear_det,
            "rotation_orthonormal_error": orthonormal_error,
            "max_linear_scale_delta": max_linear_delta,
        },
    ))


def _auto_fit_matrix3(value: Any) -> tuple[tuple[tuple[float, float, float], ...] | None, str]:
    if value is None:
        return None, "not_recorded"
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None, "malformed"
    rows: list[tuple[float, float, float]] = []
    for row in value:
        try:
            components = _numeric_components(row)
        except (TypeError, ValueError, OverflowError):
            return None, "malformed"
        if len(components) != 3 or not _all_finite(components):
            return None, "malformed"
        rows.append((float(components[0]), float(components[1]), float(components[2])))
    return tuple(rows), ""


def _matrix3_determinant(matrix: tuple[tuple[float, float, float], ...]) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _rotation_orthonormal_error(
    matrix: tuple[tuple[float, float, float], ...],
) -> float:
    max_error = 0.0
    for row_index, row in enumerate(matrix):
        row_len_sq = sum(component * component for component in row)
        max_error = max(max_error, abs(row_len_sq - 1.0))
        for other_index in range(row_index + 1, 3):
            dot = sum(row[i] * matrix[other_index][i] for i in range(3))
            max_error = max(max_error, abs(dot))
    return float(max_error)


def _max_scaled_matrix_delta(
    rotation: tuple[tuple[float, float, float], ...],
    linear: tuple[tuple[float, float, float], ...],
    scale: float,
) -> float:
    max_delta = 0.0
    for row_index in range(3):
        for column_index in range(3):
            expected = float(rotation[row_index][column_index]) * float(scale)
            actual = float(linear[row_index][column_index])
            max_delta = max(max_delta, abs(actual - expected))
    return float(max_delta)


def _validate_toe_forward_alignment(
    *,
    fit_policy: str,
    fit_report: dict[str, Any],
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if fit_policy != "bone_landmark_basis":
        return

    threshold = float(opts.min_auto_fit_toe_forward_alignment)
    require_toe_forward = _auto_fit_should_require_toe_forward(fit_report, opts)
    if require_toe_forward:
        source_frame = fit_report.get("source_frame")
        source_frame = source_frame if isinstance(source_frame, dict) else {}
        if not _auto_fit_frame_has_toe_landmarks(source_frame):
            report.add(_issue(
                "warning",
                "character.export.auto_fit_toe_forward_needs_review",
                "Character auto-fit toe-forward facing evidence is missing for a rigged source skeleton.",
                fix_hint=(
                    "Re-run Auto-Fit with the current Character Builder so imported "
                    "FBX foot-end or toe guide landmarks are recorded before the "
                    "native KOTOR rig strips temporary guide nodes."
                ),
                details={
                    "reason": "source_toe_landmarks_not_recorded",
                    "reasons": ["source_toe_landmarks_not_recorded"],
                    "frame": "source_frame",
                    "toe_forward_alignment": _safe_float(
                        source_frame.get("toe_forward_alignment")
                    ),
                    "required_alignment": threshold,
                    "landmarks": dict(source_frame.get("landmarks") or {}),
                    "landmark_sources": dict(source_frame.get("landmark_sources") or {}),
                    "source_imported_armature": dict(
                        _auto_fit_imported_skeleton_guide_evidence(fit_report)
                    ),
                    "fit_policy": fit_policy,
                },
            ))
        target_frame = fit_report.get("target_frame")
        target_frame = target_frame if isinstance(target_frame, dict) else {}
        if not _auto_fit_frame_has_toe_landmarks(target_frame):
            report.add(_issue(
                "warning",
                "character.export.auto_fit_toe_forward_needs_review",
                "Character auto-fit toe-forward facing evidence is missing for the selected KOTOR base.",
                fix_hint=(
                    "Re-run Auto-Fit with the current Character Builder and selected "
                    "native KOTOR base so target foot/toe landmarks are recorded for "
                    "orientation review."
                ),
                details={
                    "reason": "target_toe_landmarks_not_recorded",
                    "reasons": ["target_toe_landmarks_not_recorded"],
                    "frame": "target_frame",
                    "toe_forward_alignment": _safe_float(
                        target_frame.get("toe_forward_alignment")
                    ),
                    "required_alignment": threshold,
                    "landmarks": dict(target_frame.get("landmarks") or {}),
                    "landmark_sources": dict(target_frame.get("landmark_sources") or {}),
                    "source_imported_armature": dict(
                        _auto_fit_imported_skeleton_guide_evidence(fit_report)
                    ),
                    "fit_policy": fit_policy,
                },
            ))

    for frame_name in ("source_frame", "target_frame"):
        frame = fit_report.get(frame_name)
        frame = frame if isinstance(frame, dict) else {}
        if not _auto_fit_frame_has_toe_landmarks(frame):
            continue
        alignment = _safe_float(frame.get("toe_forward_alignment"))
        reasons: list[str] = []
        if alignment is None or not math.isfinite(alignment):
            reasons.append("not_recorded")
        elif alignment < threshold:
            reasons.append("low_alignment")
        if not reasons:
            continue
        report.add(_issue(
            "warning",
            "character.export.auto_fit_toe_forward_needs_review",
            "Character auto-fit toe-forward facing evidence needs review.",
            fix_hint=(
                "Review the imported mesh orientation and selected KOTOR base. "
                "Toe or foot-end guide direction should agree with the inferred "
                "humanoid forward axis before treating this fit as launch-quality."
            ),
            details={
                "reason": ",".join(reasons),
                "reasons": reasons,
                "frame": frame_name,
                "toe_forward_alignment": alignment,
                "required_alignment": threshold,
                "landmarks": dict(frame.get("landmarks") or {}),
                "landmark_sources": dict(frame.get("landmark_sources") or {}),
                "fit_policy": fit_policy,
            },
        ))


def _auto_fit_frame_has_toe_landmarks(frame: dict[str, Any]) -> bool:
    landmarks = frame.get("landmarks")
    landmarks = landmarks if isinstance(landmarks, dict) else {}
    return bool(
        landmarks.get("left_foot")
        and landmarks.get("right_foot")
        and landmarks.get("left_toe")
        and landmarks.get("right_toe")
    )


def _auto_fit_should_require_toe_forward(
    fit_report: dict[str, Any],
    opts: CharacterExportPreflightOptions,
) -> bool:
    source_frame = fit_report.get("source_frame")
    source_frame = source_frame if isinstance(source_frame, dict) else {}
    landmark_sources = _auto_fit_source_landmark_sources(fit_report)
    if not any(source == "imported_skeleton" for source in landmark_sources.values()):
        return False
    if not (
        landmark_sources.get("left_foot") == "imported_skeleton"
        and landmark_sources.get("right_foot") == "imported_skeleton"
    ):
        return False
    imported = _auto_fit_imported_skeleton_guide_evidence(fit_report)
    guide_count = _safe_int(imported.get("guide_joint_count")) or 0
    scene_count = _safe_int(imported.get("scene_guide_joint_count")) or 0
    required = int(opts.min_auto_fit_toe_forward_required_guide_count)
    return max(guide_count, scene_count) >= required


def _auto_fit_source_landmark_sources(fit_report: dict[str, Any]) -> dict[str, str]:
    source_frame = fit_report.get("source_frame")
    source_frame = source_frame if isinstance(source_frame, dict) else {}
    raw_sources = source_frame.get("landmark_sources")
    raw_sources = raw_sources if isinstance(raw_sources, dict) else {}
    return {
        str(role or ""): str(source or "")
        for role, source in raw_sources.items()
        if str(role or "").strip()
    }


def _auto_fit_imported_skeleton_guide_evidence(fit_report: dict[str, Any]) -> dict[str, Any]:
    raw = fit_report.get("source_imported_armature")
    return dict(raw) if isinstance(raw, dict) else {}


def _validate_native_render_replacement_evidence(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    native_base: dict[str, Any],
    report: ValidationReport,
) -> None:
    """Require absent native render leaves to be explicitly replacement-audited."""

    if native_snapshot is None:
        return

    replacements_raw = native_base.get("replaced_render_payload_nodes", [])
    replacements = [
        item for item in replacements_raw
        if isinstance(item, dict)
    ]
    replacement_count = native_base.get("replaced_render_payload_count")
    if replacement_count is not None:
        try:
            if int(replacement_count) != len(replacements):
                report.add(_issue(
                    "blocking",
                    "character.export.render_replacement_count_mismatch",
                    "Native render replacement evidence count does not match the replacement list.",
                    fix_hint="Rebuild the KOTOR skeleton so bind evidence is regenerated.",
                    details={
                        "declared_count": replacement_count,
                        "actual_count": len(replacements),
                    },
                ))
        except Exception:
            report.add(_issue(
                "blocking",
                "character.export.render_replacement_count_malformed",
                "Native render replacement evidence has a malformed replacement count.",
                fix_hint="Rebuild the KOTOR skeleton so bind evidence is regenerated.",
                details={"declared_count": replacement_count},
            ))

    current_paths = {
        normalize_model_path_to_native_snapshot(
            native_snapshot,
            model,
            _node_path(node),
        )
        for node in _iter_nodes(model)
    }
    snapshot_by_path = {
        tuple(node.full_path): node
        for node in native_snapshot.nodes
    }
    replacement_by_path: dict[tuple[str, ...], dict[str, Any]] = {}
    invalid_replacements: list[dict[str, Any]] = []
    for entry in replacements:
        path = _replacement_path(entry)
        if not path:
            invalid_replacements.append({
                "reason": "missing_path",
                "entry": entry,
            })
            continue
        native_node = snapshot_by_path.get(path)
        if native_node is None:
            invalid_replacements.append({
                "reason": "path_not_in_native_snapshot",
                "path": list(path),
            })
            continue
        if native_node.export_role not in _REPLACEABLE_RENDER_ROLES:
            invalid_replacements.append({
                "reason": "not_replaceable_render_payload",
                "path": list(path),
                "role": native_node.export_role,
            })
            continue
        if str(entry.get("replacement") or "") != "imported_mesh_payload":
            invalid_replacements.append({
                "reason": "unexpected_replacement_role",
                "path": list(path),
                "replacement": entry.get("replacement"),
            })
            continue
        fact_mismatches = _replacement_fact_mismatches(entry, native_node)
        if fact_mismatches:
            invalid_replacements.append({
                "reason": "native_fact_mismatch",
                "path": list(path),
                "mismatches": fact_mismatches,
            })
            continue
        if path in current_paths:
            invalid_replacements.append({
                "reason": "node_still_present",
                "path": list(path),
                "role": native_node.export_role,
            })
            continue
        replacement_by_path[path] = entry

    if invalid_replacements:
        report.add(_issue(
            "blocking",
            "character.export.invalid_native_render_replacement_evidence",
            "Native render replacement evidence includes invalid or non-native nodes.",
            fix_hint=(
                "Rebuild the KOTOR skeleton from the selected native base; "
                "only native render mesh/skin payload leaves may be recorded as replaced."
            ),
            details={
                "invalid_replacements": invalid_replacements,
                "native_snapshot_model": native_snapshot.model_name,
                "native_snapshot_game": native_snapshot.game,
            },
        ))

    missing_replacements: list[dict[str, Any]] = []
    for native_node in native_snapshot.nodes:
        if native_node.export_role not in _REPLACEABLE_RENDER_ROLES:
            continue
        path = tuple(native_node.full_path)
        if path in current_paths:
            continue
        if path in replacement_by_path:
            continue
        missing_replacements.append({
            "name": native_node.name,
            "path": list(path),
            "role": native_node.export_role,
            "vertex_count": native_node.vertex_count,
            "face_count": native_node.face_count,
            "texture": native_node.texture,
        })

    if missing_replacements:
        report.add(_issue(
            "blocking",
            "character.export.missing_native_render_replacement_evidence",
            (
                "One or more native KOTOR render payload nodes are absent from "
                "the final DAG without explicit imported-payload replacement evidence."
            ),
            fix_hint=(
                "Rebuild the KOTOR skeleton after importing the custom mesh so "
                "GhostRigger records which native render skins were intentionally replaced."
            ),
            details={
                "missing_replacements": missing_replacements,
                "native_snapshot_model": native_snapshot.model_name,
                "native_snapshot_game": native_snapshot.game,
                "expected_replacement": "imported_mesh_payload",
            },
        ))


def _replacement_path(entry: dict[str, Any]) -> tuple[str, ...]:
    raw = entry.get("path", ())
    if isinstance(raw, str):
        parts = [part for part in raw.replace("\\", "/").split("/") if part]
    else:
        try:
            parts = [str(part or "") for part in raw]
        except Exception:
            parts = []
    return tuple(part for part in parts if part)


def _replacement_fact_mismatches(
    entry: dict[str, Any],
    native_node: NativeNodeSnapshot,
) -> dict[str, dict[str, Any]]:
    """Return replacement record fields that disagree with the snapshot."""

    expected = {
        "name": native_node.name,
        "is_mesh": native_node.is_mesh,
        "is_skin": native_node.is_skin,
        "vertex_count": native_node.vertex_count,
        "face_count": native_node.face_count,
        "texture": native_node.texture,
    }
    actual = {
        "name": str(entry.get("name") or ""),
        "is_mesh": bool(entry.get("is_mesh")),
        "is_skin": bool(entry.get("is_skin")),
        "vertex_count": _safe_int(entry.get("vertex_count")),
        "face_count": _safe_int(entry.get("face_count")),
        "texture": str(entry.get("texture") or ""),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            mismatches[key] = {
                "expected": expected_value,
                "actual": actual.get(key),
            }
    return mismatches


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _validate_resref(model: Any, report: ValidationReport) -> None:
    name = str(getattr(model, "name", "") or "").strip()
    if not name:
        report.add(_issue(
            "blocking",
            "character.export.empty_resref",
            "Character model resref is empty.",
            fix_hint="Assign a stable KOTOR resref before export.",
        ))
        return
    if len(name) > KOTOR_NATIVE_RESREF_MAX_LEN:
        report.add(_issue(
            "blocking",
            "character.export.resref_too_long",
            (
                f"Character model resref '{name}' is longer than "
                f"{KOTOR_NATIVE_RESREF_MAX_LEN} characters."
            ),
            fix_hint="Use a KOTOR-safe resref of 16 characters or fewer.",
            details={"resref": name, "max_length": KOTOR_NATIVE_RESREF_MAX_LEN},
        ))


def _validate_native_snapshot_game(
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_native_snapshot_game_match:
        return
    export_game = _normalize_kotor_game(opts.export_game)
    if not export_game:
        return

    metadata = dict(snapshot.metadata or {})
    game_facts = {
        "snapshot_game": snapshot.game,
        "metadata_source_game": metadata.get("source_game"),
        "metadata_game": metadata.get("game"),
    }
    normalized_facts = {
        key: _normalize_kotor_game(value)
        for key, value in game_facts.items()
        if str(value or "").strip()
    }
    matching_facts = {
        key: value
        for key, value in normalized_facts.items()
        if value == export_game
    }
    mismatches = {
        key: value
        for key, value in normalized_facts.items()
        if value and value != "UNKNOWN" and value != export_game
    }
    if not matching_facts and not mismatches:
        report.add(_issue(
            "blocking",
            "character.export.native_snapshot_game_unknown",
            (
                "Native skeleton snapshot does not prove which KOTOR game it "
                f"came from, but the export request targets {export_game}."
            ),
            fix_hint=(
                "Choose a base KOTOR model from the configured K1/K2 game "
                "library, then rebuild the native template rig before exporting."
            ),
            details={
                "export_game": export_game,
                "native_game_facts": game_facts,
                "normalized_native_game_facts": normalized_facts,
            },
        ))
        return
    if not mismatches:
        return

    report.add(_issue(
        "blocking",
        "character.export.native_snapshot_game_mismatch",
        (
            f"Native skeleton snapshot is for {', '.join(sorted(set(mismatches.values())))} "
            f"but the export request targets {export_game}."
        ),
        fix_hint=(
            "Choose a base KOTOR model from the same game as the export target, "
            "then rebuild the native template rig before exporting."
        ),
        details={
            "export_game": export_game,
            "native_game_facts": game_facts,
            "normalized_native_game_facts": normalized_facts,
            "mismatches": mismatches,
        },
    ))


def _validate_source_provenance(
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_source_mdl:
        return
    metadata = dict(snapshot.metadata or {})
    has_source = bool(
        metadata.get("source_mdl_path")
        or metadata.get("source_resref")
        or metadata.get("source_resource_address")
    )
    if not has_source:
        report.add(_issue(
            "blocking",
            "character.export.no_native_source",
            "Native skeleton snapshot has no source MDL provenance.",
            fix_hint=(
                "Load the base skeleton from a game-library MDL/resref so export "
                "can preserve the native DAG instead of guessing it."
            ),
            details={"model_name": snapshot.model_name},
        ))


def _validate_supermodel(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_supermodel:
        return
    expected = str(snapshot.supermodel or "NULL").strip()
    actual = str(getattr(model, "supermodel", "") or "NULL").strip()
    if expected.upper() in _NULL_SUPERMODELS:
        if actual.upper() in _NULL_SUPERMODELS:
            return
        report.add(_issue(
            "warning",
            "character.export.supermodel_added",
            (
                f"Generated character uses supermodel '{actual}', but the native "
                f"base model '{snapshot.model_name}' had no supermodel."
            ),
            fix_hint="Verify this is intentional before exporting.",
        ))
        return
    if actual.lower() != expected.lower():
        report.add(_issue(
            "blocking",
            "character.export.supermodel_mismatch",
            (
                f"Generated character supermodel '{actual}' does not match the "
                f"native base supermodel '{expected}'."
            ),
            fix_hint="Preserve the selected base model's supermodel unless you are deliberately changing animation inheritance.",
            details={"expected": expected, "actual": actual},
        ))
    elif actual != expected:
        report.add(_issue(
            "blocking",
            "character.export.supermodel_case_changed",
            (
                f"Generated character supermodel casing changed from '{expected}' "
                f"to '{actual}'."
            ),
            fix_hint=(
                "Restore the exact supermodel casing from the selected native "
                "base before export. KOTOR supermodel case behavior is still "
                "Ghidra-pending, so Character Builder preserves the native value."
            ),
            details={
                "expected": expected,
                "actual": actual,
                "evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
                "pending_ghidra": "supermodel name resolution and resref case behavior",
            },
        ))


def _validate_native_dag(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    current_nodes = list(_iter_nodes(model))
    current_paths = {
        normalize_model_path_to_native_snapshot(snapshot, model, _node_path(node)): node
        for node in current_nodes
    }
    current_paths_lower = {
        tuple(
            part.lower()
            for part in normalize_model_path_to_native_snapshot(
                snapshot,
                model,
                _node_path(node),
            )
        ): node
        for node in current_nodes
    }

    for native_node in snapshot.nodes:
        if native_node.export_role not in _STRUCTURAL_ROLES:
            continue
        expected_path = tuple(native_node.full_path)
        found = current_paths.get(expected_path)
        if found is not None:
            continue
        lower_match = current_paths_lower.get(tuple(part.lower() for part in expected_path))
        if lower_match is not None:
            report.add(_issue(
                "blocking",
                "character.export.node_case_changed",
                (
                    f"Native node '{native_node.name}' is present with changed "
                    "casing or parent-path casing."
                ),
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Restore exact KOTOR node casing before export.",
                details={
                    "expected_path": list(expected_path),
                    "actual_path": list(_node_path(lower_match)),
                    "role": native_node.export_role,
                    **_native_socket_evidence_details(snapshot, native_node),
                },
            ))
            continue
        if opts.strict_parent_paths:
            exact_name_match = _find_node_exact_name(current_nodes, native_node.name)
            if exact_name_match is not None:
                report.add(_issue(
                    "blocking",
                    "character.export.node_path_changed",
                    (
                        f"Native {native_node.export_role} node '{native_node.name}' "
                        "is present but no longer lives at its original parent path."
                    ),
                    navigation=ValidationNavigationTarget(node_name=native_node.name),
                    fix_hint=(
                        "Restore the selected native skeleton hierarchy before export; "
                        "KOTOR animation inheritance depends on exact node paths."
                    ),
                    details={
                        "expected_path": list(expected_path),
                        "actual_path": list(_node_path(exact_name_match)),
                        "role": native_node.export_role,
                        **_native_socket_evidence_details(snapshot, native_node),
                    },
                ))
                continue
            report.add(_issue(
                "blocking",
                "character.export.node_path_missing",
                (
                    f"Native {native_node.export_role} node '{native_node.name}' "
                    "is missing from its original parent path."
                ),
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Rebuild from the selected native skeleton or restore the node parent path.",
                details={
                    "expected_path": list(expected_path),
                    "role": native_node.export_role,
                    **_native_socket_evidence_details(snapshot, native_node),
                },
            ))
        elif _find_node_exact_name(current_nodes, native_node.name) is None:
            report.add(_issue(
                "blocking",
                "character.export.node_missing",
                f"Native {native_node.export_role} node '{native_node.name}' is missing.",
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Restore the native node before export.",
                details={
                    "role": native_node.export_role,
                    **_native_socket_evidence_details(snapshot, native_node),
                },
            ))


def _validate_socket_categories(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_required_sockets:
        return
    current_nodes = list(_iter_nodes(model))
    present_model_paths = {
        normalize_model_path_to_native_snapshot(snapshot, model, _node_path(node))
        for node in current_nodes
    }
    present_socket_paths = {
        tuple(node.full_path)
        for node in snapshot.nodes
        if node.socket_category and tuple(node.full_path) in present_model_paths
    }
    present_categories = {
        node.socket_category
        for node in snapshot.nodes
        if node.socket_category and tuple(node.full_path) in present_socket_paths
    }
    native_categories = {
        node.socket_category
        for node in snapshot.nodes
        if node.socket_category
    }
    for category in opts.required_socket_categories:
        missing_nodes = tuple(
            node for node in snapshot.nodes
            if node.socket_category == category and tuple(node.full_path) not in present_socket_paths
        )
        if missing_nodes:
            category_evidence = _socket_category_evidence_details(
                snapshot,
                category,
                nodes=missing_nodes,
            )
            report.add(_issue(
                "blocking",
                "character.export.required_socket_missing",
                f"Required KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Restore the native attachment hook before export.",
                details={"category": category, **category_evidence},
            ))
    for category in opts.recommended_socket_categories:
        if category not in native_categories:
            continue
        if category not in present_categories:
            category_evidence = _socket_category_evidence_details(snapshot, category)
            report.add(_issue(
                "warning",
                "character.export.recommended_socket_missing",
                f"Recommended KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Preview equipment, weapons, and cutscene hooks before treating this model as game-ready.",
                details={"category": category, **category_evidence},
            ))


def _validate_no_non_native_skeleton_nodes(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_no_non_native_skeleton_nodes:
        return

    native_paths = {tuple(node.full_path) for node in snapshot.nodes}
    native_names = set(snapshot.node_names())
    for node in _iter_nodes(model):
        actual_path = _node_path(node)
        path = normalize_model_path_to_native_snapshot(
            snapshot,
            model,
            actual_path,
        )
        if path in native_paths:
            continue
        name = str(getattr(node, "name", "") or "")
        if name in native_names:
            # The exact-name/path mismatch is reported by _validate_native_dag.
            continue
        if _is_exportable_mesh_payload(node):
            continue
        report.add(_issue(
            "blocking",
            "character.export.non_native_skeleton_node",
            (
                f"Non-native node '{name or '<unnamed>'}' remains in the final "
                "Character Builder DAG."
            ),
            navigation=ValidationNavigationTarget(node_name=name),
            fix_hint=(
                "Remove imported armature/helper nodes before export. Only the "
                "selected KOTOR base skeleton may own the final DAG; imported "
                "content must be mesh/skin payload."
            ),
            details={
                "node_name": name,
                "actual_path": list(actual_path),
                "native_snapshot_model": snapshot.model_name,
                "native_snapshot_game": snapshot.game,
                "allowed_non_native_role": "mesh_or_skin_payload",
                "engine_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
            },
        ))


def _is_exportable_mesh_payload(node: Any) -> bool:
    vertices = list(getattr(node, "vertices", []) or [])
    faces = list(getattr(node, "faces", []) or [])
    return bool(vertices or faces)


def _socket_category_evidence_details(
    snapshot: NativeSkeletonSnapshot,
    category: str,
    *,
    nodes: tuple[NativeNodeSnapshot, ...] | None = None,
) -> dict[str, Any]:
    selected_nodes = nodes or tuple(
        node for node in snapshot.nodes
        if node.socket_category == category
    )
    expected_nodes = tuple(
        node.name for node in selected_nodes
    )
    return {
        "expected_native_socket_nodes": list(expected_nodes),
        **_socket_engine_evidence_details(snapshot.game, expected_nodes),
    }


def _native_socket_evidence_details(
    snapshot: NativeSkeletonSnapshot,
    node: NativeNodeSnapshot,
) -> dict[str, Any]:
    if not node.socket_category:
        return {}
    return {
        "socket_category": node.socket_category,
        **_socket_engine_evidence_details(snapshot.game, (node.name,)),
    }


def _socket_engine_evidence_details(game: str, names: tuple[str, ...]) -> dict[str, Any]:
    refs = _engine_string_refs_for_names(game, names)
    engine_verified = tuple(
        str(entry.get("string", "") or "")
        for entry in refs
        if str(entry.get("string", "") or "")
    )
    pending = tuple(name for name in names if name not in set(engine_verified))
    if engine_verified and pending:
        tier = "mixed_engine_string_refs_and_fixture_only"
    elif engine_verified:
        tier = "engine_string_ref_verified"
    elif names:
        tier = "native_fixture_only_pending_engine_string_ref"
    else:
        tier = "no_native_socket_fixture_nodes"
    return {
        "engine_string_evidence_status": KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS,
        "engine_string_refs": refs,
        "engine_verified_socket_nodes": list(engine_verified),
        "pending_engine_string_ref_nodes": list(pending),
        "engine_evidence_tier": tier,
        "native_fixture_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
        "findings_doc": CHARACTER_EXPORT_EVIDENCE["findings_doc"],
    }


def _engine_string_refs_for_names(game: str, names: tuple[str, ...]) -> list[dict[str, object]]:
    game_key = str(game or "").strip().lower()
    wanted = {str(name or "") for name in names}
    refs: list[dict[str, object]] = []
    for entry in ENGINE_VERIFIED_SOCKET_STRING_REFS:
        if str(entry.get("game", "")).lower() != game_key:
            continue
        if str(entry.get("string", "")) not in wanted:
            continue
        refs.append({
            "string": str(entry.get("string", "")),
            "string_address": str(entry.get("string_address", "")),
            "representative_refs": list(entry.get("representative_refs", ()) or ()),
        })
    return refs


def _validate_skin_payload(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    skin_nodes = [
        node for node in _iter_nodes(model)
        if bool(getattr(node, "is_skin", False))
    ]
    if not skin_nodes:
        report.add(_issue(
            "blocking",
            "character.export.no_skin_payload",
            "Character export requires at least one skinned mesh payload.",
            fix_hint="Import a render mesh and bind it to the selected KOTOR skeleton before export.",
        ))
        return

    for node in skin_nodes:
        name = str(getattr(node, "name", "") or "")
        vertices = list(getattr(node, "vertices", []) or [])
        faces = list(getattr(node, "faces", []) or [])
        bone_map_full = list(getattr(node, "bone_map", []) or [])
        # T2518: the MDL loader materializes the engine's fixed 16-slot bonemap
        # with blank trailing padding, while builder-shaped live models carry
        # exact-count arrays.  Strip TRAILING blanks before the structural
        # checks so reload verification of a <16-bone skin node is not
        # structurally guaranteed to fail; blanks BEFORE a real name remain
        # hard errors (checked below over the trimmed list).
        bone_map = list(bone_map_full)
        while bone_map and not str(bone_map[-1] or "").strip():
            bone_map.pop()
        qbone_list = list(getattr(node, "qbone_list", []) or [])
        tbone_list = list(getattr(node, "tbone_list", []) or [])
        skin_data = list(getattr(node, "skin_data", []) or [])
        # Loader-padded qbone/tbone arrays (full 16) are as valid as
        # exact-count ones; both lengths are accepted by the checks below.
        # T2526: the on-disk arrays are NODE-indexed (one entry per model
        # node, non-palette slots filled with sentinel values), so a model
        # reloaded from binary MDL legitimately carries node-count-length
        # bind arrays.  Accept that length too.
        _valid_bind_lengths = {len(bone_map), len(bone_map_full)}
        try:
            _model_node_count = len(list(model.all_nodes()))
        except Exception:
            _model_node_count = 0
        if _model_node_count:
            _valid_bind_lengths.add(_model_node_count)

        if not vertices or not faces:
            report.add(_issue(
                "blocking",
                "character.export.empty_skin_geometry",
                f"Skin mesh '{name}' has no exportable geometry.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Verify the imported mesh payload before export.",
            ))
        if vertices and faces:
            _validate_skin_geometry_values(node, vertices, faces, report)
            _validate_skin_material_evidence(node, vertices, faces, report)
        if not bone_map:
            report.add(_issue(
                "blocking",
                "character.export.empty_bonemap",
                f"Skin mesh '{name}' has no bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Bind the mesh to the KOTOR skeleton before export.",
            ))
        if skin_data and len(skin_data) != len(vertices):
            report.add(_issue(
                "blocking",
                "character.export.skin_row_count_mismatch",
                (
                    f"Skin mesh '{name}' has {len(skin_data)} skin rows for "
                    f"{len(vertices)} vertices."
                ),
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export.",
            ))
        elif not skin_data:
            report.add(_issue(
                "blocking",
                "character.export.no_skin_rows",
                f"Skin mesh '{name}' has no per-vertex skin weights.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Bind the mesh to the KOTOR skeleton before export.",
            ))
        if bone_map and len(qbone_list) not in _valid_bind_lengths:
            report.add(_issue(
                "blocking",
                "character.export.qbone_mismatch",
                f"Skin mesh '{name}' qbone list does not match the bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={"bone_map": len(bone_map), "qbone_list": len(qbone_list)},
            ))
        if bone_map and qbone_list:
            _validate_bind_transform_rows(
                node,
                qbone_list,
                kind="qbone",
                expected_components=4,
                report=report,
            )
        if bone_map and len(tbone_list) not in _valid_bind_lengths:
            report.add(_issue(
                "blocking",
                "character.export.tbone_mismatch",
                f"Skin mesh '{name}' tbone list does not match the bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={"bone_map": len(bone_map), "tbone_list": len(tbone_list)},
            ))
        if bone_map and tbone_list:
            _validate_bind_transform_rows(
                node,
                tbone_list,
                kind="tbone",
                expected_components=3,
                report=report,
            )
        if bone_map:
            _validate_bone_map_targets(node, bone_map, model, native_snapshot, opts, report)
        _validate_skin_rows(node, bone_map, report)


def _validate_skin_material_evidence(
    node: Any,
    vertices: list[Any],
    faces: list[Any],
    report: ValidationReport,
) -> None:
    """Warn when a payload can export structurally but lacks texture/UV proof."""

    name = str(getattr(node, "name", "") or "")
    uvs = list(getattr(node, "uvs", []) or [])
    face_uvs = list(getattr(node, "face_uvs", []) or [])
    texture_names = _payload_texture_names(node)
    if not texture_names:
        report.add(_issue(
            "warning",
            "character.export.payload_texture_missing",
            f"Skin mesh '{name}' has no texture or material name recorded.",
            navigation=ValidationNavigationTarget(node_name=name),
            fix_hint=(
                "Assign a KOTOR-safe texture name before treating this "
                "character as game-ready."
            ),
            details={
                "node_name": name,
                "vertex_count": len(vertices),
                "face_count": len(faces),
                "uv_count": len(uvs),
            },
        ))
    if not uvs:
        report.add(_issue(
            "warning",
            "character.export.payload_uvs_missing",
            f"Skin mesh '{name}' has no UV coordinates.",
            navigation=ValidationNavigationTarget(node_name=name),
            fix_hint=(
                "Import or author UVs for the custom payload before treating "
                "the character as game-ready."
            ),
            details={
                "node_name": name,
                "vertex_count": len(vertices),
                "face_count": len(faces),
                "texture_names": texture_names,
            },
        ))
        return

    if face_uvs:
        if len(face_uvs) != len(faces):
            report.add(_issue(
                "warning",
                "character.export.payload_face_uv_count_mismatch",
                f"Skin mesh '{name}' has face UV rows that do not match its faces.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild face UV indices before treating the payload as game-ready.",
                details={
                    "node_name": name,
                    "face_count": len(faces),
                    "face_uv_count": len(face_uvs),
                    "uv_count": len(uvs),
                },
            ))
        for face_index, uv_face in enumerate(face_uvs):
            try:
                indices = [int(value) for value in list(uv_face)[:3]]
            except Exception:
                report.add(_issue(
                    "warning",
                    "character.export.payload_face_uv_malformed",
                    f"Skin mesh '{name}' has malformed face UV indices.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild face UV indices before treating the payload as game-ready.",
                    details={"node_name": name, "face_index": face_index},
                ))
                continue
            bad_indices = [index for index in indices if index < 0 or index >= len(uvs)]
            if bad_indices:
                report.add(_issue(
                    "warning",
                    "character.export.payload_face_uv_index_out_of_range",
                    f"Skin mesh '{name}' has a face UV index outside its UV table.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild face UV indices before treating the payload as game-ready.",
                    details={
                        "node_name": name,
                        "face_index": face_index,
                        "bad_indices": bad_indices,
                        "uv_count": len(uvs),
                    },
                ))
    elif len(uvs) != len(vertices):
        report.add(_issue(
            "warning",
            "character.export.payload_uv_count_mismatch",
            f"Skin mesh '{name}' UV count does not match its vertex count.",
            navigation=ValidationNavigationTarget(node_name=name),
            fix_hint=(
                "Rebuild payload UVs or face UV indices before treating the "
                "character as game-ready."
            ),
            details={
                "node_name": name,
                "vertex_count": len(vertices),
                "uv_count": len(uvs),
                "face_uv_count": 0,
            },
        ))


def _payload_texture_names(node: Any) -> list[str]:
    names: list[str] = []
    for value in (
        getattr(node, "texture_clean", ""),
        getattr(node, "texture", ""),
        getattr(node, "bitmap", ""),
    ):
        text = str(value or "").strip()
        if text and text.upper() != "NULL":
            names.append(text)
    for value in list(getattr(node, "texture_names", []) or []):
        text = str(value or "").strip()
        if text and text.upper() != "NULL":
            names.append(text)
    result: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def _validate_skin_geometry_values(
    node: Any,
    vertices: list[Any],
    faces: list[Any],
    report: ValidationReport,
) -> None:
    name = str(getattr(node, "name", "") or "")
    for vertex_index, vertex in enumerate(vertices):
        try:
            components = _numeric_components(vertex)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < 3:
            report.add(_issue(
                "blocking",
                "character.export.vertex_malformed",
                f"Skin mesh '{name}' has a vertex without three coordinates.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild the imported mesh payload before export.",
                details={"vertex_index": vertex_index, "component_count": len(components)},
            ))
            continue
        if not _all_finite(components[:3]):
            report.add(_issue(
                "blocking",
                "character.export.vertex_nonfinite",
                f"Skin mesh '{name}' has a vertex with non-finite coordinates.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild or clean the imported mesh payload before export.",
                details={"vertex_index": vertex_index, "coordinates": [str(value) for value in components[:3]]},
            ))

    normals = list(getattr(node, "normals", []) or [])
    for normal_index, normal in enumerate(normals):
        try:
            components = _numeric_components(normal)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < 3 or not _all_finite(components[:3]):
            report.add(_issue(
                "blocking",
                "character.export.normal_nonfinite",
                f"Skin mesh '{name}' has an invalid normal vector.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh normals before export.",
                details={"normal_index": normal_index, "components": [str(value) for value in components]},
            ))

    for face_index, face in enumerate(faces):
        try:
            face_components = _numeric_components(face)
        except (TypeError, ValueError, OverflowError):
            face_components = []
        if len(face_components) < 3:
            report.add(_issue(
                "blocking",
                "character.export.face_malformed",
                f"Skin mesh '{name}' has a face without three vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Triangulate or rebuild the imported mesh payload before export.",
                details={"face_index": face_index, "index_count": len(face_components)},
            ))
            continue
        first_three = face_components[:3]
        nonfinite_indices = [str(value) for value in first_three if not math.isfinite(value)]
        if nonfinite_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_nonfinite",
                f"Skin mesh '{name}' has a face with non-finite vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export.",
                details={"face_index": face_index, "indices": nonfinite_indices},
            ))
            continue
        noninteger_indices = [value for value in first_three if not float(value).is_integer()]
        if noninteger_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_noninteger",
                f"Skin mesh '{name}' has a face with non-integer vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export; MDL face indices must reference exact vertices.",
                details={
                    "face_index": face_index,
                    "indices": [str(value) for value in noninteger_indices],
                },
            ))
            continue
        indices = [int(value) for value in first_three]
        bad_indices = [index for index in indices[:3] if index < 0 or index >= len(vertices)]
        if bad_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_out_of_range",
                f"Skin mesh '{name}' has a face referencing a missing vertex.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export.",
                details={
                    "face_index": face_index,
                    "bad_indices": bad_indices,
                    "vertex_count": len(vertices),
                },
            ))


def _validate_bind_transform_rows(
    node: Any,
    rows: list[Any],
    *,
    kind: str,
    expected_components: int,
    report: ValidationReport,
) -> None:
    name = str(getattr(node, "name", "") or "")
    for row_index, row in enumerate(rows):
        try:
            components = _numeric_components(row)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < expected_components or not _all_finite(components[:expected_components]):
            report.add(_issue(
                "blocking",
                f"character.export.{kind}_nonfinite",
                f"Skin mesh '{name}' has invalid {kind} bind-transform metadata.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={
                    "row_index": row_index,
                    "component_count": len(components),
                    "expected_components": expected_components,
                    "components": [str(value) for value in components],
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))


def _validate_bone_map_targets(
    node: Any,
    bone_map: list[Any],
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    """Require skin bindings to target the selected native KOTOR DAG.

    See ``CHARACTER_EXPORT_EVIDENCE`` and ``docs/ghidra_findings.md`` for the
    current evidence tier: native fixture/snapshot contracts are verified,
    while final MDL loader skin-reference semantics are still pending.
    """
    mesh_name = str(getattr(node, "name", "") or "")
    current_nodes = list(_iter_nodes(model))
    current_names = {str(getattr(current, "name", "") or "") for current in current_nodes}
    current_lower = {name.lower(): name for name in current_names}
    native_names = set(native_snapshot.node_names()) if native_snapshot is not None else set()
    native_lower = {name.lower(): name for name in native_names}

    for bone_map_index, bone_name_raw in enumerate(bone_map):
        bone_name = str(bone_name_raw or "").strip()
        if not bone_name:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_empty_target",
                f"Skin mesh '{mesh_name}' has an empty bone-map target.",
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint="Rebuild the skin bone map from the selected native KOTOR skeleton.",
                details={"bone_map_index": bone_map_index},
            ))
            continue

        if bone_name not in current_names:
            lower_match = current_lower.get(bone_name.lower())
            if lower_match is not None:
                report.add(_issue(
                    "blocking",
                    "character.export.bonemap_target_case_changed",
                    (
                        f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                        f"does not match native node casing '{lower_match}'."
                    ),
                    navigation=ValidationNavigationTarget(node_name=mesh_name),
                    fix_hint="Restore exact KOTOR node casing in the skin bone map.",
                    details={
                        "bone_map_index": bone_map_index,
                        "bone_name": bone_name,
                        "actual_node_name": lower_match,
                    },
                ))
            else:
                report.add(_issue(
                    "blocking",
                    "character.export.bonemap_target_missing",
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' does not exist in the export DAG.",
                    navigation=ValidationNavigationTarget(node_name=mesh_name),
                    fix_hint="Bind skin weights only to nodes that exist in the selected native KOTOR skeleton.",
                    details={
                        "bone_map_index": bone_map_index,
                        "bone_name": bone_name,
                    },
                ))
            continue

        if not opts.require_native_bone_map_targets or native_snapshot is None:
            continue

        if bone_name in native_names:
            continue
        native_case_match = native_lower.get(bone_name.lower())
        if native_case_match is not None:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_native_target_case_changed",
                (
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                    f"does not match native snapshot casing '{native_case_match}'."
                ),
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint="Use exact native KOTOR node casing in the skin bone map.",
                details={
                    "bone_map_index": bone_map_index,
                    "bone_name": bone_name,
                    "expected_native_name": native_case_match,
                    "native_snapshot_model": native_snapshot.model_name,
                },
            ))
        else:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_target_not_native",
                (
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                    "is not part of the selected native KOTOR skeleton snapshot."
                ),
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint=(
                    "Remove imported/temporary skeleton nodes from the skin bone map "
                    "and bind the mesh to the native KOTOR template nodes."
                ),
                details={
                    "bone_map_index": bone_map_index,
                    "bone_name": bone_name,
                    "native_snapshot_model": native_snapshot.model_name,
                    "engine_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
                },
            ))


def _numeric_components(value: Any) -> list[float]:
    if isinstance(value, (str, bytes)):
        raise TypeError("string values are not numeric components")
    if isinstance(value, (int, float)):
        return [float(value)]
    components: list[float] = []
    if isinstance(value, dict):
        iterable = value.values()
    elif isinstance(value, (list, tuple)):
        iterable = value
    else:
        attrs = [getattr(value, attr) for attr in ("x", "y", "z", "w") if hasattr(value, attr)]
        if attrs:
            iterable = attrs
        else:
            try:
                iterable = iter(value)
            except TypeError as exc:
                raise TypeError("value is not a numeric component sequence") from exc

    for item in iterable:
        if isinstance(item, (list, tuple, dict)):
            components.extend(_numeric_components(item))
        elif isinstance(item, (str, bytes)):
            raise TypeError("string values are not numeric components")
        else:
            components.append(float(item))
    return components


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def _validate_skin_rows(node: Any, bone_map: list[Any], report: ValidationReport) -> None:
    name = str(getattr(node, "name", "") or "")
    for row_index, row in enumerate(list(getattr(node, "skin_data", []) or [])):
        influences = list(getattr(row, "influences", []) or [])
        if not influences:
            report.add(_issue(
                "blocking",
                "character.export.vertex_unweighted",
                f"Skin mesh '{name}' has an unweighted vertex.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export.",
                details={"vertex_index": row_index},
            ))
            continue
        if len(influences) > KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX:
            report.add(_issue(
                "blocking",
                "character.export.vertex_too_many_influences",
                (
                    f"Skin mesh '{name}' has a vertex with {len(influences)} "
                    f"influences; the KOTOR MDL writer stores at most "
                    f"{KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX}."
                ),
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Prune and normalize skin weights before export.",
                details={
                    "vertex_index": row_index,
                    "influence_count": len(influences),
                    "max_influences": KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX,
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))
        total = 0.0
        has_malformed_weight = False
        for influence in influences:
            try:
                bone_index = int(getattr(influence, "bone_index", -1))
            except (TypeError, ValueError, OverflowError):
                bone_index = -1
            try:
                weight = float(getattr(influence, "weight", 0.0))
            except (TypeError, ValueError, OverflowError):
                weight = math.nan
            if not math.isfinite(weight):
                has_malformed_weight = True
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_weight_nonfinite",
                    f"Skin mesh '{name}' has a non-finite vertex weight.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export; MDL/MDX skin weights must be finite numbers.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "weight": str(weight),
                        "evidence_status": "writer_format_contract_verified_ghidra_pending",
                    },
                ))
                continue
            if weight < 0.0:
                has_malformed_weight = True
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_weight_negative",
                    f"Skin mesh '{name}' has a negative vertex weight.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export; KOTOR skin influences must not contain negative weights.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "weight": weight,
                        "evidence_status": "writer_format_contract_verified_ghidra_pending",
                    },
                ))
            total += weight
            if bone_index < 0 or bone_index >= len(bone_map):
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_bone_index_out_of_range",
                    f"Skin mesh '{name}' has a vertex influence outside its bone map.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "bone_map_size": len(bone_map),
                    },
                ))
        if not has_malformed_weight and total <= 0.0:
            report.add(_issue(
                "blocking",
                "character.export.vertex_weight_zero_sum",
                f"Skin mesh '{name}' has a vertex whose weights sum to zero.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export; every vertex needs a positive normalized weight sum.",
                details={
                    "vertex_index": row_index,
                    "weight_sum": total,
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))
        elif (
            not has_malformed_weight
            and abs(total - 1.0) > KOTOR_SKIN_WEIGHT_SUM_TOLERANCE
        ):
            report.add(_issue(
                "warning",
                "character.export.vertex_weight_sum",
                f"Skin mesh '{name}' has a vertex whose weights do not sum to 1.0.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Normalize skin weights before final export.",
                details={
                    "vertex_index": row_index,
                    "weight_sum": total,
                    "tolerance": KOTOR_SKIN_WEIGHT_SUM_TOLERANCE,
                    "pending_ghidra": "engine_weight_normalization_behavior",
                },
            ))


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    navigation: ValidationNavigationTarget | None = None,
    fix_hint: str | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    payload = dict(details or {})
    payload.setdefault("engine_evidence", CHARACTER_EXPORT_EVIDENCE)
    return ValidationIssue(
        severity=ValidationSeverity(severity),
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        navigation=navigation,
        fix_hint=fix_hint,
        details=payload,
    )


def _iter_nodes(model: Any) -> list[Any]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        return list(all_nodes())
    root = getattr(model, "root_node", None)
    if root is None:
        return []
    result: list[Any] = []
    stack = [root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)
        result.append(node)
        stack.extend(reversed(list(getattr(node, "children", []) or [])))
    return result


def _node_path(node: Any) -> tuple[str, ...]:
    names = [str(getattr(node, "name", "") or "")]
    parent = getattr(node, "parent", None)
    visited: set[int] = set()
    while parent is not None:
        parent_id = id(parent)
        if parent_id in visited:
            break
        visited.add(parent_id)
        names.append(str(getattr(parent, "name", "") or ""))
        parent = getattr(parent, "parent", None)
    names.reverse()
    return tuple(names)


def _find_node_exact_path(nodes: list[Any], path: tuple[str, ...]) -> Any | None:
    for node in nodes:
        if _node_path(node) == path:
            return node
    return None


def _normalize_kotor_game(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = raw.lower().replace("_", " ").replace("-", " ")
    compact = " ".join(compact.split())
    if (
        compact in {"2", "k2", "tsl", "kotor2", "kotor 2", "kotor ii"}
        or "gameversion.k2" in compact
        or "kotor ii" in compact
        or "kotor 2" in compact
        or "the sith lords" in compact
        or "swkotor2" in compact
    ):
        return "K2"
    if (
        compact in {"1", "k1", "kotor1", "kotor 1", "kotor i"}
        or "gameversion.k1" in compact
        or "kotor i" in compact
        or "kotor 1" in compact
        or compact == "knights of the old republic"
        or "swkotor" in compact
    ):
        return "K1"
    return raw.upper()


def _casefold(value: Any) -> str:
    return str(value or "").strip().casefold()


def _find_node_exact_name(nodes: list[Any], name: str) -> Any | None:
    for node in nodes:
        if str(getattr(node, "name", "") or "") == name:
            return node
    return None
