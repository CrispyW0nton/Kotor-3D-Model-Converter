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
from .authored_module_metadata import AuthoredAreaMetadata, compile_authored_module_metadata
from .authored_module_objects import AuthoredGameplayPlacement, build_git_bytes, validate_authored_gameplay_placement_against_walkmesh
from .authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec, normalise_resref, validate_authored_module_project
from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh
from .authored_room_materials import compile_authored_room_material_preflight
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
    player_spawns_on_floor: bool = False
    test_placeable_visible: bool = False
    player_can_walk_on_floor: bool = False
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
            repo / "native" / "GhostRigger.Domain.Core.Geometry" / "Python" / "src" / "core" / "geometry" / "model_data.py",
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
    return {
        "expected_entry_point": expected_entry,
        "expected_placeables": expected_placeables,
        "expected_waypoints": expected_waypoints,
        "expected_runtime_observations": {
            "player_start_area": expected_entry["area_resref"],
            "player_start_position": expected_entry["position"],
            "test_placeable_tags": [row["tag"] for row in expected_placeables if row["tag"]],
            "waypoint_tags": [row["tag"] for row in expected_waypoints if row["tag"]],
        },
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


def build_authored_module(project: AuthoredModuleProject) -> AuthoredModuleBuild:
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
    smoke_expectations = _smoke_expectations_from_build_parts(
        project,
        walkability=walkability_metadata,
        pathing=pathing_metadata,
    )
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
    data["map_studio_authored_module"] = {
        "task": "T2643",
        "module_root": build.module_root,
        "game": build.game,
        "authored_from_scratch": True,
        "capability_stage": "export_candidate",
        "game_tested": False,
        "warp_command": f"warp {build.module_root}",
        "rooms": [
            {
                "resref": resref,
                "wok_faces": len(getattr(geometry.wok, "faces", []) or []),
                "model_nodes": 1 + len(geometry.helper_meshes),
                "texture": str(getattr(geometry.room_mesh, "texture", "") or ""),
                "floor_surface_id": int(getattr((list(getattr(geometry.wok, "faces", []) or []) or [None])[0], "surface", -1)),
            }
            for resref, geometry in sorted(build.module.room_geometry.items())
        ],
        "gameplay_counts": _placement_counts(build.project.placements),
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

    build = build_authored_module(request.project)
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
    return contract


def _authored_game_test_steps(module_root: str) -> list[str]:
    return [
        f"Install/copy `{module_root}.mod` into the selected KOTOR `Modules` folder.",
        "Launch the matching KOTOR game.",
        f"Open the console and run `warp {module_root}`.",
        "Confirm the module loads without crashing or falling back to another area.",
        "Confirm the player appears on the generated floor, not in the void.",
        "Confirm the authored test placeable appears near the expected location when one is present.",
        "Walk across the generated floor and confirm movement is not blocked unexpectedly.",
        "Capture a screenshot or short clip as proof.",
    ]


def _authored_acceptance_checks() -> list[str]:
    return [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "test_placeable_visible",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]


def _write_authored_install_proof_files(
    *,
    output_root: Path,
    export_result: AuthoredModuleExportResult,
    game: str,
    install_path: str,
    backup_path: str,
    installed: bool,
    dry_run: bool,
    warnings: list[str],
    blocking: list[str],
) -> tuple[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    module_root = export_result.module_root or "authored"
    checklist_path = output_root / f"{module_root}_authored_module_game_checklist.md"
    proof_manifest_path = output_root / f"{module_root}_authored_module_game_manifest.json"
    steps = _authored_game_test_steps(module_root)
    checklist_lines = [
        f"# {module_root} Authored Module In-Game Test",
        "",
        "This checklist is the manual proof gate for authored Map Studio modules. The module is not game-tested until these boxes are checked from an actual KOTOR run.",
        "",
        f"- Package: `{export_result.module_path}`",
        f"- Install target: `{install_path or '(not installed)'}`",
        f"- Previous module backup: `{backup_path or '(none)'}`",
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
    proof_manifest = {
        "task": "T2644",
        "module_root": module_root,
        "game": str(game or "K1").upper(),
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
        "acceptance_checks": _authored_acceptance_checks(),
        "t2601_smoke_contract": _authored_smoke_contract_from_export_result(export_result),
        "steps": steps,
        "warnings": warnings,
        "blocking_issues": blocking,
    }
    proof_manifest_path.write_text(json.dumps(proof_manifest, indent=2), encoding="utf-8")
    return str(checklist_path), str(proof_manifest_path)


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
    if not export_result.ok:
        blocking.append(export_result.message or "Authored module export failed.")
    else:
        if not modules_dir_text:
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

    checklist_path, proof_manifest_path = _write_authored_install_proof_files(
        output_root=output_root,
        export_result=export_result,
        game=request.project.game,
        install_path=install_path,
        backup_path=backup_path,
        installed=installed,
        dry_run=request.dry_run,
        warnings=warnings,
        blocking=blocking,
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
        "player_spawns_on_floor": bool(request.player_spawns_on_floor),
        "test_placeable_visible": bool(request.test_placeable_visible),
        "player_can_walk_on_floor": bool(request.player_can_walk_on_floor),
        "screenshot_or_video_captured": bool(request.evidence_path and (request.allow_missing_evidence or Path(request.evidence_path).is_file())),
    }


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
    if isinstance(contract, dict):
        contract["game_tested"] = accepted
        contract["proof_required"] = not accepted
        if accepted:
            contract["capability_stage"] = "game_smoke_tested"
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
    "build_authored_module",
    "export_authored_module_project",
    "prepare_authored_module_install",
    "record_authored_module_game_proof",
]
