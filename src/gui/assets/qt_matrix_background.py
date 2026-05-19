"""Qt Matrix-style background widgets for GhostRigger.

This is the Qt counterpart to ``matrix_background.py``.  It intentionally avoids
Tk canvas APIs and provides QWidget/QLabel-compatible pieces that can later be
backed by the same MP4 frame source.  For now it renders a lightweight animated
digital-rain effect directly with QPainter.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C

_FONT_DIR = Path(__file__).resolve().parents[1] / "fonts" / "AurebeshAF"
_AUREBESH_FAMILY: Optional[str] = None


def aurebesh_font_family() -> str:
    """Register and return the preferred Aurebesh Qt font family."""
    global _AUREBESH_FAMILY
    if _AUREBESH_FAMILY:
        return _AUREBESH_FAMILY

    preferred = [
        "AurebeshAF-CanonTech.otf",
        "AurebeshAF-LegendsTech.otf",
        "AurebeshAF-Canon.otf",
        "AurebeshAF-Legends.otf",
    ]
    families: list[str] = []
    for filename in preferred:
        path = _FONT_DIR / filename
        if not path.exists():
            continue
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QtGui.QFontDatabase.applicationFontFamilies(font_id))

    # Family names are embedded in the font files; prefer anything with Tech.
    for family in families:
        if "tech" in family.lower():
            _AUREBESH_FAMILY = family
            return family
    if families:
        _AUREBESH_FAMILY = families[0]
        return families[0]

    _AUREBESH_FAMILY = "Consolas"
    return _AUREBESH_FAMILY


class QtMatrixEngine(QtCore.QObject):
    tick = QtCore.Signal()

    def __init__(self, parent: Optional[QtCore.QObject] = None, fps: int = 12):
        super().__init__(parent)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick.emit)
        self.interval_ms = max(16, int(1000 / max(1, fps)))

    def start(self) -> None:
        if not self.timer.isActive():
            self.timer.start(self.interval_ms)

    def stop(self) -> None:
        self.timer.stop()


class QtMatrixPanel(QtWidgets.QFrame):
    _GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        engine: Optional[QtMatrixEngine] = None,
        opacity: float = 0.45,
    ):
        super().__init__(parent)
        self.engine = engine or QtMatrixEngine(self)
        self.opacity = max(0.0, min(1.0, opacity))
        self._columns: list[float] = []
        self._speeds: list[float] = []
        self._phase = 0
        self._font_family = aurebesh_font_family()
        self._rng = random.Random(1337)
        self.setAutoFillBackground(False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        self.engine.tick.connect(self._advance)
        self.engine.start()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        count = max(1, self.width() // 12)
        old_count = len(self._columns)
        if count > old_count:
            for idx in range(old_count, count):
                self._columns.append(self._rng.uniform(-self.height(), self.height()))
                self._speeds.append(5.0 + (idx % 6) * 0.7)
        elif count < old_count:
            self._columns = self._columns[:count]
            self._speeds = self._speeds[:count]

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(C["bg"]))
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, False)
        font = QtGui.QFont(self._font_family, 9)
        font.setStyleHint(QtGui.QFont.Monospace)
        painter.setFont(font)
        glyphs = self._GLYPHS
        for idx, y in enumerate(self._columns):
            x = idx * 12 + 3
            for trail_idx, step in enumerate(range(0, 84, 12)):
                char = glyphs[(idx * 7 + trail_idx + self._phase) % len(glyphs)]
                alpha = int(max(28, 210 - step * 2) * self.opacity)
                color = QtGui.QColor(C["accent"])
                color.setAlpha(alpha)
                painter.setPen(color)
                painter.drawText(x, int(y - step), char)
        painter.end()

    def _advance(self) -> None:
        if not self._columns:
            return
        self._phase = (self._phase + 1) % len(self._GLYPHS)
        h = max(1, self.height())
        for idx, y in enumerate(self._columns):
            speed = self._speeds[idx] if idx < len(self._speeds) else 6.0
            y += speed
            if y > h + 72:
                y = self._rng.uniform(-120, -20)
            self._columns[idx] = y
        self.update()


class QtMatrixLabel(QtWidgets.QLabel):
    """Label styled to match MatrixLabel's neon-text role in the Tk UI."""

    def __init__(self, text: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(text, parent)
        self.setStyleSheet(f"color:{C['accent']}; background:transparent; font-weight:bold;")


class QtMatrixBackground(QtMatrixPanel):
    pass
