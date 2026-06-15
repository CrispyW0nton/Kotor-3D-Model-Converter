"""Validated settings for generated lightmap bakes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_LIGHTMAP_RESOLUTIONS = (256, 512, 768, 1024, 2048)
SUPPORTED_LIGHTMAP_PREVIEW_RESOLUTIONS = (64, 128, 256, 512)
SUPPORTED_LIGHTMAP_FORMATS = ("png", "tga", "jpg", "jpeg")


@dataclass
class LightmapBakeSettings:
    resolution: int = 1024
    # UI labels are artist-facing and one-indexed: UV1, UV2, UV3.
    # Internally the baker stays zero-indexed: UV1 -> 0, UV2 -> 1, UV3 -> 2.
    selected_uv_channel: int = 1
    output_format: str = "png"
    output_directory: str = ""
    filename_prefix: str = ""
    bake_selected_only: bool = False
    bake_visible_only: bool = True
    include_disabled_lights: bool = False
    include_aurora_lights: bool = True
    include_generated_rig_lights: bool = True
    include_dynamic_lights: bool = True
    include_ambient: bool = False
    include_diffuse: bool = True
    include_normal_maps: bool = True
    include_specular: bool = False
    include_environment: bool = False
    use_gpu_acceleration: bool = True
    use_shadows: bool = False
    use_ambient_occlusion: bool = False
    use_direct_lighting: bool = True
    use_indirect_approximation: bool = False
    samples_per_texel: int = 1
    ambient_strength: float = 1.0
    diffuse_strength: float = 1.0
    indirect_strength: float = 1.0
    shadow_strength: float = 1.0
    normal_bias: float = 0.002
    light_falloff_multiplier: float = 1.0
    use_aurora_lights: bool = True
    use_original_lightmap_as_reference: bool = False
    preview_resolution: int = 128
    bake_resolution: int = 0
    shadow_samples: int = 1
    padding_pixels: int = 8
    dilation_passes: int = 8
    background_color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    exposure: float = 1.0
    gamma: float = 2.2
    clamp_output: bool = True
    overwrite_existing: bool = False
    generate_manifest: bool = True
    preview_after_bake: bool = True
    quality_preset: str = "standard"

    warnings: list[str] = field(default_factory=list, repr=False)

    def normalized(self) -> "LightmapBakeSettings":
        """Return a corrected copy. Invalid user input becomes safe defaults."""
        data = asdict(self)
        data.pop("warnings", None)
        clean = LightmapBakeSettings(**data)
        clean.warnings = []

        if clean.resolution not in SUPPORTED_LIGHTMAP_RESOLUTIONS:
            clean.warnings.append(f"Unsupported resolution {clean.resolution}; using 1024.")
            clean.resolution = 1024
        if clean.bake_resolution <= 0:
            clean.bake_resolution = clean.resolution
        elif clean.bake_resolution not in SUPPORTED_LIGHTMAP_RESOLUTIONS:
            clean.bake_resolution = clean.resolution
        else:
            clean.resolution = clean.bake_resolution

        if clean.preview_resolution not in SUPPORTED_LIGHTMAP_PREVIEW_RESOLUTIONS:
            clean.warnings.append(f"Unsupported preview resolution {clean.preview_resolution}; using 128.")
            clean.preview_resolution = 128

        fmt = str(clean.output_format or "png").lower().lstrip(".")
        if fmt not in SUPPORTED_LIGHTMAP_FORMATS:
            clean.warnings.append(f"Unsupported output format {clean.output_format!r}; using png.")
            fmt = "png"
        clean.output_format = fmt

        clean.samples_per_texel = max(1, _int(clean.samples_per_texel, 1))
        clean.selected_uv_channel = max(0, _int(clean.selected_uv_channel, 1))
        clean.shadow_samples = max(1, _int(clean.shadow_samples, 1))
        clean.padding_pixels = max(0, _int(clean.padding_pixels, 8))
        clean.dilation_passes = max(0, _int(clean.dilation_passes, clean.padding_pixels))
        clean.exposure = _positive_float(clean.exposure, 1.0, "exposure", clean.warnings)
        clean.gamma = _positive_float(clean.gamma, 2.2, "gamma", clean.warnings)
        clean.ambient_strength = _non_negative_float(clean.ambient_strength, 1.0, "ambient strength", clean.warnings)
        clean.diffuse_strength = _non_negative_float(clean.diffuse_strength, 1.0, "diffuse strength", clean.warnings)
        clean.indirect_strength = _non_negative_float(clean.indirect_strength, 1.0, "indirect strength", clean.warnings)
        clean.shadow_strength = min(1.0, _non_negative_float(clean.shadow_strength, 1.0, "shadow strength", clean.warnings))
        clean.normal_bias = _non_negative_float(clean.normal_bias, 0.002, "normal bias", clean.warnings)
        clean.light_falloff_multiplier = _positive_float(
            clean.light_falloff_multiplier,
            1.0,
            "light falloff multiplier",
            clean.warnings,
        )
        clean.include_aurora_lights = bool(clean.include_aurora_lights and clean.use_aurora_lights)
        clean.output_directory = str(clean.output_directory or "").strip()
        return clean

    def validate(self) -> list[str]:
        return self.normalized().warnings

    def to_summary(self) -> dict[str, Any]:
        data = asdict(self.normalized())
        data.pop("warnings", None)
        return data

    @classmethod
    def for_quality(cls, preset: str, **overrides: Any) -> "LightmapBakeSettings":
        key = str(preset or "standard").strip().lower()
        values: dict[str, Any]
        if key == "draft":
            values = {
                "resolution": 512,
                "bake_resolution": 512,
                "preview_resolution": 128,
                "samples_per_texel": 1,
                "shadow_samples": 1,
                "padding_pixels": 4,
                "dilation_passes": 4,
                "quality_preset": "draft",
            }
        elif key == "high":
            values = {
                "resolution": 2048,
                "bake_resolution": 2048,
                "preview_resolution": 256,
                "samples_per_texel": 4,
                "shadow_samples": 4,
                "padding_pixels": 12,
                "dilation_passes": 12,
                "quality_preset": "high",
            }
        elif key == "custom":
            values = {"quality_preset": "custom"}
        else:
            values = {
                "resolution": 1024,
                "bake_resolution": 1024,
                "preview_resolution": 128,
                "samples_per_texel": 2,
                "shadow_samples": 2,
                "padding_pixels": 8,
                "dilation_passes": 8,
                "quality_preset": "standard",
            }
        values.update(overrides)
        return cls(**values).normalized()

    def output_dir_path(self) -> Path:
        return Path(self.output_directory or "exports/lightmaps")


def _int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _positive_float(value: object, fallback: float, label: str, warnings: list[str]) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        warnings.append(f"Invalid {label}; using {fallback}.")
        return fallback
    if parsed <= 0.0:
        warnings.append(f"{label} must be greater than zero; using {fallback}.")
        return fallback
    return parsed


def _non_negative_float(value: object, fallback: float, label: str, warnings: list[str]) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        warnings.append(f"Invalid {label}; using {fallback}.")
        return fallback
    if parsed < 0.0:
        warnings.append(f"{label} must be non-negative; using {fallback}.")
        return fallback
    return parsed
