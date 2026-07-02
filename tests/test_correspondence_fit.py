"""Tests for correspondence_fit.fit_skeleton_by_correspondence (T2509b) in
native/GhostRigger.Core.Math/Python/src/math/correspondence_fit.py.

Correspondence fit = align-then-refine (Option 1 Stage 3): shape-normalise +
24-rotation pre-alignment, nearest-surface correspondence, weighted-Umeyama
refinement, rigid skeleton carry, Falsifiers A (rim-ratio preservation) and B
(refinement-scale bracket).

Drexl notes: the K2 c_drexlf donor + C_DrexlF_UV.obj pair is a SELF-FIT case
(post-T2508 transfer confidence 1.0), so Falsifier A passes trivially there —
presence check, not calibration; calibration is T2510 debt.  The total scale
(~0.11: world-frame donor onto the compact normalized OBJ) is a diagnostic,
never asserted against `initial_scale_estimate` (containment heuristic, ~8.99).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
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


cf = _load_module(
    "gr_correspondence_fit",
    "native/GhostRigger.Core.Math/Python/src/math/correspondence_fit.py",
)
ap = _load_module(
    "gr_anatomical_partition_cf",
    "native/GhostRigger.Core.Math/Python/src/math/anatomical_partition.py",
)


# ---------------------------------------------------------------------------
# Synthetic donor builders
# ---------------------------------------------------------------------------


def _box_donor(subdivisions: int = 2):
    """A subdivided ANISOTROPIC box as a world-frame donor with 2 real bones.

    Anisotropic extents make the 24-rotation alignment optimum unique (a cube
    is symmetric under the whole octahedral group, which would make the
    recovered rotation arbitrary and the bone-carry assertion flaky).  Bone 0
    owns the x<0 half, bone 1 the x>=0 half; both influence enough vertices
    with enough spread to classify as real.
    """
    mesh = trimesh.creation.box(extents=(1.0, 0.6, 0.3))
    for _ in range(subdivisions):
        mesh = mesh.subdivide()
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    primary = (verts[:, 0] >= 0).astype(np.int64)
    k = 4
    bone_indices = np.full((len(verts), k), -1, dtype=np.int64)
    bone_weights = np.zeros((len(verts), k), dtype=np.float64)
    bone_indices[:, 0] = primary
    bone_weights[:, 0] = 1.0

    # Slightly inside the box and off any subdivided vertex so d_nearest > 0
    # (a bone exactly on a mesh vertex has rim ratio 0 and is skipped by
    # Falsifier A's near-zero guard — the synthetic must exercise scoring).
    bone_positions = np.array([[-0.4, 0.07, 0.03], [0.4, 0.07, 0.03]])
    return ap.DonorSkinData(
        vertices=verts,
        faces=faces,
        bone_indices=bone_indices,
        bone_weights=bone_weights,
        bone_names=["bone_L", "bone_R"],
        bone_positions=bone_positions,
        frame="world_space_v1",
    )


def _transformed_copy(donor, scale: float, translation) -> tuple:
    """The donor's own mesh under a known similarity — an 'imported' twin."""
    verts = scale * np.asarray(donor.vertices, dtype=np.float64) + np.asarray(
        translation, dtype=np.float64
    )
    return verts, np.asarray(donor.faces, dtype=np.int64)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_use_v3_false_returns_none() -> None:
    donor = _box_donor()
    iv, if_ = _transformed_copy(donor, 1.0, (0.0, 0.0, 0.0))
    assert cf.fit_skeleton_by_correspondence(iv, if_, donor) is None


def test_missing_world_frame_raises() -> None:
    donor = _box_donor()
    bad = ap.DonorSkinData(
        vertices=donor.vertices,
        faces=donor.faces,
        bone_indices=donor.bone_indices,
        bone_weights=donor.bone_weights,
        bone_names=donor.bone_names,
        bone_positions=donor.bone_positions,
        frame="unspecified",
    )
    iv, if_ = _transformed_copy(donor, 1.0, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="world_space_v1"):
        cf.fit_skeleton_by_correspondence(iv, if_, bad, use_v3=True)


def test_empty_skeleton_raises() -> None:
    donor = _box_donor()
    empty = ap.DonorSkinData(
        vertices=donor.vertices,
        faces=donor.faces,
        bone_indices=np.full_like(donor.bone_indices, -1),
        bone_weights=np.zeros_like(donor.bone_weights),
        bone_names=[],
        bone_positions=np.zeros((0, 3)),
        frame="world_space_v1",
    )
    iv, if_ = _transformed_copy(donor, 1.0, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="no bones"):
        cf.fit_skeleton_by_correspondence(iv, if_, empty, use_v3=True)


# ---------------------------------------------------------------------------
# Degenerate donor bone filter
# ---------------------------------------------------------------------------


def test_degenerate_filter_duplicate_position_primary() -> None:
    """Two bones at one world position are BOTH degenerate via filter 1, even
    when their influence sets would pass filters 2/3 (ordering is load-bearing)."""
    donor = _box_donor()
    dup_positions = donor.bone_positions.copy()
    dup_positions[1] = dup_positions[0]  # collapse onto bone 0
    dup = ap.DonorSkinData(
        vertices=donor.vertices,
        faces=donor.faces,
        bone_indices=donor.bone_indices,
        bone_weights=donor.bone_weights,
        bone_names=donor.bone_names,
        bone_positions=dup_positions,
        frame="world_space_v1",
    )
    degenerate, real = cf._classify_donor_bones(dup)
    assert degenerate == {
        "bone_L": "duplicate_position_with_bone_R",
        "bone_R": "duplicate_position_with_bone_L",
    }
    assert real == {}


# ---------------------------------------------------------------------------
# Synthetic end-to-end fits
# ---------------------------------------------------------------------------


