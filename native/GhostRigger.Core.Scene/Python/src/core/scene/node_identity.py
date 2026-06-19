"""Scene import and node-classification helpers.

The viewport must preserve authored MDL node names for animation and skinning,
but KMAX scenes can contain multiple imports of the same model.  These helpers
add a second identity layer: stable scene-object/import ids plus lightweight
node roles derived from the loaded model's own skeleton and controller data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SceneModelIdentity:
    asset_kind: str = "model"
    animation_kind: str = "static"
    skeleton_kind: str = "none"
    joint_names: frozenset[str] = field(default_factory=frozenset)
    animated_node_names: frozenset[str] = field(default_factory=frozenset)
    dummy_node_names: frozenset[str] = field(default_factory=frozenset)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "asset_kind": self.asset_kind,
            "animation_kind": self.animation_kind,
            "skeleton_kind": self.skeleton_kind,
            "joint_count": len(self.joint_names),
            "animated_node_count": len(self.animated_node_names),
            "dummy_node_count": len(self.dummy_node_names),
            "joint_names": sorted(self.joint_names),
            "animated_node_names": sorted(self.animated_node_names),
            "dummy_node_names": sorted(self.dummy_node_names),
        }


def _iter_model_nodes(model: Any) -> list[Any]:
    try:
        return list(model.all_nodes()) if model is not None and hasattr(model, "all_nodes") else []
    except Exception:
        return []


def _model_classification_value(model: Any) -> int | None:
    try:
        return int(getattr(model, "model_type"))
    except Exception:
        return None


def _normal_name(value: Any) -> str:
    return str(value or "").strip().lower()


def collect_skeleton_joint_names(model: Any) -> frozenset[str]:
    names: set[str] = set()
    for node in _iter_model_nodes(model):
        for bone_name in getattr(node, "bone_map", None) or []:
            name = _normal_name(bone_name)
            if name:
                names.add(name)
    return frozenset(names)


def collect_animated_node_names(model: Any) -> frozenset[str]:
    names: set[str] = set()
    for anim in getattr(model, "animations", None) or []:
        for node in getattr(anim, "nodes", None) or []:
            name = _normal_name(getattr(node, "name", ""))
            if name:
                names.add(name)
    for node in _iter_model_nodes(model):
        if getattr(node, "controllers", None):
            name = _normal_name(getattr(node, "name", ""))
            if name:
                names.add(name)
    return frozenset(names)


def collect_dummy_node_names(model: Any) -> frozenset[str]:
    names: set[str] = set()
    for node in _iter_model_nodes(model):
        try:
            is_dummy = bool(getattr(node, "type_label", "") == "dummy" or getattr(node, "is_dummy", False))
        except Exception:
            is_dummy = False
        if is_dummy:
            name = _normal_name(getattr(node, "name", ""))
            if name:
                names.add(name)
    return frozenset(names)


def classify_scene_model(model: Any, resource_ref: Any = None) -> SceneModelIdentity:
    joint_names = collect_skeleton_joint_names(model)
    animated_names = collect_animated_node_names(model)
    dummy_names = collect_dummy_node_names(model)
    classification = _model_classification_value(model)
    resref = _normal_name(getattr(resource_ref, "resref", "") or getattr(model, "name", ""))

    has_skin = any(bool(getattr(node, "is_skin", False)) for node in _iter_model_nodes(model))
    has_animation = bool(getattr(model, "animations", None)) or bool(animated_names)

    if classification == 4 or resref.startswith(("n_", "p_", "c_")):
        asset_kind = "character"
    elif classification == 32 or resref.startswith("plc_"):
        asset_kind = "placeable"
    elif classification == 8 or resref.startswith("dor_"):
        asset_kind = "door"
    elif has_skin:
        asset_kind = "animated_mesh"
    else:
        asset_kind = "static_mesh"

    if has_skin or joint_names:
        animation_kind = "skeletal" if has_animation else "skeletal_static"
        skeleton_kind = "skin_bone_map"
    elif has_animation:
        animation_kind = "rigid"
        skeleton_kind = "none"
    else:
        animation_kind = "static"
        skeleton_kind = "none"

    return SceneModelIdentity(
        asset_kind=asset_kind,
        animation_kind=animation_kind,
        skeleton_kind=skeleton_kind,
        joint_names=joint_names,
        animated_node_names=animated_names,
        dummy_node_names=dummy_names,
    )


def classify_scene_node(node: Any, identity: SceneModelIdentity | dict[str, Any] | None = None) -> str:
    name = _normal_name(getattr(node, "name", ""))
    if isinstance(identity, SceneModelIdentity):
        joint_names = identity.joint_names
        animated_names = identity.animated_node_names
        dummy_names = identity.dummy_node_names
    else:
        joint_names = frozenset(_normal_name(v) for v in (identity or {}).get("joint_names", ()) if _normal_name(v))
        animated_names = frozenset(_normal_name(v) for v in (identity or {}).get("animated_node_names", ()) if _normal_name(v))
        dummy_names = frozenset(_normal_name(v) for v in (identity or {}).get("dummy_node_names", ()) if _normal_name(v))

    if name and name in joint_names:
        return "joint"
    try:
        if bool(getattr(node, "is_skin", False)):
            return "skin_mesh"
        if bool(getattr(node, "is_mesh", False)):
            return "mesh"
    except Exception:
        pass
    if name and name in dummy_names:
        return "animated_dummy" if name in animated_names else "dummy"
    if name and name in animated_names:
        return "animated_node"
    return str(getattr(node, "type_label", "") or "node")
