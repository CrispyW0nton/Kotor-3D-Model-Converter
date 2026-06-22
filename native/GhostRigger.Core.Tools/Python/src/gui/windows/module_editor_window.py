"""GhostRigger Map Studio Level Editor window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject, LevelScene, LevelTransform
from src.core.modules.authored_module_export import authored_module_smoke_summary_lines
from src.core.modules.module_editor_controller import ModuleEditorController
from src.core.modules.map_studio_tool_action_dispatch import (
    MapStudioToolActionContext,
    execute_map_studio_tool_belt_action,
    resolve_map_studio_tool_belt_action,
)
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
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("mapStudioToolBeltCustomizeSearchLineEdit")
        self.search_edit.setPlaceholderText("Filter tools by name, workspace, or KOTOR guardrail")
        root.addWidget(self.search_edit)
        self.summary_label = QtWidgets.QLabel("")
        self.summary_label.setObjectName("mapStudioToolBeltCustomizeSummaryLabel")
        root.addWidget(self.summary_label)
        self.action_list = QtWidgets.QListWidget()
        self.action_list.setObjectName("mapStudioToolBeltCustomizeListWidget")
        root.addWidget(self.action_list, 1)

        selected = {str(key) for key in selected_keys}
        for action in actions:
            key = str(getattr(action, "key", "") or "")
            if not key:
                continue
            label = str(getattr(action, "label", key) or key)
            workspace = str(getattr(action, "workspace_key", "") or "builder").replace("_", " ")
            state = "usable" if bool(getattr(action, "implemented", False)) else "planned"
            item = QtWidgets.QListWidgetItem(f"{label}  [{workspace}; {state}]")
            item.setData(QtCore.Qt.UserRole, key)
            description = str(getattr(action, "description", "") or "")
            tooltip = str(getattr(action, "description", "") or "")
            guardrail = str(getattr(action, "kotor_guardrail", "") or "")
            if guardrail:
                tooltip = f"{tooltip}\nKOTOR: {guardrail}" if tooltip else f"KOTOR: {guardrail}"
            item.setData(
                QtCore.Qt.UserRole + 1,
                " ".join((key, label, workspace, state, description, guardrail)).lower(),
            )
            item.setToolTip(tooltip)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if key in selected else QtCore.Qt.Unchecked)
            self.action_list.addItem(item)
        self.action_list.itemChanged.connect(lambda _item: self._update_selection_summary())
        self.search_edit.textChanged.connect(self._filter_actions)
        self._update_selection_summary()

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _filter_actions(self, text: str) -> None:
        needle = str(text or "").strip().lower()
        for row in range(self.action_list.count()):
            item = self.action_list.item(row)
            if item is None:
                continue
            haystack = str(item.data(QtCore.Qt.UserRole + 1) or "").lower()
            item.setHidden(bool(needle and needle not in haystack))
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        selected = 0
        visible = 0
        total = self.action_list.count()
        for row in range(total):
            item = self.action_list.item(row)
            if item is None:
                continue
            if item.checkState() == QtCore.Qt.Checked:
                selected += 1
            if not item.isHidden():
                visible += 1
        self.summary_label.setText(f"{selected} selected; {visible} visible of {total} available Map Studio tools.")

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
        self._last_game_modules_dir = ""
        self._last_map_studio_install_overwrite = False
        self._library_rows: list[dict[str, Any]] = []
        self._map_studio_workspace_modes: dict[str, Any] = {}
        self._map_studio_custom_belt_keys: tuple[str, ...] = ()
        self._map_studio_tool_action_index: dict[str, Any] = {}
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
        self.map_studio_tool_belt_tabs = QtWidgets.QTabWidget()
        self.map_studio_tool_belt_tabs.setObjectName("mapStudioToolBeltTabs")
        self.map_studio_tool_belt_default_tab = QtWidgets.QWidget()
        self.map_studio_tool_belt_default_tab.setObjectName("mapStudioToolBeltDefaultTab")
        belt_row = QtWidgets.QHBoxLayout(self.map_studio_tool_belt_default_tab)
        belt_row.setContentsMargins(0, 0, 0, 0)
        belt_row.setSpacing(6)
        self.map_studio_tool_belt_label = QtWidgets.QLabel("Default Tool Belt")
        self.map_studio_tool_belt_label.setObjectName("mapStudioToolBeltLabel")
        self.map_studio_tool_belt_preset_combo = QtWidgets.QComboBox()
        self.map_studio_tool_belt_preset_combo.setObjectName("mapStudioToolBeltPresetComboBox")
        for preset in self.controller.available_map_studio_tool_belt_presets():
            self.map_studio_tool_belt_preset_combo.addItem(str(getattr(preset, "label", "") or preset.key), str(preset.key))
        self.map_studio_tool_belt_widget = QtWidgets.QWidget()
        self.map_studio_tool_belt_widget.setObjectName("mapStudioToolBeltWidget")
        self.map_studio_tool_belt_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.map_studio_tool_belt_layout = QtWidgets.QHBoxLayout(self.map_studio_tool_belt_widget)
        self.map_studio_tool_belt_layout.setContentsMargins(0, 0, 0, 0)
        self.map_studio_tool_belt_layout.setSpacing(4)
        self.map_studio_command_search_combo = QtWidgets.QComboBox()
        self.map_studio_command_search_combo.setObjectName("mapStudioCommandSearchComboBox")
        self.map_studio_command_search_combo.setEditable(True)
        self.map_studio_command_search_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.map_studio_command_search_combo.setMinimumWidth(220)
        self.map_studio_command_search_combo.setToolTip("Search and run any command-backed Map Studio tool. Shortcut: Ctrl+K.")
        self.map_studio_command_run_button = QtWidgets.QPushButton("Run")
        self.map_studio_command_run_button.setObjectName("mapStudioCommandSearchRunButton")
        self.map_studio_command_run_button.setToolTip("Run the selected Map Studio command through the shared tool action dispatcher.")
        self.map_studio_customize_tool_belt_button = QtWidgets.QPushButton("Customize Belt...")
        self.map_studio_customize_tool_belt_button.setObjectName("mapStudioCustomizeToolBeltButton")
        belt_row.addWidget(self.map_studio_tool_belt_label)
        belt_row.addWidget(self.map_studio_tool_belt_preset_combo)
        belt_row.addWidget(self.map_studio_tool_belt_widget, 1)
        belt_row.addWidget(self.map_studio_command_search_combo)
        belt_row.addWidget(self.map_studio_command_run_button)
        belt_row.addWidget(self.map_studio_customize_tool_belt_button)
        self.map_studio_tool_belt_tabs.addTab(self.map_studio_tool_belt_default_tab, "Default")

        self.map_studio_tool_belt_custom_tab = QtWidgets.QWidget()
        self.map_studio_tool_belt_custom_tab.setObjectName("mapStudioToolBeltCustomTab")
        custom_belt_root = QtWidgets.QVBoxLayout(self.map_studio_tool_belt_custom_tab)
        custom_belt_root.setContentsMargins(0, 0, 0, 0)
        custom_belt_root.setSpacing(4)
        custom_add_row = QtWidgets.QHBoxLayout()
        custom_add_row.setContentsMargins(0, 0, 0, 0)
        custom_add_row.setSpacing(6)
        self.map_studio_custom_tool_combo = QtWidgets.QComboBox()
        self.map_studio_custom_tool_combo.setObjectName("mapStudioCustomToolComboBox")
        self.map_studio_custom_tool_combo.setEditable(True)
        self.map_studio_custom_tool_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.map_studio_custom_tool_combo.setToolTip("Search all Map Studio modeling, terrain, placement, and export tools.")
        self.map_studio_custom_tool_add_button = QtWidgets.QToolButton()
        self.map_studio_custom_tool_add_button.setObjectName("mapStudioCustomToolAddButton")
        self.map_studio_custom_tool_add_button.setText("+")
        self.map_studio_custom_tool_add_button.setToolTip("Add the selected indexed tool to the custom Map Studio tool belt.")
        custom_add_row.addWidget(QtWidgets.QLabel("Custom Tool"))
        custom_add_row.addWidget(self.map_studio_custom_tool_combo, 1)
        custom_add_row.addWidget(self.map_studio_custom_tool_add_button)
        self.map_studio_custom_tool_belt_widget = QtWidgets.QWidget()
        self.map_studio_custom_tool_belt_widget.setObjectName("mapStudioCustomToolBeltWidget")
        self.map_studio_custom_tool_belt_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.map_studio_custom_tool_belt_layout = QtWidgets.QHBoxLayout(self.map_studio_custom_tool_belt_widget)
        self.map_studio_custom_tool_belt_layout.setContentsMargins(0, 0, 0, 0)
        self.map_studio_custom_tool_belt_layout.setSpacing(4)
        custom_belt_root.addLayout(custom_add_row)
        custom_belt_root.addWidget(self.map_studio_custom_tool_belt_widget)
        self.map_studio_tool_belt_tabs.addTab(self.map_studio_tool_belt_custom_tab, "Custom +")
        root.addWidget(self.map_studio_tool_belt_tabs)
        self.map_studio_command_search_readiness_label = QtWidgets.QLabel(
            "Command readiness: choose a Map Studio tool to see capability stage, affected KOTOR resources, and export/game-proof impact."
        )
        self.map_studio_command_search_readiness_label.setObjectName("mapStudioCommandSearchReadinessLabel")
        self.map_studio_command_search_readiness_label.setWordWrap(True)
        root.addWidget(self.map_studio_command_search_readiness_label)
        self._refresh_map_studio_tool_index()
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
        self.viewport_panel.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
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
        self.undo_action.triggered.connect(self.undo_map_studio_command)
        self.redo_action.triggered.connect(self.redo_map_studio_command)
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
        self.map_studio_custom_tool_add_button.clicked.connect(self._add_selected_map_studio_custom_tool)
        self.map_studio_command_run_button.clicked.connect(self._run_selected_map_studio_command_search)
        self.map_studio_command_search_combo.currentIndexChanged.connect(
            lambda _index=0: self._update_map_studio_command_search_readiness()
        )
        self.map_studio_command_search_combo.editTextChanged.connect(
            lambda _text="": self._update_map_studio_command_search_readiness()
        )
        self._connect_map_studio_tool_context_refresh_signals()
        self.map_studio_tool_belt_widget.customContextMenuRequested.connect(
            lambda pos: self._open_map_studio_tool_context_menu(self.map_studio_tool_belt_widget, pos)
        )
        self.map_studio_custom_tool_belt_widget.customContextMenuRequested.connect(
            lambda pos: self._open_map_studio_tool_context_menu(self.map_studio_custom_tool_belt_widget, pos)
        )
        self.viewport_panel.customContextMenuRequested.connect(
            lambda pos: self._open_map_studio_tool_context_menu(self.viewport_panel, pos)
        )
        self.map_studio_command_search_action = QtGui.QAction("Map Studio Command Search", self)
        self.map_studio_command_search_action.setObjectName("mapStudioCommandSearchAction")
        self.map_studio_command_search_action.setShortcut(QtGui.QKeySequence("Ctrl+K"))
        self.map_studio_command_search_action.triggered.connect(self._focus_map_studio_command_search)
        self.addAction(self.map_studio_command_search_action)
        self.map_studio_universal_transform_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        self.map_studio_universal_transform_shortcut.setObjectName("mapStudioUniversalTransformShortcut")
        self.map_studio_universal_transform_shortcut.activated.connect(self._activate_map_studio_universal_transform_shortcut)
        self.map_studio_vertex_snap_shortcut = QtGui.QShortcut(QtGui.QKeySequence("V"), self.viewport_panel)
        self.map_studio_vertex_snap_shortcut.setObjectName("mapStudioVertexSnapShortcut")
        self.map_studio_vertex_snap_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self.map_studio_vertex_snap_shortcut.activated.connect(
            lambda: self._activate_map_studio_modifier_shortcut("vertex_snap")
        )
        self.map_studio_transform_level_snap_shortcut = QtGui.QShortcut(QtGui.QKeySequence("J"), self.viewport_panel)
        self.map_studio_transform_level_snap_shortcut.setObjectName("mapStudioTransformLevelSnapShortcut")
        self.map_studio_transform_level_snap_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self.map_studio_transform_level_snap_shortcut.activated.connect(
            lambda: self._activate_map_studio_modifier_shortcut("transform_snap_level")
        )
        self.toolbar.actionRequested.connect(self._toolbar_action)
        self.toolbar.viewModeChanged.connect(self.viewport_panel.set_view_mode)
        self.toolbar.selectionModeChanged.connect(self._handle_map_studio_edit_mode_changed)
        self.asset_browser.importRequested.connect(self.import_library_asset)
        self.outliner.itemSelected.connect(self.select_item)
        self.outliner.actionRequested.connect(self._outliner_action)
        self.viewport_panel.itemSelected.connect(self.select_item)
        self.viewport_panel.transformEdited.connect(self._set_transform)
        self.viewport_panel.roomOutlinePointEdited.connect(self._set_authored_room_outline_point)
        self.viewport_panel.roomOutlinePointSnapPreviewRequested.connect(self.preview_authored_floor_plan_vertex_snap_candidates)
        self.viewport_panel.roomOutlinePointSnapped.connect(self.snap_authored_floor_plan_vertex)
        self.viewport_panel.roomOutlineEdgeSelected.connect(self._select_authored_room_outline_edge)
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
        self.export_panel.builderFixRequested.connect(self.show_map_studio_builder)
        self.export_panel.walkmeshFixRequested.connect(self.show_map_studio_walkmesh_tools)
        self.export_panel.placementFixRequested.connect(self.show_map_studio_placement_tools)
        self.export_panel.validateRequested.connect(self.validate_kmap)
        self.export_panel.selectFixTargetRequested.connect(self._select_map_studio_export_fix_target)
        for tab in (self.rooms_tab, self.walkmesh_tab, self.porter_tab, self.builder_tab, self.blueprints_tab):
            tab.actionRequested.connect(self._handle_tab_action)
        self.builder_tab.primitivePresetRequested.connect(self.create_authored_room_preset)
        self.builder_tab.roomOperationRequested.connect(self.apply_authored_room_operation)
        self.builder_tab.floorPlanExtrusionRequested.connect(self.apply_authored_floor_plan_extrusion)
        self.builder_tab.floorPlanOpeningRequested.connect(self.set_authored_floor_plan_wall_opening)
        self.builder_tab.floorPlanOpeningMarkerRequested.connect(self.create_authored_opening_transition_marker)
        self.builder_tab.floorPlanVertexSnapPreviewRequested.connect(self.preview_authored_floor_plan_vertex_snap_candidates)
        self.builder_tab.floorPlanVertexSnapRequested.connect(self.snap_authored_floor_plan_vertex)
        self.builder_tab.floorPlanVertexWeldRequested.connect(self.weld_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexFlattenRequested.connect(self.flatten_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexCleanupRequested.connect(self.cleanup_authored_floor_plan_vertices)
        self.builder_tab.floorPlanVertexMirrorRequested.connect(self.mirror_authored_floor_plan_vertices)
        self.builder_tab.floorPlanFaceFillRequested.connect(self.fill_authored_floor_plan_face)
        self.builder_tab.floorPlanFaceSplitRequested.connect(self.split_authored_floor_plan_face)
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

    def undo_map_studio_command(self) -> None:
        result = self.controller.undo_map_studio_command()
        if result is None:
            self._update_map_studio_undo_redo_actions()
            self._log("Nothing to undo.")
            return
        self._refresh_all(result.message)

    def redo_map_studio_command(self) -> None:
        result = self.controller.redo_map_studio_command()
        if result is None:
            self._update_map_studio_undo_redo_actions()
            self._log("Nothing to redo.")
            return
        self._refresh_all(result.message)

    def _update_map_studio_undo_redo_actions(self) -> None:
        undo_label = self.controller.command_history.undo_label
        redo_label = self.controller.command_history.redo_label
        self.undo_action.setEnabled(self.controller.can_undo_map_studio_command())
        self.redo_action.setEnabled(self.controller.can_redo_map_studio_command())
        self.undo_action.setText(f"Undo {undo_label}" if undo_label else "Undo")
        self.redo_action.setText(f"Redo {redo_label}" if redo_label else "Redo")

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

    def _set_map_studio_workspace_combo_key(self, key: str) -> None:
        """Keep the visible workspace selector aligned with programmatic focus changes."""

        wanted = str(key or "").strip()
        index = self.map_studio_workspace_combo.findData(wanted)
        if index < 0:
            return
        if self.map_studio_workspace_combo.currentIndex() != index:
            previous = self.map_studio_workspace_combo.blockSignals(True)
            try:
                self.map_studio_workspace_combo.setCurrentIndex(index)
            finally:
                self.map_studio_workspace_combo.blockSignals(previous)
        self._update_map_studio_workspace_guide()

    def _set_map_studio_toolbar_edit_mode(self, label: str) -> None:
        """Keep the toolbar edit-mode selector aligned with explicit workspace changes."""

        combo = getattr(self.toolbar, "selection_mode", None)
        if combo is None:
            return
        wanted = str(label or "").strip()
        index = combo.findText(wanted)
        if index < 0 or combo.currentIndex() == index:
            self._sync_map_studio_edit_mode_context(wanted)
            return
        previous = combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(previous)
        self._sync_map_studio_edit_mode_context(wanted)

    def _sync_map_studio_edit_mode_context(self, label: str) -> None:
        """Refresh workflow-panel mode context from headless Map Studio mode policy."""

        context = self.controller.map_studio_edit_mode_context(label)
        self.workflow_panel.set_edit_mode_context(
            mode_label=str(getattr(context, "label", "") or label or "Object"),
            editing_target=str(getattr(context, "editing_target", "") or ""),
            kotor_guardrail=str(getattr(context, "kotor_guardrail", "") or ""),
            next_action=str(getattr(context, "next_action", "") or ""),
        )

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
            self._set_map_studio_toolbar_edit_mode("Object")
            self.show_map_studio_geometry_tools()
        elif key == "terrain":
            self._set_map_studio_toolbar_edit_mode("Terrain")
            self.show_map_studio_terrain_tools()
        elif key == "walkmesh":
            self._set_map_studio_toolbar_edit_mode("Walkmesh")
            self.show_map_studio_walkmesh_tools()
        elif key == "placements":
            self._set_map_studio_toolbar_edit_mode("Placement")
            self.show_map_studio_placement_tools()
        elif key == "lighting":
            self._set_map_studio_toolbar_edit_mode("Object")
            self.show_map_studio_lighting_tools()
        elif key == "scripts":
            self._set_map_studio_toolbar_edit_mode("Object")
            self.show_map_studio_script_tools()
        elif key == "export":
            self._set_map_studio_toolbar_edit_mode("Export")
            self.right_tabs.setCurrentWidget(self.map_studio_export_page)
            self.workflow_panel.set_active_authoring_context(
                "Export + Game Proof: validate, stage/install, warp test, then record proof"
            )
            if log_focus:
                self._log("Map Studio export and game-proof workspace focused.")
        else:
            self._set_map_studio_toolbar_edit_mode("Object")
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

    def _sync_map_studio_tool_belt_preset_for_edit_mode(self, label: str) -> None:
        """Show the most relevant built-in tool belt for the active edit mode."""

        current_preset = self._selected_map_studio_tool_belt_preset_key()
        if current_preset == "custom":
            return
        mode_key = str(label or "Object").strip().lower()
        preset_key = {
            "object": "blockout",
            "vertex": "component",
            "edge": "component",
            "face": "component",
            "walkmesh": "component",
            "placement": "gameplay",
            "terrain": "terrain",
            "export": "export",
        }.get(mode_key, "blockout")
        index = self.map_studio_tool_belt_preset_combo.findData(preset_key)
        if index < 0 or self.map_studio_tool_belt_preset_combo.currentIndex() == index:
            return
        previous = self.map_studio_tool_belt_preset_combo.blockSignals(True)
        try:
            self.map_studio_tool_belt_preset_combo.setCurrentIndex(index)
        finally:
            self.map_studio_tool_belt_preset_combo.blockSignals(previous)
        self._refresh_map_studio_tool_belt()

    def _refresh_map_studio_tool_index(self) -> None:
        """Populate the indexed custom-belt picker with all Map Studio tools."""

        self._map_studio_tool_action_index = {
            str(getattr(action, "key", "") or ""): action
            for action in self.controller.available_map_studio_tool_belt_actions()
            if str(getattr(action, "key", "") or "")
        }
        search_results = self.controller.map_studio_tool_command_search("", limit=0, include_planned=True)
        combo = getattr(self, "map_studio_custom_tool_combo", None)
        if combo is not None:
            previous_text = combo.currentText()
            combo.blockSignals(True)
            try:
                combo.clear()
                for result in search_results:
                    state = "usable" if bool(getattr(result, "implemented", False)) else "planned"
                    combo.addItem(f"{result.display_label} [{state}]", result.key)
                    index = combo.count() - 1
                    combo.setItemData(index, self._map_studio_command_search_tooltip(result), QtCore.Qt.ToolTipRole)
                if previous_text:
                    combo.setEditText(previous_text)
            finally:
                combo.blockSignals(False)
            completer = combo.completer()
            if completer is not None:
                completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                completer.setFilterMode(QtCore.Qt.MatchContains)
                completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        command_combo = getattr(self, "map_studio_command_search_combo", None)
        if command_combo is not None:
            previous_text = command_combo.currentText()
            command_combo.blockSignals(True)
            try:
                command_combo.clear()
                for result in search_results:
                    if not bool(getattr(result, "implemented", False)):
                        continue
                    command_combo.addItem(result.display_label, result.key)
                    index = command_combo.count() - 1
                    command_combo.setItemData(index, self._map_studio_command_search_tooltip(result), QtCore.Qt.ToolTipRole)
                if previous_text:
                    command_combo.setEditText(previous_text)
            finally:
                command_combo.blockSignals(False)
            completer = command_combo.completer()
            if completer is not None:
                completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                completer.setFilterMode(QtCore.Qt.MatchContains)
                completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            self._update_map_studio_command_search_readiness()

    def _map_studio_command_search_tooltip(self, result: Any) -> str:
        """Format command-search metadata without owning the policy itself."""

        lines = [
            str(getattr(result, "description", "") or "").strip(),
            f"Capability: {str(getattr(result, 'capability_stage', '') or 'unknown').replace('_', ' ')}",
        ]
        resource_text = ", ".join(str(item) for item in tuple(getattr(result, "resource_impacts", ()) or ()))
        if resource_text:
            lines.append(f"Affects: {resource_text}")
        guardrail = str(getattr(result, "kotor_guardrail", "") or "").strip()
        if guardrail:
            lines.append(f"KOTOR: {guardrail}")
        readiness = str(getattr(result, "readiness_summary", "") or "").strip()
        if readiness:
            lines.append(readiness)
        return "\n".join(line for line in lines if line)

    def _map_studio_command_search_route(self, result: Any | None) -> Any | None:
        """Resolve the current dispatcher route for a command-search result."""

        if result is None:
            return None
        key = str(getattr(result, "key", "") or "").strip()
        if not key or key not in self._map_studio_tool_action_index:
            return None
        return resolve_map_studio_tool_belt_action(key, self._map_studio_tool_action_context(key))

    def _map_studio_command_search_context_tooltip(self, result: Any | None) -> str:
        """Format command-search tooltip with current route readiness appended."""

        if result is None:
            return ""
        tooltip = self._map_studio_command_search_tooltip(result)
        route = self._map_studio_command_search_route(result)
        if route is None or bool(getattr(route, "enabled", True)):
            return tooltip
        reason = str(getattr(route, "disabled_reason", "") or "").strip()
        if not reason:
            return tooltip
        return f"{tooltip}\nNot ready now: {reason}" if tooltip else f"Not ready now: {reason}"

    def _map_studio_tool_route_tooltip(self, action: Any, route: Any) -> str:
        """Format dispatcher route metadata for tool-belt buttons and menus."""

        lines = [
            str(getattr(action, "description", "") or getattr(route, "status_message", "") or "").strip(),
            f"Capability: {str(getattr(route, 'capability_stage', '') or 'unknown').replace('_', ' ')}",
        ]
        resource_text = ", ".join(str(item) for item in tuple(getattr(route, "resource_impacts", ()) or ()))
        if resource_text:
            lines.append(f"Affects: {resource_text}")
        guardrail = str(getattr(action, "kotor_guardrail", "") or "").strip()
        if guardrail:
            lines.append(f"KOTOR: {guardrail}")
        readiness = str(getattr(route, "readiness_summary", "") or "").strip()
        if readiness:
            lines.append(readiness)
        if not bool(getattr(route, "enabled", True)):
            reason = str(getattr(route, "disabled_reason", "") or "").strip()
            if reason:
                lines.append(f"Not ready: {reason}")
        return "\n".join(line for line in lines if line)

    def _map_studio_command_search_summary(self, result: Any | None) -> str:
        if result is None:
            return (
                "Command readiness: choose a Map Studio tool to see capability stage, "
                "affected KOTOR resources, and export/game-proof impact."
            )
        label = str(getattr(result, "display_label", "") or getattr(result, "label", "") or getattr(result, "key", "") or "Command")
        capability = str(getattr(result, "capability_stage", "") or "unknown").replace("_", " ")
        resource_text = ", ".join(str(item) for item in tuple(getattr(result, "resource_impacts", ()) or ())) or "none"
        readiness = str(getattr(result, "readiness_summary", "") or "").strip()
        summary = f"Command readiness: {label} | Capability: {capability} | Affects: {resource_text}. {readiness}".strip()
        route = self._map_studio_command_search_route(result)
        if route is not None and not bool(getattr(route, "enabled", True)):
            reason = str(getattr(route, "disabled_reason", "") or "").strip()
            if reason:
                summary = f"{summary} Not ready now: {reason}"
        return summary

    def _selected_map_studio_command_search_result(self) -> Any | None:
        combo = getattr(self, "map_studio_command_search_combo", None)
        if combo is None:
            return None
        key = str(combo.currentData() or "").strip()
        if key:
            matches = self.controller.map_studio_tool_command_search(key, limit=0)
            for result in matches:
                if str(getattr(result, "key", "") or "") == key:
                    return result
        query = str(combo.currentText() or "").strip()
        if not query:
            return None
        matches = self.controller.map_studio_tool_command_search(query, limit=1)
        return matches[0] if matches else None

    def _update_map_studio_command_search_readiness(self) -> None:
        label = getattr(self, "map_studio_command_search_readiness_label", None)
        if label is None:
            return
        result = self._selected_map_studio_command_search_result()
        summary = self._map_studio_command_search_summary(result)
        label.setText(summary)
        label.setToolTip(self._map_studio_command_search_context_tooltip(result) if result is not None else summary)

    def _clear_map_studio_tool_belt_layout(self, layout: QtWidgets.QLayout | None = None) -> None:
        target_layout = layout or self.map_studio_tool_belt_layout
        while target_layout.count():
            item = target_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _connect_map_studio_tool_context_refresh_signals(self) -> None:
        """Refresh command-surface readiness when visible Map Studio context changes."""

        for combo_name in (
            "roomPrimitiveTransformComboBox",
            "primitiveSurfaceComboBox",
            "roomSurfaceComboBox",
        ):
            combo = getattr(self.builder_tab, combo_name, None)
            if combo is not None:
                combo.currentIndexChanged.connect(lambda _index=0: self._refresh_map_studio_tool_context())

    def _refresh_map_studio_tool_context(self) -> None:
        """Rebuild Map Studio command surfaces from the current Builder selection."""

        self._refresh_map_studio_tool_belt()
        self._update_map_studio_command_search_readiness()

    def _refresh_map_studio_tool_belt(self) -> None:
        self._clear_map_studio_tool_belt_layout(self.map_studio_tool_belt_layout)
        custom_layout = getattr(self, "map_studio_custom_tool_belt_layout", None)
        if custom_layout is not None:
            self._clear_map_studio_tool_belt_layout(custom_layout)
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
        else:
            self._populate_map_studio_tool_belt_layout(self.map_studio_tool_belt_layout, actions)
        if custom_layout is not None:
            custom_actions = self.controller.map_studio_tool_belt_actions_for_preset(
                "custom",
                custom_action_keys=self._map_studio_custom_belt_keys,
            )
            if custom_actions:
                self._populate_map_studio_tool_belt_layout(custom_layout, custom_actions)
            else:
                placeholder = QtWidgets.QLabel("Use + to add any indexed Map Studio tool.")
                placeholder.setObjectName("mapStudioCustomToolBeltEmptyLabel")
                custom_layout.addWidget(placeholder)
                custom_layout.addStretch(1)

    def _build_map_studio_tool_qaction(self, action: Any, *, context_menu: bool = False) -> QtGui.QAction:
        """Create a Qt action for one Map Studio tool without owning command policy."""

        key = str(getattr(action, "key", "") or "")
        label = str(getattr(action, "label", key) or key)
        route = resolve_map_studio_tool_belt_action(key, self._map_studio_tool_action_context(key))
        qaction = QtGui.QAction(label, self)
        qaction.setObjectName(
            f"mapStudioToolContextAction_{key}" if context_menu else f"mapStudioToolBeltQAction_{key}"
        )
        qaction.setData(key)
        qaction.setEnabled(bool(route.enabled) if context_menu else bool(getattr(action, "implemented", False)))
        tooltip = self._map_studio_tool_route_tooltip(action, route)
        hotkey = str(getattr(action, "hotkey", "") or "")
        if hotkey:
            tooltip = f"{tooltip}\nHotkey: {hotkey}" if tooltip else f"Hotkey: {hotkey}"
        if tooltip:
            qaction.setToolTip(tooltip)
            qaction.setStatusTip(tooltip)
        qaction.triggered.connect(
            lambda _checked=False, tool_action=action: self._handle_map_studio_tool_belt_action(tool_action)
        )
        return qaction

    def _populate_map_studio_tool_belt_layout(self, layout: QtWidgets.QHBoxLayout, actions: tuple[Any, ...] | list[Any]) -> None:
        """Draw one Maya-style shelf row of Map Studio tool-belt actions."""

        for action in actions:
            key = str(getattr(action, "key", "") or "")
            if not key:
                continue
            qaction = self._build_map_studio_tool_qaction(action)
            button = QtWidgets.QToolButton()
            button.setDefaultAction(qaction)
            button.setObjectName(f"mapStudioToolBeltButton_{key}")
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            button.setEnabled(bool(getattr(action, "implemented", False)))
            layout.addWidget(button)
        layout.addStretch(1)

    def _add_map_studio_context_menu_action(self, menu: QtWidgets.QMenu, action: Any) -> None:
        """Add one dispatcher-backed Map Studio action to a context menu."""

        key = str(getattr(action, "key", "") or "")
        if not key:
            return
        menu.addAction(self._build_map_studio_tool_qaction(action, context_menu=True))

    def _open_map_studio_tool_context_menu(self, widget: QtWidgets.QWidget, pos: QtCore.QPoint) -> None:
        """Open a context command surface backed by the shared Map Studio dispatcher."""

        menu = QtWidgets.QMenu(widget)
        menu.setObjectName("mapStudioToolContextMenu")
        focus_search_action = menu.addAction("Command Search...")
        focus_search_action.setObjectName("mapStudioToolContextMenuCommandSearchAction")
        focus_search_action.triggered.connect(self._focus_map_studio_command_search)
        customize_action = menu.addAction("Customize Tool Belt...")
        customize_action.setObjectName("mapStudioToolContextMenuCustomizeAction")
        customize_action.triggered.connect(self._customize_map_studio_tool_belt)

        current_actions = self.controller.map_studio_tool_belt_actions_for_preset(
            self._selected_map_studio_tool_belt_preset_key(),
            custom_action_keys=self._map_studio_custom_belt_keys,
        )
        if current_actions:
            current_menu = menu.addMenu("Current Belt")
            current_menu.setObjectName("mapStudioToolContextMenuCurrentBeltMenu")
            for action in current_actions:
                self._add_map_studio_context_menu_action(current_menu, action)

        query = ""
        combo = getattr(self, "map_studio_command_search_combo", None)
        if combo is not None:
            query = str(combo.currentText() or "").strip()
        search_results = self.controller.map_studio_tool_command_search(query, limit=18)
        if search_results:
            search_menu = menu.addMenu("Matching Commands" if query else "Common Commands")
            search_menu.setObjectName("mapStudioToolContextMenuSearchResultsMenu")
            added: set[str] = set()
            for result in search_results:
                key = str(getattr(result, "key", "") or "")
                if not key or key in added:
                    continue
                action = self._map_studio_tool_action_index.get(key)
                if action is None:
                    continue
                self._add_map_studio_context_menu_action(search_menu, action)
                added.add(key)

        if menu.actions():
            menu.exec(widget.mapToGlobal(pos))

    def _focus_map_studio_command_search(self) -> None:
        """Focus the command-search field without changing the active Map Studio workspace."""

        combo = getattr(self, "map_studio_command_search_combo", None)
        if combo is None:
            return
        combo.setFocus()
        line_edit = combo.lineEdit()
        if line_edit is not None:
            line_edit.selectAll()
        self.statusBar().showMessage("Map Studio command search focused. Type a tool name and press Run.", 4000)

    def _run_selected_map_studio_command_search(self) -> None:
        """Run the selected/typed command-search action through the shared dispatcher."""

        combo = getattr(self, "map_studio_command_search_combo", None)
        if combo is None:
            return
        key = str(combo.currentData() or "").strip()
        if not key:
            query = combo.currentText().strip()
            matches = self.controller.map_studio_tool_command_search(query, limit=1)
            if matches:
                key = matches[0].key
        action = self._map_studio_tool_action_index.get(key)
        if action is None:
            self._log("Choose a Map Studio command from the command search before running it.")
            self.statusBar().showMessage("Choose a Map Studio command before running it.", 4000)
            return
        self._handle_map_studio_tool_belt_action(action)

    def _add_selected_map_studio_custom_tool(self) -> None:
        """Add the currently selected indexed tool to the custom Map Studio belt."""

        key = str(self.map_studio_custom_tool_combo.currentData() or "").strip()
        if not key:
            text = self.map_studio_custom_tool_combo.currentText().strip().lower()
            for candidate_key, action in self._map_studio_tool_action_index.items():
                label = str(getattr(action, "label", candidate_key) or candidate_key).lower()
                if text == candidate_key.lower() or text in label:
                    key = candidate_key
                    break
        if not key:
            self._log("Choose a Map Studio tool from the indexed custom tool list before adding it.")
            return
        if key not in self._map_studio_custom_belt_keys:
            self._map_studio_custom_belt_keys = (*self._map_studio_custom_belt_keys, key)
        custom_index = self.map_studio_tool_belt_preset_combo.findData("custom")
        if custom_index >= 0:
            previous = self._syncing_map_studio_tool_belt_preferences
            self._syncing_map_studio_tool_belt_preferences = True
            try:
                self.map_studio_tool_belt_preset_combo.setCurrentIndex(custom_index)
            finally:
                self._syncing_map_studio_tool_belt_preferences = previous
        self._persist_map_studio_tool_belt_preferences()
        self._refresh_map_studio_tool_belt()
        action = self._map_studio_tool_action_index.get(key)
        label = str(getattr(action, "label", key) if action is not None else key)
        self._log(f"Added {label} to the custom Map Studio tool belt.")

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
            "arch": "arch",
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
            "sculpt_erase": "erase",
            "sculpt_plateau": "plateau",
            "sculpt_ramp": "ramp",
            "sculpt_slope": "slope",
            "sculpt_terrace": "terrace",
            "sculpt_pinch": "pinch",
            "sculpt_erode": "erode",
            "sculpt_noise": "noise",
        }.get(str(action_key or "").strip(), "")

    def _map_studio_combo_data(self, combo_name: str) -> dict[str, Any]:
        """Return the current data dictionary for one Builder combo."""

        combo = getattr(self.builder_tab, combo_name, None)
        if combo is None:
            return {}
        data = combo.currentData()
        if isinstance(data, dict):
            return dict(data)
        if isinstance(data, str):
            return {"room_resref": data}
        return {}

    def _map_studio_current_room_resref(self) -> str:
        """Return the best current authored room context visible in Builder."""

        for combo_name in (
            "floorPlanVertexRoomComboBox",
            "floorPlanExtrusionRoomComboBox",
            "floorPlanOpeningRoomComboBox",
            "floorPlanOpeningMarkerRoomComboBox",
            "floorPlanUnionFirstRoomComboBox",
            "floorPlanBridgeFirstRoomComboBox",
            "roomPrimitiveTransformComboBox",
        ):
            data = self._map_studio_combo_data(combo_name)
            room = str(data.get("room_resref") or "").strip()
            if room:
                return room
        choices = self.controller.authored_floor_plan_room_choices()
        if choices:
            return str(getattr(choices[0], "room_resref", "") or "")
        return ""

    def _map_studio_selected_point_indices(self) -> tuple[int, ...]:
        """Return selected Builder point indices without owning selection policy."""

        parser = getattr(self.builder_tab, "_parse_floor_plan_point_indices", None)
        if callable(parser):
            try:
                return tuple(int(index) for index in tuple(parser() or ()))
            except Exception:
                return ()
        return ()

    def _map_studio_tool_action_context(self, action_key: str) -> MapStudioToolActionContext:
        """Collect current UI selection facts for the core action dispatcher."""

        vertex_data = self._map_studio_combo_data("floorPlanVertexRoomComboBox")
        vertex_target_data = self._map_studio_combo_data("floorPlanVertexTargetRoomComboBox")
        bridge_first = self._map_studio_combo_data("floorPlanBridgeFirstRoomComboBox")
        bridge_second = self._map_studio_combo_data("floorPlanBridgeSecondRoomComboBox")
        union_first = self._map_studio_combo_data("floorPlanUnionFirstRoomComboBox")
        union_second = self._map_studio_combo_data("floorPlanUnionSecondRoomComboBox")
        opening_data = self._map_studio_combo_data("floorPlanOpeningRoomComboBox")
        primitive_data = self._map_studio_combo_data("roomPrimitiveTransformComboBox")
        primitive_surface_data = self._map_studio_combo_data("primitiveSurfaceComboBox")
        room_surface_data = self._map_studio_combo_data("roomSurfaceComboBox")
        opening_marker_data = self._map_studio_combo_data("floorPlanOpeningMarkerRoomComboBox")
        selected_points = self._map_studio_selected_point_indices()
        source_point = getattr(self.builder_tab, "floorPlanSourcePointSpinBox", None)
        target_point = getattr(self.builder_tab, "floorPlanTargetPointSpinBox", None)
        bridge_first_edge = getattr(self.builder_tab, "floorPlanBridgeFirstEdgeSpinBox", None)
        bridge_second_edge = getattr(self.builder_tab, "floorPlanBridgeSecondEdgeSpinBox", None)
        cleanup_tolerance = getattr(self.builder_tab, "floorPlanCleanupToleranceSpinBox", None)
        flatten_axis = getattr(self.builder_tab, "floorPlanFlattenAxisComboBox", None)
        mirror_axis = getattr(self.builder_tab, "floorPlanMirrorAxisComboBox", None)
        operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
        operation_distance = getattr(self.builder_tab, "operationDistanceSpinBox", None)
        operation_edge = getattr(self.builder_tab, "operationEdgeIndexSpinBox", None)
        cut_center_x = getattr(self.builder_tab, "cutCenterXSpinBox", None)
        cut_center_y = getattr(self.builder_tab, "cutCenterYSpinBox", None)
        cut_width = getattr(self.builder_tab, "cutWidthSpinBox", None)
        cut_depth = getattr(self.builder_tab, "cutDepthSpinBox", None)
        key = str(action_key or "").strip()
        axis = "x"
        if key == "mirror_y":
            axis = "y"
        elif key == "mirror_x":
            axis = "x"
        elif key in {"cut", "cut_slice_insert_edges", "insert_edge_loop"} and operation_combo is not None:
            axis = "y" if str(operation_combo.currentData() or "") == "split_y" else "x"
        elif key in {"mirror", "flatten", "grid_snap", "transform_snap_level"}:
            axis_combo = mirror_axis if key == "mirror" else flatten_axis
            if axis_combo is not None:
                axis = str(axis_combo.currentData() or "x")
        metadata: dict[str, Any] = {}
        if cleanup_tolerance is not None:
            metadata["tolerance"] = float(cleanup_tolerance.value())
        weld_policy = getattr(self.builder_tab, "floorPlanWeldPolicyComboBox", None)
        if weld_policy is not None:
            metadata["position_policy"] = str(weld_policy.currentData() or "target")
        placement_kind_combo = getattr(self.builder_tab, "gameplayPlacementKindComboBox", None)
        placement_kind = str(placement_kind_combo.currentData() or "") if placement_kind_combo is not None else ""
        placement_template = str(getattr(getattr(self.builder_tab, "gameplayTemplateLineEdit", None), "text", lambda: "")()).strip()
        placement_tag = str(getattr(getattr(self.builder_tab, "gameplayTagLineEdit", None), "text", lambda: "")()).strip()
        placement_x = getattr(self.builder_tab, "gameplayPosXSpinBox", None)
        placement_y = getattr(self.builder_tab, "gameplayPosYSpinBox", None)
        placement_z = getattr(self.builder_tab, "gameplayPosZSpinBox", None)
        placement_bearing = getattr(self.builder_tab, "gameplayBearingSpinBox", None)
        entry_area = str(getattr(getattr(self.builder_tab, "entryPointAreaLineEdit", None), "text", lambda: "")()).strip()
        entry_x = getattr(self.builder_tab, "entryPointPosXSpinBox", None)
        entry_y = getattr(self.builder_tab, "entryPointPosYSpinBox", None)
        entry_z = getattr(self.builder_tab, "entryPointPosZSpinBox", None)
        entry_facing = getattr(self.builder_tab, "entryPointFacingSpinBox", None)
        light_room = str(getattr(getattr(self.builder_tab, "roomLightRoomLineEdit", None), "text", lambda: "")()).strip()
        light_name = str(getattr(getattr(self.builder_tab, "roomLightNameLineEdit", None), "text", lambda: "")()).strip()
        light_type_combo = getattr(self.builder_tab, "roomLightTypeComboBox", None)
        light_type = str(light_type_combo.currentData() or "point") if light_type_combo is not None else "point"
        light_x = getattr(self.builder_tab, "roomLightPosXSpinBox", None)
        light_y = getattr(self.builder_tab, "roomLightPosYSpinBox", None)
        light_z = getattr(self.builder_tab, "roomLightPosZSpinBox", None)
        light_r = getattr(self.builder_tab, "roomLightColorRSpinBox", None)
        light_g = getattr(self.builder_tab, "roomLightColorGSpinBox", None)
        light_b = getattr(self.builder_tab, "roomLightColorBSpinBox", None)
        light_radius = getattr(self.builder_tab, "roomLightRadiusSpinBox", None)
        light_intensity = getattr(self.builder_tab, "roomLightIntensitySpinBox", None)
        script_scope_combo = getattr(self.builder_tab, "scriptHookScopeComboBox", None)
        script_field_combo = getattr(self.builder_tab, "scriptHookFieldComboBox", None)
        script_scope = str(script_scope_combo.currentData() or "area") if script_scope_combo is not None else "area"
        script_field = str(
            (
                script_field_combo.currentData()
                if script_field_combo is not None and script_field_combo.currentData()
                else script_field_combo.currentText()
                if script_field_combo is not None
                else ""
            )
            or ""
        ).strip()
        script_resref = str(getattr(getattr(self.builder_tab, "scriptHookResrefLineEdit", None), "text", lambda: "")()).strip()
        wall_opening_name = str(getattr(getattr(self.builder_tab, "floorPlanOpeningNameLineEdit", None), "text", lambda: "")()).strip()
        wall_opening_edge = getattr(self.builder_tab, "floorPlanOpeningEdgeSpinBox", None)
        wall_opening_center = getattr(self.builder_tab, "floorPlanOpeningCenterSpinBox", None)
        wall_opening_width = getattr(self.builder_tab, "floorPlanOpeningWidthSpinBox", None)
        wall_opening_height = getattr(self.builder_tab, "floorPlanOpeningHeightSpinBox", None)
        wall_opening_bottom = getattr(self.builder_tab, "floorPlanOpeningBottomSpinBox", None)
        opening_marker_opening = getattr(self.builder_tab, "floorPlanOpeningMarkerNameComboBox", None)
        opening_marker_kind = getattr(self.builder_tab, "floorPlanOpeningMarkerKindComboBox", None)
        opening_marker_template = str(getattr(getattr(self.builder_tab, "floorPlanOpeningMarkerTemplateLineEdit", None), "text", lambda: "")()).strip()
        opening_marker_tag = str(getattr(getattr(self.builder_tab, "floorPlanOpeningMarkerTagLineEdit", None), "text", lambda: "")()).strip()
        opening_marker_linked_to = str(getattr(getattr(self.builder_tab, "floorPlanOpeningMarkerLinkedToLineEdit", None), "text", lambda: "")()).strip()
        opening_marker_linked_module = str(getattr(getattr(self.builder_tab, "floorPlanOpeningMarkerLinkedModuleLineEdit", None), "text", lambda: "")()).strip()
        opening_marker_transition = getattr(self.builder_tab, "floorPlanOpeningMarkerTransitionDestSpinBox", None)
        terrain_context_getter = getattr(self.builder_tab, "current_terrain_brush_context", None)
        terrain_context = terrain_context_getter() if callable(terrain_context_getter) else {}
        if not isinstance(terrain_context, dict):
            terrain_context = {}
        terrain_row = getattr(self.builder_tab, "terrainRowSpinBox", None)
        terrain_column = getattr(self.builder_tab, "terrainColumnSpinBox", None)
        module_root_line = getattr(self.builder_tab, "moduleRootLineEdit", None)
        primitive_kind_combo = getattr(self.builder_tab, "compositionPrimitiveKindComboBox", None)
        primitive_name_line = getattr(self.builder_tab, "compositionPrimitiveNameLineEdit", None)
        primitive_kind_data = primitive_kind_combo.currentData() if primitive_kind_combo is not None else {}
        if not isinstance(primitive_kind_data, dict):
            primitive_kind_data = {}
        primitive_kind = str(primitive_kind_data.get("kind") or "").strip()
        primitive_name = (
            str(getattr(primitive_name_line, "text", lambda: "")()).strip()
            if key == "primitive"
            else str(primitive_data.get("primitive_name") or "")
        )
        if primitive_name and "supports_walkmesh_surface" in primitive_data:
            metadata["supports_walkmesh_surface"] = bool(primitive_data.get("supports_walkmesh_surface"))
            metadata["selected_primitive_type"] = str(primitive_data.get("primitive_type") or "")
            metadata["selected_primitive_surface_name"] = str(primitive_data.get("surface_name") or "")
        if key == "paint_wok":
            surface_data = primitive_surface_data if primitive_name else room_surface_data
            surface_id = str(surface_data.get("surface_id") or primitive_data.get("surface_id") or "").strip()
            if surface_id:
                metadata["surface_id"] = surface_id
        terrain_room_resref = str(terrain_context.get("room_resref") or "").strip()
        if key.startswith("sculpt_"):
            current_room_resref = terrain_room_resref
        elif key == "opening":
            current_room_resref = str(opening_data.get("room_resref") or "").strip()
        elif key == "opening_marker":
            current_room_resref = str(opening_marker_data.get("room_resref") or "").strip()
        else:
            current_room_resref = str(
                vertex_data.get("room_resref")
                or primitive_data.get("room_resref")
                or self._map_studio_current_room_resref()
            ).strip()
        return MapStudioToolActionContext(
            module_root=str(getattr(module_root_line, "text", lambda: "")()).strip(),
            room_resref=current_room_resref,
            first_room_resref=str(bridge_first.get("room_resref") or union_first.get("room_resref") or ""),
            second_room_resref=str(bridge_second.get("room_resref") or union_second.get("room_resref") or ""),
            result_room_resref=str(
                getattr(getattr(self.builder_tab, "floorPlanUnionResultRoomLineEdit", None), "text", lambda: "")()
                if key == "combine"
                else getattr(getattr(self.builder_tab, "floorPlanBridgeResultRoomLineEdit", None), "text", lambda: "")()
                if key == "bridge"
                else getattr(getattr(self.builder_tab, "roomPrimitiveSeparateResultLineEdit", None), "text", lambda: "")()
            ).strip(),
            primitive_name=primitive_name,
            primitive_kind=primitive_kind,
            placement_kind=placement_kind,
            placement_template_resref=placement_template,
            placement_tag=placement_tag,
            placement_position=(
                float(placement_x.value()) if placement_x is not None else 0.0,
                float(placement_y.value()) if placement_y is not None else 0.0,
                float(placement_z.value()) if placement_z is not None else 0.0,
            ),
            placement_bearing=float(placement_bearing.value()) if placement_bearing is not None else 0.0,
            entry_area_resref=entry_area,
            entry_position=(
                float(entry_x.value()) if entry_x is not None else 0.0,
                float(entry_y.value()) if entry_y is not None else 0.0,
                float(entry_z.value()) if entry_z is not None else 0.0,
            ),
            entry_facing=float(entry_facing.value()) if entry_facing is not None else 0.0,
            light_room_resref=light_room,
            light_name=light_name,
            light_position=(
                float(light_x.value()) if light_x is not None else 0.0,
                float(light_y.value()) if light_y is not None else 0.0,
                float(light_z.value()) if light_z is not None else 2.25,
            ),
            light_color=(
                float(light_r.value()) if light_r is not None else 1.0,
                float(light_g.value()) if light_g is not None else 0.92,
                float(light_b.value()) if light_b is not None else 0.78,
            ),
            light_radius=float(light_radius.value()) if light_radius is not None else 8.0,
            light_intensity=float(light_intensity.value()) if light_intensity is not None else 1.0,
            light_type=light_type,
            script_scope=script_scope,
            script_field_name=script_field,
            script_resref=script_resref,
            wall_opening_name=wall_opening_name,
            wall_opening_edge_index=int(wall_opening_edge.value()) if wall_opening_edge is not None else 0,
            wall_opening_center_fraction=float(wall_opening_center.value()) if wall_opening_center is not None else 0.5,
            wall_opening_width=float(wall_opening_width.value()) if wall_opening_width is not None else 1.5,
            wall_opening_height=float(wall_opening_height.value()) if wall_opening_height is not None else 2.1,
            wall_opening_bottom=float(wall_opening_bottom.value()) if wall_opening_bottom is not None else 0.0,
            opening_name=str(
                (
                    opening_marker_opening.currentData()
                    if opening_marker_opening is not None and opening_marker_opening.currentData()
                    else opening_marker_opening.currentText()
                    if opening_marker_opening is not None
                    else ""
                )
                or ""
            ).strip(),
            opening_marker_kind=str(
                (
                    opening_marker_kind.currentData()
                    if opening_marker_kind is not None and opening_marker_kind.currentData()
                    else opening_marker_kind.currentText()
                    if opening_marker_kind is not None
                    else "door"
                )
                or "door"
            ),
            opening_marker_template_resref=opening_marker_template,
            opening_marker_tag=opening_marker_tag,
            opening_marker_linked_to=opening_marker_linked_to,
            opening_marker_linked_to_module=opening_marker_linked_module,
            opening_marker_transition_destination=int(opening_marker_transition.value()) if opening_marker_transition is not None else 0,
            point_index=int(source_point.value()) if source_point is not None else None,
            point_indices=selected_points,
            target_point_index=int(target_point.value()) if target_point is not None else None,
            target_room_resref=str(vertex_target_data.get("room_resref") or ""),
            first_edge_index=int(bridge_first_edge.value()) if bridge_first_edge is not None else None,
            second_edge_index=int(bridge_second_edge.value()) if bridge_second_edge is not None else None,
            axis=axis,
            positive_z=key != "reverse_normals",
            operation_distance=float(operation_distance.value()) if operation_distance is not None else 0.25,
            operation_edge_index=int(operation_edge.value()) if operation_edge is not None else 0,
            terrain_row_index=int(terrain_row.value()) if terrain_row is not None else 0,
            terrain_column_index=int(terrain_column.value()) if terrain_column is not None else 0,
            terrain_delta=float(terrain_context.get("delta", 0.1) or 0.1),
            terrain_radius=int(terrain_context.get("radius", 0) or 0),
            terrain_height=float(terrain_context.get("height", 0.0) or 0.0),
            terrain_iterations=int(terrain_context.get("iterations", 1) or 1),
            terrain_strength=float(terrain_context.get("strength", 0.5) or 0.5),
            cut_center=(
                float(cut_center_x.value()) if cut_center_x is not None else 0.0,
                float(cut_center_y.value()) if cut_center_y is not None else 0.0,
            ),
            cut_size=(
                float(cut_width.value()) if cut_width is not None else 1.0,
                float(cut_depth.value()) if cut_depth is not None else 1.0,
            ),
            export_output_dir=str(getattr(self, "_last_output_dir", "") or "").strip(),
            export_dry_run=self._map_studio_export_dry_run_enabled(),
            export_overwrite=bool(getattr(self, "_last_map_studio_install_overwrite", False))
            if key == "install_module"
            else False,
            export_game_modules_dir=str(getattr(self, "_last_game_modules_dir", "") or "").strip(),
            metadata=metadata,
        )

    def _ensure_map_studio_export_output_dir(self, title: str) -> bool:
        """Prompt once for an export/staging folder when the belt route needs it."""

        if str(getattr(self, "_last_output_dir", "") or "").strip():
            return True
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title, "")
        if not path:
            return False
        self._last_output_dir = path
        return True

    def _map_studio_authored_module_root_for_install(self) -> str:
        """Return the authored module root used for install overwrite checks."""

        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
        return str(payload.get("module_root") or getattr(self.project, "name", "") or "authored").strip().lower()

    def _ensure_map_studio_game_modules_dir(self) -> bool:
        """Prompt for the target KOTOR Modules folder when Install Test needs it."""

        modules_path = str(getattr(self, "_last_game_modules_dir", "") or "").strip()
        if not modules_path:
            modules_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select KOTOR Modules folder", "")
            if not modules_path:
                return False
            self._last_game_modules_dir = modules_path
        module_root = self._map_studio_authored_module_root_for_install()
        destination = Path(modules_path) / f"{module_root}.mod"
        self._last_map_studio_install_overwrite = False
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
                return False
            self._last_map_studio_install_overwrite = True
        return True

    def _execute_map_studio_tool_belt_command(self, action_key: str) -> bool:
        """Execute a tool-belt action when the core dispatcher has a command."""

        if action_key in {"stage_module", "install_module"} and not self._ensure_map_studio_export_output_dir(
            "Stage authored module for game test"
        ):
            self._focus_map_studio_export_proof_workspace()
            self.statusBar().showMessage("Map Studio export command canceled; choose an output folder to create a package candidate.", 5000)
            return False
        if action_key == "install_module" and not self._ensure_map_studio_game_modules_dir():
            self._focus_map_studio_export_proof_workspace()
            self.statusBar().showMessage("Install Test canceled; choose a KOTOR Modules folder to prepare an install candidate.", 5000)
            return False
        context = self._map_studio_tool_action_context(action_key)
        route = resolve_map_studio_tool_belt_action(action_key, context)
        if not route.command_method:
            if route.disabled_reason:
                self.statusBar().showMessage(route.disabled_reason, 5000)
                self._log(f"Map Studio action not ready: {route.disabled_reason}")
            return False
        if not route.enabled:
            self.statusBar().showMessage(route.disabled_reason or "Map Studio action is not ready.", 5000)
            self._log(f"Map Studio action not ready: {route.disabled_reason}")
            return False
        try:
            result = execute_map_studio_tool_belt_action(self.controller, action_key, context)
        except Exception as exc:
            self.statusBar().showMessage(str(exc), 6000)
            self._log(f"Map Studio action failed: {exc}")
            return False
        status_message = route.status_message or f"{route.label} complete."
        if action_key == "terrain" and isinstance(result, dict):
            status_message = str(result.get("summary") or status_message)
            next_action = str(result.get("next_action") or "").strip()
            if next_action:
                status_message = f"{status_message} Next: {next_action}"
            self.show_map_studio_terrain_tools()
        elif action_key == "walkmesh":
            summary = str(getattr(result, "summary", "") or status_message)
            next_action = str(getattr(result, "next_action", "") or "").strip()
            status_message = f"{summary} Next: {next_action}" if next_action else summary
            self.show_map_studio_walkmesh_tools()
        elif action_key == "validate":
            issues = list(result or ())
            errors = sum(1 for issue in issues if str(getattr(issue, "severity", "")).lower() == "error")
            warnings = sum(1 for issue in issues if str(getattr(issue, "severity", "")).lower() == "warning")
            status_message = f"Validation complete: {len(issues)} issue(s), {errors} error(s), {warnings} warning(s)."
            self.validation_panel.set_issues(issues)
            self.bottom_tabs.setCurrentWidget(self.validation_panel)
            self._set_map_studio_workspace_combo_key("export")
        elif action_key == "script":
            scope = str(getattr(result, "scope", "") or "").strip()
            field_name = str(getattr(result, "field_name", "") or "").strip()
            script_resref = str(getattr(result, "script_resref", "") or "").strip()
            if bool(getattr(result, "removed", False)):
                status_message = f"Cleared {scope} script hook {field_name}; export, install handoff, and game proof are stale."
            else:
                status_message = (
                    f"Assigned {scope} script hook {field_name} -> {script_resref}; "
                    "export, install handoff, and game proof are stale."
                )
            self.show_map_studio_script_tools()
        elif action_key == "stage_module":
            status_message = str(getattr(result, "message", "") or status_message)
            self._last_output_dir = str(route.command_kwargs.get("output_dir") or self._last_output_dir or "")
            self._log_authored_module_stage_result(result)
            self._focus_map_studio_export_proof_workspace()
        elif action_key == "install_module":
            status_message = str(getattr(result, "message", "") or status_message)
            self._last_output_dir = str(route.command_kwargs.get("output_dir") or self._last_output_dir or "")
            self._last_game_modules_dir = str(route.command_kwargs.get("game_modules_dir") or self._last_game_modules_dir or "")
            self._log_authored_module_stage_result(result)
            if not bool(getattr(result, "ok", False)):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Install Authored Module",
                    str(getattr(result, "message", "") or "Install failed."),
                )
            self._focus_map_studio_export_proof_workspace()
        elif action_key == "launch_handoff":
            summary = str(getattr(result, "summary", "") or status_message)
            blockers = tuple(getattr(result, "blocking_messages", ()) or ())
            next_action = str(getattr(result, "next_action", "") or "").strip()
            status_message = f"{summary} {blockers[0]}" if blockers else summary
            if next_action and not blockers:
                status_message = f"{status_message} Next: {next_action}"
            self._focus_map_studio_export_proof_workspace()
            self._open_map_studio_launch_handoff_dialog_from_summary(result)
        elif action_key == "record_proof":
            summary = str(getattr(result, "summary", "") or status_message)
            blockers = tuple(getattr(result, "blocking_messages", ()) or ())
            next_action = str(getattr(result, "next_action", "") or "").strip()
            status_message = f"{summary} {blockers[0]}" if blockers else summary
            if next_action and not blockers:
                status_message = f"{status_message} Next: {next_action}"
            self._focus_map_studio_export_proof_workspace()
            self._record_game_smoke_proof_from_summary(result)
        if action_key == "universal_transform":
            overlay_setter = getattr(self.viewport_panel, "set_universal_transform_overlay", None)
            if callable(overlay_setter):
                overlay_setter(result)
            dimensions = tuple(getattr(result, "dimensions", ()) or ())
            center = tuple(getattr(result, "center", ()) or ())
            if len(dimensions) == 3:
                status_message = (
                    f"Universal Transform: {getattr(result, 'primitive_name', '')} "
                    f"W {dimensions[0]:.3f} / D {dimensions[1]:.3f} / H {dimensions[2]:.3f} m"
                )
                if len(center) == 3:
                    status_message += f"; center {center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f}."
            self._log(status_message)
        self._refresh_all(status_message)
        self.workflow_panel.set_active_authoring_context(
            route.authoring_context or route.readiness_impact or route.status_message or route.label
        )
        return True

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

    def _select_map_studio_component_mode(self, component_key: str) -> None:
        """Synchronize the Builder component selector with the toolbar edit mode."""

        combo = getattr(self.builder_tab, "componentModeComboBox", None)
        if combo is None:
            return
        wanted = str(component_key or "").strip().lower()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("key") or "").strip().lower() == wanted:
                combo.setCurrentIndex(index)
                return

    def _select_map_studio_snap_mode(self, snap_key: str) -> None:
        """Synchronize the Builder snap selector with a tool-belt action."""

        combo = getattr(self.builder_tab, "snapModeComboBox", None)
        if combo is None:
            return
        wanted = str(snap_key or "").strip().lower()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("key") or "").strip().lower() == wanted:
                combo.setCurrentIndex(index)
                return

    def _focus_map_studio_vertex_workflow(self, action_key: str) -> None:
        """Route vertex-oriented belt actions to the Builder vertex workflow."""

        key = str(action_key or "").strip()
        tool_by_action = {
            "vertex_snap": "snap_vertices",
            "grid_snap": "snap_vertices",
            "transform_snap_level": "transform_snap_level",
            "weld": "weld_vertices",
            "flatten": "flatten_vertices",
            "mirror": "mirror_footprint",
            "cleanup": "cleanup_footprint",
        }
        snap_by_action = {
            "vertex_snap": "vertex",
            "grid_snap": "grid",
            "transform_snap_level": "level",
            "weld": "vertex",
            "flatten": "grid",
            "mirror": "grid",
            "cleanup": "grid",
        }
        context_by_action = {
            "vertex_snap": (
                "Vertex snap: move one floor-plan point to another point or room handle "
                "without welding topology. Hold V previews point snapping; commit through "
                "Snap Vertex so KMAP, WOK, readiness, and export-stale state update together."
            ),
            "grid_snap": (
                "Grid snap: move selected floor-plan points to the authored Map Studio grid "
                "without welding topology. Validate room seams, WOK, staged export, and game "
                "proof after snapping."
            ),
            "weld": (
                "Weld vertices: merge selected floor-plan points into one topology point "
                "and repair room/WOK references before export."
            ),
            "flatten": "Flatten vertices: align selected points on a local X/Y line for clean walls, seams, and doorways.",
            "transform_snap_level": (
                "Transform level snap: hold J with transform active to align selected vertices or edges "
                "onto one shared X/Y/Z level before validating room seams and WOK output."
            ),
            "mirror": "Mirror vertices: mirror authored footprint points while preserving a valid convex KOTOR room boundary.",
            "cleanup": "Cleanup vertices: remove duplicate or collinear floor-plan points before MDL/WOK generation.",
        }
        log_by_action = {
            "vertex_snap": (
                "Map Studio Vertex Snap focused. This moves a point to another point; it does "
                "not merge topology. Use Weld when the points should become one vertex."
            ),
            "grid_snap": (
                "Map Studio Grid Snap focused. This moves selected floor-plan points to the "
                "grid; it does not weld topology."
            ),
            "weld": "Map Studio Weld focused. Welding merges topology and can change WOK/room face references.",
            "flatten": "Map Studio Flatten focused. Align selected points before validating room seams and WOK output.",
            "transform_snap_level": "Map Studio Transform Level Snap focused. Hold J during transform to align selected vertices/edges to one level.",
            "mirror": "Map Studio Mirror focused. Mirrored footprints still need convexity and WOK validation.",
            "cleanup": "Map Studio Cleanup focused. Cleanup removes duplicate/collinear points before export.",
        }
        self._select_map_studio_component_mode("vertex")
        self._select_map_studio_modeling_tool(tool_by_action.get(key, "snap_vertices"))
        self._select_map_studio_snap_mode(snap_by_action.get(key, "grid"))
        self.workflow_panel.set_active_authoring_context(context_by_action.get(key, context_by_action["vertex_snap"]))
        self._log(log_by_action.get(key, log_by_action["vertex_snap"]))
        tool = getattr(self.builder_tab, "floorPlanVertexRoomComboBox", None)
        if tool is not None:
            tool.setFocus()
        preview = getattr(self.builder_tab, "request_floor_plan_vertex_snap_preview", None)
        if callable(preview):
            preview()

    def _activate_map_studio_universal_transform_shortcut(self) -> None:
        """Route Ctrl+T through the Map Studio tool-belt action catalog."""

        for action in self.controller.available_map_studio_tool_belt_actions():
            if str(getattr(action, "key", "") or "") == "universal_transform":
                self._handle_map_studio_tool_belt_action(action)
                return
        self._focus_map_studio_universal_transform()

    def _activate_map_studio_modifier_shortcut(self, action_key: str) -> None:
        """Route Maya-style viewport modifier shortcuts through Map Studio tools."""

        key = str(action_key or "").strip()
        if self._execute_map_studio_tool_belt_command(key):
            return
        if key == "vertex_snap":
            self._focus_map_studio_vertex_workflow("vertex_snap")
            message = (
                "Hold V: vertex snap mode focused. Select a source and target "
                "floor-plan vertex, then drag/snap in the viewport."
            )
        elif key == "transform_snap_level":
            self._focus_map_studio_vertex_workflow("transform_snap_level")
            message = (
                "Hold J: transform level snap focused. Select two or more "
                "vertices/edges to align to a shared level."
            )
        else:
            message = f"Map Studio shortcut {key} is not mapped."
        self.workflow_panel.set_active_authoring_context(message)
        self.statusBar().showMessage(message, 5000)
        self._log(message)

    def _focus_map_studio_universal_transform(self) -> None:
        """Focus the selected-component Universal Manipulator workflow."""

        self.show_map_studio_geometry_tools()
        self._select_map_studio_component_mode("object")
        self._select_map_studio_modeling_tool("universal_transform")
        self.workflow_panel.set_active_authoring_context(
            "Universal Manipulator: Ctrl+T displays selected component bounds, gizmo handles, and exact width/depth/height for modular-kit scaling."
        )
        self.statusBar().showMessage("Map Studio Universal Manipulator active. Select a mesh/component to inspect width, depth, and height.", 5000)
        self._log("Map Studio Universal Manipulator focused. Use selected bounds for exact modular-kit dimensions.")

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
                label = str(data.get("label") or wanted).strip() or wanted
                operation = str(data.get("operation") or wanted).strip() or wanted
                guardrail = str(data.get("guardrail") or "").strip()
                self.workflow_panel.set_active_authoring_context(
                    f"Terrain brush: {label}. Live strokes update dirty terrain samples only; "
                    "full MDL/WOK rebuild waits for stroke commit, validation, or export."
                )
                message = (
                    f"Map Studio terrain brush selected: {label} ({operation}). "
                    "Brush frames stay dirty-region scoped for low-latency sculpting."
                )
                if guardrail:
                    message += f" KOTOR: {guardrail}"
                self._log(message)
                return
        self.workflow_panel.set_active_authoring_context(
            f"Terrain brush: {wanted or '(none)'} is not available in the current Map Studio tool set."
        )
        self._log(f"Map Studio terrain brush '{wanted}' is not available.")

    def _focus_map_studio_opening_marker_controls(self) -> None:
        """Focus Builder controls that convert authored openings into KOTOR transition markers."""

        self.show_map_studio_geometry_tools()
        marker_room = getattr(self.builder_tab, "floorPlanOpeningMarkerRoomComboBox", None)
        if marker_room is not None:
            marker_room.setFocus()
        self.workflow_panel.set_active_authoring_context(
            "Opening marker: create a KOTOR door, trigger, or waypoint from an authored wall opening and set LinkedTo/TransitionDestin."
        )
        self._log(
            "Map Studio opening transition marker controls focused. Choose an authored opening, marker kind, template/tag, and transition destination."
        )

    def _select_authored_room_outline_edge(self, room_resref: str, edge_index: int) -> None:
        """Focus Builder edge tools after a floor-plan edge is selected in the viewport."""

        room = str(room_resref or "").strip()
        edge = int(edge_index)
        if not room or edge < 0:
            return
        self.show_map_studio_geometry_tools()
        self._select_map_studio_component_mode("edge")
        self._select_map_studio_modeling_tool("bridge")
        selector = getattr(self.builder_tab, "select_floor_plan_edge", None)
        selected = bool(selector(room, edge)) if callable(selector) else False
        context = (
            f"Edge mode: selected {room} edge {edge}. Use Bridge, Wall Opening, or Edge Extrude for KOTOR room seams."
        )
        self.workflow_panel.set_active_authoring_context(context)
        self.statusBar().showMessage(context)
        if selected:
            self._log(f"Map Studio selected floor-plan edge {edge} in {room}; Builder edge tools were synchronized.")
        else:
            self._log(
                f"Map Studio selected floor-plan edge {edge} in {room}, but Builder has no matching floor-plan room choice."
            )

    def _map_studio_export_dry_run_enabled(self) -> bool:
        """Return the current export dry-run preference from the Export panel."""

        dry_run = getattr(getattr(self, "export_panel", None), "dry_run", None)
        if dry_run is None:
            return True
        return bool(dry_run.isChecked())

    def _focus_map_studio_export_proof_workspace(self) -> None:
        """Focus the staged export/install/game-proof controls."""

        self._set_map_studio_workspace_combo_key("export")
        self.right_tabs.setCurrentWidget(self.map_studio_export_page)
        self.workflow_panel.set_active_authoring_context(
            "Export + Game Proof: validate, stage/install, warp test, then record proof"
        )

    def _select_map_studio_export_fix_target(self, target_id: str) -> None:
        """Select the authored object or entry-point controls named by export readiness."""

        target = str(target_id or "").strip()
        if not target:
            return
        if target == "entry_point":
            self._focus_map_studio_entry_point_controls()
            self.statusBar().showMessage("Focused Map Studio module entry point for the current PTH/WOK blocker.")
            return
        if target.startswith("authored:"):
            self.show_map_studio_placement_tools()
            self.select_item(target)
            try:
                self.viewport_panel.focus_selected()
            except Exception:
                pass
            self.workflow_panel.set_active_authoring_context(
                "Placement fix: move the selected authored resource onto generated walkable WOK, then Validate again."
            )
            self._log(f"Selected export blocker target {target}. Move it onto walkable WOK before staging.")
            return
        self.select_item(target)
        self._log(f"Selected export blocker target {target}.")

    def _handle_map_studio_tool_belt_action(self, action: Any) -> None:
        key = str(getattr(action, "key", "") or "")
        workspace_key = str(getattr(action, "workspace_key", "") or "")
        tool_key = str(getattr(action, "tool_key", "") or "")
        route_context = self._map_studio_tool_action_context(key)
        route = resolve_map_studio_tool_belt_action(key, route_context)
        direct_command_actions = {
            "plane",
            "cube",
            "wall",
            "ramp",
            "stairs",
            "cylinder",
            "door_frame",
            "arch",
            "universal_transform",
            "cleanup",
            "triangulate",
            "normals",
            "reverse_normals",
            "soften_edges",
            "harden_edges",
            "mirror",
            "mirror_x",
            "mirror_y",
            "mirror_z",
            "extrude",
            "bevel",
            "boolean",
            "boolean_a_minus_b",
            "boolean_b_minus_a",
            "create_room",
            "corridor",
            "terrain_patch",
            "primitive",
            "cut",
            "cut_slice_insert_edges",
            "insert_edge_loop",
            "fill",
            "fill_hole",
            "bridge",
            "shrink_wrap",
            "bend_tool",
            "curve_tool",
            "lattice",
            "combine",
            "separate",
            "duplicate_special",
            "vertex_snap",
            "grid_snap",
            "weld",
            "merge_components",
            "flatten",
            "transform_snap_level",
            "place",
            "entry_point",
            "placeable",
            "creature",
            "door",
            "waypoint",
            "trigger",
            "encounter",
            "sound",
            "camera",
            "store",
            "light",
            "script",
            "validate",
            "stage_module",
            "install_module",
            "launch_handoff",
            "record_proof",
            "opening",
            "opening_marker",
            "terrain",
            "walkmesh",
            "sculpt_raise",
            "sculpt_lower",
            "sculpt_smooth",
            "sculpt_flatten",
            "sculpt_erase",
            "sculpt_plateau",
            "sculpt_ramp",
            "sculpt_slope",
            "sculpt_terrace",
            "sculpt_pinch",
            "sculpt_erode",
            "sculpt_noise",
        }
        if key in direct_command_actions:
            if self._execute_map_studio_tool_belt_command(key):
                return
            if route.command_method:
                return
            if key == "opening_marker":
                self._focus_map_studio_opening_marker_controls()
                return
        terrain_brush = route.terrain_brush or self._map_studio_belt_terrain_brush(key)
        if terrain_brush:
            self.show_map_studio_terrain_tools()
            self._select_map_studio_terrain_brush(terrain_brush)
            self._sync_map_studio_terrain_brush_context(force_enabled=True)
            return
        primitive_kind = route.primitive_kind or self._map_studio_belt_primitive_kind(key)
        if primitive_kind:
            self.show_map_studio_geometry_tools()
            self.add_authored_room_primitive(primitive_kind, "")
            return
        placement_kind = route.placement_kind or self._map_studio_belt_placement_kind(key)
        if placement_kind:
            self.show_map_studio_placement_tools()
            self._select_map_studio_gameplay_kind(placement_kind)
            return
        if key in {
            "create_room",
            "primitive",
            "universal_transform",
            "extrude",
            "bridge",
            "cut",
            "cut_slice_insert_edges",
            "insert_edge_loop",
            "opening",
            "fill",
            "fill_hole",
            "vertex_snap",
            "grid_snap",
            "transform_snap_level",
            "weld",
            "merge_components",
            "flatten",
            "mirror",
            "mirror_x",
            "mirror_y",
            "mirror_z",
            "cleanup",
            "triangulate",
            "normals",
            "reverse_normals",
            "soften_edges",
            "harden_edges",
            "bevel",
            "boolean",
            "boolean_a_minus_b",
            "boolean_b_minus_a",
            "lattice",
            "shrink_wrap",
            "duplicate_special",
            "curve_tool",
            "bend_tool",
            "combine",
            "separate",
        }:
            self.show_map_studio_geometry_tools()
            if tool_key:
                self._select_map_studio_modeling_tool(tool_key)
            if key == "universal_transform":
                self._focus_map_studio_universal_transform()
                return
            if key == "extrude":
                operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
                if operation_combo is not None:
                    index = operation_combo.findData("edge_extrude")
                    if index >= 0:
                        operation_combo.setCurrentIndex(index)
                    operation_combo.setFocus()
            if key in {"cut", "cut_slice_insert_edges", "insert_edge_loop"}:
                operation_combo = getattr(self.builder_tab, "roomOperationComboBox", None)
                if operation_combo is not None:
                    index = operation_combo.findData("split_x")
                    if index >= 0:
                        operation_combo.setCurrentIndex(index)
                    operation_combo.setFocus()
            if key in {"boolean", "boolean_a_minus_b", "boolean_b_minus_a"}:
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
                self.workflow_panel.set_active_authoring_context(
                    "Combine: merge compatible rectangular floor-plan rooms into one explicit "
                    "export boundary. Select two rooms, set a result resref, then Apply Union."
                )
                self._log(
                    "Map Studio Combine focused. Current implementation unions compatible "
                    "rectangular floor-plan rooms; arbitrary mesh-object combine remains a later "
                    "mesh-editing slice."
                )
                if tool is not None:
                    tool.setFocus()
            if key == "separate":
                tool = getattr(self.builder_tab, "roomPrimitiveSeparateResultLineEdit", None)
                self.workflow_panel.set_active_authoring_context(
                    "Separate: split a selected authored composition primitive into its own "
                    "exportable room/object boundary for UV and texturing handoff."
                )
                self._log(
                    "Map Studio Separate focused. Choose a primitive, optionally set a result "
                    "resref, then Separate to create a distinct export boundary."
                )
                if tool is not None:
                    tool.setFocus()
            if key in {"vertex_snap", "grid_snap", "transform_snap_level", "weld", "merge_components", "flatten", "mirror", "mirror_x", "mirror_y", "mirror_z", "cleanup"}:
                self._focus_map_studio_vertex_workflow({
                    "merge_components": "weld",
                    "mirror_x": "mirror",
                    "mirror_y": "mirror",
                    "mirror_z": "mirror",
                }.get(key, key))
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
            self._focus_map_studio_export_proof_workspace()
        else:
            self.show_map_studio_builder()

    def show_map_studio_builder(self) -> None:
        """Focus the Builder tab inside the existing Map Studio Level Editor."""

        self._set_map_studio_workspace_combo_key("geometry")
        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        self.workflow_panel.set_active_authoring_context("Builder: room, terrain, placement, lighting, and script authoring")
        self._log("Map Studio Builder focused.")

    def _focus_map_studio_edit_mode_workspace(self, label: str) -> None:
        """Route the toolbar edit mode to the closest usable Map Studio workspace."""

        mode_key = str(label or "Object").strip().lower()
        if mode_key == "object":
            self.show_map_studio_builder()
            self._select_map_studio_component_mode("object")
            self._select_map_studio_modeling_tool("primitive_room")
            self.left_tabs.setCurrentWidget(self.outliner)
            return
        if mode_key == "vertex":
            self.show_map_studio_geometry_tools()
            self._select_map_studio_component_mode("vertex")
            self._select_map_studio_modeling_tool("weld_vertices")
            tool = getattr(self.builder_tab, "floorPlanVertexRoomComboBox", None)
            if tool is not None:
                tool.setFocus()
            return
        if mode_key == "edge":
            self.show_map_studio_geometry_tools()
            self._select_map_studio_component_mode("edge")
            self._select_map_studio_modeling_tool("bridge")
            tool = getattr(self.builder_tab, "floorPlanBridgeFirstRoomComboBox", None)
            if tool is not None:
                tool.setFocus()
            return
        if mode_key == "face":
            self.show_map_studio_geometry_tools()
            self._select_map_studio_component_mode("face")
            self._select_map_studio_modeling_tool("fill_face")
            tool = getattr(self.builder_tab, "fillFloorPlanFaceButton", None)
            if tool is not None:
                tool.setFocus()
            return
        if mode_key == "walkmesh":
            self._select_map_studio_component_mode("walkmesh")
            self._select_map_studio_modeling_tool("paint_wok")
            self.show_map_studio_walkmesh_tools()
            return
        if mode_key == "placement":
            self.show_map_studio_placement_tools()
            return
        if mode_key == "terrain":
            self.show_map_studio_terrain_tools()
            self._select_map_studio_modeling_tool("terrain_sculpt")
            return
        if mode_key == "export":
            self._focus_map_studio_export_proof_workspace()
            return

    def _handle_map_studio_edit_mode_changed(self, mode: str) -> None:
        """Reflect the toolbar edit mode in the Map Studio workflow/readiness panel."""

        label = str(mode or "Object").strip() or "Object"
        self._sync_map_studio_tool_belt_preset_for_edit_mode(label)
        self._focus_map_studio_edit_mode_workspace(label)
        self._sync_map_studio_edit_mode_context(label)
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

        self._set_map_studio_workspace_combo_key("geometry")
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

        self._set_map_studio_workspace_combo_key("walkmesh")
        self.workflow_tabs.setCurrentWidget(self.walkmesh_tab)
        self.workflow_panel.set_active_authoring_context("Walkmesh: inspect and paint walkable/non-walkable faces")
        self._log("Map Studio Walkmesh tools focused. Use these to inspect, load, or paint walkable faces.")

    def show_map_studio_terrain_tools(self) -> None:
        """Focus Builder's terrain heightfield controls."""

        self._set_map_studio_workspace_combo_key("terrain")
        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        terrain = getattr(self.builder_tab, "terrainRoomComboBox", None)
        if terrain is not None:
            terrain.setFocus()
        self.workflow_panel.set_active_authoring_context("Terrain: sculpt heightfield samples and slope/walkability")
        self._sync_map_studio_terrain_brush_context()
        self._log("Map Studio terrain tools focused. Create a terrain patch, choose a heightfield room, then sculpt samples.")

    def show_map_studio_lighting_tools(self) -> None:
        """Focus Builder's authored room-light controls."""

        self._set_map_studio_workspace_combo_key("lighting")
        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        name = getattr(self.builder_tab, "roomLightNameLineEdit", None)
        if name is not None:
            name.setFocus()
            name.selectAll()
        self.workflow_panel.set_active_authoring_context("Lighting: add authored room lights before lightmap/export checks")
        self._log("Map Studio lighting tools focused. Add authored room lights before staging lightmap-ready test builds.")

    def show_map_studio_placement_tools(self) -> None:
        """Focus Builder's authored gameplay placement controls."""

        self._set_map_studio_workspace_combo_key("placements")
        self.workflow_tabs.setCurrentWidget(self.builder_tab)
        search = getattr(self.builder_tab, "gameplayPaletteSearchLineEdit", None)
        if search is not None:
            search.setFocus()
            search.selectAll()
        self.workflow_panel.set_active_authoring_context("Placement: choose a KOTOR resource template and place it in the module")
        self._log("Map Studio placement tools focused. Search the game-library palette or type a template resref.")

    def show_map_studio_script_tools(self) -> None:
        """Focus Builder's authored module/area script-hook controls."""

        self._set_map_studio_workspace_combo_key("scripts")
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
        self._log_authored_module_stage_result(result)
        self._refresh_all("Authored module game-test staging updated.")

    def _log_authored_module_stage_result(self, result: Any) -> None:
        """Log staged authored-module export, checklist, and proof handoff details."""

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

    def install_authored_module(self, dry_run: bool = False) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Stage authored module package and proof files", self._last_output_dir or "")
        if not path:
            return
        modules_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select KOTOR Modules folder", "")
        if not modules_path:
            return
        module_root = self._map_studio_authored_module_root_for_install()
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
        self._last_game_modules_dir = modules_path
        self._log_authored_module_stage_result(result)
        if not result.ok:
            QtWidgets.QMessageBox.warning(self, "Install Authored Module", result.message)
        self._refresh_all("Authored module game-test install updated.")

    def record_game_smoke_proof(self) -> None:
        try:
            proof_defaults = self.controller.map_studio_game_proof_recording_handoff()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", str(exc))
            return
        self._focus_map_studio_export_proof_workspace()
        self._record_game_smoke_proof_from_summary(proof_defaults)

    def _record_game_smoke_proof_from_summary(self, proof_defaults: Any) -> bool:
        """Open the proof dialog using the controller's proof-recording defaults."""

        blockers = tuple(getattr(proof_defaults, "blocking_messages", ()) or ())
        for blocker in blockers:
            self._log(f"Proof recording setup: {blocker}")
        for warning in tuple(getattr(proof_defaults, "warnings", ()) or ()):
            self._log(f"Warning: {warning}")
        default_manifest = str(getattr(proof_defaults, "proof_manifest_path", "") or "")
        dialog = _MapStudioGameProofDialog(self, proof_manifest_path=default_manifest)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return False
        values = dialog.values()
        if not values["proof_manifest_path"]:
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", "Choose the proof manifest written by the Map Studio stage action.")
            return False
        if not values["evidence_path"] and not values["allow_missing_evidence"]:
            QtWidgets.QMessageBox.warning(self, "Record Game Smoke Proof", "Choose screenshot or video evidence from the actual KOTOR test.")
            return False
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
            return False
        self._refresh_all("Map Studio game proof updated.")
        return True

    def open_map_studio_launch_handoff(self) -> None:
        try:
            handoff = self.controller.map_studio_launch_handoff()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Open Launch Handoff", str(exc))
            return
        self._focus_map_studio_export_proof_workspace()
        self._open_map_studio_launch_handoff_dialog_from_summary(handoff)

    def _open_map_studio_launch_handoff_dialog_from_summary(self, handoff: Any) -> None:
        """Open the launch/proof handoff dialog from the controller's non-mutating summary."""

        blockers = tuple(getattr(handoff, "blocking_messages", ()) or ())
        if blockers or not bool(getattr(handoff, "ready", False)):
            message = "\n".join(blockers) if blockers else "Stage or install an authored module game-test package first."
            QtWidgets.QMessageBox.information(self, "Open Launch Handoff", message)
            self._log(f"Launch handoff not ready: {message}")
            return
        launcher_path = Path(str(getattr(handoff, "launcher_path", "") or getattr(handoff, "elevated_launch_script_path", "") or ""))
        proof_path = Path(str(getattr(handoff, "proof_manifest_path", "") or ""))
        proof_recorder_path = Path(str(getattr(handoff, "proof_recording_script_path", "") or ""))
        dialog = _MapStudioLaunchHandoffDialog(
            self,
            warp_command=str(getattr(handoff, "warp_command", "") or "warp <module>"),
            launcher_path=str(launcher_path) if launcher_path.is_file() else "",
            proof_manifest_path=str(proof_path) if proof_path.is_file() else "",
            proof_recording_script_path=str(proof_recorder_path) if proof_recorder_path.is_file() else "",
            launch_helper_command=str(getattr(handoff, "launch_helper_command", "") or ""),
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        if launcher_path.is_file():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(launcher_path)))
            self._log(f"Opened launch handoff: {launcher_path}")
        elif proof_path.is_file():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(proof_path.parent)))
            self._log(f"Opened proof folder: {proof_path.parent}")
        for warning in tuple(getattr(handoff, "warnings", ()) or ()):
            self._log(f"Warning: {warning}")
        self._log(f"Map Studio warp command: {getattr(handoff, 'warp_command', 'warp <module>')}")

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
        transition_destination: int,
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
                transition_destination=transition_destination,
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

    def preview_authored_floor_plan_vertex_snap_candidates(self, room_resref: str, point_index: int) -> None:
        """Show nearest non-mutating floor-plan vertex snap candidates."""

        setter = getattr(self.builder_tab, "set_floor_plan_vertex_snap_candidates", None)
        viewport_setter = getattr(self.viewport_panel, "set_room_outline_vertex_snap_candidates", None)
        if not callable(setter) and not callable(viewport_setter):
            return
        try:
            candidates = self.controller.authored_floor_plan_vertex_snap_candidates(
                room_resref=room_resref,
                point_index=int(point_index),
                limit=4,
            )
        except Exception:
            return
        if callable(setter):
            setter(candidates)
        if callable(viewport_setter):
            viewport_setter(room_resref, int(point_index), candidates)

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

    def split_authored_floor_plan_face(
        self,
        room_resref: str,
        point_indices: object,
    ) -> None:
        try:
            result = self.controller.split_authored_floor_plan_face(
                room_resref=room_resref,
                point_indices=tuple(point_indices or ()),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Split Floor-Plan Face", str(exc))
            return
        readiness = result.readiness
        message = f"Split floor-plan face in {room_resref}; previous exports/proofs are now stale."
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

        try:
            self.controller.commit_map_studio_terrain_sculpt_stroke(brush=brush, room_resref=room_resref)
        except Exception as exc:
            self._log(f"Terrain brush commit failed: {exc}")
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
        if str(action or "").startswith("tool_belt:"):
            key = str(action).split(":", 1)[1]
            tool_action = self._map_studio_tool_action_index.get(key)
            if tool_action is None:
                tool_action = next(
                    (
                        candidate
                        for candidate in self.controller.available_map_studio_tool_belt_actions()
                        if str(getattr(candidate, "key", "") or "") == key
                    ),
                    None,
                )
            if tool_action is not None:
                self._handle_map_studio_tool_belt_action(tool_action)
            return
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
        self._update_map_studio_undo_redo_actions()
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
        self.export_panel.set_readiness(readiness_result.readiness)
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
