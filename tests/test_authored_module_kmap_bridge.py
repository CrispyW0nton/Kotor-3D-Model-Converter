from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _authored_payload(runtime_resources=()):
    return {
        "module_root": "grdev01",
        "game": "K1",
        "display_name": "GhostRigger Dev Test",
        "rooms": [
            {
                "room_resref": "grdev01_room01",
                "primitive": {
                    "type": "floor_plan",
                    "points": [[-3.0, -2.0], [3.0, -2.0], [3.0, 2.0], [-3.0, 2.0]],
                    "wall_height": 3.0,
                    "floor_surface_id": "metal",
                    "material": {"texture": "CM_Baremetal"},
                },
                "visible_rooms": ["grdev01_room01"],
            }
        ],
        "placements": {"entry_point": {"area_resref": "grdev01", "position": [0.0, 0.0, 0.0], "facing": 0.0}},
        "runtime_resources": list(runtime_resources),
    }


def _runtime_resources():
    return [
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    ]


def test_t2640_kmap_bridge_reports_missing_authored_section() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness

    result = build_kmap_authored_module_readiness(new_kmap_project())

    assert result.project is None
    assert result.readiness is None
    assert result.warnings == ("No authored Map Studio module section is stored in this KMAP yet.",)


def test_t2640_kmap_bridge_builds_previewable_readiness_from_extra_section() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness

    project = new_kmap_project(name="grdev01", game="K1")
    project.extra_sections["authored_module"] = _authored_payload()

    result = build_kmap_authored_module_readiness(project)

    assert result.project is not None
    assert result.readiness is not None
    assert result.readiness.capability_stage == "previewable"
    assert result.readiness.can_preview is True
    assert result.readiness.can_export_candidate is False
    assert result.readiness.rooms[0].room_resref == "grdev01_room01"
    assert ("grdev01_room01", "mdl") in result.readiness.missing_runtime_resources


def test_t2909_kmap_bridge_migrates_legacy_room_entry_to_module_area() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload

    payload = _authored_payload()
    payload["placements"]["entry_point"]["area_resref"] = "grdev01_room01"

    project = authored_project_from_kmap_payload(payload)

    assert project.placements.entry_point.area_resref == "grdev01"
    assert project.placements.metadata["entry_room_resref"] == "grdev01_room01"
    assert project.extra["entry_room_resref"] == "grdev01_room01"
    assert project.extra["entry_area_migration"] == {
        "source_area_resref": "grdev01_room01",
        "runtime_area_resref": "grdev01",
        "reason": "legacy_room_resref_in_module_entry_area",
    }


def test_t2640_kmap_bridge_promotes_complete_runtime_resources_to_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness

    project = new_kmap_project(name="grdev01", game="K1")
    project.extra_sections["authored_module"] = _authored_payload(_runtime_resources())

    readiness = build_kmap_authored_module_readiness(project).readiness

    assert readiness is not None
    assert readiness.capability_stage == "export_candidate"
    assert readiness.can_export_candidate is True
    assert readiness.missing_runtime_resources == ()
    assert "warp grdev01" in readiness.next_action


def test_t2684_kmap_bridge_reports_installed_authored_module_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness

    project = new_kmap_project(name="grdev01", game="K1")
    payload = _authored_payload(_runtime_resources())
    payload["proof_manifest_path"] = "C:/tmp/grdev01_authored_module_game_manifest.json"
    payload["installed_module_path"] = "C:/Games/KOTOR/Modules/grdev01.mod"
    payload["resolved_modules_dir"] = "C:/Games/KOTOR/Modules"
    payload["elevated_launch_script_path"] = "C:/tmp/grdev01_launch_kotor_as_admin.cmd"
    payload["proof_recording_script_path"] = "C:/tmp/grdev01_record_game_proof.cmd"
    project.extra_sections["authored_module"] = payload

    readiness = build_kmap_authored_module_readiness(project).readiness

    assert readiness is not None
    assert readiness.metadata["proof_status"] == "installed_for_game_test"
    assert readiness.metadata["installed_module_path"].endswith("grdev01.mod")
    assert readiness.metadata["resolved_modules_dir"].endswith("Modules")
    assert readiness.metadata["resolved_game_root_dir"].endswith("KOTOR")
    assert "launch_grdev01_smoke_test.py" in readiness.metadata["launch_helper_command"]
    assert readiness.metadata["elevated_launch_script_path"].endswith("grdev01_launch_kotor_as_admin.cmd")
    assert readiness.metadata["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")
    assert "Run the launch helper dry-run" in readiness.next_action


