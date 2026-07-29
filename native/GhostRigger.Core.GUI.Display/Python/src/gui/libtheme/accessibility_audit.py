"""Reusable accessibility and visual-legibility diagnostics for Qt surfaces."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from .layout_applier import fit_top_level_window_to_available_screen
from .theme_model import Theme

NORMAL_TEXT_CONTRAST = 4.5
UI_BOUNDARY_CONTRAST = 3.0
MINIMUM_TARGET_SIZE = 24
FREQUENT_TARGET_SIZE = 32
_QT_UNBOUNDED_WIDGET_SIZE = 16777215


@dataclass(frozen=True, slots=True)
class AccessibilityIssue:
    """One stable, actionable accessibility finding."""

    severity: str
    code: str
    location: str
    message: str
    remediation: str


@dataclass(frozen=True, slots=True)
class AccessibilityReport:
    """Results from one widget-tree and optional theme audit."""

    surface: str
    controls_scanned: int
    issues: tuple[AccessibilityIssue, ...]

    @property
    def blocking_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def passed(self) -> bool:
        return not self.issues

    def summary(self) -> str:
        if self.passed:
            return f"{self.surface}: {self.controls_scanned} controls checked; no accessibility issues found."
        return (
            f"{self.surface}: {self.controls_scanned} controls checked; "
            f"{self.blocking_count} blocking and {self.warning_count} warning issues."
        )

    def as_text(self) -> str:
        lines = [self.summary()]
        for issue in self.issues:
            lines.extend(
                (
                    "",
                    f"[{issue.severity.upper()}] {issue.code} — {issue.location}",
                    issue.message,
                    f"Fix: {issue.remediation}",
                )
            )
        return "\n".join(lines)


_TEXT_CONTRAST_PAIRS: tuple[tuple[str, str, float, str], ...] = (
    ("window.text", "window.background", NORMAL_TEXT_CONTRAST, "window text"),
    ("text.primary", "panel.background", NORMAL_TEXT_CONTRAST, "primary panel text"),
    ("text.secondary", "panel.background", NORMAL_TEXT_CONTRAST, "secondary panel text"),
    ("panel.headerText", "panel.headerBackground", NORMAL_TEXT_CONTRAST, "panel headings"),
    ("button.text", "button.background", NORMAL_TEXT_CONTRAST, "button labels"),
    ("input.text", "input.background", NORMAL_TEXT_CONTRAST, "input text"),
    ("table.text", "table.background", NORMAL_TEXT_CONTRAST, "table text"),
    ("tree.text", "tree.background", NORMAL_TEXT_CONTRAST, "tree text"),
    ("tab.text", "tab.background", NORMAL_TEXT_CONTRAST, "inactive tab labels"),
    ("tab.selectedText", "tab.selectedBackground", NORMAL_TEXT_CONTRAST, "selected tab labels"),
    ("selection.text", "selection.background", NORMAL_TEXT_CONTRAST, "selected text"),
    ("input.focusBorder", "input.background", UI_BOUNDARY_CONTRAST, "keyboard focus boundary"),
)


def _rgb_components(value: str) -> tuple[float, float, float]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) not in (6, 8):
        raise ValueError(f"'{value}' is not a six- or eight-digit hexadecimal color")
    return tuple(int(raw[index:index + 2], 16) / 255.0 for index in (0, 2, 4))


def relative_luminance(value: str) -> float:
    """Return WCAG relative luminance for a hexadecimal sRGB color."""

    linear = []
    for component in _rgb_components(value):
        linear.append(
            component / 12.92
            if component <= 0.04045
            else ((component + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two hexadecimal colors."""

    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def audit_theme_contrast(theme: Theme) -> tuple[AccessibilityIssue, ...]:
    """Check the semantic color pairs used for readable text and focus state."""

    issues: list[AccessibilityIssue] = []
    for foreground_token, background_token, required, purpose in _TEXT_CONTRAST_PAIRS:
        foreground = theme.color(foreground_token)
        background = theme.color(background_token)
        try:
            ratio = contrast_ratio(foreground, background)
        except ValueError as exc:
            issues.append(
                AccessibilityIssue(
                    "error",
                    "theme.invalid_color",
                    theme.name,
                    f"Could not evaluate {purpose}: {exc}.",
                    "Use a six- or eight-digit hexadecimal value for both theme tokens.",
                )
            )
            continue
        if ratio + 1e-9 < required:
            issues.append(
                AccessibilityIssue(
                    "error",
                    "theme.low_contrast",
                    theme.name,
                    (
                        f"{foreground_token} on {background_token} is {ratio:.2f}:1 for "
                        f"{purpose}; at least {required:.1f}:1 is required."
                    ),
                    f"Adjust {foreground_token} or {background_token} until the required ratio is met.",
                )
            )
    return tuple(issues)


