"""Focused controller and window contracts for baked advanced modeling tools."""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
for rel in reversed(
    (
        "native/GhostRigger.Core.Scene/Python/src",
        "native/GhostRigger.Core.Resources/Python/src",
        "native/GhostRigger.Core.Project/Python/src",
        "native/GhostRigger.Core.IO/Python/src",
        "native/GhostRigger.Core.Workflow/Python/src",
        "native/GhostRigger.Core.Math/Python/src",
        "native/GhostRigger.Core.Rendering/Python/src",
        ".",
    )
):
    path = str((ROOT / rel).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)

from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    append_imported_mesh_quad,
)
from core.modules.module_editor_controller import ModuleEditorController  # noqa: E402
from core.modules.map_studio_multi_cut import (  # noqa: E402
    MultiCutSession,
    anchor_from_surface_hit,
)


def _surface(vertices, faces, *, name="surface") -> ImportedMeshSurface:
    return ImportedMeshSurface(
        name=name,
        texture="lda_floor01",
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=tuple(3 for _ in faces),
        uvs=tuple((float(index), 0.0) for index in range(len(vertices))),
        normals=tuple((0.0, 0.0, 1.0) for _ in vertices),
        uvs_lm=tuple((0.0, float(index)) for index in range(len(vertices))),
    )


class _ControllerHarness:
    def __init__(self, primitive: ImportedMeshRoomPrimitive):
        self.primitive = primitive
        self.result = primitive
        self.label = ""
        self.action_key = ""
        self.apply_count = 0

    def _apply_imported_mesh_room_edit(self, *, room_resref, action_key, label, editor):
        assert room_resref == "grmaya"
        assert action_key.startswith("map_studio.imported_mesh.")
        self.apply_count += 1
        self.action_key = action_key
        self.result = editor(self.primitive)
        self.label = label
        return True, label


def _run(primitive: ImportedMeshRoomPrimitive, op: str, **kwargs):
    harness = _ControllerHarness(primitive)
    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        harness,
        room_resref="grmaya",
        op=op,
        mesh_role="render",
        face_index=-1,
        **kwargs,
    )
    assert ok is True
    assert message.startswith("Bake")
    return harness.result


def test_controller_dispatches_mirror_bridge_bend_and_lattice_as_baked_ops() -> None:
    triangle = _surface(
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        ((0, 1, 2),),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(triangle,), game="K2")
    mirrored = _run(
        primitive,
        "mirror_geometry",
        mirror_axis="x",
        mirror_center=0.0,
        mirror_duplicate=False,
    )
    assert mirrored.metadata["last_topology_edit"]["operation"] == "mirror_geometry"

    bridge_surface = _surface(
        (
            (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0),
            (2.0, 1.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0),
        ),
        ((0, 1, 2), (3, 4, 5)),
        name="render",
    )
    bridge_primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(bridge_surface,), game="K2")
    bridged = _run(
        bridge_primitive,
        "bridge_border_edges",
        first_edge_vertices=(0, 1),
        second_edge_vertices=(3, 4),
    )
    assert bridged.metadata["last_topology_edit"]["generated_face_count"] == 2

    plane = _surface(
        ((0.0, -1.0, 0.0), (2.0, -1.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
        name="render",
    )
    plane_primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(plane,), game="K2")
    bent = _run(
        plane_primitive,
        "bend_vertices",
        deform_axis="x",
        curvature_degrees=45.0,
    )
    assert bent.metadata["last_topology_edit"]["operation"] == "bend_vertices"

    lattice = _run(
        plane_primitive,
        "lattice_deform",
        lattice_control_deltas=((0.0, 0.0, 0.0),) * 4 + ((0.0, 0.0, 0.5),) * 4,
    )
    assert lattice.metadata["last_topology_edit"]["interpolation"] == "trilinear_2x2x2"


def test_controller_dispatches_static_shrinkwrap_and_driver_delta_wrap() -> None:
    source = _surface(
        ((0.25, 0.25, 0.0), (1.0, 0.25, 0.0), (0.25, 1.0, 0.0)),
        ((0, 1, 2),),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(source,), game="K2")
    live = _surface(
        ((0.0, 0.0, 2.0), (2.0, 0.0, 2.0), (0.0, 2.0, 2.0)),
        ((0, 1, 2),),
        name="live",
    )
    shrink = _run(
        primitive,
        "shrink_wrap",
        shrink_target_surface=live,
        shrink_projection="nearest_triangle",
        shrink_align_normals=True,
    )
    assert shrink.metadata["last_topology_edit"]["operation"] == "shrink_wrap"

    driver_base = _surface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        ((0, 1, 2),),
        name="driver_base",
    )
    driver_deformed = _surface(
        ((0.0, 0.0, 1.5), (2.0, 0.0, 1.5), (0.0, 2.0, 1.5)),
        ((0, 1, 2),),
        name="driver_deformed",
    )
    wrapped = _run(
        primitive,
        "wrap_deform",
        wrap_driver_base=driver_base,
        wrap_driver_deformed=driver_deformed,
        wrap_nearest_count=3,
    )
    assert wrapped.metadata["last_topology_edit"]["dependency_policy"] == "baked_no_live_driver_graph"


