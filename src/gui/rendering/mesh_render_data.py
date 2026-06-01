"""Compatibility adapter for backend mesh render-data helpers.

Canonical owner: :mod:`src.core.rendering.mesh_render_data`.
"""

from __future__ import annotations

from src.core.rendering import mesh_render_data as _core_mesh_render_data

globals().update(
    {
        name: value
        for name, value in _core_mesh_render_data.__dict__.items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)


def _vbo_builder():
    try:
        from src.gui.rendering.gpu_renderer import _build_vbo_data
    except Exception:
        return None
    return _build_vbo_data


def iter_mesh_render_data(*args, **kwargs):
    kwargs.setdefault("vbo_builder", _vbo_builder())
    return _core_mesh_render_data.iter_mesh_render_data(*args, **kwargs)


def _extract_node_arrays(*args, **kwargs):
    kwargs.setdefault("vbo_builder", _vbo_builder())
    return _core_mesh_render_data._extract_node_arrays(*args, **kwargs)
