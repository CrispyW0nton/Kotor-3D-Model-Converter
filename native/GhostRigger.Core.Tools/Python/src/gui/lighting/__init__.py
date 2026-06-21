"""Compatibility package for editable lighting workflow helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "GhostRiggerLight": "src.core.lighting.light_model",
    "LightGroup": "src.core.lighting.light_grouping",
    "LightManager": "src.core.lighting.light_manager",
    "LightSourceType": "src.core.lighting.light_types",
    "LightType": "src.core.lighting.light_types",
    "LightingRigPreset": "src.core.lighting.light_types",
    "LightmapMode": "src.core.lighting.light_types",
    "SceneLightingMode": "src.core.lighting.light_types",
    "ShaderComplexityMode": "src.core.lighting.light_types",
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
"""GhostRigger lighting workflow package."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
