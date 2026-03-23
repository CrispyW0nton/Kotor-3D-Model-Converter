"""Common QMessageBox helper functions for consistent UI messaging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget as QWidgetType


def _coerce_parent(parent: object | None) -> QWidget | None:
    """Return a QWidget parent when available.

    Several unit tests exercise helper code with lightweight stand-ins that are
    not actual widgets. Falling back to ``None`` keeps the helpers safe in those
    cases while still using the provided widget parent in normal UI flows.
    """

    return parent if isinstance(parent, QWidget) else None
from qtpy.QtWidgets import QMessageBox, QWidget


def show_info_message(
    title: str,
    text: str,
    parent: QWidgetType | None = None,
) -> None:
    """Show an informational message box."""
    QMessageBox.information(_coerce_parent(parent), title, text, QMessageBox.StandardButton.Ok)


def show_warning_message(
    title: str,
    text: str,
    parent: QWidgetType | None = None,
) -> None:
    """Show a warning message box."""
    QMessageBox.warning(_coerce_parent(parent), title, text, QMessageBox.StandardButton.Ok)


def show_error_message(
    title: str,
    text: str,
    parent: QWidgetType | None = None,
) -> None:
    """Show an error message box."""
    QMessageBox.critical(_coerce_parent(parent), title, text, QMessageBox.StandardButton.Ok)


def ask_question(
    title: str,
    text: str,
    parent: QWidgetType | None = None,
) -> QMessageBox.StandardButton:
    """Show a question dialog and return the user's response."""
    return QMessageBox.question(
        _coerce_parent(parent),
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
