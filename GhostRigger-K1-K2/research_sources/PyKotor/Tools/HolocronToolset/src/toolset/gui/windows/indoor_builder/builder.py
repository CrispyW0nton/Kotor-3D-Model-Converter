"""Indoor map builder: kit loading, room editing, and save/export."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, cast

import qtpy

from qtpy.QtCore import QEvent, QPoint, QTimer, Qt
from qtpy.QtGui import QColor, QIcon, QImage, QPixmap, QShortcut
from qtpy.QtWidgets import (
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger

if qtpy.QT5:
    from qtpy.QtGui import QCloseEvent
    from qtpy.QtWidgets import QUndoStack  # type: ignore[reportPrivateImportUsage]
elif qtpy.QT6:
    from qtpy.QtGui import QUndoStack  # type: ignore[assignment]  # pyright: ignore[reportPrivateImportUsage]

    try:
        from qtpy.QtGui import QCloseEvent
    except ImportError:
        # Fallback for Qt6 where QCloseEvent may be in QtCore
        pass  # type: ignore[assignment, attr-defined, no-redef]
else:
    raise ValueError(f"Invalid QT_API: '{qtpy.API_NAME}'")

from pykotor.common.indoorkit import Kit
from pykotor.common.indoormap import EmbeddedKit, IndoorMap, IndoorMapRoom
from pykotor.common.modulekit import ModuleKitManager
from pykotor.common.stream import BinaryWriter  # type: ignore[reportPrivateImportUsage]
from pykotor.tools import indoorkit as indoorkit_tools
from pykotor.tools.indoormap import extract_indoor_from_module_as_modulekit
from toolset.blender import BlenderEditorMode, check_blender_and_ask, get_blender_settings
from toolset.blender.integration import BlenderEditorMixin
from toolset.data.indoorkit.qt_preview import ensure_component_image
from toolset.data.installation import HTInstallation
from toolset.gui.common.editor_pipelines import (
    populate_module_root_combobox,
    set_preview_source_image,
    update_preview_image_size,
)
from toolset.gui.common.filters import NoScrollEventFilter
from toolset.gui.common.indoor_builder_ops import (
    add_connected_indoor_rooms_to_selection,
    apply_flip_selected_rooms,
    apply_merge_selected_rooms,
    apply_paste_rooms_from_clipboard,
    apply_rotate_selected_rooms,
    cancel_indoor_operations_and_clear_selection,
    cancel_indoor_operations_and_refresh,
    cancel_indoor_operations_core,
    center_indoor_camera_on_selected_rooms,
    clear_indoor_placement_mode,
    connect_indoor_option_signals,
    connect_indoor_paint_control_signals,
    connect_indoor_renderer_signals,
    copy_selected_rooms_to_clipboard,
    cut_indoor_selection,
    delete_selected_rooms_or_hook,
    duplicate_selected_rooms_or_hook,
    get_indoor_context_hits,
    handle_indoor_double_click_select_connected,
    handle_indoor_key_press_shortcuts,
    handle_indoor_primary_press,
    handle_indoor_scroll,
    populate_indoor_context_menu,
    push_rooms_moved_undo,
    push_rooms_rotated_undo,
    push_warp_moved_undo,
    reset_indoor_camera_view,
    run_if_any_indoor_rooms_selected,
    select_all_indoor_rooms,
    sync_indoor_options_ui_from_renderer,
    toggle_check_widget,
)
from toolset.gui.common.interaction.camera import calculate_zoom_strength, handle_standard_2d_camera_movement
from toolset.gui.common.localization import translate as tr, translate_format as trf
from toolset.gui.common.status_bar_utils import format_status_bar_keys_and_buttons
from toolset.gui.common.walkmesh_materials import get_walkmesh_material_colors
from toolset.gui.widgets.installation_toolbar import InstallationToolbar, StandaloneWindowMixin
from toolset.gui.dialogs.asyncloader import AsyncLoader
from toolset.gui.windows.help import HelpWindow
from toolset.gui.windows.indoor_builder.constants import (
    DEFAULT_CAMERA_POSITION_X,
    DEFAULT_CAMERA_POSITION_Y,
    DEFAULT_CAMERA_ROTATION,
    DEFAULT_CAMERA_ZOOM,
    DUPLICATE_OFFSET_X,
    DUPLICATE_OFFSET_Y,
    DUPLICATE_OFFSET_Z,
    POSITION_CHANGE_EPSILON,
    ROTATION_CHANGE_EPSILON,
    ZOOM_STEP_FACTOR,
    ZOOM_WHEEL_SENSITIVITY,
    DragMode,
)
from toolset.gui.windows.indoor_builder.undo_commands import (
    AddRoomCommand,
    PaintWalkmeshCommand,
    ResetWalkmeshCommand,
)
from utility.common.geometry import SurfaceMaterial, Vector2, Vector3
from utility.system.os_helper import is_frozen

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import QCloseEvent, QObject
    from qtpy.QtGui import QKeyEvent, QKeySequence
    from qtpy.QtWidgets import (
        QDockWidget,
        QLayout,
        QProgressDialog,
    )

    from pykotor.common.indoorkit import KitComponent, KitComponentHook
    from pykotor.common.indoormap import MissingRoomInfo
    from pykotor.common.modulekit import ModuleKit
    from toolset.blender import ConnectionState
    from toolset.gui.common.indoor_builder_ops import RoomClipboardData


def get_kits_path() -> Path:
    if is_frozen():
        kits_path = Path("./kits").absolute()
    else:
        this_file_path = Path(__file__).absolute()
        kits_path = this_file_path.parents[2].joinpath("kits").absolute()
    return kits_path


@dataclass
class SnapResult:
    """Result of a snap operation."""

    position: Vector3
    snapped: bool = False
    hook_from: KitComponentHook | None = None
    hook_to: KitComponentHook | None = None
    target_room: IndoorMapRoom | None = None


# =============================================================================
# Main Window
# =============================================================================


class IndoorMapBuilder(QMainWindow, BlenderEditorMixin, StandaloneWindowMixin):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
        use_blender: bool = False,
    ):
        super().__init__(parent)

        # Initialize Blender integration
        self._init_blender_integration(BlenderEditorMode.INDOOR_BUILDER)
        self._use_blender_mode: bool = use_blender
        self._blender_choice_made: bool = False
        self._view_stack: QStackedWidget | None = None
        self._blender_placeholder: QWidget | None = None
        self._blender_log_buffer: deque[str] = deque(maxlen=500)
        self._blender_log_path: Path | None = None
        self._blender_log_handle: TextIO | None = None
        self._blender_progress_dialog: QProgressDialog | None = None
        self._blender_log_view: QPlainTextEdit | None = None
        self._blender_connected_once: bool = False
        self._room_id_lookup: dict[int, IndoorMapRoom] = {}
        self._transform_sync_in_progress: bool = False
        self._property_sync_in_progress: bool = False

        self._installation: HTInstallation | None = installation
        self._kits: list[Kit] = []
        self._map: IndoorMap = IndoorMap()
        # Synthetic components (e.g. merged rooms) are stored in an embedded kit so they
        # can be serialized into `.indoor` and restored on load.
        self._embedded_kit: EmbeddedKit = EmbeddedKit()
        self._filepath: os.PathLike | str = ""
        self._preview_source_image: QImage | None = None

        # Module kit management (lazy loading)
        # ModuleKitManager handles converting game modules to kit-like components
        if installation is not None:
            self._module_kit_manager: ModuleKitManager = ModuleKitManager(installation)
        else:
            self._module_kit_manager = None  # type: ignore[assignment]
        self._current_module_kit: ModuleKit | None = None

        # Undo/Redo stack
        self._undo_stack: QUndoStack = QUndoStack(self)

        # Clipboard for copy/paste
        self._clipboard: list[RoomClipboardData] = []

        from toolset.uic.qtpy.windows.indoor_builder import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Add a missing "Open .mod" action at runtime (UI code is generated; do not edit it).
        self._action_open_mod: QAction = QAction(tr("Open .mod..."), self)
        self._action_open_mod.setShortcut("Ctrl+Shift+O")
        self._action_open_mod.setStatusTip(tr("Open a built module (.mod) and load its embedded indoor map"))
        # Put it right after "Open" in File menu and toolbar.
        try:
            self.ui.menuFile.insertAction(self.ui.actionSave, self._action_open_mod)
        except Exception:
            pass

        self._setup_settings_toolbar()

        # New UI uses dock widgets - connect to dock widget signals for preview updates
        left_dock: QDockWidget | None = self.ui.leftDockWidget
        if left_dock is not None:
            # Update preview when dock widget is resized or visibility changes
            left_dock.visibilityChanged.connect(self._on_dock_visibility_changed)
            # Use event filter to update preview after geometry changes
            left_dock.installEventFilter(self)
        right_dock: QDockWidget | None = self.ui.rightDockWidget
        if right_dock is not None:
            right_dock.visibilityChanged.connect(self._on_dock_visibility_changed)

        self._setup_status_bar()
        # Walkmesh painter state
        self._painting_walkmesh: bool = False
        self._colorize_materials: bool = True
        self._material_colors: dict[SurfaceMaterial, QColor] = {}
        self._paint_stroke_active: bool = False
        self._paint_stroke_originals: dict[tuple[IndoorMapRoom, int], SurfaceMaterial] = {}
        self._paint_stroke_new: dict[tuple[IndoorMapRoom, int], SurfaceMaterial] = {}

        self._setup_signals()
        self._setup_walkmesh_painter()
        self._setup_undo_redo()
        self._setup_kits()
        self._setup_modules()
        self._refresh_window_title()

        self.ui.mapRenderer.set_map(self._map)
        self.ui.mapRenderer.set_undo_stack(self._undo_stack)
        self.ui.mapRenderer.set_status_callback(self._refresh_status_bar)

        # Initialize Options UI to match renderer state
        self._initialize_options_ui()

        # Sync settings toolbar from current map
        self._update_settings_ui()

        # Setup Blender integration UI (deferred to avoid layout issues)
        QTimer.singleShot(0, self._install_view_stack)

        # Check for Blender on first map load
        if not self._blender_choice_made and self._installation:
            QTimer.singleShot(100, self._check_blender_on_load)

        # Setup NoScrollEventFilter
        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        self._installation = installation
        self._module_kit_manager = ModuleKitManager(installation) if installation is not None else None
        try:
            self._setup_settings_toolbar()
            self._setup_modules()
            self._refresh_window_title()
        except Exception:
            self.log.exception("Failed to refresh after installation switch")

    def enable_standalone_mode(self) -> None:
        """Override: place installation toolbar in left dock above Modules instead of above the map."""
        if self._installation_toolbar is not None:
            return
        container = getattr(self.ui, "installationToolbarContainer", None)
        if container is None:
            super().enable_standalone_mode()
            return
        self._standalone_folder_paths = {}
        self._installation_toolbar = InstallationToolbar(
            container,
            folder_path_specs=list(self.STANDALONE_FOLDER_PATHS),
            requires_installation=self.STANDALONE_REQUIRES_INSTALLATION,
        )
        self._installation_toolbar.installation_changed.connect(self._handle_installation_changed)
        self._installation_toolbar.folder_paths_changed.connect(self._handle_folder_paths_changed)
        layout = container.layout()
        if layout is not None:
            layout.addWidget(self._installation_toolbar)

    def _get_semantic_colors(self) -> dict[str, str]:
        """Get semantic colors from the application palette.

        Returns:
            Dictionary with keys: 'info', 'ok', 'warn', 'error', 'muted', 'accent1', 'accent2', 'accent3'
        """
        from qtpy.QtGui import QPalette

        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            # Use default palette for fallback
            palette = QPalette()
        else:
            palette = app.palette()

        # Get base palette colors
        link_color = palette.color(QPalette.ColorRole.Link)
        mid_color = palette.color(QPalette.ColorRole.Mid)
        shadow_color = palette.color(QPalette.ColorRole.Shadow)

        # Create semantic colors from palette
        # Info: Use link color (usually blue)
        info_color = link_color

        # OK/Success: Create a green-ish color from highlight or link
        ok_color = QColor(link_color)
        if ok_color.lightness() < 128:  # Dark theme
            ok_color = QColor(0, min(255, ok_color.green() + 100), 0)
        else:  # Light theme
            ok_color = QColor(0, min(200, ok_color.green() + 50), 0)

        # Warning: Use mid color with adjustment
        warn_color = QColor(mid_color)
        if warn_color.lightness() < 128:  # Dark theme
            warn_color = warn_color.lighter(150)
        else:  # Light theme
            warn_color = warn_color.darker(120)

        # Error: Use shadow or create red variant
        error_color = QColor(shadow_color)
        if error_color.lightness() < 128:  # Dark theme
            error_color = QColor(min(255, error_color.red() + 100), 0, 0)
        else:  # Light theme
            error_color = QColor(min(200, error_color.red() + 50), 0, 0)

        # Muted: Use mid color
        muted_color = mid_color

        # Accent colors for UI elements
        accent1 = link_color  # Blue for coordinates/info
        accent2 = ok_color  # Green for success
        accent3 = QColor(link_color)  # Purple variant for keys
        if accent3.lightness() < 128:
            accent3 = QColor(min(255, accent3.red() + 50), min(255, accent3.green() + 20), min(255, accent3.blue() + 100))
        else:
            accent3 = QColor(min(200, accent3.red() + 30), min(200, accent3.green() + 10), min(200, accent3.blue() + 50))

        return {
            "info": info_color.name(),
            "ok": ok_color.name(),
            "warn": warn_color.name(),
            "error": error_color.name(),
            "muted": muted_color.name(),
            "accent1": accent1.name(),
            "accent2": accent2.name(),
            "accent3": accent3.name(),
        }

    def _setup_signals(self):
        """Connect signals to slots."""
        # Kit/component selection
        self.ui.kitSelect.currentIndexChanged.connect(self.on_kit_selected)
        self.ui.componentList.currentItemChanged.connect(self.onComponentSelected)

        # Module/component selection
        self.ui.moduleSelect.currentIndexChanged.connect(self.on_module_selected)
        self.ui.moduleComponentList.currentItemChanged.connect(self.on_module_component_selected)

        # File menu
        self.ui.actionNew.triggered.connect(self.new)
        self.ui.actionOpen.triggered.connect(self.open)
        self._action_open_mod.triggered.connect(self.open_mod)
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSaveAs.triggered.connect(self.save_as)
        self.ui.actionBuild.triggered.connect(self.build_map)
        self.ui.actionDownloadKits.triggered.connect(self.open_kit_downloader)
        # QAction.triggered emits a bool; QWidget.close takes no args.
        self.ui.actionExit.triggered.connect(lambda *_: self.close())

        # Edit menu
        self.ui.actionDeleteSelected.triggered.connect(self.delete_selected)
        self.ui.actionDuplicate.triggered.connect(self.duplicate_selected)
        self.ui.actionCut.triggered.connect(self.cut_selected)
        self.ui.actionCopy.triggered.connect(self.copy_selected)
        self.ui.actionPaste.triggered.connect(self.paste)
        self.ui.actionSelectAll.triggered.connect(self.select_all)
        self.ui.actionDeselectAll.triggered.connect(self.deselect_all)

        # View menu
        self.ui.actionZoomIn.triggered.connect(lambda: self.ui.mapRenderer.zoom_in_camera(ZOOM_STEP_FACTOR))
        self.ui.actionZoomOut.triggered.connect(lambda: self.ui.mapRenderer.zoom_in_camera(1.0 / ZOOM_STEP_FACTOR))
        self.ui.actionResetView.triggered.connect(self.reset_view)
        self.ui.actionCenterOnSelection.triggered.connect(self.center_on_selection)

        # Help menu
        self.ui.actionInstructions.triggered.connect(self.show_help_window)

        connect_indoor_renderer_signals(
            self.ui.mapRenderer,
            on_context_menu=self.on_context_menu,
            on_mouse_moved=self.on_mouse_moved,
            on_mouse_pressed=self.on_mouse_pressed,
            on_mouse_released=self.on_mouse_released,
            on_mouse_scrolled=self.on_mouse_scrolled,
            on_mouse_double_clicked=self.onMouseDoubleClicked,
            on_rooms_moved=self.on_rooms_moved,
            on_rooms_rotated=self.on_rooms_rotated,
            on_warp_moved=self.on_warp_moved,
            on_marquee_select=self.on_marquee_select,
        )

        # Ensure renderer can receive keyboard focus for accessibility
        self.ui.mapRenderer.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        connect_indoor_option_signals(
            snap_to_grid_check=self.ui.snapToGridCheck,
            snap_to_hooks_check=self.ui.snapToHooksCheck,
            show_grid_check=self.ui.showGridCheck,
            show_hooks_check=self.ui.showHooksCheck,
            grid_size_spin=self.ui.gridSizeSpin,
            rotation_snap_spin=self.ui.rotSnapSpin,
            set_snap_to_grid=self.ui.mapRenderer.set_snap_to_grid,
            set_snap_to_hooks=self.ui.mapRenderer.set_snap_to_hooks,
            set_show_grid=self.ui.mapRenderer.set_show_grid,
            set_hide_magnets=self.ui.mapRenderer.set_hide_magnets,
            set_grid_size=self.ui.mapRenderer.set_grid_size,
            set_rotation_snap=self.ui.mapRenderer.set_rotation_snap,
        )
        self.ui.showRoomLabelsCheck.toggled.connect(self.ui.mapRenderer.set_show_room_labels)

        # Settings toolbar: sync map -> UI when any setting changes
        self.ui.nameEdit.sig_editing_finished.connect(self._on_settings_changed)
        self.ui.colorEdit.sig_color_changed.connect(self._on_settings_changed)
        self.ui.warpCodeEdit.textChanged.connect(self._on_settings_changed)
        self.ui.skyboxSelect.currentIndexChanged.connect(self._on_settings_changed)
        self.ui.gameTypeSelect.currentIndexChanged.connect(self._on_settings_changed)

    def _setup_settings_toolbar(self):
        """Add settings widget to toolbar and populate skybox/game type. Set installation on nameEdit."""
        self.ui.toolBar.addWidget(self.ui.settingsToolbarWidget)
        if isinstance(self._installation, HTInstallation):
            self.ui.nameEdit.set_installation(self._installation)
        self.ui.skyboxSelect.clear()
        self.ui.skyboxSelect.addItem(tr("[None]"), "")
        for kit in self._kits:
            for skybox in kit.skyboxes:
                self.ui.skyboxSelect.addItem(skybox, skybox)
        self.ui.gameTypeSelect.clear()
        self.ui.gameTypeSelect.addItem(tr("Use Installation Default"), None)
        self.ui.gameTypeSelect.addItem("Knights of the Old Republic (K1)", False)
        self.ui.gameTypeSelect.addItem("The Sith Lords (TSL/K2)", True)

    def _update_settings_ui(self):
        """Sync toolbar widgets from current _map state."""
        self.ui.nameEdit.set_locstring(self._map.name)
        self.ui.colorEdit.blockSignals(True)
        self.ui.colorEdit.set_color(self._map.lighting)
        self.ui.colorEdit.blockSignals(False)
        self.ui.warpCodeEdit.blockSignals(True)
        self.ui.warpCodeEdit.setText(self._map.module_id)
        self.ui.warpCodeEdit.blockSignals(False)
        self.ui.skyboxSelect.blockSignals(True)
        if self._map.skybox:
            idx = self.ui.skyboxSelect.findText(self._map.skybox)
            if idx == -1:
                idx = self.ui.skyboxSelect.findData(self._map.skybox)
            self.ui.skyboxSelect.setCurrentIndex(idx if idx != -1 else 0)
        else:
            self.ui.skyboxSelect.setCurrentIndex(0)
        self.ui.skyboxSelect.blockSignals(False)
        self.ui.gameTypeSelect.blockSignals(True)
        if self._map.target_game_type is None:
            self.ui.gameTypeSelect.setCurrentIndex(0)
        elif self._map.target_game_type:
            self.ui.gameTypeSelect.setCurrentIndex(2)
        else:
            self.ui.gameTypeSelect.setCurrentIndex(1)
        self.ui.gameTypeSelect.blockSignals(False)

    def _on_settings_changed(self):
        """Read toolbar settings into _map and mark document modified."""
        self._map.name = self.ui.nameEdit.locstring()
        self._map.lighting = self.ui.colorEdit.color()
        self._map.module_id = self.ui.warpCodeEdit.text()
        self._map.skybox = self.ui.skyboxSelect.currentData()
        self._map.target_game_type = self.ui.gameTypeSelect.currentData()
        from qtpy.QtWidgets import QUndoCommand  # pyright: ignore[reportPrivateImportUsage]

        class SettingsChangedCommand(QUndoCommand):
            def __init__(self):
                super().__init__("Settings Changed")

            def undo(self): ...
            def redo(self): ...

        if not self._undo_stack.canUndo():
            self._undo_stack.push(SettingsChangedCommand())
        self._refresh_window_title()

    def _setup_walkmesh_painter(self):
        """Initialize walkmesh painting UI and palette."""
        self._material_colors = get_walkmesh_material_colors()

        self._populate_material_list()
        self._colorize_materials = True
        self.ui.colorizeMaterialsCheck.setChecked(True)
        self.ui.enablePaintCheck.setChecked(False)

        self.ui.mapRenderer.set_material_colors(self._material_colors)
        self.ui.mapRenderer.set_colorize_materials(self._colorize_materials)

        self.ui.materialList.currentItemChanged.connect(lambda _old, _new=None: self._refresh_status_bar())
        connect_indoor_paint_control_signals(
            enable_paint_check=self.ui.enablePaintCheck,
            colorize_check=self.ui.colorizeMaterialsCheck,
            reset_button=self.ui.resetPaintButton,
            on_toggle_paint=self._toggle_paint_mode,
            on_toggle_colorize=self._toggle_colorize_materials,
            on_reset_paint=self._reset_selected_walkmesh,
        )

        # Shortcut to quickly toggle paint mode
        QShortcut(Qt.Key.Key_P, self).activated.connect(lambda: self.ui.enablePaintCheck.toggle())

    def _setup_undo_redo(self):
        """Setup undo/redo actions."""
        self.ui.actionUndo.triggered.connect(self._undo_stack.undo)
        self.ui.actionRedo.triggered.connect(self._undo_stack.redo)

        # Update action enabled states
        self._undo_stack.canUndoChanged.connect(self.ui.actionUndo.setEnabled)
        self._undo_stack.canRedoChanged.connect(self.ui.actionRedo.setEnabled)
        self._undo_stack.cleanChanged.connect(self._refresh_window_title)  # Update title when clean state changes

        # Update action text with command names
        self._undo_stack.undoTextChanged.connect(lambda text: self.ui.actionUndo.setText(f"{tr('Undo')} {text}" if text else tr("Undo")))
        self._undo_stack.redoTextChanged.connect(lambda text: self.ui.actionRedo.setText(f"{tr('Redo')} {text}" if text else tr("Redo")))

        # Initial state
        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)

    def _populate_material_list(self):
        """Populate the material list with colored swatches."""
        self.ui.materialList.clear()
        for material, color in self._material_colors.items():
            pix = QPixmap(16, 16)
            pix.fill(color)
            item = QListWidgetItem(QIcon(pix), material.name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, material)
            self.ui.materialList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]
        if self.ui.materialList.count():
            self.ui.materialList.setCurrentRow(0)

    def _current_material(self) -> SurfaceMaterial | None:
        if self.ui.materialList.currentItem():
            material = self.ui.materialList.currentItem().data(Qt.ItemDataRole.UserRole)  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
            if isinstance(material, SurfaceMaterial):
                return material
        return next(iter(self._material_colors.keys()), None)

    def _toggle_paint_mode(
        self,
        enabled: bool,
    ):
        self._painting_walkmesh = enabled
        self._paint_stroke_active = False
        self._paint_stroke_originals.clear()
        self._paint_stroke_new.clear()
        self._refresh_status_bar()

    def _toggle_colorize_materials(
        self,
        enabled: bool,
    ):
        self._colorize_materials = enabled
        self.ui.mapRenderer.set_colorize_materials(enabled)
        self.ui.mapRenderer.mark_dirty()
        self._refresh_status_bar()

    def _reset_selected_walkmesh(self):
        rooms = [room for room in self.ui.mapRenderer.selected_rooms() if room.walkmesh_override is not None]
        if not rooms:
            return
        cmd = ResetWalkmeshCommand(rooms, self._invalidate_rooms)
        self._undo_stack.push(cmd)
        self._refresh_window_title()

    def _invalidate_rooms(
        self,
        rooms: list[IndoorMapRoom],
    ):
        self.ui.mapRenderer.invalidate_rooms(rooms)
        self._refresh_status_bar()

    def _setup_kits(self):
        self.ui.kitSelect.clear()
        self._kits, missing_files = indoorkit_tools.load_kits_with_missing_files(get_kits_path())

        # Kits are deprecated and optional - modules provide the same functionality
        # No need to show a dialog when kits are missing since modules can be used instead
        # if len(self._kits) == 0:
        #     ... (removed - kits are deprecated, modules handle this functionality)

        for kit in self._kits:
            self.ui.kitSelect.addItem(kit.name, kit)

    def _show_no_kits_dialog(self):
        """Show dialog asking if user wants to open kit downloader.

        This is called asynchronously via QTimer.singleShot to avoid blocking initialization.
        Headless mode is already checked before this method is scheduled, so it will only
        be called in GUI mode where exec() is safe.
        """
        from toolset.gui.common.localization import translate as tr

        # Show dialog in GUI mode using exec()
        # Headless check happens before this method is scheduled, so this is safe
        no_kit_prompt = QMessageBox(self)
        no_kit_prompt.setIcon(QMessageBox.Icon.Warning)
        no_kit_prompt.setWindowTitle(tr("No Kits Available"))
        no_kit_prompt.setText(tr("No kits were detected, would you like to open the Kit downloader?"))
        no_kit_prompt.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        no_kit_prompt.setDefaultButton(QMessageBox.StandardButton.No)

        # Use exec() for proper modal behavior in GUI mode
        result = no_kit_prompt.exec()
        if result == QMessageBox.StandardButton.Yes or no_kit_prompt.clickedButton() == QMessageBox.StandardButton.Yes:
            self.open_kit_downloader()

    def _setup_modules(self):
        """Set up the module selection combobox with available modules from the installation.

        Uses ModuleKitManager to get module roots and display names.
        Modules are loaded lazily when selected.
        """
        self.ui.moduleSelect.clear()
        self.ui.moduleComponentList.clear()

        if self._installation is None or self._module_kit_manager is None:
            # Disable modules UI if no installation is available
            self.ui.modulesGroupBox.setEnabled(False)
            return
        populate_module_root_combobox(self.ui.moduleSelect, self._module_kit_manager)

    def _set_preview_image(
        self,
        image: QImage | None,
    ):
        """Render a component preview into the unified preview pane."""
        self._preview_source_image = set_preview_source_image(self.ui.previewImage, image)

    def _update_preview_image_size(self):
        """Update preview image to match current label size."""
        update_preview_image_size(self.ui.previewImage, self._preview_source_image)

    def _on_splitter_moved(
        self,
        pos: int,  # pyright: ignore[reportUnusedParameter]
        index: int,  # pyright: ignore[reportUnusedParameter]
    ):
        """Handle splitter movement - update preview image if it exists."""
        # Refresh preview image to match new size if one is set
        if self._preview_source_image is not None:
            # Use QTimer to update after layout has adjusted
            QTimer.singleShot(10, self._update_preview_image_size)

    def _on_dock_visibility_changed(
        self,
        visible: bool,
    ):
        """Handle dock widget visibility changes - update preview image if it exists."""
        if visible and self._preview_source_image is not None:
            # Use QTimer to update after layout has adjusted
            QTimer.singleShot(10, self._update_preview_image_size)

    def eventFilter(
        self,
        obj: QObject,
        event: QEvent,
    ) -> bool:
        """Event filter for dock widgets to detect resize events."""
        if event.type() == QEvent.Type.Resize:
            if self._preview_source_image is not None:
                # Use QTimer to update after layout has adjusted
                QTimer.singleShot(10, self._update_preview_image_size)
        return super().eventFilter(obj, event)

    def _update_preview_from_selection(self):
        """Update preview image based on selected rooms.

        Shows the most recently selected room's component image.
        Only updates if no component is being dragged (cursor_component is None).
        """
        renderer = self.ui.mapRenderer
        # Don't update preview if we're dragging a component (placement mode)
        if renderer.cursor_component is not None:
            return

        # Get selected rooms - most recent is last in the list
        sel_rooms = renderer.selected_rooms()
        if sel_rooms:
            # Show the most recently selected room (last in list)
            most_recent_room = sel_rooms[-1]
            if most_recent_room.component.image is not None:
                assert isinstance(most_recent_room.component.image, QImage)
                # self._set_preview_image(QPixmap.fromImage(most_recent_room.component.image))
                self._set_preview_image(most_recent_room.component.image)
            else:
                self._set_preview_image(None)
        else:
            # No rooms selected, clear preview (unless dragging)
            self._set_preview_image(None)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _setup_status_bar(self):
        """Create a richer status bar mirroring the module designer style."""
        self._emoji_style = (
            "font-size:12pt; font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',"
            "'EmojiOne','Twemoji Mozilla','Segoe UI Symbol',sans-serif; vertical-align:middle;"
        )

        bar = QStatusBar(self)
        bar.setContentsMargins(4, 0, 4, 0)
        self.setStatusBar(bar)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(8)

        self._mouse_label = QLabel(tr("Coords:"))
        self._hover_label = QLabel(tr("Hover:"))
        self._selection_label = QLabel(tr("Selection:"))
        self._keys_label = QLabel("Keys/Buttons:")
        for lbl in (self._mouse_label, self._hover_label, self._selection_label, self._keys_label):
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        first_row.addWidget(self._mouse_label, 1)
        first_row.addWidget(self._hover_label, 1)
        first_row.addWidget(self._selection_label, 1)
        first_row.addWidget(self._keys_label, 1)

        self._mode_label = QLabel()
        self._mode_label.setTextFormat(Qt.TextFormat.RichText)
        self._mode_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(first_row)
        layout.addWidget(self._mode_label)

        bar.addWidget(container, 1)

    def on_module_selected(
        self,
        index: int = -1,  # pyright: ignore[reportUnusedParameter]
    ):
        """Handle module selection from the combobox.

        Loads module components lazily when a module is selected in the combobox.
        Uses ModuleKitManager to convert module resources into kit components.
        """
        self.ui.moduleComponentList.clear()
        self._set_preview_image(None)

        module_root: str | None = self.ui.moduleSelect.currentData()
        if not module_root or not self._installation:
            return

        try:
            # Use the ModuleKitManager to get a ModuleKit for this module
            module_kit = self._module_kit_manager.get_module_kit(module_root)

            # Ensure the kit is loaded (lazy loading)
            if not module_kit.ensure_loaded():
                from loggerplus import RobustLogger

                RobustLogger().warning(f"No components found for module '{module_root}'")
                return

            # Populate the list with components from the module kit
            for component in module_kit.components:
                # ModuleKit components are headless; Toolset UI needs a QImage preview.
                ensure_component_image(component)
                item = QListWidgetItem(component.name)
                item.setData(Qt.ItemDataRole.UserRole, component)
                self.ui.moduleComponentList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

        except Exception:  # noqa: BLE001
            from loggerplus import RobustLogger  # type: ignore[import-untyped, note]  # pyright: ignore[reportMissingTypeStubs]

            RobustLogger().exception(f"Failed to load module '{module_root}'")

    def on_module_component_selected(
        self,
        item: QListWidgetItem | None = None,
        previous: QListWidgetItem | None = None,  # pyright: ignore[reportUnusedParameter]
    ):
        """Handle module component selection from the list."""
        if item is None:
            self._set_preview_image(None)
            self.ui.mapRenderer.set_cursor_component(None)
            return

        component: KitComponent | None = item.data(Qt.ItemDataRole.UserRole)
        if component is None:
            return

        # Toggle: if same component is already selected, deselect it
        if self.ui.mapRenderer.cursor_component is component:
            # Clicking the same component again = "pick it up" (deselect)
            self.ui.moduleComponentList.clearSelection()
            self.ui.moduleComponentList.setCurrentItem(None)
            self._set_preview_image(None)
            self.ui.mapRenderer.set_cursor_component(None)
            return

        # Display component image in the preview
        self._set_preview_image(ensure_component_image(component))

        # Set as current cursor component for placement
        self.ui.mapRenderer.set_cursor_component(component)

    def _refresh_window_title(self):
        from toolset.gui.common.localization import translate as tr, translate_format as trf

        if not self._installation:
            title = tr("No installation - Indoor Map Builder")
        elif not self._filepath:
            title = trf("{name} - Indoor Map Builder", name=self._installation.name)
        else:
            title = trf("{path} - {name} - Indoor Map Builder", path=self._filepath, name=self._installation.name)

        # Add asterisk if there are unsaved changes (use isClean() instead of canUndo())
        # isClean() tracks whether the document matches the saved state
        if not self._undo_stack.isClean():
            title = "* " + title
        self.setWindowTitle(title)

    # =============================================================================
    # Blender Integration
    # =============================================================================

    def _install_view_stack(self):
        """Wrap the map renderer with a stacked widget so we can swap in Blender instructions."""
        if self._view_stack is not None:
            return

        # Find the parent layout that contains the map renderer
        # This will depend on the UI structure - adjust as needed
        parent_widget = cast("QWidget | None", self.ui.mapRenderer.parent())
        parent_layout: QLayout | None = None if parent_widget is None else parent_widget.layout()
        if not isinstance(parent_layout, QVBoxLayout):
            return  # Can't install view stack without a parent layout

        self._view_stack = QStackedWidget(self)
        parent_layout.removeWidget(self.ui.mapRenderer)
        self._view_stack.addWidget(self.ui.mapRenderer)
        self._blender_placeholder = self._create_blender_placeholder()
        self._view_stack.addWidget(self._blender_placeholder)
        parent_layout.addWidget(self._view_stack)

    def _create_blender_placeholder(self) -> QWidget:
        """Create placeholder pane shown while Blender drives the rendering."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        headline = QLabel(
            "<b>Blender mode is active.</b><br>"
            "The Holocron Toolset will defer all 3D rendering and editing to Blender. "
            "Use the Blender window to move rooms, edit textures/models, and "
            "manipulate the indoor map. This panel streams Blender's console output for diagnostics."
        )
        headline.setWordWrap(True)
        layout.addWidget(headline)

        self._blender_log_view = QPlainTextEdit(container)
        self._blender_log_view.setReadOnly(True)
        self._blender_log_view.setPlaceholderText(tr("Blender log output will appear here once the IPC bridge starts…"))
        layout.addWidget(self._blender_log_view, 1)

        return container

    def _show_blender_workspace(self):
        """Switch to Blender placeholder view."""
        if self._view_stack is not None and self._blender_placeholder is not None:
            self._view_stack.setCurrentWidget(self._blender_placeholder)

    def _show_internal_workspace(self):
        """Switch to internal renderer view."""
        if self._view_stack is not None:
            self._view_stack.setCurrentWidget(self.ui.mapRenderer)

    def _check_blender_on_load(self):
        """Check for Blender when a map is loaded."""
        if self._blender_choice_made or not self._installation:
            return

        self._blender_choice_made = True
        blender_settings = get_blender_settings()

        if blender_settings.remember_choice:
            self._use_blender_mode = blender_settings.prefer_blender
        else:
            blender_info = blender_settings.get_blender_info()
            if blender_info.is_valid:
                use_blender, _ = check_blender_and_ask(self, "Indoor Map Builder")
                if _ is not None:
                    self._use_blender_mode = use_blender

    def _refresh_room_id_lookup(self):
        """Cache Python object ids for fast lookup when Blender sends events."""
        self._room_id_lookup.clear()
        for room in self._map.rooms:
            self._room_id_lookup[id(room)] = room

    def _on_blender_material_changed(
        self,
        payload: dict[str, Any],
    ):
        """Handle material/texture changes from Blender for real-time updates."""

        def _apply():
            object_name = payload.get("object_name", "")
            material_data = payload.get("material", {})
            model_name = payload.get("model_name")

            if not model_name:
                return

            from loggerplus import RobustLogger

            RobustLogger().debug(f"[Blender][Indoor Map Builder] Material changed for {object_name} (model: {model_name})")

            # Find the room that uses this model
            room: IndoorMapRoom | None = None
            for r in self._map.rooms:
                if r.component.mdl == model_name or (r.component.name == model_name):
                    room = r
                    break

            if room is None:
                return

            # If textures were changed, we need to reload the model
            if "diffuse_texture" in material_data or "lightmap_texture" in material_data:
                # Request MDL export from Blender
                if self.is_blender_mode() and self._blender_controller is not None:
                    import tempfile

                    temp_mdl = tempfile.NamedTemporaryFile(suffix=".mdl", delete=False)
                    temp_mdl.close()

                    from toolset.blender.ipc_client import get_ipc_client

                    client = get_ipc_client()
                    if client and client.is_connected:
                        result = client.send_command(
                            "export_mdl",
                            {
                                "path": temp_mdl.name,
                                "object": object_name,
                            },
                        )
                        if result.success:
                            from loggerplus import RobustLogger

                            RobustLogger().info(f"[Blender][Indoor Map Builder] Exported updated MDL to {temp_mdl.name}")
                            # Reload the model in the renderer
                            self.ui.mapRenderer.invalidate_rooms([room])
                            self.ui.mapRenderer.update()

        QTimer.singleShot(0, _apply)

    def _on_blender_transform_changed(
        self,
        instance_id: int,
        position: dict[str, float] | None,
        rotation: dict[str, float] | None,
    ):
        """Handle room transform changes from Blender."""

        def _apply():
            prev = self._transform_sync_in_progress
            self._transform_sync_in_progress = True
            try:
                room = self._room_id_lookup.get(instance_id)
                if room is None:
                    return

                if position:
                    new_position = Vector3(
                        position.get("x", room.position.x),
                        position.get("y", room.position.y),
                        position.get("z", room.position.z),
                    )
                    push_rooms_moved_undo(
                        self._map,
                        [room],
                        [Vector3(*room.position)],
                        [new_position],
                        self._undo_stack,
                        self._invalidate_rooms,
                        position_change_epsilon=0.0,
                    )

                if rotation and "euler" in rotation:
                    euler = rotation["euler"]
                    if isinstance(euler, dict):
                        new_rotation = euler.get("z", room.rotation)
                    else:
                        new_rotation = room.rotation
                    push_rooms_rotated_undo(
                        self._map,
                        [room],
                        [room.rotation],
                        [new_rotation],
                        self._undo_stack,
                        self._invalidate_rooms,
                        rotation_change_epsilon=1e-4,
                    )
            finally:
                self._transform_sync_in_progress = prev

        QTimer.singleShot(0, _apply)

    def _on_blender_selection_changed(
        self,
        instance_ids: list[int],
    ):
        """Handle selection changes from Blender."""

        def _apply():
            rooms: list[IndoorMapRoom] = [room for room_id in instance_ids if (room := self._room_id_lookup.get(room_id)) is not None]
            if rooms:
                self.ui.mapRenderer.select_rooms(rooms)

        QTimer.singleShot(0, _apply)

    def _on_blender_state_change(
        self,
        state: ConnectionState,
    ):
        """Handle Blender connection state changes."""
        super()._on_blender_state_change(state)
        QTimer.singleShot(0, lambda: self._handle_blender_state_change(state))

    def _handle_blender_state_change(
        self,
        state: ConnectionState,
    ):
        """Handle Blender state change on UI thread."""
        if state.value == "connected":  # ConnectionState.CONNECTED
            self._blender_connected_once = True
            if self._blender_progress_dialog:
                self._blender_progress_dialog.hide()
        elif state.value == "error":
            if self._blender_progress_dialog:
                self._blender_progress_dialog.hide()
            QMessageBox.warning(
                self,
                tr("Blender Connection Error"),
                tr("Failed to connect to Blender. Please check that Blender is running and kotorblender is installed."),
            )

    def _on_blender_module_loaded(self):
        """Called when indoor map is loaded in Blender."""
        super()._on_blender_module_loaded()
        QTimer.singleShot(0, lambda: self._blender_progress_dialog.hide() if self._blender_progress_dialog else None)
        self._refresh_room_id_lookup()

    def _on_blender_mode_stopped(self):
        """Called when Blender mode is stopped."""
        super()._on_blender_mode_stopped()
        QTimer.singleShot(0, self._show_internal_workspace)

    def _on_blender_output(self, line: str):
        """Handle Blender stdout/stderr output."""
        super()._on_blender_output(line)
        if self._blender_log_view:
            self._blender_log_view.appendPlainText(line)

    def sync_room_to_blender(
        self,
        room: IndoorMapRoom,
    ):
        """Sync a room's position/rotation to Blender."""
        if not self.is_blender_mode() or self._blender_controller is None:
            return

        # For indoor maps, we need to send room data differently
        # Since Blender expects LYT rooms, we'll need to convert
        # This is a simplified version - full implementation would need
        # to handle the conversion properly
        room_id = id(room)
        if self._blender_controller.session:
            # Map room to Blender object name
            object_name = f"Room_{room_id}"
            # Update position
            self._blender_controller.update_room_position(
                object_name,
                room.position.x,
                room.position.y,
                room.position.z,
            )

    def _initialize_options_ui(self):
        """Initialize Options UI to match renderer's initial state."""
        sync_indoor_options_ui_from_renderer(
            self.ui.mapRenderer,
            snap_to_grid_check=self.ui.snapToGridCheck,
            snap_to_hooks_check=self.ui.snapToHooksCheck,
            show_grid_check=self.ui.showGridCheck,
            show_hooks_check=self.ui.showHooksCheck,
            grid_size_spin=self.ui.gridSizeSpin,
            rotation_snap_spin=self.ui.rotSnapSpin,
        )
        self.ui.showRoomLabelsCheck.setChecked(self.ui.mapRenderer.show_room_labels)

    def _refresh_status_bar(
        self,
        screen: QPoint | Vector2 | None = None,
        buttons: set[int | Qt.MouseButton] | set[Qt.MouseButton] | set[int | Qt.MouseButton] | set[Qt.MouseButton | int] | None = None,
        keys: set[int | Qt.Key] | set[Qt.Key] | set[int | Qt.Key] | set[Qt.Key | int] | set[QKeySequence] | None = None,
    ):
        self._update_status_bar(screen, buttons, keys)

    def _update_status_bar(
        self,
        screen: QPoint | Vector2 | None = None,
        buttons: set[int | Qt.MouseButton] | set[Qt.MouseButton] | set[int | Qt.MouseButton] | set[Qt.MouseButton | int] | None = None,
        keys: set[int | Qt.Key] | set[Qt.Key] | set[int | Qt.Key] | set[Qt.Key | int] | set[QKeySequence] | None = None,
    ):
        """Rich status bar mirroring Module Designer style."""
        renderer = self.ui.mapRenderer

        # Resolve screen coords
        if screen is None:
            cursor_pos = self.cursor().pos()
            screen_qp = renderer.mapFromGlobal(cursor_pos)
            screen_vec = Vector2(screen_qp.x(), screen_qp.y())
        elif isinstance(screen, QPoint):
            screen_vec = Vector2(screen.x(), screen.y())
        else:
            screen_vec = screen

        # Resolve buttons/keys - ensure they are sets
        if buttons is None:
            buttons = set(renderer.mouse_down())  # pyright: ignore[reportAttributeAccessIssue]
        elif not isinstance(buttons, set):
            # Convert to set if it's iterable, otherwise create empty set
            try:
                buttons = set(buttons)
            except (TypeError, ValueError):
                buttons = set()
        if keys is None:
            keys = set(renderer.keys_down())
        elif not isinstance(keys, set):
            # Convert to set if it's iterable, otherwise create empty set
            try:
                keys = set(keys)
            except (TypeError, ValueError):
                keys = set()

        world: Vector3 = renderer.to_world_coords(screen_vec.x, screen_vec.y)
        hover_room: IndoorMapRoom | None = renderer.room_under_mouse()
        sel_rooms = renderer.selected_rooms()
        sel_hook = renderer.selected_hook()

        # Mouse/hover
        # Get semantic colors from palette
        colors = self._get_semantic_colors()

        hover_text = (
            f"<b><span style=\"{self._emoji_style}\">🧩</span>&nbsp;Hover:</b> <span style='color:{colors['accent1']}'>{hover_room.component.name}</span>"
            if hover_room
            else f"<b><span style=\"{self._emoji_style}\">🧩</span>&nbsp;Hover:</b> <span style='color:{colors['muted']}'><i>None</i></span>"
        )
        self._hover_label.setText(hover_text)

        self._mouse_label.setText(
            f'<b><span style="{self._emoji_style}">🖱</span>&nbsp;Coords:</b> '
            f"<span style='color:{colors['accent1']}'>{world.x:.2f}</span>, "
            f"<span style='color:{colors['accent2']}'>{world.y:.2f}</span>"
        )

        # Selection
        if sel_hook is not None:
            hook_room, hook_idx = sel_hook
            sel_text = f"<b><span style=\"{self._emoji_style}\">🎯</span>&nbsp;Selected Hook:</b> <span style='color:{colors['accent1']}'>{hook_room.component.name}</span> (#{hook_idx})"
        elif sel_rooms:
            sel_text = f"<b><span style=\"{self._emoji_style}\">🟦</span>&nbsp;Selected Rooms:</b> <span style='color:{colors['accent1']}'>{len(sel_rooms)}</span>"
        else:
            sel_text = f"<b><span style=\"{self._emoji_style}\">🟦</span>&nbsp;Selected:</b> <span style='color:{colors['muted']}'><i>None</i></span>"
        self._selection_label.setText(sel_text)

        # Update preview based on selection (only if not dragging a component)
        self._update_preview_from_selection()

        # Keys/buttons (sorted with modifiers first)
        colors = self._get_semantic_colors()
        self._keys_label.setText(format_status_bar_keys_and_buttons(keys, buttons, self._emoji_style, colors["accent3"], colors["accent2"]))

        # Mode/status line (reuse colors from above)
        mode_parts: list[str] = []
        if self._painting_walkmesh:
            material = self._current_material()
            mat_text = material.name.title().replace("_", " ") if material else "Material"
            mode_parts.append(f"<span style='color:{colors['warn']}'>Paint: {mat_text}</span>")
        if self._colorize_materials:
            mode_parts.append("Colorized")
        if renderer.snap_to_grid:
            mode_parts.append("Grid Snap")
        if renderer.snap_to_hooks:
            mode_parts.append("Hook Snap")
        self._mode_label.setText(
            '<b><span style="{style}">ℹ</span>&nbsp;Status:</b> {body}'.format(
                style=self._emoji_style,
                body=" | ".join(mode_parts) if mode_parts else f"<span style='color:{colors['muted']}'><i>Idle</i></span>",
            )
        )

    def show_help_window(self):
        window = HelpWindow(self, "./wiki/Indoor-Map-Builder-User-Guide.md")
        window.setWindowIcon(self.windowIcon())
        window.show()
        window.activateWindow()

    # =========================================================================
    # File operations
    # =========================================================================

    def save(self):
        # generate_mipmap is only used when building modules, not when saving .indoor files
        # The write() method handles serialization without needing minimap generation
        if not self._filepath:
            self.save_as()
        else:
            BinaryWriter.dump(self._filepath, self._map.write())
            self._undo_stack.setClean()
            self._refresh_window_title()

    def save_as(self):
        default_name = (
            Path(self._filepath).name
            if self._filepath and str(self._filepath).strip()
            else "test.indoor"
        )
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("Save Map"),
            default_name,
            tr("Indoor Map File (*.indoor);;Module (*.mod)"),
        )
        if not filepath or not str(filepath).strip():
            return
        path = Path(filepath)
        saving_as_mod = (
            (selected_filter and (".mod" in selected_filter))
            or path.suffix.lower() == ".mod"
        )
        if saving_as_mod:
            path = path.with_suffix(".mod") if path.suffix.lower() != ".mod" else path
            if not isinstance(self._installation, HTInstallation):
                QMessageBox.warning(
                    self, tr("No Installation"), tr("Please select an installation first.")
                )
                return

            def task():
                assert isinstance(self._installation, HTInstallation)
                return self._map.build(self._installation, self._kits, path)

            loader = AsyncLoader(
                self,
                tr("Saving module..."),
                task,
                tr("Failed to build map."),
            )
            if loader.exec():
                self._undo_stack.setClean()
                msg = trf("Module saved to:\n{path}", path=path)
                QMessageBox(QMessageBox.Icon.Information, tr("Module saved"), msg).exec()
        else:
            path = path.with_suffix(".indoor") if path.suffix.lower() != ".indoor" else path
            BinaryWriter.dump(path, self._map.write())
            self._filepath = str(path)
            self._undo_stack.setClean()
            self._refresh_window_title()

    def new(self):
        if not self._undo_stack.isClean():
            result = QMessageBox.question(
                self,
                tr("Unsaved Changes"),
                tr("You have unsaved changes. Do you want to save before creating a new map?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Save:
                self.save()
            elif result == QMessageBox.StandardButton.Cancel:
                return

        self._filepath = ""
        self._map.reset()
        self.ui.mapRenderer._bwm_surface_cache.clear()
        self._undo_stack.clear()
        self._undo_stack.setClean()  # Mark as clean for new file
        self._update_settings_ui()
        self._refresh_window_title()

    def open(self):
        if not self._undo_stack.isClean():
            result = QMessageBox.question(
                self,
                tr("Unsaved Changes"),
                tr("You have unsaved changes. Do you want to save before opening another map?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Save:
                self.save()
            elif result == QMessageBox.StandardButton.Cancel:
                return

        filepath, _ = QFileDialog.getOpenFileName(self, tr("Open Map"), "", "Indoor Map File (*.indoor)")
        if filepath and str(filepath).strip():
            try:
                missing_rooms = self._map.load(Path(filepath).read_bytes(), self._kits, self._module_kit_manager)
                self._map.rebuild_room_connections()
                self.ui.mapRenderer._bwm_surface_cache.clear()
                self._filepath = filepath
                self._undo_stack.clear()
                self._undo_stack.setClean()  # Mark as clean after loading
                self._update_settings_ui()
                self._refresh_window_title()

                if missing_rooms:
                    self._show_missing_rooms_dialog(missing_rooms)
            except OSError as e:
                QMessageBox(
                    QMessageBox.Icon.Critical,
                    tr("Failed to load file"),
                    trf("{error}", error=str((e.__class__.__name__, str(e)))),
                ).exec()

    def open_mod(self):
        """Open a `.mod` file by locating it in the active installation and loading by module name.

        We intentionally do not support embedded `.indoor` payloads inside modules; the map must be
        reconstructible from real module resources.
        """
        if not isinstance(self._installation, HTInstallation):
            QMessageBox.warning(self, tr("No Installation"), tr("Please select an installation first."))
            return

        filepath, _ = QFileDialog.getOpenFileName(self, tr("Open Module"), "", "Module (*.mod);;All Files (*)")
        if not filepath or not str(filepath).strip():
            return

        mod_path = Path(filepath)
        if not mod_path.is_file():
            QMessageBox.warning(self, tr("Invalid File"), trf("File not found:\n{mod_path}", mod_path=mod_path))
            return

        # Only possible if the module exists in the active installation.
        try:
            install_modules_dir = Path(self._installation.module_path())
            if mod_path.parent.resolve() == install_modules_dir.resolve():
                self.load_module_from_name(mod_path.stem)
                return
        except Exception:
            pass

        QMessageBox.warning(
            self,
            tr("Cannot Open Module"),
            tr(
                "This .mod is not inside the active installation's Modules folder, so the Toolset cannot resolve its resources.\n\nTip: copy it into the active installation's Modules folder, then re-open."
            ),
        )

    def _show_missing_rooms_dialog(
        self,
        missing_rooms: list[MissingRoomInfo],
    ):
        """Show a dialog with information about missing rooms/kits."""
        from toolset.gui.common.localization import translate as tr, translate_format as trf

        missing_kits = [r for r in missing_rooms if r.reason == "kit_missing"]
        missing_components = [r for r in missing_rooms if r.reason == "component_missing"]

        room_count: int = len(missing_rooms)
        missing_kit_names: set[str] = {r.kit_name for r in missing_rooms if r.reason == "kit_missing"}
        missing_component_pairs: set[tuple[str, str]] = {(r.kit_name, r.component_name) for r in missing_rooms if r.reason == "component_missing" and r.component_name}

        main_parts: list[str] = []
        if missing_kit_names:
            kit_list: str = ", ".join(f"'{name}'" for name in sorted(missing_kit_names))
            main_parts.append(trf("Missing kit{plural}: {kits}", plural="s" if len(missing_kit_names) != 1 else "", kits=kit_list))
        if missing_component_pairs:
            component_list: str = ", ".join(f"'{comp}' ({kit})" for kit, comp in sorted(missing_component_pairs))
            main_parts.append(trf("Missing component{plural}: {components}", plural="s" if len(missing_component_pairs) != 1 else "", components=component_list))

        main_text = trf(
            "{count} room{plural} failed to load.\n\n{details}",
            count=room_count,
            plural="s" if room_count != 1 else "",
            details="\n".join(main_parts),
        )

        detailed_lines: list[str] = []
        if missing_kits:
            detailed_lines.append("=== Missing Kits ===")
            for room_info in missing_kits:
                kit_name = room_info.kit_name
                kit_json_path = get_kits_path() / f"{kit_name}.json"
                detailed_lines.append(f"\nRoom: Kit '{kit_name}'")
                if room_info.component_name:
                    detailed_lines.append(f"  Component: {room_info.component_name}")
                detailed_lines.append(f"  Expected Kit JSON: {kit_json_path}")
                detailed_lines.append(f"  Expected Kit Directory: {get_kits_path() / kit_name}")

        if missing_components:
            detailed_lines.append("\n=== Missing Components ===")
            for room_info in missing_components:
                kit_name = room_info.kit_name
                component_name = room_info.component_name or "Unknown"
                component_path = get_kits_path() / kit_name / "components" / component_name
                detailed_lines.append(f"\nRoom: Kit '{kit_name}', Component '{component_name}'")
                detailed_lines.append(f"  Expected Component Directory: {component_path}")

        msg_box = QMessageBox(
            QMessageBox.Icon.Warning,
            tr("Some Rooms Failed to Load"),
            main_text,
            flags=Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint,
        )
        msg_box.setDetailedText("\n".join(detailed_lines))
        msg_box.exec()

    def open_kit_downloader(self):
        from toolset.gui.windows.indoor_builder.kit_downloader import KitDownloader

        KitDownloader(self).exec()
        self._setup_kits()

    def build_map(self):
        if not isinstance(self._installation, HTInstallation):
            QMessageBox.warning(self, tr("No Installation"), tr("Please select an installation first."))
            return
        path: Path = self._installation.module_path() / f"{self._map.module_id}.mod"

        def task():
            assert isinstance(self._installation, HTInstallation)
            return self._map.build(self._installation, self._kits, path)

        msg = f"You can warp to the game using the code 'warp {self._map.module_id}'. "
        msg += f"Map files can be found in:\n{path}"
        loader = AsyncLoader(self, "Building Map...", task, "Failed to build map.")
        if loader.exec():
            QMessageBox(QMessageBox.Icon.Information, tr("Map built"), msg).exec()

    def load_module_from_name(self, module_name: str) -> bool:
        """Load a module by extracting it from the installation.

        Args:
        ----
            module_name: The module name (e.g., "end_m01aa" or "end_m01aa.rim")

        Returns:
        -------
            bool: True if the module was successfully loaded, False otherwise
        """
        if not isinstance(self._installation, HTInstallation):
            from loggerplus import RobustLogger  # type: ignore[import-untyped, note]  # pyright: ignore[reportMissingTypeStubs]

            RobustLogger().error("No installation available to load module from")
            return False

        # Check for unsaved changes
        if not self._undo_stack.isClean():
            from toolset.gui.common.localization import translate as tr

            result = QMessageBox.question(
                self,
                tr("Unsaved Changes"),
                tr("You have unsaved changes. Do you want to save before loading a module?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Save:
                self.save()
            elif result == QMessageBox.StandardButton.Cancel:
                return False

        try:
            from loggerplus import RobustLogger  # type: ignore[import-untyped, note]  # pyright: ignore[reportMissingTypeStubs]

            # Remove .rim or .mod extension if present
            module_root = module_name
            if module_root.endswith((".rim", ".mod")):
                module_root = module_root.rsplit(".", 1)[0]

            # Get installation path and kits path
            installation_path = self._installation.path()
            game = self._installation.game()

            # Extract the module
            def extract_task() -> IndoorMap:
                # Kits are deprecated; module browsing/extraction should use the implicit ModuleKit pipeline.
                return extract_indoor_from_module_as_modulekit(
                    module_root,
                    installation_path=installation_path,
                    game=game,
                    logger=RobustLogger(),
                )

            loader = AsyncLoader(
                self,
                f"Extracting module '{module_root}'...",
                extract_task,
                f"Failed to extract module '{module_root}'",
            )

            if not loader.exec():
                return False

            extracted_map = loader.result()
            if extracted_map is None:
                return False

            # Load the extracted map into the builder
            self._map = extracted_map
            self._map.rebuild_room_connections()
            self.ui.mapRenderer._bwm_surface_cache.clear()
            self.ui.mapRenderer.set_map(self._map)
            self._undo_stack.clear()
            self._undo_stack.setClean()
            self._filepath = ""  # Clear filepath since this is extracted, not loaded from file
            self._update_settings_ui()
            self._refresh_window_title()

            # Show success message
            room_count = len(self._map.rooms)
            from toolset.gui.common.localization import translate as tr, translate_format as trf

            QMessageBox(
                QMessageBox.Icon.Information,
                tr("Module Loaded"),
                trf("Successfully loaded module '{module}' with {count} room{plural}.", module=module_root, count=room_count, plural="s" if room_count != 1 else ""),
            ).exec()

            return True

        except Exception as e:  # noqa: BLE001
            from loggerplus import RobustLogger  # type: ignore[import-untyped, note]  # pyright: ignore[reportMissingTypeStubs]
            from toolset.gui.common.localization import translate as tr, translate_format as trf

            RobustLogger().exception(f"Failed to load module '{module_name}'")
            QMessageBox(
                QMessageBox.Icon.Critical,
                tr("Failed to load module"),
                trf("Failed to load module '{module}': {error}", module=module_name, error=str((e.__class__.__name__, str(e)))),
            ).exec()
            return False

    # =========================================================================
    # Edit operations
    # =========================================================================

    def delete_selected(self):
        changed = delete_selected_rooms_or_hook(
            self.ui.mapRenderer,
            self._map,
            self._undo_stack,
            self._invalidate_rooms,
        )
        if not changed:
            return
        self._refresh_window_title()

    def duplicate_selected(self):
        changed = duplicate_selected_rooms_or_hook(
            self.ui.mapRenderer,
            self._map,
            self._undo_stack,
            self._invalidate_rooms,
            Vector3(DUPLICATE_OFFSET_X, DUPLICATE_OFFSET_Y, DUPLICATE_OFFSET_Z),
        )
        if not changed:
            return
        self._refresh_window_title()

    def merge_selected(self):
        """Merge selected rooms into a single room.

        This operation combines 2 or more selected rooms into a single room with:
        - A merged walkmesh combining all source room geometries
        - Combined external hooks (internal hooks between merged rooms are removed)
        - Position at the centroid of all source rooms
        - The first room's visual model (MDL/MDX)

        The merged room is treated as a single entity for all subsequent operations.
        This action is undoable.
        """
        changed = apply_merge_selected_rooms(
            self.ui.mapRenderer,
            self._map,
            self._embedded_kit,
            self._undo_stack,
            self._invalidate_rooms,
            on_changed=self._refresh_window_title,
        )
        if not changed:
            return

    def cut_selected(self):
        cut_indoor_selection(copy_selected=self.copy_selected, delete_selected=self.delete_selected)

    def copy_selected(self):
        self._clipboard = copy_selected_rooms_to_clipboard(self.ui.mapRenderer)

    def paste(self):
        if apply_paste_rooms_from_clipboard(
            self.ui.mapRenderer,
            self._map,
            self._undo_stack,
            self._invalidate_rooms,
            self._clipboard,
            self._kits,
            on_changed=self._refresh_window_title,
        ):
            return

    def select_all(self):
        select_all_indoor_rooms(self.ui.mapRenderer, self._map.rooms)

    def deselect_all(self):
        self.ui.mapRenderer.clear_selected_rooms()
        self.ui.mapRenderer.set_cursor_component(None)
        self.ui.componentList.clearSelection()
        self.ui.componentList.setCurrentItem(None)
        self.ui.moduleComponentList.clearSelection()
        self.ui.moduleComponentList.setCurrentItem(None)
        self._set_preview_image(None)
        self._refresh_status_bar()

    # =========================================================================
    # View operations
    # =========================================================================

    def reset_view(self):
        reset_indoor_camera_view(
            self.ui.mapRenderer,
            default_camera_x=DEFAULT_CAMERA_POSITION_X,
            default_camera_y=DEFAULT_CAMERA_POSITION_Y,
            default_camera_rotation=DEFAULT_CAMERA_ROTATION,
            default_camera_zoom=DEFAULT_CAMERA_ZOOM,
        )

    def center_on_selection(self):
        center_indoor_camera_on_selected_rooms(self.ui.mapRenderer)

    # =========================================================================
    # Component selection
    # =========================================================================

    def selected_component(self) -> KitComponent | None:
        """Return the currently selected component for placement.

        ONLY returns cursor_component to prevent state desync between
        the renderer and UI lists. The cursor_component is the single
        source of truth for what component will be placed on click.
        """
        return self.ui.mapRenderer.cursor_component

    def set_warp_point(self, x: float, y: float, z: float):
        self._map.warp_point = Vector3(x, y, z)

    def on_kit_selected(
        self,
        index: int = -1,  # pyright: ignore[reportUnusedParameter]
    ):
        kit: Kit = self.ui.kitSelect.currentData()
        if not isinstance(kit, Kit):
            return
        self.ui.componentList.clear()
        self._set_preview_image(None)
        for component in kit.components:
            item = QListWidgetItem(component.name)
            item.setData(Qt.ItemDataRole.UserRole, component)
            self.ui.componentList.addItem(item)  # pyright: ignore[reportCallIssue, reportArgumentType]

    def onComponentSelected(
        self,
        item: QListWidgetItem | None = None,
        previous: QListWidgetItem | None = None,  # pyright: ignore[reportUnusedParameter]
    ):
        if item is None:
            self._set_preview_image(None)
            self.ui.mapRenderer.set_cursor_component(None)
            return

        component: KitComponent = item.data(Qt.ItemDataRole.UserRole)

        # Toggle: if same component is already selected, deselect it
        if self.ui.mapRenderer.cursor_component is component:
            # Clicking the same component again = "pick it up" (deselect)
            self.ui.componentList.clearSelection()
            self.ui.componentList.setCurrentItem(None)
            self._set_preview_image(None)
            self.ui.mapRenderer.set_cursor_component(None)
            return

        self._set_preview_image(ensure_component_image(component))
        self.ui.mapRenderer.set_cursor_component(component)

    # =========================================================================
    # Mouse event handlers
    # =========================================================================

    def on_mouse_moved(
        self,
        screen: Vector2,
        delta: Vector2,
        buttons: set[int | Qt.MouseButton] | set[Qt.MouseButton] | set[int | Qt.MouseButton] | set[Qt.MouseButton | int],
        keys: set[int | Qt.Key] | set[Qt.Key] | set[int | Qt.Key] | set[Qt.Key | int],
    ):
        self._refresh_status_bar(screen=screen, buttons=buttons, keys=keys)
        world_delta: Vector2 = self.ui.mapRenderer.to_world_delta(delta.x, delta.y)

        # Walkmesh painting drag - Shift+Left drag should paint
        handled_cam = handle_standard_2d_camera_movement(self.ui.mapRenderer, screen, delta, world_delta, buttons, keys, is_indoor_builder=True)

        if not handled_cam and (self._painting_walkmesh or Qt.Key.Key_Shift in keys) and Qt.MouseButton.LeftButton in buttons and Qt.Key.Key_Control not in keys:
            self._apply_paint_at_screen(screen)
            return

    def on_mouse_pressed(
        self,
        screen: Vector2,
        buttons: set[int | Qt.MouseButton],
        keys: set[int | Qt.Key],
    ):
        if Qt.MouseButton.LeftButton not in buttons:
            return
        if Qt.Key.Key_Control in keys:
            return  # Control is for camera pan

        # Check for walkmesh painting mode - Shift+Left click should paint
        if self._painting_walkmesh or Qt.Key.Key_Shift in keys:
            self._begin_paint_stroke(screen)
            return

        renderer = self.ui.mapRenderer
        world = renderer.to_world_coords(screen.x, screen.y)
        handle_indoor_primary_press(
            renderer,
            world,
            shift_pressed=Qt.Key.Key_Shift in keys,
            clear_placement_mode=self._clear_placement_mode,
            place_new_room=self._place_new_room,
            start_marquee=lambda: renderer.start_marquee(screen),
        )

    def _clear_placement_mode(self):
        """Clear all placement mode state - cursor component and UI selections."""
        clear_indoor_placement_mode(
            self.ui.mapRenderer,
            self.ui.componentList,
            self.ui.moduleComponentList,
            on_cleared=self._update_preview_from_selection,
        )

    def on_mouse_released(
        self,
        screen: Vector2,
        buttons: set[int | Qt.MouseButton],
        keys: set[int | Qt.Key],
    ):
        # NOTE: 'buttons' contains buttons STILL held after release (left button was just removed)
        # So if left button was just released, it will NOT be in buttons

        # ALWAYS end drag operations when ANY button is released
        # This is critical - marquee, room drag, hook drag, warp drag must all stop
        renderer = self.ui.mapRenderer

        # Finish paint stroke if active (including Shift+Left paint mode)
        if self._paint_stroke_active:
            self._finish_paint_stroke()

        # Stop hook drag if active - rebuild connections after hook position changes
        if renderer._dragging_hook:
            renderer._dragging_hook = False
            self._map.rebuild_room_connections()

        # CRITICAL: Always end any active drag operations on mouse release
        # This includes marquee selection, room dragging, warp dragging
        renderer.end_drag()

        self._refresh_status_bar(screen=screen, buttons=buttons, keys=keys)

    def on_rooms_moved(
        self,
        rooms: list[IndoorMapRoom],
        old_positions: list[Vector3],
        new_positions: list[Vector3],
    ):
        """Called when rooms have been moved via drag."""
        if push_rooms_moved_undo(
            self._map,
            rooms,
            old_positions,
            new_positions,
            self._undo_stack,
            self._invalidate_rooms,
            position_change_epsilon=POSITION_CHANGE_EPSILON,
        ):
            self._refresh_window_title()
            self._sync_rooms_to_blender_if_enabled(rooms)

    def on_rooms_rotated(
        self,
        rooms: list[IndoorMapRoom],
        old_rotations: list[float],
        new_rotations: list[float],
    ):
        """Called when rooms have been rotated during drag."""
        if push_rooms_rotated_undo(
            self._map,
            rooms,
            old_rotations,
            new_rotations,
            self._undo_stack,
            self._invalidate_rooms,
            rotation_change_epsilon=ROTATION_CHANGE_EPSILON,
        ):
            self._refresh_window_title()
            self._sync_rooms_to_blender_if_enabled(rooms)

    def _sync_rooms_to_blender_if_enabled(self, rooms: list[IndoorMapRoom]) -> None:
        if not self.is_blender_mode() or self._blender_controller is None or self._transform_sync_in_progress:
            return
        for room in rooms:
            self.sync_room_to_blender(room)

    def on_warp_moved(
        self,
        old_position: Vector3,
        new_position: Vector3,
    ):
        """Called when warp point has been moved via drag."""
        if push_warp_moved_undo(
            self._map,
            old_position,
            new_position,
            self._undo_stack,
            position_change_epsilon=POSITION_CHANGE_EPSILON,
        ):
            self._refresh_window_title()

    def on_marquee_select(
        self,
        rooms: list[IndoorMapRoom],
        additive: bool,
    ):
        """Called when marquee selection completes."""
        if not additive:
            self.ui.mapRenderer.clear_selected_rooms()
        for room in rooms:
            self.ui.mapRenderer.select_room(room, clear_existing=False)

    def _place_new_room(self, component: KitComponent):
        """Place a new room at cursor position with undo support."""
        room = IndoorMapRoom(
            component,
            Vector3(*self.ui.mapRenderer.cursor_point),
            self.ui.mapRenderer.cursor_rotation,
            flip_x=self.ui.mapRenderer.cursor_flip_x,
            flip_y=self.ui.mapRenderer.cursor_flip_y,
        )
        cmd = AddRoomCommand(self._map, room, self._invalidate_rooms)
        self._undo_stack.push(cmd)
        self.ui.mapRenderer.cursor_rotation = 0.0
        self.ui.mapRenderer.cursor_flip_x = False
        self.ui.mapRenderer.cursor_flip_y = False
        self._refresh_window_title()

    # =========================================================================
    # Walkmesh painting helpers
    # =========================================================================

    def _begin_paint_stroke(self, screen: Vector2):
        self._paint_stroke_active = True
        self._paint_stroke_originals.clear()
        self._paint_stroke_new.clear()
        self._apply_paint_at_screen(screen)

    def _apply_paint_at_screen(self, screen: Vector2):
        world = self.ui.mapRenderer.to_world_coords(screen.x, screen.y)
        self._apply_paint_at_world(world)

    def _apply_paint_at_world(self, world: Vector3):
        material = self._current_material()
        if material is None:
            return
        room, face_index = self.ui.mapRenderer.pick_face(world)
        if room is None or face_index is None:
            return
        # Ensure we have a writable walkmesh override
        if room.walkmesh_override is None:
            room.walkmesh_override = deepcopy(room.component.bwm)
        base_bwm = room.walkmesh_override
        if not (0 <= face_index < len(base_bwm.faces)):
            return

        key = (room, face_index)
        if key not in self._paint_stroke_originals:
            self._paint_stroke_originals[key] = base_bwm.faces[face_index].material

        if base_bwm.faces[face_index].material == material:
            return

        base_bwm.faces[face_index].material = material
        self._paint_stroke_new[key] = material
        self._invalidate_rooms([room])

    def _finish_paint_stroke(self):
        if not self._paint_stroke_active:
            return
        self._paint_stroke_active = False
        if not self._paint_stroke_new:
            return

        rooms: list[IndoorMapRoom] = []
        face_indices: list[int] = []
        old_materials: list[SurfaceMaterial] = []
        new_materials: list[SurfaceMaterial] = []

        for (room, face_index), new_material in self._paint_stroke_new.items():
            rooms.append(room)
            face_indices.append(face_index)
            old_materials.append(self._paint_stroke_originals.get((room, face_index), new_material))
            new_materials.append(new_material)

        cmd = PaintWalkmeshCommand(rooms, face_indices, old_materials, new_materials, self._invalidate_rooms)
        self._undo_stack.push(cmd)
        self._refresh_window_title()

    def on_mouse_scrolled(
        self,
        delta: Vector2,
        buttons: set[int | Qt.MouseButton],
        keys: set[int | Qt.Key],
    ):
        handle_indoor_scroll(
            self.ui.mapRenderer,
            delta_y=delta.y,
            ctrl_pressed=Qt.Key.Key_Control in keys,
            zoom_factor_from_delta=lambda value: calculate_zoom_strength(value, ZOOM_WHEEL_SENSITIVITY),
        )
        self._refresh_status_bar(screen=None, buttons=buttons, keys=keys)  # type: ignore[reportArgumentType]

    def onMouseDoubleClicked(
        self,
        delta: Vector2,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
    ):
        handle_indoor_double_click_select_connected(
            self.ui.mapRenderer,
            left_pressed=Qt.MouseButton.LeftButton in buttons,
            add_connected_to_selection=self.add_connected_to_selection,
        )

    def on_context_menu(self, point: QPoint):
        world, room, hook_hit = get_indoor_context_hits(
            self.ui.mapRenderer,
            screen_x=point.x(),
            screen_y=point.y(),
        )
        menu = QMenu(self)

        populate_indoor_context_menu(
            menu,
            renderer=self.ui.mapRenderer,
            room=room,
            hook_hit=hook_hit,
            world=world,
            on_duplicate=self.duplicate_selected,
            on_delete=self.delete_selected,
            on_rotate=self._rotate_selected,
            on_flip=self._flip_selected,
            on_merge=self.merge_selected,
            on_add_hook_at=self.ui.mapRenderer.add_hook_at,
            on_set_warp_point=lambda pos: self.set_warp_point(pos.x, pos.y, pos.z),
        )

        menu.popup(self.ui.mapRenderer.mapToGlobal(point))

    def _rotate_selected(self, angle: float):
        changed = apply_rotate_selected_rooms(
            self.ui.mapRenderer,
            self._map,
            self._undo_stack,
            self._invalidate_rooms,
            angle,
            on_changed=self._refresh_window_title,
        )
        if not changed:
            return

    def _flip_selected(
        self,
        flip_x: bool,
        flip_y: bool,
    ):
        changed = apply_flip_selected_rooms(
            self.ui.mapRenderer,
            self._map,
            self._undo_stack,
            self._invalidate_rooms,
            flip_x,
            flip_y,
            on_changed=self._refresh_window_title,
        )
        if not changed:
            return

    def _cancel_all_operations(self):
        """Cancel all active operations and reset to safe state.

        This is the "panic button" - cancels everything to get out of stuck states:
        - Cancels marquee selection
        - Cancels room/hook/warp dragging
        - Cancels placement mode
        - Cancels walkmesh painting
        - Clears selections (optional, can be toggled)
        """
        renderer = self.ui.mapRenderer
        cancel_indoor_operations_core(
            renderer,
            clear_paint_stroke=self._clear_paint_stroke,
            clear_placement_mode=self._clear_cursor_component_only,
            on_marquee_cleared=self._reset_renderer_drag_mode,
            on_finished=self._refresh_status_bar,
        )

    def _clear_paint_stroke(self) -> None:
        if not self._paint_stroke_active:
            return
        self._paint_stroke_active = False
        self._paint_stroke_originals.clear()
        self._paint_stroke_new.clear()

    def _clear_cursor_component_only(self) -> None:
        renderer = self.ui.mapRenderer
        renderer.set_cursor_component(None)
        renderer.clear_selected_hook()

    def _reset_renderer_drag_mode(self) -> None:
        self.ui.mapRenderer._drag_mode = DragMode.NONE

    def keyPressEvent(self, e: QKeyEvent):  # type: ignore[reportIncompatibleMethodOverride]
        key = e.key()
        modifiers = e.modifiers()
        has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        has_no_mods = not bool(modifiers)
        renderer = self.ui.mapRenderer

        handled = handle_indoor_key_press_shortcuts(
            key,
            has_ctrl=has_ctrl,
            has_no_mods=has_no_mods,
            placement_active=renderer.cursor_component is not None,
            key_escape=Qt.Key.Key_Escape,
            key_toggle_snap_grid=Qt.Key.Key_G,
            key_toggle_snap_hooks=Qt.Key.Key_H,
            key_rotate_selected=Qt.Key.Key_R,
            key_flip_selected=Qt.Key.Key_F,
            key_select_all=Qt.Key.Key_A,
            key_delete=Qt.Key.Key_Delete,
            key_backspace=Qt.Key.Key_Backspace,
            key_copy=Qt.Key.Key_C,
            key_cut=Qt.Key.Key_X,
            key_paste=Qt.Key.Key_V,
            key_duplicate=Qt.Key.Key_D,
            key_cancel_placement=Qt.Key.Key_Space,
            key_toggle_paint=Qt.Key.Key_P,
            key_reset_home=Qt.Key.Key_Home,
            key_reset_zero=Qt.Key.Key_0,
            key_refresh=Qt.Key.Key_F5,
            key_save=Qt.Key.Key_S,
            key_new=Qt.Key.Key_N,
            key_open=Qt.Key.Key_O,
            on_escape=lambda: cancel_indoor_operations_and_clear_selection(renderer, cancel_operations=self._cancel_all_operations),
            on_toggle_snap_grid=lambda: toggle_check_widget(self.ui.snapToGridCheck),
            on_toggle_snap_hooks=lambda: toggle_check_widget(self.ui.snapToHooksCheck),
            on_rotate_selected=lambda: run_if_any_indoor_rooms_selected(renderer, lambda: self._rotate_selected(self.ui.rotSnapSpin.value())),
            on_flip_selected=lambda: run_if_any_indoor_rooms_selected(renderer, lambda: self._flip_selected(True, False)),
            on_select_all=self.select_all,
            on_delete_selected=self.delete_selected,
            on_cancel_placement=self._clear_placement_mode,
            on_toggle_paint=lambda: toggle_check_widget(self.ui.enablePaintCheck),
            on_reset_view=self.reset_view,
            on_refresh=lambda: cancel_indoor_operations_and_refresh(renderer, cancel_operations=self._cancel_all_operations),
        )

        if not handled:
            self.ui.mapRenderer.keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):  # type: ignore[reportIncompatibleMethodOverride]
        self.ui.mapRenderer.keyReleaseEvent(e)

    def add_connected_to_selection(
        self,
        room: IndoorMapRoom,
    ):
        add_connected_indoor_rooms_to_selection(self.ui.mapRenderer, room)

    def closeEvent(self, e: QCloseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Handle window close event - ensure proper cleanup of all resources."""
        # Stop renderer timer first
        try:
            self.ui.mapRenderer._render_timer.stop()
            # Process events to allow renderer to stop gracefully
            QApplication.processEvents()
        except Exception:
            RobustLogger().warning("Failed to stop renderer timer during closeEvent - it may have already been stopped or not initialized.")

        # Disconnect all signals to prevent callbacks after destruction
        try:
            # Disconnect UI signals
            self.ui.kitSelect.currentIndexChanged.disconnect()
            self.ui.componentList.currentItemChanged.disconnect()
            self.ui.moduleSelect.currentIndexChanged.disconnect()
            self.ui.moduleComponentList.currentItemChanged.disconnect()

            # Disconnect renderer signals
            renderer = self.ui.mapRenderer
            try:
                renderer.customContextMenuRequested.disconnect()
                renderer.sig_mouse_moved.disconnect()
                renderer.sig_mouse_pressed.disconnect()
                renderer.sig_mouse_released.disconnect()
                renderer.sig_mouse_scrolled.disconnect()
                renderer.sig_mouse_double_clicked.disconnect()
                renderer.sig_rooms_moved.disconnect()
                renderer.sig_warp_moved.disconnect()
                renderer.sig_marquee_select.disconnect()
            except Exception:
                RobustLogger().warning("Failed to disconnect renderer signals during closeEvent - they may have already been disconnected.")

            # Disconnect undo stack signals
            if self._undo_stack is not None:
                try:
                    self._undo_stack.canUndoChanged.disconnect()
                    self._undo_stack.canRedoChanged.disconnect()
                    self._undo_stack.undoTextChanged.disconnect()
                    self._undo_stack.redoTextChanged.disconnect()
                except Exception:
                    pass
        except Exception:
            # Some signals may already be disconnected
            pass

        # Clear references
        self._kits.clear()
        self._clipboard.clear()
        self._current_module_kit = None
        if self._module_kit_manager is not None:
            try:
                self._module_kit_manager.clear_cache()
            except Exception:
                pass

        # Process any pending events before destruction
        QApplication.processEvents()

        # Call parent closeEvent (this will trigger BlenderEditorMixin cleanup if needed)
        # Wrap in try-except to handle case where widget is already being destroyed
        try:
            # Check if widget is still valid by accessing a safe property
            if self.isVisible():
                super().closeEvent(e)
            else:
                # Widget is already destroyed, just accept the event
                e.accept()
        except RuntimeError:
            # Widget has been deleted, just accept the event
            e.accept()
        except Exception:
            # Any other error, try to accept the event
            try:
                e.accept()
            except Exception:
                pass


if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_app_cli

    sys.exit(launch_app_cli("indoor-builder"))
