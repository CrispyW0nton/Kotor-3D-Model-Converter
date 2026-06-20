"""Top toolbar for the Map Studio Level Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ModuleEditorToolbar(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    viewModeChanged = QtCore.Signal(str)
    selectionModeChanged = QtCore.Signal(str)

    ACTIONS = (
        ("new", "New"),
        ("open", "Open"),
        ("save", "Save"),
        ("import_module", "Import Module"),
        ("add_room", "Add Room"),
        ("add_module", "Add Module"),
        ("validate", "Validate"),
        ("build", "Build"),
        ("export_fbx", "Export FBX"),
    )
    EDIT_MODES = (
        ("Object", "Select, move, duplicate, and organize rooms, placements, lights, and module objects."),
        ("Vertex", "Edit room and walkmesh vertices with snap, weld, flatten, mirror, and cleanup tools."),
        ("Edge", "Edit seams, door or corridor borders, bridge edges, bevels, and rectangular cuts."),
        ("Face", "Edit room faces, material intent, WOK surface intent, triangulation, and cleanup."),
        ("Walkmesh", "Inspect and paint walkable, non-walkable, door, water, and transition faces."),
        ("Placement", "Place and transform KOTOR creatures, placeables, doors, triggers, cameras, and waypoints."),
        ("Terrain", "Sculpt terrain heightfields, ramps, plateaus, erosion, smoothing, and walkability."),
        ("Export", "Validate, stage, install, hand off, warp-test, and record game proof."),
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorToolbar")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.buttons: dict[str, QtWidgets.QToolButton] = {}
        for key, label in self.ACTIONS:
            button = QtWidgets.QToolButton()
            button.setText(label)
            button.setProperty("_gr_full_text", label)
            button.setToolTip(label)
            button.clicked.connect(lambda _checked=False, name=key: self.actionRequested.emit(name))
            self.buttons[key] = button
            row.addWidget(button)
        row.addSpacing(8)
        self.view_mode = QtWidgets.QComboBox()
        self.view_mode.setObjectName("mapStudioToolbarViewModeComboBox")
        self.view_mode.addItems(["Perspective", "Top", "Front", "Side", "Wireframe", "Textured", "Lit", "Lightmap Preview", "Walkmesh Preview"])
        self.view_mode.currentTextChanged.connect(self.viewModeChanged.emit)
        row.addWidget(self.view_mode)
        self.selection_mode = QtWidgets.QComboBox()
        self.selection_mode.setObjectName("mapStudioToolbarEditModeComboBox")
        for label, tooltip in self.EDIT_MODES:
            self.selection_mode.addItem(label)
            index = self.selection_mode.count() - 1
            self.selection_mode.setItemData(index, tooltip, QtCore.Qt.ItemDataRole.ToolTipRole)
        self.selection_mode.currentTextChanged.connect(self.selectionModeChanged.emit)
        row.addWidget(self.selection_mode)
        row.addStretch(1)

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("moduleEditor")
        self.setMinimumHeight(toolbar.height)
        for button in self.buttons.values():
            button.setMinimumHeight(max(20, toolbar.height - 8))
            button.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
