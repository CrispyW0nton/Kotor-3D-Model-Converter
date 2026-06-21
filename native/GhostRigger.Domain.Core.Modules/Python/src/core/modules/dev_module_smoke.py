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
    validate_authored_gameplay_placement_against_walkmesh,
)
from .authored_room_geometry import (
    AuthoredRoomGeometry,
    PrimitiveMesh,
    RectangularRoomPrimitive,
)
from .authored_module_lighting import AuthoredRoomLight, authored_room_light_payload
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id
from .authored_module_project import (
    AuthoredModuleProject,
    compile_authored_room_spec,
    create_floor_plan_room_project,
    create_single_room_project,
    validate_authored_module_project,
)
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
from .authored_room_primitives import PrimitiveMaterial
from .authored_module_layout import compile_authored_module_layout
from .authored_module_metadata import AuthoredAreaMetadata, authored_module_id_bytes, compile_authored_module_metadata
from .authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
from .authored_room_materials import (
    AuthoredRoomMaterialPreflight,
    DEFAULT_AUTHORED_ROOM_TEXTURE,
    compile_authored_room_material_preflight,
    normalize_authored_room_texture,
)
from .authored_walkmesh_boundaries import apply_authored_walkmesh_boundary_policy_to_geometry
from .module_format import LYTLayout, VISData, WOKData


ENGINE_MODULE_IFO_RESREF = "module"


def _is_k2_game(game: str) -> bool:
    return str(game or "").strip().upper() == "K2"


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
    room_texture: str = DEFAULT_AUTHORED_ROOM_TEXTURE
    room_geometry_mode: str = "rectangular_composition"
    floor_plan_opening: bool = True
    floor_plan_opening_edge_index: int = 2
    floor_plan_opening_width: float = 1.5
    floor_plan_opening_height: float = 2.1
    include_doorway_marker: bool = True
    player_start: tuple[float, float, float] = (0.0, -3.0, 0.0)
    player_facing: float = 0.0
    include_test_placeable: bool = True
    include_start_waypoint: bool = True
    include_basic_light: bool = True
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
    module_id_hex: str = ""
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
    material_preflight: AuthoredRoomMaterialPreflight | None = None
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
class DevModuleSmokeVariantSuiteRequest:
    """Options for staging every supported smoke-module variant for manual QA."""

    output_dir: str = ""
    game: str = "K1"
    include_rectangular_composition: bool = True
    include_floor_plan_opening: bool = True
    game_modules_dir: str = ""
    game_root_dir: str = ""
    settings_path: str = ""
    auto_detect_game_modules_dir: bool = False


@dataclass
class DevModuleSmokeVariantPrep:
    """One staged smoke-module variant within the suite."""

    variant_id: str
    label: str
    room_geometry_mode: str
    prep_result: DevModuleInstallPrepResult
    module_path: str = ""
    pack_manifest_path: str = ""
    checklist_path: str = ""
    proof_manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


@dataclass
class DevModuleSmokeVariantSuiteResult:
    """Result for staging the rectangular and floor-plan smoke variants."""

    ok: bool = False
    output_dir: str = ""
    suite_checklist_path: str = ""
    suite_manifest_path: str = ""
    resolved_modules_dir: str = ""
    variants: list[DevModuleSmokeVariantPrep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_prepared"


@dataclass(frozen=True)
class DevModuleGameProofRequest:
    """Evidence supplied after a real ``warp grdev01`` in-game smoke test."""

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
class DevModuleGameProofResult:
    """Result of recording in-game smoke proof for the dev module."""

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
        texture=normalize_authored_room_texture(request.room_texture),
        include_doorway_marker=bool(request.include_doorway_marker),
    )


def _floor_plan_room_primitive(request: DevModuleSmokeRequest) -> FloorPlanRoomPrimitive:
    half_w = float(request.width) * 0.5
    half_d = float(request.depth) * 0.5
    openings: tuple[FloorPlanWallOpening, ...] = ()
    if request.floor_plan_opening:
        openings = (
            FloorPlanWallOpening(
                name="doorway_opening",
                edge_index=int(request.floor_plan_opening_edge_index),
                center_fraction=0.5,
                width=float(request.floor_plan_opening_width),
                height=float(request.floor_plan_opening_height),
                metadata={"source": "map_studio:t2614"},
            ),
        )
    return FloorPlanRoomPrimitive(
        room_resref=_normalise_resref(request.room_resref),
        points=(
            (-half_w, -half_d),
            (half_w, -half_d),
            (half_w, half_d),
            (-half_w, half_d),
        ),
        wall_height=float(request.wall_height),
        floor_surface_id=resolve_walkmesh_surface_id(request.surface_id),
        material=PrimitiveMaterial(texture=normalize_authored_room_texture(request.room_texture)),
        openings=openings,
        metadata={
            "geometry_mode": "floor_plan",
            "source": "map_studio:t2614",
        },
    )


