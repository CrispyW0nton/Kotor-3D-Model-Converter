"""Tests for landmark_alignment's T2509a additions in
native/GhostRigger.Core.Math/Python/src/math/landmark_alignment.py:

- compute_weighted_rigid_transform (weighted Umeyama, same conventions as the
  existing unweighted compute_rigid_transform)
- normalise_cloud + best_alignment_rotation (migrated from
  anatomical_partition Phase 2; consumed by correspondence fit in T2509b)

Modules are loaded by file path (the PR B/C pattern) so the tests run without
package context and do not shadow the stdlib ``math`` package.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

pytest.importorskip("scipy")

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(mod_name: str, rel_path: str):
    path = _ROOT.joinpath(*rel_path.split("/"))
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


la = _load_module(
    "gr_landmark_alignment",
    "native/GhostRigger.Core.Math/Python/src/math/landmark_alignment.py",
)


def _random_similarity_pair(n: int = 40, seed: int = 7):
    """Random cloud + its image under a known proper similarity (s, R, t)."""
    rng = np.random.default_rng(seed)
    source = rng.normal(size=(n, 3))
    # Proper rotation from QR (det fixed to +1).
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    scale = 1.7
    t = np.array([3.0, -1.0, 0.5])
    target = scale * (source @ q.T) + t
    return source, target, q, t, scale


# ---------------------------------------------------------------------------
# compute_weighted_rigid_transform
# ---------------------------------------------------------------------------


def test_uniform_weights_match_unweighted() -> None:
    source, target, _, _, _ = _random_similarity_pair()
    R_u, t_u, s_u = la.compute_rigid_transform(source, target)
    R_w, t_w, s_w = la.compute_weighted_rigid_transform(
        source, target, np.ones(len(source))
    )
    assert np.allclose(R_w, R_u, atol=1e-10)
    assert np.allclose(t_w, t_u, atol=1e-10)
    assert abs(s_w - s_u) < 1e-10


def test_exact_similarity_recovered() -> None:
    source, target, R_true, t_true, s_true = _random_similarity_pair()
    R, t, s = la.compute_weighted_rigid_transform(source, target, np.ones(len(source)))
    assert np.allclose(R, R_true, atol=1e-9)
    assert np.allclose(t, t_true, atol=1e-9)
    assert abs(s - s_true) < 1e-9
    assert abs(np.linalg.det(R) - 1.0) < 1e-9


def test_weighted_preference_honours_heavy_pair() -> None:
    rng = np.random.default_rng(11)
    source, target, _, _, _ = _random_similarity_pair(n=10, seed=11)
    # Corrupt the 9 light pairs so no exact similarity exists; keep pair 0 exact.
    target_noisy = target.copy()
    target_noisy[1:] += rng.normal(scale=0.5, size=(9, 3))
    weights = np.ones(10)
    weights[0] = 1000.0

    R, t, s = la.compute_weighted_rigid_transform(source, target_noisy, weights)
    fitted = s * (source @ R.T) + t
    residuals = np.linalg.norm(fitted - target_noisy, axis=1)
    assert residuals[0] < 0.01, f"heavy pair residual {residuals[0]:.4f}"
    assert residuals[0] < residuals[1:].mean()


def test_zero_weight_point_excluded() -> None:
    source, target, _, _, _ = _random_similarity_pair(n=12, seed=3)
    target = target.copy()
    target[5] += np.array([100.0, 0.0, 0.0])  # gross outlier

    weights = np.ones(12)
    weights[5] = 0.0
    R_a, t_a, s_a = la.compute_weighted_rigid_transform(source, target, weights)

    keep = np.arange(12) != 5
    R_b, t_b, s_b = la.compute_weighted_rigid_transform(
        source[keep], target[keep], np.ones(11)
    )
    assert np.allclose(R_a, R_b, atol=1e-10)
    assert np.allclose(t_a, t_b, atol=1e-10)
    assert abs(s_a - s_b) < 1e-10


def test_reflection_correction_gives_proper_rotation() -> None:
    source, _, _, _, _ = _random_similarity_pair(n=30, seed=5)
    mirrored = source.copy()
    mirrored[:, 0] = -mirrored[:, 0]
    R, _, _ = la.compute_weighted_rigid_transform(source, mirrored, np.ones(30))
    assert abs(np.linalg.det(R) - 1.0) < 1e-9  # proper rotation, never a mirror


def test_all_zero_weights_raises() -> None:
    source, target, _, _, _ = _random_similarity_pair(n=8, seed=2)
    with pytest.raises(ValueError):
        la.compute_weighted_rigid_transform(source, target, np.zeros(8))
    with pytest.raises(ValueError):
        la.compute_weighted_rigid_transform(source, target, -np.ones(8))


def test_degenerate_colinear_falls_back_to_translation() -> None:
    ts = np.linspace(0.0, 1.0, 10)
    source = np.stack([ts, np.zeros(10), np.zeros(10)], axis=1)
    target = source + np.array([2.0, 3.0, -1.0])
    R, t, s = la.compute_weighted_rigid_transform(source, target, np.ones(10))
    assert np.allclose(R, np.eye(3), atol=1e-10)
    assert s == 1.0
    assert np.allclose(t, [2.0, 3.0, -1.0], atol=1e-10)


# ---------------------------------------------------------------------------
# normalise_cloud + best_alignment_rotation (migrated from anatomical_partition)
# ---------------------------------------------------------------------------


def test_normalise_cloud_contract() -> None:
    rng = np.random.default_rng(9)
    pts = rng.normal(loc=5.0, scale=3.0, size=(50, 3))
    norm, centre, rms = la.normalise_cloud(pts)
    assert np.allclose(norm.mean(axis=0), 0.0, atol=1e-12)
    assert abs(np.sqrt(np.mean(np.sum(norm * norm, axis=1))) - 1.0) < 1e-12
    assert np.allclose(centre, pts.mean(axis=0))
    assert rms > 0.0


def test_best_alignment_rotation_recovers_axis_rotation() -> None:
    rng = np.random.default_rng(13)
    donor = rng.normal(size=(200, 3))
    donor[:, 1] *= 4.0  # anisotropic so the optimum is unique
    # 90° about Z is an octahedral-group member; imported = donor rotated by it.
    Rz = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    imported = donor @ Rz.T

    R = la.best_alignment_rotation(imported, donor)  # array target
    aligned = imported @ R.T
    assert float(np.abs(aligned - donor).max()) < 1e-9

    from scipy.spatial import cKDTree

    R2 = la.best_alignment_rotation(imported, cKDTree(donor))  # tree target
    assert np.allclose(R2, R, atol=1e-12)


def test_best_alignment_rotation_identity_when_aligned() -> None:
    rng = np.random.default_rng(17)
    cloud = rng.normal(size=(120, 3))
    cloud[:, 0] *= 3.0
    R = la.best_alignment_rotation(cloud, cloud)
    assert np.allclose(R, np.eye(3), atol=1e-12)


def test_anatomical_partition_delegates_to_landmark_alignment() -> None:
    """PR C's Phase 2 wrappers must return exactly what the canonical
    landmark_alignment implementations return (cross-module migration lock)."""
    ap = _load_module(
        "gr_anatomical_partition_la_test",
        "native/GhostRigger.Core.Math/Python/src/math/anatomical_partition.py",
    )
    rng = np.random.default_rng(21)
    donor = rng.normal(size=(80, 3))
    donor[:, 2] *= 2.5
    Rz = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    imported = donor @ Rz.T

    norm_ap = ap._normalise_cloud(donor)
    norm_la = la.normalise_cloud(donor)
    assert np.allclose(norm_ap[0], norm_la[0], atol=1e-12)

    from scipy.spatial import cKDTree

    tree = cKDTree(donor)
    R_ap = ap._best_alignment_rotation(imported, tree)
    R_la = la.best_alignment_rotation(imported, tree)
    assert np.allclose(R_ap, R_la, atol=1e-12)
