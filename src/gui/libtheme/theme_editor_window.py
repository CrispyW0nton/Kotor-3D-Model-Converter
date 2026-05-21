"""Theme and layout editor for GhostRigger."""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

from PySide6 import QtCore, QtGui, QtWidgets

from .layout_applier import button_mode_to_toolbutton_style
from .layout_manager import LayoutManager
from .layout_model import LayoutDefinition
from .qt_stylesheet_builder import QtStylesheetBuilder
from .style_tokens import (
    FALLBACK_COLORS,
    FALLBACK_FONTS,
    FALLBACK_METRICS,
    FALLBACK_STYLES,
    VALID_BUTTON_MODES,
    VALID_TAB_STYLE_MODES,
)
from .theme_manager import ThemeManager
from .theme_model import Theme, ThemeFont
from .theme_validator import ThemeValidator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_MATRIX_FONT_DIR = Path(__file__).resolve().parents[1] / "fonts" / "AurebeshAF"
_REGISTERED_MATRIX_FONT = False
_PIXEL_TOKEN_HINTS = (
    "width",
    "height",
    "margin",
    "padding",
    "spacing",
    "radius",
    "border",
    "size",
    "row",
    "handle",
)


def _register_bundled_matrix_font() -> None:
    """Register the packaged Aurebesh font without importing Matrix widgets."""
    global _REGISTERED_MATRIX_FONT
    if _REGISTERED_MATRIX_FONT:
        return
    for filename in (
        "AurebeshAF-CanonTech.otf",
        "AurebeshAF-LegendsTech.otf",
        "AurebeshAF-Canon.otf",
        "AurebeshAF-Legends.otf",
    ):
        path = _MATRIX_FONT_DIR / filename
        if path.exists():
            QtGui.QFontDatabase.addApplicationFont(str(path))
    _REGISTERED_MATRIX_FONT = True


def _metric_unit(token: str) -> str:
    lower = token.lower()
    if lower.endswith(".size") or "fontsize" in lower:
        return "pt" if "font" in lower else "px"
    if any(hint in lower for hint in _PIXEL_TOKEN_HINTS):
        return "px"
    return "px"


