"""UE/FBX source animation import and sampled-pose gates."""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pytest

from src.core.retargeting.fbx_importer import (
    FbxBackendClip,
    FbxBackendNode,
    FbxImportError,
    classify_source_node_name,
    import_ue_fbx_animation_clip,
)
from src.core.retargeting.source_animation import Transform
from src.core.retargeting.source_skeleton_audit import audit_source_skeleton_clip


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


def _matrix(
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> np.ndarray:
    return Transform(position=position, rotation=rotation).to_matrix()


class FakeFbxScene:
    def __init__(
        self,
        *,
        nodes: list[FbxBackendNode],
        clips: list[FbxBackendClip] | None = None,
        samples: dict[tuple[str, float, str], np.ndarray] | None = None,
        bind: dict[str, np.ndarray] | None = None,
        axis_system: str = "UE_X_FORWARD_Y_RIGHT_Z_UP",
        unit_scale_to_meters: float = 0.01,
        handedness: str = "left-handed",
    ):
        self.source_path = "fake.fbx"
        self.nodes = nodes
        self.clips = clips or [FbxBackendClip("Idle", 1.0)]
        self.samples = samples or {}
        self.bind = bind
        self.axis_system = axis_system
        self.unit_scale_to_meters = unit_scale_to_meters
        self.handedness = handedness

    def evaluate_global_transform(self, node_name: str, time_seconds: float, clip_name: str):
        key = (node_name, round(float(time_seconds), 10), clip_name)
        if key in self.samples:
            return self.samples[key]
        return _matrix()

    def bind_global_transform(self, node_name: str):
        if self.bind is None:
            return None
        return self.bind.get(node_name)


class FakeFbxBackend:
    def __init__(self, scene: FakeFbxScene):
        self.scene = scene

    def load_scene(self, path: str) -> FakeFbxScene:
        self.scene.source_path = path
        return self.scene


def test_source_hierarchy_is_imported_parent_before_child() -> None:
    scene = FakeFbxScene(
        nodes=[
            FbxBackendNode("thigh_l", "pelvis"),
            FbxBackendNode("root"),
            FbxBackendNode("pelvis", "root"),
        ]
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))

    assert [node.name for node in clip.nodes] == ["root", "pelvis", "thigh_l"]
    assert [node.parent_name for node in clip.nodes] == [None, "root", "pelvis"]


def test_evaluated_global_transforms_are_sampled() -> None:
    samples = {
        ("root", 0.0, "Idle"): _matrix(),
        ("pelvis", 0.0, "Idle"): _matrix(position=(1.0, 0.0, 0.0)),
        ("root", 1.0, "Idle"): _matrix(rotation=_quat_axis("Z", 90.0)),
        # Deliberately not root @ local: this proves the importer trusts backend globals.
        ("pelvis", 1.0, "Idle"): _matrix(position=(3.0, 4.0, 0.0)),
    }
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root"), FbxBackendNode("pelvis", "root")],
        samples=samples,
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))
    pose = clip.pose_at_time(1.0)

    assert pose.global_transforms["root"].rotation == pytest.approx(_quat_axis("Z", 90.0), abs=1e-6)
    assert pose.global_transforms["pelvis"].position == pytest.approx((3.0, 4.0, 0.0))


def test_local_transforms_are_reconstructed_from_globals() -> None:
    root_global = _matrix(rotation=_quat_axis("Z", 90.0))
    child_local = _matrix(position=(2.0, 0.0, 0.0), rotation=_quat_axis("X", 30.0))
    child_global = root_global @ child_local
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root"), FbxBackendNode("pelvis", "root")],
        samples={
            ("root", 0.0, "Idle"): root_global,
            ("pelvis", 0.0, "Idle"): child_global,
        },
        clips=[FbxBackendClip("Idle", 0.0)],
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=30.0, backend=FakeFbxBackend(scene))
    pose = clip.sampled_poses[0]

    assert pose.local_transforms["pelvis"].position == pytest.approx((2.0, 0.0, 0.0), abs=1e-6)
    assert pose.local_transforms["pelvis"].rotation == pytest.approx(_quat_axis("X", 30.0), abs=1e-6)