def test_t3104_kmap_bridge_passes_package_inventory_to_readiness() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness

    project = new_kmap_project(name="grdev01", game="K1")
    payload = _authored_payload(_runtime_resources())
    payload["proof_manifest_path"] = "C:/tmp/grdev01_authored_module_game_manifest.json"
    payload["package_resource_inventory"] = {
        "schema": "ghostrigger.map_studio.package_resource_inventory.v1",
        "module_root": "grdev01",
        "readback_ok": True,
        "required_runtime_resources": [{"resref": "grdev01", "restype": "are"}],
        "missing_required_runtime_resources": [],
        "resource_groups": {"verified_archive_resource_count": 9, "loose_staged_resource_count": 9},
        "install": {"installed": False, "dry_run": False},
    }
    project.extra_sections["authored_module"] = payload

    readiness = build_kmap_authored_module_readiness(project).readiness

    assert readiness is not None
    assert readiness.metadata["package_resource_inventory"]["module_root"] == "grdev01"
    assert readiness.metadata["package_resource_inventory"]["readback_ok"] is True


def test_t2642_dev_test_payload_roundtrips_placeable_and_waypoint() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    payload = create_dev_test_authored_module_payload()
    project = authored_project_from_kmap_payload(payload)
    restored = authored_project_to_kmap_payload(project)

    assert payload["module_root"] == "grdev01"
    assert payload["metadata"]["content_origin"] == "map_studio_original"
    assert payload["metadata"]["authored_from_scratch"] is True
    assert payload["metadata"]["copied_from_base_game_module"] is False
    assert payload["metadata"]["include_basic_light"] is True
    assert payload["metadata"]["lighting"]["profile"] == "fullbright"
    assert payload["metadata"]["lighting"]["purpose"] == "canonical_graybox_visibility"
    assert payload["rooms"][0]["primitive"]["type"] == "rectangular"
    assert payload["lights"][0]["name"] == "grdev01_key_light"
    assert payload["lights"][0]["room_resref"] == "grdev01_room01"
    assert payload["lights"][0]["metadata"]["purpose"] == "canonical_smoke_visibility"
    assert project.placements.entry_point.position == (0.0, -3.0, 0.0)
    assert project.placements.placeables[0].template_resref == "plc_bench"
    assert project.placements.waypoints[0].template_resref == "sw_startloc001"
    assert project.lights[0].name == "grdev01_key_light"
    assert restored["placements"]["placeables"][0]["tag"] == "grdev01_test_placeable"
    assert restored["placements"]["waypoints"][0]["tag"] == "start"
    assert restored["lights"][0]["name"] == "grdev01_key_light"
    assert restored["metadata"]["lighting"]["profile"] == "fullbright"
    assert restored["placements"]["metadata"]["light_count"] == 1


def test_k2_transition_runtime_fields_and_radian_bearings_survive_kmap_roundtrip() -> None:
    _install_native_payload_paths()

    import math
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import (
        AuthoredDoorInstance,
        AuthoredGameplayPlacement,
        AuthoredTriggerInstance,
        ModuleEntryPoint,
    )
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdoor", game="K2"),
        rooms=(),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdoor"),
            doors=(
                AuthoredDoorInstance(
                    template_resref="door_airlock",
                    tag="airlock",
                    position=(1.0, 2.0, 3.0),
                    bearing=math.pi / 2.0,
                    linked_to="destination",
                    linked_to_module="next_area",
                    linked_to_flags=2,
                    transition_destination=42,
                    use_tweak_color=True,
                    tweak_color=0x746B82,
                    instance_id="door-stable-id",
                ),
            ),
            triggers=(
                AuthoredTriggerInstance(
                    template_resref="newtransition",
                    tag="exit_trigger",
                    geometry=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                    linked_to="destination_door",
                    linked_to_module="next_area",
                    linked_to_flags=1,
                    transition_destination=123845,
                    instance_id="trigger-stable-id",
                ),
            ),
        ),
    )

    payload = authored_project_to_kmap_payload(project)
    restored = authored_project_from_kmap_payload(payload)
    row = restored.placements.doors[0]
    assert payload["placements"]["metadata"]["bearing_unit"] == "radians"
    assert row.bearing == math.pi / 2.0
    assert row.linked_to_flags == 2
    assert row.use_tweak_color is True
    assert row.tweak_color == 0x746B82
    assert row.instance_id == "door-stable-id"
    trigger = restored.placements.triggers[0]
    assert payload["placements"]["triggers"][0]["linked_to_flags"] == 1
    assert trigger.linked_to_module == "next_area"
    assert trigger.linked_to_flags == 1
    assert trigger.transition_destination == 123845
    assert trigger.instance_id == "trigger-stable-id"


