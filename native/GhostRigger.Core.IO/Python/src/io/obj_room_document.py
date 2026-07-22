"""Deterministic, renderer-neutral OBJ document import for Map Studio rooms.

The legacy :mod:`src.converters.mesh_converter` importer is intentionally a
KotorModel convenience path.  It changes the active material on an existing
group, which is not sufficient for environment exports where a single Maya
mesh can switch materials thousands of times.  This module keeps the file/MTL
concerns in Core.IO and returns compact material surfaces for the Scene layer
to transform into authored KMAP geometry.

No KOTOR policy lives here: source units, up-axis conversion, ResRef naming,
walkmesh intent, and project texture ownership are applied by the Map Studio
authoring workflow.
"""

from __future__ import annotations

import math
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]
IndexTriple = tuple[int, int, int]


@dataclass(frozen=True)
class ObjRoomMaterial:
    """One material declared by an OBJ companion MTL file."""

    name: str
    diffuse: Vec3 = (0.8, 0.8, 0.8)
    ambient: Vec3 = (0.2, 0.2, 0.2)
    diffuse_texture: str = ""
    diffuse_texture_path: str = ""

    @property
    def texture_exists(self) -> bool:
        return bool(self.diffuse_texture_path and Path(self.diffuse_texture_path).is_file())


@dataclass(frozen=True)
class ObjRoomSurface:
    """One compact OBJ group/material surface with aligned vertex channels."""

    name: str
    group_name: str
    material_name: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    uvs: tuple[Vec2, ...] = ()
    normals: tuple[Vec3, ...] = ()


@dataclass(frozen=True)
class ObjRoomDocument:
    """Parsed OBJ/MTL data suitable for a Map Studio room import workflow."""

    source_path: str
    mtllib_paths: tuple[str, ...]
    units_hint: str
    vertices_read: int
    texcoords_read: int
    normals_read: int
    source_face_count: int
    triangle_count: int
    bounds_min: Vec3
    bounds_max: Vec3
    materials: tuple[ObjRoomMaterial, ...]
    surfaces: tuple[ObjRoomSurface, ...]
    warnings: tuple[str, ...] = ()

    def material(self, name: str) -> ObjRoomMaterial | None:
        wanted = str(name or "")
        return next((item for item in self.materials if item.name == wanted), None)


class ObjRoomImportError(ValueError):
    """Raised when an OBJ cannot provide structurally usable room geometry."""


_UNIT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmillimet(?:er|re)s?\b|\bmm\b", re.IGNORECASE), "millimeters"),
    (re.compile(r"\bcentimet(?:er|re)s?\b|\bcm\b", re.IGNORECASE), "centimeters"),
    (re.compile(r"\bkilomet(?:er|re)s?\b|\bkm\b", re.IGNORECASE), "kilometers"),
    (re.compile(r"\bmet(?:er|re)s?\b", re.IGNORECASE), "meters"),
    (re.compile(r"\binches?\b|\bin\b", re.IGNORECASE), "inches"),
    (re.compile(r"\bfeet\b|\bfoot\b|\bft\b", re.IGNORECASE), "feet"),
)


def _unit_hint(comment: str) -> str:
    text = str(comment or "")
    if "unit" not in text.lower() and "coordinate" not in text.lower():
        return ""
    for pattern, label in _UNIT_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def _parse_vec3(tokens: list[str], *, line_number: int, label: str) -> Vec3:
    try:
        return (float(tokens[1]), float(tokens[2]), float(tokens[3]))
    except (IndexError, ValueError) as exc:
        raise ObjRoomImportError(f"OBJ line {line_number} has an invalid {label} record.") from exc


def _resolve_index(raw: str, count: int, *, line_number: int, channel: str) -> int:
    if not raw:
        return -1
    try:
        value = int(raw)
    except ValueError as exc:
        raise ObjRoomImportError(
            f"OBJ line {line_number} has a non-integer {channel} index {raw!r}."
        ) from exc
    if value == 0:
        raise ObjRoomImportError(f"OBJ line {line_number} uses forbidden zero {channel} index.")
    index = value - 1 if value > 0 else count + value
    if index < 0 or index >= count:
        raise ObjRoomImportError(
            f"OBJ line {line_number} references {channel} index {value}, outside the {count} values read so far."
        )
    return index


