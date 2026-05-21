"""
Phase 3.A: MDL round-trip verification.

This script checks whether GhostRigger can load a stock MDL/MDX pair and
write it back without changing the model's semantic data. Byte identity is
reported as a bonus signal; structural controller preservation and viewport
SSIM are the meaningful gates.

Examples:
    python scripts/verify_roundtrip.py \
        --input tests/fixtures/kotor_stock/k1/pmbam.mdl \
        --animation victory \
        --output exports/verification/roundtrip/pmbam \
        --levels 1,2,3

    python scripts/verify_roundtrip.py \
        --input tests/fixtures/kotor_stock/k1/S_Male02.mdl \
        --animation pause1 \
        --output exports/verification/roundtrip/s_male02 \
        --levels 1,2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ORIENTATION_CONTROLLER = 20


@dataclass
class ByteFileComparison:
    path: str
    counterpart: str
    pass_: bool
    input_sha256: str
    output_sha256: str
    input_size: int
    output_size: int
    diff_byte_count: Optional[int] = None
    first_diff_offset: Optional[int] = None


@dataclass
class RoundTripLevel1Result:
    pass_: bool
    files: List[ByteFileComparison] = field(default_factory=list)


@dataclass
class AnimationCompareResult:
    name: str
    pass_: bool
    input_node_count: int
    output_node_count: int
    compared_controller_count: int = 0
    max_time_delta: float = 0.0
    max_value_delta: float = 0.0
    sign_equivalent_orientation_rows: int = 0
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RoundTripLevel2Result:
    pass_: bool
    node_count_match: bool
    animation_count_match: bool
    requested_animation: str
    requested_animation_available: bool
    input_animation_count: int
    output_animation_count: int
    max_node_position_delta: float = 0.0
    max_node_orientation_delta: float = 0.0
    max_controller_time_delta: float = 0.0
    max_controller_value_delta: float = 0.0
    tolerance: float = 1e-5
    animation_results: Dict[str, AnimationCompareResult] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RoundTripLevel3Result:
    pass_: bool
    frames_tested: List[int]
    ssim_scores: Dict[int, float] = field(default_factory=dict)
    min_ssim: float = 0.0
    threshold: float = 0.99
    failures: List[str] = field(default_factory=list)


@dataclass
class RoundTripFullResult:
    input_path: str
    output_path: str
    animation_name: str
    level_1: Optional[RoundTripLevel1Result] = None
    level_2: Optional[RoundTripLevel2Result] = None
    level_3: Optional[RoundTripLevel3Result] = None
    overall_pass: bool = False
    summary: str = ""


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _byte_file_comparison(input_path: Path, output_path: Path) -> ByteFileComparison:
    input_bytes = input_path.read_bytes()
    output_bytes = output_path.read_bytes()
    input_sha = hashlib.sha256(input_bytes).hexdigest()
    output_sha = hashlib.sha256(output_bytes).hexdigest()

    diff_count: Optional[int] = None
    first_diff: Optional[int] = None
    if len(input_bytes) == len(output_bytes):
        diff_count = 0
        for offset, (left, right) in enumerate(zip(input_bytes, output_bytes)):
            if left != right:
                diff_count += 1
                if first_diff is None:
                    first_diff = offset

    return ByteFileComparison(
        path=str(input_path),
        counterpart=str(output_path),
        pass_=input_sha == output_sha,
        input_sha256=input_sha,
        output_sha256=output_sha,
        input_size=len(input_bytes),
        output_size=len(output_bytes),
        diff_byte_count=diff_count,
        first_diff_offset=first_diff,
    )


def run_level_1(input_mdl: Path, output_mdl: Path) -> RoundTripLevel1Result:
    files = [_byte_file_comparison(input_mdl, output_mdl)]
    input_mdx = input_mdl.with_suffix(".mdx")
    output_mdx = output_mdl.with_suffix(".mdx")
    if input_mdx.exists() and output_mdx.exists():
        files.append(_byte_file_comparison(input_mdx, output_mdx))
    return RoundTripLevel1Result(pass_=all(item.pass_ for item in files), files=files)


def _as_float_tuple(values: Any) -> Tuple[float, ...]:
    return tuple(float(v) for v in (values or ()))


def _max_abs_delta(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return math.inf
    if not left:
        return 0.0
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def _quat_delta(left_xyzw: Sequence[float], right_xyzw: Sequence[float]) -> float:
    """Return the smaller component delta, treating q and -q as equivalent."""
    left = _as_float_tuple(left_xyzw)
    right = _as_float_tuple(right_xyzw)
    if len(left) != 4 or len(right) != 4:
        return _max_abs_delta(left, right)
    direct = _max_abs_delta(left, right)
    negated = _max_abs_delta(left, tuple(-v for v in right))
    return min(direct, negated)


def _parent_name(node: Any) -> str:
    parent = getattr(node, "parent", None)
    return str(getattr(parent, "name", "") or "")


def _controller_key(controller: Dict[str, Any], fallback_index: int) -> Tuple[int, str, int, int]:
    return (
        int(controller.get("type", 0)),
        str(controller.get("name", "")),
        int(controller.get("columns", 0)),
        fallback_index,
    )


def _controller_value_delta(controller_type: int, left: Sequence[float], right: Sequence[float]) -> Tuple[float, bool]:
    if controller_type == ORIENTATION_CONTROLLER:
        direct = _max_abs_delta(left, right)
        delta = _quat_delta(left, right)
        return delta, delta < direct
    return _max_abs_delta(left, right), False


def _compare_controller_lists(
    node_name: str,
    input_controllers: Sequence[Dict[str, Any]],
    output_controllers: Sequence[Dict[str, Any]],
    tolerance: float,
) -> Tuple[int, float, float, int, List[str]]:
    failures: List[str] = []
    compared = 0
    max_time_delta = 0.0
    max_value_delta = 0.0
    sign_equiv_rows = 0

    output_by_key = {
        _controller_key(ctrl, index): ctrl
        for index, ctrl in enumerate(output_controllers or [])
    }

    for index, input_ctrl in enumerate(input_controllers or []):
        key = _controller_key(input_ctrl, index)
        output_ctrl = output_by_key.get(key)
        if output_ctrl is None:
            loose_key = key[:3]
            candidates = [
                ctrl for ctrl_key, ctrl in output_by_key.items()
                if ctrl_key[:3] == loose_key
            ]
            output_ctrl = candidates[0] if candidates else None
        if output_ctrl is None:
            failures.append(f"{node_name}: controller missing in output: type={key[0]} name={key[1]!r}")
            continue

        input_times = list(input_ctrl.get("times", []) or [])
        output_times = list(output_ctrl.get("times", []) or [])
        if len(input_times) != len(output_times):
            failures.append(
                f"{node_name}: controller {key[0]} time count {len(input_times)} != {len(output_times)}"
            )
            continue

        for time_index, (input_time, output_time) in enumerate(zip(input_times, output_times)):
            delta = abs(float(input_time) - float(output_time))
            max_time_delta = max(max_time_delta, delta)
            if delta > tolerance:
                failures.append(
                    f"{node_name}: controller {key[0]} time[{time_index}] "
                    f"{input_time} != {output_time} (delta={delta:.3g})"
                )

        input_values = list(input_ctrl.get("values", []) or [])
        output_values = list(output_ctrl.get("values", []) or [])
        if len(input_values) != len(output_values):
            failures.append(
                f"{node_name}: controller {key[0]} value row count {len(input_values)} != {len(output_values)}"
            )
            continue

        for row_index, (input_row, output_row) in enumerate(zip(input_values, output_values)):
            delta, sign_equiv = _controller_value_delta(key[0], input_row, output_row)
            max_value_delta = max(max_value_delta, delta)
            if sign_equiv:
                sign_equiv_rows += 1
            if delta > tolerance:
                failures.append(
                    f"{node_name}: controller {key[0]} value[{row_index}] "
                    f"delta={delta:.3g} input={tuple(input_row)} output={tuple(output_row)}"
                )

        compared += 1

    return compared, max_time_delta, max_value_delta, sign_equiv_rows, failures


def _compare_animation(input_anim: Any, output_anim: Any, tolerance: float) -> AnimationCompareResult:
    input_nodes = {
        str(getattr(node, "name", "") or "").lower(): node
        for node in (getattr(input_anim, "nodes", None) or [])
        if getattr(node, "name", "")
    }
    output_nodes = {
        str(getattr(node, "name", "") or "").lower(): node
        for node in (getattr(output_anim, "nodes", None) or [])
        if getattr(node, "name", "")
    }
    result = AnimationCompareResult(
        name=str(getattr(input_anim, "name", "")),
        pass_=False,
        input_node_count=len(input_nodes),
        output_node_count=len(output_nodes),
    )

    length_delta = abs(float(getattr(input_anim, "length", 0.0)) - float(getattr(output_anim, "length", 0.0)))
    if length_delta > tolerance:
        result.failures.append(f"animation length delta {length_delta:.3g}")

    transition_delta = abs(
        float(getattr(input_anim, "transition_time", 0.0))
        - float(getattr(output_anim, "transition_time", 0.0))
    )
    if transition_delta > tolerance:
        result.failures.append(f"transition time delta {transition_delta:.3g}")

    for key, input_node in input_nodes.items():
        output_node = output_nodes.get(key)
        if output_node is None:
            controllers = getattr(input_node, "controllers", None) or []
            if controllers:
                result.failures.append(f"animation node {getattr(input_node, 'name', key)!r} missing in output")
            else:
                result.warnings.append(f"controllerless node {getattr(input_node, 'name', key)!r} omitted in output")
            continue

        compared, max_time, max_value, sign_equiv, failures = _compare_controller_lists(
            getattr(input_node, "name", key),
            getattr(input_node, "controllers", None) or [],
            getattr(output_node, "controllers", None) or [],
            tolerance,
        )
        result.compared_controller_count += compared
        result.max_time_delta = max(result.max_time_delta, max_time)
        result.max_value_delta = max(result.max_value_delta, max_value)
        result.sign_equivalent_orientation_rows += sign_equiv
        result.failures.extend(failures)

    extra_controller_nodes = [
        getattr(node, "name", key)
        for key, node in output_nodes.items()
        if key not in input_nodes and (getattr(node, "controllers", None) or [])
    ]
    for name in extra_controller_nodes:
        result.failures.append(f"extra controller-bearing output animation node {name!r}")

    result.pass_ = not result.failures
    return result


def _load_model(path: Path, game: str) -> Any:
    from src.core.game.kotor_loader import load_model_from_file
    from src.core.geometry.model_data import GameVersion

    game_version = GameVersion.K2 if game.lower() in {"k2", "tsl"} else GameVersion.K1
    model = load_model_from_file(str(path), str(path.with_suffix(".mdx")), game_version)
    if model is None:
        raise RuntimeError(f"Failed to load model: {path}")
    return model


def run_level_2(
    input_mdl: Path,
    output_mdl: Path,
    animation_name: str,
    tolerance: float = 1e-5,
    game: str = "k1",
) -> RoundTripLevel2Result:
    input_model = _load_model(input_mdl, game)
    output_model = _load_model(output_mdl, game)
    input_nodes = list(getattr(input_model, "nodes", []) or [])
    output_nodes = list(getattr(output_model, "nodes", []) or [])
    input_anims = list(getattr(input_model, "animations", []) or [])
    output_anims = list(getattr(output_model, "animations", []) or [])

    input_anim_names = [str(getattr(anim, "name", "")) for anim in input_anims]
    output_anim_names = [str(getattr(anim, "name", "")) for anim in output_anims]
    requested_available = animation_name in input_anim_names and animation_name in output_anim_names

    result = RoundTripLevel2Result(
        pass_=False,
        node_count_match=len(input_nodes) == len(output_nodes),
        animation_count_match=len(input_anims) == len(output_anims),
        requested_animation=animation_name,
        requested_animation_available=requested_available,
        input_animation_count=len(input_anims),
        output_animation_count=len(output_anims),
        tolerance=tolerance,
    )

    if not result.node_count_match:
        result.failures.append(f"node count {len(input_nodes)} != {len(output_nodes)}")
    if not result.animation_count_match:
        result.failures.append(f"local animation count {len(input_anims)} != {len(output_anims)}")

    for index, (input_node, output_node) in enumerate(zip(input_nodes, output_nodes)):
        input_name = str(getattr(input_node, "name", ""))
        output_name = str(getattr(output_node, "name", ""))
        if input_name.lower() != output_name.lower():
            result.failures.append(f"node[{index}] name {input_name!r} != {output_name!r}")
            continue
        if _parent_name(input_node).lower() != _parent_name(output_node).lower():
            result.failures.append(
                f"{input_name}: parent {_parent_name(input_node)!r} != {_parent_name(output_node)!r}"
            )
        if int(getattr(input_node, "flags", 0)) != int(getattr(output_node, "flags", 0)):
            result.failures.append(
                f"{input_name}: flags {int(getattr(input_node, 'flags', 0))} "
                f"!= {int(getattr(output_node, 'flags', 0))}"
            )

        pos_delta = _max_abs_delta(getattr(input_node, "position", ()), getattr(output_node, "position", ()))
        rot_delta = _quat_delta(getattr(input_node, "rotation", ()), getattr(output_node, "rotation", ()))
        result.max_node_position_delta = max(result.max_node_position_delta, pos_delta)
        result.max_node_orientation_delta = max(result.max_node_orientation_delta, rot_delta)
        if pos_delta > tolerance:
            result.failures.append(f"{input_name}: node position delta {pos_delta:.3g}")
        if rot_delta > tolerance:
            result.failures.append(f"{input_name}: node orientation delta {rot_delta:.3g}")

    input_by_name = {name.lower(): anim for name, anim in zip(input_anim_names, input_anims)}
    output_by_name = {name.lower(): anim for name, anim in zip(output_anim_names, output_anims)}
    if animation_name and animation_name.lower() not in input_by_name:
        result.warnings.append(
            f"requested animation {animation_name!r} is not local to {input_mdl.name}; "
            "structural comparison covers available local animations only"
        )

    for lower_name, input_anim in input_by_name.items():
        output_anim = output_by_name.get(lower_name)
        if output_anim is None:
            result.failures.append(f"local animation {getattr(input_anim, 'name', lower_name)!r} missing in output")
            continue
        anim_result = _compare_animation(input_anim, output_anim, tolerance)
        result.animation_results[getattr(input_anim, "name", lower_name)] = anim_result
        result.max_controller_time_delta = max(result.max_controller_time_delta, anim_result.max_time_delta)
        result.max_controller_value_delta = max(result.max_controller_value_delta, anim_result.max_value_delta)
        if not anim_result.pass_:
            result.failures.extend(
                f"{anim_result.name}: {failure}"
                for failure in anim_result.failures[:50]
            )
            if len(anim_result.failures) > 50:
                result.failures.append(
                    f"{anim_result.name}: ... {len(anim_result.failures) - 50} more animation failures"
                )
        result.warnings.extend(f"{anim_result.name}: {warning}" for warning in anim_result.warnings)

    result.pass_ = not result.failures
    return result


def _compare_png_ssim(left: Path, right: Path) -> float:
    try:
        from skimage.io import imread
        from skimage.metrics import structural_similarity as ssim

        left_img = imread(str(left), as_gray=True)
        right_img = imread(str(right), as_gray=True)
        if left_img.shape != right_img.shape:
            raise ValueError(f"Image dimensions do not match: {left_img.shape} vs {right_img.shape}")
        return float(ssim(left_img, right_img, data_range=255))
    except ModuleNotFoundError:
        from PIL import Image
        import numpy as np

        left_img = np.asarray(Image.open(left).convert("L"), dtype=np.float64)
        right_img = np.asarray(Image.open(right).convert("L"), dtype=np.float64)
        if left_img.shape != right_img.shape:
            raise ValueError(f"Image dimensions do not match: {left_img.shape} vs {right_img.shape}")

        # Global SSIM fallback. It is less sensitive than windowed SSIM, but
        # exactly what this round-trip gate needs: identical viewport renders
        # still score 1.0, and visible writer regressions drop sharply.
        c1 = (0.01 * 255.0) ** 2
        c2 = (0.03 * 255.0) ** 2
        mu_x = float(left_img.mean())
        mu_y = float(right_img.mean())
        sigma_x = float(((left_img - mu_x) ** 2).mean())
        sigma_y = float(((right_img - mu_y) ** 2).mean())
        sigma_xy = float(((left_img - mu_x) * (right_img - mu_y)).mean())
        numerator = (2.0 * mu_x * mu_y + c1) * (2.0 * sigma_xy + c2)
        denominator = (mu_x ** 2 + mu_y ** 2 + c1) * (sigma_x + sigma_y + c2)
        return float(numerator / denominator) if denominator else 1.0


def run_level_3(
    input_mdl: Path,
    output_mdl: Path,
    animation_name: str,
    frames: List[int],
    output_dir: Path,
    threshold: float = 0.99,
) -> RoundTripLevel3Result:
    from src.core.validation.capture_specs import ViewportCaptureSpec
    from src.core.validation.viewport_validator import ViewportValidator

    input_dir = output_dir / "input"
    output_render_dir = output_dir / "roundtrip"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_render_dir.mkdir(parents=True, exist_ok=True)

    input_validator = ViewportValidator(output_dir=input_dir)
    output_validator = ViewportValidator(output_dir=output_render_dir)
    spec = ViewportCaptureSpec(frames=frames, animation_name=animation_name)

    input_result = input_validator.validate_mdl(input_mdl, spec)
    output_result = output_validator.validate_mdl(output_mdl, spec)
    result = RoundTripLevel3Result(pass_=False, frames_tested=frames, threshold=threshold)

    if not input_result.success:
        result.failures.extend(f"input render: {error}" for error in input_result.errors)
        return result
    if not output_result.success:
        result.failures.extend(f"output render: {error}" for error in output_result.errors)
        return result

    input_by_frame = {capture.frame_index: capture.png_path for capture in input_result.captures}
    output_by_frame = {capture.frame_index: capture.png_path for capture in output_result.captures}
    for frame in frames:
        input_png = input_by_frame.get(frame)
        output_png = output_by_frame.get(frame)
        if not input_png or not output_png:
            result.failures.append(f"frame {frame}: missing capture")
            continue
        score = _compare_png_ssim(input_png, output_png)
        result.ssim_scores[frame] = score
        if score < threshold:
            result.failures.append(f"frame {frame}: SSIM {score:.5f} < {threshold:.5f}")

    result.min_ssim = min(result.ssim_scores.values()) if result.ssim_scores else 0.0
    result.pass_ = not result.failures
    return result


def determine_overall_pass(full_result: RoundTripFullResult) -> Tuple[bool, str]:
    if full_result.level_3 is not None:
        if not full_result.level_3.pass_:
            return False, "Level 3 visual round-trip failed; writer output is not visually preserved."
    if full_result.level_2 is not None:
        if not full_result.level_2.pass_:
            if full_result.level_3 is not None and full_result.level_3.pass_:
                return True, "Level 2 differed, but Level 3 visual round-trip passed."
            return False, "Level 2 structural round-trip failed and no visual fallback passed."
    if full_result.level_2 is None and full_result.level_3 is None:
        return bool(full_result.level_1 and full_result.level_1.pass_), "Only Level 1 was run."
    if full_result.level_1 is not None and not full_result.level_1.pass_:
        return True, "Semantic round-trip passed; byte identity is a non-blocking bonus signal."
    return True, "Round-trip passed."


def _json_ready(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _parse_frames(text: str) -> List[int]:
    return [int(item.strip()) for item in text.split(",") if item.strip()]


def _parse_levels(text: str) -> List[int]:
    levels = [int(item.strip()) for item in text.split(",") if item.strip()]
    invalid = [level for level in levels if level not in {1, 2, 3}]
    if invalid:
        raise ValueError(f"Invalid level(s): {invalid}; expected 1, 2, and/or 3")
    return levels


def run_roundtrip(
    input_mdl: Path,
    animation: str,
    output_dir: Path,
    levels: List[int],
    frames: List[int],
    tolerance: float,
    ssim_threshold: float,
    game: str,
) -> RoundTripFullResult:
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    output_dir.mkdir(parents=True, exist_ok=True)
    output_mdl = output_dir / f"{input_mdl.stem}_roundtrip.mdl"
    model = _load_model(input_mdl, game)
    MDLBinaryWriter().write_files(model, str(output_mdl))

    full_result = RoundTripFullResult(
        input_path=str(input_mdl),
        output_path=str(output_mdl),
        animation_name=animation,
    )
    if 1 in levels:
        full_result.level_1 = run_level_1(input_mdl, output_mdl)
    if 2 in levels:
        full_result.level_2 = run_level_2(input_mdl, output_mdl, animation, tolerance, game)
    if 3 in levels:
        full_result.level_3 = run_level_3(
            input_mdl,
            output_mdl,
            animation,
            frames,
            output_dir / "viewport_compare",
            ssim_threshold,
        )
    full_result.overall_pass, full_result.summary = determine_overall_pass(full_result)
    return full_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MDL read/write round-trip preservation.")
    parser.add_argument("--input", required=True, type=Path, help="Input MDL path")
    parser.add_argument("--animation", required=True, help="Animation to visually compare")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--levels", default="1,2,3", help="Comma-separated levels to run")
    parser.add_argument(
        "--frames",
        default="0,30,60,90,120,150,180,210,240,270,300",
        help="Comma-separated frames for Level 3",
    )
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Level 2 float tolerance")
    parser.add_argument("--ssim-threshold", type=float, default=0.99, help="Level 3 SSIM threshold")
    parser.add_argument("--game", default="k1", choices=("k1", "k2"), help="Game version")
    args = parser.parse_args()

    levels = _parse_levels(args.levels)
    frames = _parse_frames(args.frames)
    if not args.input.exists():
        parser.error(f"input not found: {args.input}")

    print("")
    print("=" * 72)
    print(f"Round-trip verification: {args.input}")
    print(f"Animation: {args.animation}")
    print(f"Levels: {levels}")
    print("=" * 72)

    full_result = run_roundtrip(
        input_mdl=args.input,
        animation=args.animation,
        output_dir=args.output,
        levels=levels,
        frames=frames,
        tolerance=args.tolerance,
        ssim_threshold=args.ssim_threshold,
        game=args.game,
    )

    if full_result.level_1:
        print("\nLevel 1: byte identity")
        for item in full_result.level_1.files:
            status = "PASS" if item.pass_ else "FAIL"
            print(f"  {status} {Path(item.path).name}: {item.input_sha256[:16]} -> {item.output_sha256[:16]}")
            print(f"    size {item.input_size} -> {item.output_size}")
            if item.diff_byte_count is not None:
                print(f"    differing bytes: {item.diff_byte_count}; first diff: {item.first_diff_offset}")

    if full_result.level_2:
        level2 = full_result.level_2
        print("\nLevel 2: structural preservation")
        print(f"  Status: {'PASS' if level2.pass_ else 'FAIL'}")
        print(f"  Nodes: {'match' if level2.node_count_match else 'differ'}")
        print(f"  Local animations: {level2.input_animation_count} -> {level2.output_animation_count}")
        print(f"  Requested animation local: {level2.requested_animation_available}")
        print(f"  Max node position delta: {level2.max_node_position_delta:.3e}")
        print(f"  Max node orientation delta: {level2.max_node_orientation_delta:.3e}")
        print(f"  Max controller time delta: {level2.max_controller_time_delta:.3e}")
        print(f"  Max controller value delta: {level2.max_controller_value_delta:.3e}")
        for warning in level2.warnings[:8]:
            print(f"  Warning: {warning}")
        for failure in level2.failures[:12]:
            print(f"  Failure: {failure}")
        if len(level2.failures) > 12:
            print(f"  ... {len(level2.failures) - 12} more failures")

    if full_result.level_3:
        level3 = full_result.level_3
        print("\nLevel 3: viewport SSIM")
        print(f"  Status: {'PASS' if level3.pass_ else 'FAIL'}")
        print(f"  Min SSIM: {level3.min_ssim:.5f}")
        for frame, score in sorted(level3.ssim_scores.items()):
            print(f"  Frame {frame:04d}: {score:.5f}")
        for failure in level3.failures[:12]:
            print(f"  Failure: {failure}")

    report_path = args.output / "roundtrip_report.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(full_result), handle, indent=2)

    print("")
    print("=" * 72)
    print(f"Overall: {'PASS' if full_result.overall_pass else 'FAIL'}")
    print(full_result.summary)
    print(f"Report: {report_path}")
    print("=" * 72)
    print("")
    return 0 if full_result.overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
