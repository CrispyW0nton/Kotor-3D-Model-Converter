"""
src/gui/qt_bottom_strip.py — Character Builder bottom strip (M2 / T204)

The Character Builder's bottom region, ported from the AccuRig HUD
reference (audit §4.1).  Four regions, left → right:

  ┌──────────────────────────────────────────────────────────────────┐
  │ [Banner: GREEN/AMBER/RED]  [◀│▶ scrubber 0/120]  [Stats]  [Log] │
  └──────────────────────────────────────────────────────────────────┘

* **Validation banner** — colour-coded by ``validation_service.Severity``
  (green = clean, amber = warnings, red = errors).  Clicking opens the
  full validation report dialog.
* **Animation scrubber stub** — a frame slider + ◀/▶ buttons + frame
  counter.  Wired to a single ``frameChanged(int)`` signal; the
  viewport will hook into it in M4.
* **Stats line** — read-only label showing model + scene stats
  (verts / faces / bones / textures).  Driven by :meth:`set_stats`.
* **Export-log tail** — last log line shown inline; full log opens
  in a dialog on click.

Public surface
--------------
* ``QtBottomStrip(QWidget)``
* Signals:
    - ``bannerClicked()``       — request to show full validation report.
    - ``logClicked()``           — request to show full export-log dialog.
    - ``frameChanged(int)``      — current scrubber frame.
    - ``playPauseToggled(bool)`` — play/pause button state.
* Methods:
    - ``set_validation(severity, summary, issues=None)``
    - ``clear_validation()``
    - ``set_stats(text)``
    - ``set_log_tail(line)``
    - ``set_frame_range(min, max)`` / ``set_current_frame(f)``

Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md M2/T204.
Spec:    knowledge_base/roadmap/01_qt_branch_audit.md §4.1.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C


# ── Severity import (pykotor-safe) ──────────────────────────────────────────
# ``validation_service`` itself is pure-Python, but importing through
# ``src.core`` triggers the loader subtree (pykotor).  We import the
# module directly via importlib so the banner still works in test /
# headless environments where pykotor isn't installed.
try:
    from src.core.validation_service import Severity
    _SEVERITY_AVAILABLE = True
except Exception:                                       # pragma: no cover
    Severity = None                                     # type: ignore[assignment]
    _SEVERITY_AVAILABLE = False


# Banner palette — keyed off Severity values.  Aligned with the
# CharacterMode badge palette so the HUD reads consistently.
_BANNER_COLORS = {
    "clean":   ("#27AE60", "#FFFFFF"),    # green   / white
    "info":    ("#3FA9F5", "#FFFFFF"),    # blue    / white
    "warning": ("#F5A623", "#000000"),    # amber   / black
    "error":   ("#C0392B", "#FFFFFF"),    # red     / white
    "neutral": ("#444444", "#CCCCCC"),    # grey    / off-white
}


def _severity_to_key(severity) -> str:
    """Map a Severity enum / string / None to a banner palette key."""
    if severity is None:
        return "clean"
    # Enum object — read .value.
    val = getattr(severity, "value", severity)
    s = str(val).lower()
    if s in ("error", "errors"):
        return "error"
    if s in ("warning", "warn", "warnings"):
        return "warning"
    if s in ("info", "informational"):
        return "info"
    if s in ("clean", "ok", "pass", "passed"):
        return "clean"
    return "neutral"


class QtBottomStrip(QtWidgets.QWidget):
    """Status bar at the bottom of the Character Builder window.

    Hosts the validation banner, animation scrubber, scene stats, and
    a single-line tail of the export log.  Compositional widget — owns
    no state beyond its display fields; callers push state via
    setters.
    """

    bannerClicked     = QtCore.Signal()
    logClicked        = QtCore.Signal()
    frameChanged      = QtCore.Signal(int)
    playPauseToggled  = QtCore.Signal(bool)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._issues: List[object] = []
        self._is_playing = False
        self._build()
        # Default: clean banner, neutral stats, empty log.
        self.clear_validation()
        self.set_stats("—")
        self.set_log_tail("")
        self.set_frame_range(0, 0)

    # ── UI construction ──────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # ── Validation banner (clickable) ────────────────────────────────
        self._banner = _ClickableLabel("CLEAN")
        self._banner.setAlignment(QtCore.Qt.AlignCenter)
        self._banner.setMinimumWidth(150)
        self._banner.setMinimumHeight(22)
        self._banner.setCursor(QtCore.Qt.PointingHandCursor)
        self._banner.setToolTip("Click to view the full validation report.")
        self._banner.clicked.connect(self.bannerClicked.emit)
        layout.addWidget(self._banner)

        # ── Animation scrubber stub ──────────────────────────────────────
        scrubber_widget = QtWidgets.QWidget()
        scrubber_layout = QtWidgets.QHBoxLayout(scrubber_widget)
        scrubber_layout.setContentsMargins(0, 0, 0, 0)
        scrubber_layout.setSpacing(3)

        self._step_back_btn = QtWidgets.QToolButton()
        self._step_back_btn.setText("◀")
        self._step_back_btn.setToolTip("Previous frame")
        self._step_back_btn.clicked.connect(self._on_step_back)

        self._play_btn = QtWidgets.QToolButton()
        self._play_btn.setText("▶")
        self._play_btn.setCheckable(True)
        self._play_btn.setToolTip("Play / pause animation")
        self._play_btn.toggled.connect(self._on_play_toggled)

        self._step_fwd_btn = QtWidgets.QToolButton()
        self._step_fwd_btn.setText("▶")
        self._step_fwd_btn.setToolTip("Next frame")
        self._step_fwd_btn.clicked.connect(self._on_step_forward)

        self._frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._frame_slider.setRange(0, 0)
        self._frame_slider.setTracking(True)
        self._frame_slider.setMinimumWidth(160)
        self._frame_slider.valueChanged.connect(self._on_slider_changed)

        self._frame_label = QtWidgets.QLabel("0 / 0")
        self._frame_label.setMinimumWidth(60)
        self._frame_label.setAlignment(QtCore.Qt.AlignCenter)
        self._frame_label.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-family:monospace;"
        )

        for w in (self._step_back_btn, self._play_btn,
                  self._step_fwd_btn, self._frame_slider,
                  self._frame_label):
            scrubber_layout.addWidget(w)
        scrubber_widget.setMinimumWidth(260)
        layout.addWidget(scrubber_widget, 1)

        # ── Stats line ───────────────────────────────────────────────────
        self._stats_label = QtWidgets.QLabel("—")
        self._stats_label.setMinimumWidth(180)
        self._stats_label.setStyleSheet(
            f"color:{C.get('text', '#e0e0e0')}; "
            "font-family:monospace; font-size:9pt;"
        )
        layout.addWidget(self._stats_label)

        # ── Export-log tail ──────────────────────────────────────────────
        self._log_tail = _ClickableLabel("")
        self._log_tail.setMinimumWidth(180)
        self._log_tail.setStyleSheet(
            f"color:{C.get('text2', '#888')}; "
            "font-family:monospace; font-size:9pt;"
            "padding:0 4px;"
        )
        self._log_tail.setCursor(QtCore.Qt.PointingHandCursor)
        self._log_tail.setToolTip("Click to view the full export log.")
        self._log_tail.clicked.connect(self.logClicked.emit)
        layout.addWidget(self._log_tail, 1)

    # ── Validation banner API ────────────────────────────────────────────

    def set_validation(self, severity, summary: str,
                       issues: Optional[List[object]] = None) -> None:
        """Update the banner colour + text.

        Parameters
        ----------
        severity : :class:`Severity`, the string 'error' / 'warning' /
                   'info' / 'clean', or ``None`` (treated as clean).
        summary  : Short label shown in the banner (e.g. "3 errors").
        issues   : Optional list of :class:`ValidationIssue` instances
                   stashed for the bannerClicked → report dialog flow.
        """
        key = _severity_to_key(severity)
        bg, fg = _BANNER_COLORS.get(key, _BANNER_COLORS["neutral"])
        self._banner.setText(summary or key.upper())
        self._banner.setStyleSheet(
            "QLabel { "
            f"background:{bg}; color:{fg}; "
            "padding:2px 10px; border-radius:4px; "
            "font-weight:bold; "
            "}"
        )
        self._issues = list(issues or [])

    def clear_validation(self) -> None:
        self.set_validation("clean", "CLEAN", issues=[])

    def issues(self) -> List[object]:
        """Return the issue list last passed to :meth:`set_validation`."""
        return list(self._issues)

    # ── Scrubber API ─────────────────────────────────────────────────────

    def set_frame_range(self, minimum: int, maximum: int) -> None:
        minimum = int(minimum)
        maximum = int(max(minimum, maximum))
        self._frame_slider.blockSignals(True)
        self._frame_slider.setRange(minimum, maximum)
        self._frame_slider.blockSignals(False)
        self._refresh_frame_label()
        # Disable controls when there's no range to scrub.
        enabled = maximum > minimum
        for w in (self._step_back_btn, self._play_btn,
                  self._step_fwd_btn, self._frame_slider):
            w.setEnabled(enabled)

    def set_current_frame(self, frame: int) -> None:
        frame = int(frame)
        if self._frame_slider.value() == frame:
            return
        self._frame_slider.blockSignals(True)
        self._frame_slider.setValue(frame)
        self._frame_slider.blockSignals(False)
        self._refresh_frame_label()

    def current_frame(self) -> int:
        return int(self._frame_slider.value())

    def set_playing(self, playing: bool) -> None:
        """Programmatically set the play/pause state without echoing."""
        playing = bool(playing)
        if playing == self._is_playing:
            return
        self._play_btn.blockSignals(True)
        self._play_btn.setChecked(playing)
        self._play_btn.setText("⏸" if playing else "▶")
        self._play_btn.blockSignals(False)
        self._is_playing = playing

    # ── Stats / log API ──────────────────────────────────────────────────

    def set_stats(self, text: str) -> None:
        self._stats_label.setText(str(text) if text else "—")

    def set_log_tail(self, line: str) -> None:
        line = (line or "").strip()
        self._log_tail.setText(line or "(no log)")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _refresh_frame_label(self) -> None:
        cur = self._frame_slider.value()
        hi = self._frame_slider.maximum()
        self._frame_label.setText(f"{cur} / {hi}")

    def _on_slider_changed(self, value: int) -> None:
        self._refresh_frame_label()
        self.frameChanged.emit(int(value))

    def _on_step_back(self) -> None:
        self._frame_slider.setValue(max(self._frame_slider.minimum(),
                                        self._frame_slider.value() - 1))

    def _on_step_forward(self) -> None:
        self._frame_slider.setValue(min(self._frame_slider.maximum(),
                                        self._frame_slider.value() + 1))

    def _on_play_toggled(self, checked: bool) -> None:
        self._is_playing = bool(checked)
        self._play_btn.setText("⏸" if checked else "▶")
        self.playPauseToggled.emit(self._is_playing)


class _ClickableLabel(QtWidgets.QLabel):
    """QLabel that emits ``clicked`` on a left-mouse release."""

    clicked = QtCore.Signal()

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        if ev.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)


__all__ = ["QtBottomStrip"]
