"""Prepared, allocation-light topology previews for Map Studio manipulators.

The committed imported-mesh operators intentionally evaluate from an immutable
source and perform a complete topology audit.  That is the correct commit path,
but rebuilding :class:`MeshTopology` for every mouse-move event makes a dense
room feel sticky.  This module moves the topology-changing work to tool-arm
time: two authoritative operator samples establish a stable topology and the
linear channel deltas.  Drag frames then patch only the channel rows that vary.

The session never serializes KMAP data and never mutates its source primitive.
Faces and per-face material slots come directly from the prepared operator
sample; positions, UV0, lightmap UVs, and normals remain aligned with that
topology.  The controller must still run the authoritative operator once when
the gesture commits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from .authored_imported_mesh import (
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    bevel_imported_mesh_edge,
    extrude_imported_mesh_faces,
    imported_mesh_surface_index_for_role,
)

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
ChannelRow = tuple[float, ...]
Channel = tuple[ChannelRow, ...]

_ZERO_EPSILON = 1.0e-9


@dataclass(frozen=True, slots=True)
class LiveBevelOptions:
    """Width-independent bevel options that participate in session identity."""

    segments: int = 1
    profile: float = 0.5
    miter: str = "auto"
    smoothing_angle_degrees: float = 180.0
    uv_mode: str = "preserve"
    clamp_overlap: bool = True


@dataclass(frozen=True, slots=True)
class LiveTopologySessionIdentity:
    """Everything that requires preparing a new topology sample cache."""

    operation: Literal["face_extrude", "edge_bevel"]
    room_resref: str
    mesh_role: str
    face_indices: tuple[int, ...] = ()
    face_index: int = -1
    edge_corners: tuple[int, int] = (0, 1)
    direction: Vec3 | None = None
    point_normal: bool = False
    tile_size: float = 0.0
    bevel: LiveBevelOptions | None = None


@dataclass(frozen=True, slots=True)
class _SparseLinearChannel:
    """A channel sample plus slopes only for rows that actually move."""

    reference_value: float
    reference_rows: Channel
    changed_rows: tuple[tuple[int, ChannelRow], ...]

    @classmethod
    def from_samples(
        cls,
        low_value: float,
        low_rows: tuple[tuple[float, ...], ...],
        high_value: float,
        high_rows: tuple[tuple[float, ...], ...],
        *,
        label: str,
    ) -> _SparseLinearChannel:
        if len(low_rows) != len(high_rows):
            raise ValueError(
                f"Prepared {label} samples changed channel length "
                f"({len(low_rows)} != {len(high_rows)})."
            )
        span = float(high_value) - float(low_value)
        if abs(span) <= _ZERO_EPSILON:
            raise ValueError(f"Prepared {label} samples need two distinct values.")
        slopes: list[tuple[int, ChannelRow]] = []
        normalized_high: list[ChannelRow] = []
        for index, (low_row, high_row) in enumerate(zip(low_rows, high_rows)):
            first = tuple(float(value) for value in low_row)
            second = tuple(float(value) for value in high_row)
            if len(first) != len(second):
                raise ValueError(f"Prepared {label} row {index} changed arity.")
            normalized_high.append(second)
            if first != second:
                slopes.append(
                    (
                        index,
                        tuple((second[axis] - first[axis]) / span for axis in range(len(second))),
                    )
                )
        return cls(
            reference_value=float(high_value),
            reference_rows=tuple(normalized_high),
            changed_rows=tuple(slopes),
        )

    def evaluate(self, value: float) -> Channel:
        if not self.changed_rows or float(value) == self.reference_value:
            return self.reference_rows
        delta = float(value) - self.reference_value
        rows = list(self.reference_rows)
        for index, slope in self.changed_rows:
            reference = self.reference_rows[index]
            rows[index] = tuple(reference[axis] + (slope[axis] * delta) for axis in range(len(reference)))
        return tuple(rows)


@dataclass(frozen=True, slots=True)
class _PreparedSurface:
    template: ImportedMeshSurface
    vertices: _SparseLinearChannel
    uvs: _SparseLinearChannel
    normals: _SparseLinearChannel
    uvs_lm: _SparseLinearChannel
    negative_extrude_normal_vertices: frozenset[int] = frozenset()

    @classmethod
    def from_samples(
        cls,
        low_value: float,
        low: ImportedMeshSurface,
        high_value: float,
        high: ImportedMeshSurface,
        *,
        source_face_count: int,
        operation: str,
    ) -> _PreparedSurface:
        if low.faces != high.faces:
            raise ValueError("Prepared operator samples produced different face topology.")
        if low.face_mats != high.face_mats:
            raise ValueError("Prepared operator samples produced different face material slots.")
        negative_normal_vertices: frozenset[int] = frozenset()
        if operation == "face_extrude":
            side_face_count = max(0, len(high.faces) - int(source_face_count))
            side_faces = high.faces[-side_face_count:] if side_face_count else ()
            negative_normal_vertices = frozenset(index for face in side_faces for index in face)
        return cls(
            template=high,
            vertices=_SparseLinearChannel.from_samples(
                low_value, low.vertices, high_value, high.vertices, label="vertex"
            ),
            uvs=_SparseLinearChannel.from_samples(low_value, low.uvs, high_value, high.uvs, label="UV0"),
            normals=_SparseLinearChannel.from_samples(
                low_value, low.normals, high_value, high.normals, label="normal"
            ),
            uvs_lm=_SparseLinearChannel.from_samples(
                low_value, low.uvs_lm, high_value, high.uvs_lm, label="lightmap UV"
            ),
            negative_extrude_normal_vertices=negative_normal_vertices,
        )

    def evaluate(self, value: float, *, extrude: bool) -> ImportedMeshSurface:
        signed_value = float(value)
        unsigned_value = abs(signed_value)
        vertices = self.vertices.evaluate(signed_value if extrude else unsigned_value)
        # Extrude side-wall density and bevel width are both magnitude based.
        uvs = self.uvs.evaluate(unsigned_value)
        uvs_lm = self.uvs_lm.evaluate(unsigned_value)
        normals = self.normals.evaluate(unsigned_value)
        if extrude and signed_value < 0.0 and self.negative_extrude_normal_vertices:
            rows = list(normals)
            for index in self.negative_extrude_normal_vertices:
                normal = rows[index]
                rows[index] = tuple(-component for component in normal)
            normals = tuple(rows)
        return replace(
            self.template,
            vertices=tuple(tuple(row) for row in vertices),
            # Faces and face_mats intentionally remain the exact cached tuples.
            uvs=tuple(tuple(row) for row in uvs),
            normals=tuple(tuple(row) for row in normals),
            uvs_lm=tuple(tuple(row) for row in uvs_lm),
        )


class MapStudioLiveTopologySession:
    """Prepared face-extrude or edge-bevel evaluator for one immutable source."""

    __slots__ = (
        "_source",
        "_surface_index",
        "_prepared",
        "_maximum_value",
        "_bevel_edit_template",
        "identity",
    )

    def __init__(
        self,
        *,
        source: ImportedMeshRoomPrimitive,
        surface_index: int,
        prepared: _PreparedSurface,
        identity: LiveTopologySessionIdentity,
        maximum_value: float | None,
        bevel_edit_template: dict | None = None,
    ) -> None:
        self._source = source
        self._surface_index = int(surface_index)
        self._prepared = prepared
        self.identity = identity
        self._maximum_value = maximum_value
        self._bevel_edit_template = dict(bevel_edit_template or {})

    @property
    def source(self) -> ImportedMeshRoomPrimitive:
        return self._source

    @property
    def maximum_value(self) -> float | None:
        """Safe absolute bevel width, or the optional extrude distance limit."""

        return self._maximum_value

    @property
    def prepared_sample_count(self) -> int:
        return 2

    @classmethod
    def prepare_face_extrude(
        cls,
        source: ImportedMeshRoomPrimitive,
        mesh_role: str,
        face_indices: tuple[int, ...] | list[int],
        *,
        point_normal: bool = False,
        tile_size: float = 0.0,
        direction: Vec3 | None = None,
        reference_distance: float = 1.0,
        maximum_abs_distance: float | None = None,
    ) -> MapStudioLiveTopologySession:
        """Prepare a stable face-extrude topology and its sparse channel deltas."""

        surface_index = imported_mesh_surface_index_for_role(source, str(mesh_role))
        if surface_index < 0:
            raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
        selected = tuple(sorted({int(index) for index in face_indices}))
        if not selected:
            raise ValueError("Face extrude needs at least one selected face.")
        source_surface = source.surfaces[surface_index]
        if any(index < 0 or index >= len(source_surface.faces) for index in selected):
            raise ValueError("Face extrude selection contains an out-of-range face index.")
        reference = abs(float(reference_distance))
        if not math.isfinite(reference) or reference <= (_ZERO_EPSILON * 4.0):
            raise ValueError("Extrude preview reference distance must be finite and non-zero.")
        maximum: float | None = None
        if maximum_abs_distance is not None:
            maximum = abs(float(maximum_abs_distance))
            if not math.isfinite(maximum) or maximum <= (_ZERO_EPSILON * 4.0):
                raise ValueError("Extrude preview distance limit must be finite and non-zero.")
            reference = min(reference, maximum)
        normalized_direction = _normalized_direction(direction)
        low_value = reference * 0.5
        high_value = reference

        def _sample(distance: float) -> ImportedMeshRoomPrimitive:
            return extrude_imported_mesh_faces(
                source,
                str(mesh_role),
                selected,
                distance,
                point_normal=bool(point_normal),
                tile_size=float(tile_size),
                direction=normalized_direction,
            )

        low = _sample(low_value).surfaces[surface_index]
        high = _sample(high_value).surfaces[surface_index]
        prepared = _PreparedSurface.from_samples(
            low_value,
            low,
            high_value,
            high,
            source_face_count=len(source_surface.faces),
            operation="face_extrude",
        )
        identity = LiveTopologySessionIdentity(
            operation="face_extrude",
            room_resref=str(source.room_resref),
            mesh_role=str(mesh_role),
            face_indices=selected,
            direction=normalized_direction,
            point_normal=bool(point_normal),
            tile_size=float(tile_size),
        )
        return cls(
            source=source,
            surface_index=surface_index,
            prepared=prepared,
            identity=identity,
            maximum_value=maximum,
        )

    @classmethod
    def prepare_edge_bevel(
        cls,
        source: ImportedMeshRoomPrimitive,
        mesh_role: str,
        face_index: int,
        edge_corners: tuple[int, int] | list[int],
        *,
        segments: int = 1,
        profile: float = 0.5,
        miter: str = "auto",
        smoothing_angle_degrees: float = 180.0,
        uv_mode: str = "preserve",
        clamp_overlap: bool = True,
    ) -> MapStudioLiveTopologySession:
        """Prepare a bevel topology and discover its geometric safe-width clamp."""

        surface_index = imported_mesh_surface_index_for_role(source, str(mesh_role))
        if surface_index < 0:
            raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
        surface = source.surfaces[surface_index]
        selected_face = int(face_index)
        if selected_face < 0 or selected_face >= len(surface.faces):
            raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
        raw_corners = tuple(int(value) for value in tuple(edge_corners)[:2])
        if len(raw_corners) != 2:
            raise ValueError("Bevel needs two edge corner indices.")
        corner_count = len(surface.faces[selected_face])
        corners = (raw_corners[0] % corner_count, raw_corners[1] % corner_count)
        if corners[0] == corners[1]:
            raise ValueError("Edge corners must reference two different face corners.")
        options = _normalized_bevel_options(
            segments=segments,
            profile=profile,
            miter=miter,
            smoothing_angle_degrees=smoothing_angle_degrees,
            uv_mode=uv_mode,
            clamp_overlap=clamp_overlap,
        )

        xs = [row[0] for row in surface.vertices]
        ys = [row[1] for row in surface.vertices]
        zs = [row[2] for row in surface.vertices]
        diagonal = math.sqrt(
            ((max(xs) - min(xs)) ** 2)
            + ((max(ys) - min(ys)) ** 2)
            + ((max(zs) - min(zs)) ** 2)
        )
        probe_width = max(1.0, diagonal * 2.0)

        def _sample(width: float) -> ImportedMeshRoomPrimitive:
            # Preparation always clamps the probe.  ``evaluate`` preserves the
            # caller's requested clamp/raise behavior after the safe bound is
            # known.
            return bevel_imported_mesh_edge(
                source,
                str(mesh_role),
                selected_face,
                corners,
                width,
                segments=options.segments,
                profile=options.profile,
                miter=options.miter,
                smoothing_angle_degrees=options.smoothing_angle_degrees,
                uv_mode=options.uv_mode,
                clamp_overlap=True,
            )

        high_primitive = _sample(probe_width)
        high_edit = dict(high_primitive.metadata.get("last_topology_edit") or {})
        safe_width = float(high_edit.get("width", 0.0) or 0.0)
        if not math.isfinite(safe_width) or safe_width <= (_ZERO_EPSILON * 4.0):
            raise ValueError("Selected edge has no safe non-zero bevel width.")
        low_value = safe_width * 0.5
        low_primitive = _sample(low_value)
        prepared = _PreparedSurface.from_samples(
            low_value,
            low_primitive.surfaces[surface_index],
            safe_width,
            high_primitive.surfaces[surface_index],
            source_face_count=len(surface.faces),
            operation="edge_bevel",
        )
        identity = LiveTopologySessionIdentity(
            operation="edge_bevel",
            room_resref=str(source.room_resref),
            mesh_role=str(mesh_role),
            face_index=selected_face,
            edge_corners=corners,
            bevel=options,
        )
        return cls(
            source=source,
            surface_index=surface_index,
            prepared=prepared,
            identity=identity,
            maximum_value=safe_width,
            bevel_edit_template=high_edit,
        )

    def evaluate(self, value: float) -> ImportedMeshRoomPrimitive:
        """Evaluate one drag frame without rebuilding topology or serializing KMAP."""

        requested = float(value)
        if not math.isfinite(requested):
            raise ValueError("Live topology value must be finite.")
        if abs(requested) <= _ZERO_EPSILON:
            return self._source

        extrude = self.identity.operation == "face_extrude"
        evaluated_value = requested
        if extrude:
            if self._maximum_value is not None:
                evaluated_value = max(-self._maximum_value, min(self._maximum_value, requested))
        else:
            evaluated_value = abs(requested)
            maximum = float(self._maximum_value or 0.0)
            options = self.identity.bevel or LiveBevelOptions()
            if evaluated_value > maximum:
                if not options.clamp_overlap:
                    raise ValueError(
                        f"Bevel width {evaluated_value:.4f}m would invert an adjacent face; "
                        f"maximum safe width is {maximum:.4f}m."
                    )
                evaluated_value = maximum

        surface = self._prepared.evaluate(evaluated_value, extrude=extrude)
        surfaces = list(self._source.surfaces)
        surfaces[self._surface_index] = surface
        metadata = self._source.metadata
        if not extrude:
            edit = dict(self._bevel_edit_template)
            edit["width"] = float(evaluated_value)
            edit["requested_width"] = abs(float(requested))
            metadata = {**dict(self._source.metadata), "last_topology_edit": edit}
        return replace(self._source, surfaces=tuple(surfaces), metadata=metadata)


def _normalized_direction(direction: Vec3 | None) -> Vec3 | None:
    if direction is None:
        return None
    row = tuple(float(value) for value in tuple(direction)[:3])
    if len(row) != 3 or not all(math.isfinite(value) for value in row):
        raise ValueError("Extrude direction must contain three finite values.")
    length = math.sqrt(sum(value * value for value in row))
    if length <= _ZERO_EPSILON:
        return (0.0, 0.0, 1.0)
    return (row[0] / length, row[1] / length, row[2] / length)


def _normalized_bevel_options(
    *,
    segments: int,
    profile: float,
    miter: str,
    smoothing_angle_degrees: float,
    uv_mode: str,
    clamp_overlap: bool,
) -> LiveBevelOptions:
    segment_count = max(1, min(64, int(segments)))
    round_profile = max(0.0, min(1.0, float(profile)))
    if not math.isfinite(round_profile):
        raise ValueError("Bevel profile must be finite.")
    miter_mode = str(miter or "auto").strip().lower()
    if miter_mode not in {"auto", "sharp", "patch"}:
        raise ValueError("Single-edge bevel miter must be Auto, Sharp, or Patch.")
    smoothing = float(smoothing_angle_degrees)
    if not math.isfinite(smoothing):
        raise ValueError("Bevel smoothing angle must be finite.")
    smoothing = max(0.0, min(180.0, smoothing))
    uv_policy = str(uv_mode or "preserve").strip().lower()
    if uv_policy not in {"preserve", "tiled", "none"}:
        raise ValueError("Bevel UV mode must be Preserve, Tiled, or None.")
    return LiveBevelOptions(
        segments=segment_count,
        profile=round_profile,
        miter=miter_mode,
        smoothing_angle_degrees=smoothing,
        uv_mode=uv_policy,
        clamp_overlap=bool(clamp_overlap),
    )


__all__ = [
    "LiveBevelOptions",
    "LiveTopologySessionIdentity",
    "MapStudioLiveTopologySession",
]
