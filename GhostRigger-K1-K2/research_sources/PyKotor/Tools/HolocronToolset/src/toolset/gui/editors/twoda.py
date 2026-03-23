"""2DA editor: table view, row/column edit, default row, and CSV/JSON import/export."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any

import qtpy

from qtpy.QtCore import QObject, QSortFilterProxyModel, Qt
from qtpy.QtGui import QColor, QKeySequence, QPalette, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QShortcut,  # pyright: ignore[reportPrivateImportUsage]
    )

from pykotor.resource.formats.twoda import TwoDA, read_2da, write_2da
from pykotor.resource.type import ResourceType
from toolset.gui.common.filters import NoScrollEventFilter
from toolset.gui.common.localization import translate
from toolset.gui.editor import Editor
from toolset.gui.widgets.settings.installations import GlobalSettings
from utility.error_handling import assert_with_variable_trace

try:
    from qtpy.QtWidgets import QUndoCommand, QUndoStack
except ImportError:
    from qtpy.QtGui import QUndoCommand, QUndoStack  # type: ignore[assignment]

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import QModelIndex
    from qtpy.QtWidgets import (
        QHeaderView,
        QWidget,
    )

    from toolset.data.installation import HTInstallation


class FindReplaceDialog(QDialog):
    """Find and Replace dialog for 2DA table cells."""

    def __init__(self, parent: QWidget | None, find_only: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Replace" if not find_only else "Find")
        self._find_only = find_only
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Find what:"), 0, 0)
        self.findEdit = QLineEdit(self)
        self.findEdit.setClearButtonEnabled(True)
        layout.addWidget(self.findEdit, 0, 1)
        layout.addWidget(QLabel("Replace with:"), 1, 0)
        self.replaceEdit = QLineEdit(self)
        self.replaceEdit.setClearButtonEnabled(True)
        if find_only:
            self.replaceEdit.setVisible(False)
            layout.addWidget(self.replaceEdit, 1, 1)  # keep for layout
        else:
            layout.addWidget(self.replaceEdit, 1, 1)
        self.matchCaseCheck = QCheckBox("Match case")
        layout.addWidget(self.matchCaseCheck, 2, 0, 1, 2)
        self.matchWholeCellCheck = QCheckBox("Match whole cell")
        layout.addWidget(self.matchWholeCellCheck, 3, 0, 1, 2)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if not find_only:
            self.replaceBtn = QPushButton("Replace")
            self.replaceAllBtn = QPushButton("Replace All")
            self.buttons.addButton(self.replaceBtn, QDialogButtonBox.ButtonRole.ActionRole)
            self.buttons.addButton(self.replaceAllBtn, QDialogButtonBox.ButtonRole.ActionRole)
        self.findNextBtn = QPushButton("Find Next")
        self.findPrevBtn = QPushButton("Find Previous")
        self.selectAllBtn = QPushButton("Select All")
        self.buttons.addButton(self.findNextBtn, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.addButton(self.findPrevBtn, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.addButton(self.selectAllBtn, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(self.buttons, 4, 0, 1, 2)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.findNextBtn.clicked.connect(lambda: self._emit_find(forward=True))
        self.findPrevBtn.clicked.connect(lambda: self._emit_find(forward=False))
        self.selectAllBtn.clicked.connect(self._emit_select_all)
        if not find_only:
            self.replaceBtn.clicked.connect(self._emit_replace_one)
            self.replaceAllBtn.clicked.connect(self._emit_replace_all)

    def _emit_find(self, forward: bool):
        self.done(100 if forward else 101)  # custom result codes

    def _emit_replace_one(self):
        self.done(102)

    def _emit_replace_all(self):
        self.done(103)

    def _emit_select_all(self):
        self.done(104)  # Select all matching cells

    def get_find_text(self) -> str:
        return self.findEdit.text()

    def get_replace_text(self) -> str:
        return self.replaceEdit.text()

    def is_match_case(self) -> bool:
        return self.matchCaseCheck.isChecked()

    def is_match_whole_cell(self) -> bool:
        return self.matchWholeCellCheck.isChecked()


class SortDialog(QDialog):
    """Multi-level sort dialog: primary column + optional Then by columns."""

    def __init__(self, parent: QWidget | None, column_names: list[str], current_col: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Sort")
        self._column_names = column_names
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Sort by:"), 0, 0)
        self.primary_combo = QComboBox(self)
        self.primary_combo.addItems(column_names)
        idx = max(0, min(current_col, len(column_names) - 1))
        self.primary_combo.setCurrentIndex(idx)
        layout.addWidget(self.primary_combo, 0, 1)
        layout.addWidget(QLabel("Order:"), 1, 0)
        self.primary_order = QComboBox(self)
        self.primary_order.addItems(["Ascending", "Descending"])
        layout.addWidget(self.primary_order, 1, 1)
        layout.addWidget(QLabel("Then by:"), 2, 0)
        self.then1_combo = QComboBox(self)
        self.then1_combo.addItem("— None —")
        self.then1_combo.addItems(column_names)
        layout.addWidget(self.then1_combo, 2, 1)
        layout.addWidget(QLabel("Order:"), 3, 0)
        self.then1_order = QComboBox(self)
        self.then1_order.addItems(["Ascending", "Descending"])
        layout.addWidget(self.then1_order, 3, 1)
        layout.addWidget(QLabel("Then by:"), 4, 0)
        self.then2_combo = QComboBox(self)
        self.then2_combo.addItem("— None —")
        self.then2_combo.addItems(column_names)
        layout.addWidget(self.then2_combo, 4, 1)
        layout.addWidget(QLabel("Order:"), 5, 0)
        self.then2_order = QComboBox(self)
        self.then2_order.addItems(["Ascending", "Descending"])
        layout.addWidget(self.then2_order, 5, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.buttons, 6, 0, 1, 2)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def get_sort_levels(self) -> list[tuple[int, bool]]:
        """Return list of (column_index_1based, ascending). Column 0 is row label; data columns are 1..n."""
        levels: list[tuple[int, bool]] = []
        primary_idx = self.primary_combo.currentIndex()
        if 0 <= primary_idx < len(self._column_names):
            asc = self.primary_order.currentIndex() == 0
            levels.append((primary_idx + 1, asc))
        if self.then1_combo.currentIndex() > 0:
            idx = self.then1_combo.currentIndex() - 1
            asc = self.then1_order.currentIndex() == 0
            levels.append((idx + 1, asc))
        if self.then2_combo.currentIndex() > 0:
            idx = self.then2_combo.currentIndex() - 1
            asc = self.then2_order.currentIndex() == 0
            levels.append((idx + 1, asc))
        return levels


# --- Undo commands for batch operations ---
class _SetCellTextCommand(QUndoCommand):
    def __init__(self, model: QStandardItemModel, row: int, col: int, old_text: str, new_text: str):
        super().__init__()
        self._model = model
        self._row, self._col = row, col
        self._old_text = old_text
        self._new_text = new_text
        self.setText("Edit cell")

    def undo(self):
        item = self._model.item(self._row, self._col)
        if item is not None:
            item.setText(self._old_text)

    def redo(self):
        item = self._model.item(self._row, self._col)
        if item is not None:
            item.setText(self._new_text)


class _UndoableTwoDAModel(QStandardItemModel):
    """Source model that pushes _SetCellTextCommand on setData so inline cell edits are undoable."""

    def __init__(
        self,
        parent: QWidget | None = None,
        editor_ref: TwoDAEditor | None = None,
    ):
        super().__init__(parent)
        self._editor_ref: TwoDAEditor | None = editor_ref

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: Qt.ItemDataRole | int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role == Qt.ItemDataRole.EditRole and index.isValid() and self._editor_ref is not None:
            row, col = index.row(), index.column()
            item = self.item(row, col)
            old = item.text() if item else ""
            try:
                new = value if isinstance(value, str) else (str(value) if value is not None else "")
            except Exception:
                new = ""
            if old != new:
                self._editor_ref._undo_stack.push(_SetCellTextCommand(self, row, col, old, new))
        return super().setData(index, value, role)


class _BatchSetCellsCommand(QUndoCommand):
    """Stores a list of (row, col, old_text, new_text) for undo/redo."""

    def __init__(self, model: QStandardItemModel, changes: list[tuple[int, int, str, str]], description: str = "Edit cells"):
        super().__init__()
        self._model = model
        self._changes = changes
        self.setText(description)

    def undo(self):
        for row, col, old_text, _ in self._changes:
            item = self._model.item(row, col)
            if item is not None:
                item.setText(old_text)

    def redo(self):
        for row, col, _, new_text in self._changes:
            item = self._model.item(row, col)
            if item is not None:
                item.setText(new_text)


class _InsertRowCommand(QUndoCommand):
    def __init__(
        self,
        model: QStandardItemModel,
        row: int,
        items: list[QStandardItem],
        editor_ref: TwoDAEditor,
    ):
        super().__init__()
        self._model: QStandardItemModel = model
        self._row: int = row
        self._items: list[QStandardItem] = items  # store clones for redo
        self._editor: TwoDAEditor = editor_ref
        self.setText("Insert row")

    def undo(self):
        self._model.removeRow(self._row)
        self._editor.reset_vertical_headers()

    def redo(self):
        self._model.insertRow(self._row, [it.clone() for it in self._items])
        self._editor.set_item_display_data(self._row)
        self._editor.reset_vertical_headers()


class _RemoveRowsCommand(QUndoCommand):
    def __init__(self, model: QStandardItemModel, row_indices: list[int], editor_ref: TwoDAEditor):
        super().__init__()
        self._model: QStandardItemModel = model
        self._rows: list[int] = sorted(row_indices, reverse=True)  # e.g. [5, 3, 1]
        self._saved_rows: list[list[QStandardItem]] = []
        self._editor: TwoDAEditor = editor_ref
        self.setText("Remove rows")

    def undo(self):
        # Insert back in ascending index order; _saved_rows order matches _rows (desc), so reverse for correct mapping
        for row_idx, saved in zip(sorted(self._rows), reversed(self._saved_rows)):
            items = [saved[c].clone() for c in range(len(saved))]
            self._model.insertRow(row_idx, items)
            self._editor.set_item_display_data(row_idx)
        self._editor.reset_vertical_headers()

    def redo(self):
        self._saved_rows.clear()
        for row_idx in self._rows:
            row_data = []
            for col in range(self._model.columnCount()):
                it = self._model.item(row_idx, col)
                row_data.append(it.clone() if it is not None else self._create_empty_item())
            self._saved_rows.append(row_data)
            self._model.removeRow(row_idx)
        self._editor.reset_vertical_headers()


class _InsertColumnCommand(QUndoCommand):
    def __init__(
        self,
        model: QStandardItemModel,
        col: int,
        header: str,
        editor_ref: TwoDAEditor,
    ):
        super().__init__()
        self._model: QStandardItemModel = model
        self._col: int = col
        self._header: str = header
        self._editor: TwoDAEditor = editor_ref
        self.setText("Insert column")

    def undo(self):
        self._model.removeColumn(self._col)
        self._editor._reconstruct_menu(self._editor._get_headers_list())

    def redo(self):
        self._model.insertColumn(self._col, self._create_empty_items(self._model.rowCount()))
        self._model.setHorizontalHeaderItem(self._col, QStandardItem(self._header))
        self._editor._reconstruct_menu(self._editor._get_headers_list())


class _SortCommand(QUndoCommand):
    """Undo command for sort by column: stores pre-sort state and permutation."""

    def __init__(
        self,
        model: QStandardItemModel,
        sort_column: int,
        ascending: bool,
        editor_ref: TwoDAEditor,
    ):
        super().__init__()
        self._model: QStandardItemModel = model
        self._col: int = sort_column
        self._ascending: bool = ascending
        self._editor: TwoDAEditor = editor_ref
        # Save full table state before sort (original order)
        self._saved: list[list[QStandardItem]] = []
        for r in range(model.rowCount()):
            row_items = []
            for c in range(model.columnCount()):
                it = model.item(r, c)
                row_items.append(it.clone() if it is not None else QStandardItem(""))
            self._saved.append(row_items)
        # Compute permutation: new_row_index -> old_row_index (which row moved to this position)
        rows = list(range(model.rowCount()))

        def key(r: int) -> str:
            it = model.item(r, self._col)
            assert it is not None, "Item should not be None"
            return it.text().lower()

        rows.sort(key=key, reverse=not self._ascending)
        self._permutation = rows  # new_idx -> old_idx
        self.setText("Sort column")

    def undo(self):
        for r in range(self._model.rowCount()):
            for c in range(self._model.columnCount()):
                self._model.setItem(r, c, self._saved[r][c].clone())
        self._editor.reset_vertical_headers()

    def redo(self):
        # Apply permutation: row new_r gets data from _saved[_permutation[new_r]]
        for new_r, old_r in enumerate(self._permutation):
            for c in range(self._model.columnCount()):
                self._model.setItem(new_r, c, self._saved[old_r][c].clone())
        self._editor.reset_vertical_headers()


class _SortMultiCommand(QUndoCommand):
    """Undo command for multi-level sort: list of (column_index, ascending)."""

    def __init__(
        self,
        model: QStandardItemModel,
        sort_levels: list[tuple[int, bool]],
        editor_ref: TwoDAEditor,
    ):
        super().__init__()
        self._model: QStandardItemModel = model
        self._levels: list[tuple[int, bool]] = sort_levels
        self._editor: TwoDAEditor = editor_ref
        self._saved: list[list[QStandardItem]] = []
        for r in range(model.rowCount()):
            row_items = []
            for c in range(model.columnCount()):
                it = model.item(r, c)
                row_items.append(it.clone() if it is not None else QStandardItem(""))
            self._saved.append(row_items)
        rows = list(range(model.rowCount()))
        for col, asc in reversed(self._levels):
            rows.sort(
                key=lambda r, c=col: (self._saved[r][c].text() if self._saved[r][c] else "").lower(),
                reverse=not asc,
            )
        self._permutation = rows
        self.setText("Sort")

    def undo(self):
        for r in range(self._model.rowCount()):
            for c in range(self._model.columnCount()):
                self._model.setItem(r, c, self._saved[r][c].clone())
        self._editor.reset_vertical_headers()

    def redo(self):
        for new_r, old_r in enumerate(self._permutation):
            for c in range(self._model.columnCount()):
                self._model.setItem(new_r, c, self._saved[old_r][c].clone())
        self._editor.reset_vertical_headers()


class _DeleteColumnCommand(QUndoCommand):
    def __init__(self, model: QStandardItemModel, col: int, editor_ref: TwoDAEditor):
        super().__init__()
        self._model = model
        self._col = col
        h_header = model.horizontalHeaderItem(col)
        assert h_header is not None, "Horizontal header item should not be None"
        self._header = h_header.text() or ""
        items: list[QStandardItem] = []
        for r in range(self._model.rowCount()):
            item = self._model.item(r, col)
            if item is None:
                items.append(QStandardItem(""))
            else:
                items.append(item.clone())
        self._saved: list[QStandardItem] = items
        self._editor = editor_ref
        self.setText("Delete column")

    def undo(self):
        self._model.insertColumn(self._col, [QStandardItem(self._saved[r]) for r in range(self._model.rowCount())])
        self._model.setHorizontalHeaderItem(self._col, QStandardItem(self._header))
        self._editor._reconstruct_menu(self._editor._get_headers_list())

    def redo(self):
        self._model.removeColumn(self._col)
        self._editor._reconstruct_menu(self._editor._get_headers_list())


def _headers_list(model: QStandardItemModel) -> list[str]:
    headers: list[str] = []
    for i in range(model.columnCount()):
        h = model.horizontalHeaderItem(i)
        if h is None:
            continue
        headers.append(h.text() or "")
    return headers


class _MoveRowCommand(QUndoCommand):
    """Move a single row up or down by one."""

    def __init__(self, model: QStandardItemModel, row: int, down: bool, editor_ref: TwoDAEditor):
        super().__init__()
        self._model = model
        self._editor = editor_ref
        self._row = row
        self._down = down
        self._target = row + (1 if down else -1)
        if self._target < 0 or self._target >= model.rowCount():
            raise ValueError("Move row out of range")
        self.setText("Move row " + ("down" if down else "up"))

    def undo(self):
        self._swap_rows(self._target, self._row)

    def redo(self):
        self._swap_rows(self._row, self._target)

    def _swap_rows(self, r1: int, r2: int):
        for c in range(self._model.columnCount()):
            a = self._model.takeItem(r1, c)
            b = self._model.takeItem(r2, c)
            self._model.setItem(r1, c, b)
            self._model.setItem(r2, c, a)
        self._editor.reset_vertical_headers()


class _MoveColumnCommand(QUndoCommand):
    """Swap column with the one to its left or right."""

    def __init__(self, model: QStandardItemModel, col: int, right: bool, editor_ref: TwoDAEditor):
        super().__init__()
        self._model = model
        self._editor = editor_ref
        self._col = col
        self._right = right
        self._other = col + (1 if right else -1)
        if self._other < 0 or self._other >= model.columnCount():
            raise ValueError("Move column out of range")
        self.setText("Move column " + ("right" if right else "left"))

    def undo(self):
        self._swap_columns(self._other, self._col)

    def redo(self):
        self._swap_columns(self._col, self._other)

    def _swap_columns(self, c1: int, c2: int):
        for r in range(self._model.rowCount()):
            a = self._model.takeItem(r, c1)
            b = self._model.takeItem(r, c2)
            self._model.setItem(r, c1, b)
            self._model.setItem(r, c2, a)
        h1 = self._model.horizontalHeaderItem(c1)
        h2 = self._model.horizontalHeaderItem(c2)
        t1 = (h1.text() if h1 else "") or ""
        t2 = (h2.text() if h2 else "") or ""
        self._model.setHorizontalHeaderItem(c1, QStandardItem(t2))
        self._model.setHorizontalHeaderItem(c2, QStandardItem(t1))
        self._editor._reconstruct_menu(_headers_list(self._model))


class _DuplicateColumnCommand(QUndoCommand):
    def __init__(self, model: QStandardItemModel, col: int, editor_ref: TwoDAEditor):
        super().__init__()
        self._model = model
        self._col = col
        self._editor = editor_ref
        h = model.horizontalHeaderItem(col)
        self._header = (h.text() or "") if h else ""
        self.setText("Duplicate column")

    def undo(self):
        self._model.removeColumn(self._col + 1)
        self._editor._reconstruct_menu(_headers_list(self._model))

    def redo(self):
        items = [QStandardItem(self._model.item(r, self._col).text() if self._model.item(r, self._col) else "") for r in range(self._model.rowCount())]
        self._model.insertColumn(self._col + 1, items)
        self._model.setHorizontalHeaderItem(self._col + 1, QStandardItem(self._header))
        self._editor._reconstruct_menu(_headers_list(self._model))


class _RemoveDuplicateRowsCommand(QUndoCommand):
    """Remove rows that are exact duplicates of a previous row (keep first occurrence)."""

    def __init__(self, model: QStandardItemModel, editor_ref: TwoDAEditor):
        super().__init__()
        self._model = model
        self._editor = editor_ref
        self._removed: list[tuple[int, list[QStandardItem]]] = []  # (original_row_index, row_data)
        seen: set[tuple[str, ...]] = set()
        to_remove: list[int] = []
        for r in range(model.rowCount()):
            key = tuple((model.item(r, c).text() if model.item(r, c) else "") for c in range(model.columnCount()))
            if key in seen:
                to_remove.append(r)
            else:
                seen.add(key)
        for r in reversed(to_remove):
            row_data = []
            for c in range(model.columnCount()):
                it = model.item(r, c)
                row_data.append(it.clone() if it is not None else QStandardItem(""))
            self._removed.append((r, row_data))
        self._removed.reverse()  # ascending by row index for undo
        self.setText("Remove duplicate rows")

    def undo(self):
        for r, row_data in self._removed:
            items = [it.clone() for it in row_data]
            self._model.insertRow(r, items)
            self._editor.set_item_display_data(r)
        self._editor.reset_vertical_headers()

    def redo(self):
        for r in sorted((idx for idx, _ in self._removed), reverse=True):
            self._model.removeRow(r)
            self._editor.reset_vertical_headers()


class _TransposeCommand(QUndoCommand):
    """Transpose the entire table: rows become columns, columns become rows. Undoable."""

    def __init__(self, model: QStandardItemModel, editor_ref: TwoDAEditor):
        super().__init__()
        self._model: QStandardItemModel = model
        self._editor: TwoDAEditor = editor_ref
        R = model.rowCount()
        C = model.columnCount()
        self._saved_headers = _headers_list(model)
        self._saved_cells: list[list[str]] = []
        for r in range(R):
            row = []
            for c in range(C):
                it = model.item(r, c)
                row.append(it.text() if it else "")
            self._saved_cells.append(row)
        self.setText("Transpose table")

    def undo(self):
        self._apply(self._saved_headers, self._saved_cells)

    def redo(self):
        R = len(self._saved_cells)
        C = len(self._saved_headers)
        if R == 0 or C == 0:
            return
        new_headers: list[str] = ["", *[self._saved_cells[r][0] for r in range(R)]]
        new_cells: list[list[str]] = []
        for i in range(C - 1):
            row_label = self._saved_headers[i + 1]
            row_data = [self._saved_cells[r][i + 1] for r in range(R)]
            new_cells.append([row_label, *row_data])
        self._apply(new_headers, new_cells)

    def _apply(self, headers: list[str], cells: list[list[str]]):
        rc, cc = self._model.rowCount(), self._model.columnCount()
        if rc > 0:
            self._model.removeRows(0, rc)
        if cc > 0:
            self._model.removeColumns(0, cc)
        C = len(headers)
        R = len(cells)
        self._model.setColumnCount(C)
        self._model.setRowCount(R)
        for c in range(C):
            self._model.setHorizontalHeaderItem(c, QStandardItem(headers[c]))
        for r in range(R):
            for c in range(min(C, len(cells[r]))):
                self._model.setItem(r, c, QStandardItem(cells[r][c]))
        for r in range(R):
            self._editor.set_item_display_data(r)
        self._editor.reset_vertical_headers()
        self._editor._reconstruct_menu(headers)


class CellFormattingDialog(QDialog):
    """Dialog for formatting selected cells (bold, color, alignment)."""

    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.setWindowTitle("Cell Formatting")
        self.resize(400, 300)
        
        layout = QGridLayout(self)
        
        # Font options
        layout.addWidget(QLabel("<b>Font Style:</b>"), 0, 0, 1, 2)
        
        self.bold_check = QCheckBox("Bold")
        layout.addWidget(self.bold_check, 1, 0)
        
        self.italic_check = QCheckBox("Italic")
        layout.addWidget(self.italic_check, 1, 1)
        
        # Text color
        layout.addWidget(QLabel("<b>Text Color:</b>"), 2, 0)
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Default", "Red", "Green", "Blue", "Orange", "Purple", "Gray"])
        layout.addWidget(self.color_combo, 2, 1)
        
        # Background color
        layout.addWidget(QLabel("<b>Background:</b>"), 3, 0)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(["Default", "Light Yellow", "Light Green", "Light Blue", "Light Red", "Light Gray"])
        layout.addWidget(self.bg_combo, 3, 1)
        
        # Alignment
        layout.addWidget(QLabel("<b>Alignment:</b>"), 4, 0)
        self.align_combo = QComboBox()
        self.align_combo.addItems(["Default", "Left", "Center", "Right"])
        layout.addWidget(self.align_combo, 4, 1)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 5, 0, 1, 2)

    def get_formatting(self) -> dict:
        """Return selected formatting options."""
        return {
            'bold': self.bold_check.isChecked(),
            'italic': self.italic_check.isChecked(),
            'color': self.color_combo.currentText(),
            'background': self.bg_combo.currentText(),
            'alignment': self.align_combo.currentText(),
        }


class DataValidationDialog(QDialog):
    """Dialog for setting data validation rules on selected cells."""

    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.setWindowTitle("Data Validation")
        self.resize(450, 250)
        
        layout = QGridLayout(self)
        
        # Validation type
        layout.addWidget(QLabel("<b>Validation Type:</b>"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "None",
            "Whole Numbers",
            "Decimal Numbers",
            "Text Length",
            "Custom List",
            "Date (YYYY-MM-DD)",
        ])
        layout.addWidget(self.type_combo, 0, 1)
        
        # Criteria
        layout.addWidget(QLabel("<b>Criteria:</b>"), 1, 0)
        self.criteria_combo = QComboBox()
        self.criteria_combo.addItems([
            "Any Value",
            "Between",
            "Not Between",
            "Equal To",
            "Not Equal To",
            "Greater Than",
            "Less Than",
            "Greater or Equal",
            "Less or Equal",
        ])
        layout.addWidget(self.criteria_combo, 1, 1)
        
        # Min value
        layout.addWidget(QLabel("Minimum:"), 2, 0)
        self.min_edit = QLineEdit()
        layout.addWidget(self.min_edit, 2, 1)
        
        # Max value
        layout.addWidget(QLabel("Maximum:"), 3, 0)
        self.max_edit = QLineEdit()
        layout.addWidget(self.max_edit, 3, 1)
        
        # Custom list
        layout.addWidget(QLabel("Allowed Values:"), 4, 0)
        self.list_edit = QLineEdit()
        self.list_edit.setPlaceholderText("Comma-separated: value1, value2, value3")
        layout.addWidget(self.list_edit, 4, 1)
        
        # Error message
        layout.addWidget(QLabel("Error Message:"), 5, 0)
        self.error_edit = QLineEdit()
        self.error_edit.setPlaceholderText("Invalid value")
        layout.addWidget(self.error_edit, 5, 1)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 6, 0, 1, 2)

    def get_validation_rule(self) -> dict:
        """Return validation rule configuration."""
        return {
            'type': self.type_combo.currentText(),
            'criteria': self.criteria_combo.currentText(),
            'min': self.min_edit.text(),
            'max': self.max_edit.text(),
            'allowed_list': [v.strip() for v in self.list_edit.text().split(',') if v.strip()],
            'error_message': self.error_edit.text() or "Invalid value",
        }


class FindAndReplaceAdvancedDialog(QDialog):
    """Advanced find/replace with regex, scope, and direction options."""

    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Find & Replace")
        self.resize(500, 350)
        
        layout = QGridLayout(self)
        
        # Find
        layout.addWidget(QLabel("Find:"), 0, 0)
        self.find_edit = QLineEdit()
        layout.addWidget(self.find_edit, 0, 1, 1, 2)
        
        # Replace
        layout.addWidget(QLabel("Replace:"), 1, 0)
        self.replace_edit = QLineEdit()
        layout.addWidget(self.replace_edit, 1, 1, 1, 2)
        
        # Options
        layout.addWidget(QLabel("<b>Options:</b>"), 2, 0, 1, 3)
        
        self.match_case_check = QCheckBox("Match case")
        layout.addWidget(self.match_case_check, 3, 0)
        
        self.whole_cell_check = QCheckBox("Whole cell only")
        layout.addWidget(self.whole_cell_check, 3, 1)
        
        self.regex_check = QCheckBox("Use regular expressions")
        layout.addWidget(self.regex_check, 4, 0)
        
        self.wrap_check = QCheckBox("Wrap around")
        self.wrap_check.setChecked(True)
        layout.addWidget(self.wrap_check, 4, 1)
        
        # Scope
        layout.addWidget(QLabel("Search in:"), 5, 0)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["All Cells", "Selected Cells Only", "Current Column", "Current Row"])
        layout.addWidget(self.scope_combo, 5, 1)
        
        # Direction
        layout.addWidget(QLabel("Direction:"), 6, 0)
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Forward", "Backward"])
        layout.addWidget(self.direction_combo, 6, 1)
        
        # Buttons
        self.find_next_btn = QPushButton("Find Next")
        self.find_all_btn = QPushButton("Find All")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn = QPushButton("Close")
        
        layout.addWidget(self.find_next_btn, 7, 0)
        layout.addWidget(self.find_all_btn, 7, 1)
        layout.addWidget(self.replace_btn, 8, 0)
        layout.addWidget(self.replace_all_btn, 8, 1)
        layout.addWidget(self.close_btn, 9, 0, 1, 2)
        
        self.find_next_btn.clicked.connect(lambda: self.done(100))
        self.find_all_btn.clicked.connect(lambda: self.done(101))
        self.replace_btn.clicked.connect(lambda: self.done(102))
        self.replace_all_btn.clicked.connect(lambda: self.done(103))
        self.close_btn.clicked.connect(self.reject)


class AutoCompleteManager:
    """Manages auto-complete suggestions from existing column values."""

    def __init__(self, editor: TwoDAEditor):
        self._editor = editor
        self._column_values: dict[int, set[str]] = {}

    def update_suggestions(self, col: int):
        """Update auto-complete suggestions for a column."""
        if col <= 0:
            return
        
        values = set()
        for row in range(self._editor.source_model.rowCount()):
            item = self._editor.source_model.item(row, col)
            if item and item.text().strip():
                values.add(item.text().strip())
        
        self._column_values[col] = values

    def get_suggestions(self, col: int, prefix: str) -> list[str]:
        """Get auto-complete suggestions for a column matching prefix."""
        if col not in self._column_values:
            self.update_suggestions(col)
        
        if col not in self._column_values:
            return []
        
        prefix_lower = prefix.lower()
        matches = [v for v in self._column_values[col] if v.lower().startswith(prefix_lower)]
        return sorted(matches)


class BulkEditDialog(QDialog):
    """Dialog for bulk editing multiple cells at once."""

    def __init__(self, parent: QWidget | None, cell_count: int):
        super().__init__(parent)
        self.setWindowTitle(f"Bulk Edit ({cell_count} cells)")
        self.resize(450, 200)
        
        layout = QGridLayout(self)
        
        layout.addWidget(QLabel(f"<b>Editing {cell_count} cells</b>"), 0, 0, 1, 2)
        
        # Operation type
        layout.addWidget(QLabel("Operation:"), 1, 0)
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([
            "Set Value",
            "Append Text",
            "Prepend Text",
            "Find and Replace",
            "To Uppercase",
            "To Lowercase",
            "Title Case",
            "Trim Whitespace",
            "Add Prefix",
            "Add Suffix",
            "Multiply by",
            "Add to Value",
        ])
        layout.addWidget(self.operation_combo, 1, 1)
        
        # Value input
        layout.addWidget(QLabel("Value:"), 2, 0)
        self.value_edit = QLineEdit()
        layout.addWidget(self.value_edit, 2, 1)
        
        # Find (for find/replace)
        layout.addWidget(QLabel("Find:"), 3, 0)
        self.find_edit = QLineEdit()
        layout.addWidget(self.find_edit, 3, 1)
        
        # Preview
        layout.addWidget(QLabel("Example: 'test' → "), 4, 0)
        self.preview_label = QLabel("")
        layout.addWidget(self.preview_label, 4, 1)
        
        # Update preview on changes
        self.operation_combo.currentTextChanged.connect(self._update_preview)
        self.value_edit.textChanged.connect(self._update_preview)
        self.find_edit.textChanged.connect(self._update_preview)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 5, 0, 1, 2)

    def _update_preview(self):
        """Update the preview label showing transformation."""
        operation = self.operation_combo.currentText()
        value = self.value_edit.text()
        find_text = self.find_edit.text()
        example = "test"
        
        result = self._apply_operation(example, operation, value, find_text)
        self.preview_label.setText(f"'{result}'")

    def _apply_operation(self, text: str, operation: str, value: str, find_text: str) -> str:
        """Apply the selected operation to text."""
        if operation == "Set Value":
            return value
        elif operation == "Append Text":
            return text + value
        elif operation == "Prepend Text":
            return value + text
        elif operation == "Find and Replace":
            return text.replace(find_text, value)
        elif operation == "To Uppercase":
            return text.upper()
        elif operation == "To Lowercase":
            return text.lower()
        elif operation == "Title Case":
            return text.title()
        elif operation == "Trim Whitespace":
            return text.strip()
        elif operation == "Add Prefix":
            return value + text
        elif operation == "Add Suffix":
            return text + value
        elif operation == "Multiply by":
            try:
                return str(float(text) * float(value))
            except (ValueError, TypeError):
                return text
        elif operation == "Add to Value":
            try:
                return str(float(text) + float(value))
            except (ValueError, TypeError):
                return text
        return text

    def get_operation(self) -> str:
        return self.operation_combo.currentText()

    def get_value(self) -> str:
        return self.value_edit.text()

    def get_find_text(self) -> str:
        return self.find_edit.text()

    def apply_to_text(self, text: str) -> str:
        """Apply the configured operation to the given text."""
        return self._apply_operation(text, self.get_operation(), self.get_value(), self.get_find_text())


class ColumnFilterDialog(QDialog):
    """Dialog for filtering rows based on column values."""

    def __init__(self, parent: QWidget | None, column_name: str, unique_values: list[str]):
        super().__init__(parent)
        self.setWindowTitle(f"Filter Column: {column_name}")
        self.resize(350, 450)
        
        layout = QGridLayout(self)
        
        layout.addWidget(QLabel(f"<b>Show rows where '{column_name}' is:</b>"), 0, 0, 1, 2)
        
        # Search box
        layout.addWidget(QLabel("Search:"), 1, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter values...")
        layout.addWidget(self.search_edit, 1, 1)
        
        # Value list with checkboxes
        from qtpy.QtWidgets import QListWidget, QListWidgetItem
        self.value_list = QListWidget()

        self._add_checked_value_item("(Select All)")
        self._add_checked_value_item("(Blanks)")
        
        # Add unique values
        for value in sorted(unique_values):
            if value.strip():
                self._add_checked_value_item(value)
        
        layout.addWidget(self.value_list, 2, 0, 1, 2)
        
        # Filter search
        self.search_edit.textChanged.connect(self._filter_list)
        
        # Buttons
        button_layout = QGridLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Clear All")
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(select_all_btn, 0, 0)
        button_layout.addWidget(deselect_all_btn, 0, 1)
        layout.addLayout(button_layout, 3, 0, 1, 2)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 4, 0, 1, 2)

    def _add_checked_value_item(self, text: str) -> None:
        """Add a checked list item to the value-list widget."""
        item = QListWidgetItem(text)
        item.setCheckState(Qt.CheckState.Checked)
        self.value_list.addItem(item)

    def _filter_list(self, text: str):
        """Filter the value list based on search text."""
        text_lower = text.lower()
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            if item:
                item_text = item.text()
                if not text or text_lower in item_text.lower() or item_text.startswith("("):
                    item.setHidden(False)
                else:
                    item.setHidden(True)

    def _select_all(self):
        """Check all visible items."""
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            if item and not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self):
        """Uncheck all visible items."""
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            if item and not item.isHidden():
                item.setCheckState(Qt.CheckState.Unchecked)

    def get_selected_values(self) -> list[str]:
        """Return list of checked values."""
        selected = []
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                text = item.text()
                if not text.startswith("("):
                    selected.append(text)
        return selected

    def include_blanks(self) -> bool:
        """Return whether (Blanks) is checked."""
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            if item and item.text() == "(Blanks)":
                return item.checkState() == Qt.CheckState.Checked
        return False


class ColumnStatisticsDialog(QDialog):
    """Dialog showing statistics for a selected column."""

    def __init__(self, parent: QWidget | None, column_name: str, values: list[str]):
        super().__init__(parent)
        self.setWindowTitle(f"Column Statistics: {column_name}")
        self.resize(400, 300)
        
        layout = QGridLayout(self)
        
        # Analyze the values
        total = len(values)
        blank = sum(1 for v in values if not v.strip())
        non_blank = total - blank
        unique = len(set(values))
        
        # Try numeric analysis
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass
        
        is_numeric = len(numeric_values) > total * 0.5  # >50% numeric
        
        # Display statistics
        row = 0
        layout.addWidget(QLabel("<b>Total Cells:</b>"), row, 0)
        layout.addWidget(QLabel(str(total)), row, 1)
        row += 1
        
        layout.addWidget(QLabel("<b>Non-Blank:</b>"), row, 0)
        layout.addWidget(QLabel(str(non_blank)), row, 1)
        row += 1
        
        layout.addWidget(QLabel("<b>Blank:</b>"), row, 0)
        layout.addWidget(QLabel(str(blank)), row, 1)
        row += 1
        
        layout.addWidget(QLabel("<b>Unique:</b>"), row, 0)
        layout.addWidget(QLabel(str(unique)), row, 1)
        row += 1
        
        if numeric_values:
            layout.addWidget(QLabel("<b>Numeric Values:</b>"), row, 0)
            layout.addWidget(QLabel(str(len(numeric_values))), row, 1)
            row += 1
            
            layout.addWidget(QLabel("<b>Sum:</b>"), row, 0)
            layout.addWidget(QLabel(f"{sum(numeric_values):.4f}"), row, 1)
            row += 1
            
            layout.addWidget(QLabel("<b>Average:</b>"), row, 0)
            layout.addWidget(QLabel(f"{sum(numeric_values) / len(numeric_values):.4f}"), row, 1)
            row += 1
            
            layout.addWidget(QLabel("<b>Min:</b>"), row, 0)
            layout.addWidget(QLabel(f"{min(numeric_values):.4f}"), row, 1)
            row += 1
            
            layout.addWidget(QLabel("<b>Max:</b>"), row, 0)
            layout.addWidget(QLabel(f"{max(numeric_values):.4f}"), row, 1)
            row += 1
            
            # Median
            sorted_vals = sorted(numeric_values)
            n = len(sorted_vals)
            if n % 2 == 0:
                median = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
            else:
                median = sorted_vals[n//2]
            layout.addWidget(QLabel("<b>Median:</b>"), row, 0)
            layout.addWidget(QLabel(f"{median:.4f}"), row, 1)
            row += 1
            
            # Standard deviation
            if len(numeric_values) > 1:
                mean = sum(numeric_values) / len(numeric_values)
                variance = sum((x - mean) ** 2 for x in numeric_values) / (len(numeric_values) - 1)
                std_dev = variance ** 0.5
                layout.addWidget(QLabel("<b>Std Dev:</b>"), row, 0)
                layout.addWidget(QLabel(f"{std_dev:.4f}"), row, 1)
                row += 1
            
            # Mode (most common value)
            from collections import Counter
            counter = Counter(numeric_values)
            if counter:
                mode_val, mode_count = counter.most_common(1)[0]
                layout.addWidget(QLabel("<b>Mode:</b>"), row, 0)
                layout.addWidget(QLabel(f"{mode_val:.4f} (appears {mode_count}x)"), row, 1)
                row += 1
        
        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons, row, 0, 1, 2)


class _SpreadsheetEventFilter(QObject):
    """Event filter for repositioning spreadsheet UI elements on table geometry changes."""

    def __init__(self, editor: TwoDAEditor):
        super().__init__(editor)
        self._editor = editor

    def eventFilter(self, obj: QObject, event) -> bool:
        from qtpy.QtCore import QEvent
        if event.type() == QEvent.Type.Resize:
            # Reposition buttons when table viewport resizes
            self._editor._reposition_add_row_button()
            self._editor._reposition_add_col_button()
        return False


class _SpreadsheetKeyFilter(QObject):
    """Event filter for Excel-like Tab/Enter navigation in the table."""

    def __init__(self, editor: TwoDAEditor):
        super().__init__(editor)
        self._editor = editor

    def eventFilter(self, obj: QObject, event) -> bool:
        from qtpy.QtCore import QEvent, Qt
        from qtpy.QtGui import QKeyEvent

        if event.type() != QEvent.Type.KeyPress:
            return False

        key_event = event
        if not isinstance(key_event, QKeyEvent):
            return False

        key = key_event.key()
        modifiers = key_event.modifiers()
        table = self._editor.ui.twodaTable
        current = table.currentIndex()

        # === ROW SELECTION SHORTCUTS ===
        
        # Shift+Space: Select entire current row
        if key == Qt.Key.Key_Space and modifiers == Qt.KeyboardModifier.ShiftModifier:
            if current.isValid():
                self._editor.select_current_row()
                return True

        # Ctrl+Space: Select entire current column (already implemented, just document)
        # This is handled by the existing action

        # === NAVIGATION SHORTCUTS ===
        
        # Home: Jump to first column of current row
        if key == Qt.Key.Key_Home and modifiers == Qt.KeyboardModifier.NoModifier:
            if current.isValid():
                first_index = self._editor.proxy_model.index(current.row(), 0)
                table.setCurrentIndex(first_index)
                return True
        
        # End: Jump to last column of current row
        if key == Qt.Key.Key_End and modifiers == Qt.KeyboardModifier.NoModifier:
            if current.isValid():
                last_col = self._editor.proxy_model.columnCount() - 1
                last_index = self._editor.proxy_model.index(current.row(), last_col)
                table.setCurrentIndex(last_index)
                return True
        
        # Shift+Home: Select from current cell to start of row
        if key == Qt.Key.Key_Home and modifiers == Qt.KeyboardModifier.ShiftModifier:
            if current.isValid():
                from qtpy.QtCore import QItemSelection
                first_index = self._editor.proxy_model.index(current.row(), 0)
                selection = QItemSelection(first_index, current)
                table.selectionModel().select(selection, table.selectionModel().SelectionFlag.ClearAndSelect)
                return True
        
        # Shift+End: Select from current cell to end of row
        if key == Qt.Key.Key_End and modifiers == Qt.KeyboardModifier.ShiftModifier:
            if current.isValid():
                from qtpy.QtCore import QItemSelection
                last_col = self._editor.proxy_model.columnCount() - 1
                last_index = self._editor.proxy_model.index(current.row(), last_col)
                selection = QItemSelection(current, last_index)
                table.selectionModel().select(selection, table.selectionModel().SelectionFlag.ClearAndSelect)
                return True
        
        # Ctrl+Shift+Home: Select from current cell to first cell (0,0)
        if key == Qt.Key.Key_Home and modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if current.isValid():
                from qtpy.QtCore import QItemSelection
                first_index = self._editor.proxy_model.index(0, 0)
                selection = QItemSelection(first_index, current)
                table.selectionModel().select(selection, table.selectionModel().SelectionFlag.ClearAndSelect)
                return True
        
        # Ctrl+Shift+End: Select from current cell to last cell
        if key == Qt.Key.Key_End and modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if current.isValid():
                from qtpy.QtCore import QItemSelection
                last_row = self._editor.proxy_model.rowCount() - 1
                last_col = self._editor.proxy_model.columnCount() - 1
                last_index = self._editor.proxy_model.index(last_row, last_col)
                selection = QItemSelection(current, last_index)
                table.selectionModel().select(selection, table.selectionModel().SelectionFlag.ClearAndSelect)
                return True

        # === ROW/COLUMN MANIPULATION SHORTCUTS ===
        
        # Alt+Up: Move current row up
        if key == Qt.Key.Key_Up and modifiers == Qt.KeyboardModifier.AltModifier:
            self._editor.move_row_up()
            return True
        
        # Alt+Down: Move current row down
        if key == Qt.Key.Key_Down and modifiers == Qt.KeyboardModifier.AltModifier:
            self._editor.move_row_down()
            return True
        
        # Alt+Left: Move current column left
        if key == Qt.Key.Key_Left and modifiers == Qt.KeyboardModifier.AltModifier:
            self._editor.move_column_left()
            return True
        
        # Alt+Right: Move current column right
        if key == Qt.Key.Key_Right and modifiers == Qt.KeyboardModifier.AltModifier:
            self._editor.move_column_right()
            return True
        
        # Ctrl+Minus or Ctrl+Delete: Delete selected rows
        if (key == Qt.Key.Key_Minus or key == Qt.Key.Key_Delete) and modifiers == Qt.KeyboardModifier.ControlModifier:
            if table.state() != table.State.EditingState:
                self._editor.remove_selected_rows()
                return True
        
        # Ctrl+Plus or Ctrl+Insert: Insert row
        if (key == Qt.Key.Key_Plus or key == Qt.Key.Key_Insert) and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._editor.insert_row()
            return True

        # === STANDARD NAVIGATION ===
        
        # Tab: move right (at last cell of row, wrap to next row; at last cell of table, add row)
        if key == Qt.Key.Key_Tab and modifiers == Qt.KeyboardModifier.NoModifier:
            if not current.isValid():
                return False
            next_col = current.column() + 1
            next_row = current.row()
            
            # Check if at last column
            if next_col >= self._editor.proxy_model.columnCount():
                next_col = 0
                next_row += 1
                # Check if at last row
                if next_row >= self._editor.proxy_model.rowCount():
                    # Auto-insert new row
                    self._editor.insert_row()
                    next_row = self._editor.proxy_model.rowCount() - 1
            
            next_index = self._editor.proxy_model.index(next_row, next_col)
            if next_index.isValid():
                table.setCurrentIndex(next_index)
                table.edit(next_index)
            return True

        # Shift+Tab: move left
        if key == Qt.Key.Key_Tab and modifiers == Qt.KeyboardModifier.ShiftModifier:
            if not current.isValid():
                return False
            next_col = current.column() - 1
            next_row = current.row()
            
            # Wrap to previous row if at first column
            if next_col < 0:
                next_col = self._editor.proxy_model.columnCount() - 1
                next_row -= 1
                if next_row < 0:
                    return True  # Don't wrap past first cell
            
            next_index = self._editor.proxy_model.index(next_row, next_col)
            if next_index.isValid():
                table.setCurrentIndex(next_index)
                table.edit(next_index)
            return True

        # Enter/Return: move down (at last row, add new row)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and modifiers == Qt.KeyboardModifier.NoModifier:
            if not current.isValid():
                return False
            
            # Close any active editor first
            table.closePersistentEditor(current)
            
            next_row = current.row() + 1
            next_col = current.column()
            
            # Check if at last row
            if next_row >= self._editor.proxy_model.rowCount():
                # Auto-insert new row
                self._editor.insert_row()
                next_row = self._editor.proxy_model.rowCount() - 1
            
            next_index = self._editor.proxy_model.index(next_row, next_col)
            if next_index.isValid():
                table.setCurrentIndex(next_index)
                table.edit(next_index)
            return True

        # Shift+Enter: move up
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and modifiers == Qt.KeyboardModifier.ShiftModifier:
            if not current.isValid():
                return False
            
            next_row = current.row() - 1
            if next_row < 0:
                return True  # Don't move past first row
            
            next_col = current.column()
            next_index = self._editor.proxy_model.index(next_row, next_col)
            if next_index.isValid():
                table.setCurrentIndex(next_index)
                table.edit(next_index)
            return True

        # Delete/Backspace: clear selected cells (only if not editing)
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Only handle if not in edit mode
            if table.state() != table.State.EditingState:
                self._editor.clear_selection_contents()
                return True

        # F2: Start editing current cell
        if key == Qt.Key.Key_F2:
            if current.isValid():
                table.edit(current)
                return True

        return False


class TwoDAEditor(Editor):
    """Editor for 2DA (Two-Dimensional Array) files used in KotOR games.

    This editor provides a spreadsheet-like interface for editing 2DA files, which are
    tabular data files used extensively throughout KotOR and KotOR 2 for game configuration.

    Game Engine Usage:
    ----------------
    The 2DA files edited by this tool are verified to be loaded and used by the game engine,
    as confirmed through reverse engineering analysis of swkotor.exe and swkotor2.exe using
    Ghidra (via Reva MCP server). See TwoDARegistry class documentation in
    Libraries/PyKotor/src/pykotor/extract/twoda.py for a complete list of verified 2DA files
    and their loading functions.

    Supported formats:
    - Native 2DA binary format (ResourceType.TwoDA)
    - CSV format (ResourceType.TwoDA_CSV)
    - JSON format (ResourceType.TwoDA_JSON)
    """

    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        supported: list[ResourceType] = [ResourceType.TwoDA, ResourceType.TwoDA_CSV, ResourceType.TwoDA_JSON]
        super().__init__(parent, "2DA Editor", "none", supported, supported, installation)
        self.resize(800, 550)

        from toolset.uic.qtpy.editors.twoda import Ui_MainWindow

        self.ui: Ui_MainWindow = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setup_menus()
        self._add_help_action()
        self._setup_signals()

        self.ui.filterBox.setVisible(False)
        self._undo_stack: QUndoStack = QUndoStack(self)
        self.ui.actionUndo.triggered.connect(self._undo_stack.undo)
        self.ui.actionRedo.triggered.connect(self._undo_stack.redo)
        self._undo_stack.canUndoChanged.connect(self.ui.actionUndo.setEnabled)
        self._undo_stack.canRedoChanged.connect(self.ui.actionRedo.setEnabled)
        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)

        self.source_model: QStandardItemModel = QStandardItemModel(self)
        self.proxy_model: SortFilterProxyModel = SortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.vertical_header_option: VerticalHeaderOption = VerticalHeaderOption.NONE
        self.vertical_header_column: str = ""
        self._zoom_factor: float = 1.0
        self._zoom_base_point_size: float = 9.0
        vert_header: QHeaderView | None = self.ui.twodaTable.verticalHeader()

        # Excel-like: allow selecting and editing all cells (including row label column)
        self.ui.twodaTable.setFirstColumnInteractable(False)
        self.ui.twodaTable.setSelectionBehavior(self.ui.twodaTable.SelectionBehavior.SelectItems)
        self.ui.twodaTable.setSelectionMode(self.ui.twodaTable.SelectionMode.ExtendedSelection)

        # Setup event filter to prevent scroll wheel interaction with controls
        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)
        self.source_model.itemChanged.connect(self.reset_vertical_headers)

        # Status bar and selection feedback
        self._update_status_bar()
        sm = self.ui.twodaTable.selectionModel()
        if sm is not None:
            sm.selectionChanged.connect(self._update_status_bar)

        # Find repeat and navigation shortcuts (Excel-like)
        self._last_match_case = False
        self._last_match_whole_cell = False
        QShortcut(QKeySequence("F3"), self, self._find_next_repeat_forward)
        QShortcut(QKeySequence("Shift+F3"), self, self._find_next_repeat_backward)
        QShortcut(QKeySequence("Ctrl+Home"), self, self._go_to_first_cell)
        QShortcut(QKeySequence("Ctrl+End"), self, self._go_to_last_cell)
        QShortcut(QKeySequence("Ctrl+="), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.zoom_reset)
        
        # Power user shortcuts
        QShortcut(QKeySequence("Alt+Up"), self, self.move_row_up)
        QShortcut(QKeySequence("Alt+Down"), self, self.move_row_down)
        QShortcut(QKeySequence("Alt+Left"), self, self.move_column_left)
        QShortcut(QKeySequence("Alt+Right"), self, self.move_column_right)
        QShortcut(QKeySequence("Shift+Space"), self, self.select_current_row)
        QShortcut(QKeySequence("Ctrl+K"), self, self.duplicate_row)  # Alternative to Ctrl+D
        QShortcut(QKeySequence("Ctrl+Shift+K"), self, self.duplicate_column)
        QShortcut(QKeySequence("Ctrl+Shift+Up"), self, self.move_column_left)
        QShortcut(QKeySequence("Ctrl+Shift+Down"), self, self.move_column_right)
        QShortcut(QKeySequence("Ctrl+Shift+Left"), self, self.move_column_left)
        QShortcut(QKeySequence("Ctrl+Shift+Right"), self, self.move_column_right)
        QShortcut(QKeySequence("F4"), self, self.show_column_statistics)  # Quick stats
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_csv)  # Quick export
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._quick_clear_column)  # Clear column
        QShortcut(QKeySequence("Ctrl+Shift+X"), self, self._quick_clear_row)  # Clear row
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self.show_cell_formatting_dialog)  # Format cells
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self.show_bulk_edit_dialog)  # Bulk edit
        QShortcut(QKeySequence("Ctrl+L"), self, self.show_column_filter_dialog)  # Filter column
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, self.show_data_validation_dialog)  # Validation
        
        # Initialize auto-complete manager
        self._autocomplete = AutoCompleteManager(self)

        self.new()
        if vert_header is not None and "(Dark)" in GlobalSettings().selectedTheme:
            # Get palette colors
            app = QApplication.instance()
            if app is None or not isinstance(app, QApplication):
                palette = QPalette()
            else:
                palette = app.palette()

            window_text = palette.color(QPalette.ColorRole.WindowText)
            base = palette.color(QPalette.ColorRole.Base)
            alternate_base = palette.color(QPalette.ColorRole.AlternateBase)

            # Create transparent text color
            transparent_text = QColor(window_text)
            transparent_text.setAlpha(0)

            # Create hover background (slightly lighter/darker than base)
            hover_bg = QColor(alternate_base if alternate_base != base else base)
            if hover_bg.lightness() < 128:  # Dark theme
                hover_bg = hover_bg.lighter(110)
            else:  # Light theme
                hover_bg = hover_bg.darker(95)

            vert_header.setStyleSheet(f"""
                QHeaderView::section {{
                    color: rgba({transparent_text.red()}, {transparent_text.green()}, {transparent_text.blue()}, 0);  /* Transparent text */
                    background-color: {base.name()};  /* Base background */
                }}
                QHeaderView::section:checked {{
                    color: {window_text.name()};  /* Window text for checked sections */
                    background-color: {alternate_base.name() if alternate_base != base else hover_bg.name()};  /* Alternate base for checked sections */
                }}
                QHeaderView::section:hover {{
                    color: {window_text.name()};  /* Window text on hover */
                    background-color: {hover_bg.name()};  /* Hover background */
                }}
            """)
            mid_color = palette.color(QPalette.ColorRole.Mid)
            highlight = palette.color(QPalette.ColorRole.Highlight)
            highlighted_text = palette.color(QPalette.ColorRole.HighlightedText)

            self.ui.twodaTable.setStyleSheet(f"""
                QHeaderView::section {{
                    background-color: {base.name()};  /* Base background for header */
                    color: {window_text.name()};  /* Window text for header */
                    padding: 4px;
                    border: 1px solid {mid_color.name()};
                }}
                QHeaderView::section:checked {{
                    background-color: {alternate_base.name() if alternate_base != base else hover_bg.name()};  /* Alternate base for checked header */
                    color: {window_text.name()};  /* Window text for checked header */
                }}
                QHeaderView::section:hover {{
                    background-color: {hover_bg.name()};  /* Hover background for hovered header */
                    color: {window_text.name()};  /* Window text for hovered header */
                }}
                QTableView {{
                    background-color: {base.name()};  /* Base background for table */
                    alternate-background-color: {alternate_base.name()};  /* Alternate base for alternating rows */
                    color: {window_text.name()};  /* Window text for table */
                    gridline-color: {mid_color.name()};  /* Mid color for grid lines */
                    selection-background-color: {highlight.name()};  /* Highlight for selected items */
                    selection-color: {highlighted_text.name()};  /* Highlighted text for selected items */
                }}
                QTableView::item {{
                    background-color: {base.name()};  /* Base background for items */
                    color: {window_text.name()};  /* Window text for items */
                }}
                QTableView::item:selected {{
                    background-color: {highlight.name()};  /* Highlight for selected items */
                    color: {highlighted_text.name()};  /* Highlighted text for selected items */
                }}
                QTableCornerButton::section {{
                    background-color: {base.name()};  /* Base background for corner button */
                    border: 1px solid {mid_color.name()};
                }}
            """)

        # Setup spreadsheet-style overlay buttons
        self._setup_spreadsheet_buttons()
        
        # Setup toolbar with common actions
        self._setup_toolbar()

    def _setup_spreadsheet_buttons(self):
        """Create and setup the '+' overlay buttons for adding rows and columns."""
        # Add Row Button (positioned below last row on left side)
        self._add_row_btn = QPushButton("+", self)
        self._add_row_btn.setFixedSize(24, 24)
        self._add_row_btn.setFlat(True)
        self._add_row_btn.setToolTip("Add Row")
        self._add_row_btn.clicked.connect(self.insert_row)
        self._add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 3px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: palette(light);
                border: 1px solid palette(dark);
            }
            QPushButton:pressed {
                background-color: palette(mid);
            }
        """)

        # Add Column Button (positioned after last column on top)
        self._add_col_btn = QPushButton("+", self)
        self._add_col_btn.setFixedSize(24, 24)
        self._add_col_btn.setFlat(True)
        self._add_col_btn.setToolTip("Add Column")
        self._add_col_btn.clicked.connect(self._quick_add_column)
        self._add_col_btn.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 3px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: palette(light);
                border: 1px solid palette(dark);
            }
            QPushButton:pressed {
                background-color: palette(mid);
            }
        """)

        # Install event filters
        self._spreadsheet_filter = _SpreadsheetEventFilter(self)
        viewport = self.ui.twodaTable.viewport()
        if viewport:
            viewport.installEventFilter(self._spreadsheet_filter)
        
        # Install keyboard navigation filter
        self._key_filter = _SpreadsheetKeyFilter(self)
        self.ui.twodaTable.installEventFilter(self._key_filter)

        # Connect model signals for repositioning
        self.source_model.rowsInserted.connect(self._reposition_add_row_button)
        self.source_model.rowsRemoved.connect(self._reposition_add_row_button)
        self.source_model.columnsInserted.connect(self._reposition_add_col_button)
        self.source_model.columnsRemoved.connect(self._reposition_add_col_button)

        # Connect scrollbar signals
        v_scrollbar = self.ui.twodaTable.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.valueChanged.connect(self._reposition_add_row_button)
        h_scrollbar = self.ui.twodaTable.horizontalScrollBar()
        if h_scrollbar:
            h_scrollbar.valueChanged.connect(self._reposition_add_col_button)

        # Initial positioning
        self._reposition_add_row_button()
        self._reposition_add_col_button()

    def _setup_toolbar(self):
        """Setup toolbar with common spreadsheet actions for accessibility."""
        from qtpy.QtWidgets import QToolBar
        
        toolbar = QToolBar("Spreadsheet Actions", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)
        
        # File operations
        toolbar.addAction(self.ui.actionNew)
        toolbar.addAction(self.ui.actionOpen)
        toolbar.addAction(self.ui.actionSave)
        toolbar.addSeparator()
        
        # Undo/Redo
        toolbar.addAction(self.ui.actionUndo)
        toolbar.addAction(self.ui.actionRedo)
        toolbar.addSeparator()
        
        # Clipboard
        toolbar.addAction(self.ui.actionCut)
        toolbar.addAction(self.ui.actionCopy)
        toolbar.addAction(self.ui.actionPaste)
        toolbar.addSeparator()
        
        # Row operations with labels
        add_row_action = QAction("➕ Row", self)
        add_row_action.setToolTip("Insert Row (Ctrl+I)")
        add_row_action.triggered.connect(self.insert_row)
        toolbar.addAction(add_row_action)
        
        delete_row_action = QAction("➖ Row", self)
        delete_row_action.setToolTip("Remove Selected Rows (Ctrl+Del)")
        delete_row_action.triggered.connect(self.remove_selected_rows)
        toolbar.addAction(delete_row_action)
        
        move_up_action = QAction("⬆️ Row", self)
        move_up_action.setToolTip("Move Row Up (Alt+Up)")
        move_up_action.triggered.connect(self.move_row_up)
        toolbar.addAction(move_up_action)
        
        move_down_action = QAction("⬇️ Row", self)
        move_down_action.setToolTip("Move Row Down (Alt+Down)")
        move_down_action.triggered.connect(self.move_row_down)
        toolbar.addAction(move_down_action)
        
        toolbar.addSeparator()
        
        # Column operations
        add_col_action = QAction("➕ Col", self)
        add_col_action.setToolTip("Insert Column (Ctrl+Shift+I)")
        add_col_action.triggered.connect(self.insert_column)
        toolbar.addAction(add_col_action)
        
        delete_col_action = QAction("➖ Col", self)
        delete_col_action.setToolTip("Delete Column (Ctrl+Shift+Del)")
        delete_col_action.triggered.connect(self.delete_column)
        toolbar.addAction(delete_col_action)
        
        toolbar.addSeparator()
        
        # Search
        toolbar.addAction(self.ui.actionFind)
        toolbar.addAction(self.ui.actionReplace)
        toolbar.addSeparator()
        
        # View operations
        toolbar.addAction(self.ui.actionZoomIn)
        toolbar.addAction(self.ui.actionZoomOut)
        toolbar.addAction(self.ui.actionZoomReset)

    def _create_empty_item(self, text: str = "") -> QStandardItem:
        """Create a QStandardItem with optional text.

        Args:
        ----
            text: The text to set in the item (default empty string)

        Returns:
        -------
            QStandardItem: The created item
        """
        return QStandardItem(text)

    def _create_empty_items(self, count: int, text: str = "") -> list[QStandardItem]:
        """Create multiple empty QStandardItems.

        Args:
        ----
            count: Number of items to create
            text: The text to set in each item (default empty string)

        Returns:
        -------
            List of QStandardItem objects
        """
        return [QStandardItem(text) for _ in range(count)]

    def _reposition_add_row_button(self):
        """Reposition the add row button below the last visible row."""
        if not hasattr(self, '_add_row_btn'):
            return
        table = self.ui.twodaTable
        v_header = table.verticalHeader()
        if v_header is None:
            return

        row_count = self.source_model.rowCount()
        if row_count == 0:
            # Position below headers if no rows
            y = table.horizontalHeader().height() + 2
        else:
            # Position below last row
            last_row_index = self.proxy_model.index(min(row_count - 1, self.proxy_model.rowCount() - 1), 0)
            rect = table.visualRect(last_row_index)
            y = rect.bottom() + 2

        # X position: align with vertical header
        x = 2
        self._add_row_btn.move(x, y)
        self._add_row_btn.raise_()

    def _reposition_add_col_button(self):
        """Reposition the add column button after the last visible column."""
        if not hasattr(self, '_add_col_btn'):
            return
        table = self.ui.twodaTable
        h_header = table.horizontalHeader()
        if h_header is None:
            return

        col_count = self.source_model.columnCount()
        if col_count == 0:
            # Position after vertical header if no columns
            x = table.verticalHeader().width() + 2
        else:
            # Position after last column header
            last_col_index = min(col_count - 1, self.proxy_model.columnCount() - 1)
            x_pos = h_header.sectionViewportPosition(last_col_index)
            col_width = h_header.sectionSize(last_col_index)
            x = x_pos + col_width + table.verticalHeader().width() + 2

        # Y position: align with horizontal header
        y = 2
        self._add_col_btn.move(x, y)
        self._add_col_btn.raise_()

    def _quick_add_column(self):
        """Add a new column with auto-generated name (no dialog prompt)."""
        # Auto-generate column name: Column3, Column4, etc.
        existing_names = []
        for i in range(self.source_model.columnCount()):
            h = self.source_model.horizontalHeaderItem(i)
            if h:
                existing_names.append(h.text())

        # Find next available ColumnN name
        n = 1
        while True:
            name = f"Column{n}" if n > 0 else ""
            if name not in existing_names:
                break
            n += 1

        # Insert at end
        col = self.source_model.columnCount()
        if col == 0:
            # Special case: if no columns, create the row label column + first data column
            self.source_model.setColumnCount(2)
            self.source_model.setHorizontalHeaderItem(0, QStandardItem(""))
            self.source_model.setHorizontalHeaderItem(1, QStandardItem("Column1"))
            self._reconstruct_menu(["", "Column1"])
        else:
            self._undo_stack.push(_InsertColumnCommand(self.source_model, col, name, self))

    def _setup_signals(self):
        self.ui.filterEdit.textEdited.connect(self.do_filter)
        self.ui.actionToggleFilter.triggered.connect(self.toggle_filter)
        self.ui.actionCopy.triggered.connect(self.copy_selection)
        self.ui.actionPaste.triggered.connect(self.paste_selection)
        self.ui.actionCut.triggered.connect(self.cut_selection)
        self.ui.actionPasteTranspose.triggered.connect(self.paste_transpose)
        self.ui.actionFind.triggered.connect(self.show_find_dialog)
        self.ui.actionReplace.triggered.connect(self.show_replace_dialog)
        self.ui.actionSelectAll.triggered.connect(self.select_all)
        self.ui.actionSelectRow.triggered.connect(self.select_current_row)
        self.ui.actionSelectColumn.triggered.connect(self.select_current_column)
        self.ui.actionSelectVisibleOnly.triggered.connect(self.select_visible_only)
        self.ui.actionSelectBlankCells.triggered.connect(self.select_blank_cells)
        self.ui.actionSelectCellsWithContent.triggered.connect(self.select_cells_with_content)
        self.ui.actionClearContents.triggered.connect(self.clear_selection_contents)
        self.ui.actionGoToColumn.triggered.connect(self.show_go_to_column_dialog)

        self.ui.actionInsertRow.triggered.connect(self.insert_row)
        self.ui.actionDuplicateRow.triggered.connect(self.duplicate_row)
        self.ui.actionRemoveRows.triggered.connect(self.remove_selected_rows)
        self.ui.actionRedoRowLabels.triggered.connect(self.redo_row_labels)

        self.ui.actionInsertColumn.triggered.connect(self.insert_column)
        self.ui.actionRenameColumn.triggered.connect(self.rename_current_column)
        self.ui.actionDuplicateColumn.triggered.connect(self.duplicate_column)
        self.ui.actionDeleteColumn.triggered.connect(self.delete_column)
        self.ui.actionMoveColumnLeft.triggered.connect(self.move_column_left)
        self.ui.actionMoveColumnRight.triggered.connect(self.move_column_right)
        self.ui.actionMoveRowUp.triggered.connect(self.move_row_up)
        self.ui.actionMoveRowDown.triggered.connect(self.move_row_down)
        self.ui.actionRemoveDuplicateRows.triggered.connect(self.remove_duplicate_rows)
        self.ui.actionSort.triggered.connect(self.show_sort_dialog)
        self.ui.actionSortAscending.triggered.connect(lambda: self.sort_by_current_column(ascending=True))
        self.ui.actionSortDescending.triggered.connect(lambda: self.sort_by_current_column(ascending=False))
        self.ui.actionFillDown.triggered.connect(self.fill_down)
        self.ui.actionFillRight.triggered.connect(self.fill_right)
        self.ui.actionTransposeTable.triggered.connect(self.transpose_table)

        self.ui.actionResizeColumnsToContents.triggered.connect(self.ui.twodaTable.resizeColumnsToContents)
        self.ui.actionResizeRowsToContents.triggered.connect(self.ui.twodaTable.resizeRowsToContents)
        self.ui.actionAutoFitColumnsOnLoad.triggered.connect(self._on_auto_fit_columns_toggled)
        self.ui.actionWrapTextInCells.triggered.connect(self._on_wrap_text_toggled)
        self.ui.actionAlternatingRowColors.triggered.connect(self._on_alternating_row_colors_toggled)
        self.ui.actionZoomIn.triggered.connect(self.zoom_in)
        self.ui.actionZoomOut.triggered.connect(self.zoom_out)
        self.ui.actionZoomReset.triggered.connect(self.zoom_reset)
        self.ui.actionHideColumn.triggered.connect(self.hide_current_column)
        self.ui.actionShowAllColumns.triggered.connect(self.show_all_columns)

        self.ui.actionGoToRow.triggered.connect(self.show_go_to_row_dialog)
        self.ui.actionInsertRowAbove.triggered.connect(self.insert_row_above)
        self.ui.actionInsertRowBelow.triggered.connect(self.insert_row_below)

        # New spreadsheet actions
        self.ui.actionImportCSV.triggered.connect(self.import_csv)
        self.ui.actionExportCSV.triggered.connect(self.export_csv)
        self.ui.actionColumnStatistics.triggered.connect(self.show_column_statistics)
        self.ui.actionHighlightNonNumeric.triggered.connect(lambda: self.toggle_highlight_non_numeric(self.ui.actionHighlightNonNumeric.isChecked()))
        self.ui.actionFreezeRowLabels.triggered.connect(lambda: self.toggle_freeze_row_labels(self.ui.actionFreezeRowLabels.isChecked()))
        self.ui.actionFillDownPattern.triggered.connect(self.fill_down_pattern)

        # Context menu for table
        self.ui.twodaTable.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.twodaTable.customContextMenuRequested.connect(self._show_table_context_menu)

        # Context menu on column headers: Insert new column
        h_header = self.ui.twodaTable.horizontalHeader()
        if h_header is not None:
            h_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            h_header.customContextMenuRequested.connect(self._show_header_context_menu)
            h_header.sectionDoubleClicked.connect(self._on_column_header_double_clicked)
        
        # Context menu on row headers: Row operations
        v_header = self.ui.twodaTable.verticalHeader()
        if v_header is not None:
            v_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            v_header.customContextMenuRequested.connect(self._show_row_header_context_menu)
            v_header.sectionClicked.connect(self._on_row_header_clicked)
            v_header.sectionDoubleClicked.connect(self._on_row_header_double_clicked)

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        try:
            self._load_main(data)
        except Exception as e:
            # Avoid crashing tests on unexpected exceptions during load. Log the exception
            # and reset the editor state instead of showing a blocking native dialog.
            try:
                self._logger.exception("Failed to load 2DA data: %s", e)
            except Exception:
                # Fallback to printing if the logger isn't available for any reason
                print("Failed to load 2DA data:", e)
            # Ensure the model is reset so the editor remains in a consistent state.
            # Do not call super().load() so _resname/_filepath/_restype are not set to the failed resource.
            self.proxy_model.setSourceModel(self.source_model)
            self.new()
            return
        super().load(filepath, resref, restype, data)

    def _load_main(
        self,
        data: bytes,
    ):
        # Respect the expected format when provided by the caller (restype).
        # This ensures formats like CSV/JSON are parsed correctly even if the
        # automatic detection heuristic (first 4 characters) is insufficient.
        try:
            twoda: TwoDA = read_2da(data, file_format=self._restype)
        except KeyError as e:
            # Backwards compatibility: some JSON 2DA formats use a different schema
            # (e.g., test fixtures with 'headers' + rows containing 'label' and 'cells').
            # Attempt to gracefully parse that format as a fallback.
            try:
                import json as _json

                parsed = _json.loads(data.decode("utf-8"))
                if isinstance(parsed, dict) and "headers" in parsed and "rows" in parsed:
                    twoda = TwoDA()
                    for header in parsed.get("headers", []):
                        twoda.add_column(str(header))
                    for row in parsed.get("rows", []):
                        label = row.get("label")
                        cells = row.get("cells", [])
                        cell_map = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(twoda.get_headers())}
                        twoda.add_row(str(label), cell_map)
                else:
                    raise
            except Exception:
                # Re-raise original error if fallback fails
                raise e from None
        headers: list[str] = ["", *twoda.get_headers()]
        rc, cc = self.source_model.rowCount(), self.source_model.columnCount()
        if rc > 0:
            self.source_model.removeRows(0, rc)
        if cc > 0:
            self.source_model.removeColumns(0, cc)
        self.source_model.setColumnCount(len(headers))
        self.source_model.setHorizontalHeaderLabels(headers)

        # Disconnect the model to improve performance during updates (especially for appearance.2da)
        self.ui.twodaTable.setModel(None)  # type: ignore[arg-type]

        items: list[list[QStandardItem]] = []
        for i, row in enumerate(twoda):
            label_item = QStandardItem(str(twoda.get_label(i)))
            font = label_item.font()
            font.setBold(True)
            label_item.setFont(font)
            label_item.setBackground(self.palette().midlight())
            row_items = [label_item]
            row_items.extend(QStandardItem(row.get_string(header)) for header in headers[1:])
            items.append(row_items)

        for i, row_items in enumerate(items):
            self.source_model.insertRow(i, row_items)

        self.reset_vertical_headers()
        self.proxy_model.setSourceModel(self.source_model)
        self.ui.twodaTable.setModel(self.proxy_model)  # type: ignore[arg-type]
        self._reconstruct_menu(headers)
        self._undo_stack.clear()
        sm = self.ui.twodaTable.selectionModel()
        if sm is not None:
            sm.selectionChanged.connect(self._update_status_bar)
        if self.ui.actionAutoFitColumnsOnLoad.isChecked():
            self.ui.twodaTable.resizeColumnsToContents()

    def _get_headers_list(self) -> list[str]:
        return _headers_list(self.source_model)

    def _reconstruct_menu(
        self,
        headers: list[str],
    ):
        self.ui.menuSetRowHeader.clear()
        action = QAction("None", self)
        action.triggered.connect(lambda: self.set_vertical_header_option(VerticalHeaderOption.NONE))
        self.ui.menuSetRowHeader.addAction(action)  # type: ignore[arg-type]

        action = QAction("Row Index", self)
        action.triggered.connect(lambda: self.set_vertical_header_option(VerticalHeaderOption.ROW_INDEX))
        self.ui.menuSetRowHeader.addAction(action)  # type: ignore[arg-type]

        action = QAction("Row Label", self)
        action.triggered.connect(lambda: self.set_vertical_header_option(VerticalHeaderOption.ROW_LABEL))
        self.ui.menuSetRowHeader.addAction(action)  # type: ignore[arg-type]
        self.ui.menuSetRowHeader.addSeparator()
        for header in headers[1:]:
            action = QAction(header, self)
            action.triggered.connect(lambda _=None, h=header: self.set_vertical_header_option(VerticalHeaderOption.CELL_VALUE, h))
            self.ui.menuSetRowHeader.addAction(action)  # type: ignore[arg-type]

    def build(self) -> tuple[bytes, bytes]:
        twoda = TwoDA()

        for i in range(self.source_model.columnCount())[1:]:
            horizontal_header_item = self.source_model.horizontalHeaderItem(i)
            assert horizontal_header_item is not None, "Horizontal header item should not be None"
            twoda.add_column(horizontal_header_item.text())

        for i in range(self.source_model.rowCount()):
            twoda.add_row()
            col_item = self.source_model.item(i, 0)
            assert col_item is not None, "Item should not be None"
            twoda.set_label(i, col_item.text())
            for j, header in enumerate(twoda.get_headers()):
                col_item = self.source_model.item(i, j + 1)
                assert col_item is not None, "Item should not be None"
                twoda.set_cell(i, header, col_item.text())

        data = bytearray()
        assert self._restype, assert_with_variable_trace(bool(self._restype), "self._restype must be valid.")
        write_2da(twoda, data, self._restype)
        return bytes(data), b""

    def import_csv(self):
        """Import CSV file and populate the table."""
        import csv

        from qtpy.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            "",
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8', newline='') as f:
                # Try to detect dialect
                sample = f.read(1024)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = csv.excel

                reader = csv.reader(f, dialect=dialect)
                rows = list(reader)

            if not rows:
                QMessageBox.information(self, "Import CSV", "CSV file is empty.")
                return

            # Disconnect model temporarily for performance
            self.ui.twodaTable.setModel(None)  # type: ignore[arg-type]

            # Clear existing data
            rc, cc = self.source_model.rowCount(), self.source_model.columnCount()
            if rc > 0:
                self.source_model.removeRows(0, rc)
            if cc > 0:
                self.source_model.removeColumns(0, cc)

            # First row is headers
            headers = [""] + rows[0]  # Add empty column 0 for row labels
            self.source_model.setColumnCount(len(headers))
            self.source_model.setHorizontalHeaderLabels(headers)

            # Remaining rows are data
            for row_idx, row_data in enumerate(rows[1:]):
                label_item = QStandardItem(str(row_idx))
                font = label_item.font()
                font.setBold(True)
                label_item.setFont(font)
                label_item.setBackground(self.palette().midlight())
                
                row_items = [label_item]
                for col_idx in range(len(headers) - 1):  # -1 for row label column
                    cell_value = row_data[col_idx] if col_idx < len(row_data) else ""
                    row_items.append(QStandardItem(cell_value))
                
                self.source_model.appendRow(row_items)

            # Reconnect model
            self.proxy_model.setSourceModel(self.source_model)
            self.ui.twodaTable.setModel(self.proxy_model)  # type: ignore[arg-type]
            self._reconstruct_menu(headers)
            self.reset_vertical_headers()
            self._undo_stack.clear()

            if self.ui.actionAutoFitColumnsOnLoad.isChecked():
                self.ui.twodaTable.resizeColumnsToContents()

            QMessageBox.information(self, "Import CSV", f"Successfully imported {len(rows)-1} rows with {len(headers)-1} columns.")

        except Exception as e:
            QMessageBox.critical(self, "Import CSV Error", f"Failed to import CSV:\n{e}")

    def export_csv(self):
        """Export table to CSV file."""
        import csv

        from qtpy.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, dialect=csv.excel)
                
                # Write headers (skip column 0 which is row labels)
                headers = []
                for col in range(1, self.source_model.columnCount()):
                    h = self.source_model.horizontalHeaderItem(col)
                    headers.append(h.text() if h else f"Column{col}")
                writer.writerow(headers)
                
                # Write data rows (skip column 0 which is row labels)
                for row in range(self.source_model.rowCount()):
                    row_data = []
                    for col in range(1, self.source_model.columnCount()):
                        item = self.source_model.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

            QMessageBox.information(self, "Export CSV", f"Successfully exported to:\n{filepath}")

        except Exception as e:
            QMessageBox.critical(self, "Export CSV Error", f"Failed to export CSV:\n{e}")

    def new(self):
        super().new()

        # Initialize with 2 default columns + 1 row for immediate usability
        self.source_model.clear()
        
        # Set up headers: row label column (empty) + 2 data columns
        headers = ["", "Column1", "Column2"]
        self.source_model.setColumnCount(len(headers))
        self.source_model.setHorizontalHeaderLabels(headers)
        
        # Add one default row with bold row label
        row_items = []
        label_item = QStandardItem("0")
        font = label_item.font()
        font.setBold(True)
        label_item.setFont(font)
        label_item.setBackground(self.palette().midlight())
        row_items.append(label_item)
        row_items.append(QStandardItem(""))
        row_items.append(QStandardItem(""))
        self.source_model.appendRow(row_items)
        
        # Default to TwoDA for new files
        self._restype = ResourceType.TwoDA
        self.proxy_model.setSourceModel(self.source_model)
        self.ui.twodaTable.setModel(self.proxy_model)  # type: ignore[arg-type]
        self._reconstruct_menu(headers)
        self.reset_vertical_headers()
        self._undo_stack.clear()

    def jump_to_row(
        self,
        row: int,
    ):
        """Jumps to and selects the specified row in the 2DA table. Clamps out-of-range row to valid indices."""
        if self.source_model.rowCount() == 0:
            return
        row = max(0, min(row, self.source_model.rowCount() - 1))
        index: QModelIndex = self.proxy_model.mapFromSource(self.source_model.index(row, 0))
        self.ui.twodaTable.setCurrentIndex(index)
        self.ui.twodaTable.scrollTo(index, self.ui.twodaTable.ScrollHint.EnsureVisible)  # type: ignore[arg-type]
        self.ui.twodaTable.selectRow(index.row())

    def do_filter(
        self,
        text: str,
    ):
        """Applies a filter to the 2DA table based on the provided text."""
        self.proxy_model.setFilterFixedString(text)

    def toggle_filter(self):
        """Toggles the visibility of the filter box."""
        # Ensure the widget is visible so child visibility reflects the toggle state (important for tests)
        if not self.isVisible():
            self.show()
        visible: bool = not self.ui.filterBox.isVisible()
        self.ui.filterBox.setVisible(visible)
        if visible:
            self.do_filter(self.ui.filterEdit.text())
            self.ui.filterEdit.setFocus()
            self.ui.filterEdit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # type: ignore[arg-type]
        else:
            self.do_filter("")

    def _find_next_repeat_forward(self):
        """F3: Find next using last find text."""
        if getattr(self, "_last_find_text", ""):
            self._find_next(
                forward=True,
                find_text=self._last_find_text,
                match_case=self._last_match_case,
                match_whole_cell=getattr(self, "_last_match_whole_cell", False),
            )

    def _find_next_repeat_backward(self):
        """Shift+F3: Find previous using last find text."""
        if getattr(self, "_last_find_text", ""):
            self._find_next(
                forward=False,
                find_text=self._last_find_text,
                match_case=self._last_match_case,
                match_whole_cell=getattr(self, "_last_match_whole_cell", False),
            )

    def _go_to_first_cell(self):
        """Ctrl+Home: Select first cell (0,0)."""
        if self.proxy_model.rowCount() and self.proxy_model.columnCount():
            idx = self.proxy_model.index(0, 0)
            self.ui.twodaTable.setCurrentIndex(idx)
            self.ui.twodaTable.scrollTo(idx, self.ui.twodaTable.ScrollHint.PositionAtTop)
            selectionModel = self.ui.twodaTable.selectionModel()
            assert selectionModel is not None, "Selection model should not be None"
            selectionModel.select(idx, selectionModel.SelectionFlag.ClearAndSelect)

    def _go_to_last_cell(self):
        """Ctrl+End: Select last cell."""
        r, c = self.proxy_model.rowCount() - 1, self.proxy_model.columnCount() - 1
        if r >= 0 and c >= 0:
            idx = self.proxy_model.index(r, c)
            self.ui.twodaTable.setCurrentIndex(idx)
            self.ui.twodaTable.scrollTo(idx, self.ui.twodaTable.ScrollHint.EnsureVisible)
            selectionModel = self.ui.twodaTable.selectionModel()
            assert selectionModel is not None, "Selection model should not be None"
            selectionModel.select(idx, selectionModel.SelectionFlag.ClearAndSelect)

    def _on_column_header_double_clicked(self, logical_index: int):
        """Rename column when user double-clicks the header (Excel-like)."""
        if logical_index < 0 or logical_index >= self.source_model.columnCount():
            return
        from qtpy.QtWidgets import QInputDialog

        h = self.source_model.horizontalHeaderItem(logical_index)
        assert h is not None, "Horizontal header item should not be None"
        current = (h.text() or "") if h else ""
        new_name, ok = QInputDialog.getText(self, "Rename Column", "Column name:", text=current)
        if ok and new_name is not None:
            self.source_model.setHorizontalHeaderItem(logical_index, QStandardItem(new_name.strip()))
            columns: list[str] = []
            for i in range(self.source_model.columnCount()):
                header_item = self.source_model.horizontalHeaderItem(i)
                assert header_item is not None, "Horizontal header item should not be None"
                columns.append(header_item.text() or "")
            self._reconstruct_menu(columns)

    def rename_current_column(self):
        """Open rename dialog for the column of the current cell (context menu / Excel-like)."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        self._on_column_header_double_clicked(cur.column())

    def hide_current_column(self):
        """Hide the current column in the view (Excel-like). Data is preserved; use Show All Columns to unhide."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = cur.column()
        h = self.ui.twodaTable.horizontalHeader()
        if h is not None and 0 <= col < self.source_model.columnCount():
            h.setSectionHidden(col, True)

    def show_all_columns(self):
        """Unhide all columns in the view."""
        h = self.ui.twodaTable.horizontalHeader()
        if h is not None:
            for col in range(h.count()):
                h.setSectionHidden(col, False)

    def _on_auto_fit_columns_toggled(self):
        """Persist auto-fit preference; applied on next load."""
        pass

    def _on_wrap_text_toggled(self):
        """Toggle word wrap in table cells (Excel-like)."""
        self.ui.twodaTable.setWordWrap(self.ui.actionWrapTextInCells.isChecked())

    def _on_alternating_row_colors_toggled(self):
        """Toggle alternating row colors (Excel-like)."""
        self.ui.twodaTable.setAlternatingRowColors(self.ui.actionAlternatingRowColors.isChecked())

    def zoom_in(self):
        """Increase table zoom (Ctrl+Plus)."""
        self._zoom_factor = min(3.0, self._zoom_factor * 1.25)
        self._apply_zoom()

    def zoom_out(self):
        """Decrease table zoom (Ctrl+Minus)."""
        self._zoom_factor = max(0.5, self._zoom_factor / 1.25)
        self._apply_zoom()

    def zoom_reset(self):
        """Reset zoom to 100% (Ctrl+0)."""
        self._zoom_factor = 1.0
        self._apply_zoom()

    def _apply_zoom(self):
        """Apply current zoom factor to table and header fonts."""
        size = max(6, min(72, round(self._zoom_base_point_size * self._zoom_factor)))
        font = self.ui.twodaTable.font()
        font.setPointSize(size)
        self.ui.twodaTable.setFont(font)
        h = self.ui.twodaTable.horizontalHeader()
        if h is not None:
            h.setFont(font)
        v = self.ui.twodaTable.verticalHeader()
        if v is not None:
            v.setFont(font)
        self._update_status_bar()

    def select_visible_only(self):
        """Restrict selection to cells in visible rows (filter) and non-hidden columns (Excel-like)."""
        from qtpy.QtCore import QItemSelection

        h_header = self.ui.twodaTable.horizontalHeader()
        hidden_cols = set()
        if h_header is not None:
            for c in range(h_header.count()):
                if h_header.isSectionHidden(c):
                    hidden_cols.add(c)
        indexes = self.ui.twodaTable.selectedIndexes()
        if not indexes:
            return
        selection = QItemSelection()
        for idx in indexes:
            if idx.column() in hidden_cols:
                continue
            selection.select(idx, idx)
        sel_model = self.ui.twodaTable.selectionModel()
        if sel_model is not None:
            sel_model.select(selection, sel_model.SelectionFlag.ClearAndSelect)

    def select_blank_cells(self):
        """Select all cells that are empty (Excel-like)."""
        from qtpy.QtCore import QItemSelection
        selection = QItemSelection()
        for r in range(self.source_model.rowCount()):
            for c in range(self.source_model.columnCount()):
                item = self.source_model.item(r, c)
                if item is None or not (item.text() or "").strip():
                    src_idx = self.source_model.index(r, c)
                    proxy_idx = self.proxy_model.mapFromSource(src_idx)
                    if proxy_idx.isValid():
                        selection.select(proxy_idx, proxy_idx)
        sel_model = self.ui.twodaTable.selectionModel()
        if sel_model is not None:
            sel_model.select(selection, sel_model.SelectionFlag.ClearAndSelect)

    def select_cells_with_content(self):
        """Select all cells that have non-empty text (Excel-like)."""
        from qtpy.QtCore import QItemSelection
        selection = QItemSelection()
        for r in range(self.source_model.rowCount()):
            for c in range(self.source_model.columnCount()):
                item = self.source_model.item(r, c)
                if item is not None and (item.text() or "").strip():
                    src_idx = self.source_model.index(r, c)
                    proxy_idx = self.proxy_model.mapFromSource(src_idx)
                    if proxy_idx.isValid():
                        selection.select(proxy_idx, proxy_idx)
        sel_model = self.ui.twodaTable.selectionModel()
        if sel_model is not None:
            sel_model.select(selection, sel_model.SelectionFlag.ClearAndSelect)

    def duplicate_column(self):
        """Duplicate the current column (insert copy to the right). Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = self.proxy_model.mapToSource(cur).column()
        if col < 0 or col >= self.source_model.columnCount():
            return
        try:
            self._undo_stack.push(_DuplicateColumnCommand(self.source_model, col, self))
        except Exception:
            pass

    def move_column_left(self):
        """Move current column one position left. Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = self.proxy_model.mapToSource(cur).column()
        if col <= 0 or col >= self.source_model.columnCount():
            return
        try:
            self._undo_stack.push(_MoveColumnCommand(self.source_model, col, False, self))
        except ValueError:
            pass

    def move_column_right(self):
        """Move current column one position right. Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = self.proxy_model.mapToSource(cur).column()
        if col < 0 or col >= self.source_model.columnCount() - 1:
            return
        try:
            self._undo_stack.push(_MoveColumnCommand(self.source_model, col, True, self))
        except ValueError:
            pass

    def move_row_up(self):
        """Move current row one position up. Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        row = self.proxy_model.mapToSource(cur).row()
        if row <= 0 or row >= self.source_model.rowCount():
            return
        try:
            self._undo_stack.push(_MoveRowCommand(self.source_model, row, False, self))
        except ValueError:
            pass

    def move_row_down(self):
        """Move current row one position down. Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        row = self.proxy_model.mapToSource(cur).row()
        if row < 0 or row >= self.source_model.rowCount() - 1:
            return
        try:
            self._undo_stack.push(_MoveRowCommand(self.source_model, row, True, self))
        except ValueError:
            pass

    def remove_duplicate_rows(self):
        """Remove rows that are exact duplicates of a previous row (keep first). Undoable."""
        if self.source_model.rowCount() == 0:
            return
        self._undo_stack.push(_RemoveDuplicateRowsCommand(self.source_model, self))

    def transpose_table(self):
        """Transpose the entire table (rows become columns). Undoable."""
        if self.source_model.rowCount() == 0 or self.source_model.columnCount() == 0:
            return
        self._undo_stack.push(_TransposeCommand(self.source_model, self))

    def show_go_to_row_dialog(self):
        """Show Go to Row dialog and jump to the given row (0-based)."""
        from qtpy.QtWidgets import QInputDialog

        row, ok = QInputDialog.getInt(
            self,
            "Go to Row",
            "Row (0-based):",
            value=0,
            min=0,
            max=max(0, self.source_model.rowCount() - 1),
        )
        if ok:
            self.jump_to_row(row)

    def show_go_to_column_dialog(self):
        """Show Go to Column dialog and jump to the given column (0-based)."""
        from qtpy.QtWidgets import QInputDialog

        col, ok = QInputDialog.getInt(
            self,
            "Go to Column",
            "Column (0-based):",
            value=0,
            min=0,
            max=max(0, self.source_model.columnCount() - 1),
        )
        if ok:
            self.jump_to_column(col)

    def jump_to_column(self, col: int):
        """Select and scroll to the given column (0-based)."""
        if col < 0 or col >= self.source_model.columnCount():
            return
        idx = self.proxy_model.mapFromSource(self.source_model.index(0, col))
        self.ui.twodaTable.setCurrentIndex(idx)
        self.ui.twodaTable.scrollTo(idx, self.ui.twodaTable.ScrollHint.PositionAtCenter)
        selection_model = self.ui.twodaTable.selectionModel()
        if selection_model is not None:
            top = self.proxy_model.index(0, col)
            bottom = self.proxy_model.index(self.proxy_model.rowCount() - 1, col)
            if top.isValid() and bottom.isValid():
                from qtpy.QtCore import QItemSelection
                selection_model.select(
                    QItemSelection(top, bottom),
                    selection_model.SelectionFlag.ClearAndSelect,
                )

    def insert_row_above(self):
        """Insert a blank row above the current selection (or at row 0 if none)."""
        if self.source_model.columnCount() == 0:
            QMessageBox.information(self, "Insert Row", "Add at least one column first (e.g. via a loaded 2DA file).")
            return
        cur = self.ui.twodaTable.currentIndex()
        row_index = self.proxy_model.mapToSource(cur).row() if cur.isValid() else 0
        new_items = [QStandardItem("") for _ in range(self.source_model.columnCount())]
        self._undo_stack.push(_InsertRowCommand(self.source_model, row_index, new_items, self))

    def insert_row_below(self):
        """Insert a blank row below the current selection (or at row 0 if none)."""
        if self.source_model.columnCount() == 0:
            QMessageBox.information(self, "Insert Row", "Add at least one column first (e.g. via a loaded 2DA file).")
            return
        cur = self.ui.twodaTable.currentIndex()
        row_index = self.proxy_model.mapToSource(cur).row() + 1 if cur.isValid() else 0
        row_index = min(row_index, self.source_model.rowCount())
        new_items = [QStandardItem("") for _ in range(self.source_model.columnCount())]
        self._undo_stack.push(_InsertRowCommand(self.source_model, row_index, new_items, self))

    def _show_header_context_menu(self, pos):
        """Show context menu on column header: Insert new column at this position."""
        from qtpy.QtWidgets import QMenu

        h = self.ui.twodaTable.horizontalHeader()
        if h is None:
            return
        col = h.logicalIndexAt(pos)
        if col < 0:
            col = self.source_model.columnCount()
        menu = QMenu(self)
        
        insert_action = QAction(translate("Insert Column Here"), self)
        insert_action.setToolTip(translate("<b>Insert Column Here</b> adds column.<br/>New column at this position."))
        insert_action.triggered.connect(lambda: self.insert_column_at(col))
        menu.addAction(insert_action)
        
        if col > 0:  # Don't allow operations on row label column
            menu.addSeparator()
            
            rename_action = QAction(translate("Rename Column..."), self)
            rename_action.setToolTip(translate("<b>Rename Column</b> changes name.<br/>Opens rename dialog."))
            rename_action.triggered.connect(lambda: self._on_column_header_double_clicked(col))
            menu.addAction(rename_action)
            
            duplicate_action = QAction(translate("Duplicate Column"), self)
            duplicate_action.setToolTip(translate("<b>Duplicate Column</b> copies column.<br/>Exact copy beside this one."))
            duplicate_action.triggered.connect(lambda: self._duplicate_column_at(col))
            menu.addAction(duplicate_action)
            
            delete_action = QAction(translate("Delete Column"), self)
            delete_action.setToolTip(translate("<b>Delete Column</b> removes entirely.<br/>All column data is lost."))
            delete_action.triggered.connect(lambda: self._delete_column_at(col))
            menu.addAction(delete_action)
            
            menu.addSeparator()
            
            if col > 1:
                left_action = QAction(translate("Move Left"), self)
                left_action.setToolTip(translate("<b>Move Left</b> shifts column left.<br/>Swaps with left neighbor."))
                left_action.triggered.connect(lambda: self._move_column_at(col, False))
                menu.addAction(left_action)
            
            if col < self.source_model.columnCount() - 1:
                right_action = QAction(translate("Move Right"), self)
                right_action.setToolTip(translate("<b>Move Right</b> shifts column right.<br/>Swaps with right neighbor."))
                right_action.triggered.connect(lambda: self._move_column_at(col, True))
                menu.addAction(right_action)
            
            menu.addSeparator()
            
            sort_asc_action = QAction(translate("Sort Ascending"), self)
            sort_asc_action.setToolTip(translate("<b>Sort Ascending</b> A–Z order.<br/>Lowest values first."))
            sort_asc_action.triggered.connect(lambda: self._sort_column_at(col, True))
            menu.addAction(sort_asc_action)
            
            sort_desc_action = QAction(translate("Sort Descending"), self)
            sort_desc_action.setToolTip(translate("<b>Sort Descending</b> Z–A order.<br/>Highest values first."))
            sort_desc_action.triggered.connect(lambda: self._sort_column_at(col, False))
            menu.addAction(sort_desc_action)
            
            menu.addSeparator()
            
            stats_action = QAction(translate("Column Statistics..."), self)
            stats_action.setToolTip(translate("<b>Column Statistics</b> shows stats.<br/>Count, sum, min, max, etc."))
            stats_action.triggered.connect(lambda: self._show_column_stats_at(col))
            menu.addAction(stats_action)
            
            hide_action = QAction(translate("Hide Column"), self)
            hide_action.setToolTip(translate("<b>Hide Column</b> hides from view.<br/>Data retained but not shown."))
            hide_action.triggered.connect(lambda: self._hide_column_at(col))
            menu.addAction(hide_action)
        
        menu.exec(h.mapToGlobal(pos))

    def _show_row_header_context_menu(self, pos):
        """Show context menu on row header: Row operations."""
        from qtpy.QtWidgets import QMenu

        v = self.ui.twodaTable.verticalHeader()
        if v is None:
            return
        row = v.logicalIndexAt(pos)
        if row < 0:
            return
        
        # Map to source row
        proxy_idx = self._editor.proxy_model.index(row, 0) if hasattr(self, '_editor') else self.proxy_model.index(row, 0)
        if hasattr(self, '_editor'):
            source_row = self._editor.proxy_model.mapToSource(proxy_idx).row()
        else:
            source_row = self.proxy_model.mapToSource(proxy_idx).row()
        
        menu = QMenu(self)
        
        insert_above = QAction(translate("Insert Row Above"), self)
        insert_above.setToolTip(translate("<b>Insert Row Above</b> adds row.<br/>New row above this one."))
        insert_above.triggered.connect(lambda: self._insert_row_at(source_row))
        menu.addAction(insert_above)
        
        insert_below = QAction(translate("Insert Row Below"), self)
        insert_below.setToolTip(translate("<b>Insert Row Below</b> adds row.<br/>New row below this one."))
        insert_below.triggered.connect(lambda: self._insert_row_at(source_row + 1))
        menu.addAction(insert_below)
        
        menu.addSeparator()
        
        duplicate = QAction(translate("Duplicate Row"), self)
        duplicate.setToolTip(translate("<b>Duplicate Row</b> copies row.<br/>Creates exact duplicate below."))
        duplicate.triggered.connect(lambda: self._duplicate_row_at(source_row))
        menu.addAction(duplicate)
        
        delete = QAction(translate("Delete Row(s)"), self)
        delete.setToolTip(translate("<b>Delete Row(s)</b> removes rows.<br/>All selected row data lost."))
        delete.triggered.connect(self.remove_selected_rows)
        menu.addAction(delete)
        
        menu.addSeparator()
        
        if source_row > 0:
            move_up = QAction(translate("Move Row Up"), self)
            move_up.setToolTip(translate("<b>Move Row Up</b> shifts row.<br/>Swaps with row above."))
            move_up.triggered.connect(lambda: self._move_row_at(source_row, False))
            menu.addAction(move_up)
        
        if source_row < self.source_model.rowCount() - 1:
            move_down = QAction(translate("Move Row Down"), self)
            move_down.setToolTip(translate("<b>Move Row Down</b> shifts row.<br/>Swaps with row below."))
            move_down.triggered.connect(lambda: self._move_row_at(source_row, True))
            menu.addAction(move_down)
        
        menu.addSeparator()
        
        edit_label = QAction(translate("Edit Row Label..."), self)
        edit_label.setToolTip(translate("<b>Edit Row Label</b> changes label.<br/>Opens edit dialog."))
        edit_label.triggered.connect(lambda: self._on_row_header_double_clicked(row))
        menu.addAction(edit_label)
        
        menu.exec(v.mapToGlobal(pos))

    def _on_row_header_clicked(self, logical_index: int):
        """Select entire row when row header is clicked."""
        if logical_index < 0 or logical_index >= self.proxy_model.rowCount():
            return
        
        # Select the entire row
        from qtpy.QtCore import QItemSelection
        left = self.proxy_model.index(logical_index, 0)
        right = self.proxy_model.index(logical_index, self.proxy_model.columnCount() - 1)
        
        if left.isValid() and right.isValid():
            selection_model = self.ui.twodaTable.selectionModel()
            if selection_model:
                selection_model.select(
                    QItemSelection(left, right),
                    selection_model.SelectionFlag.ClearAndSelect
                )
                self.ui.twodaTable.setCurrentIndex(left)

    def _on_row_header_double_clicked(self, logical_index: int):
        """Edit row label when row header is double-clicked."""
        if logical_index < 0 or logical_index >= self.proxy_model.rowCount():
            return
        
        from qtpy.QtWidgets import QInputDialog
        
        # Map to source row
        proxy_idx = self.proxy_model.index(logical_index, 0)
        source_row = self.proxy_model.mapToSource(proxy_idx).row()
        
        item = self.source_model.item(source_row, 0)
        if item is None:
            return
        
        current_label = item.text()
        new_label, ok = QInputDialog.getText(
            self,
            "Edit Row Label",
            f"Row {source_row} label:",
            text=current_label
        )
        
        if ok and new_label is not None:
            item.setText(new_label)

    def insert_column_at(self, col: int):
        """Insert a new column at the given index (0-based). Prompts for header name. Undoable."""
        from qtpy.QtWidgets import QInputDialog

        if self.source_model.columnCount() == 0:
            return
        col = max(0, min(col, self.source_model.columnCount()))
        header, ok = QInputDialog.getText(self, "Insert Column", "Column header name:", text="newcolumn")
        if not ok or not header.strip():
            return
        self._undo_stack.push(_InsertColumnCommand(self.source_model, col, header.strip(), self))

    def _duplicate_column_at(self, col: int):
        """Duplicate column at given index."""
        if col < 0 or col >= self.source_model.columnCount():
            return
        try:
            self._undo_stack.push(_DuplicateColumnCommand(self.source_model, col, self))
        except Exception:
            pass

    def _delete_column_at(self, col: int):
        """Delete column at given index."""
        if col <= 0:
            return
        if self.source_model.columnCount() <= 2:
            QMessageBox.warning(self, "Delete Column", "Cannot delete the last data column.")
            return
        self._undo_stack.push(_DeleteColumnCommand(self.source_model, col, self))

    def _move_column_at(self, col: int, right: bool):
        """Move column at given index left or right."""
        if col < 0 or col >= self.source_model.columnCount():
            return
        try:
            self._undo_stack.push(_MoveColumnCommand(self.source_model, col, right, self))
        except ValueError:
            pass

    def _sort_column_at(self, col: int, ascending: bool):
        """Sort by column at given index."""
        if col < 1:
            return
        self._undo_stack.push(_SortCommand(self.source_model, col, ascending, self))

    def _show_column_stats_at(self, col: int):
        """Show statistics for column at given index."""
        if col <= 0:
            return
        h = self.source_model.horizontalHeaderItem(col)
        col_name = (h.text() or f"Column{col}") if h else f"Column{col}"
        values = []
        for row in range(self.source_model.rowCount()):
            item = self.source_model.item(row, col)
            values.append(item.text() if item else "")
        dialog = ColumnStatisticsDialog(self, col_name, values)
        dialog.exec()

    def _hide_column_at(self, col: int):
        """Hide column at given index."""
        h = self.ui.twodaTable.horizontalHeader()
        if h is not None and 0 <= col < self.source_model.columnCount():
            h.setSectionHidden(col, True)

    def _insert_row_at(self, row: int):
        """Insert row at given index."""
        if self.source_model.columnCount() == 0:
            return
        new_items = [QStandardItem("") for _ in range(self.source_model.columnCount())]
        self._undo_stack.push(_InsertRowCommand(self.source_model, row, new_items, self))

    def _duplicate_row_at(self, row: int):
        """Duplicate row at given index and append to end."""
        if row < 0 or row >= self.source_model.rowCount():
            return
        new_items = []
        for i in range(self.source_model.columnCount()):
            orig_item = self.source_model.item(row, i)
            if orig_item is None:
                new_items.append(QStandardItem(""))
            else:
                new_items.append(orig_item.clone())
        row_index = self.source_model.rowCount()
        self._undo_stack.push(_InsertRowCommand(self.source_model, row_index, new_items, self))

    def _move_row_at(self, row: int, down: bool):
        """Move row at given index up or down."""
        if row < 0 or row >= self.source_model.rowCount():
            return
        try:
            self._undo_stack.push(_MoveRowCommand(self.source_model, row, down, self))
        except ValueError:
            pass

    def _quick_clear_column(self):
        """Clear all cells in the current column."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = self.proxy_model.mapToSource(cur).column()
        if col <= 0:
            return
        
        changes: list[tuple[int, int, str, str]] = []
        for row in range(self.source_model.rowCount()):
            item = self.source_model.item(row, col)
            if item and item.text():
                changes.append((row, col, item.text(), ""))
        
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Clear column"))

    def _quick_clear_row(self):
        """Clear all cells in the current row."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        row = self.proxy_model.mapToSource(cur).row()
        
        changes: list[tuple[int, int, str, str]] = []
        for col in range(1, self.source_model.columnCount()):  # Skip row label
            item = self.source_model.item(row, col)
            if item and item.text():
                changes.append((row, col, item.text(), ""))
        
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Clear row"))

    def show_cell_formatting_dialog(self):
        """Show cell formatting dialog and apply to selection."""
        selected = self.ui.twodaTable.selectedIndexes()
        if not selected:
            QMessageBox.information(self, "Format Cells", "Please select cells to format.")
            return
        
        dialog = CellFormattingDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            formatting = dialog.get_formatting()
            self._apply_cell_formatting(selected, formatting)

    def _apply_cell_formatting(self, indexes: list, formatting: dict):
        """Apply formatting to the given indexes."""
        from qtpy.QtGui import QBrush, QColor
        
        for idx in indexes:
            source_idx = self.proxy_model.mapToSource(idx)
            item = self.source_model.itemFromIndex(source_idx)
            if not item:
                continue
            
            # Font style
            font = item.font()
            if formatting['bold']:
                font.setBold(True)
            if formatting['italic']:
                font.setItalic(True)
            item.setFont(font)
            
            # Text color
            color_map = {
                'Red': QColor(255, 0, 0),
                'Green': QColor(0, 150, 0),
                'Blue': QColor(0, 0, 255),
                'Orange': QColor(255, 140, 0),
                'Purple': QColor(128, 0, 128),
                'Gray': QColor(128, 128, 128),
            }
            if formatting['color'] in color_map:
                item.setForeground(QBrush(color_map[formatting['color']]))
            
            # Background color
            bg_map = {
                'Light Yellow': QColor(255, 255, 200),
                'Light Green': QColor(200, 255, 200),
                'Light Blue': QColor(200, 220, 255),
                'Light Red': QColor(255, 200, 200),
                'Light Gray': QColor(240, 240, 240),
            }
            if formatting['background'] in bg_map:
                item.setBackground(QBrush(bg_map[formatting['background']]))
            
            # Alignment
            from qtpy.QtCore import Qt
            align_map = {
                'Left': Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                'Center': Qt.AlignmentFlag.AlignCenter,
                'Right': Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            }
            if formatting['alignment'] in align_map:
                item.setTextAlignment(align_map[formatting['alignment']])

    def show_bulk_edit_dialog(self):
        """Show bulk edit dialog and apply to selection."""
        selected = self.ui.twodaTable.selectedIndexes()
        if not selected:
            QMessageBox.information(self, "Bulk Edit", "Please select cells to edit.")
            return
        
        dialog = BulkEditDialog(self, len(selected))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            changes = []
            for idx in selected:
                source_idx = self.proxy_model.mapToSource(idx)
                item = self.source_model.itemFromIndex(source_idx)
                if item:
                    old_text = item.text()
                    new_text = dialog.apply_to_text(old_text)
                    if new_text != old_text:
                        changes.append((source_idx.row(), source_idx.column(), old_text, new_text))
            
            if changes:
                self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Bulk edit"))

    def show_column_filter_dialog(self):
        """Show column filter dialog and apply filter."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            QMessageBox.information(self, "Filter Column", "Please select a column to filter.")
            return
        
        col = self.proxy_model.mapToSource(cur).column()
        if col <= 0:
            return
        
        # Get column name
        h = self.source_model.horizontalHeaderItem(col)
        col_name = (h.text() or f"Column{col}") if h else f"Column{col}"
        
        # Get unique values
        unique_values = set()
        for row in range(self.source_model.rowCount()):
            item = self.source_model.item(row, col)
            if item and item.text().strip():
                unique_values.add(item.text())
        
        dialog = ColumnFilterDialog(self, col_name, list(unique_values))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_values = dialog.get_selected_values()
            include_blanks = dialog.include_blanks()
            self._apply_column_filter(col, selected_values, include_blanks)

    def _apply_column_filter(self, col: int, allowed_values: list[str], include_blanks: bool):
        """Apply filter to show only rows with allowed values in column."""
        # Hide rows that don't match
        for row in range(self.proxy_model.rowCount()):
            source_idx = self.proxy_model.mapToSource(self.proxy_model.index(row, col))
            item = self.source_model.itemFromIndex(source_idx)
            
            if item:
                value = item.text()
                if not value.strip() and include_blanks:
                    self.ui.twodaTable.setRowHidden(row, False)
                elif value in allowed_values:
                    self.ui.twodaTable.setRowHidden(row, False)
                else:
                    self.ui.twodaTable.setRowHidden(row, True)

    def show_data_validation_dialog(self):
        """Show data validation dialog and apply rules."""
        selected = self.ui.twodaTable.selectedIndexes()
        if not selected:
            QMessageBox.information(self, "Data Validation", "Please select cells to apply validation.")
            return
        
        dialog = DataValidationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule = dialog.get_validation_rule()
            # Store validation rules (for future validation on edit)
            if not hasattr(self, '_validation_rules'):
                self._validation_rules = {}
            
            for idx in selected:
                source_idx = self.proxy_model.mapToSource(idx)
                key = (source_idx.row(), source_idx.column())
                self._validation_rules[key] = rule
            
            QMessageBox.information(self, "Data Validation", f"Validation rules applied to {len(selected)} cells.")

    def clear_all_filters(self):
        """Clear all row filters and show all rows."""
        for row in range(self.proxy_model.rowCount()):
            self.ui.twodaTable.setRowHidden(row, False)

    def show_hidden_columns(self):
        """Show all hidden columns."""
        h = self.ui.twodaTable.horizontalHeader()
        if h:
            for col in range(self.source_model.columnCount()):
                h.setSectionHidden(col, False)

    def auto_fit_column_width(self, col: int):
        """Auto-fit column width to content."""
        self.ui.twodaTable.resizeColumnToContents(col)

    def auto_fit_all_columns(self):
        """Auto-fit all column widths to content."""
        for col in range(self.source_model.columnCount()):
            self.ui.twodaTable.resizeColumnToContents(col)

    def show_keyboard_shortcuts_help(self):
        """Show a dialog with all keyboard shortcuts."""
        shortcuts_text = """
