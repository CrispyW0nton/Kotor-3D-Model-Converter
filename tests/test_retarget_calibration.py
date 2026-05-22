"""Synthetic gates for calibrated source-to-Aurora retarget frames."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.animation.animation_engine import SuperModelResolver, evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.fbx_importer import classify_source_node_name
from src.core.retargeting.reference_pose import build_reference_pose_pair
from src.core.retargeting.retarget_calibration import (
    build_calibrated_retarget_frames,
    build_orthonormal_basis,
)
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.retarget_solver import (
    RetargetSolverOptions,
    retarget_source_clip_to_aurora_animation,
)
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode, Transform


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


def _source_clip(
    node_defs: list[tuple[str, str | None]],
    pose_globals: list[dict[str, Transform]],
    *,
    duration: float | None = None,
) -> SourceSkeletonClip:
    def local_transforms(globals_by_name: dict[str, Transform]) -> dict[str, Transform]:
        global_matrices = {name: transform.to_matrix() for name, transform in globals_by_name.items()}
        result: dict[str, Transform] = {}
        for name, parent in node_defs:
            if parent:
                result[name] = Transform.from_matrix(np.linalg.inv(global_matrices[parent]) @ global_matrices[name])
            else:
                result[name] = Transform.from_matrix(global_matrices[name])
        return result

    sample_count = len(pose_globals)
    clip_duration = float(duration if duration is not None else max(0, sample_count - 1))
    times = [0.0] if sample_count == 1 else [clip_duration * index / (sample_count - 1) for index in range(sample_count)]
    poses = [
        SourcePose(
            time_seconds=time_value,
            global_transforms=globals_by_name,
            local_transforms=local_transforms(globals_by_name),
        )
        for time_value, globals_by_name in zip(times, pose_globals)
    ]
    nodes = [
        SourceSkeletonNode(
            name=name,
            parent_name=parent,
            index=index,
            rest_local=poses[0].local_transforms[name],
            rest_global=poses[0].global_transforms[name],
            classification=classify_source_node_name(name),
        )
        for index, (name, parent) in enumerate(node_defs)
    ]
    return SourceSkeletonClip(
        source_path="synthetic.fbx",
        clip_name="Synthetic",
        duration_seconds=clip_duration,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=poses[0],
        sampled_poses=poses,
        axis_system=None,
        unit_scale_to_meters=1.0,
    )


def _target_model(
    entries: list[
        tuple[
            str,
            str | None,
            tuple[float, float, float],
            tuple[float, float, float, float] | None,
        ]
    ],
) -> KotorModel:
    nodes = {
        name: ModelNode(name=name, position=position, rotation=rotation or (0.0, 0.0, 0.0, 1.0))
        for name, _parent, position, rotation in entries
    }
    for name, parent, _position, _rotation in entries:
        if parent:
            nodes[name].parent = nodes[parent]
            nodes[parent].children.append(nodes[name])
    return KotorModel(
        name="target",
        root_node=nodes[entries[0][0]],
        animations=[Animation(name="pause1", length=1.0)],
    )


def _profile() -> RetargetProfile:
    return RetargetProfile(
        name="calibrated_frame_profile",
        animation_slot="pause1",
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=[
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "Lforearm_g", side="left"),
        ],
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_orthonormal_basis_preserves_plane_hint() -> None:
    basis = build_orthonormal_basis((1.0, 0.0, 0.0), secondary_hint=(0.0, 1.0, 1.0))

    assert basis is not None
    assert basis[:, 0] == pytest.approx((1.0, 0.0, 0.0), abs=1e-8)
    assert np.dot(basis[:, 0], basis[:, 1]) == pytest.approx(0.0, abs=1e-8)
    assert np.dot(basis[:, 0], basis[:, 2]) == pytest.approx(0.0, abs=1e-8)
    assert np.dot(basis[:, 1], basis[:, 2]) == pytest.approx(0.0, abs=1e-8)
    assert np.linalg.det(basis) == pytest.approx(1.0, abs=1e-8)


def test_calibrated_frames_are_built_from_source_and_aurora_reference_segments() -> None:
    source = _source_clip(
        [("upperarm_l", None), ("lowerarm_l", "upperarm_l")],
        [
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(1.0, 0.0, 0.0)),
            }
        ],
        duration=0.0,
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "root", (0.0, 0.0, 0.0), None),
            ("LbicepL_g", "lbicep_g", (1.0, 0.0, 0.0), None),
            ("Lforearm_g", "LbicepL_g", (1.0, 0.0, 0.0), None),
        ]
    )
    reference_pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=_profile())

    report = build_calibrated_retarget_frames(_profile(), reference_pair)

    assert report.success is True
    assert len(report.frames) == 1
    frame = report.frames[0]
    assert frame.source_parent_node == "upperarm_l"
    assert frame.source_child_node == "lowerarm_l"
    assert frame.target_parent_node == "lbicep_g"
    assert frame.target_child_node == "Lforearm_g"
    assert frame.source_length == pytest.approx(1.0)
    assert frame.target_length == pytest.approx(2.0)


def test_calibrated_frame_delta_rotates_pmbam_style_intermediate_chain() -> None:
    source = _source_clip(
        [("upperarm_l", None), ("lowerarm_l", "upperarm_l")],
        [
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(1.0, 0.0, 0.0)),
            },
            {
                "upperarm_l": Transform(rotation=_quat_axis("Z", 90.0)),
                "lowerarm_l": Transform(position=(0.0, 1.0, 0.0), rotation=_quat_axis("Z", 90.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "root", (0.0, 0.0, 0.0), None),
            ("LbicepL_g", "lbicep_g", (1.0, 0.0, 0.0), None),
            ("Lforearm_g", "LbicepL_g", (1.0, 0.0, 0.0), None),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=_profile(),
        options=RetargetSolverOptions(rotation_transfer_mode="calibrated_frame_delta"),
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    assert pose.world_transforms_by_node["Lforearm_g"].position == pytest.approx((0.0, 2.0, 0.0), abs=1e-6)
    assert result.report.max_segment_direction_error_degrees == pytest.approx(0.0, abs=1e-5)


def test_calibrated_frame_delta_reproduces_target_reference_when_source_does_not_move() -> None:
    source = _source_clip(
        [("upperarm_l", None), ("lowerarm_l", "upperarm_l")],
        [
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(1.0, 0.0, 0.0)),
            }
        ],
        duration=0.0,
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "root", (0.0, 0.0, 0.0), _quat_axis("Y", 20.0)),
            ("LbicepL_g", "lbicep_g", (1.0, 0.0, 0.0), None),
            ("Lforearm_g", "LbicepL_g", (1.0, 0.0, 0.0), None),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=_profile(),
        options=RetargetSolverOptions(rotation_transfer_mode="calibrated_frame_delta"),
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 0.0)

    assert pose.local_transforms_by_node["lbicep_g"].rotation == pytest.approx(_quat_axis("Y", 20.0), abs=1e-6)
