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
_SHADOWLANDS_STYLE_ID = "architecture:k1_shadowlands"
_SHADOWLANDS_STYLE_PRESET = {
    # Measured from the retail K1 Upper and Lower Shadowlands AREs, m24aa
    # and m25aa.  Both use the identical grass/fog contract.
    "fog_enabled": True,
    "fog_color": (46, 36, 33),
    "fog_near": 0.0,
    "fog_far": 70.0,
    "sun_ambient": (0, 0, 0),
    "sun_diffuse": (0, 0, 0),
    "dynamic_ambient": (61, 48, 37),
    "shadow_opacity": 0,
    "sun_shadows": False,
    "grass": {
        "texture": "lka_grass",
        "density": 5.0,
        "quad_size": 0.8,
        "prob_ll": 0.25,
        "prob_lr": 0.25,
        "prob_ul": 0.25,
        "prob_ur": 0.25,
    },
}


@dataclass(frozen=True)
class AuthoredWorldLightingUpdate:
    """Result of one KMAP-authored ARE world-lighting edit."""

    project: AuthoredModuleProject
    settings: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class AuthoredEnvironmentStyleUpdate:
    """Result of applying a measured exterior atmosphere without overriding edits."""

    project: AuthoredModuleProject
    applied: bool
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
    # A manual Environment-tab edit deliberately takes ownership away from a
    # kit preset.  The preset helper below restores this marker only while it
    # applies the measured retail defaults itself.
    area.pop("environment_style_preset", None)
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


def apply_authored_environment_style_defaults(
    project: AuthoredModuleProject,
    style_id: str,
) -> AuthoredEnvironmentStyleUpdate:
    """Apply a measured vanilla atmosphere for a newly built exterior style.

    This is intentionally conservative: selecting Shadowlands does not erase
    a creator's existing Environment-tab lighting.  The preset is only
    written for an untouched authored area, and it remains exact enough for a
    generated clearing to meet an appended m24aa/m25aa room without a sudden
    loss of K1 grass or 70 m distance fog at the seam.
    """

    normalized = str(style_id or "").strip().lower()
    if normalized != _SHADOWLANDS_STYLE_ID:
        return AuthoredEnvironmentStyleUpdate(project, False, "No exterior atmosphere preset is required for this kit.")
    if str(project.game or "K1").strip().upper() != "K1":
        return AuthoredEnvironmentStyleUpdate(project, False, "Shadowlands atmosphere is a K1-only preset.")

    module_metadata = dict(project.metadata.metadata)
    existing_area = dict(module_metadata.get("area") or {})
    current_preset = str(existing_area.get("environment_style_preset") or "").strip().lower()
    if current_preset == _SHADOWLANDS_STYLE_ID:
        return AuthoredEnvironmentStyleUpdate(project, False, "Shadowlands grass and fog are already configured.")
    # Do not overwrite a custom world configuration or an imported vanilla
    # area that already carries grass.  Those ARE values are the authority.
    if existing_area and (
        str(existing_area.get("source") or "").strip().lower() == "map_studio:world_settings"
        or bool(existing_area.get("grass"))
        or "grass_texture" in existing_area
        or "grass_tex_name" in existing_area
    ):
        return AuthoredEnvironmentStyleUpdate(
            project,
            False,
            "Kept the existing world environment; Shadowlands grass/fog was not overwritten.",
        )

    lighting_update = update_authored_world_lighting_settings(
        project,
        {
            "profile": "standard",
            **{key: value for key, value in _SHADOWLANDS_STYLE_PRESET.items() if key != "grass"},
        },
    )
    module_metadata = dict(lighting_update.project.metadata.metadata)
    area = dict(module_metadata.get("area") or {})
    area.update(
        {
            "environment_style_preset": _SHADOWLANDS_STYLE_ID,
            "grass": {**dict(_SHADOWLANDS_STYLE_PRESET["grass"]), "source": "k1:m24aa/m25aa"},
        }
    )
    module_metadata["area"] = area
    updated = replace(
        lighting_update.project,
        metadata=replace(lighting_update.project.metadata, metadata=module_metadata),
        extra={
            **dict(lighting_update.project.extra),
            "last_environment_style_update": {
                "style_id": _SHADOWLANDS_STYLE_ID,
                "source": "k1:m24aa/m25aa",
                "grass_texture": "lka_grass",
                "fog_far": 70.0,
            },
        },
    )
    return AuthoredEnvironmentStyleUpdate(
        updated,
        True,
        "Applied measured K1 Shadowlands atmosphere: lka_grass and 70 m distance fog.",
    )


__all__ = [
    "AuthoredEnvironmentStyleUpdate",
    "AuthoredWorldLightingUpdate",
    "WORLD_LIGHTING_PROFILES",
    "apply_authored_environment_style_defaults",
    "authored_world_lighting_settings",
    "default_authored_world_lighting_settings",
    "update_authored_world_lighting_settings",
]
