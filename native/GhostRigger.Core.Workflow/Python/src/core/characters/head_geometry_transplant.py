"""Donor-preserving rendered-payload transplant for Custom Head Builder.

Core Workflow owns the multi-owner transaction:

* clone an accepted native modular-head donor;
* keep its DAG, node identities, hooks, raw bounds, palette, and bind rows;
* merge selected custom-art parts into the donor's sole mutable ``head`` skin;
* transfer weights through Core Math or explicitly rigid-bind selected parts;
* retain tight editor bounds separately from the retail donor envelope; and
* prove the result with the immutable donor structural diff.

The project stores compact settings, hashes, ranges, and sparse manual edits.
Runtime mesh/weight arrays remain on the candidate model and are regenerated
from source art after reopen.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from src.core.characters.head_donor_snapshot import (
    HeadDonorSnapshot,
    compare_head_donor_contract,
)
from src.io.head_art_importer import HeadArtDocument
from src.math.head_alignment import HeadAlignmentResult, transform_point, transform_vector
from src.math.head_skin_transfer import (
    HeadSkinTransferReport,
    HeadSkinTransferResult,
    HeadSkinWeightRow,
    head_skin_rows_sha256,
    normalize_head_skin_row,
    transfer_head_skin_weights,
)


PART_MODE_SURFACE = "surface_transfer"
PART_MODE_RIGID = "rigid_head_g"
PART_MODE_EXCLUDE = "exclude"
PART_MODES = frozenset(
    {PART_MODE_SURFACE, PART_MODE_RIGID, PART_MODE_EXCLUDE}
)


class HeadGeometryTransplantError(RuntimeError):
    """Raised when a transplant would violate the accepted donor contract."""


@dataclass(frozen=True, slots=True)
class HeadTransplantedPart:
    part_id: str
    source_name: str
    mode: str
    first_vertex: int
    vertex_count: int
    first_face: int
    face_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_id": self.part_id,
            "source_name": self.source_name,
            "mode": self.mode,
            "first_vertex": self.first_vertex,
            "vertex_count": self.vertex_count,
            "first_face": self.first_face,
            "face_count": self.face_count,
        }


@dataclass(frozen=True, slots=True)
class HeadGeometryTransplantReport:
    mutable_node_ordinal: int
    mutable_node_name: str
    donor_vertex_count: int
    donor_face_count: int
    output_vertex_count: int
    output_face_count: int
    parts: tuple[HeadTransplantedPart, ...]
    excluded_part_ids: tuple[str, ...]
    neck_vertex_count: int
    palette_size: int
    palette_names: tuple[str, ...]
    donor_skin_contract_sha256: str
    geometry_sha256: str
    baseline_weight_rows_sha256: str
    final_weight_rows_sha256: str
    payload_sha256: str
    preview_bb_min: tuple[float, float, float]
    preview_bb_max: tuple[float, float, float]
    preview_radius: float
    transfer: HeadSkinTransferReport
    manual_edit_count: int = 0
    blocking_difference_paths: tuple[str, ...] = ()
    allowed_difference_paths: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            self.output_vertex_count > 0
            and self.output_face_count > 0
            and self.transfer.accepted
            and not self.blocking_difference_paths
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_geometry_transplant",
            "version": 1,
            "accepted": self.accepted,
            "mutable_node_ordinal": self.mutable_node_ordinal,
            "mutable_node_name": self.mutable_node_name,
            "donor_vertex_count": self.donor_vertex_count,
            "donor_face_count": self.donor_face_count,
            "output_vertex_count": self.output_vertex_count,
            "output_face_count": self.output_face_count,
            "parts": [row.to_dict() for row in self.parts],
            "excluded_part_ids": list(self.excluded_part_ids),
            "neck_vertex_count": self.neck_vertex_count,
            "palette_size": self.palette_size,
            "palette_names": list(self.palette_names),
            "donor_skin_contract_sha256": self.donor_skin_contract_sha256,
            "geometry_sha256": self.geometry_sha256,
            "baseline_weight_rows_sha256": self.baseline_weight_rows_sha256,
            "final_weight_rows_sha256": self.final_weight_rows_sha256,
            "payload_sha256": self.payload_sha256,
            "preview_bb_min": list(self.preview_bb_min),
            "preview_bb_max": list(self.preview_bb_max),
            "preview_radius": self.preview_radius,
            "transfer": self.transfer.to_dict(),
            "manual_edit_count": self.manual_edit_count,
            "blocking_difference_paths": list(
                self.blocking_difference_paths
            ),
            "allowed_difference_paths": list(
                self.allowed_difference_paths
            ),
        }


@dataclass(frozen=True, slots=True)
class HeadGeometryTransplantResult:
    model: Any = field(repr=False, compare=False)
    vertex_ids: tuple[str, ...]
    baseline_rows: tuple[HeadSkinWeightRow, ...]
    rows: tuple[HeadSkinWeightRow, ...]
    samples: tuple[Any, ...] = field(repr=False, compare=False)
    report: HeadGeometryTransplantReport


def transplant_head_geometry_and_skin(
    *,
    donor_model: Any,
    donor_snapshot: HeadDonorSnapshot,
    art_document: HeadArtDocument,
    alignment: HeadAlignmentResult,
    part_modes: Mapping[str, str] | None,
    neck_vertex_ids: Sequence[str],
    maximum_surface_distance: float,
    allow_distance_fallback: bool = True,
    rigid_fallback_bone: str = "head_g",
    minimum_neck_weight: float = 0.05,
) -> HeadGeometryTransplantResult:
    """Clone a pristine donor and replace only its selected skin payload."""

    if donor_model is None:
        raise HeadGeometryTransplantError("No native donor model is loaded")
    if not isinstance(donor_snapshot, HeadDonorSnapshot):
        raise TypeError("donor_snapshot must be HeadDonorSnapshot")
    if not isinstance(art_document, HeadArtDocument):
        raise TypeError("art_document must be HeadArtDocument")
    if not isinstance(alignment, HeadAlignmentResult):
        raise TypeError("alignment must be HeadAlignmentResult")
    initial_diff = compare_head_donor_contract(donor_snapshot, donor_model)
    if initial_diff.blocking or initial_diff.allowed_payload_changes:
        raise HeadGeometryTransplantError(
            "Geometry transplant requires the pristine accepted donor; "
            "rehydrate it before rebuilding the payload"
        )
    mutable = tuple(donor_snapshot.mutable_payload_node_ordinals)
    if len(mutable) != 1:
        raise HeadGeometryTransplantError(
            "Head transplant requires exactly one mutable native head skin"
        )
    mutable_ordinal = mutable[0]
    donor_nodes = _model_nodes(donor_model)
    if mutable_ordinal < 0 or mutable_ordinal >= len(donor_nodes):
        raise HeadGeometryTransplantError(
            "The donor mutable skin ordinal is no longer present"
        )
    donor_node = donor_nodes[mutable_ordinal]
    _require_identity_payload_transform(donor_node)
    donor_skin = next(
        (
            row
            for row in donor_snapshot.skins
            if row.node_ordinal == mutable_ordinal
        ),
        None,
    )
    if donor_skin is None:
        raise HeadGeometryTransplantError(
            "The mutable donor node has no immutable skin contract"
        )
    palette = tuple(donor_skin.bone_palette)
    fallback_slot = _palette_slot(palette, rigid_fallback_bone)
    neck_slot = _palette_slot(
        palette,
        donor_snapshot.attachment_target_name,
    )

    modes = {
        part.part_id: PART_MODE_SURFACE
        for part in art_document.parts
    }
    for part_id, raw_mode in dict(part_modes or {}).items():
        if part_id not in modes:
            raise HeadGeometryTransplantError(
                f"Unknown custom-art part: {part_id}"
            )
        mode = str(raw_mode or "").strip().lower()
        if mode not in PART_MODES:
            raise HeadGeometryTransplantError(
                f"Unsupported part mode {raw_mode!r} for {part_id}"
            )
        modes[part_id] = mode

    (
        vertices,
        faces,
        normals,
        uvs,
        vertex_ids,
        rigid_indices,
        included_parts,
        excluded_parts,
        border_vertex_ids,
    ) = _merge_art_parts(
        art_document,
        alignment,
        modes,
    )
    if not vertices or not faces:
        raise HeadGeometryTransplantError(
            "At least one custom-art mesh part must remain in the head payload"
        )
    neck_ids = tuple(dict.fromkeys(str(value) for value in neck_vertex_ids))
    if len(neck_ids) < 3:
        raise HeadGeometryTransplantError(
            "Select at least three ordered neck-seam vertices"
        )
    unknown_neck = sorted(set(neck_ids) - set(vertex_ids))
    if unknown_neck:
        raise HeadGeometryTransplantError(
            f"Unknown neck-seam vertex identity: {unknown_neck[0]}"
        )
    non_boundary = sorted(set(neck_ids) - border_vertex_ids)
    if non_boundary:
        raise HeadGeometryTransplantError(
            "Neck seam selections must be vertices on a geometric boundary; "
            f"{non_boundary[0]} is not"
        )
    vertex_index_by_id = {
        vertex_id: index for index, vertex_id in enumerate(vertex_ids)
    }
    neck_indices = tuple(vertex_index_by_id[value] for value in neck_ids)

    donor_weight_rows = [
        list(getattr(row, "influences", ()) or ())
        for row in list(getattr(donor_node, "skin_data", ()) or ())
    ]
    transfer = transfer_head_skin_weights(
        donor_vertices=list(getattr(donor_node, "vertices", ()) or ()),
        donor_faces=list(getattr(donor_node, "faces", ()) or ()),
        donor_weight_rows=donor_weight_rows,
        target_vertices=vertices,
        palette_size=len(palette),
        rigid_fallback_slot=fallback_slot,
        rigid_target_indices=rigid_indices,
        maximum_surface_distance=maximum_surface_distance,
        allow_distance_fallback=allow_distance_fallback,
        neck_target_indices=neck_indices,
        neck_palette_slot=neck_slot,
        minimum_neck_weight=minimum_neck_weight,
    )
    candidate = deepcopy(donor_model)
    candidate_nodes = _model_nodes(candidate)
    payload_node = candidate_nodes[mutable_ordinal]
    raw_node_bounds = (
        tuple(getattr(payload_node, "bb_min", ())),
        tuple(getattr(payload_node, "bb_max", ())),
        float(getattr(payload_node, "radius", 0.0)),
    )
    _apply_render_payload(
        payload_node,
        vertices=vertices,
        faces=faces,
        normals=normals,
        uvs=uvs,
        rows=transfer.rows,
    )
    if (
        tuple(getattr(payload_node, "bb_min", ())),
        tuple(getattr(payload_node, "bb_max", ())),
        float(getattr(payload_node, "radius", 0.0)),
    ) != raw_node_bounds:
        raise HeadGeometryTransplantError(
            "The transplant changed the donor's raw retail node bounds"
        )
    preview_min, preview_max, preview_radius = _preview_bounds(vertices)
    setattr(candidate, "_gr_render_bounds", (preview_min, preview_max))
    setattr(candidate, "_gr_render_radius", preview_radius)
    setattr(payload_node, "_gr_head_builder_payload_bounds", (preview_min, preview_max))
    setattr(payload_node, "_gr_head_builder_vertex_ids", vertex_ids)
    metadata = getattr(candidate, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(candidate, "metadata", metadata)

    geometry_sha = _geometry_sha256(
        vertices=vertices,
        faces=faces,
        normals=normals,
        uvs=uvs,
        vertex_ids=vertex_ids,
    )
    donor_contract_sha = _hash_json(donor_skin.structural_dict())
    final_weight_sha = transfer.report.weight_rows_sha256
    diff = compare_head_donor_contract(donor_snapshot, candidate)
    blocking_paths = tuple(
        row.path for row in diff.blocking
    )
    if blocking_paths:
        raise HeadGeometryTransplantError(
            "The candidate violated the immutable donor contract: "
            + ", ".join(blocking_paths[:8])
        )
    report = HeadGeometryTransplantReport(
        mutable_node_ordinal=mutable_ordinal,
        mutable_node_name=str(getattr(payload_node, "name", "") or ""),
        donor_vertex_count=len(
            list(getattr(donor_node, "vertices", ()) or ())
        ),
        donor_face_count=len(
            list(getattr(donor_node, "faces", ()) or ())
        ),
        output_vertex_count=len(vertices),
        output_face_count=len(faces),
        parts=included_parts,
        excluded_part_ids=excluded_parts,
        neck_vertex_count=len(neck_indices),
        palette_size=len(palette),
        palette_names=palette,
        donor_skin_contract_sha256=donor_contract_sha,
        geometry_sha256=geometry_sha,
        baseline_weight_rows_sha256=final_weight_sha,
        final_weight_rows_sha256=final_weight_sha,
        payload_sha256=_payload_sha256(geometry_sha, final_weight_sha),
        preview_bb_min=preview_min,
        preview_bb_max=preview_max,
        preview_radius=preview_radius,
        transfer=transfer.report,
        allowed_difference_paths=tuple(
            row.path for row in diff.allowed_payload_changes
        ),
    )
    metadata["head_builder_transplant"] = report.to_dict()
    return HeadGeometryTransplantResult(
        model=candidate,
        vertex_ids=vertex_ids,
        baseline_rows=transfer.rows,
        rows=transfer.rows,
        samples=transfer.samples,
        report=report,
    )


def apply_head_skin_weight_edits(
    result: HeadGeometryTransplantResult,
    *,
    donor_snapshot: HeadDonorSnapshot,
    edits: Mapping[str, Mapping[str, float]],
) -> HeadGeometryTransplantResult:
    """Rebuild sparse manual edits over the deterministic transfer baseline."""

    if not isinstance(result, HeadGeometryTransplantResult):
        raise TypeError("result must be HeadGeometryTransplantResult")
    mutable_ordinal = result.report.mutable_node_ordinal
    skin_contract = next(
        (
            row
            for row in donor_snapshot.skins
            if row.node_ordinal == mutable_ordinal
        ),
        None,
    )
    if skin_contract is None:
        raise HeadGeometryTransplantError(
            "The donor skin contract is unavailable for weight editing"
        )
    palette = tuple(skin_contract.bone_palette)
    palette_by_name = {
        name.casefold(): index
        for index, name in enumerate(palette)
        if name
    }
    vertex_by_id = {
        vertex_id: index
        for index, vertex_id in enumerate(result.vertex_ids)
    }
    rows = list(result.baseline_rows)
    for vertex_id in sorted(edits):
        vertex_index = vertex_by_id.get(str(vertex_id))
        if vertex_index is None:
            raise HeadGeometryTransplantError(
                f"Unknown transplanted vertex identity: {vertex_id}"
            )
        raw_weights = dict(edits[vertex_id] or {})
        if not raw_weights:
            raise HeadGeometryTransplantError(
                f"Manual weight edit for {vertex_id} is empty"
            )
        slot_weights: dict[int, float] = {}
        for bone_name, weight in raw_weights.items():
            slot = palette_by_name.get(str(bone_name).casefold())
            if slot is None:
                raise HeadGeometryTransplantError(
                    f"Bone {bone_name!r} is not in the immutable donor palette"
                )
            slot_weights[slot] = slot_weights.get(slot, 0.0) + float(weight)
        rows[vertex_index] = normalize_head_skin_row(
            slot_weights,
            palette_size=len(palette),
            max_influences=4,
        )
    final_rows = tuple(rows)
    candidate = deepcopy(result.model)
    node = _model_nodes(candidate)[mutable_ordinal]
    _apply_skin_rows(node, final_rows)
    diff = compare_head_donor_contract(donor_snapshot, candidate)
    blocking_paths = tuple(
        row.path for row in diff.blocking
    )
    if blocking_paths:
        raise HeadGeometryTransplantError(
            "Manual weights violated the immutable donor contract: "
            + ", ".join(blocking_paths[:8])
        )
    final_sha = head_skin_rows_sha256(final_rows)
    report = replace(
        result.report,
        final_weight_rows_sha256=final_sha,
        payload_sha256=_payload_sha256(
            result.report.geometry_sha256,
            final_sha,
        ),
        manual_edit_count=len(edits),
        blocking_difference_paths=blocking_paths,
        allowed_difference_paths=tuple(
            row.path for row in diff.allowed_payload_changes
        ),
    )
    metadata = getattr(candidate, "metadata", None)
    if isinstance(metadata, dict):
        metadata["head_builder_transplant"] = report.to_dict()
    return HeadGeometryTransplantResult(
        model=candidate,
        vertex_ids=result.vertex_ids,
        baseline_rows=result.baseline_rows,
        rows=final_rows,
        samples=result.samples,
        report=report,
    )


def _merge_art_parts(
    document: HeadArtDocument,
    alignment: HeadAlignmentResult,
    modes: Mapping[str, str],
) -> tuple[
    list[tuple[float, float, float]],
    list[tuple[int, int, int]],
    list[tuple[float, float, float]],
    list[tuple[float, float]],
    tuple[str, ...],
    tuple[int, ...],
    tuple[HeadTransplantedPart, ...],
    tuple[str, ...],
    set[str],
]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    vertex_ids: list[str] = []
    rigid_indices: list[int] = []
    parts: list[HeadTransplantedPart] = []
    excluded: list[str] = []
    border_vertex_ids: set[str] = set()
    for part in document.parts:
        mode = modes[part.part_id]
        if mode == PART_MODE_EXCLUDE:
            excluded.append(part.part_id)
            continue
        vertex_offset = len(vertices)
        face_offset = len(faces)
        transformed_vertices = [
            transform_point(alignment.imported_to_headhook, vertex)
            for vertex in part.vertices
        ]
        transformed_normals = [
            transform_vector(
                alignment.imported_to_headhook,
                normal,
                normalize=True,
            )
            for normal in part.normals
        ]
        if len(transformed_normals) != len(transformed_vertices):
            raise HeadGeometryTransplantError(
                f"Part {part.part_id} has no aligned per-vertex normals"
            )
        part_uvs = (
            [tuple(float(value) for value in uv) for uv in part.uvs]
            if part.uvs
            else [(0.0, 0.0)] * len(transformed_vertices)
        )
        if len(part_uvs) != len(transformed_vertices):
            raise HeadGeometryTransplantError(
                f"Part {part.part_id} has a misaligned UV channel"
            )
        local_ids = [
            f"{part.part_id}:v:{index}"
            for index in range(len(transformed_vertices))
        ]
        vertices.extend(transformed_vertices)
        normals.extend(transformed_normals)
        uvs.extend(part_uvs)
        vertex_ids.extend(local_ids)
        faces.extend(
            tuple(vertex_offset + int(value) for value in face)
            for face in part.faces
        )
        if mode == PART_MODE_RIGID:
            rigid_indices.extend(
                range(vertex_offset, vertex_offset + len(transformed_vertices))
            )
        border_vertex_ids.update(
            local_ids[index]
            for index in _border_vertex_indices(part.faces)
        )
        parts.append(
            HeadTransplantedPart(
                part_id=part.part_id,
                source_name=part.name,
                mode=mode,
                first_vertex=vertex_offset,
                vertex_count=len(transformed_vertices),
                first_face=face_offset,
                face_count=len(part.faces),
            )
        )
    return (
        vertices,
        faces,
        normals,
        uvs,
        tuple(vertex_ids),
        tuple(rigid_indices),
        tuple(parts),
        tuple(excluded),
        border_vertex_ids,
    )


def _apply_render_payload(
    node: Any,
    *,
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    normals: Sequence[Sequence[float]],
    uvs: Sequence[Sequence[float]],
    rows: Sequence[HeadSkinWeightRow],
) -> None:
    node.vertices = [tuple(float(value) for value in row) for row in vertices]
    node.faces = [tuple(int(value) for value in row) for row in faces]
    node.normals = [tuple(float(value) for value in row) for row in normals]
    node.uvs = [tuple(float(value) for value in row) for row in uvs]
    node.tangents = []
    node.uvs_lm = []
    node.uvs_2 = []
    node.uvs_3 = []
    node.face_uvs = []
    node.face_mats = [0] * len(node.faces)
    _apply_skin_rows(node, rows)


def _apply_skin_rows(
    node: Any,
    rows: Sequence[HeadSkinWeightRow],
) -> None:
    from src.core.geometry.model_data import BoneWeight, VertexSkinData

    node.skin_data = [
        VertexSkinData(
            [
                BoneWeight(
                    influence.palette_slot,
                    influence.weight,
                )
                for influence in row.influences
            ]
        )
        for row in rows
    ]
    node.bone_weights = [
        [influence.weight for influence in row.influences]
        for row in rows
    ]
    node.bone_indices = [
        [influence.palette_slot for influence in row.influences]
        for row in rows
    ]


def _require_identity_payload_transform(node: Any) -> None:
    position = tuple(
        float(value) for value in getattr(node, "position", (0, 0, 0))
    )
    rotation = tuple(
        float(value) for value in getattr(node, "rotation", (0, 0, 0, 1))
    )
    if (
        len(position) != 3
        or any(abs(value) > 1.0e-7 for value in position)
        or len(rotation) != 4
        or any(abs(value) > 1.0e-7 for value in rotation[:3])
        or abs(abs(rotation[3]) - 1.0) > 1.0e-7
    ):
        raise HeadGeometryTransplantError(
            "The selected native head skin has a non-identity local transform; "
            "its vertex-storage convention needs an explicit adapter"
        )


def _palette_slot(palette: Sequence[str], name: str) -> int:
    wanted = str(name or "").casefold()
    matches = [
        index
        for index, value in enumerate(palette)
        if str(value or "").casefold() == wanted
    ]
    if len(matches) != 1:
        raise HeadGeometryTransplantError(
            f"Donor palette must contain exactly one {name!r} slot"
        )
    return matches[0]


def _border_vertex_indices(
    faces: Sequence[Sequence[int]],
) -> set[int]:
    edges: dict[tuple[int, int], int] = {}
    for raw in faces:
        face = tuple(int(value) for value in raw)
        for index in range(len(face)):
            edge = tuple(sorted((face[index], face[(index + 1) % len(face)])))
            edges[edge] = edges.get(edge, 0) + 1
    return {
        vertex
        for edge, count in edges.items()
        if count == 1
        for vertex in edge
    }


def _preview_bounds(
    vertices: Sequence[Sequence[float]],
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    float,
]:
    minimum = tuple(
        min(float(vertex[axis]) for vertex in vertices)
        for axis in range(3)
    )
    maximum = tuple(
        max(float(vertex[axis]) for vertex in vertices)
        for axis in range(3)
    )
    center = tuple(
        (minimum[axis] + maximum[axis]) * 0.5
        for axis in range(3)
    )
    radius = max(
        math.sqrt(
            sum(
                (float(vertex[axis]) - center[axis]) ** 2
                for axis in range(3)
            )
        )
        for vertex in vertices
    )
    return minimum, maximum, radius


def _geometry_sha256(
    *,
    vertices: Sequence[Any],
    faces: Sequence[Any],
    normals: Sequence[Any],
    uvs: Sequence[Any],
    vertex_ids: Sequence[str],
) -> str:
    return _hash_json(
        {
            "vertices": vertices,
            "faces": faces,
            "normals": normals,
            "uvs": uvs,
            "vertex_ids": vertex_ids,
        }
    )


def _payload_sha256(geometry_sha256: str, weight_sha256: str) -> str:
    return hashlib.sha256(
        f"{geometry_sha256}:{weight_sha256}".encode("ascii")
    ).hexdigest()


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_nodes(model: Any) -> list[Any]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        return list(all_nodes())
    return []


__all__ = [
    "HeadGeometryTransplantError",
    "HeadGeometryTransplantReport",
    "HeadGeometryTransplantResult",
    "HeadTransplantedPart",
    "PART_MODE_EXCLUDE",
    "PART_MODE_RIGID",
    "PART_MODE_SURFACE",
    "PART_MODES",
    "apply_head_skin_weight_edits",
    "transplant_head_geometry_and_skin",
]
