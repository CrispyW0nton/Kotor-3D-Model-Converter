from __future__ import annotations

import math

import numpy as np
import pytest

from src.math.head_alignment import (
    HeadAlignmentAnchor,
    HeadAlignmentDegenerateError,
    HeadAlignmentError,
    HeadAlignmentRequest,
    solve_headhook_alignment,
    source_axis_to_imported_matrix,
    transform_point,
)


IDENTITY = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def _hook_at(x: float, y: float, z: float):
    return (
        (1.0, 0.0, 0.0, x),
        (0.0, 1.0, 0.0, y),
        (0.0, 0.0, 1.0, z),
        (0.0, 0.0, 0.0, 1.0),
    )


def test_three_anchor_solve_keeps_body_and_headhook_spaces_distinct():
    anchors = (
        HeadAlignmentAnchor(
            "neck_center",
            (0.0, 0.0, 0.0),
            (10.0, 2.0, 3.0),
        ),
        HeadAlignmentAnchor(
            "neck_left",
            (1.0, 0.0, 0.0),
            (10.0, 3.0, 3.0),
        ),
        HeadAlignmentAnchor(
            "neck_front",
            (0.0, 1.0, 0.0),
            (9.0, 2.0, 3.0),
        ),
    )
    result = solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=anchors,
            headhook_to_body=_hook_at(10.0, 0.0, 0.0),
        )
    )

    assert result.method == "weighted_kabsch_rigid"
    assert result.confidence == "fully_constrained"
    assert result.rotation_determinant == pytest.approx(1.0)
    assert result.rms_error == pytest.approx(0.0, abs=1.0e-10)
    assert transform_point(
        result.imported_to_body,
        (0.0, 0.0, 0.0),
    ) == pytest.approx((10.0, 2.0, 3.0))
    assert transform_point(
        result.imported_to_headhook,
        (0.0, 0.0, 0.0),
    ) == pytest.approx((0.0, 2.0, 3.0))
    assert result.transform_sha256
    assert type(result).from_dict(result.to_dict()) == result


def test_two_anchor_similarity_solves_scale_and_warns_about_roll():
    result = solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=(
                HeadAlignmentAnchor("center", (0, 0, 0), (4, 5, 6)),
                HeadAlignmentAnchor("top", (0, 0, 1), (4, 7, 6)),
            ),
            headhook_to_body=IDENTITY,
            scale_mode="similarity",
        )
    )

    assert result.method == "two_anchor_direction"
    assert result.scale == pytest.approx(2.0)
    assert result.rms_error == pytest.approx(0.0, abs=1.0e-10)
    assert result.confidence == "roll_underdetermined"
    assert any("roll" in warning.lower() for warning in result.warnings)


def test_single_anchor_is_translation_only():
    result = solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=(
                HeadAlignmentAnchor("neck", (1, 2, 3), (4, 6, 8)),
            ),
            headhook_to_body=IDENTITY,
            scale_mode="similarity",
        )
    )

    assert result.scale == 1.0
    assert result.translation_in_body == pytest.approx((3.0, 4.0, 5.0))
    assert result.anchor_rank == 0


def test_kabsch_reflection_input_still_emits_proper_rotation():
    source = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    target = tuple((-x, y, z) for x, y, z in source)
    result = solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=tuple(
                HeadAlignmentAnchor(f"p{index}", left, right)
                for index, (left, right) in enumerate(zip(source, target))
            ),
            headhook_to_body=IDENTITY,
        )
    )

    assert result.rotation_determinant == pytest.approx(1.0)
    assert result.max_error > 0.0


def test_collinear_three_anchor_request_is_rejected():
    with pytest.raises(HeadAlignmentDegenerateError, match="non-collinear"):
        solve_headhook_alignment(
            HeadAlignmentRequest(
                anchors=(
                    HeadAlignmentAnchor("a", (0, 0, 0), (0, 0, 0)),
                    HeadAlignmentAnchor("b", (1, 0, 0), (1, 0, 0)),
                    HeadAlignmentAnchor("c", (2, 0, 0), (2, 0, 0)),
                ),
                headhook_to_body=IDENTITY,
            )
        )


def test_singular_headhook_transform_is_rejected():
    singular = (
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    with pytest.raises(HeadAlignmentError, match="not invertible"):
        solve_headhook_alignment(
            HeadAlignmentRequest(
                anchors=(
                    HeadAlignmentAnchor("neck", (0, 0, 0), (0, 0, 0)),
                ),
                headhook_to_body=singular,
            )
        )


def test_axis_conversion_is_explicit_and_proper():
    matrix = source_axis_to_imported_matrix(
        "blender_xyz_to_kotor_xz_minus_y",
        unit_scale_to_kotor=2.0,
    )
    assert transform_point(matrix, (1.0, 2.0, 3.0)) == pytest.approx(
        (2.0, 6.0, -4.0)
    )
    with pytest.raises(HeadAlignmentError, match="Unsupported source axis"):
        source_axis_to_imported_matrix("please_guess")
    with pytest.raises(HeadAlignmentError, match="positive"):
        source_axis_to_imported_matrix("kotor_z_up", unit_scale_to_kotor=math.nan)


def test_tripo_y_up_z_forward_axis_is_a_proper_kotor_rotation():
    matrix = source_axis_to_imported_matrix(
        "tripo_y_up_z_forward",
        unit_scale_to_kotor=2.0,
    )

    assert transform_point(matrix, (1.0, 2.0, 3.0)) == pytest.approx(
        (-2.0, 6.0, 4.0)
    )
    assert np.linalg.det(np.asarray(matrix, dtype=float)[:3, :3]) == (
        pytest.approx(8.0)
    )


def test_maya_y_up_x_forward_axis_is_a_proper_kotor_rotation():
    matrix = source_axis_to_imported_matrix(
        "maya_y_up_x_forward",
        unit_scale_to_kotor=0.01,
    )

    assert transform_point(matrix, (1.0, 2.0, 3.0)) == pytest.approx(
        (0.03, 0.01, 0.02)
    )
    assert np.linalg.det(np.asarray(matrix, dtype=float)[:3, :3]) == (
        pytest.approx(0.000001)
    )


def test_saved_alignment_fingerprint_rejects_matrix_drift():
    result = solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=(
                HeadAlignmentAnchor("neck", (0, 0, 0), (1, 2, 3)),
            ),
            headhook_to_body=IDENTITY,
        )
    )
    payload = result.to_dict()
    payload["imported_to_body"][0][3] += 1.0

    with pytest.raises(HeadAlignmentError, match="fingerprint"):
        type(result).from_dict(payload)
