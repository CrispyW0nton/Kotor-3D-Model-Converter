"""DLG editor dialog widgets: reference chooser, list windows, and link list items."""

from __future__ import annotations

import weakref

from typing import TYPE_CHECKING, ClassVar

import qtpy

from qtpy.QtCore import (
    Qt,
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtGui import QTextDocument
from qtpy.QtWidgets import QDialog, QListWidgetItem, QStyle, QStyleOptionViewItem

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.resource.generics.dlg import DLGLink
from toolset.gui.editors.dlg.list_widget_base import DLGListWidget, DLGListWidgetItem
from utility.gui.qt.widgets.itemviews.html_delegate import HTMLDelegate

if TYPE_CHECKING:
    import weakref

    from qtpy.QtCore import QObject
    from qtpy.QtWidgets import QListWidget, QPushButton

    from pykotor.resource.generics.dlg import DLGLink
    from toolset.gui.editors.dlg.editor import DLGEditor
    from toolset.gui.editors.dlg.list_widget_base import QAbstractItemDelegate


class ReferenceChooserDialog(QDialog):
    item_chosen: ClassVar[Signal] = Signal()  # pyright: ignore[reportPrivateImportUsage]

    def __init__(
        self,
        references: list[weakref.ref[DLGLink]],
        parent: DLGEditor,
        item_text: str,
    ):
        from toolset.gui.editors.dlg.editor import DLGEditor

        assert isinstance(parent, DLGEditor)
        super().__init__(parent)
        qt_constructor: type[Qt.WindowFlags | Qt.WindowType] = Qt.WindowFlags if qtpy.QT5 else Qt.WindowType  # pyright: ignore[reportAttributeAccessIssue]
        self.setWindowFlags(Qt.WindowType.Dialog | qt_constructor(Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.WindowContextHelpButtonHint))  # pyright: ignore[reportAttributeAccessIssue]
        self.setWindowTitle("Node References")

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.reference_chooser import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.editor: DLGEditor = parent

        # Replace QListWidget with custom DLGListWidget

        list_widget_placeholder: QListWidget | None = self.ui.listWidget
        if list_widget_placeholder is not None:
            # Get the parent layout and index
            parent_layout = self.ui.verticalLayout
            index = parent_layout.indexOf(list_widget_placeholder)
            # Remove the placeholder
            list_widget_placeholder.setParent(None)
            # Create and add the custom widget
            self.list_widget: DLGListWidget = DLGListWidget(parent)
            self.list_widget.use_hover_text = True
            self.list_widget.setItemDelegate(HTMLDelegate(self.list_widget))
            parent_layout.insertWidget(index, self.list_widget)
        else:
            # Fallback: create the widget directly
            self.list_widget = DLGListWidget(parent)
            self.list_widget.use_hover_text = True
            self.list_widget.setItemDelegate(HTMLDelegate(self.list_widget))
            self.ui.verticalLayout.insertWidget(0, self.list_widget)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter: NoScrollEventFilter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        # Set button icons
        self.back_button: QPushButton = self.ui.backButton
        self.forward_button: QPushButton = self.ui.forwardButton
        self.back_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))  # pyright: ignore[reportOptionalMemberAccess]
        self.forward_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))  # pyright: ignore[reportOptionalMemberAccess]

        max_width = 0
        for linkref in references:
            link: DLGLink | None = linkref()
            if link is None:
                continue
            item = DLGListWidgetItem(link=link, ref=linkref)
            # Build the HTML display
            self.list_widget.update_item(item)
            self.list_widget.addItem(item)
            max_width = max(max_width, self.calculate_html_width(item.data(Qt.ItemDataRole.DisplayRole)))

        # Connect buttons
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())
        self.back_button.clicked.connect(lambda: self.go_back())
        self.forward_button.clicked.connect(lambda: self.go_forward())

        self.setStyleSheet("""
        .link-container:hover .link-hover-text {
            display: block;
        }
        .link-container:hover .link-text {
            display: none;
        }
        .link-hover-text {
            display: none;
        }
        """)
        self.adjustSize()
        self.setMinimumSize(self.height(), self.width() + 50)
        self.forward_button.setEnabled(False)
        self.update_item_sizes()
        self.update_references(references, item_text)

    def parent(self) -> DLGEditor:
        from toolset.gui.editors.dlg.editor import DLGEditor

        parent: QObject | None = super().parent()
        assert isinstance(parent, DLGEditor)
        return parent

    def update_item_sizes(self):
        item_delegate: HTMLDelegate | QAbstractItemDelegate | None = self.list_widget.itemDelegate()
        if item_delegate is None:
            return
        for i in range(self.list_widget.count()):
            item: QListWidgetItem | None = self.list_widget.item(i)
            if not isinstance(item, QListWidgetItem):
                RobustLogger().warning(f"ReferenceChooser.update_item_sizes({i}): Item was None unexpectedly.")
                continue
            if qtpy.QT5:
                options: QStyleOptionViewItem = self.list_widget.viewOptions()  # pyright: ignore[reportAttributeAccessIssue]
            else:
                options: QStyleOptionViewItem = QStyleOptionViewItem()
                self.list_widget.initViewItemOption(options)
            item.setSizeHint(item_delegate.sizeHint(options, self.list_widget.indexFromItem(item)))

    def calculate_html_width(
        self,
        html: str,
    ) -> int:
        doc: QTextDocument = QTextDocument()
        doc.setHtml(html)
        return int(doc.idealWidth())

    def get_stylesheet(self) -> str:
        from qtpy.QtGui import QPalette
        from qtpy.QtWidgets import QApplication

        # Get palette color for dialog background
        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            palette = app.palette()
            window_color = palette.color(QPalette.ColorRole.Window)
            bg_color = window_color.name()
        else:
            # Fallback: use default palette
            default_palette = QPalette()
            window_color = default_palette.color(QPalette.ColorRole.Window)
            bg_color = window_color.name()

        font_size = 12
        return f"""
        QListWidget {{
            font-size: {font_size}pt;
            margin: 10px;
        }}
        QPushButton {{
            font-size: {font_size}pt;
            padding: 5px 10px;
        }}
        QDialog {{
            background-color: {bg_color};
        }}
        .link-container:hover .link-hover-text {{
            display: block;
        }}
        .link-container:hover .link-text {{
            display: none;
        }}
        .link-hover-text {{
            display: none;
        }}
        """

    def accept(self):
        sel_item: QListWidgetItem | None = self.list_widget.currentItem()
        if isinstance(sel_item, DLGListWidgetItem):
            self.item_chosen.emit(sel_item)
        super().accept()

    def go_back(self):
        self.parent().navigate_back()
        self.update_button_states()

    def go_forward(self):
        self.parent().navigate_forward()
        self.update_button_states()

    def update_references(
        self,
        referenceItems: list[weakref.ref[DLGLink]],
        item_text: str,
    ):
        # Note: item_text parameter is kept for API compatibility but not currently displayed
        self.list_widget.clear()
        node_path: str = ""
        for linkref in referenceItems:
            link: DLGLink | None = linkref()
            if link is None:
                continue
            listItem = DLGListWidgetItem(link=link, ref=linkref)
            self.list_widget.update_item(listItem)
            self.list_widget.addItem(listItem)
        self.update_item_sizes()
        self.adjustSize()
        self.setWindowTitle(f"Node References: {node_path}")
        self.update_button_states()

    def update_button_states(self):
        parent: DLGEditor = self.parent()
        self.back_button.setEnabled(parent.current_reference_index > 0)
        self.forward_button.setEnabled(parent.current_reference_index < len(parent.reference_history) - 1)
