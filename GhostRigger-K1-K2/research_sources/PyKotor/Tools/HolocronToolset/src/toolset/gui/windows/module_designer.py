"""Module designer window: area list, 2D view, GIT editing, and module pack/unpack."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time

from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence, TextIO, Union, cast

import qtpy

from qtpy.QtCore import QEvent, QPoint, QTimer, Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QFont, QIcon, QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.common.indoorkit import KitComponent
from pykotor.common.indoormap import EmbeddedKit, IndoorMap, IndoorMapRoom
from pykotor.common.misc import Color, ResRef
from pykotor.common.module import Module, ModuleResource
from pykotor.common.modulekit import ModuleKitManager
from pykotor.extract.file import ResourceIdentifier
from pykotor.resource.formats.bwm import BWM
from pykotor.resource.formats.erf import write_erf
from pykotor.resource.formats.lyt import LYT, LYTDoorHook, LYTObstacle, LYTRoom, LYTTrack
from pykotor.resource.formats.vis import bytes_vis
from pykotor.resource.generics.git import (
    GITCamera,
    GITCreature,
    GITDoor,
    GITEncounter,
    GITEncounterSpawnPoint,
    GITInstance,
    GITPlaceable,
    GITSound,
    GITStore,
    GITTrigger,
    GITWaypoint,
)
from pykotor.resource.generics.utd import read_utd
from pykotor.resource.generics.utt import read_utt
from pykotor.resource.generics.utw import read_utw
from pykotor.resource.type import ResourceType
from pykotor.tools import indoorkit as indoorkit_tools, module
from pykotor.tools.misc import is_mod_file
from toolset.blender import BlenderEditorMode, ConnectionState, check_blender_and_ask, get_blender_settings
from toolset.blender.integration import BlenderEditorMixin
from toolset.blender.serializers import deserialize_git_instance, serialize_module_data
from toolset.data.indoorkit.qt_preview import ensure_component_image
from toolset.data.installation import HTInstallation
from toolset.data.misc import ControlItem
from toolset.gui.common.editor_pipelines import (
    populate_module_root_combobox,
    set_exclusive_checkbox_selection,
    set_preview_source_image,
)
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
from toolset.gui.common.interaction.camera import handle_standard_2d_camera_movement
from toolset.gui.common.interaction.transforms import TransformInteractionState
from toolset.gui.common.lyt_ops import (
    add_lyt_element_to_blender,
    duplicate_lyt_element_with_offset,
    lyt_element_blender_object_name,
    lyt_element_blender_type,
    lyt_element_kind_name,
    lyt_element_name,
    remove_lyt_element,
)
from toolset.gui.common.snapping import snap_degrees, snap_radians, snap_value, snap_vector3
from toolset.gui.common.status_bar_utils import format_status_bar_keys_and_buttons
from toolset.gui.common.walkmesh_materials import (
    get_walkmesh_material_colors,
    populate_material_combo_box,
    populate_material_list_widget,
)
from toolset.gui.dialogs.insert_instance import InsertInstanceDialog
from toolset.gui.dialogs.select_module import SelectModuleDialog
from toolset.gui.editor import Editor
from toolset.gui.editors.git import DeleteCommand, MoveCommand, RotateCommand, _GeometryMode, _InstanceMode, _SpawnMode, open_instance_dialog
from toolset.gui.widgets.installation_toolbar import StandaloneWindowMixin
from toolset.gui.widgets.renderer.lyt_renderer import LYTRenderer
from toolset.gui.widgets.renderer.module import ModuleRenderer
from toolset.gui.widgets.settings.widgets.module_designer import ModuleDesignerSettings
from toolset.gui.windows.designer_controls import ModuleDesignerControls2d, ModuleDesignerControls3d, ModuleDesignerControlsFreeCam
from toolset.gui.windows.help import HelpWindow
from toolset.gui.windows.indoor_builder.constants import (
    DUPLICATE_OFFSET_X,
    DUPLICATE_OFFSET_Y,
    DUPLICATE_OFFSET_Z,
    POSITION_CHANGE_EPSILON,
    ROTATION_CHANGE_EPSILON,
    ZOOM_WHEEL_SENSITIVITY,
)
from toolset.gui.windows.indoor_builder.undo_commands import (
    AddRoomCommand,
    PaintWalkmeshCommand,
    ResetWalkmeshCommand,
)
from toolset.utils.window import open_resource_editor
from utility.common.geometry import Polygon3, SurfaceMaterial, Vector2, Vector3, Vector4
from utility.error_handling import safe_repr

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QImage, QKeyEvent, QShowEvent

    from pykotor.common.indoorkit import Kit
    from pykotor.common.module import UTT, UTW
    from pykotor.common.modulekit import ModuleKit
    from pykotor.gl.scene import Camera
    from pykotor.resource.generics.are import ARE
    from pykotor.resource.generics.git import (
        GIT,
        GITObject,
    )
    from pykotor.resource.generics.ifo import IFO
    from toolset.gui.common.indoor_builder_ops import RoomClipboardData
    from toolset.gui.widgets.renderer.lyt_renderer import LYTRenderer
    from toolset.gui.widgets.renderer.walkmesh import WalkmeshRenderer
    from toolset.gui.windows.indoor_builder.constants import ZOOM_STEP_FACTOR, DragMode  # noqa: F401  # Phase 2
    from toolset.gui.windows.indoor_builder.renderer import IndoorMapRenderer

if qtpy.QT5:
    from qtpy.QtWidgets import QUndoCommand, QUndoStack  # pyright: ignore[reportPrivateImportUsage]
elif qtpy.QT6:
    from qtpy.QtGui import QUndoCommand, QUndoStack  # pyright: ignore[reportPrivateImportUsage]
else:
    raise ValueError(f"Invalid QT_API: '{qtpy.API_NAME}'")


# =============================================================================
# Editor Mode Enum
# =============================================================================


class EditorMode:
    """Modes for the unified Module Designer.

    OBJECT  -- Default. Place/move/edit GIT instances (creatures, doors, etc.).
    LAYOUT  -- Indoor Builder room assembly mode (from indoor_builder).
    WALKMESH -- Walkmesh face/vertex selection and material painting.
    """

    OBJECT: int = 0
    LAYOUT: int = 1
    WALKMESH: int = 2


class EditorTool:
    """Active interaction tool within Object/Walkmesh mode.

    SELECT -- Click to select instances (cursor: arrow).
    MOVE   -- Drag to translate selected instances (cursor: move).
    ROTATE -- Drag to rotate selected instances (cursor: rotate).
    """

    SELECT: int = 0
    MOVE: int = 1
    ROTATE: int = 2


class WalkmeshSelectMode:
    """Selection mode within Walkmesh editor mode."""

    FACE: int = 0
    EDGE: int = 1
    VERTEX: int = 2


class _BlenderPropertyCommand(QUndoCommand):
    def __init__(
        self,
        instance: GITInstance,
        apply_func: Callable[[GITInstance, Any], None],
        old_value: Any,
        new_value: Any,
        on_change: Callable[[GITInstance], None],
        label: str,
    ):
        super().__init__(label)
        self._instance = instance
        self._apply = apply_func
        self._old = old_value
        self._new = new_value
        self._on_change = on_change

    def undo(self):
        self._apply(self._instance, self._old)
        self._on_change(self._instance)

    def redo(self):
        self._apply(self._instance, self._new)
        self._on_change(self._instance)


class _BlenderInsertCommand(QUndoCommand):
    def __init__(self, git: GIT, instance: GITInstance, editor: "ModuleDesigner"):
        super().__init__("Blender add instance")
        self._git = git
        self._instance = instance
        self._editor = editor

    def undo(self):
        if self._instance in self._git.instances():
            self._git.remove(self._instance)
        self._editor.rebuild_instance_list()

    def redo(self):
        if self._instance not in self._git.instances():
            self._git.add(self._instance)
        self._editor.rebuild_instance_list()


class _BlenderDeleteCommand(QUndoCommand):
    def __init__(self, git: GIT, instance: GITInstance, editor: "ModuleDesigner"):
        super().__init__("Blender delete instance")
        self._git = git
        self._instance = instance
        self._editor = editor

    def undo(self):
        if self._instance not in self._git.instances():
            self._git.add(self._instance)
        self._editor.rebuild_instance_list()

    def redo(self):
        if self._instance in self._git.instances():
            self._git.remove(self._instance)
        self._editor.rebuild_instance_list()


class _SetWalkmeshFaceMaterialCommand(QUndoCommand):
    def __init__(
        self,
        walkmesh: BWM,
        face_index: int,
        old_material: SurfaceMaterial,
        new_material: SurfaceMaterial,
        on_change: Callable[[], None],
    ):
        super().__init__("Set walkmesh face material")
        self._walkmesh = walkmesh
        self._face_index = face_index
        self._old_material = old_material
        self._new_material = new_material
        self._on_change = on_change

    def _set(self, material: SurfaceMaterial):
        if not (0 <= self._face_index < len(self._walkmesh.faces)):
            return
        self._walkmesh.faces[self._face_index].material = material
        self._on_change()

    def undo(self):
        self._set(self._old_material)

    def redo(self):
        self._set(self._new_material)


class _MoveWalkmeshVertexCommand(QUndoCommand):
    def __init__(
        self,
        vertex: Vector3,
        old_position: Vector3,
        new_position: Vector3,
        on_change: Callable[[], None],
    ):
        super().__init__("Move walkmesh vertex")
        self._vertex = vertex
        self._old_position = Vector3(old_position.x, old_position.y, old_position.z)
        self._new_position = Vector3(new_position.x, new_position.y, new_position.z)
        self._on_change = on_change

    def _apply(self, position: Vector3):
        self._vertex.x = position.x
        self._vertex.y = position.y
        self._vertex.z = position.z
        self._on_change()

    def undo(self):
        self._apply(self._old_position)

    def redo(self):
        self._apply(self._new_position)


_RESREF_CLASSES = (
    GITCreature,
    GITDoor,
    GITEncounter,
    GITPlaceable,
    GITSound,
    GITStore,
    GITTrigger,
    GITWaypoint,
)
_TAG_CLASSES = (GITDoor, GITTrigger, GITWaypoint, GITPlaceable)
_BEARING_CLASSES = (GITCreature, GITDoor, GITPlaceable, GITStore, GITWaypoint)

# Maps resource file types to the GIT instance class used for spawning from a drag-drop.
_RESTYPE_TO_GIT_CLASS: dict[ResourceType, type[GITInstance]] = {
    ResourceType.UTC: GITCreature,
    ResourceType.UTP: GITPlaceable,
    ResourceType.UTD: GITDoor,
    ResourceType.UTW: GITWaypoint,
    ResourceType.UTS: GITSound,
    ResourceType.UTE: GITEncounter,
    ResourceType.UTT: GITTrigger,
    ResourceType.UTM: GITStore,
}

ResrefInstance = Union[
    GITCreature,
    GITDoor,
    GITEncounter,
    GITPlaceable,
    GITSound,
    GITStore,
    GITTrigger,
    GITWaypoint,
]
TagInstance = Union[GITDoor, GITTrigger, GITWaypoint, GITPlaceable]
BearingInstance = Union[GITCreature, GITDoor, GITPlaceable, GITStore, GITWaypoint]


def run_module_designer(
    active_path: str,
    active_name: str,
    active_tsl: bool,  # noqa: FBT001
    module_path: str | None = None,
):
    """An alternative way to start the ModuleDesigner: run thisfunction in a new process so the main tool window doesn't wait on the module designer."""
    import sys

    from toolset.__main__ import main_init

    main_init()
    app = QApplication(sys.argv)
    from toolset.gui.common.tooltip_utils import install_tooltip_label_filter

    install_tooltip_label_filter(app)
    designer_ui = ModuleDesigner(
        None,
        HTInstallation(active_path, active_name, tsl=active_tsl),
        Path(module_path) if module_path is not None else None,
    )
    # Standardized resource path format
    icon_path = ":/images/icons/sith.png"
    icon_pixmap = QPixmap(icon_path)

    # Debugging: Check if the resource path is accessible
    if not icon_pixmap.isNull():
        designer_ui.log.debug(f"HT main window Icon loaded successfully from {icon_path}")
        icon = QIcon(icon_pixmap)
        designer_ui.setWindowIcon(icon)
        cast("QApplication", QApplication.instance()).setWindowIcon(icon)
    else:
        print(f"Failed to load HT main window icon from {icon_path}")
    sys.exit(app.exec())


