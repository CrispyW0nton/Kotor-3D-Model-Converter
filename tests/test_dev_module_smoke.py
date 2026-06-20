from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2601_builds_from_scratch_dev_module_resources() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import authored_module_id_bytes
    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, build_dev_test_module
    from src.core.modules.authored_room_composition import compile_authored_room_composition, create_rectangular_room_composition
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive
    from src.core.modules.module_format import AREData, GITData, IFOData
    from pykotor.resource.formats.bwm import read_bwm
    from pykotor.resource.formats.gff import read_gff

    authored = build_dev_test_module(DevModuleSmokeRequest())
    keys = {(summary.resref, summary.restype) for summary in authored.resource_summaries}
    primitive = RectangularRoomPrimitive(room_resref="grdev01_room01")
    primitive_geometry = compile_authored_room_composition(create_rectangular_room_composition(primitive))
    are = AREData.from_bytes(authored.resources[("grdev01", "are")].data)
    git = GITData.from_bytes(authored.resources[("grdev01", "git")].data)
    ifo = IFOData.from_bytes(authored.resources[("module", "ifo")].data)
    raw_are = read_gff(authored.resources[("grdev01", "are")].data)
    raw_git = read_gff(authored.resources[("grdev01", "git")].data)
    raw_ifo = read_gff(authored.resources[("module", "ifo")].data)
    raw_wok = read_bwm(authored.resources[("grdev01_room01", "wok")].data)
    raw_mdl = authored.resources[("grdev01_room01", "mdl")].data
    lyt_text = authored.resources[("grdev01", "lyt")].data.decode("ascii")
    vis_text = authored.resources[("grdev01", "vis")].data.decode("ascii")

    assert authored.module_root == "grdev01"
    assert authored.project is not None
    assert authored.project.module_root == "grdev01"
    assert authored.project.game == "K1"
    assert authored.project.rooms[0].normalised_resref() == "grdev01_room01"
    assert authored.project.rooms[0].composition is not None
    assert authored.project.metadata.metadata["task"] == "T2601"
    assert ("grdev01", "are") in keys
    assert ("grdev01", "git") in keys
    assert ("module", "ifo") in keys
    assert ("grdev01", "lyt") in keys
    assert ("grdev01", "vis") in keys
    assert ("grdev01", "pth") in keys
    assert ("grdev01_room01", "mdl") in keys
    assert ("grdev01_room01", "mdx") in keys
    assert ("grdev01_room01", "wok") in keys
    assert "grdev01_room01" in authored.module.lyt.to_text()
    assert authored.module.room_woks["grdev01_room01"].walkable_face_count() == 2
    assert authored.module.room_woks["grdev01_room01"].non_walk_face_count() == 8
    assert authored.module.room_geometry is not None
    assert authored.module.room_geometry.room_mesh.name == "grdev01_room01_mesh"
    assert authored.module.room_geometry.room_mesh.texture == "CM_Baremetal"
    assert authored.module.room_geometry.room_mesh.faces == primitive_geometry.room_mesh.faces
    assert authored.material_preflight is not None
    assert authored.material_preflight.texture == "CM_Baremetal"
    assert authored.material_preflight.blocking_issues == ()
    assert {mesh.name for mesh in authored.module.room_geometry.helper_meshes} >= {
        "grdev01_room01_wall_n",
        "grdev01_room01_wall_s",
        "grdev01_room01_wall_e",
        "grdev01_room01_wall_w",
        "grdev01_room01_door_marker",
    }
    assert authored.module.room_geometry.wok.walkable_face_count() == primitive_geometry.wok.walkable_face_count()
    assert authored.module.room_geometry.wok.non_walk_face_count() == 8
    assert authored.module.room_geometry.metadata["walkmesh_boundary_wall_faces"] == 8
    assert lyt_text.startswith("#MAXLAYOUT ASCII\n")
    assert "filedependancy grdev01.max\n" in lyt_text
    assert "beginlayout\n" in lyt_text
    assert "roomcount 1\n" in lyt_text
    assert "trackcount 0\n" in lyt_text
    assert "obstaclecount 0\n" in lyt_text
    assert "doorhookcount 0\n" in lyt_text
    assert lyt_text.rstrip().endswith("donelayout")
    assert vis_text == "grdev01_room01 1\n  grdev01_room01\n"
    assert authored.module.placements is not None
    assert authored.module.placements.entry_point.area_resref == "grdev01"
    assert authored.module.placements.placeables[0].template_resref == "plc_bench"
    assert authored.module.placements.waypoints[0].template_resref == "sw_startloc001"
    assert authored.module.placements.waypoints[0].tag == "start"
    if authored.template_reference_checks:
        template_keys = {
            (check.owner_type, check.resref, check.restype, check.ok)
            for check in authored.template_reference_checks
        }
        assert ("placeable", "plc_bench", "utp", True) in template_keys
        assert ("waypoint", "sw_startloc001", "utw", True) in template_keys
    assert len(git.placeables) == 1
    assert git.placeables[0].resref == "plc_bench"
    assert git.placeables[0].x == 1.75
    assert len(git.waypoints) == 1
    assert git.waypoints[0].tag == "start"
    assert git.waypoints[0].x == 0.0
    assert git.waypoints[0].y == -3.0
    assert are.name == "GhostRigger Dev Test"
    assert are.tag == "grdev01"
    assert are.fog_near == 100.0
    assert are.fog_far == 200.0
    assert ifo.entry_area == "grdev01"
    assert ifo.entry_y == -3.0
    assert ifo.mod_name == "GhostRigger Dev Test"
    assert ifo.tag == "MODULE"
    assert ifo.dawn_hour == 6
    assert ifo.dusk_hour == 18
    assert raw_ifo.root.get("Mod_Area_list").at(0).struct_id == 6
    assert str(raw_ifo.root.get("Mod_Area_list").at(0).get("Area_Name")) == "grdev01"
    assert raw_ifo.root.get("Mod_ID") == authored_module_id_bytes("grdev01")
    assert len(raw_ifo.root.get("Mod_ID")) == 16
    assert len(raw_ifo.root.get("Mod_Description")) == 0
    assert raw_are.root.get("Rooms").at(0).get("RoomName") == "grdev01_room01"
    assert raw_are.root.get_uint32("Version") == 193
    assert raw_are.root.get_uint32("Flags") == 7
    assert raw_are.root.get_int32("CameraStyle") == 1
    assert raw_are.root.get_single("Grass_Prob_LL") == 0.25
    assert raw_are.root.get_single("MoonFogNear") == 99.0
    assert raw_are.root.get_single("SunFogNear") == 99.0
    assert raw_are.root.get_uint8("ShadowOpacity") == 50
    assert raw_are.root.get_uint8("Unescapable") == 1
    assert not raw_are.root.exists("DisableTransit")
    assert not raw_are.root.exists("Natural")
    assert not raw_are.root.exists("FogColor")
    assert not raw_are.root.exists("SunFog")
    assert raw_git.root.get("AreaProperties").struct_id == 100
    assert raw_git.root.get("AreaProperties").get("MusicDelay") == 30000
    assert len(raw_git.root.get("List")) == 0
    raw_placeable = raw_git.root.get("Placeable List").at(0)
    raw_waypoint = raw_git.root.get("WaypointList").at(0)
    assert raw_placeable.struct_id == 9
    assert raw_waypoint.struct_id == 5
    assert raw_waypoint.exists("XOrientation")
    assert raw_waypoint.exists("YOrientation")
    assert not raw_waypoint.exists("Bearing")
    assert len(raw_wok.faces) == 10
    assert sum(1 for face in raw_wok.faces if face.material.walkable()) == 2
    room_root_offset = struct.unpack_from("<I", raw_mdl, 12 + 40)[0]
    room_anim_array_offset = struct.unpack_from("<I", raw_mdl, 12 + 88)[0]
    assert raw_mdl[12 + 83] == 1
    assert room_anim_array_offset == room_root_offset
    mesh_headers: list[tuple[tuple[float, float, float], tuple[float, float, float], float]] = []
    texture_offset = 0
    while True:
        texture_offset = raw_mdl.find(b"cm_baremetal", texture_offset)
        if texture_offset < 0:
            break
        mesh_header_offset = texture_offset - 88
        mesh_headers.append(
            (
                struct.unpack_from("<fff", raw_mdl, mesh_header_offset + 20),
                struct.unpack_from("<fff", raw_mdl, mesh_header_offset + 32),
                struct.unpack_from("<f", raw_mdl, mesh_header_offset + 44)[0],
            )
        )
        texture_offset += 1
    assert len(mesh_headers) >= 2
    assert all(bb_min != (0.0, 0.0, 0.0) or bb_max != (0.0, 0.0, 0.0) for bb_min, bb_max, _radius in mesh_headers)
    assert all(radius > 0.0 for _bb_min, _bb_max, radius in mesh_headers)
    assert authored.blocking_issues == []
    checks = {check.label: check for check in authored.walkability_checks}
    assert checks["player_start"].ok is True
    assert checks["test_placeable"].ok is True
    assert checks["player_start"].surface_id == 4
    assert checks["test_placeable"].surface_id == 4


