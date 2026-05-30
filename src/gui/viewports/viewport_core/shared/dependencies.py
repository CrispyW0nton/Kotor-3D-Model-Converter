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
from src.gui.qt_lib.rendering.renderer_backend import normalize_renderer_backend, renderer_backend_label
from src.gui.qt_lib.rendering.renderer_performance import ViewportFrameGovernor
from src.gui.qt_lib.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.rendering.picking import CpuMeshPickingProvider, PickRequest, ray_triangle_intersection
from src.gui.qt_lib.viewports.viewport_display import (
    ViewportDisplayMode,
    ViewportDisplayOptions,
)
from src.gui.qt_lib.viewports.qt_uv_viewer import QtUVViewerWindow
from src.gui.qt_lib.viewports.viewport_host import RendererSurfaceHost
from src.gui.qt_lib.viewports.frame_renderer import ArcBallCamera, FrameRenderer
from src.gui.qt_lib.viewports.viewport_navigation import (
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

__all__ = tuple(name for name in globals() if not name.startswith("__"))
