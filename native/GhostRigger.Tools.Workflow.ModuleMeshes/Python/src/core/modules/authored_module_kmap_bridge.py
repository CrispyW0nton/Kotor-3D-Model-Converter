"""Bridge KMAP project sections to authored Map Studio module readiness.

KMAP is the scene/project container.  The from-scratch module authoring contract
lives in ``AuthoredModuleProject``.  This bridge keeps the conversion headless
so Qt windows can display readiness without owning parsing or validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
from .authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_module_readiness import AuthoredModuleReadiness, build_authored_module_readiness
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_primitives import PrimitiveMaterial


@dataclass(frozen=True)
class AuthoredModuleKMapBridgeResult:
    """Authored module data found in a KMAP project, if any."""

    project: AuthoredModuleProject | None = None
    readiness: AuthoredModuleReadiness | None = None
    runtime_resources: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _vec2(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (_float(value[0], 0.0), _float(value[1], 0.0))
    return None


def _vec3(value: Any, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (_float(value[0], default[0]), _float(value[1], default[1]), _float(value[2], default[2]))
    return default


def _material(data: Any) -> PrimitiveMaterial:
    source = _dict(data)
    return PrimitiveMaterial(
        texture=str(source.get("texture") or "default"),
        diffuse=_vec3(source.get("diffuse"), (0.8, 0.8, 0.8)),
        ambient=_vec3(source.get("ambient"), (0.35, 0.35, 0.35)),
        metadata=_dict(source.get("metadata")),
    )


def _opening(data: Any) -> FloorPlanWallOpening:
    source = _dict(data)
    return FloorPlanWallOpening(
        name=str(source.get("name") or ""),
        edge_index=int(_float(source.get("edge_index"), 0.0)),
        center_fraction=_float(source.get("center_fraction"), 0.5),
        width=_float(source.get("width"), 1.5),
        height=_float(source.get("height"), 2.1),
        bottom=_float(source.get("bottom"), 0.0),
        metadata=_dict(source.get("metadata")),
    )


def _room_primitive(data: dict[str, Any], room_resref: str) -> RectangularRoomPrimitive | FloorPlanRoomPrimitive:
    primitive = _dict(data.get("primitive"))
    primitive_type = str(primitive.get("type") or primitive.get("primitive") or data.get("primitive_type") or "rectangular").lower()
    if primitive_type in {"floor_plan", "floorplan", "floor_plan_extrusion"}:
        points = tuple(point for point in (_vec2(item) for item in primitive.get("points", ()) or ()) if point is not None)
        return FloorPlanRoomPrimitive(
            room_resref=normalise_resref(primitive.get("room_resref") or room_resref),
            points=points,
            z=_float(primitive.get("z"), 0.0),
            wall_height=_float(primitive.get("wall_height"), 3.0),
            floor_surface_id=primitive.get("floor_surface_id", 4),
            material=_material(primitive.get("material")),
            include_walls=bool(primitive.get("include_walls", True)),
            openings=tuple(_opening(item) for item in primitive.get("openings", ()) or ()),
            metadata=_dict(primitive.get("metadata")),
        )
    return RectangularRoomPrimitive(
        room_resref=normalise_resref(primitive.get("room_resref") or room_resref),
        width=_float(primitive.get("width"), 10.0),
        depth=_float(primitive.get("depth"), 10.0),
        wall_height=_float(primitive.get("wall_height"), 3.0),
        floor_surface_id=primitive.get("floor_surface_id", 4),
        texture=str(primitive.get("texture") or "default"),
        include_doorway_marker=bool(primitive.get("include_doorway_marker", True)),
    )


def _placement(data: Any, module_root: str) -> AuthoredGameplayPlacement:
    source = _dict(data)
    entry = _dict(source.get("entry_point"))
    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(
            area_resref=normalise_resref(entry.get("area_resref") or module_root),
            position=_vec3(entry.get("position")),
            facing=_float(entry.get("facing"), 0.0),
        ),
        metadata=_dict(source.get("metadata")),
    )


def _runtime_resources(data: Any) -> tuple[tuple[str, str], ...]:
    keys: set[tuple[str, str]] = set()
    for item in data or ():
        if isinstance(item, str):
            stem, dot, ext = item.rpartition(".")
            if dot:
                keys.add((normalise_resref(stem), ext.strip().lower().lstrip(".")))
            continue
        source = _dict(item)
        resref = normalise_resref(source.get("resref") or source.get("name") or "")
        restype = str(source.get("restype") or source.get("type") or "").strip().lower().lstrip(".")
        if resref and restype:
            keys.add((resref, restype))
    return tuple(sorted(keys))


def authored_project_from_kmap_payload(payload: Any, *, fallback_name: str = "new_level", fallback_game: str = "K1") -> AuthoredModuleProject:
    """Convert a serializable KMAP ``authored_module`` section to core intent."""

    data = _dict(payload)
    module_root = normalise_resref(data.get("module_root") or data.get("resref") or fallback_name)
    rooms: list[AuthoredRoomSpec] = []
    for index, room_data in enumerate(data.get("rooms", ()) or ()):
        room_source = _dict(room_data)
        room_resref = normalise_resref(room_source.get("room_resref") or room_source.get("resref") or f"{module_root}_r{index + 1}")
        rooms.append(
            AuthoredRoomSpec(
                room_resref=room_resref,
                primitive=_room_primitive(room_source, room_resref),
                position=_vec3(room_source.get("position")),
                visible_rooms=tuple(normalise_resref(item) for item in room_source.get("visible_rooms", ()) or ()),
                metadata=_dict(room_source.get("metadata")),
            )
        )
    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root=module_root,
            game=str(data.get("game") or fallback_game or "K1").upper(),
            display_name=str(data.get("display_name") or fallback_name or module_root),
            tag=str(data.get("tag") or module_root),
            description=str(data.get("description") or ""),
            capability_stage=str(data.get("capability_stage") or "export_candidate"),
            metadata=_dict(data.get("metadata")),
        ),
        rooms=tuple(rooms),
        placements=_placement(data.get("placements"), module_root),
        notes=tuple(str(item) for item in data.get("notes", ()) or ()),
        extra=_dict(data.get("extra")),
    )


def build_kmap_authored_module_readiness(kmap_project: Any) -> AuthoredModuleKMapBridgeResult:
    """Return authored-module readiness for a KMAP project when present."""

    extra = _dict(getattr(kmap_project, "extra_sections", {}))
    metadata = _dict(getattr(kmap_project, "metadata", {}))
    payload = extra.get("authored_module") or metadata.get("authored_module")
    if payload is None:
        return AuthoredModuleKMapBridgeResult(
            warnings=("No authored Map Studio module section is stored in this KMAP yet.",),
            metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": False},
        )
    try:
        project = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(kmap_project, "name", "") or "new_level"),
            fallback_game=str(getattr(kmap_project, "game", "") or "K1"),
        )
    except Exception as exc:
        return AuthoredModuleKMapBridgeResult(
            blocking_messages=(f"Authored module section could not be parsed: {exc}",),
            metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": True},
        )
    resources = _runtime_resources(_dict(payload).get("runtime_resources"))
    readiness = build_authored_module_readiness(
        project,
        packaged_resources=resources,
        game_tested=bool(_dict(payload).get("game_tested", False)),
    )
    return AuthoredModuleKMapBridgeResult(
        project=project,
        readiness=readiness,
        runtime_resources=resources,
        metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": True},
    )


__all__ = [
    "AuthoredModuleKMapBridgeResult",
    "authored_project_from_kmap_payload",
    "build_kmap_authored_module_readiness",
]
