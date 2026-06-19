"""Viewport navigation profile definitions and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.core.rendering._native import native_rendering


@dataclass(frozen=True)
class ViewportNavigationProfile:
    key: str
    label: str
    summary: str


VIEWPORT_NAVIGATION_PROFILES: Mapping[str, ViewportNavigationProfile] = {
    "3dsmax": ViewportNavigationProfile(
        key="3dsmax",
        label="3ds Max",
        summary="Alt+MMB orbit, MMB pan, Alt+RMB zoom, mouse wheel zoom",
    ),
    "blender": ViewportNavigationProfile(
        key="blender",
        label="Blender",
        summary="MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, mouse wheel zoom",
    ),
    "maya": ViewportNavigationProfile(
        key="maya",
        label="Maya",
        summary="Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, mouse wheel zoom",
    ),
}

DEFAULT_VIEWPORT_NAVIGATION_PROFILE = "3dsmax"

VIEWPORT_NAVIGATION_HELP = """GhostRigger keeps global and viewport tool shortcuts reserved before profile keys are handled.

Always available in the viewport:
F: Frame all
R: Reset camera
W: Toggle wireframe
B: Toggle bones
T: Toggle texture
G: Toggle gimbal
Tab: Cycle gimbal mode
Alt+G: Toggle grid
Alt+X: Toggle X-Ray viewport overlay
Ctrl+Z / Ctrl+Y: Undo / redo viewport edit
Mouse wheel: Zoom

3ds Max profile:
Alt+Middle Mouse: Orbit
Middle Mouse: Pan
Alt+Right Mouse: Zoom
Shift+F: Front view
Shift+T: Top view
Shift+L: Left view
Shift+P: Reset perspective camera
Z: Frame all

Blender profile:
Middle Mouse: Orbit
Shift+Middle Mouse: Pan
Ctrl+Middle Mouse: Zoom
1 / Ctrl+1: Front / back view
3 / Ctrl+3: Right / left view
7 / Ctrl+7: Top / bottom view
Home: Frame all

Maya profile:
Alt+Left Mouse: Orbit
Alt+Middle Mouse: Pan
Alt+Right Mouse: Zoom
A or F: Frame all
"""


def _python_normalize_viewport_navigation_profile(value: object) -> str:
    key = str(value or "").strip().lower().replace(" ", "").replace("_", "")
    aliases = {
        "3dmax": "3dsmax",
        "3ds": "3dsmax",
        "max": "3dsmax",
        "3dsmax": "3dsmax",
        "blender": "blender",
        "maya": "maya",
    }
    return aliases.get(key, DEFAULT_VIEWPORT_NAVIGATION_PROFILE)


def normalize_viewport_navigation_profile(value: object) -> str:
    dll = native_rendering()
    if dll is not None:
        try:
            raw = dll.gr_rendering_normalize_viewport_navigation_profile(str(value or "").encode("utf-8"))
            if raw:
                profile_key = raw.decode("utf-8")
                if profile_key in VIEWPORT_NAVIGATION_PROFILES:
                    return profile_key
        except OSError:
            pass
    return _python_normalize_viewport_navigation_profile(value)


def _python_viewport_profile_label(key: object) -> str:
    profile_key = _python_normalize_viewport_navigation_profile(key)
    return VIEWPORT_NAVIGATION_PROFILES[profile_key].label


def viewport_profile_label(key: object) -> str:
    dll = native_rendering()
    if dll is not None:
        try:
            raw = dll.gr_rendering_viewport_navigation_profile_label(str(key or "").encode("utf-8"))
            if raw:
                return raw.decode("utf-8")
        except OSError:
            pass
    return _python_viewport_profile_label(key)


def has_modifier(modifiers, modifier) -> bool:
    return bool(modifiers & modifier)


__all__ = tuple(name for name in globals() if not name.startswith("__"))
