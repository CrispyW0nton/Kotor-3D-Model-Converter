"""Qt viewport host for the GhostRigger UI migration."""

from __future__ import annotations

import logging
import math
import os
import re
import threading
import time as time_module
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_gpu_renderer import GpuRenderer
from .qt_uv_viewer import QtUVViewerWindow
from .viewport_core import ArcBallCamera, FrameRenderer
from .viewport_navigation import (
    DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
    has_modifier,
    normalize_viewport_navigation_profile,
    viewport_profile_label,
)

log = logging.getLogger(__name__)


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
    r"leg|foot|elbow|wrist|knee|clavicle|arm|breast|hip(?!$)"
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

    modelChanged = QtCore.Signal(object)
    nodeSelected = QtCore.Signal(object)
    nodeMoved = QtCore.Signal(object)
    _texturePrewarmFinished = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.camera = ArcBallCamera()
        self._renderer = FrameRenderer(self.camera)
        self.model = None
        self.on_bone_selected = None
        self.on_node_selected = None
        self.on_node_moved = None

        self._mx = self._my = 0
        self._press_x = self._press_y = 0
        self._drag_threshold = 4
        self._is_dragging = False
        self._pan_dragging = False
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._gimbal_dragging = False
        self._gimbal_axis = ""
        self._gimbal_drag_start = (0, 0)
        self._gimbal_node_start_pos = (0.0, 0.0, 0.0)
        self._gimbal_node_start_rot = (0.0, 0.0, 0.0, 1.0)
        self._undo_limit = 250
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._render_pending = False
        self._last_canvas_size = (0, 0)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._fast_drag_enabled = False
        self._uv_viewer: Optional[QtUVViewerWindow] = None
        self._use_gpu = True
        self._gpu_renderer: Optional[GpuRenderer] = None
        self._owns_gpu_renderer = True
        self._gpu_tex_preload_model_id = 0
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        self._xray_mode = False
        self._dual_viewport_mode = False
        # ── T401: Joint-dot overlay state ──────────────────────────────
        # Painted by `_draw_joint_dots()` after `_draw_bones`.  Defaults
        # chosen so the dots are immediately visible on a fresh viewport;
        # M4 inspector sliders override via `set_joint_dot_size` /
        # `set_joint_dot_opacity` / `set_joint_dot_enabled`.
        self._joint_dot_enabled: bool = True
        self._joint_dot_size: int = 6        # radius in screen pixels (3 .. 16)
        self._joint_dot_opacity: float = 0.85  # 0.0 (invisible) .. 1.0 (opaque)
        # ── T402: Joint-dot interaction state ──────────────────────────
        # Symmetry mirrors X-axis translations to the AccuRig MIRROR_PAIRS
        # partner when enabled (default on — matches AccuRig UX).
        self._joint_symmetry_enabled: bool = True
        self._joint_dragging: bool = False
        self._joint_drag_node = None              # primary node under cursor
        self._joint_drag_mirror_node = None       # MIRROR_PAIRS partner, if any
        self._joint_drag_start_screen = (0, 0)
        self._joint_drag_start_pos = (0.0, 0.0, 0.0)
        self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
        self._joint_drag_world_per_px = 1.0
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
        self._build()

    @property
    def navigation_profile(self) -> str:
        return self._navigation_profile

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = normalize_viewport_navigation_profile(profile)
        if hasattr(self, "navigation_button"):
            self.navigation_button.setText(viewport_profile_label(self._navigation_profile))
            self.navigation_button.setToolTip(self._navigation_tooltip())

    def _navigation_tooltip(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        controls = {
            "3dsmax": "3ds Max: Alt+MMB orbit, MMB pan, Alt+RMB zoom, wheel zoom; Shift+F/T/L/P views",
            "blender": "Blender: MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, wheel zoom; 1/3/7/Home views",
            "maya": "Maya: Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, wheel zoom; A/F frame",
        }.get(self._navigation_profile, "")
        return f"Viewport navigation profile: {label}\n{controls}"

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tb = QtWidgets.QFrame()
        tb.setObjectName("ViewportToolbar")
        tb.setStyleSheet(
            "#ViewportToolbar { background:#202124; border:0; border-bottom:1px solid #3a3d42; }"
        )
        tb.setFixedHeight(30)
        row = QtWidgets.QHBoxLayout(tb)
        row.setContentsMargins(5, 3, 5, 3)
        row.setSpacing(3)

        self.wire_button = self._button("Wire  W", self.toggle_wireframe, checkable=True)
        self.bones_button = self._button("Bones  B", self.toggle_bones, checkable=True)
        self.texture_button = self._button("Texture  T", self.toggle_texture, checkable=True, active=True)
        self.renderer_button = self._button("GPU", self.toggle_gpu_renderer, checkable=True, active=True)
        self.xray_button = self._button("X-Ray  Alt+X", self.toggle_xray, checkable=True)
        self.joint_dot_button = self._button("Dots", self.toggle_joint_dots, checkable=True, active=True)
        self.joint_dot_button.setToolTip("Show or hide AccuRig joint-dot handles")
        self.heatmap_button = self._button("Heat", self.toggle_weight_heatmap, checkable=True)
        self.heatmap_button.setToolTip("Show selected-bone weight heat-map")
        row.addWidget(self.wire_button)
        row.addWidget(self.bones_button)
        row.addWidget(self.texture_button)
        row.addWidget(self.renderer_button)
        row.addWidget(self.xray_button)
        row.addWidget(self.joint_dot_button)
        row.addWidget(self.heatmap_button)
        row.addWidget(self._separator())

        self.shade_combo = QtWidgets.QComboBox()
        self.shade_combo.addItems(["Solid", "Wire", "Both"])
        self.shade_combo.setFixedHeight(22)
        self.shade_combo.setStyleSheet(
            "QComboBox { background:#2b2e33; color:#d7dde6; border:1px solid #464b53; "
            "padding:2px 18px 2px 7px; min-width:68px; }"
            "QComboBox:hover { border-color:#6d747f; }"
            "QComboBox::drop-down { border:0; width:16px; }"
            "QComboBox QAbstractItemView { background:#24272c; color:#d7dde6; selection-background-color:#3d5f8a; }"
        )
        row.addWidget(self.shade_combo)
        row.addWidget(self._button("Frame  F", self.frame_all))
        row.addWidget(self._button("Camera  R", self.reset_camera))
        self.walkmesh_button = self._button("WalkMesh", self.toggle_walkmesh, checkable=True)
        row.addWidget(self.walkmesh_button)
        row.addWidget(self._separator())
        self.gimbal_button = self._button("Gimbal  G", self.toggle_gimbal, checkable=True, active=True)
        row.addWidget(self.gimbal_button)
        self.gimbal_mode_button = self._button("[Translate]", self.cycle_gimbal_mode)
        row.addWidget(self.gimbal_mode_button)
        row.addWidget(self._button("UV View", self.open_uv_viewer))
        row.addWidget(self._separator())
        self.navigation_button = self._button(viewport_profile_label(self._navigation_profile), self._cycle_navigation_profile)
        self.navigation_button.setToolTip(self._navigation_tooltip())
        row.addWidget(self.navigation_button)
        row.addStretch(1)

        self.canvas = QtWidgets.QLabel("No model loaded")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(180, 140)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setScaledContents(False)
        self.canvas.setStyleSheet(
            "background:#17191c; color:#8f9aaa; border:1px solid #34383f;"
        )
        self.canvas.installEventFilter(self)
        self.shade_combo.currentTextChanged.connect(self._on_shade_change)
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_wireframe = self.wire_button.isChecked()

        root.addWidget(tb)
        root.addWidget(self.canvas, 1)

        # ── T403: Mini-thumbnail inset (top-right) ────────────────────
        # Built as a child widget of `self.canvas` so it floats over the
        # main render and tracks canvas resize via `eventFilter`.  Click
        # the thumbnail to snap the main camera back to "frame all".
        self._thumbnail_widget = _MiniThumbnailWidget(self)
        self._thumbnail_widget.setParent(self.canvas)
        self._thumbnail_widget.clicked.connect(self.reset_camera)
        self._thumbnail_widget.hide()  # shown once a model is loaded
        self._thumbnail_visible_setting: bool = True
        self._thumbnail_force_hidden: bool = False  # set by Head close-up
        self._reposition_thumbnail()

        # ── T404: Snap-view button cluster (top-center) ────────────────
        # Floating bar with 6 view-preset buttons + Persp/Ortho toggle.
        # Wired to a smooth 200 ms interpolation rather than instant snap.
        self._snap_view_widget = _FloatingSnapViewWidget(self.canvas)
        self._snap_view_widget.viewSelected.connect(self._snap_to_view)
        self._snap_view_widget.orthoToggled.connect(self.set_ortho_mode)
        # Animation state — driven by a QTimer at ~60 Hz for 200 ms.
        self._snap_anim_timer = QtCore.QTimer(self)
        self._snap_anim_timer.setInterval(int(1000.0 / SNAP_VIEW_INTERP_HZ))
        self._snap_anim_timer.timeout.connect(self._snap_anim_tick)
        self._snap_anim_t0: float = 0.0
        self._snap_anim_from = (0.0, 0.0)   # (azimuth, elevation)
        self._snap_anim_to = (0.0, 0.0)
        self._ortho_mode: bool = False
        self._reposition_snap_view()

    def _button(
        self,
        text: str,
        callback,
        *,
        checkable: bool = False,
        active: bool = False,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setCheckable(checkable)
        button.setChecked(active if checkable else False)
        button.setFixedHeight(22)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton { background:#2b2e33; color:#d7dde6; border:1px solid #464b53; padding:2px 7px; }"
            "QPushButton:checked { background:#35506f; color:#ffffff; border-color:#6ea0d8; }"
            "QPushButton:hover { background:#363a40; color:#ffffff; border-color:#6d747f; }"
            "QPushButton:pressed { background:#1f2227; }"
        )
        button.clicked.connect(lambda checked=False: callback(checked) if checkable else callback())
        return button

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("background:#4a4f58;")
        sep.setFixedWidth(1)
        return sep

    def load_model(
        self,
        model,
        texture_dir: str = "",
        extra_texture_dirs: Optional[list[str]] = None,
        texture_cache: Optional[dict[str, bytes]] = None,
    ) -> None:
        self.model = model
        self._renderer.set_model(model)
        self._clear_edit_history()
        self._gpu_tex_preload_model_id = 0
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        if model is None:
            self._pixmap = None
            self._render_pending = False
            self._renderer.set_animation_pose(None)
            self._renderer.clear_walkmesh()
            self.walkmesh_button.setChecked(False)
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
            self.renderer_button.setText("GPU" if self._use_gpu else "CPU")
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("No model loaded")
            self._update_uv_viewer_model()
            # T403: clear the thumbnail when no model is loaded.
            self._refresh_thumbnail_safe()
            self.modelChanged.emit(None)
            return
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_wireframe = self.wire_button.isChecked()
        self._on_shade_change(self.shade_combo.currentText())

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

        self._compute_bb(model)
        self.frame_all()
        self._prewarm_textures(model)
        self._update_uv_viewer_model()
        # T403: populate the mini-thumbnail inset with a neutral-pose
        # snapshot of the freshly loaded model.  Cheap (CPU render at
        # 216×276) and one-shot — subsequent re-frames don't need to
        # re-render the thumbnail since neutral pose is camera-pose
        # independent (its render path uses a private ArcBallCamera).
        self._refresh_thumbnail_safe()
        self.modelChanged.emit(model)
        self._request_render()
        self._queue_post_load_gpu_refresh()

    def set_model(self, model) -> None:
        self.load_model(model)

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

    def set_shared_gpu_renderer(self, renderer: Optional[GpuRenderer]) -> None:
        self._gpu_renderer = renderer
        self._owns_gpu_renderer = renderer is None

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
        self._renderer.show_wireframe = bool(checked) if checked is not None else not self._renderer.show_wireframe
        if self._renderer.show_wireframe:
            mode = "Both" if self._renderer.show_solid else "Wire"
        else:
            if not self._renderer.show_solid:
                self._renderer.show_solid = True
            mode = "Solid"
        self.shade_combo.blockSignals(True)
        self.shade_combo.setCurrentText(mode)
        self.shade_combo.blockSignals(False)
        self.wire_button.blockSignals(True)
        self.wire_button.setChecked(self._renderer.show_wireframe)
        self.wire_button.blockSignals(False)
        self._request_render()

    def toggle_bones(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_bones = bool(checked) if checked is not None else not self._renderer.show_bones
        self._request_render()

    def toggle_texture(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_texture = bool(checked) if checked is not None else not self._renderer.show_texture
        self.texture_button.blockSignals(True)
        self.texture_button.setChecked(self._renderer.show_texture)
        self.texture_button.blockSignals(False)
        self._request_render()

    def toggle_gpu_renderer(self, checked: Optional[bool] = None) -> None:
        self._use_gpu = bool(checked) if checked is not None else not self._use_gpu
        self.renderer_button.setChecked(self._use_gpu)
        self.renderer_button.setText("GPU" if self._use_gpu else "CPU")
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
        self._renderer.show_gimbal = bool(checked) if checked is not None else not self._renderer.show_gimbal
        self.gimbal_button.setChecked(self._renderer.show_gimbal)
        self._request_render()

    def cycle_gimbal_mode(self) -> None:
        self.set_gimbal_mode(2 if self._renderer.gimbal_mode == 1 else 1)
        self._request_render()

    def set_gimbal_mode(self, mode: int) -> None:
        self._renderer.gimbal_mode = 2 if mode == 2 else 1
        mode_label = "Rotate" if self._renderer.gimbal_mode == 2 else "Translate"
        self.gimbal_mode_button.setText(f"[{mode_label}]")

    def frame_all(self) -> None:
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max)
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
            from src.core import head_workflow as hw       # type: ignore
        except Exception:
            try:
                from core import head_workflow as hw      # type: ignore
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
        # Guard against collapsing canvases: if the widget would clip
        # off-screen, hide it rather than render half-off.
        if x < THUMBNAIL_MARGIN_PX or self.canvas.height() < THUMBNAIL_HEIGHT_PX + 2 * THUMBNAIL_MARGIN_PX:
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
          • Falls back to CPU render only — GPU rendering would
            require a second GL context and isn't worth it for a
            220×280 inset.
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
            img = ren.render(int(w), int(h))
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

    def set_selected_node(self, node) -> None:
        self._renderer.selected_node = node
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(node)
        self.nodeSelected.emit(node)
        self._request_render()

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
    def _state_changed(before_pos, before_rot, after_pos, after_rot) -> bool:
        values = tuple(before_pos) + tuple(before_rot) + tuple(after_pos) + tuple(after_rot)
        if any(not math.isfinite(float(v)) for v in values):
            return False
        return (
            any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_pos, after_pos))
            or any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_rot, after_rot))
        )

    def _commit_node_transform(self, node, before_pos, before_rot, after_pos, after_rot, label: str) -> None:
        if node is None or not self._state_changed(before_pos, before_rot, after_pos, after_rot):
            return
        self._undo_stack.append(
            {
                "node": node,
                "before_pos": tuple(before_pos),
                "before_rot": tuple(before_rot),
                "after_pos": tuple(after_pos),
                "after_rot": tuple(after_rot),
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
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        self._apply_transform_action(action, use_after=False)
        self._redo_stack.append(action)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._apply_transform_action(action, use_after=True)
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        return True

    def _notify_node_moved(self, node) -> None:
        if self.on_node_moved:
            self.on_node_moved(node)
        self.nodeMoved.emit(node)
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

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self.canvas:
            et = event.type()
            if et == QtCore.QEvent.Resize:
                size = (event.size().width(), event.size().height())
                if size != self._last_canvas_size:
                    self._last_canvas_size = size
                    self._request_render()
                # T403: keep the mini-thumbnail pinned to the top-right
                # corner as the canvas resizes.
                self._reposition_thumbnail()
                # T404: keep the snap-view bar pinned top-center.
                self._reposition_snap_view()
                return False
            if et == QtCore.QEvent.MouseButtonPress:
                self.canvas.setFocus()
                action = self._navigation_action(event.button(), event.modifiers())
                if action:
                    self._press_navigation(event, action)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._press_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseMove:
                if self._nav_dragging:
                    self._drag_navigation(event)
                    return True
                if event.buttons() & QtCore.Qt.LeftButton:
                    self._drag_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseButtonRelease:
                if self._nav_dragging and event.button() == self._nav_button:
                    self._release_navigation(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._release_lmb(event)
                    return True
            if et == QtCore.QEvent.Wheel:
                steps = event.angleDelta().y() / 120.0
                self.camera.zoom(steps)
                self._renderer.is_interactive = False
                self._request_render()
                return True
            if et == QtCore.QEvent.KeyPress:
                key = event.key()
                modifiers = event.modifiers()
                no_modifiers = not (
                    modifiers
                    & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
                )
                if key == QtCore.Qt.Key_F and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_Home and no_modifiers:
                    self.frame_all(); return True
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
                if key == QtCore.Qt.Key_Tab and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Z and (event.modifiers() & QtCore.Qt.ControlModifier):
                    if event.modifiers() & QtCore.Qt.ShiftModifier:
                        self.redo()
                    else:
                        self.undo()
                    return True
                if key == QtCore.Qt.Key_Y and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.redo()
                    return True
                if key == QtCore.Qt.Key_X and (event.modifiers() & QtCore.Qt.AltModifier):
                    self.xray_button.click()
                    return True
                if self._handle_view_key(event):
                    return True
        return super().eventFilter(obj, event)

    def _navigation_action(self, button, modifiers) -> str:
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
                self.frame_all()
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
        if key in ("headless_body", "supermodel"):
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
    def _reposition_snap_view(self) -> None:
        """Pin the snap-view bar to the top-center of the canvas."""
        if not hasattr(self, "_snap_view_widget") or self._snap_view_widget is None:
            return
        bar = self._snap_view_widget
        bar.adjustSize()
        bw, bh = bar.width(), bar.height()
        cw = max(0, self.canvas.width())
        if cw < bw + 2 * SNAP_VIEW_BAR_MARGIN:
            bar.hide()
            return
        x = max(SNAP_VIEW_BAR_MARGIN, (cw - bw) // 2)
        y = SNAP_VIEW_BAR_MARGIN
        bar.move(x, y)
        bar.show()
        bar.raise_()

    def _snap_to_view(self, view: str) -> None:
        """Smoothly interpolate the camera to a named preset view.

        Implementation: a 200 ms tween over (azimuth, elevation) driven
        by a QTimer at ~60 Hz.  Distance and target are preserved so
        the user's framing isn't clobbered when they snap to a side
        view.
        """
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
        if hasattr(self, "_snap_view_widget") and self._snap_view_widget is not None:
            btn = self._snap_view_widget.ortho_button
            with QtCore.QSignalBlocker(btn):
                btn.setChecked(new_val)
                btn.setText("Ortho" if new_val else "Persp")
        self._request_render()

    @property
    def ortho_mode(self) -> bool:
        return self._ortho_mode

    def _request_render(self, fast: bool = False) -> None:
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

    def _render_now(self) -> None:
        if not self._render_pending:
            return
        self._render_pending = False
        if self.model is None:
            self._pixmap = None
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("No model loaded")
            return
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        t0 = time_module.perf_counter()
        img = self._render_frame(w, h)
        self._last_render_ms = (time_module.perf_counter() - t0) * 1000.0
        self._last_render_wall = time_module.perf_counter()
        if img is None:
            mesh_count = len(self.model.mesh_nodes()) if hasattr(self.model, "mesh_nodes") else 0
            node_count = self.model.node_count() if hasattr(self.model, "node_count") else 0
            self.canvas.setText(f"{getattr(self.model, 'name', 'model')}\nRender unavailable\n{mesh_count} mesh | {node_count} nodes")
            return
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        self._update_fps()
        img = self._draw_performance_overlay(img, w, h)
        qimg = QtGui.QImage(
            img.tobytes("raw", "RGBA"),
            img.width,
            img.height,
            img.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        self._pixmap = QtGui.QPixmap.fromImage(qimg)
        self.canvas.setPixmap(self._pixmap)
        rendered_size = (w, h)
        self._last_rendered_canvas_size = rendered_size
        current_size = (max(8, self.canvas.width()), max(8, self.canvas.height()))
        if current_size != rendered_size:
            self._request_render()

    def _render_frame(self, w: int, h: int):
        gpu_can_match_mode = (
            self._renderer.show_solid
            and self._renderer.show_texture
        )
        if self._use_gpu and self.model is not None and gpu_can_match_mode:
            img = self._render_gpu_frame(w, h)
            if img is not None:
                self._set_renderer_badge(True)
                return self._draw_cpu_overlays(img, w, h, gpu_base=True)
        self._set_renderer_badge(False)
        img = self._renderer.render(w, h)
        if self._xray_mode:
            img = self._draw_xray_grid_overlay(img, w, h)
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
            self._gpu_renderer = GpuRenderer()
        self._preload_gpu_textures()
        tex_cache = getattr(self._renderer, "tex_cache", None)
        textures = {
            key: value
            for key, value in getattr(tex_cache, "_cache", {}).items()
            if value is not None
        }
        self._gpu_renderer.interactive = bool(
            self._renderer.is_interactive
            or self._pan_dragging
            or self._nav_dragging
            or self._is_dragging
            or time_module.perf_counter() < self._fast_frame_until
        )
        self._gpu_renderer.show_wireframe = bool(self._renderer.show_wireframe)
        self._gpu_renderer.show_grid = True
        self._gpu_renderer.cull_faces = False
        return self._gpu_renderer.render(
            self.model,
            self.camera,
            w,
            h,
            textures=textures,
            anim_pose=getattr(self._renderer, "_anim_pose", None),
            anim_time=float(getattr(self._renderer, "_anim_time", 0.0)),
            anim_base_pose=getattr(self._renderer, "_anim_base_pose", None),
        )

    def _draw_cpu_overlays(self, img, w: int, h: int, *, gpu_base: bool = False):
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
            if self._xray_mode or not gpu_base:
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
            if self._renderer.show_walkmesh:
                self._renderer._draw_walkmesh_overlay(draw, w, h)
            if self._renderer.show_wireframe:
                old_solid = self._renderer.show_solid
                try:
                    self._renderer.show_solid = False
                    self._renderer._draw_mesh_flat(draw, img, w, h)
                finally:
                    self._renderer.show_solid = old_solid
            if self._renderer.show_gimbal:
                self._renderer._draw_gimbal(draw, w, h)
            self._renderer._draw_axes(draw, w, h)
            self._renderer._draw_stats(draw, w, h)
            return img
        except Exception as exc:
            log.debug("Qt GPU overlay draw failed: %s", exc)
            return img

    # ── T401: Joint-dot overlay ────────────────────────────────────────
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

            radius = int(max(2, min(16, self._joint_dot_size)))
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
                outline_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, alpha), 1.0)
                sel_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, alpha), 2.0)
                for entry in positions:
                    if not entry or len(entry) < 4:
                        continue
                    sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                    if sx is None or sy is None:
                        continue
                    name = getattr(node, "name", "") or ""
                    color = QtGui.QColor(_classify_joint_color(name))
                    color.setAlpha(alpha)
                    painter.setBrush(QtGui.QBrush(color))
                    painter.setPen(sel_pen if node is sel_node else outline_pen)
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
            for entry in positions:
                if not entry or len(entry) < 4:
                    continue
                sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                if sx is None or sy is None:
                    continue
                name = getattr(node, "name", "") or ""
                qc = _classify_joint_color(name)
                fill = (qc.red(), qc.green(), qc.blue(), alpha)
                outline = (255, 255, 255, alpha) if node is sel_node else (0, 0, 0, alpha)
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=fill,
                    outline=outline,
                    width=2 if node is sel_node else 1,
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
        positions = getattr(self._renderer, "_bone_screen_positions", None)
        if not positions:
            return None
        # 4 px slack so the cursor can be slightly outside the painted disc.
        radius = int(max(2, self._joint_dot_size)) + 4
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
        if not self.model:
            return None
        name = (getattr(node, "name", "") or "").lower()
        if not name:
            return None
        try:
            from ..autorig.accurig import MIRROR_PAIRS
        except Exception:
            try:
                from src.autorig.accurig import MIRROR_PAIRS  # type: ignore
            except Exception:
                try:
                    from autorig.accurig import MIRROR_PAIRS  # type: ignore
                except Exception:
                    return None
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
        if partner_name is None:
            return None
        try:
            return self.model.find_node(partner_name)
        except Exception:
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
        """Set joint-dot radius in pixels.  Clamped to [2, 16]."""
        new_size = int(max(2, min(16, int(size))))
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
            y = max(8, h - 28)
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
        try:
            nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
            for node in nodes:
                if not (getattr(node, "is_mesh", False) or getattr(node, "is_skin", False)):
                    continue
                names = [
                    getattr(node, "texture", ""),
                    getattr(node, "lightmap", ""),
                    getattr(node, "txi_envmaptexture", ""),
                    getattr(node, "txi_specularcolour", ""),
                    getattr(node, "txi_bumpmaptexture", ""),
                ]
                names.extend(getattr(node, "texture_names", []) or [])
                for name in names:
                    clean = str(name or "").strip()
                    if clean and clean.upper() not in ("NULL", "NONE"):
                        tex_cache.get(clean)
            self._gpu_tex_preload_model_id = id(model)
        except Exception as exc:
            log.debug("Qt GPU texture preload failed: %s", exc)

    def _set_renderer_badge(self, gpu_active: bool) -> None:
        if not hasattr(self, "renderer_button"):
            return
        if not self._use_gpu:
            self.renderer_button.setText("CPU")
            return
        self.renderer_button.setText("GPU" if gpu_active else "CPU*")

    def _on_shade_change(self, text: str) -> None:
        mode = "Wireframe" if text == "Wire" else text
        self._renderer.show_solid = mode in ("Solid", "Both")
        self._renderer.show_wireframe = mode in ("Wireframe", "Both")
        self.wire_button.blockSignals(True)
        self.wire_button.setChecked(self._renderer.show_wireframe)
        self.wire_button.blockSignals(False)
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

        if self._renderer.show_gimbal and self._renderer.selected_node and self._renderer._gimbal_handles:
            axis = self._renderer.hit_test_gimbal(x, y)
            if axis:
                self._gimbal_dragging = True
                self._gimbal_axis = axis
                self._gimbal_drag_start = (x, y)
                self._gimbal_node_start_pos = tuple(self._renderer.selected_node.position)
                self._gimbal_node_start_rot = tuple(self._renderer.selected_node.rotation)
                self._renderer.gimbal_active_axis = axis
                self._request_render()
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
                self._joint_drag_node = joint_node
                self._joint_drag_mirror_node = self._joint_mirror_partner(joint_node)
                self._joint_drag_start_screen = (x, y)
                try:
                    self._joint_drag_start_pos = tuple(joint_node.position)
                except Exception:
                    self._joint_drag_start_pos = (0.0, 0.0, 0.0)
                if self._joint_drag_mirror_node is not None:
                    try:
                        self._joint_drag_mirror_start_pos = tuple(
                            self._joint_drag_mirror_node.position
                        )
                    except Exception:
                        self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
                else:
                    self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
                # Cache the screen→world conversion factor at the joint's
                # depth so the drag-translate math feels consistent
                # regardless of camera distance.
                try:
                    w = self.canvas.width() or 800
                    h = self.canvas.height() or 600
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

    def _drag_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._gimbal_dragging and self._renderer.selected_node:
            self._apply_gimbal_drag(x, y)
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

        if not self._is_dragging:
            if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                self._is_dragging = True
                self._renderer._hovered_bone = None
        if self._is_dragging:
            self._mx, self._my = x, y

    def _release_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            node = self._renderer.selected_node
            if node is not None:
                self._commit_node_transform(
                    node,
                    self._gimbal_node_start_pos,
                    self._gimbal_node_start_rot,
                    tuple(node.position),
                    tuple(node.rotation),
                    "Gimbal Transform",
                )
                self._notify_node_moved(node)
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
            was_dragging = self._joint_dragging
            self._joint_dragging = False
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            if was_dragging:
                try:
                    self._commit_node_transform(
                        joint,
                        self._joint_drag_start_pos,
                        tuple(joint.rotation),
                        tuple(joint.position),
                        tuple(joint.rotation),
                        "Joint Translate",
                    )
                    self._notify_node_moved(joint)
                    if mirror is not None:
                        self._commit_node_transform(
                            mirror,
                            self._joint_drag_mirror_start_pos,
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
            # Click-or-drag: always finish by selecting the joint so the
            # inspector reflects the user's intent.
            self.set_selected_node(joint)
            if self.on_bone_selected:
                self.on_bone_selected(joint)
            self._renderer._hovered_bone = None
            self._request_render()
            return

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False
        if self._is_dragging:
            self._is_dragging = False
            self._request_render()
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
            sp = self._joint_drag_start_pos
            node.position = (sp[0] + dwx, sp[1] + dwy, sp[2] + dwz)
            self._evict_transform_cache(node)

            mirror = self._joint_drag_mirror_node
            if mirror is not None and self._joint_symmetry_enabled:
                msp = self._joint_drag_mirror_start_pos
                # Mirror across the X axis: negate the X component of the
                # translation delta so the partner moves symmetrically.
                mirror.position = (msp[0] - dwx, msp[1] + dwy, msp[2] + dwz)
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
        wp, _, _ = self._renderer._node_world_transform(node)
        proj = self._renderer._proj(*wp, w, h)
        dist = max(0.5, proj[2] if proj else 1.0)
        world_per_px = (2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)) / max(h, 1)
        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos

        if self._renderer.gimbal_mode == 1:
            right, up, _fwd, _eye = self.camera._view_matrix()

            def axis_delta(axis_name: str):
                w_dir = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0)}.get(axis_name, (0.0, 0.0, 1.0))
                sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
                sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
                ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
                if ll < 1e-6:
                    return (0.0, 0.0, 0.0)
                delta = ((dx_screen * sc_x + (-dy_screen) * sc_y) / ll) * world_per_px
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

            if len(axis) == 1:
                d = axis_delta(axis)
                node.position = (start[0] + d[0], start[1] + d[1], start[2] + d[2])
            else:
                d1 = axis_delta(axis[0])
                d2 = axis_delta(axis[1])
                node.position = (start[0] + d1[0] + d2[0], start[1] + d1[1] + d2[1], start[2] + d1[2] + d2[2])
        elif self._renderer.gimbal_mode == 2:
            angle = dx_screen * 0.01
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                deg = round(math.degrees(angle) / 10.0) * 10.0
                angle = math.radians(deg)
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

    def _evict_transform_cache(self, node) -> None:
        self._renderer._wt_cache.pop(id(node), None)
        stack = list(getattr(node, "children", []) or [])
        visited = set()
        while stack:
            child = stack.pop()
            cid = id(child)
            if cid in visited:
                continue
            visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
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
            nodes = (
                list(model.all_nodes())
                if hasattr(model, "all_nodes") else
                list(model.mesh_nodes())
            )
            tex_names = []
            seen = set()
            for node in nodes:
                if not (getattr(node, "is_mesh", False)
                        or getattr(node, "is_skin", False)):
                    continue
                name = str(
                    getattr(node, "texture_clean", "")
                    or getattr(node, "texture", "")
                ).strip()
                if not name or name.upper() == "NULL":
                    continue
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    tex_names.append(name)
        except Exception:
            return
        if not tex_names:
            return
        tex_cache = self._renderer.tex_cache
        model_id = id(model)

        def load() -> None:
            any_loaded = False
            for name in tex_names:
                try:
                    any_loaded = tex_cache.get(name) is not None or any_loaded
                except Exception:
                    pass
            if any_loaded:
                self._texturePrewarmFinished.emit(model_id)

        threading.Thread(target=load, daemon=True, name="qt-tex-prewarm").start()

    def _update_uv_viewer_model(self) -> None:
        if self._uv_viewer is not None:
            self._uv_viewer.set_model(self.model)
