"""Build game-loadable placeable models from GhostStudio particle attachments.

This workflow owns the cross-package operation: clone a target-game placeable
model, graft retail emitter nodes, write/read back MDL+MDX, allocate a
``placeables.2da`` row, patch the UTP Appearance field, and collect the emitter
textures needed by the exported effect.  Source game resources are read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import re
from typing import Any, Callable, Iterable

from pykotor.resource.formats.twoda import bytes_2da, read_2da

from src.core.game.kotor_loader import load_model_from_bytes
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.particles.emitter_library import graft_particle_effects
from src.core.placeables.placeable_utp_io import (
    PlaceableBundleIssue,
    PlaceableBundleResource,
    PlaceableUTPExportResult,
    export_placeable_utp,
)
from src.core.project.placeable_asset import (
    PlaceableAppearanceMappingEvidence,
    PlaceableAsset,
)
from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import GameResourceQuery


_SAFE_RESREF = re.compile(r"^[a-z0-9_]{1,16}$")


@dataclass(frozen=True)
class ParticlePlaceableBuild:
    """One read-back-verified particle placeable and its runtime resources."""

    asset: PlaceableAsset
    utp_result: PlaceableUTPExportResult
    resources: tuple[PlaceableBundleResource, ...]
    appearance_2da_bytes: bytes
    appearance_id: int
    model_resref: str
    source_model_resref: str
    emitter_count: int
    texture_keys: tuple[tuple[str, str], ...] = ()
    issues: tuple[PlaceableBundleIssue, ...] = ()
    engine_ready: bool = False


def _read(resource_reader: Callable[[Any], bytes], query: Any) -> bytes:
    data = resource_reader(query)
    return bytes(data or b"")


def _cell(table: Any, row: int, column: str) -> str:
    try:
        return str(table.get_cell(int(row), column) or "").strip()
    except Exception:
        return ""


def _header(table: Any, wanted: str) -> str:
    for name in table.get_headers():
        if str(name).casefold() == wanted.casefold():
            return str(name)
    return ""


def _generated_label(asset: PlaceableAsset) -> str:
    return f"GhostStudio_{asset.template_resref}"[:32]


def _generated_model_resref(asset: PlaceableAsset, table: Any, source_model: str) -> str:
    template = str(asset.template_resref or "").strip().lower()
    if not _SAFE_RESREF.fullmatch(template):
        raise ValueError("Particle placeable template resref is not KOTOR-safe.")
    label_column = _header(table, "label")
    model_column = _header(table, "modelname")
    if not model_column:
        raise ValueError("placeables.2da has no modelname column.")
    marker = _generated_label(asset).casefold()
    models: dict[str, list[int]] = {}
    for row in range(table.get_height()):
        model = _cell(table, row, model_column).lower()
        if model and model not in {"****", "null"}:
            models.setdefault(model, []).append(row)
    # Reuse our own prior allocation so repeated exports are stable.
    for model, rows in models.items():
        if any(label_column and _cell(table, row, label_column).casefold() == marker for row in rows):
            return model
    if template != source_model.lower() and template not in models:
        return template
    digest = sha1(str(asset.asset_id or template).encode("utf-8")).hexdigest()
    for offset in range(0, 32, 4):
        candidate = f"{template[:11]}_{digest[offset:offset + 4]}"[:16]
        if candidate not in models and candidate != source_model.lower():
            return candidate
    raise ValueError(f"Could not allocate a collision-free model resref for {template}.")


def _appearance_row_for_model(asset: PlaceableAsset, table: Any, model_resref: str) -> int:
    model_column = _header(table, "modelname")
    label_column = _header(table, "label")
    marker = _generated_label(asset)
    matches = [
        row
        for row in range(table.get_height())
        if _cell(table, row, model_column).casefold() == model_resref.casefold()
        and (not label_column or _cell(table, row, label_column).casefold() == marker.casefold())
    ]
    if len(matches) > 1:
        raise ValueError(f"placeables.2da contains duplicate GhostStudio rows for {model_resref}: {matches}")
    if matches:
        return matches[0]
    donor = int(asset.appearance_id if asset.appearance_id is not None else -1)
    if donor < 0 or donor >= table.get_height():
        raise ValueError(f"The donor placeables.2da row {donor} does not exist.")
    values = {header: _cell(table, donor, str(header)) or "****" for header in table.get_headers()}
    values[model_column] = model_resref
    if label_column:
        values[label_column] = marker
    row = table.add_row(str(table.get_height()), values)
    if int(row) < 0:
        raise ValueError("Could not append the particle placeable appearance row.")
    return int(row)


def _resource_query(game: str, resref: str, restype: str) -> GameResourceQuery:
    return GameResourceQuery(game=str(game or "").upper() or None, resref=resref, restype=restype)


def _effect_texture_names(effects: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    names: set[str] = set()
    for record in effects:
        definition = dict(record.get("definition") or {})
        if definition.get("force_fields") or abs(float(definition.get("hue_cycle_speed") or 0.0)) > 1.0e-9:
            raise ValueError(
                "Force fields and dynamic colour are GhostStudio preview extensions and cannot be written to a retail KOTOR MDL. "
                "Disable those extensions before game export."
            )
        for key in ("texture", "depth_texture_name"):
            name = str(definition.get(key) or "").strip().lower()
            if name and name not in {"null", "none", "****"}:
                names.add(name[:16])
    return tuple(sorted(names))


def _particle_texture_resources(
    game: str,
    effects: Iterable[dict[str, Any]],
    resource_reader: Callable[[Any], bytes],
) -> tuple[PlaceableBundleResource, ...]:
    resources: list[PlaceableBundleResource] = []
    for name in _effect_texture_names(effects):
        tpc = b""
        try:
            tpc = _read(resource_reader, _resource_query(game, name, "TPC"))
        except Exception:
            tpc = b""
        if tpc:
            resources.append(PlaceableBundleResource(name, "TPC", tpc, f"{game}:particle_texture"))
            continue
        tga = b""
        try:
            tga = _read(resource_reader, _resource_query(game, name, "TGA"))
        except Exception:
            tga = b""
        if not tga:
            raise FileNotFoundError(f"Particle texture {name}.tpc/.tga does not resolve in {game}.")
        resources.append(PlaceableBundleResource(name, "TGA", tga, f"{game}:particle_texture"))
        try:
            txi = _read(resource_reader, _resource_query(game, name, "TXI"))
        except Exception:
            txi = b""
        if txi:
            resources.append(PlaceableBundleResource(name, "TXI", txi, f"{game}:particle_texture_metadata"))
    return tuple(resources)


def _passthrough_custom_resources(
    asset: PlaceableAsset,
    resource_reader: Callable[[Any], bytes],
) -> tuple[PlaceableBundleResource, ...]:
    resources: list[PlaceableBundleResource] = []
    for address in (asset.resources.pwk, *asset.resources.textures):
        if address is None:
            continue
        data = _read(resource_reader, address)
        if not data:
            raise FileNotFoundError(f"Placeable dependency does not resolve: {address.display_name()}")
        resources.append(
            PlaceableBundleResource(
                str(address.resref or ""),
                str(address.restype or ""),
                data,
                address.stable_key(),
            )
        )
    return tuple(resources)


def build_particle_placeable(
    asset: PlaceableAsset,
    *,
    base_utp_bytes: bytes | None,
    appearance_2da_bytes: bytes,
    resource_reader: Callable[[Any], bytes],
) -> ParticlePlaceableBuild:
    """Compile one authored particle attachment into retail KOTOR resources."""

    effects = tuple(dict(record) for record in (asset.metadata or {}).get("particle_effects") or ())
    if not effects:
        raise ValueError("The placeable has no particle effects to bake.")
    if not appearance_2da_bytes:
        raise ValueError("Game export needs the target game's placeables.2da.")
    table = read_2da(bytes(appearance_2da_bytes))
    donor = int(asset.appearance_id if asset.appearance_id is not None else -1)
    source_model = ""
    if asset.resources.mdl is not None and asset.resources.mdx is not None:
        source_model = str(asset.resources.mdl.resref or "").strip().lower()
        mdl_bytes = _read(resource_reader, asset.resources.mdl)
        mdx_bytes = _read(resource_reader, asset.resources.mdx)
    else:
        source_model = _cell(table, donor, "modelname").lower()
        if not source_model or source_model in {"****", "null"}:
            raise ValueError(f"Donor placeables.2da row {donor} has no loadable modelname.")
        mdl_bytes = _read(resource_reader, _resource_query(asset.game, source_model, "MDL"))
        mdx_bytes = _read(resource_reader, _resource_query(asset.game, source_model, "MDX"))
    if not mdl_bytes:
        raise FileNotFoundError(f"Base placeable model does not resolve: {source_model}.mdl")

    model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    if model is None:
        raise ValueError(f"Base placeable model could not be parsed: {source_model}")
    before_emitters = sum(1 for node in model.all_nodes() if bool(getattr(node, "is_emitter", False)))
    grafted = graft_particle_effects(model, effects)
    if grafted != len(effects):
        raise ValueError(f"Only {grafted} of {len(effects)} selected emitter records could be grafted.")

    model_resref = _generated_model_resref(asset, table, source_model)
    model.name = model_resref
    mdl_output, mdx_output = MDLBinaryWriter().write(model)
    reloaded = load_model_from_bytes(mdl_output, mdx_output)
    if reloaded is None:
        raise ValueError("The particle placeable MDL/MDX pair failed readback.")
    after_emitters = sum(1 for node in reloaded.all_nodes() if bool(getattr(node, "is_emitter", False)))
    if after_emitters < before_emitters + grafted:
        raise ValueError(
            f"Emitter readback failed: expected at least {before_emitters + grafted}, found {after_emitters}."
        )

    appearance_id = _appearance_row_for_model(asset, table, model_resref)
    merged_2da = bytes(bytes_2da(table))
    check = read_2da(merged_2da)
    if _cell(check, appearance_id, "modelname").casefold() != model_resref.casefold():
        raise ValueError("The generated placeables.2da mapping failed readback.")

    baked_asset = PlaceableAsset.from_dict(asset.to_dict())
    baked_asset.appearance_id = appearance_id
    baked_asset.resources.mdl = ResourceAddress(
        scheme="generated_output",
        game=asset.game,
        layer="particle_placeable",
        resref=model_resref,
        restype="MDL",
    )
    baked_asset.resources.mdx = ResourceAddress(
        scheme="generated_output",
        game=asset.game,
        layer="particle_placeable",
        resref=model_resref,
        restype="MDX",
    )
    baked_asset.appearance_evidence = PlaceableAppearanceMappingEvidence(
        game=asset.game,
        appearance_id=appearance_id,
        model_resref=model_resref,
        source=f"generated:{asset.game}:placeables.2da",
        source_sha256=sha256(merged_2da).hexdigest(),
        verified=True,
    )
    utp_result = export_placeable_utp(
        baked_asset,
        base_utp_bytes=base_utp_bytes,
        appearance_2da_bytes=merged_2da,
    )

    resources = [
        PlaceableBundleResource(utp_result.template_resref, "UTP", utp_result.utp_bytes, "generated_particle_utp"),
        PlaceableBundleResource(model_resref, "MDL", mdl_output, f"baked_from:{source_model}"),
        PlaceableBundleResource(model_resref, "MDX", mdx_output, f"baked_from:{source_model}"),
        *_passthrough_custom_resources(asset, resource_reader),
        *_particle_texture_resources(asset.game, effects, resource_reader),
    ]
    by_key: dict[tuple[str, str], PlaceableBundleResource] = {}
    for resource in resources:
        prior = by_key.get(resource.key)
        if prior is not None and prior.data != resource.data:
            raise ValueError(f"Particle bundle collision for {resource.key[0]}.{resource.key[1].lower()}.")
        by_key.setdefault(resource.key, resource)
    texture_keys = tuple(
        resource.key for resource in by_key.values() if resource.key[1] in {"TPC", "TGA", "TXI"}
    )
    return ParticlePlaceableBuild(
        asset=baked_asset,
        utp_result=utp_result,
        resources=tuple(by_key.values()),
        appearance_2da_bytes=merged_2da,
        appearance_id=appearance_id,
        model_resref=model_resref,
        source_model_resref=source_model,
        emitter_count=grafted,
        texture_keys=texture_keys,
        issues=(
            PlaceableBundleIssue(
                "warning",
                "particle_placeable_game_proof_required",
                f"{asset.template_resref} baked and read back with {grafted} emitter(s); a real KOTOR module load remains the final proof.",
                (asset.template_resref, "UTP"),
            ),
        ),
        engine_ready=False,
    )


__all__ = ["ParticlePlaceableBuild", "build_particle_placeable"]
