from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageDraw

from src.gui.qt_lib.gizmo.gizmo_mode import GizmoMode, TransformGizmoMode
from src.gui.qt_lib.gizmo.transform_gizmo import TransformGizmo


class DummyCamera:
    fov = 45.0


def _projector(x: float, y: float, z: float, width: int, height: int):
    return (width * 0.5 + x * 10.0, height * 0.5 - y * 10.0, max(1.0, 10.0 - z))


def test_gizmo_mode_cycles_translate_rotate_scale() -> None:
    gizmo = TransformGizmo()

    assert TransformGizmoMode is GizmoMode
    assert gizmo.mode is GizmoMode.TRANSLATE
    assert gizmo.cycle_mode() is GizmoMode.ROTATE
    assert gizmo.cycle_mode() is GizmoMode.SCALE
    assert gizmo.cycle_mode() is GizmoMode.TRANSLATE


def test_set_mode_accepts_enum_and_string_without_clearing_selection() -> None:
    node = SimpleNamespace(position=(1.0, 2.0, 3.0), rotation=(0.0, 0.0, 0.0, 1.0))
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)

    gizmo.set_mode(GizmoMode.ROTATE)
    assert gizmo.mode is GizmoMode.ROTATE
    assert gizmo.selected_object is node

    gizmo.set_mode("scale")
    assert gizmo.mode is GizmoMode.SCALE
    assert gizmo.selected_object is node


def test_rotate_renderer_keeps_x_y_z_ring_handles() -> None:
    node = SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0))
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)
    gizmo.set_mode(GizmoMode.ROTATE)
    image = Image.new("RGBA", (200, 160), (0, 0, 0, 0))

    handles = gizmo.draw(ImageDraw.Draw(image, "RGBA"), DummyCamera(), _projector, 200, 160)

    assert {"ROTATE_X", "ROTATE_Y", "ROTATE_Z"}.issubset({handle["name"] for handle in handles})
