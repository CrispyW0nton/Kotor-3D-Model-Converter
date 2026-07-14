"""Top toolbar for the Map Studio Level Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.libtheme.style_tokens import NATIVE_FALLBACK_COLORS


class ModuleEditorToolbar(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    viewModeChanged = QtCore.Signal(str)
    selectionModeChanged = QtCore.Signal(str)
    skyboxVisibilityChanged = QtCore.Signal(bool)

    ACTIONS = (
        ("new", "New"),
        ("open", "Open"),
        ("save", "Save"),
        ("import_module", "Import Module"),
        ("add_room", "Add Room"),
        ("add_module", "Add Module"),
        ("validate", "Validate"),
        ("simulate", "Play"),
        ("build", "Build"),
        ("generate_module_files", "Generate Module Files"),
        ("export_fbx", "Export FBX"),
    )
    EDIT_MODES = (
        ("Object", "Select, move, duplicate, and organize rooms, placements, lights, and module objects."),
        ("Edit (GModeler)", "GModeler edit mode: hover any face, edge, or vertex and use RMB tools - no component-mode switching needed."),
        ("Texture Paint", "Paint a unique project TGA on the nearest visible face through diffuse UV0."),
        ("Vertex", "Edit room and walkmesh vertices with snap, weld, flatten, mirror, and cleanup tools."),
        ("Edge", "Edit seams, door or corridor borders, bridge edges, bevels, and rectangular cuts."),
        ("Face", "Edit room faces, material intent, WOK surface intent, triangulation, and cleanup."),
        ("Walkmesh", "Inspect and paint walkable, non-walkable, door, water, and transition faces."),
        ("Placement", "Place and transform KOTOR creatures, placeables, doors, triggers, cameras, and waypoints."),
        ("Terrain", "Sculpt terrain heightfields, ramps, plateaus, erosion, smoothing, and walkability."),
        ("Export", "Validate, stage, install, hand off, warp-test, and record game proof."),
    )
    MAP_STUDIO_TOOL_BELT_ACTIONS = (
        ("plane", "Plane", "Add a KMAP-safe walkable plane primitive to the active authored room."),
        ("cube", "Cube", "Add a KMAP-safe cube/blockout primitive to the active authored room."),
        ("wall", "Wall", "Add a wall/slab primitive aligned to room and doorway seams."),
        ("cylinder", "Cylinder", "Add a column or pedestal cylinder primitive."),
        ("ramp", "Ramp", "Add a sloped ramp primitive with walkmesh intent."),
        ("stairs", "Stairs", "Add a stair primitive with a ramp-style WOK proxy."),
        ("arch", "Arch", "Add an arch primitive for visual portal silhouettes."),
        ("universal_transform", "Ctrl+T", "Activate the Universal Manipulator with selected width, depth, and height dimensions."),
        ("extrude", "Extrude", "Focus edge/face extrusion for room and corridor growth."),
        ("bevel", "Bevel", "Focus bevel/inset tools for blockout cleanup."),
        ("bridge", "Bridge", "Focus edge bridge tools for corridors and room joins."),
        ("vertex_snap", "Snap Vtx", "Focus vertex snapping. Hold V previews snap targets."),
        ("grid_snap", "Grid Snap", "Move selected floor-plan vertices to the authored Map Studio grid without welding topology."),
        ("transform_snap_level", "Level Snap", "Focus transform snapping. Hold J aligns selected vertices or edges to one level."),
        ("weld", "Weld", "Focus topology welding for floor-plan vertices."),
        ("terrain_patch", "Terrain", "Create or focus a terrain patch for sculpting."),
    )

    # T3001 minimal layout: these duplicate File/Tools menu entries stay
    # constructed for dispatch and back-compat but are hidden by default.
    HIDDEN_DUPLICATE_ACTIONS = frozenset({"import_module", "add_room", "add_module", "generate_module_files", "export_fbx"})

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorToolbar")
        self._ghost_theme = None
        self._simulation_active = False
        self._simulation_icon_extent = 18
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.buttons: dict[str, QtWidgets.QToolButton] = {}
        for key, label in self.ACTIONS:
            button = QtWidgets.QToolButton()
            button.setObjectName(f"mapStudioToolbarActionButton_{key}")
            button.setText(label)
            button.setProperty("_gr_full_text", label)
            button.setToolTip(label)
            if key == "simulate":
                button.setCheckable(True)
                button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.clicked.connect(lambda _checked=False, name=key: self.actionRequested.emit(name))
            self.buttons[key] = button
            row.addWidget(button)
            button.setVisible(key not in self.HIDDEN_DUPLICATE_ACTIONS)
        row.addSpacing(8)
        self.tool_belt_buttons: dict[str, QtWidgets.QToolButton] = {}
        self.modeling_label = QtWidgets.QLabel("Modeling")
        self.modeling_label.setObjectName("mapStudioMainToolbarModelingLabel")
        row.addWidget(self.modeling_label)
        # T3001 minimal layout: the Modeling strip duplicates the tool belt
        # and radial marking menu; keep constructed, hide by default.
        self.modeling_label.setVisible(False)
        for key, label, tooltip in self.MAP_STUDIO_TOOL_BELT_ACTIONS:
            button = QtWidgets.QToolButton()
            button.setObjectName(f"mapStudioMainToolBeltButton_{key}")
            button.setText(label)
            button.setProperty("_gr_full_text", label)
            button.setToolTip(f"{tooltip}\nKOTOR: routes through Map Studio KMAP tooling, not the main KMAX scene.")
            button.clicked.connect(lambda _checked=False, name=key: self.actionRequested.emit(f"tool_belt:{name}"))
            self.tool_belt_buttons[key] = button
            row.addWidget(button)
            button.setVisible(False)
        row.addSpacing(8)
        self.view_mode = QtWidgets.QComboBox()
        self.view_mode.setObjectName("mapStudioToolbarViewModeComboBox")
        self.view_mode.addItems(["Perspective", "Top", "Front", "Side", "Wireframe", "Albedo", "Textured", "Lit", "Lightmap Preview", "Walkmesh Preview"])
        self.view_mode.currentTextChanged.connect(self.viewModeChanged.emit)
        row.addWidget(self.view_mode)
        self.show_skybox = QtWidgets.QCheckBox("Skybox")
        self.show_skybox.setObjectName("mapStudioToolbarShowSkyboxCheckBox")
        self.show_skybox.setChecked(True)
        self.show_skybox.setToolTip(
            "Render loaded or authored skybox/backdrop surfaces with their real game textures. "
            "Backdrop geometry remains depth-tested but cannot be selected by GModeler."
        )
        self.show_skybox.toggled.connect(self.skyboxVisibilityChanged.emit)
        row.addWidget(self.show_skybox)
        self.selection_mode = QtWidgets.QComboBox()
        self.selection_mode.setObjectName("mapStudioToolbarEditModeComboBox")
        for label, tooltip in self.EDIT_MODES:
            self.selection_mode.addItem(label)
            index = self.selection_mode.count() - 1
            self.selection_mode.setItemData(index, tooltip, QtCore.Qt.ItemDataRole.ToolTipRole)
        self.selection_mode.currentTextChanged.connect(self.selectionModeChanged.emit)
        row.addWidget(self.selection_mode)
        row.addStretch(1)
        self._refresh_simulation_button()

    def _simulation_color(self, active: bool) -> QtGui.QColor:
        token = "error" if active else "success"
        fallback = NATIVE_FALLBACK_COLORS[token]
        theme = self._ghost_theme
        value = theme.color(token, fallback) if theme is not None else fallback
        color = QtGui.QColor(value)
        return color if color.isValid() else QtGui.QColor(fallback)

    @staticmethod
    def _simulation_icon(active: bool, color: QtGui.QColor, extent: int) -> QtGui.QIcon:
        """Draw a semantic Play triangle or Stop square at the active toolbar density."""

        size = max(14, int(extent or 18))
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(color))
        margin = max(2.5, size * 0.19)
        if active:
            painter.drawRoundedRect(
                QtCore.QRectF(margin, margin, size - (2.0 * margin), size - (2.0 * margin)),
                max(0.8, size * 0.05),
                max(0.8, size * 0.05),
            )
        else:
            painter.drawPolygon(
                QtGui.QPolygonF(
                    (
                        QtCore.QPointF(size * 0.31, margin),
                        QtCore.QPointF(size * 0.31, size - margin),
                        QtCore.QPointF(size - margin, size * 0.50),
                    )
                )
            )
        painter.end()
        return QtGui.QIcon(pixmap)

    def _refresh_simulation_button(self) -> None:
        button = self.buttons.get("simulate")
        if button is None:
            return
        active = bool(self._simulation_active)
        full_name = "Stop Play in Editor" if active else "Play in Editor"
        tooltip = (
            "Stop Play in Editor (Alt+P) and restore the authoring camera and tools."
            if active
            else (
                "Play in Editor (Alt+P) using the current walkmesh, player camera, creatures, and ambient sound. "
                "This is a GhostStudio simulation, not KOTOR engine proof."
            )
        )
        button.setText("Stop" if active else "Play")
        button.setIcon(self._simulation_icon(active, self._simulation_color(active), self._simulation_icon_extent))
        button.setProperty("_gr_full_text", full_name)
        button.setProperty("mapStudioPIEState", "playing" if active else "editing")
        button.setAccessibleName(full_name)
        button.setAccessibleDescription(tooltip)
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.update()

    def set_simulation_active(self, active: bool) -> None:
        """Present the persistent Play/Stop state without emitting an action."""

        button = self.buttons.get("simulate")
        if button is None:
            return
        blocked = button.blockSignals(True)
        try:
            self._simulation_active = bool(active)
            button.setChecked(self._simulation_active)
            self._refresh_simulation_button()
        finally:
            button.blockSignals(blocked)

    def apply_ghost_theme(self, theme) -> None:
        self._ghost_theme = theme
        self._refresh_simulation_button()

    def apply_native_theme(self) -> None:
        self._ghost_theme = None
        self._refresh_simulation_button()

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("moduleEditor")
        self.setMinimumHeight(toolbar.height)
        for button in (*self.buttons.values(), *self.tool_belt_buttons.values()):
            button.setMinimumHeight(max(20, toolbar.height - 8))
            button.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
        self._simulation_icon_extent = int(toolbar.icon_size)
        simulation_button = self.buttons.get("simulate")
        if simulation_button is not None:
            style = {
                "iconOnly": QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly,
                "textOnly": QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly,
                "textUnderIcon": QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon,
            }.get(toolbar.button_mode, QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            simulation_button.setToolButtonStyle(style)
        self._refresh_simulation_button()
