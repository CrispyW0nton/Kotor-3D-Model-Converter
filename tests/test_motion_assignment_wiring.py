"""M12/T1204 source-level guardrails for motion assignment HUD wiring."""

from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t1204_inspector_replaces_animation_library_stub():
    source = _read("src/gui/panels/qt_inspector_panel.py")

    assert "assignMotionsRequested" in source
    assert "selected_motion_source" in source
    assert "selected_motion_supermodel" in source
    assert "Open Animation Library" not in source


def test_t1204_character_builder_connects_assignment_signal_to_workflow():
    source = _read("src/gui/panels/qt_character_builder_panel.py")

    assert "assignMotionsRequested.connect" in source
    assert "_on_assign_motions_requested" in source
    assert "assign_motion_source(" in source
    assert "_on_refresh_preview_animations_requested()" in source


def test_t1204_workflow_exports_motion_assignment_api():
    source = _read("src/core/characters/headless_body_workflow.py")

    assert "MotionAssignmentResult" in source
    assert "MOTION_SOURCE_INHERITED" in source
    assert "def assign_motion_source" in source
    assert "def motion_assignment_options" in source
    assert "MOTIONS_MISSING" in source
