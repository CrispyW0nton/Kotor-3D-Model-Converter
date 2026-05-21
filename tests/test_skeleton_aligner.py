import numpy as np
import pytest

from src.core.retargeting.coordinate_normalizer import BindPoseRegistry, CoordinateNormalizer
from src.core.retargeting.sampler import load_fixture_model
from src.core.retargeting.skeleton_aligner import (
    AlignmentDriftExceeded,
    AlignmentOptions,
    align_target_skeleton_to_source,
    compute_global_scale,
    topological_sort,
)
from src.unreal.animation_retargeting import build_bone_map
from src.unreal.quinn import load_quinn_skeleton_asset, unreal_skeleton_model


def _setup(resref: str = "pmbam"):
    normalizer = CoordinateNormalizer()
    source_model = load_fixture_model(resref)
    target_model = unreal_skeleton_model(load_quinn_skeleton_asset())
    source_registry = normalizer.normalize_aurora_bind(source_model, f"kotor_{resref}")
    target_registry = normalizer.normalize_ue5_bind(target_model, "ue5_quinn")
    mapping = build_bone_map(source_model, target_model).mapping
    aligned = align_target_skeleton_to_source(
        f"kotor_{resref}",
        "ue5_quinn",
        mapping,
        target_registry,
        AlignmentOptions(),
        source_registry=source_registry,
        target_registry=target_registry,
    )
    return source_registry, target_registry, mapping, aligned


def test_topological_sort_acyclic():
    _source, target, _mapping, _aligned = _setup()
    hierarchy = {name.lower(): target.parents.get(name.lower()) or None for name in target.bone_names}
    order = topological_sort(hierarchy)
    assert order[0] == "skm_quinn_simple"
    assert order.index("root") < order.index("pelvis")
    assert order.index("pelvis") < order.index("spine_01")


def test_mapped_bone_position_parity():
    source, _target, _mapping, aligned = _setup()
    for target_name, delta in aligned.alignment_metadata.per_bone_deltas.items():
        if delta.source_mapped_from is None:
            continue
        src_pos = source.world_position(delta.source_mapped_from)
        aligned_pos = aligned.bind_world[target_name].copy()[:3, 3]
        np.testing.assert_allclose(aligned_pos, src_pos, atol=1e-6)


def test_unmapped_bone_preserves_local_offset():
    _source, target, _mapping, aligned = _setup()
    bone = "neck_01"
    parent = aligned.bone_parents[bone]
    raw_local = np.linalg.inv(target.world_matrix(parent)) @ target.world_matrix(bone)
    aligned_local = np.linalg.inv(aligned.bind_world[parent]) @ aligned.bind_world[bone]
    np.testing.assert_allclose(aligned_local, raw_local, atol=1e-6)


def test_twist_bone_segment_interpolation():
    _source, _target, _mapping, aligned = _setup()
    twist = "upperarm_twist_01_l"
    parent = "upperarm_l"
    child = "lowerarm_l"
    t = 0.333333
    expected = aligned.bind_world[parent][:3, 3] * (1.0 - t) + aligned.bind_world[child][:3, 3] * t
    np.testing.assert_allclose(aligned.bind_world[twist][:3, 3], expected, atol=1e-6)


def test_alignment_validation_catches_drift():
    source_model = load_fixture_model("pmbam")
    target_model = unreal_skeleton_model(load_quinn_skeleton_asset())
    normalizer = CoordinateNormalizer()
    source_registry = normalizer.normalize_aurora_bind(source_model, "kotor_pmbam")
    target_registry = normalizer.normalize_ue5_bind(target_model, "ue5_quinn")
    mapping = build_bone_map(source_model, target_model).mapping

    with pytest.raises(AlignmentDriftExceeded):
        align_target_skeleton_to_source(
            "kotor_pmbam",
            "ue5_quinn",
            mapping,
            target_registry,
            AlignmentOptions(max_mapped_bone_drift=-1e-6),
            source_registry=source_registry,
            target_registry=target_registry,
        )


def test_raw_snapshot_captured_for_audit():
    _source, _target, _mapping, aligned = _setup()
    assert aligned.alignment_metadata.raw_target_snapshot is not None
    assert "pelvis" in aligned.alignment_metadata.raw_target_snapshot


def test_aligned_bind_matrices_non_degenerate():
    _source, _target, _mapping, aligned = _setup()
    dets = [abs(float(np.linalg.det(matrix[:3, :3]))) for matrix in aligned.bind_world.values()]
    assert min(dets) > 1e-6


def test_global_scale_pelvis_to_head_correctness():
    source, target, mapping, _aligned = _setup()
    scale = compute_global_scale(
        source.bind_world,
        target.bind_world,
        mapping,
        "pelvis_to_head",
        None,
    )
    assert 0.1 < scale < 2.0
    assert scale == pytest.approx(_aligned.alignment_metadata.global_scale_factor)
