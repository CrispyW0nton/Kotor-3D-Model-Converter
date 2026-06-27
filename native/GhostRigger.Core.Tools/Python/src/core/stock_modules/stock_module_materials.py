"""Read-only material inventories for stock KotOR module room models."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.core.stock_modules.stock_module_archive import (
    ModuleArchiveResource,
    read_module_resource_bytes,
)


@dataclass(frozen=True)
class ModuleRoomTextureSlot:
    room_resref: str
    node_name: str
    slot_kind: str
    texture_resref: str
    face_count: int = 0
    vertex_count: int = 0
    editable_scope: str = "material_slot"


@dataclass(frozen=True)
class ModuleRoomMaterialInventory:
    room_resref: str
    slots: tuple[ModuleRoomTextureSlot, ...]
    parse_status: str = "ok"
    warning: str = ""

    @property
    def unique_textures(self) -> tuple[str, ...]:
        values = [slot.texture_resref for slot in self.slots if slot.texture_resref]
        return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class ModuleTextureUsageSummary:
    texture_resref: str
    slot_kind: str
    slot_count: int
    face_count: int
    vertex_count: int

    @property
    def label(self) -> str:
        return f"{self.texture_resref} {self.slot_kind}".strip()


@dataclass(frozen=True)
class ModuleRoomTextureDependency:
    texture_resref: str
    slot_kind: str
    slot_count: int
    face_count: int
    vertex_count: int
    source_status: str
    source_label: str
    effective_texture_resref: str
    effective_status: str
    effective_source_label: str
    overridden_slot_count: int = 0

    @property
    def summary(self) -> str:
        override = ""
        if self.overridden_slot_count:
            override = (
                f"; {self.overridden_slot_count}/{self.slot_count} slot(s) use "
                f"{self.effective_texture_resref} ({self.effective_status})"
            )
        return (
            f"{self.slot_count} {self.slot_kind} slot(s); source {self.source_status}"
            f" via {self.source_label or '(unresolved)'}{override}"
        )


@dataclass(frozen=True)
class ModuleTextureReplacementSidecar:
    resref: str
    restype: str
    source_label: str
    payload: bytes = b""

    @property
    def label(self) -> str:
        return f"{self.resref}.{self.restype}"


@dataclass(frozen=True)
class ModuleTextureReplacementDraft:
    target: ModuleRoomTextureSlot
    replacement_texture_resref: str
    replacement_source_label: str
    replacement_format: str
    replacement_payload: bytes = b""
    replacement_sidecars: tuple[ModuleTextureReplacementSidecar, ...] = ()
    status: str = "preview_only"

    @property
    def original_texture_resref(self) -> str:
        return self.target.texture_resref

    @property
    def summary(self) -> str:
        return (
            f"{self.target.room_resref}.{self.target.node_name} {self.target.slot_kind}: "
            f"{self.original_texture_resref} -> {self.replacement_texture_resref}"
        )


@dataclass(frozen=True)
class ModuleRoomTexturePreviewOverride:
    source_slot: ModuleRoomTextureSlot
    preview_texture_resref: str
    status: str
    source_label: str

    @property
    def slot_key(self) -> tuple[str, str, str]:
        return (
            _clean_resref(self.source_slot.room_resref),
            _clean_resref(self.source_slot.node_name),
            _clean_resref(self.source_slot.slot_kind),
        )

    @property
    def original_texture_resref(self) -> str:
        return self.source_slot.texture_resref

    @property
    def summary(self) -> str:
        return (
            f"{self.source_slot.room_resref}.{self.source_slot.node_name} {self.source_slot.slot_kind}: "
            f"{self.original_texture_resref} -> {self.preview_texture_resref} ({self.status})"
        )


def _clean_resref(value: object) -> str:
    return str(value or "").strip().strip("\x00").lower()


def _texture_resource_index(texture_resources: tuple[object, ...]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for resource in texture_resources:
        restype = _clean_resref(getattr(resource, "restype", ""))
        if restype not in {"tga", "tpc"}:
            continue
        resref = _clean_resref(getattr(resource, "resref", ""))
        if not resref:
            continue
        labels.setdefault(resref, _texture_resource_label(resource))
    return labels


def _texture_resource_label(resource: object) -> str:
    source = _clean_resref(getattr(resource, "source", ""))
    label = str(getattr(resource, "label", "") or "").strip()
    if source in {"imported texture", "edited texture"}:
        return f"session {label}".strip()
    game = str(getattr(resource, "game", "") or "").strip()
    if source == "game library" or game:
        return f"{game or 'game'} library {label}".strip()
    return f"module archive {label}".strip()


def _resource_map(resources: list[ModuleArchiveResource]) -> dict[tuple[str, str], ModuleArchiveResource]:
    return {(_clean_resref(resource.resref), _clean_resref(resource.restype)): resource for resource in resources}


def inspect_module_room_materials(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    room: ModuleArchiveResource,
) -> ModuleRoomMaterialInventory:
    """Parse one module-local room MDL/MDX pair and list material texture slots."""

    if room.restype != "mdl":
        return ModuleRoomMaterialInventory(room.resref, (), "skipped", "Resource is not an MDL room model.")
    by_key = _resource_map(resources)
    mdx = by_key.get((_clean_resref(room.resref), "mdx"))
    if mdx is None:
        return ModuleRoomMaterialInventory(room.resref, (), "missing_mdx", f"{room.resref}.mdx is missing.")
    try:
        mdl_bytes = read_module_resource_bytes(module_path, room)
        mdx_bytes = read_module_resource_bytes(module_path, mdx)
        from src.core.game.kotor_loader import load_model_from_bytes

        model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    except Exception as exc:
        try:
            return _inspect_room_materials_from_mdl_texture_fields(room, mdl_bytes, str(exc))
        except Exception:
            return ModuleRoomMaterialInventory(room.resref, (), "parse_failed", str(exc))
    if model is None:
        return _inspect_room_materials_from_mdl_texture_fields(
            room,
            mdl_bytes,
            "GhostRigger returned no model.",
        )

    slots: list[ModuleRoomTextureSlot] = []
    for node in getattr(model, "all_nodes", lambda: [])():
        if not bool(getattr(node, "is_mesh", False)):
            continue
        node_name = str(getattr(node, "name", "") or "")
        face_count = len(getattr(node, "faces", []) or [])
        vertex_count = len(getattr(node, "vertices", []) or [])
        diffuse = _clean_resref(getattr(node, "texture_clean", "") or getattr(node, "texture", ""))
        if diffuse and diffuse != "null":
            slots.append(
                ModuleRoomTextureSlot(
                    room_resref=room.resref,
                    node_name=node_name,
                    slot_kind="diffuse",
                    texture_resref=diffuse,
                    face_count=face_count,
                    vertex_count=vertex_count,
                )
            )
        lightmap = _clean_resref(getattr(node, "lightmap", ""))
        if lightmap and lightmap != "null":
            slots.append(
                ModuleRoomTextureSlot(
                    room_resref=room.resref,
                    node_name=node_name,
                    slot_kind="lightmap",
                    texture_resref=lightmap,
                    face_count=face_count,
                    vertex_count=vertex_count,
                    editable_scope="lightmap_slot",
                )
            )
    return ModuleRoomMaterialInventory(room.resref, tuple(slots))


def _inspect_room_materials_from_mdl_texture_fields(
    room: ModuleArchiveResource,
    mdl_bytes: bytes,
    reason: str,
) -> ModuleRoomMaterialInventory:
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields

    slots: list[ModuleRoomTextureSlot] = []
    for field in iter_mdl_texture_fields(mdl_bytes):
        diffuse = _clean_resref(field.texture_resref)
        if diffuse and diffuse != "null":
            slots.append(
                ModuleRoomTextureSlot(
                    room_resref=room.resref,
                    node_name=field.node_name,
                    slot_kind="diffuse",
                    texture_resref=diffuse,
                    editable_scope="material_slot",
                )
            )
        lightmap = _clean_resref(field.lightmap_resref)
        if lightmap and lightmap != "null":
            slots.append(
                ModuleRoomTextureSlot(
                    room_resref=room.resref,
                    node_name=field.node_name,
                    slot_kind="lightmap",
                    texture_resref=lightmap,
                    editable_scope="lightmap_slot",
                )
            )
    if not slots:
        return ModuleRoomMaterialInventory(room.resref, (), "parse_failed", reason)
    return ModuleRoomMaterialInventory(
        room.resref,
        tuple(slots),
        "texture_fields_only",
        f"Used fixed MDL texture fields because full model parsing was unavailable: {reason}",
    )


def inspect_module_materials(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    *,
    limit: int | None = None,
) -> tuple[ModuleRoomMaterialInventory, ...]:
    """Inspect module-local room MDLs and return material slots by room."""

    rooms = [resource for resource in resources if resource.restype == "mdl"]
    if limit is not None:
        rooms = rooms[: max(0, int(limit))]
    return tuple(inspect_module_room_materials(module_path, resources, room) for room in rooms)


def summarize_material_inventories(inventories: tuple[ModuleRoomMaterialInventory, ...]) -> tuple[str, str]:
    """Return compact details rows for the Module Editor details table."""

    slot_count = sum(len(item.slots) for item in inventories)
    texture_counter: Counter[str] = Counter()
    for inventory in inventories:
        texture_counter.update(slot.texture_resref for slot in inventory.slots if slot.texture_resref)
    if not inventories:
        return "0 rooms", "No room model material slots inspected yet."
    status_counts = Counter(item.parse_status for item in inventories)
    status = ", ".join(f"{key}:{value}" for key, value in sorted(status_counts.items()))
    top_textures = ", ".join(name for name, _count in texture_counter.most_common(8))
    return (
        f"{len(inventories)} rooms, {slot_count} material slots, {len(texture_counter)} textures",
        f"{status}; top textures: {top_textures or '(none)'}",
    )


def summarize_texture_usage(inventory: ModuleRoomMaterialInventory) -> tuple[ModuleTextureUsageSummary, ...]:
    """Return per-texture usage totals for one room material inventory."""

    totals: dict[tuple[str, str], list[int]] = {}
    for slot in inventory.slots:
        texture = _clean_resref(slot.texture_resref)
        slot_kind = _clean_resref(slot.slot_kind)
        if not texture:
            continue
        item = totals.setdefault((texture, slot_kind), [0, 0, 0])
        item[0] += 1
        item[1] += int(slot.face_count)
        item[2] += int(slot.vertex_count)
    rows = [
        ModuleTextureUsageSummary(
            texture_resref=texture,
            slot_kind=slot_kind,
            slot_count=values[0],
            face_count=values[1],
            vertex_count=values[2],
        )
        for (texture, slot_kind), values in totals.items()
    ]
    return tuple(sorted(rows, key=lambda item: (-item.slot_count, -item.face_count, item.texture_resref, item.slot_kind)))


def find_texture_usage_slots(
    inventories: tuple[ModuleRoomMaterialInventory, ...],
    texture_resref: str,
    *,
    slot_kind: str | None = None,
) -> tuple[ModuleRoomTextureSlot, ...]:
    """Return material slots that currently reference a texture ResRef."""

    wanted = _clean_resref(texture_resref)
    wanted_kind = _clean_resref(slot_kind) if slot_kind else ""
    slots: list[ModuleRoomTextureSlot] = []
    for inventory in inventories:
        for slot in inventory.slots:
            if _clean_resref(slot.texture_resref) != wanted:
                continue
            if wanted_kind and _clean_resref(slot.slot_kind) != wanted_kind:
                continue
            slots.append(slot)
    return tuple(slots)


def summarize_texture_dependencies(
    inventory: ModuleRoomMaterialInventory,
    texture_resources: tuple[object, ...],
    overrides: tuple[ModuleRoomTexturePreviewOverride, ...] = (),
) -> tuple[ModuleRoomTextureDependency, ...]:
    """Resolve room material texture references against available texture resources."""

    usage_rows = summarize_texture_usage(inventory)
    resource_index = _texture_resource_index(texture_resources)
    override_by_key = {override.slot_key: override for override in overrides}
    dependencies: list[ModuleRoomTextureDependency] = []
    for usage in usage_rows:
        slots = tuple(
            slot
            for slot in inventory.slots
            if _clean_resref(slot.texture_resref) == _clean_resref(usage.texture_resref)
            and _clean_resref(slot.slot_kind) == _clean_resref(usage.slot_kind)
        )
        slot_overrides = tuple(
            override
            for slot in slots
            for override in (
                override_by_key.get(
                    (
                        _clean_resref(slot.room_resref),
                        _clean_resref(slot.node_name),
                        _clean_resref(slot.slot_kind),
                    )
                ),
            )
            if override is not None
        )
        source_label = resource_index.get(_clean_resref(usage.texture_resref), "")
        effective_texture = usage.texture_resref
        effective_label = source_label
        effective_status = "source"
        if slot_overrides:
            replacement_counts = Counter(_clean_resref(override.preview_texture_resref) for override in slot_overrides)
            effective_texture = replacement_counts.most_common(1)[0][0]
            effective_label = resource_index.get(effective_texture, slot_overrides[0].source_label)
            effective_status = "/".join(sorted({override.status for override in slot_overrides}))
        dependencies.append(
            ModuleRoomTextureDependency(
                texture_resref=usage.texture_resref,
                slot_kind=usage.slot_kind,
                slot_count=usage.slot_count,
                face_count=usage.face_count,
                vertex_count=usage.vertex_count,
                source_status="resolved" if source_label else "missing",
                source_label=source_label,
                effective_texture_resref=effective_texture,
                effective_status=effective_status,
                effective_source_label=effective_label,
                overridden_slot_count=len(slot_overrides),
            )
        )
    return tuple(dependencies)


def create_texture_replacement_draft(
    target: ModuleRoomTextureSlot,
    texture_resource: ModuleArchiveResource,
    *,
    sidecar_resources: tuple[object, ...] = (),
) -> ModuleTextureReplacementDraft:
    """Build a non-destructive material-slot replacement preview."""

    restype = _clean_resref(texture_resource.restype)
    if restype not in {"tga", "tpc"}:
        raise ValueError("Texture replacement preview requires a TGA or TPC resource.")
    if target.slot_kind != "diffuse":
        raise ValueError("Only diffuse material-slot replacement previews are enabled in this first slice.")
    replacement = _clean_resref(texture_resource.resref)
    if not replacement:
        raise ValueError("Replacement texture resource has no resref.")
    if len(replacement) > 16:
        raise ValueError("Replacement texture resref exceeds 16 characters; rename the TGA/TPC before replacing this material slot.")
    if not _is_ascii_resource_name(replacement):
        raise ValueError("Replacement texture resref must be ASCII letters, numbers, or underscores.")
    replacement_payload = b""
    read_bytes = getattr(texture_resource, "read_bytes", None)
    if callable(read_bytes):
        replacement_payload = bytes(read_bytes() or b"")
    sidecars: list[ModuleTextureReplacementSidecar] = []
    for sidecar_resource in sidecar_resources:
        sidecar_restype = _clean_resref(getattr(sidecar_resource, "restype", ""))
        sidecar_resref = _clean_resref(getattr(sidecar_resource, "resref", ""))
        if sidecar_restype != "txi" or sidecar_resref != replacement:
            continue
        sidecar_read_bytes = getattr(sidecar_resource, "read_bytes", None)
        if not callable(sidecar_read_bytes):
            continue
        sidecars.append(
            ModuleTextureReplacementSidecar(
                resref=sidecar_resref,
                restype=sidecar_restype,
                source_label=str(getattr(sidecar_resource, "label", f"{sidecar_resref}.{sidecar_restype}")),
                payload=bytes(sidecar_read_bytes() or b""),
            )
        )
    return ModuleTextureReplacementDraft(
        target=target,
        replacement_texture_resref=replacement,
        replacement_source_label=texture_resource.label,
        replacement_format=restype,
        replacement_payload=replacement_payload,
        replacement_sidecars=tuple(sidecars),
    )


def _is_ascii_resource_name(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return all(character.isalnum() or character == "_" for character in value)


def create_texture_replacement_drafts_for_matching_slots(
    slots: tuple[ModuleRoomTextureSlot, ...],
    texture_resource: ModuleArchiveResource,
    *,
    original_texture_resref: str,
    sidecar_resources: tuple[object, ...] = (),
) -> tuple[ModuleTextureReplacementDraft, ...]:
    """Build replacement drafts for every diffuse slot using one original texture."""

    original = _clean_resref(original_texture_resref)
    drafts: list[ModuleTextureReplacementDraft] = []
    seen: set[tuple[str, str, str, str]] = set()
    for slot in slots:
        if slot.slot_kind != "diffuse" or _clean_resref(slot.texture_resref) != original:
            continue
        key = (
            _clean_resref(slot.room_resref),
            _clean_resref(slot.node_name),
            _clean_resref(slot.slot_kind),
            _clean_resref(slot.texture_resref),
        )
        if key in seen:
            continue
        seen.add(key)
        drafts.append(
            create_texture_replacement_draft(
                slot,
                texture_resource,
                sidecar_resources=sidecar_resources,
            )
        )
    return tuple(drafts)


def summarize_texture_preview_overrides(
    inventory: ModuleRoomMaterialInventory,
    drafts: tuple[ModuleTextureReplacementDraft, ...],
    *,
    staged_count: int = 0,
) -> tuple[ModuleRoomTexturePreviewOverride, ...]:
    """Return session-only texture overrides for one room inventory."""

    slot_by_key = {
        (_clean_resref(slot.room_resref), _clean_resref(slot.node_name), _clean_resref(slot.slot_kind)): slot
        for slot in inventory.slots
    }
    overrides: list[ModuleRoomTexturePreviewOverride] = []
    seen: set[tuple[str, str, str]] = set()
    staged_cutoff = max(0, int(staged_count))
    for index, draft in enumerate(drafts):
        key = (
            _clean_resref(draft.target.room_resref),
            _clean_resref(draft.target.node_name),
            _clean_resref(draft.target.slot_kind),
        )
        slot = slot_by_key.get(key)
        if slot is None or key in seen:
            continue
        seen.add(key)
        status = "staged" if index < staged_cutoff else "preview"
        overrides.append(
            ModuleRoomTexturePreviewOverride(
                source_slot=slot,
                preview_texture_resref=draft.replacement_texture_resref,
                status=status,
                source_label=draft.replacement_source_label,
            )
        )
    return tuple(overrides)


def texture_preview_for_slot(
    slot: ModuleRoomTextureSlot,
    overrides: tuple[ModuleRoomTexturePreviewOverride, ...],
) -> ModuleRoomTexturePreviewOverride | None:
    """Return the active session override for a source material slot."""

    key = (_clean_resref(slot.room_resref), _clean_resref(slot.node_name), _clean_resref(slot.slot_kind))
    return next((override for override in overrides if override.slot_key == key), None)
