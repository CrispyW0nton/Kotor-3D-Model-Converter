"""Full stock-module import for Map Studio.

Converts a complete KOTOR module (RIM + BIF resources) into an editable
``AuthoredModuleProject`` so Map Studio can edit geometry, placements,
lighting, and metadata — then re-export.

Pipeline:
    1. Read ARE/GIT/IFO from the module RIM
    2. Read LYT from chitin.key (room layout)
    3. Read VIS from chitin.key (room visibility)
    4. For each LYT room: load MDL/MDX → convert to PrimitiveMesh
    5. For each WOK: load walkmesh surface data
    6. Convert GIT creatures/placeables/doors/etc. → AuthoredGameplayPlacement
    7. Convert ARE metadata → AuthoredModuleMetadata
    8. Convert IFO entry point → ModuleEntryPoint
    9. Return a populated AuthoredModuleProject

Owner: Core.Scene (headless, Qt-free).  The caller (controller/window)
handles refresh and resource-manager wiring.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .authored_module_objects import (
    AuthoredCameraInstance,
    AuthoredCreatureInstance,
    AuthoredDoorInstance,
    AuthoredEncounterInstance,
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredSoundInstance,
    AuthoredStoreInstance,
    AuthoredTriggerInstance,
    AuthoredWaypointInstance,
    ModuleEntryPoint,
)
from .authored_module_project import (
    AuthoredModuleMetadata,
    AuthoredModuleProject,
    AuthoredRoomSpec,
    normalise_resref,
)
from .authored_room_geometry import PrimitiveMesh
from .authored_room_floorplan import FloorPlanRoomPrimitive

log = logging.getLogger(__name__)

Vec3 = tuple[float, float, float]
Vec4 = tuple[float, float, float, float]


@dataclass(frozen=True)
class StockModuleImportResult:
    """Result of importing a full stock module into an authored project."""

    project: AuthoredModuleProject | None
    room_count: int = 0
    placement_counts: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    source_module: str = ""
    source_game: str = ""

    @property
    def ok(self) -> bool:
        return self.project is not None and not self.errors


@dataclass(frozen=True)
class StockModuleAuxiliaryResources:
    """Selected-game LYT/VIS/PTH bytes and their physical source records."""

    area_resref: str = ""
    lyt_bytes: bytes | None = None
    vis_bytes: bytes | None = None
    pth_bytes: bytes | None = None
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


# ── Helpers ─────────────────────────────────────────────────────────────


def _gff_float(struct: Any, key: str, default: float = 0.0) -> float:
    try:
        val = struct.acquire(key, default)
        if val is not None:
            return float(val)
    except Exception:
        pass
    return default


def resolve_stock_module_auxiliary_resources(
    *,
    module_resref: str,
    game: str,
    rim_path: Path | str,
    resource_provider: Any = None,
) -> StockModuleAuxiliaryResources:
    """Resolve effective LYT/VIS/PTH bytes without crossing game installs.

    K1 module filenames frequently differ from the contained ARE resref.  For
    example, ``danm13.rim`` owns ``m13aa.are``; the auxiliary resources are
    consequently named ``m13aa`` and its PTH lives in ``danm13_s.rim``.
    """

    rim = Path(rim_path)
    module_name = normalise_resref(module_resref)
    game_tag = str(game or "K1").strip().upper()
    warnings: list[str] = []
    if not rim.is_file():
        return StockModuleAuxiliaryResources(
            area_resref=module_name,
            warnings=(f"Module container not found: {rim}",),
        )

    try:
        from pykotor.extract.capsule import LazyCapsule
        from pykotor.extract.installation import Installation, SearchLocation
        from pykotor.resource.formats.gff import read_gff
        from pykotor.resource.type import ResourceType as RT
    except Exception as exc:
        return StockModuleAuxiliaryResources(
            area_resref=module_name,
            warnings=(f"PyKotor auxiliary-resource resolver unavailable: {exc}",),
        )

    cap = LazyCapsule(rim)
    are_resrefs: list[str] = []
    entry_area = ""
    try:
        for resource in cap.resources():
            restype = resource.restype()
            resname = normalise_resref(resource.resname())
            if restype == RT.ARE and resname and resname not in are_resrefs:
                are_resrefs.append(resname)
            elif restype == RT.IFO and not entry_area:
                payload = cap.resource(resource.resname(), restype)
                if payload:
                    entry_area = normalise_resref(_gff_str(read_gff(payload).root, "Mod_Entry_Area"))
    except Exception as exc:
        warnings.append(f"Could not inspect {rim.name} area identity: {exc}")

    if entry_area and entry_area in are_resrefs:
        area_resref = entry_area
    elif are_resrefs:
        area_resref = are_resrefs[0]
    else:
        area_resref = entry_area or module_name
    if entry_area and are_resrefs and entry_area != area_resref:
        warnings.append(
            f"Primary ARE {area_resref} differs from IFO entry area {entry_area}; "
            f"using ARE resource name {area_resref} for LYT/VIS/PTH."
        )

    secondary_path = rim.parent / f"{module_name}_s.rim"
    secondary_cap = LazyCapsule(secondary_path) if secondary_path.is_file() else None

    def _record(source_path: Path | str, source_layer: str) -> dict[str, Any]:
        path = Path(source_path) if str(source_path or "") else Path()
        return {
            "resref": area_resref,
            "game": game_tag,
            "module_resref": module_name,
            "source_layer": source_layer,
            "source_path": str(source_path or ""),
            "source_archive": path.name if str(source_path or "") else "",
        }

    installation: Any = None

    def _resolve(restype: Any) -> tuple[bytes | None, dict[str, Any]]:
        nonlocal installation
        for candidate_cap, candidate_path, source_layer in (
            (cap, rim, "container"),
            (secondary_cap, secondary_path, "module"),
        ):
            if candidate_cap is None:
                continue
            try:
                contained = candidate_cap.resource(area_resref, restype)
                if contained:
                    return bytes(contained), _record(candidate_path, source_layer)
            except Exception:
                pass

        installation_error: Exception | None = None
        try:
            if installation is None:
                installation = Installation(rim.parent.parent)
            result = installation.resource(
                area_resref,
                restype,
                order=[SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN],
                module_root=module_name,
            )
            if result is not None and getattr(result, "data", None):
                source_path = Path(getattr(result, "filepath", "") or "")
                source_parts = {part.lower() for part in source_path.parts}
                if "override" in source_parts:
                    source_layer = "override"
                elif "modules" in source_parts:
                    source_layer = "module"
                elif source_path.suffix.lower() == ".bif":
                    source_layer = "chitin"
                else:
                    source_layer = "installation"
                return bytes(result.data), _record(source_path, source_layer)
        except Exception as exc:
            installation_error = exc

        # Recovered community releases frequently keep the real map payload
        # loose beside a tiny metadata-only MOD.  The caller indexes that
        # companion tree in ResourceManager; consult it only after the normal
        # installation lookup so stock-module provenance remains exact.
        if resource_provider is not None:
            try:
                getter = getattr(resource_provider, "get_strict", None)
                if not callable(getter):
                    getter = getattr(resource_provider, "get", None)
                if callable(getter):
                    supplied = getter(area_resref, int(restype.type_id), game_tag)
                    if supplied:
                        source_path = ""
                        source_getter = getattr(resource_provider, "overlay_source_path", None)
                        if callable(source_getter):
                            source_path = str(source_getter(area_resref, int(restype.type_id)) or "")
                        return bytes(supplied), _record(source_path, "module_companion")
            except Exception as exc:
                warnings.append(
                    f"Could not resolve {area_resref}.{restype.extension} from the module companion overlay: {exc}"
                )
        if installation_error is not None:
            warnings.append(f"Could not resolve {area_resref}.{restype.extension}: {installation_error}")
        return None, _record("", "unresolved")

    lyt_bytes, lyt_provenance = _resolve(RT.LYT)
    vis_bytes, vis_provenance = _resolve(RT.VIS)
    pth_bytes, pth_provenance = _resolve(RT.PTH)
    for restype, data in (("lyt", lyt_bytes), ("vis", vis_bytes), ("pth", pth_bytes)):
        if not data:
            warnings.append(f"No {game_tag} {restype.upper()} resource resolved for area {area_resref}.")
    return StockModuleAuxiliaryResources(
        area_resref=area_resref,
        lyt_bytes=lyt_bytes,
        vis_bytes=vis_bytes,
        pth_bytes=pth_bytes,
        provenance={
            "lyt": lyt_provenance,
            "vis": vis_provenance,
            "pth": pth_provenance,
        },
        warnings=tuple(warnings),
    )


def _gff_str(struct: Any, key: str, default: str = "") -> str:
    try:
        val = struct.acquire(key, default)
        if val is not None:
            # PyKotor GFF strings can be bytes or LocalizedString
            if hasattr(val, "get") and hasattr(val, "string_ref"):
                return str(val.string_ref or "")
            if isinstance(val, bytes):
                return val.decode("utf-8", errors="replace").rstrip("\x00")
            return str(val)
    except Exception:
        pass
    return default


def _gff_int(struct: Any, key: str, default: int = 0) -> int:
    try:
        val = struct.acquire(key, default)
        if val is not None:
            return int(val)
    except Exception:
        pass
    return default


def _gff_locstring_ref(struct: Any, key: str, default: int = 0) -> int:
    """Read the StringRef carried by a CExoLocString field."""

    try:
        value = struct.acquire(key, None)
    except Exception:
        value = None
    if value is None:
        return default
    for attribute in ("stringref", "string_ref"):
        try:
            return int(getattr(value, attribute))
        except (AttributeError, TypeError, ValueError):
            continue
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _gff_vector(struct: Any, key: str, count: int, default: tuple[float, ...]) -> tuple[float, ...]:
    """Read a PyKotor Vector3/Vector4 without assuming it is iterable."""

    try:
        value = struct.acquire(key, None)
    except Exception:
        value = None
    if value is None:
        return default
    names = ("x", "y", "z", "w")[:count]
    try:
        return tuple(float(getattr(value, name)) for name in names)
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        values = tuple(float(component) for component in tuple(value)[:count])
    except (TypeError, ValueError):
        return default
    return values if len(values) == count else default


def _bearing_from_orientation(x: float, y: float) -> float:
    """Convert KOTOR XY orientation to the engine's radian bearing."""

    return math.atan2(float(y), float(x))


