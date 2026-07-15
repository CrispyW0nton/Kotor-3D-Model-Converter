"""Map Studio hover-context picking contracts.

This module is deliberately headless and Qt-free.  It classifies what map
component the cursor currently hovers (vertex, edge, face, or walkmesh face)
from pre-projected screen-space candidates so the component marking menu
can build a context-sensitive action tree.

Conceptual owner: GhostRigger.Core.GUI.Helpers (viewport pickers).  The module
is packaged with the Map Studio core payloads (Scene/Tools) until a helpers
migration batch moves it; keep it free of GUI imports so that move stays cheap.

KOTOR contract: hover classification is read-only.  It never mutates authored
geometry, WOK data, or KMAP state.  Render-mesh hits and WOK hits are reported
as distinct component types because visible MDL geometry and walkmesh geometry
are independently auditable export resources.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Screen-space pickup tolerance for vertex/edge hover, in pixels.
DEFAULT_HOVER_TOLERANCE_PX = 5.0

#: Barycentric slack used for face containment tests.
_FACE_CONTAINMENT_EPSILON = -0.005

HOVER_COMPONENT_NONE = "none"
HOVER_COMPONENT_VERTEX = "vertex"
HOVER_COMPONENT_EDGE = "edge"
HOVER_COMPONENT_FACE = "face"
HOVER_COMPONENT_WALKMESH_FACE = "walkmesh_face"

HOVER_COMPONENT_TYPES: tuple[str, ...] = (
    HOVER_COMPONENT_VERTEX,
    HOVER_COMPONENT_EDGE,
    HOVER_COMPONENT_FACE,
    HOVER_COMPONENT_WALKMESH_FACE,
)


@dataclass(frozen=True)
class MapStudioHoverCandidateFace:
    """One pre-projected triangle the picker may classify under the cursor.

    ``screen_points`` and ``world_points`` must both contain exactly three
    entries.  ``walkable`` stays ``None`` for render geometry; WOK candidates
    set it to the face's walkable flag so the hover context can report
    walkmesh truth without re-reading the overlay.
    """

    room_resref: str
    mesh_role: str
    face_index: int
    screen_points: tuple[tuple[float, float], ...]
    world_points: tuple[tuple[float, float, float], ...]
    vertex_indices: tuple[int, int, int] = (-1, -1, -1)
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    material: str = ""
    walkable: bool | None = None
    depth: float = 0.0
    # Positive camera-space Z for each projected vertex.  Keeping the three
    # values (instead of only a triangle average) lets the picker evaluate the
    # surface at the cursor and prevents a large, distant triangle from
    # winning merely because one of its vertices is close to the camera.
    view_depths: tuple[float, ...] = ()
    # Base-map UVs use the same vertex indices as ``world_points``.  They are
    # optional because WOK candidates and some legacy preview meshes have no
    # texture channel.
    uv_points: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class MapStudioHoverContext:
    """What the Map Studio cursor currently hovers, in KOTOR resource terms."""

    component_type: str = HOVER_COMPONENT_NONE
    room_resref: str = ""
    mesh_role: str = ""
    face_index: int = -1
    # ``vertex_index`` / ``edge_indices`` are triangle-local corners kept for
    # existing component-operation callers.  The mesh-wide identities below
    # stay stable when the same shared component is reached from another face.
    vertex_index: int = -1
    edge_indices: tuple[int, int] = (-1, -1)
    mesh_vertex_index: int = -1
    mesh_edge_indices: tuple[int, int] = (-1, -1)
    adjacent_face_indices: tuple[int, ...] = ()
    is_border: bool = False
    world_point: tuple[float, float, float] = (0.0, 0.0, 0.0)
    face_normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    edge_direction: tuple[float, float, float] = (0.0, 0.0, 0.0)
    selector_origin_world_point: tuple[float, float, float] = (0.0, 0.0, 0.0)
    selector_world_point: tuple[float, float, float] = (0.0, 0.0, 0.0)
    selector_edge_corners: tuple[int, int] = (-1, -1)
    material: str = ""
    walkable: bool | None = None
    screen_distance: float = 0.0
    # Perspective-correct UV at ``world_point``.  Empty means the hovered
    # resource has no UV channel (for example, a WOK face).
    uv: tuple[float, ...] = ()
    view_depth: float = 0.0

    @property
    def is_hit(self) -> bool:
        return self.component_type in HOVER_COMPONENT_TYPES


@dataclass
class _BestHit:
    candidate: MapStudioHoverCandidateFace | None = None
    distance: float = math.inf
    depth: float = math.inf
    vertex_index: int = -1
    edge_indices: tuple[int, int] = (-1, -1)
    world_point: tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))
    uv: tuple[float, ...] = field(default=())


def _point_segment_distance(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float]:
    """Return (distance, t) from point to segment ab, with t clamped to [0, 1]."""

    dx = bx - ax
    dy = by - ay
    length_sq = (dx * dx) + (dy * dy)
    if length_sq <= 1.0e-12:
        return (math.hypot(px - ax, py - ay), 0.0)
    t = (((px - ax) * dx) + ((py - ay) * dy)) / length_sq
    t = max(0.0, min(1.0, t))
    cx = ax + (t * dx)
    cy = ay + (t * dy)
    return (math.hypot(px - cx, py - cy), t)


def _screen_triangle_barycentric(
    px: float,
    py: float,
    triangle: tuple[tuple[float, float], ...],
) -> tuple[float, float, float] | None:
    (ax, ay), (bx, by), (cx, cy) = triangle[:3]
    denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
    if abs(denominator) <= 1.0e-9:
        return None
    u = (((by - cy) * (px - cx)) + ((cx - bx) * (py - cy))) / denominator
    v = (((cy - ay) * (px - cx)) + ((ax - cx) * (py - cy))) / denominator
    w = 1.0 - u - v
    return (float(u), float(v), float(w))


def _candidate_view_depths(candidate: MapStudioHoverCandidateFace) -> tuple[float, float, float]:
    """Return the camera-space depth for each projected triangle corner.

    Older callers only supplied ``depth`` (the former triangle-average
    contract).  Repeating that value preserves their affine behavior while
    new viewport candidates get perspective-correct interpolation.
    """

    values = tuple(float(value) for value in tuple(getattr(candidate, "view_depths", ()) or ())[:3])
    if len(values) == 3 and all(math.isfinite(value) and value > 1.0e-12 for value in values):
        return values
    fallback = float(getattr(candidate, "depth", 0.0) or 0.0)
    return (fallback, fallback, fallback)


def _perspective_weights_and_depth(
    screen_weights: tuple[float, float, float],
    candidate: MapStudioHoverCandidateFace,
) -> tuple[tuple[float, float, float], float]:
    """Convert screen barycentrics to perspective-correct vertex weights."""

    depths = _candidate_view_depths(candidate)
    if all(math.isfinite(value) and value > 1.0e-12 for value in depths):
        weighted_inverse = tuple(float(weight) / depths[index] for index, weight in enumerate(screen_weights))
        denominator = sum(weighted_inverse)
        if denominator > 1.0e-12:
            weights = tuple(value / denominator for value in weighted_inverse)
            return (weights, 1.0 / denominator)
    # Compatibility path for tests/legacy candidates without per-vertex Z.
    weights = tuple(float(value) for value in screen_weights)
    depth = sum(weights[index] * depths[index] for index in range(3))
    return (weights, float(depth))


def _interpolate_world(
    candidate: MapStudioHoverCandidateFace,
    weights: tuple[float, float, float],
) -> tuple[float, float, float]:
    world = tuple(candidate.world_points)[:3]
    return tuple(
        sum(float(world[index][axis]) * weights[index] for index in range(3))
        for axis in range(3)
    )


def _interpolate_uv(
    candidate: MapStudioHoverCandidateFace,
    weights: tuple[float, float, float],
) -> tuple[float, ...]:
    points = tuple(getattr(candidate, "uv_points", ()) or ())[:3]
    if len(points) != 3 or any(len(tuple(point or ())) < 2 for point in points):
        return ()
    return tuple(
        sum(float(points[index][axis]) * weights[index] for index in range(3))
        for axis in range(2)
    )


def _same_candidate_face(
    first: MapStudioHoverCandidateFace | None,
    second: MapStudioHoverCandidateFace | None,
) -> bool:
    if first is None or second is None:
        return False
    return first is second or (
        str(first.room_resref or "") == str(second.room_resref or "")
        and str(first.mesh_role or "") == str(second.mesh_role or "")
        and int(first.face_index) == int(second.face_index)
        and (first.walkable is None) == (second.walkable is None)
    )


def _component_is_visible(
    candidate: MapStudioHoverCandidateFace,
    component_depth: float,
    nearest_face: _BestHit,
    face_depth_at_cursor: float | None,
) -> bool:
    """Reject a component when an opaque render face covers it at the cursor."""

    if nearest_face.candidate is None or _same_candidate_face(candidate, nearest_face.candidate):
        return True
    tested_depth = float(face_depth_at_cursor) if face_depth_at_cursor is not None else float(component_depth)
    # The projection path uses integer screen coordinates, so permit a tiny
    # numerical seam tolerance while still treating millimetre-scale stacked
    # surfaces as distinct at ordinary KOTOR room distances.
    epsilon = max(1.0e-4, abs(float(nearest_face.depth)) * 1.0e-5)
    return tested_depth <= float(nearest_face.depth) + epsilon


def _candidate_is_valid(candidate: MapStudioHoverCandidateFace) -> bool:
    return (
        len(tuple(candidate.screen_points or ())) >= 3
        and len(tuple(candidate.world_points or ())) >= 3
    )


def _mesh_vertex_indices(candidate: MapStudioHoverCandidateFace) -> tuple[int, int, int] | None:
    values = tuple(getattr(candidate, "vertex_indices", ()) or ())
    if len(values) < 3:
        return None
    result = (int(values[0]), int(values[1]), int(values[2]))
    return result if min(result) >= 0 else None


def _normalised_direction(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> tuple[float, float, float]:
    delta = (float(end[0]) - float(start[0]), float(end[1]) - float(start[1]), float(end[2]) - float(start[2]))
    length = math.sqrt((delta[0] * delta[0]) + (delta[1] * delta[1]) + (delta[2] * delta[2]))
    if length <= 1.0e-12:
        return (0.0, 0.0, 0.0)
    return (delta[0] / length, delta[1] / length, delta[2] / length)


def _face_selector(
    candidate: MapStudioHoverCandidateFace,
    px: float,
    py: float,
) -> tuple[tuple[int, int], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return the component face edge-selector line for the cursor position."""

    screen = tuple(candidate.screen_points)[:3]
    world = tuple(candidate.world_points)[:3]
    edge = min(
        ((index, (index + 1) % 3) for index in range(3)),
        key=lambda pair: _point_segment_distance(
            px,
            py,
            float(screen[pair[0]][0]),
            float(screen[pair[0]][1]),
            float(screen[pair[1]][0]),
            float(screen[pair[1]][1]),
        )[0],
    )
    center = tuple(sum(float(point[axis]) for point in world) / 3.0 for axis in range(3))
    midpoint = tuple((float(world[edge[0]][axis]) + float(world[edge[1]][axis])) * 0.5 for axis in range(3))
    return edge, center, midpoint, _normalised_direction(center, midpoint)


