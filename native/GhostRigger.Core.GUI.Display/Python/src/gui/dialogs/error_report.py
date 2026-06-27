"""Structured error reporting for user-facing model I/O failures.

Replaces ad-hoc ``QMessageBox.critical(self, "Error", str(exc))`` calls with a
rich :class:`ErrorReport` value object and a :func:`show_error_report`
presenter. Each report carries a *category*, a jargon-free *user message*, an
optional *detail* (raw exception/traceback for a "Show Details" expander), and a
list of actionable *recovery actions* rendered as dialog buttons.

Typical usage::

    from src.gui.dialogs.error_report import ErrorReport, report_from_exception, show_error_report

    try:
        do_export(model, path)
    except Exception as exc:
        report = report_from_exception("export_error", exc, context="Exporting OBJ")
        show_error_report(self, report)
        self._log(f"OBJ export error: {exc}", "error")

The friendly-message mapping turns ``FileNotFoundError``, ``PermissionError``,
``struct.error``, ``ImportError``/``ModuleNotFoundError`` and
``subprocess.TimeoutExpired`` into plain-language explanations so the user is
never shown a raw traceback as the primary message.
"""

from __future__ import annotations

import struct
import subprocess
import traceback
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

__all__ = [
    "ErrorReport",
    "report_from_exception",
    "show_error_report",
    "show_exception",
]


# Friendly titles for each category, used for the dialog window title.
_CATEGORY_TITLES: dict[str, str] = {
    "import_error": "Import Failed",
    "export_error": "Export Failed",
    "parse_error": "Could Not Read File",
    "missing_dependency": "Missing Component",
    "file_not_found": "File Not Found",
    "permission_error": "Permission Denied",
    "subprocess_error": "External Tool Failed",
    "timeout_error": "Operation Timed Out",
    "io_error": "I/O Error",
    "unknown_error": "Something Went Wrong",
}


def _friendly_message_for(exc: BaseException) -> str:
    """Map a common exception type to a jargon-free user message."""

    if isinstance(exc, FileNotFoundError):
        return "The file could not be found. Check that the path is correct and the file still exists."
    if isinstance(exc, PermissionError):
        return "Permission denied. The file may be open in another program, or you may not have write access to that location."
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "A required component is missing. See the details below for installation instructions."
    if isinstance(exc, subprocess.TimeoutExpired):
        return "The operation took too long and was cancelled."
    if isinstance(exc, (struct.error, ValueError)):
        return "The file appears to be corrupted or in an unexpected format."
    if isinstance(exc, IsADirectoryError):
        return "A folder was selected where a file was expected."
    if isinstance(exc, OSError):
        return "The system reported an input/output error while accessing the file."
    return "An unexpected error occurred. See the details below."


def _category_for(exc: BaseException) -> str:
    """Pick the most specific category for an exception type."""

    if isinstance(exc, FileNotFoundError):
        return "file_not_found"
    if isinstance(exc, PermissionError):
        return "permission_error"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "missing_dependency"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout_error"
    if isinstance(exc, (struct.error, ValueError)):
        return "parse_error"
    if isinstance(exc, OSError):
        return "io_error"
    return "unknown_error"


