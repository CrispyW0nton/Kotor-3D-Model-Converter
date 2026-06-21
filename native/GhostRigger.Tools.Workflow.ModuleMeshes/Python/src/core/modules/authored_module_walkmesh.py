"""Module-wide generated WOK helpers for authored Map Studio projects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec
from .module_format import WOKData, WOKFace


@dataclass(frozen=True)
class AuthoredModuleWalkmesh:
    """Combined module-coordinate walkmesh compiled from authored rooms."""

    wok: WOKData
    room_count: int = 0
    source_rooms: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _room_offset(room: Any) -> tuple[float, float, float]:
    position = tuple(getattr(room, "position", ()) or ())
    if len(position) < 3:
        return (0.0, 0.0, 0.0)
    return (float(position[0]), float(position[1]), float(position[2]))


def _offset_vertex(vertex: Any, offset: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        float(vertex[0]) + float(offset[0]),
        float(vertex[1]) + float(offset[1]),
        float(vertex[2]) + float(offset[2]),
    )


def combine_authored_module_walkmesh(project: AuthoredModuleProject) -> AuthoredModuleWalkmesh:
    """Compile all authored room WOKs into module-coordinate space."""

    combined = WOKData(name=f"{project.module_root}_combined")
    source_rooms: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    for room in tuple(project.rooms or ()):
        room_resref = room.normalised_resref()
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            blocking.append(f"Room {room_resref or '(unnamed)'} could not compile for module walkmesh: {exc}")
            continue
        source_wok = geometry.wok
        vertex_offset = len(combined.verts)
        face_offset = len(combined.faces)
        position_offset = _room_offset(room)
        combined.verts.extend(_offset_vertex(vertex, position_offset) for vertex in tuple(source_wok.verts or ()))
        for face in tuple(source_wok.faces or ()):
            combined.faces.append(
                WOKFace(
                    int(face.v1) + vertex_offset,
                    int(face.v2) + vertex_offset,
                    int(face.v3) + vertex_offset,
                    int(face.surface),
                    int(face.adj1) + face_offset if int(face.adj1) >= 0 else -1,
                    int(face.adj2) + face_offset if int(face.adj2) >= 0 else -1,
                    int(face.adj3) + face_offset if int(face.adj3) >= 0 else -1,
                )
            )
        source_rooms.append(room_resref)
        if position_offset != (0.0, 0.0, 0.0):
            warnings.append(
                f"Room {room_resref or '(unnamed)'} WOK was offset to module coordinates at "
                f"({position_offset[0]:.3f}, {position_offset[1]:.3f}, {position_offset[2]:.3f})."
            )

    if not combined.faces and not blocking:
        blocking.append("Authored module has no generated room WOK faces.")
    return AuthoredModuleWalkmesh(
        wok=combined,
        room_count=len(source_rooms),
        source_rooms=tuple(source_rooms),
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


__all__ = [
    "AuthoredModuleWalkmesh",
    "combine_authored_module_walkmesh",
]