def test_source_reference_pose_fallback_warns() -> None:
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root")],
        samples={
            ("root", 0.0, "Idle"): _matrix(position=(7.0, 8.0, 9.0)),
            ("root", 1.0, "Idle"): _matrix(position=(1.0, 2.0, 3.0)),
        },
        bind=None,
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))

    assert clip.rest_pose.global_transforms["root"].position == pytest.approx((7.0, 8.0, 9.0))
    assert any("using frame 0 as source reference pose" in warning for warning in clip.import_warnings)


def test_unit_and_axis_metadata_is_preserved() -> None:
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root")],
        axis_system="UE_X_FORWARD_Y_RIGHT_Z_UP",
        unit_scale_to_meters=0.01,
        handedness="left-handed",
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))

    assert clip.axis_system == "UE_X_FORWARD_Y_RIGHT_Z_UP"
    assert clip.unit_scale_to_meters == pytest.approx(0.01)
    assert clip.handedness == "left-handed"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("upperarm_twist_01_l", "twist"),
        ("ik_foot_root", "ik"),
        ("VB weapon_socket", "helper"),
        ("hand_l", "deform"),
        ("root", "root"),
    ],
)
def test_twist_ik_helper_classification(name: str, expected: str) -> None:
    assert classify_source_node_name(name) == expected


def test_multiple_clips_require_explicit_clip_name() -> None:
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root")],
        clips=[FbxBackendClip("Walk", 1.0), FbxBackendClip("Run", 1.0)],
    )

    with pytest.raises(FbxImportError, match="Walk, Run"):
        import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))

    clip = import_ue_fbx_animation_clip(
        "fake.fbx",
        clip_name="Run",
        sample_rate=1.0,
        backend=FakeFbxBackend(scene),
    )

    assert clip.clip_name == "Run"


def test_sampled_quaternions_are_normalized_and_continuous() -> None:
    scene = FakeFbxScene(
        nodes=[FbxBackendNode("root")],
        samples={
            ("root", 0.0, "Idle"): _matrix(rotation=_quat_axis("Z", 10.0)),
            ("root", 1.0, "Idle"): _matrix(rotation=_quat_axis("Z", 20.0)),
        },
    )

    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))
    q0 = clip.sampled_poses[0].global_transforms["root"].rotation
    q1 = clip.sampled_poses[-1].global_transforms["root"].rotation

    assert math.sqrt(sum(value * value for value in q0)) == pytest.approx(1.0, abs=1e-6)
    assert math.sqrt(sum(value * value for value in q1)) == pytest.approx(1.0, abs=1e-6)
    assert sum(a * b for a, b in zip(q0, q1)) >= 0.0


def test_source_animation_audit_accepts_clean_fake_clip(tmp_path: Path) -> None:
    scene = FakeFbxScene(nodes=[FbxBackendNode("root"), FbxBackendNode("pelvis", "root")])
    clip = import_ue_fbx_animation_clip("fake.fbx", sample_rate=1.0, backend=FakeFbxBackend(scene))

    report = audit_source_skeleton_clip(clip)

    assert report.success is True
    assert report.errors == []


@pytest.mark.skipif(
    not os.environ.get("GHOSTRIGGER_UE_FBX_FIXTURE"),
    reason="Set GHOSTRIGGER_UE_FBX_FIXTURE to a UE-exported FBX animation to run real import test",
)
def test_real_ue_fbx_fixture_imports_and_audits() -> None:
    fixture = os.environ["GHOSTRIGGER_UE_FBX_FIXTURE"]
    clip = import_ue_fbx_animation_clip(fixture, sample_rate=30.0)
    report = audit_source_skeleton_clip(clip)

    assert Path(fixture).exists()
    assert clip.nodes
    assert clip.duration_seconds >= 0.0
    assert clip.sampled_poses
    assert report.success is True, report.errors
