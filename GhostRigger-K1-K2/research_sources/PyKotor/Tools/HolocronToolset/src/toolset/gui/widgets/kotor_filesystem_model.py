"""KotOR filesystem model: file tree over installation/capsule with icons and resource types."""

from __future__ import annotations

import os
import pathlib
import sys

from abc import abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, Union, cast

import qtpy

from loggerplus import RobustLogger
from pykotor.extract.capsule import LazyCapsule
from utility.gui.qt.adapters.filesystem.pyfilesystemmodel import PyFileSystemModel
from utility.gui.qt.tools.image import qicon_from_file_ext, qpixmap_to_qicon

if qtpy.QT6:
    QDesktopWidget = None
    from qtpy.QtGui import (
        QUndoCommand,  # pyright: ignore[reportPrivateImportUsage]  # noqa: F401
        QUndoStack,
    )
elif qtpy.QT5:
    from qtpy.QtWidgets import (
        QUndoCommand,  # pyright: ignore[reportPrivateImportUsage]  # noqa: F401
        QUndoStack,
    )
else:
    raise RuntimeError(f"Unexpected qtpy version: '{qtpy.API_NAME}'")
from qtpy.QtWidgets import QAbstractItemView, QApplication, QFileIconProvider, QHeaderView, QMainWindow, QMenu, QStyle, QVBoxLayout, QWidget


def update_sys_path(path: pathlib.Path):
    working_dir = str(path)
    print("<SDM> [update_sys_path scope] working_dir: ", working_dir)

    if working_dir not in sys.path:
        sys.path.append(working_dir)


file_absolute_path = pathlib.Path(__file__).resolve()

pykotor_path = file_absolute_path.parents[6] / "Libraries" / "PyKotor" / "src" / "pykotor"
if pykotor_path.exists():
    update_sys_path(pykotor_path.parent)
pykotor_gl_path = file_absolute_path.parents[6] / "Libraries" / "PyKotorGL" / "src" / "pykotor"
if pykotor_gl_path.exists():
    update_sys_path(pykotor_gl_path.parent)
utility_path = file_absolute_path.parents[6] / "Libraries" / "Utility" / "src"
if utility_path.exists():
    update_sys_path(utility_path)
toolset_path = file_absolute_path.parents[3] / "toolset"
if toolset_path.exists():
    update_sys_path(toolset_path.parent)
    if __name__ == "__main__":
        os.chdir(toolset_path)


from pathlib import Path  # noqa: E402

from qtpy.QtCore import QAbstractItemModel, QDir, QModelIndex, QObject, Qt, Signal  # noqa: E402, F401
from qtpy.QtGui import QDrag, QIcon, QImage, QPalette, QPixmap  # noqa: E402
from qtpy.QtWidgets import (  # noqa: E402
    QFileSystemModel,  # pyright: ignore[reportPrivateImportUsage]
)

from pykotor.extract.file import FileResource  # noqa: E402
from pykotor.tools.misc import is_capsule_file  # noqa: E402
from toolset.gui.dialogs.load_from_location_result import ResourceItems  # noqa: E402
from toolset.gui.widgets.settings.installations import GlobalSettings  # noqa: E402
from toolset.main_init import main_init  # noqa: E402
from toolset.utils.window import open_resource_editor_from_path  # noqa: E402
from utility.gui.qt.widgets.itemviews.html_delegate import ICONS_DATA_ROLE, HTMLDelegate  # noqa: E402
from utility.gui.qt.widgets.itemviews.treeview import RobustTreeView  # noqa: E402
from utility.system.os_helper import get_size_on_disk  # noqa: E402

if TYPE_CHECKING:
    from qtpy.QtCore import QPoint, QRect
    from qtpy.QtGui import QDragEnterEvent, QDragMoveEvent, _QAction
    from qtpy.QtWidgets import _QMenu
    from typing_extensions import Literal

    from toolset.data.installation import HTInstallation
    from toolset.gui.widgets.settings.installations import InstallationConfig
    from toolset.gui.windows.main import ToolWindow
    from utility.gui.qt.adapters.filesystem.pyfilesystemmodel import PyFileSystemModel


class TreeItem:
    icon_provider: QFileIconProvider = QFileIconProvider()

    def __init__(
        self,
        path: os.PathLike | str,
        parent: TreeItem | None = None,
    ):
        super().__init__()
        self.path: Path = Path(path)
        self.parent: TreeItem | None = parent

    def row(self) -> int:
        if self.parent is None:
            return -1
        if not hasattr(self.parent, "children"):
            raise RuntimeError(f"INVALID parent item! Parent items must expose a children list, but parent was: '{self.parent.__class__.__name__}'")
        parent_children = getattr(self.parent, "children")
        if self not in parent_children:
            parent_path = getattr(self.parent, "path", "<virtual>")
            RobustLogger().warning(f"parent '{parent_path}' has orphaned the item '{self.path}' without warning!")
            return -1
        return parent_children.index(self)

    @abstractmethod
    def childCount(self) -> int:
        return 0

    @abstractmethod
    def iconData(self) -> QIcon: ...

    def data(self) -> str:
        return self.path.name


class DirItem(TreeItem):
    def __init__(
        self,
        path: Path,
        parent: TreeItem | None = None,
    ):
        super().__init__(path, parent)
        self.children: list[TreeItem] = []
        self._children_loaded: bool = False

    def childCount(self) -> int:
        return len(self.children)

    def loadChildren(self, model: KotorFileSystemModel | ResourceFileSystemModel) -> list[TreeItem]:
        idx: QModelIndex = model.indexFromItem(self)
        if self.childCount() > 0:
            model.beginRemoveRows(idx, 0, self.childCount() - 1)
            self.children = []
            model.endRemoveRows()
        print(f"{self.__class__.__name__}({self.path}).load_children, row={self.row()}")
        children: list[TreeItem] = []
        if not self.path.exists() or not self.path.is_dir():
            self._children_loaded = True
            return self.children

        qdir = QDir(str(self.path))
        qdir.setFilter(model.filter())
        for entry in qdir.entryInfoList():
            child_path = Path(entry.filePath())
            if child_path.is_dir():
                item = DirItem(child_path, self)
            elif is_capsule_file(child_path):
                item = CapsuleItem(child_path, self)
            else:
                item = FileItem(child_path, self)
            children.append(item)

        if children:
            model.beginInsertRows(idx, 0, len(children) - 1)
            self.children = list(children)
            model.endInsertRows()
        else:
            self.children = []
        self._children_loaded = True
        for child in self.children:
            model.setData(model.index(self.children.index(child), 0, idx), child.iconData(), Qt.ItemDataRole.DecorationRole)
        return self.children

    def child(self, row: int) -> TreeItem | None:
        return self.children[row]

    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_DirIcon, 16, 16)


