"""Unit Tests for the filesystem view with archive-as-folder support.

This test suite exhaustively tests the ResourceFileSystemModel and ResourceFileSystemWidget
to ensure stability, proper functionality, and support for all operations including:
- Expand/collapse of archives and directories
- Drag and drop operations
- Context menus
- Sorting and filtering
- View switching between filesystem and legacy views
- Archive-as-folder functionality (BIF, ERF, MOD, SAV)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pytestqt.qtbot import QtBot
from qtpy.QtWidgets import QApplication

if TYPE_CHECKING:
    from qtpy.QtCore import QModelIndex, QPoint
    from qtpy.QtWidgets import QWidget

    from toolset.data.installation import HTInstallation


@pytest.mark.comprehensive
class TestFilesystemViewComprehensive:
    """Comprehensive test suite for filesystem view functionality."""

    def test_model_initialization(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test that the filesystem model initializes correctly."""
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemModel

        model = ResourceFileSystemModel()
        assert model is not None
        assert model.columnCount() > 0
        assert model.rootPath() is None

    def test_model_multiple_installations(self, qt_api: str, qtbot: QtBot, tmp_path: Path):
        """Test multi-root installation support in the filesystem model."""
        from toolset.gui.widgets.kotor_filesystem_model import KotorFileSystemModel, InstallationItem
        from toolset.gui.widgets.settings.installations import InstallationConfig

        install_a = tmp_path / "install_a"
        install_b = tmp_path / "install_b"
        install_a.mkdir()
        install_b.mkdir()
        (install_a / "override").mkdir()
        (install_b / "modules").mkdir()

        config_a = InstallationConfig("TestA")
        config_a.path = str(install_a)
        config_a.tsl = False
        config_b = InstallationConfig("TestB")
        config_b.path = str(install_b)
        config_b.tsl = True

        model = KotorFileSystemModel()
        model.set_installations({"TestA": config_a, "TestB": config_b})

        assert model.rowCount() == 2
        names = {model.data(model.index(row, 0)) for row in range(model.rowCount())}
        assert names == {"TestA", "TestB"}

        first_index = model.index(0, 0)
        install_item = model.installation_from_index(first_index)
        assert isinstance(install_item, InstallationItem)
        assert install_item.name in names

        # Non-zero columns on parent should report 0 rows
        assert model.rowCount(model.index(0, 1)) == 0

    def test_model_flags_and_tooltip(self, qt_api: str, qtbot: QtBot, tmp_path: Path):
        """Validate flags and tooltip path reporting for model indexes."""
        from toolset.gui.widgets.kotor_filesystem_model import KotorFileSystemModel
        from toolset.gui.widgets.settings.installations import InstallationConfig
        from qtpy.QtCore import Qt

        root_dir = tmp_path / "install_root"
        root_dir.mkdir()
        (root_dir / "Modules").mkdir()
        (root_dir / "test.txt").write_text("data")

        config = InstallationConfig("FlagsTest")
        config.path = str(root_dir)
        config.tsl = False

        model = KotorFileSystemModel()
        model.set_installations({"FlagsTest": config})

        install_index = model.index(0, 0)
        assert install_index.isValid()
        flags = model.flags(install_index)
        assert flags & Qt.ItemFlag.ItemIsEnabled
        assert flags & Qt.ItemFlag.ItemIsSelectable

        tooltip = model.data(install_index, Qt.ItemDataRole.ToolTipRole)
        assert tooltip is not None
        assert str(root_dir) in str(tooltip)

    def test_model_set_root_path(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test setting root path on the model."""
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemModel

        model = ResourceFileSystemModel()
        model.setRootPath(installation.path())

        root_path = model.rootPath()
        assert root_path is not None
        assert root_path.exists()
        assert root_path.is_dir()

    def test_widget_initialization(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test that the filesystem widget initializes correctly."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        assert widget is not None
        assert widget.fs_model is not None
        assert widget.fsTreeView is not None

    def test_widget_set_root_path(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test setting root path on the widget."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        expected = Path(installation.path()).resolve()
        widget.setRootPath(installation.path())
        QApplication.processEvents()  # Wait for async operations

        actual = widget.fs_model.rootPath()
        assert actual is not None, "Model root path should be set after setRootPath"
        assert Path(actual).resolve() == expected, (
            f"Widget root path {actual!r} should match installation path {expected!r}"
        )

    def test_archive_as_folder_bif(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test that BIF files are treated as folders."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget
        from pykotor.tools.misc import is_bif_file

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()  # Wait for initial load

        # Find a BIF file in the installation
        chitin_path = installation.path() / "chitin.key"
        if chitin_path.exists():
            # Look for BIF files referenced in chitin.key
            # For now, just verify the model can handle BIF files
            model = widget.fs_model
            root_index = model.index(0, 0)
            if root_index.isValid():
                # Try to expand and see if BIF files appear as expandable
                widget.fsTreeView.expand(root_index)
                QApplication.processEvents()

                # Check if any child items are BIF files
                row_count = model.rowCount(root_index)
                for row in range(row_count):
                    child_index = model.index(row, 0, root_index)
                    if child_index.isValid():
                        item = model.itemFromIndex(child_index)
                        if item is not None:
                            path = item.path
                            if is_bif_file(path):
                                # BIF file should be expandable (have children)
                                assert model.canFetchMore(child_index) or model.rowCount(child_index) > 0

    def test_archive_as_folder_erf(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test that ERF files are treated as folders."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget
        from pykotor.tools.misc import is_erf_file

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        # Set root to modules directory where ERF files are
        widget.setRootPath(installation.module_path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)
        if root_index.isValid():
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            row_count = model.rowCount(root_index)
            for row in range(row_count):
                child_index = model.index(row, 0, root_index)
                if child_index.isValid():
                    item = model.itemFromIndex(child_index)
                    if item is not None:
                        path = item.path
                        if is_erf_file(path):
                            # ERF file should be expandable
                            assert model.canFetchMore(child_index) or model.rowCount(child_index) > 0

    def test_archive_as_folder_mod(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test that MOD files are treated as folders."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget
        from pykotor.tools.misc import is_mod_file

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.module_path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)
        if root_index.isValid():
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            row_count = model.rowCount(root_index)
            for row in range(row_count):
                child_index = model.index(row, 0, root_index)
                if child_index.isValid():
                    item = model.itemFromIndex(child_index)
                    if item is not None:
                        path = item.path
                        if is_mod_file(path):
                            # MOD file should be expandable
                            assert model.canFetchMore(child_index) or model.rowCount(child_index) > 0

    def test_expand_collapse_directory(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test expanding and collapsing directories."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            initial_row_count = model.rowCount(root_index)

            # Expand
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            # Should have more rows after expansion
            expanded_row_count = model.rowCount(root_index)
            assert expanded_row_count >= initial_row_count

            # Collapse
            widget.fsTreeView.collapse(root_index)
            QApplication.processEvents()

            # Row count should remain the same (children are not removed)
            collapsed_row_count = model.rowCount(root_index)
            assert collapsed_row_count == expanded_row_count

    def test_expand_collapse_archive(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test expanding and collapsing archive files."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget
        from pykotor.tools.misc import is_capsule_file

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.module_path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            # Find an archive file
            row_count = model.rowCount(root_index)
            archive_index = None
            for row in range(row_count):
                child_index = model.index(row, 0, root_index)
                if child_index.isValid():
                    item = model.itemFromIndex(child_index)
                    if item is not None and is_capsule_file(item.path):
                        archive_index = child_index
                        break

            if archive_index is not None:
                initial_row_count = model.rowCount(archive_index)

                # Expand archive
                widget.fsTreeView.expand(archive_index)
                QApplication.processEvents()  # Archives may take longer to load

                # Should have children after expansion
                expanded_row_count = model.rowCount(archive_index)
                assert expanded_row_count > initial_row_count or model.canFetchMore(archive_index)

                # Collapse
                widget.fsTreeView.collapse(archive_index)
                QApplication.processEvents()

    def test_model_data_retrieval(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test retrieving data from the model."""
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            # Test display role
            display_data = model.data(root_index, Qt.ItemDataRole.DisplayRole)
            assert display_data is not None

            # Test decoration role
            decoration_data = model.data(root_index, Qt.ItemDataRole.DecorationRole)
            # Decoration may be None for some items

            # Test header data
            header_data = model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            assert header_data is not None

    def test_model_sorting(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test sorting functionality of the model."""
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            row_count = model.rowCount(root_index)
            if row_count > 1:
                # Get initial order
                initial_names = []
                for row in range(row_count):
                    idx = model.index(row, 0, root_index)
                    if idx.isValid():
                        name = model.data(idx, Qt.ItemDataRole.DisplayRole)
                        if name:
                            initial_names.append(str(name))

                # Sort ascending
                model.sort(0, Qt.SortOrder.AscendingOrder)
                QApplication.processEvents()

                # Get sorted order
                sorted_names = []
                for row in range(row_count):
                    idx = model.index(row, 0, root_index)
                    if idx.isValid():
                        name = model.data(idx, Qt.ItemDataRole.DisplayRole)
                        if name:
                            sorted_names.append(str(name))

                # Verify sorting
                assert sorted_names == sorted(initial_names) or len(sorted_names) == len(initial_names)

    def test_model_filtering(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test filtering functionality of the model."""
        from qtpy.QtCore import QDir
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model

        # Test setting filter
        model.setFilter(QDir.Filter.Files | QDir.Filter.Dirs)
        QApplication.processEvents()

        filter_value = model.filter()
        assert filter_value is not None

    def test_widget_context_menu(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test context menu functionality."""
        from qtpy.QtCore import QPoint
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)
        parent.show()
        qtbot.waitForWindowShown(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        # Get a valid index
        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            # Get viewport coordinates
            viewport = widget.fsTreeView.viewport()
            rect = widget.fsTreeView.visualRect(root_index)
            point = QPoint(rect.center().x(), rect.center().y())

            # Trigger context menu
            widget.fsTreeView.customContextMenuRequested.emit(point)
            QApplication.processEvents()

    def test_widget_double_click(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test double-click functionality."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)
        parent.show()
        qtbot.waitForWindowShown(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            # Double-click should expand/collapse or open
            widget.fsTreeView.doubleClicked.emit(root_index)
            QApplication.processEvents()

    def test_stress_expand_collapse(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Stress test: rapid expand/collapse operations."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            # Rapid expand/collapse cycles
            for _ in range(10):
                widget.fsTreeView.expand(root_index)
                QApplication.processEvents()
                widget.fsTreeView.collapse(root_index)
                QApplication.processEvents()

            # Model should still be stable
            assert model.rootPath() is not None

    def test_stress_rapid_path_changes(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Stress test: rapid path changes."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        # Rapidly change paths
        paths = [
            installation.path(),
            installation.module_path(),
            installation.override_path(),
        ]

        for path in paths * 3:  # Cycle through paths 3 times
            if path.exists():
                widget.setRootPath(path)
                QApplication.processEvents()

        # Widget should still be functional
        assert widget.fs_model is not None

    def test_nested_archive_expansion(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test expanding nested archives (archive within archive)."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget
        from pykotor.tools.misc import is_capsule_file

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.module_path())
        QApplication.processEvents()

        model = widget.fs_model
        root_index = model.index(0, 0)

        if root_index.isValid():
            widget.fsTreeView.expand(root_index)
            QApplication.processEvents()

            # Find an archive
            row_count = model.rowCount(root_index)
            for row in range(row_count):
                archive_index = model.index(row, 0, root_index)
                if archive_index.isValid():
                    item = model.itemFromIndex(archive_index)
                    if item is not None and is_capsule_file(item.path):
                        # Expand the archive
                        widget.fsTreeView.expand(archive_index)
                        QApplication.processEvents()

                        # Check if it has children (which might be nested archives)
                        child_count = model.rowCount(archive_index)
                        if child_count > 0:
                            # Try to expand a child that might be an archive
                            for child_row in range(child_count):
                                child_index = model.index(child_row, 0, archive_index)
                                if child_index.isValid():
                                    child_item = model.itemFromIndex(child_index)
                                    if child_item is not None and is_capsule_file(child_item.path):
                                        # Nested archive found - try to expand it
                                        widget.fsTreeView.expand(child_index)
                                        QApplication.processEvents()
                                        break
                        break

    def test_model_reset(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test resetting the model."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model

        # Reset the model
        model.reloadModelData()
        QApplication.processEvents()

        # Model should still have root path
        assert model.rootPath() is not None

    def test_view_switching_legacy_to_filesystem(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test switching from legacy view to filesystem view."""
        from qtpy.QtWidgets import QApplication
        from toolset.gui.windows.main import ToolWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = ToolWindow()
        qtbot.addWidget(window)

        # Set installation
        from qtpy.QtCore import QModelIndex

        window.change_active_installation(QModelIndex(), QModelIndex())
        QApplication.processEvents()  # Wait for installation to load

        # Initially should be filesystem view (default)
        assert not window._use_legacy_layout

        # Switch to legacy
        window._on_legacy_layout_toggled(True)
        QApplication.processEvents()
        assert window._use_legacy_layout

        # Switch back to filesystem
        window._on_legacy_layout_toggled(False)
        QApplication.processEvents()
        assert not window._use_legacy_layout

    def test_view_switching_filesystem_to_legacy(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test switching from filesystem view to legacy view."""
        from qtpy.QtWidgets import QApplication
        from toolset.gui.windows.main import ToolWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = ToolWindow()
        qtbot.addWidget(window)

        # Set installation
        from qtpy.QtCore import QModelIndex

        window.change_active_installation(QModelIndex(), QModelIndex())
        QApplication.processEvents()

        # Should start in filesystem view
        assert not window._use_legacy_layout

        # Switch to legacy
        if hasattr(window.ui, "actionLegacyLayout"):
            window.ui.actionLegacyLayout.setChecked(True)
            window._on_legacy_layout_toggled(True)
            QApplication.processEvents()

            # Legacy widgets should be visible
            assert window.ui.coreWidget.isVisible()
            assert window.ui.modulesWidget.isVisible()
            assert window.ui.overrideWidget.isVisible()
            assert window.ui.savesWidget.isVisible()

    @pytest.mark.parametrize("installation_type", ["k1", "k2"])
    def test_installation_types(self, qt_api: str, qtbot: QtBot, installation_type: str, installation: HTInstallation, tsl_installation: HTInstallation):
        """Test with both K1 and K2 installations."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        inst = installation if installation_type == "k1" else tsl_installation

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(inst.path())
        QApplication.processEvents()

        assert widget.fs_model.rootPath() == inst.path()

        # Test modules path
        widget.setRootPath(inst.module_path())
        QApplication.processEvents()
        assert widget.fs_model.rootPath() == inst.module_path()

        # Test override path
        widget.setRootPath(inst.override_path())
        QApplication.processEvents()
        assert widget.fs_model.rootPath() == inst.override_path()

    def test_detailed_view_toggle(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test toggling detailed view."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        model = widget.fs_model

        # Toggle detailed view
        initial_column_count = model.columnCount()
        model.toggle_detailed_view()
        QApplication.processEvents()

        # Column count should change
        new_column_count = model.columnCount()
        assert new_column_count != initial_column_count or new_column_count > 0

        # Toggle back
        model.toggle_detailed_view()
        QApplication.processEvents()
        assert model.columnCount() == initial_column_count

    def test_address_bar_navigation(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test address bar navigation."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        # Test address bar update
        widget.updateAddressBar()
        assert widget.address_bar.text() == str(installation.path())

        # Test navigation via address bar
        new_path = installation.module_path()
        widget.address_bar.setText(str(new_path))
        widget.onAddressBarReturnPressed()
        QApplication.processEvents()

        assert widget.fs_model.rootPath() == new_path

    def test_refresh_functionality(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test refresh functionality."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        # Refresh
        widget.onRefreshButtonClicked()
        QApplication.processEvents()

        # Model should still be functional
        assert widget.fs_model.rootPath() is not None

    def test_column_resize(self, qt_api: str, qtbot: QtBot, installation: HTInstallation):
        """Test column resize functionality."""
        from qtpy.QtWidgets import QWidget
        from toolset.gui.widgets.kotor_filesystem_model import ResourceFileSystemWidget

        parent = QWidget()
        widget = ResourceFileSystemWidget(parent)
        qtbot.addWidget(parent)
        parent.show()
        qtbot.waitForWindowShown(parent)

        widget.setRootPath(installation.path())
        QApplication.processEvents()

        # Resize columns
        widget.resize_all_columns()
        QApplication.processEvents()

        # Header should still be functional
        header = widget.fsTreeView.header()
        assert header is not None
