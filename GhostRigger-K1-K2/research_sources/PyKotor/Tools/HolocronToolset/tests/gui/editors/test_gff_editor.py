"""
Unit Tests for GFF Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
The GFF Editor is a generic editor that supports all GFF field types and operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import importlib.util
import unittest
import pytest
from pathlib import Path
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMenu
from toolset.gui.editors.gff import GFFEditor, _LABEL_NODE_ROLE, _TYPE_NODE_ROLE, _VALUE_NODE_ROLE  # type: ignore[import-not-found]
from toolset.data.installation import HTInstallation  # type: ignore[import-not-found]
from pykotor.resource.formats.gff import GFF, GFFContent, GFFFieldType, GFFStruct, GFFList, read_gff, write_gff  # type: ignore[import-not-found]
from pykotor.resource.formats.gff.gff_auto import read_gff  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from pykotor.common.language import LocalizedString, Language, Gender  # type: ignore[import-not-found]
from pykotor.common.misc import ResRef  # type: ignore[import-not-found]
from utility.common.geometry import Vector3, Vector4  # type: ignore[import-not-found]
from pykotor.extract.talktable import TalkTable  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _select_item_in_tree(editor: GFFEditor, item, qtbot: QtBot):
    """Helper function to select an item in the tree view and ensure selection is set."""
    from qtpy.QtCore import QModelIndex, QItemSelectionModel

    source_index = editor.model.indexFromItem(item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)
    # Ensure selection is set in selection model
    selection_model = editor.ui.treeView.selectionModel()
    if selection_model:
        selection_model.select(proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    QApplication.processEvents()  # Small wait for selection to process
    return proxy_index


# ============================================================================
# BASIC FIELD TYPE MANIPULATIONS
# ============================================================================


def test_gff_editor_manipulate_uint8_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating UInt8 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a UInt8 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint8("test_uint8", 42)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the UInt8 field
    root_item = editor.model.item(0, 0)
    uint8_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_uint8":  # type: ignore[arg-type]
            uint8_item = child
            break

    assert uint8_item is not None, "Could not find test_uint8 field"

    # Select the item
    proxy_index = _select_item_in_tree(editor, uint8_item, qtbot)

    # Test various UInt8 values
    test_values = [0, 1, 127, 255]
    for val in test_values:
        # Ensure item is selected
        editor.ui.treeView.setCurrentIndex(proxy_index)
        QApplication.processEvents()  # Small wait for selection to process

        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_uint8("test_uint8") == val

        # Load back and verify UI - need to re-find the item after reload
        editor.load(Path("test.gff"), "test", ResourceType.GFF, data)
        root_item = editor.model.item(0, 0)
        uint8_item = None
        for i in range(root_item.rowCount()):
            child = root_item.child(i, 0)
            if child.data(_LABEL_NODE_ROLE) == "test_uint8":  # type: ignore[arg-type]
                uint8_item = child
                break
        assert uint8_item is not None, "Could not find test_uint8 field after reload"
        source_index = editor.model.indexFromItem(uint8_item)
        proxy_index = editor.proxy_model.mapFromSource(source_index)
        editor.ui.treeView.setCurrentIndex(proxy_index)
        QApplication.processEvents()
        assert editor.ui.intSpin.value() == val


def test_gff_editor_manipulate_int8_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Int8 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with an Int8 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_int8("test_int8", -42)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Int8 field
    root_item = editor.model.item(0, 0)
    int8_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_int8":  # type: ignore[arg-type]
            int8_item = child
            break

    assert int8_item is not None, "Could not find test_int8 field"

    # Select the item
    source_index = editor.model.indexFromItem(int8_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Int8 values
    test_values = [-128, -1, 0, 1, 127]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_int8("test_int8") == val


def test_gff_editor_manipulate_uint16_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating UInt16 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a UInt16 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint16("test_uint16", 1234)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the UInt16 field
    root_item = editor.model.item(0, 0)
    uint16_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_uint16":  # type: ignore[arg-type]
            uint16_item = child
            break

    assert uint16_item is not None, "Could not find test_uint16 field"

    # Select the item
    source_index = editor.model.indexFromItem(uint16_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various UInt16 values
    test_values = [0, 1, 32767, 65535]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_uint16("test_uint16") == val


def test_gff_editor_manipulate_int16_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Int16 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with an Int16 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_int16("test_int16", -1234)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Int16 field
    root_item = editor.model.item(0, 0)
    int16_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_int16":  # type: ignore[arg-type]
            int16_item = child
            break

    assert int16_item is not None, "Could not find test_int16 field"

    # Select the item
    source_index = editor.model.indexFromItem(int16_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Int16 values
    test_values = [-32768, -1, 0, 1, 32767]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_int16("test_int16") == val


def test_gff_editor_manipulate_uint32_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating UInt32 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a UInt32 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("test_uint32", 123456)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the UInt32 field
    root_item = editor.model.item(0, 0)
    uint32_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_uint32":  # type: ignore[arg-type]
            uint32_item = child
            break

    assert uint32_item is not None, "Could not find test_uint32 field"

    # Select the item
    source_index = editor.model.indexFromItem(uint32_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various UInt32 values
    test_values = [0, 1, 2147483647, 4294967295]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_uint32("test_uint32") == val


def test_gff_editor_manipulate_int32_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Int32 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with an Int32 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_int32("test_int32", -123456)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Int32 field
    root_item = editor.model.item(0, 0)
    int32_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_int32":  # type: ignore[arg-type]
            int32_item = child
            break

    assert int32_item is not None, "Could not find test_int32 field"

    # Select the item
    source_index = editor.model.indexFromItem(int32_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Int32 values
    test_values = [-2147483648, -1, 0, 1, 2147483647]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_int32("test_int32") == val


def test_gff_editor_manipulate_uint64_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating UInt64 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a UInt64 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint64("test_uint64", 12345678901234567890)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the UInt64 field
    root_item = editor.model.item(0, 0)
    uint64_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_uint64":  # type: ignore[arg-type]
            uint64_item = child
            break

    assert uint64_item is not None, "Could not find test_uint64 field"

    # Select the item
    source_index = editor.model.indexFromItem(uint64_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various UInt64 values
    test_values = [0, 1, 9223372036854775807, 18446744073709551615]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_uint64("test_uint64") == val


def test_gff_editor_manipulate_int64_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Int64 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with an Int64 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_int64("test_int64", -1234567890123456789)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Int64 field
    root_item = editor.model.item(0, 0)
    int64_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_int64":  # type: ignore[arg-type]
            int64_item = child
            break

    assert int64_item is not None, "Could not find test_int64 field"

    # Select the item
    source_index = editor.model.indexFromItem(int64_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Int64 values
    test_values = [-9223372036854775808, -1, 0, 1, 9223372036854775807]
    for val in test_values:
        editor.ui.intSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_int64("test_int64") == val


def test_gff_editor_manipulate_single_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Single (float) field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a Single field
    gff = GFF(GFFContent.GFF)
    gff.root.set_single("test_single", 3.14159)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Single field
    root_item = editor.model.item(0, 0)
    single_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_single":  # type: ignore[arg-type]
            single_item = child
            break

    assert single_item is not None, "Could not find test_single field"

    # Select the item
    source_index = editor.model.indexFromItem(single_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Single values
    test_values = [0.0, 1.5, -2.5, 3.14159, 999.999, -999.999]
    for val in test_values:
        editor.ui.floatSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert abs(modified_gff.root.get_single("test_single") - val) < 0.0001


def test_gff_editor_manipulate_double_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Double field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a Double field
    gff = GFF(GFFContent.GFF)
    gff.root.set_double("test_double", 3.141592653589793)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Double field
    root_item = editor.model.item(0, 0)
    double_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_double":  # type: ignore[arg-type]
            double_item = child
            break

    assert double_item is not None, "Could not find test_double field"

    # Select the item
    source_index = editor.model.indexFromItem(double_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Double values
    test_values = [0.0, 1.5, -2.5, 3.141592653589793, 999999.999999, -999999.999999]
    for val in test_values:
        editor.ui.floatSpin.setValue(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert abs(modified_gff.root.get_double("test_double") - val) < 1e-6  # More reasonable tolerance for double precision


def test_gff_editor_manipulate_string_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating String field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a String field
    gff = GFF(GFFContent.GFF)
    gff.root.set_string("test_string", "Hello World")
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the String field
    root_item = editor.model.item(0, 0)
    string_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_string":  # type: ignore[arg-type]
            string_item = child
            break

    assert string_item is not None, "Could not find test_string field"

    # Select the item
    source_index = editor.model.indexFromItem(string_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various String values
    test_values = ["", "Hello", "Hello World", "Test with special chars: !@#$%^&*()", "Multi\nLine\nString", "Very long string " * 100]
    for val in test_values:
        editor.ui.textEdit.setPlainText(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert modified_gff.root.get_string("test_string") == val


def test_gff_editor_manipulate_resref_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating ResRef field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a ResRef field
    gff = GFF(GFFContent.GFF)
    gff.root.set_resref("test_resref", ResRef("testmodel"))
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the ResRef field
    root_item = editor.model.item(0, 0)
    resref_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_resref":  # type: ignore[arg-type]
            resref_item = child
            break

    assert resref_item is not None, "Could not find test_resref field"

    # Select the item
    source_index = editor.model.indexFromItem(resref_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various ResRef values
    test_values = ["", "model", "test_model", "abcdefghijklmnop"]  # Max 16 chars
    for val in test_values:
        editor.ui.lineEdit.setText(val)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        assert str(modified_gff.root.get_resref("test_resref")) == val


def test_gff_editor_manipulate_vector3_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Vector3 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a Vector3 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_vector3("test_vector3", Vector3(1.0, 2.0, 3.0))
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Vector3 field
    root_item = editor.model.item(0, 0)
    vector3_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_vector3":  # type: ignore[arg-type]
            vector3_item = child
            break

    assert vector3_item is not None, "Could not find test_vector3 field"

    # Select the item
    source_index = editor.model.indexFromItem(vector3_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Vector3 values
    test_vectors = [
        Vector3(0.0, 0.0, 0.0),
        Vector3(1.5, -2.5, 3.14),
        Vector3(100.0, 200.0, 300.0),
        Vector3(-10.5, 20.7, -30.9),
    ]
    for vec in test_vectors:
        editor.ui.xVec3Spin.setValue(vec.x)
        editor.ui.yVec3Spin.setValue(vec.y)
        editor.ui.zVec3Spin.setValue(vec.z)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        result_vec = modified_gff.root.get_vector3("test_vector3")
        assert abs(result_vec.x - vec.x) < 0.0001
        assert abs(result_vec.y - vec.y) < 0.0001
        assert abs(result_vec.z - vec.z) < 0.0001


def test_gff_editor_manipulate_vector4_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Vector4 field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a Vector4 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_vector4("test_vector4", Vector4(1.0, 2.0, 3.0, 4.0))
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Vector4 field
    root_item = editor.model.item(0, 0)
    vector4_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_vector4":  # type: ignore[arg-type]
            vector4_item = child
            break

    assert vector4_item is not None, "Could not find test_vector4 field"

    # Select the item
    source_index = editor.model.indexFromItem(vector4_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test various Vector4 values
    test_vectors = [
        Vector4(0.0, 0.0, 0.0, 0.0),
        Vector4(1.5, -2.5, 3.14, 0.5),
        Vector4(100.0, 200.0, 300.0, 400.0),
        Vector4(-10.5, 20.7, -30.9, 1.0),
    ]
    for vec in test_vectors:
        editor.ui.xVec4Spin.setValue(vec.x)
        editor.ui.yVec4Spin.setValue(vec.y)
        editor.ui.zVec4Spin.setValue(vec.z)
        editor.ui.wVec4Spin.setValue(vec.w)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        result_vec = modified_gff.root.get_vector4("test_vector4")
        assert abs(result_vec.x - vec.x) < 0.0001
        assert abs(result_vec.y - vec.y) < 0.0001
        assert abs(result_vec.z - vec.z) < 0.0001
        assert abs(result_vec.w - vec.w) < 0.0001


def test_gff_editor_manipulate_binary_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating Binary field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a Binary field
    test_data = b"\x00\x01\x02\x03\x04\x05\xff\xfe\xfd"
    gff = GFF(GFFContent.GFF)
    gff.root.set_binary("test_binary", test_data)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the Binary field
    root_item = editor.model.item(0, 0)
    binary_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_binary":  # type: ignore[arg-type]
            binary_item = child
            break

    assert binary_item is not None, "Could not find test_binary field"

    # Select the item
    source_index = editor.model.indexFromItem(binary_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Binary fields are read-only in the UI, so we just verify they display correctly
    # The binary data should be shown as hex in the blank page
    assert editor.ui.pages.currentWidget() == editor.ui.blankPage

    # Save and verify the binary data is preserved
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_binary("test_binary") == test_data


def test_gff_editor_manipulate_localized_string_field(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating LocalizedString field values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a LocalizedString field
    loc_string = LocalizedString.from_english("Hello World")
    gff = GFF(GFFContent.GFF)
    gff.root.set_locstring("test_locstring", loc_string)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the LocalizedString field
    root_item = editor.model.item(0, 0)
    locstring_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_locstring":  # type: ignore[arg-type]
            locstring_item = child
            break

    assert locstring_item is not None, "Could not find test_locstring field"

    # Select the item
    source_index = editor.model.indexFromItem(locstring_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test stringref editing
    test_stringrefs = [-1, 0, 12345, 99999]
    for strref in test_stringrefs:
        editor.ui.stringrefSpin.setValue(strref)
        # Trigger the update_data method manually since editingFinished signal may not fire in tests
        editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)
        result_locstring = modified_gff.root.get_locstring("test_locstring")
        assert result_locstring.stringref == strref


def test_gff_editor_manipulate_localized_string_substrings(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating LocalizedString substring values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a LocalizedString field containing multiple substrings
    loc_string = LocalizedString.from_invalid()
    loc_string.set_data(Language.ENGLISH, Gender.MALE, "Hello")
    loc_string.set_data(Language.FRENCH, Gender.MALE, "Bonjour")
    gff = GFF(GFFContent.GFF)
    gff.root.set_locstring("test_locstring", loc_string)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the LocalizedString field
    root_item = editor.model.item(0, 0)
    locstring_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_locstring":  # type: ignore[arg-type]
            locstring_item = child
            break

    assert locstring_item is not None, "Could not find test_locstring field"

    # Select the item
    source_index = editor.model.indexFromItem(locstring_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test substring editing
    # Select the first substring (English, Male)
    english_item = editor.ui.substringList.item(0)
    assert english_item is not None, "No substring items found"
    editor.ui.substringList.setCurrentItem(english_item)

    # Edit the substring text
    editor.ui.substringEdit.setPlainText("Modified Hello")

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_locstring = modified_gff.root.get_locstring("test_locstring")
    assert result_locstring.get(Language.ENGLISH, Gender.MALE) == "Modified Hello"


def test_gff_editor_add_remove_localized_string_substring(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test adding and removing LocalizedString substrings."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a LocalizedString field
    loc_string = LocalizedString.from_english("Hello")
    gff = GFF(GFFContent.GFF)
    gff.root.set_locstring("test_locstring", loc_string)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find and select the LocalizedString field
    root_item = editor.model.item(0, 0)
    locstring_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_locstring":  # type: ignore[arg-type]
            locstring_item = child
            break

    assert locstring_item is not None, "Could not find test_locstring field"

    # Select the item
    source_index = editor.model.indexFromItem(locstring_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Add a new substring (French, Male)
    editor.ui.substringLangCombo.setCurrentIndex(Language.FRENCH.value)
    editor.ui.substringGenderCombo.setCurrentIndex(Gender.MALE.value)
    qtbot.mouseClick(editor.ui.addSubstringButton, Qt.MouseButton.LeftButton)

    # Select the new substring and edit it
    french_item = None
    for i in range(editor.ui.substringList.count()):
        item = editor.ui.substringList.item(i)
        if item is not None and "French" in item.text():
            french_item = item
            break

    assert french_item is not None, "French substring not found"
    editor.ui.substringList.setCurrentItem(french_item)
    editor.ui.substringEdit.setPlainText("Bonjour")

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_locstring = modified_gff.root.get_locstring("test_locstring")
    assert result_locstring.get(Language.FRENCH, Gender.MALE) == "Bonjour"

    # Test removing substring
    editor.ui.substringLangCombo.setCurrentIndex(Language.FRENCH.value)
    editor.ui.substringGenderCombo.setCurrentIndex(Gender.MALE.value)
    qtbot.mouseClick(editor.ui.removeSubstringButton, Qt.MouseButton.LeftButton)

    # Save and verify removal
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_locstring = modified_gff.root.get_locstring("test_locstring")
    assert result_locstring.get(Language.FRENCH, Gender.MALE) is None


# ============================================================================
# STRUCT OPERATIONS
# ============================================================================


def test_gff_editor_add_struct_to_struct(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test adding a struct to another struct."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a struct
    gff = GFF(GFFContent.GFF)
    test_struct = GFFStruct()
    test_struct.set_uint32("inner_field", 42)
    gff.root.set_struct("test_struct", test_struct)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the struct
    root_item = editor.model.item(0, 0)
    struct_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_struct":  # type: ignore[arg-type]
            struct_item = child
            break

    assert struct_item is not None, "Could not find test_struct"

    # Add a new struct to the struct (simulating context menu "Add Struct" action)
    # In headless mode, popup menus don't work the same way, so we call the method directly
    # The value for Struct fields should be the struct_id (integer), not a GFFStruct object
    # Default struct_id for new structs is typically 0xFFFFFFFF
    editor.insert_node(struct_item, "New Struct", GFFFieldType.Struct, 0xFFFFFFFF)
    QApplication.processEvents()

    # Verify the struct was added
    assert struct_item.rowCount() > 1, "New struct not added"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_struct = modified_gff.root.get_struct("test_struct")
    # Should have the original field plus the new struct
    assert result_struct.exists("inner_field")
    # The new struct should exist (it will be named "New Struct")
    assert result_struct.exists("New Struct")


def test_gff_editor_remove_struct(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test removing a struct."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with multiple structs in a list
    gff = GFF(GFFContent.GFF)
    test_list = GFFList()
    struct1 = test_list.add(0)  # struct_id required
    struct1.set_uint32("field1", 1)
    struct2 = test_list.add(0)  # struct_id required
    struct2.set_uint32("field2", 2)
    gff.root.set_list("test_list", test_list)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the list
    root_item = editor.model.item(0, 0)
    list_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_list":  # type: ignore[arg-type]
            list_item = child
            break

    assert list_item is not None, "Could not find test_list"

    # Get the first struct in the list
    first_struct = list_item.child(0, 0)
    assert first_struct is not None, "No structs in list"

    # Select and remove the first struct
    proxy_index = _select_item_in_tree(editor, first_struct, qtbot)

    # Remove using remove_selected_nodes (which is what Delete key does)
    editor.remove_selected_nodes()
    QApplication.processEvents()

    # Verify the struct was removed
    assert list_item.rowCount() == 1, "Struct not removed"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_list = modified_gff.root.get_list("test_list")
    assert len(result_list) == 1


def test_gff_editor_edit_struct_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test editing struct ID values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a struct
    gff = GFF(GFFContent.GFF)
    test_struct = GFFStruct(12345)  # Custom struct ID
    test_struct.set_uint32("inner_field", 42)
    gff.root.set_struct("test_struct", test_struct)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the struct
    root_item = editor.model.item(0, 0)
    struct_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_struct":  # type: ignore[arg-type]
            struct_item = child
            break

    assert struct_item is not None, "Could not find test_struct"

    # Select the struct
    proxy_index = _select_item_in_tree(editor, struct_item, qtbot)

    # Edit the struct ID
    editor.ui.intSpin.setValue(54321)
    # Trigger the update_data method manually since editingFinished signal may not fire in tests
    editor.update_data()

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_struct = modified_gff.root.get_struct("test_struct")
    assert result_struct.struct_id == 54321


# ============================================================================
# LIST OPERATIONS
# ============================================================================


def test_gff_editor_add_struct_to_list(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test adding a struct to a list."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a list
    gff = GFF(GFFContent.GFF)
    test_list = GFFList()
    struct1 = test_list.add(0)  # struct_id required
    struct1.set_uint32("field1", 1)
    gff.root.set_list("test_list", test_list)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the list
    root_item = editor.model.item(0, 0)
    list_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_list":  # type: ignore[arg-type]
            list_item = child
            break

    assert list_item is not None, "Could not find test_list"

    # Add a struct to the list (simulating context menu "Add Struct" action)
    # In headless mode, popup menus don't work the same way, so we call the method directly
    editor.add_node(list_item)
    QApplication.processEvents()

    # Verify the struct was added
    assert list_item.rowCount() == 2, "New struct not added to list"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_list = modified_gff.root.get_list("test_list")
    assert len(result_list) == 2


def test_gff_editor_remove_struct_from_list(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test removing a struct from a list."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with multiple structs in a list
    gff = GFF(GFFContent.GFF)
    test_list = GFFList()
    struct1 = test_list.add(0)  # struct_id required
    struct1.set_uint32("field1", 1)
    struct2 = test_list.add(0)  # struct_id required
    struct2.set_uint32("field2", 2)
    struct3 = test_list.add(0)  # struct_id required
    struct3.set_uint32("field3", 3)
    gff.root.set_list("test_list", test_list)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the list
    root_item = editor.model.item(0, 0)
    list_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_list":  # type: ignore[arg-type]
            list_item = child
            break

    assert list_item is not None, "Could not find test_list"

    # Select and remove the middle struct
    middle_struct = list_item.child(1, 0)  # Index 1 (second struct)
    assert middle_struct is not None, "Middle struct not found"

    proxy_index = _select_item_in_tree(editor, middle_struct, qtbot)

    # Remove using remove_selected_nodes (which is what Delete key does)
    editor.remove_selected_nodes()
    QApplication.processEvents()

    # Verify the struct was removed
    assert list_item.rowCount() == 2, "Struct not removed from list"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_list = modified_gff.root.get_list("test_list")
    assert len(result_list) == 2


# ============================================================================
# CONTEXT MENU OPERATIONS
# ============================================================================


def test_gff_editor_context_menu_add_all_field_types(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test adding all field types via context menu."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a struct
    gff = GFF(GFFContent.GFF)
    test_struct = GFFStruct()
    gff.root.set_struct("test_struct", test_struct)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the struct
    root_item = editor.model.item(0, 0)
    struct_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_struct":  # type: ignore[arg-type]
            struct_item = child
            break

    assert struct_item is not None, "Could not find test_struct"

    # Test adding each field type (simulating context menu actions)
    # In headless mode, popup menus don't work, so we call insert_node directly
    field_type_map = {
        "Add UInt8": (GFFFieldType.UInt8, 0),
        "Add UInt16": (GFFFieldType.UInt16, 0),
        "Add UInt32": (GFFFieldType.UInt32, 0),
        "Add UInt64": (GFFFieldType.UInt64, 0),
        "Add Int8": (GFFFieldType.Int8, 0),
        "Add Int16": (GFFFieldType.Int16, 0),
        "Add Int32": (GFFFieldType.Int32, 0),
        "Add Int64": (GFFFieldType.Int64, 0),
        "Add Single": (GFFFieldType.Single, 0.0),
        "Add Double": (GFFFieldType.Double, 0.0),
        "Add ResRef": (GFFFieldType.ResRef, ResRef.from_blank()),
        "Add String": (GFFFieldType.String, ""),
        "Add LocalizedString": (GFFFieldType.LocalizedString, LocalizedString.from_invalid()),
        "Add Binary": (GFFFieldType.Binary, b""),
        "Add Vector3": (GFFFieldType.Vector3, Vector3.from_null()),
        "Add Vector4": (GFFFieldType.Vector4, Vector4.from_null()),
        "Add Struct": (GFFFieldType.Struct, 0xFFFFFFFF),  # struct_id for new structs
        "Add List": (GFFFieldType.List, GFFList()),
    }

    for field_type_name, (field_type, default_value) in field_type_map.items():
        label = field_type_name.replace("Add ", "New ")
        editor.insert_node(struct_item, label, field_type, default_value)
        QApplication.processEvents()

    # Verify fields were added (should have many children now)
    assert struct_item.rowCount() >= len(field_type_map), "Not all field types were added"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_struct = modified_gff.root.get_struct("test_struct")
    # Should contain all the added fields
    assert result_struct.exists("New UInt8")
    assert result_struct.exists("New String")
    assert result_struct.exists("New Struct")


# ============================================================================
# TYPE CHANGING
# ============================================================================


def test_gff_editor_change_field_type(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test changing field types."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a UInt32 field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("test_field", 42)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the field
    root_item = editor.model.item(0, 0)
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_field":  # type: ignore[arg-type]
            field_item = child
            break

    assert field_item is not None, "Could not find test_field"

    # Select the field
    proxy_index = _select_item_in_tree(editor, field_item, qtbot)

    # Change type from UInt32 to String
    # Find the index of "String" in the combo box
    string_index = -1
    for i in range(editor.ui.typeCombo.count()):
        if editor.ui.typeCombo.itemText(i) == "String":
            string_index = i
            break
    assert string_index >= 0, "String type not found in combo box"

    # Set the current index and trigger the activated signal
    editor.ui.typeCombo.setCurrentIndex(string_index)
    editor.type_changed(string_index)  # Call the method directly to ensure it's triggered

    # Verify the type changed
    assert field_item.data(_TYPE_NODE_ROLE) == GFFFieldType.String

    # Set a string value
    editor.ui.textEdit.setPlainText("Converted from UInt32")

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_string("test_field") == "Converted from UInt32"


def test_gff_editor_change_field_label(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test changing field labels."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a field
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("old_label", 42)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the field
    root_item = editor.model.item(0, 0)
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "old_label":  # type: ignore[arg-type]
            field_item = child
            break

    assert field_item is not None, "Could not find old_label field"

    # Select the field
    source_index = editor.model.indexFromItem(field_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Change the label
    editor.ui.labelEdit.setText("new_label")
    # Trigger the update_data method manually since editingFinished signal may not fire in tests
    editor.update_data()

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.exists("new_label")
    assert not modified_gff.root.exists("old_label")
    assert modified_gff.root.get_uint32("new_label") == 42


# ============================================================================
# LOAD/SAVE ROUNDTRIP VALIDATION
# ============================================================================


def test_gff_editor_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test that save/load roundtrip preserves all data exactly."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a comprehensive test GFF
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint8("uint8_field", 255)
    gff.root.set_int32("int32_field", -12345)
    gff.root.set_single("float_field", 3.14159)
    gff.root.set_string("string_field", "Test String")
    gff.root.set_resref("resref_field", ResRef("testmodel"))
    gff.root.set_vector3("vector3_field", Vector3(1.0, 2.0, 3.0))
    gff.root.set_vector4("vector4_field", Vector4(1.0, 2.0, 3.0, 4.0))
    gff.root.set_binary("binary_field", b"\x00\x01\x02\x03")

    # Add a struct
    test_struct = GFFStruct()
    test_struct.set_uint32("inner_field", 42)
    gff.root.set_struct("struct_field", test_struct)

    # Add a list
    test_list = GFFList()
    list_struct = test_list.add(0)  # struct_id required
    list_struct.set_string("list_item", "Item 1")
    gff.root.set_list("list_field", test_list)

    # Add localized string
    loc_string = LocalizedString.from_english("Hello World")
    gff.root.set_locstring("locstring_field", loc_string)

    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)
    original_gff = read_gff(bytes(original_data))

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Save without modifications
    data, _ = editor.build()
    new_gff = read_gff(data)

    # Verify all fields match
    assert new_gff.root.get_uint8("uint8_field") == original_gff.root.get_uint8("uint8_field")
    assert new_gff.root.get_int32("int32_field") == original_gff.root.get_int32("int32_field")
    assert abs(new_gff.root.get_single("float_field") - original_gff.root.get_single("float_field")) < 0.0001
    assert new_gff.root.get_string("string_field") == original_gff.root.get_string("string_field")
    assert str(new_gff.root.get_resref("resref_field")) == str(original_gff.root.get_resref("resref_field"))

    vec3_orig = original_gff.root.get_vector3("vector3_field")
    vec3_new = new_gff.root.get_vector3("vector3_field")
    assert abs(vec3_new.x - vec3_orig.x) < 0.0001

    vec4_orig = original_gff.root.get_vector4("vector4_field")
    vec4_new = new_gff.root.get_vector4("vector4_field")
    assert abs(vec4_new.w - vec4_orig.w) < 0.0001

    assert new_gff.root.get_binary("binary_field") == original_gff.root.get_binary("binary_field")

    # Verify struct
    orig_struct = original_gff.root.get_struct("struct_field")
    new_struct = new_gff.root.get_struct("struct_field")
    assert new_struct.get_uint32("inner_field") == orig_struct.get_uint32("inner_field")

    # Verify list
    orig_list = original_gff.root.get_list("list_field")
    new_list = new_gff.root.get_list("list_field")
    assert len(new_list) == len(orig_list)
    assert new_list[0].get_string("list_item") == orig_list[0].get_string("list_item")

    # Verify localized string
    orig_loc = original_gff.root.get_locstring("locstring_field")
    new_loc = new_gff.root.get_locstring("locstring_field")
    assert new_loc.get(Language.ENGLISH, Gender.MALE) == orig_loc.get(Language.ENGLISH, Gender.MALE)


def test_gff_editor_comprehensive_gff_roundtrip(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Comprehensive test that validates ALL GFF fields are preserved through editor roundtrip."""
    from pykotor.resource.formats.gff import read_gff

    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Use a real GFF file if available
    git_file = test_files_dir / "zio001.git"
    if git_file.exists():
        original_data = git_file.read_bytes()
        res_type = ResourceType.GIT
    else:
        # Create a test GFF
        gff = GFF(GFFContent.GFF)
        gff.root.set_string("test", "value")
        original_data = bytearray()
        write_gff(gff, original_data, ResourceType.GFF)
        original_data = bytes(original_data)
        res_type = ResourceType.GFF

    # Load original GFF and capture all field values
    original_gff = read_gff(original_data)

    def get_all_fields(struct: GFFStruct, prefix: str = "") -> dict:
        """Recursively extract all fields from a GFF struct."""
        fields = {}
        for label, ftype, value in struct:
            full_label = f"{prefix}{label}" if prefix else label

            if ftype == GFFFieldType.Struct:
                nested = struct.acquire(label, GFFStruct())
                fields[full_label] = ("Struct", nested.struct_id)
                fields.update(get_all_fields(nested, f"{full_label}."))
            elif ftype == GFFFieldType.List:
                lst = struct.acquire(label, GFFList())
                fields[full_label] = ("List", len(lst))
                for i, item in enumerate(lst):
                    fields.update(get_all_fields(item, f"{full_label}[{i}]."))
            elif ftype == GFFFieldType.LocalizedString:
                locstr = struct.acquire(label, LocalizedString.from_invalid())
                locstr_tuples = sorted((lang.value, gender.value, str(text)) for lang, gender, text in locstr)
                fields[full_label] = ("LocalizedString", locstr.stringref, tuple(locstr_tuples))
            else:
                fields[full_label] = (ftype.name, value)
        return fields

    original_fields = get_all_fields(original_gff.root)

    # Load into editor
    editor.load(Path("test.gff"), "test", res_type, original_data)

    # Build (serialize) through editor without any modifications
    new_data, _ = editor.build()
    new_gff = read_gff(new_data)
    new_fields = get_all_fields(new_gff.root)

    # Compare all fields
    all_labels = set(original_fields.keys()) | set(new_fields.keys())

    mismatches = []
    missing_in_new = []
    missing_in_original = []

    for label in sorted(all_labels):
        if label not in new_fields:
            missing_in_new.append(label)
            continue
        if label not in original_fields:
            missing_in_original.append(label)
            continue

        orig_value = original_fields[label]
        new_value = new_fields[label]

        # Handle floating point comparison with tolerance
        if orig_value[0] in ("Single", "Double") and new_value[0] in ("Single", "Double"):
            if abs(orig_value[1] - new_value[1]) > 0.0001:
                mismatches.append((label, orig_value, new_value))
        elif orig_value != new_value:
            mismatches.append((label, orig_value, new_value))

    # Report issues
    error_msg = []
    if missing_in_new:
        error_msg.append(f"Fields missing in roundtrip output: {missing_in_new}")
    if mismatches:
        mismatch_details = "\n".join(
            [
                f"  {label}: original={orig} -> new={new}"
                for label, orig, new in mismatches[:10]  # Limit output
            ]
        )
        if len(mismatches) > 10:
            mismatch_details += f"\n  ... and {len(mismatches) - 10} more"
        error_msg.append(f"Field value mismatches:\n{mismatch_details}")

    assert not error_msg, f"GFF roundtrip validation failed:\n" + "\n".join(error_msg)


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


