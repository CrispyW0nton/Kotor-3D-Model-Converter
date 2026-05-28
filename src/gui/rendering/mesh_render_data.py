"""Renderer-neutral mesh/material extraction for lightweight WGPU drawing."""

from __future__ import annotations

import math
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
    blend_mode: str
    sprite_alpha_source: int
    sprite_glow: float
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
    bone_indices: object | None = None
    bone_weights: object | None = None
    max_influences: int = 0
    skeleton_id: int = 0
    skin_revision: int = 0
    bind_shape_matrix: object | None = None
    is_skinned: bool = False
    skinning_cpu_fallback: bool = False
    skinning_warning: str = ""


def iter_mesh_render_data(
    model,
    *,
    anim_pose=None,
    anim_base_pose=None,
    textures: dict | None = None,
    allow_cpu_skinning: bool = True,
) -> Iterable[MeshRenderData]:
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
            (
                positions,
                normals,
                uvs0,
                uvs1,
                indices,
                vbo_bone_indices,
                vbo_bone_weights,
                world_matrix,
            ) = _extract_node_arrays(node, anim_pose=anim_pose)
        except Exception:
            continue
        if positions is None or len(positions) == 0:
            continue
        skinning = _extract_skinning(
            node,
            len(positions),
            skeleton_id=id(model),
            bone_indices=vbo_bone_indices,
            bone_weights=vbo_bone_weights,
        )
        skinning_cpu_fallback = False
        if allow_cpu_skinning and anim_pose is not None and getattr(skinning, "is_skinned", False):
            try:
                from src.gui.rendering.skeleton_render_data import cpu_skin_vbo_arrays

                skinned_positions, skinned_normals = cpu_skin_vbo_arrays(
                    node,
                    positions,
                    normals,
                    skinning,
                    anim_pose,
                    model=model,
                )
                if skinned_positions is not positions:
                    positions = skinned_positions
                    normals = skinned_normals
                    skinning_cpu_fallback = True
            except Exception:
                pass
        material = _material_data(node, textures)
        source_revision = _node_revision(node)
        if getattr(skinning, "is_skinned", False):
            skin_lbs_input_mode = 1 if anim_pose is not None else 0
            source_revision = (
                *source_revision,
                int(getattr(skinning, "skin_revision", 0) or 0),
                skin_lbs_input_mode,
            )
        if skinning_cpu_fallback:
            source_revision = (*source_revision, int(round(float(getattr(anim_pose, "time", 0.0) or 0.0) * 1000.0)))
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
                world_matrix=np.asarray(world_matrix, dtype=np.float32),
                source_revision=source_revision,
                bone_indices=getattr(skinning, "bone_indices", None),
                bone_weights=getattr(skinning, "bone_weights", None),
                max_influences=int(getattr(skinning, "max_influences", 0) or 0),
                skeleton_id=int(getattr(skinning, "skeleton_id", 0) or 0),
                skin_revision=int(getattr(skinning, "skin_revision", 0) or 0),
                bind_shape_matrix=getattr(skinning, "bind_shape_matrix", None),
                is_skinned=bool(getattr(skinning, "is_skinned", False)),
                skinning_cpu_fallback=bool(skinning_cpu_fallback),
                skinning_warning=str(getattr(skinning, "warning", "") or ""),
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
    if bool(getattr(node, "is_saber", False)):
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

    is_skin = bool(getattr(node, "is_skin", False))
    world_pos, world_orient = _node_world_transform(node, anim_pose=anim_pose)
    world_matrix = node_world_matrix(node, anim_pose=anim_pose)
    if _build_vbo_data is not None:
        skin_can_lbs = bool(
            anim_pose is not None
            and is_skin
            and getattr(node, "bone_map", None)
            and getattr(node, "skin_data", None)
        )
        vbo_world_pos = world_pos
        vbo_world_orient = world_orient
        if not is_skin:
            vbo_world_pos = (0.0, 0.0, 0.0)
            vbo_world_orient = (0.0, 0.0, 0.0, 1.0)
        vdata, idx_arr = _build_vbo_data(
            node,
            vbo_world_pos,
            vbo_world_orient,
            anim_pose_node=None,
            apply_skin_node_transform_for_bind=not skin_can_lbs,
        )
        if vdata is not None:
            positions = np.asarray(vdata[:, 0:3], dtype=np.float32)
            normals = np.asarray(vdata[:, 3:6], dtype=np.float32) if vdata.shape[1] >= 6 else None
            uvs0 = np.asarray(vdata[:, 6:8], dtype=np.float32) if vdata.shape[1] >= 8 else None
            uvs1 = np.asarray(vdata[:, 8:10], dtype=np.float32) if vdata.shape[1] >= 10 else None
            indices = np.asarray(idx_arr, dtype=np.uint32) if idx_arr is not None and len(idx_arr) else None
            normals = smooth_render_normals(positions, normals, indices)
            bone_indices = None
            bone_weights = None
            if getattr(node, "is_skin", False) and vdata.shape[1] >= 22:
                bone_indices = np.rint(vdata[:, 14:18]).astype(np.uint16)
                bone_weights = np.asarray(vdata[:, 18:22], dtype=np.float32)
            return positions, normals, uvs0, uvs1, indices, bone_indices, bone_weights, world_matrix

    verts = np.asarray(getattr(node, "vertices", getattr(node, "verts", [])) or [], dtype=np.float32)
    if verts.ndim != 2 or verts.shape[1] != 3:
        return None, None, None, None, None, None, None, world_matrix
    normals = np.asarray(getattr(node, "normals", []) or [], dtype=np.float32)
    if normals.ndim != 2 or normals.shape[1] != 3 or len(normals) != len(verts):
        normals = None
    uvs0 = _node_uv_array(node, "uvs", len(verts))
    uvs1 = _node_uv_array(node, "uvs_lm", len(verts))
    faces = getattr(node, "faces", []) or []
    indices = np.asarray([int(i) for face in faces for i in tuple(face)[:3]], dtype=np.uint32)
    normals = smooth_render_normals(verts, normals, indices)
    return verts, normals, uvs0, uvs1, indices, None, None, world_matrix


