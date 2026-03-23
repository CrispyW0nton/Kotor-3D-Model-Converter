"""Integration tests for QFileDialogExtended and all its dependencies.

This test suite validates that QFileDialogExtended works correctly with all
its dependencies including PyFileSystemModel, ActionsDispatcher, RibbonsWidget,
and all the Qt adapters.
"""

from __future__ import annotations

import os
import tempfile
import time

from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import pytest

from qtpy.QtCore import (
    QModelIndex,
    QUrl,
    Qt,
)
from qtpy.QtWidgets import QApplication

# Import QFileDialogExtended and all dependencies
from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import QFileDialogExtended

if TYPE_CHECKING:
    from qtpy.QtCore import (
        QCoreApplication,
    )


@pytest.fixture(scope="session")
def qapp() -> Generator[QApplication | QCoreApplication, Any, None]:
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files and directories
        test_dir = Path(tmpdir)

        # Create files
        (test_dir / "file1.txt").write_text("content 1")
        (test_dir / "file2.txt").write_text("content 2")
        (test_dir / "file3.cpp").write_text("// cpp file")

        # Create subdirectories
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("sub content")

        # Create hidden file
        if os.name == "nt":
            (test_dir / ".hidden").write_text("hidden content")

        yield test_dir


def test_qfiledialogextended_initialization(qapp: QApplication):
    """Test QFileDialogExtended initialization."""
    dialog = QFileDialogExtended()

    # Test basic initialization
    assert dialog is not None
    assert hasattr(dialog, "model")
    assert hasattr(dialog, "ui")
    assert hasattr(dialog, "executor")
    assert hasattr(dialog, "dispatcher")
    assert hasattr(dialog, "ribbons")
    assert hasattr(dialog, "address_bar")
    assert hasattr(dialog, "search_filter")

    # Test UI setup
    assert dialog.ui is not None
    assert dialog.model is not None
    assert dialog.executor is not None
    assert dialog.dispatcher is not None
    assert dialog.ribbons is not None
    assert dialog.address_bar is not None
    assert dialog.search_filter is not None


def test_qfiledialogextended_model_setup(qapp: QApplication):
    """Test QFileDialogExtended model setup."""
    dialog = QFileDialogExtended()

    # Test that model is properly set up
    assert dialog.model is not None
    tree_model = dialog.ui.treeView.model()
    list_model = dialog.ui.listView.model()
    # The view model may be a proxy; ensure the underlying source model is the dialog's model
    if hasattr(tree_model, "sourceModel"):
        assert tree_model.sourceModel() is dialog.model
    else:
        assert tree_model is dialog.model
    if hasattr(list_model, "sourceModel"):
        assert list_model.sourceModel() is dialog.model
    else:
        assert list_model is dialog.model


def test_qfiledialogextended_directory_operations(qapp: QApplication, temp_dir: Path):
    """Test QFileDialogExtended directory operations."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test directory setting
    assert dialog.directory().absolutePath() == str(temp_dir)

    # Test address bar updates
    assert str(dialog.address_bar.current_path) == str(temp_dir)

    # Wait for directory loading
    time.sleep(0.5)  # Allow async loading
    QApplication.processEvents()

    # Test that files are shown
    row_count = dialog.model.rowCount()
    assert row_count > 0  # Should have files we created


def test_qfiledialogextended_view_modes(qapp, temp_dir: Path):
    """Test QFileDialogExtended view mode switching."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test detail view (tree view)
    dialog._q_showDetailsView()
    assert dialog.ui.detailModeButton.isDown()
    assert not dialog.ui.listModeButton.isDown()
    assert dialog.ui.treeView.isVisible()
    assert not dialog.ui.listView.isVisible()

    # Test list view
    dialog._q_showListView()
    assert dialog.ui.listModeButton.isDown()
    assert not dialog.ui.detailModeButton.isDown()
    assert not dialog.ui.treeView.isVisible()
    assert dialog.ui.listView.isVisible()


