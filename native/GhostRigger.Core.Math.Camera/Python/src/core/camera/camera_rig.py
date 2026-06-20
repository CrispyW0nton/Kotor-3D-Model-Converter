"""Extension point for future camera rigs, paths, and cuts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CameraRig:
    camera_id: str
    keyframes: list[dict] = field(default_factory=list)
    cuts: list[dict] = field(default_factory=list)
    path_points: list[tuple[float, float, float]] = field(default_factory=list)

    # TODO(TBD): connect this to a future GhostRigger timeline when one exists.
    # This object intentionally stores declarative data only; it does not attempt
    # to play animation without a real timeline, interpolation UI, or render queue.
