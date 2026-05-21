"""Tests for Sprint 3.5 per-bone basis remapping."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.retargeting.aurora_animation_writer import (
    compute_basis_change_matrix,
    conjugate_quat_wxyz,
)


def _quats_close(a, b, tolerance: float = 1e-6) -> bool:
    qa = np.asarray(a, dtype=np.float64)
    qb = np.asarray(b, dtype=np.float64)
    return bool(
        np.allclose(qa, qb, atol=tolerance)
        or np.allclose(qa, -qb, atol=tolerance)
    )


def test_identity_basis_change_is_identity():
    """Identical source/target bases leave rotations unchanged."""

    ue5_basis = np.eye(3, dtype=np.float64)
    aurora_basis = np.eye(3, dtype=np.float64)
    basis_change = compute_basis_change_matrix(ue5_basis, aurora_basis)

    test_quat = (0.70710678, 0.0, 0.70710678, 0.0)
    result = conjugate_quat_wxyz(test_quat, basis_change)

    assert basis_change == pytest.approx(np.eye(3))
    assert _quats_close(result, test_quat)


def test_orthogonal_basis_swap_maps_twist_axis():
    """A source X-axis twist maps onto the target Y twist axis."""

    ue5_basis = np.asarray(
        (
            (0.0, -1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    aurora_basis = np.eye(3, dtype=np.float64)
    basis_change = compute_basis_change_matrix(ue5_basis, aurora_basis)

    ue5_twist = (0.70710678, 0.70710678, 0.0, 0.0)
    result = conjugate_quat_wxyz(ue5_twist, basis_change)

    expected_aurora_twist = (0.70710678, 0.0, 0.70710678, 0.0)
    assert _quats_close(result, expected_aurora_twist, tolerance=1e-5)


def test_rest_pose_delta_survives_any_basis_as_identity():
    """Conjugating an identity rest delta must stay identity."""

    angle = 0.5
    c = np.cos(angle)
    s = np.sin(angle)
    arbitrary_basis = np.asarray(
        (
            (c, -s, 0.0),
            (s, c, 0.0),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )

    result = conjugate_quat_wxyz((1.0, 0.0, 0.0, 0.0), arbitrary_basis)

    assert _quats_close(result, (1.0, 0.0, 0.0, 0.0))


def test_degenerate_basis_halts():
    """Malformed rest bases must fail before writing bad animation data."""

    with pytest.raises(ValueError, match="Degenerate"):
        compute_basis_change_matrix(np.zeros((3, 3)), np.eye(3))
