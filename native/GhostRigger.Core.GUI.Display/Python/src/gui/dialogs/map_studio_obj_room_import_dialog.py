"""Compact review dialog for Map Studio's custom OBJ room workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets


_COMPONENT_ID_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 1
_COMPONENT_RECOMMENDED_ROLE = _COMPONENT_ID_ROLE + 1
_COMPONENT_AREA_ROLE = _COMPONENT_ID_ROLE + 2
_COMPONENT_TRIANGLES_ROLE = _COMPONENT_ID_ROLE + 3


class _ObjFloorComponentFilterModel(QtCore.QSortFilterProxyModel):
    """Keep the normal review compact while retaining access to every island."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._show_detail_components = False
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)
        self.setSortCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

    def set_show_detail_components(self, enabled: bool) -> None:
        self._show_detail_components = bool(enabled)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        source = self.sourceModel()
        if source is None:
            return False
        first = source.index(source_row, 0, source_parent)
        if not self._show_detail_components:
            recommended = bool(source.data(first, _COMPONENT_RECOMMENDED_ROLE))
            area = float(source.data(first, _COMPONENT_AREA_ROLE) or 0.0)
            triangles = int(source.data(first, _COMPONENT_TRIANGLES_ROLE) or 0)
            if not recommended and area < 1.0 and triangles < 32:
                return False
        expression = self.filterRegularExpression()
        if not expression.pattern():
            return True
        for column in range(source.columnCount(source_parent)):
            text = str(source.data(source.index(source_row, column, source_parent)) or "")
            if expression.match(text).hasMatch():
                return True
        return False


