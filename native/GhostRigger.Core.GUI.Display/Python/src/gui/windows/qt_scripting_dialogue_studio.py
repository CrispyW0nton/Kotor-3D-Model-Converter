"""GhostStudio-native Scripting Suite presentation.

The workbench is a full-size, non-modal product surface.  It owns Qt widgets,
shortcuts, theme/layout application, and user gestures only; document IO,
compilation, DLG mutation, validation, and packaging are delegated to the
controller/service layer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.scripting.dialogue_contract import (
    DialogueGraphLink,
    DialogueGraphNode,
    DialogueGraphSnapshot,
)
from src.gui.widgets.dialogue_graph_widget import DialogueGraphWidget
from src.gui.windows.qt_scripting_data_pages import (
    LipSoundSetPage,
    QuestJournalPage,
    TalkTablePage,
    TwoDAGlobalsPage,
)
from src.gui.windows.qt_scripting_integrated_tools_page import QtScriptingIntegratedToolsPage
from src.gui.windows.qt_scripting_project_package_pages import (
    QtScriptingPackageOverridePage,
    QtScriptingProjectHistoryPage,
)
from src.gui.windows.qt_scripting_quest_builder_page import QtQuestScaffoldPage
from src.gui.windows.qt_scripting_reference_page import QtNWScriptReferencePage
from src.gui.windows.qt_scripting_tutorial_page import QtScriptingTutorialPage


DOCUMENT_ROLE = int(QtCore.Qt.UserRole) + 21
RESOURCE_ROW_ROLE = DOCUMENT_ROLE + 1

_NSS_KEYWORDS = (
    "break", "case", "const", "continue", "default", "do", "else", "false",
    "for", "if", "return", "struct", "switch", "true", "while",
)
_NSS_TYPES = (
    "action", "effect", "event", "float", "int", "itemproperty", "location",
    "object", "string", "talent", "vector", "void",
)
_COMMON_NWSCRIPT_SYMBOLS = tuple(sorted(set(_NSS_KEYWORDS + _NSS_TYPES + (
    "ActionMoveToLocation", "ActionRandomWalk", "ActionStartConversation",
    "AssignCommand", "CreateObject", "DelayCommand", "DestroyObject",
    "ExecuteScript", "GetEnteringObject", "GetFirstPC", "GetLocation",
    "GetObjectByTag", "GetPCSpeaker", "GetPosition", "GetTag", "GetUserDefinedEventNumber",
    "OBJECT_INVALID", "SendMessageToPC", "SetGlobalBoolean", "SetGlobalNumber",
    "SignalEvent", "StartingConditional", "main",
))))


class NssSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Small theme-aware NWScript highlighter with no game-definition ownership."""

    def __init__(self, document: QtGui.QTextDocument):
        super().__init__(document)
        self._formats: dict[str, QtGui.QTextCharFormat] = {}
        self._rules: list[tuple[QtCore.QRegularExpression, str]] = []
        self.apply_palette(QtWidgets.QApplication.palette())

    @staticmethod
    def _format(color: QtGui.QColor, *, bold: bool = False, italic: bool = False) -> QtGui.QTextCharFormat:
        value = QtGui.QTextCharFormat()
        value.setForeground(color)
        value.setFontWeight(QtGui.QFont.Bold if bold else QtGui.QFont.Normal)
        value.setFontItalic(italic)
        return value

    def apply_palette(self, palette: QtGui.QPalette) -> None:
        text = palette.color(QtGui.QPalette.Text)
        accent = palette.color(QtGui.QPalette.Highlight)
        link = palette.color(QtGui.QPalette.Link)
        disabled = palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text)
        bright = palette.color(QtGui.QPalette.BrightText)
        self._formats = {
            "keyword": self._format(accent, bold=True),
            "type": self._format(link, bold=True),
            "number": self._format(bright),
            "string": self._format(link),
            "comment": self._format(disabled, italic=True),
            "function": self._format(text, bold=True),
        }
        keyword_pattern = r"\b(?:" + "|".join(map(re.escape, _NSS_KEYWORDS)) + r")\b"
        type_pattern = r"\b(?:" + "|".join(map(re.escape, _NSS_TYPES)) + r")\b"
        self._rules = [
            (QtCore.QRegularExpression(keyword_pattern), "keyword"),
            (QtCore.QRegularExpression(type_pattern), "type"),
            (QtCore.QRegularExpression(r"\b(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)\b"), "number"),
            (QtCore.QRegularExpression(r'"(?:\\.|[^"\\])*"'), "string"),
            (QtCore.QRegularExpression(r"\b[A-Za-z_]\w*(?=\s*\()"), "function"),
            (QtCore.QRegularExpression(r"//[^\n]*"), "comment"),
        ]
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        for expression, style in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), self._formats[style])


class _NssLineNumberArea(QtWidgets.QWidget):
    """Palette-driven line-number gutter owned by :class:`NssCodeEditor`."""

    def __init__(self, editor: "NssCodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("scriptingStudioNssLineNumberArea")

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt API
        return QtCore.QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt API
        self.editor.paint_line_number_area(event)


class NssCodeEditor(QtWidgets.QPlainTextEdit):
    """NWScript editor with line numbers and definition-backed completion."""

    cursorStatusChanged = QtCore.Signal(int, int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("scriptingStudioNssCodeEditor")
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setTabStopDistance(QtGui.QFontMetricsF(self.font()).horizontalAdvance(" ") * 4)
        fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.setFont(fixed)
        self.highlighter = NssSyntaxHighlighter(self.document())
        self.completer = QtWidgets.QCompleter(_COMMON_NWSCRIPT_SYMBOLS, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.activated.connect(self._insert_completion)
        self._completion_definitions: dict[str, dict[str, Any]] = {}
        self.cursorPositionChanged.connect(self._emit_cursor_status)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.line_number_area = _NssLineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width()
        self._highlight_current_line()

    def set_completion_symbols(self, symbols: object) -> None:
        values = sorted({str(value) for value in tuple(symbols or ()) if str(value).strip()}, key=str.casefold)
        model = QtCore.QStringListModel(values or list(_COMMON_NWSCRIPT_SYMBOLS), self.completer)
        self.completer.setModel(model)

    def set_completion_definitions(self, definitions: object) -> None:
        """Install definition metadata used for call insertion and signature help."""

        rows: dict[str, dict[str, Any]] = {}
        symbols = set(_COMMON_NWSCRIPT_SYMBOLS)
        for value in tuple(definitions or ()):
            if not isinstance(value, Mapping):
                continue
            name = str(value.get("name") or "").strip()
            if not name:
                continue
            row = dict(value)
            row["name"] = name
            rows[name.casefold()] = row
            symbols.add(name)
        self._completion_definitions = rows
        self.set_completion_symbols(symbols)

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rectangle: QtCore.QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rectangle.y(), self.line_number_area.width(), rectangle.height())
        if rectangle.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        content = self.contentsRect()
        self.line_number_area.setGeometry(
            QtCore.QRect(content.left(), content.top(), self.line_number_area_width(), content.height())
        )

    def paint_line_number_area(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self.line_number_area)
        palette = self.palette()
        painter.fillRect(event.rect(), palette.color(QtGui.QPalette.AlternateBase))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color_group = (
                    QtGui.QPalette.Active
                    if block_number == self.textCursor().blockNumber()
                    else QtGui.QPalette.Disabled
                )
                painter.setPen(palette.color(color_group, QtGui.QPalette.Text))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        selection = QtWidgets.QTextEdit.ExtraSelection()
        color = self.palette().color(QtGui.QPalette.Highlight)
        color.setAlpha(28)
        selection.format.setBackground(color)
        selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection] if not self.isReadOnly() else [])
        self.line_number_area.update()

    def _emit_cursor_status(self) -> None:
        cursor = self.textCursor()
        self.cursorStatusChanged.emit(cursor.blockNumber() + 1, cursor.positionInBlock() + 1)

    def _word_under_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def _insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        definition = self._completion_definitions.get(str(completion).casefold(), {})
        is_function = str(definition.get("kind") or "").casefold() == "function"
        if is_function:
            cursor.insertText(f"{completion}()")
            if tuple(definition.get("parameters") or ()):
                cursor.movePosition(QtGui.QTextCursor.Left)
        else:
            cursor.insertText(completion)
        self.setTextCursor(cursor)
        if is_function:
            self._show_signature(completion)

    def _function_before_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Left, QtGui.QTextCursor.KeepAnchor)
        if cursor.selectedText() != "(":
            return ""
        cursor.clearSelection()
        cursor.movePosition(QtGui.QTextCursor.Left)
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def _show_signature(self, function_name: str) -> None:
        definition = self._completion_definitions.get(str(function_name).casefold(), {})
        signature = str(definition.get("signature") or "").strip()
        if not signature:
            return
        description = str(definition.get("description") or "").strip()
        help_text = signature if not description else f"{signature}\n{description}"
        point = self.viewport().mapToGlobal(self.cursorRect().bottomRight())
        QtWidgets.QToolTip.showText(point, help_text, self)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API
        if self.completer.popup().isVisible() and event.key() in {
            QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return, QtCore.Qt.Key_Escape,
            QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab,
        }:
            event.ignore()
            return
        explicit = event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Space
        if not explicit:
            super().keyPressEvent(event)
        if event.text() == "(":
            self._show_signature(self._function_before_cursor())
        prefix = self._word_under_cursor()
        if explicit or (len(prefix) >= 2 and event.text() and (event.text().isalnum() or event.text() == "_")):
            self.completer.setCompletionPrefix(prefix)
            rectangle = self.cursorRect()
            rectangle.setWidth(
                self.completer.popup().sizeHintForColumn(0)
                + self.completer.popup().verticalScrollBar().sizeHint().width()
            )
            self.completer.complete(rectangle)
        else:
            self.completer.popup().hide()

    def goto_location(self, line: int | None, column: int | None = None) -> None:
        if line is None:
            return
        block = self.document().findBlockByLineNumber(max(0, int(line) - 1))
        if not block.isValid():
            return
        cursor = QtGui.QTextCursor(block)
        cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor, max(0, int(column or 1) - 1))
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()


class ScriptEditorPage(QtWidgets.QWidget):
    sourceChanged = QtCore.Signal(str, str)

    def __init__(
        self,
        document_id: str,
        source: str,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        disassembly: str = "",
        recovered_source_exact: bool = False,
    ):
        super().__init__(parent)
        self.document_id = str(document_id)
        self.setObjectName("scriptingStudioScriptEditorPage")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        guidance_text = (
            "NWScript source — Ctrl+Space completes common symbols. Compile diagnostics open at the reported line."
        )
        if disassembly:
            recovery = "exact-byte recompile passed" if recovered_source_exact else "reconstruction is not byte-identical"
            guidance_text += f" Imported NCS: {recovery}; Disassembly is authoritative."
        guidance = QtWidgets.QLabel(guidance_text)
        guidance.setObjectName("scriptingStudioScriptGuidanceLabel")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.editor_tabs = QtWidgets.QTabWidget(self)
        self.editor_tabs.setObjectName("scriptingStudioScriptRepresentationTabs")
        self.editor = NssCodeEditor(self.editor_tabs)
        self.editor.setPlainText(source)
        self.editor_tabs.addTab(self.editor, "Recovered Source" if disassembly else "Source")
        self.disassembly_editor = QtWidgets.QPlainTextEdit(self.editor_tabs)
        self.disassembly_editor.setObjectName("scriptingStudioNcsDisassembly")
        self.disassembly_editor.setReadOnly(True)
        self.disassembly_editor.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.disassembly_editor.setFont(fixed_font)
        if disassembly:
            self.disassembly_editor.setPlainText(str(disassembly))
            self.editor_tabs.addTab(self.disassembly_editor, "Authoritative Disassembly")
        layout.addWidget(self.editor_tabs, 1)
        footer = QtWidgets.QGridLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        self.find_edit = QtWidgets.QLineEdit()
        self.find_edit.setObjectName("scriptingStudioScriptFindEdit")
        self.find_edit.setPlaceholderText("Find in script…")
        self.find_edit.setClearButtonEnabled(True)
        self.replace_edit = QtWidgets.QLineEdit()
        self.replace_edit.setObjectName("scriptingStudioScriptReplaceEdit")
        self.replace_edit.setPlaceholderText("Replace with…")
        self.replace_edit.setClearButtonEnabled(True)
        find_previous = QtWidgets.QToolButton()
        find_previous.setText("Previous")
        find_previous.clicked.connect(lambda: self._find(backward=True))
        find_next = QtWidgets.QToolButton()
        find_next.setText("Next")
        find_next.clicked.connect(lambda: self._find(backward=False))
        replace_next = QtWidgets.QToolButton()
        replace_next.setText("Replace")
        replace_next.clicked.connect(self._replace_next)
        replace_all = QtWidgets.QToolButton()
        replace_all.setText("Replace All")
        replace_all.clicked.connect(self._replace_all)
        self.cursor_label = QtWidgets.QLabel("Ln 1, Col 1")
        self.cursor_label.setObjectName("scriptingStudioCursorLabel")
        footer.addWidget(self.find_edit, 0, 0)
        footer.addWidget(find_previous, 0, 1)
        footer.addWidget(find_next, 0, 2)
        footer.addWidget(self.cursor_label, 0, 4, QtCore.Qt.AlignRight)
        footer.addWidget(self.replace_edit, 1, 0)
        footer.addWidget(replace_next, 1, 1)
        footer.addWidget(replace_all, 1, 2)
        footer.setColumnStretch(0, 1)
        footer.setColumnStretch(3, 1)
        layout.addLayout(footer)
        self.editor.cursorStatusChanged.connect(
            lambda line, column: self.cursor_label.setText(f"Ln {line}, Col {column}")
        )
        self.editor.textChanged.connect(
            lambda: self.sourceChanged.emit(self.document_id, self.editor.toPlainText())
        )
        self.find_edit.returnPressed.connect(lambda: self._find(backward=False))
        self.replace_edit.returnPressed.connect(self._replace_next)
        self._install_editor_shortcuts()

    def _install_editor_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+F", lambda: self._focus_search(replace=False)),
            ("Ctrl+H", lambda: self._focus_search(replace=True)),
            ("Ctrl+G", self._goto_line_prompt),
            ("F3", lambda: self._find(backward=False)),
            ("Shift+F3", lambda: self._find(backward=True)),
        )
        self._shortcuts: list[QtGui.QShortcut] = []
        for sequence, callback in shortcuts:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _focus_search(self, *, replace: bool) -> None:
        field = self.replace_edit if replace else self.find_edit
        field.setFocus()
        field.selectAll()

    def _find(self, *, backward: bool) -> None:
        flags = QtGui.QTextDocument.FindBackward if backward else QtGui.QTextDocument.FindFlag()
        if self.find_edit.text() and not self.editor.find(self.find_edit.text(), flags):
            cursor = self.editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End if backward else QtGui.QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(self.find_edit.text(), flags)

    def _replace_next(self) -> None:
        needle = self.find_edit.text()
        if not needle:
            self._focus_search(replace=False)
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == needle:
            cursor.insertText(self.replace_edit.text())
            self.editor.setTextCursor(cursor)
        self._find(backward=False)

    def _replace_all(self) -> None:
        needle = self.find_edit.text()
        if not needle:
            self._focus_search(replace=False)
            return
        source = self.editor.toPlainText()
        updated = source.replace(needle, self.replace_edit.text())
        if updated != source:
            cursor = self.editor.textCursor()
            position = cursor.position()
            self.editor.setPlainText(updated)
            cursor = self.editor.textCursor()
            cursor.setPosition(min(position, len(updated)))
            self.editor.setTextCursor(cursor)

    def _goto_line_prompt(self) -> None:
        maximum = max(1, self.editor.document().blockCount())
        current = self.editor.textCursor().blockNumber() + 1
        line, accepted = QtWidgets.QInputDialog.getInt(
            self,
            "Go to NWScript Line",
            "Line number",
            current,
            1,
            maximum,
        )
        if accepted:
            self.editor.goto_location(line)

    def insert_template(self, source: str) -> None:
        self.editor.setPlainText(str(source or ""))
        self.editor.goto_location(1)

    def set_source(self, source: str) -> None:
        blocker = QtCore.QSignalBlocker(self.editor)
        self.editor.setPlainText(str(source or ""))
        del blocker

    def set_disassembly(self, disassembly: str, *, exact_recompile: bool = False) -> None:
        self.disassembly_editor.setPlainText(str(disassembly or ""))
        index = self.editor_tabs.indexOf(self.disassembly_editor)
        if disassembly and index < 0:
            self.editor_tabs.addTab(self.disassembly_editor, "Authoritative Disassembly")
        elif not disassembly and index >= 0:
            self.editor_tabs.removeTab(index)


