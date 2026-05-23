"""Modder-facing readiness summaries for the Retarget Workbench."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.retargeting.retarget_modes import RetargetMode, coerce_retarget_mode, get_retarget_mode_spec
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
    coerce_kotor_output_name_mode,
)


@dataclass(frozen=True)
class RetargetWorkbenchInputStatus:
    """One user-visible input row in the Retarget Workbench readiness model."""

    name: str
    present: bool
    value_label: str | None = None
    fix_hint: str | None = None


@dataclass(frozen=True)
class RetargetWorkbenchReadiness:
    """Modder-facing status snapshot for the Retarget Workbench."""

    mode: RetargetMode
    mode_label: str
    implemented: bool
    source_summary: str
    target_summary: str
    output_summary: str
    runtime_summary: str
    inputs: tuple[RetargetWorkbenchInputStatus, ...]
    can_preview: bool
    can_export: bool
    preview_status: str
    export_status: str
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()


def build_retarget_workbench_readiness(state: Any) -> RetargetWorkbenchReadiness:
    """Build a pure readiness snapshot from Retarget Workbench state."""

    mode = coerce_retarget_mode(getattr(state, "mode", RetargetMode.UNREAL_TO_KOTOR))
    spec = get_retarget_mode_spec(mode)
    if mode == RetargetMode.UNREAL_TO_KOTOR:
        inputs, source, target, output, runtime = _unreal_to_kotor_status(state)
    elif mode == RetargetMode.KOTOR_TO_KOTOR:
        inputs, source, target, output, runtime = _kotor_to_kotor_status(state)
    else:
        inputs, source, target, output, runtime = _kotor_to_unreal_status(state)

    missing = tuple(
        f"Missing: {entry.name}. {entry.fix_hint or ''}".strip()
        for entry in inputs
        if not entry.present
    )
    can_preview = bool(spec.implemented and spec.supports_preview and not missing)
    preview = getattr(state, "last_preview_result", None)
    audit = getattr(preview, "preview_audit", None)
    audit_passed = bool(audit is not None and getattr(audit, "passed", False))
    invalidation_reason = str(getattr(state, "last_preview_invalidated_reason", "") or "").strip()
    can_export = bool(
        spec.implemented
        and spec.supports_export
        and preview is not None
        and audit_passed
        and not invalidation_reason
    )

    if not spec.implemented:
        preview_status = "Not implemented yet."
        export_status = "Not implemented yet."
    elif can_preview:
        preview_status = "Ready."
        if can_export:
            export_status = "Ready."
        elif invalidation_reason:
            export_status = f"Stale preview. Run Preview Retarget again because {invalidation_reason}."
        elif preview is None:
            export_status = "Preview required before export."
        elif not audit_passed:
            export_status = "Preview audit did not pass."
        else:
            export_status = "Preview required before export."
    else:
        preview_status = "Not ready."
        export_status = (
            f"Stale preview. Run Preview Retarget again because {invalidation_reason}."
            if invalidation_reason
            else "Preview required before export."
        )

    warnings: list[str] = []
    if _output_name_mode(getattr(state, "output_naming", None)) == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        warnings.append("Custom animation patch output is not vanilla-slot playable.")

    return RetargetWorkbenchReadiness(
        mode=mode,
        mode_label=spec.label,
        implemented=bool(spec.implemented),
        source_summary=source,
        target_summary=target,
        output_summary=output,
        runtime_summary=runtime,
        inputs=tuple(inputs),
        can_preview=can_preview,
        can_export=can_export,
        preview_status=preview_status,
        export_status=export_status,
        warnings=tuple(warnings),
        blocking_messages=missing,
    )


def _unreal_to_kotor_status(state: Any):
    source_clip = getattr(state, "source_clip", None)
    target_model = getattr(state, "target_model", None)
    profile = getattr(state, "retarget_profile", None)
    output_name = _target_output_name(state)
    inputs = [
        RetargetWorkbenchInputStatus(
            "Source UE/FBX clip",
            source_clip is not None,
            _clip_label(source_clip),
            "Load a UE/FBX source animation clip.",
        ),
        RetargetWorkbenchInputStatus(
            "Target KOTOR model",
            target_model is not None,
            _model_label(target_model),
            "Load or set the KOTOR/Aurora target model.",
        ),
        RetargetWorkbenchInputStatus(
            "Retarget profile",
            profile is not None,
            _profile_label(profile),
            "Load a retarget profile.",
        ),
        RetargetWorkbenchInputStatus(
            "Target output animation",
            bool(output_name),
            output_name,
            "Choose a vanilla slot or custom patch animation name.",
        ),
    ]
    return (
        inputs,
        f"UE/FBX clip {_clip_label(source_clip)}",
        f"KOTOR model {_model_label(target_model)}",
        _output_summary(state),
        _runtime_summary(state),
    )


def _kotor_to_kotor_status(state: Any):
    source_model = getattr(state, "source_kotor_model", None)
    source_slot = str(getattr(state, "source_kotor_animation_slot", "") or "").strip()
    target_model = getattr(state, "target_model", None)
    profile = getattr(state, "retarget_profile", None)
    output_name = _target_output_name(state)
    inputs = [
        RetargetWorkbenchInputStatus(
            "Source KOTOR model",
            source_model is not None,
            _model_label(source_model),
            "Choose the KOTOR/Aurora model to sample from.",
        ),
        RetargetWorkbenchInputStatus(
            "Source KOTOR animation",
            bool(source_slot),
            source_slot or None,
            "Choose an animation from the source model or inherited supermodel chain.",
        ),
        RetargetWorkbenchInputStatus(
            "Target KOTOR model",
            target_model is not None,
            _model_label(target_model),
            "Choose the target KOTOR/Aurora model.",
        ),
        RetargetWorkbenchInputStatus(
            "Retarget profile",
            profile is not None,
            _profile_label(profile),
            "Load a retarget profile for this source/target pair.",
        ),
        RetargetWorkbenchInputStatus(
            "Target output animation",
            bool(output_name),
            output_name,
            "Choose the animation name to attach to the target.",
        ),
    ]
    source = f"KOTOR model {_model_label(source_model)} / source animation {source_slot or '(not selected)'}"
    return inputs, source, f"KOTOR model {_model_label(target_model)}", _output_summary(state), _runtime_summary(state)


def _kotor_to_unreal_status(state: Any):
    source_model = getattr(state, "source_kotor_model", None)
    source_slot = str(getattr(state, "source_kotor_animation_slot", "") or "").strip()
    skeleton = getattr(state, "target_unreal_skeleton", None)
    profile = getattr(state, "target_unreal_profile", None)
    naming = getattr(state, "output_naming", None)
    clip_name = str(getattr(naming, "unreal_clip_name", "") or "").strip()
    inputs = [
        RetargetWorkbenchInputStatus("Source KOTOR model", source_model is not None, _model_label(source_model)),
        RetargetWorkbenchInputStatus("Source KOTOR animation", bool(source_slot), source_slot or None),
        RetargetWorkbenchInputStatus("Target Unreal skeleton", skeleton is not None, _object_label(skeleton)),
        RetargetWorkbenchInputStatus("Unreal export profile", profile is not None, _object_label(profile)),
        RetargetWorkbenchInputStatus("UE animation clip name", bool(clip_name), clip_name or None),
    ]
    return (
        inputs,
        f"KOTOR model {_model_label(source_model)} / source animation {source_slot or '(not selected)'}",
        f"Unreal skeleton {_object_label(skeleton)}",
        f"UE-compatible FBX animation clip {clip_name or '(not selected)'}",
        "KOTOR → Unreal export is pending implementation.",
    )


def _target_output_name(state: Any) -> str:
    naming = getattr(state, "output_naming", None)
    raw = ""
    if naming is not None:
        raw = (
            getattr(naming, "requested_kotor_animation_name", None)
            or getattr(naming, "canonical_kotor_animation_name", None)
            or getattr(naming, "unreal_clip_name", None)
            or ""
        )
    if not str(raw or "").strip():
        profile = getattr(state, "retarget_profile", None)
        raw = getattr(profile, "animation_slot", "") if profile is not None else ""
    return str(raw or "").strip()


def _output_name_mode(naming: RetargetOutputNaming | None) -> KotorOutputAnimationNameMode:
    if naming is None:
        return KotorOutputAnimationNameMode.VANILLA_SLOT
    return coerce_kotor_output_name_mode(getattr(naming, "kotor_name_mode", None))


def _output_summary(state: Any) -> str:
    name = _target_output_name(state) or "(not selected)"
    mode = _output_name_mode(getattr(state, "output_naming", None))
    label = "Custom animation patch" if mode == KotorOutputAnimationNameMode.CUSTOM_PATCH else "Vanilla slot override"
    return f"Target output animation {name} / Output type: {label}"


def _runtime_summary(state: Any) -> str:
    mode = _output_name_mode(getattr(state, "output_naming", None))
    if mode == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        return "Requires custom animation patch/runtime support."
    return "Vanilla KOTOR-compatible if the selected slot is called by the game."


def _clip_label(clip: Any) -> str:
    if clip is None:
        return "(not selected)"
    return str(getattr(clip, "clip_name", "") or getattr(clip, "name", "") or getattr(clip, "source_path", "") or clip)


def _model_label(model: Any) -> str:
    if model is None:
        return "(not selected)"
    return str(getattr(model, "name", "") or getattr(model, "resref", "") or model)


def _profile_label(profile: Any) -> str:
    if profile is None:
        return "(not selected)"
    return str(getattr(profile, "name", "") or getattr(profile, "animation_slot", "") or profile)


def _object_label(obj: Any) -> str:
    if obj is None:
        return "(not selected)"
    return str(getattr(obj, "name", "") or getattr(obj, "label", "") or obj)
