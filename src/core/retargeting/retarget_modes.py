"""Shared mode contracts for the GhostRigger Retarget Workbench."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetargetMode(str, Enum):
    """Supported Retarget Workbench mode identifiers."""

    KOTOR_TO_KOTOR = "kotor_to_kotor"
    KOTOR_TO_UNREAL = "kotor_to_unreal"
    UNREAL_TO_KOTOR = "unreal_to_kotor"


@dataclass(frozen=True)
class RetargetModeSpec:
    """Product contract for one retargeting direction."""

    mode: RetargetMode
    label: str
    description: str
    source_kind: str
    target_kind: str
    output_kind: str
    supports_preview: bool
    supports_export: bool
    implemented: bool
    required_inputs: tuple[str, ...]


_MODE_SPECS: dict[RetargetMode, RetargetModeSpec] = {
    RetargetMode.KOTOR_TO_KOTOR: RetargetModeSpec(
        mode=RetargetMode.KOTOR_TO_KOTOR,
        label="KOTOR → KOTOR",
        description=(
            "Sample a KOTOR/Aurora source animation through the evaluator and use "
            "the verified GhostRigger preview/export pipeline to attach it as a "
            "local target animation override."
        ),
        source_kind="kotor_aurora_model_animation_slot",
        target_kind="kotor_aurora_model",
        output_kind="kotor_mdl_mdx_animation_override",
        supports_preview=True,
        supports_export=True,
        implemented=True,
        required_inputs=(
            "source_kotor_model",
            "source_kotor_animation_slot",
            "target_model",
            "retarget_profile",
            "target_output_animation_name",
        ),
    ),
    RetargetMode.KOTOR_TO_UNREAL: RetargetModeSpec(
        mode=RetargetMode.KOTOR_TO_UNREAL,
        label="KOTOR → Unreal",
        description=(
            "Export a sampled KOTOR/Aurora animation slot toward an Unreal-compatible "
            "skeleton/FBX animation clip. KOTOR source animation sampler is available; "
            "pending next adapter: UE-compatible FBX animation export."
        ),
        source_kind="kotor_aurora_model_animation_slot",
        target_kind="unreal_skeleton",
        output_kind="unreal_fbx_animation_clip",
        supports_preview=False,
        supports_export=False,
        implemented=False,
        required_inputs=("source_kotor_model", "source_kotor_animation_slot", "target_unreal_skeleton", "target_unreal_profile"),
    ),
    RetargetMode.UNREAL_TO_KOTOR: RetargetModeSpec(
        mode=RetargetMode.UNREAL_TO_KOTOR,
        label="Unreal → KOTOR",
        description="Use the verified GhostRigger UE/FBX to KOTOR preview/export pipeline.",
        source_kind="ue_fbx_source_clip",
        target_kind="kotor_aurora_model",
        output_kind="kotor_mdl_mdx_animation_override",
        supports_preview=True,
        supports_export=True,
        implemented=True,
        required_inputs=("source_clip", "target_model", "retarget_profile"),
    ),
}


def coerce_retarget_mode(value: RetargetMode | str) -> RetargetMode:
    """Return a RetargetMode from enum, value, name, or label text."""

    if isinstance(value, RetargetMode):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Retarget mode is empty.")
    for mode, spec in _MODE_SPECS.items():
        if raw == mode.value or raw.upper() == mode.name or raw.lower() == spec.label.lower():
            return mode
    raise ValueError(f"Unknown retarget mode: {raw}")


def get_retarget_mode_spec(mode: RetargetMode | str) -> RetargetModeSpec:
    """Return the immutable mode contract for a retarget direction."""

    return _MODE_SPECS[coerce_retarget_mode(mode)]


def list_retarget_mode_specs() -> list[RetargetModeSpec]:
    """Return mode specs in the product-facing dropdown order."""

    return [
        _MODE_SPECS[RetargetMode.KOTOR_TO_KOTOR],
        _MODE_SPECS[RetargetMode.KOTOR_TO_UNREAL],
        _MODE_SPECS[RetargetMode.UNREAL_TO_KOTOR],
    ]
