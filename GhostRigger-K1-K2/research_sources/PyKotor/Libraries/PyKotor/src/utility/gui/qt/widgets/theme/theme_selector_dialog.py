"""Reusable theme selector dialog: search, theme list, style list, live-apply signals. No Toolset deps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from utility.gui.qt.widgets.theme.theme_manager import ThemeManager

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


def _default_tr(text: str) -> str:
    """Default no-op translator; host can pass a real tr."""
    return text


class ThemeSelectorDialog(QDialog):
    """Non-blocking dialog for selecting application themes and styles. Emits theme_changed/style_changed."""

    theme_changed = Signal(str)
    style_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme_manager: ThemeManager | None = None,
        available_themes: list[str] | None = None,
        available_styles: list[str] | None = None,
        current_theme: str | None = None,
        current_style: str | None = None,
        tr: Callable[[str], str] | None = None,
        install_no_scroll_filter: bool = True,
    ):
        """Initialize the theme selector dialog.

        Args:
            parent: Parent widget.
            theme_manager: Optional ThemeManager; if not provided a default is created.
            available_themes: List of theme names (default: from manager.get_available_themes()).
            available_styles: List of style names (default: from manager.get_default_styles()).
            current_theme: Currently selected theme name.
            current_style: Currently selected style name (empty string = native/system).
            tr: Optional translator; defaults to identity.
            install_no_scroll_filter: If True, install utility NoScrollEventFilter on list/line edit widgets.
        """
        super().__init__(parent)
        self._tr = tr or _default_tr
        self._manager = theme_manager or ThemeManager()
        self._available_themes = available_themes if available_themes is not None else list(self._manager.get_available_themes())
        self._available_styles = available_styles if available_styles is not None else list(self._manager.get_default_styles())
        self._current_theme = current_theme
        self._current_style = current_style
        self._init_ui()
        self._populate_lists()
        if install_no_scroll_filter:
            self._install_no_scroll_filter()

    def _init_ui(self) -> None:
        """Set up the user interface (Python-built, no .ui file)."""
        self.setMinimumSize(450, 500)
        self.resize(550, 650)
        self.setWindowTitle(self._tr("Theme Selection"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
        )

        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(15, 15, 15, 15)

        # Search
        search_layout = QVBoxLayout()
        search_layout.addWidget(QLabel(self._tr("Search:")))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(self._tr("Filter themes and styles..."))
        search_layout.addWidget(self._search_edit)
        main.addLayout(search_layout)

        # Themes section
        themes_layout = QVBoxLayout()
        themes_layout.setSpacing(5)
        themes_header = QHBoxLayout()
        themes_label = QLabel(self._tr("Themes:"))
        themes_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-top: 5px;")
        themes_header.addWidget(themes_label)
        self._current_theme_display = QLineEdit()
        self._current_theme_display.setReadOnly(True)
        self._current_theme_display.setPlaceholderText(self._tr("No theme selected"))
        self._current_theme_display.setStyleSheet(
            "background-color: palette(base); border: 1px solid palette(mid); padding: 2px;"
        )
        themes_header.addWidget(self._current_theme_display)
        themes_layout.addLayout(themes_header)
        self._themes_list = QListWidget()
        self._themes_list.setMinimumHeight(200)
        self._themes_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        themes_layout.addWidget(self._themes_list)
        main.addLayout(themes_layout)

        # Styles section
        styles_layout = QVBoxLayout()
        styles_layout.setSpacing(5)
        styles_header = QHBoxLayout()
        styles_label = QLabel(self._tr("Application Styles:"))
        styles_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-top: 5px;")
        styles_header.addWidget(styles_label)
        self._current_style_display = QLineEdit()
        self._current_style_display.setReadOnly(True)
        self._current_style_display.setPlaceholderText(self._tr("No style selected"))
        self._current_style_display.setStyleSheet(
            "background-color: palette(base); border: 1px solid palette(mid); padding: 2px;"
        )
        styles_header.addWidget(self._current_style_display)
        styles_layout.addLayout(styles_header)
        self._styles_list = QListWidget()
        self._styles_list.setMaximumHeight(150)
        self._styles_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        styles_layout.addWidget(self._styles_list)
        main.addLayout(styles_layout)

        # Buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_box.rejected.connect(self.close)
        apply_btn = QPushButton(self._tr("Apply"))
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply_selection)
        self._button_box.addButton(apply_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        main.addWidget(self._button_box)

        # Connections
        self._search_edit.textChanged.connect(self._filter_items)
        self._themes_list.itemClicked.connect(self._on_theme_selected)
        self._themes_list.itemDoubleClicked.connect(self._on_theme_double_clicked)
        self._styles_list.itemClicked.connect(self._on_style_selected)
        self._styles_list.itemDoubleClicked.connect(self._on_style_double_clicked)

    def _install_no_scroll_filter(self) -> None:
        """Install utility NoScrollEventFilter on list and line edit widgets."""
        from utility.gui.qt.adapters.itemmodels.filters import NoScrollEventFilter

        no_scroll = NoScrollEventFilter(self)
        no_scroll.setup_filter(
            include_types=[QListWidget, QLineEdit],
            parent_widget=self,
        )

    def _populate_lists(self) -> None:
        """Populate theme and style lists and current displays."""
        if self._current_theme:
            self._current_theme_display.setText(self._current_theme)
        else:
            self._current_theme_display.clear()

        self._themes_list.clear()
        for theme_name in sorted(self._available_themes):
            item = QListWidgetItem(theme_name)
            item.setCheckState(Qt.CheckState.Unchecked)
            if self._current_theme and theme_name.lower() == self._current_theme.lower():
                item.setCheckState(Qt.CheckState.Checked)
                self._themes_list.setCurrentItem(item)
                self._themes_list.scrollToItem(item)
            self._themes_list.addItem(item)

        if self._current_style == "":
            self._current_style_display.setText(self._tr("Native (System Default)"))
        elif self._current_style:
            self._current_style_display.setText(self._current_style)
        else:
            self._current_style_display.clear()

        self._styles_list.clear()
        native_item = QListWidgetItem(self._tr("Native (System Default)"))
        native_item.setData(Qt.ItemDataRole.UserRole, "")
        native_item.setCheckState(Qt.CheckState.Unchecked)
        if self._current_style == "":
            native_item.setCheckState(Qt.CheckState.Checked)
            self._styles_list.setCurrentItem(native_item)
        self._styles_list.addItem(native_item)
        for style_name in sorted(self._available_styles):
            item = QListWidgetItem(style_name)
            item.setData(Qt.ItemDataRole.UserRole, style_name)
            item.setCheckState(Qt.CheckState.Unchecked)
            if self._current_style == style_name:
                item.setCheckState(Qt.CheckState.Checked)
                self._styles_list.setCurrentItem(item)
                self._styles_list.scrollToItem(item)
            self._styles_list.addItem(item)

    def _filter_items(self, text: str) -> None:
        """Filter theme and style lists by search text."""
        search = text.lower()
        for i in range(self._themes_list.count()):
            item = self._themes_list.item(i)
            if item:
                item.setHidden(search not in item.text().lower())
        for i in range(self._styles_list.count()):
            item = self._styles_list.item(i)
            if item:
                item.setHidden(search not in item.text().lower())

    def _on_theme_selected(self, item: QListWidgetItem) -> None:
        """Handle theme list selection."""
        for i in range(self._themes_list.count()):
            li = self._themes_list.item(i)
            if li:
                li.setCheckState(Qt.CheckState.Unchecked)
        item.setCheckState(Qt.CheckState.Checked)
        self._current_theme_display.setText(item.text())

    def _on_style_selected(self, item: QListWidgetItem) -> None:
        """Handle style list selection."""
        for i in range(self._styles_list.count()):
            li = self._styles_list.item(i)
            if li:
                li.setCheckState(Qt.CheckState.Unchecked)
        item.setCheckState(Qt.CheckState.Checked)
        self._current_style_display.setText(item.text())

    def _on_theme_double_clicked(self, item: QListWidgetItem) -> None:
        """Apply immediately on theme double-click."""
        self._on_theme_selected(item)
        self._apply_selection()

    def _on_style_double_clicked(self, item: QListWidgetItem) -> None:
        """Apply immediately on style double-click."""
        self._on_style_selected(item)
        self._apply_selection()

    def _apply_selection(self) -> None:
        """Emit theme_changed and/or style_changed for selected items."""
        selected_theme: str | None = None
        for i in range(self._themes_list.count()):
            item = self._themes_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected_theme = item.text()
                break
        selected_style: str | None = None
        for i in range(self._styles_list.count()):
            item = self._styles_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected_style = item.data(Qt.ItemDataRole.UserRole) or ""
                break
        if selected_theme is not None:
            self.theme_changed.emit(selected_theme)
        if selected_style is not None:
            self.style_changed.emit(selected_style)

    def update_current_selection(
        self,
        theme_name: str | None = None,
        style_name: str | None = None,
    ) -> None:
        """Update the current selection and refresh lists."""
        self._current_theme = theme_name
        self._current_style = style_name
        self._populate_lists()
