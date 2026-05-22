"""Tests for UE5/Aurora coordinate conversion."""

from __future__ import annotations

import math

from src.core.retargeting.coordinate_converter import (
    aurora_from_ue5_position,
    aurora_from_ue5_quat,
    ue5_from_aurora_position,
    ue5_from_aurora_quat,
    verify_round_trip,
)


def test_position_conversion_mirrors_x_y_and_preserves_z_up():
    converted = aurora_from_ue5_position((1.0, 2.0, 3.0))

    assert converted.to_xyz() == (-1.0, -2.0, 3.0)


def test_quaternion_conversion_matches_calibrated_xy_mirror_basis():
    converted = aurora_from_ue5_quat((0.1, 0.2, 0.3, 0.9))
    mag = math.sqrt(0.9 * 0.9 + 0.1 * 0.1 + 0.3 * 0.3 + 0.2 * 0.2)

    assert converted.to_wxyz() == (0.9 / mag, -0.1 / mag, -0.2 / mag, 0.3 / mag)


def test_position_conversion_is_involutive():
    pos = (4.0, -2.0, 9.5)
    roundtrip = ue5_from_aurora_position(aurora_from_ue5_position(pos).to_xyz())

    assert roundtrip.to_xyz() == pos


def test_quaternion_conversion_is_involutive():
    quat_xyzw = (0.1825741858, -0.3651483717, 0.5477225575, 0.7302967433)
    aurora = aurora_from_ue5_quat(quat_xyzw)
    roundtrip = ue5_from_aurora_quat(aurora.to_wxyz())

    assert all(abs(a - b) < 1e-6 for a, b in zip(quat_xyzw, roundtrip.to_xyzw()))


def test_verify_round_trip_accepts_representative_pose():
    assert verify_round_trip(
        quat_xyzw=(0.0, 0.2588190451, 0.0, 0.9659258263),
        pos_xyz=(0.25, -1.0, 1.75),
    )
