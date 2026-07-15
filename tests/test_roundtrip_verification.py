"""Tests for Sprint 3.5 Phase 3.A round-trip verification helpers."""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_verify_roundtrip_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_roundtrip.py"
    spec = importlib.util.spec_from_file_location("verify_roundtrip", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_level_1_reports_byte_differences(tmp_path):
    verify = _load_verify_roundtrip_module()
    input_mdl = tmp_path / "a.mdl"
    output_mdl = tmp_path / "b.mdl"
    input_mdl.write_bytes(b"abcd")
    output_mdl.write_bytes(b"abxd")

    result = verify.run_level_1(input_mdl, output_mdl)

    assert result.pass_ is False
    assert result.files[0].diff_byte_count == 1
    assert result.files[0].first_diff_offset == 2


def test_orientation_controller_comparison_accepts_quaternion_sign_equivalence():
    verify = _load_verify_roundtrip_module()
    input_ctrl = {
        "type": 20,
        "name": "orientation",
        "columns": 4,
        "times": [0.0],
        "values": [(0.0, 0.0, 0.0, 1.0)],
    }
    output_ctrl = {
        "type": 20,
        "name": "orientation",
        "columns": 4,
        "times": [0.0],
        "values": [(-0.0, -0.0, -0.0, -1.0)],
    }

    compared, max_time, max_value, sign_equiv, failures = verify._compare_controller_lists(
        "head",
        [input_ctrl],
        [output_ctrl],
        1e-5,
    )

    assert compared == 1
    assert max_time == 0.0
    assert max_value == 0.0
    assert sign_equiv == 1
    assert failures == []


def test_animation_compare_allows_controllerless_ancestor_stubs():
    verify = _load_verify_roundtrip_module()
    input_node = SimpleNamespace(
        name="head",
        controllers=[
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [(1.0, 2.0, 3.0)],
            }
        ],
    )
    output_stub = SimpleNamespace(name="torso", controllers=[])
    output_node = SimpleNamespace(
        name="head",
        controllers=[
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [(1.0, 2.0, 3.0)],
            }
        ],
    )
    input_anim = SimpleNamespace(name="talk", length=1.0, transition_time=0.25, nodes=[input_node])
    output_anim = SimpleNamespace(name="talk", length=1.0, transition_time=0.25, nodes=[output_stub, output_node])

    result = verify._compare_animation(input_anim, output_anim, 1e-5)

    assert result.pass_ is True
    assert result.compared_controller_count == 1
    assert result.failures == []


def test_overall_pass_treats_level_1_as_bonus():
    verify = _load_verify_roundtrip_module()
    full = verify.RoundTripFullResult(
        input_path="a.mdl",
        output_path="b.mdl",
        animation_name="victory",
        level_1=verify.RoundTripLevel1Result(pass_=False),
        level_2=verify.RoundTripLevel2Result(
            pass_=True,
            node_count_match=True,
            animation_count_match=True,
            requested_animation="victory",
            requested_animation_available=False,
            input_animation_count=0,
            output_animation_count=0,
        ),
    )

    passed, summary = verify.determine_overall_pass(full)

    assert passed is True
    assert "byte identity" in summary


def test_animation_hierarchy_does_not_cycle_when_anim_root_is_descendant():
    from src.core.mdl.mdl_writer import MDLBinaryWriter
    from src.core.geometry.model_data import Animation, ModelNode

    root = ModelNode(name="S_Male02")
    head = ModelNode(name="head_g", parent=root)
    talkdummy = ModelNode(name="talkdummy", parent=head)
    jaw = ModelNode(
        name="f_jaw_g",
        parent=talkdummy,
        controllers=[{"type": 20, "name": "orientation", "columns": 4, "times": [0.0], "values": [(0, 0, 0, 1)]}],
    )
    root.children = [head]
    head.children = [talkdummy]
    talkdummy.children = [jaw]
    anim = Animation(name="talk", anim_root="talkdummy", nodes=[root, head, talkdummy, jaw])

    nodes = MDLBinaryWriter()._animation_nodes_with_hierarchy(anim, [root, head, talkdummy, jaw])

    assert nodes[0].name == "S_Male02"
    by_name = {node.name: node for node in nodes}
    assert by_name["talkdummy"].parent.name == "head_g"
    assert by_name["f_jaw_g"].parent.name == "talkdummy"


