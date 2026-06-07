"""Selection mode toolbar for the Mesh Tools dock."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.mesh_tools.mesh_edit_types import MeshSelectionMode
from src.mesh_tools.mesh_selection_modes import MESH_SELECTION_SHORTCUTS, MODE_ORDER


class QtMeshSelectionToolbar(CollapsibleGroupBox):
    modeRequested = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Selection Mode", parent)
        self._mode_buttons: dict[MeshSelectionMode, QtWidgets.QPushButton] = {}
        self._build()

    def _build(self) -> None:
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        for index, mode in enumerate(MODE_ORDER):
            button = QtWidgets.QPushButton(mode.label)
            button.setCheckable(True)
            shortcut = next((key for key, mapped in MESH_SELECTION_SHORTCUTS.items() if mapped is mode), "")
            button.setToolTip(f"{mode.label} mode" + (f" ({shortcut})" if shortcut else ""))
            button.clicked.connect(lambda _checked=False, m=mode: self.modeRequested.emit(m))
            self._mode_buttons[mode] = button
            grid.addWidget(button, index // 2, index % 2)

    def set_active_mode(self, mode: MeshSelectionMode) -> None:
        for button_mode, button in self._mode_buttons.items():
            button.blockSignals(True)
            button.setChecked(button_mode is mode)
            button.setProperty("accent", button_mode is mode)
            button.style().unpolish(button)
            button.style().polish(button)
            button.blockSignals(False)
