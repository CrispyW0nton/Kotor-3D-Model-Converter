from __future__ import annotations

import json

from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import QSettings, Qt, Signal
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QColor, QKeyEvent


class SearchFilterWidget(QWidget):
    """A custom search/filter widget with clear, search, and history navigation buttons.

    Features:
    - X button to clear text
    - Magnifying glass button to perform search
    - Up/Down arrows to navigate search history
    - Persistent history across app restarts
    - Only stores full searches (not partial character changes)
    """

    MAX_HISTORY: ClassVar[int] = 50

    # Signals
    textChanged: Signal = Signal(str)  # Emitted when text changes
    searchRequested: Signal = Signal(str)  # Emitted when search button is clicked or Enter is pressed
    textEdited: Signal = Signal(str)  # Emitted when user types (for backward compatibility)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        history_key: str | None = None,
    ):
        """Initialize the search filter widget.

        Args:
        ----
            parent: Parent widget
            history_key: Unique key for storing search history. If None, auto-generates from widget context.
        """
        super().__init__(parent)

        # Auto-generate history key from widget context if not provided
        if history_key is None:
            widget_name = self.objectName() or "searchEdit"
            parent_class = parent.__class__.__name__ if parent else "Widget"
            self._history_key: str = f"{parent_class}_{widget_name}"
        else:
            self._history_key = history_key
        self._history: list[str] = []
        self._history_index: int = -1
        self._last_search_text: str = ""
        self._is_navigating_history: bool = False

        self._setup_ui()
        self._load_history()
        self._setup_signals()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main line edit
        self.line_edit: QLineEdit = QLineEdit(self)
        self.line_edit.setPlaceholderText("search...")
        self.line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Create icon buttons using standard icons
        self._up_button: QPushButton = self._create_icon_button("▲", "Previous search (Up)")
        self._down_button: QPushButton = self._create_icon_button("▼", "Next search (Down)")
        self._search_button: QPushButton = self._create_icon_button("🔍", "Search")
        self._clear_button: QPushButton = self._create_icon_button("✕", "Clear")

        # Add buttons to layout
        layout.addWidget(self.line_edit)
        layout.addWidget(self._up_button)
        layout.addWidget(self._down_button)
        layout.addWidget(self._search_button)
        layout.addWidget(self._clear_button)

        # Style the widget
        self._apply_styling()

    def _create_icon_button(
        self,
        text: str,
        tooltip: str,
    ) -> QPushButton:
        """Create an icon button with custom styling.

        Args:
        ----
            text: Button text/icon
            tooltip: Tooltip text

        Returns:
        -------
            Configured QPushButton
        """
        button = QPushButton(text, self)
        button.setToolTip(tooltip)
        button.setFlat(True)
        button.setFixedSize(24, 24)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        # Style the button using palette colors
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: palette(windowText);
                font-size: 11px;
                padding: 2px;
                min-width: 20px;
            }
            QPushButton:hover {
                background-color: palette(button);
                border-radius: 3px;
                color: palette(buttonText);
            }
            QPushButton:pressed {
                background-color: palette(mid);
                color: palette(buttonText);
            }
        """)

        return button

    def _apply_styling(self):
        """Apply custom styling to the widget using palette colors."""
        app = QApplication.instance()
        assert isinstance(app, QApplication), f"QApplication instance is required, got {app.__class__.__name__}"
        palette: QPalette = app.palette()

        # Get palette colors
        base_color: QColor = palette.color(QPalette.ColorRole.Base)
        text_color: QColor = palette.color(QPalette.ColorRole.Text)
        border_color: QColor = palette.color(QPalette.ColorRole.Mid)
        highlight_color: QColor = palette.color(QPalette.ColorRole.Highlight)
        placeholder_color: QColor = palette.color(QPalette.ColorRole.PlaceholderText)
        if not placeholder_color.isValid():
            # Fallback if PlaceholderText is not available
            placeholder_color = palette.color(QPalette.ColorRole.Dark)

        self.setStyleSheet(f"""
            SearchFilterWidget QLineEdit {{
                background-color: {base_color.name()};
                border: 1px solid {border_color.name()};
                border-radius: 4px;
                padding: 4px 8px;
                color: {text_color.name()};
                selection-background-color: {highlight_color.name()};
            }}
            SearchFilterWidget QLineEdit:focus {{
                border: 1px solid {highlight_color.name()};
                outline: none;
            }}
            SearchFilterWidget QLineEdit::placeholder {{
                color: {placeholder_color.name()};
            }}
        """)

    def _setup_signals(self):
        """Set up signal connections."""
        # Line edit signals
        self.line_edit.textChanged.connect(self._on_text_changed)
        self.line_edit.returnPressed.connect(self._on_search_requested)
        self.line_edit.textEdited.connect(self._on_text_edited)

        # Button signals
        self._clear_button.clicked.connect(self._on_clear_clicked)
        self._search_button.clicked.connect(self._on_search_requested)
        self._up_button.clicked.connect(self._on_history_up)
        self._down_button.clicked.connect(self._on_history_down)

    def _on_text_changed(self, text: str):
        """Handle text change."""
        if not self._is_navigating_history:
            self.textChanged.emit(text)
            self.textEdited.emit(text)  # For backward compatibility

    def _on_text_edited(self, text: str):
        """Handle text edit (user typing)."""
        if not self._is_navigating_history:
            self.textEdited.emit(text)

    def _on_clear_clicked(self):
        """Handle clear button click."""
        self.line_edit.clear()
        self.line_edit.setFocus()

    def _on_search_requested(self):
        """Handle search button click or Enter key."""
        text = self.line_edit.text().strip()
        if text and text != self._last_search_text:
            # Add to history if it's a new search
            self._add_to_history(text)
            self._last_search_text = text
        self.searchRequested.emit(text)

    def _on_history_up(self):
        """Navigate to previous search in history."""
        if not self._history:
            return

        self._is_navigating_history = True
        if self._history_index > 0:
            self._history_index -= 1
        elif self._history_index == -1:
            # Start from the end
            self._history_index = len(self._history) - 1

        self.line_edit.setText(self._history[self._history_index])
        self.line_edit.selectAll()
        self._is_navigating_history = False

    def _on_history_down(self):
        """Navigate to next search in history."""
        if not self._history:
            return

        self._is_navigating_history = True
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
        else:
            # Go back to current text or empty
            self._history_index = -1
            self.line_edit.setText("")

        if self._history_index >= 0:
            self.line_edit.setText(self._history[self._history_index])
            self.line_edit.selectAll()
        self._is_navigating_history = False

    def _add_to_history(self, text: str):
        """Add a search term to history.

        Args:
        ----
            text: Search text to add
        """
        # Remove if already exists (to move to front)
        if text in self._history:
            self._history.remove(text)

        # Add to front
        self._history.insert(0, text)

        # Limit history size
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[: self.MAX_HISTORY]

        # Reset history index
        self._history_index = -1

        # Save to persistent storage
        self._save_history()

    def _load_history(self):
        """Load search history from persistent storage."""
        settings = QSettings()
        history_data = settings.value(f"search_history/{self._history_key}", "")

        if history_data:
            try:
                if isinstance(history_data, str):
                    self._history = json.loads(history_data)
                elif isinstance(history_data, list):
                    self._history = history_data
                else:
                    self._history = []
            except (json.JSONDecodeError, TypeError):
                self._history = []
        else:
            self._history = []

        # Ensure it's a list of strings
        self._history = [str(item) for item in self._history if item]

    def _save_history(self):
        """Save search history to persistent storage."""
        settings = QSettings()
        settings.setValue(f"search_history/{self._history_key}", json.dumps(self._history))

    # Public API methods for compatibility with QLineEdit
    def text(self) -> str:
        """Get the current text."""
        return self.line_edit.text()

    def setText(self, text: str):
        """Set the text."""
        self.line_edit.setText(text)

    def setPlaceholderText(self, text: str):
        """Set placeholder text."""
        self.line_edit.setPlaceholderText(text)

    def clear(self):
        """Clear the text."""
        self.line_edit.clear()

    def setFocus(self):
        """Set focus to the line edit."""
        self.line_edit.setFocus()

    def selectAll(self):
        """Select all text."""
        self.line_edit.selectAll()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        # Allow Up/Down arrow keys to navigate history when focused
        if event.key() == Qt.Key.Key_Up:
            self._on_history_up()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Down:
            self._on_history_down()
            event.accept()
            return

        super().keyPressEvent(event)
