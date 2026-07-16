"""Indexed room catalog for modular Map Studio authoring.

The catalog enumerates rooms from every source a modder can pull geometry
from — installed game modules, exported ``.mod``/``.rim`` capsules, and
authored ``.kmap`` projects — into one labeled, searchable list. Each entry
carries the doorway connection points (KOTOR LYT door-hooks: a room, a door
name, a world position, and an orientation) so a later snapping pass can line
two rooms up entrance-to-entrance.

This module is pure data extraction: no Qt, no resource-manager mutation. The
"Add Room from Module" browser and the doorway-snapping tools build on top of
these entries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

Vec3 = tuple[float, float, float]
Vec4 = tuple[float, float, float, float]


@dataclass(frozen=True)
class RoomConnectionPoint:
    """One doorway hook on a room, in room-local coordinates.

    ``local_position`` is the hook position relative to the room's own origin
    (the source module's LYT position subtracted out), so it stays valid when
    the room is re-placed anywhere in a new module. ``orientation`` is the
    door's quaternion (x, y, z, w); the outward facing derives from it.
    """

    door: str
    local_position: Vec3
    orientation: Vec4 = (0.0, 0.0, 0.0, 1.0)

    @property
    def facing_radians(self) -> float:
        """Yaw of the door hook about +Z, from its quaternion."""
        import math

        x, y, z, w = self.orientation
        siny_cosp = 2.0 * ((w * z) + (x * y))
        cosy_cosp = 1.0 - 2.0 * ((y * y) + (z * z))
        return math.atan2(siny_cosp, cosy_cosp)


@dataclass(frozen=True)
class RoomCatalogEntry:
    """One catalog-listed room the modder can add to the current project."""

    source_kind: str  # "game_library" | "mod" | "kmap"
    source_path: str
    module_resref: str
    room_resref: str
    game: str
    label: str
    module_position: Vec3 = (0.0, 0.0, 0.0)
    connection_points: tuple[RoomConnectionPoint, ...] = ()
    area_name: str = ""

    @property
    def entry_id(self) -> str:
        """Stable id: source module plus room, namespaced by source kind."""
        return f"{self.source_kind}:{self.module_resref}:{self.room_resref}".lower()

    @property
    def connection_count(self) -> int:
        return len(self.connection_points)


@dataclass(frozen=True)
class RoomCatalogResult:
    """Catalog rows plus non-fatal notes about skipped or partial sources."""

    entries: tuple[RoomCatalogEntry, ...] = ()
    warnings: tuple[str, ...] = ()

    def sorted_entries(self) -> tuple[RoomCatalogEntry, ...]:
        """Deterministic order: module, then room, then source kind."""
        return tuple(
            sorted(self.entries, key=lambda e: (e.module_resref, e.room_resref, e.source_kind))
        )


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()


def _vec3(value: Any) -> Vec3:
    if value is None:
        return (0.0, 0.0, 0.0)
    x = float(getattr(value, "x", 0.0)) if hasattr(value, "x") else float(value[0])
    y = float(getattr(value, "y", 0.0)) if hasattr(value, "y") else float(value[1])
    z = float(getattr(value, "z", 0.0)) if hasattr(value, "z") else float(value[2])
    return (x, y, z)


def _vec4(value: Any) -> Vec4:
    if value is None:
        return (0.0, 0.0, 0.0, 1.0)
    if hasattr(value, "x"):
        return (float(value.x), float(value.y), float(value.z), float(getattr(value, "w", 1.0)))
    seq = tuple(float(v) for v in value)
    if len(seq) == 4:
        return seq  # type: ignore[return-value]
    return (0.0, 0.0, 0.0, 1.0)


def _door_hooks_by_room(lyt: Any) -> dict[str, list[RoomConnectionPoint]]:
    """Group LYT door hooks by their owning room, in room-local coordinates."""

    rooms = {
        _normalise_resref(getattr(room, "model", getattr(room, "name", ""))): _vec3(getattr(room, "position", None))
        for room in tuple(getattr(lyt, "rooms", ()) or ())
    }
    grouped: dict[str, list[RoomConnectionPoint]] = {}
    for hook in tuple(getattr(lyt, "doorhooks", ()) or ()):
        room_key = _normalise_resref(getattr(hook, "room", ""))
        if not room_key:
            continue
        origin = rooms.get(room_key, (0.0, 0.0, 0.0))
        world = _vec3(getattr(hook, "position", None))
        grouped.setdefault(room_key, []).append(
            RoomConnectionPoint(
                door=_normalise_resref(getattr(hook, "door", "")),
                local_position=(world[0] - origin[0], world[1] - origin[1], world[2] - origin[2]),
                orientation=_vec4(getattr(hook, "orientation", None)),
            )
        )
    return grouped


def _read_capsule_lyt(capsule_path: Path) -> tuple[Any, str] | None:
    """Return ``(lyt, lyt_resref)`` from a module capsule, or None."""

    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.lyt import read_lyt
    from pykotor.resource.type import ResourceType as RT

    capsule = LazyCapsule(str(capsule_path))
    lyt_resref = ""
    lyt_bytes = None
    for resource in capsule:
        if getattr(resource, "restype", None) == RT.LYT:
            lyt_resref = _normalise_resref(getattr(resource, "resname", getattr(resource, "resref", "")))
            lyt_bytes = capsule.resource(lyt_resref, RT.LYT)
            break
    if not lyt_bytes:
        # Fall back to the module resref as the LYT resref (the common case).
        lyt_resref = _normalise_resref(capsule_path.stem)
        try:
            lyt_bytes = capsule.resource(lyt_resref, RT.LYT)
        except Exception:
            lyt_bytes = None
    if not lyt_bytes:
        return None
    return read_lyt(bytes(lyt_bytes)), lyt_resref


def _area_name_from_capsule(capsule_path: Path, module_resref: str) -> str:
    """Best-effort human area name from the module ARE, or ''."""

    try:
        from pykotor.extract.capsule import LazyCapsule
        from pykotor.resource.formats.gff import read_gff
        from pykotor.resource.type import ResourceType as RT

        capsule = LazyCapsule(str(capsule_path))
        are_bytes = capsule.resource(module_resref, RT.ARE)
        if not are_bytes:
            return ""
        gff = read_gff(bytes(are_bytes))
        name_field = gff.root.acquire("Name", None)
        text = str(getattr(name_field, "stringref", "") or getattr(name_field, "get", lambda *_: "")() or "")
        return text if text and not text.isdigit() else ""
    except Exception:
        return ""


def _label_for(module_resref: str, room_resref: str, *, game: str, area_name: str, connections: int) -> str:
    base = f"{module_resref} / {room_resref}"
    parts = [base]
    if area_name:
        parts.append(f"— {area_name}")
    tags = [game] if game else []
    if connections:
        tags.append(f"{connections} door{'s' if connections != 1 else ''}")
    if tags:
        parts.append(f"({', '.join(tags)})")
    return " ".join(parts)


def build_room_catalog_from_capsule(
    capsule_path: str | Path,
    *,
    game: str = "",
    source_kind: str = "mod",
) -> RoomCatalogResult:
    """Enumerate every room in one ``.mod``/``.rim``/``.erf`` capsule."""

    path = Path(capsule_path)
    if not path.is_file():
        return RoomCatalogResult(warnings=(f"Module capsule not found: {path}",))
    try:
        parsed = _read_capsule_lyt(path)
    except Exception as exc:
        return RoomCatalogResult(warnings=(f"Could not read LYT from {path.name}: {exc}",))
    if parsed is None:
        return RoomCatalogResult(warnings=(f"No LYT/rooms found in {path.name}.",))
    lyt, lyt_resref = parsed
    module_resref = lyt_resref or _normalise_resref(path.stem)
    hooks = _door_hooks_by_room(lyt)
    area_name = _area_name_from_capsule(path, module_resref)
    entries: list[RoomCatalogEntry] = []
    for room in tuple(getattr(lyt, "rooms", ()) or ()):
        room_resref = _normalise_resref(getattr(room, "model", getattr(room, "name", "")))
        if not room_resref:
            continue
        connections = tuple(hooks.get(room_resref, ()))
        entries.append(
            RoomCatalogEntry(
                source_kind=source_kind,
                source_path=str(path),
                module_resref=module_resref,
                room_resref=room_resref,
                game=str(game or "").upper(),
                label=_label_for(module_resref, room_resref, game=str(game or "").upper(), area_name=area_name, connections=len(connections)),
                module_position=_vec3(getattr(room, "position", None)),
                connection_points=connections,
                area_name=area_name,
            )
        )
    if not entries:
        return RoomCatalogResult(warnings=(f"{path.name} declares no rooms.",))
    return RoomCatalogResult(entries=tuple(entries))


def build_room_catalog_from_kmap(kmap_path: str | Path) -> RoomCatalogResult:
    """Enumerate the authored rooms stored in a ``.kmap`` project file."""

    path = Path(kmap_path)
    if not path.is_file():
        return RoomCatalogResult(warnings=(f"KMAP not found: {path}",))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return RoomCatalogResult(warnings=(f"Could not parse {path.name}: {exc}",))
    authored = data.get("authored_module") or {}
    module_resref = _normalise_resref(authored.get("module_root") or data.get("project", {}).get("name") or path.stem)
    game = str(authored.get("game") or data.get("project", {}).get("game") or "").upper()
    entries: list[RoomCatalogEntry] = []
    for room in tuple(authored.get("rooms") or ()):
        primitive = room.get("primitive") or {}
        room_resref = _normalise_resref(
            primitive.get("room_resref") or room.get("room_resref") or (primitive.get("metadata") or {}).get("original_room_name")
        )
        if not room_resref:
            continue
        position = room.get("position") or (0.0, 0.0, 0.0)
        entries.append(
            RoomCatalogEntry(
                source_kind="kmap",
                source_path=str(path),
                module_resref=module_resref,
                room_resref=room_resref,
                game=game,
                label=_label_for(module_resref, room_resref, game=game, area_name="", connections=0),
                module_position=(float(position[0]), float(position[1]), float(position[2])),
                connection_points=(),
                area_name="",
            )
        )
    if not entries:
        return RoomCatalogResult(warnings=(f"{path.name} has no authored rooms.",))
    return RoomCatalogResult(entries=tuple(entries))


def scan_room_catalog_sources(
    *,
    module_dirs: Iterable[str | Path] = (),
    kmap_paths: Iterable[str | Path] = (),
    game: str = "",
    capsule_limit: int | None = None,
) -> RoomCatalogResult:
    """Aggregate a room catalog from module directories and loose KMAPs.

    ``module_dirs`` are scanned for ``*.mod``/``*.rim`` capsules (deduping the
    ``_s`` gameplay companions). This is deliberately dependency-light so it
    can index a game install's ``Modules`` folder or a folder of exported
    candidate modules the same way.
    """

    entries: list[RoomCatalogEntry] = []
    warnings: list[str] = []
    seen: set[str] = set()
    capsules: list[Path] = []
    for module_dir in module_dirs:
        directory = Path(module_dir)
        if not directory.is_dir():
            warnings.append(f"Module directory not found: {directory}")
            continue
        for pattern in ("*.mod", "*.rim", "*.erf"):
            for capsule in sorted(directory.glob(pattern)):
                if capsule.stem.lower().endswith("_s"):
                    continue  # gameplay-template companion, not a room source
                capsules.append(capsule)
    if capsule_limit is not None:
        capsules = capsules[: max(0, int(capsule_limit))]
    for capsule in capsules:
        result = build_room_catalog_from_capsule(capsule, game=game, source_kind="game_library")
        warnings.extend(result.warnings)
        for entry in result.entries:
            if entry.entry_id in seen:
                continue
            seen.add(entry.entry_id)
            entries.append(entry)
    for kmap_path in kmap_paths:
        result = build_room_catalog_from_kmap(kmap_path)
        warnings.extend(result.warnings)
        for entry in result.entries:
            if entry.entry_id in seen:
                continue
            seen.add(entry.entry_id)
            entries.append(entry)
    return RoomCatalogResult(entries=tuple(entries), warnings=tuple(warnings))


__all__ = [
    "RoomConnectionPoint",
    "RoomCatalogEntry",
    "RoomCatalogResult",
    "build_room_catalog_from_capsule",
    "build_room_catalog_from_kmap",
    "scan_room_catalog_sources",
]
