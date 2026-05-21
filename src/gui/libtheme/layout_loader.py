"""XML loading for GhostRigger layouts."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .layout_model import LayoutDefinition, PanelLayout, ToolbarLayout, ViewportLayout
from .layout_validator import LayoutValidator
from .style_tokens import VALID_BUTTON_MODES


def _bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


class LayoutLoader:
    def __init__(self, validator: LayoutValidator | None = None) -> None:
        self.validator = validator or LayoutValidator()

    def load_file(self, path: Path) -> LayoutDefinition | None:
        try:
            root = ET.parse(path).getroot()
        except Exception as exc:
            return LayoutDefinition(id=path.stem, name=path.stem, version="invalid", source_path=str(path), warnings=[f"Could not parse layout XML: {exc}"])
        warnings = self.validator.validate_xml(root)
        if root.tag != "layout" or not (root.get("id") and root.get("name")):
            return LayoutDefinition(
                id=(root.get("id") or path.stem).strip(),
                name=(root.get("name") or path.stem).strip(),
                version=(root.get("version") or "invalid").strip(),
                source_path=str(path),
                warnings=warnings,
            )

        main_window = root.find("mainWindow")
        toolbars: dict[str, ToolbarLayout] = {}
        for entry in root.findall("./toolbars/toolbar"):
            toolbar_id = (entry.get("id") or "").strip()
            mode = (entry.get("buttonMode") or "iconText").strip()
            if mode not in VALID_BUTTON_MODES:
                mode = "iconText"
            if toolbar_id:
                toolbars[toolbar_id] = ToolbarLayout(
                    id=toolbar_id,
                    visible=_bool(entry.get("visible"), True),
                    button_mode=mode,
                    icon_size=_int(entry.get("iconSize"), 18),
                    height=_int(entry.get("height"), 34),
                )

        panels: dict[str, PanelLayout] = {}
        for entry in root.findall("./panels/panel"):
            panel_id = (entry.get("id") or "").strip()
            if panel_id:
                panels[panel_id] = PanelLayout(
                    id=panel_id,
                    region=(entry.get("region") or "left").strip(),
                    visible=_bool(entry.get("visible"), True),
                    min_width=_int(entry.get("minWidth"), 260),
                    preferred_width=_int(entry.get("preferredWidth"), 340),
                    min_height=_int(entry.get("minHeight"), 120),
                    preferred_height=_int(entry.get("preferredHeight"), 180),
                    collapsed=_bool(entry.get("collapsed"), False),
                )

        viewport = root.find("viewport")
        viewport_region = root.find("./viewport/region")
        viewport_toolbar = root.find("./viewport/toolbar")
        vp_mode = (viewport_toolbar.get("buttonMode") if viewport_toolbar is not None else "text") or "text"
        if vp_mode not in VALID_BUTTON_MODES:
            vp_mode = "text"
        viewport_layout = ViewportLayout(
            min_width=_int(viewport_region.get("minWidth") if viewport_region is not None else None, 500),
            preferred_width=_int(viewport_region.get("preferredWidth") if viewport_region is not None else None, 900),
            toolbar_visible=_bool(viewport_toolbar.get("visible") if viewport_toolbar is not None else None, True),
            toolbar_button_mode=vp_mode,
            toolbar_compact=_bool(viewport_toolbar.get("compact") if viewport_toolbar is not None else None, False),
        )

        spacing: dict[str, int] = {}
        spacing_root = root.find("spacing")
        if spacing_root is not None:
            for child in list(spacing_root):
                spacing[child.tag] = _int(child.get("value"), 0)

        return LayoutDefinition(
            id=(root.get("id") or path.stem).strip(),
            name=(root.get("name") or path.stem).strip(),
            version=(root.get("version") or "1").strip(),
            main_width=_int(main_window.get("width") if main_window is not None else None, 1650),
            main_height=_int(main_window.get("height") if main_window is not None else None, 920),
            maximized=_bool(main_window.get("maximized") if main_window is not None else None, False),
            toolbars=toolbars,
            panels=panels,
            viewport=viewport_layout,
            spacing=spacing,
            source_path=str(path),
            warnings=warnings,
        )

    def load_dir(self, directory: Path) -> dict[str, LayoutDefinition]:
        layouts: dict[str, LayoutDefinition] = {}
        if not directory.exists():
            return layouts
        for path in sorted(directory.glob("*.xml")):
            layout = self.load_file(path)
            if layout is not None and layout.id:
                layouts[layout.id] = layout
        return layouts
