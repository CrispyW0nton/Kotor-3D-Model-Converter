"""DLG view switcher: toggle between tree view and node graph view."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import Signal  # pyright: ignore[reportPrivateImportUsage]
from qtpy.QtWidgets import QWidget

from toolset.gui.editors.dlg.model import DLGStandardItem
from toolset.gui.editors.dlg.tree_view import DLGTreeView

if TYPE_CHECKING:
    from qtpy.QtGui import QStandardItem
    from typing_extensions import Literal  # pyright: ignore[reportMissingModuleSource]

    from pykotor.resource.generics.dlg import DLGLink
    from toolset.gui.editors.dlg.model import DLGStandardItemModel
    from toolset.gui.editors.dlg.node_editor import DialogueNodeEditor


class DLGViewSwitcher(QWidget):
    """Widget that allows switching between tree view and node graph view."""

    # Signal emitted when view changes
    sig_view_changed: ClassVar[Signal] = Signal(str)  # Emits 'tree' or 'graph'

    def __init__(
        self,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        # Load UI from .ui file
        from toolset.uic.qtpy.editors.view_switcher import Ui_Widget

        self.ui: Ui_Widget = Ui_Widget()
        self.ui.setupUi(self)

        # Connect button signals
        self.ui.treeButton.clicked.connect(lambda: self.switch_view("tree"))
        self.ui.graphButton.clicked.connect(lambda: self.switch_view("graph"))

        # Create views
        self.tree_view: DLGTreeView = DLGTreeView()
        self.graph_view: DialogueNodeEditor | None = None

        # Add views to stack
        self.ui.stack.addWidget(self.tree_view)
        self.ui.stack.addWidget(self.graph_view)

        # Set initial view
        self.current_view: Literal["tree", "graph"] = "tree"
        self.ui.stack.setCurrentWidget(self.tree_view)

        # Track if graph has been built
        self.graph_built: bool = False

    def switch_view(
        self,
        view: Literal["tree", "graph"],
    ):
        """Switch between tree and graph views."""
        if view == self.current_view:
            return

        if view == "tree":
            self.ui.treeButton.setChecked(True)
            self.ui.graphButton.setChecked(False)
            self.ui.stack.setCurrentWidget(self.tree_view)
        else:
            self.ui.treeButton.setChecked(False)
            self.ui.graphButton.setChecked(True)
            self.ui.stack.setCurrentWidget(self.graph_view)

            # Build graph if needed
            if not self.graph_built:
                self.update_graph_from_tree()

        self.current_view = view
        self.sig_view_changed.emit(view)

    def update_graph_from_tree(self):
        """Update the graph view based on the current tree view state."""
        model: DLGStandardItemModel | None = self.tree_view.model()
        if not model:
            return

        # Get root links
        root_links: list[DLGLink] = []
        for row in range(model.rowCount()):
            item: DLGStandardItem | QStandardItem = model.item(row, 0)
            if item and isinstance(item, DLGStandardItem) and item.link:
                root_links.append(item.link)

        # Build graph from links
        if self.graph_view is None:
            return
        self.graph_view.build_from_dlg(root_links)
        self.graph_built = True

    def get_current_view(self) -> str:
        """Get the currently active view type."""
        return self.current_view

    def get_tree_view(self) -> DLGTreeView:
        """Get the tree view widget."""
        return self.tree_view

    def get_graph_view(self) -> DialogueNodeEditor | None:
        """Get the graph view widget."""
        return self.graph_view