# ── MDL → PrimitiveMesh ─────────────────────────────────────────────────


def mdl_node_to_primitive_mesh(
    node: Any,
    *,
    room_resref: str,
    mesh_role: str = "render",
    world_offset: Vec3 = (0.0, 0.0, 0.0),
) -> PrimitiveMesh | None:
    """Convert a single MDL mesh node into an editable PrimitiveMesh.

    Applies the room's world offset so vertices land in module world space.
    """

    vertices_raw = tuple(getattr(node, "vertices", ()) or ())
    faces_raw = tuple(getattr(node, "faces", ()) or ())
    if not vertices_raw or not faces_raw:
        return None

    ox, oy, oz = float(world_offset[0]), float(world_offset[1]), float(world_offset[2])
    vertices: list[Vec3] = []
    for vert in vertices_raw:
        try:
            vertices.append((float(vert[0]) + ox, float(vert[1]) + oy, float(vert[2]) + oz))
        except Exception:
            vertices.append((ox, oy, oz))

    faces = []
    for face in faces_raw:
        try:
            faces.append((int(face[0]), int(face[1]), int(face[2])))
        except Exception:
            continue
    if not faces:
        return None

    normals_raw = tuple(getattr(node, "normals", ()) or ())
    normals: list[Vec3] = []
    for norm in normals_raw:
        try:
            normals.append((float(norm[0]), float(norm[1]), float(norm[2])))
        except Exception:
            break
    if len(normals) != len(vertices):
        normals = []

    uvs_raw = tuple(getattr(node, "uvs", ()) or ())
    uvs: list[tuple[float, float]] = []
    for uv in uvs_raw:
        try:
            uvs.append((float(uv[0]), float(uv[1])))
        except Exception:
            break
    if len(uvs) != len(vertices):
        uvs = []

    texture = str(getattr(node, "texture", "") or "")
    diffuse = getattr(node, "diffuse", (0.8, 0.8, 0.8))
    ambient = getattr(node, "ambient", (0.35, 0.35, 0.35))

    return PrimitiveMesh(
        name=str(getattr(node, "name", "") or f"{room_resref}_{mesh_role}"),
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals) if normals else (),
        uvs=tuple(uvs) if uvs else (),
        texture=texture,
        diffuse=tuple(float(v) for v in tuple(diffuse)[:3]),
        ambient=tuple(float(v) for v in tuple(ambient)[:3]),
        metadata={
            "role": mesh_role,
            "source": "stock_mdl",
            "room_resref": room_resref,
        },
    )


