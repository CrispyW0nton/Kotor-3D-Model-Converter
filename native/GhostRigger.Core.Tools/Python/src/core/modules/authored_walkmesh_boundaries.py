"""Floor-only authored WOK boundary policy for Map Studio exports.

Odyssey derives the traversable region from the external WOK's floor perimeter.
The proven ``plcaa`` KOTOR 2 contract is therefore deliberately narrower than
ordinary render collision: the game-facing WOK contains the floor/ramp/stair
surface and its perimeter records, *not* synthetic vertical NON_WALK quads.

Map Studio still reports perimeter-wall intent for editor overlays and helper
visualisation.  That intent is metadata only and never mutates the WOK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_room_geometry import AuthoredRoomGeometry
from .module_format import WOKData


@dataclass(frozen=True)
class AuthoredWalkmeshBoundaryResult:
    """Unchanged game WOK plus editor-only perimeter-wall intent."""

    wok: WOKData
    enabled: bool
    wall_height: float
    source_vertex_count: int
    source_face_count: int
    source_boundary_edge_count: int
    helper_segment_count: int
    helper_face_count: int
    added_vertex_count: int
    added_face_count: int
    non_walk_face_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


def add_authored_walkmesh_boundary_walls(
    wok: WOKData,
    *,
    enabled: bool = True,
    wall_height: float = 3.0,
) -> AuthoredWalkmeshBoundaryResult:
    """Report editor boundary helpers without changing the external WOK.

    ``enabled`` controls only the helper/overlay intent.  It must never add
    vertical faces to the returned WOK: doing so can enclose a valid floor and
    leave KOTOR 2 unable to resolve its walkable perimeter.  The compatibility
    ``added_*`` fields now describe actual game-WOK mutation and are therefore
    always zero.
    """

    source_vertex_count = len(getattr(wok, "verts", ()) or ())
    source_face_count = len(getattr(wok, "faces", ()) or ())
    source_boundary_edges = list(wok.boundary_edges()) if hasattr(wok, "boundary_edges") else []
    height = float(wall_height)
    output = wok
    helper_segments = len(source_boundary_edges) if enabled else 0
    helper_faces = helper_segments * 2
    added_vertices = 0
    added_faces = 0
    non_walk_faces = int(output.non_walk_face_count()) if hasattr(output, "non_walk_face_count") else 0
    metadata = {
        "source": "src.core.modules.authored_walkmesh_boundaries",
        "enabled": bool(enabled),
        "wall_height": height,
        "source_vertex_count": source_vertex_count,
        "source_face_count": source_face_count,
        "source_boundary_edge_count": len(source_boundary_edges),
        "editor_helper_segment_count": helper_segments,
        "editor_helper_face_count": helper_faces,
        "added_vertex_count": added_vertices,
        "added_face_count": added_faces,
        "non_walk_face_count": non_walk_faces,
        "game_wok_face_policy": "floor_only",
        "game_wok_mutated": False,
        "helper_geometry_only": True,
    }
    return AuthoredWalkmeshBoundaryResult(
        wok=output,
        enabled=bool(enabled),
        wall_height=height,
        source_vertex_count=source_vertex_count,
        source_face_count=source_face_count,
        source_boundary_edge_count=len(source_boundary_edges),
        helper_segment_count=helper_segments,
        helper_face_count=helper_faces,
        added_vertex_count=added_vertices,
        added_face_count=added_faces,
        non_walk_face_count=non_walk_faces,
        metadata=metadata,
    )


def apply_authored_walkmesh_boundary_policy_to_geometry(
    geometry: AuthoredRoomGeometry,
    *,
    enabled: bool = True,
    wall_height: float | None = None,
) -> AuthoredRoomGeometry:
    """Attach editor boundary intent while preserving a floor-only WOK."""

    from dataclasses import replace

    metadata = dict(getattr(geometry, "metadata", {}) or {})
    height = float(wall_height if wall_height is not None else metadata.get("wall_height", 3.0))
    result = add_authored_walkmesh_boundary_walls(geometry.wok, enabled=enabled, wall_height=height)
    return replace(
        geometry,
        wok=result.wok,
        metadata={
            **metadata,
            "walkmesh_boundary_walls": dict(result.metadata),
            # Legacy manifest/UI field: this is the number of triangles an
            # editor-only wall overlay would contain, never external WOK faces.
            "walkmesh_boundary_wall_faces": int(result.helper_face_count),
            "walkmesh_boundary_helper_faces": int(result.helper_face_count),
            "walkmesh_game_wok_face_policy": "floor_only",
            "walkmesh_non_walk_face_count": int(result.non_walk_face_count),
        },
    )


__all__ = [
    "AuthoredWalkmeshBoundaryResult",
    "add_authored_walkmesh_boundary_walls",
    "apply_authored_walkmesh_boundary_policy_to_geometry",
]