def test_controller_dispatches_maya_make_hole_and_quad_draw_as_single_undoable_edits() -> None:
    make_hole_surface = _surface(
        (
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0),
            (2.0, 2.0, 0.0), (3.0, 2.0, 0.0), (2.0, 3.0, 0.0),
        ),
        ((0, 1, 2), (3, 4, 5)),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(make_hole_surface,), game="K2")
    harness = _ControllerHarness(primitive)
    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        harness,
        room_resref="grmaya",
        op="make_hole",
        mesh_role="render",
        face_index=0,
        cutter_face_index=1,
    )
    assert ok is True
    assert "face 0 using face 1" in message
    assert harness.result.metadata["last_topology_edit"]["cutter_face_removed"] is True

    quad_harness = _ControllerHarness(primitive)
    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        quad_harness,
        room_resref="grmaya",
        op="quad_draw",
        mesh_role="imported_srf_1",
        face_index=-1,
        quad_points=((1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (2.0, 2.0, 1.0), (1.0, 2.0, 1.0)),
        quad_material=9,
        quad_texture="lda_floor01",
        quad_normal_hint=(0.0, 0.0, 1.0),
    )
    assert ok is True
    assert "Quad Draw" in message
    assert len(quad_harness.result.surfaces) == 2
    assert quad_harness.result.surfaces[1].face_mats == (9, 9)
    assert quad_harness.result.metadata["last_topology_edit"]["mesh_role"] == "imported_srf_1"


def test_controller_dispatches_one_provenance_safe_edge_loop_edit() -> None:
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(), game="K2")
    primitive = append_imported_mesh_quad(
        primitive,
        "render",
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        material=9,
    )
    primitive = append_imported_mesh_quad(
        primitive,
        "render",
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
        material=9,
    )
    harness = _ControllerHarness(primitive)

    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        harness,
        room_resref="grmaya",
        op="insert_edge_loop",
        mesh_role="render",
        face_index=0,
        loop_edge_vertices=(3, 0),
        loop_position=0.25,
    )

    assert ok is True
    assert harness.apply_count == 1
    assert harness.action_key == "map_studio.imported_mesh.insert_edge_loop"
    assert "at 0.250" in message
    assert harness.result.metadata["last_topology_edit"]["operation"] == "insert_edge_loop"
    assert harness.result.metadata["last_topology_edit"]["affected_quad_count"] == 2


