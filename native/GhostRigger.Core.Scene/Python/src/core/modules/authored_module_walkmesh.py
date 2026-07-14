"""Module-wide generated WOK helpers for authored Map Studio projects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_imported_mesh import authored_room_uses_unresolved_stock_geometry
from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec
from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface
from .module_format import WOKData, WOKFace


@dataclass(frozen=True)
class AuthoredModuleWalkmesh:
    """Combined module-coordinate walkmesh compiled from authored rooms."""

    wok: WOKData
    room_count: int = 0
    source_rooms: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredWalkmeshSnapResult:
    """Nearest walkable point for one Map Studio world-space position."""

    position: tuple[float, float, float]
    face_index: int = -1
    surface_id: int = -1
    horizontal_distance: float = 0.0
    inside_face: bool = False


def _room_offset(room: Any) -> tuple[float, float, float]:
    position = tuple(getattr(room, "position", ()) or ())
    if len(position) < 3:
        return (0.0, 0.0, 0.0)
    return (float(position[0]), float(position[1]), float(position[2]))


def _room_wok_coordinate_space(room: Any) -> str:
    """Return the durable coordinate-space contract for one room WOK.

    Authored/generated room WOKs are room-local and receive the LYT position.
    Vanilla room WOKs are already stored in module/area coordinates (207TEL's
    PTH points align directly with the raw WOK), so adding the LYT position a
    second time is incorrect.  Older converted KMAPs predate the explicit
    metadata key; their stock-conversion provenance is a safe migration hint.
    """

    primitive = getattr(room, "primitive", None)
    primitive_metadata = dict(getattr(primitive, "metadata", {}) or {})
    room_metadata = dict(getattr(room, "metadata", {}) or {})
    value = str(
        primitive_metadata.get("wok_coordinate_space")
        or room_metadata.get("wok_coordinate_space")
        or ""
    ).strip().lower()
    if value in {"module", "module_space", "area", "area_space", "world", "world_space"}:
        return "module"
    if value in {"room", "room_local", "local", "local_space"}:
        return "room_local"
    if getattr(primitive, "wok", None) is not None and (
        str(room_metadata.get("source") or "").strip().lower() in {"stock_room_conversion", "stock_module_import"}
        or bool(primitive_metadata.get("imported_from"))
    ):
        return "module"
    return "room_local"


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
        room_metadata = dict(getattr(room, "metadata", {}) or {})
        if authored_room_uses_unresolved_stock_geometry(room):
            issue = str(room_metadata.get("stock_geometry_issue") or "stock room model is unavailable").strip()
            warnings.append(
                f"Room {room_resref or '(unnamed)'} was excluded from PIE collision because its stock geometry "
                f"could not be resolved ({issue})."
            )
            continue
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            blocking.append(f"Room {room_resref or '(unnamed)'} could not compile for module walkmesh: {exc}")
            continue
        source_wok = geometry.wok
        vertex_offset = len(combined.verts)
        face_offset = len(combined.faces)
        wok_coordinate_space = _room_wok_coordinate_space(room)
        position_offset = (0.0, 0.0, 0.0) if wok_coordinate_space == "module" else _room_offset(room)
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
                    int(getattr(face, "trans1", -1)),
                    int(getattr(face, "trans2", -1)),
                    int(getattr(face, "trans3", -1)),
                )
            )
        source_rooms.append(room_resref)
        if wok_coordinate_space == "module" and _room_offset(room) != (0.0, 0.0, 0.0):
            warnings.append(
                f"Room {room_resref or '(unnamed)'} uses a stock module-space WOK; "
                "its LYT position was not applied a second time."
            )
        elif position_offset != (0.0, 0.0, 0.0):
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


def _closest_barycentric_xy(
    point: tuple[float, float],
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> tuple[tuple[float, float, float], bool]:
    """Return barycentric weights for the closest XY point on a triangle."""

    px, py = point
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
    if abs(denominator) > 1.0e-12:
        wa = (((by - cy) * (px - cx)) + ((cx - bx) * (py - cy))) / denominator
        wb = (((cy - ay) * (px - cx)) + ((ax - cx) * (py - cy))) / denominator
        wc = 1.0 - wa - wb
        if min(wa, wb, wc) >= -1.0e-8:
            return (wa, wb, wc), True

    candidates: list[tuple[float, tuple[float, float, float]]] = []
    for start, end, start_weights, end_weights in (
        ((ax, ay), (bx, by), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((bx, by), (cx, cy), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((cx, cy), (ax, ay), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    ):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_sq = (dx * dx) + (dy * dy)
        t = 0.0 if length_sq <= 1.0e-12 else max(0.0, min(1.0, (((px - start[0]) * dx) + ((py - start[1]) * dy)) / length_sq))
        qx, qy = start[0] + (dx * t), start[1] + (dy * t)
        weights = tuple(start_weights[index] + ((end_weights[index] - start_weights[index]) * t) for index in range(3))
        candidates.append((((px - qx) ** 2) + ((py - qy) ** 2), weights))
    _distance_sq, weights = min(candidates, key=lambda candidate: candidate[0])
    return weights, False


def snap_position_to_authored_walkmesh(
    project: AuthoredModuleProject,
    position: Any,
    *,
    max_horizontal_distance: float | None = None,
    downward_only: bool = False,
) -> AuthoredWalkmeshSnapResult | None:
    """Snap a world-space point to the nearest walkable authored WOK face.

    XY proximity is the primary selector. When several stacked walkable faces
    contain the same XY point, the face nearest the supplied Z is chosen.
    ``downward_only`` implements Unreal-style End-key grounding: surfaces above
    the object are ignored, so stacked floors cannot pull the object upward.
    """

    values = tuple(position or ())
    if len(values) < 3:
        raise ValueError("Walkmesh snap position must contain X, Y, and Z values.")
    source = (float(values[0]), float(values[1]), float(values[2]))
    combined = combine_authored_module_walkmesh(project)
    best: tuple[tuple[float, float], AuthoredWalkmeshSnapResult] | None = None
    for face_index, face in enumerate(tuple(combined.wok.faces or ())):
        if not is_walkable_walkmesh_surface(int(face.surface)):
            continue
        try:
            a = combined.wok.verts[int(face.v1)]
            b = combined.wok.verts[int(face.v2)]
            c = combined.wok.verts[int(face.v3)]
        except (IndexError, TypeError, ValueError):
            continue
        weights, inside = _closest_barycentric_xy((source[0], source[1]), a, b, c)
        snapped = tuple(
            (float(a[axis]) * weights[0]) + (float(b[axis]) * weights[1]) + (float(c[axis]) * weights[2])
            for axis in range(3)
        )
        if bool(downward_only) and float(snapped[2]) > float(source[2]) + 1.0e-6:
            continue
        horizontal_distance = ((snapped[0] - source[0]) ** 2 + (snapped[1] - source[1]) ** 2) ** 0.5
        if max_horizontal_distance is not None and horizontal_distance > max(0.0, float(max_horizontal_distance)):
            continue
        result = AuthoredWalkmeshSnapResult(
            position=(snapped[0], snapped[1], snapped[2]),
            face_index=face_index,
            surface_id=int(face.surface),
            horizontal_distance=horizontal_distance,
            inside_face=inside,
        )
        score = (horizontal_distance, abs(snapped[2] - source[2]))
        if best is None or score < best[0]:
            best = (score, result)
    return best[1] if best is not None else None


__all__ = [
    "AuthoredModuleWalkmesh",
    "AuthoredWalkmeshSnapResult",
    "combine_authored_module_walkmesh",
    "snap_position_to_authored_walkmesh",
]
