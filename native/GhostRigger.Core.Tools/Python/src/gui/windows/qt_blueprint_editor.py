"""Qt blueprint editor panel for GhostRigger."""

from __future__ import annotations

import json
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import heading


class QtBlueprintEditorPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(heading("Blueprint Editor"))
        header.addStretch(1)
        actions = {
            "New": self.new_blueprint,
            "Open": self.open_blueprint,
            "Save": self.save_blueprint,
            "Export": self.save_blueprint,
        }
        for label, callback in actions.items():
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            header.addWidget(button)
        root.addLayout(header)
        splitter = QtWidgets.QSplitter()
        self.section_list = QtWidgets.QListWidget()
        self.section_list.addItems(["Module", "Rooms", "Walkmesh", "Resources", "Metadata"])
        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setPlaceholderText("Blueprint JSON / key-value editor migration host")
        splitter.addWidget(self.section_list)
        splitter.addWidget(self.editor)
        splitter.setSizes([180, 520])
        root.addWidget(splitter, 1)
        self._path = ""

    def new_blueprint(self) -> None:
        self._path = ""
        self.editor.setPlainText(json.dumps({"module": {}, "rooms": [], "resources": {}, "metadata": {}}, indent=2))

    def load_ipc_resource_payload(
        self,
        *,
        resource_type: str,
        resref: str,
        game: str = "",
        module_dir: str = "",
        raw: bytes | None = None,
    ) -> None:
        self._path = ""
        preview = ""
        if raw:
            preview = raw[:4096].decode("latin-1", errors="replace")
        payload = {
            "resource": {
                "type": resource_type,
                "resref": resref,
                "game": game,
                "module_dir": module_dir,
                "bytes": len(raw or b""),
            },
            "preview_latin1": preview,
            "metadata": {
                "source": "GhostRigger IPC",
            },
        }
        self.editor.setPlainText(json.dumps(payload, indent=2))

    def open_blueprint(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Blueprint",
            "",
            "Blueprint JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                self.editor.setPlainText(handle.read())
            self._path = path
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Open Blueprint", str(exc))

    def save_blueprint(self) -> None:
        path = self._path
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Blueprint",
                "blueprint.json",
                "Blueprint JSON (*.json);;All files (*.*)",
            )
            if not path:
                return
        try:
            text = self.editor.toPlainText()
            if text.strip():
                json.loads(text)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            self._path = path
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Blueprint", str(exc))


class QtBlueprintEditorWindow(QtWidgets.QMainWindow):
    """Standalone host for the Blueprint Editor panel."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Ghost-Studio Blueprint Editor")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.resize(820, 640)
        self.panel = QtBlueprintEditorPanel(self)
        self.setCentralWidget(self.panel)

    def new_blueprint(self) -> None:
        self.panel.new_blueprint()

    def open_blueprint(self) -> None:
        self.panel.open_blueprint()

    def save_blueprint(self) -> None:
        self.panel.save_blueprint()


__all__ = ["QtBlueprintEditorPanel", "QtBlueprintEditorWindow"]
