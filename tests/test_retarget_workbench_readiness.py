"""Retarget Workbench modder-facing readiness model tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.retargeting.retarget_modes import RetargetMode
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
)
from src.core.retargeting.retarget_workbench_readiness import build_retarget_workbench_readiness
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import (
    RetargetWorkbenchController,
    RetargetWorkbenchState,
)


def _missing_names(readiness) -> set[str]:
    return {item.name for item in readiness.inputs if not item.present}


def test_unreal_to_kotor_readiness_with_missing_inputs() -> None:
    readiness = build_retarget_workbench_readiness(RetargetWorkbenchState())

    assert readiness.mode == RetargetMode.UNREAL_TO_KOTOR
    assert readiness.can_preview is False
    assert readiness.can_export is False
    assert {
        "Source UE/FBX clip",
        "Target KOTOR model",
        "Retarget profile",
        "Target output animation",
    }.issubset(_missing_names(readiness))
    assert readiness.preview_status == "Not ready."


def test_unreal_to_kotor_custom_patch_output_summary() -> None:
    state = RetargetWorkbenchState(
        source_clip=SimpleNamespace(clip_name="RunForward"),
        target_model=SimpleNamespace(name="pmbam"),
        retarget_profile=SimpleNamespace(name="profile", animation_slot="pause1"),
        output_naming=RetargetOutputNaming(
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_kotor_animation_name="gr_spin_attack_01",
        ),
    )

    readiness = build_retarget_workbench_readiness(state)

    assert readiness.can_preview is True
    assert "RunForward" in readiness.source_summary
    assert "gr_spin_attack_01" in readiness.output_summary
    assert "Custom animation patch" in readiness.output_summary
    assert "Requires custom animation patch" in readiness.runtime_summary


def test_kotor_to_kotor_separates_source_and_target_names() -> None:
    state = RetargetWorkbenchState(
        mode=RetargetMode.KOTOR_TO_KOTOR,
        source_kotor_model=SimpleNamespace(name="pmbam"),
        source_kotor_animation_slot="pause1",
        target_model=SimpleNamespace(name="pfbam"),
        retarget_profile=SimpleNamespace(name="profile", animation_slot="pause1"),
        output_naming=RetargetOutputNaming(
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_kotor_animation_name="gr_bek_rally",
        ),
    )

    readiness = build_retarget_workbench_readiness(state)

    assert readiness.can_preview is True
    assert "pause1" in readiness.source_summary
    assert "gr_bek_rally" not in readiness.source_summary
    assert "gr_bek_rally" in readiness.output_summary
    assert "pfbam" in readiness.target_summary


def test_kotor_to_kotor_can_preview_only_when_all_inputs_present() -> None:
    state = RetargetWorkbenchState(mode=RetargetMode.KOTOR_TO_KOTOR)

    readiness = build_retarget_workbench_readiness(state)
    assert readiness.can_preview is False
    assert "Source KOTOR model" in _missing_names(readiness)

    state.source_kotor_model = SimpleNamespace(name="source")
    state.source_kotor_animation_slot = "pause1"
    state.target_model = SimpleNamespace(name="target")
    state.retarget_profile = SimpleNamespace(name="profile", animation_slot="")
    readiness = build_retarget_workbench_readiness(state)

    assert readiness.can_preview is False
    assert "Target output animation" in _missing_names(readiness)

    state.output_naming = RetargetOutputNaming(requested_kotor_animation_name="walk")
    readiness = build_retarget_workbench_readiness(state)

    assert readiness.can_preview is True
    assert readiness.blocking_messages == ()


def test_export_requires_current_successful_preview() -> None:
    state = RetargetWorkbenchState(
        mode=RetargetMode.KOTOR_TO_KOTOR,
        source_kotor_model=SimpleNamespace(name="source"),
        source_kotor_animation_slot="pause1",
        target_model=SimpleNamespace(name="target"),
        retarget_profile=SimpleNamespace(name="profile", animation_slot="pause1"),
        output_naming=RetargetOutputNaming(requested_kotor_animation_name="pause1"),
    )

    readiness = build_retarget_workbench_readiness(state)
    assert readiness.can_export is False
    assert readiness.export_status == "Preview required before export."

    state.last_preview_result = SimpleNamespace(preview_audit=SimpleNamespace(passed=True))
    readiness = build_retarget_workbench_readiness(state)
    assert readiness.can_export is True

    state.last_preview_invalidated_reason = "the output animation name changed"
    readiness = build_retarget_workbench_readiness(state)
    assert readiness.can_export is False
    assert "Stale preview" in readiness.export_status


def test_kotor_to_unreal_pending_status_is_clear() -> None:
    state = RetargetWorkbenchState(
        mode=RetargetMode.KOTOR_TO_UNREAL,
        source_kotor_model=SimpleNamespace(name="pmbam"),
        source_kotor_animation_slot="pause1",
        target_unreal_skeleton=SimpleNamespace(name="Quinn"),
        target_unreal_profile=SimpleNamespace(name="ue_profile"),
        output_naming=RetargetOutputNaming(unreal_clip_name="pmbam_pause1"),
    )

    readiness = build_retarget_workbench_readiness(state)

    assert readiness.implemented is False
    assert readiness.can_preview is False
    assert readiness.can_export is False
    assert readiness.preview_status == "Not implemented yet."
    assert "UE-compatible FBX animation clip" in readiness.output_summary


def test_readiness_update_calls_no_sampling_solving_or_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("readiness must not call runtime pipeline functions")

    monkeypatch.setattr("src.core.retargeting.kotor_source_animation.sample_kotor_animation_slot_as_source_clip", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_solver.retarget_source_clip_to_aurora_animation", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_preview_export.export_retarget_preview_override", fail)

    state = RetargetWorkbenchState(
        mode=RetargetMode.KOTOR_TO_KOTOR,
        source_kotor_model=SimpleNamespace(name="source"),
        source_kotor_animation_slot="pause1",
        target_model=SimpleNamespace(name="target"),
        retarget_profile=SimpleNamespace(name="profile", animation_slot="pause1"),
        output_naming=RetargetOutputNaming(requested_kotor_animation_name="pause1"),
    )

    readiness = build_retarget_workbench_readiness(state)

    assert readiness.can_preview is True


def test_controller_readiness_updates_on_mode_switch() -> None:
    controller = RetargetWorkbenchController()

    controller.set_mode(RetargetMode.KOTOR_TO_KOTOR)
    readiness = controller.readiness()

    assert readiness.mode_label == "KOTOR → KOTOR"
    assert "source animation" in readiness.source_summary.lower()
    assert "Target output animation" in readiness.output_summary
