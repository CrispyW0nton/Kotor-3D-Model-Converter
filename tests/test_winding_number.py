"""Tests for native/GhostRigger.Core.Math/Python/src/math/winding_number.py.

Foundation module for containment-v2.  The module is loaded directly by file
path (rather than imported as ``math.winding_number``, which would shadow the
stdlib ``math`` package) to keep the test independent of the embedded-Python
namespace wiring.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")


def _load_winding_number_module():
    path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "native"
        / "GhostRigger.Core.Math"
        / "Python"
        / "src"
        / "math"
        / "winding_number.py"
    )
    spec = importlib.util.spec_from_file_location("gr_winding_number", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gr_winding_number"] = module
    spec.loader.exec_module(module)
    return module


wn = _load_winding_number_module()


# ---------------------------------------------------------------------------
# 1. Watertight unit cube GWN
# ---------------------------------------------------------------------------

def test_gwn_unit_cube_inside_outside() -> None:
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))  # spans [-1, 1]^3
    inside = np.array([[0.0, 0.0, 0.0], [0.5, -0.3, 0.2], [-0.4, 0.6, -0.1]])
    outside = np.array([[5.0, 5.0, 5.0], [3.0, 0.0, 0.0], [0.0, -4.0, 2.0]])

    gwn_inside = wn.generalized_winding_number(inside, box.vertices, box.faces)
    gwn_outside = wn.generalized_winding_number(outside, box.vertices, box.faces)

    assert gwn_inside.shape == (3,)
    assert gwn_inside.dtype == np.float64
    assert np.all(gwn_inside > 0.99), gwn_inside
    assert np.all(np.abs(gwn_outside) < 0.01), gwn_outside


# ---------------------------------------------------------------------------
# 2. Degenerate (zero-area) triangles must not produce NaN
# ---------------------------------------------------------------------------

def test_gwn_degenerate_triangle_no_nan() -> None:
    # Vertices 0,1,2 are collinear -> face (0,1,2) has zero area.
    # Face (0,2,3) is a real triangle.  Also include a face with a repeated
    # vertex index (3,3,1) -> zero area by construction.
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3], [3, 3, 1]])
    query = np.array([[0.1, 0.1, 0.1], [10.0, 10.0, 10.0], [0.0, 0.0, 0.0]])

    gwn = wn.generalized_winding_number(query, vertices, faces)

    assert gwn.shape == (3,)
    assert not np.any(np.isnan(gwn)), gwn
    assert np.all(np.isfinite(gwn)), gwn


# ---------------------------------------------------------------------------
# 3. Otsu threshold: valley on bimodal cube sample, unimodal on noise
# ---------------------------------------------------------------------------

def test_otsu_finds_valley_on_cube_sample() -> None:
    # Unit box [-0.5, 0.5] sampled from the larger bbox [-1, 1]^3 -> ~1/8 of
    # points are inside (GWN ~1), the rest outside (GWN ~0): clearly bimodal.
    box = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    rng = np.random.default_rng(1234)
    samples = rng.uniform(-1.0, 1.0, size=(4000, 3))
    gwn_samples = wn.generalized_winding_number(samples, box.vertices, box.faces)

    threshold, diag = wn.adaptive_winding_threshold(gwn_samples)

    assert diag["unimodal"] is False
    assert diag["valley_location"] is not None
    assert 0.25 < threshold < 0.75, threshold
    assert abs(diag["valley_location"] - 0.5) < 0.25
    assert diag["sample_count"] == 4000


def test_otsu_declares_unimodal_on_noise() -> None:
    rng = np.random.default_rng(7)
    noise = rng.uniform(0.0, 1.0, size=5000)

    threshold, diag = wn.adaptive_winding_threshold(noise)

    assert diag["unimodal"] is True
    assert threshold == wn.DEFAULT_WINDING_THRESHOLD
    assert diag["valley_location"] is None
    assert diag["sample_count"] == 5000


# ---------------------------------------------------------------------------
# 4. Normal repair trust diagnostics
# ---------------------------------------------------------------------------

def test_repair_normals_trusts_clean_watertight_mesh() -> None:
    ico = trimesh.creation.icosphere(subdivisions=3, radius=1.0)

    repaired, diag = wn.repair_normals(ico)

    assert diag["consistent"] is True
    assert diag["inconsistent_edge_fraction"] == pytest.approx(0.0)
    assert diag["should_trust_normals"] is True
    assert repaired.faces.shape[0] > 0


def test_repair_normals_rejects_triangle_soup() -> None:
    # Three unconnected triangles with arbitrary winding: no shared edges, so
    # orientation cannot be verified -> normals must not be trusted.
    rng = np.random.default_rng(99)
    vertices = rng.uniform(-5.0, 5.0, size=(9, 3))
    faces = np.array([[0, 1, 2], [3, 5, 4], [6, 7, 8]])  # middle face flipped
    soup = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    _repaired, diag = wn.repair_normals(soup)

    assert diag["should_trust_normals"] is False
    assert diag["consistent"] is False
    assert diag["inconsistent_edge_fraction"] >= 0.0


# ---------------------------------------------------------------------------
# 5. End-to-end classification on an open creature shell
# ---------------------------------------------------------------------------

def _open_shell() -> "trimesh.Trimesh":
    """Icosphere with the top ~10% of faces removed (a hole in the top)."""
    ico = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    centroid_z = ico.triangles_center[:, 2]
    keep = centroid_z < np.percentile(centroid_z, 90.0)
    return trimesh.Trimesh(
        vertices=ico.vertices.copy(),
        faces=ico.faces[keep].copy(),
        process=False,
    )


def test_classify_points_open_shell() -> None:
    shell = _open_shell()
    rng = np.random.default_rng(2024)

    # Inside points: deep in the lower/central interior, away from the hole.
    dirs_in = rng.normal(size=(100, 3))
    dirs_in /= np.linalg.norm(dirs_in, axis=1, keepdims=True)
    radii_in = rng.uniform(0.0, 0.6, size=100)
    inside_pts = dirs_in * radii_in[:, None]
    inside_pts[:, 2] -= 0.15  # bias downward, away from the top hole

    # Outside points: far from the surface, including directly above the hole.
    dirs_out = rng.normal(size=(100, 3))
    dirs_out /= np.linalg.norm(dirs_out, axis=1, keepdims=True)
    radii_out = rng.uniform(1.6, 3.0, size=100)
    outside_pts = dirs_out * radii_out[:, None]
    outside_pts[:5] = np.array([[0.0, 0.0, z] for z in (1.8, 2.0, 2.4, 2.8, 3.0)])

    points = np.vstack([inside_pts, outside_pts])
    result = wn.classify_points(points, shell)

    mask = result["inside_mask"]
    assert mask.shape == (200,)
    assert result["gwn_values"].shape == (200,)
    assert result["signed_distance"].shape == (200,)

    inside_correct = int(np.count_nonzero(mask[:100]))
    outside_correct = int(np.count_nonzero(~mask[100:]))
    assert inside_correct >= 95, (inside_correct, result["threshold"])
    assert outside_correct >= 95, (outside_correct, result["threshold"])


# ---------------------------------------------------------------------------
# Bonus: signed-distance sign convention (documents the trimesh negation)
# ---------------------------------------------------------------------------

def test_signed_distance_sign_convention() -> None:
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    points = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])

    sd = wn.signed_distance_to_surface(points, box)

    assert sd[0] < 0.0  # inside  -> negative
    assert sd[1] > 0.0  # outside -> positive