def _object_location(widget: QtWidgets.QWidget) -> str:
    parts: list[str] = []
    current: QtCore.QObject | None = widget
    while current is not None and len(parts) < 4:
        name = str(current.objectName() or "").strip()
        if name:
            parts.append(name)
        current = current.parent()
    if parts:
        return " / ".join(reversed(parts))
    return type(widget).__name__


def _plain_button_text(widget: QtWidgets.QAbstractButton) -> str:
    return str(widget.text() or "").replace("&&", "\0").replace("&", "").replace("\0", "&").strip()


def _has_label_buddy(root: QtWidgets.QWidget, widget: QtWidgets.QWidget) -> bool:
    return any(label.buddy() is widget for label in root.findChildren(QtWidgets.QLabel))


def _meaningful_name(root: QtWidgets.QWidget, widget: QtWidgets.QWidget) -> str:
    explicit = str(widget.accessibleName() or "").strip()
    if explicit:
        return explicit
    if isinstance(widget, QtWidgets.QAbstractButton):
        return _plain_button_text(widget)
    if _has_label_buddy(root, widget):
        return "label buddy"
    return ""


def _effective_target_size(widget: QtWidgets.QWidget) -> QtCore.QSize:
    hint = widget.sizeHint()
    minimum = widget.minimumSize()
    maximum = widget.maximumSize()
    width = max(hint.width(), minimum.width())
    height = max(hint.height(), minimum.height())
    if maximum.width() < _QT_UNBOUNDED_WIDGET_SIZE:
        width = min(width, maximum.width())
    if maximum.height() < _QT_UNBOUNDED_WIDGET_SIZE:
        height = min(height, maximum.height())
    return QtCore.QSize(max(0, width), max(0, height))


def _is_audited_interactive(widget: QtWidgets.QWidget) -> bool:
    return isinstance(
        widget,
        (
            QtWidgets.QAbstractButton,
            QtWidgets.QAbstractItemView,
            QtWidgets.QAbstractSpinBox,
            QtWidgets.QComboBox,
            QtWidgets.QLineEdit,
            QtWidgets.QSlider,
            QtWidgets.QDial,
        ),
    )


def _raise_dimension_floor(widget: QtWidgets.QWidget, required: int) -> None:
    widget.setMinimumHeight(max(required, widget.minimumHeight()))
    if widget.maximumHeight() < required:
        widget.setMaximumHeight(required)


class _AccessibleControlEventFilter(QtCore.QObject):
    """Apply minimum logical hit targets to controls created after layout."""

    _EVENTS = {
        QtCore.QEvent.Type.Polish,
        QtCore.QEvent.Type.Show,
    }

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() not in self._EVENTS:
            return False
        if isinstance(watched, QtWidgets.QWidget):
            try:
                self.apply_defaults(watched)
            except RuntimeError:
                # A queued Show event can outlive a widget's C++ instance.
                pass
        return False

    @staticmethod
    def apply_defaults(widget: QtWidgets.QWidget) -> None:
        if bool(widget.property("ghostAccessibilityTargetIgnore")):
            return
        frequent = bool(widget.property("ghostFrequentAction"))
        required = FREQUENT_TARGET_SIZE if frequent else MINIMUM_TARGET_SIZE
        if isinstance(
            widget,
            (
                QtWidgets.QAbstractButton,
                QtWidgets.QAbstractSpinBox,
                QtWidgets.QComboBox,
                QtWidgets.QLineEdit,
                QtWidgets.QSlider,
                QtWidgets.QDial,
            ),
        ):
            _raise_dimension_floor(widget, required)
        if isinstance(widget, QtWidgets.QAbstractButton) and (
            frequent or (not widget.icon().isNull() and not _plain_button_text(widget))
        ):
            widget.setMinimumWidth(max(required, widget.minimumWidth()))
            if widget.maximumWidth() < required:
                widget.setMaximumWidth(required)
        if isinstance(widget, (QtWidgets.QTreeView, QtWidgets.QListView)):
            icon_size = widget.iconSize()
            widget.setIconSize(
                QtCore.QSize(
                    max(MINIMUM_TARGET_SIZE, icon_size.width()),
                    max(MINIMUM_TARGET_SIZE, icon_size.height()),
                )
            )
        if isinstance(widget, QtWidgets.QTableView):
            widget.verticalHeader().setMinimumSectionSize(MINIMUM_TARGET_SIZE)
            widget.verticalHeader().setDefaultSectionSize(
                max(MINIMUM_TARGET_SIZE, widget.verticalHeader().defaultSectionSize())
            )