def test_controller_dispatches_one_thresholded_merge_edit() -> None:
    surface = _surface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.05, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(surface,), game="K2")
    harness = _ControllerHarness(primitive)

    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        harness,
        room_resref="grmaya",
        op="merge_components",
        mesh_role="render",
        face_index=-1,
        merge_vertex_indices=(2, 1),
        merge_threshold=0.1,
    )

    assert ok is True
    assert harness.apply_count == 1
    assert harness.action_key == "map_studio.imported_mesh.merge_components"
    assert message == "Merge 2 selected vertex/vertices in grmaya"
    assert harness.result.metadata["last_topology_edit"]["operation"] == "merge_components"
    assert harness.result.metadata["last_topology_edit"]["threshold"] == 0.1


def test_controller_multi_cut_recomputes_preview_and_records_exactly_one_commit() -> None:
    surface = _surface(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.0, 0.0),
        ),
        ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4)),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(surface,), game="K2")
    first = anchor_from_surface_hit(surface, 1, (0.25, 0.5, 0.0))
    second = anchor_from_surface_hit(surface, 2, (1.75, 0.5, 0.0))
    preview_session = MultiCutSession.begin(primitive, "render").add_anchor(first).add_anchor(second)
    preview = preview_session.preview()
    harness = _ControllerHarness(primitive)

    ok, message = ModuleEditorController.commit_imported_mesh_multi_cut(
        harness,
        room_resref="grmaya",
        mesh_role="render",
        anchors=(first, second),
        expected_source_fingerprint=preview.source_fingerprint,
        expected_result_fingerprint=preview.result_fingerprint,
    )

    assert ok is True
    assert harness.apply_count == 1
    assert harness.action_key == "map_studio.imported_mesh.multi_cut"
    assert "one segment" in message
    assert harness.result.surfaces[0].faces == preview.primitive.surfaces[0].faces
    assert harness.result.metadata["last_topology_edit"]["preview"] is False


def test_controller_multi_cut_rejects_stale_preview_without_returning_changed_geometry() -> None:
    surface = _surface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        name="render",
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmaya", surfaces=(surface,), game="K2")
    first = anchor_from_surface_hit(surface, 0, (0.0, 0.0, 0.0))
    second = anchor_from_surface_hit(surface, 0, (0.5, 0.5, 0.0))
    harness = _ControllerHarness(primitive)

    try:
        ModuleEditorController.commit_imported_mesh_multi_cut(
            harness,
            room_resref="grmaya",
            mesh_role="render",
            anchors=(first, second),
            expected_source_fingerprint="stale-preview",
        )
    except ValueError as exc:
        assert "source changed" in str(exc)
    else:
        raise AssertionError("stale Multi-Cut preview should be rejected")
    assert harness.result is primitive


def _method_source(method_name: str) -> str:
    path = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ModuleEditorWindow")
    method = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    result = ast.get_source_segment(source, method)
    assert result is not None
    return result


def test_window_routes_advanced_shelf_actions_without_claiming_live_history() -> None:
    shelf = _method_source("_apply_map_studio_component_shelf_action")
    options = _method_source("_edit_map_studio_baked_modeling_options")
    make_live = _method_source("_run_map_studio_viewport_modeling_command")

    for operation in (
        "mirror_geometry",
        "bridge_border_edges",
        "bend_vertices",
        "lattice_deform",
        "shrink_wrap",
        "wrap_deform",
    ):
        assert operation in shelf
    assert 'controls["divisions"]' in options
    assert 'controls["taper"]' in options
    assert 'controls["twist_degrees"]' in options
    assert "real intermediate edge rows" in options
    assert "static 2x2x2" in options.lower()
    assert "does not create a persistent maya dependency-graph deformer" in options.lower()
    assert "_capture_map_studio_live_wrap_driver_baseline" in make_live


