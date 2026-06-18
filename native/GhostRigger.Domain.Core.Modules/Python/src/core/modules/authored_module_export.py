"""Headless authored KMAP module export pipeline for Map Studio.

This module turns editable ``AuthoredModuleProject`` intent into the Odyssey
runtime resources required by a module package.  Qt windows should call this
service through ``ModuleEditorController`` instead of assembling ARE/GIT/IFO,
LYT/VIS, WOK, or room MDL/MDX resources themselves.
"""

from __future__ import annotations

import importlib.util
import json
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
    message: str = ""
    code: str = "not_run"


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
        anchors.append(AuthoredPathAnchor("entry_point", placements.entry_point.position))
    for index, placeable in enumerate(placements.placeables):
        label = f"placeable:{placeable.tag or placeable.template_resref or f'placeable_{index + 1}'}"
        if ok_labels.get(label, False):
            anchors.append(AuthoredPathAnchor(label, placeable.position))
    for index, waypoint in enumerate(placements.waypoints):
        label = f"waypoint:{waypoint.tag or waypoint.template_resref or f'waypoint_{index + 1}'}"
        if ok_labels.get(label, False):
            anchors.append(AuthoredPathAnchor(label, waypoint.position))
    return tuple(anchors)


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
        },
    )


def _augment_authored_manifest(path: str, build: AuthoredModuleBuild, package_result: CustomModulePackResult, verification: DevModulePackageVerification | None) -> None:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
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
            }
            for resref, geometry in sorted(build.module.room_geometry.items())
        ],
        "resources": [summary.__dict__ for summary in build.resource_summaries],
        "package_ok": bool(package_result.ok),
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
        "manual_game_test_required": [
            f"Copy/install {build.module_root}.mod into the KOTOR Modules folder.",
            f"Start KOTOR and run 'warp {build.module_root}'.",
            "Confirm the room loads, player start works, and authored gameplay templates resolve.",
        ],
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
        message=(
            f"Authored Map Studio module exported: {package_result.module_path}"
            if ok
            else package_result.message
        ),
        code="export_candidate" if ok else (verification.code if verification is not None and not verification.ok else package_result.code),
    )


__all__ = [
    "AuthoredModuleBuild",
    "AuthoredModuleExportRequest",
    "AuthoredModuleExportResult",
    "AuthoredModuleResourceSummary",
    "build_authored_module",
    "export_authored_module_project",
]