def kotor_model_to_primitive_meshes(
    model: Any,
    *,
    room_resref: str,
    world_offset: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[PrimitiveMesh, ...]:
    """Convert a loaded KotorModel into editable PrimitiveMesh instances.

    Walks the model's node tree, collects all mesh nodes, and returns them
    as a tuple of PrimitiveMesh with world-offset applied vertices.  These
    are stored in the room spec metadata for viewport preview and editing.
    """

    root = getattr(model, "root_node", None)
    if root is None:
        return ()

    meshes: list[PrimitiveMesh] = []

    def _walk(node: Any) -> None:
        vertices = tuple(getattr(node, "vertices", ()) or ())
        if vertices:
            mesh = mdl_node_to_primitive_mesh(
                node,
                room_resref=room_resref,
                mesh_role=str(getattr(node, "name", "") or "render"),
                world_offset=world_offset,
            )
            if mesh is not None:
                meshes.append(mesh)
        for child in tuple(getattr(node, "children", ()) or ()):
            _walk(child)

    _walk(root)
    return tuple(meshes)


# ── GIT → AuthoredGameplayPlacement ─────────────────────────────────────


def git_gff_to_placement(git_root: Any) -> AuthoredGameplayPlacement:
    """Convert a GFF GIT root struct into authored placement instances."""

    creatures: list[AuthoredCreatureInstance] = []
    for entry in tuple(git_root.acquire("Creature List", []) or []):
        creatures.append(AuthoredCreatureInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
            bearing=_bearing_from_orientation(_gff_float(entry, "XOrientation", 1.0), _gff_float(entry, "YOrientation")),
        ))

    placeables: list[AuthoredPlaceableInstance] = []
    for entry in tuple(git_root.acquire("Placeable List", []) or []):
        placeables.append(AuthoredPlaceableInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            # Vanilla GIT placeables use the compact X/Y/Z/Bearing schema,
            # unlike creatures and waypoints.  Reading XPosition collapsed
            # every stock placeable to the origin.
            position=(
                _gff_float(entry, "X", _gff_float(entry, "XPosition")),
                _gff_float(entry, "Y", _gff_float(entry, "YPosition")),
                _gff_float(entry, "Z", _gff_float(entry, "ZPosition")),
            ),
            bearing=_gff_float(
                entry,
                "Bearing",
                _bearing_from_orientation(
                    _gff_float(entry, "XOrientation", 1.0),
                    _gff_float(entry, "YOrientation"),
                ),
            ),
            use_tweak_color=bool(_gff_int(entry, "UseTweakColor", 0)),
            tweak_color=_gff_int(entry, "TweakColor", 0) & 0xFFFFFFFF,
        ))

    doors: list[AuthoredDoorInstance] = []
    for entry in tuple(git_root.acquire("Door List", []) or []):
        doors.append(AuthoredDoorInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(
                _gff_float(entry, "X", _gff_float(entry, "XPosition")),
                _gff_float(entry, "Y", _gff_float(entry, "YPosition")),
                _gff_float(entry, "Z", _gff_float(entry, "ZPosition")),
            ),
            bearing=_gff_float(
                entry,
                "Bearing",
                _bearing_from_orientation(
                    _gff_float(entry, "XOrientation", 1.0),
                    _gff_float(entry, "YOrientation"),
                ),
            ),
            linked_to=_gff_str(entry, "LinkedTo"),
            linked_to_module=_gff_str(entry, "LinkedToModule"),
            linked_to_flags=_gff_int(entry, "LinkedToFlags", 0) & 0xFF,
            transition_destination=_gff_locstring_ref(
                entry,
                "TransitionDestin",
                _gff_int(entry, "TransitionDestination"),
            ),
            use_tweak_color=bool(_gff_int(entry, "UseTweakColor", 0)),
            tweak_color=_gff_int(entry, "TweakColor", 0) & 0xFFFFFFFF,
        ))

    triggers: list[AuthoredTriggerInstance] = []
    for entry in tuple(git_root.acquire("TriggerList", []) or []):
        geom: list[Vec3] = []
        for geo in tuple(entry.acquire("Geometry", []) or []):
            geom.append((_gff_float(geo, "PointX"), _gff_float(geo, "PointY"), _gff_float(geo, "PointZ")))
        triggers.append(AuthoredTriggerInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
            geometry=tuple(geom),
            linked_to=_gff_str(entry, "LinkedTo"),
            linked_to_module=_gff_str(entry, "LinkedToModule"),
            linked_to_flags=_gff_int(entry, "LinkedToFlags", 0) & 0xFF,
            transition_destination=_gff_locstring_ref(
                entry,
                "TransitionDestin",
                _gff_int(entry, "TransitionDestination"),
            ),
        ))

    waypoints: list[AuthoredWaypointInstance] = []
    for entry in tuple(git_root.acquire("WaypointList", []) or []):
        waypoints.append(AuthoredWaypointInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
            bearing=_bearing_from_orientation(_gff_float(entry, "XOrientation", 1.0), _gff_float(entry, "YOrientation")),
        ))

    encounters: list[AuthoredEncounterInstance] = []
    for entry in tuple(git_root.acquire("Encounter List", []) or []):
        encounters.append(AuthoredEncounterInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
        ))

    sounds: list[AuthoredSoundInstance] = []
    for entry in tuple(git_root.acquire("SoundList", []) or []):
        sounds.append(AuthoredSoundInstance(
            template_resref=normalise_resref(_gff_str(entry, "TemplateResRef")),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
        ))

    cameras: list[AuthoredCameraInstance] = []
    for entry in tuple(git_root.acquire("CameraList", []) or []):
        position = _gff_vector(
            entry,
            "Position",
            3,
            (
                _gff_float(entry, "XPosition"),
                _gff_float(entry, "YPosition"),
                _gff_float(entry, "ZPosition"),
            ),
        )
        orientation = _gff_vector(
            entry,
            "Orientation",
            4,
            (
                _gff_float(entry, "XOrientation"),
                _gff_float(entry, "YOrientation"),
                _gff_float(entry, "ZOrientation"),
                _gff_float(entry, "WOrientation", 1.0),
            ),
        )
        cameras.append(AuthoredCameraInstance(
            camera_id=_gff_int(entry, "CameraID"),
            position=(float(position[0]), float(position[1]), float(position[2])),
            orientation=(
                float(orientation[0]),
                float(orientation[1]),
                float(orientation[2]),
                float(orientation[3]),
            ),
            field_of_view=_gff_float(entry, "FieldOfView", 45.0),
            height=_gff_float(entry, "Height"),
            mic_range=_gff_float(entry, "MicRange"),
            pitch=_gff_float(entry, "Pitch"),
        ))

    stores: list[AuthoredStoreInstance] = []
    for entry in tuple(git_root.acquire("StoreList", []) or []):
        # KOTOR GIT stores name their template "ResRef", unlike every other
        # placement list ("TemplateResRef"); reading the wrong field dropped
        # the template and blocked round-trip export.
        stores.append(AuthoredStoreInstance(
            template_resref=normalise_resref(
                _gff_str(entry, "ResRef") or _gff_str(entry, "TemplateResRef")
            ),
            tag=_gff_str(entry, "Tag"),
            position=(_gff_float(entry, "XPosition"), _gff_float(entry, "YPosition"), _gff_float(entry, "ZPosition")),
            bearing=_bearing_from_orientation(
                _gff_float(entry, "YOrientation", 1.0),
                _gff_float(entry, "XOrientation"),
            ),
        ))

    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref=""),  # filled from IFO by caller
        creatures=tuple(creatures),
        doors=tuple(doors),
        triggers=tuple(triggers),
        encounters=tuple(encounters),
        sounds=tuple(sounds),
        cameras=tuple(cameras),
        stores=tuple(stores),
        placeables=tuple(placeables),
        waypoints=tuple(waypoints),
    )


