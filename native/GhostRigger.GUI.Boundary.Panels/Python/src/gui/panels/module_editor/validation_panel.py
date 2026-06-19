"""Validation issue panel for the Module Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleValidationPanel(QtWidgets.QTableWidget):
    issueActivated = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.setObjectName("ModuleValidationPanel")
        self.setAccessibleName("Map Studio validation issues")
        self.setAccessibleDescription(
            "Shows blocking issues, warnings, affected items, and suggested fixes before Map Studio export or game proof."
        )
        self.setToolTip(
            "Validation workflow: fix blocking issues first. Double-click an issue to focus its item, then validate again before staging or install."
        )
        self.setHorizontalHeaderLabels(["Severity", "Message", "Item", "Suggested Fix"])
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.itemDoubleClicked.connect(self._activated)
        self.set_issues(())

    def set_issues(self, issues) -> None:
        self.setRowCount(0)
        issue_list = list(issues or ())
        if not issue_list:
            self._add_empty_state_row()
            return
        for issue in issue_list:
            row = self.rowCount()
            self.insertRow(row)
            values = [issue.severity, issue.message, issue.item_id, issue.suggested_fix]
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, issue.item_id)
                item.setToolTip(self._issue_tooltip(issue))
                self.setItem(row, column, item)

    def _activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        item_id = str(item.data(QtCore.Qt.UserRole) or "")
        if item_id:
            self.issueActivated.emit(item_id)

    def _add_empty_state_row(self) -> None:
        self.insertRow(0)
        values = [
            "OK",
            "No validation issues are currently listed.",
            "",
            "Validate again after edits; export/install still requires staged output and in-game proof before game-ready.",
        ]
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, "")
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            item.setToolTip(
                "No validation issues are currently listed. Continue only after readiness, staged export, install, and game proof are satisfied."
            )
            self.setItem(0, column, item)

    @staticmethod
    def _issue_tooltip(issue) -> str:
        severity = str(getattr(issue, "severity", "") or "")
        message = str(getattr(issue, "message", "") or "")
        item_id = str(getattr(issue, "item_id", "") or "")
        suggested_fix = str(getattr(issue, "suggested_fix", "") or "")
        parts = [part for part in (f"Severity: {severity}", message, f"Item: {item_id}", f"Fix: {suggested_fix}") if part]
        return "\n".join(parts)