def smooth_render_normals(
    positions,
    normals=None,
    indices=None,
    *,
    crease_degrees: float = 62.0,
    position_epsilon: float = 1.0e-5,
):
    """Return render normals smoothed across compatible coincident vertices.

    KotOR binary meshes often duplicate positions at UV/lightmap seams. Averaging
    compatible duplicate normals removes artificial D3D faceting while the crease
    test preserves intentional hard edges, which is the smoothing-group behavior
    WGPU needs before buffer upload.
    """

    import numpy as np

    pos = np.asarray(positions, dtype=np.float32)
    if pos.ndim != 2 or pos.shape[1] != 3 or len(pos) == 0:
        return normals

    authored = _coerce_normal_array(normals, len(pos))
    face_accum = _area_weighted_normal_accum(pos, indices)
    base = authored if authored is not None else face_accum
    base = _normalize_rows(base, fallback=face_accum)

    buckets: dict[tuple[int, int, int], list[int]] = {}
    scale = 1.0 / max(float(position_epsilon), 1.0e-9)
    for idx, vertex in enumerate(pos):
        key = tuple(int(round(float(component) * scale)) for component in vertex[:3])
        buckets.setdefault(key, []).append(idx)

    cos_crease = math.cos(math.radians(max(0.0, min(180.0, float(crease_degrees)))))
    smoothed = base.copy()
    weights = np.linalg.norm(face_accum, axis=1)
    weights = np.where(weights > 1.0e-8, weights, 1.0)
    for members in buckets.values():
        if len(members) <= 1:
            continue
        member_normals = base[members]
        for member in members:
            ref = base[member]
            dots = member_normals @ ref
            compatible = [members[i] for i, dot in enumerate(dots) if float(dot) >= cos_crease]
            if len(compatible) <= 1:
                continue
            accum = np.zeros(3, dtype=np.float64)
            for other in compatible:
                accum += base[other].astype(np.float64) * float(weights[other])
            length = float(np.linalg.norm(accum))
            if length > 1.0e-8:
                smoothed[member] = (accum / length).astype(np.float32)

    return _normalize_rows(smoothed, fallback=base).astype(np.float32)


