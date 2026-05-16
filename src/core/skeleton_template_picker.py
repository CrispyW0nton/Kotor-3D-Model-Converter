"""
src/core/skeleton_template_picker.py - M12/T1201 skeleton picker service
========================================================================

Qt-free service for the Character Builder's external-mesh launch path.

The picker answers a practical rigging question before any binding happens:
"Which known-good KOTOR skeleton should this imported OBJ/FBX/glTF use?"

Bundled options come from the stripped template manifests under ``templates/``.
Game-install options are accepted as plain dictionaries so the GUI/MCP bridge
can feed in ``ghostrigger_list_game_models`` / model-info results without
coupling this core module to a running MCP transport.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


_VALID_GAMES = {"K1", "K2"}
_VALID_PARTS = {"body", "head", "supermodel", "creature", "unknown"}


@dataclass(frozen=True)
class SkeletonTemplateOption:
    """One selectable skeleton/template source for an imported mesh."""

    key: str
    source: str
    game: str
    part: str
    name: str
    resref: str = ""
    path: str = ""
    exists: bool = True
    size: int = 0
    source_resref: str = ""
    supermodel: str = ""
    classification: str = ""
    node_count: int = 0
    description: str = ""
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkeletonTemplateQueryResult:
    """Result returned by :func:`list_skeleton_templates`."""

    ok: bool = False
    options: List[SkeletonTemplateOption] = field(default_factory=list)
    message: str = ""
    code: str = "ok"
    warnings: List[str] = field(default_factory=list)


def _import_character_builder():  # pragma: no cover - import shim
    try:
        from src.core import character_builder as _cb  # type: ignore
    except ImportError:
        from core import character_builder as _cb      # type: ignore
    return _cb


def _norm_game(game: Optional[str]) -> Optional[str]:
    if game in (None, ""):
        return None
    value = str(game).upper()
    if value in {"1", "KOTOR1", "KOTOR", "KOTORMCP_K1"}:
        return "K1"
    if value in {"2", "TSL", "KOTOR2", "KOTORMCP_K2"}:
        return "K2"
    return value


def _norm_part(part: Optional[str]) -> Optional[str]:
    if part in (None, ""):
        return None
    value = str(part).lower()
    aliases = {
        "headless_body": "body",
        "body_variant": "body",
        "head_shell": "head",
        "mdl": "unknown",
    }
    return aliases.get(value, value)


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _manifest_path_for_template(path: str) -> str:
    p = Path(path)
    return str(p.with_name(f"{p.stem}_manifest.json"))


def _infer_part(resref: str, metadata: Mapping[str, Any]) -> str:
    explicit = _norm_part(str(metadata.get("part", "") or ""))
    if explicit in _VALID_PARTS:
        return explicit

    r = (resref or "").lower()
    if r.startswith(("pfbc", "pmbc", "pfbam", "pmbam")):
        return "body"
    if r.startswith(("pfhc", "pmhc", "p_h")) or "head" in r:
        return "head"
    if r.startswith("s_"):
        return "supermodel"
    if r.startswith("c_"):
        return "creature"
    return "unknown"


def _matches_query(option: SkeletonTemplateOption, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    haystack = " ".join(
        str(v or "").lower()
        for v in (
            option.key,
            option.name,
            option.resref,
            option.source_resref,
            option.part,
            option.supermodel,
            option.description,
        )
    )
    return q in haystack


def _dedupe_options(options: Iterable[SkeletonTemplateOption]) -> List[SkeletonTemplateOption]:
    seen = set()
    out: List[SkeletonTemplateOption] = []
    for opt in options:
        token = (opt.source, opt.game, opt.part, opt.resref.lower(), opt.path.lower())
        if token in seen:
            continue
        seen.add(token)
        out.append(opt)
    return out


def list_bundled_templates(
    *,
    game: Optional[str] = None,
    part: Optional[str] = None,
    query: str = "",
) -> List[SkeletonTemplateOption]:
    """Return bundled skeleton-only templates from ``templates/``."""

    cb = _import_character_builder()
    game_filter = _norm_game(game)
    part_filter = _norm_part(part)
    options: List[SkeletonTemplateOption] = []

    for row in cb.list_template_files():
        row_game = _norm_game(row.get("game")) or ""
        row_part = _norm_part(row.get("part")) or "unknown"
        if game_filter and row_game != game_filter:
            continue
        if part_filter and row_part != part_filter:
            continue

        path = str(row.get("path") or "")
        manifest = _read_json(_manifest_path_for_template(path))
        exists = bool(row.get("exists")) and bool(path) and os.path.isfile(path)
        warnings: List[str] = []
        if not exists:
            warnings.append("Template file is missing.")
        if not manifest:
            warnings.append("Template manifest is missing or unreadable.")

        source_resref = str(manifest.get("source_model") or "").lower()
        name = str(manifest.get("name") or row.get("name") or "")
        option = SkeletonTemplateOption(
            key=f"bundled:{row_game.lower()}:{row_part}",
            source="bundled",
            game=row_game,
            part=row_part,
            name=name,
            resref=name,
            path=path,
            exists=exists,
            size=int(row.get("size") or 0),
            source_resref=source_resref,
            supermodel=str(manifest.get("supermodel") or ""),
            classification=str(manifest.get("classification") or ""),
            node_count=int(manifest.get("node_count") or 0),
            description=str(manifest.get("description") or ""),
            warnings=warnings,
            metadata={"manifest": manifest},
        )
        if _matches_query(option, query):
            options.append(option)

    return options


def build_game_template_options(
    game: str,
    models: Sequence[Mapping[str, Any]],
    *,
    part: Optional[str] = None,
    query: str = "",
    metadata_by_resref: Optional[Mapping[str, Mapping[str, Any]]] = None,
    max_results: int = 50,
) -> List[SkeletonTemplateOption]:
    """Convert game-resource search rows into selectable skeleton options.

    ``models`` is intentionally generic. Rows from MCP typically contain
    ``resref``, ``source`` and ``size``. Optional metadata can add
    ``node_count``, ``supermodel``, ``classification`` and ``part``.
    """

    row_game = _norm_game(game) or ""
    part_filter = _norm_part(part)
    metadata_by_resref = metadata_by_resref or {}
    options: List[SkeletonTemplateOption] = []

    for raw in models:
        resref = str(raw.get("resref") or raw.get("name") or "").lower()
        if not resref:
            continue
        meta = dict(metadata_by_resref.get(resref, {}))
        meta.update({k: v for k, v in raw.items() if k not in meta})
        inferred_part = _infer_part(resref, meta)
        if part_filter and inferred_part != part_filter:
            continue

        warnings: List[str] = []
        if inferred_part == "unknown":
            warnings.append("Could not infer whether this is a body, head, supermodel, or creature skeleton.")
        if not meta.get("node_count"):
            warnings.append("Node count unavailable until the model is inspected.")
        if not meta.get("supermodel"):
            warnings.append("Supermodel unavailable until the model is inspected.")

        option = SkeletonTemplateOption(
            key=f"game:{row_game.lower()}:{resref}:{raw.get('source', 'unknown')}",
            source=str(raw.get("source") or "game"),
            game=row_game,
            part=inferred_part,
            name=resref,
            resref=resref,
            path=str(raw.get("path") or f"installation:{resref}.mdl"),
            exists=True,
            size=int(raw.get("size") or meta.get("size") or 0),
            source_resref=resref,
            supermodel=str(meta.get("supermodel") or ""),
            classification=str(meta.get("classification") or ""),
            node_count=int(meta.get("node_count") or 0),
            description=str(meta.get("description") or ""),
            warnings=warnings,
            metadata=meta,
        )
        if _matches_query(option, query):
            options.append(option)
        if len(options) >= max_results:
            break

    return _dedupe_options(options)


def list_skeleton_templates(
    *,
    game: Optional[str] = None,
    part: Optional[str] = None,
    query: str = "",
    include_bundled: bool = True,
    game_models: Optional[Sequence[Mapping[str, Any]]] = None,
    metadata_by_resref: Optional[Mapping[str, Mapping[str, Any]]] = None,
    max_results: int = 50,
) -> SkeletonTemplateQueryResult:
    """Return skeleton/template options for the external mesh workflow."""

    game_filter = _norm_game(game)
    part_filter = _norm_part(part)
    warnings: List[str] = []

    if game_filter and game_filter not in _VALID_GAMES:
        return SkeletonTemplateQueryResult(
            ok=False,
            message=f"Unknown game '{game}'. Expected K1 or K2.",
            code="invalid_game",
        )
    if part_filter and part_filter not in _VALID_PARTS:
        return SkeletonTemplateQueryResult(
            ok=False,
            message=f"Unknown skeleton part '{part}'.",
            code="invalid_part",
        )

    options: List[SkeletonTemplateOption] = []
    if include_bundled:
        options.extend(
            list_bundled_templates(game=game_filter, part=part_filter, query=query)
        )

    if game_models:
        if not game_filter:
            warnings.append("Game model rows supplied without a game filter; assuming K1.")
            game_filter = "K1"
        options.extend(
            build_game_template_options(
                game_filter,
                game_models,
                part=part_filter,
                query=query,
                metadata_by_resref=metadata_by_resref,
                max_results=max_results,
            )
        )

    options = _dedupe_options(options)[:max_results]
    if not options:
        return SkeletonTemplateQueryResult(
            ok=False,
            options=[],
            message="No skeleton templates matched the current filters.",
            code="empty",
            warnings=warnings,
        )

    return SkeletonTemplateQueryResult(
        ok=True,
        options=options,
        message=f"{len(options)} skeleton template option(s) available.",
        code="ok",
        warnings=warnings,
    )


def option_summary(option: SkeletonTemplateOption) -> str:
    """Compact human-readable label for inspector/dropdown surfaces."""

    bits = [option.game, option.part, option.name]
    if option.supermodel:
        bits.append(f"super={option.supermodel}")
    if option.node_count:
        bits.append(f"{option.node_count} nodes")
    return " / ".join(str(b) for b in bits if b)


__all__ = [
    "SkeletonTemplateOption",
    "SkeletonTemplateQueryResult",
    "build_game_template_options",
    "list_bundled_templates",
    "list_skeleton_templates",
    "option_summary",
]
