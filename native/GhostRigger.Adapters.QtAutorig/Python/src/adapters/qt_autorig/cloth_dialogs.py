"""Qt dialog adapters for cloth rig preset choices."""

from __future__ import annotations

from typing import Optional

from src.autorig.cloth_rig import ClothPresetChoice, ClothRigPreset


def _qt_application_running() -> bool:
    """Return True when a Qt application instance is available."""
    try:
        from PySide6.QtCore import QCoreApplication  # noqa: PLC0415

        return QCoreApplication.instance() is not None
    except Exception:
        return False


def run_cloth_preset_dialog(
    parent=None,
    default_preset: Optional[str] = None,
    title: str = "Cloth Rigging Preset",
    message: str = "Pick a cloth preset to apply to the selected node(s):",
) -> ClothPresetChoice:
    """Pick a cloth preset via Qt when available, default otherwise."""
    available = ClothRigPreset.names()
    if not available:
        return ClothPresetChoice(preset_name="", accepted=False)

    chosen_default = default_preset if default_preset in available else available[0]

    if not _qt_application_running():
        return ClothPresetChoice(preset_name=chosen_default, accepted=True)

    try:
        from PySide6.QtWidgets import QInputDialog  # noqa: PLC0415

        idx = available.index(chosen_default)
        name, ok = QInputDialog.getItem(parent, title, message, available, idx, False)
        if not ok or not name:
            return ClothPresetChoice(preset_name=chosen_default, accepted=False)
        return ClothPresetChoice(preset_name=name, accepted=True)
    except Exception:
        return ClothPresetChoice(preset_name=chosen_default, accepted=True)


def confirm_cloth_action(
    parent=None,
    title: str = "Cloth Rigging",
    message: str = "Apply cloth rig to the selected node(s)?",
) -> bool:
    """Confirm a cloth action via Qt when available, defaulting true headless."""
    if not _qt_application_running():
        return True

    try:
        from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

        reply = QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes
    except Exception:
        return True