class _OptionalNumberEditor(QtWidgets.QWidget):
    """Explicit optional integer/float editor; no sentinel reaches the model."""

    def __init__(self, *, decimal: bool = False, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.enabled_check = QtWidgets.QCheckBox("Set", self)
        if decimal:
            spin: QtWidgets.QAbstractSpinBox = QtWidgets.QDoubleSpinBox(self)
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setDecimals(4)
        else:
            spin = QtWidgets.QSpinBox(self)
            spin.setRange(-2_147_483_647, 2_147_483_647)
        self.spin = spin
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.spin, 1)
        self.enabled_check.toggled.connect(self.spin.setEnabled)
        self.set_value(None)

    def set_value(self, value: object) -> None:
        present = value is not None and value != ""
        self.enabled_check.setChecked(present)
        self.spin.setEnabled(present)
        if present:
            if isinstance(self.spin, QtWidgets.QDoubleSpinBox):
                self.spin.setValue(float(value))
            else:
                self.spin.setValue(int(value))

    def value_or_none(self) -> int | float | None:
        return self.spin.value() if self.enabled_check.isChecked() else None


class _ScriptParameterEditor(QtWidgets.QWidget):
    """Five integer parameters plus the TSL string parameter."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.integer_spins: list[QtWidgets.QSpinBox] = []
        for index in range(5):
            label = QtWidgets.QLabel(str(index + 1), self)
            spin = QtWidgets.QSpinBox(self)
            spin.setRange(-2_147_483_647, 2_147_483_647)
            self.integer_spins.append(spin)
            layout.addWidget(label, 0, index)
            layout.addWidget(spin, 1, index)
        self.string_edit = QtWidgets.QLineEdit(self)
        self.string_edit.setPlaceholderText("String parameter")
        layout.addWidget(self.string_edit, 2, 0, 1, 5)

    def set_values(self, values: object) -> None:
        row = tuple(values or ())
        for index, spin in enumerate(self.integer_spins):
            spin.setValue(int(row[index] if index < len(row) else 0))
        self.string_edit.setText(str(row[5] if len(row) > 5 else ""))

    def values(self) -> tuple[int, int, int, int, int, str]:
        integers = tuple(spin.value() for spin in self.integer_spins)
        return (*integers, self.string_edit.text())


class _OptionalColorEditor(QtWidgets.QWidget):
    """Optional RGBA color using normalized engine components."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled_check = QtWidgets.QCheckBox("Set", self)
        layout.addWidget(self.enabled_check)
        self.spins: list[QtWidgets.QDoubleSpinBox] = []
        for label_text in ("R", "G", "B", "A"):
            layout.addWidget(QtWidgets.QLabel(label_text, self))
            spin = QtWidgets.QDoubleSpinBox(self)
            spin.setRange(0.0, 1.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.05)
            layout.addWidget(spin, 1)
            self.spins.append(spin)
        self.enabled_check.toggled.connect(self._set_spin_enabled)
        self.set_value(None)

    def _set_spin_enabled(self, enabled: bool) -> None:
        for spin in self.spins:
            spin.setEnabled(enabled)

    def set_value(self, value: object) -> None:
        row = tuple(value or ())
        present = len(row) in {3, 4}
        self.enabled_check.setChecked(present)
        self._set_spin_enabled(present)
        values = (*row, 1.0)[:4] if present else (0.0, 0.0, 0.0, 1.0)
        for spin, component in zip(self.spins, values):
            spin.setValue(float(component))

    def value_or_none(self) -> tuple[float, float, float, float] | None:
        if not self.enabled_check.isChecked():
            return None
        return tuple(spin.value() for spin in self.spins)


