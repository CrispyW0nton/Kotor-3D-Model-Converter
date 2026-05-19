"""Reusable Qt panel widgets for migration placeholders."""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6 import QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading, icon


class QtToolPanel(QtWidgets.QWidget):
    """Small helper for first-pass Qt ports of legacy Tk panels."""

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(6, 6, 6, 6)
        self.root.setSpacing(6)
        self.root.addWidget(heading(title))

    def add_group(self, title: str) -> tuple[QtWidgets.QGroupBox, QtWidgets.QVBoxLayout]:
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        self.root.addWidget(group)
        return group, layout

    def add_buttons(self, layout: QtWidgets.QBoxLayout, labels: Iterable[str]) -> list[QtWidgets.QPushButton]:
        buttons = []
        for label in labels:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.set_status(f"{text} is pending Qt behavior wiring."))
            layout.addWidget(button)
            buttons.append(button)
        return buttons

    def add_status(self, text: str = "") -> QtWidgets.QLabel:
        self.status_label = QtWidgets.QLabel(text)
        self.status_label.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        self.root.addWidget(self.status_label)
        return self.status_label

    def set_status(self, text: str) -> None:
        if not hasattr(self, "status_label"):
            self.add_status()
        self.status_label.setText(text)


def tab_icon(name: str):
    return icon(name, 16)

