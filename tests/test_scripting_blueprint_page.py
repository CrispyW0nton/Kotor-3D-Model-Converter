from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtWidgets

from src.gui.windows.qt_scripting_blueprint_page import QtScriptingBlueprintPage


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "path": "$/Tag",
            "parent_path": "$",
            "label": "Tag",
            "field_type": "String",
            "kind": "field",
            "display_value": "fixture_placeable",
            "edit_text": "fixture_placeable",
            "editable": True,
            "depth": 0,
            "struct_id": None,
            "child_count": 0,
        },
        {
            "path": "$/InventoryList",
            "parent_path": "$",
            "label": "InventoryList",
            "field_type": "List",
            "kind": "field",
            "display_value": "1 struct(s)",
            "edit_text": "",
            "editable": False,
            "depth": 0,
            "struct_id": None,
            "child_count": 1,
        },
        {
            "path": "$/InventoryList/#0",
            "parent_path": "$/InventoryList",
            "label": "[0]",
            "field_type": "Struct",
            "kind": "list_item",
            "display_value": "Struct 501 (1 fields)",
            "edit_text": "",
            "editable": False,
            "depth": 1,
            "struct_id": 501,
            "child_count": 1,
        },
        {
            "path": "$/InventoryList/#0/InventoryRes",
            "parent_path": "$/InventoryList/#0",
            "label": "InventoryRes",
            "field_type": "ResRef",
            "kind": "field",
            "display_value": "g_w_blstrpstl01",
            "edit_text": "g_w_blstrpstl01",
            "editable": True,
            "depth": 2,
            "struct_id": None,
            "child_count": 0,
        },
    )


def test_blueprint_page_presents_complete_tree_filters_and_emits_typed_edit(app: QtWidgets.QApplication) -> None:
    page = QtScriptingBlueprintPage()
    edits: list[tuple[str, str]] = []
    searches: list[str] = []
    page.fieldEditRequested.connect(lambda path, text: edits.append((path, text)))
    page.searchRequested.connect(searches.append)
    try:
        page.set_document(
            {
                "content_type": "UTP",
                "resource_type": "utp",
                "source_path": "C:/project/fixture.utp",
                "root_struct_id": -1,
                "field_count": 4,
                "editable_field_count": 2,
                "dirty": True,
                "is_blueprint": True,
            }
        )
        page.set_field_rows(_rows())
        assert page.objectName() == "scriptingStudioBlueprintPage"
        assert page.property("ghostLayoutId") == "scriptingDialogueStudio.blueprints"
        assert page.model.rowCount() == 2
        inventory = page._items_by_path["$/InventoryList"]
        assert inventory.rowCount() == 1
        assert inventory.child(0, 0).rowCount() == 1
        assert page.resource_type_label.text() == "UTP blueprint"
        assert page.save_button.isEnabled()

        assert page.select_path("$/InventoryList/#0/InventoryRes")
        app.processEvents()
        assert page.selected_type_label.text() == "ResRef"
        assert "maximum 16" in page.format_hint_label.text()
        page.value_edit.setPlainText("edited_item")
        page.apply_button.click()
        assert edits == [("$/InventoryList/#0/InventoryRes", "edited_item")]

        page.search_edit.setText("fixture_placeable")
        app.processEvents()
        assert searches[-1] == "fixture_placeable"
        assert page.proxy.rowCount() == 1
        page.search_edit.clear()
        assert page.select_path("$/InventoryList")
        app.processEvents()
        assert page.value_edit.isReadOnly()
        assert not page.apply_button.isEnabled()
        assert "Containers are read-only" in page.format_hint_label.text()
    finally:
        page.deleteLater()
        app.processEvents()


def test_blueprint_page_open_save_validate_and_diagnostics_are_controller_driven(app: QtWidgets.QApplication) -> None:
    page = QtScriptingBlueprintPage()
    events: list[str] = []
    page.openRequested.connect(lambda: events.append("open"))
    page.saveRequested.connect(lambda: events.append("save"))
    page.saveAsRequested.connect(lambda: events.append("save_as"))
    page.validateRequested.connect(lambda: events.append("validate"))
    try:
        page.open_button.click()
        assert events == ["open"]
        page.set_document(
            {
                "content_type": "UTC",
                "resource_type": "utc",
                "source_path": "C:/project/npc.utc",
                "root_struct_id": -1,
                "field_count": 1,
                "editable_field_count": 1,
                "dirty": True,
                "is_blueprint": True,
            }
        )
        page.save_button.click()
        page.save_as_button.click()
        page.validate_button.click()
        assert events == ["open", "save", "save_as", "validate"]

        page.set_diagnostics(
            (
                {
                    "severity": "warning",
                    "code": "gff.extension_content_mismatch",
                    "path": "$",
                    "message": "Filename and content differ.",
                },
            )
        )
        assert page.diagnostics.topLevelItemCount() == 1
        assert "1 warning" in page.status_label.text()
        page.set_diagnostics(())
        assert "Verified semantic GFF readback" in page.status_label.text()
    finally:
        page.deleteLater()
        app.processEvents()


def test_blueprint_page_uses_theme_layout_hooks_without_file_or_format_ownership(app: QtWidgets.QApplication) -> None:
    page = QtScriptingBlueprintPage()
    try:
        page.apply_ghost_theme(object())
        page.apply_ghost_layout(
            SimpleNamespace(spacing_value=lambda name, default: 13 if name == "splitterHandleWidth" else 9)
        )
        assert page.splitter.handleWidth() == 13
        assert page.layout().spacing() == 9
    finally:
        page.deleteLater()
        app.processEvents()

    source = (ROOT / "src/gui/windows/qt_scripting_blueprint_page.py").read_text(encoding="utf-8")
    assert "QFileDialog" not in source
    assert "read_gff" not in source
    assert "write_gff" not in source
    assert "write_bytes" not in source
    assert "setStyleSheet" not in source
    assert "QColor(" not in source