# ── ARE → metadata ──────────────────────────────────────────────────────


def are_gff_to_metadata(are_root: Any, *, module_root: str, game: str) -> dict[str, Any]:
    """Extract lighting and area metadata from an ARE GFF root."""

    sun_ambient = _gff_int(are_root, "SunAmbientColor", 0x404040)
    sun_diffuse = _gff_int(are_root, "SunDiffuseColor", 0xFFFFFF)
    dynamic_ambient = _gff_int(are_root, "DynAmbientColor", sun_ambient)
    sun_fog_color = _gff_int(are_root, "SunFogColor", 0)
    sun_fog_near = _gff_float(are_root, "SunFogNear", 100.0)
    sun_fog_far = _gff_float(are_root, "SunFogFar", 200.0)
    fog_color = _gff_int(are_root, "FogColor", sun_fog_color)
    fog_near = _gff_float(are_root, "FogNearDist", sun_fog_near)
    fog_far = _gff_float(are_root, "FogFarDist", sun_fog_far)
    sun_shadows = _gff_int(are_root, "SunShadows")
    shadow_opacity = _gff_int(are_root, "ShadowOpacity", 128 if str(game).upper() == "K2" else 50)

    def _rgb(packed: int) -> list[int]:
        return [
            (int(packed) >> 16) & 0xFF,
            (int(packed) >> 8) & 0xFF,
            int(packed) & 0xFF,
        ]

    return {
        "sun_ambient_color": sun_ambient,
        "sun_diffuse_color": sun_diffuse,
        "dyn_ambient_color": dynamic_ambient,
        "sun_fog_on": _gff_int(are_root, "SunFogOn"),
        "sun_fog_color": sun_fog_color,
        "sun_fog_near": sun_fog_near,
        "sun_fog_far": sun_fog_far,
        "fog_color": fog_color,
        "fog_near": fog_near,
        "fog_far": fog_far,
        "sun_shadows": sun_shadows,
        "shadow_opacity": shadow_opacity,
        "are_tag": _gff_str(are_root, "Tag"),
        "ambient_id": _gff_int(are_root, "AmbientID"),
        "envaudio": _gff_int(are_root, "EnvAudio"),
        "module_root": module_root,
        "game": game,
        "lighting": {
            "profile": "standard",
            "source": "map_studio:stock_are",
            "sun_ambient": _rgb(sun_ambient),
            "sun_diffuse": _rgb(sun_diffuse),
            "dynamic_ambient": _rgb(dynamic_ambient),
            "shadow_opacity": shadow_opacity,
            "sun_shadows": sun_shadows,
        },
        "area": {
            "source": "map_studio:stock_are",
            "fog_color": _rgb(fog_color),
            "fog_near": fog_near,
            "fog_far": fog_far,
            "sun_fog_on": bool(_gff_int(are_root, "SunFogOn")),
        },
    }


