"""Read-only catalog of installed KOTOR creature (UTC) behavior templates.

The catalog indexes every effective UTC resref in a selected installation,
resolves user-facing names through dialog.tlk, and records the combat-facing
fields a Character Builder user needs to compare.  It never writes to the game
or embeds source UTC bytes in a human-readable project file.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


UTC_TEMPLATE_CATALOG_SCHEMA = "ghostrigger.installed_utc_template_catalog.v1"
UTC_SCRIPT_HOOK_FIELDS = (
    "ScriptHeartbeat",
    "ScriptOnNotice",
    "ScriptSpellAt",
    "ScriptAttacked",
    "ScriptDamaged",
    "ScriptDisturbed",
    "ScriptEndRound",
    "ScriptEndDialogu",
    "ScriptDialogue",
    "ScriptSpawn",
    "ScriptRested",
    "ScriptDeath",
    "ScriptUserDefine",
    "ScriptOnBlocked",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resource_bytes(resource: Any) -> bytes:
    value = resource.data() if callable(getattr(resource, "data", None)) else getattr(resource, "data", b"")
    if hasattr(value, "read"):
        value = value.read()
    return bytes(value or b"")


def _resource_name(resource: Any) -> str:
    value = resource.resname() if callable(getattr(resource, "resname", None)) else getattr(resource, "resname", "")
    return str(value or "").strip().lower()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _list_rows(root: Any, label: str) -> list[Any]:
    try:
        return list(root.acquire(label, []))
    except Exception:
        return []


@dataclass(frozen=True)
class UtcTemplateSummary:
    game: str
    resref: str
    display_name: str
    tag: str
    source: str
    sources: tuple[str, ...]
    sha256: str
    size: int
    appearance_type: int
    faction_id: int
    soundset: int
    challenge_rating: float
    perception_range: int
    walk_rate: int
    hit_points: int
    max_hit_points: int
    abilities: Mapping[str, int] = field(default_factory=dict)
    classes: tuple[Mapping[str, int], ...] = ()
    feats: tuple[int, ...] = ()
    skills: tuple[int, ...] = ()
    equipment: tuple[Mapping[str, Any], ...] = ()
    inventory: tuple[Mapping[str, Any], ...] = ()
    script_hooks: Mapping[str, str] = field(default_factory=dict)
    module_only_script_hooks: tuple[str, ...] = ()
    conversation: str = ""
    read_error: str = ""

    @property
    def search_text(self) -> str:
        return " ".join((self.display_name, self.resref, self.tag, self.source)).casefold()

    @property
    def is_global_template(self) -> bool:
        return any(value in {"override", "chitin"} for value in self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "resref": self.resref,
            "display_name": self.display_name,
            "tag": self.tag,
            "source": self.source,
            "sources": list(self.sources),
            "sha256": self.sha256,
            "size": self.size,
            "appearance_type": self.appearance_type,
            "faction_id": self.faction_id,
            "soundset": self.soundset,
            "challenge_rating": self.challenge_rating,
            "perception_range": self.perception_range,
            "walk_rate": self.walk_rate,
            "hit_points": self.hit_points,
            "max_hit_points": self.max_hit_points,
            "abilities": dict(self.abilities),
            "classes": [dict(value) for value in self.classes],
            "feats": list(self.feats),
            "skills": list(self.skills),
            "equipment": [dict(value) for value in self.equipment],
            "inventory": [dict(value) for value in self.inventory],
            "script_hooks": dict(self.script_hooks),
            "module_only_script_hooks": list(self.module_only_script_hooks),
            "conversation": self.conversation,
            "read_error": self.read_error,
            "global_template": self.is_global_template,
        }


class InstalledUtcTemplateCatalog:
    """Index and resolve installed UTC resources without mutating the game."""

    def __init__(
        self,
        game_directory: str | Path,
        *,
        game: str,
        installation_factory: Callable[[Path], Any] | None = None,
    ) -> None:
        self.game_directory = Path(game_directory).resolve()
        self.game = str(game or "K2").strip().upper()
        if self.game not in {"K1", "K2"}:
            raise ValueError("UTC template catalog game must be K1 or K2.")
        if installation_factory is None:
            from pykotor.extract.installation import Installation

            installation_factory = Installation
        self._installation = installation_factory(self.game_directory)
        self._entries: dict[str, UtcTemplateSummary] = {}
        self._template_bytes: dict[str, bytes] = {}
        self._resource_sources: dict[tuple[str, str], set[str]] = {}
        self._scanned = False
        self.errors: list[str] = []

    @property
    def entries(self) -> tuple[UtcTemplateSummary, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def _iter_resources(self) -> Iterable[tuple[str, Any]]:
        try:
            for resource in self._installation.override_resources():
                yield "override", resource
        except Exception as exc:
            self.errors.append(f"Override scan: {exc}")
        try:
            for module_name in self._installation.modules_list():
                try:
                    for resource in self._installation.module_resources(module_name):
                        yield f"module:{module_name}", resource
                except Exception as exc:
                    self.errors.append(f"{module_name}: {exc}")
        except Exception as exc:
            self.errors.append(f"Module scan: {exc}")
        try:
            for resource in self._installation.chitin_resources():
                yield "chitin", resource
        except Exception as exc:
            self.errors.append(f"Chitin scan: {exc}")

    def scan(
        self,
        progress: Callable[[str], None] | None = None,
    ) -> tuple[UtcTemplateSummary, ...]:
        from pykotor.resource.type import ResourceType

        utc_sources: dict[str, set[str]] = {}
        for source, resource in self._iter_resources():
            try:
                restype = resource.restype() if callable(getattr(resource, "restype", None)) else resource.restype
                resref = _resource_name(resource)
            except Exception:
                continue
            if not resref:
                continue
            extension = str(getattr(restype, "extension", "") or "").casefold()
            if restype == ResourceType.UTC or extension == "utc":
                utc_sources.setdefault(resref, set()).add(source)
            elif restype == ResourceType.NCS or extension == "ncs":
                self._resource_sources.setdefault((resref, "ncs"), set()).add(source)

        total = len(utc_sources)
        for index, resref in enumerate(sorted(utc_sources), 1):
            if progress and (index == 1 or index == total or index % 50 == 0):
                progress(f"Reading installed creature templates… {index:,} of {total:,}")
            try:
                data = self.read_template_bytes(resref)
                self._entries[resref] = self._summarize(resref, data, utc_sources[resref])
            except Exception as exc:
                sources = tuple(sorted(utc_sources[resref], key=self._source_sort_key))
                self._entries[resref] = UtcTemplateSummary(
                    game=self.game,
                    resref=resref,
                    display_name=resref,
                    tag="",
                    source=sources[0] if sources else "unknown",
                    sources=sources,
                    sha256="",
                    size=0,
                    appearance_type=-1,
                    faction_id=-1,
                    soundset=-1,
                    challenge_rating=0.0,
                    perception_range=-1,
                    walk_rate=-1,
                    hit_points=0,
                    max_hit_points=0,
                    read_error=str(exc),
                )
        self._scanned = True
        return self.entries

    @staticmethod
    def _source_sort_key(value: str) -> tuple[int, str]:
        lowered = str(value).casefold()
        if lowered == "override":
            return (0, lowered)
        if lowered.startswith("module:"):
            return (1, lowered)
        if lowered == "chitin":
            return (2, lowered)
        return (3, lowered)

    def read_template_bytes(self, resref: str) -> bytes:
        key = str(resref or "").strip().lower()
        if key in self._template_bytes:
            return self._template_bytes[key]
        from pykotor.extract.installation import SearchLocation
        from pykotor.resource.type import ResourceType

        result = self._installation.resource(
            key,
            ResourceType.UTC,
            order=[SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN],
        )
        if result is None:
            raise FileNotFoundError(f"Installed UTC template was not found: {key}.utc")
        data = _resource_bytes(result)
        if not data:
            raise ValueError(f"Installed UTC template is empty: {key}.utc")
        self._template_bytes[key] = data
        return data

    def get(self, resref: str) -> UtcTemplateSummary:
        key = str(resref or "").strip().lower()
        if key in self._entries:
            return self._entries[key]
        data = self.read_template_bytes(key)
        sources = self._find_sources_for_resref(key)
        summary = self._summarize(key, data, sources)
        self._entries[key] = summary
        return summary

    def _find_sources_for_resref(self, resref: str) -> set[str]:
        from pykotor.resource.type import ResourceType

        sources: set[str] = set()
        for source, resource in self._iter_resources():
            try:
                restype = resource.restype() if callable(getattr(resource, "restype", None)) else resource.restype
                extension = str(getattr(restype, "extension", "") or "").casefold()
                if _resource_name(resource) == resref and (restype == ResourceType.UTC or extension == "utc"):
                    sources.add(source)
            except Exception:
                continue
        return sources or {"installation"}

    def _display_name(self, value: Any, fallback: str) -> str:
        stringref = _safe_int(getattr(value, "stringref", -1), -1)
        if stringref >= 0:
            try:
                text = str(self._installation.talktable().string(stringref) or "").strip()
                if text:
                    return text
            except Exception:
                pass
        text = str(value or "").strip()
        return text if text and text != "-1" else fallback

    def _summarize(self, resref: str, data: bytes, sources: Iterable[str]) -> UtcTemplateSummary:
        from pykotor.common.language import LocalizedString
        from pykotor.common.misc import ResRef
        from pykotor.resource.formats.gff import read_gff

        root = read_gff(bytes(data)).root
        source_rows = tuple(sorted(set(sources), key=self._source_sort_key))
        hooks = {
            label: str(root.acquire(label, ResRef.from_blank()) or "").strip().lower()
            for label in UTC_SCRIPT_HOOK_FIELDS
        }
        module_only = []
        for label, script in hooks.items():
            if not script:
                continue
            script_sources = self._resource_sources.get((script, "ncs"), set())
            if script_sources and all(str(value).casefold().startswith("module:") for value in script_sources):
                module_only.append(label)
        classes = tuple({
            "class_id": _safe_int(row.acquire("Class", 0)),
            "level": _safe_int(row.acquire("ClassLevel", 0)),
        } for row in _list_rows(root, "ClassList"))
        feats = tuple(_safe_int(row.acquire("Feat", -1), -1) for row in _list_rows(root, "FeatList"))
        skills = tuple(_safe_int(row.acquire("Rank", 0)) for row in _list_rows(root, "SkillList"))
        equipment = tuple({
            "slot": _safe_int(getattr(row, "struct_id", 0)),
            "resref": str(row.acquire("EquippedRes", ResRef.from_blank()) or "").strip().lower(),
        } for row in _list_rows(root, "Equip_ItemList"))
        inventory = tuple({
            "resref": str(row.acquire("InventoryRes", ResRef.from_blank()) or "").strip().lower(),
            "droppable": bool(_safe_int(row.acquire("Dropable", 0))),
        } for row in _list_rows(root, "ItemList"))
        return UtcTemplateSummary(
            game=self.game,
            resref=resref,
            display_name=self._display_name(root.acquire("FirstName", LocalizedString.from_invalid()), resref),
            tag=str(root.acquire("Tag", resref) or resref),
            source=source_rows[0] if source_rows else "installation",
            sources=source_rows,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            appearance_type=_safe_int(root.acquire("Appearance_Type", -1), -1),
            faction_id=_safe_int(root.acquire("FactionID", -1), -1),
            soundset=_safe_int(root.acquire("SoundSetFile", -1), -1),
            challenge_rating=_safe_float(root.acquire("ChallengeRating", 0.0)),
            perception_range=_safe_int(root.acquire("PerceptionRange", -1), -1),
            walk_rate=_safe_int(root.acquire("WalkRate", -1), -1),
            hit_points=_safe_int(root.acquire("HitPoints", 0)),
            max_hit_points=_safe_int(root.acquire("MaxHitPoints", 0)),
            abilities={
                "strength": _safe_int(root.acquire("Str", 0)),
                "dexterity": _safe_int(root.acquire("Dex", 0)),
                "constitution": _safe_int(root.acquire("Con", 0)),
                "intelligence": _safe_int(root.acquire("Int", 0)),
                "wisdom": _safe_int(root.acquire("Wis", 0)),
                "charisma": _safe_int(root.acquire("Cha", 0)),
            },
            classes=classes,
            feats=tuple(value for value in feats if value >= 0),
            skills=skills,
            equipment=equipment,
            inventory=inventory,
            script_hooks=hooks,
            module_only_script_hooks=tuple(module_only),
            conversation=str(root.acquire("Conversation", ResRef.from_blank()) or "").strip().lower(),
        )

    def report(self) -> dict[str, Any]:
        entries = self.entries if self._scanned else self.scan()
        identity = hashlib.sha256(
            "\n".join(f"{row.resref}:{row.sha256}" for row in entries).encode("utf-8")
        ).hexdigest()
        return {
            "schema": UTC_TEMPLATE_CATALOG_SCHEMA,
            "game": self.game,
            "catalog_id": identity,
            "template_count": len(entries),
            "generated_at": _utc_now(),
            "read_only_source": True,
            "game_directory_embedded": False,
            "errors": list(self.errors),
            "templates": [row.to_dict() for row in entries],
        }

    def write_report(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(self.report(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        temporary = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
            ) as stream:
                temporary = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        return target


__all__ = [
    "InstalledUtcTemplateCatalog",
    "UTC_SCRIPT_HOOK_FIELDS",
    "UTC_TEMPLATE_CATALOG_SCHEMA",
    "UtcTemplateSummary",
]
