"""Compatibility package for backend transform gizmo helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "GizmoMode": "src.core.gizmo.gizmo_mode",
    "TransformGizmoMode": "src.core.gizmo.gizmo_mode",
    "TransformController": "src.core.gizmo.transform_controller",
    "TransformGizmo": "src.core.gizmo.transform_gizmo",
    "TransformSnapshot": "src.core.gizmo.transform_controller",
    "TransformSpace": "src.core.gizmo.gizmo_mode",
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
