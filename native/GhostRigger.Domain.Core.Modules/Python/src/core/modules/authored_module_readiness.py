"""Modder-facing readiness checks for authored Map Studio projects.

This module does not compile or package a module.  It answers the product
question a Map Studio panel needs before it enables preview, export, or a game
smoke test: what exists, what is still missing, and how honest we can be about
the current capability stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec, normalise_resref, validate_authored_module_project
from .authored_walkmesh_surfaces import walkmesh_surface_name


RuntimeResourceKey = tuple[str, str]


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
class AuthoredModuleReadiness:
    """Capability-honest summary for a from-scratch Map Studio module."""

    module_root: str
    game: str
    capability_stage: str
    inputs: tuple[AuthoredModuleInputStatus, ...] = ()
    rooms: tuple[AuthoredRoomReadiness, ...] = ()
    toolchain: tuple[AuthoredModuleToolchainStatus, ...] = ()
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


def _lighting_count(project: AuthoredModuleProject) -> int:
    return len(tuple(getattr(project, "lights", ()) or ()))


def _game_executable_name(game: str) -> str:
    return "swkotor2.exe" if str(game or "").upper() == "K2" else "swkotor.exe"


def _derive_game_root_dir(resolved_modules_dir: str) -> str:
    if not resolved_modules_dir:
        return ""
    return str(Path(resolved_modules_dir).parent)


def _launch_helper_command(*, game: str, proof_manifest_path: str, resolved_game_root_dir: str) -> str:
    if str(game or "").upper() != "K1" or not proof_manifest_path or not resolved_game_root_dir:
        return ""
    return (
        "python scripts/launch_grdev01_smoke_test.py "
        f'--proof-manifest "{proof_manifest_path}" '
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
        and bool(evidence_path)
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
    missing_runtime_resources: tuple[RuntimeResourceKey, ...],
    expected_runtime_resources: tuple[RuntimeResourceKey, ...],
    blocking_messages: tuple[str, ...],
    proof_status: str,
    game_tested: bool,
    proof_recording_script_path: str,
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
    light_count = _lighting_count(project)
    packaged_count = len(expected_runtime_resources) - len(missing_runtime_resources)
    package_ready = bool(expected_runtime_resources) and not missing_runtime_resources and not blocking_messages
    proof_ready = bool(game_tested)
    proof_label = "Recorded" if proof_ready else proof_status.replace("_", " ")
    if proof_recording_script_path and not proof_ready:
        proof_label = "Recorder ready after warp test"
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
            "Lighting",
            True,
            f"{light_count} authored light(s)" if light_count else "Optional",
            "Stored as room-light intent for room MDL/lightmap export",
            "Add key/fill/ambient room lights before baking or exporting lighting-sensitive modules.",
        ),
        AuthoredModuleToolchainStatus(
            "Gameplay layout",
            entry_ready,
            "Ready" if entry_ready else "Needs module entry point",
            f"Entry {normalise_resref(entry.area_resref) or '(missing)'} @ {tuple(entry.position)}; {placement_total} placement(s)",
            "Place the player start inside the module root area; add placeables, creatures, doors, and waypoints as needed.",
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
        faces = tuple(getattr(geometry.wok, "faces", ()) or ())
        floor_surface_id = int(getattr(faces[0], "surface", -1)) if faces else -1
        blockers: list[str] = []
        if not getattr(geometry.room_mesh, "faces", ()):
            blockers.append(f"Room {room_resref} has no renderable room mesh faces.")
        if walkable_faces <= 0:
            blockers.append(f"Room {room_resref} has no walkable WOK faces.")
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
    present = _present_keys(packaged_resources)
    expected = _expected_keys(project.module_root, rooms)
    present_set = set(present)
    missing = tuple(key for key in expected if key not in present_set)
    room_blocking = tuple(message for room in rooms for message in room.blocking_messages)
    blocking = tuple(validation.blocking_issues) + room_blocking
    warnings = tuple(validation.warnings)
    can_preview = not blocking and bool(rooms) and all(room.can_preview_geometry for room in rooms)
    can_export_candidate = can_preview and not missing
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
        missing_runtime_resources=missing,
        expected_runtime_resources=expected,
        blocking_messages=blocking,
        proof_status=proof_status,
        game_tested=proof_game_tested,
        proof_recording_script_path=proof_recording_script_path,
    )
    return AuthoredModuleReadiness(
        module_root=project.module_root,
        game=project.game,
        capability_stage=stage,
        inputs=_input_statuses(project),
        rooms=rooms,
        toolchain=toolchain,
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
            "walkable_face_count": sum(room.walkable_face_count for room in rooms),
            "gameplay_counts": gameplay_counts,
            "gameplay_placement_count": sum(gameplay_counts.values()),
            "lighting_count": lighting_count,
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
    "AuthoredModuleInputStatus",
    "AuthoredModuleReadiness",
    "AuthoredModuleToolchainStatus",
    "AuthoredRoomReadiness",
    "RuntimeResourceKey",
    "build_authored_module_readiness",
]