class RootItem(TreeItem):
    def __init__(
        self,
        children: list[TreeItem] | None = None,
    ):
        super().__init__(Path("/"), None)
        self.children: list[TreeItem] = [] if children is None else children
        for child in self.children:
            child.parent = self

    def childCount(self) -> int:
        return len(self.children)

    def child(self, row: int) -> TreeItem | None:
        return self.children[row] if 0 <= row < len(self.children) else None

    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_DirIcon, 16, 16)


class InstallationItem(DirItem):
    def __init__(
        self,
        name: str,
        path: Path,
        tsl: bool,
        parent: TreeItem | None = None,
    ):
        super().__init__(path, parent)
        self.name: str = name
        self.tsl: bool = tsl

    def data(self) -> str:
        return self.name

    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_ComputerIcon, 16, 16)

    def loadChildren(self, model: KotorFileSystemModel | ResourceFileSystemModel) -> list[TreeItem]:
        """Load category nodes (Core, Modules, Override, Textures, Saves) as children."""

        idx: QModelIndex = model.indexFromItem(self)
        if self.childCount() > 0:
            model.beginRemoveRows(idx, 0, self.childCount() - 1)
            self.children = []
            model.endRemoveRows()

        print(f"{self.__class__.__name__}({self.name}).loadChildren, row={self.row()}")

        # Create category nodes
        children: list[TreeItem] = []

        # Core category
        core_path = self.path / "data"
        if core_path.exists() and core_path.is_dir():
            children.append(CategoryItem("Core", core_path, self))

        # Modules category
        modules_path = self.path / "modules"
        if modules_path.exists() and modules_path.is_dir():
            children.append(CategoryItem("Modules", modules_path, self))

        # Override category
        override_path = self.path / "override"
        if override_path.exists() and override_path.is_dir():
            children.append(CategoryItem("Override", override_path, self))

        # Textures category (same as Override but filtered)
        if override_path.exists() and override_path.is_dir():
            children.append(CategoryItem("Textures", override_path, self, filter_textures=True))

        # Saves category
        saves_path = self.path / "saves"
        if saves_path.exists() and saves_path.is_dir():
            children.append(CategoryItem("Saves", saves_path, self))

        if children:
            model.beginInsertRows(idx, 0, len(children) - 1)
            self.children = children
            model.endInsertRows()
        else:
            self.children = []

        self._children_loaded = True
        return self.children


class CategoryItem(DirItem):
    """Represents a category node (Core, Modules, Override, Textures, Saves) under an installation."""

    def __init__(
        self,
        category_name: str,
        path: Path,
        parent: TreeItem | None = None,
        *,
        filter_textures: bool = False,
    ):
        super().__init__(path, parent)
        self.category_name: str = category_name
        self.filter_textures: bool = filter_textures

    def data(self) -> str:
        return self.category_name

    def iconData(self) -> QIcon:
        # Use different icons for different categories
        icon_map = {
            "Core": QStyle.StandardPixmap.SP_DirHomeIcon,
            "Modules": QStyle.StandardPixmap.SP_DirIcon,
            "Override": QStyle.StandardPixmap.SP_DirOpenIcon,
            "Textures": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Saves": QStyle.StandardPixmap.SP_FileIcon,
        }
        standard_pixmap = icon_map.get(self.category_name, QStyle.StandardPixmap.SP_DirIcon)
        return qpixmap_to_qicon(standard_pixmap, 16, 16)

    def loadChildren(self, model: KotorFileSystemModel | ResourceFileSystemModel) -> list[TreeItem]:
        """Load files/folders as children, optionally filtering for textures."""
        idx: QModelIndex = model.indexFromItem(self)
        if self.childCount() > 0:
            model.beginRemoveRows(idx, 0, self.childCount() - 1)
            self.children = []
            model.endRemoveRows()

        print(f"{self.__class__.__name__}({self.category_name}).loadChildren, row={self.row()}")
        children: list[TreeItem] = []

        if not self.path.exists() or not self.path.is_dir():
            self._children_loaded = True
            return self.children

        qdir = QDir(str(self.path))
        qdir.setFilter(model.filter())

        for entry in qdir.entryInfoList():
            child_path = Path(entry.filePath())

            # Filter for texture files if this is the Textures category
            if self.filter_textures:
                if child_path.is_file():
                    ext = child_path.suffix.lower()
                    if ext not in [".tpc", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".dds"]:
                        continue
                else:
                    # Skip directories in Textures category
                    continue

            if child_path.is_dir():
                item = DirItem(child_path, self)
            elif is_capsule_file(child_path):
                item = CapsuleItem(child_path, self)
            else:
                item = FileItem(child_path, self)
            children.append(item)

        if children:
            model.beginInsertRows(idx, 0, len(children) - 1)
            self.children = list(children)
            model.endInsertRows()
        else:
            self.children = []

        self._children_loaded = True
        for child in self.children:
            model.setData(model.index(self.children.index(child), 0, idx), child.iconData(), Qt.ItemDataRole.DecorationRole)

        return self.children


class ResourceItem(TreeItem):
    def __init__(
        self,
        file: Path | FileResource,
        parent: TreeItem | None = None,
    ):
        self.resource: FileResource
        if isinstance(file, FileResource):
            self.resource = file
            super().__init__(self.resource.filepath(), parent)
        else:
            self.resource = FileResource.from_path(file)
            super().__init__(file, parent)

    def data(self) -> str:
        assert self.resource.filename().lower() == self.path.name.lower()
        assert self.resource.filename() == self.path.name
        return self.resource.filename()

    def iconData(self) -> QIcon:
        result_qfileiconprovider: QIcon = qicon_from_file_ext(self.resource.restype().extension)
        return result_qfileiconprovider


class FileItem(ResourceItem):
    def iconData(self) -> QIcon:
        result_qfileiconprovider: QIcon = qicon_from_file_ext(self.resource.restype().extension)
        return result_qfileiconprovider

    def childCount(self) -> int:
        return 0


