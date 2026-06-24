"""Theme-aware icons for GhostRigger."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui

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
        if fallback.exists():
            return QtGui.QIcon(str(fallback))
        return self._generated_fallback_icon(name, theme, size)

    @staticmethod
    def _fallback_label(name: str) -> str:
        tokens = [token for token in str(name or "").replace("-", "_").split("_") if token]
        if not tokens:
            return "?"
        skip = {"viewport", "button", "icon", "open"}
        useful = [token for token in tokens if token.lower() not in skip] or tokens
        if len(useful) == 1:
            return useful[0][:2].upper()
        return "".join(token[0] for token in useful[:2]).upper()

    @classmethod
    def _generated_fallback_icon(cls, name: str, theme: Theme | None, size: int) -> QtGui.QIcon:
        pixel_size = max(18, min(32, int(size or 16) + 6))
        pixmap = QtGui.QPixmap(pixel_size, pixel_size)
        pixmap.fill(QtCore.Qt.transparent)

        accent = QtGui.QColor(theme.color("accent.primary")) if theme is not None else QtGui.QColor("#38bdf8")
        background = QtGui.QColor(theme.color("button.background")) if theme is not None else QtGui.QColor("#132225")
        border = QtGui.QColor(accent)
        border.setAlpha(220)
        background.setAlpha(210)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(1.0, 1.0, pixel_size - 2.0, pixel_size - 2.0)
        painter.setPen(QtGui.QPen(border, 1.2))
        painter.setBrush(QtGui.QBrush(background))
        painter.drawRoundedRect(rect, 3.0, 3.0)
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(max(6, int(pixel_size * 0.34)))
        painter.setFont(font)
        painter.setPen(accent)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, cls._fallback_label(name))
        painter.end()
        return QtGui.QIcon(pixmap)
