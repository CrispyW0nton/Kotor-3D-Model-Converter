"""Headless authored KMAP module export pipeline for Map Studio.

This module turns editable ``AuthoredModuleProject`` intent into the Odyssey
runtime resources required by a module package.  Qt windows should call this
service through ``ModuleEditorController`` instead of assembling ARE/GIT/IFO,
LYT/VIS, WOK, or room MDL/MDX resources themselves.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authored_module_layout import compile_authored_module_layout
from .authored_module_lighting import authored_room_light_payload
from .authored_module_metadata import AuthoredAreaMetadata, compile_authored_module_metadata
from .authored_module_objects import (
    AuthoredGameplayPlacement,
    build_git_bytes,
    normalise_resource_resref,
    validate_authored_gameplay_placement_against_walkmesh,
)
from .authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec, normalise_resref, validate_authored_module_project
from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh
from .authored_room_materials import compile_authored_room_material_preflight
from .authored_walkmesh_boundaries import apply_authored_walkmesh_boundary_policy_to_geometry
from .custom_module_packager import CustomModulePackRequest, CustomModulePackResult, PackagedModuleResource, package_custom_module
from .dev_module_smoke import (
    DevModulePackageVerification,
    discover_kotor_modules_dir,
    verify_dev_test_module_package,
)
from .module_format import LYTLayout, VISData, WOKData


ENGINE_MODULE_IFO_RESREF = "module"


@dataclass(frozen=True)
class AuthoredModuleResourceSummary:
    """Compact resource summary for authored-module export reports."""

    resref: str
    restype: str
    size: int
    source: str


@dataclass(frozen=True)
class AuthoredModuleExportRequest:
    """Options for packaging one authored Map Studio module project."""

    project: AuthoredModuleProject
    output_dir: str = ""
    include_reference_check: bool = False
    include_wok_check: bool = True
    include_game_template_check: bool = False
    game_root_dir: str = ""
    strict: bool = True
    dry_run: bool = False
    create_backups: bool = True
    write_loose_resources: bool = True


@dataclass
class AuthoredModuleBuild:
    """In-memory authored module resources consumed by the packager."""

    module_root: str
    game: str
    module: Any
    project: AuthoredModuleProject
    resources: dict[tuple[str, str], Any] = field(default_factory=dict)
    packaged_resources: list[PackagedModuleResource] = field(default_factory=list)
    resource_summaries: list[AuthoredModuleResourceSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthoredModuleExportResult:
    """Result from exporting an authored KMAP module package."""

    ok: bool = False
    module_root: str = ""
    room_resrefs: tuple[str, ...] = ()
    module_path: str = ""
    manifest_path: str = ""
    package_result: CustomModulePackResult | None = None
    package_verification: DevModulePackageVerification | None = None
    resources: list[AuthoredModuleResourceSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    code: str = "not_run"


@dataclass(frozen=True)
class AuthoredModuleInstallPrepRequest:
    """Options for staging an authored module for manual in-game proof."""

    project: AuthoredModuleProject
    output_dir: str = ""
    game_modules_dir: str = ""
    game_root_dir: str = ""
    settings_path: str = ""
    auto_detect_game_modules_dir: bool = False
    overwrite: bool = False
    dry_run: bool = False
    export_request: AuthoredModuleExportRequest | None = None


@dataclass
class AuthoredModuleInstallPrepResult:
    """Safe install-prep result for a manual ``warp <module>`` proof."""

    ok: bool = False
    export_result: AuthoredModuleExportResult | None = None
    installed_module_path: str = ""
    backup_module_path: str = ""
    resolved_modules_dir: str = ""
    resolved_game_root_dir: str = ""
    launch_helper_command: str = ""
    elevated_launch_script_path: str = ""
    proof_recording_script_path: str = ""
    checklist_path: str = ""
    proof_manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_prepared"


@dataclass(frozen=True)
class AuthoredModuleGameProofRequest:
    """Evidence supplied after a real authored-module in-game smoke test."""

    proof_manifest_path: str
    evidence_path: str
    tester: str = ""
    notes: str = ""
    module_loads_in_game: bool = False
    module_identity_matches_authored_resref: bool = False
    player_spawns_on_floor: bool = False
    test_placeable_visible: bool = False
    player_can_walk_on_floor: bool = False
    no_inherited_base_game_geometry_or_scripted_movers: bool = False
    allow_missing_evidence: bool = False


@dataclass
class AuthoredModuleGameProofResult:
    """Result of recording in-game proof for an authored Map Studio module."""

    ok: bool = False
    proof_manifest_path: str = ""
    pack_manifest_path: str = ""
    evidence_path: str = ""
    missing_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_recorded"


@dataclass(frozen=True)
class _ResourceRecord:
    resref: str
    restype: str
    source: str


@dataclass(frozen=True)
class _HydratedResource:
    record: _ResourceRecord
    data: bytes


@dataclass
class _ModuleState:
    name: str
    lyt: LYTLayout
    vis: VISData
    room_woks: dict[str, WOKData]
    room_geometry: dict[str, AuthoredRoomGeometry] = field(default_factory=dict)
    placements: AuthoredGameplayPlacement | None = None


def _repo_root_from_here() -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "native").is_dir() and (parent / "src").is_dir():
            return parent
    return path.parents[6]


def _load_module(module_name: str, path: Path) -> Any:
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _import_mdl_runtime() -> tuple[Any, Any]:
    try:
        from src.core.geometry import model_data as md  # type: ignore
        from src.core.mdl.mdl_writer import MDLBinaryWriter  # type: ignore

        return md, MDLBinaryWriter
    except Exception:
        repo = _repo_root_from_here()
        md = _load_module(
            "src.core.geometry.model_data",
            repo / "native" / "GhostRigger.Core.Math.vcxproj" / "Python" / "src" / "core" / "geometry" / "model_data.py",
        )
        writer_module = _load_module(
            "src.core.mdl.mdl_writer",
            repo / "src" / "core" / "mdl" / "mdl_writer.py",
        )
        return md, writer_module.MDLBinaryWriter


def _primitive_mesh_to_node(md: Any, mesh: PrimitiveMesh, parent: Any) -> Any:
    node = md.ModelNode(
        name=mesh.name,
        flags=int(md.NodeFlags.MESH),
        vertices=list(mesh.vertices),
        normals=list(mesh.normals or ((0.0, 0.0, 1.0),) * len(mesh.vertices)),
        uvs=list(mesh.uvs or ((0.0, 0.0),) * len(mesh.vertices)),
        faces=list(mesh.faces),
        face_mats=[0] * len(mesh.faces),
        texture=str(mesh.texture or ""),
        diffuse=mesh.diffuse,
        ambient=mesh.ambient,
        vertex_space=0,
    )
    node.parent = parent
    node.compute_bounds()
    return node


def _make_room_model_bytes(game: str, geometry: AuthoredRoomGeometry) -> tuple[bytes, bytes]:
    md, Writer = _import_mdl_runtime()
    root = md.ModelNode(name=geometry.room_resref, flags=int(md.NodeFlags.HEADER))
    root.children.append(_primitive_mesh_to_node(md, geometry.room_mesh, root))
    for helper_mesh in geometry.helper_meshes:
        root.children.append(_primitive_mesh_to_node(md, helper_mesh, root))
    model = md.KotorModel(
        name=geometry.room_resref,
        supermodel="NULL",
        classification="area",
        game_version=md.GameVersion.K2 if str(game).upper() == "K2" else md.GameVersion.K1,
        model_type=int(md.ModelClassification.EFFECT),
        root_node=root,
    )
    model.disable_fog = True
    model.compute_bounds()
    return Writer().write(model)


def _make_packaged(resref: str, restype: str, data: bytes, source: str) -> PackagedModuleResource:
    return PackagedModuleResource(resref=resref, restype=restype, data=data, source=source)


def _resource_summary(resources: dict[tuple[str, str], _HydratedResource]) -> list[AuthoredModuleResourceSummary]:
    return [
        AuthoredModuleResourceSummary(resref=resref, restype=restype, size=len(resource.data), source=resource.record.source)
        for (resref, restype), resource in sorted(resources.items())
    ]


def _entry_room_wok(project: AuthoredModuleProject, room_geometries: dict[str, AuthoredRoomGeometry]) -> tuple[str, WOKData | None]:
    room_names = [normalise_resref(room.room_resref) for room in project.rooms]
    if not room_names:
        return "", None
    entry = normalise_resref(project.placements.entry_point.area_resref)
    preferred = entry if entry in room_geometries else room_names[0]
    geometry = room_geometries.get(preferred)
    if geometry is None:
        return preferred, None
    return preferred, geometry.wok


def _path_anchors_from_walkability(placements: AuthoredGameplayPlacement, checks: Any) -> tuple[AuthoredPathAnchor, ...]:
    ok_labels = {str(getattr(check, "label", "")): bool(getattr(check, "ok", False)) for check in list(getattr(checks, "checks", ()) or ())}
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

    for index, creature in enumerate(placements.creatures):
        append_spatial_anchor("creature", index, creature)
    for index, door in enumerate(placements.doors):
        append_spatial_anchor("door", index, door)
    for index, trigger in enumerate(placements.triggers):
        append_spatial_anchor("trigger", index, trigger)
    for index, encounter in enumerate(placements.encounters):
        append_spatial_anchor("encounter", index, encounter)
    for index, placeable in enumerate(placements.placeables):
        append_spatial_anchor("placeable", index, placeable)
    for index, waypoint in enumerate(placements.waypoints):
        append_spatial_anchor("waypoint", index, waypoint)
    return tuple(anchors)


def _vec3_to_manifest(value: Any) -> list[float]:
    values = list(value or (0.0, 0.0, 0.0))
    while len(values) < 3:
        values.append(0.0)
    return [float(values[0]), float(values[1]), float(values[2])]


def _walkability_to_manifest(walkability: Any) -> dict[str, Any]:
    if walkability is None:
        return {
            "ok": False,
            "checks": [],
            "warnings": [],
            "blocking_issues": ["No walkability validation was run."],
        }
    return {
        "ok": bool(getattr(walkability, "ok", False)),
        "checks": [
            {
                "label": str(getattr(check, "label", "")),
                "position": _vec3_to_manifest(getattr(check, "position", (0.0, 0.0, 0.0))),
                "ok": bool(getattr(check, "ok", False)),
                "face_index": int(getattr(check, "face_index", -1)),
                "surface_id": int(getattr(check, "surface_id", -1)),
                "message": str(getattr(check, "message", "")),
            }
            for check in list(getattr(walkability, "checks", ()) or ())
        ],
        "warnings": list(getattr(walkability, "warnings", ()) or ()),
        "blocking_issues": list(getattr(walkability, "blocking_issues", ()) or ()),
    }


def _visibility_to_manifest(project: AuthoredModuleProject, layout: Any | None) -> dict[str, Any]:
    """Return a modder-facing VIS graph summary for export manifests."""

    room_names = [normalise_resref(room.room_resref) for room in tuple(project.rooms or ()) if normalise_resref(room.room_resref)]
    room_set = set(room_names)
    if layout is None:
        return {
            "source": "map_studio:authored:vis",
            "ready": False,
            "status": "Not compiled",
            "vis_resource": f"{project.module_root}.vis",
            "room_count": len(room_names),
            "vis_entry_count": 0,
            "link_count": 0,
            "cross_room_link_count": 0,
            "entries": [],
            "isolated_rooms": room_names if len(room_names) > 1 else [],
            "missing_targets": [],
            "warnings": [],
            "blocking_messages": ["VIS visibility resource was not compiled."],
            "fix_hint": "Resolve layout/VIS validation errors, then rebuild the module package.",
        }

    visibility_source = getattr(getattr(layout, "vis", None), "visibility", {}) or {}
    entries: list[dict[str, Any]] = []
    normalised_visibility: dict[str, list[str]] = {}
    missing_targets: list[dict[str, str]] = []
    for room_name in room_names:
        raw_targets = tuple(visibility_source.get(room_name, ()) or ())
        targets = []
        for raw_target in raw_targets:
            target = normalise_resref(raw_target)
            if not target or target in targets:
                continue
            targets.append(target)
            if target not in room_set:
                missing_targets.append({"room": room_name, "target": target})
        normalised_visibility[room_name] = targets
        entries.append({"room": room_name, "visible_rooms": list(targets)})

    isolated_rooms: list[str] = []
    if len(room_names) > 1:
        for room_name in room_names:
            outgoing = {target for target in normalised_visibility.get(room_name, ()) if target != room_name}
            incoming = {
                other_room
                for other_room, targets in normalised_visibility.items()
                if other_room != room_name and room_name in set(targets)
            }
            if not outgoing and not incoming:
                isolated_rooms.append(room_name)

    link_count = sum(len(targets) for targets in normalised_visibility.values())
    cross_room_link_count = sum(
        1
        for room_name, targets in normalised_visibility.items()
        for target in targets
        if target != room_name
    )
    warnings = list(getattr(layout, "warnings", ()) or ())
    if isolated_rooms:
        warnings.append(
            f"VIS graph has {len(isolated_rooms)} isolated room(s); add room visibility links before calling the module visually game-tested."
        )
    blocking_messages = [
        f"VIS room {item['room']} references missing room {item['target']}."
        for item in missing_targets
    ]
    ready = not missing_targets and not isolated_rooms
    if blocking_messages:
        status = f"Blocked: {len(blocking_messages)} broken VIS target(s)"
        fix_hint = "Remove missing VIS targets or add matching authored rooms."
    elif isolated_rooms:
        status = "Needs visibility links"
        fix_hint = "Link rooms that should see each other in the room visibility graph."
    else:
        status = "Ready"
        fix_hint = ""
    return {
        "source": "map_studio:authored:vis",
        "ready": ready,
        "status": status,
        "vis_resource": f"{project.module_root}.vis",
        "room_count": len(room_names),
        "vis_entry_count": len(normalised_visibility),
        "link_count": link_count,
        "cross_room_link_count": cross_room_link_count,
        "entries": entries,
        "isolated_rooms": isolated_rooms,
        "missing_targets": missing_targets,
        "warnings": warnings,
        "blocking_messages": blocking_messages,
        "fix_hint": fix_hint,
    }


def _lightmap_metadata(project: AuthoredModuleProject) -> dict[str, Any]:
    metadata = getattr(getattr(project, "metadata", None), "metadata", {})
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    source = metadata.get("lightmap")
    if source is None:
        source = metadata.get("lightmap_status")
    if isinstance(source, dict):
        return dict(source)
    if isinstance(source, str) and source.strip():
        return {"status": source.strip()}
    return {}


def _lightmap_rooms(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple, set)):
        values = tuple(value)
    else:
        values = ()
    return tuple(dict.fromkeys(normalise_resref(item) for item in values if normalise_resref(item)))


def _lighting_to_manifest(project: AuthoredModuleProject, room_lights: list[dict[str, Any]]) -> dict[str, Any]:
    """Return explicit lighting/lightmap proof state for export manifests."""

    room_resrefs = tuple(
        normalise_resref(getattr(room, "room_resref", ""))
        for room in tuple(project.rooms or ())
        if normalise_resref(getattr(room, "room_resref", ""))
    )
    lit_room_set = {
        normalise_resref(row.get("room_resref", ""))
        for row in room_lights
        if isinstance(row, dict) and normalise_resref(row.get("room_resref", ""))
    }
    rooms_with_lights = tuple(room for room in room_resrefs if room in lit_room_set)
    rooms_without_lights = tuple(room for room in room_resrefs if room not in lit_room_set)
    lightmap = _lightmap_metadata(project)
    raw_status = str(lightmap.get("status") or "not_started").strip().lower().replace("-", "_").replace(" ", "_")
    manifest_path = str(lightmap.get("manifest_path") or lightmap.get("path") or lightmap.get("proof_manifest_path") or "")
    lightmap_rooms = _lightmap_rooms(
        lightmap.get("rooms")
        or lightmap.get("baked_rooms")
        or lightmap.get("lightmapped_rooms")
        or lightmap.get("room_resrefs")
    )
    game_tested_lighting = bool(lightmap.get("game_tested") or raw_status in {"game_tested", "game_tested_lighting"})
    warnings: list[str] = []
    if rooms_without_lights and room_lights:
        warnings.append(f"{len(rooms_without_lights)} room(s) have no authored lights yet: {', '.join(rooms_without_lights)}.")
    if lightmap_rooms:
        missing_lightmap_rooms = tuple(room for room in room_resrefs if room not in set(lightmap_rooms))
        if missing_lightmap_rooms:
            warnings.append(f"Lightmap coverage is missing {len(missing_lightmap_rooms)} room(s): {', '.join(missing_lightmap_rooms)}.")

    if not room_resrefs:
        ready = False
        status = "Needs authored rooms"
        lightmap_status = "not_started"
        fix_hint = "Create authored rooms before planning room lights or lightmaps."
    elif game_tested_lighting:
        ready = True
        status = "Game-tested lighting"
        lightmap_status = "game_tested"
        fix_hint = "Keep the lighting proof manifest and in-game screenshot/video with the staged package."
    elif raw_status in {"baked", "export_candidate", "ready"} and manifest_path:
        ready = True
        status = "Lightmap export candidate"
        lightmap_status = "export_candidate"
        fix_hint = "Install the module and verify lighting/lightmap appearance in-game before calling it game-tested."
    elif room_lights:
        ready = False
        status = "Viewport lit only"
        lightmap_status = raw_status if raw_status != "not_started" else "viewport_lit_only"
        warnings.append(
            "Authored room lights are viewport/editor intent only until a baked lightmap manifest or in-game lighting proof is recorded."
        )
        fix_hint = "Bake or attach a lightmap manifest, then run an in-game lighting proof pass."
    else:
        ready = False
        status = "Lighting not planned"
        lightmap_status = raw_status
        warnings.append("No authored room lights or lightmap plan exists yet; viewport lighting is not game-tested module lighting.")
        fix_hint = "Add key/fill/ambient room lights and record lightmap planning before packaging a visual-quality map."

    return {
        "source": "map_studio:authored:lighting",
        "ready": ready,
        "status": status,
        "light_count": len(room_lights),
        "room_count": len(room_resrefs),
        "rooms_with_lights": list(rooms_with_lights),
        "rooms_without_lights": list(rooms_without_lights),
        "lightmap_status": lightmap_status,
        "lightmap_manifest_path": manifest_path,
        "lightmap_room_count": len(lightmap_rooms),
        "lightmap_rooms": list(lightmap_rooms),
        "game_tested_lighting": game_tested_lighting,
        "warnings": warnings,
        "fix_hint": fix_hint,
    }


def _positioned_expectations(kind: str, items: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(tuple(items or ())):
        if not hasattr(item, "position"):
            continue
        template = str(getattr(item, "template_resref", "") or "")
        tag = str(getattr(item, "tag", "") or "")
        rows.append(
            {
                "kind": kind,
                "index": index,
                "template_resref": template,
                "tag": tag,
                "label": f"{kind}:{tag or template or f'{kind}_{index + 1}'}",
                "position": _vec3_to_manifest(getattr(item, "position")),
                "bearing": float(getattr(item, "bearing", 0.0) or 0.0),
            }
        )
    return rows


def _template_dependency_rows(
    placements: AuthoredGameplayPlacement,
    *,
    packaged_keys: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    packaged = packaged_keys or set()
    rows: list[dict[str, Any]] = []
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
        for index, item in enumerate(items):
            resref = normalise_resource_resref(getattr(item, "template_resref", ""))
            if not resref:
                continue
            is_packaged = (resref, restype) in packaged
            rows.append(
                {
                    "kind": kind,
                    "index": index,
                    "template_resref": resref,
                    "restype": restype,
                    "tag": str(getattr(item, "tag", "") or ""),
                    "status": "packaged" if is_packaged else "external_or_base_game",
                    "packaged": is_packaged,
                    "required": True,
                    "message": (
                        f"{resref}.{restype} is included in this module package."
                        if is_packaged
                        else f"{resref}.{restype} must resolve from the base game, Override, or another installed mod."
                    ),
                }
            )
    return sorted(rows, key=lambda row: (row["kind"], row["template_resref"], row["restype"], row["tag"]))


def _smoke_expectations_from_build_parts(
    project: AuthoredModuleProject,
    *,
    walkability: dict[str, Any],
    pathing: dict[str, Any],
) -> dict[str, Any]:
    placements = project.placements
    expected_entry = {
        "label": "entry_point",
        "area_resref": placements.entry_point.area_resref,
        "position": _vec3_to_manifest(placements.entry_point.position),
        "facing": float(placements.entry_point.facing),
    }
    expected_placeables = _positioned_expectations("placeable", placements.placeables)
    expected_waypoints = _positioned_expectations("waypoint", placements.waypoints)
    project_metadata = dict(getattr(getattr(project, "metadata", None), "metadata", {}) or {})
    source_module = normalise_resource_resref(project_metadata.get("source_module_resref") or "")
    copied_from_base_game = bool(project_metadata.get("copied_from_base_game_module", False))
    inherited_content = bool(project_metadata.get("inherited_base_game_module_content", copied_from_base_game))
    content_origin = str(
        project_metadata.get("content_origin")
        or ("base_game_derived" if copied_from_base_game else "map_studio_original")
    )
    authored_original = content_origin == "map_studio_original" and not copied_from_base_game and not inherited_content
    expected_absent = {
        "base_game_module_geometry": bool(authored_original),
        "inherited_scripted_moving_test_objects": bool(authored_original),
        "forbidden_source_module_resrefs": ["PLCaa", "tar_m02aa"],
        "forbidden_object_descriptions": [
            "PLCaa scripted moving spheres",
            "PLCaa scripted moving cones",
            "PLCaa scripted moving rectangles",
            "Taris fallback room geometry",
        ],
    }
    return {
        "content_origin": content_origin,
        "authored_from_scratch": bool(authored_original),
        "copied_from_base_game_module": copied_from_base_game,
        "source_module_resref": source_module,
        "inherited_base_game_module_content": inherited_content,
        "source_identity": {
            "content_origin": content_origin,
            "authored_from_scratch": bool(authored_original),
            "copied_from_base_game_module": copied_from_base_game,
            "source_module_resref": source_module,
            "inherited_base_game_module_content": inherited_content,
        },
        "expected_entry_point": expected_entry,
        "expected_placeables": expected_placeables,
        "expected_waypoints": expected_waypoints,
        "expected_runtime_observations": {
            "player_start_area": expected_entry["area_resref"],
            "player_start_position": expected_entry["position"],
            "test_placeable_tags": [row["tag"] for row in expected_placeables if row["tag"]],
            "waypoint_tags": [row["tag"] for row in expected_waypoints if row["tag"]],
            "module_identity_resref": project.module_root,
            "no_inherited_base_game_geometry_or_scripted_movers": bool(authored_original),
        },
        "expected_absent_runtime_observations": expected_absent,
        "walkability": walkability,
        "all_walkability_checks_passed": bool(walkability.get("ok", False)),
        "pathing": pathing,
        "pathing_anchor_labels": list(pathing.get("anchor_labels", []) or []),
    }


def _placement_counts(placements: AuthoredGameplayPlacement) -> dict[str, int]:
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


def build_authored_module(project: AuthoredModuleProject, *, game_root_dir: str = "") -> AuthoredModuleBuild:
    """Compile authored module intent into in-memory runtime resources."""

    root = project.module_root
    room_geometries: dict[str, AuthoredRoomGeometry] = {}
    room_woks: dict[str, WOKData] = {}
    warnings: list[str] = []
    blocking: list[str] = []

    validation = validate_authored_module_project(project)
    warnings.extend(validation.warnings)
    blocking.extend(validation.blocking_issues)
    layout = None
    metadata = None
    pathing = None
    packaged: list[PackagedModuleResource] = []
    resources: dict[tuple[str, str], _HydratedResource] = {}

    try:
        layout = compile_authored_module_layout(project)
        warnings.extend(layout.warnings)
    except Exception as exc:
        blocking.append(f"Authored module layout could not be compiled: {exc}")

    for room in project.rooms:
        room_resref = room.normalised_resref()
        try:
            geometry = compile_authored_room_spec(room)
            geometry = apply_authored_walkmesh_boundary_policy_to_geometry(geometry)
        except Exception as exc:
            blocking.append(f"Room {room_resref or '(unnamed)'} geometry could not be compiled: {exc}")
            continue
        room_geometries[room_resref] = geometry
        room_woks[room_resref] = geometry.wok

    entry_room, entry_wok = _entry_room_wok(project, room_geometries)
    walkability = None
    if entry_wok is not None:
        walkability = validate_authored_gameplay_placement_against_walkmesh(project.placements, entry_wok)
        warnings.extend(walkability.warnings)
        blocking.extend(walkability.blocking_issues)
    elif project.rooms:
        blocking.append("Authored module export could not find a room WOK for gameplay walkability checks.")

    try:
        metadata = compile_authored_module_metadata(
            project.metadata,
            project.placements.entry_point,
            area=AuthoredAreaMetadata(
                name=project.metadata.display_name,
                tag=project.metadata.tag or root,
                comments="Generated by GhostRigger Map Studio authored module export.",
            ),
            room_resrefs=tuple(getattr(layout, "room_resrefs", ()) or tuple(room_geometries)),
            area_resrefs=(root,),
        )
        warnings.extend(metadata.validation.warnings)
        blocking.extend(metadata.validation.blocking_issues)
    except Exception as exc:
        blocking.append(f"Authored module metadata could not be compiled: {exc}")

    if entry_wok is not None:
        try:
            pathing = compile_authored_pathing_for_module(entry_wok, anchors=_path_anchors_from_walkability(project.placements, walkability))
            warnings.extend(pathing.validation.warnings)
            blocking.extend(pathing.validation.blocking_issues)
        except Exception as exc:
            blocking.append(f"Authored module pathing could not be compiled: {exc}")

    try:
        material_preflight = compile_authored_room_material_preflight(
            project.rooms[0].primitive.material.texture if hasattr(project.rooms[0].primitive, "material") else getattr(project.rooms[0].primitive, "texture", ""),
            game_root_dir=game_root_dir,
            require_game_resolution=False,
        )
        warnings.extend(material_preflight.warnings)
        blocking.extend(material_preflight.blocking_issues)
    except Exception as exc:
        warnings.append(f"Authored room material preflight could not run: {exc}")

    if metadata is not None:
        packaged.append(_make_packaged(root, "are", metadata.are_bytes, "map_studio:authored:are"))
        packaged.append(_make_packaged(ENGINE_MODULE_IFO_RESREF, "ifo", metadata.ifo_bytes, "map_studio:authored:ifo"))
    try:
        packaged.append(_make_packaged(root, "git", build_git_bytes(project.placements), "map_studio:authored:git"))
    except Exception as exc:
        blocking.append(f"Authored gameplay placements could not be compiled into GIT: {exc}")
    if pathing is not None:
        packaged.append(_make_packaged(root, "pth", pathing.pth_bytes, "map_studio:authored:pth"))
    for room_resref, geometry in room_geometries.items():
        try:
            mdl_bytes, mdx_bytes = _make_room_model_bytes(project.game, geometry)
        except Exception as exc:
            blocking.append(f"Room {room_resref}.mdl/.mdx could not be compiled: {exc}")
            continue
        packaged.append(_make_packaged(room_resref, "mdl", mdl_bytes, "map_studio:authored:room_model"))
        packaged.append(_make_packaged(room_resref, "mdx", mdx_bytes, "map_studio:authored:room_model"))

    if layout is not None:
        resources[(root, "lyt")] = _HydratedResource(_ResourceRecord(root, "lyt", "map_studio:authored:lyt"), layout.lyt.to_text().encode("latin-1"))
        resources[(root, "vis")] = _HydratedResource(_ResourceRecord(root, "vis", "map_studio:authored:vis"), layout.vis.to_text().encode("latin-1"))
    for room_resref, wok in room_woks.items():
        resources[(room_resref, "wok")] = _HydratedResource(_ResourceRecord(room_resref, "wok", "map_studio:authored:wok"), wok.to_bytes())
    for item in packaged:
        resources[item.key] = _HydratedResource(_ResourceRecord(item.key[0], item.key[1], item.source), bytes(item.data))

    module_state = _ModuleState(
        name=root,
        lyt=layout.lyt if layout is not None else LYTLayout(),
        vis=layout.vis if layout is not None else VISData(),
        room_woks=room_woks,
        room_geometry=room_geometries,
        placements=project.placements,
    )
    walkability_metadata = _walkability_to_manifest(walkability)
    pathing_metadata = dict(pathing.metadata) if pathing is not None else {}
    visibility_metadata = _visibility_to_manifest(project, layout)
    smoke_expectations = _smoke_expectations_from_build_parts(
        project,
        walkability=walkability_metadata,
        pathing=pathing_metadata,
    )
    room_lights = [authored_room_light_payload(light) for light in tuple(getattr(project, "lights", ()) or ())]
    lighting_metadata = _lighting_to_manifest(project, room_lights)
    packaged_keys = set(resources)
    template_dependencies = _template_dependency_rows(project.placements, packaged_keys=packaged_keys)
    packaged_template_count = sum(1 for row in template_dependencies if row["packaged"])
    external_template_count = len(template_dependencies) - packaged_template_count
    return AuthoredModuleBuild(
        module_root=root,
        game=project.game,
        module=module_state,
        project=project,
        resources=resources,
        packaged_resources=packaged,
        resource_summaries=_resource_summary(resources),
        warnings=warnings,
        blocking_issues=blocking,
        metadata={
            "source": "src.core.modules.authored_module_export",
            "entry_room": entry_room,
            "room_count": len(room_geometries),
            "resource_count": len(resources),
            "gameplay_counts": _placement_counts(project.placements),
            "gameplay_template_dependencies": template_dependencies,
            "gameplay_template_dependency_count": len(template_dependencies),
            "gameplay_packaged_template_dependency_count": packaged_template_count,
            "gameplay_external_template_dependency_count": external_template_count,
            "lighting_count": len(room_lights),
            "room_lights": room_lights,
            "lighting": lighting_metadata,
            "visibility": visibility_metadata,
            "walkability": walkability_metadata,
            "pathing": pathing_metadata,
            "smoke_expectations": smoke_expectations,
        },
    )


def _augment_authored_manifest(path: str, build: AuthoredModuleBuild, package_result: CustomModulePackResult, verification: DevModulePackageVerification | None) -> None:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    remaining_acceptance = [
        f"Install/copy {build.module_root}.mod into the KOTOR Modules folder.",
        f"Launch KOTOR and run 'warp {build.module_root}'.",
        "Confirm the module loads in-game without crashing or falling back to another area.",
        "Confirm the player appears on the generated floor, not in the void.",
        "Confirm authored test placeables and waypoints resolve as expected.",
        "Walk across the generated floor and confirm WOK/pathing behavior.",
        "Capture screenshot or video evidence and record it in the proof manifest.",
    ]
    smoke_contract = _authored_smoke_contract(build, verification)
    source_identity = dict(smoke_contract.get("source_identity") or {})
    data["map_studio_authored_module"] = {
        "task": "T2643",
        "module_root": build.module_root,
        "game": build.game,
        "content_origin": str(smoke_contract.get("content_origin") or source_identity.get("content_origin") or "map_studio_original"),
        "authored_from_scratch": bool(smoke_contract.get("authored_from_scratch", source_identity.get("authored_from_scratch", True))),
        "copied_from_base_game_module": bool(smoke_contract.get("copied_from_base_game_module", source_identity.get("copied_from_base_game_module", False))),
        "source_module_resref": str(smoke_contract.get("source_module_resref") or source_identity.get("source_module_resref") or ""),
        "inherited_base_game_module_content": bool(
            smoke_contract.get("inherited_base_game_module_content", source_identity.get("inherited_base_game_module_content", False))
        ),
        "source_identity": source_identity,
        "expected_absent_runtime_observations": dict(smoke_contract.get("expected_absent_runtime_observations") or {}),
        "capability_stage": "export_candidate",
        "game_tested": False,
        "warp_command": f"warp {build.module_root}",
        "rooms": [
            {
                "resref": resref,
                "wok_faces": len(getattr(geometry.wok, "faces", []) or []),
                "wok_walkable_faces": int(geometry.wok.walkable_face_count()) if hasattr(geometry.wok, "walkable_face_count") else 0,
                "wok_non_walk_faces": int(geometry.wok.non_walk_face_count()) if hasattr(geometry.wok, "non_walk_face_count") else 0,
                "model_nodes": 1 + len(geometry.helper_meshes),
                "texture": str(getattr(geometry.room_mesh, "texture", "") or ""),
                "floor_surface_id": int(getattr((list(getattr(geometry.wok, "faces", []) or []) or [None])[0], "surface", -1)),
                "walkmesh_boundary_wall_faces": int((geometry.metadata or {}).get("walkmesh_boundary_wall_faces") or 0),
            }
            for resref, geometry in sorted(build.module.room_geometry.items())
        ],
        "gameplay_counts": _placement_counts(build.project.placements),
        "gameplay_template_dependencies": list(build.metadata.get("gameplay_template_dependencies", []) or []),
        "gameplay_template_dependency_count": int(build.metadata.get("gameplay_template_dependency_count", 0) or 0),
        "gameplay_packaged_template_dependency_count": int(build.metadata.get("gameplay_packaged_template_dependency_count", 0) or 0),
        "gameplay_external_template_dependency_count": int(build.metadata.get("gameplay_external_template_dependency_count", 0) or 0),
        "lighting_count": int(build.metadata.get("lighting_count", 0) or 0),
        "room_lights": list(build.metadata.get("room_lights", []) or []),
        "lighting": dict(build.metadata.get("lighting", {}) or {}),
        "visibility": dict(build.metadata.get("visibility", {}) or {}),
        "walkability": dict(build.metadata.get("walkability", {})),
        "pathing": dict(build.metadata.get("pathing", {})),
        "smoke_expectations": dict(build.metadata.get("smoke_expectations", {})),
        "resources": [summary.__dict__ for summary in build.resource_summaries],
        "package_ok": bool(package_result.ok),
        "package_verification": _verification_to_manifest(verification),
        "readback": {
            "ok": bool(verification.ok) if verification is not None else False,
            "code": verification.code if verification is not None else "not_verified",
            "message": verification.message if verification is not None else "",
            "resources": [
                {
                    "resref": resource.resref,
                    "restype": resource.restype,
                    "size": resource.size,
                    "offset": resource.offset,
                }
                for resource in (verification.resources if verification is not None else [])
            ],
            "blocking_issues": list(verification.blocking_issues) if verification is not None else [],
        },
        "t2601_smoke_contract": smoke_contract,
        "modder_test_plan": _authored_modder_test_plan(
            smoke_contract=smoke_contract,
            module_path=package_result.module_path,
        ),
        "required_runtime_resources": smoke_contract["required_resources"],
        "manual_game_test_required": [
            f"Copy/install {build.module_root}.mod into the KOTOR Modules folder.",
            f"Start KOTOR and run 'warp {build.module_root}'.",
            "Confirm the room loads, player start works, and authored gameplay templates resolve.",
        ],
        "remaining_acceptance": remaining_acceptance,
    }
    data["validation"]["warnings"] = sorted(set(list(data.get("validation", {}).get("warnings", [])) + build.warnings + package_result.warnings))
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def export_authored_module_project(request: AuthoredModuleExportRequest) -> AuthoredModuleExportResult:
    """Export the current authored Map Studio project through the MOD packager."""

    build = build_authored_module(request.project, game_root_dir=request.game_root_dir)
    room_resrefs = tuple(sorted(build.module.room_geometry))
    if build.blocking_issues and request.strict:
        return AuthoredModuleExportResult(
            ok=False,
            module_root=build.module_root,
            room_resrefs=room_resrefs,
            resources=build.resource_summaries,
            warnings=build.warnings,
            blocking_issues=build.blocking_issues,
            metadata=dict(build.metadata),
            message=f"Authored Map Studio module preflight found {len(build.blocking_issues)} blocking issue(s).",
            code="preflight_failed",
        )
    if request.dry_run:
        return AuthoredModuleExportResult(
            ok=not build.blocking_issues,
            module_root=build.module_root,
            room_resrefs=room_resrefs,
            resources=build.resource_summaries,
            warnings=build.warnings + ["Dry run only; no MOD package was written."],
            blocking_issues=build.blocking_issues,
            metadata=dict(build.metadata),
            message=(
                f"Authored Map Studio module dry run passed for {build.module_root}."
                if not build.blocking_issues
                else f"Authored Map Studio module dry run found {len(build.blocking_issues)} blocking issue(s)."
            ),
            code="dry_run_passed" if not build.blocking_issues else "dry_run_failed",
        )

    pack_request = CustomModulePackRequest(
        module_root=build.module_root,
        game=build.game,
        output_dir=request.output_dir,
        archive_mode="mod",
        create_backups=request.create_backups,
        write_loose_resources=request.write_loose_resources,
        include_reference_check=request.include_reference_check,
        include_wok_check=request.include_wok_check,
        strict=request.strict,
    )
    package_result = package_custom_module(
        build,
        pack_request,
        resources=build.packaged_resources,
        now=datetime.now(timezone.utc),
    )
    verification = None
    if package_result.ok and package_result.module_path and room_resrefs:
        verification = verify_dev_test_module_package(
            package_result.module_path,
            expected_module_root=build.module_root,
            expected_room_resref=room_resrefs[0],
            game=build.game,
        )
    _augment_authored_manifest(package_result.manifest_path, build, package_result, verification)
    verification_warnings = list(verification.warnings) if verification is not None else []
    verification_blocking = list(verification.blocking_issues) if verification is not None else []
    ok = package_result.ok and (verification.ok if verification is not None else True)
    return AuthoredModuleExportResult(
        ok=ok,
        module_root=build.module_root,
        room_resrefs=room_resrefs,
        module_path=package_result.module_path,
        manifest_path=package_result.manifest_path,
        package_result=package_result,
        package_verification=verification,
        resources=build.resource_summaries,
        warnings=build.warnings + package_result.warnings + verification_warnings,
        blocking_issues=build.blocking_issues + package_result.blocking_issues + verification_blocking,
        metadata=dict(build.metadata),
        message=(
            f"Authored Map Studio module exported: {package_result.module_path}"
            if ok
            else package_result.message
        ),
        code="export_candidate" if ok else (verification.code if verification is not None and not verification.ok else package_result.code),
    )


def _next_install_backup_path(path: Path) -> Path:
    candidate = path.with_suffix(path.suffix + ".bak")
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = path.with_suffix(path.suffix + f".bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _verification_to_manifest(verification: DevModulePackageVerification | None) -> dict[str, Any]:
    if verification is None:
        return {"ok": False, "code": "not_verified"}
    return {
        "ok": verification.ok,
        "code": verification.code,
        "message": verification.message,
        "parsed_gff": list(verification.parsed_gff),
        "parsed_wok": list(verification.parsed_wok),
        "model_pairs": list(verification.model_pairs),
        "path_point_count": verification.path_point_count,
        "path_connection_count": verification.path_connection_count,
        "resources": [
            {
                "resref": resource.resref,
                "restype": resource.restype,
                "size": resource.size,
                "offset": resource.offset,
            }
            for resource in verification.resources
        ],
        "warnings": list(verification.warnings),
        "blocking_issues": list(verification.blocking_issues),
    }


def _authored_required_resource_rows(module_root: str, room_resrefs: tuple[str, ...]) -> list[dict[str, str]]:
    rows = [
        (module_root, "are", "Area metadata"),
        (module_root, "git", "Gameplay instances"),
        (ENGINE_MODULE_IFO_RESREF, "ifo", "Module entry metadata"),
        (module_root, "pth", "Path graph"),
        (module_root, "lyt", "Room layout"),
        (module_root, "vis", "Room visibility"),
    ]
    for room in room_resrefs:
        rows.extend(
            [
                (room, "wok", "Walkmesh"),
                (room, "mdl", "Room model"),
                (room, "mdx", "Room vertex data"),
            ]
        )
    return [
        {
            "resref": resref,
            "restype": restype,
            "filename": f"{resref}.{restype}",
            "purpose": purpose,
        }
        for resref, restype, purpose in rows
    ]


def _authored_smoke_contract_from_parts(
    *,
    module_root: str,
    room_resrefs: tuple[str, ...],
    built_resources: set[tuple[str, str]],
    verification: DevModulePackageVerification | None,
    capability_stage: str = "export_candidate",
    game_tested: bool = False,
) -> dict[str, Any]:
    verified = {
        (resource.resref, resource.restype)
        for resource in (verification.resources if verification is not None else ())
    }
    available = verified or built_resources
    required = _authored_required_resource_rows(module_root, room_resrefs)
    required_with_status = [
        dict(row, present=(row["resref"], row["restype"]) in available)
        for row in required
    ]
    missing = [row["filename"] for row in required_with_status if not row["present"]]
    return {
        "task": "T2601",
        "module_root": module_root,
        "warp_command": f"warp {module_root}",
        "capability_stage": capability_stage,
        "required_resources": required_with_status,
        "all_required_resources_present": not missing,
        "missing_required_resources": missing,
        "pre_game_package_readback_ok": bool(verification.ok) if verification is not None else False,
        "in_game_acceptance_checks": _authored_acceptance_checks(),
        "proof_required": not game_tested,
        "game_tested": game_tested,
    }


def _authored_smoke_contract(build: AuthoredModuleBuild, verification: DevModulePackageVerification | None) -> dict[str, Any]:
    contract = _authored_smoke_contract_from_parts(
        module_root=build.module_root,
        room_resrefs=tuple(sorted(build.module.room_geometry)),
        built_resources={(summary.resref, summary.restype) for summary in build.resource_summaries},
        verification=verification,
    )
    expectations = build.metadata.get("smoke_expectations")
    if isinstance(expectations, dict):
        contract.update(expectations)
    contract["in_game_acceptance_checks"] = _authored_acceptance_checks(
        include_test_placeable=bool(contract.get("expected_placeables"))
    )
    return contract


def _authored_smoke_contract_from_export_result(export_result: AuthoredModuleExportResult) -> dict[str, Any]:
    module_root = export_result.module_root or "authored"
    contract = _authored_smoke_contract_from_parts(
        module_root=module_root,
        room_resrefs=tuple(export_result.room_resrefs),
        built_resources={(summary.resref, summary.restype) for summary in export_result.resources},
        verification=export_result.package_verification,
        capability_stage="export_candidate" if export_result.ok else "export_blocked",
    )
    expectations = export_result.metadata.get("smoke_expectations")
    if isinstance(expectations, dict):
        contract.update(expectations)
    contract["in_game_acceptance_checks"] = _authored_acceptance_checks(
        include_test_placeable=bool(contract.get("expected_placeables"))
    )
    return contract


def authored_module_smoke_summary_lines(export_result: AuthoredModuleExportResult) -> list[str]:
    """Return concise modder-facing smoke-test expectations for a staged module."""

    contract = _authored_smoke_contract_from_export_result(export_result)
    lines = [f"Smoke test: run `{contract['warp_command']}` in the matching KOTOR game."]
    entry = contract.get("expected_entry_point")
    if isinstance(entry, dict):
        position = entry.get("position", [])
        area = str(entry.get("area_resref") or contract.get("module_root") or "")
        if len(position) >= 3:
            lines.append(
                "Expected player start: "
                f"{area} at ({float(position[0]):.2f}, {float(position[1]):.2f}, {float(position[2]):.2f})."
            )
    placeables = [row for row in contract.get("expected_placeables", []) if isinstance(row, dict)]
    if placeables:
        labels = []
        for row in placeables:
            position = _vec3_to_manifest(row.get("position", (0.0, 0.0, 0.0)))
            labels.append(
                f"{row.get('tag') or row.get('template_resref')} @ "
                f"({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})"
            )
        lines.append(f"Expected placeable(s): {', '.join(labels)}.")
    walkability = contract.get("walkability")
    if isinstance(walkability, dict):
        checks = [row for row in walkability.get("checks", []) if isinstance(row, dict)]
        passed = sum(1 for row in checks if row.get("ok"))
        if checks:
            lines.append(f"Walkability preflight: {passed}/{len(checks)} gameplay anchor(s) on generated WOK.")
    anchors = list(contract.get("pathing_anchor_labels") or [])
    if anchors:
        shown = ", ".join(str(label) for label in anchors[:8])
        suffix = "" if len(anchors) <= 8 else f", +{len(anchors) - 8} more"
        lines.append(f"Pathing anchors: {shown}{suffix}.")
    if contract.get("game_tested"):
        lines.append("Capability: game-smoke-tested.")
    else:
        lines.append("Capability: export candidate; in-game screenshot/video proof is still required.")
    return lines


def _authored_game_test_steps(module_root: str, *, include_test_placeable: bool = True) -> list[str]:
    steps = [
        f"Install/copy `{module_root}.mod` into the selected KOTOR `Modules` folder.",
        "Launch the matching KOTOR game.",
        f"Open the console and run `warp {module_root}`.",
        "Confirm the module loads without crashing or falling back to another area.",
        f"Confirm the area identity is the authored `{module_root}` smoke map, not a copied Taris/PLCaa/base-game module.",
        "Confirm the player appears on the generated floor, not in the void.",
    ]
    if include_test_placeable:
        steps.append("Confirm the authored test placeable appears near the expected location.")
    steps.extend(
        [
            "Walk across the generated floor and confirm movement is not blocked unexpectedly.",
            "Confirm there are no inherited PLCaa scripted moving spheres, cones, rectangles, or other base-game test-room movers.",
            "Capture a screenshot or short clip as proof.",
        ]
    )
    return steps


def _authored_acceptance_checks(*, include_test_placeable: bool = True) -> list[str]:
    checks = [
        "module_loads_in_game",
        "module_identity_matches_authored_resref",
        "player_spawns_on_floor",
    ]
    if include_test_placeable:
        checks.append("test_placeable_visible")
    checks.extend(
        [
            "player_can_walk_on_floor",
            "no_inherited_base_game_geometry_or_scripted_movers",
            "screenshot_or_video_captured",
        ]
    )
    return checks


def _authored_modder_test_plan(
    *,
    smoke_contract: dict[str, Any],
    module_path: str = "",
    install_path: str = "",
    proof_manifest_path: str = "",
    evidence_path: str = "",
    accepted: bool = False,
    missing_checks: list[str] | None = None,
    dry_run: bool = False,
    installed: bool = False,
) -> dict[str, Any]:
    """Build the durable game-proof checklist consumed by UI and scripts."""

    acceptance_checks = list(smoke_contract.get("in_game_acceptance_checks") or _authored_acceptance_checks())
    missing = list(missing_checks if missing_checks is not None else ([] if accepted else acceptance_checks))
    if accepted:
        capability_stage = "game_smoke_tested"
        proof_state = "game_smoke_tested"
    elif installed:
        capability_stage = "installed_test_build"
        proof_state = "installed_requires_live_warp_proof"
    else:
        capability_stage = str(smoke_contract.get("capability_stage") or "export_candidate")
        proof_state = "requires_live_warp_proof"
    return {
        "task": "T2605",
        "module_root": str(smoke_contract.get("module_root") or ""),
        "capability_stage": capability_stage,
        "game_ready": bool(accepted),
        "proof_state": proof_state,
        "warp_command": str(smoke_contract.get("warp_command") or ""),
        "module_path": module_path,
        "install": {
            "installed_module_path": install_path,
            "installed": bool(installed),
            "dry_run": bool(dry_run),
            "proof_manifest_path": proof_manifest_path,
        },
        "required_resources": list(smoke_contract.get("required_resources") or ()),
        "missing_required_resources": list(smoke_contract.get("missing_required_resources") or ()),
        "expected_runtime_observations": dict(smoke_contract.get("expected_runtime_observations") or {}),
        "expected_absent_runtime_observations": dict(smoke_contract.get("expected_absent_runtime_observations") or {}),
        "expected_entry_point": dict(smoke_contract.get("expected_entry_point") or {}),
        "expected_placeables": list(smoke_contract.get("expected_placeables") or ()),
        "expected_waypoints": list(smoke_contract.get("expected_waypoints") or ()),
        "walkability": dict(smoke_contract.get("walkability") or {}),
        "pathing_anchor_labels": list(smoke_contract.get("pathing_anchor_labels") or ()),
        "acceptance_checks": acceptance_checks,
        "missing_acceptance_checks": missing,
        "evidence": {
            "required": not bool(accepted),
            "path": evidence_path,
            "accepted_kinds": ["screenshot", "video"],
        },
        "modder_next_step": (
            "Keep the proof manifest and screenshot/video with the package."
            if accepted
            else "Install the staged .mod, warp into the module, verify every acceptance check, then record screenshot/video proof."
        ),
    }


def _authored_game_executable_name(game: str) -> str:
    return "swkotor2.exe" if str(game or "").upper() == "K2" else "swkotor.exe"


def _derive_game_root_dir_from_modules_dir(modules_dir_text: str) -> str:
    if not modules_dir_text:
        return ""
    modules_dir = Path(modules_dir_text)
    return str(modules_dir.parent)


def _files_have_same_bytes(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def _check_currentgame_module_cache(
    *,
    game_root_dir: str,
    module_root: str,
    module_path: str,
    warnings: list[str],
    blocking: list[str],
) -> None:
    if not game_root_dir or not module_root or not module_path:
        return
    cache_path = Path(game_root_dir) / "currentgame" / f"{module_root}.mod"
    if not cache_path.is_file():
        return
    package_path = Path(module_path)
    if package_path.is_file() and _files_have_same_bytes(cache_path, package_path):
        warnings.append(
            f"KOTOR currentgame already contains {cache_path.name}; restart from a clean save if warp testing behaves strangely."
        )
        return
    blocking.append(
        "KOTOR currentgame cache contains a stale "
        f"{cache_path.name}. Quit KOTOR and move or delete {cache_path} before retesting warp {module_root}."
    )


def _refresh_currentgame_module_cache(
    *,
    game_root_dir: str,
    module_root: str,
    installed_module_path: str,
    warnings: list[str],
) -> None:
    if not game_root_dir or not module_root or not installed_module_path:
        return
    cache_path = Path(game_root_dir) / "currentgame" / f"{module_root}.mod"
    if not cache_path.is_file():
        return
    installed_path = Path(installed_module_path)
    if installed_path.is_file() and _files_have_same_bytes(cache_path, installed_path):
        warnings.append(
            f"KOTOR currentgame already contains the installed {cache_path.name}; restart from a clean save if warp testing behaves strangely."
        )
        return
    backup = _next_install_backup_path(cache_path)
    shutil.copy2(cache_path, backup)
    shutil.copy2(installed_path, cache_path)
    warnings.append(f"Refreshed stale KOTOR currentgame cache {cache_path.name}; backup written to {backup}.")


def _authored_launch_helper_command(*, proof_manifest_path: Path, game: str, game_root_dir: str) -> str:
    if not game_root_dir:
        return ""
    return (
        "python scripts/launch_grdev01_smoke_test.py "
        f'--proof-manifest "{proof_manifest_path}" '
        f'--game "{str(game or "K1").upper()}" '
        f'--game-root-dir "{game_root_dir}" '
        "--dry-run"
    )


def _powershell_single_quoted(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _write_authored_elevated_launch_script(
    *,
    output_root: Path,
    module_root: str,
    game: str,
    game_root_dir: str,
    proof_manifest_path: Path,
) -> str:
    if not game_root_dir:
        return ""
    executable = Path(game_root_dir) / _authored_game_executable_name(game)
    script_path = output_root / f"{module_root}_launch_kotor_as_admin.cmd"
    ps_command = (
        "Start-Process "
        f"-FilePath {_powershell_single_quoted(executable)} "
        f"-WorkingDirectory {_powershell_single_quoted(game_root_dir)} "
        "-Verb RunAs"
    )
    lines = [
        "@echo off",
        "setlocal",
        f"echo GhostRigger authored module smoke test: {module_root}",
        f"echo Expected module package is installed in: {Path(game_root_dir) / 'Modules'}",
        f"echo This helper starts KOTOR with Windows elevation, then you must run: warp {module_root}",
        f"echo Proof manifest: {proof_manifest_path}",
        "echo.",
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_command}"',
        "if errorlevel 1 (",
        "  echo KOTOR did not launch. Start it manually as administrator and keep using this checklist.",
        "  pause",
        "  exit /b 1",
        ")",
        "echo.",
        f"echo After KOTOR opens, load a save, open the console, and run: warp {module_root}",
        "echo Capture screenshot/video evidence, then record proof with GhostRigger's proof recorder.",
        "pause",
    ]
    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(script_path)


def _record_proof_script_path() -> str:
    current = Path(__file__).resolve()
    for parent in current.parents:
        script_path = parent / "scripts" / "record_authored_module_game_proof.py"
        if script_path.is_file():
            return str(script_path)
    return "scripts\\record_authored_module_game_proof.py"


def _capture_grdev01_evidence_script_path() -> str:
    current = Path(__file__).resolve()
    for parent in current.parents:
        script_path = parent / "scripts" / "capture_grdev01_smoke_evidence.py"
        if script_path.is_file():
            return str(script_path)
    return "scripts\\capture_grdev01_smoke_evidence.py"


def _capture_evidence_command(*, proof_manifest_path: Path, module_root: str, include_test_placeable: bool = True) -> str:
    if module_root.lower() != "grdev01":
        return ""
    capture_path = _capture_grdev01_evidence_script_path()
    flags = [
        "--kotor-window-only",
        "--record-proof",
        "--module-loads-in-game",
        "--module-identity-matches-authored-resref",
        "--player-spawns-on-floor",
    ]
    if include_test_placeable:
        flags.append("--test-placeable-visible")
    flags.append("--player-can-walk-on-floor")
    flags.append("--no-inherited-base-game-geometry-or-scripted-movers")
    return f'python "{capture_path}" --proof-manifest "{proof_manifest_path}" ' + " ".join(flags)


def _write_authored_proof_recording_script(
    *,
    output_root: Path,
    module_root: str,
    proof_manifest_path: Path,
    include_test_placeable: bool = True,
) -> str:
    script_path = output_root / f"{module_root}_record_game_proof.cmd"
    recorder_path = _record_proof_script_path()
    proof_path = proof_manifest_path.resolve()
    placeable_text = "the authored placeable is visible, " if include_test_placeable else ""
    placeable_flag = "--test-placeable-visible " if include_test_placeable else ""
    lines = [
        "@echo off",
        "setlocal",
        f"echo GhostRigger authored module proof recorder: {module_root}",
        f"echo Proof manifest: {proof_path}",
        "echo.",
        f"echo Run this only after KOTOR has loaded the module with: warp {module_root}",
        f"echo Confirm the module identity is {module_root}, the player spawns on the generated floor, {placeable_text}walking works, and no PLCaa/base-game scripted movers are present.",
        "echo.",
        "set /p EVIDENCE=Drag or paste screenshot/video evidence path here, then press Enter: ",
        "set \"EVIDENCE=%EVIDENCE:\"=%\"",
        "if \"%EVIDENCE%\"==\"\" (",
        "  echo No evidence path supplied. Proof was not recorded.",
        "  pause",
        "  exit /b 1",
        ")",
        (
            f'python "{recorder_path}" --proof-manifest "{proof_path}" '
            '--evidence "%EVIDENCE%" --tester "%USERNAME%" '
            "--module-loads-in-game --module-identity-matches-authored-resref --player-spawns-on-floor "
            f"{placeable_flag}--player-can-walk-on-floor --no-inherited-base-game-geometry-or-scripted-movers"
        ),
        "if errorlevel 1 (",
        "  echo Proof recording did not complete. Check the message above.",
        "  pause",
        "  exit /b 1",
        ")",
        "echo.",
        "echo Proof recorded. Keep the evidence file with the packaged module.",
        "pause",
    ]
    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(script_path)


def _write_authored_install_proof_files(
    *,
    output_root: Path,
    export_result: AuthoredModuleExportResult,
    game: str,
    install_path: str,
    backup_path: str,
    modules_dir: str,
    game_root_dir: str,
    installed: bool,
    dry_run: bool,
    warnings: list[str],
    blocking: list[str],
) -> tuple[str, str, str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    module_root = export_result.module_root or "authored"
    smoke_contract = _authored_smoke_contract_from_export_result(export_result)
    include_test_placeable = bool(smoke_contract.get("expected_placeables"))
    checklist_path = output_root / f"{module_root}_authored_module_game_checklist.md"
    proof_manifest_path = output_root / f"{module_root}_authored_module_game_manifest.json"
    steps = _authored_game_test_steps(module_root, include_test_placeable=include_test_placeable)
    executable_name = _authored_game_executable_name(game)
    executable_path = str(Path(game_root_dir) / executable_name) if game_root_dir else executable_name
    launch_helper_command = _authored_launch_helper_command(
        proof_manifest_path=proof_manifest_path,
        game=game,
        game_root_dir=game_root_dir,
    )
    elevated_launch_script_path = _write_authored_elevated_launch_script(
        output_root=output_root,
        module_root=module_root,
        game=game,
        game_root_dir=game_root_dir,
        proof_manifest_path=proof_manifest_path,
    )
    proof_recording_script_path = _write_authored_proof_recording_script(
        output_root=output_root,
        module_root=module_root,
        proof_manifest_path=proof_manifest_path,
        include_test_placeable=include_test_placeable,
    )
    capture_evidence_command = _capture_evidence_command(
        proof_manifest_path=proof_manifest_path,
        module_root=module_root,
        include_test_placeable=include_test_placeable,
    )
    checklist_lines = [
        f"# {module_root} Authored Module In-Game Test",
        "",
        "This checklist is the manual proof gate for authored Map Studio modules. The module is not game-tested until these boxes are checked from an actual KOTOR run.",
        "",
        f"- Package: `{export_result.module_path}`",
        f"- Install target: `{install_path or '(not installed)'}`",
        f"- Previous module backup: `{backup_path or '(none)'}`",
        f"- Game root: `{game_root_dir or '(not supplied)'}`",
        f"- Expected executable: `{executable_path}`",
        f"- Dry-run helper: `{launch_helper_command or '(manual launch)'}`",
        f"- Elevated launch helper: `{elevated_launch_script_path or '(not written)'}`",
        f"- Evidence capture helper: `{capture_evidence_command or '(manual screenshot/video capture)'}`",
        f"- Proof recorder: `{proof_recording_script_path}`",
        f"- Warp command: `warp {module_root}`",
        "",
        "## Steps",
        "",
    ]
    checklist_lines.extend(f"- [ ] {step}" for step in steps)
    checklist_lines.extend(
        [
            "",
            "## Evidence",
            "",
            "- Screenshot/video path:",
            "- Tester:",
            "- Game/version:",
            "- Result:",
            "",
        ]
    )
    checklist_path.write_text("\n".join(checklist_lines), encoding="utf-8")
    modder_test_plan = _authored_modder_test_plan(
        smoke_contract=smoke_contract,
        module_path=export_result.module_path,
        install_path=install_path,
        proof_manifest_path=str(proof_manifest_path),
        dry_run=dry_run,
        installed=installed,
    )
    proof_manifest = {
        "task": "T2644",
        "module_root": module_root,
        "game": str(game or "K1").upper(),
        "capability_stage": modder_test_plan["capability_stage"],
        "proof_state": modder_test_plan["proof_state"],
        "package": {
            "module_path": export_result.module_path,
            "pack_manifest_path": export_result.manifest_path,
            "verification": _verification_to_manifest(export_result.package_verification),
        },
        "install": {
            "installed": installed,
            "dry_run": dry_run,
            "installed_module_path": install_path,
            "backup_module_path": backup_path,
        },
        "manual_proof_required": True,
        "game_tested": False,
        "warp_command": f"warp {module_root}",
        "launch_handoff": {
            "game": str(game or "").upper() or "K1",
            "resolved_modules_dir": modules_dir,
            "resolved_game_root_dir": game_root_dir,
            "expected_executable_path": executable_path,
            "launch_helper_command": launch_helper_command,
            "elevated_launch_script_path": elevated_launch_script_path,
            "evidence_capture_command": capture_evidence_command,
            "proof_recording_script_path": proof_recording_script_path,
            "dry_run_first": bool(launch_helper_command),
            "warp_command": f"warp {module_root}",
        },
        "acceptance_checks": list(smoke_contract.get("in_game_acceptance_checks") or ()),
        "modder_test_plan": modder_test_plan,
        "t2601_smoke_contract": smoke_contract,
        "steps": steps,
        "warnings": warnings,
        "blocking_issues": blocking,
    }
    proof_manifest_path.write_text(json.dumps(proof_manifest, indent=2), encoding="utf-8")
    return str(checklist_path), str(proof_manifest_path), elevated_launch_script_path, proof_recording_script_path


def _install_prep_export_request(request: AuthoredModuleInstallPrepRequest) -> AuthoredModuleExportRequest:
    if request.export_request is not None:
        return AuthoredModuleExportRequest(
            project=request.export_request.project,
            output_dir=request.export_request.output_dir or request.output_dir,
            include_reference_check=request.export_request.include_reference_check,
            include_wok_check=request.export_request.include_wok_check,
            include_game_template_check=request.export_request.include_game_template_check,
            game_root_dir=request.export_request.game_root_dir,
            strict=request.export_request.strict,
            dry_run=False,
            create_backups=request.export_request.create_backups,
            write_loose_resources=request.export_request.write_loose_resources,
        )
    return AuthoredModuleExportRequest(
        project=request.project,
        output_dir=request.output_dir,
        game_root_dir=request.game_root_dir,
        strict=True,
        dry_run=False,
    )


def prepare_authored_module_install(request: AuthoredModuleInstallPrepRequest) -> AuthoredModuleInstallPrepResult:
    """Safely stage an authored KMAP module for a manual in-game warp test."""

    export_request = _install_prep_export_request(request)
    export_result = export_authored_module_project(export_request)
    output_root = Path(export_request.output_dir or request.output_dir or ".")
    warnings = list(export_result.warnings)
    blocking = list(export_result.blocking_issues)
    installed = False
    install_path = ""
    backup_path = ""
    modules_dir_text = request.game_modules_dir
    resolved_game_root_dir = request.game_root_dir
    if not modules_dir_text and request.auto_detect_game_modules_dir:
        modules_dir_text = discover_kotor_modules_dir(
            request.project.game,
            game_root_dir=request.game_root_dir,
            settings_path=request.settings_path,
        )
        if modules_dir_text:
            warnings.append(f"Auto-detected KOTOR Modules folder: {modules_dir_text}")
        else:
            warnings.append("Could not auto-detect a KOTOR Modules folder; package is staged for manual install.")
    if not resolved_game_root_dir and modules_dir_text:
        resolved_game_root_dir = _derive_game_root_dir_from_modules_dir(modules_dir_text)
    if not export_result.ok:
        blocking.append(export_result.message or "Authored module export failed.")
    else:
        if not modules_dir_text or request.dry_run:
            _check_currentgame_module_cache(
                game_root_dir=resolved_game_root_dir,
                module_root=export_result.module_root,
                module_path=export_result.module_path,
                warnings=warnings,
                blocking=blocking,
            )
        if blocking:
            pass
        elif not modules_dir_text:
            warnings.append("No KOTOR Modules folder was supplied; package is staged but not installed for game testing.")
        else:
            modules_dir = Path(modules_dir_text)
            if not modules_dir.is_dir():
                blocking.append(f"KOTOR Modules folder does not exist: {modules_dir}")
            else:
                destination = modules_dir / f"{export_result.module_root}.mod"
                install_path = str(destination)
                if destination.exists() and not request.overwrite:
                    blocking.append(f"{destination} already exists. Re-run with overwrite=True to replace it.")
                elif request.dry_run:
                    warnings.append(f"Dry run: would copy {export_result.module_path} to {destination}.")
                else:
                    if destination.exists():
                        backup = _next_install_backup_path(destination)
                        shutil.copy2(destination, backup)
                        backup_path = str(backup)
                        warnings.append(f"Backed up existing {destination.name} to {backup}.")
                    shutil.copy2(export_result.module_path, destination)
                    installed = True
                    _refresh_currentgame_module_cache(
                        game_root_dir=resolved_game_root_dir,
                        module_root=export_result.module_root,
                        installed_module_path=str(destination),
                        warnings=warnings,
                    )

    checklist_path, proof_manifest_path, elevated_launch_script_path, proof_recording_script_path = _write_authored_install_proof_files(
        output_root=output_root,
        export_result=export_result,
        game=request.project.game,
        install_path=install_path,
        backup_path=backup_path,
        modules_dir=modules_dir_text,
        game_root_dir=resolved_game_root_dir,
        installed=installed,
        dry_run=request.dry_run,
        warnings=warnings,
        blocking=blocking,
    )
    launch_helper_command = _authored_launch_helper_command(
        proof_manifest_path=Path(proof_manifest_path),
        game=request.project.game,
        game_root_dir=resolved_game_root_dir,
    )
    ok = export_result.ok and not blocking and (installed or request.dry_run or not request.game_modules_dir)
    code = "installed" if installed else "staged_for_manual_install"
    if request.dry_run and not blocking:
        code = "dry_run"
    if blocking:
        code = "install_preflight_failed"
    return AuthoredModuleInstallPrepResult(
        ok=ok,
        export_result=export_result,
        installed_module_path=install_path if installed else "",
        backup_module_path=backup_path,
        resolved_modules_dir=modules_dir_text,
        resolved_game_root_dir=resolved_game_root_dir,
        launch_helper_command=launch_helper_command,
        elevated_launch_script_path=elevated_launch_script_path,
        proof_recording_script_path=proof_recording_script_path,
        checklist_path=checklist_path,
        proof_manifest_path=proof_manifest_path,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            f"Installed {export_result.module_root}.mod to {install_path}."
            if installed
            else "Authored module staged with manual in-game checklist."
        ),
        code=code,
    )


def _proof_request_checks(request: AuthoredModuleGameProofRequest) -> dict[str, bool]:
    return {
        "module_loads_in_game": bool(request.module_loads_in_game),
        "module_identity_matches_authored_resref": bool(request.module_identity_matches_authored_resref),
        "player_spawns_on_floor": bool(request.player_spawns_on_floor),
        "test_placeable_visible": bool(request.test_placeable_visible),
        "player_can_walk_on_floor": bool(request.player_can_walk_on_floor),
        "no_inherited_base_game_geometry_or_scripted_movers": bool(
            request.no_inherited_base_game_geometry_or_scripted_movers
        ),
        "screenshot_or_video_captured": _valid_proof_evidence_path(request.evidence_path),
    }


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


def _update_authored_pack_manifest_for_game_proof(
    *,
    pack_manifest_path: str,
    accepted: bool,
    proof_payload: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if not pack_manifest_path:
        warnings.append("No pack manifest path was available to update with authored module in-game proof.")
        return warnings
    manifest_path = Path(pack_manifest_path)
    if not manifest_path.is_file():
        warnings.append(f"Pack manifest was not found for authored module in-game proof update: {manifest_path}")
        return warnings
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"Pack manifest could not be read for authored module in-game proof update: {exc}")
        return warnings
    authored = manifest.setdefault("map_studio_authored_module", {})
    authored["game_tested"] = bool(accepted)
    contract = authored.get("t2601_smoke_contract")
    if isinstance(contract, dict):
        contract["game_tested"] = bool(accepted)
        contract["proof_required"] = not accepted
        if accepted:
            contract["capability_stage"] = "game_smoke_tested"
    if accepted:
        authored["capability_stage"] = "game_smoke_tested"
        remaining = list(authored.get("remaining_acceptance", []))
        authored["remaining_acceptance"] = [
            item
            for item in remaining
            if not any(
                needle in str(item).lower()
                for needle in ("install/copy", "warp", "confirm the module", "confirm the player", "placeables", "waypoints", "walk across", "capture")
            )
        ]
    plan = authored.get("modder_test_plan")
    if isinstance(plan, dict):
        plan["game_ready"] = bool(accepted)
        plan["proof_state"] = "game_smoke_tested" if accepted else "requires_live_warp_proof"
        plan["capability_stage"] = "game_smoke_tested" if accepted else str(plan.get("capability_stage") or "export_candidate")
        plan["missing_acceptance_checks"] = list(proof_payload.get("missing_checks") or [])
        evidence = plan.setdefault("evidence", {})
        if isinstance(evidence, dict):
            evidence["required"] = not bool(accepted)
            evidence["path"] = str(proof_payload.get("evidence_path") or "")
        plan["modder_next_step"] = (
            "Keep the proof manifest and screenshot/video with the package."
            if accepted
            else "Resolve missing in-game proof checks, then record fresh screenshot/video evidence."
        )
    authored["in_game_proof"] = proof_payload
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return warnings


def record_authored_module_game_proof(request: AuthoredModuleGameProofRequest) -> AuthoredModuleGameProofResult:
    """Record the manual in-game proof gate for an authored Map Studio module."""

    proof_manifest_path = Path(request.proof_manifest_path)
    if not proof_manifest_path.is_file():
        return AuthoredModuleGameProofResult(
            ok=False,
            proof_manifest_path=str(proof_manifest_path),
            evidence_path=request.evidence_path,
            blocking_issues=[f"Proof manifest does not exist: {proof_manifest_path}"],
            message="Could not record authored module in-game proof because the proof manifest is missing.",
            code="proof_manifest_missing",
        )
    try:
        proof = json.loads(proof_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return AuthoredModuleGameProofResult(
            ok=False,
            proof_manifest_path=str(proof_manifest_path),
            evidence_path=request.evidence_path,
            blocking_issues=[f"Proof manifest could not be read: {exc}"],
            message="Could not record authored module in-game proof because the proof manifest is unreadable.",
            code="proof_manifest_unreadable",
        )

    required = list(proof.get("acceptance_checks") or _authored_acceptance_checks())
    checks = _proof_request_checks(request)
    missing = [name for name in required if not checks.get(name, False)]
    accepted = not missing
    tested_at = datetime.now(timezone.utc).isoformat()
    proof_payload = {
        "tested_at": tested_at,
        "tester": request.tester,
        "evidence_path": request.evidence_path,
        "notes": request.notes,
        "checks": checks,
        "accepted": accepted,
        "missing_checks": missing,
    }
    proof["game_test"] = proof_payload
    proof["manual_proof_required"] = not accepted
    proof["game_tested"] = accepted
    contract = proof.get("t2601_smoke_contract")
    install = proof.get("install") if isinstance(proof.get("install"), dict) else {}
    installed = bool(install.get("installed") or str(install.get("installed_module_path") or "").strip())
    if isinstance(contract, dict):
        contract["game_tested"] = accepted
        contract["proof_required"] = not accepted
        if accepted:
            contract["capability_stage"] = "game_smoke_tested"
        proof["modder_test_plan"] = _authored_modder_test_plan(
            smoke_contract=contract,
            module_path=str((proof.get("package") or {}).get("module_path") or ""),
            install_path=str((proof.get("install") or {}).get("installed_module_path") or ""),
            proof_manifest_path=str(proof_manifest_path),
            evidence_path=request.evidence_path,
            accepted=accepted,
            missing_checks=missing,
            dry_run=bool(install.get("dry_run")),
            installed=installed,
        )
        proof["capability_stage"] = proof["modder_test_plan"]["capability_stage"]
        proof["proof_state"] = proof["modder_test_plan"]["proof_state"]
    if accepted:
        proof["completed_at"] = tested_at
    proof_manifest_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")

    pack_manifest_path = str((proof.get("package") or {}).get("pack_manifest_path") or "")
    warnings = _update_authored_pack_manifest_for_game_proof(
        pack_manifest_path=pack_manifest_path,
        accepted=accepted,
        proof_payload=proof_payload,
    )
    blocking = [f"In-game acceptance check is incomplete: {name}" for name in missing]
    return AuthoredModuleGameProofResult(
        ok=accepted,
        proof_manifest_path=str(proof_manifest_path),
        pack_manifest_path=pack_manifest_path,
        evidence_path=request.evidence_path,
        missing_checks=missing,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            "Recorded complete in-game proof for authored Map Studio module."
            if accepted
            else "Recorded incomplete authored module in-game proof attempt; module remains unproven."
        ),
        code="game_proof_recorded" if accepted else "game_proof_incomplete",
    )


__all__ = [
    "AuthoredModuleBuild",
    "AuthoredModuleExportRequest",
    "AuthoredModuleExportResult",
    "AuthoredModuleGameProofRequest",
    "AuthoredModuleGameProofResult",
    "AuthoredModuleInstallPrepRequest",
    "AuthoredModuleInstallPrepResult",
    "AuthoredModuleResourceSummary",
    "authored_module_smoke_summary_lines",
    "build_authored_module",
    "export_authored_module_project",
    "prepare_authored_module_install",
    "record_authored_module_game_proof",
]
