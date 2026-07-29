"""Qt resource and 2DA browser panels for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets
from src.gui.qt_lib.assets.qt_theme import heading
from src.gui.qt_lib.windows.progress_toast import (
    FeedbackAction,
    OperationFeedback,
    OperationPhase,
    QtProgressPanel,
)


class Qt2DABrowserPanel(QtWidgets.QWidget):
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
        self.game_combo.setAccessibleName("Filter resources by game")
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["All", "MDL", "MDX", "TPC", "TGA", "2DA", "DLG", "UTC", "UTI", "ARE", "GIT", "IFO", "WOK"])
        self.type_combo.setAccessibleName("Filter resources by type")
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter resources")
        self.search_edit.setAccessibleName("Filter resources by name")
        top.addWidget(self.game_combo)
        top.addWidget(self.type_combo)
        top.addWidget(self.search_edit, 1)
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.setAccessibleName("Scan game resources")
        self.scan_button.clicked.connect(self.scanRequested.emit)
        top.addWidget(self.scan_button)
        root.addLayout(top)
        self.feedback_panel = QtProgressPanel()
        self.feedback_panel.actionTriggered.connect(self._handle_feedback_action)
        self.feedback_panel.set_feedback(
            OperationFeedback(
                phase=OperationPhase.IDLE,
                title="Resource Browser is ready",
                detail="Select Scan to index resources, or use the filters after a scan.",
            )
        )
        root.addWidget(self.feedback_panel)
        splitter = QtWidgets.QSplitter()
        self.listbox = QtWidgets.QListWidget()
        self.listbox.setAccessibleName("Available resources")
        self.listbox.currentItemChanged.connect(self._on_current_item_changed)
        self.listbox.itemDoubleClicked.connect(self._on_item_activated)
        self.preview_tabs = QtWidgets.QTabWidget()
        self.preview_tabs.setAccessibleName("Selected resource preview")
        self.text_preview = QtWidgets.QPlainTextEdit()
        self.text_preview.setAccessibleName("Text preview")
        self.hex_preview = QtWidgets.QPlainTextEdit()
        self.hex_preview.setAccessibleName("Hex preview")
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
        visible_count = self.listbox.count()
        if visible_count:
            noun = "resource" if visible_count == 1 else "resources"
            self.feedback_panel.set_feedback(
                OperationFeedback(
                    phase=OperationPhase.READY,
                    title=f"{visible_count} {noun} available",
                    detail="Select a resource to preview it, or double-click to use it.",
                )
            )
        elif self._rows:
            subject = needle or "Current game and type filters"
            scopes = self._active_filter_scopes()
            self.feedback_panel.set_feedback(
                OperationFeedback(
                    phase=OperationPhase.BLOCKED,
                    title="No resources match these filters",
                    detail="Your indexed resources are still available. Clear or change the filters to see them.",
                    subject=subject,
                    reason="The current filters excluded every indexed resource.",
                    searched_scopes=scopes,
                    actions=(
                        FeedbackAction(
                            "clear_filters",
                            "Clear Filters",
                            "Show all indexed resources.",
                        ),
                        FeedbackAction(
                            "scan_resources",
                            "Scan Again",
                            "Refresh the resource catalog from configured game directories.",
                        ),
                    ),
                    preserves_work=True,
                )
            )
        else:
            self.feedback_panel.set_feedback(
                OperationFeedback(
                    phase=OperationPhase.BLOCKED,
                    title="No resources were indexed",
                    detail="Select Scan to search the configured KotOR game directories.",
                    reason="The resource catalog is empty.",
                    actions=(
                        FeedbackAction(
                            "scan_resources",
                            "Scan Resources",
                            "Search the configured game directories now.",
                        ),
                    ),
                    preserves_work=True,
                )
            )

    def show_lookup_failure(self, error: BaseException) -> None:
        failure = getattr(error, "failure", None)
        subject = getattr(failure, "subject", "") or str(error)
        reason = getattr(failure, "reason", "") or "The requested resource could not be resolved."
        scopes = tuple(getattr(failure, "searched_scopes", ()) or ())
        self.feedback_panel.set_feedback(
            OperationFeedback(
                phase=OperationPhase.FAILED,
                title="Resource could not be found",
                detail="Review the searched locations, scan again, or choose another resource.",
                subject=subject,
                reason=reason,
                searched_scopes=scopes,
                actions=(
                    FeedbackAction(
                        "scan_resources",
                        "Scan Again",
                        "Refresh the resource catalog from configured game directories.",
                    ),
                    FeedbackAction(
                        "choose_another",
                        "Choose Another",
                        "Return focus to the resource search.",
                    ),
                ),
                preserves_work=True,
            )
        )

    def show_loading(self, detail: str = "Scanning configured game directories...") -> None:
        self.feedback_panel.set_feedback(
            OperationFeedback(
                phase=OperationPhase.BUSY,
                title="Scanning resources",
                detail=detail,
            )
        )

    def show_scan_failed(self, reason: str) -> None:
        self.feedback_panel.set_feedback(
            OperationFeedback(
                phase=OperationPhase.FAILED,
                title="Resource scan failed",
                detail="Check the configured game directories, then try again.",
                reason=reason,
                actions=(
                    FeedbackAction("scan_resources", "Retry Scan", "Try the resource scan again."),
                ),
                preserves_work=True,
            )
        )

    def _active_filter_scopes(self) -> tuple[str, ...]:
        scopes: list[str] = []
        game_filter = self.game_combo.currentText()
        type_filter = self.type_combo.currentText()
        if game_filter != "All":
            scopes.append(f"{game_filter} resources")
        if type_filter != "All":
            scopes.append(f"{type_filter} resource type")
        if self.search_edit.text().strip():
            scopes.append("indexed resource names")
        return tuple(scopes or ["all indexed resources"])

    def _handle_feedback_action(self, key: str) -> None:
        if key in {"scan_resources", "refresh_resources"}:
            self.scanRequested.emit()
        elif key == "clear_filters":
            blockers = (
                QtCore.QSignalBlocker(self.game_combo),
                QtCore.QSignalBlocker(self.type_combo),
                QtCore.QSignalBlocker(self.search_edit),
            )
            self.game_combo.setCurrentIndex(0)
            self.type_combo.setCurrentIndex(0)
            self.search_edit.clear()
            del blockers
            self._apply_filter()
        elif key == "choose_another":
            self.search_edit.setFocus(QtCore.Qt.OtherFocusReason)

    def _on_current_item_changed(self, current, _previous) -> None:
        if not current:
            return
        row = current.data(QtCore.Qt.UserRole) or {}
        self.resourceSelected.emit(row)

    def _on_item_activated(self, item) -> None:
        row = item.data(QtCore.Qt.UserRole) or {}
        self.resourceActivated.emit(row)