@dataclass
class ErrorReport:
    """A structured, user-facing description of a recoverable failure.

    Attributes:
        category: One of ``_CATEGORY_TITLES`` keys (e.g. ``'export_error'``).
            Drives the dialog title; arbitrary strings are tolerated.
        user_message: Friendly, jargon-free explanation shown prominently.
        detail: Raw exception/traceback text for the "Show Details" expander.
        recovery_actions: Ordered ``(button_label, callback)`` tuples rendered as
            buttons. Callbacks are invoked (with exception guarding) when their
            button is clicked, before the dialog closes.
    """

    category: str
    user_message: str
    detail: str = ""
    recovery_actions: list[tuple[str, Callable[[], None]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Defensive copy so callers cannot mutate the stored action list.
        self.recovery_actions = list(self.recovery_actions or [])

    @property
    def title(self) -> str:
        """Human-readable dialog title derived from the category."""

        return _CATEGORY_TITLES.get(self.category, "Something Went Wrong")


def report_from_exception(
    category: str,
    exc: BaseException,
    *,
    context: str = "",
    user_message: Optional[str] = None,
    recovery_actions: Optional[Iterable[tuple[str, Callable[[], None]]]] = None,
) -> ErrorReport:
    """Build an :class:`ErrorReport` from a caught exception.

    ``category`` is used as-is for the title mapping and stored on the report.
    If ``user_message`` is omitted, a friendly message is derived from the
    exception type. The full formatted traceback is placed in ``detail``.
    """

    message = user_message or _friendly_message_for(exc)
    if context:
        message = f"{context}: {message}"
    # Preserve the original category the caller asked for (it may be more
    # specific than what we'd infer), but fall back to an inferred category if
    # the caller passed an empty/unknown one.
    resolved_category = category or _category_for(exc)
    detail_text = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    ).rstrip()
    return ErrorReport(
        category=resolved_category,
        user_message=message,
        detail=detail_text,
        recovery_actions=list(recovery_actions or []),
    )


def show_error_report(parent: QtWidgets.QWidget, report: ErrorReport) -> None:
    """Present ``report`` in a well-structured, window-modal dialog.

    Layout: prominent user message -> "Show Details" expander (collapsible,
    holding the raw traceback) -> recovery action buttons -> "Copy to
    Clipboard" + "Close" standard buttons. Recovery callbacks are guarded so a
    faulty recovery handler cannot crash the dialog.
    """

    dialog = QtWidgets.QDialog(parent)
    dialog.setObjectName("ErrorReportDialog")
    dialog.setWindowTitle(report.title)
    dialog.setWindowModality(QtCore.Qt.WindowModal)
    dialog.setMinimumWidth(460)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(20, 18, 20, 16)
    layout.setSpacing(12)

    # Header row: severity icon + user message.
    header = QtWidgets.QHBoxLayout()
    header.setSpacing(12)
    icon_label = QtWidgets.QLabel()
    style = getattr(dialog, "style", None)
    icon = QtWidgets.QStyle.SP_MessageBoxCritical
    if style is not None:
        icon_label.setPixmap(dialog.style().standardIcon(icon).pixmap(32, 32))
    icon_label.setFixedSize(32, 32)
    header.addWidget(icon_label, 0, QtCore.Qt.AlignTop)

    message_label = QtWidgets.QLabel(report.user_message)
    message_label.setWordWrap(True)
    message_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    header.addWidget(message_label, 1)
    layout.addLayout(header)

    # Collapsible detail expander.
    detail_button = QtWidgets.QPushButton("Show Details")
    detail_button.setCheckable(True)
    detail_button.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
    detail_edit = QtWidgets.QPlainTextEdit()
    detail_edit.setReadOnly(True)
    detail_edit.setPlainText(report.detail or "(no details available)")
    detail_edit.setMinimumHeight(140)
    detail_edit.setVisible(False)
    detail_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

    def _toggle_details(checked: bool) -> None:
        detail_edit.setVisible(checked)
        detail_button.setText("Hide Details" if checked else "Show Details")
        dialog.adjustSize()

    detail_button.toggled.connect(_toggle_details)
    layout.addWidget(detail_button, 0, QtCore.Qt.AlignLeft)
    layout.addWidget(detail_edit)

    # Recovery actions + standard buttons.
    button_row = QtWidgets.QHBoxLayout()
    for label, callback in report.recovery_actions:
        action_button = QtWidgets.QPushButton(label)

        def _invoke(checked: bool = False, cb: Callable[[], None] = callback) -> None:
            try:
                cb()
            except Exception:  # pragma: no cover - defensive: recovery must not crash UI
                traceback.print_exc()
            dialog.accept()

        action_button.clicked.connect(_invoke)
        button_row.addWidget(action_button)

    button_row.addStretch(1)

    copy_button = QtWidgets.QPushButton("Copy to Clipboard")
    close_button = QtWidgets.QPushButton("Close")
    close_button.setDefault(True)

    def _copy_to_clipboard() -> None:
        payload = f"{report.title}\n\n{report.user_message}\n\n{report.detail}"
        clip = QtWidgets.QApplication.clipboard()
        if clip is not None:
            clip.setText(payload)

    copy_button.clicked.connect(_copy_to_clipboard)
    close_button.clicked.connect(dialog.accept)
    button_row.addWidget(copy_button)
    button_row.addWidget(close_button)
    layout.addLayout(button_row)

    dialog.exec()


def show_exception(
    parent: QtWidgets.QWidget,
    category: str,
    exc: BaseException,
    *,
    context: str = "",
    user_message: Optional[str] = None,
    recovery_actions: Optional[Iterable[tuple[str, Callable[[], None]]]] = None,
) -> ErrorReport:
    """Convenience wrapper: build a report from ``exc`` and show it.

    Returns the constructed :class:`ErrorReport` so callers can log it or
    inspect its fields after dismissal.
    """

    report = report_from_exception(
        category,
        exc,
        context=context,
        user_message=user_message,
        recovery_actions=recovery_actions,
    )
    show_error_report(parent, report)
    return report
