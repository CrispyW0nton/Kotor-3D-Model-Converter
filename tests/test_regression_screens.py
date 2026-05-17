"""M11/T1102 offscreen screenshot regression for the Character Builder HUD."""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image
from PySide6 import QtCore, QtGui, QtWidgets
import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
GOLDEN_DIR = ROOT / "tests" / "golden" / "screens"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


SCREEN_CASES = [
    ("headless_body", "HEADLESS_BODY", 3),
    ("head", "HEAD", 4),
    ("supermodel", "SUPERMODEL", 3),
    ("creature", "CREATURE", 5),
]
SIMILARITY_THRESHOLD = 0.98


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setApplicationName("GhostRiggerScreenshotRegression")
    _install_test_font(app)
    yield app


def _install_test_font(app: QtWidgets.QApplication) -> None:
    font_path = pathlib.Path(os.environ.get(
        "GHOSTRIGGER_SCREENSHOT_FONT",
        r"C:\Windows\Fonts\segoeui.ttf",
    ))
    family = "Segoe UI"
    if font_path.exists():
        font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family = families[0]
    app.setFont(QtGui.QFont(family, 9))


def _mode_enum(mode_name: str) -> Any:
    from src.core.model_data import CharacterMode

    return CharacterMode[mode_name]


class _ScreenshotViewport(QtWidgets.QWidget):
    """Deterministic AccuRig-like viewport stand-in for screenshot baselines."""

    def __init__(self, mode_name: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._mode_name = mode_name
        self.setMinimumSize(460, 520)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor("#0f1110"))

        grid = QtGui.QPen(QtGui.QColor("#1f2b25"))
        grid.setWidth(1)
        painter.setPen(grid)
        for x in range(0, rect.width(), 48):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 48):
            painter.drawLine(0, y, rect.width(), y)

        cx = rect.width() // 2
        top = 82
        skin = QtGui.QColor("#c8c9c0")
        shade = QtGui.QColor("#7d817c")
        accent = QtGui.QColor("#b6d84a")
        cyan = QtGui.QColor("#66cdd3")

        painter.setPen(QtGui.QPen(shade, 14, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.drawLine(cx, top + 70, cx, top + 235)
        painter.drawLine(cx - 95, top + 95, cx + 95, top + 95)
        painter.drawLine(cx - 88, top + 105, cx - 130, top + 215)
        painter.drawLine(cx + 88, top + 105, cx + 130, top + 215)
        painter.drawLine(cx - 38, top + 235, cx - 70, top + 395)
        painter.drawLine(cx + 38, top + 235, cx + 70, top + 395)

        painter.setBrush(skin)
        painter.setPen(QtGui.QPen(QtGui.QColor("#e8e8df"), 2))
        painter.drawEllipse(QtCore.QPoint(cx, top + 38), 34, 42)
        painter.drawRoundedRect(cx - 54, top + 83, 108, 158, 26, 26)

        points = [
            (cx, top + 42, accent), (cx, top + 86, accent),
            (cx - 68, top + 104, cyan), (cx + 68, top + 104, cyan),
            (cx - 125, top + 210, accent), (cx + 125, top + 210, accent),
            (cx - 32, top + 250, accent), (cx + 32, top + 250, accent),
            (cx - 70, top + 395, cyan), (cx + 70, top + 395, cyan),
        ]
        if self._mode_name == "HEAD":
            points.extend([
                (cx - 14, top + 36, cyan), (cx + 14, top + 36, cyan),
                (cx, top + 58, accent),
            ])
        elif self._mode_name == "CREATURE":
            points.extend([
                (cx - 150, top + 250, accent), (cx + 150, top + 250, accent),
                (cx, top + 312, cyan),
            ])
        for x, y, color in points:
            painter.setBrush(color)
            painter.setPen(QtGui.QPen(QtGui.QColor("#eff7c6"), 1))
            painter.drawEllipse(QtCore.QPoint(int(x), int(y)), 11, 11)

        thumb = QtCore.QRect(rect.width() - 138, 16, 112, 184)
        painter.fillRect(thumb, QtGui.QColor("#151816"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#34443a"), 1))
        painter.drawRect(thumb)
        painter.setPen(QtGui.QPen(QtGui.QColor("#5e665f"), 6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        tx = thumb.center().x()
        painter.drawLine(tx, thumb.top() + 44, tx, thumb.bottom() - 42)
        painter.drawLine(tx - 30, thumb.top() + 72, tx + 30, thumb.top() + 72)
        painter.drawLine(tx - 16, thumb.bottom() - 42, tx - 30, thumb.bottom() - 8)
        painter.drawLine(tx + 16, thumb.bottom() - 42, tx + 30, thumb.bottom() - 8)
        painter.setBrush(QtGui.QColor("#777d78"))
        painter.drawEllipse(QtCore.QPoint(tx, thumb.top() + 30), 16, 19)


def _make_screenshot_shell(mode_name: str, step: int) -> QtWidgets.QWidget:
    from src.gui.qt_bottom_strip import QtBottomStrip
    from src.gui.qt_inspector_panel import QtInspectorPanel
    from src.gui.qt_theme import apply_theme
    from src.gui.qt_workflow_rail import QtWorkflowRail

    shell = QtWidgets.QWidget()
    shell.setObjectName("ScreenshotCharacterBuilderShell")
    shell.resize(1024, 768)
    shell.setFont(QtWidgets.QApplication.font())
    apply_theme(shell)

    root = QtWidgets.QVBoxLayout(shell)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    toolbar = QtWidgets.QFrame()
    toolbar.setObjectName("ScreenshotToolbar")
    bar = QtWidgets.QHBoxLayout(toolbar)
    bar.setContentsMargins(12, 6, 12, 6)
    brand = QtWidgets.QLabel("GHOSTRIGGER AUTORIG")
    brand.setStyleSheet("color:#8cc63f; font-weight:800; letter-spacing:0px;")
    bar.addWidget(brand)
    bar.addSpacing(12)
    for label in ("Headless", "Head", "Supermodel", "Creature"):
        chip = QtWidgets.QLabel(label)
        active = label.upper().replace("LESS", "LESS_") in mode_name or label.upper() == mode_name
        chip.setStyleSheet(
            "padding:4px 10px; border-radius:4px; "
            f"border:1px solid {'#8cc63f' if active else '#2c352e'}; "
            f"color:{'#dff4b0' if active else '#9aa39b'};"
        )
        bar.addWidget(chip)
    bar.addStretch(1)
    bar.addWidget(QtWidgets.QLabel("K1"))
    toolbar.setStyleSheet("QFrame#ScreenshotToolbar { background:#111916; }")
    root.addWidget(toolbar)

    body = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    body.setChildrenCollapsible(False)
    rail = QtWorkflowRail()
    rail.set_mode(_mode_enum(mode_name))
    rail.set_current_step(step)
    body.addWidget(rail)

    body.addWidget(_ScreenshotViewport(mode_name))

    inspector = QtInspectorPanel()
    inspector.set_active_mode(_mode_enum(mode_name))
    inspector.set_step(step)
    body.addWidget(inspector)
    body.setSizes([220, 540, 264])
    root.addWidget(body, 1)

    bottom = QtBottomStrip()
    bottom.set_validation("info", "READY", issues=[])
    bottom.set_stats("nodes: 61 | skins: 6 | hooks: ok")
    bottom.set_log_tail("export gate: clean")
    root.addWidget(bottom)
    return shell


def _capture_builder_mode(mode_name: str, step: int, out_path: pathlib.Path, qapp) -> None:
    shell = _make_screenshot_shell(mode_name, step)
    try:
        shell.show()
        qapp.processEvents()
        qapp.processEvents()

        pixmap = shell.grab()
        assert not pixmap.isNull()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        assert pixmap.save(str(out_path), "PNG")
    finally:
        shell.close()
        shell.deleteLater()
        qapp.processEvents()


def _similarity(current_path: pathlib.Path, golden_path: pathlib.Path) -> float:
    current = Image.open(current_path).convert("RGB")
    golden = Image.open(golden_path).convert("RGB")
    if current.size != golden.size:
        return 0.0
    cur = np.asarray(current, dtype=np.float32)
    ref = np.asarray(golden, dtype=np.float32)
    mse = float(np.mean((cur - ref) ** 2))
    return max(0.0, 1.0 - (mse / (255.0 ** 2)))


@pytest.mark.parametrize(
    "case_id,mode_name,step",
    SCREEN_CASES,
    ids=[case[0] for case in SCREEN_CASES],
)
def test_t1102_character_builder_mode_screenshots(
    case_id: str,
    mode_name: str,
    step: int,
    tmp_path: pathlib.Path,
    qapp,
) -> None:
    """Mode HUD screenshots should stay visually close to committed goldens."""
    golden_path = GOLDEN_DIR / f"{case_id}.png"
    current_path = tmp_path / f"{case_id}.png"

    if not golden_path.exists():
        pytest.fail(f"Missing screenshot golden: {golden_path}")

    _capture_builder_mode(mode_name, step, current_path, qapp)

    score = _similarity(current_path, golden_path)
    assert score >= SIMILARITY_THRESHOLD, (
        f"{case_id} screenshot similarity {score:.4f} is below "
        f"{SIMILARITY_THRESHOLD:.2f}; current capture: {current_path}"
    )


def test_t1102_screen_golden_manifest_is_complete() -> None:
    expected = {f"{case_id}.png" for case_id, _mode_name, _step in SCREEN_CASES}
    actual = {path.name for path in GOLDEN_DIR.glob("*.png")}
    assert expected.issubset(actual)