def _face_vertex(
    token: str,
    *,
    vertex_count: int,
    texcoord_count: int,
    normal_count: int,
    line_number: int,
) -> IndexTriple:
    parts = token.split("/")
    if len(parts) > 3:
        raise ObjRoomImportError(f"OBJ line {line_number} has invalid face vertex {token!r}.")
    vertex = _resolve_index(parts[0], vertex_count, line_number=line_number, channel="vertex")
    texcoord = (
        _resolve_index(parts[1], texcoord_count, line_number=line_number, channel="texture-coordinate")
        if len(parts) >= 2 and parts[1]
        else -1
    )
    normal = (
        _resolve_index(parts[2], normal_count, line_number=line_number, channel="normal")
        if len(parts) >= 3 and parts[2]
        else -1
    )
    return (vertex, texcoord, normal)


def _normalise(value: Vec3) -> Vec3:
    length = math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (value[0] / length, value[1] / length, value[2] / length)


def _generated_vertex_normals(vertices: list[Vec3], faces: list[Face]) -> tuple[Vec3, ...]:
    accumulated = [[0.0, 0.0, 0.0] for _ in vertices]
    for a, b, c in faces:
        ax, ay, az = vertices[a]
        bx, by, bz = vertices[b]
        cx, cy, cz = vertices[c]
        ux, uy,uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        normal = (
            uy * vz - uz * vy,
            uz * vx - ux * vz,
            ux * vy - uy * vx,
        )
        for index in (a, b, c):
            accumulated[index][0] += normal[0]
            accumulated[index][1] += normal[1]
            accumulated[index][2] += normal[2]
    return tuple(_normalise((row[0], row[1], row[2])) for row in accumulated)


def _triangle_cross_squared(a: Vec3, b: Vec3, c: Vec3) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cross = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    return sum(value * value for value in cross)


def _newell_normal(points: list[Vec3]) -> Vec3:
    nx = ny = nz = 0.0
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        nx += (point[1] - following[1]) * (point[2] + following[2])
        ny += (point[2] - following[2]) * (point[0] + following[0])
        nz += (point[0] - following[0]) * (point[1] + following[1])
    return (nx, ny, nz)


def _project_polygon(points: list[Vec3]) -> list[Vec2]:
    normal = _newell_normal(points)
    dominant = max(range(3), key=lambda axis: abs(normal[axis]))
    if dominant == 0:
        return [(point[1], point[2]) for point in points]
    if dominant == 1:
        return [(point[0], point[2]) for point in points]
    return [(point[0], point[1]) for point in points]


def _cross_2d(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle_2d(point: Vec2, a: Vec2, b: Vec2, c: Vec2, orientation: float) -> bool:
    epsilon = 1.0e-12
    first = orientation * _cross_2d(a, b, point)
    second = orientation * _cross_2d(b, c, point)
    third = orientation * _cross_2d(c, a, point)
    return first >= -epsilon and second >= -epsilon and third >= -epsilon


def _source_normal_alignment(
    triangle: tuple[IndexTriple, IndexTriple, IndexTriple],
    positions: list[Vec3],
    normals: list[Vec3],
) -> float:
    points = [positions[corner[0]] for corner in triangle]
    a, b, c = points
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    geometric = _normalise((uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx))
    source_normals = [normals[corner[2]] for corner in triangle if corner[2] >= 0]
    if not source_normals:
        return 0.0
    averaged = _normalise(
        tuple(sum(normal[axis] for normal in source_normals) for axis in range(3))
    )
    return sum(geometric[axis] * averaged[axis] for axis in range(3))


def _triangulate_quad(
    corners: list[IndexTriple],
    positions: list[Vec3],
    normals: list[Vec3],
) -> list[tuple[IndexTriple, IndexTriple, IndexTriple]]:
    candidates = (
        ((corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])),
        ((corners[0], corners[1], corners[3]), (corners[1], corners[2], corners[3])),
    )

    def score(candidate: tuple[tuple[IndexTriple, IndexTriple, IndexTriple], ...]) -> tuple[int, float, float]:
        crosses = [
            _triangle_cross_squared(
                positions[triangle[0][0]],
                positions[triangle[1][0]],
                positions[triangle[2][0]],
            )
            for triangle in candidate
        ]
        valid = sum(value > 1.0e-24 for value in crosses)
        alignment = sum(_source_normal_alignment(triangle, positions, normals) for triangle in candidate)
        return (valid, alignment, min(crosses))

    return list(max(candidates, key=score))


