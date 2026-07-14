"""Qt-free Map Studio world-lighting authoring helpers.

World lighting and fog compile into the module ARE.  They are deliberately
separate from authored room lights, which are editor intent for a future
engine-verified MDL/lightmap pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .authored_module_metadata import (
    FULLBRIGHT_LIGHTING_PROFILE,
    AuthoredAreaMetadata,
    authored_area_lighting_values,
    authored_area_metadata,
)
from .authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject


WORLD_LIGHTING_PROFILES: tuple[str, ...] = ("standard", FULLBRIGHT_LIGHTING_PROFILE, "custom")


@dataclass(frozen=True)
class AuthoredWorldLightingUpdate:
    """Result of one KMAP-authored ARE world-lighting edit."""

    project: AuthoredModuleProject
    settings: dict[str, Any]
    summary: str


def _profile(value: Any) -> str:
    text = str(value or "standard").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "standard",
        "default": "standard",
        "game": "standard",
        "kotor": "standard",
        "fullbright_graybox": FULLBRIGHT_LIGHTING_PROFILE,
        "graybox_fullbright": FULLBRIGHT_LIGHTING_PROFILE,
        "debug_fullbright": FULLBRIGHT_LIGHTING_PROFILE,
        "authored": "custom",
    }
    normalized = aliases.get(text, text)
    if normalized not in WORLD_LIGHTING_PROFILES:
        known = ", ".join(WORLD_LIGHTING_PROFILES)
        raise ValueError(f"World lighting profile must be one of: {known}.")
    return normalized


def _rgb(value: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return fallback
    try:
        return tuple(max(0, min(255, int(channel))) for channel in value[:3])  # type: ignore[return-value]
    except (TypeError, ValueError):
        return fallback


def _byte(value: Any, fallback: int) -> int:
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        return fallback


def _bool(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _finite_float(value: Any, fallback: float, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(fallback)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number.")
    return result


def _world_lighting_settings_for_module(module: AuthoredModuleMetadata, *, game: str) -> dict[str, Any]:
    is_k2 = str(game or "K1").strip().upper() == "K2"
    area = authored_area_metadata(module, AuthoredAreaMetadata())
    lighting = authored_area_lighting_values(module, area, is_k2=is_k2)
    profile = _profile(lighting.get("profile") or "standard")
    return {
        "profile": profile,
        "source": str(lighting.get("source") or "map_studio:authored:area_metadata"),
        "sun_ambient": tuple(lighting["sun_ambient"]),
        "sun_diffuse": tuple(lighting["sun_diffuse"]),
        "dynamic_ambient": tuple(lighting["dynamic_ambient"]),
        "shadow_opacity": int(lighting["shadow_opacity"]),
        "sun_shadows": bool(int(lighting["sun_shadows"])),
        "fog_enabled": bool(area.sun_fog_on),
        "fog_color": tuple(area.fog_color),
        "fog_near": float(area.fog_near),
        "fog_far": float(area.fog_far),
    }


def _baseline_world_lighting_settings(project: AuthoredModuleProject) -> dict[str, Any]:
    """Read stored ARE values with the fullbright preview/export overlay removed."""

    metadata = dict(project.metadata.metadata)
    lighting = dict(metadata.get("lighting") or {})
    lighting["profile"] = "standard"
    metadata["lighting"] = lighting
    module = replace(project.metadata, metadata=metadata)
    return _world_lighting_settings_for_module(module, game=project.game)


def _baseline_payload(settings: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sun_ambient",
        "sun_diffuse",
        "dynamic_ambient",
        "shadow_opacity",
        "sun_shadows",
        "fog_enabled",
        "fog_color",
        "fog_near",
        "fog_far",
    )
    return {key: settings[key] for key in keys}


def authored_world_lighting_settings(project: AuthoredModuleProject) -> dict[str, Any]:
    """Return normalized, UI-ready ARE world-lighting and fog values."""

    effective = _world_lighting_settings_for_module(project.metadata, game=project.game)
    baseline = _baseline_world_lighting_settings(project)
    if effective["profile"] == FULLBRIGHT_LIGHTING_PROFILE:
        effective["fog_enabled"] = False
    effective["standard_values"] = _baseline_payload(baseline)
    return effective


def default_authored_world_lighting_settings(game: str = "K1") -> dict[str, Any]:
    """Return the same normalized defaults used for an empty Map Studio UI."""

    metadata = AuthoredModuleMetadata(module_root="map_preview", game=str(game or "K1"))
    settings = _world_lighting_settings_for_module(metadata, game=metadata.game)
    settings["standard_values"] = _baseline_payload(settings)
    return settings


def update_authored_world_lighting_settings(
    project: AuthoredModuleProject,
    values: dict[str, Any] | None = None,
    **changes: Any,
) -> AuthoredWorldLightingUpdate:
    """Persist normalized world-lighting values without touching room geometry.

    The resulting edit is ARE-only authoring intent.  The controller records
    the undo checkpoint and invalidates staged/exported proof state.
    """

    requested = {**dict(values or {}), **changes}
    current = authored_world_lighting_settings(project)
    baseline = dict(current["standard_values"])
    profile = _profile(requested.get("profile", current["profile"]))
    leaving_fullbright = current["profile"] == FULLBRIGHT_LIGHTING_PROFILE and profile != FULLBRIGHT_LIGHTING_PROFILE

    def requested_value(key: str) -> Any:
        value = requested.get(key, baseline[key] if leaving_fullbright else current[key])
        if leaving_fullbright and value == current[key]:
            return baseline[key]
        return value

    sun_ambient = _rgb(requested_value("sun_ambient"), baseline["sun_ambient"])
    sun_diffuse = _rgb(requested_value("sun_diffuse"), baseline["sun_diffuse"])
    dynamic_ambient = _rgb(requested_value("dynamic_ambient"), baseline["dynamic_ambient"])
    shadow_opacity = _byte(requested_value("shadow_opacity"), baseline["shadow_opacity"])
    sun_shadows = _bool(requested_value("sun_shadows"), baseline["sun_shadows"])
    fog_enabled = _bool(requested_value("fog_enabled"), baseline["fog_enabled"])
    fog_color = _rgb(requested_value("fog_color"), baseline["fog_color"])
    fog_near = _finite_float(requested_value("fog_near"), baseline["fog_near"], label="Fog near distance")
    fog_far = _finite_float(requested_value("fog_far"), baseline["fog_far"], label="Fog far distance")
    if fog_near < 0.0 or fog_far < 0.0:
        raise ValueError("Fog near and far distances must be zero or greater.")
    if fog_far < fog_near:
        raise ValueError("Fog far distance must be greater than or equal to fog near distance.")

    module_metadata = dict(project.metadata.metadata)
    lighting = dict(module_metadata.get("lighting") or {})
    lighting.update({"profile": profile, "source": "map_studio:world_settings"})
    lighting_values = {
            "sun_ambient": list(sun_ambient),
            "sun_diffuse": list(sun_diffuse),
            "dynamic_ambient": list(dynamic_ambient),
            "shadow_opacity": shadow_opacity,
            "sun_shadows": 1 if sun_shadows else 0,
    }
    area = dict(module_metadata.get("area") or {})
    area_values = {
            "fog_color": list(fog_color),
            "fog_near": fog_near,
            "fog_far": fog_far,
            "sun_fog_on": fog_enabled,
    }
    if profile == FULLBRIGHT_LIGHTING_PROFILE:
        for key, value in lighting_values.items():
            lighting.setdefault(key, value)
        for key, value in area_values.items():
            area.setdefault(key, value)
    else:
        lighting.update(lighting_values)
        area.update(area_values)
    area["source"] = "map_studio:world_settings"
    module_metadata["lighting"] = lighting
    module_metadata["lighting_profile"] = profile
    module_metadata["area"] = area

    edit_payload = {
        "profile": profile,
        "fog_enabled": False if profile == FULLBRIGHT_LIGHTING_PROFILE else fog_enabled,
        "source": "map_studio:world_settings",
    }
    updated = replace(
        project,
        metadata=replace(project.metadata, metadata=module_metadata),
        extra={
            **dict(project.extra),
            "last_world_lighting_update": edit_payload,
        },
    )
    settings = authored_world_lighting_settings(updated)
    return AuthoredWorldLightingUpdate(
        project=updated,
        settings=settings,
        summary=(
            f"Updated ARE world lighting ({profile}) and "
            f"{'enabled' if settings['fog_enabled'] else 'disabled'} distance fog."
        ),
    )


__all__ = [
    "AuthoredWorldLightingUpdate",
    "WORLD_LIGHTING_PROFILES",
    "authored_world_lighting_settings",
    "default_authored_world_lighting_settings",
    "update_authored_world_lighting_settings",
]
