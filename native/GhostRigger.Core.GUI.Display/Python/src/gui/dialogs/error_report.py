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
    "QtErrorReportDialog",
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

_RECOVERY_GUIDANCE: dict[str, str] = {
    "refresh_resources": "Scan the resource catalog again.",
    "browse_resources": "Open the Resource Browser and inspect available templates.",
    "choose_another": "Choose another resource or template.",
    "enter_resource_identity": "Enter the resource name and type explicitly.",
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
    subject: str = ""
    reason: str = ""
    searched_scopes: tuple[str, ...] = ()
    recovery_guidance: tuple[str, ...] = ()
    preservation_message: str = ""

    def __post_init__(self) -> None:
        # Defensive copy so callers cannot mutate the stored action list.
        self.recovery_actions = list(self.recovery_actions or [])
        self.subject = str(self.subject or "").strip()
        self.reason = str(self.reason or "").strip()
        self.searched_scopes = tuple(
            dict.fromkeys(
                str(scope).strip()
                for scope in self.searched_scopes
                if str(scope).strip()
            )
        )
        self.recovery_guidance = tuple(
            dict.fromkeys(
                str(guidance).strip()
                for guidance in self.recovery_guidance
                if str(guidance).strip()
            )
        )
        self.preservation_message = str(self.preservation_message or "").strip()

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

    failure = getattr(exc, "failure", None)
    failure_message = getattr(failure, "user_message", "") if failure is not None else ""
    message = user_message or failure_message or _friendly_message_for(exc)
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
        subject=getattr(failure, "subject", "") if failure is not None else "",
        reason=getattr(failure, "reason", "") if failure is not None else "",
        searched_scopes=tuple(getattr(failure, "searched_scopes", ()) or ()),
        recovery_guidance=tuple(
            _RECOVERY_GUIDANCE[key]
            for key in tuple(getattr(failure, "recovery_options", ()) or ())
            if key in _RECOVERY_GUIDANCE
        ),
        preservation_message=(
            "No project or source data was changed." if failure is not None else ""
        ),
    )


class QtErrorReportDialog(QtWidgets.QDialog):
    """Accessible error dialog with evidence, recovery, and preserved-state details."""

    def __init__(
        self,
        report: ErrorReport,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.report = report
        self.setObjectName("ErrorReportDialog")
        self.setWindowTitle(report.title)
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setMinimumWidth(500)
        self.setAccessibleName(report.title)
        self.setAccessibleDescription(self._accessible_description())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(
            self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxCritical).pixmap(32, 32)
        )
        icon_label.setFixedSize(32, 32)
        header.addWidget(icon_label, 0, QtCore.Qt.AlignTop)
        self.message_label = QtWidgets.QLabel(report.user_message)
        self.message_label.setTextFormat(QtCore.Qt.PlainText)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        header.addWidget(self.message_label, 1)
        layout.addLayout(header)

        evidence_rows: list[str] = []
        if report.subject:
            evidence_rows.append(f"Item: {report.subject}")
        if report.reason:
            evidence_rows.append(f"Reason: {report.reason}")
        if report.searched_scopes:
            evidence_rows.append(f"Searched: {'; '.join(report.searched_scopes)}")
        if evidence_rows:
            self.evidence_label = QtWidgets.QLabel("\n".join(evidence_rows))
            self.evidence_label.setObjectName("ErrorReportEvidence")
            self.evidence_label.setTextFormat(QtCore.Qt.PlainText)
            self.evidence_label.setWordWrap(True)
            self.evidence_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addWidget(self.evidence_label)

        if report.recovery_guidance:
            recovery_label = QtWidgets.QLabel(
                "What you can do:\n"
                + "\n".join(f"• {guidance}" for guidance in report.recovery_guidance)
            )
            recovery_label.setObjectName("ErrorReportRecovery")
            recovery_label.setTextFormat(QtCore.Qt.PlainText)
            recovery_label.setWordWrap(True)
            layout.addWidget(recovery_label)
        if report.preservation_message:
            preservation_label = QtWidgets.QLabel(report.preservation_message)
            preservation_label.setObjectName("ErrorReportPreservation")
            preservation_label.setTextFormat(QtCore.Qt.PlainText)
            preservation_label.setWordWrap(True)
            layout.addWidget(preservation_label)

        self.detail_button = QtWidgets.QPushButton("Show Details")
        self.detail_button.setCheckable(True)
        self.detail_button.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.detail_edit = QtWidgets.QPlainTextEdit()
        self.detail_edit.setReadOnly(True)
        self.detail_edit.setPlainText(report.detail or "(no details available)")
        self.detail_edit.setMinimumHeight(140)
        self.detail_edit.setVisible(False)
        self.detail_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.detail_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.detail_button, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(self.detail_edit)

        button_row = QtWidgets.QHBoxLayout()
        for label, callback in report.recovery_actions:
            action_button = QtWidgets.QPushButton(label)
            action_button.clicked.connect(
                lambda _checked=False, cb=callback: self._invoke_recovery(cb)
            )
            button_row.addWidget(action_button)
        button_row.addStretch(1)
        copy_button = QtWidgets.QPushButton("Copy to Clipboard")
        close_button = QtWidgets.QPushButton("Close")
        close_button.setDefault(True)
        copy_button.clicked.connect(self._copy_to_clipboard)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(copy_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _accessible_description(self) -> str:
        report = self.report
        rows = [report.user_message]
        if report.subject:
            rows.append(f"Item: {report.subject}")
        if report.reason:
            rows.append(f"Reason: {report.reason}")
        if report.searched_scopes:
            rows.append(f"Searched: {'; '.join(report.searched_scopes)}")
        rows.extend(report.recovery_guidance)
        if report.preservation_message:
            rows.append(report.preservation_message)
        return " ".join(rows)

    def _toggle_details(self, checked: bool) -> None:
        self.detail_edit.setVisible(checked)
        self.detail_button.setText("Hide Details" if checked else "Show Details")
        self.adjustSize()

    def _invoke_recovery(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:  # pragma: no cover - recovery must not crash the dialog
            traceback.print_exc()
        self.accept()

    def _copy_to_clipboard(self) -> None:
        report = self.report
        payload = (
            f"{report.title}\n\n{report.user_message}\n\n"
            f"{self._accessible_description()}\n\n{report.detail}"
        )
        clip = QtWidgets.QApplication.clipboard()
        if clip is not None:
            clip.setText(payload)


def show_error_report(parent: QtWidgets.QWidget, report: ErrorReport) -> None:
    """Present ``report`` in a structured, window-modal dialog."""

    dialog = QtErrorReportDialog(report, parent)
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
