"""Qt stylesheet generation from theme tokens."""

from __future__ import annotations

from pathlib import Path

from .theme_model import Theme


class QtStylesheetBuilder:
    def __init__(self) -> None:
        self.icon_dir = (Path(__file__).resolve().parents[1] / "icons").as_posix()

    def build(self, theme: Theme) -> str:
        c = theme.color
        m = theme.metric
        default_font = theme.font("default")
        heading_font = theme.font("heading")
        radius = m("border.radius", 3)
        return f"""
        QMainWindow, QWidget {{
            background: {c('window.background')};
            color: {c('text.primary')};
            font-family: {default_font.family}, Segoe UI, sans-serif;
            font-size: {default_font.size}pt;
        }}
        QMenuBar, QMenu, QToolBar, QStatusBar {{
            background: {c('toolbar.background')};
            color: {c('text.primary')};
            border: 0;
        }}
        QMenuBar {{ padding: 2px 6px; }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {c('selection.background')};
            color: {c('selection.text')};
        }}
        QListWidget, QTextEdit, QPlainTextEdit, QTreeWidget, QTableWidget, QTabWidget::pane {{
            background: {c('viewport.background')};
            color: {c('text.primary')};
            border: 1px solid {c('panel.border')};
        }}
        QTabWidget::pane {{ top: -1px; }}
        QTabBar::tab {{
            background: {c('panel.background')};
            color: {c('text.secondary')};
            border: 1px solid {c('panel.border')};
            border-bottom-color: {c('panel.border')};
            padding: {max(4, m('panel.spacing', 4) + 2)}px 12px;
            min-width: 78px;
            min-height: 22px;
        }}
        QTabBar::tab:selected {{
            background: {c('viewport.background')};
            color: {c('accent.primary')};
            border-color: {c('accent.secondary')};
            border-bottom-color: {c('viewport.background')};
        }}
        QTabBar::tab:hover {{
            color: {c('accent.primary')};
            background: {c('button.hover')};
        }}
        QTabBar QToolButton {{
            background: {c('panel.altBackground')};
            color: {c('accent.primary')};
            border: 1px solid {c('panel.border')};
            width: 22px;
            height: 24px;
            padding: 0px;
            margin: 0px;
        }}
        QTabBar::scroller {{ width: 48px; }}
        QTabBar QToolButton::left-arrow {{
            image: url("{self.icon_dir}/tab_left.svg");
            width: 22px;
            height: 24px;
        }}
        QTabBar QToolButton::right-arrow {{
            image: url("{self.icon_dir}/tab_right.svg");
            width: 22px;
            height: 24px;
        }}
        QHeaderView::section {{
            background: {c('panel.altBackground')};
            color: {c('text.primary')};
            border: 1px solid {c('panel.border')};
            padding: 4px;
        }}
        QRadioButton, QCheckBox, QGroupBox {{
            color: {c('text.primary')};
        }}
        QGroupBox {{
            border: 1px solid {c('panel.border')};
            border-radius: {radius}px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            color: {c('accent.primary')};
        }}
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 13px;
            height: 13px;
        }}
        QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
            background: {c('accent.primary')};
            border: 1px solid {c('accent.secondary')};
        }}
        QRadioButton::indicator:unchecked, QCheckBox::indicator:unchecked {{
            background: {c('window.background')};
            border: 1px solid {c('text.secondary')};
        }}
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
            background: {c('input.background')};
            color: {c('input.text')};
            border: 1px solid {c('input.border')};
            border-radius: {radius}px;
            padding: 4px 6px;
            min-height: {max(18, m('button.height', 28) - 8)}px;
        }}
        QComboBox QAbstractItemView {{
            background: {c('panel.altBackground')};
            color: {c('text.primary')};
            selection-background-color: {c('selection.background')};
            selection-color: {c('selection.text')};
        }}
        QPushButton, QToolButton {{
            background: {c('button.background')};
            color: {c('button.text')};
            border: 1px solid {c('panel.border')};
            border-radius: {radius}px;
            padding: {m('button.paddingV', 5)}px {m('button.paddingH', 10)}px;
            min-height: {m('button.height', 28)}px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background: {c('button.hover')};
            color: {c('accent.primary')};
        }}
        QPushButton:checked, QToolButton:checked {{
            background: {c('button.checked')};
            color: {c('button.accentText')};
            border-color: {c('accent.primary')};
        }}
        QPushButton:disabled, QToolButton:disabled {{
            background: {c('panel.background')};
            color: {c('text.disabled')};
            border-color: {c('panel.border')};
        }}
        QPushButton[accent="true"], QToolButton[accent="true"] {{
            background: {c('accent.primary')};
            color: {c('button.accentText')};
            border-color: {c('accent.primary')};
        }}
        QPushButton[compact="true"], QToolButton[compact="true"] {{
            padding: 2px 8px;
            font-size: {max(8, default_font.size - 1)}pt;
            min-height: {max(22, m('button.height', 28) - 4)}px;
        }}
        QLabel[heading="true"] {{
            color: {c('accent.primary')};
            font-family: {heading_font.family}, Segoe UI, sans-serif;
            font-size: {heading_font.size}pt;
            font-weight: {700 if heading_font.weight.lower() == 'bold' else 400};
        }}
        QFrame#PanelHeader {{
            background: {c('panel.altBackground')};
            border-bottom: 1px solid {c('panel.border')};
        }}
        QFrame#HeaderBar, QFrame#CommandBar {{
            background: transparent;
        }}
        QFrame#HeaderBar {{
            border-bottom: 1px solid {c('toolbar.border')};
        }}
        QFrame#CommandBar {{
            border-top: 1px solid {c('toolbar.border')};
            border-bottom: 1px solid {c('panel.border')};
        }}
        QFrame#LogHeader {{
            background: {c('window.background')};
            border-top: 1px solid {c('panel.border')};
        }}
        QLabel#GhostTitle {{
            color: {c('accent.primary')};
            font-size: {max(13, heading_font.size + 4)}pt;
            font-weight: bold;
        }}
        QLabel#GhostSubtitle, QLabel#HeaderMeta {{
            color: {c('text.secondary')};
            font-size: {max(8, default_font.size - 1)}pt;
        }}
        QLabel#ModelPill {{
            background: {c('window.background')};
            color: {c('accent.primary')};
            border: 1px solid {c('panel.border')};
            border-radius: {radius}px;
            padding: 4px 10px;
            font-weight: bold;
        }}
        QScrollBar:vertical, QScrollBar:horizontal {{
            background: {c('panel.background')};
            border: 0;
            margin: 0;
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: {c('panel.border')};
            border-radius: {radius}px;
            min-height: 24px;
            min-width: 24px;
        }}
        QScrollBar::handle:hover {{
            background: {c('accent.secondary')};
        }}
        QSplitter::handle {{
            background: {c('panel.border')};
        }}
        #ViewportToolbar {{
            background: {c('toolbar.background')};
            border: 0;
            border-bottom: 1px solid {c('toolbar.border')};
        }}
        QLabel#ViewportCanvas {{
            background: {c('viewport.background')};
            color: {c('viewport.text')};
            border: 1px solid {c('viewport.border')};
        }}
        """