def test_t2614_builds_floor_plan_smoke_room_with_wall_opening() -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, build_dev_test_module

    authored = build_dev_test_module(DevModuleSmokeRequest(room_geometry_mode="floor_plan"))

    assert authored.project is not None
    assert authored.project.metadata.metadata["room_geometry_mode"] == "floor_plan"
    assert authored.project.rooms[0].composition is None
    assert authored.module.room_geometry is not None
    assert authored.module.room_geometry.metadata["primitive"] == "floor_plan_extrusion"
    assert authored.module.room_geometry.metadata["opening_count"] == 1
    assert authored.module.room_geometry.metadata["wall_count"] == 6
    assert authored.module.room_geometry.room_mesh.name == "grdev01_room01_floor"
    assert authored.module.room_geometry.room_mesh.texture == "CM_Baremetal"
    helper_names = {mesh.name for mesh in authored.module.room_geometry.helper_meshes}
    assert {
        "grdev01_room01_wall_03_left",
        "grdev01_room01_wall_03_lintel",
        "grdev01_room01_wall_03_right",
    } <= helper_names
    assert authored.module.room_geometry.wok.walkable_face_count() == 2
    assert authored.module.room_geometry.wok.non_walk_face_count() == 8
    assert authored.module.room_geometry.metadata["walkmesh_boundary_wall_faces"] == 8
    assert authored.blocking_issues == []
    checks = {check.label: check for check in authored.walkability_checks}
    assert checks["player_start"].ok is True
    assert checks["test_placeable"].ok is True


