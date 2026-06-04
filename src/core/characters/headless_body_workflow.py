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
    Step 7  ── Validate +    →  :func:`validate_and_export` (T506)
              Export

Every public function returns a *result dataclass* carrying a structured
``ok`` flag plus a human-readable ``message``.  The Qt window converts
these into bottom-strip banner colours and status-bar messages without
needing to know how the underlying services are wired.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M5/T501-T506.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    return {
        "origin": _vec_as_list(frame.origin),
        "right": _vec_as_list(frame.right),
        "forward": _vec_as_list(frame.forward),
        "up": _vec_as_list(frame.up),
        "height": float(frame.height),
        "confidence": float(frame.confidence),
        "landmarks": dict(frame.landmarks),
        "landmark_sources": dict(frame.landmark_sources),
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


def _load_gltf_or_mesh(path: str, game_version: str) -> Optional[Any]:
    """Load a glTF/GLB/FBX/OBJ via the gltf_importer.auto_import dispatcher."""
    md = _import_model_data()
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
_LEFT_FOOT_ALIASES = ("lfoot_g", "lfootg", "lfoot", "lfoot_t_g", "lfoottg", "leftfoot", "lefttoe")
_RIGHT_FOOT_ALIASES = ("rfoot_g", "rfootg", "rfoot", "rfoot_t_g", "rfoottg", "rightfoot", "righttoe")


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
    confidence = 0.65
    confidence += 0.1 if pelvis is not None else 0.0
    confidence += 0.1 if foot_center is not None else 0.0
    confidence += 0.1 if side_kind == "shoulder" else 0.0
    if prefer_skeleton_landmarks:
        core_sources = {
            landmark_sources.get(role, "")
            for role in ("left", "right", "head", "pelvis", "left_foot", "right_foot")
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
    )


def inspect_external_model_fit(
    model: Any,
    *,
    game_version: str = "K1",
    target_height: Optional[float] = None,
    reference_model: Optional[Any] = None,
    reference_label: str = "",
    fit_override: Optional[Any] = None,
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
    if reference_model is not None and target_frame is None:
        warnings.append(
            "Could not detect a complete humanoid landmark frame on the selected KOTOR base; "
            "falling back to its bounds."
        )
    elif target_frame is not None and target_frame.confidence < 0.75:
        warnings.append(
            f"KOTOR base landmark confidence is low ({target_frame.confidence:.2f})."
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
    elif source_frame is not None and target_frame is not None:
        target = float(target_height or reference_height or target_frame.height)
        scale = target / source_frame.height if source_frame.height > 1.0e-6 else 1.0
        policy = "bone_landmark_basis"
        source_height = source_frame.height
        scale_basis = "reference_bounds_height" if reference_height > 0.01 else "bone_landmark_height"
        vertical_axis = "bone_landmarks"
        report_source_frame = source_frame
        report_target_frame = target_frame
    else:
        scale = fallback_target_height / fallback_source_height
        policy = "selected_reference_bounds" if reference_bounds is not None else "origin_height"
        source_height = fallback_source_height
        scale_basis = "bounds_height"
        vertical_axis = ("x", "y", "z")[vertical_axis_index]
        report_source_frame = source_frame
        report_target_frame = target_frame

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
        fit_transform = _fit_transform_metadata(
            policy=policy,
            scale=scale,
            rotation_matrix=_basis_rotation(report_source_frame, report_target_frame),
            source_origin=report_source_frame.origin,
            target_origin=report_target_frame.origin,
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
        "target_height": float(
            target_height
            or reference_height
            or (target_frame.height if target_frame is not None else fallback_target_height)
        ),
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
) -> Dict[str, Any]:
    linear_matrix = _scale_matrix(rotation_matrix, scale)
    translation = _translation_for_affine(
        linear_matrix,
        source_origin,
        target_origin,
    )
    return {
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
    )

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
        target = float(target_height or reference_height or transform_target_frame.height)
        scale = target / transform_source_frame.height if transform_source_frame.height > 1.0e-6 else 1.0
        rotation = _basis_rotation(transform_source_frame, transform_target_frame)
        fit_transform = _fit_transform_metadata(
            policy=transform_policy,
            scale=scale,
            rotation_matrix=rotation,
            source_origin=transform_source_frame.origin,
            target_origin=transform_target_frame.origin,
        )

        def transform_point(point: Vec3) -> Vec3:
            rel = _vec_scale(_vec_sub(point, transform_source_frame.origin), scale)
            return _vec_add(transform_target_frame.origin, _mat_vec(rotation, rel))

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
            "offset": _vec_sub(transform_target_frame.origin, _mat_vec(rotation, _vec_scale(transform_source_frame.origin, scale))),
            "target_center_xy": (transform_target_frame.origin[0], transform_target_frame.origin[1]),
            "target_ground_z": transform_target_frame.origin[2],
            "external_world_positions_fit": True,
            "fit_policy": transform_policy,
            "scale_basis": (
                transform_scale_basis
                if transform_scale_basis
                else ("reference_bounds_height" if reference_height > 0.01 else "bone_landmark_height")
            ),
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


def _mark_external_import(model: Any, source_path: str) -> None:
    """Tag external DCC meshes as temporary payloads, not export DAG authority."""
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
    metadata["external_import"] = {
        "source_path": str(source_path or ""),
        "disable_kotor_uv_seam_fix": True,
    }
    for node in list(getattr(model, "all_nodes", lambda: [])() or []):
        if getattr(node, "vertices", None) and getattr(node, "uvs", None):
            setattr(node, "_external_imported", True)


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
    if detected == md.CharacterMode.HEADLESS_BODY:
        return LoadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=f"Loaded headless body: {resref} ({Path(path).name})",
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
           f"(expected Headless Body).")
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


def generate_skeleton(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    guides: Optional[Dict[str, Any]] = None,
    smooth_iterations: int = 2,
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
        return BodyRigGenerateResult(
            ok=False, bone_count=bone_count,
            message=f"Skin painting failed: {exc}",
            code="skin_failed",
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
# QC-ing a freshly-rigged body.
PREVIEW_ANIMATIONS: Tuple[Tuple[str, str], ...] = (
    ("Idle",  "pause1"),
    ("Walk",  "walk"),
    ("Run",   "run"),
    ("Talk",  "tlknorm"),
    ("Dodge", "dodge"),
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
        setattr(body, "supermodel", selected)
        state["supermodel"] = selected
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
    required_preview_names = [name for _label, name in PREVIEW_ANIMATIONS]
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
        if str(state.get("source") or "") != MOTION_SOURCE_ROM:
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "ROM_CLIP_MISSING",
                "Creature export requires a generated ROM clip to prove the rig extremes.",
            ))

    return issues


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
    """End-to-end external-mesh launch proof result (M12/T1205)."""

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
) -> Tuple[bool, List[str], int, int, str, str]:
    """Check the KOTOR-critical facts after reloading an exported body."""
    if model is None:
        return False, [], 0, 0, "", "Reloaded model is empty."

    nodes = _model_nodes(model)
    names = [str(getattr(n, "name", "") or "") for n in nodes]
    names_lower = {n.lower() for n in names}
    hooks = [n for n in names if n.lower() in {"headhook", "rhand", "lhand_g"}]
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
    for required in ("headhook", "rhand"):
        if required not in names_lower:
            problems.append(f"Missing required hook/node: {required}")
    if mesh_count <= 0:
        problems.append("Reloaded export has no mesh nodes.")
    if skin_count <= 0:
        problems.append("Reloaded export has no skinned mesh data.")
    if expected_supermodel and supermodel.lower() != expected_supermodel.lower():
        problems.append(
            f"Supermodel mismatch: expected {expected_supermodel}, got {supermodel or 'NULL'}."
        )
    return (not problems), hooks, mesh_count, skin_count, supermodel, "; ".join(problems)


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
    scene.assign(
        md.PartSlot.HEADLESS_BODY,
        rigged_model,
        resref=load.resref or _resref_from_path(mesh_path),
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

    ok, hooks, mesh_count, skin_count, supermodel, problems = (
        _verify_launch_reloaded_model(
            reloaded,
            expected_supermodel=motion.supermodel or motion_supermodel,
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
        message=(
            "Launch workflow proof passed."
            if ok else
            f"Launch workflow reload verification failed: {problems}"
        ),
        code="launch_verified" if ok else "verification_failed",
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
