"""Headless dialogue-camera framing for Play-in-Editor.

KOTOR DLG entry nodes carry a ``CameraAngle`` plus, for placed shots, a
``CameraID`` into the area camera list, an optional ``CameraFOV``, and
camera/target height offsets. Across a 160-DLG vanilla K2 census the observed
``CameraAngle`` distribution is 0 (default two-shot, ~72%), 6 (placed camera by
``CameraID``, ~24%), and 1-5 (distinct discrete shots, the remainder).

This module turns those fields plus the live speaker/listener positions into an
orbit-camera framing (target, azimuth, elevation, distance, FOV) matching the
convention the PIE viewport tick uses: azimuth is measured from +X CCW in the XY
plane, elevation from the horizontal, and the eye sits at
``target + distance * (cos e cos a, cos e sin a, sin e)``.

Parity note: ``CameraAngle == 6`` is faithful — it uses the area camera's real
authored position, height, and field of view. Angles 0-5 select *distinct,
deterministic* clean-room shots (over-shoulder reverse/counter, profile, tight
single, wide establishing, low angle); the exact Odyssey per-angle shot geometry
is not recoverable from static disassembly alone, so the distances/elevations
here are labelled approximations, not a claim of retail parity.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class DialoguePlacedCamera:
    """One authored area camera resolved for a placed (angle 6) dialogue shot."""

    position: Vec3
    height: float = 0.0
    field_of_view: float = 45.0


@dataclass(frozen=True)
class DialogueCameraFraming:
    """Resolved orbit-camera framing for one dialogue node."""

    target: Vec3
    azimuth_deg: float
    elevation_deg: float
    distance: float
    fov: float
    mode: str  # "placed" | "angle"
    camera_angle: int = 0


# Per-angle clean-room shot table. Each tuple is
# (subject, shoulder_deg, distance, base_elevation_deg): ``subject`` names which
# conversant the camera sits behind ("listener"/"speaker") or "midpoint" for a
# profile shot; ``shoulder_deg`` offsets the azimuth off the speaker-listener
# line. Angle 0 reproduces the standard KOTOR reverse two-shot exactly.
_ANGLE_SHOTS: dict[int, tuple[str, float, float, float]] = {
    0: ("listener", 22.0, 2.45, 5.0),   # default reverse over the listener's shoulder
    1: ("speaker", -22.0, 2.45, 5.0),   # counter shot over the speaker's shoulder
    2: ("midpoint", 90.0, 3.10, 8.0),   # side / profile two-shot
    3: ("speaker", 10.0, 1.90, 6.0),    # tight single on the speaker
    4: ("listener", 22.0, 4.20, 16.0),  # wide, high establishing shot
    5: ("speaker", -12.0, 2.10, -2.0),  # low hero angle
}

# Head-height base the look-at point is raised to above the taller conversant.
_LOOK_AT_BASE_HEIGHT = 1.25
_MIN_PLACED_DISTANCE = 0.35


def _vec3(value: object) -> Vec3:
    values = tuple(value or ())
    if len(values) < 3:
        values = tuple(values) + (0.0,) * (3 - len(values))
    return (float(values[0]), float(values[1]), float(values[2]))


def dialogue_camera_look_at(
    listener_position: object,
    speaker_position: object,
    *,
    target_height_offset: float = 0.0,
) -> Vec3:
    """The point both conversants are framed around (their raised midpoint)."""

    listener = _vec3(listener_position)
    speaker = _vec3(speaker_position)
    return (
        (listener[0] + speaker[0]) * 0.5,
        (listener[1] + speaker[1]) * 0.5,
        max(listener[2], speaker[2]) + _LOOK_AT_BASE_HEIGHT + float(target_height_offset or 0.0),
    )


def _framing_from_eye(
    target: Vec3,
    eye: Vec3,
    *,
    fov: float,
    mode: str,
    camera_angle: int,
    minimum_distance: float,
) -> DialogueCameraFraming:
    delta = (eye[0] - target[0], eye[1] - target[1], eye[2] - target[2])
    planar = math.hypot(delta[0], delta[1])
    distance = max(minimum_distance, math.sqrt(delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2))
    azimuth = math.degrees(math.atan2(delta[1], delta[0])) % 360.0
    elevation = math.degrees(math.atan2(delta[2], max(1.0e-6, planar)))
    return DialogueCameraFraming(
        target=target,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        distance=distance,
        fov=float(fov),
        mode=mode,
        camera_angle=int(camera_angle),
    )


def solve_map_studio_pie_dialogue_camera(
    *,
    listener_position: object,
    speaker_position: object,
    camera_angle: int = 0,
    camera_fov: float | None = None,
    camera_height_offset: float = 0.0,
    target_height_offset: float = 0.0,
    placed_camera: DialoguePlacedCamera | None = None,
) -> DialogueCameraFraming:
    """Resolve one dialogue node's orbit-camera framing.

    ``placed_camera`` is honored only when ``camera_angle == 6`` (the KOTOR
    placed-shot contract); otherwise the discrete angle shot table is used.
    A positive ``camera_fov`` overrides the shot/camera default.
    """

    angle = int(camera_angle or 0)
    listener = _vec3(listener_position)
    speaker = _vec3(speaker_position)
    height_offset = float(camera_height_offset or 0.0)
    target = dialogue_camera_look_at(listener, speaker, target_height_offset=target_height_offset)
    override_fov = float(camera_fov) if camera_fov is not None and float(camera_fov) > 0.0 else None

    if angle == 6 and placed_camera is not None:
        eye = (
            float(placed_camera.position[0]),
            float(placed_camera.position[1]),
            float(placed_camera.position[2]) + float(placed_camera.height or 0.0) + height_offset,
        )
        fov = override_fov if override_fov is not None else float(placed_camera.field_of_view or 45.0)
        return _framing_from_eye(
            target,
            eye,
            fov=fov,
            mode="placed",
            camera_angle=angle,
            minimum_distance=_MIN_PLACED_DISTANCE,
        )

    subject, shoulder_deg, distance, base_elevation_deg = _ANGLE_SHOTS.get(angle, _ANGLE_SHOTS[0])
    base_bearing = math.degrees(math.atan2(speaker[1] - listener[1], speaker[0] - listener[0]))
    if subject == "listener":
        azimuth = (base_bearing + 180.0 + shoulder_deg) % 360.0
    else:  # "speaker" and "midpoint" both orbit off the same forward bearing
        azimuth = (base_bearing + shoulder_deg) % 360.0

    planar = distance * math.cos(math.radians(base_elevation_deg))
    vertical = distance * math.sin(math.radians(base_elevation_deg)) + height_offset
    elevation = math.degrees(math.atan2(vertical, max(1.0e-6, planar)))
    fov = override_fov if override_fov is not None else 45.0
    return DialogueCameraFraming(
        target=target,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        distance=distance,
        fov=fov,
        mode="angle",
        camera_angle=angle,
    )


__all__ = [
    "DialoguePlacedCamera",
    "DialogueCameraFraming",
    "dialogue_camera_look_at",
    "solve_map_studio_pie_dialogue_camera",
]