def test_t2601_blocks_export_when_gameplay_anchor_is_off_walkmesh(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, export_dev_test_module

    result = export_dev_test_module(
        DevModuleSmokeRequest(
            output_dir=str(tmp_path),
            player_start=(99.0, 99.0, 0.0),
        )
    )

    assert result.ok is False
    assert result.code == "preflight_failed"
    assert any("player_start is outside" in issue for issue in result.blocking_issues)
    assert not (tmp_path / "install" / "Modules" / "grdev01.mod").exists()


def test_t2601_can_build_runtime_isolation_module_without_optional_placed_content() -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, build_dev_test_module
    from src.core.modules.module_format import GITData

    authored = build_dev_test_module(
        DevModuleSmokeRequest(
            include_test_placeable=False,
            include_start_waypoint=False,
        )
    )

    git = GITData.from_bytes(authored.resources[("grdev01", "git")].data)

    assert authored.module.placements is not None
    assert authored.module.placements.entry_point.area_resref == "grdev01"
    assert authored.module.placements.placeables == ()
    assert authored.module.placements.waypoints == ()
    assert len(git.placeables) == 0
    assert len(git.waypoints) == 0
    checks = {check.label: check for check in authored.walkability_checks}
    assert set(checks) == {"player_start"}
    assert checks["player_start"].ok is True
    assert authored.pathing_provenance["anchor_labels"] == ["player_start"]


def test_t2614_exports_floor_plan_smoke_manifest_with_opening_metadata(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, export_dev_test_module

    result = export_dev_test_module(DevModuleSmokeRequest(output_dir=str(tmp_path), room_geometry_mode="floor_plan"))

    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    smoke = manifest["map_studio_smoke_test"]
    assert smoke["contains"]["primitive_composition_room"] is False
    assert smoke["contains"]["floor_plan_room"] is True
    assert smoke["contains"]["simple_doorway_marker"] is False
    assert smoke["contains"]["wall_opening"] is True
    assert smoke["contains"]["walkmesh_boundary_walls"] is True
    assert smoke["authored_project"]["metadata"]["room_geometry_mode"] == "floor_plan"
    assert smoke["authored_geometry"]["source"] == "src.core.modules.authored_room_floorplan"
    assert smoke["authored_geometry"]["primitive"] == "floor_plan_extrusion"
    assert smoke["authored_geometry"]["room_mesh"] == "grdev01_room01_floor"
    assert smoke["authored_geometry"]["metadata"]["opening_count"] == 1
    assert smoke["authored_geometry"]["metadata"]["wall_count"] == 6
    assert smoke["authored_geometry"]["wok_walkable_faces"] == 2
    assert smoke["authored_geometry"]["wok_non_walk_faces"] == 8
    assert smoke["authored_geometry"]["walkmesh_boundary_wall_faces"] == 8
    assert "grdev01_room01_wall_03_lintel" in smoke["authored_geometry"]["helper_meshes"]
    assert smoke["package_verification"]["ok"] is True
    assert "grdev01_room01.mdl/.mdx" in smoke["package_verification"]["model_pairs"]


def test_t2601_can_stage_generated_room_without_doorway_marker(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, export_dev_test_module

    result = export_dev_test_module(DevModuleSmokeRequest(output_dir=str(tmp_path), include_doorway_marker=False))

    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    smoke = manifest["map_studio_smoke_test"]
    assert smoke["contains"]["simple_doorway_marker"] is False
    assert "grdev01_room01_door_marker" not in smoke["authored_geometry"]["helper_meshes"]
    assert smoke["authored_placements"]["counts"]["placeables"] == 1
    checks = {check["label"]: check for check in smoke["pre_game_checks"]["walkability_checks"]}
    assert checks["player_start"]["ok"] is True
    assert checks["test_placeable"]["ok"] is True


def test_t2601_exports_staged_mod_and_manifest(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import authored_module_id_bytes
    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, export_dev_test_module, verify_dev_test_module_package
    from src.core.modules.module_save_pipeline import RESTYPE_IDS
    from pykotor.resource.type import ResourceType

    result = export_dev_test_module(DevModuleSmokeRequest(output_dir=str(tmp_path)))

    assert RESTYPE_IDS["mdx"] == ResourceType.MDX.type_id
    assert RESTYPE_IDS["thg"] == ResourceType.THG.type_id
    assert RESTYPE_IDS["mdx"] != RESTYPE_IDS["thg"]
    assert result.ok is True
    assert result.code == "export_candidate"
    assert result.blocking_issues == []
    assert Path(result.module_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert result.package_verification is not None
    assert result.package_verification.ok is True
    assert set(result.package_verification.parsed_gff) == {"grdev01.are", "grdev01.git", "module.ifo", "grdev01.pth"}
    assert result.package_verification.parsed_wok == ("grdev01_room01.wok",)
    assert result.package_verification.model_pairs == ("grdev01_room01.mdl/.mdx",)

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    smoke = manifest["map_studio_smoke_test"]
    resources = {
        (resource["resref"], resource["restype"])
        for resource in manifest["source"]["resources"]
    }
    assert smoke["task"] == "T2601"
    assert smoke["authored_from_scratch"] is True
    assert smoke["game_tested"] is False
    assert smoke["warp_command"] == "warp grdev01"
    assert smoke["contains"]["primitive_composition_room"] is True
    assert smoke["contains"]["simple_doorway_marker"] is True
    assert smoke["contains"]["walkmesh_boundary_walls"] is True
    assert smoke["authored_project"]["source"] == "src.core.modules.authored_module_project"
    assert smoke["authored_project"]["module_root"] == "grdev01"
    assert smoke["authored_project"]["room_count"] == 1
    assert smoke["authored_project"]["metadata"]["task"] == "T2601"
    assert smoke["authored_layout"]["source"] == "src.core.modules.authored_module_layout"
    assert smoke["authored_layout"]["room_count"] == 1
    assert smoke["authored_layout"]["rooms"] == [
        {
            "resref": "grdev01_room01",
            "position": [0.0, 0.0, 0.0],
            "visible": ["grdev01_room01"],
        }
    ]
    assert smoke["authored_metadata"]["source"] == "src.core.modules.authored_module_metadata"
    assert smoke["authored_metadata"]["module_root"] == "grdev01"
    assert smoke["authored_metadata"]["engine_ifo_resref"] == "module"
    assert smoke["authored_metadata"]["display_name"] == "GhostRigger Dev Test"
    assert smoke["authored_metadata"]["tag"] == "grdev01"
    assert smoke["authored_metadata"]["fog_near"] == 100.0
    assert smoke["authored_metadata"]["fog_far"] == 200.0
    assert smoke["authored_metadata"]["dawn_hour"] == 6
    assert smoke["authored_metadata"]["dusk_hour"] == 18
    assert smoke["authored_pathing"]["source"] == "src.core.modules.authored_module_pathing"
    assert smoke["authored_pathing"]["point_count"] == 3
    assert smoke["authored_pathing"]["connection_count"] == 6
    assert smoke["authored_pathing"]["anchor_labels"] == ["player_start", "test_placeable"]
    assert smoke["authored_geometry"]["source"] == "src.core.modules.authored_room_composition"
    assert smoke["authored_geometry"]["primitive"] == "authored_room_composition"
    assert smoke["authored_geometry"]["room_mesh"] == "grdev01_room01_mesh"
    assert smoke["authored_geometry"]["texture"] == "CM_Baremetal"
    assert set(smoke["authored_geometry"]["helper_meshes"]) >= {
        "grdev01_room01_wall_n",
        "grdev01_room01_wall_s",
        "grdev01_room01_wall_e",
        "grdev01_room01_wall_w",
        "grdev01_room01_door_marker",
    }
    assert smoke["authored_geometry"]["metadata"]["compiled_mesh_count"] == 6
    assert smoke["authored_geometry"]["derived_wok"] is True
    assert smoke["authored_geometry"]["wok_walkable_faces"] == 2
    assert smoke["authored_geometry"]["wok_non_walk_faces"] == 8
    assert smoke["authored_geometry"]["walkmesh_boundary_wall_faces"] == 8
    assert smoke["authored_geometry"]["metadata"]["walkmesh_boundary_walls"]["source"] == "src.core.modules.authored_walkmesh_boundaries"
    assert smoke["authored_materials"]["source"] == "src.core.modules.authored_room_materials"
    assert smoke["authored_materials"]["texture"] == "CM_Baremetal"
    assert "CM_Baremetal" in smoke["authored_materials"]["message"]
    assert smoke["authored_placements"]["source"] == "src.core.modules.authored_module_objects"
    assert smoke["authored_placements"]["entry_area"] == "grdev01"
    assert smoke["authored_placements"]["counts"] == {
        "creatures": 0,
        "doors": 0,
        "triggers": 0,
        "encounters": 0,
        "sounds": 0,
        "cameras": 0,
        "stores": 0,
        "placeables": 1,
        "waypoints": 1,
    }
    assert smoke["authored_placements"]["creatures"] == []
    assert smoke["authored_placements"]["doors"] == []
    assert smoke["authored_placements"]["triggers"] == []
    assert smoke["authored_placements"]["placeables"][0]["template_resref"] == "plc_bench"
    assert smoke["authored_placements"]["waypoints"][0]["template_resref"] == "sw_startloc001"
    assert smoke["authored_placements"]["waypoints"][0]["tag"] == "start"
    assert smoke["pre_game_checks"]["gameplay_anchors_on_walkmesh"] is True
    if smoke["pre_game_checks"]["template_reference_checks"]:
        template_checks = {
            (check["owner_type"], check["resref"], check["restype"], check["ok"])
            for check in smoke["pre_game_checks"]["template_reference_checks"]
        }
        assert ("placeable", "plc_bench", "utp", True) in template_checks
        assert ("waypoint", "sw_startloc001", "utw", True) in template_checks
    assert smoke["package_verification"]["ok"] is True
    assert smoke["package_verification"]["code"] == "verified"
    assert "grdev01_room01.wok" in smoke["package_verification"]["parsed_wok"]
    assert "grdev01_room01.mdl/.mdx" in smoke["package_verification"]["model_pairs"]
    assert smoke["package_verification"]["path_point_count"] == 3
    assert smoke["package_verification"]["path_connection_count"] == 6
    checks = {
        check["label"]: check
        for check in smoke["pre_game_checks"]["walkability_checks"]
    }
    assert checks["player_start"]["ok"] is True
    assert checks["test_placeable"]["ok"] is True
    assert checks["player_start"]["surface_id"] == 4
    assert checks["test_placeable"]["surface_id"] == 4
    assert ("grdev01", "are") in resources
    assert ("grdev01", "git") in resources
    assert ("module", "ifo") in resources
    assert ("grdev01", "pth") in resources
    assert ("grdev01", "lyt") in resources
    assert ("grdev01", "vis") in resources
    assert ("grdev01_room01", "wok") in resources
    assert ("grdev01_room01", "mdl") in resources
    assert ("grdev01_room01", "mdx") in resources

    archive = Path(result.module_path).read_bytes()
    assert archive[:8] == b"MOD V1.0"
    resource_count = struct.unpack_from("<I", archive, 16)[0]
    keylist_offset = struct.unpack_from("<I", archive, 24)[0]
    expected_restypes = {"are", "git", "ifo", "pth", "lyt", "vis", "wok", "mdl", "mdx"}
    restype_by_id = {
        value: key
        for key, value in RESTYPE_IDS.items()
        if key in expected_restypes and key != "vis"
    }
    restype_by_id[RESTYPE_IDS["vis"]] = "vis"
    archive_keys = set()
    archive_type_ids = set()
    for index in range(resource_count):
        entry_offset = keylist_offset + index * 24
        resref = archive[entry_offset : entry_offset + 16].split(b"\x00", 1)[0].decode("ascii")
        _resource_id, restype_id, _unused = struct.unpack_from("<IHH", archive, entry_offset + 16)
        archive_keys.add((resref, restype_by_id[restype_id]))
        archive_type_ids.add((resref, restype_id))
    assert ("grdev01", "are") in archive_keys
    assert ("grdev01", "git") in archive_keys
    assert ("module", "ifo") in archive_keys
    assert ("grdev01", "pth") in archive_keys
    assert ("grdev01", "lyt") in archive_keys
    assert ("grdev01", "vis") in archive_keys
    assert ("grdev01_room01", "wok") in archive_keys
    assert ("grdev01_room01", "mdl") in archive_keys
    assert ("grdev01_room01", "mdx") in archive_keys
    assert ("grdev01_room01", ResourceType.MDX.type_id) in archive_type_ids
    assert ("grdev01_room01", ResourceType.THG.type_id) not in archive_type_ids

    verification = verify_dev_test_module_package(result.module_path)
    assert verification.ok is True
    assert verification.module_id_hex == authored_module_id_bytes("grdev01").hex()
    assert {f"{resource.resref}.{resource.restype}" for resource in verification.resources} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }


def test_t2601_package_verification_blocks_foreign_module_id(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from src.core.modules.custom_module_packager import CustomModulePackRequest, package_custom_module
    from src.core.modules.dev_module_smoke import DevModuleSmokeRequest, build_dev_test_module, verify_dev_test_module_package

    authored = build_dev_test_module(DevModuleSmokeRequest())
    foreign_module_id = bytes.fromhex("00112233445566778899aabbccddeeff")
    resources = []
    for resource in authored.packaged_resources:
        data = bytes(resource.data)
        if resource.key == ("module", "ifo"):
            gff = read_gff(data)
            gff.root.set_binary("Mod_ID", foreign_module_id)
            data = bytes_gff(gff)
        resources.append(
            type(resource)(
                resref=resource.resref,
                restype=resource.restype,
                data=data,
                source_path=resource.source_path,
                source=resource.source,
                required=resource.required,
            )
        )

    package = package_custom_module(
        authored,
        CustomModulePackRequest(
            module_root=authored.module_root,
            game=authored.game,
            output_dir=str(tmp_path),
            archive_mode="mod",
            create_backups=True,
            write_loose_resources=False,
            include_reference_check=False,
            include_wok_check=False,
            strict=True,
        ),
        resources=resources,
    )

    verification = verify_dev_test_module_package(package.module_path)

    assert package.ok is True
    assert verification.ok is False
    assert verification.module_id_hex == foreign_module_id.hex()
    assert any(
        "Mod_ID does not match GhostRigger's authored module identity" in issue
        for issue in verification.blocking_issues
    )


def test_t2601_install_prep_writes_manual_game_test_checklist(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    result = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "staged_for_manual_install"
    assert result.installed_module_path == ""
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    assert Path(result.proof_recording_script_path).is_file()
    assert "No KOTOR Modules folder was supplied" in "\n".join(result.warnings)
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    assert "warp grdev01" in checklist
    assert "Evidence capture helper:" in checklist
    assert "capture_grdev01_smoke_evidence.py" in checklist
    assert "Proof recorder:" in checklist
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    assert "record_grdev01_smoke_proof.py" in proof_recorder
    assert "--module-loads-in-game" in proof_recorder
    assert "Drag or paste screenshot/video evidence path" in proof_recorder
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert proof["install"]["installed"] is False
    assert proof["package"]["verification"]["ok"] is True
    assert proof["launch_handoff"]["warp_command"] == "warp grdev01"
    assert "capture_grdev01_smoke_evidence.py" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--record-proof" in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["launch_handoff"]["proof_recording_script_path"] == result.proof_recording_script_path
    assert proof["launch_handoff"]["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")
    assert proof["acceptance_checks"] == [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "test_placeable_visible",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]


def test_t2601_room_only_install_prep_omits_placeable_proof_requirement(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleInstallPrepRequest,
        DevModuleSmokeRequest,
        prepare_dev_test_module_install,
    )

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(
            output_dir=str(tmp_path),
            smoke_request=DevModuleSmokeRequest(
                include_test_placeable=False,
                include_start_waypoint=False,
            ),
        )
    )

    assert result.ok is True
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))

    assert "test placeable appears" not in checklist
    assert "--test-placeable-visible" not in proof_recorder
    assert "--test-placeable-visible" not in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["acceptance_checks"] == [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]


def test_t2601_install_prep_copies_to_modules_without_overwrite(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    output_dir = tmp_path / "out"

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(output_dir=str(output_dir), game_modules_dir=str(modules_dir))
    )

    installed = modules_dir / "grdev01.mod"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert installed.is_file()
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is True
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["launch_handoff"]["resolved_modules_dir"] == str(modules_dir)
    assert proof["launch_handoff"]["resolved_game_root_dir"] == str(modules_dir.parent)
    assert proof["launch_handoff"]["expected_executable_path"] == str(modules_dir.parent / "swkotor.exe")
    assert proof["launch_handoff"]["elevated_launch_script_path"] == result.elevated_launch_script_path
    assert "capture_grdev01_smoke_evidence.py" in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["launch_handoff"]["proof_recording_script_path"] == result.proof_recording_script_path

    installed.write_bytes(b"existing")
    blocked = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(output_dir=str(tmp_path / "blocked"), game_modules_dir=str(modules_dir))
    )
    assert blocked.ok is False
    assert blocked.code == "install_preflight_failed"
    assert any("already exists" in issue for issue in blocked.blocking_issues)
    assert installed.read_bytes() == b"existing"


def test_t2601_install_prep_writes_k2_launch_handoff(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    modules_dir = tmp_path / "KOTOR2" / "Modules"
    modules_dir.mkdir(parents=True)

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(output_dir=str(tmp_path / "out"), game="K2", game_modules_dir=str(modules_dir))
    )

    assert result.ok is True
    assert result.resolved_game_root_dir == str(modules_dir.parent)
    assert '--game "K2"' in result.launch_helper_command
    assert "launch_grdev01_smoke_test.py" in result.launch_helper_command
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["launch_handoff"]["game"] == "K2"
    assert proof["launch_handoff"]["expected_executable_path"] == str(modules_dir.parent / "swkotor2.exe")


def test_t2635_install_prep_overwrite_backs_up_existing_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"existing")

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(
            output_dir=str(tmp_path / "out"),
            game_modules_dir=str(modules_dir),
            overwrite=True,
        )
    )

    backup = modules_dir / "grdev01.mod.bak"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert result.backup_module_path == str(backup)
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    assert any("Backed up existing grdev01.mod" in warning for warning in result.warnings)

    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["install"]["backup_module_path"] == str(backup)
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    assert str(backup) in checklist


