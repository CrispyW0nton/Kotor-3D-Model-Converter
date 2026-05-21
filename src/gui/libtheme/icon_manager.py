"""Theme-aware icons for GhostRigger."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui

from .theme_model import Theme

_QTA_MAP = {
    "open": "fa5s.folder-open",
    "autorig": "fa5s.magic",
    "charbuilder": "fa5s.user-cog",
    "modular": "fa5s.cubes",
    "texture": "fa5s.image",
    "import": "fa5s.file-import",
    "export": "fa5s.file-export",
    "settings": "fa5s.cog",
    "anims": "fa5s.film",
    "diag": "fa5s.stethoscope",
    "library": "fa5s.book",
    "props": "fa5s.sliders-h",
}


class ThemeIconManager:
    def __init__(self, icon_dir: Path | None = None) -> None:
        self.icon_dir = icon_dir or Path(__file__).resolve().parents[1] / "icons"

    def icon(self, name: str, theme: Theme | None = None, size: int = 16) -> QtGui.QIcon:
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
