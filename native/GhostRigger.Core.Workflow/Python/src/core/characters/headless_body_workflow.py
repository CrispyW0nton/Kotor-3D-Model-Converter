"""
src/core/characters/headless_body_workflow.py — Mode 1 (Headless Body) workflow service
============================================================================

This module implements the end-to-end *Headless Body* workflow defined by
M5 / T501-T506 of the Qt-ghostrigger roadmap.  It is a **pure-Python**
service layer that the Qt Character Builder window calls into; the layer
contains no Qt dependencies so it is fully unit-testable without a
display server.

The seven workflow steps mapped onto this module:

    Step 1  ── Load Body     →  :func:`load_body`
    Step 2  ── Check Model   →  :func:`check_model`        (T502)
    Step 3  ── Body Rig      →  :func:`place_body_guides`  (T503)
                              + :func:`generate_skeleton`   (T503)
    Step 4  ── Hand Rig      →  :func:`hand_rig`            (T504)
    Step 5  ── Check Actor   →  :func:`select_preview_animation`  (T505)
    Step 6  ── Add Motions   →  reuses :mod:`qt_animation_panel`
    Step 7  ── Validate +    →  :func:`validate_for_export` (T506)
              Export           + :func:`export_scene`        (T506)

Every public function returns a *result dataclass* carrying a structured
``ok`` flag plus a human-readable ``message``.  The Qt window converts
these into bottom-strip banner colours and status-bar messages without
needing to know how the underlying services are wired.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M5/T501-T506.
"""

from __future__ import annotations

import copy
import itertools
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from src.core.characters.character_autofit_report import AutoFitOverride, AutoFitReport
except ImportError:  # pragma: no cover - package-relative fallback
    from core.characters.character_autofit_report import AutoFitOverride, AutoFitReport  # type: ignore

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
#  Lazy imports
# ──────────────────────────────────────────────────────────────────────
#
# We keep the *heavy* imports (model_data, validation_service, autorig)
# behind helper functions so this module can be imported in environments
# that lack PyKotor / OpenGL — the test suite uses this pattern to
# exercise the workflow logic in isolation.

def _import_model_data():                                   # pragma: no cover - import shim
    try:
        from src.core.geometry import model_data as _md             # type: ignore
    except ImportError:
        from core.geometry import model_data as _md                 # type: ignore
    return _md


def _import_validation_service():                           # pragma: no cover - import shim
    try:
        from src.core.diagnostics import validation_service as _vs    # type: ignore
    except ImportError:
        from core.diagnostics import validation_service as _vs         # type: ignore
    return _vs


def _import_heat_diffusion():                               # pragma: no cover - import shim
    """Lazy import of the heat-diffusion skinning module (Core.Math).

    Mirrors the ``src.math.<module>`` idiom used by
    ``landmark_alignment`` / ``transform_math`` imports.
    """
    try:
        from src.math import heat_diffusion_skinning as _hd          # type: ignore
    except ImportError:
        import heat_diffusion_skinning as _hd                       # type: ignore
    return _hd


def _import_character_builder():                            # pragma: no cover - import shim
    try:
        from src.core.characters import character_builder as _cb      # type: ignore
    except ImportError:
        from core.characters import character_builder as _cb          # type: ignore
    return _cb


# ──────────────────────────────────────────────────────────────────────
#  Supported input formats
# ──────────────────────────────────────────────────────────────────────

#: Extensions accepted by :func:`load_body`.  The detector keys off the
#: lower-cased suffix.
_MDL_EXTS  = (".mdl",)
_GLTF_EXTS = (".gltf", ".glb")
_FBX_EXTS  = (".fbx", ".obj", ".ply", ".stl")
_UTC_EXTS  = (".utc",)
_TEXTURE_EXTS = (".tga", ".tpc", ".png", ".dds", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
_DEFAULT_KOTOR_HUMANOID_HEIGHT = 2.01345

Vec3 = Tuple[float, float, float]


def supported_load_extensions() -> Tuple[str, ...]:
    """Return the full tuple of file extensions :func:`load_body` accepts.

    The order is stable and used to build the Qt file-picker filter
    string ("Body models (*.mdl *.gltf *.glb *.fbx *.obj …)").
    """
    return _MDL_EXTS + _GLTF_EXTS + _FBX_EXTS + _UTC_EXTS


def load_file_filter() -> str:
    """Qt-compatible filter string for the Load-Body dialog.

    Example output::

        "Body models (*.mdl *.gltf *.glb *.fbx *.obj *.ply *.stl *.utc);;All files (*.*)"
    """
    patterns = " ".join(f"*{ext}" for ext in supported_load_extensions())
    return f"Body models ({patterns});;All files (*.*)"


# ──────────────────────────────────────────────────────────────────────
#  Result dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LoadResult:
    """Result of :func:`load_body`.

    Attributes
    ----------
    ok            : True when the model loaded *and* matched HEADLESS_BODY.
    model         : The loaded ``KotorModel`` (may be present even when
                    ``ok=False`` — e.g. a Head model was loaded by mistake;
                    the caller can offer to switch the active mode).
    detected_mode : The ``CharacterMode`` returned by ``detect_character_mode``.
    source_path   : Absolute path the file was read from.
    resref        : Lower-case resource reference (basename without ext).
    message       : Human-readable summary suitable for the status bar.
    code          : Stable machine tag: ``"loaded"``, ``"mode_mismatch"``,
                    ``"unsupported_format"``, ``"file_not_found"``,
                    ``"load_failed"``, ``"empty_path"``.
    """
    ok:            bool                        = False
    model:         Optional[Any]               = None         # KotorModel
    detected_mode: Optional[Any]               = None         # CharacterMode
    source_path:   str                         = ""
    resref:        str                         = ""
    message:       str                         = ""
    code:          str                         = "load_failed"


@dataclass(frozen=True)
class _HumanoidFitFrame:
    """Bone-landmark frame used to snap an imported mesh to a KOTOR rig."""

    origin: Vec3
    right: Vec3
    forward: Vec3
    up: Vec3
    height: float
    confidence: float
    landmarks: Dict[str, str] = field(default_factory=dict)
    landmark_sources: Dict[str, str] = field(default_factory=dict)
    landmark_positions: Dict[str, Vec3] = field(default_factory=dict)


def _vec_as_list(value: Optional[Vec3]) -> Optional[List[float]]:
    if value is None:
        return None
    return [float(value[0]), float(value[1]), float(value[2])]


def _bounds_as_lists(
    bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[Dict[str, List[float]]]:
    if bounds is None:
        return None
    bb_min, bb_max = bounds
    return {"min": _vec_as_list(bb_min) or [], "max": _vec_as_list(bb_max) or []}


def _fit_frame_as_metadata(frame: Optional[_HumanoidFitFrame]) -> Optional[Dict[str, Any]]:
    if frame is None:
        return None
    toe_forward = _fit_frame_toe_forward(frame)
    return {
        "origin": _vec_as_list(frame.origin),
        "right": _vec_as_list(frame.right),
        "forward": _vec_as_list(frame.forward),
        "up": _vec_as_list(frame.up),
        "toe_forward": _vec_as_list(toe_forward),
        "toe_forward_alignment": (
            float(_vec_dot(frame.forward, toe_forward))
            if toe_forward is not None else None
        ),
        "height": float(frame.height),
        "confidence": float(frame.confidence),
        "landmarks": dict(frame.landmarks),
        "landmark_sources": dict(frame.landmark_sources),
        "landmark_positions": {
            str(role): _vec_as_list(position)
            for role, position in (frame.landmark_positions or {}).items()
        },
    }


def _fit_frame_toe_forward(frame: Optional[_HumanoidFitFrame]) -> Optional[Vec3]:
    if frame is None:
        return None
    positions = frame.landmark_positions or {}
    left_foot = positions.get("left_foot")
    right_foot = positions.get("right_foot")
    left_toe = positions.get("left_toe")
    right_toe = positions.get("right_toe")
    if (
        left_foot is None
        or right_foot is None
        or left_toe is None
        or right_toe is None
    ):
        return None
    foot_center = _average_points([left_foot, right_foot])
    toe_center = _average_points([left_toe, right_toe])
    if foot_center is None or toe_center is None:
        return None
    raw = _vec_sub(toe_center, foot_center)
    projected = _vec_sub(raw, _vec_scale(frame.up, _vec_dot(raw, frame.up)))
    return _vec_normalize(projected)


def _toe_forward_from_landmarks(
    *,
    left_foot: Tuple[str, Vec3, str] | None,
    right_foot: Tuple[str, Vec3, str] | None,
    left_toe: Tuple[str, Vec3, str] | None,
    right_toe: Tuple[str, Vec3, str] | None,
    up: Vec3,
) -> Optional[Vec3]:
    if (
        left_foot is None
        or right_foot is None
        or left_toe is None
        or right_toe is None
    ):
        return None
    foot_center = _average_points([left_foot[1], right_foot[1]])
    toe_center = _average_points([left_toe[1], right_toe[1]])
    if foot_center is None or toe_center is None:
        return None
    raw = _vec_sub(toe_center, foot_center)
    projected = _vec_sub(raw, _vec_scale(up, _vec_dot(raw, up)))
    return _vec_normalize(projected)


def _front_axis_from_toes(
    *,
    provisional_forward: Vec3,
    provisional_right: Vec3,
    up: Vec3,
    left_foot: Tuple[str, Vec3, str] | None,
    right_foot: Tuple[str, Vec3, str] | None,
    left_toe: Tuple[str, Vec3, str] | None,
    right_toe: Tuple[str, Vec3, str] | None,
) -> Tuple[Vec3, Vec3]:
    """Use foot-end landmarks to stabilize humanoid facing when available.

    Shoulder/collar pairs tell us left versus right, but they can be noisy on
    imported meshes or slightly posed rigs.  Toe/foot-end guides provide a
    stronger front-facing signal.  Keep the candidate that agrees with the
    left/right body labels so an imported mesh cannot silently mirror itself.
    """

    toe_forward = _toe_forward_from_landmarks(
        left_foot=left_foot,
        right_foot=right_foot,
        left_toe=left_toe,
        right_toe=right_toe,
        up=up,
    )
    if toe_forward is None:
        return provisional_forward, provisional_right

    candidates = (toe_forward, _vec_scale(toe_forward, -1.0))
    best_forward = provisional_forward
    best_right = provisional_right
    best_score = -2.0
    for candidate in candidates:
        candidate_right = _vec_normalize(_vec_cross(candidate, up))
        if candidate_right is None:
            continue
        score = _vec_dot(candidate_right, provisional_right)
        if score > best_score:
            best_score = score
            best_forward = candidate
            best_right = candidate_right

    if best_score < 0.25:
        return provisional_forward, provisional_right
    return best_forward, best_right


def _imported_armature_fit_evidence(model: Any) -> Dict[str, Any]:
    """Return durable evidence for temporary imported FBX skeleton guides."""

    names: set[str] = set()
    raw_names = getattr(model, "_gr_fbx_armatures", None)
    if isinstance(raw_names, (list, tuple, set)):
        names.update(str(name).strip() for name in raw_names if str(name).strip())
    elif raw_names:
        names.add(str(raw_names).strip())

    guide_nodes: List[Any] = []
    imported_skeleton_nodes: List[Any] = []
    for node in _iter_model_nodes(model):
        if getattr(node, "_gr_imported_armature_joint", False):
            guide_nodes.append(node)
            armature_name = str(getattr(node, "_gr_imported_armature_name", "") or "").strip()
            if armature_name:
                names.add(armature_name)
        if _node_fit_landmark_source(node) == "imported_skeleton":
            imported_skeleton_nodes.append(node)

    raw_count = getattr(model, "_gr_fbx_armature_bone_count", 0)
    try:
        recorded_count = int(raw_count or 0)
    except (TypeError, ValueError):
        recorded_count = 0
    scene_count = max(len(guide_nodes), len(imported_skeleton_nodes))
    guide_count = max(recorded_count, scene_count)

    return {
        "source": (
            "imported_fbx_armature"
            if names or recorded_count or guide_nodes
            else ("imported_skeleton_nodes" if guide_count else "none")
        ),
        "guide_joint_count": guide_count,
        "scene_guide_joint_count": scene_count,
        "armature_names": sorted(names),
    }


def _fit_frame_visual_overlay(
    model: Any,
    frame: Optional[_HumanoidFitFrame],
    bounds: Optional[Tuple[Vec3, Vec3]],
    *,
    transform_point=None,
    transform_direction=None,
    axis_length_scale: float = 1.0,
    prefer_skeleton_landmarks: bool = False,
) -> Dict[str, Any]:
    """Return viewport-friendly fit-frame evidence without mutating *model*."""

    overlay: Dict[str, Any] = {
        "bounds": (
            _bounds_as_lists(_transform_bounds(bounds, transform_point))
            if transform_point is not None
            else _bounds_as_lists(bounds)
        ),
        "origin": (
            _vec_as_list(transform_point(frame.origin))
            if frame is not None and transform_point is not None
            else (_vec_as_list(frame.origin) if frame is not None else None)
        ),
        "axes": {},
        "landmarks": [],
    }
    if frame is None:
        return overlay

    axis_length = max(float(frame.height) * float(axis_length_scale) * 0.25, 0.05)
    axes: Dict[str, Dict[str, Any]] = {}
    for name, vector in (
        ("right", frame.right),
        ("forward", frame.forward),
        ("up", frame.up),
    ):
        axis_vector = (
            transform_direction(vector)
            if transform_direction is not None
            else vector
        )
        origin = (
            transform_point(frame.origin)
            if transform_point is not None
            else frame.origin
        )
        end = _vec_add(origin, _vec_scale(axis_vector, axis_length))
        axes[name] = {
            "axis_label": _axis_label_from_vector(axis_vector),
            "vector": _vec_as_list(axis_vector),
            "end": _vec_as_list(end),
        }
    overlay["axes"] = axes

    named = _named_positions(
        model,
        prefer_skeleton_landmarks=prefer_skeleton_landmarks,
    )
    landmarks: List[Dict[str, Any]] = []
    for role, node_name in sorted((frame.landmarks or {}).items()):
        if role == "side_pair":
            continue
        clean = _clean_landmark_name(node_name)
        hit = named.get(clean)
        if hit is None:
            continue
        position = (
            transform_point(hit[1])
            if transform_point is not None
            else hit[1]
        )
        landmarks.append({
            "role": str(role),
            "name": str(hit[0]),
            "source": str(hit[2]),
            "position": _vec_as_list(position),
        })
    overlay["landmarks"] = landmarks
    return overlay


def _transform_bounds(
    bounds: Optional[Tuple[Vec3, Vec3]],
    transform_point,
) -> Optional[Tuple[Vec3, Vec3]]:
    if bounds is None or transform_point is None:
        return bounds
    bb_min, bb_max = bounds
    points: List[Vec3] = []
    for x in (bb_min[0], bb_max[0]):
        for y in (bb_min[1], bb_max[1]):
            for z in (bb_min[2], bb_max[2]):
                points.append(transform_point((float(x), float(y), float(z))))
    if not points:
        return None
    return (
        tuple(min(point[i] for point in points) for i in range(3)),  # type: ignore[return-value]
        tuple(max(point[i] for point in points) for i in range(3)),  # type: ignore[return-value]
    )


def _axis_label_from_vector(value: Optional[Vec3]) -> str:
    """Return the signed dominant world axis for a unit-ish vector."""
    if value is None:
        return "unknown"
    try:
        components = (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return "unknown"
    magnitudes = [abs(v) for v in components]
    axis_index = max(range(3), key=lambda i: magnitudes[i])
    if magnitudes[axis_index] <= 1.0e-8:
        return "unknown"
    sign = "+" if components[axis_index] >= 0.0 else "-"
    return f"{sign}{('x', 'y', 'z')[axis_index]}"


def _axis_label_from_index(index: int) -> str:
    try:
        return f"+{('x', 'y', 'z')[int(index)]}"
    except Exception:
        return "unknown"


def _axis_vector_from_label(label: Any) -> Optional[Vec3]:
    raw = str(label or "").strip().lower()
    if raw in {"", "auto", "unknown"}:
        return None
    sign = -1.0 if raw.startswith("-") else 1.0
    axis = raw[-1:] if raw[-1:] in {"x", "y", "z"} else raw
    if axis == "x":
        return (sign, 0.0, 0.0)
    if axis == "y":
        return (0.0, sign, 0.0)
    if axis == "z":
        return (0.0, 0.0, sign)
    return None


def _mode_token(value: Any) -> str:
    raw = (
        getattr(value, "value", None)
        or getattr(value, "name", None)
        or str(value or "")
    )
    return str(raw).strip().lower()


def _is_creature_mode_value(value: Any) -> bool:
    return _mode_token(value) == "creature"


def _bounds_extent_along_axis(
    bounds: Optional[Tuple[Vec3, Vec3]],
    axis: Vec3,
) -> float:
    if bounds is None:
        return 0.0
    bb_min, bb_max = bounds
    values: List[float] = []
    for x in (bb_min[0], bb_max[0]):
        for y in (bb_min[1], bb_max[1]):
            for z in (bb_min[2], bb_max[2]):
                values.append(_vec_dot((float(x), float(y), float(z)), axis))
    if not values:
        return 0.0
    return max(values) - min(values)


def _coerce_auto_fit_override(value: Any) -> AutoFitOverride:
    if isinstance(value, AutoFitOverride):
        return value
    return AutoFitOverride.from_mapping(value)


def _ground_origin_basis(frame: Optional[_HumanoidFitFrame]) -> str:
    if frame is None:
        return "bounds_bottom"
    landmarks = frame.landmarks or {}
    if landmarks.get("left_foot") and landmarks.get("right_foot"):
        return "feet"
    if landmarks.get("pelvis"):
        return "hips"
    return "bounds_bottom"


def _default_target_fit_frame(
    bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[_HumanoidFitFrame]:
    if bounds is None:
        return None
    height = _height_from_bounds(bounds)
    if height <= 1.0e-6:
        return None
    return _HumanoidFitFrame(
        origin=_bounds_ground_center(bounds),
        right=(1.0, 0.0, 0.0),
        forward=(0.0, 1.0, 0.0),
        up=(0.0, 0.0, 1.0),
        height=height,
        confidence=0.55,
        landmarks={},
    )


def _matrix_determinant(matrix: Tuple[Vec3, Vec3, Vec3]) -> float:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _matrix_inverse(matrix: Tuple[Vec3, Vec3, Vec3]) -> Optional[Tuple[Vec3, Vec3, Vec3]]:
    det = _matrix_determinant(matrix)
    if abs(det) <= 1.0e-12:
        return None
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    inv_det = 1.0 / det
    return (
        (
            (e * i - f * h) * inv_det,
            (c * h - b * i) * inv_det,
            (b * f - c * e) * inv_det,
        ),
        (
            (f * g - d * i) * inv_det,
            (a * i - c * g) * inv_det,
            (c * d - a * f) * inv_det,
        ),
        (
            (d * h - e * g) * inv_det,
            (b * g - a * h) * inv_det,
            (a * e - b * d) * inv_det,
        ),
    )


def _matrix_transpose(matrix: Tuple[Vec3, Vec3, Vec3]) -> Tuple[Vec3, Vec3, Vec3]:
    return (
        (matrix[0][0], matrix[1][0], matrix[2][0]),
        (matrix[0][1], matrix[1][1], matrix[2][1]),
        (matrix[0][2], matrix[1][2], matrix[2][2]),
    )


def _normal_transform_from_linear_matrix(
    linear_matrix: Tuple[Vec3, Vec3, Vec3],
) -> Tuple[Vec3, Vec3, Vec3]:
    inverse = _matrix_inverse(linear_matrix)
    if inverse is None:
        return linear_matrix
    return _matrix_transpose(inverse)


def _median_positive(values: Iterable[float], fallback: float = 1.0) -> float:
    clean = sorted(
        float(value)
        for value in values
        if math.isfinite(float(value)) and float(value) > 1.0e-8
    )
    if not clean:
        return float(fallback)
    mid = len(clean) // 2
    if len(clean) % 2:
        return float(clean[mid])
    return float((clean[mid - 1] + clean[mid]) * 0.5)


def _creature_bounds_fit_solution(
    bounds: Optional[Tuple[Vec3, Vec3]],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[Dict[str, Any]]:
    """Fit a non-humanoid external mesh to the selected creature footprint.

    Humanoid fallback fitting assumes the tallest source axis is "up".  Flat or
    winged creatures often violate that assumption: their vertical thickness can
    be the shortest axis.  Use the chosen KOTOR creature base as authority and
    build a proper rotation plus uniform scale from source footprint extents.
    """

    if bounds is None or reference_bounds is None:
        return None
    bb_min, bb_max = bounds
    ref_min, ref_max = reference_bounds
    source_extents = tuple(max(0.0, float(bb_max[i]) - float(bb_min[i])) for i in range(3))
    target_extents = tuple(max(0.0, float(ref_max[i]) - float(ref_min[i])) for i in range(3))
    if min(source_extents) <= 1.0e-8 or min(target_extents) <= 1.0e-8:
        return None

    max_source_extent = max(source_extents)
    min_source_axis = min(range(3), key=lambda i: source_extents[i])
    source_up_axis = 2
    if source_extents[min_source_axis] <= max_source_extent * 0.35:
        source_up_axis = min_source_axis

    horizontal_axes = [axis for axis in range(3) if axis != source_up_axis]
    if len(horizontal_axes) != 2:
        return None
    source_forward_axis = max(horizontal_axes, key=lambda i: source_extents[i])
    source_right_axis = horizontal_axes[0] if horizontal_axes[1] == source_forward_axis else horizontal_axes[1]

    rotation_rows: List[List[float]] = [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ]
    rotation_rows[0][source_right_axis] = 1.0
    rotation_rows[1][source_forward_axis] = 1.0
    rotation_rows[2][source_up_axis] = 1.0
    rotation: Tuple[Vec3, Vec3, Vec3] = tuple(tuple(row) for row in rotation_rows)  # type: ignore[assignment]
    if _matrix_determinant(rotation) < 0.0:
        rotation_rows[1][source_forward_axis] *= -1.0
        rotation = tuple(tuple(row) for row in rotation_rows)  # type: ignore[assignment]

    ratios = (
        target_extents[0] / source_extents[source_right_axis],
        target_extents[1] / source_extents[source_forward_axis],
        target_extents[2] / source_extents[source_up_axis],
    )
    scale = _median_positive(ratios)
    linear_matrix = _scale_matrix(rotation, scale)

    def transform_without_offset(point: Vec3) -> Vec3:
        return _mat_vec(linear_matrix, point)

    mapped_bounds = _transform_bounds(bounds, transform_without_offset)
    if mapped_bounds is None:
        return None
    mapped_min, mapped_max = mapped_bounds
    mapped_center_x = (mapped_min[0] + mapped_max[0]) * 0.5
    mapped_center_y = (mapped_min[1] + mapped_max[1]) * 0.5
    target_center_x = (float(ref_min[0]) + float(ref_max[0])) * 0.5
    target_center_y = (float(ref_min[1]) + float(ref_max[1])) * 0.5
    offset = (
        target_center_x - mapped_center_x,
        target_center_y - mapped_center_y,
        float(ref_min[2]) - float(mapped_min[2]),
    )
    source_origin = _bounds_ground_center(bounds)
    target_origin = _vec_add(_mat_vec(linear_matrix, source_origin), offset)
    fit_transform = _fit_transform_metadata(
        policy="creature_bounds_basis",
        scale=scale,
        rotation_matrix=rotation,
        source_origin=source_origin,
        target_origin=target_origin,
    )
    return {
        "scale": float(scale),
        "rotation_matrix": rotation,
        "linear_matrix": linear_matrix,
        "offset": offset,
        "source_origin": source_origin,
        "target_origin": target_origin,
        "fit_transform": fit_transform,
        "source_up_axis": source_up_axis,
        "source_forward_axis": source_forward_axis,
        "source_right_axis": source_right_axis,
        "source_up_label": _axis_label_from_index(source_up_axis),
        "source_forward_label": _axis_label_from_index(source_forward_axis),
        "target_up_label": "+z",
        "target_forward_label": "+y",
        "source_height": source_extents[source_up_axis],
        "target_height": target_extents[2],
        "scale_ratios": ratios,
        "source_extents": source_extents,
        "target_extents": target_extents,
    }


def _axis_scaled_matrix(
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    axis_scales: Sequence[float],
) -> Tuple[Vec3, Vec3, Vec3]:
    """Return a baked affine matrix with one scale per target axis."""

    return tuple(
        tuple(float(value) * float(axis_scales[row_index]) for value in row)
        for row_index, row in enumerate(rotation_matrix)
    )  # type: ignore[return-value]


def _axis_fit_distortion(axis_scales: Sequence[float]) -> float:
    values = [float(value) for value in axis_scales if float(value) > 1.0e-8]
    if len(values) != 3:
        return float("inf")
    return math.log(max(values) / min(values))


def _mesh_vertex_cloud(model: Any) -> List[Vec3]:
    """Collect render-payload vertices for direct replacement fit scoring."""

    vertices: List[Vec3] = []
    if model is None:
        return vertices
    for node in _iter_model_nodes(model):
        if bool(getattr(node, "_gr_hidden", False)):
            continue
        if getattr(node, "render", True) is False:
            continue
        if int(getattr(node, "vertex_space", 0) or 0) == 2:
            continue
        verts = list(getattr(node, "vertices", []) or [])
        if not verts:
            continue
        # Prefer actual mesh payload nodes.  Some imported/native models carry
        # helper nodes with vertices but no faces; those should not drive a
        # same-resref surface match.
        if not list(getattr(node, "faces", []) or []):
            continue
        for vert in verts:
            if vert is None or len(vert) < 3:
                continue
            try:
                vertices.append((float(vert[0]), float(vert[1]), float(vert[2])))
            except Exception:
                continue
    return vertices


def _sample_cloud_array(vertices: Sequence[Vec3], *, max_points: int = 1200):
    import numpy as np

    arr = np.asarray(vertices, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] < 4:
        return None
    if arr.shape[0] > max_points:
        indices = np.linspace(0, arr.shape[0] - 1, max_points, dtype=np.int64)
        arr = arr[indices]
    return arr


def _nearest_cloud_mean_square(source, target) -> float:
    import numpy as np

    mins = []
    for start in range(0, int(source.shape[0]), 256):
        chunk = source[start:start + 256]
        diff = chunk[:, None, :] - target[None, :, :]
        distances = np.sum(diff * diff, axis=2)
        mins.append(np.min(distances, axis=1))
    if not mins:
        return float("inf")
    return float(np.concatenate(mins).mean())


def _point_cloud_fit_score(
    source_vertices: Optional[Sequence[Vec3]],
    reference_vertices: Optional[Sequence[Vec3]],
    *,
    linear_matrix: Tuple[Vec3, Vec3, Vec3],
    offset: Vec3,
) -> Optional[float]:
    """Symmetric nearest-neighbor score for same-resref replacement geometry."""

    if not source_vertices or not reference_vertices:
        return None
    try:
        import numpy as np
    except Exception:  # pragma: no cover - project dependency
        return None
    source = _sample_cloud_array(source_vertices)
    reference = _sample_cloud_array(reference_vertices)
    if source is None or reference is None:
        return None
    linear = np.asarray(linear_matrix, dtype=np.float64)
    translation = np.asarray(offset, dtype=np.float64)
    mapped = (source @ linear.T) + translation
    source_to_ref = _nearest_cloud_mean_square(mapped, reference)
    ref_to_source = _nearest_cloud_mean_square(reference, mapped)
    if not math.isfinite(source_to_ref) or not math.isfinite(ref_to_source):
        return None
    return math.sqrt(max(0.0, (source_to_ref + ref_to_source) * 0.5))


def _nearest_cloud_pairs(source, target, *, chunk_size: int = 256):
    import numpy as np

    nearest = []
    distances = []
    for start in range(0, int(source.shape[0]), chunk_size):
        chunk = source[start:start + chunk_size]
        diff = chunk[:, None, :] - target[None, :, :]
        squared = np.sum(diff * diff, axis=2)
        indices = np.argmin(squared, axis=1)
        nearest.append(target[indices])
        distances.append(np.min(squared, axis=1))
    if not nearest:
        return None, None
    return np.vstack(nearest), np.concatenate(distances)


def _surface_refined_axis_fit(
    source_vertices: Optional[Sequence[Vec3]],
    reference_vertices: Optional[Sequence[Vec3]],
    *,
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    axis_scales: Sequence[float],
    offset: Vec3,
    max_iterations: int = 8,
) -> Optional[Dict[str, Any]]:
    """Refine a same-resref fit by registering source surface to native surface.

    Bounds get the replacement mesh into roughly the right frame, but a creature
    shell such as Drexl is too thin and irregular for bounding-box containment
    to be the final objective.  This pass keeps the already-selected signed axis
    frame, then iteratively solves one scale and one translation per target axis
    from trimmed nearest-surface correspondences.
    """

    if not source_vertices or not reference_vertices:
        return None
    try:
        import numpy as np
    except Exception:  # pragma: no cover - project dependency
        return None

    source = _sample_cloud_array(source_vertices, max_points=1600)
    reference = _sample_cloud_array(reference_vertices, max_points=1800)
    if source is None or reference is None:
        return None
    try:
        rotation = np.asarray(rotation_matrix, dtype=np.float64)
        initial_scales = np.asarray(tuple(float(value) for value in axis_scales), dtype=np.float64)
        current_scales = initial_scales.copy()
        current_offset = np.asarray(offset, dtype=np.float64)
    except Exception:
        return None
    if rotation.shape != (3, 3) or initial_scales.shape != (3,) or current_offset.shape != (3,):
        return None
    if not np.all(np.isfinite(initial_scales)) or np.any(initial_scales <= 1.0e-8):
        return None

    rotated_source = source @ rotation.T

    def mapped_cloud(scales, translation):
        return (rotated_source * scales) + translation

    def score(scales, translation) -> float:
        mapped = mapped_cloud(scales, translation)
        source_to_ref = _nearest_cloud_mean_square(mapped, reference)
        ref_to_source = _nearest_cloud_mean_square(reference, mapped)
        if not math.isfinite(source_to_ref) or not math.isfinite(ref_to_source):
            return float("inf")
        return math.sqrt(max(0.0, (source_to_ref + ref_to_source) * 0.5))

    current_score = score(current_scales, current_offset)
    if not math.isfinite(current_score):
        return None
    best_scales = current_scales.copy()
    best_offset = current_offset.copy()
    best_score = current_score
    trace: List[Dict[str, Any]] = []

    min_scales = initial_scales * 0.35
    max_scales = initial_scales * 2.75
    for iteration in range(max(0, int(max_iterations))):
        nearest, squared_distances = _nearest_cloud_pairs(
            mapped_cloud(current_scales, current_offset),
            reference,
        )
        if nearest is None or squared_distances is None or int(nearest.shape[0]) < 8:
            break
        cutoff = float(np.percentile(squared_distances, 80.0))
        mask = squared_distances <= cutoff
        if int(np.count_nonzero(mask)) < 20:
            mask = np.ones(int(squared_distances.shape[0]), dtype=bool)

        source_fit = rotated_source[mask]
        target_fit = nearest[mask]
        candidate_scales: List[float] = []
        candidate_offset: List[float] = []
        for axis in range(3):
            source_axis = source_fit[:, axis]
            target_axis = target_fit[:, axis]
            source_centered = source_axis - float(np.mean(source_axis))
            target_centered = target_axis - float(np.mean(target_axis))
            denom = float(np.sum(source_centered * source_centered))
            if denom <= 1.0e-12:
                scale = float(current_scales[axis])
            else:
                scale = float(np.sum(source_centered * target_centered) / denom)
            scale = max(float(min_scales[axis]), min(float(max_scales[axis]), scale))
            translation = float(np.mean(target_axis) - scale * np.mean(source_axis))
            candidate_scales.append(scale)
            candidate_offset.append(translation)

        next_scales = np.asarray(candidate_scales, dtype=np.float64)
        next_offset = np.asarray(candidate_offset, dtype=np.float64)
        next_score = score(next_scales, next_offset)
        trace.append({
            "iteration": int(iteration),
            "score_before": float(current_score),
            "score_after": float(next_score),
            "kept_pairs": int(np.count_nonzero(mask)),
        })
        if not math.isfinite(next_score) or next_score > current_score * 1.03:
            break
        current_scales = next_scales
        current_offset = next_offset
        current_score = next_score
        if next_score < best_score:
            best_score = next_score
            best_scales = next_scales.copy()
            best_offset = next_offset.copy()

    if best_score >= current_score and best_score >= score(initial_scales, np.asarray(offset, dtype=np.float64)):
        return None

    linear_matrix: Tuple[Vec3, Vec3, Vec3] = tuple(
        tuple(float(rotation[row, col]) * float(best_scales[row]) for col in range(3))
        for row in range(3)
    )  # type: ignore[assignment]
    return {
        "axis_scales": tuple(float(value) for value in best_scales),
        "offset": tuple(float(value) for value in best_offset),
        "linear_matrix": linear_matrix,
        "native_vertex_cloud_score": float(best_score),
        "iterations": len(trace),
        "trace": trace,
    }


def _replacement_axis_fit_seed(
    bounds: Tuple[Vec3, Vec3],
    reference_bounds: Tuple[Vec3, Vec3],
    *,
    prefer_identity: bool = False,
    source_vertices: Optional[Sequence[Vec3]] = None,
    reference_vertices: Optional[Sequence[Vec3]] = None,
) -> Optional[Dict[str, Any]]:
    """Find the signed axis frame that fits native bounds with least distortion."""

    bb_min, bb_max = bounds
    ref_min, ref_max = reference_bounds
    source_extents = tuple(max(0.0, float(bb_max[i]) - float(bb_min[i])) for i in range(3))
    target_extents = tuple(max(0.0, float(ref_max[i]) - float(ref_min[i])) for i in range(3))
    if min(source_extents) <= 1.0e-8 or min(target_extents) <= 1.0e-8:
        return None

    source_thin_axis = min(range(3), key=lambda axis: source_extents[axis])
    identity_rotation: Tuple[Vec3, Vec3, Vec3] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    best: Optional[Dict[str, Any]] = None
    for source_axes in itertools.permutations((0, 1, 2), 3):
        try:
            axis_scales = tuple(
                float(target_extents[target_axis]) / float(source_extents[source_axis])
                for target_axis, source_axis in enumerate(source_axes)
            )
        except Exception:
            continue
        if any((not math.isfinite(value)) or value <= 1.0e-8 for value in axis_scales):
            continue
        distortion = _axis_fit_distortion(axis_scales)
        semantic_penalty = 0.0
        if prefer_identity and source_axes[0] != 0:
            semantic_penalty += 0.25
        if source_axes[2] != source_thin_axis:
            semantic_penalty += 0.40
        for signs in itertools.product((-1.0, 1.0), repeat=3):
            rows: List[List[float]] = [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
            for target_axis, source_axis in enumerate(source_axes):
                rows[target_axis][source_axis] = signs[target_axis]
            rotation: Tuple[Vec3, Vec3, Vec3] = tuple(tuple(row) for row in rows)  # type: ignore[assignment]
            if _matrix_determinant(rotation) < 0.0:
                continue
            identity_penalty = 0.0
            if prefer_identity and rotation != identity_rotation:
                identity_penalty = 0.02
            sign_penalty = sum(0.001 for sign in signs if sign < 0.0)
            if signs[0] < 0.0:
                sign_penalty += 0.004
            if signs[2] < 0.0:
                sign_penalty += 0.002
            linear_matrix = _axis_scaled_matrix(rotation, axis_scales)
            cloud_score = None
            mapped_bounds = _transform_bounds(
                bounds,
                lambda point, matrix=linear_matrix: _mat_vec(matrix, point),
            )
            if mapped_bounds is not None:
                mapped_min, _mapped_max = mapped_bounds
                offset = (
                    float(ref_min[0]) - float(mapped_min[0]),
                    float(ref_min[1]) - float(mapped_min[1]),
                    float(ref_min[2]) - float(mapped_min[2]),
                )
                cloud_score = _point_cloud_fit_score(
                    source_vertices,
                    reference_vertices,
                    linear_matrix=linear_matrix,
                    offset=offset,
                )
            if cloud_score is not None:
                score = float(cloud_score) + (distortion * 0.01) + (sign_penalty * 0.001)
                score_basis = "native_vertex_cloud_chamfer"
            else:
                score = distortion + semantic_penalty + identity_penalty + sign_penalty
                score_basis = "bounds_extent_distortion"
            candidate = {
                "score": score,
                "score_basis": score_basis,
                "distortion": distortion,
                "native_vertex_cloud_score": cloud_score,
                "axis_scales": axis_scales,
                "source_axes": source_axes,
                "rotation_matrix": rotation,
                "source_extents": source_extents,
                "target_extents": target_extents,
                "source_right_axis": int(source_axes[0]),
                "source_forward_axis": int(source_axes[1]),
                "source_up_axis": int(source_axes[2]),
                "source_right_label": _axis_label_from_vector(rotation[0]),
                "source_forward_label": _axis_label_from_vector(rotation[1]),
                "source_up_label": _axis_label_from_vector(rotation[2]),
                "target_forward_label": "+y",
                "target_up_label": "+z",
            }
            if best is None or float(candidate["score"]) < float(best["score"]):
                best = candidate
    return best


def _uniform_creature_bounds_fit_from_axis_seed(
    bounds: Tuple[Vec3, Vec3],
    reference_bounds: Tuple[Vec3, Vec3],
    seed: Dict[str, Any],
    *,
    method: str = "creature_bounds_axis_candidates",
) -> Optional[Dict[str, Any]]:
    """Build a uniform creature fit from an already-scored axis frame."""

    bb_min, bb_max = bounds
    ref_min, ref_max = reference_bounds
    try:
        source_extents = tuple(float(value) for value in seed["source_extents"])
        target_extents = tuple(float(value) for value in seed["target_extents"])
        source_axes = (
            int(seed["source_right_axis"]),
            int(seed["source_forward_axis"]),
            int(seed["source_up_axis"]),
        )
        rotation: Tuple[Vec3, Vec3, Vec3] = seed["rotation_matrix"]
    except Exception:
        return None
    if len(source_extents) != 3 or len(target_extents) != 3:
        return None
    try:
        ratios = tuple(
            float(target_extents[target_axis]) / float(source_extents[source_axis])
            for target_axis, source_axis in enumerate(source_axes)
        )
    except Exception:
        return None
    if any((not math.isfinite(value)) or value <= 1.0e-8 for value in ratios):
        return None

    scale = _median_positive(ratios)
    linear_matrix = _scale_matrix(rotation, scale)

    def transform_without_offset(point: Vec3) -> Vec3:
        return _mat_vec(linear_matrix, point)

    mapped_bounds = _transform_bounds(bounds, transform_without_offset)
    if mapped_bounds is None:
        return None
    mapped_min, mapped_max = mapped_bounds
    mapped_center_x = (mapped_min[0] + mapped_max[0]) * 0.5
    mapped_center_y = (mapped_min[1] + mapped_max[1]) * 0.5
    target_center_x = (float(ref_min[0]) + float(ref_max[0])) * 0.5
    target_center_y = (float(ref_min[1]) + float(ref_max[1])) * 0.5
    offset = (
        target_center_x - mapped_center_x,
        target_center_y - mapped_center_y,
        float(ref_min[2]) - float(mapped_min[2]),
    )
    source_origin = _bounds_ground_center(bounds)
    target_origin = _vec_add(_mat_vec(linear_matrix, source_origin), offset)
    fit_transform = _fit_transform_metadata(
        policy="creature_bounds_basis",
        scale=scale,
        rotation_matrix=rotation,
        source_origin=source_origin,
        target_origin=target_origin,
        translation=offset,
    )
    return {
        "scale": float(scale),
        "rotation_matrix": rotation,
        "linear_matrix": linear_matrix,
        "offset": offset,
        "source_origin": source_origin,
        "target_origin": target_origin,
        "fit_transform": fit_transform,
        "source_up_axis": source_axes[2],
        "source_forward_axis": source_axes[1],
        "source_right_axis": source_axes[0],
        "source_up_label": str(seed.get("source_up_label") or _axis_label_from_index(source_axes[2])),
        "source_forward_label": str(seed.get("source_forward_label") or _axis_label_from_index(source_axes[1])),
        "target_up_label": str(seed.get("target_up_label") or "+z"),
        "target_forward_label": str(seed.get("target_forward_label") or "+y"),
        "source_height": source_extents[source_axes[2]],
        "target_height": target_extents[2],
        "scale_ratios": ratios,
        "source_extents": source_extents,
        "target_extents": target_extents,
        "axis_scales": [float(value) for value in seed.get("axis_scales", ratios)],
        "axis_fit_distortion": float(seed.get("distortion", _axis_fit_distortion(ratios))),
        "orientation_score_basis": str(seed.get("score_basis") or "bounds_extent_distortion"),
        "native_vertex_cloud_score": seed.get("native_vertex_cloud_score"),
        "method": method,
    }


def _creature_containment_orientation_seed(
    model: Any,
    bounds: Optional[Tuple[Vec3, Vec3]],
    reference_model: Optional[Any],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[Dict[str, Any]]:
    """Choose an open-creature orientation seed before containment staging."""

    if bounds is None or reference_bounds is None:
        return _creature_bounds_fit_solution(bounds, reference_bounds)
    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    external = metadata.get("external_import")
    external = external if isinstance(external, dict) else {}
    reference_name = str(getattr(reference_model, "name", "") or "")
    source_path = str(external.get("source_path") or "")
    same_resref = _replacement_source_matches_resref(source_path, reference_name)
    if same_resref:
        seed = _replacement_axis_fit_seed(
            bounds,
            reference_bounds,
            prefer_identity=external.get("target_axis_system") == "kotor_z_up",
            source_vertices=_mesh_vertex_cloud(model),
            reference_vertices=_mesh_vertex_cloud(reference_model),
        )
        if seed is not None:
            fitted = _uniform_creature_bounds_fit_from_axis_seed(
                bounds,
                reference_bounds,
                seed,
                method=(
                    "native_vertex_cloud_containment_seed"
                    if str(seed.get("score_basis") or "") == "native_vertex_cloud_chamfer"
                    else "same_resref_axis_candidate_seed"
                ),
            )
            if fitted is not None:
                return fitted
    return _creature_bounds_fit_solution(bounds, reference_bounds)


def _fit_transform_metadata_from_matrix(
    *,
    policy: str,
    linear_matrix: Tuple[Vec3, Vec3, Vec3],
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    scale: float,
    source_origin: Vec3,
    target_origin: Vec3,
    translation: Vec3,
    axis_scales: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    result = _fit_transform_metadata(
        policy=policy,
        scale=scale,
        rotation_matrix=rotation_matrix,
        source_origin=source_origin,
        target_origin=target_origin,
        translation=translation,
    )
    result["linear_matrix"] = _matrix_as_lists(linear_matrix)
    if axis_scales is not None:
        result["axis_scales"] = [float(value) for value in axis_scales]
        result["non_uniform_scale_baked"] = True
    return result


def _native_template_scaled_bounds_fit(
    model: Any,
    *,
    bounds: Tuple[Vec3, Vec3],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
    reference_model: Any,
    reference_label: str,
    fit_report: Any,
) -> Optional[Dict[str, Any]]:
    """Fit a same-resref replacement OBJ to the selected native mesh frame.

    A re-UV'd OBJ exported from a KOTOR creature often arrives normalized around
    its DCC origin.  With no imported skeleton landmarks, generic containment
    can only put the donor bones inside the source bounds.  For a direct
    replacement whose filename resolves to the selected native resref, the
    native render bounds are stronger evidence than the OBJ pivot.
    """

    if reference_bounds is None:
        return None
    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    external = metadata.get("external_import")
    external = external if isinstance(external, dict) else {}
    source_path = str(external.get("source_path") or "")
    label = reference_label or getattr(reference_model, "name", "") or ""
    if not _replacement_source_matches_resref(source_path, str(label)):
        return None

    source_vertices = _mesh_vertex_cloud(model)
    reference_vertices = _mesh_vertex_cloud(reference_model)
    seed = _replacement_axis_fit_seed(
        bounds,
        reference_bounds,
        prefer_identity=external.get("target_axis_system") == "kotor_z_up",
        source_vertices=source_vertices,
        reference_vertices=reference_vertices,
    )
    if seed is None:
        seed = _creature_bounds_fit_solution(bounds, reference_bounds)
    if seed is None:
        return None
    source_extents = tuple(float(value) for value in seed.get("source_extents", ()))
    target_extents = tuple(float(value) for value in seed.get("target_extents", ()))
    if len(source_extents) != 3 or len(target_extents) != 3:
        return None
    source_axes = (
        int(seed["source_right_axis"]),
        int(seed["source_forward_axis"]),
        int(seed["source_up_axis"]),
    )
    rotation = seed["rotation_matrix"]
    try:
        axis_scales = tuple(
            float(target_extents[target_axis]) / float(source_extents[source_axis])
            for target_axis, source_axis in enumerate(source_axes)
        )
    except Exception:
        return None
    if any((not math.isfinite(value)) or value <= 1.0e-8 for value in axis_scales):
        return None

    linear_matrix = _axis_scaled_matrix(rotation, axis_scales)

    def transform_without_offset(point: Vec3) -> Vec3:
        return _mat_vec(linear_matrix, point)

    mapped_bounds = _transform_bounds(bounds, transform_without_offset)
    if mapped_bounds is None:
        return None
    ref_min, _ref_max = reference_bounds
    mapped_min, _mapped_max = mapped_bounds
    offset: Vec3 = (
        float(ref_min[0]) - float(mapped_min[0]),
        float(ref_min[1]) - float(mapped_min[1]),
        float(ref_min[2]) - float(mapped_min[2]),
    )
    surface_refinement = _surface_refined_axis_fit(
        source_vertices,
        reference_vertices,
        rotation_matrix=rotation,
        axis_scales=axis_scales,
        offset=offset,
    )
    surface_refined = False
    surface_iterations = 0
    if surface_refinement is not None:
        axis_scales = tuple(float(value) for value in surface_refinement["axis_scales"])
        linear_matrix = surface_refinement["linear_matrix"]
        offset = surface_refinement["offset"]
        surface_refined = True
        surface_iterations = int(surface_refinement.get("iterations", 0) or 0)
    native_cloud_score = (
        surface_refinement.get("native_vertex_cloud_score")
        if surface_refinement is not None else
        seed.get("native_vertex_cloud_score")
    )

    deformation_bones, skipped_bones, bone_source = _reference_containment_fit_positions(reference_model)
    pivot_bones, pivot_skipped, _pivot_source = _skin_bone_map_fit_positions(reference_model)
    _pivot_fit_bones, pivot_outliers = _filter_reference_nearby_points(
        pivot_bones,
        reference_bounds,
    )
    skipped_bones = list(skipped_bones) + list(pivot_skipped) + [name for name, _point in pivot_outliers]
    bone_positions = [point for _name, point in deformation_bones]
    containment_adjusted_axes: List[str] = []
    containment_padding = _axis_scale_padding_to_contain_points(
        bounds=bounds,
        rotation_matrix=rotation,
        axis_scales=axis_scales,
        offset=offset,
        target_points=bone_positions,
        source_vertices=source_vertices,
        reference_vertices=reference_vertices,
        baseline_score=(
            float(native_cloud_score)
            if native_cloud_score is not None and math.isfinite(float(native_cloud_score))
            else None
        ),
    )
    if containment_padding is not None:
        axis_scales = tuple(float(value) for value in containment_padding["axis_scales"])
        linear_matrix = containment_padding["linear_matrix"]
        offset = containment_padding["offset"]
        containment_adjusted_axes = list(containment_padding.get("adjusted_axes") or [])
        if containment_padding.get("native_vertex_cloud_score") is not None:
            native_cloud_score = containment_padding.get("native_vertex_cloud_score")

    def transform_point(point: Vec3) -> Vec3:
        return _vec_add(_mat_vec(linear_matrix, point), offset)

    source_origin = _bounds_ground_center(bounds)
    target_origin = transform_point(source_origin)
    scale = _median_positive(axis_scales)
    fit_transform = _fit_transform_metadata_from_matrix(
        policy="native_template_scaled_bounds_replacement",
        linear_matrix=linear_matrix,
        rotation_matrix=rotation,
        scale=scale,
        source_origin=source_origin,
        target_origin=target_origin,
        translation=offset,
        axis_scales=axis_scales,
    )
    fitted_visual_overlay = {
        "coordinate_space": "kotor_world_after_fit",
        "source": _fit_frame_visual_overlay(
            model,
            None,
            bounds,
            transform_point=transform_point,
            axis_length_scale=scale,
        ),
        "target": _fit_frame_visual_overlay(reference_model, None, reference_bounds),
    }
    fitted_bounds = _transform_bounds(bounds, transform_point)
    if fitted_bounds is not None and bone_positions:
        all_bones_inside, outside_count = _bounds_contains_points(fitted_bounds, bone_positions)
    else:
        all_bones_inside, outside_count = False, len(bone_positions)
    source_bounds = _bounds_as_lists(bounds)
    target_bounds = _bounds_as_lists(reference_bounds)
    auto_fit_report = dict(
        (fit_report.get("auto_fit_report") if isinstance(fit_report, dict) else None)
        or {}
    )
    auto_fit_report.update({
        "source_forward_axis": str(seed["source_forward_label"]),
        "source_up_axis": str(seed["source_up_label"]),
        "target_forward_axis": str(seed["target_forward_label"]),
        "target_up_axis": str(seed["target_up_label"]),
        "scale_factor": float(scale),
        "axis_scales": [float(value) for value in axis_scales],
        "height_source": "native_template_render_bounds",
        "ground_origin_basis": (
            "native_template_surface_registration_with_anchor_padding"
            if containment_adjusted_axes else
            "native_template_surface_registration"
            if surface_refined else
            "native_template_bounds_min_corner"
        ),
        "used_landmarks": [
            "source:replacement_filename",
            "source:render_bounds",
            "source:least_distorting_axis_permutation",
            "target:selected_native_render_bounds",
            "target:selected_native_surface_vertices",
            "target:selected_native_weighted_skin_regions",
        ],
        "confidence": 0.9,
        "fallback_used": False,
        "notes": (
            "Imported mesh filename matches the selected native template; "
            "native render bounds seeded the fit, native surface registration refined placement, "
            "and a bounded center-preserving axis pad covered donor deformation anchors."
            if containment_adjusted_axes else
            "Imported mesh filename matches the selected native template; "
            "native render bounds seeded the fit and native surface registration refined the final placement."
            if surface_refined else
            "Imported mesh filename matches the selected native template; "
            "native render bounds and least-distorting axis fit drove the baked replacement fit."
        ),
    })
    report = dict(fit_report) if isinstance(fit_report, dict) else {}
    report.update({
        "ok": True,
        "code": "native_template_scaled_bounds_replacement",
        "message": "External replacement mesh fit to the selected native KOTOR template bounds.",
        "fit_policy": "native_template_scaled_bounds_replacement",
        "scale_basis": "native_template_axis_bounds_ratio",
        "scale": float(scale),
        "axis_scales": [float(value) for value in axis_scales],
        "axis_fit_distortion": float(seed.get("distortion", _axis_fit_distortion(axis_scales))),
        "orientation_score_basis": (
            "native_vertex_cloud_iterative_surface"
            if surface_refined else
            str(seed.get("score_basis") or "bounds_extent_distortion")
        ),
        "native_vertex_cloud_score": native_cloud_score,
        "surface_registration_refined": bool(surface_refined),
        "surface_registration_iterations": int(surface_iterations),
        "all_bones_inside": bool(all_bones_inside),
        "outside_count": int(outside_count),
        "bone_position_source": bone_source,
        "deformation_bone_count": len(deformation_bones),
        "dummy_bone_count": len(skipped_bones),
        "skeleton_containment_adjusted_axes": list(containment_adjusted_axes),
        "skeleton_pivot_outlier_count": len(pivot_outliers),
        "skeleton_pivot_outlier_names": [name for name, _point in pivot_outliers],
        "source_height": float(source_extents[int(seed["source_up_axis"])]),
        "target_height": float(target_extents[2]),
        "vertical_axis": str(seed["source_up_label"]).lstrip("+"),
        "reference": str(label or ""),
        "source_bounds": source_bounds,
        "reference_bounds": target_bounds,
        "source_forward_axis": str(seed["source_forward_label"]),
        "source_up_axis": str(seed["source_up_label"]),
        "target_forward_axis": str(seed["target_forward_label"]),
        "target_up_axis": str(seed["target_up_label"]),
        "scale_factor": float(scale),
        "height_source": auto_fit_report["height_source"],
        "ground_origin_basis": auto_fit_report["ground_origin_basis"],
        "used_landmarks": list(auto_fit_report["used_landmarks"]),
        "confidence": float(auto_fit_report["confidence"]),
        "fallback_used": False,
        "notes": str(auto_fit_report["notes"]),
        "auto_fit_report": auto_fit_report,
        "fit_transform": fit_transform,
        "fitted_visual_overlay": fitted_visual_overlay,
        "native_template_scaled_bounds_replacement": {
            "source_bounds": source_bounds,
            "reference_bounds": target_bounds,
            "source_path": source_path,
            "axis_scales": [float(value) for value in axis_scales],
            "axis_fit_distortion": float(seed.get("distortion", _axis_fit_distortion(axis_scales))),
            "orientation_score_basis": (
                "native_vertex_cloud_iterative_surface"
                if surface_refined else
                str(seed.get("score_basis") or "bounds_extent_distortion")
            ),
            "native_vertex_cloud_score": native_cloud_score,
            "surface_registration_refined": bool(surface_refined),
            "surface_registration_iterations": int(surface_iterations),
            "all_bones_inside": bool(all_bones_inside),
            "outside_count": int(outside_count),
            "bone_position_source": bone_source,
            "deformation_bone_count": len(deformation_bones),
            "skeleton_containment_adjusted_axes": list(containment_adjusted_axes),
            "skeleton_pivot_outlier_count": len(pivot_outliers),
            "source_axes": [int(value) for value in source_axes],
            "reference_label": str(label or ""),
        },
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
    })
    return {
        "scale": float(scale),
        "axis_scales": axis_scales,
        "axis_fit_distortion": float(seed.get("distortion", _axis_fit_distortion(axis_scales))),
        "orientation_score_basis": (
            "native_vertex_cloud_iterative_surface"
            if surface_refined else
            str(seed.get("score_basis") or "bounds_extent_distortion")
        ),
        "native_vertex_cloud_score": native_cloud_score,
        "surface_registration_refined": bool(surface_refined),
        "surface_registration_iterations": int(surface_iterations),
        "all_bones_inside": bool(all_bones_inside),
        "outside_count": int(outside_count),
        "bone_position_source": bone_source,
        "deformation_bone_count": len(deformation_bones),
        "skeleton_containment_adjusted_axes": list(containment_adjusted_axes),
        "skeleton_pivot_outlier_count": len(pivot_outliers),
        "rotation_matrix": rotation,
        "linear_matrix": linear_matrix,
        "offset": offset,
        "source_origin": source_origin,
        "target_origin": target_origin,
        "source_height": float(source_extents[int(seed["source_up_axis"])]),
        "target_height": float(target_extents[2]),
        "source_up_label": str(seed["source_up_label"]),
        "source_forward_label": str(seed["source_forward_label"]),
        "fit_transform": fit_transform,
        "fit_report": report,
        "fitted_visual_overlay": fitted_visual_overlay,
    }


_NON_DEFORMING_ATTACHMENT_NAMES = {
    "camerahook",
    "camera_hook",
    "camhook",
    "impact_bolt",
    "handconjure",
    "chestconjure",
}


def _node_lookup_by_name(model: Any) -> Dict[str, Any]:
    nodes: Dict[str, Any] = {}
    if model is None:
        return nodes
    for node in _iter_model_nodes(model):
        raw = str(getattr(node, "name", "") or "").strip()
        if not raw:
            continue
        nodes.setdefault(raw.lower(), node)
        clean = _clean_landmark_name(raw)
        if clean:
            nodes.setdefault(clean, node)
    return nodes


def _skin_bone_map_fit_positions(
    reference_model: Any,
) -> Tuple[List[Tuple[str, Vec3]], List[str], str]:
    """Return donor deformation positions from actual skin bone palettes.

    KOTOR skin meshes store the deformation authority in their compact
    ``bone_map`` palette.  The skinned mesh node itself is only render payload;
    fitting to that node's origin makes replacement meshes shrink around
    ``(0, 0, 0)`` instead of around the skeleton that will animate them.
    """

    if reference_model is None:
        return [], [], "none"
    lookup = _node_lookup_by_name(reference_model)
    positions: List[Tuple[str, Vec3]] = []
    skipped: List[str] = []
    seen: set[str] = set()
    for node in _iter_model_nodes(reference_model):
        bone_map = list(getattr(node, "bone_map", []) or [])
        if not bone_map:
            continue
        has_skin_evidence = (
            bool(getattr(node, "is_skin", False))
            or bool(getattr(node, "skin_data", None))
            or bool(getattr(node, "vertices", None))
        )
        if not has_skin_evidence:
            continue
        for bone_name in bone_map:
            raw = str(bone_name or "").strip()
            key = raw.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            clean = _clean_landmark_name(raw)
            if key in _NON_DEFORMING_ATTACHMENT_NAMES or clean in _NON_DEFORMING_ATTACHMENT_NAMES:
                skipped.append(raw)
                continue
            bone_node = lookup.get(key) or lookup.get(clean)
            pos = _node_fit_position(bone_node) if bone_node is not None else None
            if pos is None:
                skipped.append(raw)
                continue
            positions.append((raw, (float(pos[0]), float(pos[1]), float(pos[2]))))
    return positions, skipped, "skin_bone_map" if positions else "none"


def _skin_weighted_bone_map_fit_positions(
    reference_model: Any,
) -> Tuple[List[Tuple[str, Vec3]], List[str], str]:
    """Return donor bone fit anchors from weighted skin vertices.

    KOTOR creature joint pivots are not guaranteed to live inside the visible
    surface.  Drexl is the sharp example: several wing/torso pivots sit above
    the vanilla mesh bounds even though their weighted vertex regions are
    correct.  For replacement-mesh containment we therefore use the donor's
    skinned deformation envelopes as the primary fit anchors and fall back to
    raw pivot positions only when no weight evidence exists.
    """

    if reference_model is None:
        return [], [], "none"
    positions: List[Tuple[str, Vec3]] = []
    skipped: List[str] = []
    seen_skipped: set[str] = set()
    accum: Dict[str, List[float]] = {}
    order: List[str] = []

    for node in _iter_model_nodes(reference_model):
        bone_map = list(getattr(node, "bone_map", []) or [])
        skin_data = list(getattr(node, "skin_data", []) or [])
        vertices = list(getattr(node, "vertices", []) or [])
        if not bone_map or not skin_data or not vertices:
            continue
        for index, vertex in enumerate(vertices[:len(skin_data)]):
            if vertex is None or len(vertex) < 3:
                continue
            vertex_skin = skin_data[index]
            influences = list(getattr(vertex_skin, "influences", []) or [])
            if not influences:
                continue
            try:
                vx, vy, vz = float(vertex[0]), float(vertex[1]), float(vertex[2])
            except Exception:
                continue
            for influence in influences:
                try:
                    bone_index = int(getattr(influence, "bone_index"))
                    weight = float(getattr(influence, "weight"))
                except Exception:
                    continue
                if weight <= 1.0e-8 or bone_index < 0 or bone_index >= len(bone_map):
                    continue
                raw = str(bone_map[bone_index] or "").strip()
                key = raw.lower()
                clean = _clean_landmark_name(raw)
                if not key:
                    continue
                if key in _NON_DEFORMING_ATTACHMENT_NAMES or clean in _NON_DEFORMING_ATTACHMENT_NAMES:
                    if key not in seen_skipped:
                        skipped.append(raw)
                        seen_skipped.add(key)
                    continue
                if key not in accum:
                    accum[key] = [raw, 0.0, 0.0, 0.0, 0.0]
                    order.append(key)
                row = accum[key]
                row[1] += vx * weight
                row[2] += vy * weight
                row[3] += vz * weight
                row[4] += weight

    for key in order:
        raw, sx, sy, sz, total_weight = accum[key]
        if total_weight <= 1.0e-8:
            continue
        positions.append((
            str(raw),
            (
                float(sx) / float(total_weight),
                float(sy) / float(total_weight),
                float(sz) / float(total_weight),
            ),
        ))
    return positions, skipped, "skin_weighted_vertex_centroids" if positions else "none"


def _reference_containment_fit_positions(
    reference_model: Any,
) -> Tuple[List[Tuple[str, Vec3]], List[str], str]:
    """Return the safest donor points for replacement-mesh containment."""

    weighted_positions, weighted_skipped, weighted_source = _skin_weighted_bone_map_fit_positions(
        reference_model,
    )
    if weighted_positions:
        return weighted_positions, weighted_skipped, weighted_source
    return _skin_bone_map_fit_positions(reference_model)


def _mesh_face_closure_summary(faces: Sequence[Sequence[int]]) -> Dict[str, Any]:
    """Fast manifold-edge check used before expensive ray containment."""

    edge_counts: Dict[Tuple[int, int], int] = {}
    polygon_count = 0
    for face in faces:
        if face is None or len(face) < 3:
            continue
        polygon_count += 1
        indices = [int(index) for index in face]
        for index, start in enumerate(indices):
            end = indices[(index + 1) % len(indices)]
            edge = (start, end) if start <= end else (end, start)
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    boundary_edges = sum(1 for count in edge_counts.values() if count == 1)
    nonmanifold_edges = sum(1 for count in edge_counts.values() if count > 2)
    return {
        "face_count": polygon_count,
        "edge_count": len(edge_counts),
        "boundary_edge_count": boundary_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "watertight": bool(edge_counts) and boundary_edges == 0 and nonmanifold_edges == 0,
    }


def _bounds_contains_points(
    bounds: Tuple[Vec3, Vec3],
    points: Sequence[Vec3],
    *,
    tolerance: float = 1.0e-5,
) -> Tuple[bool, int]:
    bb_min, bb_max = bounds
    outside = 0
    for point in points:
        if any(
            float(point[i]) < float(bb_min[i]) - tolerance
            or float(point[i]) > float(bb_max[i]) + tolerance
            for i in range(3)
        ):
            outside += 1
    return outside == 0, outside


def _filter_reference_nearby_points(
    points: Sequence[Tuple[str, Vec3]],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
    *,
    expansion_fraction: float = 0.45,
    min_expansion: float = 0.75,
) -> Tuple[List[Tuple[str, Vec3]], List[Tuple[str, Vec3]]]:
    """Split plausible native pivots from true outliers.

    A few KOTOR creature pivots are authored just outside the render shell and
    must drive fit staging.  A corrupted/imported helper hundreds of units away
    should not.  The threshold is intentionally generous relative to the native
    reference extents so Drexl wing pivots survive while pathological points do
    not explode the fit.
    """

    if reference_bounds is None:
        return list(points), []
    ref_min, ref_max = reference_bounds
    limits: List[Tuple[float, float]] = []
    for axis in range(3):
        extent = max(float(ref_max[axis]) - float(ref_min[axis]), 1.0e-6)
        pad = max(extent * float(expansion_fraction), float(min_expansion))
        limits.append((float(ref_min[axis]) - pad, float(ref_max[axis]) + pad))
    nearby: List[Tuple[str, Vec3]] = []
    outliers: List[Tuple[str, Vec3]] = []
    for name, point in points:
        try:
            pos = (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            outliers.append((str(name), point))
            continue
        if all(limits[axis][0] <= pos[axis] <= limits[axis][1] for axis in range(3)):
            nearby.append((str(name), pos))
        else:
            outliers.append((str(name), pos))
    return nearby, outliers


def _bounds_for_points(points: Sequence[Vec3]) -> Optional[Tuple[Vec3, Vec3]]:
    if not points:
        return None
    return (
        tuple(min(float(point[axis]) for point in points) for axis in range(3)),  # type: ignore[return-value]
        tuple(max(float(point[axis]) for point in points) for axis in range(3)),  # type: ignore[return-value]
    )


def _containment_offset_from_bounds(
    mapped_bounds: Tuple[Vec3, Vec3],
    reference_bounds: Tuple[Vec3, Vec3],
    bone_bounds: Optional[Tuple[Vec3, Vec3]],
) -> Tuple[Vec3, List[str]]:
    """Return an offset that preserves native placement but contains bones."""

    mapped_min, mapped_max = mapped_bounds
    ref_min, ref_max = reference_bounds
    adjusted_axes: List[str] = []
    offset: List[float] = [
        float(ref_min[axis]) - float(mapped_min[axis])
        for axis in range(3)
    ]
    if bone_bounds is None:
        return (offset[0], offset[1], offset[2]), adjusted_axes
    bone_min, bone_max = bone_bounds
    axis_names = ("x", "y", "z")
    for axis in range(3):
        mesh_min = float(mapped_min[axis]) + offset[axis]
        mesh_max = float(mapped_max[axis]) + offset[axis]
        b_min = float(bone_min[axis])
        b_max = float(bone_max[axis])
        if b_min >= mesh_min - 1.0e-5 and b_max <= mesh_max + 1.0e-5:
            continue
        mesh_extent = max(float(mapped_max[axis]) - float(mapped_min[axis]), 1.0e-6)
        bone_extent = max(b_max - b_min, 0.0)
        if bone_extent <= mesh_extent + 1.0e-5:
            mesh_center_no_offset = (float(mapped_min[axis]) + float(mapped_max[axis])) * 0.5
            bone_center = (b_min + b_max) * 0.5
            offset[axis] = bone_center - mesh_center_no_offset
        else:
            offset[axis] = b_min - float(mapped_min[axis])
        adjusted_axes.append(axis_names[axis])
    return (offset[0], offset[1], offset[2]), adjusted_axes


def _axis_scale_padding_to_contain_points(
    *,
    bounds: Tuple[Vec3, Vec3],
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    axis_scales: Sequence[float],
    offset: Vec3,
    target_points: Sequence[Vec3],
    source_vertices: Optional[Sequence[Vec3]] = None,
    reference_vertices: Optional[Sequence[Vec3]] = None,
    baseline_score: Optional[float] = None,
    max_axis_factor: float = 1.12,
    max_score_factor: float = 1.15,
) -> Optional[Dict[str, Any]]:
    """Gently expand target axes so donor anchors fit without translating.

    This is intentionally different from ``_containment_offset_from_bounds``:
    for direct replacements, translating the mesh to chase pivots breaks the
    native surface registration.  A small center-preserving scale pad can cover
    authoring tolerances while keeping the registered surface in place.
    """

    if not target_points:
        return None
    try:
        scales = [float(value) for value in axis_scales]
        translation = [float(value) for value in offset]
    except Exception:
        return None
    linear_matrix = _axis_scaled_matrix(rotation_matrix, scales)

    def transform_point(point: Vec3) -> Vec3:
        return _vec_add(_mat_vec(linear_matrix, point), (translation[0], translation[1], translation[2]))

    fitted_bounds = _transform_bounds(bounds, transform_point)
    rotated_bounds = _transform_bounds(bounds, lambda point: _mat_vec(rotation_matrix, point))
    bone_bounds = _bounds_for_points(target_points)
    if fitted_bounds is None or rotated_bounds is None or bone_bounds is None:
        return None
    fitted_min, fitted_max = fitted_bounds
    rotated_min, rotated_max = rotated_bounds
    bone_min, bone_max = bone_bounds
    adjusted_axes: List[str] = []
    axis_names = ("x", "y", "z")
    for axis in range(3):
        current_min = float(fitted_min[axis])
        current_max = float(fitted_max[axis])
        current_half = max((current_max - current_min) * 0.5, 1.0e-8)
        center = (current_min + current_max) * 0.5
        desired_half = max(
            center - float(bone_min[axis]),
            float(bone_max[axis]) - center,
        )
        if desired_half <= current_half + 1.0e-5:
            continue
        factor = (desired_half / current_half) * 1.01
        if factor <= 1.0 or factor > float(max_axis_factor):
            continue
        scales[axis] *= factor
        rotated_center = (float(rotated_min[axis]) + float(rotated_max[axis])) * 0.5
        translation[axis] = center - (rotated_center * scales[axis])
        adjusted_axes.append(axis_names[axis])
    if not adjusted_axes:
        return None

    padded_linear = _axis_scaled_matrix(rotation_matrix, scales)
    padded_offset: Vec3 = (translation[0], translation[1], translation[2])
    padded_score = _point_cloud_fit_score(
        source_vertices,
        reference_vertices,
        linear_matrix=padded_linear,
        offset=padded_offset,
    )
    if (
        baseline_score is not None
        and padded_score is not None
        and math.isfinite(float(baseline_score))
        and math.isfinite(float(padded_score))
        and float(padded_score) > float(baseline_score) * float(max_score_factor)
    ):
        return None
    return {
        "axis_scales": tuple(float(value) for value in scales),
        "offset": padded_offset,
        "linear_matrix": padded_linear,
        "adjusted_axes": adjusted_axes,
        "native_vertex_cloud_score": padded_score,
    }


def _split_reference_containment_bones(
    deformation_bones: Sequence[Tuple[str, Vec3]],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
    *,
    tolerance: float = 0.02,
) -> Tuple[List[Tuple[str, Vec3]], List[Tuple[str, Vec3]]]:
    """Split donor bones into hard fit drivers and soft reported outliers."""

    if reference_bounds is None:
        return list(deformation_bones), []
    bb_min, bb_max = reference_bounds
    hard: List[Tuple[str, Vec3]] = []
    soft: List[Tuple[str, Vec3]] = []
    for name, point in deformation_bones:
        try:
            pos = (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            soft.append((str(name), point))
            continue
        inside = True
        for axis in range(3):
            if pos[axis] < float(bb_min[axis]) - tolerance or pos[axis] > float(bb_max[axis]) + tolerance:
                inside = False
                break
        if inside:
            hard.append((str(name), pos))
        else:
            soft.append((str(name), pos))
    return hard, soft


def _oriented_bounds_containment_solution(
    *,
    mesh_vertices: Any,
    bounds: Tuple[Vec3, Vec3],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
    bone_positions: Sequence[Vec3],
    report_bone_positions: Optional[Sequence[Vec3]] = None,
    orientation_seed: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Fit an open mesh by rotated bounds when surface volume is invalid."""

    try:
        import numpy as np
    except Exception:  # pragma: no cover - project dependency
        return None
    if not bone_positions:
        return None
    seed = orientation_seed or _creature_bounds_fit_solution(bounds, reference_bounds)
    if seed is None:
        return None
    rotation: Tuple[Vec3, Vec3, Vec3] = seed["rotation_matrix"]
    linear_matrix: Tuple[Vec3, Vec3, Vec3] = seed["linear_matrix"]
    offset: Vec3 = seed["offset"]
    bone_list = [
        (float(point[0]), float(point[1]), float(point[2]))
        for point in bone_positions
    ]
    report_bone_list = [
        (float(point[0]), float(point[1]), float(point[2]))
        for point in (report_bone_positions or bone_positions)
    ]

    def transform_point(point: Vec3) -> Vec3:
        return _vec_add(_mat_vec(linear_matrix, point), offset)

    mapped_bounds = _transform_bounds(bounds, transform_point)
    if mapped_bounds is None:
        return None
    all_inside, outside_count = _bounds_contains_points(mapped_bounds, bone_list)
    total_inside, total_outside_count = _bounds_contains_points(mapped_bounds, report_bone_list)
    scale = float(seed["scale"])
    method = "oriented_bounds_reference_seed"

    def bone_bbox_expand_fit():
        mesh_np = np.asarray(mesh_vertices, dtype=np.float64)
        rot_np = np.asarray(rotation, dtype=np.float64)
        rotated = (rot_np @ mesh_np.T).T
        mesh_min = rotated.min(axis=0)
        mesh_max = rotated.max(axis=0)
        mesh_extent = np.maximum(mesh_max - mesh_min, 1.0e-9)
        mesh_center = (mesh_min + mesh_max) * 0.5
        bone_np = np.asarray(bone_list, dtype=np.float64)
        bone_min = bone_np.min(axis=0)
        bone_max = bone_np.max(axis=0)
        bone_extent = np.maximum(bone_max - bone_min, 1.0e-9)
        bone_center = (bone_min + bone_max) * 0.5
        candidate_scale = max(scale, float(np.max(bone_extent / mesh_extent)) * 1.02)
        candidate_offset_arr = bone_center - mesh_center * candidate_scale
        candidate_offset = (
            float(candidate_offset_arr[0]),
            float(candidate_offset_arr[1]),
            float(candidate_offset_arr[2]),
        )
        candidate_linear = _scale_matrix(rotation, candidate_scale)

        def adjusted_transform(point: Vec3) -> Vec3:
            return _vec_add(_mat_vec(candidate_linear, point), candidate_offset)

        candidate_mapped = _transform_bounds(bounds, adjusted_transform)
        if candidate_mapped is None:
            return None
        candidate_inside, candidate_outside = _bounds_contains_points(candidate_mapped, bone_list)
        return (
            candidate_scale,
            candidate_linear,
            candidate_offset,
            candidate_mapped,
            candidate_inside,
            candidate_outside,
        )

    if not all_inside:
        if reference_bounds is not None:
            ref_min, ref_max = reference_bounds

            def anchored_fit(candidate_scale: float):
                candidate_linear = _scale_matrix(rotation, candidate_scale)

                def candidate_no_offset(point: Vec3) -> Vec3:
                    return _mat_vec(candidate_linear, point)

                candidate_bounds = _transform_bounds(bounds, candidate_no_offset)
                if candidate_bounds is None:
                    return None
                candidate_min, candidate_max = candidate_bounds
                candidate_offset = (
                    ((float(ref_min[0]) + float(ref_max[0])) * 0.5)
                    - ((candidate_min[0] + candidate_max[0]) * 0.5),
                    ((float(ref_min[1]) + float(ref_max[1])) * 0.5)
                    - ((candidate_min[1] + candidate_max[1]) * 0.5),
                    float(ref_min[2]) - float(candidate_min[2]),
                )

                def candidate_transform(point: Vec3) -> Vec3:
                    return _vec_add(_mat_vec(candidate_linear, point), candidate_offset)

                candidate_mapped = _transform_bounds(bounds, candidate_transform)
                if candidate_mapped is None:
                    return None
                candidate_inside, candidate_outside = _bounds_contains_points(
                    candidate_mapped,
                    bone_list,
                )
                return (
                    candidate_scale,
                    candidate_linear,
                    candidate_offset,
                    candidate_mapped,
                    candidate_inside,
                    candidate_outside,
                )

            max_scale = scale * 1.40
            high = anchored_fit(max_scale)
            for _ in range(8):
                if high is None or bool(high[4]):
                    break
                max_scale *= 1.35
                high = anchored_fit(max_scale)
            if high is None:
                return None
            if bool(high[4]):
                lo = scale
                hi = max_scale
                best = high
                for _ in range(18):
                    mid = (lo + hi) * 0.5
                    candidate = anchored_fit(mid)
                    if candidate is None:
                        break
                    if bool(candidate[4]):
                        best = candidate
                        hi = mid
                    else:
                        lo = mid
                scale, linear_matrix, offset, mapped_bounds, all_inside, outside_count = best
                method = "oriented_bounds_reference_anchor_expand"
            else:
                expanded = bone_bbox_expand_fit()
                if expanded is None:
                    return None
                scale, linear_matrix, offset, mapped_bounds, all_inside, outside_count = expanded
                method = "oriented_bounds_bone_bbox_expand"
        else:
            expanded = bone_bbox_expand_fit()
            if expanded is None:
                return None
            scale, linear_matrix, offset, mapped_bounds, all_inside, outside_count = expanded
            method = "oriented_bounds_bone_bbox_expand"

        total_inside, total_outside_count = _bounds_contains_points(
            mapped_bounds,
            report_bone_list,
        )

    source_origin = _bounds_ground_center(bounds)
    target_origin = _vec_add(_mat_vec(linear_matrix, source_origin), offset)
    fit_transform = _fit_transform_metadata(
        policy="containment_bone_inside_mesh",
        scale=scale,
        rotation_matrix=rotation,
        source_origin=source_origin,
        target_origin=target_origin,
        translation=offset,
    )
    return {
        "scale": scale,
        "rotation_matrix": rotation,
        "linear_matrix": linear_matrix,
        "offset": offset,
        "source_origin": source_origin,
        "target_origin": target_origin,
        "fit_transform": fit_transform,
        "all_inside": bool(all_inside),
        "outside_count": int(outside_count),
        "total_bones_inside": bool(total_inside),
        "total_outside_count": int(total_outside_count),
        "max_penetration": 0.0,
        "method": method,
        "containment_volume": "oriented_bounds",
        "surface_containment_checked": False,
        "containment_guarantee": "oriented_bounds_only",
        "source_up_label": str(seed.get("source_up_label") or "unknown"),
        "source_forward_label": str(seed.get("source_forward_label") or "unknown"),
    }


def _landmark_based_fit_solution(
    model: Any,
    bounds: Optional[Tuple[Vec3, Vec3]],
    reference_model: Any,
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[Dict[str, Any]]:
    """Landmark-based rigid alignment using donor skeleton bone positions.

    Replaces the bounding-box-extent heuristic (:func:`_creature_bounds_fit_solution`)
    with a Kabsch optimal rigid alignment between the imported mesh's
    vertex-cloud extrema and the donor model's actual bone/node positions.

    The donor (reference) bone positions are read in the same KOTOR world
    space that :func:`_reference_model_fit_bounds` reports, via
    :func:`_node_fit_position` (which prefers ``external_world_position`` /
    ``bone_world_position`` / ``world_transform`` before the raw local
    ``position``), so the solved transform lands the mesh in KOTOR world
    space just like the bounds-based solutions do.

    Returns ``None`` when the donor exposes fewer than four usable bone/node
    positions — a stable Kabsch fit needs at least three non-collinear
    points, and we keep a margin.  The caller then falls back to the
    creature-bounds heuristic.
    """

    if reference_model is None or bounds is None:
        return None

    # Heavy imports stay lazy so this module stays importable without NumPy.
    try:
        import numpy as np
        from src.math.landmark_alignment import align_mesh_to_skeleton
    except Exception:  # pragma: no cover - NumPy/math package are project deps
        return None

    # --- source landmarks: imported mesh vertex cloud ---------------------
    mesh_vertex_list: List[Tuple[float, float, float]] = []
    for node in _iter_model_nodes(model):
        for vert in list(getattr(node, "vertices", []) or []):
            if vert is None or len(vert) < 3:
                continue
            try:
                mesh_vertex_list.append((float(vert[0]), float(vert[1]), float(vert[2])))
            except Exception:
                continue
    if len(mesh_vertex_list) < 4:
        return None
    mesh_vertices = np.asarray(mesh_vertex_list, dtype=np.float64)

    # --- target landmarks: donor skeleton bone/node positions -------------
    bone_positions: Dict[str, np.ndarray] = {}
    for node in _iter_model_nodes(reference_model):
        pos = _node_fit_position(node)
        if pos is None:
            continue
        name = str(getattr(node, "name", "") or "").strip()
        key = name or f"node_{len(bone_positions)}"
        if key in bone_positions:
            key = f"{key}_{len(bone_positions)}"
        bone_positions[key] = np.asarray(pos, dtype=np.float64)
    # Kabsch needs >=3 non-collinear points; keep a small safety margin.
    if len(bone_positions) < 4:
        return None

    try:
        alignment = align_mesh_to_skeleton(mesh_vertices, bone_positions)
    except Exception:
        return None

    rotation: Tuple[Vec3, Vec3, Vec3] = alignment["rotation_matrix"]
    scale = float(alignment["scale"])
    kabsch_t = alignment["translation"]
    linear_matrix = _scale_matrix(rotation, scale)

    # Source origin = mesh center of mass; target origin is where that center
    # lands after the optimal transform.  This keeps the translation reported
    # by _fit_transform_metadata identical to the offset actually applied
    # (offset == target_origin - linear_matrix @ source_origin).
    source_origin = tuple(
        float(value) for value in alignment["source_landmarks"]["centroid"]
    )
    target_origin = _vec_add(_mat_vec(linear_matrix, source_origin), kabsch_t)
    offset: Vec3 = (float(kabsch_t[0]), float(kabsch_t[1]), float(kabsch_t[2]))

    # Per-landmark residuals for the fit report / validation machinery.
    linear_np = np.asarray(linear_matrix, dtype=np.float64)
    t_np = np.asarray(kabsch_t, dtype=np.float64)
    landmark_keys = ["top", "bottom", "left", "right", "front", "back", "centroid"]
    pair_errors: List[Dict[str, Any]] = []
    squared_total = 0.0
    max_error = 0.0
    worst_role = ""
    for role in landmark_keys:
        source_pt = np.asarray(alignment["source_landmarks"][role], dtype=np.float64)
        target_pt = np.asarray(alignment["target_landmarks"][role], dtype=np.float64)
        mapped = linear_np @ source_pt + t_np
        error = float(np.linalg.norm(mapped - target_pt))
        squared_total += error * error
        if error > max_error:
            max_error = error
            worst_role = role
        pair_errors.append({
            "role": role,
            "source_position": [float(value) for value in source_pt.tolist()],
            "target_position": [float(value) for value in target_pt.tolist()],
            "mapped_position": [float(value) for value in mapped.tolist()],
            "error": error,
        })
    rms_error = math.sqrt(squared_total / float(len(landmark_keys)))

    landmark_alignment_meta = {
        "method": "landmark_kabsch",
        "pair_count": len(landmark_keys),
        "paired_roles": list(landmark_keys),
        "rms_error": rms_error,
        "max_error": max_error,
        "worst_pair_role": worst_role,
        "pair_errors": pair_errors,
        "translation_basis": "kabsch_optimal",
        "error_basis": "mesh_extrema_to_bone_extrema",
        "similarity_transform_accepted": True,
        "rotation_basis": "kabsch_svd",
        "solved_scale": scale,
        "height_scale": 0.0,
        "height_scale_basis": "uniform_kabsch_scale",
        "applied_scale": scale,
        "applied_scale_basis": "uniform_kabsch_scale",
    }

    fit_transform = _fit_transform_metadata(
        policy="landmark_kabsch_basis",
        scale=scale,
        rotation_matrix=rotation,
        source_origin=source_origin,
        target_origin=target_origin,
        landmark_alignment=landmark_alignment_meta,
    )

    return {
        "scale": scale,
        "rotation_matrix": rotation,
        "linear_matrix": linear_matrix,
        "offset": offset,
        "source_origin": source_origin,
        "target_origin": target_origin,
        "fit_transform": fit_transform,
        "source_up_label": "+z",
        "source_forward_label": "+y",
        "target_up_label": "+z",
        "target_forward_label": "+y",
        "source_height": _height_from_bounds(bounds),
        "target_height": _height_from_bounds(reference_bounds),
        "rmsd": float(alignment["rmsd"]),
        "method": "landmark_kabsch",
        "bone_count": len(bone_positions),
    }


def _containment_based_fit_solution(
    model: Any,
    bounds: Optional[Tuple[Vec3, Vec3]],
    reference_model: Optional[Any],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
) -> Optional[Dict[str, Any]]:
    """Fit the imported mesh around donor deformation bones.

    Watertight meshes can use ray-cast volume tests, where every deformation
    bone position from the donor skeleton is enclosed by the mesh surface.
    Open/nonmanifold meshes do not define a reliable inside volume, so those
    assets use an oriented-bounds staging fit and report that surface
    containment was not checked.  Dummy/helper bones (camerahook, head_g, etc.)
    are excluded from containment — see the classification logic below.

    Returns ``None`` if the mesh has too few vertices/faces for containment
    testing, or if the donor model has no deformation bones.
    """
    import numpy as np
    if reference_model is None:
        return None

    # Gather imported mesh vertices and faces
    mesh_vertex_list: List[Tuple[float, float, float]] = []
    mesh_face_list: List[Tuple[int, ...]] = []
    vertex_offset = 0
    for node in _iter_model_nodes(model):
        verts = list(getattr(node, "vertices", []) or [])
        faces = list(getattr(node, "faces", []) or [])
        for vert in verts:
            if vert is None or len(vert) < 3:
                continue
            mesh_vertex_list.append((float(vert[0]), float(vert[1]), float(vert[2])))
        for face in faces:
            if face is None or len(face) < 3:
                continue
            mesh_face_list.append(tuple(int(idx) + vertex_offset for idx in face))
        vertex_offset += len(verts)
    if len(mesh_vertex_list) < 4 or len(mesh_face_list) < 1:
        return None

    mesh_arr = np.asarray(mesh_vertex_list, dtype=np.float64)
    closure = _mesh_face_closure_summary(mesh_face_list)
    reference_name = str(getattr(reference_model, "name", "") or "")
    log.info(
        "CharacterBuilder containment fit: entered reference=%s vertices=%d faces=%d watertight=%s",
        reference_name,
        len(mesh_vertex_list),
        len(mesh_face_list),
        closure["watertight"],
    )

    orientation_seed = _creature_containment_orientation_seed(
        model,
        bounds,
        reference_model,
        reference_bounds,
    )
    if orientation_seed is not None:
        rotation: Tuple[Vec3, Vec3, Vec3] = orientation_seed["rotation_matrix"]
    else:
        rotation = (
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        )
    rotation_np = np.asarray(rotation, dtype=np.float64)
    mesh_vertices = (rotation_np @ mesh_arr.T).T

    deformation_bones, skipped_bones, bone_source = _reference_containment_fit_positions(reference_model)
    if len(deformation_bones) < 1:
        log.info(
            "CharacterBuilder containment fit: no skin bone-map deformation bones found for %s",
            reference_name,
        )
        return None
    if bool(closure["watertight"]):
        containment_bones = list(deformation_bones)
        soft_bones: List[Tuple[str, Vec3]] = []
    else:
        containment_bones, soft_bones = _split_reference_containment_bones(
            deformation_bones,
            reference_bounds,
        )
    if not containment_bones:
        containment_bones = list(deformation_bones)
        soft_bones = []
    bone_positions_list = [bp[1] for bp in containment_bones]
    bone_positions = np.asarray(bone_positions_list, dtype=np.float64)

    if not bool(closure["watertight"]):
        open_mesh_fit = _oriented_bounds_containment_solution(
            mesh_vertices=mesh_arr,
            bounds=bounds,
            reference_bounds=reference_bounds,
            bone_positions=bone_positions_list,
            report_bone_positions=[bp[1] for bp in deformation_bones],
            orientation_seed=orientation_seed,
        )
        if open_mesh_fit is None:
            log.info(
                "CharacterBuilder containment fit: open mesh fallback failed for %s",
                reference_name,
            )
            return None
        fit_core = open_mesh_fit
    else:
        try:
            from src.math.containment_fit import fit_skeleton_inside_mesh
        except ImportError:
            try:
                from math.containment_fit import fit_skeleton_inside_mesh  # type: ignore
            except ImportError:
                return None

        result = fit_skeleton_inside_mesh(
            mesh_vertices=mesh_vertices,
            mesh_faces=mesh_face_list,
            bone_positions=bone_positions,
            max_iterations=30,
            scale_tolerance=0.005,
        )
        scale = float(result["scale"])
        offset = tuple(float(value) for value in result["translation"])
        linear_matrix = _scale_matrix(rotation, scale)
        source_origin = _bounds_ground_center(bounds) if bounds else (0.0, 0.0, 0.0)
        target_origin = _vec_add(_mat_vec(linear_matrix, source_origin), offset)
        fit_transform = _fit_transform_metadata(
            policy="containment_bone_inside_mesh",
            scale=scale,
            rotation_matrix=rotation,
            source_origin=source_origin,
            target_origin=target_origin,
            translation=offset,
        )
        fit_core = {
            "scale": scale,
            "rotation_matrix": rotation,
            "linear_matrix": linear_matrix,
            "offset": offset,
            "source_origin": source_origin,
            "target_origin": target_origin,
            "fit_transform": fit_transform,
            "all_inside": bool(result["all_inside"]),
            "outside_count": int(result["outside_count"]),
            "max_penetration": float(result["max_penetration"]),
            "method": str(result.get("method") or "containment_binary_search"),
            "containment_volume": "ray_cast_surface",
            "surface_containment_checked": True,
            "containment_guarantee": "watertight_surface_volume",
        }

    log.info(
        "CharacterBuilder containment fit: exit reference=%s method=%s scale=%.6f bones=%d outside=%d source=%s",
        reference_name,
        fit_core["method"],
        float(fit_core["scale"]),
        len(containment_bones),
        int(fit_core["outside_count"]),
        bone_source,
    )

    return {
        "ok": True,
        "scale": float(fit_core["scale"]),
        "rotation_matrix": fit_core["rotation_matrix"],
        "linear_matrix": fit_core["linear_matrix"],
        "offset": fit_core["offset"],
        "source_origin": fit_core["source_origin"],
        "target_origin": fit_core["target_origin"],
        "fit_transform": fit_core["fit_transform"],
        "source_height": _height_from_bounds(bounds) if bounds else 0.0,
        "target_height": _height_from_bounds(reference_bounds) if reference_bounds else 0.0,
        "all_inside": bool(fit_core["all_inside"]),
        "outside_count": int(fit_core["outside_count"]),
        "max_penetration": float(fit_core["max_penetration"]),
        "method": str(fit_core["method"]),
        "containment_volume": str(fit_core.get("containment_volume") or ""),
        "surface_containment_checked": bool(fit_core.get("surface_containment_checked", False)),
        "containment_guarantee": str(fit_core.get("containment_guarantee") or ""),
        "mesh_watertight": bool(closure["watertight"]),
        "mesh_boundary_edge_count": int(closure["boundary_edge_count"]),
        "mesh_nonmanifold_edge_count": int(closure["nonmanifold_edge_count"]),
        "bone_position_source": bone_source,
        "bone_count": len(bone_positions_list),
        "deformation_bone_count": len(containment_bones),
        "total_deformation_bone_count": len(deformation_bones),
        "hard_containment_bone_count": len(containment_bones),
        "soft_containment_bone_count": len(soft_bones),
        "total_outside_count": int(fit_core["outside_count"]) + len(soft_bones),
        "dummy_bone_count": len(skipped_bones),
        "deformation_bone_names": [bp[0] for bp in containment_bones],
        "soft_containment_bone_names": [bp[0] for bp in soft_bones],
        "dummy_bone_names": skipped_bones,
        "source_up_label": str(fit_core.get("source_up_label") or (
            orientation_seed.get("source_up_label") if orientation_seed else "unknown"
        )),
        "source_forward_label": str(fit_core.get("source_forward_label") or (
            orientation_seed.get("source_forward_label") if orientation_seed else "unknown"
        )),
        "notes": (
            f"Containment fit used {len(containment_bones)} hard donor skin bone-map positions"
            + (f" and reported {len(soft_bones)} native outlier bones. " if soft_bones else ". ")
            + f"Mesh watertight={bool(closure['watertight'])}; "
            f"surface containment checked={bool(fit_core.get('surface_containment_checked', False))}; "
            f"method={fit_core['method']}."
        ),
    }


def _manual_override_frame(
    model: Any,
    *,
    bounds: Tuple[Vec3, Vec3],
    source_frame: Optional[_HumanoidFitFrame],
    override: AutoFitOverride,
) -> Optional[_HumanoidFitFrame]:
    forward = _axis_vector_from_label(override.source_forward_axis)
    up = _axis_vector_from_label(override.source_up_axis)
    if forward is None or up is None:
        return None
    if abs(_vec_dot(forward, up)) > 1.0e-6:
        return None
    right = _vec_normalize(_vec_cross(forward, up))
    if right is None:
        return None
    forward = _vec_normalize(_vec_cross(up, right))
    if forward is None:
        return None

    ground_basis = str(override.ground_origin_basis or "auto").strip().lower()
    if ground_basis == "auto":
        ground_basis = _ground_origin_basis(source_frame)
    origin = _bounds_ground_center(bounds)
    if ground_basis == "feet" and source_frame is not None:
        origin = source_frame.origin
    elif ground_basis == "hips":
        pelvis = _find_landmark(_named_positions(model), _PELVIS_ALIASES)
        if pelvis is not None:
            origin = pelvis[1]
        elif source_frame is not None:
            origin = source_frame.origin

    height_source = str(override.height_source or "auto").strip().lower()
    if height_source == "auto":
        height_source = "landmarks" if source_frame is not None else "bounds"
    if height_source == "landmarks" and source_frame is not None:
        height = source_frame.height
    else:
        height = _bounds_extent_along_axis(bounds, up)
    if height <= 1.0e-6:
        return None
    landmarks = dict(source_frame.landmarks) if source_frame is not None else {}
    landmarks["manual_source_forward_axis"] = str(override.source_forward_axis or "")
    landmarks["manual_source_up_axis"] = str(override.source_up_axis or "")
    return _HumanoidFitFrame(
        origin=origin,
        right=right,
        forward=forward,
        up=up,
        height=height,
        confidence=0.9 if source_frame is not None else 0.65,
        landmarks=landmarks,
    )


def _used_landmark_labels(
    source_frame: Optional[_HumanoidFitFrame],
    target_frame: Optional[_HumanoidFitFrame],
) -> Tuple[str, ...]:
    labels: List[str] = []
    for prefix, frame in (("source", source_frame), ("target", target_frame)):
        if frame is None:
            continue
        for role, name in sorted((frame.landmarks or {}).items()):
            labels.append(f"{prefix}:{role}={name}")
    return tuple(labels)


def _auto_fit_confidence(
    *,
    policy: str,
    source_frame: Optional[_HumanoidFitFrame],
    target_frame: Optional[_HumanoidFitFrame],
) -> float:
    if policy == "bone_landmark_basis" and source_frame is not None and target_frame is not None:
        return min(float(source_frame.confidence), float(target_frame.confidence))
    if policy == "manual_axis_override" and source_frame is not None:
        if target_frame is not None:
            return min(float(source_frame.confidence), float(target_frame.confidence))
        return float(source_frame.confidence)
    if source_frame is not None:
        return min(0.5, max(0.0, float(source_frame.confidence) * 0.5))
    return 0.35


def _fit_frame_uses_skeleton_landmarks(
    frame: Optional[_HumanoidFitFrame],
) -> bool:
    if frame is None:
        return False
    return any(
        source in {"imported_skeleton", "skeleton_node"}
        for source in (frame.landmark_sources or {}).values()
    )


def _has_fit_landmarks(
    frame: Optional[_HumanoidFitFrame],
    *roles: str,
) -> bool:
    if frame is None:
        return False
    positions = frame.landmark_positions or {}
    return all(role in positions for role in roles)


def _preserve_skeleton_landmark_origin_for_fit(
    source_frame: Optional[_HumanoidFitFrame],
    target_frame: Optional[_HumanoidFitFrame],
) -> bool:
    """Prefer skeleton feet/origin over render bounds for rigged payloads."""

    return (
        _fit_frame_uses_skeleton_landmarks(source_frame)
        and _has_fit_landmarks(source_frame, "left_foot", "right_foot")
        and _has_fit_landmarks(target_frame, "left_foot", "right_foot")
    )


def _target_height_for_landmark_fit(
    *,
    explicit_target_height: Optional[float],
    reference_height: float,
    target_frame: _HumanoidFitFrame,
    source_frame: _HumanoidFitFrame,
) -> Tuple[float, str]:
    if explicit_target_height is not None:
        return float(explicit_target_height), "explicit_target_height"
    if _fit_frame_uses_skeleton_landmarks(source_frame):
        return float(target_frame.height), "paired_skeleton_landmark_height"
    if reference_height > 0.01:
        return float(reference_height), "reference_bounds_height"
    return float(target_frame.height), "bone_landmark_height"


def _scale_for_landmark_fit(
    *,
    height_scale: float,
    height_scale_basis: str,
    landmark_alignment: Optional[Dict[str, Any]],
    min_pair_count: int = 8,
    max_similarity_height_ratio: float = 1.35,
    max_similarity_scale_refinement_ratio: float = 1.02,
    max_rms_error: float = 0.15,
    max_pair_error: float = 0.16,
) -> Tuple[float, str]:
    """Choose the applied landmark-fit scale.

    Height matching is stable for fallback and manual workflows, but a rigged
    FBX gives us stronger evidence: paired source/target skeleton landmarks.
    When that solve is well-formed and close enough to the height-derived
    scale, let it fine-tune the imported payload placement while the selected
    native KOTOR skeleton remains the final DAG authority.
    """

    scale = float(height_scale) if math.isfinite(float(height_scale)) else 1.0
    basis = str(height_scale_basis or "bone_landmark_height")
    if not _landmark_similarity_alignment_is_usable(
        height_scale=scale,
        landmark_alignment=landmark_alignment,
        min_pair_count=min_pair_count,
        max_similarity_height_ratio=max_similarity_height_ratio,
        max_rms_error=max_rms_error,
        max_pair_error=max_pair_error,
    ):
        return scale, basis
    try:
        solved_scale = float(landmark_alignment.get("scale"))
    except Exception:
        return scale, basis
    if scale > 1.0e-8 and math.isfinite(scale):
        refinement_ratio = solved_scale / scale
        max_refine = float(max_similarity_scale_refinement_ratio)
        if (
            math.isfinite(refinement_ratio)
            and max_refine > 1.0
            and (
                refinement_ratio < 1.0 / max_refine
                or refinement_ratio > max_refine
            )
        ):
            return scale, basis
    return solved_scale, "paired_skeleton_similarity_scale"


def _landmark_similarity_alignment_is_usable(
    *,
    height_scale: float,
    landmark_alignment: Optional[Dict[str, Any]],
    min_pair_count: int = 8,
    max_similarity_height_ratio: float = 1.35,
    max_rms_error: float = 0.15,
    max_pair_error: float = 0.16,
) -> bool:
    """Return True when a paired-landmark solve may drive transform choices."""

    if landmark_alignment is None:
        return False
    try:
        solved_scale = float(landmark_alignment.get("scale"))
        pair_count = int(landmark_alignment.get("pair_count") or 0)
        rms_error = float(landmark_alignment.get("rms_error") or 0.0)
        max_error = float(landmark_alignment.get("max_error") or 0.0)
        base_scale = float(height_scale)
    except Exception:
        return False
    if (
        pair_count < int(min_pair_count)
        or not math.isfinite(solved_scale)
        or solved_scale <= 1.0e-8
        or not math.isfinite(rms_error)
        or rms_error > float(max_rms_error)
        or not math.isfinite(max_error)
        or max_error > float(max_pair_error)
    ):
        return False

    if math.isfinite(base_scale) and base_scale > 1.0e-8:
        ratio = solved_scale / base_scale
        if ratio < 1.0 / float(max_similarity_height_ratio) or ratio > float(max_similarity_height_ratio):
            return False
    return True


def _make_auto_fit_report(
    *,
    policy: str,
    scale: float,
    source_frame: Optional[_HumanoidFitFrame],
    target_frame: Optional[_HumanoidFitFrame],
    vertical_axis_index: int,
    warnings: Sequence[str],
    override: Optional[AutoFitOverride] = None,
) -> AutoFitReport:
    manual_used = policy == "manual_axis_override"
    fallback_used = policy not in {"bone_landmark_basis", "manual_axis_override"}
    notes = "; ".join(str(w) for w in warnings if str(w))
    if manual_used:
        manual_note = "Manual source axis/ground override used for this fit."
        notes = f"{manual_note} {notes}".strip()
    elif (
        source_frame is not None
        and any(
            source == "imported_skeleton"
            for source in (source_frame.landmark_sources or {}).values()
        )
    ):
        skeleton_note = "Imported skeleton landmarks drove orientation and scale."
        notes = f"{skeleton_note} {notes}".strip()
    if fallback_used and not notes:
        notes = "Used bounds-based fitting because a complete landmark frame was unavailable."
    source_forward_axis = (
        _axis_label_from_vector(source_frame.forward)
        if source_frame is not None and not fallback_used
        else "unknown"
    )
    source_up_axis = (
        _axis_label_from_vector(source_frame.up)
        if source_frame is not None and not fallback_used
        else _axis_label_from_index(vertical_axis_index)
    )
    target_forward_axis = (
        _axis_label_from_vector(target_frame.forward)
        if target_frame is not None
        else "+y"
    )
    target_up_axis = (
        _axis_label_from_vector(target_frame.up)
        if target_frame is not None
        else "+z"
    )
    height_source = "bounds" if fallback_used else "landmarks"
    ground_basis = _ground_origin_basis(None if fallback_used else source_frame)
    if manual_used and override is not None:
        override_height = str(override.height_source or "auto").strip().lower()
        override_ground = str(override.ground_origin_basis or "auto").strip().lower()
        if override_height not in {"", "auto"}:
            height_source = override_height
        if override_ground not in {"", "auto"}:
            ground_basis = override_ground
    return AutoFitReport(
        source_forward_axis=source_forward_axis,
        source_up_axis=source_up_axis,
        target_forward_axis=target_forward_axis,
        target_up_axis=target_up_axis,
        scale_factor=float(scale),
        height_source=height_source,
        ground_origin_basis=ground_basis,
        used_landmarks=_used_landmark_labels(source_frame, target_frame),
        confidence=_auto_fit_confidence(
            policy=policy,
            source_frame=source_frame,
            target_frame=target_frame,
        ),
        fallback_used=fallback_used,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────
#  Internal loader dispatch
# ──────────────────────────────────────────────────────────────────────

def _ext_of(path: str) -> str:
    return Path(path).suffix.lower()


def _resref_from_path(path: str) -> str:
    return Path(path).stem.lower()


def _load_mdl(path: str, game_version: str) -> Optional[Any]:
    """Load a KOTOR MDL/MDX pair via the kotor_loader bridge."""
    try:
        from src.core.game.kotor_loader import load_model_from_file
    except ImportError:                                     # pragma: no cover
        from core.game.kotor_loader import load_model_from_file  # type: ignore
    mdx = ""
    base, _ = os.path.splitext(path)
    cand = base + ".mdx"
    if os.path.isfile(cand):
        mdx = cand
    return load_model_from_file(path, mdx)


def _load_fbx_mesh_for_character_builder(path: str, game_version: str) -> Optional[Any]:
    """Load an FBX custom character mesh with skeleton-aware guide metadata."""

    md = _import_model_data()
    try:
        from src.converters.blender_fbx_mesh_importer import import_fbx_mesh_with_blender
    except ImportError:                                     # pragma: no cover
        from converters.blender_fbx_mesh_importer import import_fbx_mesh_with_blender  # type: ignore
    gv = (md.GameVersion.K2
          if str(game_version).upper().endswith("2")
          else md.GameVersion.K1)
    model = import_fbx_mesh_with_blender(
        path,
        model_name=_resref_from_path(path),
        game_version=gv,
    )
    setattr(model, "_gr_character_builder_fbx_importer", "blender_mesh")
    return model


def _load_gltf_or_mesh(path: str, game_version: str) -> Optional[Any]:
    """Load an external custom mesh for Character Builder.

    FBX files use the skeleton-aware Blender mesh extractor so Auto-Fit can
    align the imported payload from armature landmarks. Other external mesh
    formats keep using the generic ``gltf_importer.auto_import`` dispatcher.
    """
    md = _import_model_data()
    if _ext_of(path) == ".fbx":
        return _load_fbx_mesh_for_character_builder(path, game_version)
    try:
        from src.core.export.gltf_importer import auto_import
    except ImportError:                                     # pragma: no cover
        from core.export.gltf_importer import auto_import          # type: ignore
    gv = (md.GameVersion.K2
          if str(game_version).upper().endswith("2")
          else md.GameVersion.K1)
    return auto_import(path,
                       model_name=_resref_from_path(path),
                       game_version=gv)


def _iter_model_nodes(model: Any) -> List[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        root = getattr(model, "root_node", None)
        if root is None:
            return []
        out: List[Any] = []
        stack = [root]
        seen: set[int] = set()
        while stack:
            node = stack.pop()
            if node is None:
                continue
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            out.append(node)
            stack.extend(reversed(list(getattr(node, "children", []) or [])))
        return out


def _vertex_bounds(model: Any) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for node in _iter_model_nodes(model):
        for vert in list(getattr(node, "vertices", []) or []):
            if len(vert) < 3:
                continue
            try:
                x, y, z = float(vert[0]), float(vert[1]), float(vert[2])
            except Exception:
                continue
            mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
            maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
            found = True
    if not found:
        return None
    return (tuple(mins), tuple(maxs))  # type: ignore[return-value]


def _model_bone_bounds(model: Any) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for node in _iter_model_nodes(model):
        try:
            if hasattr(node, "bone_world_position"):
                pos = node.bone_world_position()
            else:
                pos = getattr(node, "position", None)
            if pos is None or len(pos) < 3:
                continue
            x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        except Exception:
            continue
        mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
        maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
        found = True
    if not found:
        return None
    return (tuple(mins), tuple(maxs))  # type: ignore[return-value]


def _height_from_bounds(bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]) -> float:
    if bounds is None:
        return 0.0
    bb_min, bb_max = bounds
    try:
        return max(0.0, float(bb_max[2]) - float(bb_min[2]))
    except Exception:
        return 0.0


def reference_model_height(reference_model: Any) -> float:
    """Return the KOTOR-space height of a selected base skeleton/model."""
    mesh_height = _height_from_bounds(_vertex_bounds(reference_model))
    if mesh_height > 0.01:
        return mesh_height
    bone_height = _height_from_bounds(_model_bone_bounds(reference_model))
    if bone_height > 0.01:
        return bone_height
    return 0.0


def _reference_model_fit_bounds(reference_model: Any) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """Return the preferred KOTOR-space frame for fitting external imports.

    Character Builder imports should snap to the selected base model's actual
    authored frame, not merely to a generic origin/height.  Prefer renderable
    mesh bounds because they match what the modder sees; fall back to bone
    bounds for skeleton-only templates.
    """
    if reference_model is None:
        return None
    mesh_bounds = _vertex_bounds(reference_model)
    if mesh_bounds is not None and _height_from_bounds(mesh_bounds) > 0.01:
        return mesh_bounds
    bone_bounds = _model_bone_bounds(reference_model)
    if bone_bounds is not None and _height_from_bounds(bone_bounds) > 0.01:
        return bone_bounds
    return None


# Landmark aliases are ordered by fit quality.  Keep native KOTOR deform nodes
# and DCC humanoid landmarks ahead of generic roots/hooks so a model containing
# both ``pelvis_g`` and ``rootdummy`` does not pick the wrong fit origin.
_PELVIS_ALIASES = (
    "pelvis_g", "pelvisg", "pelvis",
    "hips", "hip", "mixamorighips", "bip001pelvis",
    "rootdummy", "auroraroot", "root",
)
_HEAD_ALIASES = (
    "head_g", "headg", "head",
    "mixamorighead", "bip001head",
    "hturn_g", "hturng", "neck_g", "neckg", "neck", "headhook",
)
_LEFT_SIDE_ALIASES = (
    ("lcollar_g", "lcollarg", "lcollar_dum", "lcollardum", "leftshoulder", "lshoulder", "lclavicle", "leftarm", "larm"),
    ("lhand", "lhand_g", "lhandg", "lefthand", "lwrist", "handl", "mixamoriglefthand"),
    ("lthigh_g", "lthighg", "lthigh", "leftupleg", "leftleg", "thighl"),
    ("lfoot_g", "lfootg", "lfoot", "lfoot_t_g", "lfoottg", "leftfoot", "lefttoe", "toel"),
)
_RIGHT_SIDE_ALIASES = (
    ("rcollar_g", "rcollarg", "rcollar_dum", "rcollardum", "rightshoulder", "rshoulder", "rclavicle", "rightarm", "rarm"),
    ("rhand", "rhand_g", "rhandg", "righthand", "rwrist", "handr", "mixamorigrighthand"),
    ("rthigh_g", "rthighg", "rthigh", "rightupleg", "rightleg", "thighr"),
    ("rfoot_g", "rfootg", "rfoot", "rfoot_t_g", "rfoottg", "rightfoot", "righttoe", "toer"),
)
_LEFT_FOOT_ALIASES = ("lfoot_g", "lfootg", "lfoot", "leftfoot")
_RIGHT_FOOT_ALIASES = ("rfoot_g", "rfootg", "rfoot", "rightfoot")
_LEFT_HAND_ALIASES = ("lhand", "lhand_g", "lhandg", "lefthand", "lwrist", "handl")
_RIGHT_HAND_ALIASES = ("rhand", "rhand_g", "rhandg", "righthand", "rwrist", "handr")
_LEFT_TOE_ALIASES = (
    "lfoot_t_g", "lfoottg", "lfoot_t", "lfoott",
    "lefttoebase", "lefttoe", "ltoe", "toel", "ball_l", "balll",
    "lfoot_end", "lfootend", "leftfootend",
)
_RIGHT_TOE_ALIASES = (
    "rfoot_t_g", "rfoottg", "rfoot_t", "rfoott",
    "righttoebase", "righttoe", "rtoe", "toer", "ball_r", "ballr",
    "rfoot_end", "rfootend", "rightfootend",
)


def _clean_landmark_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    if "|" in raw:
        raw = raw.rsplit("|", 1)[-1]
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    for prefix in ("mixamorig", "mixamo", "bip001"):
        if raw.startswith(prefix) and len(raw) > len(prefix):
            raw = raw[len(prefix):]
    return "".join(ch for ch in raw if ch.isalnum())


def _node_fit_position(node: Any) -> Optional[Vec3]:
    for attr in ("external_world_position",):
        value = getattr(node, attr, None)
        if value is not None and len(value) >= 3:
            try:
                return (float(value[0]), float(value[1]), float(value[2]))
            except Exception:
                pass
    try:
        value = node.bone_world_position()
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        pass
    try:
        value = node.world_transform()[0]
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        pass
    value = getattr(node, "position", None)
    if value is not None and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return None
    return None


def _node_fit_landmark_source(node: Any) -> str:
    """Classify a node's usefulness for Character Builder Auto-Fit evidence.

    Imported FBX/GLTF skeleton joints usually arrive as header nodes with an
    ``external_world_position`` and no renderable vertices.  Mesh children can
    carry similar names, but they should not override skeleton joints when the
    user is fitting a custom mesh to a native KOTOR base.
    """

    try:
        flags = int(getattr(node, "flags", 0) or 0)
    except Exception:
        flags = 0
    vertices = list(getattr(node, "vertices", []) or [])
    has_vertices = bool(vertices)
    has_external_world = getattr(node, "external_world_position", None) is not None
    has_mesh_flag = False
    has_skin_flag = False
    try:
        md = _import_model_data()
        has_mesh_flag = bool(flags & int(md.NodeFlags.MESH))
        has_skin_flag = bool(flags & int(md.NodeFlags.SKIN))
    except Exception:
        has_mesh_flag = bool(flags & 0x20)
        has_skin_flag = bool(flags & 0x40)

    if has_vertices or has_skin_flag:
        return "mesh_payload"
    if has_external_world and not has_mesh_flag:
        return "imported_skeleton"
    if has_external_world and has_mesh_flag:
        return "imported_helper"
    if has_mesh_flag:
        return "kotor_deform_helper"
    return "skeleton_node"


def _landmark_candidate_score(
    node: Any,
    *,
    source: str,
    prefer_skeleton_landmarks: bool,
    order_index: int,
) -> Tuple[int, int]:
    if not prefer_skeleton_landmarks:
        return (0, -order_index)
    if source == "imported_skeleton":
        priority = 100
    elif source == "skeleton_node":
        priority = 90
    elif source == "imported_helper":
        priority = 80
    elif source == "kotor_deform_helper":
        priority = 70
    elif source == "mesh_payload":
        priority = 20
    else:
        priority = 10
    return (priority, -order_index)


def _named_positions(
    model: Any,
    *,
    prefer_skeleton_landmarks: bool = False,
) -> Dict[str, Tuple[str, Vec3, str]]:
    result: Dict[str, Tuple[str, Vec3, str]] = {}
    scores: Dict[str, Tuple[int, int]] = {}
    if model is None:
        return result
    for order_index, node in enumerate(_iter_model_nodes(model)):
        clean = _clean_landmark_name(getattr(node, "name", ""))
        if not clean:
            continue
        pos = _node_fit_position(node)
        if pos is not None:
            source = _node_fit_landmark_source(node)
            score = _landmark_candidate_score(
                node,
                source=source,
                prefer_skeleton_landmarks=prefer_skeleton_landmarks,
                order_index=order_index,
            )
            if clean in result and score <= scores.get(clean, (-1, -1)):
                continue
            result[clean] = (str(getattr(node, "name", "") or ""), pos, source)
            scores[clean] = score
    return result


def _find_landmark(
    positions: Dict[str, Tuple[str, Vec3, str]],
    aliases: Sequence[str] | set[str],
) -> Tuple[str, Vec3, str] | None:
    clean_aliases = _ordered_clean_aliases(aliases)
    for alias in clean_aliases:
        hit = positions.get(alias)
        if hit is not None:
            return hit
    for alias in clean_aliases:
        for key, hit in positions.items():
            if alias and key.endswith(alias):
                return hit
    return None


def _ordered_clean_aliases(aliases: Sequence[str] | set[str]) -> Tuple[str, ...]:
    if isinstance(aliases, set):
        raw_aliases = sorted(aliases)
    else:
        raw_aliases = list(aliases)
    cleaned: List[str] = []
    seen: set[str] = set()
    for alias in raw_aliases:
        clean = _clean_landmark_name(alias)
        if not clean or clean in seen:
            continue
        cleaned.append(clean)
        seen.add(clean)
    return tuple(cleaned)


def _find_side_pair(
    positions: Dict[str, Tuple[str, Vec3, str]],
) -> Tuple[Tuple[str, Vec3, str], Tuple[str, Vec3, str], str] | None:
    for index, (left_aliases, right_aliases) in enumerate(zip(_LEFT_SIDE_ALIASES, _RIGHT_SIDE_ALIASES)):
        left = _find_landmark(positions, left_aliases)
        right = _find_landmark(positions, right_aliases)
        if left is not None and right is not None:
            labels = ("shoulder", "hand", "hip", "foot")
            return left, right, labels[index]
    return None


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_scale(v: Vec3, scale: float) -> Vec3:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _vec_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_len(v: Vec3) -> float:
    return math.sqrt(max(0.0, _vec_dot(v, v)))


def _vec_normalize(v: Vec3) -> Optional[Vec3]:
    length = _vec_len(v)
    if length <= 1.0e-8:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)


def _average_points(points: Sequence[Vec3]) -> Optional[Vec3]:
    if not points:
        return None
    inv = 1.0 / float(len(points))
    return (
        sum(p[0] for p in points) * inv,
        sum(p[1] for p in points) * inv,
        sum(p[2] for p in points) * inv,
    )


def _bounds_ground_center(bounds: Optional[Tuple[Vec3, Vec3]]) -> Vec3:
    if bounds is None:
        return (0.0, 0.0, 0.0)
    bb_min, bb_max = bounds
    return (
        (float(bb_min[0]) + float(bb_max[0])) * 0.5,
        (float(bb_min[1]) + float(bb_max[1])) * 0.5,
        float(bb_min[2]),
    )


def _infer_humanoid_fit_frame(
    model: Any,
    *,
    bounds: Optional[Tuple[Vec3, Vec3]] = None,
    prefer_skeleton_landmarks: bool = False,
) -> Optional[_HumanoidFitFrame]:
    positions = _named_positions(
        model,
        prefer_skeleton_landmarks=prefer_skeleton_landmarks,
    )
    side_pair = _find_side_pair(positions)
    pelvis = _find_landmark(positions, _PELVIS_ALIASES)
    head = _find_landmark(positions, _HEAD_ALIASES)
    left_foot = _find_landmark(positions, _LEFT_FOOT_ALIASES)
    right_foot = _find_landmark(positions, _RIGHT_FOOT_ALIASES)
    left_hand = _find_landmark(positions, _LEFT_HAND_ALIASES)
    right_hand = _find_landmark(positions, _RIGHT_HAND_ALIASES)
    left_toe = _find_landmark(positions, _LEFT_TOE_ALIASES)
    right_toe = _find_landmark(positions, _RIGHT_TOE_ALIASES)

    if side_pair is None or head is None:
        return None

    left, right, side_kind = side_pair
    lower_points = [p for hit in (left_foot, right_foot) if hit is not None for p in (hit[1],)]
    foot_center = _average_points(lower_points)
    pelvis_pos = pelvis[1] if pelvis is not None else None
    lower_anchor = foot_center or pelvis_pos or _bounds_ground_center(bounds)
    upper_anchor = head[1]

    up_raw = _vec_sub(upper_anchor, pelvis_pos or lower_anchor)
    up = _vec_normalize(up_raw)
    if up is None:
        up = _vec_normalize(_vec_sub(upper_anchor, lower_anchor))
    if up is None:
        return None

    right_raw = _vec_sub(right[1], left[1])
    right_projected = _vec_sub(right_raw, _vec_scale(up, _vec_dot(right_raw, up)))
    right_vec = _vec_normalize(right_projected)
    if right_vec is None:
        return None

    # KOTOR native humanoids face +Y: forward = up x right for X-right/Z-up.
    forward = _vec_normalize(_vec_cross(up, right_vec))
    if forward is None:
        return None
    right_vec = _vec_normalize(_vec_cross(forward, up))
    if right_vec is None:
        return None
    forward, right_vec = _front_axis_from_toes(
        provisional_forward=forward,
        provisional_right=right_vec,
        up=up,
        left_foot=left_foot,
        right_foot=right_foot,
        left_toe=left_toe,
        right_toe=right_toe,
    )

    height = abs(_vec_dot(_vec_sub(upper_anchor, lower_anchor), up))
    if height <= 1.0e-5 and bounds is not None:
        bb_min, bb_max = bounds
        height = max(0.0, float(bb_max[2]) - float(bb_min[2]))
    if height <= 1.0e-5:
        return None

    origin = lower_anchor
    landmarks = {
        "left": left[0],
        "right": right[0],
        "side_pair": side_kind,
        "head": head[0],
    }
    if pelvis is not None:
        landmarks["pelvis"] = pelvis[0]
    if left_foot is not None:
        landmarks["left_foot"] = left_foot[0]
    if right_foot is not None:
        landmarks["right_foot"] = right_foot[0]
    if left_hand is not None:
        landmarks["left_hand"] = left_hand[0]
    if right_hand is not None:
        landmarks["right_hand"] = right_hand[0]
    if left_toe is not None:
        landmarks["left_toe"] = left_toe[0]
    if right_toe is not None:
        landmarks["right_toe"] = right_toe[0]
    landmark_sources = {
        "left": left[2],
        "right": right[2],
        "head": head[2],
    }
    if pelvis is not None:
        landmark_sources["pelvis"] = pelvis[2]
    if left_foot is not None:
        landmark_sources["left_foot"] = left_foot[2]
    if right_foot is not None:
        landmark_sources["right_foot"] = right_foot[2]
    if left_hand is not None:
        landmark_sources["left_hand"] = left_hand[2]
    if right_hand is not None:
        landmark_sources["right_hand"] = right_hand[2]
    if left_toe is not None:
        landmark_sources["left_toe"] = left_toe[2]
    if right_toe is not None:
        landmark_sources["right_toe"] = right_toe[2]
    landmark_positions = {
        "left": left[1],
        "right": right[1],
        "head": head[1],
    }
    if pelvis is not None:
        landmark_positions["pelvis"] = pelvis[1]
    if left_foot is not None:
        landmark_positions["left_foot"] = left_foot[1]
    if right_foot is not None:
        landmark_positions["right_foot"] = right_foot[1]
    if left_hand is not None:
        landmark_positions["left_hand"] = left_hand[1]
    if right_hand is not None:
        landmark_positions["right_hand"] = right_hand[1]
    if left_toe is not None:
        landmark_positions["left_toe"] = left_toe[1]
    if right_toe is not None:
        landmark_positions["right_toe"] = right_toe[1]
    confidence = 0.65
    confidence += 0.1 if pelvis is not None else 0.0
    confidence += 0.1 if foot_center is not None else 0.0
    confidence += 0.05 if left_toe is not None and right_toe is not None else 0.0
    confidence += 0.1 if side_kind == "shoulder" else 0.0
    if prefer_skeleton_landmarks:
        core_sources = {
            landmark_sources.get(role, "")
            for role in (
                "left", "right", "head", "pelvis",
                "left_foot", "right_foot", "left_hand", "right_hand",
                "left_toe", "right_toe",
            )
        }
        if any(source in {"imported_skeleton", "skeleton_node"} for source in core_sources):
            confidence += 0.05
        if core_sources and all(source == "mesh_payload" for source in core_sources):
            confidence -= 0.15

    return _HumanoidFitFrame(
        origin=origin,
        right=right_vec,
        forward=forward,
        up=up,
        height=height,
        confidence=min(0.95, confidence),
        landmarks=landmarks,
        landmark_sources=landmark_sources,
        landmark_positions=landmark_positions,
    )


def inspect_external_model_fit(
    model: Any,
    *,
    game_version: str = "K1",
    target_height: Optional[float] = None,
    reference_model: Optional[Any] = None,
    reference_label: str = "",
    fit_override: Optional[Any] = None,
    expected_mode: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return the deterministic auto-fit facts for an external character mesh.

    This function does not mutate *model*.  It exposes the same evidence used by
    :func:`normalize_external_model_for_kotor`: source bounds, selected KOTOR
    reference bounds, detected humanoid landmark frames, fallback axis choice,
    confidence, scale basis, and actionable warnings.  The Character Builder UI
    can display this report so a modder can understand why an import snapped or
    rotated the way it did before committing the native KOTOR skeleton build.
    """
    bounds = _vertex_bounds(model)
    imported_armature = _imported_armature_fit_evidence(model)
    if bounds is None:
        auto_fit_report = AutoFitReport(
            source_forward_axis="unknown",
            source_up_axis="unknown",
            target_forward_axis="+y",
            target_up_axis="+z",
            scale_factor=1.0,
            height_source="bounds",
            ground_origin_basis="bounds_bottom",
            confidence=0.0,
            fallback_used=True,
            notes="Import contains no renderable vertices to fit.",
        ).to_dict()
        return {
            "ok": False,
            "code": "no_vertices",
            "message": "No vertex bounds were found on the imported mesh.",
            "fit_policy": "none",
            "source_forward_axis": auto_fit_report["source_forward_axis"],
            "source_up_axis": auto_fit_report["source_up_axis"],
            "target_forward_axis": auto_fit_report["target_forward_axis"],
            "target_up_axis": auto_fit_report["target_up_axis"],
            "scale_factor": auto_fit_report["scale_factor"],
            "height_source": auto_fit_report["height_source"],
            "ground_origin_basis": auto_fit_report["ground_origin_basis"],
            "used_landmarks": auto_fit_report["used_landmarks"],
            "confidence": auto_fit_report["confidence"],
            "fallback_used": auto_fit_report["fallback_used"],
            "notes": auto_fit_report["notes"],
            "auto_fit_report": auto_fit_report,
            "source_imported_armature": imported_armature,
            "fit_transform": None,
            "visual_overlay": {
                "coordinate_space": "source_pre_fit_and_kotor_reference",
                "source": {
                    "bounds": None,
                    "origin": None,
                    "axes": {},
                    "landmarks": [],
                },
                "target": None,
            },
            "warnings": ["Import contains no renderable vertices to fit."],
        }

    reference_bounds = _reference_model_fit_bounds(reference_model)
    override = _coerce_auto_fit_override(fit_override)
    creature_fit = (
        _creature_bounds_fit_solution(bounds, reference_bounds)
        if _is_creature_mode_value(expected_mode) and not override.is_active() else None
    )
    if creature_fit is not None:
        auto_fit = AutoFitReport(
            source_forward_axis=str(creature_fit["source_forward_label"]),
            source_up_axis=str(creature_fit["source_up_label"]),
            target_forward_axis=str(creature_fit["target_forward_label"]),
            target_up_axis=str(creature_fit["target_up_label"]),
            scale_factor=float(creature_fit["scale"]),
            height_source="creature_bounds_axes",
            ground_origin_basis="selected_reference_bounds_bottom",
            used_landmarks=[
                "source:creature_bounds",
                "target:selected_creature_bounds",
            ],
            confidence=0.78,
            fallback_used=False,
            notes=(
                "Creature bounds drove orientation and scale from the selected "
                "KOTOR base skeleton."
            ),
        )
        auto_fit_report = auto_fit.to_dict()

        def transform_point(point: Vec3) -> Vec3:
            return _vec_add(
                _mat_vec(creature_fit["linear_matrix"], point),
                creature_fit["offset"],
            )

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(creature_fit["rotation_matrix"], direction)
            return _vec_normalize(rotated) or rotated

        def transform_node_position(point: Vec3) -> Vec3:
            return _mat_vec(creature_fit["linear_matrix"], point)

        return {
            "ok": True,
            "code": "fit_inspected",
            "message": "External creature mesh fit inspected using selected base bounds.",
            "fit_policy": "creature_bounds_basis",
            "scale_basis": "creature_bounds_median_extent",
            "scale": float(creature_fit["scale"]),
            "source_height": float(creature_fit["source_height"]),
            "target_height": float(creature_fit["target_height"]),
            "vertical_axis": str(creature_fit["source_up_label"]).lstrip("+"),
            "reference": str(reference_label or getattr(reference_model, "name", "") or ""),
            "source_bounds": _bounds_as_lists(bounds),
            "reference_bounds": _bounds_as_lists(reference_bounds),
            "source_frame": {
                "origin": _vec_as_list(creature_fit["source_origin"]),
                "landmarks": {"creature_bounds": "source_render_bounds"},
                "landmark_sources": {"creature_bounds": "render_bounds"},
            },
            "target_frame": {
                "origin": _vec_as_list(_bounds_ground_center(reference_bounds)),
                "landmarks": {"creature_bounds": "selected_reference_bounds"},
                "landmark_sources": {"creature_bounds": "render_bounds"},
            },
            "source_forward_axis": auto_fit.source_forward_axis,
            "source_up_axis": auto_fit.source_up_axis,
            "target_forward_axis": auto_fit.target_forward_axis,
            "target_up_axis": auto_fit.target_up_axis,
            "scale_factor": auto_fit.scale_factor,
            "height_source": auto_fit.height_source,
            "ground_origin_basis": auto_fit.ground_origin_basis,
            "used_landmarks": auto_fit_report["used_landmarks"],
            "confidence": auto_fit.confidence,
            "fallback_used": auto_fit.fallback_used,
            "notes": auto_fit.notes,
            "auto_fit_report": auto_fit_report,
            "source_imported_armature": imported_armature,
            "fit_transform": creature_fit["fit_transform"],
            "visual_overlay": {
                "coordinate_space": "source_pre_fit_and_kotor_reference",
                "source": _fit_frame_visual_overlay(model, None, bounds),
                "target": _fit_frame_visual_overlay(reference_model, None, reference_bounds),
            },
            "fitted_visual_overlay": {
                "coordinate_space": "kotor_world_after_fit",
                "source": _fit_frame_visual_overlay(
                    model,
                    None,
                    bounds,
                    transform_point=transform_point,
                    transform_direction=transform_direction,
                    axis_length_scale=float(creature_fit["scale"]),
                ),
                "target": _fit_frame_visual_overlay(reference_model, None, reference_bounds),
            },
            "warnings": [],
            "kotor_contract": {
                "native_skeleton_is_authority": True,
                "imported_mesh_role": "payload_guest",
                "final_dag_source": "selected_kotor_base",
            },
        }
    source_frame = _infer_humanoid_fit_frame(
        model,
        bounds=bounds,
        prefer_skeleton_landmarks=True,
    )
    target_frame = (
        _infer_humanoid_fit_frame(reference_model, bounds=reference_bounds)
        if reference_model is not None else None
    )
    manual_source_frame = (
        _manual_override_frame(
            model,
            bounds=bounds,
            source_frame=source_frame,
            override=override,
        )
        if override.is_active() else None
    )
    manual_target_frame = target_frame or _default_target_fit_frame(reference_bounds)
    reference_height = _height_from_bounds(reference_bounds)

    bb_min, bb_max = bounds
    extents = tuple(max(0.0, bb_max[i] - bb_min[i]) for i in range(3))
    vertical_axis_index = max(range(3), key=lambda i: extents[i])
    fallback_source_height = max(extents[vertical_axis_index], 1.0e-6)
    fallback_target_height = float(
        target_height
        or reference_height
        or _kotor_template_humanoid_height(game_version)
    )

    warnings: List[str] = []
    if source_frame is None:
        warnings.append(
            "Could not detect a complete humanoid landmark frame on the imported mesh; "
            "falling back to bounds-based axis fitting."
        )
    elif source_frame.confidence < 0.75:
        warnings.append(
            f"Imported mesh landmark confidence is low ({source_frame.confidence:.2f})."
        )
    if source_frame is not None:
        source_toe_forward = _fit_frame_toe_forward(source_frame)
        if source_toe_forward is not None:
            source_toe_alignment = _vec_dot(source_frame.forward, source_toe_forward)
            if source_toe_alignment < 0.5:
                warnings.append(
                    "Imported skeleton toe direction disagrees with the inferred "
                    "facing axis; review the source mesh orientation before building "
                    "the native KOTOR skeleton."
                )
    if reference_model is not None and target_frame is None:
        warnings.append(
            "Could not detect a complete humanoid landmark frame on the selected KOTOR base; "
            "falling back to its bounds."
        )
    elif target_frame is not None and target_frame.confidence < 0.75:
        warnings.append(
            f"KOTOR base landmark confidence is low ({target_frame.confidence:.2f})."
        )
    if target_frame is not None:
        target_toe_forward = _fit_frame_toe_forward(target_frame)
        if target_toe_forward is not None:
            target_toe_alignment = _vec_dot(target_frame.forward, target_toe_forward)
            if target_toe_alignment < 0.5:
                warnings.append(
                    "Selected KOTOR base toe direction disagrees with the inferred "
                    "facing axis; verify the base skeleton before using it as the "
                    "native rig authority."
                )

    if manual_source_frame is not None and manual_target_frame is not None:
        target = float(target_height or reference_height or manual_target_frame.height)
        scale = target / manual_source_frame.height if manual_source_frame.height > 1.0e-6 else 1.0
        policy = "manual_axis_override"
        source_height = manual_source_frame.height
        scale_basis = "manual_override_height"
        vertical_axis = "manual_override"
        report_source_frame = manual_source_frame
        report_target_frame = manual_target_frame
        report_landmark_alignment = None
    elif source_frame is not None and target_frame is not None:
        target, scale_basis = _target_height_for_landmark_fit(
            explicit_target_height=target_height,
            reference_height=reference_height,
            target_frame=target_frame,
            source_frame=source_frame,
        )
        similarity_alignment = _landmark_similarity_alignment(source_frame, target_frame)
        height_scale = target / source_frame.height if source_frame.height > 1.0e-6 else 1.0
        height_scale_basis = scale_basis
        use_similarity_transform = _landmark_similarity_alignment_is_usable(
            height_scale=height_scale,
            landmark_alignment=similarity_alignment,
        )
        scale, scale_basis = _scale_for_landmark_fit(
            height_scale=height_scale,
            height_scale_basis=height_scale_basis,
            landmark_alignment=similarity_alignment,
        )
        if similarity_alignment is not None:
            similarity_alignment = dict(similarity_alignment)
            similarity_alignment["solved_scale"] = float(similarity_alignment["scale"])
            similarity_alignment["height_scale"] = float(height_scale)
            similarity_alignment["height_scale_basis"] = height_scale_basis
            similarity_alignment["applied_scale"] = float(scale)
            similarity_alignment["applied_scale_basis"] = scale_basis
            similarity_alignment["similarity_transform_accepted"] = bool(
                use_similarity_transform
            )
            similarity_alignment["rotation_basis"] = (
                "paired_skeleton_similarity"
                if use_similarity_transform else
                "bone_landmark_basis"
            )
        policy = "bone_landmark_basis"
        source_height = source_frame.height
        vertical_axis = "bone_landmarks"
        report_source_frame = source_frame
        report_target_frame = target_frame
        report_landmark_alignment = similarity_alignment
    else:
        target = fallback_target_height
        scale = fallback_target_height / fallback_source_height
        policy = "selected_reference_bounds" if reference_bounds is not None else "origin_height"
        source_height = fallback_source_height
        scale_basis = "bounds_height"
        vertical_axis = ("x", "y", "z")[vertical_axis_index]
        report_source_frame = source_frame
        report_target_frame = target_frame
        report_landmark_alignment = None

    auto_fit = _make_auto_fit_report(
        policy=policy,
        scale=scale,
        source_frame=report_source_frame,
        target_frame=report_target_frame,
        vertical_axis_index=vertical_axis_index,
        warnings=warnings,
        override=override,
    )
    auto_fit_report = auto_fit.to_dict()
    fit_transform: Dict[str, Any] | None = None
    if report_source_frame is not None and report_target_frame is not None:
        use_similarity_transform = bool(
            report_landmark_alignment
            and report_landmark_alignment.get("similarity_transform_accepted")
        )
        rotation = (
            report_landmark_alignment["rotation_matrix"]
            if report_landmark_alignment is not None and use_similarity_transform
            else _basis_rotation(report_source_frame, report_target_frame)
        )
        preserve_skeleton_origin = _preserve_skeleton_landmark_origin_for_fit(
            report_source_frame,
            report_target_frame,
        )
        translation_basis = (
            "skeleton_landmark_native_fit_origin"
            if preserve_skeleton_origin else
            "ground_snapped_native_fit_origin"
        )
        target_origin = _ground_snapped_target_origin(
            bounds=bounds,
            rotation_matrix=rotation,
            scale=scale,
            source_origin=report_source_frame.origin,
            target_origin=report_target_frame.origin,
            target_frame=report_target_frame,
            reference_bounds=reference_bounds,
            preserve_target_origin=preserve_skeleton_origin,
        )
        if report_landmark_alignment is not None:
            report_landmark_alignment = _landmark_alignment_for_applied_transform(
                report_landmark_alignment,
                report_source_frame,
                report_target_frame,
                rotation_matrix=rotation,
                applied_scale=scale,
                source_origin=report_source_frame.origin,
                target_origin=target_origin,
                applied_scale_basis=scale_basis,
                translation_basis=translation_basis,
            )
        fit_transform = _fit_transform_metadata(
            policy=policy,
            scale=scale,
            rotation_matrix=rotation,
            source_origin=report_source_frame.origin,
            target_origin=target_origin,
            landmark_alignment=report_landmark_alignment,
        )
    else:
        mapped_min = _axis_map_to_kotor_z(bb_min, vertical_axis_index)
        mapped_max = _axis_map_to_kotor_z(bb_max, vertical_axis_index)
        norm_min = tuple(min(mapped_min[i], mapped_max[i]) for i in range(3))
        norm_max = tuple(max(mapped_min[i], mapped_max[i]) for i in range(3))
        center_x = (norm_min[0] + norm_max[0]) * 0.5
        center_y = (norm_min[1] + norm_max[1]) * 0.5
        if reference_bounds is not None:
            ref_min, ref_max = reference_bounds
            target_center_x = (float(ref_min[0]) + float(ref_max[0])) * 0.5
            target_center_y = (float(ref_min[1]) + float(ref_max[1])) * 0.5
            target_ground_z = float(ref_min[2])
        else:
            target_center_x = 0.0
            target_center_y = 0.0
            target_ground_z = 0.0
        offset = (
            target_center_x - center_x * scale,
            target_center_y - center_y * scale,
            target_ground_z - norm_min[2] * scale,
        )
        source_origin = _bounds_ground_center(bounds)
        target_origin = _transform_point_for_kotor(
            source_origin,
            vertical_axis=vertical_axis_index,
            scale=scale,
            offset=offset,
        )
        fit_transform = _fit_transform_metadata(
            policy=policy,
            scale=scale,
            rotation_matrix=_axis_map_matrix_to_kotor_z(vertical_axis_index),
            source_origin=source_origin,
            target_origin=target_origin,
        )

    return {
        "ok": True,
        "code": "fit_inspected",
        "message": f"External mesh fit inspected using {policy}.",
        "fit_policy": policy,
        "scale_basis": scale_basis,
        "scale": float(scale),
        "source_height": float(source_height),
        "target_height": float(target),
        "vertical_axis": vertical_axis,
        "reference": str(reference_label or getattr(reference_model, "name", "") or ""),
        "source_bounds": _bounds_as_lists(bounds),
        "reference_bounds": _bounds_as_lists(reference_bounds),
        "source_frame": _fit_frame_as_metadata(report_source_frame),
        "target_frame": _fit_frame_as_metadata(report_target_frame),
        "source_forward_axis": auto_fit.source_forward_axis,
        "source_up_axis": auto_fit.source_up_axis,
        "target_forward_axis": auto_fit.target_forward_axis,
        "target_up_axis": auto_fit.target_up_axis,
        "scale_factor": auto_fit.scale_factor,
        "height_source": auto_fit.height_source,
        "ground_origin_basis": auto_fit.ground_origin_basis,
        "used_landmarks": auto_fit_report["used_landmarks"],
        "confidence": auto_fit.confidence,
        "fallback_used": auto_fit.fallback_used,
        "notes": auto_fit.notes,
        "auto_fit_report": auto_fit_report,
        "source_imported_armature": imported_armature,
        "fit_transform": fit_transform,
        "visual_overlay": {
            "coordinate_space": "source_pre_fit_and_kotor_reference",
            "source": _fit_frame_visual_overlay(
                model,
                report_source_frame,
                bounds,
                prefer_skeleton_landmarks=True,
            ),
            "target": _fit_frame_visual_overlay(
                reference_model,
                report_target_frame,
                reference_bounds,
            ) if reference_model is not None else None,
        },
        "warnings": warnings,
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
    }


def _basis_matrix(frame: _HumanoidFitFrame) -> Tuple[Vec3, Vec3, Vec3]:
    return (frame.right, frame.forward, frame.up)


def _basis_rotation(
    source: _HumanoidFitFrame,
    target: _HumanoidFitFrame,
) -> Tuple[Vec3, Vec3, Vec3]:
    s = _basis_matrix(source)
    t = _basis_matrix(target)
    rows: list[Vec3] = []
    for row in range(3):
        rows.append((
            t[0][row] * s[0][0] + t[1][row] * s[1][0] + t[2][row] * s[2][0],
            t[0][row] * s[0][1] + t[1][row] * s[1][1] + t[2][row] * s[2][1],
            t[0][row] * s[0][2] + t[1][row] * s[1][2] + t[2][row] * s[2][2],
        ))
    return tuple(rows)  # type: ignore[return-value]


_SIMILARITY_LANDMARK_ROLES = (
    "pelvis",
    "head",
    "left",
    "right",
    "left_foot",
    "right_foot",
    "left_toe",
    "right_toe",
)


def _paired_landmark_positions(
    source: _HumanoidFitFrame,
    target: _HumanoidFitFrame,
) -> List[Tuple[str, Vec3, Vec3]]:
    pairs: List[Tuple[str, Vec3, Vec3]] = []
    source_positions = source.landmark_positions or {}
    target_positions = target.landmark_positions or {}
    for role in _SIMILARITY_LANDMARK_ROLES:
        source_point = source_positions.get(role)
        target_point = target_positions.get(role)
        if source_point is None or target_point is None:
            continue
        try:
            pairs.append((
                role,
                (
                    float(source_point[0]),
                    float(source_point[1]),
                    float(source_point[2]),
                ),
                (
                    float(target_point[0]),
                    float(target_point[1]),
                    float(target_point[2]),
                ),
            ))
        except Exception:
            continue
    return pairs


def _landmark_similarity_alignment(
    source: Optional[_HumanoidFitFrame],
    target: Optional[_HumanoidFitFrame],
) -> Optional[Dict[str, Any]]:
    """Solve a uniform source-to-target fit from paired skeleton landmarks.

    The native KOTOR target skeleton remains authoritative.  This helper only
    derives a better imported-payload placement transform than a single
    height/axis frame can provide.
    """

    if source is None or target is None:
        return None
    pairs = _paired_landmark_positions(source, target)
    if len(pairs) < 3:
        return None
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy is a project dependency.
        return None

    source_points = np.asarray([pair[1] for pair in pairs], dtype=np.float64)
    target_points = np.asarray([pair[2] for pair in pairs], dtype=np.float64)
    if source_points.shape[0] < 3 or target_points.shape[0] < 3:
        return None
    source_center = source_points.mean(axis=0)
    target_center = target_points.mean(axis=0)
    source_centered = source_points - source_center
    target_centered = target_points - target_center
    source_variance = float(np.sum(source_centered * source_centered))
    if source_variance <= 1.0e-10:
        return None

    covariance = source_centered.T @ target_centered
    try:
        u, singular_values, vh = np.linalg.svd(covariance)
    except Exception:
        return None
    correction = np.eye(3, dtype=np.float64)
    if float(np.linalg.det(vh.T @ u.T)) < 0.0:
        correction[-1, -1] = -1.0
    rotation = vh.T @ correction @ u.T
    scale = float(np.sum(singular_values * np.diag(correction)) / source_variance)
    if not math.isfinite(scale) or scale <= 1.0e-8:
        return None

    linear = rotation * scale
    # Snap the final transform to the KOTOR fit origin instead of the landmark
    # centroid, so pelvis/feet grounding stays deterministic for modder edits.
    source_origin = np.asarray(source.origin, dtype=np.float64)
    target_origin = np.asarray(target.origin, dtype=np.float64)
    translation = target_origin - linear @ source_origin
    mapped = (source_points @ linear.T) + translation
    errors = np.linalg.norm(mapped - target_points, axis=1)
    rms_error = float(np.sqrt(np.mean(errors * errors))) if errors.size else 0.0
    max_error = float(np.max(errors)) if errors.size else 0.0
    pair_errors: List[Dict[str, Any]] = []
    worst_pair_role = ""
    worst_pair_error = -1.0
    for index, (role, source_point, target_point) in enumerate(pairs):
        try:
            error = float(errors[index])
            mapped_point = mapped[index]
        except Exception:
            continue
        if error > worst_pair_error:
            worst_pair_error = error
            worst_pair_role = str(role)
        pair_errors.append({
            "role": str(role),
            "source_position": [float(value) for value in source_point],
            "target_position": [float(value) for value in target_point],
            "mapped_position": [float(value) for value in mapped_point.tolist()],
            "error": error,
        })
    return {
        "method": "paired_skeleton_landmark_similarity",
        "rotation_matrix": tuple(
            tuple(float(value) for value in row)
            for row in rotation.tolist()
        ),
        "scale": scale,
        "paired_roles": [role for role, _source, _target in pairs],
        "pair_count": len(pairs),
        "rms_error": rms_error,
        "max_error": max_error,
        "worst_pair_role": worst_pair_role,
        "pair_errors": pair_errors,
        "translation_basis": "native_fit_origin",
    }


def _landmark_alignment_for_applied_transform(
    alignment: Optional[Dict[str, Any]],
    source: _HumanoidFitFrame,
    target: _HumanoidFitFrame,
    *,
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    applied_scale: float,
    source_origin: Vec3,
    target_origin: Vec3,
    applied_scale_basis: str,
    translation_basis: str,
) -> Optional[Dict[str, Any]]:
    """Recompute pair residuals for the exact transform applied to the model."""

    if alignment is None:
        return None
    pairs = _paired_landmark_positions(source, target)
    if not pairs:
        return dict(alignment)
    linear_matrix = _scale_matrix(rotation_matrix, applied_scale)
    translation = _translation_for_affine(
        linear_matrix,
        source_origin,
        target_origin,
    )
    pair_errors: List[Dict[str, Any]] = []
    squared_total = 0.0
    max_error = 0.0
    worst_pair_role = ""
    for role, source_point, target_point in pairs:
        mapped_point = _vec_add(_mat_vec(linear_matrix, source_point), translation)
        delta = _vec_sub(mapped_point, target_point)
        error = _vec_len(delta)
        squared_total += error * error
        if error > max_error:
            max_error = error
            worst_pair_role = str(role)
        pair_errors.append({
            "role": str(role),
            "source_position": [float(value) for value in source_point],
            "target_position": [float(value) for value in target_point],
            "mapped_position": [float(value) for value in mapped_point],
            "error": float(error),
        })
    result = dict(alignment)
    result["pair_errors"] = pair_errors
    result["rms_error"] = math.sqrt(squared_total / float(len(pair_errors)))
    result["max_error"] = float(max_error)
    result["worst_pair_role"] = worst_pair_role
    result["applied_scale"] = float(applied_scale)
    result["applied_scale_basis"] = str(applied_scale_basis or "")
    result["translation_basis"] = str(translation_basis or "")
    result["error_basis"] = "applied_fit_transform"
    return result


def _mat_vec(matrix: Tuple[Vec3, Vec3, Vec3], vector: Vec3) -> Vec3:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2],
        matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2],
    )


def _matrix_as_lists(matrix: Tuple[Vec3, Vec3, Vec3]) -> List[List[float]]:
    return [[float(value) for value in row] for row in matrix]


def _scale_matrix(matrix: Tuple[Vec3, Vec3, Vec3], scale: float) -> Tuple[Vec3, Vec3, Vec3]:
    return tuple(
        tuple(float(value) * float(scale) for value in row)
        for row in matrix
    )  # type: ignore[return-value]


def _translation_for_affine(
    matrix: Tuple[Vec3, Vec3, Vec3],
    source_origin: Vec3,
    target_origin: Vec3,
) -> Vec3:
    mapped_origin = _mat_vec(matrix, source_origin)
    return _vec_sub(target_origin, mapped_origin)


def _ground_snapped_target_origin(
    *,
    bounds: Optional[Tuple[Vec3, Vec3]],
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    scale: float,
    source_origin: Vec3,
    target_origin: Vec3,
    target_frame: Optional[_HumanoidFitFrame] = None,
    reference_bounds: Optional[Tuple[Vec3, Vec3]] = None,
    preserve_target_origin: bool = False,
) -> Vec3:
    if preserve_target_origin:
        return target_origin
    if bounds is None:
        return target_origin
    linear_matrix = _scale_matrix(rotation_matrix, scale)
    translation = _translation_for_affine(
        linear_matrix,
        source_origin,
        target_origin,
    )

    def _mapped(point: Vec3) -> Vec3:
        return _vec_add(_mat_vec(linear_matrix, point), translation)

    mapped_bounds = _transform_bounds(bounds, _mapped)
    if mapped_bounds is None:
        return target_origin
    if reference_bounds is not None:
        target_ground_z = float(reference_bounds[0][2])
    elif target_frame is not None:
        target_ground_z = float(target_frame.origin[2])
    else:
        target_ground_z = float(target_origin[2])
    delta_z = target_ground_z - float(mapped_bounds[0][2])
    if abs(delta_z) <= 1.0e-8:
        return target_origin
    return (
        float(target_origin[0]),
        float(target_origin[1]),
        float(target_origin[2]) + delta_z,
    )


def _axis_map_matrix_to_kotor_z(vertical_axis: int) -> Tuple[Vec3, Vec3, Vec3]:
    if vertical_axis == 1:  # Y-up external model -> KOTOR Z-up
        return (
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 0.0),
        )
    if vertical_axis == 0:  # X-up external model -> KOTOR Z-up
        return (
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
        )
    return (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )


def _fit_transform_metadata(
    *,
    policy: str,
    scale: float,
    rotation_matrix: Tuple[Vec3, Vec3, Vec3],
    source_origin: Vec3,
    target_origin: Vec3,
    translation: Optional[Vec3] = None,
    landmark_alignment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    linear_matrix = _scale_matrix(rotation_matrix, scale)
    if translation is None:
        translation = _translation_for_affine(
            linear_matrix,
            source_origin,
            target_origin,
        )
    result = {
        "coordinate_space": "source_model_to_kotor_world",
        "policy": str(policy),
        "formula": "kotor_point = linear_matrix * source_point + translation",
        "scale": float(scale),
        "rotation_matrix": _matrix_as_lists(rotation_matrix),
        "linear_matrix": _matrix_as_lists(linear_matrix),
        "translation": _vec_as_list(translation),
        "source_origin": _vec_as_list(source_origin),
        "target_origin": _vec_as_list(target_origin),
    }
    if landmark_alignment:
        result["landmark_alignment"] = {
            "method": str(landmark_alignment.get("method") or ""),
            "pair_count": int(landmark_alignment.get("pair_count") or 0),
            "paired_roles": list(landmark_alignment.get("paired_roles") or []),
            "rms_error": float(landmark_alignment.get("rms_error") or 0.0),
            "max_error": float(landmark_alignment.get("max_error") or 0.0),
            "worst_pair_role": str(
                landmark_alignment.get("worst_pair_role") or ""
            ),
            "pair_errors": list(landmark_alignment.get("pair_errors") or []),
            "translation_basis": str(
                landmark_alignment.get("translation_basis") or ""
            ),
            "error_basis": str(
                landmark_alignment.get("error_basis") or ""
            ),
            "similarity_transform_accepted": bool(
                landmark_alignment.get("similarity_transform_accepted")
            ),
            "rotation_basis": str(
                landmark_alignment.get("rotation_basis") or ""
            ),
            "solved_scale": float(
                landmark_alignment.get("solved_scale")
                or landmark_alignment.get("scale")
                or 0.0
            ),
            "height_scale": float(landmark_alignment.get("height_scale") or 0.0),
            "height_scale_basis": str(
                landmark_alignment.get("height_scale_basis") or ""
            ),
            "applied_scale": float(landmark_alignment.get("applied_scale") or 0.0),
            "applied_scale_basis": str(
                landmark_alignment.get("applied_scale_basis") or ""
            ),
        }
    return result


def _kotor_template_humanoid_height(game_version: str) -> float:
    """Fallback KOTOR humanoid height when no selected base model is loaded."""
    try:
        gv = str(game_version).upper()
        if gv in {"K1", "KOTOR1", "1", "K2", "TSL", "KOTOR2", "2"}:
            return _DEFAULT_KOTOR_HUMANOID_HEIGHT
    except Exception:
        pass
    return _DEFAULT_KOTOR_HUMANOID_HEIGHT


def _axis_map_to_kotor_z(point: Tuple[float, float, float], vertical_axis: int) -> Tuple[float, float, float]:
    """Map the detected source up-axis to KOTOR Z-up while keeping handedness."""
    x, y, z = point
    if vertical_axis == 1:  # Y-up external model -> KOTOR Z-up
        return (x, z, y)
    if vertical_axis == 0:  # X-up external model -> KOTOR Z-up
        return (y, z, x)
    return (x, y, z)


def _quat_from_axis_angle(axis: str, radians_value: float) -> Tuple[float, float, float, float]:
    half = radians_value * 0.5
    s = math.sin(half)
    c = math.cos(half)
    if axis == "x":
        return (s, 0.0, 0.0, c)
    if axis == "y":
        return (0.0, s, 0.0, c)
    return (0.0, 0.0, s, c)


def _quat_mul(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    out = (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )
    length = math.sqrt(sum(v * v for v in out))
    if length <= 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(v / length for v in out)  # type: ignore[return-value]


def _rotate_point_xyz(
    point: Tuple[float, float, float],
    radians_xyz: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    x, y, z = point
    rx, ry, rz = radians_xyz
    if abs(rx) > 1e-12:
        c, s = math.cos(rx), math.sin(rx)
        y, z = y * c - z * s, y * s + z * c
    if abs(ry) > 1e-12:
        c, s = math.cos(ry), math.sin(ry)
        x, z = x * c + z * s, -x * s + z * c
    if abs(rz) > 1e-12:
        c, s = math.cos(rz), math.sin(rz)
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def _manual_fit_pivot(model: Any) -> Tuple[float, float, float]:
    bounds = _vertex_bounds(model)
    if bounds is None:
        return (0.0, 0.0, 0.0)
    bb_min, bb_max = bounds
    return (
        (bb_min[0] + bb_max[0]) * 0.5,
        (bb_min[1] + bb_max[1]) * 0.5,
        bb_min[2],
    )


def _transform_point_for_kotor(
    point: Tuple[float, float, float],
    *,
    vertical_axis: int,
    scale: float,
    offset: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    mapped = _axis_map_to_kotor_z(point, vertical_axis)
    return (
        mapped[0] * scale + offset[0],
        mapped[1] * scale + offset[1],
        mapped[2] * scale + offset[2],
    )


def _apply_point_transform_to_model(
    model: Any,
    *,
    transform_point,
    transform_direction,
    transform_node_position=None,
    mark_vertices_world: bool = False,
) -> None:
    node_transform = transform_node_position or transform_point
    for node in _iter_model_nodes(model):
        original_external_wp = getattr(node, "external_world_position", None)
        pos = getattr(node, "position", None)
        if pos is not None and len(pos) >= 3:
            try:
                source_pos = (float(pos[0]), float(pos[1]), float(pos[2]))
                node.position = node_transform(source_pos)
                if original_external_wp is None:
                    node.external_world_position = transform_point(source_pos)
            except Exception:
                pass

        if original_external_wp is not None and len(original_external_wp) >= 3:
            try:
                node.external_world_position = transform_point((
                    float(original_external_wp[0]),
                    float(original_external_wp[1]),
                    float(original_external_wp[2]),
                ))
            except Exception:
                pass

        verts = list(getattr(node, "vertices", []) or [])
        if verts:
            new_verts = []
            for vert in verts:
                try:
                    new_verts.append(transform_point((
                        float(vert[0]),
                        float(vert[1]),
                        float(vert[2]),
                    )))
                except Exception:
                    new_verts.append(vert)
            node.vertices = new_verts
            if mark_vertices_world:
                setattr(node, "_gr_vertices_in_kotor_world", True)
                try:
                    setattr(node, "vertex_space", 1)
                except Exception:
                    pass
            try:
                node.compute_bounds()
            except Exception:
                pass

        normals = list(getattr(node, "normals", []) or [])
        if normals:
            new_normals = []
            for normal in normals:
                try:
                    new_normals.append(transform_direction((
                        float(normal[0]),
                        float(normal[1]),
                        float(normal[2]),
                    )))
                except Exception:
                    new_normals.append(normal)
            node.normals = new_normals

    try:
        model.compute_bounds()
    except Exception:
        b = _vertex_bounds(model)
        if b is not None:
            model.bb_min, model.bb_max = b


def apply_external_model_fit_adjustment(
    model: Any,
    *,
    rotation_delta_degrees: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale_delta: float = 1.0,
    translation_delta: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    pivot_override: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, Any]:
    """Apply a manual post-auto-fit adjustment to an imported model.

    This is intentionally model-level rather than guide-level: it lets a user
    correct a Blender/FBX axis or unit mismatch after the automatic KOTOR base
    fit has run, before guide placement and binding.
    """
    if model is None:
        return {"ok": False, "code": "no_model", "message": "No model loaded."}

    scale = max(0.01, min(100.0, float(scale_delta or 1.0)))
    radians_xyz = tuple(math.radians(float(v or 0.0)) for v in rotation_delta_degrees)
    translation = tuple(float(v or 0.0) for v in translation_delta)
    pivot = _manual_fit_pivot(model)
    if pivot_override is not None and len(pivot_override) >= 3:
        try:
            pivot = (
                float(pivot_override[0]),
                float(pivot_override[1]),
                float(pivot_override[2]),
            )
        except Exception:
            pivot = _manual_fit_pivot(model)
    changed = False

    def transform_point(point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        rel = (
            (point[0] - pivot[0]) * scale,
            (point[1] - pivot[1]) * scale,
            (point[2] - pivot[2]) * scale,
        )
        rot = _rotate_point_xyz(rel, radians_xyz)
        return (
            rot[0] + pivot[0] + translation[0],
            rot[1] + pivot[1] + translation[1],
            rot[2] + pivot[2] + translation[2],
        )

    for node in _iter_model_nodes(model):
        pos = getattr(node, "position", None)
        if pos is not None and len(pos) >= 3:
            try:
                node.position = transform_point((float(pos[0]), float(pos[1]), float(pos[2])))
                changed = True
            except Exception:
                pass

        external_wp = getattr(node, "external_world_position", None)
        if external_wp is not None and len(external_wp) >= 3:
            try:
                node.external_world_position = transform_point((
                    float(external_wp[0]),
                    float(external_wp[1]),
                    float(external_wp[2]),
                ))
                changed = True
            except Exception:
                pass

        verts = list(getattr(node, "vertices", []) or [])
        if verts:
            new_verts = []
            for vert in verts:
                try:
                    new_verts.append(transform_point((float(vert[0]), float(vert[1]), float(vert[2]))))
                except Exception:
                    new_verts.append(vert)
            node.vertices = new_verts
            changed = True
            try:
                node.compute_bounds()
            except Exception:
                pass

        normals = list(getattr(node, "normals", []) or [])
        if normals and any(abs(v) > 1e-12 for v in radians_xyz):
            new_normals = []
            for normal in normals:
                try:
                    new_normals.append(_rotate_point_xyz((
                        float(normal[0]),
                        float(normal[1]),
                        float(normal[2]),
                    ), radians_xyz))
                except Exception:
                    new_normals.append(normal)
            node.normals = new_normals

        rot = getattr(node, "rotation", None)
        if rot is not None and len(rot) >= 4 and any(abs(v) > 1e-12 for v in radians_xyz):
            try:
                delta_q = (0.0, 0.0, 0.0, 1.0)
                for axis, angle in zip(("x", "y", "z"), radians_xyz):
                    if abs(angle) > 1e-12:
                        delta_q = _quat_mul(_quat_from_axis_angle(axis, angle), delta_q)
                node.rotation = _quat_mul(delta_q, tuple(float(v) for v in rot[:4]))
            except Exception:
                pass

    try:
        model.compute_bounds()
    except Exception:
        b = _vertex_bounds(model)
        if b is not None:
            model.bb_min, model.bb_max = b

    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    state = dict(metadata.get("manual_fit_adjustment") or {})
    old_scale = float(state.get("scale", 1.0) or 1.0)
    old_rot = tuple(float(v) for v in state.get("rotation_degrees", (0.0, 0.0, 0.0)))
    old_translation = tuple(float(v) for v in state.get("translation", (0.0, 0.0, 0.0)))
    state["scale"] = old_scale * scale
    state["rotation_degrees"] = tuple(
        old_rot[i] + float(rotation_delta_degrees[i] or 0.0)
        for i in range(3)
    )
    state["translation"] = tuple(old_translation[i] + translation[i] for i in range(3))
    metadata["manual_fit_adjustment"] = state
    return {
        "ok": changed,
        "code": "adjusted" if changed else "unchanged",
        "message": "Manual fit adjustment applied." if changed else "Nothing to adjust.",
        "scale_delta": scale,
        "rotation_delta_degrees": tuple(float(v or 0.0) for v in rotation_delta_degrees),
        "translation_delta": translation,
        "pivot": pivot,
    }


def normalize_external_model_for_kotor(
    model: Any,
    *,
    game_version: str = "K1",
    target_height: Optional[float] = None,
    reference_model: Optional[Any] = None,
    reference_label: str = "",
    fit_override: Optional[Any] = None,
    expected_mode: Optional[Any] = None,
) -> Dict[str, Any]:
    """Scale and orient an imported external mesh into KOTOR humanoid space.

    External FBX/glTF files often arrive in DCC/game-engine units, e.g. Unreal
    Manny at ~8.9 units tall.  The best fitting target is the user-selected
    KOTOR base model/supermodel; when one is unavailable we fall back to the
    canonical humanoid height so guide placement still lands in Odyssey space.
    """
    bounds = _vertex_bounds(model)
    if bounds is None:
        return {"ok": False, "code": "no_vertices", "message": "No vertex bounds."}

    bb_min, bb_max = bounds
    reference_bounds = _reference_model_fit_bounds(reference_model)
    source_frame = _infer_humanoid_fit_frame(
        model,
        bounds=bounds,
        prefer_skeleton_landmarks=True,
    )
    target_frame = (
        _infer_humanoid_fit_frame(reference_model, bounds=reference_bounds)
        if reference_model is not None else None
    )
    override = _coerce_auto_fit_override(fit_override)
    manual_source_frame = (
        _manual_override_frame(
            model,
            bounds=bounds,
            source_frame=source_frame,
            override=override,
        )
        if override.is_active() else None
    )
    manual_target_frame = target_frame or _default_target_fit_frame(reference_bounds)
    fit_report = inspect_external_model_fit(
        model,
        game_version=game_version,
        target_height=target_height,
        reference_model=reference_model,
        reference_label=reference_label,
        fit_override=override,
        expected_mode=expected_mode,
    )
    exact_native_fit = _native_template_exact_bounds_fit(
        model,
        bounds=bounds,
        reference_bounds=reference_bounds,
        reference_label=reference_label or getattr(reference_model, "name", "") or "",
        fit_report=fit_report,
    )
    if exact_native_fit is not None:
        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        metadata["kotor_normalization"] = exact_native_fit
        metadata["kotor_fit_report"] = exact_native_fit["fit_report"]
        return exact_native_fit

    native_scaled_fit = None
    if _is_creature_mode_value(expected_mode) and not override.is_active() and reference_model is not None:
        native_scaled_fit = _native_template_scaled_bounds_fit(
            model,
            bounds=bounds,
            reference_bounds=reference_bounds,
            reference_model=reference_model,
            reference_label=reference_label or getattr(reference_model, "name", "") or "",
            fit_report=fit_report,
        )
    native_scaled_fit_is_safe = (
        native_scaled_fit is not None
        and (
            bool(native_scaled_fit.get("surface_registration_refined", False))
            or
            int(native_scaled_fit.get("deformation_bone_count", 0)) <= 0
            or bool(native_scaled_fit.get("all_bones_inside", False))
        )
    )
    if native_scaled_fit_is_safe:
        def transform_point(point: Vec3) -> Vec3:
            return _vec_add(
                _mat_vec(native_scaled_fit["linear_matrix"], point),
                native_scaled_fit["offset"],
            )

        normal_matrix = _normal_transform_from_linear_matrix(native_scaled_fit["linear_matrix"])

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(normal_matrix, direction)
            return _vec_normalize(rotated) or rotated

        _apply_point_transform_to_model(
            model,
            transform_point=transform_point,
            transform_direction=transform_direction,
            mark_vertices_world=True,
        )

        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        result = {
            "ok": True,
            "code": "normalized",
            "trace_version": "ghostrigger.fit/v1",
            "scale": float(native_scaled_fit["scale"]),
            "axis_scales": tuple(float(value) for value in native_scaled_fit["axis_scales"]),
            "axis_fit_distortion": float(native_scaled_fit.get("axis_fit_distortion", 0.0)),
            "orientation_score_basis": str(native_scaled_fit.get("orientation_score_basis") or ""),
            "native_vertex_cloud_score": native_scaled_fit.get("native_vertex_cloud_score"),
            "surface_registration_refined": bool(native_scaled_fit.get("surface_registration_refined", False)),
            "surface_registration_iterations": int(native_scaled_fit.get("surface_registration_iterations", 0) or 0),
            "all_bones_inside": bool(native_scaled_fit.get("all_bones_inside", False)),
            "outside_count": int(native_scaled_fit.get("outside_count", 0)),
            "bone_position_source": str(native_scaled_fit.get("bone_position_source") or ""),
            "deformation_bone_count": int(native_scaled_fit.get("deformation_bone_count", 0)),
            "skeleton_containment_adjusted_axes": list(
                native_scaled_fit.get("skeleton_containment_adjusted_axes") or []
            ),
            "skeleton_pivot_outlier_count": int(
                native_scaled_fit.get("skeleton_pivot_outlier_count", 0) or 0
            ),
            "source_height": float(native_scaled_fit["source_height"]),
            "target_height": float(native_scaled_fit["target_height"]),
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "vertical_axis": str(native_scaled_fit["source_up_label"]).lstrip("+"),
            "offset": native_scaled_fit["offset"],
            "target_center_xy": (
                float(native_scaled_fit["target_origin"][0]),
                float(native_scaled_fit["target_origin"][1]),
            ),
            "target_ground_z": float(native_scaled_fit["target_origin"][2]),
            "external_world_positions_fit": True,
            "fit_policy": "native_template_scaled_bounds_replacement",
            "scale_basis": "native_template_axis_bounds_ratio",
            "fit_transform": native_scaled_fit["fit_transform"],
            "fit_report": native_scaled_fit["fit_report"],
            "fitted_visual_overlay": native_scaled_fit["fitted_visual_overlay"],
        }
        metadata["kotor_normalization"] = result
        metadata["kotor_fit_report"] = native_scaled_fit["fit_report"]
        return result

    # Containment-based fit handles creature-mode external meshes after the
    # already-KOTOR-space exact-template path has had first refusal.
    containment_fit = None
    if _is_creature_mode_value(expected_mode) and not override.is_active() and reference_model is not None:
        containment_fit = _containment_based_fit_solution(
            model, bounds, reference_model, reference_bounds,
        )
    if containment_fit is not None:
        def transform_point(point: Vec3) -> Vec3:
            return _vec_add(
                _mat_vec(containment_fit["linear_matrix"], point),
                containment_fit["offset"],
            )

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(containment_fit["rotation_matrix"], direction)
            return _vec_normalize(rotated) or rotated

        fitted_visual_overlay = {
            "coordinate_space": "kotor_world_after_fit",
            "source": _fit_frame_visual_overlay(
                model,
                None,
                bounds,
                transform_point=transform_point,
                transform_direction=transform_direction,
                axis_length_scale=float(containment_fit["scale"]),
            ),
            "target": _fit_frame_visual_overlay(
                reference_model,
                None,
                reference_bounds,
            ) if reference_model is not None else None,
        }
        if isinstance(fit_report, dict):
            fit_report = dict(fit_report)
        else:
            fit_report = {}
        auto_fit_report = dict(fit_report.get("auto_fit_report") or {})
        auto_fit_report.update({
            "source_forward_axis": str(containment_fit.get("source_forward_label") or "unknown"),
            "source_up_axis": str(containment_fit.get("source_up_label") or "unknown"),
            "target_forward_axis": "+y",
            "target_up_axis": "+z",
            "scale_factor": float(containment_fit["scale"]),
            "height_source": str(containment_fit.get("method") or "containment_fit"),
            "ground_origin_basis": "donor_skin_bone_containment",
            "used_landmarks": [
                "source:mesh_surface_or_oriented_bounds",
                "target:donor_skin_bone_map",
            ],
            "confidence": 0.84,
            "fallback_used": False,
            "notes": str(containment_fit.get("notes") or "Containment fit used donor deformation bones."),
        })
        fit_report.update({
            "ok": True,
            "code": "containment_bone_inside_mesh",
            "message": "External creature mesh fit inspected using donor deformation-bone containment.",
            "fit_policy": "containment_bone_inside_mesh",
            "scale_basis": str(containment_fit.get("method") or "containment_fit"),
            "scale": float(containment_fit["scale"]),
            "source_height": float(containment_fit["source_height"]),
            "target_height": float(containment_fit["target_height"]),
            "vertical_axis": str(containment_fit.get("source_up_label") or "+z").lstrip("+"),
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "source_bounds": _bounds_as_lists(bounds),
            "reference_bounds": _bounds_as_lists(reference_bounds),
            "source_forward_axis": auto_fit_report["source_forward_axis"],
            "source_up_axis": auto_fit_report["source_up_axis"],
            "target_forward_axis": "+y",
            "target_up_axis": "+z",
            "scale_factor": float(containment_fit["scale"]),
            "height_source": auto_fit_report["height_source"],
            "ground_origin_basis": auto_fit_report["ground_origin_basis"],
            "used_landmarks": list(auto_fit_report["used_landmarks"]),
            "confidence": float(auto_fit_report["confidence"]),
            "fallback_used": False,
            "notes": auto_fit_report["notes"],
            "auto_fit_report": auto_fit_report,
            "fit_transform": containment_fit["fit_transform"],
            "fitted_visual_overlay": fitted_visual_overlay,
            "containment_fit": {
                "method": str(containment_fit.get("method") or ""),
                "containment_volume": str(containment_fit.get("containment_volume") or ""),
                "surface_containment_checked": bool(containment_fit.get("surface_containment_checked", False)),
                "containment_guarantee": str(containment_fit.get("containment_guarantee") or ""),
                "mesh_watertight": bool(containment_fit.get("mesh_watertight", False)),
                "outside_count": int(containment_fit.get("outside_count", 0)),
                "total_outside_count": int(
                    containment_fit.get("total_outside_count", containment_fit.get("outside_count", 0))
                ),
                "deformation_bone_count": int(containment_fit.get("deformation_bone_count", 0)),
                "total_deformation_bone_count": int(
                    containment_fit.get("total_deformation_bone_count", containment_fit.get("deformation_bone_count", 0))
                ),
                "hard_containment_bone_count": int(
                    containment_fit.get("hard_containment_bone_count", containment_fit.get("deformation_bone_count", 0))
                ),
                "soft_containment_bone_count": int(containment_fit.get("soft_containment_bone_count", 0)),
                "soft_containment_bone_names": list(containment_fit.get("soft_containment_bone_names") or []),
                "bone_position_source": str(containment_fit.get("bone_position_source") or ""),
            },
            "kotor_contract": {
                "native_skeleton_is_authority": True,
                "imported_mesh_role": "payload_guest",
                "final_dag_source": "selected_kotor_base",
            },
        })

        _apply_point_transform_to_model(
            model,
            transform_point=transform_point,
            transform_direction=transform_direction,
            mark_vertices_world=True,
        )

        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        result = {
            "ok": True,
            "code": "normalized",
            "trace_version": "ghostrigger.fit/v1",
            "scale": float(containment_fit["scale"]),
            "source_height": float(containment_fit["source_height"]),
            "target_height": float(containment_fit["target_height"]),
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "vertical_axis": "z",
            "offset": containment_fit["offset"],
            "fit_policy": "containment_bone_inside_mesh",
            "scale_basis": str(containment_fit.get("method") or "containment_fit"),
            "all_bones_inside": containment_fit["all_inside"],
            "outside_count": containment_fit["outside_count"],
            "total_outside_count": containment_fit.get(
                "total_outside_count",
                containment_fit["outside_count"],
            ),
            "fit_method": containment_fit.get("method", ""),
            "containment_volume": containment_fit.get("containment_volume", ""),
            "surface_containment_checked": containment_fit.get("surface_containment_checked", False),
            "containment_guarantee": containment_fit.get("containment_guarantee", ""),
            "mesh_watertight": containment_fit.get("mesh_watertight", False),
            "deformation_bone_count": containment_fit.get("deformation_bone_count", 0),
            "total_deformation_bone_count": containment_fit.get(
                "total_deformation_bone_count",
                containment_fit.get("deformation_bone_count", 0),
            ),
            "hard_containment_bone_count": containment_fit.get(
                "hard_containment_bone_count",
                containment_fit.get("deformation_bone_count", 0),
            ),
            "soft_containment_bone_count": containment_fit.get("soft_containment_bone_count", 0),
            "soft_containment_bone_names": list(containment_fit.get("soft_containment_bone_names") or []),
            "bone_position_source": containment_fit.get("bone_position_source", ""),
            "fit_transform": containment_fit["fit_transform"],
            "fit_report": fit_report,
            "fitted_visual_overlay": fitted_visual_overlay,
        }
        metadata["kotor_normalization"] = result
        metadata["kotor_fit_report"] = fit_report
        return result

    landmark_fit = (
        _landmark_based_fit_solution(model, bounds, reference_model, reference_bounds)
        if _is_creature_mode_value(expected_mode) and not override.is_active() else None
    )
    if landmark_fit is not None:
        def transform_point(point: Vec3) -> Vec3:
            return _vec_add(
                _mat_vec(landmark_fit["linear_matrix"], point),
                landmark_fit["offset"],
            )

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(landmark_fit["rotation_matrix"], direction)
            return _vec_normalize(rotated) or rotated

        fitted_visual_overlay = {
            "coordinate_space": "kotor_world_after_fit",
            "source": _fit_frame_visual_overlay(
                model,
                None,
                bounds,
                transform_point=transform_point,
                transform_direction=transform_direction,
                axis_length_scale=float(landmark_fit["scale"]),
            ),
            "target": _fit_frame_visual_overlay(
                reference_model,
                None,
                reference_bounds,
            ) if reference_model is not None else None,
        }
        if isinstance(fit_report, dict):
            fit_report = dict(fit_report)
            fit_report["fitted_visual_overlay"] = fitted_visual_overlay
            fit_report["fit_transform"] = landmark_fit["fit_transform"]

        # Landmark Kabsch produces a single consistent similarity transform;
        # apply it to vertices, normals, node positions and external world
        # positions uniformly (node positions get the full affine so the
        # imported mesh's own skeleton lands in KOTOR space too).
        _apply_point_transform_to_model(
            model,
            transform_point=transform_point,
            transform_direction=transform_direction,
            mark_vertices_world=True,
        )

        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        result = {
            "ok": True,
            "code": "normalized",
            "scale": float(landmark_fit["scale"]),
            "source_height": float(landmark_fit["source_height"]),
            "target_height": float(landmark_fit["target_height"]),
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "vertical_axis": "z",
            "offset": landmark_fit["offset"],
            "target_center_xy": (
                float(landmark_fit["target_origin"][0]),
                float(landmark_fit["target_origin"][1]),
            ),
            "target_ground_z": float(landmark_fit["target_origin"][2]),
            "external_world_positions_fit": True,
            "fit_policy": "landmark_kabsch_basis",
            "scale_basis": "donor_bone_landmark_kabsch",
            "fit_transform": landmark_fit["fit_transform"],
            "fit_report": fit_report,
            "fitted_visual_overlay": fitted_visual_overlay,
        }
        metadata["kotor_normalization"] = result
        metadata["kotor_fit_report"] = fit_report
        return result

    creature_fit = (
        _creature_bounds_fit_solution(bounds, reference_bounds)
        if _is_creature_mode_value(expected_mode) and not override.is_active() else None
    )
    if creature_fit is not None:
        def transform_point(point: Vec3) -> Vec3:
            return _vec_add(
                _mat_vec(creature_fit["linear_matrix"], point),
                creature_fit["offset"],
            )

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(creature_fit["rotation_matrix"], direction)
            return _vec_normalize(rotated) or rotated

        def transform_node_position(point: Vec3) -> Vec3:
            return _mat_vec(creature_fit["linear_matrix"], point)

        fitted_visual_overlay = {
            "coordinate_space": "kotor_world_after_fit",
            "source": _fit_frame_visual_overlay(
                model,
                None,
                bounds,
                transform_point=transform_point,
                transform_direction=transform_direction,
                axis_length_scale=float(creature_fit["scale"]),
            ),
            "target": _fit_frame_visual_overlay(
                reference_model,
                None,
                reference_bounds,
            ) if reference_model is not None else None,
        }
        if isinstance(fit_report, dict):
            fit_report = dict(fit_report)
            fit_report["fitted_visual_overlay"] = fitted_visual_overlay
            fit_report["fit_transform"] = creature_fit["fit_transform"]

        _apply_point_transform_to_model(
            model,
            transform_point=transform_point,
            transform_direction=transform_direction,
            transform_node_position=transform_node_position,
            mark_vertices_world=True,
        )

        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        result = {
            "ok": True,
            "code": "normalized",
            "scale": float(creature_fit["scale"]),
            "source_height": float(creature_fit["source_height"]),
            "target_height": float(creature_fit["target_height"]),
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "vertical_axis": str(creature_fit["source_up_label"]).lstrip("+"),
            "offset": creature_fit["offset"],
            "target_center_xy": (
                float(creature_fit["target_origin"][0]),
                float(creature_fit["target_origin"][1]),
            ),
            "target_ground_z": float(creature_fit["target_origin"][2]),
            "external_world_positions_fit": True,
            "fit_policy": "creature_bounds_basis",
            "scale_basis": "creature_bounds_median_extent",
            "fit_transform": creature_fit["fit_transform"],
            "fit_report": fit_report,
            "fitted_visual_overlay": fitted_visual_overlay,
        }
        metadata["kotor_normalization"] = result
        metadata["kotor_fit_report"] = fit_report
        return result

    transform_source_frame = manual_source_frame
    transform_target_frame = manual_target_frame
    transform_policy = "manual_axis_override"
    transform_scale_basis = "manual_override_height"
    if transform_source_frame is None or transform_target_frame is None:
        transform_source_frame = source_frame
        transform_target_frame = target_frame
        transform_policy = "bone_landmark_basis"
        transform_scale_basis = ""

    if transform_source_frame is not None and transform_target_frame is not None:
        reference_height = _height_from_bounds(reference_bounds)
        if transform_policy == "manual_axis_override":
            if target_height is not None:
                target = float(target_height)
                transform_scale_basis = "explicit_target_height"
            elif reference_height > 0.01:
                target = float(reference_height)
                transform_scale_basis = "reference_bounds_height"
            else:
                target = float(transform_target_frame.height)
                transform_scale_basis = "manual_override_height"
        else:
            target, transform_scale_basis = _target_height_for_landmark_fit(
                explicit_target_height=target_height,
                reference_height=reference_height,
                target_frame=transform_target_frame,
                source_frame=transform_source_frame,
            )
        landmark_alignment = (
            None
            if transform_policy == "manual_axis_override"
            else _landmark_similarity_alignment(
                transform_source_frame,
                transform_target_frame,
            )
        )
        height_scale = target / transform_source_frame.height if transform_source_frame.height > 1.0e-6 else 1.0
        height_scale_basis = transform_scale_basis
        use_similarity_transform = _landmark_similarity_alignment_is_usable(
            height_scale=height_scale,
            landmark_alignment=landmark_alignment,
        )
        scale, transform_scale_basis = _scale_for_landmark_fit(
            height_scale=height_scale,
            height_scale_basis=height_scale_basis,
            landmark_alignment=landmark_alignment,
        )
        rotation = (
            landmark_alignment["rotation_matrix"]
            if landmark_alignment is not None and use_similarity_transform
            else _basis_rotation(transform_source_frame, transform_target_frame)
        )
        if landmark_alignment is not None:
            landmark_alignment = dict(landmark_alignment)
            landmark_alignment["solved_scale"] = float(landmark_alignment["scale"])
            landmark_alignment["height_scale"] = float(height_scale)
            landmark_alignment["height_scale_basis"] = height_scale_basis
            landmark_alignment["applied_scale"] = float(scale)
            landmark_alignment["applied_scale_basis"] = transform_scale_basis
            landmark_alignment["similarity_transform_accepted"] = bool(
                use_similarity_transform
            )
            landmark_alignment["rotation_basis"] = (
                "paired_skeleton_similarity"
                if use_similarity_transform else
                "bone_landmark_basis"
            )
        preserve_skeleton_origin = _preserve_skeleton_landmark_origin_for_fit(
            transform_source_frame,
            transform_target_frame,
        )
        translation_basis = (
            "skeleton_landmark_native_fit_origin"
            if preserve_skeleton_origin else
            "ground_snapped_native_fit_origin"
        )
        target_origin = _ground_snapped_target_origin(
            bounds=bounds,
            rotation_matrix=rotation,
            scale=scale,
            source_origin=transform_source_frame.origin,
            target_origin=transform_target_frame.origin,
            target_frame=transform_target_frame,
            reference_bounds=reference_bounds,
            preserve_target_origin=preserve_skeleton_origin,
        )
        if landmark_alignment is not None:
            landmark_alignment = _landmark_alignment_for_applied_transform(
                landmark_alignment,
                transform_source_frame,
                transform_target_frame,
                rotation_matrix=rotation,
                applied_scale=scale,
                source_origin=transform_source_frame.origin,
                target_origin=target_origin,
                applied_scale_basis=transform_scale_basis,
                translation_basis=translation_basis,
            )
        fit_transform = _fit_transform_metadata(
            policy=transform_policy,
            scale=scale,
            rotation_matrix=rotation,
            source_origin=transform_source_frame.origin,
            target_origin=target_origin,
            landmark_alignment=landmark_alignment,
        )

        def transform_point(point: Vec3) -> Vec3:
            rel = _vec_scale(_vec_sub(point, transform_source_frame.origin), scale)
            return _vec_add(target_origin, _mat_vec(rotation, rel))

        def transform_direction(direction: Vec3) -> Vec3:
            rotated = _mat_vec(rotation, direction)
            return _vec_normalize(rotated) or rotated

        def transform_node_position(point: Vec3) -> Vec3:
            rel = _vec_scale(point, scale)
            return _mat_vec(rotation, rel)

        fitted_visual_overlay = {
            "coordinate_space": "kotor_world_after_fit",
            "source": _fit_frame_visual_overlay(
                model,
                transform_source_frame,
                bounds,
                transform_point=transform_point,
                transform_direction=transform_direction,
                axis_length_scale=scale,
                prefer_skeleton_landmarks=True,
            ),
            "target": _fit_frame_visual_overlay(
                reference_model,
                transform_target_frame,
                reference_bounds,
            ) if reference_model is not None else None,
        }
        if isinstance(fit_report, dict):
            fit_report = dict(fit_report)
            fit_report["fitted_visual_overlay"] = fitted_visual_overlay
            fit_report["fit_transform"] = fit_transform

        _apply_point_transform_to_model(
            model,
            transform_point=transform_point,
            transform_direction=transform_direction,
            transform_node_position=transform_node_position,
            mark_vertices_world=True,
        )

        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(model, "metadata", metadata)
        result = {
            "ok": True,
            "code": "normalized",
            "scale": scale,
            "source_height": transform_source_frame.height,
            "target_height": target,
            "reference": reference_label or getattr(reference_model, "name", "") or "",
            "vertical_axis": "manual_override" if transform_policy == "manual_axis_override" else "bone_landmarks",
            "offset": _vec_sub(
                target_origin,
                _mat_vec(rotation, _vec_scale(transform_source_frame.origin, scale)),
            ),
            "target_center_xy": (target_origin[0], target_origin[1]),
            "target_ground_z": target_origin[2],
            "external_world_positions_fit": True,
            "fit_policy": transform_policy,
            "scale_basis": transform_scale_basis,
            "source_fit_landmarks": dict(transform_source_frame.landmarks),
            "target_fit_landmarks": dict(transform_target_frame.landmarks),
            "source_fit_confidence": transform_source_frame.confidence,
            "target_fit_confidence": transform_target_frame.confidence,
            "fit_transform": fit_transform,
            "fit_report": fit_report,
            "fitted_visual_overlay": fitted_visual_overlay,
        }
        metadata["kotor_normalization"] = result
        metadata["kotor_fit_report"] = fit_report
        return result

    extents = tuple(max(0.0, bb_max[i] - bb_min[i]) for i in range(3))
    vertical_axis = max(range(3), key=lambda i: extents[i])
    source_height = max(extents[vertical_axis], 1e-6)
    reference_height = _height_from_bounds(reference_bounds) if reference_bounds is not None else 0.0
    target = float(target_height or reference_height or _kotor_template_humanoid_height(game_version))
    scale = target / source_height if source_height > 1e-6 else 1.0

    mapped_min = _axis_map_to_kotor_z(bb_min, vertical_axis)
    mapped_max = _axis_map_to_kotor_z(bb_max, vertical_axis)
    norm_min = tuple(min(mapped_min[i], mapped_max[i]) for i in range(3))
    norm_max = tuple(max(mapped_min[i], mapped_max[i]) for i in range(3))
    center_x = (norm_min[0] + norm_max[0]) * 0.5
    center_y = (norm_min[1] + norm_max[1]) * 0.5
    if reference_bounds is not None:
        ref_min, ref_max = reference_bounds
        target_center_x = (float(ref_min[0]) + float(ref_max[0])) * 0.5
        target_center_y = (float(ref_min[1]) + float(ref_max[1])) * 0.5
        target_ground_z = float(ref_min[2])
    else:
        target_center_x = 0.0
        target_center_y = 0.0
        target_ground_z = 0.0
    offset = (
        target_center_x - center_x * scale,
        target_center_y - center_y * scale,
        target_ground_z - norm_min[2] * scale,
    )
    source_origin = _bounds_ground_center(bounds)
    target_origin = _transform_point_for_kotor(
        source_origin,
        vertical_axis=vertical_axis,
        scale=scale,
        offset=offset,
    )
    fit_transform = _fit_transform_metadata(
        policy="selected_reference_bounds" if reference_bounds is not None else "origin_height",
        scale=scale,
        rotation_matrix=_axis_map_matrix_to_kotor_z(vertical_axis),
        source_origin=source_origin,
        target_origin=target_origin,
    )

    def transform_point(point: Vec3) -> Vec3:
        return _transform_point_for_kotor(
            point,
            vertical_axis=vertical_axis,
            scale=scale,
            offset=offset,
        )

    def transform_direction(direction: Vec3) -> Vec3:
        if vertical_axis == 2:
            return direction
        mapped = _axis_map_to_kotor_z(direction, vertical_axis)
        return _vec_normalize(mapped) or mapped

    def transform_node_position(point: Vec3) -> Vec3:
        return _transform_point_for_kotor(
            point,
            vertical_axis=vertical_axis,
            scale=scale,
            offset=(0.0, 0.0, 0.0),
        )

    fitted_visual_overlay = {
        "coordinate_space": "kotor_world_after_fit",
        "source": _fit_frame_visual_overlay(
            model,
            None,
            bounds,
            transform_point=transform_point,
            axis_length_scale=scale,
        ),
        "target": None,
    }
    if isinstance(fit_report, dict):
        fit_report = dict(fit_report)
        fit_report["fitted_visual_overlay"] = fitted_visual_overlay
        fit_report["fit_transform"] = fit_transform

    _apply_point_transform_to_model(
        model,
        transform_point=transform_point,
        transform_direction=transform_direction,
        transform_node_position=transform_node_position,
        mark_vertices_world=True,
    )

    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    result = {
        "ok": True,
        "code": "normalized",
        "scale": scale,
        "source_height": source_height,
        "target_height": target,
        "reference": reference_label or getattr(reference_model, "name", "") or "",
        "vertical_axis": ("x", "y", "z")[vertical_axis],
        "offset": offset,
        "target_center_xy": (target_center_x, target_center_y),
        "target_ground_z": target_ground_z,
        "external_world_positions_fit": True,
        "fit_policy": "selected_reference_bounds" if reference_bounds is not None else "origin_height",
        "fit_transform": fit_transform,
        "fit_report": fit_report,
        "fitted_visual_overlay": fitted_visual_overlay,
    }
    metadata["kotor_normalization"] = result
    metadata["kotor_fit_report"] = fit_report
    return result


def _native_template_exact_bounds_fit(
    model: Any,
    *,
    bounds: Tuple[Vec3, Vec3],
    reference_bounds: Optional[Tuple[Vec3, Vec3]],
    reference_label: str,
    fit_report: Any,
) -> Optional[Dict[str, Any]]:
    """Trust an already KOTOR-space mesh when it matches the native base bounds."""

    if reference_bounds is None:
        return None
    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    external = metadata.get("external_import")
    external = external if isinstance(external, dict) else {}
    if external.get("target_axis_system") != "kotor_z_up":
        return None
    if not _native_template_replacement_match(
        bounds,
        reference_bounds,
        reference_label=reference_label,
        source_path=str(external.get("source_path") or ""),
    ):
        return None

    origin = _bounds_ground_center(bounds)
    rotation = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    # Compute real scale from source/target bounds instead of assuming 1.0.
    # Unit-space OBJ files (spanning -0.5 to 0.5) need to be scaled up to
    # match the KOTOR skeleton footprint.
    source_height = _height_from_bounds(bounds)
    target_height = _height_from_bounds(reference_bounds)
    if source_height > 1e-6 and target_height > 1e-6:
        fit_scale = float(target_height) / float(source_height)
    else:
        fit_scale = 1.0
    target_origin = _bounds_ground_center(reference_bounds)
    fit_transform = _fit_transform_metadata(
        policy="native_template_kotor_space_replacement",
        scale=fit_scale,
        rotation_matrix=rotation,
        source_origin=origin,
        target_origin=target_origin,
    )
    source_bounds = _bounds_as_lists(bounds)
    target_bounds = _bounds_as_lists(reference_bounds)
    used_landmarks = [
        "source:head=native_render_bounds",
        "source:pelvis=native_render_bounds",
        "source:side_pair=native_render_bounds",
        "source:left_foot=native_render_bounds",
        "source:right_foot=native_render_bounds",
        "target:head=native_render_bounds",
        "target:pelvis=native_render_bounds",
        "target:side_pair=native_render_bounds",
        "target:left_foot=native_render_bounds",
        "target:right_foot=native_render_bounds",
    ]
    report = dict(fit_report) if isinstance(fit_report, dict) else {}
    auto_fit_report = dict(report.get("auto_fit_report") or {})
    auto_fit_report.update({
        "source_forward_axis": "+y",
        "source_up_axis": "+z",
        "target_forward_axis": "+y",
        "target_up_axis": "+z",
        "scale_factor": fit_scale,
        "height_source": "native_render_bounds",
        "ground_origin_basis": "native_render_bounds_bottom",
        "used_landmarks": list(used_landmarks),
        "confidence": 0.95,
        "fallback_used": False,
        "notes": (
            "Imported mesh matched the selected native template replacement "
            "footprint and was scaled to the KOTOR skeleton height."
        ),
    })
    report.update({
        "ok": True,
        "code": "native_template_kotor_space_replacement",
        "message": "External mesh matched the selected native KOTOR replacement footprint and was scaled to fit.",
        "fit_policy": "native_template_kotor_space_replacement",
        "scale_basis": "native_render_height_ratio",
        "scale": fit_scale,
        "source_height": source_height,
        "target_height": target_height,
        "vertical_axis": "z",
        "reference": str(reference_label or ""),
        "source_bounds": source_bounds,
        "reference_bounds": target_bounds,
        "source_forward_axis": "+y",
        "source_up_axis": "+z",
        "target_forward_axis": "+y",
        "target_up_axis": "+z",
        "scale_factor": fit_scale,
        "height_source": "native_render_bounds",
        "ground_origin_basis": "native_render_bounds_bottom",
        "used_landmarks": list(used_landmarks),
        "confidence": 0.95,
        "fallback_used": False,
        "notes": auto_fit_report["notes"],
        "auto_fit_report": auto_fit_report,
        "source_frame": {
            "landmarks": {
                "head": "native_render_bounds",
                "pelvis": "native_render_bounds",
                "side_pair": "native_render_bounds",
                "left_foot": "native_render_bounds",
                "right_foot": "native_render_bounds",
            },
            "landmark_sources": {
                "head": "native_render_bounds",
                "pelvis": "native_render_bounds",
                "side_pair": "native_render_bounds",
                "left_foot": "native_render_bounds",
                "right_foot": "native_render_bounds",
            },
        },
        "target_frame": {
            "landmarks": {
                "head": "native_render_bounds",
                "pelvis": "native_render_bounds",
                "side_pair": "native_render_bounds",
                "left_foot": "native_render_bounds",
                "right_foot": "native_render_bounds",
            },
            "landmark_sources": {
                "head": "native_render_bounds",
                "pelvis": "native_render_bounds",
                "side_pair": "native_render_bounds",
                "left_foot": "native_render_bounds",
                "right_foot": "native_render_bounds",
            },
        },
        "fit_transform": fit_transform,
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
        "native_template_kotor_space_replacement": {
            "source_bounds": source_bounds,
            "reference_bounds": target_bounds,
            "source_path": str(external.get("source_path") or ""),
            "axis_conversion": str(external.get("axis_conversion") or ""),
            "reference_label": str(reference_label or ""),
        },
    })
    fitted_visual_overlay = {
        "coordinate_space": "kotor_world_after_fit",
        "source": {
            "bounds": source_bounds,
            "origin": _vec_as_list(origin),
            "axes": {
                "right": [1.0, 0.0, 0.0],
                "forward": [0.0, 1.0, 0.0],
                "up": [0.0, 0.0, 1.0],
            },
            "landmarks": [],
        },
        "target": {
            "bounds": target_bounds,
            "origin": _vec_as_list(_bounds_ground_center(reference_bounds)),
            "axes": {
                "right": [1.0, 0.0, 0.0],
                "forward": [0.0, 1.0, 0.0],
                "up": [0.0, 0.0, 1.0],
            },
            "landmarks": [],
        },
    }
    report["fitted_visual_overlay"] = fitted_visual_overlay
    return {
        "ok": True,
        "code": "native_template_kotor_space_replacement",
        "scale": 1.0,
        "source_height": _height_from_bounds(bounds),
        "target_height": _height_from_bounds(reference_bounds),
        "reference": str(reference_label or ""),
        "vertical_axis": "z",
        "offset": (0.0, 0.0, 0.0),
        "target_center_xy": (
            (float(reference_bounds[0][0]) + float(reference_bounds[1][0])) * 0.5,
            (float(reference_bounds[0][1]) + float(reference_bounds[1][1])) * 0.5,
        ),
        "target_ground_z": float(reference_bounds[0][2]),
        "external_world_positions_fit": True,
        "fit_policy": "native_template_kotor_space_replacement",
        "scale_basis": "native_render_footprint_match",
        "fit_transform": fit_transform,
        "fit_report": report,
        "fitted_visual_overlay": fitted_visual_overlay,
    }


def _native_template_replacement_match(
    source_bounds: Tuple[Vec3, Vec3],
    reference_bounds: Tuple[Vec3, Vec3],
    *,
    reference_label: str,
    source_path: str,
    tolerance: float = 0.15,
) -> bool:
    if not _replacement_source_matches_resref(source_path, reference_label):
        return False
    return all(
        abs(float(source_bounds[corner][axis]) - float(reference_bounds[corner][axis])) <= tolerance
        for corner in (0, 1)
        for axis in (0, 1)
    )


def _replacement_source_matches_resref(source_path: str, reference_label: str) -> bool:
    label = _canonical_replacement_resref(reference_label)
    if not label:
        return False
    stem = _canonical_replacement_resref(Path(str(source_path or "")).stem)
    return bool(stem and (stem == label or stem.startswith(label)))


def _canonical_replacement_resref(value: str) -> str:
    text = str(value or "").strip().lower()
    for suffix in ("_basecolor", "_diffuse", "_albedo", "_uv", "_reuv"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text[:32]


def _mark_external_import(model: Any, source_path: str) -> None:
    """Tag external DCC meshes as temporary payloads, not export DAG authority.

    OBJ files are conventionally Z-up (matching KOTOR's coordinate system) and
    require identity rotation in the native-template fit path.  Without
    ``target_axis_system`` metadata the fit pipeline falls through to the
    creature-bounds heuristic which can mis-orient already-correct meshes.
    """
    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    try:
        from src.core.characters.character_rig_state import mark_imported_temporary_skeleton
    except ImportError:                                     # pragma: no cover
        from core.characters.character_rig_state import mark_imported_temporary_skeleton  # type: ignore
    mark_imported_temporary_skeleton(
        model,
        source="headless_body_workflow._mark_external_import",
    )
    external = dict(metadata.get("external_import") or {})
    external["source_path"] = str(source_path or external.get("source_path") or "")
    external.setdefault("disable_kotor_uv_seam_fix", True)
    # OBJ meshes are Z-up by convention and match KOTOR's coordinate system.
    # Tag the axis system so the native-template fit path uses identity
    # rotation instead of falling through to the creature-bounds heuristic.
    source_lower = str(source_path or "").lower()
    if source_lower.endswith(".obj") and "target_axis_system" not in external:
        external["source_axis_system"] = "obj_z_up"
        external["target_axis_system"] = "kotor_z_up"
        external["axis_conversion"] = "obj_z_up_to_kotor_z_up_identity"
    metadata["external_import"] = external
    for node in list(getattr(model, "all_nodes", lambda: [])() or []):
        if getattr(node, "vertices", None) and getattr(node, "uvs", None):
            setattr(node, "_external_imported", True)


def _connected_face_components(
    faces: Sequence[Sequence[int]],
    vertices: Sequence[Sequence[float]],
) -> List[List[int]]:
    """Return connected face islands, joined by welded vertex positions."""

    def vertex_key(index: int) -> Tuple[int, int, int]:
        try:
            point = vertices[index]
            return (
                int(round(float(point[0]) * 100000.0)),
                int(round(float(point[1]) * 100000.0)),
                int(round(float(point[2]) * 100000.0)),
            )
        except Exception:
            return (int(index), int(index), int(index))

    vertex_to_faces: Dict[Tuple[int, int, int], List[int]] = {}
    valid_faces: List[int] = []
    for face_index, face in enumerate(faces or []):
        if face is None or len(face) < 3:
            continue
        try:
            indices = [int(value) for value in face[:3]]
        except Exception:
            continue
        if len(set(indices)) < 3:
            continue
        valid_faces.append(face_index)
        for vertex_index in indices:
            vertex_to_faces.setdefault(vertex_key(vertex_index), []).append(face_index)

    remaining = set(valid_faces)
    components: List[List[int]] = []
    while remaining:
        start = remaining.pop()
        component = [start]
        stack = [start]
        while stack:
            current = stack.pop()
            for vertex_index in faces[current][:3]:
                for neighbor in vertex_to_faces.get(vertex_key(int(vertex_index)), []):
                    if neighbor not in remaining:
                        continue
                    remaining.remove(neighbor)
                    component.append(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def _split_mesh_node_by_components(node: Any) -> List[Any]:
    """Split one unskinned render node into connected component nodes."""

    faces = list(getattr(node, "faces", []) or [])
    vertices = list(getattr(node, "vertices", []) or [])
    if len(faces) < 2 or not vertices:
        return []
    if getattr(node, "skin_data", None) or getattr(node, "bone_map", None):
        return []

    components = _connected_face_components(faces, vertices)
    if len(components) <= 1:
        return []

    split_nodes: List[Any] = []
    base_name = str(getattr(node, "name", "") or "mesh").strip() or "mesh"
    normals = list(getattr(node, "normals", []) or [])
    tangents = list(getattr(node, "tangents", []) or [])
    uvs = list(getattr(node, "uvs", []) or [])
    face_uvs = list(getattr(node, "face_uvs", []) or [])
    face_mats = list(getattr(node, "face_mats", []) or [])

    for component_index, face_indices in enumerate(components, start=1):
        vertex_map: Dict[int, int] = {}
        uv_map: Dict[int, int] = {}
        new_vertices: List[Tuple[float, float, float]] = []
        new_normals: List[Tuple[float, float, float]] = []
        new_tangents: List[Tuple[float, float, float]] = []
        new_uvs: List[Tuple[float, float]] = []
        new_faces: List[Tuple[int, int, int]] = []
        new_face_uvs: List[Tuple[int, int, int]] = []
        new_face_mats: List[int] = []

        def map_vertex(old_index: int) -> int:
            if old_index in vertex_map:
                return vertex_map[old_index]
            new_index = len(new_vertices)
            vertex_map[old_index] = new_index
            new_vertices.append(vertices[old_index])
            if old_index < len(normals):
                new_normals.append(normals[old_index])
            if old_index < len(tangents):
                new_tangents.append(tangents[old_index])
            if not face_uvs and old_index < len(uvs):
                new_uvs.append(uvs[old_index])
            return new_index

        def map_uv(old_index: int) -> int:
            if old_index in uv_map:
                return uv_map[old_index]
            new_index = len(new_uvs)
            uv_map[old_index] = new_index
            new_uvs.append(uvs[old_index] if old_index < len(uvs) else (0.0, 0.0))
            return new_index

        for face_index in face_indices:
            face = faces[face_index]
            try:
                mapped_face = tuple(map_vertex(int(value)) for value in face[:3])
            except Exception:
                continue
            if len(set(mapped_face)) < 3:
                continue
            new_faces.append(mapped_face)  # type: ignore[arg-type]
            if face_index < len(face_uvs):
                fu = face_uvs[face_index]
                try:
                    new_face_uvs.append(tuple(map_uv(int(value)) for value in fu[:3]))  # type: ignore[arg-type]
                except Exception:
                    new_face_uvs.append((0, 0, 0))
            if face_index < len(face_mats):
                try:
                    new_face_mats.append(int(face_mats[face_index]))
                except Exception:
                    new_face_mats.append(0)

        if not new_faces:
            continue
        split_node = copy.deepcopy(node)
        split_node.name = f"{base_name}_part{component_index:02d}"
        split_node.parent = getattr(node, "parent", None)
        split_node.children = []
        split_node.vertices = new_vertices
        split_node.normals = new_normals
        split_node.tangents = new_tangents
        split_node.uvs = new_uvs
        split_node.face_uvs = new_face_uvs
        split_node.faces = new_faces
        split_node.face_mats = new_face_mats
        split_node.skin_data = []
        split_node.bone_map = []
        setattr(split_node, "_external_imported", True)
        setattr(split_node, "_gr_node_splitter_component", True)
        try:
            split_node.compute_bounds()
        except Exception:
            pass
        split_nodes.append(split_node)
    return split_nodes


def split_imported_mesh_nodes(scene: Any) -> Dict[str, Any]:
    """Split imported unskinned mesh nodes into connected render islands."""

    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEADLESS_BODY) if scene is not None else None
    model = getattr(entry, "model", None) if entry is not None else None
    if model is None:
        return {
            "ok": False,
            "code": "no_body_mesh",
            "message": "Load a custom mesh before using Node Splitter.",
            "split_nodes": 0,
        }

    candidates = [
        node for node in _iter_model_nodes(model)
        if getattr(node, "vertices", None) and getattr(node, "faces", None)
    ]
    split_source_count = 0
    split_node_count = 0
    skipped_skinned = 0
    for node in list(candidates):
        if getattr(node, "skin_data", None) or getattr(node, "bone_map", None):
            skipped_skinned += 1
            continue
        parts = _split_mesh_node_by_components(node)
        if not parts:
            continue
        split_source_count += 1
        split_node_count += len(parts)
        parent = getattr(node, "parent", None)
        if parent is None and getattr(model, "root_node", None) is node:
            existing_children = list(getattr(node, "children", []) or [])
            for child in parts + existing_children:
                child.parent = node
            node.children = parts + existing_children
            node.vertices = []
            node.normals = []
            node.tangents = []
            node.uvs = []
            node.face_uvs = []
            node.faces = []
            node.face_mats = []
            node.skin_data = []
            node.bone_map = []
            node.name = f"{str(getattr(node, 'name', '') or 'mesh')}_parts"
            try:
                node.compute_bounds()
            except Exception:
                pass
            continue
        if parent is None:
            continue
        siblings = list(getattr(parent, "children", []) or [])
        try:
            index = siblings.index(node)
        except ValueError:
            index = len(siblings)
        for part in parts:
            part.parent = parent
        parent.children = siblings[:index] + parts + siblings[index + 1:]

    try:
        model.compute_bounds()
    except Exception:
        bounds = _vertex_bounds(model)
        if bounds is not None:
            model.bb_min, model.bb_max = bounds
    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    metadata["character_builder_node_splitter"] = {
        "source_nodes_split": split_source_count,
        "component_nodes_created": split_node_count,
        "skipped_skinned_nodes": skipped_skinned,
        "method": "connected_face_components",
    }

    if split_node_count:
        message = (
            f"Node Splitter separated {split_source_count} mesh node(s) into "
            f"{split_node_count} connected render node(s)."
        )
        return {
            "ok": True,
            "code": "split",
            "message": message,
            "split_nodes": split_node_count,
            "source_nodes": split_source_count,
            "skipped_skinned_nodes": skipped_skinned,
        }
    message = "Node Splitter found no unskinned multi-island mesh nodes to split."
    if skipped_skinned:
        message += f" Skipped {skipped_skinned} already-skinned node(s)."
    return {
        "ok": True,
        "code": "no_split_needed",
        "message": message,
        "split_nodes": 0,
        "source_nodes": 0,
        "skipped_skinned_nodes": skipped_skinned,
    }


def _load_utc(path: str, game_version: str) -> Optional[Any]:
    """Resolve a UTC's appearance and load the resulting body MDL.

    This is the ``creature_appearance.resolve_utc_appearance_from_library``
    path called out in the T501 acceptance criteria.  When the UTC
    resolves to a body resref, we try to load it from the configured
    KOTOR installation; if no installation library is set, we raise
    :class:`NotImplementedError` so the caller can fall back to a
    direct MDL pick.

    The ``creature_appearance`` import is deferred to inside this
    helper so test environments without PyKotor can still exercise the
    "no library configured" failure path without dragging the loader
    chain into the import graph.
    """
    if not os.path.isfile(path):
        return None
    # The full UTC → library → MDL chain depends on a configured
    # installation library that must be wired by the host application
    # (see knowledge_base/qt_workflows.md for the contract).  Surface a
    # clear NotImplementedError so the Qt window can offer a direct
    # body-MDL file picker as the fallback.
    raise NotImplementedError(
        "UTC-driven load requires a configured KOTOR installation "
        "(creature_appearance.resolve_utc_appearance_from_library). "
        "Pick a body MDL directly for now."
    )


def _coerce_expected_character_mode(md: Any, scene: Any, expected_mode: Any = None) -> Any:
    raw = expected_mode
    if raw is None:
        raw = getattr(scene, "mode", None)
    try:
        if isinstance(raw, md.CharacterMode):
            mode = raw
        else:
            token = _mode_token(raw)
            if token:
                mode = md.CharacterMode(token)
            else:
                mode = md.CharacterMode.HEADLESS_BODY
    except Exception:
        mode = md.CharacterMode.HEADLESS_BODY
    if mode in {
        md.CharacterMode.AMBIGUOUS,
        md.CharacterMode.UNSUPPORTED,
        getattr(md.CharacterMode, "MODULE", object()),
    }:
        return md.CharacterMode.HEADLESS_BODY
    return mode


# ──────────────────────────────────────────────────────────────────────
#  T501 — Load Body
# ──────────────────────────────────────────────────────────────────────

def load_body(
    path: str,
    scene: Any,
    *,
    game_version: Optional[str] = None,
    allow_mode_correction: bool = False,
    fit_reference_model: Optional[Any] = None,
    fit_reference_label: str = "",
    fit_override: Optional[Any] = None,
    expected_mode: Optional[Any] = None,
) -> LoadResult:
    """Load a body model from *path* and assign it to *scene*.

    This is the entry point for **Workflow Step 1 (Load Body)** in the
    Mode-1 (Headless Body) workflow.  Acceptance per T501:

      * MDL path uses ``pykotor_bridge.load_model_from_file`` (which
        re-exports ``kotor_loader.load_model_from_file``);
      * UTC path resolves through ``creature_appearance``; if no library
        is configured the caller falls back to a direct MDL load;
      * glTF / GLB / FBX / OBJ / PLY paths use
        ``gltf_importer.auto_import``;
      * the result is unconditionally assigned to
        ``PartSlot.HEADLESS_BODY`` so the scene reflects user intent;
      * when the auto-detected mode is *not* HEADLESS_BODY, the result
        is flagged ``ok=False`` (``code="mode_mismatch"``) so the UI
        can show a correction banner.  When
        ``allow_mode_correction=True`` the caller is responsible for
        switching the scene's mode; the slot is still populated either
        way so the user can see what they loaded.

    Parameters
    ----------
    path                  : Absolute path to the source file.
    scene                 : A :class:`CharacterScene` instance.  The
                            scene's slot dict is mutated in place.
    game_version          : ``"K1"`` or ``"K2"``.  Defaults to
                            ``scene.game_version``.
    allow_mode_correction : When True, a mode mismatch is *not* a
                            failure — the slot is assigned and the
                            caller can react to ``detected_mode``.
    fit_reference_model   : Optional real KOTOR model/skeleton chosen by
                            the user before import.  External meshes are
                            scaled/oriented to this reference instead of a
                            generic humanoid fallback.
    """
    if not path:
        return LoadResult(message="No file path given.", code="empty_path")
    if not os.path.isfile(path):
        return LoadResult(
            source_path=path,
            message=f"File not found: {path}",
            code="file_not_found",
        )

    md = _import_model_data()
    gv = (game_version or getattr(scene, "game_version", "K1") or "K1").upper()
    expected = _coerce_expected_character_mode(md, scene, expected_mode)
    expected_label = getattr(expected, "display_name", str(expected))
    ext = _ext_of(path)

    # ── Dispatch ────────────────────────────────────────────────────
    try:
        if ext in _MDL_EXTS:
            model = _load_mdl(path, gv)
        elif ext in _GLTF_EXTS or ext in _FBX_EXTS:
            model = _load_gltf_or_mesh(path, gv)
        elif ext in _UTC_EXTS:
            model = _load_utc(path, gv)
        else:
            return LoadResult(
                source_path=path,
                message=f"Unsupported format: {ext or '(no extension)'}",
                code="unsupported_format",
            )
    except NotImplementedError as exc:
        return LoadResult(
            source_path=path,
            message=str(exc),
            code="load_failed",
        )
    except Exception as exc:                                # pragma: no cover - loader-specific
        log.exception("load_body: importer raised on %s", path)
        return LoadResult(
            source_path=path,
            message=f"Load failed: {exc}",
            code="load_failed",
        )

    if model is None:
        return LoadResult(
            source_path=path,
            message="Importer returned no model.",
            code="load_failed",
        )

    normalization: Dict[str, Any] = {}
    if ext in _GLTF_EXTS or ext in _FBX_EXTS:
        _mark_external_import(model, path)
        normalization = normalize_external_model_for_kotor(
            model,
            game_version=gv,
            reference_model=fit_reference_model,
            reference_label=fit_reference_label,
            fit_override=fit_override,
            expected_mode=expected,
        )

    # ── Detect mode ─────────────────────────────────────────────────
    try:
        detected = md.detect_character_mode(model)
    except Exception:                                       # pragma: no cover
        detected = md.CharacterMode.AMBIGUOUS

    # ── Assign to scene ─────────────────────────────────────────────
    resref = _resref_from_path(path)
    scene.assign(
        md.PartSlot.HEADLESS_BODY, model,
        resref=resref,
        game_version=gv,
        source_path=path,
    )

    # ── Verdict ─────────────────────────────────────────────────────
    if detected == expected:
        loaded_label = getattr(expected, "display_name", str(expected)).lower()
        return LoadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=f"Loaded {loaded_label}: {resref} ({Path(path).name})",
            code="loaded",
        )

    # Custom OBJ/FBX/glTF bodies often arrive from Blender without KOTOR hook
    # names yet.  That is exactly the M12 skeleton-template workflow: load the
    # external mesh first, then let the user apply a known-good KOTOR skeleton.
    if detected == md.CharacterMode.AMBIGUOUS and (ext in _GLTF_EXTS or ext in _FBX_EXTS):
        scale_msg = ""
        if normalization.get("ok"):
            scale_msg = (
                f" Fit to {normalization.get('reference') or 'KOTOR scale'} "
                f"({float(normalization.get('scale', 1.0)):.3f}x)."
            )
        return LoadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=(
                f"Loaded external mesh: {resref} ({Path(path).name}). "
                "Choose a KOTOR base skeleton before rigging."
                f"{scale_msg}"
            ),
            code="loaded",
        )

    # Mode mismatch — surface the suggested mode so the UI can offer to
    # switch.  When the caller opted into mode correction, we treat the
    # load as successful (the scene already has the slot assigned).
    suggest = getattr(detected, "display_name", str(detected))
    msg = (f"Loaded {Path(path).name}, but it looks like a {suggest} model "
           f"(expected {expected_label}).")
    return LoadResult(
        ok=allow_mode_correction,
        model=model, detected_mode=detected,
        source_path=path, resref=resref,
        message=msg,
        code="loaded" if allow_mode_correction else "mode_mismatch",
    )


# ──────────────────────────────────────────────────────────────────────
#  T502 — Check Model
# ──────────────────────────────────────────────────────────────────────
#
# Wraps the existing :class:`ValidationService` and projects its
# findings into a banner-ready ``CheckModelResult``.  The acceptance
# criterion is "all 10 issue codes surface correctly":
#
#   1.  NO_GEOMETRY             — model has no mesh nodes
#   2.  K1_K2_MISMATCH          — slots belong to different game versions
#   3.  SUPERMODEL_MISMATCH     — slot supermodels disagree
#   4.  SUPERMODEL_UNKNOWN      — supermodel string not in known list
#   5.  HOOK_MISSING            — headhook / rhand / talkdummy absent
#   6.  BONE_MISSING            — expected bone (e.g. lshoulder) absent
#   7.  SKIN_MESH_UNRIGGED      — mesh has no skin_data
#   8.  WEIGHT_OVERFLOW         — vertex has > 4 influences
#   9.  WEIGHT_ZERO_SUM         — vertex weights sum to 0
#  10.  WEIGHT_UNNORMALIZED     — weights don't sum to 1.0
#
# (WEIGHT_ERRORS_TRUNCATED is an INFO-severity summary, not a finding.)

# Severity → banner key mapping consumed by the Qt bottom-strip's
# ``set_validation(severity, summary, issues)`` API.
_BANNER_KEY_FOR_SEVERITY = {
    "error":   "error",
    "warning": "warning",
    "info":    "info",
}


@dataclass
class CheckModelResult:
    """Result of :func:`check_model`.

    Attributes
    ----------
    ok          : True when no ERROR-severity issues were found.  WARNINGs
                  do not flip this False (the export step gates on its own
                  re-validation).
    issues      : Full list of :class:`ValidationIssue` instances.
    banner_key  : Banner severity tag — one of ``"clean" / "info" /
                  "warning" / "error"``.
    summary     : Short banner text, e.g. ``"3 errors, 2 warnings"``.
    error_count / warning_count / info_count : Per-severity tallies.
    codes       : ``set[str]`` of distinct issue codes found
                  (handy for tests that assert which checks fired).
    """
    ok:            bool                                  = True
    issues:        List[Any]                             = field(default_factory=list)
    banner_key:    str                                   = "clean"
    summary:       str                                   = "CLEAN"
    error_count:   int                                   = 0
    warning_count: int                                   = 0
    info_count:    int                                   = 0
    codes:         set                                   = field(default_factory=set)


def _summarize_issues(issues: List[Any]) -> Tuple[str, str, int, int, int, set]:
    """Reduce a list of ValidationIssues into a banner-ready tuple.

    Returns ``(banner_key, summary, errors, warnings, infos, codes)``.
    """
    errs = warns = infos = 0
    codes: set = set()
    for issue in issues:
        sev = getattr(issue, "severity", None)
        sev_value = getattr(sev, "value", str(sev)).lower()
        if sev_value == "error":
            errs += 1
        elif sev_value == "warning":
            warns += 1
        elif sev_value == "info":
            infos += 1
        code = getattr(issue, "code", "")
        if code:
            codes.add(code)

    if errs:
        key = "error"
    elif warns:
        key = "warning"
    elif infos:
        key = "info"
    else:
        key = "clean"

    parts: List[str] = []
    if errs:
        parts.append(f"{errs} error{'s' if errs != 1 else ''}")
    if warns:
        parts.append(f"{warns} warning{'s' if warns != 1 else ''}")
    if infos and not (errs or warns):
        parts.append(f"{infos} info")
    summary = ", ".join(parts).upper() if parts else "CLEAN"

    return key, summary, errs, warns, infos, codes


def check_model(scene: Any, *, strict: bool = False) -> CheckModelResult:
    """Workflow Step 2 (Check Model) — M5 / T502.

    Runs :class:`ValidationService` over *scene* and reduces the
    resulting issue list to a banner-friendly summary.  The Qt window
    calls this from ``_on_check_model_requested`` and pushes the
    result straight into ``bottom_strip.set_validation(...)``.

    Parameters
    ----------
    scene  : :class:`CharacterScene` to validate.
    strict : When True, several WARNINGs are promoted to ERRORs (passed
             through to ``ValidationService(strict=...)``).
    """
    # Defensive: an empty scene yields no issues but isn't really
    # 'clean' from the user's perspective.  Surface that explicitly.
    if scene is None or not getattr(scene, "slots", None):
        return CheckModelResult(
            ok=False,
            issues=[],
            banner_key="warning",
            summary="NO MODEL LOADED",
        )

    try:
        vs_mod = _import_validation_service()
        service = vs_mod.ValidationService(scene, strict=strict)
        issues = service.validate()
    except Exception as exc:                                # pragma: no cover
        log.exception("check_model: ValidationService raised")
        return CheckModelResult(
            ok=False,
            issues=[],
            banner_key="error",
            summary=f"CHECK FAILED: {exc}",
        )

    key, summary, errs, warns, infos, codes = _summarize_issues(issues)
    return CheckModelResult(
        ok=(errs == 0),
        issues=issues,
        banner_key=key,
        summary=summary,
        error_count=errs,
        warning_count=warns,
        info_count=infos,
        codes=codes,
    )


# ──────────────────────────────────────────────────────────────────────
#  T503 — Body Rig
# ──────────────────────────────────────────────────────────────────────
#
# Step 3 of the Headless-Body workflow places AcuRig guide pins for
# the humanoid profile, lets the user nudge them via the joint-dot
# HUD (M4 / T402), then generates the skeleton + heat-map weights.
#
# The service module owns only the *headless* business logic.  The
# Qt window is responsible for binding the guide-drag UX to T402's
# hit-tester / mirror logic and forwarding the final guide dict back
# here for skeleton generation.

def _import_accurig():                                      # pragma: no cover - import shim
    try:
        from src.autorig import accurig as _ar             # type: ignore
    except ImportError:
        from autorig import accurig as _ar                 # type: ignore
    return _ar


@dataclass
class BodyRigGuidesResult:
    """Result of :func:`place_body_guides`.

    Attributes
    ----------
    ok          : True when guides were successfully placed.
    guides      : ``Dict[str, RigGuide]`` keyed by joint name
                  (root / hip / chest / lshoulder / rshoulder / …).
    profile     : The detected/used AcuRig profile (``"humanoid"``).
    acurig      : The :class:`AcuRig` instance — kept on the result so
                  the caller can forward it back to
                  :func:`generate_skeleton` (avoids re-running profile
                  detection a second time).
    message     : Human-readable summary for the status bar.
    """
    ok:       bool                                   = False
    guides:   Dict[str, Any]                         = field(default_factory=dict)
    profile:  str                                    = ""
    acurig:   Optional[Any]                          = None
    message:  str                                    = ""


@dataclass
class BodyRigGenerateResult:
    """Result of :func:`generate_skeleton`.

    Attributes
    ----------
    ok                : True when build + skin succeeded.
    bone_count        : Number of bones in the generated skeleton.
    vertices_skinned  : Total vertex count that received heat-map
                        weights.
    message           : Human-readable summary.
    code              : Stable tag — ``"generated" / "no_body" /
                        "no_guides" / "build_failed" / "skin_failed"``.
    """
    ok:                bool       = False
    bone_count:        int        = 0
    vertices_skinned:  int        = 0
    message:           str        = ""
    code:              str        = "generated"
    weighting_method:  str        = ""


@dataclass
class BodyGuideEditResult:
    """Result of persisting a manual HUD joint/guide edit (M12/T1203)."""

    ok:             bool           = False
    guide_name:     str            = ""
    position:       Tuple[float, float, float] = (0.0, 0.0, 0.0)
    guides:         Dict[str, Any] = field(default_factory=dict)
    acurig:         Optional[Any]  = None
    updated_guides: List[str]      = field(default_factory=list)
    before_positions: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    after_positions:  Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    can_undo:      bool           = False
    can_redo:      bool           = False
    message:        str            = ""
    code:           str            = "updated"


@dataclass
class BodyGuideEditCommand:
    """One undoable body-guide edit command."""

    guide_name: str = ""
    before: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    after:  Dict[str, Tuple[float, float, float]] = field(default_factory=dict)


@dataclass
class BodyGuideEditHistory:
    """Undo/redo stack for AccuRig guide edits."""

    undo_stack: List[BodyGuideEditCommand] = field(default_factory=list)
    redo_stack: List[BodyGuideEditCommand] = field(default_factory=list)
    limit: int = 50

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)


def _get_body_model(scene: Any) -> Optional[Any]:
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEADLESS_BODY)


def _get_head_model(scene: Any) -> Optional[Any]:
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEAD_SHELL)


def _coerce_position3(position: Any) -> Optional[Tuple[float, float, float]]:
    try:
        values = tuple(position)
    except Exception:
        return None
    if len(values) < 3:
        return None
    try:
        return (float(values[0]), float(values[1]), float(values[2]))
    except (TypeError, ValueError):
        return None


def _snapshot_guide_positions(guides: Dict[str, Any]) -> Dict[str, Tuple[float, float, float]]:
    positions: Dict[str, Tuple[float, float, float]] = {}
    for name, guide in (guides or {}).items():
        pos = _coerce_position3(getattr(guide, "position", None))
        if pos is not None:
            positions[str(name)] = pos
    return positions


def _history_flags(history: Optional[BodyGuideEditHistory]) -> Tuple[bool, bool]:
    if history is None:
        return False, False
    return bool(history.can_undo), bool(history.can_redo)


def update_body_guide(
    acurig: Any,
    guide_name: str,
    position: Any,
    *,
    auto_mirror: bool = False,
) -> BodyGuideEditResult:
    """Persist a manual body guide edit into the live AcuRig instance.

    T1203's UX rule is simple: when a user drags an AccuRig-style
    joint dot, the next :func:`generate_skeleton` call must use that
    position.  AcuRig already models this via ``move_guide`` +
    ``locked=True``; this adapter normalizes names/positions and
    returns a status object that the Qt layer can surface.
    """
    name = (guide_name or "").strip().lower()
    if acurig is None:
        return BodyGuideEditResult(
            guide_name=name,
            message="No AcuRig guide state yet. Click Place Body Guides first.",
            code="no_acurig",
        )
    if not name:
        return BodyGuideEditResult(
            acurig=acurig,
            message="No guide name supplied.",
            code="no_name",
        )

    pos = _coerce_position3(position)
    if pos is None:
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            message=f"Guide '{name}' has no valid 3D position.",
            code="bad_position",
        )

    before = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            before = dict(acurig.get_all_guides() or {})
        except Exception:
            before = {}
    if before and name not in before:
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            position=pos,
            guides=before,
            message=f"'{name}' is not a body guide for the current AcuRig profile.",
            code="unknown_guide",
        )
    before_positions = {
        gname: getattr(guide, "position", None)
        for gname, guide in before.items()
    }
    before_snapshot = _snapshot_guide_positions(before)

    try:
        if hasattr(acurig, "move_guide"):
            acurig.move_guide(name, pos, auto_mirror=auto_mirror)
        elif before and name in before:                    # pragma: no cover
            guide = before[name]
            guide.position = pos
            guide.locked = True
        else:                                              # pragma: no cover
            return BodyGuideEditResult(
                acurig=acurig,
                guide_name=name,
                position=pos,
                message="AcuRig guide state does not support manual edits.",
                code="unsupported",
            )
    except Exception as exc:                               # pragma: no cover
        log.exception("update_body_guide: AcuRig guide update failed")
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            position=pos,
            message=f"Guide update failed: {exc}",
            code="failed",
        )

    after = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            after = dict(acurig.get_all_guides() or {})
        except Exception:                                  # pragma: no cover
            after = {}

    changed: List[str] = []
    for gname, guide in after.items():
        old_pos = before_positions.get(gname)
        new_pos = getattr(guide, "position", None)
        if gname not in before_positions or old_pos != new_pos:
            changed.append(str(gname))
    if name not in changed:
        changed.insert(0, name)
    after_snapshot_all = _snapshot_guide_positions(after)
    before_changed = {
        gname: before_snapshot[gname]
        for gname in changed
        if gname in before_snapshot
    }
    after_changed = {
        gname: after_snapshot_all[gname]
        for gname in changed
        if gname in after_snapshot_all
    }

    return BodyGuideEditResult(
        ok=True,
        acurig=acurig,
        guide_name=name,
        position=pos,
        guides=after,
        updated_guides=changed,
        before_positions=before_changed,
        after_positions=after_changed,
        message=f"Guide '{name}' locked at ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}).",
        code="updated",
    )


def update_body_guide_from_node(
    acurig: Any,
    node: Any,
    *,
    auto_mirror: bool = False,
) -> BodyGuideEditResult:
    """Persist a moved viewport node as an AcuRig guide edit."""
    name = getattr(node, "name", "") or ""
    position = getattr(node, "position", None)
    return update_body_guide(
        acurig,
        str(name),
        position,
        auto_mirror=auto_mirror,
    )


def record_body_guide_edit(
    history: Optional[BodyGuideEditHistory],
    result: BodyGuideEditResult,
) -> BodyGuideEditHistory:
    """Record a successful guide edit as an undoable command."""
    if history is None:
        history = BodyGuideEditHistory()
    if not getattr(result, "ok", False):
        return history
    before = dict(getattr(result, "before_positions", {}) or {})
    after = dict(getattr(result, "after_positions", {}) or {})
    if not before or not after or before == after:
        return history
    history.undo_stack.append(BodyGuideEditCommand(
        guide_name=getattr(result, "guide_name", ""),
        before=before,
        after=after,
    ))
    history.redo_stack.clear()
    if history.limit > 0 and len(history.undo_stack) > history.limit:
        del history.undo_stack[0:len(history.undo_stack) - history.limit]
    return history


def apply_body_guide_positions(
    acurig: Any,
    positions: Dict[str, Any],
) -> BodyGuideEditResult:
    """Apply exact guide positions without auto-mirroring."""
    if acurig is None:
        return BodyGuideEditResult(
            message="No AcuRig guide state yet. Click Place Body Guides first.",
            code="no_acurig",
        )
    normalized: Dict[str, Tuple[float, float, float]] = {}
    for name, pos in (positions or {}).items():
        coerced = _coerce_position3(pos)
        if coerced is not None:
            normalized[str(name).lower()] = coerced
    if not normalized:
        return BodyGuideEditResult(
            acurig=acurig,
            message="No guide positions supplied.",
            code="no_positions",
        )

    before = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            before = dict(acurig.get_all_guides() or {})
        except Exception:
            before = {}
    before_snapshot = _snapshot_guide_positions(before)

    try:
        for name, pos in normalized.items():
            if hasattr(acurig, "move_guide"):
                acurig.move_guide(name, pos, auto_mirror=False)
            elif before and name in before:                # pragma: no cover
                before[name].position = pos
                before[name].locked = True
            else:                                          # pragma: no cover
                return BodyGuideEditResult(
                    acurig=acurig,
                    guide_name=name,
                    position=pos,
                    message="AcuRig guide state does not support manual edits.",
                    code="unsupported",
                )
    except Exception as exc:                               # pragma: no cover
        log.exception("apply_body_guide_positions: AcuRig guide update failed")
        return BodyGuideEditResult(
            acurig=acurig,
            message=f"Guide position apply failed: {exc}",
            code="failed",
        )

    after = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            after = dict(acurig.get_all_guides() or {})
        except Exception:
            after = {}
    after_snapshot = _snapshot_guide_positions(after)
    updated = [
        name for name, pos in normalized.items()
        if before_snapshot.get(name) != after_snapshot.get(name)
    ] or list(normalized.keys())
    return BodyGuideEditResult(
        ok=True,
        acurig=acurig,
        guide_name=updated[0] if updated else "",
        position=normalized.get(updated[0], (0.0, 0.0, 0.0)) if updated else (0.0, 0.0, 0.0),
        guides=after,
        updated_guides=updated,
        before_positions={k: before_snapshot[k] for k in updated if k in before_snapshot},
        after_positions={k: after_snapshot[k] for k in updated if k in after_snapshot},
        message=f"Applied {len(updated)} guide position(s).",
        code="applied",
    )


def undo_body_guide_edit(
    acurig: Any,
    history: Optional[BodyGuideEditHistory],
) -> BodyGuideEditResult:
    """Undo the latest recorded body guide edit."""
    can_undo, can_redo = _history_flags(history)
    if history is None or not can_undo:
        return BodyGuideEditResult(
            acurig=acurig,
            can_undo=False,
            can_redo=can_redo,
            message="No guide edit to undo.",
            code="no_undo",
        )
    command = history.undo_stack.pop()
    result = apply_body_guide_positions(acurig, command.before)
    if not result.ok:
        history.undo_stack.append(command)
        result.can_undo = history.can_undo
        result.can_redo = history.can_redo
        return result
    history.redo_stack.append(command)
    result.guide_name = command.guide_name
    result.can_undo = history.can_undo
    result.can_redo = history.can_redo
    result.message = f"Undid guide edit: {command.guide_name}."
    result.code = "undone"
    return result


def redo_body_guide_edit(
    acurig: Any,
    history: Optional[BodyGuideEditHistory],
) -> BodyGuideEditResult:
    """Redo the latest undone body guide edit."""
    can_undo, can_redo = _history_flags(history)
    if history is None or not can_redo:
        return BodyGuideEditResult(
            acurig=acurig,
            can_undo=can_undo,
            can_redo=False,
            message="No guide edit to redo.",
            code="no_redo",
        )
    command = history.redo_stack.pop()
    result = apply_body_guide_positions(acurig, command.after)
    if not result.ok:
        history.redo_stack.append(command)
        result.can_undo = history.can_undo
        result.can_redo = history.can_redo
        return result
    history.undo_stack.append(command)
    result.guide_name = command.guide_name
    result.can_undo = history.can_undo
    result.can_redo = history.can_redo
    result.message = f"Redid guide edit: {command.guide_name}."
    result.code = "redone"
    return result


def place_body_guides(
    scene: Any,
    *,
    snap_to_bones: bool = True,
    acurig: Optional[Any] = None,
) -> BodyRigGuidesResult:
    """Workflow Step 3a — place AcuRig humanoid guides on the body.

    Wraps ``AcuRig.place_guides(model, profile=PROFILE_HUMANOID)``.
    Acceptance per T503: "guides snap to existing bones when present;
    otherwise sit at canonical humanoid-template positions scaled to
    the model's height".

    Parameters
    ----------
    scene          : :class:`CharacterScene` that must already have a
                     ``PartSlot.HEADLESS_BODY`` slot assigned.
    snap_to_bones  : Forwarded to ``AcuRig.place_guides``.  When True,
                     each guide auto-snaps to the nearest existing bone
                     within the configured radius (improves accuracy
                     on models that already have a rough skeleton).
    acurig         : Optional existing :class:`AcuRig` instance.  Pass
                     this in on subsequent calls to keep user-locked
                     guide overrides between the *Place Guides* and
                     *Generate Skeleton* clicks.
    """
    body = _get_body_model(scene)
    if body is None:
        return BodyRigGuidesResult(
            message="No body model loaded.  Load a body first.",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return BodyRigGuidesResult(
            message=f"AcuRig module unavailable: {exc}",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()

    profile = ar_mod.PROFILE_HUMANOID
    try:
        guides = acurig.place_guides(body, profile=profile,
                                     snap_to_bones=snap_to_bones)
    except Exception as exc:                                # pragma: no cover
        log.exception("place_body_guides: AcuRig.place_guides raised")
        return BodyRigGuidesResult(
            message=f"Guide placement failed: {exc}",
        )

    return BodyRigGuidesResult(
        ok=True,
        guides=guides,
        profile=profile,
        acurig=acurig,
        message=f"Placed {len(guides)} humanoid guide(s).",
    )


def _compute_heat_diffusion_skin_weights(
    model: Any,
    *,
    max_influence_distance: float = 5.0,
    diffusion_iterations: int = 5,
    falloff: float = 2.0,
    max_bones_per_vertex: int = 4,
) -> Dict[str, Any]:
    """Paint skin weights on ``model``'s mesh nodes via inverse-distance
    heat diffusion.

    This is the Character Builder's opt-in alternative to the nearest-bone
    fallback.  It walks the rigged model, gathers each skeleton bone's
    world position, then for every mesh node diffuses bone influence
    across the vertex adjacency graph and writes back ``skin_data`` /
    ``bone_weights`` / ``bone_indices`` in the same contract the export
    pipeline expects: one ``VertexSkinData`` row per vertex with <=4
    normalised influences that sum to 1.0.

    (Character Builder principle: "Normalize, cap, and audit influences
    after every remap or smoothing pass."  Heat diffusion produces a
    smoother ownership map than a hard nearest-bone assignment, but it is
    still a *baseline* — joint/twist areas should be range-of-motion
    checked before export.)

    Returns a report dict with ``ok``, ``vertices_skinned``,
    ``mesh_count``, ``method`` and a ``message``.
    """
    report: Dict[str, Any] = {
        "ok": False,
        "method": "heat_diffusion",
        "vertices_skinned": 0,
        "mesh_count": 0,
        "message": "",
    }
    try:
        import numpy as np  # noqa: F401  (presence check)
        hd = _import_heat_diffusion()
        md = _import_model_data()
    except Exception as exc:                                 # pragma: no cover - deps missing
        report["message"] = f"Heat-diffusion deps unavailable: {exc}"
        return report

    VertexSkinData = md.VertexSkinData
    BoneWeight = md.BoneWeight

    nodes = _iter_model_nodes(model)
    if not nodes:
        report["message"] = "No model nodes available for heat diffusion."
        return report

    # Gather bone world positions from every non-mesh (skeleton) node.
    bone_positions: Dict[str, Tuple[float, float, float]] = {}
    for node in nodes:
        if getattr(node, "vertices", None):
            continue  # mesh node — not a bone
        name = str(getattr(node, "name", "") or "").strip()
        if not name:
            continue
        pos = _node_fit_position(node)
        if pos is None:
            continue
        bone_positions.setdefault(
            name, (float(pos[0]), float(pos[1]), float(pos[2]))
        )

    if not bone_positions:
        report["message"] = "No bone positions found for heat diffusion."
        return report

    total_skinned = 0
    mesh_count = 0
    for node in nodes:
        verts = list(getattr(node, "vertices", []) or [])
        if not verts:
            continue
        faces = list(getattr(node, "faces", []) or [])
        # Ensure the mesh has a bone map; derive one from the skeleton if
        # generate_rig / auto_skin did not already populate it.
        bone_map = list(getattr(node, "bone_map", []) or [])
        if not bone_map:
            bone_map = sorted(bone_positions.keys())
            try:
                node.bone_map = bone_map
            except Exception:
                pass
        slot_by_name = {str(n): i for i, n in enumerate(bone_map)}

        verts_arr = np.asarray(
            [
                [float(v[0]), float(v[1]), float(v[2])]
                for v in verts
                if len(v) >= 3
            ],
            dtype=np.float64,
        )
        if verts_arr.shape[0] == 0:
            continue

        # Prefer bones that are present in this mesh's bone_map so the
        # heat weights reference valid slot indices; fall back to the full
        # skeleton when the map is uninformative.
        mesh_bones = {
            bname: bone_positions[bname]
            for bname in bone_map
            if bname in bone_positions
        } or dict(bone_positions)

        try:
            heat = hd.compute_heat_diffusion_weights(
                verts_arr,
                faces,
                mesh_bones,
                max_influence_distance=max_influence_distance,
                diffusion_iterations=diffusion_iterations,
                falloff=falloff,
                max_bones_per_vertex=max_bones_per_vertex,
            )
        except Exception as exc:                             # pragma: no cover
            log.exception(
                "heat diffusion failed for mesh %r",
                getattr(node, "name", "?"),
            )
            report["message"] = f"Heat diffusion failed: {exc}"
            continue

        skin_rows = []
        bw_list = []
        bi_list = []
        for vi in range(int(verts_arr.shape[0])):
            row = heat.get(vi, {})
            influences = []
            for bname, w in row.items():
                slot = slot_by_name.get(str(bname))
                if slot is None:
                    continue
                influences.append(BoneWeight(bone_index=int(slot), weight=float(w)))
            # Sort by weight desc, cap to max_bones_per_vertex, renormalise
            # so the row still sums to 1.0 (KOTOR export contract).
            influences.sort(key=lambda bw: bw.weight, reverse=True)
            influences = influences[:max_bones_per_vertex]
            total = sum(bw.weight for bw in influences)
            if total > 0:
                for bw in influences:
                    bw.weight = bw.weight / total
            skin_rows.append(VertexSkinData(influences=influences))
            bw_list.append([bw.weight for bw in influences])
            bi_list.append([bw.bone_index for bw in influences])

        try:
            node.skin_data = skin_rows
            node.bone_weights = bw_list
            node.bone_indices = bi_list
        except Exception:                                    # pragma: no cover
            pass
        total_skinned += len(skin_rows)
        mesh_count += 1

    report["ok"] = mesh_count > 0
    report["vertices_skinned"] = total_skinned
    report["mesh_count"] = mesh_count
    report["message"] = (
        f"Heat-diffusion skinning: {total_skinned} vertex row(s) across "
        f"{mesh_count} mesh(es) using {len(bone_positions)} bone(s)."
    )
    return report


def generate_skeleton(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    guides: Optional[Dict[str, Any]] = None,
    smooth_iterations: int = 2,
    use_heat_diffusion_skinning: bool = False,
) -> BodyRigGenerateResult:
    """Workflow Step 3b — Generate Skeleton button.

    Runs ``AcuRig.generate_rig`` (== ``accurig.build_skeleton`` in the
    roadmap wording) and then ``AcuRig.auto_skin`` (== ``heat_weights``)
    to produce a fully-rigged, heat-painted body model.

    Parameters
    ----------
    scene             : Scene with the body slot populated.
    acurig            : The :class:`AcuRig` instance from
                        :func:`place_body_guides` — passing it through
                        preserves user-locked guide positions.  When
                        ``None``, a fresh instance is created.
    guides            : Optional explicit guide dict (e.g. mutated by
                        the joint-dot HUD's drag-with-mirror UX).
                        When ``None``, the AcuRig instance uses its
                        internal state.
    smooth_iterations : Number of heat-map smoothing passes
                        (forwarded to ``WeightPainter.smooth_weights``).
    use_heat_diffusion_skinning
                        Opt-in alternative skinning method.  When True
                        (or when the scene carries a matching metadata
                        flag), bone influence is diffused across the
                        mesh surface and overwrites the skin rows with
                        the smoother heat-diffusion distribution.  This
                        takes priority over the nearest-bone fallback
                        while leaving the donor-weight-transfer path
                        untouched.  Default False — existing behaviour
                        is unchanged.
    """
    body = _get_body_model(scene)
    if body is None:
        return BodyRigGenerateResult(
            message="No body model loaded.",
            code="no_body",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return BodyRigGenerateResult(
            message=f"AcuRig module unavailable: {exc}",
            code="build_failed",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()
        # Without prior place_guides, we need *some* guides.
        if not guides:
            try:
                guides = acurig.place_guides(body,
                                             profile=ar_mod.PROFILE_HUMANOID,
                                             snap_to_bones=True)
            except Exception as exc:                        # pragma: no cover
                return BodyRigGenerateResult(
                    message=f"Guide placement failed: {exc}",
                    code="no_guides",
                )

    # ── Build skeleton ──────────────────────────────────────────────
    # Snapshot the body before rigging so a skin-bind failure can roll
    # the scene back to a clean baseline.  AcuRig may mutate ``body``
    # in place during ``generate_rig`` (or the scene entry's ``model``
    # may already alias it), so a deep copy is the only safe restore
    # point.  (Skinning/Deformation skill: "Start from a known baseline
    # when repairing a broken bind.")
    pre_rig_model = copy.deepcopy(body)
    try:
        rigged = acurig.generate_rig(body, guides=guides)
    except Exception as exc:                                # pragma: no cover
        log.exception("generate_skeleton: generate_rig raised")
        return BodyRigGenerateResult(
            message=f"Skeleton build failed: {exc}",
            code="build_failed",
        )

    # Count bones in the active guide map (== the active mask).
    if guides is None:
        guides = acurig.get_all_guides() if hasattr(acurig, "get_all_guides") else {}
    bone_count = len(guides or {})

    # ── Heat-map skinning ───────────────────────────────────────────
    try:
        verts_skinned = acurig.auto_skin(
            rigged,
            guides=guides,
            smooth_iterations=smooth_iterations,
        )
    except Exception as exc:                                # pragma: no cover
        log.exception("generate_skeleton: auto_skin raised")
        # The skeleton built cleanly but skin binding failed.  Roll the
        # scene back to its pre-rig baseline so the user can fix the
        # weights/donor map and retry without a half-rigged model.  We
        # restore the deep-copied snapshot taken before ``generate_rig``
        # because ``body`` may have been mutated in place during rigging.
        md = _import_model_data()
        entry = scene.get(md.PartSlot.HEADLESS_BODY)
        if entry is not None and pre_rig_model is not None:
            entry.model = pre_rig_model
            entry.dirty = True
            scene.dirty = True
        return BodyRigGenerateResult(
            ok=False,
            bone_count=bone_count,
            message=(
                "Skeleton generation succeeded but skin binding failed "
                f"({exc}). The model has been restored to its pre-rig "
                "state. Check skin weights and donor compatibility."
            ),
            code="skin_failed",
        )

    # ── Optional heat-diffusion skinning ────────────────────────────
    # Opt-in alternative to the nearest-bone fallback (priority order:
    # donor weight transfer → heat diffusion → nearest-bone fallback).
    # When enabled, diffuse bone influence across the mesh surface and
    # overwrite the skin rows with the smoother heat-diffusion weights.
    # auto_skin still ran first as the safety baseline + bone-map setup,
    # so a heat-diffusion failure gracefully leaves the auto_skin result.
    # Safe to leave off — the existing auto_skin result is the default.
    weighting_method = "heat_map"
    hd_enabled = bool(use_heat_diffusion_skinning)
    if not hd_enabled:
        for _attr in ("metadata", "meta", "options"):
            _meta = getattr(scene, _attr, None)
            if isinstance(_meta, dict) and _meta.get("use_heat_diffusion_skinning"):
                hd_enabled = True
                break
    if hd_enabled and rigged is not None:
        try:
            hd_report = _compute_heat_diffusion_skin_weights(rigged)
        except Exception as exc:                             # pragma: no cover
            log.exception("generate_skeleton: heat-diffusion skinning raised")
            hd_report = {"ok": False, "message": str(exc),
                         "vertices_skinned": 0, "method": "heat_diffusion"}
        if hd_report.get("ok"):
            verts_skinned = hd_report.get("vertices_skinned", verts_skinned)
            weighting_method = hd_report.get("method", "heat_diffusion")
        else:
            log.warning(
                "generate_skeleton: heat-diffusion skinning did not apply "
                "(%s); keeping auto_skin result.",
                hd_report.get("message", "unknown"),
            )

    # Update the scene's slot.model in case generate_rig replaced it.
    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    if entry is not None and rigged is not None:
        entry.model = rigged
        entry.dirty = True
        scene.dirty = True

    return BodyRigGenerateResult(
        ok=True,
        bone_count=bone_count,
        vertices_skinned=int(verts_skinned or 0),
        message=(f"Generated skeleton with {bone_count} bone(s); "
                 f"skinned {verts_skinned} vertices."),
        code="generated",
        weighting_method=weighting_method,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  T504 ▸ Hand-Rig step
# ─────────────────────────────────────────────────────────────────────────────
#
# The KOTOR humanoid skeleton uses a single primary finger bone per hand
# (``lfinger01`` / ``rfinger01``), plus the wrist (``lhand`` / ``rhand``)
# and forearm (``lforearm`` / ``rforearm``).  T504's job is to expose
# those six bones in the inspector as per-bone mask checkboxes, so the
# user can mute weight-painting on any of them before kicking off the
# heat-map smoothing pass.
#
# Public surface:
#   • HAND_BONES                      — the six bones the UI shows.
#   • HandRigResult                   — structured result for both calls.
#   • place_hand_guides(scene, *)     — refresh the AcuRig hand guides.
#   • apply_hand_masks(scene, *)      — push the checkbox state into
#                                       ``AcuRig.mask`` (BoneMask).

HAND_BONES: Tuple[str, ...] = (
    "lforearm", "lhand", "lfinger01",
    "rforearm", "rhand", "rfinger01",
)


@dataclass
class HandRigResult:
    """Result of :func:`place_hand_guides` / :func:`apply_hand_masks`.

    Attributes
    ----------
    ok             : True when the operation completed cleanly.
    guides         : ``Dict[str, RigGuide]`` for the six hand bones —
                     empty when ``ok is False``.
    masked_bones   : Sorted list of bone names currently masked on the
                     AcuRig instance.  Mirrors the checkbox state.
    acurig         : The :class:`AcuRig` instance — preserved so the
                     window can pass it back on the next call without
                     re-running profile detection.
    message        : Human-readable summary for the status bar.
    code           : Stable tag — ``"placed" / "masked" / "no_body" /
                     "no_acurig" / "failed"``.
    """
    ok:           bool                                   = False
    guides:       Dict[str, Any]                         = field(default_factory=dict)
    masked_bones: List[str]                              = field(default_factory=list)
    acurig:       Optional[Any]                          = None
    message:      str                                    = ""
    code:         str                                    = "placed"


def place_hand_guides(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    snap_to_bones: bool = True,
) -> HandRigResult:
    """Workflow Step 4a — refresh AcuRig humanoid guides and isolate the hand subset.

    Re-runs ``AcuRig.place_guides`` so the wrist / finger pins re-snap
    to the latest bone positions (useful after the body skeleton has
    been generated and the user wants to fine-tune hands separately).
    Returns only the six hand-relevant guides for the inspector to
    drive.
    """
    body = _get_body_model(scene)
    if body is None:
        return HandRigResult(
            message="No body model loaded.  Load a body first.",
            code="no_body",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return HandRigResult(
            message=f"AcuRig module unavailable: {exc}",
            code="no_acurig",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()

    try:
        all_guides = acurig.place_guides(
            body,
            profile=ar_mod.PROFILE_HUMANOID,
            snap_to_bones=snap_to_bones,
        )
    except Exception as exc:                                # pragma: no cover
        log.exception("place_hand_guides: AcuRig.place_guides raised")
        return HandRigResult(
            message=f"Hand-guide placement failed: {exc}",
            code="failed",
        )

    hand_guides = {
        name: guide for name, guide in (all_guides or {}).items()
        if name in HAND_BONES
    }
    # Surface whatever mask state the AcuRig already has — the UI uses
    # this to pre-populate its checkboxes on first paint.
    masked = _read_masked_bones(acurig)

    return HandRigResult(
        ok=True,
        guides=hand_guides,
        masked_bones=masked,
        acurig=acurig,
        message=(f"Placed {len(hand_guides)} hand-rig guide(s); "
                 f"{len(masked)} bone(s) currently masked."),
        code="placed",
    )


def apply_hand_masks(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    masked_bones: Optional[List[str]] = None,
) -> HandRigResult:
    """Workflow Step 4b — push the per-bone mask checkbox state into AcuRig.

    Clears the AcuRig's :class:`BoneMask` and re-applies exactly the
    bones listed in ``masked_bones``.  Only bones in :data:`HAND_BONES`
    are accepted (the body-level mask is owned by :func:`generate_skeleton`,
    not this step).

    Parameters
    ----------
    scene         : Scene whose body slot must be populated.
    acurig        : Required.  Reuse the instance from
                    :func:`place_hand_guides` so the mask survives
                    between checkbox toggles.
    masked_bones  : Iterable of bone names to mask.  Anything outside
                    :data:`HAND_BONES` is silently ignored.
    """
    body = _get_body_model(scene)
    if body is None:
        return HandRigResult(
            message="No body model loaded.",
            code="no_body",
        )

    if acurig is None:
        return HandRigResult(
            message="No AcuRig instance — click Place Hand Guides first.",
            code="no_acurig",
        )

    mask = getattr(acurig, "mask", None)
    if mask is None:                                        # pragma: no cover
        return HandRigResult(
            message="AcuRig has no BoneMask attribute.",
            code="failed",
        )

    requested = [b for b in (masked_bones or []) if b in HAND_BONES]

    try:
        # Non-hand bones (e.g. user previously masked the tail) must be
        # preserved — so only re-key the hand subset.
        for bone in HAND_BONES:
            if hasattr(mask, "is_masked") and mask.is_masked(bone) \
                    and bone not in requested:
                if hasattr(mask, "unmask"):
                    mask.unmask(bone)
                else:                                       # fallback for
                    # older BoneMask without ``unmask``: clear + re-apply
                    # the full intended set.
                    if hasattr(mask, "clear"):
                        mask.clear()
                    for b in requested:
                        mask.mask(b)
                    break
        for bone in requested:
            if not (hasattr(mask, "is_masked") and mask.is_masked(bone)):
                mask.mask(bone)
    except Exception as exc:                                # pragma: no cover
        log.exception("apply_hand_masks: mask manipulation raised")
        return HandRigResult(
            message=f"Failed to apply hand masks: {exc}",
            code="failed",
            acurig=acurig,
        )

    masked = _read_masked_bones(acurig)
    return HandRigResult(
        ok=True,
        guides={},                                          # caller still has them
        masked_bones=masked,
        acurig=acurig,
        message=(f"Hand masks updated — {len(masked)} bone(s) currently masked."),
        code="masked",
    )


def _read_masked_bones(acurig: Any) -> List[str]:
    """Best-effort accessor for ``AcuRig.mask.masked_bones``."""
    mask = getattr(acurig, "mask", None)
    if mask is None:                                        # pragma: no cover
        return []
    bones = getattr(mask, "masked_bones", None)
    if callable(bones):
        try:
            bones = bones()
        except Exception:                                   # pragma: no cover
            return []
    if bones is None:                                       # pragma: no cover
        return []
    return sorted(str(b) for b in bones)


# ─────────────────────────────────────────────────────────────────────────────
#  T505 ▸ Check-Actor step
# ─────────────────────────────────────────────────────────────────────────────
#
# The Check-Actor step lets the user preview a small, curated set of
# preview animations on the rigged body — walk / idle / talk — to
# verify the skeleton + heat-map weights look right under motion.
# These names come from the canonical KOTOR humanoid animation list
# (``template_builder._ANIM_SLOTS``).
#
# Public surface:
#   • PREVIEW_ANIMATIONS              — short tuple of (label, anim_name).
#   • CheckActorResult                — structured result for both calls.
#   • available_preview_animations()  — which previews exist on the model.
#   • play_preview_animation()        — look up the named anim + dispatch
#                                       it to the viewport if one is given.

# (Display label, actual animation name from _ANIM_SLOTS).
# The order is intentional — these are the most-used preview slots when
# QC-ing a freshly-rigged body. Some entries are optional convenience previews:
# KOTOR combat reactions often use coded slots such as ``g*d*`` instead of a
# plain ``dodge`` block, so export evidence uses the stricter proof set below.
PREVIEW_ANIMATIONS: Tuple[Tuple[str, str], ...] = (
    ("Idle",  "pause1"),
    ("Walk",  "walk"),
    ("Run",   "run"),
    ("Talk",  "tlknorm"),
    ("Dodge", "dodge"),
)

# Preview clips that must resolve before the Character Builder animation gate
# can claim the inherited supermodel path is proof-ready. Keep this tied to
# verified Aurora slot names, not UI-friendly labels or gameplay categories.
REQUIRED_PREVIEW_ANIMATIONS: Tuple[Tuple[str, str], ...] = (
    ("Idle", "pause1"),
    ("Walk", "walk"),
    ("Run", "run"),
    ("Talk", "tlknorm"),
)

MOTION_SOURCE_MODEL = "model"
MOTION_SOURCE_INHERITED = "inherited_supermodel"
MOTION_SOURCE_IMPORTED = "imported"
MOTION_SOURCE_ROM = "generated_rom"

MOTION_SOURCE_LABELS: Dict[str, str] = {
    MOTION_SOURCE_INHERITED: "Inherit PC supermodel",
    MOTION_SOURCE_MODEL: "Use model clips",
    MOTION_SOURCE_IMPORTED: "Imported clips",
    MOTION_SOURCE_ROM: "Generated ROM",
}

PC_SUPERMODEL_OPTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("K1 Female PC", "S_Female02", "K1"),
    ("K1 Female PC extended", "S_Female03", "K1"),
    ("K1 Male PC", "S_Male02", "K1"),
    ("K1 Male PC extended", "S_Male03", "K1"),
    ("K2 Female PC", "S_Female02", "K2"),
    ("K2 Female PC extended", "S_Female03", "K2"),
    ("K2 Male PC", "S_Male02", "K2"),
    ("K2 Male PC extended", "S_Male03", "K2"),
)


@dataclass
class MotionAssignmentResult:
    """Result of M12/T1204 motion assignment.

    The state is stored on ``scene.motion_assignment`` as a plain dict so
    older CharacterScene versions can participate without a schema bump.
    """
    ok:         bool                              = False
    source:     str                               = MOTION_SOURCE_MODEL
    supermodel: str                               = ""
    available:  List[Tuple[str, str]]             = field(default_factory=list)
    missing:    List[Tuple[str, str]]             = field(default_factory=list)
    message:    str                               = ""
    code:       str                               = "motion_assignment"


@dataclass
class CheckActorResult:
    """Result of :func:`available_preview_animations` /
    :func:`play_preview_animation`.

    Attributes
    ----------
    ok               : True when the operation succeeded.
    available        : List of ``(label, name)`` tuples present on the
                       body model — a subset of :data:`PREVIEW_ANIMATIONS`.
    missing          : Names from :data:`PREVIEW_ANIMATIONS` *not* found
                       on the model — useful for the UI to grey out.
    playing          : Name of the animation currently dispatched to
                       the viewport (or empty string).
    length           : Length in seconds of the playing animation (or 0).
    message          : Human-readable summary.
    code             : Stable tag — ``"listed" / "playing" / "stopped" /
                       "no_body" / "no_animations" / "anim_missing"``.
    diagnostics      : Stable reason codes for empty/fallback states.
    details          : JSON-friendly context for UI/debug displays.
    """
    ok:         bool                              = False
    available:  List[Tuple[str, str]]             = field(default_factory=list)
    missing:    List[Tuple[str, str]]             = field(default_factory=list)
    playing:    str                               = ""
    length:     float                             = 0.0
    message:    str                               = ""
    code:       str                               = "listed"
    diagnostics: List[str]                         = field(default_factory=list)
    details:    Dict[str, Any]                     = field(default_factory=dict)


def _motion_assignment_state(scene: Any) -> Dict[str, Any]:
    state = getattr(scene, "motion_assignment", None)
    if isinstance(state, dict):
        return dict(state)
    return {}


def _write_motion_assignment_state(scene: Any, state: Dict[str, Any]) -> None:
    try:
        setattr(scene, "motion_assignment", dict(state))
        setattr(scene, "dirty", True)
    except Exception:                                      # pragma: no cover
        log.debug("Could not persist motion assignment on scene", exc_info=True)


def _is_null_supermodel(value: str) -> bool:
    return (value or "").strip().upper() in {"", "NULL", "NONE"}


def normalize_kotor_game_tag(game: Any) -> str:
    """Return the canonical KOTOR game tag used for installed resources."""
    if game is None:
        return "K1"

    name = str(getattr(game, "name", "") or "").strip().upper()
    if name in {"K1", "K2"}:
        return name

    value = getattr(game, "value", None)
    if value in {1, "1"}:
        return "K1"
    if value in {2, "2"}:
        return "K2"

    text = str(game or "").strip().upper().replace("_", " ")
    if not text:
        return "K1"
    if text in {"K1", "1", "GAMEVERSION.K1", "GAMEVERSION K1", "KOTOR I", "KOTOR 1"}:
        return "K1"
    if text in {
        "K2",
        "2",
        "GAMEVERSION.K2",
        "GAMEVERSION K2",
        "KOTOR II",
        "KOTOR 2",
        "TSL",
        "THE SITH LORDS",
    }:
        return "K2"
    if (
        "KOTOR2" in text
        or "KOTOR 2" in text
        or "KOTOR II" in text
        or "OLD REPUBLIC II" in text
        or "SITH LORDS" in text
        or "TSL" in text
    ):
        return "K2"
    return "K1"


def _body_supermodel(body: Any) -> str:
    return str(getattr(body, "supermodel", "") or "").strip()


def _native_template_export_supermodel(body: Any) -> str:
    """Return the selected native KOTOR base supermodel, when recorded.

    Character Builder native-template rigs use the selected KOTOR model as the
    final DAG/export authority.  The imported mesh is only a payload guest, so
    previewing a different animation library must not silently rewrite the
    body MDL's export supermodel.
    """
    metadata = getattr(body, "metadata", None)
    if not isinstance(metadata, dict):
        return ""
    bind = metadata.get("character_builder_bind")
    if not isinstance(bind, dict):
        return ""
    native = bind.get("native_base")
    if not isinstance(native, dict):
        return ""
    return str(native.get("supermodel") or "").strip()


def motion_assignment_options(scene: Any) -> MotionAssignmentResult:
    """Return the currently selected motion source and preview split."""
    body = _get_body_model(scene)
    if body is None:
        return MotionAssignmentResult(
            message="No body model loaded. Load a body before assigning motions.",
            code="no_body",
        )

    state = _motion_assignment_state(scene)
    source = str(state.get("source") or MOTION_SOURCE_MODEL)
    supermodel = str(state.get("supermodel") or _body_supermodel(body))
    preview = available_preview_animations(scene)
    return MotionAssignmentResult(
        ok=True,
        source=source,
        supermodel=supermodel,
        available=list(preview.available),
        missing=list(preview.missing),
        message=preview.message,
        code="listed",
    )


def _normalise_imported_clips(imported_clips: Optional[Any]) -> List[str]:
    if imported_clips is None:
        return []
    names: List[str] = []
    for item in imported_clips:
        if isinstance(item, str):
            name = item
        else:
            name = str(getattr(item, "name", "") or getattr(item, "anim_name", ""))
        name = name.strip()
        if name:
            names.append(name)
    return names


def assign_motion_source(
    scene: Any,
    source: str,
    *,
    supermodel: str = "",
    imported_clips: Optional[Any] = None,
) -> MotionAssignmentResult:
    """M12/T1204: assign how this body obtains animation clips.

    ``inherited_supermodel`` mirrors normal KOTOR body behavior: the
    body MDL stores a supermodel string while the engine resolves clips
    from that parent at runtime.
    """
    body = _get_body_model(scene)
    if body is None:
        return MotionAssignmentResult(
            source=source or MOTION_SOURCE_MODEL,
            message="No body model loaded. Load a body before assigning motions.",
            code="no_body",
        )

    source = (source or MOTION_SOURCE_MODEL).strip()
    if source not in MOTION_SOURCE_LABELS:
        return MotionAssignmentResult(
            source=source,
            message=f"Unknown motion source '{source}'.",
            code="unknown_source",
        )

    clips = _normalise_imported_clips(imported_clips)
    state: Dict[str, Any] = {"source": source}
    selected_supermodel = (supermodel or _body_supermodel(body) or "").strip()

    if source == MOTION_SOURCE_INHERITED:
        selected = (selected_supermodel or "S_Female02").strip()
        if _is_null_supermodel(selected):
            selected = "S_Female02"
        export_supermodel = _native_template_export_supermodel(body)
        if export_supermodel:
            current = _body_supermodel(body)
            if not current or current.lower() != export_supermodel.lower():
                setattr(body, "supermodel", export_supermodel)
            if selected.lower() != export_supermodel.lower():
                state["preview_supermodel"] = selected
                state["export_supermodel"] = export_supermodel
                state["preserved_export_supermodel"] = True
        else:
            setattr(body, "supermodel", selected)
        state["supermodel"] = selected
        if state.get("preserved_export_supermodel"):
            message = (
                f"Preview motions will inherit from {selected}; export keeps "
                f"the native KOTOR base supermodel {state['export_supermodel']}."
            )
        else:
            message = (
                f"Motions will inherit from {selected}; KOTOR will resolve "
                "idle, walk, talk, and combat clips through the supermodel."
            )
        code = "inherited"
    elif source == MOTION_SOURCE_MODEL:
        state["supermodel"] = selected_supermodel or _body_supermodel(body)
        message = "Motions will use animation clips stored on this model."
        code = "model_clips"
    elif source == MOTION_SOURCE_IMPORTED:
        state["imported_clips"] = clips
        state["supermodel"] = selected_supermodel or _body_supermodel(body)
        message = (
            f"{len(clips)} imported clip(s) assigned."
            if clips else
            "Imported-clips source selected; import clips before export."
        )
        code = "imported_clips" if clips else "imported_empty"
    else:
        if selected_supermodel and not _is_null_supermodel(selected_supermodel):
            setattr(body, "supermodel", selected_supermodel)
        state["supermodel"] = selected_supermodel or _body_supermodel(body)
        state["generated"] = True
        message = "Generated ROM clip assigned for range-of-motion preview."
        code = "generated_rom"

    _write_motion_assignment_state(scene, state)
    preview = available_preview_animations(scene)
    return MotionAssignmentResult(
        ok=True,
        source=source,
        supermodel=str(state.get("supermodel") or ""),
        available=list(preview.available),
        missing=list(preview.missing),
        message=message,
        code=code,
    )


def _iter_model_animations(model: Any) -> List[Any]:
    """Best-effort accessor for ``KotorModel.animations`` — returns the
    list (possibly empty) of :class:`Animation` objects on the model.
    Survives ducks that name the attribute slightly differently.
    """
    for attr in ("animations", "anims", "animation_list"):
        anims = getattr(model, attr, None)
        if anims is not None:
            try:
                return list(anims)
            except Exception:                               # pragma: no cover
                return []
    return []


def available_preview_animations(scene: Any) -> CheckActorResult:
    """Workflow Step 5a — enumerate preview animations on the body model.

    Walks ``model.animations`` and splits :data:`PREVIEW_ANIMATIONS`
    into ``available`` (found) vs ``missing`` (not found).  Returns
    structured codes so the UI can grey-out missing previews and offer
    a helpful banner when none of the standard set are present.
    """
    body = _get_body_model(scene)
    if body is None:
        return CheckActorResult(
            message="No body model loaded.  Load a body first.",
            code="no_body",
        )

    motion_state = _motion_assignment_state(scene)
    motion_source = str(motion_state.get("source") or "")
    if motion_source == MOTION_SOURCE_INHERITED:
        supermodel = str(motion_state.get("supermodel") or _body_supermodel(body))
        if not _is_null_supermodel(supermodel):
            raw_game = getattr(scene, "game_version", "") or getattr(body, "game_version", "") or "K1"
            game_tag = normalize_kotor_game_tag(raw_game)
            available: List[Tuple[str, str]] = []
            missing: List[Tuple[str, str]] = []
            try:
                from src.core.animation.animation_engine import SuperModelResolver
            except ImportError:                             # pragma: no cover
                from core.animation.animation_engine import SuperModelResolver  # type: ignore
            if getattr(SuperModelResolver, "_resource_manager", None) is not None:
                for label, anim_name in PREVIEW_ANIMATIONS:
                    anim, _scale = SuperModelResolver.resolve_animation(
                        body, anim_name, game_tag,
                    )
                    if anim is not None:
                        available.append((label, anim_name))
                    else:
                        missing.append((label, anim_name))
                if available or missing:
                    return CheckActorResult(
                        ok=True,
                        available=available,
                        missing=missing,
                        message=(
                            f"{len(available)} preview clip(s) resolved through "
                            f"{supermodel}; {len(missing)} missing."
                        ),
                        code=("inherited" if available else "no_animations"),
                    )
            return CheckActorResult(
                ok=True,
                available=list(PREVIEW_ANIMATIONS),
                missing=[],
                message=(
                    f"Preview clips inherit from {supermodel}; "
                    f"{len(PREVIEW_ANIMATIONS)} standard KOTOR clips available."
                ),
                code="inherited",
            )
    if motion_source == MOTION_SOURCE_IMPORTED:
        imported = {
            name.lower()
            for name in _normalise_imported_clips(
                motion_state.get("imported_clips") or []
            )
        }
        available = [
            (label, anim_name)
            for label, anim_name in PREVIEW_ANIMATIONS
            if anim_name.lower() in imported
        ]
        missing = [
            (label, anim_name)
            for label, anim_name in PREVIEW_ANIMATIONS
            if anim_name.lower() not in imported
        ]
        return CheckActorResult(
            ok=True,
            available=available,
            missing=missing,
            message=(
                f"{len(available)} imported preview clip(s) assigned; "
                f"{len(missing)} standard clip(s) still missing."
            ),
            code=("listed" if available else "no_animations"),
        )
    if motion_source == MOTION_SOURCE_ROM:
        return CheckActorResult(
            ok=True,
            available=[("ROM Test", "generated_rom")],
            missing=list(PREVIEW_ANIMATIONS),
            message="Generated ROM is assigned; standard locomotion clips are still missing.",
            code="generated_rom",
        )

    anims = _iter_model_animations(body)
    names = {getattr(a, "name", "").lower() for a in anims if a is not None}

    available: List[Tuple[str, str]] = []
    missing:   List[Tuple[str, str]] = []
    for label, anim_name in PREVIEW_ANIMATIONS:
        if anim_name.lower() in names:
            available.append((label, anim_name))
        else:
            missing.append((label, anim_name))

    if not anims:
        return CheckActorResult(
            ok=True,
            available=[],
            missing=list(PREVIEW_ANIMATIONS),
            message=("Model has no animations — none of the standard "
                     "preview clips can be played."),
            code="no_animations",
        )

    if not available:
        return CheckActorResult(
            ok=True,
            available=[],
            missing=missing,
            message=(f"Model has {len(anims)} animation(s) but none of the "
                     f"standard preview clips "
                     f"({', '.join(n for _, n in PREVIEW_ANIMATIONS)}) "
                     "are present."),
            code="no_animations",
        )

    return CheckActorResult(
        ok=True,
        available=available,
        missing=missing,
        message=(f"{len(available)} preview clip(s) available; "
                 f"{len(missing)} missing."),
        code="listed",
    )


def available_animation_library(scene: Any) -> CheckActorResult:
    """Enumerate every animation available to the current body.

    This includes local clips and inherited supermodel clips when the
    Character Builder has configured :class:`SuperModelResolver` with the
    game resource manager.
    """
    body = _get_body_model(scene)
    if body is None:
        return CheckActorResult(
            message="No body model loaded. Load and build the character first.",
            code="no_body",
            diagnostics=["no_body"],
        )

    raw_game = getattr(scene, "game_version", "") or getattr(body, "game_version", "") or "K1"
    game_tag = normalize_kotor_game_tag(raw_game)
    try:
        from src.core.animation.animation_engine import SuperModelResolver
    except ImportError:                                     # pragma: no cover
        from core.animation.animation_engine import SuperModelResolver  # type: ignore

    motion_state = _motion_assignment_state(scene)
    selected_supermodel = str(motion_state.get("supermodel") or "").strip()
    effective_supermodel = selected_supermodel or _body_supermodel(body)
    list_model = body
    if effective_supermodel and not _is_null_supermodel(effective_supermodel):
        class _AnimationLibraryProxy:
            pass

        proxy = _AnimationLibraryProxy()
        proxy.name = getattr(body, "name", "character")
        proxy.animations = list(_iter_model_animations(body))
        proxy.anim_scale = float(getattr(body, "anim_scale", 1.0) or 1.0)
        proxy.supermodel = effective_supermodel
        list_model = proxy

    entries: List[Tuple[str, str]] = []
    diagnostics: List[str] = []
    details: Dict[str, Any] = {
        "game": game_tag,
        "body": str(getattr(body, "name", "") or ""),
        "motion_source": str(motion_state.get("source") or ""),
        "selected_supermodel": selected_supermodel,
        "effective_supermodel": effective_supermodel,
        "local_animation_count": len(_iter_model_animations(body)),
        "resolver_configured": getattr(SuperModelResolver, "_resource_manager", None) is not None,
    }
    raw_game_label = str(raw_game or "")
    if raw_game_label and raw_game_label.upper() != game_tag:
        details["raw_game"] = raw_game_label
    if effective_supermodel and not _is_null_supermodel(effective_supermodel):
        if not details["resolver_configured"]:
            diagnostics.append("resolver_not_configured")
        else:
            try:
                loaded_super = SuperModelResolver.load_supermodel(
                    effective_supermodel,
                    game_tag,
                )
            except Exception as exc:                       # pragma: no cover - defensive
                loaded_super = None
                diagnostics.append("supermodel_probe_exception")
                details["supermodel_probe_error"] = str(exc)
            if loaded_super is None:
                diagnostics.append(f"supermodel_not_found:{effective_supermodel}")
            else:
                details["resolved_supermodel"] = str(
                    getattr(loaded_super, "name", "") or effective_supermodel
                )
                details["resolved_supermodel_local_animation_count"] = len(
                    _iter_model_animations(loaded_super)
                )
    else:
        diagnostics.append("no_supermodel_selected")

    try:
        for name, source_model, _scale in SuperModelResolver.list_all_animations(list_model, game_tag):
            label = f"{name} [{source_model}]"
            entries.append((label, name))
    except Exception as exc:
        diagnostics.append("resolver_exception")
        details["resolver_error"] = str(exc)
        entries = []

    if not entries:
        for anim in _iter_model_animations(body):
            name = str(getattr(anim, "name", "") or "")
            if name:
                entries.append((f"{name} [{getattr(body, 'name', 'model')}]", name))
        if entries:
            diagnostics.append("local_fallback_used")

    if not entries:
        if not diagnostics:
            diagnostics.append("empty_chain")
        reason_text = "; ".join(diagnostics)
        return CheckActorResult(
            ok=True,
            available=[],
            missing=[],
            message=(
                "No animations are available from the body or its supermodel chain. "
                f"Diagnostics: {reason_text}."
            ),
            code="no_animations",
            diagnostics=diagnostics,
            details=details,
        )

    return CheckActorResult(
        ok=True,
        available=entries,
        missing=[],
        message=f"{len(entries)} animation clip(s) available.",
        code="listed",
        diagnostics=diagnostics,
        details=details,
    )


def _stamp_animation_library_evidence(
    model: Any,
    *,
    motion: Optional[MotionAssignmentResult],
    library: Optional[CheckActorResult],
) -> None:
    """Persist inherited-animation proof on the built model.

    The Qt Character Builder can ask for previews, but the export/report path
    needs headless evidence attached to the model itself.  This keeps animation
    readiness with the core workflow instead of with a particular UI panel.
    """
    if model is None:
        return
    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)

    motion_payload = {
        "schema": "ghostrigger.character_motion_assignment.v1",
        "source": str(getattr(motion, "source", "") or ""),
        "supermodel": str(getattr(motion, "supermodel", "") or ""),
        "code": str(getattr(motion, "code", "") or ""),
        "ok": bool(getattr(motion, "ok", False)),
        "available_preview_names": [
            str(name or "")
            for _label, name in list(getattr(motion, "available", []) or [])
            if str(name or "").strip()
        ],
        "missing_preview_names": [
            str(name or "")
            for _label, name in list(getattr(motion, "missing", []) or [])
            if str(name or "").strip()
        ],
    }

    available = [
        (str(label or ""), str(name or ""))
        for label, name in list(getattr(library, "available", []) or [])
        if str(name or "").strip()
    ]
    available_names = [name for _label, name in available]
    available_lower = {name.lower() for name in available_names}
    required_preview_names = [
        name for _label, name in REQUIRED_PREVIEW_ANIMATIONS
    ]
    required_available = [
        name for name in required_preview_names
        if name.lower() in available_lower
    ]
    required_missing = [
        name for name in required_preview_names
        if name.lower() not in available_lower
    ]
    library_details = dict(getattr(library, "details", {}) or {})
    diagnostics = [
        str(item or "")
        for item in list(getattr(library, "diagnostics", []) or [])
        if str(item or "").strip()
    ]
    status = "resolved" if available_names else "empty"
    if diagnostics and not available_names:
        status = "unresolved"
    elif diagnostics:
        status = "resolved_with_diagnostics"

    metadata["character_builder_motion_assignment"] = motion_payload
    metadata["character_builder_animation_library"] = {
        "schema": "ghostrigger.character_animation_library_evidence.v1",
        "status": status,
        "ok": bool(getattr(library, "ok", False)),
        "code": str(getattr(library, "code", "") or ""),
        "message": str(getattr(library, "message", "") or ""),
        "game": str(library_details.get("game") or ""),
        "body": str(library_details.get("body") or ""),
        "motion_source": str(library_details.get("motion_source") or motion_payload["source"]),
        "selected_supermodel": str(library_details.get("selected_supermodel") or motion_payload["supermodel"]),
        "effective_supermodel": str(library_details.get("effective_supermodel") or ""),
        "resolved_supermodel": str(library_details.get("resolved_supermodel") or ""),
        "resolver_configured": bool(library_details.get("resolver_configured", False)),
        "local_animation_count": int(library_details.get("local_animation_count") or 0),
        "resolved_supermodel_local_animation_count": int(
            library_details.get("resolved_supermodel_local_animation_count") or 0
        ),
        "available_count": len(available_names),
        "sample_animation_names": available_names[:48],
        "required_preview_names": required_preview_names,
        "required_preview_available": required_available,
        "required_preview_missing": required_missing,
        "diagnostics": diagnostics,
    }


def play_preview_animation(
    scene: Any,
    anim_name: str,
    *,
    viewport: Optional[Any] = None,
) -> CheckActorResult:
    """Workflow Step 5b — dispatch a preview animation to the viewport.

    Looks up *anim_name* on the body model and calls
    ``viewport.set_animation_pose(animation, name=anim_name,
    time=0.0, length=animation.length)`` so the M4 renderer starts
    playing it.

    Parameters
    ----------
    scene      : Scene that must already have a body slot populated.
    anim_name  : Animation name, e.g. ``"walk"`` / ``"pause1"`` /
                 ``"tlknorm"`` — matched case-insensitively against
                 ``model.animations[i].name``.
    viewport   : The Qt viewport widget.  Optional — when ``None``,
                 the workflow just confirms the animation exists
                 (useful for headless tests).
    """
    body = _get_body_model(scene)
    if body is None:
        return CheckActorResult(
            message="No body model loaded.",
            code="no_body",
        )

    target = (anim_name or "").lower().strip()
    if not target:
        return CheckActorResult(
            message="No animation name supplied.",
            code="anim_missing",
        )

    chosen = None
    source_model_name = str(getattr(body, "name", "") or "model")
    anim_scale = 1.0
    source_scope = "local"
    for a in _iter_model_animations(body):
        if getattr(a, "name", "").lower() == target:
            chosen = a
            break

    if chosen is None:
        raw_game = (
            getattr(scene, "game_version", "")
            or getattr(body, "game_version", "")
            or "K1"
        )
        game_tag = normalize_kotor_game_tag(raw_game)
        try:
            from src.core.animation.animation_engine import SuperModelResolver
        except ImportError:                                 # pragma: no cover
            from core.animation.animation_engine import SuperModelResolver  # type: ignore
        try:
            resolved, resolved_scale = SuperModelResolver.resolve_animation(
                body,
                anim_name,
                game_tag,
            )
        except Exception:
            resolved, resolved_scale = None, 1.0
        if resolved is not None:
            chosen = resolved
            anim_scale = float(resolved_scale or 1.0)
            source_scope = "inherited"
            try:
                for (
                    entry_name,
                    entry_source,
                    entry_scale,
                ) in SuperModelResolver.list_all_animations(body, game_tag):
                    if str(entry_name or "").lower() == target:
                        source_model_name = str(entry_source or source_model_name)
                        anim_scale = float(entry_scale or anim_scale)
                        break
            except Exception:
                source_model_name = str(getattr(resolved, "source", "") or source_model_name)

    if chosen is None:
        motion_state = _motion_assignment_state(scene)
        motion_source = str(motion_state.get("source") or "")
        if motion_source == MOTION_SOURCE_INHERITED:
            requested = {name.lower(): label for label, name in PREVIEW_ANIMATIONS}
            if target in requested:
                supermodel = str(
                    motion_state.get("supermodel") or _body_supermodel(body)
                )
                return CheckActorResult(
                    ok=True,
                    available=list(PREVIEW_ANIMATIONS),
                    playing=anim_name,
                    length=0.0,
                    message=(
                        f"'{anim_name}' is inherited from {supermodel}. "
                        "Export will reference the supermodel; exact playback "
                        "requires loading the supermodel clip."
                    ),
                    code="inherited_preview",
                )
        if motion_source == MOTION_SOURCE_ROM and target == "generated_rom":
            return CheckActorResult(
                ok=True,
                available=[("ROM Test", "generated_rom")],
                playing="generated_rom",
                length=4.0,
                message="Generated ROM preview selected.",
                code="generated_rom",
            )
        return CheckActorResult(
            message=f"Animation '{anim_name}' is not present on this model.",
            code="anim_missing",
        )

    length = float(getattr(chosen, "length", 0.0) or 0.0)

    # Dispatch to the viewport when we have one.  Done last so we
    # always return a structured result even if the dispatch raises.
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(
                chosen,
                name=getattr(chosen, "name", anim_name),
                time=0.0,
                length=length,
            )
        except Exception as exc:                            # pragma: no cover
            log.exception("play_preview_animation: viewport dispatch raised")
            return CheckActorResult(
                playing="",
                length=length,
                message=(f"Animation '{anim_name}' found but viewport "
                         f"dispatch failed: {exc}"),
                code="anim_missing",
            )

    return CheckActorResult(
        ok=True,
        playing=getattr(chosen, "name", anim_name),
        length=length,
        message=f"Playing '{anim_name}' ({length:.2f}s).",
        code="playing",
        details={
            "source_model": source_model_name,
            "source_scope": source_scope,
            "anim_scale": anim_scale,
        },
    )


def run_rom_test(scene: Any, *, viewport: Optional[Any] = None) -> CheckActorResult:
    """M9/T903 — assign and start the generated ROM preview.

    This is the launch-path bridge until M8's full Stewart Jones ROM
    generator lands.  It records the generated-ROM motion source on the
    scene, exposes a ``generated_rom`` preview clip, and nudges the
    viewport/bottom strip into a four-second ROM playback state.
    """
    assigned = assign_motion_source(scene, MOTION_SOURCE_ROM)
    if not assigned.ok:
        return CheckActorResult(
            message=assigned.message,
            code=assigned.code,
        )

    result = play_preview_animation(scene, "generated_rom", viewport=None)
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(
                None,
                name="generated_rom",
                time=0.0,
                length=result.length or 4.0,
            )
        except Exception as exc:                            # pragma: no cover
            log.exception("run_rom_test: viewport dispatch raised")
            return CheckActorResult(
                available=result.available,
                playing="",
                length=result.length or 4.0,
                message=f"Generated ROM assigned but viewport dispatch failed: {exc}",
                code="anim_missing",
            )

    return CheckActorResult(
        ok=result.ok,
        available=[("ROM Test", "generated_rom")],
        missing=list(PREVIEW_ANIMATIONS),
        playing="generated_rom",
        length=result.length or 4.0,
        message="Running generated ROM test for range-of-motion validation.",
        code="generated_rom",
    )


def stop_preview_animation(viewport: Optional[Any] = None) -> CheckActorResult:
    """Workflow Step 5c — stop the currently-playing preview animation.

    Calls ``viewport.set_animation_pose(None)`` per the existing
    viewport contract (line 988 of qt_viewport.py).  Returns a
    structured ``stopped`` code so the UI can refresh.
    """
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(None)
        except Exception as exc:                            # pragma: no cover
            log.exception("stop_preview_animation: viewport dispatch raised")
            return CheckActorResult(
                message=f"Failed to stop animation: {exc}",
                code="anim_missing",
            )
    return CheckActorResult(
        ok=True,
        message="Stopped preview animation.",
        code="stopped",
    )


@dataclass
class _WorkflowSeverity:
    value: str


@dataclass
class _WorkflowIssue:
    severity: _WorkflowSeverity
    code: str
    message: str
    slot: Any = None
    node: str = ""


def _motion_assignment_issues(scene: Any) -> List[Any]:
    """Pre-export motion checks for the external-mesh launch path."""
    body = _get_body_model(scene)
    if body is None:
        return []

    state = _motion_assignment_state(scene)
    source = str(state.get("source") or "")
    supermodel = str(state.get("supermodel") or _body_supermodel(body))
    local_anims = _iter_model_animations(body)

    if source == MOTION_SOURCE_INHERITED:
        if not _is_null_supermodel(supermodel):
            return []
        return [_WorkflowIssue(
            _WorkflowSeverity("error"),
            "MOTIONS_MISSING",
            "Inherited motions selected, but no KOTOR supermodel is assigned.",
        )]

    if source == MOTION_SOURCE_IMPORTED:
        clips = _normalise_imported_clips(state.get("imported_clips") or [])
        if clips:
            return []
        return [_WorkflowIssue(
            _WorkflowSeverity("error"),
            "MOTIONS_MISSING",
            "Imported motion source selected, but no imported clips are assigned.",
        )]

    if local_anims:
        return []
    if not _is_null_supermodel(supermodel):
        return []

    return [_WorkflowIssue(
        _WorkflowSeverity("error"),
        "MOTIONS_MISSING",
        "No model clips or inherited KOTOR supermodel motions are assigned.",
    )]


def _scene_mode_value(scene: Any) -> str:
    mode = getattr(scene, "mode", "")
    return (
        getattr(mode, "value", None)
        or getattr(mode, "name", "")
        or str(mode or "")
    ).lower()


def _animation_names(model: Any) -> List[str]:
    return [
        str(getattr(anim, "name", "") or "").strip().lower()
        for anim in _iter_model_animations(model)
        if str(getattr(anim, "name", "") or "").strip()
    ]


def _per_mode_export_issues(scene: Any) -> List[Any]:
    """M10/T1005 mode-specific blockers that validation_service cannot infer."""
    mode = _scene_mode_value(scene)
    issues: List[Any] = []

    if mode == "head":
        head = _get_head_model(scene)
        names = _animation_names(head) if head is not None else []
        if not any(name == "talk" or name.startswith("tlk") for name in names):
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "TALK_ANIMATION_MISSING",
                "Head export requires a talk animation for KOTOR LIP/viseme playback.",
                node="talkdummy",
            ))

    if mode == "supermodel":
        snap = getattr(scene, "metadata", {}).get("composite_snap", {})
        if not (
            isinstance(snap, dict)
            and bool(snap.get("ok"))
            and str(snap.get("code", "")).lower() == "snapped"
            and snap.get("head_local_offset") is not None
        ):
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "COMPOSITE_SNAP_MISSING",
                "Supermodel export requires a completed headhook snap before export.",
                node="headhook",
            ))

    if mode == "creature":
        state = _motion_assignment_state(scene)
        if (
            str(state.get("source") or "") != MOTION_SOURCE_ROM
            and not _creature_has_native_template_motion_proof(scene)
        ):
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "ROM_CLIP_MISSING",
                "Creature export requires a generated ROM clip to prove the rig extremes.",
            ))

    return issues


def _creature_has_native_template_motion_proof(scene: Any) -> bool:
    """Return True for native-template creatures with their own animation clips."""
    body = _get_body_model(scene)
    if body is None or not _iter_model_animations(body):
        return False
    state = getattr(body, "_gr_character_builder_rig_state", None)
    if isinstance(state, dict):
        return str(state.get("state") or "") == "native_template_final"
    if str(getattr(state, "state", "") or "") == "native_template_final":
        return True
    metadata = getattr(body, "metadata", None)
    if isinstance(metadata, dict):
        raw_state = metadata.get("character_builder_rig_state")
        if isinstance(raw_state, dict):
            return str(raw_state.get("state") or "") == "native_template_final"
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  T506 ▸ Validate + Export step
# ─────────────────────────────────────────────────────────────────────────────
#
# The final workflow step lets the user (a) run the full validation
# service with ``strict=True`` to surface every blocker, and (b) write
# the scene out to one or more of KOTOR (MDL/MDX) / FBX / glTF / OBJ
# next to a ``.ghostrig.json`` sidecar (via :class:`SceneIO`).
#
# M10/T1001 wires the already-present MDL/MDX, FBX, glTF/GLB, and OBJ
# writers through this service so the Qt export dialog can produce real
# files.  The ``.ghostrig.json`` sidecar remains an optional recovery and
# round-trip artifact written beside the selected export formats.

EXPORT_FORMATS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # (key,    display label,         extensions for the output file)
    ("kotor", "KOTOR (MDL/MDX)",      (".mdl",  ".mdx")),
    ("fbx",   "FBX (Autodesk)",       (".fbx",)),
    ("gltf",  "glTF / GLB",           (".gltf", ".glb")),
    ("obj",   "OBJ (Wavefront)",      (".obj",)),
)


def default_export_formats_for_mode(scene_or_mode: Any) -> Tuple[str, ...]:
    """Return M10/T1004 export defaults for a Character Builder mode."""
    mode = getattr(scene_or_mode, "mode", scene_or_mode)
    value = (
        getattr(mode, "value", None)
        or getattr(mode, "name", "")
        or str(mode or "")
    ).lower()
    if value == "head":
        return ("kotor", "fbx", "gltf")
    if value == "supermodel":
        return ("fbx", "gltf")
    if value in ("headless_body", "creature"):
        return ("kotor", "fbx", "gltf", "obj")
    return ("kotor",)


@dataclass
class ValidateForExportResult:
    """Result of :func:`validate_for_export`.

    Attributes
    ----------
    ok               : True when no ERROR-severity issues were found
                       under ``strict=True``.  Warnings/info do *not*
                       block export.
    error_count      : Number of ERROR issues.
    warning_count    : Number of WARNING issues.
    info_count       : Number of INFO issues.
    blocking_codes   : Sorted list of unique error codes that would
                       block export.
    issues           : Full list of :class:`ValidationIssue`-like
                       objects from the service.
    message          : Human-readable summary.
    code             : Stable tag — ``"clean" / "warnings_only" /
                       "blocked"``.
    """
    ok:             bool                          = False
    error_count:    int                           = 0
    warning_count:  int                           = 0
    info_count:     int                           = 0
    blocking_codes: List[str]                     = field(default_factory=list)
    issues:         List[Any]                     = field(default_factory=list)
    message:        str                           = ""
    code:           str                           = "clean"


@dataclass
class ExportFormatResult:
    """Per-format result inside :class:`ExportResult`."""
    key:        str   = ""
    label:      str   = ""
    ok:         bool  = False
    path:       str   = ""
    message:    str   = ""
    code:       str   = "exported"        # exported / not_implemented /
                                          # no_body / failed / skipped


@dataclass
class ExportResult:
    """Result of :func:`export_scene`.

    Attributes
    ----------
    ok               : True when at least one format succeeded *and*
                       no requested format raised.  False when a hard
                       precondition fails (e.g. no body slot,
                       validation blocked) or every format failed.
    formats          : Per-format :class:`ExportFormatResult` rows in
                       the order they were requested.
    sidecar_path     : Absolute path of the written ``.ghostrig.json``
                       (empty when ``write_sidecar`` was False).
    out_dir          : The resolved output directory.
    message          : Human-readable summary.
    code             : Stable tag — ``"exported" / "no_body" / "blocked" /
                       "no_formats" / "no_out_dir" / "all_failed"``.
    """
    ok:           bool                            = False
    formats:      List[ExportFormatResult]        = field(default_factory=list)
    sidecar_path: str                             = ""
    out_dir:      str                             = ""
    message:      str                             = ""
    code:         str                             = "exported"


@dataclass
class LaunchWorkflowResult:
    """End-to-end external-mesh export-candidate proof result (M12/T1205).

    ``ok`` means the staged MDL/MDX candidate exported and reloaded through the
    Character Builder gates. It does not mean the candidate has been tested in
    KOTOR 1 or KOTOR 2.
    """

    ok:               bool                       = False
    load_result:      Optional[LoadResult]        = None
    apply_result:     Dict[str, Any]              = field(default_factory=dict)
    guide_result:     Optional[BodyRigGuidesResult] = None
    generate_result:  Optional[BodyRigGenerateResult] = None
    motion_result:    Optional[MotionAssignmentResult] = None
    animation_library_result: Optional[CheckActorResult] = None
    export_result:    Optional[ExportResult]      = None
    reloaded_model:   Optional[Any]               = None
    mdl_path:         str                         = ""
    mdx_path:         str                         = ""
    hooks:            List[str]                   = field(default_factory=list)
    mesh_count:       int                         = 0
    skin_node_count:  int                         = 0
    supermodel:       str                         = ""
    capability_stage: str                         = ""
    game_tested:      bool                        = False
    message:          str                         = ""
    code:             str                         = "launch_workflow"


def _import_scene_io():                                     # pragma: no cover - import shim
    """Defer the SceneIO import to keep the module pykotor-free at import time."""
    try:
        from src.core.geometry.model_data import SceneIO  # type: ignore[import-untyped]
    except ImportError:
        from core.geometry.model_data import SceneIO      # type: ignore[import-untyped]
    return SceneIO


def _with_supermodel_resource_manager(
    resource_manager: Optional[Any],
):
    """Temporarily configure inherited-animation lookup for headless checks."""

    class _ResolverContext:
        def __init__(self, manager: Optional[Any]) -> None:
            self.manager = manager
            self.previous = None
            self.changed = False

        def __enter__(self):
            try:
                from src.core.animation.animation_engine import SuperModelResolver
            except ImportError:                             # pragma: no cover
                from core.animation.animation_engine import SuperModelResolver  # type: ignore
            self.resolver = SuperModelResolver
            self.previous = getattr(SuperModelResolver, "_resource_manager", None)
            if self.manager is not None and self.previous is not self.manager:
                SuperModelResolver.clear_cache()
                SuperModelResolver.configure(self.manager)
                self.changed = True
            return SuperModelResolver

        def __exit__(self, exc_type, exc, tb) -> None:
            if self.changed:
                self.resolver.clear_cache()
                self.resolver.configure(self.previous)

    return _ResolverContext(resource_manager)


def _import_mdl_binary_writer():                            # pragma: no cover - import shim
    """Defer the KOTOR MDL/MDX writer until export time."""
    try:
        from src.core.mdl.mdl_writer import MDLBinaryWriter  # type: ignore
    except ImportError:
        from core.mdl.mdl_writer import MDLBinaryWriter      # type: ignore
    return MDLBinaryWriter


def _import_mesh_exporters():                                # pragma: no cover - import shim
    """Defer interchange exporters until export time."""
    try:
        from src.converters.mesh_converter import (       # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    except ImportError:
        from converters.mesh_converter import (           # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    return FBXExporter, GLTFExporter, OBJExporter


def _load_exported_kotor_model(mdl_path: str) -> Optional[Any]:
    """Reload an exported MDL/MDX pair through GhostRigger's KOTOR loader."""
    try:
        from src.core.game.kotor_loader import load_model_from_file
    except ImportError:                                     # pragma: no cover
        from core.game.kotor_loader import load_model_from_file  # type: ignore
    mdx_path = os.path.splitext(mdl_path)[0] + ".mdx"
    return load_model_from_file(mdl_path, mdx_path if os.path.isfile(mdx_path) else "")


def _model_nodes(model: Any) -> List[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        root = getattr(model, "root_node", None)
        if root is None:
            return []
        out: List[Any] = []

        def _walk(node: Any) -> None:
            out.append(node)
            for child in list(getattr(node, "children", []) or []):
                _walk(child)

        _walk(root)
    return out


def _model_node_path(node: Any) -> Tuple[str, ...]:
    parts: List[str] = []
    seen: set[int] = set()
    current = node
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = str(getattr(current, "name", "") or "")
        if name:
            parts.append(name)
        current = getattr(current, "parent", None)
    return tuple(reversed(parts))


def _reload_structural_path_problems(
    model: Any,
    expected_native_snapshot: Optional[Any],
) -> List[str]:
    if expected_native_snapshot is None:
        return []
    structural_roles = {"socket", "helper", "deform_helper"}
    expected_paths = [
        tuple(getattr(node, "full_path", ()) or ())
        for node in list(getattr(expected_native_snapshot, "nodes", ()) or ())
        if str(getattr(node, "export_role", "") or "") in structural_roles
    ]
    expected_paths = [path for path in expected_paths if path]
    if not expected_paths:
        return []
    reloaded_paths = {_model_node_path(node) for node in _model_nodes(model)}
    missing = [
        path for path in expected_paths
        if path not in reloaded_paths
    ]
    return [
        "Reloaded export is missing native structural path: "
        + " / ".join(path)
        for path in missing
    ]


def _native_template_build_summary(model: Any) -> BodyRigGenerateResult:
    """Summarize the native-template rig path without invoking legacy AcuRig."""
    nodes = _model_nodes(model)
    skin_vertices = 0
    for node in nodes:
        if bool(getattr(node, "is_skin", False)) or bool(getattr(node, "skin_data", None)):
            try:
                skin_vertices += len(list(getattr(node, "skin_data", []) or []))
            except Exception:
                skin_vertices += 0
    return BodyRigGenerateResult(
        ok=True,
        bone_count=len(nodes),
        vertices_skinned=skin_vertices,
        message=(
            "Native KOTOR template rig applied; legacy AcuRig skeleton "
            "generation skipped for export."
        ),
        code="native_template",
    )


def model_texture_names(model: Any) -> List[str]:
    """Return unique diffuse/aux texture names referenced by a model."""
    names: List[str] = []
    seen: set[str] = set()
    fields = (
        "texture",
        "lightmap",
        "txi_envmaptexture",
        "txi_specularcolour",
        "txi_bumpmaptexture",
    )
    for node in _model_nodes(model):
        if not (
            bool(getattr(node, "is_mesh", False))
            or bool(getattr(node, "is_skin", False))
            or bool(getattr(node, "vertices", None))
        ):
            continue
        raw_names: List[Any] = [getattr(node, field, "") for field in fields]
        raw_names.extend(list(getattr(node, "texture_names", []) or []))
        for raw in raw_names:
            clean = Path(str(raw or "").strip()).stem
            if not clean or clean.upper() in {"NULL", "NONE"}:
                continue
            key = clean.lower()
            if key not in seen:
                seen.add(key)
                names.append(clean[:32])
    return names


def candidate_texture_dirs(source_path: str) -> List[str]:
    """Likely folders beside an imported FBX/OBJ/glTF that hold textures."""
    if not source_path:
        return []
    base = Path(source_path).resolve().parent
    names = ("", "Texture", "Textures", "texture", "textures", "Materials", "materials")
    out: List[str] = []
    seen: set[str] = set()
    for name in names:
        path = base / name if name else base
        if path.is_dir():
            resolved = str(path)
            key = os.path.normcase(os.path.abspath(resolved))
            if key not in seen:
                seen.add(key)
                out.append(resolved)
    return out


def texture_file_for_name(name: str, dirs: List[str]) -> str:
    """Return the first matching on-disk texture path for *name*."""
    stem = Path(str(name or "").strip()).stem
    if not stem:
        return ""
    for directory in dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for ext in _TEXTURE_EXTS:
            direct = Path(directory) / f"{stem}{ext}"
            if direct.is_file():
                return str(direct)
        try:
            for child in Path(directory).iterdir():
                if child.is_file() and child.stem.lower() == stem.lower():
                    return str(child)
        except OSError:
            continue
    return ""


def texture_resolution_report(
    model: Any,
    dirs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Report which referenced textures are found in the supplied folders."""
    dirs = list(dirs or [])
    found: Dict[str, str] = {}
    missing: List[str] = []
    for name in model_texture_names(model):
        path = texture_file_for_name(name, dirs)
        if path:
            found[name] = path
        else:
            missing.append(name)
    return {
        "expected": model_texture_names(model),
        "found": found,
        "missing": missing,
        "found_count": len(found),
        "missing_count": len(missing),
        "dirs": dirs,
    }


def export_external_textures(
    scene: Any,
    model: Any,
    out_dir: str,
) -> Dict[str, Any]:
    """Convert externally supplied texture images to game-side TGA files."""
    metadata = getattr(scene, "metadata", None)
    if not isinstance(metadata, dict):
        return {"ok": True, "written": [], "missing": [], "message": "No metadata."}
    dirs = [
        str(path)
        for path in list(metadata.get("external_texture_dirs", []) or [])
        if path and os.path.isdir(str(path))
    ]
    if not dirs:
        return {"ok": True, "written": [], "missing": [], "message": "No external texture dirs."}
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - Pillow is available in supported builds
        return {"ok": False, "written": [], "missing": [], "message": f"Pillow unavailable: {exc}"}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    missing: List[str] = []
    for name in model_texture_names(model):
        src = texture_file_for_name(name, dirs)
        if not src:
            missing.append(name)
            continue
        target = out / f"{Path(name).stem[:32]}.tga"
        try:
            img = Image.open(src).convert("RGBA")
            img.save(target, format="TGA")
            written.append(str(target))
        except Exception as exc:
            log.warning("Could not export texture %s from %s: %s", name, src, exc)
            missing.append(name)
    result = {
        "ok": not missing,
        "written": written,
        "missing": missing,
        "message": f"{len(written)} texture(s) written; {len(missing)} missing.",
    }
    metadata["external_texture_exports"] = result
    return result


def _verify_launch_reloaded_model(
    model: Any,
    *,
    expected_supermodel: str = "",
    expected_native_snapshot: Optional[Any] = None,
) -> Tuple[bool, List[str], int, int, str, str]:
    """Check the KOTOR-critical facts after reloading an exported body."""
    if model is None:
        return False, [], 0, 0, "", "Reloaded model is empty."

    nodes = _model_nodes(model)
    names = [str(getattr(n, "name", "") or "") for n in nodes]
    names_lower = {n.lower() for n in names}
    required_hooks = _native_template_required_hook_names(expected_native_snapshot)
    required_hook_lowers = {hook.lower() for hook in required_hooks}
    hooks = [n for n in names if n.lower() in required_hook_lowers]
    mesh_count = sum(
        1 for n in nodes
        if bool(getattr(n, "is_mesh", False))
        or bool(getattr(n, "vertices", None))
    )
    skin_count = sum(
        1 for n in nodes
        if bool(getattr(n, "is_skin", False))
        or bool(getattr(n, "skin_data", None))
    )
    supermodel = str(getattr(model, "supermodel", "") or "")
    problems: List[str] = []
    for required in required_hooks:
        if required not in names_lower:
            problems.append(f"Missing required hook/node: {required}")
    problems.extend(
        _reload_structural_path_problems(
            model,
            expected_native_snapshot,
        )
    )
    if mesh_count <= 0:
        problems.append("Reloaded export has no mesh nodes.")
    if skin_count <= 0:
        problems.append("Reloaded export has no skinned mesh data.")
    if expected_supermodel and supermodel.lower() != expected_supermodel.lower():
        problems.append(
            f"Supermodel mismatch: expected {expected_supermodel}, got {supermodel or 'NULL'}."
        )
    return (not problems), hooks, mesh_count, skin_count, supermodel, "; ".join(problems)


def _native_template_required_hook_names(expected_native_snapshot: Optional[Any]) -> Tuple[str, ...]:
    hook_names = tuple(
        str(name).strip().lower()
        for name in (getattr(expected_native_snapshot, "hook_names", None) or ())
        if str(name).strip()
    )
    return hook_names or ("headhook", "rhand", "lhand")


def run_external_mesh_launch_workflow(
    mesh_path: str,
    *,
    scene: Optional[Any] = None,
    game_version: str = "K1",
    out_dir: str = "",
    template_part: str = "body",
    template_model: Optional[Any] = None,
    template_label: str = "",
    motion_supermodel: str = "S_Female02",
    formats: Optional[List[str]] = None,
    require_animation_library: bool = False,
    output_resref: str = "",
) -> LaunchWorkflowResult:
    """M12/T1205: one-shot external mesh to reloadable KOTOR export.

    This is the automation equivalent of the launch workflow a modder
    expects: load external mesh, apply/bind a KOTOR native template,
    inherit PC motions, export MDL/MDX, then reload the result and verify
    hooks, supermodel, mesh count, and skin data.

    When ``template_model`` is supplied, it is the selected native KOTOR
    skeleton authority for both import fitting and final binding.  This is the
    intended path for fixtures such as Bendak.fbx -> n_mandalorian; the
    imported mesh remains a payload guest and the selected KOTOR model owns the
    final node DAG.
    """
    md = _import_model_data()
    if scene is None:
        scene = md.CharacterScene(game_version=game_version)
    if not out_dir:
        return LaunchWorkflowResult(
            message="No output directory supplied for launch workflow.",
            code="no_out_dir",
        )

    load = load_body(
        mesh_path,
        scene,
        game_version=game_version,
        allow_mode_correction=True,
        fit_reference_model=template_model,
        fit_reference_label=template_label,
    )
    if not load.ok or load.model is None:
        return LaunchWorkflowResult(
            load_result=load,
            message=f"Launch workflow stopped at load: {load.message}",
            code=load.code or "load_failed",
        )

    try:
        cb = _import_character_builder()
        template = template_model
        if template is None:
            template = cb.load_template(game=game_version, part=template_part)
        applied = cb.apply_template_rig(load.model, template, game=game_version)
    except Exception as exc:
        log.exception("run_external_mesh_launch_workflow: template apply failed")
        return LaunchWorkflowResult(
            load_result=load,
            message=f"Template rig apply failed: {exc}",
            code="template_failed",
        )
    if not bool(applied.get("ok")):
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            message=str(applied.get("message") or "Template rig apply failed."),
            code="template_failed",
        )

    rigged_model = applied.get("model")
    export_resref = str(output_resref or load.resref or _resref_from_path(mesh_path)).strip().lower()
    if output_resref and rigged_model is not None:
        try:
            rigged_model.name = export_resref[:32]
        except Exception:
            pass
    scene.assign(
        md.PartSlot.HEADLESS_BODY,
        rigged_model,
        resref=export_resref,
        game_version=game_version,
        source_path=mesh_path,
    )

    generated = _native_template_build_summary(rigged_model)

    motion = assign_motion_source(
        scene,
        MOTION_SOURCE_INHERITED,
        supermodel=motion_supermodel,
    )
    if not motion.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            generate_result=generated,
            motion_result=motion,
            message=f"Launch workflow stopped at motion assignment: {motion.message}",
            code=motion.code or "motion_failed",
        )

    animation_library = None
    resource_manager = getattr(template, "_gr_supermodel_resource_manager", None)
    with _with_supermodel_resource_manager(resource_manager):
        animation_library = available_animation_library(scene)
    _stamp_animation_library_evidence(
        rigged_model,
        motion=motion,
        library=animation_library,
    )
    if require_animation_library and not list(getattr(animation_library, "available", []) or []):
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            generate_result=generated,
            motion_result=motion,
            animation_library_result=animation_library,
            message=(
                "Launch workflow stopped at animation assignment: "
                f"{animation_library.message}"
            ),
            code=animation_library.code or "animation_library_empty",
        )

    exported = export_scene(
        scene,
        formats=list(formats or ["kotor"]),
        out_dir=out_dir,
        write_sidecar=True,
    )
    if not exported.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            generate_result=generated,
            motion_result=motion,
            animation_library_result=animation_library,
            export_result=exported,
            message=f"Launch workflow stopped at export: {exported.message}",
            code=exported.code or "export_failed",
        )

    mdl_path = ""
    for row in exported.formats:
        if row.key == "kotor" and row.ok:
            mdl_path = row.path
            break
    if not mdl_path:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            generate_result=generated,
            motion_result=motion,
            animation_library_result=animation_library,
            export_result=exported,
            message="KOTOR export did not produce an MDL path.",
            code="no_mdl_export",
        )

    try:
        reloaded = _load_exported_kotor_model(mdl_path)
    except Exception as exc:
        log.exception("run_external_mesh_launch_workflow: reload failed")
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            generate_result=generated,
            motion_result=motion,
            animation_library_result=animation_library,
            export_result=exported,
            mdl_path=mdl_path,
            mdx_path=os.path.splitext(mdl_path)[0] + ".mdx",
            message=f"Exported MDL reload failed: {exc}",
            code="reload_failed",
        )

    expected_export_supermodel = (
        _native_template_export_supermodel(rigged_model)
        or _body_supermodel(rigged_model)
        or motion.supermodel
        or motion_supermodel
    )
    ok, hooks, mesh_count, skin_count, supermodel, problems = (
        _verify_launch_reloaded_model(
            reloaded,
            expected_supermodel=expected_export_supermodel,
            expected_native_snapshot=getattr(rigged_model, "_gr_native_skeleton_snapshot", None),
        )
    )
    return LaunchWorkflowResult(
        ok=ok,
        load_result=load,
        apply_result=applied,
        generate_result=generated,
        motion_result=motion,
        animation_library_result=animation_library,
        export_result=exported,
        reloaded_model=reloaded,
        mdl_path=mdl_path,
        mdx_path=os.path.splitext(mdl_path)[0] + ".mdx",
        hooks=hooks,
        mesh_count=mesh_count,
        skin_node_count=skin_count,
        supermodel=supermodel,
        capability_stage="export_candidate" if ok else "blocked",
        game_tested=False,
        message=(
            "Export-candidate workflow proof passed; in-game testing is still required."
            if ok else
            f"Launch workflow reload verification failed: {problems}"
        ),
        code="export_candidate_verified" if ok else "verification_failed",
    )


def run_external_mesh_native_template_launch_workflow(
    mesh_path: str,
    native_template_resref: str,
    *,
    scene: Optional[Any] = None,
    game_version: str = "K1",
    game_dir: str = "",
    out_dir: str = "",
    motion_supermodel: str = "",
    formats: Optional[List[str]] = None,
    output_resref: str = "",
) -> LaunchWorkflowResult:
    """Load a custom mesh and bind it to a selected native KOTOR base resref.

    This is the headless equivalent of the Character Builder path:

    ``Choose KOTOR Base`` -> ``Load Custom Mesh`` -> ``Auto-Fit`` -> ``Build``
    -> ``Export``.

    The native base MDL loaded from ``native_template_resref`` is the authority
    for the final DAG and the imported file is only a mesh payload. For the
    Bendak fixture, call this with ``mesh_path=Bendak.fbx`` and
    ``native_template_resref=n_mandalorian``.
    """
    resref = str(native_template_resref or "").strip().lower()
    if not resref:
        return LaunchWorkflowResult(
            message="No native KOTOR base skeleton resref supplied.",
            code="no_native_template_resref",
        )

    try:
        cb = _import_character_builder()
        template = cb.load_game_skeleton_source(
            resref,
            game=game_version,
            game_dir=game_dir or None,
        )
    except Exception as exc:
        log.exception(
            "run_external_mesh_native_template_launch_workflow: native template load failed"
        )
        return LaunchWorkflowResult(
            message=f"Native KOTOR base skeleton load failed: {exc}",
            code="native_template_failed",
        )

    if template is None:
        return LaunchWorkflowResult(
            message=(
                f"Could not load native KOTOR base skeleton '{resref}'. "
                "Choose a resref that exists in the configured game library."
            ),
            code="native_template_missing",
        )

    return run_external_mesh_launch_workflow(
        mesh_path,
        scene=scene,
        game_version=game_version,
        out_dir=out_dir,
        template_model=template,
        template_label=resref,
        motion_supermodel=(
            str(motion_supermodel or "")
            or str(getattr(template, "supermodel", "") or "")
            or "S_Female02"
        ),
        formats=formats,
        require_animation_library=True,
        output_resref=output_resref or resref,
    )


def validate_for_export(
    scene: Any,
    *,
    strict: bool = True,
) -> ValidateForExportResult:
    """Workflow Step 6a — run :class:`ValidationService` with strict=True.

    Returns a structured result indicating whether the scene is safe
    to export.  ERROR-severity issues block export; WARNING / INFO
    pass through as advisory.
    """
    try:
        svc_mod = _import_validation_service()
    except Exception as exc:                                # pragma: no cover
        return ValidateForExportResult(
            message=f"ValidationService unavailable: {exc}",
            code="blocked",
        )

    try:
        service = svc_mod.ValidationService(scene, strict=strict)
        issues = list(service.validate() or [])
        issues.extend(_motion_assignment_issues(scene))
        issues.extend(_per_mode_export_issues(scene))
    except Exception as exc:                                # pragma: no cover
        log.exception("validate_for_export: ValidationService raised")
        return ValidateForExportResult(
            message=f"Validation failed: {exc}",
            code="blocked",
        )

    _summary, _label, errors, warnings, infos, codes = _summarize_issues(issues)
    # Match the established severity-read pattern from
    # ``_summarize_issues`` (``severity.value.lower() == "error"``)
    # so duck-typed fakes used in tests work the same here.
    blocking = sorted({
        getattr(i, "code", "")
        for i in issues
        if (getattr(getattr(i, "severity", None), "value",
                    getattr(getattr(i, "severity", None), "name", ""))
            or "").lower() == "error"
        and getattr(i, "code", "")
    })

    if errors > 0:
        return ValidateForExportResult(
            ok=False,
            error_count=errors, warning_count=warnings, info_count=infos,
            blocking_codes=blocking,
            issues=issues,
            message=(f"Export blocked — {errors} error(s), "
                     f"{warnings} warning(s), {infos} info "
                     f"({len(codes)} unique code(s))."),
            code="blocked",
        )

    if warnings > 0 or infos > 0:
        return ValidateForExportResult(
            ok=True,
            error_count=0, warning_count=warnings, info_count=infos,
            blocking_codes=[],
            issues=issues,
            message=(f"Export allowed — {warnings} warning(s), "
                     f"{infos} info (no blockers)."),
            code="warnings_only",
        )

    return ValidateForExportResult(
        ok=True,
        error_count=0, warning_count=0, info_count=0,
        blocking_codes=[],
        issues=issues,
        message="Scene is clean — ready to export.",
        code="clean",
    )


def _export_single_format(
    scene: Any,
    body: Any,
    fmt_key: str,
    label: str,
    out_dir: str,
    resref: str,
) -> ExportFormatResult:
    """Dispatch one format.  Returns a structured per-format row.

    M10/T1001 wires the already-present writers into the workflow service
    so the export dialog can produce real files instead of sidecar-only
    placeholders.
    """
    # Resolve output path candidate (caller is responsible for the dir).
    primary_ext = {
        "kotor": ".mdl",
        "fbx":   ".fbx",
        "gltf":  ".glb",
        "obj":   ".obj",
    }.get(fmt_key, "")
    if not primary_ext:
        return ExportFormatResult(
            key=fmt_key, label=label, ok=False,
            message=f"Unknown format key '{fmt_key}'.",
            code="failed",
        )

    out_path = os.path.join(out_dir, f"{resref}{primary_ext}")

    try:
        if fmt_key == "kotor":
            try:
                from src.core.characters.character_export_transaction import (
                    CharacterBuilderExportTransactionRequest,
                    export_character_mdl_mdx_transaction,
                )
            except ImportError:  # pragma: no cover
                from core.characters.character_export_transaction import (  # type: ignore
                    CharacterBuilderExportTransactionRequest,
                    export_character_mdl_mdx_transaction,
                )

            def _reload_exported(mdl_path, _mdx_path):
                return _load_exported_kotor_model(str(mdl_path))

            tx = export_character_mdl_mdx_transaction(
                CharacterBuilderExportTransactionRequest(
                    model=body,
                    output_mdl_path=out_path,
                    game=str(getattr(scene, "game_version", "") or "K1"),
                    native_snapshot=getattr(body, "_gr_native_skeleton_snapshot", None),
                    overwrite=True,
                    metadata={"workflow": "headless_body_workflow.export_scene"},
                    writer_cls=_import_mdl_binary_writer(),
                    loader=_reload_exported,
                )
            )
            if not tx.succeeded:
                messages = [
                    issue.message
                    for issue in tx.export_job_result.validation_report.issues
                    if getattr(issue, "message", "")
                ]
                raise RuntimeError("; ".join(messages) or "Character export transaction failed")
        elif fmt_key == "fbx":
            fbx_cls, _gltf_cls, _obj_cls = _import_mesh_exporters()
            ok = fbx_cls().export(body, out_path)
            if ok is False:
                raise RuntimeError("FBX exporter returned False")
        elif fmt_key == "gltf":
            _fbx_cls, gltf_cls, _obj_cls = _import_mesh_exporters()
            ok = gltf_cls().export(body, out_path, binary=True)
            if ok is False:
                raise RuntimeError("glTF exporter returned False")
        elif fmt_key == "obj":
            _fbx_cls, _gltf_cls, obj_cls = _import_mesh_exporters()
            ok = obj_cls().export(body, out_path)
            if ok is False:
                raise RuntimeError("OBJ exporter returned False")
    except Exception as exc:
        log.exception("export_scene: %s writer failed", fmt_key)
        return ExportFormatResult(
            key=fmt_key, label=label, ok=False, path=out_path,
            message=f"{label} export failed: {exc}",
            code="failed",
        )

    return ExportFormatResult(
        key=fmt_key, label=label, ok=True, path=out_path,
        message=f"{label} exported to {out_path}.",
        code="exported",
    )


def export_scene(
    scene: Any,
    *,
    formats: Optional[List[str]] = None,
    out_dir: str = "",
    write_sidecar: bool = True,
    skip_validation: bool = False,
) -> ExportResult:
    """Workflow Step 6b — write the scene to disk in the requested formats.

    Parameters
    ----------
    scene            : Scene whose ``PartSlot.HEADLESS_BODY`` must be
                       populated.
    formats          : Subset of ``{"kotor", "fbx", "gltf", "obj"}`` —
                       per-format results are returned in order.
    out_dir          : Destination directory (created if missing).
    write_sidecar    : When True (default), write ``<resref>.ghostrig.json``
                       to the output directory via
                       :meth:`SceneIO.write_sidecar`.
    skip_validation  : When True, bypass the UI/workflow validation gate only.
                       Reserved for "Export anyway" UX after the user
                       has acknowledged warnings.  The staged KOTOR
                       transaction still runs Character Builder preflight,
                       including the native-template-final rig-state gate.

    Notes
    -----
    M10/T1001 routes the selected formats to the real in-tree writers.
    The sidecar is written last so a failed interchange export can still
    leave a recoverable GhostRigger scene definition behind.
    """
    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    body = entry.model if entry is not None else None
    if body is None:
        return ExportResult(
            message="No body model loaded — nothing to export.",
            code="no_body",
        )

    if not out_dir:
        return ExportResult(
            message="No output directory supplied.",
            code="no_out_dir",
        )

    requested = list(formats or [])
    if not requested and not write_sidecar:
        return ExportResult(
            out_dir=out_dir,
            message="Nothing requested — pick at least one format or "
                    "enable the sidecar JSON.",
            code="no_formats",
        )

    gate: Optional[ValidateForExportResult] = None
    # Optional pre-flight validation gate.
    if not skip_validation:
        gate = validate_for_export(scene, strict=True)
        if not gate.ok:
            return ExportResult(
                out_dir=out_dir,
                message=("Export blocked by validation: "
                         f"{gate.error_count} error(s). "
                         f"Codes: {', '.join(gate.blocking_codes)}"),
                code="blocked",
            )

    # Ensure output directory exists.
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        return ExportResult(
            out_dir=out_dir,
            message=f"Cannot create output directory: {exc}",
            code="no_out_dir",
        )

    resref = (entry.resref or getattr(body, "name", "") or "untitled").lower()
    # Keep only filesystem-safe characters in the resref stem.
    resref = "".join(c for c in resref if c.isalnum() or c in ("_", "-")) \
        or "untitled"

    # Build the per-format dispatch list (preserving caller order).
    label_by_key = {key: label for key, label, _exts in EXPORT_FORMATS}
    rows: List[ExportFormatResult] = []
    for fmt_key in requested:
        if fmt_key not in label_by_key:
            rows.append(ExportFormatResult(
                key=fmt_key, label=fmt_key, ok=False,
                message=f"Unknown format '{fmt_key}'.",
                code="failed",
            ))
            continue
        rows.append(
            _export_single_format(
                scene, body, fmt_key,
                label_by_key[fmt_key], out_dir, resref,
            )
        )

    tex_export = export_external_textures(scene, body, out_dir)
    if tex_export.get("written") or tex_export.get("missing"):
        rows.append(ExportFormatResult(
            key="textures",
            label="External texture TGAs",
            ok=bool(tex_export.get("ok")),
            path=out_dir,
            message=str(tex_export.get("message", "")),
            code="exported" if tex_export.get("ok") else "failed",
        ))

    # Sidecar v2 metadata. Stored on the scene before SceneIO writes so the
    # .ghostrig.json records exactly what this export attempt produced.
    try:
        import datetime as _dt
        export_stamp = _dt.datetime.now(
            _dt.timezone.utc).isoformat().replace("+00:00", "Z")
        metadata = getattr(scene, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(scene, "metadata", metadata)
        metadata["export_results"] = [
            {
                "format": row.key,
                "label": row.label,
                "ok": bool(row.ok),
                "path": row.path,
                "code": row.code,
                "message": row.message,
            }
            for row in rows
        ]
        metadata["export_timestamps"] = {
            **dict(metadata.get("export_timestamps", {}) or {}),
            "last_export_at": export_stamp,
        }
        if gate is not None:
            metadata["validation_report"] = {
                "ok": bool(gate.ok),
                "code": gate.code,
                "error_count": gate.error_count,
                "warning_count": gate.warning_count,
                "info_count": gate.info_count,
                "blocking_codes": list(gate.blocking_codes),
            }
    except Exception:                                      # pragma: no cover
        log.debug("export_scene: could not attach sidecar v2 metadata",
                  exc_info=True)

    # Sidecar JSON — written last so even partial-failure exports
    # leave a valid scene-definition file behind.
    sidecar_path = ""
    if write_sidecar:
        try:
            sio = _import_scene_io()
            anchor = os.path.join(out_dir, f"{resref}.mdl")
            sidecar_path = sio.write_sidecar(scene, anchor)
        except Exception as exc:                            # pragma: no cover
            log.exception("export_scene: write_sidecar raised")
            rows.append(ExportFormatResult(
                key="sidecar", label="Scene JSON sidecar", ok=False,
                message=f"Sidecar write failed: {exc}",
                code="failed",
            ))

    any_ok = any(r.ok for r in rows) or bool(sidecar_path)
    if rows and not any_ok and not sidecar_path:
        return ExportResult(
            formats=rows, sidecar_path="",
            out_dir=out_dir,
            message="Every requested format failed.",
            code="all_failed",
        )

    # Build summary message.
    ok_count = sum(1 for r in rows if r.ok)
    fail_count = sum(1 for r in rows if not r.ok)
    parts = []
    if ok_count:
        parts.append(f"{ok_count} written")
    if fail_count:
        parts.append(f"{fail_count} failed")
    if sidecar_path:
        parts.append("sidecar JSON OK")
    summary = "; ".join(parts) or "nothing to export"

    return ExportResult(
        ok=True,
        formats=rows,
        sidecar_path=sidecar_path,
        out_dir=out_dir,
        message=f"Export to {out_dir}: {summary}.",
        code="exported",
    )


__all__ = [
    "BodyGuideEditResult",
    "BodyGuideEditCommand",
    "BodyGuideEditHistory",
    "BodyRigGenerateResult",
    "BodyRigGuidesResult",
    "CheckActorResult",
    "CheckModelResult",
    "EXPORT_FORMATS",
    "ExportFormatResult",
    "ExportResult",
    "HAND_BONES",
    "HandRigResult",
    "LaunchWorkflowResult",
    "LoadResult",
    "MOTION_SOURCE_IMPORTED",
    "MOTION_SOURCE_INHERITED",
    "MOTION_SOURCE_LABELS",
    "MOTION_SOURCE_MODEL",
    "MOTION_SOURCE_ROM",
    "MotionAssignmentResult",
    "PC_SUPERMODEL_OPTIONS",
    "PREVIEW_ANIMATIONS",
    "REQUIRED_PREVIEW_ANIMATIONS",
    "ValidateForExportResult",
    "apply_body_guide_positions",
    "apply_hand_masks",
    "assign_motion_source",
    "available_animation_library",
    "available_preview_animations",
    "apply_external_model_fit_adjustment",
    "check_model",
    "default_export_formats_for_mode",
    "export_scene",
    "generate_skeleton",
    "inspect_external_model_fit",
    "load_body",
    "load_file_filter",
    "motion_assignment_options",
    "normalize_kotor_game_tag",
    "normalize_external_model_for_kotor",
    "place_body_guides",
    "place_hand_guides",
    "play_preview_animation",
    "reference_model_height",
    "record_body_guide_edit",
    "redo_body_guide_edit",
    "run_external_mesh_launch_workflow",
    "run_external_mesh_native_template_launch_workflow",
    "run_rom_test",
    "stop_preview_animation",
    "undo_body_guide_edit",
    "supported_load_extensions",
    "update_body_guide",
    "update_body_guide_from_node",
    "validate_for_export",
]
