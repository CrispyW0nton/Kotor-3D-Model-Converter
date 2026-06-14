"""Validation issue panel for the Module Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleValidationPanel(QtWidgets.QTableWidget):
    issueActivated = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.setObjectName("ModuleValidationPanel")
        self.setHorizontalHeaderLabels(["Severity", "Message", "Item", "Suggested Fix"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.itemDoubleClicked.connect(self._activated)

    def set_issues(self, issues) -> None:
        self.setRowCount(0)
        for issue in issues:
            row = self.rowCount()
            self.insertRow(row)
            values = [issue.severity, issue.message, issue.item_id, issue.suggested_fix]
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, issue.item_id)
                self.setItem(row, column, item)

    def _activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        item_id = str(item.data(QtCore.Qt.UserRole) or "")
        if item_id:
            self.issueActivated.emit(item_id)
