"""Character Builder MDL export preflight checks.

The Character Builder is not allowed to treat an imported FBX mesh as the
authority for a KOTOR character.  The selected native base model owns the
runtime DAG contract: exact node names, parent paths, socket hooks, deform
helpers, supermodel inheritance, and skin payload requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .kotor_constants import CHARACTER_EXPORT_EVIDENCE, KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX
from .character_rig_state import (
    RIG_STATE_NATIVE_TEMPLATE_FINAL,
    get_character_rig_state,
    is_native_template_final_rig,
)
from .native_skeleton import (
    KOTOR_NATIVE_RESREF_MAX_LEN,
    NativeNodeSnapshot,
    NativeSkeletonSnapshot,
    capture_native_skeleton_snapshot,
)


_NULL_SUPERMODELS = {"", "NULL", "NONE"}
_STRUCTURAL_ROLES = {"socket", "helper", "deform_helper"}


@dataclass(frozen=True)
class CharacterExportPreflightOptions:
    """Tunable checks for Character Builder MDL/MDX export readiness."""

    require_source_mdl: bool = True
    require_native_snapshot: bool = True
    require_supermodel: bool = True
    require_skin_payload: bool = True
    require_required_sockets: bool = True
    require_native_template_final_rig: bool = True
    strict_parent_paths: bool = True
    required_socket_categories: tuple[str, ...] = (
        "head",
        "right_hand",
        "left_hand",
    )
    recommended_socket_categories: tuple[str, ...] = (
        "lightsaber",
        "combat_helper",
        "camera",
        "headgear",
    )


@dataclass(frozen=True)
class CharacterExportPreflightResult:
    """Result returned by :func:`preflight_character_mdl_export`."""

    report: ValidationReport
    native_snapshot: NativeSkeletonSnapshot | None = None

    @property
    def export_allowed(self) -> bool:
        return not self.report.has_blocking


def preflight_character_mdl_export(
    model: Any,
    *,
    native_snapshot: NativeSkeletonSnapshot | None = None,
    options: CharacterExportPreflightOptions | None = None,
) -> CharacterExportPreflightResult:
    """Validate that a Character Builder model is ready for MDL/MDX export.

    This does not write files.  It verifies the export contract that the engine
    depends on before a future binary writer tries to create a game candidate.
    """

    opts = options or CharacterExportPreflightOptions()
    report = ValidationReport(source="character.export_preflight")

    if model is None:
        report.add(_issue(
            "blocking",
            "character.export.no_model",
            "Character export requires a model.",
            fix_hint="Choose a base KOTOR model and import a custom mesh before exporting.",
        ))
        return CharacterExportPreflightResult(report=report, native_snapshot=None)

    if native_snapshot is None:
        native_snapshot = getattr(model, "_gr_native_skeleton_snapshot", None)

    if native_snapshot is None and opts.require_native_snapshot:
        report.add(_issue(
            "blocking",
            "character.export.missing_native_snapshot",
            "Character export requires a native KOTOR skeleton snapshot.",
            fix_hint="Choose a base KOTOR MDL from the game library before building the character rig.",
        ))
    elif native_snapshot is None:
        try:
            native_snapshot = capture_native_skeleton_snapshot(model)
        except Exception as exc:  # pragma: no cover - defensive only
            report.add(_issue(
                "error",
                "character.export.snapshot_failed",
                f"Could not capture a native skeleton snapshot: {exc}",
            ))

    _validate_resref(model, report)
    _validate_character_rig_state(model, opts, report)

    if native_snapshot is not None:
        _validate_source_provenance(native_snapshot, opts, report)
        _validate_supermodel(model, native_snapshot, opts, report)
        _validate_native_dag(model, native_snapshot, opts, report)
        _validate_socket_categories(model, native_snapshot, opts, report)

    if opts.require_skin_payload:
        _validate_skin_payload(model, report)

    return CharacterExportPreflightResult(report=report, native_snapshot=native_snapshot)


def _validate_character_rig_state(
    model: Any,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_native_template_final_rig:
        return
    if is_native_template_final_rig(model):
        return
    state = get_character_rig_state(model)
    state_data = state.to_dict() if state is not None else None
    report.add(_issue(
        "blocking",
        "character.export.not_native_template_final_rig",
        (
            "Character export requires the final native KOTOR template rig state. "
            "Imported or temporary skeletons cannot be exported as game-ready MDL/MDX."
        ),
        fix_hint="Use Build KOTOR Skeleton from the selected native base before exporting.",
        details={
            "expected_state": RIG_STATE_NATIVE_TEMPLATE_FINAL,
            "actual_state": state_data,
        },
    ))


def _validate_resref(model: Any, report: ValidationReport) -> None:
    name = str(getattr(model, "name", "") or "").strip()
    if not name:
        report.add(_issue(
            "blocking",
            "character.export.empty_resref",
            "Character model resref is empty.",
            fix_hint="Assign a stable KOTOR resref before export.",
        ))
        return
    if len(name) > KOTOR_NATIVE_RESREF_MAX_LEN:
        report.add(_issue(
            "blocking",
            "character.export.resref_too_long",
            (
                f"Character model resref '{name}' is longer than "
                f"{KOTOR_NATIVE_RESREF_MAX_LEN} characters."
            ),
            fix_hint="Use a KOTOR-safe resref of 16 characters or fewer.",
            details={"resref": name, "max_length": KOTOR_NATIVE_RESREF_MAX_LEN},
        ))


def _validate_source_provenance(
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_source_mdl:
        return
    metadata = dict(snapshot.metadata or {})
    has_source = bool(
        metadata.get("source_mdl_path")
        or metadata.get("source_resref")
        or metadata.get("source_resource_address")
    )
    if not has_source:
        report.add(_issue(
            "blocking",
            "character.export.no_native_source",
            "Native skeleton snapshot has no source MDL provenance.",
            fix_hint=(
                "Load the base skeleton from a game-library MDL/resref so export "
                "can preserve the native DAG instead of guessing it."
            ),
            details={"model_name": snapshot.model_name},
        ))


def _validate_supermodel(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_supermodel:
        return
    expected = str(snapshot.supermodel or "NULL").strip()
    actual = str(getattr(model, "supermodel", "") or "NULL").strip()
    if expected.upper() in _NULL_SUPERMODELS:
        if actual.upper() in _NULL_SUPERMODELS:
            return
        report.add(_issue(
            "warning",
            "character.export.supermodel_added",
            (
                f"Generated character uses supermodel '{actual}', but the native "
                f"base model '{snapshot.model_name}' had no supermodel."
            ),
            fix_hint="Verify this is intentional before exporting.",
        ))
        return
    if actual.lower() != expected.lower():
        report.add(_issue(
            "blocking",
            "character.export.supermodel_mismatch",
            (
                f"Generated character supermodel '{actual}' does not match the "
                f"native base supermodel '{expected}'."
            ),
            fix_hint="Preserve the selected base model's supermodel unless you are deliberately changing animation inheritance.",
            details={"expected": expected, "actual": actual},
        ))
    elif actual != expected:
        report.add(_issue(
            "warning",
            "character.export.supermodel_case_changed",
            (
                f"Generated character supermodel casing changed from '{expected}' "
                f"to '{actual}'."
            ),
            fix_hint="Keep native casing for writer/readback parity.",
            details={"expected": expected, "actual": actual},
        ))


def _validate_native_dag(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    current_nodes = list(_iter_nodes(model))
    current_paths = {_node_path(node): node for node in current_nodes}
    current_paths_lower = {
        tuple(part.lower() for part in _node_path(node)): node
        for node in current_nodes
    }

    for native_node in snapshot.nodes:
        if native_node.export_role not in _STRUCTURAL_ROLES:
            continue
        expected_path = tuple(native_node.full_path)
        found = current_paths.get(expected_path)
        if found is not None:
            continue
        lower_match = current_paths_lower.get(tuple(part.lower() for part in expected_path))
        if lower_match is not None:
            report.add(_issue(
                "blocking",
                "character.export.node_case_changed",
                (
                    f"Native node '{native_node.name}' is present with changed "
                    "casing or parent-path casing."
                ),
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Restore exact KOTOR node casing before export.",
                details={
                    "expected_path": list(expected_path),
                    "actual_path": list(_node_path(lower_match)),
                    "role": native_node.export_role,
                },
            ))
            continue
        if opts.strict_parent_paths:
            report.add(_issue(
                "blocking",
                "character.export.node_path_missing",
                (
                    f"Native {native_node.export_role} node '{native_node.name}' "
                    "is missing from its original parent path."
                ),
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Rebuild from the selected native skeleton or restore the node parent path.",
                details={"expected_path": list(expected_path), "role": native_node.export_role},
            ))
        elif _find_node_exact_name(current_nodes, native_node.name) is None:
            report.add(_issue(
                "blocking",
                "character.export.node_missing",
                f"Native {native_node.export_role} node '{native_node.name}' is missing.",
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Restore the native node before export.",
                details={"role": native_node.export_role},
            ))


def _validate_socket_categories(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_required_sockets:
        return
    current_nodes = list(_iter_nodes(model))
    present_categories = {
        node.socket_category
        for node in snapshot.nodes
        if node.socket_category and _find_node_exact_path(current_nodes, tuple(node.full_path)) is not None
    }
    for category in opts.required_socket_categories:
        if category not in present_categories:
            report.add(_issue(
                "blocking",
                "character.export.required_socket_missing",
                f"Required KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Restore the native attachment hook before export.",
                details={"category": category},
            ))
    for category in opts.recommended_socket_categories:
        if category not in present_categories:
            report.add(_issue(
                "warning",
                "character.export.recommended_socket_missing",
                f"Recommended KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Preview equipment, weapons, and cutscene hooks before treating this model as game-ready.",
                details={"category": category},
            ))


def _validate_skin_payload(model: Any, report: ValidationReport) -> None:
    skin_nodes = [
        node for node in _iter_nodes(model)
        if bool(getattr(node, "is_skin", False))
    ]
    if not skin_nodes:
        report.add(_issue(
            "blocking",
            "character.export.no_skin_payload",
            "Character export requires at least one skinned mesh payload.",
            fix_hint="Import a render mesh and bind it to the selected KOTOR skeleton before export.",
        ))
        return

    for node in skin_nodes:
        name = str(getattr(node, "name", "") or "")
        vertices = list(getattr(node, "vertices", []) or [])
        faces = list(getattr(node, "faces", []) or [])
        bone_map = list(getattr(node, "bone_map", []) or [])
        qbone_list = list(getattr(node, "qbone_list", []) or [])
        tbone_list = list(getattr(node, "tbone_list", []) or [])
        skin_data = list(getattr(node, "skin_data", []) or [])

        if not vertices or not faces:
            report.add(_issue(
                "blocking",
                "character.export.empty_skin_geometry",
                f"Skin mesh '{name}' has no exportable geometry.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Verify the imported mesh payload before export.",
            ))
        if not bone_map:
            report.add(_issue(
                "blocking",
                "character.export.empty_bonemap",
                f"Skin mesh '{name}' has no bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Bind the mesh to the KOTOR skeleton before export.",
            ))
        if skin_data and len(skin_data) != len(vertices):
            report.add(_issue(
                "blocking",
                "character.export.skin_row_count_mismatch",
                (
                    f"Skin mesh '{name}' has {len(skin_data)} skin rows for "
                    f"{len(vertices)} vertices."
                ),
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export.",
            ))
        elif not skin_data:
            report.add(_issue(
                "blocking",
                "character.export.no_skin_rows",
                f"Skin mesh '{name}' has no per-vertex skin weights.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Bind the mesh to the KOTOR skeleton before export.",
            ))
        if bone_map and len(qbone_list) != len(bone_map):
            report.add(_issue(
                "blocking",
                "character.export.qbone_mismatch",
                f"Skin mesh '{name}' qbone list does not match the bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={"bone_map": len(bone_map), "qbone_list": len(qbone_list)},
            ))
        if bone_map and len(tbone_list) != len(bone_map):
            report.add(_issue(
                "blocking",
                "character.export.tbone_mismatch",
                f"Skin mesh '{name}' tbone list does not match the bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={"bone_map": len(bone_map), "tbone_list": len(tbone_list)},
            ))
        _validate_skin_rows(node, bone_map, report)


def _validate_skin_rows(node: Any, bone_map: list[Any], report: ValidationReport) -> None:
    name = str(getattr(node, "name", "") or "")
    for row_index, row in enumerate(list(getattr(node, "skin_data", []) or [])):
        influences = list(getattr(row, "influences", []) or [])
        if not influences:
            report.add(_issue(
                "blocking",
                "character.export.vertex_unweighted",
                f"Skin mesh '{name}' has an unweighted vertex.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export.",
                details={"vertex_index": row_index},
            ))
            continue
        if len(influences) > KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX:
            report.add(_issue(
                "blocking",
                "character.export.vertex_too_many_influences",
                (
                    f"Skin mesh '{name}' has a vertex with {len(influences)} "
                    f"influences; the KOTOR MDL writer stores at most "
                    f"{KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX}."
                ),
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Prune and normalize skin weights before export.",
                details={
                    "vertex_index": row_index,
                    "influence_count": len(influences),
                    "max_influences": KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX,
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))
        total = 0.0
        for influence in influences:
            bone_index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0) or 0.0)
            total += weight
            if bone_index < 0 or bone_index >= len(bone_map):
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_bone_index_out_of_range",
                    f"Skin mesh '{name}' has a vertex influence outside its bone map.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "bone_map_size": len(bone_map),
                    },
                ))
        if abs(total - 1.0) > 0.01:
            report.add(_issue(
                "warning",
                "character.export.vertex_weight_sum",
                f"Skin mesh '{name}' has a vertex whose weights do not sum to 1.0.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Normalize skin weights before final export.",
                details={"vertex_index": row_index, "weight_sum": total},
            ))


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    navigation: ValidationNavigationTarget | None = None,
    fix_hint: str | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    payload = dict(details or {})
    payload.setdefault("engine_evidence", CHARACTER_EXPORT_EVIDENCE)
    return ValidationIssue(
        severity=ValidationSeverity(severity),
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        navigation=navigation,
        fix_hint=fix_hint,
        details=payload,
    )


def _iter_nodes(model: Any) -> list[Any]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        return list(all_nodes())
    root = getattr(model, "root_node", None)
    if root is None:
        return []
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
        stack.extend(reversed(list(getattr(node, "children", []) or [])))
    return result


def _node_path(node: Any) -> tuple[str, ...]:
    names = [str(getattr(node, "name", "") or "")]
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


def _find_node_exact_path(nodes: list[Any], path: tuple[str, ...]) -> Any | None:
    for node in nodes:
        if _node_path(node) == path:
            return node
    return None


def _find_node_exact_name(nodes: list[Any], name: str) -> Any | None:
    for node in nodes:
        if str(getattr(node, "name", "") or "") == name:
            return node
    return None
