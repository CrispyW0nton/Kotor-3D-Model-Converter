"""Pose-preserving Aurora bone renaming for UE5/Unity FBX export.

Day 4.5 v6 is intentionally narrow: this module validates a declarative
Aurora -> UE-style naming layer, helper-bone deform flags, and zero-weight
twist leaves.  It does not modify rest pose, rotations, translations, mesh
vertices, or skin weights.  Those are preserved from the native Aurora bind
pose and consumed later by Blender's name-keyed armature binding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RENAME_MAP = REPO_ROOT / "knowledge_base" / "retargeting" / "aurora_to_ue5_rename_map.json"
FORBIDDEN_SCHEMA_FIELDS = {
    "rest_pose_override",
    "rest_pose_target",
    "target_world_rotation",
    "target_world_rotation_wxyz",
    "per_bone_target_world_rotation_wxyz",
    "per_bone_target_world_position",
    "quinn_rest_pose",
    "quinn_local_rotations",
}


class SkeletonRenameError(RuntimeError):
    """Raised when the Day 4.5 v6 rename-only contract is violated."""


def _key(name: str) -> str:
    return str(name or "").strip().lower()


@dataclass(frozen=True)
class TwistLeafSpec:
    """Non-deforming twist helper inserted as a terminal leaf."""

    name: str
    parent: str
    local_translation_fraction: float = 0.5
    use_deform: bool = False
    vertex_weight_policy: str = "zero"


@dataclass(frozen=True)
class HelperLeafSpec:
    """Optional non-deforming helper leaf, e.g. a body-model head placeholder."""

    name: str
    parent: str
    local_translation_fraction: float = 1.0
    use_deform: bool = False
    vertex_weight_policy: str = "zero"
    reason: str = ""


@dataclass(frozen=True)
class RenameSpec:
    """Declarative, pose-preserving bone rename specification."""

    version: str
    rename_pairs: dict[str, str]
    helper_bones_non_deform: list[str] = field(default_factory=list)
    twist_leaves: list[TwistLeafSpec] = field(default_factory=list)
    helper_leaves: list[HelperLeafSpec] = field(default_factory=list)
    unmapped_source_bones: list[str] = field(default_factory=list)
    explicit_non_scope: list[str] = field(default_factory=list)
    source: str = "aurora_kotor"
    target: str = "ue5_manny_naming_only"
    path: Path | None = None

    def as_payload(self) -> dict[str, Any]:
        """Return the Blender-intermediate form of the rename contract."""

        return {
            "version": self.version,
            "scope": "BONE_NAMING_ONLY",
            "source": self.source,
            "target": self.target,
            "explicit_non_scope": list(self.explicit_non_scope),
            "rename_pairs": dict(self.rename_pairs),
            "helper_bones_non_deform": list(self.helper_bones_non_deform),
            "twist_leaves": [leaf.__dict__ for leaf in self.twist_leaves],
            "helper_leaves": [leaf.__dict__ for leaf in self.helper_leaves],
            "unmapped_source_bones": list(self.unmapped_source_bones),
        }


def _walk_forbidden_fields(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _key(str(key)) in FORBIDDEN_SCHEMA_FIELDS:
                hits.append(child_path)
            hits.extend(_walk_forbidden_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_walk_forbidden_fields(child, f"{path}[{index}]"))
    return hits


def _leaf_from_payload(name: str, payload: Mapping[str, Any]) -> TwistLeafSpec:
    return TwistLeafSpec(
        name=str(name),
        parent=str(payload.get("parent") or payload.get("parent_renamed") or ""),
        local_translation_fraction=float(payload.get("local_translation_fraction", 0.5)),
        use_deform=bool(payload.get("use_deform", False)),
        vertex_weight_policy=str(payload.get("vertex_weight_policy") or payload.get("weight_policy") or "zero"),
    )


def _helper_leaf_from_payload(name: str, payload: Mapping[str, Any]) -> HelperLeafSpec:
    return HelperLeafSpec(
        name=str(name),
        parent=str(payload.get("parent") or payload.get("parent_renamed") or ""),
        local_translation_fraction=float(payload.get("local_translation_fraction", 1.0)),
        use_deform=bool(payload.get("use_deform", False)),
        vertex_weight_policy=str(payload.get("vertex_weight_policy") or payload.get("weight_policy") or "zero"),
        reason=str(payload.get("reason") or ""),
    )


def _load_leaf_list(value: Any, *, helper: bool = False) -> list[TwistLeafSpec] | list[HelperLeafSpec]:
    leaves: list[Any] = []
    if isinstance(value, Mapping):
        iterator = value.items()
    else:
        iterator = ((str(item.get("name") or ""), item) for item in (value or []))
    for name, payload in iterator:
        if not name or not isinstance(payload, Mapping):
            continue
        leaves.append(_helper_leaf_from_payload(str(name), payload) if helper else _leaf_from_payload(str(name), payload))
    return leaves


def load_rename_spec(json_path: str | Path | None = None) -> RenameSpec:
    """Load and validate the Day 4.5 v6 BONE_NAMING_ONLY schema."""

    path = Path(json_path or DEFAULT_RENAME_MAP)
    payload = json.loads(path.read_text(encoding="utf-8"))
    forbidden = _walk_forbidden_fields(payload)
    if forbidden:
        raise SkeletonRenameError(
            "Rename spec contains rest-pose/rotation fields removed in Day 4.5 v6: "
            + ", ".join(forbidden)
        )
    if payload.get("scope") != "BONE_NAMING_ONLY":
        raise SkeletonRenameError(
            f"Rename map scope must be BONE_NAMING_ONLY, got {payload.get('scope')!r}. "
            "Day 4.5 v6 preserves Aurora's native bind pose."
        )

    return RenameSpec(
        version=str(payload.get("version") or ""),
        source=str(payload.get("source") or "aurora_kotor"),
        target=str(payload.get("target") or "ue5_manny_naming_only"),
        explicit_non_scope=[str(item) for item in payload.get("explicit_non_scope", [])],
        rename_pairs={_key(src): str(dst) for src, dst in dict(payload.get("rename_pairs", {})).items()},
        helper_bones_non_deform=[_key(name) for name in payload.get("aurora_helper_bones_non_deform", [])],
        twist_leaves=_load_leaf_list(payload.get("twist_bone_leaves", {}), helper=False),  # type: ignore[arg-type]
        helper_leaves=_load_leaf_list(payload.get("helper_bone_leaves", {}), helper=True),  # type: ignore[arg-type]
        unmapped_source_bones=[str(name) for name in payload.get("unmapped_aurora_bones", [])],
        path=path,
    )


def load_rename_map(path: str | Path | None = None) -> dict[str, Any]:
    """Backward-compatible dictionary loader for older callers/tests."""

    spec = load_rename_spec(path)
    payload = spec.as_payload()
    payload["_path"] = str(spec.path) if spec.path else ""
    return payload


def validate_rename_spec(spec: RenameSpec, source_bones: Iterable[str]) -> list[str]:
    """Return validation errors for a source armature.  Missing helpers are optional."""

    errors: list[str] = []
    source_keys = {_key(name) for name in source_bones}
    target_names = [str(target) for target in spec.rename_pairs.values()]
    target_keys = [_key(target) for target in target_names]

    for source_name in spec.rename_pairs:
        if source_name not in source_keys:
            errors.append(f"Source bone '{source_name}' not in armature")

    duplicates = sorted({name for name in target_keys if target_keys.count(name) > 1})
    if duplicates:
        errors.append(f"Rename collision: target names appear multiple times: {duplicates}")

    valid_parents = source_keys | set(target_keys)
    for leaf in [*spec.twist_leaves, *spec.helper_leaves]:
        if _key(leaf.parent) not in valid_parents:
            errors.append(f"Leaf '{leaf.name}' has invalid parent '{leaf.parent}'")
        if leaf.use_deform:
            errors.append(f"Leaf '{leaf.name}' must be non-deforming")
        if leaf.vertex_weight_policy.lower() != "zero":
            errors.append(f"Leaf '{leaf.name}' must use zero vertex weights")
        valid_parents.add(_key(leaf.name))

    return errors