def install_accessibility_defaults(app: QtWidgets.QApplication | None = None) -> None:
    """Install one idempotent event filter for late-created Qt controls."""

    application = app or QtWidgets.QApplication.instance()
    if application is None:
        return
    event_filter = getattr(application, "_ghost_accessibility_defaults_filter", None)
    if event_filter is None:
        event_filter = _AccessibleControlEventFilter(application)
        application.installEventFilter(event_filter)
        setattr(application, "_ghost_accessibility_defaults_filter", event_filter)
    for widget in application.allWidgets():
        try:
            event_filter.apply_defaults(widget)
        except RuntimeError:
            # Qt may destroy internal widgets while allWidgets() is iterated.
            continue


class AccessibilityAuditor:
    """Audit a live Qt surface without mutating it."""

    def audit_widget_tree(
        self,
        root: QtWidgets.QWidget,
        *,
        theme: Theme | None = None,
    ) -> AccessibilityReport:
        issues: list[AccessibilityIssue] = []
        widgets = [root, *root.findChildren(QtWidgets.QWidget)]
        interactive = [
            widget
            for widget in widgets
            if _is_audited_interactive(widget)
            and widget.isEnabled()
            and not widget.isHidden()
            and not bool(widget.property("ghostAccessibilityAuditIgnore"))
        ]
        for widget in interactive:
            issues.extend(self._audit_control(root, widget))
        issues.extend(self._audit_shortcuts(root))
        if theme is not None:
            issues.extend(audit_theme_contrast(theme))
        surface = str(root.accessibleName() or root.windowTitle() or root.objectName() or type(root).__name__)
        return AccessibilityReport(surface, len(interactive), tuple(issues))

    def _audit_control(
        self,
        root: QtWidgets.QWidget,
        widget: QtWidgets.QWidget,
    ) -> Iterable[AccessibilityIssue]:
        issues: list[AccessibilityIssue] = []
        location = _object_location(widget)
        primary = bool(widget.property("ghostPrimaryAction"))
        frequent = bool(widget.property("ghostFrequentAction"))
        status_region = bool(widget.property("ghostStatusRegion"))
        icon_only = (
            isinstance(widget, QtWidgets.QAbstractButton)
            and not widget.icon().isNull()
            and not _plain_button_text(widget)
        )
        name = _meaningful_name(root, widget)

        if (primary or icon_only or status_region) and not name:
            issues.append(
                AccessibilityIssue(
                    "error",
                    "control.missing_name",
                    location,
                    "This primary, icon-only, or changing-state control has no assistive name.",
                    "Set a stable accessibleName that states the control's purpose.",
                )
            )
        if icon_only and not str(widget.toolTip() or "").strip():
            issues.append(
                AccessibilityIssue(
                    "error",
                    "control.missing_tooltip",
                    location,
                    "This icon-only control does not explain itself on hover.",
                    "Add a concise tooltip and matching accessible name.",
                )
            )
        if status_region and not str(widget.accessibleDescription() or "").strip():
            issues.append(
                AccessibilityIssue(
                    "error",
                    "status.missing_description",
                    location,
                    "This changing-state region does not expose a descriptive state to assistive technology.",
                    "Update accessibleDescription whenever the visible status changes.",
                )
            )

        target = _effective_target_size(widget)
        required = FREQUENT_TARGET_SIZE if frequent else MINIMUM_TARGET_SIZE
        if target.width() < required or target.height() < required:
            issues.append(
                AccessibilityIssue(
                    "warning",
                    "control.small_target",
                    location,
                    (
                        f"The effective target is {target.width()}x{target.height()} logical pixels; "
                        f"this {'frequent viewport ' if frequent else ''}control needs at least "
                        f"{required}x{required}."
                    ),
                    "Increase its layout-controlled hit target without relying on DPI-specific pixel sizes.",
                )
            )

        if not bool(widget.focusPolicy() & QtCore.Qt.TabFocus):
            issues.append(
                AccessibilityIssue(
                    "error" if primary else "warning",
                    "control.not_keyboard_focusable",
                    location,
                    "This enabled interactive control is skipped by keyboard Tab navigation.",
                    "Use a TabFocus or StrongFocus policy, or explicitly exempt a mouse-only renderer surface.",
                )
            )
        return issues

    @staticmethod
    def _audit_shortcuts(root: QtWidgets.QWidget) -> Iterable[AccessibilityIssue]:
        by_shortcut: dict[str, list[QtGui.QAction]] = defaultdict(list)
        for action in root.findChildren(QtGui.QAction):
            if not action.isEnabled() or not action.isVisible() or action.isSeparator():
                continue
            for shortcut in action.shortcuts():
                key = shortcut.toString(QtGui.QKeySequence.PortableText).strip()
                if key:
                    by_shortcut[key.casefold()].append(action)

        issues: list[AccessibilityIssue] = []
        for key, actions in sorted(by_shortcut.items()):
            unique = list(dict.fromkeys(actions))
            if len(unique) < 2:
                continue
            labels = ", ".join(
                str(action.text() or action.objectName() or "unnamed action").replace("&", "")
                for action in unique
            )
            issues.append(
                AccessibilityIssue(
                    "error",
                    "shortcut.duplicate",
                    str(root.windowTitle() or root.objectName() or type(root).__name__),
                    f"Shortcut {key} is assigned to multiple active actions: {labels}.",
                    "Give each action a unique shortcut in this window scope.",
                )
            )
        return issues


