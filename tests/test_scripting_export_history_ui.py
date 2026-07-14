from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_project_history_page_filters_receipts_and_emits_asset_recovery_intent() -> None:
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import QtScriptingProjectHistoryPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtScriptingProjectHistoryPage()
    recovered: list[tuple[str, str]] = []
    page.recoverAssetRevisionRequested.connect(lambda revision_id, asset_id: recovered.append((revision_id, asset_id)))
    try:
        page.set_asset_rows(
            [
                {
                    "asset_id": "asset_script",
                    "resref": "story_run",
                    "restype": "ncs",
                    "role": "runtime",
                    "path": "scripts/story_run.ncs",
                    "dependencies": [],
                },
                {
                    "asset_id": "asset_dialogue",
                    "resref": "story_line",
                    "restype": "dlg",
                    "role": "runtime",
                    "path": "dialogues/story_line.dlg",
                    "dependencies": [],
                },
            ]
        )
        page.set_revision_rows(
            [
                {
                    "revision_id": "rev_script",
                    "created_at": "2026-07-13T01:00:00Z",
                    "message": "Script pass",
                    "project_revision": 2,
                    "asset_count": 1,
                    "asset_ids": ["asset_script"],
                },
                {
                    "revision_id": "rev_dialogue",
                    "created_at": "2026-07-13T02:00:00Z",
                    "message": "Dialogue pass",
                    "project_revision": 3,
                    "asset_count": 1,
                    "asset_ids": ["asset_dialogue"],
                },
            ]
        )
        page.revision_asset_filter_combo.setCurrentIndex(
            page.revision_asset_filter_combo.findData("asset_dialogue")
        )
        assert page.revision_view.topLevelItemCount() == 1
        page.revision_view.setCurrentItem(page.revision_view.topLevelItem(0))
        page.recover_asset_revision_button.click()
        assert recovered == [("rev_dialogue", "asset_dialogue")]

        page.set_export_history_rows(
            [
                {
                    "receipt_id": "receipt_package",
                    "created_at": "2026-07-13T03:00:00Z",
                    "operation": "package",
                    "outcome": "succeeded",
                    "destination": "C:/mods/story.mod",
                    "backup_path": "",
                    "receipt_path": "C:/mods/story.mod.ghoststudio.json",
                    "summary": "Exact readback passed",
                    "engine_proof": "not_recorded",
                    "engine_proof_evidence": "",
                    "input_hashes": [
                        {
                            "filename": "story_run.ncs",
                            "sha256": "a" * 64,
                            "byte_count": 128,
                            "source_asset_id": "asset_script",
                        }
                    ],
                    "issues": [],
                },
                {
                    "receipt_id": "receipt_install",
                    "created_at": "2026-07-13T04:00:00Z",
                    "operation": "install_override",
                    "outcome": "failed",
                    "destination": "C:/Games/KOTOR2/Override",
                    "backup_path": "C:/Games/KOTOR2/GhostStudioBackups/test",
                    "receipt_path": "",
                    "summary": "Conflict blocked",
                    "engine_proof": "not_recorded",
                    "input_hashes": [],
                    "issues": [{"severity": "blocking", "message": "Existing file differs"}],
                },
            ]
        )
        assert page.export_history_view.topLevelItemCount() == 2
        page.export_history_outcome_combo.setCurrentIndex(
            page.export_history_outcome_combo.findData("failed")
        )
        assert page.export_history_view.topLevelItem(0).isHidden()
        assert not page.export_history_view.topLevelItem(1).isHidden()
        page.export_history_outcome_combo.setCurrentIndex(0)
        page.export_history_search_edit.setText("a" * 32)
        assert not page.export_history_view.topLevelItem(0).isHidden()
        assert page.export_history_view.topLevelItem(1).isHidden()
        page.export_history_view.setCurrentItem(page.export_history_view.topLevelItem(0))
        assert "SHA-256 " + "a" * 64 in page.export_history_details.toPlainText()
        assert "Engine proof: Not recorded" in page.export_history_details.toPlainText()
    finally:
        page.deleteLater()
        app.processEvents()
