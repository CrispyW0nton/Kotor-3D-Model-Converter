"""Module Editor hydration service.

M15 starts with a headless bridge between KotOR module archives and the
existing ``module_format`` / ``module_loader`` types.  A real module is not a
single file in practice: the base ``.rim`` usually carries ARE/GIT/IFO, the
``_s.rim`` carries templates/dialogs, and a ``.mod`` can override either.
This service normalizes that inventory into a typed, editor-friendly result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


CORE_TYPES = {"are", "git", "ifo"}
LAYOUT_TYPES = {"lyt", "vis", "pth", "wok"}
TEMPLATE_TYPES = {"utc", "utd", "utp", "uti", "utt", "uts", "ute", "utm", "utw"}
SCRIPT_TYPES = {"ncs", "nss"}
DIALOG_TYPES = {"dlg"}


def _import_module_format():  # pragma: no cover - import shim
    try:
        from src.core.modules import module_format as _mf  # type: ignore
    except ImportError:
        from core.modules import module_format as _mf  # type: ignore
    return _mf


def _import_module_loader():  # pragma: no cover - import shim
    try:
        from src.core.modules import module_loader as _ml  # type: ignore
    except ImportError:
        from core.modules import module_loader as _ml  # type: ignore
    return _ml


@dataclass(frozen=True)
class ModuleResourceRecord:
    """One resource discovered in a module archive layer."""

    resref: str
    restype: str
    size: int = 0
    source: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.resref.lower(), self.restype.lower().lstrip("."))


@dataclass
class HydratedModuleResource:
    """Selected resource plus optional bytes and parsed object."""

    record: ModuleResourceRecord
    data: bytes = b""
    parsed: Any = None
    code: str = "listed"
    message: str = ""


@dataclass(frozen=True)
class ModuleHydrationRequest:
    """Input contract for hydrating a KotOR module."""

    module_root: str
    game: str = "K1"
    include_templates: bool = True
    include_scripts: bool = True
    include_dialogs: bool = True
    include_layout: bool = True


@dataclass
class ModuleHydrationResult:
    """Typed Module Editor scene payload."""

    ok: bool = False
    module_root: str = ""
    game: str = "K1"
    module: Any = None
    scene_result: Any = None
    resources: dict[tuple[str, str], HydratedModuleResource] = field(default_factory=dict)
    templates: dict[str, list[HydratedModuleResource]] = field(default_factory=dict)
    scripts: list[HydratedModuleResource] = field(default_factory=list)
    dialogs: list[HydratedModuleResource] = field(default_factory=list)
    layout: dict[str, HydratedModuleResource] = field(default_factory=dict)
    object_counts: dict[str, int] = field(default_factory=dict)
    archive_layers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_loaded"


def _record_from_any(item: Any) -> ModuleResourceRecord:
    if isinstance(item, ModuleResourceRecord):
        return item
    if isinstance(item, dict):
        return ModuleResourceRecord(
            resref=str(item.get("resref", "") or ""),
            restype=str(item.get("restype", item.get("type", item.get("extension", ""))) or ""),
            size=int(item.get("size", item.get("size_bytes", 0)) or 0),
            source=str(item.get("source", "") or ""),
        )
    return ModuleResourceRecord(
        resref=str(getattr(item, "resref", "") or ""),
        restype=str(getattr(item, "restype", getattr(item, "type", getattr(item, "extension", ""))) or ""),
        size=int(getattr(item, "size", getattr(item, "size_bytes", 0)) or 0),
        source=str(getattr(item, "source", "") or ""),
    )


def _normalise_records(records: Iterable[Any]) -> list[ModuleResourceRecord]:
    out: list[ModuleResourceRecord] = []
    for item in records:
        record = _record_from_any(item)
        if record.resref and record.restype:
            out.append(
                ModuleResourceRecord(
                    resref=record.resref.lower(),
                    restype=record.restype.lower().lstrip("."),
                    size=record.size,
                    source=record.source,
                )
            )
    return out


def _archive_priority(source: str) -> tuple[int, str]:
    lower = source.lower()
    if lower.endswith(".mod") or ".mod" in lower:
        return (30, lower)
    if lower.endswith("_s.rim") or "_s.rim" in lower:
        return (20, lower)
    if lower.endswith(".rim") or ".rim" in lower:
        return (10, lower)
    return (0, lower)


def _select_highest_priority(records: Iterable[ModuleResourceRecord]) -> dict[tuple[str, str], ModuleResourceRecord]:
    selected: dict[tuple[str, str], ModuleResourceRecord] = {}
    for record in records:
        current = selected.get(record.key)
        if current is None or _archive_priority(record.source) >= _archive_priority(current.source):
            selected[record.key] = record
    return selected


def _provider_records(provider: Any, request: ModuleHydrationRequest) -> list[ModuleResourceRecord]:
    if provider is None:
        return []
    for name in ("list_module_resources", "list_resources", "resources_for_module"):
        method = getattr(provider, name, None)
        if callable(method):
            try:
                return _normalise_records(method(request.module_root, game=request.game))
            except TypeError:
                return _normalise_records(method(request.module_root))
    records = getattr(provider, "resources", None)
    if records is not None:
        return _normalise_records(records)
    if callable(provider):
        return _normalise_records(provider(request.module_root, request.game))
    return []


def _provider_read(provider: Any, record: ModuleResourceRecord, request: ModuleHydrationRequest) -> bytes:
    if provider is None:
        return b""
    for name in ("read_resource", "get_resource_bytes", "resource_bytes"):
        method = getattr(provider, name, None)
        if callable(method):
            try:
                data = method(record.resref, record.restype, module_root=request.module_root, source=record.source, game=request.game)
            except TypeError:
                try:
                    data = method(record.resref, record.restype)
                except TypeError:
                    data = method(record)
            return bytes(data or b"")
    data_map = getattr(provider, "data", None)
    if isinstance(data_map, dict):
        return bytes(data_map.get(record.key, b"") or b"")
    return b""


def _decode_text(data: bytes) -> str:
    return data.decode("latin-1", errors="replace")


def _find_first(resources: dict[tuple[str, str], HydratedModuleResource], restype: str) -> Optional[HydratedModuleResource]:
    matches = [resource for key, resource in resources.items() if key[1] == restype]
    if not matches:
        return None
    return sorted(matches, key=lambda r: (_archive_priority(r.record.source), r.record.resref), reverse=True)[0]


def _safe_parse(resource: HydratedModuleResource, parser: Any, warnings: list[str]) -> Any:
    if not resource.data:
        resource.code = "listed"
        resource.message = "Resource bytes were not available from the provider."
        return None
    try:
        parsed = parser(resource.data)
    except Exception as exc:
        resource.code = "parse_failed"
        resource.message = str(exc)
        warnings.append(f"{resource.record.resref}.{resource.record.restype} parse failed: {exc}")
        return None
    resource.parsed = parsed
    resource.code = "parsed"
    return parsed


def _list_count(raw: Any, key: str) -> int:
    if isinstance(raw, dict):
        value = raw.get(key) or raw.get(key.replace(" ", "")) or raw.get(key.lower())
        if isinstance(value, list):
            return len(value)
    return 0


def _git_object_counts(git: Any) -> dict[str, int]:
    raw = getattr(git, "_raw", None) or {}
    return {
        "creatures": len(getattr(git, "creatures", []) or []) or _list_count(raw, "Creature List"),
        "doors": len(getattr(git, "doors", []) or []) or _list_count(raw, "Door List"),
        "placeables": len(getattr(git, "placeables", []) or []) or _list_count(raw, "Placeable List"),
        "waypoints": len(getattr(git, "waypoints", []) or []) or _list_count(raw, "WaypointList"),
        "triggers": len(getattr(git, "triggers", []) or []) or _list_count(raw, "TriggerList"),
        "encounters": _list_count(raw, "Encounter List"),
        "sounds": _list_count(raw, "SoundList"),
        "stores": _list_count(raw, "StoreList"),
    }


def hydrate_module(
    request: ModuleHydrationRequest,
    *,
    provider: Any,
    model_library: Any = None,
) -> ModuleHydrationResult:
    """Hydrate a module inventory into a typed Module Editor scene."""

    mf = _import_module_format()
    ml = _import_module_loader()
    warnings: list[str] = []
    listed = _provider_records(provider, request)
    if not listed:
        return ModuleHydrationResult(
            module_root=request.module_root,
            game=request.game,
            warnings=["No module resources were returned by the provider."],
            message=f"No resources found for module '{request.module_root}'.",
            code="no_resources",
        )

    selected_records = _select_highest_priority(listed)
    resources: dict[tuple[str, str], HydratedModuleResource] = {}
    for key, record in selected_records.items():
        resources[key] = HydratedModuleResource(
            record=record,
            data=_provider_read(provider, record, request),
        )

    module = mf.KotorModule(name=request.module_root, game=request.game)
    module.resources = {
        f"{record.resref}.{record.restype}": hydrated.data
        for record, hydrated in ((r.record, r) for r in resources.values())
        if hydrated.data
    }

    are_res = _find_first(resources, "are")
    git_res = _find_first(resources, "git")
    ifo_res = _find_first(resources, "ifo")
    if are_res is not None:
        module.are = _safe_parse(are_res, mf.AREData.from_bytes, warnings)
    if git_res is not None:
        module.git = _safe_parse(git_res, mf.GITData.from_bytes, warnings)
    if ifo_res is not None:
        module.ifo = _safe_parse(ifo_res, mf.IFOData.from_bytes, warnings)

    layout: dict[str, HydratedModuleResource] = {}
    if request.include_layout:
        lyt_res = _find_first(resources, "lyt")
        vis_res = _find_first(resources, "vis")
        if lyt_res is not None and lyt_res.data:
            try:
                module.lyt = mf.LYTLayout.from_text(_decode_text(lyt_res.data))
                lyt_res.parsed = module.lyt
                lyt_res.code = "parsed"
            except Exception as exc:
                lyt_res.code = "parse_failed"
                lyt_res.message = str(exc)
                warnings.append(f"{lyt_res.record.resref}.lyt parse failed: {exc}")
            layout["lyt"] = lyt_res
        if vis_res is not None and vis_res.data:
            try:
                module.vis = mf.VISData.from_text(_decode_text(vis_res.data))
                vis_res.parsed = module.vis
                vis_res.code = "parsed"
            except Exception as exc:
                vis_res.code = "parse_failed"
                vis_res.message = str(exc)
                warnings.append(f"{vis_res.record.resref}.vis parse failed: {exc}")
            layout["vis"] = vis_res
        for key, resource in resources.items():
            if key[1] == "pth":
                layout.setdefault("pth", resource)
            if key[1] == "wok":
                parsed = _safe_parse(resource, mf.WOKData.from_bytes, warnings)
                if parsed is not None:
                    if module.wok is None:
                        module.wok = parsed
                    module.room_woks[resource.record.resref] = parsed
                layout[f"wok:{resource.record.resref}"] = resource

    templates: dict[str, list[HydratedModuleResource]] = {}
    scripts: list[HydratedModuleResource] = []
    dialogs: list[HydratedModuleResource] = []
    for key, resource in resources.items():
        restype = key[1]
        if request.include_templates and restype in TEMPLATE_TYPES:
            templates.setdefault(restype, []).append(resource)
        elif request.include_scripts and restype in SCRIPT_TYPES:
            scripts.append(resource)
        elif request.include_dialogs and restype in DIALOG_TYPES:
            dialogs.append(resource)

    scene_result = ml.ModuleLoader(library=model_library).load_from_kotor_module(module, game=request.game)
    warnings.extend(list(getattr(scene_result, "warnings", []) or []))

    archive_layers = sorted(
        {record.source for record in listed if record.source},
        key=lambda source: (_archive_priority(source), source.lower()),
    )
    object_counts = _git_object_counts(module.git) if module.git is not None else {}
    core_loaded = any((module.are, module.git, module.ifo))
    return ModuleHydrationResult(
        ok=core_loaded,
        module_root=request.module_root,
        game=request.game,
        module=module,
        scene_result=scene_result,
        resources=resources,
        templates=templates,
        scripts=sorted(scripts, key=lambda r: r.record.resref),
        dialogs=sorted(dialogs, key=lambda r: r.record.resref),
        layout=layout,
        object_counts=object_counts,
        archive_layers=archive_layers,
        warnings=warnings,
        message=(
            f"Hydrated module '{request.module_root}' with {len(resources)} selected resource(s)."
            if core_loaded else
            f"Module '{request.module_root}' has no parsed ARE/GIT/IFO core resources."
        ),
        code="hydrated" if core_loaded else "core_missing",
    )


__all__ = [
    "ModuleResourceRecord",
    "HydratedModuleResource",
    "ModuleHydrationRequest",
    "ModuleHydrationResult",
    "hydrate_module",
]
