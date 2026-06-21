"""Native KotOR skeleton snapshot helpers for Character Builder.

Character Studio must treat the selected KotOR base model as the authority for
node names, parent paths, hooks, helper meshes, and animation inheritance.  This
module captures that information as a lightweight, JSON-friendly contract before
later workflow steps hide, strip, or replace viewport geometry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .kotor_constants import KOTOR_NATIVE_RESREF_MAX_LEN


KOTOR_SOCKET_CATEGORIES: dict[str, str] = {
    "headhook": "head",
    "cutscenehead": "head",
    "gogglehook": "headgear",
    "maskhook": "headgear",
    "revmask1hook": "headgear",
    "revmask2hook": "headgear",
    "rhand": "right_hand",
    "rhand_g": "right_hand",
    "lhand": "left_hand",
    "lhand_g": "left_hand",
    "lightsaberhook": "lightsaber",
    "deflecthook": "combat_helper",
    "impact": "combat_helper",
    "impact_bolt": "combat_helper",
    "handconjure": "combat_helper",
    "headconjure": "combat_helper",
    "camerahook": "camera",
    "freelookhook": "camera",
}


KOTOR_EXPORT_HELPER_NAMES: set[str] = {
    "rootdummy",
    "cutscenedummy",
    "talkdummy",
    "torsocam",
    "rcollar_dum",
    "lcollar_dum",
}


@dataclass(frozen=True)
class NativeNodeSnapshot:
    """Read-only facts about one node in a native KotOR model hierarchy."""

    name: str
    parent_name: str | None
    parent_path: tuple[str, ...]
    full_path: tuple[str, ...]
    child_names: tuple[str, ...]
    flags: int | None
    type_label: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    is_mesh: bool
    is_skin: bool
    is_dummy: bool
    render: bool
    has_geometry: bool
    vertex_count: int
    face_count: int
    texture: str
    socket_category: str | None = None
    export_role: str = "node"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NativeNodeSnapshot":
        payload = dict(data)
        for key in ("parent_path", "full_path", "child_names", "position", "rotation"):
            if key in payload and payload[key] is not None:
                payload[key] = tuple(payload[key])
        return cls(**payload)


@dataclass(frozen=True)
class NativeSkeletonSnapshot:
    """Native hierarchy contract captured from a selected base KotOR model."""

    model_name: str
    game: str
    supermodel: str
    classification: str
    model_type: int | None
    node_count: int
    mesh_node_count: int
    skin_node_count: int
    hook_names: tuple[str, ...]
    nodes: tuple[NativeNodeSnapshot, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["nodes"] = [node.to_dict() for node in self.nodes]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NativeSkeletonSnapshot":
        payload = dict(data)
        payload["hook_names"] = tuple(payload.get("hook_names") or ())
        payload["nodes"] = tuple(
            NativeNodeSnapshot.from_dict(node) for node in payload.get("nodes", ())
        )
        payload["metadata"] = dict(payload.get("metadata") or {})
        return cls(**payload)

    def node_names(self) -> tuple[str, ...]:
        return tuple(node.name for node in self.nodes)


def classify_native_socket_name(name: str) -> str | None:
    """Return the Character Builder socket category for an exact KotOR node name."""

    return KOTOR_SOCKET_CATEGORIES.get(str(name or "").strip().lower())


def capture_native_skeleton_snapshot(
    model: Any,
    *,
    game: str | None = None,
    include_mesh_stats: bool = True,
) -> NativeSkeletonSnapshot:
    """Capture exact native hierarchy facts from a KotOR model.

    The snapshot preserves node-name casing and parent paths.  It does not mutate
    the model and it does not decide which nodes should be hidden in the viewport.
    """

    nodes = list(_iter_model_nodes(model))
    snapshots: list[NativeNodeSnapshot] = []
    for node in nodes:
        snapshots.append(_snapshot_node(node, include_mesh_stats=include_mesh_stats))

    hooks = tuple(node.name for node in snapshots if node.socket_category)
    socket_summary: dict[str, list[str]] = {}
    for node in snapshots:
        if node.socket_category:
            socket_summary.setdefault(node.socket_category, []).append(node.name)
    metadata = {
        "source_mdl_path": str(getattr(model, "mdl_path", "") or ""),
        "source_mdx_path": str(getattr(model, "mdx_path", "") or ""),
        "source_resref": str(getattr(model, "_gr_source_resref", "") or ""),
        "requested_resref": str(getattr(model, "_gr_requested_resref", "") or ""),
        "target_resref": str(getattr(model, "_gr_target_resref", "") or ""),
        "variant_source_resref": str(getattr(model, "_gr_variant_source_resref", "") or ""),
        "variant_resolution": str(getattr(model, "_gr_variant_resolution", "") or ""),
        "source_game": str(getattr(model, "_gr_source_game", "") or ""),
        "source_layer": str(getattr(model, "_gr_source_layer", "") or ""),
        "animation_count": len(getattr(model, "animations", []) or []),
        "socket_categories": {
            category: tuple(names)
            for category, names in sorted(socket_summary.items())
        },
        "captured_for": "character_builder_native_dag",
    }

    return NativeSkeletonSnapshot(
        model_name=str(getattr(model, "name", "") or ""),
        game=str(game or _game_label(model) or "unknown"),
        supermodel=str(getattr(model, "supermodel", "") or "NULL"),
        classification=str(getattr(model, "classification", "") or ""),
        model_type=_safe_int(getattr(model, "model_type", None)),
        node_count=len(snapshots),
        mesh_node_count=sum(1 for node in snapshots if node.is_mesh),
        skin_node_count=sum(1 for node in snapshots if node.is_skin),
        hook_names=hooks,
        nodes=tuple(snapshots),
        metadata=metadata,
    )


def snapshot_node_paths(snapshot: NativeSkeletonSnapshot) -> dict[str, tuple[str, ...]]:
    """Return exact-case node name -> full path mapping for a snapshot."""

    return {node.name: node.full_path for node in snapshot.nodes}


def find_snapshot_node(
    snapshot: NativeSkeletonSnapshot,
    name: str,
    *,
    case_sensitive: bool = True,
) -> NativeNodeSnapshot | None:
    """Find a node snapshot by name, preserving exact-case lookup by default."""

    if case_sensitive:
        for node in snapshot.nodes:
            if node.name == name:
                return node
        return None

    wanted = str(name).lower()
    for node in snapshot.nodes:
        if node.name.lower() == wanted:
            return node
    return None


def build_native_skeleton_structural_diff(
    snapshot: NativeSkeletonSnapshot,
    model: Any,
    *,
    payload_mesh_names: Iterable[str] = (),
    transform_tolerance: float = 1.0e-6,
) -> dict[str, Any]:
    """Compare a captured native DAG contract with a current rigged model."""

    current_raw_nodes = list(_iter_model_nodes(model))
    current_nodes = [
        _snapshot_node(node, include_mesh_stats=True)
        for node in current_raw_nodes
    ]
    snapshot_by_path = {node.full_path: node for node in snapshot.nodes}
    current_by_path = {node.full_path: node for node in current_nodes}
    snapshot_paths = set(snapshot_by_path)
    current_paths = set(current_by_path)
    payload_names = {str(name or "") for name in payload_mesh_names}

    preserved_paths = sorted(snapshot_paths & current_paths)
    missing_paths = sorted(snapshot_paths - current_paths)
    added_paths = sorted(current_paths - snapshot_paths)

    changed_transforms: list[dict[str, Any]] = []
    for path in preserved_paths:
        before = snapshot_by_path[path]
        after = current_by_path[path]
        position_changed = not _tuple_close(
            before.position,
            after.position,
            transform_tolerance,
        )
        rotation_changed = not _tuple_close(
            before.rotation,
            after.rotation,
            transform_tolerance,
        )
        if not position_changed and not rotation_changed:
            continue
        record: dict[str, Any] = {"name": after.name, "path": list(path)}
        if position_changed:
            record["position"] = {
                "snapshot": list(before.position),
                "current": list(after.position),
            }
        if rotation_changed:
            record["rotation"] = {
                "snapshot": list(before.rotation),
                "current": list(after.rotation),
            }
        changed_transforms.append(record)

    missing_hooks = [
        {
            "name": snapshot_by_path[path].name,
            "path": list(path),
            "socket_category": snapshot_by_path[path].socket_category,
        }
        for path in missing_paths
        if snapshot_by_path[path].socket_category
    ]
    skin_rows = [
        _skin_row_record(node, payload_names=payload_names)
        for node in current_raw_nodes
        if _has_skin_rows(node)
    ]

    return {
        "schema": "ghostrigger.native_skeleton_structural_diff.v1",
        "model_name": str(getattr(model, "name", "") or ""),
        "snapshot_model_name": snapshot.model_name,
        "payload_mesh_names": sorted(payload_names),
        "summary": {
            "snapshot_node_count": len(snapshot.nodes),
            "current_node_count": len(current_nodes),
            "preserved_node_count": len(preserved_paths),
            "missing_node_count": len(missing_paths),
            "added_node_count": len(added_paths),
            "changed_transform_count": len(changed_transforms),
            "missing_hook_count": len(missing_hooks),
            "skin_mesh_count": len(skin_rows),
        },
        "preserved_nodes": [list(path) for path in preserved_paths],
        "missing_nodes": [_node_diff_record(snapshot_by_path[path]) for path in missing_paths],
        "added_nodes": [_node_diff_record(current_by_path[path]) for path in added_paths],
        "changed_transforms": changed_transforms,
        "missing_hooks": missing_hooks,
        "skin_row_counts": skin_rows,
    }


def native_skeleton_fingerprint_payload(
    snapshot: NativeSkeletonSnapshot,
) -> dict[str, Any]:
    """Return the stable native-DAG payload used for snapshot fingerprints.

    The fingerprint is proof of the KOTOR hierarchy contract, not proof of the
    local filesystem path that supplied it.  Volatile paths are therefore
    excluded, while selected resref/game/variant facts are kept because they
    define which native model contract the Character Builder used.
    """

    metadata = dict(snapshot.metadata or {})
    stable_metadata = {
        key: metadata.get(key)
        for key in (
            "source_resref",
            "requested_resref",
            "target_resref",
            "variant_source_resref",
            "variant_resolution",
            "source_game",
            "source_layer",
            "captured_for",
        )
        if metadata.get(key) not in (None, "")
    }
    return {
        "schema": "ghostrigger.native_skeleton_snapshot.v1",
        "model_name": snapshot.model_name,
        "game": snapshot.game,
        "supermodel": snapshot.supermodel,
        "classification": snapshot.classification,
        "model_type": snapshot.model_type,
        "node_count": snapshot.node_count,
        "mesh_node_count": snapshot.mesh_node_count,
        "skin_node_count": snapshot.skin_node_count,
        "hook_names": list(snapshot.hook_names),
        "metadata": stable_metadata,
        "nodes": [
            {
                "name": node.name,
                "parent_name": node.parent_name,
                "parent_path": list(node.parent_path),
                "full_path": list(node.full_path),
                "child_names": list(node.child_names),
                "flags": node.flags,
                "type_label": node.type_label,
                "is_mesh": node.is_mesh,
                "is_skin": node.is_skin,
                "is_dummy": node.is_dummy,
                "render": node.render,
                "has_geometry": node.has_geometry,
                "vertex_count": node.vertex_count,
                "face_count": node.face_count,
                "texture": node.texture,
                "socket_category": node.socket_category,
                "export_role": node.export_role,
            }
            for node in snapshot.nodes
        ],
    }


def native_skeleton_fingerprint(snapshot: NativeSkeletonSnapshot) -> str:
    """Return a SHA-256 digest for the selected native KOTOR DAG contract."""

    payload = native_skeleton_fingerprint_payload(snapshot)
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_node(node: Any, *, include_mesh_stats: bool) -> NativeNodeSnapshot:
    flags = _safe_int(getattr(node, "flags", None))
    name = str(getattr(node, "name", "") or "")
    socket_category = classify_native_socket_name(name)
    child_names = tuple(
        str(getattr(child, "name", "") or "") for child in (getattr(node, "children", []) or [])
    )
    vertices = list(getattr(node, "vertices", []) or []) if include_mesh_stats else []
    faces = list(getattr(node, "faces", []) or []) if include_mesh_stats else []
    has_geometry = bool(vertices or faces)
    is_mesh = bool(getattr(node, "is_mesh", False))
    is_skin = bool(getattr(node, "is_skin", False))
    is_dummy = bool(getattr(node, "is_dummy", False))

    return NativeNodeSnapshot(
        name=name,
        parent_name=_parent_name(node),
        parent_path=_parent_path(node),
        full_path=_full_path(node),
        child_names=child_names,
        flags=flags,
        type_label=str(getattr(node, "type_label", "") or "unknown"),
        position=_float_tuple(getattr(node, "position", (0.0, 0.0, 0.0)), 3, 0.0),
        rotation=_float_tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)), 4, 0.0, last_default=1.0),
        is_mesh=is_mesh,
        is_skin=is_skin,
        is_dummy=is_dummy,
        render=bool(getattr(node, "render", True)),
        has_geometry=has_geometry,
        vertex_count=len(vertices),
        face_count=len(faces),
        texture=str(getattr(node, "texture_clean", getattr(node, "texture", "")) or ""),
        socket_category=socket_category,
        export_role=_export_role(name, is_mesh=is_mesh, is_skin=is_skin, socket_category=socket_category),
    )


def _iter_model_nodes(model: Any) -> Iterable[Any]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        return all_nodes()
    root = getattr(model, "root_node", None)
    if root is None:
        return ()
    result: list[Any] = []
    stack = [root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)
        result.append(node)
        children = list(getattr(node, "children", []) or [])
        stack.extend(reversed(children))
    return result


def _parent_name(node: Any) -> str | None:
    parent = getattr(node, "parent", None)
    if parent is None:
        return None
    return str(getattr(parent, "name", "") or "")


def _parent_path(node: Any) -> tuple[str, ...]:
    names: list[str] = []
    parent = getattr(node, "parent", None)
    visited: set[int] = set()
    while parent is not None:
        parent_id = id(parent)
        if parent_id in visited:
            break
        visited.add(parent_id)
        names.append(str(getattr(parent, "name", "") or ""))
        parent = getattr(parent, "parent", None)
    names.reverse()
    return tuple(names)


def _full_path(node: Any) -> tuple[str, ...]:
    return _parent_path(node) + (str(getattr(node, "name", "") or ""),)


def _float_tuple(
    values: Any,
    count: int,
    default: float,
    *,
    last_default: float | None = None,
) -> tuple[Any, ...]:
    result: list[float] = []
    raw = list(values or ())
    for index in range(count):
        fallback = default
        if last_default is not None and index == count - 1:
            fallback = last_default
        try:
            result.append(float(raw[index]))
        except Exception:
            result.append(float(fallback))
    return tuple(result)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _tuple_close(left: Iterable[Any], right: Iterable[Any], tolerance: float) -> bool:
    left_values = tuple(left)
    right_values = tuple(right)
    if len(left_values) != len(right_values):
        return False
    for a, b in zip(left_values, right_values):
        try:
            if abs(float(a) - float(b)) > tolerance:
                return False
        except Exception:
            if a != b:
                return False
    return True


def _node_diff_record(node: NativeNodeSnapshot) -> dict[str, Any]:
    return {
        "name": node.name,
        "path": list(node.full_path),
        "parent_path": list(node.parent_path),
        "type_label": node.type_label,
        "export_role": node.export_role,
        "is_mesh": node.is_mesh,
        "is_skin": node.is_skin,
        "socket_category": node.socket_category,
    }


def _has_skin_rows(node: Any) -> bool:
    return bool(
        getattr(node, "is_skin", False)
        or getattr(node, "skin_data", None)
        or getattr(node, "bone_map", None)
    )


def _skin_row_record(node: Any, *, payload_names: set[str]) -> dict[str, Any]:
    name = str(getattr(node, "name", "") or "")
    vertices = list(getattr(node, "vertices", []) or [])
    skin_rows = list(getattr(node, "skin_data", []) or [])
    bone_map = list(getattr(node, "bone_map", []) or [])
    return {
        "name": name,
        "path": list(_full_path(node)),
        "payload_mesh": name in payload_names,
        "vertices": len(vertices),
        "skin_rows": len(skin_rows),
        "bone_map_count": len(bone_map),
    }


def _game_label(model: Any) -> str:
    version = getattr(model, "game_version", None)
    name = getattr(version, "name", "")
    if name:
        return str(name)
    return str(version or "")


def _export_role(
    name: str,
    *,
    is_mesh: bool,
    is_skin: bool,
    socket_category: str | None,
) -> str:
    lowered = name.lower()
    if socket_category:
        return "socket"
    if lowered in KOTOR_EXPORT_HELPER_NAMES:
        return "helper"
    if lowered.endswith(("_g", "_dum")):
        return "deform_helper"
    if is_skin:
        return "skin_mesh"
    if is_mesh:
        return "mesh"
    return "node"
