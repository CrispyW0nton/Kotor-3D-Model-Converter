"""Transactional K1/K2 retargeting for authored Map Studio projects.

Porting an authored KMAP is more than recording a UI decision.  The selected
game controls the binary MDL writer, ARE metadata, package validation, and the
target installation.  This service therefore commits the target everywhere
that owns export semantics, while leaving source geometry and resource
references intact for the target-game dependency validator to inspect.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from src.core.level import KMapProject


_SUPPORTED_GAMES = frozenset({"K1", "K2"})
_AUTHORED_SECTION = "authored_module"
_IMPORTED_MESH_KINDS = frozenset({"imported_mesh"})
_STALE_OUTPUTS = (
    "ARE",
    "GIT",
    "IFO",
    "PTH",
    "LYT",
    "VIS",
    "MDL",
    "MDX",
    "WOK",
    ".mod",
)
_EVIDENCE_KEYS = (
    "pack_manifest_path",
    "proof_manifest_path",
    "checklist_path",
    "installed_module_path",
    "backup_module_path",
    "resolved_modules_dir",
    "resolved_game_root_dir",
    "launch_helper_command",
    "elevated_launch_script_path",
    "proof_recording_script_path",
    "package_resource_inventory",
    "modder_test_plan",
    "export_job",
    "in_game_proof",
    "in_game_proof_evidence_path",
    "evidence_path",
    "game_test",
    "proof_state",
)


@dataclass
class ModulePortReport:
    ok: bool = False
    source_game: str = "K1"
    target_game: str = "K2"
    unsupported: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_ported"


def _game(value: Any) -> str:
    return str(value or "").strip().upper()


def _failure(src: str, dst: str, code: str, message: str) -> ModulePortReport:
    return ModulePortReport(
        ok=False,
        source_game=src or "K1",
        target_game=dst or "K2",
        unsupported=[message],
        message=message,
        code=code,
    )


def _retarget_imported_mesh_tags(value: Any, target_game: str) -> int:
    """Retarget every imported-mesh primitive without touching provenance.

    A recursive walk keeps this forward-compatible with authored containers
    that may later nest room primitives.  Only dictionaries explicitly tagged
    as imported meshes are changed; metadata/resource ``game`` fields remain
    source identity and are intentionally preserved.
    """

    updated = 0
    if isinstance(value, dict):
        kind = str(value.get("type") or value.get("kind") or "").strip().lower()
        if kind in _IMPORTED_MESH_KINDS:
            value["game"] = target_game
            updated += 1
        for child in value.values():
            updated += _retarget_imported_mesh_tags(child, target_game)
    elif isinstance(value, list):
        for child in value:
            updated += _retarget_imported_mesh_tags(child, target_game)
    return updated


def _invalidate_authored_evidence(payload: dict[str, Any], source_game: str, target_game: str) -> None:
    for key in _EVIDENCE_KEYS:
        payload.pop(key, None)
    payload["runtime_resources"] = []
    payload["game_tested"] = False
    payload["manual_proof_required"] = True

    previous = payload.get("export_proof_invalidation")
    previous = dict(previous) if isinstance(previous, dict) else {}
    stale_outputs = list(previous.get("stale_outputs") or ())
    for output in _STALE_OUTPUTS:
        if output not in stale_outputs:
            stale_outputs.append(output)
    payload["export_proof_invalidation"] = {
        **previous,
        "invalidates_previous_export": True,
        "invalidates_game_proof": True,
        "latest_operation": "module_port_retarget",
        "latest_summary": f"Retargeted authored module from {source_game} to {target_game}.",
        "stale_outputs": stale_outputs,
        "readiness_impact": "All target-game runtime resources must be regenerated and re-proven in game.",
        "next_action": (
            f"Validate target-game dependencies, rebuild the {target_game} module package, install it in the "
            "matching game, and record fresh in-game warp proof."
        ),
    }


def _retarget_authored_payload(
    payload: Any,
    *,
    source_game: str,
    target_game: str,
) -> tuple[dict[str, Any], int, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("The authored_module KMAP section must be a JSON object.")

    candidate = deepcopy(payload)
    payload_game = _game(candidate.get("game") or source_game)
    if payload_game not in _SUPPORTED_GAMES:
        raise ValueError(f"The authored module uses unsupported game {payload_game or '(missing)'!r}.")
    if payload_game != source_game:
        raise ValueError(
            f"The authored module is tagged {payload_game}, but this port request names {source_game} as its source."
        )

    candidate["game"] = target_game
    imported_count = _retarget_imported_mesh_tags(candidate.get("rooms", ()), target_game)
    _invalidate_authored_evidence(candidate, source_game, target_game)

    # Decode the complete candidate before touching the live KMAP.  This proves
    # that the raw section and the domain model agree on the new export target.
    from .authored_imported_mesh import ImportedMeshRoomPrimitive
    from .authored_module_kmap_bridge import authored_project_from_kmap_payload

    decoded = authored_project_from_kmap_payload(
        candidate,
        fallback_name=str(candidate.get("module_root") or "new_level"),
        fallback_game=target_game,
    )
    if decoded.game != target_game:
        raise ValueError(f"Decoded authored module remained {decoded.game}; expected {target_game}.")
    for room in decoded.rooms:
        primitive = room.primitive
        if isinstance(primitive, ImportedMeshRoomPrimitive) and _game(primitive.game) != target_game:
            raise ValueError(
                f"Imported room {room.room_resref} remained tagged {primitive.game}; expected {target_game}."
            )

    risks: list[str] = []
    placements = decoded.placements
    placement_count = sum(
        len(tuple(getattr(placements, field_name, ()) or ()))
        for field_name in (
            "creatures",
            "doors",
            "triggers",
            "encounters",
            "sounds",
            "cameras",
            "stores",
            "placeables",
            "waypoints",
        )
    )
    if placement_count:
        risks.append(
            f"{placement_count} gameplay placement(s) still reference source resrefs; validate every template in {target_game}."
        )
    if imported_count:
        risks.append(
            f"{imported_count} imported room mesh(es) were retargeted for {target_game} binary output; "
            "their texture, lightmap, and source-model dependencies still require target-game validation."
        )
    return candidate, imported_count, risks


class ModulePorterService:
    """Retarget an authored KMAP as one all-or-nothing state transition."""

    def record_port_decision(self, project: KMapProject, source_game: str, target_game: str) -> ModulePortReport:
        src = _game(source_game)
        dst = _game(target_game)
        if src not in _SUPPORTED_GAMES:
            return _failure(src, dst, "invalid_source_game", f"Unsupported source game {src or '(missing)'!r}; use K1 or K2.")
        if dst not in _SUPPORTED_GAMES:
            return _failure(src, dst, "invalid_target_game", f"Unsupported target game {dst or '(missing)'!r}; use K1 or K2.")
        if src == dst:
            return _failure(src, dst, "same_game", "Source and target game must be different for a module port.")

        current_game = _game(getattr(project, "game", ""))
        if current_game not in _SUPPORTED_GAMES:
            return _failure(
                src,
                dst,
                "invalid_project_game",
                f"The KMAP project uses unsupported game {current_game or '(missing)'!r}.",
            )
        if current_game != src:
            return _failure(
                src,
                dst,
                "source_game_mismatch",
                f"The KMAP currently targets {current_game}; it cannot be ported as a {src} project.",
            )

        try:
            metadata = deepcopy(dict(getattr(project, "metadata", {}) or {}))
            extra_sections = deepcopy(dict(getattr(project, "extra_sections", {}) or {}))
            exports = deepcopy(dict(getattr(project, "exports", {}) or {}))
        except Exception as exc:
            return _failure(src, dst, "snapshot_failed", f"The KMAP could not be snapshotted safely: {exc}")

        payload_locations: list[tuple[dict[str, Any], str]] = []
        if _AUTHORED_SECTION in extra_sections:
            payload_locations.append((extra_sections, _AUTHORED_SECTION))
        if _AUTHORED_SECTION in metadata:
            payload_locations.append((metadata, _AUTHORED_SECTION))
        if not payload_locations:
            return _failure(
                src,
                dst,
                "authored_module_missing",
                "This KMAP has no authored_module section to retarget. Convert/import its rooms into editable Map Studio geometry first.",
            )

        risks: list[str] = []
        imported_count = 0
        try:
            for container, key in payload_locations:
                updated, count, payload_risks = _retarget_authored_payload(
                    container[key],
                    source_game=src,
                    target_game=dst,
                )
                container[key] = updated
                imported_count += count
                for risk in payload_risks:
                    if risk not in risks:
                        risks.append(risk)
        except Exception as exc:
            return _failure(src, dst, "authored_module_invalid", f"The authored module could not be retargeted safely: {exc}")

        # Project/module game fields select target-game services.  Preserve the
        # previous module game as provenance before switching the live target.
        module_updates: list[tuple[Any, str, dict[str, Any]]] = []
        try:
            for module in tuple(getattr(project, "modules", ()) or ()):
                old_game = _game(getattr(module, "game", "")) or src
                module_metadata = deepcopy(dict(getattr(module, "metadata", {}) or {}))
                module_metadata.setdefault("source_game", old_game)
                module_updates.append((module, old_game, module_metadata))
                if str(getattr(module, "source_path", "") or "").strip():
                    risk = (
                        f"Module instance {getattr(module, 'module_name', '') or getattr(module, 'module_id', '(unnamed)')} "
                        f"retains a {src} source-module path; baked edits are preserved, but unresolved source resources "
                        f"must be replaced or made available in {dst}."
                    )
                    if risk not in risks:
                        risks.append(risk)
                if old_game != src:
                    risk = (
                        f"Module instance {getattr(module, 'module_name', '') or getattr(module, 'module_id', '(unnamed)')} "
                        f"originates from {old_game}; its source resources were preserved and need {dst} compatibility review."
                    )
                    if risk not in risks:
                        risks.append(risk)
        except Exception as exc:
            return _failure(src, dst, "snapshot_failed", f"Module provenance could not be snapshotted safely: {exc}")

        texture_count = len(tuple(getattr(project, "textures", ()) or ()))
        if texture_count:
            risks.append(
                f"{texture_count} KMAP texture reference(s) were preserved byte-for-byte; validate their TPC/TGA/TXI "
                f"availability and semantics in {dst}."
            )
        blueprint_count = len(tuple(getattr(project, "blueprints", ()) or ()))
        if blueprint_count:
            risks.append(
                f"{blueprint_count} blueprint reference(s) retain source resrefs and require {dst} template validation."
            )

        for key in _EVIDENCE_KEYS:
            metadata.pop(key, None)
            exports.pop(key, None)
        # ``exports`` has no durable settings contract today; any remaining
        # rows could still point at source-game artifacts, so invalidate it in
        # full rather than presenting ambiguous proof as current.
        exports.clear()
        porting = metadata.get("porting")
        porting = dict(porting) if isinstance(porting, dict) else {}
        porting.update(
            {
                "source_game": src,
                "target_game": dst,
                "mode": "authored_project_retargeted",
                "runtime_resources_invalidated": True,
                "game_proof_invalidated": True,
                "imported_mesh_count": imported_count,
                "dependency_risks": list(risks),
            }
        )
        metadata["porting"] = porting

        snapshot = {
            "game": project.game,
            "source_game": project.source_game,
            "target_game": project.target_game,
            "metadata": project.metadata,
            "extra_sections": project.extra_sections,
            "exports": project.exports,
            "dirty": project.dirty,
            "modified_at": project.modified_at,
            "modules": [
                (module, getattr(module, "game", ""), getattr(module, "metadata", {}))
                for module, _old_game, _new_metadata in module_updates
            ],
        }
        try:
            project.game = dst
            project.source_game = src
            project.target_game = dst
            project.metadata = metadata
            project.extra_sections = extra_sections
            project.exports = exports
            for module, _old_game, module_metadata in module_updates:
                module.game = dst
                module.metadata = module_metadata
            project.mark_dirty()
        except Exception as exc:
            project.game = snapshot["game"]
            project.source_game = snapshot["source_game"]
            project.target_game = snapshot["target_game"]
            project.metadata = snapshot["metadata"]
            project.extra_sections = snapshot["extra_sections"]
            project.exports = snapshot["exports"]
            project.dirty = snapshot["dirty"]
            project.modified_at = snapshot["modified_at"]
            for module, old_game, old_metadata in snapshot["modules"]:
                module.game = old_game
                module.metadata = old_metadata
            return _failure(src, dst, "commit_failed", f"The KMAP port transaction was rolled back: {exc}")

        risk_suffix = (
            f" {len(risks)} target dependency risk(s) remain in the Porter report and must be validated before game proof."
            if risks
            else " Target dependencies must still be validated before game proof."
        )
        return ModulePortReport(
            ok=True,
            source_game=src,
            target_game=dst,
            unsupported=risks,
            message=(
                f"Retargeted the authored KMAP from {src} to {dst}. Generated resources, staged packages, and prior "
                f"in-game proof were invalidated; rebuild all target-game resources.{risk_suffix}"
            ),
            code="authored_project_retargeted",
        )
