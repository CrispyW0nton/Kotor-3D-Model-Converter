"""Renderer-ready terrain walkability overlays for Map Studio.

The Terrain Builder owns WOK surface classification in core.  This module
turns that classification into lightweight triangle payloads the Qt viewport
can paint without knowing terrain or walkmesh policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .authored_module_project import AuthoredModuleProject
from .authored_terrain_builder import TerrainHeightfieldPrimitive, analyse_terrain_slopes, build_terrain_wok, terrain_triangle_slope_degrees
from .authored_walkmesh_audit import audit_authored_wok
from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface, walkmesh_surface_name

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredTerrainWalkabilityTriangle:
    """One WOK triangle projected from authored terrain intent."""

    room_resref: str
    face_index: int
    points: tuple[Vec3, Vec3, Vec3]
    surface_id: int
    surface_name: str
    walkable: bool
    slope_degrees: float
    color: str
    reason: str = ""
    validation_state: str = "unknown"
    color_role: str = "warning"
    validation_issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredWalkmeshOverlayValidation:
    """Per-room visual state derived from the serialized engine WOK contract."""

    room_resref: str
    state: str = "unknown"
    ready: bool = False
    color_role: str = "warning"
    color: str = "#d8a326"
    perimeter_count: int = 0
    closed_perimeter_count: int = 0
    issue_codes: tuple[str, ...] = ()
    message: str = "Walkmesh validation has not run."


@dataclass(frozen=True)
class AuthoredTerrainWalkabilityOverlay:
    """Complete terrain walkability overlay for the active authored module."""

    triangles: tuple[AuthoredTerrainWalkabilityTriangle, ...] = ()
    walkable_triangle_count: int = 0
    non_walk_triangle_count: int = 0
    max_slope_degrees: float = 0.0
    validation_state: str = "unknown"
    valid_room_count: int = 0
    invalid_room_count: int = 0
    unknown_room_count: int = 0
    room_validations: tuple[AuthoredWalkmeshOverlayValidation, ...] = ()
    warnings: tuple[str, ...] = ()


def _offset_point(point: Vec3, offset: Vec3) -> Vec3:
    return (
        float(point[0]) + float(offset[0]),
        float(point[1]) + float(offset[1]),
        float(point[2]) + float(offset[2]),
    )


def _raw_wok_inspector():
    for name in (
        "src.core.validation.kotor_module_engine_contract",
        "core.validation.kotor_module_engine_contract",
    ):
        try:
            return import_module(name).inspect_raw_wok_structure
        except (ImportError, AttributeError):
            continue
    return None


def authored_walkmesh_overlay_validation(
    room_resref: str,
    wok: Any,
    *,
    raw_wok_bytes: bytes | None = None,
) -> AuthoredWalkmeshOverlayValidation:
    """Classify a WOK using topology audit plus the raw perimeter-aware gate."""

    room = str(room_resref or "").strip().lower()
    if wok is None:
        return AuthoredWalkmeshOverlayValidation(
            room_resref=room,
            state="invalid",
            color_role="error",
            color="#c93434",
            issue_codes=("map.engine.wok.missing",),
            message=f"{room or '(unnamed room)'}.wok is missing.",
        )
    audit = audit_authored_wok(room, wok)
    inspector = _raw_wok_inspector()
    if inspector is None:
        return AuthoredWalkmeshOverlayValidation(
            room_resref=room,
            state="unknown",
            color_role="warning",
            color="#d8a326",
            issue_codes=("map.engine.wok.validation_unavailable",),
            message="Raw WOK engine-contract validation is unavailable in this runtime.",
        )
    try:
        payload = bytes(raw_wok_bytes) if raw_wok_bytes is not None else bytes(wok.to_bytes())
        fingerprint, report = inspector(room, payload)
    except Exception as exc:
        return AuthoredWalkmeshOverlayValidation(
            room_resref=room,
            state="invalid",
            color_role="error",
            color="#c93434",
            issue_codes=("map.engine.wok.serialization_failed",),
            message=f"{room or '(unnamed room)'}.wok could not be serialized and validated: {exc}",
        )

    issue_codes = tuple(
        dict.fromkeys(
            str(getattr(issue, "code", "") or "")
            for issue in tuple(getattr(report, "issues", ()) or ())
            if str(getattr(issue, "code", "") or "")
        )
    )
    perimeter_count = int(getattr(fingerprint, "perimeter_count", 0) or 0)
    closed_perimeter_count = int(getattr(fingerprint, "closed_perimeter_count", 0) or 0)
    raw_blocking = bool(getattr(report, "has_blocking", False))
    blocking = bool(tuple(audit.blocking_messages or ())) or raw_blocking
    if perimeter_count <= 0 or closed_perimeter_count != perimeter_count:
        blocking = True
    if blocking:
        messages = [str(value) for value in tuple(audit.blocking_messages or ()) if str(value)]
        messages.extend(
            str(getattr(issue, "message", "") or "")
            for issue in tuple(getattr(report, "blocking_issues", ()) or ())
            if str(getattr(issue, "message", "") or "")
        )
        return AuthoredWalkmeshOverlayValidation(
            room_resref=room,
            state="invalid",
            ready=False,
            color_role="error",
            color="#c93434",
            perimeter_count=perimeter_count,
            closed_perimeter_count=closed_perimeter_count,
            issue_codes=issue_codes or ("map.engine.wok.invalid",),
            message=" ".join(dict.fromkeys(messages)) or "Serialized WOK failed the engine contract.",
        )
    return AuthoredWalkmeshOverlayValidation(
        room_resref=room,
        state="valid",
        ready=True,
        color_role="success",
        color="#1b8f45",
        perimeter_count=perimeter_count,
        closed_perimeter_count=closed_perimeter_count,
        issue_codes=issue_codes,
        message=(
            f"Serialized WOK passed the engine contract with {closed_perimeter_count} closed perimeter loop(s)."
        ),
    )


def authored_terrain_walkability_overlay_for_project(project: AuthoredModuleProject) -> AuthoredTerrainWalkabilityOverlay:
    """Return UI-ready walkability triangles for terrain rooms in a project."""

    triangles: list[AuthoredTerrainWalkabilityTriangle] = []
    warnings: list[str] = []
    room_validations: list[AuthoredWalkmeshOverlayValidation] = []
    max_slope = 0.0
    for room in tuple(project.rooms or ()):
        primitive = room.primitive
        if not isinstance(primitive, TerrainHeightfieldPrimitive):
            continue
        room_resref = room.normalised_resref()
        offset = tuple(float(value) for value in tuple(room.position or (0.0, 0.0, 0.0))[:3])
        if len(offset) < 3:
            offset = (0.0, 0.0, 0.0)
        report = analyse_terrain_slopes(primitive)
        max_slope = max(max_slope, float(report.max_slope_degrees))
        warnings.extend(report.warnings)
        wok = build_terrain_wok(primitive)
        validation = authored_walkmesh_overlay_validation(room_resref, wok)
        room_validations.append(validation)
        if validation.state != "valid":
            warnings.append(f"Terrain room {room_resref}: {validation.message}")
        verts = tuple(tuple(float(axis) for axis in vertex[:3]) for vertex in tuple(getattr(wok, "verts", ()) or ()))
        faces = tuple(getattr(wok, "faces", ()) or ())
        for face_index, face in enumerate(faces):
            vertex_indices = (
                int(getattr(face, "v1", -1)),
                int(getattr(face, "v2", -1)),
                int(getattr(face, "v3", -1)),
            )
            if any(index < 0 or index >= len(verts) for index in vertex_indices):
                warnings.append(f"Terrain room {room_resref} face {face_index} references an invalid vertex.")
                continue
            points = tuple(_offset_point(verts[index], offset) for index in vertex_indices)
            slope = terrain_triangle_slope_degrees(points[0], points[1], points[2])
            max_slope = max(max_slope, float(slope))
            surface_id = int(getattr(face, "surface", -1))
            try:
                walkable = is_walkable_walkmesh_surface(surface_id)
                surface_name = walkmesh_surface_name(surface_id)
            except ValueError:
                walkable = False
                surface_name = f"SURFACE_{surface_id}"
            reason = ""
            if not walkable:
                if slope > float(primitive.max_walkable_slope_degrees):
                    reason = f"Slope {slope:.1f} deg exceeds {float(primitive.max_walkable_slope_degrees):.1f} deg."
                else:
                    reason = f"Surface {surface_id} ({surface_name}) is not walkable."
            triangles.append(
                AuthoredTerrainWalkabilityTriangle(
                    room_resref=room_resref,
                    face_index=face_index,
                    points=points,  # type: ignore[arg-type]
                    surface_id=surface_id,
                    surface_name=surface_name,
                    walkable=walkable,
                    slope_degrees=float(slope),
                    color=validation.color,
                    reason=reason,
                    validation_state=validation.state,
                    color_role=validation.color_role,
                    validation_issue_codes=validation.issue_codes,
                )
            )
    walkable_count = sum(1 for triangle in triangles if triangle.walkable)
    non_walk_count = len(triangles) - walkable_count
    invalid_room_count = sum(1 for item in room_validations if item.state == "invalid")
    unknown_room_count = sum(1 for item in room_validations if item.state == "unknown")
    valid_room_count = sum(1 for item in room_validations if item.state == "valid")
    validation_state = "invalid" if invalid_room_count else "unknown" if unknown_room_count else "valid" if room_validations else "unknown"
    return AuthoredTerrainWalkabilityOverlay(
        triangles=tuple(triangles),
        walkable_triangle_count=walkable_count,
        non_walk_triangle_count=non_walk_count,
        max_slope_degrees=float(max_slope),
        validation_state=validation_state,
        valid_room_count=valid_room_count,
        invalid_room_count=invalid_room_count,
        unknown_room_count=unknown_room_count,
        room_validations=tuple(room_validations),
        warnings=tuple(warnings),
    )


__all__ = [
    "AuthoredTerrainWalkabilityOverlay",
    "AuthoredTerrainWalkabilityTriangle",
    "AuthoredWalkmeshOverlayValidation",
    "authored_walkmesh_overlay_validation",
    "authored_terrain_walkability_overlay_for_project",
]
