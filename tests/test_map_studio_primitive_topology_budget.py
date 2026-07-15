from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _controller_with_cube():
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="elevation_test_room",
        module_root="grbudget",
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        primitive_name="polyCube1",
    )
    return controller


def _cube_payload(controller) -> dict:
    payload = controller.project.extra_sections["authored_module"]
    return next(row for row in payload["rooms"][0]["primitive"]["primitives"] if row["name"] == "polyCube1")


def test_moderate_preview_builds_but_over_budget_preview_allocates_no_mesh(monkeypatch) -> None:
    _install_native_payload_paths()
    from src.core.modules import module_editor_controller as controller_module
    from src.core.modules.authored_primitive_topology_policy import PrimitivePreviewDeferred

    controller = _controller_with_cube()
    moderate = controller.preview_authored_room_primitive_dimensions(
        room_resref="grbudget_room01",
        primitive_name="polyCube1",
        dimensions={"subdivisions_x": 10, "subdivisions_y": 10, "subdivisions_z": 10},
    )
    assert len(moderate[0]["faces"]) == 1200

    payload = controller.project.extra_sections["authored_module"]
    before = deepcopy(payload)
    identity = id(payload)
    undo_count = len(controller.command_history.undo_stack)
    calls = 0

    def forbidden_mesh(_primitive):
        nonlocal calls
        calls += 1
        raise AssertionError("preview budget must run before primitive_to_mesh")

    monkeypatch.setattr(controller_module, "primitive_to_mesh", forbidden_mesh)
    with pytest.raises(PrimitivePreviewDeferred, match="Preview deferred; Apply to build once"):
        controller.preview_authored_room_primitive_dimensions(
            room_resref="grbudget_room01",
            primitive_name="polyCube1",
            dimensions={"subdivisions_x": 60, "subdivisions_y": 60, "subdivisions_z": 60},
        )
    assert calls == 0
    assert id(controller.project.extra_sections["authored_module"]) == identity
    assert controller.project.extra_sections["authored_module"] == before
    assert len(controller.command_history.undo_stack) == undo_count


def test_absolute_budget_rejects_preview_and_commit_before_allocation_or_serialization(monkeypatch) -> None:
    _install_native_payload_paths()
    from src.core.modules import module_editor_controller as controller_module
    from src.core.modules.authored_primitive_topology_policy import PrimitiveTopologySafetyError

    controller = _controller_with_cube()
    payload = controller.project.extra_sections["authored_module"]
    before = deepcopy(payload)
    identity = id(payload)
    undo_count = len(controller.command_history.undo_stack)
    calls = {"mesh": 0, "serialize": 0}

    def forbidden_mesh(_primitive):
        calls["mesh"] += 1
        raise AssertionError("hard budget must run before primitive_to_mesh")

    def forbidden_serialize(_project):
        calls["serialize"] += 1
        raise AssertionError("hard budget must run before KMAP serialization")

    monkeypatch.setattr(controller_module, "primitive_to_mesh", forbidden_mesh)
    monkeypatch.setattr(controller_module, "authored_project_to_kmap_payload", forbidden_serialize)
    dimensions = {"subdivisions_x": 200, "subdivisions_y": 200, "subdivisions_z": 200}
    with pytest.raises(PrimitiveTopologySafetyError, match="blocked before mesh allocation"):
        controller.preview_authored_room_primitive_dimensions(
            room_resref="grbudget_room01", primitive_name="polyCube1", dimensions=dimensions
        )
    with pytest.raises(PrimitiveTopologySafetyError, match="blocked before mesh allocation"):
        controller.set_authored_room_primitive_dimensions(
            room_resref="grbudget_room01", primitive_name="polyCube1", dimensions=dimensions
        )
    assert calls == {"mesh": 0, "serialize": 0}
    assert id(controller.project.extra_sections["authored_module"]) == identity
    assert controller.project.extra_sections["authored_module"] == before
    assert len(controller.command_history.undo_stack) == undo_count


def test_typed_subdivisions_above_maya_soft_50_commit_without_clamping() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_primitive_topology_policy import MAYA_SUBDIVISION_SOFT_MAXIMUM

    controller = _controller_with_cube()
    undo_count = len(controller.command_history.undo_stack)
    typed = MAYA_SUBDIVISION_SOFT_MAXIMUM + 10
    controller.set_authored_room_primitive_dimensions(
        room_resref="grbudget_room01",
        primitive_name="polyCube1",
        dimensions={"subdivisions_x": typed, "subdivisions_y": typed, "subdivisions_z": typed},
    )
    committed = _cube_payload(controller)
    assert (committed["subdivisions_x"], committed["subdivisions_y"], committed["subdivisions_z"]) == (typed, typed, typed)
    assert len(controller.command_history.undo_stack) == undo_count + 1