# ── LYT room positions from RIM/BIF ─────────────────────────────────────


def lyt_room_positions_from_resource(
    lyt_data: bytes | None,
) -> dict[str, tuple[float, float, float]]:
    """Parse LYT binary bytes and return {room_name_lower: (x, y, z)}."""

    if not lyt_data:
        return {}
    try:
        from pykotor.resource.formats.lyt import read_lyt
        lyt = read_lyt(lyt_data)
        positions: dict[str, tuple[float, float, float]] = {}
        for room in getattr(lyt, "rooms", ()) or ():
            name = str(getattr(room, "model", getattr(room, "name", ""))).strip().lower()
            if name:
                position = getattr(room, "position", None)
                x = float(getattr(position, "x", getattr(room, "position_x", 0.0)) or 0.0)
                y = float(getattr(position, "y", getattr(room, "position_y", 0.0)) or 0.0)
                z = float(getattr(position, "z", getattr(room, "position_z", 0.0)) or 0.0)
                positions[name] = (x, y, z)
        return positions
    except Exception as exc:
        log.debug("LYT room-position parse failed: %s", exc)
        # Older MAX/KOTOR toolchains emitted harmless blank lines and mixed
        # tabs inside the room block.  Current PyKotor rejects some of those
        # files even though the retail text grammar and older tools accept the
        # room rows.  Recover only the narrow, declared room list; malformed
        # coordinates or a short list still fail closed.
        try:
            text = bytes(lyt_data).decode("latin-1", errors="replace")
            lines = [line.strip() for line in text.splitlines()]
            room_count = -1
            start = -1
            for index, line in enumerate(lines):
                parts = line.split()
                if len(parts) >= 2 and parts[0].lower() == "roomcount":
                    room_count = int(parts[1])
                    start = index + 1
                    break
            if room_count < 0 or start < 0:
                return {}
            positions: dict[str, tuple[float, float, float]] = {}
            for line in lines[start:]:
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts and parts[0].lower() in {
                    "trackcount", "obstaclecount", "doorhookcount", "donelayout"
                }:
                    break
                if len(parts) < 4:
                    return {}
                positions[parts[0].lower()] = (
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                )
                if len(positions) == room_count:
                    break
            if len(positions) != room_count:
                return {}
            log.info("Recovered %d room(s) from legacy ASCII LYT formatting.", room_count)
            return positions
        except Exception as fallback_exc:
            log.debug("Legacy ASCII LYT recovery failed: %s", fallback_exc)
            return {}


