"""Shared Qt theme constants and helpers for the GhostRigger migration."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui, QtWidgets


C = {
    "bg": "#0B0F0D",
    "bg2": "#07100C",
    "panel": "#111916",
    "panel2": "#151D1A",
    "border": "#1B2A22",
    "hover": "#183428",
    "selected": "#00FF7A",
    "accent": "#00FF7A",
    "accent2": "#00D7B5",
    "text": "#E8F0EC",
    "text2": "#7A9A88",
    "success": "#00FF7A",
    "warning": "#FFAA00",
    "error": "#FF4444",
    "gold": "#D8C66A",
}

_QT_ICON_DIR = (Path(__file__).resolve().parent / "icons").as_posix()


def icon(name: str, size: int = 16) -> QtGui.QIcon:
    icons_dir = Path(__file__).resolve().parent / "icons"
    path = icons_dir / f"{name}_{size}.png"
    if path.exists():
        return QtGui.QIcon(str(path))
    fallback = icons_dir / f"{name}_24.png"
    return QtGui.QIcon(str(fallback)) if fallback.exists() else QtGui.QIcon()


def apply_theme(widget: QtWidgets.QWidget) -> None:
    widget.setStyleSheet(
        f"""
        QWidget {{
            background: {C['bg']};
            color: {C['text']};
            font-family: Consolas, Segoe UI, sans-serif;
            font-size: 9pt;
        }}
        QMenuBar, QMenu, QToolBar, QStatusBar {{
            background: {C['panel']};
            color: {C['text']};
            border: 0;
        }}
        QMenuBar {{
            padding: 2px 6px;
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {C['border']};
            color: {C['accent']};
        }}
        QListWidget, QTextEdit, QPlainTextEdit, QTreeWidget, QTableWidget, QTabWidget::pane {{
            background: {C['bg2']};
            color: {C['text']};
            border: 1px solid {C['border']};
        }}
        QTabWidget::pane {{
            top: -1px;
        }}
        QTabBar::tab {{
            background: {C['panel']};
            color: {C['text2']};
            border: 1px solid {C['border']};
            border-bottom-color: #D8D8D8;
            padding: 6px 12px;
            min-width: 78px;
            min-height: 22px;
        }}
        QTabBar::tab:selected {{
            background: {C['bg2']};
            color: {C['accent']};
            border-color: #D8D8D8;
            border-bottom-color: {C['bg2']};
        }}
        QTabBar::tab:hover {{
            color: {C['accent']};
            background: {C['hover']};
        }}
        QTabBar QToolButton {{
            background: {C['panel2']};
            color: {C['accent']};
            border: 1px solid {C['border']};
            width: 22px;
            height: 24px;
            padding: 0px;
            margin: 0px;
        }}
        QTabBar::scroller {{
            width: 48px;
        }}
        QTabBar QToolButton::left-arrow {{
            image: url("{_QT_ICON_DIR}/tab_left.svg");
            width: 22px;
            height: 24px;
        }}
        QTabBar QToolButton::right-arrow {{
            image: url("{_QT_ICON_DIR}/tab_right.svg");
            width: 22px;
            height: 24px;
        }}
        QHeaderView::section {{
            background: {C['panel2']};
            color: {C['text']};
            border: 1px solid {C['border']};
            padding: 4px;
        }}
        QRadioButton, QCheckBox, QGroupBox {{
            color: {C['text']};
        }}
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 12px;
            height: 12px;
        }}
        QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
            background: {C['accent']};
            border: 1px solid #D8D8D8;
        }}
        QRadioButton::indicator:unchecked, QCheckBox::indicator:unchecked {{
            background: {C['bg']};
            border: 1px solid {C['text2']};
        }}
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
            background: {C['panel2']};
            color: {C['text']};
            border: 1px solid {C['border']};
            padding: 4px;
        }}
        QPushButton, QToolButton {{
            background: {C['panel2']};
            color: {C['text']};
            border: 1px solid {C['border']};
            padding: 5px 10px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background: {C['border']};
            color: {C['accent']};
        }}
        QPushButton[accent="true"], QToolButton[accent="true"] {{
            background: {C['accent']};
            color: #001A0E;
            border-color: {C['accent']};
        }}
        QPushButton[compact="true"], QToolButton[compact="true"] {{
            padding: 2px 8px;
            font-size: 8pt;
        }}
        QLabel[heading="true"] {{
            color: {C['accent']};
            font-weight: bold;
        }}
        QFrame#PanelHeader {{
            background: {C['panel2']};
            border-bottom: 1px solid {C['border']};
        }}
        QFrame#HeaderBar {{
            background: {C['bg']};
            border-bottom: 1px solid #102019;
        }}
        QFrame#CommandBar {{
            background: {C['panel']};
            border-top: 1px solid #102019;
            border-bottom: 1px solid {C['border']};
        }}
        QFrame#LogHeader {{
            background: {C['bg']};
            border-top: 1px solid {C['border']};
        }}
        QLabel#GhostTitle {{
            color: {C['accent']};
            font-size: 14pt;
            font-weight: bold;
        }}
        QLabel#GhostSubtitle, QLabel#HeaderMeta {{
            color: {C['text2']};
            font-size: 8pt;
        }}
        QLabel#ModelPill {{
            background: {C['bg']};
            color: {C['accent']};
            border: 1px solid {C['border']};
            padding: 4px 10px;
            font-weight: bold;
        }}
        QSplitter::handle {{
            background: {C['border']};
        }}
        """
    )


def heading(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setProperty("heading", True)
    return label