class MapStudioObjRoomImportDialog(QtWidgets.QDialog):
    """Review scale, textures, and exact floor components before one commit."""

    def __init__(
        self,
        preparation: Any,
        parent: QtWidgets.QWidget | None = None,
        *,
        lock_existing_module: bool = False,
    ) -> None:
        super().__init__(parent)
        self.preparation = preparation
        self.setObjectName("mapStudioObjRoomImportDialog")
        self.setWindowTitle("Import OBJ Map")
        self.setModal(True)
        self._component_items: dict[str, QtGui.QStandardItem] = {}
        self._build_ui(lock_existing_module=bool(lock_existing_module))
        self._populate_components()
        self._refresh_acceptance()

    def _build_ui(self, *, lock_existing_module: bool) -> None:
        root = QtWidgets.QVBoxLayout(self)

        source_label = QtWidgets.QLabel(
            f"<b>{Path(str(self.preparation.source_path)).name}</b><br>"
            "Map Studio detected the source scale and converted it to KOTOR Z-up metres. "
            "Confirm which connected surfaces are real floor before collision is generated."
        )
        source_label.setObjectName("mapStudioObjImportSourceSummary")
        source_label.setWordWrap(True)
        root.addWidget(source_label)

        target_group = QtWidgets.QGroupBox("Module target")
        target_group.setObjectName("mapStudioObjImportTargetGroup")
        target_form = QtWidgets.QFormLayout(target_group)
        self.module_root_edit = QtWidgets.QLineEdit(str(self.preparation.module_root or ""))
        self.module_root_edit.setObjectName("mapStudioObjImportModuleResrefEdit")
        self.module_root_edit.setMaxLength(16)
        self.room_resref_edit = QtWidgets.QLineEdit(str(self.preparation.options.room_resref or ""))
        self.room_resref_edit.setObjectName("mapStudioObjImportRoomResrefEdit")
        self.room_resref_edit.setMaxLength(16)
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.setObjectName("mapStudioObjImportGameComboBox")
        self.game_combo.addItems(("KOTOR 2", "KOTOR 1"))
        self.game_combo.setCurrentIndex(0 if str(self.preparation.options.game).upper() == "K2" else 1)
        self.module_root_edit.setReadOnly(lock_existing_module)
        self.game_combo.setEnabled(not lock_existing_module)
        if lock_existing_module:
            existing_help = "This KMAP already owns the module ResRef and target game."
            self.module_root_edit.setToolTip(existing_help)
            self.game_combo.setToolTip(existing_help)
        target_form.addRow("Module ResRef", self.module_root_edit)
        target_form.addRow("Room ResRef", self.room_resref_edit)
        target_form.addRow("Target game", self.game_combo)
        root.addWidget(target_group)

        report = self.preparation.report
        extent = tuple(
            float(report.bounds_max[index]) - float(report.bounds_min[index])
            for index in range(3)
        )
        scale_group = QtWidgets.QGroupBox("Scale and materials")
        scale_group.setObjectName("mapStudioObjImportScaleGroup")
        scale_layout = QtWidgets.QVBoxLayout(scale_group)
        scale_text = QtWidgets.QLabel(
            f"{report.source_units.title()} at {float(report.meters_per_source_unit):g} m/unit; "
            f"{str(report.axis_mapping)}; centred in X/Y with authored height preserved.<br>"
            f"KOTOR bounds: {extent[0]:.2f} × {extent[1]:.2f} × {extent[2]:.2f} m "
            f"(height is about {extent[2] / 1.8:.1f} standard 1.8 m characters).<br>"
            f"{int(report.triangle_count):,} render triangles in {int(report.split_surface_count)} engine-safe surface(s)."
        )
        scale_text.setObjectName("mapStudioObjImportScaleSummary")
        scale_text.setWordWrap(True)
        scale_layout.addWidget(scale_text)
        texture_count = len(tuple(self.preparation.texture_imports or ()))
        missing_count = len(tuple(report.missing_texture_materials or ()))
        estimated_bytes = 0
        largest_side = 0
        for _material_name, _resref, path in tuple(self.preparation.texture_imports or ()):
            reader = QtGui.QImageReader(str(path))
            size = reader.size()
            if size.isValid():
                largest_side = max(largest_side, size.width(), size.height())
                source_largest = max(size.width(), size.height())
                ratio = min(1.0, 2048.0 / float(max(1, source_largest)))
                output_width = max(1, int(round(float(size.width()) * ratio)))
                output_height = max(1, int(round(float(size.height()) * ratio)))
                estimated_bytes += output_width * output_height * 4 + 18
        texture_summary = (
            f"{texture_count} resolved image(s) will become project-local TGA resources; "
            f"{missing_count} material(s) have no original diffuse image."
        )
        if estimated_bytes:
            texture_summary += (
                f" Estimated editable storage at the default 2048 px cap: "
                f"{estimated_bytes / (1024 ** 2):.0f} MiB."
            )
        if largest_side > 2048 or estimated_bytes > 256 * 1024 * 1024:
            texture_summary += " Large source textures can make import and game loading expensive; downsize intentionally if needed."
        if missing_count:
            missing_names = ", ".join(str(value) for value in tuple(report.missing_texture_materials or ()))
            neutral_resref = str(getattr(self.preparation, "neutral_texture_resref", "") or "obj_neutral")
            texture_summary += (
                f" Missing: {missing_names}. These surfaces will use an explicit neutral project texture "
                f"({neutral_resref}), not a claimed original texture."
            )
        texture_label = QtWidgets.QLabel(texture_summary)
        texture_label.setObjectName("mapStudioObjImportTextureSummary")
        texture_label.setWordWrap(True)
        scale_layout.addWidget(texture_label)
        texture_policy_row = QtWidgets.QHBoxLayout()
        texture_policy_row.addWidget(QtWidgets.QLabel("Maximum texture size"))
        self.texture_limit_combo = QtWidgets.QComboBox()
        self.texture_limit_combo.setObjectName("mapStudioObjImportTextureLimitComboBox")
        self.texture_limit_combo.addItem("2048 px — highest engine-safe detail", 2048)
        self.texture_limit_combo.addItem("1024 px — smaller/faster package", 1024)
        self.texture_limit_combo.setToolTip(
            "Odyssey has been observed mis-sampling textures above 2048 px. "
            "Larger OBJ images are resized once during the project import."
        )
        texture_policy_row.addWidget(self.texture_limit_combo)
        texture_policy_row.addStretch(1)
        scale_layout.addLayout(texture_policy_row)
        material_group = QtWidgets.QGroupBox("Material assignments")
        material_group.setObjectName("mapStudioObjImportMaterialAssignmentsGroup")
        material_group.setCheckable(True)
        material_group.setChecked(bool(missing_count))
        material_layout = QtWidgets.QVBoxLayout(material_group)
        self.material_table = QtWidgets.QTreeWidget()
        self.material_table.setObjectName("mapStudioObjImportMaterialTable")
        self.material_table.setHeaderLabels(("OBJ material", "KOTOR texture", "Source / status"))
        self.material_table.setRootIsDecorated(False)
        self.material_table.setAlternatingRowColors(True)
        missing_materials = {str(value) for value in tuple(report.missing_texture_materials or ())}
        for material_name, texture_resref, source_path in tuple(report.texture_sources or ()):
            missing = str(material_name) in missing_materials
            status = (
                "Missing original - generated neutral fallback"
                if missing
                else Path(str(source_path)).name
            )
            item = QtWidgets.QTreeWidgetItem(
                (str(material_name), str(texture_resref), status)
            )
            if source_path:
                item.setToolTip(2, str(source_path))
            self.material_table.addTopLevelItem(item)
        self.material_table.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.material_table.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.material_table.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        material_layout.addWidget(self.material_table)
        self.material_table.setVisible(material_group.isChecked())
        material_group.toggled.connect(self.material_table.setVisible)
        scale_layout.addWidget(material_group)
        root.addWidget(scale_group)

        floor_group = QtWidgets.QGroupBox("Walkmesh floor review")
        floor_group.setObjectName("mapStudioObjImportWalkmeshReviewGroup")
        floor_layout = QtWidgets.QVBoxLayout(floor_group)
        filter_row = QtWidgets.QHBoxLayout()
        self.component_search = QtWidgets.QLineEdit()
        self.component_search.setObjectName("mapStudioObjImportComponentSearch")
        self.component_search.setPlaceholderText("Filter floors by material, surface, or analysis…")
        self.show_detail_components = QtWidgets.QCheckBox("Show tiny/detail components")
        self.show_detail_components.setObjectName("mapStudioObjImportShowDetailComponentsCheckBox")
        filter_row.addWidget(self.component_search, 1)
        filter_row.addWidget(self.show_detail_components)
        floor_layout.addLayout(filter_row)

        self.component_model = QtGui.QStandardItemModel(0, 6, self)
        self.component_model.setHorizontalHeaderLabels(
            ("Floor", "Material / surface", "Triangles", "Area m²", "Height", "Analysis")
        )
        self.component_proxy = _ObjFloorComponentFilterModel(self)
        self.component_proxy.setSourceModel(self.component_model)
        self.component_table = QtWidgets.QTableView()
        self.component_table.setObjectName("mapStudioObjImportComponentTable")
        self.component_table.setModel(self.component_proxy)
        self.component_table.setSortingEnabled(True)
        self.component_table.setAlternatingRowColors(True)
        self.component_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.component_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        header = self.component_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        floor_layout.addWidget(self.component_table, 1)

        budget_row = QtWidgets.QHBoxLayout()
        budget_row.addWidget(QtWidgets.QLabel("Walkmesh face budget"))
        self.walkmesh_budget_spin = QtWidgets.QSpinBox()
        self.walkmesh_budget_spin.setObjectName("mapStudioObjImportWalkmeshBudgetSpinBox")
        self.walkmesh_budget_spin.setRange(2, 4096)
        self.walkmesh_budget_spin.setValue(2400)
        self.walkmesh_budget_spin.setToolTip(
            "2,136 faces is the largest value observed in the studied vanilla WOK library, not a proven engine "
            "ceiling. Up to 4,096 is available when exact boundaries, holes, or stacked levels require it; any "
            "result above the observed vanilla envelope requires explicit retail traversal proof."
        )
        budget_row.addWidget(self.walkmesh_budget_spin)
        budget_row.addStretch(1)
        floor_layout.addLayout(budget_row)
        self.review_check = QtWidgets.QCheckBox(
            "I reviewed the checked components. Only these surfaces may become walkable collision."
        )
        self.review_check.setObjectName("mapStudioObjImportWalkmeshReviewAcknowledgement")
        floor_layout.addWidget(self.review_check)
        self.selection_status = QtWidgets.QLabel()
        self.selection_status.setObjectName("mapStudioObjImportSelectionStatus")
        self.selection_status.setWordWrap(True)
        floor_layout.addWidget(self.selection_status)
        root.addWidget(floor_group, 1)

        warnings = tuple(report.warnings or ())
        if warnings:
            warning_box = QtWidgets.QPlainTextEdit()
            warning_box.setObjectName("mapStudioObjImportWarnings")
            warning_box.setReadOnly(True)
            warning_box.setPlainText("\n".join(f"• {value}" for value in warnings))
            warning_box.setToolTip("Import warnings remain visible in the KMAP/output log after commit.")
            root.addWidget(warning_box)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("mapStudioObjImportButtonBox")
        self.import_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.import_button.setText("Import Reviewed Room")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self.component_search.textChanged.connect(self._apply_filter)
        self.show_detail_components.toggled.connect(self.component_proxy.set_show_detail_components)
        self.review_check.toggled.connect(self._refresh_acceptance)
        self.walkmesh_budget_spin.valueChanged.connect(lambda _value: self._refresh_acceptance())
        self.module_root_edit.textChanged.connect(self._refresh_acceptance)
        self.room_resref_edit.textChanged.connect(self._refresh_acceptance)
        self.component_model.itemChanged.connect(lambda _item: self._refresh_acceptance())

    def _populate_components(self) -> None:
        self.component_model.setRowCount(0)
        for component in tuple(self.preparation.components or ()):
            component_id = str(component.component_id)
            first = QtGui.QStandardItem(component_id)
            first.setCheckable(True)
            first.setEditable(False)
            first.setCheckState(
                QtCore.Qt.CheckState.Checked if bool(component.recommended) else QtCore.Qt.CheckState.Unchecked
            )
            first.setData(component_id, _COMPONENT_ID_ROLE)
            first.setData(bool(component.recommended), _COMPONENT_RECOMMENDED_ROLE)
            first.setData(float(component.area), _COMPONENT_AREA_ROLE)
            first.setData(int(component.triangle_count), _COMPONENT_TRIANGLES_ROLE)
            self._component_items[component_id] = first
            material_surface = ", ".join(tuple(component.material_names or ()) or tuple(component.surface_names or ()))
            triangle_item = QtGui.QStandardItem()
            triangle_item.setData(int(component.triangle_count), QtCore.Qt.ItemDataRole.DisplayRole)
            area_item = QtGui.QStandardItem()
            area_item.setData(round(float(component.area), 3), QtCore.Qt.ItemDataRole.DisplayRole)
            height = f"{float(component.bounds_min[2]):.2f} to {float(component.bounds_max[2]):.2f} m"
            row = (
                first,
                QtGui.QStandardItem(material_surface),
                triangle_item,
                area_item,
                QtGui.QStandardItem(height),
                QtGui.QStandardItem(str(component.recommendation or "Review manually.")),
            )
            for item in row[1:]:
                item.setEditable(False)
            self.component_model.appendRow(list(row))
        self.component_table.sortByColumn(3, QtCore.Qt.SortOrder.DescendingOrder)

    def _apply_filter(self, text: str) -> None:
        expression = QtCore.QRegularExpression(
            QtCore.QRegularExpression.escape(str(text or "")),
            QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption,
        )
        self.component_proxy.setFilterRegularExpression(expression)

    def selected_component_ids(self) -> tuple[str, ...]:
        return tuple(
            component_id
            for component_id, item in self._component_items.items()
            if item.checkState() == QtCore.Qt.CheckState.Checked
        )

    def module_root(self) -> str:
        return self.module_root_edit.text().strip()

    def room_resref(self) -> str:
        return self.room_resref_edit.text().strip()

    def target_game(self) -> str:
        return "K2" if self.game_combo.currentIndex() == 0 else "K1"

    def target_face_budget(self) -> int:
        return int(self.walkmesh_budget_spin.value())

    def texture_max_dimension(self) -> int:
        return int(self.texture_limit_combo.currentData() or 2048)

    def _refresh_acceptance(self) -> None:
        selected = self.selected_component_ids()
        target_ok = bool(self.module_root()) and bool(self.room_resref())
        acknowledged = bool(self.review_check.isChecked())
        self.import_button.setEnabled(bool(selected and target_ok and acknowledged))
        if not selected:
            self.selection_status.setText("Select at least one connected floor component.")
        elif not acknowledged:
            self.selection_status.setText(
                f"{len(selected)} component(s) checked. Confirm the review statement to enable import."
            )
        else:
            envelope_note = (
                " Budget is above the studied 2,136-face vanilla envelope; structural checks still run, but retail "
                "KOTOR traversal proof is mandatory."
                if self.target_face_budget() > 2136
                else ""
            )
            self.selection_status.setText(
                f"Ready to generate collision from {len(selected)} explicitly reviewed component(s).{envelope_note}"
            )


__all__ = ["MapStudioObjRoomImportDialog"]