def test_window_routes_insert_edge_loop_by_raw_edge_with_truthful_persistent_position() -> None:
    shelf = _method_source("_apply_map_studio_component_shelf_action")
    defaults = _method_source("_map_studio_baked_modeling_options")
    options = _method_source("_edit_map_studio_baked_modeling_options")

    assert '"op": "insert_edge_loop"' in shelf
    assert 'edge.get("mesh_edge_indices")' in shelf
    assert 'edge.get("edge_indices")' not in shelf.split('elif key == "insert_edge_loop":', 1)[1].split(
        'elif key == "merge_components":', 1
    )[0]
    assert '"loop_edge_vertices": raw_edge' in shelf
    assert '"loop_position": float(options["position"])' in shelf
    assert '"insert_edge_loop": {"position": 0.5}' in defaults
    assert "connected Quad Draw strip" in options
    assert "Arbitrary stock KOTOR" in options


def test_window_insert_edge_loop_commit_uses_selected_raw_vertex_pair_once() -> None:
    runner = _runtime_method("_apply_map_studio_component_shelf_action")
    calls: list[dict[str, object]] = []

    class Controller:
        @staticmethod
        def apply_imported_mesh_room_component_op(**kwargs):
            calls.append(dict(kwargs))
            return True, "Inserted provenance-safe loop"

    class Viewport:
        @staticmethod
        def map_studio_component_selection():
            return (
                {
                    "component_type": "edge",
                    "room_resref": "grmaya",
                    "mesh_role": "render",
                    "face_index": 0,
                    "edge_indices": (0, 1),
                    "mesh_edge_indices": (3, 0),
                },
            )

        @staticmethod
        def clear_map_studio_component_selection():
            return None

    class Harness:
        _apply_map_studio_component_shelf_action = runner

        def __init__(self):
            self.viewport_panel = Viewport()
            self.controller = Controller()

        @staticmethod
        def _map_studio_baked_modeling_options(_key):
            return {"position": 0.375}

        @staticmethod
        def statusBar():
            return SimpleNamespace(showMessage=lambda *_args: None)

        @staticmethod
        def _log(_message):
            return None

        @staticmethod
        def _refresh_map_studio_imported_mesh_change(_message, _room, _role):
            return None

    assert Harness()._apply_map_studio_component_shelf_action("insert_edge_loop") is True
    assert len(calls) == 1
    assert calls[0]["room_resref"] == "grmaya"
    assert calls[0]["mesh_role"] == "render"
    assert calls[0]["op"] == "insert_edge_loop"
    assert calls[0]["loop_edge_vertices"] == (3, 0)
    assert calls[0]["loop_position"] == 0.375


def test_window_difference_uses_ordered_closed_surface_selection_and_strict_options() -> None:
    runner = _runtime_method("_apply_map_studio_component_shelf_action")
    calls: list[dict[str, object]] = []

    class Controller:
        @staticmethod
        def apply_imported_mesh_room_component_op(**kwargs):
            calls.append(dict(kwargs))
            return True, "Closed solid A-B complete"

    class Viewport:
        @staticmethod
        def map_studio_component_selection():
            return (
                {"component_type": "face", "room_resref": "grmaya", "mesh_role": "render", "face_index": 0},
                {"component_type": "face", "room_resref": "grmaya", "mesh_role": "imported_srf_1", "face_index": 0},
            )

        @staticmethod
        def clear_map_studio_component_selection():
            return None

    class Harness:
        _apply_map_studio_component_shelf_action = runner

        def __init__(self):
            self.viewport_panel = Viewport()
            self.controller = Controller()

        @staticmethod
        def _map_studio_baked_modeling_options(_key):
            return {"weld_tolerance": 2.5e-6}

        @staticmethod
        def statusBar():
            return SimpleNamespace(showMessage=lambda *_args: None)

        @staticmethod
        def _log(_message):
            return None

        @staticmethod
        def _refresh_map_studio_imported_mesh_change(_message, _room, _role):
            return None

    assert Harness()._apply_map_studio_component_shelf_action("boolean_a_minus_b") is True
    assert len(calls) == 1
    assert calls[0]["op"] == "boolean_difference_closed_solids"
    assert calls[0]["mesh_role"] == "render"
    assert calls[0]["boolean_cutter_mesh_role"] == "imported_srf_1"
    assert calls[0]["boolean_weld_tolerance"] == 2.5e-6

    options = _method_source("_edit_map_studio_baked_modeling_options")
    assert "closed, " in options and "consistently wound two-manifolds" in options
    assert "Open KOTOR floors and walls are refused" in options


