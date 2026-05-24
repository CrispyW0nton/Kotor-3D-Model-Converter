"""Renderer-neutral mesh/material extraction for lightweight WGPU drawing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TextureRenderData:
    texture_id: str
    name: str
    source: object | None
    source_revision: tuple[int, int, int]


@dataclass(frozen=True)
class MaterialRenderData:
    material_id: str
    name: str
    diffuse_texture_id: str
    diffuse_texture_path: str
    diffuse_texture_data: TextureRenderData | None
    lightmap_texture_id: str
    lightmap_texture_path: str
    lightmap_texture_data: TextureRenderData | None
    base_color_rgba: tuple[float, float, float, float]
    alpha_mode: str
    alpha_cutoff: float
    double_sided: bool
    unlit: bool
    has_transparency: bool
    source_revision: tuple[int, int, int, int]


@dataclass(frozen=True)
class MeshRenderData:
    mesh_id: int
    source: object
    positions: object
    normals: object | None
    uvs0: object | None
    uvs1: object | None
    indices: object | None
    material: MaterialRenderData
    material_color: tuple[float, float, float, float]
    world_matrix: object
    source_revision: tuple[int, int, int]


def iter_mesh_render_data(model, *, anim_pose=None, textures: dict | None = None) -> Iterable[MeshRenderData]:
    """Yield mesh draw data without storing renderer resources on scene nodes."""

    if model is None:
        return []

    import numpy as np

    textures = textures or {}
    nodes = _model_nodes(model)
    rows: list[MeshRenderData] = []
    for node in nodes:
        if not _node_is_renderable_mesh(node):
            continue
        try:
            positions, normals, uvs0, uvs1, indices = _extract_node_arrays(node, anim_pose=anim_pose)
        except Exception:
            continue
        if positions is None or len(positions) == 0:
            continue
        material = _material_data(node, textures)
        rows.append(
            MeshRenderData(
                mesh_id=id(node),
                source=node,
                positions=np.asarray(positions, dtype=np.float32),
                normals=np.asarray(normals, dtype=np.float32) if normals is not None else None,
                uvs0=np.asarray(uvs0, dtype=np.float32) if uvs0 is not None else None,
                uvs1=np.asarray(uvs1, dtype=np.float32) if uvs1 is not None else None,
                indices=np.asarray(indices, dtype=np.uint32) if indices is not None else None,
                material=material,
                material_color=material.base_color_rgba,
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
            uvs0 = np.asarray(vdata[:, 6:8], dtype=np.float32) if vdata.shape[1] >= 8 else None
            uvs1 = np.asarray(vdata[:, 8:10], dtype=np.float32) if vdata.shape[1] >= 10 else None
            indices = np.asarray(idx_arr, dtype=np.uint32) if idx_arr is not None and len(idx_arr) else None
            return positions, normals, uvs0, uvs1, indices

    verts = np.asarray(getattr(node, "vertices", getattr(node, "verts", [])) or [], dtype=np.float32)
    if verts.ndim != 2 or verts.shape[1] != 3:
        return None, None, None, None, None
    normals = np.asarray(getattr(node, "normals", []) or [], dtype=np.float32)
    if normals.ndim != 2 or normals.shape[1] != 3 or len(normals) != len(verts):
        normals = np.zeros_like(verts, dtype=np.float32)
        normals[:, 2] = 1.0
    uvs0 = _node_uv_array(node, "uvs", len(verts))
    uvs1 = _node_uv_array(node, "uvs_lm", len(verts))
    faces = getattr(node, "faces", []) or []
    indices = np.asarray([int(i) for face in faces for i in tuple(face)[:3]], dtype=np.uint32)
    return verts, normals, uvs0, uvs1, indices


def texture_image_to_rgba8(texture_data: TextureRenderData | None) -> tuple[int, int, bytes] | None:
    """Return bottom-up RGBA8 bytes for WGPU upload.

    The viewport TextureCache and ResourceManager already normalize KotOR TPC/TGA
    images to bottom-up orientation. WGPU samples with the same UV convention as
    the ModernGL path, so this adapter does not flip rows during upload.
    """

    if texture_data is None or texture_data.source is None:
        return None
    try:
        image = texture_data.source
        rgba = image.convert("RGBA") if hasattr(image, "convert") else None
        if rgba is None:
            return None
        width, height = rgba.size
        if width <= 0 or height <= 0:
            return None
        return int(width), int(height), rgba.tobytes()
    except Exception:
        return None


def _node_uv_array(node, attr: str, count: int):
    import numpy as np

    raw = getattr(node, attr, []) or []
    if not raw:
        return np.full((count, 2), 0.5, dtype=np.float32)
    try:
        arr = np.asarray(raw, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] < 2:
            return np.full((count, 2), 0.5, dtype=np.float32)
        arr = arr[:, :2]
        if len(arr) < count:
            arr = np.vstack([arr, np.full((count - len(arr), 2), 0.5, dtype=np.float32)])
        return arr[:count]
    except Exception:
        return np.full((count, 2), 0.5, dtype=np.float32)


def _material_data(node, textures: dict) -> MaterialRenderData:
    diffuse_name = _clean_tex_name(getattr(node, "texture", "") or "")
    lightmap_name = _clean_tex_name(
        getattr(node, "_gr_baked_lightmap_preview_name", "")
        or getattr(node, "lightmap", "")
        or ""
    )
    diffuse_texture = _texture_data(diffuse_name, textures)
    lightmap_texture = None
    if _node_has_lightmap(node, lightmap_name):
        lightmap_texture = _texture_data(lightmap_name, textures)
    base_color = _material_color(node)
    alpha_cutoff = _clamp01(float(getattr(node, "txi_alpha_test", 0.0) or 0.0) or 0.5)
    alpha_mode = _alpha_mode(node)
    double_sided = bool(
        getattr(node, "is_dangly", False)
        or int(getattr(node, "transparency_hint", 0) or 0) in (1, 2)
        or alpha_mode == "BLEND"
    )
    material_id = "|".join(
        [
            str(id(node)),
            diffuse_name,
            lightmap_name,
            alpha_mode,
            f"{alpha_cutoff:.3f}",
            str(double_sided),
        ]
    )
    material_rev = (
        int(getattr(node, "_gr_revision", 0) or 0),
        id(diffuse_texture.source) if diffuse_texture is not None else 0,
        id(lightmap_texture.source) if lightmap_texture is not None else 0,
        hash((base_color, alpha_mode, alpha_cutoff, double_sided)),
    )
    return MaterialRenderData(
        material_id=material_id,
        name=str(getattr(node, "name", "") or material_id),
        diffuse_texture_id=diffuse_texture.texture_id if diffuse_texture is not None else "",
        diffuse_texture_path=diffuse_name,
        diffuse_texture_data=diffuse_texture,
        lightmap_texture_id=lightmap_texture.texture_id if lightmap_texture is not None else "",
        lightmap_texture_path=lightmap_name,
        lightmap_texture_data=lightmap_texture,
        base_color_rgba=base_color,
        alpha_mode=alpha_mode,
        alpha_cutoff=alpha_cutoff,
        double_sided=double_sided,
        unlit=any(abs(float(c)) > 1e-6 for c in tuple(getattr(node, "selfillum", (0.0, 0.0, 0.0)) or ())[:3]),
        has_transparency=alpha_mode in {"MASK", "CUTOUT", "BLEND"} or base_color[3] < 0.999,
        source_revision=material_rev,
    )


def _texture_data(name: str, textures: dict) -> TextureRenderData | None:
    if not name:
        return None
    source = textures.get(name.lower()) or textures.get(name)
    if source is None:
        return TextureRenderData(
            texture_id=name.lower(),
            name=name,
            source=None,
            source_revision=(0, 0, 0),
        )
    width, height = getattr(source, "size", (0, 0))
    revision = (id(source), int(width or 0), int(height or 0))
    return TextureRenderData(
        texture_id=f"{name.lower()}:{revision[0]}",
        name=name.lower(),
        source=source,
        source_revision=revision,
    )


def _node_has_lightmap(node, lightmap_name: str) -> bool:
    if not lightmap_name:
        return False
    if len(getattr(node, "uvs_lm", []) or []) <= 0:
        return False
    return bool(
        getattr(node, "has_lightmap", False)
        or getattr(node, "_gr_baked_lightmap_preview_name", "")
        or int(getattr(node, "tex_count", 1) or 1) >= 2
    )


def _alpha_mode(node) -> str:
    node_alpha = _clamp01(float(getattr(node, "alpha", 1.0) or 1.0))
    txi_blend = int(getattr(node, "txi_blending", 0) or 0)
    alpha_test = float(getattr(node, "txi_alpha_test", 0.0) or 0.0)
    transparency_hint = int(getattr(node, "transparency_hint", 0) or 0)
    if txi_blend == 2 or (txi_blend == 0 and alpha_test > 0.0 and transparency_hint > 0):
        return "MASK"
    if (
        node_alpha < 0.999
        or float(getattr(node, "txi_wateralpha", 1.0) or 1.0) < 0.999
        or bool(getattr(node, "txi_decal", False))
        or txi_blend in (1, 3)
    ):
        return "BLEND"
    return "OPAQUE"


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
    alpha *= float(getattr(node, "txi_wateralpha", 1.0) or 1.0)
    return (_clamp01(r), _clamp01(g), _clamp01(b), _clamp01(alpha))


def _node_revision(node) -> tuple[int, int, int]:
    return (
        len(getattr(node, "vertices", getattr(node, "verts", [])) or []),
        len(getattr(node, "faces", []) or []),
        int(getattr(node, "_gr_revision", 0) or 0),
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clean_tex_name(value: str) -> str:
    text = str(value or "").replace("\x00", "").strip().lower()
    if text in {"", "null", "none"}:
        return ""
    for ext in (".tga", ".tpc", ".dds", ".png", ".bmp"):
        if text.endswith(ext):
            text = text[: -len(ext)]
            break
    return text
