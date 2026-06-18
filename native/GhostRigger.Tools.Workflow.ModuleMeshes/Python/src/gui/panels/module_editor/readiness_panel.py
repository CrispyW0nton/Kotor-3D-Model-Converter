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

        self.authored_summary_label = QtWidgets.QLabel("Authored content: Not checked")
        self.authored_summary_label.setObjectName("mapStudioReadinessAuthoredSummaryLabel")
        self.authored_summary_label.setWordWrap(True)
        root.addWidget(self.authored_summary_label)

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
            self.preview_label.setText("Preview: Not ready")
            self.export_label.setText("Export: Not ready")
            self.runtime_label.setText("Runtime resources: Not checked")
            self.proof_label.setText("Game proof: Not staged")
            self.proof_recorder_label.setText("Proof recorder: Not ready")
            self.launch_label.setText("Launch handoff: Not ready")
            self.authored_summary_label.setText("Authored content: Not checked")
            self.blocking_label.setText("Create or open a Map Studio module project first.")
            self.next_action_label.setText("")
            self.game_test_button.setEnabled(False)
            self.launch_handoff_button.setEnabled(False)
            return

        module_root = str(getattr(readiness, "module_root", "") or "(unnamed)")
        game = str(getattr(readiness, "game", "") or "(game not selected)")
        stage = str(getattr(readiness, "capability_stage", "blocked") or "blocked").replace("_", " ")
        expected = tuple(getattr(readiness, "expected_runtime_resources", ()) or ())
        missing = tuple(getattr(readiness, "missing_runtime_resources", ()) or ())
        blocking = tuple(getattr(readiness, "blocking_messages", ()) or ())
        warnings = tuple(getattr(readiness, "warnings", ()) or ())

        self.header_label.setText(f"Module: {module_root} ({game})")
        self.stage_label.setText(f"Stage: {stage}")
        self.preview_label.setText(f"Preview: {getattr(readiness, 'preview_status', 'Not ready')}")
        self.export_label.setText(f"Export: {getattr(readiness, 'export_status', 'Not ready')}")
        if expected:
            self.runtime_label.setText(f"Runtime resources: {len(expected) - len(missing)}/{len(expected)} present")
        else:
            self.runtime_label.setText("Runtime resources: Not checked")
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
        room_text = ""
        if styles:
            first = dict(styles[0])
            room_text = (
                f"{first.get('room_resref', 'room')} uses {first.get('texture', '(no texture)')} / "
                f"{first.get('floor_surface_name', 'surface')} {first.get('floor_surface_id', '')}"
            )
        self.authored_summary_label.setText(
            f"Authored content: {room_text or 'No room style summary'}; {placement_total} gameplay placement(s)"
        )

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


__all__ = ["ModuleReadinessPanel"]