def test_t2601_install_prep_blocks_stale_currentgame_module_cache(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    cache_dir = game_root / "currentgame"
    modules_dir.mkdir(parents=True)
    cache_dir.mkdir()
    stale_cache = cache_dir / "grdev01.mod"
    stale_cache.write_bytes(b"stale currentgame module cache")

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(output_dir=str(tmp_path / "out"), game_modules_dir=str(modules_dir))
    )

    installed = modules_dir / "grdev01.mod"
    assert result.ok is False
    assert result.code == "install_preflight_failed"
    assert result.installed_module_path == ""
    assert not installed.exists()
    assert any("currentgame cache contains a stale grdev01.mod" in issue for issue in result.blocking_issues)
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is False
    assert any("currentgame cache contains a stale grdev01.mod" in issue for issue in proof["blocking_issues"])


def test_t2601_install_prep_can_auto_detect_modules_dir_from_settings(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleInstallPrepRequest,
        discover_kotor_modules_dir,
        prepare_dev_test_module_install,
    )

    game_root = tmp_path / "Steam" / "swkotor"
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"k1_dir": str(game_root), "k2_dir": ""}), encoding="utf-8")

    assert discover_kotor_modules_dir("K1", settings_path=str(settings_path)) == str(modules_dir)

    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(
            output_dir=str(tmp_path / "out"),
            settings_path=str(settings_path),
            auto_detect_game_modules_dir=True,
        )
    )

    installed = modules_dir / "grdev01.mod"
    assert result.ok is True
    assert result.code == "installed"
    assert result.resolved_modules_dir == str(modules_dir)
    assert result.resolved_game_root_dir == str(game_root)
    assert "launch_grdev01_smoke_test.py" in result.launch_helper_command
    assert Path(result.elevated_launch_script_path).is_file()
    assert Path(result.proof_recording_script_path).is_file()
    assert result.installed_module_path == str(installed)
    assert installed.is_file()
    assert any("Auto-detected KOTOR Modules folder" in warning for warning in result.warnings)


