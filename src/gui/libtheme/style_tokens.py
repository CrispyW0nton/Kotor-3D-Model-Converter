"""Fallback tokens for GhostRigger themes and layouts."""

from __future__ import annotations

LEGACY_MATRIX_COLORS: dict[str, str] = {
    "bg": "#0B0F0D",
    "bg2": "#07100C",
    "panel": "#111916",
    "panel2": "#151D1A",
    "border": "#1B2A22",
    "hover": "#183428",
    "selected": "#00FF7A",
    "accent": "#00FF7A",
    "accent2": "#00D7B5",
    "text": "#E8F0EC",
    "text2": "#7A9A88",
    "success": "#00FF7A",
    "warning": "#FFAA00",
    "error": "#FF4444",
    "gold": "#D8C66A",
}

TOKEN_ALIASES: dict[str, str] = {
    "bg": "window.background",
    "bg2": "viewport.background",
    "panel": "panel.background",
    "panel2": "panel.altBackground",
    "border": "panel.border",
    "hover": "button.hover",
    "selected": "selection.background",
    "accent": "accent.primary",
    "accent2": "accent.secondary",
    "text": "text.primary",
    "text2": "text.secondary",
    "gold": "text.gold",
}

FALLBACK_COLORS: dict[str, str] = {
    "window.background": LEGACY_MATRIX_COLORS["bg"],
    "panel.background": LEGACY_MATRIX_COLORS["panel"],
    "panel.altBackground": LEGACY_MATRIX_COLORS["panel2"],
    "panel.border": LEGACY_MATRIX_COLORS["border"],
    "viewport.background": LEGACY_MATRIX_COLORS["bg2"],
    "viewport.border": "#34383F",
    "viewport.text": "#8F9AAA",
    "toolbar.background": LEGACY_MATRIX_COLORS["panel"],
    "toolbar.border": LEGACY_MATRIX_COLORS["border"],
    "button.background": LEGACY_MATRIX_COLORS["panel2"],
    "button.hover": LEGACY_MATRIX_COLORS["hover"],
    "button.checked": LEGACY_MATRIX_COLORS["accent"],
    "button.text": LEGACY_MATRIX_COLORS["text"],
    "button.accentText": "#001A0E",
    "input.background": LEGACY_MATRIX_COLORS["panel2"],
    "input.text": LEGACY_MATRIX_COLORS["text"],
    "input.border": LEGACY_MATRIX_COLORS["border"],
    "selection.background": LEGACY_MATRIX_COLORS["selected"],
    "selection.text": "#FFFFFF",
    "text.primary": LEGACY_MATRIX_COLORS["text"],
    "text.secondary": LEGACY_MATRIX_COLORS["text2"],
    "text.disabled": "#55665B",
    "text.gold": LEGACY_MATRIX_COLORS["gold"],
    "accent.primary": LEGACY_MATRIX_COLORS["accent"],
    "accent.secondary": LEGACY_MATRIX_COLORS["accent2"],
    "warning": LEGACY_MATRIX_COLORS["warning"],
    "error": LEGACY_MATRIX_COLORS["error"],
    "success": LEGACY_MATRIX_COLORS["success"],
}

FALLBACK_FONTS: dict[str, dict[str, str | int]] = {
    "default": {"family": "Consolas", "size": 9, "weight": "normal"},
    "monospace": {"family": "Consolas", "size": 9, "weight": "normal"},
    "heading": {"family": "Segoe UI", "size": 10, "weight": "bold"},
}

FALLBACK_METRICS: dict[str, int] = {
    "toolbar.height": 34,
    "toolbar.iconSize": 18,
    "toolbar.spacing": 4,
    "button.height": 28,
    "button.minWidth": 76,
    "button.paddingH": 10,
    "button.paddingV": 5,
    "panel.margin": 4,
    "panel.spacing": 4,
    "panel.minWidth": 260,
    "panel.preferredWidth": 360,
    "splitter.handleWidth": 6,
    "bottom.preferredHeight": 220,
    "bottom.minHeight": 120,
    "viewport.minWidth": 500,
    "border.radius": 3,
}

VALID_BUTTON_MODES = {
    "iconOnly",
    "textOnly",
    "iconText",
    "textBesideIcon",
    "textUnderIcon",
}


def color_alias_view(colors: dict[str, str]) -> dict[str, str]:
    """Return the legacy ``C`` dictionary view for older GUI modules."""

    view: dict[str, str] = {}
    for legacy_key, token in TOKEN_ALIASES.items():
        view[legacy_key] = colors.get(token, FALLBACK_COLORS[token])
    for key in ("success", "warning", "error"):
        view[key] = colors.get(key, FALLBACK_COLORS[key])
    return view