def _triangulate_polygon(
    corners: list[IndexTriple],
    positions: list[Vec3],
    normals: list[Vec3],
) -> tuple[list[tuple[IndexTriple, IndexTriple, IndexTriple]], bool]:
    """Triangulate one OBJ polygon without fan-created degenerate faces.

    Quads choose the diagonal that best preserves the supplied Maya normals.
    Larger polygons use deterministic ear clipping in the dominant projection.
    The boolean result reports whether the conservative recovery fallback was
    needed; callers surface that fact instead of silently claiming fidelity.
    """

    if len(corners) == 3:
        return [(corners[0], corners[1], corners[2])], False
    if len(corners) == 4:
        return _triangulate_quad(corners, positions, normals), False

    points = [positions[corner[0]] for corner in corners]
    projected = _project_polygon(points)
    signed_twice_area = sum(
        projected[index][0] * projected[(index + 1) % len(projected)][1]
        - projected[(index + 1) % len(projected)][0] * projected[index][1]
        for index in range(len(projected))
    )
    orientation = 1.0 if signed_twice_area >= 0.0 else -1.0
    remaining = list(range(len(corners)))
    triangles: list[tuple[IndexTriple, IndexTriple, IndexTriple]] = []
    guard = len(remaining) * len(remaining) * 2
    while len(remaining) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for offset, current in enumerate(tuple(remaining)):
            previous = remaining[(offset - 1) % len(remaining)]
            following = remaining[(offset + 1) % len(remaining)]
            if orientation * _cross_2d(projected[previous], projected[current], projected[following]) <= 1.0e-14:
                continue
            if _triangle_cross_squared(points[previous], points[current], points[following]) <= 1.0e-24:
                continue
            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle_2d(
                    projected[candidate],
                    projected[previous],
                    projected[current],
                    projected[following],
                    orientation,
                )
                for candidate in remaining
            ):
                continue
            triangles.append((corners[previous], corners[current], corners[following]))
            del remaining[offset]
            clipped = True
            break
        if not clipped:
            break
    if len(remaining) == 3 and _triangle_cross_squared(
        points[remaining[0]], points[remaining[1]], points[remaining[2]]
    ) > 1.0e-24:
        triangles.append(
            (corners[remaining[0]], corners[remaining[1]], corners[remaining[2]])
        )
    if len(triangles) == len(corners) - 2:
        return triangles, False

    # Recovery for malformed/self-intersecting projection: choose ears by
    # maximum 3D area while keeping source order.  This remains deterministic
    # and avoids the known fan diagonal, but is explicitly reported.
    remaining = list(range(len(corners)))
    triangles = []
    while len(remaining) > 3:
        candidates: list[tuple[float, float, int, int, int, int]] = []
        for offset, current in enumerate(remaining):
            previous = remaining[(offset - 1) % len(remaining)]
            following = remaining[(offset + 1) % len(remaining)]
            triangle = (corners[previous], corners[current], corners[following])
            area = _triangle_cross_squared(points[previous], points[current], points[following])
            alignment = _source_normal_alignment(triangle, positions, normals)
            candidates.append((area, alignment, -offset, previous, current, following))
        area, _alignment, neg_offset, previous, current, following = max(candidates)
        if area <= 1.0e-24:
            break
        triangles.append((corners[previous], corners[current], corners[following]))
        del remaining[-neg_offset]
    if len(remaining) == 3:
        triangles.append((corners[remaining[0]], corners[remaining[1]], corners[remaining[2]]))
    return triangles, True


def _safe_surface_name(group_name: str, material_name: str, ordinal: int) -> str:
    source = material_name or group_name or f"surface_{ordinal}"
    leaf = source.rsplit(":", 1)[-1]
    clean = re.sub(r"[^0-9A-Za-z_]+", "_", leaf).strip("_") or f"surface_{ordinal}"
    return clean[:32]


def _parse_map_path(raw_value: str) -> str:
    """Return the filename portion of a common MTL map declaration.

    Maya's files normally contain only a path.  For interoperable files, skip
    the standard fixed-arity map options while retaining quoted paths with
    spaces.  Unknown options are left alone rather than silently consuming a
    possible filename.
    """

    try:
        tokens = shlex.split(raw_value, posix=False)
    except ValueError:
        tokens = raw_value.split()
    if not tokens:
        return ""
    option_arity = {
        "-blendu": 1,
        "-blendv": 1,
        "-boost": 1,
        "-bm": 1,
        "-cc": 1,
        "-clamp": 1,
        "-imfchan": 1,
        "-mm": 2,
        "-o": 3,
        "-s": 3,
        "-t": 3,
        "-texres": 1,
        "-type": 1,
    }
    index = 0
    while index < len(tokens) and str(tokens[index]).lower() in option_arity:
        index += 1 + option_arity[str(tokens[index]).lower()]
    return " ".join(tokens[index:]).strip().strip('"')


