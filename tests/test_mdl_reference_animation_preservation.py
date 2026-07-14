"""Vanilla-backed MDL reference-node and zero-transition preservation gates."""

from __future__ import annotations

import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.game.kotor_loader import _convert_anim, load_model_from_bytes
from src.core.geometry.model_data import (
    Animation,
    GameVersion,
    KotorModel,
    ModelNode,
    NodeFlags,
)
from src.core.mdl.mdl_reader_wrapper import read_mdl_safe
from src.core.mdl.mdl_writer import MDLBinaryWriter


_DEFAULT_K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")


def _reference_payload(model: str, reattachable: bool) -> bytes:
    encoded = model.encode("ascii")[:31]
    return encoded + (b"\x00" * (32 - len(encoded))) + struct.pack("<I", int(reattachable))


def _synthetic_reference_model(*, reattachable: bool = True) -> KotorModel:
    root = ModelNode(name="reference_fixture", flags=int(NodeFlags.HEADER))
    reference = ModelNode(
        name="BrithRef",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.REFERENCE),
        parent=root,
        reference_model="C_Brith",
        reference_reattachable=reattachable,
    )
    root.children = [reference]
    return KotorModel(
        name="reference_fixture",
        classification="tile",
        model_type=2,
        game_version=GameVersion.K1,
        root_node=root,
    )


def _resource_bytes(installation, resref: str, restype) -> bytes:
    result = installation.resource(resref, restype)
    if result is None:
        pytest.skip(f"Vanilla resource {resref}.{restype.extension} is unavailable")
    data = getattr(result, "data", result)
    if callable(data):
        data = data()
    payload = bytes(data or b"")
    if not payload:
        pytest.skip(f"Vanilla resource {resref}.{restype.extension} is empty")
    return payload


def _pykotor_animation_controller(model, animation_name: str, node_name: str, controller_type: int):
    animation = next(anim for anim in model.anims if anim.name.lower() == animation_name.lower())
    node = next(node for node in animation.all_nodes() if node.name.lower() == node_name.lower())
    return next(ctrl for ctrl in node.controllers if int(ctrl.controller_type) == int(controller_type))


def _domain_animation_controller(model, animation_name: str, node_name: str, controller_type: int) -> dict:
    animation = next(anim for anim in model.animations if anim.name.lower() == animation_name.lower())
    node = next(node for node in animation.nodes if node.name.lower() == node_name.lower())
    return next(ctrl for ctrl in node.controllers if int(ctrl.get("type", 0)) == int(controller_type))


def test_animation_conversion_preserves_legitimate_zero_transition() -> None:
    source = SimpleNamespace(
        name="animloop2",
        length=63.8333,
        transition_time=0.0,
        transition_length=0.25,
        root_model="m14aa_01f",
        events=[],
        all_nodes=lambda: [],
    )

    converted = _convert_anim(source)

    assert converted is not None
    assert converted.transition_time == 0.0


def test_reference_node_model_and_reattachable_survive_binary_write() -> None:
    model = _synthetic_reference_model(reattachable=True)
    reference = model.root_node.children[0]

    cloned = reference.clone_shallow()
    assert cloned.reference_model == "C_Brith"
    assert cloned.reference_reattachable is True

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    parsed = read_mdl_safe(mdl_bytes, source_ext=mdx_bytes)
    references = [node for node in parsed.all_nodes() if getattr(node, "reference", None) is not None]

    assert _reference_payload("C_Brith", True) in mdl_bytes
    assert len(references) == 1
    assert references[0].reference.model == "C_Brith"
    assert references[0].reference.reattachable is True


def test_cross_game_writer_preserves_zero_transition_header() -> None:
    from src.core.mdl.mdl_porter import MDLBinaryWriter as CrossGameMDLBinaryWriter

    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    animation = Animation(
        name="zero_transition",
        length=1.0,
        transition_time=0.0,
        anim_root="root",
        nodes=[ModelNode(name="root")],
    )
    model = KotorModel(
        name="zero_transition",
        game_version=GameVersion.K1,
        root_node=root,
        animations=[animation],
    )

    mdl_bytes, mdx_bytes = CrossGameMDLBinaryWriter().build(model)
    parsed = read_mdl_safe(mdl_bytes, source_ext=mdx_bytes)

    assert len(parsed.anims) == 1
    assert parsed.anims[0].transition_time == 0.0


