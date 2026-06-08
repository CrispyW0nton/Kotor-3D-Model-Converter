"""Renderer-neutral skeleton, pose, and skin helpers for viewport backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class BoneRenderData:
    bone_id: int
    node_id: int
    name: str
    parent_id: int | None
    local_matrix: object | None
    world_matrix: object | None
    bind_matrix: object | None
    inverse_bind_matrix: object | None
    length: float
    head_position: tuple[float, float, float]
    tail_position: tuple[float, float, float]
    selected: bool = False
    hovered: bool = False
    visible: bool = True
    locked: bool = False
    colour_hint: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class SkeletonRenderData:
    skeleton_id: int
    bones: tuple[BoneRenderData, ...] = ()
    root_bone_ids: tuple[int, ...] = ()
    selected_bone_ids: tuple[int, ...] = ()
    hovered_bone_id: int | None = None
    revision: int = 0
    show_names: bool = False
    show_axes: bool = False
    show_dots: bool = True
    show_links: bool = True
    show_joint_limits: bool = False


@dataclass(frozen=True)
class AnimationPlaybackState:
    active_clip_id: str = ""
    active_clip_name: str = ""
    time_seconds: float = 0.0
    frame_index: int = 0
    duration_seconds: float = 0.0
    fps: float = 30.0
    playing: bool = False
    looping: bool = True
    playback_speed: float = 1.0
    pose_revision: int = 0


@dataclass(frozen=True)
class SkeletonPose:
    skeleton_id: int
    bone_matrices: object | None = None
    inverse_bind_matrices: object | None = None
    skin_matrices: object | None = None
    world_bone_matrices: object | None = None
    revision: int = 0


@dataclass(frozen=True)
class SkinningArrays:
    bone_indices: object | None
    bone_weights: object | None
    max_influences: int = 0
    skeleton_id: int = 0
    skin_revision: int = 0
    bind_shape_matrix: object | None = None
    is_skinned: bool = False
    warning: str = ""


def build_skeleton_render_data(
    model,
    *,
    anim_pose=None,
    selected_node=None,
    selected_nodes: Iterable[object] | None = None,
    hovered_node=None,
    show_dots: bool = True,
    show_links: bool = True,
    show_names: bool = False,
    show_axes: bool = False,
) -> SkeletonRenderData | None:
    """Create backend-neutral skeleton overlay data from a KotOR model tree."""

    if model is None or getattr(model, "root_node", None) is None:
        return None
    nodes = _model_nodes(model)
    bone_nodes = [node for node in nodes if _is_bone_node(node)]
    if not bone_nodes:
        return None

    node_to_bone_id = {id(node): idx for idx, node in enumerate(bone_nodes)}
    selected_ids = {id(node) for node in (selected_nodes or ()) if node is not None}
    if selected_node is not None:
        selected_ids.add(id(selected_node))
    hovered_id = id(hovered_node) if hovered_node is not None else 0

    bones: list[BoneRenderData] = []
    root_ids: list[int] = []
    selected_bone_ids: list[int] = []
    hovered_bone_id: int | None = None
    world_positions: dict[int, tuple[float, float, float]] = {}

    for bone_id, node in enumerate(bone_nodes):
        parent = _nearest_bone_ancestor(node)
        parent_id = node_to_bone_id.get(id(parent)) if parent is not None else None
        if parent_id is None:
            root_ids.append(bone_id)
        head = _node_world_position(node, anim_pose)
        tail = head
        if parent is not None:
            tail = _node_world_position(parent, anim_pose)
        world_positions[id(node)] = head
        selected = id(node) in selected_ids
        hovered = id(node) == hovered_id
        if selected:
            selected_bone_ids.append(bone_id)
        if hovered:
            hovered_bone_id = bone_id
        bones.append(
            BoneRenderData(
                bone_id=bone_id,
                node_id=id(node),
                name=str(getattr(node, "name", "") or bone_id),
                parent_id=parent_id,
                local_matrix=None,
                world_matrix=None,
                bind_matrix=None,
                inverse_bind_matrix=None,
                length=_distance(head, tail),
                head_position=head,
                tail_position=tail,
                selected=selected,
                hovered=hovered,
                visible=True,
                locked=bool(getattr(node, "_gr_scene_object_locked", False)),
                colour_hint=_bone_colour_hint(node, selected=selected, hovered=hovered),
            )
        )

    pose_time = float(getattr(anim_pose, "time", 0.0) or 0.0) if anim_pose is not None else 0.0
    revision = hash(
        (
            id(model),
            len(bones),
            int(round(pose_time * 1000.0)),
            tuple(selected_bone_ids),
            hovered_bone_id,
            bool(show_dots),
            bool(show_links),
        )
    ) & 0x7FFFFFFF
    return SkeletonRenderData(
        skeleton_id=id(model),
        bones=tuple(bones),
        root_bone_ids=tuple(root_ids),
        selected_bone_ids=tuple(selected_bone_ids),
        hovered_bone_id=hovered_bone_id,
        revision=revision,
        show_names=bool(show_names),
        show_axes=bool(show_axes),
        show_dots=bool(show_dots),
        show_links=bool(show_links),
    )


def extract_skinning_arrays(
    node,
    vertex_count: int,
    *,
    skeleton_id: int = 0,
    bone_indices=None,
    bone_weights=None,
) -> SkinningArrays:
    """Return normalized up-to-four influence skin arrays for one mesh node."""

    import numpy as np

    if node is None or vertex_count <= 0 or not bool(getattr(node, "is_skin", False)):
        return SkinningArrays(None, None, skeleton_id=skeleton_id)
    if bone_indices is not None and bone_weights is not None:
        indices = np.asarray(bone_indices, dtype=np.uint16)
        weights = np.asarray(bone_weights, dtype=np.float32)
        if indices.shape == weights.shape and indices.ndim == 2 and indices.shape[1] >= 4:
            indices = np.ascontiguousarray(indices[:vertex_count, :4], dtype=np.uint16)
            weights = np.ascontiguousarray(weights[:vertex_count, :4], dtype=np.float32)
            if len(indices) == vertex_count:
                _normalize_weight_rows(weights)
                return SkinningArrays(
                    bone_indices=indices,
                    bone_weights=weights,
                    max_influences=4,
                    skeleton_id=skeleton_id,
                    skin_revision=_skin_revision(node, vertex_count),
                    bind_shape_matrix=np.eye(4, dtype=np.float32),
                    is_skinned=True,
                )
    skin_data = list(getattr(node, "skin_data", []) or [])
    if not skin_data:
        return SkinningArrays(None, None, skeleton_id=skeleton_id)

    indices = np.zeros((vertex_count, 4), dtype=np.uint16)
    weights = np.zeros((vertex_count, 4), dtype=np.float32)
    warning = ""
    for vi in range(vertex_count):
        influences = []
        if vi < len(skin_data):
            influences = list(getattr(skin_data[vi], "influences", []) or [])
        packed = []
        for influence in influences:
            try:
                weight = float(getattr(influence, "weight", 0.0) or 0.0)
                bone_index = int(getattr(influence, "bone_index", 0) or 0)
            except Exception:
                continue
            if weight > 0.0 and bone_index >= 0:
                packed.append((weight, bone_index))
        packed.sort(key=lambda item: item[0], reverse=True)
        packed = packed[:4]
        total = sum(weight for weight, _bone_index in packed)
        if total <= 1e-8:
            indices[vi, 0] = 0
            weights[vi, 0] = 1.0
            if influences:
                warning = "invalid skin weights normalized to bind-pose fallback"
            continue
        for slot, (weight, bone_index) in enumerate(packed):
            indices[vi, slot] = max(0, min(65535, bone_index))
            weights[vi, slot] = float(weight / total)

    return SkinningArrays(
        bone_indices=indices,
        bone_weights=weights,
        max_influences=4,
        skeleton_id=skeleton_id,
        skin_revision=_skin_revision(node, vertex_count),
        bind_shape_matrix=np.eye(4, dtype=np.float32),
        is_skinned=True,
        warning=warning,
    )


def cpu_skin_vbo_arrays(
    node,
    positions,
    normals,
    skinning: SkinningArrays,
    anim_pose,
    model=None,
) -> tuple[object, object | None]:
    """Apply the same per-skin palette contract used by the ModernGL shader."""

    if node is None or anim_pose is None or not bool(getattr(skinning, "is_skinned", False)):
        return positions, normals
    if skinning.bone_indices is None or skinning.bone_weights is None:
        return positions, normals
    try:
        import numpy as np
        from src.core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES
    except Exception:
        return positions, normals

    source_model = model or _root_model_from_node(node)
    if source_model is None:
        return positions, normals
    try:
        uploader = MatrixPaletteUploader(max_bones=MAX_BONES)
        uploader.build_inverse_bind_pose(source_model)
        uploader.compute_skin_node_palette(node, anim_pose)
        palette = uploader.as_numpy_array()
        if palette is None or len(palette) == 0:
            return positions, normals

        pos = np.asarray(positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] != 3:
            return positions, normals
        count = min(len(pos), len(skinning.bone_indices), len(skinning.bone_weights))
        if count <= 0:
            return positions, normals

        bone_ids = np.asarray(skinning.bone_indices[:count, :4], dtype=np.int64)
        bone_ids = np.clip(bone_ids, 0, len(palette) - 1)
        weights = np.asarray(skinning.bone_weights[:count, :4], dtype=np.float32)
        bind_pos = np.concatenate([pos[:count], np.ones((count, 1), dtype=np.float32)], axis=1)
        skinned_pos = np.zeros((count, 4), dtype=np.float32)
        skinned_norm = None

        norm_arr = None
        if normals is not None:
            norm_arr = np.asarray(normals, dtype=np.float32)
            if norm_arr.ndim == 2 and norm_arr.shape[1] == 3 and len(norm_arr) >= count:
                skinned_norm = np.zeros((count, 3), dtype=np.float32)

        for slot in range(4):
            ids = bone_ids[:, slot]
            w = weights[:, slot].reshape(count, 1)
            transformed = np.einsum("nij,nj->ni", palette[ids], bind_pos)
            skinned_pos += transformed * w
            if skinned_norm is not None and norm_arr is not None:
                mats3 = palette[ids, :3, :3]
                transformed_norm = np.einsum("nij,nj->ni", mats3, norm_arr[:count])
                skinned_norm += transformed_norm * w

        out_pos = np.array(pos, dtype=np.float32, copy=True)
        out_pos[:count, :] = skinned_pos[:, :3]
        out_norm = normals
        if skinned_norm is not None and norm_arr is not None:
            lengths = np.linalg.norm(skinned_norm, axis=1, keepdims=True)
            lengths = np.where(lengths < 1e-8, 1.0, lengths)
            fixed = np.array(norm_arr, dtype=np.float32, copy=True)
            fixed[:count, :] = skinned_norm / lengths
            out_norm = fixed
        return out_pos, out_norm
    except Exception:
        return positions, normals


def cpu_skin_positions(node, positions, skinning: SkinningArrays, anim_pose, model=None, anim_base_pose=None):
    """CPU LBS fallback using the existing GhostRigger skin palette math."""

    if node is None or anim_pose is None or not bool(getattr(skinning, "is_skinned", False)):
        return positions
    if skinning.bone_indices is None or skinning.bone_weights is None:
        return positions
    try:
        import numpy as np
        from src.core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES
    except Exception:
        return positions

    source_model = model or _root_model_from_node(node)
    if source_model is None:
        return positions
    try:
        uploader = MatrixPaletteUploader(max_bones=MAX_BONES)
        uploader.build_inverse_bind_pose(source_model)
        uploader.compute_skin_node_palette(
            node,
            anim_pose,
            anim_base_pose=anim_base_pose,
        )
        palette = uploader.as_numpy_array()
        if palette is None or len(palette) == 0:
            return positions
        pos = np.asarray(getattr(node, "vertices", positions), dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] != 3:
            pos = np.asarray(positions, dtype=np.float32)
        count = min(len(pos), len(skinning.bone_indices), len(skinning.bone_weights))
        if count <= 0:
            return positions
        out = np.array(pos, dtype=np.float32, copy=True)
        bind = np.concatenate([pos[:count], np.ones((count, 1), dtype=np.float32)], axis=1)
        skinned = np.zeros((count, 4), dtype=np.float32)
        for slot in range(4):
            bone_ids = np.asarray(skinning.bone_indices[:count, slot], dtype=np.int64)
            bone_ids = np.clip(bone_ids, 0, len(palette) - 1)
            weights = np.asarray(skinning.bone_weights[:count, slot], dtype=np.float32).reshape(count, 1)
            transformed = np.einsum("nij,nj->ni", palette[bone_ids], bind)
            skinned += transformed * weights
        out[:count, :] = skinned[:, :3]
        return out
    except Exception:
        return positions


def _normalize_weight_rows(weights) -> None:
    import numpy as np

    sums = np.sum(weights.astype(np.float64), axis=1)
    for row, total in enumerate(sums):
        if total > 1e-8:
            weights[row, :] = weights[row, :] / float(total)
        else:
            weights[row, :] = 0.0
            weights[row, 0] = 1.0


def _model_nodes(model) -> list:
    try:
        return list(model.all_nodes())
    except Exception:
        return list(getattr(model, "nodes", []) or [])


def _is_bone_node(node) -> bool:
    if node is None or bool(getattr(node, "_hide_skeleton_overlay", False)):
        return False
    name = str(getattr(node, "name", "") or "").lower()
    if name.startswith("ik_") or name in {"interaction", "center_of_mass"} or "hook" in name:
        return False
    if bool(getattr(node, "is_dummy", False)):
        return True
    if getattr(node, "parent", None) is None:
        return True
    if bool(getattr(node, "is_mesh", False)) and not bool(getattr(node, "is_skin", False)):
        return name.endswith(("_g", "_g0", "_dum", "dummy"))
    return False


def _nearest_bone_ancestor(node):
    parent = getattr(node, "parent", None)
    visited: set[int] = set()
    while parent is not None:
        parent_id = id(parent)
        if parent_id in visited:
            return None
        visited.add(parent_id)
        if _is_bone_node(parent):
            return parent
        parent = getattr(parent, "parent", None)
    return None


def _node_world_position(node, anim_pose=None) -> tuple[float, float, float]:
    if anim_pose is not None:
        return _animated_world_position(node, anim_pose)
    external = getattr(node, "external_world_position", None)
    if external is not None:
        try:
            return tuple(float(v) for v in tuple(external)[:3])
        except Exception:
            pass
    try:
        return tuple(float(v) for v in node.bone_world_position()[:3])
    except Exception:
        try:
            return tuple(float(v) for v in node.world_position()[:3])
        except Exception:
            return (0.0, 0.0, 0.0)


def _animated_world_position(node, anim_pose) -> tuple[float, float, float]:
    try:
        from src.core.geometry.model_data import _quat_mul, _quat_normalize_bind, _quat_rotate
    except Exception:
        return _node_world_position(node, None)

    chain = []
    current = node
    visited: set[int] = set()
    while current is not None:
        current_id = id(current)
        if current_id in visited or len(chain) > 512:
            break
        visited.add(current_id)
        chain.append(current)
        current = getattr(current, "parent", None)
    chain.reverse()

    wx = wy = wz = 0.0
    parent_orientation = [0.0, 0.0, 0.0, 1.0]
    pose_nodes = getattr(anim_pose, "nodes", {}) or {}
    for chain_node in chain:
        pose = pose_nodes.get(str(getattr(chain_node, "name", "") or "").lower())
        if pose is not None:
            pos = getattr(pose, "position", getattr(chain_node, "position", (0.0, 0.0, 0.0)))
            rot = getattr(pose, "rotation", getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        else:
            pos = getattr(chain_node, "position", (0.0, 0.0, 0.0))
            rot = getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0))
        rx, ry, rz = _quat_rotate(parent_orientation, tuple(float(v) for v in pos[:3]))
        wx += rx
        wy += ry
        wz += rz
        parent_orientation = _quat_mul(parent_orientation, _quat_normalize_bind(rot))
    return (float(wx), float(wy), float(wz))


def _distance(a, b) -> float:
    import math

    return float(math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3))))


def _bone_colour_hint(node, *, selected: bool, hovered: bool) -> tuple[float, float, float, float]:
    if selected:
        return (1.0, 0.85, 0.16, 1.0)
    if hovered:
        return (1.0, 0.95, 0.25, 1.0)
    if bool(getattr(node, "is_mesh", False)) and not bool(getattr(node, "is_dummy", False)):
        return (0.50, 0.62, 0.74, 1.0)
    return (0.66, 0.72, 0.80, 1.0)


def _skin_revision(node, vertex_count: int) -> int:
    return hash(
        (
            id(node),
            int(vertex_count),
            len(getattr(node, "skin_data", []) or []),
            tuple(getattr(node, "bone_map", []) or ()),
            int(getattr(node, "_gr_revision", 0) or 0),
        )
    ) & 0x7FFFFFFF


def _root_model_from_node(_node):
    return None
