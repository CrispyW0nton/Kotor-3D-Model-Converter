"""Reverse UE5 Manny -> Aurora bone naming for animation injection.

Sprint 3 deliberately starts with the same narrow contract as Day 4.5 v6:
rename animation channels by bone name, drop helper channels Aurora cannot
consume, and preserve the target Aurora model's bind pose and helper nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .skeleton_renamer import DEFAULT_RENAME_MAP, REPO_ROOT, SkeletonRenameError


DEFAULT_REVERSE_RENAME_MAP = REPO_ROOT / "knowledge_base" / "retargeting" / "ue5_to_aurora_rename_map.json"
REVERSE_SCOPE = "BONE_NAMING_ONLY"
REVERSE_DIRECTION = "REVERSE"


def _key(name: str) -> str:
    return str(name or "").strip().lower()


@dataclass(frozen=True)
class ReverseRenameSpec:
    """Declarative UE5 Manny/Quinn animation-channel to Aurora naming spec."""

    version: str
    rename_pairs: dict[str, str]
    ue5_only_bones_dropped: list[str] = field(default_factory=list)
    aurora_helpers_preserved_from_target: list[str] = field(default_factory=list)
    synthetic_helper_bones_dropped: list[str] = field(default_factory=list)
    source: str = "ue5_manny"
    target: str = "aurora_kotor"
    scope: str = REVERSE_SCOPE
    direction: str = REVERSE_DIRECTION
    derived_from: str = "aurora_to_ue5_rename_map.json"
    path: Path | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "target": self.target,
            "scope": self.scope,
            "direction": self.direction,
            "derived_from": self.derived_from,
            "rename_pairs": dict(self.rename_pairs),
            "ue5_only_bones_dropped": list(self.ue5_only_bones_dropped),
            "synthetic_helper_bones_dropped": list(self.synthetic_helper_bones_dropped),
            "aurora_helpers_preserved_from_target": list(self.aurora_helpers_preserved_from_target),
        }


def _require_mapping(payload: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = payload.get(field, {})
    if not isinstance(value, Mapping):
        raise SkeletonRenameError(f"Forward rename map field {field!r} must be an object")
    return value


def _load_forward_payload(forward_map_path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = Path(forward_map_path or DEFAULT_RENAME_MAP)
    return path, json.loads(path.read_text(encoding="utf-8"))


def build_reverse_rename_spec_from_forward(
    forward_map_path: str | Path | None = None,
) -> ReverseRenameSpec:
    """Invert the Day 4.5 v6 Aurora -> UE5 naming map.

    Twist leaves and synthetic UE5 humanoid helper leaves were added for export
    compatibility.  Reverse animation injection must not author those bones into
    Aurora models unless a later target-specific map explicitly opts in.
    """

    path, forward = _load_forward_payload(forward_map_path)
    if forward.get("scope") != REVERSE_SCOPE:
        raise SkeletonRenameError(f"Forward map scope must be {REVERSE_SCOPE}, got {forward.get('scope')!r}")

    forward_pairs = _require_mapping(forward, "rename_pairs")
    reverse_pairs: dict[str, str] = {}
    for aurora_name, ue5_name in forward_pairs.items():
        source_key = _key(str(ue5_name))
        target_key = _key(str(aurora_name))
        if source_key in reverse_pairs and reverse_pairs[source_key] != target_key:
            raise SkeletonRenameError(f"Cannot invert rename collision for UE5 bone {source_key!r}")
        reverse_pairs[source_key] = target_key

    twist_bones = sorted(_key(name) for name in _require_mapping(forward, "twist_bone_leaves"))
    synthetic_helpers = sorted(_key(name) for name in _require_mapping(forward, "helper_bone_leaves"))
    aurora_helpers = [_key(name) for name in forward.get("aurora_helper_bones_non_deform", [])]

    return ReverseRenameSpec(
        version=str(forward.get("version") or "1.0.0"),
        source="ue5_manny",
        target="aurora_kotor",
        scope=REVERSE_SCOPE,
        direction=REVERSE_DIRECTION,
        derived_from=path.name,
        rename_pairs=dict(sorted(reverse_pairs.items())),
        ue5_only_bones_dropped=twist_bones,
        synthetic_helper_bones_dropped=synthetic_helpers,
        aurora_helpers_preserved_from_target=aurora_helpers,
    )


def load_reverse_rename_spec(json_path: str | Path | None = None) -> ReverseRenameSpec:
    """Load a persisted reverse rename map."""

    path = Path(json_path or DEFAULT_REVERSE_RENAME_MAP)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("scope") != REVERSE_SCOPE:
        raise SkeletonRenameError(f"Reverse map scope must be {REVERSE_SCOPE}, got {payload.get('scope')!r}")
    if payload.get("direction") != REVERSE_DIRECTION:
        raise SkeletonRenameError(
            f"Reverse map direction must be {REVERSE_DIRECTION}, got {payload.get('direction')!r}"
        )

    return ReverseRenameSpec(
        version=str(payload.get("version") or ""),
        source=str(payload.get("source") or "ue5_manny"),
        target=str(payload.get("target") or "aurora_kotor"),
        scope=str(payload.get("scope") or REVERSE_SCOPE),
        direction=str(payload.get("direction") or REVERSE_DIRECTION),
        derived_from=str(payload.get("derived_from") or ""),
        rename_pairs={_key(src): _key(dst) for src, dst in dict(payload.get("rename_pairs", {})).items()},
        ue5_only_bones_dropped=[_key(name) for name in payload.get("ue5_only_bones_dropped", [])],
        synthetic_helper_bones_dropped=[_key(name) for name in payload.get("synthetic_helper_bones_dropped", [])],
        aurora_helpers_preserved_from_target=[
            _key(name) for name in payload.get("aurora_helpers_preserved_from_target", [])
        ],
        path=path,
    )


def validate_reverse_rename_spec(
    spec: ReverseRenameSpec,
    source_ue5_bones: Iterable[str],
    target_aurora_bones: Iterable[str],
    *,
    require_all_source_bones_accounted: bool = True,
) -> list[str]:
    """Validate a reverse spec against actual source and target skeleton names."""

    errors: list[str] = []
    source_keys = {_key(name) for name in source_ue5_bones}
    target_keys = {_key(name) for name in target_aurora_bones}
    mapped_source_keys = set(spec.rename_pairs)
    mapped_target_list = [_key(target) for target in spec.rename_pairs.values()]
    mapped_target_keys = set(mapped_target_list)
    dropped_keys = {_key(name) for name in [*spec.ue5_only_bones_dropped, *spec.synthetic_helper_bones_dropped]}

    for source_name, target_name in spec.rename_pairs.items():
        if source_name not in source_keys:
            errors.append(f"Mapped UE5 source bone '{source_name}' not in source skeleton")
        if _key(target_name) not in target_keys:
            errors.append(f"Mapped Aurora target bone '{target_name}' not in target skeleton")

    duplicate_targets = sorted({name for name in mapped_target_list if mapped_target_list.count(name) > 1})
    if duplicate_targets:
        errors.append(f"Reverse rename collision: target names appear multiple times: {duplicate_targets}")

    if require_all_source_bones_accounted:
        unaccounted = sorted(source_keys - mapped_source_keys - dropped_keys)
        if unaccounted:
            errors.append(f"Unmapped UE5 source bones not marked as dropped: {unaccounted}")

    dropped_and_mapped = sorted(mapped_source_keys & dropped_keys)
    if dropped_and_mapped:
        errors.append(f"UE5 bones cannot be both mapped and dropped: {dropped_and_mapped}")

    return errors


def write_reverse_rename_map(
    output_path: str | Path = DEFAULT_REVERSE_RENAME_MAP,
    forward_map_path: str | Path | None = None,
) -> Path:
    """Generate and persist the reverse map derived from the forward v6 map."""

    spec = build_reverse_rename_spec_from_forward(forward_map_path)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec.as_payload(), indent=2) + "\n", encoding="utf-8")
    return path
