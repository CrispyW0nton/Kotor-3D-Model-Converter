"""Portable, revisioned spatial snapshots for the Ghost Studio scene.

This module is Scene-owned and deliberately Qt-free.  GUI adapters may supply
viewport, grid, and capture observations, but scene identities and transforms
are serialized here so every automation surface uses the same semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Iterable, Mapping


SNAPSHOT_SCHEMA_VERSION = "1.0"
SPATIAL_API_VERSION = "ghoststudio-spatial/v1"
WORLD_FRAME_ID = "ghoststudio-world"

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


def _entity(scene_object: object) -> tuple[dict[str, Any], dict[str, Any]]:
    stable_id = str(_object_value(scene_object, "id", "") or "").strip()
    if not stable_id:
        raise ValueError("Every spatial scene object requires a stable id")
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
    materials = (
        sorted(
            {
                str(value)
                for value in material_value.values()
                if str(value or "").strip()
            }
        )
        if isinstance(material_value, Mapping)
        else []
    )
    escaped_id = stable_id.replace("~", "~0").replace("/", "~1")
    entity: dict[str, Any] = {
        "stableId": stable_id,
        "path": f"/scene/{escaped_id}",
        # ``group_id`` is not a parent relationship. Reporting it as one would
        # turn an authored grouping hint into false hierarchy evidence.
        "parentStableId": None,
        "type": str(_object_value(scene_object, "object_type", "object") or "object"),
        "visible": bool(_object_value(scene_object, "visible", True)),
        "locked": bool(_object_value(scene_object, "locked", False)),
        "selected": bool(_object_value(scene_object, "selected", False)),
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
    bounds = _bounds(metadata)
    if bounds is not None:
        entity["bounds"] = bounds
    if materials:
        entity["materials"] = materials

    revision_projection = {
        **entity,
        "name": str(_object_value(scene_object, "name", "") or ""),
        "groupId": str(_object_value(scene_object, "group_id", "") or ""),
    }
    return entity, revision_projection


def _scene_objects(scene: object) -> Iterable[object]:
    all_objects = getattr(scene, "all_objects", None)
    if callable(all_objects):
        return list(all_objects())
    return list(getattr(scene, "objects", ()) or ())


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
        normalized["rectangle"]["width"] <= 0
        or normalized["rectangle"]["height"] <= 0
        or normalized["devicePixelRatio"] <= 0
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
    if subdivisions <= 0:
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
) -> dict[str, Any]:
    """Build a deterministic semantic snapshot from one KMAX scene."""

    rows = [_entity(scene_object) for scene_object in _scene_objects(scene)]
    rows.sort(key=lambda row: row[0]["stableId"])
    entities = [row[0] for row in rows]
    revision_entities = [row[1] for row in rows]
    stable_ids = [row["stableId"] for row in entities]
    if len(stable_ids) != len(set(stable_ids)):
        raise ValueError("Spatial scene object ids must be unique")
    scene_id = str(getattr(scene, "id", "") or "").strip()
    if not scene_id:
        raise ValueError("Spatial scene requires a stable scene id")
    scene_revision = _revision(
        {
            "sceneId": scene_id,
            "metersPerUnit": _meters_per_unit(scene),
            "entities": revision_entities,
        }
    )
    timestamp = captured_at or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
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
        "selection": {
            "mode": "object",
            "stableIds": sorted(
                row["stableId"] for row in entities if row["selected"]
            ),
        },
        "evidence": [
            {
                "kind": "semantic-api",
                "claim": (
                    "Stable scene identities, visibility, selection, local "
                    "transforms, and pivots were observed from the KMAX scene API."
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
    return {
        "schema": "ghoststudio-spatial-evidence-gaps/v1",
        "sceneRevision": str(snapshot.get("sceneRevision") or ""),
        "gaps": gaps,
        "screenshotProvesGuiAction": False,
    }
