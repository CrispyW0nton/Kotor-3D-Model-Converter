"""Module-wide generated WOK helpers for authored Map Studio projects."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from .authored_imported_mesh import authored_room_uses_unresolved_stock_geometry
from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec
from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface
from .module_format import WOKData, WOKFace


_ROOM_CONNECTIONS_KEY = "walkmesh_room_connections"


@dataclass(frozen=True)
class AuthoredModuleWalkmesh:
    """Combined module-coordinate walkmesh compiled from authored rooms."""

    wok: WOKData
    room_count: int = 0
    source_rooms: tuple[str, ...] = ()
    face_room_resrefs: tuple[str, ...] = ()
    room_connections: tuple[tuple[str, str], ...] = ()
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


@dataclass(frozen=True)
class AuthoredWalkmeshPortal:
    """One reciprocal room transition written onto two WOK perimeter edges."""

    source_room_resref: str
    target_room_resref: str
    source_hook_name: str
    target_hook_name: str
    source_face_index: int
    source_local_edge: int
    target_face_index: int
    target_local_edge: int
    midpoint_gap: float
    source_midpoint: tuple[float, float, float]
    target_midpoint: tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredWalkmeshConnectionBuild:
    """Automatic WOK result for the current LEGO-style room assembly."""

    room_woks: dict[str, WOKData]
    portals: tuple[AuthoredWalkmeshPortal, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.blocking_issues


def upsert_authored_walkmesh_room_connection(
    project: AuthoredModuleProject,
    *,
    source_room_resref: str,
    source_hook_name: str,
    target_room_resref: str,
    target_hook_name: str,
    connection_source: str = "map_studio_room_snap",
) -> AuthoredModuleProject:
    """Persist one unordered room seam without baking fragile LYT indices.

    WOK transition values are LYT-room indices, so they are compiled from this
    stable resref/hook record every time the project is previewed or exported.
    """

    from .authored_module_project import normalise_resref

    source_room = normalise_resref(source_room_resref)
    target_room = normalise_resref(target_room_resref)
    source_hook = str(source_hook_name or "").strip()
    target_hook = str(target_hook_name or "").strip()
    if not source_room or not target_room or source_room == target_room:
        raise ValueError("Walkmesh room connections require two different existing room resrefs.")
    if not source_hook or not target_hook:
        raise ValueError("Walkmesh room connections require a doorway hook on both rooms.")
    room_names = {room.normalised_resref() for room in tuple(project.rooms or ())}
    if source_room not in room_names or target_room not in room_names:
        raise ValueError("Both walkmesh connection rooms must exist in the current authored module.")
    canonical = tuple(sorted(((source_room, source_hook.lower()), (target_room, target_hook.lower()))))
    rows: list[dict[str, Any]] = []
    for raw in tuple(dict(project.extra or {}).get(_ROOM_CONNECTIONS_KEY) or ()):
        row = dict(raw or {})
        existing = tuple(
            sorted(
                (
                    (str(row.get("source_room_resref") or "").strip().lower(), str(row.get("source_hook_name") or "").strip().lower()),
                    (str(row.get("target_room_resref") or "").strip().lower(), str(row.get("target_hook_name") or "").strip().lower()),
                )
            )
        )
        if existing != canonical:
            rows.append(row)
    rows.append(
        {
            "source_room_resref": source_room,
            "source_hook_name": source_hook,
            "target_room_resref": target_room,
            "target_hook_name": target_hook,
            "connection_source": str(connection_source or "map_studio_room_snap"),
            "auto_generate_walkmesh": True,
        }
    )
    extra = dict(project.extra or {})
    extra[_ROOM_CONNECTIONS_KEY] = rows
    extra["walkmesh_generation_mode"] = "automatic_room_assembly"
    return replace(project, extra=extra)


def _clear_wok_transitions(wok: WOKData) -> WOKData:
    faces = [
        replace(face, trans1=-1, trans2=-1, trans3=-1)
        for face in tuple(getattr(wok, "faces", ()) or ())
    ]
    return replace(wok, faces=faces, raw=None)


def prepare_environment_kit_room_walkmesh(
    primitive: Any,
    *,
    source_room_position: tuple[float, float, float],
    magnets: tuple[Any, ...],
) -> Any:
    """Rebase a retail module-space WOK into reusable room-local kit space.

    Original transition indices point into the source module's LYT and are
    therefore invalid after reuse.  Their exact boundary edges are retained as
    typed portal hints, then the indices are cleared so the current module can
    compile fresh reciprocal transitions from stable room connections.
    """

    wok = getattr(primitive, "wok", None)
    if wok is None:
        return primitive
    origin = tuple(float(value) for value in tuple(source_room_position or (0.0, 0.0, 0.0))[:3])
    if len(origin) != 3 or not all(math.isfinite(value) for value in origin):
        raise ValueError("Environment-kit source room position must be a finite XYZ value.")
    local_wok = offset_wok_data(wok, (-origin[0], -origin[1], -origin[2]))
    candidates: list[dict[str, Any]] = []
    source_transition_count = 0
    for face_index, face in enumerate(tuple(getattr(local_wok, "faces", ()) or ())):
        if not is_walkable_walkmesh_surface(int(getattr(face, "surface", -1))):
            continue
        indices = (int(face.v1), int(face.v2), int(face.v3))
        adjacency = (int(face.adj1), int(face.adj2), int(face.adj3))
        transitions = (int(face.trans1), int(face.trans2), int(face.trans3))
        for local_edge in range(3):
            if adjacency[local_edge] >= 0:
                continue
            if transitions[local_edge] >= 0:
                source_transition_count += 1
            start = tuple(float(value) for value in local_wok.verts[indices[local_edge]][:3])
            end = tuple(float(value) for value in local_wok.verts[indices[(local_edge + 1) % 3]][:3])
            candidates.append(
                {
                    "face_index": face_index,
                    "local_edge": local_edge,
                    "start": start,
                    "end": end,
                    "midpoint": tuple((start[axis] + end[axis]) * 0.5 for axis in range(3)),
                    "source_transition_target": transitions[local_edge],
                }
            )
    portals: list[dict[str, Any]] = []
    used: set[int] = set()
    for magnet in tuple(magnets or ()):
        magnet_id = str(getattr(magnet, "magnet_id", "") or "").strip()
        hook = tuple(float(value) for value in tuple(getattr(magnet, "local_position", ()))[:3])
        if not magnet_id or len(hook) != 3:
            continue
        choices = [
            (math.dist(tuple(row["midpoint"]), hook), index, row)
            for index, row in enumerate(candidates)
            if index not in used
        ]
        if not choices:
            continue
        distance, index, row = min(choices, key=lambda item: (item[0], item[1]))
        # Some retail exterior rooms expose a real LYT doorway hook but leave
        # the corresponding WOK perimeter edge untagged (notably m24aa).  The
        # nearest walkable boundary is still the physical threshold we need to
        # reuse.  A boundary on the opposite side of a large room is not.
        if distance > 3.0:
            continue
        used.add(index)
        portals.append(
            {
                "magnet_id": magnet_id,
                "start": list(row["start"]),
                "end": list(row["end"]),
                "midpoint": list(row["midpoint"]),
                "hook_position": list(hook),
                "hook_to_portal_offset": [float(row["midpoint"][axis]) - hook[axis] for axis in range(3)],
                "width_m": math.dist(tuple(row["start"]), tuple(row["end"])),
                "source_transition_target": int(row["source_transition_target"]),
                "source_face_index": int(row["face_index"]),
                "source_local_edge": int(row["local_edge"]),
            }
        )
    metadata = dict(getattr(primitive, "metadata", {}) or {})
    metadata.update(
        {
            "wok_coordinate_space": "room_local",
            "environment_kit_source_room_position": list(origin),
            "walkmesh_portals": portals,
            "source_walkmesh_transition_count": source_transition_count,
            "source_walkmesh_boundary_count": len(candidates),
            "reusable_walkmesh_portal_count": len(portals),
            "source_transition_indices_cleared": True,
        }
    )
    return replace(primitive, wok=_clear_wok_transitions(local_wok), metadata=metadata)


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


def _bounds_center_xy(points: Any) -> tuple[float, float] | None:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for point in tuple(points or ()):
        x, y = float(point[0]), float(point[1])
        min_x, max_x = min(min_x, x), max(max_x, x)
        min_y, max_y = min(min_y, y), max(max_y, y)
    if min_x > max_x:
        return None
    return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)


def _room_visual_center_xy(room: Any) -> tuple[float, float] | None:
    """World-space XY bounds center of the room's non-backdrop render surfaces."""

    primitive = getattr(room, "primitive", None)
    points: list[Any] = []
    for surface in tuple(getattr(primitive, "surfaces", ()) or ()):
        if bool(getattr(surface, "backdrop", False)) or bool(getattr(surface, "background_geometry", False)):
            continue
        if not bool(getattr(surface, "render", True)):
            continue
        points.extend(tuple(getattr(surface, "vertices", ()) or ()))
    center = _bounds_center_xy(points)
    if center is None:
        return None
    offset = _room_offset(room)
    return (center[0] + offset[0], center[1] + offset[1])


