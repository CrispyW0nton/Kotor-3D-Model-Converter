"""Presentation-only NWScript function and constant reference page."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from PySide6 import QtCore, QtWidgets


ROW_ROLE = int(QtCore.Qt.UserRole) + 91


class QtNWScriptReferencePage(QtWidgets.QWidget):
    searchRequested = QtCore.Signal(str, str, str, str)
    insertRequested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioNWScriptReferencePage")
        self.setProperty("ghostLayoutId", "scriptingDialogueStudio.reference")
        self._game = "K2"
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._request_search)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        header = QtWidgets.QLabel("NWScript Function Reference")
        header.setObjectName("scriptingStudioReferenceHeading")
        font = header.font()
        font.setBold(True)
        font.setPointSize(max(12, font.pointSize() + 2))
        header.setFont(font)
        root.addWidget(header)
        explanation = QtWidgets.QLabel(
            "Search the exact K1/K2 definitions used by GhostStudio's compiler. Double-click a function or use Insert Call to place it in the active script."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("scriptingStudioReferenceExplanation")
        root.addWidget(explanation)

        filters = QtWidgets.QHBoxLayout()
        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.setObjectName("scriptingStudioReferenceKindCombo")
        self.kind_combo.addItem("Engine functions", "function")
        self.kind_combo.addItem("Constants", "constant")
        filters.addWidget(self.kind_combo)
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setObjectName("scriptingStudioReferenceCategoryCombo")
        self.category_combo.addItem("All categories", "")
        filters.addWidget(self.category_combo)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("scriptingStudioReferenceSearchEdit")
        self.search_edit.setPlaceholderText("Search name, signature, or description…")
        self.search_edit.setClearButtonEnabled(True)
        filters.addWidget(self.search_edit, 1)
        root.addLayout(filters)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setObjectName("scriptingStudioReferenceSplitter")
        self.results = QtWidgets.QTreeWidget()
        self.results.setObjectName("scriptingStudioReferenceResults")
        self.results.setHeaderLabels(["Name", "Signature / Value", "Category"])
        self.results.setAlternatingRowColors(True)
        self.results.setSortingEnabled(True)
        self.results.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.results.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.results.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        splitter.addWidget(self.results)
        details_panel = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details_panel)
        details_layout.setContentsMargins(6, 0, 0, 0)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setObjectName("scriptingStudioReferenceDetails")
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details, 1)
        self.insert_button = QtWidgets.QPushButton("Insert Call in Active Script")
        self.insert_button.setObjectName("scriptingStudioReferenceInsertButton")
        details_layout.addWidget(self.insert_button)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        self.splitter = splitter
        self.summary_label = QtWidgets.QLabel("Loading definitions…")
        self.summary_label.setObjectName("scriptingStudioReferenceSummary")
        root.addWidget(self.summary_label)

        self.search_edit.textChanged.connect(lambda _text: self._timer.start())
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)
        self.category_combo.currentIndexChanged.connect(lambda _index: self._timer.start())
        self.results.currentItemChanged.connect(self._selection_changed)
        self.results.itemDoubleClicked.connect(lambda _item, _column: self._insert_current())
        self.insert_button.clicked.connect(self._insert_current)

    def set_game(self, game: str) -> None:
        target = str(game or "K2").upper()
        if target != self._game:
            self._game = target
            self._request_search()

    def set_categories(self, categories: Sequence[str]) -> None:
        selected = str(self.category_combo.currentData() or "")
        blocker = QtCore.QSignalBlocker(self.category_combo)
        self.category_combo.clear()
        self.category_combo.addItem("All categories", "")
        for category in categories:
            self.category_combo.addItem(str(category), str(category))
        index = self.category_combo.findData(selected)
        self.category_combo.setCurrentIndex(max(0, index))
        del blocker

    def set_rows(self, rows: Sequence[Mapping[str, Any]], *, summary: str = "") -> None:
        self.results.clear()
        for source in rows:
            row = dict(source)
            signature = str(row.get("signature") or row.get("value") or "")
            item = QtWidgets.QTreeWidgetItem(
                [str(row.get("name") or ""), signature, str(row.get("category") or "")]
            )
            item.setData(0, ROW_ROLE, row)
            self.results.addTopLevelItem(item)
        self.summary_label.setText(summary or f"{len(rows)} definition(s)")
        if self.results.topLevelItemCount():
            self.results.setCurrentItem(self.results.topLevelItem(0))
        else:
            self.details.clear()
        self._selection_changed(self.results.currentItem(), None)

    def _kind_changed(self, _index: int) -> None:
        self.category_combo.setEnabled(self.kind_combo.currentData() == "function")
        self.insert_button.setText(
            "Insert Call in Active Script" if self.kind_combo.currentData() == "function" else "Insert Constant in Active Script"
        )
        self._request_search()

    def _request_search(self) -> None:
        self.searchRequested.emit(
            self._game,
            str(self.kind_combo.currentData() or "function"),
            self.search_edit.text(),
            str(self.category_combo.currentData() or ""),
        )

    def _selection_changed(self, current: QtWidgets.QTreeWidgetItem | None, _previous: object) -> None:
        row = dict(current.data(0, ROW_ROLE) or {}) if current is not None else {}
        description = str(row.get("description") or "").strip()
        detail = str(row.get("signature") or row.get("value") or "")
        if description:
            detail = f"{detail}\n\n{description}"
        self.details.setPlainText(detail)
        self.insert_button.setEnabled(bool(row.get("insert_text")))

    def _insert_current(self) -> None:
        item = self.results.currentItem()
        row = dict(item.data(0, ROW_ROLE) or {}) if item is not None else {}
        text = str(row.get("insert_text") or "")
        if text:
            self.insertRequested.emit(text)

    def apply_ghost_theme(self, theme: object) -> None:
        self.update()

    def apply_ghost_layout(self, layout: object) -> None:
        spacing = getattr(layout, "spacing_value", None)
        if callable(spacing):
            self.splitter.setHandleWidth(spacing("splitterHandleWidth", 6))


__all__ = ["QtNWScriptReferencePage"]
