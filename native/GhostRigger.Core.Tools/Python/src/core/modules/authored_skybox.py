"""Headless five-sector sky-dome authoring for Map Studio.

Callers provide five imported KOTOR texture resrefs (north, east, south, west,
top).  The sectors use a subdivided cube-to-ellipsoid projection: adjacent
edges are coincident, the surface reads as a dome from inside, and the result
remains an ordinary ``ImportedMeshRoomPrimitive`` that existing KMAP/MDL
export paths can carry without a parallel runtime format.  Like retail-scale
Odyssey backdrop rooms, it is visual-only and receives an exact empty WOK.
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
SKYBOX_DOME_SUBDIVISIONS = 12


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
    """Editable intent for a visual-only, five-sector sky-dome room.

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


def _face_direction(face: str, u: float, v: float) -> Vec3:
    """Return the cube-map direction matching the legacy five-face UV order."""

    a = (2.0 * float(u)) - 1.0
    b = (2.0 * float(v)) - 1.0
    direction = {
        "north": (a, 1.0, b),
        "east": (1.0, -a, b),
        "south": (-a, -1.0, b),
        "west": (-1.0, a, b),
        "top": (b, a, 1.0),
    }[face]
    length = math.sqrt(sum(component * component for component in direction))
    return tuple(component / length for component in direction)  # type: ignore[return-value]


def _dome_vertex(face: str, u: float, v: float, spec: FiveFaceSkyboxSpec) -> tuple[Vec3, Vec3]:
    direction = _face_direction(face, u, v)
    horizontal_radius = float(spec.half_extent)
    bottom = float(spec.bottom_z)
    top = float(spec.top_z)
    center_z = (bottom + top) * 0.5
    vertical_radius = (top - bottom) * 0.5
    point = (
        direction[0] * horizontal_radius,
        direction[1] * horizontal_radius,
        center_z + (direction[2] * vertical_radius),
    )
    # Ellipsoid gradient, negated because the sky renders from inside.
    gradient = (
        point[0] / (horizontal_radius * horizontal_radius),
        point[1] / (horizontal_radius * horizontal_radius),
        (point[2] - center_z) / (vertical_radius * vertical_radius),
    )
    length = math.sqrt(sum(component * component for component in gradient))
    normal = tuple(-component / length for component in gradient)
    return point, normal  # type: ignore[return-value]


def _surface(face: str, texture: str, spec: FiveFaceSkyboxSpec) -> ImportedMeshSurface:
    divisions = SKYBOX_DOME_SUBDIVISIONS
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    uvs: list[tuple[float, float]] = []
    for row in range(divisions + 1):
        v = row / divisions
        for column in range(divisions + 1):
            u = column / divisions
            point, normal = _dome_vertex(face, u, v, spec)
            vertices.append(point)
            normals.append(normal)
            uvs.append((u, v))
    faces: list[tuple[int, int, int]] = []
    for row in range(divisions):
        for column in range(divisions):
            lower_left = (row * (divisions + 1)) + column
            lower_right = lower_left + 1
            upper_left = lower_left + divisions + 1
            upper_right = upper_left + 1
            faces.append((lower_left, lower_right, upper_right))
            faces.append((lower_left, upper_right, upper_left))
    average = tuple(sum(vertex[axis] for vertex in vertices) / len(vertices) for axis in range(3))
    return ImportedMeshSurface(
        name=f"sky_{face}",
        texture=normalise_resref(texture),
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=(0,) * len(faces),
        uvs=tuple(uvs),
        normals=tuple(normals),
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
        "skybox_geometry": "curved_dome",
        "skybox_subdivisions": SKYBOX_DOME_SUBDIVISIONS,
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
    "SKYBOX_DOME_SUBDIVISIONS",
    "SKYBOX_FACE_ORDER",
    "SKYBOX_ROOM_ROLE",
    "SKYBOX_SURFACE_ROLE",
    "build_empty_skybox_wok",
    "build_five_face_skybox_room",
    "validate_five_face_skybox_spec",
]
