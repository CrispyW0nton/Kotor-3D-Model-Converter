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


def test_resolve_animation_slot_can_require_valid_slot() -> None:
    target = _model("pmbam", anims=("pause1",))

    unresolved = resolve_animation_slot(target, "victory")
    assert unresolved.found is False
    assert unresolved.slot_name == "victory"

    with pytest.raises(ValueError, match="victory"):
        resolve_animation_slot(target, "victory", require_valid=True)
