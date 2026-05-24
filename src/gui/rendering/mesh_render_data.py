"""Renderer-neutral mesh extraction for lightweight WGPU drawing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MeshRenderData:
    mesh_id: int
    source: object
    positions: object
    normals: object | None
    indices: object | None
    material_color: tuple[float, float, float, float]
    world_matrix: object
    source_revision: tuple[int, int, int]


def iter_mesh_render_data(model, *, anim_pose=None) -> Iterable[MeshRenderData]:
    """Yield mesh draw data without storing renderer resources on scene nodes."""

    if model is None:
        return []

    import numpy as np

    nodes = _model_nodes(model)
    rows: list[MeshRenderData] = []
    for node in nodes:
        if not _node_is_renderable_mesh(node):
            continue
        try:
            positions, normals, indices = _extract_node_arrays(node, anim_pose=anim_pose)
        except Exception:
            continue
        if positions is None or len(positions) == 0:
            continue
        color = _material_color(node)
        rows.append(
            MeshRenderData(
                mesh_id=id(node),
                source=node,
                positions=np.asarray(positions, dtype=np.float32),
                normals=np.asarray(normals, dtype=np.float32) if normals is not None else None,
                indices=np.asarray(indices, dtype=np.uint32) if indices is not None else None,
                material_color=color,
                world_matrix=np.eye(4, dtype=np.float32),
                source_revision=_node_revision(node),
            )
        )
    return rows


def _model_nodes(model) -> list:
    if hasattr(model, "all_nodes"):
        try:
            return list(model.all_nodes())
        except Exception:
            pass
    if hasattr(model, "mesh_nodes"):
        try:
            return list(model.mesh_nodes())
        except Exception:
            pass
    return list(getattr(model, "nodes", []) or [])


def _node_is_renderable_mesh(node) -> bool:
    if node is None:
        return False
    if bool(getattr(node, "_gr_hidden", False)):
        return False
    if getattr(node, "render", True) is False:
        return False
    if int(getattr(node, "vertex_space", 0) or 0) == 2:
        return False
    return bool(getattr(node, "vertices", getattr(node, "verts", [])) and getattr(node, "faces", []))


def _extract_node_arrays(node, *, anim_pose=None):
    import numpy as np

    try:
        from src.gui.rendering.gpu_renderer import _build_vbo_data
    except Exception:
        _build_vbo_data = None

    world_pos, world_orient = _node_world_transform(node)
    if _build_vbo_data is not None:
        vdata, idx_arr = _build_vbo_data(node, world_pos, world_orient, anim_pose_node=None)
        if vdata is not None:
            positions = np.asarray(vdata[:, 0:3], dtype=np.float32)
            normals = np.asarray(vdata[:, 3:6], dtype=np.float32) if vdata.shape[1] >= 6 else None
            indices = np.asarray(idx_arr, dtype=np.uint32) if idx_arr is not None and len(idx_arr) else None
            return positions, normals, indices

    verts = np.asarray(getattr(node, "vertices", getattr(node, "verts", [])) or [], dtype=np.float32)
    if verts.ndim != 2 or verts.shape[1] != 3:
        return None, None, None
    normals = np.asarray(getattr(node, "normals", []) or [], dtype=np.float32)
    if normals.ndim != 2 or normals.shape[1] != 3 or len(normals) != len(verts):
        normals = np.zeros_like(verts, dtype=np.float32)
        normals[:, 2] = 1.0
    faces = getattr(node, "faces", []) or []
    indices = np.asarray([int(i) for face in faces for i in tuple(face)[:3]], dtype=np.uint32)
    return verts, normals, indices


def _node_world_transform(node) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    try:
        wp, wo = node.world_transform()
        return tuple(float(v) for v in wp[:3]), tuple(float(v) for v in wo[:4])
    except Exception:
        try:
            wp = node.world_position()
            return tuple(float(v) for v in wp[:3]), (0.0, 0.0, 0.0, 1.0)
        except Exception:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)


def _material_color(node) -> tuple[float, float, float, float]:
    raw = getattr(node, "diffuse", (0.72, 0.74, 0.76)) or (0.72, 0.74, 0.76)
    try:
        r, g, b = (float(raw[0]), float(raw[1]), float(raw[2]))
    except Exception:
        r, g, b = (0.72, 0.74, 0.76)
    alpha = float(getattr(node, "alpha", 1.0) or 1.0)
    return (_clamp01(r), _clamp01(g), _clamp01(b), _clamp01(alpha))


def _node_revision(node) -> tuple[int, int, int]:
    return (
        len(getattr(node, "vertices", getattr(node, "verts", [])) or []),
        len(getattr(node, "faces", []) or []),
        int(getattr(node, "_gr_revision", 0) or 0),
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

