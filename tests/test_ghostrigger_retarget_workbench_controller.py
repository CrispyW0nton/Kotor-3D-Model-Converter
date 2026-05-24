"""Qt Retarget Workbench controller tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.retargeting.retarget_modes import RetargetMode
from src.core.geometry.model_data import KotorModel, ModelNode
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode, Transform
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
            solver_options=None,
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

    def set_solver_options(self, options) -> None:
        self.state.solver_options = options
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


def _source_clip_for_auto_profile() -> SourceSkeletonClip:
    nodes = [
        SourceSkeletonNode("root", None, 0, Transform(), Transform()),
        SourceSkeletonNode("pelvis", "root", 1, Transform(), Transform()),
        SourceSkeletonNode("upperarm_l", "pelvis", 2, Transform(), Transform()),
        SourceSkeletonNode("lowerarm_l", "upperarm_l", 3, Transform(), Transform()),
        SourceSkeletonNode("hand_l", "lowerarm_l", 4, Transform(), Transform()),
    ]
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="source.fbx",
        clip_name="Idle",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
    )


def _ue5_source_clip_for_verified_auto_profile() -> SourceSkeletonClip:
    names = [
        "attach",
        "pelvis",
        "spine_01",
        "spine_03",
        "clavicle_l",
        "upperarm_l",
        "lowerarm_l",
        "hand_l",
        "middle_01_l",
        "middle_03_l",
        "thigh_l",
        "calf_l",
        "foot_l",
        "ball_l",
        "clavicle_r",
        "upperarm_r",
        "lowerarm_r",
        "hand_r",
        "middle_01_r",
        "middle_03_r",
        "thigh_r",
        "calf_r",
        "foot_r",
        "ball_r",
        "head",
    ]
    nodes = [
        SourceSkeletonNode(name, None, index, Transform(), Transform(), classification="deform")
        for index, name in enumerate(names)
    ]
    nodes[0] = SourceSkeletonNode("attach", None, 0, Transform(), Transform(), classification="helper")
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="M_Neutral_Stand_Idle_Loop_export.fbx",
        clip_name="root|Unreal Take|Base Layer",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
    )


def _mixamo_source_clip_for_verified_auto_profile() -> SourceSkeletonClip:
    names = [
        "mixamorig:Hips",
        "mixamorig:Spine",
        "mixamorig:Spine1",
        "mixamorig:Spine2",
        "mixamorig:Neck",
        "mixamorig:Head",
        "mixamorig:RightShoulder",
        "mixamorig:RightArm",
        "mixamorig:RightForeArm",
        "mixamorig:RightHand",
        "mixamorig:RightHandMiddle1",
        "mixamorig:RightHandMiddle3",
        "mixamorig:LeftShoulder",
        "mixamorig:LeftArm",
        "mixamorig:LeftForeArm",
        "mixamorig:LeftHand",
        "mixamorig:LeftHandMiddle1",
        "mixamorig:LeftHandMiddle3",
        "mixamorig:RightUpLeg",
        "mixamorig:RightLeg",
        "mixamorig:RightFoot",
        "mixamorig:RightToeBase",
        "mixamorig:LeftUpLeg",
        "mixamorig:LeftLeg",
        "mixamorig:LeftFoot",
        "mixamorig:LeftToeBase",
    ]
    nodes = [
        SourceSkeletonNode(name, None, index, Transform(), Transform(), classification="deform")
        for index, name in enumerate(names)
    ]
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="draw sword 1.fbx",
        clip_name="Armature|mixamo.com|Layer0",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
    )


def _target_model_for_auto_profile() -> KotorModel:
    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis_g")
    upper = ModelNode(name="lbicep_g")
    forearm = ModelNode(name="Lforearm_g")
    hand = ModelNode(name="Lhand_g")
    root.children = [pelvis]
    pelvis.parent = root
    pelvis.children = [upper]
    upper.parent = pelvis
    upper.children = [forearm]
    forearm.parent = upper
    forearm.children = [hand]
    hand.parent = forearm
    return KotorModel(name="pmbam", root_node=root)


def _pmbam_target_model_for_verified_auto_profile() -> KotorModel:
    nodes = {
        name: ModelNode(name=name)
        for name in [
            "PMBAM",
            "rootdummy",
            "pelvis_g",
            "torso_g",
            "torsoUpr_g",
            "lcollar_g",
            "lbicep_g",
            "Lforearm_g",
            "Lhand_g",
            "LbFngrB_g",
            "LbFngrT_g",
            "lthigh_g",
            "lshin_g",
            "lfoot_g",
            "lfootT_g",
            "rcollar_g",
            "rbicep_g",
            "Rforearm_g",
            "Rhand_g",
            "RbFngrB_g",
            "RbFngrT_g",
            "rthigh_g",
            "rshin_g",
            "rfoot_g",
            "rfootT_g",
            "headhook",
        ]
    }
    root = nodes["PMBAM"]
    for name, parent in {
        "rootdummy": "PMBAM",
        "pelvis_g": "rootdummy",
        "torso_g": "pelvis_g",
        "torsoUpr_g": "torso_g",
        "lcollar_g": "torsoUpr_g",
        "lbicep_g": "lcollar_g",
        "Lforearm_g": "lbicep_g",
        "Lhand_g": "Lforearm_g",
        "LbFngrB_g": "Lhand_g",
        "LbFngrT_g": "LbFngrB_g",
        "lthigh_g": "pelvis_g",
        "lshin_g": "lthigh_g",
        "lfoot_g": "lshin_g",
        "lfootT_g": "lfoot_g",
        "rcollar_g": "torsoUpr_g",
        "rbicep_g": "rcollar_g",
        "Rforearm_g": "rbicep_g",
        "Rhand_g": "Rforearm_g",
        "RbFngrB_g": "Rhand_g",
        "RbFngrT_g": "RbFngrB_g",
        "rthigh_g": "pelvis_g",
        "rshin_g": "rthigh_g",
        "rfoot_g": "rshin_g",
        "rfootT_g": "rfoot_g",
        "headhook": "PMBAM",
    }.items():
        nodes[name].parent = nodes[parent]
        nodes[parent].children.append(nodes[name])
    return KotorModel(name="PMBAM", root_node=root)


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


def test_kotor_to_unreal_mode_does_not_call_ue_to_kotor_or_mdl_paths_when_inputs_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("KOTOR-to-Unreal readiness must not call UE-to-KOTOR retarget/export internals")

    monkeypatch.setattr("src.core.retargeting.retarget_solver.retarget_source_clip_to_aurora_animation", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_preview.build_retarget_preview", fail)
    monkeypatch.setattr("src.core.retargeting.retarget_preview_export.export_retarget_preview_override", fail)

    controller, ue, _preview_action, _export_action = _ready_controller()

    controller.set_mode(RetargetMode.KOTOR_TO_UNREAL)

    assert controller.preview() is None
    assert controller.export_preview(Path("clip.fbx")) is None

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


def test_unreal_to_kotor_auto_generates_initial_profile_when_source_and_target_are_set() -> None:
    preview_action = FakeAction()
    export_action = FakeAction()
    ue = FakePreviewController()
    controller = RetargetWorkbenchController(
        ue_to_kotor_controller=ue,
        preview_action=preview_action,
        export_action=export_action,
    )

    controller.set_source_clip(_source_clip_for_auto_profile())
    controller.set_target_model(_target_model_for_auto_profile())

    profile = controller.state.retarget_profile
    assert profile is not None
    assert controller.state.retarget_profile_is_auto is True
    assert ue.state.retarget_profile is profile
    assert {entry.target_node for entry in profile.mappings} >= {"pelvis_g", "lbicep_g", "Lforearm_g", "Lhand_g"}
    assert controller.can_preview() is True


def test_unreal_to_kotor_auto_generates_verified_ue5_profile_and_solver_options() -> None:
    ue = FakePreviewController()
    controller = RetargetWorkbenchController(ue_to_kotor_controller=ue)

    controller.set_source_clip(_ue5_source_clip_for_verified_auto_profile())
    controller.set_target_model(_pmbam_target_model_for_verified_auto_profile())

    profile = controller.state.retarget_profile
    assert profile is not None
    assert profile.metadata["generated_by"] == "verified_ue5_to_aurora_mapping"
    assert profile.metadata["recommended_rotation_transfer_mode"] == "exact_segment_correction"
    assert {entry.target_node for entry in profile.mappings} >= {
        "rootdummy",
        "pelvis_g",
        "torso_g",
        "torsoUpr_g",
        "Lforearm_g",
        "Lhand_g",
        "LbFngrB_g",
        "LbFngrT_g",
        "Rforearm_g",
        "Rhand_g",
        "RbFngrB_g",
        "RbFngrT_g",
        "lfootT_g",
        "rfootT_g",
    }
    assert "headhook" not in {entry.target_node.lower() for entry in profile.mappings}
    assert controller.state.solver_options is not None
    assert controller.state.solver_options.rotation_transfer_mode == "exact_segment_correction"
    assert controller.state.solver_options.key_unmapped_reference_nodes is True
    assert ue.state.retarget_profile is profile
    assert ue.state.solver_options is controller.state.solver_options


def test_unreal_to_kotor_auto_generates_verified_mixamo_profile_and_solver_options() -> None:
    ue = FakePreviewController()
    controller = RetargetWorkbenchController(ue_to_kotor_controller=ue)

    controller.set_source_clip(_mixamo_source_clip_for_verified_auto_profile())
    controller.set_target_model(_pmbam_target_model_for_verified_auto_profile())

    profile = controller.state.retarget_profile
    assert profile is not None
    assert profile.metadata["generated_by"] == "verified_mixamo_to_aurora_mapping"
    assert profile.metadata["source_skeleton_family"] == "mixamo"
    assert profile.metadata["recommended_rotation_transfer_mode"] == "exact_segment_correction"
    assert {entry.target_node for entry in profile.mappings} >= {
        "pelvis_g",
        "torso_g",
        "torsoUpr_g",
        "Lforearm_g",
        "Lhand_g",
        "Rforearm_g",
        "Rhand_g",
        "lfoot_g",
        "rfoot_g",
    }
    assert "handconjure" not in {entry.target_node.lower() for entry in profile.mappings}
    assert controller.state.solver_options is not None
    assert controller.state.solver_options.rotation_transfer_mode == "exact_segment_correction"
    assert ue.state.retarget_profile is profile
    assert ue.state.solver_options is controller.state.solver_options


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


def test_selecting_kotor_to_unreal_mode_updates_controller_status_and_buttons() -> None:
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
    assert "FBX backend export" in statuses[-1]