def test_mdl_writer_sets_engine_maxtree_subtype_bytes():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="pmbam")
    anim_node = ModelNode(
        name="pmbam",
        controllers=[
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [(0.0, 0.0, 0.0, 1.0)],
            }
        ],
    )
    model = KotorModel(
        name="pmbam",
        root_node=root,
        animations=[Animation(name="victory", length=0.0, anim_root="pmbam", nodes=[anim_node])],
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    assert mdl_bytes[base + 0x4C] == 0x02

    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 80 + 8)[0]
    anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel)[0]
    assert mdl_bytes[base + anim_rel + 0x4C] == 0x05


def test_mdl_writer_places_animations_before_static_tree_for_kotor2_loader():
    from src.core.geometry.model_data import Animation, GameVersion, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="c_drexlf")
    anim_node = ModelNode(
        name="c_drexlf",
        controllers=[
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [(0.0, 0.0, 0.0)],
            }
        ],
    )
    model = KotorModel(
        name="c_drexlf",
        root_node=root,
        animations=[Animation(name="pause1", length=0.0, anim_root="c_drexlf", nodes=[anim_node])],
        game_version=GameVersion.K2,
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    root_rel = struct.unpack_from("<I", mdl_bytes, base + 0x28)[0]
    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 80 + 8)[0]
    first_anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel)[0]
    anim_root_rel = struct.unpack_from("<I", mdl_bytes, base + first_anim_rel + 0x28)[0]

    assert anim_table_rel < root_rel
    assert first_anim_rel < root_rel
    assert mdl_bytes[base + first_anim_rel + 0x84:base + first_anim_rel + 0x88] == b"\0" * 4
    assert anim_root_rel - first_anim_rel == 0x88
    # The on-disk +8 field has different contracts for the two MaxTree kinds:
    # static nodes are runtime-null, animation nodes point to their animation
    # geometry block so K2's relocation dispatcher can fix child arrays.
    assert struct.unpack_from("<I", mdl_bytes, base + root_rel + 0x08)[0] == 0
    assert struct.unpack_from("<I", mdl_bytes, base + anim_root_rel + 0x08)[0] == first_anim_rel


def test_mdl_writer_keeps_animation_runtime_base_slot_clear_of_events_and_root():
    from src.core.geometry.model_data import AnimEvent, Animation, GameVersion, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="c_rancor")
    animations = []
    for event_count in range(3):
        animations.append(
            Animation(
                name=f"probe{event_count}",
                length=1.0,
                anim_root="c_rancor",
                nodes=[ModelNode(name="c_rancor")],
                events=[
                    AnimEvent(time=float(index) * 0.25, name=f"event{index}")
                    for index in range(event_count)
                ],
            )
        )
    model = KotorModel(
        name="c_rancor",
        root_node=root,
        animations=animations,
        game_version=GameVersion.K2,
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0x58)[0]
    for index, expected_event_count in enumerate(range(3)):
        anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel + index * 4)[0]
        anim_abs = base + anim_rel
        event_array_rel = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x78)[0]
        event_count = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x7C)[0]
        root_rel = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x28)[0]

        assert event_count == expected_event_count
        assert mdl_bytes[anim_abs + 0x84:anim_abs + 0x88] == b"\0" * 4
        assert root_rel - anim_rel == 0x88 + expected_event_count * 0x24
        if expected_event_count:
            assert event_array_rel == anim_rel + 0x88
        else:
            assert event_array_rel == 0
        assert struct.unpack_from("<I", mdl_bytes, base + root_rel + 0x08)[0] == anim_rel


def test_mdl_writer_converts_import_space_uvs_to_game_mdx_orientation():
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(
        name="uv_mesh",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0)],
        uvs=[(0.25, 0.20)],
        uvs_lm=[(0.75, 0.30)],
    )
    root.uv_v_flip = False
    model = KotorModel(name="uv_mesh", root_node=root, animations=[])

    _mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    u0, v0 = struct.unpack_from("<ff", mdx_bytes, 12)
    u1, v1 = struct.unpack_from("<ff", mdx_bytes, 20)

    assert abs(u0 - 0.25) < 1.0e-6
    assert abs(v0 - 0.80) < 1.0e-6
    assert abs(u1 - 0.75) < 1.0e-6
    assert abs(v1 - 0.70) < 1.0e-6


