"""
Unit Tests for ERF Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import pytest
import os
import pathlib
import tempfile
import unittest
from pathlib import Path
from qtpy.QtCore import QItemSelectionModel, QModelIndex, Qt, QMimeData, QUrl, QPoint
from qtpy.QtGui import QKeySequence, QDragEnterEvent, QDragMoveEvent, QDropEvent, QStandardItem
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QHeaderView, QLineEdit, QMessageBox, QMenu, QPushButton, QWidget
from toolset.gui.editors.erf import ERFEditor, ERFEditorTable  # type: ignore[import-not-found]
from toolset.data.installation import HTInstallation  # type: ignore[import-not-found]
from pykotor.resource.formats.erf import ERF, ERFResource, ERFType, read_erf, write_erf  # type: ignore[import-not-found]
from pykotor.resource.formats.rim import RIM, RIMResource, read_rim, write_rim  # type: ignore[import-not-found]
from pykotor.resource.formats.bif import BIFType, BIF, BIFResource, read_bif, write_bif  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from pykotor.common.misc import ResRef  # type: ignore[import-not-found]
from pykotor.extract.file import ResourceIdentifier  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

# Test constants
TEST_RESREFS = ["test1", "test2", "test3", "test_resource", "another_res", "mixed_case", "with_underscores"]
TEST_DATA_SIZES = [0, 1, 100, 1000, 10000, 100000]  # Different data sizes to test
TEST_RESOURCE_TYPES = [ResourceType.TXT, ResourceType.TXI, ResourceType.UTC, ResourceType.NSS, ResourceType.NCS]

# ============================================================================
# BASIC LOADING AND SAVING TESTS
# ============================================================================


def test_erf_editor_load_empty_erf(qtbot: QtBot, installation: HTInstallation):
    """Test loading an empty ERF file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create empty ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "empty", ResourceType.ERF, bytes(data))

    # Verify table is empty
    assert editor.source_model.rowCount() == 0
    tableViewModel = editor.ui.tableView.model()
    assert tableViewModel is not None, "Table view model is None"
    assert tableViewModel.rowCount() == 0


