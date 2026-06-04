"""Character Builder MDL export preflight checks.

The Character Builder is not allowed to treat an imported FBX mesh as the
authority for a KOTOR character.  The selected native base model owns the
runtime DAG contract: exact node names, parent paths, socket hooks, deform
helpers, supermodel inheritance, and skin payload requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .kotor_constants import (
    CHARACTER_EXPORT_EVIDENCE,
    ENGINE_VERIFIED_SOCKET_STRING_REFS,
    KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS,
    KOTOR_SKIN_MAX_INFLUENCES_PER_VERTEX,
    KOTOR_SKIN_WEIGHT_SUM_TOLERANCE,
)
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

    export_game: str | None = None
    require_source_mdl: bool = True
    require_native_snapshot: bool = True
    require_native_snapshot_game_match: bool = True
    require_supermodel: bool = True
    require_skin_payload: bool = True
    require_native_bone_map_targets: bool = True
    require_no_non_native_skeleton_nodes: bool = True
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
        _validate_native_snapshot_game(native_snapshot, opts, report)
        _validate_source_provenance(native_snapshot, opts, report)
        _validate_supermodel(model, native_snapshot, opts, report)
        _validate_native_dag(model, native_snapshot, opts, report)
        _validate_no_non_native_skeleton_nodes(model, native_snapshot, opts, report)
        _validate_socket_categories(model, native_snapshot, opts, report)

    if opts.require_skin_payload:
        _validate_skin_payload(model, native_snapshot, opts, report)

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


def _validate_native_snapshot_game(
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_native_snapshot_game_match:
        return
    export_game = _normalize_kotor_game(opts.export_game)
    if not export_game:
        return

    metadata = dict(snapshot.metadata or {})
    game_facts = {
        "snapshot_game": snapshot.game,
        "metadata_source_game": metadata.get("source_game"),
        "metadata_game": metadata.get("game"),
    }
    normalized_facts = {
        key: _normalize_kotor_game(value)
        for key, value in game_facts.items()
        if str(value or "").strip()
    }
    matching_facts = {
        key: value
        for key, value in normalized_facts.items()
        if value == export_game
    }
    mismatches = {
        key: value
        for key, value in normalized_facts.items()
        if value and value != "UNKNOWN" and value != export_game
    }
    if not matching_facts and not mismatches:
        report.add(_issue(
            "blocking",
            "character.export.native_snapshot_game_unknown",
            (
                "Native skeleton snapshot does not prove which KOTOR game it "
                f"came from, but the export request targets {export_game}."
            ),
            fix_hint=(
                "Choose a base KOTOR model from the configured K1/K2 game "
                "library, then rebuild the native template rig before exporting."
            ),
            details={
                "export_game": export_game,
                "native_game_facts": game_facts,
                "normalized_native_game_facts": normalized_facts,
            },
        ))
        return
    if not mismatches:
        return

    report.add(_issue(
        "blocking",
        "character.export.native_snapshot_game_mismatch",
        (
            f"Native skeleton snapshot is for {', '.join(sorted(set(mismatches.values())))} "
            f"but the export request targets {export_game}."
        ),
        fix_hint=(
            "Choose a base KOTOR model from the same game as the export target, "
            "then rebuild the native template rig before exporting."
        ),
        details={
            "export_game": export_game,
            "native_game_facts": game_facts,
            "normalized_native_game_facts": normalized_facts,
            "mismatches": mismatches,
        },
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
            "blocking",
            "character.export.supermodel_case_changed",
            (
                f"Generated character supermodel casing changed from '{expected}' "
                f"to '{actual}'."
            ),
            fix_hint=(
                "Restore the exact supermodel casing from the selected native "
                "base before export. KOTOR supermodel case behavior is still "
                "Ghidra-pending, so Character Builder preserves the native value."
            ),
            details={
                "expected": expected,
                "actual": actual,
                "evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
                "pending_ghidra": "supermodel name resolution and resref case behavior",
            },
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
                    **_native_socket_evidence_details(snapshot, native_node),
                },
            ))
            continue
        if opts.strict_parent_paths:
            exact_name_match = _find_node_exact_name(current_nodes, native_node.name)
            if exact_name_match is not None:
                report.add(_issue(
                    "blocking",
                    "character.export.node_path_changed",
                    (
                        f"Native {native_node.export_role} node '{native_node.name}' "
                        "is present but no longer lives at its original parent path."
                    ),
                    navigation=ValidationNavigationTarget(node_name=native_node.name),
                    fix_hint=(
                        "Restore the selected native skeleton hierarchy before export; "
                        "KOTOR animation inheritance depends on exact node paths."
                    ),
                    details={
                        "expected_path": list(expected_path),
                        "actual_path": list(_node_path(exact_name_match)),
                        "role": native_node.export_role,
                        **_native_socket_evidence_details(snapshot, native_node),
                    },
                ))
                continue
            report.add(_issue(
                "blocking",
                "character.export.node_path_missing",
                (
                    f"Native {native_node.export_role} node '{native_node.name}' "
                    "is missing from its original parent path."
                ),
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Rebuild from the selected native skeleton or restore the node parent path.",
                details={
                    "expected_path": list(expected_path),
                    "role": native_node.export_role,
                    **_native_socket_evidence_details(snapshot, native_node),
                },
            ))
        elif _find_node_exact_name(current_nodes, native_node.name) is None:
            report.add(_issue(
                "blocking",
                "character.export.node_missing",
                f"Native {native_node.export_role} node '{native_node.name}' is missing.",
                navigation=ValidationNavigationTarget(node_name=native_node.name),
                fix_hint="Restore the native node before export.",
                details={
                    "role": native_node.export_role,
                    **_native_socket_evidence_details(snapshot, native_node),
                },
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
            category_evidence = _socket_category_evidence_details(snapshot, category)
            report.add(_issue(
                "blocking",
                "character.export.required_socket_missing",
                f"Required KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Restore the native attachment hook before export.",
                details={"category": category, **category_evidence},
            ))
    for category in opts.recommended_socket_categories:
        if category not in present_categories:
            category_evidence = _socket_category_evidence_details(snapshot, category)
            report.add(_issue(
                "warning",
                "character.export.recommended_socket_missing",
                f"Recommended KOTOR attachment socket category '{category}' is missing.",
                fix_hint="Preview equipment, weapons, and cutscene hooks before treating this model as game-ready.",
                details={"category": category, **category_evidence},
            ))


def _validate_no_non_native_skeleton_nodes(
    model: Any,
    snapshot: NativeSkeletonSnapshot,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    if not opts.require_no_non_native_skeleton_nodes:
        return

    native_paths = {tuple(node.full_path) for node in snapshot.nodes}
    native_names = set(snapshot.node_names())
    for node in _iter_nodes(model):
        path = _node_path(node)
        if path in native_paths:
            continue
        name = str(getattr(node, "name", "") or "")
        if name in native_names:
            # The exact-name/path mismatch is reported by _validate_native_dag.
            continue
        if _is_exportable_mesh_payload(node):
            continue
        report.add(_issue(
            "blocking",
            "character.export.non_native_skeleton_node",
            (
                f"Non-native node '{name or '<unnamed>'}' remains in the final "
                "Character Builder DAG."
            ),
            navigation=ValidationNavigationTarget(node_name=name),
            fix_hint=(
                "Remove imported armature/helper nodes before export. Only the "
                "selected KOTOR base skeleton may own the final DAG; imported "
                "content must be mesh/skin payload."
            ),
            details={
                "node_name": name,
                "actual_path": list(path),
                "native_snapshot_model": snapshot.model_name,
                "native_snapshot_game": snapshot.game,
                "allowed_non_native_role": "mesh_or_skin_payload",
                "engine_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
            },
        ))


def _is_exportable_mesh_payload(node: Any) -> bool:
    if bool(getattr(node, "is_skin", False)):
        return True
    if bool(getattr(node, "is_mesh", False)):
        return True
    if list(getattr(node, "vertices", []) or []) or list(getattr(node, "faces", []) or []):
        return True
    return False


def _socket_category_evidence_details(
    snapshot: NativeSkeletonSnapshot,
    category: str,
) -> dict[str, Any]:
    expected_nodes = tuple(
        node.name for node in snapshot.nodes
        if node.socket_category == category
    )
    return {
        "expected_native_socket_nodes": list(expected_nodes),
        **_socket_engine_evidence_details(snapshot.game, expected_nodes),
    }


def _native_socket_evidence_details(
    snapshot: NativeSkeletonSnapshot,
    node: NativeNodeSnapshot,
) -> dict[str, Any]:
    if not node.socket_category:
        return {}
    return {
        "socket_category": node.socket_category,
        **_socket_engine_evidence_details(snapshot.game, (node.name,)),
    }


def _socket_engine_evidence_details(game: str, names: tuple[str, ...]) -> dict[str, Any]:
    refs = _engine_string_refs_for_names(game, names)
    engine_verified = tuple(
        str(entry.get("string", "") or "")
        for entry in refs
        if str(entry.get("string", "") or "")
    )
    pending = tuple(name for name in names if name not in set(engine_verified))
    if engine_verified and pending:
        tier = "mixed_engine_string_refs_and_fixture_only"
    elif engine_verified:
        tier = "engine_string_ref_verified"
    elif names:
        tier = "native_fixture_only_pending_engine_string_ref"
    else:
        tier = "no_native_socket_fixture_nodes"
    return {
        "engine_string_evidence_status": KOTOR_ENGINE_SOCKET_STRING_EVIDENCE_STATUS,
        "engine_string_refs": refs,
        "engine_verified_socket_nodes": list(engine_verified),
        "pending_engine_string_ref_nodes": list(pending),
        "engine_evidence_tier": tier,
        "native_fixture_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
        "findings_doc": CHARACTER_EXPORT_EVIDENCE["findings_doc"],
    }


def _engine_string_refs_for_names(game: str, names: tuple[str, ...]) -> list[dict[str, object]]:
    game_key = str(game or "").strip().lower()
    wanted = {str(name or "") for name in names}
    refs: list[dict[str, object]] = []
    for entry in ENGINE_VERIFIED_SOCKET_STRING_REFS:
        if str(entry.get("game", "")).lower() != game_key:
            continue
        if str(entry.get("string", "")) not in wanted:
            continue
        refs.append({
            "string": str(entry.get("string", "")),
            "string_address": str(entry.get("string_address", "")),
            "representative_refs": list(entry.get("representative_refs", ()) or ()),
        })
    return refs


def _validate_skin_payload(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
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
        if vertices and faces:
            _validate_skin_geometry_values(node, vertices, faces, report)
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
        if bone_map and qbone_list:
            _validate_bind_transform_rows(
                node,
                qbone_list,
                kind="qbone",
                expected_components=4,
                report=report,
            )
        if bone_map and len(tbone_list) != len(bone_map):
            report.add(_issue(
                "blocking",
                "character.export.tbone_mismatch",
                f"Skin mesh '{name}' tbone list does not match the bone map.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={"bone_map": len(bone_map), "tbone_list": len(tbone_list)},
            ))
        if bone_map and tbone_list:
            _validate_bind_transform_rows(
                node,
                tbone_list,
                kind="tbone",
                expected_components=3,
                report=report,
            )
        if bone_map:
            _validate_bone_map_targets(node, bone_map, model, native_snapshot, opts, report)
        _validate_skin_rows(node, bone_map, report)


def _validate_skin_geometry_values(
    node: Any,
    vertices: list[Any],
    faces: list[Any],
    report: ValidationReport,
) -> None:
    name = str(getattr(node, "name", "") or "")
    for vertex_index, vertex in enumerate(vertices):
        try:
            components = _numeric_components(vertex)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < 3:
            report.add(_issue(
                "blocking",
                "character.export.vertex_malformed",
                f"Skin mesh '{name}' has a vertex without three coordinates.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild the imported mesh payload before export.",
                details={"vertex_index": vertex_index, "component_count": len(components)},
            ))
            continue
        if not _all_finite(components[:3]):
            report.add(_issue(
                "blocking",
                "character.export.vertex_nonfinite",
                f"Skin mesh '{name}' has a vertex with non-finite coordinates.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild or clean the imported mesh payload before export.",
                details={"vertex_index": vertex_index, "coordinates": [str(value) for value in components[:3]]},
            ))

    normals = list(getattr(node, "normals", []) or [])
    for normal_index, normal in enumerate(normals):
        try:
            components = _numeric_components(normal)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < 3 or not _all_finite(components[:3]):
            report.add(_issue(
                "blocking",
                "character.export.normal_nonfinite",
                f"Skin mesh '{name}' has an invalid normal vector.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh normals before export.",
                details={"normal_index": normal_index, "components": [str(value) for value in components]},
            ))

    for face_index, face in enumerate(faces):
        try:
            face_components = _numeric_components(face)
        except (TypeError, ValueError, OverflowError):
            face_components = []
        if len(face_components) < 3:
            report.add(_issue(
                "blocking",
                "character.export.face_malformed",
                f"Skin mesh '{name}' has a face without three vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Triangulate or rebuild the imported mesh payload before export.",
                details={"face_index": face_index, "index_count": len(face_components)},
            ))
            continue
        first_three = face_components[:3]
        nonfinite_indices = [str(value) for value in first_three if not math.isfinite(value)]
        if nonfinite_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_nonfinite",
                f"Skin mesh '{name}' has a face with non-finite vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export.",
                details={"face_index": face_index, "indices": nonfinite_indices},
            ))
            continue
        noninteger_indices = [value for value in first_three if not float(value).is_integer()]
        if noninteger_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_noninteger",
                f"Skin mesh '{name}' has a face with non-integer vertex indices.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export; MDL face indices must reference exact vertices.",
                details={
                    "face_index": face_index,
                    "indices": [str(value) for value in noninteger_indices],
                },
            ))
            continue
        indices = [int(value) for value in first_three]
        bad_indices = [index for index in indices[:3] if index < 0 or index >= len(vertices)]
        if bad_indices:
            report.add(_issue(
                "blocking",
                "character.export.face_index_out_of_range",
                f"Skin mesh '{name}' has a face referencing a missing vertex.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild mesh faces before export.",
                details={
                    "face_index": face_index,
                    "bad_indices": bad_indices,
                    "vertex_count": len(vertices),
                },
            ))


def _validate_bind_transform_rows(
    node: Any,
    rows: list[Any],
    *,
    kind: str,
    expected_components: int,
    report: ValidationReport,
) -> None:
    name = str(getattr(node, "name", "") or "")
    for row_index, row in enumerate(rows):
        try:
            components = _numeric_components(row)
        except (TypeError, ValueError, OverflowError):
            components = []
        if len(components) < expected_components or not _all_finite(components[:expected_components]):
            report.add(_issue(
                "blocking",
                f"character.export.{kind}_nonfinite",
                f"Skin mesh '{name}' has invalid {kind} bind-transform metadata.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild qbone/tbone skin metadata before export.",
                details={
                    "row_index": row_index,
                    "component_count": len(components),
                    "expected_components": expected_components,
                    "components": [str(value) for value in components],
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))


def _validate_bone_map_targets(
    node: Any,
    bone_map: list[Any],
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
    opts: CharacterExportPreflightOptions,
    report: ValidationReport,
) -> None:
    """Require skin bindings to target the selected native KOTOR DAG.

    See ``CHARACTER_EXPORT_EVIDENCE`` and ``docs/ghidra_findings.md`` for the
    current evidence tier: native fixture/snapshot contracts are verified,
    while final MDL loader skin-reference semantics are still pending.
    """
    mesh_name = str(getattr(node, "name", "") or "")
    current_nodes = list(_iter_nodes(model))
    current_names = {str(getattr(current, "name", "") or "") for current in current_nodes}
    current_lower = {name.lower(): name for name in current_names}
    native_names = set(native_snapshot.node_names()) if native_snapshot is not None else set()
    native_lower = {name.lower(): name for name in native_names}

    for bone_map_index, bone_name_raw in enumerate(bone_map):
        bone_name = str(bone_name_raw or "").strip()
        if not bone_name:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_empty_target",
                f"Skin mesh '{mesh_name}' has an empty bone-map target.",
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint="Rebuild the skin bone map from the selected native KOTOR skeleton.",
                details={"bone_map_index": bone_map_index},
            ))
            continue

        if bone_name not in current_names:
            lower_match = current_lower.get(bone_name.lower())
            if lower_match is not None:
                report.add(_issue(
                    "blocking",
                    "character.export.bonemap_target_case_changed",
                    (
                        f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                        f"does not match native node casing '{lower_match}'."
                    ),
                    navigation=ValidationNavigationTarget(node_name=mesh_name),
                    fix_hint="Restore exact KOTOR node casing in the skin bone map.",
                    details={
                        "bone_map_index": bone_map_index,
                        "bone_name": bone_name,
                        "actual_node_name": lower_match,
                    },
                ))
            else:
                report.add(_issue(
                    "blocking",
                    "character.export.bonemap_target_missing",
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' does not exist in the export DAG.",
                    navigation=ValidationNavigationTarget(node_name=mesh_name),
                    fix_hint="Bind skin weights only to nodes that exist in the selected native KOTOR skeleton.",
                    details={
                        "bone_map_index": bone_map_index,
                        "bone_name": bone_name,
                    },
                ))
            continue

        if not opts.require_native_bone_map_targets or native_snapshot is None:
            continue

        if bone_name in native_names:
            continue
        native_case_match = native_lower.get(bone_name.lower())
        if native_case_match is not None:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_native_target_case_changed",
                (
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                    f"does not match native snapshot casing '{native_case_match}'."
                ),
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint="Use exact native KOTOR node casing in the skin bone map.",
                details={
                    "bone_map_index": bone_map_index,
                    "bone_name": bone_name,
                    "expected_native_name": native_case_match,
                    "native_snapshot_model": native_snapshot.model_name,
                },
            ))
        else:
            report.add(_issue(
                "blocking",
                "character.export.bonemap_target_not_native",
                (
                    f"Skin mesh '{mesh_name}' bone-map target '{bone_name}' "
                    "is not part of the selected native KOTOR skeleton snapshot."
                ),
                navigation=ValidationNavigationTarget(node_name=mesh_name),
                fix_hint=(
                    "Remove imported/temporary skeleton nodes from the skin bone map "
                    "and bind the mesh to the native KOTOR template nodes."
                ),
                details={
                    "bone_map_index": bone_map_index,
                    "bone_name": bone_name,
                    "native_snapshot_model": native_snapshot.model_name,
                    "engine_evidence_status": CHARACTER_EXPORT_EVIDENCE["status"],
                },
            ))


def _numeric_components(value: Any) -> list[float]:
    if isinstance(value, (str, bytes)):
        raise TypeError("string values are not numeric components")
    if isinstance(value, (int, float)):
        return [float(value)]
    components: list[float] = []
    if isinstance(value, dict):
        iterable = value.values()
    elif isinstance(value, (list, tuple)):
        iterable = value
    else:
        attrs = [getattr(value, attr) for attr in ("x", "y", "z", "w") if hasattr(value, attr)]
        if attrs:
            iterable = attrs
        else:
            try:
                iterable = iter(value)
            except TypeError as exc:
                raise TypeError("value is not a numeric component sequence") from exc

    for item in iterable:
        if isinstance(item, (list, tuple, dict)):
            components.extend(_numeric_components(item))
        elif isinstance(item, (str, bytes)):
            raise TypeError("string values are not numeric components")
        else:
            components.append(float(item))
    return components


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


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
        has_malformed_weight = False
        for influence in influences:
            try:
                bone_index = int(getattr(influence, "bone_index", -1))
            except (TypeError, ValueError, OverflowError):
                bone_index = -1
            try:
                weight = float(getattr(influence, "weight", 0.0))
            except (TypeError, ValueError, OverflowError):
                weight = math.nan
            if not math.isfinite(weight):
                has_malformed_weight = True
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_weight_nonfinite",
                    f"Skin mesh '{name}' has a non-finite vertex weight.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export; MDL/MDX skin weights must be finite numbers.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "weight": str(weight),
                        "evidence_status": "writer_format_contract_verified_ghidra_pending",
                    },
                ))
                continue
            if weight < 0.0:
                has_malformed_weight = True
                report.add(_issue(
                    "blocking",
                    "character.export.vertex_weight_negative",
                    f"Skin mesh '{name}' has a negative vertex weight.",
                    navigation=ValidationNavigationTarget(node_name=name),
                    fix_hint="Rebuild skin weights before export; KOTOR skin influences must not contain negative weights.",
                    details={
                        "vertex_index": row_index,
                        "bone_index": bone_index,
                        "weight": weight,
                        "evidence_status": "writer_format_contract_verified_ghidra_pending",
                    },
                ))
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
        if not has_malformed_weight and total <= 0.0:
            report.add(_issue(
                "blocking",
                "character.export.vertex_weight_zero_sum",
                f"Skin mesh '{name}' has a vertex whose weights sum to zero.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Rebuild skin weights before export; every vertex needs a positive normalized weight sum.",
                details={
                    "vertex_index": row_index,
                    "weight_sum": total,
                    "evidence_status": "writer_format_contract_verified_ghidra_pending",
                },
            ))
        elif (
            not has_malformed_weight
            and abs(total - 1.0) > KOTOR_SKIN_WEIGHT_SUM_TOLERANCE
        ):
            report.add(_issue(
                "warning",
                "character.export.vertex_weight_sum",
                f"Skin mesh '{name}' has a vertex whose weights do not sum to 1.0.",
                navigation=ValidationNavigationTarget(node_name=name),
                fix_hint="Normalize skin weights before final export.",
                details={
                    "vertex_index": row_index,
                    "weight_sum": total,
                    "tolerance": KOTOR_SKIN_WEIGHT_SUM_TOLERANCE,
                    "pending_ghidra": "engine_weight_normalization_behavior",
                },
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


def _normalize_kotor_game(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = raw.lower().replace("_", " ").replace("-", " ")
    compact = " ".join(compact.split())
    if (
        compact in {"2", "k2", "tsl", "kotor2", "kotor 2", "kotor ii"}
        or "gameversion.k2" in compact
        or "kotor ii" in compact
        or "kotor 2" in compact
        or "the sith lords" in compact
        or "swkotor2" in compact
    ):
        return "K2"
    if (
        compact in {"1", "k1", "kotor1", "kotor 1", "kotor i"}
        or "gameversion.k1" in compact
        or "kotor i" in compact
        or "kotor 1" in compact
        or compact == "knights of the old republic"
        or "swkotor" in compact
    ):
        return "K1"
    return raw.upper()


def _find_node_exact_name(nodes: list[Any], name: str) -> Any | None:
    for node in nodes:
        if str(getattr(node, "name", "") or "") == name:
            return node
    return None
