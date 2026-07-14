"""Read-only resource provider foundation for GhostRigger studios.

This module is the T2304 bridge between suite-level ResourceAddress values and
the older ad-hoc game/module/resource managers. It intentionally does not write
or parse resources; callers get bytes plus provenance and can decide which
format-specific service should decode them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Protocol

from src.core.project.resource_address import ResourceAddress


_RESTYPE_TO_EXT: dict[str, str] = {
    "MDL": "mdl",
    "MDX": "mdx",
    "TPC": "tpc",
    "TGA": "tga",
    "TXI": "txi",
    "UTC": "utc",
    "UTP": "utp",
    "UTD": "utd",
    "UTI": "uti",
    "UTT": "utt",
    "UTS": "uts",
    "UTE": "ute",
    "UTM": "utm",
    "ARE": "are",
    "GIT": "git",
    "IFO": "ifo",
    "DLG": "dlg",
    "NSS": "nss",
    "NCS": "ncs",
    "LYT": "lyt",
    "VIS": "vis",
    "PTH": "pth",
    "WOK": "wok",
    "2DA": "2da",
    "TLK": "tlk",
    "MOD": "mod",
    "RIM": "rim",
    "ERF": "erf",
}

_LAYER_PRIORITY = {
    "generated": 120,
    "project": 110,
    "override": 100,
    "module": 80,
    "texturepack": 60,
    "base": 40,
    "local": 30,
    "unknown": 0,
}


class GameResourceNotFoundError(FileNotFoundError):
    """Raised when a provider cannot resolve a requested resource."""


@dataclass(frozen=True)
class GameResourceQuery:
    """Normalized read-only resource lookup request."""

    resref: str | None = None
    restype: str | None = None
    game: str | None = None
    module_id: str | None = None
    layer: str | None = None
    path: str | None = None
    address: ResourceAddress | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "resref", _clean_text(self.resref))
        object.__setattr__(self, "restype", _clean_restype(self.restype))
        object.__setattr__(self, "game", _clean_game(self.game))
        object.__setattr__(self, "module_id", _clean_text(self.module_id, lower=True))
        object.__setattr__(self, "layer", _clean_text(self.layer, lower=True))
        object.__setattr__(self, "path", _clean_text(self.path))

    def to_address(self, *, scheme: str = "game_resource") -> ResourceAddress:
        return ResourceAddress(
            scheme=scheme,
            game=self.game,
            module_id=self.module_id,
            resref=self.resref,
            restype=self.restype,
            layer=self.layer,
            path=self.path,
        )


@dataclass(frozen=True)
class GameResourceRecord:
    """Resource metadata and provenance without loading raw bytes."""

    address: ResourceAddress
    size: int = 0
    source: str = ""
    source_path: str | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", ResourceAddress.from_dict(self.address))
        object.__setattr__(self, "size", int(self.size or 0))
        object.__setattr__(self, "source", str(self.source or ""))
        object.__setattr__(self, "source_path", _clean_text(self.source_path))
        object.__setattr__(self, "priority", int(self.priority or 0))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def resref(self) -> str | None:
        return self.address.resref

    @property
    def restype(self) -> str | None:
        return self.address.restype

    @property
    def layer(self) -> str | None:
        return self.address.layer

    @property
    def key(self) -> tuple[str | None, str | None, str | None, str | None]:
        return (
            self.address.game,
            self.address.module_id,
            (self.address.resref or "").lower(),
            self.address.restype,
        )


@dataclass
class GameResourceResult:
    """Resolved resource bytes plus provenance and shadowed candidates."""

    record: GameResourceRecord
    data: bytes = b""
    shadowed_records: list[GameResourceRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def address(self) -> ResourceAddress:
        return self.record.address


class GameResourceProvider(Protocol):
    """Read-only resource provider protocol shared by all studios."""

    def list_resources(self, query: GameResourceQuery | ResourceAddress | None = None) -> list[GameResourceRecord]:
        ...

    def resolve(
        self,
        query: GameResourceQuery | ResourceAddress,
    ) -> GameResourceResult:
        ...

    def read_bytes(self, query: GameResourceQuery | ResourceAddress) -> bytes:
        ...

    def exists(self, query: GameResourceQuery | ResourceAddress) -> bool:
        ...


def coerce_resource_query(value: GameResourceQuery | ResourceAddress | dict[str, Any]) -> GameResourceQuery:
    if isinstance(value, GameResourceQuery):
        return value
    if isinstance(value, ResourceAddress):
        return GameResourceQuery(
            resref=value.resref,
            restype=value.restype,
            game=value.game,
            module_id=value.module_id,
            layer=value.layer,
            path=value.path,
            address=value,
        )
    if isinstance(value, dict):
        return coerce_resource_query(ResourceAddress.from_dict(value) if value.get("scheme") else GameResourceQuery(**value))
    raise TypeError(f"Cannot coerce resource query from {type(value).__name__}.")


class InMemoryGameResourceProvider:
    """Simple provider for tests, project layers, and generated candidates."""

    def __init__(self, resources: Iterable[tuple[GameResourceRecord, bytes] | GameResourceResult] = ()) -> None:
        self._entries: list[GameResourceResult] = []
        for item in resources:
            if isinstance(item, GameResourceResult):
                self.add(item.record, item.data)
            else:
                record, data = item
                self.add(record, data)

    def add(self, record: GameResourceRecord, data: bytes = b"") -> None:
        self._entries.append(GameResourceResult(record=record, data=bytes(data or b"")))

    def list_resources(self, query: GameResourceQuery | ResourceAddress | None = None) -> list[GameResourceRecord]:
        q = coerce_resource_query(query) if query is not None else None
        records = [entry.record for entry in self._entries]
        return _sort_records([record for record in records if q is None or _record_matches(record, q)])

    def list_module_resources(self, module_root: str, *, game: str | None = None) -> list[GameResourceRecord]:
        return self.list_resources(GameResourceQuery(game=game, module_id=module_root))

    def resolve(self, query: GameResourceQuery | ResourceAddress) -> GameResourceResult:
        q = coerce_resource_query(query)
        matches = [entry for entry in self._entries if _record_matches(entry.record, q)]
        if not matches:
            raise GameResourceNotFoundError(_missing_message(q))
        matches.sort(key=lambda entry: (-entry.record.priority, entry.record.source, entry.record.address.stable_key()))
        selected = matches[0]
        shadowed = [entry.record for entry in matches[1:]]
        warnings = _shadow_warnings(selected.record, shadowed)
        return GameResourceResult(
            record=selected.record,
            data=selected.data,
            shadowed_records=shadowed,
            warnings=warnings,
        )

    def read_bytes(self, query: GameResourceQuery | ResourceAddress) -> bytes:
        return self.resolve(query).data

    def read_resource(
        self,
        resref: str,
        restype: str,
        *,
        module_root: str | None = None,
        game: str | None = None,
        **_kwargs,
    ) -> bytes:
        return self.read_bytes(GameResourceQuery(game=game, module_id=module_root, resref=resref, restype=restype))

    def exists(self, query: GameResourceQuery | ResourceAddress) -> bool:
        try:
            self.resolve(query)
            return True
        except GameResourceNotFoundError:
            return False


class LocalFileResourceProvider:
    """Resolve local-file ResourceAddress values without treating files as game assets."""

    def list_resources(self, query: GameResourceQuery | ResourceAddress | None = None) -> list[GameResourceRecord]:
        if query is None:
            return []
        q = coerce_resource_query(query)
        if not q.path:
            return []
        path = Path(q.path)
        if not path.exists() or not path.is_file():
            return []
        return [self._record_for_path(path, q)]

    def resolve(self, query: GameResourceQuery | ResourceAddress) -> GameResourceResult:
        q = coerce_resource_query(query)
        if not q.path:
            raise GameResourceNotFoundError("Local file resource requires a path.")
        path = Path(q.path)
        if not path.exists() or not path.is_file():
            raise GameResourceNotFoundError(f"Local file resource not found: {path}")
        data = path.read_bytes()
        return GameResourceResult(record=self._record_for_path(path, q, size=len(data)), data=data)

    def read_bytes(self, query: GameResourceQuery | ResourceAddress) -> bytes:
        return self.resolve(query).data

    def exists(self, query: GameResourceQuery | ResourceAddress) -> bool:
        try:
            q = coerce_resource_query(query)
        except Exception:
            return False
        return bool(q.path and Path(q.path).is_file())

    def _record_for_path(self, path: Path, query: GameResourceQuery, *, size: int | None = None) -> GameResourceRecord:
        restype = query.restype or _clean_restype(path.suffix.lstrip("."))
        address = ResourceAddress(
            scheme="local_file",
            game=query.game,
            resref=query.resref or path.stem,
            restype=restype,
            layer="local",
            path=str(path),
        )
        return GameResourceRecord(
            address=address,
            size=int(path.stat().st_size if size is None else size),
            source="local_file",
            source_path=str(path),
            priority=_LAYER_PRIORITY["local"],
        )


class CompositeGameResourceProvider:
    """Chain providers while preserving selected and shadowed provenance."""

    def __init__(self, providers: Iterable[GameResourceProvider]) -> None:
        self.providers = list(providers)

    def list_resources(self, query: GameResourceQuery | ResourceAddress | None = None) -> list[GameResourceRecord]:
        records: list[GameResourceRecord] = []
        for provider in self.providers:
            records.extend(provider.list_resources(query))
        return _dedupe_records(_sort_records(records))

    def list_module_resources(self, module_root: str, *, game: str | None = None) -> list[GameResourceRecord]:
        return self.list_resources(GameResourceQuery(game=game, module_id=module_root))

    def resolve(self, query: GameResourceQuery | ResourceAddress) -> GameResourceResult:
        q = coerce_resource_query(query)
        matches: list[GameResourceResult] = []
        for provider in self.providers:
            try:
                matches.append(provider.resolve(q))
            except GameResourceNotFoundError:
                continue
        if not matches:
            raise GameResourceNotFoundError(_missing_message(q))
        matches.sort(key=lambda result: (-result.record.priority, result.record.source, result.record.address.stable_key()))
        selected = matches[0]
        shadowed = [*selected.shadowed_records, *(result.record for result in matches[1:])]
        return GameResourceResult(
            record=selected.record,
            data=selected.data,
            shadowed_records=shadowed,
            warnings=[*selected.warnings, *_shadow_warnings(selected.record, shadowed)],
        )

    def read_bytes(self, query: GameResourceQuery | ResourceAddress) -> bytes:
        return self.resolve(query).data

    def read_resource(
        self,
        resref: str,
        restype: str,
        *,
        module_root: str | None = None,
        game: str | None = None,
        **_kwargs,
    ) -> bytes:
        return self.read_bytes(GameResourceQuery(game=game, module_id=module_root, resref=resref, restype=restype))

    def exists(self, query: GameResourceQuery | ResourceAddress) -> bool:
        return any(provider.exists(query) for provider in self.providers)


class ResourceManagerGameResourceProvider:
    """Adapter around the existing fast ResourceManager.

    This adapter is deliberately read-only and mostly uses the ResourceManager's
    public ``get``/``list_resrefs`` surface. Where available, it inspects the
    manager's indexed archive metadata to report provenance and shadowed layers.
    """

    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def list_resources(self, query: GameResourceQuery | ResourceAddress | None = None) -> list[GameResourceRecord]:
        q = coerce_resource_query(query) if query is not None else GameResourceQuery()
        records: list[GameResourceRecord] = []
        games = [_manager_game_name(q.game)] if q.game else ["K1", "K2"]
        for game in games:
            inst = _manager_install(self.manager, game)
            if inst is None:
                continue
            records.extend(_records_from_install(inst, game, q))
        return _dedupe_records(_sort_records(records))

    def list_module_resources(self, module_root: str, *, game: str | None = None) -> list[GameResourceRecord]:
        return self.list_resources(GameResourceQuery(game=game, module_id=module_root, layer="module"))

    def resolve(self, query: GameResourceQuery | ResourceAddress) -> GameResourceResult:
        q = coerce_resource_query(query)
        if not q.resref or not q.restype:
            raise GameResourceNotFoundError("Game resource lookup requires resref and restype.")
        restype_id = _resource_manager_type_id(q.restype)
        if restype_id is None:
            raise GameResourceNotFoundError(f"Unsupported resource type: {q.restype}")
        game = _manager_game_name(q.game)
        candidates = self.list_resources(q)
        getter = getattr(self.manager, "get_strict", None) if q.game else None
        read_manager = getter if callable(getter) else self.manager.get
        if not candidates:
            if q.module_id or q.layer or q.path:
                raise GameResourceNotFoundError(_missing_message(q))
            data = read_manager(q.resref, restype_id, game)
            if data is None:
                raise GameResourceNotFoundError(_missing_message(q))
            address = q.to_address(scheme="game_resource")
            candidates = [
                GameResourceRecord(
                    address=replace(address, layer=address.layer or "unknown"),
                    size=len(data),
                    source="resource_manager",
                    priority=_LAYER_PRIORITY["unknown"],
                )
            ]
        selected = candidates[0]
        inst = _manager_install(self.manager, game)
        data = _read_selected_install_record(inst, selected, q.resref, restype_id)
        if data is None:
            if q.module_id or q.layer or q.path:
                raise GameResourceNotFoundError(_missing_message(q))
            data = read_manager(q.resref, restype_id, game)
        if data is None:
            raise GameResourceNotFoundError(_missing_message(q))
        if selected.size == 0:
            selected = replace(selected, size=len(data))
        shadowed = candidates[1:]
        warnings = _shadow_warnings(selected, shadowed)
        return GameResourceResult(
            record=selected,
            data=bytes(data),
            shadowed_records=shadowed,
            warnings=warnings,
        )

    def read_bytes(self, query: GameResourceQuery | ResourceAddress) -> bytes:
        return self.resolve(query).data

    def read_resource(
        self,
        resref: str,
        restype: str,
        *,
        module_root: str | None = None,
        game: str | None = None,
        **_kwargs,
    ) -> bytes:
        return self.read_bytes(GameResourceQuery(game=game, module_id=module_root, resref=resref, restype=restype))

    def exists(self, query: GameResourceQuery | ResourceAddress) -> bool:
        try:
            self.resolve(query)
            return True
        except GameResourceNotFoundError:
            return False


def _read_selected_install_record(inst: Any, record: GameResourceRecord, resref: str, type_id: int) -> bytes | None:
    """Read the exact indexed provenance selected by a typed query.

    ``ResourceManager.get`` intentionally applies global Override/module/base
    priority. That is wrong when Map Studio selected a particular source-module
    template whose resref is duplicated elsewhere, so address-scoped reads use
    the indexed archive directly.
    """

    if inst is None:
        return None
    layer = str(record.address.layer or "").lower()
    source_path = str(record.source_path or record.address.path or "")
    if layer == "override" and source_path:
        try:
            return Path(source_path).read_bytes()
        except OSError:
            return None
    if layer in {"module", "texturepack"}:
        collection = getattr(inst, "_mod_erfs" if layer == "module" else "_tex_erfs", ()) or ()
        wanted = str(Path(source_path).resolve()).lower() if source_path else ""
        for archive in collection:
            archive_path = str(Path(str(getattr(archive, "path", "") or "")).resolve()).lower()
            if wanted and archive_path != wanted:
                continue
            data = archive.read(resref, type_id)
            if data is not None:
                return bytes(data)
        return None
    if layer == "base":
        reader = getattr(inst, "get_bif", None)
        if callable(reader):
            data = reader(resref, type_id)
            return bytes(data) if data is not None else None
    return None


def restype_to_extension(restype: str | None) -> str:
    rt = _clean_restype(restype)
    if not rt:
        return ""
    return _RESTYPE_TO_EXT.get(rt, rt.lower())


def _records_from_install(inst: Any, game: str, query: GameResourceQuery) -> list[GameResourceRecord]:
    restype_id = _resource_manager_type_id(query.restype) if query.restype else None
    records: list[GameResourceRecord] = []
    if restype_id is None and query.restype:
        return records
    type_ids = [restype_id] if restype_id is not None else _known_resource_type_ids()
    for type_id in type_ids:
        restype = _resource_manager_restype(type_id)
        if not restype:
            continue
        records.extend(_override_records(inst, game, restype, type_id, query))
        records.extend(_erf_records(getattr(inst, "_mod_erfs", []), game, "module", restype, type_id, query))
        if restype in {"TPC", "TGA", "TXI"}:
            records.extend(_erf_records(getattr(inst, "_tex_erfs", []), game, "texturepack", restype, type_id, query))
        records.extend(_bif_records(inst, game, restype, type_id, query))
    return records


def _override_records(inst: Any, game: str, restype: str, type_id: int, query: GameResourceQuery) -> list[GameResourceRecord]:
    out: list[GameResourceRecord] = []
    suffix = f":{type_id}"
    for key, path in dict(getattr(inst, "_override", {}) or {}).items():
        if not key.endswith(suffix):
            continue
        resref = key[: -len(suffix)]
        if query.resref and resref.lower() != query.resref.lower():
            continue
        out.append(
            _record(
                game=game,
                resref=resref,
                restype=restype,
                layer="override",
                source="override",
                source_path=str(path),
                priority=_LAYER_PRIORITY["override"],
                size=_safe_path_size(path),
            )
        )
    return out


def _erf_records(
    erfs: Iterable[Any],
    game: str,
    layer: str,
    restype: str,
    type_id: int,
    query: GameResourceQuery,
) -> list[GameResourceRecord]:
    out: list[GameResourceRecord] = []
    suffix = f":{type_id}"
    for erf in erfs or []:
        source_path = str(getattr(erf, "path", "") or "")
        module_id = Path(source_path).stem.lower() if layer == "module" and source_path else None
        if query.module_id and module_id and query.module_id.lower() not in {module_id, module_id.replace("_s", "")}:
            continue
        for key, slot in dict(getattr(erf, "_index", {}) or {}).items():
            if not key.endswith(suffix):
                continue
            resref = key[: -len(suffix)]
            if query.resref and resref.lower() != query.resref.lower():
                continue
            size = int(slot[1]) if isinstance(slot, tuple) and len(slot) > 1 else 0
            out.append(
                _record(
                    game=game,
                    module_id=module_id if layer == "module" else None,
                    resref=resref,
                    restype=restype,
                    layer=layer,
                    source=f"{layer}:{Path(source_path).name}" if source_path else layer,
                    source_path=source_path or None,
                    priority=_LAYER_PRIORITY[layer],
                    size=size,
                )
            )
    return out


def _bif_records(inst: Any, game: str, restype: str, type_id: int, query: GameResourceQuery) -> list[GameResourceRecord]:
    out: list[GameResourceRecord] = []
    suffix = f":{type_id}"
    for key, slot in dict(getattr(inst, "_key_map", {}) or {}).items():
        if not key.endswith(suffix):
            continue
        resref = key[: -len(suffix)]
        if query.resref and resref.lower() != query.resref.lower():
            continue
        bif_idx, var_idx = slot
        bif = dict(getattr(inst, "_bif_index", {}) or {}).get(bif_idx)
        source_path = str(getattr(bif, "path", "") or "")
        size = 0
        table = getattr(bif, "_table", None)
        if isinstance(table, dict) and var_idx in table:
            size = int(table[var_idx][1])
        out.append(
            _record(
                game=game,
                resref=resref,
                restype=restype,
                layer="base",
                source=f"chitin:{Path(source_path).name}" if source_path else "chitin",
                source_path=source_path or None,
                priority=_LAYER_PRIORITY["base"],
                size=size,
            )
        )
    return out


def _record(
    *,
    game: str | None = None,
    module_id: str | None = None,
    resref: str,
    restype: str,
    layer: str,
    source: str,
    source_path: str | None = None,
    priority: int,
    size: int = 0,
    metadata: dict[str, Any] | None = None,
) -> GameResourceRecord:
    scheme = "module_resource" if module_id else ("override_resource" if layer == "override" else "game_resource")
    return GameResourceRecord(
        address=ResourceAddress(
            scheme=scheme,
            game=_clean_game(game),
            module_id=module_id,
            resref=resref,
            restype=restype,
            layer=layer,
            path=source_path,
        ),
        size=size,
        source=source,
        source_path=source_path,
        priority=priority,
        metadata=dict(metadata or {}),
    )


def _record_matches(record: GameResourceRecord, query: GameResourceQuery) -> bool:
    addr = record.address
    if query.path and addr.path and Path(addr.path) != Path(query.path):
        return False
    if query.game and addr.game and addr.game.lower() != query.game.lower():
        return False
    if query.module_id and (addr.module_id or "").lower() != query.module_id.lower():
        return False
    if query.resref and (addr.resref or "").lower() != query.resref.lower():
        return False
    if query.restype and (addr.restype or "").upper() != query.restype.upper():
        return False
    if query.layer and (addr.layer or "").lower() != query.layer.lower():
        return False
    return True


def _sort_records(records: Iterable[GameResourceRecord]) -> list[GameResourceRecord]:
    return sorted(
        records,
        key=lambda record: (
            -(record.priority or 0),
            record.address.game or "",
            record.address.module_id or "",
            (record.address.resref or "").lower(),
            record.address.restype or "",
            record.source,
        ),
    )


def _dedupe_records(records: Iterable[GameResourceRecord]) -> list[GameResourceRecord]:
    seen: set[tuple[str, str]] = set()
    out: list[GameResourceRecord] = []
    for record in records:
        key = (record.address.stable_key(), record.source_path or record.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _shadow_warnings(selected: GameResourceRecord, shadowed: list[GameResourceRecord]) -> list[str]:
    if not shadowed:
        return []
    return [
        (
            f"{selected.address.display_name()} from layer '{selected.layer}' shadows "
            f"{len(shadowed)} lower-priority resource(s)."
        )
    ]


def _missing_message(query: GameResourceQuery) -> str:
    if query.path:
        return f"Resource not found at local path: {query.path}"
    return f"Resource not found: {query.resref or '?'}{'.' + query.restype.lower() if query.restype else ''}"


def _safe_path_size(path: str | Path | None) -> int:
    try:
        if not path:
            return 0
        return int(Path(path).stat().st_size)
    except OSError:
        return 0


def _clean_text(value: Any, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower() if lower else text


def _clean_restype(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if text.startswith("."):
        text = text[1:]
    return text.upper()


def _clean_game(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    raw = text.lower()
    if raw in {"1", "k1", "kotor", "kotor1"}:
        return "k1"
    if raw in {"2", "k2", "tsl", "kotor2"}:
        return "k2"
    return raw


def _manager_game_name(value: str | None) -> str:
    return "K2" if _clean_game(value) == "k2" else "K1"


def _manager_install(manager: Any, game: str) -> Any | None:
    if game == "K2":
        method = getattr(manager, "get_k2", None)
        return method() if callable(method) else getattr(manager, "_k2", None)
    method = getattr(manager, "get_k1", None)
    return method() if callable(method) else getattr(manager, "_k1", None)


def _resource_manager_type_id(restype: str | None) -> int | None:
    if not restype:
        return None
    try:
        from src.core.assets.resource_manager import EXT_TO_TYPE
    except Exception:
        EXT_TO_TYPE = {}
    return dict(EXT_TO_TYPE).get(restype_to_extension(restype))


def _resource_manager_restype(type_id: int) -> str | None:
    try:
        from src.core.assets.resource_manager import TYPE_TO_EXT
    except Exception:
        TYPE_TO_EXT = {}
    ext = dict(TYPE_TO_EXT).get(type_id)
    return _clean_restype(ext) if ext else None


def _known_resource_type_ids() -> list[int]:
    try:
        from src.core.assets.resource_manager import EXT_TO_TYPE
    except Exception:
        return []
    return sorted(set(dict(EXT_TO_TYPE).values()))
