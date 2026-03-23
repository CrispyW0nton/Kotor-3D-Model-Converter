"""PTH (path) editor: waypoints and path graph with 2D camera for module designer."""

from __future__ import annotations

from contextlib import suppress
from copy import copy
from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QActionGroup,  # pyright: ignore[reportPrivateImportUsage]  # noqa: F401
    QApplication,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.generics.pth import PTH, PTHEdge, bytes_pth, read_pth
from pykotor.resource.type import ResourceType
from toolset.data.misc import ControlItem
from toolset.gui.common.interaction.camera import calculate_zoom_strength
from toolset.gui.common.walkmesh_materials import get_walkmesh_material_colors
from toolset.gui.editor import Editor
from toolset.gui.widgets.installation_toolbar import FolderPathSpec
from toolset.gui.widgets.settings.editor_settings.git import GITSettings
from toolset.gui.widgets.settings.widgets.module_designer import ModuleDesignerSettings
from utility.common.geometry import Vector2

try:
    from qtpy.QtWidgets import QUndoCommand, QUndoStack  # type: ignore[assignment]
except ImportError:
    from qtpy.QtGui import QUndoCommand, QUndoStack  # type: ignore[assignment]

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import QPoint, Qt
    from qtpy.QtGui import QColor, QKeyEvent, QKeySequence, QMouseEvent
    from qtpy.QtWidgets import (
        QAction,  # pyright: ignore[reportPrivateImportUsage]
        QClipboard,
    )

    from pykotor.extract.file import ResourceIdentifier, ResourceResult
    from pykotor.resource.formats.bwm.bwm_data import BWM
    from pykotor.resource.formats.lyt import LYT
    from pykotor.resource.generics.git import GITObject
    from toolset.data.installation import HTInstallation
    from utility.common.geometry import SurfaceMaterial, Vector3


# --- Undo commands ---


class AddNodeCommand(QUndoCommand):
    def __init__(self, pth: PTH, x: float, y: float, node_index: int):
        super().__init__()
        self._pth = pth
        self._x = x
        self._y = y
        self._node_index = node_index

    def undo(self):
        self._pth.remove(self._node_index)

    def redo(self):
        self._pth._points.insert(self._node_index, Vector2(self._x, self._y))
        for edge in self._pth._connections:
            if edge.source >= self._node_index:
                edge.source += 1
            if edge.target >= self._node_index:
                edge.target += 1


class MoveNodeCommand(QUndoCommand):
    def __init__(self, pth: PTH, node_index: int, old_x: float, old_y: float, new_x: float, new_y: float):
        super().__init__()
        self._pth = pth
        self._node_index = node_index
        self._old_x, self._old_y = old_x, old_y
        self._new_x, self._new_y = new_x, new_y

    def undo(self):
        point = self._pth.get(self._node_index)
        if point:
            point.x = self._old_x
            point.y = self._old_y

    def redo(self):
        point = self._pth.get(self._node_index)
        if point:
            point.x = self._new_x
            point.y = self._new_y


class DeleteNodeCommand(QUndoCommand):
    def __init__(self, pth: PTH, node_index: int):
        super().__init__()
        self._pth = pth
        self._node_index = node_index
        self._saved_point: tuple[float, float] | None = None
        self._saved_connections: list[tuple[int, int]] | None = None

    def _old_to_new_index(self, old: int) -> int:
        if old < self._node_index:
            return old
        if old == self._node_index:
            return self._node_index
        return old + 1

    def undo(self):
        if self._saved_point is None or self._saved_connections is None:
            return
        x, y = self._saved_point
        self._pth._points.insert(self._node_index, Vector2(x, y))
        for edge in self._pth._connections:
            if edge.source >= self._node_index:
                edge.source += 1
            if edge.target >= self._node_index:
                edge.target += 1
        for src, tgt in self._saved_connections:
            self._pth._connections.append(PTHEdge(self._old_to_new_index(src), self._old_to_new_index(tgt)))

    def redo(self):
        point = self._pth.get(self._node_index)
        if point is None:
            return
        self._saved_point = (point.x, point.y)
        self._saved_connections = [(e.source, e.target) for e in copy(self._pth._connections) if e.source == self._node_index or e.target == self._node_index]
        self._pth.remove(self._node_index)


