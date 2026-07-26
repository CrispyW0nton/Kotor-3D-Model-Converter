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
class KotorSkyboxPreset:
    """One measured retail sky texture set exposed to Map Studio authors."""

    preset_id: str
    label: str
    game: str
    source_module: str
    source_room: str
    textures: FiveFaceSkyboxTextures
    building_style_ids: tuple[str, ...] = ()
    half_extent: float = 500.0
    bottom_z: float = -180.0
    top_z: float = 320.0


_KOTOR_SKYBOX_PRESETS = (
    KotorSkyboxPreset(
        preset_id="k1_endar_spire_starfield",
        label="Endar Spire — Deep-Space Starfield",
        game="K1",
        source_module="m01aa",
        source_room="m01aa_01a",
        # The Endar Spire uses these retail space plates behind its observation
        # ports rather than a conventional planetary sky room. Repeating the
        # seamless starfield on the dome keeps custom exterior views coherent.
        textures=FiveFaceSkyboxTextures(
            north="lhr_space01",
            east="lhr_space02",
            south="lhr_space01",
            west="lhr_space02",
            top="lhr_space01",
        ),
        building_style_ids=("architecture:k1_endar_spire",),
        half_extent=360.0,
        bottom_z=-180.0,
        top_z=240.0,
    ),
    KotorSkyboxPreset(
        preset_id="k1_taris_upper_city",
        label="Taris — Upper City Skyline (M02AB)",
        game="K1",
        source_module="m02ab",
        source_room="m02ab_sky",
        # M02AB_SKY is oriented +Y/+X/-Y/-X/top as 0003/0002/0001/0004/0005.
        textures=FiveFaceSkyboxTextures(
            north="lts_sky0003",
            east="lts_sky0002",
            south="lts_sky0001",
            west="lts_sky0004",
            top="lts_sky0005",
        ),
        building_style_ids=("architecture:k1_taris_apartments",),
        half_extent=500.0,
        bottom_z=-180.0,
        top_z=320.0,
    ),
    KotorSkyboxPreset(
        preset_id="k1_shadowlands_canopy",
        label="Shadowlands — Dense Forest Canopy",
        game="K1",
        source_module="m25ab",
        source_room="m25ab_01a",
        # Shadowlands rooms use LKA_TREE05 as a cylindrical forest surround,
        # not a directional horizon. Repeating it on the authored sectors
        # preserves that enclosed, depth-fogged canopy treatment.
        textures=FiveFaceSkyboxTextures(
            north="lka_tree05",
            east="lka_tree05",
            south="lka_tree05",
            west="lka_tree05",
            top="lka_tree05",
        ),
        building_style_ids=("architecture:k1_shadowlands",),
        half_extent=260.0,
        bottom_z=-80.0,
        top_z=190.0,
    ),
    KotorSkyboxPreset(
        preset_id="k1_korriban_valley",
        label="Korriban — Valley Horizon (M36AA)",
        game="K1",
        source_module="m36aa",
        source_room="m36aa_04",
        # M36AA_04 stores +X/+Y/-Y/-X/top as 01/02/03/04/05.
        textures=FiveFaceSkyboxTextures(
            north="lko_sky02",
            east="lko_sky01",
            south="lko_sky03",
            west="lko_sky04",
            top="lko_sky05",
        ),
        building_style_ids=(
            "architecture:k1_korriban_tombs",
            "architecture:k1_korriban_caves",
        ),
        half_extent=460.0,
        bottom_z=-160.0,
        top_z=300.0,
    ),
    KotorSkyboxPreset(
        preset_id="k2_onderon_iziz_daylight",
        label="Onderon — Iziz Daylight (502OND)",
        game="K2",
        source_module="502ond",
        source_room="502ondd",
        # 502ONDD's retail backdrop meshes are Side02/01/04/03 plus
        # Top.  Map Studio remaps those inward-facing sectors into its
        # documented north/east/south/west/top order.
        textures=FiveFaceSkyboxTextures(
            north="ond_sky1",
            east="ond_sky2",
            south="ond_sky3",
            west="ond_sky4",
            top="ond_sky5",
        ),
        building_style_ids=(
            "architecture:k2_onderon_city",
            "architecture:k2_onderon_cantina",
            "architecture:k2_onderon_palace",
        ),
        half_extent=420.0,
        bottom_z=-140.0,
        top_z=280.0,
    ),
    KotorSkyboxPreset(
        preset_id="k2_onderon_sky_ramp",
        label="Onderon — Sky Ramp Horizon (504OND)",
        game="K2",
        source_module="504ond",
        source_room="504ondg",
        textures=FiveFaceSkyboxTextures(
            north="ond_sb01",
            east="ond_sb02",
            south="ond_sb03",
            west="ond_sb04",
            top="ond_sb05",
        ),
        building_style_ids=("architecture:k2_onderon_sky_ramp",),
        half_extent=520.0,
        bottom_z=-180.0,
        top_z=340.0,
    ),
    KotorSkyboxPreset(
        preset_id="k2_rhen_var_polar_day",
        label="Rhen Var — Lago d'Isola Alpine HDR Vista (CC0)",
        game="K2",
        source_module="lago_disola",
        source_room="cc0_hdr",
        # Andreas Mischok's CC0 Lago d'Isola HDRI is projected and ACES
        # tone-mapped offline into KOTOR's five inward-facing sky panels.
        # Telos 261TEL still supplies the K2-native polar lighting reference;
        # the permission-tracked Rhen Var mods supply the architecture.
        textures=FiveFaceSkyboxTextures(
            north="gr_rvskyn",
            east="gr_rvskye",
            south="gr_rvskys",
            west="gr_rvskyw",
            top="gr_rvskyt",
        ),
        building_style_ids=("architecture:k2_rhen_var",),
        half_extent=520.0,
        bottom_z=-180.0,
        top_z=340.0,
    ),
)


def available_kotor_skybox_presets(
    game: str = "",
    building_style_id: str = "",
) -> tuple[KotorSkyboxPreset, ...]:
    """Return retail sky recipes without copying any game texture bytes."""

    wanted = str(game or "").strip().upper()
    style_id = str(building_style_id or "").strip().lower()
    presets = tuple(
        preset
        for preset in _KOTOR_SKYBOX_PRESETS
        if not wanted or preset.game == wanted
    )
    if not style_id:
        return presets
    return tuple(
        sorted(
            presets,
            key=lambda preset: (
                style_id not in {value.lower() for value in preset.building_style_ids},
                preset.label.lower(),
            ),
        )
    )


def kotor_skybox_preset(preset_id: str) -> KotorSkyboxPreset | None:
    """Resolve one stable preset identifier."""

    wanted = str(preset_id or "").strip().lower()
    return next(
        (
            preset
            for preset in _KOTOR_SKYBOX_PRESETS
            if preset.preset_id.lower() == wanted
        ),
        None,
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
    "KotorSkyboxPreset",
    "SKYBOX_AUTHORING_KIND",
    "SKYBOX_DOME_SUBDIVISIONS",
    "SKYBOX_FACE_ORDER",
    "SKYBOX_ROOM_ROLE",
    "SKYBOX_SURFACE_ROLE",
    "available_kotor_skybox_presets",
    "build_empty_skybox_wok",
    "build_five_face_skybox_room",
    "kotor_skybox_preset",
    "validate_five_face_skybox_spec",
]