def test_mdl_writer_emits_full_engine_model_header_fields():
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(
        name="pmbam",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
    )
    model = KotorModel(name="pmbam", root_node=root, animations=[])

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    base = 12

    root_off = struct.unpack_from("<I", mdl_bytes, base + 0x28)[0]
    assert struct.unpack_from("<I", mdl_bytes, base + 0xA8)[0] == root_off
    assert struct.unpack_from("<I", mdl_bytes, base + 0xAC)[0] == 0
    assert struct.unpack_from("<I", mdl_bytes, base + 0xB0)[0] == len(mdx_bytes)
    assert struct.unpack_from("<I", mdl_bytes, base + 0xB4)[0] == 0
    assert struct.unpack_from("<I", mdl_bytes, base + 0xB8)[0] == 0xC4
    assert struct.unpack_from("<I", mdl_bytes, base + 0xBC)[0] == 1
    assert struct.unpack_from("<I", mdl_bytes, base + 0xC0)[0] == 1


def test_mdl_writer_preserves_header_bit_for_mesh_nodes():
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="root")
    mesh = ModelNode(
        name="helper_mesh",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
    )
    root.children = [mesh]
    model = KotorModel(name="meshflag", root_node=root, animations=[])

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    root_rel = struct.unpack_from("<I", mdl_bytes, base + 0x28)[0]
    child_arr_rel = struct.unpack_from("<I", mdl_bytes, base + root_rel + 0x2C)[0]
    mesh_rel = struct.unpack_from("<I", mdl_bytes, base + child_arr_rel)[0]

    assert struct.unpack_from("<H", mdl_bytes, base + mesh_rel)[0] == int(
        NodeFlags.HEADER | NodeFlags.MESH
    )


def test_mdl_writer_emits_engine_render_batch_arrays_for_mesh_nodes():
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.mdl.ghostrigger_mdl_reader import GhostRiggerMDLBinaryReader
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="render_batch_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH))
    root.vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    root.normals = [(0.0, 0.0, 1.0)] * 4
    root.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    root.faces = [(0, 1, 2), (0, 2, 3)]
    model = KotorModel(name="render_batch_mesh", root_node=root, animations=[])

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    reader = GhostRiggerMDLBinaryReader(mdl_bytes, 0, len(mdl_bytes), mdx_bytes, 0, len(mdx_bytes))
    reader.load()
    mesh_header = next(
        bin_node.trimesh
        for bin_node in reader._gr_bin_nodes.values()
        if getattr(bin_node, "trimesh", None) is not None
    )

    assert mesh_header.indices_counts == [6]
    assert mesh_header.indices_offsets_count == 1
    assert mesh_header.counters_count == 1
    assert mesh_header.inverted_counters == [98]

    index_abs = 12 + mesh_header.indices_offsets[0]
    assert struct.unpack_from("<6H", mdl_bytes, index_abs) == (0, 1, 2, 0, 2, 3)