class ConnectCommand(QUndoCommand):
    def __init__(self, pth: PTH, source: int, target: int, bidirectional: bool):
        super().__init__()
        self._pth = pth
        self._source = source
        self._target = target
        self._bidirectional = bidirectional

    def undo(self):
        self._pth.disconnect(self._source, self._target)
        if self._bidirectional:
            self._pth.disconnect(self._target, self._source)

    def redo(self):
        self._pth.connect(self._source, self._target)
        if self._bidirectional:
            self._pth.connect(self._target, self._source)


class DisconnectCommand(QUndoCommand):
    def __init__(self, pth: PTH, source: int, target: int, bidirectional: bool):
        super().__init__()
        self._pth = pth
        self._source = source
        self._target = target
        self._bidirectional = bidirectional

    def undo(self):
        self._pth.connect(self._source, self._target)
        if self._bidirectional:
            self._pth.connect(self._target, self._source)

    def redo(self):
        self._pth.disconnect(self._source, self._target)
        if self._bidirectional:
            self._pth.disconnect(self._target, self._source)


class PTHEditor(Editor):
    STANDALONE_FOLDER_PATHS = [
        FolderPathSpec("modules_folder", "Modules Folder", "Folder containing extracted module resources."),
    ]

    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        supported: list[ResourceType] = [ResourceType.PTH]
        super().__init__(parent, "PTH Editor", "pth", supported, supported, installation)
        self.setup_status_bar()

        from toolset.uic.qtpy.editors.pth import Ui_MainWindow

        self.ui: Ui_MainWindow = Ui_MainWindow()
        self.ui.setupUi(self)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self._setup_menus()
        self._add_help_action()
        self._setup_signals()

        self._pth: PTH = PTH()
        self._controls: PTHControlScheme = PTHControlScheme(self)
        self._undo_stack: QUndoStack = QUndoStack(self)
        self._tool_mode: str = "select"  # "select" | "add_node" | "connect"
        self._connect_drag_source_index: int | None = None  # for Connect tool
        self._drag_start_world: Vector2 | None = None  # for Select tool move
        self._drag_initial_positions: list[tuple[int, float, float]] | None = None  # (node_index, x, y) when drag started

        self.settings: GITSettings = GITSettings()

        self.material_colors: dict[SurfaceMaterial, QColor] = get_walkmesh_material_colors()

        self.nameBuffer: dict[ResourceIdentifier, str] = {}
        self.tagBuffer: dict[ResourceIdentifier, str] = {}

        self.ui.renderArea.material_colors = self.material_colors
        self.ui.renderArea.hide_walkmesh_edges = True
        self.ui.renderArea.highlight_boundaries = False
        self.ui.renderArea.show_room_boundaries = True
        self.ui.renderArea.show_grid = False

        self._setup_toolbar_and_dock()

        self.new()

    def _resolve_path_resource(self, resref: str, suffix: str) -> bytes | None:
        folder = getattr(self, "_standalone_folder_paths", {}).get("modules_folder")
        if folder is None:
            return None
        path = folder / f"{resref}.{suffix}"
        return path.read_bytes() if path.is_file() else None

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        self._installation = installation

    def _on_folder_paths_changed(self, paths: dict[str, Path | None]) -> None:
        self._standalone_folder_paths = paths

    def setup_status_bar(self):
        from toolset.uic.qtpy.widgets.pth_status_bar import Ui_Form

        # Create a widget to set as the status bar's widget
        statusWidget = QWidget()
        self.status_bar_ui = Ui_Form()
        self.status_bar_ui.setupUi(statusWidget)

        # Store references for easier access
        self.leftLabel = self.status_bar_ui.leftLabel
        self.centerLabel = self.status_bar_ui.centerLabel
        self.rightLabel = self.status_bar_ui.rightLabel

        # Set the widget to the status bar
        sbar = self.statusBar()
        assert sbar is not None
        sbar.addPermanentWidget(statusWidget, 1)

    def update_status_bar(
        self,
        *,
        left_status: str | None = None,
        center_status: str | None = None,
        right_status: str | None = None,
    ):
        """Update status bar segments. Only provided segments are updated."""
        try:
            self._core_update_status_bar(left_status, center_status, right_status)
        except RuntimeError:  # wrapped C/C++ object of type QLabel has been deleted
            self.setup_status_bar()
            self._core_update_status_bar(left_status, center_status, right_status)

    def _core_update_status_bar(
        self,
        left_status: str | None,
        center_status: str | None,
        right_status: str | None,
    ):
        if left_status is not None and left_status.strip():
            self.leftLabel.setText(left_status)
        if center_status is not None and center_status.strip():
            self.centerLabel.setText(center_status)
        if right_status is not None and right_status.strip():
            self.rightLabel.setText(right_status)

    def set_status_center(self, msg: str) -> None:
        """Set the center status bar message (e.g. hint or action result)."""
        self.update_status_bar(center_status=msg)

    def set_status_error(self, msg: str) -> None:
        """Set the right status bar message (e.g. error)."""
        self.update_status_bar(right_status=msg)

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)
        point: QPoint = event.pos()
        self.update_status_bar(left_status=f"{point.x()}, {point.y()}")

    def _setup_signals(self):
        self.ui.renderArea.sig_mouse_pressed.connect(self.on_mouse_pressed)
        self.ui.renderArea.sig_mouse_moved.connect(self.on_mouse_moved)
        self.ui.renderArea.sig_mouse_scrolled.connect(self.on_mouse_scrolled)
        self.ui.renderArea.sig_mouse_released.connect(self.on_mouse_released)
        self.ui.renderArea.customContextMenuRequested.connect(self.on_context_menu)
        self.ui.renderArea.sig_key_pressed.connect(self.on_key_pressed)
        self.ui.renderArea.sig_marquee_select.connect(self._on_marquee_select)

    def _setup_toolbar_and_dock(self):
        """Wire toolbar actions and properties dock. Uses getattr for optional UI from .ui (regenerate uic if missing)."""
        main_toolbar = getattr(self.ui, "mainToolBar", None)
        if main_toolbar is not None:
            action_select = getattr(self.ui, "actionSelect", None)
            action_add_node = getattr(self.ui, "actionAddNode", None)
            action_connect = getattr(self.ui, "actionConnect", None)
            if action_select is not None and action_add_node is not None and action_connect is not None:
                tool_group = QActionGroup(self)
                tool_group.setExclusive(True)
                for a in (action_select, action_add_node, action_connect):
                    a.setActionGroup(tool_group)
                action_select.triggered.connect(lambda: self._set_tool_mode("select"))
                action_add_node.triggered.connect(lambda: self._set_tool_mode("add_node"))
                action_connect.triggered.connect(lambda: self._set_tool_mode("connect"))

            action_undo = getattr(self.ui, "actionUndo", None)
            action_redo = getattr(self.ui, "actionRedo", None)
            if action_undo is not None:
                action_undo.triggered.connect(self._undo_stack.undo)
            if action_redo is not None:
                action_redo.triggered.connect(self._undo_stack.redo)

            action_delete = getattr(self.ui, "actionDelete", None)
            if action_delete is not None:
                action_delete.triggered.connect(self._on_toolbar_delete)

            action_toggle_walkmesh = getattr(self.ui, "actionToggleWalkmesh", None)
            if action_toggle_walkmesh is not None:
                action_toggle_walkmesh.triggered.connect(self._on_toggle_walkmesh)

            action_center_camera = getattr(self.ui, "actionCenterCamera", None)
            if action_center_camera is not None:
                action_center_camera.triggered.connect(self.ui.renderArea.center_camera)

            action_show_room_boundaries = getattr(self.ui, "actionShowRoomBoundaries", None)
            if action_show_room_boundaries is not None:
                action_show_room_boundaries.toggled.connect(
                    lambda value: setattr(self.ui.renderArea, "show_room_boundaries", value)
                )
                action_show_room_boundaries.toggled.connect(lambda _: self.ui.renderArea.update())

            action_show_grid = getattr(self.ui, "actionShowGrid", None)
            if action_show_grid is not None:
                action_show_grid.toggled.connect(lambda value: setattr(self.ui.renderArea, "show_grid", value))
                action_show_grid.toggled.connect(lambda _: self.ui.renderArea.update())

        # Properties dock is created in code so the .ui compiles with PyQt5 uic (which can fail on QDockWidget).
        properties_dock = QDockWidget(self)
        properties_dock.setObjectName("propertiesDockWidget")
        properties_dock.setWindowTitle("Properties")
        properties_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        contents = QWidget()
        layout = QVBoxLayout(contents)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)
        form = QFormLayout()
        self._properties_spin_x = QDoubleSpinBox()
        self._properties_spin_x.setDecimals(2)
        self._properties_spin_x.setRange(-999999.0, 999999.0)
        self._properties_spin_x.setSingleStep(0.1)
        self._properties_spin_y = QDoubleSpinBox()
        self._properties_spin_y.setDecimals(2)
        self._properties_spin_y.setRange(-999999.0, 999999.0)
        self._properties_spin_y.setSingleStep(0.1)
        form.addRow(QLabel("X Position"), self._properties_spin_x)
        form.addRow(QLabel("Y Position"), self._properties_spin_y)
        layout.addLayout(form)
        layout.addWidget(QLabel("Connections"))
        self._properties_connections = QListWidget()
        layout.addWidget(self._properties_connections)
        properties_dock.setWidget(contents)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, properties_dock)
        self._properties_spin_x.valueChanged.connect(self._on_property_x_changed)
        self._properties_spin_y.valueChanged.connect(self._on_property_y_changed)

    def _set_tool_mode(self, mode: str):
        self._tool_mode = mode
        self.ui.renderArea.set_connection_preview_source(None)

    def _on_marquee_select(self, world_rect: tuple[float, float, float, float], additive: bool):
        min_x, min_y, max_x, max_y = world_rect
        inside: list[Vector2] = []
        for point in self._pth:
            if min_x <= point.x <= max_x and min_y <= point.y <= max_y:
                inside.append(point)
        if inside:
            self.ui.renderArea.path_selection.select(inside, clear_existing=not additive)
        elif not additive:
            self.ui.renderArea.path_selection.clear()
        self._refresh_properties_inspector()

    def _on_toolbar_delete(self):
        selected = self.ui.renderArea.path_selection.all()
        if selected:
            idx = self._pth.find(selected[0])
            if idx is not None:
                self.remove_node(idx)
        else:
            under = self.ui.renderArea.path_nodes_under_mouse()
            if under:
                idx = self._pth.find(under[0])
                if idx is not None:
                    self.remove_node(idx)

    def _on_toggle_walkmesh(self):
        self.ui.renderArea.hide_walkmesh_edges = not self.ui.renderArea.hide_walkmesh_edges
        self.ui.renderArea.update()

    def _on_property_x_changed(self, value: float):
        self._apply_property_position(value, self._properties_spin_y.value() if self._properties_spin_y else 0.0, "x")

    def _on_property_y_changed(self, value: float):
        self._apply_property_position(self._properties_spin_x.value() if self._properties_spin_x else 0.0, value, "y")

    def _apply_property_position(self, x: float, y: float, changed: str):
        selected = self.ui.renderArea.path_selection.all()
        if not selected or len(self._pth) == 0:
            return
        point = selected[0]
        idx = self._pth.find(point)
        if idx is None:
            return
        old_x, old_y = point.x, point.y
        if changed == "x":
            point.x = x
        else:
            point.y = y
        if point.x != old_x or point.y != old_y:
            self._undo_stack.push(MoveNodeCommand(self._pth, idx, old_x, old_y, point.x, point.y))

    def _refresh_properties_inspector(self):
        """Update Properties dock from current selection."""
        if self._properties_spin_x is None or self._properties_spin_y is None or self._properties_connections is None:
            return
        selected = self.ui.renderArea.path_selection.all()
        if not selected:
            self._properties_spin_x.blockSignals(True)
            self._properties_spin_y.blockSignals(True)
            self._properties_spin_x.setEnabled(False)
            self._properties_spin_y.setEnabled(False)
            self._properties_spin_x.setValue(0.0)
            self._properties_spin_y.setValue(0.0)
            self._properties_connections.clear()
            self._properties_spin_x.blockSignals(False)
            self._properties_spin_y.blockSignals(False)
            return
        point = selected[0]
        idx = self._pth.find(point)
        if idx is None:
            return
        self._properties_spin_x.blockSignals(True)
        self._properties_spin_y.blockSignals(True)
        self._properties_spin_x.setEnabled(True)
        self._properties_spin_y.setEnabled(True)
        self._properties_spin_x.setValue(point.x)
        self._properties_spin_y.setValue(point.y)
        self._properties_spin_x.blockSignals(False)
        self._properties_spin_y.blockSignals(False)
        self._properties_connections.clear()
        for edge in self._pth.outgoing(idx):
            target = self._pth.get(edge.target)
            if target:
                self._properties_connections.addItem(f"→ {edge.target} ({target.x:.1f}, {target.y:.1f})")
        for edge in self._pth.incoming(idx):
            self._properties_connections.addItem(f"← {edge.source}")

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load PTH from bytes. Defaults when missing: see construct_pth. K1 LoadPathPoints @ 0x00508400 (LoadArea @ 0x0050e190), TSL LoadPathPoints @ 0x00721db0 (LoadArea @ 0x00718860)."""
        super().load(filepath, resref, restype, data)

        layout_data: bytes | None = None
        if self._installation is not None:
            order: list[SearchLocation] = [SearchLocation.OVERRIDE, SearchLocation.CHITIN, SearchLocation.MODULES]
            result: ResourceResult | None = self._installation.resource(resref, ResourceType.LYT, order)
            if result is not None:
                layout_data = result.data
        else:
            layout_data = self._resolve_path_resource(resref, "lyt")

        if layout_data is not None:
            self.loadLayout(read_lyt(layout_data))
        else:
            from toolset.gui.common.localization import translate as tr, trf
            from toolset.gui.helpers.callback import BetterMessageBox

            BetterMessageBox(
                tr("Layout not found"),
                trf("PTHEditor requires {resref}.lyt in order to load '{resref}.{restype}', but it could not be found.", resref=str(resref), restype=str(restype)),
                icon=QMessageBox.Icon.Critical,  # pyright: ignore[reportArgumentType]
            ).exec()

        # Path_Points/Path_Conections: X/Y 0.0, Conections/First_Conection/Destination 0 when missing (K1/TSL LoadPathPoints).
        pth: PTH = read_pth(data)
        self._loadPTH(pth)

    def _loadPTH(self, pth: PTH):
        """Apply PTH to UI. Same defaults as construct_pth (K1 0x00508400, TSL 0x00721db0)."""
        self._pth = pth
        self._undo_stack.clear()
        self.ui.renderArea.center_camera()
        self.ui.renderArea.set_pth(pth)
        self._refresh_properties_inspector()

    def build(self) -> tuple[bytes, bytes]:
        """Build PTH bytes from editor state. Write values match engine. K1 LoadPathPoints @ 0x00508400, TSL @ 0x00721db0."""
        return bytes_pth(self._pth), b""

    def new(self):
        super().new()
        self._loadPTH(PTH())

    def pth(self) -> PTH:
        return self._pth

    def loadLayout(self, layout: LYT):
        walkmeshes: list[BWM] = []
        for room in layout.rooms:
            walkmesh_data: bytes | None = None
            if self._installation is not None:
                order: list[SearchLocation] = [
                    SearchLocation.OVERRIDE,
                    SearchLocation.CHITIN,
                    SearchLocation.MODULES,
                ]
                findBWM: ResourceResult | None = self._installation.resource(room.model, ResourceType.WOK, order)
                walkmesh_data = findBWM.data if findBWM is not None else None
            else:
                walkmesh_data = self._resolve_path_resource(room.model, "wok")

            if walkmesh_data is not None:
                walkmeshes.append(read_bwm(walkmesh_data))

        self.ui.renderArea.set_walkmeshes(walkmeshes)

    def moveCameraToSelection(self):
        instance: GITObject | None = self.ui.renderArea.instance_selection.last()
        if instance is not None:
            self.ui.renderArea.camera.set_position(instance.position.x, instance.position.y)

    def move_camera(self, x: float, y: float):
        self.ui.renderArea.camera.nudge_position(x, y)

    def zoom_camera(self, amount: float):
        self.ui.renderArea.camera.nudge_zoom(amount)

    def rotate_camera(self, angle: float):
        self.ui.renderArea.camera.nudge_rotation(angle)

    def move_selected(self, x: float, y: float):
        """Move all selected nodes to (x, y). Does not push undo; call commit_move_selected() on release."""
        for point in self.ui.renderArea.path_selection.all():
            point.x = x
            point.y = y

    def commit_move_selected(self):
        """Push MoveNodeCommand for each selected node that was dragged. Call after mouse release."""
        if not self._drag_initial_positions:
            return
        for node_index, old_x, old_y in self._drag_initial_positions:
            point = self._pth.get(node_index)
            if point and (point.x != old_x or point.y != old_y):
                self._undo_stack.push(MoveNodeCommand(self._pth, node_index, old_x, old_y, point.x, point.y))
        self._drag_initial_positions = None
        self._refresh_properties_inspector()

    def select_node_under_mouse(self):
        if self.ui.renderArea.path_nodes_under_mouse():
            to_select: list[Vector2] = [self.ui.renderArea.path_nodes_under_mouse()[0]]
            self.ui.renderArea.path_selection.select(to_select)
        else:
            self.ui.renderArea.path_selection.clear()
        self._refresh_properties_inspector()

    def addNode(self, x: float, y: float) -> int:
        idx = self._pth.add(x, y)
        self._undo_stack.push(AddNodeCommand(self._pth, x, y, idx))
        return idx

    def remove_node(self, index: int):
        self._undo_stack.push(DeleteNodeCommand(self._pth, index))
        self.ui.renderArea.path_selection.clear()
        self._refresh_properties_inspector()

    def removeEdge(self, source: int, target: int):
        bidirectional = self._pth.is_connected(target, source)
        self._undo_stack.push(DisconnectCommand(self._pth, source, target, bidirectional))

    def addEdge(self, source: int, target: int, bidirectional: bool = True):
        self._undo_stack.push(ConnectCommand(self._pth, source, target, bidirectional))

    def points_under_mouse(self) -> list[Vector2]:
        return self.ui.renderArea.path_nodes_under_mouse()

    def selected_nodes(self) -> list[Vector2]:
        return self.ui.renderArea.path_selection.all()

    # region Signal Callbacks
    def on_context_menu(self, point: QPoint):
        global_point: QPoint = self.ui.renderArea.mapToGlobal(point)
        world: Vector3 = self.ui.renderArea.to_world_coords(point.x(), point.y())
        self._controls.on_render_context_menu(Vector2.from_vector3(world), global_point)

    def on_mouse_moved(self, screen: Vector2, delta: Vector2, buttons: set[int], keys: set[int]):
        world_delta: Vector2 = self.ui.renderArea.to_world_delta(delta.x, delta.y)
        world: Vector3 = self.ui.renderArea.to_world_coords(screen.x, screen.y)
        self.update_status_bar(left_status=f"{world.x:.1f}, {world.y:.1f}")
        self._controls.on_mouse_moved(screen, delta, Vector2.from_vector3(world), world_delta, buttons, keys)

    def on_mouse_scrolled(self, delta: Vector2, buttons: set[int], keys: set[int]):
        # print(f"on_mouse_scrolled(delta={delta!r})", file=self.stdout)
        self._controls.on_mouse_scrolled(delta, buttons, keys)

    def on_mouse_pressed(self, screen: Vector2, buttons: set[int], keys: set[int]):
        world = Vector2.from_vector3(self.ui.renderArea.to_world_coords(screen.x, screen.y))
        self._controls.on_mouse_pressed(screen, buttons, keys, world)

    def on_mouse_released(self, screen: Vector2, buttons: set[int], keys: set[int]):
        world = Vector2.from_vector3(self.ui.renderArea.to_world_coords(screen.x, screen.y))
        self._controls.on_mouse_released(screen, buttons, keys, world)

    def on_key_pressed(self, buttons: set[int], keys: set[int]):
        # print("on_key_pressed", file=self.stdout)
        self._controls.on_keyboard_pressed(buttons, keys)

    def keyPressEvent(self, e: QKeyEvent):
        # print(f"keyPressEvent(e={e!r})", file=self.stdout)
        if e is None:
            return
        self.ui.renderArea.keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):
        # print(f"keyReleaseEvent(e={e!r})", file=self.stdout)
        if e is None:
            return
        self.ui.renderArea.keyReleaseEvent(e)

    # endregion


class PTHControlScheme:
    def __init__(self, editor: PTHEditor):
        self.editor: PTHEditor = editor
        self.settings: GITSettings = GITSettings()

    def mouseMoveEvent(self, event: QMouseEvent):
        point: QPoint = event.pos()
        self.editor.update_status_bar(left_status=f"{point.x()}, {point.y()}")

    def on_mouse_scrolled(self, delta: Vector2, buttons: set[int], keys: set[int]):
        if self.zoom_camera.satisfied(buttons, keys):
            if not delta.y:
                return  # sometimes it'll be zero when holding middlemouse-down.
            sensSetting = ModuleDesignerSettings().zoomCameraSensitivity2d
            zoom_factor = calculate_zoom_strength(delta.y, sensSetting)
            # RobustLogger.debug(f"on_mouse_scrolled zoom_camera (delta.y={delta.y}, zoom_factor={zoom_factor}, sensSetting={sensSetting}))")
            self.editor.zoom_camera(zoom_factor)

    def on_mouse_moved(
        self,
        screen: Vector2,
        screenDelta: Vector2,
        world: Vector2,
        world_delta: Vector2,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
    ):
        if self.editor._connect_drag_source_index is not None:
            self.editor.ui.renderArea.set_connection_preview_mouse(world)
        shouldPanCamera = self.pan_camera.satisfied(buttons, keys)
        shouldrotate_camera = self.rotate_camera.satisfied(buttons, keys)
        if shouldPanCamera or shouldrotate_camera:
            self.editor.ui.renderArea.do_cursor_lock(screen)
        if shouldPanCamera:
            moveSens = ModuleDesignerSettings().moveCameraSensitivity2d / 100
            self.editor.move_camera(-world_delta.x * moveSens, -world_delta.y * moveSens)
        if shouldrotate_camera:
            delta_magnitude = abs(screenDelta.x)
            direction = -1 if screenDelta.x < 0 else 1 if screenDelta.x > 0 else 0
            rotateSens = ModuleDesignerSettings().rotateCameraSensitivity2d / 1000
            rotateAmount = delta_magnitude * rotateSens * direction
            self.editor.rotate_camera(rotateAmount)
        if self.move_selected.satisfied(buttons, keys):
            self.editor.move_selected(world.x, world.y)

    def on_mouse_pressed(
        self,
        screen: Vector2,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
        world: Vector2,
    ):
        mode = self.editor._tool_mode
        left = Qt.MouseButton.LeftButton in buttons if hasattr(buttons, "__contains__") else (Qt.MouseButton.LeftButton in buttons)

        if mode == "select" and self.select_underneath.satisfied(buttons, keys):
            nodes_under = self.editor.points_under_mouse()
            if nodes_under:
                self.editor.select_node_under_mouse()
                selected = self.editor.selected_nodes()
                if selected:
                    self.editor._drag_initial_positions = []
                    for pt in selected:
                        idx = self.editor.pth().find(pt)
                        if idx is not None:
                            self.editor._drag_initial_positions.append((idx, pt.x, pt.y))
            else:
                self.editor.ui.renderArea.start_marquee(screen)
        elif mode == "add_node" and left:
            self.editor.addNode(world.x, world.y)
            self.editor._refresh_properties_inspector()
        elif mode == "connect" and left:
            nodes_under = self.editor.points_under_mouse()
            if nodes_under:
                idx = self.editor.pth().find(nodes_under[0])
                if idx is not None:
                    self.editor._connect_drag_source_index = idx
                    self.editor.ui.renderArea.set_connection_preview_source(idx)
                    self.editor.ui.renderArea.set_connection_preview_mouse(world)

    def on_mouse_released(
        self,
        screen: Vector2,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
        world: Vector2,
    ):
        if self.editor._drag_initial_positions is not None:
            self.editor.commit_move_selected()
        src = self.editor._connect_drag_source_index
        if src is not None:
            nodes_under = self.editor.points_under_mouse()
            if nodes_under:
                tgt = self.editor.pth().find(nodes_under[0])
                if tgt is not None and tgt != src:
                    bidirectional = Qt.Key.Key_Shift in keys if hasattr(keys, "__contains__") else (Qt.Key.Key_Shift in keys)
                    self.editor.addEdge(src, tgt, bidirectional=bidirectional)
                    self.editor._refresh_properties_inspector()
            self.editor._connect_drag_source_index = None
            self.editor.ui.renderArea.set_connection_preview_source(None)

    def on_keyboard_pressed(
        self,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
    ):
        if self.delete_selected.satisfied(buttons, keys):
            node = None
            try:
                node = self.editor.pth().find(self.editor.points_under_mouse()[0])
                if node is None:
                    RobustLogger().debug("No node found to delete")
                    return
                self.editor.remove_node(node)
            except Exception:
                try:
                    node = self.editor.pth().find(self.editor.selected_nodes()[0])
                except Exception:
                    RobustLogger().debug("No node found to delete", exc_info=True)
            if node is None:
                return
            self.editor.remove_node(node)

    def onKeyboardReleased(
        self,
        buttons: set[Qt.MouseButton] | set[Qt.MouseButton] | set[int] | set[Qt.MouseButton | int],
        keys: set[Qt.Key] | set[QKeySequence] | set[int] | set[Qt.Key | QKeySequence | int],
    ):
        pass

    def on_render_context_menu(
        self,
        world: Vector2,
        screen: QPoint,
    ):
        """Handle the context menu for the render area."""
        points_under_mouse: list[Vector2] = self.editor.points_under_mouse()
        selected_nodes: list[Vector2] = self.editor.selected_nodes()

        under_mouse_index: int | None = None
        if points_under_mouse and points_under_mouse[0]:
            for point in points_under_mouse:
                with suppress(ValueError, IndexError):
                    under_mouse_index = self.editor.pth().find(point)
                    if under_mouse_index is not None:
                        break
        selected_index: int | None = None
        if selected_nodes and selected_nodes[0]:
            for selected in selected_nodes:
                with suppress(ValueError, IndexError):
                    selected_index = self.editor.pth().find(selected)
                    if selected_index is not None:
                        break
        menu = QMenu(self.editor)
        from toolset.gui.common.localization import translate as tr

        add_node_action: QAction | None = menu.addAction(tr("Add Node"))
        assert add_node_action is not None, "add_node_action is None"

        def add_node():
            self.editor.addNode(world.x, world.y)

        add_node_action.triggered.connect(add_node)

        copy_xy_coords_action: QAction | None = menu.addAction(tr("Copy XY coords"))
        assert copy_xy_coords_action is not None, "copy_xy_coords_action is None"

        def copy_xy_coords_at(wx: float, wy: float):
            clipboard: QClipboard | None = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(f"{wx:.2f}, {wy:.2f}")

        copy_xy_coords_action.triggered.connect(lambda: copy_xy_coords_at(world.x, world.y))

        if under_mouse_index is not None:
            remove_node_action: QAction | None = menu.addAction(tr("Remove Node"))
            assert remove_node_action is not None, "remove_node_action is None"

            def remove_node():
                self.editor.remove_node(under_mouse_index)

            remove_node_action.triggered.connect(remove_node)

        menu.addSeparator()

        if under_mouse_index is not None and selected_index is not None:
            add_edge_action: QAction | None = menu.addAction("Add Edge")
            assert add_edge_action is not None, "add_edge_action is None"

            def add_edge():
                self.editor.addEdge(selected_index, under_mouse_index)

            add_edge_action.triggered.connect(add_edge)
            remove_edge_action: QAction | None = menu.addAction("Remove Edge")
            assert remove_edge_action is not None, "remove_edge_action is None"

            def remove_edge():
                self.editor.removeEdge(selected_index, under_mouse_index)

            remove_edge_action.triggered.connect(remove_edge)

        menu.popup(screen)

    # Use @property decorators to allow Users to change their settings without restarting the editor.
    @property
    def pan_camera(self) -> ControlItem:
        return ControlItem(self.settings.moveCameraBind)

    @pan_camera.setter
    def pan_camera(self, value): ...

    @property
    def rotate_camera(self) -> ControlItem:
        return ControlItem(self.settings.rotateCameraBind)

    @rotate_camera.setter
    def rotate_camera(self, value): ...

    @property
    def zoom_camera(self) -> ControlItem:
        return ControlItem(self.settings.zoomCameraBind)

    @zoom_camera.setter
    def zoom_camera(self, value): ...

    @property
    def move_selected(self) -> ControlItem:
        return ControlItem(self.settings.moveSelectedBind)

    @move_selected.setter
    def move_selected(self, value): ...

    @property
    def select_underneath(self) -> ControlItem:
        return ControlItem(self.settings.selectUnderneathBind)

    @select_underneath.setter
    def select_underneath(self, value): ...

    @property
    def delete_selected(self) -> ControlItem:
        return ControlItem(self.settings.deleteSelectedBind)

    @delete_selected.setter
    def delete_selected(self, value): ...


if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("pth"))
