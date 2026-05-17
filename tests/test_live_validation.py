"""M9/T901 source-level guardrails for live validation wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_t901_builder_owns_debounced_live_validation_timer() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "self._live_validation_timer = QtCore.QTimer(self)" in src
    assert "self._live_validation_timer.setSingleShot(True)" in src
    assert "self._live_validation_timer.setInterval(200)" in src
    assert "self._live_validation_timer.timeout.connect(self._run_live_validation)" in src
    assert "def _schedule_live_validation" in src
    assert "timer.start()" in src


def test_t901_manual_and_live_validation_share_runner() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "def _on_validate_requested" in src
    assert 'self._run_validation(reason="manual", update_status=True)' in src
    assert "def _run_live_validation" in src
    assert "self._run_validation(reason=reason or \"live\", update_status=False)" in src
    assert "result = _wf.validate_for_export(self.scene, strict=True)" in src
    assert "self._last_validation_result = result" in src
    assert "self.inspector.set_validate_for_export_result(result)" in src
    assert "self.bottom_strip.set_validation(" in src


def test_t901_scene_mutation_paths_schedule_live_validation() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    for reason in [
        "game_changed",
        "mode_unlocked",
        "body_guide_history",
        "viewport_node_moved",
        "model_loaded",
        "composite_loaded",
        "skeleton_template_applied",
        "skeleton_generated",
        "hand_mask_changed",
        "motions_assigned",
        "head_rigged",
        "face_rigged",
        "phoneme_calibrated",
    ]:
        assert f'self._schedule_live_validation("{reason}")' in src
    assert 'self._schedule_live_validation(f"mode_{source}")' in src