#: A declared module-space WOK whose XY bounds center sits further than this
#: many units from the room's rendered geometry is suspect; the room-local
#: reading must then cut the misalignment by at least half to win.
_WOK_ALIGNMENT_TOLERANCE = 4.0


def resolve_room_wok_module_offset(
    room: Any, wok: Any = None
) -> tuple[tuple[float, float, float], str | None]:
    """Return the vertex offset that places one room WOK in module space.

    The declared ``wok_coordinate_space`` contract is trusted unless the WOK
    is geometrically far from the room's rendered surfaces and re-reading it
    as room-local clearly fixes the alignment.  Converted candidate modules
    can ship custom rooms whose WOK is stored room-local even though stock
    import labeled every room module-space (921srt's 921srtb); without this
    audit that room's collision floats at the label-implied coordinates and
    the player start has no floor under it in PIE or in-game.
    """

    source_wok = wok if wok is not None else getattr(getattr(room, "primitive", None), "wok", None)
    room_offset = _room_offset(room)
    if _room_wok_coordinate_space(room) != "module":
        return room_offset, None
    if room_offset == (0.0, 0.0, 0.0):
        return (0.0, 0.0, 0.0), None
    wok_center = _bounds_center_xy(getattr(source_wok, "verts", ()) or ())
    visual_center = _room_visual_center_xy(room)
    if wok_center is None or visual_center is None:
        return (0.0, 0.0, 0.0), None
    declared_error = (
        ((wok_center[0] - visual_center[0]) ** 2) + ((wok_center[1] - visual_center[1]) ** 2)
    ) ** 0.5
    corrected_error = (
        ((wok_center[0] + room_offset[0] - visual_center[0]) ** 2)
        + ((wok_center[1] + room_offset[1] - visual_center[1]) ** 2)
    ) ** 0.5
    if declared_error > _WOK_ALIGNMENT_TOLERANCE and corrected_error < declared_error * 0.5:
        room_resref = ""
        normalised = getattr(room, "normalised_resref", None)
        if callable(normalised):
            room_resref = str(normalised() or "")
        warning = (
            f"Room {room_resref or '(unnamed)'} WOK is declared module-space but its geometry sits "
            f"{declared_error:.1f} units from the room's rendered surfaces; treating it as room-local "
            f"and applying the room position ({room_offset[0]:.1f}, {room_offset[1]:.1f}, "
            f"{room_offset[2]:.1f}) instead (residual {corrected_error:.1f} units)."
        )
        return room_offset, warning
    return (0.0, 0.0, 0.0), None


