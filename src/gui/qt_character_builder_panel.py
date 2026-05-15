"""Qt character builder panels and window for GhostRigger."""

from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_theme import C, heading


def _import_model_data():
    try:
        from src.core.model_data import CharacterScene
    except ImportError:
        from core.model_data import CharacterScene  # type: ignore
    return CharacterScene


def _import_scene_io():
    try:
        from src.core.model_data import SceneIO
    except ImportError:
        from core.model_data import SceneIO  # type: ignore
    return SceneIO


class QtCharacterBuilderPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        title = QtWidgets.QHBoxLayout()
        title.addWidget(heading("Character Builder"))
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(["K1", "K2"])
        title.addWidget(self.game_combo)
        root.addLayout(title)

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._assembly_tab(), "Assembly")
        self.tabs.addTab(self._selection_tab(), "Selection")
        self.tabs.addTab(self._transform_tab(), "Transform")
        self.tabs.addTab(self._rig_tab(), "Rig")
        self.tabs.addTab(self._export_tab(), "Export")

    def _page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        return page

    def _assembly_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        page.layout().addWidget(QtWidgets.QPushButton("Load Body Template"))
        page.layout().addWidget(QtWidgets.QPushButton("Load Head Template"))
        page.layout().addWidget(QtWidgets.QPushButton("Assemble Character"))
        page.layout().addStretch(1)
        return page

    def _selection_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        self.parts_tree = QtWidgets.QTreeWidget()
        self.parts_tree.setHeaderLabels(["Slot", "Model", "Status"])
        page.layout().addWidget(self.parts_tree, 1)
        return page

    def _transform_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Fit Body", "Rotate Selected", "Scale Selected", "Reset Transform"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page

    def _rig_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Apply Template Rig", "Validate Character", "Preview Weights"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page

    def _export_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Export Scene", "Export Body", "Export Head", "Batch Export"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page


class QtCharacterBuilderWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        CharacterScene = _import_model_data()
        self.scene = CharacterScene(game_version="K1")
        self._scene_path = ""
        self.setWindowTitle("GhostRigger - Character Builder")
        self.resize(1100, 760)
        self.panel = QtCharacterBuilderPanel(self)
        self.setCentralWidget(self.panel)
        self._build_menubar()
        self._update_title()

    def _build_menubar(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_action = QtGui.QAction("New Scene", self)
        new_action.setShortcut(QtGui.QKeySequence.New)
        new_action.triggered.connect(lambda: self._new_scene())

        open_action = QtGui.QAction("Open Scene...", self)
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(lambda: self._open_scene())

        save_action = QtGui.QAction("Save Scene", self)
        save_action.setShortcut(QtGui.QKeySequence.Save)
        save_action.triggered.connect(lambda: self._save_scene())

        save_as_action = QtGui.QAction("Save Scene As...", self)
        save_as_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(lambda: self._save_scene(save_as=True))

        close_action = QtGui.QAction("Close", self)
        close_action.triggered.connect(self.close)

        file_menu.addAction(new_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(close_action)

    def _confirm_discard_or_save(self, prompt: str) -> bool:
        if not getattr(self.scene, "dirty", False):
            return True
        answer = QtWidgets.QMessageBox.question(
            self,
            "Unsaved Changes",
            prompt,
            QtWidgets.QMessageBox.Save
            | QtWidgets.QMessageBox.Discard
            | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save,
        )
        if answer == QtWidgets.QMessageBox.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.Save:
            return self._save_scene()
        return True

    @QtCore.Slot()
    def _new_scene(self) -> None:
        if not self._confirm_discard_or_save(
            "The current scene has unsaved changes. Save before creating a new scene?"
        ):
            return
        CharacterScene = _import_model_data()
        game_version = getattr(self.scene, "game_version", "K1")
        self.scene = CharacterScene(game_version=game_version)
        self._scene_path = ""
        self.statusBar().showMessage("New scene created", 3000)
        self._update_title()

    @QtCore.Slot()
    def _open_scene(self) -> None:
        if not self._confirm_discard_or_save("Save current scene before opening another?"):
            return
        SceneIO = _import_scene_io()
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Character Scene",
            "",
            f"GhostRigger Scene (*{SceneIO.EXTENSION});;All files (*.*)",
        )
        if not path:
            return
        try:
            self.scene = SceneIO.load(path, load_models=False)
            self._scene_path = path
            self.statusBar().showMessage(f"Scene loaded: {os.path.basename(path)}", 4000)
            self._update_title()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Open Failed", str(exc))

    @QtCore.Slot()
    def _save_scene(self, *, save_as: bool = False) -> bool:
        SceneIO = _import_scene_io()
        path = self._scene_path
        if not path or save_as:
            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Character Scene",
                "",
                f"GhostRigger Scene (*{SceneIO.EXTENSION});;All files (*.*)",
            )
            if not path:
                return False
            if not path.endswith(SceneIO.EXTENSION):
                path += SceneIO.EXTENSION
        try:
            SceneIO.save(self.scene, path)
            self._scene_path = path
            self.statusBar().showMessage(f"Scene saved: {os.path.basename(path)}", 4000)
            self._update_title()
            return True
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(exc))
            return False

    def _update_title(self) -> None:
        name = getattr(self.scene, "character_name", "") or ""
        if not name and self._scene_path:
            name = os.path.splitext(os.path.basename(self._scene_path))[0]
        dirty_marker = " *" if getattr(self.scene, "dirty", False) else ""
        suffix = f" - {name}" if name else ""
        self.setWindowTitle(f"GhostRigger - Character Builder{suffix}{dirty_marker}")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._confirm_discard_or_save(
            "The scene has unsaved changes. Save before closing?"
        ):
            event.accept()
        else:
            event.ignore()
