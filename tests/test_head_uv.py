"""Focused UV-orientation and integrity tests for Custom Head Builder."""

from __future__ import annotations

import pytest

from src.core.geometry.model_data import ModelNode
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.math.head_uv import (
    HeadUvError,
    apply_head_uv_transform,
    audit_head_uvs,
    build_head_uv_orientation_contract,
)


def test_uv_contract_keeps_preview_and_serialized_orientation_explicit() -> None:
    uvs = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
    faces = ((0, 1, 2),)

    matching = build_head_uv_orientation_contract(
        uvs,
        faces,
        source_v_flip_applied=False,
        serialized_transform="identity",
        preview_transform="identity",
    )
    mismatched = build_head_uv_orientation_contract(
        uvs,
        faces,
        source_v_flip_applied=False,
        serialized_transform="identity",
        preview_transform="flip_v",
    )

    assert matching.accepted
    assert matching.preview_matches_serialized
    assert mismatched.audit.accepted
    assert not mismatched.preview_matches_serialized
    assert not mismatched.accepted


def test_v_flip_is_a_uv_space_involution() -> None:
    source = ((0.2, 0.1), (0.8, 0.4), (0.5, 0.9))

    flipped = apply_head_uv_transform(source, "flip_v")

    for actual, expected in zip(
        flipped,
        ((0.2, 0.9), (0.8, 0.6), (0.5, 0.1)),
        strict=True,
    ):
        assert actual == pytest.approx(expected)
    for actual, expected in zip(
        apply_head_uv_transform(flipped, "flip_v"),
        source,
        strict=True,
    ):
        assert actual == pytest.approx(expected)


def test_uv_audit_accepts_shared_edges_without_overlap() -> None:
    audit = audit_head_uvs(
        ((0, 0), (1, 0), (1, 1), (0, 1)),
        ((0, 1, 2), (0, 2, 3)),
    )

    assert audit.accepted
    assert audit.overlapping_face_pair_count == 0
    assert audit.inconsistent_winding_face_count == 0


def test_uv_audit_reports_intentional_overlap_as_baking_warning() -> None:
    audit = audit_head_uvs(
        ((0, 0), (1, 0), (0, 1), (0, 0), (1, 0), (0, 1)),
        ((0, 1, 2), (3, 4, 5)),
    )

    assert audit.accepted
    assert audit.overlapping_face_pair_count == 1
    assert any("baking" in warning for warning in audit.warnings)


@pytest.mark.parametrize(
    ("uvs", "faces", "expected"),
    [
        (((0, 0), (1, 0)), ((0, 1, 1),), "missing_uv_count"),
        (((0, 0), (2, 0), (0, 1)), ((0, 1, 2),), "outside_unit_square_count"),
        (((0, 0), (0.5, 0), (1, 0)), ((0, 1, 2),), "degenerate_face_count"),
    ],
)
def test_uv_audit_blocks_incomplete_outside_or_degenerate_channels(
    uvs,
    faces,
    expected: str,
) -> None:
    audit = audit_head_uvs(
        uvs,
        faces,
        expected_vertex_count=3,
    )

    assert not audit.accepted
    assert getattr(audit, expected) > 0


def test_uv_transform_rejects_implicit_orientation_names() -> None:
    with pytest.raises(HeadUvError, match="identity"):
        apply_head_uv_transform(((0, 0),), "auto")


def test_mdx_writer_uses_explicit_transform_independent_of_preview_flag() -> None:
    node = ModelNode(name="head")
    node.uv_v_flip = False
    node._gr_mdx_uv_transform = "identity"

    assert MDLBinaryWriter._uv_pair_for_mdx(node, 0.25, 0.2) == (
        0.25,
        0.2,
    )

    node._gr_mdx_uv_transform = "flip_v"
    assert MDLBinaryWriter._uv_pair_for_mdx(node, 0.25, 0.2) == pytest.approx(
        (0.25, 0.8)
    )


def test_mdx_writer_keeps_legacy_uv_flag_fallback() -> None:
    node = ModelNode(name="head")
    node.uv_v_flip = False

    assert MDLBinaryWriter._uv_pair_for_mdx(node, 0.25, 0.2) == pytest.approx(
        (0.25, 0.8)
    )

    node._gr_mdx_uv_transform = "implicit"
    with pytest.raises(ValueError, match="Unsupported"):
        MDLBinaryWriter._uv_pair_for_mdx(node, 0.25, 0.2)
