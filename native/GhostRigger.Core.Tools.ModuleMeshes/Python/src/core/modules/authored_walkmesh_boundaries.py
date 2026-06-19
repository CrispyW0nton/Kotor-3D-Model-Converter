"""Authored WOK boundary policy for game-facing Map Studio exports.

Primitive room tools usually author floor/ramp/stair walkable surfaces first.
Before packaging a playable module, Map Studio also needs a clear policy for
the walkmesh perimeter so camera/LOS/collision-facing WOK data is not just a
flat open plane.  This module owns that headless export policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_room_geometry import AuthoredRoomGeometry
from .module_format import WOKData, WalkmeshWallGenerator


@dataclass(frozen=True)
class AuthoredWalkmeshBoundaryResult:
    """WOK plus a compact report of non-walk perimeter wall generation."""

    wok: WOKData
    enabled: bool
    wall_height: float
    source_vertex_count: int
    source_face_count: int
    source_boundary_edge_count: int
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
    """Return a WOK with vertical NON_WALK walls on exposed walkable edges.

    The input WOK is never mutated.  When disabled, the original WOK is returned
    in the result so callers can still report a uniform policy payload.
    """

    source_vertex_count = len(getattr(wok, "verts", ()) or ())
    source_face_count = len(getattr(wok, "faces", ()) or ())
    source_boundary_edges = list(wok.boundary_edges()) if hasattr(wok, "boundary_edges") else []
    height = float(wall_height)
    if not enabled:
        output = wok
    else:
        output = WalkmeshWallGenerator(wall_height=height).generate(wok)
    added_vertices = len(getattr(output, "verts", ()) or ()) - source_vertex_count
    added_faces = len(getattr(output, "faces", ()) or ()) - source_face_count
    non_walk_faces = int(output.non_walk_face_count()) if hasattr(output, "non_walk_face_count") else 0
    metadata = {
        "source": "src.core.modules.authored_walkmesh_boundaries",
        "enabled": bool(enabled),
        "wall_height": height,
        "source_vertex_count": source_vertex_count,
        "source_face_count": source_face_count,
        "source_boundary_edge_count": len(source_boundary_edges),
        "added_vertex_count": added_vertices,
        "added_face_count": added_faces,
        "non_walk_face_count": non_walk_faces,
    }
    return AuthoredWalkmeshBoundaryResult(
        wok=output,
        enabled=bool(enabled),
        wall_height=height,
        source_vertex_count=source_vertex_count,
        source_face_count=source_face_count,
        source_boundary_edge_count=len(source_boundary_edges),
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
    """Return room geometry whose WOK includes export-time boundary walls."""

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
            "walkmesh_boundary_wall_faces": int(result.added_face_count),
            "walkmesh_non_walk_face_count": int(result.non_walk_face_count),
        },
    )


__all__ = [
    "AuthoredWalkmeshBoundaryResult",
    "add_authored_walkmesh_boundary_walls",
    "apply_authored_walkmesh_boundary_policy_to_geometry",
]
