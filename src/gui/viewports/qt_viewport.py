"""Qt viewport host for the GhostRigger UI migration."""

from __future__ import annotations

import logging
import math
import os
import re
import subprocess
import threading
import time as time_module
import copy
from pathlib import Path
from typing import Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import QtFlowLayout, make_horizontal_overflow_area
from src.gui.qt_lib.rendering.qt_gpu_renderer import (
    GpuRenderer,
    clear_prebuilt_static_gpu_mesh_data,
    clear_prebuilt_static_gpu_model_data,
    create_viewport_renderer,
)
from src.gui.qt_lib.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.viewports.qt_uv_viewer import QtUVViewerWindow
from src.gui.qt_lib.viewports.viewport_host import RendererSurfaceHost
from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer
from src.gui.qt_lib.rendering.viewport_navigation import (
    DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
    has_modifier,
    normalize_viewport_navigation_profile,
    viewport_profile_label,
)
from src.gui.qt_lib.gizmo.gizmo_mode import GizmoMode
from src.gui.qt_lib.gizmo.transform_controller import TransformController
from src.gui.qt_lib.gizmo.transform_gizmo import TransformGizmo
from src.gui.qt_lib.gizmo.transform_math import multiply_quaternions, ray_from_mouse, rotate_vector
from src.gui.qt_lib.viewports.qt_transform_typein_bar import QtTransformTypeInBar
from src.gui.qt_lib.viewports.viewcube import (
    VIEWCUBE_MARGIN,
    VIEWCUBE_MIN_CANVAS_H,
    VIEWCUBE_MIN_CANVAS_W,
    ViewCubeWidget,
)
from src.gui.qt_lib.viewports.viewcube_math import (
    ViewAction,
    action_from_view_name,
    target_for_action,
    view_orientation_quaternion,
)
from src.gui.qt_lib.panels.axis_mode_control import AxisModeControl
from src.gui.camera.camera_controller import CameraController
from src.gui.camera.camera_gizmo_renderer import CameraGizmoRenderer
from src.gui.camera.camera_manager import CameraManager
from src.gui.camera.camera_overlays import CameraOverlays
from src.gui.camera.camera_picker import CameraPicker
from src.gui.camera.camera_viewport_adapter import CameraViewportAdapter
from src.gui.camera.frame_renderer import FrameRenderer as CameraFrameRenderer
from src.gui.lighting.light_picker import LightPicker
from src.measurement.angle_snap import AngleSnap
from src.measurement.dimension_calculator import DimensionCalculator
from src.measurement.grid_measurement import GridMeasurement
from src.measurement.measurement_controller import MeasurementController
from src.measurement.percent_snap import PercentSnap
from src.core.scene.axis_mode import AxisMode, TransformReferenceController
from src.measurement.unit_settings import MeasurementSettings
from src.measurement.unit_system import UnitSystem
from src.mesh_tools.mesh_attach import attach_selected_meshes
from src.mesh_tools.mesh_edit_types import MeshOperationOptions, MeshOperationResult, MeshSelectionMode
from src.mesh_tools.mesh_element import select_element_for_face
from src.mesh_tools.mesh_history import MeshHistory
from src.mesh_tools.mesh_operations import (
    bridge_selected,
    cap_selected_borders,
    connect_selected,
    delete_selected,
    detach_selection,
    flip_normals,
    recalculate_normals,
    remove_isolated_vertices,
    target_weld_edge,
    target_weld_vertex,
    weld_selected_vertices,
)
from src.mesh_tools.mesh_selection_convert import convert_selection
from src.mesh_tools.mesh_selection_state import MeshSelectionState
from src.mesh_tools.mesh_topology import MeshTopology, normalize_edge
from src.mesh_tools.mesh_validation import validate_mesh

log = logging.getLogger(__name__)

_GUI_DIR = Path(__file__).resolve().parents[1]
_ICON_DIR = _GUI_DIR / "icons"


def _icon(name: str) -> QtGui.QIcon:
    for suffix in (".svg", "_16.png", "_24.png", ".png"):
        path = _ICON_DIR / f"{name}{suffix}"
        if path.exists():
            return QtGui.QIcon(path.as_posix())
    return QtGui.QIcon()


def _gpu_brand_icon(brand: str) -> QtGui.QIcon:
    path = _ICON_DIR / "gpu_branding" / f"{brand}.png"
    return QtGui.QIcon(path.as_posix()) if path.exists() else QtGui.QIcon()


def _branded_control_icon(name: str) -> QtGui.QIcon:
    path = _ICON_DIR / "branded_controls" / f"{name}.png"
    return QtGui.QIcon(path.as_posix()) if path.exists() else QtGui.QIcon()


def _detect_gpu_brand() -> str:
    try:
        output = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=1.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = f"{output.stdout}\n{output.stderr}".lower()
    except Exception:
        text = ""
    if any(token in text for token in ("nvidia", "geforce", "quadro", "rtx", "gtx")):
        return "nvidia"
    if any(token in text for token in ("amd", "radeon", "rx ", "firepro")):
        return "amd"
    return "generic"


def _gpu_icon_name() -> str:
    brand = _detect_gpu_brand()
    if brand == "nvidia":
        return "nvidia"
    if brand == "amd":
        return "amd"
    return "generic"


def _gpu_icon() -> QtGui.QIcon:
    brand = _gpu_icon_name()
    if brand in {"nvidia", "amd"}:
        icon = _gpu_brand_icon(brand)
        if not icon.isNull():
            return icon
    return _icon("viewport_gpu")


def _navigation_profile_icon(profile: object) -> QtGui.QIcon:
    profile_key = normalize_viewport_navigation_profile(profile)
    if profile_key == "3dsmax":
        return _branded_control_icon("3dsmax")
    if profile_key == "blender":
        return _branded_control_icon("blender")
    if profile_key == "maya":
        return _branded_control_icon("maya")
    return QtGui.QIcon()


# ── T401: Joint-dot overlay constants ──────────────────────────────────────
# AccuRig-style color-coded joint dots painted over the mesh during character
# rigging.  Colors match the M4 roadmap spec (knowledge_base/roadmap/
# 02_roadmap_2026_05.md ─ T401):
#   center        → yellow  #FFD400  (root, hip, stomach, head, neck …)
#   center-spine  → cyan    #00D7B5  (chest, spine, torso – primary spinal column)
#   L-side        → red     #FF40 40
#   R-side        → green   #00FF7A
JOINT_DOT_COLOR_CENTER       = QtGui.QColor("#FFD400")
JOINT_DOT_COLOR_CENTER_SPINE = QtGui.QColor("#00D7B5")
JOINT_DOT_COLOR_LEFT         = QtGui.QColor("#FF4040")
JOINT_DOT_COLOR_RIGHT        = QtGui.QColor("#00FF7A")
JOINT_DOT_COLOR_KEY          = QtGui.QColor("#3A96FF")

# Bone-name classifiers.  Order matters: L/R side wins first, then spine,
# then default center.  Names are matched case-insensitively against the
# bone node's `.name`.
#
# Two side-detection strategies, OR-combined:
#   1. Direct AccuRig naming:  ``^l(shoulder|forearm|hand|thigh|calf|...)``
#      — matches `lshoulder`, `lhand`, `lthigh`, etc. (MIRROR_PAIRS roots).
#   2. Tokenised naming:        ``[_\-\.]L$`` / ``^L_`` style
#      — matches `upperarm_L`, `L_clavicle`, `bone.l`, etc.
#
# Center-spine: chest / spine / torso / ribcage / back / sternum.
_AR_BODY_PARTS = (
    r"shoulder|forearm|hand|finger|thumb|thigh|calf|ankle|toe(base)?|"
    r"leg|shin|foot|elbow|wrist|knee|clavicle|arm|breast|hip(?!$)"
)
_RE_L_SIDE = re.compile(
    rf"^l(?:{_AR_BODY_PARTS})|(?:^|[_\-\.])l(?:$|[_\-\.])",
    re.IGNORECASE,
)
_RE_R_SIDE = re.compile(
    rf"^r(?:{_AR_BODY_PARTS})|(?:^|[_\-\.])r(?:$|[_\-\.])",
    re.IGNORECASE,
)
_RE_CENTER_SPINE = re.compile(r"spine|chest|torso|ribcage|back|sternum", re.IGNORECASE)
_KEY_JOINT_RE = re.compile(
    r"^(?:"
    r"head(?:_g)?|"
    r"neck(?:lwr)?(?:_g|_\d+)?|"
    r"spine(?:_g|_\d+)?|torso(?:upr)?_g|"
    r"(?:l|r)?(?:shoulder|clavicle|collar)(?:_g)?|(?:shoulder|clavicle|collar)_(?:l|r)|"
    r"(?:l|r)?(?:elbow|forearm)(?:_g)?|(?:elbow|forearm|lowerarm)_(?:l|r)|"
    r"(?:l|r)?hand(?:_g)?|hand_(?:l|r)|"
    r"(?:l|r)?(?:knee|shin|calf)(?:_g)?|(?:knee|shin|calf)_(?:l|r)|"
    r"(?:l|r)?foot(?:t)?(?:_g)?|foot_(?:l|r)"
    r")$",
    re.IGNORECASE,
)


def _is_key_joint_name(bone_name: str) -> bool:
    return bool(_KEY_JOINT_RE.match((bone_name or "").lower()))


# ── T405: Weight heat-map gradient ─────────────────────────────────────────
# Blue → green → red gradient identical to AccuRig's weight visualization.
# Matches the normalization convention from src/autorig/accurig.py: weights
# are already in [0, 1] (sum-to-one per vertex), so we use the raw value
# directly without re-normalization.
#
#   w == 0.00  →  blue   (0, 0, 255)   "no influence"
#   w == 0.50  →  green  (0, 255, 0)   "partial influence"
#   w == 1.00  →  red    (255, 0, 0)   "full influence"
#
# Two linear segments avoid a muddy yellow midpoint (matches AccuRig).
def _weight_to_heatmap_color(w: float) -> Tuple[int, int, int]:
    """Map a weight in [0, 1] to a (r, g, b) heat-map color."""
    w = max(0.0, min(1.0, float(w)))
    if w <= 0.5:
        # Blue → Green
        t = w * 2.0   # [0, 1]
        r = 0
        g = int(round(255 * t))
        b = int(round(255 * (1.0 - t)))
    else:
        # Green → Red
        t = (w - 0.5) * 2.0   # [0, 1]
        r = int(round(255 * t))
        g = int(round(255 * (1.0 - t)))
        b = 0
    return (r, g, b)


# ── T404: Snap-view button cluster ─────────────────────────────────────────
# A small floating widget pinned to the top-center of the viewport canvas
# offering one-click camera presets — Front / Back / Left / Right / Top /
# Bottom — plus a Persp/Ortho projection toggle.  Each preset triggers a
# smooth 200 ms interpolation rather than an instant snap so spatial
# orientation is preserved as the user navigates.
SNAP_VIEW_INTERP_MS    = 200    # smooth tween duration per roadmap T404
SNAP_VIEW_INTERP_HZ    = 60     # tween tick frequency
SNAP_VIEW_BAR_HEIGHT   = 28
SNAP_VIEW_BAR_MARGIN   = 8

# Azimuth / elevation per preset (degrees).  Matches `_set_camera_view`.
SNAP_VIEW_PRESETS = {
    "front":  ( 90.0,   0.0),
    "back":   (270.0,   0.0),
    "left":   (180.0,   0.0),
    "right":  (  0.0,   0.0),
    "top":    ( 90.0,  85.0),
    "bottom": ( 90.0, -85.0),
}


class _FloatingSnapViewWidget(QtWidgets.QWidget):
    """Top-center floating bar with 6 view-preset buttons + Persp/Ortho.

    The host widget connects to:
      • :attr:`viewSelected(str)` — emitted with a preset key (front/back/
        left/right/top/bottom) when the user clicks a view button.
      • :attr:`orthoToggled(bool)` — emitted when the Persp/Ortho toggle
        flips state (``True`` == orthographic).
    """

    viewSelected = QtCore.Signal(str)
    orthoToggled = QtCore.Signal(bool)

    # Layout: 6 view buttons, a separator, 1 projection toggle.
    _VIEW_BUTTONS = [
        ("F", "front",  "Front view"),
        ("B", "back",   "Back view"),
        ("L", "left",   "Left view"),
        ("R", "right",  "Right view"),
        ("T", "top",    "Top view"),
        ("Bo", "bottom", "Bottom view"),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.setStyleSheet(
            "QWidget#snapBar {"
            "  background:rgba(20,22,27,200);"
            "  border:1px solid #3a3f47;"
            "  border-radius:5px;"
            "}"
            "QPushButton {"
            "  background:#2b2e33; color:#d7dde6; border:1px solid #464b53;"
            "  padding:1px 6px; min-width:18px; font-size:10pt;"
            "}"
            "QPushButton:hover { background:#363a40; border-color:#6d747f; }"
            "QPushButton:pressed { background:#1f2227; }"
            "QPushButton:checked {"
            "  background:#35506f; color:#ffffff; border-color:#6ea0d8;"
            "}"
        )
        self.setObjectName("snapBar")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(4)

        for label, key, tip in self._VIEW_BUTTONS:
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(20)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self.viewSelected.emit(k))
            row.addWidget(btn)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("background:#4a4f58;")
        sep.setFixedWidth(1)
        row.addWidget(sep)

        self._ortho_button = QtWidgets.QPushButton("Persp")
        self._ortho_button.setCheckable(True)
        self._ortho_button.setChecked(False)
        self._ortho_button.setToolTip("Toggle perspective / orthographic projection")
        self._ortho_button.setFixedHeight(20)
        self._ortho_button.setCursor(QtCore.Qt.PointingHandCursor)
        self._ortho_button.toggled.connect(self._on_ortho_toggled)
        row.addWidget(self._ortho_button)

        self.adjustSize()

    def apply_ghost_theme(self, theme) -> None:
        panel_bg = theme.color("panel.backgroundAlt", theme.color("panel.altBackground"))
        self.setStyleSheet(
            "QWidget#snapBar {"
            f"  background:{panel_bg};"
            f"  border:1px solid {theme.color('panel.border')};"
            "  border-radius:5px;"
            "}"
            "QPushButton {"
            f"  background:{theme.color('button.background')};"
            f"  color:{theme.color('button.text')};"
            f"  border:1px solid {theme.color('panel.border')};"
            "  padding:1px 6px; min-width:18px; font-size:10pt;"
            "}"
            "QPushButton:hover {"
            f"  background:{theme.color('button.hover')};"
            f"  border-color:{theme.color('input.focusBorder')};"
            "}"
            "QPushButton:pressed {"
            f"  background:{theme.color('button.pressed')};"
            "}"
            "QPushButton:checked {"
            f"  background:{theme.color('button.checked')};"
            f"  color:{theme.color('button.checkedText', theme.color('button.accentText'))};"
            f"  border-color:{theme.color('accent.primary')};"
            "}"
        )
        for sep in self.findChildren(QtWidgets.QFrame):
            sep.setStyleSheet(f"background:{theme.color('panel.border')};")

    def _on_ortho_toggled(self, checked: bool) -> None:
        self._ortho_button.setText("Ortho" if checked else "Persp")
        self.orthoToggled.emit(bool(checked))

    @property
    def ortho_button(self) -> QtWidgets.QPushButton:
        return self._ortho_button


# ── T403: Mini-thumbnail inset widget ──────────────────────────────────────
# A floating QGraphicsView-backed inset pinned to the top-right corner of
# the main viewport canvas.  Renders the same scene at neutral pose with
# no joint overlay, and emits ``clicked`` when the user taps it so the
# host can reset the main camera.
#
# Sized per the M4 roadmap: 220×280 px, with an 8 px margin from the
# canvas edges and a subtle border so it reads as an inset over the
# main render.
THUMBNAIL_WIDTH_PX  = 220
THUMBNAIL_HEIGHT_PX = 280
THUMBNAIL_MARGIN_PX = 8


