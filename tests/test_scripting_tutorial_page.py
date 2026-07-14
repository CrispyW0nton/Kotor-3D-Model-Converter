from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_scripting_tutorials_cover_every_preserved_workflow_and_route_to_owner() -> None:
    from PySide6 import QtWidgets

    from src.gui.windows.qt_scripting_tutorial_page import QtScriptingTutorialPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtScriptingTutorialPage()
    destinations: list[str] = []
    page.destinationRequested.connect(destinations.append)
    try:
        assert page.topic_list.count() == 9
        for key in (
            "first_script",
            "dialogue",
            "quest",
            "data_patch",
            "voice",
            "blueprints",
            "package",
            "map_handoff",
            "legacy",
        ):
            assert page.show_guide(key)
            assert page.steps.count() >= 5
            assert "proof" in page.proof_label.text().casefold() or "retail" in page.proof_label.text().casefold()
            page.open_button.click()
        assert set(destinations) == {"code", "quest", "tables", "voice", "blueprint", "package", "integrated", "project"}
    finally:
        page.deleteLater()
        app.processEvents()
