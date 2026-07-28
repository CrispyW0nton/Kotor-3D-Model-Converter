from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import pytest

from src.io.head_art_importer import (
    HeadArtImportError,
    import_head_art,
    repair_head_art_nonmanifold_overlays,
    validate_head_art_document,
)


def _write_open_quad(path: Path) -> None:
    path.write_text(
        "\n".join(
            (
                "# units: meters",
                "o custom_head",
                "v 0 0 0",
                "v 1 0 0",
                "v 1 1 0",
                "v 0 1 0",
                "vt 0 0",
                "vt 1 0",
                "vt 1 1",
                "vt 0 1",
                "usemtl face",
                "f 1/1 2/2 3/3 4/4",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def test_obj_import_is_deterministic_blob_free_and_topology_audited(
    tmp_path: Path,
):
    source = tmp_path / "face.obj"
    _write_open_quad(source)

    first, first_report = import_head_art(
        source,
        source_axis="blender_xyz_to_kotor_xz_minus_y",
        unit_scale_to_kotor=2.0,
    )
    second, second_report = import_head_art(
        source,
        source_axis="blender_xyz_to_kotor_xz_minus_y",
        unit_scale_to_kotor=2.0,
    )

    assert first_report.accepted
    assert second_report.accepted
    assert first.structural_sha256 == second.structural_sha256
    assert first.source_sha256 == second.source_sha256
    assert first.vertex_count == 4
    assert first.face_count == 2
    assert first.parts[0].vertices[2] == pytest.approx((2.0, 0.0, -2.0))
    assert first.parts[0].authored_uvs
    assert not first.parts[0].authored_normals
    assert first.parts[0].topology.border_edge_count == 4
    assert any(
        issue.check_id == "head.art.open_boundaries"
        for issue in first_report.warnings
    )

    persisted = first.project_facts()
    encoded = json.dumps(persisted)
    assert '"vertices"' not in encoded
    assert '"faces"' not in encoded
    assert '"uvs"' not in encoded
    assert persisted["source_path"] == str(source.resolve())
    assert persisted["parts"][0]["vertex_id_basis"] == (
        "obj_compacted_position_uv_normal_index"
    )


def test_obj_non_manifold_topology_is_a_blocking_import_result(
    tmp_path: Path,
):
    source = tmp_path / "nonmanifold.obj"
    source.write_text(
        "\n".join(
            (
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "v 0 -1 0",
                "v 0 0 1",
                "f 1 2 3",
                "f 2 1 4",
                "f 1 2 5",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    document, report = import_head_art(source)

    assert not report.accepted
    assert document.parts[0].topology.non_manifold_edge_count == 1
    assert any(
        issue.check_id == "head.art.non_manifold"
        for issue in report.errors
    )


def test_obj_import_compacts_redundant_maya_normal_indices_by_exact_values(
    tmp_path: Path,
) -> None:
    source = tmp_path / "maya_corner_normals.obj"
    source.write_text(
        "\n".join(
            (
                "# This file uses centimeters as units for non-parametric coordinates.",
                "v 0 0 0",
                "v 1 0 0",
                "v 1 1 0",
                "v 0 1 0",
                "vt 0 0",
                "vt 1 0",
                "vt 1 1",
                "vt 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "vn 0 0 1",
                "f 1/1/1 2/2/2 3/3/3",
                "f 1/1/4 3/3/5 4/4/6",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    document, report = import_head_art(source, flip_v=False)

    assert report.accepted
    assert document.vertex_count == 4
    assert document.face_count == 2
    assert len(document.parts[0].uvs) == 4
    assert len(document.parts[0].normals) == 4
    assert document.parts[0].faces == ((0, 1, 2), (0, 2, 3))


def test_nonmanifold_overlay_repair_is_deterministic_and_source_preserving(
    tmp_path: Path,
):
    source = tmp_path / "overlays.obj"
    source.write_text(
        "\n".join(
            (
                "o overlays",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 -1 0",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 0 1",
                "f 1 2 3",
                "f 4 5 6",
                "f 7 8 9",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    source_bytes = source.read_bytes()

    document, initial = import_head_art(source, flip_v=False)
    repaired, repair = repair_head_art_nonmanifold_overlays(document)
    final = validate_head_art_document(repaired)

    assert not initial.accepted
    assert repair.accepted
    assert repair.changed
    assert repair.removed_face_indices_by_part[0][1] == (2,)
    assert repaired.face_count == 2
    assert final.accepted
    assert source.read_bytes() == source_bytes


@dataclass
class _Node:
    name: str = "face"
    texture: str = "headtex"
    vertices: list[tuple[float, float, float]] = field(
        default_factory=lambda: [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
    )
    faces: list[tuple[int, int, int]] = field(
        default_factory=lambda: [(0, 1, 2)]
    )
    uvs: list[tuple[float, float]] = field(
        default_factory=lambda: [(0, 0), (1, 0), (0, 1)]
    )
    normals: list[tuple[float, float, float]] = field(
        default_factory=lambda: [(0, 0, 1)] * 3
    )


class _Model:
    metadata = {
        "external_import": {
            "axis_conversion": "blender_xyz_to_kotor_xz_minus_y",
        }
    }

    def all_nodes(self):
        return [_Node()]


def test_fbx_import_uses_declared_axis_and_preserves_source_indices(
    tmp_path: Path,
):
    source = tmp_path / "face.fbx"
    source.write_bytes(b"fixture")
    calls: list[tuple[Path, str]] = []

    def loader(path: Path, *, axis_conversion: str):
        calls.append((path, axis_conversion))
        model = _Model()
        model.all_nodes()[0]
        node = _Node()
        setattr(node, "_gr_source_vertex_indices", [7, 8, 9])
        model.all_nodes = lambda: [node]
        return model

    document, report = import_head_art(
        source,
        unit_scale_to_kotor=0.5,
        fbx_loader=loader,
    )

    assert report.accepted
    assert calls == [
        (
            source.resolve(),
            "blender_xyz_to_kotor_xz_minus_y",
        )
    ]
    assert document.source_axis == "blender_xyz_to_kotor_xz_minus_y"
    assert document.parts[0].vertices[1] == pytest.approx((0.5, 0.0, 0.0))
    assert document.parts[0].source_vertex_indices == (7, 8, 9)
    assert document.parts[0].vertex_id_basis == "fbx_source_control_point_index"


def test_import_rejects_unsupported_or_empty_sources(tmp_path: Path):
    unsupported = tmp_path / "face.gltf"
    unsupported.write_text("{}", encoding="utf-8")
    with pytest.raises(HeadArtImportError, match="OBJ or FBX"):
        import_head_art(unsupported)

    empty = tmp_path / "face.obj"
    empty.write_bytes(b"")
    with pytest.raises(HeadArtImportError, match="empty"):
        import_head_art(empty)