def test_bezier_controller_flag_and_tangents_survive_binary_roundtrip() -> None:
    root = ModelNode(name="bezier_fixture", flags=int(NodeFlags.HEADER))
    dummy = ModelNode(name="Dummy01", flags=int(NodeFlags.HEADER), parent=root)
    root.children = [dummy]

    anim_root = ModelNode(name="bezier_fixture", flags=int(NodeFlags.HEADER))
    anim_dummy = ModelNode(name="Dummy01", flags=int(NodeFlags.HEADER), parent=anim_root)
    anim_root.children = [anim_dummy]
    bezier_rows = [
        [0.0, 0.0, 0.0, -0.25, -0.5, -0.75, 0.25, 0.5, 0.75],
        [1.0, 2.0, 3.0, -0.5, -1.0, -1.5, 0.5, 1.0, 1.5],
    ]
    anim_dummy.controllers = [
        {
            "type": 8,
            "name": "position",
            "columns": 3,
            "times": [0.0, 1.0],
            "values": [row[:3] for row in bezier_rows],
            "is_bezier": True,
            "binary_column_count": 0x13,
            "binary_unknown0": 16,
            "binary_unknown1": [0, 0, 0],
            "binary_bezier_rows": bezier_rows,
        }
    ]
    model = KotorModel(
        name="bezier_fixture",
        classification="effect",
        model_type=0,
        game_version=GameVersion.K1,
        root_node=root,
        animations=[
            Animation(
                name="animloop2",
                length=1.0,
                transition_time=0.0,
                anim_root="bezier_fixture",
                nodes=[anim_root, anim_dummy],
            )
        ],
    )

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    parsed = read_mdl_safe(mdl_bytes, source_ext=mdx_bytes)
    parsed_controller = _pykotor_animation_controller(parsed, "animloop2", "Dummy01", 8)
    raw = getattr(parsed_controller, "_gr_binary_controller")

    assert parsed_controller.is_bezier is True
    assert raw["column_count"] == 0x13
    assert raw["unknown0"] == 16
    assert raw["row_count"] == 2
    assert raw["key_offset"] == 0
    assert raw["data_offset"] == 2
    assert raw["bezier_rows"] == bezier_rows
    assert [row.data for row in parsed_controller.rows] == bezier_rows

    reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, GameVersion.K1)
    reloaded_controller = _domain_animation_controller(reloaded, "animloop2", "Dummy01", 8)
    assert reloaded_controller["is_bezier"] is True
    assert reloaded_controller["binary_column_count"] == 0x13
    assert reloaded_controller["binary_bezier_rows"] == bezier_rows


def test_k1_dantooine_brith_reference_and_zero_transition_roundtrip() -> None:
    from pykotor.extract.installation import Installation
    from pykotor.resource.type import ResourceType

    configured = Path(os.environ.get("K1_PATH", ""))
    k1_root = configured if configured.is_dir() else _DEFAULT_K1_ROOT
    if not k1_root.is_dir():
        pytest.skip(f"KOTOR 1 installation unavailable: {k1_root}")

    installation = Installation(k1_root)
    source_mdl = _resource_bytes(installation, "m14aa_01f", ResourceType.MDL)
    source_mdx = _resource_bytes(installation, "m14aa_01f", ResourceType.MDX)
    model = load_model_from_bytes(source_mdl, source_mdx, GameVersion.K1)
    assert model is not None

    references = [node for node in model.all_nodes() if node.is_reference]
    animations = [anim for anim in model.animations if anim.name.lower() == "animloop2"]
    assert [(node.name, node.reference_model, node.reference_reattachable) for node in references] == [
        ("BrithRef", "C_Brith", False),
    ]
    assert len(animations) == 1
    assert animations[0].transition_time == 0.0

    source_parsed = read_mdl_safe(source_mdl, source_ext=source_mdx)
    source_references = [
        node for node in source_parsed.all_nodes() if getattr(node, "reference", None) is not None
    ]
    assert [(node.name, node.reference.model, node.reference.reattachable) for node in source_references] == [
        ("BrithRef", "C_Brith", False),
    ]

    output_mdl, output_mdx = MDLBinaryWriter().write(model)
    parsed = read_mdl_safe(output_mdl, source_ext=output_mdx)
    parsed_references = [
        node for node in parsed.all_nodes() if getattr(node, "reference", None) is not None
    ]
    parsed_animations = [anim for anim in parsed.anims if anim.name.lower() == "animloop2"]

    assert [(node.name, node.reference.model, node.reference.reattachable) for node in parsed_references] == [
        ("BrithRef", "C_Brith", False),
    ]
    assert len(parsed_animations) == 1
    assert parsed_animations[0].transition_time == 0.0


