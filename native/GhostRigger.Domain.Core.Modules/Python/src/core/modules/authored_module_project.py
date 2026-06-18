"""Headless authored module project contract for Map Studio.

This is the editable, Qt-free data shape that a future Map Studio UI should
own before compiling to Odyssey resources.  It deliberately stores primitive
room intent, module metadata, and gameplay placement intent instead of raw
MDL/MDX/WOK/GFF bytes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Union

from .authored_module_objects import AuthoredGameplayPlacement, validate_authored_gameplay_placement
from .authored_room_composition import AuthoredRoomComposition, compile_authored_room_composition, create_rectangular_room_composition
from .authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry, validate_floor_plan_room_primitive
from .authored_room_geometry import AuthoredRoomGeometry, RectangularRoomPrimitive, build_rectangular_room_geometry


Vec3 = tuple[float, float, float]
RoomPrimitiveIntent = Union[RectangularRoomPrimitive, FloorPlanRoomPrimitive]
_RESREF_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def normalise_resref(value: Any) -> str:
    """Return a KOTOR-safe lowercase resref fragment."""

    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def authored_resref_blocking_issue(label: str, value: Any) -> str | None:
    """Return a validation issue for unsafe authored resrefs, if any."""

    raw = str(value or "").strip()
    if "." in raw:
        raw = raw.rsplit(".", 1)[0]
    if not raw:
        return f"{label} requires a resref."
    if len(raw) > 16:
        return f"{label} resref '{raw}' is {len(raw)} characters; KOTOR resrefs must be 16 characters or fewer."
    if not _RESREF_PATTERN.match(raw):
        return f"{label} resref '{raw}' may only contain letters, numbers, and underscores."
    return None


@dataclass(frozen=True)
class AuthoredModuleMetadata:
    """Module-level data that compiles into ARE/IFO/package metadata."""

    module_root: str
    game: str = "K1"
    display_name: str = "GhostRigger Dev Test"
    tag: str = ""
    description: str = ""
    capability_stage: str = "export_candidate"
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalised_root(self) -> str:
        return normalise_resref(self.module_root)


@dataclass(frozen=True)
class AuthoredRoomSpec:
    """One authored room source in a Map Studio project."""

    room_resref: str
    primitive: RoomPrimitiveIntent
    composition: AuthoredRoomComposition | None = None
    position: Vec3 = (0.0, 0.0, 0.0)
    visible_rooms: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalised_resref(self) -> str:
        return normalise_resref(self.room_resref)


@dataclass(frozen=True)
class AuthoredModuleProject:
    """Editable from-scratch module project prior to binary compilation."""

    metadata: AuthoredModuleMetadata
    rooms: tuple[AuthoredRoomSpec, ...]
    placements: AuthoredGameplayPlacement
    notes: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def module_root(self) -> str:
        return self.metadata.normalised_root()

    @property
    def game(self) -> str:
        return str(self.metadata.game or "K1").upper()


@dataclass(frozen=True)
class AuthoredModuleProjectValidation:
    """Validation summary for authored Map Studio projects."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def validate_authored_module_project(project: AuthoredModuleProject) -> AuthoredModuleProjectValidation:
    """Validate the authored project before compiling bytes."""

    warnings: list[str] = []
    blocking: list[str] = []
    module_issue = authored_resref_blocking_issue("Authored module", project.metadata.module_root)
    if module_issue:
        blocking.append(module_issue)
    if not project.rooms:
        blocking.append("Authored module project requires at least one room.")
    seen_rooms: set[str] = set()
    for room in project.rooms:
        room_issue = authored_resref_blocking_issue("Authored room", room.room_resref)
        if room_issue:
            blocking.append(room_issue)
        resref = room.normalised_resref()
        if not resref:
            blocking.append("Authored room requires a room resref.")
        if resref in seen_rooms:
            blocking.append(f"Duplicate authored room resref: {resref}")
        seen_rooms.add(resref)
        if isinstance(room.primitive, FloorPlanRoomPrimitive):
            floorplan_validation = validate_floor_plan_room_primitive(room.primitive)
            warnings.extend(floorplan_validation.warnings)
            blocking.extend(floorplan_validation.blocking_issues)
        elif isinstance(room.primitive, RectangularRoomPrimitive):
            if float(room.primitive.width) <= 0.0 or float(room.primitive.depth) <= 0.0:
                blocking.append(f"Room {resref} rectangular primitive requires positive width and depth.")
            if float(room.primitive.wall_height) <= 0.0:
                blocking.append(f"Room {resref} rectangular primitive requires positive wall height.")
        else:
            blocking.append(f"Room {resref} has unsupported authored primitive type: {type(room.primitive)!r}")
        if room.visible_rooms:
            missing = [normalise_resref(item) for item in room.visible_rooms if normalise_resref(item) not in seen_rooms]
            if missing:
                warnings.append(f"Room {resref} references visibility targets that may be defined later: {', '.join(missing)}")
    entry_area = normalise_resref(project.placements.entry_point.area_resref)
    entry_issue = authored_resref_blocking_issue("Module entry area", project.placements.entry_point.area_resref)
    if entry_issue:
        blocking.append(entry_issue)
    if entry_area != project.module_root:
        blocking.append(f"Module entry area {entry_area or '(missing)'} does not match module root {project.module_root}.")
    placement_validation = validate_authored_gameplay_placement(project.placements)
    warnings.extend(placement_validation.warnings)
    blocking.extend(placement_validation.blocking_issues)
    return AuthoredModuleProjectValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def compile_authored_room_spec(room: AuthoredRoomSpec) -> AuthoredRoomGeometry:
    """Compile one authored room spec into room geometry and WOK data."""

    if room.composition is not None:
        return compile_authored_room_composition(room.composition)
    if isinstance(room.primitive, FloorPlanRoomPrimitive):
        return compile_floor_plan_room_geometry(room.primitive)
    if isinstance(room.primitive, RectangularRoomPrimitive):
        return build_rectangular_room_geometry(room.primitive)
    raise TypeError(f"Unsupported authored room primitive: {type(room.primitive)!r}")


