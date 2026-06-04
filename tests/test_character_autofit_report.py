from __future__ import annotations

from src.core.characters.character_autofit_report import summarize_auto_fit_quality


def _clean_skeleton_fit_report() -> dict:
    roles = [
        "pelvis",
        "head",
        "left",
        "right",
        "left_foot",
        "right_foot",
        "left_toe",
        "right_toe",
    ]
    return {
        "fit_policy": "bone_landmark_basis",
        "confidence": 0.92,
        "fallback_used": False,
        "source_frame": {
            "toe_forward_alignment": 0.96,
            "landmarks": {
                "left_foot": "L_Foot",
                "right_foot": "R_Foot",
                "left_toe": "L_Foot_end",
                "right_toe": "R_Foot_end",
            },
            "landmark_sources": {
                role: "imported_skeleton"
                for role in roles
            },
        },
        "target_frame": {
            "toe_forward_alignment": 0.94,
            "landmarks": {
                "left_foot": "lfoot_g",
                "right_foot": "rfoot_g",
                "left_toe": "lfootT_g",
                "right_toe": "rfootT_g",
            },
        },
        "fit_transform": {
            "landmark_alignment": {
                "pair_count": 8,
                "paired_roles": roles,
                "rms_error": 0.04,
                "max_error": 0.08,
                "worst_pair_role": "right_toe",
            },
        },
        "auto_fit_report": {
            "confidence": 0.92,
            "fallback_used": False,
        },
    }


def test_auto_fit_quality_summary_passes_clean_imported_skeleton_fit() -> None:
    summary = summarize_auto_fit_quality(_clean_skeleton_fit_report())

    assert summary["stage"] == "passed"
    assert summary["imported_skeleton_driven"] is True
    assert summary["source_landmark_domain"] == "skeleton_landmarks"
    assert summary["pair_count"] == 8
    assert summary["rms_error"] == 0.04
    assert summary["max_error"] == 0.08
    assert summary["worst_pair_role"] == "right_toe"
    assert summary["reasons"] == []
    assert "Skeleton-driven Auto-Fit passed" in summary["summary"]


def test_auto_fit_quality_summary_marks_bounds_fallback() -> None:
    summary = summarize_auto_fit_quality({
        "fit_policy": "origin_height",
        "confidence": 0.35,
        "fallback_used": True,
        "auto_fit_report": {
            "confidence": 0.35,
            "fallback_used": True,
        },
    })

    assert summary["stage"] == "fallback"
    assert "fallback_fit_used" in summary["reasons"]
    assert "paired_landmark_alignment_missing" in summary["reasons"]
    assert "fallback" in summary["summary"].lower()


def test_auto_fit_quality_summary_flags_weak_skeleton_evidence() -> None:
    report = _clean_skeleton_fit_report()
    report["fit_transform"]["landmark_alignment"].update({
        "pair_count": 3,
        "rms_error": 0.42,
        "max_error": 0.55,
        "worst_pair_role": "left",
    })
    report["source_frame"]["toe_forward_alignment"] = -0.1

    summary = summarize_auto_fit_quality(report)

    assert summary["stage"] == "needs_review"
    assert "too_few_paired_landmarks" in summary["reasons"]
    assert "rms_error_high" in summary["reasons"]
    assert "max_error_high" in summary["reasons"]
    assert "source_toe_forward_low" in summary["reasons"]
    assert "needs review" in summary["summary"].lower()