def _make_gameplay_placement(request: DevModuleSmokeRequest) -> AuthoredGameplayPlacement:
    root = _normalise_resref(request.module_root)
    placeables = ()
    if request.include_test_placeable:
        placeables = (
            AuthoredPlaceableInstance(
                template_resref=_normalise_resref(request.test_placeable_resref),
                tag="grdev01_test_placeable",
                position=tuple(float(value) for value in request.test_placeable_position),  # type: ignore[arg-type]
                bearing=float(request.test_placeable_facing),
            ),
        )
    waypoints = ()
    if request.include_start_waypoint:
        waypoints = (
            AuthoredWaypointInstance(
                template_resref="sw_startloc001",
                tag="start",
                position=tuple(float(value) for value in request.player_start),  # type: ignore[arg-type]
                bearing=float(request.player_facing),
            ),
        )
    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(
            area_resref=root,
            position=tuple(float(value) for value in request.player_start),  # type: ignore[arg-type]
            facing=float(request.player_facing),
        ),
        placeables=placeables,
        waypoints=waypoints,
        metadata={
            "source": "map_studio:t2601",
            "player_start_is_module_entry": True,
            "placeable_count": len(placeables),
            "waypoint_count": len(waypoints),
            "include_test_placeable": bool(request.include_test_placeable),
            "include_start_waypoint": bool(request.include_start_waypoint),
            "include_basic_light": bool(request.include_basic_light),
        },
    )


def _make_room_lights(request: DevModuleSmokeRequest) -> tuple[AuthoredRoomLight, ...]:
    if not request.include_basic_light:
        return ()
    root = _normalise_resref(request.module_root)
    room_resref = _normalise_resref(request.room_resref or f"{root}_room01")
    return (
        AuthoredRoomLight(
            name=f"{root}_key_light"[:32],
            room_resref=room_resref,
            position=(0.0, -1.5, 2.45),
            color=(1.0, 0.92, 0.76),
            radius=8.0,
            intensity=1.0,
            light_type="point",
            metadata={
                "source": "map_studio:dev_test_smoke_light",
                "purpose": "canonical_smoke_visibility",
            },
        ),
    )


def _make_authored_project(request: DevModuleSmokeRequest) -> AuthoredModuleProject:
    mode = str(request.room_geometry_mode or "rectangular_composition").strip().lower()
    if mode in {"floor_plan", "floorplan", "floor-plan"}:
        return create_floor_plan_room_project(
            module_root=request.module_root,
            game=request.game,
            display_name="GhostRigger Dev Test",
            floor_plan=_floor_plan_room_primitive(request),
            placements=_make_gameplay_placement(request),
            lights=_make_room_lights(request),
            notes=(
                "T2601 from-scratch smoke module.",
                "Generated from authored floor-plan extrusion geometry and authored gameplay placements.",
            ),
            metadata={
                "task": "T2601",
                "source": "map_studio:authored_project",
                "room_geometry_mode": "floor_plan",
            },
        )
    if mode not in {"rectangular_composition", "rectangular", "composition"}:
        raise ValueError(f"Unsupported dev module room geometry mode: {request.room_geometry_mode!r}")
    return create_single_room_project(
        module_root=request.module_root,
        game=request.game,
        display_name="GhostRigger Dev Test",
        room_primitive=_room_primitive(request),
        placements=_make_gameplay_placement(request),
        lights=_make_room_lights(request),
        notes=(
            "T2601 from-scratch smoke module.",
            "Generated from authored primitive geometry and authored gameplay placements.",
        ),
        metadata={
            "task": "T2601",
            "source": "map_studio:authored_project",
            "room_geometry_mode": "rectangular_composition",
        },
    )


def _smoke_walkability_label(label: str) -> str | None:
    if label == "entry_point":
        return "player_start"
    if label.startswith("placeable:"):
        return "test_placeable"
    return None


