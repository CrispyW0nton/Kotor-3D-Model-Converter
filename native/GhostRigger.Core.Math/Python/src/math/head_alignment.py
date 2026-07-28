"""Named-space rigid alignment for Custom Head Builder art.

The Head Builder must never treat a body ``headhook`` translation as though it
were already baked into custom geometry.  This module therefore keeps every
transform direction explicit:

``head_art_imported_object -> body_bind -> headhook_local``.

The solver is Qt-free and format-free.  It accepts authored anchor pairs plus
the body's headhook bind transform and emits proper (non-reflecting) affine
matrices suitable for project evidence and later geometry transplantation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Iterable, Sequence

import numpy as np


Vec3 = tuple[float, float, float]
Mat4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]

HEAD_ART_IMPORTED_SPACE = "head_art_imported_object"
BODY_BIND_SPACE = "body_bind"
HEADHOOK_LOCAL_SPACE = "headhook_local"


class HeadAlignmentError(ValueError):
    """Base error for an unusable alignment request."""


class HeadAlignmentDegenerateError(HeadAlignmentError):
    """Raised when the selected anchors cannot define the requested solve."""


@dataclass(frozen=True, slots=True)
class HeadAlignmentAnchor:
    """One named point correspondence in imported-art and body-bind space."""

    role: str
    source_point: Vec3
    target_point: Vec3
    weight: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", str(self.role or "").strip())
        object.__setattr__(
            self,
            "source_point",
            _vec3(self.source_point, label="source_point"),
        )
        object.__setattr__(
            self,
            "target_point",
            _vec3(self.target_point, label="target_point"),
        )
        weight = float(self.weight)
        if not math.isfinite(weight) or weight <= 0.0:
            raise HeadAlignmentError("Alignment anchor weights must be finite and positive")
        object.__setattr__(self, "weight", weight)
        if not self.role:
            raise HeadAlignmentError("Alignment anchors require a role")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "source_point": list(self.source_point),
            "target_point": list(self.target_point),
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class HeadAlignmentRequest:
    """Inputs for a head-art-to-headhook solve."""

    anchors: tuple[HeadAlignmentAnchor, ...]
    headhook_to_body: Mat4
    scale_mode: str = "fixed"
    source_space: str = HEAD_ART_IMPORTED_SPACE
    target_space: str = BODY_BIND_SPACE
    output_space: str = HEADHOOK_LOCAL_SPACE

    def __post_init__(self) -> None:
        anchors = tuple(
            row if isinstance(row, HeadAlignmentAnchor) else HeadAlignmentAnchor(**row)
            for row in self.anchors
        )
        if not anchors:
            raise HeadAlignmentError("At least one alignment anchor is required")
        roles = [row.role.casefold() for row in anchors]
        if len(roles) != len(set(roles)):
            raise HeadAlignmentError("Alignment anchor roles must be unique")
        object.__setattr__(self, "anchors", anchors)
        object.__setattr__(
            self,
            "headhook_to_body",
            _mat4(self.headhook_to_body, label="headhook_to_body"),
        )
        scale_mode = str(self.scale_mode or "fixed").strip().lower()
        if scale_mode not in {"fixed", "similarity"}:
            raise HeadAlignmentError("scale_mode must be 'fixed' or 'similarity'")
        object.__setattr__(self, "scale_mode", scale_mode)
        expected_spaces = (
            (self.source_space, HEAD_ART_IMPORTED_SPACE, "source_space"),
            (self.target_space, BODY_BIND_SPACE, "target_space"),
            (self.output_space, HEADHOOK_LOCAL_SPACE, "output_space"),
        )
        for actual, expected, label in expected_spaces:
            if str(actual) != expected:
                raise HeadAlignmentError(
                    f"{label} must be {expected!r}; received {actual!r}"
                )


@dataclass(frozen=True, slots=True)
class HeadAlignmentPairError:
    role: str
    distance: float
    source_in_body: Vec3
    target_in_body: Vec3

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "distance": self.distance,
            "source_in_body": list(self.source_in_body),
            "target_in_body": list(self.target_in_body),
        }


@dataclass(frozen=True, slots=True)
class HeadAlignmentResult:
    """A proper similarity transform and its named-space evidence."""

    method: str
    source_space: str
    target_space: str
    output_space: str
    imported_to_body: Mat4
    body_to_headhook: Mat4
    imported_to_headhook: Mat4
    rotation: tuple[Vec3, Vec3, Vec3]
    translation_in_body: Vec3
    scale: float
    rotation_determinant: float
    anchor_rank: int
    rms_error: float
    max_error: float
    pair_errors: tuple[HeadAlignmentPairError, ...]
    confidence: str
    warnings: tuple[str, ...] = ()
    transform_sha256: str = field(default="")

    def __post_init__(self) -> None:
        if self.rotation_determinant <= 0.0:
            raise HeadAlignmentError("Alignment result contains a reflected rotation")
        if not self.transform_sha256:
            object.__setattr__(
                self,
                "transform_sha256",
                _result_fingerprint(self),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_alignment",
            "version": 1,
            "method": self.method,
            "source_space": self.source_space,
            "target_space": self.target_space,
            "output_space": self.output_space,
            "imported_to_body": [list(row) for row in self.imported_to_body],
            "body_to_headhook": [list(row) for row in self.body_to_headhook],
            "imported_to_headhook": [
                list(row) for row in self.imported_to_headhook
            ],
            "rotation": [list(row) for row in self.rotation],
            "translation_in_body": list(self.translation_in_body),
            "scale": self.scale,
            "rotation_determinant": self.rotation_determinant,
            "anchor_rank": self.anchor_rank,
            "rms_error": self.rms_error,
            "max_error": self.max_error,
            "pair_errors": [row.to_dict() for row in self.pair_errors],
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "transform_sha256": self.transform_sha256,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HeadAlignmentResult":
        """Rehydrate and verify a saved alignment result."""

        if str(payload.get("schema") or "") != "ghostrigger.head_alignment":
            raise HeadAlignmentError("Unsupported saved head alignment schema")
        if int(payload.get("version") or 0) != 1:
            raise HeadAlignmentError("Unsupported saved head alignment version")
        pair_errors = tuple(
            HeadAlignmentPairError(
                role=str(row.get("role") or ""),
                distance=float(row.get("distance") or 0.0),
                source_in_body=_vec3(
                    row.get("source_in_body") or (),
                    label="source_in_body",
                ),
                target_in_body=_vec3(
                    row.get("target_in_body") or (),
                    label="target_in_body",
                ),
            )
            for row in list(payload.get("pair_errors") or [])
        )
        result = cls(
            method=str(payload.get("method") or ""),
            source_space=str(payload.get("source_space") or ""),
            target_space=str(payload.get("target_space") or ""),
            output_space=str(payload.get("output_space") or ""),
            imported_to_body=_mat4(
                payload.get("imported_to_body") or (),
                label="imported_to_body",
            ),
            body_to_headhook=_mat4(
                payload.get("body_to_headhook") or (),
                label="body_to_headhook",
            ),
            imported_to_headhook=_mat4(
                payload.get("imported_to_headhook") or (),
                label="imported_to_headhook",
            ),
            rotation=tuple(
                _vec3(row, label="rotation row")
                for row in list(payload.get("rotation") or ())
            ),
            translation_in_body=_vec3(
                payload.get("translation_in_body") or (),
                label="translation_in_body",
            ),
            scale=float(payload.get("scale") or 0.0),
            rotation_determinant=float(
                payload.get("rotation_determinant") or 0.0
            ),
            anchor_rank=int(payload.get("anchor_rank") or 0),
            rms_error=float(payload.get("rms_error") or 0.0),
            max_error=float(payload.get("max_error") or 0.0),
            pair_errors=pair_errors,
            confidence=str(payload.get("confidence") or ""),
            warnings=tuple(
                str(value)
                for value in list(payload.get("warnings") or ())
            ),
            transform_sha256=str(
                payload.get("transform_sha256") or ""
            ),
        )
        expected = _result_fingerprint(result)
        if result.transform_sha256 != expected:
            raise HeadAlignmentError(
                "Saved alignment transform fingerprint does not match its matrices"
            )
        return result


def source_axis_to_imported_matrix(
    source_axis: str,
    *,
    unit_scale_to_kotor: float = 1.0,
) -> Mat4:
    """Return the declared source-object to KOTOR imported-object transform.

    No axis is guessed from geometry.  Callers must select either an already
    KOTOR-oriented Z-up source or the explicit Blender/Y-up conversion used by
    Ghost Studio's FBX importer.
    """

    scale = float(unit_scale_to_kotor)
    if not math.isfinite(scale) or scale <= 0.0:
        raise HeadAlignmentError("unit_scale_to_kotor must be finite and positive")
    mode = str(source_axis or "").strip().lower()
    if mode in {"kotor_z_up", "z_up_right_handed", "identity"}:
        rotation = np.eye(3, dtype=np.float64)
    elif mode in {
        "blender_xyz_to_kotor_xz_minus_y",
        "blender_fbx_import_z_up",
        "y_up_right_handed",
    }:
        rotation = np.asarray(
            (
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, -1.0, 0.0),
            ),
            dtype=np.float64,
        )
    elif mode in {
        "tripo_y_up_z_forward",
        "y_up_z_forward",
    }:
        # Tripo OBJ character exports use +Y for height and +Z for facial
        # forward.  KOTOR uses +Z for height and the opposite front-view X
        # convention.  The X flip keeps this conversion a proper rotation,
        # so later similarity fitting never introduces a reflection.
        rotation = np.asarray(
            (
                (-1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0),
            ),
            dtype=np.float64,
        )
    elif mode in {
        "maya_y_up_x_forward",
        "y_up_x_forward",
    }:
        # Maya character scenes commonly use +Y for height, +X for facial
        # forward, and +Z for character right. KOTOR uses +Z for height,
        # +Y for facial forward, and +X for character right. This cyclic
        # permutation is a proper rotation (determinant +1); centimeters are
        # handled separately through ``unit_scale_to_kotor=0.01``.
        rotation = np.asarray(
            (
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            ),
            dtype=np.float64,
        )
    else:
        raise HeadAlignmentError(
            "Unsupported source axis. Choose kotor_z_up, "
            "blender_xyz_to_kotor_xz_minus_y, or "
            "tripo_y_up_z_forward, or maya_y_up_x_forward explicitly."
        )
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = scale * rotation
    return _matrix_tuple(matrix)


def solve_headhook_alignment(
    request: HeadAlignmentRequest,
) -> HeadAlignmentResult:
    """Solve imported-art anchors into body bind and headhook-local spaces."""

    if not isinstance(request, HeadAlignmentRequest):
        raise TypeError("solve_headhook_alignment expects HeadAlignmentRequest")
    source = np.asarray(
        [row.source_point for row in request.anchors],
        dtype=np.float64,
    )
    target = np.asarray(
        [row.target_point for row in request.anchors],
        dtype=np.float64,
    )
    weights = np.asarray(
        [row.weight for row in request.anchors],
        dtype=np.float64,
    )
    normalized_weights = weights / float(weights.sum())
    count = len(request.anchors)
    warnings: list[str] = []

    if count == 1:
        rotation = np.eye(3, dtype=np.float64)
        scale = 1.0
        translation = target[0] - source[0]
        rank = 0
        method = "single_anchor_translation"
        confidence = "translation_only"
        warnings.append(
            "One anchor fixes position only; rotation, roll, and scale remain authored."
        )
    elif count == 2:
        source_delta = source[1] - source[0]
        target_delta = target[1] - target[0]
        source_length = float(np.linalg.norm(source_delta))
        target_length = float(np.linalg.norm(target_delta))
        if source_length <= 1.0e-10 or target_length <= 1.0e-10:
            raise HeadAlignmentDegenerateError(
                "Two-anchor alignment requires distinct source and target points"
            )
        rotation = _rotation_between(source_delta, target_delta)
        scale = (
            target_length / source_length
            if request.scale_mode == "similarity"
            else 1.0
        )
        source_centroid = (
            normalized_weights[:, None] * source
        ).sum(axis=0)
        target_centroid = (
            normalized_weights[:, None] * target
        ).sum(axis=0)
        translation = target_centroid - scale * rotation @ source_centroid
        rank = 1
        method = "two_anchor_direction"
        confidence = "roll_underdetermined"
        warnings.append(
            "Two anchors determine direction but not roll; the minimum rotation was used."
        )
    else:
        source_centroid = (
            normalized_weights[:, None] * source
        ).sum(axis=0)
        target_centroid = (
            normalized_weights[:, None] * target
        ).sum(axis=0)
        source_centered = source - source_centroid
        target_centered = target - target_centroid
        covariance = (
            normalized_weights[:, None] * source_centered
        ).T @ target_centered
        u, singular, vt = np.linalg.svd(covariance)
        threshold = max(float(singular[0]) * 1.0e-9, 1.0e-12)
        rank = int(np.sum(singular > threshold))
        if rank < 2:
            raise HeadAlignmentDegenerateError(
                "Three-or-more-anchor alignment requires non-collinear points"
            )
        correction = np.eye(3, dtype=np.float64)
        if np.linalg.det(vt.T @ u.T) < 0.0:
            correction[2, 2] = -1.0
        rotation = vt.T @ correction @ u.T
        if request.scale_mode == "similarity":
            rotated_source = (rotation @ source_centered.T).T
            numerator = float(
                np.sum(
                    normalized_weights
                    * np.sum(target_centered * rotated_source, axis=1)
                )
            )
            denominator = float(
                np.sum(
                    normalized_weights
                    * np.sum(source_centered * source_centered, axis=1)
                )
            )
            if denominator <= 1.0e-12:
                raise HeadAlignmentDegenerateError(
                    "Alignment source anchors have no usable scale"
                )
            scale = numerator / denominator
            if not math.isfinite(scale) or scale <= 1.0e-10:
                raise HeadAlignmentDegenerateError(
                    "Alignment would require a zero, negative, or reflected scale"
                )
        else:
            scale = 1.0
        translation = target_centroid - scale * rotation @ source_centroid
        method = "weighted_kabsch_similarity" if request.scale_mode == "similarity" else "weighted_kabsch_rigid"
        confidence = "fully_constrained"

    determinant = float(np.linalg.det(rotation))
    if not math.isfinite(determinant) or determinant <= 0.0:
        raise HeadAlignmentError("Alignment solver produced a reflected rotation")

    imported_to_body_np = np.eye(4, dtype=np.float64)
    imported_to_body_np[:3, :3] = scale * rotation
    imported_to_body_np[:3, 3] = translation
    headhook_to_body_np = np.asarray(request.headhook_to_body, dtype=np.float64)
    try:
        body_to_headhook_np = np.linalg.inv(headhook_to_body_np)
    except np.linalg.LinAlgError as exc:
        raise HeadAlignmentError(
            "The body headhook bind transform is not invertible"
        ) from exc
    imported_to_headhook_np = body_to_headhook_np @ imported_to_body_np

    transformed = (
        scale * (rotation @ source.T).T
        + translation
    )
    distances = np.linalg.norm(transformed - target, axis=1)
    rms = float(
        math.sqrt(float(np.sum(normalized_weights * distances * distances)))
    )
    pair_errors = tuple(
        HeadAlignmentPairError(
            role=anchor.role,
            distance=float(distances[index]),
            source_in_body=tuple(float(value) for value in transformed[index]),
            target_in_body=anchor.target_point,
        )
        for index, anchor in enumerate(request.anchors)
    )
    return HeadAlignmentResult(
        method=method,
        source_space=request.source_space,
        target_space=request.target_space,
        output_space=request.output_space,
        imported_to_body=_matrix_tuple(imported_to_body_np),
        body_to_headhook=_matrix_tuple(body_to_headhook_np),
        imported_to_headhook=_matrix_tuple(imported_to_headhook_np),
        rotation=tuple(
            tuple(float(value) for value in row)
            for row in rotation
        ),
        translation_in_body=tuple(float(value) for value in translation),
        scale=float(scale),
        rotation_determinant=determinant,
        anchor_rank=rank,
        rms_error=rms,
        max_error=float(distances.max(initial=0.0)),
        pair_errors=pair_errors,
        confidence=confidence,
        warnings=tuple(warnings),
    )


def transform_point(matrix: Sequence[Sequence[float]], point: Sequence[float]) -> Vec3:
    """Apply an affine 4x4 matrix to a point."""

    affine = np.asarray(_mat4(matrix, label="matrix"), dtype=np.float64)
    value = np.asarray((*_vec3(point, label="point"), 1.0), dtype=np.float64)
    transformed = affine @ value
    if abs(float(transformed[3])) <= 1.0e-12:
        raise HeadAlignmentError("Point transform produced an invalid homogeneous w")
    transformed = transformed[:3] / transformed[3]
    return tuple(float(component) for component in transformed)


def transform_vector(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
    *,
    normalize: bool = False,
) -> Vec3:
    """Apply only the linear portion of a matrix to a vector."""

    affine = np.asarray(_mat4(matrix, label="matrix"), dtype=np.float64)
    value = affine[:3, :3] @ np.asarray(
        _vec3(vector, label="vector"),
        dtype=np.float64,
    )
    if normalize:
        length = float(np.linalg.norm(value))
        if length <= 1.0e-12:
            raise HeadAlignmentError("Cannot normalize a zero transformed vector")
        value = value / length
    return tuple(float(component) for component in value)


def _rotation_between(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    first = source / np.linalg.norm(source)
    second = target / np.linalg.norm(target)
    cross = np.cross(first, second)
    sine = float(np.linalg.norm(cross))
    cosine = float(np.clip(np.dot(first, second), -1.0, 1.0))
    if sine <= 1.0e-12:
        if cosine > 0.0:
            return np.eye(3, dtype=np.float64)
        candidate = np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
        if abs(float(np.dot(first, candidate))) > 0.9:
            candidate = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
        axis = candidate - float(np.dot(candidate, first)) * first
        axis = axis / np.linalg.norm(axis)
        return (2.0 * np.outer(axis, axis)) - np.eye(3, dtype=np.float64)
    axis = cross / sine
    skew = np.asarray(
        (
            (0.0, -axis[2], axis[1]),
            (axis[2], 0.0, -axis[0]),
            (-axis[1], axis[0], 0.0),
        ),
        dtype=np.float64,
    )
    return (
        np.eye(3, dtype=np.float64)
        + sine * skew
        + (1.0 - cosine) * (skew @ skew)
    )


def _vec3(value: Sequence[float], *, label: str) -> Vec3:
    row = tuple(float(component) for component in value)
    if len(row) != 3 or not all(math.isfinite(component) for component in row):
        raise HeadAlignmentError(f"{label} must contain three finite numbers")
    return row


def _mat4(value: Sequence[Sequence[float]], *, label: str) -> Mat4:
    rows = tuple(tuple(float(component) for component in row) for row in value)
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise HeadAlignmentError(f"{label} must be a 4x4 matrix")
    if not all(math.isfinite(component) for row in rows for component in row):
        raise HeadAlignmentError(f"{label} must contain only finite numbers")
    if any(abs(rows[3][index] - expected) > 1.0e-8 for index, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise HeadAlignmentError(f"{label} must be an affine 4x4 matrix")
    return rows  # type: ignore[return-value]


def _matrix_tuple(value: np.ndarray) -> Mat4:
    return tuple(
        tuple(float(component) for component in row)
        for row in value
    )  # type: ignore[return-value]


def _result_fingerprint(result: HeadAlignmentResult) -> str:
    payload = {
        "method": result.method,
        "source_space": result.source_space,
        "target_space": result.target_space,
        "output_space": result.output_space,
        "imported_to_body": result.imported_to_body,
        "body_to_headhook": result.body_to_headhook,
        "imported_to_headhook": result.imported_to_headhook,
        "scale": result.scale,
        "pair_errors": [
            (row.role, row.distance) for row in result.pair_errors
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "BODY_BIND_SPACE",
    "HEADHOOK_LOCAL_SPACE",
    "HEAD_ART_IMPORTED_SPACE",
    "HeadAlignmentAnchor",
    "HeadAlignmentDegenerateError",
    "HeadAlignmentError",
    "HeadAlignmentPairError",
    "HeadAlignmentRequest",
    "HeadAlignmentResult",
    "Mat4",
    "Vec3",
    "solve_headhook_alignment",
    "source_axis_to_imported_matrix",
    "transform_point",
    "transform_vector",
]
