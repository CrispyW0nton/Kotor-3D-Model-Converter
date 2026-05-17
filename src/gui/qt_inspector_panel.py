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
    - ``addMotionsRequested()``           — legacy Animation Library hook.
    - ``assignMotionsRequested()``        — applies selected motion source.
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
    assignMotionsRequested    = QtCore.Signal()
    motionSourceChanged       = QtCore.Signal(str)
    motionSupermodelChanged   = QtCore.Signal(str)
    exportRequested           = QtCore.Signal()
    loadRequested             = QtCore.Signal()
    fitAdjustmentChanged      = QtCore.Signal(float, float, float, float)
    fitAdjustmentResetRequested = QtCore.Signal()
    validateRequested         = QtCore.Signal()
    checkModelRequested       = QtCore.Signal()
    romTestRequested          = QtCore.Signal()
    # M5 / T503 — body-rig generation
    placeGuidesRequested      = QtCore.Signal()
    generateSkeletonRequested = QtCore.Signal()
    # M12 / T1202 — KOTOR skeleton template selection for imported meshes.
    skeletonTemplateSelected  = QtCore.Signal(str)        # (option_key,)
    browseSkeletonTemplateRequested = QtCore.Signal()
    applySkeletonTemplateRequested = QtCore.Signal()
    # M5 / T504 — Hand-rig step.
    placeHandGuidesRequested  = QtCore.Signal()
    handMaskChanged           = QtCore.Signal(str, bool)  # (bone, masked?)
    # M5 / T505 — Check-actor step.
    playPreviewAnimationRequested = QtCore.Signal(str)    # (anim_name,)
    stopPreviewAnimationRequested = QtCore.Signal()
    refreshPreviewAnimationsRequested = QtCore.Signal()
    # M6 / T602 — Head-mode facial-bone palette.
    headFacialBoneSelected    = QtCore.Signal(str)        # (bone_name,)
    rigHeadRequested          = QtCore.Signal()           # Head Rig step (M6/T601)
    rigFaceRequested          = QtCore.Signal()           # Face Rig step (M6/T601)
    # M6 / T603 — Viseme test panel (16 LIPShape buttons).
    applyVisemeRequested      = QtCore.Signal(int)        # (viseme_index,)
    # M6 / T604 — Phoneme calibration (8 phoneme → viseme mappings).
    calibratePhonemeRequested = QtCore.Signal(str, int)   # (label, viseme_index)
    # M6 / T605 — Head-mode camera preset request.
    headCameraPresetRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        # Maps step_number → QStackedWidget page index for fast lookup.
        self._step_to_index: Dict[int, int] = {}
        self._joint_combos: List[QtWidgets.QComboBox] = []
        # M6 / T602 — track the active CharacterMode so the inspector
        # can swap between the legacy face-rig stubs and the Head
        # facial-bone palette without rebuilding the whole stack.
        self._active_mode = None
        # Widget references populated by _populate_rig_page for the
        # face-rig page — needed by ``set_active_mode`` to toggle.
        self._face_legacy_widgets: List[QtWidgets.QWidget] = []
        self._head_face_palette: Optional[QtWidgets.QGroupBox] = None
        self._head_face_buttons: Dict[str, QtWidgets.QPushButton] = {}
        # M6 / T603 — Viseme test panel (16 LIPShape buttons keyed by
        # the integer viseme index).  Only visible while the inspector
        # is in HEAD mode; toggled by :meth:`set_active_mode`.
        self._head_viseme_panel: Optional[QtWidgets.QGroupBox] = None
        self._head_viseme_buttons: Dict[int, QtWidgets.QPushButton] = {}
        # M6 / T604 — Phoneme calibration panel (8 phoneme→viseme combos).
        # Same visibility rule as the viseme panel.
        self._head_phoneme_panel: Optional[QtWidgets.QGroupBox] = None
        self._head_phoneme_combos: Dict[str, QtWidgets.QComboBox] = {}
        # M12 / T1202 — AccuRig-style skeleton picker on the body-rig HUD.
        self._skeleton_template_combo: Optional[QtWidgets.QComboBox] = None
        self._skeleton_template_status: Optional[QtWidgets.QLabel] = None
        self._apply_skeleton_template_btn: Optional[QtWidgets.QPushButton] = None
        self._fit_scale_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._fit_rot_x_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._fit_rot_y_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._fit_rot_z_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._fit_adjust_status: Optional[QtWidgets.QLabel] = None
        # M12 / T1204 — mode-aware motion assignment.
        self._motion_source_combo: Optional[QtWidgets.QComboBox] = None
        self._motion_supermodel_combo: Optional[QtWidgets.QComboBox] = None
        self._motion_assignment_status: Optional[QtWidgets.QLabel] = None
        self._rom_test_btn: Optional[QtWidgets.QPushButton] = None
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
            "Choose the KOTOR base model/skeleton first, then load the\n"
            "custom MDL / FBX / OBJ mesh that should fit that rig."
        ))
        self._add_skeleton_template_picker(layout)
        btn = QtWidgets.QPushButton("Load Character…")
        btn.setProperty("accent", True)
        btn.clicked.connect(self.loadRequested.emit)
        layout.addWidget(btn)

        fit_group = QtWidgets.QGroupBox("Import Fit")
        fit_layout = QtWidgets.QGridLayout(fit_group)
        fit_layout.setContentsMargins(8, 8, 8, 8)
        fit_layout.setHorizontalSpacing(6)
        fit_layout.setVerticalSpacing(4)

        self._fit_scale_spin = QtWidgets.QDoubleSpinBox()
        self._fit_scale_spin.setRange(1.0, 1000.0)
        self._fit_scale_spin.setValue(100.0)
        self._fit_scale_spin.setSingleStep(1.0)
        self._fit_scale_spin.setSuffix("%")
        self._fit_scale_spin.setToolTip("Manual scale after auto-fit.")
        fit_layout.addWidget(QtWidgets.QLabel("Scale"), 0, 0)
        fit_layout.addWidget(self._fit_scale_spin, 0, 1, 1, 3)

        spin_specs = [
            ("Rot X", "_fit_rot_x_spin"),
            ("Rot Y", "_fit_rot_y_spin"),
            ("Rot Z", "_fit_rot_z_spin"),
        ]
        for row, (label, attr) in enumerate(spin_specs, start=1):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-180.0, 180.0)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setSuffix(" deg")
            spin.setToolTip("Manual orientation after auto-fit. Viewport rotation drags snap to 10 deg while Shift is held.")
            setattr(self, attr, spin)
            fit_layout.addWidget(QtWidgets.QLabel(label), row, 0)
            fit_layout.addWidget(spin, row, 1, 1, 3)

        reset_btn = QtWidgets.QPushButton("Reset Fit")
        reset_btn.clicked.connect(self.fitAdjustmentResetRequested.emit)
        fit_layout.addWidget(reset_btn, 4, 0, 1, 2)

        self._fit_adjust_status = QtWidgets.QLabel("Auto-fit can be fine-tuned after import.")
        self._fit_adjust_status.setWordWrap(True)
        self._fit_adjust_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt;"
        )
        fit_layout.addWidget(self._fit_adjust_status, 4, 2, 1, 2)

        for spin in (
            self._fit_scale_spin,
            self._fit_rot_x_spin,
            self._fit_rot_y_spin,
            self._fit_rot_z_spin,
        ):
            if spin is not None:
                spin.valueChanged.connect(self._emit_fit_adjustment)
        layout.addWidget(fit_group)

    def _add_skeleton_template_picker(self, layout: QtWidgets.QVBoxLayout) -> None:
        """AccuRig-style base-skeleton picker shown before custom import."""
        template_group = QtWidgets.QGroupBox("KOTOR Base Skeleton")
        template_layout = QtWidgets.QVBoxLayout(template_group)
        template_layout.setSpacing(4)

        template_row = QtWidgets.QHBoxLayout()
        template_row.addWidget(QtWidgets.QLabel("Base:"))
        self._skeleton_template_combo = QtWidgets.QComboBox()
        self._skeleton_template_combo.setEditable(True)
        self._skeleton_template_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self._skeleton_template_combo.setMaxVisibleItems(18)
        self._skeleton_template_combo.setMinimumWidth(160)
        self._skeleton_template_combo.setToolTip(
            "Pick the shipped KOTOR body/creature model that the imported mesh "
            "should match for scale, orientation, hooks, and animation retargeting."
        )
        self._skeleton_template_combo.currentIndexChanged.connect(
            self._on_skeleton_template_index_changed
        )
        if self._skeleton_template_combo.lineEdit() is not None:
            self._skeleton_template_combo.lineEdit().setPlaceholderText(
                "Search resref, e.g. pmbam or n_sithsoldier"
            )
            self._skeleton_template_combo.lineEdit().returnPressed.connect(
                self._emit_skeleton_template_from_text
            )
        template_row.addWidget(self._skeleton_template_combo, 1)
        template_layout.addLayout(template_row)

        browse_btn = QtWidgets.QPushButton("Browse MDL...")
        browse_btn.setToolTip(
            "Choose any body/creature MDL from your KOTOR install or Override folder."
        )
        browse_btn.clicked.connect(self.browseSkeletonTemplateRequested.emit)
        template_layout.addWidget(browse_btn)

        self._apply_skeleton_template_btn = QtWidgets.QPushButton("Use Skeleton")
        self._apply_skeleton_template_btn.setToolTip(
            "Attach this KOTOR skeleton to the loaded mesh after checking fit."
        )
        self._apply_skeleton_template_btn.clicked.connect(
            self.applySkeletonTemplateRequested.emit
        )
        template_layout.addWidget(self._apply_skeleton_template_btn)

        self._skeleton_template_status = QtWidgets.QLabel(
            "Pick a KOTOR base first. The custom mesh will auto-fit to this preview."
        )
        self._skeleton_template_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt;"
        )
        self._skeleton_template_status.setWordWrap(True)
        template_layout.addWidget(self._skeleton_template_status)
        layout.addWidget(template_group)

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
        btn = QtWidgets.QPushButton("Check Model")
        btn.setProperty("accent", True)
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
        # GroupBox below.  The face step keeps the legacy controls for
        # Creature/Supermodel rigs, but M6 / T602 wraps them in a
        # *legacy* container that :meth:`set_active_mode` hides when
        # the active mode is HEAD — that mode shows the dedicated Head
        # Facial Palette below instead.
        if step == _STEP_RIG_FACE:
            legacy_box = QtWidgets.QGroupBox("Legacy face-rig controls")
            legacy_box.setToolTip(
                "AcuRig-style mask + midpoint placement.  Hidden in "
                "Head mode (replaced by the Head Facial Palette).")
            legacy_layout = QtWidgets.QVBoxLayout(legacy_box)
            legacy_layout.setContentsMargins(6, 6, 6, 6)
            legacy_layout.setSpacing(4)

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
            legacy_layout.addLayout(mask_row)

            midpoint_btn = QtWidgets.QPushButton("Midpoint Placement")
            midpoint_btn.setToolTip("Snap the active pin to the volume centroid "
                                    "(accurig.midpoint_placement).")
            midpoint_btn.clicked.connect(self.midpointPlacementRequested.emit)
            legacy_layout.addWidget(midpoint_btn)

            layout.addWidget(legacy_box)
            # Track so :meth:`set_active_mode` can hide for HEAD.
            self._face_legacy_widgets.append(legacy_box)

            # ── M6 / T602 — Head Facial Palette ────────────────────
            # Hidden by default; revealed by ``set_active_mode(HEAD)``.
            # Maps every canonical KotOR facial bone to a clickable
            # button that emits ``headFacialBoneSelected(name)`` so the
            # Character Builder window can route the click to the M4
            # joint-dot HUD highlight.
            head_palette = self._build_head_facial_palette()
            layout.addWidget(head_palette)
            head_palette.setVisible(False)
            self._head_face_palette = head_palette

            # ── M6 / T603 — Viseme Test Panel ──────────────────────
            # 16 LIPShape buttons in a 4×4 grid.  Same visibility rule
            # as the facial palette: HEAD mode only.
            viseme_panel = self._build_viseme_panel()
            layout.addWidget(viseme_panel)
            viseme_panel.setVisible(False)
            self._head_viseme_panel = viseme_panel

            # ── M6 / T604 — Phoneme Calibration Panel ───────────────
            # Eight phoneme rows (label + viseme combo + apply btn).
            # HEAD-mode visibility, same toggle path as the palette
            # and viseme panel.
            phoneme_panel = self._build_phoneme_panel()
            layout.addWidget(phoneme_panel)
            phoneme_panel.setVisible(False)
            self._head_phoneme_panel = phoneme_panel

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
            actions = QtWidgets.QGroupBox("Rig Body")
            actions_layout = QtWidgets.QVBoxLayout(actions)
            actions_layout.setSpacing(4)

            self._place_guides_btn = QtWidgets.QPushButton("Place Body Guides")
            self._place_guides_btn.setToolTip(
                "Snap AcuRig humanoid guide pins onto the body model.\n"
                "Use the joint-dot HUD to fine-tune positions; drag with\n"
                "Symmetry enabled to mirror across the X axis."
            )
            self._place_guides_btn.clicked.connect(self.placeGuidesRequested.emit)
            actions_layout.addWidget(self._place_guides_btn)

            self._generate_skeleton_btn = QtWidgets.QPushButton("Rig Body")
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
            hand_actions = QtWidgets.QGroupBox("Rig Hand")
            hand_layout = QtWidgets.QVBoxLayout(hand_actions)
            hand_layout.setSpacing(4)

            self._place_hand_guides_btn = QtWidgets.QPushButton("Rig Hand")
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

    def set_skeleton_template_options(self, options: Iterable[object]) -> None:
        """Populate the body-rig skeleton-template picker (M12 / T1202)."""
        combo = getattr(self, "_skeleton_template_combo", None)
        if combo is None:                                  # pragma: no cover
            return

        def _field(option: object, name: str, default: object = "") -> object:
            if isinstance(option, dict):
                return option.get(name, default)
            return getattr(option, name, default)

        combo.blockSignals(True)
        try:
            combo.clear()
            for option in options or ():
                key = str(_field(option, "key", "") or "")
                if not key:
                    continue
                try:
                    from core.skeleton_template_picker import option_summary
                except Exception:                          # pragma: no cover
                    try:
                        from src.core.skeleton_template_picker import option_summary
                    except Exception:
                        option_summary = None              # type: ignore
                if option_summary is not None:
                    try:
                        label = option_summary(option)      # type: ignore[arg-type]
                    except Exception:
                        label = ""
                else:
                    label = ""
                if not label:
                    label = str(_field(option, "name", "") or key)
                combo.addItem(label, key)
                idx = combo.count() - 1
                tooltip_bits = [
                    str(_field(option, "description", "") or ""),
                    str(_field(option, "path", "") or ""),
                ]
                warnings = _field(option, "warnings", []) or []
                if warnings:
                    tooltip_bits.append("Warnings: " + "; ".join(map(str, warnings)))
                tooltip = "\n".join(bit for bit in tooltip_bits if bit)
                if tooltip:
                    combo.setItemData(idx, tooltip, QtCore.Qt.ToolTipRole)
        finally:
            combo.blockSignals(False)

        has_options = combo.count() > 0
        combo.setEnabled(has_options)
        if combo.completer() is not None:
            combo.completer().setFilterMode(QtCore.Qt.MatchContains)
            combo.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        if self._apply_skeleton_template_btn is not None:
            self._apply_skeleton_template_btn.setEnabled(has_options)
        if has_options:
            combo.setCurrentIndex(0)
            self.skeletonTemplateSelected.emit(str(combo.currentData() or ""))
        else:
            self.set_skeleton_template_status(
                "No skeleton templates found for this game/mode.",
                kind="warning",
            )

    def selected_skeleton_template_key(self) -> str:
        combo = getattr(self, "_skeleton_template_combo", None)
        if combo is None:
            return ""
        current = str(combo.currentData() or "")
        if current:
            return current
        typed = combo.currentText().strip().lower()
        if typed:
            for idx in range(combo.count()):
                label = combo.itemText(idx).strip().lower()
                data = str(combo.itemData(idx) or "").strip().lower()
                if typed == label or typed == data or typed in label or typed in data:
                    return str(combo.itemData(idx) or "")
        return ""

    def set_selected_skeleton_template_key(
        self,
        key: str,
        *,
        emit: bool = True,
    ) -> bool:
        combo = getattr(self, "_skeleton_template_combo", None)
        if combo is None:
            return False
        idx = combo.findData(str(key or ""))
        if idx < 0:
            return False
        combo.blockSignals(not emit)
        try:
            combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)
        if emit:
            self.skeletonTemplateSelected.emit(str(key or ""))
        return True

    def set_skeleton_template_status(
        self, message: str, *, kind: str = "info"
    ) -> None:
        label = getattr(self, "_skeleton_template_status", None)
        if label is None:                                  # pragma: no cover
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
        """M12 / T1204 — assign KOTOR motion source for export."""
        layout.addWidget(QtWidgets.QLabel(
            "Choose how this character gets KOTOR animation clips."
        ))

        source_box = QtWidgets.QGroupBox("Motion Source")
        source_layout = QtWidgets.QFormLayout(source_box)
        source_layout.setContentsMargins(8, 8, 8, 8)
        source_layout.setSpacing(6)

        self._motion_source_combo = QtWidgets.QComboBox()
        for label, key in [
            ("Inherit PC supermodel", "inherited_supermodel"),
            ("Use model clips", "model"),
            ("Imported clips", "imported"),
            ("Generated ROM", "generated_rom"),
        ]:
            self._motion_source_combo.addItem(label, key)
        self._motion_source_combo.setToolTip(
            "Pick whether export should inherit a KOTOR supermodel, "
            "use clips already stored on the model, imported clips, or ROM."
        )
        self._motion_source_combo.currentIndexChanged.connect(
            lambda _i: self.motionSourceChanged.emit(
                str(self._motion_source_combo.currentData() or "")
            )
        )
        source_layout.addRow("Source:", self._motion_source_combo)

        self._motion_supermodel_combo = QtWidgets.QComboBox()
        self._motion_supermodel_combo.setEditable(True)
        for label, value in [
            ("K1 Female PC - S_Female02", "S_Female02"),
            ("K1 Female PC ext - S_Female03", "S_Female03"),
            ("K1 Male PC - S_Male02", "S_Male02"),
            ("K1 Male PC ext - S_Male03", "S_Male03"),
            ("K2 Female PC - S_Female02", "S_Female02"),
            ("K2 Female PC ext - S_Female03", "S_Female03"),
            ("K2 Male PC - S_Male02", "S_Male02"),
            ("K2 Male PC ext - S_Male03", "S_Male03"),
        ]:
            self._motion_supermodel_combo.addItem(label, value)
        self._motion_supermodel_combo.setToolTip(
            "KOTOR supermodel written to the body MDL when inheriting motions."
        )
        self._motion_supermodel_combo.currentTextChanged.connect(
            lambda text: self.motionSupermodelChanged.emit(str(text or ""))
        )
        source_layout.addRow("Supermodel:", self._motion_supermodel_combo)
        layout.addWidget(source_box)

        btn_row = QtWidgets.QHBoxLayout()
        assign_btn = QtWidgets.QPushButton("Assign Motions")
        assign_btn.setProperty("accent", True)
        assign_btn.clicked.connect(self.assignMotionsRequested.emit)
        btn_row.addWidget(assign_btn)

        refresh_btn = QtWidgets.QPushButton("Refresh Preview")
        refresh_btn.clicked.connect(self.refreshPreviewAnimationsRequested.emit)
        btn_row.addWidget(refresh_btn)

        self._rom_test_btn = QtWidgets.QPushButton("Run ROM")
        self._rom_test_btn.setProperty("accent", True)
        self._rom_test_btn.setToolTip(
            "Assign the generated range-of-motion clip and start the ROM preview."
        )
        self._rom_test_btn.clicked.connect(self.romTestRequested.emit)
        btn_row.addWidget(self._rom_test_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._motion_assignment_status = QtWidgets.QLabel(
            "Motion assignment not set."
        )
        self._motion_assignment_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt;"
        )
        self._motion_assignment_status.setWordWrap(True)
        layout.addWidget(self._motion_assignment_status)

    def selected_motion_source(self) -> str:
        combo = getattr(self, "_motion_source_combo", None)
        if combo is None:
            return "model"
        return str(combo.currentData() or "model")

    def selected_motion_supermodel(self) -> str:
        combo = getattr(self, "_motion_supermodel_combo", None)
        if combo is None:
            return ""
        data = combo.currentData()
        text = combo.currentText()
        if text and text != combo.itemText(combo.currentIndex()):
            return str(text).strip()
        return str(data or text or "").strip()

    def set_motion_assignment_status(self, message: str, *, kind: str = "info") -> None:
        label = getattr(self, "_motion_assignment_status", None)
        if label is None:                                   # pragma: no cover
            return
        palette = {
            "info":    "#888888",
            "ok":      "#7ed957",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }
        label.setStyleSheet(
            f"color:{palette.get(kind, palette['info'])}; font-size:8pt;"
        )
        label.setText(message)

    def set_motion_assignment(self, *, source: str = "", supermodel: str = "") -> None:
        source_combo = getattr(self, "_motion_source_combo", None)
        if source_combo is not None and source:
            for i in range(source_combo.count()):
                if str(source_combo.itemData(i) or "") == source:
                    source_combo.setCurrentIndex(i)
                    break
        sm_combo = getattr(self, "_motion_supermodel_combo", None)
        if sm_combo is not None and supermodel:
            for i in range(sm_combo.count()):
                if str(sm_combo.itemData(i) or "").lower() == supermodel.lower():
                    sm_combo.setCurrentIndex(i)
                    return
            sm_combo.setEditText(supermodel)

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

    # ── M6 / T602 — Head Facial Palette helpers ──────────────────────────

    def _build_head_facial_palette(self) -> QtWidgets.QGroupBox:
        """Build the Head Facial Palette GroupBox (M6 / T602).

        Lays out three rows of bone buttons:

          * **Required** (red trim)      — head_g, f_jaw_g, f_um_g
          * **Recommended** (amber trim) — necklwr_g, neck_g, lip corners,
            mask/goggle hooks
          * **Face Rig** (gold trim)     — f_jaw_g, f_um_g, eye / lid /
            lip-corner bones from ``head_workflow.FACE_RIG_BONES``

        Each button emits :sig:`headFacialBoneSelected` with the bone
        name; the Character Builder window forwards that to the
        viewport's joint-dot HUD so the matching dot lights up.

        The bone name lists are imported from
        :mod:`src.core.head_workflow` to keep this UI in lock-step with
        the M6/T601 workflow service.  Import failure (e.g. during
        ``pytest`` runs that bypass ``src.core.__init__``) is tolerated:
        the palette renders empty but still draws a header so the user
        sees the page is HEAD-mode aware.
        """
        # Lazy-import the constants — same fallback ordering the
        # workflow modules use so the panel works regardless of how
        # ``src/`` was placed onto ``sys.path``.  Falls back to a
        # direct-file load when ``core/__init__`` would pull in
        # PyKotor (which isn't installed in lightweight test envs).
        hw = None                                             # type: ignore
        try:
            from src.core import head_workflow as hw          # type: ignore
        except Exception:
            try:
                from core import head_workflow as hw          # type: ignore
            except Exception:
                try:                                          # pragma: no cover
                    import importlib.util as _u
                    import pathlib as _pl
                    _here = _pl.Path(__file__).resolve().parents[1]
                    _hw_path = _here / "core" / "head_workflow.py"
                    if _hw_path.is_file():
                        _spec = _u.spec_from_file_location(
                            "_gr_head_workflow_inline", str(_hw_path),
                        )
                        _mod = _u.module_from_spec(_spec)
                        import sys as _sys
                        _sys.modules[_spec.name] = _mod
                        _spec.loader.exec_module(_mod)
                        hw = _mod
                except Exception:
                    hw = None                                 # type: ignore

        box = QtWidgets.QGroupBox("Head Facial Palette")
        box.setToolTip(
            "Click a bone to highlight its joint dot in the viewport.\n"
            "Required (red) bones must be present for rigging; "
            "recommended (amber) bones improve lip-sync fidelity."
        )
        outer = QtWidgets.QVBoxLayout(box)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        if hw is None:                                        # pragma: no cover
            outer.addWidget(QtWidgets.QLabel(
                "(head_workflow unavailable — palette disabled)"
            ))
            return box

        # ── Step button row ────────────────────────────────────────
        step_row = QtWidgets.QHBoxLayout()
        rig_head_btn = QtWidgets.QPushButton("Rig Head")
        rig_head_btn.setToolTip(
            "Run the neck-chain + jaw skeleton step "
            "(head_workflow.rig_head).")
        rig_head_btn.clicked.connect(self.rigHeadRequested.emit)
        rig_face_btn = QtWidgets.QPushButton("Rig Face")
        rig_face_btn.setProperty("accent", True)
        rig_face_btn.setToolTip(
            "Activate the face-rig palette knobs "
            "(head_workflow.rig_face).")
        rig_face_btn.clicked.connect(self.rigFaceRequested.emit)
        # M6 / T605 — Reset to the canonical Head camera framing.
        reset_cam_btn = QtWidgets.QPushButton("Reset Head Camera")
        reset_cam_btn.setToolTip(
            "Apply the canonical Head camera framing "
            "(head_workflow.head_camera_preset).")
        reset_cam_btn.clicked.connect(self.headCameraPresetRequested.emit)
        self._reset_head_camera_btn = reset_cam_btn
        step_row.addWidget(rig_head_btn)
        step_row.addWidget(rig_face_btn)
        step_row.addWidget(reset_cam_btn)
        step_row.addStretch(1)
        outer.addLayout(step_row)

        # ── Bone-button grids ──────────────────────────────────────
        # Required bones (red trim).
        outer.addWidget(self._build_bone_group(
            "Required",
            hw.REQUIRED_HEAD_BONES.keys(),
            descriptions=hw.REQUIRED_HEAD_BONES,
            colour="#ff6b6b",
        ))
        # Recommended bones (amber trim).
        outer.addWidget(self._build_bone_group(
            "Recommended",
            hw.RECOMMENDED_HEAD_BONES.keys(),
            descriptions=hw.RECOMMENDED_HEAD_BONES,
            colour="#ffd166",
        ))
        # Face-rig bones (gold trim).  Use a static "(face rig knob)"
        # description since the constants list is just a tuple.
        outer.addWidget(self._build_bone_group(
            "Face rig",
            hw.FACE_RIG_BONES,
            descriptions={b: "Face rig knob" for b in hw.FACE_RIG_BONES},
            colour=C.get("gold", "#FFD700"),
        ))

        return box

    def _build_bone_group(
        self,
        title: str,
        bones,
        *,
        descriptions: Dict[str, str],
        colour: str,
    ) -> QtWidgets.QGroupBox:
        """Build a sub-group of bone-buttons for the Head Facial Palette."""
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(
            f"QGroupBox {{ color:{colour}; }}"
        )
        grid = QtWidgets.QGridLayout(group)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        for idx, bone in enumerate(bones):
            row, col = divmod(idx, 2)
            btn = QtWidgets.QPushButton(bone)
            btn.setProperty("compact", True)
            btn.setToolTip(descriptions.get(bone, bone))
            # Capture ``bone`` via default-arg to dodge late binding.
            btn.clicked.connect(
                lambda _checked=False, b=bone:
                    self.headFacialBoneSelected.emit(b)
            )
            grid.addWidget(btn, row, col)
            self._head_face_buttons[bone] = btn
        return group

    def _build_viseme_panel(self) -> QtWidgets.QGroupBox:
        """Build the Viseme Test Panel GroupBox (M6 / T603).

        Renders 16 buttons, one per :class:`lip_reader.LIPShape` index,
        laid out in a 4×4 grid.  Each button emits
        :sig:`applyVisemeRequested` with the integer viseme index; the
        Character Builder window forwards that to
        :func:`head_workflow.apply_viseme` which snaps the head's
        facial bones into the matching pose by evaluating the head's
        ``talk`` animation at the right keyframe.

        The viseme list is pulled from
        :func:`head_workflow.available_visemes` so the panel and the
        runtime always agree on indices.  When ``head_workflow`` cannot
        be imported (lightweight test envs) we fall back to a 16-button
        grid labelled by index only — the buttons still emit, but
        callers may reject out-of-range indices.
        """
        # Lazy-import — same fallback ordering as the facial palette so
        # the panel survives both ``src.``-prefixed and bare ``core``
        # paths, plus a direct-file load for envs where ``core``
        # would eagerly pull in PyKotor.
        hw = None                                             # type: ignore
        try:
            from src.core import head_workflow as hw          # type: ignore
        except Exception:
            try:
                from core import head_workflow as hw          # type: ignore
            except Exception:
                try:                                          # pragma: no cover
                    import importlib.util as _u
                    import pathlib as _pl
                    _here = _pl.Path(__file__).resolve().parents[1]
                    _hw_path = _here / "core" / "head_workflow.py"
                    if _hw_path.is_file():
                        _spec = _u.spec_from_file_location(
                            "_gr_head_workflow_inline_t603", str(_hw_path),
                        )
                        _mod = _u.module_from_spec(_spec)
                        import sys as _sys
                        _sys.modules[_spec.name] = _mod
                        _spec.loader.exec_module(_mod)
                        hw = _mod
                except Exception:
                    hw = None                                 # type: ignore

        box = QtWidgets.QGroupBox("Viseme Test")
        box.setToolTip(
            "Click a viseme to snap the head's facial bones to its pose.\n"
            "Indices correspond to lip_reader.LIPShape (0..15)."
        )
        outer = QtWidgets.QVBoxLayout(box)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # Pull canonical (index, name) tuples; fall back to a placeholder
        # list when the workflow service is unavailable.
        visemes: tuple = tuple()
        if hw is not None:
            try:
                visemes = tuple(hw.available_visemes())
            except Exception:                                 # pragma: no cover
                visemes = tuple()

        if not visemes:                                       # pragma: no cover
            outer.addWidget(QtWidgets.QLabel(
                "(lip_reader unavailable — viseme panel disabled)"
            ))
            return box

        # 4×4 grid of viseme buttons.  Button text is the LIPShape
        # name (e.g. "PP", "AA", "EH") with the index as a leading
        # tag so the user can correlate to the LIP file format.
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(3)
        for slot, (idx, name) in enumerate(visemes):
            row, col = divmod(slot, 4)
            label = f"{idx:>2}  {name}"
            btn = QtWidgets.QPushButton(label)
            btn.setProperty("compact", True)
            btn.setToolTip(
                f"Apply LIPShape {idx} ({name}) to the head's facial bones."
            )
            # Capture ``idx`` via default-arg to dodge late binding.
            btn.clicked.connect(
                lambda _checked=False, i=int(idx):
                    self.applyVisemeRequested.emit(i)
            )
            grid.addWidget(btn, row, col)
            self._head_viseme_buttons[int(idx)] = btn
        outer.addLayout(grid)

        # Status line — updated by :meth:`set_viseme_status`.
        self._viseme_status = QtWidgets.QLabel(
            "Click a viseme to test the head's talk animation."
        )
        self._viseme_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt; font-style:italic;"
        )
        self._viseme_status.setWordWrap(True)
        outer.addWidget(self._viseme_status)

        return box

    def set_viseme_status(self, message: str, *, kind: str = "info") -> None:
        """Update the viseme panel's status line (M6 / T603).

        *kind* is one of ``"info"``, ``"ok"``, ``"warning"``, ``"error"``;
        anything else is treated as ``info``.  Safe to call before the
        panel has been built — silently no-ops in that case.
        """
        if not hasattr(self, "_viseme_status") or self._viseme_status is None:
            return                                           # pragma: no cover
        colour = {
            "ok":      "#7cd87c",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }.get(str(kind).lower(), C.get("text2", "#888"))
        self._viseme_status.setText(str(message))
        self._viseme_status.setStyleSheet(
            f"color:{colour}; font-size:8pt; font-style:italic;"
        )

    def _build_phoneme_panel(self) -> QtWidgets.QGroupBox:
        """Build the Phoneme Calibration Panel GroupBox (M6 / T604).

        Renders one row per entry in :data:`head_workflow.PHONEME_POSES`
        (eight rows):

            ┌──────────────────────────────────────────────────────┐
            │ AH (open vowel)   [▼ 1  EE          ] [Apply]        │
            │ EH (mid vowel)    [▼ 2  EH          ] [Apply]        │
            │ …                                                    │
            └──────────────────────────────────────────────────────┘

        The combo is pre-populated with every entry from
        :func:`head_workflow.available_visemes` (16 LIPShape values),
        with the canonical viseme index for each phoneme pre-selected.
        Clicking the row's *Apply* button emits
        :sig:`calibratePhonemeRequested(label, viseme_index)` carrying
        the combo's currently-selected viseme.

        Falls back to a stub label when ``head_workflow`` is unavailable.
        """
        # Lazy-import — same fallback chain as the other M6 panels.
        hw = None                                             # type: ignore
        try:
            from src.core import head_workflow as hw          # type: ignore
        except Exception:
            try:
                from core import head_workflow as hw          # type: ignore
            except Exception:
                try:                                          # pragma: no cover
                    import importlib.util as _u
                    import pathlib as _pl
                    _here = _pl.Path(__file__).resolve().parents[1]
                    _hw_path = _here / "core" / "head_workflow.py"
                    if _hw_path.is_file():
                        _spec = _u.spec_from_file_location(
                            "_gr_head_workflow_inline_t604", str(_hw_path),
                        )
                        _mod = _u.module_from_spec(_spec)
                        import sys as _sys
                        _sys.modules[_spec.name] = _mod
                        _spec.loader.exec_module(_mod)
                        hw = _mod
                except Exception:
                    hw = None                                 # type: ignore

        box = QtWidgets.QGroupBox("Phoneme Calibration")
        box.setToolTip(
            "Map each canonical phoneme to a LIPShape viseme.\n"
            "These mappings drive lip-sync generation when KotOR\n"
            "renders dialog from a .wav + .lip pair."
        )
        outer = QtWidgets.QVBoxLayout(box)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        phonemes: tuple = tuple()
        visemes: tuple = tuple()
        if hw is not None:
            try:
                phonemes = tuple(hw.PHONEME_POSES)
            except Exception:                                 # pragma: no cover
                phonemes = tuple()
            try:
                visemes = tuple(hw.available_visemes())
            except Exception:                                 # pragma: no cover
                visemes = tuple()

        if not phonemes or not visemes:                       # pragma: no cover
            outer.addWidget(QtWidgets.QLabel(
                "(head_workflow unavailable — phoneme panel disabled)"
            ))
            return box

        # Build the rows.
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(1, 1)                           # combo column grows
        for row, (label, default_idx) in enumerate(phonemes):
            name_lbl = QtWidgets.QLabel(label)
            name_lbl.setToolTip(
                f"{label} — canonical mapping: viseme {default_idx}"
            )

            combo = QtWidgets.QComboBox()
            for idx, vname in visemes:
                combo.addItem(f"{int(idx):>2}  {vname}", int(idx))
            # Pre-select the canonical viseme; tolerate visemes that
            # don't include the canonical index (e.g. truncated test
            # data) by leaving the combo on the first item.
            default_pos = combo.findData(int(default_idx))
            if default_pos >= 0:
                combo.setCurrentIndex(default_pos)
            combo.setToolTip(
                f"Pick the LIPShape viseme that best represents "
                f"the '{label}' mouth shape."
            )

            apply_btn = QtWidgets.QPushButton("Apply")
            apply_btn.setProperty("compact", True)
            apply_btn.setToolTip(
                f"Calibrate '{label}' to the selected viseme "
                f"(head_workflow.calibrate_phoneme)."
            )
            # Capture ``label`` + ``combo`` via default-arg to dodge
            # late binding across loop iterations.
            apply_btn.clicked.connect(
                lambda _checked=False, _label=label, _combo=combo:
                    self.calibratePhonemeRequested.emit(
                        _label, int(_combo.currentData() or 0)
                    )
            )

            grid.addWidget(name_lbl,  row, 0)
            grid.addWidget(combo,     row, 1)
            grid.addWidget(apply_btn, row, 2)
            self._head_phoneme_combos[label] = combo
        outer.addLayout(grid)

        # Status line — updated by :meth:`set_phoneme_status`.
        self._phoneme_status = QtWidgets.QLabel(
            "Choose a viseme per phoneme, then click Apply to calibrate."
        )
        self._phoneme_status.setStyleSheet(
            f"color:{C.get('text2', '#888')}; font-size:8pt; font-style:italic;"
        )
        self._phoneme_status.setWordWrap(True)
        outer.addWidget(self._phoneme_status)

        return box

    def set_phoneme_status(self, message: str, *, kind: str = "info") -> None:
        """Update the phoneme panel's status line (M6 / T604).

        *kind* is one of ``"info"``, ``"ok"``, ``"warning"``, ``"error"``;
        anything else is treated as ``info``.  Safe to call before the
        panel has been built — silently no-ops in that case.
        """
        if not hasattr(self, "_phoneme_status") or self._phoneme_status is None:
            return                                            # pragma: no cover
        colour = {
            "ok":      "#7cd87c",
            "warning": "#ffd166",
            "error":   "#ff6b6b",
        }.get(str(kind).lower(), C.get("text2", "#888"))
        self._phoneme_status.setText(str(message))
        self._phoneme_status.setStyleSheet(
            f"color:{colour}; font-size:8pt; font-style:italic;"
        )

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

    def _on_skeleton_template_index_changed(self, _index: int) -> None:
        key = self.selected_skeleton_template_key()
        if key:
            self.skeletonTemplateSelected.emit(key)

    def _emit_skeleton_template_from_text(self) -> None:
        key = self.selected_skeleton_template_key()
        if not key:
            self.set_skeleton_template_status(
                "No skeleton option matches that search. Use Browse MDL... for a specific game file.",
                kind="warning",
            )
            return
        self.set_selected_skeleton_template_key(key, emit=False)
        self.skeletonTemplateSelected.emit(key)

    def _emit_fit_adjustment(self, *_args) -> None:
        scale = (
            float(self._fit_scale_spin.value()) / 100.0
            if self._fit_scale_spin is not None else 1.0
        )
        rx = float(self._fit_rot_x_spin.value()) if self._fit_rot_x_spin is not None else 0.0
        ry = float(self._fit_rot_y_spin.value()) if self._fit_rot_y_spin is not None else 0.0
        rz = float(self._fit_rot_z_spin.value()) if self._fit_rot_z_spin is not None else 0.0
        self.fitAdjustmentChanged.emit(scale, rx, ry, rz)

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

    def set_fit_adjustment(
        self,
        *,
        scale: float = 1.0,
        rotation_degrees=(0.0, 0.0, 0.0),
        emit: bool = False,
    ) -> None:
        """Set the manual import-fit widgets from scene state."""
        spins = [
            self._fit_scale_spin,
            self._fit_rot_x_spin,
            self._fit_rot_y_spin,
            self._fit_rot_z_spin,
        ]
        for spin in spins:
            if spin is not None:
                spin.blockSignals(not emit)
        try:
            if self._fit_scale_spin is not None:
                self._fit_scale_spin.setValue(float(scale or 1.0) * 100.0)
            values = tuple(float(v or 0.0) for v in rotation_degrees)
            for spin, value in zip(
                (self._fit_rot_x_spin, self._fit_rot_y_spin, self._fit_rot_z_spin),
                values,
            ):
                if spin is not None:
                    spin.setValue(value)
        finally:
            for spin in spins:
                if spin is not None:
                    spin.blockSignals(False)

    def set_fit_adjustment_status(self, message: str, *, kind: str = "info") -> None:
        label = getattr(self, "_fit_adjust_status", None)
        if label is None:
            return
        colour = {
            "ok": "#7cd87c",
            "warning": "#ffd166",
            "error": "#ff6b6b",
        }.get(str(kind).lower(), C.get("text2", "#888"))
        label.setText(str(message))
        label.setStyleSheet(f"color:{colour}; font-size:8pt;")

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

    # ── M6 / T602 — mode-aware page composition ──────────────────────────

    def set_active_mode(self, mode) -> None:
        """Swap the Face-Rig page between legacy and Head-Palette layouts.

        Parameters
        ----------
        mode : :class:`CharacterMode` (or ``None``).  When the value is
               ``CharacterMode.HEAD`` the legacy mask / midpoint controls
               are hidden and the Head Facial Palette becomes visible;
               every other value (including ``None``) restores the
               legacy layout.

        This is the M5-invariant #4 (Inspector page rewrite retires
        legacy stubs) applied to the Face-Rig page for HEAD mode.  The
        widget tree is built once in ``_build`` ; this method only
        toggles visibility so re-applying the same mode is cheap.
        """
        self._active_mode = mode

        # HEAD-mode detection is duck-typed: we accept any object whose
        # ``.value`` or ``.name`` equals the canonical HEAD string.
        # Loading ``CharacterMode`` directly would tie this widget to
        # the pykotor-importing ``core`` package and break unit tests
        # that load the inspector in isolation.
        mode_value = (getattr(mode, "value", None)
                      or getattr(mode, "name", "")
                      or str(mode or "")).lower()
        is_head = mode_value == "head"

        # Toggle the legacy stubs.
        for widget in self._face_legacy_widgets:
            widget.setVisible(not is_head)

        # Toggle the Head Facial Palette.
        if self._head_face_palette is not None:
            self._head_face_palette.setVisible(is_head)

        # M6 / T603 — Toggle the Viseme Test Panel alongside the palette.
        if self._head_viseme_panel is not None:
            self._head_viseme_panel.setVisible(is_head)

        # M6 / T604 — Toggle the Phoneme Calibration Panel as well.
        if self._head_phoneme_panel is not None:
            self._head_phoneme_panel.setVisible(is_head)

        if self._rom_test_btn is not None:
            labels = {
                "headless_body": "Run Body ROM",
                "head": "Run Head ROM",
                "supermodel": "Run Composite ROM",
                "creature": "Run Creature ROM",
            }
            self._rom_test_btn.setText(labels.get(mode_value, "Run ROM"))

    def active_mode(self):
        """Return the most recently applied :class:`CharacterMode` (or ``None``)."""
        return self._active_mode

    def head_facial_bone_buttons(self) -> Dict[str, QtWidgets.QPushButton]:
        """Expose the Head Facial Palette buttons (M6 / T602).

        Returned dict is keyed by bone name so callers (and tests) can
        introspect / drive individual buttons without reaching into
        the private widget tree.
        """
        return dict(self._head_face_buttons)

    def head_viseme_buttons(self) -> Dict[int, QtWidgets.QPushButton]:
        """Expose the Viseme Test Panel buttons (M6 / T603).

        Returned dict is keyed by the integer LIPShape index.  The dict
        is a shallow copy so callers cannot mutate the inspector's
        internal mapping by accident.
        """
        return dict(self._head_viseme_buttons)

    def head_phoneme_combos(self) -> Dict[str, QtWidgets.QComboBox]:
        """Expose the Phoneme Calibration combos (M6 / T604).

        Returned dict is keyed by phoneme label (the canonical entries
        from :data:`head_workflow.PHONEME_POSES`).  Shallow copy —
        callers can introspect each combo's current viseme index via
        ``combo.currentData()`` without binding to private attrs.
        """
        return dict(self._head_phoneme_combos)


__all__ = ["QtInspectorPanel"]
