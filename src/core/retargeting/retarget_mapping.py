"""Role suggestions and validation for source-to-Aurora retarget profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.game.kotor_loader import resolve_animation_slot
from src.core.geometry.model_data import KotorModel

from .retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNamingError,
    coerce_kotor_output_name_mode,
    validate_custom_kotor_animation_name,
)
from .retarget_profile import RetargetMappingEntry, RetargetProfile
from .reverse_renamer import ReverseRenameSpec, load_reverse_rename_spec
from .source_animation import SourceSkeletonClip
from .mixamo_source_adapter import MixamoSourceAdapter, is_mixamo_skeleton
from .ue5_source_adapter import UE5SourceAdapter


HELPER_CLASSIFICATIONS = {"twist", "ik", "helper"}
UE5_TO_AURORA_MIN_CORE_MAPPING_COUNT = 19
MIXAMO_TO_AURORA_MIN_CORE_MAPPING_COUNT = 18

_UE5_EXACT_ROLE_BY_SOURCE = {
    "attach": "root",
    "root": "root",
    "pelvis": "pelvis",
    "spine_01": "spine",
    "spine_03": "chest",
    "clavicle_l": "clavicle",
    "clavicle_r": "clavicle",
    "upperarm_l": "upperarm",
    "upperarm_r": "upperarm",
    "lowerarm_l": "forearm",
    "lowerarm_r": "forearm",
    "hand_l": "hand",
    "hand_r": "hand",
    "thigh_l": "thigh",
    "thigh_r": "thigh",
    "calf_l": "calf",
    "calf_r": "calf",
    "foot_l": "foot",
    "foot_r": "foot",
    "ball_l": "toe",
    "ball_r": "toe",
}

_FINGER_ROLE_PREFIXES = ("index", "middle", "ring", "pinky", "thumb")


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
    used_targets: set[str] = set()
    for source_name, role in source_roles.items():
        side = detect_side(source_name)
        target_name = target_by_key.get((role, side)) or target_by_key.get((role, None))
        if not target_name:
            continue
        target_key = target_name.lower()
        if target_key in used_targets:
            continue
        used_targets.add(target_key)
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


def suggest_ue5_to_aurora_mapping(
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    *,
    spec: ReverseRenameSpec | None = None,
    adapter: UE5SourceAdapter | None = None,
) -> RetargetProfile:
    """Build the verified UE5 Manny/Quinn -> Aurora profile used by the Workbench.

    This path is deliberately narrower than :func:`suggest_initial_mapping`.
    It consumes the reverse rename policy that was validated for the PMBAM idle
    retarget workflow, resolves every target name back to the target model's
    exact Aurora casing, and avoids helper/hook guesses such as ``headhook``.
    """

    reverse_spec = spec or load_reverse_rename_spec()
    source_names = [node.name for node in source_clip.nodes]
    target_nodes = list(target_model.all_nodes())
    target_name_by_key = {node.name.lower(): node.name for node in target_nodes}
    adapter_result = (adapter or UE5SourceAdapter()).adapt(
        source_names,
        reverse_spec,
        [node.name for node in target_nodes],
    )

    source_class_by_key = {node.name.lower(): node.classification for node in source_clip.nodes}
    mappings: list[RetargetMappingEntry] = []
    for decision in adapter_result.mapped:
        target_key = str(decision.target_bone or "").lower()
        target_name = target_name_by_key.get(target_key)
        if not target_name:
            continue
        source_name = _source_name_with_original_case(decision.source_bone, source_names)
        mappings.append(
            RetargetMappingEntry(
                role=_ue5_verified_role(decision.source_bone),
                source_node=source_name,
                target_node=target_name,
                side=detect_side(decision.source_bone),
                allow_helper_mapping=(
                    decision.action == "alias"
                    or source_class_by_key.get(decision.source_bone.lower()) in HELPER_CLASSIFICATIONS
                ),
                notes=decision.reason,
            )
        )

    ignored = [
        _source_name_with_original_case(decision.source_bone, source_names)
        for decision in [*adapter_result.dropped, *adapter_result.collapsed]
    ]
    unmapped = [
        _source_name_with_original_case(decision.source_bone, source_names)
        for decision in adapter_result.unmapped
    ]
    if len(mappings) < UE5_TO_AURORA_MIN_CORE_MAPPING_COUNT:
        raise ValueError(
            "Verified UE5 → Aurora mapping found too few usable core mappings "
            f"({len(mappings)} < {UE5_TO_AURORA_MIN_CORE_MAPPING_COUNT})."
        )

    return RetargetProfile(
        version=1,
        name="verified_ue5_to_aurora_profile",
        source_clip_hint=source_clip.source_path,
        target_model_hint=target_model.name,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=mappings,
        ignored_source_nodes=ignored,
        twist_sources={},
        metadata={
            "generated_by": "verified_ue5_to_aurora_mapping",
            "source_adapter": "UE5SourceAdapter",
            "rename_map": str(reverse_spec.path or ""),
            "mapped_count": len(mappings),
            "dropped_count": len(adapter_result.dropped),
            "collapsed_count": len(adapter_result.collapsed),
            "unmapped_count": len(adapter_result.unmapped),
            "unmapped_source_nodes": unmapped,
            "recommended_rotation_transfer_mode": "exact_segment_correction",
            "key_unmapped_reference_nodes": True,
            "basis_conversion": "ue5_to_aurora_negate_xy",
        },
    )


def suggest_mixamo_to_aurora_mapping(
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    *,
    adapter: MixamoSourceAdapter | None = None,
) -> RetargetProfile:
    """Build the verified Mixamo humanoid -> Aurora profile used by the Workbench.

    Mixamo rigs use names like ``mixamorig:LeftArm`` rather than UE5 Manny names
    like ``upperarm_l``.  The generic role mapper is too loose for that family
    and can map hands/feet to Aurora helpers.  This profile keeps Mixamo as a
    first-class source family while feeding the same R3.B/segment-correction
    preview and export path used by the verified UE5 workflow.
    """

    source_names = [node.name for node in source_clip.nodes]
    if not is_mixamo_skeleton(source_names):
        raise ValueError("Source clip does not look like a Mixamo humanoid skeleton.")

    target_nodes = list(target_model.all_nodes())
    adapter_result = (adapter or MixamoSourceAdapter()).adapt(
        source_names,
        [node.name for node in target_nodes],
    )

    mappings: list[RetargetMappingEntry] = []
    for decision in adapter_result.mapped:
        if not decision.target_bone or not decision.role:
            continue
        mappings.append(
            RetargetMappingEntry(
                role=decision.role,
                source_node=decision.source_bone,
                target_node=decision.target_bone,
                side=decision.side or "center",
                notes=decision.reason,
            )
        )

    if len(mappings) < MIXAMO_TO_AURORA_MIN_CORE_MAPPING_COUNT:
        raise ValueError(
            "Verified Mixamo → Aurora mapping found too few usable core mappings "
            f"({len(mappings)} < {MIXAMO_TO_AURORA_MIN_CORE_MAPPING_COUNT})."
        )

    return RetargetProfile(
        version=1,
        name="verified_mixamo_to_aurora_profile",
        source_clip_hint=source_clip.source_path,
        target_model_hint=target_model.name,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=mappings,
        ignored_source_nodes=[decision.source_bone for decision in adapter_result.ignored],
        twist_sources={},
        metadata={
            "generated_by": "verified_mixamo_to_aurora_mapping",
            "source_adapter": "MixamoSourceAdapter",
            "source_skeleton_family": "mixamo",
            "mapped_count": len(mappings),
            "ignored_count": len(adapter_result.ignored),
            "unmapped_count": len(adapter_result.unmapped),
            "unmapped_source_nodes": [decision.source_bone for decision in adapter_result.unmapped],
            "recommended_rotation_transfer_mode": "exact_segment_correction",
            "key_unmapped_reference_nodes": True,
            "basis_conversion": "blender_fbx_to_aurora_negate_xy",
        },
    )


def validate_retarget_profile(
    profile: RetargetProfile,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    *,
    strict: bool = True,
    allow_custom_kotor_animation_name: bool = False,
    output_name_mode: KotorOutputAnimationNameMode | str = KotorOutputAnimationNameMode.VANILLA_SLOT,
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
    _validate_animation_slot(
        report,
        profile,
        target_model,
        allow_custom_kotor_animation_name=allow_custom_kotor_animation_name,
        output_name_mode=output_name_mode,
    )
    return report


def _normalize_name(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "_")


def _source_name_with_original_case(source_key: str, source_names: list[str]) -> str:
    wanted = str(source_key or "").lower()
    for name in source_names:
        if str(name or "").lower() == wanted:
            return str(name)
    return str(source_key or "")


def _ue5_verified_role(source_name: str) -> str:
    text = str(source_name or "").strip().lower()
    if text in _UE5_EXACT_ROLE_BY_SOURCE:
        return _UE5_EXACT_ROLE_BY_SOURCE[text]
    for prefix in _FINGER_ROLE_PREFIXES:
        if text.startswith(f"{prefix}_01"):
            return f"{prefix}_base"
        if text.startswith(f"{prefix}_03"):
            return f"{prefix}_tip"
    return _role_from_name(text) or text


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
    *,
    allow_custom_kotor_animation_name: bool = False,
    output_name_mode: KotorOutputAnimationNameMode | str = KotorOutputAnimationNameMode.VANILLA_SLOT,
) -> None:
    slot = str(profile.animation_slot or "").strip()
    if not slot:
        return
    mode = coerce_kotor_output_name_mode(output_name_mode)
    if allow_custom_kotor_animation_name or mode == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        try:
            validate_custom_kotor_animation_name(slot)
        except RetargetOutputNamingError as exc:
            report.add_error(str(exc))
        return
    try:
        resolve_animation_slot(target_model, slot, require_valid=True)
    except ValueError:
        report.add_error(
            f"Invalid animation slot '{slot}' for this target model/supermodel chain. "
            "UE clip names are not KOTOR animation slot names."
        )