def offset_wok_data(wok: Any, offset: tuple[float, float, float]) -> Any:
    """Return a copy of one WOK with every vertex offset; the source is unchanged."""

    if tuple(offset) == (0.0, 0.0, 0.0):
        return wok
    return WOKData(
        name=str(getattr(wok, "name", "") or ""),
        verts=[_offset_vertex(vertex, offset) for vertex in tuple(getattr(wok, "verts", ()) or ())],
        faces=list(getattr(wok, "faces", ()) or ()),
        relative_hook1=tuple(getattr(wok, "relative_hook1", (0.0, 0.0, 0.0))),
        relative_hook2=tuple(getattr(wok, "relative_hook2", (0.0, 0.0, 0.0))),
        absolute_hook1=tuple(getattr(wok, "absolute_hook1", (0.0, 0.0, 0.0))),
        absolute_hook2=tuple(getattr(wok, "absolute_hook2", (0.0, 0.0, 0.0))),
        position=tuple(getattr(wok, "position", (0.0, 0.0, 0.0))),
        adjacency_domain_count=getattr(wok, "adjacency_domain_count", None),
    )


def _room_connection_hook_position(project: AuthoredModuleProject, room: Any, hook_name: str) -> tuple[float, float, float] | None:
    """Resolve a floor-plan opening or imported LYT hook in module space."""

    wanted = str(hook_name or "").strip().lower()
    try:
        from .authored_module_layout import authored_room_connection_hooks

        for hook in authored_room_connection_hooks(project):
            if hook.room_resref == room.normalised_resref() and hook.opening_name.strip().lower() == wanted:
                return tuple(float(value) for value in hook.position)
    except Exception:
        pass
    try:
        from .map_studio_room_snapping import authored_room_door_hooks

        for hook in authored_room_door_hooks(room):
            if hook.door.strip().lower() == wanted:
                return tuple(float(value) for value in hook.world_position)
    except Exception:
        pass
    return None


