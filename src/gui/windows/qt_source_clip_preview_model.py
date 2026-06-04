"""Viewport preview adapter for imported source animation clips."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from src.core.geometry.model_data import (
    GameVersion,
    KotorModel,
    ModelClassification,
    ModelNode,
    NodeFlags,
)
from src.core.retargeting.source_animation import SourceSkeletonClip, Transform, quat_to_matrix_xyzw


@dataclass(frozen=True)
class SourceClipPreviewAnimation:
    """Lightweight animation row for an imported UE/FBX source clip."""

    name: str
    length: float = 0.0
    source_path: str = ""
    loaded_clip_name: str = ""
    frame_start: float | None = None
    frame_end: float | None = None
    frame_count: int | None = None


def build_source_clip_preview_model(clip: SourceSkeletonClip, mesh_model: KotorModel | None = None) -> KotorModel:
    """Build a lightweight dummy-node model for rendering an animation-only clip.

    UE/FBX source imports always need the sampled animation skeleton. Some FBX
    files also carry mesh geometry; when ``mesh_model`` is provided, this adapter
    appends flattened renderable mesh nodes under the preview root while keeping
    the sampled skeleton hierarchy available for the Bones/Dots overlays.
    """

    clip_name = str(getattr(clip, "clip_name", "") or "Source Clip").strip() or "Source Clip"
    root = ModelNode(name=_root_name_for_clip(clip_name), flags=int(NodeFlags.HEADER))
    setattr(root, "_gr_source_clip_preview_root", True)
    model = KotorModel(
        name=clip_name,
        supermodel="NULL",
        classification="source_clip_preview",
        game_version=GameVersion.K1,
        model_type=int(ModelClassification.CHARACTER),
        root_node=root,
    )
    setattr(model, "_gr_source_clip_preview", True)
    setattr(model, "_gr_source_clip", clip)
    setattr(model, "_gr_source_clip_name", clip_name)
    setattr(model, "_gr_source_clip_node_count", len(getattr(clip, "nodes", []) or []))
    animations = _source_clip_animation_rows(clip)
    model.animations = animations
    setattr(model, "_gr_source_clip_animations", animations)

    by_name: dict[str, ModelNode] = {}
    for node in getattr(clip, "nodes", []) or []:
        preview_node = ModelNode(
            name=str(getattr(node, "name", "") or "node"),
            flags=int(NodeFlags.HEADER),
            index=int(getattr(node, "index", 0) or 0),
        )
        _apply_transform_to_node(preview_node, getattr(node, "rest_local", None))
        rest_global = getattr(node, "rest_global", None)
        if rest_global is not None:
            preview_node.external_world_position = _finite_position(rest_global.position)
        preview_node._source_clip_classification = str(getattr(node, "classification", "") or "deform")
        if preview_node._source_clip_classification in {"twist", "ik", "helper"}:
            preview_node._hide_skeleton_overlay = True
        by_name[preview_node.name] = preview_node

    for node in getattr(clip, "nodes", []) or []:
        preview_node = by_name.get(str(getattr(node, "name", "") or "node"))
        if preview_node is None:
            continue
        parent_name = getattr(node, "parent_name", None)
        parent = by_name.get(str(parent_name)) if parent_name else None
        if parent is None:
            parent = root
        preview_node.parent = parent
        parent.children.append(preview_node)

    _apply_compact_preview_positions(root, clip)

    mesh_bounds = _append_mesh_preview_nodes(root, mesh_model)
    bounds = _merge_bounds(_bounds_from_clip(clip), mesh_bounds)
    model.bb_min, model.bb_max = bounds
    model.radius = _radius_for_bounds(*bounds)
    setattr(model, "_gr_bounds_prepared", True)
    setattr(model, "_gr_render_bounds", bounds)
    setattr(model, "_gr_source_clip_mesh_count", len([n for n in model.all_nodes() if getattr(n, "_gr_fbx_mesh_preview_node", False)]))
    return model


def _apply_compact_preview_positions(root: ModelNode, clip: SourceSkeletonClip) -> None:
    rest_globals = getattr(getattr(clip, "rest_pose", None), "global_transforms", {}) or {}
    stack = list(getattr(root, "children", []) or [])
    while stack:
        node = stack.pop()
        if getattr(node, "external_world_position", None) is not None:
            parent = getattr(node, "parent", None)
            parent_name = None
            if parent is not None and not getattr(parent, "_gr_source_clip_preview_root", False):
                parent_name = str(getattr(parent, "name", "") or "")
            compact = source_clip_parent_local_position(str(getattr(node, "name", "") or ""), parent_name, rest_globals)
            node.position = compact
            node._gr_source_clip_preview_position = compact
        stack.extend(getattr(node, "children", []) or [])


def source_clip_parent_local_position(
    node_name: str,
    parent_name: str | None,
    global_transforms: dict[str, Transform],
) -> tuple[float, float, float]:
    """Return a node position in parent-local coordinates from global source transforms.

    FBX imports can carry animation data in a different unit scale than the raw
    local keys. The global transforms are the normalized preview truth, so derive
    a parent-local offset from them by rotating the world delta into the parent
    frame. A plain child_world - parent_world delta is still world-space and will
    be rotated a second time by the hierarchical viewport pose.
    """

    transform = global_transforms.get(node_name)
    if transform is None:
        return (0.0, 0.0, 0.0)
    position = _finite_position(getattr(transform, "position", (0.0, 0.0, 0.0)))
    parent_transform = global_transforms.get(parent_name) if parent_name else None
    if parent_transform is None:
        return position
    parent_position = _finite_position(getattr(parent_transform, "position", (0.0, 0.0, 0.0)))
    delta = (
        position[0] - parent_position[0],
        position[1] - parent_position[1],
        position[2] - parent_position[2],
    )
    return _rotate_world_delta_to_parent_local(delta, getattr(parent_transform, "rotation", (0.0, 0.0, 0.0, 1.0)))


def _rotate_world_delta_to_parent_local(
    delta: tuple[float, float, float],
    parent_rotation: Iterable[float],
) -> tuple[float, float, float]:
    matrix = quat_to_matrix_xyzw(_finite_quat(parent_rotation))
    # The quaternion matrix rotates parent-local vectors into world space. Its
    # transpose rotates a world-space offset back into the parent frame.
    return (
        float(matrix[0, 0] * delta[0] + matrix[1, 0] * delta[1] + matrix[2, 0] * delta[2]),
        float(matrix[0, 1] * delta[0] + matrix[1, 1] * delta[1] + matrix[2, 1] * delta[2]),
        float(matrix[0, 2] * delta[0] + matrix[1, 2] * delta[1] + matrix[2, 2] * delta[2]),
    )


def _source_clip_animation_rows(clip: SourceSkeletonClip) -> list[SourceClipPreviewAnimation]:
    entries = list(getattr(clip, "available_clips", []) or [])
    if not entries:
        entries = [
            {
                "name": str(getattr(clip, "clip_name", "") or "Source Clip"),
                "duration_seconds": float(getattr(clip, "duration_seconds", 0.0) or 0.0),
            }
        ]

    rows: list[SourceClipPreviewAnimation] = []
    seen: set[str] = set()
    source_path = str(getattr(clip, "source_path", "") or "")
    loaded_name = str(getattr(clip, "clip_name", "") or "")
    for entry in entries:
        data = entry if isinstance(entry, dict) else {"name": str(entry)}
        name = str(data.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            SourceClipPreviewAnimation(
                name=name,
                length=_animation_length(data, clip if name == loaded_name else None),
                source_path=source_path,
                loaded_clip_name=loaded_name,
                frame_start=_optional_float(data.get("frame_start")),
                frame_end=_optional_float(data.get("frame_end")),
                frame_count=_optional_int(data.get("frame_count")),
            )
        )
    if not rows:
        rows.append(
            SourceClipPreviewAnimation(
                name=loaded_name or "Source Clip",
                length=float(getattr(clip, "duration_seconds", 0.0) or 0.0),
                source_path=source_path,
                loaded_clip_name=loaded_name,
            )
        )
    return rows


def _animation_length(data: dict[str, Any], clip: SourceSkeletonClip | None) -> float:
    if "duration_seconds" in data:
        return max(0.0, _optional_float(data.get("duration_seconds")) or 0.0)
    if clip is not None:
        return max(0.0, float(getattr(clip, "duration_seconds", 0.0) or 0.0))
    frame_start = _optional_float(data.get("frame_start"))
    frame_end = _optional_float(data.get("frame_end"))
    fps = _optional_float(data.get("fps")) or 30.0
    if frame_start is not None and frame_end is not None and fps > 0:
        return max(0.0, (frame_end - frame_start) / fps)
    return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _append_mesh_preview_nodes(root: ModelNode, mesh_model: KotorModel | None) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    if mesh_model is None:
        return None
    mesh_nodes = [node for node in getattr(mesh_model, "all_nodes", lambda: [])() if getattr(node, "vertices", None) and getattr(node, "faces", None)]
    if not mesh_nodes:
        return None

    points: list[tuple[float, float, float]] = []
    for index, source in enumerate(mesh_nodes):
        is_skin = bool(getattr(source, "is_skin", False) and getattr(source, "bone_map", None) and getattr(source, "skin_data", None))
        node = ModelNode(
            name=str(getattr(source, "name", "") or f"fbx_mesh_{index}")[:32],
            flags=int(NodeFlags.HEADER | (NodeFlags.SKIN if is_skin else NodeFlags.MESH)),
            parent=root,
        )
        node.vertices = [tuple(float(c) for c in vertex[:3]) for vertex in (getattr(source, "vertices", []) or [])]
        node.normals = [tuple(float(c) for c in normal[:3]) for normal in (getattr(source, "normals", []) or [])]
        node.uvs = [tuple(float(c) for c in uv[:2]) for uv in (getattr(source, "uvs", []) or [])]
        node.faces = [tuple(int(c) for c in face[:3]) for face in (getattr(source, "faces", []) or [])]
        node.texture = str(getattr(source, "texture", "") or "")[:32]
        node.diffuse = tuple(getattr(source, "diffuse", (0.8, 0.8, 0.8))[:3])  # type: ignore[assignment]
        node.ambient = tuple(getattr(source, "ambient", (0.2, 0.2, 0.2))[:3])  # type: ignore[assignment]
        node.render = True
        node._imported = True
        node._external_imported = bool(getattr(source, "_external_imported", False))
        node.vertex_space = 1
        if is_skin:
            node.bone_map = [str(name) for name in (getattr(source, "bone_map", []) or [])]
            node.skin_data = list(getattr(source, "skin_data", []) or [])
        node._gr_fbx_mesh_preview_node = True
        node._gr_fbx_mesh_preview_skinned = bool(is_skin)
        node.compute_bounds()
        root.children.append(node)
        points.extend(node.vertices)

    if not points:
        return None
    mins = [min(point[i] for point in points) for i in range(3)]
    maxs = [max(point[i] for point in points) for i in range(3)]
    return (
        tuple(float(value) for value in mins),  # type: ignore[return-value]
        tuple(float(value) for value in maxs),  # type: ignore[return-value]
    )


def _apply_transform_to_node(node: ModelNode, transform: Transform | None) -> None:
    if transform is None:
        return
    node.position = _finite_position(getattr(transform, "position", (0.0, 0.0, 0.0)))
    node.rotation = _finite_quat(getattr(transform, "rotation", (0.0, 0.0, 0.0, 1.0)))
    node._gr_scale = _finite_position(getattr(transform, "scale", (1.0, 1.0, 1.0)), fallback=(1.0, 1.0, 1.0))


def _bounds_from_clip(clip: SourceSkeletonClip) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for node in getattr(clip, "nodes", []) or []:
        rest_global = getattr(node, "rest_global", None)
        if rest_global is None:
            continue
        position = _finite_position(getattr(rest_global, "position", (0.0, 0.0, 0.0)))
        points.append(position)
    if not points:
        return ((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5))

    mins = [min(point[i] for point in points) for i in range(3)]
    maxs = [max(point[i] for point in points) for i in range(3)]
    span = [maxs[i] - mins[i] for i in range(3)]
    largest = max(span)
    pad = max(0.05, largest * 0.05)
    if largest <= 1e-6:
        pad = 0.5
    return (
        tuple(float(value - pad) for value in mins),  # type: ignore[return-value]
        tuple(float(value + pad) for value in maxs),  # type: ignore[return-value]
    )


def _merge_bounds(
    first: tuple[tuple[float, float, float], tuple[float, float, float]],
    second: tuple[tuple[float, float, float], tuple[float, float, float]] | None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if second is None:
        return first
    mins = [min(first[0][i], second[0][i]) for i in range(3)]
    maxs = [max(first[1][i], second[1][i]) for i in range(3)]
    span = [maxs[i] - mins[i] for i in range(3)]
    pad = max(0.05, max(span) * 0.03)
    return (
        tuple(float(value - pad) for value in mins),  # type: ignore[return-value]
        tuple(float(value + pad) for value in maxs),  # type: ignore[return-value]
    )


def _finite_position(values: Iterable[float], *, fallback: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    raw = list(values or fallback)
    out = []
    for index in range(3):
        try:
            value = float(raw[index])
        except Exception:
            value = fallback[index]
        if not math.isfinite(value):
            value = fallback[index]
        out.append(value)
    return (out[0], out[1], out[2])


def _finite_quat(values: Iterable[float]) -> tuple[float, float, float, float]:
    raw = list(values or (0.0, 0.0, 0.0, 1.0))
    out = []
    for index, fallback in enumerate((0.0, 0.0, 0.0, 1.0)):
        try:
            value = float(raw[index])
        except Exception:
            value = fallback
        if not math.isfinite(value):
            value = fallback
        out.append(value)
    mag_sq = sum(value * value for value in out)
    if mag_sq <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    mag = math.sqrt(mag_sq)
    return (out[0] / mag, out[1] / mag, out[2] / mag, out[3] / mag)


def _radius_for_bounds(bb_min: tuple[float, float, float], bb_max: tuple[float, float, float]) -> float:
    return max(
        math.sqrt(sum((bb_max[i] - bb_min[i]) ** 2 for i in range(3))) * 0.5,
        0.5,
    )


def _root_name_for_clip(clip_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in clip_name).strip("_")
    return (safe or "source_clip")[:64]
