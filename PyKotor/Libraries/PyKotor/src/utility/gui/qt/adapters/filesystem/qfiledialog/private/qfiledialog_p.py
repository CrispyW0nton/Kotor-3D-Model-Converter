from __future__ import annotations

import os
import sys
import typing

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import qtpy

from qtpy.QtCore import (
    QByteArray,
    QDir,
    QFile,
    QFileInfo,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSettings,
    QSize,
    QUrl,
    Qt,
)
from qtpy.QtGui import (
    QFontMetrics,
    QKeyEvent,
    QKeySequence,
    QPalette,
    QStandardItemModel,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QActionGroup,  # pyright: ignore[reportPrivateImportUsage]
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog as RealQFileDialog,
    QFileIconProvider,
    QFileSystemModel,  # pyright: ignore[reportPrivateImportUsage]
    QHeaderView,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,  # pyright: ignore[reportPrivateImportUsage]
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QTreeView,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from utility.gui.qt.adapters.filesystem.qfiledialog.private.qsidebar_p import QUrlModel
from utility.gui.qt.adapters.kernel.qplatformdialoghelper.qplatformdialoghelper import QPlatformFileDialogHelper
from utility.gui.qt.tools.unifiers import sip_enum_to_int

if TYPE_CHECKING:
    from qtpy.QtCore import (
        QAbstractItemModel,
        QAbstractProxyModel,
        QObject,
        QPoint,
        QRect,
    )
    from qtpy.QtGui import (
        QKeyEvent,
        QPaintEvent,
        QStandardItem,
    )
    from qtpy.QtWidgets import (
        QHeaderView,
        QPushButton,
        QWidget,
    )

    from utility.gui.qt.adapters.filesystem.qfiledialog.private.qsidebar_p import QSidebar
    from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import (
        QFileDialog,
        QFileDialog as PublicQFileDialog,
        QFileDialogOptions,  # noqa: TC004
    )
    from utility.gui.qt.adapters.filesystem.qfiledialog.ui_qfiledialog import Ui_QFileDialog


def qt_make_filter_list(filter_arg: str) -> list[str]:
    if not filter_arg:
        return []
    separator: str = ";;" if ";;" in filter_arg else "\n"
    return [part.strip() for part in filter_arg.split(separator) if part.strip()]


class QFileDialogOptionsPrivate:
    def __init__(self):
        # Prevent circular import
        self.viewMode: RealQFileDialog.ViewMode = RealQFileDialog.ViewMode.Detail
        self.fileMode: RealQFileDialog.FileMode = RealQFileDialog.FileMode.AnyFile
        self.acceptMode: RealQFileDialog.AcceptMode = RealQFileDialog.AcceptMode.AcceptOpen
        self.labelTexts: dict[RealQFileDialog.DialogLabel, str] = {}
        for label in (
            RealQFileDialog.DialogLabel.LookIn,
            RealQFileDialog.DialogLabel.FileName,
            RealQFileDialog.DialogLabel.FileType,
            RealQFileDialog.DialogLabel.Accept,
            RealQFileDialog.DialogLabel.Reject,
        ):
            self.labelTexts[label] = ""
        self.filter: QDir.Filter = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs
        self.sidebarUrls: list[QUrl] = []
        self.nameFilters: list[str] = []
        self.mimeTypeFilters: list[str] = []
        self.defaultSuffix: str = ""
        self.history: list[str] = []
        self.initialDirectory: QUrl = QUrl()
        self.initiallySelectedMimeTypeFilter: str = ""
        self.initiallySelectedNameFilter: str = ""
        self.initiallySelectedFiles: list[QUrl] = []
        self.supportedSchemes: list[str] = []
        self.useDefaultNameFilters: bool = True
        self.options: RealQFileDialog.Options = RealQFileDialog.Options(
            RealQFileDialog.Option.DontUseNativeDialog if hasattr(RealQFileDialog.Option, "DontUseNativeDialog") else RealQFileDialog.DontUseNativeDialog
        )  # noqa: E501  # pyright: ignore[reportAttributeAccessIssue]
        self.sidebar_urls: list[QUrl] = []
        self.default_suffix: str = ""


class QFSCompleter(QCompleter):
    def __init__(
        self,
        fs_model: QFileSystemModel,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.sourceModel: QFileSystemModel = fs_model
        self.sourceModel.setRootPath("")
        self.proxyModel: QAbstractProxyModel | None = None
        self.setModel(self.sourceModel)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def pathFromIndex(
        self,
        index: QModelIndex,
    ) -> str:
        dirModel: QAbstractItemModel | QFileSystemModel | None = self.proxyModel.sourceModel() if self.proxyModel else self.sourceModel
        assert isinstance(dirModel, QFileSystemModel), f"{self.__class__.__name__}.pathFromIndex: Expected QFileSystemModel, got {type(dirModel).__name__}"
        current_location = Path(dirModel.rootPath().strip())
        path = os.path.abspath(os.path.normpath(str(index.data(QFileSystemModel.Roles.FilePathRole)).strip()))  # noqa: PTH100
        relative_path = os.path.relpath(path, str(current_location))
        return os.path.normpath(relative_path).strip()

    def splitPath(
        self,
        path: str,
    ) -> list[str]:
        return list(Path(self.qt_tildeExpansion(os.path.normpath(path.strip()))).absolute().parts)

    def setSourceModel(
        self,
        model: QFileSystemModel,
    ) -> None:
        self.sourceModel = model
        if not self.proxyModel:
            self.setModel(model)

    def setProxyModel(
        self,
        model: QAbstractProxyModel,
    ) -> None:
        self.proxyModel = model
        if model:
            model.setSourceModel(self.sourceModel)
            self.setModel(model)
        else:
            self.setModel(self.sourceModel)

    def qt_tildeExpansion(
        self,
        path: str,
    ) -> str:
        if path.startswith("~"):
            return os.path.expanduser(path)  # noqa: PTH111
        return path


@dataclass
class HistoryItem:
    """Represents an item in the file dialog history."""

    path: str
    selection: list[QPersistentModelIndex]


def _qt_get_directory(
    url: QUrl,
    local: QFileInfo,
) -> QUrl:
    if url.isLocalFile():
        info: QFileInfo = local
        if not local.isAbsolute():
            info = QFileInfo(QDir.current(), url.toLocalFile())
        path_info = QFileInfo(info.absolutePath())
        if not path_info.exists() or not path_info.isDir():
            return QUrl()
        if info.exists() and info.isDir():
            return QUrl.fromLocalFile(QDir.cleanPath(info.absoluteFilePath()))
        return QUrl.fromLocalFile(path_info.absoluteFilePath())
    return url


class QFileDialogPrivate:
    """Private implementation of QFileDialog."""

    def __init__(  # noqa: PLR0913
        self,
        q: QFileDialog,
        *,
        selection: str | None = None,
        directory: QUrl | None = None,
        mode: RealQFileDialog.FileMode | None = None,
        filter: str | None = None,  # noqa: A002
        options: QFileDialogOptions | None = None,
        caption: str | None = None,
    ):
        """Initialize QFileDialogPrivate, calls _init_dialog_properties and _setup_dialog_components to setup the ui components."""
        self._public: QFileDialog = q
        self.nativeDialogInUse: bool = False
        self.platformHelper: QPlatformFileDialogHelper | None = None
        self.model: QFileSystemModel | None = None
        self.proxyModel: QAbstractProxyModel | None = None
        self.lastVisitedDir: QUrl = QUrl()
        self.currentHistoryLocation: int = -1
        self.currentHistory: list[HistoryItem] = []
        self._ignoreHistoryChange: bool = False

        self.acceptLabel: str = "&Open"
        self.showActionGroup: QActionGroup = QActionGroup(q)
        self.renameAction = QAction("&Rename", q)
        self.deleteAction = QAction("&Delete", q)
        self.showHiddenAction = QAction("&Show Hidden", q)
        self.newFolderAction = QAction("&New Folder", q)

        self.completer: QFSCompleter | None = None
        self.useDefaultCaption: bool = True

        # Signal disconnection tracking for open() method (matches C++ QFileDialogPrivate)
        # Note: QPointer is not available in qtpy, so we use a regular reference
        # In Python, object lifetime is managed differently, so a regular reference is sufficient
        self.receiverToDisconnectOnClose: QObject | Callable | Signal | None = None
        self.memberToDisconnectOnClose: QByteArray = QByteArray()
        self.signalToDisconnectOnClose: QByteArray = QByteArray()

        # Memory of what was read from QSettings in restoreState() in case widgets are not used
        self.splitterState: QByteArray = QByteArray()
        self.headerData: QByteArray = QByteArray()
        self.sidebarUrls: list[QUrl] = []
        self.defaultIconProvider: QFileIconProvider = QFileIconProvider()

        # QFileDialogArgs struct, used in some static methods of QFileDialog.
        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialogOptions

        self.options: QFileDialogOptions = QFileDialogOptions() if options is None else options
        self.filter: str = "" if filter is None else filter
        self.setWindowTitle: str = "" if caption is None else caption  # caption
        any_file = RealQFileDialog.FileMode.AnyFile if hasattr(RealQFileDialog.FileMode, "AnyFile") else RealQFileDialog.AnyFile  # pyright: ignore[reportAttributeAccessIssue]
        self.mode: RealQFileDialog.FileMode = any_file if mode is None else mode
        self.options.setOption(QFileDialogOptions.FileDialogOption.DontUseNativeDialog, True)  # TODO(th3w1zard1): native dialog, disable for now.  # noqa: FBT003

        # init_directory
        self.directory: str = "" if directory is None else directory.toLocalFile()
        self.selection: str = "" if selection is None else selection

        self.qFileDialogUi: Ui_QFileDialog | None = None
        # from utility.gui.qt.filesystem.explorer.qfiledialog.private.ui_qfiledialog import Ui_QFileDialog
        # self.qFileDialogUi: Ui_QFileDialog = Ui_QFileDialog()
        # self.qFileDialogUi.setupUi(q)
        # self.init_directory(url=QUrl.fromLocalFile(self.directory))

    def init_directory(self, url: QUrl) -> None:
        """Initialize the directory and selection from the given URL.

        This is a QFileDialogArgs constructor in the Qt src.
        We handle slightly differently, e.g. they assign a method pointer to self.directory.
        """
        local: QFileInfo = QFileInfo(url.toLocalFile())
        # default case, re-use QFileInfo to avoid stat'ing
        if not url.isEmpty():
            self.directory = str(_qt_get_directory(url, local))
        # Get the initial directory URL
        if url.isEmpty():
            lastVisited: QUrl = self.lastVisitedDir
            if os.path.normpath(lastVisited.toLocalFile()).strip("\\").strip("/") != os.path.normpath(self.directory).strip("\\").strip("/"):
                self.directory = str(_qt_get_directory(lastVisited, local))
        # The initial directory can contain both the initial directory
        # and initial selection, e.g. /home/user/foo.txt
        if self.selection.strip() and not url.isEmpty():
            if url.isLocalFile():
                if not local.isDir():
                    self.selection = local.fileName()
            else:
                # With remote URLs we can only assume.
                self.selection = url.fileName()

    def init(self, q: QFileDialog) -> None:
        """Create widgets, layout and set default values.

        Updates attributes after construction, allowing us to start the dialog from any
        reused instance.

        This method sets up the file dialog based on the provided arguments,
        including setting the window title, file mode, name filter, directory,
        and selection. It also handles the display of the dialog and the use of
        native dialogs if available.
        """
        self._public = q
        if self.setWindowTitle.strip():  # if args.caption.isEmpty():
            self.useDefaultCaption = False
            q.setWindowTitle(self.setWindowTitle)

        q.setAcceptMode(RealQFileDialog.AcceptMode.AcceptOpen)
        self.nativeDialogInUse = self.platformFileDialogHelper() is not None
        if not self.nativeDialogInUse:
            self.createWidgets()
        q.setFileMode(RealQFileDialog.FileMode.AnyFile)
        if self.filter.strip():
            q.setNameFilter(self.filter)
        dirUrl: QUrl = QUrl.fromLocalFile(self.directory)
        # QTBUG-70798, prevent the default blocking the restore logic.
        dontStoreDir: bool = not dirUrl.isValid() and not self.lastVisitedDir.isValid()
        q.setDirectoryUrl(dirUrl)
        if dontStoreDir:
            self.lastVisitedDir.clear()
        if dirUrl.isLocalFile():
            q.selectFile(self.selection)
        else:
            q.selectUrl(dirUrl)

        q = self._public
        if hasattr(QSettings, "UserScope") or not self.restoreFromSettings():
            # Try to restore from the FileDialog settings group; if it fails, fall back
            # to the pre-5.5 QByteArray serialized settings.
            settings = QSettings(QSettings.Scope.UserScope, "QtProject")
            value = settings.value("Qt/filedialog_py", QByteArray())
            if isinstance(value, QByteArray):
                q.restoreState(value)
            else:
                RobustLogger().warning(f"{self.__class__.__name__}.init: Invalid value type for Qt/filedialog_py: {type(value).__name__}")

        if hasattr(Qt, "Q_EMBEDDED_SMALLSCREEN"):  # FIXME(th3w1zard1): incorrect check, look at docs later.
            assert self.qFileDialogUi is not None, "QFileDialogUi is None"
            self.qFileDialogUi.lookInLabel.setVisible(False)
            self.qFileDialogUi.fileNameLabel.setVisible(False)
            self.qFileDialogUi.fileTypeLabel.setVisible(False)
            self.qFileDialogUi.sidebar.hide()

        sizeHint = q.sizeHint()
        if sizeHint.isValid():
            q.resize(sizeHint)

    def createWidgets(self) -> None:  # noqa: PLR0915
        """Initialize and configure all the UI components of the file dialog.
        This is essential for creating the visual interface of the dialog.

        If this function is removed, the dialog would lack its UI components,
        rendering it non-functional and unable to display any interface to the user.
        """
        if self.qFileDialogUi:
            return
        q = self._public

        # This function is sometimes called late (e.g as a fallback from setVisible). In that case we
        # need to ensure that the following UI code (setupUI in particular) doesn't reset any explicitly
        # set window state or geometry.
        self.preSize: QSize = q.size() if q.testAttribute(Qt.WidgetAttribute.WA_Resized) else QSize()
        self.preState: Qt.WindowState = q.windowState()

        self.model = QFileSystemModel(q)
        self.model.setIconProvider(self.defaultIconProvider)
        self.model.setFilter(self.options.filter())
        self.model.setObjectName("qt_filesystem_model")
        if self.platformFileDialogHelper():
            self.model.setNameFilterDisables(self.platformFileDialogHelper().defaultNameFilterDisables())
        else:
            self.model.setNameFilterDisables(False)
        # self.model.d_func().disableRecursiveSort = True  # NOTE: This is QFileSystemModelPrivate::disableRecursiveSort
        self.model.fileRenamed.connect(self._q_fileRenamed)  # noqa: SLF001
        self.model.rootPathChanged.connect(self._q_pathChanged)  # noqa: SLF001
        self.model.rowsInserted.connect(self._q_rowsInserted)  # noqa: SLF001
        self.model.setReadOnly(False)

        # Initialize UI
        from utility.gui.qt.adapters.filesystem.qfiledialog.ui_qfiledialog import Ui_QFileDialog

        self.qFileDialogUi = Ui_QFileDialog()
        self.qFileDialogUi.setupUi(q)
        button_box: QDialogButtonBox = self.qFileDialogUi.buttonBox
        button_box.setStandardButtons(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)

        open_button: QPushButton | None = button_box.button(QDialogButtonBox.StandardButton.Open)
        if open_button is not None:
            open_button.setObjectName("openButton")
            open_button.setEnabled(False)

        cancel_button: QPushButton | None = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setObjectName("cancelButton")

        # Setup sidebar
        initialBookmarks: list[QUrl] = [QUrl("file:"), QUrl.fromLocalFile(QDir.homePath())]
        self.qFileDialogUi.sidebar.setModelAndUrls(self.model, initialBookmarks)
        self.qFileDialogUi.sidebar.goToUrl.connect(self._q_goToUrl)  # noqa: SLF001

        # Setup button box
        self.qFileDialogUi.buttonBox.accepted.connect(q.accept)
        self.qFileDialogUi.buttonBox.rejected.connect(q.reject)

        self.qFileDialogUi.lookInCombo.setFileDialogPrivate(self)
        self.qFileDialogUi.lookInCombo.setHistory(self.options.history())
        self.qFileDialogUi.lookInCombo.textActivated.connect(self._q_goToDirectory)  # noqa: SLF001
        self.qFileDialogUi.lookInCombo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.qFileDialogUi.lookInCombo.setDuplicatesEnabled(False)

        # filename
        self.qFileDialogUi.fileNameEdit.setFileDialogPrivate(self)
        self.qFileDialogUi.fileNameLabel.setBuddy(self.qFileDialogUi.fileNameEdit)
        self.completer = QFSCompleter(self.model, q)
        self.qFileDialogUi.fileNameEdit.setCompleter(self.completer)

        self.qFileDialogUi.fileNameEdit.setInputMethodHints(Qt.InputMethodHint.ImhNoPredictiveText)
        self.qFileDialogUi.fileNameEdit.textChanged.connect(self._q_autoCompleteFileName)  # noqa: SLF001
        self.qFileDialogUi.fileNameEdit.textChanged.connect(self._q_updateOkButton)  # noqa: SLF001
        self.qFileDialogUi.fileNameEdit.returnPressed.connect(q.accept)

        # Setup file type combo
        self.qFileDialogUi.fileTypeCombo.setDuplicatesEnabled(False)
        self.qFileDialogUi.fileTypeCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.qFileDialogUi.fileTypeCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.qFileDialogUi.fileTypeCombo.activated.connect(self._q_useNameFilter)  # noqa: SLF001
        self.qFileDialogUi.fileTypeCombo.textActivated.connect(q.filterSelected)

        self.qFileDialogUi.listView.setFileDialogPrivate(self)
        self.qFileDialogUi.listView.setModel(self.model)
        self.qFileDialogUi.listView.activated.connect(self._q_enterDirectory)  # noqa: SLF001
        self.qFileDialogUi.listView.customContextMenuRequested.connect(self._q_showContextMenu)  # noqa: SLF001
        shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.qFileDialogUi.listView)
        shortcut.activated.connect(self._q_deleteCurrent)  # noqa: SLF001

        self.qFileDialogUi.treeView.setFileDialogPrivate(self)
        self.qFileDialogUi.treeView.setModel(self.model)
        self.qFileDialogUi.treeView.setSelectionModel(self.qFileDialogUi.listView.selectionModel())
        self.qFileDialogUi.treeView.activated.connect(self._q_enterDirectory)  # noqa: SLF001
        self.qFileDialogUi.treeView.customContextMenuRequested.connect(self._q_showContextMenu)  # noqa: SLF001
        shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.qFileDialogUi.treeView)
        shortcut.activated.connect(self._q_deleteCurrent)  # noqa: SLF001

        treeHeader: QHeaderView | None = self.qFileDialogUi.treeView.header()
        assert treeHeader is not None, "treeHeader is None"
        fm = QFontMetrics(q.font())
        treeHeader.resizeSection(0, fm.horizontalAdvance("wwwwwwwwwwwwwwwwwwwwwwwwww"))
        treeHeader.resizeSection(1, fm.horizontalAdvance("128.88 GB"))
        treeHeader.resizeSection(2, fm.horizontalAdvance("mp3Folder"))
        treeHeader.resizeSection(3, fm.horizontalAdvance("10/29/81 02:02PM"))
        treeHeader.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        # Setup show action group
        showActionGroup = QActionGroup(q)
        showActionGroup.setExclusive(False)
        showActionGroup.triggered.connect(self._q_showHeader)  # noqa: SLF001

        abstractModel: QAbstractItemModel | QFileSystemModel | None = self.proxyModel if self.proxyModel else self.model
        assert abstractModel is not None, "abstractModel is None"
        for _ in range(1, abstractModel.columnCount(QModelIndex())):
            showHeader = QAction(showActionGroup)
            showHeader.setCheckable(True)
            showHeader.setChecked(True)
            treeHeader.addAction(showHeader)

        # Setup selection model
        selections: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
        assert selections is not None, "selections is None"
        selections.selectionChanged.connect(self._q_selectionChanged)  # noqa: SLF001
        selections.currentChanged.connect(self._q_currentChanged)  # noqa: SLF001
        self._ensure_selection_model_compatibility(selections)

        self.qFileDialogUi.splitter.setStretchFactor(self.qFileDialogUi.splitter.indexOf(self.qFileDialogUi.splitter.widget(1)), 1)

        self.createToolButtons()
        self.createMenuActions()

        # Restore settings
        if not self.restoreFromSettings():
            settings = QSettings(QSettings.Scope.UserScope, "QtProject")
            q.restoreState(settings.value("Qt/filedialog"))

        # Set initial widget states from options
        q.setFileMode(self.options.fileMode())
        q.setAcceptMode(self.options.acceptMode())
        q.setViewMode(self.options.viewMode())
        q.setOptions(int(self.options.options() if qtpy.API_NAME == "PyQt5" else self.options.options().value))  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        if self.options.sidebarUrls():
            q.setSidebarUrls(self.options.sidebarUrls())
        q.setDirectoryUrl(self.options.initialDirectory())
        if self.options.mimeTypeFilters():
            q.setMimeTypeFilters(self.options.mimeTypeFilters())
        elif self.options.nameFilters():
            q.setNameFilters(self.options.nameFilters())
        q.selectNameFilter(self.options.initiallySelectedNameFilter())
        q.setDefaultSuffix(self.options.defaultSuffix())
        q.setHistory(self.options.history())
        initiallySelectedFiles = self.options.initiallySelectedFiles()
        if len(initiallySelectedFiles) == 1:
            q.selectFile(initiallySelectedFiles[0].fileName())
        for url in initiallySelectedFiles:
            q.selectUrl(url)
        self.lineEdit().selectAll()
        self._q_updateOkButton()  # noqa: SLF001
        self._updateNavigationButtons()
        self.retranslateStrings()
        q.resize(self.preSize if self.preSize.isValid() else q.sizeHint())
        q.setWindowState(self.preState)

    def _ensure_selection_model_compatibility(
        self,
        selection_model: QItemSelectionModel | None,
    ) -> None:
        """
        Qt's C++ API exposes QItemSelectionModel::index(). PyQt's binding omits this helper,
        so we emulate it to keep the Python behaviour aligned with Qt.
        """

        if selection_model is None or hasattr(selection_model, "index"):
            return

        def _index(
            row: int,
            column: int,
            parent: QModelIndex | None = None,
        ) -> QModelIndex:
            model = selection_model.model()
            if model is None:
                return QModelIndex()
            parent_index = parent if parent is not None else QModelIndex()
            return model.index(row, column, parent_index)

        setattr(selection_model, "index", _index)

    def retranslateStrings(self) -> None:
        """Retranslate the UI, including all child widgets."""
        d: QFileDialogPrivate = self
        q: QFileDialog = self._public
        app = QApplication.instance()
        assert app is not None

        if d.options.useDefaultNameFilters():
            q.setNameFilter(self.options.defaultNameFilterString())
        if not d.usingWidgets():
            return

        assert d.qFileDialogUi is not None, f"{type(self)}.retranslateStrings: No UI setup."
        # Match C++: QList<QAction*> actions = qFileDialogUi->treeView->header()->actions();
        tree_header_view: QHeaderView | None = d.qFileDialogUi.treeView.header()
        assert tree_header_view is not None, "tree_header_view is None"
        actions = tree_header_view.actions()
        # Match C++: QAbstractItemModel *abstractModel = model;
        abstractModel: QAbstractItemModel | QFileSystemModel | None = d.model
        assert abstractModel is not None
        # Match C++: #if QT_CONFIG(proxymodel) if (proxyModel) abstractModel = proxyModel; #endif
        if d.proxyModel:
            abstractModel = d.proxyModel
        # Match C++: const int total = qMin(abstractModel->columnCount(QModelIndex()), int(actions.size() + 1));
        total = min(abstractModel.columnCount(QModelIndex()), len(actions) + 1)
        # Match C++: for (int i = 1; i < total; ++i)
        for i in range(1, total):
            # Match C++: actions.at(i - 1)->setText(QFileDialog::tr("Show ") + abstractModel->headerData(i, Qt::Horizontal, Qt::DisplayRole).toString());
            header_data = abstractModel.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            header_str = str(header_data) if header_data is not None else ""
            actions[i - 1].setText(q.tr("Show ") + header_str)

        # Match C++: /* MENU ACTIONS */
        # Match C++: renameAction->setText(QFileDialog::tr("&Rename"));
        d.renameAction.setText(q.tr("&Rename"))
        # Match C++: deleteAction->setText(QFileDialog::tr("&Delete"));
        d.deleteAction.setText(q.tr("&Delete"))
        # Match C++: showHiddenAction->setText(QFileDialog::tr("Show &hidden files"));
        d.showHiddenAction.setText(q.tr("Show &hidden files"))
        # Match C++: newFolderAction->setText(QFileDialog::tr("&New Folder"));
        d.newFolderAction.setText(q.tr("&New Folder"))
        d.qFileDialogUi.retranslateUi(q)
        d.updateLookInLabel()
        d.updateFileNameLabel()
        d.updateFileTypeLabel()
        d.updateCancelButtonText()

    def createToolButtons(self) -> None:
        assert self.qFileDialogUi is not None, "QFileDialogUi is None"
        q = self._public
        q_style: QStyle | None = q.style()
        assert q_style is not None, "q_style is None"
        self.qFileDialogUi.backButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_ArrowBack, None, q))
        self.qFileDialogUi.backButton.setAutoRaise(True)
        self.qFileDialogUi.backButton.setEnabled(False)
        self.qFileDialogUi.backButton.clicked.connect(self._q_navigateBackward)

        self.qFileDialogUi.forwardButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward, None, q))
        self.qFileDialogUi.forwardButton.setAutoRaise(True)
        self.qFileDialogUi.forwardButton.setEnabled(False)
        self.qFileDialogUi.forwardButton.clicked.connect(self._q_navigateForward)

        self.qFileDialogUi.toParentButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent, None, q))
        self.qFileDialogUi.toParentButton.setAutoRaise(True)
        self.qFileDialogUi.toParentButton.setEnabled(False)
        self.qFileDialogUi.toParentButton.clicked.connect(self._q_navigateToParent)

        self.qFileDialogUi.listModeButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView, None, q))
        self.qFileDialogUi.listModeButton.setAutoRaise(True)
        self.qFileDialogUi.listModeButton.setDown(True)
        self.qFileDialogUi.listModeButton.clicked.connect(self._q_showListView)

        self.qFileDialogUi.detailModeButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView, None, q))
        self.qFileDialogUi.detailModeButton.setAutoRaise(True)
        self.qFileDialogUi.detailModeButton.clicked.connect(self._q_showDetailsView)

        toolSize = QSize(self.qFileDialogUi.fileNameEdit.sizeHint().height(), self.qFileDialogUi.fileNameEdit.sizeHint().height())
        self.qFileDialogUi.backButton.setFixedSize(toolSize)
        self.qFileDialogUi.listModeButton.setFixedSize(toolSize)
        self.qFileDialogUi.detailModeButton.setFixedSize(toolSize)
        self.qFileDialogUi.forwardButton.setFixedSize(toolSize)
        self.qFileDialogUi.toParentButton.setFixedSize(toolSize)

        self.qFileDialogUi.newFolderButton.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder, None, q))
        self.qFileDialogUi.newFolderButton.setFixedSize(toolSize)
        self.qFileDialogUi.newFolderButton.setAutoRaise(True)
        self.qFileDialogUi.newFolderButton.setEnabled(False)
        self.qFileDialogUi.newFolderButton.clicked.connect(self._q_createDirectory)

    def createMenuActions(self) -> None:
        q = self._public

        goHomeAction = QAction(q)
        goHomeAction.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_H))  # pyright: ignore[reportCallIssue, reportOperatorIssue]
        goHomeAction.triggered.connect(self._q_goHome)
        q.addAction(goHomeAction)

        goToParent = QAction(q)
        goToParent.setObjectName("qt_goto_parent_action")
        goToParent.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Up))  # pyright: ignore[reportCallIssue, reportOperatorIssue]
        goToParent.triggered.connect(self._q_navigateToParent)
        q.addAction(goToParent)

        self.renameAction = QAction(q)
        self.renameAction.setEnabled(False)
        self.renameAction.setObjectName("qt_rename_action")
        self.renameAction.triggered.connect(self._q_renameCurrent)

        self.deleteAction = QAction(q)
        self.deleteAction.setEnabled(False)
        self.deleteAction.setObjectName("qt_delete_action")
        self.deleteAction.triggered.connect(self._q_deleteCurrent)

        self.showHiddenAction = QAction(q)
        self.showHiddenAction.setObjectName("qt_show_hidden_action")
        self.showHiddenAction.setCheckable(True)
        self.showHiddenAction.triggered.connect(self._q_showHidden)

        self.newFolderAction = QAction(q)
        self.newFolderAction.setObjectName("qt_new_folder_action")
        self.newFolderAction.triggered.connect(self._q_createDirectory)

    def initHelper(self, h: QPlatformFileDialogHelper) -> None:
        """Initialize the platform file dialog helper.

        Connects signals from the helper to the appropriate slots in the file dialog.
        Ensures that the file dialog responds correctly to user interactions in the native dialog.

        If this function is removed, the file dialog would not respond to user actions in the native dialog,
        breaking the expected behavior of the file dialog.
        """
        q = self._public
        h.fileSelected.connect(self._q_emitUrlSelected)  # noqa: SLF001
        h.filesSelected.connect(self._q_emitUrlsSelected)  # noqa: SLF001
        h.currentChanged.connect(self._q_nativeCurrentChanged)  # noqa: SLF001
        h.directoryEntered.connect(self._q_nativeEnterDirectory)  # noqa: SLF001
        h.filterSelected.connect(q.filterSelected)
        # this will need to be fixed later
        # h.setOptions(self.options)  # TODO(th3w1zard1): implement the platform helpers.

    def q_func(self) -> QFileDialog:
        return self._public

    def helperPrepareShow(self, h: QPlatformFileDialogHelper) -> None:
        """Prepare the platform file dialog helper before showing the dialog.

        Sets up the initial state of the native dialog to match the current state of the QFileDialog.
        Ensures consistency between the Qt dialog and the native dialog.

        If this function is removed, the native dialog would not reflect the current state of the QFileDialog,
        leading to inconsistencies in the user interface.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.helperPrepareShow: UI is None"
        q = self._public
        self.setWindowTitle = q.windowTitle()
        self.options.setHistory(q.history())
        if self.usingWidgets():
            sidebar: QSidebar = self.qFileDialogUi.sidebar
            assert sidebar is not None
            self.options.setSidebarUrls(sidebar.urls())
        if not self.options.initiallySelectedNameFilter():
            self.options.setInitiallySelectedNameFilter(q.selectedNameFilter())
        if not self.options.initiallySelectedFiles():
            self.options.setInitiallySelectedFiles(self.userSelectedFiles())

    def helperDone(
        self,
        code: QDialog.DialogCode,
        h: QPlatformFileDialogHelper,
    ) -> None:
        """Handle the completion of the native file dialog.

        Updates the QFileDialog state based on the result of the native dialog.
        Ensures that the QFileDialog reflects the user's actions in the native dialog.

        If this function is removed, changes made in the native dialog would not be
        reflected in the QFileDialog, leading to inconsistencies in the dialog's state.
        """
        if code == QDialog.DialogCode.Accepted:
            q = self._public
            q.setViewMode(RealQFileDialog.ViewMode(self.options.viewMode()))
            q.setSidebarUrls(self.options.sidebarUrls())
            q.setHistory(self.options.history())

    def _q_useNameFilter(
        self,
        index: int,
    ) -> None:
        """Sets the current name filter to be nameFilter and update the fileNameEdit when in AcceptSave mode with the new extension.

        Matches C++ QFileDialogPrivate::useNameFilter() implementation.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_useNameFilter: UI is None"
        # Match C++: QStringList nameFilters = options->nameFilters();
        nameFilters: list[str] = self.options.nameFilters()
        # Match C++: if (index == nameFilters.size())
        if index == len(nameFilters):
            # Match C++: QAbstractItemModel *comboModel = qFileDialogUi->fileTypeCombo->model();
            comboModel = self.qFileDialogUi.fileTypeCombo.model()
            # Match C++: nameFilters.append(comboModel->index(comboModel->rowCount() - 1, 0).data().toString());
            assert comboModel is not None, f"{self.__class__.__name__}._q_useNameFilter: comboModel is None"
            combo_data = comboModel.index(comboModel.rowCount() - 1, 0).data()
            nameFilters.append(str(combo_data) if combo_data is not None else "")
            # Match C++: options->setNameFilters(nameFilters);
            self.options.setNameFilters(nameFilters)

        # Match C++: QString nameFilter = nameFilters.at(index);
        nameFilter = nameFilters[index]
        # Match C++: QStringList newNameFilters = QPlatformFileDialogHelper::cleanFilterList(nameFilter);
        newNameFilters = QPlatformFileDialogHelper.cleanFilterList(nameFilter)
        # Match C++: if (q_func()->acceptMode() == QFileDialog::AcceptSave)
        if sip_enum_to_int(self.q_func().acceptMode()) == sip_enum_to_int(RealQFileDialog.AcceptSave):
            # Match C++: QString newNameFilterExtension;
            newNameFilterExtension = ""
            # Match C++: if (newNameFilters.size() > 0)
            if len(newNameFilters) > 0:
                # Match C++: newNameFilterExtension = QFileInfo(newNameFilters.at(0)).suffix();
                newNameFilterExtension = QFileInfo(newNameFilters[0]).suffix()

            # Match C++: QString fileName = lineEdit()->text();
            fileName: str = self.lineEdit().text()
            # Match C++: const QString fileNameExtension = QFileInfo(fileName).suffix();
            fileNameExtension: str = QFileInfo(fileName).suffix()
            # Match C++: if (!fileNameExtension.isEmpty() && !newNameFilterExtension.isEmpty())
            if fileNameExtension and newNameFilterExtension:
                # Match C++: const qsizetype fileNameExtensionLength = fileNameExtension.size();
                fileNameExtensionLength = len(fileNameExtension)
                # Match C++: fileName.replace(fileName.size() - fileNameExtensionLength, fileNameExtensionLength, newNameFilterExtension);
                # Replace the extension: from position (len - extLen) for extLen chars with newExt
                fileName = fileName[: len(fileName) - fileNameExtensionLength] + newNameFilterExtension
                # Match C++: qFileDialogUi->listView->clearSelection();
                self.qFileDialogUi.listView.clearSelection()
                # Match C++: lineEdit()->setText(fileName);
                self.lineEdit().setText(fileName)

        # Match C++: model->setNameFilters(newNameFilters);
        assert self.model is not None, f"{self.__class__.__name__}._q_useNameFilter: model is None"
        self.model.setNameFilters(newNameFilters)

    def _q_goToDirectory(
        self,
        path: str,
    ) -> None:
        """Go to directory. Matches C++ QFileDialogPrivate::goToDirectory() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_goToDirectory: No UI setup."
        assert self.model is not None, f"{self.__class__.__name__}._q_goToDirectory: No model setup."
        # Match C++: enum { UrlRole = Qt::UserRole + 1 };
        url_role: int = Qt.ItemDataRole.UserRole + 1  # pyright: ignore[reportArgumentType]
        # Match C++: QModelIndex index = qFileDialogUi->lookInCombo->model()->index(...);
        index: QModelIndex = self.qFileDialogUi.lookInCombo.model().index(
            self.qFileDialogUi.lookInCombo.currentIndex(),
            self.qFileDialogUi.lookInCombo.modelColumn(),
            self.qFileDialogUi.lookInCombo.rootModelIndex(),
        )
        # Match C++: QString path2 = path;
        path2: str = path
        # Match C++: if (!index.isValid())
        if not index.isValid():
            # Match C++: index = mapFromSource(model->index(getEnvironmentVariable(path)));
            index = self.mapFromSource(self.model.index(self.getEnvironmentVariable(path)))
        else:
            # Match C++: path2 = index.data(UrlRole).toUrl().toLocalFile();
            url_data = index.data(url_role)
            url = url_data if isinstance(url_data, QUrl) else QUrl()
            path2 = url.toLocalFile()
            # Match C++: index = mapFromSource(model->index(path2));
            index = self.mapFromSource(self.model.index(path2))
        # Match C++: QDir dir(path2);
        _dir = QDir(path2)
        # Match C++: if (!dir.exists()) dir.setPath(getEnvironmentVariable(path2));
        if not _dir.exists():
            _dir.setPath(self.getEnvironmentVariable(path2))

        # Match C++: if (dir.exists() || path2.isEmpty() || path2 == model->myComputer().toString())
        if _dir.exists() or not path2 or path2 == self.model.myComputer().toString():
            # Match C++: enterDirectory(index);
            self._q_enterDirectory(index)
        # Match C++: #if QT_CONFIG(messagebox) } else { ... #endif
        else:
            # Match C++: QString message = QFileDialog::tr("%1\nDirectory not found.\nPlease verify the correct directory name was given.");
            message_template = q.tr("%1\nDirectory not found.\nPlease verify the correct directory name was given.")
            # Match C++: QMessageBox::warning(q, q->windowTitle(), message.arg(path2));
            message = message_template.replace("%1", path2)
            QMessageBox.warning(q, q.windowTitle(), message)

    def userSelectedFiles(self) -> list[QUrl]:
        """Return selected files without defaulting to the root of the file system model.

        Used for initializing QFileDialogOptions for native dialogs. The default is
        not suitable for native dialogs since it mostly equals directory().

        Matches C++ QFileDialogPrivate::userSelectedFiles() implementation.
        """
        # Match C++: QList<QUrl> files;
        files: list[QUrl] = []
        # Match C++: if (!usingWidgets()) return addDefaultSuffixToUrls(selectedFiles_sys());
        if not self.usingWidgets():
            return self.addDefaultSuffixToUrls(self.selectedFiles_sys())
        # Match C++: const QModelIndexList selectedRows = qFileDialogUi->listView->selectionModel()->selectedRows();
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.userSelectedFiles: No UI setup."
        selected_rows = self.qFileDialogUi.listView.selectionModel().selectedRows()
        # Match C++: files.reserve(selectedRows.size());
        # Match C++: for (const QModelIndex &index : selectedRows)
        # Match C++:     files.append(QUrl::fromLocalFile(index.data(QFileSystemModel::FilePathRole).toString()));
        for index in selected_rows:
            file_path_data = index.data(QFileSystemModel.Roles.FilePathRole)
            file_path_str = str(file_path_data) if file_path_data is not None else ""
            files.append(QUrl.fromLocalFile(file_path_str))
        # Match C++: if (files.isEmpty() && !lineEdit()->text().isEmpty())
        if not files and self.lineEdit().text():
            # Match C++: const QStringList typedFilesList = typedFiles();
            typed_files_list = self.typedFiles()
            # Match C++: files.reserve(typedFilesList.size());
            # Match C++: for (const QString &path : typedFilesList)
            # Match C++:     files.append(QUrl::fromLocalFile(path));
            for path in typed_files_list:
                files.append(QUrl.fromLocalFile(path))
        return files

    def addDefaultSuffixToFiles(
        self,
        filesToFix: list[str],  # noqa: N803
    ) -> list[str]:
        """Add the default suffix to files if necessary. Matches C++ QFileDialogPrivate::addDefaultSuffixToFiles() implementation."""
        files: list[str] = []
        # Match C++: for (int i=0; i<filesToFix.size(); ++i)
        for name in filesToFix:
            # Match C++: QString name = toInternal(filesToFix.at(i));
            newName: str = self.toInternal(name)
            # Match C++: QFileInfo info(name);
            info = QFileInfo(newName)
            # Match C++: const QString defaultSuffix = options->defaultSuffix();
            defaultSuffix: str = self.options.defaultSuffix()
            # Match C++: if (!defaultSuffix.isEmpty() && !info.isDir() && !info.fileName().contains(u'.'))
            if defaultSuffix and not info.isDir() and "." not in info.fileName():
                # Match C++: name += u'.' + defaultSuffix;
                newName = newName + "." + defaultSuffix
            # Match C++: if (info.isAbsolute()) { files.append(name); } else { ... }
            if info.isAbsolute():
                files.append(newName)
            else:
                # Match C++: QString path = rootPath(); if (!path.endsWith(u'/')) path += u'/'; path += name; files.append(path);
                path: str = self.rootPath()
                if not path.endswith("/"):
                    path += "/"
                path += newName
                files.append(path)
        return files

    def addDefaultSuffixToUrls(
        self,
        urlsToFix: list[QUrl],  # noqa: N803
    ) -> list[QUrl]:
        """Add the default suffix to URLs if necessary.

        Ensures that file URLs without extensions get the default suffix added.
        This is important for maintaining consistent file naming conventions when working with URLs.
        """
        urls: list[QUrl] = []
        # Match C++: urls.reserve(urlsToFix.size());
        # Match C++: const QString defaultSuffix = options->defaultSuffix();
        defaultSuffix: str = self.options.defaultSuffix()
        # Match C++: for (QUrl url : urlsToFix)
        for url in urlsToFix:
            # Match C++: if (!defaultSuffix.isEmpty())
            if defaultSuffix:
                # Match C++: const QString urlPath = url.path();
                urlPath: str = url.path()
                # Match C++: const auto idx = urlPath.lastIndexOf(u'/');
                idx = urlPath.rfind("/")
                # Match C++: if (idx != (urlPath.size() - 1) && !QStringView{urlPath}.mid(idx + 1).contains(u'.'))
                # Check if the filename (after last '/') contains a '.'
                if idx != (len(urlPath) - 1):
                    filename = urlPath[idx + 1 :]
                    if "." not in filename:
                        # Match C++: url.setPath(urlPath + u'.' + defaultSuffix);
                        url.setPath(urlPath + "." + defaultSuffix)
            # Match C++: urls.append(url);
            urls.append(url)
        return urls

    def retranslateWindowTitle(self) -> None:
        """Retranslate window title. Matches C++ QFileDialogPrivate::retranslateWindowTitle() implementation."""
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: if (!useDefaultCaption || setWindowTitle != q->windowTitle()) return;
        if not self.useDefaultCaption or self.setWindowTitle != q.windowTitle():
            return
        # Match C++: if (q->acceptMode() == QFileDialog::AcceptOpen)
        if q.acceptMode() == RealQFileDialog.AcceptMode.AcceptOpen:
            # Match C++: const QFileDialog::FileMode fileMode = q->fileMode();
            fileMode = q.fileMode()
            # Match C++: if (fileMode == QFileDialog::Directory)
            if fileMode == RealQFileDialog.FileMode.Directory:
                # Match C++: q->setWindowTitle(QFileDialog::tr("Find Directory"));
                q.setWindowTitle(q.tr("Find Directory"))
            else:
                # Match C++: q->setWindowTitle(QFileDialog::tr("Open"));
                q.setWindowTitle(q.tr("Open"))
        else:
            # Match C++: q->setWindowTitle(QFileDialog::tr("Save As"));
            q.setWindowTitle(q.tr("Save As"))
        # Match C++: setWindowTitle = q->windowTitle();
        self.setWindowTitle = q.windowTitle()

    def usingWidgets(self) -> bool:
        """Checks the Qt widget-based dialog is being used instead of the native dialog.

        This affects how various UI operations are handled.
        """
        return not self.nativeDialogInUse and self.qFileDialogUi is not None

    def rootIndex(self) -> QModelIndex:
        """Provides the root index of the current file system view.

        Crucial for correctly navigating and displaying the file system hierarchy.
        """
        view: QAbstractItemView | None = self.currentView()
        assert view is not None, f"{self.__class__.__name__}.rootIndex: No view found."
        return self.mapToSource(view.rootIndex())

    def setRootIndex(
        self,
        index: QModelIndex,
    ) -> None:
        """Updates the root index for both the tree and list views.

        Ensures that both views are synchronized and showing the same directory.

        This implementation guards against transient model mismatches. If the mapped
        index does not belong to a view's current model, we avoid calling
        setRootIndex with a mismatched index (which emits Qt warnings) and instead
        clear the root to keep the view consistent.
        """
        idx: QModelIndex = self.mapFromSource(index)
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.setRootIndex: UI is None"

        tree = self.qFileDialogUi.treeView
        listv = self.qFileDialogUi.listView

        # Only set root index if the mapped index belongs to the view's model
        try:
            if idx.isValid() and tree.model() == idx.model():
                tree.setRootIndex(idx)
            else:
                tree.setRootIndex(QModelIndex())
        except Exception:
            # Be defensive — do not raise from UI helper
            tree.setRootIndex(QModelIndex())

        try:
            if idx.isValid() and listv.model() == idx.model():
                listv.setRootIndex(idx)
            else:
                listv.setRootIndex(QModelIndex())
        except Exception:
            listv.setRootIndex(QModelIndex())

    def currentView(self) -> QAbstractItemView | None:
        """Returns the currently active view. Matches C++ QFileDialogPrivate::currentView() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.currentView: No UI setup."
        # Match C++: if (!qFileDialogUi->stackedWidget) return nullptr;
        if not self.qFileDialogUi.stackedWidget:
            return None
        # Match C++: if (qFileDialogUi->stackedWidget->currentWidget() == qFileDialogUi->listView->parent())
        # Match C++:     return qFileDialogUi->listView;
        if self.qFileDialogUi.stackedWidget.currentWidget() == self.qFileDialogUi.listView.parent():
            return self.qFileDialogUi.listView
        # Match C++: return qFileDialogUi->treeView;
        return self.qFileDialogUi.treeView

    def saveHistorySelection(self) -> None:
        """Preserves the current selection state in the history.

        Allows for restoring the selection when navigating back in history.

        If this function is removed, the dialog would lose the ability to remember selections
        when navigating through history, degrading the user experience.
        """
        if self.currentHistoryLocation < 0 or self.currentHistoryLocation >= len(self.currentHistory):
            RobustLogger().warning(f"{self.__class__.__name__}.saveHistorySelection: Invalid history location: {self.currentHistoryLocation}")
            return

        if self.qFileDialogUi is None or self.model is None:
            RobustLogger().warning(f"{self.__class__.__name__}.saveHistorySelection: UI or model is None")
            return

        item: HistoryItem = self.currentHistory[self.currentHistoryLocation]
        item.selection = []
        listview_sel_model: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
        assert listview_sel_model is not None, f"{self.__class__.__name__}.saveHistorySelection: listview_sel_model is None"
        selectedIndexes: list[QModelIndex] = listview_sel_model.selectedRows()
        for i, index in enumerate(selectedIndexes):
            if not index.isValid():
                RobustLogger().warning(f"{self.__class__.__name__}.saveHistorySelection: Invalid index: {index} at index {i} in the selection model's rows list.")
                continue
            item.selection.append(QPersistentModelIndex(index))

    def _q_pathChanged(
        self,
        path: str,
    ) -> None:
        """Handle path change. Matches C++ QFileDialogPrivate::pathChanged() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_pathChanged: No UI setup."
        assert self.model is not None, f"{self.__class__.__name__}._q_pathChanged: No model setup."
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: qFileDialogUi->toParentButton->setEnabled(QFileInfo::exists(model->rootPath()));
        self.qFileDialogUi.toParentButton.setEnabled(QFileInfo(self.model.rootPath()).exists())
        # Match C++: qFileDialogUi->sidebar->selectUrl(QUrl::fromLocalFile(newPath));
        self.qFileDialogUi.sidebar.selectUrl(QUrl.fromLocalFile(path))
        # Match C++: q->setHistory(qFileDialogUi->lookInCombo->history());
        q.setHistory(self.qFileDialogUi.lookInCombo.history())

        # Match C++: const QString newNativePath = QDir::toNativeSeparators(newPath);
        newNativePath: str = QDir.toNativeSeparators(path)

        # Match C++: // equal paths indicate this was invoked by _q_navigateBack/Forward()
        # Match C++: if (currentHistoryLocation < 0 || currentHistory.value(currentHistoryLocation).path != newNativePath) {
        if self.currentHistoryLocation < 0 or (
            self.currentHistoryLocation < len(self.currentHistory) and self.currentHistory[self.currentHistoryLocation].path != newNativePath
        ):
            # Match C++: if (currentHistoryLocation >= 0) saveHistorySelection();
            if self.currentHistoryLocation >= 0:
                self.saveHistorySelection()
            # Match C++: while (currentHistoryLocation >= 0 && currentHistoryLocation + 1 < currentHistory.size()) {
            # Match C++:     currentHistory.removeLast();
            # Match C++: }
            while self.currentHistoryLocation >= 0 and self.currentHistoryLocation + 1 < len(self.currentHistory):
                self.currentHistory.pop()
            # Match C++: currentHistory.append({newNativePath, PersistentModelIndexList()});
            self.currentHistory.append(HistoryItem(newNativePath, []))
            # Match C++: ++currentHistoryLocation;
            self.currentHistoryLocation += 1
        # Match C++: qFileDialogUi->forwardButton->setEnabled(currentHistory.size() - currentHistoryLocation > 1);
        self.qFileDialogUi.forwardButton.setEnabled(len(self.currentHistory) - self.currentHistoryLocation > 1)
        # Match C++: qFileDialogUi->backButton->setEnabled(currentHistoryLocation > 0);
        self.qFileDialogUi.backButton.setEnabled(self.currentHistoryLocation > 0)

    @staticmethod
    def maxNameLength(
        path: str,
    ) -> int:
        """Return maximum file name length for the given path. Matches C++ QFileDialogPrivate::maxNameLength() implementation."""
        # Match C++: #if defined(Q_OS_UNIX)
        if os.name == "posix":
            # Match C++: return ::pathconf(QFile::encodeName(path).data(), _PC_NAME_MAX);
            try:
                import ctypes
                import ctypes.util

                libc = ctypes.CDLL(ctypes.util.find_library("c"))
                # pathconf(path, _PC_NAME_MAX)
                _PC_NAME_MAX = 3  # Standard value for _PC_NAME_MAX
                # Note: This is a simplified implementation. Full implementation would use QFile::encodeName
                # For now, we use a reasonable default or try to get it from the system
                try:
                    result = libc.pathconf(path.encode(), _PC_NAME_MAX)
                    if result > 0:
                        return int(result)
                except (OSError, AttributeError):
                    pass
                # Fallback to common Unix default
                return 255
            except (ImportError, OSError):
                # Fallback if ctypes not available
                return 255
        # Match C++: #elif defined(Q_OS_WIN)
        elif os.name == "nt":
            # Match C++: DWORD maxLength;
            # Match C++: const QString drive = path.left(3);
            drive = path[:3] if len(path) >= 3 else path
            # Match C++: if (::GetVolumeInformation(...) == false) return -1;
            try:
                import ctypes

                from ctypes import wintypes

                kernel32 = ctypes.windll.kernel32
                max_length = wintypes.DWORD()
                # GetVolumeInformationW
                if kernel32.GetVolumeInformationW(ctypes.c_wchar_p(drive), None, 0, None, ctypes.byref(max_length), None, 0):
                    return int(max_length.value)
            except (ImportError, OSError, AttributeError):
                pass
        # Match C++: #else ... #endif
        # Match C++: return -1;
        return -1

    def emitFilesSelected(
        self,
        files: list[str],
    ) -> None:
        """Emit filesSelected signal. Matches C++ QFileDialogPrivate::emitFilesSelected() implementation."""
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: emit q->filesSelected(files);
        q.filesSelected.emit(files)
        # Match C++: if (files.size() == 1)
        if len(files) == 1:
            # Match C++: emit q->fileSelected(files.first());
            q.fileSelected.emit(files[0])

    def itemNotFound(
        self,
        fileName: str,  # noqa: N803
        mode: QFileDialog.FileMode,
    ) -> None:
        """Display error message when item not found. Matches C++ QFileDialogPrivate::itemNotFound() implementation."""
        # Match C++: #if QT_CONFIG(messagebox)
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: const QString message = mode == QFileDialog::Directory
        # Match C++:         ? QFileDialog::tr("%1\nDirectory not found.\nPlease verify the correct directory name was given.")
        # Match C++:         : QFileDialog::tr("%1\nFile not found.\nPlease verify the correct file name was given.");
        if mode == RealQFileDialog.FileMode.Directory:
            # Match C++: QFileDialog::tr("%1\nDirectory not found.\nPlease verify the correct directory name was given.")
            message_template = q.tr("%1\nDirectory not found.\nPlease verify the correct directory name was given.")
        else:
            # Match C++: QFileDialog::tr("%1\nFile not found.\nPlease verify the correct file name was given.");
            message_template = q.tr("%1\nFile not found.\nPlease verify the correct file name was given.")
        # Match C++: QMessageBox::warning(q, q->windowTitle(), message.arg(fileName));
        message = message_template.replace("%1", fileName)
        QMessageBox.warning(q, q.windowTitle(), message)

    def itemAlreadyExists(
        self,
        fileName: str,  # noqa: N803
    ) -> bool:
        """Prompt user for confirmation when file already exists. Matches C++ QFileDialogPrivate::itemAlreadyExists() implementation."""
        # Match C++: #if QT_CONFIG(messagebox)
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: const QString msg = QFileDialog::tr("%1 already exists.\nDo you want to replace it?").arg(fileName);
        msg_template = q.tr("%1 already exists.\nDo you want to replace it?")
        msg = msg_template.replace("%1", fileName)
        # Match C++: using B = QMessageBox;
        # Match C++: const auto res = B::warning(q, q->windowTitle(), msg, B::Yes | B::No, B::No);
        res: QMessageBox.StandardButton = QMessageBox.warning(
            q, q.windowTitle(), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        # Match C++: return res == B::Yes;
        return res == QMessageBox.StandardButton.Yes
        # Match C++: #endif
        # Match C++: return false;  // if messagebox not available

    def _removeForwardHistory(self) -> None:
        """Clears the forward history when a new path is visited.

        Ensures that the history behaves like a typical browser history.

        If this function is removed, the history navigation would become inconsistent,
        with the forward history remaining even after visiting new locations.
        """
        while self.currentHistoryLocation >= 0 and self.currentHistoryLocation + 1 < len(self.currentHistory):
            self.currentHistory.pop()

    def _updateNavigationButtons(self) -> None:
        """Enables or disables the forward and back buttons based on the current history state.

        This provides visual feedback about the availability of history navigation.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._updateNavigationButtons: No UI setup."
        # Forward button enabled if there's at least one item forward (currentHistoryLocation < len - 1)
        # Back button enabled if there's at least one item back (currentHistoryLocation > 0)
        self.qFileDialogUi.forwardButton.setEnabled(self.currentHistoryLocation < len(self.currentHistory) - 1)
        self.qFileDialogUi.backButton.setEnabled(self.currentHistoryLocation > 0)

    def _q_navigateBackward(self) -> None:
        """Implements the functionality for the back button.

        Matches C++ QFileDialogPrivate::navigateBackward() implementation.
        """
        # Match C++: if (!currentHistory.isEmpty() && currentHistoryLocation > 0)
        if self.currentHistory and self.currentHistoryLocation > 0:
            # Match C++: saveHistorySelection();
            self.saveHistorySelection()
            # Match C++: navigate(currentHistory[--currentHistoryLocation]);
            self.currentHistoryLocation -= 1
            self._navigateToHistoryItem(self.currentHistory[self.currentHistoryLocation])

    def _q_navigateForward(self) -> None:
        """Implements the functionality for the forward button.

        Matches C++ QFileDialogPrivate::navigateForward() implementation.
        """
        # Match C++: if (!currentHistory.isEmpty() && currentHistoryLocation < currentHistory.size() - 1)
        if self.currentHistory and self.currentHistoryLocation < len(self.currentHistory) - 1:
            # Match C++: saveHistorySelection();
            self.saveHistorySelection()
            # Match C++: navigate(currentHistory[++currentHistoryLocation]);
            self.currentHistoryLocation += 1
            self._navigateToHistoryItem(self.currentHistory[self.currentHistoryLocation])

    def _navigateToHistoryItem(
        self,
        item: HistoryItem,
    ) -> None:
        """Restores the state of a previously visited directory, including selection.

        Matches C++ navigate(HistoryItem &historyItem) implementation.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._navigateToHistoryItem: No UI setup."
        q = self._public
        self._ignoreHistoryChange = True
        try:
            q.setDirectory(item.path)
        finally:
            self._ignoreHistoryChange = False

        # Restore selection unless something has changed in the file system
        if not item.selection:
            return

        # Check if any persistent indexes are invalid (matching C++ std::any_of check)
        if any(not idx.isValid() for idx in item.selection):
            item.selection.clear()
            return

        # Use the current view mode to determine which view to use
        view: QAbstractItemView = self.qFileDialogUi.listView if q.viewMode() == RealQFileDialog.ViewMode.List else self.qFileDialogUi.treeView
        selection_model: QItemSelectionModel | None = view.selectionModel()
        if selection_model is None:
            return

        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows

        # Select first item with Clear and Current flags (matching C++ implementation)
        if item.selection:
            first_index = item.selection[0]
            # QPersistentModelIndex can be used directly with select() in Qt
            selection_model.select(first_index, flags | QItemSelectionModel.SelectionFlag.Clear | QItemSelectionModel.SelectionFlag.Current)
            view.scrollTo(first_index)

        # Select remaining items
        for persistent_index in item.selection[1:]:
            selection_model.select(persistent_index, flags)

    def _q_navigateToParent(self) -> None:
        """Implements the functionality for the "Up" or "Parent Directory" button.

        This allows users to navigate up the directory hierarchy.
        """
        assert self.model is not None, f"{self.__class__.__name__}._q_navigateToParent: No file system model setup."

        q = self._public
        root_dir = QDir(self.model.rootDirectory())
        if root_dir.isRoot():
            newDirectory = str(self.model.myComputer().toString())
        else:
            root_dir.cdUp()
            newDirectory = root_dir.absolutePath()

        q.setDirectory(newDirectory)
        q.directoryEntered.emit(newDirectory)

    def _q_createDirectory(self) -> None:
        """Creates a new directory, first asking the user for a suitable name.

        Matches C++ QFileDialogPrivate::createDirectory() implementation.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_createDirectory: No UI setup."
        assert self.model is not None, f"{self.__class__.__name__}._q_createDirectory: No file system model setup."

        q = self._public
        # Match C++: qFileDialogUi->listView->clearSelection();
        self.qFileDialogUi.listView.clearSelection()

        # Match C++: QString newFolderString = QFileDialog::tr("New Folder");
        newFolderString: str = q.tr("New Folder")
        # Match C++: QString folderName = newFolderString;
        folderName: str = newFolderString
        # Match C++: QString prefix = q->directory().absolutePath() + QDir::separator();
        prefix: str = q.directory().absolutePath() + QDir.separator()
        # Match C++: if (QFile::exists(prefix + folderName))
        if QFile.exists(prefix + folderName):
            # Match C++: qlonglong suffix = 2;
            suffix = 2
            # Match C++: while (QFile::exists(prefix + folderName))
            while QFile.exists(prefix + folderName):
                # Match C++: folderName = newFolderString + QString::number(suffix++);
                # Note: suffix++ in C++ increments after use, so we convert then increment
                folderName = newFolderString + str(suffix)
                suffix += 1

        # Match C++: QModelIndex parent = rootIndex();
        parent: QModelIndex = self.rootIndex()
        # Match C++: QModelIndex index = model->mkdir(parent, folderName);
        index: QModelIndex = self.model.mkdir(parent, folderName)
        # Match C++: if (!index.isValid()) return;
        if not index.isValid():
            return

        # Match C++: index = select(index);
        index = self.select(index)
        # Match C++: if (index.isValid())
        if index.isValid():
            # Match C++: qFileDialogUi->treeView->setCurrentIndex(index);
            self.qFileDialogUi.treeView.setCurrentIndex(index)
            # Match C++: currentView()->edit(index);
            self.currentView().edit(index)  # pyright: ignore[reportOptionalMemberAccess]

    def _q_showListView(self) -> None:
        """Show list view. Matches C++ QFileDialogPrivate::showListView() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_showListView: No UI setup."
        # Match C++: qFileDialogUi->listModeButton->setDown(true);
        self.qFileDialogUi.listModeButton.setDown(True)
        # Match C++: qFileDialogUi->detailModeButton->setDown(false);
        self.qFileDialogUi.detailModeButton.setDown(False)
        # Match C++: qFileDialogUi->treeView->hide();
        self.qFileDialogUi.treeView.hide()
        # Match C++: qFileDialogUi->listView->show();
        self.qFileDialogUi.listView.show()
        # Match C++: qFileDialogUi->stackedWidget->setCurrentWidget(qFileDialogUi->listView->parentWidget());
        parent_widget: QWidget | None = cast("QWidget", self.qFileDialogUi.listView.parentWidget())
        if parent_widget is not None:
            self.qFileDialogUi.stackedWidget.setCurrentWidget(parent_widget)
        # Match C++: qFileDialogUi->listView->doItemsLayout();
        # Note: In Python Qt bindings, doItemsLayout() may not be available, so we use schedule/execute
        if hasattr(self.qFileDialogUi.listView, "doItemsLayout"):
            self.qFileDialogUi.listView.doItemsLayout()
        else:
            self.qFileDialogUi.listView.scheduleDelayedItemsLayout()
            self.qFileDialogUi.listView.executeDelayedItemsLayout()

    def _q_showDetailsView(self) -> None:
        """Show details view. Matches C++ QFileDialogPrivate::showDetailsView() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_showDetailsView: No UI setup."
        # Match C++: qFileDialogUi->listModeButton->setDown(false);
        self.qFileDialogUi.listModeButton.setDown(False)
        # Match C++: qFileDialogUi->detailModeButton->setDown(true);
        self.qFileDialogUi.detailModeButton.setDown(True)
        # Match C++: qFileDialogUi->listView->hide();
        self.qFileDialogUi.listView.hide()
        # Match C++: qFileDialogUi->treeView->show();
        self.qFileDialogUi.treeView.show()
        # Match C++: qFileDialogUi->stackedWidget->setCurrentWidget(qFileDialogUi->treeView->parentWidget());
        parent_widget: QWidget | None = cast("QWidget", self.qFileDialogUi.treeView.parentWidget())
        if parent_widget is not None:
            self.qFileDialogUi.stackedWidget.setCurrentWidget(parent_widget)
        # Match C++: qFileDialogUi->treeView->doItemsLayout();
        # Note: In Python Qt bindings, doItemsLayout() may not be available, so we use schedule/execute
        if hasattr(self.qFileDialogUi.treeView, "doItemsLayout"):
            self.qFileDialogUi.treeView.doItemsLayout()
        else:
            self.qFileDialogUi.treeView.scheduleDelayedItemsLayout()
            self.qFileDialogUi.treeView.executeDelayedItemsLayout()

    def _q_showContextMenu(
        self,
        position: QPoint,
    ) -> None:
        """Displays a context menu with relevant actions for the selected item.

        This provides quick access to common operations on files and directories.

        If this function is removed, users would lose access to context-specific actions,
        significantly reducing the functionality and usability of the file dialog.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_showContextMenu: No UI setup."
        assert self.model is not None, f"{self.__class__.__name__}._q_showContextMenu: No file system model setup."

        view: QAbstractItemView | None = self.currentView()
        assert view is not None, f"{self.__class__.__name__}._q_showContextMenu: No view found."

        index: QModelIndex = view.indexAt(position)
        index = self.mapToSource(index.sibling(index.row(), 0))

        menu = QMenu(view)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if index.isValid():
            self._add_file_context_menu_actions(menu, index)
        self._add_context_menu_view_actions(menu)
        viewport: QWidget | None = view.viewport()
        assert viewport is not None, f"{self.__class__.__name__}._q_showContextMenu: viewport is None"
        menu.exec(viewport.mapToGlobal(position))

    def _add_file_context_menu_actions(
        self,
        menu: QMenu,  # noqa: ANN001
        index: QModelIndex,
    ) -> None:
        """Populates the context menu with actions specific to the selected file or directory.

        This provides quick access to common file operations.

        If this function is removed, the context menu would lack file-specific actions,
        reducing the functionality and convenience of the file dialog.
        """
        if self.model is None:
            RobustLogger().warning(f"{self.__class__.__name__}._add_file_context_menu_actions: No file system model setup.")
            return

        # Check ReadOnly option from dialog, not just model (matching C++ implementation)
        q = self._public
        read_only_option = sip_enum_to_int(RealQFileDialog.Option.ReadOnly)
        ro: bool = bool(sip_enum_to_int(q.options()) & read_only_option) or (self.model and self.model.isReadOnly())
        # C++ uses index.parent().data(QFileSystemModel::FilePermissions) to get directory permissions
        # This checks if we can write to the parent directory (where the file is located)
        parent_index = index.parent()
        if parent_index.isValid():
            permissions_data = parent_index.data(QFileSystemModel.Roles.FilePermissions)
            if permissions_data is not None:
                p: int = int(permissions_data) if isinstance(permissions_data, (int, QFile.Permission)) else 0
            else:
                # Fallback to fileInfo if parent data is not available
                p = self.model.fileInfo(index).permissions()  # pyright: ignore[reportAssignmentType]
        else:
            # Fallback if no parent
            p = self.model.fileInfo(index).permissions()  # pyright: ignore[reportAssignmentType]

        if self.renameAction is not None:
            self.renameAction.setEnabled(not ro and bool(p & sip_enum_to_int(QFile.Permission.WriteUser)))
            menu.addAction(self.renameAction)
        if self.deleteAction is not None:
            self.deleteAction.setEnabled(not ro and bool(p & sip_enum_to_int(QFile.Permission.WriteUser)))
            menu.addAction(self.deleteAction)
        menu.addSeparator()

    def _add_context_menu_view_actions(
        self,
        menu: QMenu,  # noqa: ANN001
    ) -> None:
        """Adds general view-related actions to the context menu.

        This provides access to view options and other general operations.

        If this function is removed, the context menu would lack important general actions,
        limiting the user's ability to control the view and perform common operations.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._add_context_menu_view_actions: No UI setup."
        if self.showHiddenAction is not None:
            menu.addAction(self.showHiddenAction)
        if self.newFolderAction is not None and self.qFileDialogUi.newFolderButton.isVisible():
            self.newFolderAction.setEnabled(self.qFileDialogUi.newFolderButton.isEnabled())
            menu.addAction(self.newFolderAction)

    def _q_renameCurrent(self) -> None:
        """Rename current item. Matches C++ QFileDialogPrivate::renameCurrent() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_renameCurrent: No UI setup."
        # Match C++: QModelIndex index = qFileDialogUi->listView->currentIndex();
        index: QModelIndex = self.qFileDialogUi.listView.currentIndex()
        # Match C++: index = index.sibling(index.row(), 0);
        index = index.sibling(index.row(), 0)
        # Match C++: if (q->viewMode() == QFileDialog::List)
        q = self._public
        if q.viewMode() == RealQFileDialog.ViewMode.List:
            # Match C++: qFileDialogUi->listView->edit(index);
            self.qFileDialogUi.listView.edit(index)
        else:
            # Match C++: qFileDialogUi->treeView->edit(index);
            self.qFileDialogUi.treeView.edit(index)

    def removeDirectory(
        self,
        path: str,
    ) -> bool:
        """Remove directory. Matches C++ QFileDialogPrivate::removeDirectory() implementation."""
        assert self.model is not None, f"{self.__class__.__name__}.removeDirectory: No model setup."
        # Match C++: QModelIndex modelIndex = model->index(path);
        modelIndex: QModelIndex = self.model.index(path)
        # Match C++: return model->remove(modelIndex);
        return self.model.remove(modelIndex)

    def _q_deleteCurrent(self) -> None:
        """Implements the functionality for deleting files or directories.

        This is a common file management operation that users expect in a file dialog.

        If this function is removed, users would lose the ability to delete files and directories
        from within the file dialog, significantly reducing its file management capabilities.
        """
        if self.qFileDialogUi is None or self.model is None or self.model.isReadOnly():
            return

        sel_model: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
        assert sel_model is not None, f"{self.__class__.__name__}._q_deleteCurrent: No selection model found."
        selectedRows: list[QModelIndex] = sel_model.selectedRows()
        # Use QPersistentModelIndex like C++ (iterating in reverse order)
        for index in reversed(selectedRows):
            persistent_index = QPersistentModelIndex(index)
            self._delete_item(persistent_index)

    def _delete_item(
        self,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Handles the actual deletion of a file or directory.

        Matches C++ deleteCurrent() implementation.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._delete_item: No UI setup."

        # Convert QPersistentModelIndex to QModelIndex if needed, matching C++ behavior
        if isinstance(index, QPersistentModelIndex):
            if not index.isValid() or index == self.qFileDialogUi.listView.rootIndex():
                return
            # Get QModelIndex from QPersistentModelIndex
            model = index.model()
            if model is None:
                return
            temp_index = model.index(index.row(), index.column(), index.parent())
            index = self.mapToSource(temp_index.sibling(temp_index.row(), 0))
        else:
            if not index.isValid() or index.parent() is None or index == self.qFileDialogUi.listView.rootIndex():
                return
            index = self.mapToSource(index.sibling(index.row(), 0))

        if not index.isValid():
            return

        assert self.model is not None, f"{self.__class__.__name__}._delete_item: No file system model setup."

        fileName: str = index.data(QFileSystemModel.Roles.FileNameRole)
        filePath: str = index.data(QFileSystemModel.Roles.FilePathRole)

        # C++ uses index.parent().data(QFileSystemModel::FilePermissions) to get directory permissions
        parent_index = index.parent()
        if parent_index.isValid():
            permissions_data = parent_index.data(QFileSystemModel.Roles.FilePermissions)
            if permissions_data is not None:
                p = int(permissions_data) if isinstance(permissions_data, (int, QFile.Permission)) else 0
            else:
                p = 0
        else:
            p = 0

        # Check write protection and confirm deletion (matching C++ logic)
        if not bool(p & sip_enum_to_int(QFile.Permission.WriteUser)):
            if not self._write_protected_warning(fileName):
                return
        elif not self._confirm_deletion(fileName):
            return

        # the event loop has run, we have to validate if the index is valid because the model might have removed it.
        if not index.isValid():
            return

        if self.model.isDir(index) and not self.model.fileInfo(index).isSymLink():
            if not self.removeDirectory(filePath):
                q = self._public
                QMessageBox.warning(
                    q,
                    q.windowTitle(),
                    q.tr("Could not delete directory.", "QFileDialog"),
                )
        else:
            self.model.remove(index)

    def _write_protected_warning(
        self,
        fileName: str,  # noqa: N803
    ) -> bool:
        """Warns the user when attempting to delete a write-protected file."""
        q = self._public
        result: QMessageBox.StandardButton = QMessageBox.warning(
            q,
            q.tr("Delete", "QFileDialog"),
            q.tr(f"'{fileName}' is write protected.\nDo you want to delete it anyway?", "QFileDialog"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _confirm_deletion(
        self,
        fileName: str,  # noqa: N803
    ) -> bool:
        """Ask for user confirmation before deleting. Matches C++ QFileDialogPrivate::deleteCurrent() confirmation logic."""
        q = self._public
        # Match C++: QMessageBox::warning(q_func(), QFileDialog::tr("Delete"), QFileDialog::tr("Are you sure you want to delete '%1'?").arg(fileName), ...)
        msg_template = q.tr("Are you sure you want to delete '%1'?")
        msg = msg_template.replace("%1", fileName)
        result: QMessageBox.StandardButton = QMessageBox.warning(
            q,
            q.tr("Delete"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _show_deletion_error(self) -> None:
        """Show an error message for failed deletion.

        Displays an error message when a directory deletion fails.
        This informs the user that the operation was unsuccessful and allows them to take appropriate action.
        """
        q = self._public
        QMessageBox.warning(q, q.windowTitle(), q.tr("Could not delete directory.", "QFileDialog"))

    def _q_autoCompleteFileName(
        self,
        text: str,
    ) -> None:
        """Auto-complete the file name.

        Provides auto-completion functionality for file names in the dialog.
        This improves user efficiency by suggesting matching file names as the user types.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_autoCompleteFileName: No UI setup."
        # Match C++: if (text.startsWith("//"_L1) || text.startsWith(u'\\'))
        if text.startswith(("//", "\\")):
            # Match C++: qFileDialogUi->listView->selectionModel()->clearSelection(); return;
            sel_listview_model: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
            if sel_listview_model is not None:
                sel_listview_model.clearSelection()
            return

        assert self.model is not None, f"{self.__class__.__name__}._q_autoCompleteFileName: No model setup."
        # Match C++: const QStringList multipleFiles = typedFiles();
        multipleFiles: list[str] = self.typedFiles()
        # Match C++: if (multipleFiles.size() > 0)
        if multipleFiles:
            # Match C++: QModelIndexList oldFiles = qFileDialogUi->listView->selectionModel()->selectedRows();
            sel_listview_model = self.qFileDialogUi.listView.selectionModel()
            assert sel_listview_model is not None, f"{self.__class__.__name__}._q_autoCompleteFileName: No selection model found."
            oldFiles: list[QModelIndex] = sel_listview_model.selectedRows()
            # Match C++: QList<QModelIndex> newFiles;
            newFiles: list[QModelIndex] = []
            # Match C++: for (const auto &file : multipleFiles)
            for file in multipleFiles:
                # Match C++: QModelIndex idx = model->index(file);
                idx: QModelIndex = self.model.index(file)
                # Match C++: if (oldFiles.removeAll(idx) == 0)
                # removeAll() removes all occurrences and returns count
                removed_count = 0
                while idx in oldFiles:
                    oldFiles.remove(idx)
                    removed_count += 1
                if removed_count == 0:
                    # Match C++: newFiles.append(idx);
                    newFiles.append(idx)
            # Match C++: for (const auto &newFile : std::as_const(newFiles))
            for newFile in newFiles:
                # Match C++: select(newFile);
                self.select(newFile)
            # Match C++: if (lineEdit()->hasFocus())
            if self.lineEdit().hasFocus():
                # Match C++: auto *sm = qFileDialogUi->listView->selectionModel();
                # Match C++: for (const auto &oldFile : std::as_const(oldFiles))
                for oldFile in oldFiles:
                    # Match C++: sm->select(oldFile, QItemSelectionModel::Toggle | QItemSelectionModel::Rows);
                    sel_listview_model.select(oldFile, QItemSelectionModel.SelectionFlag.Toggle | QItemSelectionModel.SelectionFlag.Rows)

    def typedFiles(self) -> list[str]:
        """Returns the text in the line edit which can be one or more file names.

        Parses the user input in the file name field to extract file names.
        This is essential for handling user-typed file names, especially in save dialogs.
        """
        q = self._public
        files: list[str] = []
        # Match C++: QString editText = lineEdit()->text();
        editText: str = self.lineEdit().text()
        # Match C++: if (!editText.contains(u'"')) {
        if '"' not in editText:
            prefix: str = q.directory().absolutePath() + QDir.separator()
            if os.path.exists(os.path.join(prefix, editText)):  # noqa: PTH110, PTH118
                files.append(editText)
            else:
                files.append(self.qt_tildeExpansion(editText))
        else:
            # Match C++: // " is used to separate files like so: "file1" "file2" "file3" ...
            # Match C++: // ### need escape character for filenames with quotes (")
            # Match C++: QStringList tokens = editText.split(u'\"');
            tokens: list[str] = editText.split('"')
            # Match C++: for (int i=0; i<tokens.size(); ++i) { if ((i % 2) == 0) continue; // Every even token is a separator
            for i in range(len(tokens)):
                if (i % 2) == 0:
                    continue  # Every even token is a separator
                # Match C++: #ifdef Q_OS_UNIX ... #else ... #endif
                if os.name == "posix":
                    # Match C++: const QString token = tokens.at(i);
                    token: str = tokens[i]
                    # Match C++: const QString prefix = q->directory().absolutePath() + QDir::separator();
                    prefix = q.directory().absolutePath() + QDir.separator()
                    # Match C++: if (QFile::exists(prefix + token)) files << token; else files << qt_tildeExpansion(token);
                    if os.path.exists(prefix + token):  # noqa: PTH110
                        files.append(token)
                    else:
                        files.append(self.qt_tildeExpansion(token))
                else:
                    # Match C++: #else files << toInternal(tokens.at(i)); #endif
                    files.append(self.toInternal(tokens[i]))
        return self.addDefaultSuffixToFiles(files)

    def qt_tildeExpansion(
        self,
        path: str,
    ) -> str:
        """Expand tilde in file paths.

        Matches C++ qt_tildeExpansion() implementation exactly.
        Handles ~, ~/, ~user, and ~user/path formats.
        """
        if not path.startswith("~"):
            return path

        if len(path) == 1:  # '~'
            return QDir.homePath()

        # Find separator index
        sep_index = path.find(QDir.separator())
        if sep_index == 1:  # '~/' or '~/a/b/c'
            return QDir.homePath() + path[1:]

        # Handle ~user format (Unix-like systems only)
        if os.name == "posix":
            if sep_index == -1:
                # '~user' - no separator found
                user_name_len = len(path) - 1  # length of "~"
                user_name = path[1 : user_name_len + 1]
            else:
                # '~user/a/b'
                user_name_len = sep_index - 1  # length of "~"
                user_name = path[1:sep_index]

            # Try to get home directory for the user
            try:
                import pwd

                try:
                    pw = pwd.getpwnam(user_name)
                    home_path = pw.pw_dir
                except KeyError:
                    # User not found, return original path
                    return path
            except ImportError:
                # pwd module not available (Windows), use expanduser
                home_path = os.path.expanduser(f"~{user_name}")  # noqa: PTH111
                if home_path == f"~{user_name}":
                    return path

            if sep_index == -1:
                return home_path
            return home_path + path[sep_index:]

        # Non-Unix systems: just use expanduser
        return os.path.expanduser(path)  # noqa: PTH111

    def toInternal(
        self,
        path: str,
    ) -> str:
        """Convert file path to internal representation.

        Matches C++ QFileDialogPrivate::toInternal() implementation exactly.
        On Windows: replaces backslashes with forward slashes.
        On other platforms: returns path unchanged.
        """
        # Match C++: #if defined(Q_OS_WIN) ... #else return path; #endif
        if os.name == "nt":  # Windows
            return path.replace("\\", "/")
        return path

    def basename(self, path: str) -> str:
        """Extract the filename from a path. Matches C++ QFileDialogPrivate::basename() implementation."""
        # Match C++: const qsizetype separator = QDir::toNativeSeparators(path).lastIndexOf(QDir::separator());
        native_path = QDir.toNativeSeparators(path)
        separator_index = native_path.rfind(QDir.separator())
        # Match C++: if (separator != -1)
        if separator_index != -1:
            # Match C++: return path.mid(separator + 1);
            return path[separator_index + 1 :]
        # Match C++: return path;
        return path

    def getEnvironmentVariable(self, string: str) -> str:
        """Expand environment variables in the given string.

        Matches C++ QFileDialogPrivate::getEnvironmentVariable() implementation exactly.
        On Unix: expands $VAR format using qEnvironmentVariable
        On Windows: expands %VAR% format using qEnvironmentVariable
        Otherwise returns the string unchanged.
        """
        # Match C++: if (string.size() > 1 && string.startsWith(u'$'))
        if len(string) > 1 and string.startswith("$"):
            # Match C++: return qEnvironmentVariable(QStringView{string}.mid(1).toLatin1().constData());
            var_name = string[1:]
            # qEnvironmentVariable returns empty string if not found, but we return original string if not found
            result = os.environ.get(var_name, "")
            return result if result else string
        # Match C++: if (string.size() > 2 && string.startsWith(u'%') && string.endsWith(u'%'))
        elif len(string) > 2 and string.startswith("%") and string.endswith("%"):
            # Match C++: return qEnvironmentVariable(QStringView{string}.mid(1, string.size() - 2).toLatin1().constData());
            var_name = string[1:-1]
            result = os.environ.get(var_name, "")
            return result if result else string
        return string

    def filterForMode(
        self,
        filters: QDir.Filter,
    ) -> QDir.Filter:
        combined: int = (
            sip_enum_to_int(filters)
            | sip_enum_to_int(QDir.Filter.Drives)
            | sip_enum_to_int(QDir.Filter.AllDirs)
            | sip_enum_to_int(QDir.Filter.Dirs)
            | sip_enum_to_int(QDir.Filter.Files)
        )
        if self._public.testOption(RealQFileDialog.Option.ShowDirsOnly):
            combined &= ~sip_enum_to_int(QDir.Filter.Files)
        return QDir.Filter(combined)

    def _q_updateOkButton(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """Dynamically enables or disables the OK button based on the current selection and dialog mode.

        Ensures that the button is only active when a valid selection or input is present.
        """
        q = self._public
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_updateOkButton: No UI setup."
        accept_mode: RealQFileDialog.AcceptMode = q.acceptMode()
        button_role: QDialogButtonBox.StandardButton = (
            QDialogButtonBox.StandardButton.Open if accept_mode == RealQFileDialog.AcceptMode.AcceptOpen else QDialogButtonBox.StandardButton.Save
        )
        button: QPushButton | None = self.qFileDialogUi.buttonBox.button(button_role)
        if button is None:
            return
        fileMode: int = sip_enum_to_int(q.fileMode())

        enableButton: bool = True
        isOpenDirectory: bool = False

        files: list[str] = q.selectedFiles()
        lineEditText: str = self.lineEdit().text()

        if lineEditText.startswith(("//", "\\")):
            button.setEnabled(True)
            self.updateOkButtonText()
            return

        if not files:
            enableButton = False
        elif lineEditText == "..":
            isOpenDirectory = True
        elif fileMode == sip_enum_to_int(RealQFileDialog.FileMode.Directory):
            assert self.model is not None, f"{self.__class__.__name__}._q_updateOkButton: No file system model setup."
            # C++ implementation: simpler - just check first file
            fn = files[0] if files else ""
            idx: QModelIndex = self.model.index(fn)
            if not idx.isValid():
                idx = self.model.index(self.getEnvironmentVariable(fn))
            if not idx.isValid() or not self.model.isDir(idx):
                enableButton = False
        elif fileMode == sip_enum_to_int(RealQFileDialog.FileMode.AnyFile):
            assert self.model is not None, f"{self.__class__.__name__}._q_updateOkButton: No file system model setup."
            if not files:
                enableButton = False
            else:
                fn = files[0]
                info = QFileInfo(fn)
                idx = self.model.index(fn)
                fileDir: str = ""
                fileName: str = ""
                if info.isDir():
                    fileDir = info.canonicalFilePath()
                else:
                    # C++ uses fn.mid(0, fn.lastIndexOf(u'/')) and fn.mid(fileDir.size() + 1)
                    last_slash = fn.rfind("/")
                    if last_slash != -1:
                        fileDir = fn[:last_slash]
                        fileName = fn[last_slash + 1 :]
                    else:
                        fileDir = ""
                        fileName = fn
                if ".." in lineEditText:
                    fileDir = info.canonicalFilePath()
                    fileName = info.fileName()

                # Match C++: if (fileDir == q->directory().canonicalPath() && fileName.isEmpty()) { enableButton = false; break; }
                if fileDir == q.directory().canonicalPath() and not fileName:
                    enableButton = False
                    # break (implicit in Python elif chain, but C++ uses explicit break)
                # Match C++: if (idx.isValid() && model->isDir(idx)) { isOpenDirectory = true; enableButton = true; break; }
                elif idx.isValid() and self.model.isDir(idx):
                    isOpenDirectory = True
                    enableButton = True
                    # break (implicit in Python elif chain, but C++ uses explicit break)
                # Match C++: if (!idx.isValid()) { const long maxLength = maxNameLength(fileDir); enableButton = maxLength < 0 || fileName.size() <= maxLength; }
                elif not idx.isValid():
                    maxLength: int = QFileDialogPrivate.maxNameLength(fileDir)
                    enableButton = maxLength < 0 or len(fileName) <= maxLength
        elif fileMode in (sip_enum_to_int(RealQFileDialog.FileMode.ExistingFile), sip_enum_to_int(RealQFileDialog.FileMode.ExistingFiles)):
            assert self.model is not None, f"{self.__class__.__name__}._q_updateOkButton: No file system model setup."
            for file in files:
                idx = self.model.index(file)
                if not idx.isValid():
                    idx = self.model.index(self.getEnvironmentVariable(file))
                if not idx.isValid():
                    enableButton = False
                    break
                if idx.isValid() and self.model.isDir(idx):
                    isOpenDirectory = True
                    break

        button.setEnabled(enableButton)
        self.updateOkButtonText(isOpenDirectory)

    def updateOkButtonText(
        self,
        save_as_on_folder: bool = False,  # noqa: FBT002, FBT001, N803
    ) -> None:
        """Update OK button text. Matches C++ QFileDialogPrivate::updateOkButtonText() implementation."""
        q = self._public
        # Match C++: // 'Save as' at a folder: Temporarily change to "Open".
        if save_as_on_folder:
            # Match C++: setLabelTextControl(QFileDialog::Accept, QFileDialog::tr("&Open"));
            self.setLabelTextControl(RealQFileDialog.DialogLabel.Accept, q.tr("&Open"))
        # Match C++: else if (options->isLabelExplicitlySet(QFileDialogOptions::Accept))
        elif self.options.isLabelExplicitlySet(RealQFileDialog.DialogLabel.Accept):
            # Match C++: setLabelTextControl(QFileDialog::Accept, options->labelText(QFileDialogOptions::Accept));
            self.setLabelTextControl(
                RealQFileDialog.DialogLabel.Accept,
                self.options.labelText(RealQFileDialog.DialogLabel.Accept),
            )
            return
        else:
            # Match C++: switch (q->fileMode())
            mode = q.fileMode()
            # Match C++: case QFileDialog::Directory:
            if sip_enum_to_int(mode) == sip_enum_to_int(RealQFileDialog.FileMode.Directory):
                # Match C++: setLabelTextControl(QFileDialog::Accept, QFileDialog::tr("&Choose"));
                self.setLabelTextControl(RealQFileDialog.DialogLabel.Accept, q.tr("&Choose"))
            # Match C++: default:
            else:
                # Match C++: setLabelTextControl(QFileDialog::Accept, q->acceptMode() == QFileDialog::AcceptOpen ? QFileDialog::tr("&Open") : QFileDialog::tr("&Save"));
                text: str = q.tr("&Open") if sip_enum_to_int(q.acceptMode()) == sip_enum_to_int(RealQFileDialog.AcceptMode.AcceptOpen) else q.tr("&Save")
                self.setLabelTextControl(RealQFileDialog.DialogLabel.Accept, text)

    def setLabelTextControl(
        self,
        label: RealQFileDialog.DialogLabel,
        text: str,
    ) -> None:
        """Set label text control. Matches C++ QFileDialogPrivate::setLabelTextControl() implementation."""
        # Match C++: if (!qFileDialogUi) return;
        if not self.qFileDialogUi:
            return
        # Match C++: switch (label)
        label_enum = label
        # Match C++: case QFileDialog::LookIn:
        if label_enum == RealQFileDialog.DialogLabel.LookIn:
            # Match C++: qFileDialogUi->lookInLabel->setText(text); break;
            self.qFileDialogUi.lookInLabel.setText(text)
        # Match C++: case QFileDialog::FileName:
        elif label_enum == RealQFileDialog.DialogLabel.FileName:
            # Match C++: qFileDialogUi->fileNameLabel->setText(text); break;
            self.qFileDialogUi.fileNameLabel.setText(text)
        # Match C++: case QFileDialog::FileType:
        elif label_enum == RealQFileDialog.DialogLabel.FileType:
            # Match C++: qFileDialogUi->fileTypeLabel->setText(text); break;
            self.qFileDialogUi.fileTypeLabel.setText(text)
        # Match C++: case QFileDialog::Accept:
        elif label_enum == RealQFileDialog.DialogLabel.Accept:
            # Match C++: if (q_func()->acceptMode() == QFileDialog::AcceptOpen)
            q = self._public
            if q.acceptMode() == RealQFileDialog.AcceptMode.AcceptOpen:
                # Match C++: if (QPushButton *button = qFileDialogUi->buttonBox->button(QDialogButtonBox::Open))
                button: QPushButton | None = self.qFileDialogUi.buttonBox.button(QDialogButtonBox.StandardButton.Open)
                # Match C++: button->setText(text);
                if button is not None:
                    button.setText(text)
            else:
                # Match C++: if (QPushButton *button = qFileDialogUi->buttonBox->button(QDialogButtonBox::Save))
                button = self.qFileDialogUi.buttonBox.button(QDialogButtonBox.StandardButton.Save)
                # Match C++: button->setText(text);
                if button is not None:
                    button.setText(text)
        # Match C++: case QFileDialog::Reject:
        elif label_enum == RealQFileDialog.DialogLabel.Reject:
            # Match C++: if (QPushButton *button = qFileDialogUi->buttonBox->button(QDialogButtonBox::Cancel))
            button = self.qFileDialogUi.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
            # Match C++: button->setText(text);
            if button is not None:
                button.setText(text)

    def _q_goToUrl(
        self,
        url: QUrl,
    ) -> None:
        """Navigate to the specified URL.

        Matches C++ QFileDialogPrivate::goToUrl() implementation.
        The shortcut in the side bar may have a parent that is not fetched yet (e.g. an hidden file)
        so we force the fetching.
        """
        assert self.model is not None, f"{self.__class__.__name__}._q_goToUrl: No model setup."
        # Match C++: //The shortcut in the side bar may have a parent that is not fetched yet (e.g. an hidden file)
        # Match C++: //so we force the fetching
        # Match C++: QFileSystemModelPrivate::QFileSystemNode *node = model->d_func()->node(url.toLocalFile(), true);
        # Match C++: QModelIndex idx =  model->d_func()->index(node);
        # Note: In Python, we don't have direct access to d_func(), so we use model.index() which should work
        # The force fetching is handled internally by QFileSystemModel when needed
        local_path: str = url.toLocalFile()
        idx: QModelIndex = self.model.index(local_path)
        # Match C++: enterDirectory(idx);
        if idx.isValid():
            self._q_enterDirectory(idx)

    def select(
        self,
        index: QModelIndex,
    ) -> QModelIndex:
        """Select an item in the list view. Matches C++ QFileDialogPrivate::select() implementation."""
        # Match C++: Q_ASSERT(index.isValid() ? index.model() == model : true);
        assert self.model is not None, f"{self.__class__.__name__}.select: No model setup."
        if index.isValid():
            assert index.model() == self.model, f"{self.__class__.__name__}.select: Index model mismatch."
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.select: No UI setup."
        # Match C++: QModelIndex idx = mapFromSource(index);
        idx: QModelIndex = self.mapFromSource(index)
        # Match C++: if (idx.isValid() && !qFileDialogUi->listView->selectionModel()->isSelected(idx))
        sel_listview_model: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
        assert sel_listview_model is not None, f"{self.__class__.__name__}.select: No selection model found."
        if idx.isValid() and not sel_listview_model.isSelected(idx):
            # Match C++: qFileDialogUi->listView->selectionModel()->select(idx, QItemSelectionModel::Select | QItemSelectionModel::Rows);
            sel_listview_model.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        # Match C++: return idx;
        return idx

    def _q_showHidden(self) -> None:
        """Includes hidden files and directories in the items displayed in the dialog.

        Matches C++ QFileDialogPrivate::showHidden() implementation.
        """
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: QDir::Filters dirFilters = q->filter();
        dirFilters = q.filter()
        # Match C++: dirFilters.setFlag(QDir::Hidden, showHiddenAction->isChecked());
        # In Python, we need to set/unset the flag based on action state
        assert self.showHiddenAction is not None, f"{self.__class__.__name__}._q_showHidden: No showHiddenAction."
        is_checked = self.showHiddenAction.isChecked()
        hidden_flag = QDir.Filter.Hidden
        if is_checked:
            dirFilters = QDir.Filter(sip_enum_to_int(dirFilters) | sip_enum_to_int(hidden_flag))
        else:
            dirFilters = QDir.Filter(sip_enum_to_int(dirFilters) & ~sip_enum_to_int(hidden_flag))
        # Match C++: q->setFilter(dirFilters);
        q.setFilter(dirFilters)

    def _q_rowsInserted(
        self,
        parent: QModelIndex,
    ) -> None:
        """When parent is root and rows have been inserted when none was there before then select the first one.

        Matches C++ QFileDialogPrivate::rowsInserted() implementation.
        Note: The C++ implementation just returns early if conditions aren't met, but doesn't actually select.
        However, the comment suggests it should select the first one, so this might be incomplete in C++.
        """
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}._q_rowsInserted: {type(self.qFileDialogUi).__name__} is None"
        # Match C++: if (!qFileDialogUi->treeView
        # Match C++: || parent != qFileDialogUi->treeView->rootIndex()
        # Match C++: || !qFileDialogUi->treeView->selectionModel()
        # Match C++: || qFileDialogUi->treeView->selectionModel()->hasSelection()
        # Match C++: || qFileDialogUi->treeView->model()->rowCount(parent) == 0)
        # Match C++: return;
        treeview_model: QAbstractItemModel | None = self.qFileDialogUi.treeView.model()
        sel_treeview_model: QItemSelectionModel | None = self.qFileDialogUi.treeView.selectionModel()
        if (
            not self.qFileDialogUi.treeView
            or parent != self.qFileDialogUi.treeView.rootIndex()
            or sel_treeview_model is None
            or sel_treeview_model.hasSelection()
            or treeview_model is None
            or treeview_model.rowCount(parent) == 0
        ):
            return
        # Note: C++ implementation just returns, but comment says "then select the first one"
        # This might be incomplete in C++ or handled elsewhere

    def _q_fileRenamed(
        self,
        path: str,
        oldName: str,  # noqa: N803
        newName: str,  # noqa: N803
    ) -> None:
        """Updates the dialog's state when a file or directory is renamed.

        Ensures that the dialog reflects the current state of the file system accurately.

        If this function is removed, the dialog might display outdated information
        after file renames, leading to confusion and potential errors in file operations.
        """
        # Match C++: const QFileDialog::FileMode fileMode = q_func()->fileMode();
        q = self._public
        fileMode = q.fileMode()
        # Match C++: if (fileMode == QFileDialog::Directory)
        if fileMode == RealQFileDialog.FileMode.Directory:
            # Match C++: if (path == rootPath() && lineEdit()->text() == oldName)
            if path == self.rootPath() and self.lineEdit().text() == oldName:
                # Match C++: lineEdit()->setText(newName);
                self.lineEdit().setText(newName)

    def _q_emitUrlSelected(
        self,
        file: QUrl,
    ) -> None:
        """Emit urlSelected signal. Matches C++ QFileDialogPrivate::emitUrlSelected() implementation."""
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: emit q->urlSelected(file);
        q.urlSelected.emit(file)
        # Match C++: if (file.isLocalFile())
        if file.isLocalFile():
            # Match C++: emit q->fileSelected(file.toLocalFile());
            q.fileSelected.emit(file.toLocalFile())

    def _q_emitUrlsSelected(
        self,
        files: list[QUrl],
    ) -> None:
        """Emit urlsSelected signal. Matches C++ QFileDialogPrivate::emitUrlsSelected() implementation."""
        # Match C++: Q_Q(QFileDialog);
        q = self._public
        # Match C++: emit q->urlsSelected(files);
        q.urlsSelected.emit(files)
        # Match C++: QStringList localFiles;
        localFiles: list[str] = []
        # Match C++: for (const QUrl &file : files)
        for file in files:
            # Match C++: if (file.isLocalFile())
            if file.isLocalFile():
                # Match C++: localFiles.append(file.toLocalFile());
                localFiles.append(file.toLocalFile())
        # Match C++: if (!localFiles.isEmpty())
        if localFiles:
            # Match C++: emit q->filesSelected(localFiles);
            q.filesSelected.emit(localFiles)

    def _q_nativeCurrentChanged(
        self,
        file: QUrl,
    ) -> None:
        """Notifies listeners about changes in the current URL and file selection in native dialogs.

        Ensures that the application stays updated with the user's current selection in native dialogs.
        """
        q = self._public
        q.currentUrlChanged.emit(file)
        if file.isLocalFile():
            q.currentChanged.emit(file.toLocalFile())

    def _q_nativeEnterDirectory(
        self,
        directory: QUrl,
    ) -> None:
        """Notifies listeners when a new directory is entered in native dialogs.

        Crucial for updating the application's state to reflect the current directory in native dialogs.
        """
        q = self._public
        q.directoryUrlEntered.emit(directory)
        # Windows native dialogs occasionally emit signals with empty strings - check for that
        if not directory.isEmpty():
            self.setLastVisitedDirectory(directory)
            if directory.isLocalFile():
                q.directoryEntered.emit(directory.toLocalFile())

    def canBeNativeDialog(self) -> bool:
        """Determines whether the current platform supports native file dialogs.

        This is important for deciding whether to use native dialogs or Qt-based dialogs.
        """
        return False  # TODO(th3w1zard1): Implement this

    def _q_currentChanged(
        self,
        index: QModelIndex,
    ) -> None:
        """Called when the model index corresponding to the current file is changed.

        Matches C++ QFileDialogPrivate::currentChanged() implementation.
        """
        # Match C++: updateOkButton();
        self._q_updateOkButton()
        # Match C++: emit q_func()->currentChanged(index.data(QFileSystemModel::FilePathRole).toString());
        path_data = index.data(QFileSystemModel.Roles.FilePathRole)
        path_str = str(path_data) if path_data is not None else ""
        self.q_func().currentChanged.emit(path_str)

    def _q_selectionChanged(self) -> None:
        """Called when the model index corresponding to the current file is changed.

        Matches C++ QFileDialogPrivate::selectionChanged() implementation.
        """
        assert self.model is not None, f"{self.__class__.__name__}._q_selectionChanged: {type(self.model).__name__} is None"
        assert self.qFileDialogUi is not None, f"{type(self.qFileDialogUi).__name__}._q_selectionChanged: {type(self.qFileDialogUi).__name__} is None"
        # Match C++: const QFileDialog::FileMode fileMode = q_func()->fileMode();
        q = self._public
        file_mode = q.fileMode()
        # Match C++: const QModelIndexList indexes = qFileDialogUi->listView->selectionModel()->selectedRows();
        sel_listview_model: QItemSelectionModel | None = self.qFileDialogUi.listView.selectionModel()
        assert sel_listview_model is not None, f"{self.__class__.__name__}._q_selectionChanged: No selection model found."
        indexes: list[QModelIndex] = sel_listview_model.selectedRows()
        # Match C++: bool stripDirs = fileMode != QFileDialog::Directory;
        directory_mode = RealQFileDialog.FileMode.Directory
        strip_dirs: bool = file_mode != directory_mode

        # Match C++: QStringList allFiles;
        all_files: list[str] = []
        # Match C++: for (const auto &index : indexes)
        for index in indexes:
            # Match C++: if (stripDirs && model->isDir(mapToSource(index))) continue;
            if strip_dirs and self.model.isDir(self.mapToSource(index)):
                continue
            # Match C++: allFiles.append(index.data().toString());
            index_data = index.data()
            all_files.append(str(index_data) if index_data is not None else "")
        # Match C++: if (allFiles.size() > 1)
        if len(all_files) > 1:
            # Match C++: for (qsizetype i = 0; i < allFiles.size(); ++i)
            # Match C++: allFiles.replace(i, QString(u'"' + allFiles.at(i) + u'"'));
            for i in range(len(all_files)):
                all_files[i] = f'"{all_files[i]}"'

        # Match C++: QString finalFiles = allFiles.join(u' ');
        final_files: str = " ".join(all_files)
        # Match C++: if (!finalFiles.isEmpty() && !lineEdit()->hasFocus() && lineEdit()->isVisible())
        if final_files and not self.lineEdit().hasFocus() and self.lineEdit().isVisible():
            # Match C++: lineEdit()->setText(finalFiles);
            self.lineEdit().setText(final_files)
        else:
            # Match C++: updateOkButton();
            self._q_updateOkButton()

    def _q_enterDirectory(
        self,
        index: QModelIndex,
    ) -> None:
        """Handles the action of entering a selected directory.

        Matches C++ enterDirectory() implementation including KDE single-click activation logic.
        """
        if not index.isValid() or self.model is None:
            return

        q = self._public
        # Match C++: // My Computer or a directory
        # Match C++: QModelIndex sourceIndex = index.model() == proxyModel ? mapToSource(index) : index;
        sourceIndex: QModelIndex = self.mapToSource(index) if (self.proxyModel and index.model() == self.proxyModel) else index
        # Match C++: QString path = sourceIndex.data(QFileSystemModel::FilePathRole).toString();
        path_data = sourceIndex.data(QFileSystemModel.Roles.FilePathRole)
        path: str = str(path_data) if path_data is not None else ""
        # Match C++: if (path.isEmpty() || model->isDir(sourceIndex))
        if not path or self.model.isDir(sourceIndex):
            # Match C++: if (q->directory().path() == path) return;
            if q.directory().path() == path:
                return

            # Match C++: const QFileDialog::FileMode fileMode = q->fileMode();
            fileMode = q.fileMode()
            # Match C++: q->setDirectory(path);
            q.setDirectory(path)
            # Match C++: emit q->directoryEntered(path);
            q.directoryEntered.emit(path)
            # Match C++: if (fileMode == QFileDialog::Directory)
            if fileMode == RealQFileDialog.FileMode.Directory:
                # Match C++: // ### find out why you have to do both of these.
                # Match C++: lineEdit()->setText(QString());
                self.lineEdit().setText("")
                # Match C++: lineEdit()->clear();
                self.lineEdit().clear()
        else:
            # Match C++: // Do not accept when shift-clicking to multi-select a file in environments with single-click-activation (KDE)
            from qtpy.QtGui import QGuiApplication

            # Match C++: if ((!q->style()->styleHint(QStyle::SH_ItemView_ActivateItemOnSingleClick, nullptr, qFileDialogUi->treeView)
            style_hint = q.style().styleHint(QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick, None, self.qFileDialogUi.treeView if self.qFileDialogUi else None)
            # Match C++: || q->fileMode() != QFileDialog::ExistingFiles || !(QGuiApplication::keyboardModifiers() & Qt::CTRL))
            keyboard_modifiers = QGuiApplication.keyboardModifiers()
            ctrl_pressed = bool(keyboard_modifiers & Qt.KeyboardModifier.ControlModifier)
            # Match C++: && index.model()->flags(index) & Qt::ItemIsEnabled)
            index_flags = index.model().flags(index)
            item_enabled = bool(index_flags & Qt.ItemFlag.ItemIsEnabled)
            # Match C++: { q->accept(); }
            if (not style_hint or q.fileMode() != RealQFileDialog.FileMode.ExistingFiles or not ctrl_pressed) and item_enabled:
                q.accept()

    def _q_goHome(self) -> None:
        """Provides a quick way to navigate to the user's home directory.

        This is a common and expected feature in file dialogs for easy access to personal files.
        """
        q = self._public
        q.setDirectory(QDir.homePath())

    def _q_showHeader(
        self,
        action: QAction,  # noqa: ANN001  # pyright: ignore[reportInvalidTypeForm]
    ) -> None:
        """Toggles the visibility of specific columns in the details view.

        Matches C++ showHeader() implementation which uses sender() to get action group.
        """
        if self.qFileDialogUi is None:
            return

        q = self._public
        # C++ uses q->sender() to get the action group - match that approach
        # In PyQt/PySide, sender() is a QObject method
        actionGroup: QActionGroup | None = None
        try:
            # Try to get sender if available (PyQt/PySide support this)
            if hasattr(q, "sender"):
                sender: QObject | None = q.sender()
                if sender is not None and isinstance(sender, QActionGroup):
                    actionGroup = sender
        except (AttributeError, TypeError, RuntimeError):
            pass

        # Fallback to stored action group if sender() not available or didn't work
        if actionGroup is None:
            actionGroup = self.showActionGroup

        if actionGroup is None:
            return

        header: QHeaderView | None = self.qFileDialogUi.treeView.header()
        assert header is not None, f"{self.__class__.__name__}._q_showHeader: No header found."
        columnIndex: int = actionGroup.actions().index(action) + 1
        header.setSectionHidden(columnIndex, not action.isChecked())

    def setLastVisitedDirectory(
        self,
        dir: QUrl,  # noqa: F811, A002
    ) -> None:
        """Updates the record of the last directory visited by the user.

        This is important for maintaining navigation history and providing quick access to recent locations.
        """
        self.lastVisitedDir = dir

    def setVisible(
        self,
        visible: bool,  # noqa: FBT001
    ) -> None:
        """Internal method to handle visibility changes.

        The logic has to live here so that the call to hide() QDialog calls
        this function; it wouldn't call an override of QDialog::setVisible().
        """
        q = self._public
        if visible:
            if q.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide) and not q.testAttribute(Qt.WidgetAttribute.WA_WState_Hidden):
                return
        elif q.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide) and q.testAttribute(Qt.WidgetAttribute.WA_WState_Hidden):
            return

        if self.canBeNativeDialog():
            # NOTE: this is QDialogPrivate::setNativeDialogVisible(visible)!
            # Since we don't want to define
            # the entirety of QDialogPrivate (qfiledialogprivate was already too much),
            # the following line will be skipped.
            #
            # if self.setNativeDialogVisible(visible):
            #
            # Instead, the following line will be used:
            if self.options.testOption(RealQFileDialog.Option.DontUseNativeDialog):
                # Set WA_DontShowOnScreen so that QDialogPrivate::setVisible(visible) below
                # updates the state correctly, but skips showing the non-native version:
                q.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
                # So the completer doesn't try to complete and therefore show a popup
                if not self.nativeDialogInUse:
                    assert self.completer is not None, f"{self.__class__.__name__}.setVisible: Completer is not initialized."
                    self.completer.setModel(None)  # pyright: ignore[reportArgumentType]
            else:
                self.createWidgets()
                q.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)  # noqa: FBT003
                if not self.nativeDialogInUse:
                    assert self.completer is not None, f"{self.__class__.__name__}.setVisible: Completer is not initialized."
                    if self.proxyModel is not None:
                        self.completer.setModel(self.proxyModel)
                    else:
                        assert self.model is not None, f"{self.__class__.__name__}.setVisible: File system model is not initialized."
                        self.completer.setModel(self.model)

        if visible and self.usingWidgets():
            assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.setVisible: No UI setup."
            self.qFileDialogUi.fileNameEdit.setFocus()

        QDialog.setVisible(q, visible)  # NOTE: QDialogPrivate::setVisible(visible);

    def lineEdit(self) -> QLineEdit:
        """Return the line edit widget. Matches C++ QFileDialogPrivate::lineEdit() implementation."""
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.lineEdit: No UI setup."
        # Match C++: return (QLineEdit*)qFileDialogUi->fileNameEdit;
        return self.qFileDialogUi.fileNameEdit

    def restoreFromSettings(self) -> bool:
        """Attempts to restore the dialog's state from previously saved settings.

        Helps maintain consistency in the dialog's appearance and behavior across sessions.
        """
        settings = QSettings(QSettings.Scope.UserScope, "QtProject")
        if "FileDialog" not in settings.childGroups():
            return False

        q = self._public
        settings.beginGroup("FileDialog")

        # Match C++: q->setDirectoryUrl(lastVisitedDir()->isEmpty() ? settings.value("lastVisited").toUrl() : *lastVisitedDir());
        if self.lastVisitedDir.isEmpty():
            lastVisited: str | None = settings.value("lastVisited")
            if lastVisited:
                q.setDirectoryUrl(QUrl(lastVisited))
        else:
            q.setDirectoryUrl(self.lastVisitedDir)

        viewMode = RealQFileDialog.ViewMode.Detail if settings.value("viewMode") == "Detail" else RealQFileDialog.ViewMode.List
        if sip_enum_to_int(viewMode):
            q.setViewMode(viewMode)

        self.sidebarUrls = [QUrl(url) for url in settings.value("shortcuts", [])]
        self.headerData = settings.value("treeViewHeader", QByteArray())

        history: list[str] = []
        urlStrings: list[str] = settings.value("history", [])
        for urlStr in urlStrings:
            url = QUrl(urlStr)
            if url.isLocalFile():
                history.append(url.toLocalFile())

        sidebarWidth: int = int(settings.value("sidebarWidth", -1))

        return self.restoreWidgetState(history, sidebarWidth)

    def saveSettings(self) -> None:
        """Saves the current state and configuration of the file dialog to persistent settings.

        Allows user preferences and configurations to be remembered across sessions.
        """
        q = self._public
        settings = QSettings(QSettings.Scope.UserScope, "QtProject")
        settings.beginGroup("FileDialog")

        if self.usingWidgets():
            assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.saveSettings: No UI setup."
            settings.setValue("sidebarWidth", self.qFileDialogUi.splitter.sizes()[0])
            settings.setValue("shortcuts", [url.toString() for url in self.qFileDialogUi.sidebar.urls()])
            header: QHeaderView | None = self.qFileDialogUi.treeView.header()
            assert header is not None, f"{self.__class__.__name__}.saveSettings: No header found."
            settings.setValue("treeViewHeader", header.saveState())

        historyUrls: list[str] = [QUrl.fromLocalFile(path).toString() for path in q.history()]
        settings.setValue("history", historyUrls)
        settings.setValue("lastVisited", q.directoryUrl().toString())
        viewMode: RealQFileDialog.ViewMode | None = q.viewMode()
        assert viewMode is not None, f"{self.__class__.__name__}.saveSettings: View mode is None."
        settings.setValue("viewMode", int(viewMode if qtpy.QT5 else viewMode.value))  # pyright: ignore[reportArgumentType]
        settings.setValue("qtVersion", qtpy.API_NAME)

    def restoreWidgetState(
        self,
        history: list[str],
        splitterPosition: int,  # noqa: N803
    ) -> bool:
        """Restores the state of various widgets in the file dialog, including splitter position and history.

        Ensures that the dialog's layout and navigation history are preserved across sessions.
        """
        q = self._public
        assert self.qFileDialogUi is not None, f"{self.__class__.__name__}.restoreWidgetState: No UI setup."
        # Match C++: if (splitterPosition >= 0)
        if splitterPosition >= 0:
            # Match C++: QList<int> splitterSizes; splitterSizes.append(splitterPosition);
            # Match C++: splitterSizes.append(qFileDialogUi->splitter->widget(1)->sizeHint().width());
            widget_item: QWidget | None = self.qFileDialogUi.splitter.widget(1)
            assert widget_item is not None, f"{self.__class__.__name__}.restoreWidgetState: No widget item found."
            splitterSizes: list[int] = [splitterPosition, widget_item.sizeHint().width()]
            # Match C++: qFileDialogUi->splitter->setSizes(splitterSizes);
            self.qFileDialogUi.splitter.setSizes(splitterSizes)
        else:
            # Match C++: if (!qFileDialogUi->splitter->restoreState(splitterState)) return false;
            if not self.qFileDialogUi.splitter.restoreState(self.splitterState):
                return False
            # Match C++: QList<int> list = qFileDialogUi->splitter->sizes();
            sizes: list[int] = self.qFileDialogUi.splitter.sizes()
            # Match C++: if (list.size() >= 2 && (list.at(0) == 0 || list.at(1) == 0))
            if len(sizes) >= 2 and (sizes[0] == 0 or sizes[1] == 0):  # noqa: PLR2004
                # Match C++: for (int i = 0; i < list.size(); ++i) list[i] = qFileDialogUi->splitter->widget(i)->sizeHint().width();
                for i in range(len(sizes)):
                    sizes[i] = self.qFileDialogUi.splitter.widget(i).sizeHint().width()
                # Match C++: qFileDialogUi->splitter->setSizes(list);
                self.qFileDialogUi.splitter.setSizes(sizes)

        # Match C++: qFileDialogUi->sidebar->setUrls(sidebarUrls);
        self.qFileDialogUi.sidebar.setUrls(self.sidebarUrls)

        # Match C++: static const int MaxHistorySize = 5;
        MAX_HISTORY_SIZE: int = 5
        # Match C++: if (history.size() > MaxHistorySize) history.erase(history.begin(), history.end() - MaxHistorySize);
        if len(history) > MAX_HISTORY_SIZE:
            history = history[-MAX_HISTORY_SIZE:]
        # Match C++: q->setHistory(history);
        q.setHistory(history)

        # Match C++: QHeaderView *headerView = qFileDialogUi->treeView->header();
        headerView: QHeaderView | None = self.qFileDialogUi.treeView.header()
        assert headerView is not None, f"{self.__class__.__name__}.restoreWidgetState: No header view found."
        # Match C++: if (!headerView->restoreState(headerData)) return false;
        if not headerView.restoreState(self.headerData):
            return False

        # Match C++: QList<QAction*> actions = headerView->actions();
        actions = headerView.actions()
        # Match C++: QAbstractItemModel *abstractModel = model;
        abstractModel: QAbstractItemModel | None = self.model
        # Match C++: #if QT_CONFIG(proxymodel) if (proxyModel) abstractModel = proxyModel; #endif
        if self.proxyModel:
            abstractModel = self.proxyModel
        assert abstractModel is not None, f"{self.__class__.__name__}.restoreWidgetState: No model found."
        # Match C++: const int total = qMin(abstractModel->columnCount(QModelIndex()), int(actions.size() + 1));
        total: int = min(abstractModel.columnCount(QModelIndex()), len(actions) + 1)
        # Match C++: for (int i = 1; i < total; ++i) actions.at(i - 1)->setChecked(!headerView->isSectionHidden(i));
        for i in range(1, total):
            actions[i - 1].setChecked(not headerView.isSectionHidden(i))

        # Match C++: return true;
        return True

    def mapToSource(
        self,
        index: QModelIndex,
    ) -> QModelIndex:
        """Map index from proxy model to source model. Matches C++ QFileDialogPrivate::mapToSource() implementation.

        Only attempt to call the proxy's mapToSource if the provided index actually
        belongs to the proxy model. Passing an index from a different model into
        QSortFilterProxyModel.mapToSource() can trigger Qt warnings and lead to
        undefined behaviour. If the check fails, the original index is returned
        unchanged.
        """
        if not self.proxyModel:
            return index

        # Only map if the index belongs to this proxy model; otherwise return the
        # index unchanged. Guard against unexpected exceptions just in case.
        try:
            if index.model() == self.proxyModel:
                return self.proxyModel.mapToSource(index)
        except Exception:
            pass

        return index

    def mapFromSource(
        self,
        index: QModelIndex,
    ) -> QModelIndex:
        """Map index from source model to proxy model. Matches C++ QFileDialogPrivate::mapFromSource() implementation."""
        # Match C++: return proxyModel ? proxyModel->mapFromSource(index) : index;
        return self.proxyModel.mapFromSource(index) if self.proxyModel else index

    def updateLookInLabel(self) -> None:
        """Update Look In label. Matches C++ QFileDialogPrivate::updateLookInLabel() implementation."""
        # Match C++: if (options->isLabelExplicitlySet(QFileDialogOptions::LookIn))
        if self.options.isLabelExplicitlySet(RealQFileDialog.DialogLabel.LookIn):
            # Match C++: setLabelTextControl(QFileDialog::LookIn, options->labelText(QFileDialogOptions::LookIn));
            self.setLabelTextControl(RealQFileDialog.DialogLabel.LookIn, self.options.labelText(RealQFileDialog.DialogLabel.LookIn))

    def updateFileNameLabel(self) -> None:
        """Update File Name label. Matches C++ QFileDialogPrivate::updateFileNameLabel() implementation."""
        q = self._public
        # Match C++: if (options->isLabelExplicitlySet(QFileDialogOptions::FileName))
        if self.options.isLabelExplicitlySet(RealQFileDialog.DialogLabel.FileName):
            # Match C++: setLabelTextControl(QFileDialog::FileName, options->labelText(QFileDialogOptions::FileName));
            self.setLabelTextControl(RealQFileDialog.DialogLabel.FileName, self.options.labelText(RealQFileDialog.DialogLabel.FileName))
        else:
            # Match C++: switch (q_func()->fileMode())
            # Match C++: case QFileDialog::Directory:
            if q.fileMode() == RealQFileDialog.FileMode.Directory:
                # Match C++: setLabelTextControl(QFileDialog::FileName, QFileDialog::tr("Directory:"));
                self.setLabelTextControl(RealQFileDialog.DialogLabel.FileName, q.tr("Directory:"))
            # Match C++: default:
            else:
                # Match C++: setLabelTextControl(QFileDialog::FileName, QFileDialog::tr("File &name:"));
                self.setLabelTextControl(RealQFileDialog.DialogLabel.FileName, q.tr("File &name:"))

    def updateFileTypeLabel(self) -> None:
        """Update File Type label. Matches C++ QFileDialogPrivate::updateFileTypeLabel() implementation."""
        # Match C++: if (options->isLabelExplicitlySet(QFileDialogOptions::FileType))
        if self.options.isLabelExplicitlySet(RealQFileDialog.DialogLabel.FileType):
            # Match C++: setLabelTextControl(QFileDialog::FileType, options->labelText(QFileDialogOptions::FileType));
            self.setLabelTextControl(RealQFileDialog.DialogLabel.FileType, self.options.labelText(RealQFileDialog.DialogLabel.FileType))

    def updateCancelButtonText(self) -> None:
        """Update Cancel button text. Matches C++ QFileDialogPrivate::updateCancelButtonText() implementation."""
        # Match C++: if (options->isLabelExplicitlySet(QFileDialogOptions::Reject))
        if self.options.isLabelExplicitlySet(RealQFileDialog.DialogLabel.Reject):
            # Match C++: setLabelTextControl(QFileDialog::Reject, options->labelText(QFileDialogOptions::Reject));
            self.setLabelTextControl(RealQFileDialog.DialogLabel.Reject, self.options.labelText(RealQFileDialog.DialogLabel.Reject))

    def rootPath(self) -> str:
        """Return the root path of the file system model. Matches C++ QFileDialogPrivate::rootPath() implementation."""
        # Match C++: return model->rootPath();
        assert self.model is not None, f"{self.__class__.__name__}.rootPath: No model setup."
        return self.model.rootPath()

    def platformFileDialogHelper(self) -> QPlatformFileDialogHelper | None:
        """Provides access to the platform-specific file dialog helper.

        This is important for implementing platform-specific dialog behaviors.
        """
        return self.platformHelper or None

    def setDirectory_sys(
        self,
        directory: QUrl,
    ) -> None:
        """Sets the current directory for the system (native) file dialog.

        Ensures that the native dialog opens in the correct directory.

        If this function is removed, the native dialog might not open in
        the intended directory, causing inconsistency with the Qt-based dialog.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return
        if helper.isSupportedUrl(directory):
            helper.setDirectory(directory.toString())

    def directory_sys(self) -> QUrl:
        """Retrieves the current directory from the system (native) file dialog.

        This is important for maintaining consistency between Qt and native dialogs.

        If this function is removed, the Qt dialog might not be able to
        synchronize its directory with the native dialog, leading to inconsistencies.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return QUrl.fromLocalFile(self.directory)
        return QUrl(helper.directory())

    def selectFile_sys(
        self,
        filename: QUrl,
    ) -> None:
        """Selects a file in the system (native) file dialog.

        Ensures that file selections are properly handled in native dialogs.

        If this function is removed, file selections made programmatically
        might not be reflected in native dialogs, causing inconsistencies.
        """
        # helper = self.platformFileDialogHelper()
        # if helper and helper.isSupportedUrl(filename):
        #    helper.selectFile(filename)
        if self.model is None:
            return
        file_path: str = filename.toLocalFile()
        index: QModelIndex = self.model.index(file_path)
        if not index.isValid():
            return
        self.select(index)

    def selectedFiles_sys(self) -> list[QUrl]:
        """Retrieves the list of selected files from the system (native) file dialog.

        Crucial for obtaining the user's file selection from native dialogs.
        """
        # helper = self.platformFileDialogHelper()
        # return [QUrl(url) for url in helper.selectedFiles()] if helper else []
        curView: QAbstractItemView | None = self.currentView()
        if curView is None:
            return []
        return [QUrl.fromLocalFile(index.data(QFileSystemModel.Roles.FilePathRole)) for index in curView.selectedIndexes()]

    def setFilter_sys(self) -> None:
        """Sets the file filter for the system (native) file dialog.

        Ensures that file filtering is consistent between Qt and native dialogs.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return
        helper.setFilter()

    def selectMimeTypeFilter_sys(
        self,
        filter: str,  # noqa: A002
    ) -> None:
        """Selects a MIME type filter in the system (native) file dialog.

        Allows for consistent MIME type filtering across Qt and native dialogs.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return
        helper.selectMimeTypeFilter(filter)

    def selectedMimeTypeFilter_sys(self) -> str:
        """Retrieves the currently selected MIME type filter from the system (native) file dialog.

        Ensures consistency in MIME type filtering between Qt and native dialogs.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return ""
        return helper.selectedMimeTypeFilter()

    def selectNameFilter_sys(
        self,
        filter: str,  # noqa: A002
    ) -> None:
        """Selects a name filter in the system (native) file dialog.

        Ensures that file name filtering is consistent between Qt and native dialogs.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return
        helper.selectNameFilter(filter)

    def selectedNameFilter_sys(self) -> str:
        """Retrieves the currently selected name filter from the system (native) file dialog.

        Ensures consistency in name filtering between Qt and native dialogs.
        """
        helper = self.platformFileDialogHelper()
        if helper is not None:
            return helper.selectedNameFilter()
        if self.usingWidgets() and self.qFileDialogUi is not None:
            return self.qFileDialogUi.fileTypeCombo.currentText()
        return self.options.initiallySelectedNameFilter()

    def setVisible_sys(
        self,
        *,
        visible: bool,
    ) -> None:
        """Sets the visibility of the system (native) file dialog.

        Ensures that the native dialog is visible or hidden as needed.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return
        helper.setVisible(visible)

    def visible_sys(self) -> bool:
        """Retrieves the visibility of the system (native) file dialog.

        Crucial for determining if the native dialog is currently visible.
        """
        helper = self.platformFileDialogHelper()
        if helper is None:
            return False
        return helper.isVisible()

    def getSelectedFiles(self) -> list[str]:
        """Retrieves the list of files currently selected in the file dialog.

        Crucial for obtaining the user's file selection from the dialog.
        """
        if self.qFileDialogUi is None or self.model is None:
            return []

        selected_indexes: list[QModelIndex] = self.qFileDialogUi.listView.selectedIndexes()
        return [self.model.filePath(index) for index in selected_indexes]

    def itemViewKeyboardEvent(
        self,
        e: QKeyEvent,
    ) -> bool:
        """Processes keyboard events in the item view of the file dialog.

        Matches C++ itemViewKeyboardEvent() implementation.
        For the list and tree view watch keys to goto parent and back in the history.
        Returns True if handled.
        """
        q = self._public
        # Handle Cancel key sequence
        from qtpy.QtGui import QKeySequence

        if e.matches(QKeySequence.StandardKey.Cancel):
            q.reject()
            return True

        # Handle individual keys (matching C++ switch statement with fall-through)
        # Match C++: switch (event->key()) { case Qt::Key_Backspace: ... case Qt::Key_Back: case Qt::Key_Left: ... }
        key = e.key()
        if key == Qt.Key.Key_Backspace:
            self._q_navigateToParent()
            return True
        elif key == Qt.Key.Key_Back:
            # Note: QT_KEYPAD_NAVIGATION check omitted in Python (platform-specific)
            # In C++, Key_Back falls through to Key_Left case
            # Match C++: if (event->key() == Qt::Key_Back || event->modifiers() == Qt::AltModifier)
            if e.modifiers() == Qt.KeyboardModifier.AltModifier:
                # This shouldn't happen for Key_Back, but handle it for consistency
                self._q_navigateBackward()
                return True
            # Fall through to Key_Left handling
        elif key == Qt.Key.Key_Left:
            # Match C++: if (event->key() == Qt::Key_Back || event->modifiers() == Qt::AltModifier)
            if e.modifiers() == Qt.KeyboardModifier.AltModifier:
                self._q_navigateBackward()
                return True
            # If just Left without Alt, don't handle it
            return False
        # For Key_Back without Alt, also navigate backward (fall-through from Key_Back case)
        if key == Qt.Key.Key_Back:
            self._q_navigateBackward()
            return True

        return False

    def accept(self) -> None:
        """Handles the acceptance of the file dialog, including different behaviors for open and save modes.

        Crucial for finalizing the user's file selection or save operation.
        """
        q = self._public
        if q.acceptMode() == q.AcceptMode.AcceptSave:
            q.accept()
            return
        # else:  # AcceptOpen
        selected_files: list[str] = self.getSelectedFiles()
        if selected_files:
            q.accept()
            return

        q.reject()


class QFileDialogComboBox(QComboBox):
    """Custom combo box for file dialog directory navigation.

    Matches C++ QFileDialogComboBox implementation.
    """

    def __init__(
        self,
        parent: RealQFileDialog,
    ):
        # Match C++: QFileDialogComboBox(QWidget *parent = nullptr) : QComboBox(parent), urlModel(nullptr), d_ptr(nullptr) {}
        super().__init__(parent)
        self._private: QFileDialogPrivate | None = None
        self.m_history: list[str] = []
        self.urlModel: QUrlModel | None = None  # Match C++: initialized as nullptr
        # Note: setFileDialogPrivate() will set up the urlModel

    def _d_ptr(self) -> QFileDialogPrivate:
        return typing.cast("PublicQFileDialog", self)._private  # noqa: SLF001

    def showPopup(self) -> None:  # noqa: C901
        """Show the popup menu. Matches C++ QFileDialogComboBox::showPopup() implementation."""
        # Match C++: if (model()->rowCount() > 1) QComboBox::showPopup();
        model_of_self: QAbstractItemModel | None = self.model()
        if model_of_self is not None and model_of_self.rowCount() > 1:
            QComboBox.showPopup(self)

        # Match C++: urlModel->setUrls(QList<QUrl>());
        assert self.urlModel is not None, f"{self.__class__.__name__}.showPopup: urlModel is None"
        self.urlModel.setUrls([])
        urls: list[QUrl] = []
        fs_model: QFileSystemModel | None = self._d_ptr().model
        if fs_model is None:
            return
        # Match C++: QModelIndex idx = d_ptr->model->index(d_ptr->rootPath());
        idx: QModelIndex = fs_model.index(self._d_ptr().rootPath())
        # Match C++: while (idx.isValid()) { ... idx = idx.parent(); }
        while idx.isValid():
            # Match C++: QUrl url = QUrl::fromLocalFile(idx.data(QFileSystemModel::FilePathRole).toString());
            file_path_data = idx.data(QFileSystemModel.Roles.FilePathRole)
            if isinstance(file_path_data, str):
                url: QUrl = QUrl.fromLocalFile(file_path_data)
            else:
                url = QUrl()
            if url.isValid():
                urls.append(url)
            idx = idx.parent()

        # Match C++: // add "my computer" list.append(QUrl("file:"_L1));
        urls.append(QUrl("file:"))
        # Match C++: urlModel->addUrls(list, 0);
        self.urlModel.addUrls(urls, 0)

        # Match C++: idx = model()->index(model()->rowCount() - 1, 0);
        model: QAbstractItemModel | None = self.model()
        if model is not None:
            idx = model.index(model.rowCount() - 1, 0)

        # Match C++: // append history
        history_urls: list[QUrl] = []
        # Match C++: for (int i = 0; i < m_history.size(); ++i)
        for i in range(len(self.m_history)):
            # Match C++: QUrl path = QUrl::fromLocalFile(m_history.at(i));
            path_url: QUrl = QUrl.fromLocalFile(self.m_history[i])
            # Match C++: if (!urls.contains(path)) urls.prepend(path);
            if path_url not in history_urls:
                history_urls.insert(0, path_url)

        # Match C++: if (urls.size() > 0)
        if history_urls:
            if model is not None:
                # Match C++: model()->insertRow(model()->rowCount());
                model.insertRow(model.rowCount())
                # Match C++: idx = model()->index(model()->rowCount()-1, 0);
                idx = model.index(model.rowCount() - 1, 0)
                # Match C++: // ### TODO maybe add a horizontal line before this
                # Match C++: model()->setData(idx, QFileDialog::tr("Recent Places"));
                from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialog as PublicQFileDialog

                model.setData(idx, PublicQFileDialog.tr("Recent Places", "QFileDialog"))
                # Match C++: QStandardItemModel *m = qobject_cast<QStandardItemModel*>(model());
                if isinstance(model, QStandardItemModel):
                    # Match C++: Qt::ItemFlags flags = m->flags(idx); flags &= ~Qt::ItemIsEnabled; m->item(idx.row(), idx.column())->setFlags(flags);
                    item: QStandardItem | None = model.item(idx.row(), idx.column())
                    if item is not None:
                        flags: Qt.ItemFlag = item.flags()
                        flags &= ~Qt.ItemFlag.ItemIsEnabled
                        item.setFlags(flags)
                # Match C++: urlModel->addUrls(urls, -1, false);
                self.urlModel.addUrls(history_urls, -1, move=False)
        # Match C++: setCurrentIndex(0);
        self.setCurrentIndex(0)
        # Match C++: QComboBox::showPopup();
        QComboBox.showPopup(self)

    def setFileDialogPrivate(
        self,
        private: QFileDialogPrivate,
    ) -> None:
        self._private = private
        self.urlModel = QUrlModel(self)
        self.urlModel.showFullPath = True
        assert self._private.model is not None
        assert isinstance(self._private.model, QFileSystemModel)
        self.urlModel.setFileSystemModel(self._private.model)
        self.setModel(self.urlModel)

    def setHistory(
        self,
        paths: list[str],
    ) -> None:
        """Set the browsing history. Matches C++ QFileDialogComboBox::setHistory() implementation."""
        # Match C++: m_history = paths;
        self.m_history[:] = paths
        # Match C++: Only populate the first item, showPopup will populate the rest if needed
        if self._private is None or self.urlModel is None:
            return
        url_list: list[QUrl] = []
        root_path = self._private.rootPath()
        idx: QModelIndex = self._private.model.index(root_path) if self._private.model else QModelIndex()
        # Match C++: On windows the popup display the "C:\", convert to nativeSeparators
        if idx.isValid():
            file_path = idx.data(QFileSystemModel.Roles.FilePathRole)
            if isinstance(file_path, str):
                url = QUrl.fromLocalFile(QDir.toNativeSeparators(file_path))
            else:
                url = QUrl("file:")
        else:
            url = QUrl("file:")
        if url.isValid():
            url_list.append(url)
        self.urlModel.setUrls(url_list)

    def history(self) -> list[str]:
        return self.m_history

    def paintEvent(
        self,
        e: QPaintEvent,
    ) -> None:
        painter: QStylePainter = QStylePainter(self)
        color_role = QPalette.ColorRole.Text if hasattr(QPalette, "ColorRole") else QPalette.Text  # pyright: ignore[reportAttributeAccessIssue]
        painter.setPen(self.palette().color(color_role))
        opt: QStyleOptionComboBox = QStyleOptionComboBox()
        self.initStyleOption(opt)

        style_of_self: QStyle | None = self.style()
        if style_of_self is None:
            return
        edit_rect: QRect = style_of_self.subControlRect(QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxEditField, self)
        size: int = edit_rect.width() - opt.iconSize.width() - 4
        opt.currentText = opt.fontMetrics.elidedText(opt.currentText, Qt.TextElideMode.ElideMiddle, size)

        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def keyPressEvent(
        self,
        e: QKeyEvent,
    ) -> None:
        assert self._private is not None, f"{self.__class__.__name__}.keyPressEvent: No private class setup yet."
        if not self._private.itemViewKeyboardEvent(e):
            super().keyPressEvent(e)
        e.accept()


class QFileDialogLineEdit(QLineEdit):
    def __init__(
        self,
        parent: RealQFileDialog,
    ):
        super().__init__(parent)
        self.hideOnEsc: bool = False
        self._private: QFileDialogPrivate | None = None

    def keyPressEvent(
        self,
        e: QKeyEvent,
    ) -> None:
        """FIXME: this is a hack to avoid propagating key press events
        to the dialog and from there to the "Ok" button.

        Matches C++ QFileDialogLineEdit::keyPressEvent() implementation.
        """
        # Match C++: handle keypad navigation mode (if available)
        # #ifdef QT_KEYPAD_NAVIGATION
        # if (QApplication::navigationMode() == Qt::NavigationModeKeypadDirectional) {
        #     QLineEdit::keyPressEvent(e);
        #     return;
        # }
        # #endif

        # Match C++: #if QT_CONFIG(shortcut) int key = e->key(); #endif
        key = e.key()
        super().keyPressEvent(e)
        # Match C++: #if QT_CONFIG(shortcut) if (!e->matches(QKeySequence::Cancel) && key != Qt::Key_Back) #endif e->accept();
        if not e.matches(QKeySequence.StandardKey.Cancel) and key != Qt.Key.Key_Back:
            e.accept()

    def _d_ptr(self) -> QFileDialogPrivate:
        return typing.cast("PublicQFileDialog", self)._private  # noqa: SLF001

    def setFileDialogPrivate(
        self,
        d_pointer: QFileDialogPrivate,
    ) -> None:
        self._private = d_pointer


class QFileDialogTreeView(QTreeView):
    def __init__(
        self,
        parent: QWidget,
    ):
        super().__init__(parent)
        self._private: QFileDialogPrivate | None = None

    def setFileDialogPrivate(
        self,
        private: QFileDialogPrivate,
    ) -> None:
        self._private = private
        self.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setSortingEnabled(True)
        header_view: QHeaderView | None = self.header()
        if header_view is None:
            return
        header_view.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        header_view.setStretchLastSection(False)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def _d_ptr(self) -> QFileDialogPrivate:
        return typing.cast("PublicQFileDialog", self.parent())._private  # noqa: SLF001

    def keyPressEvent(
        self,
        e: QKeyEvent,
    ) -> None:
        if not self._d_ptr().itemViewKeyboardEvent(e):
            super().keyPressEvent(e)
        e.accept()

    def sizeHint(self) -> QSize:
        height: int = max(10, self.sizeHintForRow(0))
        header_view: QHeaderView | None = self.header()
        if header_view is None:
            return QSize(0, 0)
        size_hint: QSize = header_view.sizeHint()
        return QSize(size_hint.width() * 4, height * 30)


class QFileDialogListView(QListView):
    def __init__(
        self,
        parent: QWidget,
    ):
        super().__init__(parent)

    def setFileDialogPrivate(
        self,
        d_pointer: QFileDialogPrivate,
    ) -> None:
        """Set the file dialog private pointer. Matches C++ QFileDialogListView::setFileDialogPrivate() implementation."""
        # Match C++: d_ptr = d_pointer;
        self._private: QFileDialogPrivate = d_pointer
        # Match C++: setSelectionBehavior(QAbstractItemView::SelectRows);
        self.setSelectionBehavior(QListView.SelectionBehavior.SelectRows)
        # Match C++: setWrapping(true);
        self.setWrapping(True)
        # Match C++: setResizeMode(QListView::Adjust);
        self.setResizeMode(QListView.ResizeMode.Adjust)
        # Match C++: setEditTriggers(QAbstractItemView::EditKeyPressed);
        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        # Match C++: setContextMenuPolicy(Qt::CustomContextMenu);
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Match C++: #if QT_CONFIG(draganddrop) setDragDropMode(QAbstractItemView::InternalMove); #endif
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def _d_ptr(self) -> QFileDialogPrivate:
        return typing.cast("PublicQFileDialog", self)._private  # noqa: SLF001

    def sizeHint(self) -> QSize:
        height: int = max(10, self.sizeHintForRow(0))
        return QSize(super().sizeHint().width() * 2, height * 30)

    def keyPressEvent(
        self,
        e: QKeyEvent,
    ) -> None:
        if not self._d_ptr().itemViewKeyboardEvent(e):
            super().keyPressEvent(e)
        e.accept()


if __name__ == "__main__":
    from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialog as CustomQFileDialog

    app = QApplication(sys.argv)
    dialog = CustomQFileDialog()
    dialog.show()
    sys.exit(app.exec())
