"""Qt-facing compatibility facade for GPU renderer exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_GPU_EXPORTS = "src.adapters.rendering.gpu_renderer_exports"
_FACTORY_EXPORTS = {
    "FallbackViewportRenderer": "src.adapters.rendering.renderer_factory",
    "create_viewport_renderer": "src.adapters.rendering.renderer_factory",
    "renderer_capabilities_snapshot": "src.adapters.rendering.renderer_factory",
}
_gpu_exports_module = import_module(_GPU_EXPORTS)
__all__ = tuple(getattr(_gpu_exports_module, "__all__", ())) + tuple(_FACTORY_EXPORTS)


def __getattr__(name: str) -> Any:
    factory_module = _FACTORY_EXPORTS.get(name)
    if factory_module is not None:
        value = getattr(import_module(factory_module), name)
    else:
        value = getattr(_gpu_exports_module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

