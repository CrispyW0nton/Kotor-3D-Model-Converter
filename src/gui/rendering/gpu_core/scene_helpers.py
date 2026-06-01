from __future__ import annotations

import logging
import math
from typing import Dict, Optional

from src.core.rendering.gpu_scene_helpers import (
    _BASE_SKELETONS,
    _CompositeModel,
    _apply_txi_from_textures_to_model,
    _compute_model_bounds,
)

from .renderer import GpuRenderer

log = logging.getLogger(__name__)


def render_model_autoframe(
    model,
    W: int = 512,
    H: int = 512,
    textures: Optional[Dict[str, "Image.Image"]] = None,
    anim_pose=None,
    views: Optional[list] = None,
    fov: float = 45.0,
    renderer: Optional["GpuRenderer"] = None,
    supermodel_body=None,
    supermodel_textures: Optional[Dict[str, "Image.Image"]] = None,
) -> Dict[str, "Image.Image"]:
    """Render a KotOR model from multiple autoframed camera angles."""
    if views is None:
        views = ["front", "back", "right", "left", "top", "diag"]

    if textures is not None:
        _apply_txi_from_textures_to_model(model, textures)

    _render_model = model
    _render_textures = dict(textures) if textures else {}
    if supermodel_body is not None:
        try:
            _render_model = _CompositeModel(model, supermodel_body)
            if supermodel_textures:
                _render_textures.update(supermodel_textures)
            if supermodel_textures is not None:
                _apply_txi_from_textures_to_model(supermodel_body, supermodel_textures)
            log.debug(
                "render_model_autoframe: compositing head %r onto body %r",
                getattr(model, "name", "?"),
                getattr(supermodel_body, "name", "?"),
            )
        except Exception as exc:
            log.warning("render_model_autoframe: supermodel composite failed: %s", exc)
            _render_model = model

    bounds = _compute_model_bounds(_render_model)
    cx = bounds["center_x"]
    cy = bounds["center_y"]
    cz = bounds["center_z"]
    max_ext = bounds["max_extent"]
    ext_x = bounds["extent_x"]
    ext_y = bounds["extent_y"]
    ext_z = bounds["extent_z"]

    half_fov_rad = math.radians(fov * 0.5)
    tan_hfov = math.tan(half_fov_rad)
    half_x = ext_x * 0.5
    half_y = ext_y * 0.5
    half_z = ext_z * 0.5

    def _axis_dist(perp_ext: float, depth_half: float = 0.0) -> float:
        perp_half = perp_ext * 0.5
        near_face_min = perp_half / tan_hfov + depth_half
        centre_fit = (perp_half * 1.10) / tan_hfov
        return max(near_face_min, centre_fit) + max_ext * 0.03

    _view_defs = {
        "front": {"offset": (0, +_axis_dist(max(ext_x, ext_z), half_y), 0), "up": (0, 0, 1)},
        "back": {"offset": (0, -_axis_dist(max(ext_x, ext_z), half_y), 0), "up": (0, 0, 1)},
        "right": {"offset": (+_axis_dist(max(ext_y, ext_z), half_x), 0, 0), "up": (0, 0, 1)},
        "left": {"offset": (-_axis_dist(max(ext_y, ext_z), half_x), 0, 0), "up": (0, 0, 1)},
        "top": {"offset": (0, 0, +_axis_dist(max(ext_x, ext_y), half_z)), "up": (0, 1, 0)},
        "diag": {
            "offset": (
                +_axis_dist(max_ext, 0) * 0.6,
                +_axis_dist(max_ext, 0) * 0.6,
                +_axis_dist(max_ext, 0) * 0.3,
            ),
            "up": (0, 0, 1),
        },
    }

    _renderer = renderer or GpuRenderer()
    results: Dict[str, "Image.Image"] = {}

    for view_name in views:
        if view_name not in _view_defs:
            log.warning("render_model_autoframe: unknown view %r, skipping", view_name)
            continue
        vdef = _view_defs[view_name]
        ox, oy, oz = vdef["offset"]
        eye = (cx + ox, cy + oy, cz + oz)
        target = (cx, cy, cz)
        up = vdef["up"]

        cam_dist = math.sqrt(ox**2 + oy**2 + oz**2)
        camera = type(
            "_AutoCam",
            (),
            {
                "eye": eye,
                "target": target,
                "up": up,
                "fov": fov,
                "near": max_ext * 0.005,
                "far": cam_dist * 5.0 + max_ext * 2.0,
            },
        )()

        img = _renderer.render(_render_model, camera, W, H, textures=_render_textures, anim_pose=anim_pose)
        if img:
            results[view_name] = img

    if renderer is None:
        _renderer.release()

    return results


__all__ = tuple(name for name in globals() if not name.startswith("__"))
