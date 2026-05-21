"""In-memory retarget preview gate tests."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.core.animation.animation_engine import SuperModelResolver, evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.retarget_preview import (
    RetargetPreviewError,
    RetargetPreviewRequest,
    apply_retarget_preview_to_viewport,
    audit_retarget_preview_animation,
    build_retarget_preview,
    capture_retarget_preview_angles,
)
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode, Transform, normalize_quat_xyzw, quat_dot_xyzw


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
