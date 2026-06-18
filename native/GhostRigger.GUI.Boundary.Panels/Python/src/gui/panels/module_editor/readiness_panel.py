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
            self.blocking_label.setText("Create or open a Map Studio module project first.")
            self.next_action_label.setText("")
            self.game_test_button.setEnabled(False)
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


__all__ = ["ModuleReadinessPanel"]
