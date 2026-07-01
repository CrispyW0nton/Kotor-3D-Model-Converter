"""Tests for fit_skeleton_inside_mesh_v2 in
native/GhostRigger.Core.Math/Python/src/math/containment_fit.py (PR B).

v2 uses the Generalized Winding Number oracle (PR A's winding_number.py) as its
inside-test, replacing v1's 7-ray parity check for open-shell creature meshes.

The module is loaded directly by file path (rather than imported as
``math.containment_fit``, which would shadow the stdlib ``math`` package) to keep
the test independent of the embedded-Python namespace wiring -- the same pattern
used by test_winding_number.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("scipy")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FIXTURE_PATH = _ROOT / "tests" / "fixtures" / "drexl_baseline_2026_06_30.json"

# 5 donor deformation bones (KotOR/donor space) frozen by the baseline fit.
# The baseline fixture does not store per-bone positions (see PR A gate note),
# so these mirror scripts/drexl_gwn_gate.py -- the single source of truth for
# the anchors the baseline oriented-bounds fit was measured against.
_DREXL_BONES = {
    "pelvis_g": (0.01, -0.06, 1.45),
    "tail6_g": (0.25, -4.91, 1.71),
    "Lhand_g": (-0.84, 0.10, 1.49),
    "Rhand_g": (0.87, 0.10, 1.41),
    "head_g": (0.03, 1.72, 2.03),
}


def _load_containment_fit():
    path = (
        _ROOT
        / "native"
        / "GhostRigger.Core.Math"
        / "Python"
        / "src"
        / "math"
        / "containment_fit.py"
    )
    spec = importlib.util.spec_from_file_location("gr_containment_fit", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gr_containment_fit"] = module
    spec.loader.exec_module(module)
    return module


cf = _load_containment_fit()


def _unit_box(extent: float = 2.0):
    box = trimesh.creation.box(extents=(extent, extent, extent))
    return (
        np.asarray(box.vertices, dtype=np.float64),
        np.asarray(box.faces, dtype=np.int64),
    )


def _find_drexl_obj() -> "pathlib.Path | None":
    candidates = [
        os.environ.get("GHOSTRIGGER_DREXL_OBJ"),
        os.environ.get("DREXL_PATH"),
        r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\Drexl\C_DrexlF_UV.obj",
        str(_ROOT / ".hermes" / "desktop-attachments" / "C_DrexlF_UV.obj"),
    ]
    for c in candidates:
        if c and pathlib.Path(c).is_file():
            return pathlib.Path(c)
    return None


# ---------------------------------------------------------------------------
# 1. use_v2=False is byte-identical to v1
# ---------------------------------------------------------------------------

def test_v2_default_use_v2_false_is_v1_byte_identical() -> None:
    verts, faces = _unit_box()
    bones = np.array(
        [[0.0, 0.0, 0.0], [0.3, -0.2, 0.1], [-0.25, 0.15, -0.2]], dtype=np.float64
    )

    v1 = cf.fit_skeleton_inside_mesh(verts, faces, bones)
    v2 = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones)  # default use_v2=False

    assert v2 == v1
    # v1 has no v2-only keys.
    assert "containment_fit" not in v2
    assert "trace_version" not in v2


# ---------------------------------------------------------------------------
# 2. Real Drexl mesh converges with margin under v2
# ---------------------------------------------------------------------------

def test_v2_drexl_regression_documents_single_mesh_balloon() -> None:
    """Lock in the single-mesh containment balloon finding on real Drexl.

    v2 is a genuine correctness win: unlike today's oriented-bounds fit (which
    reports outside_count=0 against a bounding box while leaving all 5 bones
    1.0-1.6 units OUTSIDE the actual shell, measured in PR A's gate), v2's GWN
    oracle achieves true shell containment with margin for every bone.

    BUT it can only do so at scale ~87 (~10x today's ~8.83).  Per-hypothesis
    analysis confirmed this is a geometric impossibility, not a solver failure:
    Drexl's tail/hand/torso bones cannot simultaneously sit inside their
    respective silhouettes under any single rigid similarity transform.  This
    test locks in that diagnostic behaviour (converged containment + a scale
    balloon) as the falsifier that motivates PR C (anatomical decomposition):
    it should be inverted to expect a sane per-region scale once PR C provides
    per-region fitting.
    """
    obj_path = _find_drexl_obj()
    if obj_path is None:
        pytest.skip("Drexl OBJ not available (set GHOSTRIGGER_DREXL_OBJ)")

    drexl = trimesh.load(str(obj_path), process=False, force="mesh")
    verts = np.asarray(drexl.vertices, dtype=np.float64)
    faces = np.asarray(drexl.faces, dtype=np.int64)

    names = list(_DREXL_BONES.keys())
    bones = np.array(list(_DREXL_BONES.values()), dtype=np.float64)

    result = cf.fit_skeleton_inside_mesh_v2(
        verts,
        faces,
        bones,
        bone_names=names,
        use_v2=True,
        target_margin=0.3,
        margin_relative_to="shell_diagonal",
    )
    fit = result["containment_fit"]

    # The genuine v2 contract and the real improvement over today: unlike the
    # baseline oriented-bounds box fit (which leaves all 5 bones 1.0-1.6 units
    # OUTSIDE the shell, measured in PR A's gate), v2's GWN oracle achieves true
    # shell containment with margin for every bone.
    assert fit["v2_normal_repair"]["should_trust_normals"] is True
    assert fit["v2_status"] == "converged"
    assert all(fit["v2_bone_inside_mask"])
    # half the target margin tolerance for optimizer imprecision
    assert all(sd <= -0.15 for sd in fit["v2_bone_signed_distances"])

    # FINDING (splitter-relevant, see CHANGES.md / report): a single rigid
    # containment cannot fit Drexl's full deformation skeleton at a body scale.
    # Every rotation hypothesis needs scale ~80-200 to engulf the tail (tail6_g)
    # and hand extremities that sit outside the torso silhouette at the baseline
    # scale (~8.83).  The fit is mathematically valid but ~10x oversized -- this
    # is direct evidence the anatomical node splitter (PR C) is a prerequisite,
    # not polish.  The bound below is a regression guard for that balloon; if a
    # future change brings Drexl under a sane body scale, revisit this test.
    assert result["scale"] > 25.0, (
        f"Drexl fit scale {result['scale']:.2f} unexpectedly sane -- re-evaluate "
        "the single-mesh containment / splitter assumption"
    )
    assert np.isfinite(result["scale"])


# ---------------------------------------------------------------------------
# 3. Synthetic watertight sphere converges quickly
# ---------------------------------------------------------------------------

def test_v2_synthetic_watertight_sphere_converges() -> None:
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    verts = np.asarray(sphere.vertices, dtype=np.float64)
    faces = np.asarray(sphere.faces, dtype=np.int64)

    bones = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.15, 0.0, 0.0],
            [0.0, 0.15, 0.0],
            [0.0, 0.0, 0.15],
            [-0.1, -0.1, 0.0],
        ],
        dtype=np.float64,
    )

    result = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones, use_v2=True)
    fit = result["containment_fit"]

    assert fit["v2_status"] == "converged"
    assert all(fit["v2_bone_inside_mask"])
    assert fit["v2_rotation_hypotheses_feasible"] >= 1


# ---------------------------------------------------------------------------
# 4. Untrustworthy normals (triangle soup) delegates to v1
# ---------------------------------------------------------------------------

def test_v2_untrustworthy_normals_delegates_to_v1() -> None:
    # 3 disjoint triangles: no shared edges -> winding cannot be verified ->
    # repair_normals reports should_trust_normals=False.
    verts = np.array(
        [
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
            [5.0, 5.0, 5.0], [6.0, 5.0, 5.0], [5.0, 6.0, 5.0],
            [-5.0, -5.0, -5.0], [-4.0, -5.0, -5.0], [-5.0, -4.0, -5.0],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]], dtype=np.int64)
    bones = np.array([[0.2, 0.2, 0.0], [0.1, 0.1, 0.0]], dtype=np.float64)

    v1 = cf.fit_skeleton_inside_mesh(verts, faces, bones)
    result = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones, use_v2=True)
    fit = result["containment_fit"]

    assert fit["v2_status"] == "delegated_to_v1"
    assert fit["v2_fallback_reason"] == "untrustworthy_normals"
    # v1 core keys preserved unchanged.
    for key in ("translation", "scale", "rotation_matrix", "all_inside",
                "outside_count", "max_penetration", "method", "iterations", "rmsd"):
        assert result[key] == v1[key]


# ---------------------------------------------------------------------------
# 5. Geometrically infeasible input returns an honest partial fit
# ---------------------------------------------------------------------------

def test_v2_infeasible_input_returns_partial_fit() -> None:
    # A very thin slab cannot contain a fully 3D bone spread at any uniform
    # scale (aspect ratio is scale-invariant) nor within the per-axis clamp.
    slab = trimesh.creation.box(extents=(2.0, 2.0, 0.02))
    verts = np.asarray(slab.vertices, dtype=np.float64)
    faces = np.asarray(slab.faces, dtype=np.int64)

    corners = np.array(
        [
            [2, 2, 2], [2, 2, -2], [2, -2, 2], [2, -2, -2],
            [-2, 2, 2], [-2, 2, -2], [-2, -2, 2], [-2, -2, -2],
        ],
        dtype=np.float64,
    )

    result = cf.fit_skeleton_inside_mesh_v2(verts, faces, corners, use_v2=True)
    fit = result["containment_fit"]

    assert fit["v2_status"] == "partial_fit"
    assert fit["v2_unresolved_anchors"]  # non-empty


# ---------------------------------------------------------------------------
# 6. v2 containment_fit schema is v1-compatible (extend-by-prefix)
# ---------------------------------------------------------------------------

def test_v2_schema_v1_compatible() -> None:
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    verts = np.asarray(sphere.vertices, dtype=np.float64)
    faces = np.asarray(sphere.faces, dtype=np.int64)
    bones = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.1, 0.0]], dtype=np.float64)

    result = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones, use_v2=True)
    v2_containment = result["containment_fit"]

    baseline = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    v1_containment = baseline["fit_report"]["containment_fit"]

    for key, value in v2_containment.items():
        if key.startswith("v2_"):
            continue  # new optional fields
        assert key in v1_containment, f"non-v2_ key {key!r} not in v1 schema"
        assert type(value) is type(v1_containment[key]), (
            f"type of {key!r} changed: {type(value)} vs {type(v1_containment[key])}"
        )


# ---------------------------------------------------------------------------
# 7. trace_version is never bumped by v2
# ---------------------------------------------------------------------------

def test_v2_trace_version_unchanged() -> None:
    verts, faces = _unit_box()
    bones = np.array([[0.0, 0.0, 0.0], [0.2, 0.1, -0.1]], dtype=np.float64)

    off = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones, use_v2=False)
    on = cf.fit_skeleton_inside_mesh_v2(verts, faces, bones, use_v2=True)

    # use_v2=False stays byte-identical to v1 (no trace_version key); absence is
    # implicitly v1. use_v2=True carries the version explicitly, still v1.
    assert off.get("trace_version", "ghostrigger.fit/v1") == "ghostrigger.fit/v1"
    assert on["trace_version"] == "ghostrigger.fit/v1"