def _room_portal_hint(
    project: AuthoredModuleProject,
    room: Any,
    hook_name: str,
    fallback: tuple[float, float, float],
) -> tuple[tuple[float, float, float], float]:
    """Return the intended module-space WOK edge midpoint and portal width."""

    wanted = str(hook_name or "").strip().lower()
    primitive = getattr(room, "primitive", None)
    metadata = {
        **dict(getattr(primitive, "metadata", {}) or {}),
        **dict(getattr(room, "metadata", {}) or {}),
    }
    room_offset = _room_offset(room)
    for raw in tuple(metadata.get("walkmesh_portals") or ()):
        row = dict(raw or {})
        if str(row.get("magnet_id") or "").strip().lower() != wanted:
            continue
        midpoint = tuple(float(value) for value in tuple(row.get("midpoint") or ())[:3])
        if len(midpoint) == 3:
            return (
                tuple(midpoint[axis] + room_offset[axis] for axis in range(3)),
                max(0.0, float(row.get("width_m", 0.0) or 0.0)),
            )

    # Floor-plan portals may be recessed into the generated WOK so their
    # perimeter edge exactly matches a stock threshold edge while the visible
    # door frame remains hosted on the wall plane.
    points = tuple(getattr(primitive, "points", ()) or ())
    for opening in tuple(getattr(primitive, "openings", ()) or ()):
        if str(getattr(opening, "name", "") or "").strip().lower() != wanted:
            continue
        opening_metadata = dict(getattr(opening, "metadata", {}) or {})
        edge_index = int(getattr(opening, "edge_index", -1))
        if edge_index < 0 or edge_index >= len(points):
            break
        start = points[edge_index]
        end = points[(edge_index + 1) % len(points)]
        dx, dy = float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
        edge_length = math.hypot(dx, dy)
        if edge_length <= 1.0e-8:
            break
        try:
            from .authored_room_floorplan import polygon_signed_area

            ccw = polygon_signed_area(tuple((float(point[0]), float(point[1])) for point in points)) > 0.0
        except Exception:
            ccw = True
        inward = (-dy / edge_length, dx / edge_length) if ccw else (dy / edge_length, -dx / edge_length)
        inset = max(0.0, float(opening_metadata.get("walkmesh_portal_inset_m", 0.0) or 0.0))
        return (
            (
                float(fallback[0]) + inward[0] * inset,
                float(fallback[1]) + inward[1] * inset,
                float(fallback[2]),
            ),
            max(0.0, float(opening_metadata.get("walkmesh_portal_width_m", opening.width) or opening.width)),
        )
    return fallback, 0.0


