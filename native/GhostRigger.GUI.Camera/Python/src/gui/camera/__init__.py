"""Compatibility package for camera workflow helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CameraManager": "src.core.camera.camera_manager",
    "FrameRenderer": "src.adapters.qt_viewport.still_frame_renderer",
    "GhostRiggerCamera": "src.core.camera.camera_model",
    "RenderOutput": "src.core.camera.render_output",
    "RenderSettings": "src.core.camera.camera_render_settings",
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
