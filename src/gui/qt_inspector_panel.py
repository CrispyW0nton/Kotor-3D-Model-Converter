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
    # M5 / T503 — body-rig generation
    placeGuidesRequested      = QtCore.Signal()
    generateSkeletonRequested = QtCore.Signal()
    # M5 / T504 — Hand-rig step.
    placeHandGuidesRequested  = QtCore.Signal()
    handMaskChanged           = QtCore.Signal(str, bool)  # (bone, masked?)
    # M5 / T505 — Check-actor step.
    playPreviewAnimationRequested = QtCore.Signal(str)    # (anim_name,)
    stopPreviewAnimationRequested = QtCore.Signal()
    refreshPreviewAnimationsRequested = QtCore.Signal()

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
        """Check-Model inspector page (M5 / T502).

        Hosts the *Run Model Check* button plus a per-issue table that
        is repopulated by :meth:`set_check_model_result` after each run.
        The table is sortable by severity / code / slot / node so the
        user can triage validator findings without leaving the panel.
        """
        layout.addWidget(QtWidgets.QLabel(
            "Verify T-pose, scale, hooks, bones, and skin weights.  All\n"
            "issues from the validation service appear in the table below\n"
            "(and a banner summary in the bottom strip)."
        ))
        btn = QtWidgets.QPushButton("Run Model Check")
        btn.clicked.connect(self.checkModelRequested.emit)
        layout.addWidget(btn)

        # Tally label — updated by ``set_check_model_result``.
        self._check_model_tally = QtWidgets.QLabel("No check has been run yet.")
        self._check_model_tally.setStyleSheet(
            "color:#888; padding:2px 0; font-style:italic;"
        )
        layout.addWidget(self._check_model_tally)

        # Issue table — code / severity / slot / node / message.
        table = QtWidgets.QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Sev", "Code", "Slot", "Node", "Message"]
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self._check_model_table = table
        layout.addWidget(table, 1)

    def set_check_model_result(self, result) -> None:
        """Populate the Check-Model page with a CheckModelResult.

        The argument is expected to be the dataclass returned by
        :func:`src.core.headless_body_workflow.check_model`; we read
        ``error_count`` / ``warning_count`` / ``info_count`` / ``codes``
        for the tally label and ``issues`` for the table.  Duck-typed
        so tests can pass a stub object.
        """
        table = getattr(self, "_check_model_table", None)
        tally = getattr(self, "_check_model_tally", None)
        if table is None or tally is None:                  # pragma: no cover
            return

        issues = list(getattr(result, "issues", []) or [])
        errs   = int(getattr(result, "error_count",   0))
        warns  = int(getattr(result, "warning_count", 0))
        infos  = int(getattr(result, "info_count",    0))
        codes  = getattr(result, "codes", set()) or set()

        if not issues:
            tally.setText("Clean — no issues reported.")
            tally.setStyleSheet("color:#7ed957; padding:2px 0;")
        else:
            tally.setText(
                f"{errs} error(s), {warns} warning(s), {infos} info "
                f"— {len(codes)} unique code(s)"
            )
            if errs:
                tally.setStyleSheet("color:#ff6b6b; padding:2px 0;")
            elif warns:
                tally.setStyleSheet("color:#ffd166; padding:2px 0;")
            else:
                tally.setStyleSheet("color:#5cc0ff; padding:2px 0;")

        # Refill table.
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for issue in issues:
            row = table.rowCount()
            table.insertRow(row)
            sev = getattr(issue, "severity", None)
            sev_value = getattr(sev, "value", str(sev)).upper()
            code = getattr(issue, "code", "")
            slot = getattr(issue, "slot", None)
            slot_label = getattr(slot, "value", "" if slot is None else str(slot))
            node = getattr(issue, "node", "") or ""
            msg = getattr(issue, "message", "") or ""
            for col, text in enumerate(
                (sev_value, code, str(slot_label), node, msg)
            ):
                item = QtWidgets.QTableWidgetItem(text)
                table.setItem(row, col, item)
        table.setSortingEnabled(True)

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

        # M5 / T504 — Retire the generic legacy "Mask" row + "Midpoint
        # Placement" stub on the body / hand rig pages.  The body page
        # now drives masking via :func:`generate_skeleton`, and the
        # hand page replaces the row with the per-finger checkbox
        # GroupBox below.  The face step keeps the legacy controls
        # until M5/T506 retires them too.
        if step == _STEP_RIG_FACE:
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

        # ── M5 / T503 — Body-rig action buttons (body step only) ─────
        if step == _STEP_RIG_BODY:
            actions = QtWidgets.QGroupBox("AcuRig actions")
            actions_layout = QtWidgets.QVBoxLayout(actions)
            actions_layout.setSpacing(4)

            self._place_guides_btn = QtWidgets.QPushButton("Place Guides")
            self._place_guides_btn.setToolTip(
                "Snap AcuRig humanoid guide pins onto the body model.\n"
                "Use the joint-dot HUD to fine-tune positions; drag with\n"
                "Symmetry enabled to mirror across the X axis."
            )
            self._place_guides_btn.clicked.connect(self.placeGuidesRequested.emit)
            actions_layout.addWidget(self._place_guides_btn)

            self._generate_skeleton_btn = QtWidgets.QPushButton(
                "Generate Skeleton"
            )
            self._generate_skeleton_btn.setProperty("accent", True)
            self._generate_skeleton_btn.setToolTip(
                "Build bones from the current guides + run heat-map\n"
                "skinning (accurig.build_skeleton + auto_skin)."
            )
            self._generate_skeleton_btn.clicked.connect(
                self.generateSkeletonRequested.emit
            )
            actions_layout.addWidget(self._generate_skeleton_btn)

            self._body_rig_status = QtWidgets.QLabel("No guides placed yet.")
            self._body_rig_status.setStyleSheet(
                f"color:{C.get('text2', '#888')}; font-size:8pt;"
            )
            self._body_rig_status.setWordWrap(True)
            actions_layout.addWidget(self._body_rig_status)

            layout.addWidget(actions)

        # ── M5 / T504 — Hand-rig action group (hands step only) ──────
        if step == _STEP_RIG_HANDS:
            hand_actions = QtWidgets.QGroupBox("Hand-rig actions")
            hand_layout = QtWidgets.QVBoxLayout(hand_actions)
            hand_layout.setSpacing(4)

            self._place_hand_guides_btn = QtWidgets.QPushButton(
                "Place Hand Guides"
            )
            self._place_hand_guides_btn.setToolTip(
                "Re-snap wrist + finger guide pins onto the body model.\n"
                "Run this *after* Generate Skeleton so AcuRig knows the\n"
                "final bone positions."
            )
            self._place_hand_guides_btn.clicked.connect(
                self.placeHandGuidesRequested.emit
            )
            hand_layout.addWidget(self._place_hand_guides_btn)

            # Per-bone mask checkboxes — six rows in a 2-column grid
            # (left side on the left, right side on the right).
            mask_group = QtWidgets.QGroupBox("Per-bone weight mask")
            mask_group.setToolTip(
                "Tick to exclude a bone from heat-map weight painting.\n"
                "Useful when a hand mesh's fingers shouldn't move with\n"
                "the wrist (e.g. mitten-style gloves on PFBC bodies)."
            )
            mask_layout = QtWidgets.QGridLayout(mask_group)
            mask_layout.setContentsMargins(6, 6, 6, 6)
            mask_layout.setHorizontalSpacing(12)
            mask_layout.setVerticalSpacing(2)

            # The six bones we expose — kept in lock-step with
            # ``headless_body_workflow.HAND_BONES``.
            _HAND_BONES_UI = (
                ("lforearm",  0, 0),
                ("lhand",     1, 0),
                ("lfinger01", 2, 0),
                ("rforearm",  0, 1),
                ("rhand",     1, 1),
                ("rfinger01", 2, 1),
            )
            self._hand_mask_checkboxes: Dict[str, QtWidgets.QCheckBox] = {}
            for bone, row, col in _HAND_BONES_UI:
                cb = QtWidgets.QCheckBox(bone)
                cb.setToolTip(f"Exclude '{bone}' from auto-skin weights.")
                # Capture ``bone`` by default-arg to dodge late-binding.
                cb.toggled.connect(
                    lambda checked, b=bone:
                        self.handMaskChanged.emit(b, bool(checked))
                )
                mask_layout.addWidget(cb, row, col)
                self._hand_mask_checkboxes[bone] = cb
            hand_layout.addWidget(mask_group)

            self._hand_rig_status = QtWidgets.QLabel(
                "Hand guides not placed yet."
            )
            self._hand_rig_status.setStyleSheet(
                f"color:{C.get('text2', '#888')}; font-size:8pt;"
            )
            self._hand_rig_status.setWordWrap(True)
            hand_layout.addWidget(self._hand_rig_status)

            layout.addWidget(hand_actions)

    def set_hand_rig_status(self, message: str, *, kind: str = "info") -> None:
        """Update the hand-rig status line (M5 / T504).

        Mirrors :meth:`set_body_rig_status` — accepts ``"info" / "ok"
        / "warning" / "error"`` and recolours the label accordingly.
        """
        label = getattr(self, "_hand_rig_status", None)
        if label is None:                                   # pragma: no cover
            return
        palette = {
            "info":    "#888888",
            "ok":      "#7ed957",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }
        colour = palette.get(kind, palette["info"])
        label.setStyleSheet(f"color:{colour}; font-size:8pt;")
        label.setText(message)

    def set_hand_masked_bones(self, masked: List[str]) -> None:
        """Reflect the AcuRig BoneMask state into the checkbox column.

        Called by the Character Builder window after
        :func:`place_hand_guides` so the UI starts in sync with whatever
        the AcuRig instance already knows.  Programmatic toggle is
        wrapped in a ``QSignalBlocker`` so we don't re-emit
        ``handMaskChanged`` and create a feedback loop.
        """
        checkboxes = getattr(self, "_hand_mask_checkboxes", None)
        if not checkboxes:                                  # pragma: no cover
            return
        masked_set = set(masked or ())
        for bone, cb in checkboxes.items():
            with QtCore.QSignalBlocker(cb):
                cb.setChecked(bone in masked_set)

    def set_body_rig_status(self, message: str, *, kind: str = "info") -> None:
        """Update the body-rig status line (M5 / T503).

        ``kind`` is one of ``"info" / "ok" / "warning" / "error"`` and
        drives the label colour.  Called by the Character Builder
        window after :func:`place_body_guides` / :func:`generate_skeleton`.
        """
        label = getattr(self, "_body_rig_status", None)
        if label is None:                                   # pragma: no cover
            return
        palette = {
            "info":    "#888888",
            "ok":      "#7ed957",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }
        colour = palette.get(kind, palette["info"])
        label.setStyleSheet(f"color:{colour}; font-size:8pt;")
        label.setText(message)

    def _populate_check_actor_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        """M5 / T505 — Check-Actor step: preview-animation player.

        Replaces the M2 legacy ``Run ROM Test`` stub.  Lists the curated
        preview clips from ``headless_body_workflow.PREVIEW_ANIMATIONS``
        (idle / walk / run / talk / dodge), greys out those not present
        on the body model, and dispatches Play / Stop to the M4 viewport
        via ``viewport.set_animation_pose``.
        """
        layout.addWidget(QtWidgets.QLabel(
            "Preview a standard animation on the rigged body to QC the\n"
            "skeleton + weights.  Missing clips are greyed out."
        ))

        # Preview-clip dropdown.
        anim_row = QtWidgets.QHBoxLayout()
        anim_row.addWidget(QtWidgets.QLabel("Preview:"))
        self._preview_anim_combo = QtWidgets.QComboBox()
        self._preview_anim_combo.setMinimumWidth(160)
        self._preview_anim_combo.setEditable(False)
        self._preview_anim_combo.setToolTip(
            "Choose which preview animation to play.\n"
            "Available clips come from KotorModel.animations."
        )
        anim_row.addWidget(self._preview_anim_combo, 1)
        layout.addLayout(anim_row)

        # Play / Stop / Refresh row.
        btn_row = QtWidgets.QHBoxLayout()

        self._preview_play_btn = QtWidgets.QPushButton("Play")
        self._preview_play_btn.setProperty("accent", True)
        self._preview_play_btn.setToolTip(
            "Dispatch the selected clip to viewport.set_animation_pose."
        )

        def _emit_play():
            name = self._preview_anim_combo.currentData()
            if not name:
                name = self._preview_anim_combo.currentText()
            if name:
                self.playPreviewAnimationRequested.emit(str(name))

        self._preview_play_btn.clicked.connect(_emit_play)
        btn_row.addWidget(self._preview_play_btn)

        self._preview_stop_btn = QtWidgets.QPushButton("Stop")
        self._preview_stop_btn.setToolTip(
            "Halt the current preview (viewport.set_animation_pose(None))."
        )
        self._preview_stop_btn.clicked.connect(
            self.stopPreviewAnimationRequested.emit
        )
        btn_row.addWidget(self._preview_stop_btn)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setProperty("compact", True)
        refresh_btn.setToolTip(
            "Re-scan KotorModel.animations and rebuild the list."
        )
        refresh_btn.clicked.connect(
            self.refreshPreviewAnimationsRequested.emit
        )
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Status / tally label.
        self._preview_status = QtWidgets.QLabel(
            "Click Refresh after generating the skeleton."
        )
        self._preview_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt;"
        )
        self._preview_status.setWordWrap(True)
        layout.addWidget(self._preview_status)

    def set_preview_animations(
        self,
        available,                       # List[Tuple[label, name]]
        missing,                         # List[Tuple[label, name]]
    ) -> None:
        """Rebuild the preview-anim dropdown (M5 / T505).

        ``available`` entries are added as enabled rows; ``missing``
        entries are added with their item flags cleared so they appear
        greyed-out (matching the QListWidget disabled-item convention).
        """
        combo = getattr(self, "_preview_anim_combo", None)
        if combo is None:                                   # pragma: no cover
            return
        with QtCore.QSignalBlocker(combo):
            combo.clear()
            for label, name in (available or []):
                combo.addItem(f"{label} ({name})", userData=name)
            # Missing entries — keep them in the list but disable
            # selection so the user sees what *should* be there.
            base_idx = combo.count()
            for label, name in (missing or []):
                combo.addItem(f"{label} ({name}) — missing", userData="")
            # Disable the trailing 'missing' rows.
            model = combo.model()
            if model is not None:
                from PySide6.QtCore import Qt  # local import for clarity
                for offset in range(len(missing or [])):
                    idx = model.index(base_idx + offset, 0)
                    if idx.isValid():
                        flags = model.flags(idx)
                        model.setData(
                            idx,
                            flags & ~Qt.ItemIsEnabled,
                            Qt.UserRole - 1,            # Qt::ItemFlags role
                        )

        # Sensible default: first enabled (== first available) row.
        if available:
            combo.setCurrentIndex(0)

    def set_preview_status(self, message: str, *, kind: str = "info") -> None:
        """Update the check-actor status line (M5 / T505)."""
        label = getattr(self, "_preview_status", None)
        if label is None:                                   # pragma: no cover
            return
        palette = {
            "info":    "#888888",
            "ok":      "#7ed957",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }
        colour = palette.get(kind, palette["info"])
        label.setStyleSheet(f"color:{colour}; font-size:8pt;")
        label.setText(message)

    def _populate_motions_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        """M5 / T505 — Add Motions step: shares the preview-animation
        player UI with the Check-Actor step.

        The legacy ``Open Animation Library…`` stub is retired here —
        the actual full animation library lives behind ``addMotionsRequested``
        and is M11 work.  For M5 we surface the same preview-clip dropdown
        + Play / Stop / Refresh controls so the user can sanity-check
        animations from this step too.
        """
        layout.addWidget(QtWidgets.QLabel(
            "Attach KOTOR motions (idle / walk / talk / combat) to this\n"
            "character.  Use the preview controls below to verify a clip\n"
            "before opening the full library."
        ))
        # Re-use the same widget identifiers — the inspector's current
        # ``step`` selector swaps which page is visible, so reusing the
        # private attribute name keeps T505 logic simple.  However, on
        # the motions page we add a *secondary* status label so we can
        # show preview state without overwriting check-actor's state.
        # (We deliberately don't recreate the combo — the user uses the
        # one on the check-actor page; this page is purely informational
        # until M11.)
        info_btn = QtWidgets.QPushButton("Open Animation Library…")
        info_btn.setToolTip(
            "Opens the full animation-library dialog (M11 work).\n"
            "For preview playback, use the Check Actor step."
        )
        info_btn.clicked.connect(self.addMotionsRequested.emit)
        layout.addWidget(info_btn)

        info = QtWidgets.QLabel(
            "Tip: head to step 6 (Check Actor) to preview walk / idle /\n"
            "talk clips on the rigged body."
        )
        info.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt; font-style:italic;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

    def _populate_validate_page(self, layout: QtWidgets.QVBoxLayout) -> None:
        """M5 / T506 — Validate + Export step.

        Replaces the M2 legacy ``Open Export Panel…`` stub with a
        proper two-button workflow:
          1. **Validate Scene** — runs the full strict ValidationService
             and surfaces a tally + per-severity tags.
          2. **Export…** — opens the modal :class:`QtExportDialog`
             (format checkboxes + output dir + sidecar toggle); the
             window slot wires the dialog's accept signal to
             ``headless_body_workflow.export_scene``.
        """
        layout.addWidget(QtWidgets.QLabel(
            "Run final validation, then export the rigged body to one\n"
            "or more formats (KOTOR / FBX / glTF / OBJ) plus a\n"
            ".ghostrig.json scene-definition sidecar."
        ))

        # ── Validation tally label ──────────────────────────────────
        self._validate_tally = QtWidgets.QLabel(
            "Validation not yet run."
        )
        self._validate_tally.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:9pt;"
        )
        self._validate_tally.setWordWrap(True)
        layout.addWidget(self._validate_tally)

        # ── Validate / Export button row ────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        validate_btn = QtWidgets.QPushButton("Validate Scene")
        validate_btn.setToolTip(
            "Run ValidationService with strict=True; surfaces any\n"
            "blocker codes that would prevent export."
        )
        validate_btn.clicked.connect(self.validateRequested.emit)
        btn_row.addWidget(validate_btn)

        self._export_btn = QtWidgets.QPushButton("Export…")
        self._export_btn.setProperty("accent", True)
        self._export_btn.setToolTip(
            "Open the export dialog: pick formats + output folder,\n"
            "write the sidecar JSON.  Blocked when validation has\n"
            "reported any ERROR-severity issues."
        )
        # M5 / T506 — the button now emits ``exportRequested`` which
        # the window opens the QtExportDialog from (replacing the
        # legacy 'Open Export Panel…' stub that opened nothing).
        self._export_btn.clicked.connect(self.exportRequested.emit)
        btn_row.addWidget(self._export_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # ── Status / last-export label ──────────────────────────────
        self._export_status = QtWidgets.QLabel("")
        self._export_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt;"
        )
        self._export_status.setWordWrap(True)
        layout.addWidget(self._export_status)

    # ── M5 / T506 — Validate + Export setters ────────────────────────

    def set_validate_for_export_result(self, result) -> None:
        """Push a :class:`ValidateForExportResult` into the page.

        Updates the tally label (with per-severity counts + blocker
        codes) and enables/disables the Export button based on
        ``result.ok``.
        """
        tally = getattr(self, "_validate_tally", None)
        if tally is None:                                    # pragma: no cover
            return
        ok = bool(getattr(result, "ok", False))
        e = int(getattr(result, "error_count", 0))
        w = int(getattr(result, "warning_count", 0))
        i = int(getattr(result, "info_count", 0))
        code = str(getattr(result, "code", "")) or ""
        msg = str(getattr(result, "message", "")) or ""

        # Pick the colour based on severity worst-case.
        if e > 0:
            colour = "#ff6b6b"
        elif w > 0:
            colour = "#ffd166"
        elif i > 0:
            colour = "#9bbcff"
        else:
            colour = "#7ed957"

        parts = [
            f"<span style='color:#ff6b6b;'>{e} error(s)</span>",
            f"<span style='color:#ffd166;'>{w} warning(s)</span>",
            f"<span style='color:#9bbcff;'>{i} info</span>",
        ]
        blockers = list(getattr(result, "blocking_codes", []) or [])
        if blockers:
            parts.append(
                "Blockers: " + ", ".join(blockers[:6])
                + (" …" if len(blockers) > 6 else "")
            )
        tally.setStyleSheet(f"color:{colour}; font-size:9pt;")
        tally.setText(" • ".join(parts) + ("\n" + msg if msg else ""))
        tally.setTextFormat(QtCore.Qt.RichText)

        # Disable Export when blocked.
        btn = getattr(self, "_export_btn", None)
        if btn is not None:
            btn.setEnabled(ok)
            btn.setToolTip(
                "Export is blocked — fix the ERROR-severity issues first."
                if not ok else
                "Open the export dialog: pick formats + output folder,\n"
                "write the sidecar JSON."
            )

    def set_export_status(self, message: str, *, kind: str = "info") -> None:
        """Update the export-result status line (M5 / T506)."""
        label = getattr(self, "_export_status", None)
        if label is None:                                    # pragma: no cover
            return
        palette = {
            "info":    "#888888",
            "ok":      "#7ed957",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }
        colour = palette.get(kind, palette["info"])
        label.setStyleSheet(f"color:{colour}; font-size:8pt;")
        label.setText(message)

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