class CapsuleItem(DirItem, FileItem):
    def __init__(
        self,
        file: Path | FileResource,
        parent: TreeItem | None = None,
    ):
        FileItem.__init__(self, file, parent)  # call BEFORE diritem.__init__!
        DirItem.__init__(self, file.filepath() if isinstance(file, FileResource) else file, parent)  # noqa: SLF001
        self.children: list[CapsuleChildItem | NestedCapsuleItem]

    def child(self, row: int) -> TreeItem:
        return self.children[row]

    def loadChildren(
        self: CapsuleItem | NestedCapsuleItem,
        model: KotorFileSystemModel | ResourceFileSystemModel,
    ) -> list[CapsuleChildItem | NestedCapsuleItem]:
        idx: QModelIndex = model.indexFromItem(self)
        if self.childCount() > 0:
            model.beginRemoveRows(idx, 0, self.childCount() - 1)
            self.children = []
            model.endRemoveRows()
        print(f"{self.__class__.__name__}({self.path}).load_children, row={self.row()}")
        children: list[NestedCapsuleItem | CapsuleChildItem] = [
            NestedCapsuleItem(res, self) if is_capsule_file(res.filename()) else CapsuleChildItem(res, self) for res in LazyCapsule(self.resource.filepath())
        ]
        if children:
            model.beginInsertRows(idx, 0, len(children) - 1)
            self.children = children
            model.endInsertRows()
        else:
            self.children = []
        self._children_loaded = True
        return self.children

    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_DirLinkOpenIcon, 16, 16)


class CapsuleChildItem(ResourceItem):
    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_FileIcon, 16, 16)


class NestedCapsuleItem(CapsuleItem, CapsuleChildItem):
    def iconData(self) -> QIcon:
        return qpixmap_to_qicon(QStyle.StandardPixmap.SP_DirLinkIcon, 16, 16)


class ResourceFileSystemTreeView(RobustTreeView):
    def parent(self) -> ResourceFileSystemWidget:
        return cast("ResourceFileSystemWidget", super().parent())

    def build_context_menu(self) -> _QMenu:
        rootMenu = super().build_context_menu()
        self._add_simple_action(rootMenu, "Resize Columns", self.parent().resize_all_columns)
        toggle_detailed_view = getattr(self.parent().fs_model, "toggle_detailed_view", None)
        if toggle_detailed_view is not None:
            self._add_simple_action(rootMenu, "Toggle Detailed View", toggle_detailed_view)
        header: QHeaderView | None = self.header()
        if header is None:
            raise RuntimeError("Header is None somehow? This should be impossible.")
        self._add_exclusive_menu_action(
            rootMenu,
            "Resize Mode",
            lambda: next((header.sectionResizeMode(i) for i in range(self.parent().fs_model.columnCount())), QHeaderView.ResizeMode.ResizeToContents),
            lambda mode: [header.setSectionResizeMode(i, mode) for i in range(self.parent().fs_model.columnCount())]
            if qtpy.QT5
            else lambda mode: [header.setSectionResizeMode(i, QHeaderView.ResizeMode(mode)) for i in range(header.count())],
            {
                "Custom": QHeaderView.ResizeMode.Custom,
                "Fixed": QHeaderView.ResizeMode.Fixed,
                "Interactive": QHeaderView.ResizeMode.Interactive,
                "ResizeToContents": QHeaderView.ResizeMode.ResizeToContents,
                "Stretch": QHeaderView.ResizeMode.Stretch,
            },
            "columnResizeMode",
        )
        self._add_multi_option_menu_action(
            rootMenu,
            "File System Filters",
            self.parent().fs_model.filter,
            self.parent().fs_model.setFilter,
            {
                "All Entries": QDir.Filter.AllEntries,
                "Files": QDir.Filter.Files,
                "Directories": QDir.Filter.Dirs,
                "Hidden Files": QDir.Filter.Hidden,
                "No Dot Files": QDir.Filter.NoDotAndDotDot,
            },
            "fileSystemFilter",
        )
        return rootMenu


class ResourceFileSystemWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        view: RobustTreeView | None = None,
        model: PyFileSystemModel | QFileSystemModel | KotorFileSystemModel | ResourceFileSystemModel | None = None,
    ):
        super().__init__(parent)

        from toolset.uic.qtpy.widgets.resource_filesystem_widget import Ui_Form

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Setup the view and model.
        if view is None:
            # Replace the default tree view with our custom one
            self.fsTreeView: ResourceFileSystemTreeView | RobustTreeView = ResourceFileSystemTreeView(self, use_columns=True)
            # Remove the default tree view and add our custom one
            self.ui.mainLayout.removeWidget(self.ui.fsTreeView)
            self.ui.fsTreeView.deleteLater()
            self.ui.mainLayout.addWidget(self.fsTreeView)
        else:
            self.fsTreeView = view
            # Replace the default tree view with the provided one
            self.ui.mainLayout.removeWidget(self.ui.fsTreeView)
            self.ui.fsTreeView.deleteLater()
            self.ui.mainLayout.addWidget(self.fsTreeView)

        self.fs_model: QFileSystemModel | KotorFileSystemModel | ResourceFileSystemModel | PyFileSystemModel = KotorFileSystemModel(self) if model is None else model
        self.fsTreeView.setModel(self.fs_model)

        # Store references for easier access
        self.address_bar = self.ui.addressBar
        self.go_button = self.ui.goButton
        self.refresh_button = self.ui.refreshButton
        self.address_layout = self.ui.addressLayout
        self.main_layout = self.ui.mainLayout

        # Connect signals
        self.address_bar.returnPressed.connect(self.onAddressBarReturnPressed)
        self.go_button.clicked.connect(self.onGoButtonClicked)
        self.refresh_button.clicked.connect(self.onRefreshButtonClicked)

        # Configure the QTreeView
        self.setup_tree_view()

    def setup_tree_view(self):
        self.undo_stack: QUndoStack = QUndoStack(self)
        h: QHeaderView | None = self.fsTreeView.header()
        assert h is not None
        h.setSectionsClickable(True)
        h.setSortIndicatorShown(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionsMovable(True)
        self.fsTreeView.setWordWrap(False)
        self.fsTreeView.setSortingEnabled(True)
        self.fsTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fsTreeView.setUniformRowHeights(True)
        self.fsTreeView.setVerticalScrollMode(self.fsTreeView.ScrollMode.ScrollPerItem)
        self.fsTreeView.setSelectionMode(self.fsTreeView.SelectionMode.ExtendedSelection)
        self.fsTreeView.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.fsTreeView.setDragEnabled(True)
        self.fsTreeView.setAcceptDrops(True)
        self.fsTreeView.setDropIndicatorShown(True)
        self.fsTreeView.expanded.connect(self.onItemExpanded)
        self.fsTreeView.collapsed.connect(self.onItemCollapsed)
        self.fsTreeView.customContextMenuRequested.connect(self.file_system_model_context_menu)
        self.fsTreeView.doubleClicked.connect(self.fileSystemModelDoubleClick)

    def setRootPath(self, path: os.PathLike | str):
        if self.fs_model is None:
            raise RuntimeError(f"Call setModel before calling {self}.setRootPath")
        self.fs_model.setRootPath(str(Path(path)))
        self.updateAddressBar()

    def updateAddressBar(self):
        """Updates the address bar to show the current root path."""
        model = self.fs_model
        if model and model.rootPath() is not None:  # noqa: SLF001
            self.address_bar.setText(str(model.rootPath()))  # noqa: SLF001
        else:
            self.address_bar.setText("")

    def onGoButtonClicked(self):
        """Handle Go button click to change the root path."""
        self.onAddressBarReturnPressed()

    def onAddressBarReturnPressed(self):
        """Handle user input in the address bar to change the root path."""
        new_path = Path(self.address_bar.text())
        if new_path.exists() and new_path.is_dir():
            self.setRootPath(new_path)
        else:
            print(f"Invalid path: {new_path}")
        self.updateAddressBar()

    def onRefreshButtonClicked(self):
        self.fs_model.reloadModelData()

    def resize_all_columns(self):
        """Adjust the view size based on content."""
        h = self.fsTreeView.header()
        assert h is not None
        for i in range(self.fs_model.columnCount()):
            h.setSectionResizeMode(i, h.ResizeMode.ResizeToContents)
        for i in range(self.fs_model.columnCount()):
            h.setSectionResizeMode(i, h.ResizeMode.Interactive)

    def onItemExpanded(self, idx: QModelIndex):
        """Handle item expansion event."""
        print(f"onItemExpanded, row={idx.row()}, col={idx.column()}")
        self.fsTreeView.debounce_layout_changed(pre_change_emit=True)
        item = idx.internalPointer()
        if isinstance(item, DirItem) and isinstance(self.fs_model, (KotorFileSystemModel, ResourceFileSystemModel, QFileSystemModel)):
            item.loadChildren(self.fs_model)
        self.refresh_item(item)
        self.fsTreeView.debounce_layout_changed(pre_change_emit=False)

    def onItemCollapsed(self, idx: QModelIndex):
        """Handle item collapse event."""
        print(f"onItemCollapsed, row={idx.row()}, col={idx.column()}")
        self.fsTreeView.debounce_layout_changed(pre_change_emit=True)
        item = idx.internalPointer()
        assert isinstance(item, TreeItem)
        self.refresh_item(item)
        self.fsTreeView.debounce_layout_changed(pre_change_emit=False)

    def model(self) -> QFileSystemModel | KotorFileSystemModel | ResourceFileSystemModel | PyFileSystemModel:
        return self.fs_model

    def fileSystemModelDoubleClick(self, idx: QModelIndex):
        item: ResourceItem | DirItem = idx.internalPointer()
        print(f"<SDM> [fileSystemModelDoubleClick scope] {item.__class__.__name__}: ", repr(item.resource if isinstance(item, ResourceItem) else item.path))

        if isinstance(item, ResourceItem) and item.path.exists() and item.path.is_file():
            mw: ToolWindow = next((w for w in QApplication.topLevelWidgets() if isinstance(w, QMainWindow) and w.__class__.__name__ == "ToolWindow"), None)  # pyright: ignore[reportAssignmentType]
            print("<SDM> [fileSystemModelDoubleClick scope] ToolWindow: ", mw)
            if mw is None:
                return
            open_resource_editor_from_path(item.path, installation=mw.active, gff_specialized=GlobalSettings().gffSpecializedEditors)
        elif isinstance(item, DirItem):
            if not item.children and isinstance(self.fs_model, (KotorFileSystemModel, ResourceFileSystemModel, QFileSystemModel)):
                item.loadChildren(self.fs_model)
            self.fsTreeView.expand(idx)
        else:
            raise TypeError("Unsupported tree item type")

    def setItemIcon(self, idx: QModelIndex, icon: QIcon | QStyle.StandardPixmap | str | QPixmap | QImage):
        if isinstance(icon, QStyle.StandardPixmap):
            q_style = QApplication.style()
            assert q_style is not None
            icon = q_style.standardIcon(icon)

        elif isinstance(icon, str):
            icon = QIcon(QPixmap(icon).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        elif isinstance(icon, QImage):
            icon = QIcon(QPixmap.fromImage(icon))

        if not isinstance(icon, QIcon):
            raise TypeError(f"Invalid icon passed to {self.__class__.__name__}.setItemIcon()!")
        if isinstance(self.fsTreeView.itemDelegate(), HTMLDelegate):
            iconData = {
                "icons": [(icon, None, "Item icon")],
                "size": 32,
                "spacing": 5,
                "rows": 1,
                "columns": 1,
            }
            self.fs_model.setData(idx, iconData, ICONS_DATA_ROLE)
        else:
            self.fs_model.setData(idx, icon, Qt.ItemDataRole.DecorationRole)

    def toggleHiddenFiles(self):
        f = self.fs_model.filter()
        print("<SDM> [toggleHiddenFiles scope] f: ", f)

        self.fs_model.setFilter(f & ~QDir.Filter.Hidden if bool(f & QDir.Filter.Hidden) else f | QDir.Filter.Hidden)  # pyright: ignore[reportArgumentType]

    def refresh_item(self, item: TreeItem, depth: int = 1):
        """Refresh the given TreeItem and its children up to the specified depth."""
        model: QFileSystemModel | KotorFileSystemModel | ResourceFileSystemModel | PyFileSystemModel = self.fs_model
        if not isinstance(item, TreeItem):
            raise TypeError(f"Expected a TreeItem, got {type(item).__name__}")
        index: QModelIndex = model.indexFromItem(item)
        if not index.isValid():
            return
        self.refresh_item_recursive(item, depth)

    def refresh_item_recursive(self, item: TreeItem, depth: int):
        """Recursively refresh the given TreeItem and its children up to the specified depth."""
        model: QFileSystemModel | KotorFileSystemModel | ResourceFileSystemModel | PyFileSystemModel = self.fs_model

        index: QModelIndex = model.indexFromItem(item)  # pyright: ignore[reportAttributeAccessIssue]
        if not index.isValid():
            return
        model.dataChanged.emit(index, index)
        if depth > 0 and isinstance(item, DirItem):
            for child in item.children:
                if child is None:
                    continue
                child_index: QModelIndex = model.indexFromItem(child)  # pyright: ignore[reportAttributeAccessIssue]
                if child_index.isValid():
                    self.setItemIcon(child_index, child.iconData())
                self.refresh_item_recursive(child, depth - 1)

    def create_root_folder(self):
        root_path: Path | None = self.fs_model.rootPath()  # pyright: ignore[reportAttributeAccessIssue]
        if root_path is None:
            return
        p = Path(root_path, "New Folder")
        p.mkdir(parents=True, exist_ok=True)
        if p.exists():
            self.fs_model.setRootPath(str(p))

    def on_empty_space_context_menu(
        self,
        point: QPoint,
    ):
        m = QMenu(self)
        sm = m.addMenu("Sort by")
        for i, t in enumerate(["Name", "Size", "Type", "Date Modified"]):
            sm.addAction(t).triggered.connect(lambda i=i: self.fsTreeView.sortByColumn(i, Qt.SortOrder.AscendingOrder))  # pyright: ignore[reportOptionalMemberAccess]
            print("<SDM> [onEmptySpaceContextMenu scope] i: ", i)

        m.addAction("Refresh").triggered.connect(lambda *args, **kwargs: self.fs_model.reloadModelData())  # pyright: ignore[reportOptionalMemberAccess]
        nm: _QMenu | None = m.addMenu("New")  # pyright: ignore[reportAttributeAccessIssue, reportAssignmentType]

        nm.addAction("Folder").triggered.connect(self.create_root_folder)  # pyright: ignore[reportOptionalMemberAccess]
        sh: _QAction = m.addAction("Show Hidden Items")
        print("<SDM> [onEmptySpaceContextMenu scope] sh: ", sh)

        sh.setCheckable(True)  # pyright: ignore[reportOptionalMemberAccess]
        sh.setChecked(bool(self.fs_model.filter() & QDir.Filter.Hidden))  # pyright: ignore[reportOptionalMemberAccess, reportOperatorIssue]
        sh.triggered.connect(self.toggleHiddenFiles)  # pyright: ignore[reportOptionalMemberAccess]
        if hasattr(m, "exec"):
            m.exec(self.fsTreeView.viewport().mapToGlobal(point))  # pyright: ignore[reportOptionalMemberAccess]
        elif hasattr(m, "exec_"):
            m.exec(self.fsTreeView.viewport().mapToGlobal(point))  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]

    def on_header_context_menu(self, point: QPoint):
        print(f"<SDM> [{self.__class__.__name__}.onHeaderContextMenu scope] point.x", point.x(), "y:", point.y())
        m = QMenu(self)
        td = m.addAction("Advanced")

        td.setCheckable(True)  # pyright: ignore[reportOptionalMemberAccess]
        td.setChecked(self.fs_model._detailed_view)  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
        td.triggered.connect(self.fs_model.toggle_detailed_view)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]

        sh = m.addAction("Show Hidden Items")
        sh.setCheckable(True)  # pyright: ignore[reportOptionalMemberAccess]
        sh.setChecked(bool(self.fs_model.filter() & QDir.Filter.Hidden))  # pyright: ignore[reportOptionalMemberAccess, reportOperatorIssue]
        sh.triggered.connect(self.toggleHiddenFiles)  # pyright: ignore[reportOptionalMemberAccess]
        self.fsTreeView.show_header_context_menu(point, m)

    def file_system_model_context_menu(
        self,
        point: QPoint,
    ):
        sel_idx: list[QModelIndex] = self.fsTreeView.selectedIndexes()
        print("<SDM> [fileSystemModelContextMenu scope] sel_idx: ", sel_idx)

        if not sel_idx:
            self.on_empty_space_context_menu(point)
            return
        resources: set[FileResource] = set()
        for idx in sel_idx:
            item: DirItem | ResourceItem = idx.internalPointer()
            if isinstance(item, ResourceItem):
                resources.add(item.resource)
            else:
                resources.add(FileResource.from_path(item.path))
        print("<SDM> [fileSystemModelContextMenu scope] resources: ", resources)

        if not resources:
            return
        mw: ToolWindow | None = next(  # pyright: ignore[reportAssignmentType]
            (w for w in QApplication.topLevelWidgets() if isinstance(w, QMainWindow) and w.__class__.__name__ == "ToolWindow"),
            None,
        )
        active_installation: HTInstallation | None = None if mw is None else mw.active
        m = QMenu(self)
        print("<SDM> [fileSystemModelContextMenu scope] m: ", m)

        m.addAction("Open").triggered.connect(
            lambda: [open_resource_editor_from_path(r.filepath(), installation=active_installation, gff_specialized=GlobalSettings().gffSpecializedEditors) for r in resources]
        )  # pyright: ignore[reportOptionalMemberAccess]

        if all(r.restype().contents == "gff" for r in resources):
            m.addAction("Open with GFF Editor").triggered.connect(
                lambda: [open_resource_editor_from_path(r.filepath(), installation=active_installation, open_as_generic_gff=True) for r in resources]
            )  # pyright: ignore[reportOptionalMemberAccess]

        m.addSeparator()
        ResourceItems(resources=list(resources), viewport=lambda: self.parent()).run_context_menu(point, installation=active_installation, menu=m)
        print("<SDM> [fileSystemModelContextMenu scope] resources: ", resources)
        self.fs_model.reloadModelData()

    def startDrag(self, actions: Qt.DropAction):  # pyright: ignore[reportOptionalMemberAccess]
        print("startDrag")
        d = QDrag(self)
        d.setMimeData(self.fs_model.mimeData(self.fsTreeView.selectedIndexes()))
        if hasattr(d, "exec_"):
            d.exec(actions)  # pyright: ignore[reportAttributeAccessIssue]
        elif hasattr(d, "exec"):
            d.exec(actions)

    def dragEnterEvent(self, e: QDragEnterEvent):
        print("dragEnterEvent")
        e.acceptProposedAction()

    def dragMoveEvent(self, e: QDragMoveEvent):
        print("dragMoveEvent")
        e.acceptProposedAction()