def test_mdl_writer_emits_full_k2_tangent_space_for_generated_render_skin():
    from src.core.geometry.model_data import (
        BoneWeight,
        GameVersion,
        KotorModel,
        ModelNode,
        NodeFlags,
        VertexSkinData,
    )
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(
        name="rancor_skin",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=["rancor_skin"],
        skin_data=[
            VertexSkinData(influences=[BoneWeight(bone_index=0, weight=1.0)])
            for _ in range(3)
        ],
        render=True,
    )
    model = KotorModel(
        name="rancor_skin",
        game_version=GameVersion.K2,
        root_node=root,
        animations=[],
    )

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    root_rel = struct.unpack_from("<I", mdl_bytes, base + 0x28)[0]
    mesh_abs = base + root_rel + 80

    assert struct.unpack_from("<I", mdl_bytes, mesh_abs + 252)[0] == 100
    assert struct.unpack_from("<I", mdl_bytes, mesh_abs + 256)[0] == 0xA3
    channel_offsets = struct.unpack_from("<11I", mdl_bytes, mesh_abs + 260)
    assert channel_offsets == (
        0,
        12,
        0xFFFFFFFF,
        24,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0xFFFFFFFF,
        32,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0xFFFFFFFF,
    )

    skin_abs = mesh_abs + 340
    assert struct.unpack_from("<I", mdl_bytes, skin_abs + 12)[0] == 68
    assert struct.unpack_from("<I", mdl_bytes, skin_abs + 16)[0] == 84

    row0 = struct.unpack_from("<25f", mdx_bytes, 0)
    assert row0[8:11] == (0.0, 1.0, 0.0)   # bitangent
    assert row0[11:14] == (-1.0, 0.0, 0.0)  # tangent
    assert row0[14:17] == (0.0, 0.0, 1.0)  # tangent-space normal
    assert row0[17:21] == (1.0, 0.0, 0.0, 0.0)
    assert row0[21:25] == (0.0, -1.0, -1.0, -1.0)

    # The trailing sentinel is one complete 100-byte row; tangent bytes stay
    # zero while the first skin weight remains the engine's one-row-past guard.
    assert len(mdx_bytes) == 4 * 100
    sentinel = struct.unpack_from("<25f", mdx_bytes, 3 * 100)
    assert sentinel[8:17] == (0.0,) * 9
    assert sentinel[17:21] == (1.0, 0.0, 0.0, 0.0)


def test_mdl_writer_keeps_nonrender_and_explicit_no_tangent_skins_compact():
    from src.core.geometry.model_data import BoneWeight, ModelNode, NodeFlags, VertexSkinData
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    def skin_node(*, render: bool, source_tangent_space=None):
        node = ModelNode(
            name="compact_skin",
            flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
            vertices=[(0.0, 0.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)],
            uvs=[(0.0, 0.0)],
            skin_data=[VertexSkinData(influences=[BoneWeight(0, 1.0)])],
            render=render,
        )
        if source_tangent_space is not None:
            node.mdx_tangent_space = source_tangent_space
        return node

    writer = MDLBinaryWriter()
    for node in (
        skin_node(render=False),
        skin_node(render=True, source_tangent_space=False),
    ):
        stride, offsets = writer._mdx_stride_for(node)
        assert stride == 64
        assert offsets["tan"] == 0xFFFFFFFF
        assert offsets["sw"] == 32
        assert offsets["br"] == 48

    # A source file can explicitly carry tangent space without a UV channel.
    # Preserve that on-disk format and synthesize a stable fallback basis.
    source_tangent = ModelNode(
        name="source_tangent",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)],
        render=False,
    )
    source_tangent.mdx_tangent_space = True
    stride, offsets = writer._mdx_stride_for(source_tangent)
    assert stride == 60
    assert offsets["tan"] == 24


def test_mdl_writer_exports_full_target_hierarchy_for_sparse_animation_tree():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="pmbam")
    pelvis = ModelNode(name="pelvis_g", parent=root)
    helper = ModelNode(name="headhook", parent=root)
    upperarm = ModelNode(name="lupperarm_g", parent=pelvis)
    hand = ModelNode(name="lhand_g", parent=upperarm)
    leg = ModelNode(name="lthigh_g", parent=pelvis)
    root.children = [pelvis, helper]
    pelvis.children = [upperarm, leg]
    upperarm.children = [hand]

    keyed_hand = ModelNode(
        name="lhand_g",
        controllers=[
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [(0.0, 0.0, 0.0, 1.0)],
            }
        ],
    )
    model = KotorModel(
        name="pmbam",
        root_node=root,
        animations=[Animation(name="victory", length=0.0, anim_root="pmbam", nodes=[keyed_hand])],
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12

    name_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0xB8)[0]
    name_count = struct.unpack_from("<I", mdl_bytes, base + 0xBC)[0]
    names = []
    for index in range(name_count):
        string_rel = struct.unpack_from("<I", mdl_bytes, base + name_table_rel + index * 4)[0]
        string_abs = base + string_rel
        end = mdl_bytes.index(b"\0", string_abs)
        names.append(mdl_bytes[string_abs:end].decode("ascii"))

    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0x58)[0]
    anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel)[0]
    anim_abs = base + anim_rel
    root_rel = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x28)[0]
    node_count = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x2C)[0]
    assert node_count == 6

    visited_offsets: set[int] = set()
    visited_names: list[str] = []

    def walk(node_rel: int) -> None:
        node_abs = base + node_rel
        assert node_rel != 0
        assert node_abs not in visited_offsets
        visited_offsets.add(node_abs)
        assert struct.unpack_from("<I", mdl_bytes, node_abs + 0x08)[0] == anim_rel
        name_index = struct.unpack_from("<H", mdl_bytes, node_abs + 0x04)[0]
        visited_names.append(names[name_index])
        child_array_rel = struct.unpack_from("<I", mdl_bytes, node_abs + 0x2C)[0]
        child_count = struct.unpack_from("<I", mdl_bytes, node_abs + 0x30)[0]
        child_count2 = struct.unpack_from("<I", mdl_bytes, node_abs + 0x34)[0]
        assert child_count == child_count2
        for child_index in range(child_count):
            child_rel = struct.unpack_from("<I", mdl_bytes, base + child_array_rel + child_index * 4)[0]
            assert child_rel != 0
            assert child_rel != node_rel
            walk(child_rel)

    walk(root_rel)

    assert visited_names == ["pmbam", "pelvis_g", "lupperarm_g", "lhand_g", "lthigh_g", "headhook"]
    assert len(visited_offsets) == node_count


