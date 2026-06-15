"""Renderer-neutral viewport display mode state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
from typing import Iterable

from src.core.rendering._native import native_rendering


class ViewportDisplayMode(str, Enum):
    WIREFRAME = "wireframe"
    HIDDEN_LINE = "hidden_line"
    SOLID = "solid"
    SHADED = "shaded"
    SMOOTH_SHADED = "smooth_shaded"
    TEXTURED = "textured"
    TEXTURED_LIGHTMAPPED = "textured_lightmapped"
    FULL_MATERIAL = "full_material"
    BOUNDING_BOX = "bounding_box"
    NORMALS_DEBUG = "normals_debug"
    UV_DEBUG = "uv_debug"


@dataclass(frozen=True)
class ViewportDisplayOptions:
    display_mode: ViewportDisplayMode = ViewportDisplayMode.FULL_MATERIAL
    show_grid: bool = True
    show_wire_overlay: bool = False
    show_edged_faces: bool = False
    show_textures: bool = True
    show_lightmaps: bool = False
    show_material_colour: bool = True
    show_alpha: bool = True
    xray: bool = False
    two_sided: bool = True
    show_normals: bool = False
    show_bounds: bool = False
    force_unlit: bool = False
    force_flat_colour: bool = False

    def with_changes(self, **changes: object) -> "ViewportDisplayOptions":
        if "display_mode" in changes:
            changes["display_mode"] = normalize_display_mode(changes["display_mode"])
        return replace(self, **changes)

    def to_legacy_flags(self) -> dict[str, object]:
        mode = self.display_mode
        wire_only = mode is ViewportDisplayMode.WIREFRAME
        textured = bool(self.show_textures and mode is not ViewportDisplayMode.WIREFRAME)
        render_mode = "flat" if mode is ViewportDisplayMode.SOLID else "shaded" if mode in {
            ViewportDisplayMode.SHADED,
            ViewportDisplayMode.SMOOTH_SHADED,
        } else "realistic"
        return {
            "show_solid": not wire_only,
            "show_wireframe": bool(wire_only or self.show_wire_overlay or self.show_edged_faces),
            "show_texture": textured,
            "show_grid": bool(self.show_grid),
            "render_mode": render_mode,
            "show_lightmap_map": bool(self.show_lightmaps),
        }

    def diagnostics(self) -> dict[str, object]:
        return {
            "display_mode": self.display_mode.value,
            "show_grid": self.show_grid,
            "show_wire_overlay": self.show_wire_overlay,
            "show_edged_faces": self.show_edged_faces,
            "show_textures": self.show_textures,
            "show_lightmaps": self.show_lightmaps,
            "show_material_colour": self.show_material_colour,
            "show_alpha": self.show_alpha,
            "xray": self.xray,
            "two_sided": self.two_sided,
            "show_normals": self.show_normals,
            "show_bounds": self.show_bounds,
            "force_unlit": self.force_unlit,
            "force_flat_colour": self.force_flat_colour,
        }


def _python_normalize_display_mode(value: object) -> ViewportDisplayMode:
    if isinstance(value, ViewportDisplayMode):
        return value
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "wire": ViewportDisplayMode.WIREFRAME,
        "wireframe": ViewportDisplayMode.WIREFRAME,
        "hidden": ViewportDisplayMode.HIDDEN_LINE,
        "hidden_line": ViewportDisplayMode.HIDDEN_LINE,
        "solid": ViewportDisplayMode.SOLID,
        "flat": ViewportDisplayMode.SOLID,
        "shaded": ViewportDisplayMode.SHADED,
        "smooth": ViewportDisplayMode.SMOOTH_SHADED,
        "smooth_shaded": ViewportDisplayMode.SMOOTH_SHADED,
        "texture": ViewportDisplayMode.TEXTURED,
        "textured": ViewportDisplayMode.TEXTURED,
        "lightmapped": ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
        "textured_lightmapped": ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
        "realistic": ViewportDisplayMode.FULL_MATERIAL,
        "full": ViewportDisplayMode.FULL_MATERIAL,
        "full_material": ViewportDisplayMode.FULL_MATERIAL,
        "bounds": ViewportDisplayMode.BOUNDING_BOX,
        "bounding_box": ViewportDisplayMode.BOUNDING_BOX,
        "normals": ViewportDisplayMode.NORMALS_DEBUG,
        "normals_debug": ViewportDisplayMode.NORMALS_DEBUG,
        "uv": ViewportDisplayMode.UV_DEBUG,
        "uv_debug": ViewportDisplayMode.UV_DEBUG,
    }
    return aliases.get(key, ViewportDisplayMode.FULL_MATERIAL)


def normalize_display_mode(value: object) -> ViewportDisplayMode:
    dll = native_rendering()
    if dll is not None:
        try:
            raw = dll.gr_rendering_normalize_display_mode(str(value or "").encode("utf-8"))
            if raw:
                return ViewportDisplayMode(raw.decode("utf-8"))
        except (OSError, ValueError):
            pass
    return _python_normalize_display_mode(value)


def display_mode_values(modes: Iterable[ViewportDisplayMode]) -> tuple[str, ...]:
    dll = native_rendering()
    if dll is not None:
        try:
            raw = dll.gr_rendering_display_mode_values_json()
            if raw:
                values = json.loads(raw.decode("utf-8"))
                if isinstance(values, list) and all(isinstance(value, str) for value in values):
                    return tuple(values)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return tuple(mode.value for mode in modes)