class SupportsRichComparison(Protocol):
    def __lt__(self, other: Any) -> bool: ...
    def __le__(self, other: Any) -> bool: ...
    def __gt__(self, other: Any) -> bool: ...
    def __ge__(self, other: Any) -> bool: ...


T = TypeVar("T", bound=Union[SupportsRichComparison, str])


class KotorFileSystemModel(QAbstractItemModel):
    # Signals
    address_changed = Signal()  # Emitted when the address bar should be updated

    COLUMN_TO_STAT_MAP: ClassVar[dict[str, str]] = {
        "Size on Disk": "size_on_disk",
        "Size Ratio": "size_ratio",
        "Mode": "st_mode",
        "Last Accessed": "st_atime",
        "Last Modified": "st_mtime",
        "Created": "st_ctime",
        "Hard Links": "st_nlink",
        "Last Accessed (ns)": "st_atime_ns",
        "Last Modified (ns)": "st_mtime_ns",
        "Created (ns)": "st_ctime_ns",
        "Inode": "st_ino",
        "Device": "st_dev",
        "User ID": "st_uid",
        "Group ID": "st_gid",
        "File Attributes": "st_file_attributes",
        "Reparse Tag": "st_reparse_tag",
        "Blocks Allocated": "st_blocks",
        "Block Size": "st_blksize",
        "Device ID": "st_rdev",
        "Flags": "st_flags",
    }
    STAT_TO_COLUMN_MAP: ClassVar[dict[str, str]] = {v: k for k, v in COLUMN_TO_STAT_MAP.items()}

    def __init__(
        self,
        parent: QObject | None = None,
    ):
        super().__init__(parent=parent)
        self._detailed_view: bool = False
        self._root: RootItem = RootItem()
        self._headers: list[str] = ["Name", "Size", "Path", "Offset", "Last Modified"]
        self._detailed_headers: list[str] = [*self._headers]
        self._detailed_headers.extend(h for h in self.COLUMN_TO_STAT_MAP if h not in self._headers)
        self._filter: QDir.Filter | int = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files
        self._thumbnail_cache: dict[str, QIcon] = {}
        self._thumbnail_cache_order: list[str] = []
        self._thumbnail_cache_limit: int = 512

    @property
    def NumColumns(self) -> int:
        """Note: This overrides a class level variable."""
        return len(self._detailed_headers if self._detailed_view else self._headers)

    def get_tree_view(self) -> RobustTreeView | None:
        """Get the tree view if parented by ResourceFileSystemWidget, else None."""
        qparent_obj = QObject.parent(self)
        if isinstance(qparent_obj, ResourceFileSystemWidget):
            return qparent_obj.fsTreeView
        return None

    def get_container_widget(self) -> ResourceFileSystemWidget | None:
        """Get the container widget if parented by ResourceFileSystemWidget, else None."""
        q_parent_obj: QObject | None = QObject.parent(self)
        if isinstance(q_parent_obj, ResourceFileSystemWidget):
            return q_parent_obj
        return None

    def toggle_detailed_view(self):
        self._detailed_view = not self._detailed_view
        print("<SDM> [toggle_detailed_view scope] self._detailed_view: ", self._detailed_view)
        container = self.get_container_widget()
        if container is not None:
            container.resize_all_columns()

    def rootPath(self) -> Path | None:
        if self._root.childCount() != 1:
            return None
        child = self._root.child(0)
        return None if child is None else child.path

    def rootPaths(self) -> list[Path]:
        return [child.path for child in self._root.children if isinstance(child, TreeItem)]

    def resetInternalData(self):  # noqa: N802
        """Qt reset hook; avoid calling begin/end reset from here to prevent recursion."""
        self._thumbnail_cache.clear()
        self._thumbnail_cache_order.clear()

    def reloadModelData(self):
        """Force a full model reset and reload of filesystem tree metadata."""
        self.beginResetModel()

        # Clear the current root item and reset it
        if self._root.childCount() > 0:
            self._root.children.clear()

        self.endResetModel()
        print("<SDM> [resetInternalData scope] Model data has been reset.")
        self.address_changed.emit()

    def setRootPath(self, path: os.PathLike | str):
        self.beginResetModel()
        if self._root.childCount() > 0:
            self._root.children.clear()
        root_item = self.create_fertile_tree_item(Path(path))
        self._root = RootItem([root_item])
        print("<SDM> [setRootPath scope] root: ", root_item.path)

        self.endResetModel()
        self.address_changed.emit()
        root_item.loadChildren(self)

    def set_installations(self, installations: dict[str, InstallationConfig]):
        self.beginResetModel()
        if self._root.childCount() > 0:
            self._root.children.clear()
        children: list[TreeItem] = []
        for installation in installations.values():
            path = Path(installation.path)
            if not path.exists() or not path.is_dir():
                continue
            children.append(InstallationItem(installation.name, path, installation.tsl))
        self._root = RootItem(children)
        self.endResetModel()
        self.address_changed.emit()
        for child in self._root.children:
            if isinstance(child, DirItem):
                child.loadChildren(self)

    def create_fertile_tree_item(self, file: Path | FileResource) -> DirItem:
        """Creates a tree item that can have children."""
        path = file.filepath() if isinstance(file, FileResource) else file
        cls = (
            NestedCapsuleItem
            if is_capsule_file(path) and not path.exists() and any(p.exists() and p.is_file() for p in path.parents)
            else CapsuleItem
            if isinstance(file, FileResource) or is_capsule_file(path)
            else DirItem
            if path.is_dir()
            else None.__class__
        )
        if cls is None.__class__:
            raise ValueError(f"invalid path: {file}")
        return cls(path)

    def get_grandpa_index(self, index: QModelIndex) -> QModelIndex:
        if isinstance(index, QModelIndex):
            if not index.isValid():
                return QModelIndex()
            return index.parent().parent() if index.parent().isValid() else QModelIndex()
        return QModelIndex()

    def itemFromIndex(self, index: QModelIndex) -> TreeItem | None:
        return index.internalPointer() if index.isValid() else None

    def indexFromItem(self, item: TreeItem) -> QModelIndex:
        if not isinstance(item, TreeItem):
            return QModelIndex()
        if item is self._root:
            return QModelIndex()
        return self.createIndex(item.row(), 0, item)

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        parent = QModelIndex() if parent is None else parent
        if parent.isValid() and parent.column() > 0:
            return 0
        if not parent.isValid():  # Root level
            return self._root.childCount()
        item = parent.internalPointer()
        assert isinstance(item, TreeItem)
        return 0 if item is None else item.childCount()

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return self.NumColumns

    def index(self, row: int, column: int, parent: QModelIndex | None = None) -> QModelIndex:
        parent = QModelIndex() if parent is None else parent
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parentItem = parent.internalPointer() if parent.isValid() else self._root
        assert isinstance(parentItem, TreeItem)
        childItem = parentItem.child(row) if parentItem else None
        return QModelIndex() if childItem is None else self.createIndex(row, column, childItem)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: PLR0911
        if not index.isValid():
            return None
        item: TreeItem = index.internalPointer()
        tree_view = self.get_tree_view()
        if tree_view is not None and isinstance(tree_view.itemDelegate(), HTMLDelegate):
            if role == Qt.ItemDataRole.DisplayRole:
                if self._detailed_view:
                    display_data = self.get_detailed_data(index)
                else:
                    display_data = self.get_default_data(index)
                # Use palette color for text instead of hardcoded black
                palette = tree_view.palette()
                text_color = palette.color(QPalette.ColorRole.WindowText)
                return f'<span style="color:{text_color.name()}; font-size:{tree_view.get_text_size()}pt;">{display_data}</span>'
            if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
                return item.iconData()
        if role == Qt.ItemDataRole.DisplayRole:
            if self._detailed_view:
                return self.get_detailed_data(index)
            return self.get_default_data(index)

        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            if isinstance(item, ResourceItem):
                thumb = self._get_thumbnail_icon(item.resource)
                if thumb is not None:
                    return thumb
            return item.iconData()

        if role == Qt.ItemDataRole.ToolTipRole:
            return self._format_item_path(item)

        if role == ICONS_DATA_ROLE and index.column() == 0:
            iconData = {
                "icons": [(item.iconData(), None, "Item icon")],
                "size": 32,
                "spacing": 5,
                "rows": 1,
                "columns": 1,
            }
            self.setData(index, iconData, ICONS_DATA_ROLE)

        return None

    def _get_thumbnail_icon(self, resource: FileResource) -> QIcon | None:
        """Generate or fetch cached thumbnail icon for supported assets."""
        restype = resource.restype()
        ext = restype.extension.lower()
        if ext not in {"tpc", "tga"}:
            return None

        source = resource.source()
        cache_key = source or f"{resource.resname()}.{ext}"
        if cache_key in self._thumbnail_cache:
            return self._thumbnail_cache[cache_key]

        data = resource.data()
        if not data:
            return None

        pixmap: QPixmap | None = None
        try:
            if ext == "tpc":
                from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

                tpc = read_tpc(data)
                if tpc.convert(TPCTextureFormat.RGB):
                    img = QImage(tpc.get().data, tpc.width, tpc.height, QImage.Format.Format_RGB888)
                else:
                    img = QImage(tpc.get().data, tpc.width, tpc.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(img)
            else:
                pixmap = QPixmap()
                pixmap.loadFromData(data)
        except Exception:
            return None

        if pixmap is None or pixmap.isNull():
            return None

        size = 128
        scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon = QIcon(scaled)
        self._thumbnail_cache[cache_key] = icon
        self._thumbnail_cache_order.append(cache_key)

        if len(self._thumbnail_cache_order) > self._thumbnail_cache_limit:
            oldest = self._thumbnail_cache_order.pop(0)
            self._thumbnail_cache.pop(oldest, None)

        return icon

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def hasChildren(self, parent: QModelIndex | None = None) -> bool:
        parent = QModelIndex() if parent is None else parent
        if not parent.isValid():
            return self._root.childCount() > 0
        item = parent.internalPointer()
        return isinstance(item, DirItem)

    def canFetchMore(self, index: QModelIndex) -> bool:
        print(f"canFetchMore({index.row()}, {index.column()})")
        if not index.isValid():
            return False
        item = index.internalPointer()
        result = isinstance(item, DirItem) and not item._children_loaded
        print("<SDM> [canFetchMore scope]", result)
        return result

    def fetchMore(self, index: QModelIndex) -> None:
        print(f"fetchMore({index.row()}, {index.column()})")
        if not index.isValid():
            return

        item: TreeItem = index.internalPointer()
        print(
            "<SDM> [fetchMore scope] index.internalPointer(): ",
            item,
            f"row: {'item is None' if item is None else item.row()}",
        )

        if isinstance(item, DirItem) and not item._children_loaded:
            item.loadChildren(self)

    def filter(self) -> QDir.Filter | int:
        return self._filter

    def setFilter(self, filters: QDir.Filter):
        self._filter = filters
        print("<SDM> [setFilter scope] self._filter: ", self._filter)

    def filePath(self, index: QModelIndex) -> str:
        if not index.isValid():
            return ""
        item = index.internalPointer()
        if not isinstance(item, TreeItem):
            return ""
        return self._format_item_path(item)

    def installation_from_index(self, index: QModelIndex) -> InstallationItem | None:
        item = self.itemFromIndex(index)
        while item is not None and not isinstance(item, InstallationItem):
            item = item.parent
        return item

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._detailed_headers[section] if self._detailed_view else self._headers[section]
        return None

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        childItem: Any = index.internalPointer()
        if not isinstance(childItem, TreeItem):
            return QModelIndex()
        parentItem = None if childItem is None else childItem.parent
        if parentItem is None or parentItem == self._root:
            return QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def human_readable_size(self, size: float, decimal_places: int = 2) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024 or unit == "PB":  # noqa: PLR2004
                break
            size /= 1024
        return f"{size:.{decimal_places}f} {unit}"

    def format_time(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ006

    def get_detailed_from_stat(self, index: QModelIndex, item: FileItem) -> str:  # noqa: C901, PLR0911
        column_name = self._detailed_headers[index.column()]

        stat_result: os.stat_result = item.resource.filepath().stat()
        if column_name in ("Size on Disk", "Size Ratio"):
            size_on_disk = get_size_on_disk(item.resource.filepath(), stat_result)
            ratio = (size_on_disk / stat_result.st_size) * 100 if stat_result.st_size else 0
            if column_name == "Size on Disk":
                return self.human_readable_size(size_on_disk)
            if column_name == "Size Ratio":
                return f"{ratio:.2f}%"
        stat_attr = self.COLUMN_TO_STAT_MAP.get(column_name, "")
        value = getattr(stat_result, stat_attr, None)
        if "size" in stat_attr:
            return "N/A" if value is None else self.human_readable_size(value)
        if "time" in stat_attr:
            if value is None:
                return "N/A"
            if stat_attr.endswith("time_ns"):
                value = value / 1e9

            return self.format_time(value)
        if column_name == "st_mode":
            if value is None:
                return "N/A"
            value = oct(value)[-3:]
        return str(value)

    def get_detailed_data(self, index: QModelIndex) -> str:
        item: FileItem | DirItem | InstallationItem = index.internalPointer()
        column_name = self._detailed_headers[index.column()]
        stat_attr = self.COLUMN_TO_STAT_MAP.get(column_name)
        if (stat_attr is not None or column_name in ("Size on Disk", "Size Ratio")) and isinstance(item, ResourceItem):
            return self.get_detailed_from_stat(index, item)
        if column_name == "Name":
            return item.data() if isinstance(item, InstallationItem) else (item.path.name if isinstance(item, DirItem) else item.resource.filename())
        if column_name == "Path":
            return self._format_item_path(item)
        if column_name == "Offset":
            return "0x0" if isinstance(item, DirItem) else f"{hex(item.resource.offset())}"
        if column_name == "Size":
            return "" if isinstance(item, DirItem) else self.human_readable_size(item.resource.size())
        return "N/A"

    def get_default_data(self, index: QModelIndex) -> str:
        item: ResourceItem | DirItem | InstallationItem = index.internalPointer()
        column_name = self._headers[index.column()]
        if column_name == "Name":
            return item.data() if isinstance(item, InstallationItem) else (item.path.name if isinstance(item, DirItem) else item.resource.filename())
        if column_name == "Path":
            return self._format_item_path(item)
        if column_name == "Offset":
            return "0x0" if isinstance(item, DirItem) else f"{hex(item.resource.offset())}"
        if column_name == "Size":
            return "" if isinstance(item, DirItem) else self.human_readable_size(item.resource.size())
        return "N/A"

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):  # noqa: C901
        def get_sort_key(item: TreeItem | None, list_index: int) -> tuple:
            """Generate a sort key that prioritizes directories over files and correctly sorts file sizes."""
            if item is None:
                return (1, "", list_index)  # Sort None items last

            is_dir = isinstance(item, DirItem)
            column_name = self._detailed_headers[column] if self._detailed_view else self._headers[column]

            if column_name == "Size":
                assert isinstance(item, (DirItem, ResourceItem))
                size_value = 0 if isinstance(item, DirItem) else item.resource.size()
                key = (
                    0 if is_dir else 1,
                    size_value,
                )  # Directories first, then by size in bytes  # pyright: ignore[reportCallIssue, reportArgumentType, reportAssignmentType]
            else:
                if column_name == "Name":
                    key_value = item.path.name if isinstance(item, DirItem) else item.path.name  # noqa: PTH119
                    key_value = key_value.lower()
                elif column_name == "Path":
                    key_value = str(item.path if isinstance(item, DirItem) else item.path.relative_to(self.rootPath()))  # pyright: ignore[reportCallIssue, reportArgumentType]
                elif column_name == "Offset":
                    assert isinstance(item, (DirItem, ResourceItem))
                    key_value = "0x0" if isinstance(item, DirItem) else f"{hex(item.resource.offset())}"
                else:
                    key_value = "N/A"
                key: tuple[Literal[0, 1], str] = (0 if is_dir else 1, key_value)  # Directories first, then by the appropriate column value

            return (*key, list_index)

        def sort_items(items: list[TreeItem | None]):
            items_copy: list[tuple[TreeItem | None, int]] = [(item, i) for i, item in enumerate(items)]
            items_copy.sort(key=lambda x: get_sort_key(x[0], x[1]), reverse=(order == Qt.SortOrder.DescendingOrder))
            for item in items_copy:
                if isinstance(item, DirItem):
                    sort_items(item.children)
            items[:] = [item for item, _ in items_copy]

        if self._root is not None:
            self.layoutAboutToBeChanged.emit()
            sort_items(self._root.children)
            self.layoutChanged.emit()

    def _format_item_path(self, item: TreeItem) -> str:
        if isinstance(item, InstallationItem):
            return str(item.path)
        if isinstance(item, DirItem):
            return str(item.path)
        if isinstance(item, ResourceItem):
            parent = item.parent
            if isinstance(parent, CapsuleItem):
                return f"{parent.resource.filepath()}::{item.resource.filename()}"
            return str(item.resource.filepath())
        return str(item.path)


class ResourceFileSystemModel(KotorFileSystemModel):
    """Backward-compatible alias for KotorFileSystemModel."""


def create_example_directory_structure(base_path: Path):
    if base_path.exists():
        import shutil

        shutil.rmtree(base_path)
    # Create some example directories and files
    (base_path / "Folder1").mkdir(parents=True, exist_ok=True)
    (base_path / "Folder2").mkdir(parents=True, exist_ok=True)
    (base_path / "Folder1" / "Subfolder1").mkdir(parents=True, exist_ok=True)
    (base_path / "Folder1" / "Subfolder1" / "SubSubFolder1").mkdir(parents=True, exist_ok=True)
    (base_path / "Folder1" / "file1.txt").write_text("This is file1 in Folder1")
    (base_path / "Folder1" / "file2.txt").write_text("This is file2 in Folder1")
    (base_path / "Folder2" / "file3.txt").write_text("This is file3 in Folder2")
    (base_path / "Folder2" / "file4.txt").write_text("This is file4 in Folder2")


class MainWindow(QMainWindow):
    def __init__(
        self,
        root_path: Path,
    ):
        super().__init__()
        self.setWindowTitle("QTreeView with HTMLDelegate")

        self.r_file_system_widget: ResourceFileSystemWidget = ResourceFileSystemWidget(self)
        self.r_file_system_widget.setRootPath(str(root_path))

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.r_file_system_widget)
        self.setCentralWidget(central_widget)
        self.setMinimumSize(824, 568)
        self.resize_and_center()

    def resize_and_center(self):
        """Resize and center the window on the screen."""
        self.r_file_system_widget.resize_all_columns()
        screen: QRect = QApplication.primaryScreen().geometry()  # pyright: ignore[reportOptionalMemberAccess]
        new_x: int = (screen.width() - self.width()) // 2
        new_y: int = (screen.height() - self.height()) // 2
        new_x: int = max(0, min(new_x, screen.width() - self.width()))
        new_y: int = max(0, min(new_y, screen.height() - self.height()))
        self.move(new_x, new_y)


if __name__ == "__main__":
    main_init()
    app = QApplication(sys.argv)
    app.setDoubleClickInterval(1)
    base_path: Path = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor").resolve()
    main_window: MainWindow = MainWindow(base_path)

    main_window.show()

    sys.exit(app.exec() if hasattr(app, "exec_") else app.exec())  # pyright: ignore[reportAttributeAccessIssue]
