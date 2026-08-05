"""Portable, revisioned spatial snapshots for the Ghost Studio scene.

This module is Scene-owned and deliberately Qt-free.  GUI adapters may supply
viewport, grid, and capture observations, but scene identities and transforms
are serialized here so every automation surface uses the same semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import islice
import json
import math
from typing import Any, Iterable, Mapping


SNAPSHOT_SCHEMA_VERSION = "1.0"
SPATIAL_API_VERSION = "ghoststudio-spatial/v1"
WORLD_FRAME_ID = "ghoststudio-world"
MAX_SPATIAL_ENTITIES = 1024
MAX_SPATIAL_TEXT_LENGTH = 512
MAX_MATERIALS_PER_ENTITY = 64
_GUI_READINESS_EVIDENCE_GAPS = frozenset(
    {
        "gui-main-thread-unobserved",
        "window-not-visible",
        "window-minimized",
        "viewport-state-unavailable",
        "viewport-not-visible",
        "grid-state-unavailable",
        "gui-readiness-callback-unavailable",
        "gui-readiness-check-failed",
    }
)

_METERS_PER_UNIT = {
    "mm": 0.001,
    "millimeter": 0.001,
    "millimeters": 0.001,
    "millimetre": 0.001,
    "millimetres": 0.001,
    "cm": 0.01,
    "centimeter": 0.01,
    "centimeters": 0.01,
    "centimetre": 0.01,
    "centimetres": 0.01,
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "metre": 1.0,
    "metres": 1.0,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
    "feet": 0.3048,
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _revision(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def _finite_vector(
    value: Any,
    *,
    length: int,
    field_name: str,
) -> list[float]:
    try:
        items = list(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a finite vector") from exc
    if len(items) < length:
        raise ValueError(f"{field_name} must contain {length} values")
    result = [float(item) for item in items[:length]]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field_name} must contain only finite values")
    return result


def _object_value(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _bounded_text(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool = True,
    maximum: int = MAX_SPATIAL_TEXT_LENGTH,
) -> str:
    text = str(value or "")
    if not allow_empty and not text.strip():
        raise ValueError(f"{field_name} is required")
    if len(text) > maximum:
        raise ValueError(f"{field_name} exceeds the spatial text bound")
    return text


def _euler_zyx_degrees_matrix(
    position: list[float],
    rotation: list[float],
    scale: list[float],
) -> list[list[float]]:
    """Compose T*Rz*Ry*Rx*S as a row-major, column-vector matrix."""

    rx, ry, rz = (math.radians(value) for value in rotation)
    cx, sx = math.cos(rx * 0.5), math.sin(rx * 0.5)
    cy, sy = math.cos(ry * 0.5), math.sin(ry * 0.5)
    cz, sz = math.cos(rz * 0.5), math.sin(rz * 0.5)
    qx = sx * cy * cz + cx * sy * sz
    qy = cx * sy * cz - sx * cy * sz
    qz = cx * cy * sz + sx * sy * cz
    qw = cx * cy * cz - sx * sy * sz

    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    sx_value, sy_value, sz_value = scale
    return [
        [
            (1.0 - 2.0 * (yy + zz)) * sx_value,
            (2.0 * (xy - wz)) * sy_value,
            (2.0 * (xz + wy)) * sz_value,
            position[0],
        ],
        [
            (2.0 * (xy + wz)) * sx_value,
            (1.0 - 2.0 * (xx + zz)) * sy_value,
            (2.0 * (yz - wx)) * sz_value,
            position[1],
        ],
        [
            (2.0 * (xz - wy)) * sx_value,
            (2.0 * (yz + wx)) * sy_value,
            (1.0 - 2.0 * (xx + yy)) * sz_value,
            position[2],
        ],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _bounds(metadata: Mapping[str, Any]) -> dict[str, list[float]] | None:
    candidate = metadata.get("bounds")
    if not isinstance(candidate, Mapping):
        return None
    try:
        minimum = _finite_vector(
            candidate.get("minimum"),
            length=3,
            field_name="bounds.minimum",
        )
        maximum = _finite_vector(
            candidate.get("maximum"),
            length=3,
            field_name="bounds.maximum",
        )
    except (TypeError, ValueError):
        return None
    if any(low > high for low, high in zip(minimum, maximum)):
        return None
    return {"minimum": minimum, "maximum": maximum}


def _entity(
    scene_object: object,
    *,
    include_bounds: bool,
    include_selection: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stable_id = _bounded_text(
        _object_value(scene_object, "id", ""),
        field_name="entity.stableId",
        allow_empty=False,
        maximum=256,
    ).strip()
    transform = _object_value(scene_object, "transform")
    if transform is None:
        raise ValueError(f"Scene object {stable_id} has no transform")
    position = _finite_vector(
        _object_value(transform, "position", (0.0, 0.0, 0.0)),
        length=3,
        field_name=f"{stable_id}.transform.position",
    )
    rotation = _finite_vector(
        _object_value(transform, "rotation", (0.0, 0.0, 0.0)),
        length=3,
        field_name=f"{stable_id}.transform.rotation",
    )
    scale = _finite_vector(
        _object_value(transform, "scale", (1.0, 1.0, 1.0)),
        length=3,
        field_name=f"{stable_id}.transform.scale",
    )
    if any(abs(component) <= 1e-12 for component in scale):
        raise ValueError(f"Scene object {stable_id} has a singular scale")
    matrix = _euler_zyx_degrees_matrix(position, rotation, scale)

    pivot_object = _object_value(scene_object, "pivot")
    pivot = {
        "coordinateFrameId": WORLD_FRAME_ID,
        "semanticSpace": "local",
        "position": _finite_vector(
            _object_value(pivot_object, "position_local", (0.0, 0.0, 0.0)),
            length=3,
            field_name=f"{stable_id}.pivot.position_local",
        ),
        "rotationEulerDegreesXYZ": _finite_vector(
            _object_value(pivot_object, "rotation_local", (0.0, 0.0, 0.0)),
            length=3,
            field_name=f"{stable_id}.pivot.rotation_local",
        ),
        "enabled": bool(_object_value(pivot_object, "enabled", True)),
    }
    metadata_value = _object_value(scene_object, "metadata", {})
    metadata = metadata_value if isinstance(metadata_value, Mapping) else {}
    material_value = _object_value(scene_object, "material_overrides", {})
    if isinstance(material_value, Mapping):
        if len(material_value) > MAX_MATERIALS_PER_ENTITY:
            raise ValueError(
                f"Scene object {stable_id} exceeds the material work bound"
            )
        materials = sorted(
            {
                _bounded_text(
                    value,
                    field_name=f"{stable_id}.material",
                    allow_empty=False,
                    maximum=256,
                )
                for value in material_value.values()
                if str(value or "").strip()
            }
        )
    else:
        materials = []
    escaped_id = stable_id.replace("~", "~0").replace("/", "~1")
    entity: dict[str, Any] = {
        "stableId": stable_id,
        "path": f"/scene/{escaped_id}",
        "type": _bounded_text(
            _object_value(scene_object, "object_type", "object"),
            field_name=f"{stable_id}.type",
            allow_empty=False,
            maximum=128,
        ),
        "visible": bool(_object_value(scene_object, "visible", True)),
        "locked": bool(_object_value(scene_object, "locked", False)),
        "coordinateFrameId": WORLD_FRAME_ID,
        "localMatrix": matrix,
        "worldMatrix": matrix,
        "pivot": pivot,
        "transformSemantics": {
            "matrixLayout": "row-major",
            "vectorConvention": "column-vector",
            "composition": "T*Rz*Ry*Rx*S",
            "rotationInput": "Euler XYZ degrees",
        },
    }
    selected = bool(_object_value(scene_object, "selected", False))
    if include_selection:
        entity["selected"] = selected
    bounds = _bounds(metadata)
    if include_bounds and bounds is not None:
        entity["bounds"] = bounds
    if materials:
        entity["materials"] = materials

    # Keep selection and future presentation-only fields out of scene identity.
    revision_projection = {
        "stableId": entity["stableId"],
        "path": entity["path"],
        "type": entity["type"],
        "visible": entity["visible"],
        "locked": entity["locked"],
        "coordinateFrameId": entity["coordinateFrameId"],
        "localMatrix": entity["localMatrix"],
        "worldMatrix": entity["worldMatrix"],
        "pivot": entity["pivot"],
        "transformSemantics": entity["transformSemantics"],
        "name": _bounded_text(
            _object_value(scene_object, "name", ""),
            field_name=f"{stable_id}.name",
        ),
        "groupId": _bounded_text(
            _object_value(scene_object, "group_id", ""),
            field_name=f"{stable_id}.groupId",
            maximum=256,
        ),
    }
    if bounds is not None:
        revision_projection["bounds"] = bounds
    if materials:
        revision_projection["materials"] = materials
    return entity, revision_projection


def _scene_objects(scene: object) -> Iterable[object]:
    objects = getattr(scene, "objects", None)
    model_instances = getattr(scene, "model_instances", None)
    for collection in (objects, model_instances):
        if collection is None:
            continue
        try:
            collection_size = len(collection)
        except TypeError:
            continue
        if collection_size > MAX_SPATIAL_ENTITIES:
            raise ValueError(
                "Spatial scene exceeds the entity work bound before traversal"
            )
    all_objects = getattr(scene, "all_objects", None)
    if callable(all_objects):
        source = all_objects()
    else:
        source = objects or ()
    rows = list(islice(iter(source), MAX_SPATIAL_ENTITIES + 1))
    if len(rows) > MAX_SPATIAL_ENTITIES:
        raise ValueError("Spatial scene exceeds the entity work bound")
    return rows


def _meters_per_unit(scene: object) -> float:
    units = getattr(scene, "units", {}) or {}
    unit_name = (
        units.get("system_unit", "cm")
        if isinstance(units, Mapping)
        else "cm"
    )
    normalized = str(unit_name or "cm").strip().casefold()
    try:
        return _METERS_PER_UNIT[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported scene system unit: {unit_name}") from exc


def _normalize_viewport(viewport: Mapping[str, Any]) -> dict[str, Any]:
    rectangle = viewport.get("rectangle")
    if not isinstance(rectangle, Mapping):
        raise ValueError("viewport.rectangle is required")
    normalized = {
        "id": str(viewport.get("id") or "main"),
        "rectangle": {
            "x": float(rectangle.get("x", 0.0)),
            "y": float(rectangle.get("y", 0.0)),
            "width": float(rectangle.get("width", 0.0)),
            "height": float(rectangle.get("height", 0.0)),
        },
        "pixelOrigin": str(viewport.get("pixelOrigin") or "top-left"),
        "devicePixelRatio": float(viewport.get("devicePixelRatio", 1.0)),
        "cameraStableId": (
            str(viewport["cameraStableId"])
            if viewport.get("cameraStableId")
            else None
        ),
        "projection": str(viewport.get("projection") or "perspective"),
        "viewMatrix": [
            _finite_vector(row, length=4, field_name="viewport.viewMatrix")
            for row in list(viewport.get("viewMatrix") or ())
        ],
        "projectionMatrix": [
            _finite_vector(
                row,
                length=4,
                field_name="viewport.projectionMatrix",
            )
            for row in list(viewport.get("projectionMatrix") or ())
        ],
        "nearClip": float(viewport.get("nearClip", 0.0)),
        "farClip": float(viewport.get("farClip", 0.0)),
    }
    if (
        not all(
            math.isfinite(value)
            for value in (
                normalized["rectangle"]["x"],
                normalized["rectangle"]["y"],
                normalized["rectangle"]["width"],
                normalized["rectangle"]["height"],
                normalized["devicePixelRatio"],
                normalized["nearClip"],
                normalized["farClip"],
            )
        )
        or normalized["rectangle"]["width"] <= 0
        or normalized["rectangle"]["height"] <= 0
        or normalized["rectangle"]["width"] > 32768
        or normalized["rectangle"]["height"] > 32768
        or normalized["devicePixelRatio"] <= 0
        or normalized["devicePixelRatio"] > 16
        or normalized["pixelOrigin"] not in {"top-left", "bottom-left"}
        or normalized["projection"] not in {"perspective", "orthographic"}
        or len(normalized["viewMatrix"]) != 4
        or len(normalized["projectionMatrix"]) != 4
        or normalized["nearClip"] <= 0
        or normalized["farClip"] <= normalized["nearClip"]
    ):
        raise ValueError("viewport state is incomplete or invalid")
    normalized["revision"] = _revision(normalized)
    return normalized


def _normalize_grid(grid: Mapping[str, Any]) -> dict[str, Any]:
    spacing_value = grid.get("spacing", (10.0, 10.0, 10.0))
    if isinstance(spacing_value, (int, float)):
        spacing_value = (spacing_value, spacing_value, spacing_value)
    spacing = _finite_vector(
        spacing_value,
        length=3,
        field_name="grid.spacing",
    )
    if any(component <= 0 for component in spacing):
        raise ValueError("grid spacing must be positive")
    subdivisions = int(grid.get("subdivisions", 10))
    if subdivisions <= 0 or subdivisions > 1_000_000:
        raise ValueError("grid subdivisions must be positive")
    return {
        "coordinateFrameId": WORLD_FRAME_ID,
        "origin": _finite_vector(
            grid.get("origin", (0.0, 0.0, 0.0)),
            length=3,
            field_name="grid.origin",
        ),
        "spacing": spacing,
        "subdivisions": subdivisions,
        "visible": bool(grid.get("visible", True)),
        "snapEnabled": bool(grid.get("snapEnabled", False)),
    }


def build_scene_spatial_snapshot(
    scene: object,
    *,
    application_version: str,
    captured_at: str | None = None,
    viewport: Mapping[str, Any] | None = None,
    grid: Mapping[str, Any] | None = None,
    capture: Mapping[str, Any] | None = None,
    include_bounds: bool = True,
    include_hierarchy: bool = True,
    include_selection: bool = True,
) -> dict[str, Any]:
    """Build a deterministic semantic snapshot from one KMAX scene."""

    if any(
        not isinstance(value, bool)
        for value in (
            include_bounds,
            include_hierarchy,
            include_selection,
        )
    ):
        raise ValueError("Spatial include flags must be booleans")
    rows = [
        _entity(
            scene_object,
            include_bounds=include_bounds,
            include_selection=include_selection,
        )
        for scene_object in _scene_objects(scene)
    ]
    rows.sort(key=lambda row: row[0]["stableId"])
    entities = [row[0] for row in rows]
    revision_entities = [row[1] for row in rows]
    stable_ids = [row["stableId"] for row in entities]
    if len(stable_ids) != len(set(stable_ids)):
        raise ValueError("Spatial scene object ids must be unique")
    scene_id = _bounded_text(
        getattr(scene, "id", ""),
        field_name="scene.id",
        allow_empty=False,
        maximum=256,
    ).strip()
    scene_revision = _revision(
        {
            "sceneId": scene_id,
            "metersPerUnit": _meters_per_unit(scene),
            "entities": revision_entities,
        }
    )
    timestamp = _bounded_text(
        captured_at
        or datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
        field_name="capturedAt",
        allow_empty=False,
        maximum=64,
    )
    snapshot: dict[str, Any] = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "application": {
            "id": "ghoststudio",
            "version": str(application_version or "unknown"),
            "apiVersion": SPATIAL_API_VERSION,
        },
        "sceneRevision": scene_revision,
        "capturedAt": timestamp,
        "coordinateFrames": [
            {
                "id": WORLD_FRAME_ID,
                "semanticSpace": "world",
                "handedness": "right",
                "metersPerUnit": _meters_per_unit(scene),
                "originMeters": [0.0, 0.0, 0.0],
                "basis": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "upAxis": "+Z",
                "forwardAxis": "+Y",
            }
        ],
        "entities": entities,
        "evidence": [
            {
                "kind": "semantic-api",
                "claim": (
                    "Stable scene identities, visibility, local transforms, "
                    "and pivots were observed from the KMAX scene API."
                ),
                "epistemicStatus": "observed",
                "confidence": 1.0,
            },
            {
                "kind": "derived-calculation",
                "claim": (
                    "Scene revisions and row-major matrices were derived from "
                    "the observed semantic scene values."
                ),
                "epistemicStatus": "inferred",
                "confidence": 0.99,
            },
        ],
    }
    if include_hierarchy:
        # KMAX's group_id is an authored grouping hint, not a parent contract.
        # Report the capability gap explicitly instead of synthesizing parents.
        snapshot["hierarchy"] = {
            "status": "unavailable",
            "reason": "scene-parent-hierarchy-unavailable",
        }
    if include_selection:
        snapshot["selection"] = {
            "mode": "object",
            "stableIds": sorted(
                row["stableId"] for row in entities if row["selected"]
            ),
        }
        snapshot["evidence"].append(
            {
                "kind": "semantic-api",
                "claim": "Object selection was observed from the KMAX scene API.",
                "epistemicStatus": "observed",
                "confidence": 1.0,
            }
        )
    if viewport is not None:
        snapshot["viewports"] = [_normalize_viewport(viewport)]
    if grid is not None:
        snapshot["grid"] = _normalize_grid(grid)
    if capture is not None:
        normalized_capture = dict(capture)
        normalized_capture["sceneRevision"] = scene_revision
        snapshot["capture"] = normalized_capture
    return snapshot


def spatial_evidence_gaps(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Report missing evidence without upgrading screenshot inference to fact."""

    gaps: list[str] = ["scene-parent-hierarchy-unavailable"]
    viewports = snapshot.get("viewports")
    if not isinstance(viewports, list) or not viewports:
        gaps.append("viewport-camera-matrices-unavailable")
    if "grid" not in snapshot:
        gaps.append("grid-state-unavailable")
    if "capture" not in snapshot:
        gaps.append("capture-unavailable")
    entities = snapshot.get("entities")
    if isinstance(entities, list) and any(
        isinstance(entity, Mapping) and "bounds" not in entity
        for entity in entities
    ):
        gaps.append("one-or-more-entity-bounds-unavailable")
    gui_readiness = snapshot.get("guiReadiness")
    if (
        isinstance(gui_readiness, Mapping)
        and gui_readiness.get("ready") is False
    ):
        reason = gui_readiness.get("reason")
        if reason in _GUI_READINESS_EVIDENCE_GAPS and reason not in gaps:
            gaps.append(str(reason))
    return {
        "schema": "ghoststudio-spatial-evidence-gaps/v1",
        "sceneRevision": str(snapshot.get("sceneRevision") or ""),
        "gaps": gaps,
        "screenshotProvesGuiAction": False,
    }
