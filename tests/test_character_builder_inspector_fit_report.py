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
        "fit_transform": {
            "landmark_alignment": {
                "pair_count": 6,
                "rms_error": 0.05879,
                "max_error": 0.12894,
                "worst_pair_role": "pelvis",
            },
        },
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
    }


def _clean_skeleton_quality_report() -> dict:
    report = _base_report()
    report["scale"] = 0.16
    report["source_frame"] = {
        "confidence": 0.92,
        "toe_forward_alignment": 0.96,
        "landmarks": {
            "left_foot": "L_Foot",
            "right_foot": "R_Foot",
            "left_toe": "L_Foot_end",
            "right_toe": "R_Foot_end",
        },
        "landmark_sources": {
            "pelvis": "imported_skeleton",
            "head": "imported_skeleton",
            "left": "imported_skeleton",
            "right": "imported_skeleton",
            "left_foot": "imported_skeleton",
            "right_foot": "imported_skeleton",
            "left_toe": "imported_skeleton",
            "right_toe": "imported_skeleton",
        },
    }
    report["target_frame"] = {
        "confidence": 0.95,
        "toe_forward_alignment": 0.94,
        "landmarks": {
            "left_foot": "lfoot_g",
            "right_foot": "rfoot_g",
            "left_toe": "lfootT_g",
            "right_toe": "rfootT_g",
        },
    }
    report["fit_transform"]["landmark_alignment"].update({
        "pair_count": 8,
        "rms_error": 0.04,
        "max_error": 0.08,
        "worst_pair_role": "right_toe",
    })
    report["source_imported_armature"] = {
        "source": "imported_fbx_armature",
        "guide_joint_count": 65,
        "scene_guide_joint_count": 65,
        "armature_names": ["Armature"],
    }
    return report


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
    assert "Fit quality: 6 paired landmarks, RMS 0.059, max 0.129, worst pelvis." in text
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


def test_import_fit_report_shows_core_quality_summary(inspector):
    inspector.set_import_fit_report(_clean_skeleton_quality_report())

    text = _fit_label(inspector).text()
    assert "Fit readiness: Skeleton-driven Auto-Fit passed" in text
    assert "8 skeleton pairs, RMS 0.040, max 0.080" in text
    assert "Final skeleton: selected KOTOR base" in text
