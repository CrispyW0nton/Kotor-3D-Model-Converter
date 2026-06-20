"""Audit helpers for KOTOR/Aurora target object-node hierarchies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.core.geometry.model_data import KotorModel, ModelNode, VertexSkinData

from .reference_pose import compute_target_rest_transforms
from .retarget_mapping import _role_from_name


@dataclass
class TargetNodeAuditEntry:
    """One Aurora node audit row. This is not a conventional skeleton bone row."""

    name: str
    parent_name: Optional[str]
    index: int
    node_type: Optional[str]
    has_skin_weights: Optional[bool]
    rest_global_position: tuple[float, float, float]
    likely_role: Optional[str]
    warnings: List[str] = field(default_factory=list)


@dataclass
class TargetSkeletonAudit:
    """Audit for a KOTOR/Aurora object-node hierarchy."""

    model_name: str
    entries: List[TargetNodeAuditEntry]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


def audit_target_aurora_nodes(model: KotorModel, supermodel_chain=None) -> TargetSkeletonAudit:
    """Audit local target Aurora nodes without treating them as UE-style bones."""

    _local, global_transforms = compute_target_rest_transforms(model)
    weighted_names = _skin_weighted_node_names(model)
    entries: List[TargetNodeAuditEntry] = []
    warnings: List[str] = []
    errors: List[str] = []
    seen: set[str] = set()
    for index, node in enumerate(model.all_nodes()):
        node_warnings: List[str] = []
        key = node.name.lower()
        if key in seen:
            message = f"Duplicate Aurora node name '{node.name}'"
            node_warnings.append(message)
            errors.append(message)
        seen.add(key)
        if node.parent is not None and node.parent not in model.all_nodes():
            message = f"Node '{node.name}' has parent outside local hierarchy"
            node_warnings.append(message)
            errors.append(message)
        transform = global_transforms[node.name]
        if not transform.is_finite():
            message = f"Node '{node.name}' has non-finite rest transform"
            node_warnings.append(message)
            errors.append(message)
        entries.append(
            TargetNodeAuditEntry(
                name=node.name,
                parent_name=node.parent.name if node.parent is not None else None,
                index=index,
                node_type=node.type_label,
                has_skin_weights=node.name.lower() in weighted_names if weighted_names else None,
                rest_global_position=transform.position,
                likely_role=_role_from_name(node.name),
                warnings=node_warnings,
            )
        )
    return TargetSkeletonAudit(model_name=model.name, entries=entries, warnings=warnings, errors=errors)


def _skin_weighted_node_names(model: KotorModel) -> set[str]:
    names: set[str] = set()
    for node in model.all_nodes():
        for bone_name in getattr(node, "bone_map", []) or []:
            if str(bone_name or "").strip():
                names.add(str(bone_name).lower())
        for skin in getattr(node, "skin_data", []) or []:
            if isinstance(skin, VertexSkinData):
                for influence in skin.influences:
                    bone_map = getattr(node, "bone_map", []) or []
                    if 0 <= influence.bone_index < len(bone_map):
                        names.add(str(bone_map[influence.bone_index]).lower())
    return names
