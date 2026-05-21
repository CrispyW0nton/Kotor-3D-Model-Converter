"""
src/gui/qt_workflow_rail.py — Left-rail workflow widget (M2 / T202)

The Character Builder's left-rail step list, ported from the AccuRig HUD
reference (audit §4.2).  The rail is mode-aware for status text and future
gates, but the visible sequence is intentionally unified around the practical
KOTOR modder path.

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

from src.gui.qt_lib.assets.qt_theme import C, heading, icon

# ── CharacterMode wiring (lazy / pykotor-safe) ──────────────────────────────
# src.core.__init__ eagerly imports the pykotor-backed loader stack, which
# is not always available in CI / headless environments.  We isolate the
# failure so the rail still renders an empty placeholder.
try:
    from src.core.qt_core.geometry.model_data import CharacterMode
    _CHARACTER_MODE_AVAILABLE = True
except Exception:                                       # pragma: no cover
    CharacterMode = None                                # type: ignore[assignment]
    _CHARACTER_MODE_AVAILABLE = False


# ── Step lists per mode (audit §4.2) ────────────────────────────────────────
#
# Each entry is (step_number, label).  The Character Builder now follows the
# practical modder path instead of the older milestone/task list:
# pick a KOTOR base, import and align the mesh, commit the skeleton, assign
# animations, preview attachments/animation, then export a game-ready MDL.
#
# These are module-level so they can be unit-tested and overridden by
# tools without monkey-patching the widget.

_STEPS_UNIFIED_CHARACTER_BUILDER: List[Tuple[int, str]] = [
    (1, "Choose Base + Load Mesh"),
    (2, "Assign Skeleton"),
    (3, "Assign Animations"),
    (4, "Preview"),
    (5, "Export MDL"),
]

_STEPS_HEADLESS_BODY: List[Tuple[int, str]] = [
    *_STEPS_UNIFIED_CHARACTER_BUILDER,
]

_STEPS_HEAD: List[Tuple[int, str]] = [
    *_STEPS_UNIFIED_CHARACTER_BUILDER,
]

_STEPS_SUPERMODEL: List[Tuple[int, str]] = [
    *_STEPS_UNIFIED_CHARACTER_BUILDER,
]

_STEPS_HUMANOID: List[Tuple[int, str]] = [
    (1, "Load Humanoid"),
    (2, "Check Model (body + head)"),
    (3, "Body Rig"),
    (4, "Hand Rig"),
    (5, "Face Rig"),
    (6, "Check Actor + Face"),
    (7, "Add Motions"),
    (8, "Validate + Export"),
]

_STEPS_CREATURE: List[Tuple[int, str]] = [
    *_STEPS_UNIFIED_CHARACTER_BUILDER,
]

_STEPS_FALLBACK: List[Tuple[int, str]] = [
    (1, "Choose Base + Load Mesh"),
    (2, "Assign Skeleton"),
    (3, "Assign Animations"),
    (4, "Preview"),
    (5, "Export MDL"),
]


def _steps_for_mode(mode) -> List[Tuple[int, str]]:
    """Return the (step_number, label) list for the given CharacterMode.

    Tolerates ``None`` and the AMBIGUOUS / UNSUPPORTED fallbacks by keeping
    the same five-step launch workflow visible so the user always has a clear
    path forward.
    """
    if mode is None or not _CHARACTER_MODE_AVAILABLE:
        return list(_STEPS_FALLBACK)
    if mode == CharacterMode.HEADLESS_BODY:
        return list(_STEPS_HEADLESS_BODY)
    if mode == CharacterMode.HEAD:
        return list(_STEPS_HEAD)
    if getattr(CharacterMode, "HUMANOID", None) is not None and mode == CharacterMode.HUMANOID:
        return list(_STEPS_HUMANOID)
    if mode == CharacterMode.SUPERMODEL:
        return list(_STEPS_SUPERMODEL)
    if mode == CharacterMode.CREATURE:
        return list(_STEPS_CREATURE)
    # AMBIGUOUS / UNSUPPORTED → fallback rail.
    return list(_STEPS_FALLBACK)


# ── Roles for embedding step metadata into QListWidgetItem ──────────────────
_ROLE_STEP_NUMBER = QtCore.Qt.UserRole + 1
_ROLE_GATE_REASON = QtCore.Qt.UserRole + 2

_ICON_FOR_STEP = {
    1: "loadmodel",
    2: "skeleton",
    3: "library",
    4: "anims",
    5: "export",
}


class QtWorkflowRail(QtWidgets.QWidget):
    """Mode-aware numbered step list (left rail of Character Builder).

    The rail is intentionally lightweight — it owns the *navigation*
    state only.  Step content (forms, buttons, sliders) lives in the
    right inspector :class:`QtInspectorPanel` and is keyed by the same
    step numbers (T203).
    """

    # Emitted when the user clicks an *enabled* step.  Payload: 1-based
    # step number (1..5 in the canonical launch list).
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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        brand = QtWidgets.QFrame()
        brand.setObjectName("GuidedRigRailBrand")
        brand_layout = QtWidgets.QVBoxLayout(brand)
        brand_layout.setContentsMargins(10, 8, 10, 8)
        brand_layout.setSpacing(0)
        title = QtWidgets.QLabel("GHOSTRIGGER")
        title.setObjectName("GuidedRigRailTitle")
        subtitle = QtWidgets.QLabel("KOTOR AUTO-RIG")
        subtitle.setObjectName("GuidedRigRailSubtitle")
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        brand.setStyleSheet(
            "QFrame#GuidedRigRailBrand { "
            f"background:{C.get('panel', '#111916')}; "
            f"border:1px solid {C.get('border', '#1B2A22')}; "
            "border-radius:4px; "
            "}"
            "QLabel#GuidedRigRailTitle { "
            f"color:{C.get('accent', '#00FF7A')}; "
            "font-size:11pt; font-weight:800; letter-spacing:0px; "
            "}"
            "QLabel#GuidedRigRailSubtitle { "
            f"color:{C.get('text2', '#7A9A88')}; "
            "font-size:8pt; font-weight:600; letter-spacing:0px; "
            "}"
        )
        layout.addWidget(brand)

        self._mode_label = QtWidgets.QLabel("(no mode)")
        self._mode_label.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt; padding-left:2px;"
        )
        layout.addWidget(self._mode_label)

        self._list = QtWidgets.QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._list.setUniformItemSizes(True)
        self._list.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._list.setIconSize(QtCore.QSize(22, 22))
        self._list.setSpacing(7)
        self._list.setStyleSheet(
            "QListWidget { "
            f"background:{C.get('panel', '#111916')}; "
            f"color:{C.get('text', '#e0e0e0')}; "
            "border:0; "
            "outline:0; "
            "}"
            "QListWidget::item { "
            f"background:{C.get('panel2', '#151D1A')}; "
            f"border:1px solid {C.get('accent', '#00FF7A')}; "
            "border-radius:5px; "
            "padding:10px 10px; "
            "min-height:32px; "
            "}"
            "QListWidget::item:hover { "
            f"background:{C.get('hover', '#183428')}; "
            "}"
            "QListWidget::item:selected { "
            f"background:{C.get('hover', '#183428')}; "
            f"color:{C.get('accent', '#00FF7A')}; "
            "font-weight:bold; "
            "}"
            "QListWidget::item:disabled { "
            "color:#55665B; border-color:#324438; background:#101713; "
            "}"
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self._list, 1)

        # Initial empty / fallback population.
        self.set_mode(None)

    def apply_ghost_theme(self, theme) -> None:
        brand = self.findChild(QtWidgets.QFrame, "GuidedRigRailBrand")
        if brand is not None:
            brand.setStyleSheet(
                "QFrame#GuidedRigRailBrand { "
                f"background:{theme.color('panel.background')}; "
                f"border:1px solid {theme.color('panel.border')}; "
                "border-radius:4px; "
                "}"
                "QLabel#GuidedRigRailTitle { "
                f"color:{theme.color('accent.primary')}; "
                "font-size:11pt; font-weight:800; letter-spacing:0px; "
                "}"
                "QLabel#GuidedRigRailSubtitle { "
                f"color:{theme.color('text.secondary')}; "
                "font-size:8pt; font-weight:600; letter-spacing:0px; "
                "}"
            )
        self._mode_label.setStyleSheet(
            f"color:{theme.color('text.secondary')}; font-size:8pt; padding-left:2px;"
        )
        self._list.setStyleSheet(
            "QListWidget { "
            f"background:{theme.color('panel.background')}; "
            f"color:{theme.color('text.primary')}; "
            "border:0; outline:0; "
            "}"
            "QListWidget::item { "
            f"background:{theme.color('button.background')}; "
            f"border:1px solid {theme.color('panel.border')}; "
            "border-radius:5px; padding:8px 10px; min-height:28px; "
            "}"
            "QListWidget::item:hover { "
            f"background:{theme.color('button.hover')}; "
            "}"
            "QListWidget::item:selected { "
            f"background:{theme.color('button.checked')}; "
            f"color:{theme.color('button.checkedText', theme.color('selection.text'))}; "
            "font-weight:bold; "
            "}"
            "QListWidget::item:disabled { "
            f"color:{theme.color('text.disabled')}; border-color:{theme.color('panel.border')}; background:{theme.color('panel.backgroundAlt', theme.color('panel.altBackground'))}; "
            "}"
        )

    def apply_ghost_layout(self, layout) -> None:
        if self.layout() is not None:
            margin = layout.spacing_value("panelSpacing", 4)
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(layout.spacing_value("panelSpacing", 4))
        self._list.setSpacing(max(2, layout.spacing_value("groupboxSpacing", 4)))

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
            item.setIcon(icon(_ICON_FOR_STEP.get(int(step_no), "charbuilder"), 24))
            item.setData(_ROLE_STEP_NUMBER, int(step_no))
            item.setSizeHint(QtCore.QSize(172, 46))
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
