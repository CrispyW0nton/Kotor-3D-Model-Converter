"""Semantic anatomy discovery for imported custom head art.

OBJ exporters often collapse a whole character head into one named surface
even when teeth, tongue, eyes, and eyelids remain disconnected geometric
islands. Facial rigging must recover those islands before skin transfer:
upper teeth belong to ``head_g``; lower teeth and tongue follow the jaw; eyes
and lids retain their native carrier nodes; only the facial shell is skinned.

This module is geometry-only. It does not load game resources, mutate models,
write files, or import Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence

import numpy as np

from src.io.head_art_importer import HeadArtPart


class HeadArtAnatomyError(ValueError):
    """Raised when disconnected custom art cannot form a facial anatomy."""


class HeadArtAnatomyRole(str, Enum):
    FACE_SHELL = "face_shell"
    LEFT_EYE = "left_eye"
    RIGHT_EYE = "right_eye"
    LEFT_EYELID = "left_eyelid"
    RIGHT_EYELID = "right_eyelid"
    UPPER_TEETH = "upper_teeth"
    LOWER_TEETH = "lower_teeth"
    TONGUE = "tongue"
    ACCESSORY = "accessory"


REQUIRED_FACIAL_ROLES = frozenset(
    {
        HeadArtAnatomyRole.FACE_SHELL,
        HeadArtAnatomyRole.LEFT_EYE,
        HeadArtAnatomyRole.RIGHT_EYE,
        HeadArtAnatomyRole.LEFT_EYELID,
        HeadArtAnatomyRole.RIGHT_EYELID,
        HeadArtAnatomyRole.UPPER_TEETH,
        HeadArtAnatomyRole.LOWER_TEETH,
        HeadArtAnatomyRole.TONGUE,
    }
)


@dataclass(frozen=True, slots=True)
class HeadArtComponent:
    component_index: int
    vertex_indices: tuple[int, ...]
    face_indices: tuple[int, ...]
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    centroid: tuple[float, float, float]
    role: HeadArtAnatomyRole = HeadArtAnatomyRole.ACCESSORY

    @property
    def vertex_count(self) -> int:
        return len(self.vertex_indices)

    @property
    def face_count(self) -> int:
        return len(self.face_indices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_index": self.component_index,
            "role": self.role.value,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "bounds_min": list(self.bounds_min),
            "bounds_max": list(self.bounds_max),
            "centroid": list(self.centroid),
        }


@dataclass(frozen=True, slots=True)
class HeadArtAnatomyReport:
    components: tuple[HeadArtComponent, ...]
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        roles = {row.role for row in self.components}
        return not self.failures and REQUIRED_FACIAL_ROLES <= roles

    def component(self, role: HeadArtAnatomyRole | str) -> HeadArtComponent:
        wanted = HeadArtAnatomyRole(role)
        matches = [row for row in self.components if row.role is wanted]
        if len(matches) != 1:
            raise HeadArtAnatomyError(
                f"Expected exactly one {wanted.value} component; found {len(matches)}"
            )
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_art_anatomy",
            "version": 1,
            "ok": self.ok,
            "components": [row.to_dict() for row in self.components],
            "warnings": list(self.warnings),
            "failures": list(self.failures),
        }


def discover_head_art_anatomy(
    part: HeadArtPart,
    *,
    weld_tolerance: float = 1.0e-7,
) -> HeadArtAnatomyReport:
    """Recover and classify disconnected facial islands in one imported part."""

    if not isinstance(part, HeadArtPart):
        raise TypeError("discover_head_art_anatomy expects HeadArtPart")
    points = np.asarray(part.vertices, dtype=np.float64)
    faces = np.asarray(part.faces, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
        raise HeadArtAnatomyError("Head art contains no usable vertex positions")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) < 1:
        raise HeadArtAnatomyError("Head art contains no triangle faces")
    tolerance = float(weld_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise HeadArtAnatomyError("weld_tolerance must be finite and positive")

    welded_ids = _welded_vertex_ids(points, tolerance)
    face_components = _face_components(faces, welded_ids)
    raw: list[HeadArtComponent] = []
    for component_index, face_indices in enumerate(face_components):
        vertex_indices = tuple(
            sorted(
                {
                    int(vertex)
                    for face_index in face_indices
                    for vertex in faces[face_index]
                }
            )
        )
        component_points = points[list(vertex_indices)]
        raw.append(
            HeadArtComponent(
                component_index=component_index,
                vertex_indices=vertex_indices,
                face_indices=tuple(face_indices),
                bounds_min=tuple(float(value) for value in component_points.min(axis=0)),
                bounds_max=tuple(float(value) for value in component_points.max(axis=0)),
                centroid=tuple(float(value) for value in component_points.mean(axis=0)),
            )
        )
    return _classify_components(raw)


def component_mesh(
    part: HeadArtPart,
    components: Iterable[HeadArtComponent],
) -> tuple[
    tuple[tuple[float, float, float], ...],
    tuple[tuple[int, int, int], ...],
    tuple[tuple[float, float, float], ...],
    tuple[tuple[float, float], ...],
    tuple[int, ...],
]:
    """Compact selected components while preserving aligned render channels."""

    selected_faces = tuple(
        sorted(
            {
                face_index
                for component in components
                for face_index in component.face_indices
            }
        )
    )
    old_indices = tuple(
        sorted(
            {
                int(vertex)
                for face_index in selected_faces
                for vertex in part.faces[face_index]
            }
        )
    )
    remap = {old: new for new, old in enumerate(old_indices)}
    vertices = tuple(part.vertices[index] for index in old_indices)
    normals = (
        tuple(part.normals[index] for index in old_indices)
        if len(part.normals) == len(part.vertices)
        else ()
    )
    uvs = (
        tuple(part.uvs[index] for index in old_indices)
        if len(part.uvs) == len(part.vertices)
        else ()
    )
    faces = tuple(
        tuple(remap[int(vertex)] for vertex in part.faces[face_index])
        for face_index in selected_faces
    )
    return vertices, faces, normals, uvs, old_indices


def _classify_components(
    components: Sequence[HeadArtComponent],
) -> HeadArtAnatomyReport:
    if len(components) < 8:
        return HeadArtAnatomyReport(
            components=tuple(components),
            failures=(
                "A facial-performance head needs separate face, eye, eyelid, "
                "upper-teeth, lower-teeth, and tongue geometry.",
            ),
        )
    ordered = sorted(
        components,
        key=lambda row: (row.face_count, row.vertex_count),
        reverse=True,
    )
    shell = ordered[0]
    minimum = np.asarray(shell.bounds_min, dtype=np.float64)
    maximum = np.asarray(shell.bounds_max, dtype=np.float64)
    extent = np.maximum(maximum - minimum, 1.0e-12)
    center_x = float((minimum[0] + maximum[0]) * 0.5)

    remaining = list(ordered[1:])
    mouth = [
        row
        for row in remaining
        if abs(row.centroid[0] - center_x) <= extent[0] * 0.16
        and 0.58 <= (row.centroid[2] - minimum[2]) / extent[2] <= 0.76
        and (row.centroid[1] - minimum[1]) / extent[1] >= 0.68
    ]
    if len(mouth) != 3:
        return HeadArtAnatomyReport(
            components=tuple(components),
            failures=(
                f"Expected three separate central mouth components; found {len(mouth)}.",
            ),
        )
    tongue = max(mouth, key=lambda row: (row.face_count, row.vertex_count))
    teeth = sorted(
        (row for row in mouth if row is not tongue),
        key=lambda row: row.centroid[2],
        reverse=True,
    )
    upper_teeth, lower_teeth = teeth

    upper_pairs = [
        row
        for row in remaining
        if row not in mouth
        and abs(row.centroid[0] - center_x) >= extent[0] * 0.08
        and 0.72 <= (row.centroid[2] - minimum[2]) / extent[2] <= 0.88
        and (row.centroid[1] - minimum[1]) / extent[1] >= 0.76
    ]
    mirrored = _mirrored_pairs(upper_pairs, center_x, extent)
    if len(mirrored) < 2:
        return HeadArtAnatomyReport(
            components=tuple(components),
            failures=(
                "Could not identify separate mirrored eye and eyelid pairs.",
            ),
        )
    mirrored.sort(
        key=lambda pair: (
            sum(row.face_count for row in pair),
            sum(row.vertex_count for row in pair),
            -sum(row.centroid[2] for row in pair),
        ),
        reverse=True,
    )
    eyes = mirrored[0]
    lids = mirrored[1]

    role_by_index: dict[int, HeadArtAnatomyRole] = {
        shell.component_index: HeadArtAnatomyRole.FACE_SHELL,
        tongue.component_index: HeadArtAnatomyRole.TONGUE,
        upper_teeth.component_index: HeadArtAnatomyRole.UPPER_TEETH,
        lower_teeth.component_index: HeadArtAnatomyRole.LOWER_TEETH,
    }
    _assign_sides(role_by_index, eyes, center_x, eye=True)
    _assign_sides(role_by_index, lids, center_x, eye=False)
    classified = tuple(
        HeadArtComponent(
            component_index=row.component_index,
            vertex_indices=row.vertex_indices,
            face_indices=row.face_indices,
            bounds_min=row.bounds_min,
            bounds_max=row.bounds_max,
            centroid=row.centroid,
            role=role_by_index.get(
                row.component_index,
                HeadArtAnatomyRole.ACCESSORY,
            ),
        )
        for row in sorted(components, key=lambda value: value.component_index)
    )
    accessory_count = sum(
        row.role is HeadArtAnatomyRole.ACCESSORY for row in classified
    )
    warnings = (
        (
            f"{accessory_count} disconnected component(s) remain accessories "
            "and require an explicit rigid or physics policy.",
        )
        if accessory_count
        else ()
    )
    return HeadArtAnatomyReport(
        components=classified,
        warnings=warnings,
    )


def _assign_sides(
    output: dict[int, HeadArtAnatomyRole],
    pair: tuple[HeadArtComponent, HeadArtComponent],
    center_x: float,
    *,
    eye: bool,
) -> None:
    left, right = sorted(pair, key=lambda row: row.centroid[0])
    if not left.centroid[0] < center_x < right.centroid[0]:
        raise HeadArtAnatomyError("Facial pair does not straddle the head center")
    output[left.component_index] = (
        HeadArtAnatomyRole.LEFT_EYE
        if eye
        else HeadArtAnatomyRole.LEFT_EYELID
    )
    output[right.component_index] = (
        HeadArtAnatomyRole.RIGHT_EYE
        if eye
        else HeadArtAnatomyRole.RIGHT_EYELID
    )


def _mirrored_pairs(
    rows: Sequence[HeadArtComponent],
    center_x: float,
    extent: np.ndarray,
) -> list[tuple[HeadArtComponent, HeadArtComponent]]:
    negative = [row for row in rows if row.centroid[0] < center_x]
    positive = [row for row in rows if row.centroid[0] > center_x]
    pairs: list[tuple[HeadArtComponent, HeadArtComponent]] = []
    unused = set(row.component_index for row in positive)
    for left in sorted(negative, key=lambda row: abs(row.centroid[0] - center_x)):
        candidates = [row for row in positive if row.component_index in unused]
        if not candidates:
            continue
        right = min(
            candidates,
            key=lambda row: (
                abs(
                    abs(left.centroid[0] - center_x)
                    - abs(row.centroid[0] - center_x)
                )
                + abs(left.centroid[1] - row.centroid[1])
                + abs(left.centroid[2] - row.centroid[2]),
                abs(left.vertex_count - row.vertex_count),
            ),
        )
        mirror_error = (
            abs(
                abs(left.centroid[0] - center_x)
                - abs(right.centroid[0] - center_x)
            )
            / extent[0]
            + abs(left.centroid[1] - right.centroid[1]) / extent[1]
            + abs(left.centroid[2] - right.centroid[2]) / extent[2]
        )
        if mirror_error <= 0.08 and abs(left.vertex_count - right.vertex_count) <= 2:
            pairs.append((left, right))
            unused.remove(right.component_index)
    return pairs


def _welded_vertex_ids(points: np.ndarray, tolerance: float) -> np.ndarray:
    keys = np.rint(points / tolerance).astype(np.int64)
    values: dict[tuple[int, int, int], int] = {}
    output = np.empty(len(points), dtype=np.int64)
    for index, raw in enumerate(keys):
        key = (int(raw[0]), int(raw[1]), int(raw[2]))
        output[index] = values.setdefault(key, len(values))
    return output


def _face_components(
    faces: np.ndarray,
    welded_ids: np.ndarray,
) -> tuple[tuple[int, ...], ...]:
    faces_by_vertex: dict[int, list[int]] = {}
    for face_index, face in enumerate(faces):
        for vertex in {int(welded_ids[int(value)]) for value in face}:
            faces_by_vertex.setdefault(vertex, []).append(face_index)
    visited: set[int] = set()
    output: list[tuple[int, ...]] = []
    for seed in range(len(faces)):
        if seed in visited:
            continue
        stack = [seed]
        visited.add(seed)
        component: list[int] = []
        while stack:
            face_index = stack.pop()
            component.append(face_index)
            for vertex in {
                int(welded_ids[int(value)]) for value in faces[face_index]
            }:
                for neighbour in faces_by_vertex.get(vertex, ()):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        stack.append(neighbour)
        output.append(tuple(sorted(component)))
    return tuple(
        sorted(
            output,
            key=lambda row: (-len(row), row[0]),
        )
    )


__all__ = [
    "HeadArtAnatomyError",
    "HeadArtAnatomyReport",
    "HeadArtAnatomyRole",
    "HeadArtComponent",
    "REQUIRED_FACIAL_ROLES",
    "component_mesh",
    "discover_head_art_anatomy",
]
