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
