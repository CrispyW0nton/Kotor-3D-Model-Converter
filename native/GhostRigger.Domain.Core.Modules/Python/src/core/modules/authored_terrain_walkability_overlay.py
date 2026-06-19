"""Renderer-ready terrain walkability overlays for Map Studio.

The Terrain Builder owns WOK surface classification in core.  This module
turns that classification into lightweight triangle payloads the Qt viewport
can paint without knowing terrain or walkmesh policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .authored_module_project import AuthoredModuleProject
from .authored_terrain_builder import TerrainHeightfieldPrimitive, analyse_terrain_slopes, build_terrain_wok, terrain_triangle_slope_degrees
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


@dataclass(frozen=True)
class AuthoredTerrainWalkabilityOverlay:
    """Complete terrain walkability overlay for the active authored module."""

    triangles: tuple[AuthoredTerrainWalkabilityTriangle, ...] = ()
    walkable_triangle_count: int = 0
    non_walk_triangle_count: int = 0
    max_slope_degrees: float = 0.0
    warnings: tuple[str, ...] = ()


def _offset_point(point: Vec3, offset: Vec3) -> Vec3:
    return (
        float(point[0]) + float(offset[0]),
        float(point[1]) + float(offset[1]),
        float(point[2]) + float(offset[2]),
    )


def authored_terrain_walkability_overlay_for_project(project: AuthoredModuleProject) -> AuthoredTerrainWalkabilityOverlay:
    """Return UI-ready walkability triangles for terrain rooms in a project."""

    triangles: list[AuthoredTerrainWalkabilityTriangle] = []
    warnings: list[str] = []
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
                    color="#00ff7a" if walkable else "#ff9f1c",
                    reason=reason,
                )
            )
    walkable_count = sum(1 for triangle in triangles if triangle.walkable)
    non_walk_count = len(triangles) - walkable_count
    return AuthoredTerrainWalkabilityOverlay(
        triangles=tuple(triangles),
        walkable_triangle_count=walkable_count,
        non_walk_triangle_count=non_walk_count,
        max_slope_degrees=float(max_slope),
        warnings=tuple(warnings),
    )


__all__ = [
    "AuthoredTerrainWalkabilityOverlay",
    "AuthoredTerrainWalkabilityTriangle",
    "authored_terrain_walkability_overlay_for_project",
]