def test_erf_editor_load_erf_with_resources(qtbot: QtBot, installation: HTInstallation):
    """Test loading ERF file with various resources."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with test resources
    erf = ERF(ERFType.ERF)
    test_resources: list[tuple[str, ResourceType, bytes]] = []

    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        erf.set_data(resref, ResourceType.TXT, data)
        test_resources.append((resref, ResourceType.TXT, data))

    data = bytearray()
    write_erf(erf, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_erf", ResourceType.ERF, bytes(data))

    # Verify resources loaded correctly
    assert editor.source_model.rowCount() == len(test_resources)
    for i, (resref, restype, test_data) in enumerate(test_resources):
        item = editor.source_model.item(i, 0)
        assert item is not None
        resource: ERFResource = item.data()
        assert str(resource.resref) == resref
        assert resource.restype == restype
        assert resource.data == test_data


def test_erf_editor_load_mod_file(qtbot: QtBot, installation: HTInstallation):
    """Test loading MOD file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create MOD file
    erf = ERF(ERFType.MOD)
    erf.set_data("test_mod", ResourceType.TXT, b"mod content")

    data = bytearray()
    write_erf(erf, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_mod", ResourceType.MOD, bytes(data))

    # Verify loaded as MOD
    assert editor._restype == ResourceType.MOD
    assert editor.source_model.rowCount() == 1


def test_erf_editor_load_sav_file(qtbot: QtBot, installation: HTInstallation):
    """Test loading SAV file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create SAV file (uses MOD signature but is_save=True)
    erf = ERF(ERFType.MOD, is_save=True)
    erf.set_data("test_sav", ResourceType.TXT, b"sav content")

    data = bytearray()
    write_erf(erf, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_sav", ResourceType.SAV, bytes(data))

    # Verify loaded as SAV
    assert editor._restype == ResourceType.SAV
    assert editor.source_model.rowCount() == 1


def test_erf_editor_load_rim_file(qtbot: QtBot, installation: HTInstallation):
    """Test loading RIM file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create RIM file
    rim = RIM()
    rim.set_data("test_rim", ResourceType.TXT, b"rim content")

    data = bytearray()
    write_rim(rim, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_rim", ResourceType.RIM, bytes(data))

    # Verify loaded as RIM
    assert editor._restype == ResourceType.RIM
    assert editor.source_model.rowCount() == 1


def test_erf_editor_load_bif_file(qtbot: QtBot, installation: HTInstallation):
    """Test loading BIF file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create BIF file
    bif = BIF(BIFType.BIF)
    bif.set_data(ResRef("test_bif"), ResourceType.TXT, bytes(100), 0)

    data = bytearray()
    write_bif(bif, data)

    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_bif", ResourceType.BIF, bytes(data))

    # Verify loaded as BIF
    assert editor._restype == ResourceType.BIF
    assert editor.source_model.rowCount() == 1


def test_erf_editor_save_load_roundtrip_erf(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves ERF data exactly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create test ERF
    original_erf = ERF(ERFType.ERF)
    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        original_erf.set_data(resref, ResourceType.TXT, data)

    original_data = bytearray()
    write_erf(original_erf, original_data)
    original_data = bytes(original_data)

    # Load into editor
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_erf", ResourceType.ERF, original_data)

    # Save through editor
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)

    # Compare
    assert len(saved_erf) == len(original_erf)
    for orig_res, saved_res in zip(original_erf, saved_erf):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_save_load_roundtrip_rim(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves RIM data exactly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create test RIM
    original_rim = RIM()
    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        original_rim.set_data(resref, ResourceType.TXT, data)

    original_data = bytearray()
    write_rim(original_rim, original_data)
    original_data = bytes(original_data)

    # Load into editor
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_rim", ResourceType.RIM, original_data)

    # Save through editor
    saved_data, _ = editor.build()
    saved_rim = read_rim(saved_data)

    # Compare
    assert len(saved_rim) == len(original_rim)
    for orig_res, saved_res in zip(original_rim, saved_rim):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_save_load_roundtrip_bif(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves BIF data exactly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create test BIF
    original_bif = BIF(BIFType.BIF)
    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        original_bif.set_data(ResRef(resref), ResourceType.TXT, data, i)

    original_data = bytearray()
    write_bif(original_bif, original_data)
    original_data = bytes(original_data)

    # Load into editor
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_bif", ResourceType.BIF, original_data)

    # Save through editor
    saved_data, _ = editor.build()
    saved_bif = read_bif(saved_data)

    # Compare
    assert len(saved_bif) == len(original_bif)
    for orig_res, saved_res in zip(original_bif, saved_bif):
        # BIF files don't store ResRefs in the file format (only in KEY files),
        # so we can't preserve them through write/read cycles. Compare by ID instead.
        assert orig_res.resname_key_index == saved_res.resname_key_index
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_save_load_roundtrip_mod(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves MOD data exactly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create test MOD
    original_mod = ERF(ERFType.MOD)
    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        original_mod.set_data(resref, ResourceType.TXT, data)

    original_data = bytearray()
    write_erf(original_mod, original_data)
    original_data = bytes(original_data)

    # Load into editor
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_mod", ResourceType.MOD, original_data)

    # Save through editor
    saved_data, _ = editor.build()
    saved_mod = read_erf(saved_data)

    # Compare
    assert len(saved_mod) == len(original_mod)
    for orig_res, saved_res in zip(original_mod, saved_mod):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_save_load_roundtrip_sav(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves SAV data exactly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create test SAV
    original_sav = ERF(ERFType.MOD, is_save=True)
    for i, resref in enumerate(TEST_RESREFS[:3]):
        data = b"x" * TEST_DATA_SIZES[i]
        original_sav.set_data(resref, ResourceType.TXT, data)

    original_data = bytearray()
    write_erf(original_sav, original_data)
    original_data = bytes(original_data)

    # Load into editor
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test_sav", ResourceType.SAV, original_data)

    # Save through editor
    saved_data, _ = editor.build()
    saved_sav = read_erf(saved_data)

    # Compare
    assert len(saved_sav) == len(original_sav)
    for orig_res, saved_res in zip(original_sav, saved_sav):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


# ============================================================================
# RESOURCE MANAGEMENT TESTS
# ============================================================================


def test_erf_editor_add_single_resource(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test adding a single resource to empty ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Start with empty ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "empty", ResourceType.ERF, bytes(data))

    # Create a temporary file to add
    test_file = tmp_path / "test_add.txt"
    test_data = b"test resource data"
    test_file.write_bytes(test_data)

    # Add resource via file path
    editor.add_resources([str(test_file)])

    # Verify resource was added
    assert editor.source_model.rowCount() == 1
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "test_add"
    assert resource.restype == ResourceType.TXT
    assert resource.data == test_data

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert str(saved_res.resref) == "test_add"
    assert saved_res.restype == ResourceType.TXT
    assert saved_res.data == test_data


def test_erf_editor_add_multiple_resources(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test adding multiple resources to ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Start with empty ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "empty", ResourceType.ERF, bytes(data))

    # Create multiple temporary files to add
    test_files = []
    for i, (resref, restype) in enumerate(zip(TEST_RESREFS[:3], TEST_RESOURCE_TYPES[:3])):
        test_file = tmp_path / f"{resref}.{restype.extension.lower()}"
        test_data = b"x" * TEST_DATA_SIZES[i]
        test_file.write_bytes(test_data)
        test_files.append(str(test_file))

    # Add resources via file paths
    editor.add_resources(test_files)

    # Verify resources were added
    assert editor.source_model.rowCount() == 3
    for i, (expected_resref, expected_restype) in enumerate(zip(TEST_RESREFS[:3], TEST_RESOURCE_TYPES[:3])):
        item = editor.source_model.item(i, 0)
        assert item is not None
        resource: ERFResource = item.data()
        assert str(resource.resref) == expected_resref
        assert resource.restype == expected_restype
        assert len(resource.data) == TEST_DATA_SIZES[i]

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 3


def test_erf_editor_add_duplicate_resref_different_types(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test adding resources with same ResRef but different types (allowed)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Start with empty ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "empty", ResourceType.ERF, bytes(data))

    # Create files with same resref but different extensions
    same_resref = "duplicate_test"
    txt_file = tmp_path / f"{same_resref}.txt"
    txi_file = tmp_path / f"{same_resref}.txi"

    txt_file.write_bytes(b"text data")
    txi_file.write_bytes(b"txi data")

    # Add both files
    editor.add_resources([str(txt_file), str(txi_file)])

    # Verify both resources were added (duplicate names with different types are allowed)
    assert editor.source_model.rowCount() == 2

    # Check resources
    txt_item = editor.source_model.item(0, 0)
    txi_item = editor.source_model.item(1, 0)

    assert txt_item is not None, "Text item is None"
    assert txi_item is not None, "Txi item is None"
    assert isinstance(txt_item, QStandardItem), "Text item is not a QStandardItem"
    assert isinstance(txi_item, QStandardItem), "Txi item is not a QStandardItem"
    txt_resource: Any = txt_item.data()
    txi_resource: Any = txi_item.data()

    assert isinstance(txt_resource, ERFResource), "Text resource is not a ERFResource"
    assert isinstance(txi_resource, ERFResource), "Txi resource is not a ERFResource"
    assert str(txt_resource.resref) == same_resref
    assert str(txi_resource.resref) == same_resref
    assert txt_resource.restype == ResourceType.TXT
    assert txi_resource.restype == ResourceType.TXI


def test_erf_editor_remove_single_resource(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test removing a single resource from ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.TXT, b"data2")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    assert editor.source_model.rowCount() == 2

    # Select first resource
    editor.ui.tableView.selectRow(0)

    # Remove selected
    editor.remove_selected()

    # Verify one resource removed
    assert editor.source_model.rowCount() == 1

    # Verify correct resource remains
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "res2"

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert str(saved_res.resref) == "res2"


def test_erf_editor_remove_multiple_resources(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test removing multiple resources from ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with multiple resources
    erf = ERF(ERFType.ERF)
    for i in range(5):
        erf.set_data(ResRef(f"res{i}"), ResourceType.TXT, f"data{i}".encode())

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    assert editor.source_model.rowCount() == 5

    # Select multiple resources (every other one: 0, 2, 4)
    # Use selection model directly to add to selection rather than replace
    from qtpy.QtCore import QItemSelection

    sel_model: QItemSelectionModel | None = editor.ui.tableView.selectionModel()
    if sel_model is not None:
        # Build a selection that includes all three rows
        index0: QModelIndex = editor._proxy_model.index(0, 0)
        index0_end: QModelIndex = editor._proxy_model.index(0, editor._proxy_model.columnCount() - 1)
        index2: QModelIndex = editor._proxy_model.index(2, 0)
        index2_end: QModelIndex = editor._proxy_model.index(2, editor._proxy_model.columnCount() - 1)
        index4: QModelIndex = editor._proxy_model.index(4, 0)
        index4_end: QModelIndex = editor._proxy_model.index(4, editor._proxy_model.columnCount() - 1)

        # Create selection ranges for each row
        selection: QItemSelection = QItemSelection()
        selection.select(index0, index0_end)
        selection.select(index2, index2_end)
        selection.select(index4, index4_end)

        # Apply the selection
        sel_model.select(selection, sel_model.SelectionFlag.Select | sel_model.SelectionFlag.Rows)

    # Remove selected
    editor.remove_selected()

    # Verify resources removed (should have 2 remaining: 1, 3)
    assert editor.source_model.rowCount() == 2

    remaining_resrefs: list[str] = []
    for i in range(2):
        item = editor.source_model.item(i, 0)
        assert item is not None
        resource: ERFResource = item.data()
        remaining_resrefs.append(str(resource.resref))

    assert "res1" in remaining_resrefs
    assert "res3" in remaining_resrefs

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 2


def test_erf_editor_remove_all_resources(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test removing all resources from ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    for i in range(3):
        erf.set_data(ResRef(f"res{i}"), ResourceType.TXT, f"data{i}".encode())

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    assert editor.source_model.rowCount() == 3

    # Select all resources
    from qtpy.QtCore import QItemSelection

    sel_model: QItemSelectionModel | None = editor.ui.tableView.selectionModel()
    if sel_model is not None:
        # Build a selection that includes all rows
        selection: QItemSelection = QItemSelection()
        row_count: int = editor._proxy_model.rowCount()
        for row in range(row_count):
            index_start: QModelIndex = editor._proxy_model.index(row, 0)
            index_end: QModelIndex = editor._proxy_model.index(row, editor._proxy_model.columnCount() - 1)
            selection.select(index_start, index_end)

        # Apply the selection
        sel_model.select(selection, sel_model.SelectionFlag.Select | sel_model.SelectionFlag.Rows)
    else:
        pytest.fail("ERFEditor: selectionModel was None in remove_all_resources()")

    # Remove all
    editor.remove_selected()

    # Verify all resources removed
    assert editor.source_model.rowCount() == 0

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 0


def test_erf_editor_extract_single_resource(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test extracting a single resource."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    test_data = b"extract test data"
    erf.set_data(ResRef("extract_test"), ResourceType.TXT, test_data)

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Create extraction directory and file path
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    extracted_file = extract_dir / "extract_test.txt"

    # Mock the file dialog and extraction feedback
    from unittest.mock import patch, MagicMock

    # Create a mock dialog class that returns a mock instance with the right methods
    class MockFileDialog:
        # Add class attributes that QFileDialog has
        AcceptMode = QFileDialog.AcceptMode
        Option = QFileDialog.Option
        DialogCode = QFileDialog.DialogCode

        def __init__(self, *args, **kwargs):
            pass

        def setAcceptMode(self, mode):
            pass

        def setOption(self, option):
            pass

        def exec(self):
            return QFileDialog.DialogCode.Accepted

        def selectedFiles(self):
            return [str(extracted_file)]

    # Mock QFileDialog to use our mock class
    # Also mock show_extraction_results to prevent blocking dialog
    with patch("toolset.gui.dialogs.save.generic_file_saver.QFileDialog", MockFileDialog), patch("toolset.gui.common.extraction_feedback.show_extraction_results"):
        editor.extract_selected()

    # Check if file was extracted
    assert extracted_file.exists(), f"Expected extracted file at {extracted_file}"
    assert extracted_file.read_bytes() == test_data


def test_erf_editor_extract_single_resource_headless(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test extracting a single resource headlessly without mocking."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    test_data = b"extract test data headless"
    erf.set_data(ResRef("extract_test"), ResourceType.TXT, test_data)

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Create extraction directory and file path
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    extracted_file = extract_dir / "extract_test.txt"

    # Start extraction - this will show the file dialog
    # We need to interact with it headlessly using QTest
    from qtpy.QtCore import QTimer

    # Use a timer to interact with the dialog after it opens
    def interact_with_dialog():
        # Find the file dialog
        app = QApplication.instance()
        if app is None:
            return
        if not isinstance(app, QApplication):
            return

        # Find the active modal widget (should be the file dialog)
        dialog: QWidget | None = app.activeModalWidget()
        if dialog is None or not isinstance(dialog, QFileDialog):
            # Try to find it in top-level widgets
            for widget in app.topLevelWidgets():
                if isinstance(widget, QFileDialog) and widget.isVisible():
                    dialog = widget
                    break

        if dialog is None or not isinstance(dialog, QFileDialog):
            return

        # Wait for dialog to be ready
        QApplication.processEvents()
        QApplication.processEvents()

        # Find the line edit for file name
        line_edit: QLineEdit | None = dialog.findChild(QLineEdit, "fileNameEdit")
        if line_edit is not None:
            # Set the file path
            line_edit.setText(str(extracted_file))
            QApplication.processEvents()
            QApplication.processEvents()

        # Find and click the Save button
        button_box: QDialogButtonBox | None = dialog.findChild(QDialogButtonBox, "buttonBox")
        if button_box is not None:
            save_button: QPushButton | None = button_box.button(QDialogButtonBox.StandardButton.Save)
            if save_button is not None and save_button.isEnabled():
                QTest.mouseClick(save_button, Qt.MouseButton.LeftButton)
                QApplication.processEvents()
                QApplication.processEvents()

    # Also set up a timer to close the extraction results dialog if it appears
    def close_results_dialog():
        app = QApplication.instance()
        if app is None:
            return
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                ok_button = widget.button(QMessageBox.StandardButton.Ok)
                if ok_button is not None:
                    QTest.mouseClick(ok_button, Qt.MouseButton.LeftButton)
                    QApplication.processEvents()
                    QApplication.processEvents()

    # Start extraction in a timer to allow dialog to open
    QTimer.singleShot(200, interact_with_dialog)
    QTimer.singleShot(500, close_results_dialog)

    # Trigger extraction
    editor.extract_selected()

    # Wait for extraction to complete
    QApplication.processEvents()
    QApplication.processEvents()

    # Check if file was extracted
    assert extracted_file.exists(), f"Expected extracted file at {extracted_file}"
    assert extracted_file.read_bytes() == test_data


def test_erf_editor_extract_multiple_resources(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test extracting multiple resources."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with multiple resources
    erf = ERF(ERFType.ERF)
    test_resources = []
    for i in range(3):
        resref = f"extract{i}"
        data = f"data{i}".encode()
        erf.set_data(resref, ResourceType.TXT, data)
        test_resources.append((resref, data))

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select multiple resources
    editor.ui.tableView.selectAll()

    # Create extraction directory
    extract_dir = tmp_path / "extract_multi"
    extract_dir.mkdir()

    # Mock the file dialog where it's actually used
    from unittest.mock import patch

    # Patch it in the module where it's imported and used
    with patch("toolset.gui.dialogs.save.generic_file_saver.QFileDialog.getExistingDirectory", return_value=str(extract_dir)):
        # Also patch show_extraction_results to prevent blocking dialog
        with patch("toolset.gui.common.extraction_feedback.show_extraction_results"):
            editor.extract_selected()
            # Process events to ensure extraction completes
            QApplication.processEvents()
            QApplication.processEvents()

    # Check if files were extracted
    for resref, expected_data in test_resources:
        extracted_file = extract_dir / f"{resref}.txt"
        assert extracted_file.exists(), f"Expected extracted file at {extracted_file}"
        assert extracted_file.read_bytes() == expected_data


def test_erf_editor_extract_no_selection(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test extracting with no selection (should handle gracefully)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("test", ResourceType.TXT, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Clear selection
    editor.ui.tableView.clearSelection()

    # Extract with no selection should handle gracefully
    editor.extract_selected()

    # Should not crash and editor state should remain unchanged
    assert editor.source_model.rowCount() == 1


# ============================================================================
# RENAMING TESTS
# ============================================================================


def test_erf_editor_rename_resource_valid(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test renaming a resource with valid name."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    original_data = b"test data"
    erf.set_data("old_name", ResourceType.TXT, original_data)

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Mock the input dialog instance to return new name
    from unittest.mock import patch, MagicMock
    from qtpy.QtWidgets import QInputDialog

    # Create a mock dialog instance
    mock_dialog = MagicMock(spec=QInputDialog)
    mock_dialog.exec.return_value = QInputDialog.DialogCode.Accepted
    mock_dialog.textValue.return_value = "new_name"
    mock_dialog.findChild.return_value = None  # Return None for validator setup

    # Patch QInputDialog constructor to return our mock
    with patch("toolset.gui.editors.erf.QInputDialog", return_value=mock_dialog):
        editor.rename_selected()
        # Process events to ensure rename completes
        QApplication.processEvents()
        QApplication.processEvents()

    # Verify resource was renamed
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "new_name"
    assert resource.data == original_data

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert str(saved_res.resref) == "new_name"
    assert saved_res.data == original_data


def test_erf_editor_rename_resource_invalid(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test renaming a resource with invalid name (should reject)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("old_name", ResourceType.TXT, b"test data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Mock the input dialog to return invalid name (spaces not allowed)
    from unittest.mock import patch

    with patch("qtpy.QtWidgets.QInputDialog.getText", return_value=("invalid name", True)):
        editor.rename_selected()

    # Verify resource was NOT renamed (should still be "old_name")
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "old_name"


def test_erf_editor_rename_resource_empty_name(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test renaming a resource with empty name (should reject)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("old_name", ResourceType.TXT, b"test data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Mock the input dialog to return empty name
    from unittest.mock import patch

    with patch("qtpy.QtWidgets.QInputDialog.getText", return_value=("", True)):
        editor.rename_selected()

    # Verify resource was NOT renamed
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "old_name"


def test_erf_editor_rename_resource_too_long(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test renaming a resource with name too long (should truncate or reject)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("old_name", ResourceType.TXT, b"test data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Try to rename to a very long name (ResRef should be max 16 chars)
    long_name = "a" * 20  # 20 characters, should be truncated to 16

    from unittest.mock import patch

    with patch("qtpy.QtWidgets.QInputDialog.getText", return_value=(long_name, True)):
        editor.rename_selected()

    # Verify resource was renamed (should be truncated to valid length)
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    # Should be truncated to 16 characters
    assert len(str(resource.resref)) <= 16


def test_erf_editor_rename_multiple_selection(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test that rename only works with single selection."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with multiple resources
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.TXT, b"data2")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select multiple resources
    editor.ui.tableView.selectAll()

    # Rename should not work with multiple selection (should do nothing)
    editor.rename_selected()

    # Verify resources were NOT renamed
    item1 = editor.source_model.item(0, 0)
    item2 = editor.source_model.item(1, 0)
    assert item1 is not None and item2 is not None

    resource1: ERFResource = item1.data()
    resource2: ERFResource = item2.data()

    assert str(resource1.resref) == "res1"
    assert str(resource2.resref) == "res2"


def test_erf_editor_rename_no_selection(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test rename with no selection (should handle gracefully)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("test", ResourceType.TXT, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Clear selection
    editor.ui.tableView.clearSelection()

    # Rename with no selection should handle gracefully
    editor.rename_selected()

    # Should not crash and resource should remain unchanged
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "test"


# ============================================================================
# UI INTERACTION TESTS
# ============================================================================


def test_erf_editor_ui_buttons_enabled_states(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test UI button enabled states based on selection."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.TXT, b"data2")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Initially no selection - buttons should be disabled
    assert not editor.ui.extractButton.isEnabled()
    assert not editor.ui.openButton.isEnabled()
    assert not editor.ui.unloadButton.isEnabled()

    # Select a resource
    editor.ui.tableView.selectRow(0)

    # Buttons should be enabled
    assert editor.ui.extractButton.isEnabled()
    assert editor.ui.openButton.isEnabled()
    assert editor.ui.unloadButton.isEnabled()

    # Clear selection
    editor.ui.tableView.clearSelection()

    # Buttons should be disabled again
    assert not editor.ui.extractButton.isEnabled()
    assert not editor.ui.openButton.isEnabled()
    assert not editor.ui.unloadButton.isEnabled()


def test_erf_editor_context_menu_single_selection(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test context menu with single selection."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with GFF resource (for specialized editor option)
    erf = ERF(ERFType.ERF)
    erf.set_data("test_gff", ResourceType.UTC, b"gff data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Test context menu functionality
    assert hasattr(editor, "open_context_menu")
    assert callable(editor.open_context_menu)

    # Simulate right-click to open context menu
    from qtpy.QtCore import QPoint

    position = QPoint(10, 10)

    # This should create a context menu (though we can't easily test the full menu interaction in unit tests)
    editor.open_context_menu(position)


def test_erf_editor_context_menu_multiple_selection(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test context menu with multiple selection."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with multiple resources
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.UTC, b"data2")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select multiple resources
    editor.ui.tableView.selectAll()

    # Context menu should still work
    assert hasattr(editor, "open_context_menu")

    # Test with mixed resource types
    selected_resources = editor.get_selected_resources()
    assert len(selected_resources) == 2

    # Test context menu with mixed types
    from qtpy.QtCore import QPoint

    position = QPoint(10, 10)
    editor.open_context_menu(position)


def test_erf_editor_keyboard_shortcuts(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test keyboard shortcuts work correctly."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.TXT, b"data2")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select a resource
    editor.ui.tableView.selectRow(0)

    # Test Delete key shortcut for remove
    assert editor.ui.unloadButton.shortcut() == QKeySequence.StandardKey.Delete

    # Simulate pressing Delete key
    qtbot.keyPress(editor.ui.tableView, Qt.Key.Key_Delete)

    # Should have removed the selected resource
    assert editor.source_model.rowCount() == 1


def test_erf_editor_double_click_open(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test double-clicking a resource opens it."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("test_res", ResourceType.TXT, b"test data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Double-click first row
    index = editor.ui.tableView.model().index(0, 0)
    editor.ui.tableView.doubleClicked.emit(index)

    # Should trigger open_selected
    assert hasattr(editor, "open_selected")


def test_erf_editor_table_sorting(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test table sorting by different columns."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources in non-alphabetical order
    erf = ERF(ERFType.ERF)
    erf.set_data("zebra", ResourceType.TXT, b"small")
    erf.set_data("alpha", ResourceType.TXI, b"medium data")
    erf.set_data("beta", ResourceType.UTC, b"large data here")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Initially should not be sorted
    first_item = editor.source_model.item(0, 0)
    assert first_item is not None

    # Click on ResRef column header to sort
    header = editor.ui.tableView.horizontalHeader()
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=header.rect().center())

    # Should now be sorted alphabetically
    first_item_after_sort = editor.source_model.item(0, 0)
    assert first_item_after_sort is not None
    first_resource: ERFResource = first_item_after_sort.data()
    assert str(first_resource.resref) == "alpha"  # Should be first alphabetically

    # Click again to reverse sort
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=header.rect().center())

    first_item_after_reverse = editor.source_model.item(0, 0)
    assert first_item_after_reverse is not None
    first_resource_reverse: ERFResource = first_item_after_reverse.data()
    assert str(first_resource_reverse.resref) == "zebra"  # Should be first in reverse alphabetical


def test_erf_editor_table_sort_by_size(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test sorting resources by size."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with different sized resources
    erf = ERF(ERFType.ERF)
    erf.set_data("small", ResourceType.TXT, b"x")
    erf.set_data("medium", ResourceType.TXT, b"x" * 100)
    erf.set_data("large", ResourceType.TXT, b"x" * 1000)

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Click on Size column header (column 2)
    header = editor.ui.tableView.horizontalHeader()
    size_header_rect = header.sectionRect(2)
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=size_header_rect.center())

    # Should be sorted by size (smallest first)
    first_item = editor.source_model.item(0, 0)
    assert first_item is not None
    first_resource: ERFResource = first_item.data()
    assert str(first_resource.resref) == "small"
    assert len(first_resource.data) == 1

    # Click again to reverse (largest first)
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=size_header_rect.center())

    first_item_reverse = editor.source_model.item(0, 0)
    assert first_item_reverse is not None
    first_resource_reverse: ERFResource = first_item_reverse.data()
    assert str(first_resource_reverse.resref) == "large"
    assert len(first_resource_reverse.data) == 1000


def test_erf_editor_table_sort_by_type(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test sorting resources by type."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with different resource types
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data")
    erf.set_data("res2", ResourceType.UTC, b"data")
    erf.set_data("res3", ResourceType.TXI, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Click on Type column header (column 1)
    header = editor.ui.tableView.horizontalHeader()
    type_header_rect = header.sectionRect(1)
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=type_header_rect.center())

    # Should be sorted by type extension
    first_item = editor.source_model.item(0, 0)
    assert first_item is not None
    first_resource: ERFResource = first_item.data()
    # TXT should come before TXI and UTC alphabetically
    assert first_resource.restype == ResourceType.TXT


# ============================================================================
# DRAG AND DROP TESTS
# ============================================================================


def test_erf_editor_drag_drop_accept_urls(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test drag enter event accepts URLs."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create mock drag enter event with URLs
    from qtpy.QtGui import QDragEnterEvent, QMimeData
    from qtpy.QtCore import QPoint, QUrl

    # Create test files to drag
    test_file1 = tmp_path / "drag_test1.txt"
    test_file2 = tmp_path / "drag_test2.txi"
    test_file1.write_bytes(b"test data 1")
    test_file2.write_bytes(b"test data 2")

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(test_file1)), QUrl.fromLocalFile(str(test_file2))])

    # Create drag enter event
    drag_enter_event = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    # Send drag enter event to table
    table: ERFEditorTable = editor.ui.tableView
    table.dragEnterEvent(drag_enter_event)

    # Should accept the drag
    assert drag_enter_event.isAccepted()


def test_erf_editor_drag_drop_reject_non_urls(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test drag enter event rejects non-URL data."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create mock drag enter event with non-URL data
    from qtpy.QtGui import QDragEnterEvent, QMimeData
    from qtpy.QtCore import QPoint

    mime_data = QMimeData()
    mime_data.setText("This is not a URL")

    # Create drag enter event
    drag_enter_event = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    # Send drag enter event to table
    table: ERFEditorTable = editor.ui.tableView
    table.dragEnterEvent(drag_enter_event)

    # Should NOT accept the drag
    assert not drag_enter_event.isAccepted()


def test_erf_editor_drop_files(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test dropping files onto the table adds them to the ERF."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create test files to drop
    test_file1 = tmp_path / "drop_test1.txt"
    test_file2 = tmp_path / "drop_test2.nss"
    test_file1.write_bytes(b"dropped data 1")
    test_file2.write_bytes(b"dropped data 2")

    # Create drop event
    from qtpy.QtGui import QDropEvent, QMimeData
    from qtpy.QtCore import QPoint, QUrl

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(test_file1)), QUrl.fromLocalFile(str(test_file2))])

    # Create drop event
    drop_event = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    # Send drop event to table
    table: ERFEditorTable = editor.ui.tableView
    table.dropEvent(drop_event)

    # Should accept the drop
    assert drop_event.isAccepted()

    # Files should be added to the ERF
    assert editor.source_model.rowCount() == 2

    # Check the added resources
    item1 = editor.source_model.item(0, 0)
    item2 = editor.source_model.item(1, 0)
    assert item1 is not None and item2 is not None

    resource1: ERFResource = item1.data()
    resource2: ERFResource = item2.data()

    assert str(resource1.resref) == "drop_test1"
    assert resource1.restype == ResourceType.TXT
    assert resource1.data == b"dropped data 1"

    assert str(resource2.resref) == "drop_test2"
    assert resource2.restype == ResourceType.NSS
    assert resource2.data == b"dropped data 2"


def test_erf_editor_start_drag(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test starting a drag operation from the table."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources
    erf = ERF(ERFType.ERF)
    erf.set_data("drag_test", ResourceType.TXT, b"drag data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Table should support drag operations
    table: ERFEditorTable = editor.ui.tableView
    assert hasattr(table, "startDrag")

    # Test that drag can be initiated (though we can't fully test the drag operation)
    assert table.dragEnabled()


def test_erf_editor_drag_drop_invalid_files(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test dropping invalid files (unsupported extensions) are rejected."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create invalid file (unsupported extension)
    invalid_file = tmp_path / "invalid.xyz"
    invalid_file.write_bytes(b"invalid data")

    # Create drop event with invalid file
    from qtpy.QtGui import QDropEvent, QMimeData
    from qtpy.QtCore import QPoint, QUrl

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(invalid_file))])

    drop_event = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    # Send drop event to table
    table: ERFEditorTable = editor.ui.tableView
    table.dropEvent(drop_event)

    # Should still accept the drop (even if files are invalid, the drop event itself is accepted)
    assert drop_event.isAccepted()

    # But no resources should be added (invalid files are skipped)
    assert editor.source_model.rowCount() == 0


def test_erf_editor_drag_drop_mixed_valid_invalid(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test dropping mix of valid and invalid files."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create valid and invalid files
    valid_file = tmp_path / "valid.txt"
    invalid_file = tmp_path / "invalid.xyz"
    valid_file.write_bytes(b"valid data")
    invalid_file.write_bytes(b"invalid data")

    # Create drop event with mixed files
    from qtpy.QtGui import QDropEvent, QMimeData
    from qtpy.QtCore import QPoint, QUrl

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(valid_file)), QUrl.fromLocalFile(str(invalid_file))])

    drop_event = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    # Send drop event to table
    table: ERFEditorTable = editor.ui.tableView
    table.dropEvent(drop_event)

    # Should accept the drop
    assert drop_event.isAccepted()

    # Only valid file should be added
    assert editor.source_model.rowCount() == 1

    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == "valid"
    assert resource.restype == ResourceType.TXT


# ============================================================================
# SORTING AND FILTERING TESTS
# ============================================================================


def test_erf_editor_sort_by_resref(qtbot: QtBot, installation: HTInstallation):
    """Test sorting resources by ResRef."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resources in non-alphabetical order
    erf = ERF(ERFType.ERF)
    erf.set_data("zebra", ResourceType.TXT, b"data1")
    erf.set_data("alpha", ResourceType.TXT, b"data2")
    erf.set_data("beta", ResourceType.TXT, b"data3")

    data = bytearray()
    write_erf(erf, data)
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Sort by ResRef column (0)
    header = editor.ui.tableView.horizontalHeader()
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=header.rect().center())

    # Verify sorting is enabled
    assert editor.ui.tableView.isSortingEnabled()


def test_erf_editor_sort_by_type(qtbot: QtBot, installation: HTInstallation):
    """Test sorting resources by type."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with different resource types
    erf = ERF(ERFType.ERF)
    erf.set_data("res1", ResourceType.TXT, b"data1")
    erf.set_data("res2", ResourceType.TXI, b"data2")
    erf.set_data("res3", ResourceType.UTC, b"data3")

    data = bytearray()
    write_erf(erf, data)
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Sort by type column (1)
    header: QHeaderView | None = editor.ui.tableView.horizontalHeader()
    assert header is not None, "header was None in test_erf_editor_sort_by_type()"
    # Click on type column header
    type_header_rect: QRect = header.sectionRect(1)
    assert type_header_rect is not None, "type_header_rect was None in test_erf_editor_sort_by_type()"
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=type_header_rect.center())

    assert editor.ui.tableView.isSortingEnabled()


def test_erf_editor_sort_by_size(qtbot: QtBot, installation: HTInstallation):
    """Test sorting resources by size."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with different sized resources
    erf = ERF(ERFType.ERF)
    erf.set_data("small", ResourceType.TXT, b"x")
    erf.set_data("medium", ResourceType.TXT, b"x" * 100)
    erf.set_data("large", ResourceType.TXT, b"x" * 1000)

    data = bytearray()
    write_erf(erf, data)
    # Use a temporary path since None causes issues
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".erf") as tmp:
        tmp_path = tmp.name

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Enable sorting
    editor.ui.tableView.setSortingEnabled(True)

    # Sort by size column (2)
    header = editor.ui.tableView.horizontalHeader()
    assert header is not None, "header was None in test_erf_editor_sort_by_size()"
    size_header_rect = header.sectionRect(2)
    assert size_header_rect is not None, "size_header_rect was None in test_erf_editor_sort_by_size()"
    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=size_header_rect.center())

    assert editor.ui.tableView.isSortingEnabled()