def vis_pairs_from_resource(vis_data: bytes | None, lyt_room_names: tuple[str, ...] = ()) -> tuple[tuple[str, str], ...]:
    """Parse VIS binary bytes and return visibility room pairs."""

    if not vis_data:
        return ()
    try:
        from pykotor.resource.formats.vis import read_vis
        vis = read_vis(vis_data)
        room_names = tuple(lyt_room_names or ())
        if not room_names and hasattr(vis, "all_rooms"):
            room_names = tuple(str(room).lower() for room in vis.all_rooms())
        return vis_pairs_from_lyt_and_vis(room_names, vis)
    except Exception as exc:
        log.debug("VIS pair parse failed: %s", exc)
        return vis_pairs_from_lyt_and_vis(lyt_room_names, None)


def lyt_room_positions_from_rim(
    rim_path: Path | str,
    lyt_resref: str,
) -> dict[str, tuple[float, float, float]]:
    """Read LYT room positions directly from a module RIM file."""

    rim = Path(rim_path)
    if not rim.exists():
        return {}
    try:
        from pykotor.extract.capsule import LazyCapsule
        from pykotor.resource.type import ResourceType as RT
        cap = LazyCapsule(rim)
        lyt_bytes = cap.resource(lyt_resref.lower(), RT.LYT)
        return lyt_room_positions_from_resource(lyt_bytes)
    except Exception as exc:
        log.debug("LYT from RIM failed for %s: %s", lyt_resref, exc)
        return {}


# ── VIS pairs ───────────────────────────────────────────────────────────


def vis_pairs_from_lyt_and_vis(
    lyt_room_names: tuple[str, ...],
    vis_data: Any | None,
) -> tuple[tuple[str, str], ...]:
    """Return (room_a, room_b) visibility pairs from a VIS object."""

    if vis_data is None:
        return ()
    pairs: list[tuple[str, str]] = []
    try:
        known_rooms = tuple(
            str(room).strip().lower()
            for room in (
                vis_data.all_rooms()
                if hasattr(vis_data, "all_rooms")
                else lyt_room_names
            )
            if str(room).strip()
        )
        for room_name in lyt_room_names:
            room_lower = str(room_name).strip().lower()
            for other in known_rooms:
                if other == room_lower:
                    continue
                visible = (
                    vis_data.get_visible(room_lower, other)
                    if hasattr(vis_data, "get_visible")
                    else other in tuple(getattr(vis_data, "_visibility", {}).get(room_lower, ()) or ())
                )
                if visible:
                    pairs.append((room_lower, other))
    except Exception as exc:
        log.debug("VIS pair extraction failed: %s", exc)
    return tuple(pairs)


# ── Main entry: import_stock_module ─────────────────────────────────────


