"""Select and materialize effective KOTOR animation sets for FBX export.

The FBX writer serializes the animation blocks carried directly by the model
it receives.  KOTOR playback is different: animation names are resolved at
runtime through the requesting model's supermodel chain and inherited
POSITION deltas receive a cumulative ``anim_scale``.  This module bridges the
two contracts without making the IO package depend on animation workflow
policy.

Candidate assembly is deliberate and matches Character Studio: the primary
body's effective clip (local override first, inherited supermodel block
otherwise) supplies body motion, while same-named effective clips from
supplemental models such as an attached head contribute only tracks for nodes
that actually exist in that attachment.  This permits a head with no local
clips to contribute jaw/eye tracks inherited from its own supermodel without
injecting that supermodel's competing pelvis/limb motion. Supplemental names
absent from the body library remain independently selectable.

Names are matched case-insensitively. Selected inherited clips are copied and
their POSITION deltas are baked with the resolved cumulative scale, allowing
the prepared model to use ``anim_scale == 1.0`` for every independent FBX
take. Exact same-named body nodes win when facial tracks are merged.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from .animation_engine import SuperModelResolver
from ..geometry.model_data import Animation, KotorModel


_POSITION_CONTROLLER_TYPE = 8


@dataclass(frozen=True)
class FbxAnimationSetInfo:
    """Immutable metadata for one effective animation available to export."""

    name: str
    source_model_name: str
    source_scope: str
    inherited: bool
    cumulative_scale: float
    length: float
    node_count: int
    event_count: int
    contributing_models: Tuple[str, ...] = ()

    # Concise aliases keep the row convenient for GUI/model-view consumers
    # without weakening the explicit serialized field names above.
    @property
    def source_model(self) -> str:
        return self.source_model_name

    @property
    def scope(self) -> str:
        return self.source_scope

    @property
    def nodes(self) -> int:
        return self.node_count

    @property
    def events(self) -> int:
        return self.event_count


@dataclass(frozen=True)
class _AnimationCandidate:
    row: FbxAnimationSetInfo
    animation: Animation
    supplemental_animations: Tuple[Tuple[str, Animation], ...] = ()
    animation_scale_baked: bool = False


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _is_null_supermodel(resref: Any) -> bool:
    return str(resref or "").strip().lower() in {"", "null", "none"}


def _model_name(model: Any, fallback: str = "") -> str:
    return str(getattr(model, "name", "") or fallback).strip()


def _effective_game(model: KotorModel, game: Any) -> str:
    requested = str(game or "").strip()
    if requested:
        return requested
    stored = getattr(model, "game_version", "")
    return str(getattr(stored, "name", stored) or "K1").strip() or "K1"


def _row_for(
    animation: Animation,
    *,
    source_model_name: str,
    source_scope: str,
    cumulative_scale: float,
) -> FbxAnimationSetInfo:
    source_model_name = str(source_model_name or "").strip()
    return FbxAnimationSetInfo(
        name=str(getattr(animation, "name", "") or "").strip(),
        source_model_name=source_model_name,
        source_scope=str(source_scope or "").strip(),
        inherited=source_scope in {"inherited", "supplemental_inherited"},
        cumulative_scale=_safe_float(cumulative_scale, 1.0) or 1.0,
        length=max(0.0, _safe_float(getattr(animation, "length", 0.0), 0.0)),
        node_count=len(getattr(animation, "nodes", None) or ()),
        event_count=len(getattr(animation, "events", None) or ()),
        contributing_models=(source_model_name,) if source_model_name else (),
    )


def _prime_explicit_base_skeleton(
    model: KotorModel,
    base_skeleton_model: Optional[KotorModel],
    game: str,
) -> KotorModel:
    """Return a shallow lookup proxy whose immediate supermodel is resolvable.

    Character Studio commonly already has the base skeleton model in memory.
    Priming it avoids a second load and also supports composed/export models
    whose transient ``supermodel`` value is NULL.  The input model is never
    changed.
    """

    if base_skeleton_model is None:
        return model

    explicit_name = _model_name(base_skeleton_model)
    requested_ref = str(getattr(model, "supermodel", "") or "").strip()
    lookup_ref = requested_ref if not _is_null_supermodel(requested_ref) else explicit_name

    if explicit_name:
        SuperModelResolver.prime_cache(explicit_name, base_skeleton_model, game)
    if lookup_ref:
        # The caller supplied this model as the primary model's resolved base,
        # so cache it under the actual reference even when its internal name
        # differs in a generated/composed fixture.
        SuperModelResolver.prime_cache(lookup_ref, base_skeleton_model, game)

    if not lookup_ref or requested_ref == lookup_ref:
        return model

    proxy = copy.copy(model)
    proxy.supermodel = lookup_ref
    return proxy


def _animation_node_key(node: Any) -> str:
    return str(getattr(node, "name", "") or "").strip().casefold()


def _animation_event_key(event: Any) -> Tuple[str, float]:
    return (
        str(getattr(event, "name", "") or "").strip().casefold(),
        _safe_float(getattr(event, "time", 0.0), 0.0),
    )


def _with_supplemental_animation(
    candidate: _AnimationCandidate,
    source_model_name: str,
    animation: Animation,
) -> _AnimationCandidate:
    """Attach one same-named facial track source to a body animation set."""

    contributors = list(candidate.row.contributing_models)
    contributor_keys = {name.casefold() for name in contributors}
    if source_model_name and source_model_name.casefold() not in contributor_keys:
        contributors.append(source_model_name)

    animations = [candidate.animation]
    animations.extend(item[1] for item in candidate.supplemental_animations)
    animations.append(animation)
    node_names: set[str] = set()
    event_keys: set[Tuple[str, float]] = set()
    node_count = 0
    event_count = 0
    max_length = 0.0
    for source_animation in animations:
        max_length = max(
            max_length,
            max(0.0, _safe_float(getattr(source_animation, "length", 0.0), 0.0)),
        )
        for node in getattr(source_animation, "nodes", None) or ():
            node_key = _animation_node_key(node)
            if node_key in node_names:
                continue
            node_names.add(node_key)
            node_count += 1
        for event in getattr(source_animation, "events", None) or ():
            event_key = _animation_event_key(event)
            if event_key in event_keys:
                continue
            event_keys.add(event_key)
            event_count += 1

    return _AnimationCandidate(
        row=replace(
            candidate.row,
            length=max_length,
            node_count=node_count,
            event_count=event_count,
            contributing_models=tuple(contributors),
        ),
        animation=candidate.animation,
        supplemental_animations=(
            *candidate.supplemental_animations,
            (source_model_name, animation),
        ),
        animation_scale_baked=candidate.animation_scale_baked,
    )


def _supplemental_node_names(model: KotorModel) -> set[str]:
    """Return attachment-local node names used to isolate facial tracks."""
    try:
        return {
            str(getattr(node, "name", "") or "").strip().casefold()
            for node in model.all_nodes()
            if str(getattr(node, "name", "") or "").strip()
        }
    except Exception:
        return set()


def _head_facial_node_names(model: KotorModel) -> set[str]:
    """Return head-local controls below ``head_g``, excluding the socket bone.

    A BAS head is already socketed to the animated body head. Replaying the
    head supermodel's root/torso/neck tracks on its nested attachment hierarchy
    would double-transform it. Facial controls and rigid inner geometry live
    below ``head_g`` and are the only supplemental tracks the composed export
    needs.
    """
    try:
        nodes = list(model.all_nodes())
    except Exception:
        return set()
    facial_names: set[str] = set()
    for node in nodes:
        if str(getattr(node, "name", "") or "").strip().casefold() != "head_g":
            continue
        pending = list(getattr(node, "children", None) or ())
        visited: set[int] = set()
        while pending:
            child = pending.pop()
            if id(child) in visited:
                continue
            visited.add(id(child))
            name = str(getattr(child, "name", "") or "").strip().casefold()
            if name:
                facial_names.add(name)
            pending.extend(getattr(child, "children", None) or ())
    return facial_names


def _bas_supplemental_animation_contexts(
    primary_model: KotorModel,
    supplemental_model: KotorModel,
) -> tuple[tuple[str, Dict[str, str]], ...]:
    """Resolve BAS slot-specific node renames for one supplemental source."""
    report = getattr(primary_model, "_gr_bas_export_report", None)
    if not isinstance(report, dict):
        return ()
    source_name = _model_name(supplemental_model).casefold()
    contexts: list[tuple[str, Dict[str, str]]] = []
    for layer in report.get("attachment_layers", ()) or ():
        if not isinstance(layer, dict):
            continue
        layer_source = str(layer.get("source_model", "") or "").strip().casefold()
        if source_name and layer_source != source_name:
            continue
        slot = str(layer.get("slot", "") or "attachment").strip().casefold()
        raw_mapping = layer.get("renamed_nodes", {}) or {}
        mapping = {
            str(old_name or "").strip().casefold(): str(new_name or "").strip()
            for old_name, new_name in raw_mapping.items()
            if str(old_name or "").strip() and str(new_name or "").strip()
        }
        contexts.append((slot, mapping))
    return tuple(contexts)


def _primary_owned_node_names(model: KotorModel) -> set[str]:
    """Return body-owned names, excluding tagged BAS attachment subtrees."""
    try:
        nodes = list(model.all_nodes())
    except Exception:
        return set()
    has_tagged_layers = any(
        bool(getattr(node, "_gr_bas_attachment_layer", False))
        for node in nodes
    )
    return {
        str(getattr(node, "name", "") or "").strip().casefold()
        for node in nodes
        if str(getattr(node, "name", "") or "").strip()
        and (
            not has_tagged_layers
            or not bool(getattr(node, "_gr_bas_attachment_layer", False))
        )
    }


def _filtered_supplemental_animation(
    animation: Animation,
    allowed_node_names: set[str],
    cumulative_scale: float,
    *,
    node_name_map: Optional[Dict[str, str]] = None,
    allow_empty: bool = False,
) -> Optional[Animation]:
    """Copy one head/accessory clip, retaining only attachment-owned tracks."""
    filtered = copy.deepcopy(animation)
    nodes = list(getattr(filtered, "nodes", None) or ())
    if allowed_node_names:
        nodes = [node for node in nodes if _animation_node_key(node) in allowed_node_names]
    if not nodes and not allow_empty:
        return None
    if node_name_map:
        for node in nodes:
            replacement = node_name_map.get(_animation_node_key(node))
            if replacement:
                node.name = replacement
    filtered.nodes = nodes
    _bake_position_scale(filtered, cumulative_scale)
    return filtered


def _collect_animation_candidates(
    model: KotorModel,
    *,
    game: str = "",
    resource_manager: Any = None,
    base_skeleton_model: Optional[KotorModel] = None,
    supplemental_models: Sequence[KotorModel] = (),
) -> Dict[str, _AnimationCandidate]:
    game = _effective_game(model, game)
    if resource_manager is not None:
        # Resolver.configure handles manager identity/revision invalidation.
        SuperModelResolver.configure(resource_manager)

    lookup_model = _prime_explicit_base_skeleton(model, base_skeleton_model, game)
    candidates: Dict[str, _AnimationCandidate] = {}

    def add_primary_local(source_model: KotorModel) -> None:
        source_name = _model_name(source_model, _model_name(model))
        for animation in getattr(source_model, "animations", None) or ():
            name = str(getattr(animation, "name", "") or "").strip()
            key = name.casefold()
            if not key or key in candidates:
                continue
            row = _row_for(
                animation,
                source_model_name=source_name,
                source_scope="local",
                cumulative_scale=1.0,
            )
            candidates[key] = _AnimationCandidate(row=row, animation=animation)

    # The primary/body model's effective track is the base of each FBX take.
    # Supplemental facial tracks with the same name are merged later so they
    # cannot hide body motion inherited through a supermodel.
    add_primary_local(model)

    # SuperModelResolver owns strict-game loading, cycle protection, local
    # override semantics, and cumulative anim_scale math.  Local rows from its
    # result are already present and therefore skipped by precedence.
    for name, source_model_name, cumulative_scale in SuperModelResolver.list_all_animations(
        lookup_model,
        game,
    ):
        key = str(name or "").strip().casefold()
        if not key or key in candidates:
            continue
        animation, resolved_scale = SuperModelResolver.resolve_animation(
            lookup_model,
            name,
            game,
        )
        if animation is None:
            continue
        scale = _safe_float(resolved_scale, cumulative_scale)
        row = _row_for(
            animation,
            source_model_name=source_model_name,
            source_scope="inherited",
            cumulative_scale=scale,
        )
        candidates[key] = _AnimationCandidate(row=row, animation=animation)

    # Add effective tracks from attached heads/accessories. A head MDL commonly
    # stores zero clips locally and inherits its jaw/eye tracks. Resolve that
    # chain, then keep only controller nodes present in the attachment's own
    # hierarchy so its supermodel cannot inject competing body locomotion.
    processed_bas_contexts: set[tuple[str, str]] = set()
    for supplemental_model in supplemental_models or ():
        if supplemental_model is None:
            continue
        supplemental_name = _model_name(supplemental_model, _model_name(model))
        bas_contexts = _bas_supplemental_animation_contexts(model, supplemental_model)
        contexts = bas_contexts or (("", {}),)
        for slot, node_name_map in contexts:
            context_key = (supplemental_name.casefold(), slot)
            if bas_contexts and context_key in processed_bas_contexts:
                continue
            if bas_contexts:
                processed_bas_contexts.add(context_key)
            allowed_node_names = _supplemental_node_names(supplemental_model)
            if slot == "head":
                facial_names = _head_facial_node_names(supplemental_model)
                if facial_names:
                    allowed_node_names = facial_names
            for name, source_name, cumulative_scale in SuperModelResolver.list_all_animations(
                supplemental_model,
                game,
            ):
                animation, resolved_scale = SuperModelResolver.resolve_animation(
                    supplemental_model,
                    name,
                    game,
                )
                if animation is None:
                    continue
                filtered_animation = _filtered_supplemental_animation(
                    animation,
                    allowed_node_names,
                    _safe_float(resolved_scale, cumulative_scale),
                    node_name_map=node_name_map,
                    allow_empty=(source_name.casefold() == supplemental_name.casefold()),
                )
                if filtered_animation is None:
                    continue
                name = str(getattr(filtered_animation, "name", "") or name or "").strip()
                key = name.casefold()
                if not key:
                    continue
                existing = candidates.get(key)
                if existing is not None:
                    candidates[key] = _with_supplemental_animation(
                        existing,
                        supplemental_name,
                        filtered_animation,
                    )
                    continue
                row = _row_for(
                    filtered_animation,
                    source_model_name=source_name,
                    source_scope=(
                        "supplemental"
                        if source_name.casefold() == supplemental_name.casefold()
                        else "supplemental_inherited"
                    ),
                    cumulative_scale=_safe_float(resolved_scale, cumulative_scale),
                )
                # The cumulative scale is already baked into the filtered copy.
                candidates[key] = _AnimationCandidate(
                    row=row,
                    animation=filtered_animation,
                    animation_scale_baked=True,
                )

    return candidates


def list_fbx_animation_sets(
    model: KotorModel,
    *,
    game: str = "",
    resource_manager: Any = None,
    base_skeleton_model: Optional[KotorModel] = None,
    supplemental_models: Sequence[KotorModel] = (),
) -> Tuple[FbxAnimationSetInfo, ...]:
    """Return the effective exportable animation inventory.

    The tuple is sorted case-insensitively by display name for deterministic
    dialogs and manifests; selection order is handled independently by
    :func:`prepare_fbx_animation_export_model`.
    """

    candidates = _collect_animation_candidates(
        model,
        game=game,
        resource_manager=resource_manager,
        base_skeleton_model=base_skeleton_model,
        supplemental_models=supplemental_models,
    )
    return tuple(
        candidate.row
        for candidate in sorted(
            candidates.values(),
            key=lambda item: (item.row.name.casefold(), item.row.name),
        )
    )


def _controller_type(controller: Dict[str, Any], fallback: Any = None) -> Optional[int]:
    raw_type = controller.get("type", controller.get("controller_type", fallback))
    try:
        return int(raw_type)
    except (TypeError, ValueError):
        if str(controller.get("name", "") or "").strip().lower() == "position":
            return _POSITION_CONTROLLER_TYPE
        return None


def _scaled_vector(value: Any, scale: float) -> Any:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return value
    try:
        scaled = list(value)
        scaled[0] = float(scaled[0]) * scale
        scaled[1] = float(scaled[1]) * scale
        scaled[2] = float(scaled[2]) * scale
    except (TypeError, ValueError):
        return value
    return tuple(scaled) if isinstance(value, tuple) else scaled


def _scale_controller_values(controller: Dict[str, Any], scale: float) -> None:
    values = controller.get("values")
    if not isinstance(values, (list, tuple)):
        return
    scaled_values = [_scaled_vector(value, scale) for value in values]
    controller["values"] = tuple(scaled_values) if isinstance(values, tuple) else scaled_values


def _bake_position_scale(animation: Animation, cumulative_scale: float) -> None:
    scale = _safe_float(cumulative_scale, 1.0)
    if abs(scale - 1.0) <= 1.0e-12:
        return

    for node in getattr(animation, "nodes", None) or ():
        controllers = getattr(node, "controllers", None)
        if isinstance(controllers, dict):
            # Legacy shape: {controller_type: {"times": ..., "values": ...}}.
            for raw_type, controller in controllers.items():
                if not isinstance(controller, dict):
                    continue
                if _controller_type(controller, raw_type) == _POSITION_CONTROLLER_TYPE:
                    _scale_controller_values(controller, scale)
            continue

        for controller in controllers or ():
            if not isinstance(controller, dict):
                continue
            if _controller_type(controller) == _POSITION_CONTROLLER_TYPE:
                _scale_controller_values(controller, scale)


def _merge_supplemental_tracks(
    animation: Animation,
    supplemental_animations: Sequence[Tuple[str, Animation]],
    primary_owned_node_names: set[str],
) -> None:
    """Merge attachment tracks while preserving actual primary-model nodes.

    A supermodel animation often contains facial tracks even when the body MDL
    has no facial nodes.  Those duplicate track names must be replaced with the
    attached head's independently scaled version.  A duplicate that names a
    node genuinely owned by the primary model remains body-authoritative.
    """

    nodes = list(getattr(animation, "nodes", None) or ())
    node_index = {
        _animation_node_key(node): index
        for index, node in enumerate(nodes)
    }
    events = list(getattr(animation, "events", None) or ())
    event_keys = {_animation_event_key(event) for event in events}

    for _source_model_name, supplemental in supplemental_animations:
        animation.length = max(
            max(0.0, _safe_float(getattr(animation, "length", 0.0), 0.0)),
            max(0.0, _safe_float(getattr(supplemental, "length", 0.0), 0.0)),
        )
        if not str(getattr(animation, "anim_root", "") or "").strip():
            supplemental_root = str(getattr(supplemental, "anim_root", "") or "").strip()
            if supplemental_root:
                animation.anim_root = supplemental_root

        for node in getattr(supplemental, "nodes", None) or ():
            node_key = _animation_node_key(node)
            existing_index = node_index.get(node_key)
            if existing_index is not None:
                if primary_owned_node_names and node_key not in primary_owned_node_names:
                    nodes[existing_index] = copy.deepcopy(node)
                continue
            node_index[node_key] = len(nodes)
            nodes.append(copy.deepcopy(node))

        for event in getattr(supplemental, "events", None) or ():
            event_key = _animation_event_key(event)
            if event_key in event_keys:
                continue
            event_keys.add(event_key)
            events.append(copy.deepcopy(event))

    animation.nodes = nodes
    animation.events = events


def _dedupe_requested_names(selected_animation_names: Iterable[Any]) -> list[str]:
    if isinstance(selected_animation_names, str):
        selected_animation_names = (selected_animation_names,)
    requested: list[str] = []
    seen: set[str] = set()
    for raw_name in selected_animation_names:
        name = str(raw_name or "").strip()
        key = name.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        requested.append(name)
    return requested


def _selection_metadata(
    *,
    requested: Optional[list[str]],
    embedded_candidates: Sequence[_AnimationCandidate],
    missing: Sequence[str],
) -> Dict[str, Any]:
    embedded = [candidate.row.name for candidate in embedded_candidates]
    return {
        "requested": None if requested is None else list(requested),
        "embedded": embedded,
        "missing": list(missing),
        "source_models": {
            candidate.row.name: candidate.row.source_model_name
            for candidate in embedded_candidates
        },
        "source_scopes": {
            candidate.row.name: candidate.row.source_scope
            for candidate in embedded_candidates
        },
        "cumulative_scales": {
            candidate.row.name: candidate.row.cumulative_scale
            for candidate in embedded_candidates
        },
        "contributing_models": {
            candidate.row.name: list(candidate.row.contributing_models)
            for candidate in embedded_candidates
        },
        "sets": [
            {
                "name": candidate.row.name,
                "source_model": candidate.row.source_model_name,
                "scope": candidate.row.source_scope,
                "cumulative_scale": candidate.row.cumulative_scale,
                "length": candidate.row.length,
                "nodes": candidate.row.node_count,
                "events": candidate.row.event_count,
                "contributing_models": list(candidate.row.contributing_models),
            }
            for candidate in embedded_candidates
        ],
    }


def prepare_fbx_animation_export_model(
    model: KotorModel,
    selected_animation_names: Optional[Iterable[str]],
    *,
    game: str = "",
    resource_manager: Any = None,
    base_skeleton_model: Optional[KotorModel] = None,
    supplemental_models: Sequence[KotorModel] = (),
    primary_model: Optional[KotorModel] = None,
    require_all: bool = True,
) -> KotorModel:
    """Deep-copy ``model`` and materialize exactly the requested FBX takes.

    ``selected_animation_names is None`` preserves the model's current local
    animation blocks for API backward compatibility.  An explicit empty
    iterable produces a mesh/rig-only model.  Non-empty selections are
    resolved case-insensitively using the precedence documented above.

    The original model, supplemental models, base skeleton, and their
    animation blocks are never mutated.
    """

    prepared = copy.deepcopy(model)

    if selected_animation_names is None:
        local_candidates = [
            _AnimationCandidate(
                row=_row_for(
                    animation,
                    source_model_name=_model_name(model),
                    source_scope="local",
                    cumulative_scale=1.0,
                ),
                animation=animation,
            )
            for animation in getattr(prepared, "animations", None) or ()
            if str(getattr(animation, "name", "") or "").strip()
        ]
        prepared.anim_scale = 1.0
        prepared._gr_fbx_animation_selection = _selection_metadata(
            requested=None,
            embedded_candidates=local_candidates,
            missing=(),
        )
        return prepared

    requested = _dedupe_requested_names(selected_animation_names)
    if not requested:
        prepared.animations = []
        prepared.anim_scale = 1.0
        prepared._gr_fbx_animation_selection = _selection_metadata(
            requested=[],
            embedded_candidates=(),
            missing=(),
        )
        return prepared

    candidates = _collect_animation_candidates(
        model,
        game=game,
        resource_manager=resource_manager,
        base_skeleton_model=base_skeleton_model,
        supplemental_models=supplemental_models,
    )

    selected_candidates: list[_AnimationCandidate] = []
    missing: list[str] = []
    for requested_name in requested:
        candidate = candidates.get(requested_name.casefold())
        if candidate is None:
            missing.append(requested_name)
        else:
            selected_candidates.append(candidate)

    if missing and require_all:
        plural = "s" if len(missing) != 1 else ""
        raise ValueError(
            f"Unknown FBX animation set{plural}: {', '.join(missing)}"
        )

    materialized: list[Animation] = []
    primary_owned_node_names = (
        _supplemental_node_names(primary_model)
        if primary_model is not None
        else _primary_owned_node_names(model)
    )
    for candidate in selected_candidates:
        animation_copy = copy.deepcopy(candidate.animation)
        if not candidate.animation_scale_baked:
            _bake_position_scale(animation_copy, candidate.row.cumulative_scale)
        _merge_supplemental_tracks(
            animation_copy,
            candidate.supplemental_animations,
            primary_owned_node_names,
        )
        materialized.append(animation_copy)

    prepared.animations = materialized
    # Each selected take now contains its own resolved translation scale.  A
    # single model-level scale cannot represent mixed local/inherited clips.
    prepared.anim_scale = 1.0
    prepared._gr_fbx_animation_selection = _selection_metadata(
        requested=requested,
        embedded_candidates=selected_candidates,
        missing=missing,
    )
    return prepared


__all__ = [
    "FbxAnimationSetInfo",
    "list_fbx_animation_sets",
    "prepare_fbx_animation_export_model",
]
