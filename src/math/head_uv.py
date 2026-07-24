"""Deterministic UV-space contracts for Custom Head Builder.

UV coordinates are never transformed with object-space alignment.  This
module owns the explicit, independently testable decision about whether V is
flipped for serialized MDX data and for editor preview.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Sequence


Vec2 = tuple[float, float]
Face = tuple[int, int, int]

UV_TRANSFORM_IDENTITY = "identity"
UV_TRANSFORM_FLIP_V = "flip_v"
UV_TRANSFORMS = frozenset({UV_TRANSFORM_IDENTITY, UV_TRANSFORM_FLIP_V})
_EPSILON = 1.0e-10


class HeadUvError(ValueError):
    """Raised when a UV decision is incomplete or structurally invalid."""


@dataclass(frozen=True, slots=True)
class HeadUvAudit:
    vertex_count: int
    face_count: int
    finite: bool
    missing_uv_count: int
    outside_unit_square_count: int
    degenerate_face_count: int
    inconsistent_winding_face_count: int
    overlapping_face_pair_count: int
    uv_sha256: str

    @property
    def accepted(self) -> bool:
        return (
            self.vertex_count > 0
            and self.face_count > 0
            and self.finite
            and self.missing_uv_count == 0
            and self.outside_unit_square_count == 0
            and self.degenerate_face_count == 0
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        rows: list[str] = []
        if self.inconsistent_winding_face_count:
            rows.append(
                "UV winding is inconsistent across "
                f"{self.inconsistent_winding_face_count} faces"
            )
        if self.overlapping_face_pair_count:
            rows.append(
                "UV triangles overlap in "
                f"{self.overlapping_face_pair_count} face pairs; this is valid "
                "for intentional mirroring but blocks unique-surface baking"
            )
        return tuple(rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_uv_audit",
            "version": 1,
            "accepted": self.accepted,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "finite": self.finite,
            "missing_uv_count": self.missing_uv_count,
            "outside_unit_square_count": self.outside_unit_square_count,
            "degenerate_face_count": self.degenerate_face_count,
            "inconsistent_winding_face_count": (
                self.inconsistent_winding_face_count
            ),
            "overlapping_face_pair_count": self.overlapping_face_pair_count,
            "warnings": list(self.warnings),
            "uv_sha256": self.uv_sha256,
        }


@dataclass(frozen=True, slots=True)
class HeadUvOrientationContract:
    source_v_flip_applied: bool
    serialized_transform: str
    preview_transform: str
    imported_uv_sha256: str
    serialized_uv_sha256: str
    preview_uv_sha256: str
    audit: HeadUvAudit

    @property
    def preview_matches_serialized(self) -> bool:
        return self.preview_uv_sha256 == self.serialized_uv_sha256

    @property
    def accepted(self) -> bool:
        return self.audit.accepted and self.preview_matches_serialized

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_uv_orientation",
            "version": 1,
            "accepted": self.accepted,
            "source_v_flip_applied": self.source_v_flip_applied,
            "serialized_transform": self.serialized_transform,
            "preview_transform": self.preview_transform,
            "preview_matches_serialized": self.preview_matches_serialized,
            "imported_uv_sha256": self.imported_uv_sha256,
            "serialized_uv_sha256": self.serialized_uv_sha256,
            "preview_uv_sha256": self.preview_uv_sha256,
            "audit": self.audit.to_dict(),
        }


def build_head_uv_orientation_contract(
    uvs: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    *,
    source_v_flip_applied: bool,
    serialized_transform: str,
    preview_transform: str,
) -> HeadUvOrientationContract:
    """Audit imported UVs and fingerprint both explicit orientation choices."""

    imported = _coerce_uvs(uvs)
    triangles = _coerce_faces(faces)
    imported_audit = audit_head_uvs(imported, triangles)
    serialized_mode = _coerce_transform(serialized_transform)
    preview_mode = _coerce_transform(preview_transform)
    serialized = apply_head_uv_transform(imported, serialized_mode)
    preview = apply_head_uv_transform(imported, preview_mode)
    return HeadUvOrientationContract(
        source_v_flip_applied=bool(source_v_flip_applied),
        serialized_transform=serialized_mode,
        preview_transform=preview_mode,
        imported_uv_sha256=head_uvs_sha256(imported),
        serialized_uv_sha256=head_uvs_sha256(serialized),
        preview_uv_sha256=head_uvs_sha256(preview),
        audit=imported_audit,
    )


def audit_head_uvs(
    uvs: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    *,
    expected_vertex_count: int | None = None,
) -> HeadUvAudit:
    """Validate one per-vertex UV channel in UV space."""

    rows = _coerce_uvs(uvs, allow_nonfinite=True)
    triangles = _coerce_faces(faces)
    expected = len(rows) if expected_vertex_count is None else int(
        expected_vertex_count
    )
    missing = max(0, expected - len(rows))
    finite = all(math.isfinite(value) for uv in rows for value in uv)
    outside = sum(
        1
        for u, v in rows
        if (
            not math.isfinite(u)
            or not math.isfinite(v)
            or u < -_EPSILON
            or u > 1.0 + _EPSILON
            or v < -_EPSILON
            or v > 1.0 + _EPSILON
        )
    )
    signed_areas: list[float] = []
    polygons: list[tuple[Vec2, Vec2, Vec2]] = []
    degenerate = 0
    for face in triangles:
        if any(index < 0 or index >= len(rows) for index in face):
            degenerate += 1
            continue
        polygon = tuple(rows[index] for index in face)
        area = _signed_area(polygon)
        signed_areas.append(area)
        polygons.append(polygon)
        if not math.isfinite(area) or abs(area) <= _EPSILON:
            degenerate += 1
    positive = sum(1 for value in signed_areas if value > _EPSILON)
    negative = sum(1 for value in signed_areas if value < -_EPSILON)
    inconsistent = min(positive, negative) if positive and negative else 0
    overlap_count = 0
    for left in range(len(polygons)):
        if abs(_signed_area(polygons[left])) <= _EPSILON:
            continue
        for right in range(left + 1, len(polygons)):
            if abs(_signed_area(polygons[right])) <= _EPSILON:
                continue
            if _triangle_overlap_area(
                polygons[left],
                polygons[right],
            ) > _EPSILON:
                overlap_count += 1
    return HeadUvAudit(
        vertex_count=len(rows),
        face_count=len(triangles),
        finite=finite,
        missing_uv_count=missing,
        outside_unit_square_count=outside,
        degenerate_face_count=degenerate,
        inconsistent_winding_face_count=inconsistent,
        overlapping_face_pair_count=overlap_count,
        uv_sha256=head_uvs_sha256(rows),
    )


def apply_head_uv_transform(
    uvs: Sequence[Sequence[float]],
    transform: str,
) -> tuple[Vec2, ...]:
    """Apply the chosen UV-space transform exactly once."""

    rows = _coerce_uvs(uvs)
    mode = _coerce_transform(transform)
    if mode == UV_TRANSFORM_IDENTITY:
        return rows
    return tuple((u, 1.0 - v) for u, v in rows)


def head_uvs_sha256(uvs: Iterable[Sequence[float]]) -> str:
    rows = [
        [_stable_float(float(uv[0])), _stable_float(float(uv[1]))]
        for uv in uvs
    ]
    encoded = json.dumps(
        rows,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coerce_transform(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode not in UV_TRANSFORMS:
        raise HeadUvError(
            "UV transform must be 'identity' or 'flip_v'"
        )
    return mode


def _coerce_uvs(
    values: Sequence[Sequence[float]],
    *,
    allow_nonfinite: bool = False,
) -> tuple[Vec2, ...]:
    rows: list[Vec2] = []
    for index, value in enumerate(values):
        if len(value) < 2:
            raise HeadUvError(f"UV {index} has fewer than two components")
        row = (float(value[0]), float(value[1]))
        if not allow_nonfinite and not all(math.isfinite(item) for item in row):
            raise HeadUvError(f"UV {index} is not finite")
        rows.append(row)
    return tuple(rows)


def _coerce_faces(values: Sequence[Sequence[int]]) -> tuple[Face, ...]:
    rows: list[Face] = []
    for index, value in enumerate(values):
        if len(value) != 3:
            raise HeadUvError(f"Face {index} is not a triangle")
        rows.append(tuple(int(item) for item in value))
    return tuple(rows)


def _signed_area(polygon: Sequence[Vec2]) -> float:
    return 0.5 * sum(
        polygon[index][0] * polygon[(index + 1) % len(polygon)][1]
        - polygon[(index + 1) % len(polygon)][0] * polygon[index][1]
        for index in range(len(polygon))
    )


def _triangle_overlap_area(
    left: Sequence[Vec2],
    right: Sequence[Vec2],
) -> float:
    subject = list(left)
    clip = list(right)
    if _signed_area(clip) < 0.0:
        clip.reverse()
    output = subject
    for index, edge_start in enumerate(clip):
        edge_end = clip[(index + 1) % len(clip)]
        input_rows = output
        output = []
        if not input_rows:
            break
        previous = input_rows[-1]
        for current in input_rows:
            current_inside = _inside(current, edge_start, edge_end)
            previous_inside = _inside(previous, edge_start, edge_end)
            if current_inside:
                if not previous_inside:
                    output.append(
                        _line_intersection(
                            previous,
                            current,
                            edge_start,
                            edge_end,
                        )
                    )
                output.append(current)
            elif previous_inside:
                output.append(
                    _line_intersection(
                        previous,
                        current,
                        edge_start,
                        edge_end,
                    )
                )
            previous = current
    return abs(_signed_area(output)) if len(output) >= 3 else 0.0


def _inside(point: Vec2, edge_start: Vec2, edge_end: Vec2) -> bool:
    return (
        (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1])
        - (edge_end[1] - edge_start[1]) * (point[0] - edge_start[0])
    ) >= -_EPSILON


def _line_intersection(
    start: Vec2,
    end: Vec2,
    clip_start: Vec2,
    clip_end: Vec2,
) -> Vec2:
    delta = (end[0] - start[0], end[1] - start[1])
    clip_delta = (
        clip_end[0] - clip_start[0],
        clip_end[1] - clip_start[1],
    )
    denominator = delta[0] * clip_delta[1] - delta[1] * clip_delta[0]
    if abs(denominator) <= _EPSILON:
        return end
    offset = (clip_start[0] - start[0], clip_start[1] - start[1])
    ratio = (
        offset[0] * clip_delta[1] - offset[1] * clip_delta[0]
    ) / denominator
    return (
        start[0] + ratio * delta[0],
        start[1] + ratio * delta[1],
    )


def _stable_float(value: float) -> float:
    if not math.isfinite(value):
        raise HeadUvError("UV hashes require finite values")
    return 0.0 if abs(value) < 1.0e-15 else round(value, 12)


__all__ = [
    "HeadUvAudit",
    "HeadUvError",
    "HeadUvOrientationContract",
    "UV_TRANSFORM_FLIP_V",
    "UV_TRANSFORM_IDENTITY",
    "UV_TRANSFORMS",
    "apply_head_uv_transform",
    "audit_head_uvs",
    "build_head_uv_orientation_contract",
    "head_uvs_sha256",
]
