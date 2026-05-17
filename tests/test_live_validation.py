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


def test_t902_validation_banner_opens_full_report_dialog() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "class _ValidationIssueTableModel" in src
    assert "class QtValidationReportDialog" in src
    assert "self.bottom_strip.bannerClicked.connect(self._on_validation_banner_clicked)" in src
    assert "def _on_validation_banner_clicked" in src
    assert "dialog = QtValidationReportDialog(issues, self)" in src
    assert "dialog.jumpRequested.connect(self._on_validation_report_jump_requested)" in src
    assert "dialog.exec()" in src


def test_t902_report_rows_show_issue_fields_and_jump_to_node() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    for field in ["Severity", "Code", "Message", "Slot", "Node"]:
        assert field in src
    assert "self._jump_btn = QtWidgets.QPushButton(\"Jump to Bone\")" in src
    assert "jumpRequested = QtCore.Signal(str)" in src
    assert "def _on_validation_report_jump_requested" in src
    assert "def _find_viewport_node" in src
    assert "viewport.set_selected_node(node)" in src
    assert "Selected validation target" in src


def test_t903_inspector_exposes_mode_aware_run_rom_button() -> None:
    src = _read("src/gui/qt_inspector_panel.py")

    assert "romTestRequested" in src
    assert "self._rom_test_btn = QtWidgets.QPushButton(\"Run ROM\")" in src
    assert "self._rom_test_btn.clicked.connect(self.romTestRequested.emit)" in src
    assert "\"Run Body ROM\"" in src
    assert "\"Run Head ROM\"" in src
    assert "\"Run Composite ROM\"" in src
    assert "\"Run Creature ROM\"" in src


def test_t903_builder_wires_run_rom_to_workflow_preview_and_validation() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "self.inspector.romTestRequested.connect(" in src
    assert "self._on_run_rom_test_requested" in src
    assert "result = _wf.run_rom_test(self.scene, viewport=viewport)" in src
    assert "self.bottom_strip.set_frame_range(0, frames)" in src
    assert "self.bottom_strip.set_playing(True)" in src
    assert "self._schedule_live_validation(\"rom_test\")" in src


def test_t903_workflow_exposes_run_rom_test_bridge() -> None:
    src = _read("src/core/headless_body_workflow.py")

    assert "def run_rom_test(" in src
    assert "assign_motion_source(scene, MOTION_SOURCE_ROM)" in src
    assert "play_preview_animation(scene, \"generated_rom\"" in src
    assert "viewport.set_animation_pose(" in src
    assert "\"run_rom_test\"" in src


def test_t904_pre_export_gate_blocks_errors_and_prompts_warnings() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "def _confirm_pre_export_validation" in src
    assert 'self._run_validation(reason="pre_export_gate", update_status=False)' in src
    assert "Export Warnings" in src
    assert "Export anyway" in src
    assert "QtWidgets.QMessageBox.Warning" in src
    assert "box.addButton(\"Cancel\", QtWidgets.QMessageBox.RejectRole)" in src
    assert "return True, True" in src
    assert "return False, False" in src


def test_t904_export_uses_warning_acknowledged_skip_validation_path() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "can_export, skip_validation = self._confirm_pre_export_validation()" in src
    assert "if not can_export:" in src
    assert "skip_validation=skip_validation" in src
    assert "def _format_validation_issue_lines" in src