def _parse_mtl_files(paths: Iterable[Path]) -> tuple[ObjRoomMaterial, ...]:
    rows: dict[str, dict[str, object]] = {}
    for path in paths:
        if not path.is_file():
            continue
        current = ""
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                command, _separator, remainder = stripped.partition(" ")
                key = command.lower()
                if key == "newmtl":
                    current = remainder.strip()
                    if current:
                        rows.setdefault(current, {})
                    continue
                if not current:
                    continue
                tokens = stripped.split()
                if key in {"kd", "ka"} and len(tokens) >= 4:
                    try:
                        rows[current]["diffuse" if key == "kd" else "ambient"] = (
                            float(tokens[1]),
                            float(tokens[2]),
                            float(tokens[3]),
                        )
                    except ValueError:
                        pass
                elif key == "map_kd":
                    texture = _parse_map_path(remainder)
                    texture_path = Path(texture)
                    if texture and not texture_path.is_absolute():
                        texture_path = path.parent / texture_path
                    rows[current]["diffuse_texture"] = texture
                    rows[current]["diffuse_texture_path"] = str(texture_path.resolve()) if texture else ""
    return tuple(
        ObjRoomMaterial(
            name=name,
            diffuse=tuple(values.get("diffuse", (0.8, 0.8, 0.8))),
            ambient=tuple(values.get("ambient", (0.2, 0.2, 0.2))),
            diffuse_texture=str(values.get("diffuse_texture", "")),
            diffuse_texture_path=str(values.get("diffuse_texture_path", "")),
        )
        for name, values in rows.items()
    )


