"""Presentation-only typed GFF/blueprint page for the Scripting Suite.

The page renders immutable field snapshots and emits authoring intent.  File
dialogs, GFF parsing, mutation, verification, and writes remain in the suite
controller and :mod:`src.core.scripting.blueprint_authoring`.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Optional, Sequence

from PySide6 import QtCore, QtGui, QtWidgets


BLUEPRINT_ROW_ROLE = int(QtCore.Qt.UserRole) + 3401
BLUEPRINT_PATH_ROLE = BLUEPRINT_ROW_ROLE + 1


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return dict(asdict(value))
    return {
        name: getattr(value, name)
        for name in (
            "path",
            "parent_path",
            "label",
            "field_type",
            "kind",
            "display_value",
            "edit_text",
            "editable",
            "depth",
            "struct_id",
            "child_count",
            "content_type",
            "resource_type",
            "source_path",
            "root_struct_id",
            "field_count",
            "editable_field_count",
            "dirty",
            "is_blueprint",
            "severity",
            "code",
            "message",
        )
        if hasattr(value, name)
    }


class QtScriptingBlueprintPage(QtWidgets.QWidget):
    """Searchable complete GFF tree with a type-aware scalar inspector."""

    openRequested = QtCore.Signal()
    saveRequested = QtCore.Signal()
    saveAsRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()
    searchRequested = QtCore.Signal(str)
    fieldEditRequested = QtCore.Signal(str, str)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        theme_manager: Any = None,
        layout_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioBlueprintPage")
        self.setProperty("ghostLayoutId", "scriptingDialogueStudio.blueprints")
        self._summary: dict[str, Any] = {}
        self._rows_by_path: dict[str, dict[str, Any]] = {}
        self._items_by_path: dict[str, QtGui.QStandardItem] = {}
        self._build_ui()
        self._bind_theme_layout(theme_manager, layout_manager)
        self.set_document({})

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Typed Blueprint / GFF Editor", self)
        title.setObjectName("scriptingStudioBlueprintHeading")
        title.setProperty("headingLevel", 1)
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(max(12, title_font.pointSize() + 2))
        title.setFont(title_font)
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.dirty_label = QtWidgets.QLabel("No resource open", self)
        self.dirty_label.setObjectName("scriptingStudioBlueprintDirtyLabel")
        title_row.addWidget(self.dirty_label)
        root.addLayout(title_row)

        guidance = QtWidgets.QLabel(
            "Edit UTC, UTP, UTD, UTI, UTE, UTM, UTS, UTT, UTW and other GFF resources without flattening them. "
            "Nested structs, list order, struct IDs, and fields GhostStudio does not recognize remain intact. "
            "PyKotor may normalize binary table layout; verified semantic readback is the save gate.",
            self,
        )
        guidance.setObjectName("scriptingStudioBlueprintGuidance")
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        command_row = QtWidgets.QHBoxLayout()
        self.open_button = self._button(
            "Open GFF…", "scriptingStudioBlueprintOpenButton", QtWidgets.QStyle.SP_DialogOpenButton
        )
        self.save_button = self._button(
            "Save", "scriptingStudioBlueprintSaveButton", QtWidgets.QStyle.SP_DialogSaveButton
        )
        self.save_as_button = self._button(
            "Save As…", "scriptingStudioBlueprintSaveAsButton", QtWidgets.QStyle.SP_DialogSaveButton
        )
        self.validate_button = self._button(
            "Check Structure", "scriptingStudioBlueprintValidateButton", QtWidgets.QStyle.SP_DialogApplyButton
        )
        for button in (self.open_button, self.save_button, self.save_as_button, self.validate_button):
            command_row.addWidget(button)
        command_row.addStretch(1)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioBlueprintSearchEdit")
        self.search_edit.setPlaceholderText("Search path, field name, type, or value…")
        self.search_edit.setClearButtonEnabled(True)
        command_row.addWidget(self.search_edit, 1)
        root.addLayout(command_row)

        summary_group = QtWidgets.QGroupBox("Open Resource", self)
        summary_group.setObjectName("scriptingStudioBlueprintSummaryGroup")
        summary_layout = QtWidgets.QGridLayout(summary_group)
        self.resource_type_label = QtWidgets.QLabel("—", summary_group)
        self.resource_type_label.setObjectName("scriptingStudioBlueprintResourceType")
        self.root_id_label = QtWidgets.QLabel("—", summary_group)
        self.root_id_label.setObjectName("scriptingStudioBlueprintRootId")
        self.field_count_label = QtWidgets.QLabel("—", summary_group)
        self.field_count_label.setObjectName("scriptingStudioBlueprintFieldCount")
        self.path_edit = QtWidgets.QLineEdit(summary_group)
        self.path_edit.setObjectName("scriptingStudioBlueprintSourcePath")
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Open a KOTOR GFF or blueprint resource")
        summary_layout.addWidget(QtWidgets.QLabel("Content"), 0, 0)
        summary_layout.addWidget(self.resource_type_label, 0, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Root struct ID"), 0, 2)
        summary_layout.addWidget(self.root_id_label, 0, 3)
        summary_layout.addWidget(QtWidgets.QLabel("Fields"), 0, 4)
        summary_layout.addWidget(self.field_count_label, 0, 5)
        summary_layout.addWidget(QtWidgets.QLabel("Source"), 1, 0)
        summary_layout.addWidget(self.path_edit, 1, 1, 1, 5)
        summary_layout.setColumnStretch(1, 1)
        root.addWidget(summary_group)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setObjectName("scriptingStudioBlueprintSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._build_tree_panel())
        self.splitter.addWidget(self._build_inspector_panel())
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        root.addWidget(self.splitter, 1)

        self.status_label = QtWidgets.QLabel("Ready", self)
        self.status_label.setObjectName("scriptingStudioBlueprintStatus")
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        root.addWidget(self.status_label)

        self.open_button.clicked.connect(self.openRequested.emit)
        self.save_button.clicked.connect(self.saveRequested.emit)
        self.save_as_button.clicked.connect(self.saveAsRequested.emit)
        self.validate_button.clicked.connect(self.validateRequested.emit)
        self.search_edit.textChanged.connect(self._filter_changed)
        self.tree.selectionModel().currentChanged.connect(self._selection_changed)
        self.apply_button.clicked.connect(self._apply_current)

    def _button(
        self,
        text: str,
        name: str,
        standard_icon: QtWidgets.QStyle.StandardPixmap,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(self.style().standardIcon(standard_icon), text, self)
        button.setObjectName(name)
        return button

    def _build_tree_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget(self)
        panel.setObjectName("scriptingStudioBlueprintTreePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QtWidgets.QLabel("Complete GFF Tree", panel)
        heading.setObjectName("scriptingStudioBlueprintTreeHeading")
        layout.addWidget(heading)

        self.model = QtGui.QStandardItemModel(0, 3, self)
        self.model.setHorizontalHeaderLabels(["Field", "Type", "Value / structure"])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setRecursiveFilteringEnabled(True)
        self.tree = QtWidgets.QTreeView(panel)
        self.tree.setObjectName("scriptingStudioBlueprintTree")
        self.tree.setModel(self.proxy)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.tree, 1)
        return panel

    def _build_inspector_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget(self)
        panel.setObjectName("scriptingStudioBlueprintInspectorPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 0, 0)
        heading = QtWidgets.QLabel("Selected Field", panel)
        heading.setObjectName("scriptingStudioBlueprintInspectorHeading")
        layout.addWidget(heading)
        form = QtWidgets.QFormLayout()
        self.selected_path_edit = QtWidgets.QLineEdit(panel)
        self.selected_path_edit.setObjectName("scriptingStudioBlueprintSelectedPath")
        self.selected_path_edit.setReadOnly(True)
        self.selected_type_label = QtWidgets.QLabel("—", panel)
        self.selected_type_label.setObjectName("scriptingStudioBlueprintSelectedType")
        self.selected_structure_label = QtWidgets.QLabel("—", panel)
        self.selected_structure_label.setObjectName("scriptingStudioBlueprintSelectedStructure")
        form.addRow("Stable path", self.selected_path_edit)
        form.addRow("GFF type", self.selected_type_label)
        form.addRow("Structure", self.selected_structure_label)
        layout.addLayout(form)
        self.value_edit = QtWidgets.QPlainTextEdit(panel)
        self.value_edit.setObjectName("scriptingStudioBlueprintValueEditor")
        self.value_edit.setPlaceholderText("Select an editable scalar field")
        layout.addWidget(self.value_edit, 1)
        self.format_hint_label = QtWidgets.QLabel("Select a field to see its required format.", panel)
        self.format_hint_label.setObjectName("scriptingStudioBlueprintFormatHint")
        self.format_hint_label.setWordWrap(True)
        layout.addWidget(self.format_hint_label)
        self.apply_button = QtWidgets.QPushButton("Apply Typed Value", panel)
        self.apply_button.setObjectName("scriptingStudioBlueprintApplyButton")
        layout.addWidget(self.apply_button)

        diagnostics_group = QtWidgets.QGroupBox("Structure Check", panel)
        diagnostics_group.setObjectName("scriptingStudioBlueprintDiagnosticsGroup")
        diagnostics_layout = QtWidgets.QVBoxLayout(diagnostics_group)
        self.diagnostics = QtWidgets.QTreeWidget(diagnostics_group)
        self.diagnostics.setObjectName("scriptingStudioBlueprintDiagnostics")
        self.diagnostics.setHeaderLabels(["Severity", "Path", "Issue"])
        self.diagnostics.setAlternatingRowColors(True)
        self.diagnostics.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.diagnostics.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.diagnostics.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.diagnostics.setMaximumHeight(160)
        diagnostics_layout.addWidget(self.diagnostics)
        layout.addWidget(diagnostics_group)
        self._show_row({})
        return panel

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

    def set_document(self, summary: Mapping[str, Any] | object) -> None:
        self._summary = _mapping(summary)
        loaded = bool(self._summary.get("content_type"))
        content = str(self._summary.get("content_type") or "—")
        blueprint = bool(self._summary.get("is_blueprint"))
        self.resource_type_label.setText(f"{content}{' blueprint' if loaded and blueprint else ''}")
        root_id = self._summary.get("root_struct_id")
        self.root_id_label.setText(str(root_id) if root_id is not None else "—")
        field_count = int(self._summary.get("field_count") or 0)
        editable_count = int(self._summary.get("editable_field_count") or 0)
        self.field_count_label.setText(f"{field_count} total • {editable_count} editable" if loaded else "—")
        self.path_edit.setText(str(self._summary.get("source_path") or ""))
        dirty = bool(self._summary.get("dirty"))
        self.dirty_label.setText("Unsaved changes" if dirty else ("Saved" if loaded else "No resource open"))
        self.save_button.setEnabled(loaded and dirty)
        self.save_as_button.setEnabled(loaded)
        self.validate_button.setEnabled(loaded)
        self.search_edit.setEnabled(loaded)

    def set_field_rows(self, rows: Sequence[Mapping[str, Any] | object]) -> None:
        selected_path = self.selected_path_edit.text()
        self.model.removeRows(0, self.model.rowCount())
        self._rows_by_path.clear()
        self._items_by_path.clear()
        for source in rows:
            row = _mapping(source)
            path = str(row.get("path") or "")
            if not path:
                continue
            parent_path = str(row.get("parent_path") or "$")
            items = [
                QtGui.QStandardItem(str(row.get("label") or path)),
                QtGui.QStandardItem(str(row.get("field_type") or "")),
                QtGui.QStandardItem(str(row.get("display_value") or "")),
            ]
            for item in items:
                item.setEditable(False)
            items[0].setData(dict(row), BLUEPRINT_ROW_ROLE)
            items[0].setData(path, BLUEPRINT_PATH_ROLE)
            items[0].setToolTip(path)
            parent_item = self._items_by_path.get(parent_path)
            if parent_item is None:
                self.model.appendRow(items)
            else:
                parent_item.appendRow(items)
            self._rows_by_path[path] = row
            self._items_by_path[path] = items[0]
        self.tree.expandToDepth(1)
        if selected_path and selected_path in self._items_by_path:
            self.select_path(selected_path)
        elif self.model.rowCount():
            self.tree.setCurrentIndex(self.proxy.mapFromSource(self.model.index(0, 0)))
        else:
            self._show_row({})

    def select_path(self, path: str) -> bool:
        item = self._items_by_path.get(str(path))
        if item is None:
            return False
        source = item.index()
        proxy = self.proxy.mapFromSource(source)
        if not proxy.isValid():
            return False
        self.tree.setCurrentIndex(proxy)
        self.tree.scrollTo(proxy)
        return True

    def set_diagnostics(self, rows: Sequence[Mapping[str, Any] | object]) -> None:
        self.diagnostics.clear()
        blocking = 0
        warnings = 0
        for source in rows:
            row = _mapping(source)
            severity = str(row.get("severity") or "info").capitalize()
            blocking += int(severity.casefold() in {"blocking", "error"})
            warnings += int(severity.casefold() == "warning")
            item = QtWidgets.QTreeWidgetItem(
                [severity, str(row.get("path") or "$"), str(row.get("message") or row.get("code") or "")]
            )
            item.setData(0, BLUEPRINT_ROW_ROLE, row)
            self.diagnostics.addTopLevelItem(item)
        if rows:
            self.set_status(f"Structure check: {blocking} blocking • {warnings} warning • {len(rows)} total", error=bool(blocking))
        else:
            self.set_status("Verified semantic GFF readback; no structure issues found.")

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(str(message or "Ready"))
        self.status_label.setProperty("status", "error" if error else "normal")
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        self.status_label.update()

    def set_busy(self, busy: bool, *, message: str = "Working…") -> None:
        for widget in (
            self.open_button,
            self.save_button,
            self.save_as_button,
            self.validate_button,
            self.search_edit,
            self.tree,
            self.value_edit,
            self.apply_button,
        ):
            widget.setEnabled(not busy)
        if busy:
            self.set_status(message)
        else:
            self.set_document(self._summary)
            self._show_row(self._current_row())

    def _filter_changed(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        self.searchRequested.emit(str(text))
        if text:
            self.tree.expandAll()

    def _current_row(self) -> dict[str, Any]:
        current = self.tree.currentIndex()
        if not current.isValid():
            return {}
        source = self.proxy.mapToSource(current).siblingAtColumn(0)
        item = self.model.itemFromIndex(source)
        return dict(item.data(BLUEPRINT_ROW_ROLE) or {}) if item is not None else {}

    def _selection_changed(self, _current: QtCore.QModelIndex, _previous: QtCore.QModelIndex) -> None:
        self._show_row(self._current_row())

    def _show_row(self, row: Mapping[str, Any]) -> None:
        current = dict(row or {})
        path = str(current.get("path") or "")
        field_type = str(current.get("field_type") or "")
        editable = bool(current.get("editable"))
        struct_id = current.get("struct_id")
        child_count = int(current.get("child_count") or 0)
        self.selected_path_edit.setText(path)
        self.selected_type_label.setText(field_type or "—")
        if struct_id is not None:
            structure = f"Struct ID {struct_id} • {child_count} child field(s)"
        elif field_type == "List":
            structure = f"List • {child_count} struct(s)"
        else:
            structure = "Scalar field" if editable else "—"
        self.selected_structure_label.setText(structure)
        blocker = QtCore.QSignalBlocker(self.value_edit)
        self.value_edit.setPlainText(str(current.get("edit_text") or current.get("display_value") or ""))
        del blocker
        self.value_edit.setReadOnly(not editable)
        self.apply_button.setEnabled(editable)
        self.format_hint_label.setText(self._format_hint(field_type, editable))

    @staticmethod
    def _format_hint(field_type: str, editable: bool) -> str:
        if not editable:
            return "Containers are read-only here. Edit their existing scalar children so unknown structure remains intact."
        return {
            "UInt8": "Whole number from 0 to 255. Decimal and 0x-prefixed hexadecimal are accepted.",
            "Int8": "Whole number from -128 to 127. Decimal and 0x-prefixed hexadecimal are accepted.",
            "UInt16": "Whole number from 0 to 65,535.",
            "Int16": "Whole number from -32,768 to 32,767.",
            "UInt32": "Whole number from 0 to 4,294,967,295.",
            "Int32": "Whole number from -2,147,483,648 to 2,147,483,647.",
            "UInt64": "Unsigned 64-bit whole number.",
            "Int64": "Signed 64-bit whole number.",
            "Single": "Finite single-precision number.",
            "Double": "Finite double-precision number.",
            "String": "Text is stored exactly as entered.",
            "ResRef": "KOTOR resource reference (maximum 16 valid characters).",
            "LocalizedString": "JSON object with stringref and substrings fields. Existing languages remain unless removed from the JSON.",
            "Binary": "Hexadecimal byte pairs; spaces, commas, colons, dashes, and 0x prefixes are accepted.",
            "Vector3": "Three comma- or space-separated numbers: X, Y, Z.",
            "Vector4": "Four comma- or space-separated numbers: X, Y, Z, W.",
        }.get(field_type, f"Value must be valid for the existing {field_type} GFF type.")

    def _apply_current(self) -> None:
        row = self._current_row()
        path = str(row.get("path") or "")
        if path and row.get("editable"):
            self.fieldEditRequested.emit(path, self.value_edit.toPlainText())

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        handle_width = 6
        spacing = 7
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value):
            handle_width = spacing_value("splitterHandleWidth", handle_width)
            spacing = spacing_value("panelSpacing", spacing)
        self.splitter.setHandleWidth(int(handle_width))
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setSpacing(int(spacing))


__all__ = ["BLUEPRINT_PATH_ROLE", "BLUEPRINT_ROW_ROLE", "QtScriptingBlueprintPage"]