def test_t2642_controller_creates_authored_dev_room_in_kmap() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")

    result = controller.create_dev_test_authored_module()

    assert controller.project.name == "grdev01"
    assert "authored_module" in controller.project.extra_sections
    assert controller.project.dirty is True
    assert result.readiness is not None
    assert result.readiness.capability_stage == "previewable"
    assert result.readiness.can_preview is True
    assert result.readiness.metadata["source_identity"]["content_origin"] == "map_studio_original"
    assert result.readiness.metadata["source_identity"]["authored_from_scratch"] is True
    assert result.readiness.metadata["lighting_count"] == 1


def test_t2667_kmap_round_trips_composition_room_primitives() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import compile_authored_room_spec, create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
    from src.core.modules.authored_room_primitives import ArchPrimitive, FloorPrimitive, RampPrimitive, StairsPrimitive

    project = create_composition_room_project(
        module_root="grdev01",
        game="K1",
        display_name="GhostRigger Primitive Composition",
        composition=AuthoredRoomComposition(
            room_resref="grdev01_room01",
            floor=FloorPrimitive(name="grdev01_floor", width=12.0, depth=8.0, surface_id="stone"),
            primitives=(
                PlacedRoomPrimitive(
                    primitive=RampPrimitive(name="grdev01_ramp", width=2.0, length=4.0, height=1.25, surface_id="metal"),
                    transform=PrimitiveTransform(translation=(2.0, 0.5, 0.0), rotation_degrees_z=90.0),
                    name="grdev01_ramp_a",
                ),
                StairsPrimitive(name="grdev01_steps", width=2.0, depth=3.0, height=1.0, steps=4, surface_id="stone"),
                ArchPrimitive(name="grdev01_arch", width=2.5, height=3.0, frame_thickness=0.3),
            ),
            metadata={"author_note": "composition round trip"},
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grdev01")),
    )

    payload = authored_project_to_kmap_payload(project)
    restored = authored_project_from_kmap_payload(payload)
    geometry = compile_authored_room_spec(restored.rooms[0])

    primitive_payload = payload["rooms"][0]["primitive"]
    assert primitive_payload["type"] == "composition"
    assert primitive_payload["floor"]["surface_id"] == "stone"
    assert primitive_payload["primitives"][0]["type"] == "ramp"
    assert primitive_payload["primitives"][0]["instance_name"] == "grdev01_ramp_a"
    assert primitive_payload["primitives"][0]["transform"]["rotation_degrees_z"] == 90.0
    assert restored.module_root == "grdev01"
    assert restored.rooms[0].metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive_count"] == 3
    assert geometry.metadata["walkmesh_primitive_count"] == 2
    assert geometry.metadata["transformed_primitive_count"] == 1
    assert geometry.wok.walkable_face_count() == 6
    assert {mesh.name for mesh in geometry.helper_meshes} == {"grdev01_ramp_a", "grdev01_steps", "grdev01_arch"}


def _ported_imported_mesh_kmap(game: str):
    _install_native_payload_paths()

    from src.core.level import MaterialReference, ModuleInstance, TextureReference, new_kmap_project
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        ModuleEntryPoint,
    )
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_format import WOKData, WOKFace

    module_root = "grport01"
    room_resref = "grport01r"
    surface = ImportedMeshSurface(
        name="painted_floor",
        texture="gr_floor",
        vertices=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0)),
        faces=((0, 1, 2),),
        uvs=((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
        lightmap="gr_floorlm",
        texture_names=("gr_floor", "gr_floorlm"),
        tex_count=2,
        uvs_lm=((0.1, 0.1), (0.9, 0.1), (0.1, 0.9)),
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref=room_resref,
        surfaces=(surface,),
        source_model="001ebo1",
        game=game,
        wok=WOKData(
            name=room_resref,
            verts=list(surface.vertices),
            faces=[WOKFace(0, 1, 2, surface=4)],
        ),
        metadata={"stock_source_game": game, "unknown_preserved": {"key": 7}},
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root=module_root,
            game=game,
            display_name="Port Fixture",
            tag=module_root,
            metadata={"lighting": {"profile": "fullbright"}},
        ),
        rooms=(AuthoredRoomSpec(room_resref=room_resref, primitive=primitive),),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref=module_root, position=(0.5, 0.5, 0.0)),
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="plc_bench",
                    tag="port_bench",
                    position=(1.0, 1.0, 0.0),
                    bearing=90.0,
                ),
            ),
        ),
        extra={"unknown_authored_data": {"preserve": True}},
    )
    project = new_kmap_project(module_root, game)
    project.modules.append(
        ModuleInstance(
            module_name=module_root,
            game=game,
            source_path=f"{game.lower()}_source.mod",
            metadata={"unknown_module_data": 11},
        )
    )
    project.textures.append(
        TextureReference(resref="gr_floor", path="Textures/gr_floor.tga", metadata={"painted": True})
    )
    project.materials.append(MaterialReference(name="Floor", texture_id=project.textures[0].texture_id))
    payload = authored_project_to_kmap_payload(authored)
    payload.update(
        {
            "runtime_resources": [f"{module_root}.are", f"{room_resref}.mdl"],
            "game_tested": True,
            "manual_proof_required": False,
            "pack_manifest_path": "stale/pack.json",
            "proof_manifest_path": "stale/proof.json",
            "installed_module_path": "stale/game/Modules/grport01.mod",
            "in_game_proof_evidence_path": "stale/proof.png",
            "package_resource_inventory": {"readback_ok": True},
            "export_job": {"status": "success"},
            "unknown_top_level": {"preserve": "yes"},
        }
    )
    project.extra_sections["authored_module"] = payload
    project.exports = {"module_path": "stale/grport01.mod", "proof_manifest_path": "stale/proof.json"}
    project.metadata["proof_manifest_path"] = "stale/project-proof.json"
    return project


