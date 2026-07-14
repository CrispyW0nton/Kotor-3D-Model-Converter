from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Native-host test setup can prepend generated payload roots.  This focused
# test intentionally exercises the canonical sources before payload generation.
import src  # noqa: E402

root_src = str(ROOT / "src")
if root_src not in src.__path__:
    src.__path__.insert(0, root_src)
import src.gui  # noqa: E402

root_gui = str(ROOT / "src" / "gui")
if root_gui not in src.gui.__path__:
    src.gui.__path__.insert(0, root_gui)
import src.gui.controllers  # noqa: E402

root_controllers = str(ROOT / "src" / "gui" / "controllers")
if root_controllers not in src.gui.controllers.__path__:
    src.gui.controllers.__path__.insert(0, root_controllers)

from PySide6 import QtCore, QtWidgets  # noqa: E402

from src.core.scripting.data_authoring import TwoDADocument  # noqa: E402
from src.gui.controllers.scripting_data_controller import ScriptingDataController  # noqa: E402
from src.gui.windows.qt_scripting_data_pages import TwoDAGlobalsPage  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_twoda_page_emits_spreadsheet_copy_paste_duplicate_and_rename_intent() -> None:
    app = _app()
    page = TwoDAGlobalsPage()
    try:
        page.set_table(
            ("name", "value"),
            ("0", "1"),
            ({"name": "alpha", "value": "10"}, {"name": "beta", "value": "20"}),
        )
        selection = page.table.selectionModel()
        page.table.setCurrentIndex(page.proxy.index(0, 1))
        selection.select(
            page.proxy.index(0, 1),
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        selection.select(
            page.proxy.index(1, 2),
            QtCore.QItemSelectionModel.SelectionFlag.Select,
        )

        copied: list[str] = []
        pasted: list[tuple[tuple[int, str | None, str], ...]] = []
        duplicated: list[tuple[int, ...]] = []
        renamed: list[tuple[str, str]] = []
        page.copyTextRequested.connect(copied.append)
        page.pasteCellsRequested.connect(pasted.append)
        page.duplicateRowsRequested.connect(duplicated.append)
        page.renameColumnRequested.connect(lambda old, new: renamed.append((old, new)))

        page.copy_button.click()
        assert copied[-1] == "beta\t20\nalpha\t10"
        page._request_paste("gamma\t30\ndelta\t40")
        assert pasted[-1] == (
            (1, "name", "gamma"),
            (1, "value", "30"),
            (0, "name", "delta"),
            (0, "value", "40"),
        )
        page.duplicate_row_button.click()
        assert duplicated[-1] == (1, 0)

        page.remove_column_combo.setCurrentText("value")
        page.column_name_edit.setText("amount")
        page.rename_column_button.click()
        assert renamed[-1] == ("value", "amount")
        page.set_history_state(True, False)
        assert page.undo_button.isEnabled()
        assert not page.redo_button.isEnabled()
    finally:
        page.deleteLater()
        app.processEvents()


def test_twoda_controller_keeps_mode_specific_snapshot_history_and_globalcat_rules() -> None:
    app = _app()

    class Window(QtWidgets.QWidget):
        pass

    window = Window()
    window.twoda_globals_page = TwoDAGlobalsPage(window)
    controller = ScriptingDataController(window)
    changes: list[bool] = []
    controller.contentChanged.connect(lambda: changes.append(True))
    try:
        controller.table = TwoDADocument(
            ("name", "value"),
            ("0", "1"),
            (("alpha", "10"), ("beta", "20")),
        )
        controller._present_table()
        controller.duplicate_table_rows((0, 1))
        controller.rename_table_column("value", "amount")
        controller.paste_table_cells(((0, "amount", "99"), (1, "amount", "88")))
        assert controller.table.headers == ("name", "amount")
        assert controller.table.row_count == 4
        assert controller.table.cell(0, "amount") == "99"
        assert controller.undo_table()
        assert controller.table.cell(0, "amount") == "10"
        assert controller.redo_table()
        assert controller.table.cell(0, "amount") == "99"

        controller.set_table_mode("globals")
        controller.add_global("MYMOD_ENABLED", "Boolean")
        assert controller.globals is not None
        assert controller.globals.variables[0].name == "MYMOD_ENABLED"
        controller.edit_table_cell(0, "type", "string")
        assert controller.globals.variables[0].value_type == "String"
        assert controller.undo_table()
        assert controller.globals.variables[0].value_type == "Boolean"
        assert not window.twoda_globals_page.duplicate_row_button.isVisible()

        controller.set_table_mode("2da")
        assert controller.table.cell(0, "amount") == "99"
        assert window.twoda_globals_page.undo_button.isEnabled()
        controller.copy_table_text("alpha\t99")
        assert QtWidgets.QApplication.clipboard().text() == "alpha\t99"
        assert len(changes) >= 7
    finally:
        window.deleteLater()
        app.processEvents()
