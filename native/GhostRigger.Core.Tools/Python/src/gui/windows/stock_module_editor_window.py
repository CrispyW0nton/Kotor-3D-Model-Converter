"""Stock KotOR MOD/RIM module editor workspace."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import tempfile

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.stock_modules.stock_module_archive import (
    ModuleArchiveResource,
    read_module_archive_resources,
    read_module_resource_bytes,
)
from src.core.stock_modules.stock_module_export_queue import (
    QueuedModuleEditDraft,
    describe_module_edit_draft,
    summarize_queued_module_patch_preflight,
    write_queued_module_patch_export_copy,
)
from src.core.stock_modules.stock_module_materials import (
    ModuleRoomMaterialInventory,
    ModuleRoomTextureSlot,
    ModuleTextureReplacementDraft,
    create_texture_replacement_draft,
    create_texture_replacement_drafts_for_matching_slots,
    find_texture_usage_slots,
    inspect_module_room_materials,
    summarize_material_inventories,
    summarize_texture_dependencies,
    summarize_texture_preview_overrides,
    summarize_texture_usage,
    texture_preview_for_slot,
)
from src.core.stock_modules.stock_module_git import (
    ModuleGitInventory,
    ModuleGitObjectEditDraft,
    ModuleGitObjectRow,
    create_git_object_edit_draft,
    inspect_module_git,
    write_git_object_patch_export_copy,
)
from src.core.stock_modules.stock_module_layout import (
    ModuleLayoutEditDraft,
    ModuleLayoutInventory,
    ModuleLayoutRoomRow,
    ModuleVisibilityRow,
    create_layout_edit_draft,
    inspect_module_layout,
    write_layout_patch_export_copy,
)
from src.core.stock_modules.stock_module_logic import (
    LOGIC_TYPES,
    ModuleLogicField,
    ModuleLogicFieldEditDraft,
    ModuleLogicInventory,
    create_logic_field_edit_draft,
    inspect_module_logic,
    write_logic_field_patch_export_copy,
)
from src.core.stock_modules.stock_module_metadata import (
    ModuleMetadataField,
    ModuleMetadataFieldEditDraft,
    ModuleMetadataInventory,
    create_metadata_field_edit_draft,
    inspect_module_metadata,
    write_metadata_field_patch_export_copy,
)
from src.core.stock_modules.stock_module_patch_plan import (
    ModuleTexturePatchIssue,
    build_texture_patch_plan,
    summarize_texture_patch_preflight,
    write_texture_patch_export_copy,
)
from src.core.stock_modules.stock_module_package_intake import (
    PreparedModuleOpenPath,
    prepare_module_open_path,
)
from src.core.stock_modules.stock_module_resource_safety import (
    classify_module_resource,
    summarize_resource_safety,
    summarize_resource_safety_scopes,
)
from src.core.stock_modules.stock_module_tga_editor import ModuleTgaEditDraft, create_tga_adjustment_draft
from src.core.stock_modules.stock_module_txi_editor import ModuleTxiEditDraft, create_txi_text_edit_draft
from src.core.stock_modules.stock_module_textures import (
    ModuleTextureFileResource,
    ModuleTextureLibraryResource,
    ModuleTextureMemoryResource,
    ModuleTexturePreview,
    decode_module_texture_preview,
)
from src.core.stock_modules.stock_module_templates import (
    ModuleTemplateField,
    ModuleTemplateFieldEditDraft,
    ModuleTemplateInventory,
    create_template_field_edit_draft,
    inspect_module_template,
    write_template_field_patch_export_copy,
)
from src.core.stock_modules.stock_module_walkmesh import (
    ModuleWokInventory,
    ModuleWokSurfacePaintDraft,
    ModuleWokSurfaceSummary,
    create_wok_surface_paint_draft,
    inspect_module_wok,
    walkmesh_surface_options,
    write_wok_surface_patch_export_copy,
)

TEXTURE_TYPES = {"tga", "tpc", "txi", "txt"}
GAMEPLAY_TYPES = {"utc", "utp", "utd", "utt", "uts", "ute", "utw", "utm", "uti"}
ROOM_TYPES = {"mdl", "mdx", "wok", "lyt", "vis"}
MODULE_TYPES = {"are", "git", "ifo"}
GIT_TEMPLATE_TYPES = {
    "creature": "utc",
    "door": "utd",
    "placeable": "utp",
    "trigger": "utt",
    "encounter": "ute",
    "waypoint": "utw",
    "sound": "uts",
    "store": "utm",
}


BrowserResource = ModuleArchiveResource | ModuleTextureFileResource | ModuleTextureLibraryResource | ModuleTextureMemoryResource


@dataclass(frozen=True)
class ModuleAuditFilterTarget:
    kind: str
    value: str


class StockModuleEditorWindow(QtWidgets.QMainWindow):
    """Dedicated editor shell for existing KotOR .mod/.rim archives."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, game_library: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghost-Studio Module Editor")
        self.setObjectName("stockModuleEditorWindow")
        self.resize(1320, 820)
        self._module_path: Path | None = None
        self._module_source_path: Path | None = None
        self._module_source_label = ""
        self._module_package_tempdir: tempfile.TemporaryDirectory[str] | None = None
        self._resources: list[ModuleArchiveResource] = []
        self._game_library: object | None = None
        self._game_library_game = "K2"
        self._game_texture_resources: list[ModuleTextureLibraryResource] = []
        self._imported_texture_resources: list[ModuleTextureFileResource | ModuleTextureMemoryResource] = []
        self._texture_preview_cache: dict[str, ModuleTexturePreview | None] = {}
        self._texture_icon_cache: dict[str, QtGui.QIcon] = {}
        self._material_inventory_cache: dict[str, ModuleRoomMaterialInventory] = {}
        self._wok_inventory_cache: dict[str, ModuleWokInventory] = {}
        self._git_inventory_cache: dict[str, ModuleGitInventory] = {}
        self._layout_inventory_cache: dict[str, ModuleLayoutInventory] = {}
        self._logic_inventory_cache: dict[str, ModuleLogicInventory] = {}
        self._metadata_inventory_cache: dict[str, ModuleMetadataInventory] = {}
        self._template_inventory_cache: dict[str, ModuleTemplateInventory] = {}
        self._room_board_hit_slots: list[tuple[QtCore.QRect, ModuleRoomTextureSlot]] = []
        self._room_board_page_by_room: dict[str, int] = {}
        self._room_board_inventory: ModuleRoomMaterialInventory | None = None
        self._room_board_visible_slot_count = 0
        self._selected_material_slot: ModuleRoomTextureSlot | None = None
        self._pending_texture_replacement: ModuleTextureReplacementDraft | None = None
        self._selected_tga_resource: BrowserResource | None = None
        self._pending_tga_edit: ModuleTgaEditDraft | None = None
        self._selected_txi_source_resource: BrowserResource | None = None
        self._pending_txi_edit: ModuleTxiEditDraft | None = None
        self._selected_wok_resource: ModuleArchiveResource | None = None
        self._pending_wok_surface_paint: ModuleWokSurfacePaintDraft | None = None
        self._selected_git_resource: ModuleArchiveResource | None = None
        self._selected_git_inventory: ModuleGitInventory | None = None
        self._pending_git_object_edit: ModuleGitObjectEditDraft | None = None
        self._selected_template_resource: ModuleArchiveResource | None = None
        self._pending_template_field_edit: ModuleTemplateFieldEditDraft | None = None
        self._selected_metadata_resource: ModuleArchiveResource | None = None
        self._pending_metadata_field_edit: ModuleMetadataFieldEditDraft | None = None
        self._selected_layout_resource: ModuleArchiveResource | None = None
        self._pending_layout_edit: ModuleLayoutEditDraft | None = None
        self._selected_logic_resource: ModuleArchiveResource | None = None
        self._pending_logic_field_edit: ModuleLogicFieldEditDraft | None = None
        self._staged_edits: list[QueuedModuleEditDraft] = []
        self._details_row_payloads: dict[int, object] = {}

        self._build_actions()
        self._build_ui()
        if game_library is not None:
            self.set_game_library(game_library)
        self.statusBar().showMessage("Module Editor ready.")

    def _build_actions(self) -> None:
        self.open_module_action = QtGui.QAction("Open Module...", self)
        self.open_module_action.setObjectName("stockModuleEditorOpenModuleAction")
        self.open_module_action.triggered.connect(self._browse_open_module)
        self.save_copy_action = QtGui.QAction("Export Edited Copy...", self)
        self.save_copy_action.setObjectName("stockModuleEditorExportCopyAction")
        self.save_copy_action.setEnabled(False)
        self.save_copy_action.triggered.connect(self._export_texture_patch_copy)
        self.import_texture_action = QtGui.QAction("Import Replacement Texture...", self)
        self.import_texture_action.setObjectName("stockModuleEditorImportTextureAction")
        self.import_texture_action.triggered.connect(self._browse_import_texture)
        self.stage_edit_action = QtGui.QAction("Stage Previewed Edit", self)
        self.stage_edit_action.setObjectName("stockModuleEditorStageEditAction")
        self.stage_edit_action.setEnabled(False)
        self.stage_edit_action.triggered.connect(self._stage_current_edit)
        self.stage_matching_textures_action = QtGui.QAction("Stage Matching Texture Uses", self)
        self.stage_matching_textures_action.setObjectName("stockModuleEditorStageMatchingTexturesAction")
        self.stage_matching_textures_action.setEnabled(False)
        self.stage_matching_textures_action.triggered.connect(self._stage_matching_texture_replacements)
        self.clear_staged_edits_action = QtGui.QAction("Clear Staged Edits", self)
        self.clear_staged_edits_action.setObjectName("stockModuleEditorClearStagedEditsAction")
        self.clear_staged_edits_action.setEnabled(False)
        self.clear_staged_edits_action.triggered.connect(self._clear_staged_edits)

    def _build_ui(self) -> None:
        toolbar = self.addToolBar("Module Editor")
        toolbar.setObjectName("stockModuleEditorToolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_module_action)
        toolbar.addAction(self.import_texture_action)
        toolbar.addAction(self.stage_edit_action)
        toolbar.addAction(self.stage_matching_textures_action)
        toolbar.addAction(self.clear_staged_edits_action)
        toolbar.addAction(self.save_copy_action)

        central = QtWidgets.QWidget(self)
        root = QtWidgets.QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        self.setCentralWidget(central)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, central)
        self.main_splitter.setObjectName("stockModuleEditorMainSplitter")
        root.addWidget(self.main_splitter, 1)

        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self.main_splitter)
        self.left_splitter.setObjectName("stockModuleEditorLeftResourceSplitter")
        self.main_splitter.addWidget(self.left_splitter)

        self.outliner = QtWidgets.QTreeWidget(self.left_splitter)
        self.outliner.setObjectName("stockModuleEditorSceneOutliner")
        self.outliner.setHeaderLabels(["Module Outliner", "Count"])
        self.outliner.itemSelectionChanged.connect(self._sync_selection_from_outliner)
        self.left_splitter.addWidget(self.outliner)

        content_frame = QtWidgets.QWidget(self.left_splitter)
        content_frame.setObjectName("stockModuleEditorContentBrowserFrame")
        content_layout = QtWidgets.QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        filter_row = QtWidgets.QHBoxLayout()
        self.content_search = QtWidgets.QLineEdit(content_frame)
        self.content_search.setObjectName("stockModuleEditorContentSearch")
        self.content_search.setPlaceholderText("Filter resources")
        self.content_type_combo = QtWidgets.QComboBox(content_frame)
        self.content_type_combo.setObjectName("stockModuleEditorContentTypeCombo")
        self.content_type_combo.addItems(["All", "Textures", "Rooms", "Gameplay", "Module", "Logic"])
        filter_row.addWidget(self.content_search, 1)
        filter_row.addWidget(self.content_type_combo)
        content_layout.addLayout(filter_row)
        self.content_browser = QtWidgets.QListWidget(content_frame)
        self.content_browser.setObjectName("stockModuleEditorContentBrowser")
        self.content_browser.setViewMode(QtWidgets.QListView.IconMode)
        self.content_browser.setResizeMode(QtWidgets.QListView.Adjust)
        self.content_browser.setMovement(QtWidgets.QListView.Static)
        self.content_browser.setIconSize(QtCore.QSize(72, 72))
        self.content_browser.setGridSize(QtCore.QSize(120, 104))
        self.content_browser.setUniformItemSizes(True)
        self.content_browser.itemSelectionChanged.connect(self._sync_selection_from_content_browser)
        content_layout.addWidget(self.content_browser, 1)
        self.left_splitter.addWidget(content_frame)

        center = QtWidgets.QWidget(self.main_splitter)
        center.setObjectName("stockModuleEditorPreviewColumn")
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)
        self.preview_label = QtWidgets.QLabel(center)
        self.preview_label.setObjectName("stockModuleEditorViewportPreview")
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumSize(500, 420)
        self.preview_label.setText("Open a MOD or RIM archive")
        self.preview_label.installEventFilter(self)
        center_layout.addWidget(self.preview_label, 1)
        self.material_board_nav = QtWidgets.QWidget(center)
        self.material_board_nav.setObjectName("stockModuleEditorMaterialBoardNavigation")
        material_board_nav_layout = QtWidgets.QHBoxLayout(self.material_board_nav)
        material_board_nav_layout.setContentsMargins(0, 0, 0, 0)
        material_board_nav_layout.setSpacing(6)
        self.material_board_prev_button = QtWidgets.QPushButton("<", self.material_board_nav)
        self.material_board_prev_button.setObjectName("stockModuleEditorMaterialBoardPrevButton")
        self.material_board_prev_button.setEnabled(False)
        self.material_board_prev_button.clicked.connect(self._previous_room_board_page)
        material_board_nav_layout.addWidget(self.material_board_prev_button)
        self.material_board_page_label = QtWidgets.QLabel("0 of 0", self.material_board_nav)
        self.material_board_page_label.setObjectName("stockModuleEditorMaterialBoardPageLabel")
        self.material_board_page_label.setAlignment(QtCore.Qt.AlignCenter)
        material_board_nav_layout.addWidget(self.material_board_page_label, 1)
        self.material_board_next_button = QtWidgets.QPushButton(">", self.material_board_nav)
        self.material_board_next_button.setObjectName("stockModuleEditorMaterialBoardNextButton")
        self.material_board_next_button.setEnabled(False)
        self.material_board_next_button.clicked.connect(self._next_room_board_page)
        material_board_nav_layout.addWidget(self.material_board_next_button)
        center_layout.addWidget(self.material_board_nav)
        self.material_filter_edit = QtWidgets.QLineEdit(center)
        self.material_filter_edit.setObjectName("stockModuleEditorMaterialFilter")
        self.material_filter_edit.setPlaceholderText("filter material targets")
        self.material_filter_edit.textChanged.connect(self._material_filter_changed)
        center_layout.addWidget(self.material_filter_edit)
        self.material_pick_panel = QtWidgets.QListWidget(center)
        self.material_pick_panel.setObjectName("stockModuleEditorMaterialPickPanel")
        self.material_pick_panel.setViewMode(QtWidgets.QListView.IconMode)
        self.material_pick_panel.setResizeMode(QtWidgets.QListView.Adjust)
        self.material_pick_panel.setMovement(QtWidgets.QListView.Static)
        self.material_pick_panel.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.material_pick_panel.setIconSize(QtCore.QSize(52, 52))
        self.material_pick_panel.setGridSize(QtCore.QSize(128, 84))
        self.material_pick_panel.setUniformItemSizes(True)
        self.material_pick_panel.setMaximumHeight(112)
        self.material_pick_panel.itemSelectionChanged.connect(self._sync_selection_from_material_pick_panel)
        center_layout.addWidget(self.material_pick_panel)
        self.material_picker = QtWidgets.QListWidget(center)
        self.material_picker.setObjectName("stockModuleEditorMaterialPicker")
        self.material_picker.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.material_picker.setUniformItemSizes(True)
        self.material_picker.setAlternatingRowColors(True)
        self.material_picker.itemSelectionChanged.connect(self._sync_selection_from_material_picker)
        center_layout.addWidget(self.material_picker)
        self.material_preview = QtWidgets.QTableWidget(center)
        self.material_preview.setObjectName("stockModuleEditorMaterialPreview")
        self.material_preview.setColumnCount(2)
        self.material_preview.setHorizontalHeaderLabels(["Picked material", "Value"])
        self.material_preview.horizontalHeader().setStretchLastSection(True)
        self.material_preview.verticalHeader().setVisible(False)
        self.material_preview.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.material_preview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.material_preview.setAlternatingRowColors(True)
        self.material_preview.setMaximumHeight(164)
        center_layout.addWidget(self.material_preview)
        texture_compare = QtWidgets.QWidget(center)
        texture_compare.setObjectName("stockModuleEditorTextureCompare")
        texture_compare_layout = QtWidgets.QHBoxLayout(texture_compare)
        texture_compare_layout.setContentsMargins(0, 0, 0, 0)
        texture_compare_layout.setSpacing(6)
        self.current_texture_preview = QtWidgets.QLabel(texture_compare)
        self.current_texture_preview.setObjectName("stockModuleEditorCurrentTexturePreview")
        self.current_texture_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.current_texture_preview.setMinimumSize(160, 120)
        self.current_texture_preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.current_texture_preview.setText("Current texture")
        texture_compare_layout.addWidget(self.current_texture_preview, 1)
        self.replacement_texture_preview = QtWidgets.QLabel(texture_compare)
        self.replacement_texture_preview.setObjectName("stockModuleEditorReplacementTexturePreview")
        self.replacement_texture_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.replacement_texture_preview.setMinimumSize(160, 120)
        self.replacement_texture_preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.replacement_texture_preview.setText("Replacement texture")
        texture_compare_layout.addWidget(self.replacement_texture_preview, 1)
        center_layout.addWidget(texture_compare)
        self.tga_editor = QtWidgets.QWidget(center)
        self.tga_editor.setObjectName("stockModuleEditorTgaEditor")
        tga_layout = QtWidgets.QHBoxLayout(self.tga_editor)
        tga_layout.setContentsMargins(0, 0, 0, 0)
        tga_layout.setSpacing(6)
        self.tga_output_resref_edit = QtWidgets.QLineEdit(self.tga_editor)
        self.tga_output_resref_edit.setObjectName("stockModuleEditorTgaOutputResRef")
        self.tga_output_resref_edit.setPlaceholderText("edited texture resref")
        self.tga_output_resref_edit.setMaxLength(16)
        self.tga_output_resref_edit.setEnabled(False)
        tga_layout.addWidget(self.tga_output_resref_edit, 1)
        self.tga_brightness_spin = QtWidgets.QSpinBox(self.tga_editor)
        self.tga_brightness_spin.setObjectName("stockModuleEditorTgaBrightnessSpin")
        self.tga_brightness_spin.setRange(-100, 100)
        self.tga_brightness_spin.setSuffix(" B")
        self.tga_brightness_spin.setEnabled(False)
        tga_layout.addWidget(self.tga_brightness_spin)
        self.tga_contrast_spin = QtWidgets.QSpinBox(self.tga_editor)
        self.tga_contrast_spin.setObjectName("stockModuleEditorTgaContrastSpin")
        self.tga_contrast_spin.setRange(-100, 100)
        self.tga_contrast_spin.setSuffix(" C")
        self.tga_contrast_spin.setEnabled(False)
        tga_layout.addWidget(self.tga_contrast_spin)
        self.tga_snow_spin = QtWidgets.QSpinBox(self.tga_editor)
        self.tga_snow_spin.setObjectName("stockModuleEditorTgaSnowSpin")
        self.tga_snow_spin.setRange(0, 100)
        self.tga_snow_spin.setSuffix(" snow")
        self.tga_snow_spin.setEnabled(False)
        tga_layout.addWidget(self.tga_snow_spin)
        self.tga_preview_button = QtWidgets.QPushButton("Preview TGA Edit", self.tga_editor)
        self.tga_preview_button.setObjectName("stockModuleEditorTgaPreviewEditButton")
        self.tga_preview_button.setEnabled(False)
        self.tga_preview_button.clicked.connect(self._preview_tga_edit)
        tga_layout.addWidget(self.tga_preview_button)
        center_layout.addWidget(self.tga_editor)
        self.txi_editor = QtWidgets.QWidget(center)
        self.txi_editor.setObjectName("stockModuleEditorTxiEditor")
        txi_layout = QtWidgets.QHBoxLayout(self.txi_editor)
        txi_layout.setContentsMargins(0, 0, 0, 0)
        txi_layout.setSpacing(6)
        self.txi_output_resref_edit = QtWidgets.QLineEdit(self.txi_editor)
        self.txi_output_resref_edit.setObjectName("stockModuleEditorTxiOutputResRef")
        self.txi_output_resref_edit.setPlaceholderText("txi sidecar resref")
        self.txi_output_resref_edit.setMaxLength(16)
        self.txi_output_resref_edit.setEnabled(False)
        txi_layout.addWidget(self.txi_output_resref_edit)
        self.txi_text_edit = QtWidgets.QPlainTextEdit(self.txi_editor)
        self.txi_text_edit.setObjectName("stockModuleEditorTxiTextEdit")
        self.txi_text_edit.setPlaceholderText("TXI directives")
        self.txi_text_edit.setMaximumHeight(74)
        self.txi_text_edit.setEnabled(False)
        txi_layout.addWidget(self.txi_text_edit, 1)
        self.txi_preview_button = QtWidgets.QPushButton("Preview TXI Sidecar", self.txi_editor)
        self.txi_preview_button.setObjectName("stockModuleEditorTxiPreviewEditButton")
        self.txi_preview_button.setEnabled(False)
        self.txi_preview_button.clicked.connect(self._preview_txi_edit)
        txi_layout.addWidget(self.txi_preview_button)
        center_layout.addWidget(self.txi_editor)
        self.wok_surface_editor = QtWidgets.QWidget(center)
        self.wok_surface_editor.setObjectName("stockModuleEditorWokSurfaceEditor")
        wok_surface_layout = QtWidgets.QHBoxLayout(self.wok_surface_editor)
        wok_surface_layout.setContentsMargins(0, 0, 0, 0)
        wok_surface_layout.setSpacing(6)
        self.wok_face_spin = QtWidgets.QSpinBox(self.wok_surface_editor)
        self.wok_face_spin.setObjectName("stockModuleEditorWokFaceSpin")
        self.wok_face_spin.setMinimum(0)
        self.wok_face_spin.setEnabled(False)
        self.wok_face_spin.setToolTip("Walkmesh face index to preview-paint")
        wok_surface_layout.addWidget(self.wok_face_spin)
        self.wok_surface_combo = QtWidgets.QComboBox(self.wok_surface_editor)
        self.wok_surface_combo.setObjectName("stockModuleEditorWokSurfaceCombo")
        self.wok_surface_combo.setEnabled(False)
        for surface in walkmesh_surface_options():
            state = "walkable" if surface.walkable else "blocked"
            self.wok_surface_combo.addItem(
                f"{surface.surface_id} - {surface.surface_name} ({state})",
                int(surface.surface_id),
            )
        wok_surface_layout.addWidget(self.wok_surface_combo, 1)
        self.wok_preview_button = QtWidgets.QPushButton("Preview WOK Paint", self.wok_surface_editor)
        self.wok_preview_button.setObjectName("stockModuleEditorWokPreviewPaintButton")
        self.wok_preview_button.setEnabled(False)
        self.wok_preview_button.clicked.connect(self._preview_wok_surface_paint)
        wok_surface_layout.addWidget(self.wok_preview_button)
        center_layout.addWidget(self.wok_surface_editor)
        self.layout_editor = QtWidgets.QWidget(center)
        self.layout_editor.setObjectName("stockModuleEditorLayoutEditor")
        layout_editor_layout = QtWidgets.QHBoxLayout(self.layout_editor)
        layout_editor_layout.setContentsMargins(0, 0, 0, 0)
        layout_editor_layout.setSpacing(6)
        self.layout_target_combo = QtWidgets.QComboBox(self.layout_editor)
        self.layout_target_combo.setObjectName("stockModuleEditorLayoutTargetCombo")
        self.layout_target_combo.setEnabled(False)
        self.layout_target_combo.currentIndexChanged.connect(self._populate_layout_field_editor)
        layout_editor_layout.addWidget(self.layout_target_combo, 1)
        self.layout_field_combo = QtWidgets.QComboBox(self.layout_editor)
        self.layout_field_combo.setObjectName("stockModuleEditorLayoutFieldCombo")
        self.layout_field_combo.setEnabled(False)
        self.layout_field_combo.currentIndexChanged.connect(self._sync_layout_edit_value)
        layout_editor_layout.addWidget(self.layout_field_combo)
        self.layout_value_edit = QtWidgets.QLineEdit(self.layout_editor)
        self.layout_value_edit.setObjectName("stockModuleEditorLayoutValueEdit")
        self.layout_value_edit.setEnabled(False)
        layout_editor_layout.addWidget(self.layout_value_edit)
        self.layout_visible_toggle = QtWidgets.QCheckBox("Visible", self.layout_editor)
        self.layout_visible_toggle.setObjectName("stockModuleEditorLayoutVisibleToggle")
        self.layout_visible_toggle.setEnabled(False)
        layout_editor_layout.addWidget(self.layout_visible_toggle)
        self.layout_preview_button = QtWidgets.QPushButton("Preview Layout Edit", self.layout_editor)
        self.layout_preview_button.setObjectName("stockModuleEditorLayoutPreviewEditButton")
        self.layout_preview_button.setEnabled(False)
        self.layout_preview_button.clicked.connect(self._preview_layout_edit)
        layout_editor_layout.addWidget(self.layout_preview_button)
        center_layout.addWidget(self.layout_editor)
        self.git_object_editor = QtWidgets.QWidget(center)
        self.git_object_editor.setObjectName("stockModuleEditorGitObjectEditor")
        git_object_layout = QtWidgets.QHBoxLayout(self.git_object_editor)
        git_object_layout.setContentsMargins(0, 0, 0, 0)
        git_object_layout.setSpacing(6)
        self.git_object_filter_edit = QtWidgets.QLineEdit(self.git_object_editor)
        self.git_object_filter_edit.setObjectName("stockModuleEditorGitObjectFilter")
        self.git_object_filter_edit.setPlaceholderText("Filter objects")
        self.git_object_filter_edit.setClearButtonEnabled(True)
        self.git_object_filter_edit.setEnabled(False)
        self.git_object_filter_edit.textChanged.connect(self._git_object_filter_changed)
        git_object_layout.addWidget(self.git_object_filter_edit)
        self.git_object_combo = QtWidgets.QComboBox(self.git_object_editor)
        self.git_object_combo.setObjectName("stockModuleEditorGitObjectCombo")
        self.git_object_combo.setEnabled(False)
        self.git_object_combo.currentIndexChanged.connect(self._populate_git_field_editor)
        git_object_layout.addWidget(self.git_object_combo, 1)
        self.git_field_combo = QtWidgets.QComboBox(self.git_object_editor)
        self.git_field_combo.setObjectName("stockModuleEditorGitFieldCombo")
        self.git_field_combo.setEnabled(False)
        self.git_field_combo.currentIndexChanged.connect(self._sync_git_object_edit_value)
        git_object_layout.addWidget(self.git_field_combo)
        self.git_value_edit = QtWidgets.QLineEdit(self.git_object_editor)
        self.git_value_edit.setObjectName("stockModuleEditorGitValueEdit")
        self.git_value_edit.setEnabled(False)
        git_object_layout.addWidget(self.git_value_edit, 1)
        self.git_preview_button = QtWidgets.QPushButton("Preview GIT Edit", self.git_object_editor)
        self.git_preview_button.setObjectName("stockModuleEditorGitPreviewEditButton")
        self.git_preview_button.setEnabled(False)
        self.git_preview_button.clicked.connect(self._preview_git_object_edit)
        git_object_layout.addWidget(self.git_preview_button)
        self.git_open_template_button = QtWidgets.QPushButton("Open Template", self.git_object_editor)
        self.git_open_template_button.setObjectName("stockModuleEditorGitOpenTemplateButton")
        self.git_open_template_button.setEnabled(False)
        self.git_open_template_button.clicked.connect(self._open_git_object_template)
        git_object_layout.addWidget(self.git_open_template_button)
        center_layout.addWidget(self.git_object_editor)
        self.template_editor = QtWidgets.QWidget(center)
        self.template_editor.setObjectName("stockModuleEditorTemplateEditor")
        template_layout = QtWidgets.QHBoxLayout(self.template_editor)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(6)
        self.template_field_combo = QtWidgets.QComboBox(self.template_editor)
        self.template_field_combo.setObjectName("stockModuleEditorTemplateFieldCombo")
        self.template_field_combo.setEnabled(False)
        self.template_field_combo.currentIndexChanged.connect(self._sync_template_edit_value)
        template_layout.addWidget(self.template_field_combo, 1)
        self.template_value_edit = QtWidgets.QLineEdit(self.template_editor)
        self.template_value_edit.setObjectName("stockModuleEditorTemplateValueEdit")
        self.template_value_edit.setEnabled(False)
        template_layout.addWidget(self.template_value_edit, 1)
        self.template_preview_button = QtWidgets.QPushButton("Preview Template Edit", self.template_editor)
        self.template_preview_button.setObjectName("stockModuleEditorTemplatePreviewEditButton")
        self.template_preview_button.setEnabled(False)
        self.template_preview_button.clicked.connect(self._preview_template_field_edit)
        template_layout.addWidget(self.template_preview_button)
        center_layout.addWidget(self.template_editor)
        self.metadata_editor = QtWidgets.QWidget(center)
        self.metadata_editor.setObjectName("stockModuleEditorMetadataEditor")
        metadata_layout = QtWidgets.QHBoxLayout(self.metadata_editor)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(6)
        self.metadata_field_combo = QtWidgets.QComboBox(self.metadata_editor)
        self.metadata_field_combo.setObjectName("stockModuleEditorMetadataFieldCombo")
        self.metadata_field_combo.setEnabled(False)
        self.metadata_field_combo.currentIndexChanged.connect(self._sync_metadata_edit_value)
        metadata_layout.addWidget(self.metadata_field_combo, 1)
        self.metadata_value_edit = QtWidgets.QLineEdit(self.metadata_editor)
        self.metadata_value_edit.setObjectName("stockModuleEditorMetadataValueEdit")
        self.metadata_value_edit.setEnabled(False)
        metadata_layout.addWidget(self.metadata_value_edit, 1)
        self.metadata_preview_button = QtWidgets.QPushButton("Preview Metadata Edit", self.metadata_editor)
        self.metadata_preview_button.setObjectName("stockModuleEditorMetadataPreviewEditButton")
        self.metadata_preview_button.setEnabled(False)
        self.metadata_preview_button.clicked.connect(self._preview_metadata_field_edit)
        metadata_layout.addWidget(self.metadata_preview_button)
        center_layout.addWidget(self.metadata_editor)
        self.logic_editor = QtWidgets.QWidget(center)
        self.logic_editor.setObjectName("stockModuleEditorLogicEditor")
        logic_layout = QtWidgets.QHBoxLayout(self.logic_editor)
        logic_layout.setContentsMargins(0, 0, 0, 0)
        logic_layout.setSpacing(6)
        self.logic_field_combo = QtWidgets.QComboBox(self.logic_editor)
        self.logic_field_combo.setObjectName("stockModuleEditorLogicFieldCombo")
        self.logic_field_combo.setEnabled(False)
        self.logic_field_combo.currentIndexChanged.connect(self._sync_logic_edit_value)
        logic_layout.addWidget(self.logic_field_combo, 1)
        self.logic_value_edit = QtWidgets.QLineEdit(self.logic_editor)
        self.logic_value_edit.setObjectName("stockModuleEditorLogicValueEdit")
        self.logic_value_edit.setEnabled(False)
        logic_layout.addWidget(self.logic_value_edit, 1)
        self.logic_preview_button = QtWidgets.QPushButton("Preview DLG Edit", self.logic_editor)
        self.logic_preview_button.setObjectName("stockModuleEditorLogicPreviewEditButton")
        self.logic_preview_button.setEnabled(False)
        self.logic_preview_button.clicked.connect(self._preview_logic_field_edit)
        logic_layout.addWidget(self.logic_preview_button)
        center_layout.addWidget(self.logic_editor)
        self.selection_label = QtWidgets.QLabel(center)
        self.selection_label.setObjectName("stockModuleEditorSelectionLabel")
        self.selection_label.setWordWrap(True)
        center_layout.addWidget(self.selection_label)
        self.edit_queue_preflight_label = QtWidgets.QLabel(center)
        self.edit_queue_preflight_label.setObjectName("stockModuleEditorEditQueuePreflight")
        self.edit_queue_preflight_label.setWordWrap(True)
        self.edit_queue_preflight_label.setText("Queued export preflight: no staged edits")
        center_layout.addWidget(self.edit_queue_preflight_label)
        self.edit_queue = QtWidgets.QListWidget(center)
        self.edit_queue.setObjectName("stockModuleEditorEditQueue")
        self.edit_queue.setUniformItemSizes(True)
        self.edit_queue.setAlternatingRowColors(True)
        self.edit_queue.setMaximumHeight(112)
        self.edit_queue.setToolTip("Staged edits that will be exported together into one copied module archive.")
        center_layout.addWidget(self.edit_queue)
        self.main_splitter.addWidget(center)

        self.details = QtWidgets.QTableWidget(self.main_splitter)
        self.details.setObjectName("stockModuleEditorResourceDetails")
        self.details.setColumnCount(2)
        self.details.setHorizontalHeaderLabels(["Field", "Value"])
        self.details.horizontalHeader().setStretchLastSection(True)
        self.details.verticalHeader().setVisible(False)
        self.details.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.details.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.details.itemSelectionChanged.connect(self._sync_selection_from_details)
        self.main_splitter.addWidget(self.details)

        self.main_splitter.setSizes([330, 660, 330])
        self.left_splitter.setSizes([330, 420])

        self.content_search.textChanged.connect(self._populate_content_browser)
        self.content_type_combo.currentTextChanged.connect(self._populate_content_browser)
        self._populate_empty_state()

    def open_module(self, path: str | Path) -> None:
        self._clear_room_board_hits()
        source_path = Path(path)
        package_tempdir: tempfile.TemporaryDirectory[str] | None = None
        extraction_dir: Path | None = None
        if source_path.suffix.lower() == ".zip":
            package_tempdir = tempfile.TemporaryDirectory(prefix="ghostrigger_module_package_")
            extraction_dir = Path(package_tempdir.name)
        try:
            prepared = prepare_module_open_path(source_path, extraction_dir)
            resources = read_module_archive_resources(prepared.module_path)
        except Exception:
            if package_tempdir is not None:
                package_tempdir.cleanup()
            raise

        self._release_module_package_tempdir()
        self._module_package_tempdir = package_tempdir
        self._module_path = prepared.module_path
        self._module_source_path = prepared.source_path
        self._module_source_label = prepared.source_label
        self._resources = resources
        self._imported_texture_resources.clear()
        self._texture_preview_cache.clear()
        self._texture_icon_cache.clear()
        self._material_inventory_cache.clear()
        self._wok_inventory_cache.clear()
        self._git_inventory_cache.clear()
        self._layout_inventory_cache.clear()
        self._logic_inventory_cache.clear()
        self._metadata_inventory_cache.clear()
        self._template_inventory_cache.clear()
        self._selected_material_slot = None
        self._pending_texture_replacement = None
        self._selected_tga_resource = None
        self._pending_tga_edit = None
        self._selected_txi_source_resource = None
        self._pending_txi_edit = None
        self._selected_wok_resource = None
        self._pending_wok_surface_paint = None
        self._selected_git_resource = None
        self._selected_git_inventory = None
        self._pending_git_object_edit = None
        self._selected_template_resource = None
        self._pending_template_field_edit = None
        self._selected_metadata_resource = None
        self._pending_metadata_field_edit = None
        self._selected_layout_resource = None
        self._pending_layout_edit = None
        self._selected_logic_resource = None
        self._pending_logic_field_edit = None
        self._staged_edits.clear()
        self._details_row_payloads.clear()
        self.setWindowTitle(f"Ghost-Studio Module Editor - {self._module_display_title(prepared)}")
        self._populate_outliner()
        self._populate_content_browser()
        self._populate_audit_details()
        self._clear_material_picker()
        self._clear_material_preview()
        self._clear_tga_editor()
        self._clear_txi_editor()
        self._clear_wok_surface_editor()
        self._clear_git_object_editor()
        self._clear_template_editor()
        self._clear_metadata_editor()
        self._clear_layout_editor()
        self._clear_logic_editor()
        self._refresh_edit_queue()
        self.preview_label.setText(f"{self._module_display_title(prepared)}\n{len(resources)} resources indexed")
        self.statusBar().showMessage(f"Opened {self._module_display_title(prepared)}: {len(resources)} resources.")

    def set_game_library(self, game_library: object, *, game: str = "K2", texture_limit: int | None = None) -> None:
        """Attach a scanned game library so its textures appear beside module resources."""

        self._game_library = game_library
        self._game_library_game = str(game or "K2").upper()
        self._game_texture_resources = self._discover_game_library_textures(game_library, self._game_library_game, texture_limit)
        self._texture_preview_cache.clear()
        self._texture_icon_cache.clear()
        self._populate_content_browser()
        self.statusBar().showMessage(
            f"Loaded {len(self._game_texture_resources)} {self._game_library_game} game-library texture references."
        )

    def _browse_open_module(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open KotOR module archive",
            "",
            "KotOR module archives (*.mod *.rim *.erf *.zip);;KotOR module packages (*.zip);;All files (*.*)",
        )
        if path:
            try:
                self.open_module(path)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._release_module_package_tempdir()
        super().closeEvent(event)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.preview_label and event.type() == QtCore.QEvent.MouseButtonRelease:
            if isinstance(event, QtGui.QMouseEvent) and event.button() == QtCore.Qt.LeftButton:
                position = event.position().toPoint() if hasattr(event, "position") else event.pos()
                board_position = self._room_board_position_from_label(position)
                if board_position is not None and self._select_room_board_slot_at(board_position):
                    return True
        return super().eventFilter(watched, event)

    def _browse_import_texture(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import replacement texture",
            "",
            "KotOR textures (*.tga *.tpc *.txi);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.import_texture(path)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))

    def import_texture(self, path: str | Path) -> ModuleTextureFileResource:
        """Add a local edited texture to this module-editing session."""

        texture_path = Path(path)
        if not texture_path.exists():
            raise FileNotFoundError(f"Texture does not exist: {texture_path}")
        restype = texture_path.suffix.lower().lstrip(".")
        restype_ids = {"tga": 3, "tpc": 3007, "txi": 2022}
        if restype not in restype_ids:
            raise ValueError("Imported texture must be a TGA, TPC, or TXI file.")
        resref = texture_path.stem.strip().lower()[:16]
        if not resref:
            raise ValueError("Imported texture filename must include a resource name.")
        resource = ModuleTextureFileResource(
            resref=resref,
            restype=restype,
            restype_id=restype_ids[restype],
            path=str(texture_path),
            size=texture_path.stat().st_size,
        )
        self._imported_texture_resources = [
            item for item in self._imported_texture_resources if item.label.lower() != resource.label.lower()
        ]
        self._imported_texture_resources.append(resource)
        self._texture_preview_cache.clear()
        self._texture_icon_cache.clear()
        if hasattr(self, "content_type_combo"):
            self.content_type_combo.setCurrentText("Textures")
        if hasattr(self, "content_search"):
            self.content_search.setText(resource.resref)
        self._populate_content_browser()
        for index in range(self.content_browser.count()):
            item = self.content_browser.item(index)
            if item is not None and item.data(QtCore.Qt.UserRole) == resource:
                self.content_browser.setCurrentItem(item)
                break
        if self._selected_material_slot is not None:
            if resource.restype in {"tga", "tpc"}:
                self._create_pending_texture_replacement(resource)
            elif (
                resource.restype == "txi"
                and self._pending_texture_replacement is not None
                and self._pending_texture_replacement.replacement_texture_resref == resource.resref
            ):
                replacement_resource = self._find_texture_resource(resource.resref)
                if replacement_resource is not None:
                    self._create_pending_texture_replacement(replacement_resource)
        self.statusBar().showMessage(f"Imported replacement texture {resource.label}.")
        return resource

    def _populate_empty_state(self) -> None:
        self._clear_room_board_hits()
        self.outliner.clear()
        root = QtWidgets.QTreeWidgetItem(["No module loaded", ""])
        self.outliner.addTopLevelItem(root)
        self.content_browser.clear()
        if hasattr(self, "material_picker"):
            self._clear_material_picker()
        if hasattr(self, "material_preview"):
            self._clear_material_preview()
        if hasattr(self, "tga_editor"):
            self._clear_tga_editor()
        if hasattr(self, "txi_editor"):
            self._clear_txi_editor()
        if hasattr(self, "wok_surface_editor"):
            self._clear_wok_surface_editor()
        if hasattr(self, "git_object_editor"):
            self._clear_git_object_editor()
        if hasattr(self, "template_editor"):
            self._clear_template_editor()
        if hasattr(self, "metadata_editor"):
            self._clear_metadata_editor()
        if hasattr(self, "layout_editor"):
            self._clear_layout_editor()
        if hasattr(self, "edit_queue"):
            self._refresh_edit_queue()
        if hasattr(self, "current_texture_preview"):
            self._clear_texture_compare()
        self.details.setRowCount(0)

    def _populate_outliner(self) -> None:
        self.outliner.clear()
        if not self._resources:
            self._populate_empty_state()
            return
        counts = Counter(item.restype for item in self._resources)
        module_root = QtWidgets.QTreeWidgetItem([
            self._module_path.name if self._module_path else "Module",
            str(len(self._resources)),
        ])
        module_root.setData(0, QtCore.Qt.UserRole, {"kind": "module"})
        self.outliner.addTopLevelItem(module_root)
        groups = [
            ("Layout and visibility", ROOM_TYPES),
            ("Textures and materials", TEXTURE_TYPES),
            ("Gameplay objects", GAMEPLAY_TYPES),
            ("Module metadata", MODULE_TYPES),
            ("Scripts and dialogue", LOGIC_TYPES),
            ("Other resources", set()),
        ]
        known = set().union(*(group for _label, group in groups if group))
        for label, restypes in groups:
            if restypes:
                group_resources = [item for item in self._resources if item.restype in restypes]
            else:
                group_resources = [item for item in self._resources if item.restype not in known]
            group_item = QtWidgets.QTreeWidgetItem([label, str(len(group_resources))])
            group_item.setData(0, QtCore.Qt.UserRole, {"kind": "group", "types": sorted(restypes)})
            module_root.addChild(group_item)
            for restype in sorted({item.restype for item in group_resources}):
                type_item = QtWidgets.QTreeWidgetItem([restype.upper(), str(counts[restype])])
                type_item.setData(0, QtCore.Qt.UserRole, {"kind": "type", "type": restype})
                group_item.addChild(type_item)
        self.outliner.expandItem(module_root)
        self.outliner.resizeColumnToContents(0)

    def _populate_content_browser(self) -> None:
        if not hasattr(self, "content_browser"):
            return
        query = self.content_search.text().strip().lower() if hasattr(self, "content_search") else ""
        category = self.content_type_combo.currentText() if hasattr(self, "content_type_combo") else "All"
        self.content_browser.clear()
        for resource in self._filtered_resources(query, category):
            safety = classify_module_resource(resource)
            item = QtWidgets.QListWidgetItem(self._resource_icon(resource), resource.label)
            tooltip_lines = [
                resource.label,
                self._resource_source_label(resource),
                f"{resource.size:,} bytes",
                f"{safety.edit_status}: {safety.workflow}",
                safety.export_policy,
            ]
            texture_pick_hint = self._texture_pick_hint(resource)
            if texture_pick_hint:
                tooltip_lines.append(texture_pick_hint)
            item.setToolTip("\n".join(tooltip_lines))
            item.setData(QtCore.Qt.UserRole, resource)
            self.content_browser.addItem(item)

    def _filtered_resources(self, query: str, category: str) -> list[BrowserResource]:
        category_types = {
            "Textures": TEXTURE_TYPES,
            "Rooms": ROOM_TYPES,
            "Gameplay": GAMEPLAY_TYPES,
            "Module": MODULE_TYPES,
            "Logic": LOGIC_TYPES,
        }.get(category, set())
        filter_directive = self._resource_filter_directive(query)
        result: list[BrowserResource] = []
        for resource in self._resources:
            if category_types and resource.restype not in category_types:
                continue
            if not self._resource_matches_query(resource, query, filter_directive):
                continue
            result.append(resource)
        if category in {"All", "Textures"}:
            for resource in self._imported_texture_resources:
                if not self._resource_matches_query(resource, query, filter_directive):
                    continue
                result.append(resource)
            for resource in self._game_texture_resources:
                if not self._resource_matches_query(resource, query, filter_directive):
                    continue
                result.append(resource)
        return result

    @staticmethod
    def _resource_filter_directive(query: str) -> tuple[str, str] | None:
        text = query.strip().lower()
        for prefix in ("status:", "scope:"):
            if text.startswith(prefix):
                value = text[len(prefix):].strip()
                if value:
                    return prefix[:-1], value
        return None

    def _resource_matches_query(
        self,
        resource: BrowserResource,
        query: str,
        filter_directive: tuple[str, str] | None,
    ) -> bool:
        if filter_directive is not None:
            kind, value = filter_directive
            safety = classify_module_resource(resource)
            if kind == "status":
                return safety.edit_status.lower() == value
            if kind == "scope":
                return safety.editable_scope.lower() == value
            return False
        if not query:
            return True
        return query in resource.label.lower() or query in self._resource_source_label(resource).lower()

    def _texture_pick_hint(self, resource: BrowserResource) -> str:
        slot = self._selected_material_slot
        if slot is None or resource.restype not in {"tga", "tpc"}:
            return ""
        replacement = str(resource.resref or "").strip()
        current = slot.texture_resref.strip()
        if not replacement or not current:
            return ""
        target = f"{slot.room_resref}.{slot.node_name} {slot.slot_kind}"
        if replacement.lower() == current.lower():
            return f"Current texture for {target}; choosing it leaves the replacement unchanged."
        return f"Click to preview replacing {target}: {current} -> {replacement}."

    def _resource_icon(self, resource: BrowserResource) -> QtGui.QIcon:
        if resource.restype in {"tga", "tpc"}:
            thumbnail = self._texture_icon(resource)
            if not thumbnail.isNull():
                return thumbnail
        pixmap = QtGui.QPixmap(72, 72)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        colors = {
            "tga": "#2f855a",
            "tpc": "#2b6cb0",
            "txi": "#805ad5",
            "mdl": "#b7791f",
            "mdx": "#975a16",
            "wok": "#718096",
            "lyt": "#0f766e",
            "vis": "#0369a1",
            "git": "#c53030",
            "are": "#047857",
            "ifo": "#7c3aed",
            "utc": "#b91c1c",
            "utp": "#a16207",
            "utd": "#4338ca",
            "utt": "#be185d",
            "uts": "#0891b2",
            "ute": "#c2410c",
            "utw": "#4d7c0f",
            "utm": "#047857",
            "uti": "#6d28d9",
            "pth": "#0e7490",
            "dlg": "#9333ea",
            "nss": "#15803d",
            "ncs": "#374151",
        }
        fill = QtGui.QColor(colors.get(resource.restype, "#2d3748"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
        painter.setBrush(QtGui.QBrush(fill))
        painter.drawRoundedRect(QtCore.QRectF(4, 4, 64, 64), 4, 4)
        painter.setPen(QtGui.QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(4, 18, 64, 24), QtCore.Qt.AlignCenter, resource.restype.upper())
        font.setPointSize(7)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(8, 42, 56, 18), QtCore.Qt.AlignCenter, f"{resource.size // 1024} KB")
        painter.end()
        return QtGui.QIcon(pixmap)

    def _texture_icon(self, resource: BrowserResource) -> QtGui.QIcon:
        key = self._resource_cache_key(resource, 72)
        cached = self._texture_icon_cache.get(key)
        if cached is not None:
            return cached
        preview = self._texture_preview(resource, max_size=72)
        if preview is None:
            return QtGui.QIcon()
        pixmap = self._pixmap_from_texture_preview(preview)
        tile = QtGui.QPixmap(72, 72)
        tile.fill(QtGui.QColor("#111827"))
        painter = QtGui.QPainter(tile)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        x = max(0, (72 - pixmap.width()) // 2)
        y = max(0, (72 - pixmap.height()) // 2)
        painter.drawPixmap(x, y, pixmap)
        painter.setPen(QtGui.QPen(QtGui.QColor("#e5e7eb"), 1))
        painter.drawRect(0, 0, 71, 71)
        painter.end()
        icon = QtGui.QIcon(tile)
        self._texture_icon_cache[key] = icon
        return icon

    def _texture_preview(self, resource: BrowserResource, *, max_size: int = 192) -> ModuleTexturePreview | None:
        key = self._resource_cache_key(resource, max_size)
        if key in self._texture_preview_cache:
            return self._texture_preview_cache[key]
        if resource.restype not in {"tga", "tpc"}:
            self._texture_preview_cache[key] = None
            return None
        try:
            data = self._texture_resource_bytes(resource)
            preview = decode_module_texture_preview(
                data,
                restype=resource.restype,
                label=resource.label,
                max_size=max_size,
            )
            if preview is None and isinstance(resource, ModuleTextureLibraryResource):
                fallback = "tga" if resource.restype == "tpc" else "tpc"
                preview = decode_module_texture_preview(
                    data,
                    restype=fallback,
                    label=resource.label,
                    max_size=max_size,
                )
        except Exception:
            preview = None
        self._texture_preview_cache[key] = preview
        return preview

    @staticmethod
    def _pixmap_from_texture_preview(preview: ModuleTexturePreview) -> QtGui.QPixmap:
        qimage = QtGui.QImage(
            preview.rgba,
            preview.preview_width,
            preview.preview_height,
            preview.preview_width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        return QtGui.QPixmap.fromImage(qimage)

    def _populate_audit_details(self) -> None:
        counts = Counter(item.restype for item in self._resources)
        safety_counts = summarize_resource_safety(self._resources)
        scope_counts = summarize_resource_safety_scopes(self._resources)
        row_payloads: dict[int, object] = {}
        rows: list[tuple[str, str]] = [
            ("Archive", str(self._module_path or "")),
            ("Source package", self._module_source_label or str(self._module_source_path or "")),
            ("Opened module path", str(self._module_path or "")),
            ("Resources", str(len(self._resources))),
            ("Texture resources", str(sum(counts[item] for item in TEXTURE_TYPES))),
            ("Room/model resources", str(sum(counts[item] for item in ROOM_TYPES))),
            ("Gameplay resources", str(sum(counts[item] for item in GAMEPLAY_TYPES))),
            ("Metadata resources", str(sum(counts[item] for item in MODULE_TYPES))),
            ("Logic resources", str(sum(counts[item] for item in LOGIC_TYPES))),
        ]
        for status in ("editable now", "partial editor", "inspect/list-only", "preserve-only"):
            row_payloads[len(rows)] = ModuleAuditFilterTarget("status", status)
            rows.append((f"{status.capitalize()} resources", str(safety_counts.get(status, 0))))
        rows.extend(
            [
                ("Editable now", "TGA/TPC/TXI texture replacement, WOK faces, LYT/VIS layout links, GIT objects, templates, ARE/IFO metadata, DLG top-level fields"),
                ("Next editing gate", "PTH graph editing, nested DLG tree editing, NSS compile/decompile checks, and visible Debug-app workflow proof"),
            ]
        )
        for scope, count in sorted(scope_counts.items()):
            row_payloads[len(rows)] = ModuleAuditFilterTarget("scope", scope)
            rows.append((f"Scope {scope}", str(count)))
        for restype, count in sorted(counts.items()):
            rows.append((restype.upper(), str(count)))
        self._set_details(rows, row_payloads=row_payloads)

    def _release_module_package_tempdir(self) -> None:
        if self._module_package_tempdir is not None:
            self._module_package_tempdir.cleanup()
            self._module_package_tempdir = None

    @staticmethod
    def _module_display_title(prepared: PreparedModuleOpenPath) -> str:
        if prepared.member_name is None:
            return prepared.display_name
        return f"{prepared.source_path.name} / {prepared.display_name}"

    def _module_export_default_path(self, edit_suffix: str) -> Path:
        if self._module_path is None:
            return Path(f"module_{edit_suffix}.mod")
        base_dir = self._module_path.parent
        if self._module_source_path is not None and self._module_source_path.suffix.lower() == ".zip":
            base_dir = self._module_source_path.parent
        stem = self._module_path.stem
        suffix = self._module_path.suffix or ".mod"
        clean_suffix = str(edit_suffix).strip("_")
        return base_dir / f"{stem}_{clean_suffix}{suffix}"

    def _sync_selection_from_outliner(self) -> None:
        item = self.outliner.currentItem()
        data = item.data(0, QtCore.Qt.UserRole) if item is not None else None
        if isinstance(data, dict) and data.get("kind") == "type":
            restype = str(data.get("type", ""))
            self.content_type_combo.setCurrentText("All")
            self.content_search.setText(f".{restype}")

    def _select_audit_filter_target(self, target: ModuleAuditFilterTarget, *, source: str) -> None:
        self.content_type_combo.setCurrentText("All")
        self.content_search.setText(f"{target.kind}:{target.value}")
        self._populate_content_browser()
        count = self.content_browser.count() if hasattr(self, "content_browser") else 0
        self.selection_label.setText(f"Filtered resources by {target.kind} {target.value} from {source}")
        self.statusBar().showMessage(f"Showing {count} resource(s) for {target.kind} {target.value}.")

    def _sync_selection_from_content_browser(self) -> None:
        self._clear_room_board_hits()
        item = self.content_browser.currentItem()
        resource = item.data(QtCore.Qt.UserRole) if item is not None else None
        if not isinstance(resource, (ModuleArchiveResource, ModuleTextureFileResource, ModuleTextureLibraryResource, ModuleTextureMemoryResource)):
            return
        if resource.restype == "tga":
            self._selected_tga_resource = resource
            self._pending_tga_edit = None
            self._populate_tga_editor(resource)
        else:
            self._selected_tga_resource = None
            self._pending_tga_edit = None
            self._clear_tga_editor()
        if resource.restype in {"tga", "tpc", "txi"}:
            self._selected_txi_source_resource = resource
            self._pending_txi_edit = None
            self._populate_txi_editor(resource)
        else:
            self._selected_txi_source_resource = None
            self._pending_txi_edit = None
            self._clear_txi_editor()
        if resource.restype != "wok":
            self._selected_wok_resource = None
            self._pending_wok_surface_paint = None
            self._clear_wok_surface_editor()
        if resource.restype != "git":
            self._selected_git_resource = None
            self._selected_git_inventory = None
            self._pending_git_object_edit = None
            self._clear_git_object_editor()
        if resource.restype not in GAMEPLAY_TYPES:
            self._selected_template_resource = None
            self._pending_template_field_edit = None
            self._clear_template_editor()
        if resource.restype not in {"are", "ifo"}:
            self._selected_metadata_resource = None
            self._pending_metadata_field_edit = None
            self._clear_metadata_editor()
        if resource.restype not in {"lyt", "vis"}:
            self._selected_layout_resource = None
            self._pending_layout_edit = None
            self._clear_layout_editor()
        if resource.restype not in LOGIC_TYPES:
            self._selected_logic_resource = None
            self._pending_logic_field_edit = None
            self._clear_logic_editor()
        rows = [
            ("Resource", resource.label),
            ("Type id", str(resource.restype_id)),
            ("Offset", str(getattr(resource, "offset", "n/a"))),
            ("Size", f"{resource.size:,} bytes"),
            ("Source", self._resource_source_label(resource)),
        ]
        safety = classify_module_resource(resource)
        rows.extend(
            [
                ("Edit status", safety.edit_status),
                ("Safety policy", safety.safety_policy),
                ("Export policy", safety.export_policy),
            ]
        )
        row_payloads: dict[int, object] = {}
        if resource.restype in TEXTURE_TYPES:
            rows.append(("Texture workflow", "thumbnail preview and material replacement target"))
            preview = self._texture_preview(resource, max_size=384)
            if preview is not None:
                rows.extend(
                    [
                        ("Dimensions", f"{preview.width} x {preview.height}"),
                        ("Preview", f"{preview.preview_width} x {preview.preview_height}"),
                    ]
                )
                self.preview_label.setPixmap(self._pixmap_from_texture_preview(preview))
                self.preview_label.setToolTip(resource.label)
            elif resource.restype in {"txi", "txt"} and (
                isinstance(resource, (ModuleTextureFileResource, ModuleTextureMemoryResource))
                or (self._module_path is not None and isinstance(resource, ModuleArchiveResource))
            ):
                try:
                    text = self._texture_resource_bytes(resource).decode("latin-1", errors="replace")
                except Exception:
                    text = ""
                self.preview_label.setText(text[:4000] or resource.label)
            else:
                self.preview_label.setText(resource.label)
            usage_slots = self._texture_usage_slots(resource.resref)
            if usage_slots:
                rows.append(("Material uses", f"{len(usage_slots)} slot(s) reference {resource.resref}"))
                for slot in usage_slots[:16]:
                    row_index = len(rows)
                    rows.append(
                        (
                            f"Used by {slot.room_resref}.{slot.node_name}",
                            f"{slot.slot_kind}; {slot.face_count} faces, {slot.vertex_count} verts",
                        )
                    )
                    row_payloads[row_index] = slot
                if len(usage_slots) > 16:
                    rows.append(("More texture uses", f"{len(usage_slots) - 16} additional material slots"))
            else:
                rows.append(("Material uses", "No parsed room material slots currently reference this texture"))
            if resource.restype in {"tga", "tpc"} and self._selected_material_slot is not None:
                draft = self._create_pending_texture_replacement(resource)
                if draft is not None:
                    rows.extend(self._texture_replacement_rows(draft))
                    self._show_room_material_board_for_slot(draft.target)
        elif resource.restype == "wok":
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_wok_resource = resource
            self._pending_wok_surface_paint = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._wok_inventory(resource)
            self._populate_wok_surface_editor(inventory)
            rows.append(("Walkmesh workflow", "face selection and surface painting target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append(("WOK parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("WOK warning", inventory.warning))
            rows.append(("Vertices", str(inventory.vertex_count)))
            rows.append(("Faces", str(inventory.face_count)))
            rows.append(("Walkable faces", str(inventory.walkable_face_count)))
            rows.append(("Non-walk faces", str(inventory.non_walk_face_count)))
            rows.append(("Boundary edges", str(inventory.boundary_edge_count)))
            rows.append(("Door/transition faces", str(inventory.transition_face_count)))
            for surface in inventory.surfaces[:12]:
                row_index = len(rows)
                rows.append(
                    (
                        f"Surface {surface.surface_id} {surface.surface_name}",
                        f"{surface.face_count} faces; {'walkable' if surface.walkable else 'blocked'}",
                    )
                )
                row_payloads[row_index] = surface
            if len(inventory.surfaces) > 12:
                rows.append(("More WOK surfaces", f"{len(inventory.surfaces) - 12} additional surface rows"))
            for issue in inventory.issue_summary:
                rows.append(("WOK validation", issue))
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        elif resource.restype == "mdl":
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_preview()
            inventory = self._room_material_inventory(resource)
            self._populate_material_picker(inventory)
            self._populate_material_pick_panel(inventory)
            row_payloads: dict[int, object] = {}
            overrides = self._texture_preview_overrides_for_room(inventory)
            rows.append(("Room material workflow", "select mesh/material slot first; per-face splitting is later"))
            rows.append(("Material parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("Material warning", inventory.warning))
            rows.append(("Material slots", str(len(inventory.slots))))
            rows.append(("Referenced textures", ", ".join(inventory.unique_textures[:12]) or "(none)"))
            if overrides:
                rows.append(("Session texture overrides", f"{len(overrides)} material slot(s) previewed in this room"))
                for override in overrides[:12]:
                    rows.append(
                        (
                            f"Preview {override.source_slot.node_name} {override.source_slot.slot_kind}",
                            f"{override.original_texture_resref} -> {override.preview_texture_resref} ({override.status})",
                        )
                    )
                if len(overrides) > 12:
                    rows.append(("More texture overrides", f"{len(overrides) - 12} additional previewed slots"))
            dependencies = summarize_texture_dependencies(
                inventory,
                self._available_texture_resources(),
                overrides,
            )
            if dependencies:
                resolved_count = sum(1 for dependency in dependencies if dependency.source_status == "resolved")
                missing_count = len(dependencies) - resolved_count
                rows.append(("Texture dependencies", f"{resolved_count} resolved, {missing_count} missing"))
                for dependency in dependencies[:12]:
                    rows.append((f"Dependency {dependency.texture_resref}", dependency.summary))
                    if dependency.overridden_slot_count:
                        rows.append(
                            (
                                f"Effective {dependency.texture_resref}",
                                f"{dependency.effective_texture_resref} from {dependency.effective_source_label}",
                            )
                        )
                if len(dependencies) > 12:
                    rows.append(("More texture dependencies", f"{len(dependencies) - 12} additional texture rows"))
            for usage in summarize_texture_usage(inventory)[:12]:
                rows.append(
                    (
                        f"Texture {usage.texture_resref}",
                        f"{usage.slot_count} {usage.slot_kind} slot(s); {usage.face_count} faces, {usage.vertex_count} verts",
                    )
                )
            for slot in inventory.slots[:12]:
                override = texture_preview_for_slot(slot, overrides)
                value = f"{slot.texture_resref} ({slot.face_count} faces, {slot.vertex_count} verts)"
                if override is not None:
                    value = (
                        f"{slot.texture_resref} -> {override.preview_texture_resref} "
                        f"({override.status}; {slot.face_count} faces, {slot.vertex_count} verts)"
                    )
                row_index = len(rows)
                rows.append(
                    (
                        f"{slot.node_name} {slot.slot_kind}",
                        value,
                    )
                )
                row_payloads[row_index] = slot
            if len(inventory.slots) > 12:
                rows.append(("More material slots", f"{len(inventory.slots) - 12} additional slots"))
            self._show_room_material_board(inventory, self._selected_material_slot)
            self._set_details(rows, row_payloads=row_payloads)
            self.selection_label.setText(f"Selected {resource.label}")
            self._update_export_action_enabled()
            return
        elif resource.restype == "git":
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_git_resource = resource
            self._pending_git_object_edit = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._git_inventory(resource)
            self._populate_git_object_editor(inventory)
            rows.append(("GIT workflow", "placed object forms and template-reference editing target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append(("GIT parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("GIT warning", inventory.warning))
            rows.append(("Placed object forms", str(inventory.total_objects)))
            for count in inventory.counts:
                rows.append((f"{count.object_type.title()} count", f"{count.count} {count.template_type}".strip()))
            for obj in inventory.objects[:16]:
                label = f"{obj.object_type}.{obj.index}"
                value = obj.template_resref or obj.tag or "(unnamed)"
                if obj.tag and obj.tag != value:
                    value = f"{value} tag={obj.tag}"
                x, y, z = obj.position
                row_index = len(rows)
                rows.append((label, f"{value} at {x:.2f}, {y:.2f}, {z:.2f}; fields={obj.field_count}"))
                row_payloads[row_index] = obj
            if len(inventory.objects) > 16:
                rows.append(("More GIT objects", f"{len(inventory.objects) - 16} additional object rows"))
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        elif resource.restype in {"lyt", "vis"}:
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_layout_resource = resource
            self._pending_layout_edit = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._layout_inventory(resource)
            self._populate_layout_editor(inventory)
            rows.append(("Layout workflow", "room placement and visibility graph editing target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append((f"{resource.restype.upper()} parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("Layout warning", inventory.warning))
            if resource.restype == "lyt":
                rows.append(("Rooms", str(inventory.room_count)))
                rows.append(("Doorhooks", str(len(inventory.doorhooks))))
                rows.append(("Unparsed layout lines", str(inventory.other_line_count)))
                for room in inventory.rooms[:16]:
                    x, y, z = room.position
                    row_index = len(rows)
                    rows.append((f"Room {room.room_resref}", f"{x:.2f}, {y:.2f}, {z:.2f}"))
                    row_payloads[row_index] = room
                if len(inventory.rooms) > 16:
                    rows.append(("More LYT rooms", f"{len(inventory.rooms) - 16} additional rooms"))
                for hook in inventory.doorhooks[:8]:
                    x, y, z = hook.position
                    qx, qy, qz, qw = hook.rotation
                    rows.append((f"Doorhook {hook.hook_name}", f"{x:.2f}, {y:.2f}, {z:.2f}; q={qx:.2f}, {qy:.2f}, {qz:.2f}, {qw:.2f}"))
                if len(inventory.doorhooks) > 8:
                    rows.append(("More doorhooks", f"{len(inventory.doorhooks) - 8} additional hooks"))
            else:
                rows.append(("VIS rooms", str(inventory.visibility_entry_count)))
                rows.append(("Visibility links", str(inventory.visibility_link_count)))
                rows.append(("Missing visibility targets", ", ".join(inventory.missing_visibility_targets) or "(none)"))
                rows.append(("Layout rooms missing VIS", ", ".join(inventory.unlisted_layout_rooms) or "(none)"))
                for entry in inventory.visibility[:16]:
                    row_index = len(rows)
                    rows.append((f"Visible from {entry.room_resref}", ", ".join(entry.visible_rooms[:12]) or "(none)"))
                    row_payloads[row_index] = entry
                if len(inventory.visibility) > 16:
                    rows.append(("More VIS rooms", f"{len(inventory.visibility) - 16} additional rooms"))
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        elif resource.restype in {"are", "ifo"}:
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_metadata_resource = resource
            self._pending_metadata_field_edit = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._metadata_inventory(resource)
            self._populate_metadata_editor(inventory)
            rows.append(("Metadata workflow", "area/module metadata inspection and override target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append((f"{resource.restype.upper()} parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("Metadata warning", inventory.warning))
            for field in inventory.fields:
                row_index = len(rows)
                rows.append((field.label, field.value))
                row_payloads[row_index] = field
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        elif resource.restype in LOGIC_TYPES:
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_logic_resource = resource
            self._pending_logic_field_edit = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._logic_inventory(resource)
            self._populate_logic_editor(inventory)
            rows.append(("Logic workflow", "path/dialogue/script inspection, DLG top-level edits, dependency checks, and list-preserving export target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append(("Resource kind", inventory.resource_kind or resource.restype.upper()))
            rows.append((f"{resource.restype.upper()} parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("Logic warning", inventory.warning))
            rows.append(("Bytes", str(inventory.byte_size)))
            if inventory.line_count:
                rows.append(("Lines", str(inventory.line_count)))
            if inventory.raw_field_count:
                rows.append(("Raw GFF fields", str(inventory.raw_field_count)))
            for field in inventory.fields:
                row_index = len(rows)
                rows.append((field.label, field.value))
                row_payloads[row_index] = field
            for list_summary in inventory.list_summaries[:12]:
                rows.append((f"{list_summary.label} list", str(list_summary.count)))
            if len(inventory.list_summaries) > 12:
                rows.append(("More logic lists", f"{len(inventory.list_summaries) - 12} additional lists"))
            if inventory.references:
                rows.append(("References", str(len(inventory.references))))
                rows.append(("Missing references", str(inventory.missing_reference_count)))
            for reference in inventory.references[:16]:
                rows.append((f"Reference {reference.status}", reference.label))
            if len(inventory.references) > 16:
                rows.append(("More references", f"{len(inventory.references) - 16} additional references"))
            if inventory.text_preview:
                rows.append(("Preview", inventory.text_preview[:240]))
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        elif resource.restype in GAMEPLAY_TYPES:
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self._selected_template_resource = resource
            self._pending_template_field_edit = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            inventory = self._template_inventory(resource)
            self._populate_template_editor(inventory)
            rows.append(("Gameplay workflow", "template form inspection and override target"))
            rows.append(("Editable scope", inventory.editable_scope))
            rows.append(("Template kind", inventory.template_kind or resource.restype.upper()))
            rows.append((f"{resource.restype.upper()} parse", inventory.parse_status))
            if inventory.warning:
                rows.append(("Template warning", inventory.warning))
            rows.append(("Raw GFF fields", str(inventory.raw_field_count)))
            for field in inventory.fields:
                row_index = len(rows)
                rows.append((field.label, field.value))
                row_payloads[row_index] = field
            for list_summary in inventory.list_summaries[:12]:
                rows.append((f"{list_summary.label} list", str(list_summary.count)))
            if len(inventory.list_summaries) > 12:
                rows.append(("More template lists", f"{len(inventory.list_summaries) - 12} additional lists"))
            self.preview_label.setText(f"{resource.label}\n{inventory.summary}\n{inventory.parse_status}")
        else:
            self._selected_material_slot = None
            self._pending_texture_replacement = None
            self.save_copy_action.setEnabled(False)
            self._clear_material_picker()
            self._clear_material_preview()
            rows.append(("Preserve/list-only workflow", safety.workflow))
            rows.append(("Editable scope", safety.editable_scope))
            self.preview_label.setText(f"{resource.label}\n{safety.edit_status}\n{safety.safety_policy}")
        self._set_details(rows, row_payloads=row_payloads)
        self.selection_label.setText(f"Selected {resource.label}")
        self._update_export_action_enabled()

    def _room_material_inventory(self, resource: ModuleArchiveResource) -> ModuleRoomMaterialInventory:
        cached = self._material_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleRoomMaterialInventory(resource.resref, (), "not_loaded", "No module archive is open.")
        else:
            inventory = inspect_module_room_materials(self._module_path, self._resources, resource)
        self._material_inventory_cache[resource.label] = inventory
        return inventory

    def _wok_inventory(self, resource: ModuleArchiveResource) -> ModuleWokInventory:
        cached = self._wok_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleWokInventory(resource.resref, "not_loaded", warning="No module archive is open.")
        else:
            inventory = inspect_module_wok(self._module_path, resource)
        self._wok_inventory_cache[resource.label] = inventory
        return inventory

    def _git_inventory(self, resource: ModuleArchiveResource) -> ModuleGitInventory:
        cached = self._git_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleGitInventory(resource.resref, "not_loaded", warning="No module archive is open.")
        else:
            inventory = inspect_module_git(self._module_path, resource)
        self._git_inventory_cache[resource.label] = inventory
        return inventory

    def _layout_inventory(self, resource: ModuleArchiveResource) -> ModuleLayoutInventory:
        cached = self._layout_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleLayoutInventory(
                resource.resref,
                resource.restype,
                "not_loaded",
                warning="No module archive is open.",
            )
        else:
            inventory = inspect_module_layout(self._module_path, self._resources, resource)
        self._layout_inventory_cache[resource.label] = inventory
        return inventory

    def _logic_inventory(self, resource: ModuleArchiveResource) -> ModuleLogicInventory:
        cached = self._logic_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleLogicInventory(
                resource.resref,
                resource.restype,
                "not_loaded",
                warning="No module archive is open.",
            )
        else:
            inventory = inspect_module_logic(self._module_path, resource, self._resources)
        self._logic_inventory_cache[resource.label] = inventory
        return inventory

    def _metadata_inventory(self, resource: ModuleArchiveResource) -> ModuleMetadataInventory:
        cached = self._metadata_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleMetadataInventory(
                resource.resref,
                resource.restype,
                "not_loaded",
                warning="No module archive is open.",
            )
        else:
            inventory = inspect_module_metadata(self._module_path, resource)
        self._metadata_inventory_cache[resource.label] = inventory
        return inventory

    def _template_inventory(self, resource: ModuleArchiveResource) -> ModuleTemplateInventory:
        cached = self._template_inventory_cache.get(resource.label)
        if cached is not None:
            return cached
        if self._module_path is None:
            inventory = ModuleTemplateInventory(
                resource.resref,
                resource.restype,
                "not_loaded",
                warning="No module archive is open.",
            )
        else:
            inventory = inspect_module_template(self._module_path, resource)
        self._template_inventory_cache[resource.label] = inventory
        return inventory

    def _texture_preview_overrides_for_room(self, inventory: ModuleRoomMaterialInventory) -> tuple[object, ...]:
        staged = tuple(
            draft
            for draft in self._staged_edits
            if isinstance(draft, ModuleTextureReplacementDraft)
            and draft.target.room_resref.lower() == inventory.room_resref.lower()
        )
        pending: tuple[ModuleTextureReplacementDraft, ...] = ()
        if (
            self._pending_texture_replacement is not None
            and self._pending_texture_replacement.target.room_resref.lower() == inventory.room_resref.lower()
        ):
            pending = (self._pending_texture_replacement,)
        return summarize_texture_preview_overrides(
            inventory,
            staged + pending,
            staged_count=len(staged),
        )

    def _available_texture_resources(self) -> tuple[BrowserResource, ...]:
        resources: list[BrowserResource] = [
            resource for resource in self._resources if resource.restype in {"tga", "tpc"}
        ]
        resources.extend(
            resource
            for resource in self._imported_texture_resources
            if resource.restype in {"tga", "tpc"}
        )
        resources.extend(self._game_texture_resources)
        return tuple(resources)

    def _room_material_inventory_by_resref(self, room_resref: str) -> ModuleRoomMaterialInventory | None:
        wanted = str(room_resref or "").strip().lower()
        if not wanted:
            return None
        for resource in self._resources:
            if resource.restype == "mdl" and resource.resref.lower() == wanted:
                return self._room_material_inventory(resource)
        return self._material_inventory_cache.get(f"{wanted}.mdl")

    def _refresh_material_views_for_room(self, room_resref: str) -> None:
        inventory = self._room_material_inventory_by_resref(room_resref)
        if inventory is None:
            return
        self._populate_material_picker(inventory)
        self._populate_material_pick_panel(inventory)
        if self._selected_material_slot is not None:
            self._sync_material_slot_selection(self._selected_material_slot)
        self._show_room_material_board(inventory, self._selected_material_slot)

    def _material_filter_changed(self, _text: str) -> None:
        inventory = self._room_board_inventory
        if inventory is None:
            return
        self._room_board_page_by_room[self._room_board_page_key(inventory)] = 0
        self._populate_material_picker(inventory)
        self._populate_material_pick_panel(inventory)
        if self._selected_material_slot is not None:
            self._sync_material_slot_selection(self._selected_material_slot)
        self._show_room_material_board(inventory, self._selected_slot_on_current_room_board_page(inventory))

    def _material_filter_query(self) -> str:
        if not hasattr(self, "material_filter_edit"):
            return ""
        return self.material_filter_edit.text().strip().lower()

    def _room_board_page_key(self, inventory: ModuleRoomMaterialInventory) -> str:
        return f"{inventory.room_resref.lower()}\0{self._material_filter_query()}"

    def _filtered_material_slots(self, inventory: ModuleRoomMaterialInventory) -> tuple[ModuleRoomTextureSlot, ...]:
        query = self._material_filter_query()
        if not query:
            return tuple(inventory.slots)
        return tuple(slot for slot in inventory.slots if self._material_slot_matches_filter(slot, query))

    @staticmethod
    def _material_slot_matches_filter(slot: ModuleRoomTextureSlot, query: str) -> bool:
        haystack = " ".join(
            (
                slot.room_resref,
                slot.node_name,
                slot.slot_kind,
                slot.texture_resref,
            )
        ).lower()
        return query in haystack

    def _create_pending_texture_replacement(
        self,
        texture_resource: BrowserResource,
    ) -> ModuleTextureReplacementDraft | None:
        slot = self._selected_material_slot
        if slot is None:
            return None
        replacement_resref = str(texture_resource.resref or "").strip().lower()
        if replacement_resref == slot.texture_resref.strip().lower():
            self._pending_texture_replacement = None
            self.save_copy_action.setEnabled(False)
            self._update_export_action_enabled()
            self._refresh_material_views_for_room(slot.room_resref)
            self._update_material_preview()
            self._update_texture_compare()
            self.statusBar().showMessage(
                f"{texture_resource.label} is already assigned to {slot.room_resref}.{slot.node_name}; choose a different TGA/TPC texture."
            )
            return None
        try:
            draft = create_texture_replacement_draft(
                slot,
                texture_resource,
                sidecar_resources=self._matching_imported_texture_sidecars(texture_resource),
            )
        except Exception as exc:
            self._pending_texture_replacement = None
            self.save_copy_action.setEnabled(False)
            self._update_export_action_enabled()
            self._refresh_material_views_for_room(slot.room_resref)
            self._update_material_preview()
            self._update_texture_compare()
            self.statusBar().showMessage(str(exc))
            return None
        self._pending_texture_replacement = draft
        self._pending_wok_surface_paint = None
        self._pending_git_object_edit = None
        self._pending_template_field_edit = None
        self._pending_metadata_field_edit = None
        self._pending_layout_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(True)
        self._update_export_action_enabled()
        self._refresh_material_views_for_room(draft.target.room_resref)
        self._update_material_preview()
        self._update_texture_compare(texture_resource)
        self.statusBar().showMessage(f"Previewing {draft.summary}")
        return draft

    def _populate_material_picker(self, inventory: ModuleRoomMaterialInventory) -> None:
        self.material_filter_edit.setEnabled(bool(inventory.slots))
        blocker = QtCore.QSignalBlocker(self.material_picker)
        try:
            self.material_picker.clear()
            slots = self._filtered_material_slots(inventory)
            self.material_picker.setEnabled(bool(slots))
            self.material_picker.setToolTip(
                f"{inventory.room_resref}: {len(slots)} of {len(inventory.slots)} material slots shown"
            )
            overrides = self._texture_preview_overrides_for_room(inventory)
            for slot in slots:
                override = texture_preview_for_slot(slot, overrides)
                texture_label = slot.texture_resref
                override_line = ""
                if override is not None:
                    texture_label = f"{slot.texture_resref} -> {override.preview_texture_resref} [{override.status}]"
                    override_line = (
                        f"\nSession preview: {slot.texture_resref} -> {override.preview_texture_resref}"
                        f" ({override.status}; {override.source_label})"
                    )
                item = QtWidgets.QListWidgetItem(
                    f"{slot.node_name}  {slot.slot_kind}: {texture_label}  "
                    f"({slot.face_count} faces, {slot.vertex_count} verts)"
                )
                item.setData(QtCore.Qt.UserRole, slot)
                item.setToolTip(
                    f"{slot.room_resref}.{slot.node_name}\n"
                    f"{slot.slot_kind}: {slot.texture_resref}\n"
                    f"{slot.face_count} faces, {slot.vertex_count} vertices"
                    f"{override_line}"
                )
                self.material_picker.addItem(item)
        finally:
            del blocker

    def _populate_material_pick_panel(self, inventory: ModuleRoomMaterialInventory) -> None:
        blocker = QtCore.QSignalBlocker(self.material_pick_panel)
        try:
            self.material_pick_panel.clear()
            slots = self._filtered_material_slots(inventory)
            self.material_pick_panel.setEnabled(bool(slots))
            self.material_pick_panel.setToolTip(
                f"{inventory.room_resref}: click a mesh/material target to inspect its texture; {len(slots)} of {len(inventory.slots)} shown"
            )
            overrides = self._texture_preview_overrides_for_room(inventory)
            for index, slot in enumerate(slots, start=1):
                override = texture_preview_for_slot(slot, overrides)
                effective_texture = override.preview_texture_resref if override is not None else slot.texture_resref
                texture_resource = self._find_texture_resource(effective_texture)
                icon = self._texture_icon(texture_resource) if texture_resource is not None else self._material_slot_icon(index)
                text = f"{slot.node_name}\n{effective_texture}"
                if override is not None:
                    text = f"{slot.node_name}\n{slot.texture_resref} -> {effective_texture}"
                item = QtWidgets.QListWidgetItem(icon, text)
                item.setData(QtCore.Qt.UserRole, slot)
                override_line = ""
                if override is not None:
                    override_line = (
                        f"\nSession preview: {slot.texture_resref} -> {override.preview_texture_resref}"
                        f" ({override.status}; {override.source_label})"
                    )
                item.setToolTip(
                    f"{slot.room_resref}.{slot.node_name}\n"
                    f"{slot.slot_kind}: {slot.texture_resref}\n"
                    f"{slot.face_count} faces, {slot.vertex_count} vertices"
                    f"{override_line}"
                )
                self.material_pick_panel.addItem(item)
        finally:
            del blocker

    def _show_room_material_board_for_slot(self, slot: ModuleRoomTextureSlot) -> None:
        inventory = self._room_material_inventory_by_resref(slot.room_resref)
        if inventory is not None:
            self._show_room_material_board(inventory, slot)

    def _show_room_material_board(
        self,
        inventory: ModuleRoomMaterialInventory,
        selected_slot: ModuleRoomTextureSlot | None = None,
    ) -> None:
        self._room_board_hit_slots.clear()
        self._room_board_inventory = inventory
        visible_slots = self._filtered_material_slots(inventory)
        self._room_board_visible_slot_count = len(visible_slots)
        if not visible_slots:
            reason = "No parsed room material slots."
            if inventory.slots and self._material_filter_query():
                reason = f"No material slots match '{self.material_filter_edit.text().strip()}'."
            self.preview_label.setText(
                f"{inventory.room_resref}\n"
                f"{inventory.parse_status}\n"
                f"{reason}"
            )
            self.preview_label.setToolTip(inventory.warning or inventory.parse_status)
            self.preview_label.setCursor(QtCore.Qt.ArrowCursor)
            self._set_room_board_navigation(0, 0, 0, 0)
            return

        page_size = 12
        page_count = max(1, (len(visible_slots) + page_size - 1) // page_size)
        page_key = self._room_board_page_key(inventory)
        page_index = max(0, min(self._room_board_page_by_room.get(page_key, 0), page_count - 1))
        if selected_slot is not None:
            selected_index = self._material_slot_index(inventory, selected_slot, visible_slots)
            if selected_index is not None:
                page_index = selected_index // page_size
        self._room_board_page_by_room[page_key] = page_index
        page_start = page_index * page_size
        page_slots = visible_slots[page_start:page_start + page_size]

        pixmap = QtGui.QPixmap(760, 420)
        palette = self.palette()
        background = palette.color(QtGui.QPalette.Window)
        foreground = palette.color(QtGui.QPalette.WindowText)
        muted = palette.color(QtGui.QPalette.PlaceholderText)
        highlight = palette.color(QtGui.QPalette.Highlight)
        base = palette.color(QtGui.QPalette.Base)
        alternate = palette.color(QtGui.QPalette.AlternateBase)
        pixmap.fill(background)

        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            header_font = QtGui.QFont(painter.font())
            header_font.setBold(True)
            header_font.setPointSize(max(10, header_font.pointSize() + 2))
            painter.setFont(header_font)
            painter.setPen(foreground)
            painter.drawText(18, 30, f"{inventory.room_resref} material targets")

            body_font = QtGui.QFont(painter.font())
            body_font.setBold(False)
            body_font.setPointSize(max(8, body_font.pointSize() - 1))
            painter.setFont(body_font)
            painter.setPen(muted)
            textures = ", ".join(inventory.unique_textures[:6]) or "(none)"
            if len(inventory.unique_textures) > 6:
                textures = f"{textures}, +{len(inventory.unique_textures) - 6}"
            page_end = min(len(visible_slots), page_start + len(page_slots))
            filter_note = f" filtered by '{self.material_filter_edit.text().strip()}'" if self._material_filter_query() else ""
            painter.drawText(18, 52, f"{page_start + 1}-{page_end} of {len(visible_slots)} slots{filter_note} | textures: {textures}")

            overrides = self._texture_preview_overrides_for_room(inventory)
            columns = 4
            tile_width = 176
            tile_height = 106
            gap = 8
            start_x = 18
            start_y = 70
            for page_offset, slot in enumerate(page_slots):
                index = page_start + page_offset
                tile_index = page_offset
                column = tile_index % columns
                row = tile_index // columns
                rect = QtCore.QRect(start_x + column * (tile_width + gap), start_y + row * (tile_height + gap), tile_width, tile_height)
                self._room_board_hit_slots.append((QtCore.QRect(rect), slot))
                override = texture_preview_for_slot(slot, overrides)
                effective_texture = override.preview_texture_resref if override is not None else slot.texture_resref
                is_selected = selected_slot is not None and self._same_material_slot(slot, selected_slot)
                painter.setPen(QtGui.QPen(highlight if is_selected else palette.color(QtGui.QPalette.Mid), 2 if is_selected else 1))
                painter.setBrush(base if row % 2 == 0 else alternate)
                painter.drawRoundedRect(rect, 4, 4)

                swatch_rect = QtCore.QRect(rect.left() + 8, rect.top() + 8, 52, 52)
                texture_resource = self._find_texture_resource(effective_texture)
                preview = self._texture_preview(texture_resource, max_size=52) if texture_resource is not None else None
                if preview is not None:
                    painter.drawPixmap(swatch_rect, self._pixmap_from_texture_preview(preview))
                else:
                    painter.fillRect(swatch_rect, highlight if is_selected else palette.color(QtGui.QPalette.Midlight))
                    painter.setPen(foreground)
                    painter.drawText(swatch_rect, QtCore.Qt.AlignCenter, str(index + 1))

                text_left = swatch_rect.right() + 8
                text_rect = QtCore.QRect(text_left, rect.top() + 8, rect.right() - text_left - 8, 72)
                painter.setPen(foreground)
                painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self._room_board_slot_text(slot, effective_texture, override is not None))
                painter.setPen(muted)
                painter.drawText(
                    QtCore.QRect(rect.left() + 8, rect.bottom() - 24, rect.width() - 16, 18),
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    f"{slot.face_count} faces, {slot.vertex_count} verts",
                )

            if len(visible_slots) > 12:
                painter.setPen(muted)
                painter.drawText(18, pixmap.height() - 18, f"Page {page_index + 1} of {page_count}")
        finally:
            painter.end()

        self.preview_label.setPixmap(pixmap)
        self.preview_label.setCursor(QtCore.Qt.PointingHandCursor)
        self._set_room_board_navigation(page_index, page_count, page_start + 1, page_start + len(page_slots))
        self.preview_label.setToolTip(
            f"{inventory.room_resref}: {len(inventory.slots)} material slots. "
            "Select a material target, then choose a TGA/TPC texture to preview a replacement."
        )

    def _clear_room_board_hits(self) -> None:
        self._room_board_hit_slots.clear()
        self._room_board_inventory = None
        self._room_board_visible_slot_count = 0
        self._set_room_board_navigation(0, 0, 0, 0)
        if hasattr(self, "preview_label"):
            self.preview_label.setCursor(QtCore.Qt.ArrowCursor)

    def _set_room_board_navigation(
        self,
        page_index: int,
        page_count: int,
        visible_start: int,
        visible_end: int,
    ) -> None:
        if not hasattr(self, "material_board_page_label"):
            return
        total = self._room_board_visible_slot_count
        if page_count <= 0 or total <= 0:
            self.material_board_page_label.setText("0 of 0")
            self.material_board_prev_button.setEnabled(False)
            self.material_board_next_button.setEnabled(False)
            self.material_board_nav.setToolTip("")
            return
        self.material_board_page_label.setText(
            f"{visible_start}-{visible_end} of {total}  |  page {page_index + 1}/{page_count}"
        )
        self.material_board_prev_button.setEnabled(page_index > 0)
        self.material_board_next_button.setEnabled(page_index + 1 < page_count)
        self.material_board_nav.setToolTip(
            f"Room material board page {page_index + 1} of {page_count}"
        )

    def _previous_room_board_page(self) -> None:
        inventory = self._room_board_inventory
        if inventory is None:
            return
        page_key = self._room_board_page_key(inventory)
        current = self._room_board_page_by_room.get(page_key, 0)
        self._room_board_page_by_room[page_key] = max(0, current - 1)
        self._show_room_material_board(inventory, self._selected_slot_on_current_room_board_page(inventory))

    def _next_room_board_page(self) -> None:
        inventory = self._room_board_inventory
        if inventory is None:
            return
        page_count = max(1, (len(self._filtered_material_slots(inventory)) + 11) // 12)
        page_key = self._room_board_page_key(inventory)
        current = self._room_board_page_by_room.get(page_key, 0)
        self._room_board_page_by_room[page_key] = min(page_count - 1, current + 1)
        self._show_room_material_board(inventory, self._selected_slot_on_current_room_board_page(inventory))

    def _selected_slot_on_current_room_board_page(
        self,
        inventory: ModuleRoomMaterialInventory,
    ) -> ModuleRoomTextureSlot | None:
        selected = self._selected_material_slot
        visible_slots = self._filtered_material_slots(inventory)
        selected_index = self._material_slot_index(inventory, selected, visible_slots) if selected is not None else None
        if selected is None or selected_index is None:
            return None
        page_index = self._room_board_page_by_room.get(self._room_board_page_key(inventory), 0)
        if selected_index // 12 == page_index:
            return selected
        return None

    def _material_slot_index(
        self,
        inventory: ModuleRoomMaterialInventory,
        slot: ModuleRoomTextureSlot,
        slots: tuple[ModuleRoomTextureSlot, ...] | None = None,
    ) -> int | None:
        for index, candidate in enumerate(slots or inventory.slots):
            if self._same_material_slot(candidate, slot):
                return index
        return None

    def _room_board_position_from_label(self, label_position: QtCore.QPoint) -> QtCore.QPoint | None:
        pixmap = self.preview_label.pixmap()
        if pixmap is None or pixmap.isNull() or not self._room_board_hit_slots:
            return None
        offset_x = (self.preview_label.width() - pixmap.width()) // 2
        offset_y = (self.preview_label.height() - pixmap.height()) // 2
        board_position = QtCore.QPoint(label_position.x() - offset_x, label_position.y() - offset_y)
        if board_position.x() < 0 or board_position.y() < 0:
            return None
        if board_position.x() > pixmap.width() or board_position.y() > pixmap.height():
            return None
        return board_position

    def _select_room_board_slot_at(self, board_position: QtCore.QPoint) -> bool:
        for rect, slot in self._room_board_hit_slots:
            if rect.contains(board_position):
                self._select_material_slot(slot, source="room material board")
                return True
        return False

    @staticmethod
    def _same_material_slot(left: ModuleRoomTextureSlot, right: ModuleRoomTextureSlot) -> bool:
        return (
            left.room_resref.lower(),
            left.node_name.lower(),
            left.slot_kind.lower(),
            left.texture_resref.lower(),
        ) == (
            right.room_resref.lower(),
            right.node_name.lower(),
            right.slot_kind.lower(),
            right.texture_resref.lower(),
        )

    @staticmethod
    def _room_board_slot_text(
        slot: ModuleRoomTextureSlot,
        effective_texture: str,
        has_override: bool,
    ) -> str:
        node = slot.node_name[:28]
        texture = slot.texture_resref
        if has_override:
            texture = f"{slot.texture_resref} -> {effective_texture}"
        if len(texture) > 34:
            texture = f"{texture[:31]}..."
        return f"{node}\n{slot.slot_kind}\n{texture}"

    def _material_slot_icon(self, index: int) -> QtGui.QIcon:
        palette = (
            "#2563eb",
            "#16a34a",
            "#d97706",
            "#dc2626",
            "#7c3aed",
            "#0891b2",
            "#4d7c0f",
            "#be185d",
        )
        pixmap = QtGui.QPixmap(52, 52)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor("#e5e7eb"), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(palette[(index - 1) % len(palette)])))
        painter.drawRoundedRect(QtCore.QRectF(3, 3, 46, 46), 4, 4)
        painter.setPen(QtGui.QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(3, 13, 46, 24), QtCore.Qt.AlignCenter, str(index))
        painter.end()
        return QtGui.QIcon(pixmap)

    def _clear_material_picker(self) -> None:
        if hasattr(self, "material_filter_edit"):
            blocker = QtCore.QSignalBlocker(self.material_filter_edit)
            try:
                self.material_filter_edit.clear()
                self.material_filter_edit.setEnabled(False)
            finally:
                del blocker
        self.material_pick_panel.clear()
        self.material_pick_panel.setEnabled(False)
        self.material_pick_panel.setToolTip("")
        self.material_picker.clear()
        self.material_picker.setEnabled(False)
        self.material_picker.setToolTip("")

    def _clear_material_preview(self) -> None:
        self.material_preview.setRowCount(0)
        self.material_preview.setToolTip("")
        self._clear_texture_compare()

    def _clear_texture_compare(self) -> None:
        self.current_texture_preview.clear()
        self.current_texture_preview.setText("Current texture")
        self.current_texture_preview.setToolTip("")
        self.replacement_texture_preview.clear()
        self.replacement_texture_preview.setText("Replacement texture")
        self.replacement_texture_preview.setToolTip("")

    def _populate_tga_editor(self, resource: BrowserResource) -> None:
        enabled = resource.restype == "tga"
        self.tga_output_resref_edit.setEnabled(enabled)
        self.tga_brightness_spin.setEnabled(enabled)
        self.tga_contrast_spin.setEnabled(enabled)
        self.tga_snow_spin.setEnabled(enabled)
        self.tga_preview_button.setEnabled(enabled)
        self.tga_output_resref_edit.setText(self._default_tga_output_resref(resource.resref))
        self.tga_brightness_spin.setValue(0)
        self.tga_contrast_spin.setValue(0)
        self.tga_snow_spin.setValue(60)
        self.tga_editor.setToolTip(f"{resource.label}: preview non-destructive TGA adjustments as an edited replacement texture")

    def _clear_tga_editor(self) -> None:
        self.tga_output_resref_edit.setEnabled(False)
        self.tga_brightness_spin.setEnabled(False)
        self.tga_contrast_spin.setEnabled(False)
        self.tga_snow_spin.setEnabled(False)
        self.tga_preview_button.setEnabled(False)
        self.tga_output_resref_edit.clear()
        self.tga_brightness_spin.setValue(0)
        self.tga_contrast_spin.setValue(0)
        self.tga_snow_spin.setValue(0)
        self.tga_editor.setToolTip("")

    def _preview_tga_edit(self) -> None:
        resource = self._selected_tga_resource
        if resource is None or resource.restype != "tga":
            self.statusBar().showMessage("Select a TGA texture before previewing a TGA edit.")
            return
        draft = create_tga_adjustment_draft(
            self._texture_resource_bytes(resource),
            source_resref=resource.resref,
            source_label=resource.label,
            output_resref=self.tga_output_resref_edit.text(),
            brightness=int(self.tga_brightness_spin.value()),
            contrast=int(self.tga_contrast_spin.value()),
            snow=int(self.tga_snow_spin.value()),
        )
        self._pending_tga_edit = draft
        rows = self._tga_edit_rows(draft)
        if draft.issues:
            rows.extend((f"TGA issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        if not draft.ready:
            self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
            self.statusBar().showMessage(f"TGA edit preview blocked: {draft.validation_status}.")
            return
        edited_resource = self._register_edited_tga_resource(draft)
        self._show_texture_resource_preview(edited_resource, draft.summary)
        replacement_draft = None
        if self._selected_material_slot is not None:
            replacement = self._create_pending_texture_replacement(edited_resource)
            if replacement is not None:
                replacement_draft = replacement
                rows.extend(self._texture_replacement_rows(replacement))
                self._set_details(rows)
        self.content_type_combo.setCurrentText("Textures")
        self.content_search.setText(edited_resource.resref)
        self._populate_content_browser()
        blocker = QtCore.QSignalBlocker(self.content_browser)
        try:
            for index in range(self.content_browser.count()):
                item = self.content_browser.item(index)
                if item is not None and item.data(QtCore.Qt.UserRole) == edited_resource:
                    self.content_browser.setCurrentItem(item)
                    break
        finally:
            del blocker
        self._selected_tga_resource = resource
        self._pending_tga_edit = draft
        self._set_details(rows)
        if replacement_draft is not None:
            self._pending_texture_replacement = replacement_draft
            self._update_texture_compare(edited_resource)
            self._update_export_action_enabled()
        self.statusBar().showMessage(f"Previewed edited TGA {edited_resource.label}.")

    def _register_edited_tga_resource(self, draft: ModuleTgaEditDraft) -> ModuleTextureMemoryResource:
        resource = ModuleTextureMemoryResource(
            resref=draft.output_resref,
            restype="tga",
            restype_id=3,
            payload=draft.output_payload,
            source_label=draft.source_label,
        )
        self._imported_texture_resources = [
            item for item in self._imported_texture_resources if item.label.lower() != resource.label.lower()
        ]
        self._imported_texture_resources.append(resource)
        self._texture_preview_cache.clear()
        self._texture_icon_cache.clear()
        return resource

    @staticmethod
    def _tga_edit_rows(draft: ModuleTgaEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending TGA edit", draft.summary),
            ("Replacement status", "preview only; source texture bytes unchanged"),
            ("Source texture", draft.source_label),
            ("Output texture", draft.label),
            ("Dimensions", f"{draft.width} x {draft.height}" if draft.width and draft.height else "not validated"),
            ("Brightness", str(draft.brightness)),
            ("Contrast", str(draft.contrast)),
            ("Snow", str(draft.snow)),
            ("Validation", draft.validation_status),
            ("Texture state", "available as session replacement texture" if draft.ready else "blocked by validation"),
        ]

    @staticmethod
    def _default_tga_output_resref(resref: str) -> str:
        base = str(resref or "").strip().lower() or "edited_tga"
        suffix = "_snow"
        if len(base) + len(suffix) <= 16:
            return f"{base}{suffix}"
        return f"{base[:16 - len(suffix)]}{suffix}"

    def _populate_txi_editor(self, resource: BrowserResource) -> None:
        enabled = resource.restype in {"tga", "tpc", "txi"}
        self.txi_output_resref_edit.setEnabled(enabled)
        self.txi_text_edit.setEnabled(enabled)
        self.txi_preview_button.setEnabled(enabled)
        self.txi_output_resref_edit.setText(resource.resref)
        self.txi_text_edit.setPlainText(self._initial_txi_text(resource))
        self.txi_editor.setToolTip(f"{resource.label}: author or edit a matching TXI sidecar")

    def _clear_txi_editor(self) -> None:
        self.txi_output_resref_edit.setEnabled(False)
        self.txi_text_edit.setEnabled(False)
        self.txi_preview_button.setEnabled(False)
        self.txi_output_resref_edit.clear()
        self.txi_text_edit.clear()
        self.txi_editor.setToolTip("")

    def _preview_txi_edit(self) -> None:
        resource = self._selected_txi_source_resource
        if resource is None or resource.restype not in {"tga", "tpc", "txi"}:
            self.statusBar().showMessage("Select a texture before previewing a TXI sidecar.")
            return
        draft = create_txi_text_edit_draft(
            source_label=resource.label,
            output_resref=self.txi_output_resref_edit.text(),
            txi_text=self.txi_text_edit.toPlainText(),
        )
        self._pending_txi_edit = draft
        rows = self._txi_edit_rows(draft)
        if draft.issues:
            rows.extend((f"TXI issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        if not draft.ready:
            self._set_details(rows)
            self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
            self.statusBar().showMessage(f"TXI sidecar preview blocked: {draft.validation_status}.")
            return
        sidecar_resource = self._register_edited_txi_resource(draft)
        replacement_draft = None
        replacement_resource = self._find_texture_resource(draft.output_resref)
        if replacement_resource is not None and self._selected_material_slot is not None:
            replacement = self._create_pending_texture_replacement(replacement_resource)
            if replacement is not None:
                replacement_draft = replacement
                rows.extend(self._texture_replacement_rows(replacement))
        self.content_type_combo.setCurrentText("Textures")
        self.content_search.setText(sidecar_resource.resref)
        self._populate_content_browser()
        blocker = QtCore.QSignalBlocker(self.content_browser)
        try:
            for index in range(self.content_browser.count()):
                item = self.content_browser.item(index)
                if item is not None and item.data(QtCore.Qt.UserRole) == sidecar_resource:
                    self.content_browser.setCurrentItem(item)
                    break
        finally:
            del blocker
        self._selected_txi_source_resource = resource
        self._pending_txi_edit = draft
        self._set_details(rows)
        if replacement_draft is not None:
            self._pending_texture_replacement = replacement_draft
            self._update_material_preview()
            self._update_export_action_enabled()
        self.preview_label.setText(draft.txi_text[:4000])
        self.statusBar().showMessage(f"Previewed TXI sidecar {sidecar_resource.label}.")

    def _register_edited_txi_resource(self, draft: ModuleTxiEditDraft) -> ModuleTextureMemoryResource:
        resource = ModuleTextureMemoryResource(
            resref=draft.output_resref,
            restype="txi",
            restype_id=2022,
            payload=draft.output_payload,
            source_label=draft.source_label,
        )
        self._imported_texture_resources = [
            item for item in self._imported_texture_resources if item.label.lower() != resource.label.lower()
        ]
        self._imported_texture_resources.append(resource)
        self._texture_preview_cache.clear()
        self._texture_icon_cache.clear()
        return resource

    @staticmethod
    def _txi_edit_rows(draft: ModuleTxiEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending TXI sidecar", draft.summary),
            ("Replacement status", "preview only; source texture bytes unchanged"),
            ("Output sidecar", draft.label),
            ("Payload bytes", str(len(draft.output_payload))),
            ("Validation", draft.validation_status),
            ("Sidecar state", "available as session TXI sidecar" if draft.ready else "blocked by validation"),
        ]

    def _initial_txi_text(self, resource: BrowserResource) -> str:
        if resource.restype == "txi":
            try:
                return self._texture_resource_bytes(resource).decode("ascii", errors="replace")
            except Exception:
                return ""
        if resource.restype == "tpc":
            preview = self._texture_preview(resource, max_size=16)
            if preview is not None and preview.txi:
                return preview.txi
        matching = next(
            (
                item
                for item in self._imported_texture_resources
                if item.restype == "txi" and item.resref.lower() == resource.resref.lower()
            ),
            None,
        )
        if matching is not None:
            try:
                return matching.read_bytes().decode("ascii", errors="replace")
            except Exception:
                return ""
        return ""

    def _populate_wok_surface_editor(self, inventory: ModuleWokInventory) -> None:
        enabled = inventory.ok and inventory.face_count > 0
        self.wok_face_spin.setEnabled(enabled)
        self.wok_surface_combo.setEnabled(enabled)
        self.wok_preview_button.setEnabled(enabled)
        self.wok_face_spin.setMaximum(max(0, inventory.face_count - 1))
        self.wok_face_spin.setValue(0)
        self.wok_surface_editor.setToolTip(f"{inventory.room_resref}: {inventory.face_count} walkmesh faces")

    def _clear_wok_surface_editor(self) -> None:
        self.wok_face_spin.setEnabled(False)
        self.wok_surface_combo.setEnabled(False)
        self.wok_preview_button.setEnabled(False)
        self.wok_face_spin.setMaximum(0)
        self.wok_face_spin.setValue(0)
        self.wok_surface_editor.setToolTip("")

    def _find_wok_surface_combo_index(self, surface_id: int) -> int:
        for index in range(self.wok_surface_combo.count()):
            if int(self.wok_surface_combo.itemData(index) or 0) == int(surface_id):
                return index
        return -1

    def _select_wok_surface_summary(self, surface: ModuleWokSurfaceSummary, *, source: str) -> None:
        if surface.face_indices:
            self.wok_face_spin.setValue(int(surface.face_indices[0]))
        combo_index = self._find_wok_surface_combo_index(surface.surface_id)
        if combo_index >= 0:
            self.wok_surface_combo.setCurrentIndex(combo_index)
        self.selection_label.setText(f"Selected WOK surface {surface.surface_id} from {source}")
        face_text = f"face {surface.face_indices[0]}" if surface.face_indices else "no face index"
        self.statusBar().showMessage(
            f"Selected WOK surface {surface.surface_id} {surface.surface_name}; {face_text} is ready for surface paint preview."
        )

    def _preview_wok_surface_paint(self) -> None:
        if self._module_path is None or self._selected_wok_resource is None:
            self.statusBar().showMessage("Select a WOK resource before previewing walkmesh surface paint.")
            return
        surface_id = int(self.wok_surface_combo.currentData() or 0)
        face_index = int(self.wok_face_spin.value())
        draft = create_wok_surface_paint_draft(
            self._module_path,
            self._selected_wok_resource,
            face_index,
            surface_id,
        )
        self._pending_wok_surface_paint = draft
        self._pending_texture_replacement = None
        self._pending_git_object_edit = None
        self._pending_template_field_edit = None
        self._pending_metadata_field_edit = None
        self._pending_layout_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._wok_surface_paint_rows(draft)
        if draft.issues:
            rows.extend((f"WOK issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending WOK surface paint: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed WOK surface paint for {draft.room_resref}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _wok_surface_paint_rows(draft: ModuleWokSurfacePaintDraft) -> list[tuple[str, str]]:
        return [
            ("Pending WOK surface paint", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Face indices", ", ".join(str(index) for index in draft.face_indices)),
            ("Old surfaces", ", ".join(f"{index}:{surface}" for index, surface in sorted(draft.old_surfaces.items()))),
            ("New surface", f"{draft.new_surface_id} {draft.new_surface_name}"),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _populate_layout_editor(self, inventory: ModuleLayoutInventory) -> None:
        blocker = QtCore.QSignalBlocker(self.layout_target_combo)
        try:
            self.layout_target_combo.clear()
            if inventory.restype == "lyt":
                for room in inventory.rooms:
                    x, y, z = room.position
                    self.layout_target_combo.addItem(
                        f"{room.room_resref}  {x:.2f}, {y:.2f}, {z:.2f}",
                        room.room_resref,
                    )
            elif inventory.restype == "vis":
                for row in inventory.visibility:
                    self.layout_target_combo.addItem(
                        f"{row.room_resref}  {row.link_count} links",
                        row.room_resref,
                    )
        finally:
            del blocker
        enabled = inventory.ok and self.layout_target_combo.count() > 0
        self.layout_target_combo.setEnabled(enabled)
        self.layout_field_combo.setEnabled(enabled)
        self.layout_preview_button.setEnabled(enabled)
        self.layout_editor.setToolTip(f"{inventory.resref}.{inventory.restype}: {inventory.editable_scope}")
        self._populate_layout_field_editor()

    def _clear_layout_editor(self) -> None:
        target_blocker = QtCore.QSignalBlocker(self.layout_target_combo)
        try:
            self.layout_target_combo.clear()
        finally:
            del target_blocker
        field_blocker = QtCore.QSignalBlocker(self.layout_field_combo)
        try:
            self.layout_field_combo.clear()
        finally:
            del field_blocker
        self.layout_target_combo.setEnabled(False)
        self.layout_field_combo.setEnabled(False)
        self.layout_value_edit.setEnabled(False)
        self.layout_visible_toggle.setEnabled(False)
        self.layout_preview_button.setEnabled(False)
        self.layout_value_edit.clear()
        self.layout_visible_toggle.setChecked(False)
        self.layout_editor.setToolTip("")

    def _current_layout_inventory(self) -> ModuleLayoutInventory | None:
        if self._selected_layout_resource is None:
            return None
        return self._layout_inventory(self._selected_layout_resource)

    def _populate_layout_field_editor(self) -> None:
        inventory = self._current_layout_inventory()
        target = str(self.layout_target_combo.currentData() or "")
        blocker = QtCore.QSignalBlocker(self.layout_field_combo)
        try:
            self.layout_field_combo.clear()
            if inventory is not None and inventory.restype == "lyt":
                self.layout_field_combo.addItem("X", "x")
                self.layout_field_combo.addItem("Y", "y")
                self.layout_field_combo.addItem("Z", "z")
            elif inventory is not None and inventory.restype == "vis":
                rooms = sorted(
                    {
                        row.room_resref
                        for row in inventory.visibility
                    }
                    | {
                        visible_room
                        for row in inventory.visibility
                        for visible_room in row.visible_rooms
                    }
                    | set(inventory.unlisted_layout_rooms)
                )
                for room in rooms:
                    if room and room != target:
                        self.layout_field_combo.addItem(room, room)
        finally:
            del blocker
        has_fields = self.layout_field_combo.count() > 0
        self.layout_field_combo.setEnabled(has_fields)
        self.layout_preview_button.setEnabled(has_fields)
        self._sync_layout_edit_value()

    def _sync_layout_edit_value(self) -> None:
        inventory = self._current_layout_inventory()
        target = str(self.layout_target_combo.currentData() or "")
        field = str(self.layout_field_combo.currentData() or "")
        if inventory is None:
            self.layout_value_edit.clear()
            self.layout_value_edit.setEnabled(False)
            self.layout_visible_toggle.setEnabled(False)
            return
        if inventory.restype == "lyt":
            room = next((item for item in inventory.rooms if item.room_resref == target), None)
            axis_index = {"x": 0, "y": 1, "z": 2}.get(field, 0)
            value = room.position[axis_index] if room is not None else 0.0
            self.layout_value_edit.setText(f"{value:.6g}")
            self.layout_value_edit.setEnabled(True)
            self.layout_visible_toggle.setEnabled(False)
            self.layout_visible_toggle.setChecked(False)
            return
        row = next((item for item in inventory.visibility if item.room_resref == target), None)
        visible = row is not None and field in row.visible_rooms
        self.layout_value_edit.clear()
        self.layout_value_edit.setEnabled(False)
        self.layout_visible_toggle.setEnabled(True)
        self.layout_visible_toggle.setChecked(visible)

    def _select_layout_target(self, target_key: str, *, source: str) -> bool:
        for index in range(self.layout_target_combo.count()):
            if str(self.layout_target_combo.itemData(index) or "") == target_key:
                self.layout_target_combo.setCurrentIndex(index)
                self.selection_label.setText(f"Selected layout target {target_key} from {source}")
                self.statusBar().showMessage(f"Selected layout target {target_key} for editing.")
                return True
        self.statusBar().showMessage(f"Layout target {target_key} is not available in the current editor.")
        return False

    def _select_layout_room_row(self, room: ModuleLayoutRoomRow, *, source: str) -> None:
        if self._select_layout_target(room.room_resref, source=source):
            for index in range(self.layout_field_combo.count()):
                if self.layout_field_combo.itemData(index) == "x":
                    self.layout_field_combo.setCurrentIndex(index)
                    break
            self._sync_layout_edit_value()

    def _select_visibility_row(self, row: ModuleVisibilityRow, *, source: str) -> None:
        if self._select_layout_target(row.room_resref, source=source):
            if row.visible_rooms:
                first_visible = row.visible_rooms[0]
                for index in range(self.layout_field_combo.count()):
                    if str(self.layout_field_combo.itemData(index) or "") == first_visible:
                        self.layout_field_combo.setCurrentIndex(index)
                        break
            self._sync_layout_edit_value()

    def _preview_layout_edit(self) -> None:
        if self._module_path is None or self._selected_layout_resource is None:
            self.statusBar().showMessage("Select a LYT or VIS resource before previewing a layout edit.")
            return
        inventory = self._current_layout_inventory()
        if inventory is None:
            self.statusBar().showMessage("Choose a layout or visibility resource before previewing an edit.")
            return
        target = str(self.layout_target_combo.currentData() or "")
        field = str(self.layout_field_combo.currentData() or "")
        value = self.layout_value_edit.text() if inventory.restype == "lyt" else str(self.layout_visible_toggle.isChecked())
        draft = create_layout_edit_draft(
            self._module_path,
            self._resources,
            self._selected_layout_resource,
            target_key=target,
            field_key=field,
            value=value,
        )
        self._pending_layout_edit = draft
        self._pending_texture_replacement = None
        self._pending_wok_surface_paint = None
        self._pending_git_object_edit = None
        self._pending_template_field_edit = None
        self._pending_metadata_field_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._layout_edit_rows(draft)
        if draft.issues:
            rows.extend((f"Layout issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending layout edit: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed {draft.restype.upper()} edit for {draft.resref}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _layout_edit_rows(draft: ModuleLayoutEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending layout edit", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Resource", f"{draft.resref}.{draft.restype}"),
            ("Edit kind", draft.edit_kind),
            ("Target", draft.target_key),
            ("Field", draft.field_key),
            ("Old value", draft.old_value),
            ("New value", draft.new_value),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _populate_git_object_editor(self, inventory: ModuleGitInventory) -> None:
        self._selected_git_inventory = inventory
        query = self._git_object_filter_query()
        rows = [row for row in inventory.objects if self._git_object_matches_filter(row, query)]
        blocker = QtCore.QSignalBlocker(self.git_object_combo)
        try:
            self.git_object_combo.clear()
            for row in rows:
                label = f"{row.object_type}.{row.index} {row.template_resref or row.tag or '(unnamed)'}"
                self.git_object_combo.addItem(label, row)
        finally:
            del blocker
        enabled = inventory.ok and self.git_object_combo.count() > 0
        self.git_object_filter_edit.setEnabled(inventory.ok and len(inventory.objects) > 0)
        self.git_object_combo.setEnabled(enabled)
        self.git_field_combo.setEnabled(enabled)
        self.git_value_edit.setEnabled(enabled)
        self.git_preview_button.setEnabled(enabled)
        if query:
            self.git_object_editor.setToolTip(
                f"{inventory.resref}: {len(rows)} of {inventory.total_objects} placed object forms match '{query}'"
            )
        else:
            self.git_object_editor.setToolTip(f"{inventory.resref}: {inventory.total_objects} placed object forms")
        self._populate_git_field_editor()

    def _clear_git_object_editor(self) -> None:
        self._selected_git_inventory = None
        filter_blocker = QtCore.QSignalBlocker(self.git_object_filter_edit)
        try:
            self.git_object_filter_edit.clear()
        finally:
            del filter_blocker
        blocker = QtCore.QSignalBlocker(self.git_object_combo)
        try:
            self.git_object_combo.clear()
        finally:
            del blocker
        field_blocker = QtCore.QSignalBlocker(self.git_field_combo)
        try:
                self.git_field_combo.clear()
        finally:
            del field_blocker
        self.git_object_filter_edit.setEnabled(False)
        self.git_object_combo.setEnabled(False)
        self.git_field_combo.setEnabled(False)
        self.git_value_edit.setEnabled(False)
        self.git_preview_button.setEnabled(False)
        self.git_open_template_button.setEnabled(False)
        self.git_value_edit.clear()
        self.git_object_editor.setToolTip("")

    def _git_object_filter_changed(self) -> None:
        if self._selected_git_inventory is not None:
            self._populate_git_object_editor(self._selected_git_inventory)

    def _git_object_filter_query(self) -> str:
        return self.git_object_filter_edit.text().strip().lower()

    @staticmethod
    def _git_object_matches_filter(row: ModuleGitObjectRow, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join(
            (
                row.object_type,
                str(row.index),
                row.template_resref,
                row.tag,
                row.template_type,
                row.list_label,
            )
        ).lower()
        return query in haystack

    @staticmethod
    def _git_object_same_target(left: ModuleGitObjectRow, right: ModuleGitObjectRow) -> bool:
        return left.object_type == right.object_type and left.index == right.index

    def _find_git_object_combo_index(self, target: ModuleGitObjectRow) -> int:
        for index in range(self.git_object_combo.count()):
            row = self.git_object_combo.itemData(index)
            if isinstance(row, ModuleGitObjectRow) and self._git_object_same_target(row, target):
                return index
        return -1

    def _select_git_object_row(self, target: ModuleGitObjectRow, *, source: str) -> None:
        combo_index = self._find_git_object_combo_index(target)
        if combo_index < 0 and self._git_object_filter_query():
            self.git_object_filter_edit.clear()
            combo_index = self._find_git_object_combo_index(target)
        if combo_index < 0:
            self.statusBar().showMessage(f"Could not find {target.object_type}.{target.index} in the current GIT inventory.")
            return
        self.git_object_combo.setCurrentIndex(combo_index)
        if self.git_field_combo.count() == 0:
            self._populate_git_field_editor()
        self.selection_label.setText(f"Selected {target.object_type}.{target.index} from {source}")
        self.statusBar().showMessage(f"Selected GIT object {target.object_type}.{target.index} for editing.")

    def _current_git_object_row(self) -> ModuleGitObjectRow | None:
        payload = self.git_object_combo.currentData()
        return payload if isinstance(payload, ModuleGitObjectRow) else None

    def _populate_git_field_editor(self) -> None:
        row = self._current_git_object_row()
        blocker = QtCore.QSignalBlocker(self.git_field_combo)
        try:
            self.git_field_combo.clear()
            if row is not None:
                for field in row.editable_fields:
                    self.git_field_combo.addItem(f"{field.label} ({field.key})", field.key)
        finally:
            del blocker
        has_fields = self.git_field_combo.count() > 0
        self.git_field_combo.setEnabled(has_fields)
        self.git_value_edit.setEnabled(has_fields)
        self.git_preview_button.setEnabled(has_fields)
        template_resource = self._git_object_template_resource(row)
        self.git_open_template_button.setEnabled(template_resource is not None)
        if template_resource is not None:
            self.git_open_template_button.setToolTip(f"Open {template_resource.label} in the template editor")
        elif row is not None:
            self.git_open_template_button.setToolTip(f"No module-local template resource found for {row.template_resref or row.tag}")
        else:
            self.git_open_template_button.setToolTip("")
        self._sync_git_object_edit_value()

    def _git_object_template_resource(self, row: ModuleGitObjectRow | None) -> ModuleArchiveResource | None:
        if row is None:
            return None
        resref = row.template_resref.strip().lower()
        restype = (row.template_type or GIT_TEMPLATE_TYPES.get(row.object_type, "")).strip().lower()
        if not resref or not restype:
            return None
        for resource in self._resources:
            if resource.restype == restype and resource.resref.lower() == resref:
                return resource
        return None

    def _open_git_object_template(self) -> None:
        row = self._current_git_object_row()
        resource = self._git_object_template_resource(row)
        if row is None:
            self.statusBar().showMessage("Choose a placed object before opening its template.")
            return
        if resource is None:
            self.statusBar().showMessage(f"No module-local {row.template_type or 'template'} resource found for {row.template_resref or row.tag}.")
            return
        self.content_type_combo.setCurrentText("Gameplay")
        self.content_search.setText(resource.resref)
        self._populate_content_browser()
        for index in range(self.content_browser.count()):
            item = self.content_browser.item(index)
            if item is not None and item.data(QtCore.Qt.UserRole) == resource:
                self.content_browser.setCurrentItem(item)
                self._sync_selection_from_content_browser()
                self.selection_label.setText(f"Opened template {resource.label} from {row.object_type}.{row.index}")
                self.statusBar().showMessage(f"Opened {resource.label} for placed object {row.object_type}.{row.index}.")
                return
        self.statusBar().showMessage(f"Template resource {resource.label} is not visible in the current content browser filter.")

    def _sync_git_object_edit_value(self) -> None:
        row = self._current_git_object_row()
        if row is None:
            self.git_value_edit.clear()
            return
        field_key = str(self.git_field_combo.currentData() or "TemplateResRef")
        for field in row.editable_fields:
            if field.key == field_key:
                self.git_value_edit.setText(field.value)
                self.git_value_edit.setToolTip(f"{field.label}: {field.value_type}")
                return
        self.git_value_edit.clear()
        self.git_value_edit.setToolTip("")

    def _preview_git_object_edit(self) -> None:
        if self._module_path is None or self._selected_git_resource is None:
            self.statusBar().showMessage("Select a GIT resource before previewing a placed-object edit.")
            return
        row = self._current_git_object_row()
        if row is None:
            self.statusBar().showMessage("Choose a placed object before previewing a GIT edit.")
            return
        draft = create_git_object_edit_draft(
            self._module_path,
            self._selected_git_resource,
            object_type=row.object_type,
            index=row.index,
            field_key=str(self.git_field_combo.currentData() or "TemplateResRef"),
            value=self.git_value_edit.text(),
        )
        self._pending_git_object_edit = draft
        self._pending_texture_replacement = None
        self._pending_wok_surface_paint = None
        self._pending_template_field_edit = None
        self._pending_metadata_field_edit = None
        self._pending_layout_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._git_object_edit_rows(draft)
        if draft.issues:
            rows.extend((f"GIT issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending GIT edit: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed GIT object edit for {draft.git_resref}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _git_object_edit_rows(draft: ModuleGitObjectEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending GIT object edit", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Object", f"{draft.object_type}.{draft.index}"),
            ("Field", draft.field_key),
            ("Old value", draft.old_value),
            ("New value", draft.new_value),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _populate_template_editor(self, inventory: ModuleTemplateInventory) -> None:
        blocker = QtCore.QSignalBlocker(self.template_field_combo)
        try:
            self.template_field_combo.clear()
            for field in inventory.fields:
                if field.editable:
                    self.template_field_combo.addItem(f"{field.label} ({field.key})", field)
        finally:
            del blocker
        enabled = inventory.ok and self.template_field_combo.count() > 0
        self.template_field_combo.setEnabled(enabled)
        self.template_value_edit.setEnabled(enabled)
        self.template_preview_button.setEnabled(enabled)
        self.template_editor.setToolTip(f"{inventory.resref}.{inventory.restype}: {inventory.template_kind}")
        self._sync_template_edit_value()

    def _clear_template_editor(self) -> None:
        blocker = QtCore.QSignalBlocker(self.template_field_combo)
        try:
            self.template_field_combo.clear()
        finally:
            del blocker
        self.template_field_combo.setEnabled(False)
        self.template_value_edit.setEnabled(False)
        self.template_preview_button.setEnabled(False)
        self.template_value_edit.clear()
        self.template_value_edit.setToolTip("")
        self.template_editor.setToolTip("")

    def _current_template_field(self):
        return self.template_field_combo.currentData()

    def _sync_template_edit_value(self) -> None:
        field = self._current_template_field()
        if field is None:
            self.template_value_edit.clear()
            self.template_value_edit.setToolTip("")
            return
        self.template_value_edit.setText(str(getattr(field, "value", "") or ""))
        self.template_value_edit.setToolTip(f"{getattr(field, 'label', '')}: {getattr(field, 'value_type', '')}")

    def _select_template_field(self, field: ModuleTemplateField, *, source: str) -> None:
        if not field.editable:
            self.statusBar().showMessage(f"{field.label} is display-only in the template editor.")
            return
        for index in range(self.template_field_combo.count()):
            candidate = self.template_field_combo.itemData(index)
            if isinstance(candidate, ModuleTemplateField) and candidate.key == field.key:
                self.template_field_combo.setCurrentIndex(index)
                self.selection_label.setText(f"Selected template field {field.label} from {source}")
                self.statusBar().showMessage(f"Selected template field {field.label} for editing.")
                return
        self.statusBar().showMessage(f"Template field {field.label} is not available in the current editor.")

    def _preview_template_field_edit(self) -> None:
        if self._module_path is None or self._selected_template_resource is None:
            self.statusBar().showMessage("Select a gameplay template resource before previewing a template edit.")
            return
        field = self._current_template_field()
        field_key = str(getattr(field, "key", "") or "")
        if not field_key:
            self.statusBar().showMessage("Choose a gameplay template field before previewing an edit.")
            return
        draft = create_template_field_edit_draft(
            self._module_path,
            self._selected_template_resource,
            field_key=field_key,
            value=self.template_value_edit.text(),
        )
        self._pending_template_field_edit = draft
        self._pending_texture_replacement = None
        self._pending_wok_surface_paint = None
        self._pending_git_object_edit = None
        self._pending_metadata_field_edit = None
        self._pending_layout_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._template_field_edit_rows(draft)
        if draft.issues:
            rows.extend((f"Template issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending template edit: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed template edit for {draft.resref}.{draft.restype}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _template_field_edit_rows(draft: ModuleTemplateFieldEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending template edit", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Resource", f"{draft.resref}.{draft.restype}"),
            ("Field", draft.field_key),
            ("Old value", draft.old_value),
            ("New value", draft.new_value),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _populate_metadata_editor(self, inventory: ModuleMetadataInventory) -> None:
        blocker = QtCore.QSignalBlocker(self.metadata_field_combo)
        try:
            self.metadata_field_combo.clear()
            for field in inventory.fields:
                if field.editable:
                    self.metadata_field_combo.addItem(f"{field.label} ({field.key})", field)
        finally:
            del blocker
        enabled = inventory.ok and self.metadata_field_combo.count() > 0
        self.metadata_field_combo.setEnabled(enabled)
        self.metadata_value_edit.setEnabled(enabled)
        self.metadata_preview_button.setEnabled(enabled)
        self.metadata_editor.setToolTip(f"{inventory.resref}.{inventory.restype}: {inventory.editable_scope}")
        self._sync_metadata_edit_value()

    def _clear_metadata_editor(self) -> None:
        blocker = QtCore.QSignalBlocker(self.metadata_field_combo)
        try:
            self.metadata_field_combo.clear()
        finally:
            del blocker
        self.metadata_field_combo.setEnabled(False)
        self.metadata_value_edit.setEnabled(False)
        self.metadata_preview_button.setEnabled(False)
        self.metadata_value_edit.clear()
        self.metadata_value_edit.setToolTip("")
        self.metadata_editor.setToolTip("")

    def _current_metadata_field(self):
        return self.metadata_field_combo.currentData()

    def _sync_metadata_edit_value(self) -> None:
        field = self._current_metadata_field()
        if field is None:
            self.metadata_value_edit.clear()
            self.metadata_value_edit.setToolTip("")
            return
        self.metadata_value_edit.setText(str(getattr(field, "value", "") or ""))
        self.metadata_value_edit.setToolTip(f"{getattr(field, 'label', '')}: {getattr(field, 'value_type', '')}")

    def _select_metadata_field(self, field: ModuleMetadataField, *, source: str) -> None:
        if not field.editable:
            self.statusBar().showMessage(f"{field.label} is display-only in the metadata editor.")
            return
        for index in range(self.metadata_field_combo.count()):
            candidate = self.metadata_field_combo.itemData(index)
            if isinstance(candidate, ModuleMetadataField) and candidate.key == field.key:
                self.metadata_field_combo.setCurrentIndex(index)
                self.selection_label.setText(f"Selected metadata field {field.label} from {source}")
                self.statusBar().showMessage(f"Selected metadata field {field.label} for editing.")
                return
        self.statusBar().showMessage(f"Metadata field {field.label} is not available in the current editor.")

    def _preview_metadata_field_edit(self) -> None:
        if self._module_path is None or self._selected_metadata_resource is None:
            self.statusBar().showMessage("Select an ARE or IFO resource before previewing a metadata edit.")
            return
        field = self._current_metadata_field()
        field_key = str(getattr(field, "key", "") or "")
        if not field_key:
            self.statusBar().showMessage("Choose a metadata field before previewing an edit.")
            return
        draft = create_metadata_field_edit_draft(
            self._module_path,
            self._selected_metadata_resource,
            field_key=field_key,
            value=self.metadata_value_edit.text(),
        )
        self._pending_metadata_field_edit = draft
        self._pending_texture_replacement = None
        self._pending_wok_surface_paint = None
        self._pending_git_object_edit = None
        self._pending_template_field_edit = None
        self._pending_layout_edit = None
        self._pending_logic_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._metadata_field_edit_rows(draft)
        if draft.issues:
            rows.extend((f"Metadata issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending metadata edit: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed metadata edit for {draft.resref}.{draft.restype}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _metadata_field_edit_rows(draft: ModuleMetadataFieldEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending metadata edit", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Resource", f"{draft.resref}.{draft.restype}"),
            ("Field", draft.field_key),
            ("Old value", draft.old_value),
            ("New value", draft.new_value),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _populate_logic_editor(self, inventory: ModuleLogicInventory) -> None:
        blocker = QtCore.QSignalBlocker(self.logic_field_combo)
        try:
            self.logic_field_combo.clear()
            for field in inventory.fields:
                if field.editable:
                    self.logic_field_combo.addItem(f"{field.label} ({field.key})", field)
        finally:
            del blocker
        enabled = inventory.restype == "dlg" and inventory.ok and self.logic_field_combo.count() > 0
        self.logic_field_combo.setEnabled(enabled)
        self.logic_value_edit.setEnabled(enabled)
        self.logic_preview_button.setEnabled(enabled)
        self.logic_editor.setToolTip(f"{inventory.resref}.{inventory.restype}: {inventory.editable_scope}")
        self._sync_logic_edit_value()

    def _clear_logic_editor(self) -> None:
        blocker = QtCore.QSignalBlocker(self.logic_field_combo)
        try:
            self.logic_field_combo.clear()
        finally:
            del blocker
        self.logic_field_combo.setEnabled(False)
        self.logic_value_edit.setEnabled(False)
        self.logic_preview_button.setEnabled(False)
        self.logic_value_edit.clear()
        self.logic_value_edit.setToolTip("")
        self.logic_editor.setToolTip("")

    def _current_logic_field(self):
        return self.logic_field_combo.currentData()

    def _sync_logic_edit_value(self) -> None:
        field = self._current_logic_field()
        if field is None:
            self.logic_value_edit.clear()
            self.logic_value_edit.setToolTip("")
            return
        self.logic_value_edit.setText(str(getattr(field, "value", "") or ""))
        self.logic_value_edit.setToolTip(f"{getattr(field, 'label', '')}: {getattr(field, 'value_type', '')}")

    def _select_logic_field(self, field: ModuleLogicField, *, source: str) -> None:
        if not field.editable:
            self.statusBar().showMessage(f"{field.label} is list-only in the logic editor.")
            return
        for index in range(self.logic_field_combo.count()):
            candidate = self.logic_field_combo.itemData(index)
            if isinstance(candidate, ModuleLogicField) and candidate.key == field.key:
                self.logic_field_combo.setCurrentIndex(index)
                self.selection_label.setText(f"Selected logic field {field.label} from {source}")
                self.statusBar().showMessage(f"Selected logic field {field.label} for editing.")
                return
        self.statusBar().showMessage(f"Logic field {field.label} is not available in the current editor.")

    def _preview_logic_field_edit(self) -> None:
        if self._module_path is None or self._selected_logic_resource is None:
            self.statusBar().showMessage("Select a DLG resource before previewing a dialogue edit.")
            return
        field = self._current_logic_field()
        field_key = str(getattr(field, "key", "") or "")
        if not field_key:
            self.statusBar().showMessage("Choose a dialogue field before previewing an edit.")
            return
        draft = create_logic_field_edit_draft(
            self._module_path,
            self._selected_logic_resource,
            field_key=field_key,
            value=self.logic_value_edit.text(),
        )
        self._pending_logic_field_edit = draft
        self._pending_texture_replacement = None
        self._pending_wok_surface_paint = None
        self._pending_layout_edit = None
        self._pending_git_object_edit = None
        self._pending_template_field_edit = None
        self._pending_metadata_field_edit = None
        self.save_copy_action.setEnabled(draft.ready)
        self._update_export_action_enabled()
        rows = self._logic_field_edit_rows(draft)
        if draft.issues:
            rows.extend((f"Logic issue {index}", issue) for index, issue in enumerate(draft.issues, start=1))
        self._set_details(rows)
        self.preview_label.setText(f"{draft.summary}\nValidation: {draft.validation_status}")
        self.selection_label.setText(f"Pending DLG edit: {draft.summary}")
        self.statusBar().showMessage(
            f"Previewed DLG edit for {draft.resref}.{draft.restype}; export is {'ready' if draft.ready else 'blocked'}."
        )

    @staticmethod
    def _logic_field_edit_rows(draft: ModuleLogicFieldEditDraft) -> list[tuple[str, str]]:
        return [
            ("Pending logic edit", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Resource", f"{draft.resref}.{draft.restype}"),
            ("Field", draft.field_key),
            ("Old value", draft.old_value),
            ("New value", draft.new_value),
            ("Validation", draft.validation_status),
            ("Export state", "ready for copied module export" if draft.ready else "blocked by validation"),
        ]

    def _update_material_preview(self) -> None:
        slot = self._selected_material_slot
        draft = self._pending_texture_replacement
        if slot is None:
            self._clear_material_preview()
            return
        inventory = self._room_material_inventory_by_resref(slot.room_resref)
        override = texture_preview_for_slot(slot, self._texture_preview_overrides_for_room(inventory)) if inventory is not None else None
        current_resource = self._find_texture_resource(slot.texture_resref)
        rows = [
            ("Room", slot.room_resref),
            ("Mesh node", slot.node_name),
            ("Scope", slot.editable_scope),
            ("Slot", slot.slot_kind),
            ("Current texture", slot.texture_resref),
            ("Current source", self._resource_source_label(current_resource) if current_resource is not None else "referenced only"),
            ("Current TXI", self._texture_sidecar_summary(slot.texture_resref)),
            ("Faces", str(slot.face_count)),
            ("Vertices", str(slot.vertex_count)),
        ]
        if override is not None:
            rows.extend(
                [
                    ("Session preview texture", override.preview_texture_resref),
                    ("Session preview state", override.status),
                    ("Session preview source", override.source_label),
                ]
            )
        if draft is not None:
            preflight = summarize_texture_patch_preflight((draft,), existing_resources=self._resources)
            plan = self._texture_patch_plan(draft)
            plan_issues = tuple(plan.issues) if plan is not None else ()
            export_state = "ready for copied module export" if plan is not None and plan.ready else "blocked by validation"
            rows.extend(
                [
                    ("Replacement", draft.replacement_texture_resref),
                    ("Replacement source", draft.replacement_source_label),
                    ("Replacement TXI", self._replacement_sidecar_summary(draft)),
                    (
                        "Replacement sidecars",
                        ", ".join(sidecar.label for sidecar in draft.replacement_sidecars) or "(none)",
                    ),
                    ("Patch preflight", preflight.source_summary),
                    ("Patched resources", preflight.patch_summary),
                    ("Bundled resources", preflight.bundle_summary),
                    ("Patch validation", "ready" if export_state.startswith("ready") else "blocked"),
                    ("Export state", export_state),
                ]
            )
            rows.extend((f"Patch issue {index}", issue.message) for index, issue in enumerate(plan_issues, start=1))
        else:
            rows.append(("Replacement", "choose a TGA/TPC texture"))
        self.material_preview.setRowCount(len(rows))
        for row_index, (field, value) in enumerate(rows):
            self.material_preview.setItem(row_index, 0, QtWidgets.QTableWidgetItem(field))
            self.material_preview.setItem(row_index, 1, QtWidgets.QTableWidgetItem(value))
        self.material_preview.resizeColumnToContents(0)
        self.material_preview.setToolTip(
            f"{slot.room_resref}.{slot.node_name} {slot.slot_kind}: {slot.texture_resref}"
        )

    def _update_texture_compare(self, replacement_resource: BrowserResource | None = None) -> None:
        slot = self._selected_material_slot
        if slot is None:
            self._clear_texture_compare()
            return
        current_resource = self._find_texture_resource(slot.texture_resref)
        self._set_texture_compare_label(
            self.current_texture_preview,
            current_resource,
            title="Current",
            fallback=f"{slot.texture_resref}\nreferenced only",
        )
        if replacement_resource is not None:
            self._set_texture_compare_label(
                self.replacement_texture_preview,
                replacement_resource,
                title="Replacement",
                fallback=replacement_resource.label,
            )
        elif self._pending_texture_replacement is not None:
            fallback = f"{self._pending_texture_replacement.replacement_texture_resref}\npreview pending"
            self._set_texture_compare_label(self.replacement_texture_preview, None, title="Replacement", fallback=fallback)
        else:
            self._set_texture_compare_label(
                self.replacement_texture_preview,
                None,
                title="Replacement",
                fallback="Choose a TGA/TPC texture",
            )

    def _set_texture_compare_label(
        self,
        label: QtWidgets.QLabel,
        resource: BrowserResource | None,
        *,
        title: str,
        fallback: str,
    ) -> None:
        label.clear()
        if resource is None:
            label.setText(f"{title}\n{fallback}")
            label.setToolTip(f"{title}: {fallback}")
            return
        preview = self._texture_preview(resource, max_size=144)
        if preview is None:
            label.setText(f"{title}\n{fallback}")
            label.setToolTip(f"{title}: {resource.label}")
            return
        label.setPixmap(self._pixmap_from_texture_preview(preview))
        label.setToolTip(f"{title}: {resource.label}\n{self._resource_source_label(resource)}")

    def _sync_selection_from_material_picker(self) -> None:
        item = self.material_picker.currentItem()
        payload = item.data(QtCore.Qt.UserRole) if item is not None else None
        if not isinstance(payload, ModuleRoomTextureSlot):
            return
        self._select_material_slot(payload, source="material picker")

    def _sync_selection_from_material_pick_panel(self) -> None:
        item = self.material_pick_panel.currentItem()
        payload = item.data(QtCore.Qt.UserRole) if item is not None else None
        if not isinstance(payload, ModuleRoomTextureSlot):
            return
        self._select_material_slot(payload, source="room material pick panel")

    def _select_material_slot(self, slot: ModuleRoomTextureSlot, *, source: str) -> None:
        self._selected_material_slot = slot
        self._pending_texture_replacement = None
        self.save_copy_action.setEnabled(False)
        self._sync_material_slot_selection(slot)
        self._update_material_preview()
        self._update_texture_compare()
        inventory = self._room_material_inventory_by_resref(slot.room_resref)
        if inventory is not None:
            self._show_room_material_board(inventory, slot)
        else:
            self.preview_label.setText(
                f"{slot.room_resref}.{slot.node_name}\n"
                f"{slot.slot_kind}: {slot.texture_resref}\n"
                "Texture is referenced but not bundled in this module archive."
            )
        self._prime_texture_browser_for_material_slot(slot)
        self.selection_label.setText(
            f"Selected material slot {slot.room_resref}.{slot.node_name} "
            f"{slot.slot_kind}: {slot.texture_resref}"
        )
        self.statusBar().showMessage(f"Selected material from {source}; choose a TGA/TPC texture to preview replacement.")

    def _prime_texture_browser_for_material_slot(self, slot: ModuleRoomTextureSlot) -> None:
        if not hasattr(self, "content_browser"):
            return
        blockers = (
            QtCore.QSignalBlocker(self.content_browser),
            QtCore.QSignalBlocker(self.content_search),
            QtCore.QSignalBlocker(self.content_type_combo),
        )
        try:
            self.content_type_combo.setCurrentText("Textures")
            self.content_search.clear()
            self.content_browser.setToolTip(
                f"Choose a TGA/TPC texture to preview replacing "
                f"{slot.room_resref}.{slot.node_name} {slot.slot_kind}: {slot.texture_resref}."
            )
            self._populate_content_browser()
            wanted = slot.texture_resref.strip().lower()
            for index in range(self.content_browser.count()):
                item = self.content_browser.item(index)
                resource = item.data(QtCore.Qt.UserRole) if item is not None else None
                if isinstance(resource, (ModuleArchiveResource, ModuleTextureFileResource, ModuleTextureLibraryResource, ModuleTextureMemoryResource)):
                    if resource.restype in {"tga", "tpc"} and resource.resref.lower() == wanted:
                        self.content_browser.setCurrentItem(item)
                        self.content_browser.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                        break
        finally:
            del blockers

    def _sync_material_slot_selection(self, slot: ModuleRoomTextureSlot) -> None:
        for widget in (self.material_picker, self.material_pick_panel):
            blocker = QtCore.QSignalBlocker(widget)
            try:
                for index in range(widget.count()):
                    item = widget.item(index)
                    if item is not None and item.data(QtCore.Qt.UserRole) == slot:
                        widget.setCurrentItem(item)
                        break
            finally:
                del blocker

    def _find_texture_resource(self, resref: str) -> BrowserResource | None:
        wanted = str(resref or "").strip().lower()
        if not wanted:
            return None
        for restype in ("tga", "tpc"):
            for resource in self._resources:
                if resource.restype == restype and resource.resref.lower() == wanted:
                    return resource
        for resource in self._imported_texture_resources:
            if resource.restype in {"tga", "tpc"} and resource.resref.lower() == wanted:
                return resource
        for resource in self._game_texture_resources:
            if resource.resref.lower() == wanted:
                return resource
        return None

    def _find_texture_sidecar_resource(self, resref: str, restype: str = "txi") -> BrowserResource | None:
        wanted = str(resref or "").strip().lower()
        wanted_type = str(restype or "").strip().lower()
        if not wanted or not wanted_type:
            return None
        for resource in self._resources:
            if resource.restype == wanted_type and resource.resref.lower() == wanted:
                return resource
        for resource in self._imported_texture_resources:
            if resource.restype == wanted_type and resource.resref.lower() == wanted:
                return resource
        for resource in self._game_texture_resources:
            if resource.restype == wanted_type and resource.resref.lower() == wanted:
                return resource
        return None

    def _texture_sidecar_summary(self, resref: str) -> str:
        resource = self._find_texture_sidecar_resource(resref, "txi")
        if resource is None:
            return "(none found)"
        return f"{resource.label} ({self._resource_source_label(resource)})"

    def _replacement_sidecar_summary(self, draft: ModuleTextureReplacementDraft) -> str:
        summaries: list[str] = []
        seen: set[str] = set()
        for sidecar in draft.replacement_sidecars:
            label = f"{sidecar.label} (bundled sidecar)"
            summaries.append(label)
            seen.add(sidecar.label.lower())
        resource = self._find_texture_sidecar_resource(draft.replacement_texture_resref, "txi")
        if resource is not None and resource.label.lower() not in seen:
            summaries.append(f"{resource.label} ({self._resource_source_label(resource)})")
        return ", ".join(summaries) or "(none found)"

    def _matching_imported_texture_sidecars(self, texture_resource: BrowserResource) -> tuple[ModuleTextureFileResource | ModuleTextureMemoryResource, ...]:
        if texture_resource.restype not in {"tga", "tpc"}:
            return ()
        wanted = texture_resource.resref.lower()
        return tuple(
            resource
            for resource in self._imported_texture_resources
            if resource.restype == "txi" and resource.resref.lower() == wanted
        )

    def _show_texture_resource_preview(self, resource: BrowserResource, caption: str) -> None:
        self._clear_room_board_hits()
        preview = self._texture_preview(resource, max_size=384)
        if preview is not None:
            self.preview_label.setPixmap(self._pixmap_from_texture_preview(preview))
            self.preview_label.setToolTip(f"{caption}\n{resource.label}")
        else:
            self.preview_label.setText(f"{caption}\n{resource.label}")

    def _texture_resource_bytes(self, resource: BrowserResource) -> bytes:
        if isinstance(resource, (ModuleTextureFileResource, ModuleTextureLibraryResource, ModuleTextureMemoryResource)):
            return resource.read_bytes()
        if self._module_path is None:
            return b""
        return read_module_resource_bytes(self._module_path, resource)

    def _resource_source_label(self, resource: BrowserResource) -> str:
        if isinstance(resource, ModuleTextureMemoryResource):
            return f"edited texture: {resource.source_label}"
        if isinstance(resource, ModuleTextureFileResource):
            return f"imported texture: {resource.path}"
        if isinstance(resource, ModuleTextureLibraryResource):
            return f"{resource.game or self._game_library_game} game library"
        return "module archive"

    def _resource_cache_key(self, resource: BrowserResource, max_size: int) -> str:
        if isinstance(resource, ModuleTextureMemoryResource):
            return f"edited:{resource.label}:{resource.size}:{resource.source_label}:{max_size}"
        if isinstance(resource, ModuleTextureFileResource):
            return f"imported:{resource.path}:{resource.size}:{resource.label}:{max_size}"
        return f"{self._resource_source_label(resource)}:{resource.label}:{max_size}"

    @staticmethod
    def _discover_game_library_textures(
        game_library: object,
        game: str,
        texture_limit: int | None,
    ) -> list[ModuleTextureLibraryResource]:
        list_textures = getattr(game_library, "list_textures", None)
        get_texture_data = getattr(game_library, "get_texture_data", None)
        get_texture = getattr(game_library, "get_texture", None)
        texture_loader = get_texture_data if callable(get_texture_data) else get_texture
        if not callable(list_textures) or not callable(texture_loader):
            return []
        try:
            names = list(list_textures(game))
        except TypeError:
            names = list(list_textures())
        except Exception:
            return []
        if texture_limit is not None:
            names = names[: max(0, int(texture_limit))]
        resources: list[ModuleTextureLibraryResource] = []
        for name in names:
            resource_game = game
            restype = "tpc"
            restype_id = 3007
            if isinstance(name, dict):
                raw_name = name.get("resref") or name.get("name") or name.get("label") or ""
                resource_game = str(name.get("game") or resource_game).upper()
                raw_type = str(name.get("type") or name.get("restype") or restype).lower().lstrip(".")
            elif isinstance(name, (tuple, list)):
                raw_name = name[0] if name else ""
                resource_game = str(name[1] if len(name) > 1 else resource_game).upper()
                raw_type = str(name[2] if len(name) > 2 else restype).lower().lstrip(".")
            else:
                raw_name = name
                raw_type = restype
            text_name = str(raw_name or "").strip().lower()
            if "." in text_name:
                text_name, suffix = text_name.rsplit(".", 1)
                raw_type = suffix or raw_type
            if raw_type == "tga":
                restype = "tga"
                restype_id = 3
            resref = text_name
            if not resref:
                continue
            resources.append(
                ModuleTextureLibraryResource(
                    resref=resref,
                    restype=restype,
                    restype_id=restype_id,
                    source="game library",
                    game=resource_game,
                    data_loader=lambda resref=resref, game=resource_game: texture_loader(resref, game),
                )
            )
        return resources

    def _texture_replacement_rows(self, draft: ModuleTextureReplacementDraft) -> list[tuple[str, str]]:
        preflight = summarize_texture_patch_preflight((draft,), existing_resources=self._resources)
        plan = self._texture_patch_plan(draft)
        plan_issues = tuple(plan.issues) if plan is not None else ()
        rows = [
            ("Pending replacement", draft.summary),
            ("Replacement status", "preview only; source archive bytes unchanged"),
            ("Replacement source", draft.replacement_source_label),
            ("Replacement sidecars", ", ".join(sidecar.label for sidecar in draft.replacement_sidecars) or "(none)"),
            ("Replacement scope", draft.target.editable_scope),
            ("Patch preflight", preflight.source_summary),
            ("Patched resources", preflight.patch_summary),
            ("Bundled resources", preflight.bundle_summary),
            ("Patch validation", "ready" if plan is not None and plan.ready else "blocked"),
            ("Export behavior", "writes a rebuilt module copy with patched MDL texture refs"),
        ]
        rows.extend((f"Patch issue {index}", issue.message) for index, issue in enumerate(plan_issues, start=1))
        match_count = self._matching_material_slot_count(draft.original_texture_resref)
        if match_count > 1:
            rows.append(("Matching texture uses", f"{match_count} diffuse slot(s) can be staged together"))
        return rows

    def _texture_patch_plan(self, draft: ModuleTextureReplacementDraft):
        if self._module_path is None:
            return None
        return build_texture_patch_plan(
            self._module_path,
            self._module_export_default_path("texture_patch"),
            (draft,),
        )

    def _matching_material_slot_count(self, texture_resref: str) -> int:
        wanted = str(texture_resref or "").strip().lower()
        if not wanted:
            return 0
        return sum(
            1
            for slot in self._all_material_slots()
            if slot.slot_kind == "diffuse" and slot.texture_resref.lower() == wanted
        )

    def _current_pending_edit(self) -> QueuedModuleEditDraft | None:
        for draft in (
            self._pending_texture_replacement,
            self._pending_wok_surface_paint,
            self._pending_layout_edit,
            self._pending_git_object_edit,
            self._pending_template_field_edit,
            self._pending_metadata_field_edit,
            self._pending_logic_field_edit,
        ):
            if draft is not None:
                return draft
        return None

    def _update_export_action_enabled(self) -> None:
        pending = self._current_pending_edit()
        pending_ready = self._edit_draft_ready(pending)
        staged_ready = bool(self._staged_edits)
        self.stage_edit_action.setEnabled(pending_ready)
        self.stage_matching_textures_action.setEnabled(
            isinstance(pending, ModuleTextureReplacementDraft) and pending_ready
        )
        self.save_copy_action.setEnabled(pending_ready or staged_ready)
        self.clear_staged_edits_action.setEnabled(staged_ready)

    def _edit_draft_ready(self, draft: QueuedModuleEditDraft | None) -> bool:
        if draft is None:
            return False
        if isinstance(draft, ModuleTextureReplacementDraft):
            plan = self._texture_patch_plan(draft)
            return bool(plan is not None and plan.ready)
        return bool(getattr(draft, "ready", False))

    def _partition_patch_ready_texture_drafts(
        self,
        drafts: tuple[ModuleTextureReplacementDraft, ...],
    ) -> tuple[tuple[ModuleTextureReplacementDraft, ...], tuple[tuple[ModuleTextureReplacementDraft, tuple[ModuleTexturePatchIssue, ...]], ...]]:
        ready: list[ModuleTextureReplacementDraft] = []
        blocked: list[tuple[ModuleTextureReplacementDraft, tuple[ModuleTexturePatchIssue, ...]]] = []
        for draft in drafts:
            plan = self._texture_patch_plan(draft)
            if plan is not None and plan.ready:
                ready.append(draft)
                continue
            blocked.append((draft, tuple(plan.issues) if plan is not None else ()))
        return tuple(ready), tuple(blocked)

    def _stage_current_edit(self) -> None:
        draft = self._current_pending_edit()
        if draft is None or not self._edit_draft_ready(draft):
            self.statusBar().showMessage("Preview a valid edit before staging it.")
            self._update_export_action_enabled()
            return
        summary = describe_module_edit_draft(draft)
        if any(describe_module_edit_draft(existing) == summary for existing in self._staged_edits):
            self.statusBar().showMessage("That edit is already staged.")
            self._update_export_action_enabled()
            return
        self._staged_edits.append(draft)
        self._refresh_edit_queue()
        if isinstance(draft, ModuleTextureReplacementDraft):
            self._refresh_material_views_for_room(draft.target.room_resref)
            self._update_material_preview()
        self.statusBar().showMessage(f"Staged edit {len(self._staged_edits)}: {summary}")

    def _stage_matching_texture_replacements(self) -> None:
        draft = self._pending_texture_replacement
        if draft is None or not self._edit_draft_ready(draft):
            self.statusBar().showMessage("Preview a valid texture replacement before staging matching texture uses.")
            self._update_export_action_enabled()
            return
        replacement_resource = self._find_texture_resource(draft.replacement_texture_resref)
        if replacement_resource is None:
            self.statusBar().showMessage("Replacement texture resource is no longer available in the Module Editor browser.")
            self._update_export_action_enabled()
            return
        slots = self._all_material_slots()
        try:
            drafts = create_texture_replacement_drafts_for_matching_slots(
                slots,
                replacement_resource,
                original_texture_resref=draft.original_texture_resref,
                sidecar_resources=self._matching_imported_texture_sidecars(replacement_resource),
            )
        except Exception as exc:
            self.statusBar().showMessage(str(exc))
            self._update_export_action_enabled()
            return
        ready_drafts, blocked_drafts = self._partition_patch_ready_texture_drafts(tuple(drafts))
        added = 0
        duplicate_count = 0
        for item in ready_drafts:
            summary = describe_module_edit_draft(item)
            if any(describe_module_edit_draft(existing) == summary for existing in self._staged_edits):
                duplicate_count += 1
                continue
            self._staged_edits.append(item)
            added += 1
        self._refresh_edit_queue()
        self._refresh_material_views_for_room(draft.target.room_resref)
        self._update_material_preview()
        if blocked_drafts or duplicate_count:
            rows = [
                ("Matching texture staging", f"{added} staged, {len(blocked_drafts)} blocked, {duplicate_count} already staged"),
                ("Original texture", draft.original_texture_resref),
                ("Replacement texture", draft.replacement_texture_resref),
                ("Patch validation", "ready" if not blocked_drafts else "partial"),
            ]
            for index, (blocked_draft, issues) in enumerate(blocked_drafts[:6], start=1):
                message = "; ".join(issue.message for issue in issues) or "Patch target is not export-ready."
                rows.append((f"Blocked target {index}", f"{blocked_draft.target.room_resref}.{blocked_draft.target.node_name}: {message}"))
            if len(blocked_drafts) > 6:
                rows.append(("Blocked target count", f"{len(blocked_drafts) - 6} additional target(s) skipped"))
            self._set_details(rows)
        if blocked_drafts:
            self.statusBar().showMessage(
                f"Staged {added} patch-ready matching texture replacement(s); skipped {len(blocked_drafts)} blocked target(s)."
            )
            return
        self.statusBar().showMessage(
            f"Staged {added} matching texture replacement(s) for {draft.original_texture_resref} -> {draft.replacement_texture_resref}."
        )

    def _all_material_slots(self) -> tuple[ModuleRoomTextureSlot, ...]:
        slots: list[ModuleRoomTextureSlot] = []
        for resource in self._resources:
            if resource.restype != "mdl":
                continue
            inventory = self._room_material_inventory(resource)
            slots.extend(inventory.slots)
        return tuple(slots)

    def _texture_usage_slots(self, texture_resref: str) -> tuple[ModuleRoomTextureSlot, ...]:
        inventories: list[ModuleRoomMaterialInventory] = []
        for resource in self._resources:
            if resource.restype != "mdl":
                continue
            inventory = self._room_material_inventory(resource)
            if inventory.slots:
                inventories.append(inventory)
        return find_texture_usage_slots(tuple(inventories), texture_resref)

    def _clear_staged_edits(self) -> None:
        texture_rooms = {
            draft.target.room_resref
            for draft in self._staged_edits
            if isinstance(draft, ModuleTextureReplacementDraft)
        }
        self._staged_edits.clear()
        self._refresh_edit_queue()
        for room_resref in texture_rooms:
            self._refresh_material_views_for_room(room_resref)
        self._update_material_preview()
        self.statusBar().showMessage("Cleared staged Module Editor edits.")

    def _refresh_edit_queue(self) -> None:
        if not hasattr(self, "edit_queue"):
            return
        self.edit_queue.clear()
        if not self._staged_edits:
            item = QtWidgets.QListWidgetItem("No staged edits")
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.edit_queue.addItem(item)
            if hasattr(self, "edit_queue_preflight_label"):
                text = "Queued export preflight: no staged edits"
                self.edit_queue_preflight_label.setText(text)
                self.edit_queue_preflight_label.setToolTip(text)
                self.edit_queue.setToolTip("Staged edits that will be exported together into one copied module archive.")
        else:
            preflight = summarize_queued_module_patch_preflight(self._staged_edits, existing_resources=self._resources)
            preflight_text = f"Queued export preflight: {preflight.summary}"
            if preflight.issues:
                preflight_text = f"{preflight_text}; {len(preflight.issues)} issue(s)"
            if hasattr(self, "edit_queue_preflight_label"):
                self.edit_queue_preflight_label.setText(preflight_text)
                self.edit_queue_preflight_label.setToolTip(
                    "\n".join(
                        [
                            preflight.source_summary,
                            f"Patched resources: {preflight.patch_summary}",
                            f"Bundled resources: {preflight.bundle_summary}",
                            f"Preserved source resources: {preflight.preserve_summary}",
                            *[issue.message for issue in preflight.issues],
                        ]
                    )
                )
                self.edit_queue.setToolTip(self.edit_queue_preflight_label.toolTip())
            for index, draft in enumerate(self._staged_edits, start=1):
                item = QtWidgets.QListWidgetItem(f"{index}. {describe_module_edit_draft(draft)}")
                item.setToolTip(describe_module_edit_draft(draft))
                self.edit_queue.addItem(item)
        self._update_export_action_enabled()

    def _export_texture_patch_copy(self) -> None:
        if self._module_path is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Open a module before exporting.")
            return
        if self._staged_edits:
            self._export_queued_patch_copy()
            return
        if self._pending_layout_edit is not None:
            self._export_layout_patch_copy()
            return
        if self._pending_metadata_field_edit is not None:
            self._export_metadata_field_patch_copy()
            return
        if self._pending_logic_field_edit is not None:
            self._export_logic_field_patch_copy()
            return
        if self._pending_template_field_edit is not None:
            self._export_template_field_patch_copy()
            return
        if self._pending_git_object_edit is not None:
            self._export_git_object_patch_copy()
            return
        if self._pending_wok_surface_paint is not None:
            self._export_wok_surface_patch_copy()
            return
        if self._pending_texture_replacement is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a texture replacement or WOK surface paint before exporting.")
            return
        default_name = self._module_export_default_path("texture_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_texture_patch_export_copy(
                self._module_path,
                path,
                (self._pending_texture_replacement,),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported patched module copy and texture patch manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe patched module copy and GhostRigger texture patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_queued_patch_copy(self) -> None:
        if self._module_path is None or not self._staged_edits:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Stage one or more previewed edits before exporting a queued module copy.")
            return
        preflight = summarize_queued_module_patch_preflight(self._staged_edits, existing_resources=self._resources)
        if not preflight.ready:
            QtWidgets.QMessageBox.warning(
                self,
                "Module Editor",
                "\n".join(issue.message for issue in preflight.issues) or "Queued edits are not ready for export.",
            )
            return
        default_name = self._module_export_default_path("queued_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export queued module edit copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_queued_module_patch_export_copy(
                self._module_path,
                path,
                tuple(self._staged_edits),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported queued module copy with {result.edit_count} edit(s): {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                f"Exported a safe queued module copy with {result.edit_count} staged edit(s).\n\n"
                f"Patched resources: {preflight.patch_summary}\n"
                f"Bundled resources: {preflight.bundle_summary}\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_template_field_patch_copy(self) -> None:
        if self._module_path is None or self._pending_template_field_edit is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a template edit before exporting.")
            return
        default_name = self._module_export_default_path("template_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_template_field_patch_export_copy(
                self._module_path,
                path,
                self._pending_template_field_edit,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported template-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe template-patched module copy and GhostRigger template patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_layout_patch_copy(self) -> None:
        if self._module_path is None or self._pending_layout_edit is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a layout edit before exporting.")
            return
        default_name = self._module_export_default_path("layout_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_layout_patch_export_copy(
                self._module_path,
                path,
                self._pending_layout_edit,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported layout-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe layout-patched module copy and GhostRigger layout patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_metadata_field_patch_copy(self) -> None:
        if self._module_path is None or self._pending_metadata_field_edit is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a metadata edit before exporting.")
            return
        default_name = self._module_export_default_path("metadata_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_metadata_field_patch_export_copy(
                self._module_path,
                path,
                self._pending_metadata_field_edit,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported metadata-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe metadata-patched module copy and GhostRigger metadata patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_logic_field_patch_copy(self) -> None:
        if self._module_path is None or self._pending_logic_field_edit is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a DLG edit before exporting.")
            return
        default_name = self._module_export_default_path("logic_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_logic_field_patch_export_copy(
                self._module_path,
                path,
                self._pending_logic_field_edit,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported DLG-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe DLG-patched module copy and GhostRigger logic patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_git_object_patch_copy(self) -> None:
        if self._module_path is None or self._pending_git_object_edit is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview a GIT object edit before exporting.")
            return
        default_name = self._module_export_default_path("git_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_git_object_patch_export_copy(
                self._module_path,
                path,
                self._pending_git_object_edit,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported GIT-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe GIT-patched module copy and GhostRigger GIT patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _export_wok_surface_patch_copy(self) -> None:
        if self._module_path is None or self._pending_wok_surface_paint is None:
            QtWidgets.QMessageBox.information(self, "Module Editor", "Preview WOK surface paint before exporting.")
            return
        default_name = self._module_export_default_path("wok_patch")
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export edited module copy",
            str(default_name),
            "KotOR module archives (*.mod *.rim *.erf);;All files (*.*)",
        )
        if not path:
            return
        try:
            result = write_wok_surface_patch_export_copy(
                self._module_path,
                path,
                self._pending_wok_surface_paint,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Module Editor", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported WOK-patched module copy and manifest: {Path(result.manifest_path).name}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            (
                "Exported a safe WOK-patched module copy and GhostRigger WOK patch manifest.\n\n"
                f"Module copy: {result.output_module}\n"
                f"Patch manifest: {result.manifest_path}\n\n"
                "The source module was not overwritten."
            ),
        )

    def _sync_selection_from_details(self) -> None:
        selected = self.details.selectedIndexes()
        if not selected:
            return
        row = selected[0].row()
        payload = self._details_row_payloads.get(row)
        if isinstance(payload, ModuleRoomTextureSlot):
            self._select_material_slot(payload, source="details table")
            return
        if isinstance(payload, ModuleGitObjectRow):
            self._select_git_object_row(payload, source="details table")
            return
        if isinstance(payload, ModuleWokSurfaceSummary):
            self._select_wok_surface_summary(payload, source="details table")
            return
        if isinstance(payload, ModuleTemplateField):
            self._select_template_field(payload, source="details table")
            return
        if isinstance(payload, ModuleMetadataField):
            self._select_metadata_field(payload, source="details table")
            return
        if isinstance(payload, ModuleLayoutRoomRow):
            self._select_layout_room_row(payload, source="details table")
            return
        if isinstance(payload, ModuleVisibilityRow):
            self._select_visibility_row(payload, source="details table")
            return
        if isinstance(payload, ModuleLogicField):
            self._select_logic_field(payload, source="details table")
            return
        if isinstance(payload, ModuleAuditFilterTarget):
            self._select_audit_filter_target(payload, source="details table")
            return

    def _set_details(self, rows: list[tuple[str, str]], *, row_payloads: dict[int, object] | None = None) -> None:
        self._details_row_payloads = dict(row_payloads or {})
        self.details.setRowCount(len(rows))
        for row_index, (field, value) in enumerate(rows):
            field_item = QtWidgets.QTableWidgetItem(field)
            value_item = QtWidgets.QTableWidgetItem(value)
            payload = self._details_row_payloads.get(row_index)
            if isinstance(payload, ModuleRoomTextureSlot):
                tooltip = (
                    f"Select this row to show {payload.room_resref}.{payload.node_name} "
                    "on the room material board."
                )
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleGitObjectRow):
                tooltip = f"Select this row to edit {payload.object_type}.{payload.index} in the GIT object editor."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleWokSurfaceSummary):
                first_face = payload.face_indices[0] if payload.face_indices else "n/a"
                tooltip = (
                    f"Select this row to target face {first_face} and surface "
                    f"{payload.surface_id} {payload.surface_name} in the WOK editor."
                )
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleTemplateField):
                state = "edit" if payload.editable else "inspect"
                tooltip = f"Select this row to {state} template field {payload.label} ({payload.key})."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleMetadataField):
                state = "edit" if payload.editable else "inspect"
                tooltip = f"Select this row to {state} metadata field {payload.label} ({payload.key})."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleLayoutRoomRow):
                tooltip = f"Select this row to edit LYT room {payload.room_resref} coordinates."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleVisibilityRow):
                tooltip = f"Select this row to edit VIS links from {payload.room_resref}."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleLogicField):
                state = "edit" if payload.editable else "inspect"
                tooltip = f"Select this row to {state} logic field {payload.label} ({payload.key})."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            elif isinstance(payload, ModuleAuditFilterTarget):
                tooltip = f"Select this row to filter the content browser to {payload.kind} {payload.value} resources."
                field_item.setToolTip(tooltip)
                value_item.setToolTip(tooltip)
            self.details.setItem(row_index, 0, field_item)
            self.details.setItem(row_index, 1, value_item)
        self.details.resizeColumnToContents(0)
