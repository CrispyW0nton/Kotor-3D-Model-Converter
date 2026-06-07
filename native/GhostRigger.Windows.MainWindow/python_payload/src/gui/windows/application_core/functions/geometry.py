"""Geometry and walkmesh helper functions for application-core windows."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

def _bounds_from_points(points) -> Optional[tuple[tuple[float, float, float], tuple[float, float, float]]]:
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
    return (
        tuple(min(point[axis] for point in valid) for axis in range(3)),
        tuple(max(point[axis] for point in valid) for axis in range(3)),
    )

def _bounds_center(bounds) -> tuple[float, float, float]:
    return (
        (float(bounds[0][0]) + float(bounds[1][0])) * 0.5,
        (float(bounds[0][1]) + float(bounds[1][1])) * 0.5,
        (float(bounds[0][2]) + float(bounds[1][2])) * 0.5,
    )

def _bounds_overlap_xy(a, b) -> bool:
    return not (
        float(a[1][0]) < float(b[0][0])
        or float(b[1][0]) < float(a[0][0])
        or float(a[1][1]) < float(b[0][1])
        or float(b[1][1]) < float(a[0][1])
    )

def _walkmesh_reference_bounds(model, renderer=None):
    if model is None or not hasattr(model, "all_nodes"):
        return None
    points = []
    for node in model.all_nodes() or []:
        name = str(getattr(node, "name", "") or "").lower()
        flags = int(getattr(node, "flags", 0) or 0)
        is_walkmesh = (
            name.startswith("walkmesh")
            or int(getattr(node, "vertex_space", 0) or 0) == 2
            or bool(getattr(node, "is_aabb", False))
            or bool(flags & 0x0200)
        )
        if not is_walkmesh:
            continue
        verts = getattr(node, "vertices", []) or []
        if not verts:
            continue
        try:
            if renderer is not None and hasattr(renderer, "_get_world_verts_for_node"):
                points.extend(renderer._get_world_verts_for_node(node))
            else:
                points.extend(verts)
        except Exception:
            points.extend(verts)
    return _bounds_from_points(points)

def _walkmesh_overlay_offset_for_model(model, wok_data, renderer=None) -> tuple[float, float, float]:
    wok_bounds = _bounds_from_points(getattr(wok_data, "verts", []) or [])
    if wok_bounds is None:
        return (0.0, 0.0, 0.0)

    reference_bounds = _walkmesh_reference_bounds(model, renderer)
    if reference_bounds is not None:
        ref_center = _bounds_center(reference_bounds)
        wok_center = _bounds_center(wok_bounds)
        return (
            ref_center[0] - wok_center[0],
            ref_center[1] - wok_center[1],
            ref_center[2] - wok_center[2],
        )

    try:
        render_bounds = model.render_bounds()
    except Exception:
        render_bounds = None
    if render_bounds is None or _bounds_overlap_xy(wok_bounds, render_bounds):
        return (0.0, 0.0, 0.0)
    render_center = _bounds_center(render_bounds)
    wok_center = _bounds_center(wok_bounds)
    return (
        render_center[0] - wok_center[0],
        render_center[1] - wok_center[1],
        float(render_bounds[0][2]) - float(wok_bounds[0][2]),
    )

def _walkmesh_overlay_node_from_wok(wok_data, label: str, world_offset=(0.0, 0.0, 0.0)):
    from src.core.geometry.model_data import ModelNode, NodeFlags

    ox, oy, oz = (float(world_offset[0]), float(world_offset[1]), float(world_offset[2]))
    raw_name = str(label or "walkmesh").split(":", 1)[-1]
    stem = Path(raw_name).stem or "walkmesh"
    node = ModelNode(name=f"{stem}_overlay", flags=int(NodeFlags.AABB), render=False)
    node.vertex_space = 1
    node.texture = "walkmesh"
    node.vertices = [
        (float(v[0]) + ox, float(v[1]) + oy, float(v[2]) + oz)
        for v in (getattr(wok_data, "verts", []) or [])
    ]
    node.faces = [
        (int(face.v1), int(face.v2), int(face.v3))
        for face in (getattr(wok_data, "faces", []) or [])
    ]
    node.face_mats = [
        int(getattr(face, "surface", 0) or 0)
        for face in (getattr(wok_data, "faces", []) or [])
    ]
    node._gr_walkmesh_overlay_proxy = True
    node._gr_walkmesh_source_label = str(label or "")
    node._gr_hidden = True
    return node

def _prebuild_gpu_mesh_data_for_model(model) -> None:
    try:
        from src.adapters.rendering.moderngl_resources import prebuild_static_gpu_mesh_data

        prebuild_static_gpu_mesh_data(model)
    except Exception:
        log.debug("Static GPU mesh prebuild failed", exc_info=True)