def test_mdl_writer_rebuilds_donor_parent_edges_on_target_hierarchy():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="C_Ithorian")
    torso = ModelNode(name="torsoUpr_g", parent=root)
    shoulder = ModelNode(name="RShoulder_g", parent=torso)
    bicep = ModelNode(name="rbicep_g", parent=shoulder)
    neck_base = ModelNode(name="NeckBase_g", parent=torso)
    neck_upper = ModelNode(name="NeckUpr03_g", parent=neck_base)
    neck = ModelNode(name="Neck_g", parent=neck_upper)
    head = ModelNode(name="Head_g", parent=neck)
    unrelated_helper = ModelNode(name="headhook", parent=root)
    root.children = [torso, unrelated_helper]
    torso.children = [shoulder, neck_base]
    shoulder.children = [bicep]
    neck_base.children = [neck_upper]
    neck_upper.children = [neck]
    neck.children = [head]

    donor_root = ModelNode(name="C_Ithorian")
    donor_torso = ModelNode(name="torsoUpr_g", parent=donor_root)
    donor_bicep = ModelNode(
        name="rbicep_g",
        parent=donor_torso,
        controllers=[{
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [(0.0, 0.0, 0.0, 1.0)],
        }],
    )
    donor_neck = ModelNode(name="Neck_g", parent=donor_torso)
    donor_head = ModelNode(name="Head_g", parent=donor_neck)
    donor_root.children = [donor_torso]
    donor_torso.children = [donor_bicep, donor_neck]
    donor_neck.children = [donor_head]
    animation = Animation(
        name="c2a1",
        length=1.0,
        anim_root="C_Ithorian",
        nodes=[donor_root, donor_torso, donor_bicep, donor_neck, donor_head],
    )
    model = KotorModel(name="c_ithlord", root_node=root, animations=[animation])
    writer = MDLBinaryWriter()
    writer._nodes = list(model.all_nodes())

    nodes = writer._animation_nodes_with_hierarchy(animation, writer._nodes)
    by_name = {node.name: node for node in nodes}

    assert [node.name for node in nodes] == [
        "C_Ithorian", "torsoUpr_g", "RShoulder_g", "rbicep_g",
        "NeckBase_g", "NeckUpr03_g", "Neck_g", "Head_g",
    ]
    assert by_name["rbicep_g"].parent is by_name["RShoulder_g"]
    assert by_name["Neck_g"].parent is by_name["NeckUpr03_g"]
    assert by_name["Head_g"].parent is by_name["Neck_g"]
    assert "headhook" not in by_name
    assert by_name["RShoulder_g"].controllers == []
    assert by_name["NeckBase_g"].controllers == []
    assert any(
        int(controller.get("type", 0)) == 20
        for controller in by_name["rbicep_g"].controllers
    )

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes)
    assert reloaded is not None
    reloaded_animation = next(
        anim for anim in reloaded.animations
        if str(anim.name or "").lower() == "c2a1"
    )
    reloaded_by_name = {
        str(node.name or ""): node
        for node in reloaded_animation.nodes
    }
    assert reloaded_by_name["rbicep_g"].parent is reloaded_by_name["RShoulder_g"]
    assert reloaded_by_name["Neck_g"].parent is reloaded_by_name["NeckUpr03_g"]
    assert reloaded_by_name["Head_g"].parent is reloaded_by_name["Neck_g"]


