"""Read-only discovery rows for stock and authored placeable templates."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from src.core.project.placeable_asset import (
    PLACEABLE_ASSET_FILE_SUFFIX,
    PlaceableAsset,
    load_placeable_asset,
    validate_placeable_asset,
)

from .game_resource_provider import GameResourceProvider, GameResourceQuery


@dataclass(frozen=True)
class PlaceableLibraryRow:
    """Map Studio-compatible interactive template row with provenance."""

    game: str
    resref: str
    label: str
    category: str = "Placeables"
    subcategory: str = ""
    source: str = ""
    asset_id: str = ""
    path: str = ""
    confidence: str = "template"
    warning: str = ""
    structural_evidence: bool = False
    engine_ready: bool = False
    priority: int = 0
    restype: str = "UTP"
    kind: str = "placeable"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "resref": self.resref,
            "template_resref": self.resref,
            "restype": self.restype.lower(),
            "resource_type": self.restype.upper(),
            "kind": self.kind,
            "label": self.label,
            "category": self.category,
            "subcategory": self.subcategory,
            "source": self.source,
            "asset_id": self.asset_id,
            "path": self.path,
            "confidence": self.confidence,
            "warning": self.warning,
            "structural_evidence": bool(self.structural_evidence),
            "engine_ready": False,
            "metadata": dict(self.metadata),
        }


def placeable_library_row_from_asset(asset: PlaceableAsset, *, path: str = "") -> PlaceableLibraryRow:
    validation = validate_placeable_asset(asset)
    messages = [issue.message for issue in validation.issues if issue.severity in {"blocking", "warning"}]
    warning = " ".join(messages[:3])
    label = asset.display_name.strip() or asset.template_resref
    return PlaceableLibraryRow(
        game=asset.game,
        resref=asset.template_resref.lower(),
        label=f"{asset.game}: {label} ({asset.template_resref.lower()})",
        category="Placeables",
        subcategory=asset.category.title(),
        source="placeable_builder",
        asset_id=asset.asset_id,
        path=str(path or ""),
        confidence="authored_structural" if validation.structural_evidence_ready else "authored_unproven",
        warning=warning,
        structural_evidence=validation.structural_evidence_ready,
        engine_ready=False,
        priority=200,
        metadata={
            "visual_source": asset.visual_source,
            "appearance_id": asset.appearance_id,
            "document_valid": validation.document_valid,
            "utp_export_ready": validation.utp_export_ready,
            "structural_evidence_ready": validation.structural_evidence_ready,
            "engine_ready": False,
        },
    )


def _discover_asset_rows(roots: Iterable[str | Path]) -> list[PlaceableLibraryRow]:
    rows: list[PlaceableLibraryRow] = []
    seen_paths: set[str] = set()
    for root_value in roots:
        root = Path(root_value)
        candidates = [root] if root.is_file() else sorted(root.rglob(f"*{PLACEABLE_ASSET_FILE_SUFFIX}")) if root.exists() else []
        for path in candidates:
            key = str(path.resolve()).lower()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                rows.append(placeable_library_row_from_asset(load_placeable_asset(path), path=str(path)))
            except Exception as exc:
                rows.append(
                    PlaceableLibraryRow(
                        game="",
                        resref=path.name[: -len(PLACEABLE_ASSET_FILE_SUFFIX)].lower(),
                        label=f"Invalid placeable asset: {path.name}",
                        source="placeable_builder",
                        path=str(path),
                        confidence="invalid",
                        warning=str(exc),
                        priority=200,
                        metadata={"document_valid": False, "engine_ready": False},
                    )
                )
    return rows


def _discover_provider_rows(provider: GameResourceProvider | None, *, game: str = "") -> list[PlaceableLibraryRow]:
    if provider is None:
        return []
    rows: list[PlaceableLibraryRow] = []
    for restype, kind, category, subcategory in (
        ("UTP", "placeable", "Placeables", ""),
        ("UTD", "door", "Placeables", "Animated Doors"),
    ):
        query = GameResourceQuery(game=game or None, restype=restype)
        for record in provider.list_resources(query):
            resref = str(record.resref or "").lower()
            if not resref:
                continue
            row_game = str(record.address.game or game or "").upper()
            rows.append(
                PlaceableLibraryRow(
                    game=row_game,
                    resref=resref,
                    label=f"{row_game + ': ' if row_game else ''}{resref}",
                    category=category,
                    subcategory=subcategory,
                    source=record.source or record.address.layer or "game_resource",
                    path=str(record.source_path or record.address.path or ""),
                    confidence="stock_template",
                    warning=(
                        f"{restype} discovered; template structure and in-game behavior are not proven by discovery alone."
                    ),
                    structural_evidence=False,
                    engine_ready=False,
                    priority=int(record.priority or 0),
                    restype=restype,
                    kind=kind,
                    metadata={
                        "address": record.address.to_dict(),
                        "size": record.size,
                        "provider_priority": record.priority,
                        "engine_ready": False,
                    },
                )
            )
    return rows


def discover_placeable_library(
    *,
    asset_roots: Iterable[str | Path] = (),
    provider: GameResourceProvider | None = None,
    game: str = "",
) -> tuple[PlaceableLibraryRow, ...]:
    """Discover project assets and canonical provider UTP records.

    Duplicate game/resref rows are resolved by priority; shadowing is retained
    as metadata so callers never silently mistake a project override for stock.
    """

    wanted_game = str(game or "").upper()
    candidates = _discover_provider_rows(provider, game=wanted_game) + _discover_asset_rows(asset_roots)
    chosen: dict[tuple[str, str, str], PlaceableLibraryRow] = {}
    shadowed: dict[tuple[str, str, str], list[PlaceableLibraryRow]] = {}
    for row in sorted(candidates, key=lambda item: (-item.priority, item.path.lower(), item.source.lower())):
        if wanted_game and row.game and row.game != wanted_game:
            continue
        key = (row.game, row.resref.lower(), row.restype.upper())
        if key in chosen:
            shadowed.setdefault(key, []).append(row)
            continue
        chosen[key] = row
    for key, hidden in shadowed.items():
        row = chosen[key]
        metadata = dict(row.metadata)
        metadata["shadowed"] = [value.to_dict() for value in hidden]
        chosen[key] = replace(row, metadata=metadata)
    return tuple(sorted(chosen.values(), key=lambda item: (item.game, item.kind, item.subcategory, item.resref)))


def discover_placeable_library_rows(**kwargs: Any) -> tuple[dict[str, Any], ...]:
    """Return dictionaries accepted by Map Studio's gameplay palette."""

    return tuple(row.to_dict() for row in discover_placeable_library(**kwargs))


__all__ = [
    "PlaceableLibraryRow",
    "discover_placeable_library",
    "discover_placeable_library_rows",
    "placeable_library_row_from_asset",
]