class ModuleDesigner(QMainWindow, BlenderEditorMixin, StandaloneWindowMixin):
    STANDALONE_REQUIRES_INSTALLATION = True

    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation,
        mod_filepath: Path | None = None,
        use_blender: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle("Module Designer")

        # Initialize Blender integration
        self._init_blender_integration(BlenderEditorMode.MODULE_DESIGNER)
        self._use_blender_mode: bool = use_blender
        self._blender_choice_made: bool = False  # Track if we've already asked about Blender
        self._view_stack: QStackedWidget | None = None
        self._blender_placeholder: QWidget | None = None
        self._blender_log_buffer: deque[str] = deque(maxlen=500)
        self._blender_log_path: Path | None = None
        self._blender_log_handle: TextIO | None = None
        self._blender_progress_dialog: QProgressDialog | None = None
        self._blender_log_view: QPlainTextEdit | None = None
        self._blender_connected_once: bool = False
        self._selection_sync_from_blender: bool = False
        self._selection_sync_in_progress: bool = False
        self._transform_sync_in_progress: bool = False
        self._property_sync_in_progress: bool = False
        self._instance_sync_in_progress: bool = False
        self._instance_id_lookup: dict[int, GITInstance] = {}
        self._last_walkmeshes: list[BWM] = []
        self._selected_walkmesh_face: tuple[BWM, int, Vector3] | None = None
        self._selected_walkmesh_edge: tuple[BWM, int, int, Vector3] | None = None
        self._selected_walkmesh_vertex: tuple[BWM, int, int, Vector3] | None = None
        self._walkmesh_vertex_drag_active: bool = False
        self._walkmesh_vertex_drag_vertex: Vector3 | None = None
        self._walkmesh_vertex_drag_old_position: Vector3 | None = None
        self._walkmesh_vertex_drag_current_position: Vector3 | None = None
        self._walkmesh_vertex_drag_anchor: Vector3 | None = None
        self._walkmesh_vertex_drag_axis: str | None = None
        self._walkmesh_select_mode: int = WalkmeshSelectMode.FACE
        self._walkmesh_face_ui_updating: bool = False
        self._object_gizmo_drag_active: bool = False
        self._object_gizmo_drag_axis: str | None = None
        self._object_gizmo_drag_anchor: Vector3 | None = None
        self._object_rotate_gizmo_drag_active: bool = False
        self._object_rotate_gizmo_anchor_angle: float | None = None
        self._object_rotate_gizmo_last_angle: float = 0.0
        self._fallback_session_path: Path | None = None
        self._last_undo_index: int = 0
        self._indoor_preview_source_image: QImage | None = None

        self._installation: HTInstallation = installation
        self._module: Module | None = None
        self._orig_filepath: Path | None = mod_filepath

        self.undo_stack: QUndoStack = QUndoStack(self)
        self.transform_state: TransformInteractionState = TransformInteractionState(self.undo_stack, self)

        self.selected_instances: list[GITInstance] = []
        self.settings: ModuleDesignerSettings = ModuleDesignerSettings()
        self.log: RobustLogger = RobustLogger()

        # Track unsaved changes
        self._has_unsaved_changes: bool = False
        self._clean_undo_index: int = 0

        self.target_frame_rate = 120  # Target higher for smoother camera
        self.camera_update_timer = QTimer()
        self.camera_update_timer.timeout.connect(self.update_camera)
        self.camera_update_timer.start(int(1000 / self.target_frame_rate))
        self.last_frame_time: float = time.time()
        self.frame_time_samples: list[float] = []  # For adaptive timing

        self.hide_creatures: bool = False
        self.hide_placeables: bool = False
        self.hide_doors: bool = False
        self.hide_triggers: bool = False
        self.hide_encounters: bool = False
        self.hide_waypoints: bool = False
        self.hide_sounds: bool = False
        self.hide_stores: bool = False
        self.hide_cameras: bool = False
        self.lock_instances: bool = False
        self.mouse_pos_history: list[Vector2] = [Vector2(0, 0), Vector2(0, 0)]

        from toolset.uic.qtpy.windows.module_designer import Ui_MainWindow

        self.ui: Ui_MainWindow = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Module Designer")  # Re-set after UI setup

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self._init_ui()
        self._install_view_stack()
        self._setup_signals()

        self.last_free_cam_time: float = 0.0  # Initialize the last toggle time

        self.material_colors: dict[SurfaceMaterial, QColor] = get_walkmesh_material_colors()

        self.ui.flatRenderer.material_colors = self.material_colors
        self.ui.flatRenderer.hide_walkmesh_edges = True
        self.ui.flatRenderer.highlight_boundaries = False
        self.ui.flatRenderer.show_room_boundaries = True
        self.ui.flatRenderer.show_grid = False

        # =====================================================================
        # Editor Mode State (Object / Layout / Walkmesh)
        # =====================================================================
        self._editor_mode: int = EditorMode.OBJECT

        # --- Indoor Builder State (Layout Mode) ---
        self._indoor_map: IndoorMap = IndoorMap()
        self._indoor_embedded_kit: EmbeddedKit = EmbeddedKit()
        self._indoor_kits: list[Kit] = []
        self._indoor_filepath: str = ""
        self._indoor_painting_walkmesh: bool = False
        self._indoor_colorize_materials: bool = True
        self._indoor_paint_stroke_active: bool = False
        self._indoor_paint_stroke_originals: dict[tuple[IndoorMapRoom, int], SurfaceMaterial] = {}
        self._indoor_paint_stroke_new: dict[tuple[IndoorMapRoom, int], SurfaceMaterial] = {}
        self._indoor_clipboard: list[RoomClipboardData] = []
        self._indoor_preview_source_image = None  # QImage | None
        self._indoor_vis_matrix: dict[int, set[int]] = {}
        self._indoor_vis_hover_row: int = -1
        self._indoor_vis_hover_col: int = -1

        # Module Kit Manager — provides implicit kits from existing game modules
        self._module_kit_manager: ModuleKitManager | None = None
        self._current_module_kit: ModuleKit | None = None
        if installation is not None:
            try:
                self._module_kit_manager = ModuleKitManager(installation)
            except Exception:
                self.log.warning("Failed to initialize ModuleKitManager, module kits will be unavailable")

        # --- Camera bookmarks (Ctrl+1..9 to save, 1..9 to recall) ---
        self._camera_bookmarks: dict[int, tuple[float, float, float, float, float, float]] = {}
        # tuple: (cam_x, cam_y, cam_z, rot_x, rot_y, rot_z) — populated by save action

        # --- Viewport shading cycle state ---
        # 0 = Lightmapped (default), 1 = Solid (no lightmap), 2 = Wireframe
        self._viewport_shading_mode: int = 0

        # --- Active tool (Select / Move / Rotate) ---
        self._active_tool: int = EditorTool.SELECT

        # Connect mode selector
        self.ui.modeSelector.currentIndexChanged.connect(self._on_mode_changed)
        # Start in Object mode — hide indoor-only UI elements
        self._apply_mode_visibility(EditorMode.OBJECT)

        # Wire tool palette buttons as a mutually exclusive group
        self._setup_tool_buttons()

        # --- Persistent status bar labels ---
        self._setup_status_bar()

        # --- Camera HUD overlay on 3D viewport ---
        self._setup_camera_hud()

        # --- Instance inspector panel ---
        self._setup_properties_panel()

        # --- Resource tree drag-and-drop ---
        self._setup_resource_dnd()

        # Setup indoor builder renderer
        self.ui.indoorRenderer.set_map(self._indoor_map)
        self.ui.indoorRenderer.set_undo_stack(self.undo_stack)
        self.ui.indoorRenderer.set_material_colors(self.material_colors)
        self.ui.indoorRenderer.set_colorize_materials(self._indoor_colorize_materials)

        # Setup indoor kit/module selectors
        self._setup_indoor_kits()
        self._setup_indoor_modules()
        self._setup_indoor_signals()
        self._setup_indoor_vis_matrix()
        self._populate_walkmesh_material_list()
        self._setup_walkmesh_face_panel()
        self._initialize_indoor_options()

        self._controls3d: ModuleDesignerControls3d | ModuleDesignerControlsFreeCam = ModuleDesignerControls3d(self, self.ui.mainRenderer)
        # self._controls3d: ModuleDesignerControls3d | ModuleDesignerControlsFreeCam = ModuleDesignerControlsFreeCam(self, self.ui.mainRenderer)  # Doesn't work when set in __init__, trigger this in onMousePressed
        self._controls2d: ModuleDesignerControls2d = ModuleDesignerControls2d(self, self.ui.flatRenderer)

        # LYT renderer for layout tab (2D LYT editing surface).
        self._lyt_renderer: LYTRenderer | None = LYTRenderer(parent=self)
        self._lyt_renderer.sig_element_selected.connect(self._on_lyt_renderer_element_selected)
        self._lyt_renderer.sig_element_moved.connect(self._on_lyt_renderer_element_moved)
        renderer_splitter = self.ui.mainRenderer.parentWidget()
        if isinstance(renderer_splitter, QSplitter):
            insert_before_flat = renderer_splitter.indexOf(self.ui.flatRenderer)
            if insert_before_flat < 0:
                insert_before_flat = 1
            renderer_splitter.insertWidget(insert_before_flat, self._lyt_renderer)
            self._lyt_renderer.setVisible(False)
        else:
            self.log.warning("Could not attach LYT renderer: parent splitter not found")

        if mod_filepath is None:  # Use singleShot timer so the ui window opens while the loading is happening.
            QTimer().singleShot(33, self.open_module_with_dialog)
        else:
            QTimer().singleShot(33, lambda: self.open_module(mod_filepath))

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        if installation is None:
            return
        self._installation = installation
        try:
            self._setup_indoor_modules()
            self._refresh_window_title()
        except Exception:
            self.log.exception("Failed to refresh after installation switch")

    def showEvent(self, a0: QShowEvent):
        if self.ui.mainRenderer._scene is None:  # noqa: SLF001
            return  # Don't show the window if the scene isn't ready, otherwise the gl context stuff will start prematurely.
        super().showEvent(a0)

    def closeEvent(self, event: QCloseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        from toolset.gui.common.localization import translate as tr

        # Only show confirmation dialog if there are unsaved changes
        if self.has_unsaved_changes():
            from toolset.gui.helpers.message_box import ask_question

            reply = ask_question(
                tr("Confirm Exit"),
                tr("Really quit the module designer? You may lose unsaved changes."),
                self,
            )

            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()  # Ignore the close event
                return

        # Stop Blender mode if active
        if self.is_blender_mode():
            self.stop_blender_mode()
        event.accept()  # Let the window close

    def _setup_signals(self):
        self.ui.actionOpen.triggered.connect(self.open_module_with_dialog)
        self.ui.actionSave.triggered.connect(self.save_git)
        self.ui.actionSettings.triggered.connect(self.open_settings_dialog)
        # QAction.triggered emits a bool; QWidget.close takes no args.
        self.ui.actionExit.triggered.connect(lambda *_: self.close())
        self.ui.actionInstructions.triggered.connect(self.show_help_window)

        self.ui.actionUndo.triggered.connect(self._on_undo)
        self.ui.actionRedo.triggered.connect(self._on_redo)

        # Connect undo stack signals for Blender sync and change tracking
        self.undo_stack.indexChanged.connect(self._on_undo_stack_changed)
        self.undo_stack.indexChanged.connect(self._on_undo_stack_index_changed)

        # Layout tab actions
        self.ui.actionAddRoom.triggered.connect(self.on_add_room)
        self.ui.actionAddDoorHook.triggered.connect(self.on_add_door_hook)
        self.ui.actionAddTrack.triggered.connect(self.on_add_track)
        self.ui.actionAddObstacle.triggered.connect(self.on_add_obstacle)
        self.ui.actionImportTexture.triggered.connect(self.on_import_texture)
        self.ui.actionGenerateWalkmesh.triggered.connect(self.on_generate_walkmesh)

        # Connect LYT editor signals to update UI
        self.ui.mainRenderer.sig_lyt_updated.connect(self.on_lyt_updated)

        self.ui.resourceTree.clicked.connect(self.on_resource_tree_single_clicked)
        self.ui.resourceTree.doubleClicked.connect(self.on_resource_tree_double_clicked)
        self.ui.resourceTree.customContextMenuRequested.connect(self.on_resource_tree_context_menu)
        self.ui.resourceSearchEdit.textChanged.connect(self._filter_resource_tree)

        instance_visibility_checkboxes = self._instance_visibility_checkboxes()
        for checkbox in instance_visibility_checkboxes:
            checkbox.toggled.connect(self.update_toggles)
        self.ui.backfaceCheck.toggled.connect(self.update_toggles)
        self.ui.lightmapCheck.toggled.connect(self.update_toggles)
        self.ui.cursorCheck.toggled.connect(self.update_toggles)
        self.ui.roomBoundariesCheck.toggled.connect(lambda value: setattr(self.ui.flatRenderer, "show_room_boundaries", value))
        self.ui.roomBoundariesCheck.toggled.connect(lambda _: self.ui.flatRenderer.update())
        self.ui.flatGridCheck.toggled.connect(lambda value: setattr(self.ui.flatRenderer, "show_grid", value))
        self.ui.flatGridCheck.toggled.connect(lambda _: self.ui.flatRenderer.update())

        for checkbox in instance_visibility_checkboxes:
            checkbox.mouseDoubleClickEvent = (  # type: ignore[method-assign]  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
                lambda _event, target_checkbox=checkbox: self.on_instance_visibility_double_click(target_checkbox)
            )

        self.ui.instanceTree.clicked.connect(self.on_instance_list_single_clicked)
        self.ui.instanceTree.doubleClicked.connect(self.on_instance_list_double_clicked)
        self.ui.instanceTree.customContextMenuRequested.connect(self.on_instance_list_right_clicked)
        self.ui.instanceSearchEdit.textChanged.connect(self._filter_instance_tree)

        self.ui.mainRenderer.sig_renderer_initialized.connect(self.on_3d_renderer_initialized)
        self.ui.mainRenderer.sig_scene_initialized.connect(self.on_3d_scene_initialized)
        self.ui.mainRenderer.sig_mouse_pressed.connect(self.on_3d_mouse_pressed)
        self.ui.mainRenderer.sig_mouse_released.connect(self.on_3d_mouse_released)
        self.ui.mainRenderer.sig_mouse_moved.connect(self.on_3d_mouse_moved)
        self.ui.mainRenderer.sig_mouse_scrolled.connect(self.on_3d_mouse_scrolled)
        self.ui.mainRenderer.sig_keyboard_pressed.connect(self.on_3d_keyboard_pressed)
        self.ui.mainRenderer.sig_object_selected.connect(self.on_3d_object_selected)
        self.ui.mainRenderer.sig_keyboard_released.connect(self.on_3d_keyboard_released)

        self.ui.flatRenderer.sig_mouse_pressed.connect(self.on_2d_mouse_pressed)
        self.ui.flatRenderer.sig_mouse_moved.connect(self.on_2d_mouse_moved)
        self.ui.flatRenderer.sig_mouse_scrolled.connect(self.on_2d_mouse_scrolled)
        self.ui.flatRenderer.sig_marquee_select.connect(self.on_2d_marquee_select)
        self.ui.flatRenderer.sig_key_pressed.connect(self.on_2d_keyboard_pressed)
        self.ui.flatRenderer.sig_mouse_released.connect(self.on_2d_mouse_released)
        self.ui.flatRenderer.sig_key_released.connect(self.on_2d_keyboard_released)

        # Layout tree signals
        self.ui.lytTree.itemSelectionChanged.connect(self.on_lyt_tree_selection_changed)
        self.ui.lytTree.customContextMenuRequested.connect(self.on_lyt_tree_context_menu)

        # Position/rotation spinbox signals
        self.ui.posXSpin.valueChanged.connect(self.on_room_position_changed)
        self.ui.posYSpin.valueChanged.connect(self.on_room_position_changed)
        self.ui.posZSpin.valueChanged.connect(self.on_room_position_changed)
        self.ui.rotXSpin.valueChanged.connect(self.on_room_rotation_changed)
        self.ui.rotYSpin.valueChanged.connect(self.on_room_rotation_changed)
        self.ui.rotZSpin.valueChanged.connect(self.on_room_rotation_changed)

        # Model edit signals
        self.ui.modelEdit.textChanged.connect(self.on_room_model_changed)
        self.ui.browseModelButton.clicked.connect(self.on_browse_model)

        # Door hook signals
        self.ui.roomNameCombo.currentTextChanged.connect(self.on_doorhook_room_changed)
        self.ui.doorNameEdit.textChanged.connect(self.on_doorhook_name_changed)

    # =========================================================================
    # Tool Palette
    # =========================================================================

    def _setup_tool_buttons(self):
        """Create a mutually-exclusive button group for Select / Move / Rotate."""
        from qtpy.QtWidgets import QButtonGroup  # noqa: PLC0415

        self._tool_button_group = QButtonGroup(self)
        self._tool_button_group.setExclusive(True)
        self._tool_button_group.addButton(self.ui.toolSelectBtn, EditorTool.SELECT)
        self._tool_button_group.addButton(self.ui.toolMoveBtn, EditorTool.MOVE)
        self._tool_button_group.addButton(self.ui.toolRotateBtn, EditorTool.ROTATE)

        self.ui.toolSelectBtn.clicked.connect(lambda: self._set_active_tool(EditorTool.SELECT))
        self.ui.toolMoveBtn.clicked.connect(lambda: self._set_active_tool(EditorTool.MOVE))
        self.ui.toolRotateBtn.clicked.connect(lambda: self._set_active_tool(EditorTool.ROTATE))

    def _set_active_tool(self, tool: int):
        """Switch the active manipulation tool and update the toolbar state."""
        self._active_tool = tool
        # Ensure the matching button is visually checked
        self.ui.toolSelectBtn.setChecked(tool == EditorTool.SELECT)
        self.ui.toolMoveBtn.setChecked(tool == EditorTool.MOVE)
        self.ui.toolRotateBtn.setChecked(tool == EditorTool.ROTATE)
        tool_names = {EditorTool.SELECT: "Select", EditorTool.MOVE: "Move", EditorTool.ROTATE: "Rotate"}
        self._show_status_message(f"Tool: {tool_names.get(tool, 'Unknown')}")
        self._update_status_bar()

    # =========================================================================
    # Status Bar
    # =========================================================================

    def _setup_status_bar(self):
        """Add persistent labels to the status bar showing mode, tool, and selection info."""
        from qtpy.QtWidgets import QLabel  # noqa: PLC0415

        self._status_mode_label = QLabel("Mode: Object")
        self._status_tool_label = QLabel("Tool: Select")
        self._status_selection_label = QLabel("Selected: 0")

        bar = self.statusBar()
        bar.addPermanentWidget(self._status_mode_label)
        bar.addPermanentWidget(self._status_tool_label)
        bar.addPermanentWidget(self._status_selection_label)
        self._update_status_bar()

    def _update_status_bar(self):
        """Refresh the persistent status bar labels from current state."""
        mode_names = {EditorMode.OBJECT: "Object", EditorMode.LAYOUT: "Layout", EditorMode.WALKMESH: "Walkmesh"}
        tool_names = {EditorTool.SELECT: "Select", EditorTool.MOVE: "Move", EditorTool.ROTATE: "Rotate"}
        self._status_mode_label.setText(f"  Mode: {mode_names.get(self._editor_mode, '?')}  ")
        self._status_tool_label.setText(f"  Tool: {tool_names.get(self._active_tool, '?')}  ")
        sel_count = len(self.selected_instances) if hasattr(self, "selected_instances") else 0
        self._status_selection_label.setText(f"  Selected: {sel_count}  ")
        self._sync_object_gizmo()

    def _object_gizmo_world_position(self) -> Vector3 | None:
        if not self.selected_instances:
            return None
        inst = self.selected_instances[0]
        return Vector3(inst.position.x, inst.position.y, inst.position.z)

    def _sync_object_gizmo(self) -> None:
        can_show = (
            self._editor_mode == EditorMode.OBJECT
            and self._active_tool in (EditorTool.MOVE, EditorTool.ROTATE)
            and bool(self.selected_instances)
            and not self.ui.lockInstancesCheck.isChecked()
        )
        if not can_show:
            self.ui.mainRenderer.set_object_gizmo(None)
            return

        position = self._object_gizmo_world_position()
        mode = "rotate" if self._active_tool == EditorTool.ROTATE else "translate"
        self.ui.mainRenderer.set_object_gizmo(position, mode=mode, drag_axis=self._object_gizmo_drag_axis)

    def _invalidate_scene_and_update_renderers(self, update_flat: bool = False) -> None:
        """Invalidate the main renderer's scene cache and update all affected renderers.

        This is a common pattern throughout the module designer: after modifying geometry,
        we need to invalidate the scene cache and trigger a re-render.

        Args:
            update_flat: If True, also update the flat renderer in addition to main renderer.
        """
        scene = self.ui.mainRenderer._scene  # noqa: SLF001
        if scene is not None:
            scene.invalidate_cache()
        self.ui.mainRenderer.update()
        if update_flat:
            self.ui.flatRenderer.update()

    def _begin_object_gizmo_drag(self, axis: str) -> None:
        if axis not in ("x", "y", "z") or not self.selected_instances:
            return

        self._object_gizmo_drag_active = True
        self._object_gizmo_drag_axis = axis
        anchor = self.ui.mainRenderer._mouse_world
        self._object_gizmo_drag_anchor = Vector3(anchor.x, anchor.y, anchor.z)
        self.transform_state.initial_positions = {instance: Vector3(instance.position.x, instance.position.y, instance.position.z) for instance in self.selected_instances}
        self.transform_state.is_drag_moving = True
        self._sync_object_gizmo()

    def _update_object_gizmo_drag(self, world: Vector3) -> None:
        if not self._object_gizmo_drag_active:
            return
        axis = self._object_gizmo_drag_axis
        anchor = self._object_gizmo_drag_anchor
        if axis not in ("x", "y", "z") or anchor is None:
            return

        delta_x = world.x - anchor.x
        delta_y = world.y - anchor.y
        delta_z = world.z - anchor.z
        for instance, initial in self.transform_state.initial_positions.items():
            new_x = initial.x
            new_y = initial.y
            new_z = initial.z
            if axis == "x":
                new_x = initial.x + delta_x
            elif axis == "y":
                new_y = initial.y + delta_y
            elif axis == "z":
                new_z = initial.z + delta_z

            if self.ui.snapCheck.isChecked():
                new_x = self._snap_to_grid(new_x)
                new_y = self._snap_to_grid(new_y)
                new_z = self._snap_to_grid(new_z)

            instance.position = Vector3(new_x, new_y, new_z)

        self._invalidate_scene_and_update_renderers()
        self._update_properties_panel()
        self._sync_object_gizmo()

    def _end_object_gizmo_drag(self) -> None:
        if not self._object_gizmo_drag_active:
            return
        self._object_gizmo_drag_active = False
        self._object_gizmo_drag_anchor = None
        self._object_gizmo_drag_axis = None
        self._sync_object_gizmo()

    def _begin_object_rotate_gizmo_drag(self, axis: str, screen: Vector2) -> None:
        if axis not in ("x", "y", "z") or not self.selected_instances:
            return

        position = self._object_gizmo_world_position()
        center = self.ui.mainRenderer._project_world_to_screen(position) if position is not None else None
        if center is None:
            return

        self._object_rotate_gizmo_drag_active = True
        self._object_gizmo_drag_axis = axis
        self._object_rotate_gizmo_anchor_angle = math.atan2(screen.y - center.y(), screen.x - center.x())
        self._object_rotate_gizmo_last_angle = 0.0
        self.transform_state.initial_rotations = {}
        for instance in self.selected_instances:
            self._capture_initial_rotation_for_transform(instance)

        self.transform_state.is_drag_rotating = True
        self._sync_object_gizmo()

    def _update_object_rotate_gizmo_drag(self, screen: Vector2) -> None:
        if not self._object_rotate_gizmo_drag_active:
            return
        axis = self._object_gizmo_drag_axis
        anchor_angle = self._object_rotate_gizmo_anchor_angle
        if axis not in ("x", "y", "z") or anchor_angle is None:
            return

        position = self._object_gizmo_world_position()
        center = self.ui.mainRenderer._project_world_to_screen(position) if position is not None else None
        if center is None:
            return

        current_angle = math.atan2(screen.y - center.y(), screen.x - center.x())
        delta_angle = current_angle - anchor_angle
        delta_angle = math.atan2(math.sin(delta_angle), math.cos(delta_angle))

        delta_angle = snap_radians(
            delta_angle,
            self.ui.rotSnapDegreeSpin.value(),
            enabled=self.ui.rotSnapCheck.isChecked(),
        )

        step = delta_angle - self._object_rotate_gizmo_last_angle
        if abs(step) <= 1e-6:
            return

        for instance in self.selected_instances:
            if isinstance(instance, GITCamera):
                yaw = step if axis == "z" else 0.0
                pitch = step if axis == "x" else 0.0
                roll = step if axis == "y" else 0.0
                instance.rotate(yaw, pitch, roll)
            elif isinstance(instance, (GITCreature, GITDoor, GITPlaceable, GITStore, GITWaypoint)):
                instance.rotate(step, 0.0, 0.0)

        self._object_rotate_gizmo_last_angle = delta_angle
        self._invalidate_scene_and_update_renderers()
        self._update_properties_panel()
        self._sync_object_gizmo()

    def _end_object_rotate_gizmo_drag(self) -> None:
        if not self._object_rotate_gizmo_drag_active:
            return
        self._object_rotate_gizmo_drag_active = False
        self._object_rotate_gizmo_anchor_angle = None
        self._object_rotate_gizmo_last_angle = 0.0
        self._object_gizmo_drag_axis = None
        self._sync_object_gizmo()

    # =========================================================================
    # Camera HUD Overlay
    # =========================================================================

    def _setup_camera_hud(self):
        """Create a translucent HUD overlay on the 3D viewport showing camera coordinates."""
        from qtpy.QtCore import QTimer  # noqa: PLC0415
        from qtpy.QtWidgets import QLabel  # noqa: PLC0415

        self._camera_hud = QLabel(self.ui.mainRenderer)
        self._camera_hud.setStyleSheet(
            "QLabel {"
            "  background-color: rgba(0, 0, 0, 160);"
            "  color: #cccccc;"
            "  font-family: Consolas, 'Courier New', monospace;"
            "  font-size: 10px;"
            "  padding: 4px 8px;"
            "  border-bottom-right-radius: 4px;"
            "}"
        )
        self._camera_hud.move(0, 0)
        self._camera_hud.setText("Camera: --")
        self._camera_hud.adjustSize()
        self._camera_hud.show()

        # Update every 200ms — lightweight, doesn't block render loop
        self._camera_hud_timer = QTimer(self)
        self._camera_hud_timer.timeout.connect(self._update_camera_hud)
        self._camera_hud_timer.start(200)

    def _update_camera_hud(self):
        """Refresh camera HUD text from current 3D scene camera."""
        scene = self.ui.mainRenderer._scene if hasattr(self.ui.mainRenderer, "_scene") else None
        if scene is None or not hasattr(scene, "camera"):
            return
        cam = scene.camera
        self._camera_hud.setText(f"X: {cam.x:8.2f}  Y: {cam.y:8.2f}  Z: {cam.z:8.2f}\n" f"Pitch: {cam.pitch:6.1f}  Yaw: {cam.yaw:6.1f}  Dist: {cam.distance:6.1f}")
        self._camera_hud.adjustSize()

    # =========================================================================
    # Instance Inspector Panel
    # =========================================================================

    def _setup_properties_panel(self):
        """Wire up instance inspector panel signals and initialize."""
        self._inspector_updating = False
        self.ui.propXSpin.valueChanged.connect(self._on_inspector_position_changed)
        self.ui.propYSpin.valueChanged.connect(self._on_inspector_position_changed)
        self.ui.propZSpin.valueChanged.connect(self._on_inspector_position_changed)
        self.ui.propBearingSpin.valueChanged.connect(self._on_inspector_bearing_changed)
        self.ui.propOpenBlueprintBtn.clicked.connect(self._on_inspector_open_blueprint)
        self._update_properties_panel()

    def _update_properties_panel(self):
        """Refresh inspector panel from current selection."""
        if not hasattr(self, "_inspector_updating"):
            return
        self._inspector_updating = True
        try:
            if not hasattr(self, "selected_instances") or not self.selected_instances:
                self.ui.propertiesGroup.setEnabled(False)
                self.ui.propResRefValue.setText("\u2014")
                self.ui.propTypeValue.setText("\u2014")
                self.ui.propXSpin.setValue(0.0)
                self.ui.propYSpin.setValue(0.0)
                self.ui.propZSpin.setValue(0.0)
                self.ui.propBearingSpin.setValue(0.0)
                return
            inst = self.selected_instances[0]
            self.ui.propertiesGroup.setEnabled(True)
            resref = str(getattr(inst, "resref", "\u2014") or "\u2014")
            self.ui.propResRefValue.setText(resref)
            type_name = type(inst).__name__.replace("GIT", "")
            self.ui.propTypeValue.setText(type_name)
            self.ui.propXSpin.setValue(inst.position.x)
            self.ui.propYSpin.setValue(inst.position.y)
            self.ui.propZSpin.setValue(inst.position.z)
            bearing = getattr(inst, "bearing", 0.0)
            self.ui.propBearingSpin.setValue(math.degrees(float(bearing)))
            has_bearing = hasattr(inst, "bearing")
            self.ui.propBearingSpin.setEnabled(has_bearing)
        finally:
            self._inspector_updating = False

    def _on_inspector_position_changed(self):
        """Handle XYZ spinbox changes from the inspector panel."""
        if not hasattr(self, "_inspector_updating") or self._inspector_updating:
            return
        if not self.selected_instances:
            return
        inst = self.selected_instances[0]
        old_pos = Vector3(inst.position.x, inst.position.y, inst.position.z)
        new_pos = Vector3(
            self.ui.propXSpin.value(),
            self.ui.propYSpin.value(),
            self.ui.propZSpin.value(),
        )
        self.undo_stack.push(MoveCommand(inst, old_pos, new_pos))
        inst.position = new_pos
        self._invalidate_scene_and_update_renderers()

    def _on_inspector_bearing_changed(self):
        """Handle bearing spinbox changes from the inspector panel."""
        if not hasattr(self, "_inspector_updating") or self._inspector_updating:
            return
        if not self.selected_instances:
            return
        inst = self.selected_instances[0]
        if not hasattr(inst, "bearing"):
            return
        inst.bearing = math.radians(self.ui.propBearingSpin.value())
        self._invalidate_scene_and_update_renderers()

    def _on_inspector_open_blueprint(self):
        """Open the blueprint editor for the selected instance."""
        if not self.selected_instances:
            return
        self.edit_instance(self.selected_instances[0])

    # =========================================================================
    # Resource Tree Drag-and-Drop
    # =========================================================================

    def _setup_resource_dnd(self) -> None:
        """Enable drag from the resource tree; accept drops on the 3D viewport."""
        self._dragged_resource: ModuleResource | None = None
        # Enable dragging items from the resource tree
        self.ui.resourceTree.setDragEnabled(True)
        self.ui.resourceTree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        # Track which resource is being dragged
        self.ui.resourceTree.itemPressed.connect(self._on_resource_tree_item_pressed)
        # Accept drops on the 3D renderer
        self.ui.mainRenderer.setAcceptDrops(True)
        self.ui.mainRenderer.installEventFilter(self)

    def _on_resource_tree_item_pressed(self, item: QTreeWidgetItem) -> None:
        """Cache the ModuleResource when the user begins pressing an item (pre-drag)."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ModuleResource):
            self._dragged_resource = data
        else:
            self._dragged_resource = None

    def _update_resource_drop_preview(self, resource: ModuleResource, screen_pos: QPoint) -> None:
        """Update ghost placement preview for the currently dragged resource."""
        git_class = _RESTYPE_TO_GIT_CLASS.get(resource.restype())
        if git_class is None:
            self.ui.mainRenderer.set_drop_preview(None)
            return

        scene = self.ui.mainRenderer._scene
        if scene is None:
            self.ui.mainRenderer.set_drop_preview(None)
            return

        try:
            world_pos = scene.screen_to_world_from_depth_buffer(screen_pos.x(), screen_pos.y())
        except Exception:  # noqa: BLE001
            world_pos = Vector3(scene.cursor.position().x, scene.cursor.position().y, scene.cursor.position().z)

        if issubclass(git_class, (GITCreature, GITWaypoint)):
            world_pos = self.ui.mainRenderer.walkmesh_point(world_pos.x, world_pos.y, world_pos.z)

        label = f"{resource.resname().upper()}.{resource.restype().extension.upper()}"
        self.ui.mainRenderer.set_drop_preview(world_pos, label)

    @staticmethod
    def _external_asset_urls(event: QEvent) -> list[Path]:
        mime_data = event.mimeData() if hasattr(event, "mimeData") else None  # type: ignore[call-arg]
        if mime_data is None or not mime_data.hasUrls():
            return []
        urls = []
        for url in mime_data.urls():
            if url.isLocalFile():
                urls.append(Path(url.toLocalFile()))
        return urls

    @staticmethod
    def _is_supported_external_asset(path: Path) -> bool:
        supported_suffixes = {".obj", ".fbx", ".gltf", ".glb", ".dae", ".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp", ".webp"}
        return path.suffix.lower() in supported_suffixes

    def _handle_external_asset_drop(self, file_paths: list[Path]) -> bool:
        if not self._is_blender_mode_enabled() or self._blender_controller is None:
            return False

        imported_assets = 0
        for file_path in file_paths:
            if not file_path.is_file() or not self._is_supported_external_asset(file_path):
                continue
            result = self._blender_controller.import_external_asset(str(file_path))
            if result is not None:
                imported_assets += 1

        if imported_assets:
            self._show_status_message(f"Imported {imported_assets} external asset(s) into Blender.", 4000)
            return True
        return False

    def eventFilter(self, obj: object, event: QEvent) -> bool:  # type: ignore[override]
        """Intercept drag-and-drop events on the 3D renderer."""
        if obj is self.ui.mainRenderer:
            etype = event.type()
            if etype in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                if self._dragged_resource is not None:
                    drag_event = event  # type: ignore[assignment]
                    self._update_resource_drop_preview(self._dragged_resource, drag_event.pos())  # type: ignore[union-attr]
                    event.acceptProposedAction()  # type: ignore[union-attr]
                    return True
                external_assets = self._external_asset_urls(event)
                if external_assets and any(self._is_supported_external_asset(path) for path in external_assets):
                    event.acceptProposedAction()  # type: ignore[union-attr]
                    return True
            elif etype == QEvent.Type.Drop:
                if self._dragged_resource is not None:
                    drop_event = event  # type: ignore[assignment]
                    pos = drop_event.pos()  # type: ignore[union-attr]
                    self._handle_resource_drop(self._dragged_resource, pos)
                    self._dragged_resource = None
                    self.ui.mainRenderer.set_drop_preview(None)
                    event.acceptProposedAction()  # type: ignore[union-attr]
                    return True
                external_assets = self._external_asset_urls(event)
                if external_assets and self._handle_external_asset_drop(external_assets):
                    event.acceptProposedAction()  # type: ignore[union-attr]
                    return True
            elif etype == QEvent.Type.DragLeave:
                self._dragged_resource = None
                self.ui.mainRenderer.set_drop_preview(None)
        elif obj is self.ui.visMatrix.viewport() and event.type() == QEvent.Type.Leave:
            self._indoor_vis_hover_row = -1
            self._indoor_vis_hover_col = -1
            self._apply_indoor_vis_hover_highlight()
        return super().eventFilter(obj, event)  # type: ignore[arg-type]

    def _handle_resource_drop(self, resource: ModuleResource, screen_pos: QPoint) -> None:
        """Spawn a new GIT instance for *resource* at the world position under *screen_pos*.

        If the resource type does not map to a spawnable GIT class (e.g. items), this is a no-op.
        """
        git_class = _RESTYPE_TO_GIT_CLASS.get(resource.restype())
        if git_class is None:
            self._show_status_message(f"Cannot spawn '{resource.restype()}' resources as GIT instances.", 3000)
            return

        # Determine world position: try depth-buffer first, fall back to scene cursor
        world_pos = Vector3(0.0, 0.0, 0.0)
        scene = self.ui.mainRenderer._scene
        if scene is not None:
            try:
                world_pos = scene.screen_to_world_from_depth_buffer(screen_pos.x(), screen_pos.y())
            except Exception:  # noqa: BLE001
                world_pos = Vector3(scene.cursor.position().x, scene.cursor.position().y, scene.cursor.position().z)

        # Create instance, pre-set its resref so InsertInstanceDialog can auto-select it
        instance: GITInstance = git_class(world_pos.x, world_pos.y, world_pos.z)
        instance.resref = ResRef(resource.resname())  # type: ignore[union-attr]

        # add_instance will show InsertInstanceDialog so the user confirms / picks location
        # Pass walkmesh_snap=True so creatures land on surfaces correctly
        walkmesh_snap = isinstance(instance, (GITCreature, GITWaypoint))
        self.add_instance(instance, walkmesh_snap=walkmesh_snap)

    # =========================================================================
    # Editor Mode Switching
    # =========================================================================

    def _instance_visibility_checkboxes(self) -> tuple[QCheckBox, ...]:
        """Return all GIT-type visibility toggle checkboxes in UI order."""
        return (
            self.ui.viewCreatureCheck,
            self.ui.viewPlaceableCheck,
            self.ui.viewDoorCheck,
            self.ui.viewSoundCheck,
            self.ui.viewTriggerCheck,
            self.ui.viewEncounterCheck,
            self.ui.viewWaypointCheck,
            self.ui.viewCameraCheck,
            self.ui.viewStoreCheck,
        )

    def _hidden_instance_class_mapping(self) -> dict[type[GITInstance], bool]:
        """Map GIT instance classes to whether they are currently hidden in UI."""
        return {
            GITCreature: self.hide_creatures,
            GITPlaceable: self.hide_placeables,
            GITDoor: self.hide_doors,
            GITTrigger: self.hide_triggers,
            GITEncounter: self.hide_encounters,
            GITWaypoint: self.hide_waypoints,
            GITSound: self.hide_sounds,
            GITStore: self.hide_stores,
            GITCamera: self.hide_cameras,
            GITInstance: False,
        }

    def _on_mode_changed(self, index: int):
        """Handle mode selector combo box change."""
        self._editor_mode = index
        if index != EditorMode.WALKMESH:
            self._clear_selected_walkmesh_face()
        self._apply_mode_visibility(index)
        self._update_status_bar()

    def _apply_mode_visibility(self, mode: int):
        """Show/hide UI elements based on the active editor mode.

        This is the key mechanism to prevent the UI from being "squished" —
        each mode only shows its relevant panels and renderers.
        """
        is_object = mode == EditorMode.OBJECT
        is_layout = mode == EditorMode.LAYOUT
        is_walkmesh = mode == EditorMode.WALKMESH

        # --- Top toolbar filter checkboxes (GIT-object specific) ---
        # These checkboxes (creature/door/placeable/etc. toggles) only apply to Object mode
        git_toggle_widgets = self._instance_visibility_checkboxes()
        for w in git_toggle_widgets:
            w.setVisible(is_object)

        # --- Left panel tab visibility ---
        # Show only the tabs relevant to the active mode to save space.
        # resourceTab and lytTab are shared (always visible).
        # walkmeshTab is visible in Walkmesh mode (and partially in Layout for painting).
        # visTab is visible in Layout + Object modes.
        left = self.ui.leftPanel
        for i in range(left.count()):
            tab_name = left.widget(i).objectName() if left.widget(i) else ""
            if tab_name == "walkmeshTab":
                left.setTabVisible(i, is_walkmesh or is_layout)
            elif tab_name == "visTab":
                left.setTabVisible(i, is_layout or is_object)
            # resourceTab and lytTab always visible

        # Switch to the most relevant tab
        if is_layout:
            self._switch_left_panel_to("lytTab")
        elif is_walkmesh:
            self._switch_left_panel_to("walkmeshTab")
        else:
            self._switch_left_panel_to("resourceTab")

        # --- Renderer visibility ---
        # Keep 3D/2D renderers available in all modes so Layout mode doesn't blank out.
        # Indoor renderer is additive in Layout mode (legacy indoor builder canvas).
        self.ui.mainRenderer.setVisible(True)
        self.ui.flatRenderer.setVisible(True)
        self.ui.indoorRenderer.setVisible(is_layout)
        lyt_renderer = getattr(self, "_lyt_renderer", None)
        if lyt_renderer is not None:
            lyt_renderer.setVisible(is_layout)

        if is_walkmesh and not self._last_walkmeshes:
            self.on_generate_walkmesh()

        # --- Right panel ---
        # instancesTab is for Object mode; layoutTab is for Layout mode
        self.ui.rightPanel.setVisible(is_object or is_layout)
        if is_object:
            self._switch_right_panel_to("instancesTab")
        elif is_layout:
            self._switch_right_panel_to("layoutTab")

        # --- Tool palette buttons ---
        # Select/Move/Rotate tools only make sense in Object or Walkmesh mode
        tool_visible = is_object or is_walkmesh
        self.ui.toolSelectBtn.setVisible(tool_visible)
        self.ui.toolMoveBtn.setVisible(tool_visible)
        self.ui.toolRotateBtn.setVisible(tool_visible)
        self.ui.toolSeparator.setVisible(tool_visible)
        self.ui.snapCheck.setVisible(tool_visible)
        self.ui.snapSizeSpin.setVisible(tool_visible)
        self.ui.rotSnapCheck.setVisible(tool_visible)
        self.ui.rotSnapDegreeSpin.setVisible(tool_visible)
        self.ui.snapSeparator.setVisible(tool_visible)

    def _switch_left_panel_to(self, tab_object_name: str):
        """Switch left panel to a specific tab by its objectName."""
        left = self.ui.leftPanel
        for i in range(left.count()):
            widget = left.widget(i)
            if widget is not None and widget.objectName() == tab_object_name:
                left.setCurrentIndex(i)
                return

    def _switch_right_panel_to(self, tab_object_name: str):
        """Switch right panel to a specific tab by its objectName."""
        right = self.ui.rightPanel
        for i in range(right.count()):
            widget = right.widget(i)
            if widget is not None and widget.objectName() == tab_object_name:
                right.setCurrentIndex(i)
                return

    @property
    def editor_mode(self) -> int:
        return self._editor_mode

    # =========================================================================
    # Indoor Builder Setup (Layout Mode)
    # =========================================================================

    def _setup_indoor_kits(self):
        """Load indoor kits from disk into the kit selector combo."""
        from toolset.gui.windows.indoor_builder.builder import get_kits_path

        kits_path = get_kits_path()
        try:
            self._indoor_kits = indoorkit_tools.load_kits(str(kits_path))
        except Exception:
            self.log.warning("Failed to load indoor kits from %s", kits_path)
            self._indoor_kits = []

        self.ui.kitSelect.clear()
        for kit in self._indoor_kits:
            self.ui.kitSelect.addItem(kit.name, kit)

    def _setup_indoor_modules(self):
        """Populate the module kit selector with available game modules."""
        try:
            populate_module_root_combobox(self.ui.moduleKitSelect, self._module_kit_manager)
        except Exception:
            self.log.warning("Failed to populate module kit list")

    def _setup_indoor_signals(self):
        """Connect signals for indoor builder controls in the Layout tab."""
        # Kit/component selection
        self.ui.kitSelect.currentIndexChanged.connect(self._on_indoor_kit_selected)
        self.ui.componentList.currentItemChanged.connect(self._on_indoor_component_selected)

        # Module kit selection
        self.ui.moduleKitSelect.currentIndexChanged.connect(self._on_module_kit_selected)
        self.ui.moduleComponentList.currentItemChanged.connect(self._on_module_component_selected)

        connect_indoor_option_signals(
            snap_to_grid_check=self.ui.snapToGridCheck,
            snap_to_hooks_check=self.ui.snapToHooksCheck,
            show_grid_check=self.ui.showGridCheck,
            show_hooks_check=self.ui.showHooksCheck,
            grid_size_spin=self.ui.gridSizeSpin,
            rotation_snap_spin=self.ui.rotSnapSpin,
            set_snap_to_grid=self.ui.indoorRenderer.set_snap_to_grid,
            set_snap_to_hooks=self.ui.indoorRenderer.set_snap_to_hooks,
            set_show_grid=self.ui.indoorRenderer.set_show_grid,
            set_hide_magnets=self.ui.indoorRenderer.set_hide_magnets,
            set_grid_size=self.ui.indoorRenderer.set_grid_size,
            set_rotation_snap=self.ui.indoorRenderer.set_rotation_snap,
        )

        connect_indoor_paint_control_signals(
            enable_paint_check=self.ui.enablePaintCheck,
            colorize_check=self.ui.colorizeMaterialsCheck,
            reset_button=self.ui.resetPaintButton,
            on_toggle_paint=self._toggle_indoor_paint_mode,
            on_toggle_colorize=self._toggle_indoor_colorize,
            on_reset_paint=self._reset_indoor_walkmesh_paint,
        )

        # Build button
        self.ui.buildIndoorButton.clicked.connect(self._build_indoor_module)

        connect_indoor_renderer_signals(
            self.ui.indoorRenderer,
            on_context_menu=self._on_indoor_context_menu,
            on_mouse_moved=self._on_indoor_mouse_moved,
            on_mouse_pressed=self._on_indoor_mouse_pressed,
            on_mouse_released=self._on_indoor_mouse_released,
            on_mouse_scrolled=self._on_indoor_mouse_scrolled,
            on_mouse_double_clicked=self._on_indoor_mouse_double_clicked,
            on_rooms_moved=self._on_indoor_rooms_moved,
            on_rooms_rotated=self._on_indoor_rooms_rotated,
            on_warp_moved=self._on_indoor_warp_moved,
        )

    def _setup_indoor_vis_matrix(self):
        """Connect and initialize the VIS matrix editor tab."""
        if not hasattr(self.ui, "visOverlayCheck"):
            self.ui.visOverlayCheck = QCheckBox("Show Overlay", self.ui.visTab)
            self.ui.visOverlayCheck.setObjectName("visOverlayCheck")
            self.ui.visOverlayCheck.setChecked(True)
            self.ui.visButtonsLayout.insertWidget(0, self.ui.visOverlayCheck)

        if not hasattr(self.ui, "visOverlayLegendLabel"):
            self.ui.visOverlayLegendLabel = QLabel(
                "Legend: solid cyan = bidirectional, dashed amber + arrow = one-way",
                self.ui.visTab,
            )
            self.ui.visOverlayLegendLabel.setObjectName("visOverlayLegendLabel")
            self.ui.visOverlayLegendLabel.setWordWrap(True)
            self.ui.visOverlayLegendLabel.setToolTip(
                "VIS overlay semantics:\n" "• Solid cyan line: both rooms see each other\n" "• Dashed amber line with arrow: one-way visibility"
            )
            self.ui.visButtonsLayout.insertWidget(1, self.ui.visOverlayLegendLabel)

        self.ui.visMatrix.itemChanged.connect(self._on_indoor_vis_item_changed)
        self.ui.visMatrix.itemEntered.connect(self._on_indoor_vis_item_hovered)
        self.ui.visMatrix.setMouseTracking(True)
        self.ui.visMatrix.viewport().installEventFilter(self)
        self.ui.visMatrix.setToolTip("Directional VIS matrix: rows are source rooms, columns are destination rooms.")
        self.ui.visSetAllButton.clicked.connect(self._set_all_indoor_vis_visible)
        self.ui.visClearAllButton.clicked.connect(self._clear_all_indoor_vis)
        self.ui.visOverlayCheck.toggled.connect(self._on_indoor_vis_overlay_toggled)
        self.ui.indoorRenderer.set_show_vis_overlay(self.ui.visOverlayCheck.isChecked())
        self.ui.mainRenderer.set_show_vis_overlay(self.ui.visOverlayCheck.isChecked())
        self._refresh_indoor_vis_matrix()

    def _on_indoor_vis_overlay_toggled(self, enabled: bool):
        self.ui.indoorRenderer.set_show_vis_overlay(enabled)
        self.ui.mainRenderer.set_show_vis_overlay(enabled)

    def _sync_main_renderer_vis_overlay(self) -> None:
        room_positions: dict[int, Vector3] = {id(room): Vector3(room.position.x, room.position.y, room.position.z) for room in self._indoor_map.rooms}
        self.ui.mainRenderer.set_vis_overlay_data(room_positions, self._indoor_vis_matrix)

    def _sync_indoor_vis_matrix(self):
        """Keep VIS matrix state aligned with current room list while preserving directionality."""
        room_ids = [id(room) for room in self._indoor_map.rooms]
        valid_ids = set(room_ids)

        for room_id in room_ids:
            if room_id not in self._indoor_vis_matrix:
                self._indoor_vis_matrix[room_id] = {other_id for other_id in room_ids if other_id != room_id}

        stale_rows = [room_id for room_id in self._indoor_vis_matrix if room_id not in valid_ids]
        for stale_room_id in stale_rows:
            self._indoor_vis_matrix.pop(stale_room_id, None)

        for room_id in room_ids:
            visible_set = self._indoor_vis_matrix.setdefault(room_id, set())
            visible_set.intersection_update(valid_ids)
            visible_set.discard(room_id)

    def _indoor_room_label(self, room: IndoorMapRoom, index: int) -> str:
        return f"{index}: {room.component.name}"

    def _refresh_indoor_vis_matrix(self):
        """Rebuild the VIS matrix widget from current room visibility state."""
        matrix = self.ui.visMatrix
        rooms = self._indoor_map.rooms
        self._sync_indoor_vis_matrix()
        self.ui.indoorRenderer.set_vis_matrix(self._indoor_vis_matrix)
        self._sync_main_renderer_vis_overlay()

        matrix.blockSignals(True)
        matrix.clear()

        if not rooms:
            matrix.setColumnCount(1)
            matrix.setHeaderLabels(["From \\ To"])
            matrix.blockSignals(False)
            return

        headers = ["From \\ To", *[self._indoor_room_label(room, index) for index, room in enumerate(rooms)]]
        matrix.setColumnCount(len(headers))
        matrix.setHeaderLabels(headers)

        for row_index, room in enumerate(rooms):
            room_id = id(room)
            item = QTreeWidgetItem(matrix)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            source_label = self._indoor_room_label(room, row_index)
            item.setText(0, source_label)
            item.setToolTip(0, f"Source room for this row: {source_label}")
            visible_set = self._indoor_vis_matrix.get(room_id, set())

            for col_index, target_room in enumerate(rooms, start=1):
                target_id = id(target_room)
                target_label = self._indoor_room_label(target_room, col_index - 1)
                if target_id == room_id:
                    item.setText(col_index, "—")
                    item.setCheckState(col_index, Qt.CheckState.Unchecked)
                    item.setToolTip(col_index, "Self-visibility is not editable")
                    continue
                item.setCheckState(col_index, Qt.CheckState.Checked if target_id in visible_set else Qt.CheckState.Unchecked)
                item.setToolTip(col_index, f"{source_label} -> {target_label}")

        matrix.resizeColumnToContents(0)
        self._apply_indoor_vis_hover_highlight()
        matrix.blockSignals(False)

    def _on_indoor_vis_item_hovered(self, item: QTreeWidgetItem, column: int):
        matrix = self.ui.visMatrix
        self._indoor_vis_hover_row = matrix.indexOfTopLevelItem(item)
        self._indoor_vis_hover_col = column - 1
        self._apply_indoor_vis_hover_highlight()

    def _apply_indoor_vis_hover_highlight(self):
        matrix = self.ui.visMatrix
        row_count = matrix.topLevelItemCount()
        if row_count <= 0:
            return

        base_background = matrix.palette().base().color()
        row_highlight = base_background.lighter(112)
        col_highlight = base_background.lighter(118)
        intersection_highlight = base_background.lighter(128)

        for row in range(row_count):
            row_item = matrix.topLevelItem(row)
            if row_item is None:
                continue
            for col in range(matrix.columnCount()):
                color = base_background
                if row == self._indoor_vis_hover_row:
                    color = row_highlight
                if col > 0 and (col - 1) == self._indoor_vis_hover_col:
                    color = intersection_highlight if row == self._indoor_vis_hover_row else col_highlight
                row_item.setBackground(col, QBrush(color))

    def _set_indoor_vis_pair(self, src_room_id: int, dst_room_id: int, visible: bool):
        """Set directional visibility from source room to destination room."""
        if src_room_id == dst_room_id:
            return

        src_set = self._indoor_vis_matrix.setdefault(src_room_id, set())
        if visible:
            src_set.add(dst_room_id)
            return
        src_set.discard(dst_room_id)

    def _on_indoor_vis_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle checkbox changes in the VIS matrix widget."""
        if column <= 0:
            return

        matrix = self.ui.visMatrix
        row_index = matrix.indexOfTopLevelItem(item)
        col_room_index = column - 1
        rooms = self._indoor_map.rooms
        if row_index < 0 or row_index >= len(rooms):
            return
        if col_room_index < 0 or col_room_index >= len(rooms):
            return

        src_room_id = id(rooms[row_index])
        dst_room_id = id(rooms[col_room_index])
        if src_room_id == dst_room_id:
            matrix.blockSignals(True)
            item.setCheckState(column, Qt.CheckState.Unchecked)
            matrix.blockSignals(False)
            return

        visible = item.checkState(column) == Qt.CheckState.Checked
        self._set_indoor_vis_pair(src_room_id, dst_room_id, visible)
        self.ui.indoorRenderer.set_vis_matrix(self._indoor_vis_matrix)
        self._sync_main_renderer_vis_overlay()

    def _set_all_indoor_vis_visible(self):
        """Set all room pairs in the VIS matrix to visible."""
        room_ids = [id(room) for room in self._indoor_map.rooms]
        self._indoor_vis_matrix = {room_id: {other_id for other_id in room_ids if other_id != room_id} for room_id in room_ids}
        self._refresh_indoor_vis_matrix()

    def _clear_all_indoor_vis(self):
        """Clear all room pair visibility in the VIS matrix."""
        room_ids = [id(room) for room in self._indoor_map.rooms]
        self._indoor_vis_matrix = {room_id: set() for room_id in room_ids}
        self._refresh_indoor_vis_matrix()

    def _populate_walkmesh_material_list(self):
        """Populate the material list in the walkmesh tab."""
        populate_material_list_widget(self.ui.materialList, self.material_colors)
        if self.ui.materialList.count():
            self.ui.materialList.setCurrentRow(0)

    def _setup_walkmesh_face_panel(self):
        """Initialize selected-face controls for Walkmesh mode."""
        from qtpy.QtWidgets import QButtonGroup, QPushButton, QWidget  # noqa: PLC0415

        populate_material_combo_box(self.ui.faceMaterialCombo)
        self.ui.faceMaterialCombo.currentIndexChanged.connect(self._on_walkmesh_face_material_changed)
        self.ui.faceWalkCheck.setEnabled(False)
        self.ui.faceWalkCheckCheck.setEnabled(False)
        self.ui.faceLosCheck.setEnabled(False)
        self.ui.faceWalkCheck.setToolTip("Derived from selected material")
        self.ui.faceWalkCheckCheck.setToolTip("Derived from selected material")
        self.ui.faceLosCheck.setToolTip("Derived from selected material")

        self._walkmesh_mode_button_group = QButtonGroup(self)
        self._walkmesh_mode_button_group.setExclusive(True)
        self._walkmesh_mode_buttons: dict[int, QPushButton] = {}
        mode_buttons_row = QWidget(self.ui.walkmeshFacePropsBox)
        mode_buttons_layout = QHBoxLayout(mode_buttons_row)
        mode_buttons_layout.setContentsMargins(0, 0, 0, 0)
        mode_buttons_layout.setSpacing(4)
        mode_specs = (
            ("Face", WalkmeshSelectMode.FACE, "Select walkmesh faces"),
            ("Edge", WalkmeshSelectMode.EDGE, "Select walkmesh edges"),
            ("Vertex", WalkmeshSelectMode.VERTEX, "Select walkmesh vertices"),
        )
        for label, mode, tooltip in mode_specs:
            button = QPushButton(label, mode_buttons_row)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _=False, m=mode: self._set_walkmesh_select_mode(m))
            mode_buttons_layout.addWidget(button)
            self._walkmesh_mode_button_group.addButton(button, mode)
            self._walkmesh_mode_buttons[mode] = button
        self.ui.walkmeshFaceLayout.addRow("Select Mode:", mode_buttons_row)

        self._walkmesh_mode_value = QLabel("Face", self.ui.walkmeshFacePropsBox)
        self.ui.walkmeshFaceLayout.addRow("Active:", self._walkmesh_mode_value)

        self._walkmesh_face_index_value = QLabel("—", self.ui.walkmeshFacePropsBox)
        self.ui.walkmeshFaceLayout.addRow("Face Index:", self._walkmesh_face_index_value)
        self._walkmesh_edge_index_value = QLabel("—", self.ui.walkmeshFacePropsBox)
        self.ui.walkmeshFaceLayout.addRow("Edge:", self._walkmesh_edge_index_value)
        self._walkmesh_vertex_index_value = QLabel("—", self.ui.walkmeshFacePropsBox)
        self.ui.walkmeshFaceLayout.addRow("Vertex:", self._walkmesh_vertex_index_value)
        self._walkmesh_face_adjacency_value = QLabel("—", self.ui.walkmeshFacePropsBox)
        self._walkmesh_face_adjacency_value.setWordWrap(True)
        self.ui.walkmeshFaceLayout.addRow("Adjacency:", self._walkmesh_face_adjacency_value)
        self._set_walkmesh_select_mode(WalkmeshSelectMode.FACE, show_status=False)
        self._clear_selected_walkmesh_face()

    def _clear_selected_walkmesh_face(self):
        self._selected_walkmesh_face = None
        self._selected_walkmesh_edge = None
        self._selected_walkmesh_vertex = None
        self._walkmesh_vertex_drag_active = False
        self._walkmesh_vertex_drag_vertex = None
        self._walkmesh_vertex_drag_old_position = None
        self._walkmesh_vertex_drag_current_position = None
        self._walkmesh_vertex_drag_anchor = None
        self._walkmesh_vertex_drag_axis = None
        self._refresh_walkmesh_face_panel()

    def _sync_walkmesh_renderer_selection(self):
        self.ui.mainRenderer.set_walkmesh_selection(
            face=self._selected_walkmesh_face,
            edge=self._selected_walkmesh_edge,
            vertex=self._selected_walkmesh_vertex,
            drag_axis=self._walkmesh_vertex_drag_axis,
        )

    def _walkmesh_mode_name(self) -> str:
        return {
            WalkmeshSelectMode.FACE: "Face",
            WalkmeshSelectMode.EDGE: "Edge",
            WalkmeshSelectMode.VERTEX: "Vertex",
        }.get(self._walkmesh_select_mode, "Face")

    def _set_walkmesh_select_mode(self, mode: int, *, show_status: bool = True) -> None:
        if mode not in (WalkmeshSelectMode.FACE, WalkmeshSelectMode.EDGE, WalkmeshSelectMode.VERTEX):
            return

        if self._walkmesh_vertex_drag_active:
            self._end_walkmesh_vertex_drag()

        self._walkmesh_select_mode = mode
        self._selected_walkmesh_edge = None
        self._selected_walkmesh_vertex = None
        self._refresh_walkmesh_face_panel()
        if show_status:
            self._show_status_message(f"Walkmesh select mode: {self._walkmesh_mode_name()}")

    def _cycle_walkmesh_select_mode(self):
        self._set_walkmesh_select_mode((self._walkmesh_select_mode + 1) % 3)

    def _pick_walkmesh_face_at_world(self, world: Vector3) -> tuple[BWM, int, Vector3] | None:
        return self.ui.mainRenderer.walkmesh_face(world.x, world.y)

    @property
    def _walkmesh_select_bind(self) -> ControlItem:
        return ControlItem(self.settings.selectObject3dBind)

    @property
    def _walkmesh_vertex_drag_x_bind(self) -> ControlItem:
        return ControlItem(self.settings.walkmeshVertexDragXAxis3dBind)

    @property
    def _walkmesh_vertex_drag_y_bind(self) -> ControlItem:
        return ControlItem(self.settings.walkmeshVertexDragYAxis3dBind)

    @property
    def _walkmesh_vertex_drag_z_bind(self) -> ControlItem:
        return ControlItem(self.settings.walkmeshVertexDragZAxis3dBind)

    def _selected_walkmesh_vertex_object(self) -> Vector3 | None:
        selection = self._selected_walkmesh_vertex
        if selection is None:
            return None

        walkmesh, face_index, vertex_index, _ = selection
        if not (0 <= face_index < len(walkmesh.faces)):
            return None
        if vertex_index not in (0, 1, 2):
            return None
        face = walkmesh.faces[face_index]
        return [face.v1, face.v2, face.v3][vertex_index]

    def _selected_walkmesh_room_offset(self) -> Vector3:
        if self._selected_walkmesh_face is None:
            return Vector3(0.0, 0.0, 0.0)
        return self._selected_walkmesh_face[2]

    def _begin_walkmesh_vertex_drag(self, axis: str) -> None:
        vertex = self._selected_walkmesh_vertex_object()
        if vertex is None or axis not in ("x", "y", "z"):
            self._walkmesh_vertex_drag_active = False
            return

        self._walkmesh_vertex_drag_active = True
        self._walkmesh_vertex_drag_axis = axis
        self._walkmesh_vertex_drag_vertex = vertex
        self._walkmesh_vertex_drag_old_position = Vector3(vertex.x, vertex.y, vertex.z)
        self._walkmesh_vertex_drag_current_position = Vector3(vertex.x, vertex.y, vertex.z)
        self._walkmesh_vertex_drag_anchor = Vector3(vertex.x, vertex.y, vertex.z)
        self._sync_walkmesh_renderer_selection()

    def _update_walkmesh_vertex_drag(self, world: Vector3, buttons: set[Qt.MouseButton], keys: set[Qt.Key]) -> None:
        if not self._walkmesh_vertex_drag_active:
            return
        vertex = self._walkmesh_vertex_drag_vertex
        anchor = self._walkmesh_vertex_drag_anchor
        axis = self._walkmesh_vertex_drag_axis
        if vertex is None or anchor is None:
            return

        room_offset = self._selected_walkmesh_room_offset()
        world_local = Vector3(world.x - room_offset.x, world.y - room_offset.y, world.z - room_offset.z)
        target = Vector3(world_local.x, world_local.y, anchor.z)
        if axis == "x" or self._walkmesh_vertex_drag_x_bind.satisfied(buttons, keys):
            target = Vector3(world_local.x, anchor.y, anchor.z)
        elif axis == "y" or self._walkmesh_vertex_drag_y_bind.satisfied(buttons, keys):
            target = Vector3(anchor.x, world_local.y, anchor.z)
        elif axis == "z" or self._walkmesh_vertex_drag_z_bind.satisfied(buttons, keys):
            target = Vector3(anchor.x, anchor.y, world_local.z)

        if self.ui.snapCheck.isChecked():
            grid = self.ui.snapSizeSpin.value()
            target = snap_vector3(target, grid, enabled=grid > 0)

        if math.isclose(vertex.x, target.x, abs_tol=1e-6) and math.isclose(vertex.y, target.y, abs_tol=1e-6) and math.isclose(vertex.z, target.z, abs_tol=1e-6):
            return

        vertex.x = target.x
        vertex.y = target.y
        vertex.z = target.z
        self._walkmesh_vertex_drag_current_position = Vector3(target.x, target.y, target.z)
        self._on_walkmesh_face_data_changed()

    def _end_walkmesh_vertex_drag(self) -> None:
        if not self._walkmesh_vertex_drag_active:
            return

        vertex = self._walkmesh_vertex_drag_vertex
        old_position = self._walkmesh_vertex_drag_old_position
        new_position = self._walkmesh_vertex_drag_current_position

        self._walkmesh_vertex_drag_active = False
        self._walkmesh_vertex_drag_vertex = None
        self._walkmesh_vertex_drag_old_position = None
        self._walkmesh_vertex_drag_current_position = None
        self._walkmesh_vertex_drag_anchor = None
        self._walkmesh_vertex_drag_axis = None
        self._sync_walkmesh_renderer_selection()

        if vertex is None or old_position is None or new_position is None:
            return

        if (
            math.isclose(old_position.x, new_position.x, abs_tol=1e-6)
            and math.isclose(old_position.y, new_position.y, abs_tol=1e-6)
            and math.isclose(old_position.z, new_position.z, abs_tol=1e-6)
        ):
            return

        self.undo_stack.push(
            _MoveWalkmeshVertexCommand(
                vertex,
                old_position,
                new_position,
                self._on_walkmesh_face_data_changed,
            )
        )
        self._show_status_message(
            f"Walkmesh vertex moved to ({new_position.x:.3f}, {new_position.y:.3f}, {new_position.z:.3f})",
            2000,
        )

    def _select_walkmesh_face_from_world(self, world: Vector3):
        if self._walkmesh_select_mode == WalkmeshSelectMode.VERTEX:
            vertex_selection = self.ui.mainRenderer.walkmesh_vertex(world.x, world.y)
            if vertex_selection is None:
                self._clear_selected_walkmesh_face()
                return
            walkmesh, face_index, vertex_index, room_offset = vertex_selection
            self._selected_walkmesh_vertex = (walkmesh, face_index, vertex_index, room_offset)
            self._selected_walkmesh_edge = None
            self._selected_walkmesh_face = (walkmesh, face_index, room_offset)
            self._refresh_walkmesh_face_panel()
            return

        if self._walkmesh_select_mode == WalkmeshSelectMode.EDGE:
            edge_selection = self.ui.mainRenderer.walkmesh_edge(world.x, world.y)
            if edge_selection is None:
                self._clear_selected_walkmesh_face()
                return
            walkmesh, face_index, edge_index, room_offset = edge_selection
            self._selected_walkmesh_edge = (walkmesh, face_index, edge_index, room_offset)
            self._selected_walkmesh_vertex = None
            self._selected_walkmesh_face = (walkmesh, face_index, room_offset)
            self._refresh_walkmesh_face_panel()
            return

        selection = self._pick_walkmesh_face_at_world(world)
        if selection is None:
            self._clear_selected_walkmesh_face()
            return
        self._selected_walkmesh_edge = None
        self._selected_walkmesh_vertex = None
        self._selected_walkmesh_face = selection
        self._refresh_walkmesh_face_panel()

    def _refresh_walkmesh_face_panel(self):
        self._walkmesh_face_ui_updating = True
        try:
            self._walkmesh_mode_value.setText(self._walkmesh_mode_name())
            for mode, button in getattr(self, "_walkmesh_mode_buttons", {}).items():
                button.setChecked(mode == self._walkmesh_select_mode)
            selected = self._selected_walkmesh_face
            has_selected = selected is not None
            self.ui.walkmeshFacePropsBox.setEnabled(has_selected)
            if not has_selected:
                self._walkmesh_face_index_value.setText("—")
                self._walkmesh_edge_index_value.setText("—")
                self._walkmesh_vertex_index_value.setText("—")
                self._walkmesh_face_adjacency_value.setText("—")
                self.ui.faceWalkCheck.setChecked(False)
                self.ui.faceWalkCheckCheck.setChecked(False)
                self.ui.faceLosCheck.setChecked(False)
                self.ui.faceMaterialCombo.setCurrentIndex(-1)
                return

            walkmesh, face_index, _ = selected
            if not (0 <= face_index < len(walkmesh.faces)):
                self._selected_walkmesh_face = None
                self._selected_walkmesh_edge = None
                self._selected_walkmesh_vertex = None
                self.ui.walkmeshFacePropsBox.setEnabled(False)
                self._walkmesh_face_index_value.setText("—")
                self._walkmesh_edge_index_value.setText("—")
                self._walkmesh_vertex_index_value.setText("—")
                self._walkmesh_face_adjacency_value.setText("—")
                self.ui.faceWalkCheck.setChecked(False)
                self.ui.faceWalkCheckCheck.setChecked(False)
                self.ui.faceLosCheck.setChecked(False)
                self.ui.faceMaterialCombo.setCurrentIndex(-1)
                return

            face = walkmesh.faces[face_index]
            self._walkmesh_face_index_value.setText(str(face_index))
            if self._selected_walkmesh_edge is not None:
                self._walkmesh_edge_index_value.setText(str(self._selected_walkmesh_edge[2]))
            else:
                self._walkmesh_edge_index_value.setText("—")
            if self._selected_walkmesh_vertex is not None:
                vertex_slot = self._selected_walkmesh_vertex[2]
                vertex = [face.v1, face.v2, face.v3][vertex_slot]
                global_vertex_index = next(
                    (index for index, candidate in enumerate(walkmesh.vertices()) if candidate is vertex),
                    -1,
                )
                if global_vertex_index >= 0:
                    self._walkmesh_vertex_index_value.setText(f"{vertex_slot} (global {global_vertex_index})")
                else:
                    self._walkmesh_vertex_index_value.setText(str(vertex_slot))
            else:
                self._walkmesh_vertex_index_value.setText("—")
            material = face.material
            combo_index = self.ui.faceMaterialCombo.findData(material)
            self.ui.faceMaterialCombo.setCurrentIndex(combo_index)

            adjacency = walkmesh.adjacencies(face)
            face_id_by_identity = {id(candidate): index for index, candidate in enumerate(walkmesh.faces)}
            transitions = [face.trans1, face.trans2, face.trans3]
            parts: list[str] = []
            for edge_index, adjacent in enumerate(adjacency):
                transition = transitions[edge_index]
                transition_text = "—" if transition is None else str(transition)
                if adjacent is None:
                    parts.append(f"E{edge_index}: none (T={transition_text})")
                    continue
                adjacent_face_index = face_id_by_identity.get(id(adjacent.face), -1)
                if adjacent_face_index >= 0:
                    parts.append(f"E{edge_index}: F{adjacent_face_index} (edge {adjacent.edge}, T={transition_text})")
                else:
                    parts.append(f"E{edge_index}: edge {adjacent.edge} (T={transition_text})")
            self._walkmesh_face_adjacency_value.setText(" | ".join(parts))

            # Derived booleans currently map to material semantics; dedicated face flags can be added later.
            walkable = material.walkable()
            line_of_sight = material is not SurfaceMaterial.OBSCURING
            self.ui.faceWalkCheck.setChecked(walkable)
            self.ui.faceWalkCheckCheck.setChecked(walkable)
            self.ui.faceLosCheck.setChecked(line_of_sight)

            material_row = next(
                (row for row in range(self.ui.materialList.count()) if self.ui.materialList.item(row).data(Qt.ItemDataRole.UserRole) == material),
                -1,
            )
            if material_row >= 0:
                self.ui.materialList.setCurrentRow(material_row)
        finally:
            self._sync_walkmesh_renderer_selection()
            self._walkmesh_face_ui_updating = False

    def _on_walkmesh_face_material_changed(self, index: int):
        if self._walkmesh_face_ui_updating or index < 0:
            return

        selection = self._selected_walkmesh_face
        if selection is None:
            return

        material = self.ui.faceMaterialCombo.itemData(index)
        if not isinstance(material, SurfaceMaterial):
            return

        walkmesh, face_index, _ = selection
        if not (0 <= face_index < len(walkmesh.faces)):
            return

        old_material = walkmesh.faces[face_index].material
        if old_material == material:
            return

        self.undo_stack.push(
            _SetWalkmeshFaceMaterialCommand(
                walkmesh,
                face_index,
                old_material,
                material,
                self._on_walkmesh_face_data_changed,
            )
        )
        self._show_status_message(f"Walkmesh face {face_index} material set to {material.name}")

    def _on_walkmesh_face_data_changed(self):
        self._refresh_walkmesh_face_panel()
        self._invalidate_scene_and_update_renderers()

    def _show_info_message(self, title: str, text: str) -> None:
        """Show informational message dialog."""
        from qtpy.QtWidgets import QMessageBox

        QMessageBox.information(self, title, text)

    def _show_warning_message(self, title: str, text: str) -> None:
        """Show warning message dialog."""
        from qtpy.QtWidgets import QMessageBox

        QMessageBox.warning(self, title, text)

    def _show_error_message(self, title: str, text: str) -> None:
        """Show error message dialog."""
        from qtpy.QtWidgets import QMessageBox

        QMessageBox.critical(self, title, text)

    def _get_or_create_layout_resource(self) -> LYT | None:
        """Get the layout resource from the current module, creating an empty one if needed.

        Returns:
            LYT object if module exists and has layout, None if module doesn't exist.
        """
        if self._module is None:
            return None

        layout_module = self._module.layout()
        if layout_module is None:
            self.log.warning("No layout resource found in module")
            return None

        lyt: LYT | None = layout_module.resource()
        if lyt is None:
            lyt = LYT()
            layout_module._resource_obj = lyt  # noqa: SLF001

        return lyt

    def _is_blender_mode_enabled(self) -> bool:
        """Check if Blender mode is active and controller is available."""
        return self.is_blender_mode() and self._blender_controller is not None

    def _show_status_message(self, message: str, duration_ms: int = 2000) -> None:
        """Display a temporary status message in the status bar.

        Most UI actions show a status message for 2 seconds. This helper
        consolidates that common pattern.

        Args:
            message: The status message to display
            duration_ms: Duration in milliseconds (default 2000)
        """
        self.statusBar().showMessage(message, duration_ms)

    def _is_rotatable_instance(self, instance: GITObject) -> bool:
        return isinstance(instance, (GITCamera, GITCreature, GITDoor, GITPlaceable, GITStore, GITWaypoint))

    def _capture_initial_rotation_for_transform(self, instance: GITObject) -> None:
        if isinstance(instance, GITCamera):
            self.transform_state.initial_rotations[instance] = Vector4(
                instance.orientation.x,
                instance.orientation.y,
                instance.orientation.z,
                instance.orientation.w,
            )
        elif self._is_rotatable_instance(instance):
            self.transform_state.initial_rotations[instance] = float(instance.bearing)

    # --- Indoor Kit/Module Selection Handlers ---

    def _clear_list_selection(self, list_widget) -> None:
        """Clear selection from a QListWidget while temporarily blocking signals.

        This is a common pattern: temporarily disable signals,  clear selection and
        current item, then re-enable signals to avoid triggering selection change events.
        """
        list_widget.blockSignals(True)
        try:
            list_widget.clearSelection()
            list_widget.setCurrentItem(None)
        finally:
            list_widget.blockSignals(False)

    def _on_indoor_kit_selected(self, index: int):
        """Handle kit selection in the Layout tab."""
        self.ui.componentList.clear()
        if index < 0 or index >= len(self._indoor_kits):
            return
        kit = self._indoor_kits[index]
        for comp in kit.components:
            item = QListWidgetItem(comp.name)
            item.setData(Qt.ItemDataRole.UserRole, comp)
            # Generate preview image
            try:
                qimage = ensure_component_image(comp)
                if qimage is not None:
                    pix = QPixmap.fromImage(qimage).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
                    item.setIcon(QIcon(pix))
            except Exception:
                pass
            self.ui.componentList.addItem(item)

    def _on_indoor_component_selected(self, current, previous):
        """Handle component selection — update preview and set cursor component for placement.

        Toggle behavior: clicking the same component again deselects it (cancels placement).
        """
        renderer = self.ui.indoorRenderer
        if current is None:
            self._set_indoor_preview_image(None)
            renderer.set_cursor_component(None)
            return
        comp = current.data(Qt.ItemDataRole.UserRole)
        if comp is None or not isinstance(comp, KitComponent):
            return

        # Toggle: if same component is already selected, deselect it
        if renderer.cursor_component is comp:
            self._clear_list_selection(self.ui.componentList)
            self._set_indoor_preview_image(None)
            renderer.set_cursor_component(None)
            return

        # Clear the other list's selection to avoid confusion
        self._clear_list_selection(self.ui.moduleComponentList)

        self._set_indoor_preview_image(ensure_component_image(comp))
        renderer.set_cursor_component(comp)

    def _set_indoor_preview_image(self, qimage: QImage | None):
        """Update the indoor preview image label."""
        self._indoor_preview_source_image = set_preview_source_image(self.ui.indoorPreviewImage, qimage)

    def _on_module_kit_selected(self, index: int):
        """Handle module kit selection — lazy-load the module's rooms."""
        self.ui.moduleComponentList.clear()
        if self._module_kit_manager is None or index < 0:
            return
        module_root = self.ui.moduleKitSelect.itemData(index)
        if module_root is None:
            return
        try:
            self._current_module_kit = self._module_kit_manager.get_module_kit(str(module_root))
            if not self._current_module_kit.ensure_loaded():
                return
            for comp in self._current_module_kit.components:
                item = QListWidgetItem(comp.name)
                item.setData(Qt.ItemDataRole.UserRole, comp)
                self.ui.moduleComponentList.addItem(item)
        except Exception:
            self.log.warning("Failed to load module kit for %s", module_root)

    def _on_module_component_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        """Handle module component selection — set cursor for placement with toggle."""
        renderer = self.ui.indoorRenderer
        if current is None:
            self._set_indoor_preview_image(None)
            renderer.set_cursor_component(None)
            return
        comp = current.data(Qt.ItemDataRole.UserRole)
        if comp is None or not isinstance(comp, KitComponent):
            return

        # Toggle: if same component is already selected, deselect it
        if renderer.cursor_component is comp:
            self._clear_list_selection(self.ui.moduleComponentList)
            self._set_indoor_preview_image(None)
            renderer.set_cursor_component(None)
            return

        # Clear the other list's selection to avoid confusion
        self._clear_list_selection(self.ui.componentList)

        self._set_indoor_preview_image(ensure_component_image(comp))
        renderer.set_cursor_component(comp)

    # --- Indoor Paint / Build Handlers ---

    def _toggle_indoor_paint_mode(self, enabled: bool):
        self._indoor_painting_walkmesh = enabled
        self._indoor_paint_stroke_active = False
        self._indoor_paint_stroke_originals.clear()
        self._indoor_paint_stroke_new.clear()

    def _toggle_indoor_colorize(self, enabled: bool):
        self._indoor_colorize_materials = enabled
        self.ui.indoorRenderer.set_colorize_materials(enabled)
        self.ui.indoorRenderer.mark_dirty()

    def _current_indoor_material(self) -> SurfaceMaterial | None:
        """Return the currently selected walkmesh material from the material list."""
        item = self.ui.materialList.currentItem()
        if item is not None:
            material = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(material, SurfaceMaterial):
                return material
        return None

    # --- Walkmesh Paint Stroke Logic ---

    def _begin_indoor_paint_stroke(self, screen: Vector2):
        """Start a new walkmesh paint stroke."""
        self._indoor_paint_stroke_active = True
        self._indoor_paint_stroke_originals.clear()
        self._indoor_paint_stroke_new.clear()
        self._apply_indoor_paint_at_screen(screen)

    def _apply_indoor_paint_at_screen(self, screen: Vector2):
        """Convert screen coords to world and apply paint."""
        world = self.ui.indoorRenderer.to_world_coords(screen.x, screen.y)
        self._apply_indoor_paint_at_world(world)

    def _apply_indoor_paint_at_world(self, world: Vector3):
        """Paint the walkmesh face at the given world position with the current material."""
        material = self._current_indoor_material()
        if material is None:
            return
        room, face_index = self.ui.indoorRenderer.pick_face(world)
        if room is None or face_index is None:
            return
        # Ensure we have a writable walkmesh override
        if room.walkmesh_override is None:
            room.walkmesh_override = deepcopy(room.component.bwm)
        base_bwm = room.walkmesh_override
        if not (0 <= face_index < len(base_bwm.faces)):
            return

        key = (room, face_index)
        if key not in self._indoor_paint_stroke_originals:
            self._indoor_paint_stroke_originals[key] = base_bwm.faces[face_index].material

        if base_bwm.faces[face_index].material == material:
            return

        base_bwm.faces[face_index].material = material
        self._indoor_paint_stroke_new[key] = material
        self._invalidate_indoor_rooms([room])

    def _finish_indoor_paint_stroke(self):
        """Finish the current paint stroke and push an undo command."""
        if not self._indoor_paint_stroke_active:
            return
        self._indoor_paint_stroke_active = False
        if not self._indoor_paint_stroke_new:
            return

        rooms: list[IndoorMapRoom] = []
        face_indices: list[int] = []
        old_materials: list[SurfaceMaterial] = []
        new_materials: list[SurfaceMaterial] = []

        for (room, face_index), new_material in self._indoor_paint_stroke_new.items():
            rooms.append(room)
            face_indices.append(face_index)
            old_materials.append(self._indoor_paint_stroke_originals.get((room, face_index), new_material))
            new_materials.append(new_material)

        cmd = PaintWalkmeshCommand(rooms, face_indices, old_materials, new_materials, self._invalidate_indoor_rooms)
        self.undo_stack.push(cmd)

    def _reset_indoor_walkmesh_paint(self):
        """Reset walkmesh paint on selected rooms."""
        rooms = [r for r in self.ui.indoorRenderer.selected_rooms() if r.walkmesh_override is not None]
        if not rooms:
            return
        self.undo_stack.push(ResetWalkmeshCommand(rooms, self.ui.indoorRenderer.mark_dirty))

    def _build_indoor_module(self):
        """Build the indoor layout into a .mod file."""
        from qtpy.QtWidgets import QFileDialog

        if not self._indoor_map.rooms:
            self._show_warning_message("Build", "No rooms have been placed. Add rooms first.")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Save Module", "", "Module Files (*.mod)")
        if not filepath:
            return
        try:
            game = self._installation.game() if self._installation else None
            self._indoor_map.build(self._installation, self._indoor_kits, filepath, game_override=game)
            self._apply_indoor_vis_overrides_to_build(filepath)
            self._show_info_message("Build Complete", f"Module saved to:\n{filepath}")
        except Exception as e:
            self._show_error_message("Build Failed", f"Failed to build module:\n{e}")

    def _apply_indoor_vis_overrides_to_build(self, output_path: os.PathLike | str):
        """Apply VIS matrix state to the freshly built module's VIS resource."""
        vis = self._indoor_map.vis
        mod = self._indoor_map.mod
        if vis is None or mod is None:
            return

        room_ids: list[int] = []
        room_names: list[str] = []
        for room in self._indoor_map.rooms:
            room_name = self._indoor_map.room_names.get(room)
            if room_name is None:
                continue
            room_ids.append(id(room))
            room_names.append(room_name)

        for src_index, src_name in enumerate(room_names):
            visible_targets = self._indoor_vis_matrix.get(room_ids[src_index], set())
            for dst_index, dst_name in enumerate(room_names):
                if src_index == dst_index:
                    continue
                vis.set_visible(src_name, dst_name, room_ids[dst_index] in visible_targets)

        mod.set_data(self._indoor_map.module_id, ResourceType.VIS, bytes_vis(vis))
        write_erf(mod, output_path)

    # --- Indoor File I/O ---

    def _indoor_new(self):
        """Create a new empty indoor map, prompting to save if dirty."""
        if not self.undo_stack.isClean():
            result = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before creating a new map?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Save:
                self._indoor_save()
            elif result == QMessageBox.StandardButton.Cancel:
                return

        self._indoor_filepath = ""
        self._indoor_map.reset()
        self.ui.indoorRenderer._bwm_surface_cache.clear()
        self._indoor_vis_matrix.clear()
        self._refresh_indoor_vis_matrix()
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._refresh_window_title()

    def _indoor_save(self):
        """Save the current indoor map to its existing filepath, or prompt for one."""
        from pykotor.common.stream import BinaryWriter

        if not self._indoor_filepath:
            self._indoor_save_as()
        else:
            BinaryWriter.dump(self._indoor_filepath, self._indoor_map.write())
            self.undo_stack.setClean()
            self._refresh_window_title()

    def _indoor_save_as(self):
        """Save the current indoor map to a new filepath."""
        from qtpy.QtWidgets import QFileDialog

        from pykotor.common.stream import BinaryWriter

        default_name = Path(self._indoor_filepath).name if self._indoor_filepath else "untitled.indoor"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Indoor Map", default_name, "Indoor Map File (*.indoor)")
        if not filepath or not str(filepath).strip():
            return
        BinaryWriter.dump(Path(filepath), self._indoor_map.write())
        self._indoor_filepath = str(Path(filepath))
        self.undo_stack.setClean()
        self._refresh_window_title()

    def _indoor_open(self):
        """Open an .indoor file, prompting to save if dirty."""
        from qtpy.QtWidgets import QFileDialog

        if not self.undo_stack.isClean():
            result = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before opening another map?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Save:
                self._indoor_save()
            elif result == QMessageBox.StandardButton.Cancel:
                return

        filepath, _ = QFileDialog.getOpenFileName(self, "Open Indoor Map", "", "Indoor Map File (*.indoor)")
        if not filepath or not str(filepath).strip():
            return
        try:
            missing_rooms = self._indoor_map.load(Path(filepath).read_bytes(), self._indoor_kits, self._module_kit_manager)
            self._indoor_map.rebuild_room_connections()
            self.ui.indoorRenderer._bwm_surface_cache.clear()
            self._indoor_filepath = filepath
            self._indoor_vis_matrix.clear()
            self._refresh_indoor_vis_matrix()
            self.undo_stack.clear()
            self.undo_stack.setClean()
            self._refresh_window_title()

            if missing_rooms:
                details = "\n".join(f"- {r.kit_name}/{r.component_name} ({r.reason})" for r in missing_rooms)
                self._show_warning_message("Missing Rooms", f"Some rooms failed to load:\n\n{details}")
        except Exception as e:
            self._show_error_message("Failed to Load", f"Failed to load indoor map:\n{e}")

    def _cancel_all_indoor_operations(self):
        """Cancel all active indoor operations and reset to a safe state.

        This is the "panic button" — cancels marquee, drags, paint, and placement.
        """
        renderer = self.ui.indoorRenderer
        cancel_indoor_operations_core(
            renderer,
            clear_paint_stroke=self._clear_indoor_paint_stroke,
            clear_placement_mode=self._indoor_clear_placement_mode,
        )

    def _clear_indoor_paint_stroke(self) -> None:
        if not self._indoor_paint_stroke_active:
            return
        self._indoor_paint_stroke_active = False
        self._indoor_paint_stroke_originals.clear()
        self._indoor_paint_stroke_new.clear()

    def _update_indoor_status_bar(self, screen):
        """Update the existing status bar labels with indoor-mode info."""
        renderer = self.ui.indoorRenderer
        colors = self._get_semantic_colors()

        # World coordinates
        world = renderer.to_world_coords(screen.x, screen.y)
        self.mouse_pos_label.setText(
            f"<b><span style='{self._emoji_style}'>🖱</span>&nbsp;Coords:</b> "
            f"<span style='color:{colors['accent1']}'>{world.x:.2f}</span>, "
            f"<span style='color:{colors['accent2']}'>{world.y:.2f}</span>"
        )

        # Selection / hover info
        hover_room: IndoorMapRoom | None = renderer.room_under_mouse()
        sel_rooms = renderer.selected_rooms()
        sel_hook = renderer.selected_hook()

        parts: list[str] = []
        if hover_room is not None:
            parts.append(f"Hover: <span style='color:{colors['accent1']}'>{hover_room.component.name}</span>")
        if sel_hook is not None:
            hook_room, hook_idx = sel_hook
            parts.append(f"Hook: <span style='color:{colors['accent1']}'>{hook_room.component.name}</span> #{hook_idx}")
        elif sel_rooms:
            parts.append(f"Selected: <span style='color:{colors['accent1']}'>{len(sel_rooms)}</span> room(s)")

        if self._indoor_painting_walkmesh:
            parts.append(f"<span style='color:{colors['warn']}'>PAINT</span>")
        if renderer.cursor_component is not None:
            parts.append(f"Place: <span style='color:{colors['info']}'>{renderer.cursor_component.name}</span>")

        sel_text = " | ".join(parts) if parts else f"<span style='color:{colors['muted']}'><i>None</i></span>"
        self.selected_instance_label.setText(f"<b><span style='{self._emoji_style}'>🧩</span>&nbsp;Layout:</b> {sel_text}")

        # Camera / view info
        self.view_camera_label.setText(
            f"<b><span style='{self._emoji_style}'>🎥</span>&nbsp;Mode:</b> "
            f"<span style='color:{colors['info']}'>Layout</span> | "
            f"Rooms: <span style='color:{colors['accent1']}'>{len(self._indoor_map.rooms)}</span>"
        )

    # --- Indoor Renderer Event Stubs ---
    # These forward to the indoor renderer's internal handling or
    # will be expanded as the merge progresses.

    # =========================================================================
    # Indoor View Navigation
    # =========================================================================

    def _indoor_reset_view(self):
        """Reset the indoor renderer camera to its default position."""
        from toolset.gui.windows.indoor_builder.constants import (
            DEFAULT_CAMERA_POSITION_X,
            DEFAULT_CAMERA_POSITION_Y,
            DEFAULT_CAMERA_ROTATION,
            DEFAULT_CAMERA_ZOOM,
        )

        reset_indoor_camera_view(
            self.ui.indoorRenderer,
            default_camera_x=DEFAULT_CAMERA_POSITION_X,
            default_camera_y=DEFAULT_CAMERA_POSITION_Y,
            default_camera_rotation=DEFAULT_CAMERA_ROTATION,
            default_camera_zoom=DEFAULT_CAMERA_ZOOM,
        )

    def _indoor_center_on_selection(self):
        """Center the indoor camera on the selected rooms."""
        center_indoor_camera_on_selected_rooms(self.ui.indoorRenderer)

    def _indoor_add_connected_to_selection(self, room: IndoorMapRoom):
        """Recursively select a room and all rooms connected via hooks."""
        add_connected_indoor_rooms_to_selection(self.ui.indoorRenderer, room)

    # =========================================================================
    # Indoor Room Operations (Layout Mode)
    # =========================================================================

    def _invalidate_indoor_rooms(self, rooms: list[IndoorMapRoom]):
        """Refresh the indoor renderer after room changes."""
        self.ui.indoorRenderer.invalidate_rooms(rooms)
        self._refresh_indoor_vis_matrix()
        self._sync_lyt_from_indoor_map()

    def _sync_lyt_from_indoor_map(self) -> None:
        """Sync IndoorMap rooms → module LYT (in-memory) and refresh layout tree."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None:
            return
        lyt.rooms.clear()
        module_id = self._indoor_map.module_id
        for i, room in enumerate(self._indoor_map.rooms):
            model_name = f"{module_id}_room{i}"
            lyt.rooms.append(LYTRoom(model_name, room.position))
        self.rebuild_layout_tree()

    def _indoor_place_new_room(self, component: KitComponent):
        """Place a new room at the cursor position with undo support."""
        renderer = self.ui.indoorRenderer
        room = IndoorMapRoom(
            component,
            Vector3(*renderer.cursor_point),
            renderer.cursor_rotation,
            flip_x=renderer.cursor_flip_x,
            flip_y=renderer.cursor_flip_y,
        )
        cmd = AddRoomCommand(self._indoor_map, room, self._invalidate_indoor_rooms)
        self.undo_stack.push(cmd)
        renderer.cursor_rotation = 0.0
        renderer.cursor_flip_x = False
        renderer.cursor_flip_y = False

    def _indoor_delete_selected(self):
        """Delete selected rooms or hooks."""
        delete_selected_rooms_or_hook(
            self.ui.indoorRenderer,
            self._indoor_map,
            self.undo_stack,
            self._invalidate_indoor_rooms,
        )

    def _indoor_duplicate_selected(self):
        """Duplicate selected rooms or hooks."""
        duplicate_selected_rooms_or_hook(
            self.ui.indoorRenderer,
            self._indoor_map,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            Vector3(DUPLICATE_OFFSET_X, DUPLICATE_OFFSET_Y, DUPLICATE_OFFSET_Z),
        )

    def _indoor_merge_selected(self):
        """Merge 2+ selected rooms into a single room."""
        apply_merge_selected_rooms(
            self.ui.indoorRenderer,
            self._indoor_map,
            self._indoor_embedded_kit,
            self.undo_stack,
            self._invalidate_indoor_rooms,
        )

    def _indoor_rotate_selected(self, angle: float):
        """Rotate selected rooms by a fixed angle."""
        apply_rotate_selected_rooms(
            self.ui.indoorRenderer,
            self._indoor_map,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            angle,
        )

    def _indoor_flip_selected(self, flip_x: bool, flip_y: bool):
        """Flip selected rooms."""
        apply_flip_selected_rooms(
            self.ui.indoorRenderer,
            self._indoor_map,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            flip_x,
            flip_y,
        )

    def _indoor_cut_selected(self):
        cut_indoor_selection(copy_selected=self._indoor_copy_selected, delete_selected=self._indoor_delete_selected)

    def _indoor_copy_selected(self):
        """Copy selected rooms to the indoor clipboard."""
        self._indoor_clipboard = copy_selected_rooms_to_clipboard(self.ui.indoorRenderer)

    def _indoor_paste(self):
        """Paste rooms from the indoor clipboard."""
        apply_paste_rooms_from_clipboard(
            self.ui.indoorRenderer,
            self._indoor_map,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            self._indoor_clipboard,
            self._indoor_kits,
        )

    def _indoor_clear_placement_mode(self):
        """Clear cursor component and UI selections."""
        clear_indoor_placement_mode(
            self.ui.indoorRenderer,
            self.ui.componentList,
            self.ui.moduleComponentList,
        )

    # =========================================================================
    # Indoor Renderer Signal Handlers
    # =========================================================================

    def _on_indoor_mouse_moved(self, coords: QPoint, coords_delta: QPoint, mouse_down: set[Qt.MouseButton], keys_down: set[Qt.Key]):
        """Handle mouse move in the indoor renderer — paint stroke + status bar update."""
        renderer = self.ui.indoorRenderer
        world_delta: Vector2 = renderer.to_world_delta(coords_delta.x, coords_delta.y)
        handled_cam = handle_standard_2d_camera_movement(
            renderer,
            coords,
            coords_delta,
            world_delta,
            mouse_down,
            keys_down,
            is_indoor_builder=True,
        )

        if not handled_cam and self._indoor_paint_stroke_active and Qt.MouseButton.LeftButton in mouse_down:
            self._apply_indoor_paint_at_screen(Vector2(coords.x, coords.y))
        self._update_indoor_status_bar(coords)

    def _on_indoor_mouse_pressed(self, coords: QPoint, mouse_down: set[Qt.MouseButton], keys_down: set[Qt.Key]):
        """Handle mouse press in Indoor Layout mode."""
        renderer = self.ui.indoorRenderer
        if Qt.MouseButton.LeftButton not in mouse_down:
            return
        if Qt.Key.Key_Control in keys_down:
            return  # Control = camera pan

        # Walkmesh painting
        if self._indoor_painting_walkmesh or Qt.Key.Key_Shift in keys_down:
            self._begin_indoor_paint_stroke(Vector2(coords.x, coords.y))
            return

        world = renderer.to_world_coords(coords.x, coords.y)
        handle_indoor_primary_press(
            renderer,
            world,
            shift_pressed=Qt.Key.Key_Shift in keys_down,
            clear_placement_mode=self._indoor_clear_placement_mode,
            place_new_room=self._indoor_place_new_room,
            start_marquee=lambda: renderer.start_marquee(coords),
        )

    def _on_indoor_mouse_released(self, coords: QPoint, mouse_down: set[Qt.MouseButton], keys_down: set[Qt.Key]):
        """Handle mouse release — finalize paint strokes."""
        if self._indoor_paint_stroke_active:
            self._finish_indoor_paint_stroke()
        renderer = self.ui.indoorRenderer
        if renderer._dragging_hook:  # noqa: SLF001
            renderer._dragging_hook = False  # noqa: SLF001
            self._indoor_map.rebuild_room_connections()
        renderer.end_drag()

    def _on_indoor_mouse_double_clicked(self, coords: QPoint, mouse_down: set[Qt.MouseButton], keys_down: set[Qt.Key]):
        """Handle double-click — select room and all connected rooms via hooks."""
        handle_indoor_double_click_select_connected(
            self.ui.indoorRenderer,
            left_pressed=Qt.MouseButton.LeftButton in mouse_down,
            add_connected_to_selection=self._indoor_add_connected_to_selection,
        )

    def _on_indoor_mouse_scrolled(self, delta: QPoint, mouse_down: set[Qt.MouseButton], keys_down: set[Qt.Key]):
        """Handle scroll — zoom (Ctrl+scroll), drag rotation, or placement rotation."""
        renderer = self.ui.indoorRenderer

        handle_indoor_scroll(
            renderer,
            delta_y=delta.y,
            ctrl_pressed=Qt.Key.Key_Control in keys_down,
            zoom_factor_from_delta=lambda value: (1.0 + ZOOM_WHEEL_SENSITIVITY) ** (value / 120.0),
        )

    def _on_indoor_rooms_moved(self, rooms: list[IndoorMapRoom], old_positions: list[Vector3], new_positions: list[Vector3]):
        """Handle room drag completion — create undo command."""
        if push_rooms_moved_undo(
            self._indoor_map,
            rooms,
            old_positions,
            new_positions,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            position_change_epsilon=POSITION_CHANGE_EPSILON,
        ):
            self._sync_main_renderer_vis_overlay()

    def _on_indoor_rooms_rotated(self, rooms: list[IndoorMapRoom], old_rotations: list[float], new_rotations: list[float]):
        """Handle room rotation during drag — create undo command."""
        push_rooms_rotated_undo(
            self._indoor_map,
            rooms,
            old_rotations,
            new_rotations,
            self.undo_stack,
            self._invalidate_indoor_rooms,
            rotation_change_epsilon=ROTATION_CHANGE_EPSILON,
        )

    def _on_indoor_warp_moved(self, old_pos: Vector3, new_pos: Vector3):
        """Handle warp point drag."""
        push_warp_moved_undo(self._indoor_map, old_pos, new_pos, self.undo_stack)

    # =========================================================================
    # Indoor Context Menu
    # =========================================================================

    def _on_indoor_context_menu(self, point: QPoint):
        """Build and show the right-click context menu for indoor renderer."""
        renderer = self.ui.indoorRenderer
        world, room, hook_hit = get_indoor_context_hits(
            renderer,
            screen_x=point.x(),
            screen_y=point.y(),
        )
        menu = QMenu(self)

        populate_indoor_context_menu(
            menu,
            renderer=renderer,
            room=room,
            hook_hit=hook_hit,
            world=world,
            on_duplicate=self._indoor_duplicate_selected,
            on_delete=self._indoor_delete_selected,
            on_rotate=self._indoor_rotate_selected,
            on_flip=self._indoor_flip_selected,
            on_merge=self._indoor_merge_selected,
            on_add_hook_at=renderer.add_hook_at,
        )

        menu.popup(renderer.mapToGlobal(point))

    # =========================================================================
    # Indoor Options Initialization
    # =========================================================================

    def _initialize_indoor_options(self):
        """Initialize indoor options UI to match renderer state."""
        renderer = self.ui.indoorRenderer
        sync_indoor_options_ui_from_renderer(
            renderer,
            snap_to_grid_check=self.ui.snapToGridCheck,
            snap_to_hooks_check=self.ui.snapToHooksCheck,
            show_grid_check=self.ui.showGridCheck,
            show_hooks_check=self.ui.showHooksCheck,
            grid_size_spin=self.ui.gridSizeSpin,
            rotation_snap_spin=self.ui.rotSnapSpin,
        )

    def _init_ui(self):
        self.custom_status_bar = QStatusBar(self)
        self.setStatusBar(self.custom_status_bar)

        # Remove default margins/spacing for better space usage
        self.custom_status_bar.setContentsMargins(4, 0, 4, 0)

        # Emoji styling constant for consistent, crisp rendering
        # Uses proper emoji font fallback and slightly larger size for clarity
        self._emoji_style = "font-size:12pt; font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji','EmojiOne','Twemoji Mozilla','Segoe UI Symbol',sans-serif; vertical-align:middle;"

        # Create a main container widget that spans the full width
        self.custom_status_bar_container = QWidget()
        self.custom_status_bar_layout = QVBoxLayout(self.custom_status_bar_container)
        self.custom_status_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_status_bar_layout.setSpacing(2)

        # Create labels for the status bar with proper styling
        self.mouse_pos_label = QLabel("Mouse Coords: ")
        self.buttons_keys_pressed_label = QLabel("Keys/Buttons: ")
        self.selected_instance_label = QLabel("Selected Instance: ")
        self.view_camera_label = QLabel("View: ")

        # Set labels to allow rich text
        for label in [self.mouse_pos_label, self.buttons_keys_pressed_label, self.selected_instance_label, self.view_camera_label]:
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # First row: distribute evenly across full width
        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(8)

        first_row.addWidget(self.mouse_pos_label, 1)
        first_row.addWidget(self.selected_instance_label, 2)
        first_row.addWidget(self.buttons_keys_pressed_label, 1)

        # Second row: camera info spans full width
        self.custom_status_bar_layout.addLayout(first_row)
        self.custom_status_bar_layout.addWidget(self.view_camera_label)

        self.blender_status_chip = QLabel("Blender: idle")
        self.blender_status_chip.setTextFormat(Qt.TextFormat.RichText)
        self.blender_status_chip.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.custom_status_bar_layout.addWidget(self.blender_status_chip)

        # Add the container as a regular widget (not permanent) to use full width
        self.custom_status_bar.addWidget(self.custom_status_bar_container, 1)

    def _install_view_stack(self):
        """Wrap the GL/2D split with a stacked widget so we can swap in Blender instructions."""
        if self._view_stack is not None:
            return

        self._view_stack = QStackedWidget(self)
        self.ui.verticalLayout_2.removeWidget(self.ui.splitter)
        self._view_stack.addWidget(self.ui.splitter)
        self._blender_placeholder = self._create_blender_placeholder()
        self._view_stack.addWidget(self._blender_placeholder)
        self.ui.verticalLayout_2.addWidget(self._view_stack)

    def _create_blender_placeholder(self) -> QWidget:
        """Create placeholder pane shown while Blender drives the rendering."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        headline = QLabel(
            "<b>Blender mode is active.</b><br>"
            "The Holocron Toolset will defer all 3D rendering and editing to Blender. "
            "Use the Blender window to move the camera, manipulate instances, and "
            "open object context menus. This panel streams Blender's console output for diagnostics."
        )
        headline.setWordWrap(True)
        layout.addWidget(headline)

        self._blender_log_view = QPlainTextEdit(container)
        self._blender_log_view.setReadOnly(True)
        self._blender_log_view.setPlaceholderText("Blender log output will appear here once the IPC bridge starts…")
        layout.addWidget(self._blender_log_view, 1)

        return container

    def _show_blender_workspace(self):
        if self._view_stack is not None and self._blender_placeholder is not None:
            self._view_stack.setCurrentWidget(self._blender_placeholder)

    def _show_internal_workspace(self):
        if self._view_stack is not None:
            self._view_stack.setCurrentWidget(self.ui.splitter)

    def _invoke_on_ui_thread(self, func: Callable[[], None]):
        """Ensure UI mutations run on the main Qt thread."""
        QTimer.singleShot(0, func)

    def _prepare_for_blender_session(self, module_root: str):
        """Initialize UI elements before launching Blender."""
        self._blender_connected_once = False
        self._show_blender_workspace()
        self._start_blender_log_capture(module_root)
        self._update_blender_status_chip("Launching…", severity="info")
        self._show_blender_progress_dialog(f"Launching Blender for '{module_root}'…")

    def _start_blender_log_capture(self, module_root: str):
        log_dir = Path(tempfile.gettempdir()) / "HolocronToolset" / "blender_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._blender_log_path = log_dir / f"{module_root}_{timestamp}.log"
        try:
            self._blender_log_handle = self._blender_log_path.open("w", encoding="utf-8", buffering=1)
        except OSError as exc:
            self.log.error("Failed to open blender log file %s: %s", self._blender_log_path, exc)
            self._blender_log_handle = None
        self._blender_log_buffer.clear()
        if self._blender_log_view:
            self._blender_log_view.clear()

    def _close_blender_log_capture(self):
        if self._blender_log_handle:
            try:
                self._blender_log_handle.close()
            except OSError:
                pass
        self._blender_log_handle = None
        if self._blender_log_path:
            self.log.debug("Blender log saved to %s", self._blender_log_path)

    def _append_blender_log_line(self, line: str):
        self._blender_log_buffer.append(line)
        if self._blender_log_handle:
            try:
                self._blender_log_handle.write(line + "\n")
            except OSError:
                self._blender_log_handle = None
        if self._blender_log_view:
            self._blender_log_view.appendPlainText(line)

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

    def _update_blender_status_chip(self, message: str, *, severity: str = "info"):
        if not hasattr(self, "blender_status_chip"):
            return
        colors = self._get_semantic_colors()
        color = colors.get(severity, colors["info"])
        self.blender_status_chip.setText(f"<b><span style='{self._emoji_style}'>🧠</span>&nbsp;Blender:</b> <span style='color:{color}'>{message}</span>")

    def _show_blender_progress_dialog(self, message: str):
        if self._blender_progress_dialog is None:
            dialog = QProgressDialog(self)
            dialog.setLabelText(message)
            dialog.setCancelButtonText("Cancel launch")
            dialog.setWindowTitle("Connecting to Blender")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            dialog.setMinimum(0)
            dialog.setMaximum(0)
            dialog.canceled.connect(self._cancel_blender_launch)
            self._blender_progress_dialog = dialog
        else:
            self._blender_progress_dialog.setLabelText(message)
        self._blender_progress_dialog.show()

    def _dismiss_blender_progress_dialog(self):
        if self._blender_progress_dialog is not None:
            self._blender_progress_dialog.hide()

    def _cancel_blender_launch(self):
        self.log.warning("User cancelled Blender launch")
        self.stop_blender_mode()
        self._close_blender_log_capture()
        self._show_internal_workspace()
        self._dismiss_blender_progress_dialog()

    def _on_blender_output(self, line: str):
        super()._on_blender_output(line)

        def _append():
            self._append_blender_log_line(line)

        self._invoke_on_ui_thread(_append)

    def _on_blender_state_change(self, state: ConnectionState):
        super()._on_blender_state_change(state)
        self._invoke_on_ui_thread(lambda: self._handle_blender_state_change(state))

    def _handle_blender_state_change(self, state: ConnectionState):
        if state == ConnectionState.CONNECTING:
            self._update_blender_status_chip("Connecting…", severity="info")
        elif state == ConnectionState.CONNECTED:
            self._blender_connected_once = True
            self._dismiss_blender_progress_dialog()
            self._update_blender_status_chip("Connected", severity="ok")
        elif state == ConnectionState.ERROR:
            self._update_blender_status_chip("Connection error", severity="error")
        elif state == ConnectionState.DISCONNECTED and self._blender_connected_once:
            self._update_blender_status_chip("Disconnected", severity="warn")

    def _on_blender_connection_failed(self):
        self._invoke_on_ui_thread(lambda: self._handle_blender_launch_failure("IPC handshake failed"))

    def _handle_blender_launch_failure(self, reason: str):
        self._dismiss_blender_progress_dialog()
        self._update_blender_status_chip(f"Failed: {reason}", severity="error")
        self._close_blender_log_capture()
        self._show_internal_workspace()
        self._emit_blender_fallback_package(reason)

    def _emit_blender_fallback_package(self, failure_reason: str):
        if self._module is None:
            return
        try:
            lyt_module = self._module.layout()
            git_module = self._module.git()
            if not lyt_module or not git_module:
                self.log.warning("Cannot export fallback session: missing LYT or GIT resource")
                return
            lyt_resource = lyt_module.resource()
            git_resource = git_module.resource()
            if lyt_resource is None or git_resource is None:
                self.log.warning("Cannot export fallback session: resources not loaded")
                return
            payload = serialize_module_data(
                lyt_resource,
                git_resource,
                self._last_walkmeshes,
                self._module.root(),
                str(self._installation.path()),
            )
            fallback_dir = Path(tempfile.gettempdir()) / "HolocronToolset" / "sessions"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / f"{self._module.root()}_{int(time.time())}.json"
            fallback_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._fallback_session_path = fallback_path
            self._show_info_message(
                "Blender IPC failed",
                (
                    f"Blender could not be reached ({failure_reason}).\n\n"
                    f"A fallback session was exported to:\n{fallback_path}\n\n"
                    "Open Blender manually and choose File ▸ Import ▸ Holocron Toolset Session (.json) "
                    "to continue inside Blender."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self.log.error("Failed to export fallback session: %s", exc)

    def _on_blender_module_loaded(self):
        super()._on_blender_module_loaded()
        self._invoke_on_ui_thread(self._dismiss_blender_progress_dialog)

    def _on_blender_mode_stopped(self):
        super()._on_blender_mode_stopped()
        self._invoke_on_ui_thread(self._close_blender_log_capture)
        self._invoke_on_ui_thread(self._show_internal_workspace)

    def _on_blender_selection_changed(self, instance_ids: list[int]):
        def _apply():
            prev = self._selection_sync_in_progress
            self._selection_sync_in_progress = True
            try:
                resolved = [inst for inst in (self._instance_id_lookup.get(instance_id) for instance_id in instance_ids) if inst is not None]
                self.set_selection(cast("list[GITInstance]", resolved))
            finally:
                self._selection_sync_in_progress = prev

        self._invoke_on_ui_thread(_apply)

    def _on_blender_transform_changed(
        self,
        instance_id: int,
        position: dict | None,
        rotation: dict | None,
    ):
        def _apply():
            # Set flag to prevent sync loop
            prev = self._transform_sync_in_progress
            self._transform_sync_in_progress = True
            try:
                instance = self._instance_id_lookup.get(instance_id)
                if instance is None:
                    return
                mutated = False

                if position:
                    current_position = Vector3(
                        instance.position.x,
                        instance.position.y,
                        instance.position.z,
                    )
                    new_position = Vector3(
                        position.get("x", current_position.x),
                        position.get("y", current_position.y),
                        position.get("z", current_position.z),
                    )
                    if not self._vector3_close(current_position, new_position):
                        self.undo_stack.push(MoveCommand(instance, current_position, new_position))
                        mutated = True

                if rotation and isinstance(instance, _BEARING_CLASSES) and "euler" in rotation:
                    new_bearing = rotation["euler"].get("z")
                    if new_bearing is not None and not math.isclose(instance.bearing, new_bearing, abs_tol=1e-4):
                        self.undo_stack.push(RotateCommand(instance, instance.bearing, float(new_bearing)))
                        mutated = True

                if rotation and isinstance(instance, GITCamera) and "quaternion" in rotation:
                    quat = rotation["quaternion"]
                    current_orientation = Vector4(
                        instance.orientation.x,
                        instance.orientation.y,
                        instance.orientation.z,
                        instance.orientation.w,
                    )
                    new_orientation = Vector4(
                        quat.get("x", current_orientation.x),
                        quat.get("y", current_orientation.y),
                        quat.get("z", current_orientation.z),
                        quat.get("w", current_orientation.w),
                    )
                    if not self._vector4_close(current_orientation, new_orientation):
                        self.undo_stack.push(RotateCommand(instance, current_orientation, new_orientation))
                        mutated = True

                if mutated:
                    self._after_instance_mutation(instance)
            finally:
                self._transform_sync_in_progress = prev

        self._invoke_on_ui_thread(_apply)

    def _on_blender_context_menu_requested(self, instance_ids: list[int]):
        def _apply():
            resolved = [inst for inst in (self._instance_id_lookup.get(instance_id) for instance_id in instance_ids) if inst is not None]
            if not resolved:
                return
            prev = self._selection_sync_in_progress
            self._selection_sync_in_progress = True
            try:
                self.set_selection(cast("list[GITInstance]", resolved))
            finally:
                self._selection_sync_in_progress = prev
            menu = self.on_context_menu_selection_exists(instances=resolved, get_menu=True)
            if menu is not None:
                self.show_final_context_menu(menu)

        self._invoke_on_ui_thread(_apply)

    def _on_blender_instance_changed(self, action: str, payload: dict):
        def _apply():
            if action == "added":
                self._handle_blender_instance_added(payload)
            elif action == "removed":
                self._handle_blender_instance_removed(payload)

        self._invoke_on_ui_thread(_apply)

    def _on_blender_instance_updated(self, instance_id: int, properties: dict):
        def _apply():
            instance = self._instance_id_lookup.get(instance_id)
            if instance is None:
                return
            self._apply_blender_property_updates(instance, properties)

        self._invoke_on_ui_thread(_apply)

    def _on_blender_material_changed(self, payload: dict):
        """Handle material/texture changes from Blender."""

        def _apply():
            object_name = payload.get("object_name", "")
            material_data = payload.get("material", {})
            model_name = payload.get("model_name")

            if not model_name:
                return

            self.log.info(f"Material changed for {object_name} (model: {model_name})")

            # If textures were changed, we need to export the MDL and reload it
            if "diffuse_texture" in material_data or "lightmap_texture" in material_data:
                # Request MDL export from Blender
                if self._is_blender_mode_enabled() and self._blender_controller is not None:
                    # Export MDL to a temp location
                    import tempfile

                    temp_mdl = tempfile.NamedTemporaryFile(suffix=".mdl", delete=False)
                    temp_mdl.close()

                    # Use IPC to export MDL
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
                            self.log.info(f"Exported updated MDL to {temp_mdl.name}")
                            # TODO: Reload the MDL in the toolset and update the module
                            # This would require finding the MDL resource in the module
                            # and replacing it with the exported version

        self._invoke_on_ui_thread(_apply)

    def update_status_bar(
        self,
        mouse_pos: QPoint | Vector2,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
        renderer: WalkmeshRenderer | ModuleRenderer,
    ):
        """Update the status bar, using rich text formatting for improved clarity."""

        if isinstance(mouse_pos, QPoint):
            assert not isinstance(mouse_pos, Vector2)
            norm_mouse_pos = Vector2(float(mouse_pos.x()), float(mouse_pos.y()))
        else:
            norm_mouse_pos = mouse_pos

        # Get semantic colors from palette
        colors = self._get_semantic_colors()

        # Mouse and camera info
        if isinstance(renderer, ModuleRenderer):
            # Check if scene is initialized before accessing it
            if renderer._scene is None:
                self.mouse_pos_label.setText(
                    f"<b><span style='{self._emoji_style}'>🖱</span>&nbsp;Coords:</b> <span style='font-style:italic; color:{colors['muted']}'>— not available —</span>"
                )
                self.view_camera_label.setText(
                    f"<b><span style='{self._emoji_style}'>🎥</span>&nbsp;View:</b> <span style='font-style:italic; color:{colors['muted']}'>— not available —</span>"
                )
            else:
                pos = renderer.scene.cursor.position()
                world_pos_3d = Vector3(pos.x, pos.y, pos.z)
                world_pos = world_pos_3d
                self.mouse_pos_label.setText(
                    f"<b><span style='{self._emoji_style}'>🖱</span>&nbsp;Coords:</b> "
                    f"<span style='color:{colors['accent1']}'>{world_pos_3d.y:.2f}</span>, "
                    f"<span style='color:{colors['accent2']}'>{world_pos_3d.z:.2f}</span>"
                )

                camera = renderer.scene.camera
                cam_text = (
                    f"<b><span style='{self._emoji_style}'>🎥</span>&nbsp;View:</b> "
                    f"<span style='color:{colors['warn']}'>Pos ("
                    f"{camera.x:.2f}, {camera.y:.2f}, {camera.z:.2f}</span>), "
                    f"Pitch: <span style='color:{colors['accent3']}'>{camera.pitch:.2f}</span>, "
                    f"Yaw: <span style='color:{colors['accent3']}'>{camera.yaw:.2f}</span>, "
                    f"FOV: <span style='color:{colors['info']}'>{camera.fov:.2f}</span>"
                )
                self.view_camera_label.setText(cam_text)
        else:
            if isinstance(norm_mouse_pos, Vector2):
                norm_mouse_pos = Vector2(float(norm_mouse_pos.x), float(norm_mouse_pos.y))
            else:
                norm_mouse_pos = Vector2(float(norm_mouse_pos.x()), float(norm_mouse_pos.y()))
            world_pos = renderer.to_world_coords(norm_mouse_pos.x, norm_mouse_pos.y)
            self.mouse_pos_label.setText(f"<b><span style='{self._emoji_style}'>🖱</span>&nbsp;Coords:</b> <span style='color:{colors['accent1']}'>{world_pos.y:.2f}</span>")
            self.view_camera_label.setText(
                f"<b><span style='{self._emoji_style}'>🎥</span>&nbsp;View:</b> <span style='font-style:italic; color:{colors['muted']}'>— not available —</span>"
            )

        # Format keys and buttons using shared utility
        self.buttons_keys_pressed_label.setText(format_status_bar_keys_and_buttons(keys, buttons, self._emoji_style, colors["accent3"], colors["accent2"]))

        # Selected instance with better style
        if self.selected_instances:
            instance = self.selected_instances[0]
            if isinstance(instance, GITCamera):
                instance_name = f"<span style='color:{colors['warn']}'>[Camera]</span> <code>{instance!r}</code>"
            else:
                instance_name = f"<span style='color:{colors['accent1']}'>{instance.identifier()}</span>"
            self.selected_instance_label.setText(f"<b><span style='{self._emoji_style}'>🟦</span>&nbsp;Selected Instance:</b> {instance_name}")
        else:
            self.selected_instance_label.setText(
                f"<b><span style='{self._emoji_style}'>🟦</span>&nbsp;Selected Instance:</b> <span style='color:{colors['muted']}'><i>None</i></span>"
            )

    def _refresh_window_title(self):
        if self._module is None:
            title = f"No Module - {self._installation.name} - Module Designer[*]"
        else:
            title = f"{self._module.root()} - {self._installation.name} - Module Designer[*]"
        self.setWindowTitle(title)
        self.setWindowModified(self.has_unsaved_changes())

    def on_lyt_updated(self, lyt: LYT):
        """Handle LYT updates from the editor."""
        if self._module is not None:
            layout = self._module.layout()
            if layout is not None:
                layout.save()
            self.rebuild_resource_tree()

    def open_module_with_dialog(self):
        dialog = SelectModuleDialog(self, self._installation)

        if dialog.exec():
            mod_filepath = self._installation.module_path().joinpath(dialog.module)

            # Only consider Blender if enabled in Module Designer settings
            self._blender_choice_made = True  # Mark that we've checked
            if self.settings.useBlender:
                use_blender, blender_info = check_blender_and_ask(self, "Module Designer")
                if blender_info is not None:
                    self._use_blender_mode = use_blender
                else:
                    self._use_blender_mode = False
            else:
                self._use_blender_mode = False

            self.open_module(mod_filepath)

    #    @with_variable_trace(Exception)
    def open_module(
        self,
        mod_filepath: Path,
    ):
        """Opens a module."""
        # Check for Blender if not already checked (when opening directly via constructor or file)
        if not self._blender_choice_made:
            self._blender_choice_made = True
            # Only consider Blender when enabled in Module Designer settings (disabled by default)
            if not self.settings.useBlender:
                self._use_blender_mode = False
            else:
                blender_settings = get_blender_settings()

                # Check if user has a remembered preference
                if blender_settings.remember_choice:
                    # Use remembered preference
                    self._use_blender_mode = blender_settings.prefer_blender
                else:
                    # Show dialog to ask user (if Blender is detected)
                    blender_info = blender_settings.get_blender_info()
                    if blender_info.is_valid:
                        use_blender, blender_info_result = check_blender_and_ask(self, "Module Designer")
                        if blender_info_result is not None:
                            self._use_blender_mode = use_blender
                        # If user cancelled, default to built-in
                        elif use_blender is False and blender_info_result is None:
                            self._use_blender_mode = False
                    else:
                        # Blender not available, use built-in
                        self._use_blender_mode = False

        mod_root: str = self._installation.get_module_root(mod_filepath)
        mod_filepath = self._ensure_mod_file(mod_filepath, mod_root)

        self.unload_module()
        combined_module = Module(mod_root, self._installation, use_dot_mod=is_mod_file(mod_filepath))
        git_module = combined_module.git()
        if git_module is None:
            raise ValueError(f"This module '{mod_root}' is missing a GIT!")
        git: GIT | None = git_module.resource()
        if git is None:
            raise ValueError(f"This module '{mod_root}' is missing a GIT!")

        walkmeshes: list[BWM] = []
        for mod_resource in combined_module.resources.values():
            res_obj = mod_resource.resource()
            if res_obj is not None and mod_resource.restype() == ResourceType.WOK:
                walkmeshes.append(res_obj)
        self._last_walkmeshes = walkmeshes
        result: tuple[Module, GIT, list[BWM]] = (combined_module, git, walkmeshes)
        new_module, git, walkmeshes = result
        self._module = new_module
        if self._lyt_renderer is not None:
            self._lyt_renderer.set_module(new_module)

        # Get LYT for Blender mode
        lyt: LYT | None = None
        lyt_module = combined_module.layout()
        if lyt_module is not None:
            lyt = lyt_module.resource()
        if lyt is None:
            lyt = LYT()

        # Start Blender mode if requested
        if self._use_blender_mode:
            self._prepare_for_blender_session(mod_root)
            blender_started = self.start_blender_mode(
                lyt=lyt,
                git=git,
                walkmeshes=walkmeshes,
                module_root=mod_root,
                installation_path=self._installation.path(),
            )
            if blender_started:
                self.setWindowTitle(f"Module Designer - {mod_root} (Blender Mode)")
            else:
                # Fall back to built-in if Blender fails
                self._use_blender_mode = False
                self.log.warning("Blender mode failed, using built-in renderer")

        if not self._use_blender_mode:
            self.ui.flatRenderer.set_git(git)
            try:
                self.ui.mainRenderer.initialize_renderer(self._installation, new_module)
            except RuntimeError as exc:
                self.log.warning(
                    "ModuleRenderer OpenGL initialization failed; continuing with limited non-3D functionality: %s",
                    exc,
                )
            if self.ui.mainRenderer._scene:
                self.ui.mainRenderer._scene.show_cursor = self.ui.cursorCheck.isChecked()
            self.ui.flatRenderer.set_walkmeshes(walkmeshes)
            self.ui.flatRenderer.center_camera()
            self.setWindowTitle(f"Module Designer - {mod_root}")
        else:
            self._show_blender_workspace()

        self.show()
        # Inherently calls On3dSceneInitialized when done.

        # Mark initial state as clean (no unsaved changes)
        self._mark_clean_state()

    def _ensure_mod_file(self, mod_filepath: Path, mod_root: str) -> Path:
        mod_file = mod_filepath.with_name(f"{mod_root}.mod")
        if not mod_file.is_file():
            if self._confirm_create_mod(mod_root):
                self._create_mod(mod_file, mod_root)
                return mod_file
            return mod_filepath

        if mod_file != mod_filepath and not self._confirm_use_mod(mod_filepath, mod_file):
            return mod_filepath
        return mod_file

    def _confirm_create_mod(self, mod_root: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Editing .RIM/.ERF modules is discouraged.",
                f"The Module Designer would like to create a .mod for module '{mod_root}', would you like to do this now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _create_mod(self, mod_file: Path, mod_root: str):
        self.log.info("Creating '%s.mod' from the rims/erfs...", mod_root)
        module.rim_to_mod(mod_file, game=self._installation.game())
        self._installation.reload_module(mod_file.name)

    def _confirm_use_mod(self, orig_filepath: Path, mod_filepath: Path) -> bool:
        return (
            QMessageBox.question(
                self,
                f"{orig_filepath.suffix} file chosen when {mod_filepath.suffix} preferred.",
                (
                    f"You've chosen '{orig_filepath.name}' with a '{orig_filepath.suffix}' extension.<br><br>"
                    f"The Module Designer recommends modifying .mod's.<br><br>"
                    f"Use '{mod_filepath.name}' instead?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )

    def unload_module(self):
        self._module = None
        self.ui.mainRenderer.shutdown_renderer()

    def show_help_window(self):
        window = HelpWindow(self, "./help/tools/1-moduleEditor.md")
        window.show()

    def open_settings_dialog(self):
        """Open the settings dialog for the module designer."""
        from toolset.gui.dialogs.settings import SettingsDialog

        dialog = SettingsDialog(self)
        # Navigate directly to the Module Designer settings page
        for i in range(dialog.ui.settingsTree.topLevelItemCount()):
            item = dialog.ui.settingsTree.topLevelItem(i)
            if item and item.text(0) == "Module Designer":
                dialog.ui.settingsTree.setCurrentItem(item)
                dialog.on_page_change(item)
                break
        dialog.exec()

    def git(self) -> GIT:
        assert self._module is not None
        git = self._module.git()
        assert git is not None
        git_resource = git.resource()
        assert git_resource is not None
        return git_resource

    def are(self) -> ARE:
        assert self._module is not None
        are = self._module.are()
        assert are is not None
        are_resource = are.resource()
        assert are_resource is not None
        return are_resource

    def ifo(self) -> IFO:
        assert self._module is not None
        ifo = self._module.info()
        assert ifo is not None
        ifo_resource = ifo.resource()
        assert ifo_resource is not None
        return ifo_resource

    def save_git(self):
        assert self._module is not None
        git_module = self._module.git()
        assert git_module is not None
        git_module.save()

        # Also save the layout if it has been modified
        layout_module = self._module.layout()
        if layout_module is not None:
            layout_module.save()

        # Mark the current state as clean after saving
        self._mark_clean_state()

    def rebuild_resource_tree(self):
        """Rebuilds the resource tree widget.

        Rebuilds the resource tree widget by:
            - Clearing existing items
            - Enabling the tree
            - Grouping resources by type into categories
            - Adding category items and resource items
            - Sorting items alphabetically.
        """
        # Only build if module is loaded
        if self._module is None:
            self.ui.resourceTree.setEnabled(False)
            return

        # Block signals and sorting during bulk update for better performance
        self.ui.resourceTree.blockSignals(True)
        self.ui.resourceTree.setSortingEnabled(False)
        self.ui.resourceTree.clear()
        self.ui.resourceTree.setEnabled(True)

        categories: dict[ResourceType, QTreeWidgetItem] = {
            ResourceType.UTC: QTreeWidgetItem(["Creatures"]),
            ResourceType.UTP: QTreeWidgetItem(["Placeables"]),
            ResourceType.UTD: QTreeWidgetItem(["Doors"]),
            ResourceType.UTI: QTreeWidgetItem(["Items"]),
            ResourceType.UTE: QTreeWidgetItem(["Encounters"]),
            ResourceType.UTT: QTreeWidgetItem(["Triggers"]),
            ResourceType.UTW: QTreeWidgetItem(["Waypoints"]),
            ResourceType.UTS: QTreeWidgetItem(["Sounds"]),
            ResourceType.UTM: QTreeWidgetItem(["Merchants"]),
            ResourceType.DLG: QTreeWidgetItem(["Dialogs"]),
            ResourceType.FAC: QTreeWidgetItem(["Factions"]),
            ResourceType.MDL: QTreeWidgetItem(["Models"]),
            ResourceType.TGA: QTreeWidgetItem(["Textures"]),
            ResourceType.NCS: QTreeWidgetItem(["Scripts"]),
            ResourceType.IFO: QTreeWidgetItem(["Module Data"]),
            ResourceType.INVALID: QTreeWidgetItem(["Other"]),
        }
        categories[ResourceType.MDX] = categories[ResourceType.MDL]
        categories[ResourceType.WOK] = categories[ResourceType.MDL]
        categories[ResourceType.TPC] = categories[ResourceType.TGA]
        categories[ResourceType.IFO] = categories[ResourceType.IFO]
        categories[ResourceType.ARE] = categories[ResourceType.IFO]
        categories[ResourceType.GIT] = categories[ResourceType.IFO]
        categories[ResourceType.LYT] = categories[ResourceType.IFO]
        categories[ResourceType.VIS] = categories[ResourceType.IFO]
        categories[ResourceType.PTH] = categories[ResourceType.IFO]
        categories[ResourceType.NSS] = categories[ResourceType.NCS]

        for value in categories.values():
            self.ui.resourceTree.addTopLevelItem(value)

        for resource in self._module.resources.values():
            item = QTreeWidgetItem([f"{resource.resname()}.{resource.restype().extension}"])
            item.setData(0, Qt.ItemDataRole.UserRole, resource)
            category: QTreeWidgetItem = categories.get(resource.restype(), categories[ResourceType.INVALID])
            category.addChild(item)

        self.ui.resourceTree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.ui.resourceTree.setSortingEnabled(True)

        # Restore signals after bulk update
        self.ui.resourceTree.blockSignals(False)

        # Apply current search filter
        filter_text = self.ui.resourceSearchEdit.text()
        if filter_text:
            self._filter_resource_tree(filter_text)

    def _filter_resource_tree(self, text: str):
        """Show/hide resource tree items based on search text."""
        text_lower = text.lower()
        tree = self.ui.resourceTree
        for group_idx in range(tree.topLevelItemCount()):
            group_node = tree.topLevelItem(group_idx)
            if group_node is None:
                continue
            visible_children = 0
            for child_idx in range(group_node.childCount()):
                child = group_node.child(child_idx)
                if child is None:
                    continue
                matches = not text_lower or text_lower in child.text(0).lower()
                child.setHidden(not matches)
                if matches:
                    visible_children += 1
            group_node.setHidden(visible_children == 0)
            # Auto-expand groups with matches when searching
            if text_lower and visible_children > 0:
                group_node.setExpanded(True)

    def open_module_resource(self, resource: ModuleResource):
        active_path = resource.active()
        if active_path is None:
            QMessageBox(
                QMessageBox.Icon.Critical,
                "Failed to open editor",
                f"Resource {resource.identifier()} has no active file path.",
            ).exec()
            return
        editor: Editor | QMainWindow | None = open_resource_editor(
            active_path,
            installation=self._installation,
            parent_window=self,
            resname=resource.resname(),
            restype=resource.restype(),
            data=resource.data(),
        )[1]

        if editor is None:
            QMessageBox(
                QMessageBox.Icon.Critical,
                "Failed to open editor",
                f"Failed to open editor for file: {resource.identifier()}",
            ).exec()
        elif isinstance(editor, Editor):
            editor.sig_saved_file.connect(lambda: self._on_saved_resource(resource))

    def copy_resource_to_override(self, resource: ModuleResource):
        location = self._installation.override_path() / f"{resource.identifier()}"
        data = resource.data()
        if data is None:
            RobustLogger().error(f"Cannot find resource {resource.identifier()} anywhere to copy to Override. Locations: {resource.locations()}")
            return
        location.write_bytes(data)
        resource.add_locations([location])
        resource.activate(location)
        scene = self.ui.mainRenderer._scene
        if scene is not None:
            scene.clear_cache_buffer.append(resource.identifier())

    def activate_resource_file(
        self,
        resource: ModuleResource,
        location: os.PathLike | str,
    ):
        resource.activate(location)
        scene = self.ui.mainRenderer._scene
        if scene is not None:
            scene.clear_cache_buffer.append(resource.identifier())

    def select_resource_item(
        self,
        instance: GITInstance,
        *,
        clear_existing: bool = True,
    ):
        if clear_existing:
            self.ui.resourceTree.clearSelection()
        this_ident = instance.identifier()
        if this_ident is None:  # Should only ever be None for GITCamera.
            assert isinstance(instance, GITCamera), f"Should only ever be None for GITCamera, not {type(instance).__name__}."
            return

        for i in range(self.ui.resourceTree.topLevelItemCount()):
            parent: QTreeWidgetItem | None = self.ui.resourceTree.topLevelItem(i)
            if parent is None:
                self.log.warning("parent was None in ModuleDesigner.selectResourceItem()")
                continue
            for j in range(parent.childCount()):
                item = parent.child(j)
                if item is None:
                    self.log.warning(f"parent.child({j}) was somehow None in selectResourceItem")
                    continue
                res: ModuleResource = item.data(0, Qt.ItemDataRole.UserRole)
                if not isinstance(res, ModuleResource):
                    self.log.warning("item.data(0, Qt.ItemDataRole.UserRole) returned non ModuleResource in ModuleDesigner.selectResourceItem(): %s", safe_repr(res))
                    continue
                if res.identifier() != this_ident:
                    continue
                self.log.debug("Selecting ModuleResource in selectResourceItem loop: %s", res.identifier())
                parent.setExpanded(True)
                item.setSelected(True)
                self.ui.resourceTree.scrollToItem(item)

    def select_resource_items(
        self,
        instances: Sequence[GITInstance],
        *,
        clear_existing: bool = True,
    ):
        """Select all matching resources in the resource tree for the provided instances."""
        if clear_existing:
            self.ui.resourceTree.clearSelection()

        first_match: QTreeWidgetItem | None = None
        identifier_lookup: set[ResourceIdentifier] = set()
        for instance in instances:
            this_ident = instance.identifier()
            if this_ident is not None:
                identifier_lookup.add(this_ident)

        if not identifier_lookup:
            return

        for i in range(self.ui.resourceTree.topLevelItemCount()):
            parent = self.ui.resourceTree.topLevelItem(i)
            if parent is None:
                continue
            for j in range(parent.childCount()):
                item = parent.child(j)
                if item is None:
                    continue
                res = item.data(0, Qt.ItemDataRole.UserRole)
                if not isinstance(res, ModuleResource):
                    continue
                if res.identifier() not in identifier_lookup:
                    continue
                parent.setExpanded(True)
                item.setSelected(True)
                if first_match is None:
                    first_match = item

        if first_match is not None:
            self.ui.resourceTree.scrollToItem(first_match)

    def rebuild_instance_list(self):
        self.log.debug("rebuildInstanceList called.")

        # Only build if module is loaded
        if self._module is None:
            self.ui.instanceTree.setEnabled(False)
            self.ui.rightPanel.setVisible(False)
            return

        # Block signals during bulk update for better performance
        self.ui.instanceTree.blockSignals(True)
        self.ui.instanceTree.clear()
        self.ui.instanceTree.setEnabled(True)
        self.ui.rightPanel.setVisible(True)

        hidden_mapping = self._hidden_instance_class_mapping()
        icon_mapping: dict[type[GITInstance], QPixmap] = {
            GITCreature: QPixmap(":/images/icons/k1/creature.png"),
            GITPlaceable: QPixmap(":/images/icons/k1/placeable.png"),
            GITDoor: QPixmap(":/images/icons/k1/door.png"),
            GITSound: QPixmap(":/images/icons/k1/sound.png"),
            GITTrigger: QPixmap(":/images/icons/k1/trigger.png"),
            GITEncounter: QPixmap(":/images/icons/k1/encounter.png"),
            GITWaypoint: QPixmap(":/images/icons/k1/waypoint.png"),
            GITCamera: QPixmap(":/images/icons/k1/camera.png"),
            GITStore: QPixmap(":/images/icons/k1/merchant.png"),
            GITInstance: QPixmap(32, 32),
        }
        # Mapping from GIT instance class to group label
        group_label_mapping: dict[type[GITInstance], str] = {
            GITCreature: "Creatures",
            GITPlaceable: "Placeables",
            GITDoor: "Doors",
            GITTrigger: "Triggers",
            GITEncounter: "Encounters",
            GITWaypoint: "Waypoints",
            GITSound: "Sounds",
            GITStore: "Stores",
            GITCamera: "Cameras",
        }

        if self._module is None:
            return
        git_module = self._module.git()
        if git_module is None:
            return
        git_resource = git_module.resource()
        if git_resource is None:
            return
        git: GIT = git_resource

        # Build room buckets from layout (scene hierarchy: Module -> Area -> Rooms -> Objects)
        lyt: LYT | None = None
        layout_module = self._module.layout()
        if layout_module is not None:
            lyt = layout_module.resource()
        room_buckets: list[tuple[str, str, Vector3, BWM | None]] = []
        room_walkmeshes: dict[str, BWM] = {}
        for module_resource in self._module.resources.values():
            if module_resource.restype() != ResourceType.WOK:
                continue
            resource_obj = module_resource.resource()
            if isinstance(resource_obj, BWM):
                room_walkmeshes[module_resource.resname().lower()] = resource_obj

        if lyt is not None:
            for idx, room in enumerate(lyt.rooms):
                room_key = f"room:{idx}"
                room_label = f"Room {idx + 1}: {room.model}"
                room_walkmesh = room_walkmeshes.get(room.model.lower())
                room_buckets.append((room_key, room_label, room.position, room_walkmesh))

        grouped_by_room: dict[str, dict[type[GITInstance], list[tuple[str, str, str, QIcon, GITInstance, QFont]]]] = {}

        def _ensure_room_group(room_key: str) -> dict[type[GITInstance], list[tuple[str, str, str, QIcon, GITInstance, QFont]]]:
            if room_key not in grouped_by_room:
                grouped_by_room[room_key] = {cls: [] for cls in group_label_mapping}
            return grouped_by_room[room_key]

        def _instance_room_key(instance: GITInstance) -> str:
            if not room_buckets:
                return "room:unassigned"

            best_containing_key: str | None = None
            best_containing_score = float("inf")
            for room_key, _room_label, room_pos, room_walkmesh in room_buckets:
                if room_walkmesh is None:
                    continue

                world_face = room_walkmesh.faceAt(instance.position.x, instance.position.y)
                local_x = instance.position.x - room_pos.x
                local_y = instance.position.y - room_pos.y
                local_face = room_walkmesh.faceAt(local_x, local_y)

                contains_world = world_face is not None
                contains_local = local_face is not None
                if not contains_world and not contains_local:
                    continue

                world_z_delta = float("inf")
                if world_face is not None:
                    world_z = world_face.determine_z(instance.position.x, instance.position.y)
                    world_z_delta = abs(instance.position.z - world_z)

                local_z_delta = float("inf")
                if local_face is not None:
                    local_z = local_face.determine_z(local_x, local_y) + room_pos.z
                    local_z_delta = abs(instance.position.z - local_z)

                z_delta = min(world_z_delta, local_z_delta)
                dx = instance.position.x - room_pos.x
                dy = instance.position.y - room_pos.y
                planar_distance_sq = dx * dx + dy * dy
                containing_score = z_delta * z_delta + planar_distance_sq * 0.01

                if containing_score < best_containing_score:
                    best_containing_score = containing_score
                    best_containing_key = room_key

            if best_containing_key is not None:
                return best_containing_key

            best_key = "room:unassigned"
            best_distance = float("inf")
            for room_key, _room_label, room_pos, _room_walkmesh in room_buckets:
                dx = instance.position.x - room_pos.x
                dy = instance.position.y - room_pos.y
                dz = instance.position.z - room_pos.z
                distance_sq = dx * dx + dy * dy + dz * dz
                if distance_sq < best_distance:
                    best_distance = distance_sq
                    best_key = room_key
            return best_key

        for instance in git.instances():
            cls = instance.__class__
            if hidden_mapping.get(cls, False):
                continue

            struct_index: int = git.index(instance)
            icon = QIcon(icon_mapping.get(cls, icon_mapping[GITInstance]))
            font = self.ui.instanceTree.font()

            if isinstance(instance, GITCamera):
                name = f"Camera #{instance.camera_id}"
                tooltip = f"Struct Index: {struct_index}\nCamera ID: {instance.camera_id}\nFOV: {instance.fov}"
                sort_key = "cam" + str(instance.camera_id).rjust(10, "0")
            else:
                this_ident = instance.identifier()
                assert this_ident is not None
                resname: str = this_ident.resname
                name = resname
                tag: str = ""
                module_resource: ModuleResource[ARE] | None = self._module.resource(this_ident.resname, this_ident.restype)
                if module_resource is None:
                    continue
                abstracted_resource = module_resource.resource()
                if abstracted_resource is None:
                    continue

                if isinstance(instance, GITDoor) or (isinstance(instance, GITTrigger) and module_resource):
                    name = module_resource.localized_name() or resname
                    tag = instance.tag
                elif isinstance(instance, GITWaypoint):
                    name = self._installation.string(instance.name)
                    tag = instance.tag
                elif module_resource:
                    name = module_resource.localized_name() or resname
                    tag = abstracted_resource.tag

                if module_resource is None:
                    font = QFont(font)
                    font.setItalic(True)

                tooltip = f"Struct Index: {struct_index}\nResRef: {resname}\nName: {name}\nTag: {tag}"
                ident = instance.identifier()
                assert ident is not None
                sort_key = ident.restype.extension + name

            room_key = _instance_room_key(instance)
            room_group = _ensure_room_group(room_key)
            if cls in room_group:
                room_group[cls].append((sort_key, name, tooltip, icon, instance, font))

        module_label = "Module"
        info_module = self._module.info()
        if info_module is not None:
            module_label = f"Module: {info_module.resname().upper()}"

        area_label = "Area"
        are_module = self._module.are()
        if are_module is not None:
            area_label = f"Area: {are_module.resname().upper()}"

        module_node = QTreeWidgetItem(self.ui.instanceTree)
        module_node.setText(0, module_label)
        module_node.setFlags(module_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore[operator]
        module_node.setExpanded(True)

        area_node = QTreeWidgetItem(module_node)
        area_node.setText(0, area_label)
        area_node.setFlags(area_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore[operator]
        area_node.setExpanded(True)

        ordered_rooms: list[tuple[str, str]] = [(room_key, room_label) for room_key, room_label, _pos, _walkmesh in room_buckets]
        ordered_rooms.append(("room:unassigned", "Unassigned"))

        for room_key, room_label in ordered_rooms:
            room_group = grouped_by_room.get(room_key)
            if not room_group:
                continue

            room_count = sum(len(entries) for entries in room_group.values())
            if room_count == 0:
                continue

            room_node = QTreeWidgetItem(area_node)
            room_node.setText(0, f"{room_label} ({room_count})")
            room_node.setFlags(room_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore[operator]
            room_node.setExpanded(True)

            for cls, label in group_label_mapping.items():
                entries = room_group.get(cls, [])
                if not entries:
                    continue
                entries.sort(key=lambda e: e[0])

                type_node = QTreeWidgetItem(room_node)
                type_node.setText(0, f"{label} ({len(entries)})")
                type_node.setIcon(0, QIcon(icon_mapping.get(cls, icon_mapping[GITInstance])))
                type_node.setFlags(type_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore[operator]
                type_node.setExpanded(True)

                for sort_key, name, tooltip, icon, instance, font in entries:
                    child = QTreeWidgetItem(type_node)
                    child.setText(0, name)
                    child.setIcon(0, icon)
                    child.setFont(0, font)
                    child.setToolTip(0, tooltip)
                    child.setData(0, Qt.ItemDataRole.UserRole, instance)
                    child.setData(0, Qt.ItemDataRole.UserRole + 1, sort_key)

        # Restore signals after bulk update
        self.ui.instanceTree.blockSignals(False)

        # Apply current search filter
        filter_text = self.ui.instanceSearchEdit.text()
        if filter_text:
            self._filter_instance_tree(filter_text)

        self._refresh_instance_id_lookup()

    def _filter_instance_tree(self, text: str):
        """Show/hide instance tree items based on search text."""
        text_lower = text.lower()
        tree = self.ui.instanceTree

        def _apply(item: QTreeWidgetItem) -> bool:
            self_match = not text_lower or text_lower in item.text(0).lower()
            if item.childCount() == 0:
                item.setHidden(not self_match)
                return self_match

            visible_child = False
            for idx in range(item.childCount()):
                child = item.child(idx)
                if child is None:
                    continue
                if _apply(child):
                    visible_child = True

            visible = self_match or visible_child
            item.setHidden(not visible)
            if text_lower:
                item.setExpanded(visible_child)
            return visible

        for root_idx in range(tree.topLevelItemCount()):
            root = tree.topLevelItem(root_idx)
            if root is None:
                continue
            _apply(root)

    def _refresh_instance_id_lookup(self):
        """Cache Python object ids for fast lookup when Blender sends events."""
        self._instance_id_lookup.clear()
        if self._module is None:
            return
        git_module = self._module.git()
        if git_module is None:
            return
        git_resource = git_module.resource()
        if git_resource is None:
            return
        if hasattr(git_resource, "instances"):
            for instance in git_resource.instances():
                self._instance_id_lookup[id(instance)] = instance

    @staticmethod
    def _vector3_close(a: Vector3, b: Vector3, epsilon: float = 1e-4) -> bool:
        return abs(a.x - b.x) <= epsilon and abs(a.y - b.y) <= epsilon and abs(a.z - b.z) <= epsilon

    @staticmethod
    def _vector4_close(a: Vector4, b: Vector4, epsilon: float = 1e-4) -> bool:
        return abs(a.x - b.x) <= epsilon and abs(a.y - b.y) <= epsilon and abs(a.z - b.z) <= epsilon and abs(a.w - b.w) <= epsilon

    def _after_instance_mutation(
        self,
        instance: GITInstance | None,
        *,
        refresh_lists: bool = False,
    ):
        self._invalidate_scene_and_update_renderers(update_flat=True)

        # Sync instance to Blender if not already syncing from Blender
        if (
            instance is not None
            and self.is_blender_mode()
            and self._blender_controller is not None
            and not self._transform_sync_in_progress
            and not self._property_sync_in_progress
        ):
            self.sync_instance_to_blender(instance)

        if refresh_lists:
            selected = list(self.selected_instances)
            self.rebuild_instance_list()
            if selected:
                self.set_selection(selected)

    def _construct_instance_from_blender_payload(self, payload: dict[str, Any]) -> GITInstance | None:
        instance_block = payload.get("instance") or payload
        data = deserialize_git_instance(instance_block)
        type_name = data.get("type")
        position = data.get("position", (0.0, 0.0, 0.0))

        type_map: dict[str, type[GITInstance]] = {
            "GITCamera": GITCamera,
            "GITCreature": GITCreature,
            "GITDoor": GITDoor,
            "GITEncounter": GITEncounter,
            "GITPlaceable": GITPlaceable,
            "GITSound": GITSound,
            "GITStore": GITStore,
            "GITTrigger": GITTrigger,
            "GITWaypoint": GITWaypoint,
        }

        cls = type_map.get(type_name or "")
        if cls is None:
            self.log.warning("Blender requested unsupported instance type: %s", type_name)
            return None

        instance = cls(position[0], position[1], position[2])
        self._apply_deserialized_instance_data(instance, data)
        return instance

    def _apply_deserialized_instance_data(self, instance: GITInstance, data: dict[str, Any]):
        pos = data.get("position")
        if pos is not None:
            instance.position = Vector3(*pos)

        if "resref" in data and isinstance(instance, _RESREF_CLASSES):
            cast("ResrefInstance", instance).resref = ResRef(str(data["resref"]))
        if "tag" in data and isinstance(instance, _TAG_CLASSES):
            cast("TagInstance", instance).tag = str(data["tag"])
        if "bearing" in data and isinstance(instance, _BEARING_CLASSES):
            typed_instance = cast("BearingInstance", instance)
            typed_instance.bearing = float(data["bearing"])

        if isinstance(instance, GITCamera) and "orientation" in data:
            instance.orientation = Vector4(*data["orientation"])

        if isinstance(instance, GITPlaceable) and "tweak_color" in data:
            tweak_color = data.get("tweak_color")
            instance.tweak_color = Color.from_bgr_integer(int(tweak_color)) if tweak_color is not None else None

        if isinstance(instance, GITTrigger) and "geometry" in data:
            polygon = Polygon3()
            for vertex in data.get("geometry", []):
                polygon.append(Vector3(*vertex))
            instance.geometry = polygon
            instance.tag = data.get("tag", instance.tag)

        if isinstance(instance, GITEncounter):
            polygon = Polygon3()
            for vertex in data.get("geometry", []):
                polygon.append(Vector3(*vertex))
            instance.geometry = polygon
            spawn_points: list[dict[str, Any]] = data.get("spawn_points", [])
            instance.spawn_points.clear()
            for sp_data in spawn_points:
                pos_data = sp_data.get("position", {})
                spawn = GITEncounterSpawnPoint(
                    pos_data.get("x", 0.0),
                    pos_data.get("y", 0.0),
                    pos_data.get("z", 0.0),
                )
                spawn.orientation = sp_data.get("orientation", 0.0)
                instance.spawn_points.append(spawn)

    def _handle_blender_instance_added(self, payload: dict[str, Any]):
        instance = self._construct_instance_from_blender_payload(payload)
        if instance is None:
            return
        git_resource = self.git()
        cmd = _BlenderInsertCommand(git_resource, instance, self)
        self.undo_stack.push(cmd)
        self.set_selection([instance])
        runtime_id = payload.get("runtime_id")
        if runtime_id is not None and self._blender_controller is not None:
            try:
                runtime_key = int(runtime_id)
            except (TypeError, ValueError):
                runtime_key = None
            if runtime_key is not None:
                self._blender_controller.bind_runtime_instance(
                    runtime_key,
                    instance,
                    payload.get("name"),
                )

    def _handle_blender_instance_removed(self, payload: dict[str, Any]):
        instance_id = payload.get("id")
        runtime_id = payload.get("runtime_id")
        instance: GITInstance | None = None
        if instance_id is not None:
            try:
                instance = self._instance_id_lookup.get(int(instance_id))
            except (TypeError, ValueError):
                instance = None
        if instance is None and runtime_id is not None:
            try:
                instance = self._instance_id_lookup.get(int(runtime_id))
            except (TypeError, ValueError):
                instance = None
        if instance is None:
            self.log.warning("Blender removed instance that is unknown to the toolset: %s", payload)
            return
        self.selected_instances = [inst for inst in self.selected_instances if inst is not instance]
        cmd = _BlenderDeleteCommand(self.git(), instance, self)
        self.undo_stack.push(cmd)

    def _queue_blender_property_update(
        self,
        instance: GITInstance,
        key: str,
        value: Any,
    ) -> bool:
        refresh_lists = False
        setter_func: Callable[[GITInstance, Any], None] | None = None
        old_value: Any | None = None
        new_value: Any = value

        def _on_change(refresh: bool) -> Callable[[GITInstance], None]:
            def _handler(inst: GITInstance) -> None:
                self._after_instance_mutation(inst, refresh_lists=refresh)

            return _handler

        if key == "resref" and isinstance(instance, _RESREF_CLASSES):
            typed_instance = cast("ResrefInstance", instance)
            old_value = str(typed_instance.resref)
            new_value = str(value or "")
            refresh_lists = True

            def resref_setter(inst: GITInstance, val: Any) -> None:
                cast("ResrefInstance", inst).resref = ResRef(str(val or ""))

            setter_func = resref_setter

        elif key == "tag" and isinstance(instance, _TAG_CLASSES):
            typed_instance = cast("TagInstance", instance)
            old_value = typed_instance.tag
            new_value = str(value or "")
            refresh_lists = True

            def tag_setter(inst: GITInstance, val: Any) -> None:
                cast("TagInstance", inst).tag = str(val or "")

            setter_func = tag_setter

        elif key == "tweak_color" and isinstance(instance, GITPlaceable):
            current = instance.tweak_color.bgr_integer() if instance.tweak_color else None
            try:
                new_value = int(value) if value is not None else None
            except (TypeError, ValueError):
                new_value = None
            old_value = current
            refresh_lists = False

            def color_setter(inst: GITInstance, val: Any) -> None:
                placeable = cast("GITPlaceable", inst)
                placeable.tweak_color = Color.from_bgr_integer(int(val)) if val is not None else None

            setter_func = color_setter
        else:
            self.log.debug("Ignoring unsupported Blender property update '%s'", key)
            return False

        if old_value == new_value or setter_func is None:
            return False

        command = _BlenderPropertyCommand(
            instance,
            setter_func,
            old_value,
            new_value,
            _on_change(refresh_lists),
            f"Blender set {key}",
        )
        self.undo_stack.push(command)
        return True

    def _apply_blender_property_updates(self, instance: GITInstance, properties: dict[str, Any]):
        any_updates = False
        for key, value in properties.items():
            any_updates |= self._queue_blender_property_update(instance, key, value)

    def select_instance_item_on_list(self, instance: GITInstance):
        self.select_instance_items_on_list([instance])

    def select_instance_items_on_list(
        self,
        instances: Sequence[GITInstance],
        *,
        clear_existing: bool = True,
    ):
        """Select all matching instances in the sidebar tree."""
        if clear_existing:
            self.ui.instanceTree.clearSelection()

        target_ids: set[int] = {id(instance) for instance in instances}
        first_match: QTreeWidgetItem | None = None

        tree = self.ui.instanceTree

        def _visit(node: QTreeWidgetItem) -> None:
            nonlocal first_match
            data = node.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, GITInstance) and id(data) in target_ids:
                node.setSelected(True)
                if first_match is None:
                    first_match = node
            for idx in range(node.childCount()):
                child = node.child(idx)
                if child is not None:
                    _visit(child)

        for root_idx in range(tree.topLevelItemCount()):
            root = tree.topLevelItem(root_idx)
            if root is not None:
                _visit(root)

        if first_match is not None:
            self.ui.instanceTree.scrollToItem(first_match)

    def update_toggles(self):
        scene = self.ui.mainRenderer._scene
        if scene is None:
            return

        hidden_by_instance_type = {
            "creature": not self.ui.viewCreatureCheck.isChecked(),
            "placeable": not self.ui.viewPlaceableCheck.isChecked(),
            "door": not self.ui.viewDoorCheck.isChecked(),
            "trigger": not self.ui.viewTriggerCheck.isChecked(),
            "encounter": not self.ui.viewEncounterCheck.isChecked(),
            "waypoint": not self.ui.viewWaypointCheck.isChecked(),
            "sound": not self.ui.viewSoundCheck.isChecked(),
            "store": not self.ui.viewStoreCheck.isChecked(),
            "camera": not self.ui.viewCameraCheck.isChecked(),
        }

        self._apply_instance_visibility_toggles(scene, hidden_by_instance_type)

        self.ui.mainRenderer.apply_render_overrides(
            backface_culling=self.ui.backfaceCheck.isChecked(),
            use_lightmap=self.ui.lightmapCheck.isChecked(),
            show_cursor=self.ui.cursorCheck.isChecked(),
        )

        # Sync to Blender if active
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            visibility_map = {instance_type: not hidden for instance_type, hidden in hidden_by_instance_type.items()}
            for instance_type, visible in visibility_map.items():
                self._blender_controller.set_visibility(instance_type, visible)

            self._blender_controller.set_render_settings(
                backface_culling=scene.backface_culling,
                use_lightmap=scene.use_lightmap,
                show_cursor=scene.show_cursor,
            )

        self.rebuild_instance_list()

    def _apply_instance_visibility_toggles(self, scene: Any, hidden_by_instance_type: dict[str, bool]) -> None:
        """Apply instance-type visibility flags across editor, 3D scene, and 2D renderer."""

        self.hide_creatures = scene.hide_creatures = self.ui.flatRenderer.hide_creatures = hidden_by_instance_type["creature"]
        self.hide_placeables = scene.hide_placeables = self.ui.flatRenderer.hide_placeables = hidden_by_instance_type["placeable"]
        self.hide_doors = scene.hide_doors = self.ui.flatRenderer.hide_doors = hidden_by_instance_type["door"]
        self.hide_triggers = scene.hide_triggers = self.ui.flatRenderer.hide_triggers = hidden_by_instance_type["trigger"]
        self.hide_encounters = scene.hide_encounters = self.ui.flatRenderer.hide_encounters = hidden_by_instance_type["encounter"]
        self.hide_waypoints = scene.hide_waypoints = self.ui.flatRenderer.hide_waypoints = hidden_by_instance_type["waypoint"]
        self.hide_sounds = scene.hide_sounds = self.ui.flatRenderer.hide_sounds = hidden_by_instance_type["sound"]
        self.hide_stores = scene.hide_stores = self.ui.flatRenderer.hide_stores = hidden_by_instance_type["store"]
        self.hide_cameras = scene.hide_cameras = self.ui.flatRenderer.hide_cameras = hidden_by_instance_type["camera"]

    #    @with_variable_trace(Exception)
    def add_instance(
        self,
        instance: GITObject,
        *,
        walkmesh_snap: bool = True,
    ):
        """Adds a GIT instance to the editor.

        Args:
        ----
            instance: {The instance to add}
            walkmesh_snap (optional): {Whether to snap the instance to the walkmesh}.
        """
        if walkmesh_snap:
            camera_z = self.ui.mainRenderer._scene.camera.z if self.ui.mainRenderer._scene else 0.0
            instance.position.z = self.ui.mainRenderer.walkmesh_point(
                instance.position.x,
                instance.position.y,
                camera_z,
            ).z

        if not isinstance(instance, GITCamera):
            assert self._module is not None
            ident = instance.identifier()
            assert ident is not None
            dialog = InsertInstanceDialog(self, self._installation, self._module, ident.restype)

            if dialog.exec():
                self.rebuild_resource_tree()
                instance.resref = ResRef(dialog.resname)  # pyright: ignore[reportAttributeAccessIssue]
                assert self._module is not None
                git = self._module.git()
                assert git is not None
                git_resource = git.resource()
                assert git_resource is not None
                git_resource.add(instance)

                if isinstance(instance, GITWaypoint):
                    utw: UTW = read_utw(dialog.data)
                    instance.tag = utw.tag
                    instance.name = utw.name
                elif isinstance(instance, GITTrigger):
                    utt: UTT = read_utt(dialog.data)
                    instance.tag = utt.tag
                    if not instance.geometry:
                        RobustLogger().info("Creating default triangle trigger geometry for %s.%s...", instance.resref, "utt")
                        instance.geometry.create_triangle(origin=instance.position)
                elif isinstance(instance, GITEncounter):
                    if not instance.geometry:
                        RobustLogger().info("Creating default triangle trigger geometry for %s.%s...", instance.resref, "ute")
                        instance.geometry.create_triangle(origin=instance.position)
                elif isinstance(instance, GITDoor):
                    utd: module.UTD = read_utd(dialog.data)
                    instance.tag = utd.tag
        else:
            assert self._module is not None
            git_module = self._module.git()
            assert git_module is not None
            git_resource = git_module.resource()
            assert git_resource is not None
            git_resource.add(instance)
        self._invalidate_scene_and_update_renderers()

        # Sync to Blender if not already syncing from Blender
        if self.is_blender_mode() and self._blender_controller is not None and not self._instance_sync_in_progress:
            self.add_instance_to_blender(instance)

        self.rebuild_instance_list()

    #    @with_variable_trace()
    def add_instance_at_cursor(
        self,
        instance: GITObject,
    ):
        scene = self.ui.mainRenderer._scene
        if scene is None:
            self.log.warning("Cannot add instance at cursor while Blender mode controls rendering.")
            return

        instance.position.x = scene.cursor.position().x
        instance.position.y = scene.cursor.position().y
        instance.position.z = scene.cursor.position().z

        if not isinstance(instance, GITCamera):
            assert self._module is not None
            ident = instance.identifier()
            assert ident is not None
            dialog = InsertInstanceDialog(self, self._installation, self._module, ident.restype)

            if dialog.exec():
                self.rebuild_resource_tree()
                instance.resref = ResRef(dialog.resname)  # pyright: ignore[reportAttributeAccessIssue]
                assert self._module is not None
                git = self._module.git()
                assert git is not None
                git_resource = git.resource()
                assert git_resource is not None
                git_resource.add(instance)
        else:
            assert self._module is not None
            if isinstance(instance, (GITEncounter, GITTrigger)) and not instance.geometry:
                self.log.info("Creating default triangle geometry for %s.%s", instance.resref, "utt" if isinstance(instance, GITTrigger) else "ute")
                instance.geometry.create_triangle(origin=instance.position)
            git_module = self._module.git()
            assert git_module is not None
            git_resource = git_module.resource()
            assert git_resource is not None
            git_resource.add(instance)

        # Sync to Blender if not already syncing from Blender
        if self.is_blender_mode() and self._blender_controller is not None and not self._instance_sync_in_progress:
            self.add_instance_to_blender(instance)

        self.rebuild_instance_list()

    #    @with_variable_trace()
    def edit_instance(
        self,
        instance: GITObject | None = None,
    ):
        if instance is None:
            if not self.selected_instances:
                return
            instance = self.selected_instances[0]
        if open_instance_dialog(self, instance, self._installation):
            if not isinstance(instance, GITCamera):
                ident = instance.identifier()
                if ident is not None:
                    scene = self.ui.mainRenderer._scene
                    if scene is not None:
                        scene.clear_cache_buffer.append(ident)

            # Sync property changes to Blender
            if self._is_blender_mode_enabled() and self._blender_controller is not None:
                self.sync_instance_to_blender(instance)

            self.rebuild_instance_list()

    def snap_camera_to_view(
        self,
        git_camera_instance: GITCamera,
    ):
        try:
            view_camera: Camera = self._get_scene_camera()
        except RuntimeError:
            return
        true_pos = view_camera.true_position()
        # Convert vec3 to Vector3
        git_camera_instance.position = Vector3(float(true_pos.x), float(true_pos.y), float(true_pos.z))

        self.undo_stack.push(MoveCommand(git_camera_instance, git_camera_instance.position, git_camera_instance.position))

        self.log.debug("Create RotateCommand for undo/redo functionality")
        pitch = math.pi - (view_camera.pitch + (math.pi / 2))
        yaw = math.pi / 2 - view_camera.yaw
        new_orientation = Vector4.from_euler(yaw, 0, pitch)
        self.undo_stack.push(RotateCommand(git_camera_instance, git_camera_instance.orientation, new_orientation))
        git_camera_instance.orientation = new_orientation

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.update_instance_position(
                git_camera_instance,
                git_camera_instance.position.x,
                git_camera_instance.position.y,
                git_camera_instance.position.z,
            )
            self._blender_controller.update_instance_rotation(
                git_camera_instance,
                orientation=(new_orientation.x, new_orientation.y, new_orientation.z, new_orientation.w),
            )

    def snap_view_to_git_camera(
        self,
        git_camera_instance: GITCamera,
    ):
        try:
            view_camera: Camera = self._get_scene_camera()
        except RuntimeError:
            return
        euler: Vector3 = git_camera_instance.orientation.to_euler()
        view_camera.pitch = math.pi - euler.z - math.radians(git_camera_instance.pitch)
        view_camera.yaw = math.pi / 2 - euler.x
        view_camera.x = git_camera_instance.position.x
        view_camera.y = git_camera_instance.position.y
        view_camera.z = git_camera_instance.position.z + git_camera_instance.height
        view_camera.distance = 0

        # Sync viewport to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.set_camera_view(
                view_camera.x,
                view_camera.y,
                view_camera.z,
                yaw=view_camera.yaw,
                pitch=view_camera.pitch,
                distance=view_camera.distance,
            )

    def snap_view_to_git_instance(
        self,
        git_instance: GITObject,
    ):
        try:
            camera: Camera = self._get_scene_camera()
        except RuntimeError:
            return
        yaw: float | None = git_instance.yaw()
        camera.yaw = camera.yaw if yaw is None else yaw
        camera.x, camera.y, camera.z = git_instance.position
        camera.y = git_instance.position.y
        camera.z = git_instance.position.z + 2
        camera.distance = 0

        # Sync viewport to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.set_camera_view(
                camera.x,
                camera.y,
                camera.z,
                yaw=camera.yaw,
                pitch=camera.pitch,
                distance=camera.distance,
            )

    def _get_scene_camera(self) -> Camera:
        scene = self.ui.mainRenderer._scene
        if scene is None:
            raise RuntimeError("Internal renderer is unavailable while Blender controls the viewport.")
        result: Camera = scene.camera
        return result

    def snap_camera_to_entry_location(self):
        scene = self.ui.mainRenderer._scene
        if scene is None:
            if self._is_blender_mode_enabled() and self._blender_controller is not None:
                entry_pos = self.ifo().entry_position
                self._blender_controller.set_camera_view(
                    entry_pos.x,
                    entry_pos.y,
                    entry_pos.z,
                )
            return

        scene.camera.x = self.ifo().entry_position.x
        scene.camera.y = self.ifo().entry_position.y
        scene.camera.z = self.ifo().entry_position.z

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.set_camera_view(
                scene.camera.x,
                scene.camera.y,
                scene.camera.z,
                yaw=scene.camera.yaw,
                pitch=scene.camera.pitch,
                distance=scene.camera.distance,
            )

    def _add_camera_view_preset_submenu(self, menu: QMenu):
        presets_menu = menu.addMenu("Camera View Presets")
        if presets_menu is None:
            return

        preset_names = ["Front", "Back", "Right", "Left", "Top", "Bottom", "Isometric"]
        for preset_name in preset_names:
            presets_menu.addAction(preset_name).triggered.connect(lambda _=None, p=preset_name: self.apply_camera_view_preset(p))  # pyright: ignore[reportOptionalMemberAccess]

    def apply_camera_view_preset(self, preset_name: str):
        scene = self.ui.mainRenderer._scene
        if scene is None:
            return

        camera = scene.camera
        preset_angles: dict[str, tuple[float, float]] = {
            "Front": (0.0, 0.0),
            "Back": (0.0, math.pi),
            "Right": (0.0, math.pi / 2),
            "Left": (0.0, -math.pi / 2),
            "Top": (-math.pi / 2 + 0.001, camera.yaw),
            "Bottom": (math.pi / 2 - 0.001, camera.yaw),
            "Isometric": (-math.radians(35.264), math.radians(45.0)),
        }
        if preset_name not in preset_angles:
            return

        pitch, yaw = preset_angles[preset_name]
        camera.pitch = pitch
        camera.yaw = yaw

        focus = self.selected_instances[0].position if self.selected_instances else self.ifo().entry_position
        self.ui.flatRenderer.snap_camera_to_point(focus)
        self.ui.mainRenderer.update()

        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.set_camera_view(
                camera.x,
                camera.y,
                camera.z,
                yaw=camera.yaw,
                pitch=camera.pitch,
                distance=camera.distance,
            )

        self._show_status_message(f"Camera preset: {preset_name}")

    def toggle_free_cam(self):
        if isinstance(self._controls3d, ModuleDesignerControls3d):
            self.log.info("Enabling ModuleDesigner free cam")
            self._controls3d = ModuleDesignerControlsFreeCam(self, self.ui.mainRenderer)
        else:
            self.log.info("Disabling ModuleDesigner free cam")
            self._controls3d = ModuleDesignerControls3d(self, self.ui.mainRenderer)

    # region Selection Manipulations
    def set_selection(self, instances: list[GITObject]):
        was_syncing = self._selection_sync_in_progress
        self._selection_sync_in_progress = True
        scene = self.ui.mainRenderer._scene
        try:
            unique_instances = list(dict.fromkeys(instances))
            if unique_instances:
                if scene is not None:
                    scene.select(unique_instances[0])
                self.ui.flatRenderer.instance_selection.select(unique_instances)
                self.select_instance_items_on_list(unique_instances)
                self.select_resource_items(unique_instances)
                self.selected_instances = unique_instances
            else:
                if scene is not None:
                    scene.selection.clear()
                self.ui.flatRenderer.instance_selection.clear()
                self.selected_instances.clear()
        finally:
            self._selection_sync_in_progress = was_syncing

        if self.is_blender_mode() and not was_syncing:
            self.sync_selection_to_blender(self.selected_instances)

        self._update_status_bar()
        self._update_properties_panel()

    def focus_selected_instances(self):
        """Snap 2D/3D views to current selection centroid."""
        if not self.selected_instances:
            return

        count = len(self.selected_instances)
        if count == 1:
            focus_point = self.selected_instances[0].position
        else:
            x_total = sum(instance.position.x for instance in self.selected_instances)
            y_total = sum(instance.position.y for instance in self.selected_instances)
            z_total = sum(instance.position.z for instance in self.selected_instances)
            focus_point = Vector3(x_total / count, y_total / count, z_total / count)

        self.ui.mainRenderer.snap_camera_to_point(focus_point)
        self.ui.flatRenderer.snap_camera_to_point(focus_point)

    def delete_selected(
        self,
        *,
        no_undo_stack: bool = False,
    ):
        assert self._module is not None
        instances_to_delete = self.selected_instances.copy()
        if not no_undo_stack:
            self.undo_stack.push(DeleteCommand(self.git(), instances_to_delete, self))  # noqa: SLF001
        git_module = self._module.git()
        assert git_module is not None
        git_resource = git_module.resource()
        if git_resource is not None:
            for instance in instances_to_delete:
                git_resource.remove(instance)
                # Sync deletion to Blender
                if self._is_blender_mode_enabled() and self._blender_controller is not None:
                    self._blender_controller.remove_instance(instance)
        self.selected_instances.clear()
        if self.ui.mainRenderer._scene:
            self.ui.mainRenderer._scene.selection.clear()
        self._invalidate_scene_and_update_renderers()
        self.ui.flatRenderer.instance_selection.clear()
        self.rebuild_instance_list()

    def duplicate_selected_instances(self):
        """Duplicate selected GIT instances with a small positional offset.

        Creates deep copies of each selected instance, offsets them by (0.5, 0.5, 0) meters,
        adds them to the GIT, and selects the new copies. Supports undo.
        """
        if not self.selected_instances:
            return
        assert self._module is not None
        git_module = self._module.git()
        assert git_module is not None
        git_resource = git_module.resource()
        assert git_resource is not None

        OFFSET = 0.5  # meters — small enough to stay nearby, large enough to be visible
        new_instances: list[GITObject] = []
        for inst in self.selected_instances:
            clone = deepcopy(inst)
            clone.position = Vector3(clone.position.x + OFFSET, clone.position.y + OFFSET, clone.position.z)
            git_resource.add(clone)
            new_instances.append(clone)
            # Sync to Blender
            if self._is_blender_mode_enabled() and self._blender_controller is not None:
                self.add_instance_to_blender(clone)

        self._invalidate_scene_and_update_renderers()
        self.rebuild_instance_list()
        self.set_selection(new_instances)
        self._show_status_message(f"Duplicated {len(new_instances)} instance(s)")

    def _snap_to_grid(self, value: float) -> float:
        """Snap a coordinate value to the nearest grid increment if snapping is enabled."""
        return snap_value(value, self.ui.snapSizeSpin.value(), enabled=self.ui.snapCheck.isChecked())

    def _snap_rotation(self, degrees: float) -> float:
        """Snap a rotation value to the nearest increment if rotation snapping is enabled."""
        return snap_degrees(degrees, self.ui.rotSnapDegreeSpin.value(), enabled=self.ui.rotSnapCheck.isChecked())

    def move_selected(  # noqa: PLR0913
        self,
        x: float,
        y: float,
        z: float | None = None,
        *,
        no_undo_stack: bool = False,
        no_z_coord: bool = False,
    ):
        if self.ui.lockInstancesCheck.isChecked():
            return

        walkmesh_renderer: ModuleRenderer | None = self.ui.mainRenderer if self.ui.mainRenderer._scene is not None else None
        for instance in self.selected_instances:
            self.log.debug("Moving %s", instance.resref)
            new_x = self._snap_to_grid(instance.position.x + x)
            new_y = self._snap_to_grid(instance.position.y + y)
            if no_z_coord:
                new_z = instance.position.z
            else:
                if walkmesh_renderer is not None:
                    new_z = instance.position.z + (z or walkmesh_renderer.walkmesh_point(instance.position.x, instance.position.y).z)
                else:
                    new_z = instance.position.z + (z or 0.0)
            old_position: Vector3 = instance.position
            new_position: Vector3 = Vector3(new_x, new_y, new_z)
            if not no_undo_stack:
                self.undo_stack.push(MoveCommand(instance, old_position, new_position))
            instance.position = new_position

            # Sync to Blender if not already syncing from Blender
            if self.is_blender_mode() and self._blender_controller is not None and not self._transform_sync_in_progress:
                self._blender_controller.update_instance_position(instance, new_x, new_y, new_z)

    def rotate_selected(self, x: float, y: float):
        if self.ui.lockInstancesCheck.isChecked():
            return

        for instance in self.selected_instances:
            new_yaw = x / 60
            new_pitch = (y or 1) / 60
            new_roll = 0.0
            if not self._is_rotatable_instance(instance):
                continue  # doesn't support rotations.
            # Apply rotation snap if enabled (convert to degrees, snap, convert back)
            new_yaw = snap_radians(new_yaw, self.ui.rotSnapDegreeSpin.value(), enabled=self.ui.rotSnapCheck.isChecked())
            new_pitch = snap_radians(new_pitch, self.ui.rotSnapDegreeSpin.value(), enabled=self.ui.rotSnapCheck.isChecked())
            instance.rotate(new_yaw, new_pitch, new_roll)

            # Sync to Blender if not already syncing from Blender
            if self.is_blender_mode() and self._blender_controller is not None and not self._transform_sync_in_progress:
                if isinstance(instance, GITCamera):
                    ori = instance.orientation
                    self._blender_controller.update_instance_rotation(
                        instance,
                        orientation=(ori.x, ori.y, ori.z, ori.w),
                    )
                else:
                    self._blender_controller.update_instance_rotation(
                        instance,
                        bearing=instance.bearing,
                    )

    # endregion

    # region Signal Callbacks
    def _on_saved_resource(
        self,
        resource: ModuleResource,
    ):
        resource.reload()
        scene = self.ui.mainRenderer._scene
        if scene is not None:
            scene.clear_cache_buffer.append(ResourceIdentifier(resource.resname(), resource.restype()))

    def handle_undo_redo_from_long_action_finished(self):
        """Called when mouse interactions end. Saves movements onto the stack."""
        self.transform_state.finalize_undo_actions()

    def on_instance_list_single_clicked(self):
        selected_items = self.ui.instanceTree.selectedItems()
        if not selected_items:
            return
        instances = [item.data(0, Qt.ItemDataRole.UserRole) for item in selected_items]
        instances = [instance for instance in instances if isinstance(instance, GITInstance)]
        if instances:
            self.set_selection(instances)

    def on_instance_list_double_clicked(self):
        if self.ui.instanceTree.selectedItems():
            instance = self.get_git_instance_from_highlighted_list_item()
            if instance is not None:
                self.set_selection([instance])
                self.focus_selected_instances()
                self.edit_instance(instance)

    def get_git_instance_from_highlighted_list_item(self) -> GITInstance | None:
        selected = self.ui.instanceTree.selectedItems()
        if not selected:
            return None
        item: QTreeWidgetItem = selected[0]
        result = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(result, GITInstance):
            return None
        return result

    def on_instance_visibility_double_click(self, checkbox: QCheckBox):
        visibility_checkboxes: tuple[QCheckBox, ...] = (
            self.ui.viewCreatureCheck,
            self.ui.viewPlaceableCheck,
            self.ui.viewDoorCheck,
            self.ui.viewSoundCheck,
            self.ui.viewTriggerCheck,
            self.ui.viewEncounterCheck,
            self.ui.viewWaypointCheck,
            self.ui.viewCameraCheck,
            self.ui.viewStoreCheck,
        )
        set_exclusive_checkbox_selection(checkbox, visibility_checkboxes)

    def enter_instance_mode(self):
        instance_mode = _InstanceMode.__new__(_InstanceMode)
        # HACK:
        instance_mode.delete_selected = self.delete_selected  # type: ignore[method-assign]
        instance_mode.edit_selected_instance = self.edit_instance  # type: ignore[method-assign]
        instance_mode.build_list = self.rebuild_instance_list  # type: ignore[method-assign]
        instance_mode.update_visibility = self.update_toggles  # type: ignore[method-assign]
        instance_mode.set_selection = lambda instances: self.set_selection(list(instances))  # type: ignore[method-assign]
        instance_mode.select_underneath = lambda: self.set_selection(self.ui.flatRenderer.instances_under_mouse())  # type: ignore[method-assign]
        instance_mode.__init__(self, self._installation, self.git())  # type: ignore[misc]
        # self._controls2d._mode.rotateSelectedToPoint = self.rotateSelected
        self._controls2d._mode = instance_mode  # noqa: SLF001

    def enter_geometry_mode(self):
        self._controls2d._mode = _GeometryMode(self, self._installation, self.git(), hide_others=False)  # noqa: SLF001

    def enter_spawn_mode(self):
        self._controls2d._mode = _SpawnMode(self, self._installation, self.git(), hide_others=False)  # noqa: SLF001

    def on_resource_tree_context_menu(self, point: QPoint):
        menu = QMenu(self)
        cur_item = self.ui.resourceTree.currentItem()
        if cur_item is None:
            return
        data = cur_item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ModuleResource):
            self._active_instance_location_menu(data, menu)
        menu.exec(self.ui.resourceTree.mapToGlobal(point))

    def on_resource_tree_double_clicked(self, point: QPoint):
        cur_item = self.ui.resourceTree.currentItem()
        assert cur_item is not None
        data = cur_item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ModuleResource):
            self.open_module_resource(data)

    def on_resource_tree_single_clicked(self, point: QPoint):
        cur_item = self.ui.resourceTree.currentItem()
        assert cur_item is not None
        data = cur_item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ModuleResource):
            self.jump_to_instance_list_action(data=data)

    def _instances_for_resource(self, data: ModuleResource) -> list[GITInstance]:
        """Collect all GIT instances represented by a module resource."""
        this_ident = data.identifier()
        return [instance for instance in self.git().instances() if instance.identifier() == this_ident]

    def jump_to_instance_list_action(self, *args, data: ModuleResource, **kwargs):
        matching_instances = self._instances_for_resource(data)
        if not matching_instances:
            return
        self.set_selection(matching_instances)

    def _active_instance_location_menu(self, data: ModuleResource, menu: QMenu):
        """Builds an active override menu for a module resource.

        Args:
        ----
            data: ModuleResource - The module resource data
            menu: QMenu - The menu to build actions on
        """
        copy_to_override_action = QAction("Copy To Override", self)
        copy_to_override_action.triggered.connect(lambda _=None, r=data: self.copy_resource_to_override(r))

        menu.addAction("Edit Active File").triggered.connect(lambda _=None, r=data: self.open_module_resource(r))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Reload Active File").triggered.connect(lambda _=None: data.reload())  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction(copy_to_override_action)
        menu.addSeparator()
        for location in data.locations():
            location_action = QAction(str(location), self)
            location_action.triggered.connect(lambda _=None, loc=location: self.activate_resource_file(data, loc))  # pyright: ignore[reportOptionalMemberAccess]
            if location == data.active():
                location_action.setEnabled(False)
            if os.path.commonpath([str(location.absolute()), str(self._installation.override_path())]) == str(self._installation.override_path()):
                copy_to_override_action.setEnabled(False)
            menu.addAction(location_action)

        def jump_to_instance_list_action(*args, data: ModuleResource = data, **kwargs):
            matching_instances = self._instances_for_resource(data)
            if matching_instances:
                self.set_selection(matching_instances)

        menu.addAction("Find in Instance List").triggered.connect(jump_to_instance_list_action)  # pyright: ignore[reportOptionalMemberAccess]

    def on_3d_mouse_moved(self, screen: Vector2, screen_delta: Vector2, world: Vector3, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(screen, buttons, keys, self.ui.mainRenderer)
        if (
            self._editor_mode == EditorMode.OBJECT
            and self._active_tool == EditorTool.ROTATE
            and self._object_rotate_gizmo_drag_active
            and self._walkmesh_select_bind.satisfied(buttons, keys)
        ):
            self._update_object_rotate_gizmo_drag(screen)
            return
        if (
            self._editor_mode == EditorMode.OBJECT
            and self._active_tool == EditorTool.MOVE
            and self._object_gizmo_drag_active
            and self._walkmesh_select_bind.satisfied(buttons, keys)
        ):
            self._update_object_gizmo_drag(world)
            return
        if (
            self._editor_mode == EditorMode.WALKMESH
            and self._walkmesh_select_mode == WalkmeshSelectMode.VERTEX
            and self._walkmesh_vertex_drag_active
            and self._walkmesh_select_bind.satisfied(buttons, keys)
        ):
            self._update_walkmesh_vertex_drag(world, buttons, keys)
        self._controls3d.on_mouse_moved(screen, screen_delta, world, buttons, keys)

    def on_3d_mouse_scrolled(self, delta: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.mainRenderer)
        self._controls3d.on_mouse_scrolled(delta, buttons, keys)

    def on_3d_mouse_pressed(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(screen, buttons, keys, self.ui.mainRenderer)
        if (
            self._editor_mode == EditorMode.OBJECT
            and self._active_tool == EditorTool.ROTATE
            and self.selected_instances
            and self._walkmesh_select_bind.satisfied(buttons, keys)
        ):
            axis = self.ui.mainRenderer.object_gizmo_handle(screen.x, screen.y)
            if axis is not None:
                self._begin_object_rotate_gizmo_drag(axis, screen)
                return
        if self._editor_mode == EditorMode.OBJECT and self._active_tool == EditorTool.MOVE and self.selected_instances and self._walkmesh_select_bind.satisfied(buttons, keys):
            axis = self.ui.mainRenderer.object_gizmo_handle(screen.x, screen.y)
            if axis is not None:
                self._begin_object_gizmo_drag(axis)
                return

        self._controls3d.on_mouse_pressed(screen, buttons, keys)
        if self._editor_mode != EditorMode.WALKMESH:
            return
        if not self._walkmesh_select_bind.satisfied(buttons, keys):
            return

        if self._walkmesh_select_mode == WalkmeshSelectMode.VERTEX and self._selected_walkmesh_vertex is not None:
            axis = self.ui.mainRenderer.walkmesh_vertex_gizmo_handle(screen.x, screen.y)
            if axis is not None:
                self._begin_walkmesh_vertex_drag(axis)
                return

        world = self.ui.mainRenderer._mouse_world
        self._select_walkmesh_face_from_world(world)
        if self._walkmesh_select_mode == WalkmeshSelectMode.VERTEX:
            self._show_status_message("Vertex selected. Click an axis handle (X/Y/Z) to drag.", 1500)

    def do_cursor_lock(
        self,
        mut_scr: Vector2,
        *,
        center_mouse: bool = True,
        do_rotations: bool = True,
    ):
        new_pos: QPoint = QCursor.pos()
        renderer: ModuleRenderer = self.ui.mainRenderer
        if center_mouse:
            old_pos = renderer.mapToGlobal(renderer.rect().center())
            QCursor.setPos(old_pos.x(), old_pos.y())
            local_center: QPoint = renderer.mapFromGlobal(QPoint(old_pos.x(), old_pos.y()))
            mut_scr.x, mut_scr.y = float(local_center.x()), float(local_center.y())
            renderer._mouse_prev.x, renderer._mouse_prev.y = mut_scr.x, mut_scr.y
        else:
            old_pos = renderer.mapToGlobal(QPoint(int(renderer._mouse_prev.x), int(renderer._mouse_prev.y)))
            QCursor.setPos(old_pos)
            local_old_pos: QPoint = renderer.mapFromGlobal(QPoint(old_pos.x(), old_pos.y()))
            mut_scr.x, mut_scr.y = float(local_old_pos.x()), float(local_old_pos.y())
            renderer._mouse_prev.x, renderer._mouse_prev.y = mut_scr.x, mut_scr.y

        if do_rotations:
            yaw_delta = old_pos.x() - new_pos.x()
            pitch_delta = old_pos.y() - new_pos.y()
            if isinstance(self._controls3d, ModuleDesignerControlsFreeCam):
                strength = self.settings.rotateCameraSensitivityFC / 10000
                clamp = False
            else:
                strength = self.settings.rotateCameraSensitivity3d / 10000
                clamp = True
            renderer.rotate_camera(yaw_delta * strength, -pitch_delta * strength, clamp_rotations=clamp)

    def on_3d_mouse_released(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(screen, buttons, keys, self.ui.mainRenderer)
        if self._object_rotate_gizmo_drag_active:
            self._end_object_rotate_gizmo_drag()
        if self._object_gizmo_drag_active:
            self._end_object_gizmo_drag()
        if self._walkmesh_vertex_drag_active:
            self._end_walkmesh_vertex_drag()
        self._controls3d.on_mouse_released(screen, buttons, keys)

    def on_3d_keyboard_released(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.mainRenderer)
        self._controls3d.on_keyboard_released(buttons, keys)

    def on_3d_keyboard_pressed(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.mainRenderer)
        self._controls3d.on_keyboard_pressed(buttons, keys)

    def on_3d_object_selected(self, instance: GITInstance):
        if instance is not None:
            self.set_selection([instance])
        else:
            self.set_selection([])

    def on_context_menu(self, world: Vector3, point: QPoint, *, is_flat_renderer_call: bool | None = None):
        self.log.debug(f"onContextMenu(world={world}, point={point}, isFlatRendererCall={is_flat_renderer_call})")
        if self._module is None:
            self.log.warning("onContextMenu No module.")
            return
        scene = self.ui.mainRenderer._scene
        if scene is None:
            self._show_info_message(
                "Use Blender",
                "Spatial context menus are managed by Blender while Blender mode is active. Right-click the object inside Blender to see the Holocron context menu.",
            )
            return

        if len(scene.selection) == 0:
            self.log.debug("onContextMenu No selection")
            menu = self.build_insert_instance_menu(world)
        else:
            menu = self.on_context_menu_selection_exists(world, is_flat_renderer_call=is_flat_renderer_call, get_menu=True)

        if menu is None:
            return
        self.show_final_context_menu(menu)

    def build_insert_instance_menu(self, world: Vector3):
        menu = QMenu(self)

        scene = self.ui.mainRenderer._scene
        if scene is None:
            return menu

        rot = scene.camera
        menu.addAction("Insert Camera").triggered.connect(lambda: self.add_instance(GITCamera(*world), walkmesh_snap=False))  # pyright: ignore[reportArgumentType, reportOptionalMemberAccess]
        menu.addAction("Insert Camera at View").triggered.connect(lambda: self.add_instance(GITCamera(rot.x, rot.y, rot.z, rot.yaw, rot.pitch, 0, 0), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addSeparator()
        self._add_camera_view_preset_submenu(menu)
        menu.addSeparator()
        menu.addAction("Insert Creature").triggered.connect(lambda: self.add_instance(GITCreature(*world), walkmesh_snap=True))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Door").triggered.connect(lambda: self.add_instance(GITDoor(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Placeable").triggered.connect(lambda: self.add_instance(GITPlaceable(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Store").triggered.connect(lambda: self.add_instance(GITStore(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Sound").triggered.connect(lambda: self.add_instance(GITSound(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Waypoint").triggered.connect(lambda: self.add_instance(GITWaypoint(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Encounter").triggered.connect(lambda: self.add_instance(GITEncounter(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Trigger").triggered.connect(lambda: self.add_instance(GITTrigger(*world), walkmesh_snap=False))  # pyright: ignore[reportOptionalMemberAccess]
        return menu

    def on_instance_list_right_clicked(
        self,
        *args,
        **kwargs,
    ):
        selected = self.ui.instanceTree.selectedItems()
        if not selected:
            return
        item: QTreeWidgetItem = selected[0]
        instance = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(instance, GITInstance):
            return
        self.on_context_menu_selection_exists(instances=[instance])

    def on_context_menu_selection_exists(
        self,
        world: Vector3 | None = None,
        *,
        is_flat_renderer_call: bool | None = None,
        get_menu: bool | None = None,
        instances: Sequence[GITInstance] | None = None,
    ) -> QMenu | None:  # sourcery skip: extract-method
        self.log.debug(f"onContextMenuSelectionExists(isFlatRendererCall={is_flat_renderer_call}, getMenu={get_menu})")
        menu = QMenu(self)
        instances = self.selected_instances if instances is None else instances

        if instances:
            instance = instances[0]
            if isinstance(instance, GITCamera):
                menu.addAction("Snap Camera to 3D View").triggered.connect(lambda: self.snap_camera_to_view(instance))  # pyright: ignore[reportOptionalMemberAccess]
                menu.addAction("Snap 3D View to Camera").triggered.connect(lambda: self.snap_view_to_git_camera(instance))  # pyright: ignore[reportOptionalMemberAccess]
            else:
                menu.addAction("Snap 3D View to Instance Position").triggered.connect(lambda: self.snap_view_to_git_instance(instance))  # pyright: ignore[reportOptionalMemberAccess]
            self._add_camera_view_preset_submenu(menu)
            menu.addSeparator()
            menu.addAction("Copy position to clipboard").triggered.connect(lambda: QApplication.clipboard().setText(str(instance.position)))  # pyright: ignore[reportOptionalMemberAccess]
            menu.addAction("Edit Instance").triggered.connect(lambda: self.edit_instance(instance))  # pyright: ignore[reportOptionalMemberAccess]
            menu.addAction("Remove").triggered.connect(self.delete_selected)  # pyright: ignore[reportOptionalMemberAccess]
            menu.addSeparator()
            if world is not None and not isinstance(self._controls2d._mode, _SpawnMode):
                self._controls2d._mode._get_render_context_menu(Vector2(world.x, world.y), menu)
        if not get_menu:
            self.show_final_context_menu(menu)
            return None
        return menu

    def show_final_context_menu(self, menu: QMenu):
        menu.popup(self.cursor().pos())
        menu.aboutToHide.connect(self.ui.mainRenderer.reset_all_down)
        menu.aboutToHide.connect(self.ui.flatRenderer.reset_all_down)

    def on_3d_renderer_initialized(self):
        self.log.debug("ModuleDesigner on3dRendererInitialized")
        self.show()
        self.activateWindow()

    def on_3d_scene_initialized(self):
        self.log.debug("ModuleDesigner on3dSceneInitialized")
        self._refresh_window_title()
        self.show()
        self.activateWindow()

        self.update_toggles()
        if self.selected_instances:
            self.set_selection(list(self.selected_instances))

        # Defer UI population to avoid blocking during module load
        QTimer.singleShot(50, self._deferred_initialization)

    def _deferred_initialization(self):
        """Complete initialization after window is shown."""
        self.log.debug("Building resource tree and instance list...")
        self.rebuild_resource_tree()
        self.rebuild_instance_list()
        self.rebuild_layout_tree()
        self.enter_instance_mode()
        self.log.info("Module designer ready")

    def on_2d_mouse_moved(self, screen: Vector2, delta: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dMouseMoved, screen: %s, delta: %s, buttons: %s, keys: %s", screen, delta, buttons, keys)
        world_delta: Vector2 = self.ui.flatRenderer.to_world_delta(delta.x, delta.y)
        world: Vector3 = self.ui.flatRenderer.to_world_coords(screen.x, screen.y)
        self._controls2d.on_mouse_moved(screen, delta, Vector2.from_vector3(world), world_delta, buttons, keys)
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.flatRenderer)

    def on_2d_mouse_released(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dMouseReleased, screen: %s, buttons: %s, keys: %s", screen, buttons, keys)
        self._controls2d.on_mouse_released(screen, buttons, keys)
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.flatRenderer)

    def on_2d_keyboard_pressed(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dKeyboardPressed, buttons: %s, keys: %s", buttons, keys)
        self._controls2d.on_keyboard_pressed(buttons, keys)
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.flatRenderer)

    def on_2d_keyboard_released(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dKeyboardReleased, buttons: %s, keys: %s", buttons, keys)
        self._controls2d.on_keyboard_released(buttons, keys)
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.flatRenderer)

    def on_2d_mouse_scrolled(self, delta: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dMouseScrolled, delta: %s, buttons: %s, keys: %s", delta, buttons, keys)
        self.update_status_bar(QCursor.pos(), buttons, keys, self.ui.flatRenderer)
        self._controls2d.on_mouse_scrolled(delta, buttons, keys)

    def on_2d_mouse_pressed(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        # self.log.debug("on2dMousePressed, screen: %s, buttons: %s, keys: %s", screen, buttons, keys)
        self._controls2d.on_mouse_pressed(screen, buttons, keys)
        self.update_status_bar(screen, buttons, keys, self.ui.flatRenderer)

    def on_2d_marquee_select(self, world_rect: tuple[float, float, float, float], additive: bool):
        """Select instances inside the marquee world rect (same behavior as GITEditor)."""
        min_x, min_y, max_x, max_y = world_rect
        git = self.git()
        in_rect: list[GITInstance] = []
        for instance in git.instances():
            if not self.ui.flatRenderer.is_instance_visible(instance):
                continue
            x, y = instance.position.x, instance.position.y
            if min_x <= x <= max_x and min_y <= y <= max_y:
                in_rect.append(instance)
        if additive:
            current = self.selected_instances
            combined = list({*current, *in_rect})
            self.set_selection(combined)
        else:
            self.set_selection(in_rect)

    # endregion

    # region Layout Tab Handlers
    def on_add_room(self):
        """Add a new room to the layout."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None:
            return

        # Create a new room at origin
        room = LYTRoom(model="newroom", position=Vector3(0, 0, 0))
        lyt.rooms.append(room)

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.add_room(room.model, room.position.x, room.position.y, room.position.z)

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Added room '{room.model}' to layout")

    def on_add_door_hook(self):
        """Add a new door hook to the layout."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None or not lyt.rooms:
            if lyt is not None:
                self.log.warning("Cannot add door hook: no rooms in layout")
            return

        # Create a new door hook
        doorhook = LYTDoorHook(room=lyt.rooms[0].model, door=f"door{len(lyt.doorhooks)}", position=Vector3(0, 0, 0), orientation=Vector4(0, 0, 0, 1))
        lyt.doorhooks.append(doorhook)

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.add_door_hook(
                doorhook.room,
                doorhook.door,
                doorhook.position.x,
                doorhook.position.y,
                doorhook.position.z,
                orientation=(doorhook.orientation.x, doorhook.orientation.y, doorhook.orientation.z, doorhook.orientation.w),
            )

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Added door hook '{doorhook.door}' to layout")

    def on_add_track(self):
        """Add a new track to the layout."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None:
            return

        # Create a new track
        track = LYTTrack(model="newtrack", position=Vector3(0, 0, 0))
        lyt.tracks.append(track)

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.add_track(track.model, track.position.x, track.position.y, track.position.z)

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Added track '{track.model}' to layout")

    def on_add_obstacle(self):
        """Add a new obstacle to the layout."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None:
            return

        # Create a new obstacle
        obstacle = LYTObstacle(model="newobstacle", position=Vector3(0, 0, 0))
        lyt.obstacles.append(obstacle)

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            self._blender_controller.add_obstacle(obstacle.model, obstacle.position.x, obstacle.position.y, obstacle.position.z)

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Added obstacle '{obstacle.model}' to layout")

    def on_import_texture(self):
        """Import a texture for use in the layout."""
        from qtpy.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(self, "Import Texture", "", "Image Files (*.tga *.tpc *.dds *.png *.jpg)")

        if file_path:
            self.log.info(f"Importing texture from {file_path}")
            # TODO: Implement texture import logic

    def on_generate_walkmesh(self):
        """Generate walkmesh from the current layout."""
        lyt = self._get_or_create_layout_resource()
        if lyt is None or not lyt.rooms:
            if lyt is not None:
                self.log.warning("Cannot generate walkmesh: no rooms in layout")
            return

        self.log.info("Generating walkmesh from layout...")
        walkmesh_templates: dict[str, BWM] = {}
        if self._module is not None:
            for module_resource in self._module.resources.values():
                if module_resource.restype() != ResourceType.WOK:
                    continue
                resource_obj = module_resource.resource()
                if isinstance(resource_obj, BWM):
                    walkmesh_templates[module_resource.resname().lower()] = resource_obj

        self.ui.flatRenderer.generate_walkmeshes(lyt, walkmesh_templates=walkmesh_templates)
        self.ui.flatRenderer.center_camera()
        self.ui.flatRenderer.update()
        self.log.info("Walkmesh generated from current layout")

    def rebuild_layout_tree(self):
        """Rebuild the layout tree widget to show current LYT structure."""
        if self._module is None:
            return

        lyt = self._get_or_create_layout_resource()
        if lyt is None:
            return

        self.ui.lytTree.blockSignals(True)
        self.ui.lytTree.clear()

        # Add rooms
        if lyt.rooms:
            rooms_item = QTreeWidgetItem(["Rooms"])
            self.ui.lytTree.addTopLevelItem(rooms_item)
            for room in lyt.rooms:
                room_item = QTreeWidgetItem([room.model])
                room_item.setData(0, Qt.ItemDataRole.UserRole, room)
                rooms_item.addChild(room_item)
            rooms_item.setExpanded(True)

        # Add door hooks
        if lyt.doorhooks:
            doors_item = QTreeWidgetItem(["Door Hooks"])
            self.ui.lytTree.addTopLevelItem(doors_item)
            for doorhook in lyt.doorhooks:
                door_item = QTreeWidgetItem([doorhook.door])
                door_item.setData(0, Qt.ItemDataRole.UserRole, doorhook)
                doors_item.addChild(door_item)
            doors_item.setExpanded(True)

        # Add tracks
        if lyt.tracks:
            tracks_item = QTreeWidgetItem(["Tracks"])
            self.ui.lytTree.addTopLevelItem(tracks_item)
            for track in lyt.tracks:
                track_item = QTreeWidgetItem([track.model])
                track_item.setData(0, Qt.ItemDataRole.UserRole, track)
                tracks_item.addChild(track_item)
            tracks_item.setExpanded(True)

        # Add obstacles
        if lyt.obstacles:
            obstacles_item = QTreeWidgetItem(["Obstacles"])
            self.ui.lytTree.addTopLevelItem(obstacles_item)
            for obstacle in lyt.obstacles:
                obstacle_item = QTreeWidgetItem([obstacle.model])
                obstacle_item.setData(0, Qt.ItemDataRole.UserRole, obstacle)
                obstacles_item.addChild(obstacle_item)
            obstacles_item.setExpanded(True)

        self.ui.lytTree.blockSignals(False)

        # Update LYT renderer if it exists
        if self._lyt_renderer:
            self._lyt_renderer.set_lyt(lyt)

    def on_lyt_tree_selection_changed(self):
        """Handle selection change in the layout tree."""
        selected_items: list[QTreeWidgetItem] = self.ui.lytTree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if self._lyt_renderer is not None and data is not None and self._lyt_renderer.get_selected_element() is not data:
            self._lyt_renderer.select_element(data)

        if isinstance(data, LYTRoom):
            self.ui.lytElementTabs.setCurrentIndex(0)  # Room tab
            self.update_room_properties(data)
            self.ui.mainRenderer.snap_camera_to_point(data.position)
            self.ui.flatRenderer.snap_camera_to_point(data.position)
        elif isinstance(data, LYTDoorHook):
            self.ui.lytElementTabs.setCurrentIndex(1)  # Door Hook tab
            self.update_doorhook_properties(data)
            self.ui.mainRenderer.snap_camera_to_point(data.position)
            self.ui.flatRenderer.snap_camera_to_point(data.position)

    def _find_lyt_tree_item_by_data(self, target: object) -> QTreeWidgetItem | None:
        root = self.ui.lytTree.invisibleRootItem()
        stack: list[QTreeWidgetItem] = [root]
        while stack:
            current = stack.pop()
            for i in range(current.childCount()):
                child = current.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is target:
                    return child
                stack.append(child)
        return None

    def _on_lyt_renderer_element_selected(self, element: LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle | None):
        if element is None:
            return
        item = self._find_lyt_tree_item_by_data(element)
        if item is None:
            return
        self.ui.lytTree.blockSignals(True)
        try:
            self.ui.lytTree.setCurrentItem(item)
        finally:
            self.ui.lytTree.blockSignals(False)
        self.on_lyt_tree_selection_changed()

    def _on_lyt_renderer_element_moved(self, element: LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle, _new_position: Vector3):
        # LYTRenderer already applies the new transform directly to the element.
        # Refresh dependent UI/renderers and record that the module changed.
        self.rebuild_layout_tree()
        self._mark_changes_made()
        lyt = self._get_or_create_layout_resource()
        if lyt is not None:
            self.on_lyt_updated(lyt)

    def update_room_properties(self, room: LYTRoom):
        """Update the room property editors with the selected room's data."""
        self.ui.modelEdit.blockSignals(True)
        self.ui.posXSpin.blockSignals(True)
        self.ui.posYSpin.blockSignals(True)
        self.ui.posZSpin.blockSignals(True)
        self.ui.rotXSpin.blockSignals(True)
        self.ui.rotYSpin.blockSignals(True)
        self.ui.rotZSpin.blockSignals(True)

        self.ui.modelEdit.setText(room.model)
        self.ui.posXSpin.setValue(room.position.x)
        self.ui.posYSpin.setValue(room.position.y)
        self.ui.posZSpin.setValue(room.position.z)

        # LYTRoom doesn't have orientation - reset rotation spinboxes
        self.ui.rotXSpin.setValue(0)
        self.ui.rotYSpin.setValue(0)
        self.ui.rotZSpin.setValue(0)

        self.ui.modelEdit.blockSignals(False)
        self.ui.posXSpin.blockSignals(False)
        self.ui.posYSpin.blockSignals(False)
        self.ui.posZSpin.blockSignals(False)
        self.ui.rotXSpin.blockSignals(False)
        self.ui.rotYSpin.blockSignals(False)
        self.ui.rotZSpin.blockSignals(False)

    def update_doorhook_properties(self, doorhook: LYTDoorHook):
        """Update the door hook property editors with the selected door hook's data."""
        if self._module is None:
            return

        layout_module = self._module.layout()
        if layout_module is None:
            return

        lyt: LYT | None = layout_module.resource()
        if lyt is None:
            return

        self.ui.roomNameCombo.blockSignals(True)
        self.ui.doorNameEdit.blockSignals(True)

        # Populate room combo
        self.ui.roomNameCombo.clear()
        for room in lyt.rooms:
            self.ui.roomNameCombo.addItem(room.model)

        # Set current values
        self.ui.roomNameCombo.setCurrentText(doorhook.room)
        self.ui.doorNameEdit.setText(doorhook.door)

        self.ui.roomNameCombo.blockSignals(False)
        self.ui.doorNameEdit.blockSignals(False)

    def get_selected_lyt_element(self) -> LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle | None:
        """Get the currently selected LYT element from the tree."""
        selected_items = self.ui.lytTree.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].data(0, Qt.ItemDataRole.UserRole)

    def on_room_position_changed(self):
        """Handle room position change from spinboxes."""
        element = self.get_selected_lyt_element()
        if not isinstance(element, LYTRoom):
            return

        element.position.x = self.ui.posXSpin.value()
        element.position.y = self.ui.posYSpin.value()
        element.position.z = self.ui.posZSpin.value()

        # Mark changes made
        self._mark_changes_made()

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            obj_name = f"Room_{element.model}"
            self._blender_controller.update_room_position(
                obj_name,
                element.position.x,
                element.position.y,
                element.position.z,
            )

    def on_room_rotation_changed(self):
        """Handle room rotation change from spinboxes."""
        element = self.get_selected_lyt_element()
        if not isinstance(element, LYTRoom):
            return

        # LYTRoom doesn't have orientation property - this is a no-op
        # Rotation is handled at the model level, not the room level

    def on_room_model_changed(self):
        """Handle room model name change."""
        element = self.get_selected_lyt_element()
        if not isinstance(element, LYTRoom):
            return

        old_model = element.model
        element.model = self.ui.modelEdit.text()

        # Sync to Blender - update room model
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            old_obj_name = f"Room_{old_model}"
            # Update room properties (model change requires removing and re-adding, but for now just update position)
            # The model itself would need to be reloaded, which is complex, so we'll just update position
            self._blender_controller.update_room_position(
                old_obj_name,
                element.position.x,
                element.position.y,
                element.position.z,
            )

        self.rebuild_layout_tree()
        self._mark_changes_made()

    def on_browse_model(self):
        """Browse for a model file to assign to the room."""
        from qtpy.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(self, "Select Model", "", "Model Files (*.mdl)")

        if file_path:
            model_name = Path(file_path).stem
            self.ui.modelEdit.setText(model_name)

    def on_doorhook_room_changed(self):
        """Handle door hook room change."""
        element = self.get_selected_lyt_element()
        if not isinstance(element, LYTDoorHook):
            return

        element.room = self.ui.roomNameCombo.currentText()

        # Mark changes made
        self._mark_changes_made()

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            obj_name = f"DoorHook_{element.door}"
            self._blender_controller.update_door_hook(
                obj_name,
                room=element.room,
            )

    def on_doorhook_name_changed(self):
        """Handle door hook name change."""
        element = self.get_selected_lyt_element()
        if not isinstance(element, LYTDoorHook):
            return

        old_door = element.door
        element.door = self.ui.doorNameEdit.text()

        # Sync to Blender - update door name
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            old_obj_name = f"DoorHook_{old_door}"
            self._blender_controller.update_door_hook(
                old_obj_name,
                door=element.door,
            )

        self.rebuild_layout_tree()
        self._mark_changes_made()

    def on_lyt_tree_context_menu(self, point: QPoint):
        """Show context menu for layout tree items."""
        item = self.ui.lytTree.itemAt(point)
        if not item:
            return

        element = item.data(0, Qt.ItemDataRole.UserRole)
        if not element:
            return

        menu = QMenu(self)

        # Common operations
        edit_action = QAction("Edit Properties", self)
        edit_action.triggered.connect(lambda: self.edit_lyt_element(element))
        menu.addAction(edit_action)

        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(lambda: self.duplicate_lyt_element(element))
        menu.addAction(duplicate_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_lyt_element(element))
        menu.addAction(delete_action)

        menu.addSeparator()

        # Type-specific operations
        if isinstance(element, LYTRoom):
            load_model_action = QAction("Load Room Model", self)
            load_model_action.triggered.connect(lambda: self.load_room_model(element))
            menu.addAction(load_model_action)

        elif isinstance(element, LYTDoorHook):
            place_action = QAction("Place in 3D View", self)
            place_action.triggered.connect(lambda: self.place_doorhook_in_view(element))
            menu.addAction(place_action)

        menu.exec(self.ui.lytTree.mapToGlobal(point))

    def edit_lyt_element(self, element: LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle):
        """Open editor dialog for LYT element."""
        # Select the element in the tree
        for i in range(self.ui.lytTree.topLevelItemCount()):
            parent = self.ui.lytTree.topLevelItem(i)
            if parent:
                for j in range(parent.childCount()):
                    child = parent.child(j)
                    if child and child.data(0, Qt.ItemDataRole.UserRole) == element:
                        self.ui.lytTree.setCurrentItem(child)
                        break

    def duplicate_lyt_element(self, element: LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle):
        """Duplicate the selected LYT element."""
        if self._module is None:
            return

        layout_module = self._module.layout()
        if layout_module is None:
            return

        lyt: LYT | None = layout_module.resource()
        if lyt is None:
            return

        # Create duplicate with offset
        offset = Vector3(10, 10, 0)

        new_element = duplicate_lyt_element_with_offset(lyt, element, offset)

        # Sync to Blender
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            add_lyt_element_to_blender(self._blender_controller, new_element)

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Duplicated {type(element).__name__}")

    def delete_lyt_element(self, element: LYTRoom | LYTDoorHook | LYTTrack | LYTObstacle):
        """Delete the selected LYT element."""
        if self._module is None:
            return

        layout_module = self._module.layout()
        if layout_module is None:
            return

        lyt: LYT | None = layout_module.resource()
        if lyt is None:
            return

        # Confirm deletion
        element_type = lyt_element_kind_name(element)
        element_name = lyt_element_name(element)

        reply = QMessageBox.question(
            self, "Confirm Delete", f"Delete {element_type} '{element_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        blender_type = lyt_element_blender_type(element)

        # Remove element
        remove_lyt_element(lyt, element)

        # Sync to Blender (would need object name, but we can try to find it)
        if self._is_blender_mode_enabled() and self._blender_controller is not None:
            obj_name = lyt_element_blender_object_name(element)
            self._blender_controller.remove_lyt_element(obj_name, blender_type)

        self.rebuild_layout_tree()
        self._mark_changes_made()
        self.log.info(f"Deleted {element_type} '{element_name}'")

    def load_room_model(self, room: LYTRoom):
        """Load and display a room model in the 3D view."""
        if self._module is None:
            return

        # Try to load the MDL file
        mdl_resource = self._module.resource(room.model, ResourceType.MDL)
        if mdl_resource:
            self.log.info(f"Loading room model: {room.model}")
            # The model will be loaded and positioned at room.position
            # This would integrate with the 3D renderer's model loading system
        else:
            self.log.warning(f"Room model not found: {room.model}")
            self._show_warning_message("Model Not Found", f"Could not find model '{room.model}.mdl' in the module.")

    def place_doorhook_in_view(self, doorhook: LYTDoorHook):
        """Place the door hook at the current 3D view position."""
        # Get the cursor position from the 3D view
        scene = self.ui.mainRenderer._scene
        if scene:
            doorhook.position.x = scene.cursor.position().x
            doorhook.position.y = scene.cursor.position().y
            doorhook.position.z = scene.cursor.position().z
            self.rebuild_layout_tree()
            self._mark_changes_made()
            self.log.info(f"Placed door hook '{doorhook.door}' in 3D view")

    # endregion

    # region Events
    def keyPressEvent(self, e: QKeyEvent | None):  # noqa: FBT001, FBT002  # pyright: ignore[reportIncompatibleMethodOverride]
        if e is None:
            return

        # Route keyboard shortcuts based on active editor mode
        if self._editor_mode == EditorMode.LAYOUT:
            if self._handle_indoor_key_press(e):
                return
            # Forward unhandled keys to the indoor renderer for its internal handling
            self.ui.indoorRenderer.keyPressEvent(e)
            return

        # Handle Object/Walkmesh mode shortcuts
        if self._handle_object_mode_key_press(e):
            return

        super().keyPressEvent(e)
        self.ui.mainRenderer.keyPressEvent(e)
        self.ui.flatRenderer.keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent | None):  # noqa: FBT001, FBT002  # pyright: ignore[reportIncompatibleMethodOverride]
        if e is None:
            return

        if self._editor_mode == EditorMode.LAYOUT:
            self.ui.indoorRenderer.keyReleaseEvent(e)
            return

        super().keyReleaseEvent(e)
        self.ui.mainRenderer.keyReleaseEvent(e)
        self.ui.flatRenderer.keyReleaseEvent(e)

    def _handle_object_mode_key_press(self, e: QKeyEvent) -> bool:
        """Handle keyboard shortcuts when in Object or Walkmesh mode.

        Returns True if the key was handled, False to pass through.
        """
        key = e.key()
        modifiers = e.modifiers()
        has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        has_no_mods = not bool(modifiers)
        has_only_keypad = modifiers == Qt.KeyboardModifier.KeypadModifier

        # Q / W / E — switch active tool (Blender/Unity-style)
        if key == Qt.Key.Key_Q and has_no_mods:
            self._set_active_tool(EditorTool.SELECT)
            return True
        if key == Qt.Key.Key_W and has_no_mods:
            self._set_active_tool(EditorTool.MOVE)
            return True
        if key == Qt.Key.Key_E and has_no_mods:
            self._set_active_tool(EditorTool.ROTATE)
            return True

        # F — focus camera on selected instances (Unity-style)
        if key == Qt.Key.Key_F and has_no_mods:
            self.focus_selected_instances()
            return True

        # G — toggle grid snap
        if key == Qt.Key.Key_G and has_no_mods:
            self.ui.snapCheck.toggle()
            state = "ON" if self.ui.snapCheck.isChecked() else "OFF"
            self._show_status_message("Grid Snap: " + ("ON" if state else "OFF") + f" ({self.ui.snapSizeSpin.value():.2f} m)")
            return True

        # Z — cycle viewport shading (Lightmapped → Solid → Wireframe → ...)
        if key == Qt.Key.Key_Z and has_no_mods:
            self._cycle_viewport_shading()
            return True

        # T — cycle Walkmesh selection mode (Face → Edge → Vertex)
        if key == Qt.Key.Key_T and has_no_mods and self._editor_mode == EditorMode.WALKMESH:
            self._cycle_walkmesh_select_mode()
            return True

        # 1 / 2 / 3 — direct Walkmesh selection mode (Face / Edge / Vertex)
        if self._editor_mode == EditorMode.WALKMESH and has_no_mods:
            if key == Qt.Key.Key_1:
                self._set_walkmesh_select_mode(WalkmeshSelectMode.FACE)
                return True
            if key == Qt.Key.Key_2:
                self._set_walkmesh_select_mode(WalkmeshSelectMode.EDGE)
                return True
            if key == Qt.Key.Key_3:
                self._set_walkmesh_select_mode(WalkmeshSelectMode.VERTEX)
                return True

        # NumPad camera presets (Blender-style): 1=Front, 3=Right, 7=Top, 9=Bottom
        if has_only_keypad:
            if key == Qt.Key.Key_1:
                self.apply_camera_view_preset("Front")
                return True
            if key == Qt.Key.Key_3:
                self.apply_camera_view_preset("Right")
                return True
            if key == Qt.Key.Key_7:
                self.apply_camera_view_preset("Top")
                return True
            if key == Qt.Key.Key_9:
                self.apply_camera_view_preset("Bottom")
                return True

        # Delete / Backspace — delete selected instances
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and has_no_mods:
            if self.selected_instances:
                self.delete_selected()
            return True

        # Camera bookmarks: Ctrl+1..9 saves, 1..9 recalls
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            slot = key - Qt.Key.Key_1  # 0-based
            if has_ctrl:
                self._save_camera_bookmark(slot)
                return True
            elif has_no_mods:
                self._recall_camera_bookmark(slot)
                return True

        # Ctrl+D — duplicate selected instances (Unity-style)
        if key == Qt.Key.Key_D and has_ctrl:
            self.duplicate_selected_instances()
            return True

        # Space — cycle through editor modes (Object → Layout → Walkmesh → ...)
        if key == Qt.Key.Key_Space and has_no_mods:
            next_mode = (self._editor_mode + 1) % 3
            self.ui.modeSelector.setCurrentIndex(next_mode)
            return True

        return False

    def _cycle_viewport_shading(self):
        """Cycle viewport shading: Lightmapped → Solid → back.

        Updates the lightmapCheck UI checkbox to match.
        """
        self._viewport_shading_mode = (self._viewport_shading_mode + 1) % 2
        labels = ["Lightmapped", "Solid"]
        mode_label = labels[self._viewport_shading_mode]

        if self._viewport_shading_mode == 0:
            # Lightmapped
            self.ui.lightmapCheck.setChecked(True)
        elif self._viewport_shading_mode == 1:
            # Solid (no lightmap)
            self.ui.lightmapCheck.setChecked(False)

        self._show_status_message(f"Viewport Shading: {mode_label}")

    def _save_camera_bookmark(self, slot: int):
        """Save current 3D camera position/orientation to a bookmark slot."""
        scene = self.ui.mainRenderer._scene
        if scene is None:
            return
        cam = scene.camera
        self._camera_bookmarks[slot] = (cam.x, cam.y, cam.z, cam.pitch, cam.yaw, cam.distance)
        self._show_status_message(f"Camera bookmark {slot + 1} saved")

    def _recall_camera_bookmark(self, slot: int):
        """Recall a previously saved camera bookmark."""
        bookmark = self._camera_bookmarks.get(slot)
        if bookmark is None:
            self._show_status_message(f"Camera bookmark {slot + 1} is empty")
            return
        scene = self.ui.mainRenderer._scene
        if scene is None:
            return
        cam = scene.camera
        cam.x, cam.y, cam.z, cam.pitch, cam.yaw, cam.distance = bookmark
        self.ui.mainRenderer.update()
        # Also sync 2D view to the same XY position
        self.ui.flatRenderer.snap_camera_to_point(Vector3(bookmark[0], bookmark[1], bookmark[2]))
        self._show_status_message(f"Camera bookmark {slot + 1} recalled")

    def _handle_indoor_key_press(self, e: QKeyEvent) -> bool:
        """Handle keyboard shortcuts when in Layout (indoor) mode.

        Returns True if the key was handled, False to pass through.
        """
        key = e.key()
        modifiers = e.modifiers()
        has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        has_no_mods = not bool(modifiers)
        renderer: IndoorMapRenderer = self.ui.indoorRenderer
        return handle_indoor_key_press_shortcuts(
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
            on_escape=lambda: cancel_indoor_operations_and_clear_selection(renderer, cancel_operations=self._cancel_all_indoor_operations),
            on_toggle_snap_grid=lambda: toggle_check_widget(self.ui.snapToGridCheck),
            on_toggle_snap_hooks=lambda: toggle_check_widget(self.ui.snapToHooksCheck),
            on_rotate_selected=lambda: run_if_any_indoor_rooms_selected(renderer, lambda: self._indoor_rotate_selected(self.ui.rotSnapSpin.value())),
            on_flip_selected=lambda: run_if_any_indoor_rooms_selected(renderer, lambda: self._indoor_flip_selected(True, False)),
            on_select_all=lambda: select_all_indoor_rooms(renderer, self._indoor_map.rooms, refresh=True),
            on_delete_selected=self._indoor_delete_selected,
            on_cancel_placement=self._indoor_clear_placement_mode,
            on_toggle_paint=lambda: toggle_check_widget(self.ui.enablePaintCheck),
            on_reset_view=self._indoor_reset_view,
            on_refresh=lambda: cancel_indoor_operations_and_refresh(renderer, cancel_operations=self._cancel_all_indoor_operations),
            on_copy=self._indoor_copy_selected,
            on_cut=self._indoor_cut_selected,
            on_paste=self._indoor_paste,
            on_duplicate=self._indoor_duplicate_selected,
            on_save=self._indoor_save,
            on_new=self._indoor_new,
            on_open=self._indoor_open,
        )

    # endregion

    def _on_undo(self):
        """Handle undo action."""
        self.undo_stack.undo()
        # Blender sync is handled by _on_undo_stack_changed

    def _on_redo(self):
        """Handle redo action."""
        self.undo_stack.redo()
        # Blender sync is handled by _on_undo_stack_changed

    def _on_undo_stack_changed(self, index: int):
        """Handle undo stack index changes to sync with Blender."""
        if not self.is_blender_mode() or self._blender_controller is None:
            return

        # Don't sync if we're in the middle of applying a Blender change
        if self._transform_sync_in_progress or self._property_sync_in_progress or self._instance_sync_in_progress:
            return

        # Track previous index to determine if we're undoing or redoing
        if not hasattr(self, "_last_undo_index"):
            self._last_undo_index = index
            return

        # If index decreased, we undid something
        if index < self._last_undo_index:
            # Sync undo to Blender
            self._blender_controller.undo()
        # If index increased, we redid something
        elif index > self._last_undo_index:
            # Sync redo to Blender
            self._blender_controller.redo()

        self._last_undo_index = index

    def _on_undo_stack_index_changed(self, index: int):
        """Track unsaved changes based on undo stack state."""
        # If we're at the clean index, there are no unsaved changes
        self._has_unsaved_changes = index != self._clean_undo_index
        self._refresh_window_title()

    def _mark_clean_state(self):
        """Mark the current state as clean (no unsaved changes)."""
        self._clean_undo_index = self.undo_stack.index()
        self._has_unsaved_changes = False
        self._refresh_window_title()

    def _mark_changes_made(self):
        """Mark that changes have been made."""
        self._has_unsaved_changes = True
        self._refresh_window_title()

    def has_unsaved_changes(self) -> bool:
        """Return True if there are unsaved changes."""
        return self._has_unsaved_changes

    def update_camera(self):
        if self._use_blender_mode and not self.ui.mainRenderer._scene:
            return
        # For standard 3D orbit controls, require the mouse to be over the 3D view
        # before applying keyboard-driven camera updates. In free-cam mode we allow
        # movement even when the cursor isn't strictly over the widget so that
        # "press F then WASD to fly" behaves as expected.
        from toolset.gui.windows.designer_controls import ModuleDesignerControlsFreeCam

        if not self.ui.mainRenderer.underMouse() and not isinstance(self._controls3d, ModuleDesignerControlsFreeCam):
            return

        # Check camera rotation and movement keys
        keys: set[Qt.Key] = self.ui.mainRenderer.keys_down()
        buttons: set[Qt.MouseButton] = self.ui.mainRenderer.mouse_down()
        rotation_keys: dict[str, bool] = {
            "left": self._controls3d.rotate_camera_left.satisfied(buttons, keys),
            "right": self._controls3d.rotate_camera_right.satisfied(buttons, keys),
            "up": self._controls3d.rotate_camera_up.satisfied(buttons, keys),
            "down": self._controls3d.rotate_camera_down.satisfied(buttons, keys),
        }
        movement_keys: dict[str, bool] = {
            "up": self._controls3d.move_camera_up.satisfied(buttons, keys),
            "down": self._controls3d.move_camera_down.satisfied(buttons, keys),
            "left": self._controls3d.move_camera_left.satisfied(buttons, keys),
            "right": self._controls3d.move_camera_right.satisfied(buttons, keys),
            "forward": self._controls3d.move_camera_forward.satisfied(buttons, keys),
            "backward": self._controls3d.move_camera_backward.satisfied(buttons, keys),
            "in": self._controls3d.zoom_camera_in.satisfied(buttons, keys),
            "out": self._controls3d.zoom_camera_out.satisfied(buttons, keys),
        }

        # Determine last frame time to determine the delta modifiers
        cur_time = time.time()
        time_since_last_frame = cur_time - self.last_frame_time
        self.last_frame_time = cur_time

        # Clamp frame time to avoid huge jumps (e.g. window was minimized or rendering
        # stalled). MUST NOT return early here — doing so causes the fly cam to appear
        # "stuck" whenever the renderer is slow, because camera updates are completely
        # skipped.  Instead we cap the effective delta so movement stays smooth.
        time_since_last_frame = min(time_since_last_frame, 0.05)  # cap at 50 ms (≈20 FPS minimum step)

        # Calculate rotation delta with frame-independent timing
        norm_rotate_units_setting: float = self.settings.rotateCameraSensitivity3d / 1000
        norm_rotate_units_setting *= self.target_frame_rate * time_since_last_frame
        angle_units_delta: float = (math.pi / 4) * norm_rotate_units_setting

        # Rotate camera based on key inputs
        if rotation_keys["left"]:
            self.ui.mainRenderer.rotate_camera(angle_units_delta, 0)
        elif rotation_keys["right"]:
            self.ui.mainRenderer.rotate_camera(-angle_units_delta, 0)
        if rotation_keys["up"]:
            self.ui.mainRenderer.rotate_camera(0, angle_units_delta)
        elif rotation_keys["down"]:
            self.ui.mainRenderer.rotate_camera(0, -angle_units_delta)

        # Calculate movement delta
        if self._controls3d.speed_boost_control.satisfied(
            self.ui.mainRenderer.mouse_down(),
            self.ui.mainRenderer.keys_down(),
            exact_keys_and_buttons=False,
        ):
            move_units_delta: float = (
                self.settings.boostedFlyCameraSpeedFC if isinstance(self._controls3d, ModuleDesignerControlsFreeCam) else self.settings.boostedMoveCameraSensitivity3d
            )
        else:
            move_units_delta = self.settings.flyCameraSpeedFC if isinstance(self._controls3d, ModuleDesignerControlsFreeCam) else self.settings.moveCameraSensitivity3d

        move_units_delta /= 500  # normalize
        move_units_delta *= time_since_last_frame * self.target_frame_rate  # apply modifier based on frame time

        # Zoom camera based on inputs
        if movement_keys["in"]:
            self.ui.mainRenderer.zoom_camera(move_units_delta)
        if movement_keys["out"]:
            self.ui.mainRenderer.zoom_camera(-move_units_delta)

        # Move camera based on key inputs
        if movement_keys["up"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                if self.ui.mainRenderer._scene:
                    self.ui.mainRenderer._scene.camera.z += move_units_delta
            else:
                self.ui.mainRenderer.move_camera(0, 0, move_units_delta)
        if movement_keys["down"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                if self.ui.mainRenderer._scene:
                    self.ui.mainRenderer._scene.camera.z -= move_units_delta
            else:
                self.ui.mainRenderer.move_camera(0, 0, -move_units_delta)

        if movement_keys["left"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                self.ui.mainRenderer.pan_camera(0, -move_units_delta, 0)
            else:
                self.ui.mainRenderer.move_camera(0, -move_units_delta, 0)
        if movement_keys["right"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                self.ui.mainRenderer.pan_camera(0, move_units_delta, 0)
            else:
                self.ui.mainRenderer.move_camera(0, move_units_delta, 0)

        if movement_keys["forward"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                self.ui.mainRenderer.pan_camera(move_units_delta, 0, 0)
            else:
                self.ui.mainRenderer.move_camera(move_units_delta, 0, 0)
        if movement_keys["backward"]:
            if isinstance(self._controls3d, ModuleDesignerControls3d):
                self.ui.mainRenderer.pan_camera(-move_units_delta, 0, 0)
            else:
                self.ui.mainRenderer.move_camera(-move_units_delta, 0, 0)


if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_app_cli

    sys.exit(launch_app_cli("module-designer"))