def _coerce_normal_array(normals, count: int):
    import numpy as np

    if normals is None:
        return None
    try:
        arr = np.asarray(normals, dtype=np.float32)
    except Exception:
        return None
    if arr.ndim != 2 or arr.shape[1] < 3 or len(arr) != count:
        return None
    arr = arr[:, :3]
    if not np.all(np.isfinite(arr)):
        arr = arr.copy()
        arr[~np.all(np.isfinite(arr), axis=1)] = 0.0
    if np.count_nonzero(np.linalg.norm(arr, axis=1) > 1.0e-8) == 0:
        return None
    return arr


def _area_weighted_normal_accum(positions, indices):
    import numpy as np

    pos = np.asarray(positions, dtype=np.float64)
    accum = np.zeros((len(pos), 3), dtype=np.float64)
    if indices is None:
        tri_indices = np.arange(len(pos), dtype=np.uint32)
    else:
        tri_indices = np.asarray(indices, dtype=np.uint32).reshape(-1)
    usable = (len(tri_indices) // 3) * 3
    for i0, i1, i2 in tri_indices[:usable].reshape((-1, 3)):
        if int(i0) >= len(pos) or int(i1) >= len(pos) or int(i2) >= len(pos):
            continue
        if i0 == i1 or i1 == i2 or i0 == i2:
            continue
        v0 = pos[int(i0)]
        v1 = pos[int(i1)]
        v2 = pos[int(i2)]
        normal = np.cross(v1 - v0, v2 - v0)
        if float(np.dot(normal, normal)) <= 1.0e-18:
            continue
        accum[int(i0)] += normal
        accum[int(i1)] += normal
        accum[int(i2)] += normal
    return accum.astype(np.float32)


def _normalize_rows(values, *, fallback=None):
    import numpy as np

    arr = np.asarray(values, dtype=np.float32).copy()
    if arr.ndim != 2 or arr.shape[1] != 3:
        return arr
    fallback_arr = np.asarray(fallback, dtype=np.float32) if fallback is not None else None
    for idx in range(len(arr)):
        row = arr[idx]
        length = float(np.linalg.norm(row))
        if length <= 1.0e-8 and fallback_arr is not None and idx < len(fallback_arr):
            row = fallback_arr[idx]
            length = float(np.linalg.norm(row))
        if length <= 1.0e-8:
            arr[idx] = (0.0, 0.0, 1.0)
        else:
            arr[idx] = row / length
    return arr


def _extract_skinning(
    node,
    vertex_count: int,
    *,
    skeleton_id: int = 0,
    bone_indices=None,
    bone_weights=None,
):
    try:
        from src.gui.rendering.skeleton_render_data import extract_skinning_arrays

        return extract_skinning_arrays(
            node,
            vertex_count,
            skeleton_id=skeleton_id,
            bone_indices=bone_indices,
            bone_weights=bone_weights,
        )
    except Exception:
        from types import SimpleNamespace

        return SimpleNamespace(
            bone_indices=None,
            bone_weights=None,
            max_influences=0,
            skeleton_id=skeleton_id,
            skin_revision=0,
            bind_shape_matrix=None,
            is_skinned=False,
            warning="skin adapter unavailable",
        )


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
    blend_mode = _blend_mode(node)
    sprite_alpha_source = _sprite_alpha_source(node)
    sprite_glow = _sprite_glow(node)
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
            blend_mode,
            f"{alpha_cutoff:.3f}",
            str(sprite_alpha_source),
            f"{sprite_glow:.3f}",
            str(double_sided),
        ]
    )
    material_rev = (
        int(getattr(node, "_gr_revision", 0) or 0),
        id(diffuse_texture.source) if diffuse_texture is not None else 0,
        id(lightmap_texture.source) if lightmap_texture is not None else 0,
        hash((base_color, alpha_mode, blend_mode, alpha_cutoff, sprite_alpha_source, round(sprite_glow, 3), double_sided)),
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
        blend_mode=blend_mode,
        sprite_alpha_source=sprite_alpha_source,
        sprite_glow=sprite_glow,
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
    sprite_alpha = _sprite_alpha_source(node)
    if txi_blend == 2 or (txi_blend == 0 and transparency_hint > 0):
        return "MASK"
    if (
        node_alpha < 0.999
        or float(getattr(node, "txi_wateralpha", 1.0) or 1.0) < 0.999
        or bool(getattr(node, "txi_decal", False))
        or txi_blend in (1, 3)
        or sprite_alpha
    ):
        return "BLEND"
    return "OPAQUE"


def _blend_mode(node) -> str:
    explicit = str(getattr(node, "_gr_sprite_render_mode", "") or "").lower()
    if explicit == "additive":
        return "ADDITIVE"
    if explicit == "lighten":
        return "LIGHTEN"
    if explicit in {"opaque", "cutout", "blend"}:
        return "ALPHA"
    txi_blend = int(getattr(node, "txi_blending", 0) or 0)
    if _sprite_alpha_source(node) and _sprite_glow(node) > 0.001:
        return "LIGHTEN"
    if txi_blend == 1:
        return "ADDITIVE"
    if txi_blend == 3:
        return "LIGHTEN"
    return "ALPHA"


def _sprite_alpha_source(node) -> int:
    source = str(getattr(node, "_gr_sprite_alpha_source", "") or "").lower()
    if source in {"luminance", "brightness", "matte", "black_key"}:
        return 1
    if _is_saber_hilt(node):
        return 0
    text = f"{getattr(node, 'name', '')} {getattr(node, 'texture', '')}".lower()
    return 1 if any(token in text for token in ("saber", "sabre", "lsabre", "blade", "glow", "flare", "beam")) else 0


def _sprite_glow(node) -> float:
    explicit = getattr(node, "_gr_sprite_glow", None)
    if explicit is not None:
        try:
            return max(0.0, min(4.0, float(explicit)))
        except Exception:
            return 0.0
    if _is_saber_hilt(node):
        return 0.0
    text = f"{getattr(node, 'name', '')} {getattr(node, 'texture', '')}".lower()
    return 1.6 if any(token in text for token in ("saber", "sabre", "lsabre", "blade", "glow", "flare", "beam")) else 0.0


def _is_saber_hilt(node) -> bool:
    name = str(getattr(node, "name", "") or "").lower()
    texture = str(getattr(node, "texture", "") or "").lower()
    if texture.startswith(("w_lghtsbr", "w_shortsbr", "w_dblsbr")):
        return True
    return name.startswith(("lghtsbr", "lshandle")) or "handle" in name


def _node_world_transform(node, *, anim_pose=None) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    if anim_pose is not None:
        try:
            return _animated_node_world_transform(node, anim_pose)
        except Exception:
            pass
    try:
        wp, wo = node.world_transform()
        return tuple(float(v) for v in wp[:3]), tuple(float(v) for v in wo[:4])
    except Exception:
        try:
            wp = node.world_position()
            return tuple(float(v) for v in wp[:3]), (0.0, 0.0, 0.0, 1.0)
        except Exception:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)


