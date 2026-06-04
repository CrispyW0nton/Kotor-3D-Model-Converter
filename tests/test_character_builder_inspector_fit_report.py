from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6 import QtWidgets  # noqa: E402

from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


@pytest.fixture
def inspector(qapp):
    panel = QtInspectorPanel()
    panel.set_step(1)
    yield panel
    panel.deleteLater()


def _fit_label(panel: QtInspectorPanel) -> QtWidgets.QLabel:
    label = panel.findChild(QtWidgets.QLabel, "CharacterBuilderImportFitReportLabel")
    assert label is not None
    return label


def _base_report() -> dict:
    return {
        "fit_policy": "bone_landmark_basis",
        "scale": 0.207754,
        "scale_basis": "paired_skeleton_landmark_height",
        "reference": "n_mandalorian",
        "source_frame": {"confidence": 0.95},
        "target_frame": {"confidence": 0.90},
        "auto_fit_report": {
            "source_forward_axis": "+y",
            "source_up_axis": "+z",
            "target_forward_axis": "+y",
            "target_up_axis": "+z",
            "confidence": 0.95,
            "fallback_used": False,
            "height_source": "landmarks",
            "ground_origin_basis": "feet",
            "used_landmarks": [
                "source:head=Head",
                "source:pelvis=Pelvis",
                "target:head=head_g",
            ],
        },
        "warnings": [],
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
    }


def test_import_fit_report_shows_labeled_fbx_armature_guides(inspector):
    report = _base_report()
    report["source_imported_armature"] = {
        "source": "imported_fbx_armature",
        "guide_joint_count": 65,
        "scene_guide_joint_count": 65,
        "armature_names": ["Armature"],
    }

    inspector.set_import_fit_report(report)

    text = _fit_label(inspector).text()
    assert "Auto-fit: bone_landmark_basis" in text
    assert "Reference: n_mandalorian." in text
    assert "Source skeleton guides: FBX armature Armature, 65 guide joints." in text
    assert "Final skeleton: selected KOTOR base; imported mesh is geometry payload." in text


def test_import_fit_report_shows_unlabeled_imported_skeleton_guides(inspector):
    report = _base_report()
    report["source_imported_armature"] = {
        "source": "imported_skeleton_nodes",
        "guide_joint_count": 67,
        "scene_guide_joint_count": 67,
        "armature_names": [],
    }

    inspector.set_import_fit_report(report)

    text = _fit_label(inspector).text()
    assert "Source skeleton guides: 67 imported skeleton guide nodes." in text
    assert "FBX armature" not in text