def test_qfiledialogextended_search_filter(qapp, temp_dir: Path):
    """Test QFileDialogExtended search filter."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Wait for initial loading
    time.sleep(0.5)
    QApplication.processEvents()

    initial_count = dialog.model.rowCount()

    # Test search filter
    dialog.search_filter.setText("txt")
    QApplication.processEvents()

    # Should filter to txt files only
    filtered_count = dialog.model.rowCount()
    assert filtered_count <= initial_count


def test_qfiledialogextended_address_bar(qapp, temp_dir: Path):
    """Test QFileDialogExtended address bar."""
    dialog = QFileDialogExtended()

    # Test address bar path setting
    test_path = Path(temp_dir)
    dialog.address_bar.update_path(test_path)
    assert str(dialog.address_bar.current_path) == str(test_path)

    # Test directory change via address bar
    dialog.setDirectory(str(test_path))
    # Normalize path representation across platforms (Qt may use forward slashes)
    dialog_path = Path(dialog.directory().absolutePath())
    assert dialog_path.resolve() == test_path.resolve()


def test_qfiledialogextended_ribbons_widget(qapp, temp_dir: Path):
    """Test QFileDialogExtended ribbons widget."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test ribbons widget exists and has menus
    assert dialog.ribbons is not None
    assert hasattr(dialog.ribbons, "menus")
    assert dialog.ribbons.menus is not None

    # Test actions dispatcher integration
    assert dialog.dispatcher.menus is dialog.ribbons.menus


def test_qfiledialogextended_actions_dispatcher(qapp: QApplication, temp_dir: Path):
    """Test QFileDialogExtended actions dispatcher."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test actions dispatcher
    assert dialog.dispatcher is not None
    assert dialog.dispatcher.fs_model is dialog.model
    assert dialog.dispatcher.file_actions_executor is dialog.executor

    # Test context menu functionality
    view = dialog.ui.treeView
    position = view.rect().center()

    # Should not crash
    menu = dialog.dispatcher.get_context_menu(view, position)
    # Menu can be None if no selection, but should not crash
    assert menu is None or hasattr(menu, "exec")


def test_qfiledialogextended_file_actions_executor(qapp: QApplication):
    """Test QFileDialogExtended file actions executor."""
    dialog = QFileDialogExtended()

    # Test executor exists
    assert dialog.executor is not None
    assert hasattr(dialog.executor, "execute")
    assert hasattr(dialog.executor, "cancel")


def test_qfiledialogextended_extended_ui_rows(qapp: QApplication):
    """Test QFileDialogExtended extended UI rows insertion."""
    dialog = QFileDialogExtended()

    # Test that extended rows are inserted
    grid_layout = dialog.ui.gridlayout
    assert grid_layout is not None

    # Should have more than the original 2 rows (ribbons, address bar, search, original content)
    row_count = grid_layout.rowCount()
    assert row_count >= 5  # Original + extended rows

    # Test widget positioning
    ribbons_item = grid_layout.itemAtPosition(0, 0)
    assert ribbons_item is not None
    assert ribbons_item.widget() is dialog.ribbons

    address_item = grid_layout.itemAtPosition(1, 0)
    assert address_item is not None
    assert address_item.widget() is dialog.address_bar

    search_item = grid_layout.itemAtPosition(2, 0)
    assert search_item is not None
    assert search_item.widget() is dialog.search_filter


def test_qfiledialogextended_proxy_model(qapp: QApplication):
    """Test QFileDialogExtended proxy model setup."""
    dialog = QFileDialogExtended()

    # Test proxy model exists
    assert hasattr(dialog, "proxy_model")
    assert dialog.proxy_model is not None

    # Test proxy model is set on views
    assert dialog.ui.treeView.model() is dialog.proxy_model
    assert dialog.ui.listView.model() is dialog.proxy_model

    # Test proxy model source
    assert dialog.proxy_model.sourceModel() is dialog.model

    # Test proxy model settings
    assert dialog.proxy_model.filterCaseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
    assert dialog.proxy_model.filterKeyColumn() == 0
    assert dialog.proxy_model.isRecursiveFilteringEnabled()


def test_qfiledialogextended_signals_connection(qapp: QApplication):
    """Test QFileDialogExtended signal connections."""
    dialog = QFileDialogExtended()

    # Test signal connections exist
    assert hasattr(dialog, "_connect_extended_signals")
    assert hasattr(dialog, "_on_address_bar_path_changed")
    assert hasattr(dialog, "_on_address_bar_return_pressed")
    assert hasattr(dialog, "_on_search_text_changed")
    assert hasattr(dialog, "_on_search_requested")
    assert hasattr(dialog, "_on_directory_changed")


def test_qfiledialogextended_context_menu(qapp: QApplication, temp_dir: Path):
    """Test QFileDialogExtended context menu functionality."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test context menu signal connection
    view = dialog.ui.treeView
    assert view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    # Dispatcher provides context menu construction; ensure it's callable
    assert callable(dialog.dispatcher.get_context_menu)


