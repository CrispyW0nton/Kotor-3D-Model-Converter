# ─────────────────────────────────────────────────────────────────────
#  viewport.py — Backward-compatibility shim (T001 split, 2026-05)
#
#  The old 9 932-line ``src.gui.viewport`` module has been split into:
#
#      viewport_core.py   Tk-free rasterizer, camera, texture cache,
#                         FrameRenderer — safe to import under Qt.
#      viewport_tk.py     Legacy Tk widgets (UVViewerWindow,
#                         ViewportWidget) — scheduled for deletion in
#                         M3 / T302.
#
#  This shim preserves the public name ``src.gui.viewport`` so legacy
#  importers (``character_builder_window``, ``main_window``,
#  ``qt_uv_viewer``, MCP tools, regression tests) keep working without
#  modification. New code should import from ``viewport_core`` directly.
#
#  Importing this module pulls tkinter; use ``viewport_core`` if you
#  want Tk-free imports under the Qt branch.
# ─────────────────────────────────────────────────────────────────────

from .viewport_core import *  # noqa: F401,F403 — re-export the full core
from .viewport_tk import UVViewerWindow, ViewportWidget  # noqa: F401
