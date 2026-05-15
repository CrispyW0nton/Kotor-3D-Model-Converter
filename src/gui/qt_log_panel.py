"""Qt output log panel for GhostRigger."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_theme import C

log = logging.getLogger(__name__)


class QtLogPanel(QtWidgets.QWidget):
    MAX_LOG_LINES = 500

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._collapsed = False
        self._lines: list[tuple[str, str, str]] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QtWidgets.QFrame()
        header.setObjectName("LogHeader")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setText("// Output Log")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.toggle_button.clicked.connect(self._toggle_collapse)
        row.addWidget(self.toggle_button)
        row.addStretch(1)

        self.save_button = QtWidgets.QPushButton("Save")
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.save_button.clicked.connect(self._save_log)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear)
        for button in (self.save_button, self.copy_button, self.clear_button):
            button.setProperty("compact", True)
            row.addWidget(button)

        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(118)
        self.text.setMaximumHeight(220)

        root.addWidget(header)
        root.addWidget(self.text)

    def log(self, msg: str, level: str = "info") -> None:
        stamp = QtCore.QTime.currentTime().toString("HH:mm:ss")
        self._lines.append((stamp, msg, level))
        if len(self._lines) > self.MAX_LOG_LINES:
            self._lines = self._lines[-self.MAX_LOG_LINES :]
        self._render()

    def get_text(self) -> str:
        return "\n".join(f"[{stamp}] {msg}" for stamp, msg, _level in self._lines)

    def clear(self) -> None:
        self._lines.clear()
        self.text.clear()

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self.text.setVisible(not self._collapsed)
        self.toggle_button.setText(">> Output Log" if self._collapsed else "// Output Log")

    def _render(self) -> None:
        colors = {
            "info": C["text2"],
            "success": C["success"],
            "warning": C["warning"],
            "error": C["error"],
        }
        html = []
        for stamp, msg, level in self._lines:
            color = colors.get(level, C["text2"])
            html.append(
                f'<span style="color:{C["accent2"]}; font-size:8pt">[{stamp}]</span> '
                f'<span style="color:{color}">{msg}</span>'
            )
        self.text.setHtml("<br>".join(html))
        self.text.moveCursor(QtGui.QTextCursor.End)

    def _copy_to_clipboard(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.get_text())

    def _save_log(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Output Log",
            "ghostrigger_log.txt",
            "Text files (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.get_text(), encoding="utf-8")
        except Exception as exc:
            log.error("Log save failed: %s", exc)
