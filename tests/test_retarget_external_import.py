"""Regression tests for Retarget Workbench external-file import routing."""

from __future__ import annotations

import inspect
import sys


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
    assert source.index(fbx_source_route) < source.index("model = self._load_external_retarget_model(path)")


def test_kotor_to_unreal_target_fbx_import_routes_to_unreal_skeleton_before_mesh_conversion() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_import_external_model)

    fbx_target_route = 'role == "target" and suffix == ".fbx" and controller is not None and mode_name == "KOTOR_TO_UNREAL"'
    assert fbx_target_route in source
    assert "controller.set_target_unreal_skeleton(import_unreal_target_skeleton_from_fbx(path))" in source
    assert source.index(fbx_target_route) < source.index("model = self._load_external_retarget_model(path)")
