from __future__ import annotations

from types import SimpleNamespace

from src.core.characters.native_skeleton import (
    build_native_skeleton_structural_diff,
    capture_native_skeleton_snapshot,
    classify_native_socket_name,
    find_snapshot_node,
    native_skeleton_fingerprint,
    snapshot_node_paths,
)
from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags


def _node(
    name: str,
    *,
    parent: ModelNode | None = None,
    flags: int = int(NodeFlags.HEADER),
) -> ModelNode:
    node = ModelNode(name=name, flags=flags)
    if parent is not None:
        node.parent = parent
        parent.children.append(node)
    return node


def test_native_socket_classifier_accepts_kotor_hand_variants() -> None:
    assert classify_native_socket_name("rhand") == "right_hand"
    assert classify_native_socket_name("Rhand_g") == "right_hand"
    assert classify_native_socket_name("lhand") == "left_hand"
    assert classify_native_socket_name("Lhand_g") == "left_hand"


def test_native_skeleton_snapshot_captures_exact_dag_facts() -> None:
    root = _node("PMBAM")
    root.position = (1.0, 2.0, 3.0)
    root.rotation = (0.0, 0.0, 0.707, 0.707)
    pelvis = _node("pelvis_g", parent=root, flags=int(NodeFlags.HEADER | NodeFlags.MESH))
    pelvis.vertices = [(0.0, 0.0, 0.0)]
    pelvis.faces = [(0, 0, 0)]
    headhook = _node("headhook", parent=pelvis)
    lhand = _node("Lhand_g", parent=pelvis, flags=int(NodeFlags.HEADER | NodeFlags.MESH))
    skin = _node(
        "Torso",
        parent=root,
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
    )
    skin.vertices = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]
    skin.faces = [(0, 1, 2)]
    skin.texture = "PMBAM01"

    model = KotorModel(name="pmbam", root_node=root, supermodel="S_Male02")
    model.model_type = 4
    model.classification = "CHARACTER"
    model.animations = [SimpleNamespace(name="walk")]
    model._gr_source_resref = "pmbam"
    model._gr_source_game = "K1"
    model._gr_source_layer = "game_library"

    snapshot = capture_native_skeleton_snapshot(model, game="K1")

    assert snapshot.model_name == "pmbam"
    assert snapshot.game == "K1"
    assert snapshot.supermodel == "S_Male02"
    assert snapshot.node_count == 5
    assert snapshot.mesh_node_count == 3
    assert snapshot.skin_node_count == 1
    assert snapshot.hook_names == ("headhook", "Lhand_g")
    assert snapshot.metadata["source_resref"] == "pmbam"
    assert snapshot.metadata["animation_count"] == 1
    assert snapshot.metadata["socket_categories"]["head"] == ("headhook",)
    assert snapshot.metadata["socket_categories"]["left_hand"] == ("Lhand_g",)

    paths = snapshot_node_paths(snapshot)
    assert paths["Lhand_g"] == ("PMBAM", "pelvis_g", "Lhand_g")
    pelvis_snapshot = find_snapshot_node(snapshot, "pelvis_g")
    assert pelvis_snapshot is not None
    assert pelvis_snapshot.flags == int(NodeFlags.HEADER | NodeFlags.MESH)
    assert pelvis_snapshot.position == (0.0, 0.0, 0.0)
    assert pelvis_snapshot.is_mesh is True
    assert pelvis_snapshot.has_geometry is True
    assert pelvis_snapshot.export_role == "deform_helper"

    skin_snapshot = find_snapshot_node(snapshot, "Torso")
    assert skin_snapshot is not None
    assert skin_snapshot.is_skin is True
    assert skin_snapshot.vertex_count == 3
    assert skin_snapshot.face_count == 1
    assert skin_snapshot.texture == "PMBAM01"
    assert len(native_skeleton_fingerprint(snapshot)) == 64


def test_native_skeleton_snapshot_round_trips_json_friendly_contract() -> None:
    root = _node("N_Mandalorian")
    _node("rhand", parent=root)
    model = KotorModel(name="n_mandalorian", root_node=root, supermodel="NULL")

    snapshot = capture_native_skeleton_snapshot(model, game="K1")
    restored = type(snapshot).from_dict(snapshot.to_dict())

    assert restored == snapshot
    assert restored.node_names() == ("N_Mandalorian", "rhand")
    assert native_skeleton_fingerprint(restored) == native_skeleton_fingerprint(snapshot)


def test_native_skeleton_structural_diff_reports_binding_changes() -> None:
    root = _node("PMBAM")
    pelvis = _node("pelvis_g", parent=root)
    headhook = _node("headhook", parent=pelvis)
    _node("Torso", flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN), parent=root)
    model = KotorModel(name="pmbam", root_node=root, supermodel="S_Male02")
    snapshot = capture_native_skeleton_snapshot(model, game="K1")

    pelvis.position = (0.0, 0.0, 1.25)
    pelvis.children.remove(headhook)
    payload = _node(
        "BendakPayload",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
    )
    payload.vertices = [(0.0, 0.0, 0.0), (0.0, 0.5, 0.0)]
    payload.faces = [(0, 1, 1)]
    payload.bone_map = ["pelvis_g"]
    payload.skin_data = [SimpleNamespace(), SimpleNamespace()]

    diff = build_native_skeleton_structural_diff(
        snapshot,
        model,
        payload_mesh_names=("BendakPayload",),
    )

    assert diff["schema"] == "ghostrigger.native_skeleton_structural_diff.v1"
    assert diff["summary"]["missing_hook_count"] == 1
    assert diff["missing_hooks"] == [
        {
            "name": "headhook",
            "path": ["PMBAM", "pelvis_g", "headhook"],
            "socket_category": "head",
        }
    ]
    assert any(item["name"] == "BendakPayload" for item in diff["added_nodes"])
    assert diff["changed_transforms"][0]["name"] == "pelvis_g"
    payload_rows = [
        item for item in diff["skin_row_counts"]
        if item["name"] == "BendakPayload"
    ]
    assert payload_rows == [
        {
            "name": "BendakPayload",
            "path": ["PMBAM", "BendakPayload"],
            "payload_mesh": True,
            "vertices": 2,
            "skin_rows": 2,
            "bone_map_count": 1,
        }
    ]
