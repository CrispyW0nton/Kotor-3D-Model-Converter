"""GhostRigger Map Studio Level Editor window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject, LevelScene, LevelTransform
from src.core.modules.authored_module_export import authored_module_smoke_summary_lines
from src.core.modules.module_editor_controller import ModuleEditorController
from src.gui.panels.module_editor.blueprints_tab import BlueprintsTab
from src.gui.panels.module_editor.builder_tab import BuilderTab
from src.gui.panels.module_editor.export_panel import ModuleExportPanel
from src.gui.panels.module_editor.module_editor_asset_browser import ModuleEditorAssetBrowser
from src.gui.panels.module_editor.module_editor_outliner import ModuleEditorOutliner
from src.gui.panels.module_editor.module_editor_properties import ModuleEditorPropertiesPanel
from src.gui.panels.module_editor.module_editor_toolbar import ModuleEditorToolbar
from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel
from src.gui.panels.module_editor.porter_tab import PorterTab
from src.gui.panels.module_editor.readiness_panel import ModuleReadinessPanel
from src.gui.panels.module_editor.rooms_tab import RoomsTab
from src.gui.panels.module_editor.validation_panel import ModuleValidationPanel
from src.gui.panels.module_editor.walkmesh_tab import WalkmeshTab
from src.gui.panels.module_editor.workflow_panel import MapStudioWorkflowPanel
from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE


class _MapStudioGameProofDialog(QtWidgets.QDialog):
    """Collect manual KOTOR smoke-test proof before marking a module tested."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, proof_manifest_path: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Record Map Studio Game Proof")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        self.proof_manifest_edit = QtWidgets.QLineEdit(proof_manifest_path)
        self.proof_manifest_edit.setObjectName("mapStudioProofManifestLineEdit")
        proof_browse = QtWidgets.QPushButton("Browse...")
        proof_browse.setObjectName("mapStudioProofManifestBrowseButton")
        proof_row = QtWidgets.QHBoxLayout()
        proof_row.addWidget(self.proof_manifest_edit, 1)
        proof_row.addWidget(proof_browse)
        form.addRow("Proof manifest", proof_row)

        self.evidence_edit = QtWidgets.QLineEdit()
        self.evidence_edit.setObjectName("mapStudioProofEvidenceLineEdit")
        evidence_browse = QtWidgets.QPushButton("Browse...")
        evidence_browse.setObjectName("mapStudioProofEvidenceBrowseButton")
        evidence_row = QtWidgets.QHBoxLayout()
        evidence_row.addWidget(self.evidence_edit, 1)
        evidence_row.addWidget(evidence_browse)
        form.addRow("Screenshot/video", evidence_row)

        self.tester_edit = QtWidgets.QLineEdit()
        self.tester_edit.setObjectName("mapStudioProofTesterLineEdit")
        form.addRow("Tester", self.tester_edit)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("mapStudioProofNotesEdit")
        self.notes_edit.setMaximumHeight(90)
        form.addRow("Notes", self.notes_edit)

        checks_box = QtWidgets.QGroupBox("KOTOR in-game acceptance checks")
        checks_box.setObjectName("mapStudioProofChecksGroupBox")
        checks_layout = QtWidgets.QVBoxLayout(checks_box)
        self.module_loads_box = QtWidgets.QCheckBox("`warp` loads the generated module in KOTOR")
        self.module_loads_box.setObjectName("mapStudioProofModuleLoadsCheckBox")
        self.player_floor_box = QtWidgets.QCheckBox("Player appears on the generated floor, not in void")
        self.player_floor_box.setObjectName("mapStudioProofPlayerFloorCheckBox")
        self.placeable_visible_box = QtWidgets.QCheckBox("Authored/test placeable appears where expected")
        self.placeable_visible_box.setObjectName("mapStudioProofPlaceableVisibleCheckBox")
        self.walkable_floor_box = QtWidgets.QCheckBox("Player can walk across the generated floor")
        self.walkable_floor_box.setObjectName("mapStudioProofWalkableFloorCheckBox")
        self.allow_missing_evidence_box = QtWidgets.QCheckBox("Record incomplete attempt if evidence file is missing")
        self.allow_missing_evidence_box.setObjectName("mapStudioProofAllowMissingEvidenceCheckBox")
        for widget in (
            self.module_loads_box,
            self.player_floor_box,
            self.placeable_visible_box,
            self.walkable_floor_box,
            self.allow_missing_evidence_box,
        ):
            checks_layout.addWidget(widget)
        layout.addWidget(checks_box)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        proof_browse.clicked.connect(self._browse_proof_manifest)
        evidence_browse.clicked.connect(self._browse_evidence)

    def values(self) -> dict[str, Any]:
        return {
            "proof_manifest_path": self.proof_manifest_edit.text().strip(),
            "evidence_path": self.evidence_edit.text().strip(),
            "tester": self.tester_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
            "module_loads_in_game": self.module_loads_box.isChecked(),
            "player_spawns_on_floor": self.player_floor_box.isChecked(),
            "test_placeable_visible": self.placeable_visible_box.isChecked(),
            "player_can_walk_on_floor": self.walkable_floor_box.isChecked(),
            "allow_missing_evidence": self.allow_missing_evidence_box.isChecked(),
        }

    def _browse_proof_manifest(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Map Studio proof manifest",
            self.proof_manifest_edit.text().strip(),
            "Proof manifest (*.json);;All files (*.*)",
        )
        if path:
            self.proof_manifest_edit.setText(path)

    def _browse_evidence(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select KOTOR screenshot or video evidence",
            self.evidence_edit.text().strip(),
            "Evidence (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov *.mkv);;All files (*.*)",
        )
        if path:
            self.evidence_edit.setText(path)


class _MapStudioLaunchHandoffDialog(QtWidgets.QDialog):
    """Show the exact manual warp-test handoff before opening KOTOR."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        warp_command: str,
        launcher_path: str = "",
        proof_manifest_path: str = "",
        proof_recording_script_path: str = "",
        launch_helper_command: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Map Studio Warp Test Handoff")
        self.setModal(True)
        root = QtWidgets.QVBoxLayout(self)

        self.warning_label = QtWidgets.QLabel(
            "Launching KOTOR is not game proof. After the game opens, run the exact warp command, "
            "verify spawn/walk/placeables in-game, then record proof with screenshot or video evidence."
        )
        self.warning_label.setObjectName("mapStudioLaunchHandoffWarningLabel")
        self.warning_label.setWordWrap(True)
        root.addWidget(self.warning_label)

        form = QtWidgets.QFormLayout()
        root.addLayout(form)

        self.warp_command_edit = QtWidgets.QLineEdit(warp_command)
        self.warp_command_edit.setObjectName("mapStudioLaunchWarpCommandLineEdit")
        self.warp_command_edit.setReadOnly(True)
        copy_warp_button = QtWidgets.QPushButton("Copy")
        copy_warp_button.setObjectName("mapStudioLaunchCopyWarpCommandButton")
        warp_row = QtWidgets.QHBoxLayout()
        warp_row.addWidget(self.warp_command_edit, 1)
        warp_row.addWidget(copy_warp_button)
        form.addRow("Run this exact KOTOR console command", warp_row)

        self.launcher_path_edit = QtWidgets.QLineEdit(launcher_path)
        self.launcher_path_edit.setObjectName("mapStudioLaunchScriptPathLineEdit")
        self.launcher_path_edit.setReadOnly(True)
        form.addRow("Launch script", self.launcher_path_edit)

        self.proof_manifest_edit = QtWidgets.QLineEdit(proof_manifest_path)
        self.proof_manifest_edit.setObjectName("mapStudioLaunchProofManifestLineEdit")
        self.proof_manifest_edit.setReadOnly(True)
        form.addRow("Proof manifest", self.proof_manifest_edit)

        self.proof_recorder_edit = QtWidgets.QLineEdit(proof_recording_script_path)
        self.proof_recorder_edit.setObjectName("mapStudioLaunchProofRecorderLineEdit")
        self.proof_recorder_edit.setReadOnly(True)
        form.addRow("Proof recorder", self.proof_recorder_edit)

        self.helper_command_edit = QtWidgets.QPlainTextEdit(launch_helper_command)
        self.helper_command_edit.setObjectName("mapStudioLaunchHelperCommandEdit")
        self.helper_command_edit.setReadOnly(True)
        self.helper_command_edit.setMaximumHeight(64)
        form.addRow("CLI helper", self.helper_command_edit)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText(
            "Open Launcher" if launcher_path else "Open Proof Folder"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        copy_warp_button.clicked.connect(
            lambda: QtGui.QGuiApplication.clipboard().setText(self.warp_command_edit.text())
        )


class _MapStudioNewProjectDialog(QtWidgets.QDialog):
    """Collect the KOTOR-facing identity for a new Map Studio KMAP."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        module_root: str = "grdev01",
        game: str = "K1",
        author: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Map Studio KMAP")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        self.hint_label = QtWidgets.QLabel(
            "Create a KMAP project with the KOTOR module root it will eventually export as. "
            "Use a resref-safe name: 16 characters or fewer, letters, numbers, and underscores."
        )
        self.hint_label.setObjectName("mapStudioNewProjectHintLabel")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        self.module_root_edit = QtWidgets.QLineEdit(module_root or "grdev01")
        self.module_root_edit.setObjectName("mapStudioNewProjectModuleRootLineEdit")
        self.module_root_edit.setPlaceholderText("grdev01")
        form.addRow("Module root / KMAP name", self.module_root_edit)

        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.setObjectName("mapStudioNewProjectGameComboBox")
        self.game_combo.addItem("Knights of the Old Republic (K1)", "K1")
        self.game_combo.addItem("The Sith Lords (K2)", "K2")
        index = self.game_combo.findData(str(game or "K1").upper())
        self.game_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Target game", self.game_combo)

        self.author_edit = QtWidgets.QLineEdit(author or "")
        self.author_edit.setObjectName("mapStudioNewProjectAuthorLineEdit")
        self.author_edit.setPlaceholderText("modder name or team")
        form.addRow("Author", self.author_edit)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "name": self.module_root_edit.text().strip(),
            "game": str(self.game_combo.currentData() or "K1"),
            "author": self.author_edit.text().strip(),
        }


