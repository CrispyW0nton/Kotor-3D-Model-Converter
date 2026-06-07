"""Qt resource and 2DA browser panels for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import heading


class QtTwoDaBrowserPanel(QtWidgets.QWidget):
    refreshRequested = QtCore.Signal(str)
    tableSelected = QtCore.Signal(str, str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("2DA Browser"))
        top = QtWidgets.QHBoxLayout()
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(["K1", "K2"])
        top.addWidget(self.game_combo)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(lambda: self.refreshRequested.emit(self.game_combo.currentText()))
        top.addWidget(refresh)
        root.addLayout(top)
        splitter = QtWidgets.QSplitter()
        self.listbox = QtWidgets.QListWidget()
        self.listbox.currentTextChanged.connect(
            lambda name: self.tableSelected.emit(self.game_combo.currentText(), name)
        )
        self.listbox.itemDoubleClicked.connect(
            lambda item: self.tableSelected.emit(self.game_combo.currentText(), item.text())
        )
        self.table = QtWidgets.QTableWidget()
        splitter.addWidget(self.listbox)
        splitter.addWidget(self.table)
        splitter.setSizes([180, 520])
        root.addWidget(splitter, 1)


class QtResourceBrowserPanel(QtWidgets.QWidget):
    scanRequested = QtCore.Signal()
    resourceSelected = QtCore.Signal(dict)
    resourceActivated = QtCore.Signal(dict)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Resources"))
        top = QtWidgets.QHBoxLayout()
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(["All", "K1", "K2"])
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["All", "MDL", "MDX", "TPC", "TGA", "2DA", "DLG", "UTC", "UTI", "ARE", "GIT", "IFO", "WOK"])
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter resources")
        top.addWidget(self.game_combo)
        top.addWidget(self.type_combo)
        top.addWidget(self.search_edit, 1)
        scan = QtWidgets.QPushButton("Scan")
        scan.clicked.connect(self.scanRequested.emit)
        top.addWidget(scan)
        root.addLayout(top)
        splitter = QtWidgets.QSplitter()
        self.listbox = QtWidgets.QListWidget()
        self.listbox.currentItemChanged.connect(self._on_current_item_changed)
        self.listbox.itemDoubleClicked.connect(self._on_item_activated)
        self.preview_tabs = QtWidgets.QTabWidget()
        self.text_preview = QtWidgets.QPlainTextEdit()
        self.hex_preview = QtWidgets.QPlainTextEdit()
        self.preview_tabs.addTab(self.text_preview, "Text")
        self.preview_tabs.addTab(self.hex_preview, "Hex")
        splitter.addWidget(self.listbox)
        splitter.addWidget(self.preview_tabs)
        splitter.setSizes([260, 420])
        root.addWidget(splitter, 1)
        self.game_combo.currentTextChanged.connect(lambda _text: self._apply_filter())
        self.type_combo.currentTextChanged.connect(lambda _text: self._apply_filter())
        self.search_edit.textChanged.connect(lambda _text: self._apply_filter())

    def set_resources(self, rows: list[dict]) -> None:
        self._rows = list(rows)
        self._apply_filter()

    def _apply_filter(self) -> None:
        self.listbox.clear()
        game_filter = self.game_combo.currentText().upper()
        type_filter = self.type_combo.currentText().lower()
        needle = self.search_edit.text().lower().strip()
        for row in self._rows:
            game = str(row.get("game") or "").upper()
            ext = str(row.get("type") or row.get("ext") or "mdl").lower()
            name = str(row.get("resref") or row.get("name") or "")
            if game_filter != "ALL" and game != game_filter:
                continue
            if type_filter != "all" and ext != type_filter:
                continue
            if needle and needle not in name.lower():
                continue
            item = QtWidgets.QListWidgetItem(f"{name}.{ext}  [{row.get('game', '')}]")
            item.setData(QtCore.Qt.UserRole, row)
            self.listbox.addItem(item)

    def _on_current_item_changed(self, current, _previous) -> None:
        if not current:
            return
        row = current.data(QtCore.Qt.UserRole) or {}
        self.resourceSelected.emit(row)

    def _on_item_activated(self, item) -> None:
        row = item.data(QtCore.Qt.UserRole) or {}
        self.resourceActivated.emit(row)
