"""Regression tests for Retarget Workbench external-file import routing."""

from __future__ import annotations

import inspect
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _sample_clip():
    from src.core.retargeting.source_animation import (
        SourcePose,
        SourceSkeletonClip,
        SourceSkeletonNode,
        Transform,
    )

    root_local = Transform()
    child_local = Transform(position=(1.0, 0.0, 0.0))
    root_global = Transform()
    child_global = Transform(position=(1.0, 0.0, 0.0))
    nodes = [
        SourceSkeletonNode("Root", None, 0, root_local, root_global),
        SourceSkeletonNode("RHand", "Root", 1, child_local, child_global),
    ]
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="demo.fbx",
        clip_name="root|Unreal Take|Base Layer",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
        axis_system="blender_fbx_import_z_up",
        available_clips=[
            {"name": "root|Unreal Take|Base Layer", "duration_seconds": 1.0, "frame_start": 0.0, "frame_end": 30.0},
        ],
    )


def test_mesh_converter_imports_without_legacy_top_level_core_package() -> None:
    sys.modules.pop("core", None)

    from src.converters.mesh_converter import FBXImporter, KotorModel

    assert FBXImporter.__name__ == "FBXImporter"
    assert KotorModel.__module__ == "src.core.geometry.model_data"


def test_unreal_source_fbx_import_routes_to_source_clip_before_mesh_conversion() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_import_external_model)

    fbx_source_route = 'role == "source" and suffix == ".fbx" and controller is not None and mode_name == "UNREAL_TO_KOTOR"'
    assert fbx_source_route in source
    assert "controller.load_source_clip(path)" in source
    assert "import_fbx_mesh_with_blender" in source
    assert "window.set_source_clip_preview(clip, mesh_model=mesh_model)" in source
    assert source.index(fbx_source_route) < source.index("model = self._load_external_retarget_model(path)")


def test_kotor_to_unreal_target_fbx_import_routes_to_unreal_skeleton_before_mesh_conversion() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_import_external_model)

    fbx_target_route = 'role == "target" and suffix == ".fbx" and controller is not None and mode_name == "KOTOR_TO_UNREAL"'
    assert fbx_target_route in source
    assert "controller.set_target_unreal_skeleton(import_unreal_target_skeleton_from_fbx(path))" in source
    assert source.index(fbx_target_route) < source.index("model = self._load_external_retarget_model(path)")


def test_source_clip_preview_model_preserves_imported_skeleton_for_viewport() -> None:
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    model = build_source_clip_preview_model(_sample_clip())

    assert model.name == "root|Unreal Take|Base Layer"
    assert model.node_count() == 3
    assert getattr(model, "_gr_source_clip_preview") is True
    assert getattr(model, "_gr_source_clip_node_count") == 2
    assert [anim.name for anim in model.animations] == ["root|Unreal Take|Base Layer"]
    assert model.animations[0].length == 1.0
    assert [node.name for node in model.root_node.children] == ["Root"]
    root = model.root_node.children[0]
    assert [node.name for node in root.children] == ["RHand"]
    assert getattr(root.children[0], "external_world_position") == (1.0, 0.0, 0.0)
    bb_min, bb_max = getattr(model, "_gr_render_bounds")
    assert bb_min[0] < bb_max[0]
    assert bb_min[1] < bb_max[1]
    assert bb_min[2] < bb_max[2]


def test_source_clip_preview_model_can_include_fbx_mesh_geometry() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.geometry.model_data import GameVersion
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    mesh_model = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["root"],
            "actions": [{"name": "root|Unreal Take|Base Layer"}],
            "meshes": [
                {
                    "name": "Body",
                    "vertices": [[-1, 0, 0], [1, 0, 0], [0, 0, 2]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0, 0], [1, 0], [0.5, 1]],
                    "faces": [[0, 1, 2]],
                    "materials": [{"name": "BodyMat", "texture": "Body_D", "diffuse": [0.5, 0.6, 0.7]}],
                }
            ],
        },
        model_name="source_body",
        game_version=GameVersion.K1,
    )

    model = build_source_clip_preview_model(_sample_clip(), mesh_model=mesh_model)
    mesh_nodes = [node for node in model.all_nodes() if getattr(node, "_gr_fbx_mesh_preview_node", False)]

    assert getattr(model, "_gr_source_clip_preview") is True
    assert getattr(model, "_gr_source_clip_mesh_count") == 1
    assert len(mesh_nodes) == 1
    assert mesh_nodes[0].name == "Body"
    assert mesh_nodes[0].texture == "Body_D"
    assert mesh_nodes[0].vertex_space == 1
    assert mesh_nodes[0].vertices
    assert mesh_nodes[0].faces == [(0, 1, 2)]


def test_retarget_window_source_clip_preview_populates_animation_list() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_clip_preview(_sample_clip())

        assert window.panel.anim_list.count() == 1
        assert window.panel.selected_animation() == "root|Unreal Take|Base Layer"
        assert window.panel.anim_list.currentItem().data(QtCore.Qt.UserRole) is not None
        assert window.source_viewport.model is not None
        assert getattr(window.source_viewport.model, "_gr_source_clip_preview") is True
    finally:
        window.close()


def test_mesh_converter_has_blender_fbx_mesh_fallback() -> None:
    from src.converters.mesh_converter import FBXImporter

    source = inspect.getsource(FBXImporter.import_file)

    assert "import_fbx_mesh_with_blender" in source
    assert source.index("import_fbx_mesh_with_blender") > source.index("_load_trimesh")