class _MapStudioToolBeltCustomizeDialog(QtWidgets.QDialog):
    """Choose which Map Studio actions appear in the session tool belt."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        actions: tuple[Any, ...] = (),
        selected_keys: tuple[str, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize Map Studio Tool Belt")
        self.setModal(True)
        root = QtWidgets.QVBoxLayout(self)
        self.hint_label = QtWidgets.QLabel(
            "Choose the modeling, terrain, gameplay, and validation actions you want in the active tool belt. "
            "This custom belt is kept for the current Map Studio session."
        )
        self.hint_label.setObjectName("mapStudioToolBeltCustomizeHintLabel")
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)
        self.action_list = QtWidgets.QListWidget()
        self.action_list.setObjectName("mapStudioToolBeltCustomizeListWidget")
        root.addWidget(self.action_list, 1)

        selected = {str(key) for key in selected_keys}
        for action in actions:
            key = str(getattr(action, "key", "") or "")
            if not key:
                continue
            item = QtWidgets.QListWidgetItem(str(getattr(action, "label", key) or key))
            item.setData(QtCore.Qt.UserRole, key)
            tooltip = str(getattr(action, "description", "") or "")
            guardrail = str(getattr(action, "kotor_guardrail", "") or "")
            if guardrail:
                tooltip = f"{tooltip}\nKOTOR: {guardrail}" if tooltip else f"KOTOR: {guardrail}"
            item.setToolTip(tooltip)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if key in selected else QtCore.Qt.Unchecked)
            self.action_list.addItem(item)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_action_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        for row in range(self.action_list.count()):
            item = self.action_list.item(row)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                key = str(item.data(QtCore.Qt.UserRole) or "")
                if key:
                    keys.append(key)
        return tuple(keys)


class ModuleEditorWindow(QtWidgets.QMainWindow):
    """Top-level KMAP Map Studio Level Editor window."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        theme_manager: Any = None,
        layout_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setWindowTitle("GhostRigger Map Studio - Level Editor")
        self.controller = ModuleEditorController()
        self.theme_manager = theme_manager or getattr(parent, "theme_manager", None)
        self.layout_manager = layout_manager or getattr(parent, "layout_manager", None)
        self._last_output_dir = ""
        self._library_rows: list[dict[str, Any]] = []
        self._map_studio_workspace_modes: dict[str, Any] = {}
        self._map_studio_custom_belt_keys: tuple[str, ...] = ()
        self._syncing_map_studio_tool_belt_preferences = False
        self.resource_manager: Any = None
        self._build_actions()
        self._build_menus()
        self._build_ui()
        self._connect()
        self.set_renderer_settings(RendererSettings.from_settings(getattr(parent, "settings_data", {}) or {}))
        self.set_navigation_profile(
            getattr(parent, "settings_data", {}).get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
            if parent is not None
            else DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        )
        self._refresh_all()
        if self.layout_manager is not None:
            self.apply_ghost_layout(self.layout_manager.current_layout or self.layout_manager.get_layout())
        if self.theme_manager is not None:
            self.apply_ghost_theme(self.theme_manager.current_theme or self.theme_manager.get_theme())

    @property
    def project(self) -> KMapProject:
        return self.controller.project

    def _build_actions(self) -> None:
        self.new_action = QtGui.QAction("New KMAP", self)
        self.open_action = QtGui.QAction("Open KMAP...", self)
        self.save_action = QtGui.QAction("Save KMAP", self)
        self.save_as_action = QtGui.QAction("Save KMAP As...", self)
        self.import_module_action = QtGui.QAction("Import Module...", self)
        self.import_library_asset_action = QtGui.QAction("Import Selected Library Asset", self)
        self.export_fbx_action = QtGui.QAction("Export FBX...", self)
        self.export_package_action = QtGui.QAction("Export Scene Package...", self)
        self.close_action = QtGui.QAction("Close", self)
        self.undo_action = QtGui.QAction("Undo", self)
        self.redo_action = QtGui.QAction("Redo", self)
        self.delete_action = QtGui.QAction("Delete Selected", self)
        self.duplicate_action = QtGui.QAction("Duplicate Selected", self)
        self.rename_action = QtGui.QAction("Rename Selected", self)
        self.validate_action = QtGui.QAction("Validate KMAP", self)
        self.build_action = QtGui.QAction("Build Module Files", self)
        self.generate_walls_action = QtGui.QAction("Generate Walls", self)
        self.paint_walkmesh_action = QtGui.QAction("Paint Walkmesh Faces", self)
        self.open_output_action = QtGui.QAction("Open Output Folder", self)
        self.help_action = QtGui.QAction("Map Studio Help", self)
        self.kmap_help_action = QtGui.QAction("KMAP Format Help", self)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        for action in (self.new_action, self.open_action, self.save_action, self.save_as_action):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.import_module_action)
        file_menu.addAction(self.import_library_asset_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_fbx_action)
        file_menu.addAction(self.export_package_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_action)

        edit_menu = self.menuBar().addMenu("Edit")
        for action in (self.undo_action, self.redo_action, self.delete_action, self.duplicate_action, self.rename_action):
            edit_menu.addAction(action)

        view_menu = self.menuBar().addMenu("View")
        self.outliner_action = view_menu.addAction("Show Outliner")
        self.outliner_action.setCheckable(True)
        self.outliner_action.setChecked(True)
        self.properties_action = view_menu.addAction("Show Properties")
        self.properties_action.setCheckable(True)
        self.properties_action.setChecked(True)
        self.viewport_action = view_menu.addAction("Show Viewport")
        self.viewport_action.setCheckable(True)
        self.viewport_action.setChecked(True)
        self.validation_action = view_menu.addAction("Show Validation Panel")
        self.validation_action.setCheckable(True)
        self.validation_action.setChecked(True)
        view_menu.addAction("Reset Layout").triggered.connect(self._reset_layout)

        tools_menu = self.menuBar().addMenu("Tools")
        for action in (self.validate_action, self.build_action, self.generate_walls_action, self.paint_walkmesh_action, self.open_output_action):
            tools_menu.addAction(action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.help_action)
        help_menu.addAction(self.kmap_help_action)

    def _build_ui(self) -> None:
        shell = QtWidgets.QWidget()
        self.setCentralWidget(shell)
        root = QtWidgets.QVBoxLayout(shell)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)
        self.toolbar = ModuleEditorToolbar(self)
        root.addWidget(self.toolbar)
        self.map_studio_scope_label = QtWidgets.QLabel(
            "Map Studio Level Editor: KMAP terrain, rooms, walkmesh, placements, validation, staged export, install handoff, and game proof."
        )
        self.map_studio_scope_label.setObjectName("mapStudioLevelEditorScopeLabel")
        self.map_studio_scope_label.setWordWrap(True)
        root.addWidget(self.map_studio_scope_label)
        workspace_row = QtWidgets.QHBoxLayout()
        workspace_row.setContentsMargins(0, 0, 0, 0)
        workspace_row.setSpacing(6)
        self.map_studio_workspace_label = QtWidgets.QLabel("Workspace")
        self.map_studio_workspace_label.setObjectName("mapStudioWorkspaceLabel")
        self.map_studio_workspace_combo = QtWidgets.QComboBox()
        self.map_studio_workspace_combo.setObjectName("mapStudioWorkspaceComboBox")
        for mode in self.controller.map_studio_workspace_modes():
            key = str(getattr(mode, "key", "") or "")
            if not key:
                continue
            self._map_studio_workspace_modes[key] = mode
            self.map_studio_workspace_combo.addItem(str(getattr(mode, "label", key) or key), key)
        self.map_studio_workspace_guide_label = QtWidgets.QLabel("")
        self.map_studio_workspace_guide_label.setObjectName("mapStudioWorkspaceGuideLabel")
        self.map_studio_workspace_guide_label.setWordWrap(True)
        self.map_studio_open_workspace_button = QtWidgets.QPushButton("Open Workspace")
        self.map_studio_open_workspace_button.setObjectName("mapStudioOpenWorkspaceButton")
        workspace_row.addWidget(self.map_studio_workspace_label)
        workspace_row.addWidget(self.map_studio_workspace_combo)
        workspace_row.addWidget(self.map_studio_workspace_guide_label, 1)
        workspace_row.addWidget(self.map_studio_open_workspace_button)
        root.addLayout(workspace_row)
        belt_row = QtWidgets.QHBoxLayout()
        belt_row.setContentsMargins(0, 0, 0, 0)
        belt_row.setSpacing(6)
        self.map_studio_tool_belt_label = QtWidgets.QLabel("Tool Belt")
        self.map_studio_tool_belt_label.setObjectName("mapStudioToolBeltLabel")
        self.map_studio_tool_belt_preset_combo = QtWidgets.QComboBox()
        self.map_studio_tool_belt_preset_combo.setObjectName("mapStudioToolBeltPresetComboBox")
        for preset in self.controller.available_map_studio_tool_belt_presets():
            self.map_studio_tool_belt_preset_combo.addItem(str(getattr(preset, "label", "") or preset.key), str(preset.key))
        self.map_studio_tool_belt_widget = QtWidgets.QWidget()
        self.map_studio_tool_belt_widget.setObjectName("mapStudioToolBeltWidget")
        self.map_studio_tool_belt_layout = QtWidgets.QHBoxLayout(self.map_studio_tool_belt_widget)
        self.map_studio_tool_belt_layout.setContentsMargins(0, 0, 0, 0)
        self.map_studio_tool_belt_layout.setSpacing(4)
        self.map_studio_customize_tool_belt_button = QtWidgets.QPushButton("Customize Belt...")
        self.map_studio_customize_tool_belt_button.setObjectName("mapStudioCustomizeToolBeltButton")
        belt_row.addWidget(self.map_studio_tool_belt_label)
        belt_row.addWidget(self.map_studio_tool_belt_preset_combo)
        belt_row.addWidget(self.map_studio_tool_belt_widget, 1)
        belt_row.addWidget(self.map_studio_customize_tool_belt_button)
        root.addLayout(belt_row)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root.addWidget(self.main_splitter, 1)

        left = QtWidgets.QWidget()
        left.setMinimumWidth(240)
        left.setMaximumWidth(380)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.outliner = ModuleEditorOutliner(left)
        self.asset_browser = ModuleEditorAssetBrowser(left)
        self.left_tabs = QtWidgets.QTabWidget()
        self.left_tabs.addTab(self.outliner, "Outliner")
        self.left_tabs.addTab(self.asset_browser, "Assets")
        self.workflow_tabs = QtWidgets.QTabWidget()
        self.rooms_tab = RoomsTab()
        self.walkmesh_tab = WalkmeshTab()
        self.porter_tab = PorterTab()
        self.builder_tab = BuilderTab()
        self.builder_tab.set_primitive_presets(self.controller.available_authored_room_presets())
        self.builder_tab.set_terrain_shape_presets(self.controller.available_authored_terrain_shape_presets())
        self.builder_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())
        self.walkmesh_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())
        self.builder_tab.set_composition_primitive_kinds(self.controller.available_authored_composition_primitive_kinds())
        self.builder_tab.set_gameplay_placement_kinds(self.controller.available_authored_gameplay_placement_kinds())
        self.builder_tab.set_script_hook_fields(self.controller.authored_script_hook_field_choices())
        self.builder_tab.set_modeling_component_modes(self.controller.available_map_studio_component_modes())
        self.builder_tab.set_modeling_tools(self.controller.available_map_studio_modeling_tools())
        self.builder_tab.set_modeling_snap_modes(self.controller.available_map_studio_snap_modes())
        self.builder_tab.set_terrain_brushes(self.controller.available_map_studio_terrain_brushes())
        self.blueprints_tab = BlueprintsTab()
        for label, widget in (
            ("Rooms", self.rooms_tab),
            ("Walkmesh", self.walkmesh_tab),
            ("Porter", self.porter_tab),
            ("Builder", self.builder_tab),
            ("Blueprints", self.blueprints_tab),
        ):
            self.workflow_tabs.addTab(widget, label)
        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.left_tabs)
        self.left_splitter.addWidget(self.workflow_tabs)
        self.left_splitter.setStretchFactor(0, 3)
        self.left_splitter.setStretchFactor(1, 2)
        self.left_splitter.setSizes([520, 340])
        left_layout.addWidget(self.left_splitter, 1)
        self.main_splitter.addWidget(left)

        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.viewport_panel = ModuleEditorViewportPanel(center)
        center_layout.addWidget(self.viewport_panel, 1)
        self.main_splitter.addWidget(center)

        right = QtWidgets.QWidget()
        right.setMinimumWidth(260)
        right.setMaximumWidth(520)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.properties = ModuleEditorPropertiesPanel(right)
        self.workflow_panel = MapStudioWorkflowPanel(right)
        self.readiness_panel = ModuleReadinessPanel(right)
        self.export_panel = ModuleExportPanel(right)
        self.right_tabs = QtWidgets.QTabWidget()
        self.right_tabs.setObjectName("mapStudioRightTabs")
        self.right_tabs.addTab(self.properties, "Properties")
        export_page = QtWidgets.QWidget(self.right_tabs)
        self.map_studio_export_page = export_page
        export_layout = QtWidgets.QVBoxLayout(export_page)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.addWidget(self.workflow_panel)
        export_layout.addWidget(self.readiness_panel)
        export_layout.addWidget(self.export_panel)
        self.right_tabs.addTab(export_page, "Export")
        right_layout.addWidget(self.right_tabs, 1)
        self.main_splitter.addWidget(right)

        self.bottom_tabs = QtWidgets.QTabWidget()
        self.validation_panel = ModuleValidationPanel()
        self.output_log = QtWidgets.QPlainTextEdit()
        self.output_log.setReadOnly(True)
        self.bottom_tabs.addTab(self.validation_panel, "Validation")
        self.bottom_tabs.addTab(self.output_log, "Output")
        self.bottom_tabs.setMinimumHeight(82)
        self.bottom_tabs.setMaximumHeight(165)
        root.addWidget(self.bottom_tabs)
        self.statusBar().showMessage("Map Studio Level Editor ready.")
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([285, 1220, 320])
        self._update_map_studio_workspace_guide()
        self._refresh_map_studio_tool_belt()

    def _connect(self) -> None:
        self.new_action.triggered.connect(self.new_kmap)
        self.open_action.triggered.connect(self.open_kmap)
        self.save_action.triggered.connect(self.save_kmap)
        self.save_as_action.triggered.connect(self.save_kmap_as)
        self.import_module_action.triggered.connect(self.import_module)
        self.import_library_asset_action.triggered.connect(self.import_selected_library_asset)
        self.export_fbx_action.triggered.connect(lambda: self.export_fbx(False))
        self.export_package_action.triggered.connect(lambda: self.build_module_files())
        self.close_action.triggered.connect(self.close)
        self.delete_action.triggered.connect(self.delete_selected)
        self.duplicate_action.triggered.connect(self.duplicate_selected)
        self.rename_action.triggered.connect(self.rename_selected)
        self.validate_action.triggered.connect(self.validate_kmap)
        self.build_action.triggered.connect(self.build_module_files)
        self.generate_walls_action.triggered.connect(lambda: self._handle_tab_action("Generate Walls"))
        self.paint_walkmesh_action.triggered.connect(lambda: self._handle_tab_action("Paint Face"))
        self.open_output_action.triggered.connect(self.open_output_folder)
        self.help_action.triggered.connect(lambda: self._show_help("Map Studio"))
        self.kmap_help_action.triggered.connect(lambda: self._show_help("KMAP Format"))
        self.map_studio_workspace_combo.currentIndexChanged.connect(self._handle_map_studio_workspace_changed)
        self.map_studio_open_workspace_button.clicked.connect(lambda: self._open_selected_map_studio_workspace())
        self.map_studio_tool_belt_preset_combo.currentIndexChanged.connect(self._handle_map_studio_tool_belt_preset_changed)
        self.map_studio_customize_tool_belt_button.clicked.connect(self._customize_map_studio_tool_belt)
        self.toolbar.actionRequested.connect(self._toolbar_action)
        self.toolbar.viewModeChanged.connect(self.viewport_panel.set_view_mode)
        self.toolbar.selectionModeChanged.connect(self._handle_map_studio_edit_mode_changed)
        self.asset_browser.importRequested.connect(self.import_library_asset)
        self.outliner.itemSelected.connect(self.select_item)
        self.outliner.actionRequested.connect(self._outliner_action)
        self.viewport_panel.itemSelected.connect(self.select_item)
        self.viewport_panel.transformEdited.connect(self._set_transform)
        self.viewport_panel.roomOutlinePointEdited.connect(self._set_authored_room_outline_point)
        self.viewport_panel.roomPrimitiveSelected.connect(self._select_authored_room_primitive)
        self.viewport_panel.roomPrimitiveMoved.connect(self._move_authored_room_primitive)
        self.viewport_panel.terrainBrushFrameRequested.connect(self.apply_map_studio_viewport_terrain_brush_frame)
        self.viewport_panel.terrainBrushStrokeCommitted.connect(self.commit_map_studio_viewport_terrain_brush_stroke)
        self.validation_panel.issueActivated.connect(self.select_item)
        self.readiness_panel.gameTestRequested.connect(self.record_game_smoke_proof)
        self.readiness_panel.launchHandoffRequested.connect(self.open_map_studio_launch_handoff)
        self.workflow_panel.newProjectRequested.connect(self.new_kmap)
        self.workflow_panel.openProjectRequested.connect(self.open_kmap)
        self.workflow_panel.saveProjectRequested.connect(self.save_kmap)
        self.workflow_panel.renameSelectedRequested.connect(self.rename_selected)
        self.workflow_panel.duplicateSelectedRequested.connect(self.duplicate_selected)
        self.workflow_panel.deleteSelectedRequested.connect(self.delete_selected)
        self.workflow_panel.focusSelectedRequested.connect(self.viewport_panel.focus_selected)
        self.workflow_panel.builderRequested.connect(self.show_map_studio_builder)
        self.workflow_panel.geometryToolsRequested.connect(self.show_map_studio_geometry_tools)
        self.workflow_panel.starterRoomRequested.connect(self.create_map_studio_starter_room)
        self.workflow_panel.doorwayBlockoutRequested.connect(self.create_map_studio_doorway_blockout)
        self.workflow_panel.corridorRequested.connect(self.create_map_studio_corridor)
        self.workflow_panel.starterTerrainRequested.connect(self.create_map_studio_starter_terrain)
        self.workflow_panel.terrainToolsRequested.connect(self.show_map_studio_terrain_tools)
        self.workflow_panel.lightingToolsRequested.connect(self.show_map_studio_lighting_tools)
        self.workflow_panel.placementToolsRequested.connect(self.show_map_studio_placement_tools)
        self.workflow_panel.scriptToolsRequested.connect(self.show_map_studio_script_tools)
        self.workflow_panel.testPlaceableRequested.connect(self.add_map_studio_test_placeable)
        self.workflow_panel.walkmeshToolsRequested.connect(self.show_map_studio_walkmesh_tools)
        self.workflow_panel.validateRequested.connect(self.validate_kmap)
        self.workflow_panel.stageRequested.connect(lambda: self.stage_authored_module(self.export_panel.dry_run.isChecked()))
        self.workflow_panel.installRequested.connect(lambda: self.install_authored_module(self.export_panel.dry_run.isChecked()))
        self.workflow_panel.launchHandoffRequested.connect(self.open_map_studio_launch_handoff)
        self.workflow_panel.proofRequested.connect(self.record_game_smoke_proof)
        self.properties.transformChanged.connect(self._set_transform)
        self.properties.visibilityChanged.connect(lambda item_id, value: self._set_visibility(item_id, value))
        self.properties.lockChanged.connect(lambda item_id, value: self._set_locked(item_id, value))
        self.properties.propertyChanged.connect(self._set_property)
        self.properties.transitionChanged.connect(self._set_authored_gameplay_transition)
        self.properties.cameraChanged.connect(self._set_authored_gameplay_camera_properties)
        self.properties.roomLightChanged.connect(self._set_authored_room_light_properties)
        self.export_panel.exportRequested.connect(self.export_fbx)
        self.export_panel.devTestModuleRequested.connect(self.stage_dev_test_module)
        self.export_panel.authoredModuleRequested.connect(self.export_authored_module)
        self.export_panel.authoredModuleStageRequested.connect(self.stage_authored_module)
        self.export_panel.authoredModuleInstallRequested.connect(self.install_authored_module)
        for tab in (self.rooms_tab, self.walkmesh_tab, self.porter_tab, self.builder_tab, self.blueprints_tab):
            tab.actionRequested.connect(self._handle_tab_action)
        self.builder_tab.primitivePresetRequested.connect(self.create_authored_room_preset)
        self.builder_tab.roomOperationRequested.connect(self.apply_authored_room_operation)
        self.builder_tab.floorPlanExtrusionRequested.connect(self.apply_authored_floor_plan_extrusion)
        self.builder_tab.floorPlanOpeningRequested.connect(self.set_authored_floor_plan_wall_opening)
        self.builder_tab.floorPlanOpeningMarkerRequested.connect(self.create_authored_opening_transition_marker)
        self.builder_tab.floorPlanVertexSnapRequested.connect(self.snap_authored_floor_plan_vertex)
        self.builder_tab.floorPlanVertexWeldRequested.connect(self.weld_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexFlattenRequested.connect(self.flatten_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexCleanupRequested.connect(self.cleanup_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexMirrorRequested.connect(self.mirror_authored_floor_plan_vertices)
        self.builder_tab.floorPlanFaceFillRequested.connect(self.fill_authored_floor_plan_face)
        self.builder_tab.floorPlanFaceTriangulateRequested.connect(self.triangulate_authored_floor_plan_face)
        self.builder_tab.floorPlanNormalsCleanupRequested.connect(self.cleanup_authored_floor_plan_normals)
        self.builder_tab.terrainOperationRequested.connect(self.apply_authored_terrain_operation)
        self.builder_tab.terrainLiveBrushFrameRequested.connect(self.preview_map_studio_terrain_sculpt_frame)
        for combo_name in ("terrainRoomComboBox", "terrainBrushComboBox"):
            combo = getattr(self.builder_tab, combo_name, None)
            if combo is not None:
                combo.currentIndexChanged.connect(lambda _index=0: self._sync_map_studio_terrain_brush_context())
        terrain_radius = getattr(self.builder_tab, "terrainRadiusSpinBox", None)
        if terrain_radius is not None:
            terrain_radius.valueChanged.connect(lambda _value=0: self._sync_map_studio_terrain_brush_context())
        self.builder_tab.roomRectangularUnionRequested.connect(self.merge_authored_floor_plan_rooms)
        self.builder_tab.floorPlanBridgeRequested.connect(self.bridge_authored_floor_plan_edges)
        self.builder_tab.roomPrimitiveAddRequested.connect(self.add_authored_room_primitive)
        self.builder_tab.roomPrimitiveTransformRequested.connect(self.apply_authored_room_primitive_transform)
        self.builder_tab.roomPrimitiveDimensionsRequested.connect(self.apply_authored_room_primitive_dimensions)
        self.builder_tab.roomPrimitiveStyleRequested.connect(self.apply_authored_room_primitive_style)
        self.builder_tab.roomPrimitiveRemoveRequested.connect(self.remove_authored_room_primitive)
        self.builder_tab.roomPrimitiveSeparateRequested.connect(self.separate_authored_room_primitive)
        self.builder_tab.roomStyleRequested.connect(self.apply_authored_room_style)
        self.walkmesh_tab.roomSurfaceRequested.connect(self.apply_authored_walkmesh_surface)
        self.builder_tab.roomLightRequested.connect(self.add_authored_room_light)
        self.builder_tab.moduleEntryPointRequested.connect(self.set_authored_module_entry_point)
        self.builder_tab.gameplayPlacementRequested.connect(self.add_authored_gameplay_placement)
        self.builder_tab.gameplayPlacementStatusChanged.connect(self.workflow_panel.set_active_authoring_context)
        self.builder_tab.modelingContextChanged.connect(self.workflow_panel.set_active_authoring_context)
        self.builder_tab.scriptHookRequested.connect(self.set_authored_script_hook)
        self.outliner_action.toggled.connect(lambda visible: self.outliner.setVisible(visible))
        self.properties_action.toggled.connect(lambda visible: self.properties.setVisible(visible))
        self.viewport_action.toggled.connect(lambda visible: self.viewport_panel.setVisible(visible))
        self.validation_action.toggled.connect(lambda visible: self.bottom_tabs.setVisible(visible))

    def new_kmap(self) -> None:
        if not self._confirm_discard_or_save():
            return
        dialog = _MapStudioNewProjectDialog(
            self,
            module_root=str(getattr(self.project, "name", "") or "grdev01"),
            game=str(getattr(self.project, "game", "") or "K1"),
            author=str(getattr(self.project, "author", "") or ""),
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            project = self.controller.new_project(**dialog.values())
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "New Map Studio KMAP", str(exc))
            return
        self._refresh_all(f"Created Map Studio KMAP {project.name} for {project.game}.")

    def open_kmap(self) -> None:
        if not self._confirm_discard_or_save():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open KMAP", "", "GhostRigger KMAP (*.kmap);;JSON files (*.json);;All files (*.*)")
        if not path:
            return
        try:
            self.controller.open_project(path)
            self._refresh_all(f"Opened {Path(path).name}.")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Open KMAP", str(exc))

    def save_kmap(self) -> None:
        if not self.project.path:
            self.save_kmap_as()
            return
        self.controller.save_project()
        self._refresh_all(f"Saved {Path(self.project.path).name}.")

    def save_kmap_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save KMAP As", f"{self.project.name}.kmap", "GhostRigger KMAP (*.kmap)")
        if not path:
            return
        if not path.lower().endswith(".kmap"):
            path += ".kmap"
        self.controller.save_project(path)
        self._refresh_all(f"Saved {Path(path).name}.")

    def import_module(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Import module folder", "")
        if not path:
            return
        module = self.controller.add_module(Path(path).name, source_path=path)
        self._refresh_all(f"Imported module reference {module.module_name}.")

    def set_library_rows(self, rows: list[dict[str, Any]]) -> None:
        self._library_rows = [dict(row) for row in rows]
        self.asset_browser.set_rows(self._library_rows)
        self.builder_tab.set_gameplay_palette_entries(self.controller.authored_gameplay_palette_entries(self._library_rows))

    def set_renderer_settings(self, settings: RendererSettings | dict | None) -> None:
        renderer_settings = settings if isinstance(settings, RendererSettings) else RendererSettings.from_settings(settings or {})
        viewport_panel = getattr(self, "viewport_panel", None)
        if viewport_panel is not None and hasattr(viewport_panel, "set_renderer_settings"):
            viewport_panel.set_renderer_settings(renderer_settings)

    def import_selected_library_asset(self) -> None:
        row = self.asset_browser.selected_row()
        if not row:
            self.left_tabs.setCurrentWidget(self.asset_browser)
            self._log("Select an asset in the Assets tab first.")
            return
        self.import_library_asset(row)

    def import_library_asset(self, row: dict[str, Any]) -> None:
        try:
            item = self.controller.import_library_asset(row, resource_manager=self.resource_manager)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Import Library Asset", str(exc))
            return
        item_name = getattr(item, "name", getattr(item, "module_name", str(row.get("resref", "asset"))))
        self.left_tabs.setCurrentWidget(self.outliner)
        self._refresh_all(f"Imported library asset {item_name}.")

    def delete_selected(self) -> None:
        if self.controller.remove_selected():
            self._refresh_all("Deleted selected item.")

    def duplicate_selected(self) -> None:
        if self.controller.duplicate_selected() is not None:
            self._refresh_all("Duplicated selected item.")

    def rename_selected(self) -> None:
        item_id = self.controller.model.selected_ids[0] if self.controller.model.selected_ids else ""
        if not item_id:
            return
        if item_id.startswith("authored:"):
            authored = next((row for row in self.controller.authored_gameplay_placements() if getattr(row, "placement_id", "") == item_id), None)
            if authored is None:
                return
            current = str(getattr(authored, "tag", "") or getattr(authored, "template_resref", "") or item_id)
            name, ok = QtWidgets.QInputDialog.getText(self, "Rename Authored Placement", "Name:", text=current)
            if ok and name.strip():
                try:
                    self.controller.rename_authored_gameplay_placement(item_id, tag=name.strip())
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(self, "Rename Authored Placement", str(exc))
                    return
                self._refresh_all("Renamed authored gameplay placement.")
            return
        if item_id.startswith("authored_light:"):
            light = next((row for row in self.controller.authored_room_lights() if getattr(row, "light_id", "") == item_id), None)
            if light is None:
                return
            current = str(getattr(light, "name", "") or item_id)
            name, ok = QtWidgets.QInputDialog.getText(self, "Rename Authored Room Light", "Name:", text=current)
            if ok and name.strip():
                try:
                    self.controller.rename_authored_room_light(item_id, name=name.strip())
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(self, "Rename Authored Room Light", str(exc))
                    return
                self._refresh_all("Renamed authored room light.")
            return
        item = self.project.find_room(item_id) or self.project.find_module(item_id) or self.project.find_blueprint(item_id)
        if item is None:
            return
        current = getattr(item, "name", getattr(item, "module_name", ""))
        name, ok = QtWidgets.QInputDialog.getText(self, "Rename Selected", "Name:", text=current)
        if ok and name.strip():
            self._set_property(item_id, "name", name.strip())

    def validate_kmap(self) -> None:
        issues = self.controller.validate()
        self.validation_panel.set_issues(issues)
        errors = sum(1 for issue in issues if issue.severity.lower() == "error")
        self._log(f"Validation complete: {len(issues)} issue(s), {errors} error(s).")
        self.bottom_tabs.setCurrentWidget(self.validation_panel)

    def _selected_map_studio_workspace_key(self) -> str:
        return str(self.map_studio_workspace_combo.currentData() or "").strip()

    def _update_map_studio_workspace_guide(self) -> None:
        key = self._selected_map_studio_workspace_key()
        mode = self._map_studio_workspace_modes.get(key)
        if mode is None:
            self.map_studio_workspace_guide_label.setText(
                "Choose the Map Studio workspace for the current KOTOR level-authoring task."
            )
            return
        summary = str(getattr(mode, "summary", "") or "")
        next_action = str(getattr(mode, "next_action", "") or "")
        text = summary
        if next_action:
            text = f"{summary} Next: {next_action}" if summary else f"Next: {next_action}"
        self.map_studio_workspace_guide_label.setText(text)

    def _handle_map_studio_workspace_changed(self, _index: int) -> None:
        self._update_map_studio_workspace_guide()
        self._open_selected_map_studio_workspace(log_focus=False)

    def _open_selected_map_studio_workspace(self, *, log_focus: bool = True) -> None:
        key = self._selected_map_studio_workspace_key()
        if key == "geometry":
            self.show_map_studio_geometry_tools()
        elif key == "terrain":
            self.show_map_studio_terrain_tools()
        elif key == "walkmesh":
            self.show_map_studio_walkmesh_tools()
        elif key == "placements":
            self.show_map_studio_placement_tools()
        elif key == "lighting":
            self.show_map_studio_lighting_tools()
        elif key == "scripts":
            self.show_map_studio_script_tools()
        elif key == "export":
            self.right_tabs.setCurrentWidget(self.map_studio_export_page)
            self.workflow_panel.set_active_authoring_context(
                "Export + Game Proof: validate, stage/install, warp test, then record proof"
            )
            if log_focus:
                self._log("Map Studio export and game-proof workspace focused.")
        else:
            self.left_tabs.setCurrentWidget(self.outliner)
            self.workflow_panel.set_active_authoring_context(
                "Project: KMAP identity, target game, outliner, asset browser, and save/open state"
            )
            if log_focus:
                self._log("Map Studio project workspace focused.")

    def _selected_map_studio_tool_belt_preset_key(self) -> str:
        return str(self.map_studio_tool_belt_preset_combo.currentData() or "blockout").strip() or "blockout"

    def _apply_map_studio_tool_belt_preferences_from_project(self) -> None:
        preferences = self.controller.map_studio_tool_belt_preferences()
        preset_key = str(getattr(preferences, "preset_key", "blockout") or "blockout")
        custom_keys = tuple(str(item) for item in getattr(preferences, "custom_action_keys", ()) or ())
        self._syncing_map_studio_tool_belt_preferences = True
        try:
            self._map_studio_custom_belt_keys = custom_keys
            index = self.map_studio_tool_belt_preset_combo.findData(preset_key)
            if index < 0:
                index = self.map_studio_tool_belt_preset_combo.findData("blockout")
            if index >= 0 and self.map_studio_tool_belt_preset_combo.currentIndex() != index:
                self.map_studio_tool_belt_preset_combo.setCurrentIndex(index)
        finally:
            self._syncing_map_studio_tool_belt_preferences = False

    def _persist_map_studio_tool_belt_preferences(self) -> None:
        if self._syncing_map_studio_tool_belt_preferences:
            return
        self.controller.set_map_studio_tool_belt_preferences(
            preset_key=self._selected_map_studio_tool_belt_preset_key(),
            custom_action_keys=self._map_studio_custom_belt_keys,
        )

    def _handle_map_studio_tool_belt_preset_changed(self, _index: int) -> None:
        self._persist_map_studio_tool_belt_preferences()
        self._refresh_map_studio_tool_belt()

    def _clear_map_studio_tool_belt_layout(self) -> None:
        while self.map_studio_tool_belt_layout.count():
            item = self.map_studio_tool_belt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_map_studio_tool_belt(self) -> None:
        self._clear_map_studio_tool_belt_layout()
        preset_key = self._selected_map_studio_tool_belt_preset_key()
        actions = self.controller.map_studio_tool_belt_actions_for_preset(
            preset_key,
            custom_action_keys=self._map_studio_custom_belt_keys,
        )
        if not actions and preset_key == "custom":
            placeholder = QtWidgets.QLabel("Customize the belt to choose visible tools.")
            placeholder.setObjectName("mapStudioToolBeltEmptyCustomLabel")
            self.map_studio_tool_belt_layout.addWidget(placeholder)
            self.map_studio_tool_belt_layout.addStretch(1)
            return
        for action in actions:
            key = str(getattr(action, "key", "") or "")
            if not key:
                continue
            button = QtWidgets.QToolButton()
            button.setObjectName(f"mapStudioToolBeltButton_{key}")
            button.setText(str(getattr(action, "label", key) or key))
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            button.setEnabled(bool(getattr(action, "implemented", False)))
            tooltip = str(getattr(action, "description", "") or "")
            hotkey = str(getattr(action, "hotkey", "") or "")
            guardrail = str(getattr(action, "kotor_guardrail", "") or "")
            if hotkey:
                tooltip = f"{tooltip}\nHotkey: {hotkey}" if tooltip else f"Hotkey: {hotkey}"
            if guardrail:
                tooltip = f"{tooltip}\nKOTOR: {guardrail}" if tooltip else f"KOTOR: {guardrail}"
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, tool_action=action: self._handle_map_studio_tool_belt_action(tool_action))
            self.map_studio_tool_belt_layout.addWidget(button)
        self.map_studio_tool_belt_layout.addStretch(1)

    def _customize_map_studio_tool_belt(self) -> None:
        all_actions = self.controller.available_map_studio_tool_belt_actions()
        selected_keys = self._map_studio_custom_belt_keys
        if not selected_keys:
            selected_keys = tuple(
                str(getattr(action, "key", "") or "") for action in all_actions if bool(getattr(action, "implemented", False))
            )
        dialog = _MapStudioToolBeltCustomizeDialog(
            self,
            actions=all_actions,
            selected_keys=selected_keys,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        self._map_studio_custom_belt_keys = dialog.selected_action_keys()
        custom_index = self.map_studio_tool_belt_preset_combo.findData("custom")
        if custom_index >= 0:
            self._syncing_map_studio_tool_belt_preferences = True
            try:
                self.map_studio_tool_belt_preset_combo.setCurrentIndex(custom_index)
            finally:
                self._syncing_map_studio_tool_belt_preferences = False
        self._persist_map_studio_tool_belt_preferences()
        self._refresh_map_studio_tool_belt()
        self._log("Map Studio custom tool belt saved in this KMAP.")

    def _map_studio_belt_primitive_kind(self, action_key: str) -> str:
        """Map direct shelf buttons to authored composition primitive kinds."""

        return {
            "plane": "plane",
            "cube": "cube",
            "wall": "wall",
            "ramp": "ramp",
            "stairs": "stairs",
            "cylinder": "cylinder",
            "door_frame": "door_frame",
        }.get(str(action_key or "").strip(), "")

    def _map_studio_belt_placement_kind(self, action_key: str) -> str:
        """Map direct shelf buttons to authored KOTOR placement kinds."""

        return {
            "placeable": "placeable",
            "creature": "creature",
            "door": "door",
            "waypoint": "waypoint",
            "trigger": "trigger",
            "encounter": "encounter",
            "sound": "sound",
            "camera": "camera",
            "store": "store",
        }.get(str(action_key or "").strip(), "")

    def _map_studio_belt_terrain_brush(self, action_key: str) -> str:
        """Map direct shelf buttons to terrain sculpt brush keys."""

        return {
            "sculpt_raise": "raise",
            "sculpt_lower": "lower",
            "sculpt_smooth": "smooth",
            "sculpt_flatten": "flatten",
            "sculpt_plateau": "plateau",
            "sculpt_ramp": "ramp",
            "sculpt_terrace": "terrace",
            "sculpt_pinch": "pinch",
            "sculpt_erode": "erode",
            "sculpt_noise": "noise",
        }.get(str(action_key or "").strip(), "")

    def _focus_map_studio_entry_point_controls(self) -> None:
        """Focus Builder controls for the authored IFO player start."""

        self.show_map_studio_placement_tools()
        area = getattr(self.builder_tab, "entryPointAreaLineEdit", None)
        if area is not None:
            area.setFocus()
            area.selectAll()
        self.workflow_panel.set_active_authoring_context(
            "Entry point: edit the module IFO player start and keep it on walkable WOK"
        )
        self._log("Map Studio entry point controls focused. Set the area resref, XYZ, and facing before validation/game proof.")

    def _select_map_studio_modeling_tool(self, tool_key: str) -> None:
        """Focus the Builder modeling tool matching a belt action."""

        combo = getattr(self.builder_tab, "modelingToolComboBox", None)
        if combo is None:
            return
        wanted = str(tool_key or "").strip()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("key") or "") == wanted:
                combo.setCurrentIndex(index)
                combo.setFocus()
                return

    def _select_map_studio_gameplay_kind(self, placement_kind: str) -> None:
        """Focus the Builder placement controls for one KOTOR resource kind."""

        combo = getattr(self.builder_tab, "gameplayPlacementKindComboBox", None)
        if combo is None:
            return
        wanted = str(placement_kind or "").strip().lower()
        for index in range(combo.count()):
            if str(combo.itemData(index) or "").strip().lower() == wanted:
                combo.setCurrentIndex(index)
                break
        search = getattr(self.builder_tab, "gameplayPaletteSearchLineEdit", None)
        if search is not None:
            search.setFocus()
            search.selectAll()
        else:
            combo.setFocus()

    def _select_map_studio_terrain_brush(self, brush_key: str) -> None:
        """Focus the Builder terrain sculpt brush matching a belt action."""

        combo = getattr(self.builder_tab, "terrainBrushComboBox", None)
        if combo is None:
            return
        wanted = str(brush_key or "").strip()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("key") or "") == wanted:
                combo.setCurrentIndex(index)
                combo.setFocus()
                return

    def _handle_map_studio_tool_belt_action(self, action: Any) -> None:
        key = str(getattr(action, "key", "") or "")
        workspace_key = str(getattr(action, "workspace_key", "") or "")
        tool_key = str(getattr(action, "tool_key", "") or "")
        if key == "validate":
            self.validate_kmap()
            return
        if key == "corridor":
            self.create_map_studio_corridor()
            return
        if key == "terrain_patch":
            self.create_map_studio_starter_terrain()
            return
        if key == "entry_point":
            self._focus_map_studio_entry_point_controls()
            return
        terrain_brush = self._map_studio_belt_terrain_brush(key)
        if terrain_brush:
            self.show_map_studio_terrain_tools()
            self._select_map_studio_terrain_brush(terrain_brush)
            self._sync_map_studio_terrain_brush_context(force_enabled=True)
            return
        primitive_kind = self._map_studio_belt_primitive_kind(key)
        if primitive_kind:
            self.show_map_studio_geometry_tools()
            self.add_authored_room_primitive(primitive_kind, "")
            return
        placement_kind = self._map_studio_belt_placement_kind(key)
        if placement_kind:
            self.show_map_studio_placement_tools()
            self._select_map_studio_gameplay_kind(placement_kind)
            return
        if key in {"create_room", "primitive", "extrude", "bridge", "cut", "opening", "fill", "vertex_snap", "weld", "flatten", "mirror", "cleanup", "triangulate", "normals", "bevel", "boolean", "combine", "separate"}:
            self.show_map_studio_geometry_tools()
            if tool_key:
                self._select_map_studio_modeling_tool(tool_key)
            if key == "extrude":
                operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
                if operation_combo is not None:
                    index = operation_combo.findData("edge_extrude")
                    if index >= 0:
                        operation_combo.setCurrentIndex(index)
                    operation_combo.setFocus()
            if key == "cut":
                operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
                if operation_combo is not None:
                    index = operation_combo.findData("split_x")
                    if index >= 0:
                        operation_combo.setCurrentIndex(index)
                    operation_combo.setFocus()
            if key == "boolean":
                operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
                if operation_combo is not None:
                    index = operation_combo.findData("rectangular_cut")
                    if index >= 0:
                        operation_combo.setCurrentIndex(index)
                    operation_combo.setFocus()
            if key == "bridge":
                tool = getattr(self.builder_tab, "floorPlanBridgeFirstRoomComboBox", None)
                if tool is not None:
                    tool.setFocus()
            if key == "opening":
                tool = getattr(self.builder_tab, "floorPlanOpeningRoomComboBox", None)
                if tool is not None:
                    tool.setFocus()
            if key == "combine":
                tool = getattr(self.builder_tab, "floorPlanUnionFirstRoomComboBox", None)
                if tool is not None:
                    tool.setFocus()
            if key == "separate":
                tool = getattr(self.builder_tab, "roomPrimitiveSeparateResultLineEdit", None)
                if tool is not None:
                    tool.setFocus()
            if key in {"vertex_snap", "weld", "flatten", "mirror", "cleanup"}:
                tool = getattr(self.builder_tab, "floorPlanVertexRoomComboBox", None)
                if tool is not None:
                    tool.setFocus()
            return
        if workspace_key == "terrain":
            self.show_map_studio_terrain_tools()
        elif workspace_key == "walkmesh":
            self.show_map_studio_walkmesh_tools()
        elif workspace_key == "placements":
            self.show_map_studio_placement_tools()
        elif workspace_key == "lighting":
            self.show_map_studio_lighting_tools()
        elif workspace_key == "scripts":
            self.show_map_studio_script_tools()
        elif workspace_key == "export":
            self.right_tabs.setCurrentWidget(self.map_studio_export_page)
        else:
            self.show_map_studio_builder()

    def show_map_studio_builder(self) -> None:
        """Focus the Builder tab inside the existing Map Studio Level Editor."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        self.workflow_panel.set_active_authoring_context("Builder: room, terrain, placement, lighting, and script authoring")
        self._log("Map Studio Builder focused.")

    def _handle_map_studio_edit_mode_changed(self, mode: str) -> None:
        """Reflect the toolbar edit mode in the Map Studio workflow/readiness panel."""

        label = str(mode or "Object").strip() or "Object"
        descriptions = {
            "Object": "select, move, duplicate, and organize rooms, placements, lights, and module objects",
            "Vertex": "edit room and walkmesh vertices with snap, weld, flatten, mirror, and cleanup tools",
            "Edge": "edit seams, door or corridor borders, bridge edges, bevels, and rectangular cuts",
            "Face": "edit room faces, material intent, WOK surface intent, triangulation, and cleanup",
            "Walkmesh": "inspect and paint walkable, non-walkable, door, water, and transition faces",
            "Placement": "place and transform KOTOR creatures, placeables, doors, triggers, cameras, and waypoints",
            "Terrain": "sculpt terrain heightfields, ramps, plateaus, erosion, smoothing, and walkability",
            "Export": "validate, stage, install, hand off, warp-test, and record game proof",
        }
        context = f"{label} mode: {descriptions.get(label, 'author the active Map Studio selection')}"
        self.workflow_panel.set_active_authoring_context(context)
        self.statusBar().showMessage(f"Map Studio {context}", 5000)
        self._log(f"Map Studio edit mode changed: {context}")

    def show_map_studio_geometry_tools(self) -> None:
        """Focus Builder's primitive, operation, and modular room controls."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        primitive = getattr(self.builder_tab, "roomPrimitivePresetComboBox", None)
        if primitive is not None:
            primitive.setFocus()
        self.workflow_panel.set_active_authoring_context(
            "Geometry: primitive rooms, extrusion, bevel/inset, rectangular cuts, boolean union, and modular room pieces"
        )
        self._log("Map Studio geometry tools focused. Use Builder to create rooms, edit primitives, apply bevels/cuts, and compose modular pieces.")

    def show_map_studio_walkmesh_tools(self) -> None:
        """Focus the existing Walkmesh tab inside the Map Studio Level Editor."""

        self.workflow_tabs.setCurrentWidget(self.walkmesh_tab)
        self.workflow_panel.set_active_authoring_context("Walkmesh: inspect and paint walkable/non-walkable faces")
        self._log("Map Studio Walkmesh tools focused. Use these to inspect, load, or paint walkable faces.")

    def show_map_studio_terrain_tools(self) -> None:
        """Focus Builder's terrain heightfield controls."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        terrain = getattr(self.builder_tab, "terrainRoomComboBox", None)
        if terrain is not None:
            terrain.setFocus()
        self.workflow_panel.set_active_authoring_context("Terrain: sculpt heightfield samples and slope/walkability")
        self._sync_map_studio_terrain_brush_context()
        self._log("Map Studio terrain tools focused. Create a terrain patch, choose a heightfield room, then sculpt samples.")

    def show_map_studio_lighting_tools(self) -> None:
        """Focus Builder's authored room-light controls."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        name = getattr(self.builder_tab, "roomLightNameLineEdit", None)
        if name is not None:
            name.setFocus()
            name.selectAll()
        self.workflow_panel.set_active_authoring_context("Lighting: add authored room lights before lightmap/export checks")
        self._log("Map Studio lighting tools focused. Add authored room lights before staging lightmap-ready test builds.")

    def show_map_studio_placement_tools(self) -> None:
        """Focus Builder's authored gameplay placement controls."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        search = getattr(self.builder_tab, "gameplayPaletteSearchLineEdit", None)
        if search is not None:
            search.setFocus()
            search.selectAll()
        self.workflow_panel.set_active_authoring_context("Placement: choose a KOTOR resource template and place it in the module")
        self._log("Map Studio placement tools focused. Search the game-library palette or type a template resref.")

    def show_map_studio_script_tools(self) -> None:
        """Focus Builder's authored module/area script-hook controls."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        script = getattr(self.builder_tab, "scriptHookResrefLineEdit", None)
        if script is not None:
            script.setFocus()
            script.selectAll()
        self.workflow_panel.set_active_authoring_context("Scripts: assign ARE/IFO script hook resrefs")
        self._log("Map Studio script-hook tools focused. Assign ARE/IFO script resrefs that resolve from the package, Override, or base game.")

    def add_map_studio_test_placeable(self) -> None:
        """Add a known-safe test placeable through the existing authored placement service."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        self.add_authored_gameplay_placement(
            "placeable",
            "plc_bench",
            "map_studio_test_placeable",
            1.75,
            1.5,
            0.0,
            0.0,
        )

    def add_map_studio_camera(self) -> None:
        """Add an authored camera marker through the existing gameplay placement service."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        camera_count = sum(
            1
            for placement in self.controller.authored_gameplay_placements()
            if str(getattr(placement, "kind", "") or "").lower() == "camera"
        )
        self.add_authored_gameplay_placement(
            "camera",
            "",
            str(camera_count + 1),
            0.0,
            -2.5,
            1.6,
            0.0,
        )
        self.workflow_panel.set_active_authoring_context(
            "Camera: authored camera marker added. Move it in Properties or the viewport, then validate before export."
        )

    def add_map_studio_room_light(self) -> None:
        """Add an authored room light through the room-light service."""

        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        light_count = len(tuple(self.controller.authored_room_lights() or ()))
        self.add_authored_room_light(
            "",
            f"key_light_{light_count + 1}",
            0.0,
            0.0,
            2.25,
            1.0,
            0.92,
            0.78,
            8.0,
            1.0,
            "point",
        )
        self.workflow_panel.set_active_authoring_context(
            "Lighting: authored room light added. Tune color, radius, and position before export/lightmap checks."
        )

    def set_authored_module_entry_point(
        self,
        area_resref: str,
        x: float,
        y: float,
        z: float,
        facing: float,
    ) -> None:
        """Update the authored module IFO player start from Builder controls."""

        try:
            self.controller.set_authored_module_entry_point(
                area_resref=area_resref,
                position=(x, y, z),
                facing=facing,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Set Module Entry Point", str(exc))
            return
        self._refresh_all("Updated Map Studio module entry point/player start.")

    def create_map_studio_starter_room(self) -> None:
        """Create a small authored room through the existing Builder preset path."""

        self._create_map_studio_starter_preset(
            preset_id="rectangular_dev_room",
            module_root="grdev01",
            label="starter room",
        )

    def create_map_studio_doorway_blockout(self) -> None:
        """Create a doorway-focused authored room through the Builder preset path."""

        self._create_map_studio_starter_preset(
            preset_id="doorway_blockout",
            module_root="grdoor",
            label="doorway blockout",
        )

    def create_map_studio_corridor(self) -> None:
        """Create a corridor/hall authored room through the Builder preset path."""

        self._create_map_studio_starter_preset(
            preset_id="wide_hall",
            module_root="grhall",
            label="corridor",
        )

    def create_map_studio_starter_terrain(self) -> None:
        """Create a terrain authored module through the existing Builder preset path."""

        self._create_map_studio_starter_preset(
            preset_id="terrain_heightfield",
            module_root="grterrain",
            label="terrain patch",
        )

    def _create_map_studio_starter_preset(self, *, preset_id: str, module_root: str, label: str) -> None:
        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        module_root_edit = getattr(self.builder_tab, "moduleRootLineEdit", None)
        if module_root_edit is not None:
            module_root_edit.setText(module_root)
        self._log(f"Creating Map Studio {label} from Builder preset {preset_id}.")
        self.create_authored_room_preset(preset_id, module_root)

    def build_module_files(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder", self._last_output_dir or "")
        if not path:
            return
        result = self.controller.build_preview(path)
        self._last_output_dir = result.output_dir
        self._log(result.message)
        if result.manifest_path:
            self._log(f"Manifest: {result.manifest_path}")
        self.validate_kmap()

    def stage_dev_test_module(self, dry_run: bool = False) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Stage grdev01 dev test module", self._last_output_dir or "")
        if not path:
            return
        result = self.controller.stage_dev_test_module(path, dry_run=dry_run)
        self._last_output_dir = path
        self._log(result.message)
        export_result = result.export_result
        if export_result is not None:
            if export_result.module_path:
                self._log(f"Package: {export_result.module_path}")
            if export_result.manifest_path:
                self._log(f"Manifest: {export_result.manifest_path}")
        if result.checklist_path:
            self._log(f"Game-test checklist: {result.checklist_path}")
        if result.proof_manifest_path:
            self._log(f"Proof manifest: {result.proof_manifest_path}")
        if getattr(result, "launch_helper_command", ""):
            self._log(f"Launch dry-run helper: {result.launch_helper_command}")
        if getattr(result, "elevated_launch_script_path", ""):
            self._log(f"Elevated launch helper: {result.elevated_launch_script_path}")
        if getattr(result, "proof_recording_script_path", ""):
            self._log(f"Proof recorder: {result.proof_recording_script_path}")
        for warning in result.warnings:
            self._log(f"Warning: {warning}")
        for issue in result.blocking_issues:
            self._log(f"Blocking: {issue}")

    def export_authored_module(self, dry_run: bool = False) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Export authored KMAP module", self._last_output_dir or "")
        if not path:
            return
        try:
            result = self.controller.export_authored_module(path, dry_run=dry_run)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Export Authored Module", str(exc))
            return
        self._last_output_dir = path
        self._log(result.message)
        if result.module_path:
            self._log(f"Package: {result.module_path}")
        if result.manifest_path:
            self._log(f"Manifest: {result.manifest_path}")
        for line in authored_module_smoke_summary_lines(result):
            self._log(line)
        for warning in result.warnings:
            self._log(f"Warning: {warning}")
        for issue in result.blocking_issues:
            self._log(f"Blocking: {issue}")
        self._refresh_all("Authored module export state updated.")

    def stage_authored_module(self, dry_run: bool = False) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Stage authored module for game test", self._last_output_dir or "")
        if not path:
            return
        try:
            result = self.controller.stage_authored_module(path, dry_run=dry_run)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Stage Authored Module", str(exc))
            return
        self._last_output_dir = path
        self._log(result.message)
        export_result = result.export_result
        if export_result is not None:
            if export_result.module_path:
                self._log(f"Package: {export_result.module_path}")
            if export_result.manifest_path:
                self._log(f"Manifest: {export_result.manifest_path}")
        if result.installed_module_path:
            self._log(f"Installed module: {result.installed_module_path}")
        if result.checklist_path:
            self._log(f"Game-test checklist: {result.checklist_path}")
        if result.proof_manifest_path:
            self._log(f"Proof manifest: {result.proof_manifest_path}")
        if export_result is not None:
            for line in authored_module_smoke_summary_lines(export_result):
                self._log(line)
        for warning in result.warnings:
            self._log(f"Warning: {warning}")
        for issue in result.blocking_issues:
            self._log(f"Blocking: {issue}")
        self._refresh_all("Authored module game-test staging updated.")

    def install_authored_module(self, dry_run: bool = False) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Stage authored module package and proof files", self._last_output_dir or "")
        if not path:
            return
        modules_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select KOTOR Modules folder", "")
        if not modules_path:
            return
        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
        module_root = str(payload.get("module_root") or getattr(self.project, "name", "") or "authored").strip().lower()
        destination = Path(modules_path) / f"{module_root}.mod"
        overwrite = False
        if destination.exists():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Install Authored Module",
                f"{destination.name} already exists in the selected Modules folder.\n\n"
                "GhostRigger will create a .bak backup before replacing it. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
            overwrite = True
        try:
            result = self.controller.stage_authored_module(
                path,
                dry_run=dry_run,
                game_modules_dir=modules_path,
                overwrite=overwrite,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Install Authored Module", str(exc))
            return
        self._last_output_dir = path
        self._log(result.message)
        export_result = result.export_result
        if export_result is not None:
            if export_result.module_path:
                self._log(f"Package: {export_result.module_path}")
            if export_result.manifest_path:
                self._log(f"Manifest: {export_result.manifest_path}")
        if result.installed_module_path:
            self._log(f"Installed module: {result.installed_module_path}")
        if result.backup_module_path:
            self._log(f"Backup module: {result.backup_module_path}")
        if result.checklist_path:
            self._log(f"Game-test checklist: {result.checklist_path}")
        if result.proof_manifest_path:
            self._log(f"Proof manifest: {result.proof_manifest_path}")
        if export_result is not None:
            for line in authored_module_smoke_summary_lines(export_result):
                self._log(line)
        for warning in result.warnings:
            self._log(f"Warning: {warning}")
        for issue in result.blocking_issues:
            self._log(f"Blocking: {issue}")
        if not result.ok:
            QtWidgets.QMessageBox.warning(self, "Install Authored Module", result.message)
        self._refresh_all("Authored module game-test install updated.")

    def record_game_smoke_proof(self) -> None:
        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
        default_manifest = str(payload.get("proof_manifest_path") or "")
        dialog = _MapStudioGameProofDialog(self, proof_manifest_path=default_manifest)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        values = dialog.values()
        if not values["proof_manifest_path"]:
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", "Choose the proof manifest written by the Map Studio stage action.")
            return
        if not values["evidence_path"] and not values["allow_missing_evidence"]:
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", "Choose screenshot or video evidence from the actual KOTOR test.")
            return
        result = self.controller.record_map_studio_game_proof(**values)
        self._log(result.message)
        if getattr(result, "proof_manifest_path", ""):
            self._log(f"Proof manifest: {result.proof_manifest_path}")
        if getattr(result, "pack_manifest_path", ""):
            self._log(f"Pack manifest: {result.pack_manifest_path}")
        if getattr(result, "evidence_path", ""):
            self._log(f"Evidence: {result.evidence_path}")
        for warning in getattr(result, "warnings", ()):
            self._log(f"Warning: {warning}")
        for issue in getattr(result, "blocking_issues", ()):
            self._log(f"Blocking: {issue}")
        if not getattr(result, "ok", False):
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", result.message)
        self._refresh_all("Map Studio game proof updated.")

    def open_map_studio_launch_handoff(self) -> None:
        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
        launcher_path = Path(str(payload.get("elevated_launch_script_path") or ""))
        proof_path = Path(str(payload.get("proof_manifest_path") or ""))
        proof_recorder_path = Path(str(payload.get("proof_recording_script_path") or ""))
        module_root = str(payload.get("module_root") or getattr(self.project, "name", "") or "").strip()
        warp_command = str(payload.get("warp_command") or (f"warp {module_root}" if module_root else "warp <module>"))
        launch_helper_command = str(payload.get("launch_helper_command") or "")
        if launcher_path.is_file() or proof_path.is_file():
            dialog = _MapStudioLaunchHandoffDialog(
                self,
                warp_command=warp_command,
                launcher_path=str(launcher_path) if launcher_path.is_file() else "",
                proof_manifest_path=str(proof_path) if proof_path.is_file() else "",
                proof_recording_script_path=str(proof_recorder_path) if proof_recorder_path.is_file() else "",
                launch_helper_command=launch_helper_command,
            )
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            if launcher_path.is_file():
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(launcher_path)))
                self._log(f"Opened launch handoff: {launcher_path}")
            elif proof_path.is_file():
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(proof_path.parent)))
                self._log(f"Opened proof folder: {proof_path.parent}")
            self._log(f"Map Studio warp command: {warp_command}")
            return
        QtWidgets.QMessageBox.information(
            self,
            "Open Launch Handoff",
            "Stage or install an authored module game-test package before opening the launch handoff.",
        )

    def create_authored_room_preset(self, preset_id: str, module_root: str) -> None:
        try:
            result = self.controller.create_authored_room_preset_module(preset_id=preset_id, module_root=module_root)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Create Authored Room Primitive", str(exc))
            return
        readiness = result.readiness
        message = f"Created authored module {self.project.name} from primitive preset {preset_id}."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_room_operation(
        self,
        operation: str,
        distance: float,
        edge_index: int,
        cut_center_x: float,
        cut_center_y: float,
        cut_width: float,
        cut_depth: float,
    ) -> None:
        try:
            if operation == "rectangular_cut":
                result = self.controller.apply_authored_room_operation(
                    operation=operation,
                    center=(cut_center_x, cut_center_y),
                    size=(cut_width, cut_depth),
                )
            elif operation in {"split_x", "split_y"}:
                result = self.controller.apply_authored_room_operation(
                    operation=operation,
                    axis="x" if operation == "split_x" else "y",
                    coordinate=cut_center_x if operation == "split_x" else cut_center_y,
                )
            elif operation == "edge_extrude":
                result = self.controller.apply_authored_room_operation(
                    operation=operation,
                    distance=distance,
                    edge_index=edge_index,
                )
            else:
                result = self.controller.apply_authored_room_operation(operation=operation, distance=distance)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Room Operation", str(exc))
            return
        readiness = result.readiness
        message = f"Applied room operation {operation}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_floor_plan_extrusion(
        self,
        room_resref: str,
        z: float,
        wall_height: float,
        include_walls: bool,
        floor_surface_id: str,
    ) -> None:
        try:
            result = self.controller.set_authored_floor_plan_extrusion(
                room_resref=room_resref,
                z=z,
                wall_height=wall_height,
                include_walls=include_walls,
                floor_surface_id=floor_surface_id,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Floor-Plan Extrusion", str(exc))
            return
        readiness = result.readiness
        message = f"Updated floor-plan extrusion for {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def set_authored_floor_plan_wall_opening(
        self,
        room_resref: str,
        name: str,
        edge_index: int,
        center_fraction: float,
        width: float,
        height: float,
        bottom: float,
    ) -> None:
        try:
            result = self.controller.apply_authored_room_operation(
                operation="wall_opening",
                room_resref=room_resref,
                name=name,
                edge_index=edge_index,
                center_fraction=center_fraction,
                width=width,
                height=height,
                bottom=bottom,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Floor-Plan Wall Opening", str(exc))
            return
        readiness = result.readiness
        opening_label = name or f"edge {edge_index}"
        message = f"Updated wall opening {opening_label} in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def create_authored_opening_transition_marker(
        self,
        room_resref: str,
        opening_name: str,
        marker_kind: str,
        template_resref: str,
        tag: str,
        linked_to: str,
        linked_to_module: str,
    ) -> None:
        try:
            result = self.controller.apply_authored_room_operation(
                operation="opening_transition_marker",
                room_resref=room_resref,
                opening_name=opening_name,
                marker_kind=marker_kind,
                template_resref=template_resref,
                tag=tag,
                linked_to=linked_to,
                linked_to_module=linked_to_module,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Create Opening Transition Marker", str(exc))
            return
        readiness = result.readiness
        marker_label = tag or opening_name or marker_kind
        message = f"Created {marker_kind} marker {marker_label} from wall opening; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def bridge_authored_floor_plan_edges(
        self,
        first_room_resref: str,
        first_edge_index: int,
        second_room_resref: str,
        second_edge_index: int,
        result_room_resref: str,
    ) -> None:
        try:
            result = self.controller.bridge_authored_floor_plan_edges(
                first_room_resref=first_room_resref,
                first_edge_index=first_edge_index,
                second_room_resref=second_room_resref,
                second_edge_index=second_edge_index,
                result_room_resref=result_room_resref,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Bridge Floor-Plan Edges", str(exc))
            return
        readiness = result.readiness
        message = (
            f"Bridged floor-plan edge {first_edge_index} in {first_room_resref} "
            f"to edge {second_edge_index} in {second_room_resref}; previous exports/proofs are now stale."
        )
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def snap_authored_floor_plan_vertex(
        self,
        room_resref: str,
        point_index: int,
        target_point_index: int,
        target_room_resref: str,
    ) -> None:
        try:
            result = self.controller.snap_authored_floor_plan_vertex(
                room_resref=room_resref,
                point_index=point_index,
                target_point_index=target_point_index,
                target_room_resref=target_room_resref,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Snap Floor-Plan Vertex", str(exc))
            return
        readiness = result.readiness
        target_label = target_room_resref or room_resref
        message = (
            f"Snapped floor-plan point {point_index} in {room_resref} to point {target_point_index} in {target_label}; "
            "previous exports/proofs are now stale."
        )
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def weld_authored_floor_plan_vertices(
        self,
        room_resref: str,
        point_indices: object,
        target_point_index: int,
        position_policy: str,
    ) -> None:
        try:
            result = self.controller.weld_authored_floor_plan_vertices(
                room_resref=room_resref,
                point_indices=tuple(point_indices or ()),
                target_point_index=target_point_index,
                position_policy=position_policy,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Weld Floor-Plan Vertices", str(exc))
            return
        readiness = result.readiness
        message = f"Welded floor-plan vertices in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def flatten_authored_floor_plan_vertices(
        self,
        room_resref: str,
        point_indices: object,
        axis: str,
        value: object,
    ) -> None:
        try:
            flatten_value = None if value is None else float(value)
            result = self.controller.flatten_authored_floor_plan_vertices(
                room_resref=room_resref,
                point_indices=tuple(point_indices or ()),
                axis=axis,
                value=flatten_value,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Flatten Floor-Plan Vertices", str(exc))
            return
        readiness = result.readiness
        message = f"Flattened floor-plan vertices in {room_resref} on {axis}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def cleanup_authored_floor_plan_vertices(
        self,
        room_resref: str,
        tolerance: float,
    ) -> None:
        try:
            result = self.controller.cleanup_authored_floor_plan_vertices(
                room_resref=room_resref,
                tolerance=float(tolerance),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Cleanup Floor-Plan Vertices", str(exc))
            return
        readiness = result.readiness
        message = f"Cleaned redundant floor-plan vertices in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def mirror_authored_floor_plan_vertices(
        self,
        room_resref: str,
        axis: str,
    ) -> None:
        try:
            result = self.controller.mirror_authored_floor_plan_vertices(
                room_resref=room_resref,
                axis=axis,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Mirror Floor-Plan Footprint", str(exc))
            return
        readiness = result.readiness
        message = f"Mirrored floor-plan footprint in {room_resref} across local {axis}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def fill_authored_floor_plan_face(
        self,
        room_resref: str,
        point_indices: object,
    ) -> None:
        try:
            result = self.controller.fill_authored_floor_plan_face(
                room_resref=room_resref,
                point_indices=tuple(point_indices or ()),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Fill Floor-Plan Face", str(exc))
            return
        readiness = result.readiness
        message = f"Filled floor-plan face loop in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def triangulate_authored_floor_plan_face(
        self,
        room_resref: str,
    ) -> None:
        try:
            result = self.controller.triangulate_authored_floor_plan_face(
                room_resref=room_resref,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Triangulate Floor-Plan Face", str(exc))
            return
        readiness = result.readiness
        message = f"Triangulated floor-plan face in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def cleanup_authored_floor_plan_normals(
        self,
        room_resref: str,
    ) -> None:
        try:
            result = self.controller.cleanup_authored_floor_plan_normals(
                room_resref=room_resref,
                positive_z=True,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Cleanup Floor-Plan Normals", str(exc))
            return
        readiness = result.readiness
        message = f"Cleaned floor-plan normals in {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_terrain_operation(
        self,
        operation: str,
        room_resref: str,
        row_index: int,
        column_index: int,
        height: float,
        delta: float,
        radius: int,
        iterations: int,
        strength: float,
    ) -> None:
        try:
            result = self.controller.apply_authored_terrain_operation(
                operation=operation,
                room_resref=room_resref,
                row_index=row_index,
                column_index=column_index,
                height=height,
                delta=delta,
                radius=radius,
                iterations=iterations,
                strength=strength,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Terrain Operation", str(exc))
            return
        readiness = result.readiness
        message = f"Applied terrain operation {operation} to {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def preview_map_studio_terrain_sculpt_frame(
        self,
        brush: str,
        room_resref: str,
        row_index: int,
        column_index: int,
        height: float,
        delta: float,
        radius: int,
        iterations: int,
        strength: float,
    ) -> None:
        try:
            performance_policy = self.controller.map_studio_viewport_performance_policy()
            frame = self.controller.prepare_map_studio_terrain_sculpt_frame(
                room_resref=room_resref,
                brush=brush,
                points=((int(row_index), int(column_index), 1.0),),
                delta=delta,
                radius=radius,
                height=height,
                iterations=iterations,
                strength=strength,
                budget_ms=float(getattr(performance_policy, "terrain_brush_budget_ms", 4.0) or 4.0),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Check Live Terrain Brush Frame", str(exc))
            return
        status = (
            f"Live terrain frame: {frame.performance.estimated_apply_ms:.3f} ms / "
            f"{frame.performance.budget_ms:.3f} ms, {frame.performance.affected_sample_count} sample(s), "
            f"{'ready' if frame.should_apply_live else 'too heavy'}; full MDL/WOK rebuild deferred."
        )
        if getattr(frame, "warnings", ()):
            status = f"{status} {frame.warnings[0]}"
        label = getattr(self.builder_tab, "terrainBrushStatusLabel", None)
        if label is not None:
            label.setText(status)
        self._log(status)

    def _sync_map_studio_terrain_brush_context(self, *, force_enabled: bool | None = None) -> None:
        """Keep the viewport terrain brush state aligned with Builder controls."""

        context_getter = getattr(self.builder_tab, "current_terrain_brush_context", None)
        context = context_getter() if callable(context_getter) else {}
        if not isinstance(context, dict):
            context = {}
        enabled = force_enabled
        if not bool(context.get("enabled", False)):
            enabled = False
        setter = getattr(self.viewport_panel, "set_terrain_brush_interaction", None)
        if callable(setter):
            setter(
                enabled=enabled,
                room_resref=str(context.get("room_resref") or ""),
                brush=str(context.get("brush") or ""),
                row_count=int(context.get("row_count", 0) or 0),
                column_count=int(context.get("column_count", 0) or 0),
                radius=int(context.get("radius", 0) or 0),
            )

    def apply_map_studio_viewport_terrain_brush_frame(self, brush: str, room_resref: str, points: object) -> None:
        """Apply one live viewport terrain sculpt frame without a full Map Studio rebuild."""

        context_getter = getattr(self.builder_tab, "current_terrain_brush_context", None)
        context = context_getter() if callable(context_getter) else {}
        if not isinstance(context, dict):
            context = {}
        try:
            performance_policy = self.controller.map_studio_viewport_performance_policy()
            result = self.controller.apply_map_studio_terrain_sculpt_frame(
                room_resref=room_resref,
                brush=brush,
                points=tuple(points or ()),
                delta=float(context.get("delta", 0.1) or 0.1),
                radius=int(context.get("radius", 0) or 0),
                height=float(context.get("height", 0.0) or 0.0),
                iterations=int(context.get("iterations", 1) or 1),
                strength=float(context.get("strength", 0.5) or 0.5),
                budget_ms=float(getattr(performance_policy, "terrain_brush_budget_ms", 4.0) or 4.0),
            )
        except Exception as exc:
            status = f"Live terrain brush failed: {exc}"
            label = getattr(self.builder_tab, "terrainBrushStatusLabel", None)
            if label is not None:
                label.setText(status)
            self._log(status)
            return
        if result.applied:
            overlay = self.controller.authored_terrain_walkability_overlay()
            overlay_setter = getattr(self.viewport_panel, "set_terrain_walkability_overlay", None)
            if callable(overlay_setter):
                overlay_setter(overlay)
        frame = result.frame
        status = (
            f"Live terrain brush: {frame.performance.estimated_apply_ms:.3f} ms, "
            f"{frame.performance.affected_sample_count} dirty sample(s); full rebuild deferred."
        )
        if not result.applied:
            status = result.message
        label = getattr(self.builder_tab, "terrainBrushStatusLabel", None)
        if label is not None:
            label.setText(status)

    def commit_map_studio_viewport_terrain_brush_stroke(self, brush: str, room_resref: str) -> None:
        """Refresh Map Studio once after a live terrain brush stroke is released."""

        message = (
            f"Committed terrain brush {brush} on {room_resref}; refreshed terrain walkability, readiness, and export state."
        )
        self._refresh_all(message)
        self._sync_map_studio_terrain_brush_context()

    def merge_authored_floor_plan_rooms(self, first_room_resref: str, second_room_resref: str, result_room_resref: str) -> None:
        try:
            result = self.controller.merge_authored_floor_plan_rooms(
                first_room_resref=first_room_resref,
                second_room_resref=second_room_resref,
                result_room_resref=result_room_resref,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Union Rectangular Rooms", str(exc))
            return
        readiness = result.readiness
        label = result_room_resref.strip() or first_room_resref
        message = f"Merged floor-plan rooms {first_room_resref} and {second_room_resref} into {label}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def add_authored_room_primitive(self, primitive_kind: str, primitive_name: str) -> None:
        try:
            result = self.controller.add_authored_room_primitive(
                primitive_kind=primitive_kind,
                primitive_name=primitive_name,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Add Room Primitive", str(exc))
            return
        readiness = result.readiness
        label = primitive_name or primitive_kind
        message = f"Added room primitive {label}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_room_primitive_transform(
        self,
        room_resref: str,
        primitive_name: str,
        tx: float,
        ty: float,
        tz: float,
        rot_z: float,
        sx: float,
        sy: float,
        sz: float,
        px: float,
        py: float,
        pz: float,
    ) -> None:
        try:
            result = self.controller.set_authored_room_primitive_transform(
                room_resref=room_resref,
                primitive_name=primitive_name,
                translation=(tx, ty, tz),
                rotation_degrees_z=rot_z,
                scale=(sx, sy, sz),
                pivot=(px, py, pz),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Primitive Transform", str(exc))
            return
        readiness = result.readiness
        message = f"Transformed room primitive {primitive_name}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_room_primitive_dimensions(self, room_resref: str, primitive_name: str, dimensions: object) -> None:
        try:
            result = self.controller.set_authored_room_primitive_dimensions(
                room_resref=room_resref,
                primitive_name=primitive_name,
                dimensions=dimensions,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Primitive Dimensions", str(exc))
            return
        readiness = result.readiness
        message = f"Edited room primitive dimensions for {primitive_name}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_room_primitive_style(self, room_resref: str, primitive_name: str, texture: str, surface_id: str) -> None:
        try:
            result = self.controller.set_authored_room_primitive_style(
                room_resref=room_resref,
                primitive_name=primitive_name,
                texture=texture,
                surface_id=surface_id,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Primitive Material + Surface", str(exc))
            return
        readiness = result.readiness
        message = f"Styled room primitive {primitive_name}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def remove_authored_room_primitive(self, room_resref: str, primitive_name: str) -> None:
        try:
            result = self.controller.remove_authored_room_primitive(
                room_resref=room_resref,
                primitive_name=primitive_name,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Remove Room Primitive", str(exc))
            return
        readiness = result.readiness
        message = f"Removed room primitive {primitive_name}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def separate_authored_room_primitive(self, room_resref: str, primitive_name: str, result_room_resref: str) -> None:
        try:
            result = self.controller.separate_authored_room_primitive(
                room_resref=room_resref,
                primitive_name=primitive_name,
                result_room_resref=result_room_resref,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Separate Room Primitive", str(exc))
            return
        readiness = result.readiness
        message = f"Separated room primitive {primitive_name}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_room_style(self, texture: str, floor_surface: str) -> None:
        try:
            result = self.controller.apply_authored_room_style(texture=texture, floor_surface=floor_surface)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Room Material + Surface", str(exc))
            return
        readiness = result.readiness
        message = "Applied room material and walkmesh surface; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def apply_authored_walkmesh_surface(self, room_resref: str, floor_surface: str) -> None:
        try:
            result = self.controller.set_authored_room_walkmesh_surface(room_resref=room_resref, floor_surface=floor_surface)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Apply Room WOK Surface", str(exc))
            return
        readiness = result.readiness
        message = f"Applied WOK surface {floor_surface} to room {room_resref}; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def add_authored_room_light(
        self,
        room_resref: str,
        name: str,
        pos_x: float,
        pos_y: float,
        pos_z: float,
        color_r: float,
        color_g: float,
        color_b: float,
        radius: float,
        intensity: float,
        light_type: str,
    ) -> None:
        try:
            result = self.controller.add_authored_room_light(
                room_resref=room_resref,
                name=name,
                position=(pos_x, pos_y, pos_z),
                color=(color_r, color_g, color_b),
                radius=radius,
                intensity=intensity,
                light_type=light_type,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Add Room Light", str(exc))
            return
        readiness = result.readiness
        message = "Added authored room light; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def add_authored_gameplay_placement(
        self,
        kind: str,
        template_resref: str,
        tag: str,
        x: float,
        y: float,
        z: float,
        bearing: float,
    ) -> None:
        try:
            result = self.controller.add_authored_gameplay_placement(
                kind=kind,
                template_resref=template_resref,
                tag=tag,
                position=(x, y, z),
                bearing=bearing,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Add Gameplay Placement", str(exc))
            return
        readiness = result.readiness
        message = f"Added authored {kind} placement; previous exports/proofs are now stale."
        if readiness is not None:
            message = f"{message} Readiness: {readiness.capability_stage}."
        self._refresh_all(message)

    def set_authored_script_hook(self, scope: str, field_name: str, script_resref: str) -> None:
        try:
            if str(script_resref or "").strip():
                update = self.controller.set_authored_script_hook(
                    scope=scope,
                    field_name=field_name,
                    script_resref=script_resref,
                )
                message = f"Assigned {update.scope} script hook {update.field_name} -> {update.script_resref}."
            else:
                update = self.controller.remove_authored_script_hook(
                    scope=scope,
                    field_name=field_name,
                )
                message = f"Cleared {update.scope} script hook {update.field_name}."
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Script Hook", str(exc))
            return
        self._refresh_all(f"{message} Previous exports/proofs are now stale.")

    def export_fbx(self, dry_run: bool = False) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export KMAP Scene", f"{self.project.name}.fbx", "FBX files (*.fbx)")
        if not path:
            return
        result = self.controller.export_fbx(path, dry_run=dry_run)
        self.validation_panel.set_issues(result.issues)
        self._log(result.message)
        if result.manifest_path:
            self._log(f"Manifest: {result.manifest_path}")
        for warning in result.warnings:
            self._log(warning)

    def open_output_folder(self) -> None:
        if self._last_output_dir:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self._last_output_dir))
        else:
            self._log("No output folder has been generated yet.")

    def select_item(self, item_id: str) -> None:
        self.controller.model.select(item_id)
        self.outliner.select_id(item_id)
        self.viewport_panel.select_id(item_id)
        self.properties.set_selection(item_id)
        self.workflow_panel.set_selection_context(self._selected_item_label(item_id))
        self.statusBar().showMessage(f"Selected {item_id}")

    def _selected_item_label(self, item_id: str) -> str:
        if not item_id:
            return ""
        authored = next((row for row in self.controller.authored_gameplay_placements() if getattr(row, "placement_id", "") == item_id), None)
        if authored is not None:
            kind = str(getattr(authored, "kind", "resource") or "resource")
            tag = str(getattr(authored, "tag", "") or getattr(authored, "template_resref", "") or item_id)
            return f"{kind}: {tag}"
        authored_light = next((row for row in self.controller.authored_room_lights() if getattr(row, "light_id", "") == item_id), None)
        if authored_light is not None:
            name = str(getattr(authored_light, "name", "") or item_id)
            room = str(getattr(authored_light, "room_resref", "") or "")
            return f"room light: {name}" + (f" ({room})" if room else "")
        item = self.project.find_room(item_id) or self.project.find_module(item_id) or self.project.find_blueprint(item_id)
        if item is None:
            return item_id
        if hasattr(item, "module_name"):
            return f"module: {getattr(item, 'module_name', item_id)}"
        if hasattr(item, "room_id"):
            return f"room: {getattr(item, 'name', item_id)}"
        return f"blueprint: {getattr(item, 'name', item_id)}"

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._confirm_discard_or_save():
            event.accept()
        else:
            event.ignore()

    def _toolbar_action(self, action: str) -> None:
        mapping = {
            "new": self.new_kmap,
            "open": self.open_kmap,
            "save": self.save_kmap,
            "import_module": self.import_module,
            "add_room": lambda: self._handle_tab_action("Add Room"),
            "add_module": lambda: self._handle_tab_action("Add Module"),
            "validate": self.validate_kmap,
            "build": self.build_module_files,
            "export_fbx": lambda: self.export_fbx(False),
        }
        callback = mapping.get(action)
        if callback:
            callback()

    def _handle_tab_action(self, action: str) -> None:
        if action == "Create grdev01 Dev Room":
            result = self.controller.create_dev_test_authored_module()
            readiness = result.readiness
            message = "Created grdev01 authored module with one primitive room, generated walkmesh intent, player start, and test placeable."
            if readiness is not None:
                message = f"{message} Readiness: {readiness.capability_stage}."
            self._refresh_all(message)
            return
        if action == "Load LYT":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load LYT", "", "LYT files (*.lyt);;All files (*.*)")
            if path:
                result = self.controller.load_lyt(path)
                self._refresh_all(result.message)
            return
        if action == "Load WOK":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load WOK", "", "Walkmesh files (*.wok *.dwk *.pwk *.bwm);;All files (*.*)")
            if path:
                result = self.controller.load_wok(path)
                self._refresh_all(result.message)
            return
        if action in {"Add Room", "Add Module"}:
            if action == "Add Module":
                module = self.controller.add_module(f"Module{len(self.project.modules) + 1:03d}")
                self.select_item(module.module_id)
            else:
                room = LevelScene(self.project).add_room(f"Room{len(self.project.rooms) + 1:03d}", module_id=self.controller.model.active_module_id)
                self.select_item(room.room_id)
            self._refresh_all(f"{action} complete.")
            return
        if action == "Remove Room":
            self.delete_selected()
            return
        if action == "Duplicate Room":
            self.duplicate_selected()
            return
        if action == "Save Layout":
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save LYT", f"{self.project.name}.lyt", "LYT files (*.lyt)")
            if path:
                self.controller.layout_service.save_lyt_text(self.project, path)
                self._log(f"Saved layout {path}.")
            return
        if action == "Validate Module":
            self.validate_kmap()
            return
        if action in {"Generate Module Files", "Generate Manifest", "Build ERF/RIM Preview", "Build Loose Override Package"}:
            self.build_module_files()
            return
        if action in {"Port K1 to K2", "Port K2 to K1"}:
            report = self.controller.record_port("K1", "K2") if action.endswith("K2") else self.controller.record_port("K2", "K1")
            self._refresh_all(report.message)
            return
        if action == "Add Blueprint":
            blueprint = self.controller.add_blueprint(blueprint_type=self.blueprints_tab.type_combo.currentText())
            self._refresh_all(f"Added blueprint {blueprint.name}.")
            return
        if action == "Add Camera":
            self.add_map_studio_camera()
            return
        if action == "Add Light":
            self.add_map_studio_room_light()
            return
        if action == "Send to GModular":
            ok, message = self.controller.blueprint_service.send_to_gmodular(None)
            self._log(message if not ok else "Sent blueprint to GModular.")
            return
        if action in {"Focus Selected Room", "Focus in Viewport"}:
            self.viewport_panel.focus_selected()
            return
        self._log(f"{action} is available as an editor hook; backend support is experimental.")

    def _outliner_action(self, action: str, item_id: str) -> None:
        if item_id:
            self.select_item(item_id)
        mapping = {
            "add_module": "Add Module",
            "add_room": "Add Room",
            "add_blueprint": "Add Blueprint",
            "add_camera": "Add Camera",
            "add_light": "Add Light",
            "delete": "Remove Room",
            "duplicate": "Duplicate Room",
            "focus_in_viewport": "Focus in Viewport",
            "validate_selected": "Validate Module",
        }
        if action == "rename":
            self.rename_selected()
        else:
            self._handle_tab_action(mapping.get(action, action))

    def _set_transform(self, item_id: str, transform: LevelTransform) -> None:
        if item_id.startswith("authored_light:"):
            try:
                self.controller.set_authored_room_light_transform(
                    item_id,
                    position=transform.position,
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Move Authored Room Light", str(exc))
                return
            self._refresh_all()
            return
        if item_id.startswith("authored:"):
            try:
                self.controller.set_authored_gameplay_placement_transform(
                    item_id,
                    position=transform.position,
                    bearing=float(transform.rotation[2]) if len(transform.rotation) >= 3 else None,
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Move Authored Gameplay Placement", str(exc))
                return
            self._refresh_all()
            return
        if LevelScene(self.project).set_transform(item_id, transform):
            self._refresh_all()

    def _set_authored_room_outline_point(self, room_resref: str, point_index: int, world_position: object) -> None:
        try:
            self.controller.move_authored_room_outline_point(
                room_resref=room_resref,
                point_index=int(point_index),
                world_position=tuple(world_position),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Move Authored Room Outline Point", str(exc))
            return
        self._refresh_all()

    def _select_authored_room_primitive(self, room_resref: str, primitive_name: str) -> None:
        selected = self.builder_tab.select_room_primitive(room_resref, primitive_name)
        if selected:
            self.workflow_tabs.setCurrentWidget(self.builder_tab)
            self.statusBar().showMessage(f"Selected room primitive {primitive_name}")

    def _move_authored_room_primitive(self, room_resref: str, primitive_name: str, world_delta: object) -> None:
        try:
            self.controller.move_authored_room_primitive(
                room_resref=room_resref,
                primitive_name=primitive_name,
                world_delta=tuple(world_delta),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Move Authored Room Primitive", str(exc))
            return
        self._refresh_all()

    def _set_visibility(self, item_id: str, visible: bool) -> None:
        if item_id.startswith("authored:"):
            return
        if LevelScene(self.project).set_visibility(item_id, visible):
            self._refresh_all()

    def _set_locked(self, item_id: str, locked: bool) -> None:
        if item_id.startswith("authored:"):
            return
        if LevelScene(self.project).set_locked(item_id, locked):
            self._refresh_all()

    def _set_property(self, item_id: str, key: str, value: Any) -> None:
        if item_id.startswith("authored:"):
            if key == "name":
                try:
                    self.controller.rename_authored_gameplay_placement(item_id, tag=str(value or "").strip())
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(self, "Rename Authored Placement", str(exc))
                    return
                self._refresh_all("Renamed authored gameplay placement.")
            return
        if item_id.startswith("authored_light:"):
            if key == "name":
                try:
                    self.controller.rename_authored_room_light(item_id, name=str(value or "").strip())
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(self, "Rename Authored Room Light", str(exc))
                    return
                self._refresh_all("Renamed authored room light.")
            return
        item = self.project.find_room(item_id) or self.project.find_module(item_id) or self.project.find_blueprint(item_id)
        if item is None:
            return
        if key == "name" and hasattr(item, "module_name"):
            item.module_name = str(value)
        elif hasattr(item, key):
            setattr(item, key, value)
        self.project.mark_dirty()
        self._refresh_all()

    def _set_authored_gameplay_transition(self, item_id: str, linked_to: str, linked_to_module: str, transition_destination: int) -> None:
        if not item_id.startswith("authored:"):
            return
        try:
            self.controller.set_authored_gameplay_transition(
                item_id,
                linked_to=linked_to,
                linked_to_module=linked_to_module,
                transition_destination=transition_destination,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Edit Authored Transition", str(exc))
            return
        self._refresh_all("Updated authored transition destination.")

    def _set_authored_gameplay_camera_properties(
        self,
        item_id: str,
        camera_id: int,
        field_of_view: float,
        height: float,
        mic_range: float,
        pitch: float,
    ) -> None:
        if not item_id.startswith("authored:camera:"):
            return
        try:
            self.controller.set_authored_gameplay_camera_properties(
                item_id,
                camera_id=camera_id,
                field_of_view=field_of_view,
                height=height,
                mic_range=mic_range,
                pitch=pitch,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Edit Authored Camera", str(exc))
            return
        self._refresh_all("Updated authored camera properties.")

    def _set_authored_room_light_properties(self, item_id: str, light_type: str, color: object, radius: float, intensity: float) -> None:
        if not item_id.startswith("authored_light:"):
            return
        try:
            self.controller.set_authored_room_light_properties(
                item_id,
                light_type=light_type,
                color=color,
                radius=radius,
                intensity=intensity,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Edit Authored Room Light", str(exc))
            return
        self._refresh_all("Updated authored room light properties.")

    def _refresh_all(self, message: str = "") -> None:
        self.setWindowTitle(f"GhostRigger Map Studio - Level Editor - {self.project.name}{' *' if self.project.dirty else ''}")
        self._apply_map_studio_tool_belt_preferences_from_project()
        self._refresh_map_studio_tool_belt()
        authored_placements = self.controller.authored_gameplay_placements()
        authored_room_lights = self.controller.authored_room_lights()
        authored_markers = self.controller.authored_gameplay_preview_markers()
        authored_marker_geometry = self.controller.authored_gameplay_marker_geometry()
        authored_room_outline_geometry = self.controller.authored_room_outline_geometry()
        authored_terrain_walkability_overlay = self.controller.authored_terrain_walkability_overlay()
        authored_walkmesh_status = self.controller.authored_walkmesh_status()
        authored_walkmesh_room_surfaces = self.controller.authored_walkmesh_room_surface_choices()
        authored_room_primitives = self.controller.authored_room_primitive_transforms()
        authored_floor_plan_rooms = self.controller.authored_floor_plan_room_choices()
        authored_terrain_rooms = self.controller.authored_terrain_room_choices()
        self.builder_tab.set_module_entry_point(self.controller.authored_module_entry_point())
        self.builder_tab.set_room_primitives(authored_room_primitives)
        self.builder_tab.set_floor_plan_room_choices(authored_floor_plan_rooms)
        self.builder_tab.set_terrain_room_choices(authored_terrain_rooms)
        self.builder_tab.set_script_hooks(self.controller.authored_script_hooks())
        self.walkmesh_tab.set_walkmesh_status(authored_walkmesh_status)
        self.walkmesh_tab.set_room_surface_choices(authored_walkmesh_room_surfaces)
        self.properties.set_project(self.project, authored_placements, authored_room_lights)
        self.outliner.set_project(self.project, authored_placements, authored_room_lights)
        self.viewport_panel.set_project(
            self.project,
            authored_placements,
            authored_room_lights,
            authored_markers,
            authored_marker_geometry,
            authored_room_outline_geometry,
            authored_terrain_walkability_overlay,
        )
        self._sync_map_studio_terrain_brush_context()
        readiness_result = self.controller.authored_module_readiness()
        self.workflow_panel.set_state(self.project, readiness_result.readiness)
        self.readiness_panel.set_readiness(readiness_result.readiness)
        self.validation_panel.set_issues(self.controller.validate())
        if self.controller.model.selected_ids:
            self.select_item(self.controller.model.selected_ids[0])
        else:
            self.workflow_panel.set_selection_context("")
        if message:
            self._log(message)

    def _log(self, message: str) -> None:
        if not message:
            return
        self.output_log.appendPlainText(message)
        self.statusBar().showMessage(message)

    def _confirm_discard_or_save(self) -> bool:
        if not self.project.dirty:
            return True
        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved KMAP",
            "Save changes before continuing?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
        )
        if result == QtWidgets.QMessageBox.Cancel:
            return False
        if result == QtWidgets.QMessageBox.Save:
            self.save_kmap()
            return not self.project.dirty
        return True

    def _reset_layout(self) -> None:
        if self.layout_manager is not None:
            self.apply_ghost_layout(self.layout_manager.get_layout())
        else:
            self.main_splitter.setSizes([285, 1220, 320])

    def _show_help(self, topic: str) -> None:
        QtWidgets.QMessageBox.information(
            self,
            topic,
            "Map Studio is GhostRigger's Level Editor opened from the Module Editor icon. It works on KMAP projects and keeps terrain, rooms, walkmeshes, placements, validation, staged export, install handoff, and game-test proof in one workflow without embedding heavy mesh or texture blobs.",
        )

    def set_navigation_profile(self, profile: object) -> None:
        self.viewport_panel.set_navigation_profile(profile)

    def apply_ghost_theme(self, theme) -> None:
        if theme is None:
            return
        if getattr(theme, "is_native", lambda: False)():
            self.apply_native_theme()
            return
        stylesheet = ""
        try:
            from src.gui.libtheme.qt_stylesheet_builder import QtStylesheetBuilder

            stylesheet = QtStylesheetBuilder().build(theme)
        except Exception:
            stylesheet = ""
        if stylesheet:
            self.setStyleSheet(stylesheet)
        for widget in self.findChildren(QtWidgets.QWidget):
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)

    def apply_native_theme(self) -> None:
        self.setStyleSheet("")
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.setStyleSheet("")
        for widget in self.findChildren(QtWidgets.QWidget):
            hook = getattr(widget, "apply_native_theme", None)
            if callable(hook):
                hook()

    def apply_ghost_layout(self, layout) -> None:
        if layout is None:
            return
        self.resize(layout.main_width, layout.main_height)
        self.main_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.main_splitter.setSizes([
            max(240, min(340, layout.panel("library").preferred_width)),
            max(900, layout.viewport.preferred_width),
            max(260, min(420, layout.panel("properties").preferred_width)),
        ])
        if hasattr(self, "left_splitter"):
            self.left_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
            self.left_splitter.setSizes([max(360, layout.main_height - 520), 320])
        bottom = layout.panel("outputLog")
        self.bottom_tabs.setMinimumHeight(max(72, min(120, bottom.min_height)))
        self.bottom_tabs.setMaximumHeight(max(120, min(180, bottom.preferred_height)))
        self.toolbar.apply_ghost_layout(layout)
        for widget in self.findChildren(QtWidgets.QWidget):
            hook = getattr(widget, "apply_ghost_layout", None)
            if callable(hook) and widget is not self.toolbar:
                hook(layout)
