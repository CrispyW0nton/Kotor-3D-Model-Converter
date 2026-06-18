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
    assert payload["rooms"][0]["primitive"]["type"] == "rectangular"
    assert project.placements.entry_point.position == (0.0, -3.0, 0.0)
    assert project.placements.placeables[0].template_resref == "plc_bench"
    assert project.placements.waypoints[0].template_resref == "sw_startloc001"
    assert restored["placements"]["placeables"][0]["tag"] == "grdev01_test_placeable"
    assert restored["placements"]["waypoints"][0]["tag"] == "start"


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
