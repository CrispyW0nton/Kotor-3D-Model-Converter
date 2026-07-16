"""Bounded creature planning for Map Studio Play in Editor.

This module deliberately stops at the editor-safe boundary.  It resolves the
real body/head model recipe for every authored UTC placement and projects the
small behavior subset PIE can represent honestly: idle animation,
walkmesh-bounded free-roam *intent*, and a relationship marker.  It never
executes NCS, starts DLG conversations, or fabricates Odyssey combat/AI state.

The resulting plan is immutable and does not mutate KMAP placement data,
source UTC resources, or model resources.  A GUI/runtime adapter may consume
the recipes with ``build_bas_preview_model`` and the retained PIE actor API.
Export plus a manual ``warp plcaa`` remains the engine proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Iterable


Vec3 = tuple[float, float, float]
UTCReader = Callable[[str, str], bytes | None]


PIE_CREATURE_RUNTIME_LIMITATIONS: tuple[str, ...] = (
    "PIE does not execute NWScript/NCS event handlers or Odyssey action queues.",
    "PIE does not run DLG conversations, quests, cutscenes, perception, faction AI, or combat.",
    "A hostile relationship is an editor marker only; it does not make the creature attack.",
    "Free-roam is only an editor intent until a caller supplies deterministic walkmesh routing.",
    "Export and a manual warp to plcaa remain the authoritative KOTOR runtime proof.",
)


_UTC_SCRIPT_FIELDS: tuple[tuple[str, str], ...] = (
    ("on_spawn", "spawn"),
    ("on_heartbeat", "heartbeat"),
    ("on_notice", "notice"),
    ("on_dialog", "dialog"),
    ("on_end_dialog", "end_dialog"),
    ("on_attacked", "attacked"),
    ("on_damaged", "damaged"),
    ("on_death", "death"),
    ("on_blocked", "blocked"),
    ("on_disturbed", "disturbed"),
    ("on_end_round", "end_round"),
    ("on_rested", "rested"),
    ("on_spell", "spell"),
    ("on_user_defined", "user_defined"),
)


@dataclass(frozen=True)
class MapStudioPIECreatureRenderRecipe:
    """One retained Odyssey actor recipe resolved from a UTC placement."""

    actor_id: str
    body_model_resref: str
    head_model_resref: str = ""
    body_texture_resref: str = ""
    visible_in_game: bool = True
    animation_candidates: tuple[str, ...] = ("pause1", "walk", "run")

    @property
    def can_build_actor(self) -> bool:
        return bool(self.visible_in_game and self.body_model_resref)

    @property
    def attachment_model_resrefs(self) -> tuple[tuple[str, str], ...]:
        if not self.head_model_resref:
            return ()
        return (("head", self.head_model_resref),)


@dataclass(frozen=True)
class MapStudioPIECreatureBehaviorState:
    """Editor-safe behavior projection; never an Odyssey runtime claim."""

    locomotion: str
    relationship: str
    relationship_marker: str
    faction_id: int | None
    conversation_resref: str
    script_events: tuple[tuple[str, str], ...]
    authored_behavior: bool
    scripts_suppressed: bool
    conversation_suppressed: bool
    exact_runtime_parity: bool = False


@dataclass(frozen=True)
class MapStudioPIECreatureSpec:
    """Resolved actor and bounded behavior for one KMAP creature placement."""

    placement_id: str
    runtime_template_resref: str
    source_template_resref: str
    tag: str
    position: Vec3
    facing_radians: float
    render: MapStudioPIECreatureRenderRecipe
    behavior: MapStudioPIECreatureBehaviorState
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapStudioPIECreaturePlan:
    """Immutable creature lane consumed later by the Qt/renderer adapter."""

    game: str
    specs: tuple[MapStudioPIECreatureSpec, ...]
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = PIE_CREATURE_RUNTIME_LIMITATIONS

    @property
    def renderable_count(self) -> int:
        return sum(1 for spec in self.specs if spec.render.can_build_actor)

    @property
    def free_roam_count(self) -> int:
        return sum(1 for spec in self.specs if spec.behavior.locomotion == "free_roam")

    @property
    def hostile_marker_count(self) -> int:
        return sum(1 for spec in self.specs if spec.behavior.relationship == "hostile")

    @property
    def suppressed_script_creature_count(self) -> int:
        return sum(1 for spec in self.specs if spec.behavior.scripts_suppressed)


@dataclass(frozen=True)
class MapStudioPIEPreparedCreature:
    """One copy-owned retained actor artifact prepared off the Qt thread."""

    spec: MapStudioPIECreatureSpec
    actor_model: Any
    prepared_root: Any
    animation_engine: Any
    initial_pose: Any
    animation_name: str


@dataclass(frozen=True)
class MapStudioPIECreaturePreparationResult:
    """Immutable publication envelope for one generation of PIE actors."""

    entries: tuple[MapStudioPIEPreparedCreature, ...]
    prototype_models: tuple[tuple[tuple[Any, ...], Any], ...]
    failures: tuple[str, ...]
    total_spec_count: int
    suppressed_script_creature_count: int
    elapsed_ms: float
    composition_ms: float
    hierarchy_copy_ms: float
    animation_ms: float
    prototype_cache_hits: int
    cancelled: bool = False


def play_map_studio_pie_safe_idle(engine: Any) -> str:
    """Select a real safe idle clip without inventing creature behavior."""

    for candidate in ("pause1", "cpause1", "listen", "idlepose"):
        if engine.play(candidate, loop=True, blend=False):
            return str(
                getattr(getattr(engine, "current_animation", None), "name", candidate) or candidate
            ).lower()
    return ""


def play_map_studio_pie_scene_animation(engine: Any, candidates: tuple[str, ...]) -> str:
    """Play the first authored scene-animation clip that resolves, else safe idle.

    ``candidates`` come from the module's OnEnter script (a seated NPC's sit
    clip, a talker's talk clip); they vary by model, so the first that the
    creature's own model/supermodel actually contains is played. When none
    resolve (or none were authored), fall back to the neutral safe idle so a
    creature is never left unposed.
    """

    for candidate in tuple(candidates or ()):
        clean = str(candidate or "").strip().lower()
        if clean and clean not in ("pause1", "walk", "run") and engine.play(clean, loop=True, blend=False):
            return str(
                getattr(getattr(engine, "current_animation", None), "name", clean) or clean
            ).lower()
    return play_map_studio_pie_safe_idle(engine)


def apply_map_studio_pie_actor_texture_override(
    prepared_root: Any,
    texture_resref: str,
) -> int:
    """Apply copy-owned instance texture state to one prepared body DAG.

    Retail Odyssey reads appearance.2da ``RaceTex`` for non-B full-body
    creatures and applies that texture to the model instance.  Prototype and
    source MDLs are shared across placements, so mutating either would leak one
    appearance variant into every actor.  This helper only edits the deep-copied
    hierarchy that PIE is about to publish and deliberately skips BAS
    attachment layers (detachable heads own their own appearance contract).
    """

    clean = _clean_resref(texture_resref)
    if prepared_root is None or not clean:
        return 0
    changed = 0
    stack = [prepared_root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        if node is None or id(node) in visited:
            continue
        visited.add(id(node))
        stack.extend(tuple(getattr(node, "children", ()) or ()))
        if bool(getattr(node, "_gr_bas_attachment_layer", False)):
            continue
        if (
            not tuple(getattr(node, "vertices", ()) or ())
            or not tuple(getattr(node, "faces", ()) or ())
            or not bool(getattr(node, "render", True))
            or bool(getattr(node, "is_aabb", False))
        ):
            continue
        node.texture = clean
        texture_names = list(getattr(node, "texture_names", ()) or ())
        if texture_names:
            texture_names[0] = clean
        else:
            texture_names = [clean]
        node.texture_names = texture_names
        setattr(node, "_gr_instance_texture_override", clean)
        changed += 1
    return changed


def prepare_map_studio_pie_creature_actor_artifacts(
    plan: MapStudioPIECreaturePlan,
    resource_manager: Any,
    resolver: Any,
    game: str,
    source_models: dict[tuple[str, str], Any],
    prototype_models: dict[tuple[Any, ...], Any],
    *,
    model_bytes_loader: Callable[..., Any],
    model_composer: Callable[..., Any],
    animation_engine_factory: Callable[[Any], Any],
    hierarchy_preparer: Callable[[Any], Any],
    supermodel_configurer: Callable[[Any], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> MapStudioPIECreaturePreparationResult:
    """Prepare creature DAG copies and poses without touching Qt or live scene state.

    Workflow/BAS/animation services are injected so this headless core module
    does not reverse the dependency direction into Systems or GUI packages.
    """

    started = perf_counter()
    composition_seconds = 0.0
    hierarchy_copy_seconds = 0.0
    animation_seconds = 0.0
    prototype_cache_hits = 0
    prepared: list[MapStudioPIEPreparedCreature] = []
    failures: list[str] = []
    new_prototypes: dict[tuple[Any, ...], Any] = {}
    local_sources = dict(source_models or {})
    local_prototypes = dict(prototype_models or {})
    game_tag = str(game or "K1").strip().upper()

    def cancellation_requested() -> bool:
        return bool(cancel_requested is not None and cancel_requested())

    def result(*, cancelled: bool = False) -> MapStudioPIECreaturePreparationResult:
        return MapStudioPIECreaturePreparationResult(
            entries=tuple(prepared),
            prototype_models=tuple(new_prototypes.items()),
            failures=tuple(failures),
            total_spec_count=len(tuple(getattr(plan, "specs", ()) or ())),
            suppressed_script_creature_count=plan.suppressed_script_creature_count,
            elapsed_ms=(perf_counter() - started) * 1000.0,
            composition_ms=composition_seconds * 1000.0,
            hierarchy_copy_ms=hierarchy_copy_seconds * 1000.0,
            animation_ms=animation_seconds * 1000.0,
            prototype_cache_hits=prototype_cache_hits,
            cancelled=cancelled,
        )

    if cancellation_requested():
        return result(cancelled=True)
    if supermodel_configurer is not None:
        supermodel_configurer(resource_manager)

    def load_source(resref: str) -> Any:
        clean = str(resref or "").strip().lower()
        if not clean:
            return None
        key = (game_tag, clean)
        model = local_sources.get(key)
        if model is not None:
            return model
        override = resolver.model_resource_bytes(clean) if resolver is not None else None
        if override is not None:
            model = model_bytes_loader(*override, resref=clean)
        else:
            strict_loader = getattr(resource_manager, "load_model_strict", None)
            if not callable(strict_loader):
                raise RuntimeError(
                    "PIE creature preparation requires target-game-strict model loading"
                )
            model = strict_loader(clean, game_tag)
        local_sources[key] = model
        return model

    for spec in tuple(getattr(plan, "specs", ()) or ())[:64]:
        if cancellation_requested():
            return result(cancelled=True)
        if not spec.render.can_build_actor:
            continue
        try:
            body_resref = str(spec.render.body_model_resref or "").strip().lower()
            head_resref = str(spec.render.head_model_resref or "").strip().lower()
            body_model = load_source(body_resref)
            if cancellation_requested():
                return result(cancelled=True)
            head_model = load_source(head_resref) if head_resref else None
            if cancellation_requested():
                return result(cancelled=True)
            if body_model is None:
                failures.append(f"{spec.tag}: body {body_resref} could not be loaded")
                continue
            if head_resref and head_model is None:
                failures.append(f"{spec.tag}: head {head_resref} could not be loaded")
                continue
            cache_key = (
                game_tag,
                body_resref,
                head_resref,
                id(body_model),
                id(head_model) if head_model is not None else 0,
            )
            actor_model = local_prototypes.get(cache_key)
            if actor_model is None:
                phase_started = perf_counter()
                actor_model = (
                    model_composer(
                        body_model=body_model,
                        attachment_models={"head": head_model},
                        name=f"{body_resref}_{head_resref}_pie_creature",
                    )
                    if head_model is not None
                    else body_model
                )
                composition_seconds += perf_counter() - phase_started
                if cancellation_requested():
                    return result(cancelled=True)
                local_prototypes[cache_key] = actor_model
                new_prototypes[cache_key] = actor_model
            else:
                prototype_cache_hits += 1

            phase_started = perf_counter()
            prepared_root = hierarchy_preparer(actor_model)
            hierarchy_copy_seconds += perf_counter() - phase_started
            if cancellation_requested():
                return result(cancelled=True)
            if prepared_root is None:
                failures.append(f"{spec.tag}: retained Odyssey hierarchy could not be copied")
                continue
            apply_map_studio_pie_actor_texture_override(
                prepared_root,
                getattr(spec.render, "body_texture_resref", ""),
            )

            phase_started = perf_counter()
            engine = animation_engine_factory(actor_model)
            # Authored scene animation (seated/talking from the OnEnter script)
            # first; a neutral safe idle only when none resolves.
            animation_name = play_map_studio_pie_scene_animation(
                engine, tuple(getattr(spec.render, "animation_candidates", ()) or ())
            )
            if not animation_name:
                animation_seconds += perf_counter() - phase_started
                failures.append(f"{spec.tag}: no pause1/cpause1/listen safe idle clip resolved")
                continue
            initial_pose = engine.evaluate()
            animation_seconds += perf_counter() - phase_started
            if cancellation_requested():
                return result(cancelled=True)
            prepared.append(
                MapStudioPIEPreparedCreature(
                    spec=spec,
                    actor_model=actor_model,
                    prepared_root=prepared_root,
                    animation_engine=engine,
                    initial_pose=initial_pose,
                    animation_name=animation_name,
                )
            )
        except Exception as exc:
            failures.append(f"{getattr(spec, 'tag', 'creature')}: {exc}")

    return result()


def _clean_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    if text in {"", "****", "null"}:
        return ""
    return text[:16]


def _vec3(value: Any) -> Vec3:
    try:
        values = tuple(value)
        return (float(values[0]), float(values[1]), float(values[2]))
    except (IndexError, TypeError, ValueError):
        return (0.0, 0.0, 0.0)


def _placement_id(row: Any, index: int) -> str:
    explicit = str(getattr(row, "placement_id", "") or "").strip()
    if explicit:
        return explicit
    token = str(getattr(row, "instance_id", "") or "").strip()
    return f"authored:creature:{token or index}"


def _resource_type_name(value: Any) -> str:
    text = str(value or "").strip().lower().lstrip(".")
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = -1
    return "utc" if numeric in {2027, 2009} else text


def _template_overrides(resources: Iterable[Any]) -> dict[str, bytes]:
    rows: dict[str, bytes] = {}
    for item in tuple(resources or ()):
        try:
            resref, restype, data = item
        except (TypeError, ValueError):
            continue
        key = _clean_resref(resref)
        if key and _resource_type_name(restype) == "utc" and data:
            rows[key] = bytes(data)
    return rows


def _read_utc_contract(data: bytes) -> tuple[int | None, str, tuple[tuple[str, str], ...], bool, int | None]:
    """Return faction, conversation, scripts, visibility, and appearance."""

    from pykotor.resource.generics.utc import read_utc

    utc = read_utc(bytes(data))
    faction_id = int(getattr(utc, "faction_id", 0))
    conversation = _clean_resref(getattr(utc, "conversation", ""))
    scripts = tuple(
        (event, resref)
        for attribute, event in _UTC_SCRIPT_FIELDS
        if (resref := _clean_resref(getattr(utc, attribute, "")))
    )
    visible = not bool(getattr(utc, "will_not_render", False))
    try:
        appearance_id = int(getattr(utc, "appearance_id", -1))
    except (TypeError, ValueError):
        appearance_id = None
    return faction_id, conversation, scripts, visible, appearance_id


def _relationship_for(role: str, faction_id: int | None) -> str:
    clean = str(role or "template").strip().lower().replace("-", "_").replace(" ", "_")
    if clean in {"hostile", "hostile_1", "hostile_2"}:
        return "hostile"
    if clean in {"friendly", "friendly_1", "friendly_2", "player"}:
        return "friendly"
    if clean == "neutral":
        return "neutral"
    if faction_id in {1, 3}:
        return "hostile"
    if faction_id in {0, 2, 4}:
        return "friendly"
    if faction_id == 5:
        return "neutral"
    return "template_unknown"


def _relationship_marker(relationship: str) -> str:
    return {
        "hostile": "hostile_red",
        "friendly": "friendly_blue",
        "neutral": "neutral_gray",
    }.get(relationship, "template_unknown_gray")


def _creatures_and_metadata(project_or_rows: Any) -> tuple[tuple[Any, ...], dict[str, dict[str, Any]], str]:
    placements = getattr(project_or_rows, "placements", None)
    if placements is not None:
        creatures = tuple(getattr(placements, "creatures", ()) or ())
        metadata = dict(getattr(placements, "metadata", {}) or {})
        game = str(getattr(project_or_rows, "game", "K1") or "K1")
    elif hasattr(project_or_rows, "creatures"):
        creatures = tuple(getattr(project_or_rows, "creatures", ()) or ())
        metadata = dict(getattr(project_or_rows, "metadata", {}) or {})
        game = "K1"
    else:
        creatures = tuple(
            row
            for row in tuple(project_or_rows or ())
            if str(getattr(row, "kind", "creature") or "creature").strip().lower() in {"creature", "utc", "npc"}
        )
        metadata = {}
        game = "K1"
    raw_behaviors = dict(metadata.get("creature_behaviors") or {})
    behaviors = {
        str(key): dict(value)
        for key, value in raw_behaviors.items()
        if isinstance(value, dict)
    }
    return creatures, behaviors, game


def build_map_studio_pie_creature_plan(
    project_or_rows: Any,
    resolver: Any,
    *,
    game: str | None = None,
    utc_reader: UTCReader | None = None,
    template_resources: Iterable[Any] = (),
    scene_animations: dict[str, tuple[str, ...]] | None = None,
) -> MapStudioPIECreaturePlan:
    """Resolve safe PIE creature recipes without executing game behavior.

    ``resolver`` follows the existing ``TemplateModelResolver`` contract and
    must expose ``creature_model`` and, optionally, ``creature_head_model`` and
    ``creature_body_texture``.
    ``utc_reader`` is a headless resource callback taking ``(resref, game)``.
    Authored/generated UTC bytes in ``template_resources`` take priority.
    """

    creatures, behavior_records, inferred_game = _creatures_and_metadata(project_or_rows)
    game_tag = str(game or inferred_game or "K1").strip().upper()
    overrides = _template_overrides(template_resources)
    scene_map = {str(k).strip().lower(): tuple(v) for k, v in dict(scene_animations or {}).items()}
    scene_matched = 0
    specs: list[MapStudioPIECreatureSpec] = []
    plan_warnings: list[str] = []

    for index, row in enumerate(creatures):
        placement_id = _placement_id(row, index)
        runtime_template = _clean_resref(getattr(row, "template_resref", ""))
        record = dict(behavior_records.get(placement_id) or {})
        source_template = _clean_resref(
            record.get("source_template_resref")
            or getattr(row, "creature_source_template_resref", "")
            or runtime_template
        )
        role = str(
            record.get("faction_role")
            or getattr(row, "creature_behavior_role", "")
            or "template"
        ).strip().lower()
        movement = str(
            record.get("movement_mode")
            or getattr(row, "creature_movement_mode", "")
            or "stationary"
        ).strip().lower().replace("-", "_")
        authored_behavior = bool(record) or role not in {"", "template"} or movement == "free_roam"
        locomotion = "free_roam" if authored_behavior and movement == "free_roam" else "idle"

        row_warnings: list[str] = []
        body = ""
        head = ""
        body_texture = ""
        if resolver is None:
            row_warnings.append("No creature model resolver was supplied.")
        elif not source_template:
            row_warnings.append("Creature placement has no source UTC resref.")
        else:
            try:
                body = _clean_resref(resolver.creature_model(source_template))
            except Exception as exc:
                row_warnings.append(f"Body model resolution failed: {exc}")
            try:
                head_method = getattr(resolver, "creature_head_model", None)
                if callable(head_method):
                    head = _clean_resref(head_method(source_template))
            except Exception as exc:
                row_warnings.append(f"Head model resolution failed: {exc}")
            try:
                body_texture_method = getattr(resolver, "creature_body_texture", None)
                if callable(body_texture_method):
                    body_texture = _clean_resref(body_texture_method(source_template))
            except Exception as exc:
                row_warnings.append(f"Body texture resolution failed: {exc}")
        if not body:
            row_warnings.append(f"UTC {source_template or runtime_template or '(blank)'} has no resolved body model.")

        utc_data = overrides.get(runtime_template) or overrides.get(source_template)
        if utc_data is None and utc_reader is not None:
            for candidate in tuple(dict.fromkeys((runtime_template, source_template))):
                if not candidate:
                    continue
                try:
                    loaded = utc_reader(candidate, game_tag)
                except Exception as exc:
                    row_warnings.append(f"UTC {candidate} could not be read: {exc}")
                    loaded = None
                if loaded:
                    utc_data = bytes(loaded)
                    break

        faction_id: int | None = None
        conversation = _clean_resref(
            record.get("conversation_resref")
            or getattr(row, "creature_conversation_resref", "")
        )
        scripts: tuple[tuple[str, str], ...] = ()
        visible = True
        if utc_data:
            try:
                faction_id, utc_conversation, scripts, visible, _appearance_id = _read_utc_contract(utc_data)
                if not conversation:
                    conversation = utc_conversation
            except Exception as exc:
                row_warnings.append(f"UTC {runtime_template or source_template} could not be parsed: {exc}")
        else:
            row_warnings.append(
                f"UTC {runtime_template or source_template or '(blank)'} metadata was unavailable; "
                "relationship and script references may be incomplete."
            )

        relationship = _relationship_for(role, faction_id)
        scripts_suppressed = bool(scripts) or locomotion == "free_roam"
        conversation_suppressed = bool(conversation)
        if not visible:
            row_warnings.append("UTC WillNotRender is set; PIE should not create a visible actor.")
        behavior = MapStudioPIECreatureBehaviorState(
            locomotion=locomotion,
            relationship=relationship,
            relationship_marker=_relationship_marker(relationship),
            faction_id=faction_id,
            conversation_resref=conversation,
            script_events=scripts,
            authored_behavior=authored_behavior,
            scripts_suppressed=scripts_suppressed,
            conversation_suppressed=conversation_suppressed,
        )
        creature_tag = str(getattr(row, "tag", "") or runtime_template or source_template)
        scene_clips = scene_map.get(creature_tag.strip().lower())
        if scene_clips:
            scene_matched += 1
            animation_candidates = tuple(scene_clips)
        else:
            animation_candidates = ("pause1", "walk", "run")
        render = MapStudioPIECreatureRenderRecipe(
            actor_id=f"__map_studio_pie_creature__:{placement_id}",
            body_model_resref=body,
            head_model_resref=head,
            body_texture_resref=body_texture,
            visible_in_game=visible,
            animation_candidates=animation_candidates,
        )
        specs.append(
            MapStudioPIECreatureSpec(
                placement_id=placement_id,
                runtime_template_resref=runtime_template,
                source_template_resref=source_template,
                tag=creature_tag,
                position=_vec3(getattr(row, "position", (0.0, 0.0, 0.0))),
                facing_radians=float(getattr(row, "bearing", 0.0) or 0.0),
                render=render,
                behavior=behavior,
                warnings=tuple(dict.fromkeys(row_warnings)),
            )
        )

    script_count = sum(1 for spec in specs if spec.behavior.scripts_suppressed)
    dialogue_count = sum(1 for spec in specs if spec.behavior.conversation_suppressed)
    unresolved_count = sum(1 for spec in specs if not spec.render.can_build_actor and spec.render.visible_in_game)
    if script_count:
        plan_warnings.append(
            f"{script_count} creature(s) reference or request NWScript behavior; PIE keeps those references but does not execute them."
        )
    if dialogue_count:
        plan_warnings.append(
            f"{dialogue_count} creature(s) reference DLG conversations; PIE does not run dialogue state."
        )
    if unresolved_count:
        plan_warnings.append(f"{unresolved_count} visible creature actor recipe(s) have no resolved body model.")
    if scene_map:
        plan_warnings.append(
            f"Authored scene animations from the module OnEnter script matched {scene_matched} of {len(specs)} "
            "creature(s) by tag; the rest use a neutral idle."
        )
    return MapStudioPIECreaturePlan(
        game=game_tag,
        specs=tuple(specs),
        warnings=tuple(plan_warnings),
    )


__all__ = [
    "MapStudioPIECreatureBehaviorState",
    "MapStudioPIECreaturePlan",
    "MapStudioPIECreaturePreparationResult",
    "MapStudioPIECreatureRenderRecipe",
    "MapStudioPIECreatureSpec",
    "MapStudioPIEPreparedCreature",
    "PIE_CREATURE_RUNTIME_LIMITATIONS",
    "apply_map_studio_pie_actor_texture_override",
    "build_map_studio_pie_creature_plan",
    "play_map_studio_pie_safe_idle",
    "play_map_studio_pie_scene_animation",
    "prepare_map_studio_pie_creature_actor_artifacts",
]
