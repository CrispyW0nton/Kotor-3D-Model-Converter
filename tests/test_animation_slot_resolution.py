"""Tests for KOTOR animation slot and supermodel-chain helpers."""

from __future__ import annotations

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.animation.fbx_animation_selection import (
    FbxAnimationSetInfo,
    list_fbx_animation_sets,
    prepare_fbx_animation_export_model,
)
from src.core.game.kotor_loader import (
    get_valid_animation_slots,
    load_supermodel_chain,
    resolve_animation_slot,
)
from src.core.geometry.model_data import AnimEvent, Animation, KotorModel, ModelNode


def _model(
    name: str,
    *,
    supermodel: str = "NULL",
    anims: tuple[str, ...] = (),
    anim_scale: float = 1.0,
) -> KotorModel:
    model = KotorModel(name=name, supermodel=supermodel, anim_scale=anim_scale)
    model.animations = [Animation(name=anim, length=1.0) for anim in anims]
    return model


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_valid_animation_slots_include_local_overrides_and_inherited_slots() -> None:
    target = _model("pmbam", supermodel="S_Male02", anims=("victory",), anim_scale=2.0)
    supermodel = _model("S_Male02", anims=("pause1", "victory"), anim_scale=3.0)
    SuperModelResolver.prime_cache("S_Male02", supermodel)

    assert get_valid_animation_slots(target) == ["pause1", "victory"]

    local_slot = resolve_animation_slot(target, "victory", require_valid=True)
    assert local_slot.found is True
    assert local_slot.inherited is False
    assert local_slot.source_model_name == "pmbam"
    assert local_slot.cumulative_scale == 1.0

    inherited_slot = resolve_animation_slot(target, "pause1", require_valid=True)
    assert inherited_slot.found is True
    assert inherited_slot.inherited is True
    assert inherited_slot.source_model_name == "S_Male02"
    assert inherited_slot.cumulative_scale == 2.0


def test_animation_entries_classify_local_inherited_and_override_sources() -> None:
    from src.core.animation.animation_engine import AnimationEngine

    target = _model("P_BastilaH", supermodel="P_BastilaBB", anims=("talk", "listen"))
    body = _model("P_BastilaBB", supermodel="S_Female03")
    female = _model("S_Female03", anims=("talk", "walk"))
    SuperModelResolver.prime_cache("P_BastilaBB", body)
    SuperModelResolver.prime_cache("S_Female03", female)

    entries = {
        str(entry["name"]).lower(): entry
        for entry in AnimationEngine(target).list_all_animations()
    }

    assert entries["listen"]["source_type"] == "local"
    assert entries["listen"]["source_scope"] == "local"
    assert entries["listen"]["overrides_inherited"] is False
    assert entries["talk"]["source_type"] == "override"
    assert entries["talk"]["source_scope"] == "local"
    assert entries["talk"]["overrides_inherited"] is True
    assert entries["walk"]["source_type"] == "inherited"
    assert entries["walk"]["source_scope"] == "inherited"
    assert entries["walk"]["inherited"] is True


def test_load_supermodel_chain_reports_loaded_and_missing_entries() -> None:
    target = _model("pmbam", supermodel="S_Male02")
    supermodel = _model("S_Male02", supermodel="S_Missing")
    SuperModelResolver.prime_cache("S_Male02", supermodel)
    SuperModelResolver.prime_cache("S_Missing", None)

    chain = load_supermodel_chain(target)

    assert chain.root_model_name == "pmbam"
    assert [entry.resref for entry in chain.entries] == ["S_Male02", "S_Missing"]
    assert chain.entries[0].loaded is True
    assert chain.entries[0].model_name == "S_Male02"
    assert chain.entries[1].loaded is False
    assert chain.loaded_models() == ["S_Male02"]


