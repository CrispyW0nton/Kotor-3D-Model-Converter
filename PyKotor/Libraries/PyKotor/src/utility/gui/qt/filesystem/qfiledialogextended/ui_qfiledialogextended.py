from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtWidgets import (
        QLayout,
    )
    from typing_extensions import Self

    from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import QFileDialogExtended


class Ui_QFileDialogExtended(QFileDialog):  # noqa: N801
    def setupUi(self, dialog: QFileDialogExtended) -> Self:
        # Main layout
        gridlayout: QLayout | None = dialog.layout()
        assert isinstance(gridlayout, QGridLayout)
        self.gridlayout: QGridLayout = gridlayout  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Look In label and combo
        look_in_label: QLabel | None = dialog.findChild(QLabel, "lookInLabel")
        assert isinstance(look_in_label, QLabel)
        self.lookInLabel: QLabel = look_in_label  # pylint: disable=attribute-defined-outside-init,invalid-name

        look_in_combo: QComboBox | None = dialog.findChild(QComboBox, "lookInCombo")
        assert isinstance(look_in_combo, QComboBox)
        self.lookInCombo: QComboBox = look_in_combo  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Toolbar buttons
        back_button: QToolButton | None = dialog.findChild(QToolButton, "backButton")
        assert isinstance(back_button, QToolButton)
        self.backButton: QToolButton = back_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        forward_button: QToolButton | None = dialog.findChild(QToolButton, "forwardButton")
        assert isinstance(forward_button, QToolButton)
        self.forwardButton: QToolButton = forward_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        to_parent_button: QToolButton | None = dialog.findChild(QToolButton, "toParentButton")
        assert isinstance(to_parent_button, QToolButton)
        self.toParentButton: QToolButton = to_parent_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        new_folder_button: QToolButton | None = dialog.findChild(QToolButton, "newFolderButton")
        assert isinstance(new_folder_button, QToolButton)
        self.newFolderButton: QToolButton = new_folder_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        list_mode_button: QToolButton | None = dialog.findChild(QToolButton, "listModeButton")
        assert isinstance(list_mode_button, QToolButton)
        self.listModeButton: QToolButton = list_mode_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        detail_mode_button: QToolButton | None = dialog.findChild(QToolButton, "detailModeButton")
        assert isinstance(detail_mode_button, QToolButton)
        self.detailModeButton: QToolButton = detail_mode_button  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Splitter
        splitter: QSplitter | None = dialog.findChild(QSplitter, "splitter")
        assert isinstance(splitter, QSplitter)
        self.splitter: QSplitter = splitter  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Sidebar
        sidebar: QFrame | None = dialog.findChild(QFrame, "sidebar")  # QFileDialogSidebar
        assert isinstance(sidebar, QFrame)
        self.sidebar: QFrame = sidebar  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Main frame
        frame: QFrame | None = dialog.findChild(QFrame, "frame")
        assert isinstance(frame, QFrame)
        self.frame: QFrame = frame  # pylint: disable=attribute-defined-outside-init,invalid-name

        # Stacked widget for list and tree views
        stacked_widget: QStackedWidget | None = dialog.findChild(QStackedWidget, "stackedWidget")
        assert isinstance(stacked_widget, QStackedWidget)
        self.stackedWidget: QStackedWidget = stacked_widget  # pylint: disable=attribute-defined-outside-init,invalid-name
        assert self.stackedWidget.count() == 2, "StackedWidget should contain 2 pages"  # noqa: PLR2004

        # List view page
        page: QWidget | None = self.stackedWidget.widget(0)
        assert isinstance(page, QWidget)
        self.page: QWidget = page

        list_view: QListView | None = dialog.findChild(QListView, "listView")  # QFileDialogListView
        assert isinstance(list_view, QListView)
        self.listView: QListView = list_view

        # Tree view page
        page_2: QWidget | None = self.stackedWidget.widget(1)
        assert isinstance(page_2, QWidget)
        self.page_2: QWidget = page_2

        tree_view: QTreeView | None = dialog.findChild(QTreeView, "treeView")  # QFileDialogTreeView
        assert isinstance(tree_view, QTreeView)
        self.treeView: QTreeView = tree_view

        # File name label and edit
        file_name_label: QLabel | None = dialog.findChild(QLabel, "fileNameLabel")
        assert isinstance(file_name_label, QLabel)
        self.fileNameLabel: QLabel = file_name_label

        file_name_edit: QLineEdit | None = dialog.findChild(QLineEdit, "fileNameEdit")  # QFileDialogLineEdit
        assert isinstance(file_name_edit, QLineEdit)
        self.fileNameEdit: QLineEdit = file_name_edit

        # Button box
        button_box: QDialogButtonBox | None = dialog.findChild(QDialogButtonBox, "buttonBox")
        assert isinstance(button_box, QDialogButtonBox)
        self.buttonBox: QDialogButtonBox = button_box

        # File type label and combo
        file_type_label: QLabel | None = dialog.findChild(QLabel, "fileTypeLabel")
        assert isinstance(file_type_label, QLabel)
        self.fileTypeLabel: QLabel = file_type_label

        file_type_combo: QComboBox | None = dialog.findChild(QComboBox, "fileTypeCombo")
        assert isinstance(file_type_combo, QComboBox)
        self.fileTypeCombo: QComboBox = file_type_combo

        # Define layouts based on found widgets
        vboxlayout: QLayout | None = self.frame.layout()
        assert isinstance(vboxlayout, QVBoxLayout)
        self.vboxlayout: QVBoxLayout = vboxlayout

        vboxlayout1: QLayout | None = self.page.layout()
        assert isinstance(vboxlayout1, QVBoxLayout)
        self.vboxlayout1: QVBoxLayout = vboxlayout1

        vboxlayout2: QLayout | None = self.page_2.layout()
        assert isinstance(vboxlayout2, QVBoxLayout)
        self.vboxlayout2: QVBoxLayout = vboxlayout2

        hboxlayout: QLayout | None = self.gridlayout.itemAtPosition(0, 1).layout()  # pyright: ignore[reportOptionalMemberAccess]
        assert isinstance(hboxlayout, QHBoxLayout)
        self.hboxlayout: QHBoxLayout = hboxlayout

        # Assert correct widget containment
        item = self.gridlayout.itemAtPosition(0, 0)
        assert item is not None
        assert item.widget() == self.lookInLabel

        item = self.gridlayout.itemAtPosition(0, 1)
        assert item is not None
        assert item.layout() == self.hboxlayout

        item = self.gridlayout.itemAtPosition(1, 0)
        assert item is not None
        assert item.widget() == self.splitter

        item = self.gridlayout.itemAtPosition(2, 0)
        assert item is not None
        assert item.widget() == self.fileNameLabel

        item = self.gridlayout.itemAtPosition(2, 1)
        assert item is not None
        assert item.widget() == self.fileNameEdit

        item = self.gridlayout.itemAtPosition(2, 2)
        assert item is not None
        assert item.widget() == self.buttonBox

        item = self.gridlayout.itemAtPosition(3, 0)
        assert item is not None
        assert item.widget() == self.fileTypeLabel

        item = self.gridlayout.itemAtPosition(3, 1)
        assert item is not None
        assert item.widget() == self.fileTypeCombo

        item = self.hboxlayout.itemAt(0)
        assert item is not None
        assert item.widget() == self.lookInCombo
        item = self.hboxlayout.itemAt(1)
        assert item is not None
        assert item.widget() == self.backButton
        item = self.hboxlayout.itemAt(2)
        assert item is not None
        assert item.widget() == self.forwardButton
        item = self.hboxlayout.itemAt(3)
        assert item is not None
        assert item.widget() == self.toParentButton
        item = self.hboxlayout.itemAt(4)
        assert item is not None
        assert item.widget() == self.newFolderButton
        item = self.hboxlayout.itemAt(5)
        assert item is not None
        assert item.widget() == self.listModeButton
        item = self.hboxlayout.itemAt(6)
        assert item is not None
        assert item.widget() == self.detailModeButton

        widget = self.splitter.widget(0)
        assert widget is not None
        assert widget == self.sidebar
        widget = self.splitter.widget(1)
        assert widget is not None
        assert widget == self.frame

        item = self.vboxlayout.itemAt(0)
        assert item is not None
        assert item.widget() == self.stackedWidget

        widget = self.stackedWidget.widget(0)
        assert widget is not None
        assert widget == self.page

        widget = self.stackedWidget.widget(1)
        assert widget is not None
        assert widget == self.page_2

        item = self.vboxlayout1.itemAt(0)
        assert item is not None
        assert item.widget() == self.listView
        item = self.vboxlayout2.itemAt(0)
        assert item is not None
        assert item.widget() == self.treeView

        layout_page = self.page.layout()
        assert layout_page is not None
        assert layout_page == self.vboxlayout1
        layout_page_2 = self.page_2.layout()
        assert layout_page_2 is not None
        assert layout_page_2 == self.vboxlayout2

        return self
