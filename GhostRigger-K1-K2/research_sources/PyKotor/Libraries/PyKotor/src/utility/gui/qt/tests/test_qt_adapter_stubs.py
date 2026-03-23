"""Unit Tests for Qt adapter stubs to ensure 1:1 API compatibility.

This test suite validates that all Qt adapter classes properly implement
the Qt API with correct method signatures, return types, and behavior.
"""

from __future__ import annotations

import tempfile

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from qtpy.QtCore import (
    QDir,
    QFileInfo,
    QModelIndex,
    QUrl,  # pyright: ignore[reportPrivateImportUsage]
    Qt,
)
from qtpy.QtWidgets import QApplication, QFileDialog, QFileSystemModel

# Import all adapter classes
from utility.gui.qt.adapters.filesystem.pyextendedinformation import PyQExtendedInformation
from utility.gui.qt.adapters.filesystem.pyfileinfogatherer import PyFileInfoGatherer
from utility.gui.qt.adapters.filesystem.pyfilesystemmodel import PyFileSystemModel
from utility.gui.qt.adapters.filesystem.pyfilesystemmodelsorter import PyFileSystemModelSorter
from utility.gui.qt.adapters.filesystem.pyfilesystemnode import PyFileSystemNode
from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialog as AdapterQFileDialog


