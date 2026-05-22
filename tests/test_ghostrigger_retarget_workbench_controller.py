"""Qt Retarget Workbench controller tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.retargeting.retarget_modes import RetargetMode
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import (
    RetargetWorkbenchController,
    RetargetWorkbenchError,
    combo_current_retarget_mode,
    populate_retarget_mode_combo,
)


class FakeAction:
    def __init__(self) -> None:
        self.enabled_values: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt-style fake
        self.enabled_values.append(bool(enabled))

    def isEnabled(self) -> bool:  # noqa: N802 - Qt-style fake
        return self.enabled_values[-1] if self.enabled_values else False


class FakePreviewController:
    def __init__(self) -> None:
        self.state = SimpleNamespace(
            source_clip=None,
            target_model=None,
            retarget_profile=None,
            last_preview_result=None,
            last_preview_is_current=False,
        )
        self.preview_calls: list[tuple[bool, bool]] = []
        self.export_calls: list[tuple[Path, bool, bool]] = []

    def set_source_clip(self, clip) -> None:
        self.state.source_clip = clip
        self.state.last_preview_is_current = False

    def set_target_model(self, model) -> None:
        self.state.target_model = model
        self.state.last_preview_is_current = False

    def set_retarget_profile(self, profile) -> None:
        self.state.retarget_profile = profile
        self.state.last_preview_is_current = False

    def current_target_model(self):
        return self.state.target_model

    def can_preview(self) -> bool:
        return bool(self.state.source_clip and self.state.target_model and self.state.retarget_profile)

    def can_export(self) -> bool:
        return bool(self.state.last_preview_result and self.state.last_preview_is_current)

    def update_enabled(self) -> None:
        pass

    def preview_retarget(self, *, auto_play: bool = True, show_node_overlay: bool = True):
        self.preview_calls.append((auto_play, show_node_overlay))
        result = SimpleNamespace(slot_name="pause1", preview_audit=SimpleNamespace(passed=True))
        self.state.last_preview_result = result
        self.state.last_preview_is_current = True
        return result

    def export_retarget_preview(self, output_mdl_path, *, overwrite: bool = False, write_manifest: bool = True):
        self.export_calls.append((Path(output_mdl_path), overwrite, write_manifest))
        return SimpleNamespace(mdl_path=Path(output_mdl_path), slot_name="pause1")


class FakeCombo:
    def __init__(self) -> None:
        self.object_name = ""
        self.items: list[tuple[str, object]] = []
        self.index = -1
        self.tooltip = ""

    def setObjectName(self, name: str) -> None:  # noqa: N802 - Qt-style fake
        self.object_name = name

    def clear(self) -> None:
        self.items.clear()
        self.index = -1

    def addItem(self, label: str, data=None) -> None:  # noqa: N802 - Qt-style fake
        self.items.append((label, data))

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - Qt-style fake
        self.index = index

    def currentData(self):  # noqa: N802 - Qt-style fake
        return self.items[self.index][1]

    def currentText(self) -> str:  # noqa: N802 - Qt-style fake
        return self.items[self.index][0]

    def setToolTip(self, text: str) -> None:  # noqa: N802 - Qt-style fake
        self.tooltip = text


def _ready_controller() -> tuple[RetargetWorkbenchController, FakePreviewController, FakeAction, FakeAction]:
    preview_action = FakeAction()
    export_action = FakeAction()
    ue = FakePreviewController()
    controller = RetargetWorkbenchController(
        ue_to_kotor_controller=ue,
        preview_action=preview_action,
        export_action=export_action,
    )
    controller.set_target_model(SimpleNamespace(name="pmbam"))
    controller.set_source_clip(SimpleNamespace(clip_name="UE_Idle"))
    controller.set_retarget_profile(SimpleNamespace(animation_slot="pause1"))
    return controller, ue, preview_action, export_action


def test_mode_switch_invalidates_preview_and_export() -> None:
    controller, ue, _preview_action, export_action = _ready_controller()
    preview = controller.preview()
    export = controller.export_preview(Path("pmbam.mdl"), overwrite=True)

    assert preview is not None
    assert export is not None
    assert export_action.isEnabled() is True

    previous_revision = controller.state.dirty_revision
    controller.set_mode(RetargetMode.KOTOR_TO_KOTOR)

    assert controller.state.last_preview_result is None
    assert controller.state.last_export_result is None
    assert ue.state.last_preview_result is None
    assert ue.state.last_preview_is_current is False
    assert controller.state.dirty_revision == previous_revision + 1
    assert export_action.isEnabled() is False


def test_unimplemented_modes_do_not_call_solvers_or_writers(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("pending workbench modes must not call retarget/export internals")

    monkeypatch.setattr("src.core.retargeting.retarget_solver.retarget_source_clip_to_aurora_animation", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_preview.build_retarget_preview", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_preview_export.export_retarget_preview_override", fail)

    controller, ue, _preview_action, _export_action = _ready_controller()

    controller.set_mode(RetargetMode.KOTOR_TO_KOTOR)
    with pytest.raises(RetargetWorkbenchError, match="KOTOR → KOTOR preview is not implemented yet"):
        controller.preview()
    with pytest.raises(RetargetWorkbenchError, match="KOTOR → KOTOR preview is not implemented yet"):
        controller.export_preview(Path("pmbam.mdl"))

    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)
    with pytest.raises(RetargetWorkbenchError, match="KOTOR → Unreal export is not implemented yet"):
        controller.preview()
    with pytest.raises(RetargetWorkbenchError, match="KOTOR → Unreal export is not implemented yet"):
        controller.export_preview(Path("clip.fbx"))

    assert ue.preview_calls == []
    assert ue.export_calls == []


def test_unreal_to_kotor_delegates_to_existing_preview_and_export() -> None:
    controller, ue, _preview_action, export_action = _ready_controller()

    preview = controller.preview(auto_play=False, show_node_overlay=False)
    export = controller.export_preview(Path("pmbam.mdl"), overwrite=True, write_manifest=False)

    assert preview is ue.state.last_preview_result
    assert ue.preview_calls == [(False, False)]
    assert export.mdl_path == Path("pmbam.mdl")
    assert ue.export_calls == [(Path("pmbam.mdl"), True, False)]
    assert controller.state.last_preview_result is preview
    assert controller.state.last_export_result is export
    assert export_action.isEnabled() is True


def test_mode_dropdown_contains_all_modes_and_defaults_to_unreal_to_kotor() -> None:
    combo = FakeCombo()

    populate_retarget_mode_combo(combo)

    assert combo.object_name == "retargetModeComboBox"
    assert [label for label, _data in combo.items] == [
        "KOTOR → KOTOR",
        "KOTOR → Unreal",
        "Unreal → KOTOR",
    ]
    assert combo_current_retarget_mode(combo) == RetargetMode.UNREAL_TO_KOTOR
    assert "verified GhostRigger" in combo.tooltip


def test_selecting_pending_mode_updates_controller_status_and_buttons() -> None:
    controller, _ue, preview_action, export_action = _ready_controller()
    logs: list[tuple[str, str]] = []
    statuses: list[str] = []
    controller.log_callback = lambda message, level="info": logs.append((message, level))
    controller.status_callback = statuses.append

    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)

    assert controller.state.mode == RetargetMode.KOTOR_TO_UNREAL
    assert "UE-compatible FBX animation clip" in controller.mode_status_text()
    assert preview_action.isEnabled() is False
    assert export_action.isEnabled() is False
    assert any("Retarget mode changed to KOTOR → Unreal" in message for message, _level in logs)
    assert "pending UE FBX export adapter" in statuses[-1]
