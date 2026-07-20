"""Validation helpers for layout XML."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .style_tokens import VALID_BUTTON_MODES

KNOWN_PANELS = {
    "contentBrowser",
    "library",
    "modules",
    "scene",
    "properties",
    "animationLibrary",
    "meshTools",
    "nodes",
    "lighting",
    "cameras",
    "moduleMeshes",
    "spriteMaterials",
    "adjustPivot",
    "2das",
    "resources",
    "outputLog",
    "pythonTerminal",
    "guiEditorCatalog",
    "guiEditorInspector",
}

KNOWN_DOCKS = {
    "content_browser",
    "scene",
    "properties",
    "animations",
    "nodes",
    "lighting",
    "cameras",
    "module_meshes",
    "sprite_materials",
    "mesh_tools",
    "adjust_pivot",
    "2das",
    "resources",
    "output_log",
    "python_terminal",
}

VALID_DOCK_AREAS = {"left", "right", "bottom", "top"}
VALID_DOCK_MODES = {"tabbed", "vertical", "horizontal"}


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
        for group in root.findall("./dockLayout/group"):
            group_id = (group.get("id") or "").strip()
            area = (group.get("area") or "left").strip()
            mode = (group.get("mode") or "tabbed").strip()
            if not group_id:
                warnings.append("Dock layout group is missing required attribute 'id'.")
            if area not in VALID_DOCK_AREAS:
                warnings.append(f"Dock group '{group_id}' uses unsupported area '{area}'.")
            if mode not in VALID_DOCK_MODES:
                warnings.append(f"Dock group '{group_id}' uses unsupported mode '{mode}'.")
            for dock in group.findall("./dock"):
                dock_id = (dock.get("id") or "").strip()
                if dock_id and dock_id not in KNOWN_DOCKS:
                    warnings.append(f"Unknown dock id '{dock_id}' will be ignored by older builds.")
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
