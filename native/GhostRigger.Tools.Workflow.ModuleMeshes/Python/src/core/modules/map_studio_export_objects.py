"""Map Studio export-object boundary summaries.

The Level Editor stores editable authored intent, but modders need to know
which objects/rooms will become independent MDL/MDX/WOK outputs before they
leave GhostRigger for UVs or texture work.  This module keeps that policy in
the headless module layer instead of making Qt panels inspect KMAP payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_project import (
    AuthoredModuleProject,
    compile_authored_room_spec,
    normalise_resref,
)
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_terrain_builder import TerrainHeightfieldPrimitive


@dataclass(frozen=True)
class MapStudioExportObjectBoundary:
    """One modder-facing object/room boundary produced by Map Studio export."""

    object_id: str
    label: str
    source_room_resref: str
    object_kind: str
    export_resref: str
    resources: tuple[tuple[str, str], ...]
    primitive_type: str
    primitive_count: int = 0
    helper_mesh_count: int = 0
    render_mesh_count: int = 0
    walkmesh_face_count: int = 0
    walkable_face_count: int = 0
    material_textures: tuple[str, ...] = ()
    uv_handoff_recommended: bool = False
    status: str = "export_candidate"
    notes: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        """Return a stable JSON/KMAP-friendly dictionary for readiness panels."""

        return {
            "object_id": self.object_id,
            "label": self.label,
            "source_room_resref": self.source_room_resref,
            "object_kind": self.object_kind,
            "export_resref": self.export_resref,
            "resources": [[resref, restype] for resref, restype in self.resources],
            "primitive_type": self.primitive_type,
            "primitive_count": self.primitive_count,
            "helper_mesh_count": self.helper_mesh_count,
            "render_mesh_count": self.render_mesh_count,
            "walkmesh_face_count": self.walkmesh_face_count,
            "walkable_face_count": self.walkable_face_count,
            "material_textures": list(self.material_textures),
            "uv_handoff_recommended": self.uv_handoff_recommended,
            "status": self.status,
            "notes": list(self.notes),
            "blocking_messages": list(self.blocking_messages),
        }


def _primitive_texture(value: Any) -> str:
    material = getattr(value, "material", None)
    return str(getattr(material, "texture", "") or "").strip()


def _base_primitive(value: Any) -> Any:
    return value.primitive if isinstance(value, PlacedRoomPrimitive) else value


def _composition_textures(composition: AuthoredRoomComposition) -> tuple[str, ...]:
    textures: list[str] = []
    floor_texture = _primitive_texture(composition.floor)
    if floor_texture:
        textures.append(floor_texture)
    for primitive in tuple(composition.primitives or ()):
        texture = _primitive_texture(_base_primitive(primitive))
        if texture:
            textures.append(texture)
    return tuple(dict.fromkeys(textures))


def _object_kind(primitive: Any, metadata: dict[str, Any]) -> str:
    if isinstance(primitive, AuthoredRoomComposition):
        if metadata.get("separated_from_room"):
            return "separated_primitive_object"
        return "composition_room"
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        return "terrain_room"
    if isinstance(primitive, FloorPlanRoomPrimitive):
        return "floor_plan_room"
    if isinstance(primitive, RectangularRoomPrimitive):
        return "rectangular_room"
    return type(primitive).__name__.removesuffix("Primitive").lower() or "room"


def _primitive_count(primitive: Any) -> int:
    if isinstance(primitive, AuthoredRoomComposition):
        return len(tuple(primitive.primitives or ())) + 1
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        rows = len(tuple(primitive.heights or ()))
        cols = len(tuple(primitive.heights[0] or ())) if rows else 0
        return rows * cols
    return 1


def _object_notes(*, primitive: Any, metadata: dict[str, Any], resref: str) -> tuple[str, ...]:
    notes = [f"Exports as {resref}.mdl, {resref}.mdx, and {resref}.wok."]
    if isinstance(primitive, AuthoredRoomComposition):
        if metadata.get("separated_from_room"):
            notes.append(
                f"Separated from {normalise_resref(metadata.get('separated_from_room'))}; "
                "safe for independent DCC UV/texturing handoff."
            )
        else:
            notes.append("Composition room keeps authored primitives as one export boundary.")
    elif isinstance(primitive, TerrainHeightfieldPrimitive):
        notes.append("Terrain boundary should keep sculpt changes and WOK validation together.")
    elif isinstance(primitive, FloorPlanRoomPrimitive):
        notes.append("Floor-plan boundary is suitable for external UV cleanup after geometry stabilizes.")
    return tuple(notes)


def map_studio_export_object_boundaries(project: AuthoredModuleProject) -> tuple[MapStudioExportObjectBoundary, ...]:
    """Return modder-facing export object boundaries for an authored module."""

    boundaries: list[MapStudioExportObjectBoundary] = []
    for room in tuple(project.rooms or ()):
        resref = normalise_resref(room.room_resref)
        metadata = dict(room.metadata or {})
        primitive = room.primitive
        primitive_type = type(primitive).__name__
        blocking: list[str] = []
        helper_mesh_count = 0
        render_mesh_count = 0
        walkmesh_face_count = 0
        walkable_face_count = 0
        material_textures: tuple[str, ...] = ()
        try:
            geometry = compile_authored_room_spec(room)
            helpers = tuple(getattr(geometry, "helper_meshes", ()) or ())
            helper_mesh_count = len(helpers)
            render_mesh_count = 1 + helper_mesh_count
            faces = tuple(getattr(getattr(geometry, "wok", None), "faces", ()) or ())
            walkmesh_face_count = len(faces)
            walkable_face_count = int(getattr(geometry.wok, "walkable_face_count", lambda: 0)())
            room_texture = str(getattr(geometry.room_mesh, "texture", "") or "").strip()
            if room_texture:
                material_textures = (room_texture,)
        except Exception as exc:
            blocking.append(f"Export object {resref or '(unnamed)'} could not compile: {exc}")
        if isinstance(primitive, AuthoredRoomComposition):
            material_textures = _composition_textures(primitive) or material_textures
        kind = _object_kind(primitive, metadata)
        uv_handoff = kind in {"composition_room", "separated_primitive_object", "floor_plan_room", "rectangular_room"}
        boundaries.append(
            MapStudioExportObjectBoundary(
                object_id=f"room:{resref}",
                label=f"{resref} ({kind.replace('_', ' ')})",
                source_room_resref=resref,
                object_kind=kind,
                export_resref=resref,
                resources=((resref, "mdl"), (resref, "mdx"), (resref, "wok")),
                primitive_type=primitive_type,
                primitive_count=_primitive_count(primitive),
                helper_mesh_count=helper_mesh_count,
                render_mesh_count=render_mesh_count,
                walkmesh_face_count=walkmesh_face_count,
                walkable_face_count=walkable_face_count,
                material_textures=material_textures,
                uv_handoff_recommended=uv_handoff,
                status="blocked" if blocking else "export_candidate",
                notes=_object_notes(primitive=primitive, metadata=metadata, resref=resref),
                blocking_messages=tuple(blocking),
            )
        )
    return tuple(boundaries)


__all__ = [
    "MapStudioExportObjectBoundary",
    "map_studio_export_object_boundaries",
]
