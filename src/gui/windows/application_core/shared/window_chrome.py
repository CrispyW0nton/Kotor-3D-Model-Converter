"""Main-window actions, menus, and top chrome widgets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.assets.qt_matrix_background import QtMatrixLabel, QtMatrixPanel
from src.gui.qt_lib.dialogs.qt_dialogs import (
    show_about,
    show_format_reference,
    show_ipc_info,
    show_viewport_navigation_reference,
)
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS

C = dict(LEGACY_MATRIX_COLORS)
_GUI_DIR = Path(__file__).resolve().parents[3]
_QT_ICON_DIR = (_GUI_DIR / "icons").as_posix()


class WindowChromeMixin:
    """Actions, menus, command strip, and Matrix header behavior."""

    def _build_actions(self):
        self.new_scene_action = QtGui.QAction(self._icon("new_scene"), "New Scene", self)
        self.new_scene_action.setShortcut("Ctrl+N")
        self.new_scene_action.triggered.connect(self._new_scene)
        self.open_scene_action = QtGui.QAction(self._icon("open"), "Open Scene...", self)
        self.open_scene_action.setShortcut("Ctrl+O")
        self.open_scene_action.triggered.connect(self._open_scene)
        self.save_scene_action = QtGui.QAction("Save Scene", self)
        self.save_scene_action.setShortcut("Ctrl+S")
        self.save_scene_action.triggered.connect(self._save_scene)
        self.save_scene_as_action = QtGui.QAction("Save Scene As...", self)
        self.save_scene_as_action.setShortcut("Ctrl+Shift+S")
        self.save_scene_as_action.triggered.connect(self._save_scene_as)
        self.close_scene_action = QtGui.QAction("Close Scene", self)
        self.close_scene_action.triggered.connect(self._close_scene)
        self.export_scene_action = QtGui.QAction("Export Scene...", self)
        self.export_scene_action.triggered.connect(self._export_scene)

        self.open_model_action = QtGui.QAction(self._icon("open"), "Open MDL (binary)...", self)
        self.open_model_action.setShortcut("Ctrl+Shift+M")
        self.open_model_action.triggered.connect(self._open_model)

        self.open_ascii_action = QtGui.QAction("Open MDL (ASCII text)...", self)
        self.open_ascii_action.setShortcut("Ctrl+Shift+O")
        self.open_ascii_action.triggered.connect(lambda _checked=False: self._open_model(ascii_only=True))
        self.clear_model_action = QtGui.QAction("Clear Model", self)
        self.clear_model_action.setShortcut("Ctrl+W")
        self.clear_model_action.triggered.connect(self._clear_model)
        self.import_obj_action = QtGui.QAction("Import OBJ...", self)
        self.import_obj_action.setShortcut("Ctrl+I")
        self.import_obj_action.triggered.connect(self._import_obj)
        self.import_fbx_action = QtGui.QAction("Import FBX...", self)
        self.import_fbx_action.triggered.connect(self._import_fbx)
        self.import_gltf_action = QtGui.QAction("Import GLB/GLTF...", self)
        self.import_gltf_action.triggered.connect(self._import_gltf)
        self.save_ascii_action = QtGui.QAction("Save ASCII MDL...", self)
        self.save_ascii_action.setShortcut("Ctrl+Alt+S")
        self.save_ascii_action.triggered.connect(self._save_ascii_mdl)
        self.export_binary_action = QtGui.QAction("Export Binary MDL...", self)
        self.export_binary_action.setShortcut("Ctrl+M")
        self.export_binary_action.triggered.connect(self._export_mdl_binary)
        self.export_obj_action = QtGui.QAction("Export OBJ...", self)
        self.export_obj_action.setShortcut("Ctrl+E")
        self.export_obj_action.triggered.connect(self._export_obj)
        self.export_fbx_action = QtGui.QAction("Export FBX...", self)
        self.export_fbx_action.triggered.connect(self._export_fbx)
        self.export_selected_fbx_action = QtGui.QAction("Export Selected FBX...", self)
        self.export_selected_fbx_action.triggered.connect(self._export_selected_fbx)
        self.export_gltf_action = QtGui.QAction("Export GLB/GLTF...", self)
        self.export_gltf_action.setShortcut("Ctrl+G")
        self.export_gltf_action.triggered.connect(self._export_gltf)
        self.export_humanoid_action = QtGui.QAction("Export Humanoid Template...", self)
        self.export_humanoid_action.triggered.connect(self._export_humanoid_template)
        self.texture_dir_action = QtGui.QAction("Set Texture Directory...", self)
        self.texture_dir_action.triggered.connect(self._set_texture_dir)
        self.settings_action = QtGui.QAction(self._icon("settings"), "Settings...", self)
        self.settings_action.setShortcut("F2")
        self.settings_action.triggered.connect(self._open_settings_dialog)
        self.theme_editor_action = QtGui.QAction(self._icon("settings"), "Theme Editor...", self)
        self.theme_editor_action.triggered.connect(self._open_theme_editor_window)
        self.autorig_action = QtGui.QAction(self._icon("autorig"), "Auto-Rig Current Model", self)
        self.autorig_action.setShortcut("Ctrl+R")
        self.autorig_action.triggered.connect(self._quick_autorig)
        self.remove_rig_action = QtGui.QAction("Remove Rigging", self)
        self.remove_rig_action.triggered.connect(self._remove_rig)
        self.frame_all_action = QtGui.QAction("Frame All", self)
        self.frame_all_action.setShortcut("F")
        self.frame_all_action.triggered.connect(lambda: self._call_viewport("frame_all"))
        self.reset_camera_action = QtGui.QAction("Reset Camera", self)
        self.reset_camera_action.setShortcut("R")
        self.reset_camera_action.triggered.connect(lambda: self._call_viewport("reset_camera"))
        self.undo_viewport_action = QtGui.QAction("Undo Viewport Edit", self)
        self.undo_viewport_action.setShortcut("Ctrl+Z")
        self.undo_viewport_action.triggered.connect(lambda: self._call_viewport("undo"))
        self.redo_viewport_action = QtGui.QAction("Redo Viewport Edit", self)
        self.redo_viewport_action.setShortcut("Ctrl+Y")
        self.redo_viewport_action.triggered.connect(lambda: self._call_viewport("redo"))
        self.wire_action = QtGui.QAction("Toggle Wireframe", self)
        self.wire_action.setShortcut("W")
        self.wire_action.triggered.connect(lambda: self._click_viewport_button("wire_button"))
        self.bones_action = QtGui.QAction("Toggle Bones", self)
        self.bones_action.setShortcut("B")
        self.bones_action.triggered.connect(lambda: self._click_viewport_button("bones_button"))
        self.texture_action = QtGui.QAction("Toggle Texture", self)
        self.texture_action.setShortcut("T")
        self.texture_action.triggered.connect(lambda: self._click_viewport_button("texture_button"))
        self.grid_action = QtGui.QAction("Toggle Grid", self)
        self.grid_action.setShortcut("Alt+G")
        self.grid_action.triggered.connect(lambda: self._click_viewport_button("grid_button"))
        self.uv_action = QtGui.QAction("Open UV Viewer...", self)
        self.uv_action.triggered.connect(self._open_uv_viewer)
        self.diag_action = QtGui.QAction(self._icon("diag"), "Diagnostics...", self)
        self.diag_action.setShortcut("Ctrl+D")
        self._configure_dock_toggle_action(self.diag_action, "diagnostics", self._show_diagnostics_panel)
        self.fbx_sdk_status_action = QtGui.QAction("FBX SDK Status", self)
        self.fbx_sdk_status_action.triggered.connect(self._show_fbx_sdk_status)
        self.fbx_sdk_setup_action = QtGui.QAction("Autodesk FBX SDK Setup...", self)
        self.fbx_sdk_setup_action.triggered.connect(self._open_fbx_sdk_setup)
        self.info_action = QtGui.QAction("Model Info...", self)
        self.info_action.triggered.connect(self._show_model_info)
        self.refresh_action = QtGui.QAction("Refresh All", self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.triggered.connect(self._refresh_all)
        self.character_builder_action = QtGui.QAction(self._icon("charbuilder"), "Character Builder (New Window)...", self)
        self.character_builder_action.setShortcut("Ctrl+B")
        self.character_builder_action.triggered.connect(self._open_qt_character_builder_window)
        self.anims_action = QtGui.QAction(self._icon("anims"), "Animation Library", self)
        self.anims_action.setShortcut("Ctrl+A")
        self.anims_action.triggered.connect(lambda: self._show_content_browser("Animation"))
        self.animation_browser_dock_action = QtGui.QAction(self._icon("anims"), "Animation Browser", self)
        self._configure_dock_toggle_action(
            self.animation_browser_dock_action,
            "animations",
            lambda: self._show_workspace_dock("animations"),
        )
        self.body_attachment_panel_action = QtGui.QAction(self._icon("body_attachment"), "Body Attachment System", self)
        self._configure_dock_toggle_action(
            self.body_attachment_panel_action,
            "body_attachment",
            lambda: self._show_workspace_dock("body_attachment"),
        )
        self.retarget_workbench_action = QtGui.QAction(self._icon("anims"), "Animation Retargeting Workbench...", self)
        self.retarget_workbench_action.setShortcut("Ctrl+Shift+A")
        self.retarget_workbench_action.triggered.connect(self._open_animation_retarget_window)
        self.load_retarget_source_clip_action = QtGui.QAction("Load UE/FBX Source Animation...", self)
        self.load_retarget_source_clip_action.triggered.connect(self._load_retarget_source_clip)
        self.load_retarget_profile_action = QtGui.QAction("Load Retarget Profile...", self)
        self.load_retarget_profile_action.triggered.connect(self._load_retarget_profile)
        self.preview_retarget_action = QtGui.QAction(self._icon("anims"), "Preview Retarget", self)
        self.preview_retarget_action.setEnabled(False)
        self.preview_retarget_action.triggered.connect(self._preview_retarget_animation)
        self.export_retarget_preview_action = QtGui.QAction("Export Retarget Preview...", self)
        self.export_retarget_preview_action.setEnabled(False)
        self.export_retarget_preview_action.triggered.connect(self._export_retarget_preview)
        self.unreal_animator_action = QtGui.QAction(self._icon("anims"), "Unreal Animator...", self)
        self.unreal_animator_action.setShortcut("Ctrl+Shift+U")
        self.unreal_animator_action.triggered.connect(self._open_unreal_animator_window)
        self.sequence_editor_action = QtGui.QAction(self._icon("sequence"), "Sequence Editor", self)
        self.sequence_editor_action.setShortcut("Ctrl+Alt+Q")
        self._configure_dock_toggle_action(self.sequence_editor_action, "sequence_editor", self._show_sequence_editor_dock)
        self.sequence_editor_window_action = QtGui.QAction(self._icon("anims"), "Sequence Editor (Window)...", self)
        self.sequence_editor_window_action.triggered.connect(self._open_sequence_editor_window)
        self.modules_action = QtGui.QAction(self._icon("modular"), "Open Module Editor", self)
        self.modules_action.triggered.connect(self._open_module_editor_window)
        self.rig_window_action = QtGui.QAction(self._icon("rig"), "Open Rigging Window", self)
        self.rig_window_action.triggered.connect(self._open_rig_window)
        self.texture_tool_action = QtGui.QAction(self._icon("texture"), "Texture Tool...", self)
        self.texture_tool_action.triggered.connect(self._open_texture_tool_window)
        self.blueprint_editor_action = QtGui.QAction(self._icon("library"), "Blueprint Editor...", self)
        self.blueprint_editor_action.triggered.connect(self._open_blueprint_editor_window)
        self.content_browser_action = QtGui.QAction(self._icon("library"), "Open Content Browser", self)
        self._configure_dock_toggle_action(
            self.content_browser_action,
            "content_browser",
            lambda: self._show_content_browser("All"),
        )
        self.scene_panel_action = QtGui.QAction(self._icon("scene"), "Scene Information", self)
        self._configure_dock_toggle_action(self.scene_panel_action, "scene", lambda: self._show_workspace_dock("scene"))
        self.properties_panel_action = QtGui.QAction(self._icon("props"), "Open Properties", self)
        self._configure_dock_toggle_action(
            self.properties_panel_action,
            "properties",
            lambda: self._show_workspace_dock("properties"),
        )
        self.nodes_panel_action = QtGui.QAction(self._icon("skeleton"), "Open Nodes Panel", self)
        self._configure_dock_toggle_action(self.nodes_panel_action, "nodes", lambda: self._show_workspace_dock("nodes"))
        self.lighting_panel_action = QtGui.QAction(self._icon("lights"), "Open Lighting Panel", self)
        self._configure_dock_toggle_action(self.lighting_panel_action, "lighting", lambda: self._show_workspace_dock("lighting"))
        self.camera_panel_action = QtGui.QAction(self._icon("cameras"), "Open Camera Panel", self)
        self._configure_dock_toggle_action(self.camera_panel_action, "cameras", lambda: self._show_workspace_dock("cameras"))
        self.render_frame_action = QtGui.QAction("Render Camera Still...", self)
        self.render_frame_action.triggered.connect(self._open_render_frame_dialog)
        self.twoda_panel_action = QtGui.QAction(self._icon("twoda"), "Open 2DA Browser", self)
        self._configure_dock_toggle_action(self.twoda_panel_action, "2das", lambda: self._show_workspace_dock("2das"))
        self.resources_panel_action = QtGui.QAction(self._icon("resources"), "Open Resource Browser", self)
        self._configure_dock_toggle_action(
            self.resources_panel_action,
            "resources",
            lambda: self._show_workspace_dock("resources"),
        )
        self.module_meshes_panel_action = QtGui.QAction(self._icon("module_meshes"), "Open Module Meshes", self)
        self._configure_dock_toggle_action(
            self.module_meshes_panel_action,
            "module_meshes",
            lambda: self._show_workspace_dock("module_meshes"),
        )
        self.sprite_materials_panel_action = QtGui.QAction(self._icon("sprite_materials"), "Open Sprite Materials", self)
        self._configure_dock_toggle_action(
            self.sprite_materials_panel_action,
            "sprite_materials",
            lambda: self._show_workspace_dock("sprite_materials"),
        )
        self.adjust_pivot_panel_action = QtGui.QAction(self._icon("viewport_gimbal"), "Open Adjust Pivot", self)
        self._configure_dock_toggle_action(
            self.adjust_pivot_panel_action,
            "adjust_pivot",
            lambda: self._show_workspace_dock("adjust_pivot"),
        )
        self.set_mdlops_action = QtGui.QAction("Set MDLOps Path...", self)
        self.set_mdlops_action.triggered.connect(self._set_mdlops)
        self.compile_action = QtGui.QAction("Compile ASCII MDL to Binary", self)
        self.compile_action.triggered.connect(self._compile_mdlops)
        self.decompile_action = QtGui.QAction("Decompile Binary MDL", self)
        self.decompile_action.triggered.connect(self._decompile_mdlops)
        self.port_model_action = QtGui.QAction("Port Current Model (K1/K2)...", self)
        self.port_model_action.triggered.connect(self._port_current_model)
        self.generate_module_action = QtGui.QAction("Generate Module Files...", self)
        self.generate_module_action.triggered.connect(self._generate_module_files)
        self.about_module_action = QtGui.QAction("About Module Editor", self)
        self.about_module_action.triggered.connect(self._about_modular)
        self.validate_character_action = QtGui.QAction("Validate Current Character...", self)
        self.validate_character_action.triggered.connect(self._validate_current_character)
        self.ping_scripter_action = QtGui.QAction("Ping GhostScripter (port 7002)...", self)
        self.ping_scripter_action.triggered.connect(lambda: self._ipc_ping("GhostScripter", 7002))
        self.ping_gmodular_action = QtGui.QAction("Ping GModular (port 7003)...", self)
        self.ping_gmodular_action.triggered.connect(lambda: self._ipc_ping("GModular", 7003))
        self.notify_gmodular_action = QtGui.QAction("Notify GModular: Blueprint Saved...", self)
        self.notify_gmodular_action.triggered.connect(self._ipc_notify_saved)
        self.refresh_gmodular_action = QtGui.QAction("Refresh GModular Viewport", self)
        self.refresh_gmodular_action.triggered.connect(self._ipc_refresh_gmodular)
        self.about_action = QtGui.QAction("About GhostRigger...", self)
        self.about_action.triggered.connect(lambda: show_about(self))

        self.quit_action = QtGui.QAction("Exit", self)
        self.quit_action.setShortcut("Alt+F4")
        self.quit_action.triggered.connect(self.close)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_scene_action)
        file_menu.addAction(self.open_scene_action)
        self.recent_scenes_menu = file_menu.addMenu("Recent Scenes")
        self._rebuild_recent_scenes_menu()
        file_menu.addAction(self.save_scene_action)
        file_menu.addAction(self.save_scene_as_action)
        file_menu.addAction(self.close_scene_action)
        file_menu.addSeparator()
        file_menu.addAction(self.open_model_action)
        file_menu.addAction(self.open_ascii_action)
        file_menu.addAction(self.clear_model_action)
        file_menu.addSeparator()
        file_menu.addAction(self.import_obj_action)
        file_menu.addAction(self.import_fbx_action)
        file_menu.addAction(self.import_gltf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_ascii_action)
        file_menu.addAction(self.export_scene_action)
        file_menu.addAction(self.export_binary_action)
        file_menu.addAction(self.export_obj_action)
        file_menu.addAction(self.export_fbx_action)
        file_menu.addAction(self.export_selected_fbx_action)
        file_menu.addAction(self.export_gltf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_humanoid_action)
        file_menu.addSeparator()
        file_menu.addAction(self.texture_dir_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        customise_menu = self.menuBar().addMenu("Customise")
        customise_menu.addAction(self.settings_action)
        customise_menu.addAction(self.theme_editor_action)

        model_menu = self.menuBar().addMenu("Model")
        for action in (
            self.autorig_action,
            self.remove_rig_action,
            None,
            self.frame_all_action,
            self.reset_camera_action,
            None,
            self.undo_viewport_action,
            self.redo_viewport_action,
            None,
            self.wire_action,
            self.bones_action,
            self.texture_action,
            self.grid_action,
            None,
            self.uv_action,
            self.info_action,
            self.refresh_action,
        ):
            self._add_menu_action(model_menu, action)

        mdlops_menu = self.menuBar().addMenu("MDLOps")
        mdlops_menu.addAction(self.set_mdlops_action)
        mdlops_menu.addAction(self.compile_action)
        mdlops_menu.addAction(self.decompile_action)

        help_menu = self.menuBar().addMenu("Help")
        format_action = QtGui.QAction("KotOR MDL Format Reference", self)
        format_action.triggered.connect(lambda: show_format_reference(self))
        viewport_controls_action = QtGui.QAction("Viewport Navigation Controls", self)
        viewport_controls_action.triggered.connect(lambda: show_viewport_navigation_reference(self))
        help_menu.addAction(self.about_action)
        help_menu.addAction(viewport_controls_action)
        help_menu.addAction(format_action)
        diagnostics_menu = help_menu.addMenu("Diagnostics")
        diagnostics_menu.addAction(self.fbx_sdk_status_action)

        retarget_menu = self.menuBar().addMenu("Retarget")
        retarget_menu.addAction(self.load_retarget_source_clip_action)
        retarget_menu.addAction(self.load_retarget_profile_action)
        retarget_menu.addAction(self.preview_retarget_action)
        retarget_menu.addAction(self.export_retarget_preview_action)
        retarget_menu.addSeparator()
        retarget_menu.addAction(self.retarget_workbench_action)
        retarget_menu.addAction(self.unreal_animator_action)

        modules_menu = self.menuBar().addMenu("Modules")
        modules_menu.addAction(self.modules_action)
        modules_menu.addAction(self.rig_window_action)
        modules_menu.addAction(self.retarget_workbench_action)
        modules_menu.addAction(self.unreal_animator_action)
        modules_menu.addAction(self.sequence_editor_action)
        modules_menu.addAction(self.sequence_editor_window_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.content_browser_action)
        modules_menu.addAction(self.scene_panel_action)
        modules_menu.addAction(self.properties_panel_action)
        modules_menu.addAction(self.body_attachment_panel_action)
        modules_menu.addAction(self.nodes_panel_action)
        modules_menu.addAction(self.lighting_panel_action)
        modules_menu.addAction(self.camera_panel_action)
        modules_menu.addAction(self.module_meshes_panel_action)
        modules_menu.addAction(self.sprite_materials_panel_action)
        modules_menu.addAction(self.adjust_pivot_panel_action)
        modules_menu.addAction(self.twoda_panel_action)
        modules_menu.addAction(self.resources_panel_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.port_model_action)
        modules_menu.addAction(self.generate_module_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.about_module_action)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.diag_action)
        tools_menu.addAction(self.fbx_sdk_status_action)
        setup_menu = tools_menu.addMenu("Setup")
        setup_menu.addAction(self.fbx_sdk_setup_action)
        tools_menu.addAction(self.render_frame_action)
        tools_menu.addAction(self.texture_tool_action)
        tools_menu.addAction(self.blueprint_editor_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.character_builder_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.validate_character_action)

        ipc_menu = self.menuBar().addMenu("IPC")
        server_action = QtGui.QAction("GhostRigger Server (port 7001) - This Program", self)
        server_action.setEnabled(False)
        ipc_menu.addAction(server_action)
        ipc_menu.addSeparator()
        ipc_menu.addAction(self.ping_scripter_action)
        ipc_menu.addAction(self.ping_gmodular_action)
        ipc_menu.addSeparator()
        ipc_menu.addAction(self.notify_gmodular_action)
        ipc_menu.addAction(self.refresh_gmodular_action)
        ipc_menu.addSeparator()
        ipc_info_action = QtGui.QAction("IPC Protocol Info", self)
        ipc_info_action.triggered.connect(lambda: show_ipc_info(self))
        ipc_menu.addAction(ipc_info_action)

    def _build_toolbar(self):
        # The original GhostRigger top chrome is rebuilt as regular Qt widgets
        # so later panels can be swapped in without changing the host frame.
        pass

    def _icon(self, name: str, size: int = 16) -> QtGui.QIcon:
        if hasattr(self, "theme_manager"):
            return self.theme_manager.icon(name, size)
        svg = _GUI_DIR / "icons" / f"{name}.svg"
        if svg.exists():
            return QtGui.QIcon(str(svg))
        path = _GUI_DIR / "icons" / f"{name}_{size}.png"
        if path.exists():
            return QtGui.QIcon(str(path))
        fallback = _GUI_DIR / "icons" / f"{name}_24.png"
        return QtGui.QIcon(str(fallback)) if fallback.exists() else QtGui.QIcon()

    def _placeholder_action(self, text: str, shortcut: str = "") -> QtGui.QAction:
        action = QtGui.QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda _checked=False, label=text: self._not_migrated(label))
        return action

    def _add_menu_action(self, menu: QtWidgets.QMenu, action: Optional[QtGui.QAction]):
        if action is None:
            menu.addSeparator()
        else:
            menu.addAction(action)

    def _not_migrated(self, label: str):
        self._log(f"{label} is waiting for its Qt panel migration.", "warning")

    def _make_header(self) -> QtWidgets.QFrame:
        header = QtMatrixPanel(engine=self._matrix_engine, opacity=0.55)
        header.setObjectName("HeaderBar")
        header.setFixedHeight(58)
        self.header_bar = header

        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(18, 7, 18, 7)
        layout.setSpacing(10)

        logo = QtWidgets.QLabel()
        pix = self._icon("logo", 24).pixmap(24, 24)
        if not pix.isNull():
            logo.setPixmap(pix)
        else:
            logo.setText("//")
            logo.setStyleSheet(f"color:{C['accent']}; font-weight:bold; font-size:16pt;")
        logo.setStyleSheet(logo.styleSheet() + "background:transparent;")
        layout.addWidget(logo)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title = QtMatrixLabel("GHOSTRIGGER")
        title.setObjectName("GhostTitle")
        subtitle = QtWidgets.QLabel("Odyssey Engine Pipeline  //  KotOR 1 & 2 TSL")
        subtitle.setObjectName("GhostSubtitle")
        subtitle.setStyleSheet("background:transparent;")
        self.header_title = title
        self.header_subtitle = subtitle
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)

        meta_box = QtWidgets.QVBoxLayout()
        meta_box.setContentsMargins(0, 0, 0, 0)
        meta_box.setSpacing(2)
        self.metrics_label = QtWidgets.QLabel("")
        self.metrics_label.setObjectName("HeaderMeta")
        self.version_label = QtWidgets.QLabel(f"v{self.APP_VERSION}")
        self.version_label.setObjectName("HeaderMeta")
        self.ipc_label = QtWidgets.QLabel("IPC: port 7001 *")
        self.ipc_label.setObjectName("HeaderIpcMeta")
        for label in (self.metrics_label, self.version_label, self.ipc_label):
            label.setAlignment(QtCore.Qt.AlignRight)
            label.setStyleSheet(label.styleSheet() + "background:transparent;")
            meta_box.addWidget(label)
        layout.addLayout(meta_box)
        self._apply_matrix_bar_config(header)
        return header

    def _make_command_bar(self) -> QtWidgets.QWidget:
        host = QtWidgets.QFrame()
        host.setObjectName("CommandBarHost")
        host.setMinimumHeight(36)
        self.command_bar_host = host

        host_layout = QtWidgets.QHBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)

        bar = QtWidgets.QFrame(host)
        bar.setObjectName("CommandBar")
        bar.setMinimumHeight(36)
        self.command_bar = bar

        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(5)

        self.model_pill = QtWidgets.QLabel("// Untitled Scene")
        self.model_pill.setObjectName("ModelPill")
        self.model_pill.setMinimumWidth(170)
        self.model_pill.setMaximumWidth(260)
        self.model_pill.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.model_pill.setToolTip("Active KMAX scene.")
        layout.addWidget(self.model_pill, 0, QtCore.Qt.AlignVCenter)

        layout.addWidget(self._tool_button("New Scene  Ctrl+N", self.new_scene_action, "new_scene"))
        layout.addWidget(self._tool_button("Open Scene  Ctrl+O", self.open_scene_action, "open"))
        layout.addWidget(self._tool_button("Save  Ctrl+S", self.save_scene_action, "save"))
        layout.addWidget(self._tool_button("Auto-Rig  R", self.autorig_action, "autorig"))
        layout.addWidget(self._tool_button("Character Builder", self.character_builder_action, "charbuilder"))
        layout.addWidget(self._tool_button("Modules", self.modules_action, "modular"))
        layout.addWidget(self._tool_button("Tex Dir", self.texture_dir_action, "texture"))
        layout.addWidget(self._tool_button("Settings  F2", self.settings_action, "settings", compact=True))

        import_button = self._menu_button("Import", "import", [
            self.import_obj_action,
            self.import_fbx_action,
            self.import_gltf_action,
            None,
            self.open_ascii_action,
        ])
        export_button = self._menu_button("Export", "export", [
            self.export_binary_action,
            self.export_obj_action,
            self.export_fbx_action,
            self.export_gltf_action,
            None,
            self.export_humanoid_action,
            None,
            self.save_ascii_action,
            self.compile_action,
        ])
        layout.addWidget(import_button)
        layout.addWidget(export_button)

        layout.addStretch(1)
        layout.addWidget(self._tool_button("Content", self.content_browser_action, "library", compact=True))
        layout.addWidget(self._tool_button("Scene Information", self.scene_panel_action, "scene", compact=True))
        layout.addWidget(self._tool_button("Properties", self.properties_panel_action, "props", compact=True))
        layout.addWidget(self._tool_button("BAS", self.body_attachment_panel_action, "body_attachment", compact=True))
        layout.addWidget(self._tool_button("Sequence Editor", self.sequence_editor_action, "sequence", compact=True))
        layout.addWidget(self._tool_button("Animation Browser", self.animation_browser_dock_action, "anims", compact=True))
        layout.addWidget(self._tool_button("Nodes", self.nodes_panel_action, "skeleton", compact=True))
        layout.addWidget(self._tool_button("Lighting", self.lighting_panel_action, "lights", compact=True))
        layout.addWidget(self._tool_button("Cameras", self.camera_panel_action, "cameras", compact=True))
        layout.addWidget(self._tool_button("Module Meshes", self.module_meshes_panel_action, "module_meshes", compact=True))
        layout.addWidget(self._tool_button("Sprite Materials", self.sprite_materials_panel_action, "sprite_materials", compact=True))
        layout.addWidget(self._tool_button("Adjust Pivot", self.adjust_pivot_panel_action, "viewport_gimbal", compact=True))
        layout.addWidget(self._tool_button("2DA Browser", self.twoda_panel_action, "twoda", compact=True))
        layout.addWidget(self._tool_button("Resource Browser", self.resources_panel_action, "resources", compact=True))
        layout.addWidget(self._tool_button("Diagnostics  Ctrl+D", self.diag_action, "diag", compact=True))

        self.visual_profile_combo = QtWidgets.QComboBox()
        self.visual_profile_combo.setObjectName("VisualProfileCombo")
        self.visual_profile_combo.setToolTip("Apply a saved visual profile layout.")
        self.visual_profile_combo.setMinimumWidth(170)
        self._populate_visual_profile_combo()
        self.visual_profile_combo.currentIndexChanged.connect(self._on_visual_profile_selected)
        bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        host_layout.addWidget(bar, 1)
        host_layout.addWidget(self.visual_profile_combo, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return host

    def _populate_visual_profile_combo(self) -> None:
        combo = getattr(self, "visual_profile_combo", None)
        if combo is None:
            return
        combo.blockSignals(True)
        try:
            combo.clear()
            for layout in self.layout_manager.available_layouts():
                if layout.id == "default":
                    continue
                combo.addItem(layout.name, layout.id)
            selected = self.layout_manager.settings.selected_layout
            index = combo.findData(selected)
            combo.setCurrentIndex(max(index, 0))
        finally:
            combo.blockSignals(False)

    def _on_visual_profile_selected(self, _index: int) -> None:
        combo = getattr(self, "visual_profile_combo", None)
        if combo is None:
            return
        layout_id = str(combo.currentData() or "default")
        current = self.layout_manager.settings.selected_layout
        if layout_id == current:
            return
        self.layout_manager.select_layout(layout_id, window=self)
        self._sync_theme_layout_settings()
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Could not save visual profile: {exc}", "warning")
        layout = self.layout_manager.get_layout(layout_id)
        self._log(f"Visual profile applied: {layout.name}", "success")

    def _make_viewport_toolbar_band(self, toolbar: QtWidgets.QWidget | None) -> QtWidgets.QWidget | None:
        if toolbar is None:
            return None
        band = QtWidgets.QFrame()
        band.setObjectName("ViewportToolbarBand")
        band.setFrameShape(QtWidgets.QFrame.StyledPanel)
        band.setLineWidth(1)
        band.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        band.setFixedHeight(max(28, toolbar.height()))
        row = QtWidgets.QHBoxLayout(band)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        toolbar.setParent(band)
        toolbar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        row.addWidget(toolbar, 1)
        self.viewport_toolbar_band = band
        self.viewport_toolbar_hosted_scroll = toolbar
        return band

    def _sync_viewport_toolbar_band(self) -> None:
        toolbar = getattr(self, "viewport_toolbar_hosted_scroll", None)
        band = getattr(self, "viewport_toolbar_band", None)
        if toolbar is not None and band is not None:
            height = self._height_for_wrapping_widget(toolbar, max(28, toolbar.sizeHint().height()))
            toolbar.setMinimumHeight(height)
            toolbar.setMaximumHeight(height)
            band.setFixedHeight(height)

    def _sync_reserved_top_rows(self) -> None:
        command_bar = getattr(self, "command_bar", None)
        if command_bar is not None:
            height = self._height_for_wrapping_widget(command_bar, max(36, command_bar.sizeHint().height()))
            command_bar.setMinimumHeight(height)
            command_bar.setMaximumHeight(height)
            host = getattr(self, "command_bar_host", None)
            if host is not None:
                host_height = max(36, height, host.sizeHint().height())
                host.setMinimumHeight(host_height)
                host.setMaximumHeight(host_height)
        self._sync_viewport_toolbar_band()
        top_shell = getattr(self, "reserved_top_shell", None)
        if top_shell is not None:
            top_shell.updateGeometry()
        top_toolbar = getattr(self, "reserved_top_toolbar", None)
        if top_toolbar is not None:
            top_toolbar.updateGeometry()

    @staticmethod
    def _height_for_wrapping_widget(widget: QtWidgets.QWidget, fallback: int) -> int:
        layout = widget.layout()
        width = max(1, widget.width())
        if layout is not None and layout.hasHeightForWidth():
            return max(1, layout.heightForWidth(width))
        return max(1, int(fallback))

    def _matrix_bar_settings(self, theme=None) -> dict:
        legacy = dict(self.settings_data.get("matrix_bar", {}))
        style = ""
        glyphs = ""
        font_family = ""
        image_path = ""
        if theme is not None:
            styles = getattr(theme, "styles", {})
            style = str(styles.get("matrixBar.style", "") or "")
            glyphs = str(styles.get("matrixBar.glyphs", "") or "")
            font_family = str(styles.get("matrixBar.fontFamily", "") or "")
            image_path = str(styles.get("matrixBar.imagePath", "") or "")
            try:
                crop = (
                    float(styles.get("matrixBar.cropX", 0) or 0),
                    float(styles.get("matrixBar.cropY", 0) or 0),
                    float(styles.get("matrixBar.cropW", 100) or 100),
                    float(styles.get("matrixBar.cropH", 100) or 100),
                )
            except (TypeError, ValueError):
                crop = (0.0, 0.0, 100.0, 100.0)
        else:
            crop = (0.0, 0.0, 100.0, 100.0)
        if not style:
            style = str(legacy.get("style") or ("matrix" if self.settings_data.get("matrix_background", True) else "disabled"))
        return {
            "style": style,
            "glyphs": glyphs or str(legacy.get("glyphs") or ""),
            "font_family": font_family or str(legacy.get("font_family") or ""),
            "image_path": image_path or str(legacy.get("image_path") or ""),
            "crop": crop,
        }

    def _apply_matrix_bar_config(self, panel: QtMatrixPanel, theme=None) -> None:
        cfg = self._matrix_bar_settings(theme)
        style = str(cfg.get("style") or "matrix")
        panel.set_matrix_config(
            style=style,
            glyphs=str(cfg.get("glyphs") or ""),
            font_family=str(cfg.get("font_family") or ""),
            image_path=str(cfg.get("image_path") or ""),
            crop=cfg.get("crop"),
        )

    def _apply_matrix_theme(self, theme) -> None:
        for panel in (getattr(self, "header_bar", None),):
            if panel is not None:
                self._apply_matrix_bar_config(panel, theme)
                panel.apply_ghost_theme(theme)
        if hasattr(self, "header_subtitle"):
            self.header_subtitle.setStyleSheet(
                f"color:{theme.color('matrixBar.subtext', theme.color('text.secondary'))}; background:transparent;"
            )
        for label in (getattr(self, "metrics_label", None), getattr(self, "version_label", None)):
            if label is not None:
                label.setStyleSheet(
                    f"color:{theme.color('matrixBar.metaText', theme.color('text.secondary'))}; background:transparent;"
                )
        if hasattr(self, "ipc_label"):
            self.ipc_label.setStyleSheet(
                f"color:{theme.color('matrixBar.ipcText', theme.color('accent.primary'))}; background:transparent; font-size:7pt;"
            )

    def _tool_button(
        self,
        text: str,
        action: QtGui.QAction,
        icon_name: str = "",
        accent: bool = False,
        compact: bool = False,
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("CommandStripButton")
        button.setText(text)
        button.setProperty("_gr_full_text", text)
        button.setProperty("_gr_ignore_layout_button_mode", True)
        if icon_name:
            button.setIcon(self._icon(icon_name, 18))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        button.setIconSize(QtCore.QSize(18, 18))
        button.setFixedSize(30, 22)
        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        button.setProperty("accent", accent)
        button.setProperty("compact", compact)
        if action.isCheckable():
            button.setCheckable(True)
            button.setChecked(action.isChecked())
            action.toggled.connect(button.setChecked)
        button.clicked.connect(action.trigger)
        if action.shortcut():
            button.setToolTip(f"{action.text()} ({action.shortcut().toString()})")
        else:
            button.setToolTip(action.text())
        return button

    def _menu_button(
        self,
        text: str,
        icon_name: str,
        actions: list[Optional[QtGui.QAction]],
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("CommandStripMenuButton")
        button.setText(text)
        button.setProperty("_gr_full_text", text)
        button.setProperty("_gr_ignore_layout_button_mode", True)
        button.setIcon(self._icon(icon_name, 18))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        button.setIconSize(QtCore.QSize(18, 18))
        button.setFixedSize(34, 22)
        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        button.setToolTip(text)
        menu = QtWidgets.QMenu(button)
        for action in actions:
            self._add_menu_action(menu, action)
        button.setMenu(menu)
        return button

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Plain)
        sep.setStyleSheet(f"color:{C['border']}; background:{C['border']};")
        sep.setFixedWidth(1)
        return sep
