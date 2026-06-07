"""Shared lighting enums and labels."""

from __future__ import annotations

from enum import Enum


class _LabelEnum(str, Enum):
    @property
    def label(self) -> str:
        return _LABELS.get(str(self.value), str(self.value).replace("_", " ").title())


class LightType(_LabelEnum):
    POINT = "point"
    SPOT = "spot"
    DIRECTIONAL = "directional"
    AREA = "area"
    AMBIENT = "ambient"
    AURORA_POINT = "aurora_point"
    AURORA_AMBIENT = "aurora_ambient"
    AURORA_UNKNOWN = "aurora_unknown"


class LightSourceType(_LabelEnum):
    AURORA = "Aurora"
    GENERATED_RIG = "GeneratedRig"
    EDITABLE = "Editable"


class SceneLightingMode(_LabelEnum):
    SCENE_LIT = "scene"
    UNLIT = "unlit"
    FULLBRIGHT = "fullbright"
    LIGHTMAP_PREVIEW = "lightmap_preview"
    DIFFUSE_ONLY = "diffuse_only"
    NORMAL_ONLY = "normal_only"
    SPECULAR_ONLY = "specular_only"
    ENVIRONMENT_ONLY = "environment_only"
    SHADER_COMPLEXITY = "shader_complexity"
    PHOTOREAL_PREVIEW = "photoreal_preview"


class LightmapMode(_LabelEnum):
    DISABLED = "disabled"
    BAKED = "baked"
    DYNAMIC_PREVIEW = "dynamic_preview"
    HYBRID = "hybrid"
    DEBUG = "debug"


class ShaderComplexityMode(_LabelEnum):
    OFF = "off"
    BASIC = "basic"
    OVERDRAW = "overdraw"
    TEXTURE_COST = "texture_cost"
    LIGHTING_COST = "lighting_cost"
    FULL_COMPLEXITY = "full_complexity"


class LightingRigPreset(_LabelEnum):
    NONE = "none"
    KOTOR_ORIGINAL = "kotor_original"
    NEUTRAL_STUDIO = "neutral_studio"
    CINEMATIC_WARM = "cinematic_warm"
    CINEMATIC_COLD = "cinematic_cold"
    INTERIOR_TORCH = "interior_torch"
    EXTERIOR_MOONLIGHT = "exterior_moonlight"
    PHOTOREAL_SOFTBOX = "photoreal_softbox"
    UNREAL_PREVIEW = "unreal_preview"
    MAX_STYLE_PREVIEW = "max_style_preview"


_LABELS = {
    "point": "Point",
    "spot": "Spot",
    "directional": "Directional",
    "area": "Area",
    "ambient": "Ambient",
    "aurora_point": "AuroraPoint",
    "aurora_ambient": "AuroraAmbient",
    "aurora_unknown": "AuroraUnknown",
    "scene": "Scene Lit",
    "unlit": "Unlit",
    "fullbright": "Fullbright",
    "lightmap_preview": "Lightmap Preview",
    "diffuse_only": "Diffuse Only",
    "normal_only": "Normal Only",
    "specular_only": "Specular Only",
    "environment_only": "Environment Only",
    "shader_complexity": "Shader Complexity",
    "photoreal_preview": "Photoreal Preview",
    "disabled": "Disabled",
    "baked": "Baked",
    "dynamic_preview": "Dynamic Preview",
    "hybrid": "Hybrid",
    "debug": "Debug",
    "off": "Off",
    "basic": "Basic",
    "overdraw": "Overdraw",
    "texture_cost": "Texture Cost",
    "lighting_cost": "Lighting Cost",
    "full_complexity": "Full Complexity",
    "none": "None",
    "kotor_original": "KOTOR Original",
    "neutral_studio": "Neutral Studio",
    "cinematic_warm": "Cinematic Warm",
    "cinematic_cold": "Cinematic Cold",
    "interior_torch": "Interior Torch",
    "exterior_moonlight": "Exterior Moonlight",
    "photoreal_softbox": "Photoreal Softbox",
    "unreal_preview": "Unreal Preview",
    "max_style_preview": "3ds Max Style Preview",
}
