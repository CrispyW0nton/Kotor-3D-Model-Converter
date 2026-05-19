"""Small Qt dialogs used by the migrated GhostRigger shell."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from src.gui.qt_lib.rendering.viewport_navigation import VIEWPORT_NAVIGATION_HELP


def show_about(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.about(
        parent,
        "About GhostRigger",
        "GhostRigger-K1-K2\nOdyssey Engine Pipeline v6.1\n\nQt migration shell.",
    )


def show_format_reference(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "KotOR MDL Format Reference",
        "The full MDL/MDX format reference will be migrated into a Qt document viewer.",
    )


def show_viewport_navigation_reference(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "Viewport Navigation Controls",
        VIEWPORT_NAVIGATION_HELP,
    )


def show_ipc_info(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "IPC Protocol Info",
        "GhostRigger IPC runs on port 7001. GhostScripter and GModular integration will be wired into Qt next.",
    )