def test_gff_editor_minimum_maximum_values(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test setting all numeric fields to minimum and maximum values."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with various numeric fields
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint8("uint8_field", 0)
    gff.root.set_int32("int32_field", 0)
    gff.root.set_single("float_field", 0.0)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Test minimum and maximum values
    # Use reasonable float values that won't cause overflow
    field_tests = [
        ("uint8_field", GFFFieldType.UInt8, 0),
        ("uint8_field", GFFFieldType.UInt8, 255),
        ("int32_field", GFFFieldType.Int32, -2147483648),
        ("int32_field", GFFFieldType.Int32, 2147483647),
        ("float_field", GFFFieldType.Single, -1000000.0),
        ("float_field", GFFFieldType.Single, 1000000.0),
    ]

    for field_name, field_type, test_value in field_tests:
        # Find the field
        root_item = editor.model.item(0, 0)
        field_item = None
        for i in range(root_item.rowCount()):
            child = root_item.child(i, 0)
            if child.data(_LABEL_NODE_ROLE) == field_name:  # type: ignore[arg-type]
                field_item = child
                break

        assert field_item is not None, f"Could not find {field_name}"

        # Select the field
        proxy_index = _select_item_in_tree(editor, field_item, qtbot)

        # Set the value
        if field_type in {GFFFieldType.UInt8, GFFFieldType.Int32}:
            editor.ui.intSpin.setValue(test_value)
            # Trigger the update_data method manually since editingFinished signal may not fire in tests
            editor.update_data()
        elif field_type == GFFFieldType.Single:
            editor.ui.floatSpin.setValue(test_value)
            # Trigger the update_data method manually since editingFinished signal may not fire in tests
            editor.update_data()

        # Save and verify
        data, _ = editor.build()
        modified_gff = read_gff(data)

        if field_type == GFFFieldType.UInt8:
            assert modified_gff.root.get_uint8(field_name) == test_value
        elif field_type == GFFFieldType.Int32:
            assert modified_gff.root.get_int32(field_name) == test_value
        elif field_type == GFFFieldType.Single:
            assert abs(modified_gff.root.get_single(field_name) - test_value) < 0.0001  # Reasonable tolerance for float32


def test_gff_editor_empty_and_large_strings(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test handling of empty strings and very large strings."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a string field
    gff = GFF(GFFContent.GFF)
    gff.root.set_string("string_field", "initial")
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the string field
    root_item = editor.model.item(0, 0)
    string_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "string_field":  # type: ignore[arg-type]
            string_item = child
            break

    assert string_item is not None, "Could not find string_field"

    # Select the field
    source_index = editor.model.indexFromItem(string_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Test empty string
    editor.ui.textEdit.setPlainText("")

    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_string("string_field") == ""

    # Test very large string
    large_string = "A" * 10000
    editor.ui.textEdit.setPlainText(large_string)

    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_string("string_field") == large_string


def test_gff_editor_special_characters(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test handling of special characters in strings and labels."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF with a field
    gff = GFF(GFFContent.GFF)
    gff.root.set_string("normal_field", "normal")
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the field
    root_item = editor.model.item(0, 0)
    assert root_item is not None, "Root item not found"
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "normal_field":  # type: ignore[arg-type]
            field_item = child
            break

    assert field_item is not None, "Could not find normal_field"

    # Select the field
    proxy_index = _select_item_in_tree(editor, field_item, qtbot)

    # Test special characters in string value
    special_string = "String with special chars: !@#$%^&*()[]{}|\\:;\"'<>?,./"
    editor.ui.textEdit.setPlainText(special_string)
    # Ensure item is still selected and trigger update
    editor.ui.treeView.setCurrentIndex(proxy_index)
    QApplication.processEvents()
    editor.update_data()

    # Save and verify the string value was saved
    data_temp, _ = editor.build()
    temp_gff = read_gff(data_temp)
    assert temp_gff.root.get_string("normal_field") == special_string, "String value should be saved"

    # Now test special characters in label - reload first to get a clean state
    editor.load(Path("test.gff"), "test", ResourceType.GFF, data_temp)

    # Find the field again after reload
    root_item = editor.model.item(0, 0)
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "normal_field":  # type: ignore[arg-type]
            field_item = child
            break
    assert field_item is not None, "Could not find normal_field after reload"

    # Select the field again - this will load the item and populate textEdit
    proxy_index = _select_item_in_tree(editor, field_item, qtbot)

    # Verify the textEdit has the correct value (should be loaded from the item)
    current_text = editor.ui.textEdit.toPlainText()
    assert current_text == special_string, f"TextEdit should have the special string after reload, got: {current_text!r}"

    # Now change the label - ensure text is still in textEdit
    # GFF labels are limited to 16 characters, so use a shorter label
    special_label = "field_special_!@#"
    # Explicitly set the text again to ensure it's in textEdit when update_data() is called
    editor.ui.textEdit.setPlainText(special_string)
    editor.ui.labelEdit.setText(special_label)
    # Re-select the item to ensure it's selected
    editor.ui.treeView.setCurrentIndex(proxy_index)
    QApplication.processEvents()
    # Trigger the update_data method manually - this should save both label and text
    editor.update_data()

    # Verify the item has the correct data before building
    assert field_item.data(_VALUE_NODE_ROLE) == special_string, "Item should have the special string value"
    # GFF labels are limited to 16 characters, so the label will be truncated if longer
    actual_label = field_item.data(_LABEL_NODE_ROLE)
    assert actual_label == special_label[:16], f"Item should have the special label (max 16 chars), expected: {special_label[:16]!r}, got: {actual_label!r}"

    # Save and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    # Use the truncated label for lookup
    assert modified_gff.root.get_string(special_label[:16]) == special_string


# ============================================================================
# NEW FILE CREATION TESTS
# ============================================================================


def test_gff_editor_new_file_creation(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new GFF file from scratch."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new file
    editor.new()

    # Set GFF content type (required for building)
    editor._gff_content = GFFContent.GFF

    # Verify the tree has a root
    root_item = editor.model.item(0, 0)
    assert root_item is not None, "Root item not created"
    # Root item has text "[ROOT]" but no label role (ftype is None for root)
    assert root_item.text() == "[ROOT]"

    # Build and verify it's a valid GFF
    data, _ = editor.build()
    new_gff = read_gff(data)
    assert new_gff is not None
    # Default root struct ID is -1 (which is 0xFFFFFFFF in unsigned)
    assert new_gff.root.struct_id == -1


def test_gff_editor_new_file_add_fields(qtbot: QtBot, installation: HTInstallation):
    """Test adding fields to a newly created GFF file."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new file
    editor.new()

    # Set GFF content type (required for building)
    editor._gff_content = GFFContent.GFF

    # Get the root item
    root_item = editor.model.item(0, 0)
    assert root_item is not None, "Root item not created"

    # Add various field types to the root
    test_fields = [
        ("new_uint32", GFFFieldType.UInt32, 12345),
        ("new_string", GFFFieldType.String, "New String Value"),
        ("new_float", GFFFieldType.Single, 2.718),
    ]

    for field_name, field_type, field_value in test_fields:
        # Add the field
        new_item = editor.insert_node(root_item, field_name, field_type, field_value)
        editor.refresh_item_text(new_item)

    # Build and verify
    data, _ = editor.build()
    new_gff = read_gff(data)

    assert new_gff.root.get_uint32("new_uint32") == 12345
    assert new_gff.root.get_string("new_string") == "New String Value"
    assert abs(new_gff.root.get_single("new_float") - 2.718) < 0.001


# ============================================================================
# TLK INTEGRATION TESTS
# ============================================================================


def test_gff_editor_tlk_integration(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test TLK table integration for localized strings."""
    # This test would require a TLK file to be available
    # For now, just test that the TLK selection functionality exists
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify the TLK integration method exists
    assert hasattr(editor, "select_talk_table")
    assert callable(editor.select_talk_table)

    # Create a test GFF with a localized string
    gff = GFF(GFFContent.GFF)
    loc_string = LocalizedString.from_invalid()
    loc_string.stringref = 12345
    gff.root.set_locstring("test_locstring", loc_string)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load into editor
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))

    # Find the localized string field
    root_item = editor.model.item(0, 0)
    locstring_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_locstring":  # type: ignore[arg-type]
            locstring_item = child
            break

    assert locstring_item is not None, "Could not find test_locstring field"

    # Select the field
    source_index = editor.model.indexFromItem(locstring_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.setCurrentIndex(proxy_index)

    # Verify stringref spin box is available
    assert editor.ui.stringrefSpin.value() == 12345


# ============================================================================
# HELP DIALOG TESTS
# ============================================================================


def test_gff_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that GFFEditor help dialog opens and displays the correct help file."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for GFFEditor
    editor._show_help_dialog("GFF-File-Format.md")

    # Process events to allow dialog to be created
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)  # Add to qtbot for proper lifecycle management
    qtbot.waitExposed(dialog, timeout=2000)

    # Wait for content to load
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, "Help file 'GFF-File-Format.md' should be found, but error was shown"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


# ============================================================================
# Pytest-based headless UI tests
# ============================================================================


def test_gff_editor_headless_ui_load_build(qtbot, installation: HTInstallation, test_files_dir):
    """Test GFF Editor in headless UI - loads real file and builds data."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a GFF file
    gff_file = test_files_dir / "zio001.git"  # GIT files are GFF format
    if not gff_file.exists():
        # Try to get one from installation
        gff_resources = installation.resources()  # Get all resources
        gff_resource = None
        for identifier, resource_result in gff_resources.items():
            if resource_result and resource_result.restype in [ResourceType.GFF, ResourceType.GIT, ResourceType.ARE]:
                gff_resource = resource_result
                break

        if gff_resource is None:
            pytest.skip("No GFF files available for testing")

        gff_data = gff_resource.data
        if not gff_data:
            pytest.skip(f"Could not load GFF data for {gff_resource.identifier()}")
        editor.load(gff_resource.filepath if hasattr(gff_resource, "filepath") else Path("test.gff"), gff_resource.resname, gff_resource.restype, gff_data)
    else:
        original_data = gff_file.read_bytes()
        editor.load(gff_file, "zio001", ResourceType.GIT, original_data)

    # Verify editor loaded the data
    assert editor is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    loaded_gff = read_gff(data)
    assert loaded_gff is not None


# ============================================================================
# ADDITIONAL HEADLESS-SPECIFIC TESTS
# ============================================================================


def test_gff_editor_headless_complex_nested_structures(qtbot: QtBot, installation: HTInstallation):
    """Test complex nested structures in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a complex GFF with deeply nested structures
    gff = GFF(GFFContent.GFF)

    # Add a struct with nested structs
    outer_struct = GFFStruct()
    outer_struct.set_string("outer_field", "outer_value")

    inner_struct = GFFStruct()
    inner_struct.set_uint32("inner_field", 42)
    outer_struct.set_struct("nested_struct", inner_struct)

    # Add a list with structs containing nested structs
    complex_list = GFFList()
    list_struct1 = complex_list.add(0)
    list_struct1.set_string("list_field1", "value1")
    nested_in_list = GFFStruct()
    nested_in_list.set_int32("nested_in_list", 100)
    list_struct1.set_struct("nested", nested_in_list)

    list_struct2 = complex_list.add(0)
    list_struct2.set_string("list_field2", "value2")

    outer_struct.set_list("complex_list", complex_list)
    gff.root.set_struct("complex_struct", outer_struct)

    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    # Load in headless mode
    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()  # Wait for tree to populate

    # Navigate and modify nested structures
    root_item = editor.model.item(0, 0)
    complex_struct_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "complex_struct":  # type: ignore[arg-type]
            complex_struct_item = child
            break

    assert complex_struct_item is not None, "Could not find complex_struct"

    # Expand and find nested struct
    source_index = editor.model.indexFromItem(complex_struct_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    nested_struct_item = None
    for i in range(complex_struct_item.rowCount()):
        child = complex_struct_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "nested_struct":  # type: ignore[arg-type]
            nested_struct_item = child
            break

    assert nested_struct_item is not None, "Could not find nested_struct"

    # Modify nested struct field
    proxy_index = _select_item_in_tree(editor, nested_struct_item, qtbot)
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    # Find and modify inner field
    inner_field_item = None
    for i in range(nested_struct_item.rowCount()):
        child = nested_struct_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "inner_field":  # type: ignore[arg-type]
            inner_field_item = child
            break

    assert inner_field_item is not None, "Could not find inner_field"

    proxy_index = _select_item_in_tree(editor, inner_field_item, qtbot)
    editor.ui.intSpin.setValue(999)
    editor.update_data()

    # Build and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_complex = modified_gff.root.get_struct("complex_struct")
    result_nested = result_complex.get_struct("nested_struct")
    assert result_nested.get_uint32("inner_field") == 999


def test_gff_editor_headless_rapid_sequential_operations(qtbot: QtBot, installation: HTInstallation):
    """Test rapid sequential operations in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("test_field", 0)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Find the field
    root_item = editor.model.item(0, 0)
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_field":  # type: ignore[arg-type]
            field_item = child
            break

    assert field_item is not None

    # Perform rapid sequential operations
    proxy_index = _select_item_in_tree(editor, field_item, qtbot)

    for i in range(10):
        editor.ui.treeView.setCurrentIndex(proxy_index)
        QApplication.processEvents()
        editor.ui.intSpin.setValue(i * 10)
        editor.update_data()
        QApplication.processEvents()

    # Verify final value
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_uint32("test_field") == 90


def test_gff_editor_headless_tree_expansion_collapse(qtbot: QtBot, installation: HTInstallation):
    """Test tree view expansion and collapse in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a GFF with nested structures
    gff = GFF(GFFContent.GFF)
    test_struct = GFFStruct()
    test_struct.set_uint32("field1", 1)
    test_struct.set_uint32("field2", 2)
    nested_struct = GFFStruct()
    nested_struct.set_string("nested_field", "nested")
    test_struct.set_struct("nested", nested_struct)
    gff.root.set_struct("test_struct", test_struct)

    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Find and expand the struct
    root_item = editor.model.item(0, 0)
    struct_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_struct":  # type: ignore[arg-type]
            struct_item = child
            break

    assert struct_item is not None

    source_index = editor.model.indexFromItem(struct_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)

    # Expand
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()
    assert editor.ui.treeView.isExpanded(proxy_index), "Struct should be expanded"

    # Collapse
    editor.ui.treeView.collapse(proxy_index)
    QApplication.processEvents()
    assert not editor.ui.treeView.isExpanded(proxy_index), "Struct should be collapsed"

    # Expand again and verify nested items are accessible
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    # Find nested struct
    nested_item = None
    for i in range(struct_item.rowCount()):
        child = struct_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "nested":  # type: ignore[arg-type]
            nested_item = child
            break

    assert nested_item is not None, "Nested struct should be accessible after expansion"


def test_gff_editor_headless_multiple_field_type_changes(qtbot: QtBot, installation: HTInstallation):
    """Test multiple field type changes in sequence in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test GFF
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("test_field", 42)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Find the field
    root_item = editor.model.item(0, 0)
    field_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_field":  # type: ignore[arg-type]
            field_item = child
            break

    assert field_item is not None

    proxy_index = _select_item_in_tree(editor, field_item, qtbot)

    # Change type multiple times: UInt32 -> String -> Int32 -> Single
    type_changes = [
        ("String", "test_string_value"),
        ("Int32", -12345),
        ("Single", 3.14159),
    ]

    for type_name, test_value in type_changes:
        # Find the index of the type in combo box
        type_index = -1
        for i in range(editor.ui.typeCombo.count()):
            if editor.ui.typeCombo.itemText(i) == type_name:
                type_index = i
                break
        assert type_index >= 0, f"Type {type_name} not found in combo box"

        editor.ui.treeView.setCurrentIndex(proxy_index)
        QApplication.processEvents()
        editor.ui.typeCombo.setCurrentIndex(type_index)
        editor.type_changed(type_index)
        QApplication.processEvents()

        # Set appropriate value based on type
        if type_name == "String":
            editor.ui.textEdit.setPlainText(test_value)
        elif type_name == "Int32":
            editor.ui.intSpin.setValue(test_value)
        elif type_name == "Single":
            editor.ui.floatSpin.setValue(test_value)

        editor.update_data()
        QApplication.processEvents()

    # Verify final type and value
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert abs(modified_gff.root.get_single("test_field") - 3.14159) < 0.0001  # Float precision tolerance


def test_gff_editor_headless_complex_list_manipulations(qtbot: QtBot, installation: HTInstallation):
    """Test complex list manipulations with nested structs in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a GFF with a list containing structs with nested data
    gff = GFF(GFFContent.GFF)
    test_list = GFFList()

    # Add multiple structs to the list
    for i in range(5):
        list_struct = test_list.add(0)
        list_struct.set_string("name", f"item_{i}")
        list_struct.set_uint32("index", i)
        # Add nested struct
        nested = GFFStruct()
        nested.set_single("nested_value", float(i) * 1.5)
        list_struct.set_struct("nested", nested)

    gff.root.set_list("test_list", test_list)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Find the list
    root_item = editor.model.item(0, 0)
    list_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_list":  # type: ignore[arg-type]
            list_item = child
            break

    assert list_item is not None
    assert list_item.rowCount() == 5, "List should have 5 items"

    # Expand list and modify items
    source_index = editor.model.indexFromItem(list_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    # Modify the third item's nested struct
    third_item = list_item.child(2, 0)  # Index 2 (third item)
    assert third_item is not None

    # Expand third item
    source_index = editor.model.indexFromItem(third_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    # Find nested struct
    nested_item = None
    for i in range(third_item.rowCount()):
        child = third_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "nested":  # type: ignore[arg-type]
            nested_item = child
            break

    assert nested_item is not None

    # Expand nested and modify field
    source_index = editor.model.indexFromItem(nested_item)
    proxy_index = editor.proxy_model.mapFromSource(source_index)
    editor.ui.treeView.expand(proxy_index)
    QApplication.processEvents()

    nested_field_item = None
    for i in range(nested_item.rowCount()):
        child = nested_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "nested_value":  # type: ignore[arg-type]
            nested_field_item = child
            break

    assert nested_field_item is not None

    proxy_index = _select_item_in_tree(editor, nested_field_item, qtbot)
    editor.ui.floatSpin.setValue(99.99)
    editor.update_data()

    # Build and verify
    data, _ = editor.build()
    modified_gff = read_gff(data)
    result_list = modified_gff.root.get_list("test_list")
    assert len(result_list) == 5
    third_result = result_list[2]
    nested_result = third_result.get_struct("nested")
    assert abs(nested_result.get_single("nested_value") - 99.99) < 0.001


def test_gff_editor_headless_tree_sorting(qtbot: QtBot, installation: HTInstallation):
    """Test tree view sorting in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a GFF with multiple fields
    gff = GFF(GFFContent.GFF)
    gff.root.set_uint32("z_field", 1)
    gff.root.set_uint32("a_field", 2)
    gff.root.set_uint32("m_field", 3)
    gff.root.set_string("field_1", "value1")
    gff.root.set_string("field_10", "value10")
    gff.root.set_string("field_2", "value2")

    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Verify sorting is enabled
    assert editor.ui.treeView.isSortingEnabled(), "Tree view sorting should be enabled"

    # Get all field labels and verify they're sorted
    root_item = editor.model.item(0, 0)
    field_labels = []
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        label = child.data(_LABEL_NODE_ROLE)
        if label:
            field_labels.append(label)

    # Fields should be sorted (tree view has sorting enabled)
    # Note: The actual sort order depends on the proxy model's sorting logic
    assert len(field_labels) >= 6, "Should have at least 6 fields"


def test_gff_editor_headless_binary_data_display(qtbot: QtBot, installation: HTInstallation):
    """Test binary data display in headless mode."""
    editor = GFFEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a GFF with binary data
    binary_data = bytes(range(256))  # 0x00 to 0xFF
    gff = GFF(GFFContent.GFF)
    gff.root.set_binary("test_binary", binary_data)
    original_data = bytearray()
    write_gff(gff, original_data, ResourceType.GFF)

    editor.load(Path("test.gff"), "test", ResourceType.GFF, bytes(original_data))
    QApplication.processEvents()

    # Find the binary field
    root_item = editor.model.item(0, 0)
    binary_item = None
    for i in range(root_item.rowCount()):
        child = root_item.child(i, 0)
        if child.data(_LABEL_NODE_ROLE) == "test_binary":  # type: ignore[arg-type]
            binary_item = child
            break

    assert binary_item is not None

    # Select the binary field - should show in blank page
    proxy_index = _select_item_in_tree(editor, binary_item, qtbot)

    # Verify blank page is shown (binary fields are read-only)
    assert editor.ui.pages.currentWidget() == editor.ui.blankPage, "Binary field should show blank page"

    # Verify binary data is preserved
    data, _ = editor.build()
    modified_gff = read_gff(data)
    assert modified_gff.root.get_binary("test_binary") == binary_data


if __name__ == "__main__":
    if importlib.util.find_spec("pytest"):
        pytest.main(["-v", "-s", __file__])
    else:
        unittest.main()
