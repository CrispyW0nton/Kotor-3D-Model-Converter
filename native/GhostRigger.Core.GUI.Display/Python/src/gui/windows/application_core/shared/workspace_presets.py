"""Workspace/studio presets for the GhostRigger main window.

A *workspace preset* is a named arrangement of the detachable dock panels.
Switching presets shows the docks relevant to a task (modeling, rigging,
animation, level design) and hides the rest, instead of presenting all 17
panels at once.

Dock keys mirror the real ``_detachable_panels`` registry populated by
``WorkspaceDockMixin._create_detachable_panel`` (see ``workspace_docks.py``).
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

# QSettings scope shared with the rest of the main-window persistence.
WORKSPACE_QSETTINGS_ORG = "GhostRigger"
WORKSPACE_QSETTINGS_APP = "MainWindow"
WORKSPACE_QSETTINGS_KEY = "workspace_preset"

DEFAULT_WORKSPACE_PRESET = "modeling"

# Dock keys controlled by presets. Persistent utility docks (output_log,
# python_terminal, 2das, resources, sequence_editor) are intentionally left
# out so that presets only affect authoring panels.
WORKSPACE_DOCK_KEYS: tuple[str, ...] = (
    "scene",
    "content_browser",
    "properties",
    "animations",
    "body_attachment",
    "nodes",
    "lighting",
    "cameras",
    "module_meshes",
    "sprite_materials",
    "mesh_tools",
    "adjust_pivot",
    "diagnostics",
)

WORKSPACE_PRESETS: dict[str, dict] = {
    "modeling": {
        "label": "Modeling",
        "visible_docks": [
            "scene",
            "content_browser",
            "properties",
            "mesh_tools",
            "adjust_pivot",
        ],
        "hidden_docks": [
            "animations",
            "body_attachment",
            "lighting",
            "cameras",
            "module_meshes",
            "sprite_materials",
            "nodes",
            "diagnostics",
        ],
    },
    "rigging": {
        "label": "Rigging",
        "visible_docks": [
            "scene",
            "properties",
            "body_attachment",
            "animations",
            "nodes",
        ],
        "hidden_docks": [
            "content_browser",
            "lighting",
            "cameras",
            "module_meshes",
            "sprite_materials",
            "mesh_tools",
            "adjust_pivot",
            "diagnostics",
        ],
    },
    "animation": {
        "label": "Animation",
        "visible_docks": [
            "scene",
            "properties",
            "animations",
            "lighting",
            "cameras",
        ],
        "hidden_docks": [
            "content_browser",
            "body_attachment",
            "module_meshes",
            "sprite_materials",
            "mesh_tools",
            "adjust_pivot",
            "nodes",
            "diagnostics",
        ],
    },
    "level_design": {
        "label": "Level Design",
        "visible_docks": [
            "scene",
            "content_browser",
            "properties",
            "module_meshes",
            "lighting",
        ],
        "hidden_docks": [
            "animations",
            "body_attachment",
            "cameras",
            "sprite_materials",
            "mesh_tools",
            "adjust_pivot",
            "nodes",
            "diagnostics",
        ],
    },
}


def workspace_preset_choices() -> list[tuple[str, str]]:
    """Return ``(preset_id, label)`` pairs in a stable display order."""
    return [(key, str(preset.get("label", key))) for key, preset in WORKSPACE_PRESETS.items()]


def workspace_settings() -> QtCore.QSettings:
    """Return the QSettings handle used to persist the active workspace."""
    return QtCore.QSettings(WORKSPACE_QSETTINGS_ORG, WORKSPACE_QSETTINGS_APP)


def load_saved_workspace_preset() -> str:
    """Return the last-used workspace preset id, defaulting to modeling."""
    settings = workspace_settings()
    value = settings.value(WORKSPACE_QSETTINGS_KEY, DEFAULT_WORKSPACE_PRESET)
    preset_id = str(value or DEFAULT_WORKSPACE_PRESET)
    if preset_id not in WORKSPACE_PRESETS:
        return DEFAULT_WORKSPACE_PRESET
    return preset_id


def save_workspace_preset(preset_id: str) -> None:
    """Persist the active workspace preset id."""
    if preset_id not in WORKSPACE_PRESETS:
        return
    settings = workspace_settings()
    settings.setValue(WORKSPACE_QSETTINGS_KEY, preset_id)


class WorkspaceSwitcher(QtWidgets.QWidget):
    """Compact combo box for switching between workspace presets.

    Emits :pyattr:`presetSelected` ``(preset_id)`` when the user picks a new
    workspace. The combo is populated from :data:`WORKSPACE_PRESETS` and is
    safe to construct before the dock panels exist.
    """

    presetSelected = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, current: str = DEFAULT_WORKSPACE_PRESET) -> None:
        super().__init__(parent)
        self.setObjectName("WorkspaceSwitcher")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QtWidgets.QLabel("Workspace", self)
        label.setObjectName("WorkspaceSwitcherLabel")
        label.setStyleSheet("background:transparent;")
        layout.addWidget(label)

        self._combo = QtWidgets.QComboBox(self)
        self._combo.setObjectName("WorkspaceSwitcherCombo")
        self._combo.setToolTip("Switch the active workspace (dock panel arrangement).")
        self._combo.setMinimumWidth(150)
        layout.addWidget(self._combo)

        self._populate(current)
        self._combo.currentIndexChanged.connect(self._on_index_changed)

    def _populate(self, current: str) -> None:
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for preset_id, label in workspace_preset_choices():
                self._combo.addItem(label, preset_id)
            index = self._combo.findData(current)
            self._combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._combo.blockSignals(False)

    def _on_index_changed(self, _index: int) -> None:
        preset_id = str(self._combo.currentData() or DEFAULT_WORKSPACE_PRESET)
        self.presetSelected.emit(preset_id)

    def set_current_preset(self, preset_id: str, *, emit: bool = False) -> None:
        """Update the combo selection without triggering a signal by default."""
        if preset_id not in WORKSPACE_PRESETS:
            return
        index = self._combo.findData(preset_id)
        if index < 0:
            return
        if emit:
            self._combo.setCurrentIndex(index)
        else:
            self._combo.blockSignals(True)
            try:
                self._combo.setCurrentIndex(index)
            finally:
                self._combo.blockSignals(False)
