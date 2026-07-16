"""Head model resolution helpers for Body Attachment System previews."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


_RESOURCE_SENTINELS = {"", "****", "none", "null"}


@dataclass(frozen=True)
class BasHeadResolution:
    requested_resref: str = ""
    resolved_resref: str = ""
    source: str = ""
    candidates: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)


def normalize_bas_model_resref(value: object) -> str:
    """Return a lowercase model resref from UI text, labels, paths, or game tags."""

    text = str(value or "").strip().strip("\"'")
    if not text:
        return ""
    text = text.replace("\\", "/")
    if "/" in text:
        text = Path(text).stem
    if ":" in text and re.match(r"^[A-Za-z0-9_]+:", text):
        text = text.rsplit(":", 1)[-1].strip()
    for suffix in (".mdl", ".mdx", ".json"):
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)]
            break

    hyphen_tail = text.rsplit(" - ", 1)[-1].strip()
    if hyphen_tail and hyphen_tail != text and _looks_like_resref(hyphen_tail):
        text = hyphen_tail
    else:
        tokens = re.findall(r"[A-Za-z0-9_]{3,32}", text)
        for token in reversed(tokens):
            if _looks_like_resref(token):
                text = token
                break

    text = re.sub(r"[^A-Za-z0-9_]+", "", text).lower()
    return "" if text in _RESOURCE_SENTINELS else text


def resolve_bas_head_resref(
    *,
    requested: object = "",
    body_model: Any = None,
    body_resref: object = "",
    manager: Any = None,
    game: str = "K1",
) -> BasHeadResolution:
    """Resolve the head resref BAS should load for a head attachment.

    Explicit user requests always win when they name an available model.  If no
    direct head request is available, the resolver tries appearance.2da/heads.2da
    and then conservative body-name candidates such as ``p_carthbbh``.
    """

    game_tag = str(game or "K1").strip().upper() or "K1"
    requested_resref = normalize_bas_model_resref(requested)
    candidates: list[str] = []
    warnings: list[str] = []

    if requested_resref:
        candidates.append(requested_resref)
        if _model_exists(manager, requested_resref, game_tag) or manager is None:
            return BasHeadResolution(
                requested_resref=requested_resref,
                resolved_resref=requested_resref,
                source="requested",
                candidates=tuple(_dedupe(candidates)),
            )
        warnings.append(f"requested head '{requested_resref}' was not found in {game_tag}")

    body_key = normalize_bas_model_resref(body_resref or getattr(body_model, "_gr_source_resref", "") or getattr(body_model, "name", ""))
    table_head = _resolve_head_from_appearance_tables(manager, body_key, game_tag)
    if table_head:
        candidates.append(table_head)
        if _model_exists(manager, table_head, game_tag) or manager is None:
            return BasHeadResolution(
                requested_resref=requested_resref,
                resolved_resref=table_head,
                source="appearance_2da",
                candidates=tuple(_dedupe(candidates)),
                warnings=tuple(warnings),
            )

    for candidate in _body_name_head_candidates(body_key):
        candidates.append(candidate)
        if _model_exists(manager, candidate, game_tag) or manager is None:
            return BasHeadResolution(
                requested_resref=requested_resref,
                resolved_resref=candidate,
                source="body_resref",
                candidates=tuple(_dedupe(candidates)),
                warnings=tuple(warnings),
            )

    return BasHeadResolution(
        requested_resref=requested_resref,
        resolved_resref=requested_resref,
        source="unresolved_requested" if requested_resref else "unresolved",
        candidates=tuple(_dedupe(candidates)),
        warnings=tuple(warnings),
    )


def _looks_like_resref(value: str) -> bool:
    text = str(value or "").strip().lower()
    if text in _RESOURCE_SENTINELS:
        return False
    if len(text) > 16:
        return False
    return bool(re.match(r"^[a-z0-9_]+$", text))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_bas_model_resref(value)
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _model_exists(manager: Any, resref: str, game: str) -> bool:
    res = normalize_bas_model_resref(resref)
    if not res or manager is None:
        return False
    try:
        if hasattr(manager, "get_strict"):
            from src.core.assets.resource_manager import RES_MDL

            if manager.get_strict(res, RES_MDL, game) is not None:
                return True
        elif hasattr(manager, "get_mdl") and manager.get_mdl(res, game) is not None:
            return True
    except Exception:
        pass
    try:
        inst = manager.get_k1() if game == "K1" and hasattr(manager, "get_k1") else manager.get_k2() if hasattr(manager, "get_k2") else None
        if inst is not None and hasattr(inst, "has"):
            from src.core.assets.resource_manager import RES_MDL

            return bool(inst.has(res, RES_MDL))
    except Exception:
        pass
    try:
        return any(str(name).lower() == res and str(tag).upper() == game for name, tag in manager.list_models(game))
    except Exception:
        return False


def _resolve_head_from_appearance_tables(manager: Any, body_resref: str, game: str) -> str:
    if manager is None or not body_resref:
        return ""
    try:
        from src.core.assets.resource_manager import RES_2DA
        from src.core.templates.twoda import TwoDA

        getter = manager.get_strict if hasattr(manager, "get_strict") else manager.get
        appearance_bytes = getter("appearance", RES_2DA, game)
        heads_bytes = getter("heads", RES_2DA, game)
        if not appearance_bytes or not heads_bytes:
            return ""
        appearance = TwoDA.from_bytes(appearance_bytes, name="appearance")
        heads = TwoDA.from_bytes(heads_bytes, name="heads")
        model_columns = [col for col in appearance.columns if col.lower().startswith("model")]
        for row in appearance:
            if not any(normalize_bas_model_resref(row.get(col, "")) == body_resref for col in model_columns):
                continue
            normalhead = str(row.get("normalhead", "") or "").strip()
            if not normalhead or normalhead == "****":
                continue
            try:
                head_index = int(float(normalhead))
            except Exception:
                continue
            if head_index < 0 or head_index >= len(heads):
                continue
            head = normalize_bas_model_resref(heads[head_index].get("head", ""))
            if head:
                return head
    except Exception:
        return ""
    return ""


def _body_name_head_candidates(body_resref: str) -> tuple[str, ...]:
    body = normalize_bas_model_resref(body_resref)
    if not body:
        return ()
    candidates = [f"{body}h"]
    if body.startswith("p_"):
        candidates.append(f"{body[:-2]}h" if len(body) > 2 and body[-2:].isalpha() else f"{body}h")
    if body.endswith(("ba", "bb", "bc", "bd", "be")) and len(body) > 2:
        candidates.append(f"{body[:-2]}h")
    if body.endswith(("a", "b", "c", "d", "e")) and len(body) > 1:
        candidates.append(f"{body[:-1]}h")
    return tuple(_dedupe(candidates))
