from __future__ import annotations

import os


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_feedback_panel_exposes_textual_state_progress_and_actions() -> None:
    app = _qapp()

    from src.gui.qt_lib.windows.progress_toast import (
        FeedbackAction,
        OperationFeedback,
        OperationPhase,
        QtProgressPanel,
    )

    panel = QtProgressPanel()
    action_keys: list[str] = []
    cancelled: list[bool] = []
    panel.actionTriggered.connect(action_keys.append)
    panel.cancelRequested.connect(lambda: cancelled.append(True))
    panel.set_feedback(
        OperationFeedback(
            phase=OperationPhase.BLOCKED,
            title="Creature template was not found",
            detail="GhostStudio could not place c_gizka.utc.",
            subject="c_gizka.utc",
            reason="No matching K2 UTC was available.",
            searched_scopes=("project resources", "K2 Override", "K2 base game files"),
            actions=(
                FeedbackAction("refresh_resources", "Scan Again", "Refresh the resource catalog."),
                FeedbackAction("choose_another", "Choose Another", "Return to the creature list."),
            ),
            cancellable=True,
            preserves_work=True,
        )
    )
    panel.show()
    app.processEvents()

    assert panel.property("operationPhase") == "blocked"
    assert panel.phase_label.text() == "Blocked"
    assert panel.accessibleName() == "Creature template was not found"
    assert "c_gizka.utc" in panel.accessibleDescription()
    assert "Searched: project resources; K2 Override; K2 base game files" in panel.context_label.text()
    assert panel.preservation_label.text() == "Your current work was preserved."
    assert panel.action_button("refresh_resources").toolTip() == "Refresh the resource catalog."
    assert panel.minimumHeight() >= panel.sizeHint().height()

    panel.action_button("refresh_resources").click()
    panel.cancel_button.click()

    assert action_keys == ["refresh_resources"]
    assert cancelled == [True]


def test_feedback_panel_distinguishes_busy_success_stale_and_failed_without_color() -> None:
    _qapp()

    from src.gui.qt_lib.windows.progress_toast import (
        OperationFeedback,
        OperationPhase,
        QtProgressPanel,
    )

    panel = QtProgressPanel()
    expected_labels = {
        OperationPhase.BUSY: "In progress",
        OperationPhase.SUCCEEDED: "Completed",
        OperationPhase.STALE: "Update needed",
        OperationPhase.FAILED: "Failed",
    }
    for phase, label in expected_labels.items():
        panel.set_feedback(OperationFeedback(phase=phase, title=label, detail="State detail"))
        assert panel.phase_label.text() == label
        assert panel.property("operationPhase") == phase.value

    panel.set_feedback(
        OperationFeedback(
            phase=OperationPhase.BUSY,
            title="Scanning resources",
            detail="2 of 5 locations checked.",
            progress_value=2,
            progress_total=5,
            cancellable=True,
        )
    )
    panel.show()
    _qapp().processEvents()
    assert panel.progress.maximum() == 5
    assert panel.progress.value() == 2
    assert panel.cancel_button.isVisible()


def test_feedback_contract_rejects_actions_without_identity_or_label() -> None:
    import pytest
    from src.gui.qt_lib.windows.progress_toast import FeedbackAction

    with pytest.raises(ValueError, match="stable key"):
        FeedbackAction("", "Retry")
    with pytest.raises(ValueError, match="visible label"):
        FeedbackAction("retry", "")


def test_resource_browser_turns_empty_and_filtered_results_into_recoverable_states() -> None:
    app = _qapp()

    from src.gui.qt_lib.panels.qt_resource_panel import QtResourceBrowserPanel
    from src.gui.qt_lib.windows.progress_toast import OperationPhase

    panel = QtResourceBrowserPanel()
    scans: list[bool] = []
    panel.scanRequested.connect(lambda: scans.append(True))

    assert panel.feedback_panel.feedback.phase is OperationPhase.IDLE
    assert "Scan" in panel.feedback_panel.feedback.detail

    panel.set_resources([])
    app.processEvents()
    assert panel.feedback_panel.feedback.phase is OperationPhase.BLOCKED
    assert panel.feedback_panel.feedback.title == "No resources were indexed"
    panel.feedback_panel.action_button("scan_resources").click()
    assert scans == [True]

    panel.set_resources(
        [
            {
                "game": "K2",
                "resref": "c_gizka",
                "type": "utc",
                "source": "K2 base game files",
            }
        ]
    )
    panel.search_edit.setText("missing")
    app.processEvents()
    assert panel.listbox.count() == 0
    assert panel.feedback_panel.feedback.phase is OperationPhase.BLOCKED
    assert panel.feedback_panel.feedback.title == "No resources match these filters"
    assert panel.feedback_panel.feedback.subject == "missing"

    panel.feedback_panel.action_button("clear_filters").click()
    app.processEvents()
    assert panel.search_edit.text() == ""
    assert panel.listbox.count() == 1
    assert panel.feedback_panel.feedback.phase is OperationPhase.READY


def test_structured_resource_failure_populates_panel_and_error_report() -> None:
    _qapp()

    from src.core.resources.game_resource_provider import (
        GameResourceNotFoundError,
        GameResourceQuery,
        InMemoryGameResourceProvider,
    )
    from src.gui.dialogs.error_report import QtErrorReportDialog, report_from_exception
    from src.gui.qt_lib.panels.qt_resource_panel import QtResourceBrowserPanel
    from src.gui.qt_lib.windows.progress_toast import OperationPhase

    provider = InMemoryGameResourceProvider(scope_label="K2 project resources")
    try:
        provider.resolve(GameResourceQuery(game="k2", resref="c_gizka", restype="utc"))
    except GameResourceNotFoundError as exc:
        failure = exc
    else:  # pragma: no cover - proof guard
        raise AssertionError("Expected a structured missing-resource failure.")

    panel = QtResourceBrowserPanel()
    panel.show_lookup_failure(failure)
    assert panel.feedback_panel.feedback.phase is OperationPhase.FAILED
    assert panel.feedback_panel.feedback.subject == "c_gizka.utc"
    assert panel.feedback_panel.feedback.searched_scopes == ("K2 project resources",)

    report = report_from_exception("file_not_found", failure, context="Placing creature")
    assert report.subject == "c_gizka.utc"
    assert report.reason == "No matching resource was available."
    assert report.searched_scopes == ("K2 project resources",)
    assert report.preservation_message == "No project or source data was changed."
    assert "Scan the resource catalog again." in report.recovery_guidance

    dialog = QtErrorReportDialog(report)
    assert dialog.accessibleName() == "File Not Found"
    assert "c_gizka.utc" in dialog.accessibleDescription()
    assert dialog.message_label.text().startswith("Placing creature:")
