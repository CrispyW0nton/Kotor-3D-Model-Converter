"""Headless walkmesh editor service for the Module Editor.

T1503 exposes the existing ``WOKData`` parser/writer as workflow-safe editor
operations: face selection, surface-material painting, validation, and binary
round-trip checks.  The UI can render the returned face metadata while keeping
all mutation in this Qt-free service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Optional


@dataclass(frozen=True)
class WalkmeshSurfaceMaterial:
    """One surface material option shown in the walkmesh paint palette."""

    surface_id: int
    name: str
    walkable: bool
    color: tuple[float, float, float, float] = (0.6, 0.6, 0.6, 0.45)


@dataclass(frozen=True)
class WalkmeshFaceInfo:
    """Viewport/inspector metadata for one WOK triangle."""

    face_index: int
    vertices: tuple[int, int, int]
    surface_id: int
    surface_name: str
    walkable: bool
    selected: bool = False
    adjacency: tuple[int, int, int] = (-1, -1, -1)
    centroid: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class WalkmeshValidationIssue:
    """Actionable walkmesh validation finding."""

    severity: str
    code: str
    message: str
    face_index: int = -1
    edge_index: int = -1
    detail: str = ""


@dataclass
class WalkmeshValidationReport:
    """Summary of whether a WOK is usable and safe to save."""

    ok: bool = False
    room: str = ""
    vertex_count: int = 0
    face_count: int = 0
    walkable_face_count: int = 0
    non_walk_face_count: int = 0
    boundary_edge_count: int = 0
    transition_face_count: int = 0
    surface_distribution: dict[int, int] = field(default_factory=dict)
    issues: list[WalkmeshValidationIssue] = field(default_factory=list)
    message: str = ""
    code: str = "not_validated"


@dataclass
class WalkmeshWorkbench:
    """Editor-ready WOK payload for a module room."""

    ok: bool = False
    room: str = ""
    wok: Any = None
    faces: list[WalkmeshFaceInfo] = field(default_factory=list)
    surfaces: list[WalkmeshSurfaceMaterial] = field(default_factory=list)
    selected_face_index: int = -1
    validation: Optional[WalkmeshValidationReport] = None
    message: str = ""
    code: str = "not_loaded"


@dataclass
class WalkmeshSelectionResult:
    """Result of selecting a WOK triangle by index or viewport point."""

    ok: bool = False
    room: str = ""
    face_index: int = -1
    face: Optional[WalkmeshFaceInfo] = None
    workbench: Optional[WalkmeshWorkbench] = None
    message: str = ""
    code: str = "not_selected"


@dataclass
class WalkmeshEditResult:
    """Result of painting one or more WOK triangle surfaces."""

    ok: bool = False
    room: str = ""
    face_indices: tuple[int, ...] = ()
    old_surfaces: dict[int, int] = field(default_factory=dict)
    new_surface_id: int = -1
    new_surface_name: str = ""
    workbench: Optional[WalkmeshWorkbench] = None
    message: str = ""
    code: str = "not_edited"


@dataclass
class WalkmeshRoundTripResult:
    """Binary write/read verification for a WOK after edits."""

    ok: bool = False
    room: str = ""
    original_size: int = 0
    output_size: int = 0
    reparsed_vertex_count: int = 0
    reparsed_face_count: int = 0
    material_distribution: dict[int, int] = field(default_factory=dict)
    message: str = ""
    code: str = "not_checked"


def _import_module_format():
    """Import module_format in both package and direct-test contexts."""

    for name in (
        "src.core.modules.module_format",
        "core.modules.module_format",
        "core.module_format",
        "src.core.module_format",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module("src.core.modules.module_format")


def _import_walkmesh_renderer():
    try:
        return import_module("core.walkmesh_renderer")
    except ImportError:
        try:
            return import_module("src.core.walkmesh_renderer")
        except ImportError:
            return None


def _module_from_input(value: Any) -> Any:
    if _looks_like_wok(value):
        return value
    return getattr(value, "module", value)


def _looks_like_wok(value: Any) -> bool:
    return hasattr(value, "verts") and hasattr(value, "faces")


def _room_woks(module_like: Any) -> dict[str, Any]:
    module = _module_from_input(module_like)
    room_woks = getattr(module, "room_woks", None)
    if isinstance(room_woks, dict):
        return room_woks
    return {}


def _select_wok(module_like: Any, room: str = "") -> tuple[str, Any]:
    module = _module_from_input(module_like)
    if _looks_like_wok(module):
        return room or getattr(module, "name", "") or "walkmesh", module

    rooms = _room_woks(module)
    if room:
        direct = rooms.get(room) or rooms.get(room.lower()) or rooms.get(room.upper())
        if direct is not None:
            return room, direct

    if rooms:
        room_name = sorted(rooms.keys())[0]
        return room_name, rooms[room_name]

    wok = getattr(module, "wok", None)
    if wok is not None:
        return room or getattr(wok, "name", "") or getattr(module, "name", "") or "walkmesh", wok

    return room, None


def _surface_names() -> dict[int, str]:
    names = getattr(_import_module_format(), "WOK_SURFACE_NAMES", {})
    return dict(names) if isinstance(names, dict) else {}


def _walkable_ids() -> set[int]:
    ids = getattr(_import_module_format(), "WALKABLE_IDS", set())
    return set(ids)


def _surface_name(surface_id: int) -> str:
    names = _surface_names()
    return names.get(surface_id, f"SURFACE_{surface_id}")


def _surface_color(surface_id: int) -> tuple[float, float, float, float]:
    renderer = _import_walkmesh_renderer()
    if renderer and hasattr(renderer, "surface_color"):
        return renderer.surface_color(surface_id)
    return (0.6, 0.6, 0.6, 0.45)


def _is_walkable(surface_id: int) -> bool:
    return surface_id in _walkable_ids()


def _face_indices(face: Any) -> tuple[int, int, int]:
    return (int(getattr(face, "v1", -1)), int(getattr(face, "v2", -1)), int(getattr(face, "v3", -1)))


def _face_adjacency(face: Any) -> tuple[int, int, int]:
    return (int(getattr(face, "adj1", -1)), int(getattr(face, "adj2", -1)), int(getattr(face, "adj3", -1)))


def _centroid(wok: Any, face: Any) -> tuple[float, float, float]:
    indices = _face_indices(face)
    verts = getattr(wok, "verts", [])
    if any(i < 0 or i >= len(verts) for i in indices):
        return (0.0, 0.0, 0.0)
    points = [verts[i] for i in indices]
    return (
        sum(float(p[0]) for p in points) / 3.0,
        sum(float(p[1]) for p in points) / 3.0,
        sum(float(p[2]) for p in points) / 3.0,
    )


def _face_info(wok: Any, face_index: int, selected_face_index: int = -1) -> Optional[WalkmeshFaceInfo]:
    faces = getattr(wok, "faces", [])
    if face_index < 0 or face_index >= len(faces):
        return None
    face = faces[face_index]
    surface_id = int(getattr(face, "surface", 0))
    return WalkmeshFaceInfo(
        face_index=face_index,
        vertices=_face_indices(face),
        surface_id=surface_id,
        surface_name=_surface_name(surface_id),
        walkable=_is_walkable(surface_id),
        selected=face_index == selected_face_index,
        adjacency=_face_adjacency(face),
        centroid=_centroid(wok, face),
    )


def _surface_distribution(wok: Any) -> dict[int, int]:
    if hasattr(wok, "surface_distribution"):
        return dict(wok.surface_distribution())
    dist: dict[int, int] = {}
    for face in getattr(wok, "faces", []):
        surface = int(getattr(face, "surface", 0))
        dist[surface] = dist.get(surface, 0) + 1
    return dist


def _walkable_face_count(wok: Any) -> int:
    if hasattr(wok, "walkable_face_count"):
        return int(wok.walkable_face_count())
    return sum(1 for face in getattr(wok, "faces", []) if _is_walkable(int(getattr(face, "surface", 0))))


def _non_walk_face_count(wok: Any) -> int:
    if hasattr(wok, "non_walk_face_count"):
        return int(wok.non_walk_face_count())
    return sum(1 for face in getattr(wok, "faces", []) if int(getattr(face, "surface", 0)) == 7)


def _boundary_edges(wok: Any) -> list[tuple[int, int, int, int]]:
    if hasattr(wok, "boundary_edges"):
        return list(wok.boundary_edges())
    return []


def walkmesh_surface_palette() -> list[WalkmeshSurfaceMaterial]:
    """Return the KOTOR WOK material palette with color and walkability flags."""

    return [
        WalkmeshSurfaceMaterial(
            surface_id=surface_id,
            name=name,
            walkable=_is_walkable(surface_id),
            color=_surface_color(surface_id),
        )
        for surface_id, name in sorted(_surface_names().items())
    ]


def build_walkmesh_workbench(
    module_like: Any,
    *,
    room: str = "",
    selected_face_index: int = -1,
) -> WalkmeshWorkbench:
    """Build editor-facing face, palette, and validation metadata for a WOK."""

    room_name, wok = _select_wok(module_like, room)
    if wok is None:
        return WalkmeshWorkbench(
            ok=False,
            room=room_name,
            message="No WOK/DWK/PWK walkmesh is loaded for this module room.",
            code="no_walkmesh",
        )

    faces = [
        info
        for index in range(len(getattr(wok, "faces", [])))
        for info in [_face_info(wok, index, selected_face_index)]
        if info is not None
    ]
    validation = validate_walkmesh(wok, room=room_name)
    return WalkmeshWorkbench(
        ok=True,
        room=room_name,
        wok=wok,
        faces=faces,
        surfaces=walkmesh_surface_palette(),
        selected_face_index=selected_face_index,
        validation=validation,
        message=f"Loaded walkmesh {room_name}: {len(getattr(wok, 'verts', []))} verts, {len(faces)} faces.",
        code="loaded",
    )


def select_walkmesh_face(
    module_like: Any,
    *,
    room: str = "",
    face_index: Optional[int] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
) -> WalkmeshSelectionResult:
    """Select a WOK triangle by explicit index or XY viewport point."""

    room_name, wok = _select_wok(module_like, room)
    if wok is None:
        return WalkmeshSelectionResult(ok=False, room=room_name, message="No walkmesh loaded.", code="no_walkmesh")

    resolved = -1
    if face_index is not None:
        resolved = int(face_index)
    elif x is not None and y is not None and hasattr(wok, "face_at_point"):
        resolved = int(wok.face_at_point(float(x), float(y)))
    else:
        return WalkmeshSelectionResult(
            ok=False,
            room=room_name,
            message="Provide a face index or an XY point to select a walkmesh face.",
            code="selection_missing",
        )

    info = _face_info(wok, resolved, resolved)
    if info is None:
        return WalkmeshSelectionResult(
            ok=False,
            room=room_name,
            face_index=resolved,
            message=f"No walkmesh face found at selection {resolved}.",
            code="face_not_found",
        )

    workbench = build_walkmesh_workbench(wok, room=room_name, selected_face_index=resolved)
    return WalkmeshSelectionResult(
        ok=True,
        room=room_name,
        face_index=resolved,
        face=info,
        workbench=workbench,
        message=f"Selected face {resolved} ({info.surface_name}).",
        code="selected",
    )


def set_walkmesh_face_surface(
    module_like: Any,
    face_indices: int | list[int] | tuple[int, ...],
    surface_id: int,
    *,
    room: str = "",
) -> WalkmeshEditResult:
    """Paint one or more walkmesh faces with a KOTOR surface material."""

    room_name, wok = _select_wok(module_like, room)
    if wok is None:
        return WalkmeshEditResult(ok=False, room=room_name, message="No walkmesh loaded.", code="no_walkmesh")

    if isinstance(face_indices, int):
        indices = (face_indices,)
    else:
        indices = tuple(int(i) for i in face_indices)

    if not indices:
        return WalkmeshEditResult(ok=False, room=room_name, message="No face indices were provided.", code="no_faces")

    names = _surface_names()
    if int(surface_id) not in names:
        return WalkmeshEditResult(
            ok=False,
            room=room_name,
            face_indices=indices,
            new_surface_id=int(surface_id),
            new_surface_name=_surface_name(int(surface_id)),
            message=f"Surface material {surface_id} is not a known KOTOR WOK material.",
            code="unknown_surface",
        )

    faces = getattr(wok, "faces", [])
    old_surfaces: dict[int, int] = {}
    for index in indices:
        if index < 0 or index >= len(faces):
            return WalkmeshEditResult(
                ok=False,
                room=room_name,
                face_indices=indices,
                old_surfaces=old_surfaces,
                new_surface_id=int(surface_id),
                new_surface_name=_surface_name(int(surface_id)),
                message=f"Face index {index} is outside the walkmesh face range.",
                code="face_not_found",
            )
        old_surfaces[index] = int(getattr(faces[index], "surface", 0))

    for index in indices:
        if hasattr(wok, "set_face_surface"):
            wok.set_face_surface(index, int(surface_id))
        else:
            setattr(faces[index], "surface", int(surface_id))

    workbench = build_walkmesh_workbench(wok, room=room_name, selected_face_index=indices[-1])
    return WalkmeshEditResult(
        ok=True,
        room=room_name,
        face_indices=indices,
        old_surfaces=old_surfaces,
        new_surface_id=int(surface_id),
        new_surface_name=_surface_name(int(surface_id)),
        workbench=workbench,
        message=f"Painted {len(indices)} face(s) as {_surface_name(int(surface_id))}.",
        code="surface_changed",
    )


def paint_walkmesh_point(
    module_like: Any,
    *,
    x: float,
    y: float,
    surface_id: int,
    room: str = "",
) -> WalkmeshEditResult:
    """Paint the WOK face under an XY viewport point."""

    selection = select_walkmesh_face(module_like, room=room, x=x, y=y)
    if not selection.ok:
        return WalkmeshEditResult(
            ok=False,
            room=selection.room,
            message=selection.message,
            code=selection.code,
        )
    return set_walkmesh_face_surface(module_like, selection.face_index, surface_id, room=selection.room)


def validate_walkmesh(module_like: Any, *, room: str = "") -> WalkmeshValidationReport:
    """Validate WOK structure and editor-facing walkability concerns."""

    room_name, wok = _select_wok(module_like, room)
    if wok is None:
        return WalkmeshValidationReport(
            ok=False,
            room=room_name,
            message="No walkmesh loaded.",
            code="no_walkmesh",
            issues=[
                WalkmeshValidationIssue(
                    severity="error",
                    code="NO_WALKMESH",
                    message="The module room has no WOK/DWK/PWK walkmesh loaded.",
                )
            ],
        )

    verts = getattr(wok, "verts", [])
    faces = getattr(wok, "faces", [])
    issues: list[WalkmeshValidationIssue] = []
    known_surfaces = _surface_names()

    if not verts:
        issues.append(WalkmeshValidationIssue("error", "NO_VERTICES", "Walkmesh has no vertices."))
    if not faces:
        issues.append(WalkmeshValidationIssue("error", "NO_FACES", "Walkmesh has no faces."))

    for face_index, face in enumerate(faces):
        for edge_index, vertex_index in enumerate(_face_indices(face)):
            if vertex_index < 0 or vertex_index >= len(verts):
                issues.append(
                    WalkmeshValidationIssue(
                        severity="error",
                        code="BAD_VERTEX_INDEX",
                        message=f"Face {face_index} references missing vertex {vertex_index}.",
                        face_index=face_index,
                        edge_index=edge_index,
                    )
                )
        surface = int(getattr(face, "surface", 0))
        if surface not in known_surfaces:
            issues.append(
                WalkmeshValidationIssue(
                    severity="warning",
                    code="UNKNOWN_SURFACE",
                    message=f"Face {face_index} uses unknown surface material {surface}.",
                    face_index=face_index,
                )
            )
        for edge_index, adjacent in enumerate(_face_adjacency(face)):
            if adjacent != -1 and (adjacent < 0 or adjacent >= len(faces)):
                issues.append(
                    WalkmeshValidationIssue(
                        severity="warning",
                        code="BAD_ADJACENCY",
                        message=f"Face {face_index} edge {edge_index} references missing adjacent face {adjacent}.",
                        face_index=face_index,
                        edge_index=edge_index,
                    )
                )

    walkable_count = _walkable_face_count(wok)
    if faces and walkable_count == 0:
        issues.append(
            WalkmeshValidationIssue(
                severity="error",
                code="NO_WALKABLE_FACES",
                message="No faces use a walkable surface material, so creatures cannot path through this room.",
            )
        )

    boundary_edges = _boundary_edges(wok)
    if walkable_count > 0 and not boundary_edges:
        issues.append(
            WalkmeshValidationIssue(
                severity="warning",
                code="NO_BOUNDARY_EDGES",
                message="No walkable boundary edges were detected; review blockers and perimeter walls before save.",
            )
        )

    transition_count = sum(
        1
        for face in faces
        if int(getattr(face, "surface", 0)) == 18 or _surface_name(int(getattr(face, "surface", 0))) == "DOOR"
    )
    if walkable_count > 0 and transition_count == 0:
        issues.append(
            WalkmeshValidationIssue(
                severity="info",
                code="NO_TRANSITION_SURFACES",
                message="No DOOR transition surfaces were found; that is fine for isolated rooms but unusual for connected modules.",
            )
        )

    has_errors = any(issue.severity.lower() == "error" for issue in issues)
    return WalkmeshValidationReport(
        ok=not has_errors,
        room=room_name,
        vertex_count=len(verts),
        face_count=len(faces),
        walkable_face_count=walkable_count,
        non_walk_face_count=_non_walk_face_count(wok),
        boundary_edge_count=len(boundary_edges),
        transition_face_count=transition_count,
        surface_distribution=_surface_distribution(wok),
        issues=issues,
        message="Walkmesh validation passed." if not has_errors else "Walkmesh validation found blocking errors.",
        code="valid" if not has_errors else "invalid",
    )


def roundtrip_walkmesh(module_like: Any, *, room: str = "") -> WalkmeshRoundTripResult:
    """Serialize and reparse a WOK, confirming core counts/materials survive."""

    room_name, wok = _select_wok(module_like, room)
    if wok is None:
        return WalkmeshRoundTripResult(ok=False, room=room_name, message="No walkmesh loaded.", code="no_walkmesh")

    if not hasattr(wok, "to_bytes"):
        return WalkmeshRoundTripResult(
            ok=False,
            room=room_name,
            message="The loaded walkmesh object cannot be serialized.",
            code="no_writer",
        )

    data = wok.to_bytes()
    mf = _import_module_format()
    reparsed = mf.WOKData.from_bytes(data)
    same_counts = len(getattr(reparsed, "verts", [])) == len(getattr(wok, "verts", [])) and len(
        getattr(reparsed, "faces", [])
    ) == len(getattr(wok, "faces", []))
    same_materials = _surface_distribution(reparsed) == _surface_distribution(wok)
    ok = same_counts and same_materials

    return WalkmeshRoundTripResult(
        ok=ok,
        room=room_name,
        original_size=len(getattr(wok, "raw", b"") or b""),
        output_size=len(data),
        reparsed_vertex_count=len(getattr(reparsed, "verts", [])),
        reparsed_face_count=len(getattr(reparsed, "faces", [])),
        material_distribution=_surface_distribution(reparsed),
        message="Walkmesh binary round-trip preserved vertices, faces, and surface materials."
        if ok
        else "Walkmesh binary round-trip changed counts or surface materials.",
        code="roundtrip_ok" if ok else "roundtrip_changed",
    )
