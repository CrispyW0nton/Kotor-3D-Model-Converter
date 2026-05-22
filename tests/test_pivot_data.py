from __future__ import annotations

from src.core.scene import KMaxScene, KMaxSerializer, PivotData, SceneObjectInstance, Transform


def test_scene_object_default_pivot_is_origin() -> None:
    obj = SceneObjectInstance(id="obj-1", name="Test")

    assert obj.pivot.position_local == (0.0, 0.0, 0.0)
    assert obj.pivot.rotation_local == (0.0, 0.0, 0.0)
    assert obj.pivot.enabled is True


def test_kmax_pivot_round_trip() -> None:
    scene = KMaxScene.new(name="Pivot Test")
    scene.objects.append(
        SceneObjectInstance(
            id="obj-1",
            name="Test",
            transform=Transform(position=(1.0, 2.0, 3.0)),
            pivot=PivotData(position_local=(4.0, 5.0, 6.0), rotation_local=(10.0, 20.0, 30.0)),
        )
    )

    payload = KMaxSerializer.to_dict(scene)
    restored = KMaxSerializer.from_dict(payload)

    assert restored.objects[0].pivot.position_local == (4.0, 5.0, 6.0)
    assert restored.objects[0].pivot.rotation_local == (10.0, 20.0, 30.0)


def test_legacy_kmax_without_pivot_loads_with_default_pivot() -> None:
    payload = {
        "file_type": "GhostRiggerKMax",
        "file_version": 1,
        "scene": {"id": "scene-1", "name": "Legacy"},
        "objects": [
            {
                "id": "obj-1",
                "name": "Legacy Object",
                "object_type": "model",
                "source_ref": {"resref": "p_test", "game": "K1"},
                "transform": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
            }
        ],
    }

    restored = KMaxSerializer.from_dict(payload)

    assert restored.objects[0].pivot.position_local == (0.0, 0.0, 0.0)
    assert restored.objects[0].pivot.rotation_local == (0.0, 0.0, 0.0)

