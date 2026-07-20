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
    "DOOR_OPEN_TRANSITION_CANDIDATES",
    "DOOR_OPENED_HOLD_CANDIDATES",
    "DOOR_CLOSE_TRANSITION_CANDIDATES",
    "DOOR_CLOSED_HOLD_CANDIDATES",
    "build_map_studio_pie_door_plan",
    "advance_map_studio_pie_door_animation",
    "door_state_clip_candidates",
    "play_map_studio_pie_door_clip",
]
