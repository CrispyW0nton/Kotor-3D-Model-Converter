"""Animated door actors for Play-in-Editor.

The PIE door system already tracks each door's open/closed state
(``MapStudioPIEDoorState``). This module gives those doors a retained,
animated actor: each authored door placement resolves to its genericdoors
model, and when its state flips the actor plays the door model's real
``opening1``/``opened1``/``closing1``/``closed`` clips (with candidate
fallbacks for models that name them differently). It mirrors the creature
actor pipeline — the baked static door is hidden and the animated actor takes
its place — but doors are stationary and only re-animate on a state change.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

Vec3 = tuple[float, float, float]

# Ordered candidate clips; the first the door model actually contains is used.
DOOR_OPEN_TRANSITION_CANDIDATES: tuple[str, ...] = ("opening1", "opening", "open1", "open")
DOOR_OPENED_HOLD_CANDIDATES: tuple[str, ...] = ("opened1", "opened", "open1", "open", "openidle")
DOOR_CLOSE_TRANSITION_CANDIDATES: tuple[str, ...] = ("closing1", "closing", "close1", "close")
DOOR_CLOSED_HOLD_CANDIDATES: tuple[str, ...] = ("closed", "closed1", "close", "default", "off")


@dataclass(frozen=True)
class MapStudioPIEDoorSpec:
    """One authored door placement resolved to a renderable, animatable model."""

    door_id: str
    tag: str
    model_resref: str
    position: Vec3
    bearing: float

    @property
    def can_build_actor(self) -> bool:
        return bool(self.model_resref)


@dataclass(frozen=True)
class MapStudioPIEDoorAnimationStep:
    """State after advancing one real door animation clip."""

    is_open: bool
    transitioning: bool
    animation_name: str


@dataclass(frozen=True)
class MapStudioPIEDoorVerticalPosePolicy:
    """PIE correction for a retail clip whose panel travels below its frame.

    Some generic-door models encode a vertically sliding panel with negative
    local Z travel.  In the authored Map Studio frame that makes the visible
    panel descend into the floor.  The policy is derived from the model's
    actual held-open pose, so horizontal, hinged, and already-upward doors are
    left byte-for-byte untouched.
    """

    base_z_by_node: tuple[tuple[str, float], ...] = ()
    reason: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.base_z_by_node)


def _clean_resref(value: Any) -> str:
    return str(value or "").strip().lower()


def _vec3(value: Any) -> Vec3:
    values = tuple(value or ())
    if len(values) < 3:
        return (0.0, 0.0, 0.0)
    return (float(values[0]), float(values[1]), float(values[2]))


def build_map_studio_pie_door_plan(placements: Any, resolver: Any) -> tuple[MapStudioPIEDoorSpec, ...]:
    """Resolve every authored door placement to a door-model actor spec.

    ``resolver`` follows the stock content resolver contract and exposes
    ``door_model(utd_resref)``. Doors whose model cannot be resolved are
    skipped (they keep their static preview).
    """

    door_model = getattr(resolver, "door_model", None)
    specs: list[MapStudioPIEDoorSpec] = []
    for index, door in enumerate(tuple(getattr(placements, "doors", ()) or ())):
        template = _clean_resref(getattr(door, "template_resref", ""))
        model = _clean_resref(door_model(template)) if callable(door_model) and template else ""
        instance_id = str(getattr(door, "instance_id", "") or "").strip()
        specs.append(
            MapStudioPIEDoorSpec(
                door_id=f"authored:door:{instance_id or index}",
                tag=str(getattr(door, "tag", "") or template),
                model_resref=model,
                position=_vec3(getattr(door, "position", (0.0, 0.0, 0.0))),
                bearing=float(getattr(door, "bearing", 0.0) or 0.0),
            )
        )
    return tuple(specs)


def door_state_clip_candidates(*, is_open: bool, transitioning: bool) -> tuple[str, ...]:
    """Candidate clips for a door's current state.

    ``transitioning`` selects the one-shot opening/closing swing; otherwise the
    held opened/closed pose. The consumer plays the first clip that resolves.
    """

    if is_open:
        return DOOR_OPEN_TRANSITION_CANDIDATES if transitioning else DOOR_OPENED_HOLD_CANDIDATES
    return DOOR_CLOSE_TRANSITION_CANDIDATES if transitioning else DOOR_CLOSED_HOLD_CANDIDATES


def play_map_studio_pie_door_clip(engine: Any, candidates: tuple[str, ...], *, loop: bool) -> str:
    """Play the first candidate clip the door model contains; '' if none do."""

    for candidate in tuple(candidates or ()):
        clean = str(candidate or "").strip().lower()
        if clean and engine.play(clean, loop=loop, blend=False):
            return str(getattr(getattr(engine, "current_animation", None), "name", clean) or clean).lower()
    return ""


def build_map_studio_pie_door_vertical_pose_policy(
    model: Any,
    open_pose: Any,
    *,
    minimum_vertical_travel: float = 0.12,
) -> MapStudioPIEDoorVerticalPosePolicy:
    """Detect downward-dominant sliding panels from an evaluated open pose."""

    iterator = getattr(model, "all_nodes", None)
    nodes = tuple(iterator() or ()) if callable(iterator) else ()
    base_by_name = {
        str(getattr(node, "name", "") or "").strip().lower(): tuple(
            float(value)
            for value in tuple(getattr(node, "position", (0.0, 0.0, 0.0)) or ())[:3]
        )
        for node in nodes
        if str(getattr(node, "name", "") or "").strip()
    }
    corrected: list[tuple[str, float]] = []
    threshold = max(0.01, float(minimum_vertical_travel))
    for raw_name, node_pose in dict(getattr(open_pose, "nodes", {}) or {}).items():
        name = str(raw_name or getattr(node_pose, "name", "") or "").strip().lower()
        base = base_by_name.get(name)
        position = tuple(getattr(node_pose, "position", ()) or ())
        if base is None or len(base) < 3 or len(position) < 3:
            continue
        dx = float(position[0]) - float(base[0])
        dy = float(position[1]) - float(base[1])
        dz = float(position[2]) - float(base[2])
        planar_travel = math.hypot(dx, dy)
        if dz <= -threshold and abs(dz) >= max(threshold, planar_travel * 1.15):
            corrected.append((name, float(base[2])))
    return MapStudioPIEDoorVerticalPosePolicy(
        base_z_by_node=tuple(sorted(corrected)),
        reason=("downward_open_pose_reflected_upward" if corrected else ""),
    )


def apply_map_studio_pie_door_vertical_pose_policy(
    pose: Any,
    policy: MapStudioPIEDoorVerticalPosePolicy | None,
) -> Any:
    """Reflect only the detected panel's below-frame Z delta above its frame."""

    if pose is None or policy is None or not policy.enabled:
        return pose
    base_by_name = dict(policy.base_z_by_node)
    for raw_name, node_pose in dict(getattr(pose, "nodes", {}) or {}).items():
        name = str(raw_name or getattr(node_pose, "name", "") or "").strip().lower()
        base_z = base_by_name.get(name)
        position = tuple(getattr(node_pose, "position", ()) or ())
        if base_z is None or len(position) < 3:
            continue
        delta_z = float(position[2]) - float(base_z)
        if delta_z < 0.0:
            node_pose.position = (
                float(position[0]),
                float(position[1]),
                float(base_z) - delta_z,
            )
    return pose