def test_module_porter_retargets_imported_mesh_without_losing_authored_data(tmp_path: Path) -> None:
    from copy import deepcopy

    from src.core.level import KMapSerializer
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_porter_service import ModulePorterService

    project = _ported_imported_mesh_kmap("K1")
    before_payload = deepcopy(project.extra_sections["authored_module"])
    before_primitive = deepcopy(before_payload["rooms"][0]["primitive"])
    before_primitive.pop("game")
    before_placements = deepcopy(before_payload["placements"])
    before_texture = project.textures[0].to_dict()
    before_material = project.materials[0].to_dict()

    report = ModulePorterService().record_port_decision(project, "K1", "K2")

    assert report.ok is True
    assert report.code == "authored_project_retargeted"
    assert report.unsupported
    assert project.game == "K2"
    assert project.source_game == "K1"
    assert project.target_game == "K2"
    assert project.modules[0].game == "K2"
    assert project.modules[0].metadata["source_game"] == "K1"
    assert project.modules[0].metadata["unknown_module_data"] == 11
    payload = project.extra_sections["authored_module"]
    assert payload["game"] == "K2"
    assert payload["rooms"][0]["primitive"]["game"] == "K2"
    after_primitive = deepcopy(payload["rooms"][0]["primitive"])
    after_primitive.pop("game")
    assert after_primitive == before_primitive
    assert payload["placements"] == before_placements
    assert project.textures[0].to_dict() == before_texture
    assert project.materials[0].to_dict() == before_material
    assert payload["unknown_top_level"] == {"preserve": "yes"}
    assert payload["extra"]["unknown_authored_data"] == {"preserve": True}
    assert payload["rooms"][0]["primitive"]["metadata"]["stock_source_game"] == "K1"
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert payload["manual_proof_required"] is True
    assert payload["export_proof_invalidation"]["invalidates_previous_export"] is True
    assert payload["export_proof_invalidation"]["invalidates_game_proof"] is True
    for stale_key in (
        "pack_manifest_path",
        "proof_manifest_path",
        "installed_module_path",
        "in_game_proof_evidence_path",
        "package_resource_inventory",
        "export_job",
    ):
        assert stale_key not in payload
    assert project.exports == {}
    assert "proof_manifest_path" not in project.metadata

    decoded = authored_project_from_kmap_payload(payload)
    assert decoded.game == "K2"
    assert isinstance(decoded.rooms[0].primitive, ImportedMeshRoomPrimitive)
    assert decoded.rooms[0].primitive.game == "K2"
    assert decoded.rooms[0].primitive.surfaces[0].uvs_lm == (
        (0.10000000149011612, 0.10000000149011612),
        (0.8999999761581421, 0.10000000149011612),
        (0.10000000149011612, 0.8999999761581421),
    )
    assert decoded.rooms[0].primitive.wok is not None
    assert decoded.rooms[0].primitive.wok.faces[0].surface == 4

    kmap_path = tmp_path / "grport01.kmap"
    KMapSerializer.save(project, kmap_path)
    reopened = KMapSerializer.load(kmap_path)
    reopened_authored = authored_project_from_kmap_payload(reopened.extra_sections["authored_module"])
    assert reopened.game == "K2"
    assert reopened.source_game == "K1"
    assert reopened.target_game == "K2"
    assert reopened.modules[0].game == "K2"
    assert reopened_authored.game == "K2"
    assert reopened_authored.rooms[0].primitive.game == "K2"
    assert reopened_authored.placements.placeables[0].position == (1.0, 1.0, 0.0)