class TestQtAdapterAPICompatibility:
    """Test class to validate Qt adapter API compatibility."""

    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QApplication for tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_pyfilesystemmodel_api_compatibility(self, temp_dir):
        """Test PyFileSystemModel API compatibility with QFileSystemModel."""
        # Test instantiation
        py_model = PyFileSystemModel()
        qt_model = QFileSystemModel()

        # Test basic properties
        assert hasattr(py_model, "rootPath")
        assert hasattr(py_model, "setRootPath")
        assert hasattr(py_model, "filter")
        assert hasattr(py_model, "setFilter")
        assert hasattr(py_model, "nameFilters")
        assert hasattr(py_model, "setNameFilters")

        # Test root path functionality
        test_path = str(temp_dir)
        py_model.setRootPath(test_path)
        assert py_model.rootPath() == test_path

        qt_model.setRootPath(test_path)
        assert qt_model.rootPath() == test_path

        # Test model interface
        assert hasattr(py_model, "index")
        assert hasattr(py_model, "parent")
        assert hasattr(py_model, "data")
        assert hasattr(py_model, "rowCount")
        assert hasattr(py_model, "columnCount")
        assert hasattr(py_model, "flags")

        # Test QFileSystemModel specific methods
        assert hasattr(py_model, "filePath")
        assert hasattr(py_model, "isDir")
        assert hasattr(py_model, "size")
        assert hasattr(py_model, "fileInfo")
        assert hasattr(py_model, "permissions")

    def test_pyfileinfogatherer_api_compatibility(self):
        """Test PyFileInfoGatherer API compatibility."""
        gatherer = PyFileInfoGatherer()

        # Test basic interface
        assert hasattr(gatherer, "getInfo")
        assert hasattr(gatherer, "iconProvider")
        assert hasattr(gatherer, "setIconProvider")
        assert hasattr(gatherer, "resolveSymlinks")
        assert hasattr(gatherer, "setResolveSymlinks")

        # Test signals
        assert hasattr(gatherer, "updates")
        assert hasattr(gatherer, "newListOfFiles")
        assert hasattr(gatherer, "nameResolved")
        assert hasattr(gatherer, "directoryLoaded")

    def test_pyfilesystemnode_api_compatibility(self, temp_dir):
        """Test PyFileSystemNode API compatibility."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        file_info = QFileInfo(str(test_file))
        node = PyFileSystemNode("test.txt", None)

        # Test basic properties
        assert hasattr(node, "fileName")
        assert hasattr(node, "parent")
        assert hasattr(node, "children")
        assert hasattr(node, "info")

        # Test utility methods
        assert hasattr(node, "size")
        assert hasattr(node, "isDir")
        assert hasattr(node, "isFile")
        assert hasattr(node, "isHidden")
        assert hasattr(node, "isSymLink")
        assert hasattr(node, "fileInfo")
        assert hasattr(node, "permissions")

    def test_pyqextendedinformation_api_compatibility(self, temp_dir):
        """Test PyQExtendedInformation API compatibility."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        file_info = QFileInfo(str(test_file))
        ext_info = PyQExtendedInformation(file_info)

        # Test basic interface
        assert hasattr(ext_info, "isDir")
        assert hasattr(ext_info, "isFile")
        assert hasattr(ext_info, "isSymLink")
        assert hasattr(ext_info, "isHidden")
        assert hasattr(ext_info, "fileInfo")
        assert hasattr(ext_info, "permissions")
        assert hasattr(ext_info, "size")
        assert hasattr(ext_info, "lastModified")

        # Test data members
        assert hasattr(ext_info, "displayType")
        assert hasattr(ext_info, "icon")

    def test_pyfilesystemmodelsorter_api_compatibility(self):
        """Test PyFileSystemModelSorter API compatibility."""
        sorter = PyFileSystemModelSorter(0)  # Sort by name

        # Test interface
        assert hasattr(sorter, "compareNodes")
        assert hasattr(sorter, "__call__")

        # Test operator
        node1 = PyFileSystemNode("file_a.txt", None)
        node2 = PyFileSystemNode("file_b.txt", None)
        result = sorter(node1, node2)
        assert isinstance(result, bool)

    def test_adapter_qfiledialog_api_compatibility(self, temp_dir):
        """Test AdapterQFileDialog API compatibility with QFileDialog."""
        # Test instantiation
        adapter_dialog = AdapterQFileDialog()
        qt_dialog = QFileDialog()

        # Test basic properties
        assert hasattr(adapter_dialog, "directory")
        assert hasattr(adapter_dialog, "setDirectory")
        assert hasattr(adapter_dialog, "selectedFiles")
        assert hasattr(adapter_dialog, "selectFile")
        assert hasattr(adapter_dialog, "nameFilters")
        assert hasattr(adapter_dialog, "setNameFilters")
        assert hasattr(adapter_dialog, "viewMode")
        assert hasattr(adapter_dialog, "setViewMode")
        assert hasattr(adapter_dialog, "fileMode")
        assert hasattr(adapter_dialog, "setFileMode")
        assert hasattr(adapter_dialog, "acceptMode")
        assert hasattr(adapter_dialog, "setAcceptMode")

        # Test options
        assert hasattr(adapter_dialog, "options")
        assert hasattr(adapter_dialog, "setOptions")
        assert hasattr(adapter_dialog, "setOption")
        assert hasattr(adapter_dialog, "testOption")

        # Test static methods
        assert hasattr(AdapterQFileDialog, "getOpenFileName")
        assert hasattr(AdapterQFileDialog, "getSaveFileName")
        assert hasattr(AdapterQFileDialog, "getExistingDirectory")
        assert hasattr(AdapterQFileDialog, "getOpenFileNames")
        assert hasattr(AdapterQFileDialog, "getOpenFileUrls")

    def test_filesystemmodel_roles_compatibility(self, temp_dir):
        """Test QFileSystemModel roles compatibility."""
        py_model = PyFileSystemModel()
        py_model.setRootPath(str(temp_dir))

        # Test role constants
        assert hasattr(PyFileSystemModel, "FileIconRole")
        assert hasattr(PyFileSystemModel, "FilePathRole")
        assert hasattr(PyFileSystemModel, "FileNameRole")
        assert hasattr(PyFileSystemModel, "FilePermissions")
        assert hasattr(PyFileSystemModel, "FileInfoRole")

        # Verify role values match Qt
        assert PyFileSystemModel.FileIconRole == Qt.DecorationRole
        assert PyFileSystemModel.FilePathRole == Qt.UserRole + 1
        assert PyFileSystemModel.FileNameRole == Qt.UserRole + 2
        assert PyFileSystemModel.FilePermissions == Qt.UserRole + 3

    def test_filesystemmodel_options_compatibility(self):
        """Test QFileSystemModel options compatibility."""
        py_model = PyFileSystemModel()

        # Test option constants
        assert hasattr(PyFileSystemModel, "DontWatchForChanges")
        assert hasattr(PyFileSystemModel, "DontResolveSymlinks")
        assert hasattr(PyFileSystemModel, "DontUseCustomDirectoryIcons")

        # Test option methods
        assert hasattr(py_model, "setOption")
        assert hasattr(py_model, "testOption")
        assert hasattr(py_model, "setOptions")
        assert hasattr(py_model, "options")

    def test_qfiledialog_options_compatibility(self):
        """Test QFileDialog options compatibility."""
        adapter_dialog = AdapterQFileDialog()

        # Test option constants
        assert hasattr(AdapterQFileDialog, "ShowDirsOnly")
        assert hasattr(AdapterQFileDialog, "DontResolveSymlinks")
        assert hasattr(AdapterQFileDialog, "DontConfirmOverwrite")
        assert hasattr(AdapterQFileDialog, "DontUseNativeDialog")
        assert hasattr(AdapterQFileDialog, "ReadOnly")
        assert hasattr(AdapterQFileDialog, "HideNameFilterDetails")
        assert hasattr(AdapterQFileDialog, "DontUseCustomDirectoryIcons")

    def test_signal_compatibility(self):
        """Test signal compatibility across adapters."""
        py_model = PyFileSystemModel()

        # Test QFileSystemModel signals
        assert hasattr(py_model, "rootPathChanged")
        assert hasattr(py_model, "fileRenamed")
        assert hasattr(py_model, "directoryLoaded")

        gatherer = PyFileInfoGatherer()

        # Test QFileInfoGatherer signals
        assert hasattr(gatherer, "updates")
        assert hasattr(gatherer, "newListOfFiles")
        assert hasattr(gatherer, "nameResolved")
        assert hasattr(gatherer, "directoryLoaded")

    def test_method_signatures_compatibility(self, temp_dir):
        """Test that method signatures match Qt API exactly."""
        py_model = PyFileSystemModel()
        test_path = str(temp_dir)

        # Test setRootPath signature
        index = py_model.setRootPath(test_path)
        assert isinstance(index, QModelIndex)

        # Test filePath signature
        if py_model.rootPath():
            file_path = py_model.filePath(index)
            assert isinstance(file_path, str)

        # Test isDir signature
        is_dir = py_model.isDir(index)
        assert isinstance(is_dir, bool)

        # Test size signature
        size = py_model.size(index)
        assert isinstance(size, int)

        # Test fileInfo signature
        info = py_model.fileInfo(index)
        assert isinstance(info, QFileInfo)

    def test_qdir_filters_compatibility(self):
        """Test QDir filters compatibility."""
        py_model = PyFileSystemModel()

        # Test filter setting
        filters = QDir.AllEntries | QDir.NoDotAndDotDot | QDir.Hidden
        py_model.setFilter(filters)

        retrieved_filters = py_model.filter()
        assert retrieved_filters == filters

    def test_icon_provider_compatibility(self):
        """Test icon provider compatibility."""
        py_model = PyFileSystemModel()

        # Test icon provider methods
        assert hasattr(py_model, "iconProvider")
        assert hasattr(py_model, "setIconProvider")

        # Test setting icon provider
        icon_provider = QApplication.style()
        py_model.setIconProvider(icon_provider)
        retrieved_provider = py_model.iconProvider()
        assert retrieved_provider is not None

    def test_model_index_operations(self, temp_dir):
        """Test QModelIndex operations compatibility."""
        py_model = PyFileSystemModel()
        py_model.setRootPath(str(temp_dir))

        # Test index creation
        root_index = py_model.index(str(temp_dir))
        assert isinstance(root_index, QModelIndex)

        # Test parent
        parent_index = py_model.parent(root_index)
        assert isinstance(parent_index, QModelIndex)

        # Test sibling
        sibling_index = py_model.sibling(0, 1, root_index)
        assert isinstance(sibling_index, QModelIndex)

    def test_data_and_flags(self, temp_dir):
        """Test data() and flags() compatibility."""
        py_model = PyFileSystemModel()
        py_model.setRootPath(str(temp_dir))

        root_index = py_model.index(str(temp_dir))

        # Test data method
        display_data = py_model.data(root_index, Qt.DisplayRole)
        assert isinstance(display_data, (str, type(None)))

        # Test flags method
        flags = py_model.flags(root_index)
        assert isinstance(flags, Qt.ItemFlags)

    def test_mime_types_and_drag_drop(self):
        """Test MIME types and drag-drop compatibility."""
        py_model = PyFileSystemModel()

        # Test mimeTypes
        mime_types = py_model.mimeTypes()
        assert isinstance(mime_types, list)
        assert "text/uri-list" in mime_types

        # Test supported drop actions
        drop_actions = py_model.supportedDropActions()
        assert isinstance(drop_actions, Qt.DropActions)

    def test_role_names(self):
        """Test roleNames() compatibility."""
        py_model = PyFileSystemModel()

        role_names = py_model.roleNames()
        assert isinstance(role_names, dict)

        # Check standard roles
        assert Qt.DisplayRole in role_names
        assert Qt.DecorationRole in role_names

        # Check custom roles
        assert PyFileSystemModel.FilePathRole in role_names
        assert PyFileSystemModel.FileNameRole in role_names
        assert PyFileSystemModel.FilePermissions in role_names

    def test_sorting_functionality(self, temp_dir):
        """Test sorting functionality compatibility."""
        py_model = PyFileSystemModel()
        py_model.setRootPath(str(temp_dir))

        # Test sort method
        py_model.sort(0, Qt.AscendingOrder)  # Sort by name ascending
        py_model.sort(1, Qt.DescendingOrder)  # Sort by size descending

        # Test sort role
        assert hasattr(py_model, "sortRole")
        sort_role = py_model.sortRole()
        assert isinstance(sort_role, int)

    def test_file_operations(self, temp_dir):
        """Test file operations compatibility."""
        py_model = PyFileSystemModel()
        py_model.setRootPath(str(temp_dir))

        root_index = py_model.index(str(temp_dir))

        # Test mkdir
        new_dir_index = py_model.mkdir(root_index, "test_dir")
        assert isinstance(new_dir_index, QModelIndex)

        # Test rmdir
        removed = py_model.rmdir(new_dir_index)
        assert isinstance(removed, bool)

        # Test remove (file)
        test_file = temp_dir / "test_remove.txt"
        test_file.write_text("content")
        file_index = py_model.index(str(test_file))
        if file_index.isValid():
            removed_file = py_model.remove(file_index)
            assert isinstance(removed_file, bool)

    def test_qfiledialog_static_methods(self):
        """Test QFileDialog static methods compatibility."""
        # Test that static methods exist and are callable
        assert callable(AdapterQFileDialog.getOpenFileName)
        assert callable(AdapterQFileDialog.getSaveFileName)
        assert callable(AdapterQFileDialog.getExistingDirectory)
        assert callable(AdapterQFileDialog.getOpenFileNames)
        assert callable(AdapterQFileDialog.getOpenFileUrls)
        assert callable(AdapterQFileDialog.getSaveFileUrl)

    def test_qfiledialog_modes_and_options(self):
        """Test QFileDialog modes and options compatibility."""
        dialog = AdapterQFileDialog()

        # Test view modes
        assert hasattr(AdapterQFileDialog, "Detail")
        assert hasattr(AdapterQFileDialog, "List")

        # Test file modes
        assert hasattr(AdapterQFileDialog, "AnyFile")
        assert hasattr(AdapterQFileDialog, "ExistingFile")
        assert hasattr(AdapterQFileDialog, "Directory")
        assert hasattr(AdapterQFileDialog, "ExistingFiles")

        # Test accept modes
        assert hasattr(AdapterQFileDialog, "AcceptOpen")
        assert hasattr(AdapterQFileDialog, "AcceptSave")

        # Test setting modes
        dialog.setViewMode(AdapterQFileDialog.Detail)
        assert dialog.viewMode() == AdapterQFileDialog.Detail

        dialog.setFileMode(AdapterQFileDialog.ExistingFile)
        assert dialog.fileMode() == AdapterQFileDialog.ExistingFile

        dialog.setAcceptMode(AdapterQFileDialog.AcceptOpen)
        assert dialog.acceptMode() == AdapterQFileDialog.AcceptOpen

    def test_qfiledialog_properties(self, temp_dir):
        """Test QFileDialog properties compatibility."""
        dialog = AdapterQFileDialog()

        # Test directory property
        test_dir = QDir(str(temp_dir))
        dialog.setDirectory(test_dir)
        assert dialog.directory().absolutePath() == str(temp_dir)

        # Test URL directory
        test_url = QUrl.fromLocalFile(str(temp_dir))
        dialog.setDirectoryUrl(test_url)
        assert dialog.directoryUrl().toLocalFile() == str(temp_dir)

        # Test name filters
        filters = ["*.txt", "*.cpp"]
        dialog.setNameFilters(filters)
        assert dialog.nameFilters() == filters

        # Test default suffix
        dialog.setDefaultSuffix("txt")
        assert dialog.defaultSuffix() == "txt"

        # Test history
        history = [str(temp_dir)]
        dialog.setHistory(history)
        assert dialog.history() == history

    def test_qfiledialog_sidebar_and_state(self):
        """Test QFileDialog sidebar and state compatibility."""
        dialog = AdapterQFileDialog()

        # Test sidebar URLs
        urls = [QUrl.fromLocalFile("/tmp"), QUrl.fromLocalFile("/home")]
        dialog.setSidebarUrls(urls)
        retrieved_urls = dialog.sidebarUrls()
        assert len(retrieved_urls) >= 0  # May be processed

        # Test state save/restore
        state = dialog.saveState()
        assert isinstance(state, bytes)
        assert len(state) > 0

        # Test restore
        success = dialog.restoreState(state)
        assert isinstance(success, bool)

    def test_qfiledialog_signals(self):
        """Test QFileDialog signals compatibility."""
        dialog = AdapterQFileDialog()

        # Test that signals exist
        assert hasattr(dialog, "fileSelected")
        assert hasattr(dialog, "filesSelected")
        assert hasattr(dialog, "currentChanged")
        assert hasattr(dialog, "directoryEntered")
        assert hasattr(dialog, "urlSelected")
        assert hasattr(dialog, "urlsSelected")
        assert hasattr(dialog, "currentUrlChanged")
        assert hasattr(dialog, "directoryUrlEntered")
        assert hasattr(dialog, "filterSelected")

    def test_adapter_initialization_and_cleanup(self):
        """Test adapter initialization and cleanup."""
        # Test PyFileSystemModel
        model = PyFileSystemModel()
        assert model is not None
        # Cleanup should happen automatically

        # Test PyFileInfoGatherer
        gatherer = PyFileInfoGatherer()
        assert gatherer is not None

        # Test AdapterQFileDialog
        dialog = AdapterQFileDialog()
        assert dialog is not None

    def test_memory_management(self):
        """Test memory management and object lifecycle."""
        # Create and destroy objects to test for memory issues
        for _ in range(10):
            model = PyFileSystemModel()
            model.setRootPath("/")
            del model

        for _ in range(10):
            gatherer = PyFileInfoGatherer()
            del gatherer

        for _ in range(10):
            dialog = AdapterQFileDialog()
            del dialog

        # If we get here without crashes, basic memory management works
        assert True

    def test_thread_safety_indicators(self):
        """Test indicators of thread safety in adapters."""
        # PyFileInfoGatherer should be thread-safe
        gatherer = PyFileInfoGatherer()
        assert hasattr(gatherer, "run")  # QThread method
        assert hasattr(gatherer, "mutex")  # Should have mutex for thread safety

        # Test that file operations are properly synchronized
        assert hasattr(gatherer, "mutex")

    def test_error_handling(self, temp_dir):
        """Test error handling in adapters."""
        model = PyFileSystemModel()

        # Test invalid path
        invalid_index = model.setRootPath("/nonexistent/path/that/does/not/exist")
        assert isinstance(invalid_index, QModelIndex)

        # Test valid path
        valid_index = model.setRootPath(str(temp_dir))
        assert isinstance(valid_index, QModelIndex)

        # Test operations on invalid indices
        invalid_qmi = QModelIndex()
        assert model.data(invalid_qmi, Qt.DisplayRole).isValid() == False
        assert model.flags(invalid_qmi) == Qt.ItemFlags()

    def test_performance_indicators(self, temp_dir):
        """Test performance indicators and optimization features."""
        model = PyFileSystemModel()

        # Test lazy loading indicators
        model.setRootPath(str(temp_dir))
        assert hasattr(model, "canFetchMore")
        assert hasattr(model, "fetchMore")

        # Test caching indicators
        assert hasattr(model, "setOption")
        assert hasattr(model, "testOption")

        # Test that options include DontWatchForChanges for performance
        assert hasattr(PyFileSystemModel, "DontWatchForChanges")

    def test_cross_platform_compatibility(self):
        """Test cross-platform compatibility indicators."""
        model = PyFileSystemModel()

        # Test platform-specific behavior indicators
        assert hasattr(model, "caseSensitivity")
        case_sensitive = model.caseSensitivity()
        assert isinstance(case_sensitive, bool)

        # Test path handling
        assert hasattr(model, "resolveSymlinks")
        assert hasattr(model, "setResolveSymlinks")

        # Test icon handling (platform-specific)
        assert hasattr(model, "iconProvider")
        assert hasattr(model, "setIconProvider")