def map_studio_pie_door_visual_nodes(root: Any) -> tuple[Any, ...]:
    """Return renderable door meshes, excluding collision/transition helpers."""

    visual_nodes: list[Any] = []
    stack = [root] if root is not None else []
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        stack.extend(tuple(getattr(node, "children", ()) or ()))
        if bool(getattr(node, "_gr_map_studio_pie_transition_helper", False)):
            continue
        if (
            bool(getattr(node, "render", True))
            and tuple(getattr(node, "vertices", ()) or ())
            and tuple(getattr(node, "faces", ()) or ())
        ):
            visual_nodes.append(node)
    return tuple(visual_nodes)


def set_map_studio_pie_door_visuals_hidden(nodes: Any, hidden: bool) -> bool:
    """Toggle a prepared static/animated door visual set; report any change."""

    changed = False
    wanted = bool(hidden)
    for node in tuple(nodes or ()):
        if bool(getattr(node, "_gr_hidden", False)) == wanted:
            continue
        setattr(node, "_gr_hidden", wanted)
        changed = True
    return changed


def advance_map_studio_pie_door_animation(
    engine: Any,
    *,
    wanted_open: bool,
    current_open: bool,
    transitioning: bool,
    delta_time: float,
) -> MapStudioPIEDoorAnimationStep:
    """Advance opening/closing for the selected model clip's actual length."""

    wanted = bool(wanted_open)
    current = bool(current_open)
    active = bool(transitioning)
    if wanted != current:
        current = wanted
        active = bool(
            play_map_studio_pie_door_clip(
                engine,
                door_state_clip_candidates(is_open=current, transitioning=True),
                loop=False,
            )
        )
        if not active:
            play_map_studio_pie_door_clip(
                engine,
                door_state_clip_candidates(is_open=current, transitioning=False),
                loop=True,
            )

    step = max(0.0, min(float(delta_time), 0.25))
    still_playing = bool(engine.advance(step))
    if active and not still_playing:
        play_map_studio_pie_door_clip(
            engine,
            door_state_clip_candidates(is_open=current, transitioning=False),
            loop=True,
        )
        active = False
    name = str(getattr(getattr(engine, "current_animation", None), "name", "") or "").lower()
    return MapStudioPIEDoorAnimationStep(current, active, name)


__all__ = [
    "MapStudioPIEDoorSpec",
    "MapStudioPIEDoorAnimationStep",
    "MapStudioPIEDoorVerticalPosePolicy",
    "DOOR_OPEN_TRANSITION_CANDIDATES",
    "DOOR_OPENED_HOLD_CANDIDATES",
    "DOOR_CLOSE_TRANSITION_CANDIDATES",
    "DOOR_CLOSED_HOLD_CANDIDATES",
    "build_map_studio_pie_door_plan",
    "build_map_studio_pie_door_vertical_pose_policy",
    "apply_map_studio_pie_door_vertical_pose_policy",
    "map_studio_pie_door_visual_nodes",
    "set_map_studio_pie_door_visuals_hidden",
    "advance_map_studio_pie_door_animation",
    "door_state_clip_candidates",
    "play_map_studio_pie_door_clip",
]
