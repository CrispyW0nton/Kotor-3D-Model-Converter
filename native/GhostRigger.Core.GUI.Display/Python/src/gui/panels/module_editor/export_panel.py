"""Export options panel for KMAP scenes."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleExportPanel(QtWidgets.QWidget):
    targetGameRequested = QtCore.Signal(str)
    exportRequested = QtCore.Signal(bool)
    devTestModuleRequested = QtCore.Signal(bool)
    authoredModuleRequested = QtCore.Signal(bool)
    authoredModuleStageRequested = QtCore.Signal(bool)
    authoredModuleInstallRequested = QtCore.Signal(bool)
    builderFixRequested = QtCore.Signal()
    walkmeshFixRequested = QtCore.Signal()
    placementFixRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()
    selectFixTargetRequested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        self._fix_target_id = ""
        root = QtWidgets.QVBoxLayout(self)
        self.export_scope_label = QtWidgets.QLabel(
            "Export the current KMAP as a complete KOTOR .mod package for K1 or K2."
        )
        self.export_scope_label.setObjectName("mapStudioExportScopeLabel")
        self.export_scope_label.setWordWrap(True)
        target_row = QtWidgets.QWidget(self)
        target_row.setObjectName("mapStudioExportTargetGameRow")
        target_layout = QtWidgets.QVBoxLayout(target_row)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(QtWidgets.QLabel("KOTOR target game"))
        self.target_game_combo = QtWidgets.QComboBox(target_row)
        self.target_game_combo.setObjectName("mapStudioExportTargetGameComboBox")
        self.target_game_combo.addItem("Knights of the Old Republic (K1)", "K1")
        self.target_game_combo.addItem("The Sith Lords (K2)", "K2")
        self.target_game_combo.setToolTip(
            "Retarget the authored KMAP before export. This changes MDL binary flavor and invalidates prior package/game proof."
        )
        self.target_game_combo.activated.connect(self._emit_target_game)
        target_layout.addWidget(self.target_game_combo, 1)
        self.target_game_hint_label = QtWidgets.QLabel(
            "Target changes are transactional and undoable; source-game resrefs remain dependency risks until validation passes."
        )
        self.target_game_hint_label.setObjectName("mapStudioExportTargetGameHintLabel")
        self.target_game_hint_label.setWordWrap(True)
        self.export_safety_label = QtWidgets.QLabel(
            "Safe install: stage first, then install to a chosen Modules folder with backup. A module is not game-ready until a live warp test is recorded."
        )
        self.export_safety_label.setObjectName("mapStudioExportSafetyLabel")
        self.export_safety_label.setWordWrap(True)
        root.addWidget(self.export_scope_label)
        root.addWidget(target_row)
        self.visible_only = QtWidgets.QCheckBox("Visible Only")
        self.visible_only.setChecked(True)
        self.include_textures = QtWidgets.QCheckBox("Include Textures")
        self.include_textures.setChecked(True)
        self.include_lightmaps = QtWidgets.QCheckBox("Include Lightmaps")
        self.include_lightmaps.setChecked(True)
        self.include_walkmesh = QtWidgets.QCheckBox("Include Walkmesh")
        self.include_walkmesh.setChecked(True)
        self.copy_textures = QtWidgets.QCheckBox("Copy Textures")
        self.dry_run = QtWidgets.QCheckBox("Dry Run")
        self.dry_run.setObjectName("mapStudioExportDryRunCheckBox")
        self.dry_run.setChecked(False)
        self.dry_run.setToolTip("Preview the export/install action without writing final files or copying to a game folder.")
        for widget in (self.visible_only, self.include_textures, self.include_lightmaps, self.include_walkmesh, self.copy_textures, self.dry_run):
            widget.setParent(self)
            widget.hide()
        self.dry_run_hint_label = QtWidgets.QLabel(
            "Dry Run checked: validate and preview the operation. Clear it only when you are ready to write staged files or install for testing."
        )
        self.dry_run_hint_label.setObjectName("mapStudioExportDryRunHintLabel")
        self.dry_run_hint_label.setWordWrap(True)
        self.dry_run_hint_label.hide()
        self.export_gate_label = QtWidgets.QLabel(
            "Status: Not checked. Validate the map before exporting a KOTOR .mod."
        )
        self.export_gate_label.setObjectName("mapStudioExportReadinessGateLabel")
        self.export_gate_label.setWordWrap(True)
        root.addWidget(self.export_gate_label)
        self.export_blocker_table = QtWidgets.QTableWidget(0, 3)
        self.export_blocker_table.setObjectName("mapStudioExportBlockerTable")
        self.export_blocker_table.setHorizontalHeaderLabels(("Blocker", "KOTOR export impact", "Next fix"))
        self.export_blocker_table.verticalHeader().setVisible(False)
        self.export_blocker_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.export_blocker_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._make_table_fit_panel(self.export_blocker_table)
        self.export_blocker_table.setMinimumHeight(72)
        self.export_blocker_table.setMaximumHeight(150)
        self.export_blocker_table.itemDoubleClicked.connect(self._emit_blocker_target)
        self.export_blocker_table.setParent(self)
        self.export_blocker_table.hide()
        self.blocker_summary_label = QtWidgets.QLabel("Export checks: Not checked")
        self.blocker_summary_label.setObjectName("mapStudioExportBlockerSummaryLabel")
        self.blocker_summary_label.setWordWrap(True)
        self.fix_action_label = QtWidgets.QLabel(
            "Fix action: Resolve blockers in Builder, Walkmesh, Placement, then Validate before staging."
        )
        self.fix_action_label.setObjectName("mapStudioExportFixActionLabel")
        self.fix_action_label.setWordWrap(True)
        self.fix_actions_widget = QtWidgets.QWidget(self)
        fix_actions = QtWidgets.QGridLayout(self.fix_actions_widget)
        fix_actions.setContentsMargins(0, 0, 0, 0)
        fix_actions.setSpacing(4)
        self.fix_builder_button = QtWidgets.QPushButton("Open Builder")
        self.fix_builder_button.setObjectName("mapStudioExportFixBuilderButton")
        self.fix_walkmesh_button = QtWidgets.QPushButton("Open Walkmesh Tools")
        self.fix_walkmesh_button.setObjectName("mapStudioExportFixWalkmeshButton")
        self.fix_placement_button = QtWidgets.QPushButton("Open Placement Tools")
        self.fix_placement_button.setObjectName("mapStudioExportFixPlacementButton")
        self.fix_select_target_button = QtWidgets.QPushButton("Select Blocking Anchor")
        self.fix_select_target_button.setObjectName("mapStudioExportFixSelectTargetButton")
        self.fix_validate_button = QtWidgets.QPushButton("Validate Map")
        self.fix_validate_button.setObjectName("mapStudioExportFixValidateButton")
        self.fix_builder_button.clicked.connect(self.builderFixRequested.emit)
        self.fix_walkmesh_button.clicked.connect(self.walkmeshFixRequested.emit)
        self.fix_placement_button.clicked.connect(self.placementFixRequested.emit)
        self.fix_select_target_button.clicked.connect(self._emit_fix_target)
        self.fix_validate_button.clicked.connect(self.validateRequested.emit)
        for index, button in enumerate((
            self.fix_builder_button,
            self.fix_walkmesh_button,
            self.fix_placement_button,
            self.fix_select_target_button,
        )):
            fix_actions.addWidget(button, index // 2, index % 2)
        self.action_guide_toggle = QtWidgets.QToolButton(self)
        self.action_guide_toggle.setObjectName("mapStudioExportActionGuideButton")
        self.action_guide_toggle.setText("Explain package choices")
        self.action_guide_toggle.setCheckable(True)
        self.action_guide_toggle.setChecked(False)
        self.action_guide_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.action_guide_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.action_guide_label = QtWidgets.QLabel(
            "Export writes the .mod to a location you choose. Install also copies it to a KOTOR Modules folder with backup."
        )
        self.action_guide_label.setObjectName("mapStudioExportActionGuideLabel")
        self.action_guide_label.setWordWrap(True)
        self.action_guide_table = QtWidgets.QTableWidget(0, 4, self)
        self.action_guide_table.setObjectName("mapStudioExportActionGuideTable")
        self.action_guide_table.setHorizontalHeaderLabels(("Action", "Writes", "Use when", "Game proof"))
        self.action_guide_table.verticalHeader().setVisible(False)
        self.action_guide_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.action_guide_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._make_table_fit_panel(self.action_guide_table)
        self.action_guide_table.setMinimumHeight(132)
        self._populate_action_guide()
        self.action_guide_toggle.toggled.connect(self._set_action_guide_visible)
        self._set_action_guide_visible(False)
        self.export_button = QtWidgets.QPushButton("Export FBX")
        self.export_button.setToolTip(
            "External FBX scene handoff only; it is not a KOTOR-playable module package."
        )
        self.export_button.clicked.connect(lambda: self.exportRequested.emit(self.dry_run.isChecked()))
        self.export_button.setParent(self)
        self.export_button.hide()
        self.dev_test_button = QtWidgets.QPushButton("Stage grdev01 Dev Test Module")
        self.dev_test_button.setObjectName("mapStudioStageDevTestModuleButton")
        self.dev_test_button.setToolTip("Build and stage the first from-scratch GhostRigger dev-test .mod package.")
        self.dev_test_button.clicked.connect(lambda: self.devTestModuleRequested.emit(self.dry_run.isChecked()))
        self.dev_test_button.setParent(self)
        self.dev_test_button.hide()
        self.authored_module_button = QtWidgets.QPushButton("Export .mod Package...")
        self.authored_module_button.setObjectName("mapStudioExportAuthoredModuleButton")
        self.authored_module_button.setToolTip("Compile this KMAP into a complete, install-safe KOTOR .mod package.")
        self.authored_module_button.clicked.connect(lambda: self.authoredModuleRequested.emit(self.dry_run.isChecked()))
        self.authored_stage_button = QtWidgets.QPushButton("Stage Authored Module for Game Test")
        self.authored_stage_button.setObjectName("mapStudioStageAuthoredModuleButton")
        self.authored_stage_button.setToolTip("Package the authored module and write a checklist/proof manifest for an in-game warp test.")
        self.authored_stage_button.clicked.connect(lambda: self.authoredModuleStageRequested.emit(self.dry_run.isChecked()))
        self.authored_stage_button.setParent(self)
        self.authored_stage_button.hide()
        self.authored_install_button = QtWidgets.QPushButton("Install .mod for Game Test...")
        self.authored_install_button.setObjectName("mapStudioInstallAuthoredModuleButton")
        self.authored_install_button.setToolTip("Package the authored module, copy it to a chosen KOTOR Modules folder, and write a checklist/proof manifest.")
        self.authored_install_button.clicked.connect(lambda: self.authoredModuleInstallRequested.emit(self.dry_run.isChecked()))

        root.addWidget(self.fix_validate_button)
        root.addWidget(self.authored_module_button)
        root.addWidget(self.authored_install_button)

        self.details_toggle = QtWidgets.QToolButton(self)
        self.details_toggle.setObjectName("mapStudioExportAdvancedDetailsButton")
        self.details_toggle.setText("Advanced export details")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setChecked(False)
        self.details_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        root.addWidget(self.details_toggle)
        for widget in (
            self.target_game_hint_label,
            self.export_safety_label,
            self.blocker_summary_label,
            self.fix_action_label,
            self.fix_actions_widget,
            self.action_guide_toggle,
            self.action_guide_label,
        ):
            root.addWidget(widget)
        self._export_detail_widgets = (
            self.target_game_hint_label,
            self.export_safety_label,
            self.blocker_summary_label,
            self.fix_action_label,
            self.fix_actions_widget,
            self.action_guide_toggle,
        )
        self.details_toggle.toggled.connect(self._set_export_details_visible)
        self._set_export_details_visible(False)
        self.target_game_combo.setMinimumWidth(0)
        self.target_game_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumWidth(0)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Ignored,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        self.set_readiness(None)
        root.addStretch(1)

    def _set_export_details_visible(self, visible: bool) -> None:
        if not visible:
            self.action_guide_toggle.setChecked(False)
        for widget in self._export_detail_widgets:
            widget.setVisible(bool(visible))
        self.details_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        )

    @staticmethod
    def _make_table_fit_panel(table: QtWidgets.QTableWidget) -> None:
        """Wrap narrow-panel tables instead of growing a horizontal scrollbar."""

        table.setWordWrap(True)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    def _set_action_guide_visible(self, visible: bool) -> None:
        self.action_guide_label.setVisible(bool(visible))
        self.action_guide_table.setVisible(False)
        self.action_guide_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        )

    def set_target_game(self, game: str, *, source_game: str = "") -> None:
        """Reflect the KMAP export target without recursively requesting a port."""

        target = str(game or "K1").strip().upper()
        index = self.target_game_combo.findData(target)
        blocked = self.target_game_combo.blockSignals(True)
        try:
            self.target_game_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.target_game_combo.blockSignals(blocked)
        source = str(source_game or target).strip().upper()
        if source and source != target:
            self.target_game_hint_label.setText(
                f"Source {source} -> target {target}: validate every preserved texture/template resref, then rebuild and re-prove in game."
            )
        else:
            self.target_game_hint_label.setText(
                f"Target {target}: changing this runs the K1/K2 port transaction and invalidates prior package/game proof."
            )

    def _emit_target_game(self, _index: int) -> None:
        self.targetGameRequested.emit(str(self.target_game_combo.currentData() or "K1"))

    def _populate_action_guide(self) -> None:
        rows = (
            (
                "Export FBX",
                "External FBX scene handoff",
                "Use for DCC review; it is not a KOTOR-playable module package.",
                "Not a game proof path.",
            ),
            (
                "Export Authored KMAP Module",
                "Staged KOTOR .mod package",
                "Use after validation when you want a package candidate without installing it.",
                "Still needs staged install and live warp proof.",
            ),
            (
                "Stage Authored Module for Game Test",
                ".mod, checklist, proof manifest",
                "Use before copying into a KOTOR Modules folder.",
                "Creates the proof handoff; does not prove game-ready.",
            ),
            (
                "Install Authored Module for Game Test",
                ".mod copied to selected Modules folder with backup",
                "Use when you are ready to launch KOTOR and run the warp test.",
                "Requires live warp test and recorded evidence.",
            ),
        )
        self.action_guide_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.action_guide_table.setItem(row, column, item)

    def set_readiness(self, readiness: object | None) -> None:
        """Reflect authored-module export readiness without owning validation policy."""

        if readiness is None:
            self.export_gate_label.setText(
                "Status: Not ready. Add a room, then Validate before exporting."
            )
            self._set_authored_module_buttons_enabled(False)
            self._set_fix_action_state(builder=True, walkmesh=False, placement=False, validate=True)
            self._set_export_blocker_rows(
                (
                    (
                        "No readiness result",
                        "Current authored KMAP package actions stay locked.",
                        "Create or open a KMAP, then use Builder and Validate before staging/installing.",
                    ),
                )
            )
            return

        can_export = bool(getattr(readiness, "can_export_candidate", False))
        export_status = str(getattr(readiness, "export_status", "Not ready") or "Not ready")
        next_action = str(getattr(readiness, "next_action", "") or "")
        metadata = dict(getattr(readiness, "metadata", {}) or {})
        pathing = dict(metadata.get("pathing") or {})
        pathing_blockers = tuple(str(item) for item in tuple(pathing.get("blocking_messages", ()) or ()) if str(item).strip())
        pathing_targets = tuple(item for item in tuple(pathing.get("blocking_targets", ()) or ()) if isinstance(item, dict))
        blocking_messages = tuple(
            str(item) for item in tuple(getattr(readiness, "blocking_messages", ()) or ()) if str(item).strip()
        )
        fix_hint = str(pathing.get("fix_hint") or "Use Builder/Walkmesh tools to put the module entry point and gameplay anchors on generated walkable WOK.")

        missing_runtime_resources = tuple(
            getattr(readiness, "missing_runtime_resources", ()) or ()
        )
        can_build_initial_package = (
            bool(getattr(readiness, "can_preview", False))
            and bool(missing_runtime_resources)
            and export_status.strip().lower() == "missing runtime resources"
            and not pathing_blockers
            and not blocking_messages
        )
        self._set_authored_module_buttons_enabled(can_export or can_build_initial_package)
        if can_export:
            self.export_gate_label.setText(
                "Status: Ready to export a .mod. Test it in KOTOR before release."
            )
            self._set_fix_action_state(builder=False, walkmesh=False, placement=False, validate=False)
            self._set_export_blocker_rows(
                (
                    (
                        "No current export blockers",
                        "Authored .mod package actions are unlocked.",
                        "Stage or install, warp in-game, and record proof before game-ready status.",
                    ),
                )
            )
            return

        if can_build_initial_package:
            self.export_gate_label.setText(
                "Status: Ready to build a .mod. Required KOTOR files will be generated during export."
            )
            self._set_fix_action_state(builder=False, walkmesh=False, placement=False, validate=False)
            self._set_export_blocker_rows(
                (
                    (
                        "No current build blockers",
                        "The first export will generate the missing room and module resources.",
                        "Choose Export .mod Package, then test the result in KOTOR before release.",
                    ),
                )
            )
            return

        if pathing_blockers:
            self.export_gate_label.setText(
                "Status: Blocked - walkmesh/pathing needs attention before export."
            )
            self._set_fix_action_state(
                builder=True,
                walkmesh=True,
                placement=True,
                validate=True,
                target_id=self._first_fix_target_id(pathing_targets),
            )
            self._set_export_blocker_rows(
                tuple(
                    (
                        blocker,
                        "Blocks authored .mod package, stage, and install actions.",
                        self._fix_hint_for_target(pathing_targets, fallback=fix_hint),
                        self._target_id_for_blocker(pathing_targets, blocker),
                    )
                    for blocker in pathing_blockers
                )
            )
            return

        if blocking_messages:
            self.export_gate_label.setText(
                "Status: Blocked - fix the validation issues before export."
            )
            self._set_fix_action_state(
                builder=True,
                walkmesh=any("wok" in message.lower() or "walkmesh" in message.lower() for message in blocking_messages),
                placement=any(
                    key in message.lower()
                    for message in blocking_messages
                    for key in ("entry_point", "creature", "placeable", "door", "trigger", "waypoint", "encounter")
                ),
                validate=True,
            )
            self._set_export_blocker_rows(
                tuple(
                    (
                        message,
                        "Blocks authored .mod package, stage, and install actions.",
                        next_action or "Resolve the blocking readiness issue, then run Validate again.",
                    )
                    for message in blocking_messages[:8]
                )
            )
            return

        self.export_gate_label.setText(f"Status: Not ready - {export_status}")
        self._set_fix_action_state(builder=True, walkmesh=True, placement=False, validate=True)
        self._set_export_blocker_rows(
            (
                (
                    export_status,
                    "Authored .mod package actions stay locked.",
                    next_action or "Generate missing KOTOR runtime resources before staging/installing.",
                ),
            )
        )

    def _set_authored_module_buttons_enabled(self, enabled: bool) -> None:
        for button in (
            self.authored_module_button,
            self.authored_stage_button,
            self.authored_install_button,
        ):
            button.setEnabled(enabled)

    def _set_fix_action_state(
        self,
        *,
        builder: bool,
        walkmesh: bool,
        placement: bool,
        validate: bool,
        target_id: str = "",
    ) -> None:
        self._fix_target_id = str(target_id or "")
        self.fix_builder_button.setEnabled(builder)
        self.fix_walkmesh_button.setEnabled(walkmesh)
        self.fix_placement_button.setEnabled(placement)
        self.fix_select_target_button.setEnabled(bool(self._fix_target_id))
        self.fix_validate_button.setEnabled(validate)
        enabled = []
        if self._fix_target_id:
            enabled.append("Select anchor")
        if builder:
            enabled.append("Builder")
        if walkmesh:
            enabled.append("Walkmesh")
        if placement:
            enabled.append("Placement")
        if validate:
            enabled.append("Validate")
        if enabled:
            self.fix_action_label.setText("Fix action: " + " / ".join(enabled) + " tools are relevant for the current blocker.")
        else:
            self.fix_action_label.setText("Fix action: No blocker action needed; stage/install, then record live game proof.")

    def _emit_fix_target(self) -> None:
        if self._fix_target_id:
            self.selectFixTargetRequested.emit(self._fix_target_id)

    def _emit_blocker_target(self, item: QtWidgets.QTableWidgetItem) -> None:
        target_id = str(item.data(QtCore.Qt.UserRole) or "").strip()
        if target_id:
            self.selectFixTargetRequested.emit(target_id)

    @staticmethod
    def _first_fix_target_id(targets: tuple[dict[str, object], ...]) -> str:
        for target in targets:
            value = str(target.get("target_id") or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _fix_hint_for_target(targets: tuple[dict[str, object], ...], *, fallback: str) -> str:
        for target in targets:
            action = str(target.get("fix_action") or "").strip()
            target_id = str(target.get("target_id") or "").strip()
            if action and target_id:
                return f"{action} Target: {target_id}."
            if action:
                return action
        return fallback

    @staticmethod
    def _target_id_for_blocker(targets: tuple[dict[str, object], ...], blocker: str) -> str:
        blocker_text = str(blocker or "")
        for target in targets:
            label = str(target.get("anchor_label") or "").strip()
            target_id = str(target.get("target_id") or "").strip()
            if label and target_id and label in blocker_text:
                return target_id
        return ""

    def _set_export_blocker_rows(self, rows: tuple[tuple[str, ...], ...]) -> None:
        self.export_blocker_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            target_id = str(values[3] if len(values) > 3 else "")
            for column, text in enumerate(values[:3]):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                item.setData(QtCore.Qt.UserRole, target_id)
                self.export_blocker_table.setItem(row, column, item)
        if not rows:
            self.blocker_summary_label.setText("Export checks: No blockers reported.")
            return
        summaries = []
        for values in rows[:8]:
            blocker = str(values[0] if values else "Export blocker")
            fix = str(values[2] if len(values) > 2 else "Run Validate for the next step.")
            summaries.append(f"- {blocker}\n  Next: {fix}")
        self.blocker_summary_label.setText("Export checks:\n" + "\n".join(summaries))
