"""Retarget Workbench output naming controller tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.core.retargeting.retarget_modes import RetargetMode
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
)
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import RetargetWorkbenchController


class FakePreviewController:
    def __init__(self) -> None:
        self.state = SimpleNamespace(
            source_clip=None,
            target_model=None,
            retarget_profile=None,
            output_naming=None,
            last_preview_result=None,
            last_preview_is_current=False,
        )

    def set_source_clip(self, clip) -> None:
        self.state.source_clip = clip
        self.state.last_preview_is_current = False

    def set_target_model(self, model) -> None:
        self.state.target_model = model
        self.state.last_preview_is_current = False

    def set_retarget_profile(self, profile) -> None:
        self.state.retarget_profile = profile
        self.state.last_preview_is_current = False

    def set_output_naming(self, naming: RetargetOutputNaming | None) -> None:
        self.state.output_naming = naming
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
        naming = self.state.output_naming
        name = "pause1"
        mode = KotorOutputAnimationNameMode.VANILLA_SLOT
        requires_patch = False
        if naming is not None and naming.requested_kotor_animation_name:
            name = naming.requested_kotor_animation_name
            mode = naming.kotor_name_mode
            requires_patch = mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
        result = SimpleNamespace(
            slot_name=name,
            animation_block=SimpleNamespace(name=name),
            preview_audit=SimpleNamespace(passed=True),
            output_name_mode=mode,
            requires_custom_animation_patch=requires_patch,
        )
        self.state.last_preview_result = result
        self.state.last_preview_is_current = True
        return result

    def export_retarget_preview(self, output_mdl_path, *, overwrite: bool = False, write_manifest: bool = True):
        return SimpleNamespace(mdl_path=Path(output_mdl_path), slot_name=self.state.last_preview_result.slot_name)


def _controller() -> tuple[RetargetWorkbenchController, FakePreviewController]:
    ue = FakePreviewController()
    controller = RetargetWorkbenchController(ue_to_kotor_controller=ue)
    controller.set_target_model(SimpleNamespace(name="pmbam", animations=[SimpleNamespace(name="pause1")]))
    controller.set_source_clip(SimpleNamespace(clip_name="RunForward"))
    controller.set_retarget_profile(SimpleNamespace(animation_slot="pause1"))
    return controller, ue


def test_changing_output_naming_invalidates_preview_and_export() -> None:
    controller, ue = _controller()
    controller.set_target_kotor_animation_slot("pause1")
    preview = controller.preview()
    controller.state.last_export_result = object()

    assert preview is not None
    assert ue.state.last_preview_is_current is True

    controller.set_custom_kotor_animation_name("gr_spin_attack_01")

    assert controller.state.last_preview_result is None
    assert controller.state.last_export_result is None
    assert ue.state.last_preview_result is None
    assert ue.state.last_preview_is_current is False
    assert controller.state.output_naming is not None
    assert controller.state.output_naming.kotor_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH


def test_custom_mode_preview_uses_custom_name() -> None:
    controller, ue = _controller()

    controller.set_custom_kotor_animation_name("gr_spin_attack_01")
    preview = controller.preview()

    assert ue.state.output_naming is not None
    assert ue.state.output_naming.kotor_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
    assert preview.animation_block.name == "gr_spin_attack_01"
    assert preview.requires_custom_animation_patch is True


def test_vanilla_slot_and_custom_name_do_not_overwrite_future_source_slot() -> None:
    controller, _ue = _controller()
    controller.set_source_kotor_animation_slot("pause1")
    controller.set_custom_kotor_animation_name("gr_bek_rally")

    assert controller.state.source_kotor_animation_slot == "pause1"
    assert controller.state.output_naming is not None
    assert controller.state.output_naming.requested_kotor_animation_name == "gr_bek_rally"


def test_output_name_mode_selector_is_only_for_kotor_output_modes() -> None:
    controller, _ue = _controller()

    assert controller.current_mode_spec().mode == RetargetMode.UNREAL_TO_KOTOR
    controller.set_kotor_output_name_mode(KotorOutputAnimationNameMode.CUSTOM_PATCH)
    assert controller.state.output_naming is not None
    assert controller.state.output_naming.kotor_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH

    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)

    assert controller.can_preview() is False
    assert controller.can_export() is False
