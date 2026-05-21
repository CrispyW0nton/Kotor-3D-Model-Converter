"""XML loading for GhostRigger themes."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .style_tokens import FALLBACK_COLORS, FALLBACK_FONTS, FALLBACK_METRICS, VALID_BUTTON_MODES
from .theme_model import Theme, ThemeFont, ThemeIcons
from .theme_validator import ThemeValidator


class ThemeLoader:
    def __init__(self, validator: ThemeValidator | None = None) -> None:
        self.validator = validator or ThemeValidator()

    def load_file(self, path: Path) -> Theme | None:
        try:
            root = ET.parse(path).getroot()
        except Exception as exc:
            return Theme(
                id=path.stem,
                name=path.stem,
                version="invalid",
                source_path=str(path),
                warnings=[f"Could not parse theme XML: {exc}"],
            )
        warnings = self.validator.validate_xml(root)
        if root.tag != "theme" or not (root.get("id") and root.get("name")):
            return Theme(
                id=(root.get("id") or path.stem).strip(),
                name=(root.get("name") or path.stem).strip(),
                version=(root.get("version") or "invalid").strip(),
                source_path=str(path),
                warnings=warnings,
            )

        metadata = root.find("metadata")
        colors = dict(FALLBACK_COLORS)
        for entry in root.findall("./colors/color"):
            name = (entry.get("name") or "").strip()
            value = (entry.get("value") or "").strip()
            if name and value:
                colors[name] = value

        fonts: dict[str, ThemeFont] = {}
        for role, data in FALLBACK_FONTS.items():
            fonts[role] = ThemeFont(role=role, family=str(data["family"]), size=int(data["size"]), weight=str(data["weight"]))
        for entry in root.findall("./fonts/font"):
            role = (entry.get("role") or "default").strip()
            family = (entry.get("family") or fonts.get(role, fonts["default"]).family).strip()
            try:
                size = int(entry.get("size") or fonts.get(role, fonts["default"]).size)
            except ValueError:
                size = fonts.get(role, fonts["default"]).size
            weight = (entry.get("weight") or "normal").strip()
            fonts[role] = ThemeFont(role=role, family=family, size=size, weight=weight)

        provider = (root.findtext("./icons/provider") or "qtawesome").strip()
        default_mode = (root.findtext("./icons/defaultMode") or "iconText").strip()
        if default_mode not in VALID_BUTTON_MODES:
            default_mode = "iconText"
        sizes: dict[str, int] = {"toolbar": 18, "largeToolbar": 24}
        for entry in root.findall("./icons/size"):
            role = (entry.get("role") or "").strip()
            try:
                value = int(entry.get("value") or "")
            except ValueError:
                continue
            if role:
                sizes[role] = value

        metrics = dict(FALLBACK_METRICS)
        for entry in root.findall("./metrics/metric"):
            name = (entry.get("name") or "").strip()
            try:
                value = int(entry.get("value") or "")
            except ValueError:
                continue
            if name:
                metrics[name] = value

        high_contrast_text = (root.findtext("./metadata/highContrast") or root.get("highContrast") or "false").lower()
        return Theme(
            id=(root.get("id") or path.stem).strip(),
            name=(root.get("name") or path.stem).strip(),
            version=(root.get("version") or "1").strip(),
            author=(metadata.findtext("author") if metadata is not None else None) or "GhostRigger",
            description=(metadata.findtext("description") if metadata is not None else None) or "",
            mode=((metadata.findtext("mode") if metadata is not None else None) or "dark").strip().lower(),
            colors=colors,
            fonts=fonts,
            icons=ThemeIcons(provider=provider, default_mode=default_mode, sizes=sizes),
            metrics=metrics,
            high_contrast=high_contrast_text in {"1", "true", "yes"},
            source_path=str(path),
            warnings=warnings,
        )

    def load_dir(self, directory: Path) -> dict[str, Theme]:
        themes: dict[str, Theme] = {}
        if not directory.exists():
            return themes
        for path in sorted(directory.glob("*.xml")):
            theme = self.load_file(path)
            if theme is not None and theme.id:
                themes[theme.id] = theme
        return themes
