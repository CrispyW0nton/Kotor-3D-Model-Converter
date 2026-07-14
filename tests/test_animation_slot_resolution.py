"""Tests for KOTOR animation slot and supermodel-chain helpers."""

from __future__ import annotations

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.game.kotor_loader import (
    get_valid_animation_slots,
    load_supermodel_chain,
    resolve_animation_slot,
)
from src.core.geometry.model_data import Animation, KotorModel


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


def test_resolve_animation_slot_can_require_valid_slot() -> None:
    target = _model("pmbam", anims=("pause1",))

    unresolved = resolve_animation_slot(target, "victory")
    assert unresolved.found is False
    assert unresolved.slot_name == "victory"

    with pytest.raises(ValueError, match="victory"):
        resolve_animation_slot(target, "victory", require_valid=True)
