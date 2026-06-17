"""Theme-aware icons for GhostRigger."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui

from .theme_model import Theme

_QTA_MAP = {
    "new_scene": "fa5s.folder-plus",
    "open": "fa5s.folder-open",
    "save": "fa5s.save",
    "autorig": "fa5s.magic",
    "charbuilder": "fa5s.user-cog",
    "modular": "fa5s.cubes",
    "texture": "fa5s.image",
    "import": "fa5s.file-import",
    "export": "fa5s.file-export",
    "settings": "fa5s.cog",
    "anims": "fa5s.film",
    "sequence": "fa5s.stream",
    "diag": "fa5s.stethoscope",
    "library": "fa5s.book",
    "props": "fa5s.sliders-h",
    "scene": "fa5s.layer-group",
    "lights": "fa5s.lightbulb",
    "cameras": "fa5s.camera",
    "mesh_tools": "fa5s.draw-polygon",
    "output_log": "fa5s.stream",
    "python_terminal": "fa5s.terminal",
}


class ThemeIconManager:
    def __init__(self, icon_dir: Path | None = None) -> None:
        self.icon_dir = icon_dir or Path(__file__).resolve().parents[1] / "icons"
        self._cache: dict[tuple[str, str, str, int], QtGui.QIcon] = {}

    def clear(self) -> None:
        self._cache.clear()

    def icon(self, name: str, theme: Theme | None = None, size: int = 16) -> QtGui.QIcon:
        theme_id = theme.id if theme is not None else ""
        color = theme.color("accent.primary") if theme is not None else ""
        key = (name, theme_id, color, int(size))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        icon = self._build_icon(name, theme, size)
        self._cache[key] = icon
        return icon

    def _build_icon(self, name: str, theme: Theme | None = None, size: int = 16) -> QtGui.QIcon:
        path = self.icon_dir / f"{name}.svg"
        if path.exists():
            return QtGui.QIcon(str(path))
        if theme is not None and theme.icons.provider == "qtawesome":
            qta_name = _QTA_MAP.get(name)
            if qta_name:
                try:
                    import qtawesome as qta

                    return qta.icon(qta_name, color=theme.color("accent.primary"))
                except Exception:
                    pass
        path = self.icon_dir / f"{name}_{size}.png"
        if path.exists():
            return QtGui.QIcon(str(path))
        fallback = self.icon_dir / f"{name}_24.png"
        return QtGui.QIcon(str(fallback)) if fallback.exists() else QtGui.QIcon()
