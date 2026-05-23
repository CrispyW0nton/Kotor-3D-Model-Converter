"""KOTOR-to-Unreal Retarget Workbench controller tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.core.retargeting.retarget_modes import RetargetMode, get_retarget_mode_spec
from src.core.retargeting.retarget_output_naming import RetargetOutputNaming
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import RetargetWorkbenchController


class FakeAction:
    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled_values.append(bool(enabled))

    def isEnabled(self) -> bool:  # noqa: N802
        return self.enabled_values[-1] if self.enabled_values else False


class FakeFbxBackend:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


def _preview_result(name: str = "pmbam_pause1") -> SimpleNamespace:
    report = SimpleNamespace(resolved_slot_name="pause1", sample_count=2, warnings=[])
    return SimpleNamespace(
        source_sample_result=SimpleNamespace(report=report),
        target_skeleton=SimpleNamespace(name="UE5 Manny"),
        animation_clip=SimpleNamespace(clip_name=name, poses=[object()], sample_rate=30.0),
        validation_report=SimpleNamespace(has_blocking=False, has_errors=False, issues=[]),
        warnings=[],
    )


def _controller(*, builder=None, exporter=None, backend=None):
    preview_action = FakeAction()
    export_action = FakeAction()
    calls: dict[str, list] = {"build": [], "export": []}

    def default_builder(request):
        calls["build"].append(request)
        return _preview_result(getattr(request.output_naming, "unreal_clip_name", "pmbam_pause1"))

    def default_export(request):
        calls["export"].append(request)
        return SimpleNamespace(succeeded=True, final_paths=[request.output_fbx_path], validation_report=SimpleNamespace(issues=[]))

    controller = RetargetWorkbenchController(
        preview_action=preview_action,
        export_action=export_action,
        build_kotor_to_unreal_preview_fn=builder or default_builder,
        export_kotor_to_unreal_preview_fn=exporter or default_export,
        unreal_fbx_export_backend=backend if backend is not None else FakeFbxBackend(),
    )
    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)
    return controller, preview_action, export_action, calls


def _fill_required_inputs(controller: RetargetWorkbenchController) -> None:
    controller.set_source_kotor_model(SimpleNamespace(name="pmbam"))
    controller.set_source_kotor_animation_slot("pause1")
    controller.set_target_unreal_skeleton(SimpleNamespace(name="UE5 Manny"))
    controller.set_retarget_profile(SimpleNamespace(name="pmbam_to_manny"))
    controller.set_output_unreal_clip_name("pmbam_pause1")


def test_kotor_to_unreal_mode_is_now_implemented() -> None:
    spec = get_retarget_mode_spec(RetargetMode.KOTOR_TO_UNREAL)

    assert spec.implemented is True
    assert spec.supports_preview is True
    assert spec.supports_export is True


def test_can_preview_requires_kotor_to_unreal_inputs() -> None:
    controller, preview_action, _export_action, _calls = _controller()

    assert controller.can_preview() is False
    controller.set_source_kotor_model(SimpleNamespace(name="source"))
    assert controller.can_preview() is False
    controller.set_source_kotor_animation_slot("pause1")
    assert controller.can_preview() is False
    controller.set_target_unreal_skeleton(SimpleNamespace(name="UE5 Manny"))
    assert controller.can_preview() is False
    controller.set_retarget_profile(SimpleNamespace(name="profile"))
    assert controller.can_preview() is False
    controller.set_output_unreal_clip_name("pmbam_pause1")

    assert controller.can_preview() is True
    assert preview_action.isEnabled() is True


def test_preview_delegates_to_kotor_to_unreal_adapter() -> None:
    controller, _preview_action, export_action, calls = _controller()
    _fill_required_inputs(controller)

    preview = controller.preview()

    assert preview.clip_name == "pmbam_pause1"
    assert calls["build"][0].source_model.name == "pmbam"
    assert calls["build"][0].source_animation_slot == "pause1"
    assert calls["build"][0].target_skeleton.name == "UE5 Manny"
    assert calls["build"][0].output_naming.unreal_clip_name == "pmbam_pause1"
    assert controller.state.last_kotor_to_unreal_preview_result.animation_clip is preview
    assert export_action.isEnabled() is True


def test_changing_ue_clip_name_invalidates_preview_and_export() -> None:
    controller, _preview_action, export_action, _calls = _controller()
    _fill_required_inputs(controller)
    controller.preview()
    controller.state.last_export_result = object()

    controller.set_output_unreal_clip_name("pmbam_pause1_new")

    assert controller.state.last_kotor_to_unreal_preview_result is None
    assert controller.state.last_export_result is None
    assert export_action.isEnabled() is False


def test_export_delegates_to_ue_export_path_and_not_mdl_writer() -> None:
    controller, _preview_action, _export_action, calls = _controller()
    _fill_required_inputs(controller)
    preview = controller.preview()

    result = controller.export_preview(Path("pmbam_pause1.fbx"), overwrite=True, write_manifest=True)

    assert result.succeeded is True
    assert len(calls["export"]) == 1
    request = calls["export"][0]
    assert request.preview_result.animation_clip is preview
    assert request.output_fbx_path == Path("pmbam_pause1.fbx")
    assert request.exporter_backend is controller.state.unreal_fbx_export_backend


def test_kotor_to_unreal_missing_backend_disables_export() -> None:
    controller, _preview_action, export_action, _calls = _controller(backend=None)
    controller.set_unreal_fbx_export_backend(None)
    _fill_required_inputs(controller)
    controller.preview()

    assert controller.can_export() is False
    assert export_action.isEnabled() is False
    assert "No FBX export backend" in controller.readiness().export_status
