"""Viewport selection-mode labels and icon names."""

from __future__ import annotations

VIEWPORT_SELECTION_MODES: tuple[tuple[str, str, str], ...] = (
    ("object", "Object", "viewport_select_object"),
    ("mesh", "Mesh", "viewport_select_mesh"),
    ("helpers", "Helpers", "viewport_select_helpers"),
    ("lights", "Lights", "viewport_select_lights"),
    ("cameras", "Cameras", "viewport_select_cameras"),
)
VIEWPORT_SELECTION_MODE_LABELS = {mode: label for mode, label, _icon_name in VIEWPORT_SELECTION_MODES}
VIEWPORT_SELECTION_MODE_ICONS = {mode: icon_name for mode, _label, icon_name in VIEWPORT_SELECTION_MODES}

__all__ = tuple(name for name in globals() if not name.startswith("__"))
