"""Qt-facing bridge for TPC render helpers."""

from __future__ import annotations

from src.core.graphics import tpc_render_utils as _core_tpc_render_utils

globals().update(
    {
        name: value
        for name, value in _core_tpc_render_utils.__dict__.items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)

