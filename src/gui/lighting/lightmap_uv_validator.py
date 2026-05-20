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


class LightmapUVValidator:
    """Inspect existing mesh UVs without modifying them."""

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

        result.degenerate_triangles = self.detect_degenerate_triangles(mesh, uv_channel)
        if result.degenerate_triangles:
            result.warnings.append(f"{len(result.degenerate_triangles)} degenerate or zero-area UV triangle(s).")

        inverted = self._detect_inverted(mesh, uv_channel)
        if inverted:
            result.warnings.append(f"{len(inverted)} UV triangle(s) have inverted winding.")

        result.overlaps = self.detect_overlaps(mesh, uv_channel)
        if result.overlaps:
            result.warnings.append(f"{len(result.overlaps)} possible overlapping UV island pair(s).")

        return result

    def has_lightmap_uvs(self, mesh: object) -> bool:
        return bool(getattr(mesh, "uvs_lm", None))

    def find_best_uv_channel(self, mesh: object) -> int:
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
        boxes: list[tuple[float, float, float, float, int]] = []
        for fi, tri in enumerate(self._face_uv_triangles(mesh, uv_channel)):
            if tri is None:
                continue
            xs = [p[0] for p in tri]
            ys = [p[1] for p in tri]
            area = abs(_area2(tri))
            if area <= 1.0e-10:
                continue
            boxes.append((min(xs), min(ys), max(xs), max(ys), fi))

        overlaps: list[tuple[int, int]] = []
        for idx, a in enumerate(boxes):
            for b in boxes[idx + 1:]:
                if len(overlaps) >= 128:
                    return overlaps
                if a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
                    continue
                if _triangles_overlap_2d(
                    self._face_uv_triangles(mesh, uv_channel)[a[4]],
                    self._face_uv_triangles(mesh, uv_channel)[b[4]],
                ):
                    overlaps.append((a[4], b[4]))
        return overlaps

    def detect_degenerate_triangles(self, mesh: object, uv_channel: int) -> list[int]:
        result: list[int] = []
        for fi, tri in enumerate(self._face_uv_triangles(mesh, uv_channel)):
            if tri is None or abs(_area2(tri)) <= 1.0e-10:
                result.append(fi)
        return result

    def estimate_texel_density(self, mesh: object, uv_channel: int, resolution: int) -> dict[str, float]:
        values: list[float] = []
        verts = list(getattr(mesh, "vertices", []) or [])
        for fi, face in enumerate(getattr(mesh, "faces", []) or []):
            tri_uv = self._face_uv_triangle(mesh, uv_channel, fi)
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

    def _uvs(self, mesh: object, uv_channel: int) -> list:
        attr = {0: "uvs", 1: "uvs_lm", 2: "uvs_2", 3: "uvs_3"}.get(int(uv_channel), "uvs")
        return list(getattr(mesh, attr, []) or [])

    def _face_uv_triangles(self, mesh: object, uv_channel: int) -> list[tuple[tuple[float, float], ...] | None]:
        return [self._face_uv_triangle(mesh, uv_channel, fi) for fi, _face in enumerate(getattr(mesh, "faces", []) or [])]

    def _face_uv_triangle(self, mesh: object, uv_channel: int, face_index: int) -> tuple[tuple[float, float], ...] | None:
        faces = getattr(mesh, "faces", []) or []
        if face_index >= len(faces):
            return None
        face = faces[face_index]
        uvs = self._uvs(mesh, uv_channel)
        if not uvs:
            return None
        if uv_channel == 0:
            face_uvs = getattr(mesh, "face_uvs", []) or []
            if face_uvs and face_index < len(face_uvs):
                indices = face_uvs[face_index]
            else:
                indices = face
        else:
            indices = face
        try:
            return tuple((float(uvs[int(i)][0]), float(uvs[int(i)][1])) for i in indices)
        except Exception:
            return None

    def _detect_inverted(self, mesh: object, uv_channel: int) -> list[int]:
        return [fi for fi, tri in enumerate(self._face_uv_triangles(mesh, uv_channel)) if tri is not None and _area2(tri) < -1.0e-10]


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
