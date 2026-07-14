"""Project Map Studio readiness into KMAP validation-table issues.

The Level Editor already has a validation table with suggested fixes.  This
module keeps the authored-module readiness policy in core while giving the UI a
plain issue list it can display without knowing how readiness is derived.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.core.level import KMapValidationIssue


def authored_module_readiness_validation_issues(
    readiness: Any | None,
    *,
    bridge_warnings: Iterable[str] = (),
    bridge_blocking_messages: Iterable[str] = (),
) -> list[KMapValidationIssue]:
    """Return validation rows for Map Studio readiness/status state."""

    issues: list[KMapValidationIssue] = []
    for index, message in enumerate(tuple(bridge_blocking_messages or ())):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_AUTHORED_SECTION_INVALID",
                str(message),
                f"authored_module:bridge:{index}",
                "Open the KMAP in Map Studio Builder and recreate or repair the authored module section.",
            )
        )
    for index, message in enumerate(tuple(bridge_warnings or ())):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_AUTHORED_MODULE_MISSING",
                str(message),
                f"authored_module:bridge_warning:{index}",
                "Use Map Studio Builder to create terrain, a starter room, or a dev-test map before export.",
            )
        )
    if readiness is None:
        return _dedupe(issues)

    metadata = dict(getattr(readiness, "metadata", {}) or {})
    project_texture_validation = dict(metadata.get("project_texture_validation", {}) or {})
    project_texture_rows = tuple(
        dict(row)
        for row in tuple(project_texture_validation.get("issues") or ())
        if isinstance(row, dict)
    )
    project_texture_blocking_tails = {
        _message_tail(str(row.get("message") or ""))
        for row in project_texture_rows
        if str(row.get("severity") or "").lower() == "error"
    }
    project_texture_warning_tails = {
        _message_tail(str(row.get("message") or ""))
        for row in project_texture_rows
        if str(row.get("severity") or "").lower() == "warning"
    }
    geometry_validation = dict(metadata.get("geometry_validation", {}) or {})
    geometry_blocking_messages = tuple(
        str(message) for message in tuple(geometry_validation.get("blocking_messages") or ()) if str(message).strip()
    )
    geometry_warnings = tuple(
        str(message) for message in tuple(geometry_validation.get("warnings") or ()) if str(message).strip()
    )
    geometry_winding_warnings = tuple(
        message
        for message in geometry_warnings
        if "floor-plan winding" in message.lower() or ("clockwise" in message.lower() and "cleanup face normals" in message.lower())
    )
    geometry_degenerate_blockers = tuple(
        message
        for message in geometry_blocking_messages
        if "degenerate" in message.lower() or "zero-area face" in message.lower() or "zero area face" in message.lower()
    )
    geometry_blocking_tails = {_message_tail(message) for message in geometry_blocking_messages}
    geometry_warning_tails = {_message_tail(message) for message in geometry_warnings}
    geometry_winding_warning_tails = {_message_tail(message) for message in geometry_winding_warnings}
    geometry_degenerate_blocker_tails = {_message_tail(message) for message in geometry_degenerate_blockers}
    geometry_fix = str(geometry_validation.get("fix_hint") or "").strip() or (
        "Use Cleanup Footprint, Weld Vertices, Cleanup Face Normals, or split invalid floor-plan rooms before build/export."
    )
    for index, message in enumerate(geometry_degenerate_blockers):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_DEGENERATE_FACE",
                message,
                f"authored_floor_plan_degenerate_face:blocker:{index}",
                "Use Cleanup, Weld/Merge, Split, or Triangulate to remove zero-area authored faces before generating MDL/WOK output.",
            )
        )
    for index, message in enumerate(geometry_blocking_messages):
        if _message_tail(message) in geometry_degenerate_blocker_tails:
            continue
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_BLOCKER",
                message,
                f"authored_floor_plan_geometry:blocker:{index}",
                geometry_fix,
            )
        )
    for index, message in enumerate(geometry_winding_warnings):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING",
                message,
                f"authored_floor_plan_winding:warning:{index}",
                "Use Cleanup Face Normals or Reverse Normals so generated room geometry and WOK winding face the intended direction.",
            )
        )
    for index, message in enumerate(geometry_warnings):
        if _message_tail(message) in geometry_winding_warning_tails:
            continue
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_WARNING",
                message,
                f"authored_floor_plan_geometry:warning:{index}",
                geometry_fix,
            )
        )

    pathing = dict(metadata.get("pathing", {}) or {})
    pathing_blocking_messages = tuple(
        str(message) for message in tuple(pathing.get("blocking_messages") or ()) if str(message).strip()
    )
    pathing_warnings = tuple(str(message) for message in tuple(pathing.get("warnings") or ()) if str(message).strip())
    pathing_blocking_tails = {_message_tail(message) for message in pathing_blocking_messages}
    pathing_warning_tails = {_message_tail(message) for message in pathing_warnings}
    pathing_fix = str(pathing.get("fix_hint") or "").strip() or (
        "Move the module entry point, doors, triggers, waypoints, creatures, and placeables onto generated walkable WOK before export."
    )
    player_start_targets = tuple(
        dict(target)
        for target in tuple(pathing.get("blocking_targets") or ())
        if str(dict(target).get("anchor_label") or "").strip() == "entry_point"
        or str(dict(target).get("target_id") or "").strip() == "entry_point"
        or str(dict(target).get("workspace") or "").strip() == "entry_point"
    )
    player_start_pathing_messages = tuple(
        str(target.get("message") or "Module entry point/player start is not on generated walkable WOK.").strip()
        for target in player_start_targets
        if str(target.get("message") or "").strip()
    ) or tuple(message for message in pathing_blocking_messages if "entry_point" in message or "player start" in message.lower())
    player_start_pathing_tails = {_message_tail(message) for message in player_start_pathing_messages}
    for index, message in enumerate(player_start_pathing_messages):
        target = player_start_targets[index] if index < len(player_start_targets) else {}
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_PLAYER_START_NOT_WALKABLE",
                message.replace("entry_point", "Module entry point/player start", 1),
                f"authored_entry_point:walkable:{index}",
                str(target.get("fix_action") or "").strip()
                or "Focus the module entry point controls and move the player start onto generated walkable WOK.",
            )
        )
    for index, message in enumerate(pathing_blocking_messages):
        if _message_tail(message) in player_start_pathing_tails:
            continue
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_PTH_PATHING_BLOCKER",
                message,
                f"authored_pth_pathing:blocker:{index}",
                pathing_fix,
            )
        )
    for index, message in enumerate(pathing_warnings):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_PTH_PATHING_WARNING",
                message,
                f"authored_pth_pathing:warning:{index}",
                pathing_fix,
            )
        )

    topology_specs = (
        (
            "invalid_wok_face_count",
            "invalid vertex indices",
            "MAP_STUDIO_WOK_INVALID_TRIANGLE",
            "authored_wok_invalid_triangle:blocker",
            "Regenerate or repair the room/walkmesh so every WOK triangle references valid vertices before export.",
            "Generated WOK has {count} triangle(s) with invalid vertex indices.",
        ),
        (
            "degenerate_wok_face_count",
            "degenerate face",
            "MAP_STUDIO_WOK_DEGENERATE_TRIANGLE",
            "authored_wok_degenerate_triangle:blocker",
            "Use Cleanup, Weld/Merge, Flatten, or Triangulate to remove zero-area WOK triangles before export.",
            "Generated WOK has {count} degenerate triangle(s).",
        ),
        (
            "non_manifold_wok_edge_count",
            "non-manifold walkable edge",
            "MAP_STUDIO_WOK_NON_MANIFOLD_EDGE",
            "authored_wok_non_manifold_edge:blocker",
            "Separate, bridge, weld, or cleanup the affected walkable surfaces so each WOK edge has valid ownership.",
            "Generated WOK has {count} non-manifold walkable edge(s).",
        ),
    )
    topology_blocking_tails: set[str] = set()
    for metadata_key, phrase, code, location_prefix, fix, fallback in topology_specs:
        topology_messages = tuple(
            str(message)
            for message in tuple(getattr(readiness, "blocking_messages", ()) or ())
            if phrase in str(message)
        )
        if not topology_messages and int(metadata.get(metadata_key, 0) or 0) > 0:
            topology_messages = (fallback.format(count=int(metadata.get(metadata_key, 0) or 0)),)
        topology_blocking_tails.update(_message_tail(message) for message in topology_messages)
        for index, message in enumerate(topology_messages):
            issues.append(
                KMapValidationIssue(
                    "Error",
                    code,
                    message,
                    f"{location_prefix}:{index}",
                    fix,
                )
            )

    slope_blocking_messages = tuple(
        str(message)
        for message in tuple(getattr(readiness, "blocking_messages", ()) or ())
        if "steeper than" in str(message) and "walkable face" in str(message)
    )
    if not slope_blocking_messages and int(metadata.get("steep_walkable_face_count", 0) or 0) > 0:
        count = int(metadata.get("steep_walkable_face_count", 0) or 0)
        max_slope = float(metadata.get("max_walkable_slope_degrees", 0.0) or 0.0)
        allowed = float(metadata.get("max_allowed_walkable_slope_degrees", 45.0) or 45.0)
        slope_blocking_messages = (
            f"Generated WOK has {count} walkable face(s) steeper than {allowed:.1f} degrees "
            f"(max {max_slope:.1f} degrees).",
        )
    slope_blocking_tails = {_message_tail(message) for message in slope_blocking_messages}
    for index, message in enumerate(slope_blocking_messages):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_WOK_BAD_SLOPE",
                message,
                f"authored_wok_slope:blocker:{index}",
                "Flatten the terrain/ramp, paint steep faces non-walkable, or lower the grade before export/proof.",
            )
        )

    transition_surface_gate = dict(metadata.get("transition_surface_gate", {}) or {})
    transition_surface_blocking_messages = tuple(
        str(message)
        for message in tuple(transition_surface_gate.get("blocking_messages") or ())
        if str(message).strip()
    )
    transition_surface_warning_messages = tuple(
        str(message)
        for message in tuple(transition_surface_gate.get("warnings") or ())
        if str(message).strip()
    )
    transition_surface_blocking_tails = {_message_tail(message) for message in transition_surface_blocking_messages}
    transition_surface_warning_tails = {_message_tail(message) for message in transition_surface_warning_messages}
    transition_surface_fix = str(transition_surface_gate.get("fix_hint") or "").strip() or (
        "Paint linked doorway walkmesh faces as WOK DOOR surface 18 before export."
    )
    for index, message in enumerate(transition_surface_blocking_messages):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_TRANSITION_WOK_SURFACE_BLOCKER",
                message,
                f"authored_transition_surface:blocker:{index}",
                transition_surface_fix,
            )
        )
    for index, message in enumerate(transition_surface_warning_messages):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_TRANSITION_WOK_SURFACE_WARNING",
                message,
                f"authored_transition_surface:warning:{index}",
                transition_surface_fix,
            )
        )

    doorway_transition = dict(metadata.get("doorway_transition", {}) or {})
    doorway_transition_warnings = tuple(
        str(message)
        for message in tuple(doorway_transition.get("warnings") or ())
        if str(message).strip()
    )
    doorway_transition_warning_tails = {_message_tail(message) for message in doorway_transition_warnings}
    doorway_transition_fix = str(doorway_transition.get("fix_hint") or "").strip() or (
        "Add or complete a door, trigger, or waypoint transition marker for each authored doorway opening."
    )
    for index, message in enumerate(doorway_transition_warnings):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_DOORWAY_TRANSITION_INTENT_MISSING",
                message,
                f"authored_doorway_transition:warning:{index}",
                doorway_transition_fix,
            )
        )

    visibility = dict(metadata.get("visibility", {}) or {})
    visibility_blocking_messages = tuple(
        str(message) for message in tuple(visibility.get("blocking_messages") or ()) if str(message).strip()
    )
    visibility_warnings = tuple(str(message) for message in tuple(visibility.get("warnings") or ()) if str(message).strip())
    visibility_blocking_tails = {_message_tail(message) for message in visibility_blocking_messages}
    visibility_warning_tails = {_message_tail(message) for message in visibility_warnings}
    visibility_fix = str(visibility.get("fix_hint") or "").strip() or (
        "Open the VIS visibility controls and connect rooms that should render together."
    )
    for index, message in enumerate(visibility_blocking_messages):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_VISIBILITY_BLOCKER",
                message,
                f"authored_vis_visibility:blocker:{index}",
                visibility_fix,
            )
        )
    for index, message in enumerate(visibility_warnings):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_VISIBILITY_WARNING",
                message,
                f"authored_vis_visibility:warning:{index}",
                visibility_fix,
            )
        )

    lighting = dict(metadata.get("lighting", {}) or {})
    lighting_warnings = tuple(str(message) for message in tuple(lighting.get("warnings") or ()) if str(message).strip())
    lighting_warning_tails = {_message_tail(message) for message in lighting_warnings}
    lighting_fix = str(lighting.get("fix_hint") or "").strip() or (
        "Add authored room lights, bake or attach lightmap output, then verify lighting in game."
    )
    for index, message in enumerate(lighting_warnings):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_LIGHTING_WARNING",
                message,
                f"authored_lighting:warning:{index}",
                lighting_fix,
            )
        )

    export_proof_invalidation = dict(metadata.get("export_proof_invalidation", {}) or {})
    if bool(export_proof_invalidation.get("invalidates_previous_export")) or bool(
        export_proof_invalidation.get("invalidates_game_proof")
    ):
        latest_summary = str(export_proof_invalidation.get("latest_summary") or "").strip()
        stale_outputs = tuple(
            str(value).strip()
            for value in tuple(export_proof_invalidation.get("stale_outputs") or ())
            if str(value).strip()
        )
        output_label = ", ".join(stale_outputs) if stale_outputs else "generated module resources"
        if latest_summary:
            message = f"{latest_summary} Stale outputs: {output_label}."
        else:
            message = f"Authored Map Studio edits made packaged output or game proof stale. Stale outputs: {output_label}."
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_EXPORT_PROOF_STALE",
                message,
                "authored_module:export_proof_stale",
                str(export_proof_invalidation.get("next_action") or "").strip()
                or "Regenerate the authored module package, reinstall it, and record fresh in-game proof.",
            )
        )

    package_manifest_evidence = dict(metadata.get("package_manifest_evidence", {}) or {})
    missing_package_evidence = tuple(
        str(item).strip()
        for item in tuple(package_manifest_evidence.get("missing") or ())
        if str(item).strip()
    )
    if bool(getattr(readiness, "can_export_candidate", False)) and missing_package_evidence:
        labels = {
            "pack_manifest_path": "pack manifest path",
            "proof_manifest_path": "proof manifest path",
            "package_resource_inventory": "package resource inventory",
            "package_resource_inventory.readback_ok": "package readback proof",
        }
        evidence_label = ", ".join(labels.get(item, item) for item in missing_package_evidence)
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_PACKAGE_MANIFEST_EVIDENCE_MISSING",
                f"Runtime resources are generated, but package manifest evidence is incomplete: {evidence_label}.",
                "authored_module:package_manifest_evidence",
                "Stage or install the authored module from Map Studio so the .mod pack manifest, proof manifest, and resource readback inventory are current.",
            )
        )

    for item in tuple(getattr(readiness, "inputs", ()) or ()):
        if bool(getattr(item, "present", False)):
            continue
        name = str(getattr(item, "name", "") or "Map Studio input")
        value = str(getattr(item, "value_label", "") or "")
        fix = str(getattr(item, "fix_hint", "") or "Fill in this Map Studio input before preview/export.")
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_INPUT_MISSING",
                f"{name} is not ready. {value}".strip(),
                f"authored_input:{_slug(name)}",
                fix,
            )
        )

    for index, message in enumerate(tuple(getattr(readiness, "blocking_messages", ()) or ())):
        if _message_tail(str(message)) in project_texture_blocking_tails:
            continue
        if _message_tail(str(message)) in geometry_blocking_tails:
            continue
        if _message_tail(str(message)) in pathing_blocking_tails:
            continue
        if _message_tail(str(message)) in transition_surface_blocking_tails:
            continue
        if _message_tail(str(message)) in visibility_blocking_tails:
            continue
        if _message_tail(str(message)) in topology_blocking_tails:
            continue
        if _message_tail(str(message)) in slope_blocking_tails:
            continue
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_READINESS_BLOCKER",
                str(message),
                f"authored_blocker:{index}",
                "Fix this authored module blocker before preview, staged export, or install.",
            )
        )

    for resource in tuple(getattr(readiness, "missing_runtime_resources", ()) or ()):
        resref, restype = _resource_label(resource)
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_RUNTIME_RESOURCE_MISSING",
                f"Runtime resource {resref}.{restype} has not been generated or staged.",
                f"authored_runtime:{resref}.{restype}",
                "Stage/build the authored module so ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX, and WOK files are present.",
            )
        )

    for status in tuple(getattr(readiness, "toolchain", ()) or ()):
        if bool(getattr(status, "ready", False)):
            continue
        name = str(getattr(status, "name", "") or "Map Studio step")
        status_text = str(getattr(status, "status", "") or "Not ready")
        value = str(getattr(status, "value_label", "") or "")
        fix = str(getattr(status, "fix_hint", "") or "Complete this Map Studio step before export/install.")
        severity = "Error" if name in {"Geometry authoring", "Walkmesh", "Gameplay layout"} and not bool(getattr(readiness, "can_preview", False)) else "Warning"
        issues.append(
            KMapValidationIssue(
                severity,
                "MAP_STUDIO_TOOLCHAIN_NOT_READY",
                f"{name}: {status_text}. {value}".strip(),
                f"authored_toolchain:{_slug(name)}",
                fix,
            )
        )

    for ref in tuple(metadata.get("transition_references") or ()):
        if bool(ref.get("complete", False)):
            continue
        label = str(ref.get("tag") or ref.get("template_resref") or ref.get("kind") or "transition")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_TRANSITION_DESTINATION_MISSING",
                str(ref.get("message") or f"Transition {label} is missing a destination."),
                f"authored_transition:{_slug(label)}",
                "Set LinkedTo plus LinkedToModule/TransitionDestin in the selected door, trigger, or waypoint properties.",
            )
        )

    for ref in tuple(metadata.get("script_references") or ()):
        if bool(ref.get("packaged", False)):
            continue
        script = str(ref.get("script_resref") or "script")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_SCRIPT_EXTERNAL",
                str(ref.get("message") or f"Script hook {script}.ncs is external."),
                f"authored_script:{_slug(script)}",
                "Package the custom NCS script or confirm the base-game/Override script is installed for the test.",
            )
        )

    for ref in tuple(metadata.get("gameplay_template_references") or ()):
        if bool(ref.get("packaged", False)):
            continue
        template = str(ref.get("template_resref") or "template")
        restype = str(ref.get("restype") or "resource")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_TEMPLATE_EXTERNAL",
                str(ref.get("message") or f"Template {template}.{restype} is external."),
                f"authored_template:{_slug(template)}.{restype}",
                "Package custom templates or verify the template exists in the base game, Override, or another installed mod.",
            )
        )

    if bool(getattr(readiness, "ready_for_game_test", False)) and not bool(getattr(readiness, "game_tested", False)):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_GAME_PROOF_REQUIRED",
                "Module is exportable but not game-ready until a live KOTOR warp test is recorded.",
                "authored_module:proof",
                "Install the staged .mod, warp to the module in KOTOR, then record screenshot/video proof.",
            )
        )

    open_edge_warning_messages = tuple(
        str(message)
        for message in tuple(getattr(readiness, "warnings", ()) or ())
        if "open/boundary walkable edge" in str(message)
    )
    open_edge_warning_tails = {_message_tail(message) for message in open_edge_warning_messages}
    for index, message in enumerate(open_edge_warning_messages):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_WOK_OPEN_EDGE_WARNING",
                message,
                f"authored_wok_open_edge:warning:{index}",
                "Confirm each open WOK edge is an intentional room perimeter, doorway seam, or transition boundary before export.",
            )
        )

    for index, message in enumerate(tuple(getattr(readiness, "warnings", ()) or ())):
        if _message_tail(str(message)) in project_texture_warning_tails:
            continue
        if _message_tail(str(message)) in geometry_warning_tails:
            continue
        if _message_tail(str(message)) in pathing_warning_tails:
            continue
        if _message_tail(str(message)) in transition_surface_warning_tails:
            continue
        if _message_tail(str(message)) in visibility_warning_tails:
            continue
        if _message_tail(str(message)) in lighting_warning_tails:
            continue
        if _message_tail(str(message)) in open_edge_warning_tails:
            continue
        if _message_tail(str(message)) in doorway_transition_warning_tails:
            continue
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_READINESS_WARNING",
                str(message),
                f"authored_warning:{index}",
                "Review this Map Studio readiness warning before calling the module export-ready.",
            )
        )
    return _dedupe(issues)


def _resource_label(resource: Any) -> tuple[str, str]:
    if isinstance(resource, tuple) and len(resource) >= 2:
        return str(resource[0] or "").strip() or "module", str(resource[1] or "").strip().lower() or "resource"
    text = str(resource or "").strip()
    stem, dot, ext = text.rpartition(".")
    if dot:
        return stem or "module", ext.lower() or "resource"
    return text or "module", "resource"


def _slug(value: str) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "item"


def _message_tail(message: str) -> str:
    text = str(message or "").strip()
    if "could not compile:" in text:
        text = text.split("could not compile:", 1)[1].strip()
    if text.lower().startswith("room ") and ": " in text:
        text = text.split(": ", 1)[1].strip()
    return text


def _dedupe(issues: list[KMapValidationIssue]) -> list[KMapValidationIssue]:
    seen: set[tuple[str, str, str]] = set()
    result: list[KMapValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.message, issue.item_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


__all__ = ["authored_module_readiness_validation_issues"]
