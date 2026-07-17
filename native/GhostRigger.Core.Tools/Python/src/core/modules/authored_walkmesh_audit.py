"""Headless WOK topology audits for authored Map Studio modules."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface


MAX_WALKABLE_SLOPE_DEGREES = 45.0
DOOR_TRANSITION_SURFACE_ID = 18
EMPIRICAL_STOCK_WOK_FACE_MAX = 2_136


@dataclass(frozen=True)
class AuthoredWalkmeshAudit:
    """Room-level generated WOK safety facts for readiness/export gates."""

    room_resref: str
    face_count: int = 0
    walkable_face_count: int = 0
    non_walk_face_count: int = 0
    walkable_component_count: int = 0
    largest_walkable_component_faces: int = 0
    invalid_face_count: int = 0
    degenerate_face_count: int = 0
    non_manifold_edge_count: int = 0
    open_edge_count: int = 0
    transition_surface_face_count: int = 0
    steep_walkable_face_count: int = 0
    max_walkable_slope_degrees: float = 0.0
    max_allowed_walkable_slope_degrees: float = MAX_WALKABLE_SLOPE_DEGREES
    ready: bool = False
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()

    @property
    def disconnected_component_count(self) -> int:
        """Return extra walkable islands beyond the primary connected island."""

        return max(0, int(self.walkable_component_count) - 1)


def _face_vertices(face: Any) -> tuple[int, int, int]:
    return int(face.v1), int(face.v2), int(face.v3)


def _is_walkable(face: Any) -> bool:
    return is_walkable_walkmesh_surface(int(getattr(face, "surface", -1)))


def _edge_key(a: int, b: int) -> tuple[int, int]:
    """Return an edge key in the WOK's explicit vertex-index topology.

    Coincident coordinates are not sufficient evidence that two Odyssey WOK
    vertices are connected. Vanilla rooms intentionally duplicate vertices at
    collision seams, so coordinate keys invent adjacencies and hide real
    perimeter edges.
    """

    return (a, b) if a <= b else (b, a)


def _triangle_area(verts: tuple[Any, ...], face: Any) -> float:
    a_idx, b_idx, c_idx = _face_vertices(face)
    ax, ay, az = (float(value) for value in verts[a_idx])
    bx, by, bz = (float(value) for value in verts[b_idx])
    cx, cy, cz = (float(value) for value in verts[c_idx])
    ab = (bx - ax, by - ay, bz - az)
    ac = (cx - ax, cy - ay, cz - az)
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2])


def _face_slope_degrees(verts: tuple[Any, ...], face: Any) -> float:
    a_idx, b_idx, c_idx = _face_vertices(face)
    ax, ay, az = (float(value) for value in verts[a_idx])
    bx, by, bz = (float(value) for value in verts[b_idx])
    cx, cy, cz = (float(value) for value in verts[c_idx])
    ab = (bx - ax, by - ay, bz - az)
    ac = (cx - ax, cy - ay, cz - az)
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2])
    if length <= 1.0e-12:
        return 90.0
    z_axis_alignment = min(1.0, max(0.0, abs(normal[2]) / length))
    return math.degrees(math.acos(z_axis_alignment))


def _face_is_valid(verts: tuple[Any, ...], face: Any) -> bool:
    indices = _face_vertices(face)
    return all(0 <= index < len(verts) for index in indices)


def _face_is_degenerate(verts: tuple[Any, ...], face: Any) -> bool:
    indices = _face_vertices(face)
    if len(set(indices)) < 3:
        return True
    return _triangle_area(verts, face) <= 1.0e-8


def audit_authored_wok(room_resref: str, wok: Any) -> AuthoredWalkmeshAudit:
    """Audit generated WOK topology without mutating the room or walkmesh."""

    resref = str(room_resref or "").strip().lower()
    verts = tuple(getattr(wok, "verts", ()) or ())
    faces = tuple(getattr(wok, "faces", ()) or ())
    face_count = len(faces)
    walkable_face_count = sum(1 for face in faces if _is_walkable(face))
    non_walk_face_count = max(0, face_count - walkable_face_count)

    invalid_faces: set[int] = set()
    degenerate_faces: set[int] = set()
    steep_walkable_faces: set[int] = set()
    walkable_faces: set[int] = set()
    transition_surface_face_count = 0
    max_walkable_slope = 0.0
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)

    for face_index, face in enumerate(faces):
        if not _face_is_valid(verts, face):
            invalid_faces.add(face_index)
            continue
        if _face_is_degenerate(verts, face):
            degenerate_faces.add(face_index)
            continue
        if int(getattr(face, "surface", -1)) == DOOR_TRANSITION_SURFACE_ID:
            transition_surface_face_count += 1
        if not _is_walkable(face):
            continue
        walkable_faces.add(face_index)
        slope = _face_slope_degrees(verts, face)
        max_walkable_slope = max(max_walkable_slope, float(slope))
        if slope > MAX_WALKABLE_SLOPE_DEGREES:
            steep_walkable_faces.add(face_index)
        a_idx, b_idx, c_idx = _face_vertices(face)
        for edge in ((a_idx, b_idx), (b_idx, c_idx), (c_idx, a_idx)):
            edge_faces[_edge_key(edge[0], edge[1])].append(face_index)

    adjacency: dict[int, set[int]] = {face_index: set() for face_index in walkable_faces}
    non_manifold_edge_count = 0
    open_edge_count = 0
    for connected_faces in edge_faces.values():
        unique_faces = sorted(set(connected_faces))
        if len(unique_faces) == 1:
            open_edge_count += 1
        if len(unique_faces) > 2:
            non_manifold_edge_count += 1
        for left in unique_faces:
            for right in unique_faces:
                if left != right:
                    adjacency[left].add(right)

    for face_index in walkable_faces:
        face = faces[face_index]
        for adjacent_index in (
            int(getattr(face, "adj1", -1)),
            int(getattr(face, "adj2", -1)),
            int(getattr(face, "adj3", -1)),
        ):
            if adjacent_index in walkable_faces:
                adjacency[face_index].add(adjacent_index)
                adjacency[adjacent_index].add(face_index)

    components: list[int] = []
    remaining = set(walkable_faces)
    while remaining:
        start = remaining.pop()
        count = 1
        queue: deque[int] = deque((start,))
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    count += 1
                    queue.append(neighbor)
        components.append(count)

    component_count = len(components)
    largest_component = max(components) if components else 0
    blocking: list[str] = []
    warnings: list[str] = []
    label = resref or "(unnamed room)"
    if walkable_face_count <= 0:
        blocking.append(f"Room {label} generated WOK has no walkable faces.")
    if invalid_faces:
        blocking.append(f"Room {label} generated WOK has {len(invalid_faces)} face(s) with invalid vertex indices.")
    # Degenerate/non-manifold/steep/island findings are advisory: vanilla
    # BioWare WOKs ship all of them (001ebo alone has degenerate faces, a
    # >45deg walkable face, and intentionally disconnected walkable islands)
    # and run fine in game, so stock round-trips must not be vetoed by them.
    if degenerate_faces:
        warnings.append(f"Room {label} generated WOK has {len(degenerate_faces)} degenerate face(s).")
    if non_manifold_edge_count:
        warnings.append(f"Room {label} generated WOK has {non_manifold_edge_count} non-manifold walkable edge(s).")
    if open_edge_count:
        warnings.append(
            f"Room {label} generated WOK has {open_edge_count} open/boundary walkable edge(s); "
            "confirm each one is an intentional room perimeter, doorway seam, or transition boundary before export."
        )
    if steep_walkable_faces:
        warnings.append(
            f"Room {label} generated WOK has {len(steep_walkable_faces)} walkable face(s) steeper than "
            f"{MAX_WALKABLE_SLOPE_DEGREES:.1f} degrees; paint them blocked/ramp-safe if creatures should not path there."
        )
    if component_count > 1:
        warnings.append(
            f"Room {label} generated WOK has {component_count} disconnected walkable island(s); "
            "bridge/weld/snap room floors if they should be one navigable area."
        )
    if face_count > EMPIRICAL_STOCK_WOK_FACE_MAX:
        warnings.append(
            f"Room {label} WOK has {face_count} faces, above the empirical stock-room maximum of "
            f"{EMPIRICAL_STOCK_WOK_FACE_MAX}; this render-resolution walkmesh was not decimated."
        )
    if face_count > 0 and walkable_face_count == face_count:
        warnings.append(f"Room {label} WOK is fully walkable; paint blockers for walls, pits, or out-of-bounds floor if needed.")

    return AuthoredWalkmeshAudit(
        room_resref=resref,
        face_count=face_count,
        walkable_face_count=walkable_face_count,
        non_walk_face_count=non_walk_face_count,
        walkable_component_count=component_count,
        largest_walkable_component_faces=largest_component,
        invalid_face_count=len(invalid_faces),
        degenerate_face_count=len(degenerate_faces),
        non_manifold_edge_count=non_manifold_edge_count,
        open_edge_count=open_edge_count,
        transition_surface_face_count=int(transition_surface_face_count),
        steep_walkable_face_count=len(steep_walkable_faces),
        max_walkable_slope_degrees=float(max_walkable_slope),
        ready=not blocking,
        warnings=tuple(warnings),
        blocking_messages=tuple(blocking),
    )


__all__ = [
    "AuthoredWalkmeshAudit",
    "DOOR_TRANSITION_SURFACE_ID",
    "EMPIRICAL_STOCK_WOK_FACE_MAX",
    "MAX_WALKABLE_SLOPE_DEGREES",
    "audit_authored_wok",
]
