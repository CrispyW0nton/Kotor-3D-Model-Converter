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
        panel_alt = c("panel.backgroundAlt", c("panel.altBackground"))
        button_padding_x = m("button.paddingX", m("button.paddingH", 10))
        button_padding_y = m("button.paddingY", m("button.paddingV", 5))
        input_height = m("input.height", max(18, m("button.height", 28) - 8))
        tab_mode = theme.style("tab.mode", "standard")
        tab_border = f"1px solid {c('panel.border')}"
        tab_selected_border = c("accent.secondary")
        tab_selected_extra = f"border-bottom-color: {c('tab.selectedBackground')};"
        if tab_mode == "flat":
            tab_border = "0px"
            tab_selected_extra = f"border-bottom: 2px solid {c('accent.primary')};"
        elif tab_mode == "beveled":
            tab_selected_border = c("accent.primary")
            tab_selected_extra = (
                f"border-top-color: {c('accent.primary')}; "
                f"border-left-color: {c('panel.backgroundAlt', c('panel.altBackground'))}; "
                f"border-right-color: {c('panel.border')}; "
                f"border-bottom-color: {c('tab.selectedBackground')};"
            )
        return f"""
        QMainWindow, QWidget {{
            background: {c('window.background')};
            color: {c('window.text', c('text.primary'))};
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
            background: {c('table.background', c('viewport.background'))};
            color: {c('table.text', c('text.primary'))};
            border: 1px solid {c('panel.border')};
        }}
        QTabWidget::pane {{ top: -1px; }}
        QTabBar::tab {{
            background: {c('tab.background')};
            color: {c('tab.text')};
            border: {tab_border};
            border-bottom-color: {c('panel.border')};
            padding: {m('tab.paddingY', m('tab.padding', max(4, m('panel.spacing', 4) + 2)))}px {m('tab.paddingX', 12)}px;
            margin: {m('tab.marginY', m('tab.margin', 0))}px {m('tab.marginX', m('tab.margin', 0))}px;
            min-width: {m('tab.width', 78)}px;
            min-height: {m('tab.height', 14)}px;
        }}
        QTabBar::tab:selected {{
            background: {c('tab.selectedBackground')};
            color: {c('tab.selectedText')};
            border-color: {tab_selected_border};
            {tab_selected_extra}
        }}
        QTabBar::tab:hover {{
            color: {c('accent.primary')};
            background: {c('button.hover')};
        }}
        QTabBar QToolButton {{
            background: {panel_alt};
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
            background: {c('table.headerBackground')};
            color: {c('table.headerText')};
            border: 1px solid {c('table.grid', c('panel.border'))};
            padding: 4px;
        }}
        QTreeWidget, QTreeView {{
            background: {c('tree.background')};
            color: {c('tree.text')};
        }}
        QTableWidget, QTableView {{
            gridline-color: {c('table.grid')};
            alternate-background-color: {panel_alt};
        }}
        QRadioButton, QCheckBox, QGroupBox {{
            color: {c('text.primary')};
        }}
        QGroupBox {{
            border: 1px solid {c('groupbox.border')};
            border-radius: {radius}px;
            margin-top: {m('groupbox.margin', 8)}px;
            padding-top: {m('groupbox.margin', 8)}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            color: {c('groupbox.title')};
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
            min-height: {input_height}px;
        }}
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
            border-color: {c('input.focusBorder')};
        }}
        QComboBox QAbstractItemView {{
            background: {panel_alt};
            color: {c('text.primary')};
            selection-background-color: {c('selection.background')};
            selection-color: {c('selection.text')};
        }}
        QPushButton, QToolButton {{
            background: {c('button.background')};
            color: {c('button.text')};
            border: 1px solid {c('panel.border')};
            border-radius: {radius}px;
            padding: {button_padding_y}px {button_padding_x}px;
            min-height: {m('button.height', 28)}px;
            min-width: {m('button.minWidth', 76)}px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background: {c('button.hover')};
            color: {c('accent.primary')};
        }}
        QPushButton:pressed, QToolButton:pressed {{
            background: {c('button.pressed')};
        }}
        QPushButton:checked, QToolButton:checked {{
            background: {c('button.checked')};
            color: {c('button.checkedText', c('button.accentText'))};
            border-color: {c('accent.primary')};
        }}
        QPushButton:disabled, QToolButton:disabled {{
            background: {c('button.disabledBackground')};
            color: {c('button.disabledText', c('text.disabled'))};
            border-color: {c('panel.border')};
        }}
        QPushButton[accent="true"], QToolButton[accent="true"] {{
            background: {c('accent.primary')};
            color: {c('button.accentText')};
            border-color: {c('accent.primary')};
        }}
        QPushButton[compact="true"], QToolButton[compact="true"] {{
            padding: 1px 6px;
            font-size: {max(8, default_font.size - 1)}pt;
            min-height: {max(16, m('button.height', 16))}px;
            min-width: {m('button.minWidth', 64)}px;
        }}
        QLabel[heading="true"] {{
            color: {c('accent.primary')};
            font-family: {heading_font.family}, Segoe UI, sans-serif;
            font-size: {heading_font.size}pt;
            font-weight: {700 if heading_font.weight.lower() == 'bold' else 400};
        }}
        QFrame#PanelHeader {{
            background: {c('panel.headerBackground')};
            color: {c('panel.headerText')};
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
            background: {c('scrollbar.background')};
            border: 0;
            margin: 0;
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: {c('scrollbar.handle')};
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
        QStatusBar {{
            min-height: {m('statusbar.height', 24)}px;
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
