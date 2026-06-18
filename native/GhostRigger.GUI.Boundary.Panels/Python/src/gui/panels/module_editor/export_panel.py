"""Export options panel for KMAP scenes."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleExportPanel(QtWidgets.QWidget):
    exportRequested = QtCore.Signal(bool)
    devTestModuleRequested = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
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
        self.dry_run.setChecked(True)
        for widget in (self.visible_only, self.include_textures, self.include_lightmaps, self.include_walkmesh, self.copy_textures, self.dry_run):
            root.addWidget(widget)
        self.export_button = QtWidgets.QPushButton("Export FBX")
        self.export_button.clicked.connect(lambda: self.exportRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.export_button)
        self.dev_test_button = QtWidgets.QPushButton("Stage grdev01 Dev Test Module")
        self.dev_test_button.setObjectName("mapStudioStageDevTestModuleButton")
        self.dev_test_button.setToolTip("Build and stage the first from-scratch GhostRigger dev-test .mod package.")
        self.dev_test_button.clicked.connect(lambda: self.devTestModuleRequested.emit(self.dry_run.isChecked()))
        root.addWidget(self.dev_test_button)
        root.addStretch(1)