def test_t2615_variant_suite_stages_rectangular_and_floor_plan_packages(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeVariantSuiteRequest, prepare_dev_test_module_variant_suite

    result = prepare_dev_test_module_variant_suite(DevModuleSmokeVariantSuiteRequest(output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "staged_variant_suite"
    assert Path(result.suite_checklist_path).is_file()
    assert Path(result.suite_manifest_path).is_file()
    assert [variant.variant_id for variant in result.variants] == ["rectangular_composition", "floor_plan_opening"]
    for variant in result.variants:
        assert variant.prep_result.ok is True
        assert variant.prep_result.installed_module_path == ""
        assert Path(variant.module_path).is_file()
        assert Path(variant.pack_manifest_path).is_file()
        assert Path(variant.proof_manifest_path).is_file()

    checklist = Path(result.suite_checklist_path).read_text(encoding="utf-8")
    assert "test one variant at a time" in checklist
    assert "Rectangular composition baseline" in checklist
    assert "Floor-plan extrusion with wall opening" in checklist
    assert checklist.count("Run `warp grdev01`") == 2

    manifest = json.loads(Path(result.suite_manifest_path).read_text(encoding="utf-8"))
    assert manifest["task"] == "T2615"
    assert manifest["install_policy"] == "stage_all_copy_one_variant_at_a_time"
    assert [variant["variant_id"] for variant in manifest["variants"]] == ["rectangular_composition", "floor_plan_opening"]
    assert all(variant["ok"] for variant in manifest["variants"])
    rect_manifest = json.loads(Path(result.variants[0].pack_manifest_path).read_text(encoding="utf-8"))
    floor_manifest = json.loads(Path(result.variants[1].pack_manifest_path).read_text(encoding="utf-8"))
    assert rect_manifest["map_studio_smoke_test"]["contains"]["primitive_composition_room"] is True
    assert floor_manifest["map_studio_smoke_test"]["contains"]["floor_plan_room"] is True
    assert floor_manifest["map_studio_smoke_test"]["contains"]["wall_opening"] is True
    assert rect_manifest["map_studio_smoke_test"]["game_tested"] is False
    assert floor_manifest["map_studio_smoke_test"]["game_tested"] is False


def test_t2615_variant_suite_blocks_when_all_variants_disabled(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import DevModuleSmokeVariantSuiteRequest, prepare_dev_test_module_variant_suite

    result = prepare_dev_test_module_variant_suite(
        DevModuleSmokeVariantSuiteRequest(
            output_dir=str(tmp_path),
            include_rectangular_composition=False,
            include_floor_plan_opening=False,
        )
    )

    assert result.ok is False
    assert result.code == "variant_suite_preflight_failed"
    assert result.variants == []
    assert any("at least one enabled variant" in issue for issue in result.blocking_issues)
    assert Path(result.suite_manifest_path).is_file()
