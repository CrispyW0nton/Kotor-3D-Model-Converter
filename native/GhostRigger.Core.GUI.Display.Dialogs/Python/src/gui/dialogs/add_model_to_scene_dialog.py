"""Explicit add/replace prompt for model-library imports."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6 import QtCore, QtWidgets


class AddModelToSceneChoice(str, Enum):
    CLEAR_AND_LOAD = "clear_and_load"
    ADD_TO_SCENE = "add_to_scene"
    CANCEL = "cancel"


class AddModelToSceneDialog(QtWidgets.QDialog):
    """Modal dialog with unambiguous scene import choices."""

    MIN_WIDTH = 420
    DEFAULT_WIDTH = 460
    MAX_WIDTH = 520

    def __init__(self, model_label: str = "model", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.choice = AddModelToSceneChoice.CANCEL
        self.setWindowTitle("Add Model to Scene")
        self.setModal(True)
        self.setSizeGripEnabled(False)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._build(model_label)
        self.apply_ghost_layout(None)

    def _build(self, model_label: str) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        message = QtWidgets.QLabel(
            "The current scene already contains objects. What would you like to do?"
        )
        message.setWordWrap(True)
        message.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        root.addWidget(message)

        detail = QtWidgets.QLabel(str(model_label or ""))
        detail.setObjectName("DialogSubtleLabel")
        detail.setWordWrap(True)
        detail.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        root.addWidget(detail)

        self.remember_check = QtWidgets.QCheckBox("Remember my choice for this session")
        root.addWidget(self.remember_check)

        self.placement_combo = QtWidgets.QComboBox()
        self.placement_combo.addItem("Auto offset if needed", "auto_offset")
        self.placement_combo.addItem("World origin", "origin")
        root.addWidget(self.placement_combo)

        buttons = QtWidgets.QDialogButtonBox()
        self.clear_button = buttons.addButton("Clear Scene and Load Model", QtWidgets.QDialogButtonBox.DestructiveRole)
        self.add_button = buttons.addButton("Add to Existing Scene", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = buttons.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        self.add_button.setDefault(True)
        buttons.clicked.connect(self._on_button_clicked)
        root.addWidget(buttons)

    def _on_button_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        if button is self.clear_button:
            self.choice = AddModelToSceneChoice.CLEAR_AND_LOAD
            self.accept()
        elif button is self.add_button:
            self.choice = AddModelToSceneChoice.ADD_TO_SCENE
            self.accept()
        else:
            self.choice = AddModelToSceneChoice.CANCEL
            self.reject()

    @property
    def remember_choice(self) -> bool:
        return bool(self.remember_check.isChecked())

    @property
    def placement_mode(self) -> str:
        return str(self.placement_combo.currentData() or "auto_offset")

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(
            "QLabel#DialogSubtleLabel {"
            f"color:{theme.color('text.secondary', theme.color('panel.text'))};"
            "}"
        )

    def apply_ghost_layout(self, layout) -> None:
        requested = int(getattr(layout, "dialog_width", self.DEFAULT_WIDTH) or self.DEFAULT_WIDTH)
        width = min(self.MAX_WIDTH, max(self.MIN_WIDTH, requested))
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        self.adjustSize()
        self.resize(width, self.sizeHint().height())
