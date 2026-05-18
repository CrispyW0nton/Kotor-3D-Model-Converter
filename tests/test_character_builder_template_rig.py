from __future__ import annotations

import math

from src.core.character_builder import apply_template_rig
from src.core.model_data import BoneWeight, KotorModel, ModelNode, NodeFlags, VertexSkinData


def _node(name: str, flags: int = int(NodeFlags.HEADER), parent: ModelNode | None = None) -> ModelNode:
    node = ModelNode(name=name, flags=flags)
    if parent is not None:
        node.parent = parent
        parent.children.append(node)
    return node


def test_apply_template_rig_strips_imported_armature_and_clears_old_skin() -> None:
    src_root = _node("Bendak_UE")
    src_root.position = (10.0, 0.0, 0.0)
    ue_pelvis = _node("pelvis", parent=src_root)
    ue_pelvis.position = (0.0, 2.0, 0.0)
    ue_spine = _node("spine_01", parent=ue_pelvis)
    mesh = _node(
        "Bendak",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=ue_spine,
    )
    mesh.position = (0.0, 0.0, 3.0)
    mesh.vertices = [(1.0, 0.0, 0.0)]
    mesh.normals = [(0.0, 0.0, 1.0)]
    mesh.faces = [(0, 0, 0)]
    mesh.bone_map = ["pelvis"]
    mesh.bone_map_floats = [0.0]
    mesh.skin_data = [VertexSkinData([BoneWeight(0, 1.0)])]
    mesh.qbone_list = [(0.0, 0.0, 0.0, 1.0)]
    mesh.tbone_list = [(0.0, 0.0, 0.0)]
    mesh.children.append(_node("UE_Mesh_Attachment"))
    mesh.children[-1].parent = mesh
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    _node("rootdummy", parent=kotor_root)
    _node("template_body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=kotor_root)
    template = KotorModel(name="n_mandalorian03", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged = result["model"]
    names = [node.name for node in rigged.all_nodes()]
    assert names[0] == "N_Mandalorian"
    assert "rootdummy" in names
    assert "Bendak" in names
    assert "pelvis" not in names
    assert "spine_01" not in names
    assert "UE_Mesh_Attachment" not in names
    assert "template_body_mesh" not in names

    rigged_mesh = rigged.find_node("Bendak")
    assert rigged_mesh is not None
    assert rigged_mesh.parent is rigged.root_node
    assert rigged_mesh.children == []
    assert rigged_mesh.is_mesh is True
    assert rigged_mesh.is_skin is False
    assert rigged_mesh.bone_map == []
    assert rigged_mesh.skin_data == []
    assert rigged_mesh.qbone_list == []
    assert rigged_mesh.tbone_list == []
    assert rigged_mesh.position == (0.0, 0.0, 0.0)
    assert rigged_mesh.rotation == (0.0, 0.0, 0.0, 1.0)
    assert rigged_mesh.vertices[0] == (11.0, 2.0, 3.0)
    assert "KOTOR skeleton built" in result["message"]
    assert result["removed_import_nodes"] >= 3


def test_apply_template_rig_preserves_adjusted_template_scale_in_manual_mode() -> None:
    src_root = _node("import_root")
    mesh = _node("body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(0.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh_model = KotorModel(name="body", root_node=src_root)

    kotor_root = _node("AdjustedSkeleton")
    hand = _node("rhand", parent=kotor_root)
    hand.position = (1.25, 0.5, 0.75)
    template = KotorModel(name="adjusted", root_node=kotor_root)

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual", scale_factor=1.0)

    assert result["ok"] is True
    rigged_hand = result["model"].find_node("rhand")
    assert rigged_hand is not None
    assert math.isclose(rigged_hand.position[0], 1.25)
    assert math.isclose(rigged_hand.position[1], 0.5)
    assert math.isclose(rigged_hand.position[2], 0.75)
    assert result["scale"] == 1.0
