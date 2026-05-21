"""UE/FBX source animation importer facade.

The importer is backend-neutral for tests and future tool integrations. A real
FBX backend must provide evaluated global matrices; if none is configured, the
public import function fails explicitly instead of pretending raw channels are
safe enough.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import math
from typing import Dict, Iterable, List, Optional, Protocol, Sequence

import numpy as np

from .coordinate import UE_UNIT_SCALE_TO_METERS, UE_X_FORWARD_Y_RIGHT_Z_UP
from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
    hemisphere_continuity_xyzw,
)


FRAME0_REFERENCE_WARNING = "No complete FBX bind/default pose found; using frame 0 as source reference pose."


class FbxImportUnavailableError(RuntimeError):
    """Raised when no supported FBX import backend is available."""


class FbxImportError(ValueError):
    """Raised when an FBX source cannot be imported deterministically."""


@dataclass(frozen=True)
class FbxBackendNode:
    """Minimal backend-neutral node record used by the importer."""

    name: str
    parent_name: Optional[str] = None


@dataclass(frozen=True)
class FbxBackendClip:
    """Minimal backend-neutral animation stack record."""

    name: str
    duration_seconds: float


class FbxBackendScene(Protocol):
    """Protocol expected from a project-supported FBX backend scene."""

    source_path: str
    nodes: Sequence[FbxBackendNode]
    clips: Sequence[FbxBackendClip]
    axis_system: Optional[str]
    unit_scale_to_meters: Optional[float]
    handedness: Optional[str]

    def evaluate_global_transform(self, node_name: str, time_seconds: float, clip_name: str) -> Iterable[Iterable[float]]:
        ...


class FbxBackend(Protocol):
    """Protocol for backend objects that can load an FBX scene."""

    def load_scene(self, path: str) -> FbxBackendScene:
        ...


def classify_source_node_name(name: str) -> str:
    """Classify a UE/FBX source node name without discarding it."""

    raw = str(name or "").strip()
    lowered = raw.lower().replace(" ", "_")
    if lowered in {"root", "scene", "armature"}:
        return "root"
    if (
        "twist" in lowered
        or "roll" in lowered
        or "forearm_twist" in lowered
        or "upperarm_twist" in lowered
        or "thigh_twist" in lowered
        or "calf_twist" in lowered
    ):
        return "twist"
    if (
        lowered.startswith("ik_")
        or "_ik" in lowered
        or "ik_hand" in lowered
        or "ik_foot" in lowered
        or "effector" in lowered
        or "pole" in lowered
    ):
        return "ik"
    if (
        "helper" in lowered
        or "socket" in lowered
        or "weapon" in lowered
        or "attach" in lowered
        or "virtual" in lowered
        or lowered.startswith("vb_")
        or lowered.startswith("vb")
    ):
        return "helper"
    return "deform"


def import_ue_fbx_animation_clip(
    path: str,
    *,
    clip_name: Optional[str] = None,
    sample_rate: float = 30.0,
    reference_pose: str | float | None = None,
    backend: Optional[FbxBackend] = None,
) -> SourceSkeletonClip:
    """Import and sample a UE/FBX skeleton animation clip."""

    backend = backend or _default_backend()
    scene = backend.load_scene(str(path))
    nodes = _topological_nodes(scene.nodes)
    if not nodes:
        raise FbxImportError("FBX file contains no source skeleton nodes.")
    selected_clip = _select_clip(scene.clips, clip_name)
    if selected_clip.duration_seconds < 0:
        raise FbxImportError(f"FBX animation stack '{selected_clip.name}' has negative duration.")
    sample_times = _sample_times(selected_clip.duration_seconds, sample_rate)

    warnings: List[str] = []
    axis_system = getattr(scene, "axis_system", None) or UE_X_FORWARD_Y_RIGHT_Z_UP
    unit_scale = getattr(scene, "unit_scale_to_meters", None)
    if unit_scale is None:
        unit_scale = UE_UNIT_SCALE_TO_METERS
        warnings.append("FBX unit scale metadata unavailable; assuming Unreal centimeters (0.01 meters).")
    handedness = getattr(scene, "handedness", None) or "left-handed"

    global_by_time: Dict[float, Dict[str, np.ndarray]] = {}
    previous_quat_by_node: Dict[str, tuple[float, float, float, float]] = {}
    sampled_poses: List[SourcePose] = []
    for time_value in sample_times:
        globals_for_time: Dict[str, np.ndarray] = {}
        for node in nodes:
            matrix = np.asarray(
                scene.evaluate_global_transform(node.name, time_value, selected_clip.name),
                dtype=np.float64,
            )
            if matrix.shape != (4, 4):
                raise FbxImportError(f"Backend returned non-4x4 global matrix for node '{node.name}'.")
            globals_for_time[node.name] = matrix
        global_by_time[time_value] = globals_for_time
        pose = _pose_from_global_matrices(nodes, globals_for_time, time_value)
        for node_name, transform in pose.global_transforms.items():
            fixed = hemisphere_continuity_xyzw(transform.rotation, previous_quat_by_node.get(node_name))
            previous_quat_by_node[node_name] = fixed
            pose.global_transforms[node_name] = Transform(
                position=transform.position,
                rotation=fixed,
                scale=transform.scale,
            )
        sampled_poses.append(pose)

    rest_global_matrices = _reference_global_matrices(
        scene,
        nodes,
        selected_clip.name,
        reference_pose,
        global_by_time,
        warnings,
    )
    rest_pose = _pose_from_global_matrices(nodes, rest_global_matrices, 0.0)
    source_nodes = [
        SourceSkeletonNode(
            name=node.name,
            parent_name=node.parent_name,
            index=index,
            rest_local=rest_pose.local_transforms[node.name],
            rest_global=rest_pose.global_transforms[node.name],
            classification=classify_source_node_name(node.name),
        )
        for index, node in enumerate(nodes)
    ]

    return SourceSkeletonClip(
        source_path=str(path),
        clip_name=selected_clip.name,
        duration_seconds=float(selected_clip.duration_seconds),
        sample_rate=float(sample_rate),
        nodes=source_nodes,
        rest_pose=rest_pose,
        sampled_poses=sampled_poses,
        axis_system=axis_system,
        unit_scale_to_meters=float(unit_scale),
        handedness=handedness,
        import_warnings=warnings,
    )


def _default_backend() -> FbxBackend:
    if importlib.util.find_spec("fbx") is None:
        raise FbxImportUnavailableError(
            "FBX import backend is not available. Configure the project-supported "
            "FBX backend before importing Unreal animation clips."
        )
    raise FbxImportUnavailableError(
        "Autodesk FBX Python bindings were found, but GhostRigger has not wired "
        "the production FBX SDK backend yet. Configure the project-supported FBX backend."
    )


def _select_clip(clips: Sequence[FbxBackendClip], clip_name: Optional[str]) -> FbxBackendClip:
    available = list(clips or [])
    if not available:
        raise FbxImportError("FBX file contains a skeleton but no animation stack.")
    if clip_name:
        wanted = str(clip_name).lower()
        for clip in available:
            if clip.name.lower() == wanted:
                return clip
        raise FbxImportError(
            f"FBX file does not contain animation stack '{clip_name}'. "
            f"Available stacks: {', '.join(clip.name for clip in available)}."
        )
    if len(available) > 1:
        raise FbxImportError(
            "FBX file contains multiple animation stacks: "
            f"{', '.join(clip.name for clip in available)}. Pass clip_name explicitly."
        )
    return available[0]


def _topological_nodes(nodes: Sequence[FbxBackendNode]) -> List[FbxBackendNode]:
    by_name: Dict[str, FbxBackendNode] = {}
    for node in nodes:
        key = node.name.lower()
        if key in by_name:
            raise FbxImportError(
                f"Source skeleton has duplicate node name '{node.name}'; cannot build deterministic retarget mapping."
            )
        by_name[key] = node

    ordered: List[FbxBackendNode] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(node: FbxBackendNode) -> None:
        key = node.name.lower()
        if key in permanent:
            return
        if key in temporary:
            raise FbxImportError(f"Source skeleton hierarchy has a cycle at '{node.name}'.")
        temporary.add(key)
        if node.parent_name:
            parent = by_name.get(node.parent_name.lower())
            if parent is None:
                raise FbxImportError(f"Source skeleton parent '{node.parent_name}' for '{node.name}' is missing.")
            visit(parent)
        temporary.remove(key)
        permanent.add(key)
        ordered.append(node)

    for node in nodes:
        visit(node)
    return ordered


def _sample_times(duration_seconds: float, sample_rate: float) -> List[float]:
    duration = max(0.0, float(duration_seconds))
    rate = float(sample_rate or 30.0)
    if rate <= 0.0:
        raise FbxImportError("sample_rate must be positive.")
    frame_count = int(math.floor(duration * rate + 1e-7))
    times = {0.0, duration}
    for frame in range(frame_count + 1):
        value = min(duration, frame / rate)
        times.add(round(value, 10))
    return sorted(times)


def _pose_from_global_matrices(
    nodes: Sequence[FbxBackendNode],
    globals_for_time: Dict[str, np.ndarray],
    time_seconds: float,
) -> SourcePose:
    global_transforms: Dict[str, Transform] = {}
    local_transforms: Dict[str, Transform] = {}
    for node in nodes:
        global_matrix = globals_for_time[node.name]
        global_transforms[node.name] = Transform.from_matrix(global_matrix)
        if node.parent_name:
            parent_matrix = globals_for_time[node.parent_name]
            local_matrix = np.linalg.inv(parent_matrix) @ global_matrix
        else:
            local_matrix = global_matrix
        local_transforms[node.name] = Transform.from_matrix(local_matrix)
    return SourcePose(
        time_seconds=float(time_seconds),
        global_transforms=global_transforms,
        local_transforms=local_transforms,
    )


def _reference_global_matrices(
    scene: FbxBackendScene,
    nodes: Sequence[FbxBackendNode],
    clip_name: str,
    reference_pose: str | float | None,
    sampled_globals: Dict[float, Dict[str, np.ndarray]],
    warnings: List[str],
) -> Dict[str, np.ndarray]:
    if isinstance(reference_pose, (int, float)):
        return {
            node.name: np.asarray(
                scene.evaluate_global_transform(node.name, float(reference_pose), clip_name),
                dtype=np.float64,
            )
            for node in nodes
        }

    for method_name in ("bind_global_transform", "default_global_transform"):
        method = getattr(scene, method_name, None)
        if method is None:
            continue
        matrices: Dict[str, np.ndarray] = {}
        complete = True
        for node in nodes:
            value = method(node.name)
            if value is None:
                complete = False
                break
            matrix = np.asarray(value, dtype=np.float64)
            if matrix.shape != (4, 4):
                complete = False
                break
            matrices[node.name] = matrix
        if complete:
            return matrices

    warnings.append(FRAME0_REFERENCE_WARNING)
    first_time = min(sampled_globals)
    return sampled_globals[first_time]
