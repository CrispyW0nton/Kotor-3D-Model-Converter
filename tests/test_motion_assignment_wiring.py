"""M12/T1204 source-level guardrails for motion assignment HUD wiring."""

from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]

NATIVE_SOURCE_FALLBACKS = {
    "src/gui/panels/qt_inspector_panel.py": (
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_inspector_panel.py"
    ),
    "src/gui/panels/qt_character_builder_panel.py": (
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_character_builder_panel.py"
    ),
    "src/core/characters/headless_body_workflow.py": (
        "native/GhostRigger.Core.Workflow/Python/src/core/characters/headless_body_workflow.py"
    ),
}


def _read(path: str) -> str:
    resolved = ROOT / path
    if not resolved.exists() and path in NATIVE_SOURCE_FALLBACKS:
        resolved = ROOT / NATIVE_SOURCE_FALLBACKS[path]
    return resolved.read_text(encoding="utf-8")


def _method_block(source: str, name: str) -> str:
    start = source.index(f"def {name}")
    end = source.find("\n    def ", start + 1)
    if end < 0:
        end = len(source)
    return source[start:end]


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


def test_t1204_character_builder_motion_and_export_handlers_use_safe_workflow_import():
    source = _read("src/gui/panels/qt_character_builder_panel.py")

    for name in (
        "_on_assign_motions_requested",
        "_on_refresh_preview_animations_requested",
        "_on_play_preview_animation_requested",
        "_on_stop_preview_animation_requested",
        "_on_export_requested",
        "_start_preview_animation",
    ):
        block = _method_block(source, name)
        assert "from core.characters import headless_body_workflow as _wf" not in block
        assert "from core.characters.headless_body_workflow import CheckActorResult" not in block
        assert "_workflow_module()" in block


def test_t1205_character_builder_preview_sets_gpu_skinning_base_pose():
    source = _read("src/gui/panels/qt_character_builder_panel.py")
    block = _method_block(source, "_start_preview_animation")

    assert "base_pose = engine.evaluate(0.0)" in block
    assert "viewport.set_anim_base_pose(base_pose)" in block
    assert "viewport.set_animation_pose(" in block


def test_t1205_character_builder_preview_fallback_uses_live_viewport():
    source = _read("src/gui/panels/qt_character_builder_panel.py")
    block = _method_block(source, "_on_play_preview_animation_requested")

    assert 'viewport=getattr(self, "viewport", None)' in block


def test_t1204_workflow_exports_motion_assignment_api():
    source = _read("src/core/characters/headless_body_workflow.py")

    assert "MotionAssignmentResult" in source
    assert "MOTION_SOURCE_INHERITED" in source
    assert "def assign_motion_source" in source
    assert "def motion_assignment_options" in source
    assert "MOTIONS_MISSING" in source
