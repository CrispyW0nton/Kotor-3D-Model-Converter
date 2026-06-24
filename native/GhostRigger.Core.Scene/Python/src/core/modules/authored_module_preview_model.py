"""Build a live viewport model from authored Map Studio geometry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, compile_authored_room_spec
from .authored_room_geometry import PrimitiveMesh


@dataclass(frozen=True)
class AuthoredModulePreviewModelResult:
    """Result for the live Map Studio mesh preview."""

    model: Any | None
    room_count: int = 0
    mesh_count: int = 0
    warnings: tuple[str, ...] = ()


def _import_model_data() -> Any:
    try:
        from src.core.geometry import model_data as md  # type: ignore

        return md
    except Exception:
        from core.geometry import model_data as md  # type: ignore

        return md


def _vec3(value: object) -> tuple[float, float, float]:
    try:
        x, y, z = tuple(value)[:3]  # type: ignore[arg-type]
    except Exception:
        return (0.0, 0.0, 0.0)
    return (float(x), float(y), float(z))


def _round_tuple(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(round(float(value), 5) for value in values)


def _point_summary(points: tuple[tuple[float, float, float], ...]) -> dict[str, object]:
    if not points:
        return {"count": 0}
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    zs = [float(point[2]) for point in points]
    return {
        "count": len(points),
        "min": _round_tuple((min(xs), min(ys), min(zs))),
        "max": _round_tuple((max(xs), max(ys), max(zs))),
        "sum": _round_tuple((sum(xs), sum(ys), sum(zs))),
        "first": _round_tuple(tuple(float(value) for value in points[0][:3])),
        "last": _round_tuple(tuple(float(value) for value in points[-1][:3])),
    }


def _face_summary(faces: tuple[tuple[int, int, int], ...]) -> dict[str, object]:
    if not faces:
        return {"count": 0}
    sums = (
        sum(int(face[0]) for face in faces),
        sum(int(face[1]) for face in faces),
        sum(int(face[2]) for face in faces),
    )
    return {
        "count": len(faces),
        "sum": sums,
        "first": tuple(int(value) for value in faces[0][:3]),
        "last": tuple(int(value) for value in faces[-1][:3]),
    }


def _mesh_signature(mesh: PrimitiveMesh) -> dict[str, object]:
    vertices = tuple(mesh.vertices or ())
    faces = tuple(mesh.faces or ())
    return {
        "name": str(mesh.name or ""),
        "vertices": _point_summary(vertices),
        "faces": _face_summary(faces),
        "texture": str(mesh.texture or ""),
        "diffuse": _round_tuple(tuple(float(value) for value in mesh.diffuse[:3])),
        "ambient": _round_tuple(tuple(float(value) for value in mesh.ambient[:3])),
    }


def _preview_key(signature_rows: list[dict[str, object]]) -> str:
    payload = json.dumps(signature_rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _mesh_node(md: Any, mesh: PrimitiveMesh, parent: Any, *, room_resref: str, role: str) -> Any:
    vertices = [tuple(float(value) for value in point[:3]) for point in tuple(mesh.vertices or ())]
    faces = [tuple(int(value) for value in face[:3]) for face in tuple(mesh.faces or ())]
    normals = [tuple(float(value) for value in normal[:3]) for normal in tuple(mesh.normals or ())]
    if len(normals) != len(vertices):
        normals = [(0.0, 0.0, 1.0)] * len(vertices)
    uvs = [tuple(float(value) for value in uv[:2]) for uv in tuple(mesh.uvs or ())]
    if len(uvs) != len(vertices):
        uvs = [(0.0, 0.0)] * len(vertices)
    texture = str(mesh.texture or "")
    node = md.ModelNode(
        name=str(mesh.name or f"{room_resref}_{role}"),
        flags=int(md.NodeFlags.MESH),
        vertices=vertices,
        normals=normals,
        uvs=uvs,
        faces=faces,
        face_mats=[0] * len(faces),
        texture=texture,
        texture_names=[texture] if texture else [],
        tex_count=1,
        diffuse=tuple(float(value) for value in mesh.diffuse[:3]),
        ambient=tuple(float(value) for value in mesh.ambient[:3]),
        vertex_space=0,
    )
    node.parent = parent
    setattr(node, "_gr_map_studio_room_resref", room_resref)
    setattr(node, "_gr_map_studio_mesh_role", role)
    setattr(node, "_gr_map_studio_authored_mesh", True)
    node.compute_bounds()
    return node


def _room_signature(room: AuthoredRoomSpec, meshes: tuple[PrimitiveMesh, ...]) -> dict[str, object]:
    return {
        "room": str(room.room_resref or ""),
        "position": _round_tuple(_vec3(room.position)),
        "meshes": [_mesh_signature(mesh) for mesh in meshes],
    }


def build_authored_module_preview_model(project: AuthoredModuleProject) -> AuthoredModulePreviewModelResult:
    """Compile authored KMAP room geometry into the viewport's normal KotorModel path."""

    md = _import_model_data()
    root = md.ModelNode(name=str(project.module_root or "map_studio_preview"), flags=int(md.NodeFlags.HEADER))
    warnings: list[str] = []
    signature_rows: list[dict[str, object]] = []
    room_count = 0
    mesh_count = 0

    for room in tuple(project.rooms or ()):
        room_resref = str(room.room_resref or "room")
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            warnings.append(f"Room {room_resref} could not compile for preview: {exc}")
            continue
        meshes = (geometry.room_mesh,) + tuple(geometry.helper_meshes or ())
        meshes = tuple(mesh for mesh in meshes if mesh.vertices and mesh.faces)
        if not meshes:
            warnings.append(f"Room {room_resref} has no previewable render mesh.")
            continue

        compiled_resref = str(geometry.room_resref or room_resref)
        room_node = md.ModelNode(
            name=compiled_resref,
            flags=int(md.NodeFlags.HEADER),
            position=_vec3(room.position),
        )
        room_node.parent = root
        setattr(room_node, "_gr_map_studio_room_resref", compiled_resref)
        setattr(room_node, "_gr_map_studio_authored_room", True)
        for index, mesh in enumerate(meshes):
            role = "render" if index == 0 else str(getattr(mesh, "metadata", {}).get("role", "") or f"helper_{index}")
            room_node.children.append(_mesh_node(md, mesh, room_node, room_resref=compiled_resref, role=role))
            mesh_count += 1
        root.children.append(room_node)
        room_count += 1
        signature_rows.append(_room_signature(room, meshes))

    if mesh_count <= 0:
        return AuthoredModulePreviewModelResult(model=None, room_count=room_count, mesh_count=0, warnings=tuple(warnings))

    model = md.KotorModel(
        name=str(project.module_root or "map_studio_preview"),
        supermodel="NULL",
        classification="area",
        game_version=md.GameVersion.K2 if str(project.game).upper() == "K2" else md.GameVersion.K1,
        model_type=int(md.ModelClassification.EFFECT),
        root_node=root,
    )
    model.disable_fog = True
    try:
        model.compute_all_tangents()
    except Exception:
        pass
    model.compute_bounds()
    key = _preview_key(signature_rows)
    setattr(model, "_gr_map_studio_preview_model", True)
    setattr(model, "_gr_map_studio_preview_key", key)
    setattr(model, "_gr_map_studio_preview_summary", {"rooms": room_count, "meshes": mesh_count, "warnings": tuple(warnings)})
    return AuthoredModulePreviewModelResult(model=model, room_count=room_count, mesh_count=mesh_count, warnings=tuple(warnings))
