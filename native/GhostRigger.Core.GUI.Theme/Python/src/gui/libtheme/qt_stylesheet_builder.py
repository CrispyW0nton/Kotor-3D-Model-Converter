"""Qt stylesheet generation from theme tokens."""

from __future__ import annotations

from pathlib import Path

from .theme_model import Theme


class QtStylesheetBuilder:
    def __init__(self) -> None:
        self.icon_dir = (Path(__file__).resolve().parents[1] / "icons").as_posix()

    @staticmethod
    def _is_light_hex(value: str) -> bool:
        try:
            raw = str(value or "").strip().lstrip("#")
            r, g, b = (int(raw[index:index + 2], 16) for index in (0, 2, 4))
        except Exception:
            return True
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) >= 128

    def build(self, theme: Theme) -> str:
        if theme.is_native() or theme.is_palette_only():
            return ""
        c = theme.color
        m = theme.metric
        default_font = theme.font("default")
        heading_font = theme.font("heading")
        mono_font = theme.font("monospace")
        radius = m("border.radius", 3)
        panel_alt = c("panel.backgroundAlt", c("panel.altBackground"))
        button_padding_x = m("button.paddingX", m("button.paddingH", 10))
        button_padding_y = m("button.paddingY", m("button.paddingV", 5))
        input_height = m("input.height", max(18, m("button.height", 28) - 8))
        spin_button_width = m("spinbox.buttonWidth", 16)
        spin_button_height = max(8, input_height // 2)
        spin_arrow_variant = "light" if self._is_light_hex(c("spinbox.arrow")) else "dark"
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
        QWidget#WgpuViewportSurface {{
            background: transparent;
            border: 0;
        }}
        QMenuBar, QMenu, QToolBar, QStatusBar {{
            background: {c('toolbar.background')};
            color: {c('text.primary')};
            border: 0;
        }}
        QToolBar#ReservedTopToolbar {{
            background: {c('window.background')};
            border: 0;
            spacing: 0;
            padding: 0;
        }}
        QWidget#ReservedTopUi {{
            background: {c('window.background')};
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
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background: {c('selection.background')};
            color: {c('selection.text')};
        }}
        QTreeWidget::item:selected:!active, QTreeView::item:selected:!active {{
            background: {c('selection.background')};
            color: {c('selection.text')};
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
        QDoubleSpinBox, QSpinBox {{
            padding: 3px {spin_button_width + 7}px 3px 6px;
        }}
        QDoubleSpinBox::up-button, QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: {spin_button_width}px;
            height: {spin_button_height}px;
            margin: 1px 1px 0 0;
            background: {c('spinbox.buttonBackground')};
            border-left: 1px solid {c('spinbox.buttonBorder')};
            border-bottom: 1px solid {c('spinbox.buttonBorder')};
            border-top-right-radius: {max(0, radius - 1)}px;
        }}
        QDoubleSpinBox::down-button, QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: {spin_button_width}px;
            height: {spin_button_height}px;
            margin: 0 1px 1px 0;
            background: {c('spinbox.buttonBackground')};
            border-left: 1px solid {c('spinbox.buttonBorder')};
            border-top: 1px solid {c('spinbox.buttonBorder')};
            border-bottom-right-radius: {max(0, radius - 1)}px;
        }}
        QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
        QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
            background: {c('spinbox.buttonHover')};
        }}
        QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed,
        QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed {{
            background: {c('spinbox.buttonPressed')};
        }}
        QDoubleSpinBox::up-button:disabled, QSpinBox::up-button:disabled,
        QDoubleSpinBox::down-button:disabled, QSpinBox::down-button:disabled {{
            background: {c('button.disabledBackground')};
            border-color: {c('panel.border')};
        }}
        QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
            image: url("{self.icon_dir}/spin_up_{spin_arrow_variant}.svg");
            width: 8px;
            height: 8px;
        }}
        QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
            image: url("{self.icon_dir}/spin_down_{spin_arrow_variant}.svg");
            width: 8px;
            height: 8px;
        }}
        QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled,
        QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {{
            opacity: 0.55;
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
        QToolButton#LogPanelIconButton,
        QToolButton#PythonTerminalIconButton {{
            background: {c('viewportToolbar.background', c('button.background'))};
            border: 1px solid {c('viewportToolbar.border', c('panel.border'))};
            border-radius: {min(radius, 2)}px;
            padding: 1px;
            min-width: 34px;
            max-width: 34px;
            min-height: 24px;
            max-height: 24px;
        }}
        QToolButton#LogPanelIconButton:hover,
        QToolButton#PythonTerminalIconButton:hover {{
            background: {c('button.hover')};
            border-color: {c('accent.primary')};
        }}
        QToolButton#LogPanelIconButton:pressed,
        QToolButton#PythonTerminalIconButton:pressed {{
            background: {c('button.pressed')};
        }}
        QLineEdit#PythonCommandInput {{
            background: {panel_alt};
            color: {c('input.text')};
            border-color: {c('input.focusBorder', c('input.border'))};
        }}
        QToolButton#CollapsibleGroupToggle {{
            min-width: 16px;
            max-width: 16px;
            min-height: 16px;
            max-height: 16px;
            width: 16px;
            height: 16px;
            padding: 0px;
            margin: 0px;
            border-radius: {min(radius, 2)}px;
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
        QFrame#HeaderBar, QFrame#CommandBar, QFrame#CommandBarHost {{
            background: transparent;
        }}
        QFrame#HeaderBar {{
            border-bottom: 1px solid {c('toolbar.border')};
        }}
        QFrame#CommandBarHost {{
            border-top: 1px solid {c('toolbar.border')};
            border-bottom: 1px solid {c('panel.border')};
        }}
        QFrame#CommandBar {{
            border: 0;
        }}
        QFrame#CommandBar QToolButton#CommandStripButton,
        QFrame#CommandBar QToolButton#CommandStripMenuButton {{
            background: {c('viewportToolbar.background', c('button.background'))};
            color: {c('button.text')};
            border: 1px solid {c('viewportToolbar.border', c('panel.border'))};
            border-radius: {min(radius, 2)}px;
            padding: 1px 5px;
            font-size: {max(7, default_font.size - 1)}pt;
            min-height: {max(20, m('button.height', 20))}px;
            max-height: {max(20, m('button.height', 20))}px;
            min-width: {max(28, m('button.height', 20) + 8)}px;
        }}
        QFrame#CommandBar QToolButton#CommandStripMenuButton {{
            min-width: {max(32, m('button.height', 20) + 12)}px;
        }}
        QFrame#CommandBar QToolButton#CommandStripButton:hover,
        QFrame#CommandBar QToolButton#CommandStripMenuButton:hover {{
            background: {c('button.hover')};
            color: {c('accent.primary')};
            border-color: {c('accent.primary')};
        }}
        QFrame#CommandBar QToolButton#CommandStripButton:pressed,
        QFrame#CommandBar QToolButton#CommandStripMenuButton:pressed {{
            background: {c('button.pressed')};
        }}
        QFrame#CommandBar QToolButton#CommandStripButton:checked {{
            background: {c('button.checked')};
            color: {c('button.checkedText', c('button.text'))};
            border-color: {c('accent.primary')};
        }}
        QComboBox#VisualProfileCombo {{
            background: {c('viewportToolbar.background', c('input.background'))};
            color: {c('input.text')};
            border: 1px solid {c('viewportToolbar.border', c('input.border'))};
            border-radius: {min(radius, 2)}px;
            min-height: {max(18, m('button.height', 18))}px;
            padding: 1px 7px;
        }}
        QFrame#LogHeader, QFrame#PythonTerminalHeader {{
            background: {c('window.background')};
            border: 0;
        }}
        QLabel#LogSectionTitle, QLabel#PythonTerminalTitle {{
            color: {c('accent.primary')};
            font-family: {mono_font.family};
            font-size: {max(8, mono_font.size)}pt;
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
            background: transparent;
            color: {c('text.primary')};
            border: 0;
            padding: 2px 6px;
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
        QMainWindow::separator {{
            background: {c('panel.border')};
            width: 4px;
            height: 4px;
        }}
        QMainWindow::separator:hover {{
            background: {c('panel.border')};
        }}
        QStatusBar {{
            min-height: {m('statusbar.height', 24)}px;
        }}
        #ViewportToolbar, #ViewportToolbarBand {{
            background: {c('viewportToolbar.background')};
            border: 1px solid {c('viewportToolbar.border')};
        }}
        QLabel#ViewportCanvas {{
            background: {c('viewport.background')};
            color: {c('viewport.text')};
            border: 1px solid {c('viewport.border')};
        }}
        """
