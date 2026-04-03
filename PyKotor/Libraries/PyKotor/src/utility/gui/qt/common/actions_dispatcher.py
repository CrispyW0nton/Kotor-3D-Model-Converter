"""Utilities for preparing and dispatching file system-related UI actions.

This module defines ActionsDispatcher which prepares actions (rename, delete, copy/paste,
properties dialogs, open-in-terminal, etc.) and delegates execution to a FileActionsExecutor.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import platform

from enum import IntEnum
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Union, cast

from qtpy.QtCore import (
    QAbstractProxyModel,
    QByteArray,
    QDataStream,
    QDir,
    QIODevice,
    QMimeData,
    QSortFilterProxyModel,
    QUrl,
    Qt,
)
from qtpy.QtGui import QClipboard, QColor, QPalette, QValidator
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColumnView,
    QDialog,
    QFileDialog,
    QFileSystemModel,  # pyright: ignore[reportPrivateImportUsage]
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from utility.gui.qt.common.column_options_dialog import SetDefaultColumnsDialog
from utility.gui.qt.common.filesystem.file_properties_dialog import FilePropertiesDialog
from utility.gui.qt.common.filesystem.filename_validator import FileNameValidator
from utility.gui.qt.common.menu_definitions import FileExplorerMenus, MenuContext
from utility.gui.qt.common.tasks.actions_executor import FileActionsExecutor

try:
    importlib.util.find_spec("win32com")  # pyright: ignore[reportAttributeAccessIssue]
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

try:
    importlib.util.find_spec("comtypes")  # pyright: ignore[reportAttributeAccessIssue]
    HAS_COMTYPES = True
except ImportError:
    HAS_COMTYPES = False

if TYPE_CHECKING:
    from qtpy.QtCore import QModelIndex, QPoint
    from qtpy.QtWidgets import QMenu

    from utility.gui.qt.common.filesystem.file_properties_dialog import FileProperties


class DropEffect(IntEnum):
    """Enumeration of drag-and-drop effects for UI actions.

    Attributes:
        NONE: No drop effect.
        CUT: Cut operation effect.
        LINK: Link operation effect.
        COPY: Copy operation effect.
    """

    NONE = 0
    CUT = 2
    LINK = 4
    COPY = 5


class ActionsDispatcher:
    """Dispatches certain actions to the executor after preparing them.

    Actions defined here will need more context and preparation before they can call queue_task.
    The goal is to omit preparation whenever possible, to reduce overall complexity
    for simpler actions. However some will need clipboard context, input dialogs and other constructs.

    See FileExplorerActions for simpler action examples.
    """

    def __init__(
        self,
        fs_model: QFileSystemModel,
        dialog: QFileDialog,
        file_actions_executor: FileActionsExecutor | None = None,
    ):
        self.fs_model: QFileSystemModel = fs_model
        self.dialog: QFileDialog = dialog
        self.file_actions_executor: FileActionsExecutor = FileActionsExecutor() if file_actions_executor is None else file_actions_executor
        self.file_actions_executor.TaskCompleted.connect(self._handle_task_result)
        self.file_actions_executor.TaskFailed.connect(self._handle_task_error)
        RobustLogger().debug("Connected TaskCompleted signal to handle_task_result")
        self.menus: FileExplorerMenus = FileExplorerMenus()
        self.task_operations: dict[str, str] = {}
        self.setup_signals()

    def setup_signals(self):
        """Set up signal connections for menu actions using declarative definitions."""
        from utility.gui.qt.common.action_definitions import FileExplorerActions

        actions = FileExplorerActions()
        for action_key, definition in actions.ACTION_DEFINITIONS.items():
            action = actions.actions[action_key]
            action.triggered.connect(lambda checked=False, defn=definition: self._handle_action(defn, checked))

    def _handle_action(self, definition, checked: bool = False):
        """Handle action triggered from declarative definition."""
        # Call prepare function if specified
        if definition.prepare_func:
            prepare_method = getattr(self, definition.prepare_func, None)
            if prepare_method:
                prepare_method(**definition.extra_kwargs)
                return  # Prepare methods handle their own execution

        # Call handler function if specified
        if definition.handler_func:
            handler_method = getattr(self, definition.handler_func, None)
            if handler_method:
                handler_method(**definition.extra_kwargs)
                return

        # Queue task if operation specified
        if definition.operation:
            paths = self.get_selected_paths() if definition.operation in ["open_file", "get_properties", "open_terminal", "delete_items", "rename_item"] else []
            self.queue_task(definition.operation, *paths, **definition.extra_kwargs)

    def prepare_duplicate_finder(self):
        """Prepare duplicate finding in the current directory."""
        directory = self.get_current_directory()
        self.queue_task("find_duplicates", directory)

    def prepare_hash_generator(self):
        """Prepare hash generation for selected files."""
        selected_items = self.get_selected_paths()
        if not selected_items:
            return

        algorithms = ["MD5", "SHA1", "SHA256"]
        algorithm, ok = QInputDialog.getItem(self.dialog, "Hash Generator", "Select hash algorithm:", algorithms, 0, editable=False)
        if ok and algorithm:
            self.queue_task("generate_hashes", selected_items, algorithm)

    def prepare_permissions_editor(self):
        """Prepare permissions editing for selected files."""
        selected_items = self.get_selected_paths()
        if not selected_items:
            return

        self.queue_task("edit_permissions", selected_items)

    def prepare_file_shredder(self):
        """Prepare secure file deletion for selected files."""
        selected_items = self.get_selected_paths()
        if not selected_items:
            return

        confirm = QMessageBox.warning(
            self.dialog,
            "Confirm Secure Deletion",
            "Are you sure you want to securely delete the selected files? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.queue_task("shred_files", selected_items)

    def prepare_file_comparison(self):
        """Prepare file comparison for exactly two selected files."""
        selected_items = self.get_selected_paths()
        if len(selected_items) != 2:  # noqa: PLR2004
            QMessageBox.warning(self.dialog, "Invalid Selection", "Please select exactly two files for comparison.")
            return

        self.queue_task("compare_files", selected_items)

    def prepare_open_in_terminal(self):
        """Prepare opening the current directory in the system terminal."""
        current_dir = self.get_current_directory()
        self.queue_task("open_terminal", current_dir)

    def prepare_customize_context_menu(self):
        """Prepare the context menu customization dialog."""
        # This would typically open a dialog to customize the context menu.
        # For now, we'll just show a message.
        QMessageBox.information(self.dialog, "Customize Context Menu", "Context menu customization feature is not implemented yet.")

    def show_set_default_columns_dialog(self):
        """Show dialog to set default columns for the file dialog."""
        dialog = SetDefaultColumnsDialog(self.dialog)
        if dialog.exec():
            selected_columns = dialog.get_selected_columns()
            self.queue_task("set_default_columns", selected_columns)

    def size_columns_to_fit(self):
        """Size columns to fit contents in the current view."""
        view = self.get_current_view()
        if isinstance(view, QTableView):
            view.resizeColumnsToContents()
        elif isinstance(view, QTreeView):
            view_header = view.header()
            assert view_header is not None, "View header is None"
            for column in range(view_header.count()):
                view.resizeColumnToContents(column)
        elif isinstance(view, QHeaderView):
            view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        elif isinstance(view, QColumnView):
            view.setSizeAdjustPolicy(QColumnView.SizeAdjustPolicy.AdjustToContents)

    def toggle_item_checkboxes(self):
        """Toggle checkboxes in the current view's item delegate."""
        view: QAbstractItemView = self.get_current_view()
        delegate = view.itemDelegate()
        if not isinstance(delegate, QStyledItemDelegate):
            view.setItemDelegate(QStyledItemDelegate())
            delegate = view.itemDelegate()
            assert isinstance(delegate, QStyledItemDelegate)
        # Check if delegate has hasCheckBoxes attribute using try/except for strict type checking
        try:
            current_state = delegate.hasCheckBoxes
        except AttributeError:
            current_state = False
        delegate.setCheckBoxes(not current_state)
        view_viewport = view.viewport()
        assert view_viewport is not None, "View viewport is None"
        view_viewport.update()

    def get_current_directory(self) -> Path:
        """Get the current directory as a Path object."""
        return Path(self.fs_model.rootPath()).absolute()

    def confirm_deletion(self, items: list[Path]) -> bool:
        """Show a custom deletion confirmation dialog for the given items."""
        if not items:
            return False

        class CustomDeleteDialog(QDialog):
            """Custom dialog to confirm deletion of files/folders."""

            def __init__(self, parent: QWidget, items: list[Path]):
                super().__init__(parent)
                self.setWindowTitle("Confirm Deletion")
                self.setMinimumWidth(400)
                layout = QVBoxLayout(self)

                # Header
                header = QLabel("Are you sure you want to delete the following items?")
                header.setStyleSheet("font-weight: bold; font-size: 14px;")
                layout.addWidget(header)

                # Scrollable area for items
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                content = QWidget()
                content_layout = QVBoxLayout(content)

                for item in items:
                    item_label = QLabel(f'<a href="{item}">{item.name}</a>')
                    item_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                    item_label.setOpenExternalLinks(True)
                    content_layout.addWidget(item_label)

                scroll.setWidget(content)
                layout.addWidget(scroll)

                # Buttons
                button_layout = QHBoxLayout()
                delete_button = QPushButton("Delete")
                palette = delete_button.palette()
                palette.setColor(QPalette.ColorRole.Button, QColor(255, 77, 77))
                palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
                delete_button.setPalette(palette)
                delete_button.clicked.connect(self.accept)
                cancel_button = QPushButton("Cancel")
                cancel_button.clicked.connect(self.reject)
                button_layout.addWidget(delete_button)
                button_layout.addWidget(cancel_button)
                layout.addLayout(button_layout)

        dialog = CustomDeleteDialog(self.dialog, items)
        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted

    def get_selected_paths(self) -> list[Path]:
        """Get the currently selected file paths as Path objects."""
        return [Path(file) for file in self.dialog.selectedFiles()]

    def get_menu(self, index: QModelIndex) -> QMenu:
        """Get the context menu for a specific index."""
        shift_mod = Qt.KeyboardModifier.ShiftModifier
        shift_held = bool(QApplication.keyboardModifiers() & shift_mod) or bool(QApplication.queryKeyboardModifiers() & shift_mod)
        if not index.isValid():
            return self.menus.create_menu(context=MenuContext.EMPTY, shift=shift_held)
        proxy_model: QAbstractProxyModel | None = cast("Union[None, QAbstractProxyModel]", self.dialog.proxyModel())
        source_index: QModelIndex = index if proxy_model is None else proxy_model.mapToSource(index)
        if self.fs_model.isDir(source_index):
            return self.menus.create_menu(context=MenuContext.DIR, shift=shift_held)
        return self.menus.create_menu(context=MenuContext.FILE, shift=shift_held)

    def get_context_menu(self, view: QAbstractItemView, pos: QPoint) -> QMenu:
        """Get the context menu for the given view at the specified position."""
        view_selection_model = view.selectionModel()
        assert view_selection_model is not None, "View selection model is None"
        selected_indexes = view_selection_model.selectedIndexes()
        if not selected_indexes:
            return self.menus.create_menu(context=MenuContext.EMPTY)
        if len(selected_indexes) == 1:
            return self.get_menu(selected_indexes[0])

        # Multiple items selected
        shift_mod = Qt.KeyboardModifier.ShiftModifier
        shift_held = bool(QApplication.keyboardModifiers() & shift_mod)  # or bool(QApplication.queryKeyboardModifiers() & shift_mod)

        # Convert selection indexes to source indexes
        source_indexes: list[QModelIndex] = []
        for idx in selected_indexes:
            if not idx.isValid():
                continue
            model = idx.model()
            if isinstance(model, QAbstractProxyModel):
                source_indexes.append(model.mapToSource(idx))
            elif self.fs_model is not model:
                raise ValueError("Selected indexes are not from the same model")
            else:
                source_indexes.append(idx)

        all_dirs = all(self.fs_model.isDir(idx) for idx in source_indexes)
        all_files = all(not self.fs_model.isDir(idx) for idx in source_indexes)

        context = MenuContext.DIR if all_dirs else MenuContext.FILE if all_files else MenuContext.MIXED
        multi = len(source_indexes) > 1
        return self.menus.create_menu(context=context, shift=shift_held, multi=multi)

    def _handle_task_error(self, task_name: str, error: Exception):
        """Handle task failure by logging the error."""
        RobustLogger().error(f"Task '{task_name}' failed with error: {error}")

    def prepare_sort(self, column_name):
        """Prepare sorting by the given column name."""
        column_map: dict[str, int] = {}
        for column in range(self.fs_model.columnCount()):
            header = self.fs_model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            assert isinstance(header, str)
            column_map[header.casefold()] = column

        assert isinstance(column_name, str)
        if column_name.casefold() in column_map:
            self.toggle_sort_order()
        else:
            RobustLogger().warning(f"Unsupported sort column '{column_name}'")

    def get_current_view(self) -> QAbstractItemView:
        """Get the currently visible view (list or tree) in the file dialog."""
        for this_view in self.dialog.findChildren(QAbstractItemView):
            if not isinstance(this_view, QAbstractItemView):
                continue
            if this_view.isVisible() and this_view.isEnabled():
                return this_view
        raise RuntimeError("No visible view found")

    def toggle_sort_order(self):
        """Toggle the sort order of the current view between ascending and descending.

        Handles sorting for QSortFilterProxyModel, QTreeView, QTableView, and QHeaderView.
        For proxy models, updates the sort order directly on the model.
        For views, toggles the sort indicator and applies the new sort order to the view.
        Does nothing if sorting is not enabled on the view.
        """
        # stubs are wrong, cast it as correct type.
        proxy_model: QAbstractProxyModel | None = cast("Union[None, QAbstractProxyModel]", self.dialog.proxyModel())
        if isinstance(proxy_model, QSortFilterProxyModel):
            current_column = proxy_model.sortColumn()
            current_order = proxy_model.sortOrder()

            new_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            proxy_model.sort(current_column, new_order)
        else:
            inner_view: QAbstractItemView = self.get_current_view()
            if isinstance(inner_view, QTreeView):
                assert isinstance(inner_view, QTreeView), "Inner view is not a QTreeView"
                if not inner_view.isSortingEnabled():
                    return
                inner_view_header = inner_view.header()
                assert inner_view_header is not None, "View header is None"
                current_column = inner_view_header.sortIndicatorSection()
                current_order = inner_view_header.sortIndicatorOrder()

                new_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
                inner_view.sortByColumn(current_column, new_order)
                inner_view_header.setSortIndicator(current_column, new_order)
            elif isinstance(inner_view, QTableView):
                if not inner_view.isSortingEnabled():
                    return
                horizontal_header = inner_view.horizontalHeader()
                assert horizontal_header is not None, "View horizontal header is None"
                current_column = horizontal_header.sortIndicatorSection()
                current_order = horizontal_header.sortIndicatorOrder()
                new_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
                inner_view.sortByColumn(current_column, new_order)
                horizontal_header.setSortIndicator(current_column, new_order)
            elif isinstance(inner_view, QHeaderView):
                current_order = inner_view.sortIndicatorOrder()
                current_column = inner_view.sortIndicatorSection()
                next_sort_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
                inner_view.setSortIndicator(current_column, next_sort_order)

    def prepare_rename(self):
        """Handle the 'Rename' action for selected items."""
        selected_items = self.get_selected_paths()
        if not selected_items:
            return

        old_path = selected_items[0]
        validator = FileNameValidator(self.dialog)
        while True:
            name, ok = QInputDialog.getText(
                self.dialog,
                "New File",
                "File name:",
                QLineEdit.EchoMode.Normal,
                "",
                flags=Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.MSWindowsFixedSizeDialogHint | Qt.WindowType.WindowCloseButtonHint,
                inputMethodHints=Qt.InputMethodHint.ImhNoAutoUppercase | Qt.InputMethodHint.ImhLatinOnly | Qt.InputMethodHint.ImhNoPredictiveText,
            )
            if not ok:
                return
            if not name or not name.strip():
                QMessageBox.warning(self.dialog, "Invalid File Name", "File name cannot be empty/blank.")
                continue
            if validator.validate(name, 0)[0] != QValidator.State.Acceptable:
                QMessageBox.warning(self.dialog, "Invalid File Name", "File name contains invalid characters.")
                continue
            if len(PurePath(name).stem) > 16:  # resref max length  # noqa: PLR2004
                QMessageBox.warning(self.dialog, "File Name Too Long", "File name is too long.")
                continue
            new_file_path = old_path.parent / name
            if (new_file_path).exists():
                QMessageBox.warning(self.dialog, "File Exists", "File with this name already exists.")
                continue
            break

        if ok and name:
            new_path = old_path.parent / name
            self.queue_task("rename", old_path, new_path)

    def prepare_new_folder(self):
        """Handle the 'New Folder' action."""
        current_dir = Path(self.fs_model.rootPath())
        name, ok = QInputDialog.getText(self.dialog, "New Folder", "Folder name:")

        if ok and name:
            new_folder_path = current_dir / name
            self.queue_task("new_folder", new_folder_path)

    def prepare_new_file(self):
        """Handle the 'New File' action."""
        current_dir = Path(self.fs_model.rootPath())
        validator = FileNameValidator(self.dialog)
        while True:
            name, ok = QInputDialog.getText(
                self.dialog,
                "New File",
                "File name:",
                QLineEdit.EchoMode.Normal,
                "",
                flags=Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.MSWindowsFixedSizeDialogHint | Qt.WindowType.WindowCloseButtonHint,
                inputMethodHints=Qt.InputMethodHint.ImhNoAutoUppercase | Qt.InputMethodHint.ImhLatinOnly | Qt.InputMethodHint.ImhNoPredictiveText,
            )
            if not ok:
                return
            if not name:
                QMessageBox.warning(self.dialog, "Invalid File Name", "File name cannot be empty.")
                continue
            if validator.validate(name, 0)[0] != QValidator.State.Acceptable:
                QMessageBox.warning(self.dialog, "Invalid File Name", "File name contains invalid characters.")
                continue
            if len(PurePath(name).stem) > 16:  # resref max length  # noqa: PLR2004
                QMessageBox.warning(self.dialog, "File Name Too Long", "File name is too long.")
                continue
            new_file_path = current_dir / name
            if (new_file_path).exists():
                QMessageBox.warning(self.dialog, "File Exists", "File with this name already exists.")
                continue
            break

        self.queue_task("new_file", new_file_path)

    def prepare_delete(self):
        """Handle the 'Delete' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        if self.confirm_deletion(paths):
            self.queue_task("delete", paths)

    def prepare_create_shortcut(self):
        """Handle the 'Create Shortcut' action for selected items."""
        source_paths = self.get_selected_paths()
        if not source_paths:
            return
        shortcut_path = source_paths[0].parent / f"{source_paths[0].stem} - Shortcut{source_paths[0].suffix}"
        self.queue_task("create_shortcut", source_paths, shortcut_path)

    def prepare_open_with(self):
        """Handle the 'Open With' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("open_with", paths)

    def prepare_open_terminal(self):
        """Handle the 'Open Terminal' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        path = paths[0]
        if path.is_file():
            path = path.parent
        self.queue_task("open_terminal", path)

    def prepare_compress(self):
        """Handle the 'Compress' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        archive_path = paths[0].parent / f"{paths[0].stem}.zip"
        self.queue_task("compress_items", paths, archive_path)

    def prepare_extract(self):
        """Handle the 'Extract' action for selected archive files."""
        paths = self.get_selected_paths()
        if not paths:
            return
        archive_path = paths[0]
        extract_path = archive_path.parent
        self.queue_task("extract_items", archive_path, extract_path)

    def prepare_take_ownership(self):
        """Handle the 'Take Ownership' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("take_ownership", paths)

    def prepare_send_to(self, destination):
        """Handle the 'Send To' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("send_to", paths, destination)

    def prepare_open_as_admin(self):
        """Handle the 'Open as Administrator' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("open_as_admin", paths)

    def prepare_print(self):
        """Handle the 'Print' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("print_file", paths)

    def prepare_share(self):
        """Handle the 'Share' action for selected items."""
        paths = self.get_selected_paths()
        if not paths:
            return
        self.queue_task("share", paths)

    def prepare_show_hidden_items(self, show: bool):  # noqa: FBT001
        """Handle the 'Show Hidden Items' action."""
        self.fs_model.setFilter(self.fs_model.filter() | QDir.Filter.Hidden if show else self.fs_model.filter() & ~QDir.Filter.Hidden)
        self.queue_task("refresh_view")

    def prepare_show_file_extensions(self, show: bool):  # noqa: FBT001
        """Handle the 'Show File Extensions' action."""
        # Check for Qt version-specific methods using try/except for strict type checking
        try:
            self.fs_model.setNameFilterDisables(not show)  # type: ignore[attr-defined]
        except AttributeError:
            pass  # Method not available in this Qt version
        try:
            self.fs_model.setNameFilters([] if show else ["*"])  # type: ignore[attr-defined]
        except AttributeError:
            pass  # Method not available in this Qt version
        self.queue_task("refresh_view")

    def on_open_file(self):
        """Handle the 'Open' action for selected files."""
        paths = self.get_selected_paths()
        self.queue_task("open_file", paths)

    def on_open_dir(self):
        """Handle the 'Open' action for selected directories."""
        # Prefer in-app navigation instead of launching external explorers.
        paths = self.get_selected_paths()
        if not paths:
            return
        for path in paths:
            if path.is_dir():
                try:
                    # Prefer using the dialog API so the directory opens inside the app
                    self.dialog.setDirectory(str(path))
                except Exception:
                    # Fallback to the external/open_dir operation if needed
                    self.queue_task("open_dir", [path])

    def on_open(self):
        """Handle the 'Open' action for selected items."""
        # Handles both double-click and context menu 'Open'. For directories,
        # navigate inside the dialog. For files, fall back to existing behaviour
        # (which may open the file externally).
        paths = self.get_selected_paths()
        for path in paths:
            if path.is_dir():
                try:
                    self.dialog.setDirectory(str(path))
                except Exception:
                    self.queue_task("open_dir", [path])
            else:
                self.queue_task("open_file", [path])

    def on_open_with_file(self):
        """Retrieve and queue the open with task for the selected file."""
        paths = self.get_selected_paths()
        self.queue_task("open_with", paths)

    def on_properties_file(self):
        """Retrieve and queue the properties task for the selected file."""
        paths = self.get_selected_paths()
        self.queue_task("get_properties", paths[0])

    def on_properties_dir(self):
        """Retrieve and queue the properties task for the selected directory."""
        paths = self.get_selected_paths()
        self.queue_task("get_properties", paths[0])

    def on_open_terminal_file(self):
        """Open a terminal window at the parent directory of the selected file path."""
        paths = self.get_selected_paths()
        self.queue_task("open_terminal", paths[0].parent)

    def on_open_terminal_dir(self):
        """Open a terminal window at the selected directory path."""
        paths = self.get_selected_paths()
        self.queue_task("open_terminal", paths[0])

    def on_rename_item(self):
        """Rename the selected item."""
        paths = self.get_selected_paths()
        self.queue_task("rename_item", paths[0])

    def on_copy_items(self):
        """Copy the selected items to the clipboard."""
        self._prepare_clipboard_data(is_cut=False)

    def on_cut_items(self):
        """Cut the selected items to the clipboard."""
        self._prepare_clipboard_data(is_cut=True)

    def on_delete_items(self):
        """Delete the selected items after confirmation."""
        paths = self.get_selected_paths()
        self.queue_task("delete_items", paths)

    def on_paste_items(self):
        """Paste items from the clipboard to the current directory."""
        print("on_paste_items")
        self._handle_paste()

    def _prepare_clipboard_data(self, *, is_cut: bool):
        """Prepare and set clipboard data for file operations (copy/cut).

        This method handles platform-specific clipboard formatting to ensure
        compatibility with native file managers across Windows, macOS, and Linux.

        Args:
            is_cut (bool): If True, prepares data for cut operation; if False, for copy operation.

        Returns:
            None

        Raises:
            AssertionError: If clipboard is not available on the system.

        Note:
            - Sets standard MIME URLs for file paths
            - Sets "Preferred DropEffect" with appropriate drop action
            - Windows: Uses "FileGroupDescriptorW" format with absolute paths
            - macOS: Uses "com.apple.NSFilePromiseContent" plist format
            - Linux/Unix: Uses "x-special/gnome-copied-files" format with action prefix
            - Stores copied items and cut status in instance variables for later reference
        """
        paths = self.get_selected_paths()
        if not paths:
            return

        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(str(item)) for item in paths]
        mime_data.setUrls(urls)

        # Set the Preferred DropEffect
        drop_effect = DropEffect.CUT if is_cut else DropEffect.COPY
        effect_data = QByteArray()
        data_stream = QDataStream(effect_data, QIODevice.OpenModeFlag.WriteOnly)
        data_stream.setByteOrder(QDataStream.ByteOrder.LittleEndian)
        data_stream.writeInt32(drop_effect.value)
        mime_data.setData("Preferred DropEffect", effect_data)

        # Set platform-specific data
        if platform.system() == "Windows":
            file_descriptor_list = [f"<{p.absolute()}>" for p in paths]
            file_contents = "\n".join(file_descriptor_list)
            mime_data.setData("FileGroupDescriptorW", QByteArray(file_contents.encode("utf-16-le")))
        elif platform.system() == "Darwin":
            import plistlib

            plist_data = {"NSFilenamesPboardType": [str(item) for item in paths]}
            mime_data.setData("com.apple.NSFilePromiseContent", QByteArray(plistlib.dumps(plist_data)))
        else:  # Linux and other Unix-like
            action = "cut" if is_cut else "copy"
            mime_data.setData("x-special/gnome-copied-files", QByteArray(f"{action}\n".encode() + b"\n".join(str(item).encode() for item in paths)))

        clipboard = QApplication.clipboard()
        assert clipboard is not None, "Clipboard is not available"
        clipboard.setMimeData(mime_data, QClipboard.Mode.Clipboard)
        self.copied_items = paths
        self.is_cut = is_cut

    def _handle_paste(self):
        destination_folder = self.get_current_directory()
        clipboard = QApplication.clipboard()
        assert clipboard is not None, "Clipboard is not available"
        mime_data = clipboard.mimeData()
        assert mime_data is not None, "Clipboard mime data is not available"

        if mime_data.hasUrls():
            urls = mime_data.urls()
            sources = [Path(url.toLocalFile()) for url in urls]
            is_cut = self._get_preferred_drop_effect(mime_data) == DropEffect.CUT

            if self._can_paste_data_object(destination_folder, mime_data):
                if is_cut:
                    self.queue_task("move_item", sources, destination_folder)
                else:
                    self.queue_task("copy_item", sources, destination_folder)
                if is_cut:
                    clipboard.clear()
            else:
                QMessageBox.warning(self.dialog, "Paste Error", "Cannot paste the items to the selected destination.")

    def _can_paste_data_object(self, destination: Path, mime_data: QMimeData) -> bool:
        if not destination.is_dir() or not os.access(str(destination), os.W_OK):
            return False

        if mime_data.hasUrls():
            for url in mime_data.urls():
                source_path = Path(url.toLocalFile())
                if not source_path.exists():
                    return False
                if source_path.is_dir() and destination in source_path.parents:
                    return False

        return True

    def _get_preferred_drop_effect(self, mime_data: QMimeData) -> int:
        effect_data = mime_data.data("Preferred DropEffect")
        if effect_data:
            return int.from_bytes(effect_data, byteorder="little")  # pyright: ignore[reportArgumentType]
        return DropEffect.COPY.value

    def _handle_task_result(self, task_id: str, result: Any):
        """Maps the task_id to the operation's callback function and calls it with the result."""
        RobustLogger().debug(f"Handling task result for task_id: {task_id}, result: {result}")
        operation = self.task_operations.get(task_id)
        if operation == "get_properties":
            self.show_properties_dialog(result)
        else:
            print("Operation completed successfully:", operation)
        self.task_operations.pop(task_id)

    def show_properties_dialog(self, properties: list[FileProperties]):
        """Display properties dialogs for the given file properties.

        Opens a non-blocking FilePropertiesDialog for each property in the list,
        allowing the user to view and edit file information.

        Args:
            properties: A list of FileProperties objects to display in dialogs.
        """
        for prop in properties:
            RobustLogger().debug(f"Showing properties dialog for: {prop.name}")
            dialog = FilePropertiesDialog(prop, self.dialog)
            dialog.show()  # don't block

    def queue_task(self, operation: str, *args, **kwargs) -> str:
        """Queue a task for execution with the specified operation and arguments.

        Args:
            operation: The name of the operation to queue.
            *args: Variable length argument list to pass to the operation.
            **kwargs: Arbitrary keyword arguments to pass to the operation.

        Returns:
            str: A unique task identifier for the queued task.
        """
        task_id = self.file_actions_executor.queue_task(operation, args=args, kwargs=kwargs)
        self.task_operations[task_id] = operation
        RobustLogger().debug(f"Queued task: {task_id} for operation: {operation}")
        return task_id


