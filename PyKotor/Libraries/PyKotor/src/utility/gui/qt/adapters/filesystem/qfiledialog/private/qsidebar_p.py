from __future__ import annotations

import os

from typing import TYPE_CHECKING, Any, Iterable, cast

from qtpy.QtCore import (
    QDir,
    QEvent,
    QFileInfo,
    QItemSelectionModel,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    QUrl,
    Qt,
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtGui import (
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QGuiApplication,
    QStandardItemModel,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QFileIconProvider,
    QFileSystemModel,  # pyright: ignore[reportPrivateImportUsage]
    QListView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtCore import (
        QAbstractItemModel,  # pyright: ignore[reportPrivateImportUsage]
        QMetaObject,
        QModelIndex,
        QObject,
        QPoint,
    )
    from qtpy.QtGui import (
        QAbstractFileIconProvider,
        QDragEnterEvent,
        QFocusEvent,
        QIcon,
        QKeyEvent,
        QPixmap,
        _QAction,
    )
    from qtpy.QtWidgets import QStyleOptionViewItem  # pyright: ignore[reportPrivateImportUsage]


class QSideBarDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        value = index.data(QUrlModel.EnabledRole)
        # Match C++: if (value.isValid()) { if (!qvariant_cast<bool>(value)) ... }
        # In Python, value will be None if invalid, or a bool if valid
        if value is not None:
            # Match C++: if (!qvariant_cast<bool>(value))
            if not bool(value):
                option.state &= ~QStyle.StateFlag.State_Enabled  # pyright: ignore[reportAttributeAccessIssue]


# Match C++: constexpr char uriListMimeType[] = "text/uri-list";
_URI_LIST_MIME_TYPE = "text/uri-list"


class QUrlModel(QStandardItemModel):
    """QUrlModel lets you have indexes from a QFileSystemModel to a list.  When QFileSystemModel
    changes them QUrlModel will automatically update.

    Example usage: File dialog sidebar and combo box
    """

    UrlRole: int = Qt.ItemDataRole.UserRole + 1
    EnabledRole: int = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.showFullPath = False
        self.fileSystemModel: QFileSystemModel | None = None
        self.watching: list[QUrlModel.WatchItem] = []
        self.invalidUrls: list[QUrl] = []
        self.modelConnections: list[QMetaObject.Connection] = []  # Store connections for proper cleanup (matching C++)

    def __del__(self):
        """Cleanup connections on destruction, matching C++ destructor behavior."""
        if hasattr(self, "modelConnections"):
            for conn in self.modelConnections:
                if conn is not None:
                    try:
                        conn.disconnect()
                    except (RuntimeError, TypeError, AttributeError):
                        pass

    def mimeTypes(self) -> list[str]:
        # Match C++: return QStringList(QLatin1StringView(uriListMimeType));
        return [_URI_LIST_MIME_TYPE]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # pyright: ignore[reportIncompatibleMethodOverride]
        flags = super().flags(index)
        if index.isValid():
            flags &= ~Qt.ItemFlag.ItemIsEditable
            flags &= ~Qt.ItemFlag.ItemIsDropEnabled

        if index.data(Qt.ItemDataRole.DecorationRole) is None:
            flags &= ~Qt.ItemFlag.ItemIsEnabled

        return flags

    def mimeData(self, indexes: Iterable[QModelIndex]) -> QMimeData:
        """Return MIME data for the given indexes. Matches C++ QUrlModel::mimeData() implementation."""
        # Match C++: QList<QUrl> list;
        list_: list[QUrl] = []
        # Match C++: for (const auto &index : indexes) { if (index.column() == 0) list.append(index.data(UrlRole).toUrl()); }
        for index in indexes:
            if index.column() == 0:
                url_data = index.data(self.UrlRole)
                # Match C++: index.data(UrlRole).toUrl()
                url = url_data if isinstance(url_data, QUrl) else QUrl()
                list_.append(url)  # noqa: PERF401
        # Match C++: QMimeData *data = new QMimeData(); data->setUrls(list); return data;
        data = QMimeData()
        data.setUrls(list_)
        return data

    def canDrop(self, event: QDragEnterEvent) -> bool:
        # Match C++: if (!hasSupportedFormat(event->mimeData())) return false;
        mimedata_event: QMimeData | None = event.mimeData()
        if mimedata_event is None:
            return False
        if not mimedata_event.hasFormat(_URI_LIST_MIME_TYPE):
            return False
        list_: list[QUrl] = mimedata_event.urls()
        assert self.fileSystemModel is not None, "fileSystemModel is None"
        for url in list_:
            idx: QModelIndex = self.fileSystemModel.index(url.toLocalFile())
            if not self.fileSystemModel.isDir(idx):
                return False
        return True

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        # Match C++: if (!hasSupportedFormat(data)) return false;
        if not data.hasFormat(_URI_LIST_MIME_TYPE):
            return False
        self.addUrls(data.urls(), row)
        return True

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Set data for the model index. Matches C++ QUrlModel::setData() implementation."""
        # Match C++: if (value.userType() == QMetaType::QUrl)
        # In Python, we check isinstance(value, QUrl) which is equivalent
        if isinstance(value, QUrl):
            url = value
            assert self.fileSystemModel is not None, "fileSystemModel is None"
            # Match C++: QModelIndex dirIndex = fileSystemModel->index(url.toLocalFile());
            dirIndex = self.fileSystemModel.index(url.toLocalFile())
            # Match C++: On windows the popup display the "C:\", convert to nativeSeparators
            if self.showFullPath:
                # Match C++: QStandardItemModel::setData(index, QDir::toNativeSeparators(fileSystemModel->data(dirIndex, QFileSystemModel::FilePathRole).toString()));
                file_path_data = self.fileSystemModel.data(dirIndex, QFileSystemModel.Roles.FilePathRole)
                file_path_str = str(file_path_data) if file_path_data is not None else ""
                super().setData(index, QDir.toNativeSeparators(file_path_str))
            else:
                # Match C++: QStandardItemModel::setData(index, QDir::toNativeSeparators(...), Qt::ToolTipRole);
                file_path_data = self.fileSystemModel.data(dirIndex, QFileSystemModel.Roles.FilePathRole)
                file_path_str = str(file_path_data) if file_path_data is not None else ""
                super().setData(index, QDir.toNativeSeparators(file_path_str), Qt.ItemDataRole.ToolTipRole)
                # Match C++: QStandardItemModel::setData(index, fileSystemModel->data(dirIndex).toString());
                display_data = self.fileSystemModel.data(dirIndex)
                display_str = str(display_data) if display_data is not None else ""
                super().setData(index, display_str)
            # Match C++: QStandardItemModel::setData(index, fileSystemModel->data(dirIndex, Qt::DecorationRole), Qt::DecorationRole);
            decoration_data = self.fileSystemModel.data(dirIndex, Qt.ItemDataRole.DecorationRole)
            super().setData(index, decoration_data, Qt.ItemDataRole.DecorationRole)
            # Match C++: QStandardItemModel::setData(index, url, UrlRole);
            super().setData(index, url, self.UrlRole)
            return True
        # Match C++: return QStandardItemModel::setData(index, value, role);
        return super().setData(index, value, role)

    def setUrl(
        self,
        index: QModelIndex,
        url: QUrl,
        dirIndex: QModelIndex,  # noqa: N803
    ):
        """Set URL for the model index. Matches C++ QUrlModel::setUrl() implementation."""
        # Ensure url is a QUrl object (handle cases where it might be a string)
        if isinstance(url, str):
            url = QUrl.fromLocalFile(url) if url else QUrl()
        elif not isinstance(url, QUrl):
            url = QUrl(url) if url else QUrl()
        # Match C++: setData(index, url, UrlRole);
        self.setData(index, url, self.UrlRole)
        # Match C++: if (url.path().isEmpty())
        # In Python, path() returns a string, so we check for empty string directly
        url_path = url.path()
        if not url_path or url_path == "":
            assert self.fileSystemModel is not None, "fileSystemModel is None"
            # Match C++: setData(index, fileSystemModel->myComputer());
            self.setData(index, self.fileSystemModel.myComputer())
            # Match C++: setData(index, fileSystemModel->myComputer(Qt::DecorationRole), Qt::DecorationRole);
            self.setData(index, self.fileSystemModel.myComputer(Qt.ItemDataRole.DecorationRole), Qt.ItemDataRole.DecorationRole)
        else:
            # Match C++: QString newName;
            newName: str
            if self.showFullPath:
                # Match C++: newName = QDir::toNativeSeparators(dirIndex.data(QFileSystemModel::FilePathRole).toString());
                file_path_data = dirIndex.data(QFileSystemModel.Roles.FilePathRole)
                newName = QDir.toNativeSeparators(str(file_path_data) if file_path_data is not None else "")
            else:
                # Match C++: newName = dirIndex.data().toString();
                display_data = dirIndex.data()
                newName = str(display_data) if display_data is not None else ""

            assert self.fileSystemModel is not None, "fileSystemModel is None"
            # Match C++: QIcon newIcon = qvariant_cast<QIcon>(dirIndex.data(Qt::DecorationRole));
            decoration_data = dirIndex.data(Qt.ItemDataRole.DecorationRole)
            newIcon = cast("QIcon", decoration_data) if decoration_data is not None else None

            if not dirIndex.isValid():
                # Match C++: const QAbstractFileIconProvider *provider = fileSystemModel->iconProvider();
                provider: QAbstractFileIconProvider | None = self.fileSystemModel.iconProvider()
                if provider:
                    # Match C++: newIcon = provider->icon(QAbstractFileIconProvider::Folder);
                    newIcon = provider.icon(QFileIconProvider.IconType.Folder)
                # Match C++: newName = QFileInfo(url.toLocalFile()).fileName();
                newName = QFileInfo(url.toLocalFile()).fileName()
                # Match C++: if (!invalidUrls.contains(url)) invalidUrls.append(url);
                if url not in self.invalidUrls:
                    self.invalidUrls.append(url)
                # Match C++: setData(index, false, EnabledRole);
                self.setData(index, False, self.EnabledRole)  # noqa: FBT003
            else:
                # Match C++: setData(index, true, EnabledRole);
                self.setData(index, True, self.EnabledRole)  # noqa: FBT003

            # Match C++: // newIcon could be null if fileSystemModel->iconProvider() returns null
            # Match C++: if (!newIcon.isNull()) {
            if newIcon is not None and not newIcon.isNull():
                # Match C++: // Make sure that we have at least 32x32 images
                # Match C++: const QSize size = newIcon.actualSize(QSize(32,32));
                size: QSize = newIcon.actualSize(QSize(32, 32))
                # Match C++: if (size.width() < 32)
                if size.width() < 32:  # noqa: PLR2004
                    # Match C++: const auto widget = qobject_cast<QWidget *>(parent());
                    widget = cast("QWidget | None", self.parent())
                    # Match C++: const auto dpr = widget ? widget->devicePixelRatio() : qApp->devicePixelRatio();
                    app = QGuiApplication.instance()
                    dpr = widget.devicePixelRatio() if isinstance(widget, QWidget) and widget else (app.devicePixelRatio() if isinstance(app, QGuiApplication) else 1.0)  # pyright: ignore[reportAttributeAccessIssue]
                    # Match C++: const auto smallPixmap = newIcon.pixmap(QSize(32, 32), dpr);
                    small_pixmap: QPixmap = newIcon.pixmap(QSize(32, 32), dpr)
                    # Match C++: const auto newPixmap = smallPixmap.scaledToWidth(32 * dpr, Qt::SmoothTransformation);
                    new_pixmap = small_pixmap.scaledToWidth(int(32 * dpr), Qt.TransformationMode.SmoothTransformation)
                    # Match C++: newIcon.addPixmap(newPixmap);
                    newIcon.addPixmap(new_pixmap)

            # Match C++: if (index.data().toString() != newName) setData(index, newName);
            current_data = index.data()
            current_name = str(current_data) if current_data is not None else ""
            if current_name != newName:
                self.setData(index, newName)
            # Match C++: QIcon oldIcon = qvariant_cast<QIcon>(index.data(Qt::DecorationRole));
            old_decoration_data = index.data(Qt.ItemDataRole.DecorationRole)
            oldIcon: QIcon | None = cast("QIcon", old_decoration_data) if old_decoration_data is not None else None
            # Match C++: if (oldIcon.cacheKey() != newIcon.cacheKey()) setData(index, newIcon, Qt::DecorationRole);
            # In C++, both oldIcon and newIcon are QIcon objects (value types), not pointers
            # An empty QIcon has cacheKey 0. The comparison happens regardless of whether newIcon is empty.
            # In Python, we need to handle None (which represents empty QIcon in our context)
            from qtpy.QtGui import QIcon as QtQIcon

            # Get cache keys: None/empty icons have cacheKey 0
            new_icon_cache_key = newIcon.cacheKey() if newIcon is not None and not newIcon.isNull() else 0
            old_icon_cache_key = oldIcon.cacheKey() if oldIcon is not None and not oldIcon.isNull() else 0
            if old_icon_cache_key != new_icon_cache_key:
                # Match C++: setData(index, newIcon, Qt::DecorationRole);
                # In C++, newIcon is always a QIcon object (may be empty), so we pass it directly
                # In Python, if newIcon is None, we use an empty QIcon to match C++ behavior
                icon_to_set = newIcon if newIcon is not None else QtQIcon()
                self.setData(index, icon_to_set, Qt.ItemDataRole.DecorationRole)

    def setUrls(self, list_: list[QUrl]):
        """Set URLs in the model. Matches C++ QUrlModel::setUrls() implementation."""
        # Match C++: removeRows(0, rowCount());
        self.removeRows(0, self.rowCount())
        # Match C++: invalidUrls.clear();
        self.invalidUrls.clear()
        # Match C++: watching.clear();
        self.watching.clear()
        # Match C++: addUrls(list, 0);
        self.addUrls(list_, 0)

    def addUrls(
        self,
        list_: list[QUrl],
        row: int = -1,
        move: bool = True,
    ):
        """Add URLs to the model at the specified row. Matches C++ QUrlModel::addUrls() implementation."""
        # Match C++: if (row == -1) row = rowCount();
        if row == -1:
            row = self.rowCount()
        # Match C++: row = qMin(row, rowCount());
        row = min(row, self.rowCount())
        assert self.fileSystemModel is not None, "fileSystemModel is None"
        # Match C++: const auto rend = list.crend(); for (auto it = list.crbegin(); it != rend; ++it)
        for it in reversed(list_):
            # Ensure url is a QUrl object (handle cases where it might be a string)
            if isinstance(it, str):
                url = QUrl.fromLocalFile(it) if it else QUrl()
            elif isinstance(it, QUrl):
                url = it
            else:
                url = QUrl(it) if it else QUrl()
            # Match C++: if (!url.isValid() || url.scheme() != "file"_L1) continue;
            if not url.isValid() or url.scheme() != "file":
                continue
            # Match C++: const QString cleanUrl = QDir::cleanPath(url.toLocalFile());
            clean_url: str = QDir.cleanPath(url.toLocalFile())
            # Match C++: if (!cleanUrl.isEmpty()) url = QUrl::fromLocalFile(cleanUrl);
            # Note: If cleanUrl is empty, we keep the original URL (matching C++ behavior)
            if clean_url:
                url = QUrl.fromLocalFile(clean_url)
            # If cleanUrl is empty, we continue with the original URL, but the later
            # fileSystemModel->index(cleanUrl) check will fail, effectively skipping this entry

            # Match C++: for (int j = 0; move && j < rowCount(); ++j)
            if move:
                for j in range(self.rowCount()):
                    # Match C++: QString local = index(j, 0).data(UrlRole).toUrl().toLocalFile();
                    local = cast("QUrl", self.index(j, 0).data(self.UrlRole)).toLocalFile()
                    # Match C++: #if defined(Q_OS_WIN) const Qt::CaseSensitivity cs = Qt::CaseInsensitive; #else const Qt::CaseSensitivity cs = Qt::CaseSensitive; #endif
                    # Match C++: if (!cleanUrl.compare(local, cs))
                    if os.name == "nt":
                        # Case-insensitive comparison on Windows (equivalent to Qt::CaseInsensitive)
                        if clean_url.casefold() == local.casefold():
                            # Match C++: removeRow(j); if (j <= row) row--; break;
                            self.removeRow(j)
                            if j <= row:
                                row -= 1
                            break
                    else:
                        # Case-sensitive comparison on Unix-like systems (equivalent to Qt::CaseSensitive)
                        if clean_url == local:
                            # Match C++: removeRow(j); if (j <= row) row--; break;
                            self.removeRow(j)
                            if j <= row:
                                row -= 1
                            break
            # Match C++: row = qMax(row, 0);
            row = max(row, 0)
            # Match C++: QModelIndex idx = fileSystemModel->index(cleanUrl);
            idx = self.fileSystemModel.index(clean_url)
            # Match C++: if (!fileSystemModel->isDir(idx)) continue;
            if not self.fileSystemModel.isDir(idx):
                continue
            # Match C++: insertRows(row, 1);
            self.insertRows(row, 1)
            # Match C++: setUrl(index(row, 0), url, idx);
            self.setUrl(self.index(row, 0), url, idx)
            # Match C++: watching.append({idx, cleanUrl});
            self.watching.append(self.WatchItem(idx, clean_url))

    def urls(self) -> list[QUrl]:
        """Return the complete list of URLs. Matches C++ QUrlModel::urls() implementation."""
        # Match C++: QList<QUrl> list; const int numRows = rowCount(); list.reserve(numRows);
        list_: list[QUrl] = []
        num_rows: int = self.rowCount()
        # Match C++: for (int i = 0; i < numRows; ++i) list.append(data(index(i, 0), UrlRole).toUrl());
        for i in range(num_rows):
            url_data = self.data(self.index(i, 0), self.UrlRole)
            url = url_data if isinstance(url_data, QUrl) else QUrl()
            list_.append(url)
        return list_

    def setFileSystemModel(self, model: QFileSystemModel):
        if model == self.fileSystemModel:
            return
        if self.fileSystemModel is not None:
            # Disconnect all previous connections
            if hasattr(self, "modelConnections"):
                for conn in self.modelConnections:
                    if conn is not None:
                        try:
                            conn.disconnect()
                        except (RuntimeError, TypeError):
                            pass
            else:
                # Fallback to direct disconnection if modelConnections doesn't exist
                self.fileSystemModel.dataChanged.disconnect(self.dataChanged)
                self.fileSystemModel.layoutChanged.disconnect(self.layoutChanged)
                self.fileSystemModel.rowsRemoved.disconnect(self.layoutChanged)
        self.fileSystemModel = model
        if self.fileSystemModel is not None:
            # Store connections for proper cleanup (matching C++ modelConnections)
            # Match C++: modelConnections = { connect(...), connect(...), connect(...) };
            self.modelConnections = [
                self.fileSystemModel.dataChanged.connect(self.dataChanged),
                self.fileSystemModel.layoutChanged.connect(self.layoutChanged),
                self.fileSystemModel.rowsRemoved.connect(self.layoutChanged),
            ]
        # Match C++: when fileSystemModel is nullptr, modelConnections array is NOT modified
        # It keeps its previous value (which may contain disconnected/invalid connections)
        # In Python, we preserve the existing modelConnections list (may be empty or contain stale connections)
        # This matches C++ behavior where the array always exists but connections may be invalid
        self.clear()
        self.insertColumns(0, 1)

    def dataChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex):  # noqa: N803
        """Handle data changes in the file system model. Matches C++ QUrlModel::dataChanged() implementation."""
        # Match C++: QModelIndex parent = topLeft.parent();
        parent = topLeft.parent()
        # Match C++: for (int i = 0; i < watching.size(); ++i)
        for i in range(len(self.watching)):
            # Match C++: QModelIndex index = watching.at(i).index;
            index = self.watching[i].index
            # Match C++: if (index.model() && topLeft.model()) { Q_ASSERT(index.model() == topLeft.model()); }
            if index.model() is not None and topLeft.model() is not None:
                assert index.model() == topLeft.model(), "Model mismatch in dataChanged"
            # Match C++: if (index.row() >= topLeft.row() && index.row() <= bottomRight.row() && ...)
            if (
                index.row() >= topLeft.row()
                and index.row() <= bottomRight.row()
                and index.column() >= topLeft.column()
                and index.column() <= bottomRight.column()
                and index.parent() == parent
            ):
                # Match C++: changed(watching.at(i).path);
                self.changed(self.watching[i].path)

    def layoutChanged(self):
        """Handle layout changes in the file system model. Matches C++ QUrlModel::layoutChanged() implementation."""
        # Match C++: QStringList paths; paths.reserve(watching.size());
        paths: list[str] = []
        # Match C++: for (const WatchItem &item : std::as_const(watching)) paths.append(item.path);
        for item in self.watching:
            paths.append(item.path)
        # Match C++: watching.clear();
        self.watching.clear()
        assert self.fileSystemModel is not None, "fileSystemModel is None"
        # Match C++: for (const auto &path : paths) { QModelIndex newIndex = fileSystemModel->index(path); watching.append({newIndex, path}); if (newIndex.isValid()) changed(path); }
        for path in paths:
            newIndex: QModelIndex = self.fileSystemModel.index(path)
            self.watching.append(self.WatchItem(newIndex, path))
            if newIndex.isValid():
                self.changed(path)

    def changed(self, path: str):
        """Update data for items matching the given path. Matches C++ QUrlModel::changed() implementation."""
        # Match C++: for (int i = 0; i < rowCount(); ++i)
        for i in range(self.rowCount()):
            # Match C++: QModelIndex idx = index(i, 0);
            idx: QModelIndex = self.index(i, 0)
            # Match C++: if (idx.data(UrlRole).toUrl().toLocalFile() == path)
            url_data = idx.data(self.UrlRole)
            url = url_data if isinstance(url_data, QUrl) else QUrl()
            if url.toLocalFile() == path:
                # Match C++: setData(idx, idx.data(UrlRole).toUrl());
                self.setData(idx, url)

    class WatchItem:  # noqa: D106
        def __init__(self, index: QModelIndex, path: str):
            self.index: QModelIndex = index
            self.path: str = path


class QSidebar(QListView):
    goToUrl = Signal(QUrl)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.urlModel: QUrlModel | None = None

    def __del__(self):
        """Destructor matching C++ QSidebar::~QSidebar() implementation (empty)."""
        pass

    def urls(self) -> list[QUrl]:
        assert self.urlModel is not None, f"{type(self).__name__}.urls: No URL model setup."
        return self.urlModel.urls()

    def setUrls(self, urls: list[QUrl]) -> None:
        assert self.urlModel is not None, f"{type(self).__name__}.setUrls: No URL model setup."
        self.urlModel.setUrls(urls)

    def addUrls(self, urls: list[QUrl], row: int) -> None:
        """Add URLs to the sidebar at the specified row.

        Matches C++ inline implementation: urlModel->addUrls(list, row)
        The move parameter defaults to True in QUrlModel.addUrls.
        """
        assert self.urlModel is not None, f"{type(self).__name__}.addUrls: No URL model setup."
        self.urlModel.addUrls(urls, row)

    def setModelAndUrls(self, model: QFileSystemModel, newUrls: list[QUrl]) -> None:  # noqa: N803
        """Set model and URLs. Matches C++ QSidebar::setModelAndUrls() implementation."""
        # Match C++: setUniformItemSizes(true);
        self.setUniformItemSizes(True)
        # Match C++: urlModel = new QUrlModel(this);
        self.urlModel = QUrlModel(self)
        # Match C++: urlModel->setFileSystemModel(model);
        self.urlModel.setFileSystemModel(model)
        # Match C++: setModel(urlModel);
        self.setModel(self.urlModel)
        # Match C++: setItemDelegate(new QSideBarDelegate(this));
        self.setItemDelegate(QSideBarDelegate(self))

        # Match C++: connect(selectionModel(), &QItemSelectionModel::currentChanged, this, &QSidebar::clicked);
        sel_model: QItemSelectionModel | None = self.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self.clicked)
        # Match C++: #if QT_CONFIG(draganddrop) setDragDropMode(QAbstractItemView::DragDrop); #endif
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        # Match C++: #if QT_CONFIG(menu) setContextMenuPolicy(Qt::CustomContextMenu); connect(...); #endif
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        # Match C++: urlModel->setUrls(newUrls);
        self.urlModel.setUrls(newUrls)
        # Match C++: setCurrentIndex(this->model()->index(0,0));
        sidebar_model: QAbstractItemModel | None = self.model()
        if sidebar_model is not None:
            self.setCurrentIndex(sidebar_model.index(0, 0))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.urlModel and self.urlModel.canDrop(event):
            QListView.dragEnterEvent(self, event)

    def sizeHint(self) -> QSize:
        sidebar_model: QAbstractItemModel | None = self.model()
        if sidebar_model is None:
            return QListView.sizeHint(self)
        return self.sizeHintForIndex(sidebar_model.index(0, 0)) + QSize(2 * self.frameWidth(), 2 * self.frameWidth())

    def selectUrl(self, url: QUrl) -> None:
        """Select URL in sidebar. Matches C++ QSidebar::selectUrl() implementation."""
        # Match C++: disconnect(selectionModel(), &QItemSelectionModel::currentChanged, this, &QSidebar::clicked);
        sel_model: QItemSelectionModel | None = self.selectionModel()
        if sel_model is not None:
            try:
                sel_model.currentChanged.disconnect(self.clicked)
            except (TypeError, RuntimeError):
                # Signal was not connected, which is fine
                pass

        # Match C++: selectionModel()->clear();
        if sel_model is not None:
            sel_model.clear()
        # Match C++: for (int i = 0; i < model()->rowCount(); ++i)
        sidebar_model: QAbstractItemModel | None = self.model()
        if sidebar_model is None:
            return
        # Match C++: for (int i = 0; i < model()->rowCount(); ++i)
        for i in range(sidebar_model.rowCount()):
            # Match C++: if (model()->index(i, 0).data(QUrlModel::UrlRole).toUrl() == url)
            url_data = sidebar_model.index(i, 0).data(QUrlModel.UrlRole)
            url_from_data = url_data if isinstance(url_data, QUrl) else QUrl()
            if url_from_data == url:
                # Match C++: emit goToUrl(url);
                self.goToUrl.emit(url)
                # Match C++: selectionModel()->setCurrentIndex(model()->index(i, 0), QItemSelectionModel::SelectCurrent);
                if sel_model is not None:
                    sel_model.setCurrentIndex(sidebar_model.index(i, 0), QItemSelectionModel.SelectionFlag.SelectCurrent)
                # Match C++: break;
                break
        # Match C++: connect(selectionModel(), &QItemSelectionModel::currentChanged, this, &QSidebar::clicked);
        if sel_model is not None:
            sel_model.currentChanged.connect(self.clicked)

    def showContextMenu(self, position: QPoint) -> None:
        """Show context menu for sidebar items. Matches C++ QSidebar::showContextMenu() implementation."""
        # Match C++: QList<QAction *> actions;
        actions: list[_QAction] = []
        # Match C++: if (indexAt(position).isValid())
        if self.indexAt(position).isValid():
            # Match C++: QAction *action = new QAction(QFileDialog::tr("Remove"), this);
            # Import QFileDialog to use its tr() method, matching C++ QFileDialog::tr()
            from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialog as PythonQFileDialog

            action = QAction(PythonQFileDialog.tr("Remove"), self)
            # Match C++: if (indexAt(position).data(QUrlModel::UrlRole).toUrl().path().isEmpty()) action->setEnabled(false);
            url_data = self.indexAt(position).data(QUrlModel.UrlRole)
            url = url_data if isinstance(url_data, QUrl) else QUrl()
            url_path = url.path()
            if not url_path or url_path == "":
                action.setEnabled(False)
            # Match C++: connect(action, &QAction::triggered, this, &QSidebar::removeEntry);
            action.triggered.connect(self.removeEntry)
            # Match C++: actions.append(action);
            actions.append(action)
        # Match C++: if (actions.size() > 0) QMenu::exec(actions, mapToGlobal(position));
        if actions:
            QMenu.exec(actions, self.mapToGlobal(position))

    def removeEntry(self) -> None:
        """Remove selected entries from the sidebar. Matches C++ QSidebar::removeEntry() implementation."""
        sel_model: QItemSelectionModel | None = self.selectionModel()
        if sel_model is None:
            return
        sidebar_model: QAbstractItemModel | None = self.model()
        if sidebar_model is None:
            return
        # Match C++: const QList<QModelIndex> idxs = selectionModel()->selectedIndexes();
        indexes: list[QModelIndex] = sel_model.selectedIndexes()
        # Match C++: // Create a list of QPersistentModelIndex as the removeRow() calls below could invalidate the indexes in "idxs"
        # Match C++: const QList<QPersistentModelIndex> persIndexes(idxs.cbegin(), idxs.cend());
        persistent_indexes: list[QPersistentModelIndex] = [QPersistentModelIndex(idx) for idx in indexes]
        # Match C++: for (const QPersistentModelIndex &persistent : persIndexes)
        for persistent in persistent_indexes:
            # Match C++: if (!persistent.data(QUrlModel::UrlRole).toUrl().path().isEmpty())
            # Only remove rows where path is NOT empty (user-added bookmarks)
            # System entries like "Computer" have empty paths and should not be removed
            url_data = persistent.data(QUrlModel.UrlRole)
            url = url_data if isinstance(url_data, QUrl) else QUrl()
            url_path = url.path()
            if url_path and url_path != "":
                # Match C++: model()->removeRow(persistent.row());
                sidebar_model.removeRow(persistent.row())

    def clicked(self, index: QModelIndex) -> None:
        """Handle click on sidebar item. Matches C++ QSidebar::clicked() implementation."""
        sidebar_model: QAbstractItemModel | None = self.model()
        if sidebar_model is None:
            return
        # Match C++: QUrl url = model()->index(index.row(), 0).data(QUrlModel::UrlRole).toUrl();
        url_data = sidebar_model.index(index.row(), 0).data(QUrlModel.UrlRole)
        url = url_data if isinstance(url_data, QUrl) else QUrl()
        # Match C++: selectUrl(url);
        self.selectUrl(url)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Handle focus in event. Matches C++ QSidebar::focusInEvent() implementation."""
        # Match C++: QAbstractScrollArea::focusInEvent(event);
        QAbstractScrollArea.focusInEvent(self, event)
        # Match C++: viewport()->update();
        viewport: QWidget | None = self.viewport()
        if viewport is not None:
            viewport.update()

    def event(self, event: QEvent) -> bool:
        """Handle events. Matches C++ QSidebar::event() implementation."""
        # Match C++: if (event->type() == QEvent::KeyRelease)
        if event.type() == QEvent.Type.KeyRelease:
            # Match C++: QKeyEvent *ke = static_cast<QKeyEvent *>(event);
            key_event = cast("QKeyEvent", event)
            # Match C++: if (ke->key() == Qt::Key_Delete)
            if key_event.key() == Qt.Key.Key_Delete:
                # Match C++: removeEntry(); return true;
                self.removeEntry()
                return True
        # Match C++: return QListView::event(event);
        return QListView.event(self, event)
