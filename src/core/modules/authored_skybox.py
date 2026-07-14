"""Headless five-face skybox authoring for Map Studio.

This module owns only the deterministic authored-room recipe.  Panorama and
HDR conversion belongs in a later image/texture adapter; callers provide five
already-imported KOTOR texture resrefs here (north, east, south, west, top).
The resulting room is an ordinary ``ImportedMeshRoomPrimitive`` so the
existing KMAP and module-export paths can carry it without a parallel format.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
from .authored_module_project import AuthoredRoomSpec, authored_resref_blocking_issue, normalise_resref
from .module_format import WOKData


Vec3 = tuple[float, float, float]

SKYBOX_FACE_ORDER = ("north", "east", "south", "west", "top")
SKYBOX_SURFACE_ROLE = "visual_only_backdrop"
SKYBOX_ROOM_ROLE = "visual_only_backdrop"
SKYBOX_AUTHORING_KIND = "five_face_skybox"


@dataclass(frozen=True)
class FiveFaceSkyboxTextures:
    """Texture resrefs mapped to the five inward-facing skybox panels."""

    north: str
    east: str
    south: str
    west: str
    top: str

    def ordered_items(self) -> tuple[tuple[str, str], ...]:
        return (
            ("north", self.north),
            ("east", self.east),
            ("south", self.south),
            ("west", self.west),
            ("top", self.top),
        )


@dataclass(frozen=True)
class FiveFaceSkyboxSpec:
    """Editable intent for a visual-only, five-face skybox room.

    Geometry uses KOTOR's Z-up room space.  North is +Y and east is +X.
    ``bottom_z`` and ``top_z`` are room-local, while ``position`` is the LYT
    room placement.  The box intentionally has no bottom panel.
    """

    room_resref: str
    textures: FiveFaceSkyboxTextures
    half_extent: float = 500.0
    bottom_z: float = -500.0
    top_z: float = 500.0
    position: Vec3 = (0.0, 0.0, 0.0)
    visible_rooms: tuple[str, ...] = ()
    game: str = "K1"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FiveFaceSkyboxValidation:
    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_five_face_skybox_spec(spec: FiveFaceSkyboxSpec) -> FiveFaceSkyboxValidation:
    """Validate resref and geometry invariants without silently truncating."""

    blocking: list[str] = []
    room_issue = authored_resref_blocking_issue("Skybox room", spec.room_resref)
    if room_issue:
        blocking.append(room_issue)

    for face, texture in spec.textures.ordered_items():
        issue = authored_resref_blocking_issue(f"Skybox {face} texture", texture)
        if issue:
            blocking.append(issue)

    half_extent = _finite_float(spec.half_extent)
    bottom_z = _finite_float(spec.bottom_z)
    top_z = _finite_float(spec.top_z)
    if half_extent is None or half_extent <= 0.0:
        blocking.append("Skybox half extent must be a finite value greater than zero.")
    if bottom_z is None or top_z is None:
        blocking.append("Skybox bottom and top Z values must be finite.")
    elif top_z <= bottom_z:
        blocking.append("Skybox top Z must be greater than bottom Z.")

    try:
        position = tuple(spec.position)
    except TypeError:
        position = ()
    if len(position) != 3 or any(_finite_float(value) is None for value in position):
        blocking.append("Skybox room position must contain three finite XYZ values.")

    game = str(spec.game or "").strip().upper()
    if game not in {"K1", "K2"}:
        blocking.append("Skybox game must be K1 or K2.")

    for target in tuple(spec.visible_rooms or ()):
        issue = authored_resref_blocking_issue("Skybox visibility target", target)
        if issue:
            blocking.append(issue)

    return FiveFaceSkyboxValidation(ok=not blocking, blocking_issues=tuple(blocking))


def build_empty_skybox_wok(room_resref: str) -> WOKData:
    """Return the explicit zero-vertex/zero-face WOK used by visual-only rooms."""

    issue = authored_resref_blocking_issue("Skybox room", room_resref)
    if issue:
        raise ValueError(issue)
    return WOKData(name=normalise_resref(room_resref), verts=[], faces=[])


def _face_vertices(
    face: str,
    *,
    half_extent: float,
    bottom_z: float,
    top_z: float,
) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    e = float(half_extent)
    b = float(bottom_z)
    t = float(top_z)
    # Vertex order is counter-clockwise when each panel is viewed from inside
    # the box; (0, 1, 2) therefore points toward the room interior.
    vertices = {
        "north": ((-e, e, b), (e, e, b), (e, e, t), (-e, e, t)),
        "east": ((e, e, b), (e, -e, b), (e, -e, t), (e, e, t)),
        "south": ((e, -e, b), (-e, -e, b), (-e, -e, t), (e, -e, t)),
        "west": ((-e, -e, b), (-e, e, b), (-e, e, t), (-e, -e, t)),
        "top": ((-e, -e, t), (-e, e, t), (e, e, t), (e, -e, t)),
    }
    return vertices[face]


def _inward_normal(face: str) -> Vec3:
    return {
        "north": (0.0, -1.0, 0.0),
        "east": (-1.0, 0.0, 0.0),
        "south": (0.0, 1.0, 0.0),
        "west": (1.0, 0.0, 0.0),
        "top": (0.0, 0.0, -1.0),
    }[face]


def _surface(face: str, texture: str, spec: FiveFaceSkyboxSpec) -> ImportedMeshSurface:
    vertices = _face_vertices(
        face,
        half_extent=float(spec.half_extent),
        bottom_z=float(spec.bottom_z),
        top_z=float(spec.top_z),
    )
    normal = _inward_normal(face)
    average = tuple(sum(vertex[axis] for vertex in vertices) / 4.0 for axis in range(3))
    return ImportedMeshSurface(
        name=f"sky_{face}",
        texture=normalise_resref(texture),
        vertices=vertices,
        faces=((0, 1, 2), (0, 2, 3)),
        face_mats=(0, 0),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        normals=(normal,) * 4,
        texture_names=(normalise_resref(texture),),
        tex_count=1,
        has_shadow=False,
        render=True,
        background_geometry=True,
        mesh_average_point=average,
        backdrop=True,
    )


def _normalised_visible_rooms(spec: FiveFaceSkyboxSpec, room_resref: str) -> tuple[str, ...]:
    ordered = (room_resref, *(normalise_resref(item) for item in tuple(spec.visible_rooms or ())))
    result: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return tuple(result)


def build_five_face_skybox_room(spec: FiveFaceSkyboxSpec) -> AuthoredRoomSpec:
    """Build a KMAP-compatible visual-only room with an exact empty WOK."""

    validation = validate_five_face_skybox_spec(spec)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))

    room_resref = normalise_resref(spec.room_resref)
    textures = tuple(
        (face, normalise_resref(texture))
        for face, texture in spec.textures.ordered_items()
    )
    surfaces = tuple(_surface(face, texture, spec) for face, texture in textures)
    role_rows = [
        {"index": index, "face": face, "role": SKYBOX_SURFACE_ROLE}
        for index, (face, _texture) in enumerate(textures)
    ]

    invariant_metadata = {
        "authored_kind": SKYBOX_AUTHORING_KIND,
        "source": "map_studio:authored_skybox",
        "room_role": SKYBOX_ROOM_ROLE,
        "visual_only": True,
        "backdrop_only": True,
        "is_backdrop": True,
        "walkmesh_policy": "exact_empty_wok",
        "skybox_face_order": list(SKYBOX_FACE_ORDER),
        "surface_roles": role_rows,
        "texture_resrefs": {face: texture for face, texture in textures},
    }
    primitive_metadata = dict(spec.metadata or {})
    primitive_metadata.update(invariant_metadata)
    room_metadata = dict(spec.metadata or {})
    room_metadata.update(invariant_metadata)
    room_metadata["primitive"] = "imported_mesh"

    primitive = ImportedMeshRoomPrimitive(
        room_resref=room_resref,
        surfaces=surfaces,
        source_model="",
        game=str(spec.game).upper(),
        wok=build_empty_skybox_wok(room_resref),
        metadata=primitive_metadata,
    )
    return AuthoredRoomSpec(
        room_resref=room_resref,
        primitive=primitive,
        position=tuple(float(value) for value in spec.position),
        visible_rooms=_normalised_visible_rooms(spec, room_resref),
        metadata=room_metadata,
    )


__all__ = [
    "FiveFaceSkyboxSpec",
    "FiveFaceSkyboxTextures",
    "FiveFaceSkyboxValidation",
    "SKYBOX_AUTHORING_KIND",
    "SKYBOX_FACE_ORDER",
    "SKYBOX_ROOM_ROLE",
    "SKYBOX_SURFACE_ROLE",
    "build_empty_skybox_wok",
    "build_five_face_skybox_room",
    "validate_five_face_skybox_spec",
]
