"""Viewport preview adapter for imported source animation clips."""

from __future__ import annotations

import math
from typing import Iterable

from src.core.geometry.model_data import (
    GameVersion,
    KotorModel,
    ModelClassification,
    ModelNode,
    NodeFlags,
)
from src.core.retargeting.source_animation import SourceSkeletonClip, Transform


def build_source_clip_preview_model(clip: SourceSkeletonClip) -> KotorModel:
    """Build a lightweight dummy-node model for rendering an animation-only clip.

    UE/FBX source imports can legitimately contain only a sampled skeleton clip,
    with no mesh payload.  The Retarget Workbench source viewport still needs a
    renderable hierarchy, so this adapter mirrors the clip's node tree as
    ``ModelNode`` dummy joints and gives the viewport prepared bounds from the
    clip rest/global pose.  It intentionally lives in the Qt/window layer rather
    than in the FBX backend so import data stays backend-neutral.
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
    setattr(model, "_gr_source_clip_name", clip_name)
    setattr(model, "_gr_source_clip_node_count", len(getattr(clip, "nodes", []) or []))

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

    bounds = _bounds_from_clip(clip)
    model.bb_min, model.bb_max = bounds
    model.radius = _radius_for_bounds(*bounds)
    setattr(model, "_gr_bounds_prepared", True)
    setattr(model, "_gr_render_bounds", bounds)
    return model


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
