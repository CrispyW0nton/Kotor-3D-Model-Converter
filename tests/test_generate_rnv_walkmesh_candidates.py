from __future__ import annotations

import pytest
from pykotor.resource.type import ResourceType

from core.modules.module_format import WOKData, WOKFace
from scripts.build_rnv_k2_full_candidates import (
    _apply_koq200_floor_wok_repair,
    _remove_reviewed_floor_wall_faces,
)
from scripts.generate_rnv_walkmesh_candidates import (
    _find_ascii_wok_keys,
    _reserialize_wok_derived_tables,
    _resource_drift,
)
from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure


def _two_face_floor() -> bytes:
    return WOKData(
        name="fixture",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 4, -1, -1, 3, 7, -1, -1),
            WOKFace(0, 2, 3, 4, 2, -1, -1, -1, 7, -1),
        ],
        adjacency_domain_count=2,
        relative_hook1=(1.0, 2.0, 3.0),
        relative_hook2=(4.0, 5.0, 6.0),
        absolute_hook1=(7.0, 8.0, 9.0),
        absolute_hook2=(10.0, 11.0, 12.0),
        position=(13.0, 14.0, 15.0),
    ).to_bytes()


def _floor_with_reviewed_wall_strip() -> bytes:
    return WOKData(
        name="fixture",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (2.0, 1.0, 3.0),
            (2.0, 0.0, 3.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (3.0, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 1, -1, -1, 1, 7, -1, -1),
            WOKFace(0, 2, 3, 1, 0, -1, -1, -1, 9, -1),
            WOKFace(4, 5, 6, 1, -1, -1, 3),
            WOKFace(4, 6, 7, 1, 2, -1, -1),
            # A horizontal NON_WALK floor margin is deliberately retained;
            # the reviewed repair must not blanket-delete NON_WALK geometry.
            WOKFace(8, 9, 10, 7),
        ],
        adjacency_domain_count=4,
        relative_hook1=(1.0, 2.0, 3.0),
        relative_hook2=(4.0, 5.0, 6.0),
        absolute_hook1=(7.0, 8.0, 9.0),
        absolute_hook2=(10.0, 11.0, 12.0),
        position=(13.0, 14.0, 15.0),
    ).to_bytes()


def test_derived_table_rebuild_preserves_indexed_semantics_and_header_vectors() -> None:
    source = _two_face_floor()
    candidate, report = _reserialize_wok_derived_tables(source, resref="fixture")

    assert candidate
    assert report["candidate_raw_structure_valid"] is True
    assert report["header_vectors_match"] is True
    assert all(report["fingerprint_match"].values())
    assert report["candidate_perimeters"]["open_loop_count"] == 0
    assert report["candidate_aabb"]["complete_one_leaf_per_face"] is True


def test_reviewed_wall_strip_removal_preserves_floor_indices_transitions_and_nonwalk_margin() -> None:
    source = _floor_with_reviewed_wall_strip()
    candidate, report = _remove_reviewed_floor_wall_faces(
        source,
        room="fixture",
        face_indices=(2, 3),
        min_slope_degrees=80.0,
        min_z_span=2.0,
    )

    before = WOKData.from_bytes(source)
    after = WOKData.from_bytes(candidate)
    assert after.verts == before.verts
    assert after.adjacency_domain_count == 2
    assert [(face.v1, face.v2, face.v3, face.surface) for face in after.faces] == [
        (0, 1, 2, 1),
        (0, 2, 3, 1),
        (8, 9, 10, 7),
    ]
    assert [(after.faces[0].trans1, after.faces[1].trans2)] == [(7, 9)]
    assert report["removed_face_count"] == 2
    assert report["before"]["face_count"] == 5
    assert report["after"]["face_count"] == 3
    assert report["transition_semantics_preserved"] is True
    assert {row["source_face_index"] for row in report["removed_faces"]} == {2, 3}
    assert all(row["surface_before"] == 1 for row in report["removed_faces"])
    assert all(row["surface_after"] is None for row in report["removed_faces"])
    assert all(row["slope_degrees"] == pytest.approx(90.0) for row in report["removed_faces"])
    assert all(row["z_span"] == pytest.approx(3.0) for row in report["removed_faces"])

    fingerprint, validation = inspect_raw_wok_structure("fixture", candidate)
    assert not validation.issues
    assert fingerprint.aabb_missing_face_count == 0
    assert fingerprint.aabb_covered_face_count == 3
    assert fingerprint.perimeter_count == fingerprint.closed_perimeter_count == 1
    assert fingerprint.transition_count == 2


def test_reviewed_wall_strip_removal_fails_closed_for_ambiguous_floor_face() -> None:
    with pytest.raises(ValueError, match="slope gate"):
        _remove_reviewed_floor_wall_faces(
            _floor_with_reviewed_wall_strip(),
            room="fixture",
            face_indices=(0,),
            min_slope_degrees=80.0,
            min_z_span=2.0,
        )


def test_koq200_floor_repair_does_not_mutate_historical_rnvcanyon_build() -> None:
    source = _floor_with_reviewed_wall_strip()
    candidate, report = _apply_koq200_floor_wok_repair(
        source,
        module="rnvcanyon",
        room="koq200_01d",
    )
    assert candidate == source
    assert report is None


def test_ascii_wok_detection_requires_ascii_suffix_node_text_and_non_bwm() -> None:
    resources = {
        ("koq200_01a", ResourceType.WOK): b"BWM V1.0" + b"\0" * 128,
        ("koq200_01a-ascii", ResourceType.WOK): b"node trimesh walkmesh\nendnode\n",
        ("not_ascii_name", ResourceType.WOK): b"node trimesh walkmesh\n",
        ("koq200_01b-ascii", ResourceType.WOK): b"BWM V1.0" + b"\0" * 128,
        ("koq200_01c-ascii", ResourceType.MDL): b"node trimesh geometry\n",
    }

    assert _find_ascii_wok_keys(resources) == [("koq200_01a-ascii", ResourceType.WOK)]


def test_resource_drift_reports_only_content_change_and_removal() -> None:
    keep = ("keep", ResourceType.WOK)
    change = ("change", ResourceType.WOK)
    remove = ("remove", ResourceType.WOK)
    before = {keep: b"same", change: b"old", remove: b"gone"}
    after = {keep: b"same", change: b"new"}

    rows = _resource_drift(before, after)

    assert [(row["resource"], row["change"]) for row in rows] == [
        ("change.wok", "content_changed"),
        ("remove.wok", "removed"),
    ]