def test_supermodel_resolver_cache_is_game_specific() -> None:
    class Manager:
        def load_model(self, resref: str, game: str = "K1"):
            return _model(resref, anims=(f"{game.lower()}only",))

    SuperModelResolver.configure(Manager())

    k1_model = SuperModelResolver.load_supermodel("S_Male02", "K1")
    k2_model = SuperModelResolver.load_supermodel("S_Male02", "K2")

    assert [anim.name for anim in k1_model.animations] == ["k1only"]
    assert [anim.name for anim in k2_model.animations] == ["k2only"]


def test_supermodel_resolver_prefers_target_game_strict_loader() -> None:
    calls: list[tuple[str, str, str]] = []

    class Manager:
        def load_model(self, resref: str, game: str = "K1"):
            calls.append(("fallback", resref, game))
            return _model(resref, anims=("wronggame",))

        def load_model_strict(self, resref: str, game: str = "K1"):
            calls.append(("strict", resref, game))
            return _model(resref, anims=(f"{game.lower()}only",))

    SuperModelResolver.configure(Manager())

    model = SuperModelResolver.load_supermodel("S_Male02", "K2")

    assert model is not None
    assert [anim.name for anim in model.animations] == ["k2only"]
    assert calls == [("strict", "S_Male02", "K2")]


def test_supermodel_resolver_cache_tracks_manager_identity_and_revision() -> None:
    class Manager:
        def __init__(self, label: str) -> None:
            self.label = label
            self.revision = 1
            self.calls = 0

        def load_model_strict(self, resref: str, game: str = "K1"):
            self.calls += 1
            return _model(resref, anims=(f"{self.label}_{self.revision}",))

    first_manager = Manager("first")
    SuperModelResolver.configure(first_manager)
    initial = SuperModelResolver.load_supermodel("S_Male02", "K1")

    SuperModelResolver.configure(first_manager)
    retained = SuperModelResolver.load_supermodel("S_Male02", "K1")
    assert retained is initial
    assert first_manager.calls == 1

    first_manager.revision += 1
    SuperModelResolver.configure(first_manager)
    revised = SuperModelResolver.load_supermodel("S_Male02", "K1")
    assert revised is not initial
    assert [anim.name for anim in revised.animations] == ["first_2"]
    assert first_manager.calls == 2

    second_manager = Manager("second")
    second_manager.revision = first_manager.revision
    SuperModelResolver.configure(second_manager)
    replaced = SuperModelResolver.load_supermodel("S_Male02", "K1")
    assert replaced is not revised
    assert [anim.name for anim in replaced.animations] == ["second_2"]
    assert second_manager.calls == 1


def test_resolve_animation_slot_can_require_valid_slot() -> None:
    target = _model("pmbam", anims=("pause1",))

    unresolved = resolve_animation_slot(target, "victory")
    assert unresolved.found is False
    assert unresolved.slot_name == "victory"

    with pytest.raises(ValueError, match="victory"):
        resolve_animation_slot(target, "victory", require_valid=True)


def _keyed_animation(
    name: str,
    values: tuple[tuple[float, ...], ...],
    *,
    legacy: bool = False,
    node_name: str = "root",
) -> Animation:
    node = ModelNode(name=node_name)
    controller = {
        "type": 8,
        "times": [float(index) for index in range(len(values))],
        "values": [list(value) for value in values],
    }
    node.controllers = {8: controller} if legacy else [controller]
    return Animation(
        name=name,
        length=max(0.0, float(len(values) - 1)),
        events=[],
        nodes=[node],
    )


