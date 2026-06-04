"""Qt main-window shell for GhostRigger.

This is the first migration step away from Tkinter.  Qt owns the main
application window and process event loop. Legacy Tk tools were removed in
M3/T302; this shell exposes only Qt workflows.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import traceback
import copy
import importlib
from contextlib import contextmanager
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Optional

log = logging.getLogger(__name__)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Tk fallback
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

try:  # PySide exposes object-lifetime checks through shiboken.
    import shiboken6
except Exception:  # pragma: no cover - defensive fallback for unusual PySide installs
    shiboken6 = None

from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, enrich_library_rows_with_resource_metadata
from src.gui.qt_lib.panels.qt_log_panel import QtLogPanel, QtLogPanelHandler
from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel
from src.gui.qt_lib.panels.qt_camera_panel import QtCameraPanel
from src.gui.qt_lib.panels.qt_mesh_tools_panel import QtMeshToolsPanel
from src.gui.qt_lib.panels.qt_sprite_material_panel import QtSpriteMaterialPanel
from src.gui.qt_lib.panels.adjust_pivot_panel import AdjustPivotPanel
from src.gui.qt_lib.assets.qt_theme import (
    make_scrollable_panel,
    update_legacy_palette,
)
from src.gui.qt_lib.assets.qt_matrix_background import QtMatrixEngine, QtMatrixLabel, QtMatrixPanel
from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel
from src.gui.qt_lib.panels.qt_skeleton_panel import QtSkeletonPanel
from src.gui.qt_lib.panels.qt_scene_outliner_panel import QtSceneOutlinerPanel
from src.gui.qt_lib.viewports.qt_viewport import QtMainViewportWidget
from src.gui.viewports.viewport_core.widget_scaffold import create_custom_viewport_widget
from src.gui.qt_lib.panels.qt_animation_panel import (
    QtAnimationsPanel,
    animation_row_label,
)
from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel
from src.gui.qt_lib.windows.qt_blueprint_editor import QtBlueprintEditorWindow
from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.gui.qt_lib.panels.qt_diagnostics_panel import QtDiagnosticsPanel, QtDiagnosticsWindow
from src.gui.qt_lib.dialogs.qt_dialogs import show_about, show_format_reference, show_ipc_info, show_viewport_navigation_reference
from src.gui.qt_lib.dialogs.add_model_to_scene_dialog import AddModelToSceneChoice, AddModelToSceneDialog
from src.gui.qt_lib.dialogs.qt_lightmap_baker_dialog import QtLightmapBakerDialog
from src.gui.qt_lib.dialogs.qt_render_frame_dialog import QtRenderFrameDialog
from src.gui.qt_lib.panels.qt_resource_panel import QtResourceBrowserPanel, QtTwoDaBrowserPanel
from src.gui.qt_lib.windows.module_editor_window import ModuleEditorWindow
from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow
from src.gui.qt_lib.windows.qt_retarget_preview_controller import (
    QtRetargetViewportAdapter,
    RetargetPreviewUiController,
)
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import (
    RetargetWorkbenchController,
    combo_current_retarget_mode,
)
from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode
from src.gui.qt_lib.panels.qt_rig_panel import QtRigWindow
from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog, save_settings
from src.gui.qt_lib.panels.qt_texture_panel import QtTextureToolWindow
from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow
from src.gui.qt_lib.sequence_editor.sequence_editor_window import SequenceEditorWindow
from src.ipc.server import GhostRiggerIPCServer
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE, normalize_viewport_navigation_profile
from src.core.rendering.hardware_info import collect_hardware_diagnostics
from src.systems.bas.attachment_alignment import (
    default_bas_attachment_transform,
    normalize_bas_transform,
)
from src.core.rendering.renderer_backend import RendererBackend, renderer_backend_label, supported_renderer_backend
from src.adapters.rendering.renderer_factory import renderer_capabilities_snapshot
from src.core.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.integration.editor_services import (
    ActiveViewportService,
    DiagnosticsService,
    EditorIntegrationEventBus,
    RendererService,
    SceneService,
    SelectionService,
)
from src.gui.qt_lib.integration.tool_integration_registry import build_default_tool_integration_registry
from src.gui.libtheme import LayoutManager, ThemeManager
from src.gui.libtheme.style_tokens import FALLBACK_STYLES, LEGACY_MATRIX_COLORS
from src.gui.libtheme.theme_editor_window import ThemeEditorWindow
from src.gui.libtheme.theme_settings import ThemeLayoutSettings
from src.gui.libtheme.theme_watcher import ThemeLayoutWatcher
from src.gui.qt_lib.windows.progress_toast import QtProgressPanel, QtProgressToast
from src.measurement.unit_settings import MeasurementSettings
from src.core.scene.kmax_scene_manager import KMaxSceneManager
from src.core.scene.axis_mode import AxisMode
from src.core.scene.scene_object import Transform
from src.core.scene.scene_resource_ref import SceneResourceRef
from src.systems.bas.model_recipe import (
    BAS_SLOT_ORDER,
    BAS_SOCKET_BY_SLOT,
    build_bas_model_recipe,
    load_bas_model_recipe,
    save_bas_model_recipe,
)


C = dict(LEGACY_MATRIX_COLORS)
_SPLASH_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}

_GUI_DIR = Path(__file__).resolve().parents[1]
_QT_ICON_DIR = (_GUI_DIR / "icons").as_posix()
_WGPU_BACKEND_TYPES = {
    RendererBackend.WGPU_D3D12.value: "D3D12",
    RendererBackend.PYGFX_WGPU.value: "D3D12",
}

from src.gui.windows.application_core.application_core_lib.shared.dock_hosts import QtDetachableDockWidget, QtFloatingDockHost
from src.gui.windows.application_core.application_core_lib.functions.geometry import (
    _bounds_center,
    _bounds_from_points,
    _bounds_overlap_xy,
    _prebuild_gpu_mesh_data_for_model,
    _walkmesh_overlay_node_from_wok,
    _walkmesh_overlay_offset_for_model,
    _walkmesh_reference_bounds,
)
from src.gui.windows.application_core.application_core_lib.shared.log_panel import GhostRiggerLogPanel
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import (
    _primary_screen_available_geometry,
    _qt_object_alive,
    _wgpu_backend_type,
    _wgpu_backend_restart_required,
)
from src.gui.windows.application_core.application_core_lib.shared.splash import QtStartupSplash, _ThemeColorOverride
from src.gui.windows.application_core.application_core_lib.functions.splash_theme import (
    _darken_hex,
    _lighten_hex,
    _native_splash_palette_colors,
    _palette_hex,
    _surface_fill,
)
from src.gui.windows.application_core.application_core_lib.shared.scene_workflow import SceneWorkflowMixin
from src.gui.windows.application_core.application_core_lib.shared.viewport_tools import ViewportToolsMixin
from src.gui.windows.application_core.application_core_lib.shared.model_io import ModelIoMixin
from src.gui.windows.application_core.application_core_lib.shared.retarget_workflow import RetargetWorkflowMixin
from src.gui.windows.application_core.application_core_lib.shared.animation_workflow import AnimationWorkflowMixin
from src.gui.windows.application_core.application_core_lib.shared.bas_workflow import BasWorkflowMixin
from src.gui.windows.application_core.application_core_lib.shared.resource_panels import ResourcePanelsMixin
from src.gui.windows.application_core.application_core_lib.shared.retarget_window_workflow import RetargetWindowWorkflowMixin
from src.gui.windows.application_core.application_core_lib.shared.resource_loading import ResourceLoadingMixin
from src.gui.windows.application_core.application_core_lib.shared.window_lifecycle import WindowLifecycleMixin
from src.gui.windows.application_core.application_core_lib.shared.editor_services import EditorServicesMixin
from src.gui.windows.application_core.application_core_lib.shared.startup_library import StartupLibraryMixin
from src.gui.windows.application_core.application_core_lib.shared.main_layout import MainWindowLayoutMixin
from src.gui.windows.application_core.application_core_lib.shared.window_chrome import WindowChromeMixin
from src.gui.windows.application_core.application_core_lib.shared.theme_layout import ThemeLayoutMixin
from src.gui.windows.application_core.application_core_lib.toolboxes.workspace_docks import WorkspaceDockMixin
from src.gui.windows.application_core.application_core_lib.shared.workers import (
    AnimationLibraryScanWorker,
    AutoDetectWorker,
    LibraryBatchExportWorker,
    LibraryScanWorker,
    ModelListItem,
    ModelLoadWorker,
    ResourceModelLoadWorker,
)
from src.gui.windows.application_core.application_core_lib.functions.app_runner import run_qt_application
from src.gui.windows.application_core.application_core_lib.functions.startup_library import (
    _build_prelaunch_library_input as _build_prelaunch_library_input_impl,
    _collect_prewindow_startup_diagnostics,
    _index_game_libraries_sync as _index_game_libraries_sync_impl,
    _read_settings_file,
    _write_settings_file,
)


def _index_game_libraries_sync(k1_dir: str = "", k2_dir: str = "") -> tuple[object, list[dict]]:
    return _index_game_libraries_sync_impl(k1_dir, k2_dir)


def _scan_library_rows_sync(k1_dir: str = "", k2_dir: str = "") -> list[dict]:
    _mgr, rows = _index_game_libraries_sync(k1_dir, k2_dir)
    return rows


def _build_prelaunch_library_input(
    app_root: Path,
    startup_input: Optional[dict] = None,
    status_callback=None,
) -> dict:
    return _build_prelaunch_library_input_impl(
        app_root,
        startup_input,
        status_callback,
        indexer=_index_game_libraries_sync,
        read_settings=_read_settings_file,
        write_settings=_write_settings_file,
    )


class QtGhostRiggerMainWindow(
    WindowChromeMixin,
    MainWindowLayoutMixin,
    ViewportToolsMixin,
    ModelIoMixin,
    RetargetWorkflowMixin,
    AnimationWorkflowMixin,
    BasWorkflowMixin,
    ResourcePanelsMixin,
    RetargetWindowWorkflowMixin,
    ResourceLoadingMixin,
    WindowLifecycleMixin,
    SceneWorkflowMixin,
    ThemeLayoutMixin,
    StartupLibraryMixin,
    EditorServicesMixin,
    WorkspaceDockMixin,
    QtWidgets.QMainWindow,
):
    APP_TITLE = "GhostRigger-K1-K2  //  Odyssey Engine Pipeline v6.1"
    APP_VERSION = "6.1.0"
    # Source-contract anchors for tests that still inspect this shell after the
    # behavior moved into mixins:
    # worker.progress.connect(self._on_model_load_progress)
    # gpuUploadProgress.connect(self._on_viewport_gpu_upload_progress)
    # def _on_scene_outliner_helper_node_selected(self, node)
    # self.viewport.set_selected_node(node, source="scene outliner helper")
    # def _on_scene_outliner_light_node_selected(self, node)
    # self.viewport.set_selected_node(node, source="scene outliner light")
    # self.lighting_panel.select_light(node)

    def __init__(self, app_root: Optional[Path] = None, startup_input: Optional[dict] = None):
        super().__init__()
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QtWidgets.QMainWindow.AnimatedDocks
            | QtWidgets.QMainWindow.AllowNestedDocks
            | QtWidgets.QMainWindow.AllowTabbedDocks
            | QtWidgets.QMainWindow.GroupedDragging
        )
        all_dock_areas = (
            QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.TopDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        self.setTabPosition(all_dock_areas, QtWidgets.QTabWidget.North)
        self.app_root = app_root or Path(__file__).resolve().parents[2]
        self.startup_input = startup_input or {}
        self.settings_path = self.app_root / "settings.json"
        self.settings_data = self._load_settings()
        self.settings_data.setdefault("model_double_click_behaviour", "always ask")
        self.settings_data.setdefault("default_import_placement", "auto_offset")
        self.settings_data.setdefault("recent_scenes", [])
        self.settings_data.setdefault("last_axis_mode", AxisMode.WORLD.value)
        self.settings_data.setdefault("last_pivot_edit_mode", "affect_object_only")
        self.settings_data.setdefault("show_adjust_pivot_toolbox", True)
        self.settings_data.setdefault("autoscan", True)
        self.settings_data.setdefault("fbx_sdk", {})
        self.settings_data.setdefault("mixamo_companion_mesh_path", "")
        RendererSettings.apply_defaults(self.settings_data)
        self._preloaded_library = dict(self.startup_input.get("preloaded_library") or {})
        self._preloaded_hardware_diagnostics = dict(self.startup_input.get("hardware_diagnostics") or {})
        self._preloaded_renderer_capabilities = list(self.startup_input.get("renderer_capabilities") or [])
        self._suppress_theme_progress_toast = True
        self.theme_manager = ThemeManager(self.app_root, self.settings_data, self)
        self.layout_manager = LayoutManager(self.app_root, self.settings_data, self)
        self.theme_manager.themeChanged.connect(self._on_theme_changed)
        self.theme_manager.applier.themeApplyStarted.connect(self._on_theme_apply_started)
        self.theme_manager.applier.themeApplyProgress.connect(self._on_theme_apply_progress)
        self.theme_manager.applier.themeApplyFinished.connect(self._on_theme_apply_finished)
        self.theme_manager.applier.themeApplyFailed.connect(self._on_theme_apply_failed)
        self.layout_manager.layoutChanged.connect(self._on_layout_changed)
        self._theme_watcher: Optional[ThemeLayoutWatcher] = None
        self._button_mode_override = self.layout_manager.settings.button_mode_override
        self._icon_size_override = self.layout_manager.settings.icon_size_override
        self._worker_thread: Optional[QtCore.QThread] = None
        self._model_worker: Optional[QtCore.QObject] = None
        self._scan_thread: Optional[QtCore.QThread] = None
        self._scan_worker: Optional[QtCore.QObject] = None
        self._auto_detect_thread: Optional[QtCore.QThread] = None
        self._auto_detect_worker: Optional[QtCore.QObject] = None
        self._animation_scan_thread: Optional[QtCore.QThread] = None
        self._animation_scan_worker: Optional[QtCore.QObject] = None
        self._batch_thread: Optional[QtCore.QThread] = None
        self._batch_worker: Optional[QtCore.QObject] = None
        self._floating_dock_hosts: dict[str, QtFloatingDockHost] = {}
        self._dock_toggle_actions: dict[str, QtGui.QAction] = {}
        self._dock_rehosting = False
        self._library_rows: list[dict] = []
        self.scene_manager = KMaxSceneManager()
        self._scene_texture_dirs: list[str] = []
        self._pending_scene_import_action = "add"
        self._pending_scene_import_placement = str(
            self.settings_data.get("default_import_placement") or "auto_offset"
        )
        self._session_model_double_click_choice = ""
        self._syncing_scene_skeleton_selection = False
        self._current_model = None
        self._bas_body_model = None
        self._bas_preview_model = None
        self._bas_attachments: dict[str, object] = {}
        self._bas_attachment_resrefs: dict[str, str] = {}
        self._bas_attachment_transforms: dict[str, dict[str, list[float]]] = {}
        self._bas_active_build_name = ""
        self._bas_mode = "headless_body"
        self._current_head_model = None
        self._current_attachment_model = None
        self._model_path = ""
        self._current_game = ""
        self._resource_manager = None
        self._resource_manager_dirs: tuple[str, str] = ("", "")
        self._progress_toast: Optional[QtProgressToast] = None
        self._gui_log_handler: Optional[QtLogPanelHandler] = None
        self._ipc_server: Optional[GhostRiggerIPCServer] = None
        self._pending_gpu_upload_model_id = 0
        self._pending_gpu_upload_total = 0
        self._texture_dir = ""
        self._animation_engine = None
        self._animation_loop = False
        self._animation_last_tick: Optional[float] = None
        self._animation_status_last_update = 0.0
        self._retarget_source_model = None
        self._retarget_target_model = None
        self._retarget_engine = None
        self._retarget_mapping_report = None
        self._retarget_last_tick: Optional[float] = None
        self._character_builder_window: Optional[QtCharacterBuilderWindow] = None
        self.sequence_editor_window: Optional[SequenceEditorWindow] = None
        self.sequence_editor_dock: Optional[QtWidgets.QDockWidget] = None
        self.sequence_editor_docked_window: Optional[SequenceEditorWindow] = None
        self._matrix_engine = QtMatrixEngine(self, fps=12)
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._animation_timer.setInterval(30)
        self._animation_timer.timeout.connect(self._tick_animation)
        self._retarget_timer = QtCore.QTimer(self)
        self._retarget_timer.setInterval(33)
        self._retarget_timer.timeout.connect(self._tick_retarget_animation)
        self._configure_fbx_sdk_paths(refresh=True)

        self.setWindowTitle(self.APP_TITLE)
        initial_layout = self.layout_manager.get_layout()
        self.resize(initial_layout.main_width, initial_layout.main_height)
        self.setMinimumSize(1100, 700)
        self._place_on_primary_startup_screen()
        update_legacy_palette(self.theme_manager.get_theme())
        self._build_actions()
        self._diagnostics_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self)
        self._diagnostics_shortcut.activated.connect(self._show_diagnostics_panel)
        self._build_menu()
        self._build_toolbar()
        self._build_layout()
        self.theme_manager.register_theme_aware_widget(self)
        self.theme_manager.apply_current_theme(self)
        self.layout_manager.apply_current_layout(self)
        self._build_statusbar()
        self._apply_preloaded_library()
        self._refresh_scene_view()
        self.scene_manager.active_scene.mark_clean()
        self._update_scene_chrome()
        self._configure_theme_watcher()
        self._log("Qt host window ready.", "success")
        self._start_ipc_server()
        QtCore.QTimer.singleShot(1200, self._enable_theme_progress_toasts)
        QtCore.QTimer.singleShot(0, self._open_startup_inputs)
        if not self._preloaded_library.get("detection_attempted"):
            QtCore.QTimer.singleShot(250, self._auto_detect_dirs_on_startup)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._progress_toast is not None and self._progress_toast.isVisible():
            self._progress_toast._reposition()
        self._sync_reserved_top_rows()

    def _start_ipc_server(self) -> None:
        if self._ipc_server is not None:
            return

        def load_model_by_resref(game: str, resref: str) -> None:
            self._load_resource_model_on_ui_thread(str(resref or ""), str(game or "K2"))

        def open_mdl(resref: str, _module_dir: str = "") -> None:
            game = str(getattr(self, "_current_game", "") or "K2")
            self._load_resource_model_on_ui_thread(str(resref or ""), game)

        def open_blueprint_resource(resource_type: str):
            def _open(resref: str, module_dir: str = "") -> None:
                game = str(getattr(self, "_current_game", "") or "K2")
                self._open_blueprint_resource_from_ipc(resource_type, str(resref or ""), game, str(module_dir or ""))

            return _open

        def refresh_viewport() -> None:
            self._refresh_all()

        def show_panel(panel: str) -> None:
            self._show_workspace_dock(str(panel or ""))

        def select_module_mesh(mesh_name: str) -> None:
            self._select_module_mesh_by_name_from_ipc(str(mesh_name or ""))

        def set_renderer_backend(backend: str, allow_fallback: object = None) -> None:
            renderer = self.settings_data.setdefault("renderer", {})
            selected = supported_renderer_backend(str(backend or ""))
            renderer["backend"] = selected.value
            if allow_fallback is not None:
                renderer["allow_fallback"] = bool(allow_fallback)
            settings = RendererSettings.from_settings(self.settings_data)
            self.viewport.set_renderer_settings(settings)
            self._log(f"IPC renderer backend: {renderer_backend_label(settings.backend)}", "info")

        def set_dummy_helpers(visible: object) -> None:
            enabled = bool(visible)
            self.viewport.set_dummy_helper_visibility(enabled)
            self._log(f"IPC dummy helpers: {'visible' if enabled else 'hidden'}", "info")

        def set_light_helpers(helpers: object, volumes: object = None) -> None:
            helper_visible = bool(helpers)
            volume_visible = helper_visible if volumes is None else bool(volumes)
            self.viewport.set_light_helper_visibility(helper_visible, volume_visible)
            self._log(
                f"IPC light helpers: {'visible' if helper_visible else 'hidden'}"
                f", volumes {'visible' if volume_visible else 'hidden'}",
                "info",
            )

        def select_helper(name: str = "") -> None:
            model = getattr(self.viewport, "model", None)
            try:
                nodes = list(model.all_nodes()) if model is not None and hasattr(model, "all_nodes") else []
            except Exception:
                nodes = []
            needle = str(name or "").strip().lower()
            selected = None
            for node in nodes:
                if not self.viewport._is_general_helper_node(node):
                    continue
                if bool(getattr(node, "_gr_hidden", False)):
                    continue
                if not needle or str(getattr(node, "name", "") or "").lower() == needle:
                    selected = node
                    break
            if selected is None:
                self._log(f"IPC select_helper: {name or '<first-helper>'} not found", "warning")
                return
            self.viewport.set_viewport_selection_mode("helpers")
            self.viewport.set_selected_node(selected, source="IPC select_helper")
            self._log(f"IPC select_helper: {getattr(selected, 'name', '<helper>')}", "success")

        def capture_viewport(path: str) -> None:
            target = Path(str(path or "")).expanduser()
            if not target.is_absolute():
                target = Path.cwd() / target
            target.parent.mkdir(parents=True, exist_ok=True)
            pixmap = self.viewport.canvas.grab()
            if pixmap.save(str(target)):
                self._log(f"IPC viewport capture: {target}", "info")
            else:
                self._log(f"IPC viewport capture failed: {target}", "warning")

        try:
            self._ipc_server = GhostRiggerIPCServer(
                {
                    "open_utc": open_blueprint_resource("utc"),
                    "open_utp": open_blueprint_resource("utp"),
                    "open_utd": open_blueprint_resource("utd"),
                    "open_mdl": open_mdl,
                    "load_model_by_resref": load_model_by_resref,
                    "refresh_viewport": refresh_viewport,
                    "show_panel": show_panel,
                    "select_module_mesh": select_module_mesh,
                    "set_renderer_backend": set_renderer_backend,
                    "set_dummy_helpers": set_dummy_helpers,
                    "set_light_helpers": set_light_helpers,
                    "select_helper": select_helper,
                    "capture_viewport": capture_viewport,
                }
            )
            self._ipc_server.start()
            self._log("IPC server starting on port 7001.", "info")
        except Exception as exc:
            self._ipc_server = None
            self._log(f"IPC server failed to start: {exc}", "warning")

    def _enable_theme_progress_toasts(self) -> None:
        self._suppress_theme_progress_toast = False

    def _place_on_primary_startup_screen(self) -> None:
        geometry = _primary_screen_available_geometry()
        if geometry is None:
            return
        size = self.size()
        if not size.isValid() or size.isEmpty():
            size = self.sizeHint()
        width = max(1, min(int(size.width()), int(geometry.width())))
        height = max(1, min(int(size.height()), int(geometry.height())))
        x = geometry.x() + max(0, (geometry.width() - width) // 2)
        y = geometry.y() + max(0, (geometry.height() - height) // 2)
        self.setGeometry(x, y, width, height)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._progress_toast is not None and self._progress_toast.isVisible():
            self._progress_toast._reposition()

    def _load_settings(self) -> dict:
        try:
            if self.settings_path.exists():
                return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Could not read settings.json: %s", exc)
        return {}






































































































































































































































































































































































def run(app_root: Optional[str] = None, startup_input: Optional[dict] = None) -> int:
    return run_qt_application(
        app_root,
        startup_input,
        window_cls=QtGhostRiggerMainWindow,
        splash_cls=QtStartupSplash,
        read_settings=_read_settings_file,
        collect_startup_diagnostics=_collect_prewindow_startup_diagnostics,
        build_prelaunch_library_input=_build_prelaunch_library_input,
    )