def test_synthetic_uniform_scale_recovery() -> None:
    donor = _box_donor()
    iv, if_ = _transformed_copy(donor, 2.0, (5.0, 0.0, 0.0))

    result = cf.fit_skeleton_by_correspondence(iv, if_, donor, use_v3=True)
    assert result is not None
    assert abs(result.scale - 2.0) < 0.01
    # Bones carried by the same similarity as the mesh.
    expected_bones = 2.0 * donor.bone_positions + np.array([5.0, 0.0, 0.0])
    assert np.allclose(result.fitted_bone_positions, expected_bones, atol=0.02)
    assert result.surface_confidence > 0.99
    assert result.falsifier_b["passed"], result.falsifier_b
    # Refinement scale ~1: pre-alignment already matched the global scale.
    assert abs(result.diagnostics["refinement_scale"] - 1.0) < 0.05


def test_ratio_preservation_on_synthetic_fit() -> None:
    """Falsifier A scores the 2 real bones and passes (rim ratios are
    similarity-invariant).  First non-trivial Falsifier A run; RATIO_TOLERANCE
    calibration itself is T2510 debt."""
    donor = _box_donor()
    iv, if_ = _transformed_copy(donor, 1.3, (0.0, -2.0, 1.0))

    result = cf.fit_skeleton_by_correspondence(iv, if_, donor, use_v3=True)
    assert result is not None
    assert result.real_bone_count == 2
    assert result.falsifier_a["n_real_bones_scored"] == 2
    assert result.falsifier_a["passed"], result.falsifier_a["violations"]
    assert result.falsifier_a["tolerance_used"] == pytest.approx(0.50)


def test_falsifier_b_bracket_contract() -> None:
    """Falsifier B is the balloon guard on the refinement scale: outside
    [0.5, 2.0] fails, inside passes; the report is a signal, not an exception."""
    ok = cf._run_falsifier_b(1.0)
    assert ok["passed"] and ok["bracket"] == [0.5, 2.0]
    assert cf._run_falsifier_b(0.5)["passed"]
    assert cf._run_falsifier_b(2.0)["passed"]
    assert not cf._run_falsifier_b(0.3)["passed"]
    assert not cf._run_falsifier_b(2.5)["passed"]
    assert not cf._run_falsifier_b(20.0)["passed"]  # the v2 balloon signature


def test_trace_version_stable() -> None:
    donor = _box_donor()
    iv, if_ = _transformed_copy(donor, 1.0, (0.0, 0.0, 0.0))
    result = cf.fit_skeleton_by_correspondence(iv, if_, donor, use_v3=True)
    assert result is not None
    assert result.trace_version == "ghostrigger.correspondence/v1"


# ---------------------------------------------------------------------------
# Drexl self-fit acceptance (K2-gated)
# ---------------------------------------------------------------------------


def test_drexl_correspondence_self_fit(capsys) -> None:
    """Load-bearing Drexl acceptance for T2509b.

    Drexl is a SELF-FIT case (C_DrexlF_UV.obj is geometrically the donor,
    transfer confidence 1.0 post-T2508), so: surface correspondence must be
    near-perfect, the refinement scale near-identity, and the collapsed wing
    chain must land in the degenerate bucket via the duplicate-position filter.
    Falsifier A passes trivially here — presence check, not calibration (T2510).
    The total scale (~0.11) is recorded as a diagnostic only; it is NOT compared
    to initial_scale_estimate (containment heuristic ~8.99 — different quantity).
    """
    from tests.test_anatomical_partition import _load_drexl_model, _load_imported_drexl

    try:
        from src.core.game.kotor_loader import build_donor_skin_data_from_model
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"donor builder unavailable: {exc}")

    model = _load_drexl_model()
    donor = build_donor_skin_data_from_model(model)
    iv, if_ = _load_imported_drexl()

    result = cf.fit_skeleton_by_correspondence(iv, if_, donor, use_v3=True)
    assert result is not None

    with capsys.disabled():
        d = result.diagnostics
        print("\n=== T2509b Drexl self-fit ===")
        print(
            f"surface_confidence={result.surface_confidence:.4f}  "
            f"pre_scale={d['pre_alignment_scale']:.4f}  "
            f"refine_scale={d['refinement_scale']:.4f}  "
            f"total_scale={d['total_scale']:.4f}"
        )
        print(
            f"falsifier_a passed={result.falsifier_a['passed']} "
            f"scored={result.falsifier_a['n_real_bones_scored']}  "
            f"falsifier_b passed={result.falsifier_b['passed']}"
        )
        print(f"degenerate ({len(result.degenerate_donor_bones)}): "
              f"{result.degenerate_donor_bones}")
        print(f"real_bone_count={result.real_bone_count}  "
              f"init_scale_est(diag)={result.initial_scale_estimate:.4f}")

    # Surface correspondence: self-fit must be near-perfect post align+refine.
    assert result.surface_confidence >= 0.99, result.surface_confidence

    # Refinement near-identity (pre-alignment already matched global scale).
    assert abs(result.diagnostics["refinement_scale"] - 1.0) < 0.05

    # No balloon.
    assert result.falsifier_b["passed"], result.falsifier_b

    # Collapsed wing chain lands in the degenerate bucket via filter 1.
    for wing in ("Rwing_03", "Rwing_05", "Rwing_07"):
        assert wing in result.degenerate_donor_bones, result.degenerate_donor_bones
        assert result.degenerate_donor_bones[wing].startswith("duplicate_position"), (
            wing,
            result.degenerate_donor_bones[wing],
        )

    # Plenty of real bones remain for Falsifier A to score.
    assert result.real_bone_count >= 40
    assert result.falsifier_a["passed"], result.falsifier_a["violations"]
