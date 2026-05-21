from pathlib import Path

import numpy as np
import pytest

from src.core.retargeting.coordinate_normalizer import BindPoseRegistry, CoordinateNormalizer
from src.core.retargeting.mesh_loader import load_kotor_skinned_mesh
from src.core.retargeting.mesh_rebinder import (
    BindPoseDegenerate,
    RebindOptions,
    SourceMesh,
    rebind_mesh_to_target_skeleton,
    redistribute_to_twist_bone,
)
from src.core.retargeting.sampler import DEFAULT_CORPUS_ROOT, load_fixture_model
from src.unreal.animation_retargeting import build_bone_map
from src.unreal.quinn import load_quinn_skeleton_asset, unreal_skeleton_model


def _fixture_path(resref: str) -> Path:
    return DEFAULT_CORPUS_ROOT / "k1" / f"{resref}.mdl"


def _quinn_model():
    return unreal_skeleton_model(load_quinn_skeleton_asset())


def _registries_and_map(resref: str = "pmbam"):
    normalizer = CoordinateNormalizer()
    source_model = load_fixture_model(resref)
    target_model = _quinn_model()
    source_registry = normalizer.normalize_aurora_bind(source_model, f"kotor_{resref}")
    target_registry = normalizer.normalize_ue5_bind(target_model, "ue5_quinn")
    mapping = build_bone_map(source_model, target_model).mapping
    return normalizer, source_registry, target_registry, mapping


def _rebind(
    resref: str = "pmbam",
    mesh_node_name: str | None = None,
    options: RebindOptions | None = None,
):
    normalizer, _source_registry, target_registry, mapping = _registries_and_map(resref)
    mesh = load_kotor_skinned_mesh(_fixture_path(resref), mesh_node_name=mesh_node_name)
    return mesh, rebind_mesh_to_target_skeleton(
        mesh,
        f"kotor_{resref}",
        "ue5_quinn",
        mapping,
        target_registry,
        normalizer,
        options or RebindOptions(),
    )


def test_preflight_validation_catches_degenerate_bind():
    identity = np.eye(4, dtype=np.float64)
    degenerate = np.eye(4, dtype=np.float64)
    degenerate[2, 2] = 0.0
    source_registry = BindPoseRegistry(
        skeleton_id="source",
        bone_names=["root"],
        bone_index={"root": 0},
        parents={},
        bind_world={"root": identity},
        bind_world_inv={"root": identity},
        local_bind={"root": identity},
    )
    target_registry = BindPoseRegistry(
        skeleton_id="target",
        bone_names=["root"],
        bone_index={"root": 0},
        parents={},
        bind_world={"root": degenerate},
        bind_world_inv={"root": identity},
        local_bind={"root": degenerate},
    )
    mesh = SourceMesh(
        name="synthetic",
        positions=np.asarray([[0.0, 0.0, 0.0]], dtype=np.float64),
        normals=np.asarray([[0.0, 0.0, 1.0]], dtype=np.float64),
        uvs=np.asarray([[0.0, 0.0]], dtype=np.float64),
        bone_indices=np.asarray([[0, -1, -1, -1]], dtype=np.int32),
        bone_weights=np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        faces=np.zeros((0, 3), dtype=np.int64),
        source_bind_world={"root": identity},
        bbox_diagonal=1.0,
        source_bone_names=["root"],
        source_bone_index={"root": 0},
        metadata={"source_registry": source_registry},
    )

    with pytest.raises(BindPoseDegenerate):
        rebind_mesh_to_target_skeleton(
            mesh,
            "source",
            "target",
            {"root": "root"},
            target_registry,
            CoordinateNormalizer(),
            RebindOptions(),
        )


def test_index_remap_table_correctness():
    mesh, rebound = _rebind("pmbam")
    remap = rebound.transplant_metadata["index_remap"]["source_to_target"]
    assert remap["lcollar_g"] == "clavicle_l"
    assert remap["rcollar_g"] == "clavicle_r"


def test_weight_conservation_pmbam():
    _mesh, rebound = _rebind("pmbam")
    drift = float(np.max(np.abs(rebound.bone_weights.astype(np.float64).sum(axis=1) - 1.0)))
    assert drift <= 1e-6


def test_no_invalid_indices_pmbam():
    _mesh, rebound = _rebind("pmbam")
    assert int(rebound.bone_indices.max()) < 89


def test_twist_redistribution_monotonic():
    parent = np.asarray([0.0, 0.0, 0.0], dtype=np.float64)
    child = np.asarray([1.0, 0.0, 0.0], dtype=np.float64)
    samples = np.asarray([[t, 0.0, 0.0] for t in np.linspace(0.0, 1.0, 10)], dtype=np.float64)
    twist_weights = [
        redistribute_to_twist_bone(sample, parent, child, twist_curve="smoothstep")[1]
        for sample in samples
    ]
    assert all(a <= b + 1e-12 for a, b in zip(twist_weights, twist_weights[1:]))
    assert twist_weights[0] == pytest.approx(0.0)
    assert twist_weights[-1] == pytest.approx(0.5)


def test_normal_transformation_preserves_unit_length():
    _mesh, rebound = _rebind("pmbam")
    lengths = np.linalg.norm(rebound.normals, axis=1)
    np.testing.assert_allclose(lengths, 1.0, atol=1e-5)


def _parity_metrics(resref: str):
    mesh, rebound = _rebind(resref)
    deviations = np.linalg.norm(rebound.positions - mesh.positions, axis=1) / mesh.bbox_diagonal
    return {
        "mean": float(np.mean(deviations)),
        "p95": float(np.percentile(deviations, 95)),
        "max": float(np.max(deviations)),
    }


def test_bind_pose_parity_pmbam_aligned():
    metrics = _parity_metrics("pmbam")
    assert metrics["mean"] <= 0.01
    assert metrics["p95"] <= 0.05


def test_bind_pose_parity_pfbam_aligned():
    metrics = _parity_metrics("pfbam")
    assert metrics["mean"] <= 0.01
    assert metrics["p95"] <= 0.05


def test_raw_transplant_failure_documented_pmbam():
    mesh, rebound = _rebind("pmbam", options=RebindOptions(enable_skeleton_prealignment=False))
    deviations = np.linalg.norm(rebound.positions - mesh.positions, axis=1) / mesh.bbox_diagonal
    assert float(np.mean(deviations)) > 0.02
