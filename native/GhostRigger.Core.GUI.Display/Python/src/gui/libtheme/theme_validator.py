"""Validation helpers for theme XML."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from .accessibility_audit import audit_theme_contrast
from .style_tokens import (
    FALLBACK_COLORS,
    FALLBACK_METRICS,
    VALID_BUTTON_MODES,
    VALID_TAB_STYLE_MODES,
)
from .theme_model import Theme

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


class ThemeValidator:
    """Validate a theme file without making invalid files fatal."""

    recommended_tokens = tuple(FALLBACK_COLORS.keys())

    def validate_xml(self, root: ET.Element) -> list[str]:
        warnings: list[str] = []
        if root.tag != "theme":
            warnings.append("Root element must be <theme>.")
        for attr in ("id", "name", "version"):
            if not (root.get(attr) or "").strip():
                warnings.append(f"Theme is missing required attribute '{attr}'.")
        seen = set()
        for color in root.findall("./colors/color"):
            name = (color.get("name") or "").strip()
            value = (color.get("value") or "").strip()
            if not name:
                warnings.append("A <color> entry is missing a name.")
            if value and not _HEX_COLOR_RE.match(value):
                warnings.append(f"Color '{name}' has invalid value '{value}'.")
            seen.add(name)
        for token in self.recommended_tokens:
            if token not in seen:
                warnings.append(f"Theme is missing recommended color token '{token}'; fallback will be used.")
        for metric in root.findall("./metrics/metric"):
            name = metric.get("name") or ""
            try:
                value = int(metric.get("value") or "")
            except ValueError:
                warnings.append(f"Metric '{name}' must be an integer.")
                continue
            if value < 0 or value > 5000:
                warnings.append(f"Metric '{name}' has suspicious value '{value}'.")
        mode = (root.findtext("./icons/defaultMode") or "").strip()
        if mode and mode not in VALID_BUTTON_MODES:
            warnings.append(f"Icon defaultMode '{mode}' is not a supported button mode.")
        for style in root.findall("./styles/style"):
            name = (style.get("name") or "").strip()
            value = (style.get("value") or "").strip()
            if name == "tab.mode" and value not in VALID_TAB_STYLE_MODES:
                warnings.append(f"Tab style mode '{value}' is not supported.")
        return warnings

    def validate_theme(self, theme: Theme) -> list[str]:
        warnings = list(theme.warnings)
        if not theme.id or not theme.name:
            warnings.append("Theme id and name are required.")
        for key, value in theme.colors.items():
            if not _HEX_COLOR_RE.match(value):
                warnings.append(f"Color token '{key}' has invalid value '{value}'.")
        for key, value in theme.metrics.items():
            if value < 0:
                warnings.append(f"Metric '{key}' must not be negative.")
        tab_mode = theme.styles.get("tab.mode", "")
        if tab_mode and tab_mode not in VALID_TAB_STYLE_MODES:
            warnings.append(f"Tab style mode '{tab_mode}' is not supported.")
        warnings.extend(
            f"Accessibility contrast: {issue.message}"
            for issue in audit_theme_contrast(theme)
        )
        return list(dict.fromkeys(warnings))
