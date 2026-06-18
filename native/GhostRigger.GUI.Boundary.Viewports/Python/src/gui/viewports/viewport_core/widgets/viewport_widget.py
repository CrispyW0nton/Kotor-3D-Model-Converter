from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403
from .state_helpers import ViewportStateMixin
from .construction import ViewportConstructionMixin
from .scene_models import ViewportSceneModelMixin
from .display_controls import ViewportDisplayControlsMixin
from .camera_workflow import ViewportCameraWorkflowMixin
from .measurement_controls import ViewportMeasurementControlsMixin
from .transform_camera import ViewportTransformCameraMixin
from .selection_mesh import ViewportSelectionMeshMixin
from .history_animation import ViewportHistoryAnimationMixin
from .event_navigation import ViewportEventNavigationMixin
from .rendering_pipeline import ViewportRenderingPipelineMixin
from .overlay_layers import ViewportOverlayLayersMixin
from .picking_hover import ViewportPickingHoverMixin
from .drag_interactions import ViewportDragInteractionsMixin
from .resource_cache import ViewportResourceCacheMixin

class QtViewportWidget(
    ViewportResourceCacheMixin,
    ViewportDragInteractionsMixin,
    ViewportPickingHoverMixin,
    ViewportOverlayLayersMixin,
    ViewportRenderingPipelineMixin,
    ViewportEventNavigationMixin,
    ViewportHistoryAnimationMixin,
    ViewportSelectionMeshMixin,
    ViewportTransformCameraMixin,
    ViewportMeasurementControlsMixin,
    ViewportCameraWorkflowMixin,
    ViewportDisplayControlsMixin,
    ViewportSceneModelMixin,
    ViewportConstructionMixin,
    ViewportStateMixin,
    QtWidgets.QWidget,
):
    """Qt model viewport backed by GhostRigger's shared frame renderer."""

    DEFAULT_THUMBNAIL_ENABLED = False
    DEFAULT_COMPACT_CONTROLS = False
    DEFAULT_VIEWPORT_TOOLBAR_VISIBLE = True
    DEFAULT_VIEWCUBE_VISIBLE = True
    DEFAULT_TRANSFORM_TYPEIN_VISIBLE = True
    VIEWPORT_ROLE = "base"

    modelChanged = QtCore.Signal(object)
    nodeSelected = QtCore.Signal(object)
    nodeMoved = QtCore.Signal(object)
    meshSelectionChanged = QtCore.Signal(list)
    meshHovered = QtCore.Signal(object)
    meshSubobjectSelectionChanged = QtCore.Signal(object)
    meshVisibilityChanged = QtCore.Signal()
    measurementSettingsChanged = QtCore.Signal(dict)
    cameraSelectionChanged = QtCore.Signal(object)
    cameraChanged = QtCore.Signal()
    activeCameraChanged = QtCore.Signal(object)
    sceneObjectDeleteRequested = QtCore.Signal(str)
    statusMessage = QtCore.Signal(str)
    renderStateChanged = QtCore.Signal(str)
    gpuUploadProgress = QtCore.Signal(int, int)
    _texturePrewarmFinished = QtCore.Signal(object)
    _deferredTxiFinished = QtCore.Signal(object)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        thumbnail_enabled: Optional[bool] = None,
        compact_controls: Optional[bool] = None,
    ):
        super().__init__(parent)
        if thumbnail_enabled is None:
            thumbnail_enabled = self.DEFAULT_THUMBNAIL_ENABLED
        if compact_controls is None:
            compact_controls = self.DEFAULT_COMPACT_CONTROLS
        self.viewport_role = self.VIEWPORT_ROLE
        self._compact_controls = bool(compact_controls)
        self._viewport_toolbar_visible = bool(self.DEFAULT_VIEWPORT_TOOLBAR_VISIBLE)
        self._viewcube_visible = bool(self.DEFAULT_VIEWCUBE_VISIBLE)
        self._transform_typein_visible = bool(self.DEFAULT_TRANSFORM_TYPEIN_VISIBLE)
        self.camera = ArcBallCamera()
        self._renderer = FrameRenderer(self.camera)
        self._renderer.show_gimbal = bool(getattr(self._renderer, "show_gimbal", True))
        self.display_options = ViewportDisplayOptions()
        setattr(self._renderer, "display_options", self.display_options)
        self.model = None
        self._scene_instances: list = []
        self._scene_model = None
        self._scene_name = "Untitled Scene"
        self.on_bone_selected = None
        self.on_node_selected = None
        self.on_node_moved = None

        self._mx = self._my = 0
        self._press_x = self._press_y = 0
        self._drag_threshold = 4
        self._is_dragging = False
        self._mesh_box_start = None
        self._mesh_box_selecting = False
        self._selected_meshes: list = []
        self._selected_viewport_nodes: list = []
        self._marquee_base_selection: list = []
        self._mesh_hover_enabled = True
        self._hovered_mesh_node = None
        self._hovered_mesh_face_bounds = None
        self._hovered_helper_node = None
        self._hovered_camera_node = None
        self._dummy_helpers_visible = True
        self._viewport_selection_mode = "object"
        self._suspend_mesh_hover_during_animation = False
        self._pan_dragging = False
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._gimbal_dragging = False
        self._gimbal_axis = ""
        self._gimbal_drag_start = (0, 0)
        self._gimbal_node_start_pos = (0.0, 0.0, 0.0)
        self._gimbal_node_start_rot = (0.0, 0.0, 0.0, 1.0)
        self._gimbal_joint_start_positions: dict[int, tuple[float, float, float]] = {}
        self._gimbal_joint_mirror_nodes: list = []
        self._gimbal_model_applied_translation = (0.0, 0.0, 0.0)
        self._gimbal_model_applied_rotation = 0.0
        self._gimbal_model_applied_scale = 1.0
        self._snap_key_down: bool = False
        self.unit_system = UnitSystem()
        self.angle_snap = AngleSnap()
        self.percent_snap = PercentSnap()
        self.measurement_settings = MeasurementSettings()
        self.measurement_controller = MeasurementController(self.unit_system)
        self.dimension_calculator = DimensionCalculator()
        self._measurement_mode = False
        self._transform_gizmo = TransformGizmo(
            TransformController(self._evict_transform_cache, self.angle_snap, self.percent_snap)
        )
        self._picking_provider = CpuMeshPickingProvider(
            mesh_nodes=lambda _scene: list(self._renderer._iter_visible_mesh_nodes()),
            projected_bounds=self._projected_mesh_bounds,
            ray_builder=ray_from_mouse,
            point_in_triangle=self._point_in_triangle,
            bounds_from_points=lambda points: self._bounds_from_points(points, min_extent=0.05),
        )
        self._last_pick_hit = None
        self._last_pick_diagnostics: dict[str, object] = {}
        self._last_selection_source = "startup"
        self.transform_reference_controller = TransformReferenceController()
        self._pivot_edit_mode = "affect_object_only"
        self._pick_reference_waiting = False
        self._light_picker = LightPicker()
        self.camera_manager = CameraManager()
        self._camera_adapter = CameraViewportAdapter(self.camera)
        self.camera_controller = CameraController(self.camera_manager, self._camera_adapter)
        self._camera_picker = CameraPicker()
        self._camera_helper_renderer = CameraGizmoRenderer()
        self._camera_overlays = CameraOverlays()
        self._camera_frame_renderer = CameraFrameRenderer(self)
        self._camera_view_active = False
        self._lock_view_to_camera = False
        self._active_camera_guard = False
        self._render_suppress_camera_overlays = False
        self._transform_gizmo_dragging = False
        self._mesh_transform_promotes_to_model_root = False
        self._transform_gizmo_mirror_nodes: list = []
        self._transform_gizmo_mirror_start_positions: dict[int, tuple[float, float, float]] = {}
        self._undo_limit = 250
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.mesh_selection_state = MeshSelectionState()
        self._mesh_history = MeshHistory()
        self._mesh_topology_cache: dict[int, MeshTopology] = {}
        self._mesh_target_weld_source: int | None = None
        self._render_pending = False
        self._last_canvas_size = (0, 0)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._fast_drag_enabled = False
        self._uv_viewer: Optional[QtUVViewerWindow] = None
        self._use_gpu = True
        self._renderer_settings = RendererSettings()
        self._frame_governor = ViewportFrameGovernor(
            self._renderer_settings.target_fps,
            idle_mode=self._renderer_settings.idle_render_mode,
        )
        self._gpu_renderer: Optional[object] = None
        self._owns_gpu_renderer = True
        self._gpu_tex_preload_model_id = 0
        self._gpu_upload_total = 0
        self._gpu_upload_model_id = 0
        self._last_renderer_backend_id = ""
        self._last_render_state_text = ""
        self._last_display_mode_warning = ""
        self._selection_orbit_bounds: Optional[tuple[tuple[float, float, float], tuple[float, float, float]]] = None
        self._selection_orbit_bounds_node_id = 0
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        self._xray_mode = False
        self._dual_viewport_mode = False
        # ── T401: Joint-dot overlay state ──────────────────────────────
        # Painted by `_draw_joint_dots()` after `_draw_bones`.  Defaults
        # chosen so the dots are immediately visible on a fresh viewport;
        # M4 inspector sliders override via `set_joint_dot_size` /
        # `set_joint_dot_opacity` / `set_joint_dot_enabled`.
        self._joint_dot_enabled: bool = True
        self._joint_dot_size: int = 3        # radius in screen pixels (1 .. 8)
        self._joint_dot_opacity: float = 0.90  # 0.0 (invisible) .. 1.0 (opaque)
        # ── T402: Joint-dot interaction state ──────────────────────────
        # Symmetry mirrors X-axis translations to the AccuRig MIRROR_PAIRS
        # partner when enabled (default on — matches AccuRig UX).
        self._joint_symmetry_enabled: bool = True
        self._joint_dragging: bool = False
        self._joint_drag_node = None              # primary node under cursor
        self._joint_drag_mirror_node = None       # MIRROR_PAIRS partner, if any
        self._joint_drag_nodes: list = []
        self._joint_drag_mirror_nodes: list = []
        self._joint_drag_start_positions: dict[int, tuple[float, float, float]] = {}
        self._joint_drag_start_screen = (0, 0)
        self._joint_drag_start_pos = (0.0, 0.0, 0.0)
        self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
        self._joint_drag_world_per_px = 1.0
        self._selected_joint_nodes: list = []
        self._joint_marquee_selecting: bool = False
        self._joint_marquee_start = (0, 0)
        self._joint_marquee_current = (0, 0)
        # ── T405: Weight heat-map overlay state ─────────────────────────
        # When enabled, every vertex of every skin mesh is painted with a
        # color from `_weight_to_heatmap_color` based on the *selected*
        # bone's weight on that vertex.  The selected bone is the one
        # currently picked via the inspector / joint-dot hit-test.
        self._weight_heatmap_enabled: bool = False
        self._weight_heatmap_dot_size: int = 3
        # ── T406: Per-mode camera-preset state ──────────────────────────
        # The active character mode (set via `set_character_mode`) drives
        # which camera-framing preset is applied on mode-change.  The
        # `_mode_user_camera_dirty` flag — set the first time the user
        # touches the camera after a mode preset is applied — prevents
        # subsequent renders from clobbering the user's framing.
        self._character_mode: Optional[str] = None
        self._mode_user_camera_dirty: bool = False
        self._thumbnail_visible_setting: bool = bool(thumbnail_enabled)
        self._last_render_wall = 0.0
        self._last_render_ms = 0.0
        self._fps_accum = 0.0
        self._fps_frames = 0
        self._fps_last_wall = time_module.perf_counter()
        self._fps_display = 0.0
        self._fast_frame_until = 0.0
        self._last_performance_overlay_label = ""
        self._last_performance_overlay_update_wall = 0.0
        self._overlay_rebuild_count = 0
        self._overlay_rebuild_rate_hz = 0.0
        self._overlay_rebuild_window_started = time_module.perf_counter()
        self._skip_overlay_pixmap_update = False
        self._map_studio_room_outline_geometry = None
        self._map_studio_marker_geometry = None
        self._map_studio_marker_hit_zones: list[dict[str, object]] = []
        self._map_studio_room_outline_hit_zones: list[dict[str, object]] = []
        self._gpu_texture_snapshot_key = None
        self._gpu_texture_snapshot_cache: dict = {}
        self._gpu_texture_snapshot_rebuilds = 0
        self._gpu_baked_lightmap_snapshot_model_id = 0
        self._gpu_baked_lightmap_snapshot: tuple[tuple[str, str, float], ...] = ()

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_now)
        self._last_rendered_canvas_size = (0, 0)
        self._post_load_refresh_timer = QtCore.QTimer(self)
        self._post_load_refresh_timer.setSingleShot(True)
        self._post_load_refresh_timer.timeout.connect(self._post_load_gpu_refresh)
        self._post_load_refresh_model_id = 0
        self._texturePrewarmFinished.connect(self._on_texture_prewarm_finished)
        self._deferredTxiFinished.connect(self._on_deferred_txi_finished)
        self._build()
        self._selection_rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self.canvas)
        self._selection_rubber_band.hide()


__all__ = ("QtViewportWidget",)