def load_obj_room_document(path: str | Path, *, flip_v: bool = True) -> ObjRoomDocument:
    """Parse an OBJ into deterministic compact group/material surfaces.

    Faces are fan-triangulated in source order.  Position/UV/normal index
    tuples are compacted per material surface, preserving hard normals and UV
    seams.  OBJ negative indices are resolved at the point they are read.
    """

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"OBJ source does not exist: {source}")
    if source.suffix.lower() != ".obj":
        raise ObjRoomImportError("Map Studio room import requires an .obj file.")

    positions: list[Vec3] = []
    texcoords: list[Vec2] = []
    normals: list[Vec3] = []
    buckets: dict[tuple[str, str], list[tuple[IndexTriple, IndexTriple, IndexTriple]]] = {}
    mtllib_names: list[str] = []
    warnings: list[str] = []
    units_hint = ""
    group_name = "default"
    material_name = ""
    source_face_count = 0
    triangle_count = 0
    degenerate_faces = 0
    triangulation_fallbacks = 0

    with source.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, raw in enumerate(stream, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if not units_hint:
                    units_hint = _unit_hint(stripped[1:])
                continue
            command, _separator, remainder = stripped.partition(" ")
            key = command.lower()
            tokens = stripped.split()
            if key == "v":
                positions.append(_parse_vec3(tokens, line_number=line_number, label="vertex"))
            elif key == "vt":
                try:
                    u = float(tokens[1])
                    v = float(tokens[2])
                except (IndexError, ValueError) as exc:
                    raise ObjRoomImportError(
                        f"OBJ line {line_number} has an invalid texture-coordinate record."
                    ) from exc
                texcoords.append((u, 1.0 - v if flip_v else v))
            elif key == "vn":
                normals.append(_normalise(_parse_vec3(tokens, line_number=line_number, label="normal")))
            elif key in {"g", "o"}:
                group_name = remainder.strip() or "default"
            elif key == "usemtl":
                material_name = remainder.strip()
            elif key == "mtllib":
                try:
                    names = shlex.split(remainder, posix=False)
                except ValueError:
                    names = remainder.split()
                mtllib_names.extend(name.strip('"') for name in names if name.strip('"'))
            elif key == "f":
                source_face_count += 1
                corners = [
                    _face_vertex(
                        token,
                        vertex_count=len(positions),
                        texcoord_count=len(texcoords),
                        normal_count=len(normals),
                        line_number=line_number,
                    )
                    for token in tokens[1:]
                ]
                if len(corners) < 3:
                    warnings.append(f"Skipped OBJ line {line_number}: face has fewer than three corners.")
                    continue
                bucket = buckets.setdefault((group_name, material_name), [])
                triangles, used_fallback = _triangulate_polygon(corners, positions, normals)
                triangulation_fallbacks += int(used_fallback)
                for triangle in triangles:
                    if len({triangle[0][0], triangle[1][0], triangle[2][0]}) < 3 or _triangle_cross_squared(
                        positions[triangle[0][0]],
                        positions[triangle[1][0]],
                        positions[triangle[2][0]],
                    ) <= 1.0e-24:
                        degenerate_faces += 1
                        continue
                    bucket.append(triangle)
                    triangle_count += 1

    if not positions:
        raise ObjRoomImportError(f"OBJ {source.name} contains no vertices.")
    if triangle_count <= 0:
        raise ObjRoomImportError(f"OBJ {source.name} contains no usable triangle faces.")
    if degenerate_faces:
        warnings.append(f"Skipped {degenerate_faces} degenerate triangle(s) with repeated position indices.")
    if triangulation_fallbacks:
        warnings.append(
            f"Recovered {triangulation_fallbacks} non-simple polygon(s) with the conservative 3D ear fallback; "
            "review those surfaces before engine export."
        )

    mtllib_paths = tuple((source.parent / name).resolve() for name in dict.fromkeys(mtllib_names))
    materials = _parse_mtl_files(mtllib_paths)
    material_names = {item.name for item in materials}
    used_material_names = {key[1] for key, faces in buckets.items() if faces and key[1]}
    for missing in sorted(used_material_names - material_names):
        warnings.append(f'OBJ uses material "{missing}" but no companion MTL declaration was found.')
    for material in materials:
        if material.name in used_material_names and material.diffuse_texture and not material.texture_exists:
            warnings.append(
                f'Material "{material.name}" references missing diffuse texture {material.diffuse_texture!r}.'
            )
    for mtl_path in mtllib_paths:
        if not mtl_path.is_file():
            warnings.append(f"Missing companion material library: {mtl_path}")

    surfaces: list[ObjRoomSurface] = []
    for ordinal, ((surface_group, surface_material), triangles) in enumerate(buckets.items()):
        if not triangles:
            continue
        index_map: dict[IndexTriple, int] = {}
        surface_vertices: list[Vec3] = []
        surface_uvs: list[Vec2] = []
        surface_normals: list[Vec3] = []
        surface_faces: list[Face] = []
        all_have_uvs = True
        all_have_normals = True

        def compact(corner: IndexTriple) -> int:
            nonlocal all_have_uvs, all_have_normals
            existing = index_map.get(corner)
            if existing is not None:
                return existing
            index = len(surface_vertices)
            index_map[corner] = index
            vi, vti, vni = corner
            surface_vertices.append(positions[vi])
            if vti >= 0:
                surface_uvs.append(texcoords[vti])
            else:
                all_have_uvs = False
                surface_uvs.append((0.0, 0.0))
            if vni >= 0:
                surface_normals.append(normals[vni])
            else:
                all_have_normals = False
                surface_normals.append((0.0, 0.0, 0.0))
            return index

        for triangle in triangles:
            surface_faces.append(tuple(compact(corner) for corner in triangle))
        final_normals = (
            tuple(surface_normals)
            if all_have_normals
            else _generated_vertex_normals(surface_vertices, surface_faces)
        )
        surfaces.append(
            ObjRoomSurface(
                name=_safe_surface_name(surface_group, surface_material, ordinal),
                group_name=surface_group,
                material_name=surface_material,
                vertices=tuple(surface_vertices),
                faces=tuple(surface_faces),
                uvs=tuple(surface_uvs) if all_have_uvs else (),
                normals=final_normals,
            )
        )

    bounds_min = tuple(min(vertex[axis] for vertex in positions) for axis in range(3))
    bounds_max = tuple(max(vertex[axis] for vertex in positions) for axis in range(3))
    return ObjRoomDocument(
        source_path=str(source),
        mtllib_paths=tuple(str(path) for path in mtllib_paths),
        units_hint=units_hint,
        vertices_read=len(positions),
        texcoords_read=len(texcoords),
        normals_read=len(normals),
        source_face_count=source_face_count,
        triangle_count=triangle_count,
        bounds_min=tuple(float(value) for value in bounds_min),
        bounds_max=tuple(float(value) for value in bounds_max),
        materials=materials,
        surfaces=tuple(surfaces),
        warnings=tuple(dict.fromkeys(warnings)),
    )


__all__ = [
    "ObjRoomDocument",
    "ObjRoomImportError",
    "ObjRoomMaterial",
    "ObjRoomSurface",
    "load_obj_room_document",
]
