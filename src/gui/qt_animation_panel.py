"""Qt animation panels for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import C, heading


class QtAnimationsPanel(QtWidgets.QWidget):
    animationSelected = QtCore.Signal(str)
    animationActionRequested = QtCore.Signal(str, str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animations"))
        self.listbox = QtWidgets.QListWidget()
        self.listbox.currentTextChanged.connect(self.animationSelected.emit)
        root.addWidget(self.listbox, 1)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMaximumHeight(90)
        root.addWidget(self.info)
        self.seek = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        root.addWidget(self.seek)
        controls = QtWidgets.QHBoxLayout()
        for label in ("Play", "Stop", "Loop", "Export"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            controls.addWidget(button)
        root.addLayout(controls)

    def load_model(self, model) -> None:
        self.listbox.clear()
        animations = getattr(model, "animations", []) or [] if model else []
        for anim in animations:
            self.listbox.addItem(getattr(anim, "name", str(anim)))
        self.info.setPlainText(f"{len(animations)} animation(s)")

    def selected_animation(self) -> str:
        item = self.listbox.currentItem()
        return item.text() if item else ""

    def _emit_action(self, action: str) -> None:
        self.animationActionRequested.emit(action, self.selected_animation())


class QtAnimationLibraryPanel(QtWidgets.QWidget):
    libraryActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animation Library"))
        scan = QtWidgets.QHBoxLayout()
        for label in ("Scan Animations", "Refresh"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            scan.addWidget(button)
        root.addLayout(scan)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter animations")
        root.addWidget(self.filter_edit)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Model", "Animation", "Frames", "Source"])
        root.addWidget(self.tree, 1)
        actions = QtWidgets.QHBoxLayout()
        for label in ("Load", "Preview", "Export"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            actions.addWidget(button)
        root.addLayout(actions)

    def set_entries(self, entries: list[dict]) -> None:
        self.tree.clear()
        for entry in entries:
            item = QtWidgets.QTreeWidgetItem([
                str(entry.get("model", "")),
                str(entry.get("animation", "")),
                str(entry.get("frames", "")),
                str(entry.get("source", "")),
            ])
            item.setData(0, QtCore.Qt.UserRole, entry)
            self.tree.addTopLevelItem(item)

    def selected_entry(self) -> Optional[dict]:
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None
