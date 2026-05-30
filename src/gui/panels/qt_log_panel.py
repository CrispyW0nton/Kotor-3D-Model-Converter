"""Qt output log panel for GhostRigger."""

from __future__ import annotations

import codeop
import contextlib
import html
import io
import logging
from pathlib import Path
import re
import sys
import traceback
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, icon

log = logging.getLogger(__name__)


_EXCEPTION_RE = re.compile(r"\b(?:Traceback \(most recent call last\)|[A-Za-z_][\w.]*Error:|Exception:|CRITICAL|ERROR)\b")


def _normalise_log_level(level: str | int) -> str:
    if isinstance(level, int):
        if level >= logging.ERROR:
            return "error"
        if level >= logging.WARNING:
            return "warning"
        if level <= logging.DEBUG:
            return "debug"
        return "info"
    text = str(level or "info").strip().lower()
    if text in {"critical", "fatal", "exception", "error"}:
        return "error"
    if text in {"warn", "warning"}:
        return "warning"
    if text in {"success", "debug"}:
        return text
    return "info"


def _detect_log_level(message: str, level: str | int = "info") -> str:
    normalised = _normalise_log_level(level)
    if normalised != "info":
        return normalised
    if _EXCEPTION_RE.search(message):
        return "error"
    return normalised


class PythonLogSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighting for Python logging output and tracebacks."""

    def __init__(self, document: QtGui.QTextDocument):
        super().__init__(document)
        self._colors = {
            "time": QtGui.QColor(C["accent2"]),
            "debug": QtGui.QColor("#7f8c8d"),
            "info": QtGui.QColor(C["text2"]),
            "success": QtGui.QColor(C["success"]),
            "warning": QtGui.QColor(C["warning"]),
            "error": QtGui.QColor(C["error"]),
            "path": QtGui.QColor("#8ab4f8"),
            "call": QtGui.QColor("#c792ea"),
            "line": QtGui.QColor("#f6c177"),
        }
        self._rules = [
            (re.compile(r"^\[\d{2}:\d{2}:\d{2}\]"), "time"),
            (re.compile(r"\bDEBUG\b"), "debug"),
            (re.compile(r"\bINFO\b"), "info"),
            (re.compile(r"\bSUCCESS\b"), "success"),
            (re.compile(r"\b(?:WARNING|WARN)\b"), "warning"),
            (re.compile(r"\b(?:ERROR|CRITICAL|FATAL)\b"), "error"),
            (re.compile(r"Traceback \(most recent call last\):"), "error"),
            (re.compile(r"\b[A-Za-z_][\w.]*Error:"), "error"),
            (re.compile(r"\b(?:Exception|RuntimeError|ValueError|ImportError|TypeError|AttributeError):"), "error"),
            (re.compile(r'File ".*?", line \d+'), "path"),
            (re.compile(r"\bline \d+\b"), "line"),
            (re.compile(r"\bin [A-Za-z_][\w.<>]*"), "call"),
        ]

    def _format(self, color_name: str, *, bold: bool = False) -> QtGui.QTextCharFormat:
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(self._colors[color_name])
        if bold:
            fmt.setFontWeight(QtGui.QFont.Bold)
        return fmt

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        block_level = ""
        if re.search(r"\b(?:ERROR|CRITICAL|FATAL)\b|Traceback \(most recent call last\):|[A-Za-z_][\w.]*Error:", text):
            block_level = "error"
        elif re.search(r"\b(?:WARNING|WARN)\b", text):
            block_level = "warning"
        elif re.search(r"\bSUCCESS\b", text):
            block_level = "success"
        elif re.search(r"\bDEBUG\b", text):
            block_level = "debug"
        if block_level:
            self.setFormat(0, len(text), self._format(block_level))

        for pattern, color_name in self._rules:
            fmt = self._format(color_name, bold=color_name in {"error", "warning"})
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class _GuiLogEmitter(QtCore.QObject):
    record = QtCore.Signal(str, str)


class QtLogPanelHandler(logging.Handler):
    """Qt-safe logging handler that forwards Python log records to a log panel."""

    def __init__(self, panel: "QtLogPanel"):
        super().__init__(logging.DEBUG)
        self.panel = panel
        self.emitter = _GuiLogEmitter(panel)
        self.emitter.record.connect(panel.log)
        self.setFormatter(logging.Formatter("%(levelname)s  %(name)s  %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            level = _normalise_log_level(record.levelno)
            self.emitter.record.emit(message, level)
        except Exception:
            self.handleError(record)


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


def _make_log_tool_button(
    icon_name: str,
    tooltip: str,
    *,
    object_name: str = "LogPanelIconButton",
) -> QtWidgets.QToolButton:
    button = QtWidgets.QToolButton()
    button.setObjectName(object_name)
    button.setAutoRaise(False)
    button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
    button.setIcon(icon(icon_name, 18))
    button.setIconSize(QtCore.QSize(18, 18))
    button.setFixedSize(34, 24)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setProperty("compact", True)
    button.setProperty("_gr_ignore_layout_button_mode", True)
    button.setProperty("_gr_full_text", tooltip)
    return button


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
        header.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        label = QtWidgets.QLabel("// Python")
        label.setObjectName("PythonTerminalTitle")
        row.addWidget(label)
        row.addStretch(1)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(0)
        self.output.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.output.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.output.setObjectName("PythonTerminalOutput")

        self.input_row_host = QtWidgets.QFrame()
        self.input_row_host.setObjectName("PythonTerminalInputRow")
        self.input_row_host.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        input_row = QtWidgets.QHBoxLayout(self.input_row_host)
        input_row.setContentsMargins(0, 2, 0, 0)
        input_row.setSpacing(4)
        prompt = QtWidgets.QLabel(">>>")
        prompt.setStyleSheet(f"color:{C['accent2']}; font-family:monospace;")
        self.input = _PythonInput()
        self.input.setObjectName("PythonCommandInput")
        self.input.setMinimumHeight(24)
        self.input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.input.setPlaceholderText("Enter Python and press Return")
        self.input.returnPressed.connect(self._execute_input)
        self.input.historyPrevious.connect(self._history_previous)
        self.input.historyNext.connect(self._history_next)
        input_row.addWidget(prompt)
        input_row.addWidget(self.input, 1)

        self.run_button = _make_log_tool_button(
            "python_run",
            "Run Python command",
            object_name="PythonTerminalIconButton",
        )
        self.copy_button = _make_log_tool_button(
            "python_copy",
            "Copy Python output",
            object_name="PythonTerminalIconButton",
        )
        self.clear_button = _make_log_tool_button(
            "python_clear",
            "Clear Python output",
            object_name="PythonTerminalIconButton",
        )
        for button in (self.run_button, self.copy_button, self.clear_button):
            input_row.addWidget(button)
        self.run_button.clicked.connect(self._execute_input)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear)

        root.addWidget(header)
        root.addWidget(self.output, 1)
        root.addWidget(self.input_row_host)
        self.apply_native_theme()

    def apply_ghost_theme(self, theme) -> None:
        if theme is not None and getattr(theme, "is_native", lambda: False)():
            self.apply_native_theme()
            return
        background = theme.color("panel.backgroundAlt", theme.color("input.background"))
        text = theme.color("input.text")
        border = theme.color("input.focusBorder", theme.color("input.border"))
        radius = theme.metric("border.radius", 3)
        self.input.setStyleSheet(
            "QLineEdit#PythonCommandInput { "
            f"background: {background}; color: {text}; "
            f"border: 1px solid {border}; border-radius: {radius}px; "
            "padding: 4px 6px; "
            "}"
        )

    def apply_native_theme(self) -> None:
        palette = self.input.palette()
        base = palette.color(QtGui.QPalette.Base)
        lighter = base.lighter(132 if base.lightness() < 150 else 108)
        text = palette.color(QtGui.QPalette.Text)
        border = palette.color(QtGui.QPalette.Highlight)
        self.input.setStyleSheet(
            "QLineEdit#PythonCommandInput { "
            f"background: {lighter.name()}; color: {text.name()}; "
            f"border: 1px solid {border.name()}; border-radius: 3px; "
            "padding: 4px 6px; "
            "}"
        )

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
        header.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        self.title_label = QtWidgets.QLabel("// Output Log")
        self.title_label.setObjectName("LogSectionTitle")
        row.addWidget(self.title_label)
        row.addStretch(1)

        self.save_button = _make_log_tool_button("log_save", "Save output log")
        self.copy_button = _make_log_tool_button("log_copy", "Copy output log")
        self.clear_button = _make_log_tool_button("log_clear", "Clear output log")
        self.save_button.clicked.connect(self._save_log)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button.clicked.connect(self.clear)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(0)
        self.text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.text.setObjectName("PythonLogInspector")
        self.highlighter = PythonLogSyntaxHighlighter(self.text.document())

        self.log_footer = QtWidgets.QFrame()
        self.log_footer.setObjectName("LogFooter")
        self.log_footer.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        footer_row = QtWidgets.QHBoxLayout(self.log_footer)
        footer_row.setContentsMargins(4, 2, 4, 2)
        footer_row.setSpacing(4)
        footer_row.addStretch(1)
        for button in (self.save_button, self.copy_button, self.clear_button):
            footer_row.addWidget(button)

        log_layout.addWidget(header)
        log_layout.addWidget(self.text, 1)
        log_layout.addWidget(self.log_footer)

        self.terminal = QtPythonTerminalPanel(self)
        self.terminal.set_context(log_panel=self, parent_widget=self.parentWidget())
        self.content_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.log_content)
        self.content_splitter.addWidget(self.terminal)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 2)
        self.content_splitter.setSizes([900, 520])

        root.addWidget(self.content_splitter, 1)

    def apply_ghost_theme(self, theme) -> None:
        self.terminal.apply_ghost_theme(theme)

    def apply_native_theme(self) -> None:
        self.terminal.apply_native_theme()

    def log(self, msg: str, level: str = "info") -> None:
        stamp = QtCore.QTime.currentTime().toString("HH:mm:ss")
        level = _detect_log_level(msg, level)
        self._lines.append((stamp, msg, level))
        if len(self._lines) > self.MAX_LOG_LINES:
            self._lines = self._lines[-self.MAX_LOG_LINES :]
        self._render()
        if level == "error":
            self._surface_error_log()

    def get_text(self) -> str:
        return "\n".join(f"[{stamp}] {msg}" for stamp, msg, _level in self._lines)

    def get_html(self) -> str:
        rows = []
        for stamp, msg, level in self._lines:
            css = {
                "debug": "#7f8c8d",
                "info": C["text2"],
                "success": C["success"],
                "warning": C["warning"],
                "error": C["error"],
            }.get(level, C["text2"])
            rows.append(
                f'<div class="log-row {level}"><span class="stamp">[{html.escape(stamp)}]</span> '
                f'<span style="color:{css}">{html.escape(msg)}</span></div>'
            )
        return "\n".join(rows)

    def clear(self) -> None:
        self._lines.clear()
        self.text.clear()

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self.content_splitter.setVisible(not self._collapsed)

    def _render(self) -> None:
        self.text.setPlainText(self.get_text())
        self.text.moveCursor(QtGui.QTextCursor.End)

    def _surface_error_log(self) -> None:
        if self._collapsed:
            self._toggle_collapse()
        self.content_splitter.show()
        self.text.setFocus(QtCore.Qt.OtherFocusReason)
        self.text.raise_()

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


__all__ = ["PythonLogSyntaxHighlighter", "QtLogPanel", "QtLogPanelHandler", "QtPythonTerminalPanel"]
