"""Native KotOR skeleton snapshot helpers for Character Builder.

Character Studio must treat the selected KotOR base model as the authority for
node names, parent paths, hooks, helper meshes, and animation inheritance.  This
module captures that information as a lightweight, JSON-friendly contract before
later workflow steps hide, strip, or replace viewport geometry.
"""

from __future__ import annotations

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
    "lhand": "left_hand",
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
