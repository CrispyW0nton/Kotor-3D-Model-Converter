"""Map Studio readiness/status panel.

The panel is deliberately presentation-only: it displays the headless
``AuthoredModuleReadiness`` contract produced by ``src.core.modules`` and keeps
packaging policy out of Qt widgets.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets


class ModuleReadinessPanel(QtWidgets.QWidget):
    """Small modder-facing status card for scratch-built Map Studio modules."""

    gameTestRequested = QtCore.Signal()
    launchHandoffRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleReadinessPanel")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self.header_label = QtWidgets.QLabel("Map Studio readiness")
        self.header_label.setObjectName("mapStudioReadinessHeaderLabel")
        self.header_label.setWordWrap(True)
        root.addWidget(self.header_label)

        self.stage_label = QtWidgets.QLabel("Stage: Not ready")
        self.stage_label.setObjectName("mapStudioReadinessStageLabel")
        self.stage_label.setWordWrap(True)
        root.addWidget(self.stage_label)

        self.toolchain_label = QtWidgets.QLabel("Pipeline: Not checked")
        self.toolchain_label.setObjectName("mapStudioReadinessToolchainLabel")
        self.toolchain_label.setWordWrap(True)
        root.addWidget(self.toolchain_label)

        self.preview_label = QtWidgets.QLabel("Preview: Not ready")
        self.preview_label.setObjectName("mapStudioReadinessPreviewLabel")
        self.preview_label.setWordWrap(True)
        root.addWidget(self.preview_label)

        self.export_label = QtWidgets.QLabel("Export: Not ready")
        self.export_label.setObjectName("mapStudioReadinessExportLabel")
        self.export_label.setWordWrap(True)
        root.addWidget(self.export_label)

        self.runtime_label = QtWidgets.QLabel("Runtime resources: Not checked")
        self.runtime_label.setObjectName("mapStudioReadinessRuntimeLabel")
        self.runtime_label.setWordWrap(True)
        root.addWidget(self.runtime_label)
        self.runtime_resource_table = QtWidgets.QTableWidget(0, 3)
        self.runtime_resource_table.setObjectName("mapStudioReadinessRuntimeResourceTable")
        self.runtime_resource_table.setHorizontalHeaderLabels(("Resource", "Status", "Fix / meaning"))
        self.runtime_resource_table.verticalHeader().setVisible(False)
        self.runtime_resource_table.horizontalHeader().setStretchLastSection(True)
        self.runtime_resource_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.runtime_resource_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.runtime_resource_table.setMinimumHeight(96)
        self.runtime_resource_table.setMaximumHeight(180)
        root.addWidget(self.runtime_resource_table)

        self.proof_label = QtWidgets.QLabel("Game proof: Not staged")
        self.proof_label.setObjectName("mapStudioReadinessGameProofLabel")
        self.proof_label.setWordWrap(True)
        root.addWidget(self.proof_label)

        self.proof_recorder_label = QtWidgets.QLabel("Proof recorder: Not ready")
        self.proof_recorder_label.setObjectName("mapStudioReadinessProofRecorderLabel")
        self.proof_recorder_label.setWordWrap(True)
        root.addWidget(self.proof_recorder_label)

        self.launch_label = QtWidgets.QLabel("Launch handoff: Not ready")
        self.launch_label.setObjectName("mapStudioReadinessLaunchHandoffLabel")
        self.launch_label.setWordWrap(True)
        root.addWidget(self.launch_label)

        self.warp_command_label = QtWidgets.QLabel("Warp test command")
        self.warp_command_label.setObjectName("mapStudioReadinessWarpCommandLabel")
        root.addWidget(self.warp_command_label)

        warp_row = QtWidgets.QHBoxLayout()
        warp_row.setContentsMargins(0, 0, 0, 0)
        warp_row.setSpacing(4)
        self.warp_command_edit = QtWidgets.QLineEdit()
        self.warp_command_edit.setObjectName("mapStudioReadinessWarpCommandLineEdit")
        self.warp_command_edit.setReadOnly(True)
        self.warp_command_edit.setPlaceholderText("Stage or install a module to get the warp command")
        self.copy_warp_command_button = QtWidgets.QPushButton("Copy Warp")
        self.copy_warp_command_button.setObjectName("mapStudioReadinessCopyWarpCommandButton")
        self.copy_warp_command_button.clicked.connect(lambda: self._copy_text(self.warp_command_edit.text()))
        warp_row.addWidget(self.warp_command_edit, 1)
        warp_row.addWidget(self.copy_warp_command_button)
        root.addLayout(warp_row)

        self.launch_helper_label = QtWidgets.QLabel("Launch helper")
        self.launch_helper_label.setObjectName("mapStudioReadinessLaunchHelperPathLabel")
        root.addWidget(self.launch_helper_label)

        launch_helper_row = QtWidgets.QHBoxLayout()
        launch_helper_row.setContentsMargins(0, 0, 0, 0)
        launch_helper_row.setSpacing(4)
        self.launch_helper_edit = QtWidgets.QLineEdit()
        self.launch_helper_edit.setObjectName("mapStudioReadinessLaunchHelperLineEdit")
        self.launch_helper_edit.setReadOnly(True)
        self.launch_helper_edit.setPlaceholderText("Install for game test to create a launch helper")
        self.copy_launch_helper_button = QtWidgets.QPushButton("Copy Helper")
        self.copy_launch_helper_button.setObjectName("mapStudioReadinessCopyLaunchHelperButton")
        self.copy_launch_helper_button.clicked.connect(lambda: self._copy_text(self.launch_helper_edit.text()))
        launch_helper_row.addWidget(self.launch_helper_edit, 1)
        launch_helper_row.addWidget(self.copy_launch_helper_button)
        root.addLayout(launch_helper_row)

        self.proof_manifest_label = QtWidgets.QLabel("Proof manifest")
        self.proof_manifest_label.setObjectName("mapStudioReadinessProofManifestPathLabel")
        root.addWidget(self.proof_manifest_label)

        proof_manifest_row = QtWidgets.QHBoxLayout()
        proof_manifest_row.setContentsMargins(0, 0, 0, 0)
        proof_manifest_row.setSpacing(4)
        self.proof_manifest_edit = QtWidgets.QLineEdit()
        self.proof_manifest_edit.setObjectName("mapStudioReadinessProofManifestLineEdit")
        self.proof_manifest_edit.setReadOnly(True)
        self.proof_manifest_edit.setPlaceholderText("Stage for game test to create a proof manifest")
        self.copy_proof_manifest_button = QtWidgets.QPushButton("Copy Manifest")
        self.copy_proof_manifest_button.setObjectName("mapStudioReadinessCopyProofManifestButton")
        self.copy_proof_manifest_button.clicked.connect(lambda: self._copy_text(self.proof_manifest_edit.text()))
        proof_manifest_row.addWidget(self.proof_manifest_edit, 1)
        proof_manifest_row.addWidget(self.copy_proof_manifest_button)
        root.addLayout(proof_manifest_row)

        self.authored_summary_label = QtWidgets.QLabel("Authored content: Not checked")
        self.authored_summary_label.setObjectName("mapStudioReadinessAuthoredSummaryLabel")
        self.authored_summary_label.setWordWrap(True)
        root.addWidget(self.authored_summary_label)

        self.template_references_label = QtWidgets.QLabel("Template references: Not checked")
        self.template_references_label.setObjectName("mapStudioReadinessTemplateReferencesLabel")
        self.template_references_label.setWordWrap(True)
        root.addWidget(self.template_references_label)

        self.transition_references_label = QtWidgets.QLabel("Transitions: Not checked")
        self.transition_references_label.setObjectName("mapStudioReadinessTransitionReferencesLabel")
        self.transition_references_label.setWordWrap(True)
        root.addWidget(self.transition_references_label)
        self.transition_reference_table = QtWidgets.QTableWidget(0, 4)
        self.transition_reference_table.setObjectName("mapStudioReadinessTransitionReferenceTable")
        self.transition_reference_table.setHorizontalHeaderLabels(("Kind", "Tag", "Destination", "Status / fix"))
        self.transition_reference_table.verticalHeader().setVisible(False)
        self.transition_reference_table.horizontalHeader().setStretchLastSection(True)
        self.transition_reference_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.transition_reference_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.transition_reference_table.setMinimumHeight(76)
        self.transition_reference_table.setMaximumHeight(150)
        root.addWidget(self.transition_reference_table)

        self.script_references_label = QtWidgets.QLabel("ARE/IFO script hooks: Not checked")
        self.script_references_label.setObjectName("mapStudioReadinessScriptReferencesLabel")
        self.script_references_label.setWordWrap(True)
        root.addWidget(self.script_references_label)
        self.script_reference_table = QtWidgets.QTableWidget(0, 4)
        self.script_reference_table.setObjectName("mapStudioReadinessScriptReferenceTable")
        self.script_reference_table.setHorizontalHeaderLabels(("Scope", "Field", "Script", "Status / fix"))
        self.script_reference_table.verticalHeader().setVisible(False)
        self.script_reference_table.horizontalHeader().setStretchLastSection(True)
        self.script_reference_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.script_reference_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.script_reference_table.setMinimumHeight(76)
        self.script_reference_table.setMaximumHeight(150)
        root.addWidget(self.script_reference_table)

        self.blocking_label = QtWidgets.QLabel("")
        self.blocking_label.setObjectName("mapStudioReadinessBlockingLabel")
        self.blocking_label.setWordWrap(True)
        root.addWidget(self.blocking_label)

        self.next_action_label = QtWidgets.QLabel("")
        self.next_action_label.setObjectName("mapStudioReadinessNextActionLabel")
        self.next_action_label.setWordWrap(True)
        root.addWidget(self.next_action_label)

        self.game_test_button = QtWidgets.QPushButton("Record Game Smoke Proof")
        self.game_test_button.setObjectName("mapStudioRecordGameProofButton")
        self.game_test_button.clicked.connect(self.gameTestRequested.emit)
        root.addWidget(self.game_test_button)

        self.launch_handoff_button = QtWidgets.QPushButton("Open Launch Handoff")
        self.launch_handoff_button.setObjectName("mapStudioOpenLaunchHandoffButton")
        self.launch_handoff_button.clicked.connect(self.launchHandoffRequested.emit)
        root.addWidget(self.launch_handoff_button)
        root.addStretch(1)
        self.set_readiness(None)

    def set_readiness(self, readiness: Any | None) -> None:
        """Display readiness from ``build_authored_module_readiness``."""

        if readiness is None:
            self.header_label.setText("Map Studio readiness")
            self.stage_label.setText("Stage: No authored module project selected")
            self.toolchain_label.setText("Pipeline: Not checked")
            self.preview_label.setText("Preview: Not ready")
            self.export_label.setText("Export: Not ready")
            self.runtime_label.setText("Runtime resources: Not checked")
            self._set_runtime_resource_rows((), (), ())
            self.proof_label.setText("Game proof: Not staged")
            self.proof_recorder_label.setText("Proof recorder: Not ready")
            self.launch_label.setText("Launch handoff: Not ready")
            self.warp_command_edit.clear()
            self.launch_helper_edit.clear()
            self.proof_manifest_edit.clear()
            self._update_copy_buttons()
            self.authored_summary_label.setText("Authored content: Not checked")
            self.template_references_label.setText("Template references: Not checked")
            self.transition_references_label.setText("Transitions: Not checked")
            self._set_transition_reference_rows(())
            self.script_references_label.setText("ARE/IFO script hooks: Not checked")
            self._set_script_reference_rows(())
            self.blocking_label.setText("Create or open a Map Studio module project first.")
            self.next_action_label.setText("")
            self.game_test_button.setEnabled(False)
            self.launch_handoff_button.setEnabled(False)
            return

        module_root = str(getattr(readiness, "module_root", "") or "(unnamed)")
        game = str(getattr(readiness, "game", "") or "(game not selected)")
        stage = str(getattr(readiness, "capability_stage", "blocked") or "blocked").replace("_", " ")
        expected = tuple(getattr(readiness, "expected_runtime_resources", ()) or ())
        present = tuple(getattr(readiness, "present_runtime_resources", ()) or ())
        missing = tuple(getattr(readiness, "missing_runtime_resources", ()) or ())
        blocking = tuple(getattr(readiness, "blocking_messages", ()) or ())
        warnings = tuple(getattr(readiness, "warnings", ()) or ())

        self.header_label.setText(f"Module: {module_root} ({game})")
        self.stage_label.setText(f"Stage: {stage}")
        toolchain = tuple(getattr(readiness, "toolchain", ()) or ())
        if toolchain:
            parts = []
            for item in toolchain:
                name = str(getattr(item, "name", "") or "Step")
                status = str(getattr(item, "status", "") or "Not checked")
                marker = "Ready" if bool(getattr(item, "ready", False)) else "Needs work"
                parts.append(f"{name}: {marker} ({status})")
            self.toolchain_label.setText("Pipeline: " + " | ".join(parts))
        else:
            self.toolchain_label.setText("Pipeline: Not checked")
        self.preview_label.setText(f"Preview: {getattr(readiness, 'preview_status', 'Not ready')}")
        self.export_label.setText(f"Export: {getattr(readiness, 'export_status', 'Not ready')}")
        if expected:
            self.runtime_label.setText(f"Runtime resources: {len(expected) - len(missing)}/{len(expected)} present")
        else:
            self.runtime_label.setText("Runtime resources: Not checked")
        self._set_runtime_resource_rows(expected, present, missing)
        metadata = dict(getattr(readiness, "metadata", {}) or {})
        proof_status = str(metadata.get("proof_status") or "not_ready")
        installed_path = str(metadata.get("installed_module_path") or "")
        proof_manifest = str(metadata.get("proof_manifest_path") or "")
        evidence_path = str(metadata.get("in_game_proof_evidence_path") or "")
        launch_status = str(metadata.get("launch_status") or "not_ready")
        launch_helper = str(metadata.get("launch_helper_command") or "")
        elevated_launch_script = str(metadata.get("elevated_launch_script_path") or "")
        proof_recorder_script = str(metadata.get("proof_recording_script_path") or "")
        expected_executable = str(metadata.get("expected_executable_path") or "")
        warp_command = str(metadata.get("warp_command") or f"warp {module_root}")
        self.warp_command_edit.setText(warp_command if module_root and module_root != "(unnamed)" else "")
        self.launch_helper_edit.setText(elevated_launch_script or launch_helper)
        self.proof_manifest_edit.setText(proof_manifest)
        self._update_copy_buttons()
        if bool(getattr(readiness, "game_tested", False)):
            suffix = f" Evidence: {evidence_path}" if evidence_path else ""
            self.proof_label.setText(f"Game proof: Recorded.{suffix}")
        elif installed_path:
            self.proof_label.setText(f"Game proof: Installed for warp test. {installed_path}")
        elif proof_manifest:
            self.proof_label.setText(f"Game proof: Staged; proof manifest ready. {proof_manifest}")
        elif proof_status == "not_staged":
            self.proof_label.setText("Game proof: Not staged yet; install the .mod and run the warp test.")
        else:
            self.proof_label.setText("Game proof: Not ready")
        if proof_recorder_script:
            self.proof_recorder_label.setText(f"Proof recorder: Ready after the KOTOR warp test. {proof_recorder_script}")
        elif proof_manifest:
            self.proof_recorder_label.setText("Proof recorder: Use Record Game Smoke Proof after capturing screenshot/video evidence.")
        else:
            self.proof_recorder_label.setText("Proof recorder: Not ready")
        if elevated_launch_script:
            self.launch_label.setText(f"Launch handoff: Elevated launcher ready. {elevated_launch_script}")
        elif launch_helper:
            self.launch_label.setText(f"Launch handoff: Dry-run helper ready. {launch_helper}")
        elif launch_status == "installed_missing_game_root":
            self.launch_label.setText(f"Launch handoff: Installed; choose the KOTOR game root, launch {expected_executable}, then run `{warp_command}`.")
        elif installed_path:
            self.launch_label.setText(f"Launch handoff: Launch {expected_executable}, then run `{warp_command}`.")
        elif proof_manifest:
            self.launch_label.setText("Launch handoff: Install the staged .mod into a KOTOR Modules folder first.")
        else:
            self.launch_label.setText("Launch handoff: Not ready")
        styles = list(metadata.get("room_styles", ()) or ())
        gameplay_counts = dict(metadata.get("gameplay_counts", {}) or {})
        placement_total = int(metadata.get("gameplay_placement_count", sum(int(value) for value in gameplay_counts.values()) if gameplay_counts else 0))
        lighting_count = int(metadata.get("lighting_count", 0) or 0)
        room_text = ""
        if styles:
            first = dict(styles[0])
            room_text = (
                f"{first.get('room_resref', 'room')} uses {first.get('texture', '(no texture)')} / "
                f"{first.get('floor_surface_name', 'surface')} {first.get('floor_surface_id', '')}"
            )
        self.authored_summary_label.setText(
            f"Authored content: {room_text or 'No room style summary'}; "
            f"{placement_total} gameplay placement(s); {lighting_count} room light(s)"
        )
        template_refs = list(metadata.get("gameplay_template_references", ()) or ())
        template_count = int(metadata.get("gameplay_template_reference_count", len(template_refs)) or 0)
        packaged_template_count = int(metadata.get("gameplay_packaged_template_count", 0) or 0)
        external_template_count = int(metadata.get("gameplay_external_template_count", 0) or 0)
        if template_refs:
            names = []
            for ref in template_refs[:4]:
                item = dict(ref)
                resref = str(item.get("template_resref") or "(missing)")
                restype = str(item.get("restype") or "")
                status = "packaged" if bool(item.get("packaged")) else "external"
                names.append(f"{resref}.{restype} ({status})")
            suffix = f"; {', '.join(names)}"
            if len(template_refs) > 4:
                suffix += f"; +{len(template_refs) - 4} more"
            self.template_references_label.setText(
                f"Template references: {template_count} total, {packaged_template_count} packaged, "
                f"{external_template_count} external/base-game{suffix}"
            )
        else:
            self.template_references_label.setText("Template references: None")

        transition_refs = list(metadata.get("transition_references", ()) or ())
        transition_count = int(metadata.get("transition_count", len(transition_refs)) or 0)
        transition_complete_count = int(metadata.get("transition_complete_count", 0) or 0)
        transition_incomplete_count = int(
            metadata.get("transition_incomplete_count", max(0, transition_count - transition_complete_count)) or 0
        )
        if transition_refs:
            self.transition_references_label.setText(
                f"Transitions: {transition_complete_count}/{transition_count} linked; "
                f"{transition_incomplete_count} need destination"
            )
        else:
            self.transition_references_label.setText("Transitions: None")
        self._set_transition_reference_rows(transition_refs)

        script_refs = list(metadata.get("script_references", ()) or ())
        script_count = int(metadata.get("script_reference_count", len(script_refs)) or 0)
        script_packaged_count = int(metadata.get("script_packaged_count", 0) or 0)
        script_external_count = int(metadata.get("script_external_count", max(0, script_count - script_packaged_count)) or 0)
        if script_refs:
            self.script_references_label.setText(
                f"ARE/IFO script hooks: {script_count} referenced, {script_packaged_count} packaged, "
                f"{script_external_count} external/Override"
            )
        else:
            self.script_references_label.setText("ARE/IFO script hooks: None")
        self._set_script_reference_rows(script_refs)

        if blocking:
            body = "Blocking: " + "; ".join(str(item) for item in blocking[:4])
            if len(blocking) > 4:
                body += f"; +{len(blocking) - 4} more"
        elif missing:
            missing_text = ", ".join(f"{resref}.{restype}" for resref, restype in missing[:6])
            body = f"Missing: {missing_text}"
            if len(missing) > 6:
                body += f", +{len(missing) - 6} more"
        elif warnings:
            body = "Warnings: " + "; ".join(str(item) for item in warnings[:4])
        else:
            body = "No readiness blockers."
        self.blocking_label.setText(body)
        self.next_action_label.setText(str(getattr(readiness, "next_action", "") or ""))
        self.game_test_button.setEnabled(bool(getattr(readiness, "ready_for_game_test", False)))
        self.launch_handoff_button.setEnabled(bool(elevated_launch_script or proof_manifest or installed_path))

    def _copy_text(self, text: str) -> None:
        value = str(text or "").strip()
        if not value:
            return
        QtWidgets.QApplication.clipboard().setText(value)

    def _update_copy_buttons(self) -> None:
        self.copy_warp_command_button.setEnabled(bool(self.warp_command_edit.text().strip()))
        self.copy_launch_helper_button.setEnabled(bool(self.launch_helper_edit.text().strip()))
        self.copy_proof_manifest_button.setEnabled(bool(self.proof_manifest_edit.text().strip()))

    @staticmethod
    def _normalise_resource_key(resource: Any) -> tuple[str, str]:
        if isinstance(resource, tuple) and len(resource) >= 2:
            return (str(resource[0] or "").strip().lower(), str(resource[1] or "").strip().lower().lstrip("."))
        return (str(resource or "").strip().lower(), "")

    @staticmethod
    def _format_resource_key(resource: Any) -> str:
        resref, restype = ModuleReadinessPanel._normalise_resource_key(resource)
        if resref and restype:
            return f"{resref}.{restype}"
        return resref or "(unknown resource)"

    def _set_runtime_resource_rows(self, expected: tuple[Any, ...], present: tuple[Any, ...], missing: tuple[Any, ...]) -> None:
        """Show which KOTOR runtime files are expected, present, or missing."""

        present_keys = {self._normalise_resource_key(item) for item in present}
        missing_keys = {self._normalise_resource_key(item) for item in missing}
        resources = tuple(expected or ())
        if not resources:
            self.runtime_resource_table.setRowCount(1)
            for column, text in enumerate((
                "No runtime resource list yet",
                "Not checked",
                "Create or open an authored KMAP module to see ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX readiness.",
            )):
                self.runtime_resource_table.setItem(0, column, self._table_item(text))
            return

        self.runtime_resource_table.setRowCount(len(resources))
        for row, resource in enumerate(resources):
            key = self._normalise_resource_key(resource)
            if key in present_keys:
                status = "Present"
                fix = "Ready for packaging/staging."
            elif key in missing_keys:
                status = "Missing"
                fix = "Generate or stage this runtime file before export/install."
            else:
                status = "Expected"
                fix = "Expected by the module contract; validate/export to confirm."
            for column, text in enumerate((self._format_resource_key(resource), status, fix)):
                self.runtime_resource_table.setItem(row, column, self._table_item(text))

    @staticmethod
    def _reference_value(reference: Any, key: str, default: Any = "") -> Any:
        if isinstance(reference, dict):
            return reference.get(key, default)
        return getattr(reference, key, default)

    def _set_transition_reference_rows(self, references: tuple[Any, ...] | list[Any]) -> None:
        """Show authored door, trigger, or waypoint transition link readiness."""

        rows = list(references or ())
        if not rows:
            self.transition_reference_table.setRowCount(1)
            for column, text in enumerate((
                "No transition references",
                "Not checked",
                "",
                "Add a door, trigger, or waypoint transition when this module needs area links.",
            )):
                self.transition_reference_table.setItem(0, column, self._table_item(text))
            return

        self.transition_reference_table.setRowCount(len(rows))
        for row, reference in enumerate(rows):
            kind = str(self._reference_value(reference, "kind", "transition") or "transition")
            tag = str(self._reference_value(reference, "tag", "") or "(untagged)")
            destination = str(
                self._reference_value(reference, "linked_to_module", "")
                or self._reference_value(reference, "linked_to", "")
                or self._reference_value(reference, "template_resref", "")
                or "(not linked)"
            )
            complete = bool(self._reference_value(reference, "complete", False))
            status = str(self._reference_value(reference, "status", "") or ("linked" if complete else "unlinked"))
            message = str(self._reference_value(reference, "message", "") or "")
            if not message:
                message = "Ready for export." if complete else "Choose a destination area/module before game proof."
            for column, text in enumerate((kind, tag, destination, f"{status}: {message}")):
                self.transition_reference_table.setItem(row, column, self._table_item(text))

    def _set_script_reference_rows(self, references: tuple[Any, ...] | list[Any]) -> None:
        """Show ARE/IFO script hook packaging readiness."""

        rows = list(references or ())
        if not rows:
            self.script_reference_table.setRowCount(1)
            for column, text in enumerate((
                "No ARE/IFO script hooks",
                "Not checked",
                "",
                "Assign ARE/IFO script hooks only when this module needs custom runtime behavior.",
            )):
                self.script_reference_table.setItem(0, column, self._table_item(text))
            return

        self.script_reference_table.setRowCount(len(rows))
        for row, reference in enumerate(rows):
            scope = str(self._reference_value(reference, "scope", "") or "module")
            field_name = str(self._reference_value(reference, "field_name", "") or "(unknown field)")
            script_resref = str(self._reference_value(reference, "script_resref", "") or "(missing script)")
            restype = str(self._reference_value(reference, "restype", "ncs") or "ncs").lstrip(".")
            packaged = bool(self._reference_value(reference, "packaged", False))
            status = str(self._reference_value(reference, "status", "") or ("packaged" if packaged else "external_or_override"))
            message = str(self._reference_value(reference, "message", "") or "")
            if not message:
                message = "Script will be packaged." if packaged else "Script must exist in the base game, Override, or another mod."
            for column, text in enumerate((scope, field_name, f"{script_resref}.{restype}", f"{status}: {message}")):
                self.script_reference_table.setItem(row, column, self._table_item(text))

    @staticmethod
    def _table_item(text: str) -> QtWidgets.QTableWidgetItem:
        item = QtWidgets.QTableWidgetItem(str(text or ""))
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        return item


__all__ = ["ModuleReadinessPanel"]