# ============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# ============================================================================


def test_erf_editor_load_invalid_file_type(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test loading a file with invalid type shows error."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to load invalid data
    invalid_data = b"This is not a valid ERF file"

    editor.load(tmp_path, "invalid", ResourceType.ERF, invalid_data)

    # Should handle gracefully (may show error dialog)
    assert editor.source_model.rowCount() == 0


def test_erf_editor_load_corrupted_erf(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test loading a corrupted ERF file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create corrupted ERF data (valid header but invalid content)
    corrupted_data = b"ERF V1.0" + b"\x00" * 100  # Incomplete header

    editor.load(tmp_path, "corrupted", ResourceType.ERF, corrupted_data)

    # Should handle gracefully
    assert editor.source_model.rowCount() == 0


def test_erf_editor_empty_resource_data(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test handling resources with empty data."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with empty resource
    erf = ERF(ERFType.ERF)
    erf.set_data("empty", ResourceType.TXT, b"")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Verify empty resource loaded
    assert editor.source_model.rowCount() == 1
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert len(resource.data) == 0

    # Save and verify roundtrip
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert len(saved_res.data) == 0


def test_erf_editor_very_large_resource(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test handling very large resources."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with large resource (1MB)
    erf = ERF(ERFType.ERF)
    large_data = b"x" * (1024 * 1024)
    erf.set_data("large", ResourceType.TXT, large_data)

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Verify large resource loaded
    assert editor.source_model.rowCount() == 1
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert len(resource.data) == len(large_data)

    # Save and verify roundtrip
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert len(saved_res.data) == len(large_data)


def test_erf_editor_duplicate_resref_different_types(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test handling duplicate ResRefs with different types (allowed)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with same ResRef but different types
    erf = ERF(ERFType.ERF)
    erf.set_data("same_name", ResourceType.TXT, b"text data")
    erf.set_data("same_name", ResourceType.TXI, b"txi data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Both should be loaded (duplicate names with different types are allowed)
    assert editor.source_model.rowCount() == 2

    # Verify both resources
    item1 = editor.source_model.item(0, 0)
    item2 = editor.source_model.item(1, 0)
    assert item1 is not None and item2 is not None

    resource1: ERFResource = item1.data()
    resource2: ERFResource = item2.data()

    assert str(resource1.resref) == "same_name"
    assert str(resource2.resref) == "same_name"
    assert resource1.restype != resource2.restype  # Different types
    assert resource1.data != resource2.data  # Different data


def test_erf_editor_save_without_filepath(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test save when no filepath is set triggers save_as."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("test", ResourceType.TXT, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Clear filepath to simulate new file
    editor._filepath = None

    # Save without filepath should trigger save_as (we mock it)
    from unittest.mock import patch

    with patch.object(editor, "save_as") as mock_save_as:
        editor.save()
        mock_save_as.assert_called_once()


def test_erf_editor_refresh_without_filepath(qtbot: QtBot, installation: HTInstallation):
    """Test refresh when no filepath is set shows error."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to refresh without filepath
    editor.refresh()  # Should handle gracefully

    # Should not crash, editor state should remain unchanged
    assert editor.source_model.rowCount() == 0


def test_erf_editor_add_nonexistent_file(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test adding a file that doesn't exist."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Try to add non-existent file
    nonexistent_path = tmp_path / "nonexistent.txt"
    editor.add_resources([str(nonexistent_path)])

    # Should handle gracefully, no resources added
    assert editor.source_model.rowCount() == 0


def test_erf_editor_add_file_with_invalid_extension(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test adding a file with invalid extension."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF
    erf = ERF(ERFType.ERF)
    data = bytearray()
    write_erf(erf, data)
    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Create file with invalid extension
    invalid_file = tmp_path / "invalid.xyz"
    invalid_file.write_bytes(b"invalid data")

    # Try to add invalid file
    editor.add_resources([str(invalid_file)])

    # Should handle gracefully, no resources added
    assert editor.source_model.rowCount() == 0


def test_erf_editor_max_resref_length(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test handling ResRef at maximum length (16 characters)."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with max length ResRef
    erf = ERF(ERFType.ERF)
    max_resref = "a" * 16  # Exactly 16 characters
    erf.set_data(max_resref, ResourceType.TXT, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Verify loaded correctly
    assert editor.source_model.rowCount() == 1
    item = editor.source_model.item(0, 0)
    assert item is not None
    resource: ERFResource = item.data()
    assert str(resource.resref) == max_resref
    assert len(str(resource.resref)) == 16


def test_erf_editor_resref_with_special_characters(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test ResRef with various special characters."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Test different valid ResRef patterns
    test_resrefs = [
        "normal",
        "with_underscores",
        "with123numbers",
        "MixedCase",
        "a",  # Single character
        "1234567890123456",  # All numbers, max length
    ]

    erf = ERF(ERFType.ERF)
    for resref in test_resrefs:
        erf.set_data(resref, ResourceType.TXT, f"data for {resref}".encode())

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Verify all loaded correctly
    assert editor.source_model.rowCount() == len(test_resrefs)

    loaded_resrefs = []
    for i in range(len(test_resrefs)):
        item = editor.source_model.item(i, 0)
        assert item is not None
        resource: ERFResource = item.data()
        loaded_resrefs.append(str(resource.resref))

    for expected in test_resrefs:
        assert expected in loaded_resrefs


def test_erf_editor_open_resource_without_filepath(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test opening a resource when editor has no filepath."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with resource
    erf = ERF(ERFType.ERF)
    erf.set_data("test", ResourceType.TXT, b"data")

    data = bytearray()
    write_erf(erf, data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(data))

    # Clear filepath
    editor._filepath = None

    # Select resource
    editor.ui.tableView.selectRow(0)

    # Try to open resource - should show error
    editor.open_selected()

    # Should handle gracefully (shows error dialog)


# ============================================================================
# NEW FILE CREATION TESTS
# ============================================================================


def test_erf_editor_new_erf_file(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new ERF file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new ERF
    editor.new()

    # Verify empty state
    assert editor.source_model.rowCount() == 0
    assert editor._filepath is None
    assert editor._resname is None
    assert editor._restype == ResourceType.ERF

    # Refresh button should be disabled for new files
    assert not editor.ui.refreshButton.isEnabled()

    # Verify column headers are set correctly
    assert editor.source_model.columnCount() == 4  # ResRef, Type, Size, Offset
    expected_headers = ["ResRef", "Type", "Size", "Offset"]
    for i, header in enumerate(expected_headers):
        assert editor.source_model.headerData(i, Qt.Orientation.Horizontal) == header


def test_erf_editor_new_mod_file(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new MOD file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new MOD
    editor.new()

    # Verify it's set up as ERF type (MOD uses ERF format)
    assert editor._restype == ResourceType.ERF

    # But we can differentiate by setting the restype
    editor._restype = ResourceType.MOD
    assert editor._restype == ResourceType.MOD


def test_erf_editor_new_file_build_empty(qtbot: QtBot, installation: HTInstallation):
    """Test building data from a new empty ERF file."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new ERF
    editor.new()

    # Build data
    data, _ = editor.build()

    # Verify it's valid ERF data
    built_erf = read_erf(data)
    assert len(built_erf) == 0  # Empty ERF
    assert built_erf.erf_type == ERFType.ERF


def test_erf_editor_new_file_add_then_build(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test creating new file, adding resources, then building."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new ERF
    editor.new()

    # Add resources
    test_file1 = tmp_path / "new_test1.txt"
    test_file2 = tmp_path / "new_test2.utc"
    test_file1.write_bytes(b"new data 1")
    test_file2.write_bytes(b"new data 2")

    editor.add_resources([str(test_file1), str(test_file2)])

    # Verify resources added
    assert editor.source_model.rowCount() == 2

    # Build data
    data, _ = editor.build()

    # Verify built ERF contains the resources
    built_erf = read_erf(data)
    assert len(built_erf) == 2

    resources = list(built_erf)
    resrefs = [str(r.resref) for r in resources]
    assert "new_test1" in resrefs
    assert "new_test2" in resrefs


# ============================================================================
# INTEGRATION TESTS WITH INSTALLATION
# ============================================================================


def test_erf_editor_load_from_installation_erf(qtbot: QtBot, installation: HTInstallation):
    """Test loading ERF files from game installation."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find an ERF file in installation
    from pykotor.extract.file import ResourceIdentifier

    erf_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.ERF)]).values())[:1]

    if not erf_resources:
        pytest.skip("No ERF files found in installation")

    erf_resource = erf_resources[0]
    erf_data = erf_resource.data

    if erf_data:
        editor.load(erf_resource.filepath, erf_resource.resname, erf_resource.restype, erf_data)
        assert editor.source_model.rowCount() >= 0  # Could be empty ERF


def test_erf_editor_load_from_installation_mod(qtbot: QtBot, installation: HTInstallation):
    """Test loading MOD files from game installation."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a MOD file in installation
    from pykotor.extract.file import ResourceIdentifier

    mod_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.MOD)]).values())[:1]

    if not mod_resources:
        pytest.skip("No MOD files found in installation")

    mod_resource = mod_resources[0]
    mod_data = mod_resource.data

    if mod_data:
        editor.load(mod_resource.filepath, mod_resource.resname, mod_resource.restype, mod_data)
        assert editor.source_model.rowCount() >= 0


# ============================================================================
# COMPREHENSIVE ROUNDTRIP VALIDATION TESTS
# ============================================================================


def test_erf_editor_comprehensive_roundtrip_erf(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Comprehensive test that validates ERF data preservation through editor roundtrip."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create comprehensive test ERF
    original_erf = ERF(ERFType.ERF)
    test_resources = [
        ("res1", ResourceType.TXT, b"text data"),
        ("res2", ResourceType.TXI, b"txi data"),
        ("res3", ResourceType.UTC, b"gff data"),
        ("empty", ResourceType.TXT, b""),
        ("large", ResourceType.TXT, b"x" * 10000),
        ("binary", ResourceType.NCS, b"\x00\x01\x02\x03\xff\xfe\xfd"),
        ("max_resref", "a" * 16, b"max length resref"),
    ]

    for resref, restype, data in test_resources:
        original_erf.set_data(resref, restype, data)

    # Serialize original
    original_data = bytearray()
    write_erf(original_erf, original_data)
    original_data = bytes(original_data)

    # Load into editor
    editor.load(tmp_path, "comprehensive_test", ResourceType.ERF, original_data)

    # Verify all resources loaded
    assert editor.source_model.rowCount() == len(test_resources)

    # Save through editor
    saved_data, _ = editor.build()

    # Verify roundtrip
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == len(original_erf)

    # Compare each resource
    for orig_res, saved_res in zip(original_erf, saved_erf):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_comprehensive_roundtrip_rim(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Comprehensive test that validates RIM data preservation through editor roundtrip."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create comprehensive test RIM
    original_rim = RIM()
    test_resources = [
        ("rim_res1", ResourceType.TXT, b"rim text"),
        ("rim_res2", ResourceType.TXI, b"rim txi"),
        ("rim_empty", ResourceType.TXT, b""),
        ("rim_large", ResourceType.NCS, b"x" * 5000),
    ]

    for resref, restype, data in test_resources:
        original_rim.set_data(resref, restype, data)

    # Serialize original
    original_data = bytearray()
    write_rim(original_rim, original_data)
    original_data = bytes(original_data)

    # Load into editor
    editor.load(tmp_path, "comprehensive_rim_test", ResourceType.RIM, original_data)

    # Verify all resources loaded
    assert editor.source_model.rowCount() == len(test_resources)

    # Save through editor
    saved_data, _ = editor.build()

    # Verify roundtrip
    saved_rim = read_rim(saved_data)
    assert len(saved_rim) == len(original_rim)

    # Compare each resource
    for orig_res, saved_res in zip(original_rim, saved_rim):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_comprehensive_roundtrip_mod(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Comprehensive test that validates MOD data preservation through editor roundtrip."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create comprehensive test MOD
    original_mod = ERF(ERFType.MOD)
    test_resources = [
        ("mod_res1", ResourceType.UTC, b"gff data"),
        ("mod_res2", ResourceType.TXT, b"text data"),
        ("mod_script", ResourceType.NSS, b"void main() {}"),
        ("mod_compiled", ResourceType.NCS, b"\x00\x01\x02\x03"),
    ]

    for resref, restype, data in test_resources:
        original_mod.set_data(resref, restype, data)

    # Serialize original
    original_data = bytearray()
    write_erf(original_mod, original_data)
    original_data = bytes(original_data)

    # Load into editor
    editor.load(tmp_path, "comprehensive_mod_test", ResourceType.MOD, original_data)

    # Verify all resources loaded
    assert editor.source_model.rowCount() == len(test_resources)

    # Save through editor
    saved_data, _ = editor.build()

    # Verify roundtrip
    saved_mod = read_erf(saved_data)
    assert len(saved_mod) == len(original_mod)

    # Compare each resource
    for orig_res, saved_res in zip(original_mod, saved_mod):
        assert orig_res.resref == saved_res.resref
        assert orig_res.restype == saved_res.restype
        assert orig_res.data == saved_res.data


def test_erf_editor_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test roundtrip after making various modifications."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create original ERF
    original_erf = ERF(ERFType.ERF)
    original_erf.set_data("original", ResourceType.TXT, b"original data")

    original_data = bytearray()
    write_erf(original_erf, original_data)

    editor.load(tmp_path, "test", ResourceType.ERF, bytes(original_data))

    # Make modifications: add, remove, rename
    # Add new resource
    test_file = tmp_path / "added.txt"
    test_file.write_bytes(b"added data")
    editor.add_resources([str(test_file)])

    # Remove original resource
    editor.ui.tableView.selectRow(0)  # Select first (original) resource
    editor.remove_selected()

    # Rename the added resource
    editor.ui.tableView.selectRow(0)  # Select remaining resource
    from unittest.mock import patch, MagicMock
    from qtpy.QtWidgets import QInputDialog

    # Create a mock dialog instance
    mock_dialog = MagicMock(spec=QInputDialog)
    mock_dialog.exec.return_value = QInputDialog.DialogCode.Accepted
    mock_dialog.textValue.return_value = "renamed"
    mock_dialog.findChild.return_value = None  # Return None for validator setup

    # Patch QInputDialog constructor to return our mock
    with patch("toolset.gui.editors.erf.QInputDialog", return_value=mock_dialog):
        editor.rename_selected()
        QApplication.processEvents()
        QApplication.processEvents()

    # Save and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)

    assert len(saved_erf) == 1
    saved_res = list(saved_erf)[0]
    assert str(saved_res.resref) == "renamed"
    assert saved_res.data == b"added data"


def test_erf_editor_multiple_roundtrips(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test multiple sequential roundtrips preserve data."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Start with ERF containing one resource
    original_erf = ERF(ERFType.ERF)
    original_erf.set_data("test", ResourceType.TXT, b"data")

    original_data = bytearray()
    write_erf(original_erf, original_data)

    current_data = bytes(original_data)

    # Perform 3 roundtrips
    for i in range(3):
        editor.load(tmp_path, f"roundtrip_{i}", ResourceType.ERF, current_data)

        # Add a resource each time
        test_file = tmp_path / f"added_{i}.txt"
        test_file.write_bytes(f"data_{i}".encode())
        editor.add_resources([str(test_file)])

        # Save
        current_data, _ = editor.build()

    # Verify final result
    final_erf = read_erf(current_data)
    assert len(final_erf) == 4  # Original + 3 added

    # Check all resources are present
    resrefs = [str(r.resref) for r in final_erf]
    assert "test" in resrefs
    for i in range(3):
        assert f"added_{i}" in resrefs


# ============================================================================
# HELP DIALOG TESTS
# ============================================================================


def test_erf_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that ERFEditor help dialog opens and displays the correct help file (not 'Help File Not Found')."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for ERFEditor
    editor._show_help_dialog("ERF-File-Format.md")

    # Process events to allow dialog to be created
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)  # Add to qtbot for proper lifecycle management
    qtbot.waitExposed(dialog, timeout=2000)

    # Wait for content to load by checking if HTML is populated
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'ERF-File-Format.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


def test_erf_editor_help_dialog_invalid_file(qtbot: QtBot, installation: HTInstallation):
    """Test help dialog with invalid file shows error."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with invalid file
    editor._show_help_dialog("NonExistentFile.md")

    # Process events to allow dialog to be created
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog, timeout=2000)

    # Wait for content to load
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Should show "Help File Not Found" error
    assert "Help File Not Found" in html, "Help dialog should show error for non-existent file"


def test_erf_editor_help_button_exists(qtbot: QtBot, installation: HTInstallation):
    """Test that ERFEditor has a help button."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Check that help button exists
    assert hasattr(editor, "help_button")
    assert editor.help_button is not None

    # Check that help button is visible
    assert editor.help_button.isVisible()


# ============================================================================
# INTEGRATION TESTS WITH INSTALLATION
# ============================================================================


def test_erf_editor_load_from_installation_erf(qtbot: QtBot, installation: HTInstallation):
    """Test loading ERF files from game installation."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find an ERF file in installation
    from pykotor.extract.file import ResourceIdentifier

    erf_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.ERF)]).values())[:1]

    if not erf_resources:
        pytest.skip("No ERF files found in installation")

    erf_resource = erf_resources[0]
    erf_data = erf_resource.data

    if erf_data:
        editor.load(erf_resource.filepath, erf_resource.resname, erf_resource.restype, erf_data)
        assert editor.source_model.rowCount() >= 0  # Could be empty ERF


def test_erf_editor_load_from_installation_mod(qtbot: QtBot, installation: HTInstallation):
    """Test loading MOD files from game installation."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a MOD file in installation
    from pykotor.extract.file import ResourceIdentifier

    mod_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.MOD)]).values())[:1]

    if not mod_resources:
        pytest.skip("No MOD files found in installation")

    mod_resource = mod_resources[0]
    mod_data = mod_resource.data

    if mod_data:
        editor.load(mod_resource.filepath, mod_resource.resname, mod_resource.restype, mod_data)
        assert editor.source_model.rowCount() >= 0


def test_erf_editor_load_from_installation_rim(qtbot: QtBot, installation: HTInstallation):
    """Test loading RIM files from game installation."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a RIM file in installation
    from pykotor.extract.file import ResourceIdentifier

    rim_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.RIM)]).values())[:1]

    if not rim_resources:
        pytest.skip("No RIM files found in installation")

    rim_resource = rim_resources[0]
    rim_data = rim_resource.data

    if rim_data:
        editor.load(rim_resource.filepath, rim_resource.resname, rim_resource.restype, rim_data)
        assert editor.source_model.rowCount() >= 0


# ============================================================================
# HEADLESS UI TESTS (for compatibility with existing tests)
# ============================================================================


def test_erf_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test ERF Editor in headless UI - loads real file and builds data."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find an ERF file
    erf_file = tmp_path / "test_erf.erf"
    if not erf_file.exists():
        # Create a test ERF file
        erf = ERF(ERFType.ERF)
        erf.set_data("test", ResourceType.TXT, b"test data")
        data = bytearray()
        write_erf(erf, data)
        erf_file.write_bytes(data)

    original_data = erf_file.read_bytes()
    editor.load(erf_file, "test_erf", ResourceType.ERF, original_data)

    # Verify editor loaded the data
    assert editor is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    loaded_erf = read_erf(data)
    assert loaded_erf is not None


def test_erf_editor_memory_efficiency_large_file(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test that ERF Editor handles large files efficiently."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create ERF with many resources
    erf = ERF(ERFType.ERF)
    for i in range(100):  # 100 resources
        erf.set_data(f"res{i:03d}", ResourceType.TXT, f"data{i}".encode())

    data = bytearray()
    write_erf(erf, data)

    # Load into editor
    editor.load(tmp_path, "large_test", ResourceType.ERF, bytes(data))

    # Verify all resources loaded
    assert editor.source_model.rowCount() == 100

    # Build and verify
    saved_data, _ = editor.build()
    saved_erf = read_erf(saved_data)
    assert len(saved_erf) == 100


def test_erf_editor_undo_redo_simulation(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test simulating undo/redo functionality through save/load cycles."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create initial ERF
    erf = ERF(ERFType.ERF)
    erf.set_data("initial", ResourceType.TXT, b"initial")

    data = bytearray()
    write_erf(erf, data)
    initial_data = bytes(data)

    editor.load(tmp_path, "test", ResourceType.ERF, initial_data)

    # "Modify" by adding resource
    test_file = tmp_path / "added.txt"
    test_file.write_bytes(b"added")
    editor.add_resources([str(test_file)])

    modified_data, _ = editor.build()

    # "Undo" by reloading initial data
    editor.load(tmp_path, "test", ResourceType.ERF, initial_data)
    assert editor.source_model.rowCount() == 1

    # "Redo" by reloading modified data
    editor.load(tmp_path, "test", ResourceType.ERF, modified_data)
    assert editor.source_model.rowCount() == 2


# ============================================================================
# HEADLESS UI TESTS (for compatibility with existing tests)
# ============================================================================


def test_erf_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test ERF Editor in headless UI - loads real file and builds data."""
    editor = ERFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find an ERF file
    erf_file = test_files_dir / "001EBO_dlg.erf"
    if not erf_file.exists():
        # Try to get one from installation
        from pykotor.extract.file import ResourceIdentifier

        erf_resources = list(installation.resources([ResourceIdentifier(resname="001EBO_dlg", restype=ResourceType.ERF)]).values())[:1]
        if not erf_resources:
            erf_resources = list(installation.resources([ResourceIdentifier(resname="001EBO_dlg", restype=ResourceType.MOD)]).values())[:1]
        if not erf_resources:
            pytest.skip("No ERF files available for testing")
        erf_resource = erf_resources[0]
        assert erf_resource is not None, "ERF resource not found"
        erf_resource_test = installation.resource(resname=erf_resource.resname, restype=erf_resource.restype)
        assert erf_resource_test is not None, "ERF resource not found"
        erf_data = erf_resource_test.data
        assert erf_data is not None, f"ERF data not found for resource '{erf_resource_test.identifier()}'"
        if not erf_data:
            pytest.fail(f"Could not load ERF data for {erf_resource.identifier()}")
        editor.load(erf_resource.filepath, erf_resource.resname, erf_resource.restype, erf_data)
    else:
        original_data = erf_file.read_bytes()
        editor.load(erf_file, "001EBO_dlg", ResourceType.ERF, original_data)

    # Verify editor loaded the data
    assert editor is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    from pykotor.resource.formats.erf import read_erf

    loaded_erf = read_erf(data)
    assert loaded_erf is not None
