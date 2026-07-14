"""Canonical PyKotor UTP export, readback, and resource-bundle checks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, InventoryItem, ResRef
from pykotor.resource.formats.gff import GFFContent, bytes_gff, read_gff
from pykotor.resource.formats.twoda import read_2da
from pykotor.resource.generics.dlg import read_dlg
from pykotor.resource.generics.utd import read_utd
from pykotor.resource.generics.utp import UTP, dismantle_utp, read_utp


_SCRIPT_ATTRS: tuple[str, ...] = (
    "on_closed",
    "on_damaged",
    "on_death",
    "on_end_dialog",
    "on_open_failed",
    "on_heartbeat",
    "on_inventory",
    "on_melee_attack",
    "on_force_power",
    "on_open",
    "on_lock",
    "on_unlock",
    "on_used",
    "on_user_defined",
    "on_disarm",
    "on_trap_triggered",
)

_DOOR_SCRIPT_ATTRS: tuple[str, ...] = (
    "on_click",
    "on_closed",
    "on_damaged",
    "on_death",
    "on_disarm",
    "on_heartbeat",
    "on_lock",
    "on_melee",
    "on_open",
    "on_open_failed",
    "on_power",
    "on_trap_triggered",
    "on_unlock",
    "on_user_defined",
)

_DLG_SCRIPT_ATTRS = frozenset(("active1", "active2", "script1", "script2", "on_abort", "on_end"))


def _game(value: str) -> Game:
    clean = str(value or "").strip().upper()
    if clean == "K1":
        return Game.K1
    if clean == "K2":
        return Game.K2
    raise ValueError("Placeable UTP export game must be K1 or K2.")


def _resref(value: Any) -> ResRef:
    return ResRef(str(value or "").strip().lower())


def _sha(data: bytes) -> str:
    return sha256(bytes(data)).hexdigest()


@dataclass(frozen=True)
class PlaceableUTPReadback:
    template_resref: str
    tag: str
    display_name: str
    appearance_id: int
    static: bool
    useable: bool
    has_inventory: bool
    inventory_items: tuple[str, ...]
    lockable: bool
    locked: bool
    key_required: bool
    key_name: str
    unlock_dc: int
    lock_dc: int
    maximum_hp: int
    current_hp: int
    hardness: int
    trap_detectable: bool
    trap_disarmable: bool
    trap_type: int
    conversation_resref: str
    scripts: dict[str, str]

    @property
    def dependency_keys(self) -> tuple[tuple[str, str], ...]:
        keys = {(value.lower(), "NCS") for value in self.scripts.values() if value}
        if self.conversation_resref:
            keys.add((self.conversation_resref.lower(), "DLG"))
        keys.update((value.lower(), "UTI") for value in self.inventory_items if value)
        return tuple(sorted(keys))


@dataclass(frozen=True)
class PlaceableUTPExportResult:
    template_resref: str
    game: str
    utp_bytes: bytes
    readback: PlaceableUTPReadback
    output_sha256: str
    base_sha256: str = ""
    base_structural_evidence: bool = False
    appearance_mapping_evidence: bool = False
    structurally_grounded: bool = False
    engine_ready: bool = False
    readiness_status: str = "synthetic_unverified"
    preserved_unknown_labels: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    output_path: str = ""

    def as_resource_tuple(self) -> tuple[str, str, bytes]:
        return (self.template_resref, ".UTP", self.utp_bytes)


def _apply_asset_to_utp(utp: UTP, asset: Any) -> UTP:
    gameplay = asset.gameplay
    utp.resref = _resref(asset.template_resref)
    utp.tag = str(asset.tag or "")
    utp.name = LocalizedString.from_english(str(asset.display_name or asset.template_resref))
    utp.description = LocalizedString.from_english(str(asset.description or ""))
    utp.comment = str(asset.comment or "")
    utp.appearance_id = int(asset.appearance_id)
    utp.static = bool(gameplay.static)
    utp.useable = bool(gameplay.useable)
    utp.has_inventory = bool(gameplay.has_inventory)
    utp.inventory = [InventoryItem(_resref(value)) for value in gameplay.inventory_items]
    utp.lockable = bool(gameplay.lockable)
    utp.locked = bool(gameplay.locked)
    utp.key_required = bool(gameplay.key_required)
    utp.key_name = str(gameplay.key_name or "")
    utp.auto_remove_key = bool(gameplay.auto_remove_key)
    utp.unlock_dc = int(gameplay.unlock_dc)
    utp.lock_dc = int(gameplay.lock_dc)
    utp.trap_detectable = bool(gameplay.trap_detectable)
    utp.trap_detect_dc = int(gameplay.trap_detect_dc)
    utp.trap_disarmable = bool(gameplay.trap_disarmable)
    utp.trap_disarm_dc = int(gameplay.trap_disarm_dc)
    utp.trap_flag = int(gameplay.trap_flag)
    utp.trap_one_shot = bool(gameplay.trap_one_shot)
    utp.trap_type = int(gameplay.trap_type)
    utp.maximum_hp = int(gameplay.maximum_hp)
    utp.current_hp = int(gameplay.current_hp)
    utp.hardness = int(gameplay.hardness)
    utp.plot = bool(gameplay.plot)
    utp.min1_hp = bool(gameplay.min1_hp)
    utp.not_blastable = bool(gameplay.not_blastable)
    utp.party_interact = bool(gameplay.party_interact)
    utp.conversation = _resref(gameplay.conversation_resref)
    for name in _SCRIPT_ATTRS:
        setattr(utp, name, _resref(asset.scripts.get(name, "")))
    return utp


def read_placeable_utp(data: bytes) -> PlaceableUTPReadback:
    utp = read_utp(bytes(data))
    return PlaceableUTPReadback(
        template_resref=str(utp.resref).lower(),
        tag=str(utp.tag or ""),
        display_name=str(utp.name or ""),
        appearance_id=int(utp.appearance_id),
        static=bool(utp.static),
        useable=bool(utp.useable),
        has_inventory=bool(utp.has_inventory),
        inventory_items=tuple(str(item.resref).lower() for item in utp.inventory),
        lockable=bool(utp.lockable),
        locked=bool(utp.locked),
        key_required=bool(utp.key_required),
        key_name=str(utp.key_name or "").lower(),
        unlock_dc=int(utp.unlock_dc),
        lock_dc=int(utp.lock_dc),
        maximum_hp=int(utp.maximum_hp),
        current_hp=int(utp.current_hp),
        hardness=int(utp.hardness),
        trap_detectable=bool(utp.trap_detectable),
        trap_disarmable=bool(utp.trap_disarmable),
        trap_type=int(utp.trap_type),
        conversation_resref=str(utp.conversation).lower(),
        scripts={name: str(getattr(utp, name)).lower() for name in _SCRIPT_ATTRS if str(getattr(utp, name))},
    )


def _dialog_script_dependencies(data: bytes) -> tuple[tuple[str, str], ...]:
    """Return compiled-script resources referenced by a DLG graph."""

    dialog = read_dlg(bytes(data))
    dependencies: set[tuple[str, str]] = set()
    visited: set[int] = set()

    def walk(value: Any) -> None:
        if isinstance(value, (str, int, float, bool, bytes, type(None), ResRef)):
            return
        identity = id(value)
        if identity in visited:
            return
        visited.add(identity)
        if isinstance(value, (tuple, list, set)):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        module_name = str(getattr(type(value), "__module__", "") or "")
        if "pykotor.resource.generics.dlg" not in module_name:
            return
        for name, item in vars(value).items():
            if name in _DLG_SCRIPT_ATTRS:
                resref = str(item or "").strip().lower()
                if resref:
                    dependencies.add((resref, "NCS"))
            walk(item)

    walk(dialog)
    return tuple(sorted(dependencies))


def interactive_resource_dependency_keys(restype: str, data: bytes) -> tuple[tuple[str, str], ...]:
    """Return directly declared runtime dependencies for UTP, UTD, or DLG.

    This deliberately reports only structurally declared references. Compiled
    NCS can contain further tag/global/resource behavior and therefore remains
    a separate manual/game-proof boundary.
    """

    clean_type = str(restype or "").strip().upper().lstrip(".")
    payload = bytes(data or b"")
    if clean_type == "UTP":
        return read_placeable_utp(payload).dependency_keys
    if clean_type == "UTD":
        door = read_utd(payload)
        dependencies = {
            (str(getattr(door, name, "") or "").strip().lower(), "NCS")
            for name in _DOOR_SCRIPT_ATTRS
            if str(getattr(door, name, "") or "").strip()
        }
        conversation = str(getattr(door, "conversation", "") or "").strip().lower()
        if conversation:
            dependencies.add((conversation, "DLG"))
        key_name = str(getattr(door, "key_name", "") or "").strip().lower()
        if bool(getattr(door, "key_required", False)) and key_name:
            dependencies.add((key_name, "UTI"))
        return tuple(sorted(dependencies))
    if clean_type == "DLG":
        return _dialog_script_dependencies(payload)
    return ()


def _appearance_mapping_matches(asset: Any, appearance_2da_bytes: bytes | None) -> tuple[bool, str]:
    evidence = getattr(asset, "appearance_evidence", None)
    if evidence is None or not evidence.verified or not appearance_2da_bytes:
        return False, ""
    if _sha(appearance_2da_bytes) != str(evidence.source_sha256 or "").lower():
        return False, ""
    if evidence.appearance_id != asset.appearance_id or str(evidence.game or "").upper() != str(asset.game or "").upper():
        return False, ""
    try:
        table = read_2da(appearance_2da_bytes)
        mapped = str(table.get_cell(int(asset.appearance_id), "modelname") or "").strip().lower()
    except Exception:
        return False, ""
    expected = str(evidence.model_resref or "").strip().lower()
    model_ref = getattr(getattr(asset, "resources", None), "mdl", None)
    if model_ref is not None and model_ref.resref:
        expected = str(model_ref.resref).lower()
    return bool(mapped and mapped == expected), mapped


def export_placeable_utp(
    asset: Any,
    *,
    base_utp_bytes: bytes | None = None,
    appearance_2da_bytes: bytes | None = None,
    output_path: str | Path | None = None,
) -> PlaceableUTPExportResult:
    """Export through canonical PyKotor labels and independently read back.

    A supplied base UTP is cloned as raw GFF before known fields are patched,
    preserving unknown vanilla fields and their ordering. No result is marked
    engine-ready; only byte-verified structural grounding is reported.
    """

    from src.core.project.placeable_asset import validate_placeable_asset

    validation = validate_placeable_asset(asset)
    if not validation.utp_export_ready:
        blocking = "; ".join(issue.message for issue in validation.issues if issue.severity == "blocking")
        raise ValueError(blocking or "Placeable asset is not ready for UTP export.")

    game = _game(asset.game)
    base_hash = ""
    base_verified = False
    preserved_unknown: tuple[str, ...] = ()
    if base_utp_bytes:
        base_hash = _sha(base_utp_bytes)
        base_gff = read_gff(base_utp_bytes)
        if base_gff.content != GFFContent.UTP:
            raise ValueError("Base structural authority is not a UTP GFF.")
        base_utp = read_utp(base_utp_bytes)
        updated = _apply_asset_to_utp(base_utp, asset)
        patch_gff = dismantle_utp(updated, game)
        output_gff = deepcopy(base_gff)
        for label in patch_gff.root.keys():
            output_gff.root._fields[label] = deepcopy(patch_gff.root._fields[label])
        preserved_unknown = tuple(sorted(set(base_gff.root.keys()) - set(patch_gff.root.keys())))
        evidence = getattr(asset, "base_evidence", None)
        template = getattr(asset, "base_template", None)
        base_verified = bool(
            evidence
            and template
            and evidence.template
            and evidence.template.stable_key() == template.stable_key()
            and str(evidence.sha256 or "").lower() == base_hash
            and int(evidence.field_count or 0) == len(base_gff.root)
        )
    else:
        output_gff = dismantle_utp(_apply_asset_to_utp(UTP(), asset), game)

    output_bytes = bytes_gff(output_gff)
    reloaded_gff = read_gff(output_bytes)
    if reloaded_gff.content != GFFContent.UTP:
        raise ValueError("Exported placeable did not read back as UTP.")
    if base_utp_bytes and any(label not in reloaded_gff.root for label in preserved_unknown):
        raise ValueError("Base-template clone lost unknown UTP fields during export.")
    readback = read_placeable_utp(output_bytes)
    if readback.template_resref != str(asset.template_resref).lower() or readback.appearance_id != int(asset.appearance_id):
        raise ValueError("UTP readback does not match authored template identity or Appearance row.")

    appearance_verified, _mapped_model = _appearance_mapping_matches(asset, appearance_2da_bytes)
    grounded = bool(base_verified and appearance_verified)
    warnings: list[str] = []
    if not base_verified:
        warnings.append("No matching byte-verified base UTP structure was supplied.")
    if not appearance_verified:
        warnings.append("placeables.2da Appearance-to-model mapping was not byte-verified.")
    warnings.append("UTP readback is not an in-game load/appearance proof.")
    written = ""
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
                delete=False,
            ) as stream:
                temporary = stream.name
                stream.write(output_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        written = str(target)
    return PlaceableUTPExportResult(
        template_resref=readback.template_resref,
        game=str(asset.game).upper(),
        utp_bytes=output_bytes,
        readback=readback,
        output_sha256=_sha(output_bytes),
        base_sha256=base_hash,
        base_structural_evidence=base_verified,
        appearance_mapping_evidence=appearance_verified,
        structurally_grounded=grounded,
        engine_ready=False,
        readiness_status="structurally_grounded_unproven" if grounded else "synthetic_or_unverified",
        preserved_unknown_labels=preserved_unknown,
        warnings=tuple(warnings),
        output_path=written,
    )


@dataclass(frozen=True)
class PlaceableBundleResource:
    resref: str
    restype: str
    data: bytes
    source: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.resref.strip().lower(), self.restype.strip().lstrip(".").upper())

    def as_tuple(self) -> tuple[str, str, bytes]:
        return (self.key[0], f".{self.key[1]}", bytes(self.data))


@dataclass(frozen=True)
class PlaceableBundleIssue:
    severity: str
    code: str
    message: str
    resource_key: tuple[str, str] | None = None


@dataclass(frozen=True)
class PlaceableResourceBundle:
    resources: tuple[PlaceableBundleResource, ...]
    issues: tuple[PlaceableBundleIssue, ...] = ()
    engine_ready: bool = False

    @property
    def output_resources(self) -> tuple[tuple[str, str, bytes], ...]:
        return tuple(resource.as_tuple() for resource in self.resources)

    @property
    def has_blocking(self) -> bool:
        return any(issue.severity == "blocking" for issue in self.issues)


class PlaceableResourceCollisionError(ValueError):
    """Raised when two payloads claim one case-insensitive KOTOR key."""


def _coerce_resource(value: Any) -> PlaceableBundleResource:
    if isinstance(value, PlaceableBundleResource):
        return value
    resref, restype, data = value[:3]
    source = value[3] if len(value) > 3 else ""
    return PlaceableBundleResource(str(resref), str(restype), bytes(data), str(source))


def validate_placeable_resource_bundle(resources: Iterable[Any]) -> tuple[PlaceableBundleIssue, ...]:
    normalized = tuple(_coerce_resource(value) for value in resources)
    by_key = {resource.key: resource for resource in normalized}
    issues: list[PlaceableBundleIssue] = []
    for resource in normalized:
        if resource.key[1] != "UTP":
            continue
        try:
            readback = read_placeable_utp(resource.data)
        except Exception as exc:
            issues.append(PlaceableBundleIssue("blocking", "invalid_utp_payload", str(exc), resource.key))
            continue
        for dependency in readback.dependency_keys:
            if dependency not in by_key:
                issues.append(
                    PlaceableBundleIssue(
                        "blocking",
                        "missing_placeable_dependency",
                        f"{resource.key[0]}.utp references missing {dependency[0]}.{dependency[1].lower()}.",
                        dependency,
                    )
                )
    return tuple(issues)


def build_placeable_resource_bundle(
    asset: Any,
    utp_result: PlaceableUTPExportResult,
    *,
    resource_reader: Callable[[Any], bytes],
    existing_resources: Iterable[Any] = (),
) -> PlaceableResourceBundle:
    existing = tuple(_coerce_resource(value) for value in existing_resources)
    by_key: dict[tuple[str, str], PlaceableBundleResource] = {resource.key: resource for resource in existing}
    new_resources: list[PlaceableBundleResource] = []

    def add(resource: PlaceableBundleResource) -> None:
        prior = by_key.get(resource.key)
        if prior is not None:
            if bytes(prior.data) != bytes(resource.data):
                raise PlaceableResourceCollisionError(
                    f"Resource collision for {resource.key[0]}.{resource.key[1].lower()}: "
                    f"{prior.source or 'existing bundle'} vs {resource.source or 'placeable asset'}."
                )
            return
        by_key[resource.key] = resource
        new_resources.append(resource)

    add(PlaceableBundleResource(utp_result.template_resref, "UTP", utp_result.utp_bytes, "generated_utp"))
    refs = [asset.resources.mdl, asset.resources.mdx, asset.resources.pwk, *asset.resources.textures]
    for address in (value for value in refs if value is not None):
        if not address.resref or not address.restype:
            raise ValueError(f"Bundled placeable resource lacks resref/restype: {address.display_name()}")
        add(
            PlaceableBundleResource(
                address.resref,
                address.restype,
                bytes(resource_reader(address)),
                address.stable_key(),
            )
        )
    combined = (*existing, *new_resources)
    issues = validate_placeable_resource_bundle(combined)
    return PlaceableResourceBundle(resources=tuple(new_resources), issues=issues, engine_ready=False)


__all__ = [
    "PlaceableBundleIssue",
    "PlaceableBundleResource",
    "PlaceableResourceBundle",
    "PlaceableResourceCollisionError",
    "PlaceableUTPExportResult",
    "PlaceableUTPReadback",
    "build_placeable_resource_bundle",
    "export_placeable_utp",
    "interactive_resource_dependency_keys",
    "read_placeable_utp",
    "validate_placeable_resource_bundle",
]
