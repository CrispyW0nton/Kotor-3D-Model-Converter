"""Qt retarget preview controller tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gui.qt_lib.windows.qt_retarget_preview_controller import (
    QtRetargetViewportAdapter,
    RetargetPreviewUiController,
)


class FakeAction:
    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt-style fake
        self.enabled_values.append(bool(enabled))

    def isEnabled(self) -> bool:  # noqa: N802 - Qt-style fake
        return self.enabled_values[-1] if self.enabled_values else False


class FakeViewport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def set_model(self, model) -> None:
        self.calls.append(("set_model", model))

    def set_animation_pose(self, pose, **kwargs) -> None:
        self.calls.append(("set_animation_pose", (pose, kwargs)))

    def toggle_bones(self, checked) -> None:
        self.calls.append(("toggle_bones", checked))

    def set_joint_dot_enabled(self, enabled: bool) -> None:
        self.calls.append(("set_joint_dot_enabled", enabled))


class FakeEngine:
    def __init__(self, model) -> None:
        self.model = model
        self.current_animation = None
        self.current_time = 0.0
        self.is_playing = False

    def play(self, slot_name: str, loop: bool = True, blend: bool = False) -> bool:
        self.current_animation = SimpleNamespace(name=slot_name, length=1.0)
        self.is_playing = True
        self.current_time = 0.0
        return True

    def stop(self) -> None:
        self.is_playing = False

    def seek(self, time_seconds: float) -> None:
        self.current_time = float(time_seconds)

    def evaluate(self, _time_seconds=None):
        return {"pose": self.current_time}

    def advance(self, dt: float) -> bool:
        self.current_time += float(dt)
        return self.is_playing


def _profile(slot: str = "pause1"):
    return SimpleNamespace(animation_slot=slot)


def _preview(slot: str = "pause1", warnings: list[str] | None = None):
    return SimpleNamespace(
        slot_name=slot,
        animation_block=SimpleNamespace(name=slot, length=1.25),
        solver_report=SimpleNamespace(mapped_node_count=3, generated_orientation_track_count=3),
        preview_audit=SimpleNamespace(root_drift_distance=0.0, passed=True),
        warnings=warnings or [],
    )


def test_preview_action_disabled_until_inputs_exist() -> None:
    action = FakeAction()
    controller = RetargetPreviewUiController(preview_action=action)

    assert action.isEnabled() is False

    controller.set_target_model(SimpleNamespace(name="target"))
    assert action.isEnabled() is False

    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    assert action.isEnabled() is False

    controller.set_retarget_profile(_profile())
    assert action.isEnabled() is True


def test_successful_preview_calls_core_and_viewport_adapter() -> None:
    logs: list[tuple[str, str]] = []
    statuses: list[str] = []
    applied: list[tuple[object, object, bool, bool]] = []
    built_requests = []
    action = FakeAction()
    source = SimpleNamespace(clip_name="UE_Idle")
    target = SimpleNamespace(name="target")
    profile = _profile()
    preview = _preview(warnings=["mesh deformation audit skipped", "unmapped optional role: toe_l"])

    def build(request):
        built_requests.append(request)
        return preview

    def apply(result, viewport, *, auto_play=True, show_node_overlay=True):
        applied.append((result, viewport, auto_play, show_node_overlay))

    controller = RetargetPreviewUiController(
        viewport=SimpleNamespace(name="viewport"),
        preview_action=action,
        log_callback=lambda message, level="info": logs.append((message, level)),
        status_callback=statuses.append,
        build_preview=build,
        apply_preview=apply,
    )
    controller.set_target_model(target)
    controller.set_source_clip(source)
    controller.set_retarget_profile(profile)

    result = controller.preview_retarget()

    assert result is preview
    assert built_requests[0].source_clip is source
    assert built_requests[0].target_model is target
    assert built_requests[0].profile is profile
    assert applied == [(preview, controller.viewport, True, True)]
    assert controller.state.last_preview_result is preview
    assert any("Retarget preview built successfully" in message for message, _level in logs)
    assert any("mesh deformation audit skipped" in message for message, _level in logs)
    assert any("unmapped optional role: toe_l" in message for message, _level in logs)
    assert statuses[-1] == "Retarget preview ready: pause1"
    assert action.isEnabled() is True


def test_invalid_slot_failure_does_not_touch_viewport() -> None:
    logs: list[tuple[str, str]] = []
    viewport = FakeViewport()

    def build(_request):
        raise ValueError(
            "Invalid animation slot 'UE_Run_Fwd'. UE clip names are not KOTOR animation slot names."
        )

    controller = RetargetPreviewUiController(
        viewport=viewport,
        log_callback=lambda message, level="info": logs.append((message, level)),
        build_preview=build,
    )
    controller.set_target_model(SimpleNamespace(name="target"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Run_Fwd"))
    controller.set_retarget_profile(_profile("UE_Run_Fwd"))

    assert controller.preview_retarget() is None

    assert viewport.calls == []
    assert controller.state.last_preview_result is None
    assert "UE clip names are not KOTOR animation slot names" in controller.last_error
    assert any("UE clip names are not KOTOR animation slot names" in message for message, _level in logs)


def test_preview_action_does_not_write_files(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.mdl.mdl_writer import MDLBinaryWriter
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter

    def fail(*_args, **_kwargs):
        raise AssertionError("Preview Retarget must not write MDL/MDX files")

    monkeypatch.setattr(AuroraAnimationWriter, "inject", fail)
    monkeypatch.setattr(MDLBinaryWriter, "write", fail)

    controller = RetargetPreviewUiController(
        viewport=FakeViewport(),
        build_preview=lambda _request: _preview(),
        apply_preview=lambda *_args, **_kwargs: None,
    )
    controller.set_target_model(SimpleNamespace(name="target"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    controller.set_retarget_profile(_profile())

    assert controller.preview_retarget() is not None


def test_preview_button_reenabled_after_success_and_failure() -> None:
    action = FakeAction()

    def build_success(_request):
        assert action.isEnabled() is False
        return _preview()

    controller = RetargetPreviewUiController(
        preview_action=action,
        build_preview=build_success,
        apply_preview=lambda *_args, **_kwargs: None,
    )
    controller.set_target_model(SimpleNamespace(name="target"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    controller.set_retarget_profile(_profile())

    assert controller.preview_retarget() is not None
    assert action.isEnabled() is True

    def build_failure(_request):
        assert action.isEnabled() is False
        raise RuntimeError("boom")

    controller._build_preview = build_failure
    assert controller.preview_retarget() is None
    assert action.isEnabled() is True


def test_real_viewport_adapter_maps_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.gui.windows.qt_retarget_preview_controller.AnimationEngine",
        FakeEngine,
    )
    viewport = FakeViewport()
    adapter = QtRetargetViewportAdapter(viewport)
    model = SimpleNamespace(name="preview_model")

    adapter.set_model(model)
    adapter.set_active_animation("pause1")
    adapter.set_time(0.0)
    adapter.enable_node_overlay(True)
    adapter.play()
    adapter.pause()

    call_names = [name for name, _value in viewport.calls]
    assert call_names == [
        "set_model",
        "set_animation_pose",
        "toggle_bones",
        "set_joint_dot_enabled",
        "set_animation_pose",
    ]
    assert viewport.calls[0] == ("set_model", model)
    assert viewport.calls[2] == ("toggle_bones", True)
    assert viewport.calls[3] == ("set_joint_dot_enabled", True)
