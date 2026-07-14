"""Project/history and package/Override pages for Scripting Studio.

These widgets are presentation-only.  They expose user intent through Qt
signals and accept immutable dictionaries/lists from a controller.  Project
creation, resource import, revision snapshots, archive writes, and game-install
writes remain owned by the Qt-free scripting services.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Sequence

from PySide6 import QtCore, QtGui, QtWidgets


PAGE_ROW_ROLE = int(QtCore.Qt.UserRole) + 74


def _icon(widget: QtWidgets.QWidget, standard: QtWidgets.QStyle.StandardPixmap) -> QtGui.QIcon:
    return widget.style().standardIcon(standard)


def _readable_status(value: object, fallback: str = "Not ready") -> str:
    text = str(value or fallback).strip().replace("_", " ")
    return text[:1].upper() + text[1:] if text else fallback


class NarrativeAssetFilterModel(QtCore.QSortFilterProxyModel):
    """Fast asset inventory filtering without rebuilding the source model."""

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._query = ""
        self._restype = "all"
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def set_filters(self, query: str, restype: str) -> None:
        self.beginFilterChange()
        self._query = str(query or "").strip().casefold()
        self._restype = str(restype or "all").strip().casefold()
        self.endFilterChange()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        index = self.sourceModel().index(source_row, 0, source_parent)
        row = dict(index.data(PAGE_ROW_ROLE) or {})
        if self._restype not in {"", "all"} and str(row.get("restype") or "").casefold() != self._restype:
            return False
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("resref", "restype", "role", "path", "status", "dependency_summary")
        ).casefold()
        return not self._query or self._query in haystack


class QtScriptingProjectHistoryPage(QtWidgets.QWidget):
    """Roomy project inventory, revision history, and recent-project surface."""

    newProjectRequested = QtCore.Signal(object)
    openProjectRequested = QtCore.Signal()
    saveProjectRequested = QtCore.Signal()
    importAssetsRequested = QtCore.Signal()
    refreshInventoryRequested = QtCore.Signal()
    validateProjectRequested = QtCore.Signal()
    assetActivated = QtCore.Signal(object)
    createRevisionRequested = QtCore.Signal(str)
    recoverRevisionRequested = QtCore.Signal(str)
    recoverAssetRevisionRequested = QtCore.Signal(str, str)
    recoverLegacyHistoryRequested = QtCore.Signal(str)
    openLegacyQuestRequested = QtCore.Signal(str)
    recentProjectActivated = QtCore.Signal(str)
    forgetRecentRequested = QtCore.Signal(str)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        theme_manager: Any = None,
        layout_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioProjectHistoryPage")
        self.setProperty("ghostLayoutId", "scriptingStudioProjectHistory")
        self._project: dict[str, Any] = {}
        self._asset_rows: list[dict[str, Any]] = []
        self._revision_rows: list[dict[str, Any]] = []
        self._legacy_history_rows: list[dict[str, Any]] = []
        self._export_history_rows: list[dict[str, Any]] = []
        self._recent_rows: list[dict[str, Any]] = []
        self._build_ui()
        self._bind_theme_layout(theme_manager, layout_manager)
        self.set_project({})

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(7)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Narrative Project & History")
        title.setObjectName("scriptingStudioProjectHeading")
        title.setProperty("headingLevel", 1)
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.project_status_label = QtWidgets.QLabel("No project open")
        self.project_status_label.setObjectName("scriptingStudioProjectStatusLabel")
        title_row.addWidget(self.project_status_label)
        outer.addLayout(title_row)

        explanation = QtWidgets.QLabel(
            "Keep scripts, dialogues, quests, tables, and blueprints in one portable project. "
            "History snapshots recover into a new folder, so the live project is never silently overwritten."
        )
        explanation.setObjectName("scriptingStudioProjectGuidanceLabel")
        explanation.setWordWrap(True)
        outer.addWidget(explanation)

        action_row = QtWidgets.QHBoxLayout()
        self.new_project_button = self._push_button(
            "New Project…", "scriptingStudioNewProjectButton", QtWidgets.QStyle.SP_FileIcon
        )
        self.open_project_button = self._push_button(
            "Open Project…", "scriptingStudioOpenProjectButton", QtWidgets.QStyle.SP_DialogOpenButton
        )
        self.save_project_button = self._push_button(
            "Save Project", "scriptingStudioSaveProjectButton", QtWidgets.QStyle.SP_DialogSaveButton
        )
        self.import_assets_button = self._push_button(
            "Import Resources…", "scriptingStudioImportAssetsButton", QtWidgets.QStyle.SP_ArrowDown
        )
        self.refresh_inventory_button = self._push_button(
            "Refresh Inventory", "scriptingStudioRefreshInventoryButton", QtWidgets.QStyle.SP_BrowserReload
        )
        self.validate_project_button = self._push_button(
            "Check Readiness", "scriptingStudioValidateProjectButton", QtWidgets.QStyle.SP_DialogApplyButton
        )
        for button in (
            self.new_project_button,
            self.open_project_button,
            self.save_project_button,
            self.import_assets_button,
            self.refresh_inventory_button,
            self.validate_project_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        self.target_game_combo = QtWidgets.QComboBox()
        self.target_game_combo.setObjectName("scriptingStudioProjectTargetGameCombo")
        self.target_game_combo.addItems(["K1", "K2"])
        self.target_game_combo.setCurrentText("K2")
        self.target_game_combo.setToolTip("Target game for a new narrative project")
        action_row.addWidget(QtWidgets.QLabel("New project target"))
        action_row.addWidget(self.target_game_combo)
        outer.addLayout(action_row)

        summary = QtWidgets.QGroupBox("Open Project")
        summary.setObjectName("scriptingStudioProjectSummaryGroup")
        summary_layout = QtWidgets.QGridLayout(summary)
        self.project_name_label = QtWidgets.QLabel("—")
        self.project_name_label.setObjectName("scriptingStudioProjectNameLabel")
        self.project_game_label = QtWidgets.QLabel("—")
        self.project_game_label.setObjectName("scriptingStudioProjectGameLabel")
        self.project_revision_label = QtWidgets.QLabel("—")
        self.project_revision_label.setObjectName("scriptingStudioProjectRevisionLabel")
        self.project_path_edit = QtWidgets.QLineEdit()
        self.project_path_edit.setObjectName("scriptingStudioProjectPathEdit")
        self.project_path_edit.setReadOnly(True)
        self.project_path_edit.setPlaceholderText("Open or create a narrative project")
        summary_layout.addWidget(QtWidgets.QLabel("Name"), 0, 0)
        summary_layout.addWidget(self.project_name_label, 0, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Target"), 0, 2)
        summary_layout.addWidget(self.project_game_label, 0, 3)
        summary_layout.addWidget(QtWidgets.QLabel("Revision"), 0, 4)
        summary_layout.addWidget(self.project_revision_label, 0, 5)
        summary_layout.addWidget(QtWidgets.QLabel("Manifest"), 1, 0)
        summary_layout.addWidget(self.project_path_edit, 1, 1, 1, 5)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.setColumnStretch(3, 1)
        outer.addWidget(summary)

        self.project_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.project_splitter.setObjectName("scriptingStudioProjectHistorySplitter")
        self.project_splitter.setChildrenCollapsible(False)
        self.project_splitter.addWidget(self._build_asset_panel())
        self.project_splitter.addWidget(self._build_history_panel())
        self.project_splitter.setStretchFactor(0, 3)
        self.project_splitter.setStretchFactor(1, 2)
        outer.addWidget(self.project_splitter, 1)

        self.new_project_button.clicked.connect(
            lambda: self.newProjectRequested.emit({"game": self.target_game_combo.currentText()})
        )
        self.open_project_button.clicked.connect(self.openProjectRequested.emit)
        self.save_project_button.clicked.connect(self.saveProjectRequested.emit)
        self.import_assets_button.clicked.connect(self.importAssetsRequested.emit)
        self.refresh_inventory_button.clicked.connect(self.refreshInventoryRequested.emit)
        self.validate_project_button.clicked.connect(self.validateProjectRequested.emit)

    def _push_button(
        self,
        text: str,
        object_name: str,
        standard_icon: QtWidgets.QStyle.StandardPixmap,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(_icon(self, standard_icon), text)
        button.setObjectName(object_name)
        return button

    def _build_asset_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("scriptingStudioAssetInventoryPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QLabel("Project Resources")
        heading.setObjectName("scriptingStudioAssetInventoryHeading")
        header.addWidget(heading)
        header.addStretch(1)
        self.asset_count_label = QtWidgets.QLabel("0 resources")
        self.asset_count_label.setObjectName("scriptingStudioAssetCountLabel")
        header.addWidget(self.asset_count_label)
        layout.addLayout(header)
        filter_row = QtWidgets.QHBoxLayout()
        self.asset_search_edit = QtWidgets.QLineEdit()
        self.asset_search_edit.setObjectName("scriptingStudioAssetSearchEdit")
        self.asset_search_edit.setPlaceholderText("Search name, path, role, or dependency…")
        self.asset_search_edit.setClearButtonEnabled(True)
        self.asset_type_combo = QtWidgets.QComboBox()
        self.asset_type_combo.setObjectName("scriptingStudioAssetTypeFilter")
        self.asset_type_combo.addItem("All types", "all")
        filter_row.addWidget(self.asset_search_edit, 1)
        filter_row.addWidget(self.asset_type_combo)
        layout.addLayout(filter_row)

        self.asset_model = QtGui.QStandardItemModel(0, 6, self)
        self.asset_model.setHorizontalHeaderLabels(["Resource", "Type", "Role", "Path", "Dependencies", "Status"])
        self.asset_proxy = NarrativeAssetFilterModel(self)
        self.asset_proxy.setSourceModel(self.asset_model)
        self.asset_view = QtWidgets.QTreeView()
        self.asset_view.setObjectName("scriptingStudioAssetInventoryView")
        self.asset_view.setModel(self.asset_proxy)
        self.asset_view.setRootIsDecorated(False)
        self.asset_view.setAlternatingRowColors(True)
        self.asset_view.setSortingEnabled(True)
        self.asset_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.asset_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.asset_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.asset_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.asset_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.asset_view.header().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.asset_view.header().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.asset_view.header().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.asset_view, 1)
        self.asset_search_edit.textChanged.connect(self._update_asset_filter)
        self.asset_type_combo.currentIndexChanged.connect(self._update_asset_filter)
        self.asset_view.doubleClicked.connect(self._activate_asset)
        return panel

    def _build_history_panel(self) -> QtWidgets.QWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("scriptingStudioProjectHistoryTabs")
        tabs.addTab(self._build_revisions_tab(), "Snapshots")
        tabs.addTab(self._build_legacy_history_tab(), "Legacy History")
        tabs.addTab(self._build_export_history_tab(), "Export History")
        tabs.addTab(self._build_recent_tab(), "Recent Projects")
        tabs.addTab(self._build_readiness_tab(), "Readiness")
        return tabs

    def _build_revisions_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        guidance = QtWidgets.QLabel(
            "Snapshots include every tracked resource and can be recovered as a separate project copy."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("Resource"))
        self.revision_asset_filter_combo = QtWidgets.QComboBox()
        self.revision_asset_filter_combo.setObjectName("scriptingStudioRevisionAssetFilter")
        self.revision_asset_filter_combo.addItem("All tracked resources", "")
        self.revision_asset_filter_combo.setToolTip(
            "Filter snapshots by stable project resource ID before recovering a single historical asset."
        )
        filter_row.addWidget(self.revision_asset_filter_combo, 1)
        layout.addLayout(filter_row)
        self.revision_view = QtWidgets.QTreeWidget()
        self.revision_view.setObjectName("scriptingStudioRevisionView")
        self.revision_view.setHeaderLabels(["Created", "Message", "Project rev", "Resources"])
        self.revision_view.setAlternatingRowColors(True)
        self.revision_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.revision_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.revision_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.revision_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.revision_view.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.revision_view, 1)
        self.revision_message_edit = QtWidgets.QLineEdit()
        self.revision_message_edit.setObjectName("scriptingStudioRevisionMessageEdit")
        self.revision_message_edit.setPlaceholderText("What changed in this snapshot?")
        layout.addWidget(self.revision_message_edit)
        buttons = QtWidgets.QHBoxLayout()
        self.create_revision_button = self._push_button(
            "Create Snapshot", "scriptingStudioCreateRevisionButton", QtWidgets.QStyle.SP_DialogSaveButton
        )
        self.recover_revision_button = self._push_button(
            "Recover as New Copy…", "scriptingStudioRecoverRevisionButton", QtWidgets.QStyle.SP_DialogOpenButton
        )
        self.recover_revision_button.setToolTip("Never overwrites the open project")
        self.recover_asset_revision_button = self._push_button(
            "Recover Selected Resource…",
            "scriptingStudioRecoverAssetRevisionButton",
            QtWidgets.QStyle.SP_FileDialogNewFolder,
        )
        self.recover_asset_revision_button.setToolTip(
            "Writes the historical resource and its hash/manifest metadata into a new folder"
        )
        buttons.addWidget(self.create_revision_button)
        buttons.addWidget(self.recover_revision_button)
        buttons.addWidget(self.recover_asset_revision_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.create_revision_button.clicked.connect(
            lambda: self.createRevisionRequested.emit(self.revision_message_edit.text().strip())
        )
        self.recover_revision_button.clicked.connect(self._recover_selected_revision)
        self.recover_asset_revision_button.clicked.connect(self._recover_selected_revision_asset)
        self.revision_asset_filter_combo.currentIndexChanged.connect(self._populate_revision_view)
        self.revision_view.itemDoubleClicked.connect(lambda _item, _column: self._recover_selected_revision())
        return page

    def _build_legacy_history_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        page.setObjectName("scriptingStudioLegacyHistoryTab")
        layout = QtWidgets.QVBoxLayout(page)
        guidance = QtWidgets.QLabel(
            "Imported GhostScripter scripts, quests, dialogues, project metadata, 2DA plans, dependencies, "
            "preferences, and recent-project rows stay read-only here. Preferences are never silently applied. "
            "Recovery writes the preserved content and provenance into a new folder."
        )
        guidance.setObjectName("scriptingStudioLegacyHistoryGuidance")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.setObjectName("scriptingStudioLegacyHistorySplitter")
        self.legacy_history_view = QtWidgets.QTreeWidget()
        self.legacy_history_view.setObjectName("scriptingStudioLegacyHistoryView")
        self.legacy_history_view.setHeaderLabels(["Created", "Kind", "Resource", "Revision", "Summary"])
        self.legacy_history_view.setAlternatingRowColors(True)
        self.legacy_history_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.legacy_history_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.legacy_history_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.legacy_history_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.legacy_history_view.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.legacy_history_view.header().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        splitter.addWidget(self.legacy_history_view)
        self.legacy_history_details = QtWidgets.QPlainTextEdit()
        self.legacy_history_details.setObjectName("scriptingStudioLegacyHistoryDetails")
        self.legacy_history_details.setReadOnly(True)
        self.legacy_history_details.setPlaceholderText(
            "Select an imported snapshot to inspect its identity, source row, hash, and content preview."
        )
        splitter.addWidget(self.legacy_history_details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        buttons = QtWidgets.QHBoxLayout()
        self.recover_legacy_history_button = self._push_button(
            "Recover Selected…",
            "scriptingStudioRecoverLegacyHistoryButton",
            QtWidgets.QStyle.SP_FileDialogNewFolder,
        )
        self.recover_legacy_history_button.setEnabled(False)
        self.recover_legacy_history_button.setToolTip(
            "Writes exact archived content and a SHA-256 provenance manifest into a new folder"
        )
        self.open_legacy_quest_button = self._push_button(
            "Open Quest in Builder",
            "scriptingStudioOpenLegacyQuestButton",
            QtWidgets.QStyle.SP_DialogOpenButton,
        )
        self.open_legacy_quest_button.setEnabled(False)
        self.open_legacy_quest_button.setToolTip(
            "Loads the preserved quest JSON into the editable Quest Builder without changing the archive"
        )
        buttons.addWidget(self.recover_legacy_history_button)
        buttons.addWidget(self.open_legacy_quest_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.legacy_history_view.currentItemChanged.connect(self._show_legacy_history_details)
        self.recover_legacy_history_button.clicked.connect(self._recover_selected_legacy_history)
        self.open_legacy_quest_button.clicked.connect(self._open_selected_legacy_quest)
        return page

    def _build_export_history_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        guidance = QtWidgets.QLabel(
            "Every package, stage, Override install, and global talk-table operation records exact input hashes. "
            "Engine proof remains ‘not recorded’ until an in-game result is attached."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        filters = QtWidgets.QHBoxLayout()
        self.export_history_search_edit = QtWidgets.QLineEdit()
        self.export_history_search_edit.setObjectName("scriptingStudioExportHistorySearch")
        self.export_history_search_edit.setPlaceholderText("Search destination, receipt, resource, hash, or result…")
        self.export_history_search_edit.setClearButtonEnabled(True)
        self.export_history_operation_combo = QtWidgets.QComboBox()
        self.export_history_operation_combo.setObjectName("scriptingStudioExportHistoryOperationFilter")
        self.export_history_operation_combo.addItem("All operations", "")
        self.export_history_outcome_combo = QtWidgets.QComboBox()
        self.export_history_outcome_combo.setObjectName("scriptingStudioExportHistoryOutcomeFilter")
        self.export_history_outcome_combo.addItem("All results", "")
        self.export_history_outcome_combo.addItem("Succeeded", "succeeded")
        self.export_history_outcome_combo.addItem("Failed", "failed")
        filters.addWidget(self.export_history_search_edit, 1)
        filters.addWidget(self.export_history_operation_combo)
        filters.addWidget(self.export_history_outcome_combo)
        layout.addLayout(filters)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.setObjectName("scriptingStudioExportHistorySplitter")
        self.export_history_view = QtWidgets.QTreeWidget()
        self.export_history_view.setObjectName("scriptingStudioExportHistoryView")
        self.export_history_view.setHeaderLabels(
            ["Created", "Operation", "Result", "Destination", "Inputs", "Engine proof"]
        )
        self.export_history_view.setAlternatingRowColors(True)
        self.export_history_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.export_history_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.export_history_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.export_history_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.export_history_view.header().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.export_history_view.header().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.export_history_view.header().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        splitter.addWidget(self.export_history_view)
        self.export_history_details = QtWidgets.QPlainTextEdit()
        self.export_history_details.setObjectName("scriptingStudioExportHistoryDetails")
        self.export_history_details.setReadOnly(True)
        self.export_history_details.setPlaceholderText("Select an operation to inspect hashes, backups, and receipts.")
        splitter.addWidget(self.export_history_details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        self.export_history_search_edit.textChanged.connect(self._filter_export_history)
        self.export_history_operation_combo.currentIndexChanged.connect(self._filter_export_history)
        self.export_history_outcome_combo.currentIndexChanged.connect(self._filter_export_history)
        self.export_history_view.currentItemChanged.connect(self._show_export_history_details)
        return page

    def _build_recent_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.recent_view = QtWidgets.QTreeWidget()
        self.recent_view.setObjectName("scriptingStudioRecentProjectsView")
        self.recent_view.setHeaderLabels(["Project", "Game", "Last opened"])
        self.recent_view.setAlternatingRowColors(True)
        self.recent_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.recent_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.recent_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.recent_view, 1)
        buttons = QtWidgets.QHBoxLayout()
        self.open_recent_button = self._push_button(
            "Open Selected", "scriptingStudioOpenRecentButton", QtWidgets.QStyle.SP_DialogOpenButton
        )
        self.forget_recent_button = self._push_button(
            "Forget from List", "scriptingStudioForgetRecentButton", QtWidgets.QStyle.SP_DialogDiscardButton
        )
        buttons.addWidget(self.open_recent_button)
        buttons.addWidget(self.forget_recent_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.open_recent_button.clicked.connect(self._open_selected_recent)
        self.forget_recent_button.clicked.connect(self._forget_selected_recent)
        self.recent_view.itemDoubleClicked.connect(lambda _item, _column: self._open_selected_recent())
        return page

    def _build_readiness_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.issue_summary_label = QtWidgets.QLabel("No readiness check has run")
        self.issue_summary_label.setObjectName("scriptingStudioProjectIssueSummary")
        self.issue_summary_label.setWordWrap(True)
        layout.addWidget(self.issue_summary_label)
        self.issue_view = QtWidgets.QTreeWidget()
        self.issue_view.setObjectName("scriptingStudioProjectIssueView")
        self.issue_view.setHeaderLabels(["Severity", "Resource", "Issue"])
        self.issue_view.setAlternatingRowColors(True)
        self.issue_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.issue_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.issue_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.issue_view, 1)
        return page

    def _bind_theme_layout(self, theme_manager: Any, layout_manager: Any) -> None:
        if theme_manager is not None:
            register = getattr(theme_manager, "register_theme_aware_widget", None)
            if callable(register):
                register(self)
            current = getattr(theme_manager, "current_theme", None)
            if current is not None:
                self.apply_ghost_theme(current)
        if layout_manager is not None:
            changed = getattr(layout_manager, "layoutChanged", None)
            if changed is not None and hasattr(changed, "connect"):
                changed.connect(self.apply_ghost_layout)
            current = getattr(layout_manager, "current_layout", None)
            if current is not None:
                self.apply_ghost_layout(current)

    def _update_asset_filter(self) -> None:
        self.asset_proxy.set_filters(
            self.asset_search_edit.text(),
            str(self.asset_type_combo.currentData() or "all"),
        )

    def _activate_asset(self, proxy_index: QtCore.QModelIndex) -> None:
        source = self.asset_proxy.mapToSource(proxy_index)
        row = dict(self.asset_model.item(source.row(), 0).data(PAGE_ROW_ROLE) or {})
        if row:
            self.assetActivated.emit(row)

    def _selected_tree_row(self, tree: QtWidgets.QTreeWidget) -> dict[str, Any]:
        item = tree.currentItem()
        return dict(item.data(0, PAGE_ROW_ROLE) or {}) if item is not None else {}

    def _recover_selected_revision(self) -> None:
        revision_id = str(self._selected_tree_row(self.revision_view).get("revision_id") or "")
        if revision_id:
            self.recoverRevisionRequested.emit(revision_id)

    def _recover_selected_revision_asset(self) -> None:
        revision_id = str(self._selected_tree_row(self.revision_view).get("revision_id") or "")
        asset_id = str(self.revision_asset_filter_combo.currentData() or "")
        if revision_id and asset_id:
            self.recoverAssetRevisionRequested.emit(revision_id, asset_id)

    def _recover_selected_legacy_history(self) -> None:
        record_id = str(self._selected_tree_row(self.legacy_history_view).get("record_id") or "")
        if record_id:
            self.recoverLegacyHistoryRequested.emit(record_id)

    def _open_selected_legacy_quest(self) -> None:
        row = self._selected_tree_row(self.legacy_history_view)
        record_id = str(row.get("record_id") or "")
        if record_id and str(row.get("kind") or "").casefold() == "quest":
            self.openLegacyQuestRequested.emit(record_id)

    def _show_legacy_history_details(
        self,
        current: QtWidgets.QTreeWidgetItem | None,
        _previous: QtWidgets.QTreeWidgetItem | None,
    ) -> None:
        row = dict(current.data(0, PAGE_ROW_ROLE) or {}) if current is not None else {}
        self.recover_legacy_history_button.setEnabled(bool(row.get("record_id")))
        self.open_legacy_quest_button.setEnabled(
            bool(row.get("record_id")) and str(row.get("kind") or "").casefold() == "quest"
        )
        if not row:
            self.legacy_history_details.clear()
            return
        content = str(row.get("content") or row.get("content_preview") or "")
        preview_limit = 4000
        preview = content[:preview_limit]
        if bool(row.get("content_truncated")):
            total = int(row.get("character_count") or len(content))
            preview += f"\n… {max(0, total - len(content))} more character(s); recovery preserves all content."
        elif len(content) > preview_limit:
            preview += f"\n… {len(content) - preview_limit} more character(s); recovery preserves all content."
        source_row = dict(row.get("source_row", {}) or {})
        for key in ("content", "source", "script_text", "data_json", "snapshot", "json_data"):
            value = source_row.get(key)
            if isinstance(value, str) and len(value) > 400:
                source_row[key] = f"<preserved content shown above; {len(value)} character(s)>"
        try:
            source_text = json.dumps(source_row, ensure_ascii=False, indent=2, sort_keys=False)
        except (TypeError, ValueError):
            source_text = repr(source_row)
        if len(source_text) > 8000:
            source_text = source_text[:8000] + "\n… source metadata truncated in this preview; recovery preserves it."
        lines = [
            f"Record: {row.get('record_id') or '—'}",
            f"Kind: {_readable_status(row.get('kind'), 'Unknown')}",
            f"Resource: {row.get('identity') or '—'}",
            f"Created: {row.get('created_at') or '—'}",
            f"Revision: {row.get('revision') or '—'}",
            f"Recovered filename: {row.get('suggested_filename') or '—'}",
            f"Archived bytes: {row.get('byte_count') or len(content.encode('utf-8'))}",
            f"SHA-256: {row.get('sha256') or '—'}",
            f"Source: {row.get('source_table') or '—'} row {row.get('source_row_index', '—')}",
            "",
            "Content preview",
            preview or "(empty snapshot content)",
            "",
            "Preserved source row",
            source_text,
        ]
        self.legacy_history_details.setPlainText("\n".join(lines))

    def _populate_revision_view(self, *_args: object) -> None:
        selected_revision = str(self._selected_tree_row(self.revision_view).get("revision_id") or "")
        asset_id = str(self.revision_asset_filter_combo.currentData() or "")
        self.revision_view.clear()
        visible = 0
        for row in self._revision_rows:
            asset_ids = {str(value) for value in tuple(row.get("asset_ids", ()) or ())}
            if asset_id and asset_id not in asset_ids:
                continue
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(row.get("created_at") or ""),
                    str(row.get("message") or "Snapshot"),
                    str(row.get("project_revision") or ""),
                    str(row.get("asset_count") or 0),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            item.setToolTip(1, str(row.get("manifest_path") or ""))
            self.revision_view.addTopLevelItem(item)
            visible += 1
            if str(row.get("revision_id") or "") == selected_revision:
                self.revision_view.setCurrentItem(item)
        self.recover_revision_button.setEnabled(bool(visible))
        self.recover_asset_revision_button.setEnabled(bool(visible and asset_id))

    def _filter_export_history(self, *_args: object) -> None:
        query = self.export_history_search_edit.text().strip().casefold()
        operation = str(self.export_history_operation_combo.currentData() or "").casefold()
        outcome = str(self.export_history_outcome_combo.currentData() or "").casefold()
        for index in range(self.export_history_view.topLevelItemCount()):
            item = self.export_history_view.topLevelItem(index)
            row = dict(item.data(0, PAGE_ROW_ROLE) or {})
            inputs = tuple(row.get("input_hashes", ()) or ())
            haystack = " ".join(
                (
                    str(row.get("created_at") or ""),
                    str(row.get("operation") or ""),
                    str(row.get("outcome") or ""),
                    str(row.get("destination") or ""),
                    str(row.get("backup_path") or ""),
                    str(row.get("receipt_path") or ""),
                    str(row.get("summary") or ""),
                    str(row.get("engine_proof") or ""),
                    *(str(value.get("filename") or "") for value in inputs if isinstance(value, Mapping)),
                    *(str(value.get("sha256") or "") for value in inputs if isinstance(value, Mapping)),
                )
            ).casefold()
            visible = (
                (not operation or str(row.get("operation") or "").casefold() == operation)
                and (not outcome or str(row.get("outcome") or "").casefold() == outcome)
                and (not query or query in haystack)
            )
            item.setHidden(not visible)

    def _show_export_history_details(
        self,
        current: QtWidgets.QTreeWidgetItem | None,
        _previous: QtWidgets.QTreeWidgetItem | None,
    ) -> None:
        row = dict(current.data(0, PAGE_ROW_ROLE) or {}) if current is not None else {}
        if not row:
            self.export_history_details.clear()
            return
        lines = [
            f"Receipt: {row.get('receipt_id') or '—'}",
            f"Created: {row.get('created_at') or '—'}",
            f"Operation: {_readable_status(row.get('operation'), 'Unknown')}",
            f"Result: {_readable_status(row.get('outcome'), 'Unknown')}",
            f"Destination: {row.get('destination') or '—'}",
            f"Backup: {row.get('backup_path') or '—'}",
            f"Operation receipt: {row.get('receipt_path') or '—'}",
            f"Engine proof: {_readable_status(row.get('engine_proof'), 'Not recorded')}",
        ]
        if row.get("engine_proof_evidence"):
            lines.append(f"Proof evidence: {row['engine_proof_evidence']}")
        if row.get("summary"):
            lines.extend(("", "Summary", str(row["summary"])))
        lines.extend(("", "Exact input fingerprints"))
        inputs = tuple(row.get("input_hashes", ()) or ())
        if inputs:
            for value in inputs:
                if not isinstance(value, Mapping):
                    continue
                lines.append(
                    f"• {value.get('filename') or 'input'} — {value.get('byte_count') or 0} bytes — "
                    f"SHA-256 {value.get('sha256') or 'missing'}"
                )
        else:
            lines.append("• No valid input bytes reached this operation.")
        issues = tuple(row.get("issues", ()) or ())
        if issues:
            lines.extend(("", "Issues"))
            for value in issues:
                if isinstance(value, Mapping):
                    lines.append(
                        f"• {_readable_status(value.get('severity'), 'Info')}: {value.get('message') or value.get('code') or ''}"
                    )
        self.export_history_details.setPlainText("\n".join(lines))

    def _open_selected_recent(self) -> None:
        path = str(self._selected_tree_row(self.recent_view).get("manifest_path") or "")
        if path:
            self.recentProjectActivated.emit(path)

    def _forget_selected_recent(self) -> None:
        project_id = str(self._selected_tree_row(self.recent_view).get("project_id") or "")
        if project_id:
            self.forgetRecentRequested.emit(project_id)

    def set_project(self, row: Mapping[str, Any]) -> None:
        self._project = dict(row or {})
        opened = bool(self._project.get("project_id"))
        self.project_name_label.setText(str(self._project.get("name") or "—"))
        game = str(self._project.get("game") or "—")
        self.project_game_label.setText(game)
        self.project_revision_label.setText(str(self._project.get("revision") or "—"))
        self.project_path_edit.setText(str(self._project.get("manifest_path") or ""))
        self.project_status_label.setText(_readable_status(self._project.get("status"), "Project open" if opened else "No project open"))
        if game in {"K1", "K2"}:
            self.target_game_combo.setCurrentText(game)
        for widget in (
            self.save_project_button,
            self.import_assets_button,
            self.refresh_inventory_button,
            self.validate_project_button,
            self.create_revision_button,
        ):
            widget.setEnabled(opened)

    def set_asset_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._asset_rows = [dict(row) for row in rows]
        selected_id = ""
        selected = self.asset_view.currentIndex()
        if selected.isValid():
            source = self.asset_proxy.mapToSource(selected)
            selected_id = str(dict(self.asset_model.item(source.row(), 0).data(PAGE_ROW_ROLE) or {}).get("asset_id") or "")
        self.asset_model.removeRows(0, self.asset_model.rowCount())
        types = sorted({str(row.get("restype") or "").lower() for row in self._asset_rows if row.get("restype")})
        current_type = str(self.asset_type_combo.currentData() or "all")
        blocker = QtCore.QSignalBlocker(self.asset_type_combo)
        self.asset_type_combo.clear()
        self.asset_type_combo.addItem("All types", "all")
        for restype in types:
            self.asset_type_combo.addItem(restype.upper(), restype)
        index = self.asset_type_combo.findData(current_type)
        self.asset_type_combo.setCurrentIndex(max(0, index))
        del blocker
        for row in self._asset_rows:
            dependencies = row.get("dependencies", ()) or ()
            dependency_summary = str(row.get("dependency_summary") or f"{len(dependencies)} linked")
            row["dependency_summary"] = dependency_summary
            values = (
                row.get("resref") or row.get("filename") or "resource",
                str(row.get("restype") or "").upper(),
                _readable_status(row.get("role"), "Runtime"),
                row.get("path") or "",
                dependency_summary,
                _readable_status(row.get("status"), "Tracked"),
            )
            items = [QtGui.QStandardItem(str(value)) for value in values]
            for item in items:
                item.setEditable(False)
            items[0].setData(dict(row), PAGE_ROW_ROLE)
            items[0].setToolTip(str(row.get("path") or row.get("resref") or ""))
            self.asset_model.appendRow(items)
        self.asset_count_label.setText(f"{len(self._asset_rows)} resource(s)")
        selected_revision_asset = str(self.revision_asset_filter_combo.currentData() or "")
        blocker = QtCore.QSignalBlocker(self.revision_asset_filter_combo)
        self.revision_asset_filter_combo.clear()
        self.revision_asset_filter_combo.addItem("All tracked resources", "")
        for row in self._asset_rows:
            asset_id = str(row.get("asset_id") or "")
            if not asset_id:
                continue
            label = f"{row.get('resref') or row.get('filename') or asset_id}.{str(row.get('restype') or '').lower()}"
            self.revision_asset_filter_combo.addItem(label.rstrip("."), asset_id)
        index = self.revision_asset_filter_combo.findData(selected_revision_asset)
        self.revision_asset_filter_combo.setCurrentIndex(max(0, index))
        del blocker
        self._populate_revision_view()
        self._update_asset_filter()
        if selected_id:
            for source_row in range(self.asset_model.rowCount()):
                row = dict(self.asset_model.item(source_row, 0).data(PAGE_ROW_ROLE) or {})
                if str(row.get("asset_id") or "") == selected_id:
                    self.asset_view.setCurrentIndex(self.asset_proxy.mapFromSource(self.asset_model.index(source_row, 0)))
                    break

    def set_revision_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._revision_rows = [dict(row) for row in rows]
        self._populate_revision_view()

    def set_legacy_history_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._legacy_history_rows = [dict(row) for row in rows]
        selected_id = str(self._selected_tree_row(self.legacy_history_view).get("record_id") or "")
        self.legacy_history_view.clear()
        selected_item: QtWidgets.QTreeWidgetItem | None = None
        for row in self._legacy_history_rows:
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(row.get("created_at") or ""),
                    _readable_status(row.get("kind"), "Unknown"),
                    str(row.get("identity") or ""),
                    str(row.get("revision") or ""),
                    str(row.get("summary") or ""),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            item.setToolTip(2, str(row.get("suggested_filename") or row.get("identity") or ""))
            self.legacy_history_view.addTopLevelItem(item)
            if str(row.get("record_id") or "") == selected_id:
                selected_item = item
        if selected_item is not None:
            self.legacy_history_view.setCurrentItem(selected_item)
        else:
            self.legacy_history_details.clear()
            self.recover_legacy_history_button.setEnabled(False)

    def set_export_history_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._export_history_rows = [dict(row) for row in rows]
        current_operation = str(self.export_history_operation_combo.currentData() or "")
        blocker = QtCore.QSignalBlocker(self.export_history_operation_combo)
        self.export_history_operation_combo.clear()
        self.export_history_operation_combo.addItem("All operations", "")
        for operation in sorted({str(row.get("operation") or "") for row in self._export_history_rows}):
            if operation:
                self.export_history_operation_combo.addItem(_readable_status(operation), operation)
        index = self.export_history_operation_combo.findData(current_operation)
        self.export_history_operation_combo.setCurrentIndex(max(0, index))
        del blocker
        self.export_history_view.clear()
        for row in self._export_history_rows:
            inputs = tuple(row.get("input_hashes", ()) or ())
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(row.get("created_at") or ""),
                    _readable_status(row.get("operation"), "Unknown"),
                    _readable_status(row.get("outcome"), "Unknown"),
                    str(row.get("destination") or ""),
                    str(len(inputs)),
                    _readable_status(row.get("engine_proof"), "Not recorded"),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            item.setToolTip(3, str(row.get("summary") or row.get("destination") or ""))
            self.export_history_view.addTopLevelItem(item)
        self.export_history_details.clear()
        self._filter_export_history()

    def set_recent_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._recent_rows = [dict(row) for row in rows]
        self.recent_view.clear()
        for row in self._recent_rows:
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(row.get("name") or row.get("manifest_path") or "Project"),
                    str(row.get("game") or ""),
                    str(row.get("last_opened_at") or ""),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            item.setToolTip(0, str(row.get("manifest_path") or ""))
            self.recent_view.addTopLevelItem(item)
        enabled = bool(self._recent_rows)
        self.open_recent_button.setEnabled(enabled)
        self.forget_recent_button.setEnabled(enabled)

    def set_project_issues(self, rows: Sequence[Mapping[str, Any]], *, summary: str = "") -> None:
        self.issue_view.clear()
        issues = [dict(row) for row in rows]
        blocking = 0
        warnings = 0
        for row in issues:
            severity = _readable_status(row.get("severity"), "Info")
            blocking += int(severity.casefold() in {"blocking", "error"})
            warnings += int(severity.casefold() == "warning")
            item = QtWidgets.QTreeWidgetItem(
                [severity, str(row.get("resource") or row.get("asset_id") or ""), str(row.get("message") or "")]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            self.issue_view.addTopLevelItem(item)
        self.issue_summary_label.setText(summary or f"{blocking} blocking • {warnings} warning • {len(issues)} total")

    def set_busy(self, busy: bool, *, message: str = "") -> None:
        self.setEnabled(not busy)
        if message:
            self.project_status_label.setText(str(message))

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        handle_width = 6
        spacing = 7
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value):
            handle_width = spacing_value("splitterHandleWidth", handle_width)
            spacing = spacing_value("panelSpacing", spacing)
        self.project_splitter.setHandleWidth(int(handle_width))
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setSpacing(int(spacing))


class QtScriptingPackageOverridePage(QtWidgets.QWidget):
    """Verified ERF/MOD/SAV package and explicit two-step Override workflow."""

    addPackageFilesRequested = QtCore.Signal()
    packageOutputBrowseRequested = QtCore.Signal(str)
    packageBuildRequested = QtCore.Signal(object)
    stageOutputBrowseRequested = QtCore.Signal(str)
    stageOverrideRequested = QtCore.Signal(object)
    stageInspectRequested = QtCore.Signal(str)
    gameRootBrowseRequested = QtCore.Signal(str)
    installOverrideRequested = QtCore.Signal(object)
    packageResourceActivated = QtCore.Signal(object)
    readinessRefreshRequested = QtCore.Signal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        theme_manager: Any = None,
        layout_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioPackageOverridePage")
        self.setProperty("ghostLayoutId", "scriptingStudioPackageOverride")
        self._package_rows: list[dict[str, Any]] = []
        self._stage_ready = False
        self._readiness_ready = False
        self._build_ui()
        self._bind_theme_layout(theme_manager, layout_manager)
        self.set_readiness({}, issues=())

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(7)
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Package & Test Install")
        title.setObjectName("scriptingStudioPackageHeading")
        title.setProperty("headingLevel", 1)
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.readiness_label = QtWidgets.QLabel("Not ready")
        self.readiness_label.setObjectName("scriptingStudioPackageReadinessLabel")
        title_row.addWidget(self.readiness_label)
        self.refresh_readiness_button = QtWidgets.QPushButton(
            _icon(self, QtWidgets.QStyle.SP_BrowserReload), "Refresh Readiness"
        )
        self.refresh_readiness_button.setObjectName("scriptingStudioPackageRefreshReadinessButton")
        title_row.addWidget(self.refresh_readiness_button)
        outer.addLayout(title_row)
        guidance = QtWidgets.QLabel(
            "Build produces a PyKotor archive only after exact resource readback. Override is a deliberate two-step "
            "workflow: stage files first, then explicitly install them into a chosen game copy."
        )
        guidance.setObjectName("scriptingStudioPackageGuidanceLabel")
        guidance.setWordWrap(True)
        outer.addWidget(guidance)

        self.package_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.package_splitter.setObjectName("scriptingStudioPackageOverrideSplitter")
        self.package_splitter.setChildrenCollapsible(False)
        self.package_splitter.addWidget(self._build_archive_group())
        self.package_splitter.addWidget(self._build_override_group())
        self.package_splitter.setStretchFactor(0, 1)
        self.package_splitter.setStretchFactor(1, 1)
        outer.addWidget(self.package_splitter, 3)

        issues_group = QtWidgets.QGroupBox("Verification & Safety")
        issues_group.setObjectName("scriptingStudioPackageIssuesGroup")
        issues_layout = QtWidgets.QVBoxLayout(issues_group)
        self.package_issue_view = QtWidgets.QTreeWidget()
        self.package_issue_view.setObjectName("scriptingStudioPackageIssueView")
        self.package_issue_view.setHeaderLabels(["Severity", "Resource", "Message"])
        self.package_issue_view.setAlternatingRowColors(True)
        self.package_issue_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.package_issue_view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.package_issue_view.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        issues_layout.addWidget(self.package_issue_view)
        outer.addWidget(issues_group, 1)
        self.refresh_readiness_button.clicked.connect(self.readinessRefreshRequested.emit)

    def _build_archive_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Distribution Archive — ERF / MOD / SAV")
        group.setObjectName("scriptingStudioArchiveBuildGroup")
        layout = QtWidgets.QVBoxLayout(group)
        description = QtWidgets.QLabel(
            "Use MOD for module content, ERF for a general resource archive, or SAV for an advanced save-game "
            "container. SAV does not become a complete playable save unless every engine-required save resource is supplied. "
            "Source NSS files are excluded by default."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        controls = QtWidgets.QGridLayout()
        self.archive_type_combo = QtWidgets.QComboBox()
        self.archive_type_combo.setObjectName("scriptingStudioArchiveTypeCombo")
        self.archive_type_combo.addItem("MOD — module archive", "MOD")
        self.archive_type_combo.addItem("ERF — resource archive", "ERF")
        self.archive_type_combo.addItem("SAV — save-game container (advanced)", "SAV")
        self.package_output_edit = QtWidgets.QLineEdit()
        self.package_output_edit.setObjectName("scriptingStudioPackageOutputEdit")
        self.package_output_edit.setPlaceholderText("Choose an output .mod, .erf, or .sav file")
        self.package_output_browse_button = QtWidgets.QToolButton()
        self.package_output_browse_button.setObjectName("scriptingStudioPackageOutputBrowseButton")
        self.package_output_browse_button.setText("Browse…")
        self.include_source_check = QtWidgets.QCheckBox("Include source files such as NSS")
        self.include_source_check.setObjectName("scriptingStudioPackageIncludeSourceCheck")
        self.overwrite_package_check = QtWidgets.QCheckBox("Replace an existing archive and its GhostStudio manifest")
        self.overwrite_package_check.setObjectName("scriptingStudioPackageOverwriteCheck")
        controls.addWidget(QtWidgets.QLabel("Archive format"), 0, 0)
        controls.addWidget(self.archive_type_combo, 0, 1, 1, 2)
        controls.addWidget(QtWidgets.QLabel("Output file"), 1, 0)
        controls.addWidget(self.package_output_edit, 1, 1)
        controls.addWidget(self.package_output_browse_button, 1, 2)
        controls.addWidget(self.include_source_check, 2, 1, 1, 2)
        controls.addWidget(self.overwrite_package_check, 3, 1, 1, 2)
        controls.setColumnStretch(1, 1)
        layout.addLayout(controls)

        toolbar = QtWidgets.QHBoxLayout()
        self.add_package_files_button = QtWidgets.QPushButton(
            _icon(self, QtWidgets.QStyle.SP_FileDialogNewFolder), "Add Resource Files…"
        )
        self.add_package_files_button.setObjectName("scriptingStudioAddPackageFilesButton")
        self.build_package_button = QtWidgets.QPushButton(
            _icon(self, QtWidgets.QStyle.SP_DialogSaveButton), "Build & Verify Archive"
        )
        self.build_package_button.setObjectName("scriptingStudioBuildPackageButton")
        toolbar.addWidget(self.add_package_files_button)
        toolbar.addWidget(self.build_package_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.package_resource_view = QtWidgets.QTreeWidget()
        self.package_resource_view.setObjectName("scriptingStudioPackageResourceView")
        self.package_resource_view.setHeaderLabels(["Resource", "Type", "Role", "Bytes", "Status"])
        self.package_resource_view.setAlternatingRowColors(True)
        self.package_resource_view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in range(1, 5):
            self.package_resource_view.header().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.package_resource_view, 1)
        self.package_result_label = QtWidgets.QLabel("No archive built in this session")
        self.package_result_label.setObjectName("scriptingStudioPackageResultLabel")
        self.package_result_label.setWordWrap(True)
        layout.addWidget(self.package_result_label)
        self.add_package_files_button.clicked.connect(self.addPackageFilesRequested.emit)
        self.package_output_browse_button.clicked.connect(
            lambda: self.packageOutputBrowseRequested.emit(str(self.archive_type_combo.currentData() or "MOD"))
        )
        self.build_package_button.clicked.connect(self._request_package_build)
        self.package_resource_view.itemDoubleClicked.connect(self._activate_package_resource)
        return group

    def _build_override_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Override Test Workflow")
        group.setObjectName("scriptingStudioOverrideWorkflowGroup")
        layout = QtWidgets.QVBoxLayout(group)
        safety = QtWidgets.QLabel(
            "Stage is safe and does not touch the game. Install is the only button here that writes to a game folder. "
            "Different existing files are blocked unless you explicitly choose backup-and-replace."
        )
        safety.setObjectName("scriptingStudioOverrideSafetyLabel")
        safety.setWordWrap(True)
        layout.addWidget(safety)

        stage_group = QtWidgets.QGroupBox("1. Stage and verify")
        stage_layout = QtWidgets.QGridLayout(stage_group)
        self.stage_output_edit = QtWidgets.QLineEdit()
        self.stage_output_edit.setObjectName("scriptingStudioOverrideStageOutputEdit")
        self.stage_output_edit.setPlaceholderText("Choose a build staging folder")
        self.stage_output_browse_button = QtWidgets.QToolButton()
        self.stage_output_browse_button.setObjectName("scriptingStudioOverrideStageBrowseButton")
        self.stage_output_browse_button.setText("Browse…")
        self.replace_owned_stage_check = QtWidgets.QCheckBox("Refresh an existing GhostStudio-owned stage")
        self.replace_owned_stage_check.setObjectName("scriptingStudioReplaceOwnedStageCheck")
        self.stage_override_button = QtWidgets.QPushButton(
            _icon(self, QtWidgets.QStyle.SP_DialogApplyButton), "Stage Override Files"
        )
        self.stage_override_button.setObjectName("scriptingStudioStageOverrideButton")
        self.inspect_stage_button = QtWidgets.QPushButton("Verify Existing Stage")
        self.inspect_stage_button.setObjectName("scriptingStudioInspectOverrideStageButton")
        stage_layout.addWidget(QtWidgets.QLabel("Stage folder"), 0, 0)
        stage_layout.addWidget(self.stage_output_edit, 0, 1)
        stage_layout.addWidget(self.stage_output_browse_button, 0, 2)
        stage_layout.addWidget(self.replace_owned_stage_check, 1, 1, 1, 2)
        stage_layout.addWidget(self.stage_override_button, 2, 1)
        stage_layout.addWidget(self.inspect_stage_button, 2, 2)
        stage_layout.setColumnStretch(1, 1)
        layout.addWidget(stage_group)

        install_group = QtWidgets.QGroupBox("2. Explicitly install for testing")
        install_layout = QtWidgets.QGridLayout(install_group)
        self.game_root_edit = QtWidgets.QLineEdit()
        self.game_root_edit.setObjectName("scriptingStudioGameRootEdit")
        self.game_root_edit.setPlaceholderText("Choose a KOTOR 1 or KOTOR 2 installation")
        self.game_root_browse_button = QtWidgets.QToolButton()
        self.game_root_browse_button.setObjectName("scriptingStudioGameRootBrowseButton")
        self.game_root_browse_button.setText("Browse…")
        self.conflict_policy_combo = QtWidgets.QComboBox()
        self.conflict_policy_combo.setObjectName("scriptingStudioOverrideConflictPolicyCombo")
        self.conflict_policy_combo.addItem("Block if a different file exists (recommended)", "block")
        self.conflict_policy_combo.addItem("Back up the old file, then replace it", "backup")
        self.install_override_button = QtWidgets.QPushButton(
            _icon(self, QtWidgets.QStyle.SP_ArrowForward), "Install Staged Files into Game Override"
        )
        self.install_override_button.setObjectName("scriptingStudioInstallOverrideButton")
        self.install_override_button.setEnabled(False)
        install_layout.addWidget(QtWidgets.QLabel("Game folder"), 0, 0)
        install_layout.addWidget(self.game_root_edit, 0, 1)
        install_layout.addWidget(self.game_root_browse_button, 0, 2)
        install_layout.addWidget(QtWidgets.QLabel("Existing files"), 1, 0)
        install_layout.addWidget(self.conflict_policy_combo, 1, 1, 1, 2)
        install_layout.addWidget(self.install_override_button, 2, 1, 1, 2)
        install_layout.setColumnStretch(1, 1)
        layout.addWidget(install_group)

        self.stage_result_label = QtWidgets.QLabel("No verified stage selected")
        self.stage_result_label.setObjectName("scriptingStudioOverrideStageResultLabel")
        self.stage_result_label.setWordWrap(True)
        self.install_result_label = QtWidgets.QLabel("No game install performed in this session")
        self.install_result_label.setObjectName("scriptingStudioOverrideInstallResultLabel")
        self.install_result_label.setWordWrap(True)
        layout.addWidget(self.stage_result_label)
        layout.addWidget(self.install_result_label)
        layout.addStretch(1)
        self.stage_output_browse_button.clicked.connect(
            lambda: self.stageOutputBrowseRequested.emit(self.stage_output_edit.text())
        )
        self.stage_override_button.clicked.connect(self._request_override_stage)
        self.inspect_stage_button.clicked.connect(
            lambda: self.stageInspectRequested.emit(self.stage_output_edit.text().strip())
        )
        self.game_root_browse_button.clicked.connect(
            lambda: self.gameRootBrowseRequested.emit(self.game_root_edit.text())
        )
        self.install_override_button.clicked.connect(self._request_override_install)
        self.game_root_edit.textChanged.connect(self._update_install_enabled)
        return group

    def _bind_theme_layout(self, theme_manager: Any, layout_manager: Any) -> None:
        if theme_manager is not None:
            register = getattr(theme_manager, "register_theme_aware_widget", None)
            if callable(register):
                register(self)
            current = getattr(theme_manager, "current_theme", None)
            if current is not None:
                self.apply_ghost_theme(current)
        if layout_manager is not None:
            changed = getattr(layout_manager, "layoutChanged", None)
            if changed is not None and hasattr(changed, "connect"):
                changed.connect(self.apply_ghost_layout)
            current = getattr(layout_manager, "current_layout", None)
            if current is not None:
                self.apply_ghost_layout(current)

    def _request_package_build(self) -> None:
        self.packageBuildRequested.emit(
            {
                "archive_type": str(self.archive_type_combo.currentData() or "MOD"),
                "output_path": self.package_output_edit.text().strip(),
                "include_source": self.include_source_check.isChecked(),
                "overwrite": self.overwrite_package_check.isChecked(),
            }
        )

    def _request_override_stage(self) -> None:
        self.stageOverrideRequested.emit(
            {
                "output_dir": self.stage_output_edit.text().strip(),
                "include_source": self.include_source_check.isChecked(),
                "replace_owned": self.replace_owned_stage_check.isChecked(),
            }
        )

    def _request_override_install(self) -> None:
        self.installOverrideRequested.emit(
            {
                "stage_path": self.stage_output_edit.text().strip(),
                "game_root": self.game_root_edit.text().strip(),
                "on_conflict": str(self.conflict_policy_combo.currentData() or "block"),
            }
        )

    def _activate_package_resource(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        row = dict(item.data(0, PAGE_ROW_ROLE) or {})
        if row:
            self.packageResourceActivated.emit(row)

    def _update_install_enabled(self) -> None:
        self.install_override_button.setEnabled(self._stage_ready and bool(self.game_root_edit.text().strip()))

    def set_package_resources(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._package_rows = [dict(row) for row in rows]
        self.package_resource_view.clear()
        for row in self._package_rows:
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(row.get("filename") or row.get("resref") or "resource"),
                    str(row.get("restype") or "").upper(),
                    _readable_status(row.get("role"), "Runtime"),
                    str(row.get("byte_count") or len(row.get("data", b"") or b"")),
                    _readable_status(row.get("status"), "Ready"),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, dict(row))
            item.setToolTip(0, str(row.get("source_path") or row.get("source_asset_id") or ""))
            self.package_resource_view.addTopLevelItem(item)
        self.build_package_button.setEnabled(self._readiness_ready and bool(self._package_rows))
        self.stage_override_button.setEnabled(self._readiness_ready and bool(self._package_rows))

    def set_readiness(self, row: Mapping[str, Any], *, issues: Sequence[Mapping[str, Any]]) -> None:
        summary = dict(row or {})
        ready = bool(summary.get("ready"))
        self._readiness_ready = ready
        self.readiness_label.setText(
            str(summary.get("summary") or ("Ready to package" if ready else "Not ready to package"))
        )
        self.set_issues(issues)
        self.build_package_button.setEnabled(ready and bool(self._package_rows))
        self.stage_override_button.setEnabled(ready and bool(self._package_rows))

    def set_archive_result(self, row: Mapping[str, Any]) -> None:
        result = dict(row or {})
        if result.get("output_path"):
            self.package_output_edit.setText(str(result.get("output_path")))
        self.package_result_label.setText(
            str(result.get("summary") or (
                f"Verified archive: {result.get('output_path')}" if result.get("committed") else "Archive build did not commit"
            ))
        )

    def set_override_stage_result(self, row: Mapping[str, Any]) -> None:
        result = dict(row or {})
        if result.get("stage_path"):
            self.stage_output_edit.setText(str(result.get("stage_path")))
        self._stage_ready = bool(result.get("committed") or result.get("ready"))
        self.stage_result_label.setText(
            str(result.get("summary") or (
                f"Verified stage: {result.get('stage_path')}" if self._stage_ready else "Override stage is not ready"
            ))
        )
        self._update_install_enabled()

    def set_install_result(self, row: Mapping[str, Any]) -> None:
        result = dict(row or {})
        self.install_result_label.setText(
            str(result.get("summary") or (
                f"Installed {len(result.get('installed', ()) or ())} file(s). Backup: {result.get('backup_path') or 'none needed'}"
                if result.get("committed")
                else "No game install was committed"
            ))
        )

    def set_issues(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.package_issue_view.clear()
        for source in rows:
            row = dict(source)
            item = QtWidgets.QTreeWidgetItem(
                [
                    _readable_status(row.get("severity"), "Info"),
                    str(row.get("resource") or ""),
                    str(row.get("message") or ""),
                ]
            )
            item.setData(0, PAGE_ROW_ROLE, row)
            self.package_issue_view.addTopLevelItem(item)

    def set_busy(self, busy: bool, *, message: str = "") -> None:
        for widget in (
            self.add_package_files_button,
            self.build_package_button,
            self.stage_override_button,
            self.inspect_stage_button,
            self.install_override_button,
        ):
            widget.setEnabled(not busy)
        if message:
            self.readiness_label.setText(str(message))
        if not busy:
            self.build_package_button.setEnabled(self._readiness_ready and bool(self._package_rows))
            self.stage_override_button.setEnabled(self._readiness_ready and bool(self._package_rows))
            self._update_install_enabled()

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        handle_width = 6
        spacing = 7
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value):
            handle_width = spacing_value("splitterHandleWidth", handle_width)
            spacing = spacing_value("panelSpacing", spacing)
        self.package_splitter.setHandleWidth(int(handle_width))
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setSpacing(int(spacing))


__all__ = [
    "NarrativeAssetFilterModel",
    "QtScriptingPackageOverridePage",
    "QtScriptingProjectHistoryPage",
]
