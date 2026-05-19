"""
src/gui/qt_workflow_rail.py — Left-rail workflow widget (M2 / T202)

The Character Builder's left-rail step list, ported from the AccuRig HUD
reference (audit §4.2).  The rail is **mode-aware**: the visible step
sequence changes when the user switches CharacterMode in the toolbar,
but step numbering stays consistent.

Public surface
--------------
* ``QtWorkflowRail(QWidget)``     — the rail widget itself.
* ``QtWorkflowRail.stepSelected(int)`` — emitted when the user clicks
  an *enabled* step.  Payload: 1-based step index.
* ``QtWorkflowRail.set_mode(CharacterMode | None)`` — repopulates the
  list for the given mode.  Passing ``None`` shows an empty rail with a
  placeholder hint.
* ``QtWorkflowRail.set_step_enabled(int, bool, reason="")`` — toggles
  a step's gating; disabled steps grey out and show *reason* as a tooltip.
* ``QtWorkflowRail.current_step()`` / ``set_current_step(int)`` —
  programmatic selection.

Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md M2/T202.
Spec:    knowledge_base/roadmap/01_qt_branch_audit.md §4.2.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_theme import C, heading

# ── CharacterMode wiring (lazy / pykotor-safe) ──────────────────────────────
# src.core.__init__ eagerly imports the pykotor-backed loader stack, which
# is not always available in CI / headless environments.  We isolate the
# failure so the rail still renders an empty placeholder.
try:
    from ..core.model_data import CharacterMode
    _CHARACTER_MODE_AVAILABLE = True
except Exception:                                       # pragma: no cover
    CharacterMode = None                                # type: ignore[assignment]
    _CHARACTER_MODE_AVAILABLE = False


# ── Step lists per mode (audit §4.2) ────────────────────────────────────────
#
# Each entry is (step_number, label).  Step numbering is intentionally
# *consistent* across modes so the inspector pages line up 1:1 (see T203);
# a step that doesn't apply to a mode is simply absent from that mode's
# list rather than renumbered.
#
# These are module-level so they can be unit-tested and overridden by
# tools without monkey-patching the widget.

_STEPS_HEADLESS_BODY: List[Tuple[int, str]] = [
    (1, "Load Body"),
    (2, "Check Model (T-pose, scale)"),
    (3, "Body Rig (humanoid pins)"),
    (4, "Hand Rig (fingers)"),
    (6, "Check Actor (idle/walk/talk)"),
    (7, "Add Motions"),
    (8, "Validate + Export"),
]

_STEPS_HEAD: List[Tuple[int, str]] = [
    (1, "Load Head"),
    (2, "Check Model"),
    (3, "Head Rig (head/neck/jaw)"),
    (4, "Face Rig (lids, lip corners)"),
    (5, "LIP & Phoneme Test"),
    (6, "Check Face (jaw/blink/visemes)"),
    (8, "Validate + Export"),
]

_STEPS_SUPERMODEL: List[Tuple[int, str]] = [
    (1, "Load Body + Load Head"),
    (2, "Check both, fit at headhook"),
    (3, "Body Rig"),
    (4, "Hand Rig"),
    (5, "Face Rig"),
    (6, "Check Actor + Face"),
    (7, "Add Motions"),
    (8, "Validate + Export"),
]

_STEPS_CREATURE: List[Tuple[int, str]] = [
    (1, "Load Creature"),
    (2, "Check Model"),
    (3, "Profile Pick (humanoid / quadruped / droid / prop)"),
    (4, "Limb Rig (per profile)"),
    (5, "Special: Tail / Wing / Tentacle Spline-IK"),
    (6, "ROM Test (Stewart Jones range-of-motion)"),
    (7, "Add Motions"),
    (8, "Validate + Export"),
]

_STEPS_FALLBACK: List[Tuple[int, str]] = [
    (1, "Load Model"),
    (8, "Validate + Export"),
]


def _steps_for_mode(mode) -> List[Tuple[int, str]]:
    """Return the (step_number, label) list for the given CharacterMode.

    Tolerates ``None`` (empty rail) and the AMBIGUOUS / UNSUPPORTED
    fallbacks (single-step "Load" + "Export" hint so the user always
    has somewhere to start).
    """
    if mode is None or not _CHARACTER_MODE_AVAILABLE:
        return list(_STEPS_FALLBACK)
    if mode == CharacterMode.HEADLESS_BODY:
        return list(_STEPS_HEADLESS_BODY)
    if mode == CharacterMode.HEAD:
        return list(_STEPS_HEAD)
    if mode == CharacterMode.SUPERMODEL:
        return list(_STEPS_SUPERMODEL)
    if mode == CharacterMode.CREATURE:
        return list(_STEPS_CREATURE)
    # AMBIGUOUS / UNSUPPORTED → fallback rail.
    return list(_STEPS_FALLBACK)


# ── Roles for embedding step metadata into QListWidgetItem ──────────────────
_ROLE_STEP_NUMBER = QtCore.Qt.UserRole + 1
_ROLE_GATE_REASON = QtCore.Qt.UserRole + 2


class QtWorkflowRail(QtWidgets.QWidget):
    """Mode-aware numbered step list (left rail of Character Builder).

    The rail is intentionally lightweight — it owns the *navigation*
    state only.  Step content (forms, buttons, sliders) lives in the
    right inspector :class:`QtInspectorPanel` and is keyed by the same
    step numbers (T203).
    """

    # Emitted when the user clicks an *enabled* step.  Payload: 1-based
    # step number (1..8 in the canonical list).
    stepSelected = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._current_mode = None
        # Maps 1-based step number → (enabled, gate_reason).  Persists
        # gating decisions across set_mode() calls so callers don't
        # have to re-issue gates every time the mode changes.
        self._gates: Dict[int, Tuple[bool, str]] = {}
        self._build()

    # ── UI construction ──────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(heading("Workflow"))

        self._mode_label = QtWidgets.QLabel("(no mode)")
        self._mode_label.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:9pt; font-style:italic;"
        )
        layout.addWidget(self._mode_label)

        self._list = QtWidgets.QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._list.setUniformItemSizes(True)
        self._list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._list.setStyleSheet(
            "QListWidget { "
            f"background:{C.get('bg2', '#1a1a1a')}; "
            f"color:{C.get('text', '#e0e0e0')}; "
            "border:1px solid #2a2a2a; "
            "outline:0; "
            "}"
            "QListWidget::item { padding:6px 8px; }"
            "QListWidget::item:selected { "
            f"background:{C.get('accent', '#00FF7A')}; "
            "color:#000000; "
            "font-weight:bold; "
            "}"
            "QListWidget::item:disabled { color:#666666; }"
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self._list, 1)

        # Initial empty / fallback population.
        self.set_mode(None)

    # ── Public API ────────────────────────────────────────────────────────

    def set_mode(self, mode) -> None:
        """Repopulate the rail for *mode*.

        Re-applies any previously-set gates from :attr:`_gates` so a
        disabled step stays disabled across mode switches.
        """
        self._current_mode = mode

        if mode is None:
            self._mode_label.setText("(no mode)")
        else:
            display = getattr(mode, "display_name", str(mode))
            self._mode_label.setText(f"Mode: {display}")

        steps = _steps_for_mode(mode)
        self._list.blockSignals(True)
        self._list.clear()
        for step_no, label in steps:
            item = QtWidgets.QListWidgetItem(f"{step_no}. {label}")
            item.setData(_ROLE_STEP_NUMBER, int(step_no))
            # Re-apply persisted gate (if any).
            enabled, reason = self._gates.get(int(step_no), (True, ""))
            self._apply_gate_to_item(item, enabled, reason)
            self._list.addItem(item)
        self._list.blockSignals(False)

        # Auto-select first enabled step so keyboard navigation works
        # immediately after a mode switch.
        first_enabled = self._first_enabled_row()
        if first_enabled is not None:
            self._list.setCurrentRow(first_enabled)

    def current_mode(self):
        """Return the CharacterMode last passed to :meth:`set_mode`."""
        return self._current_mode

    def steps(self) -> List[Tuple[int, str]]:
        """Return the current rail's step list as (number, label) tuples."""
        out: List[Tuple[int, str]] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            step_no = int(item.data(_ROLE_STEP_NUMBER) or 0)
            # Strip the "<n>. " prefix to get the bare label back.
            text = item.text()
            label = text.split(". ", 1)[1] if ". " in text else text
            out.append((step_no, label))
        return out

    def set_step_enabled(self, step_number: int, enabled: bool,
                         reason: str = "") -> None:
        """Toggle gating for a step.

        Parameters
        ----------
        step_number : 1-based step number (as listed in the rail).
        enabled     : ``False`` greys the row and ignores clicks.
        reason      : Tooltip explaining *why* the step is gated.  Shown
                      when the user hovers a disabled row.
        """
        step_number = int(step_number)
        self._gates[step_number] = (bool(enabled), str(reason))
        # Apply to the live row if it exists for the current mode.
        for i in range(self._list.count()):
            item = self._list.item(i)
            if int(item.data(_ROLE_STEP_NUMBER) or 0) == step_number:
                self._apply_gate_to_item(item, enabled, reason)
                break

    def is_step_enabled(self, step_number: int) -> bool:
        enabled, _reason = self._gates.get(int(step_number), (True, ""))
        return bool(enabled)

    def current_step(self) -> Optional[int]:
        """Return the 1-based step number of the selected row (or None)."""
        item = self._list.currentItem()
        if item is None:
            return None
        step_no = int(item.data(_ROLE_STEP_NUMBER) or 0)
        return step_no or None

    def set_current_step(self, step_number: int) -> bool:
        """Programmatically select the row with the given step number.

        Returns True when the step exists in the current mode's rail.
        """
        for i in range(self._list.count()):
            item = self._list.item(i)
            if int(item.data(_ROLE_STEP_NUMBER) or 0) == int(step_number):
                self._list.setCurrentRow(i)
                return True
        return False

    # ── Internal helpers ─────────────────────────────────────────────────

    def _apply_gate_to_item(self, item: QtWidgets.QListWidgetItem,
                            enabled: bool, reason: str) -> None:
        flags = item.flags()
        if enabled:
            flags |= QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
            item.setData(_ROLE_GATE_REASON, "")
            item.setToolTip("")
        else:
            flags &= ~QtCore.Qt.ItemIsEnabled
            # Selectable is left on so the user can still focus the row
            # and read the gate-reason tooltip; setEnabled is what
            # actually greys it.
            item.setData(_ROLE_GATE_REASON, reason or "Not available yet")
            item.setToolTip(reason or "Not available yet")
        item.setFlags(flags)

    def _first_enabled_row(self) -> Optional[int]:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.flags() & QtCore.Qt.ItemIsEnabled:
                return i
        return None

    # ── Signal plumbing ──────────────────────────────────────────────────

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        if not (item.flags() & QtCore.Qt.ItemIsEnabled):
            # Disabled — surface the gate reason as a transient tooltip.
            reason = str(item.data(_ROLE_GATE_REASON) or "Not available yet")
            QtWidgets.QToolTip.showText(
                QtGui.QCursor.pos(), reason, self._list
            )
            return
        step_no = int(item.data(_ROLE_STEP_NUMBER) or 0)
        if step_no:
            self.stepSelected.emit(step_no)

    def _on_current_row_changed(self, row: int) -> None:
        # Keep the "currentRow" tracking the active selection but only
        # emit stepSelected via _on_item_clicked so we don't double-fire
        # on programmatic set_current_step() calls.
        if row < 0:
            return
        item = self._list.item(row)
        if item is None or not (item.flags() & QtCore.Qt.ItemIsEnabled):
            return


__all__ = ["QtWorkflowRail"]
