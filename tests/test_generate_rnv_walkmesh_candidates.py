from __future__ import annotations

from pykotor.resource.type import ResourceType

from core.modules.module_format import WOKData, WOKFace
from scripts.generate_rnv_walkmesh_candidates import (
    _find_ascii_wok_keys,
    _reserialize_wok_derived_tables,
    _resource_drift,
)


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


def test_derived_table_rebuild_preserves_indexed_semantics_and_header_vectors() -> None:
    source = _two_face_floor()
    candidate, report = _reserialize_wok_derived_tables(source, resref="fixture")

    assert candidate
    assert report["candidate_raw_structure_valid"] is True
    assert report["header_vectors_match"] is True
    assert all(report["fingerprint_match"].values())
    assert report["candidate_perimeters"]["open_loop_count"] == 0
    assert report["candidate_aabb"]["complete_one_leaf_per_face"] is True


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