def test_fbx_animation_inventory_prefers_body_then_supplemental_then_inherited() -> None:
    body = _model(
        "pmbam",
        supermodel="S_Male02",
        anims=("talk",),
        anim_scale=2.0,
    )
    body.animations[0].nodes = [ModelNode(name="body_face")]
    head = _model("pmha01", supermodel="P_Male01", anims=("talk", "blink"))
    base = _model(
        "S_Male02",
        supermodel="S_Male03",
        anims=("talk", "walk"),
        anim_scale=3.0,
    )
    ancestor = _model("S_Male03", anims=("dance",))
    SuperModelResolver.prime_cache("S_Male03", ancestor, "K1")

    rows = list_fbx_animation_sets(
        body,
        game="K1",
        base_skeleton_model=base,
        supplemental_models=(head,),
    )

    assert all(isinstance(row, FbxAnimationSetInfo) for row in rows)
    assert [row.name for row in rows] == ["blink", "dance", "talk", "walk"]
    by_name = {row.name: row for row in rows}
    assert by_name["talk"].source_model_name == "pmbam"
    assert by_name["talk"].source_scope == "local"
    assert by_name["talk"].contributing_models == ("pmbam", "pmha01")
    assert by_name["blink"].source_model == "pmha01"
    assert by_name["blink"].scope == "supplemental"
    assert by_name["walk"].source_scope == "inherited"
    assert by_name["walk"].cumulative_scale == pytest.approx(2.0)
    assert by_name["dance"].cumulative_scale == pytest.approx(6.0)


def test_fbx_animation_selection_materializes_exact_takes_and_bakes_position_scale() -> None:
    body = _model("pmbam", supermodel="S_Male02", anim_scale=2.0)
    body.animations = [_keyed_animation("local", ((1.0, 2.0, 3.0),))]
    head = _model("pmha01")
    head_walk = _keyed_animation(
        "walk",
        ((10.0, 20.0, 30.0),),
        node_name="face_g",
    )
    head_walk.nodes.append(
        _keyed_animation("walk", ((90.0, 90.0, 90.0),)).nodes[0]
    )
    head_walk.length = 2.0
    head_walk.events = [
        AnimEvent(time=0.5, name="hit"),
        AnimEvent(time=0.75, name="blink"),
    ]
    head.animations = [
        _keyed_animation("blink", ((4.0, 5.0, 6.0),)),
        head_walk,
    ]
    base = _model("S_Male02")
    base.animations = [
        _keyed_animation("walk", ((1.0, 2.0, 3.0, 99.0),), legacy=True)
    ]
    base.animations[0].length = 1.0
    base.animations[0].events = [AnimEvent(time=0.5, name="hit")]

    prepared = prepare_fbx_animation_export_model(
        body,
        ("WALK", "blink", "walk", "LOCAL"),
        game="K1",
        base_skeleton_model=base,
        supplemental_models=(head,),
    )

    assert prepared is not body
    assert [animation.name for animation in prepared.animations] == [
        "walk",
        "blink",
        "local",
    ]
    assert prepared.anim_scale == 1.0
    inherited_controller = prepared.animations[0].nodes[0].controllers[8]
    assert inherited_controller["values"] == [[2.0, 4.0, 6.0, 99.0]]
    facial_controller = prepared.animations[0].nodes[1].controllers[0]
    assert [node.name for node in prepared.animations[0].nodes] == ["root", "face_g"]
    assert prepared.animations[0].nodes[1].name == "face_g"
    assert facial_controller["values"] == [[10.0, 20.0, 30.0]]
    assert prepared.animations[0].length == 2.0
    assert [event.name for event in prepared.animations[0].events] == ["hit", "blink"]
    assert prepared.animations[1].nodes[0].controllers[0]["values"] == [
        [4.0, 5.0, 6.0]
    ]
    assert prepared.animations[2].nodes[0].controllers[0]["values"] == [
        [1.0, 2.0, 3.0]
    ]

    # Source assets remain untouched, including the inherited block.
    assert body.anim_scale == 2.0
    assert base.animations[0].nodes[0].controllers[8]["values"] == [
        [1.0, 2.0, 3.0, 99.0]
    ]
    metadata = prepared._gr_fbx_animation_selection
    assert metadata["requested"] == ["WALK", "blink", "LOCAL"]
    assert metadata["embedded"] == ["walk", "blink", "local"]
    assert metadata["missing"] == []
    assert metadata["source_models"] == {
        "walk": "S_Male02",
        "blink": "pmha01",
        "local": "pmbam",
    }
    assert metadata["cumulative_scales"]["walk"] == pytest.approx(2.0)
    assert metadata["contributing_models"]["walk"] == ["S_Male02", "pmha01"]


