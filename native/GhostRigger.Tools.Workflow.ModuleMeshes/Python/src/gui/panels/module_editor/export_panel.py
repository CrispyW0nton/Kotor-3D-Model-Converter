"""Export options panel for KMAP scenes."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleExportPanel(QtWidgets.QWidget):
    exportRequested = QtCore.Signal(bool)
    devTestModuleRequested = QtCore.Signal(bool)
    authoredModuleRequested = QtCore.Signal(bool)
    authoredModuleStageRequested = QtCore.Signal(bool)
    authoredModuleInstallRequested = QtCore.Signal(bool)
    builderFixRequested = QtCore.Signal()
    walkmeshFixRequested = QtCore.Signal()
    placementFixRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        self.export_scope_label = QtWidgets.QLabel(
            "Export paths: use FBX for external scene handoff, or export/stage an authored KMAP module as a KOTOR .mod package."
        )
        self.export_scope_label.setObjectName("mapStudioExportScopeLabel")
        self.export_scope_label.setWordWrap(True)
        self.export_safety_label = QtWidgets.QLabel(
            "Safe install: stage first, then install to a chosen Modules folder with backup. A module is not game-ready until a live warp test is recorded."
        )
        self.export_safety_label.setObjectName("mapStudioExportSafetyLabel")
        self.export_safety_label.setWordWrap(True)
        root.addWidget(self.export_scope_label)
        root.addWidget(self.export_safety_label)
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
        self.dry_run.setChecked(True)
        self.dry_run.setToolTip("Preview the export/install action without writing final files or copying to a game folder.")
        for widget in (self.visible_only, self.include_textures, self.include_lightmaps, self.include_walkmesh, self.copy_textures, self.dry_run):
            root.addWidget(widget)
        self.dry_run_hint_label = QtWidgets.QLabel(
            "Dry Run checked: validate and preview the operation. Clear it only when you are ready to write staged files or install for testing."
        )
        self.dry_run_hint_label.setObjectName("mapStudioExportDryRunHintLabel")
        self.dry_run_hint_label.setWordWrap(True)
        root.addWidget(self.dry_run_hint_label)
        self.export_gate_label = QtWidgets.QLabel(
            "Current authored-module export gate: Not checked. Readiness must pass before KOTOR .mod packaging."
        )
        self.export_gate_label.setObjectName("mapStudioExportReadinessGateLabel")
        self.export_gate_label.setWordWrap(True)
        root.addWidget(self.export_gate_label)
        self.export_blocker_table = QtWidgets.QTableWidget(0, 3)
        self.export_blocker_table.setObjectName("mapStudioExportBlockerTable")
        self.export_blocker_table.setHorizontalHeaderLabels(("Blocker", "KOTOR export impact", "Next fix"))
        self.export_blocker_table.verticalHeader().setVisible(False)
        self.export_blocker_table.horizontalHeader().setStretchLastSection(True)
        self.export_blocker_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.export_blocker_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.export_blocker_table.setMinimumHeight(72)
        self.export_blocker_table.setMaximumHeight(150)
        root.addWidget(self.export_blocker_table)
        self.fix_action_label = QtWidgets.QLabel(
            "Fix action: Resolve blockers in Builder, Walkmesh, Placement, then Validate before staging."
        )
        self.fix_action_label.setObjectName("mapStudioExportFixActionLabel")
        self.fix_action_label.setWordWrap(True)
        root.addWidget(self.fix_action_label)
        fix_actions = QtWidgets.QHBoxLayout()
        fix_actions.setContentsMargins(0, 0, 0, 0)
        fix_actions.setSpacing(4)
        self.fix_builder_button = QtWidgets.QPushButton("Open Builder")
        self.fix_builder_button.setObjectName("mapStudioExportFixBuilderButton")
        self.fix_walkmesh_button = QtWidgets.QPushButton("Open Walkmesh Tools")
        self.fix_walkmesh_button.setObjectName("mapStudioExportFixWalkmeshButton")
        self.fix_placement_button = QtWidgets.QPushButton("Open Placement Tools")
        self.fix_placement_button.setObjectName("mapStudioExportFixPlacementButton")
        self.fix_validate_button = QtWidgets.QPushButton("Validate Again")
        self.fix_validate_button.setObjectName("mapStudioExportFixValidateButton")
        self.fix_builder_button.clicked.connect(self.builderFixRequested.emit)
        self.fix_walkmesh_button.clicked.connect(self.walkmeshFixRequested.emit)
        self.fix_placement_button.clicked.connect(self.placementFixRequested.emit)
        self.fix_validate_button.clicked.connect(self.validateRequested.emit)
        for button in (
            self.fix_builder_button,
            self.fix_walkmesh_button,
            self.fix_placement_button,
            self.fix_validate_button,
        ):
            fix_actions.addWidget(button)
        root.addLayout(fix_actions)
        self.action_guide_label = QtWidgets.QLabel(
            "Export action guide: choose FBX only for external DCC handoff; choose authored-module actions when testing a KOTOR .mod."
        )
        self.action_guide_label.setObjectName("mapStudioExportActionGuideLabel")
        self.action_guide_label.setWordWrap(True)
        root.addWidget(self.action_guide_label)
        self.action_guide_table = QtWidgets.QTableWidget(0, 4)
        self.action_guide_table.setObjectName("mapStudioExportActionGuideTable")
        self.action_guide_table.setHorizontalHeaderLabels(("Action", "Writes", "Use when", "Game proof"))
        self.action_guide_table.verticalHeader().setVisible(False)
        self.action_guide_table.horizontalHeader().setStretchLastSection(True)
        self.action_guide_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.action_guide_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.action_guide_table.setMinimumHeight(132)
        self._populate_action_guide()
        root.addWidget(self.action_guide_table)
        self.export_button = QtWidgets.QPushButton("Export FBX")
        self.export_button.clicked.connect(lambda: self.exportRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.export_button)
        self.dev_test_button = QtWidgets.QPushButton("Stage grdev01 Dev Test Module")
        self.dev_test_button.setObjectName("mapStudioStageDevTestModuleButton")
        self.dev_test_button.setToolTip("Build and stage the first from-scratch GhostRigger dev-test .mod package.")
        self.dev_test_button.clicked.connect(lambda: self.devTestModuleRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.dev_test_button)
        self.authored_module_button = QtWidgets.QPushButton("Export Authored KMAP Module")
        self.authored_module_button.setObjectName("mapStudioExportAuthoredModuleButton")
        self.authored_module_button.setToolTip("Compile the authored module stored in this KMAP and package it as an install-safe .mod.")
        self.authored_module_button.clicked.connect(lambda: self.authoredModuleRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.authored_module_button)
        self.authored_stage_button = QtWidgets.QPushButton("Stage Authored Module for Game Test")
        self.authored_stage_button.setObjectName("mapStudioStageAuthoredModuleButton")
        self.authored_stage_button.setToolTip("Package the authored module and write a checklist/proof manifest for an in-game warp test.")
        self.authored_stage_button.clicked.connect(lambda: self.authoredModuleStageRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.authored_stage_button)
        self.authored_install_button = QtWidgets.QPushButton("Install Authored Module for Game Test...")
        self.authored_install_button.setObjectName("mapStudioInstallAuthoredModuleButton")
        self.authored_install_button.setToolTip("Package the authored module, copy it to a chosen KOTOR Modules folder, and write a checklist/proof manifest.")
        self.authored_install_button.clicked.connect(lambda: self.authoredModuleInstallRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.authored_install_button)
        self.set_readiness(None)
        root.addStretch(1)

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
                "Current authored-module export gate: Not checked. Create/open a KMAP and run readiness before packaging a KOTOR .mod."
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
        blocking_messages = tuple(
            str(item) for item in tuple(getattr(readiness, "blocking_messages", ()) or ()) if str(item).strip()
        )
        fix_hint = str(pathing.get("fix_hint") or "Use Builder/Walkmesh tools to put the module entry point and gameplay anchors on generated walkable WOK.")

        self._set_authored_module_buttons_enabled(can_export)
        if can_export:
            self.export_gate_label.setText(
                "Current authored-module export gate: Ready to stage as a KOTOR .mod candidate. Still record a live warp test before calling it game-ready."
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

        if pathing_blockers:
            self.export_gate_label.setText(
                f"Current authored-module export gate: Blocked by PTH/WOK pathing. {export_status}"
            )
            self._set_fix_action_state(builder=True, walkmesh=True, placement=True, validate=True)
            self._set_export_blocker_rows(
                tuple(
                    (
                        blocker,
                        "Blocks authored .mod package, stage, and install actions.",
                        fix_hint,
                    )
                    for blocker in pathing_blockers
                )
            )
            return

        if blocking_messages:
            self.export_gate_label.setText(
                f"Current authored-module export gate: Blocked by readiness validation. {export_status}"
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

        self.export_gate_label.setText(f"Current authored-module export gate: Not ready. {export_status}")
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

    def _set_fix_action_state(self, *, builder: bool, walkmesh: bool, placement: bool, validate: bool) -> None:
        self.fix_builder_button.setEnabled(builder)
        self.fix_walkmesh_button.setEnabled(walkmesh)
        self.fix_placement_button.setEnabled(placement)
        self.fix_validate_button.setEnabled(validate)
        enabled = []
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

    def _set_export_blocker_rows(self, rows: tuple[tuple[str, str, str], ...]) -> None:
        self.export_blocker_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.export_blocker_table.setItem(row, column, item)
