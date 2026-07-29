"""Theme-aware progress panels and viewport toast notifications."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS

C = dict(LEGACY_MATRIX_COLORS)
_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}


class OperationPhase(str, Enum):
    """Visible lifecycle states shared by GhostStudio workflows."""

    IDLE = "idle"
    READY = "ready"
    BLOCKED = "blocked"
    BUSY = "busy"
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    STALE = "stale"
    CANCELLED = "cancelled"


_PHASE_LABELS: dict[OperationPhase, str] = {
    OperationPhase.IDLE: "Ready to begin",
    OperationPhase.READY: "Ready",
    OperationPhase.BLOCKED: "Blocked",
    OperationPhase.BUSY: "In progress",
    OperationPhase.FAILED: "Failed",
    OperationPhase.SUCCEEDED: "Completed",
    OperationPhase.STALE: "Update needed",
    OperationPhase.CANCELLED: "Cancelled",
}


@dataclass(frozen=True)
class FeedbackAction:
    """One user-facing recovery or next action."""

    key: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", str(self.key or "").strip())
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        if not self.key or not self.label:
            raise ValueError("Feedback actions require a stable key and visible label.")


@dataclass(frozen=True)
class OperationFeedback:
    """Presentation-ready state without workflow-specific widget logic."""

    phase: OperationPhase
    title: str
    detail: str = ""
    subject: str = ""
    reason: str = ""
    searched_scopes: tuple[str, ...] = ()
    actions: tuple[FeedbackAction, ...] = ()
    progress_value: int | None = None
    progress_total: int | None = None
    cancellable: bool = False
    preserves_work: bool = False

    def __post_init__(self) -> None:
        phase = self.phase if isinstance(self.phase, OperationPhase) else OperationPhase(str(self.phase))
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "title", str(self.title or "").strip())
        object.__setattr__(self, "detail", str(self.detail or "").strip())
        object.__setattr__(self, "subject", str(self.subject or "").strip())
        object.__setattr__(self, "reason", str(self.reason or "").strip())
        object.__setattr__(
            self,
            "searched_scopes",
            tuple(dict.fromkeys(str(scope).strip() for scope in self.searched_scopes if str(scope).strip())),
        )
        object.__setattr__(self, "actions", tuple(self.actions or ()))
        if not self.title:
            raise ValueError("Operation feedback requires a visible title.")

    @property
    def phase_label(self) -> str:
        return _PHASE_LABELS[self.phase]

    @property
    def accessible_description(self) -> str:
        rows = [self.phase_label, self.detail]
        if self.subject:
            rows.append(f"Item: {self.subject}")
        if self.reason:
            rows.append(f"Reason: {self.reason}")
        if self.searched_scopes:
            rows.append(f"Searched: {'; '.join(self.searched_scopes)}")
        if self.preserves_work:
            rows.append("Your current work was preserved.")
        return " ".join(row for row in rows if row)


def _lighten_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.lighter(int(factor * 100)).name().upper()


def _darken_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.darker(int(factor * 100)).name().upper()


def _surface_fill(value: str, style: str) -> str:
    style = style if style in _SURFACE_STYLES else "matte"
    if style == "flat":
        return value
    if style == "bevelled":
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_lighten_hex(value, 1.18)}, stop:1 {_darken_hex(value, 1.05)})"
    if style == "glossy":
        return (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {_lighten_hex(value, 1.35)}, stop:0.48 {_lighten_hex(value, 1.10)}, "
            f"stop:0.50 {value}, stop:1 {_darken_hex(value, 1.18)})"
        )
    return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {value}, stop:1 {_darken_hex(value, 1.06)})"


class QtProgressPanel(QtWidgets.QFrame):
    """Reusable themed operation-state block used by panels and toasts."""

    actionTriggered = QtCore.Signal(str)
    cancelRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, compact: bool = False):
        super().__init__(parent)
        self._compact = compact
        self._action_buttons: dict[str, QtWidgets.QPushButton] = {}
        if not compact:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred,
                QtWidgets.QSizePolicy.Minimum,
            )
        self.feedback = OperationFeedback(
            phase=OperationPhase.IDLE,
            title="Ready",
            detail="Choose an action to begin.",
        )
        self.setObjectName("ProgressPanel")
        self.setAccessibleName(self.feedback.title)
        layout = QtWidgets.QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(3)
        else:
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(6)
        self.phase_icon_label = QtWidgets.QLabel()
        self.phase_icon_label.setObjectName("ProgressPanelPhaseIcon")
        self.phase_icon_label.setFixedSize(18, 18)
        self.phase_label = QtWidgets.QLabel()
        self.phase_label.setObjectName("ProgressPanelPhase")
        self.phase_label.setTextFormat(QtCore.Qt.PlainText)
        status_row.addWidget(self.phase_icon_label)
        status_row.addWidget(self.phase_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("ProgressPanelTitle")
        self.title_label.setTextFormat(QtCore.Qt.PlainText)
        self.detail_label = QtWidgets.QLabel()
        self.detail_label.setObjectName("ProgressPanelDetail")
        self.detail_label.setTextFormat(QtCore.Qt.PlainText)
        self.detail_label.setWordWrap(True)
        if compact:
            self.detail_label.setMaximumHeight(32)
        self.context_label = QtWidgets.QLabel()
        self.context_label.setObjectName("ProgressPanelContext")
        self.context_label.setTextFormat(QtCore.Qt.PlainText)
        self.context_label.setWordWrap(True)
        self.context_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.preservation_label = QtWidgets.QLabel()
        self.preservation_label.setObjectName("ProgressPanelPreservation")
        self.preservation_label.setTextFormat(QtCore.Qt.PlainText)
        self.preservation_label.setWordWrap(True)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setAccessibleName("Operation progress")
        self.progress.setTextVisible(False)
        if compact:
            self.progress.setFixedHeight(5)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.context_label)
        layout.addWidget(self.preservation_label)
        layout.addWidget(self.progress)

        self.action_row = QtWidgets.QHBoxLayout()
        self.action_row.setSpacing(6)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("ProgressPanelCancelButton")
        self.cancel_button.setAccessibleName("Cancel current operation")
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.action_row.addStretch(1)
        self.action_row.addWidget(self.cancel_button)
        layout.addLayout(self.action_row)

        self.apply_ghost_theme(None)
        self.set_feedback(self.feedback)

    def apply_ghost_theme(self, theme, *, color_prefix: str = "", surface_style: str = "flat") -> None:
        if theme is None:
            panel = C["panel"]
            border = C["accent"]
            text = C["text"]
            subtext = C["text2"]
            bg = C["bg"]
            progress = C["accent"]
        else:
            if color_prefix:
                panel = theme.color(f"{color_prefix}.progressBackground", theme.color("panel.backgroundAlt", theme.color("panel.altBackground")))
                border = theme.color(f"{color_prefix}.border", theme.color("accent.primary"))
                text = theme.color(f"{color_prefix}.text", theme.color("text.primary"))
                subtext = theme.color(f"{color_prefix}.secondaryText", theme.color("text.secondary"))
                bg = theme.color(f"{color_prefix}.progressTrack", theme.color("input.background"))
                progress = theme.color(f"{color_prefix}.progressFill", theme.color("success", theme.color("accent.primary")))
            else:
                panel = theme.color("panel.backgroundAlt", theme.color("panel.altBackground"))
                border = theme.color("accent.primary")
                text = theme.color("text.primary")
                subtext = theme.color("text.secondary")
                bg = theme.color("input.background")
                progress = theme.color("success", theme.color("accent.primary"))
        panel_fill = _surface_fill(panel, surface_style)
        bg_fill = _surface_fill(bg, surface_style)
        border_top = _lighten_hex(border, 1.16)
        border_bottom = _darken_hex(border, 1.18)
        title_font_rule = "font-size: 11px;" if self._compact else ""
        detail_font_rule = "font-size: 10px;" if self._compact else ""
        progress_height = 5 if self._compact else 8
        self.setStyleSheet(
            f"""
            QFrame#ProgressPanel,
            QFrame#StartupSplashProgressPanel {{
                background: {panel_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QLabel#ProgressPanelTitle {{
                color: {text};
                font-weight: 700;
                {title_font_rule}
            }}
            QLabel#ProgressPanelDetail {{
                color: {subtext};
                {detail_font_rule}
            }}
            QLabel#ProgressPanelPhase,
            QLabel#ProgressPanelContext,
            QLabel#ProgressPanelPreservation {{
                color: {subtext};
                {detail_font_rule}
            }}
            QProgressBar {{
                background: {bg_fill};
                border: 1px solid {border};
                height: {progress_height}px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {progress};
            }}
            """
        )

    def set_feedback(self, feedback: OperationFeedback) -> None:
        self.feedback = feedback
        self.setProperty("operationPhase", feedback.phase.value)
        self.setAccessibleName(feedback.title)
        self.setAccessibleDescription(feedback.accessible_description)
        self.phase_label.setText(feedback.phase_label)
        self.phase_icon_label.setPixmap(self._phase_icon(feedback.phase).pixmap(16, 16))
        self.title_label.setText(feedback.title)
        self.detail_label.setText(feedback.detail)
        self.title_label.setToolTip(feedback.title)
        self.detail_label.setToolTip(feedback.detail)
        self.detail_label.setVisible(bool(feedback.detail))

        context_rows: list[str] = []
        if feedback.subject:
            context_rows.append(f"Item: {feedback.subject}")
        if feedback.reason:
            context_rows.append(f"Reason: {feedback.reason}")
        if feedback.searched_scopes:
            context_rows.append(f"Searched: {'; '.join(feedback.searched_scopes)}")
        self.context_label.setText("\n".join(context_rows))
        self.context_label.setVisible(bool(context_rows))
        self.preservation_label.setText(
            "Your current work was preserved." if feedback.preserves_work else ""
        )
        self.preservation_label.setVisible(feedback.preserves_work)

        if feedback.phase is OperationPhase.BUSY:
            if feedback.progress_total is not None and feedback.progress_total > 0:
                self.progress.setRange(0, feedback.progress_total)
                self.progress.setValue(
                    max(0, min(int(feedback.progress_value or 0), feedback.progress_total))
                )
            else:
                self.progress.setRange(0, 0)
            self.progress.setVisible(True)
        elif feedback.phase is OperationPhase.SUCCEEDED:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            self.progress.setVisible(True)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.progress.setVisible(False)

        self._replace_action_buttons(feedback.actions)
        self.cancel_button.setVisible(feedback.cancellable)
        if not self._compact:
            self.setMinimumHeight(0)
            self.layout().activate()
            self.setMinimumHeight(self.sizeHint().height())
        self.style().unpolish(self)
        self.style().polish(self)

    def _replace_action_buttons(self, actions: tuple[FeedbackAction, ...]) -> None:
        for button in self._action_buttons.values():
            self.action_row.removeWidget(button)
            button.deleteLater()
        self._action_buttons.clear()
        for action in actions:
            button = QtWidgets.QPushButton(action.label)
            button.setObjectName(f"ProgressPanelAction_{action.key}")
            button.setAccessibleName(action.label)
            button.setAccessibleDescription(action.description)
            button.setToolTip(action.description)
            button.clicked.connect(
                lambda _checked=False, key=action.key: self.actionTriggered.emit(key)
            )
            self.action_row.insertWidget(max(0, self.action_row.count() - 2), button)
            self._action_buttons[action.key] = button

    def action_button(self, key: str) -> Optional[QtWidgets.QPushButton]:
        return self._action_buttons.get(str(key))

    def _phase_icon(self, phase: OperationPhase) -> QtGui.QIcon:
        standard = {
            OperationPhase.IDLE: QtWidgets.QStyle.SP_MessageBoxInformation,
            OperationPhase.READY: QtWidgets.QStyle.SP_DialogApplyButton,
            OperationPhase.BLOCKED: QtWidgets.QStyle.SP_MessageBoxWarning,
            OperationPhase.BUSY: QtWidgets.QStyle.SP_BrowserReload,
            OperationPhase.FAILED: QtWidgets.QStyle.SP_MessageBoxCritical,
            OperationPhase.SUCCEEDED: QtWidgets.QStyle.SP_DialogApplyButton,
            OperationPhase.STALE: QtWidgets.QStyle.SP_MessageBoxWarning,
            OperationPhase.CANCELLED: QtWidgets.QStyle.SP_DialogCancelButton,
        }[phase]
        return self.style().standardIcon(standard)

    def set_busy(self, title: str, detail: str, *, cancellable: bool = False) -> None:
        self.set_feedback(
            OperationFeedback(
                phase=OperationPhase.BUSY,
                title=title,
                detail=detail,
                cancellable=cancellable,
            )
        )

    def set_progress(self, title: str, detail: str, value: int, total: int) -> None:
        self.set_feedback(
            OperationFeedback(
                phase=OperationPhase.BUSY,
                title=title,
                detail=detail,
                progress_value=value,
                progress_total=total,
            )
        )

    def set_finished(self, title: str, detail: str) -> None:
        self.set_feedback(
            OperationFeedback(
                phase=OperationPhase.SUCCEEDED,
                title=title,
                detail=detail,
            )
        )


class QtProgressToast(QtWidgets.QFrame):
    """Small non-modal progress toast anchored to the viewport canvas."""

    actionTriggered = QtCore.Signal(str)
    cancelRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("ProgressToast")
        self.setAccessibleName("Operation status")
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(360)
        self._action_callbacks: dict[str, Callable[[], None]] = {}
        self._close_timer = QtCore.QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.hide)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.progress_panel = QtProgressPanel(self, compact=True)
        self.progress_panel.actionTriggered.connect(self._on_action_triggered)
        self.progress_panel.cancelRequested.connect(self.cancelRequested.emit)
        layout.addWidget(self.progress_panel)
        parent_theme = getattr(getattr(parent, "theme_manager", None), "current_theme", None)
        if parent_theme is not None:
            self.apply_ghost_theme(parent_theme)

    def apply_ghost_theme(self, theme) -> None:
        self.progress_panel.apply_ghost_theme(theme)

    def apply_native_theme(self) -> None:
        theme = None
        parent = self.parentWidget()
        if parent is not None:
            theme = getattr(getattr(parent, "theme_manager", None), "current_theme", None)
            if theme is None:
                manager = getattr(parent, "theme_manager", None)
                if manager is not None:
                    theme = manager.get_theme()
        self.progress_panel.apply_ghost_theme(theme)

    def show_busy(self, title: str, detail: str):
        self.present(OperationFeedback(OperationPhase.BUSY, title, detail))

    def update_progress(self, title: str, detail: str, value: int, total: int):
        self.present(
            OperationFeedback(
                OperationPhase.BUSY,
                title,
                detail,
                progress_value=value,
                progress_total=total,
            )
        )

    def finish(self, title: str, detail: str, delay_ms: int = 2200):
        self.present(
            OperationFeedback(OperationPhase.SUCCEEDED, title, detail),
            delay_ms=delay_ms,
        )

    def present(
        self,
        feedback: OperationFeedback,
        *,
        callbacks: Optional[dict[str, Callable[[], None]]] = None,
        delay_ms: Optional[int] = None,
    ) -> None:
        self._close_timer.stop()
        self._action_callbacks = dict(callbacks or {})
        self.progress_panel.set_feedback(feedback)
        self.setAccessibleName(feedback.title)
        self.setAccessibleDescription(feedback.accessible_description)
        self._reposition()
        self.show()
        self.raise_()
        if delay_ms is not None and not feedback.actions and not feedback.cancellable:
            self._close_timer.start(max(0, int(delay_ms)))

    def _on_action_triggered(self, key: str) -> None:
        self.actionTriggered.emit(key)
        callback = self._action_callbacks.get(key)
        if callback is not None:
            try:
                callback()
            except Exception:  # pragma: no cover - recovery actions must not crash the UI
                traceback.print_exc()
        self.hide()

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        margin = 12
        viewport = getattr(parent, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        target = canvas if canvas is not None and canvas.isVisible() else viewport
        if target is not None and target.isVisible():
            rect = target.rect()
            x = rect.left() + margin
            y = max(rect.top() + margin, rect.bottom() - self.height() - margin + 1)
            point = target.mapToGlobal(QtCore.QPoint(x, y))
        else:
            x = margin
            y = max(margin, parent.height() - self.height() - margin)
            point = parent.mapToGlobal(QtCore.QPoint(x, y))
        self.move(point)