def _vertex_selector(
    candidate: MapStudioHoverCandidateFace,
    vertex_corner: int,
    px: float,
    py: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Choose the incident edge most aligned with the cursor around a vertex."""

    screen = tuple(candidate.screen_points)[:3]
    world = tuple(candidate.world_points)[:3]
    origin_screen = screen[vertex_corner]
    cursor_delta = (px - float(origin_screen[0]), py - float(origin_screen[1]))
    cursor_length = math.hypot(cursor_delta[0], cursor_delta[1])

    def score(other_corner: int) -> float:
        edge_delta = (
            float(screen[other_corner][0]) - float(origin_screen[0]),
            float(screen[other_corner][1]) - float(origin_screen[1]),
        )
        edge_length = math.hypot(edge_delta[0], edge_delta[1])
        if cursor_length <= 1.0e-9 or edge_length <= 1.0e-9:
            return -float(other_corner)
        return ((cursor_delta[0] * edge_delta[0]) + (cursor_delta[1] * edge_delta[1])) / (cursor_length * edge_length)

    other = max((index for index in range(3) if index != vertex_corner), key=score)
    target = tuple(float(value) for value in world[other])
    origin = tuple(float(value) for value in world[vertex_corner])
    return target, _normalised_direction(origin, target)


def _adjacent_faces_for_mesh_vertices(
    candidates: tuple[MapStudioHoverCandidateFace, ...],
    candidate: MapStudioHoverCandidateFace,
    required_vertices: frozenset[int],
) -> tuple[int, ...]:
    if not required_vertices:
        return (int(candidate.face_index),)
    faces = {
        int(other.face_index)
        for other in candidates
        if other.walkable is None
        and str(other.room_resref or "") == str(candidate.room_resref or "")
        and str(other.mesh_role or "") == str(candidate.mesh_role or "")
        and (indices := _mesh_vertex_indices(other)) is not None
        and required_vertices.issubset(frozenset(indices))
    }
    return tuple(sorted(faces)) or (int(candidate.face_index),)


def _mesh_vertex_is_border(
    candidates: tuple[MapStudioHoverCandidateFace, ...],
    candidate: MapStudioHoverCandidateFace,
    mesh_vertex_index: int,
) -> bool:
    edge_counts: dict[tuple[int, int], int] = {}
    for other in candidates:
        if (
            other.walkable is not None
            or str(other.room_resref or "") != str(candidate.room_resref or "")
            or str(other.mesh_role or "") != str(candidate.mesh_role or "")
        ):
            continue
        indices = _mesh_vertex_indices(other)
        if indices is None or mesh_vertex_index not in indices:
            continue
        for start in range(3):
            edge = tuple(sorted((indices[start], indices[(start + 1) % 3])))
            if mesh_vertex_index in edge:
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
    return any(count == 1 for count in edge_counts.values())


def pick_map_studio_hover_context(
    candidates,
    screen_x: float,
    screen_y: float,
    *,
    tolerance_px: float = DEFAULT_HOVER_TOLERANCE_PX,
    prefer_walkmesh: bool = False,
) -> MapStudioHoverContext:
    """Classify the hovered component from pre-projected face candidates.

    Priority: vertex within tolerance > edge within tolerance > face
    containment > none.  Vertex/edge classification only applies to render
    geometry; WOK candidates always classify as whole walkmesh faces because
    walkmesh editing operates on WOK faces, not WOK vertices, in this slice.

    ``prefer_walkmesh`` flips the render-over-walkmesh tie-break for callers
    in walkmesh/terrain component modes.
    """

    px = float(screen_x)
    py = float(screen_y)
    tolerance = max(0.0, float(tolerance_px))

    best_vertex = _BestHit()
    best_edge = _BestHit()
    best_render_face = _BestHit()
    best_walkmesh_face = _BestHit()

    candidate_items = tuple(candidate for candidate in tuple(candidates or ()) if _candidate_is_valid(candidate))
    # Resolve the nearest surface at the exact cursor pixel first.  Component
    # proximity is evaluated only after this pass so a perfectly aligned edge
    # or vertex on geometry behind that surface cannot steal the hover.
    face_depth_at_cursor: dict[int, float] = {}
    for candidate in candidate_items:
        screen_points = tuple(candidate.screen_points)[:3]
        bary = _screen_triangle_barycentric(px, py, screen_points)
        if bary is None or min(bary) < _FACE_CONTAINMENT_EPSILON:
            continue
        weights, hit_depth = _perspective_weights_and_depth(bary, candidate)
        face_depth_at_cursor[id(candidate)] = float(hit_depth)
        center_x = sum(point[0] for point in screen_points) / 3.0
        center_y = sum(point[1] for point in screen_points) / 3.0
        center_distance = math.hypot(px - center_x, py - center_y)
        target = best_walkmesh_face if candidate.walkable is not None else best_render_face
        if (hit_depth, center_distance) < (target.depth, target.distance):
            target.candidate = candidate
            target.distance = center_distance
            target.depth = float(hit_depth)
            target.world_point = _interpolate_world(candidate, weights)
            target.uv = _interpolate_uv(candidate, weights)

    for candidate in candidate_items:
        screen_points = tuple(candidate.screen_points)[:3]
        is_walkmesh = candidate.walkable is not None

        if not is_walkmesh:
            for index, (sx, sy) in enumerate(screen_points):
                distance = math.hypot(px - float(sx), py - float(sy))
                if distance > tolerance:
                    continue
                weights, component_depth = _perspective_weights_and_depth(
                    tuple(1.0 if corner == index else 0.0 for corner in range(3)),
                    candidate,
                )
                if not _component_is_visible(
                    candidate,
                    component_depth,
                    best_render_face,
                    face_depth_at_cursor.get(id(candidate)),
                ):
                    continue
                if (distance, component_depth) < (best_vertex.distance, best_vertex.depth):
                    best_vertex.candidate = candidate
                    best_vertex.distance = distance
                    best_vertex.depth = float(component_depth)
                    best_vertex.vertex_index = index
                    best_vertex.world_point = _interpolate_world(candidate, weights)
                    best_vertex.uv = _interpolate_uv(candidate, weights)

            for start_index in range(3):
                end_index = (start_index + 1) % 3
                ax, ay = screen_points[start_index]
                bx, by = screen_points[end_index]
                distance, t = _point_segment_distance(px, py, float(ax), float(ay), float(bx), float(by))
                if distance > tolerance:
                    continue
                screen_weights = [0.0, 0.0, 0.0]
                screen_weights[start_index] = 1.0 - t
                screen_weights[end_index] = t
                weights, component_depth = _perspective_weights_and_depth(tuple(screen_weights), candidate)
                if not _component_is_visible(
                    candidate,
                    component_depth,
                    best_render_face,
                    face_depth_at_cursor.get(id(candidate)),
                ):
                    continue
                if (distance, component_depth) < (best_edge.distance, best_edge.depth):
                    best_edge.candidate = candidate
                    best_edge.distance = distance
                    best_edge.depth = float(component_depth)
                    best_edge.edge_indices = (start_index, end_index)
                    best_edge.world_point = _interpolate_world(candidate, weights)
                    best_edge.uv = _interpolate_uv(candidate, weights)

    if best_vertex.candidate is not None:
        candidate = best_vertex.candidate
        local_vertex = int(best_vertex.vertex_index)
        mesh_indices = _mesh_vertex_indices(candidate)
        mesh_vertex = mesh_indices[local_vertex] if mesh_indices is not None else local_vertex
        adjacent = _adjacent_faces_for_mesh_vertices(candidate_items, candidate, frozenset((mesh_vertex,))) if mesh_indices is not None else (int(candidate.face_index),)
        selector_point, edge_direction = _vertex_selector(candidate, local_vertex, px, py)
        return MapStudioHoverContext(
            component_type=HOVER_COMPONENT_VERTEX,
            room_resref=str(candidate.room_resref or ""),
            mesh_role=str(candidate.mesh_role or ""),
            face_index=int(candidate.face_index),
            vertex_index=local_vertex,
            mesh_vertex_index=int(mesh_vertex),
            adjacent_face_indices=adjacent,
            is_border=_mesh_vertex_is_border(candidate_items, candidate, mesh_vertex) if mesh_indices is not None else True,
            world_point=best_vertex.world_point,
            face_normal=tuple(candidate.normal),
            edge_direction=edge_direction,
            selector_origin_world_point=best_vertex.world_point,
            selector_world_point=selector_point,
            uv=best_vertex.uv,
            material=str(candidate.material or ""),
            walkable=None,
            screen_distance=float(best_vertex.distance),
            view_depth=float(best_vertex.depth),
        )

    if best_edge.candidate is not None:
        candidate = best_edge.candidate
        local_edge = tuple(int(value) for value in best_edge.edge_indices)
        mesh_indices = _mesh_vertex_indices(candidate)
        mesh_edge = (
            tuple(sorted((mesh_indices[local_edge[0]], mesh_indices[local_edge[1]])))
            if mesh_indices is not None
            else local_edge
        )
        adjacent = _adjacent_faces_for_mesh_vertices(candidate_items, candidate, frozenset(mesh_edge)) if mesh_indices is not None else (int(candidate.face_index),)
        world = tuple(candidate.world_points)[:3]
        edge_direction = _normalised_direction(world[local_edge[0]], world[local_edge[1]])
        return MapStudioHoverContext(
            component_type=HOVER_COMPONENT_EDGE,
            room_resref=str(candidate.room_resref or ""),
            mesh_role=str(candidate.mesh_role or ""),
            face_index=int(candidate.face_index),
            edge_indices=local_edge,
            mesh_edge_indices=mesh_edge,
            adjacent_face_indices=adjacent,
            is_border=len(adjacent) <= 1,
            world_point=best_edge.world_point,
            face_normal=tuple(candidate.normal),
            edge_direction=edge_direction,
            uv=best_edge.uv,
            material=str(candidate.material or ""),
            walkable=None,
            screen_distance=float(best_edge.distance),
            view_depth=float(best_edge.depth),
        )

    face_hits: list[tuple[_BestHit, str]] = []
    if best_render_face.candidate is not None:
        face_hits.append((best_render_face, HOVER_COMPONENT_FACE))
    if best_walkmesh_face.candidate is not None:
        face_hits.append((best_walkmesh_face, HOVER_COMPONENT_WALKMESH_FACE))
    if face_hits:
        if len(face_hits) > 1:
            wanted = HOVER_COMPONENT_WALKMESH_FACE if prefer_walkmesh else HOVER_COMPONENT_FACE
            face_hits.sort(key=lambda item: 0 if item[1] == wanted else 1)
        hit, component_type = face_hits[0]
        candidate = hit.candidate
        selector_edge, selector_origin, selector_point, selector_direction = _face_selector(candidate, px, py)
        return MapStudioHoverContext(
            component_type=component_type,
            room_resref=str(candidate.room_resref or ""),
            mesh_role=str(candidate.mesh_role or ""),
            face_index=int(candidate.face_index),
            world_point=hit.world_point,
            face_normal=tuple(candidate.normal),
            edge_direction=selector_direction,
            selector_origin_world_point=selector_origin,
            selector_world_point=selector_point,
            selector_edge_corners=selector_edge,
            uv=hit.uv,
            material=str(candidate.material or ""),
            walkable=candidate.walkable,
            screen_distance=float(hit.distance),
            view_depth=float(hit.depth),
        )

    return MapStudioHoverContext()


def map_studio_hover_context_summary(context: MapStudioHoverContext | None) -> str:
    """Return a short status-bar summary for the hovered component."""

    if context is None or not context.is_hit:
        return ""
    room = str(context.room_resref or "").strip() or "(unassigned room)"
    if context.component_type == HOVER_COMPONENT_VERTEX:
        vertex = context.mesh_vertex_index if context.mesh_vertex_index >= 0 else context.vertex_index
        return f"Vertex {vertex} of face {context.face_index} in {room}"
    if context.component_type == HOVER_COMPONENT_EDGE:
        a, b = context.mesh_edge_indices if min(context.mesh_edge_indices) >= 0 else context.edge_indices
        return f"Edge {a}-{b} of face {context.face_index} in {room}"
    if context.component_type == HOVER_COMPONENT_WALKMESH_FACE:
        walkable = "walkable" if bool(context.walkable) else "non-walkable"
        return f"WOK face {context.face_index} ({walkable}) in {room}"
    return f"Face {context.face_index} in {room}"
