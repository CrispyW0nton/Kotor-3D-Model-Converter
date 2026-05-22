from __future__ import annotations

from src.core.scene.axis_mode import AxisMode, IDENTITY_BASIS, TransformReferenceController


class DummyObject:
    def __init__(self, object_id: str = "obj-1", rotation=(0.0, 0.0, 0.0, 1.0), parent=None) -> None:
        self._gr_scene_object_id = object_id
        self.rotation = rotation
        self.parent = parent


class DummyScene:
    def __init__(self, ids: set[str]) -> None:
        self.objects = [type("SceneObj", (), {"id": object_id})() for object_id in ids]


def test_world_and_local_axis_modes() -> None:
    controller = TransformReferenceController()
    selected = DummyObject(rotation=(0.0, 0.0, 0.70710678, 0.70710678))

    controller.set_axis_mode(AxisMode.WORLD)
    assert controller.get_transform_basis(selected) == IDENTITY_BASIS

    controller.set_axis_mode(AxisMode.LOCAL)
    basis = controller.get_transform_basis(selected)
    assert round(basis[0][1], 6) == 1.0
    assert round(basis[1][0], 6) == -1.0


def test_parent_without_parent_falls_back_to_world() -> None:
    controller = TransformReferenceController(AxisMode.PARENT)

    assert controller.get_transform_basis(DummyObject(parent=None)) == IDENTITY_BASIS


def test_pick_reference_and_deleted_reference_fallback() -> None:
    controller = TransformReferenceController()
    target = DummyObject("target", rotation=(0.0, 0.70710678, 0.0, 0.70710678))

    controller.resolve_pick_reference(target)
    assert controller.get_axis_mode() is AxisMode.PICK
    picked_basis = controller.get_transform_basis(DummyObject("selected"), scene=DummyScene({"target"}))
    assert round(picked_basis[0][2], 6) == -1.0

    assert controller.get_transform_basis(DummyObject("selected"), scene=DummyScene(set())) == IDENTITY_BASIS
    assert controller.picked_reference() is None

