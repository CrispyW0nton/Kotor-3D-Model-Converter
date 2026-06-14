from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.gizmo.gizmo_mode import GizmoMode
from src.core.gizmo.transform_controller import TransformController
from src.core.gizmo.transform_gizmo import TransformGizmo


class DummyCamera:
    fov = 45.0

    def _view_matrix(self):
        return (
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, -1.0, 0.0),
            (0.0, 10.0, 0.0),
        )


def test_gizmo_origin_tracks_object_position_updates() -> None:
    node = SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0))
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)

    assert gizmo.get_gizmo_origin_world() == pytest.approx((0.0, 0.0, 0.0))

    node.position = (100.0, 0.0, 0.0)
    gizmo.update_from_object_transform()
    assert gizmo.get_gizmo_origin_world() == pytest.approx((100.0, 0.0, 0.0))

    node.position = (100.0, 25.0, -10.0)
    gizmo.update_from_selection()
    assert gizmo.get_gizmo_origin_world() == pytest.approx((100.0, 25.0, -10.0))


def test_gizmo_origin_prefers_active_pivot_world() -> None:
    node = SimpleNamespace(
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_pivot_world=(12.0, 3.0, 0.0),
    )
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)

    assert gizmo.get_gizmo_origin_world() == pytest.approx((12.0, 3.0, 0.0))


def test_helper_gizmo_origin_prefers_helper_center_unless_pivot_editing() -> None:
    light = SimpleNamespace(
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        is_light=True,
        _gr_pivot_world=(12.0, 3.0, 0.0),
        _gr_gizmo_world_position=(14.0, 5.0, 1.0),
    )
    gizmo = TransformGizmo()
    gizmo.set_selected_object(light)

    assert gizmo.get_gizmo_origin_world() == pytest.approx((14.0, 5.0, 1.0))

    light._gr_pivot_edit_mode = "affect_pivot_only"
    gizmo.update_from_object_transform()
    assert gizmo.get_gizmo_origin_world() == pytest.approx((12.0, 3.0, 0.0))


def test_translate_drag_moves_object_and_gizmo_pivot_together() -> None:
    node = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_pivot_world=(0.0, 0.0, 0.0),
    )
    gizmo = TransformGizmo(TransformController())
    gizmo.set_selected_object(node)
    gizmo.set_mode(GizmoMode.TRANSLATE)

    gizmo.begin_drag("TRANSLATE_X", (100, 100), DummyCamera())
    gizmo.drag((130, 100), DummyCamera(), 500)

    assert node.position[0] > 0.0
    assert gizmo.get_gizmo_origin_world()[0] == pytest.approx(node.position[0])


def test_translate_center_handle_moves_object_in_view_plane() -> None:
    node = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_pivot_world=(0.0, 0.0, 0.0),
    )
    gizmo = TransformGizmo(TransformController())
    gizmo.set_selected_object(node)
    gizmo.set_mode(GizmoMode.TRANSLATE)

    gizmo.begin_drag("TRANSLATE_VIEW", (100, 100), DummyCamera())
    gizmo.drag((130, 80), DummyCamera(), 500)

    assert node.position[0] > 0.0
    assert node.position[2] > 0.0
    assert gizmo.get_gizmo_origin_world() == pytest.approx(node.position)


def test_translate_center_handle_is_pickable() -> None:
    class _Draw:
        def line(self, *args, **kwargs):
            pass

        def polygon(self, *args, **kwargs):
            pass

        def ellipse(self, *args, **kwargs):
            pass

    def projector(x, y, z, _width, _height):
        return (100.0 + float(x), 100.0 - float(z), 5.0)

    node = SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0))
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)
    gizmo.draw(_Draw(), DummyCamera(), projector, 400, 300)

    assert gizmo.hit_test((100, 100), DummyCamera()) == "TRANSLATE_VIEW"


def test_snapped_translate_moves_gizmo_to_actual_object_position() -> None:
    node = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_pivot_world=(0.0, 0.0, 0.0),
    )
    controller = TransformController()
    controller.set_position_snap(True, 1.0)
    gizmo = TransformGizmo(controller)
    gizmo.set_selected_object(node)
    gizmo.set_mode(GizmoMode.TRANSLATE)

    gizmo.begin_drag("TRANSLATE_X", (100, 100), DummyCamera())
    gizmo.drag((112, 100), DummyCamera(), 500)

    assert gizmo.get_gizmo_origin_world()[0] == pytest.approx(node.position[0])


def test_scene_root_scale_updates_metadata_without_mutating_vertices() -> None:
    child = SimpleNamespace(vertices=[(1.0, 2.0, 3.0)])
    root = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(4.0, 5.0, 6.0)],
        children=[child],
        _gr_scene_object_root=True,
        _gr_scale=(1.0, 1.0, 1.0),
    )
    gizmo = TransformGizmo(TransformController())
    gizmo.set_selected_object(root)
    gizmo.set_mode(GizmoMode.SCALE)

    gizmo.begin_drag("SCALE_UNIFORM", (100, 100), DummyCamera())
    gizmo.drag((130, 90), DummyCamera(), 500)

    assert root._gr_scale[0] > 1.0
    assert root.vertices == [(4.0, 5.0, 6.0)]
    assert child.vertices == [(1.0, 2.0, 3.0)]