class _MiniThumbnailWidget(QtWidgets.QGraphicsView):
    """Top-right inset that previews the scene at neutral pose.

    Implemented as a ``QGraphicsView`` per the M4/T403 spec.  The host
    widget pushes a pre-rendered ``QPixmap`` via :meth:`set_thumbnail`;
    a click anywhere on the widget emits :attr:`clicked` so the host
    can reset the main camera.
    """

    clicked = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(THUMBNAIL_WIDTH_PX, THUMBNAIL_HEIGHT_PX)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        self.setStyleSheet(
            "QGraphicsView {"
            "  background:#101216;"
            "  border:1px solid #3a3f47;"
            "  border-radius:4px;"
            "}"
        )
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Click to reset camera (frame all)")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        # The graphics scene holds a single QPixmap item — the thumbnail
        # render.  Updates replace that item's pixmap rather than the
        # scene contents so geometry stays stable.

        self._scene = QtWidgets.QGraphicsScene(self)
        self._scene.setBackgroundBrush(QtGui.QColor("#101216"))
        self.setScene(self._scene)
        self._pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)
        # Placeholder text shown until a render arrives.
        self._placeholder = self._scene.addText(
            "Neutral pose",
            QtGui.QFont("Sans", 8),
        )
        self._placeholder.setDefaultTextColor(QtGui.QColor("#8f9aaa"))
        self._placeholder.setPos(8.0, 8.0)

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(
            "QGraphicsView {"
            f"  background:{theme.color('viewport.background')};"
            f"  border:1px solid {theme.color('viewport.border')};"
            "  border-radius:4px;"
            "}"
        )
        self._scene.setBackgroundBrush(QtGui.QColor(theme.color("viewport.background")))
        self._placeholder.setDefaultTextColor(QtGui.QColor(theme.color("viewport.text")))

    def set_thumbnail(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        """Replace the inset's pixmap with *pixmap* (or clear if None)."""
        if pixmap is None or pixmap.isNull():
            self._pixmap_item.setPixmap(QtGui.QPixmap())
            self._placeholder.setVisible(True)
            return
        # Scale into the widget while preserving aspect ratio so a
        # square-ish character still reads correctly inside the
        # 220×280 frame.
        scaled = pixmap.scaled(
            THUMBNAIL_WIDTH_PX - 4,
            THUMBNAIL_HEIGHT_PX - 4,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self._pixmap_item.setPixmap(scaled)
        # Centre the pixmap in the scene.
        px = (THUMBNAIL_WIDTH_PX - scaled.width()) * 0.5
        py = (THUMBNAIL_HEIGHT_PX - scaled.height()) * 0.5
        self._pixmap_item.setPos(px, py)
        self._placeholder.setVisible(False)
        self._scene.setSceneRect(
            0.0, 0.0, float(THUMBNAIL_WIDTH_PX), float(THUMBNAIL_HEIGHT_PX)
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


def _classify_joint_color(bone_name: str) -> QtGui.QColor:
    """Return the joint-dot color appropriate for *bone_name* per T401 spec.

    Resolution order:
      1. L-side / R-side prefix or `_L` / `_R` suffix tokens win first.
      2. Then center-spine tokens (chest, spine, torso, …).
      3. Default → center yellow.

    Key joints are deliberately not classified here. They keep this original
    palette fill and receive a blue accent ring in the draw layer.
    """
    if not bone_name:
        return JOINT_DOT_COLOR_CENTER
    if _RE_L_SIDE.search(bone_name):
        return JOINT_DOT_COLOR_LEFT
    if _RE_R_SIDE.search(bone_name):
        return JOINT_DOT_COLOR_RIGHT
    if _RE_CENTER_SPINE.search(bone_name):
        return JOINT_DOT_COLOR_CENTER_SPINE
    return JOINT_DOT_COLOR_CENTER


class QtViewportWidget(QtWidgets.QWidget):
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
    meshSubobjectSelectionChanged = QtCore.Signal(object)
    meshVisibilityChanged = QtCore.Signal()
    measurementSettingsChanged = QtCore.Signal(dict)
    cameraSelectionChanged = QtCore.Signal(object)
    cameraChanged = QtCore.Signal()
    activeCameraChanged = QtCore.Signal(object)
    statusMessage = QtCore.Signal(str)
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
        self._hovered_mesh_node = None
        self._hovered_mesh_face_bounds = None
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
        self._gpu_renderer: Optional[object] = None
        self._owns_gpu_renderer = True
        self._gpu_tex_preload_model_id = 0
        self._gpu_upload_total = 0
        self._gpu_upload_model_id = 0
        self._last_renderer_backend_id = ""
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

        self._render_timer = QtCore.QTimer(self)
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

    def _ensure_renderer_gimbal_state(self) -> bool:
        """Keep older/reloaded FrameRenderer instances compatible with the gimbal UI."""

        if not hasattr(self._renderer, "show_gimbal"):
            self._renderer.show_gimbal = True
        visible = bool(getattr(self._renderer, "show_gimbal", True))
        if hasattr(self, "gimbal_button"):
            self.gimbal_button.blockSignals(True)
            self.gimbal_button.setChecked(visible)
            self.gimbal_button.blockSignals(False)
        return visible

    def _set_renderer_gimbal_visible(self, visible: bool) -> None:
        self._renderer.show_gimbal = bool(visible)
        self._transform_gizmo.visible = bool(visible)

    def _active_gizmo_node(self):
        node = getattr(self._renderer, "selected_node", None)
        if node is not None:
            return node
        return None

    def _gizmo_world_position(self, node) -> tuple[float, float, float] | None:
        if node is None:
            return None
        if self._is_external_skeleton_node(node):
            return self._external_overlay_world_position(node)
        pivot_local = getattr(node, "_gr_pivot_local", None)
        if pivot_local is not None and not bool(getattr(node, "_gr_pivot_world_dirty", False)):
            try:
                position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
                rotation = tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
                local = tuple(float(v) for v in pivot_local[:3])
                offset = rotate_vector(rotation, local)
                pivot_world = (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])
                setattr(node, "_gr_pivot_world", pivot_world)
                return pivot_world
            except Exception:
                pass
        pivot_world = getattr(node, "_gr_pivot_world", None)
        if pivot_world is not None:
            try:
                return tuple(float(v) for v in pivot_world[:3])
            except Exception:
                pass
        if self._is_selected_model_root(node):
            try:
                bb_min, bb_max = self._renderer._get_render_bounds()
                return (
                    (float(bb_min[0]) + float(bb_max[0])) * 0.5,
                    (float(bb_min[1]) + float(bb_max[1])) * 0.5,
                    (float(bb_min[2]) + float(bb_max[2])) * 0.5,
                )
            except Exception:
                pass
        wp, _wo, _is_id = self._renderer._node_world_transform(node)
        return (float(wp[0]), float(wp[1]), float(wp[2]))

    @staticmethod
    def _quat_conjugate(quat) -> tuple[float, float, float, float]:
        try:
            x, y, z, w = (float(v) for v in tuple(quat)[:4])
            return (-x, -y, -z, w)
        except Exception:
            return (0.0, 0.0, 0.0, 1.0)

    def _scene_instance_for_node(self, node):
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if not object_id:
            return None
        return next((obj for obj in self._scene_instances if getattr(obj, "id", "") == object_id), None)

    def _sync_transform_reference_for_node(self, node) -> None:
        if node is None:
            return
        try:
            object_rotation = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
            pivot_rotation = getattr(node, "_gr_pivot_rotation", None)
            reference_rotation = (
                multiply_quaternions(object_rotation, pivot_rotation)
                if pivot_rotation is not None
                else object_rotation
            )
            setattr(node, "_gr_reference_rotation", reference_rotation)
            basis = self.transform_reference_controller.get_transform_basis(node, self.camera, None)
            setattr(node, "_gr_axis_basis", basis)
        except Exception:
            setattr(node, "_gr_axis_basis", ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        setattr(node, "_gr_pivot_edit_mode", self._pivot_edit_mode)

    def set_axis_mode(self, mode) -> None:
        resolved = self.transform_reference_controller.set_axis_mode(mode)
        self._pick_reference_waiting = resolved is AxisMode.PICK
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.set_axis_mode(resolved)
        if self._pick_reference_waiting:
            self.statusMessage.emit("Pick an object to use as transform reference.")
        self._request_render(fast=True)

    def axis_mode(self) -> AxisMode:
        return self.transform_reference_controller.get_axis_mode()

    def set_pivot_edit_mode(self, mode: str) -> None:
        mode = str(mode or "affect_object_only")
        if mode == "affect_hierarchy_only":
            self.statusMessage.emit("Hierarchy mode is not available for this selection.")
            return
        self._pivot_edit_mode = mode if mode in {"affect_pivot_only", "affect_object_only"} else "affect_object_only"
        node = getattr(self._renderer, "selected_node", None)
        if node is not None:
            setattr(node, "_gr_pivot_edit_mode", self._pivot_edit_mode)
            self._sync_transform_reference_for_node(node)
            self._transform_gizmo.update_from_object_transform()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def pivot_edit_mode(self) -> str:
        return self._pivot_edit_mode

    def _pivot_world_from_instance(self, instance) -> tuple[float, float, float]:
        transform = getattr(instance, "transform", None)
        pivot = getattr(instance, "pivot", None)
        position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        rotation_q = self._euler_degrees_to_quat(getattr(transform, "rotation", (0.0, 0.0, 0.0)))
        local = tuple(float(v) for v in getattr(pivot, "position_local", (0.0, 0.0, 0.0))[:3])
        offset = rotate_vector(rotation_q, local)
        return (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])

    def _pivot_local_from_node(self, node) -> tuple[float, float, float]:
        instance = self._scene_instance_for_node(node)
        if instance is None:
            return (0.0, 0.0, 0.0)
        transform = getattr(instance, "transform", None)
        position = tuple(float(v) for v in getattr(node, "position", getattr(transform, "position", (0.0, 0.0, 0.0)))[:3])
        pivot_world = tuple(float(v) for v in getattr(node, "_gr_pivot_world", position)[:3])
        rotation = tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
        rel = (pivot_world[0] - position[0], pivot_world[1] - position[1], pivot_world[2] - position[2])
        local = rotate_vector(self._quat_conjugate(rotation), rel)
        try:
            setattr(node, "_gr_pivot_local", local)
            setattr(node, "_gr_pivot_world_dirty", False)
        except Exception:
            pass
        return local

    @property
    def navigation_profile(self) -> str:
        return self._navigation_profile

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = normalize_viewport_navigation_profile(profile)
        self._sync_navigation_button()

    def _toolbar_text(self, full: str, compact: str) -> str:
        return compact if self._compact_controls else full

    def _navigation_button_text(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        if not self._compact_controls:
            return label
        return {
            "3ds Max": "3ds",
            "Blender": "Blnd",
            "Maya": "Maya",
        }.get(label, label[:4])

    def _gimbal_mode_button_text(self) -> str:
        mode = self._transform_gizmo.mode
        if mode == GizmoMode.ROTATE:
            return "[R]" if self._compact_controls else "[Rotate]"
        if mode == GizmoMode.SCALE:
            return "[S]" if self._compact_controls else "[Scale]"
        return "[T]" if self._compact_controls else "[Translate]"

    def _gimbal_mode_icon_name(self) -> str:
        mode = self._transform_gizmo.mode
        if mode == GizmoMode.ROTATE:
            return "viewport_rotate"
        if mode == GizmoMode.SCALE:
            return "viewport_scale"
        return "viewport_translate"

    def _sync_gimbal_mode_button(self) -> None:
        button = getattr(self, "gimbal_mode_button", None)
        if button is None:
            return
        button.setIcon(_icon(self._gimbal_mode_icon_name()))
        button.setText("")
        button.setToolTip(f"Cycle gimbal mode: {self._transform_gizmo.mode.value.title()}")

    def _navigation_tooltip(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        controls = {
            "3dsmax": "3ds Max: Alt+MMB orbit, MMB pan, Alt+RMB zoom, wheel zoom; Shift+F/T/L/P views",
            "blender": "Blender: MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, wheel zoom; 1/3/7/Home views",
            "maya": "Maya: Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, wheel zoom; A/F frame",
        }.get(self._navigation_profile, "")
        return f"Viewport navigation profile: {label}\n{controls}"

    def _select_navigation_profile(self, profile: object) -> None:
        self.set_navigation_profile(profile)

    def _build_navigation_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        for profile in ("3dsmax", "blender", "maya"):
            label = viewport_profile_label(profile)
            action = menu.addAction(_navigation_profile_icon(profile), label)
            action.setCheckable(True)
            action.setData(profile)
            action.triggered.connect(lambda _checked=False, value=profile: self._select_navigation_profile(value))
        return menu

    def _sync_navigation_button(self) -> None:
        button = getattr(self, "navigation_button", None)
        if button is None:
            return
        button.setIcon(_navigation_profile_icon(self._navigation_profile))
        button.setText("")
        button.setToolTip(self._navigation_tooltip())
        menu = button.menu()
        if menu is not None:
            for action in menu.actions():
                profile = action.data()
                action.setChecked(profile == self._navigation_profile)

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root_layout = root

        tb = QtWidgets.QFrame()
        tb.setObjectName("ViewportToolbar")
        tb.setFrameShape(QtWidgets.QFrame.StyledPanel)
        tb.setLineWidth(1)
        tb.setMinimumHeight(30)
        self.viewport_toolbar = tb
        row = QtFlowLayout(
            tb,
            margin=0,
            hspacing=2 if self._compact_controls else 3,
            vspacing=2,
            horizontal_alignment=QtCore.Qt.AlignHCenter,
        )
        row.setContentsMargins(4 if self._compact_controls else 5, 3, 4 if self._compact_controls else 5, 3)

        self.renderer_button = self._icon_button(
            "GPU",
            self.toggle_gpu_renderer,
            "viewport_gpu",
            checkable=True,
            active=True,
            tooltip="GPU renderer",
        )
        self.renderer_button.setObjectName("ViewportGpuButton")
        self.renderer_button.setIcon(_gpu_icon())
        self.renderer_button.setIconSize(QtCore.QSize(28, 20))
        self.renderer_button.setFixedWidth(34)
        self.renderer_button.setMinimumWidth(34)
        self.renderer_button.setMaximumWidth(34)
        self.renderer_button.setStyleSheet("QPushButton#ViewportGpuButton { padding: 0px; }")
        self.solid_button = self._icon_button(
            "Solid",
            lambda _checked=False: self.set_shade_mode("solid"),
            "viewport_solid",
            checkable=True,
            active=True,
            tooltip="Solid mesh",
        )
        self.wire_button = self._icon_button(
            "Wire  W",
            lambda _checked=False: self.set_shade_mode("wire"),
            "viewport_wire",
            checkable=True,
            tooltip="Wireframe only (W)",
        )
        self.solid_wire_button = self._icon_button(
            "Solid + Wire",
            lambda _checked=False: self.set_shade_mode("both"),
            "viewport_solid_wire",
            checkable=True,
            tooltip="Solid mesh with wireframe overlay",
        )
        self.bones_button = self._icon_button(
            "Bones  B",
            self.toggle_bones,
            "viewport_bones",
            checkable=True,
            tooltip="Bones (B)",
        )
        self.texture_button = self._icon_button(
            "Texture  T",
            self.toggle_texture,
            "viewport_texture",
            checkable=True,
            active=True,
            tooltip="Texture (T)",
        )
        self.grid_button = self._icon_button(
            "Grid",
            self.toggle_grid,
            "viewport_grid",
            checkable=True,
            active=True,
            tooltip="Show or hide the viewport grid",
        )
        self.joint_dot_button = self._icon_button(
            "Dots",
            self.toggle_joint_dots,
            "viewport_dots",
            checkable=True,
            active=True,
            tooltip="Show or hide AccuRig joint-dot handles",
        )
        self.heatmap_button = self._icon_button(
            "Heat",
            self.toggle_weight_heatmap,
            "viewport_heat",
            checkable=True,
            tooltip="Show selected-bone weight heat-map",
        )
        self.xray_button = self._button(
            self._toolbar_text("X-Ray  Alt+X", "X"),
            self.toggle_xray,
            checkable=True,
            tooltip="X-Ray (Alt+X)",
        )
        self.xray_button.setVisible(False)
        self.xray_button.setEnabled(False)
        row.addWidget(self.renderer_button)
        row.addWidget(self.solid_button)
        row.addWidget(self.wire_button)
        row.addWidget(self.solid_wire_button)
        row.addWidget(self.bones_button)
        row.addWidget(self.texture_button)
        row.addWidget(self.grid_button)
        row.addWidget(self.joint_dot_button)
        row.addWidget(self.heatmap_button)
        row.addWidget(self._separator())

        self.render_realistic_button = self._icon_button(
            "Realistic",
            lambda _checked=False: self.set_render_mode("realistic"),
            "viewport_render_realistic",
            checkable=True,
            active=True,
            tooltip="Realistic shader",
        )
        self.render_shaded_button = self._icon_button(
            "Shaded",
            lambda _checked=False: self.set_render_mode("shaded"),
            "viewport_render_shaded",
            checkable=True,
            tooltip="Shaded shader",
        )
        self.render_flat_button = self._icon_button(
            "Flat",
            lambda _checked=False: self.set_render_mode("flat"),
            "viewport_render_flat",
            checkable=True,
            tooltip="Flat shader",
        )
        row.addWidget(self.render_realistic_button)
        row.addWidget(self.render_shaded_button)
        row.addWidget(self.render_flat_button)
        row.addWidget(self._separator())
        row.addWidget(self._icon_button("Frame  F", self.frame_all, "viewport_frame", tooltip="Frame all (F)"))
        self.walkmesh_button = self._icon_button(
            "WalkMesh",
            self.toggle_walkmesh,
            "viewport_wire",
            checkable=True,
            tooltip="Walkmesh overlay",
        )
        self.walkmesh_button.hide()
        row.addWidget(self._separator())
        self.gimbal_button = self._icon_button(
            "Gimbal  G",
            self.toggle_gimbal,
            "viewport_gimbal",
            checkable=True,
            active=True,
            tooltip="Gimbal (G)",
        )
        row.addWidget(self.gimbal_button)
        self.gimbal_mode_button = self._icon_button(
            self._gimbal_mode_button_text(),
            self.cycle_gimbal_mode,
            self._gimbal_mode_icon_name(),
            tooltip="Cycle gimbal mode",
        )
        self._sync_gimbal_mode_button()
        row.addWidget(self.gimbal_mode_button)
        self.measure_button = self._icon_button(
            "Measure",
            self.toggle_measurement_mode,
            "viewport_measure",
            checkable=True,
            tooltip="Distance measurement tool",
        )
        row.addWidget(self.measure_button)
        self.uv_button = self._icon_button(
            "UV View",
            self.open_uv_viewer,
            "viewport_uv",
            tooltip="Open UV view",
        )
        row.addWidget(self.uv_button)
        self.navigation_button = QtWidgets.QToolButton()
        self.navigation_button.setObjectName("ViewportNavigationButton")
        self.navigation_button.setProperty("_gr_ignore_layout_button_mode", True)
        self.navigation_button.setFixedSize(34, 22)
        self.navigation_button.setIconSize(QtCore.QSize(22, 18))
        self.navigation_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.navigation_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.navigation_button.setMenu(self._build_navigation_menu())
        self._sync_navigation_button()
        row.addWidget(self.navigation_button)
        self.lock_camera_button = self._icon_button(
            "Lock View To Camera",
            self.set_lock_view_to_camera,
            "viewport_lock_camera",
            checkable=True,
            tooltip="Lock viewport navigation to the active scene camera",
        )
        row.addWidget(self.lock_camera_button)
        row.addWidget(self._separator())
        self.axis_mode_control = AxisModeControl(self, compact=self._compact_controls)
        self.axis_mode_control.label.hide()
        self.axis_mode_control.axisModeChanged.connect(self.set_axis_mode)
        row.addWidget(self.axis_mode_control)

        self.canvas = RendererSurfaceHost(self)
        self.canvas.setObjectName("ViewportCanvas")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(120 if self._compact_controls else 180, 100 if self._compact_controls else 140)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Ignored if self._compact_controls else QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setScaledContents(False)
        self.canvas.installEventFilter(self)
        self._install_label_renderer_surface("modern_gl")
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_solid = True
        self._renderer.show_wireframe = False
        self._renderer.show_grid = self.grid_button.isChecked()
        self._renderer.render_mode = "realistic"
        self._sync_shade_buttons()
        self._sync_render_mode_buttons()

        toolbar_scroll = make_horizontal_overflow_area(
            tb,
            "ViewportToolbarScroll",
            height=44,
            parent=self,
        )
        toolbar_scroll.setMinimumWidth(0)
        self.viewport_toolbar_scroll = toolbar_scroll
        if self._compact_controls:
            toolbar_scroll.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
            root.addWidget(toolbar_scroll)
            self.setMinimumSize(140, 130)
            self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        else:
            root.addWidget(toolbar_scroll)
        root.addWidget(self.canvas, 1)
        self.transform_typein_bar = QtTransformTypeInBar(self)
        self.transform_typein_bar.transformValueEdited.connect(self._on_transform_typein_edited)
        self.transform_typein_bar.gridEdited.connect(self._on_grid_spacing_edited)
        self.transform_typein_bar.snapToggled.connect(self.toggle_snap)
        self.transform_typein_bar.angleSnapToggled.connect(self.toggle_angle_snap)
        self.transform_typein_bar.angleIncrementChanged.connect(self._on_angle_snap_increment_changed)
        self.transform_typein_bar.percentSnapToggled.connect(self.toggle_percent_snap)
        self.transform_typein_bar.percentIncrementChanged.connect(self._on_percent_snap_increment_changed)
        self.angle_snap_button = self.transform_typein_bar.angle_button
        self.angle_snap_combo = self.transform_typein_bar.angle_combo
        self.percent_snap_button = self.transform_typein_bar.percent_button
        self.percent_snap_combo = self.transform_typein_bar.percent_combo
        self.snap_button = self.transform_typein_bar.snap_button
        root.addWidget(self.transform_typein_bar)
        self._sync_transform_typein_bar()

        # ── T403: Mini-thumbnail inset (top-right) ────────────────────
        # Built as a child widget of `self.canvas` so it floats over the
        # main render and tracks canvas resize via `eventFilter`.  Click
        # the thumbnail to snap the main camera back to "frame all".
        self._thumbnail_widget = _MiniThumbnailWidget(self)
        self._thumbnail_widget.setParent(self.canvas)
        self._thumbnail_widget.clicked.connect(self.reset_camera)
        self._thumbnail_widget.hide()  # shown once a model is loaded
        self._thumbnail_force_hidden: bool = False  # set by Head close-up
        self._reposition_thumbnail()

        # ── T404: Snap-view button cluster (top-center) ────────────────
        # ViewCube overlay replaces the old visible snap buttons while
        # preserving their command layer below.
        self._viewcube_widget = ViewCubeWidget(self.canvas, camera_state=self._viewcube_camera_state)
        self._viewcube_widget.viewActionRequested.connect(self.execute_view_action)
        self._viewcube_widget.orientationRequested.connect(self.animate_to_orientation)
        self._viewcube_widget.dragOrbitRequested.connect(self.orbit_from_viewcube_drag)
        self._snap_view_widget = self._viewcube_widget
        # Animation state — driven by a QTimer at ~60 Hz for 200 ms.
        self._snap_anim_timer = QtCore.QTimer(self)
        self._snap_anim_timer.setInterval(int(1000.0 / SNAP_VIEW_INTERP_HZ))
        self._snap_anim_timer.timeout.connect(self._snap_anim_tick)
        self._snap_anim_t0: float = 0.0
        self._snap_anim_from = (0.0, 0.0)   # (azimuth, elevation)
        self._snap_anim_to = (0.0, 0.0)
        self._ortho_mode: bool = False
        self._reposition_viewcube()
        self.set_viewport_chrome_visible(
            toolbar=self._viewport_toolbar_visible,
            viewcube=self._viewcube_visible,
            transform_typein=self._transform_typein_visible,
        )

    def _install_label_renderer_surface(self, backend_id: str = "modern_gl") -> None:
        label = QtWidgets.QLabel("Empty Scene", self.canvas)
        label.setObjectName("ViewportImageSurface")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setMinimumSize(120 if self._compact_controls else 180, 100 if self._compact_controls else 140)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored if self._compact_controls else QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        label.setFocusPolicy(QtCore.Qt.StrongFocus)
        label.setMouseTracking(True)
        label.setScaledContents(False)
        self.canvas.set_renderer_surface(label, backend_id=backend_id, live_surface=False)
        self.canvas.install_input_bridge(self)

    def _active_renderer_backend_id(self) -> str:
        renderer = self._gpu_renderer
        if renderer is None:
            return str(getattr(self._renderer_settings.backend, "value", self._renderer_settings.backend))
        diagnostics = {}
        get_diagnostics = getattr(renderer, "get_diagnostics", None)
        if callable(get_diagnostics):
            try:
                diagnostics = get_diagnostics() or {}
            except Exception:
                diagnostics = {}
        return str(diagnostics.get("backend_id") or getattr(renderer, "backend_id", "") or "")

    def _renderer_uses_live_surface(self, backend_id: str) -> bool:
        return str(backend_id or "").startswith("wgpu_")

    def _sync_renderer_surface(self, *, force: bool = False) -> None:
        if self._gpu_renderer is None:
            if force or self.canvas.current_surface() is None:
                self._install_label_renderer_surface("modern_gl")
            return
        backend_id = self._active_renderer_backend_id()
        if not backend_id:
            backend_id = str(getattr(self._gpu_renderer, "backend_id", "") or "")
        live_surface = self._renderer_uses_live_surface(backend_id)
        if (
            not force
            and self.canvas.current_surface() is not None
            and self.canvas.surface_backend_id() == backend_id
            and self.canvas.is_live_surface() == live_surface
        ):
            return
        if live_surface:
            create_surface = getattr(self._gpu_renderer, "create_surface_widget", None)
            if callable(create_surface):
                try:
                    surface = create_surface(self.canvas)
                    backend_id = self._active_renderer_backend_id() or backend_id
                    live_surface = self._renderer_uses_live_surface(backend_id)
                    self.canvas.set_renderer_surface(surface, backend_id=backend_id, live_surface=live_surface)
                    self.canvas.install_input_bridge(self)
                    return
                except Exception as exc:
                    log.info("WGPU surface creation failed, falling back through renderer factory: %s", exc)
        self._install_label_renderer_surface(backend_id or "modern_gl")

    def take_viewport_toolbar(self) -> QtWidgets.QWidget | None:
        """Detach the viewport tool strip so the application shell can host it."""

        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        toolbar = getattr(self, "viewport_toolbar", None)
        if toolbar_scroll is None:
            return toolbar
        layout = getattr(self, "_root_layout", None) or self.layout()
        if layout is not None and layout.indexOf(toolbar_scroll) >= 0:
            layout.removeWidget(toolbar_scroll)
        if toolbar is not None and hasattr(toolbar_scroll, "takeWidget"):
            toolbar_scroll.takeWidget()
        toolbar_scroll.setParent(None)
        toolbar_scroll.deleteLater()
        self.viewport_toolbar_scroll = None
        return toolbar

    def set_viewport_chrome_visible(
        self,
        *,
        toolbar: bool | None = None,
        viewcube: bool | None = None,
        transform_typein: bool | None = None,
    ) -> None:
        """Show or hide optional viewport UI chrome for embedded workflows."""

        if toolbar is not None:
            self._viewport_toolbar_visible = bool(toolbar)
        if viewcube is not None:
            self._viewcube_visible = bool(viewcube)
        if transform_typein is not None:
            self._transform_typein_visible = bool(transform_typein)
        self._sync_viewport_chrome_visibility()
        self._request_render(fast=True)

    def _sync_viewport_chrome_visibility(self) -> None:
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setVisible(self._viewport_toolbar_visible)
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        if toolbar is not None:
            toolbar.setVisible(self._viewport_toolbar_visible)
        typein = getattr(self, "transform_typein_bar", None)
        if typein is not None:
            typein.setVisible(self._transform_typein_visible)
        cube = getattr(self, "_viewcube_widget", None)
        if cube is not None:
            if self._viewcube_visible:
                self._reposition_viewcube()
            else:
                cube.hide()

    @property
    def viewport_toolbar_chrome_visible(self) -> bool:
        return bool(self._viewport_toolbar_visible)

    @property
    def viewcube_chrome_visible(self) -> bool:
        return bool(self._viewcube_visible)

    @property
    def transform_typein_chrome_visible(self) -> bool:
        return bool(self._transform_typein_visible)

    def _button(
        self,
        text: str,
        callback,
        *,
        checkable: bool = False,
        active: bool = False,
        tooltip: Optional[str] = None,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setProperty("_gr_full_text", text)
        button.setCheckable(checkable)
        button.setChecked(active if checkable else False)
        button.setFixedHeight(22)
        if self._compact_controls:
            width = max(24, min(58, button.fontMetrics().horizontalAdvance(text) + 16))
            button.setFixedWidth(width)
            button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        if tooltip:
            button.setToolTip(tooltip)
        button.clicked.connect(lambda checked=False: callback(checked) if checkable else callback())
        return button

    def _icon_button(
        self,
        text: str,
        callback,
        icon_name: str,
        *,
        checkable: bool = False,
        active: bool = False,
        tooltip: Optional[str] = None,
    ) -> QtWidgets.QPushButton:
        button = self._button(
            "",
            callback,
            checkable=checkable,
            active=active,
            tooltip=tooltip or text,
        )
        button.setProperty("_gr_full_text", text)
        button.setProperty("_gr_ignore_layout_button_mode", True)
        button.setIcon(_icon(icon_name))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setFixedWidth(30)
        button.setMinimumWidth(30)
        button.setMaximumWidth(30)
        button.setToolTip(tooltip or text)
        return button

    def apply_ghost_theme(self, theme) -> None:
        self._current_theme = theme
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        if toolbar is not None:
            toolbar.setStyleSheet(
                f"#ViewportToolbar {{ background:{theme.color('viewportToolbar.background', theme.color('toolbar.background'))}; "
                f"border:1px solid {theme.color('viewportToolbar.border', theme.color('toolbar.border'))}; }}"
            )
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                f"QScrollArea {{ background:{theme.color('viewportToolbar.background', theme.color('toolbar.background'))}; border:0; }}"
            )
        combo_style = (
            f"QComboBox {{ background:{theme.color('input.background')}; "
            f"color:{theme.color('input.text')}; border:1px solid {theme.color('input.border')}; "
            "padding:2px 18px 2px 7px; }"
            f"QComboBox:hover {{ border-color:{theme.color('accent.secondary')}; }}"
            "QComboBox::drop-down { border:0; width:16px; }"
            f"QComboBox QAbstractItemView {{ background:{theme.color('panel.backgroundAlt', theme.color('panel.altBackground'))}; "
            f"color:{theme.color('text.primary')}; selection-background-color:{theme.color('selection.background')}; }}"
        )
        for combo_name in ():
            combo = getattr(self, combo_name, None)
            if combo is not None:
                combo.setStyleSheet(combo_style)
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.apply_ghost_theme(theme)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setStyleSheet("")
        for sep in self.findChildren(QtWidgets.QFrame):
            if sep.frameShape() == QtWidgets.QFrame.VLine:
                sep.setStyleSheet(f"background:{theme.color('panel.border')};")
        self.canvas.setStyleSheet(
            f"background:{theme.color('viewport.background')}; "
            f"color:{theme.color('viewport.text')}; "
            f"border:1px solid {theme.color('viewport.border')};"
        )
        if hasattr(self._renderer, "set_theme_colors"):
            self._renderer.set_theme_colors(theme)
        if self._gpu_renderer is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
            self._gpu_renderer.set_theme_colors(theme)
        if hasattr(self, "transform_typein_bar"):
            self.transform_typein_bar.apply_ghost_theme(theme)
        if hasattr(self, "_snap_view_widget"):
            self._snap_view_widget.apply_ghost_theme(theme)
        if hasattr(self, "_thumbnail_widget"):
            self._thumbnail_widget.apply_ghost_theme(theme)
        self._request_render(fast=True)

    def apply_native_theme(self) -> None:
        self._current_theme = None
        self.setStyleSheet("")
        for child in self.findChildren(QtWidgets.QWidget):
            child.setStyleSheet("")
        self._apply_native_palette_to_renderers()
        self._ensure_renderer_gimbal_state()
        self._request_render(fast=True)

    @staticmethod
    def _palette_rgb(palette: QtGui.QPalette, role: QtGui.QPalette.ColorRole) -> tuple[int, int, int]:
        color = palette.color(role)
        return (color.red(), color.green(), color.blue())

    def _apply_native_palette_to_renderers(self) -> None:
        app = QtWidgets.QApplication.instance()
        palette = app.palette() if app is not None else self.palette()
        native_colors = {
            "window": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Window),
            "base": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Base),
            "text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Text),
            "button": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Button),
            "button_text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.ButtonText),
            "mid": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Mid),
            "highlight": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Highlight),
            "highlighted_text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.HighlightedText),
        }
        if hasattr(self._renderer, "set_native_palette_colors"):
            self._renderer.set_native_palette_colors(**native_colors)
        elif hasattr(self._renderer, "reset_theme_colors"):
            self._renderer.reset_theme_colors()
        if self._gpu_renderer is not None:
            if hasattr(self._gpu_renderer, "set_native_palette_colors"):
                self._gpu_renderer.set_native_palette_colors(
                    base=native_colors["base"],
                    text=native_colors["text"],
                    highlight=native_colors["highlight"],
                )
            elif hasattr(self._gpu_renderer, "reset_theme_colors"):
                self._gpu_renderer.reset_theme_colors()

    def apply_ghost_layout(self, layout) -> None:
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        toolbar_layout = layout.toolbar("viewport")
        if toolbar is not None:
            toolbar.setVisible(self._viewport_toolbar_visible and toolbar_layout.visible and layout.viewport.toolbar_visible)
            toolbar.setMinimumHeight(toolbar_layout.height)
            toolbar.setMaximumHeight(16777215)
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setVisible(self._viewport_toolbar_visible and toolbar_layout.visible and layout.viewport.toolbar_visible)
            toolbar_scroll.setFixedHeight(max(toolbar_layout.height + 14, toolbar_layout.height))
            parent = toolbar_scroll.parentWidget()
            if parent is not None and parent.objectName() == "ViewportToolbarBand":
                parent.setFixedHeight(toolbar_scroll.height())
        self._compact_controls = bool(layout.viewport.toolbar_compact)
        mode = getattr(layout.viewport, "toolbar_button_mode", toolbar_layout.button_mode)
        icon_size = toolbar_layout.icon_size
        from src.gui.libtheme.layout_applier import LayoutApplier

        LayoutApplier().apply_toolbar_button_mode(
            self,
            toolbar_layout.__class__(
                id=toolbar_layout.id,
                visible=toolbar_layout.visible,
                button_mode=mode,
                icon_size=icon_size,
                height=toolbar_layout.height,
            ),
        )
        self.canvas.setMinimumSize(
            max(120, layout.viewport.min_width // 4 if self._compact_controls else 180),
            100 if self._compact_controls else 140,
        )
        if hasattr(self, "transform_typein_bar"):
            self.transform_typein_bar.apply_ghost_layout(layout)
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.apply_ghost_layout(layout)
        self._sync_viewport_chrome_visibility()

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFixedWidth(1)
        return sep

    def load_model(
        self,
        model,
        texture_dir: str = "",
        extra_texture_dirs: Optional[list[str]] = None,
        texture_cache: Optional[dict[str, bytes]] = None,
    ) -> None:
        old_model = self.model
        if old_model is not None and old_model is not model:
            clear_prebuilt_static_gpu_model_data(old_model)
        self.model = model
        self._hovered_mesh_node = None
        self._hovered_mesh_face_bounds = None
        self._renderer.set_model(model)
        self.camera_manager.set_model(model)
        self._camera_view_active = False
        self._refresh_camera_view_combo()
        self._clear_edit_history()
        self._gpu_tex_preload_model_id = 0
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
            self._gpu_renderer.reset_framebuffers()
        if model is None:
            self._transform_gizmo.clear_selection()
            self._gpu_upload_total = 0
            self._gpu_upload_model_id = 0
            self._pixmap = None
            self._render_pending = False
            self._renderer.set_animation_pose(None)
            self._renderer.clear_walkmesh()
            self.walkmesh_button.setChecked(False)
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
            self._use_gpu = True
            self.renderer_button.setChecked(True)
            self.renderer_button.setToolTip("GPU renderer")
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("Empty Scene")
            self._update_uv_viewer_model()
            self.camera_manager.set_model(None)
            self._refresh_camera_view_combo()
            # T403: clear the thumbnail when no model is loaded.
            self._refresh_thumbnail_safe()
            self.modelChanged.emit(None)
            self._request_render(fast=True)
            return
        self._gpu_upload_model_id = id(model)
        self._gpu_upload_total = int(getattr(model, "_gr_gpu_prebuilt_mesh_count", 0) or 0)
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_bones = self.bones_button.isChecked()
        self._sync_shade_buttons()
        self._sync_render_mode_buttons()

        search_dirs = []
        seen_dirs: set[str] = set()
        if texture_dir and os.path.isdir(texture_dir):
            seen_dirs.add(os.path.normcase(os.path.abspath(texture_dir)))
            search_dirs.append(texture_dir)
        for directory in extra_texture_dirs or []:
            key = os.path.normcase(os.path.abspath(directory)) if directory else ""
            if directory and os.path.isdir(directory) and key not in seen_dirs:
                seen_dirs.add(key)
                search_dirs.append(directory)
        if search_dirs:
            self._renderer.tex_cache.set_search_dirs(search_dirs)

        if not getattr(model, "_gr_bounds_prepared", False):
            self._compute_bb(model)
        prepared_bounds = getattr(model, "_gr_render_bounds", None)
        if prepared_bounds:
            self.camera.frame_bounds(*prepared_bounds)
        else:
            self.frame_all()
        self._prewarm_textures(model)
        self._start_deferred_txi_metadata(model)
        self._update_uv_viewer_model()
        # T403: populate the mini-thumbnail inset with a neutral-pose
        # snapshot of the freshly loaded model.  This uses the same GPU-only
        # viewport rendering policy as the main canvas.
        if self._thumbnail_visible_setting:
            self._refresh_thumbnail_safe()
        self.modelChanged.emit(model)
        try:
            root_node = getattr(model, "root_node", None)
            if root_node is not None and not bool(getattr(root_node, "_gr_scene_composite_root", False)):
                self.set_selected_node(root_node)
        except Exception:
            log.debug("Could not select imported model root", exc_info=True)
        self._request_render(fast=True)
        self._queue_post_load_gpu_refresh()

    def set_model(self, model) -> None:
        self.load_model(model)

    def load_scene_instances(
        self,
        instances: list,
        *,
        scene_name: str = "Untitled Scene",
        texture_dirs: Optional[list[str]] = None,
    ) -> None:
        """Render the active KMAX scene through a synthetic multi-object model."""

        self._scene_instances = list(instances or [])
        self._scene_name = scene_name or "Untitled Scene"
        selected_id = str(
            getattr(next((obj for obj in self._scene_instances if getattr(obj, "selected", False)), None), "id", "")
            or ""
        )
        composite = self._build_scene_composite_model(self._scene_instances, self._scene_name)
        if composite is None:
            self._scene_model = None
            self.load_model(None)
            return
        self._scene_model = composite
        dirs = [directory for directory in (texture_dirs or []) if directory]
        self.load_model(composite, dirs[0] if dirs else "", extra_texture_dirs=dirs[1:])
        if selected_id:
            self.select_scene_object(selected_id)
        else:
            self.set_selected_node(None)

    def _build_scene_composite_model(self, instances: list, scene_name: str):
        visible = [obj for obj in instances if getattr(obj, "visible", True)]
        if not visible:
            return None
        try:
            from src.core.qt_core.geometry.model_data import KotorModel, ModelNode, NodeFlags
        except Exception:
            from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

        root = ModelNode(name="scene_root", flags=int(NodeFlags.HEADER))
        setattr(root, "_gr_scene_composite_root", True)
        composite = KotorModel(name=scene_name or "Untitled Scene", root_node=root)
        first_model = None
        for instance in visible:
            runtime_model = (getattr(instance, "metadata", {}) or {}).get("_runtime_model")
            model_root = getattr(runtime_model, "root_node", None)
            if runtime_model is None or model_root is None:
                continue
            first_model = first_model or runtime_model
            try:
                node = copy.deepcopy(model_root)
            except Exception:
                node = model_root.clone_shallow()
                node.children = []
            source_position = tuple(float(v) for v in getattr(model_root, "position", (0.0, 0.0, 0.0))[:3])
            source_rotation = tuple(float(v) for v in getattr(model_root, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
            scene_position = tuple(float(v) for v in instance.transform.position[:3])
            scene_rotation = self._euler_degrees_to_quat(instance.transform.rotation)
            scene_scale = tuple(float(v) for v in getattr(instance.transform, "scale", (1.0, 1.0, 1.0))[:3])
            node.parent = root
            node.position = scene_position
            node.rotation = scene_rotation
            node._gr_scale = scene_scale
            setattr(node, "_gr_scene_object_id", instance.id)
            setattr(node, "_gr_scene_object_root", True)
            setattr(node, "_gr_scene_object_name", instance.name)
            setattr(node, "_gr_scene_object_locked", bool(getattr(instance, "locked", False)))
            setattr(node, "_gr_scene_gpu_transform", True)
            setattr(node, "_gr_scene_source_position", source_position)
            setattr(node, "_gr_scene_source_rotation", source_rotation)
            pivot_world_fn = getattr(self, "_pivot_world_from_instance", None)
            pivot_world = (
                pivot_world_fn(instance)
                if callable(pivot_world_fn)
                else tuple(float(v) for v in instance.transform.position[:3])
            )
            pivot_data = getattr(instance, "pivot", None)
            pivot_local = tuple(float(v) for v in getattr(pivot_data, "position_local", (0.0, 0.0, 0.0))[:3])
            setattr(node, "_gr_pivot_world", pivot_world)
            setattr(node, "_gr_pivot_local", pivot_local)
            setattr(node, "_gr_pivot_world_dirty", False)
            setattr(node, "_gr_pivot_rotation", self._euler_degrees_to_quat(getattr(pivot_data, "rotation_local", (0.0, 0.0, 0.0))))
            setattr(node, "_gr_reference_rotation", getattr(node, "_gr_pivot_rotation"))
            setattr(node, "_gr_pivot_edit_mode", getattr(self, "_pivot_edit_mode", "affect_object_only"))

            # Preserve authored MDL node names for animations, skin bone maps,
            # and qBone/tBone rows while keeping scene placement as metadata.
            self._tag_scene_object_nodes(node, instance.id, node)
            self._tag_scene_source_indices(node, runtime_model)
            root.children.append(node)
        if not root.children:
            return None
        if first_model is not None:
            composite.game_version = getattr(first_model, "game_version", composite.game_version)
            composite.classification = "scene"
            composite.model_type = getattr(first_model, "model_type", composite.model_type)
        try:
            composite.compute_bounds()
            setattr(composite, "_gr_bounds_prepared", True)
            setattr(composite, "_gr_render_bounds", (composite.bb_min, composite.bb_max))
        except Exception:
            pass
        return composite

    def _tag_scene_object_nodes(self, node, object_id: str, root_node) -> None:
        stack = [node]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            setattr(current, "_gr_scene_object_id", object_id)
            setattr(current, "_gr_scene_object_root_ref", root_node)
            stack.extend(getattr(current, "children", []) or [])

    @staticmethod
    def _apply_scene_instance_scale(node, scale) -> None:
        try:
            sx, sy, sz = (float(v) for v in tuple(scale)[:3])
        except Exception:
            return
        if abs(sx - 1.0) < 1e-9 and abs(sy - 1.0) < 1e-9 and abs(sz - 1.0) < 1e-9:
            return
        stack = [node]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            try:
                px, py, pz = tuple(float(v) for v in getattr(current, "position", (0.0, 0.0, 0.0))[:3])
                current.position = (px * sx, py * sy, pz * sz)
            except Exception:
                pass
            vertices = getattr(current, "vertices", None)
            if vertices is not None:
                try:
                    current.vertices = [(float(x) * sx, float(y) * sy, float(z) * sz) for x, y, z in vertices]
                    compute_bounds = getattr(current, "compute_bounds", None)
                    if callable(compute_bounds):
                        compute_bounds()
                except Exception:
                    pass
            stack.extend(getattr(current, "children", []) or [])

    def _tag_scene_source_indices(self, copied_root, source_model) -> None:
        """Preserve original MDL DFS indices on scene copies for qBone lookup."""
        try:
            source_nodes = list(source_model.all_nodes()) if hasattr(source_model, "all_nodes") else []
        except Exception:
            source_nodes = []
        if not source_nodes:
            return

        copied_nodes = []
        stack = [copied_root]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            copied_nodes.append(current)
            stack.extend(reversed(getattr(current, "children", []) or []))

        for idx, current in enumerate(copied_nodes):
            if idx >= len(source_nodes):
                break
            setattr(current, "_gr_source_dfs_index", idx)
            setattr(current, "_gr_source_model_id", id(source_model))
            setattr(current, "_gr_source_node_name", getattr(source_nodes[idx], "name", ""))

    @staticmethod
    def _euler_degrees_to_quat(rotation: tuple[float, float, float]) -> tuple[float, float, float, float]:
        try:
            rx, ry, rz = (math.radians(float(v)) for v in rotation[:3])
        except Exception:
            return (0.0, 0.0, 0.0, 1.0)
        cx, sx = math.cos(rx * 0.5), math.sin(rx * 0.5)
        cy, sy = math.cos(ry * 0.5), math.sin(ry * 0.5)
        cz, sz = math.cos(rz * 0.5), math.sin(rz * 0.5)
        return (
            sx * cy * cz + cx * sy * sz,
            cx * sy * cz - sx * cy * sz,
            cx * cy * sz + sx * sy * cz,
            cx * cy * cz - sx * sy * sz,
        )

    def select_scene_object(self, object_id: str) -> None:
        node = self._scene_node_for_object(object_id)
        self.set_selected_node(node)

    def _scene_node_for_object(self, object_id: str):
        model = self.model
        if model is None or not getattr(model, "root_node", None):
            return None
        for child in getattr(model.root_node, "children", []) or []:
            if getattr(child, "_gr_scene_object_id", "") == object_id:
                return child
        return None

    def _scene_root_for_node(self, node):
        if node is None:
            return None
        root_ref = getattr(node, "_gr_scene_object_root_ref", None)
        if root_ref is not None:
            return root_ref
        current = node
        while current is not None:
            if bool(getattr(current, "_gr_scene_object_root", False)):
                return current
            current = getattr(current, "parent", None)
        return None

    def refresh_model_geometry(self) -> None:
        """Refresh bounds/caches after in-place model vertex transforms."""
        if self.model is None:
            return
        try:
            self._compute_bb(self.model)
        except Exception:
            pass
        try:
            self._renderer._wt_cache.clear()
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
        except Exception:
            pass
        if self._gpu_renderer is not None:
            try:
                self._gpu_renderer.clear_caches()
            except Exception:
                pass
        self._request_render(fast=True)

    def set_external_skeleton(
        self,
        model,
        offset=(0.0, 0.0, 0.0),
    ) -> None:
        """Preview a reference skeleton over the active model (M12/T1202)."""
        self._renderer._ext_skeleton = model
        self._renderer._ext_skel_scale = 1.0
        self._renderer._ext_skel_selected_node = None
        self._renderer._ext_skel_selected_ids = set()
        self._selected_joint_nodes = []
        try:
            self._renderer._ext_skel_offset = [
                float(offset[0]),
                float(offset[1]),
                float(offset[2]),
            ]
        except Exception:
            self._renderer._ext_skel_offset = [0.0, 0.0, 0.0]
        if offset == (0.0, 0.0, 0.0):
            self._fit_external_skeleton_overlay(model)
        self._request_render()

    def clear_external_skeleton(self) -> None:
        """Remove the reference-skeleton preview overlay."""
        self._renderer._ext_skeleton = None
        self._renderer._ext_skel_offset = [0.0, 0.0, 0.0]
        self._renderer._ext_skel_scale = 1.0
        self._renderer._ext_bone_screen_positions = []
        self._renderer._ext_skel_selected_node = None
        self._renderer._ext_skel_selected_ids = set()
        self._request_render()

    def _fit_external_skeleton_overlay(self, skeleton) -> None:
        """Fit a KOTOR template skeleton preview to the active source mesh."""
        if self.model is None or skeleton is None:
            return
        try:
            target_min = tuple(float(v) for v in getattr(self.model, "bb_min"))
            target_max = tuple(float(v) for v in getattr(self.model, "bb_max"))
        except Exception:
            return
        if len(target_min) != 3 or len(target_max) != 3:
            return
        points = []
        try:
            nodes = list(skeleton.all_nodes()) if hasattr(skeleton, "all_nodes") else []
        except Exception:
            nodes = []
        for node in nodes:
            try:
                if getattr(node, "is_skin", False):
                    continue
                p = tuple(float(v) for v in node.bone_world_position())
            except Exception:
                continue
            if len(p) == 3:
                points.append(p)
        if not points:
            return
        skel_min = tuple(min(p[i] for p in points) for i in range(3))
        skel_max = tuple(max(p[i] for p in points) for i in range(3))
        target_h = max(target_max[2] - target_min[2], 1e-6)
        skel_h = max(skel_max[2] - skel_min[2], 1e-6)
        scale = max(0.05, min(50.0, target_h / skel_h))
        target_center = tuple((target_min[i] + target_max[i]) * 0.5 for i in range(3))
        skel_center = tuple((skel_min[i] + skel_max[i]) * 0.5 for i in range(3))
        self._renderer._ext_skel_scale = scale
        self._renderer._ext_skel_offset = [
            target_center[i] - skel_center[i] * scale
            for i in range(3)
        ]

    def set_acurig_guides(self, guides: dict) -> None:
        """Display live AcuRig guide positions over the body rig view."""
        if hasattr(self._renderer, "set_acurig_guides"):
            self._renderer.set_acurig_guides(guides or {})
        else:                                             # pragma: no cover
            self._renderer._acurig_guides_overlay = guides or {}
        self._request_render()

    def clear_acurig_guides(self) -> None:
        """Remove the AcuRig guide overlay."""
        if hasattr(self._renderer, "set_acurig_guides"):
            self._renderer.set_acurig_guides({})
        else:                                             # pragma: no cover
            self._renderer._acurig_guides_overlay = {}
        self._request_render()

    def set_dual_viewport_mode(self, enabled: bool) -> None:
        self._dual_viewport_mode = bool(enabled)

    def set_animation_supermodel_hud_placement(self, placement: str) -> None:
        value = str(placement or "").strip().lower()
        if value not in {"center", "bottom"}:
            value = "center"
        self._renderer.animation_supermodel_hud_placement = value
        self._request_render()

    def set_hidden_bone_name_fragments(self, fragments: list[str] | tuple[str, ...]) -> None:
        self._renderer.set_hidden_bone_name_fragments(fragments)
        selected = getattr(self._renderer, "selected_node", None)
        if selected is not None and self._renderer.is_hidden_bone_name(getattr(selected, "name", "")):
            self._renderer.selected_node = None
        self._request_render()

    def set_shared_gpu_renderer(self, renderer: Optional[GpuRenderer]) -> None:
        self._gpu_renderer = renderer
        self._owns_gpu_renderer = renderer is None
        theme = getattr(self, "_current_theme", None)
        if theme is not None and self._gpu_renderer is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
            self._gpu_renderer.set_theme_colors(theme)
        elif self._gpu_renderer is not None:
            self._apply_native_palette_to_renderers()

    def set_renderer_settings(self, settings: RendererSettings | dict | None) -> None:
        self._renderer_settings = settings if isinstance(settings, RendererSettings) else RendererSettings.from_settings(settings or {})
        if self._gpu_renderer is not None and self._owns_gpu_renderer:
            apply_settings = getattr(self._gpu_renderer, "set_settings", None)
            if callable(apply_settings):
                apply_settings(self._renderer_settings)
            else:
                shutdown = getattr(self._gpu_renderer, "shutdown", None) or getattr(self._gpu_renderer, "release", None)
                if callable(shutdown):
                    shutdown()
                self._gpu_renderer = None
        self._request_render(fast=True)

    def set_game_library(self, library, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_game_library(library, game_tag)

    def set_installation(self, installation, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_installation(installation, game_tag)

    def set_resource_manager(self, manager, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_resource_manager(manager, game_tag)

    @property
    def tex_cache(self):
        return self._renderer.tex_cache

    def toggle_wireframe(self, checked: Optional[bool] = None) -> None:
        if checked is False:
            self.set_shade_mode("solid")
        else:
            self.set_shade_mode("wire")

    def set_shade_mode(self, mode: str) -> None:
        mode_key = (mode or "solid").strip().lower()
        if mode_key in {"wireframe", "wire"}:
            self._renderer.show_solid = False
            self._renderer.show_wireframe = True
        elif mode_key in {"both", "solid+wire", "solid_wire"}:
            self._renderer.show_solid = True
            self._renderer.show_wireframe = True
        else:
            self._renderer.show_solid = True
            self._renderer.show_wireframe = False
        self._sync_shade_buttons()
        self._request_render()

    def _sync_shade_buttons(self) -> None:
        state = {
            "solid_button": self._renderer.show_solid and not self._renderer.show_wireframe,
            "wire_button": self._renderer.show_wireframe and not self._renderer.show_solid,
            "solid_wire_button": self._renderer.show_solid and self._renderer.show_wireframe,
        }
        for name, checked in state.items():
            button = getattr(self, name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)

    def set_render_mode(self, mode: str) -> None:
        mode_key = (mode or "realistic").strip().lower()
        if mode_key not in {"realistic", "shaded", "flat"}:
            mode_key = "realistic"
        self._renderer.render_mode = mode_key
        self.toggle_gpu_renderer(True)
        self._sync_render_mode_buttons()
        self._request_render(fast=True)

    def _sync_render_mode_buttons(self) -> None:
        active = getattr(self._renderer, "render_mode", "realistic") or "realistic"
        for mode, name in (
            ("realistic", "render_realistic_button"),
            ("shaded", "render_shaded_button"),
            ("flat", "render_flat_button"),
        ):
            button = getattr(self, name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(active == mode)
            button.blockSignals(False)

    def toggle_bones(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_bones = bool(checked) if checked is not None else not self._renderer.show_bones
        self._request_render()

    def toggle_texture(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_texture = bool(checked) if checked is not None else not self._renderer.show_texture
        self.texture_button.blockSignals(True)
        self.texture_button.setChecked(self._renderer.show_texture)
        self.texture_button.blockSignals(False)
        self._request_render()

    def toggle_grid(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not bool(getattr(self._renderer, "show_grid", True))
        self._renderer.show_grid = enabled
        if self._gpu_renderer is not None:
            self._gpu_renderer.show_grid = enabled
        self.grid_button.blockSignals(True)
        self.grid_button.setChecked(enabled)
        self.grid_button.blockSignals(False)
        self._request_render(fast=True)

    def set_lighting_mode(self, mode: str) -> None:
        mode = str(mode or "scene").strip().lower()
        allowed = {
            "scene",
            "unlit",
            "studio",
            "fullbright",
            "lightmap_preview",
            "diffuse_only",
            "normal_only",
            "specular_only",
            "environment_only",
            "shader_complexity",
            "photoreal_preview",
        }
        if mode not in allowed:
            mode = "scene"
        setattr(self._renderer, "lighting_mode", mode)
        if self._gpu_renderer is not None:
            self._gpu_renderer.lighting_mode = mode
        self._request_render()

    def set_texture_map_enabled(self, map_name: str, enabled: bool) -> None:
        key = str(map_name or "").strip().lower()
        attr = {
            "diffuse": "show_diffuse_map",
            "lightmap": "show_lightmap_map",
            "environment": "show_environment_map",
            "env": "show_environment_map",
            "specular": "show_specular_map",
            "normal": "show_normal_map",
        }.get(key)
        if not attr:
            return
        setattr(self._renderer, attr, bool(enabled))
        if self._gpu_renderer is not None:
            setattr(self._gpu_renderer, attr, bool(enabled))
        self._request_render()

    def set_lightmap_settings(self, intensity: float, mode: str) -> None:
        try:
            intensity_value = max(0.0, min(float(intensity), 4.0))
        except (TypeError, ValueError):
            intensity_value = 0.55
        mode_value = str(mode or "baked").strip().lower()
        if mode_value not in {"disabled", "baked", "dynamic_preview", "hybrid", "debug", "phong", "emissive"}:
            mode_value = "baked"
        setattr(self._renderer, "lightmap_intensity", intensity_value)
        setattr(self._renderer, "lightmap_mode", mode_value)
        if self._gpu_renderer is not None:
            self._gpu_renderer.lightmap_intensity = intensity_value
            self._gpu_renderer.lightmap_mode = mode_value
        self._request_render()

    def set_shader_complexity_mode(self, mode: str) -> None:
        value = str(mode or "off").strip().lower()
        if value not in {"off", "basic", "overdraw", "texture_cost", "lighting_cost", "full_complexity"}:
            value = "off"
        setattr(self._renderer, "shader_complexity_mode", value)
        if self._gpu_renderer is not None:
            setattr(self._gpu_renderer, "shader_complexity_mode", value)
        if value != "off":
            self.set_lighting_mode("shader_complexity")
        else:
            self._request_render()

    def set_light_helper_visibility(self, helpers: bool, volumes: bool) -> None:
        for target in (self._renderer, self._gpu_renderer):
            if target is None:
                continue
            setattr(target, "show_light_gizmos", bool(helpers))
            setattr(target, "show_light_radius_volumes", bool(volumes))
        self._request_render()

    def refresh_lighting(self) -> None:
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        self._request_render()

    def refresh_cameras(self) -> None:
        if self._camera_view_active:
            camera = self.camera_manager.get_active_camera()
            if camera is not None:
                self.update_view_from_camera(camera)
            else:
                self.switch_to_perspective()
        self._refresh_camera_view_combo()
        self._request_render()

    def create_scene_camera(self, camera_type: str = "Cinematic Camera"):
        camera = self.camera_controller.create_camera(camera_type=camera_type, from_current_view=True)
        self.set_selected_node(camera.original_ref)
        self._refresh_camera_view_combo()
        self.cameraChanged.emit()
        self._request_render()
        return camera

    def create_camera_from_current_view(self, make_active: bool = True):
        camera = self.camera_controller.create_camera_from_current_view(make_active=make_active)
        self.set_selected_node(camera.original_ref)
        self._refresh_camera_view_combo()
        if make_active:
            self.switch_to_camera(camera.id)
        self.cameraChanged.emit()
        return camera

    def duplicate_selected_camera(self, camera_id: str | None = None):
        camera = self.camera_manager.get_camera(camera_id or "")
        if camera is None:
            selected = self.camera_manager.selected_cameras()
            camera = selected[-1] if selected else None
        if camera is None:
            return None
        dup = self.camera_manager.duplicate_camera(camera.id)
        if dup is not None:
            self.set_selected_node(dup.original_ref)
        self._refresh_camera_view_combo()
        self.cameraChanged.emit()
        self._request_render()
        return dup

    def delete_camera(self, camera_id: str) -> bool:
        if self.camera_manager.active_camera_id == camera_id:
            self.switch_to_perspective()
        ok = self.camera_manager.delete_camera(camera_id)
        if ok:
            self._refresh_camera_view_combo()
            self.cameraChanged.emit()
            self._request_render()
        return ok

    def delete_selected_camera(self) -> None:
        selected = self.camera_manager.selected_cameras()
        if len(selected) > 1:
            answer = QtWidgets.QMessageBox.question(self, "Delete Cameras", f"Delete {len(selected)} selected cameras?")
            if answer != QtWidgets.QMessageBox.Yes:
                return
        for camera in list(selected):
            self.delete_camera(camera.id)

    def switch_to_camera(self, camera_id: str):
        camera = self.camera_manager.set_active_camera(camera_id)
        if camera is None:
            return None
        if not self._camera_view_active:
            self._camera_adapter.save_perspective_state()
        self._camera_view_active = True
        self.update_view_from_camera(camera)
        self._refresh_camera_view_combo()
        self.activeCameraChanged.emit(camera.original_ref)
        self._request_render()
        return camera

    def switch_to_perspective(self) -> None:
        self.camera_manager.clear_active_camera()
        if self._camera_view_active:
            self._camera_adapter.restore_perspective_state()
        self._camera_view_active = False
        self._refresh_camera_view_combo()
        self.activeCameraChanged.emit(None)
        self._request_render()

    def is_camera_view_active(self) -> bool:
        return bool(self._camera_view_active and self.camera_manager.get_active_camera() is not None)

    def update_view_from_camera(self, camera) -> None:
        self._camera_adapter.update_view_from_camera(camera)
        self._request_render()

    def update_camera_from_view(self, camera=None) -> None:
        target = camera or self.camera_manager.get_active_camera()
        if target is None:
            return
        if bool(getattr(target, "locked", False)):
            return
        self._camera_adapter.update_camera_from_view(target)
        self.camera_manager._store_on_model()
        self.cameraChanged.emit()

    def align_active_camera_to_view(self):
        camera = self.camera_controller.align_active_camera_to_view()
        if camera is not None:
            self.cameraChanged.emit()
            self._request_render()
        return camera

    def align_camera_to_current_view(self, camera_id: str):
        camera = self.camera_manager.get_camera(camera_id)
        if camera is None:
            return None
        self._camera_adapter.update_camera_from_view(camera)
        self.cameraChanged.emit()
        self._request_render()
        return camera

    def align_view_to_camera(self, camera_id: str):
        return self.switch_to_camera(camera_id)

    def set_lock_view_to_camera(self, checked: Optional[bool] = None) -> None:
        self._lock_view_to_camera = bool(checked) if checked is not None else not self._lock_view_to_camera
        if hasattr(self, "lock_camera_button"):
            self.lock_camera_button.blockSignals(True)
            self.lock_camera_button.setChecked(self._lock_view_to_camera)
            self.lock_camera_button.blockSignals(False)

    def render_still_frame(self, settings=None, camera_id: str = "") -> str:
        camera = self.camera_manager.get_camera(camera_id) if camera_id else self.camera_manager.get_active_camera()
        return self._camera_frame_renderer.render_to_file(
            settings,
            camera,
            module_name=str(getattr(self.model, "name", "") or "scene"),
        )

    def _refresh_camera_view_combo(self) -> None:
        combo = getattr(self, "camera_view_combo", None)
        if combo is None:
            return
        current = self.camera_manager.active_camera_id if self._camera_view_active else ""
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Perspective", "")
        combo.addItem("Top", "__top__")
        combo.addItem("Front", "__front__")
        combo.addItem("Side", "__side__")
        for camera in self.camera_manager.get_all_cameras():
            combo.addItem(camera.name, camera.id)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _on_camera_view_combo_changed(self) -> None:
        combo = getattr(self, "camera_view_combo", None)
        if combo is None:
            return
        value = str(combo.currentData() or "")
        if not value:
            self.switch_to_perspective()
        elif value == "__top__":
            self.switch_to_perspective()
            self._snap_to_view("top")
        elif value == "__front__":
            self.switch_to_perspective()
            self._snap_to_view("front")
        elif value == "__side__":
            self.switch_to_perspective()
            self._snap_to_view("right")
        else:
            self.switch_to_camera(value)

    def toggle_gpu_renderer(self, checked: Optional[bool] = None) -> None:
        self._use_gpu = True
        self.renderer_button.setChecked(True)
        self.renderer_button.setToolTip("GPU renderer")
        self._request_render(fast=True)

    def toggle_xray(self, checked: Optional[bool] = None) -> None:
        self._xray_mode = bool(checked) if checked is not None else not self._xray_mode
        self.xray_button.blockSignals(True)
        self.xray_button.setChecked(self._xray_mode)
        self.xray_button.blockSignals(False)
        self._request_render(fast=True)

    def toggle_joint_dots(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for the AccuRig joint-dot HUD layer."""
        enabled = bool(checked) if checked is not None else not self._joint_dot_enabled
        self.set_joint_dot_enabled(enabled)

    def toggle_weight_heatmap(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for the selected-bone weight heat-map HUD layer."""
        enabled = bool(checked) if checked is not None else not self._weight_heatmap_enabled
        self.set_weight_heatmap_enabled(enabled)

    def toggle_walkmesh(self, checked: Optional[bool] = None) -> None:
        if self._renderer._walkmesh_overlay is None:
            parent = self.window()
            coload = getattr(parent, "_try_coload_walkmesh", None)
            if callable(coload):
                try:
                    coload()
                except TypeError:
                    coload(None)
            if self._renderer._walkmesh_overlay is None:
                self.walkmesh_button.setChecked(False)
                self._request_render()
                return
        self._renderer.show_walkmesh = bool(checked) if checked is not None else not self._renderer.show_walkmesh
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def toggle_gimbal(self, checked: Optional[bool] = None) -> None:
        current = self._ensure_renderer_gimbal_state()
        self._set_renderer_gimbal_visible(bool(checked) if checked is not None else not current)
        self.gimbal_button.setChecked(self._ensure_renderer_gimbal_state())
        self._request_render()

    def toggle_measurement_mode(self, checked: Optional[bool] = None) -> None:
        self._measurement_mode = bool(checked) if checked is not None else not self._measurement_mode
        self.measure_button.setChecked(self._measurement_mode)
        if not self._measurement_mode:
            self.measurement_controller.active = False
        self._request_render()

    def toggle_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.measurement_settings.snap_enabled
        self.measurement_settings.snap_enabled = enabled
        self._apply_snap_settings_to_controller()
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def toggle_angle_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.angle_snap.enabled
        self.angle_snap.set_enabled(enabled)
        self.measurement_settings.angle_snap_enabled = enabled
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def toggle_percent_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.percent_snap.enabled
        self.percent_snap.set_enabled(enabled)
        self.measurement_settings.percent_snap_enabled = enabled
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def _on_angle_snap_increment_changed(self, text: str) -> None:
        try:
            value = float(str(text or "").replace("deg", "").replace("°", "").strip())
        except ValueError:
            return
        value = max(1e-6, min(value, 360.0))
        self.angle_snap.set_increment_degrees(value)
        self.measurement_settings.angle_snap_increment_degrees = value
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def _on_percent_snap_increment_changed(self, text: str) -> None:
        try:
            value = float(str(text or "").replace("%", "").strip())
        except ValueError:
            return
        value = max(1e-6, min(value, 1000.0))
        self.percent_snap.set_increment_percent(value)
        self.measurement_settings.percent_snap_increment_percent = value
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def set_measurement_settings(self, values: dict | MeasurementSettings | None) -> None:
        settings = values if isinstance(values, MeasurementSettings) else MeasurementSettings.from_dict(values)
        self.measurement_settings = settings
        self.unit_system.set_system_unit(settings.system_unit)
        self.unit_system.set_display_unit(settings.display_unit)
        self.angle_snap.set_enabled(settings.angle_snap_enabled)
        self.angle_snap.set_increment_degrees(settings.angle_snap_increment_degrees)
        self.percent_snap.set_enabled(settings.percent_snap_enabled)
        self.percent_snap.set_increment_percent(settings.percent_snap_increment_percent)
        self.measurement_controller.configure(self.unit_system, settings.distance_precision)
        self._renderer.unit_system = self.unit_system
        self._renderer.grid_measurement = GridMeasurement(
            self.unit_system,
            minor_spacing=settings.minor_grid_spacing,
            major_spacing=settings.major_grid_spacing,
            show_labels=settings.show_grid_measurements,
            precision=settings.distance_precision,
        )
        self._apply_snap_settings_to_controller()
        self._sync_transform_typein_bar()
        self._request_render()

    def _apply_snap_settings_to_controller(self) -> None:
        controller = getattr(self._transform_gizmo, "controller", None)
        if controller is not None and hasattr(controller, "set_position_snap"):
            controller.set_position_snap(
                self.measurement_settings.snap_enabled,
                self.measurement_settings.minor_grid_spacing,
            )

    def _emit_measurement_settings_changed(self) -> None:
        self.measurementSettingsChanged.emit({"measurement": self.measurement_settings.to_dict()})

    def _sync_transform_typein_bar(self) -> None:
        bar = getattr(self, "transform_typein_bar", None)
        if bar is None:
            return
        mode = self._transform_gizmo.mode
        mode_label = {
            GizmoMode.TRANSLATE: "MOVE",
            GizmoMode.ROTATE: "ROTATE",
            GizmoMode.SCALE: "SCALE",
        }.get(mode, "MOVE")
        bar.set_mode_label(mode_label)
        bar.set_grid_text(self.unit_system.format_distance(
            self.measurement_settings.minor_grid_spacing,
            self.measurement_settings.distance_precision,
        ))
        bar.set_snap_state(
            snap=self.measurement_settings.snap_enabled,
            angle=self.angle_snap.enabled,
            percent=self.percent_snap.enabled,
        )
        bar.set_increment_texts(
            angle=f"{self.angle_snap.increment_degrees:g}°",
            percent=f"{self.percent_snap.increment_percent:g}%",
        )
        node = getattr(self._renderer, "selected_node", None)
        bar.set_transform_enabled(node is not None)
        if node is None:
            bar.set_transform_values(("", "", ""))
            return
        if mode == GizmoMode.ROTATE:
            rx, ry, rz = self._quat_to_euler_degrees(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            bar.set_transform_values((f"{rx:.3f}°", f"{ry:.3f}°", f"{rz:.3f}°"))
        elif mode == GizmoMode.SCALE:
            sx, sy, sz = self._node_scale(node)
            bar.set_transform_values((f"{sx:.3f}", f"{sy:.3f}", f"{sz:.3f}"))
        else:
            px, py, pz = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
            p = self.measurement_settings.distance_precision
            bar.set_transform_values(
                (
                    self.unit_system.format_distance(px, p),
                    self.unit_system.format_distance(py, p),
                    self.unit_system.format_distance(pz, p),
                )
            )

    def _on_grid_spacing_edited(self, text: str) -> None:
        try:
            spacing = self.unit_system.parse_distance(text)
        except ValueError:
            self._sync_transform_typein_bar()
            return
        spacing = max(1e-6, float(spacing))
        self.measurement_settings.minor_grid_spacing = spacing
        self.measurement_settings.major_grid_spacing = max(spacing, spacing * 10.0)
        self.set_measurement_settings(self.measurement_settings)
        self._emit_measurement_settings_changed()

    def _on_transform_typein_edited(self, axis: str, text: str) -> None:
        node = getattr(self._renderer, "selected_node", None)
        if node is None:
            self._sync_transform_typein_bar()
            return
        axis_index = {"X": 0, "Y": 1, "Z": 2}.get(axis)
        if axis_index is None:
            return
        before_pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
        before_rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        before_vertices = self._snapshot_vertices(node)
        before_scale = self._node_scale(node)
        before_pivot_world = self._optional_tuple_attr(node, "_gr_pivot_world")
        before_pivot_rotation = self._optional_tuple_attr(node, "_gr_pivot_rotation")
        try:
            if self._transform_gizmo.mode == GizmoMode.ROTATE:
                self._apply_rotation_typein(node, axis_index, text)
                label = "Set Rotation"
            elif self._transform_gizmo.mode == GizmoMode.SCALE:
                self._apply_scale_typein(node, axis_index, text)
                label = "Set Scale"
            else:
                self._apply_position_typein(node, axis_index, text)
                label = "Set Position"
        except ValueError:
            self._sync_transform_typein_bar()
            return
        after_vertices = self._snapshot_vertices(node)
        self._commit_node_transform(
            node,
            before_pos,
            before_rot,
            tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
            tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            label,
            before_vertices=before_vertices,
            after_vertices=after_vertices,
            before_scale=before_scale,
            after_scale=self._node_scale(node),
            before_pivot_world=before_pivot_world,
            after_pivot_world=self._optional_tuple_attr(node, "_gr_pivot_world"),
            before_pivot_rotation=before_pivot_rotation,
            after_pivot_rotation=self._optional_tuple_attr(node, "_gr_pivot_rotation"),
        )
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render(fast=True)

    def _apply_position_typein(self, node, axis_index: int, text: str) -> None:
        value = self.unit_system.parse_distance(text)
        if self.measurement_settings.snap_enabled:
            inc = self.measurement_settings.minor_grid_spacing
            value = round(value / inc) * inc
        position = list(tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3]))
        old_position = tuple(position)
        position[axis_index] = float(value)
        new_position = tuple(position)
        node.position = new_position
        if str(getattr(node, "_gr_pivot_edit_mode", "") or "") != "affect_pivot_only":
            pivot_world = getattr(node, "_gr_pivot_world", None)
            if pivot_world is not None:
                delta = (
                    new_position[0] - old_position[0],
                    new_position[1] - old_position[1],
                    new_position[2] - old_position[2],
                )
                updated = (
                    float(pivot_world[0]) + delta[0],
                    float(pivot_world[1]) + delta[1],
                    float(pivot_world[2]) + delta[2],
                )
                setattr(node, "_gr_pivot_world", updated)
                setattr(node, "_gr_pivot_world_dirty", True)
                setattr(node, "_gr_gizmo_world_position", updated)

    def _apply_rotation_typein(self, node, axis_index: int, text: str) -> None:
        value = float(str(text or "").replace("deg", "").replace("°", "").strip())
        if self.angle_snap.enabled:
            value = self.angle_snap.snap_degrees(value)
        euler = list(self._quat_to_euler_degrees(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))))
        euler[axis_index] = value
        node.rotation = self._euler_degrees_to_quat(euler)

    def _apply_scale_typein(self, node, axis_index: int, text: str) -> None:
        raw = str(text or "").strip()
        if raw.endswith("%"):
            value = float(raw[:-1].strip()) / 100.0
        else:
            value = float(raw)
        if self.percent_snap.enabled:
            value = self.percent_snap.snap_scale_factor(value)
        value = max(0.001, float(value))
        scale = list(self._node_scale(node))
        old_value = max(0.001, scale[axis_index])
        scale[axis_index] = value
        ratio = value / old_value
        if bool(getattr(node, "is_camera", False)):
            node._gr_helper_size = max(0.05, float(getattr(node, "_gr_helper_size", 1.0) or 1.0) * ratio)
            node._gr_scale = tuple(scale)
            return
        if bool(getattr(node, "_gr_scene_object_root", False)):
            node._gr_scale = tuple(scale)
            return
        verts = getattr(node, "vertices", None)
        if verts is not None:
            node.vertices = [
                tuple(
                    coord * ratio if idx == axis_index else coord
                    for idx, coord in enumerate(tuple(vertex[:3]))
                )
                for vertex in verts
            ]
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
        node._gr_scale = tuple(scale)

    @staticmethod
    def _snapshot_vertices(node):
        vertices = getattr(node, "vertices", None)
        if vertices is None:
            return None
        return tuple(tuple(float(c) for c in vertex[:3]) for vertex in vertices)

    @staticmethod
    def _optional_tuple_attr(node, name: str):
        raw = getattr(node, name, None)
        if raw is None:
            return None
        try:
            return tuple(float(v) for v in raw)
        except Exception:
            return None

    @staticmethod
    def _node_scale(node) -> tuple[float, float, float]:
        raw = getattr(node, "_gr_scale", getattr(node, "scale", (1.0, 1.0, 1.0)))
        try:
            values = tuple(float(v) for v in raw[:3])
        except Exception:
            values = (1.0, 1.0, 1.0)
        return (values + (1.0, 1.0, 1.0))[:3]

    @staticmethod
    def _quat_to_euler_degrees(q) -> tuple[float, float, float]:
        try:
            x, y, z, w = [float(v) for v in q[:4]]
        except Exception:
            return (0.0, 0.0, 0.0)
        length = math.sqrt(x * x + y * y + z * z + w * w)
        if length <= 1e-9:
            return (0.0, 0.0, 0.0)
        x, y, z, w = x / length, y / length, z / length, w / length
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2.0 * (w * y - z * x)
        pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))

    @staticmethod
    def _euler_degrees_to_quat(euler) -> tuple[float, float, float, float]:
        rx, ry, rz = (math.radians(float(v)) for v in tuple(euler)[:3])

        def axis_quat(axis: str, angle: float) -> tuple[float, float, float, float]:
            half = angle * 0.5
            s = math.sin(half)
            c = math.cos(half)
            if axis == "X":
                return (s, 0.0, 0.0, c)
            if axis == "Y":
                return (0.0, s, 0.0, c)
            return (0.0, 0.0, s, c)

        return multiply_quaternions(
            axis_quat("Z", rz),
            multiply_quaternions(axis_quat("Y", ry), axis_quat("X", rx)),
        )

    def cycle_gimbal_mode(self) -> None:
        self._transform_gizmo.cycle_mode()
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {self._transform_gizmo.mode.value.title()}")
        self._request_render()

    def set_gimbal_mode(self, mode: int) -> None:
        if mode == 2:
            self._transform_gizmo.set_mode(GizmoMode.ROTATE)
        elif mode == 3:
            self._transform_gizmo.set_mode(GizmoMode.SCALE)
        else:
            self._transform_gizmo.set_mode(GizmoMode.TRANSLATE)
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {self._transform_gizmo.mode.value.title()}")
        self._request_render(fast=True)

    def _set_transform_gizmo_mode(self, mode: GizmoMode) -> None:
        self._transform_gizmo.set_mode(mode)
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {mode.value.title()}")
        self._request_render(fast=True)

    def _sync_legacy_gimbal_mode(self) -> None:
        if self._transform_gizmo.mode == GizmoMode.ROTATE:
            self._renderer.gimbal_mode = 2
        elif self._transform_gizmo.mode == GizmoMode.SCALE:
            self._renderer.gimbal_mode = 3
        else:
            self._renderer.gimbal_mode = 1

    def frame_all(self) -> None:
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max)
        self._request_render()

    def frame_selection_or_all(self) -> None:
        bounds = self._selection_navigation_bounds()
        if bounds is not None:
            self.camera.frame_bounds(bounds[0], bounds[1])
        else:
            self.frame_all()
            return
        self._request_render()

    def reset_camera(self) -> None:
        self.camera.__init__()
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max, reset_view=True)
        self._request_render()

    # ── M6 / T605 — Head-mode camera preset ──────────────────────────
    def apply_head_camera_preset(self) -> tuple:
        """Apply :data:`head_workflow.HEAD_CAMERA_PRESET` to the camera.

        Pulls the canonical ``(eye, target, up, fov_deg, clip)`` framing
        for Head mode from :func:`head_workflow.head_camera_preset` and
        converts the eye→target vector into the :class:`ArcBallCamera`'s
        spherical state ``(target, distance, azimuth, elevation)``,
        then sets ``fov``, ``_near`` and ``_far`` to match.  Triggers a
        single render request on success.

        Returns
        -------
        (ok, message) : Tuple[bool, str]
            ``ok=False`` is returned when ``head_workflow`` is
            unavailable or the preset payload is malformed.  Callers
            (M6 / T605 mode-switch glue) can surface ``message`` via
            the bottom strip / status bar.
        """
        # Lazy-import the workflow service — same fallback chain the
        # other M6 UI hooks use so we don't bind to a particular
        # ``sys.path`` layout.
        hw = None
        try:
            from src.core.qt_core.characters import head_workflow as hw       # type: ignore
        except Exception:
            try:
                from core.qt_core.characters import head_workflow as hw      # type: ignore
            except Exception:
                try:                                      # pragma: no cover
                    import importlib.util as _u
                    import pathlib as _pl
                    _here = _pl.Path(__file__).resolve().parents[1]
                    _hw_path = _here / "core" / "head_workflow.py"
                    if _hw_path.is_file():
                        _spec = _u.spec_from_file_location(
                            "_gr_head_workflow_inline_t605", str(_hw_path),
                        )
                        _mod = _u.module_from_spec(_spec)
                        import sys as _sys
                        _sys.modules[_spec.name] = _mod
                        _spec.loader.exec_module(_mod)
                        hw = _mod
                except Exception:
                    hw = None
        if hw is None:                                    # pragma: no cover
            return False, "head_workflow unavailable; head camera preset skipped."

        try:
            sph = hw.head_camera_spherical()
        except ValueError as exc:
            return False, f"Head camera preset malformed: {exc}"
        except Exception as exc:                          # pragma: no cover
            return False, f"head_camera_spherical() raised: {exc}"

        cam = self.camera
        cam.target    = [sph["target_x"], sph["target_y"], sph["target_z"]]
        cam.distance  = sph["distance"]
        cam.azimuth   = sph["azimuth"]
        cam.elevation = sph["elevation"]
        cam.fov       = sph["fov"]
        cam._near     = sph["near"]
        cam._far      = sph["far"]

        try:
            self._request_render()
        except Exception:                                 # pragma: no cover
            pass

        return True, (
            f"Head camera preset applied (fov={cam.fov:.1f}°, "
            f"dist={cam.distance:.2f})."
        )

    # ── T403: Mini-thumbnail inset wiring ──────────────────────────────
    def _reposition_thumbnail(self) -> None:
        """Pin the thumbnail to the top-right corner of the canvas."""
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        cw = max(0, self.canvas.width())
        x = cw - THUMBNAIL_WIDTH_PX - THUMBNAIL_MARGIN_PX
        y = THUMBNAIL_MARGIN_PX
        viewcube = getattr(self, "_viewcube_widget", None)
        if viewcube is not None and viewcube.isVisible():
            y = max(y, viewcube.y() + viewcube.height() + THUMBNAIL_MARGIN_PX)
        # Guard against collapsing canvases: if the widget would clip
        # off-screen, hide it rather than render half-off.
        if x < THUMBNAIL_MARGIN_PX or y + THUMBNAIL_HEIGHT_PX + THUMBNAIL_MARGIN_PX > self.canvas.height():
            self._thumbnail_widget.hide()
            return
        self._thumbnail_widget.move(x, y)
        self._apply_thumbnail_visibility()

    def _apply_thumbnail_visibility(self) -> None:
        """Combine user-setting + force-hide (Head close-up) flags."""
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        if self._thumbnail_force_hidden or not self._thumbnail_visible_setting:
            self._thumbnail_widget.hide()
            return
        # Only show once we actually have a model + a thumbnail to render.
        if self.model is None:
            self._thumbnail_widget.hide()
            return
        self._thumbnail_widget.show()
        self._thumbnail_widget.raise_()

    def set_thumbnail_visible(self, visible: bool) -> None:
        """User-level setting (Body / Creature modes)."""
        self._thumbnail_visible_setting = bool(visible)
        self._apply_thumbnail_visibility()

    def set_thumbnail_force_hidden(self, hidden: bool) -> None:
        """Auto-hide hook used by Head close-up mode."""
        self._thumbnail_force_hidden = bool(hidden)
        self._apply_thumbnail_visibility()

    @property
    def thumbnail_widget(self) -> Optional["_MiniThumbnailWidget"]:
        return getattr(self, "_thumbnail_widget", None)

    def refresh_thumbnail(self) -> None:
        """Re-render the neutral-pose thumbnail from the current model.

        Cheap to call: only runs when a model is loaded and the
        thumbnail is currently visible / configured-visible.  The
        render uses a *dedicated* throwaway camera + a clean
        FrameRenderer state (no joint overlay, no walkmesh, no
        gimbal) so the inset is a clean reference image.
        """
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        if self.model is None:
            self._thumbnail_widget.set_thumbnail(None)
            self._apply_thumbnail_visibility()
            return
        try:
            pixmap = self._render_neutral_pose_thumbnail(
                THUMBNAIL_WIDTH_PX - 4, THUMBNAIL_HEIGHT_PX - 4
            )
        except Exception as exc:
            log.debug("Thumbnail render failed: %s", exc)
            pixmap = None
        self._thumbnail_widget.set_thumbnail(pixmap)
        self._apply_thumbnail_visibility()

    def _refresh_thumbnail_safe(self) -> None:
        """Defensive wrapper around :meth:`refresh_thumbnail`.

        Used from hot paths (``load_model``, ``_render_now``) where a
        crash in the thumbnail render path must not propagate up and
        kill the main viewport.  Any exception is logged and swallowed.
        """
        try:
            self.refresh_thumbnail()
        except Exception as exc:
            log.debug("Thumbnail refresh suppressed: %s", exc)

    def _render_neutral_pose_thumbnail(self, w: int, h: int) -> Optional[QtGui.QPixmap]:
        """Render a clean, joint-overlay-free preview at neutral pose.

        Implementation notes:
          • Uses a private ``ArcBallCamera`` framed to the model bbox
            so the thumbnail composition is independent of the user's
            main-view camera (avoids zoomed-in / panned-off-screen
            thumbnails after the user pokes the main view).
          • Temporarily flips the renderer's ``show_bones`` /
            ``selected_node`` / animation state to neutral so the
            preview reads as a clean reference; original state is
            restored in a try/finally.
          • Uses the viewport GPU renderer only; if GPU rendering is
            unavailable, no CPU thumbnail is generated.
        """
        if self.model is None:
            return None
        ren = self._renderer
        # Snapshot state we are about to override.
        snap = {
            "show_bones": ren.show_bones,
            "selected_node": ren.selected_node,
            "show_gimbal": getattr(ren, "show_gimbal", False),
            "show_walkmesh": getattr(ren, "show_walkmesh", False),
            "show_wireframe": ren.show_wireframe,
            "anim_pose": getattr(ren, "_anim_pose", None),
        }
        # Use a private camera framed to the model bbox.
        main_cam = ren.cam
        try:
            thumb_cam = ArcBallCamera()
            try:
                bb_min, bb_max = ren._get_render_bounds()
                thumb_cam.frame_bounds(bb_min, bb_max, reset_view=True)
            except Exception:
                pass
            ren.cam = thumb_cam
            ren.show_bones = False
            ren.selected_node = None
            if hasattr(ren, "show_gimbal"):
                ren.show_gimbal = False
            if hasattr(ren, "show_walkmesh"):
                ren.show_walkmesh = False
            ren.show_wireframe = False
            if hasattr(ren, "_anim_pose"):
                ren._anim_pose = None
            img = None
            if self.model is not None:
                try:
                    if self._gpu_renderer is None:
                        self._gpu_renderer = create_viewport_renderer(self._renderer_settings)
                    self._preload_gpu_textures()
                    tex_cache = getattr(ren, "tex_cache", None)
                    textures = {
                        key: value
                        for key, value in getattr(tex_cache, "_cache", {}).items()
                        if value is not None
                    }
                    self._gpu_renderer.interactive = False
                    self._gpu_renderer.show_wireframe = False
                    self._gpu_renderer.show_grid = True
                    self._gpu_renderer.cull_faces = False
                    img = self._gpu_renderer.render(
                        self.model,
                        thumb_cam,
                        int(w),
                        int(h),
                        textures=textures,
                        anim_pose=None,
                        anim_time=0.0,
                        anim_base_pose=None,
                    )
                except Exception as exc:
                    log.debug("Thumbnail GPU render failed: %s", exc)
                    img = None
            if img is None:
                return None
        finally:
            ren.cam = main_cam
            ren.show_bones = snap["show_bones"]
            ren.selected_node = snap["selected_node"]
            if hasattr(ren, "show_gimbal"):
                ren.show_gimbal = snap["show_gimbal"]
            if hasattr(ren, "show_walkmesh"):
                ren.show_walkmesh = snap["show_walkmesh"]
            ren.show_wireframe = snap["show_wireframe"]
            if hasattr(ren, "_anim_pose"):
                ren._anim_pose = snap["anim_pose"]
        if img is None:
            return None
        try:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            qimg = QtGui.QImage(
                img.tobytes("raw", "RGBA"),
                img.width,
                img.height,
                img.width * 4,
                QtGui.QImage.Format_RGBA8888,
            ).copy()
            return QtGui.QPixmap.fromImage(qimg)
        except Exception as exc:
            log.debug("Thumbnail QImage conversion failed: %s", exc)
            return None

    def set_selected_node(self, node, orbit_bounds=None) -> None:
        scene_root = self._scene_root_for_node(node)
        if scene_root is not None:
            node = scene_root
        if node is not None and self._renderer.is_hidden_bone_name(getattr(node, "name", "")):
            node = None
        if node is not None and bool(getattr(node, "is_camera", False)):
            camera = self.camera_manager.find_by_original(node)
            if camera is not None:
                self.camera_manager.select_camera(camera.id)
                self.cameraSelectionChanged.emit(node)
        elif hasattr(self, "camera_manager"):
            self.camera_manager.clear_camera_selection()
            self.cameraSelectionChanged.emit(None)
        if node is not None and self._is_selectable_mesh_node(node):
            self.set_selected_meshes([node], orbit_bounds=orbit_bounds)
            return
        self._clear_mesh_selection_flags()
        self._selected_meshes = []
        self._set_selection_orbit_bounds(node, orbit_bounds)
        self._renderer.selected_node = node
        if node is None:
            self._selected_joint_nodes = []
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
            self._transform_gizmo.clear_selection()
        elif self._is_selected_model_root(node):
            self._selected_joint_nodes = []
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
            self._sync_transform_reference_for_node(node)
            wp = self._gizmo_world_position(node)
            if wp is not None:
                setattr(node, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(node)
        elif not self._is_selected_model_root(node):
            known = {id(n) for n in self._selected_joint_nodes}
            if id(node) not in known:
                self._selected_joint_nodes = [node]
            if self._is_external_skeleton_node(node):
                self._renderer._ext_skel_selected_node = node
                self._renderer._ext_skel_selected_ids = {id(n) for n in self._selected_joint_nodes}
            else:
                self._renderer._ext_skel_selected_node = None
                self._renderer._ext_skel_selected_ids = set()
            self._sync_transform_reference_for_node(node)
            wp = self._gizmo_world_position(node)
            if wp is not None:
                setattr(node, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(node)
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(node)
        self.nodeSelected.emit(node)
        self.meshSelectionChanged.emit([])
        self._emit_mesh_subobject_selection()
        self._sync_transform_typein_bar()
        self._request_render()

    def get_selected_meshes(self) -> list:
        return [node for node in getattr(self, "_selected_meshes", []) if self._is_selectable_mesh_node(node)]

    def get_visible_meshes(self) -> list:
        try:
            return [node for node in self._renderer._iter_visible_mesh_nodes() if not getattr(node, "_gr_hidden", False)]
        except Exception:
            return []

    def _active_edit_mesh(self):
        active = getattr(self._renderer, "selected_node", None)
        if self._is_selectable_mesh_node(active):
            return active
        meshes = self.get_selected_meshes()
        return meshes[0] if meshes else None

    def _active_topology(self) -> MeshTopology | None:
        mesh = self._active_edit_mesh()
        if mesh is None:
            return None
        cached = self._mesh_topology_cache.get(id(mesh))
        if cached is None or cached.mesh is not mesh:
            cached = MeshTopology.build_from_mesh(mesh)
            self._mesh_topology_cache[id(mesh)] = cached
        return cached

    def _invalidate_mesh_topology(self, mesh=None) -> None:
        if mesh is None:
            self._mesh_topology_cache.clear()
        else:
            self._mesh_topology_cache.pop(id(mesh), None)
        self._renderer._wt_cache.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node_cache()

    def set_mesh_selection_mode(self, mode) -> None:
        try:
            mode = mode if isinstance(mode, MeshSelectionMode) else MeshSelectionMode(str(mode).lower())
        except Exception:
            return
        self.mesh_selection_state.set_mode(mode)
        if mode is MeshSelectionMode.OBJECT:
            self.mesh_selection_state.clear_subobject_selection()
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_select_all(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if state.mode is MeshSelectionMode.OBJECT:
            self.set_selected_meshes(self.get_visible_meshes())
            return
        if topology is None:
            return
        if state.mode is MeshSelectionMode.VERTEX:
            state.selected_vertices = set(range(len(topology.vertices)))
        elif state.mode is MeshSelectionMode.EDGE:
            state.selected_edges = set(topology.edges)
        elif state.mode is MeshSelectionMode.BORDER:
            state.selected_borders = set(range(len(topology.border_loops)))
        elif state.mode is MeshSelectionMode.FACE:
            state.selected_faces = set(range(len(topology.faces)))
        elif state.mode is MeshSelectionMode.POLYGON:
            state.selected_polygons = set(range(len(topology.faces)))
            state.status_message = "Polygon Mode is using individual faces for this triangulated mesh."
        elif state.mode is MeshSelectionMode.ELEMENT:
            state.selected_elements = set(range(len(topology.connected_elements)))
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_clear_selection(self) -> None:
        if self.mesh_selection_state.mode is MeshSelectionMode.OBJECT:
            self.set_selected_meshes([])
            return
        self.mesh_selection_state.clear_subobject_selection()
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_invert_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode is MeshSelectionMode.VERTEX:
            state.selected_vertices = set(range(len(topology.vertices))) - state.selected_vertices
        elif state.mode is MeshSelectionMode.EDGE:
            state.selected_edges = set(topology.edges) - state.selected_edges
        elif state.mode is MeshSelectionMode.BORDER:
            state.selected_borders = set(range(len(topology.border_loops))) - set(state.selected_borders)
        elif state.mode is MeshSelectionMode.FACE:
            state.selected_faces = set(range(len(topology.faces))) - state.selected_faces
        elif state.mode is MeshSelectionMode.POLYGON:
            state.selected_polygons = set(range(len(topology.faces))) - state.selected_polygons
        elif state.mode is MeshSelectionMode.ELEMENT:
            state.selected_elements = set(range(len(topology.connected_elements))) - state.selected_elements
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_grow_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
            selected = set(state.selected_faces or state.selected_polygons)
            for fi in list(selected):
                selected.update(topology.face_to_faces.get(fi, set()))
            if state.mode is MeshSelectionMode.FACE:
                state.selected_faces = selected
            else:
                state.selected_polygons = selected
        elif state.mode is MeshSelectionMode.VERTEX:
            for vi in list(state.selected_vertices):
                for edge in topology.vertex_to_edges.get(vi, set()):
                    state.selected_vertices.update(edge)
        elif state.mode is MeshSelectionMode.EDGE:
            for edge in list(state.selected_edges):
                for vi in edge:
                    state.selected_edges.update(topology.vertex_to_edges.get(vi, set()))
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_shrink_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
            selected = set(state.selected_faces or state.selected_polygons)
            keep = {fi for fi in selected if topology.face_to_faces.get(fi, set()).issubset(selected)}
            if state.mode is MeshSelectionMode.FACE:
                state.selected_faces = keep
            else:
                state.selected_polygons = keep
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_loop_selection(self) -> MeshOperationResult:
        topology = self._active_topology()
        state = self.mesh_selection_state
        if topology is None or not state.selected_edges:
            return MeshOperationResult.fail("Select an edge before Loop.")
        loop = topology.find_edge_loop(next(iter(state.selected_edges)))
        if not loop:
            return MeshOperationResult.fail("This topology does not support an edge loop from the selected edge.")
        state.selected_edges = set(loop)
        state.mode = MeshSelectionMode.EDGE
        self._emit_mesh_subobject_selection()
        self._request_render()
        return MeshOperationResult.ok("Selected edge loop.", selection_changed=True)

    def mesh_tool_ring_selection(self) -> MeshOperationResult:
        topology = self._active_topology()
        state = self.mesh_selection_state
        if topology is None or not state.selected_edges:
            return MeshOperationResult.fail("Select an edge before Ring.")
        ring = topology.find_edge_ring(next(iter(state.selected_edges)))
        if not ring:
            return MeshOperationResult.fail("This topology does not support an edge ring from the selected edge.")
        state.selected_edges = set(ring)
        state.mode = MeshSelectionMode.EDGE
        self._emit_mesh_subobject_selection()
        self._request_render()
        return MeshOperationResult.ok("Selected edge ring.", selection_changed=True)

    def mesh_tool_convert_selection(self, mode) -> MeshOperationResult:
        topology = self._active_topology()
        if topology is None:
            return MeshOperationResult.fail("No active mesh selected.")
        try:
            target = mode if isinstance(mode, MeshSelectionMode) else MeshSelectionMode(str(mode).lower())
        except Exception:
            return MeshOperationResult.fail("Unknown target selection mode.")
        result = convert_selection(self.mesh_selection_state, topology, target)
        self._emit_mesh_subobject_selection()
        self._request_render()
        return result

    def mesh_tool_operation(self, operation: str, options: dict | None = None) -> MeshOperationResult:
        options_obj = MeshOperationOptions(**(options or {}))
        op = str(operation or "").strip().lower()
        meshes = self.get_selected_meshes()
        mesh = self._active_edit_mesh()
        affected = list(meshes or ([mesh] if mesh is not None else []))
        before = self._mesh_history.snapshot(affected)
        result: MeshOperationResult
        new_node = None
        if op == "attach":
            result, new_node = attach_selected_meshes(meshes)
            if result.success and new_node is not None:
                self._replace_meshes_with_combined(meshes, new_node)
                self.set_selected_meshes([new_node])
                affected = [new_node]
        elif mesh is None:
            result = MeshOperationResult.fail("No active mesh selected.")
        elif op == "weld":
            result = weld_selected_vertices(mesh, self.mesh_selection_state, options_obj)
        elif op == "target_weld":
            if self.mesh_selection_state.mode is MeshSelectionMode.EDGE:
                selected_edges = sorted(self.mesh_selection_state.selected_edges)
                if len(selected_edges) == 2:
                    result = target_weld_edge(mesh, selected_edges[0], selected_edges[1], options_obj)
                else:
                    result = MeshOperationResult.fail("Target Edge Weld requires exactly two selected border edges.")
            else:
                selected = sorted(self.mesh_selection_state.selected_vertices)
                if self._mesh_target_weld_source is None and selected:
                    self._mesh_target_weld_source = selected[0]
                    result = MeshOperationResult.ok("Target Weld source vertex set. Pick the target vertex.")
                elif self._mesh_target_weld_source is not None and selected:
                    result = target_weld_vertex(mesh, self.mesh_selection_state, self._mesh_target_weld_source, selected[-1], options_obj)
                    self._mesh_target_weld_source = None
                else:
                    result = MeshOperationResult.fail("Select a source vertex, then a target vertex.")
        elif op == "bridge":
            result = bridge_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "connect":
            result = connect_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "cap":
            result = cap_selected_borders(mesh, self.mesh_selection_state, options_obj)
        elif op == "delete":
            result = delete_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "remove_isolated":
            result = remove_isolated_vertices(mesh)
        elif op == "flip_normals":
            result = flip_normals(mesh, self.mesh_selection_state)
        elif op == "recalculate_normals":
            result = recalculate_normals(mesh, self.mesh_selection_state)
        elif op == "detach":
            result, new_node = detach_selection(mesh, self.mesh_selection_state)
            if result.success and new_node is not None:
                self._append_mesh_node(new_node, parent=getattr(mesh, "parent", None))
                self.set_selected_meshes([new_node])
                affected = [mesh, new_node]
        else:
            result = MeshOperationResult.fail(f"Unsupported mesh operation: {operation}")
        if result.success and (result.topology_changed or op in {"attach", "detach"}):
            after = self._mesh_history.snapshot(affected)
            self._mesh_history.record(result.message, before, after)
            self._invalidate_mesh_topology()
            for node in affected:
                if hasattr(node, "compute_bounds"):
                    node.compute_bounds()
            self.meshVisibilityChanged.emit()
        self.mesh_selection_state.status_message = result.message if result.success else "; ".join(result.errors or [result.message])
        self._emit_mesh_subobject_selection()
        self._request_render()
        return result

    def _replace_meshes_with_combined(self, meshes: list, combined) -> None:
        parent = getattr(meshes[0], "parent", None) if meshes else getattr(self.model, "root_node", None)
        for node in meshes:
            setattr(node, "_gr_hidden", True)
            if getattr(node, "parent", None) is not None:
                try:
                    node.parent.children.remove(node)
                except ValueError:
                    pass
        self._append_mesh_node(combined, parent=parent)

    def _append_mesh_node(self, node, parent=None) -> None:
        if parent is None:
            parent = getattr(self.model, "root_node", None)
        if parent is not None:
            node.parent = parent
            if node not in parent.children:
                parent.children.append(node)

    def mesh_tool_undo(self) -> bool:
        ok = self._mesh_history.undo()
        if ok:
            self._invalidate_mesh_topology()
            self._emit_mesh_subobject_selection()
            self._request_render()
        return ok

    def mesh_tool_redo(self) -> bool:
        ok = self._mesh_history.redo()
        if ok:
            self._invalidate_mesh_topology()
            self._emit_mesh_subobject_selection()
            self._request_render()
        return ok

    def _emit_mesh_subobject_selection(self) -> None:
        state = self.mesh_selection_state
        active = self._active_edit_mesh()
        state.active_mesh_id = str(getattr(active, "name", "")) if active is not None else None
        state.selected_mesh_ids = {str(getattr(node, "name", id(node))) for node in self.get_selected_meshes()}
        self.meshSubobjectSelectionChanged.emit(state)

    def set_baked_lightmap_assignments(self, assignments: dict, *, preview: bool = True) -> None:
        model = self.model
        if model is None:
            return
        by_name = {str(name): str(path) for name, path in (assignments or {}).items() if path}
        nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        for node in nodes:
            name = str(getattr(node, "name", ""))
            if name not in by_name:
                continue
            if not hasattr(node, "_gr_original_lightmap_assignment"):
                setattr(node, "_gr_original_lightmap_assignment", getattr(node, "lightmap", ""))
                setattr(node, "_gr_original_has_lightmap", bool(getattr(node, "has_lightmap", False)))
            path = by_name[name]
            setattr(node, "_gr_baked_lightmap_path", path)
            setattr(node, "_gr_baked_lightmap_preview_path", path if preview else "")
            setattr(node, "_gr_baked_lightmap_preview_name", Path(path).stem.lower())
            if not preview:
                setattr(node, "lightmap", Path(path).stem.lower())
                setattr(node, "has_lightmap", True)
        setattr(model, "_gr_baked_lightmap_assignments", dict(by_name))
        setattr(model, "_gr_baked_lightmap_preview_enabled", bool(preview))
        self._renderer.textures.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        self._request_render()

    def revert_baked_lightmaps(self) -> None:
        model = self.model
        if model is None:
            return
        nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        for node in nodes:
            if hasattr(node, "_gr_original_lightmap_assignment"):
                setattr(node, "lightmap", getattr(node, "_gr_original_lightmap_assignment", ""))
                setattr(node, "has_lightmap", bool(getattr(node, "_gr_original_has_lightmap", False)))
            for attr in ("_gr_baked_lightmap_preview_path", "_gr_baked_lightmap_preview_name"):
                if hasattr(node, attr):
                    delattr(node, attr)
        setattr(model, "_gr_baked_lightmap_preview_enabled", False)
        self._renderer.textures.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        self._request_render()

    def get_baked_lightmap_assignments(self) -> dict:
        model = self.model
        return dict(getattr(model, "_gr_baked_lightmap_assignments", {}) or {}) if model is not None else {}

    def _clear_mesh_selection_flags(self) -> None:
        for node in self._selected_meshes:
            try:
                setattr(node, "_gr_selected", False)
            except Exception:
                pass

    @staticmethod
    def _is_selectable_mesh_node(node) -> bool:
        verts = getattr(node, "vertices", getattr(node, "verts", [])) or []
        faces = getattr(node, "faces", []) or []
        return bool(verts and faces)

    def set_selected_meshes(self, nodes: list, orbit_bounds=None) -> None:
        clean_nodes = []
        seen = set()
        for node in nodes or []:
            if node is None or not self._is_selectable_mesh_node(node):
                continue
            if getattr(node, "_gr_hidden", False):
                continue
            node_id = id(node)
            if node_id in seen:
                continue
            seen.add(node_id)
            clean_nodes.append(node)
        self._clear_mesh_selection_flags()
        self._selected_meshes = clean_nodes
        for node in clean_nodes:
            setattr(node, "_gr_selected", True)
        active = clean_nodes[0] if clean_nodes else None
        self._set_selection_orbit_bounds(active, orbit_bounds if len(clean_nodes) == 1 else None)
        self._renderer.selected_node = active
        if active is None:
            self._transform_gizmo.clear_selection()
        else:
            self._sync_transform_reference_for_node(active)
            wp = self._gizmo_world_position(active)
            if wp is not None:
                setattr(active, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(active)
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(active)
        self.nodeSelected.emit(active)
        self.meshSelectionChanged.emit(list(clean_nodes))
        self._emit_mesh_subobject_selection()
        self._sync_transform_typein_bar()
        self._request_render()

    def _set_selection_orbit_bounds(self, node, bounds) -> None:
        if node is None or bounds is None:
            self._selection_orbit_bounds = None
            self._selection_orbit_bounds_node_id = 0
            return
        try:
            bb_min = tuple(float(v) for v in bounds[0][:3])
            bb_max = tuple(float(v) for v in bounds[1][:3])
            self._selection_orbit_bounds = (bb_min, bb_max)
            self._selection_orbit_bounds_node_id = id(node)
        except Exception:
            self._selection_orbit_bounds = None
            self._selection_orbit_bounds_node_id = 0

    @staticmethod
    def _bounds_from_points(points, min_extent: float = 0.0):
        valid = []
        for point in points or []:
            try:
                x, y, z = float(point[0]), float(point[1]), float(point[2])
            except Exception:
                continue
            if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                valid.append((x, y, z))
        if not valid:
            return None
        mins = [min(point[i] for point in valid) for i in range(3)]
        maxs = [max(point[i] for point in valid) for i in range(3)]
        if min_extent > 0.0:
            half = float(min_extent) * 0.5
            for axis in range(3):
                if abs(maxs[axis] - mins[axis]) < min_extent:
                    center = (mins[axis] + maxs[axis]) * 0.5
                    mins[axis] = center - half
                    maxs[axis] = center + half
        return tuple(mins), tuple(maxs)

    @staticmethod
    def _bounds_center(bounds) -> tuple[float, float, float]:
        return (
            (float(bounds[0][0]) + float(bounds[1][0])) * 0.5,
            (float(bounds[0][1]) + float(bounds[1][1])) * 0.5,
            (float(bounds[0][2]) + float(bounds[1][2])) * 0.5,
        )

    def _selection_navigation_bounds(self):
        active = getattr(self._renderer, "selected_node", None)
        selected_meshes = [node for node in self._selected_meshes if self._is_selectable_mesh_node(node)]
        if (
            active is not None
            and self._selection_orbit_bounds is not None
            and self._selection_orbit_bounds_node_id == id(active)
            and len(selected_meshes) <= 1
        ):
            return self._selection_orbit_bounds
        if selected_meshes:
            points = []
            for node in selected_meshes:
                try:
                    points.extend(self._renderer._get_world_verts_for_node(node))
                except Exception:
                    continue
            return self._bounds_from_points(points, min_extent=0.05)
        if active is not None:
            if self._is_selectable_mesh_node(active):
                try:
                    return self._bounds_from_points(
                        self._renderer._get_world_verts_for_node(active),
                        min_extent=0.05,
                    )
                except Exception:
                    pass
            try:
                wp, _wo, _is_id = self._renderer._node_world_transform(active)
            except Exception:
                wp = getattr(active, "position", (0.0, 0.0, 0.0))
            return self._bounds_from_points([wp], min_extent=0.35)
        return None

    def _focus_camera_on_selection(self) -> bool:
        bounds = self._selection_navigation_bounds()
        if bounds is None:
            return False
        pivot = self._bounds_center(bounds)
        self._set_camera_target_preserving_eye(pivot)
        return True

    def _set_camera_target_preserving_eye(self, target) -> None:
        try:
            eye = self.camera.eye()
            tx, ty, tz = float(target[0]), float(target[1]), float(target[2])
            vx, vy, vz = eye[0] - tx, eye[1] - ty, eye[2] - tz
            dist = math.sqrt(vx * vx + vy * vy + vz * vz)
            if not math.isfinite(dist) or dist < 0.05:
                self.camera.target = [tx, ty, tz]
                return
            self.camera.target = [tx, ty, tz]
            self.camera.distance = max(0.05, dist)
            self.camera.azimuth = math.degrees(math.atan2(vy, vx)) % 360.0
            self.camera.elevation = max(-85.0, min(85.0, math.degrees(math.asin(max(-1.0, min(1.0, vz / dist))))))
        except Exception:
            try:
                self.camera.target = [float(target[0]), float(target[1]), float(target[2])]
            except Exception:
                pass

    def select_all_meshes(self) -> None:
        if self.model is None:
            self.set_selected_meshes([])
            return
        try:
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = self._all_geometry_nodes()
        self.set_selected_meshes([node for node in nodes if not getattr(node, "_gr_hidden", False)])

    def _all_geometry_nodes(self) -> list:
        if self.model is None:
            return []
        sources = []
        if hasattr(self.model, "mesh_nodes"):
            sources.append(self.model.mesh_nodes() or [])
        if hasattr(self.model, "all_nodes"):
            sources.append(self.model.all_nodes() or [])
        sources.append(getattr(self.model, "_gr_extra_module_mesh_nodes", []) or [])
        result = []
        seen = set()
        for source in sources:
            for node in source:
                if node is None or id(node) in seen:
                    continue
                if not self._is_selectable_mesh_node(node):
                    continue
                seen.add(id(node))
                result.append(node)
        return result

    def refresh_view(self) -> None:
        self._renderer._wt_cache.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node_cache()
        self._request_render()

    def _set_selected_joint_nodes(self, nodes: list, *, primary=None) -> None:
        """Replace the current bone selection with an ordered de-duplicated list."""
        seen = set()
        selected = []
        for node in nodes or []:
            if node is None:
                continue
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            selected.append(node)
        self._selected_joint_nodes = selected
        self._renderer.selected_node = primary if primary is not None else (selected[-1] if selected else None)
        if self._selection_targets_external_skeleton(selected or [self._renderer.selected_node]):
            self._renderer._ext_skel_selected_node = self._renderer.selected_node
            self._renderer._ext_skel_selected_ids = {id(n) for n in selected}
        else:
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self.nodeSelected.emit(self._renderer.selected_node)
        self._request_render()

    def _toggle_selected_joint_node(self, node) -> None:
        if node is None:
            return
        selected = list(self._selected_joint_nodes)
        for i, existing in enumerate(selected):
            if existing is node:
                selected.pop(i)
                self._set_selected_joint_nodes(selected)
                return
        selected.append(node)
        self._set_selected_joint_nodes(selected, primary=node)

    def _joint_nodes_in_rect(self, x0: int, y0: int, x1: int, y1: int) -> list:
        positions = self._joint_hit_positions()
        if not positions:
            return []
        lx, hx = sorted((int(x0), int(x1)))
        ly, hy = sorted((int(y0), int(y1)))
        nodes = []
        seen = set()
        for entry in positions:
            if not entry or len(entry) < 4:
                continue
            sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
            if sx is None or sy is None or node is None:
                continue
            if lx <= sx <= hx and ly <= sy <= hy and id(node) not in seen:
                seen.add(id(node))
                nodes.append(node)
        return nodes

    def _external_skeleton_node_ids(self) -> set[int]:
        skel = getattr(self._renderer, "_ext_skeleton", None)
        if skel is None:
            return set()
        try:
            return {id(node) for node in skel.all_nodes()}
        except Exception:
            return set()

    def _is_external_skeleton_node(self, node) -> bool:
        return node is not None and id(node) in self._external_skeleton_node_ids()

    def _selection_targets_external_skeleton(self, nodes: list) -> bool:
        ext_ids = self._external_skeleton_node_ids()
        if not ext_ids:
            return False
        return any(node is not None and id(node) in ext_ids for node in nodes or [])

    def _joint_hit_positions(self) -> list:
        ext_positions = list(getattr(self._renderer, "_ext_bone_screen_positions", None) or [])
        bone_positions = list(getattr(self._renderer, "_bone_screen_positions", None) or [])
        return ext_positions + bone_positions

    def _external_overlay_world_position(self, node) -> tuple[float, float, float]:
        ox, oy, oz = getattr(self._renderer, "_ext_skel_offset", [0.0, 0.0, 0.0])
        scale = float(getattr(self._renderer, "_ext_skel_scale", 1.0) or 1.0)
        p = node.bone_world_position()
        return (p[0] * scale + ox, p[1] * scale + oy, p[2] * scale + oz)

    def _external_world_delta_to_local(self, delta: tuple[float, float, float]) -> tuple[float, float, float]:
        scale = max(1e-6, float(getattr(self._renderer, "_ext_skel_scale", 1.0) or 1.0))
        return (delta[0] / scale, delta[1] / scale, delta[2] / scale)

    def _all_model_nodes(self, model) -> list:
        if model is None:
            return []
        try:
            return list(model.all_nodes())
        except Exception:
            root = getattr(model, "root_node", None)
            if root is None:
                return []
            nodes = []
            stack = [root]
            seen = set()
            while stack:
                node = stack.pop()
                if id(node) in seen:
                    continue
                seen.add(id(node))
                nodes.append(node)
                stack.extend(getattr(node, "children", []) or [])
            return nodes

    def _node_overlay_world_position(self, node) -> tuple[float, float, float]:
        if self._is_external_skeleton_node(node):
            return self._external_overlay_world_position(node)
        try:
            return tuple(float(v) for v in node.bone_world_position())
        except Exception:
            try:
                wp, _wo, _ = self._renderer._node_world_transform(node)
                return tuple(float(v) for v in wp)
            except Exception:
                return tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0)))

    def _move_external_node_to_overlay_world(self, node, target_world: tuple[float, float, float]) -> bool:
        if node is None or not self._is_external_skeleton_node(node):
            return False
        current_world = self._external_overlay_world_position(node)
        delta_world = (
            float(target_world[0]) - current_world[0],
            float(target_world[1]) - current_world[1],
            float(target_world[2]) - current_world[2],
        )
        delta_local = self._external_world_delta_to_local(delta_world)
        try:
            pos = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0)))
            node.position = (
                pos[0] + delta_local[0],
                pos[1] + delta_local[1],
                pos[2] + delta_local[2],
            )
            self._evict_transform_cache(node)
            return True
        except Exception:
            return False

    def _nearest_imported_bone_at(self, sx: int, sy: int, radius: int = 18):
        if self.model is None:
            return None
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        best_node = None
        best_d2 = radius * radius
        for node in self._all_model_nodes(self.model):
            if getattr(node, "is_mesh", False) or getattr(node, "is_skin", False):
                continue
            name = getattr(node, "name", "") or ""
            if not name:
                continue
            try:
                wp = self._node_overlay_world_position(node)
                sp = self._renderer._proj(wp[0], wp[1], wp[2], w, h)
            except Exception:
                sp = None
            if sp is None:
                continue
            d2 = (float(sp[0]) - float(sx)) ** 2 + (float(sp[1]) - float(sy)) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_node = node
        return best_node

    def _snap_selected_external_bones_to_imported_at_cursor(self, sx: int, sy: int) -> bool:
        target = self._nearest_imported_bone_at(sx, sy)
        if target is None:
            return False
        selected = [
            node for node in (self._selected_joint_nodes or [self._renderer.selected_node])
            if self._is_external_skeleton_node(node)
        ]
        if not selected:
            return False
        target_world = self._node_overlay_world_position(target)
        moved = False
        for node in selected:
            moved = self._move_external_node_to_overlay_world(node, target_world) or moved
        if moved:
            self._request_render(fast=True)
        return moved

    @staticmethod
    def _gimbal_world_axis(axis_name: str) -> tuple[float, float, float]:
        return {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0)}.get(
            axis_name,
            (0.0, 0.0, 1.0),
        )

    def _projected_axis_delta(
        self,
        axis_name: str,
        origin_world: tuple[float, float, float],
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
    ) -> tuple[float, float, float]:
        """Return a world delta that follows the visible gimbal axis on screen."""
        w_dir = self._gimbal_world_axis(axis_name)
        arm = max(float(world_per_px) * 120.0, 0.01)
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        try:
            start_sp = self._renderer._proj(
                origin_world[0],
                origin_world[1],
                origin_world[2],
                w,
                h,
            )
            end_sp = self._renderer._proj(
                origin_world[0] + w_dir[0] * arm,
                origin_world[1] + w_dir[1] * arm,
                origin_world[2] + w_dir[2] * arm,
                w,
                h,
            )
        except Exception:
            start_sp = end_sp = None
        if start_sp is not None and end_sp is not None:
            sx = float(end_sp[0]) - float(start_sp[0])
            sy = float(end_sp[1]) - float(start_sp[1])
            length = math.sqrt(sx * sx + sy * sy)
            if length >= 1e-6:
                pixels_along = (float(dx_screen) * sx + float(dy_screen) * sy) / length
                delta = (pixels_along / length) * arm
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

        right, up, _fwd, _eye = self.camera._view_matrix()
        sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
        sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
        ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
        if ll < 1e-6:
            return (0.0, 0.0, 0.0)
        delta = ((float(dx_screen) * sc_x + (-float(dy_screen)) * sc_y) / ll) * world_per_px
        return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

    def refresh_node_transform(self, node=None) -> None:
        if node is not None:
            before = getattr(node, "_gr_undo_before_transform", None)
            if before is not None:
                try:
                    self._commit_node_transform(
                        node,
                        before[0],
                        before[1],
                        tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                        tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
                        "Set Position",
                    )
                finally:
                    try:
                        delattr(node, "_gr_undo_before_transform")
                    except Exception:
                        pass
            self._evict_transform_cache(node)
        else:
            self._renderer._wt_cache.clear()
        self._request_render()

    def _clear_edit_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @staticmethod
    def _state_changed(before_pos, before_rot, after_pos, after_rot, before_vertices=None, after_vertices=None) -> bool:
        values = tuple(before_pos) + tuple(before_rot) + tuple(after_pos) + tuple(after_rot)
        if any(not math.isfinite(float(v)) for v in values):
            return False
        if before_vertices is not None or after_vertices is not None:
            if before_vertices != after_vertices:
                return True
        return (
            any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_pos, after_pos))
            or any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_rot, after_rot))
        )

    def _commit_node_transform(
        self,
        node,
        before_pos,
        before_rot,
        after_pos,
        after_rot,
        label: str,
        *,
        before_vertices=None,
        after_vertices=None,
        before_scale=None,
        after_scale=None,
        before_pivot_world=None,
        after_pivot_world=None,
        before_pivot_rotation=None,
        after_pivot_rotation=None,
    ) -> None:
        scale_changed = before_scale is not None and after_scale is not None and tuple(before_scale) != tuple(after_scale)
        pivot_changed = (
            (before_pivot_world is not None and after_pivot_world is not None and tuple(before_pivot_world) != tuple(after_pivot_world))
            or (
                before_pivot_rotation is not None
                and after_pivot_rotation is not None
                and tuple(before_pivot_rotation) != tuple(after_pivot_rotation)
            )
        )
        if node is None or (
            not scale_changed
            and not pivot_changed
            and not self._state_changed(before_pos, before_rot, after_pos, after_rot, before_vertices, after_vertices)
        ):
            return
        self._undo_stack.append(
            {
                "node": node,
                "before_pos": tuple(before_pos),
                "before_rot": tuple(before_rot),
                "after_pos": tuple(after_pos),
                "after_rot": tuple(after_rot),
                "before_vertices": before_vertices,
                "after_vertices": after_vertices,
                "before_scale": before_scale,
                "after_scale": after_scale,
                "before_pivot_world": before_pivot_world,
                "after_pivot_world": after_pivot_world,
                "before_pivot_rotation": before_pivot_rotation,
                "after_pivot_rotation": after_pivot_rotation,
                "label": label,
            }
        )
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _apply_transform_action(self, action: dict, use_after: bool) -> None:
        node = action.get("node")
        if node is None:
            return
        node.position = action["after_pos"] if use_after else action["before_pos"]
        node.rotation = action["after_rot"] if use_after else action["before_rot"]
        vertices = action.get("after_vertices") if use_after else action.get("before_vertices")
        scale = action.get("after_scale") if use_after else action.get("before_scale")
        pivot_world = action.get("after_pivot_world") if use_after else action.get("before_pivot_world")
        pivot_rotation = action.get("after_pivot_rotation") if use_after else action.get("before_pivot_rotation")
        if scale is not None:
            node._gr_scale = tuple(scale)
        if pivot_world is not None:
            node._gr_pivot_world = tuple(pivot_world)
            node._gr_gizmo_world_position = tuple(pivot_world)
            node._gr_pivot_world_dirty = True
        if pivot_rotation is not None:
            node._gr_pivot_rotation = tuple(pivot_rotation)
        if vertices is not None:
            node.vertices = [tuple(v) for v in vertices]
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render()

    def undo(self) -> bool:
        if getattr(self, "mesh_selection_state", None) is not None and self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self.mesh_tool_undo():
                return True
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        self._apply_transform_action(action, use_after=False)
        self._redo_stack.append(action)
        return True

    def redo(self) -> bool:
        if getattr(self, "mesh_selection_state", None) is not None and self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self.mesh_tool_redo():
                return True
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._apply_transform_action(action, use_after=True)
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        return True

    def _notify_node_moved(self, node) -> None:
        if bool(getattr(node, "is_camera", False)):
            camera = self.camera_manager.find_by_original(node)
            if camera is not None:
                camera.position = tuple(float(v) for v in getattr(node, "position", camera.position)[:3])
                camera.rotation = tuple(float(v) for v in getattr(node, "rotation", camera.rotation)[:4])
                camera.metadata["helper_size"] = float(getattr(node, "_gr_helper_size", camera.metadata.get("helper_size", 1.0)) or 1.0)
                camera.apply_to_original()
                self.camera_manager._store_on_model()
                if self.camera_manager.active_camera_id == camera.id:
                    self.update_view_from_camera(camera)
                self.cameraChanged.emit()
        if self.on_node_moved:
            self.on_node_moved(node)
        self.nodeMoved.emit(node)
        if node is getattr(self._renderer, "selected_node", None):
            self._transform_gizmo.update_from_object_transform()
        self._sync_transform_typein_bar()
        if self._renderer.rig_edit_mode and self._renderer.on_bone_moved:
            try:
                self._renderer.on_bone_moved(node.name, node.position)
            except Exception:
                pass

    def set_anim_base_pose(self, base_pose) -> None:
        self._renderer.set_anim_base_pose(base_pose)

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        self._fast_frame_until = max(self._fast_frame_until, time_module.perf_counter() + 0.12)
        self._request_render(fast=True)

    def clear_animation_pose(self) -> None:
        self._renderer.set_animation_pose(None)
        self._fast_frame_until = 0.0
        self._request_render()

    def load_walkmesh(self, wok_data_or_path, world_offset=(0.0, 0.0, 0.0)) -> None:
        self._renderer.load_walkmesh(wok_data_or_path, world_offset)
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def clear_walkmesh(self) -> None:
        self._renderer.clear_walkmesh()
        self.walkmesh_button.setChecked(False)
        self._request_render()

    def open_uv_viewer(self) -> None:
        if self._uv_viewer is None:
            self._uv_viewer = QtUVViewerWindow(self.window())
            self._uv_viewer.destroyed.connect(lambda *_: setattr(self, "_uv_viewer", None))
            self._uv_viewer._tex_cache = self._renderer.tex_cache
            self._update_uv_viewer_model()
            if self._renderer.selected_node:
                self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self._uv_viewer.show()
        self._uv_viewer.raise_()
        self._uv_viewer.activateWindow()

    def _cycle_navigation_profile(self) -> None:
        order = ["3dsmax", "blender", "maya"]
        try:
            index = order.index(self._navigation_profile)
        except ValueError:
            index = -1
        self.set_navigation_profile(order[(index + 1) % len(order)])

    def _is_viewport_event_source(self, obj) -> bool:
        return obj is self.canvas or obj is self.canvas.current_surface()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if self._is_viewport_event_source(obj):
            et = event.type()
            if et == QtCore.QEvent.Resize:
                size = (event.size().width(), event.size().height())
                if size != self._last_canvas_size:
                    self._last_canvas_size = size
                    self._request_render()
                # Keep the ViewCube pinned to the viewport overlay corner.
                self._reposition_viewcube()
                # Keep the mini-thumbnail nearby without covering the cube.
                self._reposition_thumbnail()
                return False
            if et == QtCore.QEvent.FocusOut:
                self._snap_key_down = False
                return False
            if et == QtCore.QEvent.Leave:
                if self._hovered_mesh_node is not None:
                    self._hovered_mesh_node = None
                    self._hovered_mesh_face_bounds = None
                    self._request_render(fast=True)
                return False
            if et == QtCore.QEvent.MouseButtonPress:
                self.canvas.setFocus()
                action = self._navigation_action(event.button(), event.modifiers())
                if action:
                    self._press_navigation(event, action)
                    return True
                if event.button() == QtCore.Qt.RightButton:
                    self._show_mesh_context_menu(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    if self._measurement_mode:
                        self._handle_measurement_click(event)
                        return True
                    self._press_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseMove:
                if self._nav_dragging:
                    self._drag_navigation(event)
                    return True
                if self._measurement_mode and not (event.buttons() & QtCore.Qt.LeftButton):
                    self._handle_measurement_preview(event)
                    return True
                if event.buttons() & QtCore.Qt.LeftButton:
                    self._drag_lmb(event)
                    return True
                self._update_gizmo_hover(event)
                self._update_mesh_hover(event)
                return False
            if et == QtCore.QEvent.MouseButtonRelease:
                if self._nav_dragging and event.button() == self._nav_button:
                    self._release_navigation(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._release_lmb(event)
                    return True
            if et in (QtCore.QEvent.FocusOut, QtCore.QEvent.WindowDeactivate):
                if self._transform_gizmo_dragging:
                    self._cancel_transform_gizmo_drag()
                    return True
            if et == QtCore.QEvent.Wheel:
                if self.is_camera_view_active() and not self._lock_view_to_camera:
                    return True
                steps = event.angleDelta().y() / 120.0
                self.camera.zoom(steps)
                if self.is_camera_view_active() and self._lock_view_to_camera:
                    self.update_camera_from_view()
                self._renderer.is_interactive = False
                self._request_render()
                return True
            if et == QtCore.QEvent.KeyPress:
                key = event.key()
                if key == QtCore.Qt.Key_V and not event.isAutoRepeat():
                    self._snap_key_down = True
                    return True
                modifiers = event.modifiers()
                no_modifiers = not (
                    modifiers
                    & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
                )
                if key == QtCore.Qt.Key_F and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_Home and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_Z and no_modifiers:
                    self.frame_selection_or_all(); return True
                if self._active_gizmo_node() is not None:
                    if key == QtCore.Qt.Key_W and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.TRANSLATE); return True
                    if key == QtCore.Qt.Key_E and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.ROTATE); return True
                    if key == QtCore.Qt.Key_R and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.SCALE); return True
                if key == QtCore.Qt.Key_R and no_modifiers:
                    self.reset_camera(); return True
                if key == QtCore.Qt.Key_W and no_modifiers:
                    self.wire_button.click(); return True
                if key == QtCore.Qt.Key_B and no_modifiers:
                    self.bones_button.click(); return True
                if key == QtCore.Qt.Key_T and no_modifiers:
                    self.texture_button.click(); return True
                if key == QtCore.Qt.Key_G and no_modifiers:
                    self.gimbal_button.click(); return True
                if key == QtCore.Qt.Key_G and (event.modifiers() & QtCore.Qt.AltModifier):
                    self.grid_button.click(); return True
                if key == QtCore.Qt.Key_S and no_modifiers:
                    self.snap_button.click(); return True
                if key == QtCore.Qt.Key_A and no_modifiers and self._navigation_profile != "maya":
                    self.angle_snap_button.click(); return True
                if key == QtCore.Qt.Key_P and no_modifiers:
                    self.percent_snap_button.click(); return True
                if key == QtCore.Qt.Key_Tab and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Space and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Escape and no_modifiers:
                    if self._pick_reference_waiting:
                        self._pick_reference_waiting = False
                        self.transform_reference_controller.clear_pick_reference()
                        self.statusMessage.emit("Pick reference cancelled.")
                        self._request_render(fast=True)
                        return True
                    if self._transform_gizmo_dragging:
                        self._cancel_transform_gizmo_drag()
                        return True
                    if self._measurement_mode:
                        self.measurement_controller.clear_measurement()
                        self.measure_button.setChecked(False)
                        self._measurement_mode = False
                        self._request_render()
                        return True
                if key == QtCore.Qt.Key_Z and (event.modifiers() & QtCore.Qt.ControlModifier):
                    if event.modifiers() & QtCore.Qt.ShiftModifier:
                        self.redo()
                    else:
                        self.undo()
                    return True
                if key == QtCore.Qt.Key_Y and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.redo()
                    return True
                if key == QtCore.Qt.Key_A and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.select_all_meshes()
                    return True
                if key == QtCore.Qt.Key_X and (event.modifiers() & QtCore.Qt.AltModifier):
                    return True
                if self._handle_view_key(event):
                    return True
            if et == QtCore.QEvent.KeyRelease:
                if event.key() == QtCore.Qt.Key_V and not event.isAutoRepeat():
                    self._snap_key_down = False
                    return True
        return super().eventFilter(obj, event)

    def _world_point_from_mouse(self, event) -> tuple[float, float, float]:
        x = int(event.position().x())
        y = int(event.position().y())
        origin, direction = ray_from_mouse((x, y), self.camera, self.canvas.width(), self.canvas.height())
        dz = float(direction[2])
        if abs(dz) > 1e-8:
            t = -float(origin[2]) / dz
            if t > 0.0:
                point = origin + direction * t
                return (float(point[0]), float(point[1]), 0.0)
        try:
            target = getattr(self.camera, "target", (0.0, 0.0, 0.0))
            return (float(target[0]), float(target[1]), float(target[2]))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _handle_measurement_click(self, event) -> None:
        world = self._world_point_from_mouse(event)
        if self.measurement_controller.point_a is None or self.measurement_controller.point_b is not None:
            self.measurement_controller.begin_measurement(world)
        else:
            self.measurement_controller.finish_measurement(world)
        self._request_render(fast=True)

    def _handle_measurement_preview(self, event) -> None:
        if self.measurement_controller.point_a is None or self.measurement_controller.point_b is not None:
            return
        self.measurement_controller.update_preview(self._world_point_from_mouse(event))
        self._request_render(fast=True)

    def _navigation_action(self, button, modifiers) -> str:
        if self.is_camera_view_active() and not self._lock_view_to_camera:
            return ""
        alt = has_modifier(modifiers, QtCore.Qt.AltModifier)
        shift = has_modifier(modifiers, QtCore.Qt.ShiftModifier)
        ctrl = has_modifier(modifiers, QtCore.Qt.ControlModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if button == QtCore.Qt.MiddleButton and alt:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton and alt:
                return "zoom"
            return ""
        if profile == "blender":
            if button == QtCore.Qt.MiddleButton and shift:
                return "pan"
            if button == QtCore.Qt.MiddleButton and ctrl:
                return "zoom"
            if button == QtCore.Qt.MiddleButton:
                return "orbit"
            return ""
        if profile == "maya":
            if not alt:
                return ""
            if button == QtCore.Qt.LeftButton:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton:
                return "zoom"
        return ""

    def _press_navigation(self, event, action: str) -> None:
        self._nav_dragging = action
        self._nav_button = event.button()
        self._mx = int(event.position().x())
        self._my = int(event.position().y())
        self._renderer._hovered_bone = None

    def _drag_navigation(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        if self._nav_dragging == "orbit":
            self.camera.orbit(dx * 0.4, -dy * 0.4)
        elif self._nav_dragging == "pan":
            self.camera.pan(dx, dy, self.canvas.height())
        elif self._nav_dragging == "zoom":
            self.camera.zoom((-dy + dx) / 120.0)
        if self.is_camera_view_active() and self._lock_view_to_camera:
            self.update_camera_from_view()
        self._renderer.is_interactive = self._fast_drag_enabled
        self._request_render(fast=True)

    def _release_navigation(self, _event) -> None:
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._renderer.is_interactive = False
        self._fast_frame_until = 0.0
        self._request_render()

    def _handle_view_key(self, event) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if ctrl or alt:
                return False
            if key == QtCore.Qt.Key_F and shift:
                self._set_camera_view("front")
            elif key == QtCore.Qt.Key_T and shift:
                self._set_camera_view("top")
            elif key == QtCore.Qt.Key_L and shift:
                self._set_camera_view("left")
            elif key == QtCore.Qt.Key_P and shift:
                self.reset_camera()
            elif key == QtCore.Qt.Key_Z and not shift:
                self.frame_selection_or_all()
            else:
                return False
            return True
        if profile == "blender":
            if alt or shift:
                return False
            if key == QtCore.Qt.Key_1:
                self._set_camera_view("back" if ctrl else "front")
            elif key == QtCore.Qt.Key_3:
                self._set_camera_view("left" if ctrl else "right")
            elif key == QtCore.Qt.Key_7:
                self._set_camera_view("bottom" if ctrl else "top")
            elif key == QtCore.Qt.Key_Home:
                self.frame_all()
            else:
                return False
            return True
        if profile == "maya":
            if ctrl or alt or shift:
                return False
            if key in (QtCore.Qt.Key_A, QtCore.Qt.Key_F):
                self.frame_all()
                return True
            return False
        return False

    def _set_camera_view(self, view: str) -> None:
        # T404: delegate to the smooth-interpolation path so keyboard
        # shortcuts (Shift+F / T / L / 1 / 3 / 7) feel consistent with
        # the new snap-view button cluster.
        self._snap_to_view(view)

    # ── T406: Per-mode camera presets ──────────────────────────────────
    def set_character_mode(self, mode: object) -> None:
        """React to a Character-Mode change by reframing the camera.

        Mode-specific presets:
          • Head           → auto-frame the ``head_g`` subtree (with
                             20% padding) and force-hide the thumbnail
                             (Head close-up).
          • Creature       → frame the full model bbox.
          • Headless Body  → frame the full body + bias the camera
                             toward the upper torso (canonical front).
          • Supermodel     → same as Headless Body (skeletons only).
          • Ambiguous /
            Unsupported   → leave the camera alone.

        ``_mode_user_camera_dirty`` tracks whether the user has touched
        the camera since the last preset was applied; the preset only
        runs on a *change* of mode so subsequent renders never clobber
        the user's framing.
        """
        # Accept either the enum or its string value.
        key = getattr(mode, "value", mode)
        key = str(key).lower() if key is not None else None
        if key == self._character_mode:
            return
        self._character_mode = key
        self._mode_user_camera_dirty = False
        self._apply_mode_camera_preset(key)

    @property
    def character_mode(self) -> Optional[str]:
        return self._character_mode

    def _apply_mode_camera_preset(self, key: Optional[str]) -> None:
        """Apply the camera-framing preset for the active mode."""
        if not self.model or not getattr(self.model, "root_node", None):
            return
        if key == "head":
            framed = self._frame_head_subtree(padding=0.20)
            # Auto-hide the mini-thumbnail in Head close-up.
            self.set_thumbnail_force_hidden(True)
            if not framed:
                # Fallback to full-bbox framing if no head subtree exists.
                self.frame_all()
            return
        # Non-Head modes always show the thumbnail (mode-driven hide-flag off).
        self.set_thumbnail_force_hidden(False)
        if key == "creature":
            # Full bbox; no special biasing for quadrupeds since the
            # bbox is asymmetric and `frame_all` already accounts for it.
            self.frame_all()
            return
        if key in ("headless_body", "humanoid", "supermodel"):
            # Body modes default to the canonical front view + frame-all
            # so the silhouette reads clearly.  The dual front+back
            # framing the spec mentions is satisfied implicitly: front
            # is the default, and the user can flick to back via the
            # T404 snap-view cluster.
            self.camera.azimuth = self.camera.DEFAULT_AZIMUTH
            self.camera.elevation = self.camera.DEFAULT_ELEVATION
            self.frame_all()
            return
        # Ambiguous / Unsupported / None → no preset.

    def _frame_head_subtree(self, padding: float = 0.20) -> bool:
        """Frame the camera tightly on the ``head_g`` subtree bbox.

        Walks downward from any node whose name contains ``head_g``
        (case-insensitive) and computes the world-space bbox of every
        vertex it owns or any descendant owns.  Returns True if a head
        subtree was found and the camera was reframed, False otherwise.
        """
        if not self.model or not getattr(self.model, "root_node", None):
            return False
        # Locate the head subtree root.  Walk the full node tree to
        # find any node whose lowercased name contains "head_g" — this
        # catches ``head_g``, ``HEAD_G``, ``f_head_g`` etc.
        head_root = None
        visited = set()
        stack = [self.model.root_node]
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            nlow = (getattr(node, "name", "") or "").lower()
            if "head_g" in nlow or nlow == "head":
                head_root = node
                break
            stack.extend(getattr(node, "children", []) or [])
        if head_root is None:
            return False
        # Walk the head subtree and accumulate the world bbox of all verts.
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        sub_visited = set()
        sub_stack = [head_root]
        while sub_stack:
            node = sub_stack.pop()
            sid = id(node)
            if sid in sub_visited:
                continue
            sub_visited.add(sid)
            sub_stack.extend(getattr(node, "children", []) or [])
            verts = getattr(node, "vertices", None) or []
            if not verts:
                continue
            try:
                wp, _, _ = self._renderer._node_world_transform(node)
            except Exception:
                wp = node.world_position() if hasattr(node, "world_position") else (0.0, 0.0, 0.0)
            for vx, vy, vz in verts:
                x, y, z = vx + wp[0], vy + wp[1], vz + wp[2]
                if x < mins[0]: mins[0] = x
                if y < mins[1]: mins[1] = y
                if z < mins[2]: mins[2] = z
                if x > maxs[0]: maxs[0] = x
                if y > maxs[1]: maxs[1] = y
                if z > maxs[2]: maxs[2] = z
                has_data = True
        if not has_data:
            # Fall back to the node's own world position if it has no verts.
            try:
                wp, _, _ = self._renderer._node_world_transform(head_root)
                mins = [wp[0] - 0.2, wp[1] - 0.2, wp[2] - 0.2]
                maxs = [wp[0] + 0.2, wp[1] + 0.2, wp[2] + 0.2]
                has_data = True
            except Exception:
                return False
        # Apply padding by expanding the bbox.
        pad = float(max(0.0, padding))
        dx = (maxs[0] - mins[0]) * pad * 0.5
        dy = (maxs[1] - mins[1]) * pad * 0.5
        dz = (maxs[2] - mins[2]) * pad * 0.5
        mins[0] -= dx; mins[1] -= dy; mins[2] -= dz
        maxs[0] += dx; maxs[1] += dy; maxs[2] += dz
        try:
            self.camera.frame_bounds(tuple(mins), tuple(maxs), reset_view=True)
        except Exception as exc:
            log.debug("Head-subtree frame_bounds failed: %s", exc)
            return False
        self._request_render()
        return True

    # ── T404: Snap-view interpolation + Persp/Ortho ───────────────────
    def _reposition_viewcube(self) -> None:
        """Pin the ViewCube to the top-right viewport overlay area."""
        cube = getattr(self, "_viewcube_widget", None)
        if cube is None:
            return
        if not getattr(self, "_viewcube_visible", True):
            cube.hide()
            return
        cube.adjustSize()
        cw = max(0, self.canvas.width())
        ch = max(0, self.canvas.height())
        if cw < VIEWCUBE_MIN_CANVAS_W or ch < VIEWCUBE_MIN_CANVAS_H:
            cube.hide()
            return
        x = max(VIEWCUBE_MARGIN, cw - cube.width() - VIEWCUBE_MARGIN)
        y = VIEWCUBE_MARGIN
        cube.move(x, y)
        cube.show()
        cube.raise_()

    def _reposition_snap_view(self) -> None:
        """Backward-compatible name for older tests/extensions."""
        self._reposition_viewcube()

    def _viewcube_camera_state(self) -> tuple[float, float, bool]:
        return (
            float(getattr(self.camera, "azimuth", 90.0)),
            float(getattr(self.camera, "elevation", 20.0)),
            bool(getattr(self, "_ortho_mode", False)),
        )

    def execute_view_action(self, action: object) -> None:
        """Route ViewCube and legacy commands through the existing camera."""
        try:
            view_action = action if isinstance(action, ViewAction) else ViewAction(str(action))
        except ValueError:
            return
        if view_action is ViewAction.PERSPECTIVE:
            self.set_view_perspective()
            return
        if view_action is ViewAction.HOME:
            self.set_view_home()
            return
        target = target_for_action(view_action)
        if target is not None:
            self.animate_to_orientation(*target)

    def animate_to_orientation(self, azimuth: float, elevation: float) -> None:
        """Smoothly interpolate the arcball camera to an azimuth/elevation."""
        if self.is_camera_view_active() and not self._lock_view_to_camera:
            self.switch_to_perspective()
        from_az = float(self.camera.azimuth)
        from_el = float(self.camera.elevation)
        to_az, to_el = float(azimuth), float(elevation)
        delta_az = ((to_az - from_az) + 540.0) % 360.0 - 180.0
        self._snap_anim_from = (from_az, from_el)
        self._snap_anim_to = (from_az + delta_az, to_el)
        self._snap_anim_t0 = time_module.perf_counter()
        if not self._snap_anim_timer.isActive():
            self._snap_anim_timer.start()

    def orbit_from_viewcube_drag(self, daz: float, del_: float) -> None:
        """Orbit the existing camera in response to a ViewCube drag."""
        if self._snap_anim_timer.isActive():
            self._snap_anim_timer.stop()
        if self.is_camera_view_active() and not self._lock_view_to_camera:
            self.switch_to_perspective()
        self.camera.orbit(float(daz), float(del_))
        if self.is_camera_view_active() and self._lock_view_to_camera:
            self.update_camera_from_view()
        self._renderer.is_interactive = self._fast_drag_enabled
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._request_render(fast=True)

    def get_orientation_quaternion(self) -> tuple[float, float, float, float]:
        return view_orientation_quaternion(self.camera.azimuth, self.camera.elevation)

    def set_view_front(self) -> None:
        self.execute_view_action(ViewAction.FRONT)

    def set_view_back(self) -> None:
        self.execute_view_action(ViewAction.BACK)

    def set_view_left(self) -> None:
        self.execute_view_action(ViewAction.LEFT)

    def set_view_right(self) -> None:
        self.execute_view_action(ViewAction.RIGHT)

    def set_view_top(self) -> None:
        self.execute_view_action(ViewAction.TOP)

    def set_view_bottom(self) -> None:
        self.execute_view_action(ViewAction.BOTTOM)

    def set_view_perspective(self) -> None:
        self.set_ortho_mode(not self._ortho_mode)
        if self.is_camera_view_active():
            self.switch_to_perspective()
        else:
            self._request_render(fast=True)

    def set_view_home(self) -> None:
        self.reset_camera()

    def _snap_to_view(self, view: str) -> None:
        """Legacy snap-view entry point retained for shortcuts/extensions."""
        action = action_from_view_name(view)
        if action is not None:
            self.execute_view_action(action)
            return
        target = SNAP_VIEW_PRESETS.get(view)
        if target is None:
            return
        # Snapshot start state.  Azimuth must take the shortest angular
        # path (handle wrap-around 0 ↔ 360).
        from_az = float(self.camera.azimuth)
        from_el = float(self.camera.elevation)
        to_az, to_el = float(target[0]), float(target[1])
        delta_az = ((to_az - from_az) + 540.0) % 360.0 - 180.0
        to_az_resolved = from_az + delta_az
        self._snap_anim_from = (from_az, from_el)
        self._snap_anim_to = (to_az_resolved, to_el)
        self._snap_anim_t0 = time_module.perf_counter()
        if not self._snap_anim_timer.isActive():
            self._snap_anim_timer.start()

    def _snap_anim_tick(self) -> None:
        """One frame of the 200 ms snap-view tween."""
        elapsed_ms = (time_module.perf_counter() - self._snap_anim_t0) * 1000.0
        t = max(0.0, min(1.0, elapsed_ms / float(SNAP_VIEW_INTERP_MS)))
        # Ease-in-out cubic — feels natural for a camera snap.
        if t < 0.5:
            ease = 4.0 * t * t * t
        else:
            f = (2.0 * t - 2.0)
            ease = 1.0 + 0.5 * f * f * f
        from_az, from_el = self._snap_anim_from
        to_az,   to_el   = self._snap_anim_to
        self.camera.azimuth   = (from_az + (to_az - from_az) * ease) % 360.0
        self.camera.elevation = from_el + (to_el - from_el) * ease
        if t >= 1.0:
            self._snap_anim_timer.stop()
            # Snap to exact target to defeat float drift.
            self.camera.azimuth   = to_az % 360.0
            self.camera.elevation = to_el
        if self.is_camera_view_active() and self._lock_view_to_camera:
            self.update_camera_from_view()
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._request_render(fast=True)

    def set_ortho_mode(self, ortho: bool) -> None:
        """Toggle perspective ↔ orthographic projection.

        Implementation note: ``ArcBallCamera`` only models a perspective
        projection.  We simulate orthographic by collapsing the FOV to
        a very small value and increasing the camera distance to keep
        the framing roughly stable — visually indistinguishable from
        a true ortho projection for the rigging use case.
        """
        new_val = bool(ortho)
        if new_val == self._ortho_mode:
            return
        self._ortho_mode = new_val
        # Persist a "real" perspective FOV the first time we go ortho so
        # we can restore exactly on toggle-off.
        if not hasattr(self, "_persp_fov_saved") or self._persp_fov_saved is None:
            self._persp_fov_saved = float(getattr(self.camera, "fov", 45.0))
        if new_val:
            # Save current state and shrink FOV.
            self._persp_fov_saved = float(self.camera.fov)
            self._persp_distance_saved = float(self.camera.distance)
            # Pull camera back and shrink FOV proportionally so the
            # projected size of the model stays approximately constant.
            ortho_fov = 1.5
            scale = math.tan(math.radians(self._persp_fov_saved) * 0.5) / math.tan(
                math.radians(ortho_fov) * 0.5
            )
            self.camera.fov = ortho_fov
            self.camera.distance = max(0.5, self._persp_distance_saved * scale)
        else:
            # Restore perspective.
            self.camera.fov = float(getattr(self, "_persp_fov_saved", 45.0))
            saved_dist = getattr(self, "_persp_distance_saved", None)
            if saved_dist is not None:
                self.camera.distance = float(saved_dist)
        # Keep the snap-view bar's toggle button in sync if the call
        # came from somewhere other than the bar itself.
        if hasattr(self, "_snap_view_widget") and self._snap_view_widget is not None and hasattr(self._snap_view_widget, "ortho_button"):
            btn = self._snap_view_widget.ortho_button
            with QtCore.QSignalBlocker(btn):
                btn.setChecked(new_val)
                btn.setText("Ortho" if new_val else "Persp")
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._request_render()

    @property
    def ortho_mode(self) -> bool:
        return self._ortho_mode

    def _request_render(self, fast: bool = False) -> None:
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._render_pending = True
        now = time_module.perf_counter()
        min_interval_ms = 33 if self._dual_viewport_mode else 16
        if fast:
            self._fast_frame_until = max(self._fast_frame_until, now + 0.08)
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            delay = max(1, int(min_interval_ms - elapsed_ms))
        else:
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            delay = max(16, int(min_interval_ms - elapsed_ms))
        if self._render_timer.isActive():
            delay = min(delay, max(1, self._render_timer.remainingTime()))
        self._render_timer.start(delay)

    def _queue_post_load_gpu_refresh(self) -> None:
        self._post_load_refresh_model_id = id(self.model) if self.model is not None else 0
        self._post_load_refresh_timer.start(250)

    def _post_load_gpu_refresh(self) -> None:
        if self.model is None or id(self.model) != self._post_load_refresh_model_id:
            return
        self._request_render()

    def _on_texture_prewarm_finished(self, model_id: object) -> None:
        if self.model is not None and id(self.model) == model_id:
            self._queue_post_load_gpu_refresh()

    def _start_deferred_txi_metadata(self, model) -> None:
        if model is None or not getattr(model, "_gr_defer_txi_metadata", False):
            return
        try:
            setattr(model, "_gr_defer_txi_metadata", False)
        except Exception:
            pass
        model_id = id(model)
        renderer = self._renderer

        def load() -> None:
            try:
                renderer._load_txi_metadata_for_model(model)
            except Exception:
                log.debug("Deferred TXI metadata load failed", exc_info=True)
            self._deferredTxiFinished.emit(model_id)

        threading.Thread(target=load, daemon=True, name="qt-txi-prewarm").start()

    def _on_deferred_txi_finished(self, model_id: object) -> None:
        if self.model is not None and id(self.model) == model_id:
            self._prewarm_textures(self.model)
            self._queue_post_load_gpu_refresh()

    def _render_now(self) -> None:
        if not self._render_pending:
            return
        self._render_pending = False
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        t0 = time_module.perf_counter()
        try:
            img = self._render_frame(w, h)
        except Exception as exc:
            log.error("GPU viewport render failed for %s: %s", getattr(self.model, "name", "scene"), exc, exc_info=True)
            img = None
        self._last_render_ms = (time_module.perf_counter() - t0) * 1000.0
        self._last_render_wall = time_module.perf_counter()
        if img is None:
            if self.model is None:
                self.canvas.setText("GPU render unavailable\nEmpty Scene")
                return
            mesh_count = len(self.model.mesh_nodes()) if hasattr(self.model, "mesh_nodes") else 0
            node_count = self.model.node_count() if hasattr(self.model, "node_count") else 0
            self.canvas.setText(f"{getattr(self.model, 'name', 'model')}\nGPU render unavailable\n{mesh_count} mesh | {node_count} nodes")
            return
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        self._update_fps()
        qimg = QtGui.QImage(
            img.tobytes("raw", "RGBA"),
            img.width,
            img.height,
            img.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        self._pixmap = QtGui.QPixmap.fromImage(qimg)
        if self.canvas.is_live_surface():
            self.canvas.set_overlay_pixmap(self._pixmap)
        else:
            self.canvas.setPixmap(self._pixmap)
        rendered_size = (w, h)
        self._last_rendered_canvas_size = rendered_size
        current_size = (max(8, self.canvas.width()), max(8, self.canvas.height()))
        if current_size != rendered_size:
            self._request_render()

    def _render_frame(self, w: int, h: int):
        self._use_gpu = True
        img = self._render_gpu_frame(w, h)
        if img is None:
            self._set_renderer_badge(False)
            return None
        self._set_renderer_badge(True)
        img = self._draw_gpu_viewport_overlays(img, w, h)
        img = self._draw_performance_overlay(img, w, h)
        return img

    def _draw_xray_grid_overlay(self, img, w: int, h: int):
        if img is None:
            return None
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self._renderer._draw_grid(ImageDraw.Draw(img, "RGBA"), w, h)
            return img
        except Exception as exc:
            log.debug("X-Ray grid overlay draw failed: %s", exc)
            return img

    def _render_gpu_frame(self, w: int, h: int):
        if self._gpu_renderer is None:
            self._gpu_renderer = create_viewport_renderer(self._renderer_settings)
            theme = getattr(self, "_current_theme", None)
            if theme is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
                self._gpu_renderer.set_theme_colors(theme)
            else:
                self._apply_native_palette_to_renderers()
            self._sync_renderer_surface(force=True)
        else:
            self._sync_renderer_surface()
        self._preload_gpu_textures()
        tex_cache = getattr(self._renderer, "tex_cache", None)
        textures = {
            key: value
            for key, value in getattr(tex_cache, "_cache", {}).items()
            if value is not None
        }
        try:
            from PIL import Image

            nodes = self.model.all_nodes() if hasattr(self.model, "all_nodes") else []
            for node in nodes:
                override_path = str(getattr(node, "_gr_baked_lightmap_preview_path", "") or getattr(node, "_gr_baked_lightmap_path", "") or "")
                override_name = str(getattr(node, "_gr_baked_lightmap_preview_name", "") or "")
                if override_path and override_name and os.path.isfile(override_path):
                    textures[override_name.lower()] = Image.open(override_path).convert("RGBA")
        except Exception:
            pass
        self._gpu_renderer.interactive = bool(
            self._renderer.is_interactive
            or self._pan_dragging
            or self._nav_dragging
            or self._is_dragging
            or time_module.perf_counter() < self._fast_frame_until
        )
        self._gpu_renderer.show_solid = bool(self._renderer.show_solid)
        self._gpu_renderer.show_texture = bool(self._renderer.show_texture)
        self._gpu_renderer.show_diffuse_map = bool(getattr(self._renderer, "show_diffuse_map", True))
        self._gpu_renderer.show_lightmap_map = bool(getattr(self._renderer, "show_lightmap_map", True))
        self._gpu_renderer.show_environment_map = bool(getattr(self._renderer, "show_environment_map", True))
        self._gpu_renderer.show_specular_map = bool(getattr(self._renderer, "show_specular_map", True))
        self._gpu_renderer.show_normal_map = bool(getattr(self._renderer, "show_normal_map", True))
        self._gpu_renderer.lighting_mode = str(getattr(self._renderer, "lighting_mode", "scene") or "scene")
        self._gpu_renderer.scene_ambient = float(getattr(self._renderer, "scene_ambient", 0.06))
        self._gpu_renderer.lightmap_intensity = float(getattr(self._renderer, "lightmap_intensity", 0.55))
        self._gpu_renderer.lightmap_mode = str(getattr(self._renderer, "lightmap_mode", "baked") or "baked")
        self._gpu_renderer.show_light_gizmos = bool(getattr(self._renderer, "show_light_gizmos", True))
        self._gpu_renderer.show_wireframe = bool(self._renderer.show_wireframe)
        self._gpu_renderer.render_mode = str(getattr(self._renderer, "render_mode", "realistic") or "realistic")
        self._gpu_renderer.selected_node = getattr(self._renderer, "selected_node", None)
        self._gpu_renderer.selected_nodes = list(getattr(self, "_selected_meshes", []) or [])
        self._gpu_renderer.show_grid = bool(getattr(self._renderer, "show_grid", True))
        self._gpu_renderer.cull_faces = False
        try:
            self._gpu_renderer.surface_host_diagnostics = self.canvas.diagnostics()
        except Exception:
            pass
        img = self._gpu_renderer.render(
            self.model,
            self.camera,
            w,
            h,
            textures=textures,
            anim_pose=getattr(self._renderer, "_anim_pose", None),
            anim_time=float(getattr(self._renderer, "_anim_time", 0.0)),
            anim_base_pose=getattr(self._renderer, "_anim_base_pose", None),
        )
        diagnostics = {}
        get_diagnostics = getattr(self._gpu_renderer, "get_diagnostics", None)
        if callable(get_diagnostics):
            try:
                diagnostics = get_diagnostics() or {}
            except Exception:
                diagnostics = {}
        backend_id = str(diagnostics.get("backend_id") or getattr(self._gpu_renderer, "backend_id", "") or "")
        if backend_id and (
            self.canvas.surface_backend_id() != backend_id
            or self.canvas.is_live_surface() != self._renderer_uses_live_surface(backend_id)
        ):
            self._sync_renderer_surface(force=True)
        if backend_id and backend_id != self._last_renderer_backend_id:
            self._last_renderer_backend_id = backend_id
            label = str(diagnostics.get("name") or backend_id)
            self.statusMessage.emit(f"Renderer: {label}")
        if getattr(self._gpu_renderer, "deferred_mesh_uploads", False):
            model_id = id(self.model)

            def _continue_uploads() -> None:
                if self.model is not None and id(self.model) == model_id:
                    self._request_render(fast=True)

            QtCore.QTimer.singleShot(1, _continue_uploads)
        if self._gpu_upload_total > 0 and self.model is not None and id(self.model) == self._gpu_upload_model_id:
            uploaded = min(len(getattr(self._gpu_renderer, "_mesh_cache", {}) or {}), self._gpu_upload_total)
            if not getattr(self._gpu_renderer, "deferred_mesh_uploads", False):
                uploaded = self._gpu_upload_total
            self.gpuUploadProgress.emit(uploaded, self._gpu_upload_total)
            if uploaded >= self._gpu_upload_total:
                self._gpu_upload_total = 0
                self._gpu_upload_model_id = 0
        return img

    def _draw_gpu_viewport_overlays(self, img, w: int, h: int):
        """Draw screen-space viewport tools over an already-rendered GPU frame.

        This intentionally does not call FrameRenderer.render() or any CPU mesh
        rasterizer.  It only restores the interactive overlay layer that lives
        above the GPU scene: gimbal tools, transform gizmo, HUD stats, axes,
        selection outlines, measurement/camera helpers, and editor markers.
        """
        if img is None:
            return None
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self._renderer._last_W = w
            self._renderer._last_H = h
            try:
                self._renderer._frame_view = self._renderer._cam_view_matrix()
                self._renderer._frame_verts_cache = {}
                self._renderer._frame_norms_cache = {}
            except Exception:
                pass
            draw = ImageDraw.Draw(img, "RGBA")
            if self._xray_mode:
                self._renderer._draw_grid(draw, w, h)
            # T405: weight heat-map runs BEFORE bones so the joint dots
            # stay clearly visible on top of the colored vertex cloud.
            if self._weight_heatmap_enabled:
                self._draw_weight_heatmap(draw, w, h)
            if self._renderer.show_bones:
                self._renderer._draw_bones(draw, w, h)
                # T401: paint AccuRig-style color-coded joint dots on top.
                # Runs only when the skeleton is visible — the dots are
                # meant to make joints clickable/identifiable during rig
                # editing.  Cheap (one pass over `_bone_screen_positions`).
                if self._joint_dot_enabled:
                    self._draw_joint_dots(img, w, h)
            if getattr(self._renderer, "_ext_skeleton", None) is not None:
                self._renderer._draw_ext_skeleton(draw, w, h)
            if self._renderer.show_walkmesh:
                self._renderer._draw_walkmesh_overlay(draw, w, h)
            self._draw_camera_helpers(draw, w, h)
            if self._ensure_renderer_gimbal_state():
                self._draw_transform_gizmo(draw, w, h)
            self._draw_measurement_overlay(draw, w, h)
            self._draw_hovered_mesh_outline(draw, w, h)
            self._draw_mesh_subobject_selection(draw, w, h)
            self._draw_joint_marquee(draw)
            self._renderer._draw_axes(draw, w, h)
            self._renderer._draw_stats(draw, w, h)
            self._draw_active_camera_overlays(draw, w, h)
            return img
        except Exception as exc:
            log.debug("Qt GPU overlay draw failed: %s", exc)
            return img

    def _draw_cpu_overlays(self, img, w: int, h: int, *, gpu_base: bool = False):
        return self._draw_gpu_viewport_overlays(img, w, h)

    def _draw_transform_gizmo_overlay(self, img, w: int, h: int):
        if img is None:
            return None
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self._renderer._last_W = w
            self._renderer._last_H = h
            self._renderer._frame_view = self._renderer._cam_view_matrix()
            self._draw_camera_helpers(ImageDraw.Draw(img, "RGBA"), w, h)
            self._draw_transform_gizmo(ImageDraw.Draw(img, "RGBA"), w, h)
            self._draw_measurement_overlay(ImageDraw.Draw(img, "RGBA"), w, h)
            self._draw_active_camera_overlays(ImageDraw.Draw(img, "RGBA"), w, h)
            return img
        except Exception as exc:
            log.debug("Transform gizmo overlay draw failed: %s", exc)
            return img

    def _draw_transform_gizmo(self, draw, w: int, h: int) -> None:
        if not self._ensure_renderer_gimbal_state():
            return
        self._transform_gizmo.visible = True
        node = self._active_gizmo_node()
        if node is None:
            self._transform_gizmo.clear_selection()
            return
        if node is not None:
            try:
                wp = self._gizmo_world_position(node)
                setattr(node, "_gr_gizmo_world_position", wp)
            except Exception:
                pass
            self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)
        self._transform_gizmo.renderer.AXIS_COLORS = {
            "X": tuple(getattr(self._renderer, "gimbal_x_color", (220, 60, 60)))[:3] + (255,),
            "Y": tuple(getattr(self._renderer, "gimbal_y_color", (60, 220, 80)))[:3] + (255,),
            "Z": tuple(getattr(self._renderer, "gimbal_z_color", (70, 135, 240)))[:3] + (255,),
        }
        self._transform_gizmo.renderer.HILITE = (
            tuple(getattr(self._renderer, "gimbal_active_color", (255, 235, 80)))[:3] + (255,)
        )
        self._transform_gizmo.draw(draw, self.camera, self._renderer._proj, w, h)

    def _draw_measurement_overlay(self, draw, w: int, h: int) -> None:
        try:
            self.measurement_controller.draw_overlay(draw, self._renderer._proj, w, h)
        except Exception as exc:
            log.debug("Measurement overlay draw failed: %s", exc)

    def _draw_camera_helpers(self, draw, w: int, h: int) -> None:
        try:
            active_id = self.camera_manager.active_camera_id
            self._camera_helper_renderer.draw(
                draw,
                self.camera_manager.get_all_cameras(),
                active_id,
                self._renderer._proj,
                w,
                h,
            )
        except Exception as exc:
            log.debug("Camera helper draw failed: %s", exc)

    def _draw_active_camera_overlays(self, draw, w: int, h: int) -> None:
        try:
            if bool(getattr(self, "_render_suppress_camera_overlays", False)):
                return
            camera = self.camera_manager.get_active_camera()
            if camera is None or not self._camera_view_active:
                return
            self._camera_overlays.draw(draw, camera, w, h, include_guides=True)
        except Exception as exc:
            log.debug("Camera overlay draw failed: %s", exc)

    # ── T401: Joint-dot overlay ────────────────────────────────────────
    def _draw_joint_marquee(self, draw) -> None:
        if not self._joint_marquee_selecting:
            return
        try:
            x0, y0 = self._joint_marquee_start
            x1, y1 = self._joint_marquee_current
            if abs(x1 - x0) < self._drag_threshold and abs(y1 - y0) < self._drag_threshold:
                return
            left, right = sorted((int(x0), int(x1)))
            top, bottom = sorted((int(y0), int(y1)))
            draw.rectangle([left, top, right, bottom], fill=(255, 212, 0, 38), outline=(255, 212, 0, 210), width=1)
        except Exception as exc:
            log.debug("Joint marquee draw failed: %s", exc)

    def _draw_joint_dots(self, img, w: int, h: int) -> None:
        """Paint AccuRig-style color-coded joint dots over the mesh.

        Color classification follows the M4 spec:
          * center        → ``JOINT_DOT_COLOR_CENTER``         (#FFD400)
          * center-spine  → ``JOINT_DOT_COLOR_CENTER_SPINE``   (#00D7B5)
          * L-side        → ``JOINT_DOT_COLOR_LEFT``           (#FF4040)
          * R-side        → ``JOINT_DOT_COLOR_RIGHT``          (#00FF7A)

        Size and opacity are inspector-driven (see ``set_joint_dot_size`` /
        ``set_joint_dot_opacity``).  This method consumes the renderer's
        per-frame ``_bone_screen_positions`` cache (already populated by
        ``_draw_bones``) so projection cost is zero.
        """
        try:
            positions = getattr(self._renderer, "_bone_screen_positions", None)
            if not positions:
                return

            radius = int(max(1, min(8, self._joint_dot_size)))
            alpha = int(round(max(0.0, min(1.0, self._joint_dot_opacity)) * 255))
            if alpha <= 0:
                return

            # Convert the PIL image to a QImage in-place so we can render
            # smooth, anti-aliased Qt circles.  The image is wrapped
            # via the buffer protocol — no pixel copy is performed.
            try:
                from PIL.ImageQt import ImageQt
            except Exception:
                # Fallback: draw with PIL primitives (no AA but still correct).
                self._draw_joint_dots_pil(img, positions, radius, alpha)
                return

            qimg = QtGui.QImage(ImageQt(img))
            painter = QtGui.QPainter(qimg)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                # Selected node gets a brighter outline so the user can
                # still see selection state through the dot.
                sel_node = getattr(self._renderer, "selected_node", None)
                selected_ids = {id(n) for n in self._selected_joint_nodes}
                outline_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, alpha), 1.0)
                sel_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, alpha), 2.0)
                key_color = QtGui.QColor(JOINT_DOT_COLOR_KEY)
                key_color.setAlpha(alpha)
                key_pen = QtGui.QPen(key_color, 2.0)
                for entry in positions:
                    if not entry or len(entry) < 4:
                        continue
                    sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                    if sx is None or sy is None:
                        continue
                    name = getattr(node, "name", "") or ""
                    color = QtGui.QColor("#FFDA28") if node is sel_node else QtGui.QColor(_classify_joint_color(name))
                    color.setAlpha(alpha)
                    if _is_key_joint_name(name):
                        painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
                        painter.setPen(key_pen)
                        painter.drawEllipse(
                            QtCore.QPointF(float(sx), float(sy)),
                            float(radius + 2),
                            float(radius + 2),
                        )
                    painter.setBrush(QtGui.QBrush(color))
                    painter.setPen(sel_pen if node is sel_node or id(node) in selected_ids else outline_pen)
                    painter.drawEllipse(
                        QtCore.QPointF(float(sx), float(sy)),
                        float(radius),
                        float(radius),
                    )
            finally:
                painter.end()

            # Copy the painted QImage pixels back into the PIL image
            # buffer.  We rely on PIL's `frombytes` to avoid returning a
            # new object (the caller already holds `img`).
            try:
                qimg_rgba = qimg.convertToFormat(QtGui.QImage.Format_RGBA8888)
                ptr = qimg_rgba.constBits()
                # PySide6 returns a memoryview; ensure we have raw bytes
                raw = bytes(ptr)[: qimg_rgba.sizeInBytes()]
                from PIL import Image as _PILImage  # noqa: F401  (import side-effect safety)
                img.frombytes(raw)
            except Exception as exc:
                log.debug("Joint-dot pixel writeback fell back: %s", exc)
                self._draw_joint_dots_pil(img, positions, radius, alpha)
        except Exception as exc:
            log.debug("Joint-dot overlay failed: %s", exc)

    # ── T405: Weight heat-map overlay ──────────────────────────────────
    def _draw_weight_heatmap(self, draw, W: int, H: int) -> None:
        """Paint a per-vertex weight heat-map for the selected bone.

        For every skin-mesh node in the model, project each vertex to
        screen space and stamp a small filled circle whose color is
        :func:`_weight_to_heatmap_color` of the selected bone's weight
        on that vertex.  Vertices not influenced by the selected bone
        receive weight 0 → deep blue.

        No-op fast paths:
          * No model or no selected node → return immediately.
          * Selected node not present in a given mesh's ``bone_map`` →
            skip that mesh (all its vertices would be weight=0 noise).
        """
        if self.model is None:
            return
        sel = self._renderer.selected_node
        if sel is None:
            return
        sel_name = (getattr(sel, "name", "") or "").lower()
        if not sel_name:
            return
        try:
            mesh_iter = self.model.mesh_nodes() if hasattr(self.model, "mesh_nodes") else []
        except Exception:
            return
        radius = int(max(1, min(8, self._weight_heatmap_dot_size)))
        for node in mesh_iter:
            try:
                verts = getattr(node, "vertices", None) or []
                skin_data = getattr(node, "skin_data", None) or []
                bone_map = getattr(node, "bone_map", None) or []
                if not verts or not skin_data or not bone_map:
                    continue
                # Find the selected bone's index in this mesh's bone_map.
                # Bone names in bone_map are stored as authored; compare
                # case-insensitively.
                sel_idx = -1
                for i, bn in enumerate(bone_map):
                    if isinstance(bn, str) and bn.lower() == sel_name:
                        sel_idx = i
                        break
                if sel_idx < 0:
                    continue
                # Project all verts in this mesh in one batched call.
                try:
                    wp, _wo, _ = self._renderer._node_world_transform(node)
                except Exception:
                    wp = (0.0, 0.0, 0.0)
                world_verts = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
                projections = self._renderer._proj_batch(world_verts, W, H)
                for vi, proj in enumerate(projections):
                    if proj is None:
                        continue
                    sx, sy, _depth = proj
                    if sx < -radius or sy < -radius or sx > W + radius or sy > H + radius:
                        continue
                    # Look up the selected bone's weight on this vertex.
                    weight = 0.0
                    if vi < len(skin_data):
                        infl = getattr(skin_data[vi], "influences", None) or []
                        for bw in infl:
                            if getattr(bw, "bone_index", -1) == sel_idx:
                                weight = float(getattr(bw, "weight", 0.0))
                                break
                    r8, g8, b8 = _weight_to_heatmap_color(weight)
                    fill = (r8, g8, b8, 200)
                    draw.ellipse(
                        [sx - radius, sy - radius, sx + radius, sy + radius],
                        fill=fill,
                        outline=None,
                    )
            except Exception as exc:
                log.debug("Heat-map draw skipped node %s: %s",
                          getattr(node, "name", "?"), exc)
                continue

    def set_weight_heatmap_enabled(self, enabled: bool) -> None:
        """Toggle the per-vertex weight heat-map overlay."""
        new_val = bool(enabled)
        if new_val == self._weight_heatmap_enabled:
            if hasattr(self, "heatmap_button"):
                self.heatmap_button.blockSignals(True)
                self.heatmap_button.setChecked(new_val)
                self.heatmap_button.blockSignals(False)
            return
        self._weight_heatmap_enabled = new_val
        if hasattr(self, "heatmap_button"):
            self.heatmap_button.blockSignals(True)
            self.heatmap_button.setChecked(new_val)
            self.heatmap_button.blockSignals(False)
        self._request_render()

    def set_weight_heatmap_dot_size(self, size: int) -> None:
        """Set the heat-map dot radius in pixels.  Clamped to [1, 8]."""
        new_size = int(max(1, min(8, int(size))))
        if new_size == self._weight_heatmap_dot_size:
            return
        self._weight_heatmap_dot_size = new_size
        self._request_render()

    @property
    def weight_heatmap_enabled(self) -> bool:
        return self._weight_heatmap_enabled

    @property
    def weight_heatmap_dot_size(self) -> int:
        return self._weight_heatmap_dot_size

    def _draw_joint_dots_pil(self, img, positions, radius: int, alpha: int) -> None:
        """PIL-only fallback for ``_draw_joint_dots`` (no anti-aliasing).

        Used when ``PIL.ImageQt`` is unavailable or the QImage round-trip
        fails.  Functionally equivalent — colors and hit positions match.
        """
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img, "RGBA")
            sel_node = getattr(self._renderer, "selected_node", None)
            selected_ids = {id(n) for n in self._selected_joint_nodes}
            for entry in positions:
                if not entry or len(entry) < 4:
                    continue
                sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                if sx is None or sy is None:
                    continue
                name = getattr(node, "name", "") or ""
                qc = QtGui.QColor("#FFDA28") if node is sel_node else _classify_joint_color(name)
                fill = (qc.red(), qc.green(), qc.blue(), alpha)
                is_selected = node is sel_node or id(node) in selected_ids
                outline = (255, 255, 255, alpha) if is_selected else (0, 0, 0, alpha)
                if _is_key_joint_name(name):
                    key_outline = (
                        JOINT_DOT_COLOR_KEY.red(),
                        JOINT_DOT_COLOR_KEY.green(),
                        JOINT_DOT_COLOR_KEY.blue(),
                        alpha,
                    )
                    draw.ellipse(
                        [sx - radius - 2, sy - radius - 2, sx + radius + 2, sy + radius + 2],
                        outline=key_outline,
                        width=2,
                    )
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=fill,
                    outline=outline,
                    width=2 if is_selected else 1,
                )
        except Exception as exc:
            log.debug("Joint-dot PIL fallback failed: %s", exc)

    # ── T402: Joint-dot hit-test + symmetry ────────────────────────────
    def _joint_dot_hit_test(self, x: int, y: int):
        """Return the joint node under screen pixel ``(x, y)`` or ``None``.

        Uses the same ``_bone_screen_positions`` cache populated by the
        renderer's last ``_draw_bones`` pass, so this is essentially
        free.  The hit-radius is the user's current joint-dot radius
        plus a small slack so corner pixels still count.
        """
        if not self._joint_dot_enabled:
            return None
        positions = self._joint_hit_positions()
        if not positions:
            return None
        # 4 px slack so the cursor can be slightly outside the painted disc.
        radius = int(max(1, min(8, self._joint_dot_size))) + 4
        r2 = radius * radius
        best_node = None
        best_d2 = r2
        best_depth = 1e18
        for entry in positions:
            if not entry or len(entry) < 4:
                continue
            sx, sy, depth, node = entry[0], entry[1], entry[2], entry[3]
            if sx is None or sy is None:
                continue
            dx = sx - x
            dy = sy - y
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            # Prefer the closer (smaller depth) of the dots within range —
            # when joints overlap on screen the front-most one should win.
            if d2 < best_d2 or (d2 == best_d2 and depth < best_depth):
                best_d2 = d2
                best_depth = depth
                best_node = node
        return best_node

    def _joint_mirror_partner(self, node):
        """Return the MIRROR_PAIRS partner node of ``node`` or ``None``.

        Symmetry-aware drags rely on this to look up the bone whose
        position must be reflected across the model's X axis.  Looks
        up partners using ``src/autorig/accurig.MIRROR_PAIRS`` (the
        canonical AccuRig L↔R table) in both directions.
        """
        if node is None or not self._joint_symmetry_enabled:
            return None
        search_model = (
            getattr(self._renderer, "_ext_skeleton", None)
            if self._is_external_skeleton_node(node)
            else self.model
        )
        if not search_model:
            return None
        name = (getattr(node, "name", "") or "").lower()
        if not name:
            return None
        try:
            from src.autorig.accurig import MIRROR_PAIRS
        except Exception:
            try:
                from src.autorig.accurig import MIRROR_PAIRS  # type: ignore
            except Exception:
                try:
                    from autorig.accurig import MIRROR_PAIRS  # type: ignore
                except Exception:
                    MIRROR_PAIRS = {}
        partner_name = None
        # Forward lookup (left -> right)
        if name in MIRROR_PAIRS:
            partner_name = MIRROR_PAIRS[name]
        else:
            # Reverse lookup (right -> left)
            for ln, rn in MIRROR_PAIRS.items():
                if rn == name:
                    partner_name = ln
                    break
        if partner_name is not None:
            try:
                found = search_model.find_node(partner_name)
                if found is not None:
                    return found
            except Exception:
                pass

        # KOTOR skeletons include useful l*/r* pairs that are not all in
        # AcuRig's compact guide table, for example lcollar_dum/rcollar_dum.
        candidates = []
        if name.startswith("l"):
            candidates.append("r" + name[1:])
        elif name.startswith("r"):
            candidates.append("l" + name[1:])
        candidates.extend([
            name.replace("_l", "_r"),
            name.replace("_r", "_l"),
            name.replace(".l", ".r"),
            name.replace(".r", ".l"),
            name.replace("left", "right"),
            name.replace("right", "left"),
        ])
        for candidate in candidates:
            if not candidate or candidate == name:
                continue
            try:
                found = search_model.find_node(candidate)
                if found is not None:
                    return found
            except Exception:
                continue
        return None

    def set_joint_symmetry(self, enabled: bool) -> None:
        """Toggle MIRROR_PAIRS-based symmetry for joint-dot drags."""
        self._joint_symmetry_enabled = bool(enabled)

    @property
    def joint_symmetry_enabled(self) -> bool:
        return self._joint_symmetry_enabled

    # ── T401: Public setters (inspector wires these later in M4) ───────
    def set_joint_dot_enabled(self, enabled: bool) -> None:
        """Toggle the joint-dot overlay layer on/off."""
        new_val = bool(enabled)
        if new_val == self._joint_dot_enabled:
            if hasattr(self, "joint_dot_button"):
                self.joint_dot_button.blockSignals(True)
                self.joint_dot_button.setChecked(new_val)
                self.joint_dot_button.blockSignals(False)
            return
        self._joint_dot_enabled = new_val
        if hasattr(self, "joint_dot_button"):
            self.joint_dot_button.blockSignals(True)
            self.joint_dot_button.setChecked(new_val)
            self.joint_dot_button.blockSignals(False)
        self._request_render()

    def set_joint_dot_size(self, size: int) -> None:
        """Set joint-dot radius in pixels.  Clamped to [1, 8]."""
        new_size = int(max(1, min(8, int(size))))
        if new_size == self._joint_dot_size:
            return
        self._joint_dot_size = new_size
        self._request_render()

    def set_joint_dot_opacity(self, opacity: float) -> None:
        """Set joint-dot opacity in [0.0, 1.0]."""
        new_op = float(max(0.0, min(1.0, float(opacity))))
        if abs(new_op - self._joint_dot_opacity) < 1e-4:
            return
        self._joint_dot_opacity = new_op
        self._request_render()

    @property
    def joint_dot_enabled(self) -> bool:
        return self._joint_dot_enabled

    @property
    def joint_dot_size(self) -> int:
        return self._joint_dot_size

    @property
    def joint_dot_opacity(self) -> float:
        return self._joint_dot_opacity

    def _request_render(self, fast: bool = False) -> None:
        """Best-effort viewport refresh used by joint-dot setters.

        Reuses the existing render-coalescing timer when available; falls
        back to a direct ``update()`` so the overlay reflects state
        changes immediately even on minimal viewports.
        """
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        try:
            if (
                hasattr(self, "_render_timer")
                and self._render_timer is not None
                and hasattr(self, "_last_render_wall")
            ):
                self._render_pending = True
                now = time_module.perf_counter()
                min_interval_ms = 33 if getattr(self, "_dual_viewport_mode", False) else 16
                if fast:
                    self._fast_frame_until = max(
                        getattr(self, "_fast_frame_until", 0.0),
                        now + 0.08,
                    )
                    elapsed_ms = (
                        (now - self._last_render_wall) * 1000.0
                        if self._last_render_wall else min_interval_ms
                    )
                    delay = max(1, int(min_interval_ms - elapsed_ms))
                else:
                    elapsed_ms = (
                        (now - self._last_render_wall) * 1000.0
                        if self._last_render_wall else min_interval_ms
                    )
                    delay = max(16, int(min_interval_ms - elapsed_ms))
                if self._render_timer.isActive():
                    delay = min(delay, max(1, self._render_timer.remainingTime()))
                self._render_timer.start(delay)
                return
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass

    def _update_fps(self) -> None:
        now = time_module.perf_counter()
        delta = max(0.0, now - self._fps_last_wall)
        self._fps_last_wall = now
        self._fps_accum += delta
        self._fps_frames += 1
        if self._fps_accum >= 0.5:
            self._fps_display = self._fps_frames / max(self._fps_accum, 1e-6)
            self._fps_accum = 0.0
            self._fps_frames = 0

    def _draw_performance_overlay(self, img, w: int, h: int):
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            fps = self._fps_display
            if fps <= 0.0 and self._last_render_ms > 0.0:
                fps = 1000.0 / max(self._last_render_ms, 1.0)
            mode = "fast" if time_module.perf_counter() < self._fast_frame_until else "hq"
            label = f"{fps:4.0f} fps  {self._last_render_ms:4.0f} ms  {mode}"
            text_w = self._renderer._hud_text_width(label) if hasattr(self._renderer, "_hud_text_width") else len(label) * 7
            x = max(8, w - text_w - 20)
            y = max(8, h - 50)
            self._renderer._draw_hud_pill(
                draw,
                x,
                y,
                label,
                fill=(18, 22, 27),
                fg=(156, 232, 184),
                outline=(42, 90, 62),
            )
            return img
        except Exception as exc:
            log.debug("Viewport FPS overlay draw failed: %s", exc)
            return img

    def _preload_gpu_textures(self) -> None:
        model = self.model
        tex_cache = getattr(self._renderer, "tex_cache", None)
        if model is None or tex_cache is None or id(model) == self._gpu_tex_preload_model_id:
            return
        # Do not synchronously decode archive textures on the Qt paint path.
        # Background _prewarm_textures() populates TextureCache, and each refresh
        # uploads whatever is already resident. Missing textures render with the
        # GPU fallback material until the background pass emits a refresh.
        self._gpu_tex_preload_model_id = id(model)

    def _set_renderer_badge(self, gpu_active: bool) -> None:
        if not hasattr(self, "renderer_button"):
            return
        self._use_gpu = True
        self.renderer_button.setChecked(True)
        backend = ""
        if self._gpu_renderer is not None:
            get_diagnostics = getattr(self._gpu_renderer, "get_diagnostics", None)
            if callable(get_diagnostics):
                try:
                    backend = str((get_diagnostics() or {}).get("name") or "")
                except Exception:
                    backend = ""
        label = f"GPU renderer: {backend}" if backend else "GPU renderer"
        self.renderer_button.setToolTip(label if gpu_active else "GPU renderer unavailable")

    def _on_shade_change(self, text: str) -> None:
        self.set_shade_mode(text)

    def _on_render_mode_change(self, text: str) -> None:
        self.set_render_mode(text)

    @staticmethod
    def _point_in_triangle(px: float, py: float, a, b, c) -> bool:
        denom = ((b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]))
        if abs(denom) < 1e-6:
            return False
        w1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denom
        w2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denom
        w3 = 1.0 - w1 - w2
        return w1 >= -0.001 and w2 >= -0.001 and w3 >= -0.001

    def _front_facing_score(self, world_verts, face) -> float:
        try:
            i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
            p0, p1, p2 = world_verts[i0], world_verts[i1], world_verts[i2]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            cx = (p0[0] + p1[0] + p2[0]) / 3.0
            cy = (p0[1] + p1[1] + p2[1]) / 3.0
            cz = (p0[2] + p1[2] + p2[2]) / 3.0
            eye_getter = getattr(self.camera, "eye", (0.0, 0.0, 0.0))
            eye = eye_getter() if callable(eye_getter) else eye_getter
            to_eye = (eye[0] - cx, eye[1] - cy, eye[2] - cz)
            dot = nx * to_eye[0] + ny * to_eye[1] + nz * to_eye[2]
            normal_len = max(1e-6, math.sqrt(nx * nx + ny * ny + nz * nz))
            view_len = max(1e-6, math.sqrt(to_eye[0] * to_eye[0] + to_eye[1] * to_eye[1] + to_eye[2] * to_eye[2]))
            return dot / (normal_len * view_len)
        except Exception:
            return 0.0

    def _projected_mesh_bounds(self, node, width: int, height: int):
        world_verts = self._renderer._get_world_verts_for_node(node)
        if not world_verts:
            return None
        projected = self._renderer._proj_batch(world_verts, width, height)
        visible = [p for p in projected if p is not None]
        if not visible:
            return None
        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        return (min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4, world_verts, projected)

    def _mesh_hit_test(self, sx: int, sy: int):
        detail = self._mesh_hit_test_detail(sx, sy)
        return detail[0] if detail is not None else None

    def _mesh_subobject_hit_test(self, sx: int, sy: int):
        mesh = self._active_edit_mesh()
        topology = self._active_topology()
        if mesh is None or topology is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            bounds = self._projected_mesh_bounds(mesh, width, height)
        except Exception:
            bounds = None
        if bounds is None:
            return None
        _min_x, _min_y, _max_x, _max_y, _world_verts, projected = bounds
        mode = self.mesh_selection_state.mode
        if mode is MeshSelectionMode.VERTEX:
            best = self._nearest_projected_vertex(projected, sx, sy)
            return ("vertex", best) if best is not None else None
        if mode in (MeshSelectionMode.EDGE, MeshSelectionMode.BORDER):
            best_edge = self._nearest_projected_edge(projected, topology.edges, sx, sy)
            if best_edge is None:
                return None
            if mode is MeshSelectionMode.BORDER:
                if best_edge not in topology.border_edges:
                    self.mesh_selection_state.status_message = "Selected edge is not an open border edge."
                    self._emit_mesh_subobject_selection()
                    return None
                border_idx = topology.border_index_for_edge(best_edge)
                return ("border", border_idx) if border_idx is not None else None
            return ("edge", best_edge)
        if mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON, MeshSelectionMode.ELEMENT):
            face_idx = self._projected_face_hit(topology, projected, sx, sy)
            if face_idx is None:
                return None
            if mode is MeshSelectionMode.ELEMENT:
                element_idx = select_element_for_face(topology, face_idx)
                return ("element", element_idx) if element_idx is not None else None
            return ("face", face_idx)
        return None

    def _apply_mesh_subobject_hit(self, hit, modifiers) -> bool:
        if hit is None:
            return False
        kind, value = hit
        state = self.mesh_selection_state
        additive = bool(modifiers & QtCore.Qt.ShiftModifier)
        toggle = bool(modifiers & QtCore.Qt.ControlModifier)

        def update_set(target: set, item) -> set:
            new_values = set(target) if additive or toggle else set()
            if toggle and item in new_values:
                new_values.remove(item)
            else:
                new_values.add(item)
            return new_values

        if kind == "vertex":
            state.selected_vertices = update_set(state.selected_vertices, int(value))
        elif kind == "edge":
            state.selected_edges = update_set(state.selected_edges, normalize_edge(*value))
        elif kind == "border":
            state.selected_borders = update_set(set(state.selected_borders), int(value))
        elif kind == "face":
            if state.mode is MeshSelectionMode.POLYGON:
                state.selected_polygons = update_set(state.selected_polygons, int(value))
                state.status_message = "Polygon Mode is using individual faces for this triangulated mesh."
            else:
                state.selected_faces = update_set(state.selected_faces, int(value))
        elif kind == "element":
            state.selected_elements = update_set(state.selected_elements, int(value))
        else:
            return False
        self._emit_mesh_subobject_selection()
        self._request_render()
        return True

    def _nearest_projected_vertex(self, projected, sx: int, sy: int, radius: float = 12.0) -> int | None:
        best = None
        best_dist = radius * radius
        for idx, point in enumerate(projected):
            if point is None:
                continue
            dx = float(point[0]) - sx
            dy = float(point[1]) - sy
            dist = dx * dx + dy * dy
            if dist <= best_dist:
                best_dist = dist
                best = idx
        return best

    def _nearest_projected_edge(self, projected, edges, sx: int, sy: int, radius: float = 10.0):
        best = None
        best_dist = radius * radius
        for edge in edges:
            p0, p1 = projected[edge[0]], projected[edge[1]]
            if p0 is None or p1 is None:
                continue
            dist = self._point_segment_dist2(float(sx), float(sy), float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1]))
            if dist <= best_dist:
                best_dist = dist
                best = normalize_edge(*edge)
        return best

    @staticmethod
    def _point_segment_dist2(px, py, ax, ay, bx, by) -> float:
        dx = bx - ax
        dy = by - ay
        denom = dx * dx + dy * dy
        if denom <= 1e-12:
            return (px - ax) * (px - ax) + (py - ay) * (py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        cx = ax + t * dx
        cy = ay + t * dy
        return (px - cx) * (px - cx) + (py - cy) * (py - cy)

    def _projected_face_hit(self, topology: MeshTopology, projected, sx: int, sy: int) -> int | None:
        best = None
        best_depth = float("inf")
        for fi, face in enumerate(topology.faces):
            try:
                p0, p1, p2 = projected[face[0]], projected[face[1]], projected[face[2]]
                if p0 is None or p1 is None or p2 is None:
                    continue
                if not self._point_in_triangle(sx, sy, p0, p1, p2):
                    continue
                depth = (p0[2] + p1[2] + p2[2]) / 3.0
                if depth < best_depth:
                    best_depth = depth
                    best = fi
            except Exception:
                continue
        return best

    @staticmethod
    def _ray_triangle_intersection(origin, direction, v0, v1, v2) -> float | None:
        eps = 1.0e-8
        ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
        dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])
        ax, ay, az = float(v0[0]), float(v0[1]), float(v0[2])
        bx, by, bz = float(v1[0]), float(v1[1]), float(v1[2])
        cx, cy, cz = float(v2[0]), float(v2[1]), float(v2[2])

        e1x, e1y, e1z = bx - ax, by - ay, bz - az
        e2x, e2y, e2z = cx - ax, cy - ay, cz - az
        px, py, pz = dy * e2z - dz * e2y, dz * e2x - dx * e2z, dx * e2y - dy * e2x
        det = e1x * px + e1y * py + e1z * pz
        if abs(det) < eps:
            return None
        inv_det = 1.0 / det
        tx, ty, tz = ox - ax, oy - ay, oz - az
        u = (tx * px + ty * py + tz * pz) * inv_det
        if u < -eps or u > 1.0 + eps:
            return None
        qx, qy, qz = ty * e1z - tz * e1y, tz * e1x - tx * e1z, tx * e1y - ty * e1x
        v = (dx * qx + dy * qy + dz * qz) * inv_det
        if v < -eps or u + v > 1.0 + eps:
            return None
        t = (e2x * qx + e2y * qy + e2z * qz) * inv_det
        return t if t > eps else None

    def _mesh_hit_test_detail(self, sx: int, sy: int):
        if self.model is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        best = None
        best_face_bounds = None
        best_t = float("inf")
        try:
            ray_origin, ray_direction = ray_from_mouse((sx, sy), self.camera, width, height)
        except Exception:
            ray_origin = ray_direction = None
        try:
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = []
        for node in nodes:
            if getattr(node, "_gr_hidden", False):
                continue
            try:
                bounds = self._projected_mesh_bounds(node, width, height)
                if bounds is None:
                    continue
                min_x, min_y, max_x, max_y, world_verts, projected = bounds
                if sx < min_x or sx > max_x or sy < min_y or sy > max_y:
                    continue
                for face in getattr(node, "faces", []) or []:
                    try:
                        i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                        if i0 < 0 or i1 < 0 or i2 < 0:
                            continue
                        v0, v1, v2 = world_verts[i0], world_verts[i1], world_verts[i2]
                        hit_t = (
                            self._ray_triangle_intersection(ray_origin, ray_direction, v0, v1, v2)
                            if ray_origin is not None and ray_direction is not None
                            else None
                        )
                        if hit_t is None:
                            p0, p1, p2 = projected[i0], projected[i1], projected[i2]
                            if p0 is None or p1 is None or p2 is None:
                                continue
                            if not self._point_in_triangle(sx, sy, p0, p1, p2):
                                continue
                            hit_t = max(1.0e-6, (p0[2] + p1[2] + p2[2]) / 3.0)
                        if hit_t >= best_t:
                            continue
                        best_t = hit_t
                        best = node
                        best_face_bounds = self._bounds_from_points(
                            [world_verts[i0], world_verts[i1], world_verts[i2]],
                            min_extent=0.05,
                        )
                    except Exception:
                        continue
            except Exception:
                continue
        if best is None:
            return None
        return best, best_face_bounds

    def _pick_reference_hit_test(self, sx: int, sy: int):
        camera_node = self._camera_hit_test(sx, sy)
        if camera_node is not None:
            return camera_node
        light_node = self._light_hit_test(sx, sy)
        if light_node is not None:
            return light_node
        mesh_hit = self._mesh_hit_test_detail(sx, sy)
        if mesh_hit is None:
            return None
        node = mesh_hit[0]
        return self._scene_root_for_node(node) or node

    def _light_hit_test(self, sx: int, sy: int, radius: int = 12):
        if self.model is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        self._light_picker.max_screen_distance = int(radius)
        return self._light_picker.hit_test(
            nodes,
            sx,
            sy,
            width,
            height,
            self._renderer._proj,
            self._renderer._node_world_transform,
        )

    def _camera_hit_test(self, sx: int, sy: int, radius: int = 14):
        if self.model is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        self._camera_picker.max_screen_distance = int(radius)
        hit = self._camera_picker.hit_test(
            self.camera_manager.get_all_cameras(),
            sx,
            sy,
            width,
            height,
            self._renderer._proj,
        )
        if not hit:
            return None
        camera, kind = hit
        if kind == "target":
            node = getattr(camera, "original_ref", None)
            if node is not None:
                setattr(node, "_gr_camera_target_handle", True)
        return getattr(camera, "original_ref", None)

    def _set_mesh_hidden(self, node, hidden: bool) -> None:
        if node is None:
            return
        setattr(node, "_gr_hidden", bool(hidden))
        if hidden and self._renderer.selected_node is node:
            self.set_selected_node(None)
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node_cache()
        self.meshVisibilityChanged.emit()
        self._request_render()

    def _set_selected_meshes_hidden(self, hidden: bool) -> None:
        nodes = list(self._selected_meshes)
        if not nodes:
            return
        changed = False
        for node in nodes:
            before = bool(getattr(node, "_gr_hidden", False))
            setattr(node, "_gr_hidden", bool(hidden))
            changed = changed or before != bool(hidden)
        if changed:
            if self._gpu_renderer is not None:
                self._gpu_renderer.invalidate_node_cache()
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _hide_unselected_meshes(self) -> None:
        selected_ids = {id(node) for node in self._selected_meshes}
        changed = False
        try:
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = []
        for node in nodes:
            if id(node) in selected_ids:
                continue
            if not getattr(node, "_gr_hidden", False):
                setattr(node, "_gr_hidden", True)
                changed = True
        if changed:
            if self._gpu_renderer is not None:
                self._gpu_renderer.invalidate_node_cache()
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _unhide_all_meshes(self) -> None:
        changed = False
        for node in self._all_geometry_nodes():
            if getattr(node, "_gr_hidden", False):
                setattr(node, "_gr_hidden", False)
                changed = True
        if changed:
            if self._gpu_renderer is not None:
                self._gpu_renderer.invalidate_node_cache()
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _store_selected_mesh_names(self, attr: str, title: str) -> None:
        nodes = [node for node in self._selected_meshes if self._is_selectable_mesh_node(node)]
        if self.model is None or not nodes:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, title, "Name:")
        if not ok or not name.strip():
            return
        store = getattr(self.model, attr, None)
        if store is None:
            store = {}
            setattr(self.model, attr, store)
        group_name = name.strip()
        store[group_name] = [str(getattr(node, "name", "") or "<mesh>") for node in nodes]
        if attr == "_gr_mesh_groups":
            for node in nodes:
                setattr(node, "_gr_mesh_group", group_name)
            self.meshVisibilityChanged.emit()

    def _mesh_nodes_in_rect(self, rect: QtCore.QRect) -> list:
        if self.model is None:
            return []
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = []
        selected = []
        norm_rect = rect.normalized()
        for node in nodes:
            if getattr(node, "_gr_hidden", False):
                continue
            try:
                bounds = self._projected_mesh_bounds(node, width, height)
                if bounds is None:
                    continue
                min_x, min_y, max_x, max_y, _world_verts, _projected = bounds
                mesh_rect = QtCore.QRect(
                    QtCore.QPoint(int(min_x), int(min_y)),
                    QtCore.QPoint(int(max_x), int(max_y)),
                ).normalized()
                if norm_rect.intersects(mesh_rect):
                    selected.append(node)
            except Exception:
                continue
        return selected

    def _show_mesh_context_menu(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        node = self._mesh_hit_test(x, y)
        selected_ids = {id(mesh) for mesh in self._selected_meshes}
        if node is not None and id(node) not in selected_ids:
            return
        menu = QtWidgets.QMenu(self)
        multi = len(self._selected_meshes) > 1
        hide_action = menu.addAction("Hide Selected" if multi else "Hide Mesh")
        unhide_action = menu.addAction("Unhide Selected" if multi else "Unhide Mesh")
        menu.addSeparator()
        hide_unselected_action = menu.addAction("Hide Unselected")
        unhide_all_action = menu.addAction("Unhide All")
        menu.addSeparator()
        selection_set_action = menu.addAction("Create Selection Set...")
        mesh_group_action = menu.addAction("Create Mesh Group...")
        hide_action.setEnabled(any(not getattr(mesh, "_gr_hidden", False) for mesh in self._selected_meshes))
        unhide_action.setEnabled(any(getattr(mesh, "_gr_hidden", False) for mesh in self._selected_meshes))
        hide_unselected_action.setEnabled(self.model is not None)
        unhide_all_action.setEnabled(self.model is not None)
        selection_set_action.setEnabled(bool(self._selected_meshes))
        mesh_group_action.setEnabled(bool(self._selected_meshes))
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is hide_action:
            self._set_selected_meshes_hidden(True)
        elif chosen is unhide_action:
            self._set_selected_meshes_hidden(False)
        elif chosen is hide_unselected_action:
            self._hide_unselected_meshes()
        elif chosen is unhide_all_action:
            self._unhide_all_meshes()
        elif chosen is selection_set_action:
            self._store_selected_mesh_names("_gr_selection_sets", "Selection Set")
        elif chosen is mesh_group_action:
            self._store_selected_mesh_names("_gr_mesh_groups", "Mesh Group")

    def _update_gizmo_hover(self, event) -> None:
        if not self._ensure_renderer_gimbal_state() or self._active_gizmo_node() is None:
            if self._transform_gizmo.hovered_handle is not None:
                self._transform_gizmo.hovered_handle = None
                self._request_render(fast=True)
            return
        x, y = int(event.position().x()), int(event.position().y())
        before = self._transform_gizmo.hovered_handle
        handle = self._transform_gizmo.hit_test((x, y), self.camera)
        if handle != before:
            self._request_render(fast=True)

    def _update_mesh_hover(self, event) -> None:
        if self.model is None:
            if self._hovered_mesh_node is not None:
                self._hovered_mesh_node = None
                self._hovered_mesh_face_bounds = None
                self._request_render(fast=True)
            return
        if self._transform_gizmo.hovered_handle or self._measurement_mode:
            return
        x, y = int(event.position().x()), int(event.position().y())
        hit = self._mesh_hit_test_detail(x, y)
        node = hit[0] if hit is not None else None
        face_bounds = hit[1] if hit is not None else None
        if node is self._hovered_mesh_node and face_bounds == self._hovered_mesh_face_bounds:
            return
        self._hovered_mesh_node = node
        self._hovered_mesh_face_bounds = face_bounds
        self._request_render(fast=True)

    def _begin_transform_gizmo_drag(self, x: int, y: int) -> bool:
        node = self._active_gizmo_node()
        if not self._ensure_renderer_gimbal_state() or node is None:
            return False
        if bool(getattr(node, "_gr_camera_locked", False)):
            return False
        if bool(getattr(node, "_gr_scene_object_locked", False)):
            self.statusMessage.emit("Selected object is locked.")
            return False
        try:
            wp = self._gizmo_world_position(node)
            setattr(node, "_gr_gizmo_world_position", wp)
        except Exception:
            pass
        self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)
        handle = self._transform_gizmo.hit_test((x, y), self.camera)
        if not handle:
            return False
        self._transform_gizmo_dragging = True
        self._gimbal_dragging = False
        self._transform_gizmo.begin_drag(handle, (x, y), self.camera)
        self._renderer.is_interactive = True
        self._request_render(fast=True)
        return True

    def _cancel_transform_gizmo_drag(self) -> None:
        self._transform_gizmo.cancel_drag()
        self._transform_gizmo_dragging = False
        self._renderer.is_interactive = False
        self._renderer._wt_cache.clear()
        self._request_render()

    def _commit_transform_gizmo_drag(self) -> None:
        before, after, node = self._transform_gizmo.end_drag()
        self._transform_gizmo_dragging = False
        self._renderer.is_interactive = False
        self._renderer._wt_cache.clear()
        if node is not None and before is not None and after is not None:
            self._commit_node_transform(
                node,
                before.position,
                before.rotation,
                after.position,
                after.rotation,
                f"Gizmo {self._transform_gizmo.mode.value.title()}",
                before_vertices=before.vertices,
                after_vertices=after.vertices,
                before_scale=before.scale,
                after_scale=after.scale,
                before_pivot_world=before.pivot_world,
                after_pivot_world=after.pivot_world,
                before_pivot_rotation=before.pivot_rotation,
                after_pivot_rotation=after.pivot_rotation,
            )
            self._notify_node_moved(node)
        self._request_render()

    def _press_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        self._mx = self._press_x = x
        self._my = self._press_y = y
        self._is_dragging = False
        self._gimbal_dragging = False
        self._joint_dragging = False
        self._joint_drag_node = None
        self._joint_drag_mirror_node = None
        self._joint_drag_nodes = []
        self._joint_drag_mirror_nodes = []
        self._joint_drag_start_positions = {}
        self._joint_marquee_selecting = False
        self._joint_marquee_start = (x, y)
        self._joint_marquee_current = (x, y)
        self._mesh_box_start = None
        self._mesh_box_selecting = False
        if hasattr(self, "_selection_rubber_band"):
            self._selection_rubber_band.hide()

        if self._begin_transform_gizmo_drag(x, y):
            return

        # ── T402: Prefer joint-dot click over plain bone hit-test ──────
        # The dots are painted on top of the bone markers, so a click
        # within their hit-radius should select the same joint AND arm
        # a translate-drag.  The drag activates lazily on cursor motion
        # past `_drag_threshold` so simple clicks still behave as
        # selection-only (matching AccuRig).
        if self._renderer.show_bones and self._joint_dot_enabled:
            joint_node = self._joint_dot_hit_test(x, y)
            if joint_node is not None:
                modifiers = event.modifiers()
                if modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                    self._toggle_selected_joint_node(joint_node)
                    self._renderer._hovered_bone = joint_node
                    self._request_render()
                    return
                self._joint_drag_node = joint_node
                if len(self._selected_joint_nodes) > 1 and any(n is joint_node for n in self._selected_joint_nodes):
                    self._joint_drag_nodes = list(self._selected_joint_nodes)
                    self._joint_drag_mirror_node = None
                else:
                    self._joint_drag_nodes = [joint_node]
                selected_ids = {id(n) for n in self._joint_drag_nodes}
                self._joint_drag_mirror_nodes = []
                if self._joint_symmetry_enabled:
                    for drag_node in self._joint_drag_nodes:
                        partner = self._joint_mirror_partner(drag_node)
                        if partner is not None and id(partner) not in selected_ids:
                            selected_ids.add(id(partner))
                            self._joint_drag_mirror_nodes.append(partner)
                self._joint_drag_mirror_node = (
                    self._joint_drag_mirror_nodes[0]
                    if self._joint_drag_mirror_nodes else None
                )
                self._joint_drag_start_screen = (x, y)
                try:
                    self._joint_drag_start_pos = tuple(joint_node.position)
                except Exception:
                    self._joint_drag_start_pos = (0.0, 0.0, 0.0)
                self._joint_drag_start_positions = {}
                for drag_node in self._joint_drag_nodes:
                    try:
                        self._joint_drag_start_positions[id(drag_node)] = tuple(drag_node.position)
                    except Exception:
                        self._joint_drag_start_positions[id(drag_node)] = (0.0, 0.0, 0.0)
                if self._joint_drag_mirror_node is not None:
                    for mirror_node in self._joint_drag_mirror_nodes:
                        try:
                            self._joint_drag_start_positions[id(mirror_node)] = tuple(
                                mirror_node.position
                            )
                        except Exception:
                            self._joint_drag_start_positions[id(mirror_node)] = (0.0, 0.0, 0.0)
                    self._joint_drag_mirror_start_pos = self._joint_drag_start_positions.get(
                        id(self._joint_drag_mirror_node),
                        (0.0, 0.0, 0.0),
                    )
                else:
                    self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
                # Cache the screen→world conversion factor at the joint's
                # depth so the drag-translate math feels consistent
                # regardless of camera distance.
                try:
                    w = self.canvas.width() or 800
                    h = self.canvas.height() or 600
                    if self._is_external_skeleton_node(joint_node):
                        wp = self._external_overlay_world_position(joint_node)
                    else:
                        wp, _, _ = self._renderer._node_world_transform(joint_node)
                    proj = self._renderer._proj(*wp, w, h)
                    dist = max(0.5, proj[2] if proj else 1.0)
                    self._joint_drag_world_per_px = (
                        2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)
                    ) / max(h, 1)
                except Exception:
                    self._joint_drag_world_per_px = 0.01
                self._renderer._hovered_bone = joint_node
                self._request_render()
                return

        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(x, y)
            if node:
                self._renderer._hovered_bone = node
                self._request_render()
                return

        if self._renderer.show_bones and self._joint_dot_enabled:
            self._joint_marquee_selecting = True
            self._joint_marquee_start = (x, y)
            self._joint_marquee_current = (x, y)
            self._request_render()
            return
        self._mesh_box_start = QtCore.QPoint(x, y)

    def _drag_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._transform_gizmo_dragging:
            self._transform_gizmo.drag((x, y), self.camera, self.canvas.height())
            node = getattr(self._renderer, "selected_node", None)
            if node is not None:
                self._notify_node_moved(node)
            self._request_render(fast=True)
            return
        if self._gimbal_dragging and self._renderer.selected_node:
            if (
                self._snap_key_down
                and self._renderer.gimbal_mode == 1
                and self._selection_targets_external_skeleton(
                    self._selected_joint_nodes or [self._renderer.selected_node]
                )
                and self._snap_selected_external_bones_to_imported_at_cursor(x, y)
            ):
                self._request_render(fast=True)
                return
            self._apply_gimbal_drag(x, y)
            self._notify_node_moved(self._renderer.selected_node)
            self._request_render(fast=True)
            return

        # ── T402: Joint-dot drag translation ────────────────────────────
        # Activate joint drag the moment the cursor leaves the click slop
        # circle, then keep translating the primary node (and its mirror
        # partner, if symmetry is on) per screen→world delta.
        if self._joint_drag_node is not None:
            sx0, sy0 = self._joint_drag_start_screen
            if not self._joint_dragging:
                if (
                    abs(x - sx0) > self._drag_threshold
                    or abs(y - sy0) > self._drag_threshold
                ):
                    self._joint_dragging = True
                    self._renderer.is_interactive = True
            if self._joint_dragging:
                self._apply_joint_drag(x, y)
                self._request_render(fast=True)
            return

        if self._joint_marquee_selecting:
            self._joint_marquee_current = (x, y)
            if not self._is_dragging:
                if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                    self._is_dragging = True
            self._request_render(fast=True)
            return

        if not self._is_dragging:
            if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                self._is_dragging = True
                self._renderer._hovered_bone = None
        if self._is_dragging:
            self._mx, self._my = x, y
            if self._mesh_box_start is not None:
                self._mesh_box_selecting = True
                rect = QtCore.QRect(self._mesh_box_start, QtCore.QPoint(x, y)).normalized()
                self._selection_rubber_band.setGeometry(rect)
                self._selection_rubber_band.show()

    def _release_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._transform_gizmo_dragging:
            self._commit_transform_gizmo_drag()
            return
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            node = self._renderer.selected_node
            if node is not None:
                if (
                    not self._is_selected_model_root(node)
                    and len(self._selected_joint_nodes) > 1
                    and any(n is node for n in self._selected_joint_nodes)
                    and self._renderer.gimbal_mode == 1
                ):
                    for sel_node in self._selected_joint_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(sel_node),
                            tuple(sel_node.position),
                        )
                        self._commit_node_transform(
                            sel_node,
                            before_pos,
                            tuple(sel_node.rotation),
                            tuple(sel_node.position),
                            tuple(sel_node.rotation),
                            "Gimbal Multi-Joint Translate",
                        )
                        self._notify_node_moved(sel_node)
                    for mirror_node in self._gimbal_joint_mirror_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(mirror_node),
                            tuple(mirror_node.position),
                        )
                        self._commit_node_transform(
                            mirror_node,
                            before_pos,
                            tuple(mirror_node.rotation),
                            tuple(mirror_node.position),
                            tuple(mirror_node.rotation),
                            "Gimbal Multi-Joint Translate (mirror)",
                        )
                        self._notify_node_moved(mirror_node)
                elif not self._is_selected_model_root(node):
                    self._commit_node_transform(
                        node,
                        self._gimbal_node_start_pos,
                        self._gimbal_node_start_rot,
                        tuple(node.position),
                        tuple(node.rotation),
                        "Gimbal Transform",
                    )
                    self._notify_node_moved(node)
                    for mirror_node in self._gimbal_joint_mirror_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(mirror_node),
                            tuple(mirror_node.position),
                        )
                        self._commit_node_transform(
                            mirror_node,
                            before_pos,
                            tuple(mirror_node.rotation),
                            tuple(mirror_node.position),
                            tuple(mirror_node.rotation),
                            "Gimbal Transform (mirror)",
                        )
                        self._notify_node_moved(mirror_node)
            self._request_render()
            return

        # ── T402: Joint-drag release ─────────────────────────────────────
        # Two modes:
        #   • If the user dragged → commit the translation (and its mirror)
        #     onto the undo stack with one "Joint Translate" entry, then
        #     keep the joint selected as the active node.
        #   • If the user just clicked (no drag) → treat as selection-only.
        if self._joint_drag_node is not None:
            joint = self._joint_drag_node
            mirror = self._joint_drag_mirror_node
            mirror_nodes = list(self._joint_drag_mirror_nodes)
            was_dragging = self._joint_dragging
            self._joint_dragging = False
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            if was_dragging:
                try:
                    for moved in self._joint_drag_nodes or [joint]:
                        start_pos = self._joint_drag_start_positions.get(
                            id(moved),
                            self._joint_drag_start_pos if moved is joint else tuple(moved.position),
                        )
                        self._commit_node_transform(
                            moved,
                            start_pos,
                            tuple(moved.rotation),
                            tuple(moved.position),
                            tuple(moved.rotation),
                            "Joint Translate",
                        )
                        self._notify_node_moved(moved)
                    for mirror in mirror_nodes:
                        mirror_start = self._joint_drag_start_positions.get(
                            id(mirror),
                            self._joint_drag_mirror_start_pos,
                        )
                        self._commit_node_transform(
                            mirror,
                            mirror_start,
                            tuple(mirror.rotation),
                            tuple(mirror.position),
                            tuple(mirror.rotation),
                            "Joint Translate (mirror)",
                        )
                        self._notify_node_moved(mirror)
                except Exception as exc:
                    log.debug("Joint-drag commit failed: %s", exc)
            self._joint_drag_node = None
            self._joint_drag_mirror_node = None
            self._joint_drag_nodes = []
            self._joint_drag_mirror_nodes = []
            self._joint_drag_start_positions = {}
            # Click-or-drag: always finish by selecting the joint so the
            # inspector reflects the user's intent.
            if was_dragging and self._selected_joint_nodes:
                self._set_selected_joint_nodes(self._selected_joint_nodes, primary=joint)
            else:
                self.set_selected_node(joint)
            if self.on_bone_selected:
                self.on_bone_selected(joint)
            self._renderer._hovered_bone = None
            self._request_render()
            return

        if self._joint_marquee_selecting:
            self._joint_marquee_selecting = False
            self._renderer.is_interactive = False
            if self._is_dragging:
                nodes = self._joint_nodes_in_rect(
                    self._joint_marquee_start[0],
                    self._joint_marquee_start[1],
                    x,
                    y,
                )
                self._set_selected_joint_nodes(nodes)
                if self.on_bone_selected:
                    self.on_bone_selected(self._renderer.selected_node)
                self._is_dragging = False
                self._request_render()
                return
            self._request_render()

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False
        if self._is_dragging:
            if self._mesh_box_selecting and self._mesh_box_start is not None:
                rect = QtCore.QRect(self._mesh_box_start, QtCore.QPoint(x, y)).normalized()
                self._selection_rubber_band.hide()
                nodes = self._mesh_nodes_in_rect(rect)
                if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                    current_ids = {id(node) for node in self._selected_meshes}
                    nodes = list(self._selected_meshes) + [node for node in nodes if id(node) not in current_ids]
                self.set_selected_meshes(nodes)
                self._mesh_box_start = None
                self._mesh_box_selecting = False
                self._is_dragging = False
                return
            if hasattr(self, "_selection_rubber_band"):
                self._selection_rubber_band.hide()
            self._mesh_box_start = None
            self._mesh_box_selecting = False
            self._is_dragging = False
            self._request_render()
            return

        if self._pick_reference_waiting:
            target = self._pick_reference_hit_test(x, y)
            if target is not None:
                self.transform_reference_controller.resolve_pick_reference(target)
                self._pick_reference_waiting = False
                label = str(getattr(target, "_gr_scene_object_name", getattr(target, "name", "Object")) or "Object")
                if hasattr(self, "axis_mode_control"):
                    self.axis_mode_control.set_axis_mode(AxisMode.PICK, label=f"Pick: {label[:24]}")
                self.statusMessage.emit(f"Transform reference picked: {label}")
                self._request_render(fast=True)
            else:
                self.statusMessage.emit("Pick an object to use as transform reference.")
            return

        if self._renderer.show_bones:
            # T402: joint-dot hit-test takes priority over the underlying
            # bone hit-test so clicks on a dot always select the right node.
            node = (
                self._joint_dot_hit_test(x, y)
                if self._joint_dot_enabled
                else None
            )
            if node is None:
                node = self._renderer.hit_test_bone(x, y)
            if node:
                self.set_selected_node(node)
                if self.on_bone_selected:
                    self.on_bone_selected(node)
                return
        if self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self._apply_mesh_subobject_hit(
                self._mesh_subobject_hit_test(x, y),
                event.modifiers(),
            ):
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
        camera_node = self._camera_hit_test(x, y)
        if camera_node is not None:
            if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                camera = self.camera_manager.find_by_original(camera_node)
                if camera is not None:
                    self.camera_manager.select_camera(camera.id, additive=True)
                    self.cameraSelectionChanged.emit(camera_node)
            self.set_selected_node(camera_node)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        light_node = self._light_hit_test(x, y)
        if light_node is not None:
            self.set_selected_node(light_node)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        mesh_hit = self._mesh_hit_test_detail(x, y)
        if mesh_hit is not None:
            mesh_node, face_bounds = mesh_hit
            self.set_selected_node(mesh_node, orbit_bounds=face_bounds)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        self.set_selected_node(None)
        if self.on_bone_selected:
            self.on_bone_selected(None)

    def _press_pan(self, event) -> None:
        self._pan_dragging = True
        self._mx = int(event.position().x())
        self._my = int(event.position().y())

    def _drag_pan(self, event) -> None:
        if not self._pan_dragging:
            return
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        self.camera.pan(dx, dy, self.canvas.height())
        self._request_render(fast=True)

    def _release_pan(self, event) -> None:
        self._pan_dragging = False
        self._renderer.is_interactive = False
        self._request_render()

    # ── T402: Joint-drag translation math ──────────────────────────────
    def _apply_joint_drag(self, mx: int, my: int) -> None:
        """Translate the drag-target joint (and its mirror) by the
        screen-delta from the press point.

        Movement is performed in the camera's right/up plane (the
        standard 3-axis-free-translate behaviour for joint-dot drags
        in AccuRig).  Depth along the view forward is left untouched —
        joint dots are inherently a 2D screen-space affordance.

        Symmetry: when ``self._joint_symmetry_enabled`` is True and a
        MIRROR_PAIRS partner was identified at press-time, the partner
        joint receives the same delta with the X component negated, so
        L↔R parity is preserved while editing.
        """
        node = self._joint_drag_node
        if node is None:
            return
        try:
            sx0, sy0 = self._joint_drag_start_screen
            dx_screen = mx - sx0
            dy_screen = my - sy0
            wpp = float(self._joint_drag_world_per_px)
            # Camera basis at press time (right/up of view matrix).
            try:
                right, up, _fwd, _eye = self.camera._view_matrix()
            except Exception:
                # Defensive fallback if the camera matrix isn't available
                right = (1.0, 0.0, 0.0)
                up = (0.0, 1.0, 0.0)
            # Screen-space delta → world-space vector.
            #   +x screen drag → +right
            #   +y screen drag → -up   (Qt y axis points down)
            dwx = (dx_screen * right[0] + (-dy_screen) * up[0]) * wpp
            dwy = (dx_screen * right[1] + (-dy_screen) * up[1]) * wpp
            dwz = (dx_screen * right[2] + (-dy_screen) * up[2]) * wpp
            drag_nodes = self._joint_drag_nodes or [node]
            for drag_node in drag_nodes:
                delta = (
                    self._external_world_delta_to_local((dwx, dwy, dwz))
                    if self._is_external_skeleton_node(drag_node)
                    else (dwx, dwy, dwz)
                )
                sp = self._joint_drag_start_positions.get(
                    id(drag_node),
                    self._joint_drag_start_pos if drag_node is node else tuple(drag_node.position),
                )
                drag_node.position = (sp[0] + delta[0], sp[1] + delta[1], sp[2] + delta[2])
                self._evict_transform_cache(drag_node)

            mirror_nodes = list(self._joint_drag_mirror_nodes)
            for mirror in mirror_nodes:
                msp = self._joint_drag_start_positions.get(
                    id(mirror),
                    self._joint_drag_mirror_start_pos,
                )
                mdx, mdy, mdz = (
                    self._external_world_delta_to_local((dwx, dwy, dwz))
                    if self._is_external_skeleton_node(mirror)
                    else (dwx, dwy, dwz)
                )
                # Mirror across the X axis: negate the X component of the
                # translation delta so the partner moves symmetrically.
                mirror.position = (msp[0] - mdx, msp[1] + mdy, msp[2] + mdz)
                self._evict_transform_cache(mirror)
        except Exception as exc:
            log.debug("Joint-drag translation failed: %s", exc)

    def _apply_gimbal_drag(self, mx: int, my: int) -> None:
        node = self._renderer.selected_node
        if not node:
            return
        sx0, sy0 = self._gimbal_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        if self._is_external_skeleton_node(node):
            wp = self._external_overlay_world_position(node)
        else:
            wp, _, _ = self._renderer._node_world_transform(node)
        proj = self._renderer._proj(*wp, w, h)
        dist = max(0.5, proj[2] if proj else 1.0)
        world_per_px = (2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)) / max(h, 1)
        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos
        if self._is_selected_model_root(node):
            self._apply_model_gimbal_drag(
                dx_screen,
                dy_screen,
                world_per_px,
                axis,
                wp,
            )
            return

        if self._renderer.gimbal_mode == 1:
            def axis_delta(axis_name: str):
                return self._projected_axis_delta(
                    axis_name,
                    wp,
                    dx_screen,
                    dy_screen,
                    world_per_px,
                )

            if len(axis) == 1:
                d = axis_delta(axis)
            else:
                d1 = axis_delta(axis[0])
                d2 = axis_delta(axis[1])
                d = (d1[0] + d2[0], d1[1] + d2[1], d1[2] + d2[2])
            if any(n is node for n in self._selected_joint_nodes) and len(self._selected_joint_nodes) > 1:
                for sel_node in self._selected_joint_nodes:
                    sp = self._gimbal_joint_start_positions.get(id(sel_node), tuple(sel_node.position))
                    delta = (
                        self._external_world_delta_to_local(d)
                        if self._is_external_skeleton_node(sel_node)
                        else d
                    )
                    sel_node.position = (sp[0] + delta[0], sp[1] + delta[1], sp[2] + delta[2])
                    self._evict_transform_cache(sel_node)
            else:
                delta = self._external_world_delta_to_local(d) if self._is_external_skeleton_node(node) else d
                node.position = (start[0] + delta[0], start[1] + delta[1], start[2] + delta[2])
            for mirror_node in self._gimbal_joint_mirror_nodes:
                sp = self._gimbal_joint_start_positions.get(id(mirror_node), tuple(mirror_node.position))
                delta = (
                    self._external_world_delta_to_local(d)
                    if self._is_external_skeleton_node(mirror_node)
                    else d
                )
                mirror_node.position = (sp[0] - delta[0], sp[1] + delta[1], sp[2] + delta[2])
                self._evict_transform_cache(mirror_node)
        elif self._renderer.gimbal_mode == 2:
            angle = dx_screen * 0.01
            angle = self.angle_snap.snap_radians(angle)
            ha = angle * 0.5
            c, s = math.cos(ha), math.sin(ha)
            rq = {"X": (s, 0.0, 0.0, c), "Y": (0.0, s, 0.0, c)}.get(axis, (0.0, 0.0, s, c))
            ax, ay, az, aw = rq
            bx, by, bz, bw = self._gimbal_node_start_rot
            new_rot = (
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            )
            ll = math.sqrt(sum(v * v for v in new_rot))
            if ll > 1e-9:
                node.rotation = tuple(v / ll for v in new_rot)

        self._evict_transform_cache(node)

    def _is_selected_model_root(self, node) -> bool:
        return bool(
            self.model is not None
            and (
                node is getattr(self.model, "root_node", None)
                or bool(getattr(node, "_gr_scene_object_root", False))
            )
        )

    def _model_gimbal_axis_delta(
        self,
        axis_name: str,
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
        origin_world: tuple[float, float, float] | None = None,
    ) -> tuple[float, float, float]:
        if origin_world is not None:
            return self._projected_axis_delta(
                axis_name,
                origin_world,
                dx_screen,
                dy_screen,
                world_per_px,
            )
        right, up, _fwd, _eye = self.camera._view_matrix()
        w_dir = self._gimbal_world_axis(axis_name)
        sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
        sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
        ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
        if ll < 1e-6:
            return (0.0, 0.0, 0.0)
        delta = ((dx_screen * sc_x + (-dy_screen) * sc_y) / ll) * world_per_px
        return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

    def _apply_model_gimbal_drag(
        self,
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
        axis: str,
        origin_world: tuple[float, float, float] | None = None,
    ) -> None:
        if self.model is None:
            return
        mode = int(getattr(self._renderer, "gimbal_mode", 1) or 1)
        translation_delta = (0.0, 0.0, 0.0)
        rotation_delta = (0.0, 0.0, 0.0)
        scale_delta = 1.0

        if mode == 1:
            if len(axis) == 1:
                target = self._model_gimbal_axis_delta(
                    axis,
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
            else:
                d1 = self._model_gimbal_axis_delta(
                    axis[0],
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
                d2 = self._model_gimbal_axis_delta(
                    axis[1],
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
                target = (d1[0] + d2[0], d1[1] + d2[1], d1[2] + d2[2])
            prev = self._gimbal_model_applied_translation
            translation_delta = tuple(target[i] - prev[i] for i in range(3))
            self._gimbal_model_applied_translation = target
        elif mode == 2:
            angle = dx_screen * 0.01
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                deg = round(math.degrees(angle) / 10.0) * 10.0
                angle = math.radians(deg)
            delta_angle = angle - float(self._gimbal_model_applied_rotation or 0.0)
            self._gimbal_model_applied_rotation = angle
            deg_delta = math.degrees(delta_angle)
            if axis == "X":
                rotation_delta = (deg_delta, 0.0, 0.0)
            elif axis == "Y":
                rotation_delta = (0.0, deg_delta, 0.0)
            else:
                rotation_delta = (0.0, 0.0, deg_delta)
        elif mode == 3:
            target_scale = max(0.01, min(100.0, math.exp(dx_screen * 0.006)))
            prev_scale = max(0.01, float(self._gimbal_model_applied_scale or 1.0))
            scale_delta = target_scale / prev_scale
            self._gimbal_model_applied_scale = target_scale

        if (
            abs(scale_delta - 1.0) < 1e-6
            and all(abs(v) < 1e-6 for v in translation_delta)
            and all(abs(v) < 1e-6 for v in rotation_delta)
        ):
            return
        try:
            try:
                from core.qt_core.characters import headless_body_workflow as _wf
            except ImportError:                              # pragma: no cover
                from src.core.qt_core.characters import headless_body_workflow as _wf  # type: ignore
            result = _wf.apply_external_model_fit_adjustment(
                self.model,
                rotation_delta_degrees=rotation_delta,
                scale_delta=scale_delta,
                translation_delta=translation_delta,
            )
            if bool(result.get("ok")):
                self.refresh_model_geometry()
                root_node = getattr(self.model, "root_node", None)
                if root_node is not None:
                    self._renderer.selected_node = root_node
        except Exception as exc:
            log.debug("Model gimbal transform failed: %s", exc)

    def _hit_test_model_bounds(self, sx: int, sy: int) -> bool:
        if self.model is None:
            return False
        try:
            bb_min, bb_max = self._renderer._get_render_bounds()
            w = self.canvas.width() or 800
            h = self.canvas.height() or 600
            points = []
            for x in (bb_min[0], bb_max[0]):
                for y in (bb_min[1], bb_max[1]):
                    for z in (bb_min[2], bb_max[2]):
                        sp = self._renderer._proj(float(x), float(y), float(z), w, h)
                        if sp is not None:
                            points.append(sp)
            if not points:
                return False
            min_x = min(p[0] for p in points) - 12
            max_x = max(p[0] for p in points) + 12
            min_y = min(p[1] for p in points) - 12
            max_y = max(p[1] for p in points) + 12
            return min_x <= sx <= max_x and min_y <= sy <= max_y
        except Exception:
            return False

    def _draw_hovered_mesh_outline(self, draw, w: int, h: int) -> None:
        node = getattr(self, "_hovered_mesh_node", None)
        if node is None or getattr(node, "_gr_hidden", False):
            return
        try:
            bounds = self._projected_mesh_bounds(node, w, h)
            if bounds is None:
                return
            _min_x, _min_y, _max_x, _max_y, world_verts, projected = bounds
            faces = list(getattr(node, "faces", []) or [])
            if not faces:
                return

            edge_faces: dict[tuple[int, int], list[bool]] = {}
            for face in faces:
                try:
                    i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                    if i0 < 0 or i1 < 0 or i2 < 0:
                        continue
                    if i0 >= len(projected) or i1 >= len(projected) or i2 >= len(projected):
                        continue
                    if projected[i0] is None or projected[i1] is None or projected[i2] is None:
                        continue
                    front = self._front_facing_score(world_verts, (i0, i1, i2)) >= 0.0
                    for a, b in ((i0, i1), (i1, i2), (i2, i0)):
                        edge_faces.setdefault(normalize_edge(a, b), []).append(front)
                except Exception:
                    continue

            outline_edges = []
            for edge, front_flags in edge_faces.items():
                if len(front_flags) == 1 or (any(front_flags) and not all(front_flags)):
                    p0, p1 = projected[edge[0]], projected[edge[1]]
                    if p0 is not None and p1 is not None:
                        outline_edges.append(((float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))))
            if not outline_edges:
                return
            shadow = (0, 0, 0, 155)
            glow = (0, 215, 181, 230)
            for p0, p1 in outline_edges:
                draw.line([p0, p1], fill=shadow, width=5)
            for p0, p1 in outline_edges:
                draw.line([p0, p1], fill=glow, width=2)
        except Exception as exc:
            log.debug("Hovered mesh outline draw failed: %s", exc)

    def _draw_selected_model_outline(self, draw, w: int, h: int) -> None:
        if self.model is None or not self._is_selected_model_root(getattr(self._renderer, "selected_node", None)):
            self._draw_hovered_mesh_outline(draw, w, h)
            return
        try:
            mesh_nodes = self.model.mesh_nodes() if hasattr(self.model, "mesh_nodes") else []
            points: list[tuple[float, float]] = []
            for node in mesh_nodes:
                if getattr(node, "_gr_hidden", False):
                    continue
                bounds = self._projected_mesh_bounds(node, w, h)
                if bounds is None:
                    continue
                _min_x, _min_y, _max_x, _max_y, _world_verts, projected = bounds
                for point in projected:
                    if point is not None:
                        points.append((float(point[0]), float(point[1])))
            if len(points) < 3:
                return

            unique = sorted(set(points))

            def cross(o, a, b) -> float:
                return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

            lower: list[tuple[float, float]] = []
            for point in unique:
                while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                    lower.pop()
                lower.append(point)
            upper: list[tuple[float, float]] = []
            for point in reversed(unique):
                while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                    upper.pop()
                upper.append(point)
            hull = lower[:-1] + upper[:-1]
            if len(hull) < 3:
                return

            shadow = (0, 0, 0, 155)
            glow = (255, 212, 0, 230)
            closed = hull + [hull[0]]
            draw.line(closed, fill=shadow, width=6)
            draw.line(closed, fill=glow, width=2)
        except Exception as exc:
            log.debug("Selected model outline draw failed: %s", exc)

    def _draw_mesh_subobject_selection(self, draw, w: int, h: int) -> None:
        state = getattr(self, "mesh_selection_state", None)
        if state is None or state.mode is MeshSelectionMode.OBJECT:
            return
        mesh = self._active_edit_mesh()
        topology = self._active_topology()
        if mesh is None or topology is None:
            return
        try:
            bounds = self._projected_mesh_bounds(mesh, w, h)
            if bounds is None:
                return
            _min_x, _min_y, _max_x, _max_y, _world_verts, projected = bounds

            def point(vi):
                if vi < 0 or vi >= len(projected):
                    return None
                p = projected[vi]
                if p is None:
                    return None
                return (float(p[0]), float(p[1]))

            def draw_edge(edge, color, width=2):
                p0 = point(edge[0])
                p1 = point(edge[1])
                if p0 is not None and p1 is not None:
                    draw.line([p0, p1], fill=color, width=width)

            if state.mode is MeshSelectionMode.VERTEX:
                for vi in state.selected_vertices:
                    p = point(vi)
                    if p is not None:
                        x, y = p
                        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(0, 255, 122, 235), outline=(255, 255, 255, 230))
            elif state.mode is MeshSelectionMode.EDGE:
                for edge in state.selected_edges:
                    draw_edge(edge, (0, 215, 181, 245), 3)
                for edge in getattr(mesh, "_gr_connect_edges", set()) or set():
                    draw_edge(edge, (255, 212, 0, 210), 1)
            elif state.mode is MeshSelectionMode.BORDER:
                for idx in state.selected_borders:
                    if isinstance(idx, int) and 0 <= idx < len(topology.border_loops):
                        loop = topology.border_loops[idx]
                        for i in range(len(loop) - 1):
                            draw_edge((loop[i], loop[i + 1]), (255, 170, 0, 245), 3)
            elif state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
                faces = state.selected_faces if state.mode is MeshSelectionMode.FACE else state.selected_polygons
                for fi in faces:
                    if 0 <= fi < len(topology.faces):
                        pts = [point(vi) for vi in topology.faces[fi]]
                        if all(p is not None for p in pts):
                            draw.polygon(pts, fill=(0, 255, 122, 58), outline=(0, 255, 122, 230))
            elif state.mode is MeshSelectionMode.ELEMENT:
                for idx in state.selected_elements:
                    if 0 <= idx < len(topology.connected_elements):
                        for fi in topology.connected_elements[idx]:
                            pts = [point(vi) for vi in topology.faces[fi]]
                            if all(p is not None for p in pts):
                                draw.polygon(pts, fill=(0, 215, 181, 48), outline=(0, 215, 181, 210))
        except Exception as exc:
            log.debug("Mesh sub-object overlay draw failed: %s", exc)

    def _evict_transform_cache(self, node) -> None:
        clear_prebuilt_static_gpu_mesh_data(node)
        self._renderer._wt_cache.pop(id(node), None)
        try:
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
        except Exception:
            pass
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node(node)
        stack = list(getattr(node, "children", []) or [])
        visited = set()
        while stack:
            child = stack.pop()
            cid = id(child)
            if cid in visited:
                continue
            visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            if self._gpu_renderer is not None:
                self._gpu_renderer.invalidate_node(child)
            stack.extend(getattr(child, "children", []) or [])

    def _compute_bb(self, model) -> None:
        if model is None or not getattr(model, "root_node", None):
            return
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        visited = set()
        stack = [model.root_node]
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            stack.extend(getattr(node, "children", []) or [])
            verts = getattr(node, "vertices", None) or []
            if not verts:
                continue
            try:
                wp, wo, _ = self._renderer._node_world_transform(node)
            except Exception:
                wp = node.world_position() if hasattr(node, "world_position") else (0.0, 0.0, 0.0)
            for vx, vy, vz in verts:
                x, y, z = vx + wp[0], vy + wp[1], vz + wp[2]
                mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
                maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
                has_data = True
        if has_data:
            model.bb_min = tuple(mins)
            model.bb_max = tuple(maxs)

    def _prewarm_textures(self, model) -> None:
        try:
            tex_names = self._texture_names_for_prewarm(model)
        except Exception:
            return
        if not tex_names:
            return
        tex_cache = self._renderer.tex_cache
        model_id = id(model)

        def load() -> None:
            any_loaded = False
            for index, name in enumerate(tex_names):
                try:
                    any_loaded = tex_cache.get(name) is not None or any_loaded
                except Exception:
                    pass
                if any_loaded and (index % 2 == 1 or index == len(tex_names) - 1):
                    try:
                        self._texturePrewarmFinished.emit(model_id)
                    except RuntimeError:
                        return
                if index % 3 == 2:
                    time_module.sleep(0.01)
            if any_loaded:
                try:
                    self._texturePrewarmFinished.emit(model_id)
                except RuntimeError:
                    pass

        threading.Thread(target=load, daemon=True, name="qt-tex-prewarm").start()

    @staticmethod
    def _texture_names_for_prewarm(model) -> list[str]:
        if model is None:
            return []
        nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else list(model.mesh_nodes())
        names: list[str] = []
        seen: set[str] = set()
        for node in nodes:
            if not getattr(node, "vertices", None):
                continue
            candidates = [
                getattr(node, "texture_clean", ""),
                getattr(node, "texture", ""),
                getattr(node, "lightmap", ""),
                getattr(node, "bump_map", ""),
                getattr(node, "txi_envmaptexture", ""),
                getattr(node, "txi_specularcolour", ""),
                getattr(node, "txi_bumpmaptexture", ""),
            ]
            candidates.extend(getattr(node, "texture_names", []) or [])
            for raw in candidates:
                clean = str(raw or "").strip()
                if not clean:
                    continue
                clean = clean.rsplit(".", 1)[0] if "." in clean else clean
                key = clean.lower()
                if key in seen or key.upper() in ("NULL", "NONE", "****"):
                    continue
                seen.add(key)
                names.append(key)
        return names

    def _update_uv_viewer_model(self) -> None:
        if self._uv_viewer is not None:
            self._uv_viewer.set_model(self.model)


class QtMainViewportWidget(QtViewportWidget):
    """Main application viewport with main-window defaults."""

    VIEWPORT_ROLE = "main"
    DEFAULT_THUMBNAIL_ENABLED = False


class QtCharacterBuilderViewportWidget(QtViewportWidget):
    """Character Builder viewport with builder-specific HUD affordances."""

    VIEWPORT_ROLE = "character_builder"
    DEFAULT_THUMBNAIL_ENABLED = True


class QtRetargetViewportWidget(QtViewportWidget):
    """Animation retargeting viewport with workbench-specific defaults."""

    VIEWPORT_ROLE = "retarget"
    DEFAULT_THUMBNAIL_ENABLED = False
    DEFAULT_VIEWPORT_TOOLBAR_VISIBLE = False
    DEFAULT_VIEWCUBE_VISIBLE = False
    DEFAULT_TRANSFORM_TYPEIN_VISIBLE = False


class QtUnrealAnimatorViewportWidget(QtViewportWidget):
    """Unreal Animator viewport with compact controls for split-pane layouts."""

    VIEWPORT_ROLE = "unreal_animator"
    DEFAULT_THUMBNAIL_ENABLED = False
    DEFAULT_COMPACT_CONTROLS = True
