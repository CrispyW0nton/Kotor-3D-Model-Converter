"""Strict KOTOR slot gate tests for animation override export."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.geometry.model_data import Animation, KotorModel
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationInjectionResult,
    AuroraAnimationWriter,
    InvalidAnimationSlotError,
    prepare_local_animation_override_for_export,
)


def _model(
    name: str,
    *,
    supermodel: str = "NULL",
    anims: tuple[str, ...] = (),
) -> KotorModel:
    model = KotorModel(name=name, supermodel=supermodel)
    model.animations = [Animation(name=anim, length=1.0) for anim in anims]
    return model


def _request(tmp_path: Path, slot: str) -> AuroraAnimationInjectionRequest:
    r3a = tmp_path / "clip.json"
    r3a.write_text(json.dumps({"frame_count": 1, "target_curves": {}}), encoding="utf-8")
    target = tmp_path / "target.mdl"
    target.write_bytes(b"minimal target")
    return AuroraAnimationInjectionRequest(
        r3a_animation_json=r3a,
        target_mdl=target,
        animation_slot=slot,
        output_mdl=tmp_path / "out" / "target.mdl",
        output_manifest=tmp_path / "out" / "manifest.json",
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_invalid_slot_rejects_export_before_writer(monkeypatch, tmp_path: Path) -> None:
    target_model = _model("pmbam", supermodel="S_Male02", anims=("talk_normal",))
    SuperModelResolver.prime_cache("S_Male02", _model("S_Male02", anims=("pause1",)))
    request = _request(tmp_path, "ue_walk_forward")
    writer_called = False

    class SpyWriter:
        def write_files(self, *_args, **_kwargs):
            nonlocal writer_called
            writer_called = True

    monkeypatch.setattr(AuroraAnimationWriter, "_load_model", lambda self, req: target_model)
    monkeypatch.setattr(
        AuroraAnimationWriter,
        "build_animation_from_r3a",
        lambda self, **_kwargs: Animation(name="M_Neutral_Stand_Idle_Loop", length=1.0),
    )
    monkeypatch.setattr(
        "src.core.retargeting.aurora_animation_writer.MDLBinaryWriter",
        lambda: SpyWriter(),
    )

    result = AuroraAnimationWriter().inject(request)

    assert result.success is False
    assert writer_called is False
    assert not request.output_mdl.exists()
    assert not request.output_mdl.with_suffix(".mdx").exists()
    assert not request.output_manifest.exists()
    assert "Invalid animation slot 'ue_walk_forward'" in result.errors[0]
    assert "pause1" in result.errors[0]
    assert "talk_normal" in result.errors[0]
    assert "UE clip names are not KOTOR animation slot names" in result.errors[0]


def test_inherited_slot_is_accepted_and_written_as_local_override(monkeypatch, tmp_path: Path) -> None:
    target_model = _model("pmbam", supermodel="S_Male02")
    SuperModelResolver.prime_cache("S_Male02", _model("S_Male02", anims=("pause1",)))
    request = _request(tmp_path, "pause1")
    captured: dict[str, KotorModel] = {}

    class SpyWriter:
        def write_files(self, model: KotorModel, output_path: str):
            captured["model"] = model
            Path(output_path).write_bytes(b"mdl")
            Path(output_path).with_suffix(".mdx").write_bytes(b"mdx")

        def write_animation_override_files(self, model: KotorModel, _source_mdl, _source_mdx, output_path, _animation, **_kwargs):
            self.write_files(model, str(output_path))

    monkeypatch.setattr(AuroraAnimationWriter, "_load_model", lambda self, req: target_model)
    monkeypatch.setattr(
        AuroraAnimationWriter,
        "build_animation_from_r3a",
        lambda self, **_kwargs: Animation(name="UE_Idle_Clip", length=1.0),
    )
    monkeypatch.setattr(
        "src.core.retargeting.aurora_animation_writer.MDLBinaryWriter",
        lambda: SpyWriter(),
    )
    monkeypatch.setattr(
        AuroraAnimationWriter,
        "_load_output_model",
        lambda self, _mdl, _game: captured["model"],
    )
    monkeypatch.setattr(
        "src.core.retargeting.aurora_animation_writer.validate_raw_animation_footprint",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, issues=[]),
    )

    result = AuroraAnimationWriter().inject(request)

    assert result.success is True, result.errors
    assert captured["model"].animations[-1].name == "pause1"
    assert result.animation_slot == "pause1"
    assert result.operation == "appended_local_override"


def test_local_slot_takes_priority_over_inherited_slot_for_export() -> None:
    target_model = _model("pmbam", supermodel="S_Male02", anims=("custom1",))
    SuperModelResolver.prime_cache("S_Male02", _model("S_Male02", anims=("custom1",)))

    prepared, resolved = prepare_local_animation_override_for_export(
        target_model,
        Animation(name="UE_Custom_Clip", length=1.0),
        "custom1",
    )

    assert prepared.name == "custom1"
    assert resolved.inherited is False
    assert resolved.source_model_name == "pmbam"


def test_requested_slot_casing_resolves_to_canonical_slot_name() -> None:
    target_model = _model("pmbam", supermodel="S_Male02")
    SuperModelResolver.prime_cache("S_Male02", _model("S_Male02", anims=("pause1",)))

    prepared, resolved = prepare_local_animation_override_for_export(
        target_model,
        Animation(name="UE_Pause", length=1.0),
        "Pause1",
    )

    assert resolved.slot_name == "pause1"
    assert prepared.name == "pause1"


def test_existing_local_animation_respects_replace_existing_policy() -> None:
    target_model = _model("pmbam", anims=("pause1",))

    with pytest.raises(ValueError, match="already exists"):
        prepare_local_animation_override_for_export(
            target_model,
            Animation(name="UE_Pause", length=1.0),
            "pause1",
            replace_existing=False,
        )

    prepared, _resolved = prepare_local_animation_override_for_export(
        target_model,
        Animation(name="UE_Pause", length=1.0),
        "pause1",
        replace_existing=True,
    )
    assert prepared.name == "pause1"


def test_invalid_slot_helper_does_not_mutate_caller_animation() -> None:
    target_model = _model("pmbam", anims=("pause1",))
    source = Animation(name="UE_Run_Fwd", length=1.0)

    with pytest.raises(InvalidAnimationSlotError):
        prepare_local_animation_override_for_export(target_model, source, "UE_Run_Fwd")

    assert source.name == "UE_Run_Fwd"