def test_mdl_writer_repairs_donor_edges_when_target_names_are_duplicated():
    from src.core.geometry.model_data import Animation, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="root", index=0)
    torso = ModelNode(name="torso", index=1, parent=root)
    shoulder = ModelNode(name="shoulder", index=2, parent=torso)
    arm = ModelNode(name="arm", index=3, parent=shoulder)
    duplicate_a = ModelNode(name="duplicate", index=4, parent=root)
    duplicate_b = ModelNode(name="duplicate", index=5, parent=root)
    root.children = [torso, duplicate_a, duplicate_b]
    torso.children = [shoulder]
    shoulder.children = [arm]

    donor_root = ModelNode(name="root", index=0)
    donor_torso = ModelNode(name="torso", index=1, parent=donor_root)
    donor_arm = ModelNode(name="arm", index=3, parent=donor_torso)
    donor_root.children = [donor_torso]
    donor_torso.children = [donor_arm]
    animation = Animation(
        name="attack",
        length=1.0,
        anim_root="root",
        nodes=[donor_root, donor_torso, donor_arm],
    )
    target_nodes = [root, torso, shoulder, arm, duplicate_a, duplicate_b]

    writer = MDLBinaryWriter()
    rebuilt = writer._animation_nodes_with_hierarchy(animation, target_nodes)
    by_index = {int(node.index): node for node in rebuilt}

    assert sorted(by_index) == [0, 1, 2, 3]
    assert by_index[3].parent is by_index[2]
    writer._validate_animation_export_tree(
        animation,
        rebuilt,
        target_nodes,
        allow_source_subset=True,
    )


def test_mdl_writer_preserves_existing_sparse_donor_animation_tree():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="C_DrexlF")
    render_mesh = ModelNode(name="tailGeo", parent=root)
    cutscene = ModelNode(name="cutscenedummy", parent=root)
    rootdummy = ModelNode(name="rootdummy", parent=cutscene)
    pelvis = ModelNode(name="pelvis_g", parent=rootdummy)
    root.children = [render_mesh, cutscene]
    cutscene.children = [rootdummy]
    rootdummy.children = [pelvis]

    anim_root = ModelNode(name="C_DrexlF")
    anim_cutscene = ModelNode(name="cutscenedummy", parent=anim_root)
    anim_rootdummy = ModelNode(name="rootdummy", parent=anim_cutscene)
    anim_pelvis = ModelNode(
        name="pelvis_g",
        parent=anim_rootdummy,
        controllers=[
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [(0.0, 0.0, 0.0, 1.0)],
            }
        ],
    )
    anim_root.children = [anim_cutscene]
    anim_cutscene.children = [anim_rootdummy]
    anim_rootdummy.children = [anim_pelvis]

    model = KotorModel(
        name="C_DrexlF",
        root_node=root,
        animations=[
            Animation(
                name="cwalk",
                length=1.0,
                anim_root="C_DrexlF",
                nodes=[anim_root, anim_cutscene, anim_rootdummy, anim_pelvis],
            )
        ],
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    name_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0xB8)[0]
    name_count = struct.unpack_from("<I", mdl_bytes, base + 0xBC)[0]
    names = []
    for index in range(name_count):
        string_rel = struct.unpack_from("<I", mdl_bytes, base + name_table_rel + index * 4)[0]
        string_abs = base + string_rel
        end = mdl_bytes.index(b"\0", string_abs)
        names.append(mdl_bytes[string_abs:end].decode("ascii"))

    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0x58)[0]
    anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel)[0]
    anim_abs = base + anim_rel
    root_rel = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x28)[0]
    node_count = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x2C)[0]

    visited_names: list[str] = []
    controller_counts: dict[str, int] = {}

    def walk(node_rel: int) -> None:
        node_abs = base + node_rel
        name_index = struct.unpack_from("<H", mdl_bytes, node_abs + 0x04)[0]
        name = names[name_index]
        visited_names.append(name)
        controller_counts[name] = struct.unpack_from("<I", mdl_bytes, node_abs + 0x3C)[0]
        child_array_rel = struct.unpack_from("<I", mdl_bytes, node_abs + 0x2C)[0]
        child_count = struct.unpack_from("<I", mdl_bytes, node_abs + 0x30)[0]
        for child_index in range(child_count):
            child_rel = struct.unpack_from("<I", mdl_bytes, base + child_array_rel + child_index * 4)[0]
            walk(child_rel)

    walk(root_rel)

    assert node_count == 5
    assert len(visited_names) == 4
    assert visited_names == ["C_DrexlF", "cutscenedummy", "rootdummy", "pelvis_g"]
    assert "tailGeo" not in visited_names
    assert controller_counts["C_DrexlF"] == 0
    assert controller_counts["cutscenedummy"] == 0
    assert controller_counts["pelvis_g"] == 1


