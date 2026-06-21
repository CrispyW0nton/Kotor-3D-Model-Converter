"""Modder-facing readiness checks for authored Map Studio projects.

This module does not compile or package a module.  It answers the product
question a Map Studio panel needs before it enables preview, export, or a game
smoke test: what exists, what is still missing, and how honest we can be about
the current capability stage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .authored_module_metadata import authored_area_script_hooks, authored_module_script_hooks
from .authored_module_objects import normalise_resource_resref, validate_authored_gameplay_placement_against_walkmesh
from .authored_module_placements import authored_gameplay_placement_rows
from .authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec, normalise_resref, validate_authored_module_project
from .authored_module_walkmesh import combine_authored_module_walkmesh
from .authored_room_floorplan import FloorPlanRoomPrimitive, polygon_signed_area, validate_floor_plan_room_primitive
from .map_studio_export_objects import map_studio_export_object_boundaries
from .authored_walkmesh_audit import audit_authored_wok
from .authored_walkmesh_surfaces import walkmesh_surface_name


RuntimeResourceKey = tuple[str, str]


_COMPONENT_EDIT_RESOURCE_IMPACTS: dict[str, tuple[str, str]] = {
    "MDL": (
        "Room model geometry changed.",
        "Regenerate the room MDL before staging the module.",
    ),
    "MDX": (
        "Room vertex buffers changed.",
        "Regenerate the paired MDX with the room MDL.",
    ),
    "WOK": (
        "Walkmesh may no longer match the edited floor or openings.",
        "Review walkable surfaces, edges, and blockers before export.",
    ),
    "LYT": (
        "Room layout membership may be stale.",
        "Rebuild the module layout after room geometry changes.",
    ),
    "VIS": (
        "Visibility links may no longer match the room shape.",
        "Review room visibility/portal intent and rebuild VIS.",
    ),
    "PTH": (
        "Path graph may cross invalid WOK space.",
        "Rebuild PTH after walkmesh and entry/transition checks pass.",
    ),
    ".mod": (
        "Packaged module is stale.",
        "Re-stage the .mod and record fresh in-game proof.",
    ),
}


@dataclass(frozen=True)
class AuthoredModuleInputStatus:
    """One user-facing Map Studio input and its readiness state."""

    name: str
    present: bool
    value_label: str = ""
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredRoomReadiness:
    """Preview/export readiness for one authored room."""

    room_resref: str
    primitive_type: str
    can_preview_geometry: bool
    mesh_name: str = ""
    texture: str = ""
    floor_surface_id: int = -1
    floor_surface_name: str = ""
    helper_mesh_count: int = 0
    walkable_face_count: int = 0
    walkable_component_count: int = 0
    invalid_wok_face_count: int = 0
    degenerate_wok_face_count: int = 0
    non_manifold_wok_edge_count: int = 0
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredModuleToolchainStatus:
    """One stage in the from-scratch Map Studio authoring pipeline."""

    name: str
    ready: bool
    status: str
    value_label: str = ""
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredGameplayTemplateReference:
    """One template resource referenced by authored GIT gameplay placement data."""

    kind: str
    template_resref: str
    restype: str
    tag: str = ""
    status: str = "external_or_base_game"
    packaged: bool = False
    required: bool = True
    message: str = ""


@dataclass(frozen=True)
class AuthoredModuleTransitionReference:
    """One authored transition/area-link candidate from door, trigger, or waypoint data."""

    kind: str
    tag: str
    template_resref: str = ""
    linked_to: str = ""
    linked_to_module: str = ""
    status: str = "unlinked"
    complete: bool = False
    message: str = ""


@dataclass(frozen=True)
class AuthoredModuleScriptReference:
    """One authored module or area script hook referenced by an ARE/IFO field."""

    scope: str
    field_name: str
    script_resref: str
    restype: str = "ncs"
    status: str = "external_or_override"
    packaged: bool = False
    message: str = ""


@dataclass(frozen=True)
class AuthoredModulePathingReadiness:
    """Modder-facing summary of the generated module PTH/path graph."""

    ready: bool
    status: str
    pth_resource: str = ""
    point_count: int = 0
    connection_count: int = 0
    walkmesh_component_count: int = 0
    anchor_labels: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    blocking_targets: tuple[dict[str, Any], ...] = ()
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredModuleVisibilityReadiness:
    """Modder-facing summary of authored VIS room visibility intent."""

    ready: bool
    status: str
    room_count: int = 0
    vis_entry_count: int = 0
    link_count: int = 0
    cross_room_link_count: int = 0
    isolated_rooms: tuple[str, ...] = ()
    missing_targets: tuple[dict[str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredComponentEditReadiness:
    """Latest component-edit risk summary for Map Studio readiness UI."""

    ready: bool
    status: str
    latest_room_resref: str = ""
    latest_operation: str = ""
    latest_summary: str = ""
    edit_count: int = 0
    risky_edit_count: int = 0
    topology_changed: bool = False
    walkmesh_review_required: bool = False
    export_candidate_stale: bool = False
    game_proof_stale: bool = False
    stale_outputs: tuple[str, ...] = ()
    resource_impacts: tuple[dict[str, str], ...] = ()
    next_action: str = ""
    validation_messages: tuple[str, ...] = ()
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredFloorPlanGeometryReadiness:
    """Headless safety summary for authored floor-plan room footprints."""

    ready: bool
    status: str
    floor_plan_room_count: int = 0
    checked_room_count: int = 0
    opening_count: int = 0
    blocking_issue_count: int = 0
    warning_count: int = 0
    blocking_messages: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredDoorwayTransitionReadiness:
    """Doorway/transition intent summary for authored wall openings."""

    ready: bool
    status: str
    opening_count: int = 0
    transition_marker_count: int = 0
    transition_reference_count: int = 0
    linked_transition_count: int = 0
    warnings: tuple[str, ...] = ()
    fix_hint: str = ""


@dataclass(frozen=True)
class AuthoredModuleReadiness:
    """Capability-honest summary for a from-scratch Map Studio module."""

    module_root: str
    game: str
    capability_stage: str
    inputs: tuple[AuthoredModuleInputStatus, ...] = ()
    rooms: tuple[AuthoredRoomReadiness, ...] = ()
    toolchain: tuple[AuthoredModuleToolchainStatus, ...] = ()
    geometry_validation: AuthoredFloorPlanGeometryReadiness = field(
        default_factory=lambda: AuthoredFloorPlanGeometryReadiness(True, "No floor-plan rooms")
    )
    doorway_transition: AuthoredDoorwayTransitionReadiness = field(
        default_factory=lambda: AuthoredDoorwayTransitionReadiness(True, "No wall openings")
    )
    visibility: AuthoredModuleVisibilityReadiness = field(
        default_factory=lambda: AuthoredModuleVisibilityReadiness(True, "No authored rooms")
    )
    component_edit: AuthoredComponentEditReadiness = field(
        default_factory=lambda: AuthoredComponentEditReadiness(True, "No component edits")
    )
    can_preview: bool = False
    can_export_candidate: bool = False
    ready_for_game_test: bool = False
    game_tested: bool = False
    preview_status: str = "Not ready"
    export_status: str = "Not ready"
    next_action: str = ""
    expected_runtime_resources: tuple[RuntimeResourceKey, ...] = ()
    present_runtime_resources: tuple[RuntimeResourceKey, ...] = ()
    missing_runtime_resources: tuple[RuntimeResourceKey, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def _resource_key(resource: Any) -> RuntimeResourceKey | None:
    if isinstance(resource, tuple) and len(resource) >= 2:
        return normalise_resref(resource[0]), str(resource[1] or "").strip().lower().lstrip(".")
    key = getattr(resource, "key", None)
    if isinstance(key, tuple) and len(key) >= 2:
        return normalise_resref(key[0]), str(key[1] or "").strip().lower().lstrip(".")
    resref = getattr(resource, "resref", "")
    restype = getattr(resource, "restype", getattr(resource, "type", ""))
    if resref or restype:
        return normalise_resref(resref), str(restype or "").strip().lower().lstrip(".")
    if isinstance(resource, str):
        stem, dot, ext = resource.rpartition(".")
        if dot:
            return normalise_resref(stem), ext.strip().lower().lstrip(".")
    return None


def _present_keys(resources: Iterable[Any]) -> tuple[RuntimeResourceKey, ...]:
    keys = {_key for resource in list(resources or ()) if (_key := _resource_key(resource)) and _key != ("", "")}
    return tuple(sorted(keys))


def _expected_keys(module_root: str, rooms: Iterable[AuthoredRoomReadiness]) -> tuple[RuntimeResourceKey, ...]:
    root = normalise_resref(module_root)
    keys: set[RuntimeResourceKey] = {
        (root, "are"),
        (root, "git"),
        ("module", "ifo"),
        (root, "pth"),
        (root, "lyt"),
        (root, "vis"),
    }
    for room in rooms:
        room_resref = normalise_resref(room.room_resref)
        if room_resref:
            keys.add((room_resref, "wok"))
            keys.add((room_resref, "mdl"))
            keys.add((room_resref, "mdx"))
    return tuple(sorted(keys))


def _gameplay_counts(project: AuthoredModuleProject) -> dict[str, int]:
    placements = project.placements
    return {
        "creatures": len(tuple(placements.creatures or ())),
        "doors": len(tuple(placements.doors or ())),
        "triggers": len(tuple(placements.triggers or ())),
        "encounters": len(tuple(placements.encounters or ())),
        "sounds": len(tuple(placements.sounds or ())),
        "cameras": len(tuple(placements.cameras or ())),
        "stores": len(tuple(placements.stores or ())),
        "placeables": len(tuple(placements.placeables or ())),
        "waypoints": len(tuple(placements.waypoints or ())),
    }


_RESOURCE_PLACEMENT_LABELS: tuple[tuple[str, str, str], ...] = (
    ("creatures", "creatures", "utc"),
    ("placeables", "placeables", "utp"),
    ("doors", "doors", "utd"),
    ("triggers", "triggers", "utt"),
    ("encounters", "encounters", "ute"),
    ("cameras", "cameras", "git"),
    ("sounds", "sounds", "uts"),
    ("stores", "merchants/stores", "utm"),
    ("waypoints", "waypoints", "utw"),
)


def _resource_placement_palette(gameplay_counts: dict[str, int]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "kind": key,
            "label": label,
            "restype": restype,
            "count": int(gameplay_counts.get(key, 0) or 0),
        }
        for key, label, restype in _RESOURCE_PLACEMENT_LABELS
    )


def _resource_placement_summary(gameplay_counts: dict[str, int]) -> str:
    parts = [
        f"{int(gameplay_counts.get(key, 0) or 0)} {label}"
        for key, label, _restype in _RESOURCE_PLACEMENT_LABELS
        if int(gameplay_counts.get(key, 0) or 0) > 0
    ]
    return ", ".join(parts) if parts else "No extra KOTOR resources placed yet"


def _resource_placement_palette_label() -> str:
    return ", ".join(label for _key, label, _restype in _RESOURCE_PLACEMENT_LABELS)


def _template_reference_entry(
    *,
    kind: str,
    restype: str,
    template_resref: Any,
    tag: Any,
    present: set[RuntimeResourceKey],
) -> AuthoredGameplayTemplateReference | None:
    resref = normalise_resource_resref(template_resref)
    if not resref:
        return None
    key = (resref, restype)
    packaged = key in present
    status = "packaged" if packaged else "external_or_base_game"
    message = (
        f"{resref}.{restype} will be written into the module package."
        if packaged
        else f"{resref}.{restype} must resolve from the base game, Override, or another installed mod."
    )
    return AuthoredGameplayTemplateReference(
        kind=kind,
        template_resref=resref,
        restype=restype,
        tag=str(tag or ""),
        status=status,
        packaged=packaged,
        message=message,
    )


def _gameplay_template_references(
    project: AuthoredModuleProject,
    *,
    present: set[RuntimeResourceKey],
) -> tuple[AuthoredGameplayTemplateReference, ...]:
    placements = project.placements
    refs: list[AuthoredGameplayTemplateReference] = []
    for kind, restype, items in (
        ("creature", "utc", tuple(placements.creatures or ())),
        ("door", "utd", tuple(placements.doors or ())),
        ("trigger", "utt", tuple(placements.triggers or ())),
        ("encounter", "ute", tuple(placements.encounters or ())),
        ("sound", "uts", tuple(placements.sounds or ())),
        ("store", "utm", tuple(placements.stores or ())),
        ("placeable", "utp", tuple(placements.placeables or ())),
        ("waypoint", "utw", tuple(placements.waypoints or ())),
    ):
        for item in items:
            ref = _template_reference_entry(
                kind=kind,
                restype=restype,
                template_resref=getattr(item, "template_resref", ""),
                tag=getattr(item, "tag", ""),
                present=present,
            )
            if ref is not None:
                refs.append(ref)
    return tuple(sorted(refs, key=lambda item: (item.kind, item.template_resref, item.restype, item.tag)))


def _transition_reference_entry(
    *,
    kind: str,
    template_resref: Any,
    tag: Any,
    linked_to: Any,
    linked_to_module: Any = "",
) -> AuthoredModuleTransitionReference | None:
    destination = str(linked_to or "").strip()
    destination_module = normalise_resref(linked_to_module)
    if not destination and not destination_module:
        return None
    label = str(tag or template_resref or kind).strip()
    template = normalise_resource_resref(template_resref)
    if destination and destination_module:
        status = "module_transition"
        complete = True
        message = f"{kind.title()} {label} links to {destination} in module {destination_module}."
    elif destination:
        status = "local_transition"
        complete = True
        message = f"{kind.title()} {label} links to local destination {destination}."
    else:
        status = "missing_destination"
        complete = False
        message = f"{kind.title()} {label} names module {destination_module} but no destination tag/waypoint."
    return AuthoredModuleTransitionReference(
        kind=kind,
        tag=label,
        template_resref=template,
        linked_to=destination,
        linked_to_module=destination_module,
        status=status,
        complete=complete,
        message=message,
    )


def _transition_references(project: AuthoredModuleProject) -> tuple[AuthoredModuleTransitionReference, ...]:
    placements = project.placements
    refs: list[AuthoredModuleTransitionReference] = []
    for kind, items in (
        ("door", tuple(placements.doors or ())),
        ("trigger", tuple(placements.triggers or ())),
        ("waypoint", tuple(placements.waypoints or ())),
    ):
        for item in items:
            ref = _transition_reference_entry(
                kind=kind,
                template_resref=getattr(item, "template_resref", ""),
                tag=getattr(item, "tag", ""),
                linked_to=getattr(item, "linked_to", ""),
                linked_to_module=getattr(item, "linked_to_module", ""),
            )
            if ref is not None:
                refs.append(ref)
    return tuple(sorted(refs, key=lambda item: (item.kind, item.tag, item.linked_to_module, item.linked_to)))


def _script_reference_entry(
    *,
    scope: str,
    field_name: str,
    script_resref: Any,
    present: set[RuntimeResourceKey],
) -> AuthoredModuleScriptReference | None:
    script = normalise_resource_resref(script_resref)
    if not script:
        return None
    key = (script, "ncs")
    packaged = key in present
    status = "packaged" if packaged else "external_or_override"
    message = (
        f"{scope} script hook {field_name} uses packaged script {script}.ncs."
        if packaged
        else f"{scope} script hook {field_name} expects {script}.ncs from the base game, Override, or another installed mod."
    )
    return AuthoredModuleScriptReference(
        scope=scope,
        field_name=field_name,
        script_resref=script,
        status=status,
        packaged=packaged,
        message=message,
    )


def _script_references(
    project: AuthoredModuleProject,
    *,
    present: set[RuntimeResourceKey],
) -> tuple[AuthoredModuleScriptReference, ...]:
    refs: list[AuthoredModuleScriptReference] = []
    for field_name, script_resref in authored_module_script_hooks(project.metadata).items():
        ref = _script_reference_entry(scope="module", field_name=field_name, script_resref=script_resref, present=present)
        if ref is not None:
            refs.append(ref)
    for field_name, script_resref in authored_area_script_hooks(project.metadata).items():
        ref = _script_reference_entry(scope="area", field_name=field_name, script_resref=script_resref, present=present)
        if ref is not None:
            refs.append(ref)
    return tuple(sorted(refs, key=lambda item: (item.scope, item.field_name, item.script_resref)))


def _path_anchors_from_walkability(project: AuthoredModuleProject, walkability: Any) -> tuple[AuthoredPathAnchor, ...]:
    ok_labels = {str(getattr(check, "label", "")): bool(getattr(check, "ok", False)) for check in list(getattr(walkability, "checks", ()) or ())}
    placements = project.placements
    anchors: list[AuthoredPathAnchor] = []
    if ok_labels.get("entry_point", False):
        anchors.append(AuthoredPathAnchor("entry_point", placements.entry_point.position, metadata={"kind": "entry_point"}))

    def append_spatial_anchor(kind: str, index: int, item: Any) -> None:
        if not hasattr(item, "position"):
            return
        template = str(getattr(item, "template_resref", "") or "")
        tag = str(getattr(item, "tag", "") or "")
        label = f"{kind}:{tag or template or f'{kind}_{index + 1}'}"
        if ok_labels.get(label, False):
            anchors.append(
                AuthoredPathAnchor(
                    label,
                    tuple(getattr(item, "position")),
                    metadata={
                        "kind": kind,
                        "index": index,
                        "template_resref": template,
                        "tag": tag,
                    },
                )
            )

    for index, creature in enumerate(tuple(placements.creatures or ())):
        append_spatial_anchor("creature", index, creature)
    for index, door in enumerate(tuple(placements.doors or ())):
        append_spatial_anchor("door", index, door)
    for index, trigger in enumerate(tuple(placements.triggers or ())):
        append_spatial_anchor("trigger", index, trigger)
    for index, encounter in enumerate(tuple(placements.encounters or ())):
        append_spatial_anchor("encounter", index, encounter)
    for index, placeable in enumerate(tuple(placements.placeables or ())):
        append_spatial_anchor("placeable", index, placeable)
    for index, waypoint in enumerate(tuple(placements.waypoints or ())):
        append_spatial_anchor("waypoint", index, waypoint)
    return tuple(anchors)


def _pathing_blocking_targets(project: AuthoredModuleProject, walkability: Any) -> tuple[dict[str, Any], ...]:
    """Map failed pathing checks to selectable Map Studio anchors."""

    rows = tuple(authored_gameplay_placement_rows(project))
    by_kind_and_label: dict[tuple[str, str], Any] = {}
    for row in rows:
        kind = str(getattr(row, "kind", "") or "").strip().lower()
        labels = {
            str(getattr(row, "tag", "") or "").strip(),
            str(getattr(row, "template_resref", "") or "").strip(),
            f"{kind}_{int(getattr(row, 'index', 0)) + 1}",
        }
        for label in labels:
            if label:
                by_kind_and_label[(kind, label)] = row

    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for check in tuple(getattr(walkability, "checks", ()) or ()):
        if bool(getattr(check, "ok", False)):
            continue
        label = str(getattr(check, "label", "") or "").strip()
        if not label:
            continue
        if label == "entry_point":
            target = {
                "anchor_label": label,
                "target_id": "entry_point",
                "workspace": "entry_point",
                "fix_action": "Focus the module entry point controls and move the player start onto generated walkable WOK.",
            }
        else:
            parts = label.split(":")
            kind = parts[0].strip().lower()
            placement_label = parts[1].strip() if len(parts) > 1 else ""
            row = by_kind_and_label.get((kind, placement_label))
            target_id = str(getattr(row, "placement_id", "") or "") if row is not None else ""
            target = {
                "anchor_label": label,
                "target_id": target_id,
                "workspace": "placement",
                "placement_kind": kind,
                "fix_action": f"Select the {kind or 'gameplay'} placement and move it onto generated walkable WOK.",
            }
        key = (str(target.get("workspace") or ""), str(target.get("target_id") or target.get("anchor_label") or ""))
        if key in seen:
            continue
        seen.add(key)
        target["message"] = str(getattr(check, "message", "") or "")
        targets.append(target)
    return tuple(targets)


def _pathing_readiness(project: AuthoredModuleProject) -> AuthoredModulePathingReadiness:
    root = normalise_resref(project.module_root)
    if not root:
        return AuthoredModulePathingReadiness(
            ready=False,
            status="Needs module resref",
            fix_hint="Choose a module resref before Map Studio can name the generated PTH resource.",
        )
    if not project.rooms:
        return AuthoredModulePathingReadiness(
            ready=False,
            status="Needs room WOK",
            pth_resource=f"{root}.pth",
            fix_hint="Create at least one room so Map Studio can compile walkmesh-backed pathing.",
        )

    module_walkmesh = combine_authored_module_walkmesh(project)
    blocking: list[str] = list(module_walkmesh.blocking_issues)
    if not module_walkmesh.wok.faces:
        return AuthoredModulePathingReadiness(
            ready=False,
            status="Needs room WOK",
            pth_resource=f"{root}.pth",
            blocking_messages=tuple(blocking),
            fix_hint="Fix room geometry before Map Studio can compile PTH pathing.",
        )

    walkability = validate_authored_gameplay_placement_against_walkmesh(project.placements, module_walkmesh.wok)
    blocking.extend(str(issue) for issue in tuple(getattr(walkability, "blocking_issues", ()) or ()))
    if blocking:
        blocking_targets = _pathing_blocking_targets(project, walkability)
        return AuthoredModulePathingReadiness(
            ready=False,
            status="Blocked",
            pth_resource=f"{root}.pth",
            blocking_messages=tuple(blocking),
            blocking_targets=blocking_targets,
            fix_hint="Move entry points and gameplay anchors onto walkable WOK faces before export.",
        )

    try:
        compiled = compile_authored_pathing_for_module(module_walkmesh.wok, anchors=_path_anchors_from_walkability(project, walkability))
    except Exception as exc:
        return AuthoredModulePathingReadiness(
            ready=False,
            status="Blocked",
            pth_resource=f"{root}.pth",
            blocking_messages=(f"Authored PTH pathing could not compile: {exc}",),
            fix_hint="Fix path points, walkmesh islands, or gameplay anchors before export.",
        )
    metadata = dict(getattr(compiled, "metadata", {}) or {})
    return AuthoredModulePathingReadiness(
        ready=True,
        status="Ready",
        pth_resource=f"{root}.pth",
        point_count=int(metadata.get("point_count", 0) or 0),
        connection_count=int(metadata.get("connection_count", 0) or 0),
        walkmesh_component_count=int(metadata.get("walkmesh_component_count", 0) or 0),
        anchor_labels=tuple(str(label) for label in list(metadata.get("anchor_labels", []) or ())),
        warnings=tuple(module_walkmesh.warnings) + tuple(getattr(getattr(compiled, "validation", None), "warnings", ()) or ()),
        fix_hint="Validate in game by walking between authored anchors after export.",
    )


def _component_edit_readiness(project: AuthoredModuleProject) -> AuthoredComponentEditReadiness:
    """Summarize latest floor-plan/component edit risk without touching export files."""

    audits: list[tuple[str, dict[str, Any]]] = []
    for room in tuple(project.rooms or ()):
        room_resref = normalise_resref(room.room_resref)
        audit = dict(room.metadata.get("last_component_edit_audit") or {})
        primitive = getattr(room, "primitive", None)
        if not audit and primitive is not None:
            audit = dict(getattr(primitive, "metadata", {}).get("last_component_edit_audit") or {})
        if audit:
            audits.append((room_resref, audit))
    if not audits:
        return AuthoredComponentEditReadiness(
            ready=True,
            status="No component edits",
            fix_hint="Use vertex, edge, face, or walkmesh tools when room geometry needs manual cleanup.",
        )
    latest_room, latest = audits[-1]
    risky = [
        audit
        for _room, audit in audits
        if bool(audit.get("walkmesh_review_required"))
        or bool(audit.get("export_candidate_stale"))
        or bool(audit.get("game_proof_stale"))
        or bool(audit.get("topology_changed"))
    ]
    latest_messages = tuple(str(message) for message in list(latest.get("validation_messages") or ()) if str(message).strip())
    walkmesh_review = any(bool(audit.get("walkmesh_review_required")) for _room, audit in audits)
    topology_changed = any(bool(audit.get("topology_changed")) for _room, audit in audits)
    export_stale = any(bool(audit.get("export_candidate_stale")) for _room, audit in audits)
    proof_stale = any(bool(audit.get("game_proof_stale")) for _room, audit in audits)
    stale_outputs = tuple(
        dict.fromkeys(
            str(output)
            for _room, audit in audits
            for output in tuple(audit.get("stale_outputs") or ())
            if str(output).strip()
        )
    )
    resource_impacts = _component_edit_resource_impacts(stale_outputs)
    next_action = str(latest.get("next_action") or "").strip()
    ready = not risky
    fix_hint = (
        "Inspect WOK surface intent, regenerate MDL/MDX/WOK/PTH resources, then record fresh game proof."
        if not ready
        else "No risky component edits are waiting for review."
    )
    return AuthoredComponentEditReadiness(
        ready=ready,
        status="Ready" if ready else "Needs WOK/export review",
        latest_room_resref=latest_room,
        latest_operation=str(latest.get("operation") or ""),
        latest_summary=str(latest.get("summary") or ""),
        edit_count=len(audits),
        risky_edit_count=len(risky),
        topology_changed=topology_changed,
        walkmesh_review_required=walkmesh_review,
        export_candidate_stale=export_stale,
        game_proof_stale=proof_stale,
        stale_outputs=stale_outputs,
        resource_impacts=resource_impacts,
        next_action=next_action or fix_hint,
        validation_messages=latest_messages,
        fix_hint=fix_hint,
    )


def _component_edit_resource_impacts(stale_outputs: Iterable[str]) -> tuple[dict[str, str], ...]:
    """Map stale KOTOR outputs to modder-facing export impact rows."""

    impacts: list[dict[str, str]] = []
    for output in stale_outputs:
        resource = str(output or "").strip()
        if not resource:
            continue
        why, fix = _COMPONENT_EDIT_RESOURCE_IMPACTS.get(
            resource,
            (
                "Generated runtime resource may be stale.",
                "Regenerate this resource before packaging the module.",
            ),
        )
        impacts.append({"resource": resource, "why_stale": why, "fix": fix})
    return tuple(impacts)


def _floor_plan_points(points: Any) -> tuple[tuple[float, float], ...]:
    return tuple((float(point[0]), float(point[1])) for point in tuple(points or ()))


def _floor_plan_edge_length(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return (dx * dx + dy * dy) ** 0.5


def _floor_plan_collinear_point_count(points: tuple[tuple[float, float], ...]) -> int:
    if len(points) < 3:
        return 0
    count = 0
    for index, point in enumerate(points):
        prev_point = points[index - 1]
        next_point = points[(index + 1) % len(points)]
        if _floor_plan_edge_length(prev_point, point) <= 1.0e-7:
            continue
        if _floor_plan_edge_length(point, next_point) <= 1.0e-7:
            continue
        abx = point[0] - prev_point[0]
        aby = point[1] - prev_point[1]
        bcx = next_point[0] - point[0]
        bcy = next_point[1] - point[1]
        if abs((abx * bcy) - (aby * bcx)) <= 1.0e-7:
            count += 1
    return count


def _floor_plan_geometry_readiness(project: AuthoredModuleProject) -> AuthoredFloorPlanGeometryReadiness:
    """Validate editable floor-plan intent before export/build systems run."""

    floor_plan_rooms = tuple(
        room for room in tuple(project.rooms or ()) if isinstance(getattr(room, "primitive", None), FloorPlanRoomPrimitive)
    )
    if not floor_plan_rooms:
        return AuthoredFloorPlanGeometryReadiness(
            ready=True,
            status="No floor-plan rooms",
            fix_hint="Draw or add a floor-plan room when this module needs editable room geometry.",
        )

    blocking: list[str] = []
    warnings: list[str] = []
    checked = 0
    opening_count = 0
    for room in floor_plan_rooms:
        primitive = room.primitive
        opening_count += len(tuple(getattr(primitive, "openings", ()) or ()))
        room_resref = normalise_resref(getattr(room, "room_resref", "") or getattr(primitive, "room_resref", ""))
        label = room_resref or "(unnamed)"
        try:
            points = _floor_plan_points(primitive.points)
        except Exception as exc:
            blocking.append(f"Room {label} floor-plan points are not numeric: {exc}")
            continue
        checked += 1
        if any(not (math.isfinite(point[0]) and math.isfinite(point[1])) for point in points):
            blocking.append(f"Room {label} floor-plan points must be finite numbers.")
            continue

        validation = validate_floor_plan_room_primitive(primitive)
        blocking.extend(f"Room {label}: {message}" for message in validation.blocking_issues)
        warnings.extend(f"Room {label}: {message}" for message in validation.warnings)

        if len(points) >= 3:
            signed_area = polygon_signed_area(points)
            if signed_area < -1.0e-7:
                warnings.append(f"Room {label} floor-plan winding is clockwise. Use Cleanup Face Normals before export.")
            collinear_count = _floor_plan_collinear_point_count(points)
            if collinear_count:
                warnings.append(
                    f"Room {label} floor-plan has {collinear_count} collinear point(s). Use Cleanup Footprint to simplify it."
                )
            tiny_edge_count = sum(
                1
                for index, point in enumerate(points)
                if _floor_plan_edge_length(point, points[(index + 1) % len(points)]) < 0.05
            )
            if tiny_edge_count:
                warnings.append(
                    f"Room {label} floor-plan has {tiny_edge_count} very short edge(s). Weld or cleanup vertices before packaging."
                )

    ready = not blocking
    if not ready:
        status = f"Blocked: {len(blocking)} issue(s)"
        fix_hint = "Use Cleanup Footprint, Weld Vertices, or split invalid rooms before build/export."
    elif warnings:
        status = f"Warnings: {len(warnings)} issue(s)"
        fix_hint = "Review footprint warnings, then run Preview/Validate before packaging."
    else:
        status = "Ready"
        fix_hint = "Floor-plan room footprints are ready for room MDL/MDX/WOK generation."
    return AuthoredFloorPlanGeometryReadiness(
        ready=ready,
        status=status,
        floor_plan_room_count=len(floor_plan_rooms),
        checked_room_count=checked,
        opening_count=opening_count,
        blocking_issue_count=len(blocking),
        warning_count=len(warnings),
        blocking_messages=tuple(blocking),
        warnings=tuple(warnings),
        fix_hint=fix_hint,
    )


def _doorway_transition_readiness(
    project: AuthoredModuleProject,
    *,
    geometry_validation: AuthoredFloorPlanGeometryReadiness,
    transition_references: tuple[AuthoredModuleTransitionReference, ...],
) -> AuthoredDoorwayTransitionReadiness:
    """Summarize whether authored openings have KOTOR door/transition intent."""

    opening_count = int(geometry_validation.opening_count)
    placements = project.placements
    transition_marker_count = (
        len(tuple(getattr(placements, "doors", ()) or ()))
        + len(tuple(getattr(placements, "triggers", ()) or ()))
        + len(tuple(getattr(placements, "waypoints", ()) or ()))
    )
    transition_reference_count = len(tuple(transition_references or ()))
    linked_transition_count = sum(1 for ref in transition_references if bool(getattr(ref, "complete", False)))
    warnings: list[str] = []
    if opening_count <= 0:
        return AuthoredDoorwayTransitionReadiness(
            ready=True,
            status="No wall openings",
            opening_count=0,
            transition_marker_count=transition_marker_count,
            transition_reference_count=transition_reference_count,
            linked_transition_count=linked_transition_count,
            fix_hint="Add a floor-plan wall opening when this room needs a doorway, portal, or transition blockout.",
        )
    if transition_marker_count <= 0:
        warnings.append(
            f"{opening_count} floor-plan opening(s) exist without authored door, trigger, or waypoint markers. "
            "Add a KOTOR door/transition marker and review DOOR WOK surface intent before game proof."
        )
        return AuthoredDoorwayTransitionReadiness(
            ready=False,
            status="Needs door/trigger/waypoint marker",
            opening_count=opening_count,
            transition_marker_count=transition_marker_count,
            transition_reference_count=transition_reference_count,
            linked_transition_count=linked_transition_count,
            warnings=tuple(warnings),
            fix_hint="Use Placement > Door, Trigger, or Waypoint near the opening, then set transition destinations if it leaves the area.",
        )
    if transition_reference_count <= 0:
        warnings.append(
            f"{opening_count} floor-plan opening(s) and {transition_marker_count} door/trigger/waypoint marker(s) exist, "
            "but no transition destination is configured yet."
        )
        return AuthoredDoorwayTransitionReadiness(
            ready=False,
            status="Needs transition review",
            opening_count=opening_count,
            transition_marker_count=transition_marker_count,
            transition_reference_count=transition_reference_count,
            linked_transition_count=linked_transition_count,
            warnings=tuple(warnings),
            fix_hint="If the opening is an area exit, set the linked tag/waypoint and module resref on the door, trigger, or waypoint.",
        )
    if linked_transition_count < transition_reference_count:
        warnings.append(
            f"{transition_reference_count - linked_transition_count} authored transition(s) near doorway work still need destination tags/waypoints."
        )
        return AuthoredDoorwayTransitionReadiness(
            ready=False,
            status="Needs linked transition destination",
            opening_count=opening_count,
            transition_marker_count=transition_marker_count,
            transition_reference_count=transition_reference_count,
            linked_transition_count=linked_transition_count,
            warnings=tuple(warnings),
            fix_hint="Complete linked_to and linked_to_module for each authored transition before game proof.",
        )
    return AuthoredDoorwayTransitionReadiness(
        ready=True,
        status="Ready",
        opening_count=opening_count,
        transition_marker_count=transition_marker_count,
        transition_reference_count=transition_reference_count,
        linked_transition_count=linked_transition_count,
        fix_hint="Doorway openings have authored transition markers. Verify DOOR WOK surfaces and door alignment in game.",
    )


def _lighting_count(project: AuthoredModuleProject) -> int:
    return len(tuple(getattr(project, "lights", ()) or ()))


def _lighting_room_coverage(project: AuthoredModuleProject, rooms: tuple[AuthoredRoomReadiness, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    room_resrefs = tuple(room.room_resref for room in rooms if room.room_resref)
    lit_rooms = {
        normalise_resref(getattr(light, "room_resref", ""))
        for light in tuple(getattr(project, "lights", ()) or ())
        if normalise_resref(getattr(light, "room_resref", ""))
    }
    rooms_with_lights = tuple(room for room in room_resrefs if room in lit_rooms)
    rooms_without_lights = tuple(room for room in room_resrefs if room not in lit_rooms)
    return rooms_with_lights, rooms_without_lights


def _visibility_readiness(project: AuthoredModuleProject) -> AuthoredModuleVisibilityReadiness:
    """Audit authored VIS intent against the final room set."""

    room_names = tuple(
        normalise_resref(getattr(room, "room_resref", ""))
        for room in tuple(getattr(project, "rooms", ()) or ())
        if normalise_resref(getattr(room, "room_resref", ""))
    )
    room_set = set(room_names)
    if not room_names:
        return AuthoredModuleVisibilityReadiness(
            ready=False,
            status="Needs authored rooms",
            fix_hint="Create at least one room before Map Studio can compile LYT/VIS data.",
        )

    missing_targets: list[dict[str, str]] = []
    warnings: list[str] = []
    explicit_entry_count = 0
    link_count = 0
    cross_room_link_count = 0
    isolated_rooms: list[str] = []
    for room in tuple(project.rooms or ()):
        room_name = normalise_resref(room.room_resref)
        if not room_name:
            continue
        explicit_targets = tuple(normalise_resref(target) for target in tuple(room.visible_rooms or ()) if normalise_resref(target))
        if explicit_targets:
            explicit_entry_count += 1
            targets = explicit_targets
            if room_name not in targets:
                warnings.append(f"Room {room_name} VIS does not include itself; add {room_name} to its visible rooms.")
        else:
            targets = (room_name,)

        for target in targets:
            if target not in room_set:
                missing_targets.append({"room": room_name, "target": target})
                continue
            link_count += 1
            if target != room_name:
                cross_room_link_count += 1
        if len(room_names) > 1 and not any(target in room_set and target != room_name for target in targets):
            isolated_rooms.append(room_name)

    blocking = tuple(
        f"Room {item['room']} references missing visible room {item['target']}."
        for item in missing_targets
    )
    if isolated_rooms:
        warnings.append(
            f"{len(isolated_rooms)} room(s) have no cross-room VIS links: {', '.join(isolated_rooms)}. "
            "Add visibility links between rooms that should render together."
        )
    ready = not blocking and not isolated_rooms and not warnings
    if blocking:
        status = f"Blocked: {len(blocking)} broken VIS target(s)"
        fix_hint = "Remove missing VIS targets or add the referenced authored rooms before export."
    elif isolated_rooms:
        status = "Needs visibility links"
        fix_hint = "Connect adjacent rooms in the VIS editor so KOTOR can render the intended room set."
    elif warnings:
        status = f"Warnings: {len(warnings)} issue(s)"
        fix_hint = "Review authored visible-room lists before packaging the module."
    else:
        status = "Ready"
        fix_hint = "VIS room visibility intent is ready for staged export; verify culling in game."
    return AuthoredModuleVisibilityReadiness(
        ready=ready,
        status=status,
        room_count=len(room_names),
        vis_entry_count=explicit_entry_count or len(room_names),
        link_count=link_count,
        cross_room_link_count=cross_room_link_count,
        isolated_rooms=tuple(isolated_rooms),
        missing_targets=tuple(missing_targets),
        warnings=tuple(warnings),
        blocking_messages=blocking,
        fix_hint=fix_hint,
    )


def _game_executable_name(game: str) -> str:
    return "swkotor2.exe" if str(game or "").upper() == "K2" else "swkotor.exe"


_PROOF_EVIDENCE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}


def _valid_proof_evidence_path(evidence_path: str) -> bool:
    if not evidence_path:
        return False
    path = Path(evidence_path)
    return path.is_file() and path.stat().st_size > 0 and path.suffix.lower() in _PROOF_EVIDENCE_EXTENSIONS


def _derive_game_root_dir(resolved_modules_dir: str) -> str:
    if not resolved_modules_dir:
        return ""
    return str(Path(resolved_modules_dir).parent)


def _launch_helper_command(*, game: str, proof_manifest_path: str, resolved_game_root_dir: str) -> str:
    if not proof_manifest_path or not resolved_game_root_dir:
        return ""
    return (
        "python scripts/launch_grdev01_smoke_test.py "
        f'--proof-manifest "{proof_manifest_path}" '
        f'--game "{str(game or "K1").upper()}" '
        f'--game-root-dir "{resolved_game_root_dir}" '
        "--dry-run"
    )


def _recorded_game_proof_complete(proof: dict[str, Any]) -> bool:
    game_test = proof.get("game_test")
    if not isinstance(game_test, dict):
        return False
    evidence_path = str(game_test.get("evidence_path") or proof.get("in_game_proof_evidence_path") or proof.get("evidence_path") or "")
    return (
        bool(proof.get("game_tested"))
        and proof.get("manual_proof_required") is False
        and bool(game_test.get("accepted"))
        and not list(game_test.get("missing_checks") or ())
        and _valid_proof_evidence_path(evidence_path)
    )


def _input_statuses(project: AuthoredModuleProject) -> tuple[AuthoredModuleInputStatus, ...]:
    root = project.module_root
    entry = project.placements.entry_point
    gameplay_counts = _gameplay_counts(project)
    gameplay_total = sum(gameplay_counts.values())
    light_count = _lighting_count(project)
    gameplay_label = ", ".join(f"{count} {kind}" for kind, count in gameplay_counts.items() if count)
    return (
        AuthoredModuleInputStatus(
            "Module resref",
            bool(root),
            root or "(not selected)",
            "Choose a 16-character-or-shorter module resref such as grdev01.",
        ),
        AuthoredModuleInputStatus(
            "Game",
            project.game in {"K1", "K2"},
            project.game,
            "Choose whether this module targets KOTOR 1 or KOTOR 2.",
        ),
        AuthoredModuleInputStatus(
            "Authored rooms",
            bool(project.rooms),
            f"{len(project.rooms)} room(s)",
            "Create at least one primitive or floor-plan room.",
        ),
        AuthoredModuleInputStatus(
            "Module entry point",
            normalise_resref(entry.area_resref) == root and bool(root),
            f"{normalise_resref(entry.area_resref) or '(missing)'} @ {tuple(entry.position)}",
            "Place the player start inside the module's entry area on walkable WOK.",
        ),
        AuthoredModuleInputStatus(
            "Room lighting",
            True,
            f"{light_count} authored light(s)" if light_count else "No authored lights yet",
            "Add room lights when the module needs authored lighting or future lightmap baking.",
        ),
        AuthoredModuleInputStatus(
            "Gameplay placements",
            True,
            gameplay_label or "No extra objects yet",
            "Add creatures, placeables, doors, waypoints, triggers, sounds, cameras, or stores when this module needs gameplay content.",
        ),
    )


def _room_primitive_summary(rooms: tuple[AuthoredRoomReadiness, ...]) -> str:
    names = []
    for room in rooms:
        label = room.primitive_type
        if label == "FloorPlanRoomPrimitive":
            label = "floor-plan extrusion"
        elif label == "AuthoredRoomComposition":
            label = "primitive composition"
        elif label == "RectangularRoomPrimitive":
            label = "rectangular primitive"
        elif label.endswith("Primitive"):
            label = label[:-9].lower()
        names.append(label)
    unique = tuple(dict.fromkeys(names))
    return ", ".join(unique) if unique else "none"


def _toolchain_statuses(
    project: AuthoredModuleProject,
    *,
    rooms: tuple[AuthoredRoomReadiness, ...],
    pathing: AuthoredModulePathingReadiness,
    template_references: tuple[AuthoredGameplayTemplateReference, ...],
    transition_references: tuple[AuthoredModuleTransitionReference, ...],
    script_references: tuple[AuthoredModuleScriptReference, ...],
    missing_runtime_resources: tuple[RuntimeResourceKey, ...],
    expected_runtime_resources: tuple[RuntimeResourceKey, ...],
    blocking_messages: tuple[str, ...],
    proof_status: str,
    game_tested: bool,
    proof_recording_script_path: str,
    geometry_validation: AuthoredFloorPlanGeometryReadiness,
    doorway_transition: AuthoredDoorwayTransitionReadiness,
    visibility: AuthoredModuleVisibilityReadiness,
    component_edit: AuthoredComponentEditReadiness,
) -> tuple[AuthoredModuleToolchainStatus, ...]:
    """Summarize the full Map Studio path from geometry intent to game proof."""

    room_count = len(rooms)
    walkable_faces = sum(room.walkable_face_count for room in rooms)
    room_blocking = tuple(message for room in rooms for message in room.blocking_messages)
    geometry_ready = bool(room_count) and not room_blocking
    entry = project.placements.entry_point
    entry_ready = normalise_resref(entry.area_resref) == project.module_root and bool(project.module_root)
    gameplay_counts = _gameplay_counts(project)
    placement_total = sum(gameplay_counts.values())
    placement_summary = _resource_placement_summary(gameplay_counts)
    placement_status = "Planned" if placement_total else "Optional"
    packaged_templates = sum(1 for ref in template_references if ref.packaged)
    external_templates = len(template_references) - packaged_templates
    template_label = (
        f"; {len(template_references)} template ref(s), {packaged_templates} packaged, {external_templates} external/base-game"
        if template_references
        else "; no template refs"
    )
    light_count = _lighting_count(project)
    rooms_with_lights, rooms_without_lights = _lighting_room_coverage(project, rooms)
    if light_count:
        lighting_status = f"{light_count} authored light(s)"
        lighting_value = (
            f"{light_count} authored light(s) across {len(rooms_with_lights)} room(s); "
            f"{len(rooms_without_lights)} room(s) still need lighting/lightmap planning"
        )
    else:
        lighting_status = "Optional"
        lighting_value = "No authored room lights yet; lightmap planning not started"
    packaged_count = len(expected_runtime_resources) - len(missing_runtime_resources)
    package_ready = bool(expected_runtime_resources) and not missing_runtime_resources and not blocking_messages
    proof_ready = bool(game_tested)
    proof_label = "Recorded" if proof_ready else proof_status.replace("_", " ")
    if proof_recording_script_path and not proof_ready:
        proof_label = "Recorder ready after warp test"
    transition_count = len(transition_references)
    complete_transitions = sum(1 for ref in transition_references if ref.complete)
    incomplete_transitions = transition_count - complete_transitions
    if transition_count:
        transition_ready = incomplete_transitions == 0
        transition_status = "Ready" if transition_ready else "Needs destination"
        transition_value = f"{complete_transitions}/{transition_count} authored transition(s) linked"
        transition_fix = "Set a destination tag/waypoint and module resref for each authored transition."
    else:
        transition_ready = True
        transition_status = "Optional"
        transition_value = "No authored transitions yet"
        transition_fix = "Add a door, trigger, or waypoint transition when this module needs exits."
    script_ref_count = len(script_references)
    packaged_scripts = sum(1 for ref in script_references if ref.packaged)
    external_scripts = script_ref_count - packaged_scripts
    if script_ref_count:
        script_status = "Ready"
        script_value = f"{script_ref_count} script hook(s), {packaged_scripts} packaged, {external_scripts} external/Override"
        script_fix = "Package custom NCS scripts or confirm the referenced base-game/Override scripts are installed."
    else:
        script_status = "Optional"
        script_value = "No authored module/area script hooks"
        script_fix = "Add OnEnter, OnExit, heartbeat, or module event scripts when this map needs scripted behavior."
    return (
        AuthoredModuleToolchainStatus(
            "Geometry authoring",
            geometry_ready,
            "Ready" if geometry_ready else "Needs authored room geometry",
            (
                f"{room_count} room(s), {_room_primitive_summary(rooms)}; tools: primitives, "
                "floor-plan extrusion, bevel, inset, rectangular cut, rectangular union"
            ),
            "Create a primitive/composition room or fix room geometry blockers.",
        ),
        AuthoredModuleToolchainStatus(
            "Walkmesh",
            walkable_faces > 0 and not room_blocking,
            "Ready" if walkable_faces > 0 and not room_blocking else "Needs walkable WOK faces",
            f"{walkable_faces} walkable face(s)",
            "Set a walkable floor/ramp/stair WOK surface and keep gameplay objects on walkable faces.",
        ),
        AuthoredModuleToolchainStatus(
            "Floor-plan validation",
            geometry_validation.ready,
            geometry_validation.status,
            (
                f"{geometry_validation.checked_room_count}/{geometry_validation.floor_plan_room_count} floor-plan room(s) checked; "
                f"{geometry_validation.opening_count} opening(s); "
                f"{geometry_validation.blocking_issue_count} blocker(s), {geometry_validation.warning_count} warning(s)"
            ),
            geometry_validation.fix_hint,
        ),
        AuthoredModuleToolchainStatus(
            "Doorway/transition intent",
            doorway_transition.ready,
            doorway_transition.status,
            (
                f"{doorway_transition.opening_count} opening(s); "
                f"{doorway_transition.transition_marker_count} door/trigger/waypoint marker(s); "
                f"{doorway_transition.linked_transition_count}/{doorway_transition.transition_reference_count} linked transition(s)"
            ),
            doorway_transition.fix_hint,
        ),
        AuthoredModuleToolchainStatus(
            "Component edit audit",
            component_edit.ready,
            component_edit.status,
            component_edit.latest_summary
            or f"{component_edit.edit_count} recorded component edit(s), {component_edit.risky_edit_count} needing review",
            component_edit.fix_hint,
        ),
        AuthoredModuleToolchainStatus(
            "PTH pathing",
            pathing.ready,
            pathing.status,
            (
                f"{pathing.pth_resource or '(no PTH)'}; {pathing.point_count} point(s), "
                f"{pathing.connection_count} connection(s), {pathing.walkmesh_component_count} walkmesh island(s); "
                f"anchors: {', '.join(pathing.anchor_labels) or 'walkmesh center only'}"
            ),
            pathing.fix_hint or "Fix walkability/path anchors before export.",
        ),
        AuthoredModuleToolchainStatus(
            "VIS visibility",
            visibility.ready,
            visibility.status,
            (
                f"{visibility.vis_entry_count} VIS entr{'y' if visibility.vis_entry_count == 1 else 'ies'}; "
                f"{visibility.link_count} link(s), {visibility.cross_room_link_count} cross-room; "
                f"{len(visibility.isolated_rooms)} isolated room(s), {len(visibility.missing_targets)} missing target(s)"
            ),
            visibility.fix_hint,
        ),
        AuthoredModuleToolchainStatus(
            "Lighting",
            True,
            lighting_status,
            lighting_value,
            "Add key/fill/ambient room lights before baking or exporting lighting-sensitive modules.",
        ),
        AuthoredModuleToolchainStatus(
            "Resource placement",
            True,
            placement_status,
            f"{placement_summary}; palette: {_resource_placement_palette_label()}",
            "Place KOTOR resources from the game library when the module needs creatures, objects, exits, sounds, cameras, or merchants.",
        ),
        AuthoredModuleToolchainStatus(
            "Gameplay layout",
            entry_ready,
            "Ready" if entry_ready else "Needs module entry point",
            f"Entry {normalise_resref(entry.area_resref) or '(missing)'} @ {tuple(entry.position)}; {placement_total} placement(s){template_label}",
            "Place the player start inside the module root area; add or package custom templates when placements should not rely on base-game resources.",
        ),
        AuthoredModuleToolchainStatus(
            "Transitions",
            transition_ready,
            transition_status,
            transition_value,
            transition_fix,
        ),
        AuthoredModuleToolchainStatus(
            "Scripts",
            True,
            script_status,
            script_value,
            script_fix,
        ),
        AuthoredModuleToolchainStatus(
            "Runtime package",
            package_ready,
            "Ready" if package_ready else "Needs generated module resources",
            f"{packaged_count}/{len(expected_runtime_resources)} resources present",
            "Generate ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX, WOK, and the installable .mod package.",
        ),
        AuthoredModuleToolchainStatus(
            "In-game proof",
            proof_ready,
            proof_label,
            proof_recording_script_path or "No proof recorder yet",
            "Run KOTOR, warp to the module, verify spawn/walk/placeables, then record screenshot/video evidence.",
        ),
    )


def _room_readiness(project: AuthoredModuleProject) -> tuple[AuthoredRoomReadiness, ...]:
    rooms: list[AuthoredRoomReadiness] = []
    for room in project.rooms:
        room_resref = room.normalised_resref()
        primitive_type = type(room.primitive).__name__
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            rooms.append(
                AuthoredRoomReadiness(
                    room_resref=room_resref,
                    primitive_type=primitive_type,
                    can_preview_geometry=False,
                    blocking_messages=(f"Room {room_resref or '(unnamed)'} could not compile: {exc}",),
                )
            )
            continue
        walkable_faces = int(getattr(geometry.wok, "walkable_face_count", lambda: 0)())
        walkmesh_audit = audit_authored_wok(room_resref, geometry.wok)
        faces = tuple(getattr(geometry.wok, "faces", ()) or ())
        floor_surface_id = int(getattr(faces[0], "surface", -1)) if faces else -1
        blockers: list[str] = []
        if not getattr(geometry.room_mesh, "faces", ()):
            blockers.append(f"Room {room_resref} has no renderable room mesh faces.")
        if walkable_faces <= 0:
            blockers.append(f"Room {room_resref} has no walkable WOK faces.")
        blockers.extend(walkmesh_audit.blocking_messages)
        rooms.append(
            AuthoredRoomReadiness(
                room_resref=normalise_resref(geometry.room_resref or room_resref),
                primitive_type=primitive_type,
                can_preview_geometry=not blockers,
                mesh_name=str(getattr(geometry.room_mesh, "name", "") or ""),
                texture=str(getattr(geometry.room_mesh, "texture", "") or ""),
                floor_surface_id=floor_surface_id,
                floor_surface_name=walkmesh_surface_name(floor_surface_id) if floor_surface_id >= 0 else "",
                helper_mesh_count=len(tuple(getattr(geometry, "helper_meshes", ()) or ())),
                walkable_face_count=walkable_faces,
                walkable_component_count=walkmesh_audit.walkable_component_count,
                invalid_wok_face_count=walkmesh_audit.invalid_face_count,
                degenerate_wok_face_count=walkmesh_audit.degenerate_face_count,
                non_manifold_wok_edge_count=walkmesh_audit.non_manifold_edge_count,
                warnings=tuple(walkmesh_audit.warnings),
                blocking_messages=tuple(blockers),
            )
        )
    return tuple(rooms)


def build_authored_module_readiness(
    project: AuthoredModuleProject,
    *,
    packaged_resources: Iterable[Any] = (),
    game_tested: bool = False,
    proof_metadata: dict[str, Any] | None = None,
) -> AuthoredModuleReadiness:
    """Build a capability-honest readiness summary for Map Studio UI/export."""

    proof = dict(proof_metadata or {})
    validation = validate_authored_module_project(project)
    rooms = _room_readiness(project)
    gameplay_counts = _gameplay_counts(project)
    lighting_count = _lighting_count(project)
    rooms_with_lights, rooms_without_lights = _lighting_room_coverage(project, rooms)
    present = _present_keys(packaged_resources)
    expected = _expected_keys(project.module_root, rooms)
    present_set = set(present)
    template_references = _gameplay_template_references(project, present=present_set)
    transition_references = _transition_references(project)
    script_references = _script_references(project, present=present_set)
    pathing = _pathing_readiness(project)
    visibility = _visibility_readiness(project)
    component_edit = _component_edit_readiness(project)
    geometry_validation = _floor_plan_geometry_readiness(project)
    doorway_transition = _doorway_transition_readiness(
        project,
        geometry_validation=geometry_validation,
        transition_references=transition_references,
    )
    export_object_boundaries = map_studio_export_object_boundaries(project)
    external_template_count = sum(1 for ref in template_references if not ref.packaged)
    incomplete_transition_count = sum(1 for ref in transition_references if not ref.complete)
    external_script_count = sum(1 for ref in script_references if not ref.packaged)
    missing = tuple(key for key in expected if key not in present_set)
    room_blocking = tuple(message for room in rooms for message in room.blocking_messages)
    preview_blocking = tuple(validation.blocking_issues) + room_blocking + geometry_validation.blocking_messages
    pathing_blocking = tuple(pathing.blocking_messages or ())
    visibility_blocking = tuple(visibility.blocking_messages or ())
    blocking = preview_blocking + pathing_blocking + visibility_blocking
    template_warnings: tuple[str, ...] = ()
    if external_template_count:
        template_warnings = (
            f"{external_template_count} gameplay template reference(s) rely on base-game, Override, "
            "or another installed mod resource instead of being packaged in this .mod.",
        )
    transition_warnings: tuple[str, ...] = ()
    if incomplete_transition_count:
        transition_warnings = (
            f"{incomplete_transition_count} authored transition(s) name a module but are missing a destination tag/waypoint.",
        )
    script_warnings: tuple[str, ...] = ()
    if external_script_count:
        script_warnings = (
            f"{external_script_count} authored script hook(s) rely on base-game, Override, or another installed mod .ncs instead of being packaged.",
        )
    component_warnings = component_edit.validation_messages if not component_edit.ready else ()
    room_warnings = tuple(warning for room in rooms for warning in room.warnings)
    warnings = (
        tuple(validation.warnings)
        + room_warnings
        + geometry_validation.warnings
        + tuple(pathing.warnings or ())
        + tuple(visibility.warnings or ())
        + doorway_transition.warnings
        + template_warnings
        + transition_warnings
        + script_warnings
        + component_warnings
    )
    can_preview = not preview_blocking and bool(rooms) and all(room.can_preview_geometry for room in rooms)
    can_export_candidate = can_preview and not missing and pathing.ready and not visibility_blocking
    proof_game_tested = can_export_candidate and _recorded_game_proof_complete(proof)
    ready_for_game_test = can_export_candidate and not proof_game_tested
    proof_manifest_path = str(proof.get("proof_manifest_path") or "")
    checklist_path = str(proof.get("checklist_path") or "")
    installed_module_path = str(proof.get("installed_module_path") or "")
    backup_module_path = str(proof.get("backup_module_path") or "")
    resolved_modules_dir = str(proof.get("resolved_modules_dir") or "")
    resolved_game_root_dir = str(proof.get("resolved_game_root_dir") or "") or _derive_game_root_dir(resolved_modules_dir)
    evidence_path = str(proof.get("in_game_proof_evidence_path") or proof.get("evidence_path") or "")
    warp_command = str(proof.get("warp_command") or f"warp {project.module_root}")
    expected_executable_path = str(proof.get("expected_executable_path") or "")
    if not expected_executable_path:
        executable_name = _game_executable_name(project.game)
        expected_executable_path = str(Path(resolved_game_root_dir) / executable_name) if resolved_game_root_dir else executable_name
    launch_helper = str(proof.get("launch_helper_command") or "") or _launch_helper_command(
        game=project.game,
        proof_manifest_path=proof_manifest_path,
        resolved_game_root_dir=resolved_game_root_dir,
    )
    elevated_launch_script_path = str(proof.get("elevated_launch_script_path") or "")
    proof_recording_script_path = str(proof.get("proof_recording_script_path") or "")
    modder_test_plan = dict(proof.get("modder_test_plan") or {}) if isinstance(proof.get("modder_test_plan"), dict) else {}
    if proof_game_tested:
        proof_status = "game_smoke_tested"
        launch_status = "proof_recorded"
    elif installed_module_path:
        proof_status = "installed_for_game_test"
        launch_status = "ready_for_launch_helper" if resolved_game_root_dir else "installed_missing_game_root"
    elif proof_manifest_path or checklist_path:
        proof_status = "staged_for_game_test"
        launch_status = "install_first"
    elif can_export_candidate:
        proof_status = "not_staged"
        launch_status = "package_first"
    else:
        proof_status = "not_ready"
        launch_status = "not_ready"
    if proof_game_tested:
        stage = "game_tested"
        preview_status = "Ready"
        export_status = "Game-tested"
        next_action = "Keep the proof manifest and screenshots with the package before calling this launch-ready."
    elif can_export_candidate:
        stage = "export_candidate"
        preview_status = "Ready"
        export_status = "Ready for package/game smoke test"
        if installed_module_path:
            if launch_helper:
                next_action = f"Run the launch helper dry-run, launch KOTOR, run `{warp_command}`, then record proof with screenshot/video evidence."
            else:
                next_action = f"Launch KOTOR and run `{warp_command}`, then record the proof manifest with screenshot/video evidence."
        elif proof_manifest_path or checklist_path:
            next_action = f"Install/copy the staged package into KOTOR Modules, launch KOTOR, and run `warp {project.module_root}`."
        else:
            next_action = f"Package the module, install it, launch KOTOR, and run `warp {project.module_root}` for game proof."
    elif can_preview:
        stage = "previewable"
        preview_status = "Ready"
        if not pathing.ready:
            export_status = "Pathing blocked"
            next_action = pathing.fix_hint or "Move the module entry point and gameplay anchors onto generated walkable WOK before export."
        elif visibility_blocking:
            export_status = "VIS visibility blocked"
            next_action = visibility.fix_hint or "Fix broken VIS room links before staging the module."
        else:
            export_status = "Missing runtime resources"
            next_action = "Generate or stage ARE/GIT/IFO/PTH/LYT/VIS, room WOK, and matching room MDL/MDX resources before export."
    else:
        stage = "blocked"
        preview_status = "Not ready"
        export_status = "Not ready"
        next_action = "Fix the blocking project, room, or walkmesh issues before preview/export."
    toolchain = _toolchain_statuses(
        project,
        rooms=rooms,
        pathing=pathing,
        template_references=template_references,
        transition_references=transition_references,
        script_references=script_references,
        missing_runtime_resources=missing,
        expected_runtime_resources=expected,
        blocking_messages=blocking,
        proof_status=proof_status,
        game_tested=proof_game_tested,
        proof_recording_script_path=proof_recording_script_path,
        geometry_validation=geometry_validation,
        doorway_transition=doorway_transition,
        visibility=visibility,
        component_edit=component_edit,
    )
    return AuthoredModuleReadiness(
        module_root=project.module_root,
        game=project.game,
        capability_stage=stage,
        inputs=_input_statuses(project),
        rooms=rooms,
        toolchain=toolchain,
        geometry_validation=geometry_validation,
        doorway_transition=doorway_transition,
        visibility=visibility,
        component_edit=component_edit,
        can_preview=can_preview,
        can_export_candidate=can_export_candidate,
        ready_for_game_test=ready_for_game_test,
        game_tested=proof_game_tested,
        preview_status=preview_status,
        export_status=export_status,
        next_action=next_action,
        expected_runtime_resources=expected,
        present_runtime_resources=present,
        missing_runtime_resources=missing,
        warnings=warnings,
        blocking_messages=blocking,
        metadata={
            "source": "src.core.modules.authored_module_readiness",
            "room_count": len(rooms),
            "export_object_count": len(export_object_boundaries),
            "export_object_boundaries": [boundary.to_metadata() for boundary in export_object_boundaries],
            "uv_handoff_object_count": sum(1 for boundary in export_object_boundaries if boundary.uv_handoff_recommended),
            "walkable_face_count": sum(room.walkable_face_count for room in rooms),
            "walkable_component_count": sum(room.walkable_component_count for room in rooms),
            "disconnected_walkmesh_room_count": sum(1 for room in rooms if room.walkable_component_count > 1),
            "invalid_wok_face_count": sum(room.invalid_wok_face_count for room in rooms),
            "degenerate_wok_face_count": sum(room.degenerate_wok_face_count for room in rooms),
            "non_manifold_wok_edge_count": sum(room.non_manifold_wok_edge_count for room in rooms),
            "pathing": {
                "ready": pathing.ready,
                "status": pathing.status,
                "pth_resource": pathing.pth_resource,
                "point_count": pathing.point_count,
                "connection_count": pathing.connection_count,
                "walkmesh_component_count": pathing.walkmesh_component_count,
                "anchor_labels": list(pathing.anchor_labels),
                "warnings": list(pathing.warnings),
                "blocking_messages": list(pathing.blocking_messages),
                "blocking_targets": list(pathing.blocking_targets),
                "fix_hint": pathing.fix_hint,
            },
            "visibility": {
                "ready": visibility.ready,
                "status": visibility.status,
                "room_count": visibility.room_count,
                "vis_entry_count": visibility.vis_entry_count,
                "link_count": visibility.link_count,
                "cross_room_link_count": visibility.cross_room_link_count,
                "isolated_rooms": list(visibility.isolated_rooms),
                "missing_targets": [dict(item) for item in visibility.missing_targets],
                "warnings": list(visibility.warnings),
                "blocking_messages": list(visibility.blocking_messages),
                "fix_hint": visibility.fix_hint,
            },
            "geometry_validation": {
                "ready": geometry_validation.ready,
                "status": geometry_validation.status,
                "floor_plan_room_count": geometry_validation.floor_plan_room_count,
                "checked_room_count": geometry_validation.checked_room_count,
                "opening_count": geometry_validation.opening_count,
                "blocking_issue_count": geometry_validation.blocking_issue_count,
                "warning_count": geometry_validation.warning_count,
                "blocking_messages": list(geometry_validation.blocking_messages),
                "warnings": list(geometry_validation.warnings),
                "fix_hint": geometry_validation.fix_hint,
            },
            "doorway_transition": {
                "ready": doorway_transition.ready,
                "status": doorway_transition.status,
                "opening_count": doorway_transition.opening_count,
                "transition_marker_count": doorway_transition.transition_marker_count,
                "transition_reference_count": doorway_transition.transition_reference_count,
                "linked_transition_count": doorway_transition.linked_transition_count,
                "warnings": list(doorway_transition.warnings),
                "fix_hint": doorway_transition.fix_hint,
            },
            "component_edit": {
                "ready": component_edit.ready,
                "status": component_edit.status,
                "latest_room_resref": component_edit.latest_room_resref,
                "latest_operation": component_edit.latest_operation,
                "latest_summary": component_edit.latest_summary,
                "edit_count": component_edit.edit_count,
                "risky_edit_count": component_edit.risky_edit_count,
                "topology_changed": component_edit.topology_changed,
                "walkmesh_review_required": component_edit.walkmesh_review_required,
                "export_candidate_stale": component_edit.export_candidate_stale,
                "game_proof_stale": component_edit.game_proof_stale,
                "stale_outputs": list(component_edit.stale_outputs),
                "resource_impacts": [dict(row) for row in component_edit.resource_impacts],
                "next_action": component_edit.next_action,
                "validation_messages": list(component_edit.validation_messages),
                "fix_hint": component_edit.fix_hint,
            },
            "gameplay_counts": gameplay_counts,
            "gameplay_placement_count": sum(gameplay_counts.values()),
            "resource_placement_summary": _resource_placement_summary(gameplay_counts),
            "resource_placement_palette": list(_resource_placement_palette(gameplay_counts)),
            "gameplay_template_reference_count": len(template_references),
            "gameplay_packaged_template_count": sum(1 for ref in template_references if ref.packaged),
            "gameplay_external_template_count": external_template_count,
            "gameplay_template_references": [
                {
                    "kind": ref.kind,
                    "template_resref": ref.template_resref,
                    "restype": ref.restype,
                    "tag": ref.tag,
                    "status": ref.status,
                    "packaged": ref.packaged,
                    "required": ref.required,
                    "message": ref.message,
                }
                for ref in template_references
            ],
            "transition_count": len(transition_references),
            "transition_complete_count": sum(1 for ref in transition_references if ref.complete),
            "transition_incomplete_count": incomplete_transition_count,
            "transition_references": [
                {
                    "kind": ref.kind,
                    "tag": ref.tag,
                    "template_resref": ref.template_resref,
                    "linked_to": ref.linked_to,
                    "linked_to_module": ref.linked_to_module,
                    "status": ref.status,
                    "complete": ref.complete,
                    "message": ref.message,
                }
                for ref in transition_references
            ],
            "script_reference_count": len(script_references),
            "script_packaged_count": sum(1 for ref in script_references if ref.packaged),
            "script_external_count": external_script_count,
            "script_references": [
                {
                    "scope": ref.scope,
                    "field_name": ref.field_name,
                    "script_resref": ref.script_resref,
                    "restype": ref.restype,
                    "status": ref.status,
                    "packaged": ref.packaged,
                    "message": ref.message,
                }
                for ref in script_references
            ],
            "lighting_count": lighting_count,
            "lighting_room_count": len(rooms_with_lights),
            "rooms_with_authored_lights": list(rooms_with_lights),
            "rooms_without_authored_lights": list(rooms_without_lights),
            "lightmap_planning_status": "planned" if lighting_count else "not_started",
            "room_lights": [
                {
                    "name": light.name,
                    "room_resref": light.room_resref,
                    "position": [float(light.position[0]), float(light.position[1]), float(light.position[2])],
                    "color": [float(light.color[0]), float(light.color[1]), float(light.color[2])],
                    "radius": float(light.radius),
                    "intensity": float(light.intensity),
                    "light_type": light.light_type,
                }
                for light in tuple(getattr(project, "lights", ()) or ())
            ],
            "proof_status": proof_status,
            "proof_game_tested": proof_game_tested,
            "proof_manifest_path": proof_manifest_path,
            "checklist_path": checklist_path,
            "installed_module_path": installed_module_path,
            "backup_module_path": backup_module_path,
            "resolved_modules_dir": resolved_modules_dir,
            "resolved_game_root_dir": resolved_game_root_dir,
            "expected_executable_path": expected_executable_path,
            "launch_helper_command": launch_helper,
            "elevated_launch_script_path": elevated_launch_script_path,
            "proof_recording_script_path": proof_recording_script_path,
            "modder_test_plan": modder_test_plan,
            "launch_status": launch_status,
            "warp_command": warp_command,
            "in_game_proof_evidence_path": evidence_path,
            "room_styles": [
                {
                    "room_resref": room.room_resref,
                    "texture": room.texture,
                    "floor_surface_id": room.floor_surface_id,
                    "floor_surface_name": room.floor_surface_name,
                }
                for room in rooms
            ],
            "toolchain": [
                {
                    "name": status.name,
                    "ready": status.ready,
                    "status": status.status,
                    "value_label": status.value_label,
                    "fix_hint": status.fix_hint,
                }
                for status in toolchain
            ],
        },
    )


__all__ = [
    "AuthoredGameplayTemplateReference",
    "AuthoredComponentEditReadiness",
    "AuthoredFloorPlanGeometryReadiness",
    "AuthoredModuleTransitionReference",
    "AuthoredModuleInputStatus",
    "AuthoredModulePathingReadiness",
    "AuthoredModuleReadiness",
    "AuthoredModuleScriptReference",
    "AuthoredModuleToolchainStatus",
    "AuthoredModuleVisibilityReadiness",
    "AuthoredRoomReadiness",
    "RuntimeResourceKey",
    "build_authored_module_readiness",
]