def node_world_matrix(node, *, anim_pose=None):
    import numpy as np

    pos, quat = _node_world_transform(node, anim_pose=anim_pose)
    x, y, z, w = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
    length_sq = x * x + y * y + z * z + w * w
    if length_sq > 1e-9:
        inv_len = 1.0 / math.sqrt(length_sq)
        x, y, z, w = x * inv_len, y * inv_len, z * inv_len, w * inv_len
    else:
        x, y, z, w = 0.0, 0.0, 0.0, 1.0
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    matrix = np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), float(pos[0])],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), float(pos[1])],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), float(pos[2])],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return matrix


def _animated_node_world_transform(node, anim_pose) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    import math

    from src.core.qt_core.geometry.model_data import (
        _quat_mul,
        _quat_normalize,
        _quat_normalize_bind,
        _quat_rotate,
    )

    cache = getattr(anim_pose, "_gr_mesh_world_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            setattr(anim_pose, "_gr_mesh_world_cache", cache)
        except Exception:
            pass
    cached = cache.get(id(node))
    if cached is not None:
        return cached

    chain = []
    current = node
    visited: set[int] = set()
    while current is not None:
        node_id = id(current)
        if node_id in visited or len(chain) > 512:
            break
        visited.add(node_id)
        chain.append(current)
        current = getattr(current, "parent", None)
    chain.reverse()

    wx = wy = wz = 0.0
    parent_orientation = [0.0, 0.0, 0.0, 1.0]
    pose_nodes = getattr(anim_pose, "nodes", {}) or {}
    pose_nodes_by_index = getattr(anim_pose, "nodes_by_index", {}) or {}
    duplicate_node_names = set(getattr(anim_pose, "duplicate_node_names", set()) or set())
    last_i = len(chain) - 1
    for index, chain_node in enumerate(chain):
        is_leaf = index == last_i
        node_name_key = str(getattr(chain_node, "name", "") or "").lower()
        pose_node = None
        try:
            pose_node = pose_nodes_by_index.get(int(getattr(chain_node, "index", -1)))
        except Exception:
            pose_node = None
        if pose_node is None and node_name_key not in duplicate_node_names:
            pose_node = pose_nodes.get(node_name_key)
        if pose_node is not None:
            lx, ly, lz = getattr(pose_node, "position", getattr(chain_node, "position", (0.0, 0.0, 0.0)))
            if not (math.isfinite(lx) and math.isfinite(ly) and math.isfinite(lz)):
                lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
            rot = list(getattr(pose_node, "rotation", getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0))))
            if not all(math.isfinite(v) for v in rot):
                rot = list(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            if is_leaf:
                length_sq = rot[0] * rot[0] + rot[1] * rot[1] + rot[2] * rot[2] + rot[3] * rot[3]
                node_rot = [rot[0] / math.sqrt(length_sq), rot[1] / math.sqrt(length_sq), rot[2] / math.sqrt(length_sq), rot[3] / math.sqrt(length_sq)] if length_sq > 1e-9 else [0.0, 0.0, 0.0, 1.0]
            else:
                node_rot = _quat_normalize_bind(rot)
        else:
            lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
            rot = list(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            node_rot = _quat_normalize(rot) if is_leaf else _quat_normalize_bind(rot)

        rx, ry, rz = _quat_rotate(parent_orientation, (lx, ly, lz))
        wx += rx
        wy += ry
        wz += rz
        parent_orientation = _quat_mul(parent_orientation, node_rot)

    if not (math.isfinite(wx) and math.isfinite(wy) and math.isfinite(wz)):
        wp, wo = node.world_transform()
        result = (tuple(float(v) for v in wp[:3]), tuple(float(v) for v in wo[:4]))
    else:
        wo = tuple(parent_orientation)
        length_sq = sum(float(v) * float(v) for v in wo[:4])
        if length_sq > 1e-9 and abs(length_sq - 1.0) > 1e-4:
            scale = 1.0 / math.sqrt(length_sq)
            wo = tuple(float(v) * scale for v in wo[:4])
        result = ((float(wx), float(wy), float(wz)), tuple(float(v) for v in wo[:4]))
    cache[id(node)] = result
    return result


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
