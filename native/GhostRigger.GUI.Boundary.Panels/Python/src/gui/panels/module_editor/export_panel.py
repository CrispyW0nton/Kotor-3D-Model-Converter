"""Export options panel for KMAP scenes."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleExportPanel(QtWidgets.QWidget):
    exportRequested = QtCore.Signal(bool)
    devTestModuleRequested = QtCore.Signal(bool)
    authoredModuleRequested = QtCore.Signal(bool)
    authoredModuleStageRequested = QtCore.Signal(bool)
    authoredModuleInstallRequested = QtCore.Signal(bool)

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
        root.addStretch(1)
