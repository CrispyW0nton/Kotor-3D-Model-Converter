"""Read-only native head donor discovery with source provenance.

Core Resources owns discovery and resolution.  This module deliberately does
not parse MDL/MDX bytes or decide whether a model is structurally eligible;
Core Workflow performs that inspection after a user selects a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from src.core.characters.head_builder_project import ResourceView
from src.core.resources.game_resource_provider import (
    GameResourceNotFoundError,
    GameResourceProvider,
    GameResourceQuery,
    GameResourceRecord,
)


_STOCK_LAYERS = frozenset({"base", "module"})
_HEAD_RESREF_PATTERNS = (
    re.compile(r"^p[fm]h[a-z]\d\d$", re.IGNORECASE),
    re.compile(r"^p_[a-z0-9_]+h$", re.IGNORECASE),
    re.compile(r"^[np]_[a-z0-9_]*head[a-z0-9_]*$", re.IGNORECASE),
)


class HeadDonorCatalogError(RuntimeError):
    """Base error for donor discovery and resolution."""


class HeadDonorNotFoundError(HeadDonorCatalogError):
    """Raised when an MDL/MDX donor pair cannot be resolved."""


@dataclass(frozen=True, slots=True)
class HeadDonorCandidate:
    """Lightweight catalog row; no model decode has occurred yet."""

    game: str
    resref: str
    resource_view: ResourceView
    mdl_record: GameResourceRecord
    mdx_record: GameResourceRecord | None
    shadowed_mdl: tuple[GameResourceRecord, ...] = ()
    shadowed_mdx: tuple[GameResourceRecord, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def candidate_id(self) -> str:
        return (
            f"{self.game.upper()}:{self.resref.lower()}:"
            f"{self.resource_view.value}"
        )

    @property
    def complete_pair(self) -> bool:
        return self.mdx_record is not None

    @property
    def stock(self) -> bool:
        records = [
            record
            for record in (self.mdl_record, self.mdx_record)
            if record is not None
        ]
        return bool(records) and all(
            str(record.layer or "").lower() in _STOCK_LAYERS
            for record in records
        )

    @property
    def effective_override(self) -> bool:
        return any(
            str(record.layer or "").lower() == "override"
            for record in (self.mdl_record, self.mdx_record)
            if record is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "game": self.game.upper(),
            "resref": self.resref,
            "resource_view": self.resource_view.value,
            "complete_pair": self.complete_pair,
            "stock": self.stock,
            "effective_override": self.effective_override,
            "mdl": _record_to_dict(self.mdl_record),
            "mdx": (
                _record_to_dict(self.mdx_record)
                if self.mdx_record is not None
                else None
            ),
            "shadowed_mdl": [
                _record_to_dict(record) for record in self.shadowed_mdl
            ],
            "shadowed_mdx": [
                _record_to_dict(record) for record in self.shadowed_mdx
            ],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class HeadDonorResourceBundle:
    """Selected candidate plus immutable source bytes and hashes."""

    candidate: HeadDonorCandidate
    mdl_bytes: bytes = field(repr=False)
    mdx_bytes: bytes = field(repr=False)
    mdl_sha256: str = ""
    mdx_sha256: str = ""

    def __post_init__(self) -> None:
        mdl_bytes = bytes(self.mdl_bytes or b"")
        mdx_bytes = bytes(self.mdx_bytes or b"")
        if not mdl_bytes:
            raise ValueError("A head donor bundle requires nonempty MDL bytes")
        if not mdx_bytes:
            raise ValueError("A head donor bundle requires nonempty MDX bytes")
        object.__setattr__(self, "mdl_bytes", mdl_bytes)
        object.__setattr__(self, "mdx_bytes", mdx_bytes)
        object.__setattr__(
            self,
            "mdl_sha256",
            str(self.mdl_sha256 or _sha256(mdl_bytes)).lower(),
        )
        object.__setattr__(
            self,
            "mdx_sha256",
            str(self.mdx_sha256 or _sha256(mdx_bytes)).lower(),
        )

    def provenance_dict(self) -> dict[str, Any]:
        payload = self.candidate.to_dict()
        payload["mdl_sha256"] = self.mdl_sha256
        payload["mdx_sha256"] = self.mdx_sha256
        payload["mdl_size"] = len(self.mdl_bytes)
        payload["mdx_size"] = len(self.mdx_bytes)
        return payload


class HeadDonorCatalog:
    """Search and resolve installed-game MDL/MDX donor pairs."""

    def __init__(self, provider: GameResourceProvider):
        self.provider = provider

    def search(
        self,
        *,
        game: str,
        resource_view: ResourceView | str = ResourceView.STOCK_ONLY,
        text: str = "",
        limit: int = 250,
        head_like_only: bool = True,
    ) -> list[HeadDonorCandidate]:
        view = ResourceView(resource_view)
        query_text = str(text or "").strip().lower()
        records = self.provider.list_resources(
            GameResourceQuery(game=game, restype="MDL")
        )
        grouped = _group_by_resref(records)
        rows: list[HeadDonorCandidate] = []
        for resref_key, mdl_records in grouped.items():
            display_resref = str(mdl_records[0].resref or resref_key)
            if query_text and query_text not in display_resref.lower():
                continue
            if head_like_only and not looks_like_head_resref(display_resref):
                continue
            try:
                rows.append(
                    self._candidate_from_records(
                        game=game,
                        resref=display_resref,
                        resource_view=view,
                        mdl_records=mdl_records,
                    )
                )
            except HeadDonorNotFoundError:
                continue
        rows.sort(
            key=lambda row: (
                0 if query_text and row.resref.lower() == query_text else 1,
                row.resref.lower(),
                row.candidate_id,
            )
        )
        return rows[: max(0, int(limit))]

    def resolve(
        self,
        *,
        game: str,
        resref: str,
        resource_view: ResourceView | str = ResourceView.STOCK_ONLY,
    ) -> HeadDonorResourceBundle:
        view = ResourceView(resource_view)
        clean_resref = str(resref or "").strip()
        if not clean_resref:
            raise HeadDonorNotFoundError("Head donor resref cannot be blank")
        mdl_records = self.provider.list_resources(
            GameResourceQuery(game=game, resref=clean_resref, restype="MDL")
        )
        candidate = self._candidate_from_records(
            game=game,
            resref=clean_resref,
            resource_view=view,
            mdl_records=mdl_records,
        )
        if candidate.mdx_record is None:
            raise HeadDonorNotFoundError(
                f"Head donor has no {view.value} MDX pair: {game}:{clean_resref}"
            )
        try:
            mdl_result = self.provider.resolve(candidate.mdl_record.address)
            mdx_result = self.provider.resolve(candidate.mdx_record.address)
        except GameResourceNotFoundError as exc:
            raise HeadDonorNotFoundError(
                f"Unable to read donor pair: {game}:{clean_resref}"
            ) from exc
        return HeadDonorResourceBundle(
            candidate=candidate,
            mdl_bytes=mdl_result.data,
            mdx_bytes=mdx_result.data,
        )

    def _candidate_from_records(
        self,
        *,
        game: str,
        resref: str,
        resource_view: ResourceView,
        mdl_records: Iterable[GameResourceRecord],
    ) -> HeadDonorCandidate:
        mdl_candidates = _records_for_view(mdl_records, resource_view)
        if not mdl_candidates:
            raise HeadDonorNotFoundError(
                f"No {resource_view.value} MDL donor found: {game}:{resref}"
            )
        mdl_record = mdl_candidates[0]
        mdx_records = self.provider.list_resources(
            GameResourceQuery(game=game, resref=resref, restype="MDX")
        )
        mdx_candidates = _records_for_view(mdx_records, resource_view)
        mdx_record = mdx_candidates[0] if mdx_candidates else None
        warnings: list[str] = []
        if mdx_record is None:
            warnings.append("MDX pair is missing.")
        elif str(mdl_record.layer or "").lower() != str(
            mdx_record.layer or ""
        ).lower():
            warnings.append(
                "Effective MDL and MDX resolve from different resource layers; "
                "the mixed pair must be explicitly reviewed."
            )
        elif _resource_container_key(mdl_record) != _resource_container_key(
            mdx_record
        ):
            warnings.append(
                "Effective MDL and MDX resolve from different source "
                "containers; the mixed pair must be explicitly reviewed."
            )
        if resource_view is ResourceView.EFFECTIVE_OVERRIDE and any(
            str(record.layer or "").lower() == "override"
            for record in (mdl_record, mdx_record)
            if record is not None
        ):
            warnings.append(
                "Effective Override view selected user-modified donor bytes."
            )
        return HeadDonorCandidate(
            game=str(game or "").upper(),
            resref=str(mdl_record.resref or resref),
            resource_view=resource_view,
            mdl_record=mdl_record,
            mdx_record=mdx_record,
            shadowed_mdl=tuple(mdl_candidates[1:]),
            shadowed_mdx=tuple(mdx_candidates[1:]),
            warnings=tuple(warnings),
        )


def looks_like_head_resref(resref: str) -> bool:
    """Return a cheap discovery hint; structural eligibility is checked later."""

    text = str(resref or "").strip()
    return bool(text and any(pattern.match(text) for pattern in _HEAD_RESREF_PATTERNS))


def _records_for_view(
    records: Iterable[GameResourceRecord],
    view: ResourceView,
) -> list[GameResourceRecord]:
    candidates = list(records)
    if view is ResourceView.STOCK_ONLY:
        candidates = [
            record
            for record in candidates
            if str(record.layer or "").lower() in _STOCK_LAYERS
        ]
    return sorted(
        candidates,
        key=lambda record: (
            -int(record.priority or 0),
            str(record.layer or ""),
            str(record.source or ""),
            str(record.source_path or ""),
        ),
    )


def _group_by_resref(
    records: Iterable[GameResourceRecord],
) -> dict[str, list[GameResourceRecord]]:
    grouped: dict[str, list[GameResourceRecord]] = {}
    for record in records:
        resref = str(record.resref or "").strip()
        if not resref:
            continue
        grouped.setdefault(resref.lower(), []).append(record)
    return grouped


def _record_to_dict(record: GameResourceRecord) -> dict[str, Any]:
    return {
        "address": record.address.to_dict(),
        "size": int(record.size or 0),
        "source": str(record.source or ""),
        "source_path": str(record.source_path or ""),
        "priority": int(record.priority or 0),
        "metadata": dict(record.metadata or {}),
    }


def _resource_container_key(record: GameResourceRecord) -> tuple[str, str, str]:
    layer = str(record.layer or "").strip().lower()
    module_id = str(record.address.module_id or "").strip().lower()
    source_path = str(record.source_path or record.address.path or "").strip()
    if source_path:
        path = Path(source_path)
        container = (
            str(path.parent)
            if layer == "override"
            else str(path)
        )
    else:
        container = str(record.source or "").strip()
    return layer, module_id, container.casefold()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "HeadDonorCatalog",
    "HeadDonorCatalogError",
    "HeadDonorCandidate",
    "HeadDonorNotFoundError",
    "HeadDonorResourceBundle",
    "looks_like_head_resref",
]
