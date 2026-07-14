"""Qt controller coverage for exporting an approved retarget preview."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.core.retargeting.retarget_preview_export import RetargetPreviewExportResult
from src.gui.qt_lib.windows.qt_retarget_preview_controller import RetargetPreviewUiController


class FakeAction:
    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt-style fake
        self.enabled_values.append(bool(enabled))

    def isEnabled(self) -> bool:  # noqa: N802 - Qt-style fake
        return self.enabled_values[-1] if self.enabled_values else False


def _profile(slot: str = "pause1"):
    return SimpleNamespace(animation_slot=slot)


def _preview(slot: str = "pause1", *, passed: bool = True):
    return SimpleNamespace(
        slot_name=slot,
        animation_block=SimpleNamespace(name=slot, length=1.0),
        solver_report=SimpleNamespace(mapped_node_count=2, generated_orientation_track_count=2),
        preview_audit=SimpleNamespace(passed=passed, root_drift_distance=0.0),
        warnings=[],
    )


def _export_result(path: Path):
    return RetargetPreviewExportResult(
        mdl_path=path,
        mdx_path=path.with_suffix(".mdx"),
        manifest_path=path.with_suffix(".retarget_preview.json"),
        slot_name="pause1",
        verified_roundtrip=True,
        warnings=["writer warning"],
    )


def _ready_controller(*, build_preview=None, export_preview=None, resource_manager_provider=None):
    preview_action = FakeAction()
    export_action = FakeAction()
    controller = RetargetPreviewUiController(
        preview_action=preview_action,
        export_action=export_action,
        build_preview=build_preview or (lambda _request: _preview()),
        apply_preview=lambda *_args, **_kwargs: None,
        export_preview=export_preview or (lambda request: _export_result(request.output_mdl_path)),
        resource_manager_provider=resource_manager_provider,
    )
    controller.set_target_model(SimpleNamespace(name="pmbam"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    controller.set_retarget_profile(_profile())
    return controller, preview_action, export_action


def test_export_action_disabled_until_successful_current_preview() -> None:
    preview_action = FakeAction()
    export_action = FakeAction()
    controller = RetargetPreviewUiController(
        preview_action=preview_action,
        export_action=export_action,
        build_preview=lambda _request: _preview(),
        apply_preview=lambda *_args, **_kwargs: None,
    )

    assert export_action.isEnabled() is False

    controller.set_target_model(SimpleNamespace(name="pmbam"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    controller.set_retarget_profile(_profile())
    assert preview_action.isEnabled() is True
    assert export_action.isEnabled() is False

    assert controller.preview_retarget() is not None
    assert export_action.isEnabled() is True

    controller.set_source_clip(SimpleNamespace(clip_name="UE_Run"))
    assert export_action.isEnabled() is False

    controller._build_preview = lambda _request: (_ for _ in ()).throw(RuntimeError("boom"))
    assert controller.preview_retarget() is None
    assert export_action.isEnabled() is False


def test_export_action_calls_core_helper(tmp_path: Path) -> None:
    logs: list[tuple[str, str]] = []
    exports = []
    resource_manager = object()

    def export_preview(request):
        exports.append(request)
        return _export_result(request.output_mdl_path)

    controller, _preview_action, export_action = _ready_controller(
        export_preview=export_preview,
        resource_manager_provider=lambda: resource_manager,
    )
    controller.log_callback = lambda message, level="info": logs.append((message, level))

    preview = controller.preview_retarget()
    result = controller.export_retarget_preview(tmp_path / "pmbam.mdl", overwrite=True)

    assert result is not None
    assert exports[0].preview_result is preview
    assert exports[0].verify_roundtrip is True
    assert exports[0].output_mdx_path == tmp_path / "pmbam.mdx"
    assert exports[0].resource_manager is resource_manager
    assert any("Retarget preview exported successfully" in message for message, _level in logs)
    assert any("writer warning" in message for message, _level in logs)
    assert export_action.isEnabled() is True


def test_stale_preview_cannot_export(tmp_path: Path) -> None:
    exports = []
    controller, _preview_action, _export_action = _ready_controller(
        export_preview=lambda request: exports.append(request) or _export_result(request.output_mdl_path)
    )
    controller.preview_retarget()

    controller.set_retarget_profile(_profile("pause2"))
    result = controller.export_retarget_preview(tmp_path / "pmbam.mdl", overwrite=True)

    assert result is None
    assert exports == []
    assert "preview is stale" in controller.last_error
    assert "Run Preview Retarget again" in controller.last_error


def test_export_failure_reports_error_and_keeps_preview(tmp_path: Path) -> None:
    def export_preview(_request):
        raise RuntimeError("roundtrip failed")

    controller, _preview_action, _export_action = _ready_controller(export_preview=export_preview)
    preview = controller.preview_retarget()

    result = controller.export_retarget_preview(tmp_path / "pmbam.mdl", overwrite=True)

    assert result is None
    assert controller.state.last_preview_result is preview
    assert controller.last_error == "roundtrip failed"


def test_export_does_not_rebuild_preview_or_touch_viewport(tmp_path: Path) -> None:
    controller, _preview_action, _export_action = _ready_controller()
    controller.preview_retarget()
    controller._build_preview = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("export must not rebuild preview")
    )
    controller._apply_preview = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("export must not mutate viewport")
    )

    assert controller.export_retarget_preview(tmp_path / "pmbam.mdl", overwrite=True) is not None