def test_mdl_writer_preserves_binary_compressed_orientation_controller_metadata():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="C_DrexlF")
    anim_root = ModelNode(
        name="C_DrexlF",
        controllers=[
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0, 1.0],
                "values": [(0.0, 0.0, 0.0, 1.0), (0.0, 0.707106, 0.0, 0.707106)],
                "binary_unknown0": 28,
                "binary_column_count": 2,
                "binary_unknown1": [0, 0, 0],
                "binary_compressed_quaternion_words": [0x3FFFFFFF, 0x20002000],
            }
        ],
    )
    model = KotorModel(
        name="C_DrexlF",
        root_node=root,
        animations=[
            Animation(
                name="cwalk",
                length=1.0,
                anim_root="C_DrexlF",
                nodes=[anim_root],
            )
        ],
    )

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)
    base = 12
    anim_table_rel = struct.unpack_from("<I", mdl_bytes, base + 0x58)[0]
    anim_rel = struct.unpack_from("<I", mdl_bytes, base + anim_table_rel)[0]
    anim_abs = base + anim_rel
    anim_root_rel = struct.unpack_from("<I", mdl_bytes, anim_abs + 0x28)[0]
    node_abs = base + anim_root_rel

    ctrl_arr_rel = struct.unpack_from("<I", mdl_bytes, node_abs + 0x38)[0]
    ctrl_data_rel = struct.unpack_from("<I", mdl_bytes, node_abs + 0x44)[0]
    ctrl_data_count = struct.unpack_from("<I", mdl_bytes, node_abs + 0x48)[0]
    ctrl_abs = base + ctrl_arr_rel
    ctrl_data_abs = base + ctrl_data_rel

    assert struct.unpack_from("<I", mdl_bytes, ctrl_abs)[0] == 20
    assert struct.unpack_from("<H", mdl_bytes, ctrl_abs + 0x04)[0] == 28
    assert struct.unpack_from("<H", mdl_bytes, ctrl_abs + 0x06)[0] == 2
    assert struct.unpack_from("<H", mdl_bytes, ctrl_abs + 0x08)[0] == 0
    assert struct.unpack_from("<H", mdl_bytes, ctrl_abs + 0x0A)[0] == 2
    assert mdl_bytes[ctrl_abs + 0x0C] == 2
    assert ctrl_data_count == 4
    assert struct.unpack_from("<ff", mdl_bytes, ctrl_data_abs) == (0.0, 1.0)
    assert struct.unpack_from("<II", mdl_bytes, ctrl_data_abs + 8) == (0x3FFFFFFF, 0x20002000)


def test_legacy_mdl_porter_sets_engine_maxtree_model_subtype_byte():
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.core.mdl.mdl_porter import MDLBinaryWriter

    model = KotorModel(name="pmbam", root_node=ModelNode(name="pmbam"))

    mdl_bytes, _mdx_bytes = MDLBinaryWriter().build(model)

    base = 12
    root_off = struct.unpack_from("<I", mdl_bytes, base + 0x28)[0]
    assert mdl_bytes[base + 0x4C] == 0x02
    assert struct.unpack_from("<I", mdl_bytes, base + 0xA8)[0] == root_off
    assert struct.unpack_from("<I", mdl_bytes, base + 0xB8)[0] == 0xC4
