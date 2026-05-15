"""
src/gui/qt_inspector_panel.py — Right-side contextual inspector (M2 / T203)

The Character Builder's right inspector is a :class:`QStackedWidget`
whose pages are keyed by **step number** (1..8) — the same numbering
used by :class:`QtWorkflowRail` (T202).  Selecting a step in the rail
swaps the inspector to the matching page.

Each page hosts the AccuRig-equivalent control bundle for that step
(audit §4.3): joint-name combo, symmetry toggle, mask controls,
midpoint-placement push-pin, hemisphere mesh probe, joint opacity /
size sliders, and the trailing 'Add Motions' / 'Export' actions.

The widgets here are **placeholders wired to signals** — they expose
the surface that downstream milestones (M4 joint-dot HUD, M5/M6/M7/M8
mode workflows, M9 validation banner wiring) will hook into.  No
backend logic lives in this file; the inspector is purely a
controller surface.

Public surface
--------------
* ``QtInspectorPanel(QWidget)``
* Signals:
    - ``stepChanged(int)``               — emitted after a page switch.
    - ``jointSelected(str)``              — combo box pick.
    - ``symmetryToggled(bool)``           — symmetry checkbox.
    - ``masksReset()``                    — Reset Masks button.
    - ``midpointPlacementRequested()``    — Midpoint Placement button.
    - ``hemisphereModeChanged(str)``      — 'whole' / 'front'.
    - ``jointOpacityChanged(float)``      — 0..1.
    - ``jointSizeChanged(float)``         — 0..1.
    - ``addMotionsRequested()``           — opens Animation Library.
    - ``exportRequested()``               — opens Export panel.
* Methods:
    - ``set_step(step_number)``           — programmatic page switch.
    - ``current_step()``                  — currently displayed page #.
    - ``populate_joints(iterable)``       — fill joint name combo.

Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md M2/T203.
Spec:    knowledge_base/roadmap/01_qt_branch_audit.md §4.3.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_theme import C, heading


# Canonical step numbers (must stay aligned with qt_workflow_rail.py).
_STEP_LOAD          = 1
_STEP_CHECK_MODEL   = 2
_STEP_RIG_BODY      = 3
_STEP_RIG_HANDS     = 4
_STEP_RIG_FACE      = 5
_STEP_CHECK_ACTOR   = 6
_STEP_MOTIONS       = 7
_STEP_VALIDATE      = 8

# Default page title per step (used by every mode — the rail decides
# which steps appear, but if a mode reuses step 3 for "Body Rig" or
# "Head Rig", the inspector page still says "Rig").  Detailed mode-
# specific copy can be layered in later via a setter.
_PAGE_TITLES: Dict[int, str] = {
    _STEP_LOAD:        "1. Load",
    _STEP_CHECK_MODEL: "2. Check Model",
    _STEP_RIG_BODY:    "3. Rig — Skeleton & Pins",
    _STEP_RIG_HANDS:   "4. Rig — Hands / Limbs",
    _STEP_RIG_FACE:    "5. Rig — Face / Special",
    _STEP_CHECK_ACTOR: "6. Check Actor / ROM",
    _STEP_MOTIONS:     "7. Add Motions",
    _STEP_VALIDATE:    "8. Validate + Export",
}


class QtInspectorPanel(QtWidgets.QWidget):
    """Contextual inspector: a QStackedWidget keyed by step number.

    Every step that the workflow rail can surface (1..8) has a
    dedicated page here.  Pages share a small AccuRig-equivalent
    control library — joint combo, symmetry, mask, sliders — assembled
    in different combinations per step.

    The inspector is intentionally backend-agnostic: it emits semantic
    signals and exposes setters, but never reaches into the scene
    directly.  Wiring happens in :class:`QtCharacterBuilderWindow`.
    """

    # ── Public signals ──────────────────────────────────────────────────
    stepChanged               = QtCore.Signal(int)
    jointSelected             = QtCore.Signal(str)
    symmetryToggled           = QtCore.Signal(bool)
    masksReset                = QtCore.Signal()
    midpointPlacementRequested = QtCore.Signal()
    hemisphereModeChanged     = QtCore.Signal(str)        # 'whole' | 'front'
    jointOpacityChanged       = QtCore.Signal(float)      # 0..1
    jointSizeChanged          = QtCore.Signal(float)      # 0..1
    addMotionsRequested       = QtCore.Signal()
    exportRequested           = QtCore.Signal()
    loadRequested             = QtCore.Signal()
    validateRequested         = QtCore.Signal()
    checkModelRequested       = QtCore.Signal()
    romTestRequested          = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        # Maps step_number → QStackedWidget page index for fast lookup.
        self._step_to_index: Dict[int, int] = {}
        self._joint_combos: List[QtWidgets.QComboBox] = []
        self._build()

    # ── UI construction ──────────────────────────────────────────────────

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        root.addWidget(heading("Inspector"))

        self._title_label = QtWidgets.QLabel(_PAGE_TITLES[_STEP_LOAD])
        self._title_label.setStyleSheet(
            f"color:{C.get('gold', '#FFD700')}; font-weight:bold; padding:2px 0;"
        )
        root.addWidget(self._title_label)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setStyleSheet(
            f"QStackedWidget {{ background:{C.get('bg2', '#1a1a1a')}; }}"
        )
        root.addWidget(self._stack, 1)

        # Build one page per canonical step.  Order matters: index 0 is
        # step 1 (Load), ..., index 7 is step 8 (Validate+Export).
        for step in (_STEP_LOAD, _STEP_CHECK_MODEL, _STEP_RIG_BODY,
                     _STEP_RIG_HANDS, _STEP_RIG_FACE, _STEP_CHECK_ACTOR,
                     _STEP_MOTIONS, _STEP_VALIDATE):
            page = self._build_page_for_step(step)
            idx = self._stack.addWidget(page)
            self._step_to_index[step] = idx

        # Default to step 1.
        self._stack.setCurrentIndex(0)

    def _page_layout(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        page._gr_layout = layout                            # type: ignore[attr-defined]
        return page

    def _build_page_for_step(self, step: int) -> QtWidgets.QWidget:
        page = self._page_layout()
        layout: QtWidgets.QVBoxLayout = page._gr_layout      # type: ignore[attr-defined]

        if step == _STEP_LOAD:
            self._populate_load_page(layout)
        elif step == _STEP_CHECK_MODEL:
            self._populate_check_model_page(layout)
        elif step in (_STEP_RIG_BODY, _STEP_RIG_HANDS, _STEP_RIG_FACE):
            self._populate_rig_page(layout, step)
        elif step == _STEP_CHECK_ACTOR:
            self._populate_check_actor_page(layout)
        elif step == _STEP_MOTIONS:
            self._populate_motions_page(layout)
        elif step == _STEP_VALIDATE:
            self._populate_validate_page(layout)
        else:                                                # pragma: no cover
            layout.addWidget(QtWidgets.QLabel(f"(no page for step {step})"))

        layout.addStretch(1)
        return page

    # ── Step-specific page builders ──────────────────────────────────────

    def _populate_load_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        layout.addWidget(QtWidgets.QLabel(
            "Load the source MDL / FBX / OBJ for this character mode.\n"
            "Auto-detection will pick a CharacterMode after load."
        ))
        btn = QtWidgets.QPushButton("Load Model…")
        btn.clicked.connect(self.loadRequested.emit)
        layout.addWidget(btn)

    def _populate_check_model_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        layout.addWidget(QtWidgets.QLabel(
            "Verify T-pose, scale, and topology.  Issues will appear in the\n"
            "bottom validation banner."
        ))
        btn = QtWidgets.QPushButton("Run Model Check")
        btn.clicked.connect(self.checkModelRequested.emit)
        layout.addWidget(btn)

    def _populate_rig_page(self, layout: QtWidgets.QVBoxLayout,
                            step: int) -> None:
        """Body / Hand / Face rig pages share the AccuRig control library."""
        # Joint name dropdown — populated by populate_joints().
        joint_row = QtWidgets.QHBoxLayout()
        joint_row.addWidget(QtWidgets.QLabel("Joint:"))
        combo = QtWidgets.QComboBox()
        combo.setEditable(False)
        combo.setMinimumWidth(140)
        combo.currentTextChanged.connect(self._on_joint_selected)
        self._joint_combos.append(combo)
        joint_row.addWidget(combo, 1)
        layout.addLayout(joint_row)

        # Symmetry checkbox.
        symmetry_row = QtWidgets.QHBoxLayout()
        symmetry_cb = QtWidgets.QCheckBox("Symmetry")
        symmetry_cb.setToolTip("Mirror placement across the X axis "
                               "(driven by grig.SymmetryEngine).")
        symmetry_cb.toggled.connect(self.symmetryToggled.emit)
        symmetry_row.addWidget(symmetry_cb)
        symmetry_row.addStretch(1)
        layout.addLayout(symmetry_row)

        # Mask / Reset Masks.
        mask_row = QtWidgets.QHBoxLayout()
        mask_cb = QtWidgets.QCheckBox("Mask")
        mask_cb.setToolTip("Limit bone-influence painting to the masked "
                           "region (per-region accurig.bone_masks).")
        reset_btn = QtWidgets.QPushButton("Reset Masks")
        reset_btn.setProperty("compact", True)
        reset_btn.clicked.connect(self.masksReset.emit)
        mask_row.addWidget(mask_cb)
        mask_row.addWidget(reset_btn)
        mask_row.addStretch(1)
        layout.addLayout(mask_row)

        # Midpoint Placement push-pin.
        midpoint_btn = QtWidgets.QPushButton("Midpoint Placement")
        midpoint_btn.setToolTip("Snap the active pin to the volume centroid "
                                "(accurig.midpoint_placement).")
        midpoint_btn.clicked.connect(self.midpointPlacementRequested.emit)
        layout.addWidget(midpoint_btn)

        # Hemisphere mesh probe (Whole / Front).
        hemi_group = QtWidgets.QGroupBox("Mesh Probe")
        hemi_layout = QtWidgets.QHBoxLayout(hemi_group)
        whole_rb = QtWidgets.QRadioButton("Whole Mesh")
        front_rb = QtWidgets.QRadioButton("Front Part")
        whole_rb.setChecked(True)
        whole_rb.toggled.connect(
            lambda checked: checked and self.hemisphereModeChanged.emit("whole")
        )
        front_rb.toggled.connect(
            lambda checked: checked and self.hemisphereModeChanged.emit("front")
        )
        hemi_layout.addWidget(whole_rb)
        hemi_layout.addWidget(front_rb)
        hemi_layout.addStretch(1)
        layout.addWidget(hemi_group)

        # Joint Opacity / Size sliders.
        slider_group = QtWidgets.QGroupBox("Joint Overlay")
        slider_layout = QtWidgets.QGridLayout(slider_group)
        slider_layout.addWidget(QtWidgets.QLabel("Opacity:"), 0, 0)
        opacity = self._make_unit_slider()
        opacity.valueChanged.connect(
            lambda v: self.jointOpacityChanged.emit(v / 100.0)
        )
        slider_layout.addWidget(opacity, 0, 1)

        slider_layout.addWidget(QtWidgets.QLabel("Size:"), 1, 0)
        size = self._make_unit_slider()
        size.setValue(50)
        size.valueChanged.connect(
            lambda v: self.jointSizeChanged.emit(v / 100.0)
        )
        slider_layout.addWidget(size, 1, 1)
        layout.addWidget(slider_group)

        # Step-specific hint banner so users know which sub-page they're on.
        if step == _STEP_RIG_BODY:
            hint = "Place humanoid pelvis / spine / limb pins."
        elif step == _STEP_RIG_HANDS:
            hint = "Fine-tune finger / wrist pins (or limbs for Creature mode)."
        else:  # _STEP_RIG_FACE
            hint = ("Place facial bones (f_jaw_g, f_um_g, lip corners) or "
                    "Spline-IK CVs for tails / wings / tentacles.")
        hint_label = QtWidgets.QLabel(hint)
        hint_label.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt; font-style:italic;"
        )
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

    def _populate_check_actor_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        layout.addWidget(QtWidgets.QLabel(
            "Run a Range-of-Motion test — every joint cycles through its\n"
            "limits.  Issues appear in the bottom banner."
        ))
        rom_btn = QtWidgets.QPushButton("Run ROM Test")
        rom_btn.clicked.connect(self.romTestRequested.emit)
        layout.addWidget(rom_btn)

    def _populate_motions_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        layout.addWidget(QtWidgets.QLabel(
            "Browse the animation library and attach KOTOR clips\n"
            "(idle, walk, talk, combat) to this character."
        ))
        btn = QtWidgets.QPushButton("Open Animation Library…")
        btn.clicked.connect(self.addMotionsRequested.emit)
        layout.addWidget(btn)

    def _populate_validate_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        layout.addWidget(QtWidgets.QLabel(
            "Final validation + export pipeline (KOTOR / FBX / glTF / OBJ)."
        ))
        validate_btn = QtWidgets.QPushButton("Validate Scene")
        validate_btn.clicked.connect(self.validateRequested.emit)
        layout.addWidget(validate_btn)

        export_btn = QtWidgets.QPushButton("Open Export Panel…")
        export_btn.setProperty("accent", True)
        export_btn.clicked.connect(self.exportRequested.emit)
        layout.addWidget(export_btn)

    # ── Small reusable bits ──────────────────────────────────────────────

    def _make_unit_slider(self) -> QtWidgets.QSlider:
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(100)
        slider.setTracking(True)
        slider.setMinimumWidth(120)
        return slider

    # ── Signal helpers ───────────────────────────────────────────────────

    def _on_joint_selected(self, name: str) -> None:
        # Keep all rig-page combos in sync so switching pages doesn't
        # lose the joint context.
        sender = self.sender()
        for combo in self._joint_combos:
            if combo is sender:
                continue
            if combo.currentText() != name:
                combo.blockSignals(True)
                idx = combo.findText(name)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                combo.blockSignals(False)
        if name:
            self.jointSelected.emit(name)

    # ── Public API ───────────────────────────────────────────────────────

    def set_step(self, step_number: int) -> bool:
        """Switch the stack to the page for *step_number*.

        Returns True when the step has a registered page, False
        otherwise (the stack is left unchanged in that case).
        """
        idx = self._step_to_index.get(int(step_number))
        if idx is None:
            return False
        if self._stack.currentIndex() != idx:
            self._stack.setCurrentIndex(idx)
            self._title_label.setText(_PAGE_TITLES.get(
                int(step_number), f"Step {step_number}"
            ))
            self.stepChanged.emit(int(step_number))
        return True

    def current_step(self) -> int:
        """Return the step number currently displayed."""
        current_idx = self._stack.currentIndex()
        for step, idx in self._step_to_index.items():
            if idx == current_idx:
                return step
        return _STEP_LOAD                                    # pragma: no cover

    def populate_joints(self, names: Iterable[str]) -> None:
        """Fill every rig-page joint dropdown with *names*.

        Call this whenever the active model's skeleton changes.  The
        currently-selected joint is preserved when it still exists in
        the new list.
        """
        unique = list(dict.fromkeys(str(n) for n in names if n))
        for combo in self._joint_combos:
            current = combo.currentText()
            combo.blockSignals(True)
            try:
                combo.clear()
                combo.addItems(unique)
                if current and current in unique:
                    combo.setCurrentIndex(unique.index(current))
            finally:
                combo.blockSignals(False)


__all__ = ["QtInspectorPanel"]