def test_module_porter_rejects_invalid_or_inconsistent_requests_without_mutation() -> None:
    from src.core.level import KMapSerializer
    from src.core.modules.module_porter_service import ModulePorterService

    service = ModulePorterService()
    for source, target, expected_code in (
        ("K1", "K3", "invalid_target_game"),
        ("K2", "K1", "source_game_mismatch"),
        ("K1", "K1", "same_game"),
    ):
        project = _ported_imported_mesh_kmap("K1")
        before = KMapSerializer.to_dict(project)
        report = service.record_port_decision(project, source, target)
        assert report.ok is False
        assert report.code == expected_code
        assert KMapSerializer.to_dict(project) == before


def test_module_porter_k1_k2_roundtrip_reopens_and_builds_target_raw_contract(tmp_path: Path) -> None:
    import struct

    from src.core.level import KMapSerializer, new_kmap_project
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.module_porter_service import ModulePorterService

    expected_function_pointers = {
        "K1": (4_273_776, 4_216_096),
        "K2": (4_285_200, 4_216_320),
    }
    for source, target in (("K1", "K2"), ("K2", "K1")):
        project = new_kmap_project("grportfp", source)
        project.extra_sections["authored_module"] = create_dev_test_authored_module_payload(
            module_root="grportfp",
            game=source,
            include_test_placeable=False,
            include_start_waypoint=False,
        )
        report = ModulePorterService().record_port_decision(project, source, target)
        assert report.ok is True

        path = tmp_path / f"{source.lower()}_to_{target.lower()}.kmap"
        KMapSerializer.save(project, path)
        reopened = KMapSerializer.load(path)
        authored = authored_project_from_kmap_payload(
            reopened.extra_sections["authored_module"],
            fallback_name=reopened.name,
            fallback_game=reopened.game,
        )
        build = build_authored_module(authored)
        room_resref = authored.rooms[0].normalised_resref()
        mdl = build.resources[(room_resref, "mdl")].data

        assert authored.game == target
        assert build.game == target
        assert struct.unpack_from("<II", mdl, 12) == expected_function_pointers[target]
        contract = build.metadata["engine_contract"]
        assert contract["export_ready"] is True
        assert contract["blocking_issues"] == []
        assert contract["rooms"][0]["mdl"]["nonzero_node_plus_8"] == 0
        assert contract["rooms"][0]["mdl"]["aabb_node_count"] >= 1
        assert contract["rooms"][0]["wok"]["closed_perimeter_count"] >= 1
