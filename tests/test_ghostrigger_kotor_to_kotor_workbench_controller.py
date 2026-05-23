"""KOTOR-to-KOTOR Retarget Workbench controller tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.core.retargeting.retarget_modes import RetargetMode, get_retarget_mode_spec
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
)
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import RetargetWorkbenchController


class FakeAction:
    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled_values.append(bool(enabled))

    def isEnabled(self) -> bool:  # noqa: N802
        return self.enabled_values[-1] if self.enabled_values else False


def _preview_result(name: str = "gr_bek_rally"):
    return SimpleNamespace(
        slot_name=name,
        animation_block=SimpleNamespace(name=name),
        preview_audit=SimpleNamespace(passed=True),
        output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        requires_custom_animation_patch=True,
        solver_report=SimpleNamespace(mapped_node_count=1),
        warnings=["preview warning"],
    )


def _adapter_result(name: str = "gr_bek_rally"):
    return SimpleNamespace(
        source_sample_result=SimpleNamespace(
            report=SimpleNamespace(resolved_slot_name="pause1", sample_count=2, warnings=["sample warning"])
        ),
        preview_result=_preview_result(name),
        warnings=["sample warning", "preview warning"],
    )


def _controller(*, builder=None, exporter=None, apply_preview=None):
    preview_action = FakeAction()
    export_action = FakeAction()
    calls: dict[str, list] = {"build": [], "apply": [], "export": []}

    def default_builder(request):
        calls["build"].append(request)
        return _adapter_result()

    def default_apply(preview, viewport, *, auto_play=True, show_node_overlay=True):
        calls["apply"].append((preview, viewport, auto_play, show_node_overlay))

    def default_export(request):
        calls["export"].append(request)
        return SimpleNamespace(mdl_path=request.output_mdl_path, slot_name=request.preview_result.slot_name)

    controller = RetargetWorkbenchController(
        viewport=SimpleNamespace(name="viewport"),
        preview_action=preview_action,
        export_action=export_action,
        build_kotor_to_kotor_preview=builder or default_builder,
        apply_preview=apply_preview or default_apply,
        export_preview=exporter or default_export,
    )
    controller.set_mode(RetargetMode.KOTOR_TO_KOTOR)
    return controller, preview_action, export_action, calls


def _fill_required_inputs(controller: RetargetWorkbenchController) -> None:
    controller.set_source_kotor_model(SimpleNamespace(name="source"))
    controller.set_source_kotor_animation_slot("pause1")
    controller.set_target_model(SimpleNamespace(name="target", mdl_path="target.mdl"))
    controller.set_retarget_profile(SimpleNamespace(animation_slot="pause1"))
    controller.set_custom_kotor_animation_name("gr_bek_rally")


def test_kotor_to_kotor_mode_is_implemented() -> None:
    spec = get_retarget_mode_spec(RetargetMode.KOTOR_TO_KOTOR)

    assert spec.implemented is True
    assert spec.supports_preview is True
    assert spec.supports_export is True


def test_can_preview_requires_all_kotor_to_kotor_inputs() -> None:
    controller, preview_action, _export_action, _calls = _controller()

    assert controller.can_preview() is False
    controller.set_source_kotor_model(SimpleNamespace(name="source"))
    assert controller.can_preview() is False
    controller.set_source_kotor_animation_slot("pause1")
    assert controller.can_preview() is False
    controller.set_target_model(SimpleNamespace(name="target"))
    assert controller.can_preview() is False
    controller.set_retarget_profile(SimpleNamespace(animation_slot=""))
    assert controller.can_preview() is False
    controller.set_custom_kotor_animation_name("gr_bek_rally")

    assert controller.can_preview() is True
    assert preview_action.isEnabled() is True


def test_kotor_to_kotor_preview_delegates_to_adapter_and_viewport() -> None:
    controller, _preview_action, export_action, calls = _controller()
    _fill_required_inputs(controller)

    preview = controller.preview(auto_play=False, show_node_overlay=False)

    assert preview.slot_name == "gr_bek_rally"
    assert calls["build"][0].source_model.name == "source"
    assert calls["build"][0].source_animation_slot == "pause1"
    assert calls["build"][0].target_model.name == "target"
    assert calls["build"][0].output_naming.requested_kotor_animation_name == "gr_bek_rally"
    assert calls["apply"] == [(preview, controller.viewport, False, False)]
    assert controller.state.last_preview_result is preview
    assert export_action.isEnabled() is True


def test_changing_source_animation_invalidates_preview_and_export() -> None:
    controller, _preview_action, export_action, _calls = _controller()
    _fill_required_inputs(controller)
    controller.preview()
    controller.state.last_export_result = object()

    controller.set_source_kotor_animation_slot("new_anim")

    assert controller.state.last_preview_result is None
    assert controller.state.last_export_result is None
    assert export_action.isEnabled() is False


def test_changing_target_output_name_invalidates_without_overwriting_source_slot() -> None:
    controller, _preview_action, _export_action, _calls = _controller()
    _fill_required_inputs(controller)
    controller.preview()

    controller.set_custom_kotor_animation_name("gr_new_name")

    assert controller.state.source_kotor_animation_slot == "pause1"
    assert controller.state.last_preview_result is None
    assert controller.state.output_naming.requested_kotor_animation_name == "gr_new_name"


def test_kotor_to_kotor_export_uses_last_preview_only() -> None:
    controller, _preview_action, _export_action, calls = _controller()
    _fill_required_inputs(controller)
    preview = controller.preview()
    calls["build"].clear()

    result = controller.export_preview(Path("pmbam.mdl"), overwrite=True, write_manifest=False)

    assert result.mdl_path == Path("pmbam.mdl")
    assert calls["build"] == []
    assert len(calls["export"]) == 1
    request = calls["export"][0]
    assert request.preview_result is preview
    assert request.verify_roundtrip is True
    assert request.kotor_output_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
    assert request.requires_custom_animation_patch is True


def test_switching_to_kotor_to_unreal_does_not_call_kotor_to_kotor_paths() -> None:
    controller, _preview_action, export_action, calls = _controller()

    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)

    assert controller.can_preview() is False
    assert controller.can_export() is False
    assert export_action.isEnabled() is False
    assert calls["build"] == []
    assert calls["export"] == []
