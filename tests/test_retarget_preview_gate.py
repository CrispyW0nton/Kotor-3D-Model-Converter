"""In-memory retarget preview gate tests."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.core.animation.animation_engine import SuperModelResolver, evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.coordinate import BasisConversion
from src.core.retargeting.retarget_preview import (
    RetargetPreviewError,
    RetargetPreviewRequest,
    apply_retarget_preview_to_viewport,
    audit_retarget_preview_animation,
    build_retarget_preview,
    capture_retarget_preview_angles,
)
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.retarget_solver import RetargetSolverOptions
from src.core.retargeting.source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
    normalize_quat_xyzw,
    quat_dot_xyzw,
    quat_to_matrix_xyzw,
)
from src.core.retargeting.ue5_to_aurora_r3b_preview import (
    _continuity_aligned_terminal_basis,
    _mapped_exact_segments,
    _mapped_terminal_twist_chains,
    apply_verified_pmbam_segment_pose_correction,
    _terminal_chain_basis,
)


def _quat_axis(axis: str, degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    s = math.sin(radians / 2.0)
    c = math.cos(radians / 2.0)
    if axis.upper() == "X":
        return (s, 0.0, 0.0, c)
    if axis.upper() == "Y":
        return (0.0, s, 0.0, c)
    if axis.upper() == "Z":
        return (0.0, 0.0, s, c)
    raise ValueError(axis)


def _quat_neg(quat: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return tuple(-value for value in quat)  # type: ignore[return-value]


def _source_clip(
    node_defs: list[tuple[str, str | None]],
    pose_globals: list[dict[str, Transform]],
    *,
    duration: float | None = None,
) -> SourceSkeletonClip:
    def local_transforms(globals_by_name: dict[str, Transform]) -> dict[str, Transform]:
        matrices = {name: transform.to_matrix() for name, transform in globals_by_name.items()}
        local: dict[str, Transform] = {}
        for name, parent in node_defs:
            local_matrix = matrices[name] if parent is None else np.linalg.inv(matrices[parent]) @ matrices[name]
            local[name] = Transform.from_matrix(local_matrix)
        return local

    clip_duration = float(duration if duration is not None else max(0, len(pose_globals) - 1))
    times = [0.0] if len(pose_globals) == 1 else [clip_duration * i / (len(pose_globals) - 1) for i in range(len(pose_globals))]
    poses = [
        SourcePose(time_seconds=time_value, global_transforms=globals_by_name, local_transforms=local_transforms(globals_by_name))
        for time_value, globals_by_name in zip(times, pose_globals)
    ]
    nodes = [
        SourceSkeletonNode(
            name=name,
            parent_name=parent,
            index=index,
            rest_local=poses[0].local_transforms[name],
            rest_global=poses[0].global_transforms[name],
            classification="root" if parent is None else "deform",
        )
        for index, (name, parent) in enumerate(node_defs)
    ]
    return SourceSkeletonClip(
        source_path="fake.fbx",
        clip_name="UE_Test",
        duration_seconds=clip_duration,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=poses[0],
        sampled_poses=poses,
        axis_system="TEST_SOURCE_AXIS",
        unit_scale_to_meters=1.0,
    )


def _target_model(
    entries: list[tuple[str, str | None, tuple[float, float, float], tuple[float, float, float, float] | None]],
    *,
    anims: tuple[str, ...] = ("pause1",),
) -> KotorModel:
    nodes = {
        name: ModelNode(name=name, position=position, rotation=rotation or (0.0, 0.0, 0.0, 1.0))
        for name, _parent, position, rotation in entries
    }
    for name, parent, _pos, _rot in entries:
        if parent:
            nodes[name].parent = nodes[parent]
            nodes[parent].children.append(nodes[name])
    return KotorModel(
        name="target",
        root_node=nodes[entries[0][0]],
        animations=[Animation(name=name, length=1.0) for name in anims],
    )


def _profile(mappings: list[RetargetMappingEntry], *, slot: str = "pause1") -> RetargetProfile:
    return RetargetProfile(
        name="preview_profile",
        animation_slot=slot,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=mappings,
    )


class FakeViewport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def set_model(self, model) -> None:
        self.calls.append(("set_model", model.name))

    def set_active_animation(self, slot_name: str) -> None:
        self.calls.append(("set_active_animation", slot_name))

    def set_time(self, time_seconds: float) -> None:
        self.calls.append(("set_time", time_seconds))

    def play(self) -> None:
        self.calls.append(("play", None))

    def pause(self) -> None:
        self.calls.append(("pause", None))

    def enable_node_overlay(self, enabled: bool) -> None:
        self.calls.append(("enable_node_overlay", enabled))

    def set_camera_preset(self, preset: str) -> None:
        self.calls.append(("set_camera_preset", preset))

    def capture_viewport(self, path: Path) -> Path:
        self.calls.append(("capture_viewport", Path(path).name))
        return Path(path)


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_preview_builds_in_memory_local_override() -> None:
    source = _source_clip(
        [("root", None)],
        [{"root": Transform()}, {"root": Transform(rotation=_quat_axis("Z", 30.0))}],
    )
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)], anims=("pause1",))
    original_animation_names = [animation.name for animation in target.animations]
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    assert preview.animation_block.name == "pause1"
    assert any(animation.name == "pause1" for animation in preview.preview_model.animations)
    assert [animation.name for animation in target.animations] == original_animation_names
    assert preview.preview_model is not target


def test_inherited_slot_is_overridden_locally_in_preview() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)], anims=())
    supermodel = KotorModel(name="S_Test", animations=[Animation(name="pause1", length=1.0)])
    target.supermodel = "S_Test"
    SuperModelResolver.prime_cache("S_Test", supermodel)
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    local_pause = [animation for animation in preview.preview_model.animations if animation.name == "pause1"]
    assert len(local_pause) == 1
    resolved, _scale = SuperModelResolver.resolve_animation(preview.preview_model, "pause1")
    assert resolved is local_pause[0]


def test_invalid_slot_fails_before_viewport_mutation() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)], anims=("pause1",))
    profile = _profile([RetargetMappingEntry("root", "root", "root")], slot="UE_Run_Fwd")
    viewport = FakeViewport()

    with pytest.raises(RetargetPreviewError, match="UE clip names are not KOTOR animation slot names"):
        preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
        apply_retarget_preview_to_viewport(preview, viewport)

    assert viewport.calls == []


def test_apply_preview_to_viewport_calls_expected_methods() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])
    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
    viewport = FakeViewport()

    apply_retarget_preview_to_viewport(preview, viewport, auto_play=True, show_node_overlay=True)

    assert [name for name, _value in viewport.calls] == [
        "set_model",
        "set_active_animation",
        "set_time",
        "enable_node_overlay",
        "play",
    ]
    assert viewport.calls[1] == ("set_active_animation", "pause1")

    paused_viewport = FakeViewport()
    apply_retarget_preview_to_viewport(preview, paused_viewport, auto_play=False)
    assert paused_viewport.calls[-1] == ("pause", None)


def test_preview_audit_catches_nan_transform() -> None:
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            ModelNode(
                name="root",
                controllers=[
                    {
                        "type": 20,
                        "name": "orientation",
                        "columns": 4,
                        "times": [0.0],
                        "values": [[float("nan"), 0.0, 0.0, 1.0]],
                    }
                ],
            )
        ],
    )

    audit = audit_retarget_preview_animation(model=target, animation_block=animation)

    assert audit.passed is False
    assert any("non-finite" in failure for failure in audit.finite_transform_failures)


def test_non_root_translations_are_stable() -> None:
    source = _source_clip(
        [("root", None), ("forearm_l", "root")],
        [
            {"root": Transform(), "forearm_l": Transform(position=(1.0, 2.0, 3.0))},
            {"root": Transform(), "forearm_l": Transform(position=(9.0, 8.0, 7.0))},
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lforearm", "root", (1.0, 2.0, 3.0), None),
        ]
    )
    profile = _profile([RetargetMappingEntry("forearm", "forearm_l", "lforearm", side="left")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
    pose = evaluate_aurora_animation_pose(preview.preview_model, preview.animation_block, 1.0)

    assert preview.preview_audit.non_root_translation_deviations == []
    assert pose.local_transforms_by_node["lforearm"].position == pytest.approx((1.0, 2.0, 3.0))


def test_root_drift_stripped_by_default() -> None:
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform(position=(0.0, 0.0, 0.0))},
            {"root": Transform(position=(100.0, 0.0, 0.0))},
        ],
    )
    target = _target_model([("root", None, (5.0, 6.0, 7.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    assert preview.preview_audit.root_drift_distance <= 1e-4
    assert preview.solver_report.stripped_root_translation is True


def test_quaternion_continuity_survives_preview_path() -> None:
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform(rotation=_quat_axis("Z", 10.0))},
            {"root": Transform(rotation=_quat_neg(_quat_axis("Z", 20.0)))},
        ],
    )
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
    values = preview.animation_block.nodes[0].controllers[0]["values"]

    assert quat_dot_xyzw(values[0], values[1]) >= 0.0
    assert preview.preview_audit.passed is True


def test_preview_does_not_write_files(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.mdl.mdl_writer import MDLBinaryWriter
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter

    def fail(*_args, **_kwargs):
        raise AssertionError("preview must not write files")

    monkeypatch.setattr(AuroraAnimationWriter, "inject", fail)
    monkeypatch.setattr(MDLBinaryWriter, "write", fail)

    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    assert preview.slot_name == "pause1"


def test_verified_ue5_profile_uses_r3b_writer_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("root", None), ("upperarm_l", "root")],
        [
            {
                "root": Transform(),
                "upperarm_l": Transform(position=(1.0, 0.0, 0.0), rotation=_quat_axis("Y", 10.0)),
            },
            {
                "root": Transform(),
                "upperarm_l": Transform(position=(1.0, 0.0, 0.0), rotation=_quat_axis("Y", 35.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "rootdummy", (1.0, 0.0, 0.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("root", "root", "rootdummy"),
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
        ]
    )
    profile.name = "verified_ue5_to_aurora_profile"
    profile.metadata["generated_by"] = "verified_ue5_to_aurora_mapping"

    def fail_generic_solver(*_args, **_kwargs):
        raise AssertionError("verified UE5 -> Aurora preview must not use the generic solver")

    captured: dict[str, object] = {}

    def fake_build_animation(self, *, payload, model, slot_name, **kwargs):
        captured["payload"] = payload
        captured["slot_name"] = slot_name
        captured["kwargs"] = kwargs
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr("src.core.retargeting.retarget_preview.retarget_source_clip_to_aurora_animation", fail_generic_solver)
    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    payload = captured["payload"]
    assert preview.slot_name == "pause1"
    assert captured["slot_name"] == "pause1"
    assert captured["kwargs"]["source_reference_mode"] == "hybrid_limb_source_rest"
    assert set(payload["target_curves"]) == {"rootdummy", "lbicep_g"}
    assert payload["target_curves"]["lbicep_g"]["source_bone"] == "upperarm_l"
    assert payload["target_curves"]["lbicep_g"]["source_parent"] == "root"
    assert payload["target_curves"]["lbicep_g"]["source_parent_frames"]
    assert any("R3.B hybrid local-basis" in warning for warning in preview.warnings)


def test_verified_mixamo_profile_passes_source_rest_reference_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("mixamorig:Hips", None)],
        [{"mixamorig:Hips": Transform()}, {"mixamorig:Hips": Transform()}],
    )
    target = _target_model([("pelvis_g", None, (0.0, 0.0, 0.0), None)], anims=("pause1",))
    profile = _profile([RetargetMappingEntry("pelvis", "mixamorig:Hips", "pelvis_g")])
    profile.name = "verified_mixamo_to_aurora_profile"
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_reference_mode"] = "source_rest"

    captured: dict[str, object] = {}

    def fake_build_animation(self, *, payload, model, slot_name, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    assert captured["kwargs"]["source_reference_mode"] == "source_rest"
    assert captured["payload"]["metadata"]["source_quaternion_conversion"] == "ue5_to_aurora"


def test_verified_mixamo_profile_passes_identity_quaternion_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("mixamorig:Hips", None)],
        [{"mixamorig:Hips": Transform()}, {"mixamorig:Hips": Transform()}],
    )
    target = _target_model([("pelvis_g", None, (0.0, 0.0, 0.0), None)], anims=("pause1",))
    profile = _profile([RetargetMappingEntry("pelvis", "mixamorig:Hips", "pelvis_g")])
    profile.name = "verified_mixamo_to_aurora_profile"
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_reference_mode"] = "source_rest"
    profile.metadata["source_quaternion_conversion"] = "blender_identity"

    captured: dict[str, object] = {}

    def fake_build_animation(self, *, payload, model, slot_name, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    build_retarget_preview(RetargetPreviewRequest(source, target, profile))

    assert captured["kwargs"]["source_reference_mode"] == "source_rest"
    assert captured["payload"]["metadata"]["source_quaternion_conversion"] == "blender_identity"


def test_verified_mixamo_root_motion_moves_target_root_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("armature_root", None), ("mixamorig:Hips", "armature_root")],
        [
            {
                "armature_root": Transform(),
                "mixamorig:Hips": Transform(position=(0.0, 0.0, 0.0)),
            },
            {
                "armature_root": Transform(),
                "mixamorig:Hips": Transform(position=(2.0, 0.0, 0.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("PMBAM", None, (0.0, 0.0, 0.0), None),
            ("pelvis_g", "PMBAM", (0.0, 0.0, 1.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile([RetargetMappingEntry("pelvis", "mixamorig:Hips", "pelvis_g")])
    profile.name = "verified_mixamo_to_aurora_profile"
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_reference_mode"] = "source_rest"

    def fake_build_animation(self, *, model, slot_name, **_kwargs):
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    preview = build_retarget_preview(
        RetargetPreviewRequest(
            source,
            target,
            profile,
            solver_options=RetargetSolverOptions(root_translation_policy="copy_source_root"),
        )
    )

    root_node = next(node for node in preview.animation_block.nodes if node.name == "PMBAM")
    pelvis_node = next(node for node in preview.animation_block.nodes if node.name == "pelvis_g")
    root_position = next(controller for controller in root_node.controllers if controller["name"] == "position")

    assert root_position["values"] == [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
    assert all(controller["name"] != "position" for controller in pelvis_node.controllers)
    assert preview.preview_audit.passed is True
    assert preview.preview_audit.allow_root_motion is True
    assert preview.solver_report.generated_position_track_count == 1
    assert preview.solver_report.stripped_root_translation is False
    assert any("root movement enabled" in warning for warning in preview.warnings)


def test_verified_mixamo_root_motion_stays_in_place_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("mixamorig:Hips", None)],
        [
            {"mixamorig:Hips": Transform(position=(0.0, 0.0, 0.0))},
            {"mixamorig:Hips": Transform(position=(2.0, 0.0, 0.0))},
        ],
    )
    target = _target_model([("PMBAM", None, (0.0, 0.0, 0.0), None), ("pelvis_g", "PMBAM", (0.0, 0.0, 1.0), None)])
    profile = _profile([RetargetMappingEntry("pelvis", "mixamorig:Hips", "pelvis_g")])
    profile.name = "verified_mixamo_to_aurora_profile"
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_reference_mode"] = "source_rest"

    def fake_build_animation(self, *, model, slot_name, **_kwargs):
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
    root_node = next(node for node in preview.animation_block.nodes if node.name == "PMBAM")

    assert all(controller["name"] != "position" for controller in root_node.controllers)
    assert preview.preview_audit.root_drift_distance <= 1e-4
    assert preview.preview_audit.allow_root_motion is False
    assert preview.solver_report.generated_position_track_count == 0
    assert preview.solver_report.stripped_root_translation is True


def test_verified_ue5_profile_applies_exact_segment_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.retargeting.aurora_animation_writer import AuroraAnimationWriter, CTRL_ORIENTATION

    source = _source_clip(
        [("root", None), ("upperarm_l", "root"), ("lowerarm_l", "upperarm_l")],
        [
            {
                "root": Transform(),
                "upperarm_l": Transform(position=(1.0, 0.0, 0.0)),
                "lowerarm_l": Transform(position=(2.0, 0.0, 0.0)),
            },
            {
                "root": Transform(),
                "upperarm_l": Transform(position=(1.0, 0.0, 0.0)),
                "lowerarm_l": Transform(position=(1.0, 1.0, 0.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "rootdummy", (1.0, 0.0, 0.0), None),
            ("Lforearm_g", "lbicep_g", (1.0, 0.0, 0.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("root", "root", "rootdummy"),
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "Lforearm_g", side="left"),
        ]
    )
    profile.metadata["generated_by"] = "verified_ue5_to_aurora_mapping"

    def fake_build_animation(self, *, model, slot_name, **_kwargs):
        return Animation(
            name=slot_name,
            length=source.duration_seconds,
            anim_root=model.root_node.name,
            nodes=[
                ModelNode(
                    name=node.name,
                    controllers=[
                        {
                            "type": CTRL_ORIENTATION,
                            "name": "orientation",
                            "columns": 4,
                            "times": [0.0, 1.0],
                            "values": [list(node.rotation), list(node.rotation)],
                        }
                    ],
                )
                for node in model.all_nodes()
            ],
        )

    monkeypatch.setattr(AuroraAnimationWriter, "build_animation_from_r3a", fake_build_animation)
    monkeypatch.setattr(AuroraAnimationWriter, "_validate_export_motion_amplitude", lambda *_args, **_kwargs: [])

    preview = build_retarget_preview(RetargetPreviewRequest(source, target, profile))
    pose = evaluate_aurora_animation_pose(preview.preview_model, preview.animation_block, 1.0)
    parent = np.asarray(pose.world_transforms_by_node["lbicep_g"].position)
    child = np.asarray(pose.world_transforms_by_node["Lforearm_g"].position)
    actual = child - parent
    actual = actual / np.linalg.norm(actual)

    assert actual == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert any("exact KOTOR humanoid segment correction" in warning for warning in preview.warnings)


def test_verified_mixamo_segment_correction_uses_visible_blender_basis() -> None:
    source = _source_clip(
        [
            ("mixamorig:RightArm", None),
            ("mixamorig:RightForeArm", "mixamorig:RightArm"),
        ],
        [
            {
                "mixamorig:RightArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightForeArm": Transform(position=(1.0, 0.0, 0.0)),
            },
            {
                "mixamorig:RightArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightForeArm": Transform(position=(0.0, 1.0, 0.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("rbicep_g", "rootdummy", (1.0, 0.0, 0.0), None),
            ("Rforearm_g", "rbicep_g", (1.0, 0.0, 0.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("upperarm", "mixamorig:RightArm", "rbicep_g", side="right"),
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_reference_mode"] = "hybrid_limb_source_rest"

    preview = build_retarget_preview(
        RetargetPreviewRequest(
            source,
            target,
            profile,
            solver_options=RetargetSolverOptions(
                rotation_transfer_mode="exact_segment_correction",
                key_unmapped_reference_nodes=True,
                source_reference_mode="hybrid_limb_source_rest",
                basis_conversion=None,
            ),
        )
    )

    pose = evaluate_aurora_animation_pose(preview.preview_model, preview.animation_block, 1.0)
    parent = np.asarray(pose.world_transforms_by_node["rbicep_g"].position)
    child = np.asarray(pose.world_transforms_by_node["Rforearm_g"].position)
    actual = child - parent
    actual = actual / np.linalg.norm(actual)

    assert actual == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert any("exact KOTOR humanoid segment correction" in warning for warning in preview.warnings)


def test_verified_mixamo_stable_policy_keeps_spine_but_softens_clavicle_exact_correction() -> None:
    profile = _profile(
        [
            RetargetMappingEntry("spine", "mixamorig:Spine", "torso_g", side="center"),
            RetargetMappingEntry("chest", "mixamorig:Spine2", "torsoUpr_g", side="center"),
            RetargetMappingEntry("clavicle", "mixamorig:RightShoulder", "rcollar_g", side="right"),
            RetargetMappingEntry("upperarm", "mixamorig:RightArm", "rbicep_g", side="right"),
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
            RetargetMappingEntry("hand", "mixamorig:RightHand", "Rhand_g", side="right"),
            RetargetMappingEntry("index_base", "mixamorig:RightHandIndex1", "RaFngrB_g", side="right"),
            RetargetMappingEntry("index_tip", "mixamorig:RightHandIndex3", "RaFngrT_g", side="right"),
            RetargetMappingEntry("middle_base", "mixamorig:RightHandMiddle1", "RbFngrB_g", side="right"),
            RetargetMappingEntry("middle_tip", "mixamorig:RightHandMiddle3", "RbFngrT_g", side="right"),
            RetargetMappingEntry("ring_base", "mixamorig:RightHandRing1", "RcFngrB_g", side="right"),
            RetargetMappingEntry("ring_tip", "mixamorig:RightHandRing3", "RcFngrT_g", side="right"),
            RetargetMappingEntry("pinky_base", "mixamorig:RightHandPinky1", "RdFngrB_g", side="right"),
            RetargetMappingEntry("pinky_tip", "mixamorig:RightHandPinky3", "RdFngrT_g", side="right"),
            RetargetMappingEntry("thumb_base", "mixamorig:RightHandThumb1", "RThumbB_g", side="right"),
            RetargetMappingEntry("thumb_tip", "mixamorig:RightHandThumb3", "RThumbT_g", side="right"),
            RetargetMappingEntry("calf", "mixamorig:RightLeg", "rshin_g", side="right"),
            RetargetMappingEntry("foot", "mixamorig:RightFoot", "rfoot_g", side="right"),
            RetargetMappingEntry("toe", "mixamorig:RightToeBase", "rfootT_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "mixamo_stable_humanoid"

    segments = _mapped_exact_segments(profile)
    source_pairs = {(source_parent, source_child) for source_parent, source_child, _target_parent, _target_child in segments}

    assert ("mixamorig:Spine", "mixamorig:Spine2") in source_pairs
    assert ("mixamorig:RightShoulder", "mixamorig:RightArm") not in source_pairs
    assert ("mixamorig:RightArm", "mixamorig:RightForeArm") in source_pairs
    assert ("mixamorig:RightHand", "mixamorig:RightHandIndex1") not in source_pairs
    assert ("mixamorig:RightHand", "mixamorig:RightHandMiddle1") in source_pairs
    assert ("mixamorig:RightHand", "mixamorig:RightHandRing1") not in source_pairs
    assert ("mixamorig:RightHandIndex1", "mixamorig:RightHandIndex3") in source_pairs
    assert ("mixamorig:RightHandMiddle1", "mixamorig:RightHandMiddle3") in source_pairs
    assert ("mixamorig:RightHandRing1", "mixamorig:RightHandRing3") in source_pairs
    assert ("mixamorig:RightHandPinky1", "mixamorig:RightHandPinky3") in source_pairs
    assert ("mixamorig:RightHandThumb1", "mixamorig:RightHandThumb3") in source_pairs
    assert ("mixamorig:RightFoot", "mixamorig:RightToeBase") in source_pairs


def test_verified_mixamo_explicit_full_policy_keeps_clavicle_exact_correction() -> None:
    profile = _profile(
        [
            RetargetMappingEntry("spine", "mixamorig:Spine", "torso_g", side="center"),
            RetargetMappingEntry("chest", "mixamorig:Spine2", "torsoUpr_g", side="center"),
            RetargetMappingEntry("clavicle", "mixamorig:RightShoulder", "rcollar_g", side="right"),
            RetargetMappingEntry("upperarm", "mixamorig:RightArm", "rbicep_g", side="right"),
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "pmbam_full_humanoid"

    segments = _mapped_exact_segments(profile)
    source_pairs = {(source_parent, source_child) for source_parent, source_child, _target_parent, _target_child in segments}

    assert ("mixamorig:Spine", "mixamorig:Spine2") in source_pairs
    assert ("mixamorig:RightShoulder", "mixamorig:RightArm") in source_pairs
    assert ("mixamorig:RightArm", "mixamorig:RightForeArm") in source_pairs


def test_verified_mixamo_stable_policy_disables_terminal_twist_by_default() -> None:
    profile = _profile(
        [
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
            RetargetMappingEntry("hand", "mixamorig:RightHand", "Rhand_g", side="right"),
            RetargetMappingEntry("middle_base", "mixamorig:RightHandMiddle1", "RbFngrB_g", side="right"),
            RetargetMappingEntry("calf", "mixamorig:RightLeg", "rshin_g", side="right"),
            RetargetMappingEntry("foot", "mixamorig:RightFoot", "rfoot_g", side="right"),
            RetargetMappingEntry("toe", "mixamorig:RightToeBase", "rfootT_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "mixamo_stable_humanoid"

    assert _mapped_terminal_twist_chains(profile) == []


def test_verified_mixamo_segment_correction_uses_target_rest_roll_anchor() -> None:
    source = _source_clip(
        [
            ("mixamorig:RightArm", None),
            ("mixamorig:RightForeArm", "mixamorig:RightArm"),
        ],
        [
            {
                "mixamorig:RightArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightForeArm": Transform(position=(0.0, 1.0, 0.0)),
            },
            {
                "mixamorig:RightArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightForeArm": Transform(position=(0.0, 1.0, 0.0)),
            },
        ],
        duration=1.0,
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("rbicep_g", "rootdummy", (0.0, 0.0, 0.0), None),
            ("Rforearm_g", "rbicep_g", (1.0, 0.0, 0.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("upperarm", "mixamorig:RightArm", "rbicep_g", side="right"),
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "mixamo_stable_humanoid"
    profile.metadata["exact_segment_rotation_anchor"] = "target_rest"
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            ModelNode(
                name="rbicep_g",
                controllers=[
                    {
                        "type": 20,
                        "times": [0.0, 1.0],
                        "values": [list(_quat_axis("X", 90.0)), list(_quat_axis("X", 90.0))],
                    }
                ],
            )
        ],
    )

    corrected = apply_verified_pmbam_segment_pose_correction(
        animation=animation,
        source_clip=source,
        target_model=target,
        profile=profile,
    )

    evaluated = evaluate_aurora_animation_pose(target, animation, 0.0)
    parent = np.asarray(evaluated.world_transforms_by_node["rbicep_g"].position)
    child = np.asarray(evaluated.world_transforms_by_node["Rforearm_g"].position)
    segment = child - parent
    segment = segment / np.linalg.norm(segment)
    z_axis = quat_to_matrix_xyzw(evaluated.world_transforms_by_node["rbicep_g"].rotation)[:3, :3] @ np.asarray(
        (0.0, 0.0, 1.0)
    )

    assert corrected == 2
    assert segment == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert z_axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)


def test_verified_mixamo_terminal_finger_segment_uses_target_rest_roll_anchor() -> None:
    source = _source_clip(
        [
            ("mixamorig:RightHandMiddle1", None),
            ("mixamorig:RightHandMiddle3", "mixamorig:RightHandMiddle1"),
        ],
        [
            {
                "mixamorig:RightHandMiddle1": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightHandMiddle3": Transform(position=(0.0, 1.0, 0.0)),
            },
            {
                "mixamorig:RightHandMiddle1": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightHandMiddle3": Transform(position=(0.0, 1.0, 0.0)),
            },
        ],
        duration=1.0,
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("Rhand_g", "rootdummy", (0.0, 0.0, 0.0), None),
            ("RbFngrB_g", "Rhand_g", (1.0, 0.0, 0.0), None),
            ("RbFngrT_g", "RbFngrB_g", (1.0, 0.0, 0.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry(
                "middle_base",
                "mixamorig:RightHandMiddle1",
                "RbFngrB_g",
                side="right",
            ),
            RetargetMappingEntry(
                "middle_tip",
                "mixamorig:RightHandMiddle3",
                "RbFngrT_g",
                side="right",
            ),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "mixamo_stable_humanoid"
    profile.metadata["exact_segment_rotation_anchor"] = "target_rest"
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            ModelNode(
                name="RbFngrB_g",
                controllers=[
                    {
                        "type": 20,
                        "times": [0.0, 1.0],
                        "values": [list(_quat_axis("X", 90.0)), list(_quat_axis("X", 90.0))],
                    }
                ],
            )
        ],
    )

    corrected = apply_verified_pmbam_segment_pose_correction(
        animation=animation,
        source_clip=source,
        target_model=target,
        profile=profile,
    )

    evaluated = evaluate_aurora_animation_pose(target, animation, 0.0)
    parent = np.asarray(evaluated.world_transforms_by_node["RbFngrB_g"].position)
    child = np.asarray(evaluated.world_transforms_by_node["RbFngrT_g"].position)
    segment = child - parent
    segment = segment / np.linalg.norm(segment)
    z_axis = quat_to_matrix_xyzw(evaluated.world_transforms_by_node["RbFngrB_g"].rotation)[:3, :3] @ np.asarray(
        (0.0, 0.0, 1.0)
    )

    assert corrected == 2
    assert segment == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert z_axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)


def test_verified_mixamo_segment_correction_mirrors_positions_to_prevent_crossed_feet() -> None:
    source = _source_clip(
        [
            ("mixamorig:Hips", None),
            ("mixamorig:LeftUpLeg", "mixamorig:Hips"),
            ("mixamorig:LeftLeg", "mixamorig:LeftUpLeg"),
            ("mixamorig:LeftFoot", "mixamorig:LeftLeg"),
            ("mixamorig:RightUpLeg", "mixamorig:Hips"),
            ("mixamorig:RightLeg", "mixamorig:RightUpLeg"),
            ("mixamorig:RightFoot", "mixamorig:RightLeg"),
        ],
        [
            {
                "mixamorig:Hips": Transform(position=(0.0, 0.0, 0.0)),
                # Blender-imported Mixamo has the opposite visual left/right X
                # sign from PMBAM, so the workbench must mirror positions while
                # preserving Blender source rotations.
                "mixamorig:LeftUpLeg": Transform(position=(0.5, 0.0, -0.2)),
                "mixamorig:LeftLeg": Transform(position=(0.5, 0.0, -1.0)),
                "mixamorig:LeftFoot": Transform(position=(0.5, 0.2, -1.6)),
                "mixamorig:RightUpLeg": Transform(position=(-0.5, 0.0, -0.2)),
                "mixamorig:RightLeg": Transform(position=(-0.5, 0.0, -1.0)),
                "mixamorig:RightFoot": Transform(position=(-0.5, 0.2, -1.6)),
            },
            {
                "mixamorig:Hips": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:LeftUpLeg": Transform(position=(0.45, 0.0, -0.2)),
                "mixamorig:LeftLeg": Transform(position=(0.4, 0.0, -1.0)),
                "mixamorig:LeftFoot": Transform(position=(0.35, 0.25, -1.6)),
                "mixamorig:RightUpLeg": Transform(position=(-0.45, 0.0, -0.2)),
                "mixamorig:RightLeg": Transform(position=(-0.4, 0.0, -1.0)),
                "mixamorig:RightFoot": Transform(position=(-0.35, 0.25, -1.6)),
            },
        ],
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("pelvis_g", "rootdummy", (0.0, 0.0, 0.0), None),
            ("lthigh_g", "pelvis_g", (-0.5, 0.0, -0.2), None),
            ("lshin_g", "lthigh_g", (0.0, 0.0, -0.8), None),
            ("lfoot_g", "lshin_g", (0.0, 0.2, -0.6), None),
            ("rthigh_g", "pelvis_g", (0.5, 0.0, -0.2), None),
            ("rshin_g", "rthigh_g", (0.0, 0.0, -0.8), None),
            ("rfoot_g", "rshin_g", (0.0, 0.2, -0.6), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("pelvis", "mixamorig:Hips", "pelvis_g", side="center"),
            RetargetMappingEntry("thigh", "mixamorig:LeftUpLeg", "lthigh_g", side="left"),
            RetargetMappingEntry("calf", "mixamorig:LeftLeg", "lshin_g", side="left"),
            RetargetMappingEntry("foot", "mixamorig:LeftFoot", "lfoot_g", side="left"),
            RetargetMappingEntry("thigh", "mixamorig:RightUpLeg", "rthigh_g", side="right"),
            RetargetMappingEntry("calf", "mixamorig:RightLeg", "rshin_g", side="right"),
            RetargetMappingEntry("foot", "mixamorig:RightFoot", "rfoot_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["source_reference_mode"] = "source_rest"
    profile.metadata["source_quaternion_conversion"] = "blender_identity"
    profile.metadata["exact_segment_correction_policy"] = "pmbam_full_humanoid"
    basis_conversion = BasisConversion(
        source_basis=((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        target_basis=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    )

    preview = build_retarget_preview(
        RetargetPreviewRequest(
            source,
            target,
            profile,
            solver_options=RetargetSolverOptions(
                rotation_transfer_mode="exact_segment_correction",
                key_unmapped_reference_nodes=True,
                source_reference_mode="source_rest",
                basis_conversion=basis_conversion,
            ),
        )
    )

    for pose in source.sampled_poses:
        evaluated = evaluate_aurora_animation_pose(target, preview.animation_block, pose.time_seconds)
        left_foot_x = evaluated.world_transforms_by_node["lfoot_g"].position[0]
        right_foot_x = evaluated.world_transforms_by_node["rfoot_g"].position[0]
        assert right_foot_x > left_foot_x


def test_verified_mixamo_terminal_twist_correction_aligns_hand_roll_plane() -> None:
    source = _source_clip(
        [
            ("mixamorig:RightForeArm", None),
            ("mixamorig:RightHand", "mixamorig:RightForeArm"),
            ("mixamorig:RightHandMiddle1", "mixamorig:RightHand"),
        ],
        [
            {
                "mixamorig:RightForeArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightHand": Transform(position=(1.0, 0.0, 0.0)),
                "mixamorig:RightHandMiddle1": Transform(position=(1.0, 1.0, 0.0)),
            },
            {
                "mixamorig:RightForeArm": Transform(position=(0.0, 0.0, 0.0)),
                "mixamorig:RightHand": Transform(position=(1.0, 0.0, 0.0)),
                "mixamorig:RightHandMiddle1": Transform(position=(1.0, 1.0, 0.0)),
            },
        ],
        duration=1.0,
    )
    target = _target_model(
        [
            ("rootdummy", None, (0.0, 0.0, 0.0), None),
            ("Rforearm_g", "rootdummy", (0.0, 0.0, 0.0), None),
            ("Rhand_g", "Rforearm_g", (1.0, 0.0, 0.0), None),
            ("RbFngrB_g", "Rhand_g", (0.0, 0.0, 1.0), None),
        ],
        anims=("pause1",),
    )
    profile = _profile(
        [
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
            RetargetMappingEntry("hand", "mixamorig:RightHand", "Rhand_g", side="right"),
            RetargetMappingEntry("middle_base", "mixamorig:RightHandMiddle1", "RbFngrB_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["source_reference_mode"] = "source_rest"
    profile.metadata["source_quaternion_conversion"] = "blender_identity"
    profile.metadata["exact_segment_correction_policy"] = "pmbam_full_humanoid"

    preview = build_retarget_preview(
        RetargetPreviewRequest(
            source,
            target,
            profile,
            solver_options=RetargetSolverOptions(
                rotation_transfer_mode="exact_segment_correction",
                key_unmapped_reference_nodes=True,
                source_reference_mode="source_rest",
            ),
        )
    )

    evaluated = evaluate_aurora_animation_pose(target, preview.animation_block, 0.0)
    source_basis = _terminal_chain_basis(
        source.sampled_poses[0].global_transforms["mixamorig:RightForeArm"].position,
        source.sampled_poses[0].global_transforms["mixamorig:RightHand"].position,
        source.sampled_poses[0].global_transforms["mixamorig:RightHandMiddle1"].position,
    )
    target_rest_basis = _terminal_chain_basis(
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 0.0, 1.0),
    )
    hand_rotation = quat_to_matrix_xyzw(evaluated.world_transforms_by_node["Rhand_g"].rotation)[:3, :3]
    corrected_basis = hand_rotation @ target_rest_basis

    assert source_basis is not None
    assert target_rest_basis is not None
    assert float(np.dot(corrected_basis[:, 0], source_basis[:, 0])) > 0.999
    assert float(np.dot(corrected_basis[:, 2], source_basis[:, 2])) > 0.999


def test_verified_mixamo_terminal_basis_continuity_prevents_roll_plane_flip() -> None:
    previous = np.eye(3, dtype=np.float64)
    flipped = np.asarray(
        (
            (1.0, -0.0, -0.0),
            (0.0, -1.0, -0.0),
            (0.0, -0.0, -1.0),
        ),
        dtype=np.float64,
    )

    corrected = _continuity_aligned_terminal_basis(flipped, previous)

    assert float(np.dot(corrected[:, 0], previous[:, 0])) > 0.999
    assert float(np.dot(corrected[:, 2], previous[:, 2])) > 0.999


def test_verified_mixamo_explicit_limb_only_policy_still_skips_torso_pairs() -> None:
    profile = _profile(
        [
            RetargetMappingEntry("spine", "mixamorig:Spine", "torso_g", side="center"),
            RetargetMappingEntry("chest", "mixamorig:Spine2", "torsoUpr_g", side="center"),
            RetargetMappingEntry("clavicle", "mixamorig:RightShoulder", "rcollar_g", side="right"),
            RetargetMappingEntry("upperarm", "mixamorig:RightArm", "rbicep_g", side="right"),
            RetargetMappingEntry("forearm", "mixamorig:RightForeArm", "Rforearm_g", side="right"),
        ]
    )
    profile.metadata["generated_by"] = "verified_mixamo_to_aurora_mapping"
    profile.metadata["source_skeleton_family"] = "mixamo"
    profile.metadata["exact_segment_correction_policy"] = "mixamo_limb_only"

    segments = _mapped_exact_segments(profile)
    source_pairs = {(source_parent, source_child) for source_parent, source_child, _target_parent, _target_child in segments}

    assert ("mixamorig:Spine", "mixamorig:Spine2") not in source_pairs
    assert ("mixamorig:RightShoulder", "mixamorig:RightArm") not in source_pairs
    assert ("mixamorig:RightArm", "mixamorig:RightForeArm") in source_pairs


def test_verified_ue5_segment_policy_keeps_spine_and_clavicle_exact_correction() -> None:
    profile = _profile(
        [
            RetargetMappingEntry("spine", "spine_01", "torso_g", side="center"),
            RetargetMappingEntry("chest", "spine_03", "torsoUpr_g", side="center"),
            RetargetMappingEntry("clavicle", "clavicle_l", "lcollar_g", side="left"),
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "Lforearm_g", side="left"),
        ]
    )
    profile.metadata["generated_by"] = "verified_ue5_to_aurora_mapping"

    segments = _mapped_exact_segments(profile)
    source_pairs = {(source_parent, source_child) for source_parent, source_child, _target_parent, _target_child in segments}

    assert ("spine_01", "spine_03") in source_pairs
    assert ("clavicle_l", "upperarm_l") in source_pairs
    assert ("upperarm_l", "lowerarm_l") in source_pairs


def test_capture_hook_requests_standard_angles(tmp_path: Path) -> None:
    viewport = FakeViewport()

    paths = capture_retarget_preview_angles(viewport, tmp_path, basename="retarget")

    assert [path.name for path in paths] == [
        "retarget_front.png",
        "retarget_side.png",
        "retarget_back.png",
        "retarget_top.png",
        "retarget_three_quarter.png",
    ]
    assert [value for name, value in viewport.calls if name == "set_camera_preset"] == [
        "front",
        "side",
        "back",
        "top",
        "three_quarter",
    ]
