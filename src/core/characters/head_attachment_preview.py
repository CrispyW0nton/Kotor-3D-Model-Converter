"""Renderer-neutral attachment and inherited-animation preview contracts.

KOTOR keeps a modular head and body as independent models.  The body owns an
exact ``headhook`` node and both models evaluate the same supermodel chain.
This module builds a disposable combined viewport copy while preserving those
runtime semantics in the durable report: no body clips are copied into the
head and the export candidate is never mutated.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Callable, Iterable


_NULL_REFS = frozenset({"", "null", "none"})
_FACIAL_TOKENS = (
    "brow",
    "eye",
    "jaw",
    "lid",
    "lip",
    "mouth",
    "teeth",
    "tongue",
)


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_name(model: Any) -> str:
    return str(getattr(model, "name", "") or "")


def _supermodel(model: Any) -> str:
    value = str(getattr(model, "supermodel", "") or "").strip()
    return "" if value.casefold() in _NULL_REFS else value


def _model_nodes(model: Any) -> list[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        return []


def _animation_names(model: Any) -> tuple[str, ...]:
    return tuple(
        str(getattr(animation, "name", "") or "")
        for animation in list(getattr(model, "animations", ()) or ())
        if str(getattr(animation, "name", "") or "")
    )


def _node_path(node: Any) -> str:
    parts: list[str] = []
    visited: set[int] = set()
    current = node
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        name = str(getattr(current, "name", "") or "")
        if name:
            parts.append(name)
        current = getattr(current, "parent", None)
    return "/".join(reversed(parts))


def _world_position(node: Any) -> tuple[float, float, float]:
    position = [0.0, 0.0, 0.0]
    visited: set[int] = set()
    current = node
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = tuple(
            getattr(current, "position", (0.0, 0.0, 0.0))
            or (0.0, 0.0, 0.0)
        )
        if len(value) >= 3:
            position[0] += float(value[0])
            position[1] += float(value[1])
            position[2] += float(value[2])
        current = getattr(current, "parent", None)
    return (position[0], position[1], position[2])


def _find_exact_headhook(model: Any) -> Any | None:
    matches = [
        node
        for node in _model_nodes(model)
        if str(getattr(node, "name", "") or "").casefold() == "headhook"
    ]
    return matches[0] if len(matches) == 1 else None


def _first_root(model: Any) -> Any | None:
    root = getattr(model, "root_node", None)
    if root is not None:
        return root
    for node in _model_nodes(model):
        if getattr(node, "parent", None) is None:
            return node
    return None


def _is_facial_node(name: str) -> bool:
    key = str(name or "").casefold()
    return key.startswith("f_") or any(token in key for token in _FACIAL_TOKENS)


@dataclass(frozen=True, slots=True)
class HeadPreviewAnimation:
    """One effective animation available through the head supermodel chain."""

    name: str
    source_model: str
    source_scope: str
    cumulative_scale: float
    length: float
    target_node_count: int
    head_target_names: tuple[str, ...] = ()
    facial_target_names: tuple[str, ...] = ()

    @property
    def facial(self) -> bool:
        return bool(self.facial_target_names)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_model": self.source_model,
            "source_scope": self.source_scope,
            "cumulative_scale": self.cumulative_scale,
            "length": self.length,
            "target_node_count": self.target_node_count,
            "head_target_names": list(self.head_target_names),
            "facial_target_names": list(self.facial_target_names),
            "facial": self.facial,
        }


@dataclass(frozen=True, slots=True)
class HeadAttachmentPreviewReport:
    """Structural proof for a disposable body/head preview."""

    accepted: bool
    game: str
    body_resref: str
    head_resref: str
    body_supermodel: str
    head_supermodel: str
    headhook_node_path: str
    headhook_world_position: tuple[float, float, float]
    head_root_name: str
    source_head_parent_name: str
    preview_head_parent_name: str
    source_head_local_animation_names: tuple[str, ...]
    preview_head_local_animation_names: tuple[str, ...]
    effective_animations: tuple[HeadPreviewAnimation, ...]
    selected_animation_names: tuple[str, ...]
    facial_animation_names: tuple[str, ...]
    supermodel_chain: tuple[str, ...]
    blocking_issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contract_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.contract_sha256:
            payload = self.to_dict()
            payload["contract_sha256"] = ""
            object.__setattr__(
                self,
                "contract_sha256",
                _canonical_sha256(payload),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "game": self.game,
            "body_resref": self.body_resref,
            "head_resref": self.head_resref,
            "body_supermodel": self.body_supermodel,
            "head_supermodel": self.head_supermodel,
            "headhook_node_path": self.headhook_node_path,
            "headhook_world_position": list(self.headhook_world_position),
            "head_root_name": self.head_root_name,
            "source_head_parent_name": self.source_head_parent_name,
            "preview_head_parent_name": self.preview_head_parent_name,
            "source_head_local_animation_names": list(
                self.source_head_local_animation_names
            ),
            "preview_head_local_animation_names": list(
                self.preview_head_local_animation_names
            ),
            "effective_animations": [
                row.to_dict() for row in self.effective_animations
            ],
            "selected_animation_names": list(self.selected_animation_names),
            "facial_animation_names": list(self.facial_animation_names),
            "supermodel_chain": list(self.supermodel_chain),
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "contract_sha256": self.contract_sha256,
        }


@dataclass(frozen=True, slots=True)
class HeadAttachmentPreviewResult:
    """Models plus the immutable attachment-preview report."""

    body_model: Any = field(repr=False, compare=False)
    head_model: Any = field(repr=False, compare=False)
    preview_model: Any = field(repr=False, compare=False)
    report: HeadAttachmentPreviewReport


SupermodelLoader = Callable[[str], Any | None]


def _walk_supermodels(
    head_model: Any,
    loader: SupermodelLoader,
) -> tuple[list[Any], list[str], list[str]]:
    models = [head_model]
    chain: list[str] = []
    issues: list[str] = []
    visited = {_model_name(head_model).casefold()}
    super_ref = _supermodel(head_model)
    while super_ref:
        key = super_ref.casefold()
        if key in visited:
            issues.append(
                f"Supermodel chain cycles at '{super_ref}'."
            )
            break
        visited.add(key)
        inherited = loader(super_ref)
        if inherited is None:
            issues.append(
                f"Supermodel '{super_ref}' could not be resolved for preview."
            )
            break
        models.append(inherited)
        chain.append(_model_name(inherited) or super_ref)
        super_ref = _supermodel(inherited)
    return models, chain, issues


def _effective_animations(
    models: Iterable[Any],
    head_node_names: set[str],
) -> tuple[HeadPreviewAnimation, ...]:
    rows: dict[str, HeadPreviewAnimation] = {}
    cumulative_scale = 1.0
    for model_index, model in enumerate(models):
        source_name = _model_name(model)
        for animation in list(getattr(model, "animations", ()) or ()):
            name = str(getattr(animation, "name", "") or "")
            key = name.casefold()
            if not name or key in rows:
                continue
            target_names = tuple(
                str(getattr(node, "name", "") or "")
                for node in list(getattr(animation, "nodes", ()) or ())
                if str(getattr(node, "name", "") or "")
            )
            head_targets = tuple(
                sorted(
                    {
                        target
                        for target in target_names
                        if target.casefold() in head_node_names
                    },
                    key=str.casefold,
                )
            )
            facial_targets = tuple(
                target for target in head_targets if _is_facial_node(target)
            )
            rows[key] = HeadPreviewAnimation(
                name=name,
                source_model=source_name,
                source_scope=("local" if model_index == 0 else "inherited"),
                cumulative_scale=cumulative_scale,
                length=float(getattr(animation, "length", 0.0) or 0.0),
                target_node_count=len(target_names),
                head_target_names=head_targets,
                facial_target_names=facial_targets,
            )
        step_scale = float(getattr(model, "anim_scale", 1.0) or 1.0)
        cumulative_scale *= step_scale
    return tuple(
        sorted(rows.values(), key=lambda row: (row.name.casefold(), row.name))
    )


def _select_animations(
    effective: tuple[HeadPreviewAnimation, ...],
    requested: Iterable[str],
) -> tuple[tuple[str, ...], list[str]]:
    by_name = {row.name.casefold(): row for row in effective}
    selected: list[str] = []
    missing: list[str] = []
    for raw_name in requested:
        name = str(raw_name or "").strip()
        if not name:
            continue
        row = by_name.get(name.casefold())
        if row is None:
            missing.append(name)
        elif row.name.casefold() not in {
            value.casefold() for value in selected
        }:
            selected.append(row.name)
    return tuple(selected), missing


def build_head_attachment_preview(
    *,
    body_model: Any,
    head_model: Any,
    game: str,
    body_resref: str = "",
    head_resref: str = "",
    supermodel_loader: SupermodelLoader,
    selected_animation_names: Iterable[str] = (
        "tlknorm",
        "talk",
        "listen",
        "walk",
    ),
) -> HeadAttachmentPreviewResult:
    """Build an exact-headhook preview without mutating either source model."""

    blocking: list[str] = []
    warnings: list[str] = []
    source_head_root = _first_root(head_model)
    source_parent = (
        str(getattr(getattr(source_head_root, "parent", None), "name", "") or "")
        if source_head_root is not None
        else ""
    )
    body_supermodel = _supermodel(body_model)
    head_supermodel = _supermodel(head_model)
    if not body_supermodel:
        blocking.append("The preview body has no supermodel reference.")
    if not head_supermodel:
        blocking.append("The head has no supermodel reference.")
    if (
        body_supermodel
        and head_supermodel
        and body_supermodel.casefold() != head_supermodel.casefold()
    ):
        blocking.append(
            "Body/head supermodel mismatch: "
            f"body='{body_supermodel}', head='{head_supermodel}'."
        )

    body_copy = deepcopy(body_model)
    head_copy = deepcopy(head_model)
    hook = _find_exact_headhook(body_copy)
    head_root = _first_root(head_copy)
    if hook is None:
        blocking.append(
            "The preview body must contain exactly one node named 'headhook'."
        )
    if head_root is None:
        blocking.append("The head has no attachable root node.")

    if hook is not None and head_root is not None:
        children = getattr(hook, "children", None)
        if children is None:
            hook.children = []
            children = hook.children
        head_root.parent = hook
        children.append(head_root)
        for node in _model_nodes(head_copy):
            setattr(node, "_gr_head_builder_attachment_layer", True)
            setattr(node, "_gr_head_builder_attachment_root_ref", head_root)
        setattr(head_root, "_gr_head_builder_attachment_root", True)
        setattr(head_root, "_gr_head_builder_attachment_slot", "head")

    models, chain, chain_issues = _walk_supermodels(
        head_model,
        supermodel_loader,
    )
    blocking.extend(chain_issues)
    head_node_names = {
        str(getattr(node, "name", "") or "").casefold()
        for node in _model_nodes(head_model)
        if str(getattr(node, "name", "") or "")
    }
    effective = _effective_animations(models, head_node_names)
    selected, missing = _select_animations(
        effective,
        selected_animation_names,
    )
    if missing:
        warnings.append(
            "Requested preview animations were unavailable: "
            + ", ".join(missing)
            + "."
        )
    facial_names = tuple(row.name for row in effective if row.facial)
    if not effective:
        blocking.append(
            "The head and its supermodel chain expose no animations."
        )
    if not facial_names:
        blocking.append(
            "No effective animation targets facial nodes owned by the head."
        )
    selected_keys = {name.casefold() for name in selected}
    if selected and not any(
        row.facial and row.name.casefold() in selected_keys for row in effective
    ):
        warnings.append(
            "The selected preview set contains no facial-targeting clip."
        )

    source_local = _animation_names(head_model)
    preview_local = _animation_names(head_copy)
    if source_local != preview_local:
        blocking.append(
            "Preview construction changed the head's local animation inventory."
        )
    preview_parent = (
        str(getattr(getattr(head_root, "parent", None), "name", "") or "")
        if head_root is not None
        else ""
    )
    if hook is not None and preview_parent.casefold() != "headhook":
        blocking.append("The preview head root was not parented to headhook.")

    report = HeadAttachmentPreviewReport(
        accepted=not blocking,
        game=str(game or "").upper(),
        body_resref=str(body_resref or _model_name(body_model)),
        head_resref=str(head_resref or _model_name(head_model)),
        body_supermodel=body_supermodel,
        head_supermodel=head_supermodel,
        headhook_node_path=_node_path(hook) if hook is not None else "",
        headhook_world_position=(
            _world_position(hook) if hook is not None else (0.0, 0.0, 0.0)
        ),
        head_root_name=(
            str(getattr(head_root, "name", "") or "")
            if head_root is not None
            else ""
        ),
        source_head_parent_name=source_parent,
        preview_head_parent_name=preview_parent,
        source_head_local_animation_names=source_local,
        preview_head_local_animation_names=preview_local,
        effective_animations=effective,
        selected_animation_names=selected,
        facial_animation_names=facial_names,
        supermodel_chain=tuple(chain),
        blocking_issues=tuple(blocking),
        warnings=tuple(warnings),
    )
    return HeadAttachmentPreviewResult(
        body_model=body_copy,
        head_model=head_copy,
        preview_model=body_copy,
        report=report,
    )


__all__ = [
    "HeadAttachmentPreviewReport",
    "HeadAttachmentPreviewResult",
    "HeadPreviewAnimation",
    "SupermodelLoader",
    "build_head_attachment_preview",
]
