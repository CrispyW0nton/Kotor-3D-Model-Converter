"""Headless authored module project contract for Map Studio.

This is the editable, Qt-free data shape that a future Map Studio UI should
own before compiling to Odyssey resources.  It deliberately stores primitive
room intent, module metadata, and gameplay placement intent instead of raw
MDL/MDX/WOK/GFF bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_module_objects import AuthoredGameplayPlacement
from .authored_room_geometry import RectangularRoomPrimitive


Vec3 = tuple[float, float, float]


def normalise_resref(value: Any) -> str:
    """Return a KOTOR-safe lowercase resref fragment."""

    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


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
    primitive: RectangularRoomPrimitive
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
    if not project.module_root:
        blocking.append("Authored module project requires a module resref.")
    if not project.rooms:
        blocking.append("Authored module project requires at least one room.")
    seen_rooms: set[str] = set()
    for room in project.rooms:
        resref = room.normalised_resref()
        if not resref:
            blocking.append("Authored room requires a room resref.")
        if resref in seen_rooms:
            blocking.append(f"Duplicate authored room resref: {resref}")
        seen_rooms.add(resref)
        if room.visible_rooms:
            missing = [normalise_resref(item) for item in room.visible_rooms if normalise_resref(item) not in seen_rooms]
            if missing:
                warnings.append(f"Room {resref} references visibility targets that may be defined later: {', '.join(missing)}")
    entry_area = normalise_resref(project.placements.entry_point.area_resref)
    if entry_area != project.module_root:
        blocking.append(f"Module entry area {entry_area or '(missing)'} does not match module root {project.module_root}.")
    return AuthoredModuleProjectValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


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
        visible_rooms=(normalise_resref(room_primitive.room_resref),),
        metadata={"primitive": "rectangular_room"},
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
    "create_single_room_project",
    "normalise_resref",
    "validate_authored_module_project",
]
