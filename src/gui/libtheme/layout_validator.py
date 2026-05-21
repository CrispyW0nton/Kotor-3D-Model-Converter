"""Validation helpers for layout XML."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .style_tokens import VALID_BUTTON_MODES

KNOWN_PANELS = {
    "library",
    "modules",
    "properties",
    "animationLibrary",
    "meshTools",
    "outputLog",
    "pythonTerminal",
    "lighting",
    "camera",
    "moduleMeshes",
}


class LayoutValidator:
    """Validate layout XML and return warnings instead of raising."""

    def validate_xml(self, root: ET.Element) -> list[str]:
        warnings: list[str] = []
        if root.tag != "layout":
            warnings.append("Root element must be <layout>.")
        for attr in ("id", "name", "version"):
            if not (root.get(attr) or "").strip():
                warnings.append(f"Layout is missing required attribute '{attr}'.")
        for toolbar in root.findall("./toolbars/toolbar"):
            mode = (toolbar.get("buttonMode") or "iconText").strip()
            if mode not in VALID_BUTTON_MODES:
                warnings.append(f"Toolbar '{toolbar.get('id')}' uses unsupported buttonMode '{mode}'.")
            self._check_int(warnings, "toolbar iconSize", toolbar.get("iconSize"), 8, 96)
            self._check_int(warnings, "toolbar height", toolbar.get("height"), 20, 160)
        for panel in root.findall("./panels/panel"):
            panel_id = (panel.get("id") or "").strip()
            if panel_id and panel_id not in KNOWN_PANELS:
                warnings.append(f"Unknown panel id '{panel_id}' will be ignored by older builds.")
            min_width = self._check_int(warnings, f"{panel_id} minWidth", panel.get("minWidth"), 0, 2000)
            preferred_width = self._check_int(warnings, f"{panel_id} preferredWidth", panel.get("preferredWidth"), 0, 4000)
            if min_width is not None and preferred_width is not None and preferred_width < min_width:
                warnings.append(f"Panel '{panel_id}' preferredWidth is smaller than minWidth.")
            min_height = self._check_int(warnings, f"{panel_id} minHeight", panel.get("minHeight"), 0, 2000)
            preferred_height = self._check_int(warnings, f"{panel_id} preferredHeight", panel.get("preferredHeight"), 0, 3000)
            if min_height is not None and preferred_height is not None and preferred_height < min_height:
                warnings.append(f"Panel '{panel_id}' preferredHeight is smaller than minHeight.")
        viewport_toolbar = root.find("./viewport/toolbar")
        if viewport_toolbar is not None:
            mode = (viewport_toolbar.get("buttonMode") or "text").strip()
            if mode not in VALID_BUTTON_MODES:
                warnings.append(f"Viewport toolbar uses unsupported buttonMode '{mode}'.")
        return warnings

    @staticmethod
    def _check_int(
        warnings: list[str],
        label: str,
        raw_value: str | None,
        minimum: int,
        maximum: int,
    ) -> int | None:
        if raw_value in (None, ""):
            return None
        try:
            value = int(raw_value)
        except ValueError:
            warnings.append(f"{label} must be an integer.")
            return None
        if value < minimum or value > maximum:
            warnings.append(f"{label} value '{value}' is outside {minimum}-{maximum}.")
        return value
