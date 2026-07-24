from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.core.characters.head_donor_snapshot import (
    capture_head_donor_snapshot,
    compare_head_donor_contract,
    validate_head_donor_snapshot,
)
from src.core.characters.head_geometry_transplant import (
    HeadGeometryTransplantError,
    PART_MODE_RIGID,
    apply_head_skin_weight_edits,
    transplant_head_geometry_and_skin,
)
from src.core.characters.head_texture_materials import (
    HeadTextureMaterialError,
    apply_head_texture_materials,
)
from src.core.game.kotor_loader import load_model_from_bytes
from src.core.geometry.model_data import (
    BoneWeight,
    GameVersion,
    KotorModel,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.io.head_art_importer import import_head_art
from src.io.head_texture_asset import (
    build_head_texture_output_policy,
    inspect_head_texture,
)
from src.math.head_alignment import (
    HeadAlignmentAnchor,
    HeadAlignmentRequest,
    solve_headhook_alignment,
)
from src.math.head_uv import build_head_uv_orientation_contract


def _attach(parent: ModelNode, child: ModelNode) -> None:
    parent.children.append(child)
    child.parent = parent


def _donor() -> KotorModel:
    root = ModelNode(name="PFHA04", index=0, number=0)
    neck = ModelNode(name="neck_g", index=1, number=30)
    head_bone = ModelNode(name="head_g", index=2, number=32)
    jaw = ModelNode(name="f_jaw_g", index=3, number=37)
    skin = ModelNode(
        name="head",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        index=4,
        number=355,
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=["head_g", "neck_g", "f_jaw_g"],
        skin_data=[
            VertexSkinData([BoneWeight(1, 0.5), BoneWeight(0, 0.5)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(2, 1.0)]),
        ],
        bb_min=(-2.0, -2.0, -2.0),
        bb_max=(2.0, 2.0, 2.0),
        radius=3.0,
    )
    skin.bone_node_indices = [2, 1, 3]
    skin.bone_map_floats = [2.0, 1.0, 3.0, 0.0, 0.0]
    skin.qbone_list = [(0.0, 0.0, 0.0, 1.0)] * 5
    skin.tbone_list = [(0.0, 0.0, 0.0)] * 5
    for child in (neck, head_bone, jaw, skin):
        _attach(root, child)
    model = KotorModel(
        name="PFHA04",
        supermodel="S_Female03",
        game_version=GameVersion.K2,
        model_type=4,
        root_node=root,
        bb_min=(-5.0, -5.0, -1.0),
        bb_max=(5.0, 5.0, 10.0),
        radius=7.0,
        super_root_node_name="neck_g",
        geometry_node_count=564,
    )
    model._gr_render_bounds = ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    model._gr_render_radius = 1.0
    return model


def _snapshot(model: KotorModel):
    snapshot = capture_head_donor_snapshot(
        model,
        game="K2",
        resref="PFHA04",
        resource_view="stock_only",
        mdl_sha256="a" * 64,
        mdx_sha256="b" * 64,
    )
    assert validate_head_donor_snapshot(snapshot).eligible
    return snapshot


def _write_art(path: Path, *, two_parts: bool = False) -> None:
    rows = [
        "o face",
        "v 0 0 0",
        "v 1 0 0",
        "v 0 1 0",
        "vt 0 0",
        "vt 1 0",
        "vt 0 1",
        "f 1/1 2/2 3/3",
    ]
    if two_parts:
        rows.extend(
            (
                "o hair",
                "v 0 0 0.2",
                "v 0.2 0 0.2",
                "v 0 0.2 0.2",
                "vt 0 0",
                "vt 1 0",
                "vt 0 1",
                "f 4/4 5/5 6/6",
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _identity_alignment():
    return solve_headhook_alignment(
        HeadAlignmentRequest(
            anchors=(
                HeadAlignmentAnchor("a", (0, 0, 0), (0, 0, 0)),
                HeadAlignmentAnchor("b", (1, 0, 0), (1, 0, 0)),
                HeadAlignmentAnchor("c", (0, 1, 0), (0, 1, 0)),
            ),
            headhook_to_body=(
                (1, 0, 0, 0),
                (0, 1, 0, 0),
                (0, 0, 1, 0),
                (0, 0, 0, 1),
            ),
        )
    )


def _write_texture(path: Path) -> None:
    from PIL import Image

    Image.new("RGBA", (4, 4), (80, 120, 160, 255)).save(
        path,
        format="TGA",
    )


def test_transplant_changes_only_allowed_payload_and_preserves_native_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "head.obj"
    _write_art(source)
    art, report = import_head_art(source)
    assert report.accepted
    donor = _donor()
    snapshot = _snapshot(donor)
    part_id = art.parts[0].part_id

    result = transplant_head_geometry_and_skin(
        donor_model=donor,
        donor_snapshot=snapshot,
        art_document=art,
        alignment=_identity_alignment(),
        part_modes=None,
        neck_vertex_ids=[
            f"{part_id}:v:0",
            f"{part_id}:v:1",
            f"{part_id}:v:2",
        ],
        maximum_surface_distance=0.01,
        minimum_neck_weight=0.1,
    )

    donor_nodes = donor.all_nodes()
    output_nodes = result.model.all_nodes()
    assert [node.name for node in output_nodes] == [
        node.name for node in donor_nodes
    ]
    assert [node.number for node in output_nodes] == [
        node.number for node in donor_nodes
    ]
    output_skin = output_nodes[4]
    donor_skin = donor_nodes[4]
    assert output_skin.bone_map == donor_skin.bone_map
    assert output_skin.bone_node_indices == donor_skin.bone_node_indices
    assert output_skin.bone_map_floats == donor_skin.bone_map_floats
    assert output_skin.qbone_list == donor_skin.qbone_list
    assert output_skin.tbone_list == donor_skin.tbone_list
    assert output_skin.bb_min == donor_skin.bb_min
    assert output_skin.bb_max == donor_skin.bb_max
    assert output_skin.radius == donor_skin.radius
    assert result.model.bb_min == donor.bb_min
    assert result.model.bb_max == donor.bb_max
    assert result.model.radius == donor.radius
    diff = compare_head_donor_contract(snapshot, result.model)
    assert diff.blocking == ()
    assert diff.allowed_payload_changes
    assert result.report.accepted
    assert result.report.neck_vertex_count == 3
    assert result.report.transfer.neck_floor_adjustment_count >= 1


def test_rigid_part_uses_head_g_without_changing_palette(
    tmp_path: Path,
) -> None:
    source = tmp_path / "parts.obj"
    _write_art(source, two_parts=True)
    art, report = import_head_art(source)
    assert report.accepted
    donor = _donor()
    snapshot = _snapshot(donor)
    face, hair = art.parts

    result = transplant_head_geometry_and_skin(
        donor_model=donor,
        donor_snapshot=snapshot,
        art_document=art,
        alignment=_identity_alignment(),
        part_modes={hair.part_id: PART_MODE_RIGID},
        neck_vertex_ids=[
            f"{face.part_id}:v:0",
            f"{face.part_id}:v:1",
            f"{face.part_id}:v:2",
        ],
        maximum_surface_distance=1.0,
    )

    hair_record = next(
        row for row in result.report.parts if row.part_id == hair.part_id
    )
    for row in result.rows[
        hair_record.first_vertex:
        hair_record.first_vertex + hair_record.vertex_count
    ]:
        assert len(row.influences) == 1
        assert row.influences[0].palette_slot == 0
        assert row.influences[0].weight == 1.0
    assert result.report.transfer.explicit_rigid_count == 3
    assert result.report.palette_names == (
        "head_g",
        "neck_g",
        "f_jaw_g",
    )


def test_manual_weight_edits_are_sparse_deterministic_and_contract_safe(
    tmp_path: Path,
) -> None:
    source = tmp_path / "edit.obj"
    _write_art(source)
    art, _report = import_head_art(source)
    donor = _donor()
    snapshot = _snapshot(donor)
    part_id = art.parts[0].part_id
    baseline = transplant_head_geometry_and_skin(
        donor_model=donor,
        donor_snapshot=snapshot,
        art_document=art,
        alignment=_identity_alignment(),
        part_modes=None,
        neck_vertex_ids=[
            f"{part_id}:v:0",
            f"{part_id}:v:1",
            f"{part_id}:v:2",
        ],
        maximum_surface_distance=0.01,
    )
    edits = {
        f"{part_id}:v:2": {
            "head_g": 0.25,
            "f_jaw_g": 0.75,
        }
    }

    first = apply_head_skin_weight_edits(
        baseline,
        donor_snapshot=snapshot,
        edits=edits,
    )
    second = apply_head_skin_weight_edits(
        baseline,
        donor_snapshot=snapshot,
        edits=edits,
    )

    assert first.report.manual_edit_count == 1
    assert first.report.final_weight_rows_sha256 == (
        second.report.final_weight_rows_sha256
    )
    assert first.report.final_weight_rows_sha256 != (
        first.report.baseline_weight_rows_sha256
    )
    assert compare_head_donor_contract(
        snapshot,
        first.model,
    ).blocking == ()
    weights = {
        row.palette_slot: row.weight
        for row in first.rows[2].influences
    }
    assert weights == pytest.approx({2: 0.75, 0: 0.25})


def test_transplant_rejects_non_boundary_neck_selection(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fan.obj"
    source.write_text(
        "\n".join(
            (
                "o fan",
                "v -1 -1 0",
                "v 1 -1 0",
                "v 1 1 0",
                "v -1 1 0",
                "v 0 0 0",
                "f 1 2 5",
                "f 2 3 5",
                "f 3 4 5",
                "f 4 1 5",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    art, _report = import_head_art(source)
    donor = _donor()
    part_id = art.parts[0].part_id
    center_index = next(
        index
        for index, vertex in enumerate(art.parts[0].vertices)
        if vertex == pytest.approx((0.0, 0.0, 0.0))
    )
    boundary_indices = [
        index
        for index in range(len(art.parts[0].vertices))
        if index != center_index
    ]

    with pytest.raises(HeadGeometryTransplantError, match="not"):
        transplant_head_geometry_and_skin(
            donor_model=donor,
            donor_snapshot=_snapshot(donor),
            art_document=art,
            alignment=_identity_alignment(),
            part_modes=None,
            neck_vertex_ids=[
                f"{part_id}:v:{boundary_indices[0]}",
                f"{part_id}:v:{boundary_indices[1]}",
                f"{part_id}:v:{center_index}",
            ],
            maximum_surface_distance=2.0,
        )


def test_transplant_requires_pristine_donor(tmp_path: Path) -> None:
    source = tmp_path / "pristine.obj"
    _write_art(source)
    art, _report = import_head_art(source)
    donor = _donor()
    snapshot = _snapshot(donor)
    donor.all_nodes()[4].vertices[0] = (9.0, 9.0, 9.0)
    part_id = art.parts[0].part_id

    with pytest.raises(HeadGeometryTransplantError, match="pristine"):
        transplant_head_geometry_and_skin(
            donor_model=donor,
            donor_snapshot=snapshot,
            art_document=art,
            alignment=_identity_alignment(),
            part_modes=None,
            neck_vertex_ids=[
                f"{part_id}:v:0",
                f"{part_id}:v:1",
                f"{part_id}:v:2",
            ],
            maximum_surface_distance=1.0,
        )


def test_texture_material_policy_is_explicit_and_donor_safe(
    tmp_path: Path,
) -> None:
    source = tmp_path / "head.obj"
    texture_path = tmp_path / "head_diffuse.tga"
    _write_art(source)
    _write_texture(texture_path)
    art, _report = import_head_art(source, flip_v=False)
    donor = _donor()
    snapshot = _snapshot(donor)
    part = art.parts[0]
    transplant = transplant_head_geometry_and_skin(
        donor_model=donor,
        donor_snapshot=snapshot,
        art_document=art,
        alignment=_identity_alignment(),
        part_modes=None,
        neck_vertex_ids=[
            f"{part.part_id}:v:0",
            f"{part.part_id}:v:1",
            f"{part.part_id}:v:2",
        ],
        maximum_surface_distance=0.01,
    )
    asset = inspect_head_texture(texture_path)
    policy = build_head_texture_output_policy(
        asset,
        output_resref="P_CDH01",
        output_format="TGA",
        txi_delivery="sidecar",
    )
    uv_contract = build_head_uv_orientation_contract(
        part.uvs,
        part.faces,
        source_v_flip_applied=art.flip_v,
        serialized_transform="identity",
        preview_transform="identity",
    )

    result = apply_head_texture_materials(
        transplant,
        donor_snapshot=snapshot,
        asset=asset,
        output_policy=policy,
        uv_contract=uv_contract,
    )

    output_skin = result.model.all_nodes()[4]
    assert output_skin.texture == "P_CDH01"
    assert output_skin.uvs == transplant.model.all_nodes()[4].uvs
    assert output_skin.uv_v_flip is False
    assert output_skin._gr_mdx_uv_transform == "identity"
    assert result.report.accepted
    assert result.report.preview_matches_serialized
    assert result.report.packaged_files == ("P_CDH01.tga", "P_CDH01.txi")
    assert compare_head_donor_contract(snapshot, result.model).blocking == ()

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(result.model)
    reopened = load_model_from_bytes(mdl_bytes, mdx_bytes)
    reopened_skin = next(
        node
        for node in reopened.all_nodes()
        if str(node.name).casefold() == "head"
    )
    for actual, expected in zip(
        reopened_skin.uvs,
        part.uvs,
        strict=True,
    ):
        assert actual == pytest.approx(expected, abs=1.0e-6)
    assert reopened_skin.texture.casefold() == "p_cdh01"


def test_texture_material_policy_rejects_preview_serialization_mismatch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "head.obj"
    texture_path = tmp_path / "head_diffuse.tga"
    _write_art(source)
    _write_texture(texture_path)
    art, _report = import_head_art(source)
    donor = _donor()
    snapshot = _snapshot(donor)
    part = art.parts[0]
    transplant = transplant_head_geometry_and_skin(
        donor_model=donor,
        donor_snapshot=snapshot,
        art_document=art,
        alignment=_identity_alignment(),
        part_modes=None,
        neck_vertex_ids=[
            f"{part.part_id}:v:0",
            f"{part.part_id}:v:1",
            f"{part.part_id}:v:2",
        ],
        maximum_surface_distance=0.01,
    )
    asset = inspect_head_texture(texture_path)
    policy = build_head_texture_output_policy(
        asset,
        output_resref="P_CDH01",
        output_format="TPC",
    )
    mismatch = build_head_uv_orientation_contract(
        part.uvs,
        part.faces,
        source_v_flip_applied=art.flip_v,
        serialized_transform="identity",
        preview_transform="flip_v",
    )

    with pytest.raises(HeadTextureMaterialError, match="differs"):
        apply_head_texture_materials(
            transplant,
            donor_snapshot=snapshot,
            asset=asset,
            output_policy=policy,
            uv_contract=mismatch,
        )
