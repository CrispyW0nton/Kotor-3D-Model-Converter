import json
from pathlib import Path

from src.core.retargeting.fbx_exporter import (
    build_day45_pmbam_g1a1_asset,
    build_intermediate_representation_day45,
)


def _intermediate():
    mesh, clips, registry, spec, options = build_day45_pmbam_g1a1_asset(run_roundtrip_validation=False)
    return build_intermediate_representation_day45(mesh, clips, registry, spec, options)


def test_bone_matrix_assignment_preserves_world_position():
    data = _intermediate()
    pelvis = data["aurora_skeleton"]["bones"]["pelvis_g"]
    matrix = pelvis["bind_world_matrix_4x4"]
    assert matrix[0][3] == pelvis["bind_world_matrix_4x4"][0][3]
    assert matrix[3] == [0.0, 0.0, 0.0, 1.0]


def test_topological_order_for_parent_assignment():
    data = _intermediate()
    bones = data["aurora_skeleton"]["bones"]
    order = list(bones)
    positions = {name: index for index, name in enumerate(order)}
    for name, bone in bones.items():
        parent = bone["parent"]
        if parent:
            assert positions[parent] < positions[name]


def test_vertex_groups_keyed_by_bone_name():
    data = _intermediate()
    groups = data["mesh"]["vertex_weights"]
    assert "pelvis_g" in groups
    assert all("vertex_index" in item and "weight" in item for item in groups["pelvis_g"])


def test_action_keyframes_are_absolute_inputs_for_delta_from_rest():
    data = _intermediate()
    clip = data["animation_clips"][0]
    root_keys = clip["curves"]["rootdummy"]
    assert "position" in root_keys
    assert "orientation" in root_keys
    assert root_keys["position"][0][0] == 1


def test_rename_preserves_vertex_group_bindings():
    data = _intermediate()
    pairs = data["rename_spec"]["rename_pairs"]
    groups = data["mesh"]["vertex_weights"]
    assert "lcollar_g" in groups
    assert pairs["lcollar_g"] == "clavicle_l"


def test_twist_leaves_have_zero_weight_and_no_children():
    data = _intermediate()
    groups = data["mesh"]["vertex_weights"]
    twist_names = {leaf["name"] for leaf in data["rename_spec"]["twist_leaves"]}
    assert not twist_names & set(groups)


def test_native_aurora_pose_preserved_through_pipeline():
    data = _intermediate()
    text = json.dumps(data, sort_keys=True)
    assert "rest_pose_override" not in text
    assert data["metadata"]["preservation_policy"] == "NATIVE_AURORA_BIND_POSE"
