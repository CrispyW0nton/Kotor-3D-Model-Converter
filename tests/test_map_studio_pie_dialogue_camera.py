"""Focused contracts for the headless PIE dialogue-camera solver.

Grounded in the 160-DLG vanilla K2 CameraAngle census: 0 (default two-shot),
6 (placed camera by CameraID), and 1-5 (distinct discrete shots). The exact
Odyssey per-angle geometry is not recoverable from static disassembly, so these
assert the *structural* contract: angle 6 is faithful to the authored camera,
each angle 0-5 yields a distinct deterministic framing, and FOV/height overrides
apply. Editor-side framing, never a retail-camera claim.
"""

from __future__ import annotations

import math

import pytest


def _solve(**kwargs):
    from src.core.modules.map_studio_pie_dialogue_camera import solve_map_studio_pie_dialogue_camera

    return solve_map_studio_pie_dialogue_camera(**kwargs)


def test_look_at_is_the_raised_midpoint() -> None:
    from src.core.modules.map_studio_pie_dialogue_camera import dialogue_camera_look_at

    target = dialogue_camera_look_at((0.0, 0.0, 0.0), (10.0, 0.0, 2.0), target_height_offset=0.5)
    assert target[0] == pytest.approx(5.0)
    assert target[1] == pytest.approx(0.0)
    # raised above the taller conversant (z=2.0) by the base head height + offset
    assert target[2] == pytest.approx(2.0 + 1.25 + 0.5)


def test_default_angle_zero_reproduces_reverse_over_listener_shoulder() -> None:
    framing = _solve(
        listener_position=(0.0, 0.0, 0.0),
        speaker_position=(10.0, 0.0, 0.0),
        camera_angle=0,
    )
    assert framing.mode == "angle"
    assert framing.target == pytest.approx((5.0, 0.0, 1.25))
    # base bearing 0 deg, over the listener's shoulder -> 180 + 22
    assert framing.azimuth_deg == pytest.approx(202.0)
    assert framing.elevation_deg == pytest.approx(5.0, abs=1e-6)
    assert framing.distance == pytest.approx(2.45)
    assert framing.fov == pytest.approx(45.0)


def test_counter_shot_angle_one_differs_from_default() -> None:
    default = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(10.0, 0.0, 0.0), camera_angle=0)
    counter = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(10.0, 0.0, 0.0), camera_angle=1)
    # counter shot orbits to the speaker side (base bearing 0 - 22 -> 338)
    assert counter.azimuth_deg == pytest.approx(338.0)
    assert abs(counter.azimuth_deg - default.azimuth_deg) > 90.0


def test_angles_zero_through_five_are_all_distinct() -> None:
    framings = [
        _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(6.0, 0.0, 0.0), camera_angle=a)
        for a in range(6)
    ]
    signatures = {
        (round(f.azimuth_deg, 3), round(f.elevation_deg, 3), round(f.distance, 3)) for f in framings
    }
    assert len(signatures) == 6  # every discrete angle produces a distinct shot
    assert all(f.mode == "angle" for f in framings)


def test_unknown_angle_falls_back_to_default_shot() -> None:
    default = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(4.0, 0.0, 0.0), camera_angle=0)
    unknown = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(4.0, 0.0, 0.0), camera_angle=99)
    assert (unknown.azimuth_deg, unknown.distance) == pytest.approx((default.azimuth_deg, default.distance))


def test_placed_camera_angle_six_uses_authored_position_and_fov() -> None:
    from src.core.modules.map_studio_pie_dialogue_camera import DialoguePlacedCamera

    framing = _solve(
        listener_position=(0.0, 0.0, 0.0),
        speaker_position=(10.0, 0.0, 0.0),
        camera_angle=6,
        placed_camera=DialoguePlacedCamera(position=(5.0, 5.0, 2.0), height=0.5, field_of_view=60.0),
    )
    assert framing.mode == "placed"
    assert framing.target == pytest.approx((5.0, 0.0, 1.25))
    # eye at (5,5,2.5), look-at (5,0,1.25): delta (0,5,1.25)
    assert framing.azimuth_deg == pytest.approx(90.0)
    assert framing.elevation_deg == pytest.approx(math.degrees(math.atan2(1.25, 5.0)))
    assert framing.distance == pytest.approx(math.sqrt(25.0 + 1.25 ** 2))
    assert framing.fov == pytest.approx(60.0)


def test_placed_camera_ignored_without_angle_six() -> None:
    from src.core.modules.map_studio_pie_dialogue_camera import DialoguePlacedCamera

    framing = _solve(
        listener_position=(0.0, 0.0, 0.0),
        speaker_position=(10.0, 0.0, 0.0),
        camera_angle=0,
        placed_camera=DialoguePlacedCamera(position=(5.0, 5.0, 2.0)),
    )
    assert framing.mode == "angle"  # angle != 6 never uses a placed camera


def test_camera_fov_override_wins_over_shot_and_camera_defaults() -> None:
    from src.core.modules.map_studio_pie_dialogue_camera import DialoguePlacedCamera

    angle = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(5.0, 0.0, 0.0), camera_angle=0, camera_fov=72.0)
    assert angle.fov == pytest.approx(72.0)
    placed = _solve(
        listener_position=(0.0, 0.0, 0.0),
        speaker_position=(5.0, 0.0, 0.0),
        camera_angle=6,
        camera_fov=33.0,
        placed_camera=DialoguePlacedCamera(position=(1.0, 1.0, 1.0), field_of_view=60.0),
    )
    assert placed.fov == pytest.approx(33.0)


def test_camera_height_offset_raises_the_eye() -> None:
    low = _solve(listener_position=(0.0, 0.0, 0.0), speaker_position=(5.0, 0.0, 0.0), camera_angle=0)
    high = _solve(
        listener_position=(0.0, 0.0, 0.0),
        speaker_position=(5.0, 0.0, 0.0),
        camera_angle=0,
        camera_height_offset=1.5,
    )
    assert high.elevation_deg > low.elevation_deg
