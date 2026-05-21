import numpy as np

from src.core.retargeting.baker import (
    BakerOptions,
    bake_retargeted_clip,
    compute_bind_offsets,
    max_quat_component_delta,
)
from src.core.retargeting.coordinate_normalizer import CoordinateNormalizer, quat_mul_wxyz
from src.core.retargeting.sampler import load_fixture_model, sample_clip_to_fixed_rate
from src.unreal.animation_retargeting import build_bone_map
from src.unreal.quinn import load_quinn_skeleton_asset, unreal_skeleton_model


def _quinn_model():
    return unreal_skeleton_model(load_quinn_skeleton_asset())


def test_bind_offsets_reconstruct_target_bind_rotations():
    normalizer = CoordinateNormalizer()
    source = load_fixture_model("S_Male01")
    target = _quinn_model()
    source_registry = normalizer.normalize_aurora_bind(source, "kotor_s_male01")
    target_registry = normalizer.normalize_ue5_bind(target, "ue5_quinn")
    report = build_bone_map(source, target)

    offsets = compute_bind_offsets(source_registry, target_registry, report.mapping)

    for source_name, target_name in report.mapping.items():
        reconstructed = quat_mul_wxyz(
            offsets.offset_for(source_name),
            source_registry.world_rotation(source_name),
        )
        delta = max_quat_component_delta(reconstructed, target_registry.world_rotation(target_name))
        assert delta <= 1e-6


def test_identity_retarget_matches_source_clip():
    model = load_fixture_model("S_Male01")
    normalizer = CoordinateNormalizer()
    registry = normalizer.normalize_aurora_bind(model, "kotor_s_male01")
    sampled = sample_clip_to_fixed_rate("S_Male01", "c2d1", fps=30.0)
    identity_map = {name.lower(): name.lower() for name in sampled.bone_names}
    offsets = compute_bind_offsets(registry, registry, identity_map)

    baked = bake_retargeted_clip(sampled, registry, registry, identity_map, offsets)

    np.testing.assert_allclose(baked.positions, sampled.positions, atol=1e-5)
    np.testing.assert_allclose(baked.scales, sampled.scales, atol=1e-5)
    assert max_quat_component_delta(baked.rotations, sampled.rotations) <= 1e-5


def test_g1a1_pmbam_to_quinn_bake_shape_and_sanity():
    normalizer = CoordinateNormalizer()
    source = load_fixture_model("pmbam")
    target = _quinn_model()
    source_registry = normalizer.normalize_aurora_bind(source, "kotor_pmbam")
    target_registry = normalizer.normalize_ue5_bind(target, "ue5_quinn")
    report = build_bone_map(source, target)
    offsets = compute_bind_offsets(source_registry, target_registry, report.mapping)
    sampled = sample_clip_to_fixed_rate("pmbam", "g1a1", fps=30.0)

    baked = bake_retargeted_clip(sampled, source_registry, target_registry, report.mapping, offsets)

    assert baked.frame_count == sampled.frame_count
    assert len(baked.bone_names) == len(target_registry.bone_names)
    assert "pelvis" in {name.lower() for name in baked.bone_names}
    assert "lowerarm_twist_01_l" in {name.lower() for name in baked.bone_names}
    assert np.all(np.isfinite(baked.positions))
    assert np.all(np.isfinite(baked.rotations))
    quat_norms = np.linalg.norm(baked.rotations.astype(np.float64), axis=2)
    np.testing.assert_allclose(quat_norms, 1.0, atol=1e-4)


def test_twist_distribution_derives_unmapped_quinn_twist_bones():
    normalizer = CoordinateNormalizer()
    source = load_fixture_model("pmbam")
    target = _quinn_model()
    source_registry = normalizer.normalize_aurora_bind(source, "kotor_pmbam")
    target_registry = normalizer.normalize_ue5_bind(target, "ue5_quinn")
    report = build_bone_map(source, target)
    offsets = compute_bind_offsets(source_registry, target_registry, report.mapping)
    sampled = sample_clip_to_fixed_rate("pmbam", "g1a1", fps=30.0)

    baked = bake_retargeted_clip(
        sampled,
        source_registry,
        target_registry,
        report.mapping,
        offsets,
        options=BakerOptions(twist_bone_rotation_weight=0.35),
    )

    index = {name.lower(): idx for idx, name in enumerate(baked.bone_names)}
    twist = baked.rotations[:, index["lowerarm_twist_01_l"], :].astype(np.float64)
    bind = target_registry.local_rotation("lowerarm_twist_01_l")
    deltas = np.asarray([max_quat_component_delta(row, bind) for row in twist])
    assert float(np.max(deltas)) > 1e-5