class ThemeEditorWindow(QtWidgets.QMainWindow):
    """Editor with local preview and explicit full-application apply actions."""

    themeApplied = QtCore.Signal(str)

    def __init__(
        self,
        theme_manager: ThemeManager,
        layout_manager: LayoutManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.layout_manager = layout_manager
        self._theme = copy.deepcopy(theme_manager.current_theme or theme_manager.get_theme())
        self._layout = copy.deepcopy(layout_manager.current_layout or layout_manager.get_layout())
        self._dirty = False
        _register_bundled_matrix_font()
        self.setObjectName("ThemeEditorWindow")
        self.setWindowTitle("Theme Editor")
        self.resize(1180, 760)
        self._build()
        self._load_theme(self._theme.id)
        self._load_layout(self._layout.id)
        self._refresh_preview()

    def _build(self) -> None:
        toolbar = QtWidgets.QToolBar("Theme Editor Actions", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, slot in (
            ("Apply Theme", self._apply_theme_to_app),
            ("Apply Layout", self._apply_layout_to_app),
            ("Save", self._save),
            ("Reset Changes", self._reset_changes),
            ("Open Theme XML", self._open_theme_xml),
            ("Open Themes Folder", lambda: self._open_folder(self.theme_manager.user_theme_dir)),
            ("Validate All Themes", self._validate_themes),
            ("Validate All Layouts", self._validate_layouts),
        ):
            action = QtGui.QAction(text, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.setCentralWidget(splitter)
        editor_tabs = QtWidgets.QTabWidget()
        splitter.addWidget(editor_tabs)
        splitter.addWidget(self._build_preview_area())
        splitter.setSizes([520, 660])

        editor_tabs.addTab(self._build_theme_page(), "Theme")
        editor_tabs.addTab(self._build_color_page(), "Colours")
        editor_tabs.addTab(self._build_font_page(), "Fonts")
        editor_tabs.addTab(self._build_metric_page(), "Metrics")
        editor_tabs.addTab(self._build_layout_page(), "Layout")

    def _build_theme_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.theme_combo = QtWidgets.QComboBox()
        for theme in self.theme_manager.available_themes():
            self.theme_combo.addItem(theme.name, theme.id)
        self.theme_combo.currentIndexChanged.connect(lambda _=0: self._load_theme(str(self.theme_combo.currentData() or "matrix")))
        self.theme_name = QtWidgets.QLineEdit()
        self.theme_id = QtWidgets.QLineEdit()
        self.theme_version = QtWidgets.QLineEdit()
        self.theme_description = QtWidgets.QPlainTextEdit()
        self.theme_description.setMaximumHeight(70)
        for widget in (self.theme_name, self.theme_id, self.theme_version, self.theme_description):
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._mark_dirty)
        form.addRow("Select theme", self.theme_combo)
        form.addRow("Theme id", self.theme_id)
        form.addRow("Name", self.theme_name)
        form.addRow("Version", self.theme_version)
        form.addRow("Description", self.theme_description)
        root.addLayout(form)
        buttons = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Duplicate Theme", self._duplicate_theme),
            ("Create New Theme", self._new_theme),
            ("Rename Theme", self._rename_theme),
            ("Save Theme As", self._save_theme_as),
            ("Reload Theme", self._reload_theme),
            ("Validate Theme", self._validate_theme),
        ):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        root.addLayout(buttons)
        root.addStretch(1)
        return page

    def _build_color_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        self.color_filter = QtWidgets.QLineEdit()
        self.color_filter.setPlaceholderText("Search colour tokens")
        self.color_filter.textChanged.connect(self._populate_color_tokens)
        root.addWidget(self.color_filter)
        self.color_list = QtWidgets.QTreeWidget()
        self.color_list.setHeaderLabels(["Token", "Colour", "Value"])
        self.color_list.setRootIsDecorated(False)
        self.color_list.setUniformRowHeights(True)
        self.color_list.header().setStretchLastSection(False)
        self.color_list.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.color_list.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.color_list.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.color_list.itemSelectionChanged.connect(self._select_color_token)
        root.addWidget(self.color_list, 1)
        form = QtWidgets.QFormLayout()
        self.color_token_name = QtWidgets.QLineEdit()
        self.color_token_name.setReadOnly(True)
        self.color_value = QtWidgets.QLineEdit()
        self.color_value.textEdited.connect(self._set_color_from_text)
        picker = QtWidgets.QPushButton("Colour Picker")
        picker.clicked.connect(self._pick_color)
        reset = QtWidgets.QPushButton("Reset Token")
        reset.clicked.connect(self._reset_color)
        form.addRow("Token name", self.color_token_name)
        form.addRow("Hex colour", self.color_value)
        form.addRow("", picker)
        form.addRow("", reset)
        root.addLayout(form)
        return page

    def _build_font_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.font_role = QtWidgets.QComboBox()
        self.font_role.currentTextChanged.connect(self._select_font_role)
        self.font_family = QtWidgets.QFontComboBox()
        self.font_family.currentFontChanged.connect(lambda font: self._set_font_field("family", font.family()))
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(6, 36)
        self.font_size.valueChanged.connect(lambda value: self._set_font_field("size", int(value)))
        self.font_weight = QtWidgets.QComboBox()
        self.font_weight.addItems(["normal", "bold"])
        self.font_weight.currentTextChanged.connect(lambda value: self._set_font_field("weight", value))
        self.font_preview = QtWidgets.QLabel("Aa GhostRigger 0123456789")
        form.addRow("Font role", self.font_role)
        form.addRow("Family", self.font_family)
        form.addRow("Size", self.font_size)
        form.addRow("Weight", self.font_weight)
        form.addRow("Preview", self.font_preview)
        return page

    def _build_metric_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        self.metric_filter = QtWidgets.QLineEdit()
        self.metric_filter.setPlaceholderText("Search metric tokens")
        self.metric_filter.textChanged.connect(self._populate_metric_tokens)
        root.addWidget(self.metric_filter)
        style_row = QtWidgets.QFormLayout()
        self.tab_style_mode_combo = QtWidgets.QComboBox()
        for mode in ("standard", "flat", "beveled"):
            if mode in VALID_TAB_STYLE_MODES:
                self.tab_style_mode_combo.addItem(mode.title(), mode)
        self.tab_style_mode_combo.currentIndexChanged.connect(
            lambda _=0: self._set_tab_style_mode(str(self.tab_style_mode_combo.currentData() or "standard"))
        )
        style_row.addRow("Tab style mode", self.tab_style_mode_combo)
        root.addLayout(style_row)
        self.metric_table = QtWidgets.QTableWidget(0, 2)
        self.metric_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._configure_metric_table(self.metric_table, first_column_width=270)
        root.addWidget(self.metric_table)
        return page

    def _build_layout_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.layout_combo = QtWidgets.QComboBox()
        for layout in self.layout_manager.available_layouts():
            self.layout_combo.addItem(layout.name, layout.id)
        self.layout_combo.currentIndexChanged.connect(lambda _=0: self._load_layout(str(self.layout_combo.currentData() or "default")))
        self.button_mode = QtWidgets.QComboBox()
        for mode in sorted(VALID_BUTTON_MODES):
            self.button_mode.addItem(mode, mode)
        self.button_mode.currentTextChanged.connect(self._set_layout_button_mode)
        form.addRow("Select layout", self.layout_combo)
        form.addRow("Button mode preview", self.button_mode)
        root.addLayout(form)
        self.layout_metric_table = QtWidgets.QTableWidget(0, 2)
        self.layout_metric_table.setHorizontalHeaderLabels(["Layout metric", "Value"])
        self._configure_metric_table(self.layout_metric_table, first_column_width=285)
        root.addWidget(self.layout_metric_table, 1)
        buttons = QtWidgets.QHBoxLayout()
        validate = QtWidgets.QPushButton("Validate Layout")
        validate.clicked.connect(self._validate_layout)
        save_as = QtWidgets.QPushButton("Save Layout As")
        save_as.clicked.connect(self._save_layout_as)
        buttons.addWidget(validate)
        buttons.addWidget(save_as)
        buttons.addStretch(1)
        root.addLayout(buttons)
        return page

    def _configure_metric_table(self, table: QtWidgets.QTableWidget, *, first_column_width: int) -> None:
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setShowGrid(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setMinimumSectionSize(120)
        table.setColumnWidth(0, first_column_width)

    def _metric_name_cell(self, token: str) -> QtWidgets.QWidget:
        label = QtWidgets.QLabel(token)
        label.setObjectName("MetricTokenLabel")
        label.setToolTip(token)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setContentsMargins(8, 0, 8, 0)
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 1)
        return wrapper

    def _metric_value_cell(
        self,
        token: str,
        value: int,
        *,
        changed,
        minimum: int = 0,
        maximum: int = 5000,
    ) -> QtWidgets.QWidget:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(int(value))
        spin.setAccelerated(True)
        spin.setKeyboardTracking(False)
        spin.setSuffix(f" {_metric_unit(token)}")
        spin.setProperty("metricToken", token)
        spin.valueChanged.connect(lambda number, key=token: changed(key, int(number)))
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(spin, 0)
        layout.addStretch(1)
        return wrapper

    def _build_preview_area(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("ThemeEditorPreview")
        root = QtWidgets.QVBoxLayout(panel)
        self.preview_toolbar = QtWidgets.QToolBar("Preview Toolbar")
        for text in ("Open", "Save", "Build", "Export"):
            action = QtGui.QAction(text, self.preview_toolbar)
            self.preview_toolbar.addAction(action)
        root.addWidget(self.preview_toolbar)
        row = QtWidgets.QHBoxLayout()
        sample = QtWidgets.QPushButton("Sample Button")
        checked = QtWidgets.QPushButton("Checked")
        checked.setCheckable(True)
        checked.setChecked(True)
        disabled = QtWidgets.QPushButton("Disabled")
        disabled.setEnabled(False)
        for button in (sample, checked, disabled):
            row.addWidget(button)
        root.addLayout(row)
        self.preview_line = QtWidgets.QLineEdit("Sample line edit")
        self.preview_combo = QtWidgets.QComboBox()
        self.preview_combo.addItems(["Default", "Compact", "Wide"])
        self.preview_spin = QtWidgets.QSpinBox()
        self.preview_check = QtWidgets.QCheckBox("Sample checkbox")
        form = QtWidgets.QFormLayout()
        form.addRow("Line edit", self.preview_line)
        form.addRow("Combo box", self.preview_combo)
        form.addRow("Spin box", self.preview_spin)
        form.addRow("", self.preview_check)
        group = QtWidgets.QGroupBox("Sample Group")
        group.setLayout(form)
        root.addWidget(group)
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(QtWidgets.QLabel("Selected tab content"), "Selected")
        tabs.addTab(QtWidgets.QLabel("Inactive tab content"), "Inactive")
        root.addWidget(tabs)
        self.preview_table = QtWidgets.QTableWidget(3, 3)
        self.preview_table.setHorizontalHeaderLabels(["Token", "State", "Value"])
        self.preview_table.setItem(0, 0, QtWidgets.QTableWidgetItem("button.background"))
        self.preview_table.setItem(1, 0, QtWidgets.QTableWidgetItem("input.text"))
        self.preview_table.setItem(2, 0, QtWidgets.QTableWidgetItem("selection.background"))
        root.addWidget(self.preview_table)
        self.preview_tree = QtWidgets.QTreeWidget()
        self.preview_tree.setHeaderLabels(["Tree", "Status"])
        QtWidgets.QTreeWidgetItem(self.preview_tree, ["Panel", "Ready"])
        root.addWidget(self.preview_tree)
        status_row = QtWidgets.QHBoxLayout()
        for text, token in (("Info", "info"), ("Warning", "warning"), ("Error", "error"), ("Success", "success")):
            label = QtWidgets.QLabel(text)
            label.setProperty("_preview_token", token)
            status_row.addWidget(label)
        root.addLayout(status_row)
        self.viewport_swatch = QtWidgets.QLabel("Viewport / transform bar preview")
        self.viewport_swatch.setAlignment(QtCore.Qt.AlignCenter)
        self.viewport_swatch.setMinimumHeight(72)
        root.addWidget(self.viewport_swatch)
        return panel

    def _load_theme(self, theme_id: str) -> None:
        theme = self.theme_manager.get_theme(theme_id)
        self._theme = copy.deepcopy(theme)
        self.theme_id.setText(self._theme.id)
        self.theme_name.setText(self._theme.name)
        self.theme_version.setText(self._theme.version)
        self.theme_description.setPlainText(self._theme.description)
        self._populate_color_tokens()
        self._populate_fonts()
        self._populate_metric_tokens()
        self._populate_style_controls()
        self._dirty = False
        self._refresh_preview()

    def _load_layout(self, layout_id: str) -> None:
        self._layout = copy.deepcopy(self.layout_manager.get_layout(layout_id))
        self.button_mode.setCurrentText(self._layout.toolbar("main").button_mode)
        self._populate_layout_metrics()
        self._refresh_preview()

    def _populate_color_tokens(self) -> None:
        text = self.color_filter.text().strip().lower() if hasattr(self, "color_filter") else ""
        self.color_list.clear()
        for token, value in sorted(self._theme.colors.items()):
            if text and text not in token.lower():
                continue
            item = QtWidgets.QTreeWidgetItem(self.color_list, [token, "", value])
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            item.setBackground(1, QtGui.QColor(value))
            item.setToolTip(1, value)

    def _select_color_token(self) -> None:
        item = self.color_list.currentItem()
        if item is None:
            return
        self.color_token_name.setText(item.text(0))
        self.color_value.setText(item.text(2))

    def _set_color_from_text(self, value: str) -> None:
        token = self.color_token_name.text().strip()
        value = value.strip()
        if not token or not _HEX_RE.match(value):
            return
        self._theme.colors[token] = value.upper()
        item = self.color_list.currentItem()
        if item is not None:
            item.setText(2, value.upper())
            item.setBackground(1, QtGui.QColor(value.upper()))
            item.setToolTip(1, value.upper())
        self._mark_dirty()
        self._refresh_preview()

    def _pick_color(self) -> None:
        current = QtGui.QColor(self.color_value.text())
        picked = QtWidgets.QColorDialog.getColor(current, self, "Select colour")
        if picked.isValid():
            self.color_value.setText(picked.name().upper())
            self._set_color_from_text(picked.name().upper())

    def _reset_color(self) -> None:
        token = self.color_token_name.text().strip()
        if token in FALLBACK_COLORS:
            self.color_value.setText(FALLBACK_COLORS[token])
            self._set_color_from_text(FALLBACK_COLORS[token])

    def _populate_fonts(self) -> None:
        self.font_role.blockSignals(True)
        self.font_role.clear()
        for role in sorted(set(FALLBACK_FONTS) | set(self._theme.fonts)):
            self.font_role.addItem(role)
        self.font_role.blockSignals(False)
        self._select_font_role(self.font_role.currentText())

    def _select_font_role(self, role: str) -> None:
        if not role:
            return
        font = self._theme.font(role)
        self.font_family.blockSignals(True)
        self.font_size.blockSignals(True)
        self.font_weight.blockSignals(True)
        self.font_family.setCurrentFont(QtGui.QFont(font.family))
        self.font_size.setValue(font.size)
        self.font_weight.setCurrentText(font.weight)
        self.font_family.blockSignals(False)
        self.font_size.blockSignals(False)
        self.font_weight.blockSignals(False)
        self.font_preview.setFont(QtGui.QFont(font.family, font.size, 700 if font.weight == "bold" else 400))

    def _set_font_field(self, field: str, value: object) -> None:
        role = self.font_role.currentText()
        if not role:
            return
        font = copy.deepcopy(self._theme.font(role))
        if field == "size":
            font.size = int(value)
        elif field == "family":
            font.family = str(value)
        elif field == "weight":
            font.weight = str(value)
        self._theme.fonts[role] = ThemeFont(role=role, family=font.family, size=font.size, weight=font.weight)
        self._select_font_role(role)
        self._mark_dirty()
        self._refresh_preview()

    def _populate_metric_tokens(self) -> None:
        text = self.metric_filter.text().strip().lower() if hasattr(self, "metric_filter") else ""
        rows = [(k, v) for k, v in sorted(self._theme.metrics.items()) if not text or text in k.lower()]
        self.metric_table.setUpdatesEnabled(False)
        self.metric_table.setRowCount(len(rows))
        for row, (token, value) in enumerate(rows):
            self.metric_table.setCellWidget(row, 0, self._metric_name_cell(token))
            self.metric_table.setCellWidget(
                row,
                1,
                self._metric_value_cell(token, int(value), changed=self._metric_spin_changed),
            )
        self.metric_table.setUpdatesEnabled(True)

    def _populate_style_controls(self) -> None:
        if not hasattr(self, "tab_style_mode_combo"):
            return
        self.tab_style_mode_combo.blockSignals(True)
        mode = self._theme.styles.get("tab.mode", FALLBACK_STYLES["tab.mode"])
        index = self.tab_style_mode_combo.findData(mode)
        self.tab_style_mode_combo.setCurrentIndex(max(index, 0))
        self.tab_style_mode_combo.blockSignals(False)

    def _set_tab_style_mode(self, mode: str) -> None:
        if mode not in VALID_TAB_STYLE_MODES:
            mode = FALLBACK_STYLES["tab.mode"]
        self._theme.styles["tab.mode"] = mode
        self._mark_dirty()
        self._refresh_preview()

    def _metric_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        key_item = self.metric_table.item(item.row(), 0)
        if key_item is None:
            return
        try:
            value = max(0, min(5000, int(item.text())))
        except ValueError:
            return
        self._theme.metrics[key_item.text()] = value
        self._mark_dirty()
        self._refresh_preview()

    def _metric_spin_changed(self, token: str, value: int) -> None:
        self._theme.metrics[token] = max(0, min(5000, int(value)))
        self._mark_dirty()
        self._refresh_preview()

    def _populate_layout_metrics(self) -> None:
        rows = [
            ("window.defaultWidth", self._layout.main_width),
            ("window.defaultHeight", self._layout.main_height),
            ("toolbar.height", self._layout.toolbar("main").height),
            ("toolbar.iconSize", self._layout.toolbar("main").icon_size),
            ("leftPanel.preferredWidth", self._layout.panel("library").preferred_width),
            ("rightPanel.preferredWidth", self._layout.panel("properties").preferred_width),
            ("farRightPanel.preferredWidth", self._layout.panel("meshTools").preferred_width),
            ("bottomPanel.preferredHeight", self._layout.panel("outputLog").preferred_height),
            ("panel.margin", self._layout.spacing_value("margin", FALLBACK_METRICS["panel.margin"])),
            ("panel.spacing", self._layout.spacing_value("panelSpacing", FALLBACK_METRICS["panel.spacing"])),
            ("input.height", self._layout.spacing_value("inputHeight", FALLBACK_METRICS["input.height"])),
            ("tab.height", self._layout.spacing_value("tabHeight", FALLBACK_METRICS["tab.height"])),
            ("tab.width", self._layout.spacing_value("tabWidth", FALLBACK_METRICS["tab.width"])),
            ("tab.padding", self._layout.spacing_value("tabPadding", FALLBACK_METRICS["tab.padding"])),
            ("tab.paddingX", self._layout.spacing_value("tabPaddingX", FALLBACK_METRICS["tab.paddingX"])),
            ("tab.paddingY", self._layout.spacing_value("tabPaddingY", FALLBACK_METRICS["tab.paddingY"])),
            ("tab.margin", self._layout.spacing_value("tabMargin", FALLBACK_METRICS["tab.margin"])),
            ("tab.marginX", self._layout.spacing_value("tabMarginX", FALLBACK_METRICS["tab.marginX"])),
            ("tab.marginY", self._layout.spacing_value("tabMarginY", FALLBACK_METRICS["tab.marginY"])),
            ("table.rowHeight", self._layout.spacing_value("tableRowHeight", FALLBACK_METRICS["table.rowHeight"])),
            ("tree.rowHeight", self._layout.spacing_value("treeRowHeight", FALLBACK_METRICS["tree.rowHeight"])),
            ("splitter.handleWidth", self._layout.spacing_value("splitterHandleWidth", FALLBACK_METRICS["splitter.handleWidth"])),
        ]
        self.layout_metric_table.setUpdatesEnabled(False)
        self.layout_metric_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.layout_metric_table.setCellWidget(row, 0, self._metric_name_cell(key))
            self.layout_metric_table.setCellWidget(
                row,
                1,
                self._metric_value_cell(key, int(value), changed=self._layout_metric_spin_changed, minimum=0),
            )
        self.layout_metric_table.setUpdatesEnabled(True)

    def _layout_metric_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        key = self.layout_metric_table.item(item.row(), 0).text()
        try:
            value = max(12, min(5000, int(item.text())))
        except ValueError:
            return
        self._set_layout_metric(key, value)
        self._mark_dirty()
        self._refresh_preview()

    def _layout_metric_spin_changed(self, key: str, value: int) -> None:
        self._set_layout_metric(key, max(0, min(5000, int(value))))
        self._mark_dirty()
        self._refresh_preview()

    def _set_layout_metric(self, key: str, value: int) -> None:
        if key == "window.defaultWidth":
            self._layout.main_width = value
        elif key == "window.defaultHeight":
            self._layout.main_height = value
        elif key == "toolbar.height":
            self._layout.toolbar("main").height = value
        elif key == "toolbar.iconSize":
            self._layout.toolbar("main").icon_size = value
        elif key == "leftPanel.preferredWidth":
            self._layout.panel("library").preferred_width = value
        elif key == "rightPanel.preferredWidth":
            self._layout.panel("properties").preferred_width = value
        elif key == "farRightPanel.preferredWidth":
            self._layout.panel("meshTools").preferred_width = value
        elif key == "bottomPanel.preferredHeight":
            self._layout.panel("outputLog").preferred_height = value
        else:
            xml_name = {
                "panel.margin": "margin",
                "panel.spacing": "panelSpacing",
                "input.height": "inputHeight",
                "tab.height": "tabHeight",
                "tab.width": "tabWidth",
                "tab.padding": "tabPadding",
                "tab.paddingX": "tabPaddingX",
                "tab.paddingY": "tabPaddingY",
                "tab.margin": "tabMargin",
                "tab.marginX": "tabMarginX",
                "tab.marginY": "tabMarginY",
                "table.rowHeight": "tableRowHeight",
                "tree.rowHeight": "treeRowHeight",
                "splitter.handleWidth": "splitterHandleWidth",
            }.get(key, key)
            self._layout.spacing[xml_name] = value

    def _set_layout_button_mode(self, mode: str) -> None:
        if mode in VALID_BUTTON_MODES:
            self._layout.toolbar("main").button_mode = mode
            self._mark_dirty()
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not hasattr(self, "preview_toolbar"):
            return
        self._theme.id = self.theme_id.text().strip() or self._theme.id
        self._theme.name = self.theme_name.text().strip() or self._theme.name
        self._theme.version = self.theme_version.text().strip() or self._theme.version
        self._theme.description = self.theme_description.toPlainText().strip()
        preview_theme = copy.deepcopy(self._theme)
        if hasattr(self, "tab_style_mode_combo"):
            preview_theme.styles["tab.mode"] = str(self.tab_style_mode_combo.currentData() or FALLBACK_STYLES["tab.mode"])
        for layout_token, metric_token in {
            "tabHeight": "tab.height",
            "tabWidth": "tab.width",
            "tabPadding": "tab.padding",
            "tabPaddingX": "tab.paddingX",
            "tabPaddingY": "tab.paddingY",
            "tabMargin": "tab.margin",
            "tabMarginX": "tab.marginX",
            "tabMarginY": "tab.marginY",
        }.items():
            if layout_token in self._layout.spacing:
                preview_theme.metrics[metric_token] = int(self._layout.spacing[layout_token])
        self.centralWidget().setStyleSheet(QtStylesheetBuilder().build(preview_theme))
        icon_size = self._layout.toolbar("main").icon_size
        self.preview_toolbar.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.preview_toolbar.setToolButtonStyle(button_mode_to_toolbutton_style(self._layout.toolbar("main").button_mode))
        self.preview_toolbar.setMinimumHeight(self._layout.toolbar("main").height)
        self.preview_toolbar.setMaximumHeight(self._layout.toolbar("main").height + 8)
        spacing = self._layout.spacing_value("panelSpacing", 4)
        margin = self._layout.spacing_value("margin", 4)
        for layout in self.centralWidget().findChildren(QtWidgets.QLayout):
            layout.setSpacing(spacing)
            layout.setContentsMargins(margin, margin, margin, margin)
        self.preview_table.verticalHeader().setDefaultSectionSize(self._layout.spacing_value("tableRowHeight", 22))
        for label in self.findChildren(QtWidgets.QLabel):
            token = label.property("_preview_token")
            if token:
                label.setStyleSheet(f"color:{self._theme.color(str(token))}; font-weight:bold;")
        self.viewport_swatch.setStyleSheet(
            f"background:{self._theme.color('viewport.background')}; "
            f"color:{self._theme.color('viewport.text')}; "
            f"border:1px solid {self._theme.color('transformBar.border')};"
        )

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _apply_theme_to_app(self) -> None:
        self.theme_manager.themes[self._theme.id] = copy.deepcopy(self._theme)
        self.theme_manager.settings.selected_theme = self._theme.id
        self.theme_manager.settings.theme_mode = "manual"
        self.theme_manager.current_theme = copy.deepcopy(self._theme)
        self.theme_manager.applier.apply_theme(self._theme, self.parentWidget())
        self.themeApplied.emit(self._theme.id)

    def _apply_layout_to_app(self) -> None:
        parent = self.parentWidget()
        self.layout_manager.layouts[self._layout.id] = copy.deepcopy(self._layout)
        self.layout_manager.settings.selected_layout = self._layout.id
        if isinstance(parent, QtWidgets.QMainWindow):
            self.layout_manager.current_layout = copy.deepcopy(self._layout)
            self.layout_manager.applier.apply_layout(self._layout, parent)

    def _duplicate_theme(self) -> None:
        new_id = f"{self._theme.id}_copy"
        self._theme.id = new_id
        self._theme.name = f"{self._theme.name} Copy"
        self.theme_id.setText(new_id)
        self.theme_name.setText(self._theme.name)
        self._mark_dirty()

    def _new_theme(self) -> None:
        self._theme = Theme(
            id="new_theme",
            name="New Theme",
            version="1",
            colors=dict(FALLBACK_COLORS),
            metrics=dict(FALLBACK_METRICS),
            styles=dict(FALLBACK_STYLES),
        )
        self._load_theme_fields()

    def _rename_theme(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "Rename Theme", "Theme name", text=self.theme_name.text())
        if ok and text.strip():
            self.theme_name.setText(text.strip())
            self._mark_dirty()

    def _load_theme_fields(self) -> None:
        self.theme_id.setText(self._theme.id)
        self.theme_name.setText(self._theme.name)
        self.theme_version.setText(self._theme.version)
        self.theme_description.setPlainText(self._theme.description)
        self._populate_color_tokens()
        self._populate_fonts()
        self._populate_metric_tokens()
        self._populate_style_controls()
        self._refresh_preview()

    def _reload_theme(self) -> None:
        self.theme_manager.reload()
        self._load_theme(str(self.theme_combo.currentData() or self._theme.id))

    def _save(self) -> None:
        self._save_theme_to_path(self.theme_manager.user_theme_dir / f"{self._theme.id}.xml")
        self._save_layout_to_path(self.layout_manager.user_layout_dir / f"{self._layout.id}.xml")

    def _save_theme_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Theme As", str(self.theme_manager.user_theme_dir / f"{self._theme.id}.xml"), "Theme XML (*.xml)")
        if path:
            self._save_theme_to_path(Path(path))

    def _save_layout_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Layout As", str(self.layout_manager.user_layout_dir / f"{self._layout.id}.xml"), "Layout XML (*.xml)")
        if path:
            self._save_layout_to_path(Path(path))

    def _save_theme_to_path(self, path: Path) -> None:
        warnings = ThemeValidator().validate_theme(self._theme)
        invalid = [w for w in warnings if "invalid value" in w]
        if invalid:
            QtWidgets.QMessageBox.warning(self, "Theme Validation", "\n".join(invalid[:12]))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        self._theme_xml().write(path, encoding="utf-8", xml_declaration=True)
        self.theme_manager.reload()
        self._dirty = False

    def _save_layout_to_path(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        self._layout_xml().write(path, encoding="utf-8", xml_declaration=True)
        self.layout_manager.reload()
        self._dirty = False

    def _theme_xml(self) -> ET.ElementTree:
        root = ET.Element("theme", {"id": self._theme.id, "name": self._theme.name, "version": self._theme.version})
        metadata = ET.SubElement(root, "metadata")
        ET.SubElement(metadata, "author").text = self._theme.author
        ET.SubElement(metadata, "description").text = self._theme.description
        ET.SubElement(metadata, "mode").text = self._theme.mode
        colors = ET.SubElement(root, "colors")
        for name, value in sorted(self._theme.colors.items()):
            ET.SubElement(colors, "color", {"name": name, "value": value})
        fonts = ET.SubElement(root, "fonts")
        for font in sorted(self._theme.fonts.values(), key=lambda f: f.role):
            ET.SubElement(fonts, "font", {"role": font.role, "family": font.family, "size": str(font.size), "weight": font.weight})
        icons = ET.SubElement(root, "icons")
        ET.SubElement(icons, "provider").text = self._theme.icons.provider
        ET.SubElement(icons, "defaultMode").text = self._theme.icons.default_mode
        for role, size in sorted(self._theme.icons.sizes.items()):
            ET.SubElement(icons, "size", {"role": role, "value": str(size)})
        metrics = ET.SubElement(root, "metrics")
        for name, value in sorted(self._theme.metrics.items()):
            ET.SubElement(metrics, "metric", {"name": name, "value": str(max(0, min(5000, int(value))))})
        styles = ET.SubElement(root, "styles")
        for name, value in sorted({**FALLBACK_STYLES, **self._theme.styles}.items()):
            ET.SubElement(styles, "style", {"name": name, "value": value})
        ET.indent(root)
        return ET.ElementTree(root)

    def _layout_xml(self) -> ET.ElementTree:
        root = ET.Element("layout", {"id": self._layout.id, "name": self._layout.name, "version": self._layout.version})
        ET.SubElement(root, "mainWindow", {"width": str(self._layout.main_width), "height": str(self._layout.main_height), "maximized": str(self._layout.maximized).lower()})
        toolbars = ET.SubElement(root, "toolbars")
        for toolbar in self._layout.toolbars.values():
            ET.SubElement(toolbars, "toolbar", {"id": toolbar.id, "visible": str(toolbar.visible).lower(), "buttonMode": toolbar.button_mode, "iconSize": str(toolbar.icon_size), "height": str(toolbar.height)})
        panels = ET.SubElement(root, "panels")
        for panel in self._layout.panels.values():
            ET.SubElement(panels, "panel", {"id": panel.id, "region": panel.region, "visible": str(panel.visible).lower(), "minWidth": str(panel.min_width), "preferredWidth": str(panel.preferred_width), "minHeight": str(panel.min_height), "preferredHeight": str(panel.preferred_height)})
        viewport = ET.SubElement(root, "viewport")
        ET.SubElement(viewport, "region", {"id": "mainViewport", "minWidth": str(self._layout.viewport.min_width), "preferredWidth": str(self._layout.viewport.preferred_width)})
        ET.SubElement(viewport, "toolbar", {"visible": str(self._layout.viewport.toolbar_visible).lower(), "buttonMode": self._layout.viewport.toolbar_button_mode, "compact": str(self._layout.viewport.toolbar_compact).lower()})
        spacing = ET.SubElement(root, "spacing")
        for name, value in sorted(self._layout.spacing.items()):
            ET.SubElement(spacing, name, {"value": str(max(0, min(5000, int(value))))})
        ET.indent(root)
        return ET.ElementTree(root)

    def _open_theme_xml(self) -> None:
        path = Path(self._theme.source_path) if self._theme.source_path else self.theme_manager.user_theme_dir / f"{self._theme.id}.xml"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _validate_theme(self) -> None:
        lines = ThemeValidator().validate_theme(self._theme) or ["Theme is valid."]
        QtWidgets.QMessageBox.information(self, "Theme Validation", "\n".join(lines[:80]))

    def _validate_layout(self) -> None:
        lines = list(self._layout.warnings) or ["Layout is valid."]
        QtWidgets.QMessageBox.information(self, "Layout Validation", "\n".join(lines[:80]))

    def _validate_themes(self) -> None:
        self.theme_manager.reload()
        QtWidgets.QMessageBox.information(self, "Theme Validation", "\n".join((self.theme_manager.diagnostics or ["All themes are valid."])[:80]))

    def _validate_layouts(self) -> None:
        self.layout_manager.reload()
        QtWidgets.QMessageBox.information(self, "Layout Validation", "\n".join((self.layout_manager.diagnostics or ["All layouts are valid."])[:80]))

    def _reset_changes(self) -> None:
        self._load_theme(str(self.theme_combo.currentData() or self.theme_manager.get_theme().id))
        self._load_layout(str(self.layout_combo.currentData() or self.layout_manager.get_layout().id))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self._dirty:
            result = QtWidgets.QMessageBox.question(self, "Theme Editor", "Discard unsaved theme/layout changes?")
            if result != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        super().closeEvent(event)