if __name__ == "__main__":
    import sys
    import traceback

    test_app = QApplication(sys.argv)

    test_file_dialog = QFileDialog()
    test_file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)  # noqa: FBT003
    test_file_dialog.setFileMode(QFileDialog.FileMode.Directory)
    test_file_dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)  # noqa: FBT003

    test_tree_view = test_file_dialog.findChild(QTreeView)
    assert isinstance(test_tree_view, QTreeView)
    test_fs_model = test_tree_view.model()
    assert isinstance(test_fs_model, QFileSystemModel)
    test_file_actions_executor = FileActionsExecutor()
    test_menu_actions_dispatcher = ActionsDispatcher(test_fs_model, test_file_dialog, test_file_actions_executor)

    def on_task_failed(task_id: str, error: Exception):
        """
        Handle task failure by logging the error and displaying an error dialog.

        Args:
            task_id: The unique identifier of the failed task.
            error: The exception that caused the task to fail.
        """
        RobustLogger().exception(f"Task {task_id} failed", exc_info=error)
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Icon.Critical)
        error_msg.setText(f"Task {task_id} failed")
        error_msg.setInformativeText(str(error))
        error_msg.setDetailedText("".join(traceback.format_exception(type(error), error, None)))
        error_msg.setWindowTitle("Task Failed")
        error_msg.exec()

    test_file_actions_executor.TaskFailed.connect(on_task_failed)
    test_views = test_file_dialog.findChildren(QAbstractItemView)

    for test_view in test_views:
        if not isinstance(test_view, QAbstractItemView):
            continue
        print("Setting context menu policy for view:", test_view.objectName(), "of type:", type(test_view).__name__)

        def show_context_menu(
            pos: QPoint,
            inner_view: QAbstractItemView = test_view,
        ):
            """Display a context menu at the specified position within the item view.

            Args:
                pos: The position where the context menu should be displayed.
                inner_view: The QAbstractItemView instance to display the context menu for.
                           Defaults to the view parameter from the enclosing scope.
            """
            index = inner_view.indexAt(pos)
            if not index.isValid():
                inner_view.clearSelection()
            menu = test_menu_actions_dispatcher.get_context_menu(inner_view, pos)
            if menu:
                viewport = inner_view.viewport()
                assert viewport is not None, "Viewport is not available"
                menu.exec(viewport.mapToGlobal(pos))

        test_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        with contextlib.suppress(TypeError):  # TypeError: disconnect() failed between 'customContextMenuRequested' and all its connections
            test_view.customContextMenuRequested.disconnect()
        test_view.customContextMenuRequested.connect(show_context_menu)

    test_file_dialog.resize(800, 600)
    test_file_dialog.show()
    sys.exit(test_app.exec())