def create_single_room_project(
    *,
    module_root: str,
    game: str,
    display_name: str,
    room_primitive: RectangularRoomPrimitive,
    placements: AuthoredGameplayPlacement,
    notes: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> AuthoredModuleProject:
    """Create the first useful from-scratch Map Studio project shape."""

    root = normalise_resref(module_root)
    room = AuthoredRoomSpec(
        room_resref=normalise_resref(room_primitive.room_resref),
        primitive=room_primitive,
        composition=create_rectangular_room_composition(room_primitive),
        visible_rooms=(normalise_resref(room_primitive.room_resref),),
        metadata={"primitive": "rectangular_room", "composition": "authored_room_composition"},
    )
    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root=root,
            game=str(game or "K1").upper(),
            display_name=display_name,
            tag=root,
            metadata=dict(metadata or {}),
        ),
        rooms=(room,),
        placements=placements,
        notes=notes,
    )


def create_floor_plan_room_project(
    *,
    module_root: str,
    game: str,
    display_name: str,
    floor_plan: FloorPlanRoomPrimitive,
    placements: AuthoredGameplayPlacement,
    notes: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> AuthoredModuleProject:
    """Create a single-room project from an editable floor-plan extrusion."""

    root = normalise_resref(module_root)
    room_resref = normalise_resref(floor_plan.room_resref)
    room = AuthoredRoomSpec(
        room_resref=room_resref,
        primitive=floor_plan,
        visible_rooms=(room_resref,),
        metadata={
            "primitive": "floor_plan_extrusion",
            "source": "src.core.modules.authored_module_project",
        },
    )
    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root=root,
            game=str(game or "K1").upper(),
            display_name=display_name,
            tag=root,
            metadata=dict(metadata or {}),
        ),
        rooms=(room,),
        placements=placements,
        notes=notes,
    )


__all__ = [
    "AuthoredModuleMetadata",
    "AuthoredModuleProject",
    "AuthoredModuleProjectValidation",
    "AuthoredRoomSpec",
    "RoomPrimitiveIntent",
    "authored_resref_blocking_issue",
    "compile_authored_room_spec",
    "create_floor_plan_room_project",
    "create_single_room_project",
    "normalise_resref",
    "validate_authored_module_project",
]
