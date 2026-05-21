"""Qt output log panel for GhostRigger."""

from __future__ import annotations

import codeop
import contextlib
import io
import logging
from pathlib import Path
import sys
import traceback
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C

log = logging.getLogger(__name__)


class _PythonInput(QtWidgets.QLineEdit):
    """Single-line terminal input with shell-style history navigation."""

    historyPrevious = QtCore.Signal()
    historyNext = QtCore.Signal()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() == QtCore.Qt.Key_Up:
            self.historyPrevious.emit()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key_Down:
            self.historyNext.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class QtPythonTerminalPanel(QtWidgets.QWidget):
    """Small embedded Python console for quick runtime inspection."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._compiler = codeop.CommandCompiler()
        self._buffer: list[str] = []
        self._history: list[str] = []
        self._history_index = 0
        self._namespace: dict[str, object] = {
            "__name__": "__ghostrigger_terminal__",
            "__doc__": "GhostRigger embedded Python terminal",
            "QtCore": QtCore,
            "QtGui": QtGui,
            "QtWidgets": QtWidgets,
        }
        self._build()
        self.write("GhostRigger Python terminal ready.\n")

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QtWidgets.QFrame()
        header.setObjectName("PythonTerminalHeader")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        label = QtWidgets.QLabel("// Python")
        label.setObjectName("PythonTerminalTitle")
        row.addWidget(label)
        row.addStretch(1)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(118)
        self.output.setMaximumHeight(220)
        self.output.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.output.setObjectName("PythonTerminalOutput")

        input_row = QtWidgets.QHBoxLayout()
        input_row.setContentsMargins(0, 2, 0, 0)
        input_row.setSpacing(4)
        prompt = QtWidgets.QLabel(">>>")
        prompt.setStyleSheet(f"color:{C['accent2']}; font-family:monospace;")
        self.input = _PythonInput()
        self.input.setPlaceholderText("Enter Python and press Return")
        self.input.returnPressed.connect(self._execute_input)
        self.input.historyPrevious.connect(self._history_previous)
        self.input.historyNext.connect(self._history_next)
        input_row.addWidget(prompt)
        input_row.addWidget(self.input, 1)

        footer = QtWidgets.QFrame()
        footer.setObjectName("PythonTerminalFooter")
        footer_row = QtWidgets.QHBoxLayout(footer)
        footer_row.setContentsMargins(4, 2, 4, 2)
        footer_row.setSpacing(4)
        footer_row.addStretch(1)

        self.run_button = QtWidgets.QPushButton("Run")
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.clear_button = QtWidgets.QPushButton("Clear")
        for button in (self.run_button, self.copy_button, self.clear_button):
            button.setProperty("compact", True)
            footer_row.addWidget(button)
        self.run_button.clicked.connect(self._execute_input)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear)

        root.addWidget(header)
        root.addWidget(self.output, 1)
        root.addLayout(input_row)
        root.addWidget(footer)

    def set_context(self, **values: object) -> None:
        self._namespace.update(values)

    def write(self, text: str) -> None:
        if not text:
            return
        self.output.moveCursor(QtGui.QTextCursor.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(QtGui.QTextCursor.End)

    def clear(self) -> None:
        self.output.clear()

    def _execute_input(self) -> None:
        line = self.input.text()
        self.input.clear()
        if not line and not self._buffer:
            return
        self._history.append(line)
        self._history_index = len(self._history)
        prompt = "... " if self._buffer else ">>> "
        self.write(f"{prompt}{line}\n")
        self._buffer.append(line)
        source = "\n".join(self._buffer)
        try:
            compiled = self._compiler(source, "<GhostRigger terminal>", "single")
        except Exception:
            self._buffer.clear()
            self._write_exception()
            return
        if compiled is None:
            return
        self._buffer.clear()
        stdout = io.StringIO()
        stderr = io.StringIO()
        old_displayhook = sys.displayhook

        def _displayhook(value):
            if value is not None:
                print(repr(value))

        sys.displayhook = _displayhook
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compiled, self._namespace, self._namespace)
        except Exception:
            traceback.print_exc(file=stderr)
        finally:
            sys.displayhook = old_displayhook
        self.write(stdout.getvalue())
        self.write(stderr.getvalue())

    def _write_exception(self) -> None:
        out = io.StringIO()
        traceback.print_exc(file=out)
        self.write(out.getvalue())

    def _copy_to_clipboard(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.output.toPlainText())

    def _history_previous(self) -> None:
        if not self._history:
            return
        self._history_index = max(0, self._history_index - 1)
        self.input.setText(self._history[self._history_index])

    def _history_next(self) -> None:
        if not self._history:
            return
        self._history_index = min(len(self._history), self._history_index + 1)
        self.input.setText("" if self._history_index == len(self._history) else self._history[self._history_index])


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

        self.log_content = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(self.log_content)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        header = QtWidgets.QFrame()
        header.setObjectName("LogHeader")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        self.title_label = QtWidgets.QLabel("// Output Log")
        self.title_label.setObjectName("LogSectionTitle")
        row.addWidget(self.title_label)
        row.addStretch(1)

        self.save_button = QtWidgets.QPushButton("Save")
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.save_button.clicked.connect(self._save_log)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear)

        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(118)
        self.text.setMaximumHeight(220)

        footer = QtWidgets.QFrame()
        footer.setObjectName("LogFooter")
        footer_row = QtWidgets.QHBoxLayout(footer)
        footer_row.setContentsMargins(4, 2, 4, 2)
        footer_row.setSpacing(4)
        footer_row.addStretch(1)
        for button in (self.save_button, self.copy_button, self.clear_button):
            button.setProperty("compact", True)
            footer_row.addWidget(button)

        log_layout.addWidget(header)
        log_layout.addWidget(self.text, 1)
        log_layout.addWidget(footer)

        self.terminal = QtPythonTerminalPanel(self)
        self.terminal.set_context(log_panel=self, parent_widget=self.parentWidget())
        self.content_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.log_content)
        self.content_splitter.addWidget(self.terminal)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 2)
        self.content_splitter.setSizes([900, 520])

        root.addWidget(self.content_splitter)

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
        self.content_splitter.setVisible(not self._collapsed)

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


__all__ = ["QtLogPanel", "QtPythonTerminalPanel"]
