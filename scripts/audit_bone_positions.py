"""Audit viewport validation bone positions against a rest-pose baseline.

This is a Sprint 3.5 diagnostic tool. It consumes JSON emitted by
``scripts/validate_mdl.py`` and flags parent-child distance changes plus
frame-to-frame position jumps. It is intentionally conservative: the output is
evidence for root-cause triage, not a replacement for viewport visual review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.game.kotor_loader import load_model_from_file
from src.core.animation.animation_engine import AnimationEngine


Vec3 = Tuple[float, float, float]


def _dist(a: Vec3, b: Vec3) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _quat_mul_xyzw(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return _quat_normalize_xyzw(
        (
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )
    )


def _quat_normalize_xyzw(q: Tuple[float, float, float, float]):
    length = math.sqrt(sum(v * v for v in q))
    if length <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(float(v / length) for v in q)


def _quat_rotate_xyzw(q: Tuple[float, float, float, float], v: Vec3) -> Vec3:
    x, y, z, w = _quat_normalize_xyzw(q)
    qv = (v[0], v[1], v[2], 0.0)
    conj = (-x, -y, -z, w)
    rotated = _quat_mul_xyzw(_quat_mul_xyzw((x, y, z, w), qv), conj)
    return (rotated[0], rotated[1], rotated[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _positions_for_capture(capture: dict) -> Dict[str, Vec3]:
    out: Dict[str, Vec3] = {}
    for bone in capture.get("bone_positions", []) or []:
        name = str(bone.get("name", "") or "").lower()
        pos = bone.get("world_position", [0.0, 0.0, 0.0])
        if name and len(pos) >= 3:
            out[name] = (float(pos[0]), float(pos[1]), float(pos[2]))
    return out


def _load_first_capture_positions(path: Path) -> Dict[str, Vec3]:
    data = json.loads(path.read_text(encoding="utf-8"))
    captures = data.get("captures", []) or []
    if not captures:
        raise ValueError(f"No captures in {path}")
    return _positions_for_capture(captures[0])


def _parent_map(model_path: Path, mdx_path: Path | None = None) -> Dict[str, str]:
    model = load_model_from_file(
        str(model_path),
        str(mdx_path) if mdx_path and mdx_path.exists() else str(model_path.with_suffix(".mdx")),
    )
    if model is None:
        raise ValueError(f"Could not load model for parent map: {model_path}")
    out: Dict[str, str] = {}
    for node in model.all_nodes():
        if node.parent is not None:
            out[str(node.name).lower()] = str(node.parent.name).lower()
    return out


def _animation_positions(model_path: Path, animation: str, frame_count: int, fps: float) -> List[dict]:
    model = load_model_from_file(str(model_path), str(model_path.with_suffix(".mdx")))
    if model is None:
        raise ValueError(f"Could not load model for animation audit: {model_path}")
    engine = AnimationEngine(model)
    if not engine.play(animation, loop=False, blend=False):
        raise ValueError(f"Animation not found: {animation}")
    nodes = model.all_nodes()
    node_by_key = {node.name.lower(): node for node in nodes}
    out: List[dict] = []
    for frame in range(frame_count):
        pose = engine.evaluate(frame / fps)
        world_pos: Dict[str, Vec3] = {}
        world_rot: Dict[str, Tuple[float, float, float, float]] = {}
        for node in nodes:
            key = node.name.lower()
            node_pose = pose.nodes.get(key)
            local_pos = node_pose.position if node_pose is not None else node.position
            local_rot = node_pose.rotation if node_pose is not None else node.rotation
            parent = node.parent
            if parent is None:
                world_pos[key] = tuple(float(v) for v in local_pos)
                world_rot[key] = _quat_normalize_xyzw(tuple(float(v) for v in local_rot))
            else:
                parent_key = parent.name.lower()
                parent_pos = world_pos.get(parent_key, (0.0, 0.0, 0.0))
                parent_rot = world_rot.get(parent_key, (0.0, 0.0, 0.0, 1.0))
                world_pos[key] = _add(parent_pos, _quat_rotate_xyzw(parent_rot, tuple(float(v) for v in local_pos)))
                world_rot[key] = _quat_mul_xyzw(parent_rot, tuple(float(v) for v in local_rot))
        out.append(
            {
                "frame_index": frame,
                "bone_positions": [
                    {
                        "name": node.name,
                        "world_position": list(world_pos[node.name.lower()]),
                        "world_rotation_quat_xyzw": list(world_rot[node.name.lower()]),
                    }
                    for node in nodes
                    if node.name.lower() in world_pos
                ],
            }
        )
    return out


def audit(
    model_path: Path,
    rest_validation: Path,
    validation_files: Iterable[Path],
    length_tolerance: float,
    max_frame_delta: float,
    animation: Optional[str] = None,
    frame_count: int = 0,
    fps: float = 30.0,
) -> dict:
    parents = _parent_map(model_path)
    rest = _load_first_capture_positions(rest_validation)
    rest_lengths: Dict[str, float] = {}
    for child, parent in parents.items():
        if child in rest and parent in rest:
            length = _dist(rest[child], rest[parent])
            if length > 1e-8:
                rest_lengths[child] = length

    length_issues = []
    motion_issues = []
    summaries = []

    expanded_validations: list[tuple[str, list[dict]]] = []
    for validation in validation_files:
        data = json.loads(validation.read_text(encoding="utf-8"))
        expanded_validations.append((str(validation), data.get("captures", []) or []))
    if animation:
        expanded_validations.append(
            (
                f"{model_path}::{animation}",
                _animation_positions(model_path, animation, frame_count=frame_count, fps=fps),
            )
        )

    for validation_name, captures in expanded_validations:
        previous_positions: Dict[str, Vec3] | None = None
        for capture in captures:
            frame = int(capture.get("frame_index") or 0)
            positions = _positions_for_capture(capture)
            frame_length_issues = 0
            for child, rest_length in rest_lengths.items():
                parent = parents.get(child)
                if not parent or child not in positions or parent not in positions:
                    continue
                current = _dist(positions[child], positions[parent])
                ratio = current / rest_length if rest_length > 1e-8 else 1.0
                if abs(ratio - 1.0) > length_tolerance:
                    frame_length_issues += 1
                    length_issues.append(
                        {
                            "validation": validation_name,
                            "frame": frame,
                            "bone": child,
                            "parent": parent,
                            "rest_length": rest_length,
                            "current_length": current,
                            "ratio": ratio,
                        }
                    )
            if previous_positions is not None:
                for name, pos in positions.items():
                    prev = previous_positions.get(name)
                    if prev is None:
                        continue
                    delta = _dist(pos, prev)
                    if delta > max_frame_delta:
                        motion_issues.append(
                            {
                                "validation": validation_name,
                                "frame": frame,
                                "bone": name,
                                "delta_from_previous_capture": delta,
                            }
                        )
            previous_positions = positions
            summaries.append(
                {
                    "validation": validation_name,
                    "frame": frame,
                    "bones": len(positions),
                    "length_issues": frame_length_issues,
                }
            )

    length_issues.sort(key=lambda item: abs(float(item["ratio"]) - 1.0), reverse=True)
    motion_issues.sort(key=lambda item: float(item["delta_from_previous_capture"]), reverse=True)
    return {
        "model": str(model_path),
        "rest_validation": str(rest_validation),
        "length_tolerance": length_tolerance,
        "max_frame_delta": max_frame_delta,
        "animation": animation,
        "frame_count": frame_count if animation else None,
        "fps": fps if animation else None,
        "rest_bone_lengths": len(rest_lengths),
        "summary": summaries,
        "length_issue_count": len(length_issues),
        "motion_issue_count": len(motion_issues),
        "top_length_issues": length_issues[:40],
        "top_motion_issues": motion_issues[:40],
        "all_length_issues": length_issues,
        "all_motion_issues": motion_issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit viewport bone positions")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--rest-validation", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--length-tolerance", type=float, default=0.05)
    parser.add_argument("--max-frame-delta", type=float, default=0.01)
    parser.add_argument("--animation", default="", help="Optionally evaluate this animation for all frames")
    parser.add_argument("--frame-count", type=int, default=0)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()

    report = audit(
        model_path=args.model,
        rest_validation=args.rest_validation,
        validation_files=args.validation,
        length_tolerance=args.length_tolerance,
        max_frame_delta=args.max_frame_delta,
        animation=args.animation or None,
        frame_count=args.frame_count,
        fps=args.fps,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote bone audit: {args.output}")
    print(f"Length issues: {report['length_issue_count']}")
    print(f"Motion issues: {report['motion_issue_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
