"""Presentation widgets for the Custom KOTOR Head Builder.

The widgets in this module deliberately contain no MDL parsing, skin transfer,
2DA mutation, package installation, or project persistence.  They collect
plain user input, emit typed action payloads, and render immutable results from
``HeadBuilderService`` through the Core Tools controller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from PySide6 import QtCore, QtGui, QtWidgets


HEAD_BUILDER_STEPS: tuple[tuple[int, str], ...] = (
    (1, "Project and game"),
    (2, "Import custom art"),
    (3, "Select native donor"),
    (4, "Align neck seam and head hook"),
    (5, "Replace donor geometry and skin"),
    (6, "UVs, textures, and materials"),
    (7, "Attachment and animation preview"),
    (8, "Optional hair/accessory physics"),
    (9, "Binary preflight"),
    (10, "Game records and package"),
    (11, "Safe retail test"),
)

RETAIL_CHECKS: tuple[tuple[str, str], ...] = (
    ("idle", "Neutral idle and camera rotation"),
    ("movement", "Walk and run"),
    ("combat", "Combat and several attacks"),
    ("dialogue", "Talk, emotion, and head tracking"),
    ("save_load", "Save and reload"),
    ("warp", "Leave and re-enter or warp"),
    ("attachment", "Head remains attached at the neck seam"),
    ("texture", "Texture and UV orientation remain correct"),
)


def _dialog_start(value: str) -> str:
    path = Path(str(value or "")).expanduser()
    if path.is_file():
        return str(path.parent)
    return str(path)


def _set_combo_data(combo: QtWidgets.QComboBox, value: object) -> None:
    index = combo.findData(value)
    if index < 0:
        index = combo.findText(str(value or ""), QtCore.Qt.MatchFixedString)
    if index >= 0:
        combo.setCurrentIndex(index)


def _plain_text(value: object) -> str:
    return str(value or "").strip()


class _PathField(QtWidgets.QWidget):
    """Theme-neutral path input with an explicit browse action."""

    changed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        folder: bool,
        title: str,
        file_filter: str = "All files (*)",
        save: bool = False,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.folder = bool(folder)
        self.title = str(title)
        self.file_filter = str(file_filter)
        self.save = bool(save)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.edit = QtWidgets.QLineEdit(self)
        self.edit.setClearButtonEnabled(True)
        self.button = QtWidgets.QPushButton("Browse…", self)
        self.button.clicked.connect(self._browse)
        self.edit.textChanged.connect(self.changed.emit)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: object) -> None:  # noqa: N802 - Qt convention
        self.edit.setText(str(value or ""))

    def _browse(self) -> None:
        current = _dialog_start(self.text())
        if self.folder:
            selected = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.title,
                current,
            )
        elif self.save:
            selected, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self.title,
                self.text(),
                self.file_filter,
            )
        else:
            selected, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                self.title,
                current,
                self.file_filter,
            )
        if selected:
            self.setText(selected)


class _AnchorRow(QtWidgets.QWidget):
    captureRequested = QtCore.Signal(str, str)

    def __init__(
        self,
        role: str,
        label: str,
        *,
        optional: bool,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.role = role
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(4)
        layout.setVerticalSpacing(3)
        self.enabled = QtWidgets.QCheckBox(label, self)
        self.enabled.setChecked(not optional)
        self.enabled.setToolTip(
            "The centre anchor is required. Left/front anchors fix orientation "
            "and scale when enabled."
        )
        layout.addWidget(self.enabled, 0, 0, 1, 2)
        self.source_spins = self._spins()
        self.target_spins = self._spins()
        layout.addWidget(QtWidgets.QLabel("Custom"), 1, 0)
        self._add_spins(layout, self.source_spins, 1)
        source_pick = QtWidgets.QPushButton("Use selected vertex", self)
        source_pick.clicked.connect(
            lambda: self.captureRequested.emit(self.role, "source")
        )
        layout.addWidget(source_pick, 1, 5)
        layout.addWidget(QtWidgets.QLabel("Body"), 2, 0)
        self._add_spins(layout, self.target_spins, 2)
        target_pick = QtWidgets.QPushButton("Use selected vertex", self)
        target_pick.clicked.connect(
            lambda: self.captureRequested.emit(self.role, "target")
        )
        layout.addWidget(target_pick, 2, 5)
        self.weight = QtWidgets.QDoubleSpinBox(self)
        self.weight.setRange(0.01, 100.0)
        self.weight.setDecimals(3)
        self.weight.setValue(1.0)
        layout.addWidget(QtWidgets.QLabel("Weight"), 0, 3)
        layout.addWidget(self.weight, 0, 4)

    @staticmethod
    def _spins() -> tuple[QtWidgets.QDoubleSpinBox, ...]:
        rows: list[QtWidgets.QDoubleSpinBox] = []
        for _axis in range(3):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-100000.0, 100000.0)
            spin.setDecimals(6)
            spin.setSingleStep(0.01)
            rows.append(spin)
        return tuple(rows)

    @staticmethod
    def _add_spins(
        layout: QtWidgets.QGridLayout,
        spins: tuple[QtWidgets.QDoubleSpinBox, ...],
        row: int,
    ) -> None:
        for column, spin in enumerate(spins, start=2):
            spin.setPrefix(("X ", "Y ", "Z ")[column - 2])
            layout.addWidget(spin, row, column)

    def payload(self) -> dict[str, Any] | None:
        if not self.enabled.isChecked():
            return None
        return {
            "role": self.role,
            "source_point": [spin.value() for spin in self.source_spins],
            "target_point": [spin.value() for spin in self.target_spins],
            "weight": self.weight.value(),
        }

    def set_point(self, side: str, point: Iterable[float]) -> None:
        values = tuple(float(value) for value in point)
        if len(values) < 3:
            return
        spins = self.source_spins if side == "source" else self.target_spins
        self.enabled.setChecked(True)
        for spin, value in zip(spins, values[:3]):
            spin.setValue(value)


class QtHeadBuilderProperties(QtWidgets.QWidget):
    """Context-sensitive right-side controls for all eleven Head steps."""

    actionRequested = QtCore.Signal(str, object)
    captureRequested = QtCore.Signal(str, str)
    previewAnimationRequested = QtCore.Signal(str)
    dialoguePreviewRequested = QtCore.Signal(str, str)
    dialoguePreviewStopRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeadBuilderProperties")
        self.setProperty("ghostLayoutId", "headBuilderProperties")
        self._loading = False
        self._busy = False
        self._anchor_rows: dict[str, _AnchorRow] = {}
        self._retail_checks: dict[str, QtWidgets.QCheckBox] = {}
        self._source_texture_paths: list[str] = []
        self._evidence_paths: list[str] = []
        self._install_preview_id = ""
        self._facial_performance_mode = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        heading = QtWidgets.QVBoxLayout()
        self.title = QtWidgets.QLabel("1. Project and game", self)
        title_font = self.title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self.title.setFont(title_font)
        self.title.setWordWrap(True)
        self.status = QtWidgets.QLabel("Ready", self)
        self.status.setObjectName("HeadBuilderCommandStatus")
        self.status.setWordWrap(True)
        self.status.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        heading.addWidget(self.title)
        heading.addWidget(self.status)
        root.addLayout(heading)
        self.guidance = QtWidgets.QLabel(
            "Create or open a Head Project. Structural proof, editor preview, "
            "and retail observation are tracked separately.",
            self,
        )
        self.guidance.setWordWrap(True)
        root.addWidget(self.guidance)
        self.facial_mode_notice = QtWidgets.QLabel(self)
        self.facial_mode_notice.setObjectName(
            "HeadBuilderFacialPerformanceNotice"
        )
        self.facial_mode_notice.setProperty("role", "warning")
        self.facial_mode_notice.setWordWrap(True)
        self.facial_mode_notice.setVisible(False)
        root.addWidget(self.facial_mode_notice)
        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.setObjectName("HeadBuilderStepStack")
        for builder in (
            self._build_project_page,
            self._build_import_page,
            self._build_donor_page,
            self._build_alignment_page,
            self._build_skin_page,
            self._build_texture_page,
            self._build_preview_page,
            self._build_physics_page,
            self._build_preflight_page,
            self._build_package_page,
            self._build_retail_page,
        ):
            self.stack.addWidget(self._scroll_page(builder()))
        root.addWidget(self.stack, 1)

    def set_facial_performance_mode(self, enabled: bool) -> None:
        """Show the export contract for the advanced facial-head workflow."""

        self._facial_performance_mode = bool(enabled)
        self.facial_mode_notice.setText(
            "Custom Animation Patch required for full facial-performance curves. "
            "A vanilla LIP fallback is available for an unpatched game."
        )
        self.facial_mode_notice.setVisible(self._facial_performance_mode)
        if hasattr(self, "skin_settings_group"):
            self.skin_settings_group.setTitle(
                "Semantic facial surface transfer"
                if self._facial_performance_mode
                else "Donor surface transfer"
            )
        if hasattr(self, "maximum_surface_distance"):
            current_distance = self.maximum_surface_distance.value()
            if self._facial_performance_mode and abs(
                current_distance - 100.0
            ) <= 1.0e-9:
                self.maximum_surface_distance.setValue(0.05)
            elif not self._facial_performance_mode and abs(
                current_distance - 0.05
            ) <= 1.0e-9:
                self.maximum_surface_distance.setValue(100.0)
        if hasattr(self, "transplant_button"):
            self.transplant_button.setText(
                "Build animated face, eyes, lids, teeth, and tongue"
                if self._facial_performance_mode
                else "Replace donor geometry and transfer skin"
            )
        if hasattr(self, "weight_edit_group"):
            self.weight_edit_group.setEnabled(
                not self._facial_performance_mode
            )
            self.weight_edit_group.setToolTip(
                (
                    "Semantic mode assigns each facial component to its exact "
                    "native control; manual single-skin edits are disabled."
                )
                if self._facial_performance_mode
                else ""
            )

    def _page(
        self,
        object_name: str,
        summary: str,
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QVBoxLayout]:
        page = QtWidgets.QWidget(self)
        page.setObjectName(object_name)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(7)
        copy = QtWidgets.QLabel(summary, page)
        copy.setWordWrap(True)
        layout.addWidget(copy)
        return page, layout

    @staticmethod
    def _scroll_page(page: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QtWidgets.QFrame.NoFrame)
        area.setWidget(page)
        return area

    @staticmethod
    def _form_group(
        title: str,
        parent: QtWidgets.QWidget,
    ) -> tuple[QtWidgets.QGroupBox, QtWidgets.QFormLayout]:
        group = QtWidgets.QGroupBox(title, parent)
        form = QtWidgets.QFormLayout(group)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        return group, form

    def _build_project_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepProjectGame",
            "Choose the target game and output identity before reading any "
            "donor. Verification fingerprints the EXE, chitin.key, and one "
            "stock model without modifying the installation.",
        )
        project_group, form = self._form_group("Head Project", page)
        self.project_name = QtWidgets.QLineEdit("Untitled Head", page)
        self.project_name.setObjectName("HeadBuilderProjectName")
        self.game = QtWidgets.QComboBox(page)
        self.game.addItem("KOTOR I", "K1")
        self.game.addItem("KOTOR II", "K2")
        self.game.setCurrentIndex(1)
        self.resource_view = QtWidgets.QComboBox(page)
        self.resource_view.addItem("Stock game resources only", "stock_only")
        self.resource_view.addItem(
            "Effective resources including Override",
            "effective_override",
        )
        self.game_dir = _PathField(
            folder=True,
            title="Choose the installed KOTOR folder",
            parent=page,
        )
        self.output_dir = _PathField(
            folder=True,
            title="Choose the Head Project output folder",
            parent=page,
        )
        self.output_resref = QtWidgets.QLineEdit(page)
        self.output_resref.setObjectName("HeadBuilderOutputResref")
        self.output_resref.setMaxLength(16)
        self.output_resref.setPlaceholderText("Example: P_MYHEAD")
        self.context_gender = QtWidgets.QComboBox(page)
        for label, data in (
            ("Female", "female"),
            ("Male", "male"),
            ("Custom/other", "custom"),
        ):
            self.context_gender.addItem(label, data)
        self.context_role = QtWidgets.QComboBox(page)
        self.context_role.addItem("Player character", "player")
        self.context_role.addItem("Companion or NPC", "companion")
        self.body_resref = QtWidgets.QLineEdit(page)
        self.body_resref.setMaxLength(16)
        self.body_resref.setPlaceholderText("Compatible headless body ResRef")
        form.addRow("Project name", self.project_name)
        form.addRow("Target game", self.game)
        form.addRow("Resource view", self.resource_view)
        form.addRow("Installed game", self.game_dir)
        form.addRow("Output folder", self.output_dir)
        form.addRow("New head ResRef", self.output_resref)
        form.addRow("Character context", self.context_gender)
        form.addRow("Use as", self.context_role)
        form.addRow("Preview body", self.body_resref)
        layout.addWidget(project_group)
        row = QtWidgets.QHBoxLayout()
        new_button = QtWidgets.QPushButton("New Head Project", page)
        new_button.setObjectName("HeadBuilderNewProjectButton")
        new_button.clicked.connect(
            lambda: self._emit("new_project", self.project_payload())
        )
        open_button = QtWidgets.QPushButton("Open…", page)
        open_button.clicked.connect(self._choose_open_project)
        save_button = QtWidgets.QPushButton("Save", page)
        save_button.clicked.connect(lambda: self._emit("save_project", {}))
        save_as_button = QtWidgets.QPushButton("Save As…", page)
        save_as_button.clicked.connect(self._choose_save_project)
        row.addWidget(new_button)
        row.addWidget(open_button)
        row.addWidget(save_button)
        row.addWidget(save_as_button)
        layout.addLayout(row)
        apply_button = QtWidgets.QPushButton(
            "Apply and verify installed game",
            page,
        )
        apply_button.setObjectName("HeadBuilderVerifyInstallButton")
        apply_button.clicked.connect(
            lambda: self._emit("configure_and_verify", self.project_payload())
        )
        layout.addWidget(apply_button)
        self.install_fingerprint = QtWidgets.QLabel("Not verified", page)
        self.install_fingerprint.setWordWrap(True)
        layout.addWidget(self.install_fingerprint)
        layout.addStretch(1)
        return page

    def _build_import_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepImportArt",
            "Import OBJ or FBX art into named KOTOR object space. Source bytes, "
            "axis policy, topology facts, and hashes are saved; mesh arrays "
            "remain in memory and are deterministically reimported.",
        )
        group, form = self._form_group("Custom head art", page)
        self.art_path = _PathField(
            folder=False,
            title="Choose custom head art",
            file_filter="3D head art (*.obj *.fbx);;All files (*)",
            parent=page,
        )
        self.source_axis = QtWidgets.QComboBox(page)
        self.source_axis.addItem("Detect from file type", "auto")
        self.source_axis.addItem("Already KOTOR Z-up", "kotor_z_up")
        self.source_axis.addItem(
            "Blender XYZ → KOTOR X,Z,-Y",
            "blender_xyz_to_kotor_xz_minus_y",
        )
        self.source_axis.addItem(
            "Tripo Y-up, Z-forward → KOTOR",
            "tripo_y_up_z_forward",
        )
        self.source_axis.addItem(
            "Maya Y-up, X-forward → KOTOR",
            "maya_y_up_x_forward",
        )
        self.unit_scale = QtWidgets.QDoubleSpinBox(page)
        self.unit_scale.setRange(0.000001, 1000000.0)
        self.unit_scale.setDecimals(6)
        self.unit_scale.setValue(1.0)
        self.flip_import_v = QtWidgets.QCheckBox(
            "Flip V once during import",
            page,
        )
        self.flip_import_v.setChecked(True)
        self.normal_policy = QtWidgets.QComboBox(page)
        self.normal_policy.addItem("Preserve authored normals", "preserve")
        self.normal_policy.addItem(
            "Recalculate only missing normals",
            "recalculate_missing",
        )
        self.weld_import = QtWidgets.QCheckBox(
            "Weld exact duplicate vertices",
            page,
        )
        self.triangulate_import = QtWidgets.QCheckBox(
            "Triangulate polygon faces",
            page,
        )
        self.triangulate_import.setChecked(True)
        form.addRow("OBJ or FBX", self.art_path)
        form.addRow("Source axes", self.source_axis)
        form.addRow("Unit scale to KOTOR", self.unit_scale)
        form.addRow("UV import", self.flip_import_v)
        form.addRow("Normals", self.normal_policy)
        form.addRow("Cleanup", self.weld_import)
        form.addRow("", self.triangulate_import)
        layout.addWidget(group)
        texture_group = QtWidgets.QGroupBox("Source textures", page)
        texture_layout = QtWidgets.QVBoxLayout(texture_group)
        self.source_texture_list = QtWidgets.QListWidget(page)
        texture_layout.addWidget(self.source_texture_list)
        texture_row = QtWidgets.QHBoxLayout()
        add_texture = QtWidgets.QPushButton("Add texture…", page)
        add_texture.clicked.connect(self._choose_source_textures)
        remove_texture = QtWidgets.QPushButton("Remove selected", page)
        remove_texture.clicked.connect(self._remove_source_textures)
        texture_row.addWidget(add_texture)
        texture_row.addWidget(remove_texture)
        texture_layout.addLayout(texture_row)
        layout.addWidget(texture_group)
        row = QtWidgets.QHBoxLayout()
        import_button = QtWidgets.QPushButton("Import custom head art", page)
        import_button.setObjectName("HeadBuilderImportArtButton")
        import_button.clicked.connect(
            lambda: self._emit("import_art", self.import_payload())
        )
        reimport_button = QtWidgets.QPushButton("Reimport source", page)
        reimport_button.clicked.connect(
            lambda: self._emit("import_art", self.import_payload())
        )
        row.addWidget(import_button)
        row.addWidget(reimport_button)
        layout.addLayout(row)
        self.import_summary = QtWidgets.QLabel("No custom art imported", page)
        self.import_summary.setWordWrap(True)
        layout.addWidget(self.import_summary)
        self.part_tree = QtWidgets.QTreeWidget(page)
        self.part_tree.setHeaderLabels(
            ["Part", "Material", "Vertices", "Faces", "Topology"]
        )
        self.part_tree.setRootIsDecorated(False)
        self.part_tree.setAlternatingRowColors(True)
        layout.addWidget(self.part_tree)
        return page

    def _build_donor_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepNativeDonor",
            "Choose a native modular head from the selected game. Stock-only "
            "mode never silently substitutes an Override resource.",
        )
        search_row = QtWidgets.QHBoxLayout()
        self.donor_search = QtWidgets.QLineEdit(page)
        self.donor_search.setPlaceholderText("Search ResRefs, for example PFHA")
        self.donor_advanced = QtWidgets.QCheckBox("Include nonstandard names", page)
        search_button = QtWidgets.QPushButton("Search installed heads", page)
        search_button.setObjectName("HeadBuilderDonorSearchButton")
        search_button.clicked.connect(
            lambda: self._emit(
                "search_donors",
                {
                    "text": self.donor_search.text().strip(),
                    "include_nonstandard": self.donor_advanced.isChecked(),
                },
            )
        )
        search_row.addWidget(self.donor_search, 1)
        search_row.addWidget(self.donor_advanced)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)
        self.donor_table = QtWidgets.QTableWidget(0, 4, page)
        self.donor_table.setObjectName("HeadBuilderDonorTable")
        self.donor_table.setHorizontalHeaderLabels(
            ["Head", "Source", "MDL + MDX", "Notes"]
        )
        self.donor_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.donor_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.donor_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.donor_table.horizontalHeader().setStretchLastSection(True)
        self.donor_table.doubleClicked.connect(
            lambda _index: self._select_current_donor()
        )
        layout.addWidget(self.donor_table)
        select_button = QtWidgets.QPushButton("Use selected native donor", page)
        select_button.setObjectName("HeadBuilderSelectDonorButton")
        select_button.clicked.connect(self._select_current_donor)
        layout.addWidget(select_button)
        component_group = QtWidgets.QGroupBox(
            "Build a vanilla component combination",
            page,
        )
        component_layout = QtWidgets.QVBoxLayout(component_group)
        component_copy = QtWidgets.QLabel(
            "The selected donor is the safe carrier. Search and highlight any "
            "compatible vanilla head above, then assign its face, eyes, "
            "eyelids/lashes, or hair. Blank slots use the carrier.",
            page,
        )
        component_copy.setWordWrap(True)
        component_layout.addWidget(component_copy)
        component_form = QtWidgets.QFormLayout()
        component_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        self.component_recipe_name = QtWidgets.QLineEdit(
            "Custom combination",
            page,
        )
        self.component_recipe_name.setObjectName(
            "HeadBuilderComponentRecipeName"
        )
        self.component_species = QtWidgets.QComboBox(page)
        self.component_species.setObjectName("HeadBuilderComponentSpecies")
        self.component_species.addItem(
            "Human or near-human modular head",
            "human_or_near_human",
        )
        self.component_species.addItem(
            "Humanoid alien modular head (for example Twi'lek)",
            "humanoid_alien",
        )
        component_form.addRow("Combination name", self.component_recipe_name)
        component_form.addRow("Head family", self.component_species)
        component_layout.addLayout(component_form)
        component_grid = QtWidgets.QGridLayout()
        component_grid.addWidget(QtWidgets.QLabel("Part", page), 0, 0)
        component_grid.addWidget(QtWidgets.QLabel("Source head ResRef", page), 0, 1)
        component_grid.addWidget(QtWidgets.QLabel("Assign", page), 0, 2)
        self.component_source_fields: dict[str, QtWidgets.QLineEdit] = {}
        for row, (role, label) in enumerate(
            (
                ("face", "Face + mouth"),
                ("eyes", "Eye meshes / color"),
                ("eyelashes", "Eyelids / lashes"),
                ("hair", "Hair / head-tail meshes"),
            ),
            start=1,
        ):
            field = QtWidgets.QLineEdit(page)
            field.setMaxLength(16)
            field.setPlaceholderText("Carrier")
            field.setObjectName(
                "HeadBuilderComponent"
                + "".join(part.title() for part in role.split("_"))
                + "Resref"
            )
            assign = QtWidgets.QPushButton("Use highlighted head", page)
            assign.clicked.connect(
                lambda _checked=False, selected_role=role: (
                    self._set_component_source_from_current(selected_role)
                )
            )
            self.component_source_fields[role] = field
            component_grid.addWidget(QtWidgets.QLabel(label, page), row, 0)
            component_grid.addWidget(field, row, 1)
            component_grid.addWidget(assign, row, 2)
        component_layout.addLayout(component_grid)
        build_components = QtWidgets.QPushButton(
            "Build vanilla combination",
            page,
        )
        build_components.setObjectName("HeadBuilderBuildComponentsButton")
        build_components.clicked.connect(
            lambda: self._emit(
                "build_component_recipe",
                self.component_recipe_payload(),
            )
        )
        component_layout.addWidget(build_components)
        self.component_summary = QtWidgets.QLabel(
            "Select a carrier donor, then choose its component sources.",
            page,
        )
        self.component_summary.setObjectName("HeadBuilderComponentSummary")
        self.component_summary.setWordWrap(True)
        component_layout.addWidget(self.component_summary)
        alien_note = QtWidgets.QLabel(
            "Twi'lek-style modular alien heads use this workflow within their "
            "own family. Full-body Rodian, Duros, Bith, Trandoshan, and similar "
            "models need the extraction/retarget workflow. Ithorians are "
            "intentionally unsupported for player bodies.",
            page,
        )
        alien_note.setWordWrap(True)
        component_layout.addWidget(alien_note)
        layout.addWidget(component_group)
        compare_group = QtWidgets.QGroupBox("Compare donor contracts", page)
        compare_layout = QtWidgets.QVBoxLayout(compare_group)
        self.donor_contract = QtWidgets.QPlainTextEdit(page)
        self.donor_contract.setReadOnly(True)
        self.donor_contract.setPlaceholderText(
            "Select a donor to see its root, attachment link, supermodel, "
            "node declaration, palette, bind rows, and retail envelope."
        )
        compare_layout.addWidget(self.donor_contract)
        compare_button = QtWidgets.QPushButton(
            "Compare current candidate with donor",
            page,
        )
        compare_button.clicked.connect(
            lambda: self._emit("compare_donor", {})
        )
        compare_layout.addWidget(compare_button)
        layout.addWidget(compare_group)
        return page

    def _build_alignment_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepAlignment",
            "Pick matching points in custom-art object space and body-bind "
            "space. Ghost Studio solves into the body's exact headhook-local "
            "space; it never blindly bakes the hook translation into vertices.",
        )
        context, form = self._form_group("Body attachment context", page)
        self.alignment_body_resref = QtWidgets.QLineEdit(page)
        self.alignment_body_resref.setMaxLength(16)
        self.headhook_path = QtWidgets.QLineEdit(page)
        self.headhook_path.setReadOnly(True)
        self.headhook_path.setPlaceholderText(
            "Load the body to resolve its unique headhook"
        )
        load_body = QtWidgets.QPushButton("Load body and show headhook", page)
        load_body.clicked.connect(
            lambda: self._emit(
                "load_alignment_body",
                {"body_resref": self.alignment_body_resref.text().strip()},
            )
        )
        form.addRow("Preview body ResRef", self.alignment_body_resref)
        form.addRow("Resolved headhook path", self.headhook_path)
        form.addRow("", load_body)
        layout.addWidget(context)
        anchors = QtWidgets.QGroupBox("Neck seam anchors", page)
        anchor_layout = QtWidgets.QVBoxLayout(anchors)
        for role, label, optional in (
            ("neck_center", "Centre seam anchor", False),
            ("neck_left", "Left orientation anchor", True),
            ("neck_front", "Front orientation anchor", True),
        ):
            row = _AnchorRow(role, label, optional=optional, parent=page)
            row.captureRequested.connect(self.captureRequested.emit)
            self._anchor_rows[role] = row
            anchor_layout.addWidget(row)
        layout.addWidget(anchors)
        solve, form = self._form_group("Alignment solve", page)
        self.scale_mode = QtWidgets.QComboBox(page)
        self.scale_mode.addItem("Keep imported scale", "fixed")
        self.scale_mode.addItem("Solve one uniform scale", "similarity")
        self.maximum_rms = QtWidgets.QDoubleSpinBox(page)
        self.maximum_rms.setRange(0.0, 1000.0)
        self.maximum_rms.setDecimals(6)
        self.maximum_rms.setValue(0.01)
        form.addRow("Scale", self.scale_mode)
        form.addRow("Maximum seam error", self.maximum_rms)
        layout.addWidget(solve)
        row = QtWidgets.QHBoxLayout()
        preview_custom = QtWidgets.QPushButton("Show custom head", page)
        preview_custom.clicked.connect(
            lambda: self._emit("show_custom_art", {})
        )
        reset = QtWidgets.QPushButton("Reset anchors", page)
        reset.clicked.connect(self.reset_anchors)
        solve_button = QtWidgets.QPushButton("Solve headhook alignment", page)
        solve_button.setObjectName("HeadBuilderSolveAlignmentButton")
        solve_button.clicked.connect(
            lambda: self._emit("solve_alignment", self.alignment_payload())
        )
        row.addWidget(preview_custom)
        row.addWidget(reset)
        row.addWidget(solve_button)
        layout.addLayout(row)
        self.alignment_summary = QtWidgets.QLabel("Alignment not solved", page)
        self.alignment_summary.setWordWrap(True)
        layout.addWidget(self.alignment_summary)
        return page

    def _build_skin_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepSkin",
            "The safe path keeps the donor DAG, palette, qBone/tBone rows, "
            "sparse identities, hooks, bounds, and supermodel. Only the native "
            "rendered head skin payload is replaced.",
        )
        self.skin_part_table = QtWidgets.QTableWidget(0, 4, page)
        self.skin_part_table.setHorizontalHeaderLabels(
            ["Imported part", "Skin method", "Vertices", "Faces"]
        )
        self.skin_part_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.skin_part_table)
        settings, form = self._form_group("Donor surface transfer", page)
        self.skin_settings_group = settings
        self.maximum_surface_distance = QtWidgets.QDoubleSpinBox(page)
        self.maximum_surface_distance.setRange(0.000001, 1000000.0)
        self.maximum_surface_distance.setDecimals(6)
        self.maximum_surface_distance.setValue(100.0)
        self.allow_distance_fallback = QtWidgets.QCheckBox(
            "Rigid-bind vertices beyond the distance limit",
            page,
        )
        self.allow_distance_fallback.setChecked(True)
        self.rigid_bone = QtWidgets.QLineEdit("head_g", page)
        self.minimum_neck_weight = QtWidgets.QDoubleSpinBox(page)
        self.minimum_neck_weight.setRange(0.0, 1.0)
        self.minimum_neck_weight.setDecimals(4)
        self.minimum_neck_weight.setValue(0.05)
        self.neck_vertex_ids = QtWidgets.QPlainTextEdit(page)
        self.neck_vertex_ids.setPlaceholderText(
            "One stable boundary vertex ID per line"
        )
        capture_neck = QtWidgets.QPushButton(
            "Use selected boundary vertices",
            page,
        )
        capture_neck.clicked.connect(
            lambda: self.captureRequested.emit("neck_vertices", "source")
        )
        form.addRow("Maximum transfer distance", self.maximum_surface_distance)
        form.addRow("Distance fallback", self.allow_distance_fallback)
        form.addRow("Rigid fallback bone", self.rigid_bone)
        form.addRow("Minimum neck-link weight", self.minimum_neck_weight)
        form.addRow("Neck boundary vertices", self.neck_vertex_ids)
        form.addRow("", capture_neck)
        layout.addWidget(settings)
        transplant = QtWidgets.QPushButton(
            "Replace donor geometry and transfer skin",
            page,
        )
        self.transplant_button = transplant
        transplant.setObjectName("HeadBuilderTransplantButton")
        transplant.clicked.connect(
            lambda: self._emit("transplant", self.transplant_payload())
        )
        layout.addWidget(transplant)
        self.skin_summary = QtWidgets.QLabel("No transplanted payload", page)
        self.skin_summary.setWordWrap(True)
        layout.addWidget(self.skin_summary)
        edit_group, edit_form = self._form_group(
            "Selected vertex weight fix",
            page,
        )
        self.weight_edit_group = edit_group
        self.weight_vertex_id = QtWidgets.QLineEdit(page)
        self.weight_vertex_id.setPlaceholderText(
            "Pick a transplanted vertex or enter its stable ID"
        )
        pick_weight = QtWidgets.QPushButton("Use selected vertex", page)
        pick_weight.clicked.connect(
            lambda: self.captureRequested.emit("weight_vertex", "candidate")
        )
        vertex_row = QtWidgets.QWidget(page)
        vertex_layout = QtWidgets.QHBoxLayout(vertex_row)
        vertex_layout.setContentsMargins(0, 0, 0, 0)
        vertex_layout.addWidget(self.weight_vertex_id, 1)
        vertex_layout.addWidget(pick_weight)
        edit_form.addRow("Vertex", vertex_row)
        self.weight_rows: list[
            tuple[QtWidgets.QComboBox, QtWidgets.QDoubleSpinBox]
        ] = []
        for index in range(4):
            row_widget = QtWidgets.QWidget(page)
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            bone = QtWidgets.QComboBox(page)
            bone.setEditable(True)
            weight = QtWidgets.QDoubleSpinBox(page)
            weight.setRange(0.0, 1.0)
            weight.setDecimals(6)
            row_layout.addWidget(bone, 1)
            row_layout.addWidget(weight)
            self.weight_rows.append((bone, weight))
            edit_form.addRow(f"Influence {index + 1}", row_widget)
        edit_buttons = QtWidgets.QHBoxLayout()
        apply_edit = QtWidgets.QPushButton("Apply normalized weights", page)
        apply_edit.clicked.connect(
            lambda: self._emit("edit_weights", self.weight_edit_payload())
        )
        reset_edit = QtWidgets.QPushButton("Reset selected vertex", page)
        reset_edit.clicked.connect(
            lambda: self._emit(
                "reset_weight",
                {"vertex_id": self.weight_vertex_id.text().strip()},
            )
        )
        reset_all = QtWidgets.QPushButton("Restore transferred baseline", page)
        reset_all.clicked.connect(
            lambda: self._emit("reset_all_weights", {})
        )
        edit_buttons.addWidget(apply_edit)
        edit_buttons.addWidget(reset_edit)
        edit_buttons.addWidget(reset_all)
        edit_form.addRow("", edit_buttons)
        layout.addWidget(edit_group)
        return page

    def _build_texture_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepTextures",
            "Preview and serialized UV orientation are explicit independent "
            "choices. The accepted configuration requires them to agree; no "
            "renderer-wide hidden flip is used as an export repair.",
        )
        group, form = self._form_group("Texture and UV contract", page)
        self.texture_path = _PathField(
            folder=False,
            title="Choose a KOTOR head texture",
            file_filter=(
                "Head texture sources (*.png *.tga *.tpc);;All files (*)"
            ),
            parent=page,
        )
        self.txi_path = _PathField(
            folder=False,
            title="Choose optional TXI metadata",
            file_filter="Texture metadata (*.txi);;All files (*)",
            parent=page,
        )
        self.texture_resref = QtWidgets.QLineEdit(page)
        self.texture_resref.setMaxLength(16)
        self.texture_format = QtWidgets.QComboBox(page)
        self.texture_format.addItem("TGA + TXI sidecar", "TGA")
        self.texture_format.addItem("TPC with embedded TXI", "TPC")
        self.serialized_uv = QtWidgets.QComboBox(page)
        self.serialized_uv.addItem("Keep imported UVs", "identity")
        self.serialized_uv.addItem("Flip V once", "flip_v")
        self.preview_uv = QtWidgets.QComboBox(page)
        self.preview_uv.addItem("Match imported UVs", "identity")
        self.preview_uv.addItem("Flip V once", "flip_v")
        self.alpha_mode = QtWidgets.QComboBox(page)
        self.alpha_mode.addItem("Opaque", "opaque")
        self.alpha_mode.addItem("Alpha blend", "blend")
        self.alpha_mode.addItem("Cutout / punchthrough", "punchthrough")
        self.environment_map = QtWidgets.QLineEdit(page)
        self.environment_map.setMaxLength(16)
        self.bump_map = QtWidgets.QLineEdit(page)
        self.bump_map.setMaxLength(16)
        self.clamp_s = QtWidgets.QCheckBox("Clamp horizontally", page)
        self.clamp_t = QtWidgets.QCheckBox("Clamp vertically", page)
        self.mipmap = QtWidgets.QCheckBox("Build/use mipmaps", page)
        self.mipmap.setChecked(True)
        self.preserve_txi = QtWidgets.QCheckBox(
            "Preserve unknown source TXI lines",
            page,
        )
        self.preserve_txi.setChecked(True)
        form.addRow("Texture", self.texture_path)
        form.addRow("Optional TXI", self.txi_path)
        form.addRow("Output texture ResRef", self.texture_resref)
        form.addRow("Package format", self.texture_format)
        form.addRow("Serialized MDX UVs", self.serialized_uv)
        form.addRow("Editor preview UVs", self.preview_uv)
        form.addRow("Alpha", self.alpha_mode)
        form.addRow("Environment map", self.environment_map)
        form.addRow("Bump map", self.bump_map)
        form.addRow("Sampler", self.clamp_s)
        form.addRow("", self.clamp_t)
        form.addRow("", self.mipmap)
        form.addRow("TXI policy", self.preserve_txi)
        layout.addWidget(group)
        views = QtWidgets.QGroupBox("Viewport view", page)
        view_row = QtWidgets.QHBoxLayout(views)
        self.view_mode_group = QtWidgets.QButtonGroup(self)
        self.view_mode_group.setExclusive(True)
        for label, mode in (
            ("Textured", "textured"),
            ("Unlit", "unlit"),
            ("Lit", "lit"),
            ("UV checker", "uv_checker"),
            ("Wireframe", "wireframe"),
        ):
            button = QtWidgets.QPushButton(label, page)
            button.setCheckable(True)
            if mode == "textured":
                button.setChecked(True)
            self.view_mode_group.addButton(button)
            button.clicked.connect(
                lambda _checked=False, key=mode: self._emit(
                    "viewport_display",
                    {"mode": key},
                )
            )
            view_row.addWidget(button)
        layout.addWidget(views)
        apply_button = QtWidgets.QPushButton(
            "Apply UV, texture, and material contract",
            page,
        )
        apply_button.setObjectName("HeadBuilderTextureButton")
        apply_button.clicked.connect(
            lambda: self._emit("configure_texture", self.texture_payload())
        )
        layout.addWidget(apply_button)
        self.texture_summary = QtWidgets.QLabel(
            "No verified texture contract",
            page,
        )
        self.texture_summary.setWordWrap(True)
        layout.addWidget(self.texture_summary)
        return page

    def _build_preview_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepPreview",
            "The preview composites the modular head under the selected body's "
            "real headhook and resolves inherited animations through the donor "
            "supermodel chain without copying body clips into the head.",
        )
        group, form = self._form_group("Attachment preview", page)
        self.preview_body_resref = QtWidgets.QLineEdit(page)
        self.preview_body_resref.setMaxLength(16)
        self.preview_animations = QtWidgets.QLineEdit(
            "tlknorm, talk, listen, walk, run, combat",
            page,
        )
        self.preview_animations.setToolTip(
            "Comma-separated inherited animation names to prove and expose."
        )
        form.addRow("Headless body", self.preview_body_resref)
        form.addRow("Animation set", self.preview_animations)
        layout.addWidget(group)
        build = QtWidgets.QPushButton(
            "Build exact-headhook preview",
            page,
        )
        build.setObjectName("HeadBuilderPreviewButton")
        build.clicked.connect(
            lambda: self._emit("build_preview", self.preview_payload())
        )
        layout.addWidget(build)
        preset_group = QtWidgets.QGroupBox("Playback presets", page)
        preset_layout = QtWidgets.QGridLayout(preset_group)
        for index, (label, animation) in enumerate(
            (
                ("Neutral", "tlknorm"),
                ("Talk", "talk"),
                ("Listen", "listen"),
                ("Blink", "blink"),
                ("Emotion", "talkangry"),
                ("Head track", "tlkplead"),
                ("Walk", "walk"),
                ("Run", "run"),
                ("Combat", "creadyr"),
            )
        ):
            button = QtWidgets.QPushButton(label, page)
            button.clicked.connect(
                lambda _checked=False, name=animation:
                self.previewAnimationRequested.emit(name)
            )
            preset_layout.addWidget(button, index // 3, index % 3)
        stop = QtWidgets.QPushButton("Stop", page)
        stop.clicked.connect(
            lambda: self.previewAnimationRequested.emit("")
        )
        preset_layout.addWidget(stop, 3, 0, 1, 3)
        layout.addWidget(preset_group)

        dialogue_group = QtWidgets.QGroupBox(
            "Synchronized dialogue facial preview",
            page,
        )
        dialogue_layout = QtWidgets.QFormLayout(dialogue_group)
        self.dialogue_audio_path = _PathField(
            folder=False,
            title="Choose dialogue audio",
            file_filter=(
                "Dialogue audio (*.wav *.mp3 *.ogg *.flac);;All files (*)"
            ),
            parent=dialogue_group,
        )
        self.dialogue_lip_path = _PathField(
            folder=False,
            title="Choose matching KOTOR LIP",
            file_filter="KOTOR lip animation (*.lip);;All files (*)",
            parent=dialogue_group,
        )
        dialogue_layout.addRow("Dialogue audio", self.dialogue_audio_path)
        dialogue_layout.addRow("Matching LIP", self.dialogue_lip_path)
        dialogue_buttons = QtWidgets.QHBoxLayout()
        self.dialogue_preview_button = QtWidgets.QPushButton(
            "Play audio + face",
            dialogue_group,
        )
        self.dialogue_preview_button.setObjectName(
            "HeadBuilderDialoguePreviewButton"
        )
        self.dialogue_preview_button.clicked.connect(
            lambda: self.dialoguePreviewRequested.emit(
                self.dialogue_audio_path.text(),
                self.dialogue_lip_path.text(),
            )
        )
        self.dialogue_stop_button = QtWidgets.QPushButton(
            "Stop",
            dialogue_group,
        )
        self.dialogue_stop_button.setObjectName(
            "HeadBuilderDialogueStopButton"
        )
        self.dialogue_stop_button.setEnabled(False)
        self.dialogue_stop_button.clicked.connect(
            self.dialoguePreviewStopRequested.emit
        )
        dialogue_buttons.addWidget(self.dialogue_preview_button)
        dialogue_buttons.addWidget(self.dialogue_stop_button)
        dialogue_layout.addRow("", dialogue_buttons)
        self.dialogue_preview_status = QtWidgets.QLabel(
            "Choose matching dialogue audio and LIP data.",
            dialogue_group,
        )
        self.dialogue_preview_status.setWordWrap(True)
        dialogue_layout.addRow(self.dialogue_preview_status)
        layout.addWidget(dialogue_group)

        self.preview_summary = QtWidgets.QPlainTextEdit(page)
        self.preview_summary.setReadOnly(True)
        self.preview_summary.setPlaceholderText(
            "Geometry root, attachment link, supermodel, local clips, inherited "
            "node declaration, headhook transform, and animation inventory "
            "appear here."
        )
        layout.addWidget(self.preview_summary)
        return page

    def set_dialogue_preview_status(
        self,
        message: str,
        *,
        playing: bool,
    ) -> None:
        """Present synchronized audio/facial playback state."""

        self.dialogue_preview_status.setText(str(message or ""))
        self.dialogue_preview_button.setEnabled(not playing)
        self.dialogue_stop_button.setEnabled(bool(playing))

    def _build_physics_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepPhysics",
            "Optional hair/accessory physics is excluded from this release. "
            "The safe rigid baseline remains the authoritative candidate, and "
            "the project records that physics was not requested.",
        )
        notice = QtWidgets.QGroupBox("Rigid baseline retained", page)
        notice_layout = QtWidgets.QVBoxLayout(notice)
        text = QtWidgets.QLabel(
            "Hair, horns, scalp, accessories, and distant geometry stay "
            "rigid-bound to the selected fallback bone unless a future "
            "opt-in physics workflow is explicitly run.",
            page,
        )
        text.setWordWrap(True)
        notice_layout.addWidget(text)
        return_button = QtWidgets.QPushButton(
            "Return to rigid baseline",
            page,
        )
        return_button.clicked.connect(
            lambda: self._emit("return_rigid_baseline", {})
        )
        notice_layout.addWidget(return_button)
        layout.addWidget(notice)
        layout.addStretch(1)
        return page

    def _build_preflight_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepPreflight",
            "Preflight builds an in-memory MDL/MDX candidate, reloads it, and "
            "checks donor structure, offsets, palettes, weights, UVs, bounds, "
            "root/link identity, and K1/K2 pointer family before publishing.",
        )
        self.preflight_tree = QtWidgets.QTreeWidget(page)
        self.preflight_tree.setObjectName("HeadBuilderPreflightTree")
        self.preflight_tree.setHeaderLabels(
            ["Severity", "Check", "Result", "How to fix"]
        )
        self.preflight_tree.setAlternatingRowColors(True)
        self.preflight_tree.header().setStretchLastSection(True)
        layout.addWidget(self.preflight_tree)
        row = QtWidgets.QHBoxLayout()
        run = QtWidgets.QPushButton("Run binary preflight", page)
        run.setObjectName("HeadBuilderPreflightButton")
        run.clicked.connect(lambda: self._emit("run_preflight", {}))
        acknowledge = QtWidgets.QPushButton(
            "Acknowledge displayed warnings",
            page,
        )
        acknowledge.clicked.connect(
            lambda: self._emit(
                "acknowledge_warnings",
                {"warning_ids": self.warning_ids()},
            )
        )
        export = QtWidgets.QPushButton("Export verified MDL + MDX", page)
        export.setObjectName("HeadBuilderBinaryExportButton")
        export.clicked.connect(lambda: self._emit("export_binary", {}))
        row.addWidget(run)
        row.addWidget(acknowledge)
        row.addWidget(export)
        layout.addLayout(row)
        self.preflight_summary = QtWidgets.QLabel(
            "Preflight not run",
            page,
        )
        self.preflight_summary.setWordWrap(True)
        layout.addWidget(self.preflight_summary)
        return page

    def _build_package_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepPackage",
            "Game rows are re-found by stable values and appended or cloned "
            "without fixed row numbers. Unrelated mod rows are never silently "
            "overwritten.",
        )
        group, form = self._form_group("Game record merge", page)
        self.appearance_donor_label = QtWidgets.QLineEdit(page)
        self.appearance_donor_label.setPlaceholderText(
            "Installed appearance.2da label to clone"
        )
        self.appearance_label = QtWidgets.QLineEdit(page)
        self.appearance_label.setPlaceholderText(
            "Optional stable label; Ghost Studio can generate one"
        )
        self.portrait_resref = QtWidgets.QLineEdit(page)
        self.portrait_resref.setMaxLength(16)
        self.portrait_donor_resref = QtWidgets.QLineEdit(page)
        self.portrait_donor_resref.setMaxLength(16)
        self.package_dir = _PathField(
            folder=True,
            title="Choose the package output folder",
            parent=page,
        )
        self.utc_template = _PathField(
            folder=False,
            title="Choose an optional UTC test actor",
            file_filter="KOTOR creature blueprints (*.utc);;All files (*)",
            parent=page,
        )
        form.addRow("Appearance donor label", self.appearance_donor_label)
        form.addRow("New appearance label", self.appearance_label)
        form.addRow("Optional portrait ResRef", self.portrait_resref)
        form.addRow("Portrait donor ResRef", self.portrait_donor_resref)
        form.addRow("Package folder", self.package_dir)
        form.addRow("Optional UTC test actor", self.utc_template)
        layout.addWidget(group)
        build = QtWidgets.QPushButton(
            "Build game records and reversible package",
            page,
        )
        build.setObjectName("HeadBuilderPackageButton")
        build.clicked.connect(
            lambda: self._emit("build_package", self.package_payload())
        )
        layout.addWidget(build)
        self.package_summary = QtWidgets.QPlainTextEdit(page)
        self.package_summary.setReadOnly(True)
        self.package_summary.setPlaceholderText(
            "The heads.2da/appearance.2da before-and-after plan, package files, "
            "TSLPatcher alternative, and hashes appear here."
        )
        layout.addWidget(self.package_summary)
        return page

    def _build_retail_page(self) -> QtWidgets.QWidget:
        page, layout = self._page(
            "HeadBuilderStepRetail",
            "Prepare is read-only and shows exact destinations. Install requires "
            "confirmation of that exact preview, refuses a running game or "
            "launcher, backs up changed files, and never edits the EXE.",
        )
        row = QtWidgets.QHBoxLayout()
        prepare = QtWidgets.QPushButton("Prepare Test Install", page)
        prepare.setObjectName("HeadBuilderPrepareInstallButton")
        prepare.clicked.connect(lambda: self._emit("prepare_install", {}))
        install = QtWidgets.QPushButton("Install exact preview", page)
        install.setObjectName("HeadBuilderInstallButton")
        install.clicked.connect(
            lambda: self._emit(
                "install_prepared",
                {
                    "preview_id": self._install_preview_id,
                    "confirmed": self.confirm_install.isChecked(),
                },
            )
        )
        restore = QtWidgets.QPushButton("Restore Previous Test", page)
        restore.setObjectName("HeadBuilderRestoreButton")
        restore.clicked.connect(lambda: self._emit("restore_install", {}))
        row.addWidget(prepare)
        row.addWidget(install)
        row.addWidget(restore)
        layout.addLayout(row)
        self.install_tree = QtWidgets.QTreeWidget(page)
        self.install_tree.setHeaderLabels(
            ["Destination", "Action", "Current hash", "Candidate hash"]
        )
        self.install_tree.setAlternatingRowColors(True)
        self.install_tree.header().setStretchLastSection(True)
        layout.addWidget(self.install_tree)
        self.confirm_install = QtWidgets.QCheckBox(
            "I reviewed every destination above and confirm this exact preview",
            page,
        )
        layout.addWidget(self.confirm_install)
        checklist = QtWidgets.QGroupBox("Retail KOTOR checklist", page)
        checklist_layout = QtWidgets.QVBoxLayout(checklist)
        for key, label in RETAIL_CHECKS:
            checkbox = QtWidgets.QCheckBox(label, page)
            self._retail_checks[key] = checkbox
            checklist_layout.addWidget(checkbox)
        layout.addWidget(checklist)
        evidence, form = self._form_group("Observed evidence", page)
        self.observer_session = QtWidgets.QLineEdit(page)
        self.observer_session.setPlaceholderText(
            "Observer session identifier"
        )
        self.retail_evidence_list = QtWidgets.QListWidget(page)
        add_evidence = QtWidgets.QPushButton(
            "Add screenshot or video…",
            page,
        )
        add_evidence.clicked.connect(self._choose_retail_evidence)
        self.user_confirmed = QtWidgets.QCheckBox(
            "I personally observed every checked item pass in retail KOTOR",
            page,
        )
        form.addRow("Observer session", self.observer_session)
        form.addRow("Saved artifacts", self.retail_evidence_list)
        form.addRow("", add_evidence)
        form.addRow("User confirmation", self.user_confirmed)
        layout.addWidget(evidence)
        record = QtWidgets.QPushButton(
            "Record Retail observed: pass",
            page,
        )
        record.setObjectName("HeadBuilderRecordRetailPassButton")
        record.clicked.connect(
            lambda: self._emit("record_retail_pass", self.retail_payload())
        )
        layout.addWidget(record)
        self.retail_summary = QtWidgets.QLabel(
            "Retail observed: not tested",
            page,
        )
        self.retail_summary.setWordWrap(True)
        layout.addWidget(self.retail_summary)
        return page

    def _emit(self, action: str, payload: object) -> None:
        if not self._loading and not self._busy:
            self.actionRequested.emit(str(action), payload)

    def _choose_open_project(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Head Project",
            "",
            "Ghost Studio Head Project (*.ghosthead.json);;JSON files (*.json)",
        )
        if path:
            self._emit("open_project", {"path": path})

    def _choose_save_project(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Head Project",
            "",
            "Ghost Studio Head Project (*.ghosthead.json)",
        )
        if path:
            if not path.lower().endswith(".ghosthead.json"):
                path += ".ghosthead.json"
            self._emit("save_project", {"path": path})

    def _choose_source_textures(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Add source textures",
            "",
            "Head texture sources (*.png *.tga *.tpc *.txi);;All files (*)",
        )
        for path in paths:
            if path not in self._source_texture_paths:
                self._source_texture_paths.append(path)
        self._sync_source_texture_list()

    def _remove_source_textures(self) -> None:
        selected = {
            item.text() for item in self.source_texture_list.selectedItems()
        }
        self._source_texture_paths = [
            path for path in self._source_texture_paths if path not in selected
        ]
        self._sync_source_texture_list()

    def _sync_source_texture_list(self) -> None:
        self.source_texture_list.clear()
        self.source_texture_list.addItems(self._source_texture_paths)

    def _choose_retail_evidence(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Attach retail observer evidence",
            "",
            "Images and video (*.png *.jpg *.jpeg *.webp *.mp4 *.webm *.mkv);;"
            "All files (*)",
        )
        for path in paths:
            if path not in self._evidence_paths:
                self._evidence_paths.append(path)
        self.retail_evidence_list.clear()
        self.retail_evidence_list.addItems(self._evidence_paths)

    def _select_current_donor(self) -> None:
        resref = self._current_donor_resref()
        if resref:
            self._emit("select_donor", {"resref": resref})

    def _current_donor_resref(self) -> str:
        row = self.donor_table.currentRow()
        if row < 0:
            return ""
        item = self.donor_table.item(row, 0)
        return (
            str(item.data(QtCore.Qt.UserRole) or item.text())
            if item is not None
            else ""
        )

    def _set_component_source_from_current(self, role: str) -> None:
        resref = self._current_donor_resref()
        field = self.component_source_fields.get(str(role))
        if resref and field is not None:
            field.setText(resref)

    def set_step(self, step: int) -> bool:
        number = int(step)
        if not 1 <= number <= len(HEAD_BUILDER_STEPS):
            return False
        self.stack.setCurrentIndex(number - 1)
        self.title.setText(f"{number}. {HEAD_BUILDER_STEPS[number - 1][1]}")
        return True

    def project_payload(self) -> dict[str, Any]:
        return {
            "display_name": self.project_name.text().strip() or "Untitled Head",
            "game": str(self.game.currentData() or "K2"),
            "resource_view": str(
                self.resource_view.currentData() or "stock_only"
            ),
            "game_install_dir": self.game_dir.text(),
            "output_project_dir": self.output_dir.text(),
            "output_head_resref": self.output_resref.text().strip(),
            "character_context": {
                "gender": str(self.context_gender.currentData() or "custom"),
                "role": str(self.context_role.currentData() or "player"),
                "body_resref": self.body_resref.text().strip(),
            },
        }

    def import_payload(self) -> dict[str, Any]:
        return {
            "path": self.art_path.text(),
            "source_axis": str(self.source_axis.currentData() or "auto"),
            "unit_scale_to_kotor": self.unit_scale.value(),
            "flip_v": self.flip_import_v.isChecked(),
            "source_texture_paths": tuple(self._source_texture_paths),
            "cleanup_policy": {
                "normal_policy": str(
                    self.normal_policy.currentData() or "preserve"
                ),
                "weld_exact_duplicates": self.weld_import.isChecked(),
                "triangulate": self.triangulate_import.isChecked(),
                "repair_nonmanifold_overlays": (
                    self._facial_performance_mode
                ),
            },
        }

    def component_recipe_payload(self) -> dict[str, Any]:
        return {
            "recipe_name": (
                self.component_recipe_name.text().strip()
                or "Custom combination"
            ),
            "species_mode": str(
                self.component_species.currentData()
                or "human_or_near_human"
            ),
            "face_resref": self.component_source_fields["face"].text().strip(),
            "eyes_resref": self.component_source_fields["eyes"].text().strip(),
            "eyelashes_resref": (
                self.component_source_fields["eyelashes"].text().strip()
            ),
            "hair_resref": self.component_source_fields["hair"].text().strip(),
        }

    def alignment_payload(self) -> dict[str, Any]:
        return {
            "body_resref": self.alignment_body_resref.text().strip(),
            "headhook_node_path": self.headhook_path.text().strip(),
            "anchors": [
                payload
                for row in self._anchor_rows.values()
                if (payload := row.payload()) is not None
            ],
            "scale_mode": str(self.scale_mode.currentData() or "fixed"),
            "maximum_rms_error": self.maximum_rms.value(),
        }

    def transplant_payload(self) -> dict[str, Any]:
        part_modes: dict[str, str] = {}
        for row in range(self.skin_part_table.rowCount()):
            item = self.skin_part_table.item(row, 0)
            combo = self.skin_part_table.cellWidget(row, 1)
            if item is not None and isinstance(combo, QtWidgets.QComboBox):
                part_modes[str(item.data(QtCore.Qt.UserRole) or "")] = str(
                    combo.currentData() or "surface_transfer"
                )
        return {
            "facial_performance_mode": self._facial_performance_mode,
            "part_modes": part_modes,
            "neck_vertex_ids": [
                line.strip()
                for line in self.neck_vertex_ids.toPlainText().splitlines()
                if line.strip()
            ],
            "maximum_surface_distance": self.maximum_surface_distance.value(),
            "allow_distance_fallback": (
                self.allow_distance_fallback.isChecked()
            ),
            "rigid_fallback_bone": self.rigid_bone.text().strip() or "head_g",
            "minimum_neck_weight": self.minimum_neck_weight.value(),
        }

    def weight_edit_payload(self) -> dict[str, Any]:
        weights: dict[str, float] = {}
        for bone, weight in self.weight_rows:
            name = bone.currentText().strip()
            if name and weight.value() > 0.0:
                weights[name] = weight.value()
        return {
            "vertex_id": self.weight_vertex_id.text().strip(),
            "weights_by_bone": weights,
        }

    def texture_payload(self) -> dict[str, Any]:
        output_format = str(self.texture_format.currentData() or "TGA")
        return {
            "texture_path": self.texture_path.text(),
            "txi_path": self.txi_path.text() or None,
            "output_texture_resref": self.texture_resref.text().strip(),
            "output_format": output_format,
            "txi_delivery": "embedded" if output_format == "TPC" else "sidecar",
            "serialized_uv_transform": str(
                self.serialized_uv.currentData() or "identity"
            ),
            "preview_uv_transform": str(
                self.preview_uv.currentData() or "identity"
            ),
            "alpha_mode": str(self.alpha_mode.currentData() or "opaque"),
            "environment_map_resref": self.environment_map.text().strip(),
            "bumpmap_resref": self.bump_map.text().strip(),
            "clamp_s": self.clamp_s.isChecked(),
            "clamp_t": self.clamp_t.isChecked(),
            "mipmap": self.mipmap.isChecked(),
            "preserve_source_txi": self.preserve_txi.isChecked(),
        }

    def preview_payload(self) -> dict[str, Any]:
        return {
            "body_resref": self.preview_body_resref.text().strip(),
            "selected_animation_names": tuple(
                value.strip()
                for value in self.preview_animations.text().split(",")
                if value.strip()
            ),
        }

    def package_payload(self) -> dict[str, Any]:
        return {
            "appearance_donor_label": (
                self.appearance_donor_label.text().strip()
            ),
            "appearance_label": self.appearance_label.text().strip(),
            "portrait_resref": self.portrait_resref.text().strip(),
            "portrait_donor_resref": (
                self.portrait_donor_resref.text().strip()
            ),
            "package_directory": self.package_dir.text() or None,
            "utc_template_path": self.utc_template.text() or None,
        }

    def retail_payload(self) -> dict[str, Any]:
        return {
            "observer_session": self.observer_session.text().strip(),
            "checklist": {
                key: checkbox.isChecked()
                for key, checkbox in self._retail_checks.items()
            },
            "artifact_paths": tuple(self._evidence_paths),
            "confirmed_by_user": self.user_confirmed.isChecked(),
        }

    def warning_ids(self) -> tuple[str, ...]:
        rows: list[str] = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self.preflight_tree)
        while iterator.value():
            item = iterator.value()
            if item.text(0).casefold() == "warning":
                check_id = str(item.data(0, QtCore.Qt.UserRole) or "")
                if check_id:
                    rows.append(check_id)
            iterator += 1
        return tuple(dict.fromkeys(rows))

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = bool(busy)
        self.status.setText(message or ("Working…" if busy else "Ready"))
        self.stack.setEnabled(not busy)

    def set_message(self, message: str, *, error: bool = False) -> None:
        self.status.setText(str(message or ("Action failed" if error else "Ready")))
        self.status.setProperty("headBuilderError", bool(error))
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_project(
        self,
        project: Any,
        *,
        document_path: str = "",
        dirty: bool = False,
    ) -> None:
        self._loading = True
        try:
            self.project_name.setText(_plain_text(project.display_name))
            _set_combo_data(self.game, getattr(project.game, "value", project.game))
            _set_combo_data(
                self.resource_view,
                getattr(project.resource_view, "value", project.resource_view),
            )
            self.game_dir.setText(project.game_install_dir)
            self.output_dir.setText(project.output_project_dir)
            self.output_resref.setText(project.output_head_resref)
            context = dict(project.character_context or {})
            _set_combo_data(self.context_gender, context.get("gender", "custom"))
            _set_combo_data(self.context_role, context.get("role", "player"))
            body = str(
                context.get("body_resref")
                or dict(project.attachment_preview or {}).get("body_resref")
                or dict(
                    dict(project.alignment or {}).get("body_context") or {}
                ).get("body_resref")
                or ""
            )
            self.body_resref.setText(body)
            self.alignment_body_resref.setText(body)
            self.preview_body_resref.setText(body)
            appearance = dict(project.appearance_customization or {})
            if appearance.get("mode") == "vanilla_components":
                self.component_recipe_name.setText(
                    str(appearance.get("recipe_name") or "Custom combination")
                )
                _set_combo_data(
                    self.component_species,
                    appearance.get(
                        "species_mode",
                        "human_or_near_human",
                    ),
                )
                selections = dict(appearance.get("selections") or {})
                for role, field in self.component_source_fields.items():
                    field.setText(str(selections.get(role) or ""))
                self.component_summary.setText(
                    "Saved vanilla combination — "
                    + ", ".join(
                        f"{role}: {str(selections.get(role) or 'carrier')}"
                        for role in ("face", "eyes", "eyelashes", "hair")
                    )
                )
            verification = dict(
                project.extensions.get("game_install_verification") or {}
            )
            if verification:
                fingerprint = str(
                    verification.get("fingerprint_sha256") or ""
                )
                self.install_fingerprint.setText(
                    (
                        "Verified read-only — "
                        if verification.get("verified")
                        else "Verification failed — "
                    )
                    + (fingerprint[:16] or "no fingerprint")
                )
            else:
                self.install_fingerprint.setText("Not verified")
            self.set_step(int(project.current_step))
            self.status.setText(
                f"{'Modified' if dirty else 'Saved'}"
                + (f" — {document_path}" if document_path else "")
            )
            texture = dict(project.texture_materials or {})
            source = dict(texture.get("source") or {})
            policy = dict(texture.get("output_policy") or {})
            if source:
                self.texture_path.setText(source.get("source_path", ""))
                self.txi_path.setText(source.get("txi_path", ""))
            if policy:
                self.texture_resref.setText(policy.get("output_resref", ""))
                _set_combo_data(
                    self.texture_format,
                    policy.get("output_format", "TGA"),
                )
                _set_combo_data(
                    self.alpha_mode,
                    policy.get("alpha_mode", "opaque"),
                )
                self.environment_map.setText(
                    policy.get("environment_map_resref", "")
                )
                self.bump_map.setText(policy.get("bumpmap_resref", ""))
            uv = dict(texture.get("uv_orientation") or {})
            if uv:
                _set_combo_data(
                    self.serialized_uv,
                    uv.get("serialized_transform", "identity"),
                )
                _set_combo_data(
                    self.preview_uv,
                    uv.get("preview_transform", "identity"),
                )
            package = dict(project.package_state or {})
            patch = dict(package.get("game_record_patch") or {})
            self.appearance_donor_label.setText(
                patch.get("appearance_donor_label", "")
            )
            self.appearance_label.setText(patch.get("appearance_label", ""))
            self.portrait_resref.setText(patch.get("portrait_resref", ""))
            self.portrait_donor_resref.setText(
                patch.get("portrait_donor_resref", "")
            )
            self.package_dir.setText(package.get("package_directory", ""))
            retail = dict(project.retail_test or {})
            if retail.get("passed"):
                self.retail_summary.setText(
                    "Retail observed: pass — "
                    + str(retail.get("observer_session") or "")
                )
        finally:
            self._loading = False

    def set_donor_rows(self, rows: Iterable[Any]) -> None:
        candidates = list(rows)
        self.donor_table.setRowCount(len(candidates))
        for row_index, candidate in enumerate(candidates):
            data = (
                candidate.to_dict()
                if hasattr(candidate, "to_dict")
                else dict(candidate)
            )
            resref = str(data.get("resref") or "")
            origin = "Override" if data.get("effective_override") else (
                "Stock" if data.get("stock") else "Mixed"
            )
            pair = "Ready" if data.get("complete_pair") else "Missing MDX"
            notes = "; ".join(str(value) for value in data.get("warnings") or ())
            values = (resref, origin, pair, notes)
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column == 0:
                    item.setData(QtCore.Qt.UserRole, resref)
                self.donor_table.setItem(row_index, column, item)
        self.donor_table.resizeColumnsToContents()
        if candidates:
            self.donor_table.selectRow(0)

    def set_donor_selection(self, selection: Any) -> None:
        snapshot = selection.snapshot
        for field in self.component_source_fields.values():
            if not field.text().strip():
                field.setText(str(snapshot.resref))
        palette = (
            snapshot.skins[0].bone_palette
            if getattr(snapshot, "skins", ())
            else ()
        )
        inherited_declaration = getattr(
            snapshot,
            "inherited_node_declaration",
            getattr(snapshot, "geometry_node_declaration", ""),
        )
        retail_min = getattr(
            snapshot,
            "retail_bb_min",
            getattr(snapshot, "model_bb_min", ()),
        )
        retail_max = getattr(
            snapshot,
            "retail_bb_max",
            getattr(snapshot, "model_bb_max", ()),
        )
        retail_radius = getattr(
            snapshot,
            "retail_radius",
            getattr(snapshot, "model_radius", 0.0),
        )
        self.donor_contract.setPlainText(
            "\n".join(
                (
                    f"Geometry root: {snapshot.geometry_root_name}",
                    f"Body attachment link: {snapshot.attachment_target_name}",
                    f"Supermodel: {snapshot.supermodel or 'None'}",
                    f"Local nodes: {snapshot.local_node_count}",
                    (
                        "Inherited node declaration: "
                        f"{inherited_declaration}"
                    ),
                    f"Local animation clips: {len(snapshot.local_animation_names)}",
                    f"Skin palette ({len(palette)}): {', '.join(palette)}",
                    (
                        "Retail model envelope: "
                        f"{retail_min} .. {retail_max}; radius {retail_radius:g}"
                    ),
                    (
                        "Preview geometry bounds: "
                        f"{snapshot.preview_bb_min} .. {snapshot.preview_bb_max}"
                    ),
                    (
                        "Provenance: "
                        f"{snapshot.game}:{snapshot.resref} "
                        f"({snapshot.resource_view})"
                    ),
                )
            )
        )

    def set_component_result(self, result: Any) -> None:
        report = result.report
        selections = dict(getattr(report, "source_resrefs", {}) or {})
        self.component_summary.setText(
            "Accepted vanilla combination — "
            f"{len(report.target_node_ordinals)} carrier mesh slots updated; "
            f"DAG-blocking differences: "
            f"{len(report.blocking_difference_paths)}. "
            + ", ".join(
                f"{role}: {resref}"
                for role, resref in selections.items()
            )
        )

    def set_art_document(self, document: Any, report: Any) -> None:
        self.art_path.setText(document.source_path)
        self.import_summary.setText(
            f"{document.source_format} — {document.vertex_count:,} vertices, "
            f"{document.face_count:,} faces, {len(document.parts)} parts — "
            f"{len(report.errors)} errors, {len(report.warnings)} warnings"
        )
        self.part_tree.clear()
        self.skin_part_table.setRowCount(len(document.parts))
        for row, part in enumerate(document.parts):
            topology = part.topology
            border_edges = getattr(
                topology,
                "border_edge_count",
                getattr(topology, "boundary_edge_count", 0),
            )
            summary = (
                f"{border_edges} boundary; "
                f"{topology.degenerate_face_count} degenerate"
            )
            self.part_tree.addTopLevelItem(
                QtWidgets.QTreeWidgetItem(
                    [
                        part.name,
                        part.material_name,
                        str(len(part.vertices)),
                        str(len(part.faces)),
                        summary,
                    ]
                )
            )
            item = QtWidgets.QTableWidgetItem(part.name)
            item.setData(QtCore.Qt.UserRole, part.part_id)
            self.skin_part_table.setItem(row, 0, item)
            combo = QtWidgets.QComboBox(self.skin_part_table)
            combo.addItem("Transfer donor surface weights", "surface_transfer")
            combo.addItem("Rigid-bind to fallback bone", "rigid_head_g")
            combo.addItem("Exclude from output", "exclude")
            lower = f"{part.name} {part.material_name}".casefold()
            if any(token in lower for token in ("hair", "horn", "accessory")):
                combo.setCurrentIndex(1)
            self.skin_part_table.setCellWidget(row, 1, combo)
            self.skin_part_table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(str(len(part.vertices))),
            )
            self.skin_part_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(str(len(part.faces))),
            )
        self.part_tree.resizeColumnToContents(0)
        self.skin_part_table.resizeColumnsToContents()

    def set_alignment_body(
        self,
        *,
        body_resref: str,
        headhook_node_path: str,
    ) -> None:
        self.alignment_body_resref.setText(body_resref)
        self.preview_body_resref.setText(body_resref)
        self.body_resref.setText(body_resref)
        self.headhook_path.setText(headhook_node_path)

    def set_anchor_point(
        self,
        role: str,
        side: str,
        point: Iterable[float],
    ) -> None:
        row = self._anchor_rows.get(str(role))
        if row is not None:
            row.set_point(side, point)

    def append_neck_vertex_ids(self, values: Iterable[str]) -> None:
        existing = {
            line.strip()
            for line in self.neck_vertex_ids.toPlainText().splitlines()
            if line.strip()
        }
        existing.update(str(value) for value in values if str(value))
        self.neck_vertex_ids.setPlainText("\n".join(sorted(existing)))

    def set_weight_vertex(self, vertex_id: str) -> None:
        self.weight_vertex_id.setText(str(vertex_id or ""))

    def reset_anchors(self) -> None:
        for index, row in enumerate(self._anchor_rows.values()):
            row.enabled.setChecked(index == 0)
            for spin in (*row.source_spins, *row.target_spins):
                spin.setValue(0.0)

    def set_alignment_result(self, result: Any) -> None:
        self.alignment_summary.setText(
            f"{result.method} — seam RMS {result.rms_error:.6g}, "
            f"maximum {result.max_error:.6g}, scale {result.scale:.6g}, "
            f"proper rotation det {result.rotation_determinant:.6g}, "
            f"confidence {result.confidence}"
        )

    def set_transplant_result(self, result: Any) -> None:
        report = result.report
        if hasattr(report, "facial_skin_vertex_count"):
            component_rows = tuple(report.component_nodes or ())
            component_vertices = sum(
                int(row[2]) for row in component_rows
            )
            component_faces = sum(int(row[3]) for row in component_rows)
            self.skin_summary.setText(
                "Accepted semantic facial payload — "
                f"{report.facial_skin_vertex_count + component_vertices:,} "
                "visible vertices, "
                f"{report.facial_skin_face_count + component_faces:,} faces, "
                f"{len(component_rows)} articulated facial components, "
                f"{report.rigid_accessory_vertex_count} rigid accessory "
                "vertices. DAG-blocking differences: "
                f"{len(report.blocking_difference_paths)}."
            )
            return
        self.skin_summary.setText(
            f"Accepted donor-preserving payload — "
            f"{report.output_vertex_count:,} vertices, "
            f"{report.output_face_count:,} faces, "
            f"{report.palette_size} palette slots, "
            f"{report.manual_edit_count} manual edits. "
            f"DAG-blocking differences: "
            f"{len(report.blocking_difference_paths)}."
        )
        palette = list(report.palette_names)
        for combo, _weight in self.weight_rows:
            current = combo.currentText()
            combo.clear()
            combo.addItem("")
            combo.addItems(palette)
            if current:
                combo.setCurrentText(current)

    def set_texture_result(self, result: Any) -> None:
        report = result.report
        policy = result.output_policy
        self.texture_summary.setText(
            f"Accepted {policy.output_format} contract — "
            f"{policy.output_resref}; packaged files "
            f"{', '.join(policy.packaged_files)}. "
            f"Preview/serialized UV match: "
            f"{'yes' if report.preview_matches_serialized else 'no'}."
        )

    def set_preview_result(self, result: Any) -> None:
        report = result.report
        self.preview_summary.setPlainText(
            "\n".join(
                (
                    f"Geometry root: {report.head_root_name}",
                    f"Body attachment link: {report.source_head_parent_name}",
                    f"Body headhook: {report.headhook_node_path}",
                    f"Headhook world position: {report.headhook_world_position}",
                    f"Head supermodel: {report.head_supermodel or 'None'}",
                    f"Local head clips: {len(report.source_head_local_animation_names)}",
                    f"Effective animations: {len(report.effective_animations)}",
                    f"Facial animations: {len(report.facial_animation_names)}",
                    f"Supermodel chain: {' → '.join(report.supermodel_chain) or 'None'}",
                    f"Contract: {report.contract_sha256}",
                )
            )
        )

    def set_preflight_report(self, report: Any) -> None:
        self.preflight_tree.clear()
        for issue in report.issues:
            severity = getattr(issue.severity, "value", issue.severity)
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(severity).title(),
                    issue.check_id,
                    issue.message,
                    issue.fix_hint,
                ]
            )
            item.setData(0, QtCore.Qt.UserRole, issue.check_id)
            self.preflight_tree.addTopLevelItem(item)
        self.preflight_tree.resizeColumnToContents(0)
        self.preflight_tree.resizeColumnToContents(1)
        self.preflight_summary.setText(
            (
                "Export allowed"
                if report.export_allowed
                else "Export remains blocked"
            )
            + f" — {len(report.blocking_issues)} blocking, "
            f"{len(report.warning_issues)} warnings, "
            f"{len(report.unacknowledged_warning_ids)} unacknowledged."
        )

    def set_package_result(self, result: Any) -> None:
        merge = result.reference_merge
        self.package_summary.setPlainText(
            "\n".join(
                (
                    f"Package: {result.package_directory}",
                    f"heads.2da row: {merge.heads_row}",
                    f"appearance.2da row: {merge.appearance_row}",
                    f"portraits.2da row: {merge.portraits_row}",
                    f"Files: {len(result.files)}",
                    f"Report: {result.report_path}",
                    f"TSLPatcher: {result.patch_path}",
                )
            )
        )
        self.package_dir.setText(result.package_directory)

    def set_install_preview(self, preview: Any) -> None:
        self._install_preview_id = str(preview.preview_id or "")
        self.confirm_install.setChecked(False)
        self.install_tree.clear()
        for row in preview.files:
            payload = dict(row)
            self.install_tree.addTopLevelItem(
                QtWidgets.QTreeWidgetItem(
                    [
                        str(payload.get("destination") or ""),
                        str(payload.get("action") or ""),
                        str(payload.get("current_sha256") or "")[:16],
                        str(payload.get("candidate_sha256") or "")[:16],
                    ]
                )
            )
        self.install_tree.resizeColumnToContents(0)
        self.retail_summary.setText(
            f"Read-only preview ready — {len(preview.files)} exact "
            f"destination(s); no game files changed."
        )

    def set_install_result(self, result: Any) -> None:
        if result.installed:
            self.retail_summary.setText(
                f"Test installed transactionally — "
                f"{len(result.installed_files)} file(s). Retail is still "
                "not tested until the checklist is observed."
            )
        elif result.restored:
            self.retail_summary.setText(
                f"Previous test restored — "
                f"{len(result.restored_files)} file(s)."
            )

    def apply_ghost_theme(self, _theme: object) -> None:
        """All controls use semantic application palette roles."""

        self.update()

    def apply_ghost_layout(self, layout: object) -> None:
        spacing = getattr(layout, "spacing_value", lambda _key, default: default)
        if self.layout() is not None:
            margin = int(spacing("panelSpacing", 6))
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(int(spacing("groupboxSpacing", 6)))


class QtHeadBuilderAssetTree(QtWidgets.QWidget):
    """Compact left-side project/resource provenance view."""

    resourceActivated = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeadBuilderAssetTree")
        self.setProperty("ghostLayoutId", "headBuilderAssets")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        label = QtWidgets.QLabel("PROJECT ASSETS", self)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        self.tree = QtWidgets.QTreeWidget(self)
        self.tree.setHeaderLabels(["Asset", "Source"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._activated)
        layout.addWidget(self.tree, 1)

    def _activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        resource_id = str(item.data(0, QtCore.Qt.UserRole) or "")
        if resource_id:
            self.resourceActivated.emit(resource_id)

    def set_project(self, project: Any) -> None:
        self.tree.clear()
        for resource_id in sorted(project.resources):
            resource = project.resources[resource_id]
            source = (
                resource.origin.value.replace("_", " ").title()
                + (" — stock" if resource.stock else "")
            )
            item = QtWidgets.QTreeWidgetItem(
                [
                    resource.resref
                    or Path(resource.source_path).name
                    or resource.resource_id,
                    source,
                ]
            )
            item.setData(0, QtCore.Qt.UserRole, resource.resource_id)
            item.setToolTip(
                0,
                f"{resource.resource_type} · {resource.source_path or resource.container}\n"
                f"SHA-256 {resource.sha256}",
            )
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)

    def apply_ghost_theme(self, _theme: object) -> None:
        self.update()

    def apply_ghost_layout(self, layout: object) -> None:
        spacing = getattr(layout, "spacing_value", lambda _key, default: default)
        if self.layout() is not None:
            value = int(spacing("panelSpacing", 4))
            self.layout().setContentsMargins(value, value, value, value)


class QtHeadBuilderEvidencePanel(QtWidgets.QWidget):
    """Filterable bottom panel with honest evidence levels and outcomes."""

    stepRequested = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeadBuilderEvidencePanel")
        self.setProperty("ghostLayoutId", "headBuilderEvidence")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        filters = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("VALIDATION & EVIDENCE", self)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Filter checks, messages, or hashes")
        self.level = QtWidgets.QComboBox(self)
        self.level.addItem("All evidence", "")
        self.level.addItem("Structural", "structural")
        self.level.addItem("Editor visual", "editor_visual")
        self.level.addItem("Retail observed", "retail_observed")
        self.level.addItem("Not tested", "not_tested")
        filters.addWidget(label)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.level)
        layout.addLayout(filters)
        self.table = QtWidgets.QTreeWidget(self)
        self.table.setHeaderLabels(
            ["Outcome", "Evidence", "Level", "Message", "Recorded"]
        )
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.table.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.table, 1)
        self.search.textChanged.connect(self._apply_filter)
        self.level.currentIndexChanged.connect(self._apply_filter)

    def set_project(self, project: Any) -> None:
        self.table.clear()
        for record in reversed(list(project.validation_results or [])):
            hashes = " ".join(
                f"{key}:{value}" for key, value in record.hashes.items()
            )
            item = QtWidgets.QTreeWidgetItem(
                [
                    record.outcome.value.replace("_", " ").title(),
                    record.label,
                    record.level.value.replace("_", " ").title(),
                    record.message,
                    record.recorded_at,
                ]
            )
            item.setData(
                0,
                QtCore.Qt.UserRole,
                self._step_for_check(record.check_id),
            )
            item.setData(
                0,
                QtCore.Qt.UserRole + 1,
                record.level.value,
            )
            item.setToolTip(
                3,
                record.message
                + (f"\n{hashes}" if hashes else "")
                + (
                    f"\nObserver: {record.observer_session}"
                    if record.observer_session
                    else ""
                ),
            )
            self.table.addTopLevelItem(item)
        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(1)
        self.table.resizeColumnToContents(2)
        self._apply_filter()

    @staticmethod
    def _step_for_check(check_id: str) -> int:
        key = str(check_id or "").casefold()
        if ".retail." in key or ".install" in key:
            return 11
        if ".package." in key:
            return 10
        if ".preflight." in key or ".binary." in key:
            return 9
        if ".preview." in key or ".attachment" in key:
            return 7
        if ".texture" in key or ".uv" in key:
            return 6
        if ".transplant" in key or ".skin" in key or ".weight" in key:
            return 5
        if ".alignment" in key or ".headhook" in key:
            return 4
        if ".donor" in key:
            return 3
        if ".art" in key or ".import" in key:
            return 2
        return 1

    def _apply_filter(self) -> None:
        text = self.search.text().strip().casefold()
        level = str(self.level.currentData() or "")
        for row in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(row)
            haystack = " ".join(item.text(column) for column in range(5)).casefold()
            item_level = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
            item.setHidden(
                (bool(text) and text not in haystack)
                or (bool(level) and level != item_level)
            )

    def _activate(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        step = int(item.data(0, QtCore.Qt.UserRole) or 0)
        if step:
            self.stepRequested.emit(step)

    def apply_ghost_theme(self, _theme: object) -> None:
        self.update()

    def apply_ghost_layout(self, layout: object) -> None:
        spacing = getattr(layout, "spacing_value", lambda _key, default: default)
        if self.layout() is not None:
            value = int(spacing("panelSpacing", 4))
            self.layout().setContentsMargins(value, value, value, value)
            self.layout().setSpacing(value)


__all__ = [
    "HEAD_BUILDER_STEPS",
    "RETAIL_CHECKS",
    "QtHeadBuilderAssetTree",
    "QtHeadBuilderEvidencePanel",
    "QtHeadBuilderProperties",
]
