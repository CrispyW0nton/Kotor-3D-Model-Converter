"""Standalone GhostRigger Module/Level Editor window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject, LevelScene, LevelTransform
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
from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE


class ModuleEditorWindow(QtWidgets.QMainWindow):
    """Top-level KMAP/Module Editor window with its own menus and viewport."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        theme_manager: Any = None,
        layout_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setWindowTitle("GhostRigger Module Editor")
        self.controller = ModuleEditorController()
        self.theme_manager = theme_manager or getattr(parent, "theme_manager", None)
        self.layout_manager = layout_manager or getattr(parent, "layout_manager", None)
        self._last_output_dir = ""
        self._library_rows: list[dict[str, Any]] = []
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
        self.help_action = QtGui.QAction("Module Editor Help", self)
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
        self.builder_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())
        self.builder_tab.set_gameplay_placement_kinds(self.controller.available_authored_gameplay_placement_kinds())
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
        self.readiness_panel = ModuleReadinessPanel(right)
        self.export_panel = ModuleExportPanel(right)
        right_tabs = QtWidgets.QTabWidget()
        right_tabs.addTab(self.properties, "Properties")
        export_page = QtWidgets.QWidget(right_tabs)
        export_layout = QtWidgets.QVBoxLayout(export_page)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.addWidget(self.readiness_panel)
        export_layout.addWidget(self.export_panel)
        right_tabs.addTab(export_page, "Export")
        right_layout.addWidget(right_tabs, 1)
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
        self.statusBar().showMessage("Module Editor ready.")
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([285, 1220, 320])

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
        self.help_action.triggered.connect(lambda: self._show_help("Module Editor"))
        self.kmap_help_action.triggered.connect(lambda: self._show_help("KMAP Format"))
        self.toolbar.actionRequested.connect(self._toolbar_action)
        self.toolbar.viewModeChanged.connect(self.viewport_panel.set_view_mode)
        self.asset_browser.importRequested.connect(self.import_library_asset)
        self.outliner.itemSelected.connect(self.select_item)
        self.outliner.actionRequested.connect(self._outliner_action)
        self.viewport_panel.itemSelected.connect(self.select_item)
        self.validation_panel.issueActivated.connect(self.select_item)
        self.readiness_panel.gameTestRequested.connect(lambda: self._log("Run the installed module in KOTOR and record proof before marking game-tested."))
        self.properties.transformChanged.connect(self._set_transform)
        self.properties.visibilityChanged.connect(lambda item_id, value: self._set_visibility(item_id, value))
        self.properties.lockChanged.connect(lambda item_id, value: self._set_locked(item_id, value))
        self.properties.propertyChanged.connect(self._set_property)
        self.export_panel.exportRequested.connect(self.export_fbx)
        self.export_panel.devTestModuleRequested.connect(self.stage_dev_test_module)
        self.export_panel.authoredModuleRequested.connect(self.export_authored_module)
        self.export_panel.authoredModuleStageRequested.connect(self.stage_authored_module)
        for tab in (self.rooms_tab, self.walkmesh_tab, self.porter_tab, self.builder_tab, self.blueprints_tab):
            tab.actionRequested.connect(self._handle_tab_action)
        self.builder_tab.primitivePresetRequested.connect(self.create_authored_room_preset)
        self.builder_tab.roomOperationRequested.connect(self.apply_authored_room_operation)
        self.builder_tab.roomStyleRequested.connect(self.apply_authored_room_style)
        self.builder_tab.gameplayPlacementRequested.connect(self.add_authored_gameplay_placement)
        self.outliner_action.toggled.connect(lambda visible: self.outliner.setVisible(visible))
        self.properties_action.toggled.connect(lambda visible: self.properties.setVisible(visible))
        self.viewport_action.toggled.connect(lambda visible: self.viewport_panel.setVisible(visible))
        self.validation_action.toggled.connect(lambda visible: self.bottom_tabs.setVisible(visible))

    def new_kmap(self) -> None:
        if not self._confirm_discard_or_save():
            return
        self.controller.new_project()
        self._refresh_all("Created new KMAP project.")

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
            self._refresh_all("Duplicated selected room.")

    def rename_selected(self) -> None:
        item_id = self.controller.model.selected_ids[0] if self.controller.model.selected_ids else ""
        if not item_id:
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
        for warning in result.warnings:
            self._log(f"Warning: {warning}")
        for issue in result.blocking_issues:
            self._log(f"Blocking: {issue}")
        self._refresh_all("Authored module game-test staging updated.")

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
        self.statusBar().showMessage(f"Selected {item_id}")

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
        if LevelScene(self.project).set_transform(item_id, transform):
            self._refresh_all()

    def _set_visibility(self, item_id: str, visible: bool) -> None:
        if LevelScene(self.project).set_visibility(item_id, visible):
            self._refresh_all()

    def _set_locked(self, item_id: str, locked: bool) -> None:
        if LevelScene(self.project).set_locked(item_id, locked):
            self._refresh_all()

    def _set_property(self, item_id: str, key: str, value: Any) -> None:
        item = self.project.find_room(item_id) or self.project.find_module(item_id) or self.project.find_blueprint(item_id)
        if item is None:
            return
        if key == "name" and hasattr(item, "module_name"):
            item.module_name = str(value)
        elif hasattr(item, key):
            setattr(item, key, value)
        self.project.mark_dirty()
        self._refresh_all()

    def _refresh_all(self, message: str = "") -> None:
        self.setWindowTitle(f"GhostRigger Level Editor - {self.project.name}{' *' if self.project.dirty else ''}")
        self.properties.set_project(self.project)
        self.outliner.set_project(self.project)
        self.viewport_panel.set_project(self.project)
        readiness_result = self.controller.authored_module_readiness()
        self.readiness_panel.set_readiness(readiness_result.readiness)
        if self.controller.model.selected_ids:
            self.select_item(self.controller.model.selected_ids[0])
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
            "The Module Editor works on GhostRigger KMAP projects. KMAP stores source references, transforms, editable room/module state, walkmesh metadata, blueprints, textures, validation data, and export manifests without embedding heavy mesh or texture blobs.",
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