def test_k1_dantooine_bezier_controller_roundtrip_is_structurally_lossless() -> None:
    from pykotor.extract.installation import Installation
    from pykotor.resource.type import ResourceType

    configured = Path(os.environ.get("K1_PATH", ""))
    k1_root = configured if configured.is_dir() else _DEFAULT_K1_ROOT
    if not k1_root.is_dir():
        pytest.skip(f"KOTOR 1 installation unavailable: {k1_root}")

    installation = Installation(k1_root)
    source_mdl = _resource_bytes(installation, "m14aa_01f", ResourceType.MDL)
    source_mdx = _resource_bytes(installation, "m14aa_01f", ResourceType.MDX)

    source_parsed = read_mdl_safe(source_mdl, source_ext=source_mdx)
    source_controller = _pykotor_animation_controller(source_parsed, "animloop2", "Dummy01", 8)
    source_raw = getattr(source_controller, "_gr_binary_controller")
    source_times = [row.time for row in source_controller.rows]
    source_rows = [list(row.data) for row in source_controller.rows]

    assert source_controller.is_bezier is True
    assert source_raw["column_count"] == 0x13
    assert source_raw["unknown0"] == 16
    assert source_raw["row_count"] == 37
    assert source_raw["key_offset"] == 0
    assert source_raw["data_offset"] == 37
    assert len(source_raw["bezier_rows"]) == 37
    assert {len(row) for row in source_raw["bezier_rows"]} == {9}
    assert source_raw["bezier_rows"] == source_rows

    model = load_model_from_bytes(source_mdl, source_mdx, GameVersion.K1)
    assert model is not None
    domain_controller = _domain_animation_controller(model, "animloop2", "Dummy01", 8)
    assert domain_controller["values"] == [row[:3] for row in source_rows]
    assert domain_controller["is_bezier"] is True
    assert domain_controller["binary_column_count"] == 0x13
    assert domain_controller["binary_unknown0"] == 16
    assert domain_controller["binary_bezier_rows"] == source_rows

    output_mdl, output_mdx = MDLBinaryWriter().write(model)
    output_parsed = read_mdl_safe(output_mdl, source_ext=output_mdx)
    output_controller = _pykotor_animation_controller(output_parsed, "animloop2", "Dummy01", 8)
    output_raw = getattr(output_controller, "_gr_binary_controller")

    header_fields = (
        "type",
        "unknown0",
        "row_count",
        "key_offset",
        "data_offset",
        "column_count",
        "unknown1",
    )
    assert {field: output_raw[field] for field in header_fields} == {
        field: source_raw[field] for field in header_fields
    }
    assert output_controller.is_bezier is True
    assert [row.time for row in output_controller.rows] == source_times
    assert [list(row.data) for row in output_controller.rows] == source_rows
    assert output_raw["bezier_rows"] == source_raw["bezier_rows"]
    assert struct.pack(f"<{len(source_times)}f", *source_times) == struct.pack(
        f"<{len(output_controller.rows)}f",
        *(row.time for row in output_controller.rows),
    )
    assert b"".join(struct.pack("<9f", *row) for row in source_rows) == b"".join(
        struct.pack("<9f", *row.data)
        for row in output_controller.rows
    )
    assert output_mdx == source_mdx

    reloaded = load_model_from_bytes(output_mdl, output_mdx, GameVersion.K1)
    reloaded_controller = _domain_animation_controller(reloaded, "animloop2", "Dummy01", 8)
    assert reloaded_controller["is_bezier"] is True
    assert reloaded_controller["binary_column_count"] == 0x13
    assert reloaded_controller["binary_unknown0"] == 16
    assert reloaded_controller["binary_bezier_rows"] == source_rows
