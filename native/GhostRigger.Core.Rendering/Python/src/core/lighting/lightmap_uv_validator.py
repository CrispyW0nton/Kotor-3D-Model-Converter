"""UV validation for generated lightmap baking."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass
class UVValidationResult:
    mesh_name: str
    uv_channel: int
    usable: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    overlaps: list[tuple[int, int]] = field(default_factory=list)
    degenerate_triangles: list[int] = field(default_factory=list)
    texel_density: dict[str, float] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if self.errors:
            return "blocked"
        if self.warnings or self.overlaps or self.degenerate_triangles:
            return "warning"
        return "ok"


@dataclass
class UVChannelInfo:
    mesh_name: str
    channel_index: int
    display_name: str
    uv_count: int
    face_count: int
    has_uvs: bool
    has_overlaps: bool
    has_out_of_bounds_uvs: bool
    coverage_ratio: float
    recommended_for_lightmap: bool
    notes: list[str] = field(default_factory=list)


class LightmapUVValidator:
    """Inspect existing mesh UVs without modifying them."""

    def inspect_mesh_uv_channels(self, mesh: object, max_channels: int = 3) -> list[UVChannelInfo]:
        """Return artist-facing UV channel stats for a selected mesh.

        The UI displays UV1/UV2/UV3 while the data model remains zero-indexed.
        Lightmap bakes normally want UV2/internal channel 1 because diffuse UVs
        often tile, mirror, or overlap in ways that are valid for materials but
        invalid for lightmaps.
        """
        infos: list[UVChannelInfo] = []
        highest = max(max_channels, self._highest_existing_channel(mesh) + 1)
        for channel in range(highest):
            validation = self.validate_mesh_uvs(mesh, channel)
            uvs = self._uvs(mesh, channel)
            notes = [*validation.warnings, *validation.errors]
            coverage = self.estimate_coverage_ratio(mesh, channel)
            has_out_of_bounds = any("outside the 0-1 range" in note for note in notes)
            has_uvs = bool(uvs)
            recommended = (
                has_uvs
                and not validation.errors
                and not validation.overlaps
                and not has_out_of_bounds
                and not validation.degenerate_triangles
                and coverage >= 0.03
                and channel != 0
            )
            if has_uvs and channel == 0 and (validation.overlaps or has_out_of_bounds or coverage > 0.95):
                notes.append("UV1 appears to be diffuse/material UVs and may be tiled or stacked.")
            if has_uvs and coverage < 0.03:
                notes.append("Atlas coverage is very low; generated lightmap UVs may bake cleaner.")
            infos.append(
                UVChannelInfo(
                    mesh_name=str(getattr(mesh, "name", "mesh") or "mesh"),
                    channel_index=channel,
                    display_name=self.display_name(channel),
                    uv_count=len(uvs),
                    face_count=len(getattr(mesh, "faces", []) or []),
                    has_uvs=has_uvs,
                    has_overlaps=bool(validation.overlaps),
                    has_out_of_bounds_uvs=has_out_of_bounds,
                    coverage_ratio=coverage,
                    recommended_for_lightmap=recommended,
                    notes=notes,
                )
            )
        return infos

    def validate_mesh_uvs(self, mesh: object, uv_channel: int) -> UVValidationResult:
        name = str(getattr(mesh, "name", "mesh") or "mesh")
        uvs = self._uvs(mesh, uv_channel)
        faces = list(getattr(mesh, "faces", []) or [])
        result = UVValidationResult(name, uv_channel, usable=True)

        if not uvs:
            result.usable = False
            result.errors.append("Mesh has no usable UVs.")
            return result
        if not faces:
            result.usable = False
            result.errors.append("Mesh has no triangles.")
            return result

        outside = 0
        bad_values = 0
        for uv in uvs:
            try:
                u, v = float(uv[0]), float(uv[1])
            except Exception:
                bad_values += 1
                continue
            if not isfinite(u) or not isfinite(v):
                bad_values += 1
            elif u < 0.0 or u > 1.0 or v < 0.0 or v > 1.0:
                outside += 1
        if bad_values:
            result.warnings.append(f"{bad_values} UV coordinate(s) contain invalid numeric values.")
        if outside:
            result.warnings.append(f"{outside} UV coordinate(s) are outside the 0-1 range.")

        triangles = self._face_uv_triangles(mesh, uv_channel)
        result.degenerate_triangles = _detect_degenerate_triangles(triangles)
        if result.degenerate_triangles:
            result.warnings.append(f"{len(result.degenerate_triangles)} degenerate or zero-area UV triangle(s).")

        inverted = _detect_inverted_triangles(triangles)
        if inverted:
            result.warnings.append(f"{len(inverted)} UV triangle(s) have inverted winding.")

        result.overlaps = _detect_overlaps_from_triangles(triangles)
        if result.overlaps:
            result.warnings.append(f"{len(result.overlaps)} possible overlapping UV island pair(s).")

        return result

    def has_lightmap_uvs(self, mesh: object) -> bool:
        return bool(getattr(mesh, "uvs_lm", None))

    def find_best_uv_channel(self, mesh: object) -> int:
        for info in self.inspect_mesh_uv_channels(mesh, 3):
            if info.channel_index == 1 and info.recommended_for_lightmap:
                return 1
        if self.has_lightmap_uvs(mesh):
            return 1
        if getattr(mesh, "uvs", None):
            return 0
        if getattr(mesh, "uvs_2", None):
            return 2
        if getattr(mesh, "uvs_3", None):
            return 3
        return -1

    def detect_overlaps(self, mesh: object, uv_channel: int) -> list[tuple[int, int]]:
        return _detect_overlaps_from_triangles(self._face_uv_triangles(mesh, uv_channel))

    def detect_degenerate_triangles(self, mesh: object, uv_channel: int) -> list[int]:
        return _detect_degenerate_triangles(self._face_uv_triangles(mesh, uv_channel))

    def estimate_texel_density(self, mesh: object, uv_channel: int, resolution: int) -> dict[str, float]:
        values: list[float] = []
        verts = list(getattr(mesh, "vertices", []) or [])
        triangles = self._face_uv_triangles(mesh, uv_channel)
        for fi, face in enumerate(getattr(mesh, "faces", []) or []):
            tri_uv = triangles[fi] if fi < len(triangles) else None
            if tri_uv is None:
                continue
            try:
                p0, p1, p2 = (verts[int(face[0])], verts[int(face[1])], verts[int(face[2])])
            except Exception:
                continue
            uv_area = abs(_area2(tri_uv)) * 0.5
            world_area = _tri_world_area(p0, p1, p2)
            if uv_area > 1.0e-12 and world_area > 1.0e-12:
                values.append((uv_area * resolution * resolution) / world_area)
        if not values:
            return {"min": 0.0, "max": 0.0, "average": 0.0}
        return {"min": min(values), "max": max(values), "average": sum(values) / len(values)}

    def estimate_coverage_ratio(self, mesh: object, uv_channel: int) -> float:
        area = 0.0
        for tri in self._face_uv_triangles(mesh, uv_channel):
            if tri is None:
                continue
            area += max(0.0, abs(_area2(tri)) * 0.5)
        return max(0.0, min(1.0, float(area)))

    def is_safe_for_baking(self, mesh: object, uv_channel: int) -> bool:
        info = self.inspect_mesh_uv_channels(mesh, max_channels=uv_channel + 1)[uv_channel]
        return bool(info.has_uvs and not info.has_overlaps and not info.has_out_of_bounds_uvs and info.coverage_ratio > 0.0)

    def display_name(self, uv_channel: int) -> str:
        return f"UV{int(uv_channel) + 1}"

    def _uvs(self, mesh: object, uv_channel: int) -> list:
        attr = uv_attr_for_channel(uv_channel)
        return list(getattr(mesh, attr, []) or [])

    def _face_uv_indices(self, mesh: object, uv_channel: int, face_index: int):
        faces = getattr(mesh, "faces", []) or []
        if face_index >= len(faces):
            return None
        face_uvs = getattr(mesh, face_uv_attr_for_channel(uv_channel), []) or []
        if face_uvs and face_index < len(face_uvs):
            return face_uvs[face_index]
        return faces[face_index]

    def _face_uv_triangles(self, mesh: object, uv_channel: int) -> list[tuple[tuple[float, float], ...] | None]:
        faces = list(getattr(mesh, "faces", []) or [])
        uvs = self._uvs(mesh, uv_channel)
        face_uvs = list(getattr(mesh, face_uv_attr_for_channel(uv_channel), []) or [])
        if not uvs:
            return [None] * len(faces)
        triangles: list[tuple[tuple[float, float], ...] | None] = []
        for face_index, face in enumerate(faces):
            indices = face_uvs[face_index] if face_index < len(face_uvs) else face
            try:
                triangles.append(
                    tuple((float(uvs[int(index)][0]), float(uvs[int(index)][1])) for index in indices)
                )
            except Exception:
                triangles.append(None)
        return triangles

    def _face_uv_triangle(self, mesh: object, uv_channel: int, face_index: int) -> tuple[tuple[float, float], ...] | None:
        faces = getattr(mesh, "faces", []) or []
        if face_index >= len(faces):
            return None
        face = faces[face_index]
        uvs = self._uvs(mesh, uv_channel)
        if not uvs:
            return None
        indices = self._face_uv_indices(mesh, uv_channel, face_index)
        try:
            return tuple((float(uvs[int(i)][0]), float(uvs[int(i)][1])) for i in indices)
        except Exception:
            return None

    def _detect_inverted(self, mesh: object, uv_channel: int) -> list[int]:
        return _detect_inverted_triangles(self._face_uv_triangles(mesh, uv_channel))

    def _highest_existing_channel(self, mesh: object) -> int:
        highest = -1
        for channel in range(8):
            if self._uvs(mesh, channel):
                highest = channel
        return highest


def _detect_overlaps_from_triangles(
    triangles: list[tuple[tuple[float, float], ...] | None],
) -> list[tuple[int, int]]:
    """Find exact triangle overlaps after a sweep-line AABB broadphase.

    Atlas-scale rooms can contain tens of thousands of triangles.  Cache the
    UV triangle stream once and only compare boxes whose X intervals are
    simultaneously active; the former nested scan rebuilt the complete stream
    twice for every candidate pair and became effectively unusable on imported
    cave meshes.
    """

    boxes: list[tuple[float, float, float, float, int]] = []
    for face_index, triangle in enumerate(triangles):
        if triangle is None or abs(_area2(triangle)) <= 1.0e-10:
            continue
        xs = (triangle[0][0], triangle[1][0], triangle[2][0])
        ys = (triangle[0][1], triangle[1][1], triangle[2][1])
        boxes.append((min(xs), min(ys), max(xs), max(ys), face_index))
    boxes.sort(key=lambda box: (box[0], box[2], box[1], box[3], box[4]))

    active: list[tuple[float, float, float, float, int]] = []
    overlaps: set[tuple[int, int]] = set()
    for current in boxes:
        current_min_x = current[0]
        active = [candidate for candidate in active if candidate[2] > current_min_x]
        for candidate in active:
            if candidate[3] <= current[1] or current[3] <= candidate[1]:
                continue
            first_index, second_index = sorted((candidate[4], current[4]))
            if _triangles_overlap_2d(triangles[first_index], triangles[second_index]):
                overlaps.add((first_index, second_index))
                if len(overlaps) >= 128:
                    return sorted(overlaps)
        active.append(current)
    return sorted(overlaps)


def _detect_degenerate_triangles(
    triangles: list[tuple[tuple[float, float], ...] | None],
) -> list[int]:
    return [
        face_index
        for face_index, triangle in enumerate(triangles)
        if triangle is None or abs(_area2(triangle)) <= 1.0e-10
    ]


def _detect_inverted_triangles(
    triangles: list[tuple[tuple[float, float], ...] | None],
) -> list[int]:
    return [
        face_index
        for face_index, triangle in enumerate(triangles)
        if triangle is not None and _area2(triangle) < -1.0e-10
    ]


def uv_attr_for_channel(uv_channel: int) -> str:
    return {0: "uvs", 1: "uvs_lm", 2: "uvs_2", 3: "uvs_3"}.get(int(uv_channel), f"uvs_{int(uv_channel)}")


def face_uv_attr_for_channel(uv_channel: int) -> str:
    return {0: "face_uvs", 1: "face_uvs_lm", 2: "face_uvs_2", 3: "face_uvs_3"}.get(int(uv_channel), f"face_uvs_{int(uv_channel)}")


def _area2(tri: tuple[tuple[float, float], ...]) -> float:
    (u0, v0), (u1, v1), (u2, v2) = tri
    return (u1 - u0) * (v2 - v0) - (v1 - v0) * (u2 - u0)


def _tri_world_area(a, b, c) -> float:
    ax, ay, az = float(a[0]), float(a[1]), float(a[2])
    bx, by, bz = float(b[0]), float(b[1]), float(b[2])
    cx, cy, cz = float(c[0]), float(c[1]), float(c[2])
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    return ((cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2) ** 0.5) * 0.5


def _triangles_overlap_2d(a, b) -> bool:
    if a is None or b is None:
        return False
    axes = []
    for tri in (a, b):
        for i in range(3):
            p0, p1 = tri[i], tri[(i + 1) % 3]
            edge = (p1[0] - p0[0], p1[1] - p0[1])
            axes.append((-edge[1], edge[0]))
    for ax in axes:
        amin, amax = _project(a, ax)
        bmin, bmax = _project(b, ax)
        if amax <= bmin or bmax <= amin:
            return False
    return True


def _project(tri, axis):
    vals = [p[0] * axis[0] + p[1] * axis[1] for p in tri]
    return min(vals), max(vals)