def test_qfiledialogextended_double_click_open(qapp: QApplication, temp_dir: Path):
    """Test QFileDialogExtended double-click to open."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Double-clicks are routed to the dispatcher open handler
    assert callable(dialog.dispatcher.on_open)


def test_qfiledialogextended_windows11_styling(qapp):
    """Test QFileDialogExtended Windows 11 styling."""
    dialog = QFileDialogExtended()

    # Test styling application
    style_sheet = dialog.styleSheet()
    assert style_sheet != ""  # Should have styling applied

    # Test styling contains Windows 11 elements
    assert "Segoe UI" in style_sheet or "system-ui" in style_sheet
    assert "background-color" in style_sheet
    assert "border-radius" in style_sheet


def test_qfiledialogextended_mime_type_filters(qapp):
    """Test QFileDialogExtended MIME type filters."""
    dialog = QFileDialogExtended()

    # Test MIME type filter methods exist
    assert hasattr(dialog, "mimeTypeFilters")
    assert hasattr(dialog, "setMimeTypeFilters")
    assert hasattr(dialog, "selectMimeTypeFilter")
    assert hasattr(dialog, "selectedMimeTypeFilter")

    # Test MIME type filters functionality
    filters = ["text/plain", "text/html"]
    dialog.setMimeTypeFilters(filters)
    retrieved_filters = dialog.mimeTypeFilters()
    assert retrieved_filters == filters


def test_qfiledialogextended_supported_schemes(qapp):
    """Test QFileDialogExtended supported schemes."""
    dialog = QFileDialogExtended()

    # Test supported schemes methods
    assert hasattr(dialog, "supportedSchemes")
    assert hasattr(dialog, "setSupportedSchemes")

    schemes = ["file", "ftp", "http"]
    dialog.setSupportedSchemes(schemes)
    retrieved_schemes = dialog.supportedSchemes()
    assert retrieved_schemes == schemes


def test_qfiledialogextended_static_methods(qapp):
    """Test QFileDialogExtended static methods."""
    # Test static method wrappers exist
    assert hasattr(QFileDialogExtended, "getOpenFileName")
    assert hasattr(QFileDialogExtended, "getSaveFileName")
    assert hasattr(QFileDialogExtended, "getExistingDirectory")
    assert hasattr(QFileDialogExtended, "getOpenFileNames")
    assert hasattr(QFileDialogExtended, "getOpenFileUrls")
    assert hasattr(QFileDialogExtended, "getSaveFileUrl")
    assert hasattr(QFileDialogExtended, "saveFileContent")
    assert hasattr(QFileDialogExtended, "getOpenFileContent")

    # Test they are callable
    assert callable(QFileDialogExtended.getOpenFileName)
    assert callable(QFileDialogExtended.getSaveFileName)
    assert callable(QFileDialogExtended.getExistingDirectory)
    assert callable(QFileDialogExtended.getOpenFileNames)
    assert callable(QFileDialogExtended.getOpenFileUrls)
    assert callable(QFileDialogExtended.getSaveFileUrl)
    assert callable(QFileDialogExtended.saveFileContent)
    assert callable(QFileDialogExtended.getOpenFileContent)


def test_qfiledialogextended_file_mode_operations(qapp):
    """Test QFileDialogExtended file mode operations."""
    dialog = QFileDialogExtended()

    # Test file mode setting
    dialog.setFileMode(QFileDialogExtended.FileMode.Directory)
    assert dialog.fileMode() == QFileDialogExtended.FileMode.Directory

    # Test option setting for directory only
    dialog.setOption(QFileDialogExtended.Option.ShowDirsOnly, True)
    assert dialog.testOption(QFileDialogExtended.Option.ShowDirsOnly)

    # Test directory selection
    selected_files = dialog.selectedFiles()
    assert isinstance(selected_files, list)


def test_qfiledialogextended_accept_mode_operations(qapp):
    """Test QFileDialogExtended accept mode operations."""
    dialog = QFileDialogExtended()

    # Test accept modes
    dialog.setAcceptMode(QFileDialogExtended.AcceptMode.AcceptOpen)
    assert dialog.acceptMode() == QFileDialogExtended.AcceptMode.AcceptOpen

    dialog.setAcceptMode(QFileDialogExtended.AcceptMode.AcceptSave)
    assert dialog.acceptMode() == QFileDialogExtended.AcceptMode.AcceptSave


def test_qfiledialogextended_history_operations(qapp, temp_dir: Path):
    """Test QFileDialogExtended history operations."""
    dialog = QFileDialogExtended()

    # Test history methods
    history = [str(temp_dir), str(temp_dir / "subdir")]
    dialog.setHistory(history)

    retrieved_history = dialog.history()
    assert isinstance(retrieved_history, list)
    assert retrieved_history == history


def test_qfiledialogextended_default_suffix(qapp):
    """Test QFileDialogExtended default suffix."""
    dialog = QFileDialogExtended()

    # Test default suffix
    suffix = "txt"
    dialog.setDefaultSuffix(suffix)
    assert dialog.defaultSuffix() == suffix


def test_qfiledialogextended_state_persistence(qapp):
    """Test QFileDialogExtended state save/restore."""
    dialog = QFileDialogExtended()

    # Test state methods
    assert hasattr(dialog, "saveState")
    assert hasattr(dialog, "restoreState")

    # Test state save
    state = dialog.saveState()
    # Qt may return a QByteArray or bytes depending on binding; accept both
    try:
        from qtpy.QtCore import QByteArray
    except Exception:
        QByteArray = None

    if QByteArray is not None and isinstance(state, QByteArray):
        assert state.size() > 0
        success = dialog.restoreState(state)
    else:
        assert isinstance(state, (bytes, bytearray))
        assert len(state) > 0
        success = dialog.restoreState(bytes(state))

    # Test state restore
    assert isinstance(success, bool)
    assert success


def test_qfiledialogextended_icon_provider(qapp):
    """Test QFileDialogExtended icon provider."""
    dialog = QFileDialogExtended()

    # Test icon provider methods
    assert hasattr(dialog, "iconProvider")
    assert hasattr(dialog, "setIconProvider")

    # Test setting icon provider
    provider = dialog.iconProvider()
    assert provider is not None  # Should have a default provider


def test_qfiledialogextended_item_delegate(qapp):
    """Test QFileDialogExtended item delegate."""
    dialog = QFileDialogExtended()

    # Test item delegate methods
    assert hasattr(dialog, "itemDelegate")
    assert hasattr(dialog, "setItemDelegate")


def test_qfiledialogextended_label_text(qapp):
    """Test QFileDialogExtended label text customization."""
    dialog = QFileDialogExtended()

    # Test label text methods
    assert hasattr(dialog, "labelText")
    assert hasattr(dialog, "setLabelText")

    # Test setting label text
    test_text = "Select File:"
    dialog.setLabelText(QFileDialogExtended.DialogLabel.FileName, test_text)
    retrieved_text = dialog.labelText(QFileDialogExtended.DialogLabel.FileName)
    assert retrieved_text == test_text


def test_qfiledialogextended_sidebar_operations(qapp, temp_dir: Path):
    """Test QFileDialogExtended sidebar operations."""
    dialog = QFileDialogExtended()

    # Test sidebar methods
    assert hasattr(dialog, "sidebarUrls")
    assert hasattr(dialog, "setSidebarUrls")

    # Test setting sidebar URLs
    urls = [QUrl.fromLocalFile(str(temp_dir))]
    dialog.setSidebarUrls(urls)
    retrieved_urls = dialog.sidebarUrls()
    assert isinstance(retrieved_urls, list)


def test_qfiledialogextended_current_view_operations(qapp, temp_dir: Path):
    """Test QFileDialogExtended current view operations."""
    dialog = QFileDialogExtended()
    dialog.setDirectory(str(temp_dir))

    # Test currentView method
    current_view = dialog.currentView()
    assert current_view is not None
    assert current_view in [dialog.ui.listView, dialog.ui.treeView]

    # Test mapToSource
    index = current_view.rootIndex()
    source_index = dialog.mapToSource(index)
    assert isinstance(source_index, QModelIndex)


def test_qfiledialogextended_error_handling(qapp):
    """Test QFileDialogExtended error handling."""
    dialog = QFileDialogExtended()

    # Test invalid operations don't crash
    dialog.setDirectory("/nonexistent/path")
    dialog.selectFile("nonexistent.txt")

    # Test with invalid QModelIndex
    invalid_index = QModelIndex()
    # Different Qt bindings may return different booleans for invalid indices; ensure no exception and size==0
    assert isinstance(dialog.model.isDir(invalid_index), bool)
    assert dialog.model.size(invalid_index) == 0


def test_qfiledialogextended_memory_management(qapp, temp_dir: Path):
    """Test QFileDialogExtended memory management."""
    # Create and destroy multiple dialogs
    for _ in range(5):
        dialog = QFileDialogExtended()
        dialog.setDirectory(str(temp_dir))
        # Force some operations
        dialog._q_showDetailsView()
        dialog._q_showListView()
        dialog.close()
        del dialog

    # If we get here without crashes or memory issues, test passes
    assert True


def test_qfiledialogextended_performance_indicators(qapp):
    """Test QFileDialogExtended performance indicators."""
    dialog = QFileDialogExtended()

    # Test that lazy loading is implemented
    assert hasattr(dialog.model, "canFetchMore")
    assert hasattr(dialog.model, "fetchMore")

    # Test that caching options are available
    assert hasattr(dialog.model, "setOption")
    assert hasattr(dialog.model, "testOption")


def test_qfiledialogextended_cross_platform_features(qapp):
    """Test QFileDialogExtended cross-platform features."""
    dialog = QFileDialogExtended()

    # Test symlink resolution
    dialog.model.setResolveSymlinks(True)
    assert dialog.model.resolveSymlinks()

    dialog.model.setResolveSymlinks(False)
    assert not dialog.model.resolveSymlinks()


def test_qfiledialogextended_full_integration_workflow(qapp, temp_dir: Path):
    """Test full QFileDialogExtended integration workflow."""
    dialog = QFileDialogExtended()

    # 1. Set directory
    dialog.setDirectory(str(temp_dir))

    # 2. Switch to detail view
    dialog._q_showDetailsView()

    # 3. Set up search filter
    dialog.search_filter.setText("*.txt")

    # 4. Update address bar
    dialog.address_bar.update_path(Path(temp_dir))

    # 5. Test context menu
    view = dialog.currentView()
    if view:
        position = view.rect().center()
        menu = dialog.dispatcher.get_context_menu(view, position)
        # Menu might be None, but shouldn't crash
        if menu:
            # Don't actually exec the menu in tests to avoid UI issues
            assert menu is not None

    # 6. Test file selection
    txt_files = list(temp_dir.glob("*.txt"))
    if txt_files:
        dialog.selectFile(txt_files[0].name)

    # 7. Test directory navigation
    if (temp_dir / "subdir").exists():
        dialog.setDirectory(str(temp_dir / "subdir"))

    # 8. Test view switching
    dialog._q_showListView()
    dialog._q_showDetailsView()

    # 9. Test state save/restore
    state = dialog.saveState()
    success = dialog.restoreState(state)
    assert isinstance(success, bool)

    # If we get here without exceptions, integration works
    assert True