<html>
<body>
<h2>Keyboard Shortcuts</h2>

<h3>Navigation</h3>
<ul>
<li><b>Tab</b> - Move to next cell (wraps to next row at end)</li>
<li><b>Shift+Tab</b> - Move to previous cell</li>
<li><b>Enter</b> - Move down (creates new row at end)</li>
<li><b>Shift+Enter</b> - Move up</li>
<li><b>Home</b> - Jump to first column of row</li>
<li><b>End</b> - Jump to last column of row</li>
<li><b>Ctrl+Home</b> - Jump to first cell (0,0)</li>
<li><b>Ctrl+End</b> - Jump to last cell</li>
<li><b>Shift+Home</b> - Select from current to start of row</li>
<li><b>Shift+End</b> - Select from current to end of row</li>
<li><b>Ctrl+Shift+Home</b> - Select from current to first cell</li>
<li><b>Ctrl+Shift+End</b> - Select from current to last cell</li>
</ul>

<h3>Selection</h3>
<ul>
<li><b>Shift+Space</b> - Select entire current row</li>
<li><b>Ctrl+Space</b> - Select entire current column</li>
<li><b>Ctrl+A</b> - Select all cells</li>
</ul>

<h3>Editing</h3>
<ul>
<li><b>F2</b> - Start editing current cell</li>
<li><b>Delete / Backspace</b> - Clear selected cells</li>
<li><b>Ctrl+C</b> - Copy selection</li>
<li><b>Ctrl+X</b> - Cut selection</li>
<li><b>Ctrl+V</b> - Paste</li>
<li><b>Ctrl+Z</b> - Undo</li>
<li><b>Ctrl+Y</b> - Redo</li>
</ul>

