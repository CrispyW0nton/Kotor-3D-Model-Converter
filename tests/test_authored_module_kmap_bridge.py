from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
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
    assert restored["placements"]["metadata"]["light_count"] == 1


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
