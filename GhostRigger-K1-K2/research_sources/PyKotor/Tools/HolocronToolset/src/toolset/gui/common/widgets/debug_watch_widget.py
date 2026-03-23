"""Debug Watch Widget - Shows watch expressions during debugging."""

from __future__ import annotations

from qtpy.QtWidgets import (
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)


class DebugWatchWidget(QWidget):
    """Widget that displays and manages watch expressions during debugging."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._watch_expressions: list[str] = []
        self._watch_values: dict[str, str] = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        from toolset.uic.qtpy.widgets.debug_watch_widget import Ui_DebugWatchWidget

        self.ui = Ui_DebugWatchWidget()
        self.ui.setupUi(self)

        # Get references to UI elements
        self.expression_input = self.ui.expressionInput
        self.add_button = self.ui.addButton
        self.table = self.ui.table

        # Configure table
        self.table.setHorizontalHeaderLabels(["Expression", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # Localization
        from toolset.gui.common.localization import translate as tr

        self.expression_input.setPlaceholderText(tr("Enter expression to watch..."))
        self.add_button.setText(tr("Add Watch"))

        # Connect signals
        self.expression_input.returnPressed.connect(self._add_watch)
        self.add_button.clicked.connect(self._add_watch)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _add_watch(self):
        """Add a watch expression."""
        expression = self.expression_input.text().strip()
        if expression and expression not in self._watch_expressions:
            self._watch_expressions.append(expression)
            self._watch_values[expression] = ""
            self._update_table()
            self.expression_input.clear()

    def _remove_watch(self, expression: str):
        """Remove a watch expression."""
        if expression in self._watch_expressions:
            self._watch_expressions.remove(expression)
            if expression in self._watch_values:
                del self._watch_values[expression]
            self._update_table()

    def _show_context_menu(self, position):
        """Show context menu for watch table."""
        item = self.ui.table.itemAt(position)
        if item is None:
            return

        row = item.row()
        if row < len(self._watch_expressions):
            expression = self._watch_expressions[row]

            from qtpy.QtWidgets import QMenu

            from toolset.gui.common.localization import translate as tr

            menu = QMenu(self)
            remove_action = menu.addAction(tr("Remove Watch"))
            if remove_action:
                remove_action.triggered.connect(lambda: self._remove_watch(expression))
                menu.exec(self.ui.table.mapToGlobal(position))

    def _update_table(self):
        """Update the watch expressions table."""
        self.ui.table.setRowCount(0)

        for expression in self._watch_expressions:
            row = self.ui.table.rowCount()
            self.ui.table.insertRow(row)

            # Expression
            expr_item = QTableWidgetItem(expression)
            self.ui.table.setItem(row, 0, expr_item)

            # Value
            value = self._watch_values.get(expression, "Not evaluated")
            value_item = QTableWidgetItem(str(value))
            self.ui.table.setItem(row, 1, value_item)

        # Resize columns to fit content
        self.ui.table.resizeColumnsToContents()

    def update_watch_values(self, watch_values: dict[str, str]):
        """Update watch expression values.

        Args:
        ----
            watch_values: dict mapping expressions to their evaluated values
        """
        self._watch_values.update(watch_values)
        self._update_table()

    def get_watch_expressions(self) -> list[str]:
        """Get list of watch expressions."""
        return self._watch_expressions.copy()

    def clear(self):
        """Clear all watch expressions."""
        self._watch_expressions.clear()
        self._watch_values.clear()
        self.ui.table.setRowCount(0)
