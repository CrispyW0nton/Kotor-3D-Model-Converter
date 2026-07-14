"""Focused contracts for the bounded Map Studio PIE creature lane."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from pykotor.common.misc import Game, ResRef
from pykotor.resource.generics.utc import UTC, bytes_utc

from src.core.modules.map_studio_pie_creatures import (
    PIE_CREATURE_RUNTIME_LIMITATIONS,
    build_map_studio_pie_creature_plan,
)


class _Resolver:
    def __init__(self) -> None:
        self.body_calls: list[str] = []
        self.head_calls: list[str] = []

    def creature_model(self, resref: str) -> str:
        self.body_calls.append(resref)
        return {
            "source_npc": "pmbam",
            "stock_friend": "n_twilekf",
            "hidden_actor": "c_coneh",
        }.get(resref, "")

    def creature_head_model(self, resref: str) -> str:
        self.head_calls.append(resref)
        return "pmhc01" if resref == "source_npc" else ""


def _utc(
    *,
    faction: int,
    conversation: str = "",
    spawn: str = "",
    heartbeat: str = "",
    hidden: bool = False,
) -> bytes:
    utc = UTC()
    utc.faction_id = faction
    utc.conversation = ResRef(conversation)
    utc.on_spawn = ResRef(spawn)
    utc.on_heartbeat = ResRef(heartbeat)
    utc.will_not_render = hidden
    return bytes_utc(utc, Game.K2)


def test_plan_uses_source_utc_for_body_head_and_suppresses_game_runtime_behavior() -> None:
    generated = _utc(
        faction=1,
        conversation="npc_dialog",
        spawn="gr_spawn",
        heartbeat="a_heartbeat",
    )
    project = SimpleNamespace(
        game="K2",
        placements=SimpleNamespace(
            creatures=(
                SimpleNamespace(
                    template_resref="generated_npc",
                    instance_id="i_npc",
                    tag="Test NPC",
                    position=(1.0, 2.0, 3.0),
                    bearing=0.75,
                ),
            ),
            metadata={
                "creature_behaviors": {
                    "authored:creature:i_npc": {
                        "source_template_resref": "source_npc",
                        "generated_template_resref": "generated_npc",
                        "faction_role": "hostile",
                        "conversation_resref": "npc_dialog",
                        "movement_mode": "free_roam",
                    },
                },
            },
        ),
    )
    before = deepcopy(project)
    resolver = _Resolver()

    plan = build_map_studio_pie_creature_plan(
        project,
        resolver,
        template_resources=(("generated_npc", "UTC", generated),),
    )

    assert project == before
    assert plan.game == "K2"
    assert len(plan.specs) == 1
    spec = plan.specs[0]
    assert spec.placement_id == "authored:creature:i_npc"
    assert spec.runtime_template_resref == "generated_npc"
    assert spec.source_template_resref == "source_npc"
    assert spec.position == (1.0, 2.0, 3.0)
    assert spec.facing_radians == 0.75
    assert resolver.body_calls == ["source_npc"]
    assert resolver.head_calls == ["source_npc"]
    assert spec.render.body_model_resref == "pmbam"
    assert spec.render.attachment_model_resrefs == (("head", "pmhc01"),)
    assert spec.render.can_build_actor is True
    assert spec.behavior.locomotion == "free_roam"
    assert spec.behavior.relationship == "hostile"
    assert spec.behavior.relationship_marker == "hostile_red"
    assert spec.behavior.script_events == (("spawn", "gr_spawn"), ("heartbeat", "a_heartbeat"))
    assert spec.behavior.conversation_resref == "npc_dialog"
    assert spec.behavior.scripts_suppressed is True
    assert spec.behavior.conversation_suppressed is True
    assert spec.behavior.exact_runtime_parity is False
    assert plan.renderable_count == 1
    assert plan.free_roam_count == 1
    assert plan.hostile_marker_count == 1
    assert plan.suppressed_script_creature_count == 1
    assert any("does not execute" in warning for warning in plan.warnings)
    assert any("does not run dialogue" in warning for warning in plan.warnings)


def test_template_relationship_is_read_without_inventing_scripted_movement() -> None:
    stock_bytes = _utc(faction=2, spawn="k_ai_master")
    row = SimpleNamespace(
        kind="creature",
        placement_id="authored:creature:7",
        template_resref="stock_friend",
        tag="Stock Friend",
        position=(4.0, 5.0, 0.0),
        bearing=1.25,
        creature_behavior_role="template",
        creature_movement_mode="stationary",
    )
    resolver = _Resolver()

    plan = build_map_studio_pie_creature_plan(
        (row,),
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: stock_bytes if resref == "stock_friend" else None,
    )

    spec = plan.specs[0]
    assert spec.behavior.relationship == "friendly"
    assert spec.behavior.relationship_marker == "friendly_blue"
    assert spec.behavior.locomotion == "idle"
    assert spec.behavior.authored_behavior is False
    assert spec.behavior.script_events == (("spawn", "k_ai_master"),)
    assert spec.behavior.scripts_suppressed is True
    assert spec.render.body_model_resref == "n_twilekf"
    assert spec.render.head_model_resref == ""


def test_hidden_and_unresolved_creatures_never_become_fake_visible_actors() -> None:
    hidden = SimpleNamespace(
        kind="creature",
        placement_id="authored:creature:hidden",
        template_resref="hidden_actor",
        tag="Invisible helper",
        position=(0.0, 0.0, 0.0),
        bearing=0.0,
    )
    unresolved = SimpleNamespace(
        kind="creature",
        placement_id="authored:creature:missing",
        template_resref="missing_actor",
        tag="Missing",
        position=(0.0, 0.0, 0.0),
        bearing=0.0,
    )
    resolver = _Resolver()
    plan = build_map_studio_pie_creature_plan(
        (hidden, unresolved),
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: _utc(faction=5, hidden=True) if resref == "hidden_actor" else None,
    )

    assert plan.specs[0].render.visible_in_game is False
    assert plan.specs[0].render.can_build_actor is False
    assert any("WillNotRender" in warning for warning in plan.specs[0].warnings)
    assert plan.specs[1].render.can_build_actor is False
    assert any("no resolved body" in warning for warning in plan.specs[1].warnings)
    assert any("no resolved body model" in warning for warning in plan.warnings)


def test_contract_names_the_unsupported_engine_systems() -> None:
    text = " ".join(PIE_CREATURE_RUNTIME_LIMITATIONS)
    assert "NWScript" in text
    assert "DLG" in text
    assert "combat" in text
    assert "manual warp to plcaa" in text


def test_kmap_shell_public_snapshot_routes_authored_creatures_and_sounds() -> None:
    """PIE consumers must not ask the outer KMapProject for placements."""

    from src.core.level.kmap_model import KMapProject
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import (
        AuthoredCreatureInstance,
        AuthoredGameplayPlacement,
        AuthoredSoundInstance,
        ModuleEntryPoint,
    )
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject
    from src.core.modules.module_editor_controller import ModuleEditorController
    from src.core.modules.module_editor_model import ModuleEditorModel

    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="plcaa", game="K2"),
        rooms=(),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="plcaa"),
            creatures=(AuthoredCreatureInstance("npc_template", instance_id="npc_1"),),
            sounds=(AuthoredSoundInstance("ambient_uts", instance_id="sound_1"),),
        ),
    )
    shell = KMapProject(name="plcaa", game="K2")
    shell.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    controller = ModuleEditorController(ModuleEditorModel(project=shell))

    snapshot = controller.map_studio_authored_placements_snapshot()

    assert not hasattr(shell, "placements")
    assert snapshot is not None
    assert [row.template_resref for row in snapshot.creatures] == ["npc_template"]
    assert [row.template_resref for row in snapshot.sounds] == ["ambient_uts"]

    # This public worker-facing snapshot is isolated from Scene's cached
    # authored project; callers cannot mutate controller state accidentally.
    snapshot.metadata["worker_mutation"] = True
    second = controller.map_studio_authored_placements_snapshot()
    assert "worker_mutation" not in second.metadata


def test_safe_idle_fallback_includes_creature_and_listening_clips() -> None:
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_safe_idle

    class Engine:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.current_animation = None

        def play(self, name: str, **_kwargs) -> bool:
            self.calls.append(name)
            if name != "listen":
                return False
            self.current_animation = SimpleNamespace(name=name)
            return True

    engine = Engine()
    assert play_map_studio_pie_safe_idle(engine) == "listen"
    assert engine.calls == ["pause1", "cpause1", "listen"]


def test_headless_actor_preparation_reuses_recipe_and_returns_copy_owned_artifacts() -> None:
    from src.core.modules.map_studio_pie_creatures import (
        prepare_map_studio_pie_creature_actor_artifacts,
    )

    render = SimpleNamespace(
        can_build_actor=True,
        body_model_resref="body",
        head_model_resref="head",
    )
    specs = tuple(
        SimpleNamespace(tag=f"npc_{index}", render=render)
        for index in range(2)
    )
    plan = SimpleNamespace(specs=specs, suppressed_script_creature_count=2)
    body = object()
    head = object()
    compose_calls: list[tuple[object, object]] = []
    engines: list[object] = []

    def compose(*, body_model, attachment_models, name):
        compose_calls.append((body_model, attachment_models["head"]))
        return SimpleNamespace(name=name)

    class Engine:
        def __init__(self, model) -> None:
            self.model = model
            self.current_animation = None
            engines.append(self)

        def play(self, name: str, **_kwargs) -> bool:
            if name != "listen":
                return False
            self.current_animation = SimpleNamespace(name=name)
            return True

        def evaluate(self):
            return SimpleNamespace(nodes={"root": object()})

    roots: list[object] = []

    def prepare_root(_model):
        root = object()
        roots.append(root)
        return root

    class Manager:
        def load_model(self, *_args):
            raise AssertionError("the already resident source cache must be used")

    class Resolver:
        def model_resource_bytes(self, _resref):
            raise AssertionError("the already resident source cache must be used")

    def bytes_loader(*_args, **_kwargs):
        raise AssertionError("the already resident source cache must be used")

    preview_sentinel = SimpleNamespace(children=["flattened-authoring-preview"])
    kwargs = dict(
        model_bytes_loader=bytes_loader,
        model_composer=compose,
        animation_engine_factory=Engine,
        hierarchy_preparer=prepare_root,
    )
    result = prepare_map_studio_pie_creature_actor_artifacts(
        plan,
        Manager(),
        Resolver(),
        "K2",
        {("K2", "body"): body, ("K2", "head"): head},
        {},
        **kwargs,
    )

    assert len(compose_calls) == 1
    assert len(result.prototype_models) == 1
    assert result.prototype_cache_hits == 1
    assert len(result.entries) == 2
    assert result.entries[0].prepared_root is not result.entries[1].prepared_root
    assert result.entries[0].animation_engine is not result.entries[1].animation_engine
    assert [entry.animation_name for entry in result.entries] == ["listen", "listen"]
    assert preview_sentinel.children == ["flattened-authoring-preview"]

    warm = prepare_map_studio_pie_creature_actor_artifacts(
        plan,
        Manager(),
        Resolver(),
        "K2",
        {("K2", "body"): body, ("K2", "head"): head},
        dict(result.prototype_models),
        **kwargs,
    )
    assert len(compose_calls) == 1
    assert warm.prototype_models == ()
    assert warm.prototype_cache_hits == 2
    assert len(engines) == 4


def test_cancel_and_stale_generation_cannot_publish_prepared_creatures() -> None:
    from threading import Event

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class Future:
        def __init__(self) -> None:
            self.cancelled = False
            self.result_called = False

        def cancel(self) -> None:
            self.cancelled = True

        def result(self):
            self.result_called = True
            raise AssertionError("a stale generation must not read or publish its result")

    future = Future()
    cancel_event = Event()
    window = SimpleNamespace(
        _map_studio_pie_creature_prepare_generation=4,
        _map_studio_pie_creature_prepare_future=future,
        _map_studio_pie_creature_prepare_cancel=cancel_event,
        _map_studio_pie_creature_prepare_preview_id=123,
        _map_studio_pie_creature_summary="preparing",
    )
    ModuleEditorWindow._cancel_map_studio_pie_creature_preparation(window)
    assert future.cancelled is True
    assert cancel_event.is_set() is True
    assert window._map_studio_pie_creature_prepare_generation == 5
    assert window._map_studio_pie_creature_prepare_future is None
    assert window._map_studio_pie_creature_prepare_cancel is None
    assert window._map_studio_pie_creature_prepare_preview_id == 0

    stale = Future()
    preview = object()
    window._map_studio_pie_creature_prepare_future = stale
    window._map_studio_pie_creature_prepare_preview_id = id(preview)
    window._map_studio_pie_session = object()
    ModuleEditorWindow._poll_map_studio_pie_creature_preparation(window, 4, preview)
    assert stale.result_called is False


def test_running_creature_preparation_stops_cooperatively_between_heavy_phases() -> None:
    from threading import Event

    from src.core.modules.map_studio_pie_creatures import (
        prepare_map_studio_pie_creature_actor_artifacts,
    )

    cancel = Event()
    body = SimpleNamespace(name="body")
    render = SimpleNamespace(
        can_build_actor=True,
        body_model_resref="body",
        head_model_resref="",
    )
    plan = SimpleNamespace(
        specs=(
            SimpleNamespace(tag="first", render=render),
            SimpleNamespace(tag="second", render=render),
        ),
        suppressed_script_creature_count=0,
    )
    hierarchy_calls: list[str] = []

    class Manager:
        def load_model_strict(self, _resref, _game):
            return body

    class Resolver:
        def model_resource_bytes(self, _resref):
            return None

    class Engine:
        current_animation = SimpleNamespace(name="pause1")

        def __init__(self, _model):
            pass

        def play(self, *_args, **_kwargs):
            return True

        def evaluate(self):
            return object()

    def prepare_root(model):
        hierarchy_calls.append(model.name)
        cancel.set()
        return object()

    result = prepare_map_studio_pie_creature_actor_artifacts(
        plan,
        Manager(),
        Resolver(),
        "K2",
        {("K2", "body"): body},
        {},
        model_bytes_loader=lambda *_args, **_kwargs: body,
        model_composer=lambda **_kwargs: body,
        animation_engine_factory=Engine,
        hierarchy_preparer=prepare_root,
        cancel_requested=cancel.is_set,
    )

    assert result.cancelled is True
    assert result.entries == ()
    assert hierarchy_calls == ["body"]
