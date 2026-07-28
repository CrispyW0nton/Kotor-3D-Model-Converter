"""Focused binary/readback and structural preflight tests for Head Builder."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.characters.head_facial_transplant import (
    _disable_replaced_donor_render_nodes,
)
from src.core.characters.head_donor_snapshot import (
    capture_head_donor_snapshot,
)
from src.core.geometry.model_data import (
    Animation,
    BoneWeight,
    GameVersion,
    KotorModel,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)
from src.core.game.kotor_loader import load_model_from_bytes
from src.core.validation.head_builder_preflight import (
    preflight_head_builder_export,
)
from src.io.head_binary_export import (
    build_verified_head_binary,
    write_verified_head_binary,
)


def _attach(parent: ModelNode, child: ModelNode) -> None:
    parent.children.append(child)
    child.parent = parent


def _head() -> KotorModel:
    root = ModelNode(name="PFHA04", index=0, number=0)
    neck = ModelNode(name="neck_g", index=1, number=30)
    head_g = ModelNode(name="head_g", index=2, number=32)
    jaw = ModelNode(name="f_jaw_g", index=3, number=37)
    skin = ModelNode(
        name="head",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        index=4,
        number=355,
        vertices=[
            (-0.1, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.0, 0.0, 0.2),
        ],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="P_CDH01",
        bone_map=["head_g", "neck_g", "f_jaw_g"],
        skin_data=[
            VertexSkinData(
                [BoneWeight(0, 0.8), BoneWeight(1, 0.2)]
            ),
            VertexSkinData(
                [BoneWeight(0, 0.9), BoneWeight(2, 0.1)]
            ),
            VertexSkinData(
                [BoneWeight(0, 1.0)]
            ),
        ],
        bb_min=(-0.1, 0.0, 0.0),
        bb_max=(0.1, 0.0, 0.2),
        radius=0.15,
    )
    skin.bone_node_indices = [2, 1, 3]
    skin.qbone_list = [(0.0, 0.0, 0.0, 1.0)] * 5
    skin.tbone_list = [(0.0, 0.0, 0.0)] * 5
    skin._gr_mdx_uv_transform = "identity"
    skin.uv_v_flip = False
    for child in (neck, head_g, jaw, skin):
        _attach(root, child)
    return KotorModel(
        name="PFHA04",
        supermodel="S_Female03",
        game_version=GameVersion.K2,
        model_type=4,
        root_node=root,
        bb_min=(-5.0, -5.0, -1.0),
        bb_max=(5.0, 5.0, 10.0),
        radius=7.0,
        super_root_node_name="neck_g",
        geometry_node_count=5,
        preserve_native_supernode_numbers=True,
    )


def _snapshot(model: KotorModel):
    return capture_head_donor_snapshot(
        model,
        game="K2",
        resref="PFHA04",
        resource_view="stock_only",
        mdl_sha256="a" * 64,
        mdx_sha256="b" * 64,
        provenance={"stock": True},
    )


@dataclass
class _TextureReport:
    accepted: bool = True
    preview_matches_serialized: bool = True
    uv_warnings: tuple[str, ...] = ()
    texture_warnings: tuple[str, ...] = ()


@dataclass
class _AttachmentReport:
    accepted: bool = True
    source_head_local_animation_names: tuple[str, ...] = ()
    preview_head_local_animation_names: tuple[str, ...] = ()


def test_binary_build_preserves_raw_roots_bounds_payload_and_game_family() -> None:
    model = _head()
    snapshot = _snapshot(model)

    build = build_verified_head_binary(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
    )

    inspection = build.inspection
    assert inspection.accepted
    assert inspection.model_function_pointers == (4285200, 4216320)
    assert inspection.geometry_root_offset != (
        inspection.attachment_root_offset
    )
    assert inspection.geometry_root_name == "P_CUSTOMH"
    assert inspection.attachment_root_name == "neck_g"
    assert inspection.raw_geometry_node_count == 5
    assert inspection.raw_model_bounds == (
        (-5.0, -5.0, -1.0),
        (5.0, 5.0, 10.0),
        7.0,
    )
    assert inspection.candidate_payload_sha256 == (
        inspection.reloaded_payload_sha256
    )
    assert inspection.donor_contract_diff.blocking == ()
    assert inspection.mdl_sha256
    assert inspection.mdx_sha256
    reloaded = load_model_from_bytes(
        build.mdl_bytes,
        build.mdx_bytes,
        GameVersion.K2,
    )
    assert reloaded is not None
    assert reloaded.preserve_native_supernode_numbers is True
    assert [node.number for node in reloaded.all_nodes()] == [
        0,
        30,
        32,
        37,
        355,
    ]


def test_binary_readback_hashes_every_certified_component_payload() -> None:
    model = _head()
    assert model.root_node is not None
    eye = ModelNode(
        name="eyeLA",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        index=5,
        number=356,
        vertices=[(-0.03, -0.02, 0.1), (0.01, -0.02, 0.1), (-0.01, 0.01, 0.1)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="PFHA04EYE",
        bb_min=(-0.03, -0.02, 0.1),
        bb_max=(0.01, 0.01, 0.1),
        radius=0.025,
    )
    _attach(model.root_node, eye)
    model.geometry_node_count = 6
    skin = model.find_node("head")
    assert skin is not None
    skin.qbone_list.append((0.0, 0.0, 0.0, 1.0))
    skin.tbone_list.append((0.0, 0.0, 0.0))
    snapshot = _snapshot(model)
    eye_ordinal = model.all_nodes().index(eye)
    snapshot = replace(
        snapshot,
        compatibility={
            "component_payload_node_ordinals": [eye_ordinal],
            "component_source_resrefs": {"eyes": "PFHA02"},
        },
    )
    candidate = deepcopy(model)
    candidate_eye = candidate.find_node("eyeLA")
    assert candidate_eye is not None
    candidate_eye.texture = "PFHA02EYE"

    build = build_verified_head_binary(
        candidate,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_EYEMIX",
    )

    assert build.inspection.accepted
    assert build.inspection.candidate_payload_sha256 == (
        build.inspection.reloaded_payload_sha256
    )
    assert build.inspection.donor_contract_diff.blocking == ()
    reloaded_eye = build.inspection.reloaded_model.find_node("eyeLA")
    assert reloaded_eye is not None
    assert reloaded_eye.texture.casefold() == "pfha02eye"


def test_disabled_donor_mesh_serializes_static_alpha_controller() -> None:
    node = SimpleNamespace(
        name="donor_component",
        render=True,
        alpha=1.0,
        vertices=[(0.0, 0.0, 0.0)],
        faces=[(0, 0, 0)],
        controllers=[
            {
                "type": 132,
                "name": "alpha",
                "columns": 1,
                "times": [0.0],
                "values": [[1.0]],
                "binary_unknown0": 0xFFFF,
                "binary_column_count": 1,
                "binary_unknown1": [0, 0, 0],
            }
        ],
    )

    disabled = _disable_replaced_donor_render_nodes(
        [node],
        assigned_node_ids=set(),
    )

    assert disabled == ("donor_component",)
    assert node.render is False
    assert node.alpha == 0.0
    assert node.controllers[0]["type"] == 132
    assert node.controllers[0]["times"] == [0.0]
    assert node.controllers[0]["values"] == [[0.0]]


def test_disabled_donor_mesh_creates_missing_alpha_controller() -> None:
    node = SimpleNamespace(
        name="donor_component",
        render=True,
        alpha=1.0,
        vertices=[(0.0, 0.0, 0.0)],
        faces=[(0, 0, 0)],
        controllers=[],
    )

    _disable_replaced_donor_render_nodes([node], assigned_node_ids=set())

    assert node.controllers == [
        {
            "type": 132,
            "name": "alpha",
            "columns": 1,
            "times": [0.0],
            "values": [[0.0]],
            "binary_unknown0": 0xFFFF,
            "binary_column_count": 1,
            "binary_unknown1": [0, 0, 0],
        }
    ]


def test_verified_binary_publish_is_atomic_and_requires_explicit_overwrite(
    tmp_path: Path,
) -> None:
    model = _head()
    build = build_verified_head_binary(
        model,
        donor_snapshot=_snapshot(model),
        game="K2",
        output_resref="P_CUSTOMH",
    )

    written = write_verified_head_binary(
        build,
        output_dir=tmp_path,
        manifest_metadata={"project_id": "project"},
    )

    assert Path(written.mdl_path).read_bytes() == build.mdl_bytes
    assert Path(written.mdx_path).read_bytes() == build.mdx_bytes
    assert Path(written.manifest_path).is_file()
    assert list(tmp_path.glob(".*.tmp")) == []
    with pytest.raises(FileExistsError, match="explicit overwrite"):
        write_verified_head_binary(build, output_dir=tmp_path)
    overwritten = write_verified_head_binary(
        build,
        output_dir=tmp_path,
        overwrite=True,
    )
    assert Path(overwritten.mdl_path).read_bytes() == build.mdl_bytes


def test_preflight_requires_explicit_warning_acknowledgment() -> None:
    model = _head()
    snapshot = _snapshot(model)
    texture = _TextureReport(
        uv_warnings=("Intentional mirrored UV overlap.",)
    )

    pending = preflight_head_builder_export(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
        texture_report=texture,
        attachment_report=_AttachmentReport(),
    )
    accepted = preflight_head_builder_export(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
        texture_report=texture,
        attachment_report=_AttachmentReport(),
        acknowledged_warning_ids=(
            "head.preflight.uv_texture_warnings",
        ),
    )

    assert pending.blocking_issues == ()
    assert pending.export_allowed is False
    assert pending.unacknowledged_warning_ids == (
        "head.preflight.uv_texture_warnings",
    )
    assert accepted.export_allowed is True
    assert accepted.unacknowledged_warning_ids == ()
    assert accepted.binary_build is not None


def test_preflight_blocks_nonfinite_geometry_before_writer_sanitization() -> None:
    model = _head()
    snapshot = _snapshot(model)
    model.all_nodes()[4].vertices[0] = (float("nan"), 0.0, 0.0)

    report = preflight_head_builder_export(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
        texture_report=_TextureReport(),
        attachment_report=_AttachmentReport(),
    )

    assert report.export_allowed is False
    assert report.binary_build is None
    assert "head.preflight.nonfinite_payload" in {
        issue.check_id for issue in report.blocking_issues
    }


def test_preflight_blocks_missing_required_facial_weight_and_local_clip() -> None:
    model = _head()
    snapshot = _snapshot(model)
    skin = model.all_nodes()[4]
    skin.skin_data[1] = VertexSkinData([BoneWeight(0, 1.0)])
    model.animations = [Animation(name="walk")]

    report = preflight_head_builder_export(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
        texture_report=_TextureReport(),
        attachment_report=_AttachmentReport(),
    )

    check_ids = {issue.check_id for issue in report.blocking_issues}
    assert report.export_allowed is False
    assert "head.preflight.required_facial_weights" in check_ids
    assert "head.preflight.local_animations" in check_ids


def test_binary_build_rejects_wrong_attachment_root() -> None:
    model = _head()
    snapshot = _snapshot(model)
    model.super_root_node_name = "head_g"

    build = build_verified_head_binary(
        model,
        donor_snapshot=snapshot,
        game="K2",
        output_resref="P_CUSTOMH",
    )

    assert build.inspection.accepted is False
    assert any(
        "attachment root" in issue.casefold()
        for issue in build.inspection.blocking_issues
    )
