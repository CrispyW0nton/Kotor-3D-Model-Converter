"""Headless primitive mesh generation for the Mesh Tools workbench."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


@dataclass(slots=True)
class PrimitiveMeshData:
    name: str
    primitive: str
    vertices: list[Vec3]
    faces: list[Face]
    normals: list[Vec3] = field(default_factory=list)
    uvs: list[Vec2] = field(default_factory=list)
    face_mats: list[int] = field(default_factory=list)
    material: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_primitive_mesh(primitive: str, options: dict[str, Any] | None = None) -> PrimitiveMeshData:
    """Build renderer-ready triangle mesh data for one modeling primitive."""

    opts = dict(options or {})
    kind = _normalise_kind(primitive)
    name = str(opts.get("name") or kind.title()).strip() or kind.title()
    material = str(opts.get("material") or opts.get("default_material") or "").strip()
    if kind == "floor":
        mesh = _box(name, _dims(opts, (4.0, 4.0, 0.08)), material)
    elif kind == "wall":
        mesh = _box(name, _dims(opts, (4.0, 0.16, 2.5)), material)
    elif kind == "cube":
        mesh = _box(name, _dims(opts, (1.0, 1.0, 1.0)), material)
    elif kind == "cylinder":
        mesh = _cylinder(name, _dims(opts, (1.0, 1.0, 2.0)), int(opts.get("segments", 24) or 24), material)
    elif kind == "arch":
        mesh = _arch(name, _dims(opts, (3.0, 0.35, 3.0)), int(opts.get("segments", 12) or 12), material)
    elif kind == "ramp":
        mesh = _ramp(name, _dims(opts, (3.0, 2.0, 1.0)), material)
    elif kind == "stairs":
        mesh = _stairs(name, _dims(opts, (3.0, 2.0, 1.5)), int(opts.get("steps", opts.get("segments", 5)) or 5), material)
    else:
        raise ValueError(f"Unsupported primitive: {primitive}")
    mesh.primitive = kind
    mesh.metadata.update(
        {
            "primitive": kind,
            "uv_policy": "Generated box/cylindrical UVs normalized per primitive.",
            "material_policy": "All generated faces use material slot 0 unless edited later.",
            "normal_policy": "Vertex normals are regenerated from geometric face normals.",
        }
    )
    return _finalise(mesh)


def _normalise_kind(value: str) -> str:
    text = str(value or "").strip().lower().replace("create_", "")
    aliases = {"box": "cube", "plane": "floor"}
    return aliases.get(text, text)


def _dims(options: dict[str, Any], default: Vec3) -> Vec3:
    raw = options.get("dimensions", options.get("size", default))
    if isinstance(raw, dict):
        values = (raw.get("x", raw.get("width", default[0])), raw.get("y", raw.get("depth", default[1])), raw.get("z", raw.get("height", default[2])))
    else:
        values = raw
    try:
        seq = list(values)
        dims = tuple(max(1.0e-5, abs(float(seq[i]))) for i in range(3))
        return dims  # type: ignore[return-value]
    except Exception:
        return default


def _box(name: str, dims: Vec3, material: str) -> PrimitiveMeshData:
    x, y, z = (value * 0.5 for value in dims)
    vertices = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    faces = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return PrimitiveMeshData(name, "box", vertices, faces, material=material)


def _cylinder(name: str, dims: Vec3, segments: int, material: str) -> PrimitiveMeshData:
    segments = max(3, min(128, int(segments)))
    rx, ry, h = dims[0] * 0.5, dims[1] * 0.5, dims[2] * 0.5
    vertices: list[Vec3] = [(0.0, 0.0, -h), (0.0, 0.0, h)]
    for z in (-h, h):
        for index in range(segments):
            a = (math.tau * index) / segments
            vertices.append((math.cos(a) * rx, math.sin(a) * ry, z))
    faces: list[Face] = []
    for index in range(segments):
        nxt = (index + 1) % segments
        b0, b1 = 2 + index, 2 + nxt
        t0, t1 = 2 + segments + index, 2 + segments + nxt
        faces.extend([(0, b1, b0), (1, t0, t1), (b0, b1, t1), (b0, t1, t0)])
    return PrimitiveMeshData(name, "cylinder", vertices, faces, material=material)


def _arch(name: str, dims: Vec3, segments: int, material: str) -> PrimitiveMeshData:
    segments = max(4, min(64, int(segments)))
    width, depth, height = dims
    radius = width * 0.5
    spring = max(0.0, height - radius)
    d = depth * 0.5
    profile: list[tuple[float, float]] = [(-radius, 0.0)]
    for index in range(segments + 1):
        a = math.pi - (math.pi * index / segments)
        profile.append((math.cos(a) * radius, spring + math.sin(a) * radius))
    profile.append((radius, 0.0))
    vertices = [(x, -d, z) for x, z in profile] + [(x, d, z) for x, z in profile]
    faces: list[Face] = []
    count = len(profile)
    for index in range(count):
        nxt = (index + 1) % count
        faces.extend([(index, nxt, count + nxt), (index, count + nxt, count + index)])
    for index in range(1, count - 1):
        faces.append((0, index, index + 1))
        faces.append((count, count + index + 1, count + index))
    return PrimitiveMeshData(name, "arch", vertices, faces, material=material)


def _ramp(name: str, dims: Vec3, material: str) -> PrimitiveMeshData:
    x, y, z = dims[0] * 0.5, dims[1] * 0.5, dims[2]
    vertices = [(-x, -y, 0.0), (x, -y, 0.0), (x, y, 0.0), (-x, y, 0.0), (x, -y, z), (x, y, z)]
    faces = [(0, 2, 1), (0, 3, 2), (1, 2, 5), (1, 5, 4), (0, 1, 4), (0, 4, 3), (3, 4, 5), (3, 5, 2)]
    return PrimitiveMeshData(name, "ramp", vertices, faces, material=material)


def _stairs(name: str, dims: Vec3, steps: int, material: str) -> PrimitiveMeshData:
    steps = max(1, min(64, int(steps)))
    total_w, total_d, total_h = dims
    step_d = total_d / steps
    step_h = total_h / steps
    vertices: list[Vec3] = []
    faces: list[Face] = []
    x = total_w * 0.5
    y0 = -total_d * 0.5
    for index in range(steps):
        y = y0 + index * step_d
        z = index * step_h
        block = _box(f"{name}_step_{index + 1}", (total_w, step_d, (index + 1) * step_h), material)
        base = len(vertices)
        vertices.extend((vx, vy + y + step_d * 0.5, vz + ((index + 1) * step_h) * 0.5) for vx, vy, vz in block.vertices)
        faces.extend(tuple(base + vi for vi in face) for face in block.faces)
    mesh = PrimitiveMeshData(name, "stairs", vertices, faces, material=material)
    mesh.metadata["step_count"] = steps
    return mesh


def _finalise(mesh: PrimitiveMeshData) -> PrimitiveMeshData:
    mesh.face_mats = [0 for _ in mesh.faces]
    mesh.uvs = _planar_uvs(mesh.vertices)
    mesh.normals = _vertex_normals(mesh.vertices, mesh.faces)
    return mesh


def _planar_uvs(vertices: list[Vec3]) -> list[Vec2]:
    if not vertices:
        return []
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    min_x, min_y = min(xs), min(ys)
    width = max(max(xs) - min_x, 1.0e-7)
    depth = max(max(ys) - min_y, 1.0e-7)
    return [((x - min_x) / width, (y - min_y) / depth) for x, y, _z in vertices]


def _vertex_normals(vertices: list[Vec3], faces: list[Face]) -> list[Vec3]:
    accum = [[0.0, 0.0, 0.0] for _ in vertices]
    for face in faces:
        a, b, c = face
        if min(face) < 0 or max(face) >= len(vertices):
            continue
        normal = _face_normal(vertices[a], vertices[b], vertices[c])
        for vi in face:
            accum[vi][0] += normal[0]
            accum[vi][1] += normal[1]
            accum[vi][2] += normal[2]
    result = []
    for value in accum:
        length = math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])
        result.append((0.0, 0.0, 1.0) if length <= 1.0e-9 else (value[0] / length, value[1] / length, value[2] / length))
    return result


def _face_normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
    length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    return (0.0, 0.0, 1.0) if length <= 1.0e-9 else (n[0] / length, n[1] / length, n[2] / length)
