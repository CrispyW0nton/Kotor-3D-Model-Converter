"""From-scratch Map Studio dev-module smoke builder.

T2601 proves the first useful Map Studio contract: GhostRigger can author a
small module without cloning a vanilla area, produce the core Odyssey resources,
and package them through the install-safe custom-module packager.  This is not
an in-game certification layer; the manifest intentionally marks the package as
an export candidate until a modder/dev runs it in KOTOR with ``warp grdev01``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .custom_module_packager import (
    CustomModulePackRequest,
    CustomModulePackResult,
    PackagedModuleResource,
    package_custom_module,
)
from .authored_module_objects import (
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredWaypointInstance,
    ModuleEntryPoint,
    build_git_bytes,
)
from .authored_room_geometry import (
    AuthoredRoomGeometry,
    PrimitiveMesh,
    RectangularRoomPrimitive,
    build_rectangular_room_geometry,
)
from .authored_room_composition import compile_authored_room_composition
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id, walkmesh_surface_name
from .authored_module_project import (
    AuthoredModuleProject,
    create_single_room_project,
    validate_authored_module_project,
)
from .authored_module_layout import compile_authored_module_layout
from .authored_module_metadata import AuthoredAreaMetadata, compile_authored_module_metadata
from .authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
from .module_format import LYTLayout, VISData, WOKData


@dataclass(frozen=True)
class DevModuleSmokeRequest:
    """Options for the first from-scratch module proof package."""

    module_root: str = "grdev01"
    game: str = "K1"
    output_dir: str = ""
    room_resref: str = "grdev01_room01"
    width: float = 10.0
    depth: float = 10.0
    wall_height: float = 3.0
    surface_id: int | str = 4
    room_texture: str = "default"
    player_start: tuple[float, float, float] = (0.0, -3.0, 0.0)
    player_facing: float = 0.0
    test_placeable_resref: str = "plc_bench"
    test_placeable_position: tuple[float, float, float] = (1.75, 1.5, 0.0)
    test_placeable_facing: float = 0.0
    include_reference_check: bool = False
    include_game_template_check: bool = True
    game_root_dir: str = ""
    settings_path: str = ""
    include_wok_check: bool = True
    strict: bool = True


@dataclass(frozen=True)
class DevModuleResourceSummary:
    """Compact resource summary for reports and tests."""

    resref: str
    restype: str
    size: int
    source: str


@dataclass(frozen=True)
class DevModuleWalkabilityCheck:
    """Pre-game check that a gameplay anchor sits on generated walkmesh."""

    label: str
    position: tuple[float, float, float]
    ok: bool
    face_index: int
    surface_id: int
    message: str


@dataclass(frozen=True)
class DevModuleTemplateReferenceCheck:
    """Pre-game check that an external gameplay template exists in KOTOR data."""

    owner_type: str
    resref: str
    restype: str
    ok: bool
    source_path: str = ""
    message: str = ""


@dataclass(frozen=True)
class DevModuleArchiveResource:
    """Resource record read back from a generated MOD archive."""

    resref: str
    restype: str
    size: int
    offset: int


@dataclass
class DevModulePackageVerification:
    """Headless package readback report for the T2601 smoke module."""

    ok: bool = False
    module_path: str = ""
    resources: list[DevModuleArchiveResource] = field(default_factory=list)
    parsed_gff: tuple[str, ...] = ()
    parsed_wok: tuple[str, ...] = ()
    model_pairs: tuple[str, ...] = ()
    path_point_count: int = 0
    path_connection_count: int = 0
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_verified"


@dataclass
class AuthoredDevModule:
    """Headless module-like object consumed by the custom module packager."""

    module_root: str
    game: str
    module: Any
    project: AuthoredModuleProject | None = None
    metadata_provenance: dict[str, Any] = field(default_factory=dict)
    pathing_provenance: dict[str, Any] = field(default_factory=dict)
    resources: dict[tuple[str, str], Any] = field(default_factory=dict)
    packaged_resources: list[PackagedModuleResource] = field(default_factory=list)
    resource_summaries: list[DevModuleResourceSummary] = field(default_factory=list)
    walkability_checks: list[DevModuleWalkabilityCheck] = field(default_factory=list)
    template_reference_checks: list[DevModuleTemplateReferenceCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


@dataclass
class DevModuleSmokeResult:
    """Result from building and packaging the dev test module."""

    ok: bool = False
    module_root: str = ""
    room_resref: str = ""
    module_path: str = ""
    manifest_path: str = ""
    package_result: CustomModulePackResult | None = None
    package_verification: DevModulePackageVerification | None = None
    resources: list[DevModuleResourceSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_run"


@dataclass(frozen=True)
class DevModuleInstallPrepRequest:
    """Options for staging the smoke module for a manual in-game warp test."""

    output_dir: str = ""
    game_modules_dir: str = ""
    game_root_dir: str = ""
    settings_path: str = ""
    auto_detect_game_modules_dir: bool = False
    game: str = "K1"
    overwrite: bool = False
    dry_run: bool = False
    smoke_request: DevModuleSmokeRequest | None = None


@dataclass
class DevModuleInstallPrepResult:
    """Safe install-prep result for the manual ``warp grdev01`` proof."""

    ok: bool = False
    export_result: DevModuleSmokeResult | None = None
    installed_module_path: str = ""
    resolved_modules_dir: str = ""
    checklist_path: str = ""
    proof_manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_prepared"


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
    room_geometry: AuthoredRoomGeometry | None = None
    placements: AuthoredGameplayPlacement | None = None


def _normalise_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


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
    """Import the room MDL writer even when native payload paths are split."""

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


def _make_git_bytes(request: DevModuleSmokeRequest) -> bytes:
    return build_git_bytes(_make_gameplay_placement(request))


def _room_primitive(request: DevModuleSmokeRequest) -> RectangularRoomPrimitive:
    return RectangularRoomPrimitive(
        room_resref=_normalise_resref(request.room_resref),
        width=float(request.width),
        depth=float(request.depth),
        wall_height=float(request.wall_height),
        floor_surface_id=resolve_walkmesh_surface_id(request.surface_id),
        texture=str(request.room_texture or ""),
        include_doorway_marker=True,
    )


def _make_gameplay_placement(request: DevModuleSmokeRequest) -> AuthoredGameplayPlacement:
    root = _normalise_resref(request.module_root)
    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(
            area_resref=root,
            position=tuple(float(value) for value in request.player_start),  # type: ignore[arg-type]
            facing=float(request.player_facing),
        ),
        placeables=(
            AuthoredPlaceableInstance(
                template_resref=_normalise_resref(request.test_placeable_resref),
                tag="grdev01_test_placeable",
                position=tuple(float(value) for value in request.test_placeable_position),  # type: ignore[arg-type]
                bearing=float(request.test_placeable_facing),
            ),
        ),
        waypoints=(
            AuthoredWaypointInstance(
                template_resref="sw_startloc001",
                tag="start",
                position=tuple(float(value) for value in request.player_start),  # type: ignore[arg-type]
                bearing=float(request.player_facing),
            ),
        ),
        metadata={
            "source": "map_studio:t2601",
            "player_start_is_module_entry": True,
            "placeable_count": 1,
            "waypoint_count": 1,
        },
    )


def _make_authored_project(request: DevModuleSmokeRequest) -> AuthoredModuleProject:
    return create_single_room_project(
        module_root=request.module_root,
        game=request.game,
        display_name="GhostRigger Dev Test",
        room_primitive=_room_primitive(request),
        placements=_make_gameplay_placement(request),
        notes=(
            "T2601 from-scratch smoke module.",
            "Generated from authored primitive geometry and authored gameplay placements.",
        ),
        metadata={
            "task": "T2601",
            "source": "map_studio:authored_project",
        },
    )


def _walkable_ids() -> set[int]:
    try:
        from .module_format import WALKABLE_IDS

        return set(WALKABLE_IDS)
    except Exception:
        return {1, 3, 4, 5, 9, 10, 11, 12, 13, 14, 19, 20, 21}


def _walkability_check(label: str, position: tuple[float, float, float], wok: WOKData) -> DevModuleWalkabilityCheck:
    face_index = wok.face_at_point(float(position[0]), float(position[1]))
    if face_index < 0:
        return DevModuleWalkabilityCheck(
            label=label,
            position=position,
            ok=False,
            face_index=-1,
            surface_id=-1,
            message=f"{label} is outside the generated room walkmesh.",
        )
    face = wok.faces[face_index]
    surface_id = int(face.surface)
    surface_name = walkmesh_surface_name(surface_id)
    if surface_id not in _walkable_ids():
        return DevModuleWalkabilityCheck(
            label=label,
            position=position,
            ok=False,
            face_index=face_index,
            surface_id=surface_id,
            message=f"{label} is on WOK face {face_index}, but surface {surface_id} ({surface_name}) is not walkable.",
        )
    floor_z = float(wok.verts[face.v1][2] + wok.verts[face.v2][2] + wok.verts[face.v3][2]) / 3.0
    if abs(float(position[2]) - floor_z) > 0.05:
        return DevModuleWalkabilityCheck(
            label=label,
            position=position,
            ok=False,
            face_index=face_index,
            surface_id=surface_id,
            message=f"{label} Z={position[2]:.3f} is not on generated floor Z={floor_z:.3f}.",
        )
    return DevModuleWalkabilityCheck(
        label=label,
        position=position,
        ok=True,
        face_index=face_index,
        surface_id=surface_id,
        message=f"{label} is on walkable WOK face {face_index} ({surface_name}).",
    )


def _validate_gameplay_anchors(request: DevModuleSmokeRequest, wok: WOKData) -> list[DevModuleWalkabilityCheck]:
    return [
        _walkability_check("player_start", request.player_start, wok),
        _walkability_check("test_placeable", request.test_placeable_position, wok),
    ]


def _game_root_for_template_check(request: DevModuleSmokeRequest) -> str:
    for root in _candidate_game_roots(
        request.game,
        explicit_root=request.game_root_dir,
        settings_path=request.settings_path,
    ):
        if (root / "chitin.key").is_file():
            return str(root)
    return ""


def _template_reference_check(
    *,
    installation: Any,
    owner_type: str,
    resref: str,
    restype_name: str,
) -> DevModuleTemplateReferenceCheck:
    from pykotor.extract.file import ResourceQuery
    from pykotor.resource.type import ResourceType

    normalised = _normalise_resref(resref)
    restype = getattr(ResourceType, restype_name.upper())
    result = installation.find_one(ResourceQuery(normalised, restype))
    if result is None:
        return DevModuleTemplateReferenceCheck(
            owner_type=owner_type,
            resref=normalised,
            restype=restype_name.lower(),
            ok=False,
            message=f"{owner_type} template {normalised}.{restype_name.lower()} was not found in the selected KOTOR install.",
        )
    source_path = str(getattr(result, "filepath", "") or "")
    return DevModuleTemplateReferenceCheck(
        owner_type=owner_type,
        resref=normalised,
        restype=restype_name.lower(),
        ok=True,
        source_path=source_path,
        message=f"{owner_type} template {normalised}.{restype_name.lower()} resolved from KOTOR data.",
    )


def _validate_gameplay_templates(
    request: DevModuleSmokeRequest,
    placement: AuthoredGameplayPlacement,
) -> tuple[list[DevModuleTemplateReferenceCheck], list[str]]:
    if not request.include_game_template_check:
        return [], ["Game-library template resolution is disabled for this smoke package."]
    game_root = _game_root_for_template_check(request)
    if not game_root:
        return [], ["Could not locate a KOTOR install for gameplay template resolution; package still requires an in-game smoke test."]
    try:
        from pykotor.extract.installation import Installation

        installation = Installation(game_root)
    except Exception as exc:
        return [], [f"KOTOR template resolution could not initialize for {game_root}: {exc}"]
    checks: list[DevModuleTemplateReferenceCheck] = []
    for creature in placement.creatures:
        checks.append(
            _template_reference_check(
                installation=installation,
                owner_type="creature",
                resref=creature.template_resref,
                restype_name="utc",
            )
        )
    for door in placement.doors:
        checks.append(
            _template_reference_check(
                installation=installation,
                owner_type="door",
                resref=door.template_resref,
                restype_name="utd",
            )
        )
    for trigger in placement.triggers:
        checks.append(
            _template_reference_check(
                installation=installation,
                owner_type="trigger",
                resref=trigger.template_resref,
                restype_name="utt",
            )
        )
    for placeable in placement.placeables:
        checks.append(
            _template_reference_check(
                installation=installation,
                owner_type="placeable",
                resref=placeable.template_resref,
                restype_name="utp",
            )
        )
    for waypoint in placement.waypoints:
        checks.append(
            _template_reference_check(
                installation=installation,
                owner_type="waypoint",
                resref=waypoint.template_resref,
                restype_name="utw",
            )
        )
    return checks, [f"Gameplay templates resolved against KOTOR install: {game_root}"]


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


def _make_room_model_bytes(request: DevModuleSmokeRequest, geometry: AuthoredRoomGeometry) -> tuple[bytes, bytes]:
    md, Writer = _import_mdl_runtime()
    root = md.ModelNode(name=geometry.room_resref, flags=int(md.NodeFlags.HEADER))
    mesh = _primitive_mesh_to_node(md, geometry.room_mesh, root)
    root.children.append(mesh)
    for helper_mesh in geometry.helper_meshes:
        root.children.append(_primitive_mesh_to_node(md, helper_mesh, root))
    model = md.KotorModel(
        name=geometry.room_resref,
        supermodel="NULL",
        classification="area",
        game_version=md.GameVersion.K2 if str(request.game).upper() == "K2" else md.GameVersion.K1,
        model_type=int(md.ModelClassification.EFFECT),
        root_node=root,
    )
    model.compute_bounds()
    return Writer().write(model)


def _make_packaged(resref: str, restype: str, data: bytes, source: str) -> PackagedModuleResource:
    return PackagedModuleResource(resref=resref, restype=restype, data=data, source=source)


def build_dev_test_module(request: DevModuleSmokeRequest | None = None) -> AuthoredDevModule:
    """Build the in-memory resources for ``grdev01`` without writing files."""

    request = request or DevModuleSmokeRequest()
    project = _make_authored_project(request)
    root = project.module_root
    room_spec = project.rooms[0]
    room = room_spec.normalised_resref()
    geometry = (
        compile_authored_room_composition(room_spec.composition)
        if room_spec.composition is not None
        else build_rectangular_room_geometry(room_spec.primitive)
    )
    placements = project.placements
    compiled_metadata = compile_authored_module_metadata(
        project.metadata,
        placements.entry_point,
        area=AuthoredAreaMetadata(
            name=project.metadata.display_name,
            tag=project.module_root,
            comments="Generated by GhostRigger Map Studio T2601 smoke builder.",
        ),
    )
    layout = compile_authored_module_layout(project)
    lyt = layout.lyt
    vis = layout.vis
    wok = geometry.wok
    walkability_checks = _validate_gameplay_anchors(request, wok)
    walkability_by_label = {check.label: check for check in walkability_checks}
    path_anchors = []
    if walkability_by_label.get("player_start") and walkability_by_label["player_start"].ok:
        path_anchors.append(AuthoredPathAnchor("player_start", request.player_start))
    if walkability_by_label.get("test_placeable") and walkability_by_label["test_placeable"].ok:
        path_anchors.append(AuthoredPathAnchor("test_placeable", request.test_placeable_position))
    compiled_pathing = compile_authored_pathing_for_module(
        wok,
        anchors=tuple(path_anchors),
    )
    template_checks, template_warnings = _validate_gameplay_templates(request, placements)
    module_state = _ModuleState(name=root, lyt=lyt, vis=vis, room_woks={room: wok}, room_geometry=geometry, placements=placements)

    packaged = [
        _make_packaged(root, "are", compiled_metadata.are_bytes, "map_studio:t2601:are"),
        _make_packaged(root, "git", _make_git_bytes(request), "map_studio:t2601:git"),
        _make_packaged(root, "ifo", compiled_metadata.ifo_bytes, "map_studio:t2601:ifo"),
        _make_packaged(root, "pth", compiled_pathing.pth_bytes, "map_studio:t2601:pth"),
    ]
    mdl_bytes, mdx_bytes = _make_room_model_bytes(request, geometry)
    packaged.extend(
        [
            _make_packaged(room, "mdl", mdl_bytes, "map_studio:t2601:room_model"),
            _make_packaged(room, "mdx", mdx_bytes, "map_studio:t2601:room_model"),
        ]
    )
    resources = {
        (root, "lyt"): _HydratedResource(_ResourceRecord(root, "lyt", "map_studio:t2601:lyt"), lyt.to_text().encode("latin-1")),
        (root, "vis"): _HydratedResource(_ResourceRecord(root, "vis", "map_studio:t2601:vis"), vis.to_text().encode("latin-1")),
        (room, "wok"): _HydratedResource(_ResourceRecord(room, "wok", "map_studio:t2601:wok"), wok.to_bytes()),
    }
    for item in packaged:
        resources[item.key] = _HydratedResource(_ResourceRecord(item.key[0], item.key[1], item.source), bytes(item.data))
    summaries = [
        DevModuleResourceSummary(resref=resref, restype=restype, size=len(_resource.data), source=_resource.record.source)
        for (resref, restype), _resource in sorted(resources.items())
    ]
    warnings = list(template_warnings)
    if not request.include_reference_check:
        warnings.append("Game-library template reference validation is disabled for this smoke package.")
    blocking = [check.message for check in walkability_checks if not check.ok]
    blocking.extend(check.message for check in template_checks if not check.ok)
    project_validation = validate_authored_module_project(project)
    warnings.extend(project_validation.warnings)
    blocking.extend(project_validation.blocking_issues)
    return AuthoredDevModule(
        module_root=root,
        game=project.game,
        module=module_state,
        project=project,
        metadata_provenance=dict(compiled_metadata.metadata),
        pathing_provenance=dict(compiled_pathing.metadata),
        resources=resources,
        packaged_resources=packaged,
        resource_summaries=summaries,
        walkability_checks=walkability_checks,
        template_reference_checks=template_checks,
        warnings=warnings,
        blocking_issues=blocking,
    )


def _archive_restype_by_id() -> dict[int, str]:
    from .module_save_pipeline import RESTYPE_IDS

    expected = {"are", "git", "ifo", "pth", "lyt", "vis", "wok", "mdl", "mdx"}
    restype_by_id = {
        value: restype
        for restype, value in RESTYPE_IDS.items()
        if restype in expected and restype != "vis"
    }
    restype_by_id[RESTYPE_IDS["vis"]] = "vis"
    return restype_by_id


def _read_mod_archive_payloads(module_path: Path) -> dict[tuple[str, str], tuple[DevModuleArchiveResource, bytes]]:
    archive = module_path.read_bytes()
    if len(archive) < 160:
        raise ValueError(f"{module_path} is too small to be a MOD archive.")
    if archive[:8] != b"MOD V1.0":
        raise ValueError(f"{module_path} is not a MOD V1.0 archive.")
    resource_count = struct.unpack_from("<I", archive, 16)[0]
    keylist_offset = struct.unpack_from("<I", archive, 24)[0]
    reslist_offset = struct.unpack_from("<I", archive, 28)[0]
    restype_by_id = _archive_restype_by_id()
    resources: dict[tuple[str, str], tuple[DevModuleArchiveResource, bytes]] = {}
    for index in range(resource_count):
        key_offset = keylist_offset + index * 24
        data_record_offset = reslist_offset + index * 8
        if key_offset + 24 > len(archive) or data_record_offset + 8 > len(archive):
            raise ValueError(f"{module_path} has a truncated archive table.")
        resref = archive[key_offset : key_offset + 16].split(b"\x00", 1)[0].decode("ascii", errors="replace").lower()
        _resource_id, restype_id, _unused = struct.unpack_from("<IHH", archive, key_offset + 16)
        restype = restype_by_id.get(restype_id, f"id:{restype_id}")
        offset, size = struct.unpack_from("<II", archive, data_record_offset)
        if offset + size > len(archive):
            raise ValueError(f"{module_path} has an out-of-range resource payload for {resref}.{restype}.")
        record = DevModuleArchiveResource(resref=resref, restype=restype, size=size, offset=offset)
        resources[(resref, restype)] = (record, archive[offset : offset + size])
    return resources


def _gff_content_name(data: bytes) -> str:
    from pykotor.resource.formats.gff import read_gff

    return str(read_gff(data).content.name).lower()


def _pth_counts(data: bytes) -> tuple[int, int]:
    from pykotor.resource.generics.pth import read_pth

    pth = read_pth(data)
    point_count = len(pth)
    connection_count = sum(len(pth.outgoing(index)) for index in range(point_count))
    return point_count, connection_count


def _verify_room_model_pair(room: str, mdl: bytes, mdx: bytes) -> tuple[bool, str]:
    if len(mdl) < 12:
        return False, f"{room}.mdl is too small to contain an MDL header."
    if not mdx:
        return False, f"{room}.mdx is empty."
    mdl_payload_size = struct.unpack_from("<I", mdl, 4)[0]
    mdx_size = struct.unpack_from("<I", mdl, 8)[0]
    if mdl_payload_size + 12 != len(mdl):
        return False, f"{room}.mdl header size {mdl_payload_size} does not match file length {len(mdl)}."
    if mdx_size != len(mdx):
        return False, f"{room}.mdl references MDX size {mdx_size}, but {room}.mdx is {len(mdx)} bytes."
    return True, f"{room}.mdl/.mdx header sizes agree."


def verify_dev_test_module_package(
    module_path: str | Path,
    *,
    expected_module_root: str = "grdev01",
    expected_room_resref: str = "grdev01_room01",
) -> DevModulePackageVerification:
    """Read back the generated MOD and verify the smoke-test resource contract."""

    module_path = Path(module_path)
    module_root = _normalise_resref(expected_module_root)
    room = _normalise_resref(expected_room_resref)
    try:
        payloads = _read_mod_archive_payloads(module_path)
    except Exception as exc:
        return DevModulePackageVerification(
            ok=False,
            module_path=str(module_path),
            blocking_issues=[str(exc)],
            message=f"Could not read back {module_path.name}: {exc}",
            code="archive_read_failed",
        )

    expected = {
        (module_root, "are"),
        (module_root, "git"),
        (module_root, "ifo"),
        (module_root, "pth"),
        (module_root, "lyt"),
        (module_root, "vis"),
        (room, "wok"),
        (room, "mdl"),
        (room, "mdx"),
    }
    blocking = [f"Missing generated resource {resref}.{restype}." for resref, restype in sorted(expected - set(payloads))]
    warnings: list[str] = []
    parsed_gff: list[str] = []
    path_point_count = 0
    path_connection_count = 0
    for restype in ("are", "git", "ifo", "pth"):
        key = (module_root, restype)
        if key not in payloads:
            continue
        try:
            content = _gff_content_name(payloads[key][1])
            if content != restype:
                blocking.append(f"{module_root}.{restype} parsed as {content.upper()}, expected {restype.upper()}.")
            else:
                parsed_gff.append(f"{module_root}.{restype}")
                if restype == "pth":
                    path_point_count, path_connection_count = _pth_counts(payloads[key][1])
                    if path_point_count < 1:
                        blocking.append(f"{module_root}.pth parsed but contains no path points.")
        except Exception as exc:
            blocking.append(f"{module_root}.{restype} did not parse as GFF: {exc}")

    parsed_wok: list[str] = []
    wok_key = (room, "wok")
    if wok_key in payloads:
        try:
            wok = WOKData.from_bytes(payloads[wok_key][1])
            if not wok.faces:
                blocking.append(f"{room}.wok parsed without walkmesh faces.")
            elif wok.walkable_face_count() < 1:
                blocking.append(f"{room}.wok parsed but contains no walkable faces.")
            else:
                parsed_wok.append(f"{room}.wok")
        except Exception as exc:
            blocking.append(f"{room}.wok did not parse as WOK/BWM: {exc}")

    model_pairs: list[str] = []
    mdl_key = (room, "mdl")
    mdx_key = (room, "mdx")
    if mdl_key in payloads and mdx_key in payloads:
        ok, message = _verify_room_model_pair(room, payloads[mdl_key][1], payloads[mdx_key][1])
        if ok:
            model_pairs.append(f"{room}.mdl/.mdx")
        else:
            blocking.append(message)

    for restype in ("lyt", "vis"):
        key = (module_root, restype)
        if key not in payloads:
            continue
        text = payloads[key][1].decode("latin-1", errors="replace").lower()
        if room not in text:
            blocking.append(f"{module_root}.{restype} does not reference room {room}.")

    resources = [record for record, _payload in sorted(payloads.values(), key=lambda item: (item[0].resref, item[0].restype))]
    ok = not blocking
    return DevModulePackageVerification(
        ok=ok,
        module_path=str(module_path),
        resources=resources,
        parsed_gff=tuple(parsed_gff),
        parsed_wok=tuple(parsed_wok),
        model_pairs=tuple(model_pairs),
        path_point_count=path_point_count,
        path_connection_count=path_connection_count,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            f"{module_path.name} package readback verified for from-scratch module smoke test."
            if ok
            else f"{module_path.name} package readback found {len(blocking)} blocking issue(s)."
        ),
        code="verified" if ok else "verification_failed",
    )


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


def _augment_manifest(
    path: str,
    request: DevModuleSmokeRequest,
    authored: AuthoredDevModule,
    result: CustomModulePackResult,
    verification: DevModulePackageVerification | None = None,
) -> None:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["map_studio_smoke_test"] = {
        "task": "T2601",
        "module_root": authored.module_root,
        "room_resref": _normalise_resref(request.room_resref),
        "authored_from_scratch": True,
        "capability_stage": "export_candidate",
        "game_tested": False,
        "warp_command": f"warp {authored.module_root}",
        "contains": {
            "primitive_composition_room": True,
            "simple_doorway_marker": True,
            "room_mdl_mdx": True,
            "floor_walkmesh": True,
            "player_start": True,
            "test_placeable_template": request.test_placeable_resref,
        },
        "authored_project": {
            "source": "src.core.modules.authored_module_project",
            "module_root": authored.project.module_root if authored.project else authored.module_root,
            "game": authored.project.game if authored.project else authored.game,
            "display_name": authored.project.metadata.display_name if authored.project else "",
            "room_count": len(authored.project.rooms) if authored.project else 0,
            "notes": list(authored.project.notes) if authored.project else [],
            "metadata": dict(authored.project.metadata.metadata) if authored.project else {},
        },
        "authored_layout": {
            "source": "src.core.modules.authored_module_layout",
            "room_count": len(authored.module.lyt.rooms),
            "rooms": [
                {
                    "resref": room.model,
                    "position": [room.x, room.y, room.z],
                    "visible": list(authored.module.vis.visibility.get(room.model, [])),
                }
                for room in authored.module.lyt.rooms
            ],
        },
        "authored_metadata": {
            "source": authored.metadata_provenance.get("source", "src.core.modules.authored_module_metadata"),
            "module_root": authored.metadata_provenance.get("module_root", authored.module_root),
            "display_name": authored.metadata_provenance.get(
                "display_name",
                authored.project.metadata.display_name if authored.project else "",
            ),
            "tag": authored.metadata_provenance.get(
                "tag",
                authored.project.metadata.tag if authored.project else authored.module_root,
            ),
            "fog_near": authored.metadata_provenance.get("fog_near"),
            "fog_far": authored.metadata_provenance.get("fog_far"),
            "dawn_hour": authored.metadata_provenance.get("dawn_hour"),
            "dusk_hour": authored.metadata_provenance.get("dusk_hour"),
        },
        "authored_pathing": {
            "source": authored.pathing_provenance.get("source", "src.core.modules.authored_module_pathing"),
            "point_count": authored.pathing_provenance.get("point_count", 0),
            "connection_count": authored.pathing_provenance.get("connection_count", 0),
            "anchor_labels": list(authored.pathing_provenance.get("anchor_labels", [])),
            "walkmesh_bounds": list(authored.pathing_provenance.get("walkmesh_bounds", [])),
        },
        "authored_geometry": {
            "source": authored.module.room_geometry.metadata.get("source", "src.core.modules.authored_room_geometry")
            if authored.module.room_geometry
            else "unknown",
            "primitive": authored.module.room_geometry.metadata.get("primitive") if authored.module.room_geometry else "unknown",
            "room_mesh": authored.module.room_geometry.room_mesh.name if authored.module.room_geometry else "",
            "helper_meshes": [mesh.name for mesh in authored.module.room_geometry.helper_meshes] if authored.module.room_geometry else [],
            "derived_wok": True,
            "metadata": dict(authored.module.room_geometry.metadata) if authored.module.room_geometry else {},
        },
        "authored_placements": {
            "source": "src.core.modules.authored_module_objects",
            "entry_area": authored.module.placements.entry_point.area_resref if authored.module.placements else "",
            "player_start": list(authored.module.placements.entry_point.position) if authored.module.placements else [],
            "counts": {
                "creatures": len(authored.module.placements.creatures) if authored.module.placements else 0,
                "doors": len(authored.module.placements.doors) if authored.module.placements else 0,
                "triggers": len(authored.module.placements.triggers) if authored.module.placements else 0,
                "encounters": len(authored.module.placements.encounters) if authored.module.placements else 0,
                "sounds": len(authored.module.placements.sounds) if authored.module.placements else 0,
                "cameras": len(authored.module.placements.cameras) if authored.module.placements else 0,
                "stores": len(authored.module.placements.stores) if authored.module.placements else 0,
                "placeables": len(authored.module.placements.placeables) if authored.module.placements else 0,
                "waypoints": len(authored.module.placements.waypoints) if authored.module.placements else 0,
            },
            "creatures": [
                {
                    "template_resref": item.template_resref,
                    "tag": item.tag,
                    "position": list(item.position),
                    "bearing": item.bearing,
                }
                for item in (authored.module.placements.creatures if authored.module.placements else ())
            ],
            "doors": [
                {
                    "template_resref": item.template_resref,
                    "tag": item.tag,
                    "position": list(item.position),
                    "bearing": item.bearing,
                    "linked_to": item.linked_to,
                    "linked_to_module": item.linked_to_module,
                    "transition_destination": item.transition_destination,
                }
                for item in (authored.module.placements.doors if authored.module.placements else ())
            ],
            "triggers": [
                {
                    "template_resref": item.template_resref,
                    "tag": item.tag,
                    "position": list(item.position),
                    "geometry": [list(point) for point in item.geometry],
                    "linked_to": item.linked_to,
                    "linked_to_module": item.linked_to_module,
                    "transition_destination": item.transition_destination,
                }
                for item in (authored.module.placements.triggers if authored.module.placements else ())
            ],
            "placeables": [
                {
                    "template_resref": item.template_resref,
                    "tag": item.tag,
                    "position": list(item.position),
                    "bearing": item.bearing,
                }
                for item in (authored.module.placements.placeables if authored.module.placements else ())
            ],
            "waypoints": [
                {
                    "template_resref": item.template_resref,
                    "tag": item.tag,
                    "position": list(item.position),
                    "bearing": item.bearing,
                }
                for item in (authored.module.placements.waypoints if authored.module.placements else ())
            ],
            "metadata": dict(authored.module.placements.metadata) if authored.module.placements else {},
        },
        "pre_game_checks": {
            "gameplay_anchors_on_walkmesh": all(check.ok for check in authored.walkability_checks),
            "walkability_checks": [
                {
                    "label": check.label,
                    "position": list(check.position),
                    "ok": check.ok,
                    "face_index": check.face_index,
                    "surface_id": check.surface_id,
                    "message": check.message,
                }
                for check in authored.walkability_checks
            ],
            "gameplay_templates_resolved": all(check.ok for check in authored.template_reference_checks),
            "template_reference_checks": [
                {
                    "owner_type": check.owner_type,
                    "resref": check.resref,
                    "restype": check.restype,
                    "ok": check.ok,
                    "source_path": check.source_path,
                    "message": check.message,
                }
                for check in authored.template_reference_checks
            ],
        },
        "package_verification": _verification_to_manifest(verification),
        "remaining_acceptance": [
            "Install/copy the generated .mod to the game's Modules directory.",
            f"Start KOTOR and run 'warp {authored.module_root}'.",
            "Confirm the room loads, the player start works, and the test placeable resolves.",
        ],
    }
    data["validation"]["warnings"] = sorted(set(list(data.get("validation", {}).get("warnings", [])) + authored.warnings + result.warnings))
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def export_dev_test_module(request: DevModuleSmokeRequest | None = None) -> DevModuleSmokeResult:
    """Build and package the first from-scratch Map Studio dev test module."""

    request = request or DevModuleSmokeRequest()
    authored = build_dev_test_module(request)
    if authored.blocking_issues and request.strict:
        return DevModuleSmokeResult(
            ok=False,
            module_root=authored.module_root,
            room_resref=_normalise_resref(request.room_resref),
            resources=authored.resource_summaries,
            warnings=authored.warnings,
            blocking_issues=authored.blocking_issues,
            message=f"Map Studio dev test module preflight found {len(authored.blocking_issues)} blocking issue(s).",
            code="preflight_failed",
        )
    pack_request = CustomModulePackRequest(
        module_root=authored.module_root,
        game=authored.game,
        output_dir=request.output_dir,
        archive_mode="mod",
        create_backups=True,
        write_loose_resources=True,
        include_reference_check=request.include_reference_check,
        include_wok_check=request.include_wok_check,
        strict=request.strict,
    )
    result = package_custom_module(
        authored,
        pack_request,
        resources=authored.packaged_resources,
        now=datetime.now(timezone.utc),
    )
    verification = None
    if result.ok and result.module_path:
        verification = verify_dev_test_module_package(
            result.module_path,
            expected_module_root=authored.module_root,
            expected_room_resref=_normalise_resref(request.room_resref),
        )
    _augment_manifest(result.manifest_path, request, authored, result, verification)
    verification_warnings = list(verification.warnings) if verification is not None else []
    verification_blocking = list(verification.blocking_issues) if verification is not None else []
    ok = result.ok and (verification.ok if verification is not None else True)
    return DevModuleSmokeResult(
        ok=ok,
        module_root=authored.module_root,
        room_resref=_normalise_resref(request.room_resref),
        module_path=result.module_path,
        manifest_path=result.manifest_path,
        package_result=result,
        package_verification=verification,
        resources=authored.resource_summaries,
        warnings=authored.warnings + result.warnings + verification_warnings,
        blocking_issues=authored.blocking_issues + result.blocking_issues + verification_blocking,
        message=(
            f"Map Studio dev test module exported: {result.module_path}"
            if ok
            else result.message
        ),
        code="export_candidate" if ok else (verification.code if verification is not None and not verification.ok else result.code),
    )


def _install_prep_smoke_request(request: DevModuleInstallPrepRequest) -> DevModuleSmokeRequest:
    if request.smoke_request is not None:
        if request.smoke_request.output_dir:
            return request.smoke_request
        return DevModuleSmokeRequest(
            module_root=request.smoke_request.module_root,
            game=request.smoke_request.game,
            output_dir=request.output_dir,
            room_resref=request.smoke_request.room_resref,
            width=request.smoke_request.width,
            depth=request.smoke_request.depth,
            wall_height=request.smoke_request.wall_height,
            surface_id=request.smoke_request.surface_id,
            room_texture=request.smoke_request.room_texture,
            player_start=request.smoke_request.player_start,
            player_facing=request.smoke_request.player_facing,
            test_placeable_resref=request.smoke_request.test_placeable_resref,
            test_placeable_position=request.smoke_request.test_placeable_position,
            test_placeable_facing=request.smoke_request.test_placeable_facing,
            include_reference_check=request.smoke_request.include_reference_check,
            include_game_template_check=request.smoke_request.include_game_template_check,
            game_root_dir=request.smoke_request.game_root_dir,
            settings_path=request.smoke_request.settings_path,
            include_wok_check=request.smoke_request.include_wok_check,
            strict=request.smoke_request.strict,
        )
    return DevModuleSmokeRequest(output_dir=request.output_dir, game=request.game)


def _settings_json_path(explicit: str = "") -> Path:
    if explicit:
        return Path(explicit)
    return _repo_root_from_here() / "src" / "settings.json"


def _settings_game_root(game: str, settings_path: str = "") -> str:
    path = _settings_json_path(settings_path)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    key = "k2_dir" if str(game).upper() == "K2" else "k1_dir"
    return str(data.get(key) or "").strip()


def _game_modules_dir_from_root(root: str | Path) -> Path:
    return Path(root) / "Modules"


def _candidate_game_roots(game: str, *, explicit_root: str = "", settings_path: str = "") -> list[Path]:
    game_tag = str(game or "K1").upper()
    roots: list[str] = []
    if explicit_root:
        roots.append(explicit_root)
    env_keys = (
        ("GHOSTRIGGER_K2_DIR", "K2_PATH", "KOTOR2_PATH")
        if game_tag == "K2"
        else ("GHOSTRIGGER_K1_DIR", "K1_PATH", "KOTOR_PATH")
    )
    roots.extend(os.environ.get(key, "") for key in env_keys)
    roots.append(_settings_game_root(game_tag, settings_path))
    if game_tag == "K2":
        roots.extend(
            [
                r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
                r"C:\Program Files\Steam\steamapps\common\Knights of the Old Republic II",
                r"C:\GOG Games\Star Wars - KotOR2",
            ]
        )
    else:
        roots.extend(
            [
                r"C:\Program Files (x86)\Steam\steamapps\common\swkotor",
                r"C:\Program Files\Steam\steamapps\common\swkotor",
                r"C:\GOG Games\Star Wars - KotOR",
            ]
        )
    seen: set[str] = set()
    candidates: list[Path] = []
    for root in roots:
        if not root:
            continue
        path = Path(root).expanduser()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def discover_kotor_modules_dir(
    game: str = "K1",
    *,
    explicit_modules_dir: str = "",
    game_root_dir: str = "",
    settings_path: str = "",
) -> str:
    """Resolve the safest known KOTOR ``Modules`` folder for smoke install prep."""

    if explicit_modules_dir:
        modules = Path(explicit_modules_dir)
        return str(modules) if modules.is_dir() else ""
    for root in _candidate_game_roots(game, explicit_root=game_root_dir, settings_path=settings_path):
        modules = _game_modules_dir_from_root(root)
        if modules.is_dir():
            return str(modules)
    return ""


def _game_test_steps(module_root: str) -> list[str]:
    return [
        f"Install/copy `{module_root}.mod` into the selected KOTOR `Modules` folder.",
        "Launch the matching KOTOR game.",
        f"Open the console and run `warp {module_root}`.",
        "Confirm the module loads without crashing or falling back to another area.",
        "Confirm the player appears on the generated floor, not in the void.",
        "Confirm the test placeable appears near the expected location.",
        "Walk across the generated floor and confirm movement is not blocked unexpectedly.",
        "Capture a screenshot or short clip as proof.",
    ]


def _write_install_proof_files(
    *,
    output_root: Path,
    export_result: DevModuleSmokeResult,
    game: str,
    install_path: str,
    installed: bool,
    dry_run: bool,
    warnings: list[str],
    blocking: list[str],
) -> tuple[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    module_root = export_result.module_root or "grdev01"
    checklist_path = output_root / f"{module_root}_in_game_smoke_checklist.md"
    proof_manifest_path = output_root / f"{module_root}_in_game_smoke_manifest.json"
    steps = _game_test_steps(module_root)
    checklist_lines = [
        f"# {module_root} In-Game Smoke Test",
        "",
        "This checklist is the manual proof gate for T2601. The module is not game-tested until these boxes are checked from an actual KOTOR run.",
        "",
        f"- Package: `{export_result.module_path}`",
        f"- Install target: `{install_path or '(not installed)'}`",
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
        "task": "T2601",
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
        },
        "manual_proof_required": True,
        "warp_command": f"warp {module_root}",
        "acceptance_checks": [
            "module_loads_in_game",
            "player_spawns_on_floor",
            "test_placeable_visible",
            "player_can_walk_on_floor",
            "screenshot_or_video_captured",
        ],
        "steps": steps,
        "warnings": warnings,
        "blocking_issues": blocking,
    }
    proof_manifest_path.write_text(json.dumps(proof_manifest, indent=2), encoding="utf-8")
    return str(checklist_path), str(proof_manifest_path)


def prepare_dev_test_module_install(request: DevModuleInstallPrepRequest | None = None) -> DevModuleInstallPrepResult:
    """Safely stage ``grdev01.mod`` for a manual in-game ``warp grdev01`` test."""

    request = request or DevModuleInstallPrepRequest()
    smoke_request = _install_prep_smoke_request(request)
    export_result = export_dev_test_module(smoke_request)
    output_root = Path(smoke_request.output_dir or request.output_dir or ".")
    warnings = list(export_result.warnings)
    blocking = list(export_result.blocking_issues)
    installed = False
    install_path = ""
    modules_dir_text = request.game_modules_dir
    if not modules_dir_text and request.auto_detect_game_modules_dir:
        modules_dir_text = discover_kotor_modules_dir(
            smoke_request.game,
            game_root_dir=request.game_root_dir,
            settings_path=request.settings_path,
        )
        if modules_dir_text:
            warnings.append(f"Auto-detected KOTOR Modules folder: {modules_dir_text}")
        else:
            warnings.append("Could not auto-detect a KOTOR Modules folder; package is staged for manual install.")
    if not export_result.ok:
        blocking.append(export_result.message or "Smoke module export failed.")
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
                    shutil.copy2(export_result.module_path, destination)
                    installed = True
    checklist_path, proof_manifest_path = _write_install_proof_files(
        output_root=output_root,
        export_result=export_result,
        game=smoke_request.game,
        install_path=install_path,
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
    return DevModuleInstallPrepResult(
        ok=ok,
        export_result=export_result,
        installed_module_path=install_path if installed else "",
        resolved_modules_dir=modules_dir_text,
        checklist_path=checklist_path,
        proof_manifest_path=proof_manifest_path,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            f"Installed {export_result.module_root}.mod to {install_path}."
            if installed
            else "Smoke module staged with manual in-game checklist."
        ),
        code=code,
    )


__all__ = [
    "AuthoredDevModule",
    "DevModuleInstallPrepRequest",
    "DevModuleInstallPrepResult",
    "DevModuleResourceSummary",
    "DevModuleSmokeRequest",
    "DevModuleSmokeResult",
    "build_dev_test_module",
    "discover_kotor_modules_dir",
    "export_dev_test_module",
    "prepare_dev_test_module_install",
    "verify_dev_test_module_package",
]
