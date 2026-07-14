"""Non-Qt orchestration for the Placeable Builder product workbench."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from pykotor.resource.formats.gff import GFFContent, read_gff
from pykotor.resource.formats.twoda import read_2da
from pykotor.resource.generics.utp import read_utp

from src.core.placeables.placeable_utp_io import PlaceableUTPExportResult, export_placeable_utp
from src.core.project.placeable_asset import (
    PLACEABLE_ASSET_FILE_SUFFIX,
    PLACEABLE_SCRIPT_HOOKS,
    PlaceableAppearanceMappingEvidence,
    PlaceableAsset,
    PlaceableAssetValidation,
    PlaceableBaseTemplateEvidence,
    PlaceableGameplay,
    load_placeable_asset,
    save_placeable_asset,
    validate_placeable_asset,
)
from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import GameResourceProvider, GameResourceQuery
from src.core.workflow.placeable_builder_service import placeable_library_rows


@dataclass(frozen=True)
class PlaceableBuilderSaveResult:
    ok: bool
    asset: PlaceableAsset
    validation: PlaceableAssetValidation
    sidecar_path: str = ""
    utp_path: str = ""
    utp_result: PlaceableUTPExportResult | None = None
    messages: tuple[str, ...] = ()
    engine_ready: bool = False


def _asset(value: PlaceableAsset | Mapping[str, Any]) -> PlaceableAsset:
    if isinstance(value, PlaceableAsset):
        return PlaceableAsset.from_dict(value.to_dict())
    return PlaceableAsset.from_dict(dict(value or {}))


def _safe_copy_resref(value: str) -> str:
    clean = "".join(char for char in str(value or "").strip().lower() if char.isalnum() or char == "_")
    clean = clean or "placeable"
    suffix = "_copy"
    return f"{clean[: 16 - len(suffix)]}{suffix}"


class PlaceableBuilderToolService:
    """Coordinate documents, providers, UTP output, and evidence without Qt."""

    def __init__(self, library_root: str | Path, *, provider: GameResourceProvider | None = None) -> None:
        self.library_root = Path(library_root)
        self.provider = provider

    def set_library_root(self, root: str | Path) -> None:
        self.library_root = Path(root)

    def set_provider(self, provider: GameResourceProvider | None) -> None:
        self.provider = provider

    def rows(self, *, game: str = "") -> tuple[dict[str, Any], ...]:
        return placeable_library_rows(self.library_root, game=game, provider=self.provider)

    @staticmethod
    def new_asset(*, game: str = "K2") -> PlaceableAsset:
        return PlaceableAsset(game=str(game or "K2").upper())

    @staticmethod
    def clone_asset(value: PlaceableAsset | Mapping[str, Any]) -> PlaceableAsset:
        source = _asset(value)
        data = source.to_dict()
        fresh = PlaceableAsset()
        data["asset_id"] = fresh.asset_id
        data["template_resref"] = _safe_copy_resref(source.template_resref)
        data["tag"] = data["template_resref"]
        data["display_name"] = f"{source.display_name or source.template_resref or 'Placeable'} Copy"
        metadata = dict(data.get("metadata") or {})
        metadata["cloned_from_asset_id"] = source.asset_id
        metadata["cloned_from_template_resref"] = source.template_resref
        data["metadata"] = metadata
        return PlaceableAsset.from_dict(data)

    def _read(self, query: GameResourceQuery | ResourceAddress) -> bytes | None:
        if self.provider is None:
            return None
        try:
            data = self.provider.read_bytes(query)
        except Exception:
            return None
        return bytes(data) if data else None

    def _placeables_2da(self, game: str) -> bytes | None:
        return self._read(GameResourceQuery(game=game, resref="placeables", restype="2DA"))

    def _appearance_model(self, game: str, appearance_id: int | None) -> tuple[str, bytes | None]:
        data = self._placeables_2da(game)
        if data is None or appearance_id is None or appearance_id < 0:
            return "", data
        try:
            table = read_2da(data)
            model = str(table.get_cell(int(appearance_id), "modelname") or "").strip().lower()
        except Exception:
            model = ""
        return ("" if model in {"", "****", "null"} else model), data

    def _base_bytes(self, asset: PlaceableAsset) -> bytes | None:
        if asset.base_template is None:
            return None
        return self._read(asset.base_template)

    def _with_provider_evidence(self, value: PlaceableAsset | Mapping[str, Any]) -> PlaceableAsset:
        asset = _asset(value)
        base_bytes = self._base_bytes(asset)
        if base_bytes:
            try:
                gff = read_gff(base_bytes)
                if gff.content == GFFContent.UTP:
                    asset.base_evidence = PlaceableBaseTemplateEvidence(
                        template=asset.base_template,
                        sha256=sha256(base_bytes).hexdigest(),
                        field_count=len(gff.root),
                        source=asset.base_template.stable_key() if asset.base_template else "",
                    )
            except Exception:
                pass
        model_resref, appearance_bytes = self._appearance_model(asset.game, asset.appearance_id)
        expected_model = model_resref
        if asset.resources.mdl is not None and asset.resources.mdl.resref:
            expected_model = str(asset.resources.mdl.resref).lower()
        if appearance_bytes and model_resref and expected_model == model_resref:
            asset.appearance_evidence = PlaceableAppearanceMappingEvidence(
                game=asset.game,
                appearance_id=asset.appearance_id,
                model_resref=model_resref,
                source=f"{asset.game}:placeables.2da",
                source_sha256=sha256(appearance_bytes).hexdigest(),
                verified=True,
            )
        return asset

    def validate(self, value: PlaceableAsset | Mapping[str, Any]) -> PlaceableAssetValidation:
        return validate_placeable_asset(self._with_provider_evidence(value))

    def load_row(self, row: Mapping[str, Any]) -> PlaceableAsset:
        data = dict(row or {})
        path = str(data.get("path") or "")
        if str(data.get("source") or "") == "placeable_builder" and path:
            return load_placeable_asset(path)
        if self.provider is None:
            raise ValueError("A KOTOR resource provider is required to clone a stock placeable.")
        game = str(data.get("game") or "K2").upper()
        resref = str(data.get("resref") or data.get("template_resref") or "").strip().lower()
        if not resref:
            raise ValueError("The selected library row has no UTP resref.")
        raw = self.provider.read_bytes(GameResourceQuery(game=game, resref=resref, restype="UTP"))
        gff = read_gff(raw)
        if gff.content != GFFContent.UTP:
            raise ValueError(f"{resref}.utp is not a UTP GFF resource.")
        utp = read_utp(raw)
        address_data = dict((data.get("metadata") or {}).get("address") or {})
        base_address = (
            ResourceAddress.from_dict(address_data)
            if address_data
            else ResourceAddress(
                scheme="game_resource",
                game=game,
                layer="base",
                resref=resref,
                restype="UTP",
            )
        )
        gameplay = PlaceableGameplay(
            static=bool(utp.static),
            useable=bool(utp.useable),
            has_inventory=bool(utp.has_inventory),
            inventory_items=[str(item.resref).lower() for item in utp.inventory],
            lockable=bool(utp.lockable),
            locked=bool(utp.locked),
            key_required=bool(utp.key_required),
            key_name=str(utp.key_name or "").lower(),
            auto_remove_key=bool(utp.auto_remove_key),
            unlock_dc=int(utp.unlock_dc),
            lock_dc=int(utp.lock_dc),
            trap_detectable=bool(utp.trap_detectable),
            trap_detect_dc=int(utp.trap_detect_dc),
            trap_disarmable=bool(utp.trap_disarmable),
            trap_disarm_dc=int(utp.trap_disarm_dc),
            trap_flag=int(utp.trap_flag),
            trap_one_shot=bool(utp.trap_one_shot),
            trap_type=int(utp.trap_type),
            maximum_hp=int(utp.maximum_hp),
            current_hp=int(utp.current_hp),
            hardness=int(utp.hardness),
            plot=bool(utp.plot),
            min1_hp=bool(utp.min1_hp),
            not_blastable=bool(utp.not_blastable),
            party_interact=bool(utp.party_interact),
            conversation_resref=str(utp.conversation).lower(),
        )
        scripts = {
            hook: str(getattr(utp, hook)).lower()
            for hook in PLACEABLE_SCRIPT_HOOKS
            if str(getattr(utp, hook))
        }
        asset = PlaceableAsset(
            game=game,
            template_resref=resref,
            tag=str(utp.tag or resref),
            display_name=str(utp.name or resref),
            description=str(utp.description or ""),
            comment=str(utp.comment or ""),
            category=str(data.get("subcategory") or "decor").strip().lower() or "decor",
            visual_source="stock",
            appearance_id=int(utp.appearance_id),
            gameplay=gameplay,
            scripts=scripts,
            base_template=base_address,
            base_evidence=PlaceableBaseTemplateEvidence(
                template=base_address,
                sha256=sha256(raw).hexdigest(),
                field_count=len(gff.root),
                source=str(data.get("source") or base_address.stable_key()),
            ),
            metadata={"cloned_from_stock_utp": resref, "source_library_row": data},
        )
        return self._with_provider_evidence(asset)

    def save(self, value: PlaceableAsset | Mapping[str, Any]) -> PlaceableBuilderSaveResult:
        asset = self._with_provider_evidence(value)
        validation = validate_placeable_asset(asset)
        if not validation.utp_export_ready:
            messages = tuple(issue.message for issue in validation.issues if issue.severity == "blocking")
            return PlaceableBuilderSaveResult(False, asset, validation, messages=messages)
        self.library_root.mkdir(parents=True, exist_ok=True)
        sidecar = self.library_root / f"{asset.template_resref}{PLACEABLE_ASSET_FILE_SUFFIX}"
        utp_path = self.library_root / f"{asset.template_resref}.utp"
        try:
            utp_result = export_placeable_utp(
                asset,
                base_utp_bytes=self._base_bytes(asset),
                appearance_2da_bytes=self._placeables_2da(asset.game),
                output_path=utp_path,
            )
            save_placeable_asset(asset, sidecar)
        except Exception as exc:
            return PlaceableBuilderSaveResult(False, asset, validation, messages=(str(exc),))
        messages = tuple(utp_result.warnings)
        return PlaceableBuilderSaveResult(
            True,
            asset,
            validate_placeable_asset(asset),
            sidecar_path=str(sidecar),
            utp_path=str(utp_path),
            utp_result=utp_result,
            messages=messages,
            engine_ready=False,
        )

    def export_utp(
        self,
        value: PlaceableAsset | Mapping[str, Any],
        output_path: str | Path,
    ) -> PlaceableBuilderSaveResult:
        asset = self._with_provider_evidence(value)
        validation = validate_placeable_asset(asset)
        if not validation.utp_export_ready:
            messages = tuple(issue.message for issue in validation.issues if issue.severity == "blocking")
            return PlaceableBuilderSaveResult(False, asset, validation, messages=messages)
        try:
            result = export_placeable_utp(
                asset,
                base_utp_bytes=self._base_bytes(asset),
                appearance_2da_bytes=self._placeables_2da(asset.game),
                output_path=output_path,
            )
        except Exception as exc:
            return PlaceableBuilderSaveResult(False, asset, validation, messages=(str(exc),))
        return PlaceableBuilderSaveResult(
            True,
            asset,
            validate_placeable_asset(asset),
            utp_path=str(output_path),
            utp_result=result,
            messages=tuple(result.warnings),
            engine_ready=False,
        )

    def preview_model_resref(self, value: PlaceableAsset | Mapping[str, Any]) -> str:
        asset = self._with_provider_evidence(value)
        if asset.resources.mdl is not None and asset.resources.mdl.resref:
            return str(asset.resources.mdl.resref).lower()
        if asset.appearance_evidence and asset.appearance_evidence.model_resref:
            return str(asset.appearance_evidence.model_resref).lower()
        model, _data = self._appearance_model(asset.game, asset.appearance_id)
        return model


__all__ = ["PlaceableBuilderSaveResult", "PlaceableBuilderToolService"]
