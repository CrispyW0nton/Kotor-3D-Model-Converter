"""Role suggestions and validation for source-to-Aurora retarget profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.game.kotor_loader import resolve_animation_slot
from src.core.geometry.model_data import KotorModel

from .retarget_profile import RetargetMappingEntry, RetargetProfile
from .source_animation import SourceSkeletonClip


HELPER_CLASSIFICATIONS = {"twist", "ik", "helper"}


@dataclass
class RetargetProfileValidationReport:
    """Validation result for one profile/source/target combination."""

    success: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.success = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def detect_side(name: str) -> Optional[str]:
    """Return obvious left/right/center side metadata from a node name."""

    text = _normalize_name(name)
    tokens = [token for token in text.replace(".", "_").split("_") if token]
    if "left" in tokens or text.endswith("_l") or text.endswith(".l") or text.startswith("l_"):
        return "left"
    if "right" in tokens or text.endswith("_r") or text.endswith(".r") or text.startswith("r_"):
        return "right"
    if text.startswith("l") and len(text) > 1 and text[1].isalpha() and not text.startswith("lower"):
        return "left"
    if text.startswith("r") and len(text) > 1 and text[1].isalpha() and not text.startswith("root"):
        return "right"
    return "center"


def suggest_source_roles(clip: SourceSkeletonClip) -> Dict[str, str]:
    """Suggest semantic roles for deform/root source nodes."""

    suggestions: Dict[str, str] = {}
    for node in clip.nodes:
        if node.classification in HELPER_CLASSIFICATIONS:
            continue
        role = _role_from_name(node.name)
        if role:
            suggestions[node.name] = role
    return suggestions


def suggest_target_roles(model: KotorModel) -> Dict[str, str]:
    """Suggest conservative semantic roles for an Aurora object-node hierarchy."""

    suggestions: Dict[str, str] = {}
    for node in model.all_nodes():
        role = _role_from_name(node.name)
        if role:
            suggestions[node.name] = role
    return suggestions


def suggest_initial_mapping(source_clip: SourceSkeletonClip, target_model: KotorModel) -> RetargetProfile:
    """Build a first-pass suggested mapping profile without claiming correctness."""

    source_roles = suggest_source_roles(source_clip)
    target_roles = suggest_target_roles(target_model)
    target_by_key: Dict[Tuple[str, Optional[str]], str] = {}
    for target_name, role in target_roles.items():
        target_by_key.setdefault((role, detect_side(target_name)), target_name)
        target_by_key.setdefault((role, None), target_name)

    mappings: List[RetargetMappingEntry] = []
    for source_name, role in source_roles.items():
        side = detect_side(source_name)
        target_name = target_by_key.get((role, side)) or target_by_key.get((role, None))
        if not target_name:
            continue
        mappings.append(
            RetargetMappingEntry(
                role=role,
                source_node=source_name,
                target_node=target_name,
                side=side,
            )
        )

    return RetargetProfile(
        version=1,
        name="suggested_source_to_aurora_profile",
        source_clip_hint=source_clip.source_path,
        target_model_hint=target_model.name,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=mappings,
        ignored_source_nodes=[
            node.name for node in source_clip.nodes if node.classification in HELPER_CLASSIFICATIONS
        ],
        twist_sources={},
        metadata={"generated_by": "suggest_initial_mapping"},
    )


def validate_retarget_profile(
    profile: RetargetProfile,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    *,
    strict: bool = True,
) -> RetargetProfileValidationReport:
    """Validate a retarget profile without mutating source or target assets."""

    report = RetargetProfileValidationReport()
    source_by_name = {node.name.lower(): node for node in source_clip.nodes}
    target_by_name = {node.name.lower(): node for node in target_model.all_nodes()}

    source_usage: Dict[str, List[RetargetMappingEntry]] = {}
    target_usage: Dict[str, List[RetargetMappingEntry]] = {}

    for entry in profile.mappings:
        source_key = entry.source_node.lower()
        target_key = entry.target_node.lower()
        source_node = source_by_name.get(source_key)
        target_node = target_by_name.get(target_key)
        if source_node is None:
            report.add_error(
                f"Retarget profile '{profile.name}' maps source node '{entry.source_node}' "
                "but the imported source clip does not contain that node."
            )
        else:
            source_usage.setdefault(source_key, []).append(entry)
            if source_node.classification in HELPER_CLASSIFICATIONS:
                message = (
                    f"Source node '{entry.source_node}' is classified as twist/helper and should not be "
                    "mapped as a normal KOTOR controller target. Use twist_sources or explicitly allow helper mapping."
                )
                if entry.allow_helper_mapping:
                    report.add_warning(message)
                elif strict:
                    report.add_error(message)
                else:
                    report.add_warning(message)

        if target_node is None:
            report.add_error(
                f"Retarget profile '{profile.name}' maps target node '{entry.target_node}', "
                "but that node does not exist on the KOTOR/Aurora target model. "
                "KOTOR controllers must target existing Aurora nodes, not UE skeleton bones."
            )
        else:
            target_usage.setdefault(target_key, []).append(entry)

        _check_side_hint(report, entry)

    for source_key, entries in source_usage.items():
        if len(entries) > 1:
            report.add_error(
                f"Source node '{entries[0].source_node}' is mapped more than once as a normal retarget source."
            )
    for target_key, entries in target_usage.items():
        if len(entries) > 1:
            report.add_error(
                f"Target Aurora node '{entries[0].target_node}' is mapped by multiple normal retarget entries."
            )

    _warn_required_roles(report, profile)
    _warn_parent_chain_consistency(report, profile, source_by_name, target_by_name)
    _validate_animation_slot(report, profile, target_model)
    return report


def _normalize_name(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "_")


def _role_from_name(name: str) -> Optional[str]:
    text = _normalize_name(name)
    stripped = text.removesuffix("_g")
    if stripped in {"root", "rootdummy", "armature", "scene"}:
        return "root"
    if "pelvis" in stripped or "hips" in stripped:
        return "pelvis"
    if "upperchest" in stripped or "chest" in stripped or "torso_upper" in stripped:
        return "chest"
    if "spine_03" in stripped or "spine3" in stripped:
        return "chest"
    if "spine" in stripped or "torso" in stripped:
        return "spine"
    if "neck" in stripped:
        return "neck"
    if "head" in stripped:
        return "head"
    if "clavicle" in stripped or "shoulder" in stripped:
        return "clavicle"
    if "upperarm" in stripped or "upper_arm" in stripped or "bicep" in stripped:
        return "upperarm"
    if "lowerarm" in stripped or "lower_arm" in stripped or "forearm" in stripped:
        return "forearm"
    if "hand" in stripped:
        return "hand"
    if "thigh" in stripped or "upperleg" in stripped or "upper_leg" in stripped:
        return "thigh"
    if "calf" in stripped or "lowerleg" in stripped or "lower_leg" in stripped or "shin" in stripped:
        return "calf"
    if "foot" in stripped:
        return "foot"
    if "toe" in stripped or "ball" in stripped:
        return "toe"
    if "weapon" in stripped or "rhand" == stripped or "lhand" == stripped:
        return "weapon_hook"
    return None


def _check_side_hint(report: RetargetProfileValidationReport, entry: RetargetMappingEntry) -> None:
    expected = entry.side
    if not expected or expected == "center":
        return
    source_side = detect_side(entry.source_node)
    target_side = detect_side(entry.target_node)
    if source_side not in {expected, "center"}:
        report.add_warning(
            f"Mapping role '{entry.role}' side '{expected}' does not match source node '{entry.source_node}' side '{source_side}'."
        )
    if target_side not in {expected, "center"}:
        report.add_warning(
            f"Mapping role '{entry.role}' side '{expected}' does not match target node '{entry.target_node}' side '{target_side}'."
        )


def _warn_required_roles(report: RetargetProfileValidationReport, profile: RetargetProfile) -> None:
    present = {(entry.role, entry.side or "center") for entry in profile.mappings}
    required = [
        ("pelvis", "center"),
        ("head", "center"),
        ("upperarm", "left"),
        ("forearm", "left"),
        ("hand", "left"),
        ("upperarm", "right"),
        ("forearm", "right"),
        ("hand", "right"),
        ("thigh", "left"),
        ("calf", "left"),
        ("foot", "left"),
        ("thigh", "right"),
        ("calf", "right"),
        ("foot", "right"),
    ]
    if not any(entry.role in {"spine", "chest"} for entry in profile.mappings):
        report.add_warning("Profile is missing a central spine/chest mapping.")
    for role, side in required:
        if (role, side) not in present and (role, None) not in present:
            report.add_warning(f"Profile is missing required role '{role}' on side '{side}'.")


def _is_descendant(name: str, ancestor: str, parent_by_name: Dict[str, Optional[str]]) -> bool:
    current = parent_by_name.get(name.lower())
    wanted = ancestor.lower()
    seen: set[str] = set()
    while current:
        key = current.lower()
        if key == wanted:
            return True
        if key in seen:
            return False
        seen.add(key)
        current = parent_by_name.get(key)
    return False


def _warn_parent_chain_consistency(
    report: RetargetProfileValidationReport,
    profile: RetargetProfile,
    source_by_name,
    target_by_name,
) -> None:
    role_pairs = [
        ("upperarm", "forearm"),
        ("forearm", "hand"),
        ("thigh", "calf"),
        ("calf", "foot"),
    ]
    source_parent = {node.name.lower(): node.parent_name for node in source_by_name.values()}
    target_parent = {
        node.name.lower(): (node.parent.name if node.parent is not None else None)
        for node in target_by_name.values()
    }
    by_role_side = {(entry.role, entry.side or "center"): entry for entry in profile.mappings}
    for parent_role, child_role in role_pairs:
        for side in ("left", "right", "center"):
            parent = by_role_side.get((parent_role, side))
            child = by_role_side.get((child_role, side))
            if not parent or not child:
                continue
            if parent.source_node.lower() in source_by_name and child.source_node.lower() in source_by_name:
                if not _is_descendant(child.source_node, parent.source_node, source_parent):
                    report.add_warning(
                        f"Source '{child.source_node}' is not below '{parent.source_node}' for {parent_role}->{child_role}."
                    )
            if parent.target_node.lower() in target_by_name and child.target_node.lower() in target_by_name:
                if not _is_descendant(child.target_node, parent.target_node, target_parent):
                    report.add_warning(
                        f"Target '{child.target_node}' is not below '{parent.target_node}' for {parent_role}->{child_role}."
                    )


def _validate_animation_slot(
    report: RetargetProfileValidationReport,
    profile: RetargetProfile,
    target_model: KotorModel,
) -> None:
    slot = str(profile.animation_slot or "").strip()
    if not slot:
        return
    try:
        resolve_animation_slot(target_model, slot, require_valid=True)
    except ValueError:
        report.add_error(
            f"Invalid animation slot '{slot}' for this target model/supermodel chain. "
            "UE clip names are not KOTOR animation slot names."
        )
