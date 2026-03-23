"""VS Code-style inline find/replace widget for code editors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import qtpy

from qtpy.QtCore import (
    Qt,
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtWidgets import QWidget

from toolset.gui.common.localization import translate as tr

if TYPE_CHECKING:
    from qtpy.QtGui import QKeyEvent
    from qtpy.QtWidgets import QCheckBox, QLineEdit, QPushButton

if qtpy.QT5:
    pass  # pyright: ignore[reportAttributeAccessIssue]
elif qtpy.QT6:
    pass  # pyright: ignore[reportAttributeAccessIssue]


class FindReplaceWidget(QWidget):
    """VS Code-style inline find/replace bar that appears above the editor."""

    find_requested = Signal(str, bool, bool, bool)  # text, case_sensitive, whole_words, regex
    replace_requested = Signal(str, str, bool, bool, bool)  # find, replace, case_sensitive, whole_words, regex
    replace_all_requested = Signal(str, str, bool, bool, bool)
    close_requested = Signal()
    find_next_requested = Signal()
    find_previous_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        """Set up the UI components."""
        from toolset.uic.qtpy.widgets.find_replace_widget import Ui_FindReplaceWidget

        self.ui: Ui_FindReplaceWidget = Ui_FindReplaceWidget()
        self.ui.setupUi(self)

        # Get references to UI elements
        self.find_input: QLineEdit = self.ui.findInput
        self.replace_input: QLineEdit = self.ui.replaceInput
        self.prev_button: QPushButton = self.ui.prevButton
        self.next_button: QPushButton = self.ui.nextButton
        self.replace_button: QPushButton = self.ui.replaceButton
        self.replace_all_button: QPushButton = self.ui.replaceAllButton
        self.close_button: QPushButton = self.ui.closeButton
        self.case_sensitive_check: QCheckBox = self.ui.caseSensitiveCheck
        self.whole_words_check: QCheckBox = self.ui.wholeWordsCheck
        self.regex_check: QCheckBox = self.ui.regexCheck

        # Apply localization
        self.ui.findLabel.setText(tr("Find:"))
        self.find_input.setPlaceholderText(tr("Find..."))
        self.ui.replaceLabel.setText(tr("Replace:"))
        self.replace_input.setPlaceholderText(tr("Replace..."))
        self.prev_button.setToolTip(tr("Find Previous (Shift+F3)"))
        self.next_button.setToolTip(tr("Find Next (F3)"))
        self.replace_button.setText(tr("Replace"))
        self.replace_all_button.setText(tr("Replace All"))
        self.close_button.setToolTip(tr("Close (Escape)"))
        self.case_sensitive_check.setToolTip(tr("Match Case"))
        self.whole_words_check.setToolTip(tr("Match Whole Word"))
        self.regex_check.setToolTip(tr("Use Regular Expression"))

        self._connect_signals()

        # Initially disable replace buttons
        self.replace_button.setEnabled(False)
        self.replace_all_button.setEnabled(False)

        # Initially hide replace components
        self._set_replace_widgets_visible(False)

        # Style
        self.setStyleSheet("""
            FindReplaceWidget {
                background-color: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QLineEdit {
                padding: 4px;
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
            QPushButton {
                padding: 4px 8px;
                border: 1px solid palette(mid);
                border-radius: 3px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: palette(light);
            }
            QPushButton:disabled {
                color: palette(disabledText);
            }
            QCheckBox {
                spacing: 4px;
            }
        """)

        self._show_replace: bool = False

    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self.find_input.returnPressed.connect(self._on_find_next)
        self.find_input.textChanged.connect(self._on_find_text_changed)
        self.replace_input.returnPressed.connect(self._on_replace_next)
        self.replace_input.textChanged.connect(self._on_replace_text_changed)

        for button, handler in (
            (self.prev_button, self._on_find_previous),
            (self.next_button, self._on_find_next),
            (self.replace_button, self._on_replace),
            (self.replace_all_button, self._on_replace_all),
            (self.close_button, self.hide),
        ):
            button.clicked.connect(handler)

        for checkbox in (self.case_sensitive_check, self.whole_words_check, self.regex_check):
            checkbox.toggled.connect(self._on_options_changed)

    def _set_replace_widgets_visible(self, visible: bool) -> None:
        """Show/hide replace-related widgets while keeping find controls visible."""
        self.ui.replaceLabel.setVisible(visible)
        self.replace_input.setVisible(visible)
        self.replace_button.setVisible(visible)
        self.replace_all_button.setVisible(visible)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.close_requested.emit()
        elif event.key() == Qt.Key.Key_F3:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._on_find_previous()
            else:
                self._on_find_next()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_H:
            self.toggle_replace()
        else:
            super().keyPressEvent(event)

    def show_find(self, text: str | None = None):
        """Show the find widget."""
        self._show_replace = False
        self._set_replace_widgets_visible(False)
        self.show()
        if text:
            self.find_input.setText(text)
            self.find_input.selectAll()
        else:
            # Try to get selected text from editor
            self.find_input.selectAll()
        self.find_input.setFocus()

    def show_replace(self, text: str | None = None):
        """Show the find and replace widget."""
        self._show_replace = True
        self._set_replace_widgets_visible(True)
        self.show()
        if text:
            self.find_input.setText(text)
            self.find_input.selectAll()
        else:
            self.find_input.selectAll()
        self.find_input.setFocus()

    def toggle_replace(self):
        """Toggle between find and replace modes."""
        if self._show_replace:
            self.show_find()
        else:
            self.show_replace()

    def _on_find_text_changed(self):
        """Handle find text changes."""
        has_text = bool(self.find_input.text())
        self.next_button.setEnabled(has_text)  # or .setDisabled(not has_text)
        self.prev_button.setEnabled(has_text)  # or .setDisabled(not has_text)
        self.replace_button.setEnabled(has_text)  # or .setDisabled(not has_text)
        self._update_replace_all_button()

        # Auto-search as user types
        if has_text:
            self._on_find_next()

    def _on_replace_text_changed(self):
        """Handle replace text changes."""
        self._update_replace_all_button()

    def _update_replace_all_button(self):
        """Update the replace all button enabled state."""
        has_find_text = bool(self.find_input.text())
        has_replace_text = bool(self.replace_input.text())
        self.replace_all_button.setEnabled(has_find_text and has_replace_text)  # or .setDisabled(not has_find_text or not has_replace_text)

    def _on_find_next(self):
        """Emit find next signal."""
        text = self.find_input.text()
        if text:
            self.find_requested.emit(
                text,
                self.case_sensitive_check.isChecked(),
                self.whole_words_check.isChecked(),
                self.regex_check.isChecked(),
            )
            self.find_next_requested.emit()

    def _on_find_previous(self):
        """Emit find previous signal."""
        text = self.find_input.text()
        if text:
            self.find_requested.emit(
                text,
                self.case_sensitive_check.isChecked(),
                self.whole_words_check.isChecked(),
                self.regex_check.isChecked(),
            )
            self.find_previous_requested.emit()

    def _on_replace(self):
        """Emit replace signal."""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if find_text and replace_text:
            self.replace_requested.emit(
                find_text,
                replace_text,
                self.case_sensitive_check.isChecked(),
                self.whole_words_check.isChecked(),
                self.regex_check.isChecked(),
            )

    def _on_replace_next(self):
        """Emit replace signal and then find next."""
        # First replace the current match
        self._on_replace()
        # Then find the next occurrence
        self._on_find_next()

    def _on_replace_all(self):
        """Emit replace all signal."""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if find_text and replace_text:
            self.replace_all_requested.emit(
                find_text,
                replace_text,
                self.case_sensitive_check.isChecked(),
                self.whole_words_check.isChecked(),
                self.regex_check.isChecked(),
            )

    def _on_options_changed(self):
        """Handle option checkbox changes."""
        if self.find_input.text():
            self._on_find_next()
