from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.scene import KMaxSceneManager, PivotData, Transform
from src.core.scene.kmax_serializer import KMaxSerializer
from src.core.scene.scene_resource_ref import SceneResourceRef
from src.core.gizmo.transform_gizmo import TransformGizmo


def test_kmax_transform_and_pivot_restore_gizmo_origin(tmp_path: Path) -> None:
    manager = KMaxSceneManager()
    obj = manager.add_model_instance(
        SceneResourceRef(resource_type="model", game="K1", resref="p_test"),
        Transform(position=(100.0, 2.0, 3.0), rotation=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)),
    )
    manager.update_object_pivot(obj.id, position_local=(4.0, 0.0, 0.0), rotation_local=(0.0, 0.0, 0.0))
    path = tmp_path / "gizmo_scene.kmax"
    manager.save_kmax(path)

    loaded = KMaxSerializer.load(path)
    restored = loaded.objects[0]
    assert restored.transform.position == (100.0, 2.0, 3.0)
    assert restored.pivot == PivotData(position_local=(4.0, 0.0, 0.0), rotation_local=(0.0, 0.0, 0.0))

    node = SimpleNamespace(
        position=restored.transform.position,
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_pivot_world=(
            restored.transform.position[0] + restored.pivot.position_local[0],
            restored.transform.position[1] + restored.pivot.position_local[1],
            restored.transform.position[2] + restored.pivot.position_local[2],
        ),
    )
    gizmo = TransformGizmo()
    gizmo.set_selected_object(node)

    assert gizmo.get_gizmo_origin_world() == pytest.approx((104.0, 2.0, 3.0))