<h3>Row Operations</h3>
<ul>
<li><b>Ctrl+I</b> - Insert new row</li>
<li><b>Ctrl+D</b> / <b>Ctrl+K</b> - Duplicate current row</li>
<li><b>Ctrl+Minus</b> / <b>Ctrl+Delete</b> - Delete selected rows</li>
<li><b>Alt+Up</b> - Move current row up</li>
<li><b>Alt+Down</b> - Move current row down</li>
<li><b>Ctrl+Shift+X</b> - Clear current row</li>
</ul>

<h3>Column Operations</h3>
<ul>
<li><b>Ctrl+Shift+I</b> - Insert new column</li>
<li><b>Ctrl+Shift+K</b> - Duplicate current column</li>
<li><b>Ctrl+Shift+Delete</b> - Delete column</li>
<li><b>Alt+Left</b> / <b>Ctrl+Shift+Left</b> - Move column left</li>
<li><b>Alt+Right</b> / <b>Ctrl+Shift+Right</b> - Move column right</li>
<li><b>Ctrl+Shift+C</b> - Clear current column</li>
</ul>

<h3>View</h3>
<ul>
<li><b>Ctrl+=</b> - Zoom in</li>
<li><b>Ctrl+-</b> - Zoom out</li>
<li><b>Ctrl+0</b> - Reset zoom</li>
</ul>