def test_fbx_animation_selection_distinguishes_preserve_empty_and_missing() -> None:
    body = _model("pmbam", anims=("pause1",), anim_scale=2.5)

    preserved = prepare_fbx_animation_export_model(body, None)
    assert preserved is not body
    assert preserved.animations is not body.animations
    assert [animation.name for animation in preserved.animations] == ["pause1"]
    assert preserved.anim_scale == 1.0
    assert preserved._gr_fbx_animation_selection["requested"] is None

    empty = prepare_fbx_animation_export_model(body, ())
    assert empty.animations == []
    assert empty._gr_fbx_animation_selection["requested"] == []

    with pytest.raises(ValueError, match="does_not_exist"):
        prepare_fbx_animation_export_model(body, ("does_not_exist",))

    partial = prepare_fbx_animation_export_model(
        body,
        ("pause1", "does_not_exist"),
        require_all=False,
    )
    assert [animation.name for animation in partial.animations] == ["pause1"]
    assert partial._gr_fbx_animation_selection["missing"] == ["does_not_exist"]


def test_fbx_animation_selection_merges_filtered_inherited_head_tracks() -> None:
    body_root = ModelNode(name="body_root")
    pelvis = ModelNode(name="pelvis", parent=body_root)
    body_root.children.append(pelvis)
    body = _model("body", supermodel="S_Body", anim_scale=2.0)
    body.root_node = body_root

    primary_talk = _keyed_animation("talk", ((1.0, 0.0, 0.0),))
    primary_talk.nodes[0].name = "pelvis"
    body_super = _model("S_Body")
    body_super.animations = [primary_talk]

    head_root = ModelNode(name="head_root")
    jaw = ModelNode(name="jaw", parent=head_root)
    head_root.children.append(jaw)
    head = _model("head", supermodel="S_Head", anim_scale=4.0)
    head.root_node = head_root
    assert head.animations == []

    jaw_track = ModelNode(
        name="jaw",
        controllers=[{
            "type": 8,
            "times": [0.0],
            "values": [[0.0, 1.0, 0.0]],
        }],
    )
    foreign_pelvis_track = ModelNode(
        name="pelvis",
        controllers=[{
            "type": 8,
            "times": [0.0],
            "values": [[99.0, 99.0, 99.0]],
        }],
    )
    head_super = _model("S_Head")
    head_super.animations = [
        Animation(name="talk", length=2.0, nodes=[jaw_track, foreign_pelvis_track])
    ]

    SuperModelResolver.prime_cache("S_Body", body_super, "K1")
    SuperModelResolver.prime_cache("S_Head", head_super, "K1")

    rows = list_fbx_animation_sets(body, game="K1", supplemental_models=(head,))
    talk_row = next(row for row in rows if row.name == "talk")
    assert talk_row.contributing_models == ("S_Body", "head")
    assert talk_row.node_count == 2

    prepared = prepare_fbx_animation_export_model(
        body,
        ("talk",),
        game="K1",
        supplemental_models=(head,),
    )
    talk = prepared.animations[0]
    assert [node.name for node in talk.nodes] == ["pelvis", "jaw"]
    assert talk.nodes[0].controllers[0]["values"] == [[2.0, 0.0, 0.0]]
    assert talk.nodes[1].controllers[0]["values"] == [[0.0, 4.0, 0.0]]
    assert body_super.animations[0].nodes[0].controllers[0]["values"] == [
        [1.0, 0.0, 0.0]
    ]
    assert head_super.animations[0].nodes[0].controllers[0]["values"] == [
        [0.0, 1.0, 0.0]
    ]