class DialogueEditorPage(QtWidgets.QWidget):
    fieldsApplied = QtCore.Signal(str, str, str, object)
    settingsApplied = QtCore.Signal(str, object)
    addStarterRequested = QtCore.Signal(str)
    addChildRequested = QtCore.Signal(str, str)
    linkExistingRequested = QtCore.Signal(str, str, str)
    startExistingRequested = QtCore.Signal(str, str)
    retargetLinkRequested = QtCore.Signal(str, str, str)
    removeLinkRequested = QtCore.Signal(str, str)
    deleteNodeRequested = QtCore.Signal(str, str)
    makeEditableCopyRequested = QtCore.Signal(str)
    audioPreviewRequested = QtCore.Signal(str, str, str)
    audioBrowseRequested = QtCore.Signal(str, str)
    audioStopRequested = QtCore.Signal(str)
    participantBrowseRequested = QtCore.Signal(str, str, str)

    def __init__(self, document_id: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.document_id = str(document_id)
        self._selected_row: dict[str, Any] = {}
        self._rows_by_link: dict[str, dict[str, Any]] = {}
        self._rows_by_node: dict[str, list[dict[str, Any]]] = {}
        self._tree_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._selection_syncing = False
        self._settings_row: dict[str, Any] = {}
        self._audio_active_field: str | None = None
        self._node_filter_timer = QtCore.QTimer(self)
        self._node_filter_timer.setSingleShot(True)
        self._node_filter_timer.setInterval(150)
        self._node_filter_timer.timeout.connect(self._apply_node_filter)
        self.setObjectName("scriptingStudioDialogueEditorPage")
        layout = QtWidgets.QVBoxLayout(self)
        margin = self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutLeftMargin, None, self)
        spacing = self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutVerticalSpacing, None, self)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(max(0, spacing))
        guidance = QtWidgets.QLabel(
            "Conversation graph — NPC entries lead to player replies, and replies lead back to entries. "
            "Link Existing supports shared branches and valid alternating cycles. "
            "Imported unknown GFF fields are preserved for topology-stable edits; use Make Editable Copy… "
            "before changing their graph."
        )
        guidance.setObjectName("scriptingStudioDialogueGuidanceLabel")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        buttons = QtWidgets.QHBoxLayout()
        self.topology_lock_label = QtWidgets.QLabel(
            "Topology locked: this imported DLG contains unmapped fields. The original is protected.",
            self,
        )
        self.topology_lock_label.setObjectName("scriptingStudioDialogueTopologyLockLabel")
        self.topology_lock_label.setWordWrap(True)
        layout.addWidget(self.topology_lock_label)
        self.add_starter_button = QtWidgets.QPushButton("Add New Starting Entry")
        self.add_starter_button.setObjectName("scriptingStudioDialogueAddStarterButton")
        self.add_child_button = QtWidgets.QPushButton("Add New Child")
        self.add_child_button.setObjectName("scriptingStudioDialogueAddChildButton")
        self.link_existing_button = QtWidgets.QPushButton("Link Existing…")
        self.link_existing_button.setObjectName("scriptingStudioDialogueLinkExistingButton")
        self.start_existing_button = QtWidgets.QPushButton("Start at Existing…")
        self.start_existing_button.setObjectName("scriptingStudioDialogueStartExistingButton")
        self.retarget_button = QtWidgets.QPushButton("Retarget Link…")
        self.retarget_button.setObjectName("scriptingStudioDialogueRetargetLinkButton")
        self.remove_button = QtWidgets.QPushButton("Remove Link")
        self.remove_button.setObjectName("scriptingStudioDialogueRemoveLinkButton")
        self.delete_node_button = QtWidgets.QPushButton("Delete Node…")
        self.delete_node_button.setObjectName("scriptingStudioDialogueDeleteNodeButton")
        self.make_editable_copy_button = QtWidgets.QPushButton("Make Editable Copy…")
        self.make_editable_copy_button.setObjectName("scriptingStudioDialogueMakeEditableCopyButton")
        buttons.addWidget(self.add_starter_button)
        buttons.addWidget(self.add_child_button)
        buttons.addWidget(self.link_existing_button)
        buttons.addWidget(self.start_existing_button)
        buttons.addWidget(self.retarget_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.delete_node_button)
        buttons.addWidget(self.make_editable_copy_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        filter_row = QtWidgets.QHBoxLayout()
        filter_label = QtWidgets.QLabel("Find conversation node")
        filter_label.setObjectName("scriptingStudioDialogueNodeFilterLabel")
        self.node_filter_edit = QtWidgets.QLineEdit(self)
        self.node_filter_edit.setObjectName("scriptingStudioDialogueNodeFilterEdit")
        self.node_filter_edit.setPlaceholderText("Search dialogue text, speaker, condition, script, or comment…")
        self.node_filter_edit.setClearButtonEnabled(True)
        self.node_kind_filter = QtWidgets.QComboBox(self)
        self.node_kind_filter.setObjectName("scriptingStudioDialogueNodeKindFilter")
        self.node_kind_filter.addItem("All nodes", "all")
        self.node_kind_filter.addItem("NPC entries", "entry")
        self.node_kind_filter.addItem("Player replies", "reply")
        self.node_filter_result_label = QtWidgets.QLabel("", self)
        self.node_filter_result_label.setObjectName("scriptingStudioDialogueNodeFilterResult")
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.node_filter_edit, 1)
        filter_row.addWidget(self.node_kind_filter)
        filter_row.addWidget(self.node_filter_result_label)
        self._node_filter_layout = filter_row

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setObjectName("scriptingStudioDialogueSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.view_tabs = QtWidgets.QTabWidget(self)
        self.view_tabs.setObjectName("scriptingStudioDialogueViewTabs")
        self.graph = DialogueGraphWidget(self.view_tabs)
        self.graph.setObjectName("scriptingStudioDialogueGraph")
        self.view_tabs.addTab(self.graph, "Graph")

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("scriptingStudioDialogueTree")
        self.tree.setHeaderLabels(["Conversation", "Speaker", "Conditions"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        outline_page = QtWidgets.QWidget(self.view_tabs)
        outline_page.setObjectName("scriptingStudioDialogueOutlinePage")
        outline_layout = QtWidgets.QVBoxLayout(outline_page)
        outline_layout.setContentsMargins(0, 0, 0, 0)
        outline_layout.addLayout(self._node_filter_layout)
        outline_layout.addWidget(self.tree, 1)
        self.view_tabs.addTab(outline_page, "Outline")
        self.splitter.addWidget(self.view_tabs)
        self.inspector = self._build_inspector()
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)

        self.tree.currentItemChanged.connect(self._selection_changed)
        self.graph.nodeSelected.connect(self._graph_node_selected)
        self.graph.linkSelected.connect(self._graph_link_selected)
        self.add_starter_button.clicked.connect(lambda: self.addStarterRequested.emit(self.document_id))
        self.add_child_button.clicked.connect(self._request_add_child)
        self.link_existing_button.clicked.connect(self._request_link_existing)
        self.start_existing_button.clicked.connect(self._request_start_existing)
        self.retarget_button.clicked.connect(self._request_retarget)
        self.remove_button.clicked.connect(self._request_remove)
        self.delete_node_button.clicked.connect(self._request_delete_node)
        self.make_editable_copy_button.clicked.connect(
            lambda: self.makeEditableCopyRequested.emit(self.document_id)
        )
        self.node_filter_edit.textChanged.connect(lambda _value: self._node_filter_timer.start())
        self.node_kind_filter.currentIndexChanged.connect(lambda _index: self._node_filter_timer.start())
        self.set_topology_policy(False)

    def _build_inspector(self) -> QtWidgets.QWidget:
        tabs = QtWidgets.QTabWidget(self)
        tabs.setObjectName("scriptingStudioDialogueInspectorScroll")
        self.inspector_tabs = tabs

        line_scroll, line_form = self._form_page("scriptingStudioDialogueLinePage")
        self.kind_label = QtWidgets.QLabel("No node selected")
        self.kind_label.setObjectName("scriptingStudioDialogueKindLabel")
        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setObjectName("scriptingStudioDialogueTextEdit")
        self.text_edit.setPlaceholderText("Spoken dialogue text")
        self.text_edit.setMinimumHeight(self.fontMetrics().height() * 5)
        self.text_stringref_spin = self._int_spin(-1)
        self.text_substrings_table = self._table(("Substring ID", "Localized text"), "scriptingStudioDialogueLocalizedTable")
        localized_editor = self._table_editor(
            self.text_substrings_table,
            lambda: self._append_table_row(self.text_substrings_table, (self.text_substrings_table.rowCount() * 2, "")),
        )
        self.speaker_edit = self._line("Speaker tag (entries)")
        self.listener_edit = self._line("Listener tag")
        self.node_comment_edit = self._line("Developer note for this line")
        self.delay_spin = self._int_spin(-1)
        self.wait_flags_spin = self._int_spin(0)
        line_form.addRow("Selected", self.kind_label)
        line_form.addRow("Text", self.text_edit)
        line_form.addRow("TLK stringref (-1 = embedded)", self.text_stringref_spin)
        line_form.addRow("Localized substrings", localized_editor)
        line_form.addRow("Speaker", self._participant_reference_controls("speaker", self.speaker_edit))
        line_form.addRow("Listener", self._participant_reference_controls("listener", self.listener_edit))
        line_form.addRow("Node comment", self.node_comment_edit)
        line_form.addRow("Delay (-1 = automatic)", self.delay_spin)
        line_form.addRow("Wait flags", self.wait_flags_spin)
        tabs.addTab(line_scroll, "Line")

        script_scroll, script_form = self._form_page("scriptingStudioDialogueScriptsPage")
        self.script1_edit = self._resref_line("Action script")
        self.script2_edit = self._resref_line("Second action script")
        self.script1_params = _ScriptParameterEditor(self)
        self.script2_params = _ScriptParameterEditor(self)
        self.condition1_edit = self._resref_line("First conditional script")
        self.condition2_edit = self._resref_line("Second conditional script")
        self.condition1_params = _ScriptParameterEditor(self)
        self.condition2_params = _ScriptParameterEditor(self)
        self.condition1_not = QtWidgets.QCheckBox("Invert first condition")
        self.condition2_not = QtWidgets.QCheckBox("Invert second condition")
        self.logic_or = QtWidgets.QCheckBox("Use OR when both conditions are set")
        self.is_child_check = QtWidgets.QCheckBox("Shared/child target (IsChild)")
        self.display_inactive_check = QtWidgets.QCheckBox("Show when condition is inactive (TSL)")
        self.link_comment_edit = self._line("Developer note for this branch")
        script_form.addRow("Action script", self.script1_edit)
        script_form.addRow("Action parameters", self.script1_params)
        script_form.addRow("Action script 2 (TSL)", self.script2_edit)
        script_form.addRow("Action 2 parameters", self.script2_params)
        script_form.addRow("Condition", self.condition1_edit)
        script_form.addRow("Condition parameters", self.condition1_params)
        script_form.addRow("Condition 2 (TSL)", self.condition2_edit)
        script_form.addRow("Condition 2 parameters", self.condition2_params)
        script_form.addRow(self.condition1_not)
        script_form.addRow(self.condition2_not)
        script_form.addRow(self.logic_or)
        script_form.addRow(self.is_child_check)
        script_form.addRow(self.display_inactive_check)
        script_form.addRow("Link comment", self.link_comment_edit)
        tabs.addTab(script_scroll, "Scripts & Links")

        audio_scroll, audio_form = self._form_page("scriptingStudioDialogueAudioQuestPage")
        self.sound_edit = self._resref_line("Sound resref")
        sound_controls = self._audio_reference_controls("sound", self.sound_edit)
        self.sound_exists_check = QtWidgets.QCheckBox("Sound resource exists")
        self.voice_edit = self._resref_line("Voice-over resref")
        voice_controls = self._audio_reference_controls("voice", self.voice_edit)
        self.quest_edit = self._line("Quest tag")
        self.quest_entry_spin = self._int_spin(0)
        self.plot_index_spin = self._int_spin(-1)
        self.plot_xp_spin = self._double_spin(-1_000_000.0, 1_000_000.0)
        self.record_vo_check = QtWidgets.QCheckBox("Record voice-over (TSL)")
        self.record_no_vo_override_check = QtWidgets.QCheckBox("Override RecordNoVO (TSL)")
        self.vo_text_changed_check = QtWidgets.QCheckBox("Voice-over text changed (TSL)")
        self.emotion_spin = self._int_spin(0)
        self.facial_spin = self._int_spin(0)
        self.alien_race_node_spin = self._int_spin(0)
        audio_form.addRow("Sound", sound_controls)
        audio_form.addRow("Sound preview", self.sound_audio_status)
        audio_form.addRow(self.sound_exists_check)
        audio_form.addRow("Voice-over", voice_controls)
        audio_form.addRow("Voice preview", self.voice_audio_status)
        audio_note = QtWidgets.QLabel(
            "Preview resolves the target game's WAV resource or a browsed local file. "
            "It does not stage the file or prove retail KOTOR playback."
        )
        audio_note.setObjectName("scriptingStudioDialogueAudioPreviewNote")
        audio_note.setWordWrap(True)
        audio_form.addRow(audio_note)
        audio_form.addRow("Quest", self.quest_edit)
        audio_form.addRow("Quest entry", self.quest_entry_spin)
        audio_form.addRow("Plot index", self.plot_index_spin)
        audio_form.addRow("Plot XP percentage", self.plot_xp_spin)
        audio_form.addRow(self.record_vo_check)
        audio_form.addRow(self.record_no_vo_override_check)
        audio_form.addRow(self.vo_text_changed_check)
        audio_form.addRow("Emotion ID", self.emotion_spin)
        audio_form.addRow("Facial animation ID", self.facial_spin)
        audio_form.addRow("Alien race node", self.alien_race_node_spin)
        tabs.addTab(audio_scroll, "Audio & Quest")

        camera_scroll, camera_form = self._form_page("scriptingStudioDialogueCameraPage")
        self.camera_angle_spin = self._int_spin(0)
        self.camera_anim_edit = _OptionalNumberEditor(parent=self)
        self.camera_id_edit = _OptionalNumberEditor(parent=self)
        self.camera_fov_edit = _OptionalNumberEditor(decimal=True, parent=self)
        self.camera_height_edit = _OptionalNumberEditor(decimal=True, parent=self)
        self.camera_effect_edit = _OptionalNumberEditor(parent=self)
        self.target_height_edit = _OptionalNumberEditor(decimal=True, parent=self)
        self.fade_type_spin = self._int_spin(0, 255)
        self.fade_color_edit = _OptionalColorEditor(self)
        self.fade_delay_edit = _OptionalNumberEditor(decimal=True, parent=self)
        self.fade_length_edit = _OptionalNumberEditor(decimal=True, parent=self)
        self.node_id_spin = self._int_spin(0)
        self.post_proc_node_spin = self._int_spin(0)
        self.unskippable_check = QtWidgets.QCheckBox("Node cannot be skipped (TSL)")
        camera_form.addRow("Camera angle", self.camera_angle_spin)
        camera_form.addRow("Camera animation", self.camera_anim_edit)
        camera_form.addRow("Camera ID", self.camera_id_edit)
        camera_form.addRow("Field of view", self.camera_fov_edit)
        camera_form.addRow("Height offset", self.camera_height_edit)
        camera_form.addRow("Video effect", self.camera_effect_edit)
        camera_form.addRow("Target height", self.target_height_edit)
        camera_form.addRow("Fade type", self.fade_type_spin)
        camera_form.addRow("Fade color", self.fade_color_edit)
        camera_form.addRow("Fade delay", self.fade_delay_edit)
        camera_form.addRow("Fade length", self.fade_length_edit)
        camera_form.addRow("Node ID (TSL)", self.node_id_spin)
        camera_form.addRow("Post-process node", self.post_proc_node_spin)
        camera_form.addRow(self.unskippable_check)
        tabs.addTab(camera_scroll, "Camera & FX")

        animation_scroll, animation_form = self._form_page("scriptingStudioDialogueAnimationsPage")
        self.animations_table = self._table(("Participant", "Animation ID"), "scriptingStudioDialogueAnimationsTable")
        animation_form.addRow(
            "Participant animations",
            self._table_editor(
                self.animations_table,
                lambda: self._append_table_row(self.animations_table, ("OWNER", 6)),
            ),
        )
        tabs.addTab(animation_scroll, "Animations")

        settings_scroll, settings_form = self._form_page("scriptingStudioDialogueSettingsPage")
        self.on_end_edit = self._resref_line("EndConversation script")
        self.on_abort_edit = self._resref_line("EndConverAbort script")
        self.skippable_check = QtWidgets.QCheckBox("Conversation can be skipped")
        self.delay_entry_spin = self._int_spin(0)
        self.delay_reply_spin = self._int_spin(0)
        self.ambient_track_edit = self._resref_line("Ambient music")
        self.animated_cut_check = QtWidgets.QCheckBox("Animated cutscene")
        self.camera_model_edit = self._resref_line("Camera model")
        self.conversation_type_combo = QtWidgets.QComboBox(self)
        self.conversation_type_combo.addItem("Human", 0)
        self.conversation_type_combo.addItem("Computer", 1)
        self.conversation_type_combo.addItem("Other", 2)
        self.conversation_type_combo.addItem("Unknown", 3)
        self.computer_type_combo = QtWidgets.QComboBox(self)
        self.computer_type_combo.addItem("Modern", 0)
        self.computer_type_combo.addItem("Ancient", 1)
        self.old_hit_check = QtWidgets.QCheckBox("Use legacy hit check")
        self.unequip_items_check = QtWidgets.QCheckBox("Unequip all items")
        self.unequip_hands_check = QtWidgets.QCheckBox("Unequip hand items")
        self.word_count_spin = self._int_spin(0)
        self.vo_id_edit = self._line("Voice-over set ID")
        self.root_comment_edit = self._line("Root author note")
        self.alien_race_owner_spin = self._int_spin(0)
        self.post_proc_owner_spin = self._int_spin(0)
        self.record_no_vo_spin = self._int_spin(0)
        self.next_node_id_spin = self._int_spin(0)
        self.stunts_table = self._table(("Participant", "Stunt model"), "scriptingStudioDialogueStuntsTable")
        settings_form.addRow("On end", self.on_end_edit)
        settings_form.addRow("On abort", self.on_abort_edit)
        settings_form.addRow(self.skippable_check)
        settings_form.addRow("Default entry delay", self.delay_entry_spin)
        settings_form.addRow("Default reply delay", self.delay_reply_spin)
        settings_form.addRow("Ambient track", self.ambient_track_edit)
        settings_form.addRow(self.animated_cut_check)
        settings_form.addRow("Camera model", self.camera_model_edit)
        settings_form.addRow("Conversation type", self.conversation_type_combo)
        settings_form.addRow("Computer style", self.computer_type_combo)
        settings_form.addRow(self.old_hit_check)
        settings_form.addRow(self.unequip_items_check)
        settings_form.addRow(self.unequip_hands_check)
        settings_form.addRow("Word count", self.word_count_spin)
        settings_form.addRow("VO ID", self.vo_id_edit)
        settings_form.addRow("Root comment", self.root_comment_edit)
        settings_form.addRow("Alien race owner", self.alien_race_owner_spin)
        settings_form.addRow("Post-process owner", self.post_proc_owner_spin)
        settings_form.addRow("RecordNoVO", self.record_no_vo_spin)
        settings_form.addRow("Next node ID", self.next_node_id_spin)
        settings_form.addRow(
            "Stunt models",
            self._table_editor(
                self.stunts_table,
                lambda: self._append_table_row(self.stunts_table, ("OWNER", "")),
            ),
        )
        self.apply_settings_button = QtWidgets.QPushButton("Apply Dialogue Settings")
        self.apply_settings_button.setObjectName("scriptingStudioDialogueApplySettingsButton")
        self.apply_settings_button.clicked.connect(self._apply_settings)
        settings_form.addRow(self.apply_settings_button)
        tabs.addTab(settings_scroll, "Dialogue")

        self.apply_button = QtWidgets.QPushButton("Apply Node & Link Properties")
        self.apply_button.setObjectName("scriptingStudioDialogueApplyButton")
        container = QtWidgets.QWidget(self)
        outer = QtWidgets.QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(tabs, 1)
        outer.addWidget(self.apply_button)
        self.apply_button.clicked.connect(self._apply_fields)
        return container

    def _form_page(self, object_name: str) -> tuple[QtWidgets.QScrollArea, QtWidgets.QFormLayout]:
        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName(object_name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget(scroll)
        form = QtWidgets.QFormLayout(content)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        scroll.setWidget(content)
        return scroll, form

    @staticmethod
    def _int_spin(minimum: int, maximum: int = 2_147_483_647) -> QtWidgets.QSpinBox:
        value = QtWidgets.QSpinBox()
        value.setRange(minimum, maximum)
        return value

    @staticmethod
    def _double_spin(minimum: float, maximum: float) -> QtWidgets.QDoubleSpinBox:
        value = QtWidgets.QDoubleSpinBox()
        value.setRange(minimum, maximum)
        value.setDecimals(4)
        return value

    def _table(self, headers: tuple[str, ...], object_name: str) -> QtWidgets.QTableWidget:
        table = QtWidgets.QTableWidget(0, len(headers), self)
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(list(headers))
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setMinimumHeight(self.fontMetrics().height() * 6)
        return table

    def _table_editor(self, table: QtWidgets.QTableWidget, add_callback: Callable[[], None]) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        buttons = QtWidgets.QHBoxLayout()
        add_button = QtWidgets.QToolButton(panel)
        add_button.setText("Add")
        remove_button = QtWidgets.QToolButton(panel)
        remove_button.setText("Remove")
        add_button.clicked.connect(add_callback)
        remove_button.clicked.connect(lambda: self._remove_selected_table_row(table))
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return panel

    @staticmethod
    def _append_table_row(table: QtWidgets.QTableWidget, values: object) -> None:
        row_index = table.rowCount()
        table.insertRow(row_index)
        for column, value in enumerate(tuple(values or ())):
            table.setItem(row_index, column, QtWidgets.QTableWidgetItem(str(value)))
        table.setCurrentCell(row_index, 0)
        table.editItem(table.item(row_index, 0))

    @staticmethod
    def _remove_selected_table_row(table: QtWidgets.QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    @staticmethod
    def _line(placeholder: str) -> QtWidgets.QLineEdit:
        value = QtWidgets.QLineEdit()
        value.setPlaceholderText(placeholder)
        return value

    @staticmethod
    def _resref_line(placeholder: str) -> QtWidgets.QLineEdit:
        value = DialogueEditorPage._line(placeholder)
        value.setMaxLength(16)
        return value

    def _audio_reference_controls(self, field: str, editor: QtWidgets.QLineEdit) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget(self)
        container.setObjectName(f"scriptingStudioDialogue{field.title()}AudioControls")
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(max(2, self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutHorizontalSpacing)))
        browse = QtWidgets.QPushButton("Browse…", container)
        browse.setObjectName(f"scriptingStudioDialogue{field.title()}AudioBrowseButton")
        browse.setToolTip("Choose a local audio file and fill this KOTOR ResRef from its filename.")
        play = QtWidgets.QPushButton("Play", container)
        play.setObjectName(f"scriptingStudioDialogue{field.title()}AudioPlayButton")
        play.setToolTip("Preview this target-game WAV resource through GhostStudio.")
        stop = QtWidgets.QPushButton("Stop", container)
        stop.setObjectName(f"scriptingStudioDialogue{field.title()}AudioStopButton")
        stop.setToolTip("Stop the current dialogue audio preview.")
        stop.setEnabled(False)
        layout.addWidget(editor, 1)
        layout.addWidget(browse)
        layout.addWidget(play)
        layout.addWidget(stop)

        status = QtWidgets.QWidget(self)
        status.setObjectName(f"scriptingStudioDialogue{field.title()}AudioStatus")
        status_layout = QtWidgets.QHBoxLayout(status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        label = QtWidgets.QLabel("Not previewing", status)
        label.setObjectName(f"scriptingStudioDialogue{field.title()}AudioStatusLabel")
        progress = QtWidgets.QProgressBar(status)
        progress.setObjectName(f"scriptingStudioDialogue{field.title()}AudioProgress")
        progress.setRange(0, 1000)
        progress.setValue(0)
        progress.setTextVisible(False)
        status_layout.addWidget(label, 1)
        status_layout.addWidget(progress, 1)

        setattr(self, f"{field}_audio_browse_button", browse)
        setattr(self, f"{field}_audio_play_button", play)
        setattr(self, f"{field}_audio_stop_button", stop)
        setattr(self, f"{field}_audio_status_label", label)
        setattr(self, f"{field}_audio_progress", progress)
        setattr(self, f"{field}_audio_status", status)

        browse.clicked.connect(lambda: self.audioBrowseRequested.emit(self.document_id, field))
        play.clicked.connect(
            lambda: self.audioPreviewRequested.emit(self.document_id, field, editor.text().strip())
        )
        stop.clicked.connect(lambda: self.audioStopRequested.emit(self.document_id))
        editor.textChanged.connect(
            lambda text: play.setEnabled(bool(self._selected_row) and bool(str(text).strip()))
        )
        return container

    def _participant_reference_controls(self, field: str, editor: QtWidgets.QLineEdit) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget(self)
        container.setObjectName(f"scriptingStudioDialogue{field.title()}Controls")
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(max(2, self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutHorizontalSpacing)))
        browse = QtWidgets.QPushButton("Browse NPCs…", container)
        browse.setObjectName(f"scriptingStudioDialogue{field.title()}BrowseButton")
        browse.setToolTip(
            "Choose a placed/module creature tag, UTC blueprint Tag, or participant already used in this conversation."
        )
        browse.clicked.connect(
            lambda: self.participantBrowseRequested.emit(self.document_id, field, editor.text().strip())
        )
        layout.addWidget(editor, 1)
        layout.addWidget(browse)
        return container

    @staticmethod
    def _node_matches_filter(row: Mapping[str, Any], query: str, kind: str) -> bool:
        if kind not in {"", "all"} and str(row.get("kind") or "").casefold() != kind:
            return False
        if not query:
            return True
        haystack = " ".join(
            str(row.get(key) or "")
            for key in (
                "text", "speaker", "listener", "active1", "active2", "script1", "script2",
                "node_comment", "link_comment", "quest", "sound", "voice",
            )
        ).casefold()
        return query in haystack

    def _apply_node_filter(self) -> None:
        query = self.node_filter_edit.text().strip().casefold()
        kind = str(self.node_kind_filter.currentData() or "all").casefold()
        visible_count = 0

        def update_item(item: QtWidgets.QTreeWidgetItem) -> bool:
            nonlocal visible_count
            child_matches = [update_item(item.child(index)) for index in range(item.childCount())]
            child_match = any(child_matches)
            row = dict(item.data(0, DOCUMENT_ROLE) or {})
            own_match = self._node_matches_filter(row, query, kind)
            visible = own_match or child_match
            item.setHidden(not visible)
            if own_match:
                visible_count += 1
            if child_match and (query or kind != "all"):
                item.setExpanded(True)
            return visible

        for index in range(self.tree.topLevelItemCount()):
            update_item(self.tree.topLevelItem(index))
        total = len(self._rows_by_link)
        self.node_filter_result_label.setText(
            "" if not query and kind == "all" else f"{visible_count} of {total}"
        )
        current = self.tree.currentItem()
        if current is not None and not current.isHidden():
            return
        first_visible: QtWidgets.QTreeWidgetItem | None = None
        pending = [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        while pending and first_visible is None:
            item = pending.pop(0)
            if not item.isHidden():
                first_visible = item
                break
            pending[0:0] = [item.child(index) for index in range(item.childCount())]
        if first_visible is not None:
            self.tree.setCurrentItem(first_visible)
            return
        self._selection_syncing = True
        try:
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
            self._load_selected_row({})
            self.graph.clear_selection()
        finally:
            self._selection_syncing = False

    def set_graph(self, rows: list[dict[str, Any]]) -> None:
        selected_link = str(self._selected_row.get("link_id") or "")
        normalized_rows = [dict(row) for row in rows]
        self._rows_by_link = {
            str(row.get("link_id") or ""): row
            for row in normalized_rows
            if str(row.get("link_id") or "")
        }
        self._rows_by_node = {}
        for row in normalized_rows:
            node_id = str(row.get("node_id") or "")
            if node_id:
                self._rows_by_node.setdefault(node_id, []).append(row)
        self.tree.clear()
        items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        pending = list(normalized_rows)
        while pending:
            progressed = False
            for row in list(pending):
                parent_id = str(row.get("parent_link_id") or "")
                if parent_id and parent_id not in items:
                    continue
                label = str(row.get("text") or "<empty line>").replace("\n", " ")
                prefix = "NPC" if row.get("kind") == "entry" else "PLAYER"
                condition = " / ".join(value for value in (row.get("active1"), row.get("active2")) if value)
                item = QtWidgets.QTreeWidgetItem([f"{prefix}: {label}", str(row.get("speaker") or ""), condition])
                item.setData(0, DOCUMENT_ROLE, row)
                if parent_id:
                    items[parent_id].addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                items[str(row.get("link_id") or "")] = item
                pending.remove(row)
                progressed = True
            if not progressed:
                for row in pending:
                    item = QtWidgets.QTreeWidgetItem(["Broken/cyclic link", "", ""])
                    item.setData(0, DOCUMENT_ROLE, row)
                    self.tree.addTopLevelItem(item)
                    items[str(row.get("link_id") or "")] = item
                break
        self._tree_items = items
        self.tree.expandToDepth(2)
        self.graph.set_graph(self._graph_snapshot(normalized_rows))
        if selected_link and selected_link in items:
            self.tree.setCurrentItem(items[selected_link])
        elif self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self._load_selected_row({})
            self.graph.clear_selection()
        self._apply_node_filter()

    @staticmethod
    def _graph_snapshot(rows: list[dict[str, Any]]) -> DialogueGraphSnapshot:
        by_link = {str(row.get("link_id") or ""): row for row in rows}
        nodes: dict[str, DialogueGraphNode] = {}
        links: list[DialogueGraphLink] = []
        for row in rows:
            node_id = str(row.get("node_id") or "")
            kind = str(row.get("kind") or "reply")
            if node_id and node_id not in nodes:
                speaker = str(row.get("speaker") or "")
                title = speaker or ("Player Reply" if kind == "reply" else "NPC Entry")
                nodes[node_id] = DialogueGraphNode(
                    node_id=node_id,
                    kind=kind,
                    title=title,
                    preview=str(row.get("text") or ""),
                    speaker=speaker,
                    listener=str(row.get("listener") or ""),
                    depth=int(row.get("depth") or 0),
                    list_index=int(row.get("list_index", -1) if row.get("list_index") is not None else -1),
                )
            parent_link_id = str(row.get("parent_link_id") or "")
            parent_row = by_link.get(parent_link_id, {})
            first = str(row.get("active1") or "")
            second = str(row.get("active2") or "")
            if first and bool(row.get("active1_not")):
                first = f"NOT {first}"
            if second and bool(row.get("active2_not")):
                second = f"NOT {second}"
            if first and second:
                condition = f"{first} {'OR' if bool(row.get('logic')) else 'AND'} {second}"
            else:
                condition = first or second
            links.append(
                DialogueGraphLink(
                    link_id=str(row.get("link_id") or ""),
                    source_node_id=str(parent_row.get("node_id") or "") or None,
                    target_node_id=node_id or None,
                    starter=not parent_link_id,
                    condition=condition,
                    comment=str(row.get("link_comment") or ""),
                )
            )
        return DialogueGraphSnapshot(tuple(nodes.values()), tuple(links))

    def _selection_changed(self, current: QtWidgets.QTreeWidgetItem | None, _previous: object = None) -> None:
        row = dict(current.data(0, DOCUMENT_ROLE) or {}) if current is not None else {}
        self._load_selected_row(row)
        if row and not self._selection_syncing:
            self._selection_syncing = True
            try:
                self.graph.select_link(str(row.get("link_id") or ""))
            finally:
                self._selection_syncing = False

    def _graph_node_selected(self, node_id: str) -> None:
        if self._selection_syncing:
            return
        candidates = self._rows_by_node.get(str(node_id), [])
        current_link = str(self._selected_row.get("link_id") or "")
        row = next((value for value in candidates if str(value.get("link_id") or "") == current_link), None)
        if row is None and candidates:
            row = candidates[0]
        if row is not None:
            self._select_graph_row(row)

    def _graph_link_selected(self, link_id: str) -> None:
        if not self._selection_syncing:
            row = self._rows_by_link.get(str(link_id))
            if row is not None:
                self._select_graph_row(row)

    def _select_graph_row(self, row: dict[str, Any]) -> None:
        item = self._tree_items.get(str(row.get("link_id") or ""))
        if item is None or item.isHidden():
            current_link = str(self._selected_row.get("link_id") or "")
            self._selection_syncing = True
            try:
                if not current_link or not self.graph.select_link(current_link):
                    self.graph.clear_selection()
            finally:
                self._selection_syncing = False
            return
        self._selection_syncing = True
        try:
            self.tree.setCurrentItem(item)
            self._load_selected_row(row)
        finally:
            self._selection_syncing = False

    def _load_selected_row(self, row: dict[str, Any]) -> None:
        previous_link = str(self._selected_row.get("link_id") or "")
        next_link = str(row.get("link_id") or "")
        selection_changed = previous_link != next_link
        if previous_link and selection_changed:
            self.audioStopRequested.emit(self.document_id)
        self._selected_row = row
        self.kind_label.setText(
            f"{str(row.get('kind') or 'node').title()}  •  {row.get('node_id') or 'unresolved'}"
            if row else "No node selected"
        )
        self.text_edit.setPlainText(str(row.get("text") or ""))
        self.text_stringref_spin.setValue(int(row.get("text_stringref", -1) if row else -1))
        self._set_table_rows(self.text_substrings_table, tuple(row.get("text_substrings") or ()))
        self.speaker_edit.setText(str(row.get("speaker") or ""))
        self.listener_edit.setText(str(row.get("listener") or ""))
        self.node_comment_edit.setText(str(row.get("node_comment") or ""))
        self.delay_spin.setValue(int(row.get("delay", -1) if row else -1))
        self.wait_flags_spin.setValue(int(row.get("wait_flags") or 0))
        self.script1_edit.setText(str(row.get("script1") or ""))
        self.script2_edit.setText(str(row.get("script2") or ""))
        self.script1_params.set_values(row.get("script1_params"))
        self.script2_params.set_values(row.get("script2_params"))
        self.condition1_params.set_values(row.get("active1_params"))
        self.condition2_params.set_values(row.get("active2_params"))
        self.sound_edit.setText(str(row.get("sound") or ""))
        self.voice_edit.setText(str(row.get("voice") or ""))
        self.sound_exists_check.setChecked(bool(row.get("sound_exists")))
        self.quest_edit.setText(str(row.get("quest") or ""))
        self.quest_entry_spin.setValue(int(row.get("quest_entry") or 0))
        self.plot_index_spin.setValue(int(row.get("plot_index") or 0))
        self.plot_xp_spin.setValue(float(row.get("plot_xp_percentage") or 0.0))
        self.record_vo_check.setChecked(bool(row.get("record_vo")))
        self.record_no_vo_override_check.setChecked(bool(row.get("record_no_vo_override")))
        self.vo_text_changed_check.setChecked(bool(row.get("vo_text_changed")))
        self.emotion_spin.setValue(int(row.get("emotion_id") or 0))
        self.facial_spin.setValue(int(row.get("facial_id") or 0))
        self.alien_race_node_spin.setValue(int(row.get("alien_race_node") or 0))
        self.condition1_edit.setText(str(row.get("active1") or ""))
        self.condition2_edit.setText(str(row.get("active2") or ""))
        self.condition1_not.setChecked(bool(row.get("active1_not")))
        self.condition2_not.setChecked(bool(row.get("active2_not")))
        self.logic_or.setChecked(bool(row.get("logic")))
        self.is_child_check.setChecked(bool(row.get("is_child")))
        self.display_inactive_check.setChecked(bool(row.get("display_inactive")))
        self.link_comment_edit.setText(str(row.get("link_comment") or ""))
        self.camera_angle_spin.setValue(int(row.get("camera_angle") or 0))
        self.camera_anim_edit.set_value(row.get("camera_anim"))
        self.camera_id_edit.set_value(row.get("camera_id"))
        self.camera_fov_edit.set_value(row.get("camera_fov"))
        self.camera_height_edit.set_value(row.get("camera_height"))
        self.camera_effect_edit.set_value(row.get("camera_effect"))
        self.target_height_edit.set_value(row.get("target_height"))
        self.fade_type_spin.setValue(int(row.get("fade_type") or 0))
        self.fade_color_edit.set_value(row.get("fade_color"))
        self.fade_delay_edit.set_value(row.get("fade_delay"))
        self.fade_length_edit.set_value(row.get("fade_length"))
        self.node_id_spin.setValue(int(row.get("node_id_tsl") or 0))
        self.post_proc_node_spin.setValue(int(row.get("post_proc_node") or 0))
        self.unskippable_check.setChecked(bool(row.get("unskippable")))
        self._set_table_rows(
            self.animations_table,
            tuple(
                (value.get("participant", ""), value.get("animation_id", 0))
                if isinstance(value, Mapping)
                else value
                for value in tuple(row.get("animations") or ())
            ),
        )
        has_row = bool(row)
        topology_enabled = not bool(getattr(self, "_topology_locked", False))
        self.add_starter_button.setEnabled(topology_enabled)
        self.add_child_button.setEnabled(has_row and topology_enabled)
        self.link_existing_button.setEnabled(has_row and topology_enabled)
        self.start_existing_button.setEnabled(bool(self._rows_by_node) and topology_enabled)
        self.retarget_button.setEnabled(has_row and topology_enabled)
        self.remove_button.setEnabled(has_row and topology_enabled)
        self.delete_node_button.setEnabled(has_row and topology_enabled)
        self.apply_button.setEnabled(has_row)
        for field, editor in (("sound", self.sound_edit), ("voice", self.voice_edit)):
            getattr(self, f"{field}_audio_browse_button").setEnabled(has_row)
            if selection_changed or self._audio_active_field != field:
                getattr(self, f"{field}_audio_play_button").setEnabled(has_row and bool(editor.text().strip()))
            if selection_changed:
                getattr(self, f"{field}_audio_stop_button").setEnabled(False)
                getattr(self, f"{field}_audio_status_label").setText("Not previewing")
                getattr(self, f"{field}_audio_progress").setValue(0)
        if selection_changed:
            self._audio_active_field = None

    def set_audio_reference(self, field: str, resref: str, *, message: str = "") -> None:
        key = "voice" if str(field).strip().lower() in {"voice", "vo"} else "sound"
        editor = self.voice_edit if key == "voice" else self.sound_edit
        editor.setText(str(resref or "").strip().lower()[:16])
        getattr(self, f"{key}_audio_status_label").setText(
            str(message or "Local file linked for preview; apply node fields to keep the ResRef.")
        )

    def set_audio_preview_state(
        self,
        field: str,
        state: str,
        *,
        message: str = "",
        position_ms: int = 0,
        duration_ms: int = 0,
    ) -> None:
        key = "voice" if str(field).strip().lower() in {"voice", "vo"} else "sound"
        normalized = str(state or "stopped").strip().lower()
        playing = normalized in {"loading", "playing"}
        self._audio_active_field = key if playing else None
        getattr(self, f"{key}_audio_play_button").setEnabled(
            not playing and bool((self.voice_edit if key == "voice" else self.sound_edit).text().strip())
        )
        getattr(self, f"{key}_audio_stop_button").setEnabled(playing)
        label = getattr(self, f"{key}_audio_status_label")
        label.setText(str(message or normalized.title() or "Not previewing"))
        progress = getattr(self, f"{key}_audio_progress")
        if duration_ms > 0:
            progress.setValue(max(0, min(1000, int(round((position_ms / duration_ms) * 1000.0)))))
        elif not playing:
            progress.setValue(0)

    def _apply_fields(self) -> None:
        row = self._selected_row
        if not row:
            return
        if self._audio_active_field is not None:
            self.audioStopRequested.emit(self.document_id)
        values: dict[str, Any] = {
            "speaker": self.speaker_edit.text().strip(),
            "listener": self.listener_edit.text().strip(),
            "node_comment": self.node_comment_edit.text(),
            "delay": self.delay_spin.value(),
            "wait_flags": self.wait_flags_spin.value(),
            "script1": self.script1_edit.text().strip(),
            "script2": self.script2_edit.text().strip(),
            "script1_params": self.script1_params.values(),
            "script2_params": self.script2_params.values(),
            "sound": self.sound_edit.text().strip(),
            "sound_exists": int(self.sound_exists_check.isChecked()),
            "voice": self.voice_edit.text().strip(),
            "quest": self.quest_edit.text().strip(),
            "quest_entry": self.quest_entry_spin.value(),
            "plot_index": self.plot_index_spin.value(),
            "plot_xp_percentage": self.plot_xp_spin.value(),
            "record_vo": self.record_vo_check.isChecked(),
            "record_no_vo_override": self.record_no_vo_override_check.isChecked(),
            "vo_text_changed": self.vo_text_changed_check.isChecked(),
            "emotion_id": self.emotion_spin.value(),
            "facial_id": self.facial_spin.value(),
            "alien_race_node": self.alien_race_node_spin.value(),
            "active1": self.condition1_edit.text().strip(),
            "active2": self.condition2_edit.text().strip(),
            "active1_not": self.condition1_not.isChecked(),
            "active2_not": self.condition2_not.isChecked(),
            "logic": self.logic_or.isChecked(),
            "active1_params": self.condition1_params.values(),
            "active2_params": self.condition2_params.values(),
            "is_child": self.is_child_check.isChecked(),
            "display_inactive": self.display_inactive_check.isChecked(),
            "link_comment": self.link_comment_edit.text(),
            "camera_angle": self.camera_angle_spin.value(),
            "camera_anim": self.camera_anim_edit.value_or_none(),
            "camera_id": self.camera_id_edit.value_or_none(),
            "camera_fov": self.camera_fov_edit.value_or_none(),
            "camera_height": self.camera_height_edit.value_or_none(),
            "camera_effect": self.camera_effect_edit.value_or_none(),
            "target_height": self.target_height_edit.value_or_none(),
            "fade_type": self.fade_type_spin.value(),
            "fade_color": self.fade_color_edit.value_or_none(),
            "fade_delay": self.fade_delay_edit.value_or_none(),
            "fade_length": self.fade_length_edit.value_or_none(),
            "node_id": self.node_id_spin.value(),
            "post_proc_node": self.post_proc_node_spin.value(),
            "unskippable": self.unskippable_check.isChecked(),
            "animations": self._mapping_table_values(self.animations_table, "participant", "animation_id", integer_column=1),
        }
        original_text = str(row.get("text") or "")
        original_ref = int(row.get("text_stringref", -1))
        original_substrings = tuple((int(key), str(value)) for key, value in tuple(row.get("text_substrings") or ()))
        edited_text = self.text_edit.toPlainText()
        edited_ref = self.text_stringref_spin.value()
        edited_substrings = tuple((int(key), str(value)) for key, value in self._table_values(self.text_substrings_table))
        text_changed = edited_text != original_text
        localization_changed = edited_ref != original_ref or edited_substrings != original_substrings
        if text_changed and not localization_changed:
            values["text"] = edited_text
        elif localization_changed:
            substring_map = dict(edited_substrings)
            if text_changed:
                substring_map[0] = edited_text
                edited_ref = -1
            values["text_stringref"] = edited_ref
            values["text_substrings"] = tuple(sorted(substring_map.items()))
        self.fieldsApplied.emit(
            self.document_id,
            str(row.get("node_id") or ""),
            str(row.get("link_id") or ""),
            values,
        )

    def set_settings(self, row: Mapping[str, Any]) -> None:
        self._settings_row = dict(row)
        self.on_end_edit.setText(str(row.get("on_end") or ""))
        self.on_abort_edit.setText(str(row.get("on_abort") or ""))
        self.skippable_check.setChecked(bool(row.get("skippable")))
        self.delay_entry_spin.setValue(int(row.get("delay_entry") or 0))
        self.delay_reply_spin.setValue(int(row.get("delay_reply") or 0))
        self.ambient_track_edit.setText(str(row.get("ambient_track") or ""))
        self.animated_cut_check.setChecked(bool(row.get("animated_cut")))
        self.camera_model_edit.setText(str(row.get("camera_model") or ""))
        self._set_combo_data(self.conversation_type_combo, int(row.get("conversation_type") or 0))
        self._set_combo_data(self.computer_type_combo, int(row.get("computer_type") or 0))
        self.old_hit_check.setChecked(bool(row.get("old_hit_check")))
        self.unequip_items_check.setChecked(bool(row.get("unequip_items")))
        self.unequip_hands_check.setChecked(bool(row.get("unequip_hands")))
        self.word_count_spin.setValue(int(row.get("word_count") or 0))
        self.vo_id_edit.setText(str(row.get("vo_id") or ""))
        self.root_comment_edit.setText(str(row.get("comment") or ""))
        self.alien_race_owner_spin.setValue(int(row.get("alien_race_owner") or 0))
        self.post_proc_owner_spin.setValue(int(row.get("post_proc_owner") or 0))
        self.record_no_vo_spin.setValue(int(row.get("record_no_vo") or 0))
        self.next_node_id_spin.setValue(int(row.get("next_node_id") or 0))
        self._set_table_rows(
            self.stunts_table,
            tuple(
                (value.get("participant", ""), value.get("stunt_model", ""))
                if isinstance(value, Mapping)
                else value
                for value in tuple(row.get("stunts") or ())
            ),
        )

    def _apply_settings(self) -> None:
        values = {
            "on_end": self.on_end_edit.text().strip(),
            "on_abort": self.on_abort_edit.text().strip(),
            "skippable": self.skippable_check.isChecked(),
            "delay_entry": self.delay_entry_spin.value(),
            "delay_reply": self.delay_reply_spin.value(),
            "ambient_track": self.ambient_track_edit.text().strip(),
            "animated_cut": int(self.animated_cut_check.isChecked()),
            "camera_model": self.camera_model_edit.text().strip(),
            "conversation_type": int(self.conversation_type_combo.currentData() or 0),
            "computer_type": int(self.computer_type_combo.currentData() or 0),
            "old_hit_check": self.old_hit_check.isChecked(),
            "unequip_items": self.unequip_items_check.isChecked(),
            "unequip_hands": self.unequip_hands_check.isChecked(),
            "word_count": self.word_count_spin.value(),
            "vo_id": self.vo_id_edit.text(),
            "comment": self.root_comment_edit.text(),
            "alien_race_owner": self.alien_race_owner_spin.value(),
            "post_proc_owner": self.post_proc_owner_spin.value(),
            "record_no_vo": self.record_no_vo_spin.value(),
            "next_node_id": self.next_node_id_spin.value(),
            "stunts": self._mapping_table_values(self.stunts_table, "participant", "stunt_model"),
        }
        self.settingsApplied.emit(self.document_id, values)

    @staticmethod
    def _set_combo_data(combo: QtWidgets.QComboBox, value: int) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_table_rows(table: QtWidgets.QTableWidget, rows: object) -> None:
        table.setRowCount(0)
        for values in tuple(rows or ()):
            row_index = table.rowCount()
            table.insertRow(row_index)
            for column, value in enumerate(tuple(values or ())):
                table.setItem(row_index, column, QtWidgets.QTableWidgetItem(str(value)))

    @staticmethod
    def _table_values(table: QtWidgets.QTableWidget) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(str(table.item(row, column).text() if table.item(row, column) is not None else "") for column in range(table.columnCount()))
            for row in range(table.rowCount())
        )

    @classmethod
    def _mapping_table_values(
        cls,
        table: QtWidgets.QTableWidget,
        first_key: str,
        second_key: str,
        *,
        integer_column: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        for row in cls._table_values(table):
            second: Any = row[1]
            if integer_column == 1:
                second = int(second or 0)
            result.append({first_key: row[0], second_key: second})
        return tuple(result)

    def _request_add_child(self) -> None:
        link_id = str(self._selected_row.get("link_id") or "")
        if link_id:
            self.addChildRequested.emit(self.document_id, link_id)

    def set_topology_policy(self, requires_editable_copy: bool) -> None:
        self._topology_locked = bool(requires_editable_copy)
        self.topology_lock_label.setVisible(self._topology_locked)
        self.make_editable_copy_button.setVisible(self._topology_locked)
        self.make_editable_copy_button.setEnabled(self._topology_locked)
        self._load_selected_row(dict(self._selected_row))

    def select_link(self, link_id: str) -> bool:
        row = self._rows_by_link.get(str(link_id))
        if row is None:
            return False
        self._select_graph_row(row)
        return True

    def _target_rows(self, kind: str, *, exclude_node_id: str = "") -> list[dict[str, Any]]:
        target_kind = str(kind or "").strip().lower()
        rows: list[dict[str, Any]] = []
        for node_id, appearances in self._rows_by_node.items():
            if node_id == str(exclude_node_id or "") or not appearances:
                continue
            row = appearances[0]
            if str(row.get("kind") or "").lower() != target_kind:
                continue
            rows.append({
                "node_id": node_id,
                "kind": target_kind,
                "text": str(row.get("text") or ""),
                "speaker": str(row.get("speaker") or ""),
                "listener": str(row.get("listener") or ""),
                "incoming_links": len(appearances),
            })
        return sorted(rows, key=lambda row: (row["speaker"].casefold(), row["text"].casefold(), row["node_id"]))

    def _choose_target(self, title: str, kind: str, *, exclude_node_id: str = "") -> str:
        picker = _DialogueTargetPicker(
            self._target_rows(kind, exclude_node_id=exclude_node_id),
            title=title,
            parent=self,
        )
        if picker.exec() != QtWidgets.QDialog.Accepted:
            return ""
        return picker.selected_node_id

    def _request_link_existing(self) -> None:
        row = self._selected_row
        source_link_id = str(row.get("link_id") or "")
        source_kind = str(row.get("kind") or "")
        if not source_link_id or source_kind not in {"entry", "reply"}:
            return
        target_kind = "reply" if source_kind == "entry" else "entry"
        target_id = self._choose_target(
            f"Link Existing {target_kind.title()}",
            target_kind,
        )
        if target_id:
            self.linkExistingRequested.emit(self.document_id, source_link_id, target_id)

    def _request_start_existing(self) -> None:
        target_id = self._choose_target("Start at Existing NPC Entry", "entry")
        if target_id:
            self.startExistingRequested.emit(self.document_id, target_id)

    def _request_retarget(self) -> None:
        row = self._selected_row
        link_id = str(row.get("link_id") or "")
        target_kind = str(row.get("kind") or "")
        if not link_id or target_kind not in {"entry", "reply"}:
            return
        target_id = self._choose_target(
            f"Retarget Link to Existing {target_kind.title()}",
            target_kind,
            exclude_node_id=str(row.get("node_id") or ""),
        )
        if target_id:
            self.retargetLinkRequested.emit(self.document_id, link_id, target_id)

    def _request_remove(self) -> None:
        link_id = str(self._selected_row.get("link_id") or "")
        if link_id:
            self.removeLinkRequested.emit(self.document_id, link_id)

    def _request_delete_node(self) -> None:
        node_id = str(self._selected_row.get("node_id") or "")
        if not node_id:
            return
        text = str(self._selected_row.get("text") or "<empty line>").replace("\n", " ")
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete Dialogue Node",
            f"Delete this node and every incoming link to it?\n\n{text[:160]}\n\n"
            "Shared branches that point here will also be removed. This does not delete surviving nodes.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.deleteNodeRequested.emit(self.document_id, node_id)


class _DialogueTargetPicker(QtWidgets.QDialog):
    """Searchable existing-node chooser used by topology actions."""

    def __init__(
        self,
        rows: object,
        *,
        title: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioDialogueTargetPicker")
        self.setWindowTitle(str(title or "Choose Existing Dialogue Node"))
        self.setModal(True)
        self.resize(720, 440)
        layout = QtWidgets.QVBoxLayout(self)
        guidance = QtWidgets.QLabel(
            "Choose an existing node. GhostStudio reuses that exact node object, preserving its fields and "
            "allowing shared branches or alternating cycles.",
            self,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioDialogueTargetSearchEdit")
        self.search_edit.setPlaceholderText("Search text, speaker, listener, or node ID…")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        self.tree = QtWidgets.QTreeWidget(self)
        self.tree.setObjectName("scriptingStudioDialogueTargetTree")
        self.tree.setHeaderLabels(["Existing node", "Speaker", "Listener", "Incoming"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.tree.header().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        for raw in tuple(rows or ()):
            row = dict(raw) if isinstance(raw, Mapping) else {}
            node_id = str(row.get("node_id") or "")
            if not node_id:
                continue
            kind = "NPC" if str(row.get("kind") or "") == "entry" else "PLAYER"
            text = str(row.get("text") or "<empty line>").replace("\n", " ")
            item = QtWidgets.QTreeWidgetItem([
                f"{kind}: {text}",
                str(row.get("speaker") or ""),
                str(row.get("listener") or ""),
                str(int(row.get("incoming_links") or 0)),
            ])
            item.setData(0, DOCUMENT_ROLE, row)
            item.setToolTip(0, node_id)
            self.tree.addTopLevelItem(item)
        layout.addWidget(self.tree, 1)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Use Existing Node")
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self._accept_selected)
        self.buttons.rejected.connect(self.reject)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self._accept_selected())
        self.tree.currentItemChanged.connect(lambda _current, _previous: self._update_acceptance())
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._update_acceptance()

    @property
    def selected_node_id(self) -> str:
        current = self.tree.currentItem()
        row = dict(current.data(0, DOCUMENT_ROLE) or {}) if current is not None else {}
        return str(row.get("node_id") or "")

    def _update_acceptance(self) -> None:
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(bool(self.selected_node_id))

    def _apply_filter(self, value: str) -> None:
        query = str(value or "").strip().casefold()
        first_visible: QtWidgets.QTreeWidgetItem | None = None
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            row = dict(item.data(0, DOCUMENT_ROLE) or {})
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("text", "speaker", "listener", "node_id", "kind")
            ).casefold()
            visible = not query or query in haystack
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item
        if first_visible is None:
            self.tree.setCurrentItem(None)
        elif self.tree.currentItem() is None or self.tree.currentItem().isHidden():
            self.tree.setCurrentItem(first_visible)
        self._update_acceptance()

    def _accept_selected(self) -> None:
        if self.selected_node_id:
            self.accept()


class _ResourceFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._query = ""
        self._kind = "all"
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def set_filters(self, query: str, kind: str) -> None:
        self.beginFilterChange()
        self._query = str(query or "").strip().lower()
        self._kind = str(kind or "all").strip().lower()
        self.endFilterChange()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        index = self.sourceModel().index(source_row, 0, source_parent)
        row = dict(index.data(RESOURCE_ROW_ROLE) or {})
        if self._kind not in {"", "all"} and str(row.get("kind") or "").lower() != self._kind:
            return False
        haystack = " ".join(str(row.get(key) or "") for key in ("resref", "restype", "origin", "status")).lower()
        return not self._query or self._query in haystack


class _DialogueParticipantPicker(QtWidgets.QDialog):
    """Searchable, palette-driven chooser for dialogue participant tags."""

    def __init__(
        self,
        rows: object,
        *,
        current: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioDialogueParticipantPicker")
        self.setWindowTitle("Choose Dialogue Participant")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)
        guidance = QtWidgets.QLabel(
            "Choose a creature tag placed in the current module, read from a UTC blueprint, or already used "
            "in this dialogue. Appearance data decorates these real tags but does not invent participants. "
            "You can still type a custom creature tag in the inspector.",
            self,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioDialogueParticipantSearch")
        self.search_edit.setPlaceholderText("Filter tag, appearance ID, model, race, or head…")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        self.tree = QtWidgets.QTreeWidget(self)
        self.tree.setObjectName("scriptingStudioDialogueParticipantTree")
        self.tree.setHeaderLabels(["Participant Tag", "Source", "Appearance ID", "Body Model", "Head", "Race"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in range(1, 6):
            self.tree.header().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.tree, 1)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        self._accept_button = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        layout.addWidget(buttons)
        current_key = str(current or "").casefold()
        for value in tuple(rows or ()):
            if not isinstance(value, Mapping):
                continue
            row = dict(value)
            tag = str(row.get("tag") or "").strip()
            if not tag:
                continue
            item = QtWidgets.QTreeWidgetItem(
                [
                    tag,
                    str(row.get("source") or ""),
                    str(row.get("appearance_id") or ""),
                    str(row.get("body_model") or ""),
                    str(row.get("head") or ""),
                    str(row.get("race") or ""),
                ]
            )
            item.setData(0, DOCUMENT_ROLE, row)
            self.tree.addTopLevelItem(item)
            if current_key and tag.casefold() == current_key:
                self.tree.setCurrentItem(item)
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.search_edit.textChanged.connect(self._apply_filter)
        self.tree.currentItemChanged.connect(lambda _current, _previous: self._update_acceptance())
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self._accept_selected())
        self._update_acceptance()

    @property
    def selected_tag(self) -> str:
        item = self.tree.currentItem()
        return str(item.text(0) if item is not None and not item.isHidden() else "").strip()

    def _update_acceptance(self) -> None:
        self._accept_button.setEnabled(bool(self.selected_tag))

    def _apply_filter(self, value: str) -> None:
        query = str(value or "").strip().casefold()
        first_visible: QtWidgets.QTreeWidgetItem | None = None
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            haystack = " ".join(item.text(column) for column in range(item.columnCount())).casefold()
            visible = not query or query in haystack
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item
        if first_visible is not None and (self.tree.currentItem() is None or self.tree.currentItem().isHidden()):
            self.tree.setCurrentItem(first_visible)
        elif first_visible is None:
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
        self._update_acceptance()

    def _accept_selected(self) -> None:
        if self.selected_tag:
            self.accept()


class QtScriptingDialogueStudioWindow(QtWidgets.QMainWindow):
    """Full-size GhostStudio workbench for the complete narrative toolchain."""

    newScriptRequested = QtCore.Signal(str)
    newDialogueRequested = QtCore.Signal(str)
    openFileRequested = QtCore.Signal(str)
    saveRequested = QtCore.Signal(str, bool)
    saveAllRequested = QtCore.Signal()
    compileRequested = QtCore.Signal(str)
    validateRequested = QtCore.Signal(str)
    buildRequested = QtCore.Signal(str)
    refreshResourcesRequested = QtCore.Signal(str)
    resourceActivated = QtCore.Signal(object)
    targetGameChanged = QtCore.Signal(str)
    documentClosed = QtCore.Signal(str)
    referenceSearchRequested = QtCore.Signal(str, str, str, str)
    referenceInsertRequested = QtCore.Signal(str)
    dialogueAudioPreviewRequested = QtCore.Signal(str, str, str)
    dialogueAudioBrowseRequested = QtCore.Signal(str, str)
    dialogueAudioStopRequested = QtCore.Signal(str)
    dialogueParticipantBrowseRequested = QtCore.Signal(str, str, str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("GhostStudio — Scripting Suite")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.setWindowModality(QtCore.Qt.NonModal)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(1120, 720)
        self.setObjectName("scriptingDialogueStudioWindow")
        self.setProperty("ghostLayoutId", "scriptingDialogueStudio")
        if parent is not None:
            studio_icon = self._icon("scripting_dialogue_studio", QtWidgets.QStyle.SP_FileDialogDetailedView)
            if not studio_icon.isNull():
                self.setWindowIcon(studio_icon)
        self._document_rows: dict[str, dict[str, Any]] = {}
        self._document_pages: dict[str, QtWidgets.QWidget] = {}
        self._reference_symbols: set[str] = set(_COMMON_NWSCRIPT_SYMBOLS)
        self._reference_definitions: tuple[dict[str, Any], ...] = ()
        self._save_all_handler: Callable[[], bool] | None = None
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._update_action_state()

        theme_manager = getattr(parent, "theme_manager", None)
        layout_manager = getattr(parent, "layout_manager", None)
        if theme_manager is not None:
            theme_manager.register_theme_aware_widget(self)
            self.apply_ghost_theme(theme_manager.current_theme or theme_manager.get_theme())
        if layout_manager is not None:
            layout_manager.layoutChanged.connect(self.apply_ghost_layout)
            self.apply_ghost_layout(layout_manager.current_layout or layout_manager.get_layout())
        else:
            self.resize(1450, 860)

    def _icon(self, name: str, fallback: QtWidgets.QStyle.StandardPixmap) -> QtGui.QIcon:
        provider = getattr(self.parent(), "_icon", None)
        if callable(provider):
            icon = provider(name, 18)
            if icon is not None and not icon.isNull():
                return icon
        return QtWidgets.QApplication.style().standardIcon(fallback)

    def _build_actions(self) -> None:
        self.new_script_action = QtGui.QAction(self._icon("new_scene", QtWidgets.QStyle.SP_FileIcon), "New Script", self)
        self.new_script_action.setStatusTip("Create an editable KOTOR NWScript source file.")
        self.new_script_action.setShortcut("Ctrl+N")
        self.new_script_action.triggered.connect(lambda: self.newScriptRequested.emit(self.target_game()))
        self.new_dialogue_action = QtGui.QAction(self._icon("dialogue", QtWidgets.QStyle.SP_FileDialogDetailedView), "New Dialogue", self)
        self.new_dialogue_action.setStatusTip("Create a branching KOTOR dialogue resource.")
        self.new_dialogue_action.setShortcut("Ctrl+Shift+N")
        self.new_dialogue_action.triggered.connect(lambda: self.newDialogueRequested.emit(self.target_game()))
        self.open_action = QtGui.QAction(self._icon("open", QtWidgets.QStyle.SP_DialogOpenButton), "Open NSS, NCS, or DLG…", self)
        self.open_action.setIconText("Open")
        self.open_action.setStatusTip("Open a script or dialogue as an editable GhostStudio document.")
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(lambda: self.openFileRequested.emit(self.target_game()))
        self.save_action = QtGui.QAction(self._icon("save", QtWidgets.QStyle.SP_DialogSaveButton), "Save", self)
        self.save_action.setStatusTip("Save the current source document without writing into the installed game.")
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(lambda: self.saveRequested.emit(self.current_document_id(), False))
        self.save_as_action = QtGui.QAction("Save As…", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(lambda: self.saveRequested.emit(self.current_document_id(), True))
        self.save_all_action = QtGui.QAction("Save All", self)
        self.save_all_action.setStatusTip("Save every changed script and dialogue document.")
        self.save_all_action.setShortcut("Ctrl+Alt+S")
        self.save_all_action.triggered.connect(self.saveAllRequested.emit)
        self.compile_action = QtGui.QAction(self._icon("build", QtWidgets.QStyle.SP_CommandLink), "Compile Script", self)
        self.compile_action.setIconText("Compile")
        self.compile_action.setStatusTip("Compile the current NWScript source and show line diagnostics.")
        self.compile_action.setShortcut("F7")
        self.compile_action.triggered.connect(lambda: self.compileRequested.emit(self.current_document_id()))
        self.validate_action = QtGui.QAction(self._icon("diag", QtWidgets.QStyle.SP_MessageBoxInformation), "Validate", self)
        self.validate_action.setStatusTip("Validate the current resource before packaging it.")
        self.validate_action.setShortcut("Ctrl+Shift+V")
        self.validate_action.triggered.connect(lambda: self.validateRequested.emit(self.current_document_id()))
        self.build_action = QtGui.QAction(self._icon("export", QtWidgets.QStyle.SP_DialogSaveButton), "Build Narrative Resources", self)
        self.build_action.setIconText("Build")
        self.build_action.setStatusTip("Build validated NCS and DLG resources for Map Studio or module export.")
        self.build_action.setShortcut("Ctrl+B")
        self.build_action.triggered.connect(lambda: self.buildRequested.emit(self.target_game()))
        self.refresh_action = QtGui.QAction(self._icon("refresh", QtWidgets.QStyle.SP_BrowserReload), "Refresh Game Resources", self)
        self.refresh_action.setStatusTip("Load the installed game's script and dialogue catalog on demand.")
        self.refresh_action.triggered.connect(lambda: self.refreshResourcesRequested.emit(self.target_game()))
        self.main_template_action = QtGui.QAction("Apply main() Template", self)
        self.main_template_action.triggered.connect(
            lambda: self._apply_script_template(
                "void main()\n{\n    // Add KOTOR gameplay actions here.\n}\n"
            )
        )
        self.conditional_template_action = QtGui.QAction("Apply StartingConditional() Template", self)
        self.conditional_template_action.triggered.connect(
            lambda: self._apply_script_template(
                "int StartingConditional()\n{\n    // Return TRUE when this dialogue branch is available.\n    return TRUE;\n}\n"
            )
        )
        self.quest_template_action = QtGui.QAction("Apply Quest-State Template", self)
        self.quest_template_action.triggered.connect(
            lambda: self._apply_script_template(
                "void main()\n{\n    // Register the variable first, then replace this placeholder name/state.\n"
                "    SetGlobalNumber(\"GLOBAL_NAME\", 1);\n}\n"
            )
        )
        self.guide_action = QtGui.QAction("Scripting Studio Guide", self)
        self.guide_action.setShortcut("F1")
        self.guide_action.triggered.connect(self._show_quick_guide)
        self.close_action = QtGui.QAction("Close", self)
        self.close_action.setShortcut("Ctrl+W")
        self.close_action.triggered.connect(self.close)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        for action in (
            self.new_script_action, self.new_dialogue_action, self.open_action, None,
            self.save_action, self.save_as_action, self.save_all_action, None, self.close_action,
        ):
            file_menu.addSeparator() if action is None else file_menu.addAction(action)
        build_menu = self.menuBar().addMenu("Build")
        build_menu.addAction(self.compile_action)
        build_menu.addAction(self.validate_action)
        build_menu.addSeparator()
        build_menu.addAction(self.build_action)
        script_menu = self.menuBar().addMenu("Script")
        script_menu.addAction(self.main_template_action)
        script_menu.addAction(self.conditional_template_action)
        script_menu.addAction(self.quest_template_action)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.refresh_action)
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.guide_action)

    def _build_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Scripting Suite", self)
        toolbar.setObjectName("scriptingDialogueStudioToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        for action in (
            self.new_script_action, self.new_dialogue_action, self.open_action, None,
            self.save_action, self.save_all_action, None,
            self.compile_action, self.validate_action, self.build_action,
        ):
            toolbar.addSeparator() if action is None else toolbar.addAction(action)
        toolbar.addSeparator()
        target_label = QtWidgets.QLabel("Target game")
        target_label.setObjectName("scriptingStudioTargetGameLabel")
        toolbar.addWidget(target_label)
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.setObjectName("scriptingStudioTargetGameComboBox")
        self.game_combo.addItems(["K1", "K2"])
        self.game_combo.setCurrentText("K2")
        self.game_combo.currentTextChanged.connect(self.targetGameChanged.emit)
        toolbar.addWidget(self.game_combo)
        self.studio_toolbar = toolbar
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

    def _build_script_dialogue_workspace(self) -> QtWidgets.QWidget:
        outer = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        outer.setObjectName("scriptingDialogueStudioOuterSplitter")
        outer.setChildrenCollapsible(False)
        outer.addWidget(self._build_resource_panel())
        workspace = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        workspace.setObjectName("scriptingDialogueStudioWorkspaceSplitter")
        workspace.setChildrenCollapsible(False)
        self.editor_tabs = QtWidgets.QTabWidget()
        self.editor_tabs.setObjectName("scriptingDialogueStudioEditorTabs")
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.setMovable(True)
        self.editor_tabs.tabCloseRequested.connect(self._tab_close_requested)
        self.editor_tabs.currentChanged.connect(lambda _index: self._update_action_state())
        self.welcome_page = self._build_welcome_page()
        welcome_index = self.editor_tabs.addTab(self.welcome_page, "Start")
        self.editor_tabs.tabBar().setTabButton(welcome_index, QtWidgets.QTabBar.RightSide, None)
        self.editor_tabs.tabBar().setTabButton(welcome_index, QtWidgets.QTabBar.LeftSide, None)
        workspace.addWidget(self.editor_tabs)
        workspace.addWidget(self._build_diagnostics_panel())
        workspace.setStretchFactor(0, 5)
        workspace.setStretchFactor(1, 1)
        outer.addWidget(workspace)
        outer.setStretchFactor(0, 0)
        outer.setStretchFactor(1, 1)
        self.outer_splitter = outer
        self.workspace_splitter = workspace
        return outer

    def _build_central(self) -> None:
        """Compose every preserved GhostScripter workflow without crowding editors."""

        suite = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        suite.setObjectName("scriptingSuiteNavigationSplitter")
        suite.setChildrenCollapsible(False)

        navigation_panel = QtWidgets.QWidget(self)
        navigation_panel.setObjectName("scriptingSuiteNavigationPanel")
        navigation_layout = QtWidgets.QVBoxLayout(navigation_panel)
        navigation_layout.setContentsMargins(6, 8, 6, 8)
        heading = QtWidgets.QLabel("Scripting Suite", navigation_panel)
        heading.setObjectName("scriptingSuiteNavigationHeading")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)
        navigation_layout.addWidget(heading)
        self.suite_navigation = QtWidgets.QListWidget(navigation_panel)
        self.suite_navigation.setObjectName("scriptingSuiteNavigation")
        self.suite_navigation.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.suite_navigation.setUniformItemSizes(True)
        navigation_layout.addWidget(self.suite_navigation, 1)
        target_note = QtWidgets.QLabel(
            "All editors use the target game selected above. Source game files open as copies.",
            navigation_panel,
        )
        target_note.setObjectName("scriptingSuiteNavigationSafetyNote")
        target_note.setWordWrap(True)
        navigation_layout.addWidget(target_note)

        self.suite_stack = QtWidgets.QStackedWidget(self)
        self.suite_stack.setObjectName("scriptingSuitePageStack")
        self.script_dialogue_workspace = self._build_script_dialogue_workspace()
        self.nwscript_reference_page = QtNWScriptReferencePage(self)
        self.quest_scaffold_page = QtQuestScaffoldPage(self)
        self.quest_journal_page = QuestJournalPage(self)
        self.twoda_globals_page = TwoDAGlobalsPage(self)
        self.talk_table_page = TalkTablePage(self)
        self.lip_sound_set_page = LipSoundSetPage(self)
        self.project_history_page = QtScriptingProjectHistoryPage(self)
        self.package_override_page = QtScriptingPackageOverridePage(self)
        self.integrated_tools_page = QtScriptingIntegratedToolsPage(self)
        self.tutorial_page = QtScriptingTutorialPage(self)

        pages: list[tuple[str, str, QtWidgets.QWidget]] = [
            ("code", "Scripts & Dialogue", self.script_dialogue_workspace),
            ("reference", "NWScript Reference", self.nwscript_reference_page),
            ("quest", "Quest Builder", self.quest_scaffold_page),
            ("journal", "Journal (JRL)", self.quest_journal_page),
            ("tables", "2DA & Globals", self.twoda_globals_page),
            ("talk", "Talk Table (TLK)", self.talk_table_page),
            ("voice", "Voice, Lip & SSF", self.lip_sound_set_page),
            ("project", "Project & History", self.project_history_page),
            ("package", "Package & Test Install", self.package_override_page),
            ("tutorial", "Guided Workflows", self.tutorial_page),
        ]
        try:
            from src.gui.windows.qt_scripting_blueprint_page import QtScriptingBlueprintPage

            self.blueprint_page = QtScriptingBlueprintPage(self)
            pages.append(("blueprint", "Blueprint & GFF", self.blueprint_page))
        except ImportError:
            self.blueprint_page = None
        pages.append(("integrated", "Integrated Tools", self.integrated_tools_page))

        self._suite_page_rows: dict[str, int] = {}
        for row, (key, label, page) in enumerate(pages):
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, key)
            self.suite_navigation.addItem(item)
            self.suite_stack.addWidget(page)
            self._suite_page_rows[key] = row

        self.suite_navigation.currentRowChanged.connect(self._suite_page_changed)
        self.nwscript_reference_page.searchRequested.connect(self.referenceSearchRequested.emit)
        self.nwscript_reference_page.insertRequested.connect(self.referenceInsertRequested.emit)
        self.targetGameChanged.connect(self.nwscript_reference_page.set_game)
        self.tutorial_page.destinationRequested.connect(self.show_suite_page)

        suite.addWidget(navigation_panel)
        suite.addWidget(self.suite_stack)
        suite.setStretchFactor(0, 0)
        suite.setStretchFactor(1, 1)
        self.suite_splitter = suite
        self.suite_navigation_panel = navigation_panel
        self.suite_navigation.setCurrentRow(0)
        self.setCentralWidget(suite)

    def _suite_page_changed(self, row: int) -> None:
        if row < 0 or row >= self.suite_stack.count():
            return
        self.suite_stack.setCurrentIndex(row)
        key = str(self.suite_navigation.item(row).data(QtCore.Qt.UserRole) or "")
        if key == "code":
            self._update_action_state()
        else:
            self.compile_action.setEnabled(False)
            self.validate_action.setEnabled(False)
        self.statusBar().showMessage(f"Scripting Suite — {self.suite_navigation.item(row).text()}", 3500)

    def show_suite_page(self, key: str) -> bool:
        row = self._suite_page_rows.get(str(key or "").strip().lower())
        if row is None:
            return False
        self.suite_navigation.setCurrentRow(row)
        return True

    def _build_welcome_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        page.setObjectName("scriptingStudioWelcomePage")
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.addStretch(1)

        content = QtWidgets.QWidget()
        content.setObjectName("scriptingStudioWelcomeContent")
        content.setMaximumWidth(820)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("GhostStudio Scripting Suite")
        title.setObjectName("scriptingStudioWelcomeTitle")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(max(title_font.pointSize() + 5, 15))
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Author scripts, conversations, quests, journals, tables, voice data, and packaged KOTOR resources in one focused workbench."
        )
        subtitle.setObjectName("scriptingStudioWelcomeSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        start_group = QtWidgets.QGroupBox("Start authoring")
        start_group.setObjectName("scriptingStudioWelcomeStartGroup")
        start_layout = QtWidgets.QGridLayout(start_group)
        start_actions = (
            ("New Script", self.new_script_action, "Write and compile an NSS gameplay script."),
            ("New Dialogue", self.new_dialogue_action, "Build NPC and player conversation branches."),
            ("Open Resource…", self.open_action, "Open NSS, NCS, or DLG from disk."),
            ("Browse Game Resources", self.refresh_action, "Load vanilla resources into the browser at left."),
        )
        for index, (label, action, description) in enumerate(start_actions):
            button = QtWidgets.QPushButton(action.icon(), label)
            button.setObjectName(f"scriptingStudioWelcomeAction{index + 1}")
            button.setToolTip(description)
            button.clicked.connect(action.trigger)
            start_layout.addWidget(button, index // 2, index % 2)
        layout.addWidget(start_group)

        workflow_group = QtWidgets.QGroupBox("Map Studio workflow")
        workflow_group.setObjectName("scriptingStudioWelcomeWorkflowGroup")
        workflow_layout = QtWidgets.QVBoxLayout(workflow_group)
        workflow = QtWidgets.QLabel(
            "1. Open Edit Script or Edit Dialogue from a placed map object.\n"
            "2. Author, compile, and validate here.\n"
            "3. Choose Build Narrative Resources. Map Studio stages validated runtime resources for export.\n"
            "After any further edit, build again before exporting the map."
        )
        workflow.setObjectName("scriptingStudioWelcomeWorkflowText")
        workflow.setWordWrap(True)
        workflow_layout.addWidget(workflow)
        safety = QtWidgets.QLabel(
            "Installed game resources always open as copies. GhostStudio never overwrites the game during editing."
        )
        safety.setObjectName("scriptingStudioWelcomeSafetyText")
        safety.setWordWrap(True)
        workflow_layout.addWidget(safety)
        layout.addWidget(workflow_group)

        guide = QtWidgets.QPushButton("Open Quick Guide (F1)")
        guide.setObjectName("scriptingStudioWelcomeGuideButton")
        guide.clicked.connect(self.guide_action.trigger)
        layout.addWidget(guide, 0, QtCore.Qt.AlignLeft)

        outer.addWidget(content, 0, QtCore.Qt.AlignHCenter)
        outer.addStretch(1)
        return page

    def _build_resource_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("scriptingStudioResourcePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        heading = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Scripts & Dialogues")
        title.setObjectName("scriptingStudioResourceHeading")
        heading.addWidget(title)
        heading.addStretch(1)
        refresh = QtWidgets.QToolButton()
        refresh.setDefaultAction(self.refresh_action)
        heading.addWidget(refresh)
        layout.addLayout(heading)
        self.resource_search = QtWidgets.QLineEdit()
        self.resource_search.setObjectName("scriptingStudioResourceSearchEdit")
        self.resource_search.setPlaceholderText("Search open and game resources…")
        self.resource_search.setClearButtonEnabled(True)
        layout.addWidget(self.resource_search)
        self.resource_kind_combo = QtWidgets.QComboBox()
        self.resource_kind_combo.setObjectName("scriptingStudioResourceKindComboBox")
        self.resource_kind_combo.addItem("All resources", "all")
        self.resource_kind_combo.addItem("Scripts", "script")
        self.resource_kind_combo.addItem("Dialogues", "dialogue")
        layout.addWidget(self.resource_kind_combo)
        self.resource_tree = QtWidgets.QTreeView()
        self.resource_tree.setObjectName("scriptingStudioResourceTree")
        self.resource_tree.setRootIsDecorated(False)
        self.resource_tree.setAlternatingRowColors(True)
        self.resource_tree.setSortingEnabled(True)
        self.resource_model = QtGui.QStandardItemModel(self)
        self.resource_model.setHorizontalHeaderLabels(["Resource", "Type", "Origin"])
        self.resource_proxy = _ResourceFilterProxy(self)
        self.resource_proxy.setSourceModel(self.resource_model)
        self.resource_tree.setModel(self.resource_proxy)
        self.resource_tree.doubleClicked.connect(self._activate_resource_index)
        layout.addWidget(self.resource_tree, 1)
        note = QtWidgets.QLabel(
            "Refresh loads the installed-game catalog on demand. Game resources open as editable copies; saving never overwrites the installation."
        )
        note.setObjectName("scriptingStudioResourceSafetyLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.resource_search.textChanged.connect(self._update_resource_filter)
        self.resource_kind_combo.currentIndexChanged.connect(self._update_resource_filter)
        return panel

    def _build_diagnostics_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("scriptingStudioDiagnosticsPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Compiler, Validation & Packaging")
        title.setObjectName("scriptingStudioDiagnosticsHeading")
        header.addWidget(title)
        header.addStretch(1)
        self.diagnostic_summary = QtWidgets.QLabel("Ready")
        self.diagnostic_summary.setObjectName("scriptingStudioDiagnosticSummary")
        header.addWidget(self.diagnostic_summary)
        layout.addLayout(header)
        self.diagnostics_tree = QtWidgets.QTreeWidget()
        self.diagnostics_tree.setObjectName("scriptingStudioDiagnosticsTree")
        self.diagnostics_tree.setHeaderLabels(["Severity", "Resource", "Line", "Message"])
        self.diagnostics_tree.setAlternatingRowColors(True)
        self.diagnostics_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.diagnostics_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.diagnostics_tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.diagnostics_tree.header().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.diagnostics_tree.itemActivated.connect(self._diagnostic_activated)
        layout.addWidget(self.diagnostics_tree, 1)
        return panel

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage(
            "Choose a Scripting Suite page. Structural readback is not retail KOTOR execution proof.", 0
        )

    def _apply_script_template(self, source: str) -> None:
        page = self.editor_tabs.currentWidget()
        if not isinstance(page, ScriptEditorPage):
            QtWidgets.QMessageBox.information(
                self,
                "NWScript Template",
                "Open or create a script tab before applying a template.",
            )
            return
        if page.editor.toPlainText().strip():
            choice = QtWidgets.QMessageBox.question(
                self,
                "Replace Script Source",
                "Replace the current script with this starter template?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel,
            )
            if choice != QtWidgets.QMessageBox.Yes:
                return
        page.insert_template(source)

    def _show_quick_guide(self) -> None:
        self.show_suite_page("tutorial")

    def set_save_all_handler(self, callback: Callable[[], bool]) -> None:
        self._save_all_handler = callback

    def target_game(self) -> str:
        return str(self.game_combo.currentText() or "K2").upper()

    def set_target_game(self, game: str) -> None:
        value = str(game or "K2").upper()
        index = self.game_combo.findText(value)
        if index >= 0:
            self.game_combo.setCurrentIndex(index)
        self.nwscript_reference_page.set_game(value)

    def set_reference_categories(self, categories: object) -> None:
        self.nwscript_reference_page.set_categories(tuple(categories or ()))

    def set_reference_rows(self, rows: object, *, summary: str = "") -> None:
        values = tuple(rows or ())
        self.nwscript_reference_page.set_rows(values, summary=summary)

    def set_script_completion_symbols(self, values: object) -> None:
        symbols = set(_COMMON_NWSCRIPT_SYMBOLS)
        symbols.update(str(value) for value in tuple(values or ()) if str(value).strip())
        self._reference_symbols = symbols
        for page in self._document_pages.values():
            if isinstance(page, ScriptEditorPage):
                page.editor.set_completion_symbols(symbols)

    def set_script_completion_definitions(self, values: object) -> None:
        definitions = tuple(dict(value) for value in tuple(values or ()) if isinstance(value, Mapping))
        self._reference_definitions = definitions
        for page in self._document_pages.values():
            if isinstance(page, ScriptEditorPage):
                page.editor.set_completion_definitions(definitions)

    def insert_into_active_script(self, text: str) -> bool:
        page = self.editor_tabs.currentWidget()
        if not isinstance(page, ScriptEditorPage):
            return False
        page.editor.insertPlainText(str(text or ""))
        self.show_suite_page("code")
        page.editor.setFocus(QtCore.Qt.OtherFocusReason)
        return True

    def current_document_id(self) -> str:
        widget = self.editor_tabs.currentWidget()
        return str(getattr(widget, "document_id", "") or "")

    def page_for_document(self, document_id: str) -> QtWidgets.QWidget | None:
        return self._document_pages.get(str(document_id))

    def add_script_document(self, row: Mapping[str, Any], source: str) -> ScriptEditorPage:
        document_id = str(row.get("document_id") or "")
        existing = self._document_pages.get(document_id)
        if isinstance(existing, ScriptEditorPage):
            self.editor_tabs.setCurrentWidget(existing)
            return existing
        page = ScriptEditorPage(
            document_id,
            source,
            self,
            disassembly=str(row.get("disassembly") or ""),
            recovered_source_exact=bool(row.get("recovered_source_exact")),
        )
        if self._reference_definitions:
            page.editor.set_completion_definitions(self._reference_definitions)
        else:
            page.editor.set_completion_symbols(self._reference_symbols)
        page.sourceChanged.connect(self._forward_script_changed)
        self._document_pages[document_id] = page
        self._document_rows[document_id] = dict(row)
        self.editor_tabs.addTab(page, "")
        self.editor_tabs.setCurrentWidget(page)
        self._refresh_document_label(document_id)
        self._update_action_state()
        return page

    def add_dialogue_document(self, row: Mapping[str, Any]) -> DialogueEditorPage:
        document_id = str(row.get("document_id") or "")
        existing = self._document_pages.get(document_id)
        if isinstance(existing, DialogueEditorPage):
            self.editor_tabs.setCurrentWidget(existing)
            return existing
        page = DialogueEditorPage(document_id, self)
        page.fieldsApplied.connect(self._forward_dialogue_fields)
        page.settingsApplied.connect(self._forward_dialogue_settings)
        page.addStarterRequested.connect(self._forward_add_starter)
        page.addChildRequested.connect(self._forward_add_child)
        page.linkExistingRequested.connect(self._forward_link_existing)
        page.startExistingRequested.connect(self._forward_start_existing)
        page.retargetLinkRequested.connect(self._forward_retarget_link)
        page.removeLinkRequested.connect(self._forward_remove_link)
        page.deleteNodeRequested.connect(self._forward_delete_node)
        page.makeEditableCopyRequested.connect(self.dialogueMakeEditableCopyRequested.emit)
        page.audioPreviewRequested.connect(self.dialogueAudioPreviewRequested.emit)
        page.audioBrowseRequested.connect(self.dialogueAudioBrowseRequested.emit)
        page.audioStopRequested.connect(self.dialogueAudioStopRequested.emit)
        page.participantBrowseRequested.connect(self.dialogueParticipantBrowseRequested.emit)
        self._document_pages[document_id] = page
        self._document_rows[document_id] = dict(row)
        self.editor_tabs.addTab(page, "")
        self.editor_tabs.setCurrentWidget(page)
        self._refresh_document_label(document_id)
        page.set_topology_policy(bool(row.get("topology_requires_editable_copy")))
        self._update_action_state()
        return page

    # Signals are attached by the controller to avoid exposing mutable DLG models.
    scriptSourceChanged = QtCore.Signal(str, str)
    dialogueFieldsApplied = QtCore.Signal(str, str, str, object)
    dialogueSettingsApplied = QtCore.Signal(str, object)
    dialogueAddStarterRequested = QtCore.Signal(str)
    dialogueAddChildRequested = QtCore.Signal(str, str)
    dialogueLinkExistingRequested = QtCore.Signal(str, str, str)
    dialogueStartExistingRequested = QtCore.Signal(str, str)
    dialogueRetargetLinkRequested = QtCore.Signal(str, str, str)
    dialogueRemoveLinkRequested = QtCore.Signal(str, str)
    dialogueDeleteNodeRequested = QtCore.Signal(str, str)
    dialogueMakeEditableCopyRequested = QtCore.Signal(str)

    def _forward_script_changed(self, document_id: str, source: str) -> None:
        self.scriptSourceChanged.emit(document_id, source)

    def _forward_dialogue_fields(self, document_id: str, node_id: str, link_id: str, values: object) -> None:
        self.dialogueFieldsApplied.emit(document_id, node_id, link_id, values)

    def _forward_dialogue_settings(self, document_id: str, values: object) -> None:
        self.dialogueSettingsApplied.emit(document_id, values)

    def _forward_add_starter(self, document_id: str) -> None:
        self.dialogueAddStarterRequested.emit(document_id)

    def _forward_add_child(self, document_id: str, link_id: str) -> None:
        self.dialogueAddChildRequested.emit(document_id, link_id)

    def _forward_link_existing(self, document_id: str, source_link_id: str, target_node_id: str) -> None:
        self.dialogueLinkExistingRequested.emit(document_id, source_link_id, target_node_id)

    def _forward_start_existing(self, document_id: str, target_node_id: str) -> None:
        self.dialogueStartExistingRequested.emit(document_id, target_node_id)

    def _forward_retarget_link(self, document_id: str, link_id: str, target_node_id: str) -> None:
        self.dialogueRetargetLinkRequested.emit(document_id, link_id, target_node_id)

    def _forward_remove_link(self, document_id: str, link_id: str) -> None:
        self.dialogueRemoveLinkRequested.emit(document_id, link_id)

    def _forward_delete_node(self, document_id: str, node_id: str) -> None:
        self.dialogueDeleteNodeRequested.emit(document_id, node_id)

    def update_document_row(self, row: Mapping[str, Any]) -> None:
        document_id = str(row.get("document_id") or "")
        if not document_id:
            return
        self._document_rows[document_id] = dict(row)
        self._refresh_document_label(document_id)
        page = self._document_pages.get(document_id)
        if isinstance(page, DialogueEditorPage):
            page.set_topology_policy(bool(row.get("topology_requires_editable_copy")))

    def _refresh_document_label(self, document_id: str) -> None:
        page = self._document_pages.get(document_id)
        if page is None:
            return
        index = self.editor_tabs.indexOf(page)
        if index < 0:
            return
        row = self._document_rows.get(document_id, {})
        label = str(row.get("display_name") or row.get("resref") or "Untitled")
        if bool(row.get("dirty")):
            label += " *"
        self.editor_tabs.setTabText(index, label)
        self.editor_tabs.setTabToolTip(index, str(row.get("source_path") or row.get("origin") or label))

    def set_dialogue_graph(self, document_id: str, rows: list[dict[str, Any]]) -> None:
        page = self._document_pages.get(str(document_id))
        if isinstance(page, DialogueEditorPage):
            page.set_graph(rows)

    def select_dialogue_link(self, document_id: str, link_id: str) -> bool:
        page = self._document_pages.get(str(document_id))
        return bool(isinstance(page, DialogueEditorPage) and page.select_link(link_id))

    def set_dialogue_settings(self, document_id: str, row: Mapping[str, Any]) -> None:
        page = self._document_pages.get(str(document_id))
        if isinstance(page, DialogueEditorPage):
            page.set_settings(row)

    def set_dialogue_audio_reference(
        self,
        document_id: str,
        field: str,
        resref: str,
        *,
        message: str = "",
    ) -> None:
        page = self._document_pages.get(str(document_id))
        if isinstance(page, DialogueEditorPage):
            page.set_audio_reference(field, resref, message=message)

    def choose_dialogue_participant(
        self,
        document_id: str,
        field: str,
        rows: object,
        *,
        current: str = "",
    ) -> str:
        page = self._document_pages.get(str(document_id))
        if not isinstance(page, DialogueEditorPage):
            return ""
        dialog = _DialogueParticipantPicker(rows, current=current, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return ""
        selected = dialog.selected_tag
        if not selected:
            return ""
        editor = page.listener_edit if str(field).casefold() == "listener" else page.speaker_edit
        editor.setText(selected)
        editor.setFocus(QtCore.Qt.OtherFocusReason)
        return selected

    def set_dialogue_audio_preview_state(
        self,
        document_id: str,
        field: str,
        state: str,
        *,
        message: str = "",
        position_ms: int = 0,
        duration_ms: int = 0,
    ) -> None:
        page = self._document_pages.get(str(document_id))
        if isinstance(page, DialogueEditorPage):
            page.set_audio_preview_state(
                field,
                state,
                message=message,
                position_ms=position_ms,
                duration_ms=duration_ms,
            )

    def set_resource_rows(self, rows: list[dict[str, Any]]) -> None:
        self.resource_model.removeRows(0, self.resource_model.rowCount())
        for row in rows:
            label = str(row.get("resref") or row.get("display_name") or "resource")
            type_label = str(row.get("restype") or row.get("kind") or "").upper()
            origin = str(row.get("origin") or "")
            items = [QtGui.QStandardItem(label), QtGui.QStandardItem(type_label), QtGui.QStandardItem(origin)]
            for item in items:
                item.setEditable(False)
            items[0].setData(dict(row), RESOURCE_ROW_ROLE)
            self.resource_model.appendRow(items)
        self.resource_tree.resizeColumnToContents(0)
        self._update_resource_filter()

    def _update_resource_filter(self) -> None:
        self.resource_proxy.set_filters(
            self.resource_search.text(),
            str(self.resource_kind_combo.currentData() or "all"),
        )

    def _activate_resource_index(self, index: QtCore.QModelIndex) -> None:
        source = self.resource_proxy.mapToSource(index)
        row = dict(self.resource_model.item(source.row(), 0).data(RESOURCE_ROW_ROLE) or {})
        if row:
            self.resourceActivated.emit(row)

    def set_diagnostics(self, rows: list[dict[str, Any]], *, summary: str = "") -> None:
        self.diagnostics_tree.clear()
        blocking = 0
        warnings = 0
        for row in rows:
            severity = str(row.get("severity") or "info").title()
            line = row.get("line")
            item = QtWidgets.QTreeWidgetItem([
                severity,
                str(row.get("resource") or ""),
                str(line or ""),
                str(row.get("message") or ""),
            ])
            item.setData(0, DOCUMENT_ROLE, dict(row))
            item.setToolTip(3, str(row.get("fix_hint") or row.get("message") or ""))
            self.diagnostics_tree.addTopLevelItem(item)
            key = severity.lower()
            blocking += int(key in {"blocking", "error"})
            warnings += int(key == "warning")
        self.diagnostic_summary.setText(summary or f"{blocking} blocking • {warnings} warning • {len(rows)} total")

    def _diagnostic_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        row = dict(item.data(0, DOCUMENT_ROLE) or {})
        resource = str(row.get("resource") or "").lower()
        for document_id, metadata in self._document_rows.items():
            if str(metadata.get("resref") or "").lower() != resource:
                continue
            page = self._document_pages.get(document_id)
            if page is not None:
                self.editor_tabs.setCurrentWidget(page)
            if isinstance(page, ScriptEditorPage):
                page.editor.goto_location(row.get("line"), row.get("column"))
            break

    def _tab_close_requested(self, index: int) -> None:
        page = self.editor_tabs.widget(index)
        if page is self.welcome_page:
            return
        document_id = str(getattr(page, "document_id", "") or "")
        row = self._document_rows.get(document_id, {})
        if row.get("dirty"):
            choice = QtWidgets.QMessageBox.question(
                self,
                "Unsaved Narrative Resource",
                f"Save changes to {row.get('display_name') or 'this document'} before closing it?",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Save,
            )
            if choice == QtWidgets.QMessageBox.Cancel:
                return
            if choice == QtWidgets.QMessageBox.Save:
                self.saveRequested.emit(document_id, False)
                if self._document_rows.get(document_id, {}).get("dirty"):
                    return
        self.editor_tabs.removeTab(index)
        self._document_pages.pop(document_id, None)
        self._document_rows.pop(document_id, None)
        if page is not None:
            page.deleteLater()
        self.documentClosed.emit(document_id)
        self._update_action_state()

    def _update_action_state(self) -> None:
        navigation = getattr(self, "suite_navigation", None)
        if navigation is not None:
            item = navigation.currentItem()
            if item is not None and str(item.data(QtCore.Qt.UserRole) or "") != "code":
                self.save_action.setEnabled(False)
                self.save_as_action.setEnabled(False)
                self.compile_action.setEnabled(False)
                self.validate_action.setEnabled(False)
                return
        document_id = self.current_document_id()
        row = self._document_rows.get(document_id, {})
        has_document = bool(document_id)
        is_script = str(row.get("kind") or "") == "script"
        self.save_action.setEnabled(has_document)
        self.save_as_action.setEnabled(has_document)
        self.compile_action.setEnabled(is_script)
        self.validate_action.setEnabled(has_document)

    def dirty_document_ids(self) -> tuple[str, ...]:
        return tuple(key for key, row in self._document_rows.items() if bool(row.get("dirty")))

    def focus_document(self, document_id: str) -> None:
        page = self._document_pages.get(str(document_id))
        if page is not None:
            self.editor_tabs.setCurrentWidget(page)
            self.raise_()
            self.activateWindow()

    def apply_ghost_theme(self, theme: Any) -> None:
        palette = self.palette()
        for page in self._document_pages.values():
            if isinstance(page, ScriptEditorPage):
                page.editor.highlighter.apply_palette(palette)
            elif isinstance(page, DialogueEditorPage):
                page.graph.apply_palette(palette)
        for page in (
            self.nwscript_reference_page,
            self.quest_scaffold_page,
            self.quest_journal_page,
            self.twoda_globals_page,
            self.talk_table_page,
            self.lip_sound_set_page,
            self.project_history_page,
            self.package_override_page,
            self.tutorial_page,
            self.blueprint_page,
            self.integrated_tools_page,
        ):
            apply_theme = getattr(page, "apply_ghost_theme", None)
            if callable(apply_theme):
                apply_theme(theme)
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        self.resize(layout.main_width, layout.main_height)
        self.suite_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.outer_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.workspace_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        resource_panel = layout.panel("library")
        navigation_width = max(190, min(280, int(resource_panel.preferred_width * 0.72)))
        self.suite_splitter.setSizes([navigation_width, max(900, layout.main_width - navigation_width)])
        self.outer_splitter.setSizes([resource_panel.preferred_width, max(800, layout.viewport.preferred_width)])
        self.workspace_splitter.setSizes([
            max(540, layout.main_height - layout.panel("output_log").preferred_height),
            layout.panel("output_log").preferred_height,
        ])
        toolbar = layout.toolbar("main")
        self.studio_toolbar.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
        self.studio_toolbar.setMinimumHeight(toolbar.height)
        for page in (
            self.nwscript_reference_page,
            self.quest_scaffold_page,
            self.quest_journal_page,
            self.twoda_globals_page,
            self.talk_table_page,
            self.lip_sound_set_page,
            self.project_history_page,
            self.package_override_page,
            self.tutorial_page,
            self.blueprint_page,
            self.integrated_tools_page,
        ):
            apply_layout = getattr(page, "apply_ghost_layout", None)
            if callable(apply_layout):
                apply_layout(layout)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 - Qt API
        dirty = self.dirty_document_ids()
        if not dirty:
            self.dialogueAudioStopRequested.emit("")
            event.accept()
            return
        choice = QtWidgets.QMessageBox.question(
            self,
            "Unsaved Scripts or Dialogues",
            f"{len(dirty)} document(s) have unsaved changes. Save all before closing the studio?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save,
        )
        if choice == QtWidgets.QMessageBox.Cancel:
            event.ignore()
        elif choice == QtWidgets.QMessageBox.Discard:
            self.dialogueAudioStopRequested.emit("")
            event.accept()
        elif self._save_all_handler is not None and self._save_all_handler():
            self.dialogueAudioStopRequested.emit("")
            event.accept()
        else:
            event.ignore()


__all__ = [
    "DialogueEditorPage",
    "NssCodeEditor",
    "NssSyntaxHighlighter",
    "QtScriptingDialogueStudioWindow",
    "ScriptEditorPage",
]