def _walkable_boundary_edges(
    wok: WOKData,
    *,
    module_offset: tuple[float, float, float],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    verts = tuple(getattr(wok, "verts", ()) or ())
    for face_index, face in enumerate(tuple(getattr(wok, "faces", ()) or ())):
        if not is_walkable_walkmesh_surface(int(getattr(face, "surface", -1))):
            continue
        indices = (int(face.v1), int(face.v2), int(face.v3))
        adjacency = (int(face.adj1), int(face.adj2), int(face.adj3))
        for local_edge in range(3):
            if adjacency[local_edge] >= 0:
                continue
            try:
                start = _offset_vertex(verts[indices[local_edge]], module_offset)
                end = _offset_vertex(verts[indices[(local_edge + 1) % 3]], module_offset)
            except (IndexError, TypeError, ValueError):
                continue
            rows.append(
                {
                    "face_index": face_index,
                    "local_edge": local_edge,
                    "start": start,
                    "end": end,
                    "midpoint": tuple((start[axis] + end[axis]) * 0.5 for axis in range(3)),
                    "width": math.dist(start, end),
                }
            )
    return tuple(rows)


def _assign_transition(wok: WOKData, face_index: int, local_edge: int, target_room_index: int) -> WOKData:
    faces = list(tuple(getattr(wok, "faces", ()) or ()))
    face = faces[int(face_index)]
    key = ("trans1", "trans2", "trans3")[int(local_edge)]
    faces[int(face_index)] = replace(face, **{key: int(target_room_index)})
    return replace(wok, faces=faces, raw=None)


def compile_authored_room_connection_walkmeshes(
    project: AuthoredModuleProject,
    room_woks: Mapping[str, WOKData] | None = None,
    *,
    woks_are_module_space: bool = False,
    module_space_room_resrefs: set[str] | frozenset[str] | tuple[str, ...] = (),
    midpoint_tolerance: float = 0.075,
) -> AuthoredWalkmeshConnectionBuild:
    """Generate and validate reciprocal current-module WOK portals.

    This is the shared atomic seam compiler for authored/authored,
    stock/stock, and mixed stock/authored room joins. It never trusts copied
    source-module transition indices and never fabricates a connection between
    boundary edges whose module-space midpoints do not actually coincide.
    """

    supplied = dict(room_woks or {})
    explicit_module_space = {str(value or "").strip().lower() for value in module_space_room_resrefs}
    compiled: dict[str, WOKData] = {}
    blocking: list[str] = []
    warnings: list[str] = []
    rooms = tuple(project.rooms or ())
    room_by_name = {room.normalised_resref(): room for room in rooms}
    for room in rooms:
        room_resref = room.normalised_resref()
        wok = supplied.get(room_resref)
        if wok is None:
            try:
                wok = compile_authored_room_spec(room).wok
            except Exception as exc:
                blocking.append(f"Room {room_resref} WOK could not be generated: {exc}")
                continue
        # Reused kit rooms must never retain transition indices into the
        # source game's original LYT. Their current connections are rebuilt
        # below from stable room/hook records.
        metadata = {
            **dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {}),
            **dict(getattr(room, "metadata", {}) or {}),
        }
        compiled[room_resref] = (
            _clear_wok_transitions(wok)
            if metadata.get("environment_kit_piece_id") or metadata.get("source_transition_indices_cleared")
            else replace(wok, faces=list(tuple(getattr(wok, "faces", ()) or ())), raw=None)
        )

    order = {room.normalised_resref(): index for index, room in enumerate(rooms)}
    claimed: set[tuple[str, int, int]] = set()
    portals: list[AuthoredWalkmeshPortal] = []
    for raw in tuple(dict(project.extra or {}).get(_ROOM_CONNECTIONS_KEY) or ()):
        row = dict(raw or {})
        source_name = str(row.get("source_room_resref") or "").strip().lower()
        target_name = str(row.get("target_room_resref") or "").strip().lower()
        source_hook_name = str(row.get("source_hook_name") or "").strip()
        target_hook_name = str(row.get("target_hook_name") or "").strip()
        source_room = room_by_name.get(source_name)
        target_room = room_by_name.get(target_name)
        if source_room is None or target_room is None:
            blocking.append(f"Walkmesh room connection {source_name or '?'} -> {target_name or '?'} references a missing room.")
            continue
        source_hook = _room_connection_hook_position(project, source_room, source_hook_name)
        target_hook = _room_connection_hook_position(project, target_room, target_hook_name)
        if source_hook is None or target_hook is None:
            blocking.append(
                f"Walkmesh room connection {source_name}/{source_hook_name} -> {target_name}/{target_hook_name} "
                "references a missing doorway hook."
            )
            continue
        source_hint, source_width = _room_portal_hint(project, source_room, source_hook_name, source_hook)
        target_hint, target_width = _room_portal_hint(project, target_room, target_hook_name, target_hook)
        source_wok = compiled.get(source_name)
        target_wok = compiled.get(target_name)
        if source_wok is None or target_wok is None:
            continue
        source_offset = (
            (0.0, 0.0, 0.0)
            if woks_are_module_space or source_name in explicit_module_space
            else resolve_room_wok_module_offset(source_room, source_wok)[0]
        )
        target_offset = (
            (0.0, 0.0, 0.0)
            if woks_are_module_space or target_name in explicit_module_space
            else resolve_room_wok_module_offset(target_room, target_wok)[0]
        )
        source_edges = [
            edge
            for edge in _walkable_boundary_edges(source_wok, module_offset=source_offset)
            if (source_name, int(edge["face_index"]), int(edge["local_edge"])) not in claimed
        ]
        target_edges = [
            edge
            for edge in _walkable_boundary_edges(target_wok, module_offset=target_offset)
            if (target_name, int(edge["face_index"]), int(edge["local_edge"])) not in claimed
        ]
        if not source_edges or not target_edges:
            blocking.append(f"Rooms {source_name} and {target_name} do not expose unclaimed walkable WOK perimeter edges.")
            continue

        def edge_score(edge: dict[str, Any], hint: tuple[float, float, float], expected_width: float) -> tuple[float, float]:
            return (
                math.dist(tuple(edge["midpoint"]), hint),
                abs(float(edge["width"]) - expected_width) if expected_width > 0.0 else 0.0,
            )

        source_edge = min(source_edges, key=lambda edge: edge_score(edge, source_hint, source_width))
        target_edge = min(target_edges, key=lambda edge: edge_score(edge, target_hint, target_width))
        source_hint_gap = math.dist(tuple(source_edge["midpoint"]), source_hint)
        target_hint_gap = math.dist(tuple(target_edge["midpoint"]), target_hint)
        midpoint_gap = math.dist(tuple(source_edge["midpoint"]), tuple(target_edge["midpoint"]))
        if source_hint_gap > max(0.25, source_width * 0.25) or target_hint_gap > max(0.25, target_width * 0.25):
            blocking.append(
                f"Rooms {source_name} and {target_name} have no WOK boundary edge at their doorway hooks "
                f"(source gap {source_hint_gap:.3f} m, target gap {target_hint_gap:.3f} m)."
            )
            continue
        if midpoint_gap > float(midpoint_tolerance):
            blocking.append(
                f"Rooms {source_name} and {target_name} doorway WOK edges are {midpoint_gap:.3f} m apart; "
                "the LEGO join was rejected instead of exporting a cracked walkmesh."
            )
            continue
        source_face = int(source_edge["face_index"])
        source_local_edge = int(source_edge["local_edge"])
        target_face = int(target_edge["face_index"])
        target_local_edge = int(target_edge["local_edge"])
        compiled[source_name] = _assign_transition(compiled[source_name], source_face, source_local_edge, order[target_name])
        compiled[target_name] = _assign_transition(compiled[target_name], target_face, target_local_edge, order[source_name])
        claimed.update(
            {
                (source_name, source_face, source_local_edge),
                (target_name, target_face, target_local_edge),
            }
        )
        portals.append(
            AuthoredWalkmeshPortal(
                source_room_resref=source_name,
                target_room_resref=target_name,
                source_hook_name=source_hook_name,
                target_hook_name=target_hook_name,
                source_face_index=source_face,
                source_local_edge=source_local_edge,
                target_face_index=target_face,
                target_local_edge=target_local_edge,
                midpoint_gap=midpoint_gap,
                source_midpoint=tuple(source_edge["midpoint"]),
                target_midpoint=tuple(target_edge["midpoint"]),
            )
        )
    return AuthoredWalkmeshConnectionBuild(
        room_woks=compiled,
        portals=tuple(portals),
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def combine_authored_module_walkmesh(project: AuthoredModuleProject) -> AuthoredModuleWalkmesh:
    """Compile all authored room WOKs into module-coordinate space."""

    combined = WOKData(name=f"{project.module_root}_combined")
    source_rooms: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    raw_woks: dict[str, WOKData] = {}
    room_face_offsets: dict[str, int] = {}
    face_room_resrefs: list[str] = []
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
            raw_woks[room_resref] = compile_authored_room_spec(room).wok
        except Exception as exc:
            blocking.append(f"Room {room_resref or '(unnamed)'} could not compile for module walkmesh: {exc}")
    connection_build = compile_authored_room_connection_walkmeshes(project, raw_woks)
    warnings.extend(connection_build.warnings)
    blocking.extend(connection_build.blocking_issues)
    for room in tuple(project.rooms or ()):
        room_resref = room.normalised_resref()
        source_wok = connection_build.room_woks.get(room_resref)
        if source_wok is None:
            continue
        vertex_offset = len(combined.verts)
        face_offset = len(combined.faces)
        room_face_offsets[room_resref] = face_offset
        wok_coordinate_space = _room_wok_coordinate_space(room)
        position_offset, alignment_warning = resolve_room_wok_module_offset(room, source_wok)
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
            face_room_resrefs.append(room_resref)
        source_rooms.append(room_resref)
        if alignment_warning:
            warnings.append(alignment_warning)
        elif wok_coordinate_space == "module" and _room_offset(room) != (0.0, 0.0, 0.0):
            warnings.append(
                f"Room {room_resref or '(unnamed)'} uses a stock module-space WOK; "
                "its LYT position was not applied a second time."
            )
        elif position_offset != (0.0, 0.0, 0.0):
            warnings.append(
                f"Room {room_resref or '(unnamed)'} WOK was offset to module coordinates at "
                f"({position_offset[0]:.3f}, {position_offset[1]:.3f}, {position_offset[2]:.3f})."
            )

    # Individual Odyssey WOK files express room joins through ``transN`` room
    # indices. PIE uses one combined in-memory WOK, so stitch those same
    # validated portal edges into ordinary face adjacency for navigation and
    # collision. Exported per-room WOK transition values remain untouched.
    for portal in connection_build.portals:
        if (
            portal.source_room_resref not in room_face_offsets
            or portal.target_room_resref not in room_face_offsets
        ):
            continue
        source_face_index = (
            room_face_offsets[portal.source_room_resref] + int(portal.source_face_index)
        )
        target_face_index = (
            room_face_offsets[portal.target_room_resref] + int(portal.target_face_index)
        )
        if not (
            0 <= source_face_index < len(combined.faces)
            and 0 <= target_face_index < len(combined.faces)
        ):
            blocking.append(
                f"Combined PIE WOK portal {portal.source_room_resref} -> "
                f"{portal.target_room_resref} resolved outside the compiled face table."
            )
            continue
        source_adj_key = ("adj1", "adj2", "adj3")[int(portal.source_local_edge)]
        target_adj_key = ("adj1", "adj2", "adj3")[int(portal.target_local_edge)]
        combined.faces[source_face_index] = replace(
            combined.faces[source_face_index],
            **{source_adj_key: target_face_index},
        )
        combined.faces[target_face_index] = replace(
            combined.faces[target_face_index],
            **{target_adj_key: source_face_index},
        )

    if not combined.faces and not blocking:
        blocking.append("Authored module has no generated room WOK faces.")
    return AuthoredModuleWalkmesh(
        wok=combined,
        room_count=len(source_rooms),
        source_rooms=tuple(source_rooms),
        face_room_resrefs=tuple(face_room_resrefs),
        room_connections=tuple(
            dict.fromkeys(
                tuple(
                    sorted(
                        (
                            str(portal.source_room_resref or "").strip().lower(),
                            str(portal.target_room_resref or "").strip().lower(),
                        )
                    )
                )
                for portal in connection_build.portals
                if str(portal.source_room_resref or "").strip()
                and str(portal.target_room_resref or "").strip()
            )
        ),
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
    "AuthoredWalkmeshConnectionBuild",
    "AuthoredWalkmeshPortal",
    "AuthoredWalkmeshSnapResult",
    "combine_authored_module_walkmesh",
    "compile_authored_room_connection_walkmeshes",
    "offset_wok_data",
    "prepare_environment_kit_room_walkmesh",
    "resolve_room_wok_module_offset",
    "snap_position_to_authored_walkmesh",
    "upsert_authored_walkmesh_room_connection",
]
