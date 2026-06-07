"""wgpu-py renderer backend for the Qt viewport.

This backend uses rendercanvas' Qt widget as the WGPU presentation surface.
ModernGL remains GhostRigger's complete scene renderer; WGPU currently provides
live-surface clear/grid plus basic untextured mesh rendering.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib import util as importlib_util
from pathlib import Path
from typing import ClassVar

from src.adapters.rendering.null_renderer import NullDiagnosticRenderer
from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_capabilities import (
    WGPU_DISPLAY_MODES,
    WGPU_FALLBACK_DISPLAY_MODES,
    RendererCapabilities,
)
from src.core.rendering.renderer_performance import (
    RenderQueueCache,
    TextureResidencyInfo,
    bounds_intersects_frustum,
    extract_frustum_planes,
    group_render_batches,
    instancing_summary,
    texture_array_groups,
)
from src.core.rendering.renderer_profiler import RendererProfiler
from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.picking import PickHit
from src.core.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions, normalize_display_mode
from src.core.lighting.light_gizmo_renderer import LIGHT_HELPER_COLORS
from src.core.rendering.wgpu_shared import (
    SELECTION_YELLOW,
    WgpuLightResource,
    WgpuMaterialResource,
    WgpuMeshResource,
    WgpuPickResources,
    WgpuSkeletonResource,
    WgpuSkinResource,
    WgpuTextureResource,
    _WGPU_BACKENDS,
    _WGPU_BACKEND_ENV,
    _WgpuBackendSpec,
    _adapter_info_dict,
    _blend_rgb,
    _format_is_srgb,
    _joint_marker_segments,
    _mat4_lookat,
    _mat4_perspective_wgpu,
    _mat4_tobytes,
    _point_distance,
    _relative_luma,
    _rgb_float,
    _rgba8,
    _srgb_channel_to_linear,
    _srgb_to_linear,
)

log = logging.getLogger(__name__)

def _probe_script() -> str:
    return r'''
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    from rendercanvas.qt import QRenderWidget
    import wgpu
except Exception as exc:
    print(json.dumps({"available": False, "reason": f"import failed: {exc}"}))
    raise SystemExit(0)

try:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    canvas = QRenderWidget()
    canvas.resize(64, 64)
    context = canvas.get_context("wgpu")
    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    if adapter is None:
        raise RuntimeError("no suitable WGPU adapter found")
    device = adapter.request_device_sync(required_features=[], required_limits={})
    fmt = context.get_preferred_format(adapter)
    context.configure(device=device, format=fmt)

    def draw():
        view = context.get_current_texture().create_view()
        encoder = device.create_command_encoder()
        render_pass = encoder.begin_render_pass(color_attachments=[{
            "view": view,
            "resolve_target": None,
            "clear_value": (0.05, 0.06, 0.07, 1.0),
            "load_op": wgpu.LoadOp.clear,
            "store_op": wgpu.StoreOp.store,
        }])
        render_pass.end()
        device.queue.submit([encoder.finish()])

    canvas.request_draw(draw)
    canvas.force_draw()
    app.processEvents()
    info = getattr(adapter, "info", None)
    print(json.dumps({
        "available": True,
        "reason": "",
        "format": fmt,
        "adapter": {
            "vendor": getattr(info, "vendor", None),
            "device": getattr(info, "device", None),
            "description": getattr(info, "description", None),
            "adapter_type": getattr(info, "adapter_type", None),
            "backend_type": getattr(info, "backend_type", None),
        },
    }))
except Exception as exc:
    print(json.dumps({"available": False, "reason": str(exc)}))
finally:
    try:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()
    except Exception:
        pass
'''



__all__ = tuple(name for name in globals() if not name.startswith("__"))
