"""JRL Editor settings: persistence and settings dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


try:
    from qtpy.QtCore import QSettings
except ImportError:
    from qtpy.QtCore import QSettings  # type: ignore[no-redef]


_FILTER_MODES: list[tuple[str, str]] = [
    ("smart", "Smart — show quest if name/tag OR any entry matches"),
    ("quest_only", "Quest only — match quest name or tag only"),
    ("all_levels", "All levels — show any quest or entry that matches"),
]

_SETTINGS_PREFIX = "jrl_editor/"


class JRLEditorSettings:
    """Persistent settings for the JRL editor, backed by QSettings."""

    def __init__(self) -> None:
        self._q = QSettings("HolocronToolset", "JRLEditor")

    @property
    def filter_mode(self) -> str:
        return str(self._q.value(f"{_SETTINGS_PREFIX}filter_mode", "smart"))

    @filter_mode.setter
    def filter_mode(self, value: str) -> None:
        self._q.setValue(f"{_SETTINGS_PREFIX}filter_mode", value)

    @property
    def jump_auto_open(self) -> bool:
        v = self._q.value(f"{_SETTINGS_PREFIX}jump_auto_open", True)
        if isinstance(v, bool):
            return v
        return str(v).lower() not in ("false", "0", "no")

    @jump_auto_open.setter
    def jump_auto_open(self, value: bool) -> None:
        self._q.setValue(f"{_SETTINGS_PREFIX}jump_auto_open", value)


class JRLSettingsDialog(QDialog):
    """Settings dialog for the JRL editor."""

    def __init__(self, parent: QWidget | None, settings: JRLEditorSettings) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Journal Editor Settings")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._filter_combo = QComboBox()
        for key, label in _FILTER_MODES:
            self._filter_combo.addItem(label, key)
        current_mode = settings.filter_mode
        for i in range(self._filter_combo.count()):
            if self._filter_combo.itemData(i) == current_mode:
                self._filter_combo.setCurrentIndex(i)
                break
        form.addRow(QLabel("Filter mode:"), self._filter_combo)

        self._jump_check = QCheckBox("Auto-open editor when exactly one result found")
        self._jump_check.setChecked(settings.jump_auto_open)
        form.addRow(QLabel("Jump to scripts/dialogs:"), self._jump_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self._settings.filter_mode = self._filter_combo.currentData()
        self._settings.jump_auto_open = self._jump_check.isChecked()
        self.accept()
