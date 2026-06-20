"""Mode-aware output animation naming for Retarget Workbench exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.game.kotor_loader import get_valid_animation_slots, resolve_animation_slot

from .retarget_modes import RetargetMode, coerce_retarget_mode


class KotorOutputAnimationNameMode(str, Enum):
    """How a KOTOR-targeted retarget output should be named."""

    VANILLA_SLOT = "vanilla_slot"
    CUSTOM_PATCH = "custom_patch"


@dataclass(frozen=True)
class RetargetOutputNaming:
    """User-selected output animation naming policy."""

    kotor_name_mode: KotorOutputAnimationNameMode = KotorOutputAnimationNameMode.VANILLA_SLOT
    requested_kotor_animation_name: str | None = None
    canonical_kotor_animation_name: str | None = None
    unreal_clip_name: str | None = None
    display_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedRetargetOutputName:
    """Resolved AnimationBlock identity for a retarget output."""

    mode: KotorOutputAnimationNameMode
    requested_name: str
    animation_block_name: str
    display_label: str | None
    requires_custom_animation_patch: bool
    warnings: tuple[str, ...] = ()


class RetargetOutputNamingError(ValueError):
    """Raised when an output animation name cannot be used safely."""


def is_kotor_output_mode(mode: RetargetMode | str) -> bool:
    return coerce_retarget_mode(mode) in {
        RetargetMode.UNREAL_TO_KOTOR,
        RetargetMode.KOTOR_TO_KOTOR,
    }


def coerce_kotor_output_name_mode(value: KotorOutputAnimationNameMode | str | None) -> KotorOutputAnimationNameMode:
    if isinstance(value, KotorOutputAnimationNameMode):
        return value
    raw = str(value or KotorOutputAnimationNameMode.VANILLA_SLOT.value).strip().lower()
    aliases = {
        "vanilla": KotorOutputAnimationNameMode.VANILLA_SLOT,
        "vanilla_slot": KotorOutputAnimationNameMode.VANILLA_SLOT,
        "slot": KotorOutputAnimationNameMode.VANILLA_SLOT,
        "custom": KotorOutputAnimationNameMode.CUSTOM_PATCH,
        "custom_patch": KotorOutputAnimationNameMode.CUSTOM_PATCH,
        "patch": KotorOutputAnimationNameMode.CUSTOM_PATCH,
    }
    if raw not in aliases:
        raise RetargetOutputNamingError(f"Unknown KOTOR output animation name mode: {value}")
    return aliases[raw]


def validate_custom_kotor_animation_name(name: str) -> str:
    """Return a trimmed, case-preserved custom KOTOR animation name."""

    text = str(name or "").strip()
    if not text:
        raise RetargetOutputNamingError("Custom KOTOR animation name cannot be empty.")
    if text in {".", ".."}:
        raise RetargetOutputNamingError(f"Custom KOTOR animation name '{text}' is not safe for MDL export.")
    if len(text) > 64:
        raise RetargetOutputNamingError("Custom KOTOR animation names are limited to 64 characters.")
    forbidden = {
        "\x00": "NUL",
        "\n": "newline",
        "\r": "newline",
        "\t": "tab",
        "/": "slash",
        "\\": "backslash",
    }
    for token, label in forbidden.items():
        if token in text:
            raise RetargetOutputNamingError(
                f"Custom KOTOR animation name '{text}' is not safe for MDL export: contains {label}."
            )
    if any(ord(ch) < 32 for ch in text):
        raise RetargetOutputNamingError(
            f"Custom KOTOR animation name '{text}' is not safe for MDL export: contains a control character."
        )
    return text


def validate_unreal_clip_name(name: str | None) -> str:
    """Return a filesystem/asset-safe Unreal animation clip name.

    KOTOR -> Unreal output names are Unreal/FBX clip names, not Aurora
    animation slots. Preserve user-facing case, convert whitespace to
    underscores, and reject path/control characters before any export path is
    built.
    """

    text = str(name or "").strip()
    if not text:
        raise RetargetOutputNamingError("KOTOR -> Unreal output requires a UE animation clip name.")
    if len(text) > 128:
        raise RetargetOutputNamingError("UE animation clip names are limited to 128 characters.")
    forbidden = {
        "\x00": "NUL",
        "\n": "newline",
        "\r": "newline",
        "\t": "tab",
        "/": "slash",
        "\\": "backslash",
    }
    for token, label in forbidden.items():
        if token in text:
            raise RetargetOutputNamingError(
                f"UE animation clip name '{text}' is not safe for export: contains {label}."
            )
    if any(ord(ch) < 32 for ch in text):
        raise RetargetOutputNamingError(
            f"UE animation clip name '{text}' is not safe for export: contains a control character."
        )
    sanitized = _sanitize_unreal_clip_name(text)
    if not sanitized:
        raise RetargetOutputNamingError("KOTOR -> Unreal output requires a UE animation clip name.")
    return sanitized


def resolve_retarget_output_name(
    *,
    workbench_mode: RetargetMode | str,
    naming: RetargetOutputNaming,
    target_model=None,
    target_supermodel_chain=None,
    require_export_safe: bool = True,
) -> ResolvedRetargetOutputName:
    """Resolve the output AnimationBlock name for one workbench mode."""

    mode = coerce_retarget_mode(workbench_mode)
    if not is_kotor_output_mode(mode):
        clip_name = validate_unreal_clip_name(naming.unreal_clip_name or naming.requested_kotor_animation_name)
        return ResolvedRetargetOutputName(
            mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_name=clip_name,
            animation_block_name=clip_name,
            display_label=_optional_text(naming.display_label),
            requires_custom_animation_patch=False,
        )

    name_mode = coerce_kotor_output_name_mode(naming.kotor_name_mode)
    requested = (
        naming.requested_kotor_animation_name
        or naming.canonical_kotor_animation_name
        or naming.unreal_clip_name
        or ""
    )
    if name_mode == KotorOutputAnimationNameMode.VANILLA_SLOT:
        slot = str(requested or "").strip()
        if not slot:
            raise RetargetOutputNamingError("Vanilla slot override mode requires a target KOTOR animation slot.")
        try:
            resolved = resolve_animation_slot(target_model, slot, require_valid=require_export_safe)
        except Exception as exc:
            suggestions = _slot_suggestions(target_model)
            raise RetargetOutputNamingError(
                f"Invalid target KOTOR animation slot '{slot}'. "
                "Vanilla slot override mode requires a valid local or inherited Aurora animation slot. "
                "Switch to Custom animation patch mode if your runtime patch will play custom animation names. "
                f"Choose one of: {suggestions}."
            ) from exc
        canonical = str(resolved.slot_name or slot)
        return ResolvedRetargetOutputName(
            mode=KotorOutputAnimationNameMode.VANILLA_SLOT,
            requested_name=slot,
            animation_block_name=canonical,
            display_label=_optional_text(naming.display_label),
            requires_custom_animation_patch=False,
        )

    custom_name = validate_custom_kotor_animation_name(requested)
    warnings: list[str] = []
    if any((not ch.isalnum()) and ch not in {"_", "-"} for ch in custom_name):
        warnings.append(
            "Custom animation name contains spaces or punctuation. Verify your runtime patch calls this name exactly."
        )
    try:
        resolved = resolve_animation_slot(target_model, custom_name, require_valid=True)
        if str(resolved.slot_name or "").lower() == custom_name.lower():
            warnings.append(
                f"Custom animation name '{custom_name}' matches a vanilla slot and may behave like a normal local override."
            )
    except Exception:
        pass
    return ResolvedRetargetOutputName(
        mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        requested_name=custom_name,
        animation_block_name=custom_name,
        display_label=_optional_text(naming.display_label),
        requires_custom_animation_patch=True,
        warnings=tuple(warnings),
    )


def naming_metadata(resolved: ResolvedRetargetOutputName) -> dict[str, Any]:
    return {
        "kotor_output_name_mode": resolved.mode.value,
        "animation_name": resolved.animation_block_name,
        "requires_custom_animation_patch": bool(resolved.requires_custom_animation_patch),
        "vanilla_slot_safe": not bool(resolved.requires_custom_animation_patch),
        "display_label": resolved.display_label,
    }


def _slot_suggestions(target_model) -> str:
    try:
        slots = get_valid_animation_slots(target_model)
    except Exception:
        slots = []
    if not slots:
        return "(no local or inherited slots resolved)"
    shown = slots[:12]
    suffix = "" if len(slots) <= 12 else f", ... ({len(slots) - 12} more)"
    return ", ".join(shown) + suffix


def _sanitize_unreal_clip_name(value: str) -> str:
    text = str(value or "").strip().replace(" ", "_")
    out = "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-"})
    return out.strip("_-")


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