def test_window_commits_make_hole_and_quad_draw_instead_of_reporting_a_no_op() -> None:
    commit = _method_source("_commit_map_studio_modeling_tool_gesture")

    assert '"op": "make_hole"' in commit
    assert '"cutter_face_index"' in commit
    assert '"op": "quad_draw"' in commit
    assert '"quad_points"' in commit
    assert '"_map_studio_quad_draw_target_state"' in commit
    assert "no geometry was changed" not in commit


def test_window_multi_cut_uses_preview_then_enter_commit_instead_of_per_click_mutation() -> None:
    gesture = _method_source("_commit_map_studio_modeling_tool_gesture")
    evaluator = _method_source("_evaluate_map_studio_multi_cut_preview")
    handler = _method_source("_handle_map_studio_multi_cut_gesture")
    panel_source = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")

    assert "face_split_at_point" not in gesture
    assert "_handle_map_studio_multi_cut_gesture" in gesture
    assert "session.preview()" in evaluator
    assert "_show_live_imported_surface" in evaluator
    assert "commit_imported_mesh_multi_cut" in handler
    assert '"phase": "preview"' in panel_source
    assert '"phase": "commit"' in panel_source
    assert "QtCore.Qt.Key_Backspace" in panel_source
    assert "Multi-Cut line cleared; the tool remains active." in panel_source


def _runtime_method(method_name: str):
    namespace: dict[str, object] = {}
    exec(textwrap.dedent(_method_source(method_name)), namespace)
    return namespace[method_name]


def test_make_live_wrap_baseline_can_be_recaptured_without_shadowing_its_method() -> None:
    capture = _runtime_method("_capture_map_studio_live_wrap_driver_baseline")
    surface = _surface(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), ((0, 1, 2),))

    class Harness:
        _capture_map_studio_live_wrap_driver_baseline = capture

        def __init__(self):
            self.viewport_panel = SimpleNamespace(_map_studio_live_surface=("driver", "render"))

        def _map_studio_imported_surface_in_room_space(self, room, role, destination):
            assert (room, role, destination) == ("driver", "render", "driver")
            return surface

    harness = Harness()
    assert harness._capture_map_studio_live_wrap_driver_baseline() is True
    assert harness._capture_map_studio_live_wrap_driver_baseline() is True
    assert harness._map_studio_live_wrap_driver_state == ("driver", "render", surface)
    assert callable(harness._capture_map_studio_live_wrap_driver_baseline)


def test_failed_persistent_tool_activation_returns_without_recursive_belt_dispatch() -> None:
    runner = _runtime_method("_run_map_studio_viewport_modeling_command")
    messages: list[str] = []

    class Harness:
        _run_map_studio_viewport_modeling_command = runner

        def __init__(self):
            self.viewport_panel = SimpleNamespace(activate_map_studio_modeling_tool=lambda _key: False)

        def statusBar(self):
            return SimpleNamespace(showMessage=lambda message, _duration=0: messages.append(message))

        def _map_studio_tool_action_for_key(self, _key):
            raise AssertionError("failed persistent activation must not fall through")

        def _handle_map_studio_tool_belt_action(self, _action):
            raise AssertionError("failed persistent activation must not recurse through the belt")

    Harness()._run_map_studio_viewport_modeling_command("quad_draw")
    assert messages == ["Quad Draw could not start in the current selection context."]


def test_object_transform_and_history_commands_use_scoped_geometry_refresh() -> None:
    executor = _method_source("_execute_map_studio_tool_belt_command")
    for command in (
        "reset_authored_room_primitive_transform",
        "zero_authored_room_primitive_pivot",
        "delete_authored_room_primitive_history",
    ):
        assert command in executor