class AccessibilityAuditDialog(QtWidgets.QDialog):
    """Readable, copyable presentation for a live accessibility audit."""

    def __init__(self, report: AccessibilityReport, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.report = report
        self.setObjectName("AccessibilityAuditDialog")
        self.setWindowTitle("Accessibility Audit")
        self.setAccessibleName(f"Accessibility audit for {report.surface}")
        self.setAccessibleDescription(report.summary())
        self.resize(860, 620)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        summary = QtWidgets.QLabel(report.summary(), self)
        summary.setObjectName("AccessibilityAuditSummary")
        summary.setWordWrap(True)
        summary.setAccessibleName("Accessibility audit summary")
        root.addWidget(summary)

        self.report_text = QtWidgets.QPlainTextEdit(self)
        self.report_text.setObjectName("AccessibilityAuditReport")
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText(report.as_text())
        self.report_text.setAccessibleName("Accessibility audit findings")
        self.report_text.setAccessibleDescription(
            "A list of control, keyboard, target-size, shortcut, and theme contrast findings."
        )
        root.addWidget(self.report_text, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, self)
        copy_button = buttons.addButton("Copy Report", QtWidgets.QDialogButtonBox.ActionRole)
        copy_button.setAccessibleDescription("Copy the complete accessibility audit to the clipboard")
        copy_button.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(report.as_text())
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        QtCore.QTimer.singleShot(
            0,
            lambda: fit_top_level_window_to_available_screen(self),
        )


def show_accessibility_audit(
    root: QtWidgets.QWidget,
    *,
    theme: Theme | None = None,
) -> AccessibilityReport:
    """Audit ``root`` and show a modal, copyable report."""

    report = AccessibilityAuditor().audit_widget_tree(root, theme=theme)
    AccessibilityAuditDialog(report, root).exec()
    return report


__all__ = [
    "AccessibilityAuditDialog",
    "AccessibilityAuditor",
    "AccessibilityIssue",
    "AccessibilityReport",
    "FREQUENT_TARGET_SIZE",
    "MINIMUM_TARGET_SIZE",
    "NORMAL_TEXT_CONTRAST",
    "UI_BOUNDARY_CONTRAST",
    "audit_theme_contrast",
    "contrast_ratio",
    "install_accessibility_defaults",
    "relative_luminance",
    "show_accessibility_audit",
]
