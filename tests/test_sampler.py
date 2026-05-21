import numpy as np

from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
from src.core.retargeting.sampler import (
    StockCorpusResourceManager,
    build_effective_controller_table,
    load_fixture_model,
    resolve_supermodel_chain,
    sample_clip_to_fixed_rate,
)


def _pose_arrays(model, pose, bone_names):
    positions = []
    rotations = []
    scales = []
    node_lookup = {node.name.lower(): node for node in model.all_nodes()}
    for name in bone_names:
        key = name.lower()
        pose_node = pose.nodes.get(key)
        bind_node = node_lookup[key]
        if pose_node is None:
            pos = bind_node.position
            rot = bind_node.rotation
            scale = 1.0
        else:
            pos = pose_node.position
            rot = pose_node.rotation
            scale = pose_node.scale
        positions.append(pos)
        rotations.append((rot[3], rot[0], rot[1], rot[2]))
        scales.append((scale, scale, scale))
    return (
        np.asarray(positions, dtype=np.float32),
        np.asarray(rotations, dtype=np.float32),
        np.asarray(scales, dtype=np.float32),
    )


def test_frame_0_matches_animation_engine_pose():
    manager = StockCorpusResourceManager()
    SuperModelResolver.configure(manager)
    SuperModelResolver.clear_cache()
    model = load_fixture_model("S_Male01")
    engine = AnimationEngine(model)
    assert engine.play("c2d1", loop=False, blend=False)

    sampled = sample_clip_to_fixed_rate("S_Male01", "c2d1", fps=30.0)
    expected_positions, expected_rotations, expected_scales = _pose_arrays(
        model,
        engine.evaluate(0.0),
        sampled.bone_names,
    )

    np.testing.assert_allclose(sampled.positions[0], expected_positions, atol=1e-5)
    np.testing.assert_allclose(sampled.rotations[0], expected_rotations, atol=1e-5)
    np.testing.assert_allclose(sampled.scales[0], expected_scales, atol=1e-5)


def test_supermodel_inheritance_uses_fixture_corpus():
    chain = resolve_supermodel_chain("pmbam", "k1")
    assert chain == ["PMBAM", "S_Female02", "S_Female01", "S_Male02", "S_Male01"]

    table = build_effective_controller_table(chain, "g1a1")
    assert table
    assert {entry.source_model for entry in table.values()} == {"S_Male02"}

    sampled = sample_clip_to_fixed_rate("pmbam", "g1a1", fps=30.0)
    assert sampled.source_chain == chain
    assert sampled.resolved_clip_source == "S_Male02"
    assert sampled.frame_count > 1
    assert sampled.positions.shape[0] == sampled.frame_count
    assert sampled.positions.shape[1] == len(sampled.bone_names)


def test_sampler_uses_g5_palette_path_for_every_frame():
    sampled = sample_clip_to_fixed_rate("pmbam", "walk", fps=30.0)

    assert sampled.bake_math_audit_id == "G5"
    assert sampled.palette_frames == sampled.frame_count
    assert sampled.rotations.shape == (sampled.frame_count, len(sampled.bone_names), 4)
    assert sampled.scales.shape == (sampled.frame_count, len(sampled.bone_names), 3)