def import_stock_module(
    *,
    module_resref: str,
    game: str,
    rim_path: Path | str,
    resource_provider: Any = None,
    model_loader: Any = None,
    lyt_room_positions: dict[str, Vec3] | None = None,
    vis_pairs: tuple[tuple[str, str], ...] | None = None,
    lyt_bytes: bytes | None = None,
    vis_bytes: bytes | None = None,
    pth_bytes: bytes | None = None,
    stock_resource_provenance: Mapping[str, Mapping[str, Any]] | None = None,
) -> StockModuleImportResult:
    """Import a complete stock KOTOR module into an editable AuthoredModuleProject.

    ``resource_provider`` must have a ``get(name, res_type, game) -> bytes | None``
    API (ResourceManager or PyKotor Installation).  ``model_loader`` must have a
    ``load(resref, game) -> KotorModel | None`` API.

    Returns a StockModuleImportResult with the populated project or errors.
    """

    warnings: list[str] = []
    errors: list[str] = []
    rim = Path(rim_path)
    if not rim.exists():
        return StockModuleImportResult(
            project=None, errors=(f"RIM not found: {rim}",),
            source_module=module_resref, source_game=game,
        )

    resolved_area_resref = ""
    resolved_provenance: dict[str, Mapping[str, Any]] = {}
    if lyt_bytes is None or vis_bytes is None or pth_bytes is None:
        auxiliary = resolve_stock_module_auxiliary_resources(
            module_resref=module_resref,
            game=game,
            rim_path=rim,
            resource_provider=resource_provider,
        )
        resolved_area_resref = auxiliary.area_resref
        warnings.extend(auxiliary.warnings)
        if lyt_bytes is None:
            lyt_bytes = auxiliary.lyt_bytes
        if vis_bytes is None:
            vis_bytes = auxiliary.vis_bytes
        if pth_bytes is None:
            pth_bytes = auxiliary.pth_bytes
        resolved_provenance.update(auxiliary.provenance)
    resolved_provenance.update(dict(stock_resource_provenance or {}))

    if lyt_room_positions is None:
        lyt_room_positions = lyt_room_positions_from_resource(lyt_bytes)
    if vis_pairs is None:
        vis_pairs = vis_pairs_from_resource(vis_bytes, tuple(lyt_room_positions or ()))

    # ── 1. Read ARE/GIT/IFO from RIM ────────────────────────────────────
    try:
        from pykotor.extract.capsule import LazyCapsule
        from pykotor.resource.formats.gff import read_gff
        from pykotor.resource.type import ResourceType as RT
    except Exception as exc:
        return StockModuleImportResult(
            project=None, errors=(f"PyKotor import failed: {exc}",),
            source_module=module_resref, source_game=game,
        )

    are_root = git_root = ifo_root = pth_root = None
    are_bytes: bytes | None = None
    git_bytes: bytes | None = None
    ifo_bytes: bytes | None = None
    are_resref = ""
    try:
        cap = LazyCapsule(rim)
        for res in cap:
            rt = res.restype()
            try:
                if rt == RT.ARE and are_root is None:
                    are_bytes = bytes(cap.resource(res.resname(), rt) or b"")
                    are_root = read_gff(are_bytes).root
                    are_resref = normalise_resref(res.resname())
                elif rt == RT.GIT and git_root is None:
                    git_bytes = bytes(cap.resource(res.resname(), rt) or b"")
                    git_root = read_gff(git_bytes).root
                elif rt == RT.IFO and ifo_root is None:
                    ifo_bytes = bytes(cap.resource(res.resname(), rt) or b"")
                    ifo_root = read_gff(ifo_bytes).root
            except Exception as exc:
                warnings.append(f"Failed to read {res.resname()}.{rt.extension} from RIM: {exc}")
    except Exception as exc:
        errors.append(f"Failed to open RIM {rim}: {exc}")
        return StockModuleImportResult(project=None, errors=tuple(errors), source_module=module_resref, source_game=game)

    if are_root is None:
        errors.append("ARE resource not found in module RIM.")
    if git_root is None:
        errors.append("GIT resource not found in module RIM.")
    if ifo_root is None:
        errors.append("IFO resource not found in module RIM.")
    if errors:
        return StockModuleImportResult(project=None, errors=tuple(errors), source_module=module_resref, source_game=game)

    if are_bytes and "are" not in resolved_provenance:
        resolved_provenance["are"] = {
            "resref": are_resref or resolved_area_resref or normalise_resref(module_resref),
            "game": str(game or "").upper(),
            "module_resref": normalise_resref(module_resref),
            "source_layer": "module",
            "source_archive": rim.name,
        }
    for restype, raw, resref in (
        ("git", git_bytes, are_resref or resolved_area_resref or normalise_resref(module_resref)),
        ("ifo", ifo_bytes, "module"),
    ):
        if raw and restype not in resolved_provenance:
            resolved_provenance[restype] = {
                "resref": resref,
                "game": str(game or "").upper(),
                "module_resref": normalise_resref(module_resref),
                "source_layer": "module",
                "source_archive": rim.name,
            }

    # ── 2. Extract IFO entry point ──────────────────────────────────────
    # The re-exported module names its ARE/GIT/LYT/VIS after the module root
    # (the filename you warp to), so the entry area must equal the module root
    # for the emitted module to be self-consistent. Custom modules routinely
    # differ here -- the file, the area resref, and the IFO Mod_Entry_Area can
    # all be different names (RNVcanyon: file rnvcanyon / area koq200; RNVcity:
    # file rnvcity / area koq201 / entry koq200 which doesn't even exist). We
    # keep the original spawn position/facing but normalise the entry AREA to
    # the module root so export produces a module you can warp to by filename.
    entry_area = _gff_str(ifo_root, "Mod_Entry_Area")
    normalised_entry_area = normalise_resref(entry_area)
    module_entry_area = normalise_resref(module_resref)
    if normalised_entry_area and normalised_entry_area != module_entry_area:
        warnings.append(
            f"IFO entry area {normalised_entry_area!r} normalised to module root "
            f"{module_entry_area!r} so the re-exported module is self-consistent."
        )
    entry_direction_x = _gff_float(ifo_root, "Mod_Entry_Dir_X", 1.0)
    entry_direction_y = _gff_float(ifo_root, "Mod_Entry_Dir_Y", 0.0)
    entry_facing = (
        0.0
        if abs(entry_direction_x) <= 1.0e-12 and abs(entry_direction_y) <= 1.0e-12
        else math.atan2(entry_direction_y, entry_direction_x)
    )
    entry_point = ModuleEntryPoint(
        area_resref=module_entry_area,
        position=(_gff_float(ifo_root, "Mod_Entry_X"), _gff_float(ifo_root, "Mod_Entry_Y"), _gff_float(ifo_root, "Mod_Entry_Z")),
        facing=entry_facing,
    )

    # ── 3. Extract ARE metadata ─────────────────────────────────────────
    are_meta = are_gff_to_metadata(are_root, module_root=module_resref, game=game)

    # ── 4. Extract GIT placements ───────────────────────────────────────
    placement = git_gff_to_placement(git_root)
    placement = AuthoredGameplayPlacement(
        entry_point=entry_point,
        creatures=placement.creatures,
        doors=placement.doors,
        triggers=placement.triggers,
        encounters=placement.encounters,
        sounds=placement.sounds,
        cameras=placement.cameras,
        stores=placement.stores,
        placeables=placement.placeables,
        waypoints=placement.waypoints,
        metadata={**placement.metadata, "source": "stock_module_import"},
    )
    placement_counts = {
        "creatures": len(placement.creatures),
        "placeables": len(placement.placeables),
        "doors": len(placement.doors),
        "triggers": len(placement.triggers),
        "waypoints": len(placement.waypoints),
        "sounds": len(placement.sounds),
        "encounters": len(placement.encounters),
        "cameras": len(placement.cameras),
        "stores": len(placement.stores),
    }

    # ── 5. Build room specs from ARE room names ─────────────────────────
    are_rooms = tuple(are_root.acquire("Rooms", []) or [])
    visibility: dict[str, set[str]] = {}
    for source, target in tuple(vis_pairs or ()):
        source_name = normalise_resref(source)
        target_name = normalise_resref(target)
        if source_name and target_name and source_name != target_name:
            visibility.setdefault(source_name, set()).add(target_name)
    room_specs: list[AuthoredRoomSpec] = []
    are_room_entries: dict[str, Any] = {}
    are_room_order: list[str] = []
    for room_entry in are_rooms:
        room_name = normalise_resref(_gff_str(room_entry, "RoomName"))
        if room_name and room_name != "null" and room_name not in are_room_entries:
            are_room_entries[room_name] = room_entry
            are_room_order.append(room_name)
    # LYT is the actual room-model layout. Vanilla modules may contain
    # visual/animated rooms there that are intentionally absent from ARE
    # Rooms (K2 151HAR's 151harS asteroid/traffic room is one example).
    room_order = list(lyt_room_positions or ())
    room_order.extend(name for name in are_room_order if name not in room_order)
    for room_name in room_order:
        room_entry = are_room_entries.get(room_name)
        original_room_name = _gff_str(room_entry, "RoomName") if room_entry is not None else room_name
        are_listed = room_entry is not None

        # Room position from LYT if available
        room_position = (0.0, 0.0, 0.0)
        if lyt_room_positions:
            pos = lyt_room_positions.get(room_name) or lyt_room_positions.get(original_room_name.lower())
            if pos is not None:
                room_position = (float(pos[0]), float(pos[1]), float(pos[2]))

        # Keep the first import pass metadata-only. The old path decoded every
        # room model here, discarded the meshes, then decoded every model a
        # second time during editable conversion. The controller now performs
        # one explicit conversion pass immediately after import.
        primitive = FloorPlanRoomPrimitive(
            room_resref=room_name,
            points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        )

        room_meta: dict[str, Any] = {
            "source": "stock_module_import",
            "original_room_name": original_room_name,
            "imported_mesh_count": 0,
            "model_resolution_deferred": model_loader is not None,
            "are_listed": are_listed,
            "lyt_listed": room_name in (lyt_room_positions or {}),
        }
        room_specs.append(AuthoredRoomSpec(
            room_resref=room_name,
            primitive=primitive,
            position=room_position,
            visible_rooms=tuple(sorted(visibility.get(room_name, set()))),
            metadata=room_meta,
        ))

    if not room_specs:
        warnings.append("No rooms found in the module LYT or ARE Rooms list.")
    elif len(room_specs) > len(are_room_entries):
        warnings.append(
            f"Preserved {len(room_specs) - len(are_room_entries)} LYT-only visual/animated room(s) absent from ARE Rooms."
        )

    # ── 6. Build the project ────────────────────────────────────────────
    metadata = AuthoredModuleMetadata(
        module_root=normalise_resref(module_resref),
        game=game.upper(),
        display_name=f"{module_resref} (imported)",
        tag=are_meta.get("are_tag", ""),
        description=f"Imported from stock module {module_resref} ({game})",
        capability_stage="imported",
        metadata={
            "are": are_meta,
            "lighting": dict(are_meta.get("lighting") or {}),
            "area": dict(are_meta.get("area") or {}),
            "source_rim": str(rim),
            "original_entry_area": entry_area,
        },
    )

    provenance_by_type = resolved_provenance

    def _source_resource_record(data: bytes | None, restype: str) -> dict[str, Any]:
        raw = bytes(data or b"")
        if not raw:
            return {}
        provenance = {
            str(key): value
            for key, value in dict(provenance_by_type.get(restype, {}) or {}).items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        return {
            **provenance,
            "restype": restype,
            "encoding": "base64",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data": base64.b64encode(raw).decode("ascii"),
        }

    stock_resources = {
        restype: record
        for restype, record in (
            ("lyt", _source_resource_record(lyt_bytes, "lyt")),
            ("vis", _source_resource_record(vis_bytes, "vis")),
            ("pth", _source_resource_record(pth_bytes, "pth")),
            ("are", _source_resource_record(are_bytes, "are")),
            ("git", _source_resource_record(git_bytes, "git")),
            ("ifo", _source_resource_record(ifo_bytes, "ifo")),
        )
        if record
    }

    project = AuthoredModuleProject(
        metadata=metadata,
        rooms=tuple(room_specs),
        placements=placement,
        lights=(),
        notes=tuple(warnings),
        extra={
            "imported_from": "stock_module",
            "import_source": str(rim),
            "import_game": game.upper(),
            "source_area_resref": resolved_area_resref or normalise_resref(entry_area),
            "source_are_room_resrefs": list(are_room_order),
            "vis_pairs": list(vis_pairs or ()),
            "stock_resources": stock_resources,
            "stock_pth_preserved": bool(stock_resources.get("pth")),
            "stock_git_preserved": bool(stock_resources.get("git")),
            "stock_ifo_preserved": bool(stock_resources.get("ifo")),
        },
    )

    return StockModuleImportResult(
        project=project,
        room_count=len(room_specs),
        placement_counts=placement_counts,
        warnings=tuple(warnings),
        errors=(),
        source_module=module_resref,
        source_game=game,
    )
