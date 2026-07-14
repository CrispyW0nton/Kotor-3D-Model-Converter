from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtWidgets

from src.gui.controllers.scripting_blueprint_controller import ScriptingBlueprintController
from src.gui.windows.qt_scripting_blueprint_page import QtScriptingBlueprintPage


def _fixture_bytes() -> bytes:
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, GFFStruct, bytes_gff

    gff = GFF(GFFContent.UTP)
    gff.root.set_string("Tag", "controller_fixture")
    gff.root.set_resref("TemplateResRef", ResRef("ctrl_fixture"))
    gff.root.set_uint8("Useable", 1)
    inventory = GFFList()
    item = GFFStruct(91)
    item.set_resref("InventoryRes", ResRef("g_w_blstrpstl01"))
    inventory.append(item)
    gff.root.set_list("ItemList", inventory)
    return bytes_gff(gff)


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _controller() -> tuple[QtWidgets.QMainWindow, QtScriptingBlueprintPage, ScriptingBlueprintController]:
    window = QtWidgets.QMainWindow()
    page = QtScriptingBlueprintPage(window)
    window.blueprint_page = page
    window.setCentralWidget(page)
    controller = ScriptingBlueprintController(window, game_provider=lambda: "K2", parent=window)
    return window, page, controller


def test_blueprint_controller_opens_edits_and_exposes_verified_project_snapshot(
    app: QtWidgets.QApplication,
    tmp_path: Path,
) -> None:
    source = tmp_path / "ctrl_fixture.utp"
    source.write_bytes(_fixture_bytes())
    window, page, controller = _controller()
    changes: list[bool] = []
    opened: list[tuple[str, str]] = []
    controller.contentChanged.connect(lambda: changes.append(True))
    controller.documentOpened.connect(lambda resref, restype: opened.append((resref, restype)))
    try:
        assert controller.open_path(source)
        assert opened == [("ctrl_fixture", "utp")]
        assert page.model.rowCount() == 4
        assert page.select_path("$/Tag")
        app.processEvents()
        page.value_edit.setPlainText("edited_in_controller")
        page.apply_button.click()
        app.processEvents()
        assert controller.document.value("$/Tag") == "edited_in_controller"
        assert changes == [True]
        assert page.selected_path_edit.text() == "$/Tag"
        assert page.dirty_label.text() == "Unsaved changes"

        snapshot = controller.current_resource_snapshot()
        assert snapshot is not None
        assert snapshot["resref"] == "ctrl_fixture"
        assert snapshot["restype"] == "utp"
        assert snapshot["role"] == "runtime"
        assert snapshot["game"] == "K2"
        assert snapshot["metadata"]["semantic_readback_verified"] is True
        from pykotor.resource.formats.gff import read_gff

        assert read_gff(snapshot["data"]).root.get_string("Tag") == "edited_in_controller"
        assert controller.resource_snapshots() == (snapshot,)
    finally:
        window.deleteLater()
        app.processEvents()


def test_blueprint_controller_rejects_invalid_edit_without_mutating_document(
    app: QtWidgets.QApplication,
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid_edit.utp"
    source.write_bytes(_fixture_bytes())
    window, page, controller = _controller()
    errors: list[str] = []
    controller.operationFailed.connect(errors.append)
    try:
        assert controller.open_path(source)
        assert controller.document.value("$/Useable") == 1
        assert controller.edit_field("$/Tag", "valid_unsaved_change")
        assert controller.document.dirty
        assert not controller.edit_field("$/Useable", "999")
        assert controller.document.value("$/Useable") == 1
        assert controller.document.value("$/Tag") == "valid_unsaved_change"
        assert controller.document.dirty
        assert "between 0 and 255" in errors[-1]
        assert page.selected_path_edit.text() == "$/Useable"
    finally:
        window.deleteLater()
        app.processEvents()


def test_blueprint_controller_save_as_is_atomic_and_validation_reports_content_mismatch(
    app: QtWidgets.QApplication,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.utp"
    source.write_bytes(_fixture_bytes())
    output = tmp_path / "renamed.utc"
    window, page, controller = _controller()
    diagnostics: list[tuple[list[dict[str, object]], str]] = []
    controller.diagnosticsChanged.connect(lambda rows, summary: diagnostics.append((list(rows), summary)))
    try:
        assert controller.open_path(source)
        assert controller.edit_field("$/Tag", "saved_value")
        assert controller.save_as(output)
        assert output.is_file()
        assert controller.resref == "renamed"
        assert controller.document.source_path == output
        assert not controller.document.dirty
        from pykotor.resource.formats.gff import read_gff

        assert read_gff(output).root.get_string("Tag") == "saved_value"
        rows = controller.validate()
        assert any(row.code == "gff.extension_content_mismatch" for row in rows)
        assert diagnostics[-1][0][0]["severity"] == "warning"
        assert "1 warning" in diagnostics[-1][1]
        assert page.diagnostics.topLevelItemCount() == 1
    finally:
        window.deleteLater()
        app.processEvents()


def test_blueprint_controller_open_bytes_search_close_and_missing_path(
    app: QtWidgets.QApplication,
    tmp_path: Path,
) -> None:
    window, page, controller = _controller()
    errors: list[str] = []
    closed: list[bool] = []
    statuses: list[str] = []
    controller.operationFailed.connect(errors.append)
    controller.documentClosed.connect(lambda: closed.append(True))
    controller.statusChanged.connect(statuses.append)
    try:
        assert controller.open_bytes(_fixture_bytes(), resref="archive_plc")
        assert controller.document.source_path is None
        matches = controller.search("inventory")
        assert {row.path for row in matches} == {"$/ItemList/#0/InventoryRes"}
        assert "1 GFF field" in statuses[-1]
        assert not controller.open_path(tmp_path / "missing.utp")
        assert controller.resref == "archive_plc"  # Failed open preserves the working document.
        assert "does not exist" in errors[-1]

        controller.close()
        assert closed == [True]
        assert controller.current_resource_snapshot() is None
        assert controller.resource_snapshots() == ()
        assert page.model.rowCount() == 0
    finally:
        window.deleteLater()
        app.processEvents()