def _validate_gameplay_anchors(placements: AuthoredGameplayPlacement, wok: WOKData) -> list[DevModuleWalkabilityCheck]:
    validation = validate_authored_gameplay_placement_against_walkmesh(placements, wok)
    checks: list[DevModuleWalkabilityCheck] = []
    for check in validation.checks:
        smoke_label = _smoke_walkability_label(check.label)
        if smoke_label is None:
            continue
        checks.append(
            DevModuleWalkabilityCheck(
                label=smoke_label,
                position=check.position,
                ok=check.ok,
                face_index=check.face_index,
                surface_id=check.surface_id,
                message=check.message.replace(check.label, smoke_label, 1),
            )
        )
    return checks


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
    model.disable_fog = True
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
    geometry = compile_authored_room_spec(room_spec)
    geometry = apply_authored_walkmesh_boundary_policy_to_geometry(geometry, wall_height=float(request.wall_height))
    placements = project.placements
    compiled_metadata = compile_authored_module_metadata(
        project.metadata,
        placements.entry_point,
        area=AuthoredAreaMetadata(
            name=project.metadata.display_name,
            tag=project.module_root,
            comments="Generated by GhostRigger Map Studio T2601 smoke builder.",
        ),
        room_resrefs=(room,),
        area_resrefs=(root,),
    )
    layout = compile_authored_module_layout(project)
    lyt = layout.lyt
    vis = layout.vis
    wok = geometry.wok
    walkability_checks = _validate_gameplay_anchors(placements, wok)
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
    material_game_root = _game_root_for_template_check(request) if request.include_game_template_check else ""
    material_preflight = compile_authored_room_material_preflight(
        geometry.room_mesh.texture,
        game_root_dir=material_game_root,
        require_game_resolution=False,
    )
    module_state = _ModuleState(name=root, lyt=lyt, vis=vis, room_woks={room: wok}, room_geometry=geometry, placements=placements)

    packaged = [
        _make_packaged(root, "are", compiled_metadata.are_bytes, "map_studio:t2601:are"),
        _make_packaged(root, "git", _make_git_bytes(request), "map_studio:t2601:git"),
        _make_packaged(ENGINE_MODULE_IFO_RESREF, "ifo", compiled_metadata.ifo_bytes, "map_studio:t2601:ifo"),
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
    warnings.extend(material_preflight.warnings)
    if not request.include_reference_check:
        warnings.append("Game-library template reference validation is disabled for this smoke package.")
    blocking = [check.message for check in walkability_checks if not check.ok]
    blocking.extend(check.message for check in template_checks if not check.ok)
    blocking.extend(material_preflight.blocking_issues)
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
        material_preflight=material_preflight,
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


def _gff_root(data: bytes) -> Any:
    from pykotor.resource.formats.gff import read_gff

    return read_gff(data).root


def _gff_root_labels(root: Any) -> set[str]:
    return {str(label) for label, _field_type, _value in root}


def _require_gff_fields(root: Any, owner: str, labels: tuple[str, ...], blocking: list[str]) -> None:
    present = _gff_root_labels(root)
    for label in labels:
        if label not in present:
            blocking.append(f"{owner} is missing KOTOR engine field {label}.")


def _list_length(value: Any) -> int:
    try:
        return len(value)
    except Exception:
        return -1


def _verify_ifo_engine_contract(data: bytes, module_root: str, blocking: list[str]) -> str:
    root = _gff_root(data)
    _require_gff_fields(
        root,
        "module.ifo",
        (
            "Mod_ID",
            "Mod_Creator_ID",
            "Mod_Version",
            "Mod_VO_ID",
            "Expansion_Pack",
            "Mod_Name",
            "Mod_Tag",
            "Mod_Hak",
            "Mod_Description",
            "Mod_IsSaveGame",
            "Mod_Entry_Area",
            "Mod_Expan_List",
            "Mod_CutSceneList",
            "Mod_GVar_List",
            "Mod_Area_list",
        ),
        blocking,
    )
    area_list = root.get("Mod_Area_list")
    raw_module_id = bytes(root.get("Mod_ID") or b"")
    module_id_hex = raw_module_id.hex()
    if len(raw_module_id) != 16:
        blocking.append(f"module.ifo Mod_ID must be 16 bytes; found {len(raw_module_id)} byte(s).")
    expected_module_id = authored_module_id_bytes(module_root)
    if raw_module_id and raw_module_id != expected_module_id:
        blocking.append(
            "module.ifo Mod_ID does not match GhostRigger's authored module identity "
            f"for {module_root}: got {module_id_hex}, expected {expected_module_id.hex()}."
        )
    if _list_length(area_list) < 1:
        blocking.append("module.ifo Mod_Area_list must contain the authored area resref.")
        return module_id_hex
    first_area = str(area_list.at(0).get("Area_Name") or "").lower()
    if first_area != module_root:
        blocking.append(f"module.ifo Mod_Area_list first Area_Name is {first_area or '(blank)'}, expected {module_root}.")
    if str(root.get("Mod_Tag") or "") != "MODULE":
        blocking.append("module.ifo Mod_Tag must be stock-style MODULE for K1 runtime loading.")
    try:
        description_count = len(root.get("Mod_Description"))
    except Exception:
        description_count = -1
    if description_count != 0:
        blocking.append("module.ifo Mod_Description must be an empty locstring for the dev smoke module.")
    return module_id_hex


def _verify_are_engine_contract(data: bytes, module_root: str, room: str, blocking: list[str], *, game: str = "K1") -> None:
    root = _gff_root(data)
    _require_gff_fields(
        root,
        f"{module_root}.are",
        (
            "ID",
            "Creator_ID",
            "Version",
            "Tag",
            "Name",
            "Map",
            "Expansion_List",
            "AlphaTest",
            "CameraStyle",
            "SunAmbientColor",
            "SunDiffuseColor",
            "SunFogOn",
            "SunFogNear",
            "SunFogFar",
            "SunFogColor",
            "DynAmbientColor",
            "LoadScreenID",
            "Rooms",
            "OnEnter",
            "OnExit",
            "OnHeartbeat",
            "OnUserDefined",
        ),
        blocking,
    )
    rooms = root.get("Rooms")
    if _list_length(rooms) < 1:
        blocking.append(f"{module_root}.are Rooms must contain at least one room model.")
        return
    room_names = {str(rooms.at(index).get("RoomName") or "").lower() for index in range(len(rooms))}
    if room not in room_names:
        blocking.append(f"{module_root}.are Rooms does not reference room model {room}.")
    try:
        unescapable = root.get_uint8("Unescapable")
    except Exception:
        unescapable = None
    if not _is_k2_game(game) and unescapable != 1:
        blocking.append(f"{module_root}.are Unescapable must be 1 for K1 stock-shape smoke modules.")


def _verify_git_engine_contract(data: bytes, module_root: str, blocking: list[str]) -> None:
    root = _gff_root(data)
    _require_gff_fields(
        root,
        f"{module_root}.git",
        (
            "UseTemplates",
            "AreaProperties",
            "CameraList",
            "Creature List",
            "Door List",
            "TriggerList",
            "Encounter List",
            "SoundList",
            "StoreList",
            "List",
            "Placeable List",
            "WaypointList",
        ),
        blocking,
    )
    area_properties = root.get("AreaProperties")
    if area_properties is None:
        return
    _require_gff_fields(
        area_properties,
        f"{module_root}.git AreaProperties",
        (
            "AmbientSndDay",
            "AmbientSndNight",
            "AmbientSndDayVol",
            "AmbientSndNitVol",
            "EnvAudio",
            "MusicBattle",
            "MusicDay",
            "MusicNight",
            "MusicDelay",
        ),
        blocking,
    )


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
    game: str = "K1",
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
        (ENGINE_MODULE_IFO_RESREF, "ifo"),
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
    module_id_hex = ""
    path_point_count = 0
    path_connection_count = 0
    for resref, restype in (
        (module_root, "are"),
        (module_root, "git"),
        (ENGINE_MODULE_IFO_RESREF, "ifo"),
        (module_root, "pth"),
    ):
        key = (resref, restype)
        if key not in payloads:
            continue
        try:
            content = _gff_content_name(payloads[key][1])
            if content != restype:
                blocking.append(f"{resref}.{restype} parsed as {content.upper()}, expected {restype.upper()}.")
            else:
                parsed_gff.append(f"{resref}.{restype}")
                if restype == "ifo":
                    module_id_hex = _verify_ifo_engine_contract(payloads[key][1], module_root, blocking)
                elif restype == "are":
                    _verify_are_engine_contract(payloads[key][1], module_root, room, blocking, game=game)
                elif restype == "git":
                    _verify_git_engine_contract(payloads[key][1], module_root, blocking)
                if restype == "pth":
                    path_point_count, path_connection_count = _pth_counts(payloads[key][1])
                    if path_point_count < 1:
                        blocking.append(f"{resref}.pth parsed but contains no path points.")
        except Exception as exc:
            blocking.append(f"{resref}.{restype} did not parse as GFF: {exc}")

    parsed_wok: list[str] = []
    wok_key = (room, "wok")
    if wok_key in payloads:
        try:
            from pykotor.resource.formats.bwm import read_bwm

            bwm = read_bwm(payloads[wok_key][1], regenerate_derived=True)
            faces = list(getattr(bwm, "faces", ()) or ())
            walkable_count = sum(
                1
                for face in faces
                if getattr(getattr(face, "material", None), "walkable", lambda: False)()
            )
            if not faces:
                blocking.append(f"{room}.wok parsed without walkmesh faces.")
            elif walkable_count < 1:
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
        module_id_hex=module_id_hex,
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
        "module_id_hex": verification.module_id_hex,
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
    geometry = authored.module.room_geometry
    geometry_metadata = dict(geometry.metadata) if geometry else {}
    geometry_primitive = str(geometry_metadata.get("primitive") or "unknown")
    helper_meshes = list(geometry.helper_meshes) if geometry else []
    helper_mesh_names = [mesh.name for mesh in helper_meshes]
    has_doorway_marker = any(mesh.metadata.get("primitive") == "doorway_marker" or "door_marker" in mesh.name for mesh in helper_meshes)
    has_wall_opening = int(geometry_metadata.get("opening_count") or 0) > 0
    data["map_studio_smoke_test"] = {
        "task": "T2601",
        "module_root": authored.module_root,
        "room_resref": _normalise_resref(request.room_resref),
        "authored_from_scratch": True,
        "capability_stage": "export_candidate",
        "game_tested": False,
        "warp_command": f"warp {authored.module_root}",
        "contains": {
            "primitive_composition_room": geometry_primitive == "authored_room_composition",
            "floor_plan_room": geometry_primitive == "floor_plan_extrusion",
            "simple_doorway_marker": has_doorway_marker,
            "wall_opening": has_wall_opening,
            "room_mdl_mdx": True,
            "floor_walkmesh": True,
            "walkmesh_boundary_walls": int(geometry_metadata.get("walkmesh_boundary_wall_faces") or 0) > 0,
            "simple_authored_lighting": bool(authored.project and authored.project.lights),
            "player_start": True,
            "test_placeable_template": request.test_placeable_resref,
        },
        "authored_project": {
            "source": "src.core.modules.authored_module_project",
            "module_root": authored.project.module_root if authored.project else authored.module_root,
            "game": authored.project.game if authored.project else authored.game,
            "display_name": authored.project.metadata.display_name if authored.project else "",
            "room_count": len(authored.project.rooms) if authored.project else 0,
            "light_count": len(authored.project.lights) if authored.project else 0,
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
            "engine_ifo_resref": ENGINE_MODULE_IFO_RESREF,
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
            "source": geometry.metadata.get("source", "src.core.modules.authored_room_geometry")
            if geometry
            else "unknown",
            "primitive": geometry_primitive,
            "room_mesh": geometry.room_mesh.name if geometry else "",
            "texture": geometry.room_mesh.texture if geometry else "",
            "helper_meshes": helper_mesh_names,
            "derived_wok": True,
            "wok_faces": len(getattr(geometry.wok, "faces", []) or []) if geometry else 0,
            "wok_walkable_faces": int(geometry.wok.walkable_face_count()) if geometry and hasattr(geometry.wok, "walkable_face_count") else 0,
            "wok_non_walk_faces": int(geometry.wok.non_walk_face_count()) if geometry and hasattr(geometry.wok, "non_walk_face_count") else 0,
            "walkmesh_boundary_wall_faces": int(geometry_metadata.get("walkmesh_boundary_wall_faces") or 0),
            "metadata": geometry_metadata,
        },
        "authored_materials": {
            "source": authored.material_preflight.metadata.get("source", "src.core.modules.authored_room_materials")
            if authored.material_preflight
            else "unknown",
            "texture": authored.material_preflight.texture if authored.material_preflight else "",
            "resolved": authored.material_preflight.resolved if authored.material_preflight else False,
            "source_path": authored.material_preflight.source_path if authored.material_preflight else "",
            "source_kind": authored.material_preflight.source_kind if authored.material_preflight else "",
            "message": authored.material_preflight.message if authored.material_preflight else "",
            "metadata": dict(authored.material_preflight.metadata) if authored.material_preflight else {},
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
        "authored_lighting": {
            "source": "src.core.modules.authored_module_lighting",
            "lighting_count": len(authored.project.lights) if authored.project else 0,
            "room_lights": [authored_room_light_payload(light) for light in (authored.project.lights if authored.project else ())],
            "lightmap_status": "viewport_lit_only" if authored.project and authored.project.lights else "not_started",
            "game_tested_lighting": False,
            "message": (
                "Authored room lights are editor/export intent; bake or verify lighting in-game before calling this game-tested."
                if authored.project and authored.project.lights
                else "No authored room lights are present in this smoke build."
            ),
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
            game=request.game,
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
            room_geometry_mode=request.smoke_request.room_geometry_mode,
            floor_plan_opening=request.smoke_request.floor_plan_opening,
            floor_plan_opening_edge_index=request.smoke_request.floor_plan_opening_edge_index,
            floor_plan_opening_width=request.smoke_request.floor_plan_opening_width,
            floor_plan_opening_height=request.smoke_request.floor_plan_opening_height,
            player_start=request.smoke_request.player_start,
            player_facing=request.smoke_request.player_facing,
            include_test_placeable=request.smoke_request.include_test_placeable,
            include_start_waypoint=request.smoke_request.include_start_waypoint,
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


def _derive_game_root_dir_from_modules_dir(modules_dir_text: str) -> str:
    if not modules_dir_text:
        return ""
    return str(Path(modules_dir_text).parent)


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


def _game_executable_name(game: str) -> str:
    return "swkotor2.exe" if str(game or "").upper() == "K2" else "swkotor.exe"


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


def _next_install_backup_path(path: Path) -> Path:
    candidate = path.with_suffix(path.suffix + ".bak")
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = path.with_suffix(path.suffix + f".bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _dev_launch_helper_command(*, proof_manifest_path: Path, game: str, game_root_dir: str) -> str:
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


def _write_dev_elevated_launch_script(
    *,
    output_root: Path,
    module_root: str,
    game: str,
    game_root_dir: str,
    proof_manifest_path: Path,
) -> str:
    if not game_root_dir:
        return ""
    executable = Path(game_root_dir) / _game_executable_name(game)
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
        f"echo GhostRigger Map Studio dev smoke test: {module_root}",
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


def _record_dev_proof_script_path() -> str:
    current = Path(__file__).resolve()
    for parent in current.parents:
        script_path = parent / "scripts" / "record_grdev01_smoke_proof.py"
        if script_path.is_file():
            return str(script_path)
    return "scripts\\record_grdev01_smoke_proof.py"


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
        "--player-spawns-on-floor",
    ]
    if include_test_placeable:
        flags.append("--test-placeable-visible")
    flags.append("--player-can-walk-on-floor")
    return f'python "{capture_path}" --proof-manifest "{proof_manifest_path}" ' + " ".join(flags)


def _write_dev_proof_recording_script(
    *,
    output_root: Path,
    module_root: str,
    proof_manifest_path: Path,
    include_test_placeable: bool = True,
) -> str:
    script_path = output_root / f"{module_root}_record_game_proof.cmd"
    recorder_path = _record_dev_proof_script_path()
    proof_path = proof_manifest_path.resolve()
    placeable_text = "the test placeable is visible, " if include_test_placeable else ""
    placeable_flag = "--test-placeable-visible " if include_test_placeable else ""
    lines = [
        "@echo off",
        "setlocal",
        f"echo GhostRigger Map Studio dev proof recorder: {module_root}",
        f"echo Proof manifest: {proof_path}",
        "echo.",
        f"echo Run this only after KOTOR has loaded the module with: warp {module_root}",
        f"echo Confirm the player spawns on the generated floor, {placeable_text}and walking works.",
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
            "--module-loads-in-game --player-spawns-on-floor "
            f"{placeable_flag}--player-can-walk-on-floor"
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


def _game_test_steps(module_root: str, *, include_test_placeable: bool = True) -> list[str]:
    steps = [
        f"Install/copy `{module_root}.mod` into the selected KOTOR `Modules` folder.",
        "Launch the matching KOTOR game.",
        f"Open the console and run `warp {module_root}`.",
        "Confirm the module loads without crashing or falling back to another area.",
        "Confirm the player appears on the generated floor, not in the void.",
    ]
    if include_test_placeable:
        steps.append("Confirm the test placeable appears near the expected location.")
    steps.extend(
        [
            "Walk across the generated floor and confirm movement is not blocked unexpectedly.",
            "Capture a screenshot or short clip as proof.",
        ]
    )
    return steps


def _dev_acceptance_checks(*, include_test_placeable: bool = True) -> list[str]:
    checks = [
        "module_loads_in_game",
        "player_spawns_on_floor",
    ]
    if include_test_placeable:
        checks.append("test_placeable_visible")
    checks.extend(
        [
            "player_can_walk_on_floor",
            "screenshot_or_video_captured",
        ]
    )
    return checks


def _write_install_proof_files(
    *,
    output_root: Path,
    export_result: DevModuleSmokeResult,
    game: str,
    install_path: str,
    backup_path: str,
    modules_dir: str,
    game_root_dir: str,
    installed: bool,
    dry_run: bool,
    warnings: list[str],
    blocking: list[str],
    include_test_placeable: bool = True,
) -> tuple[str, str, str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    module_root = export_result.module_root or "grdev01"
    checklist_path = output_root / f"{module_root}_in_game_smoke_checklist.md"
    proof_manifest_path = output_root / f"{module_root}_in_game_smoke_manifest.json"
    steps = _game_test_steps(module_root, include_test_placeable=include_test_placeable)
    executable_name = _game_executable_name(game)
    executable_path = str(Path(game_root_dir) / executable_name) if game_root_dir else executable_name
    launch_helper_command = _dev_launch_helper_command(
        proof_manifest_path=proof_manifest_path,
        game=game,
        game_root_dir=game_root_dir,
    )
    elevated_launch_script_path = _write_dev_elevated_launch_script(
        output_root=output_root,
        module_root=module_root,
        game=game,
        game_root_dir=game_root_dir,
        proof_manifest_path=proof_manifest_path,
    )
    proof_recording_script_path = _write_dev_proof_recording_script(
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
        f"# {module_root} In-Game Smoke Test",
        "",
        "This checklist is the manual proof gate for T2601. The module is not game-tested until these boxes are checked from an actual KOTOR run.",
        "",
        f"- Package: `{export_result.module_path}`",
        f"- Install target: `{install_path or '(not installed)'}`",
        f"- Previous module backup: `{backup_path or '(none)'}`",
        f"- Modules folder: `{modules_dir or '(not supplied)'}`",
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
        "acceptance_checks": _dev_acceptance_checks(include_test_placeable=include_test_placeable),
        "steps": steps,
        "warnings": warnings,
        "blocking_issues": blocking,
    }
    proof_manifest_path.write_text(json.dumps(proof_manifest, indent=2), encoding="utf-8")
    return str(checklist_path), str(proof_manifest_path), elevated_launch_script_path, proof_recording_script_path


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
    backup_path = ""
    modules_dir_text = request.game_modules_dir
    resolved_game_root_dir = request.game_root_dir
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
    if not resolved_game_root_dir and modules_dir_text:
        resolved_game_root_dir = _derive_game_root_dir_from_modules_dir(modules_dir_text)
    if not export_result.ok:
        blocking.append(export_result.message or "Smoke module export failed.")
    else:
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
    checklist_path, proof_manifest_path, elevated_launch_script_path, proof_recording_script_path = _write_install_proof_files(
        output_root=output_root,
        export_result=export_result,
        game=smoke_request.game,
        install_path=install_path,
        backup_path=backup_path,
        modules_dir=modules_dir_text,
        game_root_dir=resolved_game_root_dir,
        installed=installed,
        dry_run=request.dry_run,
        warnings=warnings,
        blocking=blocking,
        include_test_placeable=smoke_request.include_test_placeable,
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
        backup_module_path=backup_path,
        resolved_modules_dir=modules_dir_text,
        resolved_game_root_dir=resolved_game_root_dir,
        launch_helper_command=_dev_launch_helper_command(
            proof_manifest_path=Path(proof_manifest_path),
            game=smoke_request.game,
            game_root_dir=resolved_game_root_dir,
        ),
        elevated_launch_script_path=elevated_launch_script_path,
        proof_recording_script_path=proof_recording_script_path,
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


def _suite_variant_specs(request: DevModuleSmokeVariantSuiteRequest) -> list[tuple[str, str, str]]:
    specs: list[tuple[str, str, str]] = []
    if request.include_rectangular_composition:
        specs.append(("rectangular_composition", "Rectangular composition baseline", "rectangular_composition"))
    if request.include_floor_plan_opening:
        specs.append(("floor_plan_opening", "Floor-plan extrusion with wall opening", "floor_plan"))
    return specs


def _write_variant_suite_files(
    *,
    output_root: Path,
    request: DevModuleSmokeVariantSuiteRequest,
    variants: list[DevModuleSmokeVariantPrep],
    resolved_modules_dir: str,
    warnings: list[str],
    blocking: list[str],
) -> tuple[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    checklist_path = output_root / "grdev01_variant_suite_checklist.md"
    manifest_path = output_root / "grdev01_variant_suite_manifest.json"
    checklist_lines = [
        "# grdev01 Smoke Variant Suite",
        "",
        "This suite stages every supported Map Studio smoke-module geometry variant.",
        "Both variants intentionally produce `grdev01.mod`; test one variant at a time by copying that variant's package into the KOTOR `Modules` folder.",
        "",
        f"- Resolved Modules folder: `{resolved_modules_dir or '(not resolved)'}`",
        f"- Variant count: {len(variants)}",
        "",
        "## Variant Test Order",
        "",
    ]
    for variant in variants:
        checklist_lines.extend(
            [
                f"### {variant.label}",
                "",
                f"- Variant id: `{variant.variant_id}`",
                f"- Package: `{variant.module_path}`",
                f"- Pack manifest: `{variant.pack_manifest_path}`",
                f"- Variant proof manifest: `{variant.proof_manifest_path}`",
                f"- Variant checklist: `{variant.checklist_path}`",
                f"- Copy target: `{str(Path(resolved_modules_dir) / 'grdev01.mod') if resolved_modules_dir else 'Modules/grdev01.mod'}`",
                "- [ ] Copy this variant's `grdev01.mod` to the KOTOR `Modules` folder.",
                "- [ ] Launch the matching KOTOR game.",
                "- [ ] Run `warp grdev01`.",
                "- [ ] Confirm the room loads.",
                "- [ ] Confirm the player appears on the generated floor.",
                "- [ ] Confirm the test placeable appears.",
                "- [ ] Walk across the generated floor.",
                "- [ ] Capture screenshot/video evidence and record it in the variant proof manifest.",
                "",
            ]
        )
    manifest = {
        "task": "T2615",
        "module_root": "grdev01",
        "game": str(request.game or "K1").upper(),
        "manual_proof_required": True,
        "resolved_modules_dir": resolved_modules_dir,
        "install_policy": "stage_all_copy_one_variant_at_a_time",
        "warnings": warnings,
        "blocking_issues": blocking,
        "variants": [
            {
                "variant_id": variant.variant_id,
                "label": variant.label,
                "room_geometry_mode": variant.room_geometry_mode,
                "ok": variant.prep_result.ok,
                "code": variant.prep_result.code,
                "module_path": variant.module_path,
                "pack_manifest_path": variant.pack_manifest_path,
                "checklist_path": variant.checklist_path,
                "proof_manifest_path": variant.proof_manifest_path,
                "warnings": variant.warnings,
                "blocking_issues": variant.blocking_issues,
            }
            for variant in variants
        ],
    }
    checklist_path.write_text("\n".join(checklist_lines), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(checklist_path), str(manifest_path)


def prepare_dev_test_module_variant_suite(request: DevModuleSmokeVariantSuiteRequest | None = None) -> DevModuleSmokeVariantSuiteResult:
    """Stage every supported ``grdev01`` smoke geometry variant for manual game QA.

    The suite deliberately does not install all variants because they share the
    same module root.  Instead it writes one package per variant and a checklist
    that tells the tester to copy and prove one `grdev01.mod` at a time.
    """

    request = request or DevModuleSmokeVariantSuiteRequest()
    output_root = Path(request.output_dir or "artifacts/map_studio/grdev01_variant_suite")
    specs = _suite_variant_specs(request)
    warnings: list[str] = []
    blocking: list[str] = []
    variants: list[DevModuleSmokeVariantPrep] = []
    if not specs:
        blocking.append("Smoke variant suite requires at least one enabled variant.")
    resolved_modules_dir = request.game_modules_dir
    if not resolved_modules_dir and request.auto_detect_game_modules_dir:
        resolved_modules_dir = discover_kotor_modules_dir(
            request.game,
            game_root_dir=request.game_root_dir,
            settings_path=request.settings_path,
        )
        if resolved_modules_dir:
            warnings.append(f"Auto-detected KOTOR Modules folder: {resolved_modules_dir}")
        else:
            warnings.append("Could not auto-detect a KOTOR Modules folder; variants are staged for manual copy.")
    for variant_id, label, mode in specs:
        variant_output = output_root / variant_id
        prep = prepare_dev_test_module_install(
            DevModuleInstallPrepRequest(
                output_dir=str(variant_output),
                game=request.game,
                smoke_request=DevModuleSmokeRequest(
                    output_dir=str(variant_output),
                    game=request.game,
                    room_geometry_mode=mode,
                ),
            )
        )
        export_result = prep.export_result
        pack_manifest_path = export_result.manifest_path if export_result else ""
        module_path = export_result.module_path if export_result else ""
        variant = DevModuleSmokeVariantPrep(
            variant_id=variant_id,
            label=label,
            room_geometry_mode=mode,
            prep_result=prep,
            module_path=module_path,
            pack_manifest_path=pack_manifest_path,
            checklist_path=prep.checklist_path,
            proof_manifest_path=prep.proof_manifest_path,
            warnings=list(prep.warnings),
            blocking_issues=list(prep.blocking_issues),
        )
        variants.append(variant)
        warnings.extend(f"{variant_id}: {warning}" for warning in prep.warnings)
        blocking.extend(f"{variant_id}: {issue}" for issue in prep.blocking_issues)
    checklist_path, manifest_path = _write_variant_suite_files(
        output_root=output_root,
        request=request,
        variants=variants,
        resolved_modules_dir=resolved_modules_dir,
        warnings=warnings,
        blocking=blocking,
    )
    ok = bool(variants) and all(variant.prep_result.ok for variant in variants) and not blocking
    return DevModuleSmokeVariantSuiteResult(
        ok=ok,
        output_dir=str(output_root),
        suite_checklist_path=checklist_path,
        suite_manifest_path=manifest_path,
        resolved_modules_dir=resolved_modules_dir,
        variants=variants,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            "Smoke variant suite staged for manual in-game proof."
            if ok
            else "Smoke variant suite staging completed with blocking issue(s)."
        ),
        code="staged_variant_suite" if ok else "variant_suite_preflight_failed",
    )


def _proof_request_checks(request: DevModuleGameProofRequest) -> dict[str, bool]:
    return {
        "module_loads_in_game": bool(request.module_loads_in_game),
        "player_spawns_on_floor": bool(request.player_spawns_on_floor),
        "test_placeable_visible": bool(request.test_placeable_visible),
        "player_can_walk_on_floor": bool(request.player_can_walk_on_floor),
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


def _default_acceptance_checks() -> list[str]:
    return [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "test_placeable_visible",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]


def _update_pack_manifest_for_game_proof(
    *,
    pack_manifest_path: str,
    accepted: bool,
    proof_payload: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if not pack_manifest_path:
        warnings.append("No pack manifest path was available to update with in-game proof.")
        return warnings
    manifest_path = Path(pack_manifest_path)
    if not manifest_path.is_file():
        warnings.append(f"Pack manifest was not found for in-game proof update: {manifest_path}")
        return warnings
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"Pack manifest could not be read for in-game proof update: {exc}")
        return warnings
    smoke = manifest.setdefault("map_studio_smoke_test", {})
    smoke["game_tested"] = bool(accepted)
    if accepted:
        smoke["capability_stage"] = "game_smoke_tested"
        remaining = list(smoke.get("remaining_acceptance", []))
        smoke["remaining_acceptance"] = [
            item
            for item in remaining
            if not any(
                needle in str(item).lower()
                for needle in ("install/copy", "warp", "confirm the room loads", "confirm the player", "walk across")
            )
        ]
    smoke["in_game_proof"] = proof_payload
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return warnings


def record_dev_module_game_proof(request: DevModuleGameProofRequest) -> DevModuleGameProofResult:
    """Record the manual in-game proof gate for ``grdev01``.

    This intentionally does not infer success from generated files.  A smoke
    module becomes game-tested only when the caller supplies the concrete KOTOR
    acceptance checks plus a screenshot/video evidence path.
    """

    proof_manifest_path = Path(request.proof_manifest_path)
    if not proof_manifest_path.is_file():
        return DevModuleGameProofResult(
            ok=False,
            proof_manifest_path=str(proof_manifest_path),
            evidence_path=request.evidence_path,
            blocking_issues=[f"Proof manifest does not exist: {proof_manifest_path}"],
            message="Could not record in-game proof because the proof manifest is missing.",
            code="proof_manifest_missing",
        )
    try:
        proof = json.loads(proof_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return DevModuleGameProofResult(
            ok=False,
            proof_manifest_path=str(proof_manifest_path),
            evidence_path=request.evidence_path,
            blocking_issues=[f"Proof manifest could not be read: {exc}"],
            message="Could not record in-game proof because the proof manifest is unreadable.",
            code="proof_manifest_unreadable",
        )

    required = list(proof.get("acceptance_checks") or _default_acceptance_checks())
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
    if accepted:
        proof["completed_at"] = tested_at
    proof_manifest_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")

    pack_manifest_path = str((proof.get("package") or {}).get("pack_manifest_path") or "")
    warnings = _update_pack_manifest_for_game_proof(
        pack_manifest_path=pack_manifest_path,
        accepted=accepted,
        proof_payload=proof_payload,
    )
    blocking = [f"In-game acceptance check is incomplete: {name}" for name in missing]
    return DevModuleGameProofResult(
        ok=accepted,
        proof_manifest_path=str(proof_manifest_path),
        pack_manifest_path=pack_manifest_path,
        evidence_path=request.evidence_path,
        missing_checks=missing,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            "Recorded complete in-game smoke proof for grdev01."
            if accepted
            else "Recorded incomplete in-game smoke proof attempt; module remains unproven."
        ),
        code="game_proof_recorded" if accepted else "game_proof_incomplete",
    )


__all__ = [
    "AuthoredDevModule",
    "DevModuleGameProofRequest",
    "DevModuleGameProofResult",
    "DevModuleInstallPrepRequest",
    "DevModuleInstallPrepResult",
    "DevModuleResourceSummary",
    "DevModuleSmokeRequest",
    "DevModuleSmokeResult",
    "DevModuleSmokeVariantPrep",
    "DevModuleSmokeVariantSuiteRequest",
    "DevModuleSmokeVariantSuiteResult",
    "build_dev_test_module",
    "discover_kotor_modules_dir",
    "export_dev_test_module",
    "prepare_dev_test_module_install",
    "prepare_dev_test_module_variant_suite",
    "record_dev_module_game_proof",
    "verify_dev_test_module_package",
]
