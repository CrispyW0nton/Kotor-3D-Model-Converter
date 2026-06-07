"""ModernGL-backed mesh render-data adapter.

Canonical DTO/helper owner: :mod:`src.core.rendering.mesh_render_data`.
This adapter injects the ModernGL VBO builder for legacy render-data callers
that expect prebuilt GPU rows.
"""

from __future__ import annotations

from src.core.rendering import mesh_render_data as _core_mesh_render_data

_CORE_EXPORTS = {
    name
    for name in _core_mesh_render_data.__dict__
    if not (name.startswith("__") and name.endswith("__"))
}
__all__ = tuple(sorted(_CORE_EXPORTS | {"iter_mesh_render_data", "_extract_node_arrays"}))


def _vbo_builder():
    try:
        from src.adapters.rendering.moderngl_resources import _build_vbo_data
    except Exception:
        return None
    return _build_vbo_data


def iter_mesh_render_data(*args, **kwargs):
    kwargs.setdefault("vbo_builder", _vbo_builder())
    return _core_mesh_render_data.iter_mesh_render_data(*args, **kwargs)


def _extract_node_arrays(*args, **kwargs):
    kwargs.setdefault("vbo_builder", _vbo_builder())
    return _core_mesh_render_data._extract_node_arrays(*args, **kwargs)


def __getattr__(name: str):
    if name not in _CORE_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_core_mesh_render_data, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _CORE_EXPORTS)
