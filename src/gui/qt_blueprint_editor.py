"""Qt blueprint editor panel for GhostRigger."""

from __future__ import annotations

import json
from typing import Optional

from PySide6 import QtWidgets

from .qt_theme import heading


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