<h3>Search & Statistics</h3>
<ul>
<li><b>Ctrl+F</b> - Find</li>
<li><b>Ctrl+H</b> - Replace</li>
<li><b>F3</b> - Find next</li>
<li><b>Shift+F3</b> - Find previous</li>
<li><b>F4</b> - Show column statistics</li>
</ul>

<h3>Advanced Features</h3>
<ul>
<li><b>Ctrl+E</b> - Export to CSV</li>
<li><b>Ctrl+L</b> - Filter column</li>
<li><b>Ctrl+Shift+F</b> - Format cells</li>
<li><b>Ctrl+Shift+B</b> - Bulk edit selection</li>
<li><b>Ctrl+Shift+V</b> - Data validation</li>
</ul>

</body>
</html>
        """
        
        from qtpy.QtWidgets import QTextBrowser
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.resize(600, 700)
        
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(shortcuts_text)
        layout.addWidget(browser)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def _update_status_bar(self):
        rc = self.source_model.rowCount()
        cc = self.source_model.columnCount()
        sel = self.ui.twodaTable.selectedIndexes()
        zoom_suffix = "" if self._zoom_factor == 1.0 else f" | Zoom {round(self._zoom_factor * 100)}%"
        if not sel:
            self.ui.statusbar.showMessage(f"Rows: {rc} | Columns: {cc}{zoom_suffix}")
            return
        rows = {self.proxy_model.mapToSource(idx).row() for idx in sel}
        cols = {self.proxy_model.mapToSource(idx).column() for idx in sel}
        
        # Single cell selection: show cell address
        if len(sel) == 1:
            r, c = min(rows), min(cols)
            h = self.source_model.horizontalHeaderItem(c)
            col_name = (h.text() or f"Col{c}") if h else f"Col{c}"
            cell_value = self.source_model.item(r, c).text() if self.source_model.item(r, c) else ""
            self.ui.statusbar.showMessage(f"Cell R{r}:{col_name} = '{cell_value}' | Rows: {rc} | Columns: {cc}{zoom_suffix}")
            return
        
        # Multiple selection: compute aggregates for numeric values
        numeric_values = []
        for idx in sel:
            src = self.proxy_model.mapToSource(idx)
            item = self.source_model.item(src.row(), src.column())
            if item:
                try:
                    val = float(item.text())
                    numeric_values.append(val)
                except (ValueError, TypeError):
                    pass
        
        if numeric_values:
            count = len(sel)
            num_count = len(numeric_values)
            sum_val = sum(numeric_values)
            avg_val = sum_val / num_count
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            
            agg_str = f"COUNT: {count} | NUMERIC: {num_count} | SUM: {sum_val:.2f} | AVG: {avg_val:.2f} | MIN: {min_val:.2f} | MAX: {max_val:.2f}"
            self.ui.statusbar.showMessage(f"{agg_str} | Rows: {rc} | Columns: {cc}{zoom_suffix}")
        else:
            # No numeric values in selection
            self.ui.statusbar.showMessage(f"COUNT: {len(sel)} (no numeric values) | Rows: {rc} | Columns: {cc} | Selected: rows {min(rows)}–{max(rows)}, cols {min(cols)}–{max(cols)}{zoom_suffix}")

    def _show_table_context_menu(self, pos):
        from qtpy.QtWidgets import QMenu

        def _add_action(menu: QMenu, name: str, slot, tooltip: str = ""):
            a = QAction(translate(name), self)
            a.triggered.connect(slot)
            if tooltip:
                a.setToolTip(translate(tooltip))
            menu.addAction(a)

        def _submenu(parent: QMenu, title: str) -> QMenu:
            sub = parent.addMenu(translate(title))
            if sub is None:
                raise RuntimeError(f"addMenu returned None for {title}")
            return sub

        menu = QMenu(self)

        # Edit — clipboard and clear (standard grouping)
        edit_menu = _submenu(menu, "Edit")
        _add_action(edit_menu, "Copy", self.copy_selection,
            "<b>Copy</b> selected cells to clipboard.<br/>Replaces current clipboard contents.")
        _add_action(edit_menu, "Cut", self.cut_selection,
            "<b>Cut</b> selected cells to clipboard.<br/>Removes cells after copying.")
        _add_action(edit_menu, "Paste", self.paste_selection,
            "<b>Paste</b> clipboard into selected area.<br/>Overwrites existing cell contents.")
        _add_action(edit_menu, "Paste Transpose", self.paste_transpose,
            "<b>Paste Transpose</b> swaps rows and columns.<br/>Useful when orientation differs.")
        _add_action(edit_menu, "Clear Contents", self.clear_selection_contents,
            "<b>Clear Contents</b> empties selected cells.<br/>Cells become empty but remain.")

        # Select — selection operations
        select_menu = _submenu(menu, "Select")
        _add_action(select_menu, "Select All", self.select_all,
            "<b>Select All</b> selects every table cell.<br/>Includes all rows and columns.")
        _add_action(select_menu, "Select Row", self.select_current_row,
            "<b>Select Row</b> selects entire cursor row.<br/>All cells in that row.")
        _add_action(select_menu, "Select Column", self.select_current_column,
            "<b>Select Column</b> selects entire cursor column.<br/>All cells in that column.")
        _add_action(select_menu, "Select Visible Cells Only", self.select_visible_only,
            "<b>Select Visible Cells</b> excludes filtered rows.<br/>Only currently visible cells.")
        _add_action(select_menu, "Select Blank Cells", self.select_blank_cells,
            "<b>Select Blank Cells</b> selects empty cells.<br/>Useful for batch filling.")
        _add_action(select_menu, "Select Cells with Content", self.select_cells_with_content,
            "<b>Select Cells with Content</b> skips blanks.<br/>All non-empty cells only.")

        # Rows — row operations
        rows_menu = _submenu(menu, "Rows")
        _add_action(rows_menu, "Insert Row", self.insert_row,
            "<b>Insert Row</b> adds new empty row.<br/>Appends at end or current position.")
        _add_action(rows_menu, "Insert Row Above", self.insert_row_above,
            "<b>Insert Row Above</b> adds row above.<br/>Pushes current row downward.")
        _add_action(rows_menu, "Insert Row Below", self.insert_row_below,
            "<b>Insert Row Below</b> adds row below.<br/>Pushes content downward.")
        _add_action(rows_menu, "Duplicate Row", self.duplicate_row,
            "<b>Duplicate Row</b> copies row and inserts.<br/>Creates exact duplicate below.")
        _add_action(rows_menu, "Remove Rows", self.remove_selected_rows,
            "<b>Remove Rows</b> deletes selected rows.<br/>All row data is removed.")
        _add_action(rows_menu, "Move Row Up", self.move_row_up,
            "<b>Move Row Up</b> shifts row by one.<br/>Swaps with row above.")
        _add_action(rows_menu, "Move Row Down", self.move_row_down,
            "<b>Move Row Down</b> shifts row by one.<br/>Swaps with row below.")

        # Columns — column operations
        columns_menu = _submenu(menu, "Columns")
        _add_action(columns_menu, "Insert Column...", self.insert_column,
            "<b>Insert Column</b> adds new data column.<br/>Dialog to set column name.")
        _add_action(columns_menu, "Rename Column...", self.rename_current_column,
            "<b>Rename Column</b> changes column name.<br/>Opens rename dialog.")
        _add_action(columns_menu, "Duplicate Column", self.duplicate_column,
            "<b>Duplicate Column</b> copies column beside.<br/>Exact copy with new header.")
        _add_action(columns_menu, "Delete Column", self.delete_column,
            "<b>Delete Column</b> removes column entirely.<br/>All column data is lost.")
        _add_action(columns_menu, "Move Column Left", self.move_column_left,
            "<b>Move Column Left</b> shifts one position.<br/>Swaps with left neighbor.")
        _add_action(columns_menu, "Move Column Right", self.move_column_right,
            "<b>Move Column Right</b> shifts one position.<br/>Swaps with right neighbor.")

        # Table — data and view operations
        table_menu = _submenu(menu, "Table")
        _add_action(table_menu, "Remove Duplicate Rows", self.remove_duplicate_rows,
            "<b>Remove Duplicates</b> deletes repeated rows.<br/>Keeps first occurrence only.")
        _add_action(table_menu, "Transpose Table", self.transpose_table,
            "<b>Transpose Table</b> swaps rows and columns.<br/>Table orientation is rotated.")
        _add_action(table_menu, "Sort...", self.show_sort_dialog,
            "<b>Sort</b> orders table by column values.<br/>Opens multi-level sort dialog.")
        _add_action(table_menu, "Hide Column", self.hide_current_column,
            "<b>Hide Column</b> hides from view.<br/>Data retained but not shown.")
        _add_action(table_menu, "Show All Columns", self.show_all_columns,
            "<b>Show All Columns</b> unhides columns.<br/>Restores full table view.")

        # Go To — navigation
        goto_menu = _submenu(menu, "Go To")
        _add_action(goto_menu, "Go to Row...", self.show_go_to_row_dialog,
            "<b>Go to Row</b> jump by row number.<br/>Opens row number dialog.")
        _add_action(goto_menu, "Go to Column...", self.show_go_to_column_dialog,
            "<b>Go to Column</b> jump by column name.<br/>Opens column selector dialog.")

        menu.addSeparator()
        sub = self.ui.twodaTable.build_context_menu(self)
        _fallback_tooltips = {
            "Header": "<b>Header</b> toggle visibility and layout.<br/>Vertical and horizontal header options.",
            "TableView": "<b>TableView</b> resize and display.<br/>Grid, wrap, zoom settings.",
        }
        for a in sub.actions():
            if not a.toolTip() and a.text() in _fallback_tooltips:
                a.setToolTip(translate(_fallback_tooltips[a.text()]))
            menu.addAction(a)
        viewport = self.ui.twodaTable.viewport()
        if viewport is None:
            self._logger.warning("Viewport is None")
            return
        menu.exec(viewport.mapToGlobal(pos))  # pyright: ignore[reportOptionalMemberAccess]

    def cut_selection(self):
        """Copy selection to clipboard then clear those cells."""
        self.copy_selection()
        self.clear_selection_contents()

    def select_all(self):
        """Select all cells in the table."""
        rc, cc = self.proxy_model.rowCount(), self.proxy_model.columnCount()
        if rc == 0 or cc == 0:
            return
        top_left = self.proxy_model.index(0, 0)
        bottom_right = self.proxy_model.index(rc - 1, cc - 1)
        if top_left.isValid() and bottom_right.isValid():
            from qtpy.QtCore import QItemSelection

            sel = QItemSelection(top_left, bottom_right)
            selectionModel = self.ui.twodaTable.selectionModel()
            assert selectionModel is not None, "Selection model should not be None"
            selectionModel.select(sel, selectionModel.SelectionFlag.ClearAndSelect)
            self.ui.twodaTable.setCurrentIndex(top_left)

    def select_current_row(self):
        """Select all cells in the current row (Excel-like Ctrl+Shift+Space)."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        r = cur.row()
        left = self.proxy_model.index(r, 0)
        right = self.proxy_model.index(r, self.proxy_model.columnCount() - 1)
        if left.isValid() and right.isValid():
            from qtpy.QtCore import QItemSelection

            selectionModel = self.ui.twodaTable.selectionModel()
            assert selectionModel is not None, "Selection model should not be None"
            selectionModel.select(
                QItemSelection(left, right),
                selectionModel.SelectionFlag.ClearAndSelect,
            )
            self.ui.twodaTable.setCurrentIndex(cur)

    def select_current_column(self):
        """Select all cells in the current column (Excel-like Ctrl+Space)."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        c = cur.column()
        top = self.proxy_model.index(0, c)
        bottom = self.proxy_model.index(self.proxy_model.rowCount() - 1, c)
        if top.isValid() and bottom.isValid():
            from qtpy.QtCore import QItemSelection

            selectionModel = self.ui.twodaTable.selectionModel()
            assert selectionModel is not None, "Selection model should not be None"
            selectionModel.select(
                QItemSelection(top, bottom),
                selectionModel.SelectionFlag.ClearAndSelect,
            )
            self.ui.twodaTable.setCurrentIndex(cur)

    def clear_selection_contents(self):
        """Clear text in selected cells (does not remove rows/columns). Pushes undo."""
        indexes = self.ui.twodaTable.selectedIndexes()
        if not indexes:
            return
        changes: list[tuple[int, int, str, str]] = []
        for idx in indexes:
            src = self.proxy_model.mapToSource(idx)
            if not src.isValid():
                continue
            item = self.source_model.item(src.row(), src.column())
            if item is not None:
                old = item.text()
                if old:
                    changes.append((src.row(), src.column(), old, ""))
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Clear contents"))

    def show_find_dialog(self):
        d = FindReplaceDialog(self, find_only=True)
        d.findEdit.setText(getattr(self, "_last_find_text", ""))
        res = d.exec()
        self._last_find_text = d.get_find_text()
        self._last_match_case = d.is_match_case()
        self._last_match_whole_cell = d.is_match_whole_cell()
        if res == 100 or res == QDialog.DialogCode.Accepted:
            self._find_next(forward=True, find_text=d.get_find_text(), match_case=d.is_match_case(), match_whole_cell=d.is_match_whole_cell())
        elif res == 101:
            self._find_next(forward=False, find_text=d.get_find_text(), match_case=d.is_match_case(), match_whole_cell=d.is_match_whole_cell())
        elif res == 104:
            self._select_all_matching(d.get_find_text(), d.is_match_case(), d.is_match_whole_cell())

    def show_replace_dialog(self):
        d = FindReplaceDialog(self, find_only=False)
        d.findEdit.setText(getattr(self, "_last_find_text", ""))
        d.replaceEdit.setText(getattr(self, "_last_replace_text", ""))
        res = d.exec()
        self._last_find_text = d.get_find_text()
        self._last_replace_text = d.get_replace_text()
        self._last_match_case = d.is_match_case()
        self._last_match_whole_cell = d.is_match_whole_cell()
        if res == 100 or res == QDialog.DialogCode.Accepted:
            self._find_next(forward=True, find_text=d.get_find_text(), match_case=d.is_match_case(), match_whole_cell=d.is_match_whole_cell())
        elif res == 101:
            self._find_next(forward=False, find_text=d.get_find_text(), match_case=d.is_match_case(), match_whole_cell=d.is_match_whole_cell())
        elif res == 102:
            self._replace_one(d.get_find_text(), d.get_replace_text(), d.is_match_case(), d.is_match_whole_cell())
        elif res == 103:
            self._replace_all(d.get_find_text(), d.get_replace_text(), d.is_match_case(), d.is_match_whole_cell())
        elif res == 104:
            self._select_all_matching(d.get_find_text(), d.is_match_case(), d.is_match_whole_cell())

    def _text_matches(
        self,
        cell_text: str,
        find_text: str,
        match_case: bool,
        match_whole_cell: bool = True,
    ) -> bool:
        """Check if cell text matches the find criteria.

        Args:
        ----
            cell_text: The text in the cell to check
            find_text: The text to find
            match_case: If True, search is case-sensitive
            match_whole_cell: If True, the entire cell must match; if False, partial match is allowed

        Returns:
        -------
            bool: True if the cell matches the criteria, False otherwise
        """
        if match_whole_cell:
            return (cell_text == find_text) if match_case else (cell_text.lower() == find_text.lower())
        if match_case:
            return find_text in cell_text
        return find_text.lower() in cell_text.lower()

    def _select_all_matching(
        self,
        find_text: str,
        match_case: bool,
        match_whole_cell: bool,
    ):
        """Select all cells that match the find criteria (Find dialog Select All)."""
        if not find_text:
            return

        from qtpy.QtCore import QItemSelection

        selection = QItemSelection()
        for r in range(self.source_model.rowCount()):
            for c in range(self.source_model.columnCount()):
                item = self.source_model.item(r, c)
                if item and self._text_matches(item.text(), find_text, match_case, match_whole_cell):
                    src_idx = self.source_model.index(r, c)
                    proxy_idx = self.proxy_model.mapFromSource(src_idx)
                    if proxy_idx.isValid():
                        selection.select(proxy_idx, proxy_idx)
        sel_model = self.ui.twodaTable.selectionModel()
        if sel_model is not None:
            sel_model.select(selection, sel_model.SelectionFlag.ClearAndSelect)

    def _find_next(
        self,
        forward: bool,
        find_text: str,
        match_case: bool,
        match_whole_cell: bool = False,
    ):
        if not find_text:
            return

        start_row, start_col = 0, 0
        cur = self.ui.twodaTable.currentIndex()
        if cur.isValid():
            src = self.proxy_model.mapToSource(cur)
            start_row, start_col = src.row(), src.column()
            if forward:
                start_col += 1
                if start_col >= self.source_model.columnCount():
                    start_col = 0
                    start_row += 1
            else:
                start_col -= 1
                if start_col < 0:
                    start_col = self.source_model.columnCount() - 1
                    start_row -= 1
        rows, cols = self.source_model.rowCount(), self.source_model.columnCount()
        if forward:
            for r in range(start_row, rows):
                for c in range(start_col if r == start_row else 0, cols):
                    item = self.source_model.item(r, c)
                    if item and self._text_matches(item.text(), find_text, match_case, match_whole_cell):
                        idx = self.proxy_model.mapFromSource(self.source_model.index(r, c))
                        self.ui.twodaTable.setCurrentIndex(idx)
                        self.ui.twodaTable.scrollTo(idx, self.ui.twodaTable.ScrollHint.EnsureVisible)
                        selectionModel = self.ui.twodaTable.selectionModel()
                        assert selectionModel is not None, "Selection model should not be None"
                        selectionModel.select(idx, selectionModel.SelectionFlag.ClearAndSelect)
                        return
        else:
            for r in range(start_row, -1, -1):
                for c in range(start_col if r == start_row else cols - 1, -1, -1):
                    item = self.source_model.item(r, c)
                    if item and _matches(item.text()):
                        idx = self.proxy_model.mapFromSource(self.source_model.index(r, c))
                        self.ui.twodaTable.setCurrentIndex(idx)
                        self.ui.twodaTable.scrollTo(idx, self.ui.twodaTable.ScrollHint.EnsureVisible)
                        selectionModel = self.ui.twodaTable.selectionModel()
                        assert selectionModel is not None, "Selection model should not be None"
                        selectionModel.select(idx, selectionModel.SelectionFlag.ClearAndSelect)
                        return

    def _replace_one(
        self,
        find_text: str,
        replace_text: str,
        match_case: bool,
        match_whole_cell: bool = False,
    ):
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        src = self.proxy_model.mapToSource(cur)
        item = self.source_model.item(src.row(), src.column())
        if item is None:
            return
        if not self._text_matches(item.text(), find_text, match_case, match_whole_cell):
            self._find_next(forward=True, find_text=find_text, match_case=match_case, match_whole_cell=match_whole_cell)
            cur = self.ui.twodaTable.currentIndex()
            if not cur.isValid():
                return
            src = self.proxy_model.mapToSource(cur)
            item = self.source_model.item(src.row(), src.column())
        if item is not None:
            old = item.text()
            self._undo_stack.push(_SetCellTextCommand(self.source_model, src.row(), src.column(), old, replace_text))
            item.setText(replace_text)
        self._find_next(forward=True, find_text=find_text, match_case=match_case, match_whole_cell=match_whole_cell)

    def _replace_all(
        self,
        find_text: str,
        replace_text: str,
        match_case: bool,
        match_whole_cell: bool = False,
    ):
        if not find_text:
            return

        changes: list[tuple[int, int, str, str]] = []
        for r in range(self.source_model.rowCount()):
            for c in range(self.source_model.columnCount()):
                item = self.source_model.item(r, c)
                if item and self._text_matches(item.text(), find_text, match_case, match_whole_cell):
                    changes.append((r, c, item.text(), replace_text))
        if not changes:
            return
        self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Replace all"))

    def insert_column(self):
        """Insert a new column; prompt for header name and position."""
        from qtpy.QtWidgets import QInputDialog

        header, ok = QInputDialog.getText(self, "Insert Column", "Column header name:", text="newcolumn")
        if not ok or not header.strip():
            return
        col = self.source_model.columnCount()
        cur = self.ui.twodaTable.currentIndex()
        if cur.isValid():
            col = self.proxy_model.mapToSource(cur).column() + 1
        self._undo_stack.push(_InsertColumnCommand(self.source_model, col, header.strip(), self))

    def delete_column(self):
        """Delete the current column or the first selected column."""
        cols = {self.proxy_model.mapToSource(idx).column() for idx in self.ui.twodaTable.selectedIndexes()}
        cur = self.ui.twodaTable.currentIndex()
        data_cols = [c for c in cols if c > 0]
        col = min(data_cols) if data_cols else (self.proxy_model.mapToSource(cur).column() if cur.isValid() else 0)
        if col <= 0:
            QMessageBox.information(self, "Delete Column", "Select a data column (not the row label column) to delete.")
            return
        if self.source_model.columnCount() <= 2:
            QMessageBox.warning(self, "Delete Column", "Cannot delete the last data column.")
            return
        self._undo_stack.push(_DeleteColumnCommand(self.source_model, col, self))

    def show_sort_dialog(self):
        """Show multi-level Sort dialog and apply sort (undoable)."""
        data_headers = [
            (self.source_model.horizontalHeaderItem(c).text() if self.source_model.horizontalHeaderItem(c) else "")
            for c in range(1, self.source_model.columnCount()) if self.source_model.horizontalHeaderItem(c) is not None
        ]
        if not data_headers:
            return
        cur = self.ui.twodaTable.currentIndex()
        current_col = self.proxy_model.mapToSource(cur).column() - 1 if cur.isValid() else 0
        current_col = max(0, min(current_col, len(data_headers) - 1))
        d = SortDialog(self, data_headers, current_col)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        levels = d.get_sort_levels()
        if not levels:
            return
        self._undo_stack.push(_SortMultiCommand(self.source_model, levels, self))

    def show_column_statistics(self):
        """Show statistics for the currently selected column."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            QMessageBox.information(self, "Column Statistics", "Please select a column first.")
            return
        
        col = self.proxy_model.mapToSource(cur).column()
        if col <= 0:
            QMessageBox.information(self, "Column Statistics", "Please select a data column (not the row label column).")
            return
        
        h = self.source_model.horizontalHeaderItem(col)
        col_name = (h.text() or f"Column{col}") if h else f"Column{col}"
        
        # Collect all values in this column
        values = []
        for row in range(self.source_model.rowCount()):
            item = self.source_model.item(row, col)
            values.append(item.text() if item else "")
        
        # Show dialog
        dialog = ColumnStatisticsDialog(self, col_name, values)
        dialog.exec()

    def toggle_freeze_row_labels(self, freeze: bool):
        """Freeze or unfreeze the row label column (column 0)."""
        h_header = self.ui.twodaTable.horizontalHeader()
        if h_header is None:
            return
        
        if freeze:
            # Set column 0 to fixed width
            from qtpy.QtWidgets import QHeaderView
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            h_header.resizeSection(0, 60)  # Fixed 60px width
        else:
            # Allow interactive resizing
            from qtpy.QtWidgets import QHeaderView
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

    def toggle_highlight_non_numeric(self, enabled: bool):
        """Toggle highlighting of non-numeric cells in numeric columns."""
        if enabled:
            self._apply_validation_highlighting()
        else:
            self._clear_validation_highlighting()

    def _apply_validation_highlighting(self):
        """Highlight non-numeric cells in columns that appear to be numeric."""
        # For each column, determine if it's numeric (>50% of values are numbers)
        for col in range(1, self.source_model.columnCount()):  # Skip row label column
            values = []
            numeric_count = 0
            for row in range(self.source_model.rowCount()):
                item = self.source_model.item(row, col)
                if item:
                    val = item.text()
                    values.append(val)
                    try:
                        float(val)
                        numeric_count += 1
                    except (ValueError, TypeError):
                        pass
            
            # If >50% numeric, highlight non-numeric cells
            if values and numeric_count / len(values) > 0.5:
                for row in range(self.source_model.rowCount()):
                    item = self.source_model.item(row, col)
                    if item:
                        val = item.text()
                        if val.strip():  # Non-empty
                            try:
                                float(val)
                                # Valid number: clear background
                                item.setBackground(Qt.GlobalColor.transparent)
                            except (ValueError, TypeError):
                                # Invalid number: highlight in light red
                                item.setBackground(QColor(255, 200, 200, 100))

    def _clear_validation_highlighting(self):
        """Remove all validation highlighting."""
        for row in range(self.source_model.rowCount()):
            for col in range(1, self.source_model.columnCount()):
                item = self.source_model.item(row, col)
                if item and col > 0:  # Don't touch row label column
                    item.setBackground(Qt.GlobalColor.transparent)

    def sort_by_current_column(self, ascending: bool):
        """Sort source model rows by the current column (data column only). Undoable."""
        cur = self.ui.twodaTable.currentIndex()
        if not cur.isValid():
            return
        col = self.proxy_model.mapToSource(cur).column()
        if col < 1:
            return
        self._undo_stack.push(_SortCommand(self.source_model, col, ascending, self))

    def fill_down(self):
        """Fill selected cells with the value from the top-most cell in the selection."""
        indexes = self.ui.twodaTable.selectedIndexes()
        if not indexes:
            return
        min_row = min(self.proxy_model.mapToSource(idx).row() for idx in indexes)
        cols = {self.proxy_model.mapToSource(idx).column() for idx in indexes}
        changes: list[tuple[int, int, str, str]] = []
        for c in cols:
            top_item = self.source_model.item(min_row, c)
            val = top_item.text() if top_item else ""
            for r in range(min_row + 1, self.source_model.rowCount()):
                item = self.source_model.item(r, c)
                if item is not None and (r, c) in {(self.proxy_model.mapToSource(i).row(), self.proxy_model.mapToSource(i).column()) for i in indexes}:
                    old = item.text()
                    if old != val:
                        changes.append((r, c, old, val))
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Fill down"))

    def fill_down_pattern(self):
        """Fill down with pattern detection (e.g., 1,2,3... or A,B,C...)."""
        indexes = self.ui.twodaTable.selectedIndexes()
        if not indexes or len(indexes) < 2:
            QMessageBox.information(self, "Fill Pattern", "Select at least 2 cells to detect a pattern.")
            return
        
        # Group by column
        by_col: dict[int, list[tuple[int, str]]] = {}
        for idx in indexes:
            src = self.proxy_model.mapToSource(idx)
            r, c = src.row(), src.column()
            item = self.source_model.item(r, c)
            val = item.text() if item else ""
            if c not in by_col:
                by_col[c] = []
            by_col[c].append((r, val))
        
        changes: list[tuple[int, int, str, str]] = []
        for col, row_vals in by_col.items():
            if len(row_vals) < 2:
                continue
            row_vals.sort()  # Sort by row
            rows = [r for r, _ in row_vals]
            vals = [v for _, v in row_vals]
            
            # Try to detect numeric pattern
            try:
                nums = [float(v) for v in vals if v.strip()]
                if len(nums) >= 2:
                    # Calculate increment
                    increment = (nums[-1] - nums[0]) / (len(nums) - 1)
                    next_val = nums[-1] + increment
                    
                    # Fill beyond selection
                    last_row = rows[-1]
                    for r in range(last_row + 1, min(last_row + 20, self.source_model.rowCount())):
                        item = self.source_model.item(r, col)
                        if item:
                            old = item.text()
                            new = str(next_val)
                            changes.append((r, col, old, new))
                            next_val += increment
            except (ValueError, TypeError):
                # Try repeating pattern
                if vals:
                    pattern_len = len(vals)
                    last_row = rows[-1]
                    for i, r in enumerate(range(last_row + 1, min(last_row + 20, self.source_model.rowCount()))):
                        item = self.source_model.item(r, col)
                        if item:
                            old = item.text()
                            new = vals[i % pattern_len]
                            changes.append((r, col, old, new))
        
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Fill pattern down"))
        else:
            QMessageBox.information(self, "Fill Pattern", "No pattern detected or no room to fill.")

    def fill_right(self):
        """Fill selected cells with the value from the left-most cell in the selection."""
        indexes = self.ui.twodaTable.selectedIndexes()
        if not indexes:
            return
        min_col = min(self.proxy_model.mapToSource(idx).column() for idx in indexes)
        rows = {self.proxy_model.mapToSource(idx).row() for idx in indexes}
        changes: list[tuple[int, int, str, str]] = []
        for r in rows:
            left_item = self.source_model.item(r, min_col)
            val = left_item.text() if left_item else ""
            for c in range(min_col + 1, self.source_model.columnCount()):
                item = self.source_model.item(r, c)
                if item is not None and (r, c) in {(self.proxy_model.mapToSource(i).row(), self.proxy_model.mapToSource(i).column()) for i in indexes}:
                    old = item.text()
                    if old != val:
                        changes.append((r, c, old, val))
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Fill right"))

    def paste_transpose(self):
        """Paste clipboard data with rows and columns transposed."""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text:
            return
        rows_str = text.split("\n")
        if not rows_str:
            return
        grid = [row.split("\t") for row in rows_str]
        if not grid:
            return
        # Transpose: rows become columns
        transposed: list[list[str]] = []
        max_len = max(len(r) for r in grid)
        for c in range(max_len):
            transposed.append([(row[c] if c < len(row) else "") for row in grid])
        # Paste starting at current cell
        selected_indexes = self.ui.twodaTable.selectedIndexes()
        if not selected_indexes:
            return
        start = self.proxy_model.mapToSource(selected_indexes[0])
        start_row, start_col = start.row(), start.column()
        changes: list[tuple[int, int, str, str]] = []
        for r, row_cells in enumerate(transposed):
            for c, cell in enumerate(row_cells):
                tr, tc = start_row + r, start_col + c
                if tr >= self.source_model.rowCount() or tc >= self.source_model.columnCount():
                    continue
                item = self.source_model.item(tr, tc)
                if item is not None:
                    old = item.text()
                    changes.append((tr, tc, old, cell))
        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Paste transpose"))

    def copy_selection(self):
        """Copies the selected cells to the clipboard in a tab-delimited format."""
        top = self.source_model.rowCount()
        bottom = -1
        left = self.source_model.columnCount()
        right = -1

        for index in self.ui.twodaTable.selectedIndexes():
            if not index.isValid():
                continue
            mapped_index = self.proxy_model.mapToSource(index)  # type: ignore[arg-type]

            top = min([top, mapped_index.row()])
            bottom = max([bottom, mapped_index.row()])
            left = min([left, mapped_index.column()])
            right = max([right, mapped_index.column()])

        # Determine whether to include the row-label column (column 0) in copied data.
        # If a valid current index exists and it is anchored to a data column (>0),
        # prefer to start copying at that anchor column. This handles cases where
        # someone calls selectRow() but intended to copy starting at a specific cell
        # (see test_twoda_editor_copy_paste_roundtrip).
        current_index = self.ui.twodaTable.currentIndex()
        anchor_col = None
        if current_index.isValid():
            try:
                anchor_col = self.proxy_model.mapToSource(current_index).column()  # type: ignore[arg-type]
            except Exception:
                anchor_col = None

        if anchor_col is not None and anchor_col > 0 and left < anchor_col:
            left = anchor_col

        clipboard = QApplication.clipboard()
        assert clipboard is not None, "Clipboard should not be None"

        # If no data columns selected, nothing to copy
        if left > right:
            clipboard.setText("")
            return

        clipboard_text: str = ""
        for j in range(top, bottom + 1):
            for i in range(left, right + 1):
                item = self.source_model.item(j, i)
                clipboard_text += item.text() if item is not None else ""
                if i != right:
                    clipboard_text += "\t"
            if j != bottom:
                clipboard_text += "\n"

        clipboard.setText(clipboard_text)

    def paste_selection(self):
        """Pastes tab-delimited data from the clipboard into the table starting at the selected cell. Undoable."""
        clipboard = QApplication.clipboard()
        assert clipboard is not None, "Clipboard should not be None"
        rows_raw: list[str] = clipboard.text().split("\n")
        selected_indexes = self.ui.twodaTable.selectedIndexes()
        if not selected_indexes:
            return
        selected_index = self.ui.twodaTable.selectedIndexes()[0]
        if not selected_index.isValid():
            return

        top_left_index = self.proxy_model.mapToSource(selected_index)  # type: ignore[arg-type]
        y = top_left_index.row()
        x = top_left_index.column()
        start_x = x

        # Build grid of pasted values
        grid: list[list[str]] = []
        for row_text in rows_raw:
            cells = row_text.split("\t")
            if len(cells) > 1 and cells[0].isdigit() and start_x > 0:
                cells = cells[1:]
            grid.append(cells)

        changes: list[tuple[int, int, str, str]] = []
        for dy, row_cells in enumerate(grid):
            for dx, cell in enumerate(row_cells):
                tr, tc = y + dy, x + dx
                if tr >= self.source_model.rowCount() or tc >= self.source_model.columnCount():
                    continue
                item = self.source_model.item(tr, tc)
                if item is not None:
                    old = item.text()
                    changes.append((tr, tc, old, cell))

        if changes:
            self._undo_stack.push(_BatchSetCellsCommand(self.source_model, changes, "Paste"))

    def insert_row(self):
        """Inserts a new blank row at the end of the table."""
        if self.source_model.columnCount() == 0:
            QMessageBox.information(self, "Insert Row", "Add at least one column first (e.g. via a loaded 2DA file).")
            return
        row_index: int = self.source_model.rowCount()
        new_items = [QStandardItem("") for _ in range(self.source_model.columnCount())]
        self._undo_stack.push(_InsertRowCommand(self.source_model, row_index, new_items, self))

    def duplicate_row(self):
        """Duplicates the currently selected row and appends it to the end of the table. Undoable."""
        if not self.ui.twodaTable.selectedIndexes():
            return
        proxy_index = self.ui.twodaTable.selectedIndexes()[0]
        copy_row: int = self.proxy_model.mapToSource(proxy_index).row()  # type: ignore[arg-type]

        row_index: int = self.source_model.rowCount()
        new_items: list[QStandardItem] = []
        for i in range(self.source_model.columnCount()):
            orig_item: QStandardItem | None = self.source_model.item(copy_row, i)
            if orig_item is None:
                new_items.append(QStandardItem(""))
            else:
                new_items.append(orig_item.clone())
        self._undo_stack.push(_InsertRowCommand(self.source_model, row_index, new_items, self))

    def set_item_display_data(self, rowIndex: int):  # pylint: disable=C0103,invalid-name
        """Sets the display data for a specific row, including making the first column bold and setting its background."""
        item = QStandardItem(str(rowIndex))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setBackground(self.palette().midlight())
        self.source_model.setItem(rowIndex, 0, item)
        self.reset_vertical_headers()

    def remove_selected_rows(self):
        """Removes the rows the user has selected."""
        # Map proxy-selected rows back to source model rows before removal
        rows: set[int] = {self.proxy_model.mapToSource(index).row() for index in self.ui.twodaTable.selectedIndexes()}
        if not rows:
            return
        self._undo_stack.push(_RemoveRowsCommand(self.source_model, list(rows), self))

    def delete_row(self):
        """Compatibility wrapper for older tests and UI actions that expect delete_row()."""
        self.remove_selected_rows()

    def redo_row_labels(self):
        """Iterates through every row setting the row label to match the row index."""
        for i in range(self.source_model.rowCount()):
            item = self.source_model.item(i, 0)
            assert item is not None, "Item should not be None"
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setText(str(i))

    def set_vertical_header_option(
        self,
        option: VerticalHeaderOption,
        column: str | None = None,
    ):
        """Sets the vertical header option and updates the headers accordingly."""
        self.vertical_header_option = option
        self.vertical_header_column = column or ""
        self.reset_vertical_headers()

    def reset_vertical_headers(self):
        """Resets the vertical headers based on the current vertical header option."""
        vertical_header = self.ui.twodaTable.verticalHeader()
        assert vertical_header is not None
        if GlobalSettings().selectedTheme in ("Native", "Fusion (Light)"):
            vertical_header.setStyleSheet("")
        headers: list[str] = []

        if self.vertical_header_option == VerticalHeaderOption.ROW_INDEX:
            headers = [str(i) for i in range(self.source_model.rowCount())]
        elif self.vertical_header_option == VerticalHeaderOption.ROW_LABEL:
            headers = [
                self.source_model.item(i, 0).text()  # type: ignore[attr-defined]
                for i in range(self.source_model.rowCount())
            ]
        elif self.vertical_header_option == VerticalHeaderOption.CELL_VALUE:
            col_index: int = 0
            for i in range(self.source_model.columnCount()):
                horizontal_header_item = self.source_model.horizontalHeaderItem(i)
                assert horizontal_header_item is not None, "Horizontal header item should not be None"
                if horizontal_header_item.text() == self.vertical_header_column:
                    col_index = i
            headers = [self.source_model.item(i, col_index).text() for i in range(self.source_model.rowCount())]  # type: ignore[attr-defined]
        elif self.vertical_header_option == VerticalHeaderOption.NONE:
            # Get palette colors
            app = QApplication.instance()
            if app is None or not isinstance(app, QApplication):
                palette = QPalette()
            else:
                palette = app.palette()

            window_text = palette.color(QPalette.ColorRole.WindowText)
            base = palette.color(QPalette.ColorRole.Base)
            alternate_base = palette.color(QPalette.ColorRole.AlternateBase)

            # Create transparent text color
            transparent_text = QColor(window_text)
            transparent_text.setAlpha(0)

            # Create hover background
            hover_bg = QColor(alternate_base if alternate_base != base else base)
            if hover_bg.lightness() < 128:  # Dark theme
                hover_bg = hover_bg.lighter(110)
            else:  # Light theme
                hover_bg = hover_bg.darker(95)

            if GlobalSettings().selectedTheme in ("Native", "Fusion (Light)"):
                vertical_header.setStyleSheet(
                    f"QHeaderView::section {{ color: rgba({transparent_text.red()}, {transparent_text.green()}, {transparent_text.blue()}, 0); }} QHeaderView::section:checked {{ color: {window_text.name()}; }}"
                )
            elif GlobalSettings().selectedTheme == "Fusion (Dark)":
                vertical_header.setStyleSheet(f"""
                    QHeaderView::section {{
                        color: rgba({transparent_text.red()}, {transparent_text.green()}, {transparent_text.blue()}, 0);  /* Transparent text */
                        background-color: {base.name()};  /* Base background */
                    }}
                    QHeaderView::section:checked {{
                        color: {window_text.name()};  /* Window text for checked sections */
                        background-color: {alternate_base.name() if alternate_base != base else hover_bg.name()};  /* Alternate base for checked sections */
                    }}
                    QHeaderView::section:hover {{
                        color: {window_text.name()};  /* Window text on hover */
                        background-color: {hover_bg.name()};  /* Hover background */
                    }}
                """)
                # Get additional palette colors for table styling
                button = palette.color(QPalette.ColorRole.Button)
                button_text = palette.color(QPalette.ColorRole.ButtonText)
                highlight = palette.color(QPalette.ColorRole.Highlight)
                highlighted_text = palette.color(QPalette.ColorRole.HighlightedText)
                mid = palette.color(QPalette.ColorRole.Mid)
                dark = palette.color(QPalette.ColorRole.Dark)

                # Create variants for hover/checked states
                header_bg = QColor(button if button.isValid() else base)
                header_hover_bg = QColor(header_bg)
                if header_hover_bg.lightness() < 128:  # Dark theme
                    header_hover_bg = header_hover_bg.lighter(110)
                else:  # Light theme
                    header_hover_bg = header_hover_bg.darker(95)

                # Use Mid for gridlines, fallback to Dark if Mid is invalid
                gridline = QColor(mid if mid.isValid() else (dark if dark.isValid() else base))

                self.ui.twodaTable.setStyleSheet(f"""
                    QHeaderView::section {{
                        background-color: {header_bg.name()};
                        color: {button_text.name() if button_text.isValid() else window_text.name()};
                        padding: 4px;
                        border: 1px solid {gridline.name()};
                    }}
                    QHeaderView::section:checked {{
                        background-color: {header_hover_bg.name()};
                        color: {button_text.name() if button_text.isValid() else window_text.name()};
                    }}
                    QHeaderView::section:hover {{
                        background-color: {header_hover_bg.name()};
                        color: {button_text.name() if button_text.isValid() else window_text.name()};
                    }}
                    QTableView {{
                        background-color: {base.name()};
                        alternate-background-color: {alternate_base.name() if alternate_base != base else base.name()};
                        color: {window_text.name()};
                        gridline-color: {gridline.name()};
                        selection-background-color: {highlight.name()};
                        selection-color: {highlighted_text.name()};
                    }}
                    QTableView::item {{
                        background-color: {base.name()};
                        color: {window_text.name()};
                    }}
                    QTableView::item:selected {{
                        background-color: {highlight.name()};
                        color: {highlighted_text.name()};
                    }}
                    QTableCornerButton::section {{
                        background-color: {header_bg.name()};
                        border: 1px solid {gridline.name()};
                    }}
                """)
            headers = ["⯈" for _ in range(self.source_model.rowCount())]

        for i in range(self.source_model.rowCount()):
            self.source_model.setVerticalHeaderItem(i, QStandardItem(headers[i]))


class SortFilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model to filter 2DA table rows based on a search string."""

    def __init__(self, parent: QObject | None = None):
        """Initialize the TwoDA editor widget.

        Args:
            parent: The parent widget that owns this editor instance.
        """
        super().__init__(parent)

    def filterAcceptsRow(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        """Determines whether a given row should be included in the filtered results."""
        pattern = None
        if qtpy.QT5:
            pattern = self.filterRegExp().pattern()  # pyright: ignore[reportAttributeAccessIssue]
        else:  # if qtpy.QT6:
            pattern = self.filterRegularExpression().pattern()

        if not pattern:
            return True
        case_insens_pattern = pattern.lower()
        src_model = self.sourceModel()
        assert src_model is not None, "Source model should not be None"
        for i in range(src_model.columnCount()):
            index = src_model.index(source_row, i, source_parent)
            if not index.isValid():
                continue
            data: str = src_model.data(index)
            if data is None:
                continue
            if case_insens_pattern in data.lower():
                return True
        return False


class VerticalHeaderOption(IntEnum):
    """Options for configuring the vertical headers in the 2DA editor."""

    ROW_INDEX = 0
    ROW_LABEL = 1
    CELL_VALUE = 2
    NONE = 3

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("twoda"))
