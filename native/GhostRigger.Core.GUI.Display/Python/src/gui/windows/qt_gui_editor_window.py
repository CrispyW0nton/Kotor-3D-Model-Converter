"""Standalone, themed Odyssey GUI authoring workbench.

The visual move/resize and texture-backed preview model is informed by Andrew
McOlash's MIT-licensed ``amcolash/kotor-gui-editor``.  This implementation is a
native GhostRigger Qt workbench with a lossless GFF document, game-install
resource resolution, typed fields, add/delete operations, and atomic save
handoff rather than a port of the Electron source.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.rendering.kotor_gui_preview import (
    DecodedKotorGuiTexture,
    KotorGuiBorderSnapshot,
    KotorGuiControlSnapshot,
    KotorGuiPreviewSnapshot,
    decode_kotor_gui_texture,
)
from src.core.tools.kotor_gui_document import GUI_CONTROL_TYPES, GuiFieldSpec, KotorGuiDocument


TextureProvider = Callable[[str, str], bytes | None]


class _TextureSignals(QtCore.QObject):
    loaded = QtCore.Signal(str, str, object)


class _TextureDecodeTask(QtCore.QRunnable):
    def __init__(self, game: str, resref: str, provider: TextureProvider) -> None:
        super().__init__()
        self.game = game
        self.resref = resref
        self.provider = provider
        self.signals = _TextureSignals()

    @QtCore.Slot()
    def run(self) -> None:
        result: DecodedKotorGuiTexture | None = None
        try:
            raw = self.provider(self.game, self.resref)
            if raw:
                result = decode_kotor_gui_texture(raw, max_size=512)
        except Exception:
            result = None
        self.signals.loaded.emit(self.game, self.resref, result)


class QtKotorGuiPreviewCanvas(QtWidgets.QWidget):
    """Texture-backed GUI canvas with selection, dragging, and resize handles."""

    controlSelected = QtCore.Signal(str)
    controlGeometryChanged = QtCore.Signal(str, int, int, int, int)
    deleteRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("guiEditorPreviewCanvas")
        self.setAccessibleName("GUI Editor texture-backed layout canvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._snapshot: KotorGuiPreviewSnapshot | None = None
        self._selected_key = ""
        self._canvas_rect = QtCore.QRectF()
        self._texture_provider: TextureProvider | None = None
        self._textures: dict[tuple[str, str], QtGui.QPixmap | None] = {}
        self._pending_textures: set[tuple[str, str]] = set()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._interaction_mode = ""
        self._interaction_start = QtCore.QPointF()
        self._interaction_original: tuple[int, int, int, int] | None = None
        self._interaction_extent: tuple[int, int, int, int] | None = None

    def set_texture_provider(self, provider: TextureProvider | None) -> None:
        self._texture_provider = provider
        self._queue_snapshot_textures()

    def set_snapshot(self, snapshot: KotorGuiPreviewSnapshot | None) -> None:
        self._snapshot = snapshot
        self._selected_key = ""
        self._cancel_interaction()
        self._queue_snapshot_textures()
        self.update()

    def set_selected_key(self, key: str) -> None:
        self._selected_key = str(key or "")
        self._cancel_interaction()
        self.update()

    def selected_key(self) -> str:
        return self._selected_key

    def _queue_snapshot_textures(self) -> None:
        if self._snapshot is None or self._texture_provider is None:
            return
        for control in self._snapshot.controls:
            for resref in control.texture_resrefs:
                self._queue_texture(self._snapshot.game, resref)

    def _queue_texture(self, game: str, resref: str) -> None:
        key = (game, str(resref or "").strip().lower())
        if not key[1] or key in self._textures or key in self._pending_textures or self._texture_provider is None:
            return
        self._pending_textures.add(key)
        task = _TextureDecodeTask(key[0], key[1], self._texture_provider)
        task.signals.loaded.connect(self._texture_loaded)
        self._thread_pool.start(task)

    @QtCore.Slot(str, str, object)
    def _texture_loaded(self, game: str, resref: str, result: object) -> None:
        key = (str(game), str(resref))
        self._pending_textures.discard(key)
        pixmap: QtGui.QPixmap | None = None
        if isinstance(result, DecodedKotorGuiTexture):
            image = QtGui.QImage(
                result.rgba,
                result.width,
                result.height,
                result.width * 4,
                QtGui.QImage.Format_RGBA8888,
            ).copy()
            pixmap = QtGui.QPixmap.fromImage(image)
        self._textures[key] = pixmap
        self.update()

    def _texture(self, resref: str) -> QtGui.QPixmap | None:
        if self._snapshot is None or not resref:
            return None
        key = (self._snapshot.game, str(resref).strip().lower())
        if key not in self._textures:
            self._queue_texture(*key)
        return self._textures.get(key)

    def _preview_rect(self) -> QtCore.QRectF:
        snapshot = self._snapshot
        available = QtCore.QRectF(self.rect()).adjusted(18.0, 18.0, -18.0, -18.0)
        if snapshot is None or available.width() <= 0 or available.height() <= 0:
            return QtCore.QRectF()
        scale = min(
            available.width() / float(snapshot.source_width),
            available.height() / float(snapshot.source_height),
        )
        width = snapshot.source_width * scale
        height = snapshot.source_height * scale
        return QtCore.QRectF(
            available.center().x() - width * 0.5,
            available.center().y() - height * 0.5,
            width,
            height,
        )

    def _local_extent(self, control: KotorGuiControlSnapshot) -> tuple[float, float, float, float]:
        if control.key == self._selected_key and self._interaction_extent is not None:
            return tuple(float(value) for value in self._interaction_extent)
        return control.left, control.top, control.width, control.height

    def _absolute_extent(self, control: KotorGuiControlSnapshot) -> tuple[float, float, float, float]:
        snapshot = self._snapshot
        if snapshot is None:
            return 0.0, 0.0, 0.0, 0.0
        left, top, width, height = self._local_extent(control)
        parent_key = control.parent_key
        visited = {control.key}
        while parent_key:
            if parent_key in visited:
                break
            visited.add(parent_key)
            parent = snapshot.control(parent_key)
            if parent is None:
                break
            parent_left, parent_top, _parent_width, _parent_height = self._local_extent(parent)
            left += parent_left
            top += parent_top
            parent_key = parent.parent_key
        return left, top, width, height

    def _control_rect(self, control: KotorGuiControlSnapshot) -> QtCore.QRectF:
        snapshot = self._snapshot
        canvas = self._canvas_rect
        if snapshot is None or canvas.isEmpty():
            return QtCore.QRectF()
        left, top, width, height = self._absolute_extent(control)
        scale_x = canvas.width() / snapshot.source_width
        scale_y = canvas.height() / snapshot.source_height
        return QtCore.QRectF(
            canvas.left() + left * scale_x,
            canvas.top() + top * scale_y,
            width * scale_x,
            height * scale_y,
        )

    @staticmethod
    def _qcolor(rgba: tuple[float, float, float, float] | None, fallback: QtGui.QColor) -> QtGui.QColor:
        if rgba is None:
            return fallback
        red, green, blue, alpha = rgba
        return QtGui.QColor.fromRgbF(
            max(0.0, min(1.0, red)),
            max(0.0, min(1.0, green)),
            max(0.0, min(1.0, blue)),
            max(0.0, min(1.0, alpha)),
        )

    def _draw_border(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        border: KotorGuiBorderSnapshot | None,
    ) -> None:
        if border is None or rect.isEmpty():
            return
        palette = self.palette()
        color = self._qcolor(border.color_rgba, palette.color(QtGui.QPalette.Base))
        if border.fill_style == 1:
            painter.fillRect(rect, color)
        fill = self._texture(border.fill)
        if border.fill_style == 2 and fill is not None and not fill.isNull():
            painter.drawPixmap(rect, fill, QtCore.QRectF(fill.rect()))
        dimension = min(float(max(0, border.dimension)), rect.width() * 0.5, rect.height() * 0.5)
        edge = self._texture(border.edge)
        if dimension > 0 and edge is not None and not edge.isNull():
            painter.drawPixmap(QtCore.QRectF(rect.left(), rect.top(), rect.width(), dimension), edge, QtCore.QRectF(edge.rect()))
            painter.drawPixmap(QtCore.QRectF(rect.left(), rect.bottom() - dimension, rect.width(), dimension), edge, QtCore.QRectF(edge.rect()))
            painter.drawPixmap(QtCore.QRectF(rect.left(), rect.top(), dimension, rect.height()), edge, QtCore.QRectF(edge.rect()))
            painter.drawPixmap(QtCore.QRectF(rect.right() - dimension, rect.top(), dimension, rect.height()), edge, QtCore.QRectF(edge.rect()))
        corner = self._texture(border.corner)
        if dimension > 0 and corner is not None and not corner.isNull():
            source = QtCore.QRectF(corner.rect())
            for left, top in (
                (rect.left(), rect.top()),
                (rect.right() - dimension, rect.top()),
                (rect.left(), rect.bottom() - dimension),
                (rect.right() - dimension, rect.bottom() - dimension),
            ):
                painter.drawPixmap(QtCore.QRectF(left, top, dimension, dimension), corner, source)

    @staticmethod
    def _text_alignment(value: int) -> QtCore.Qt.AlignmentFlag:
        horizontal = QtCore.Qt.AlignLeft
        if value & 4:
            horizontal = QtCore.Qt.AlignRight
        elif value & 2:
            horizontal = QtCore.Qt.AlignHCenter
        vertical = QtCore.Qt.AlignTop
        if value & 32:
            vertical = QtCore.Qt.AlignBottom
        elif value & 16:
            vertical = QtCore.Qt.AlignVCenter
        return horizontal | vertical

    def _draw_control(self, painter: QtGui.QPainter, control: KotorGuiControlSnapshot) -> None:
        rect = self._control_rect(control)
        if rect.isEmpty() or not rect.intersects(self._canvas_rect):
            return
        painter.save()
        painter.setClipRect(self._canvas_rect)
        self._draw_border(painter, rect, control.border)
        if control.text is not None and control.text.value:
            color = self._qcolor(control.text.color_rgba, self.palette().color(QtGui.QPalette.Text))
            painter.setPen(color)
            painter.drawText(rect.adjusted(3.0, 2.0, -3.0, -2.0), self._text_alignment(control.text.alignment), control.text.value)
        ordinary = QtGui.QColor(self.palette().color(QtGui.QPalette.Link))
        ordinary.setAlphaF(0.30)
        painter.setPen(QtGui.QPen(ordinary, 1.0, QtCore.Qt.DotLine))
        painter.drawRect(rect)
        painter.restore()

    def _handle_rects(self, rect: QtCore.QRectF) -> dict[str, QtCore.QRectF]:
        size = 8.0
        half = size * 0.5
        points = {
            "nw": rect.topLeft(),
            "n": QtCore.QPointF(rect.center().x(), rect.top()),
            "ne": rect.topRight(),
            "e": QtCore.QPointF(rect.right(), rect.center().y()),
            "se": rect.bottomRight(),
            "s": QtCore.QPointF(rect.center().x(), rect.bottom()),
            "sw": rect.bottomLeft(),
            "w": QtCore.QPointF(rect.left(), rect.center().y()),
        }
        return {name: QtCore.QRectF(point.x() - half, point.y() - half, size, size) for name, point in points.items()}

    def _draw_selection(self, painter: QtGui.QPainter) -> None:
        if self._snapshot is None:
            return
        control = self._snapshot.control(self._selected_key)
        if control is None:
            return
        rect = self._control_rect(control)
        highlight = self.palette().color(QtGui.QPalette.Highlight)
        fill = QtGui.QColor(highlight)
        fill.setAlphaF(0.12)
        painter.fillRect(rect, fill)
        painter.setPen(QtGui.QPen(highlight, 2.0))
        painter.drawRect(rect)
        if control.parent_key and not control.locked:
            painter.setBrush(self.palette().brush(QtGui.QPalette.Base))
            for handle in self._handle_rects(rect).values():
                painter.drawRect(handle)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.brush(QtGui.QPalette.Window))
        self._canvas_rect = self._preview_rect()
        if self._snapshot is None or self._canvas_rect.isEmpty():
            painter.setPen(palette.color(QtGui.QPalette.PlaceholderText))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "Load or create a KOTOR .gui resource to begin.")
            return
        painter.fillRect(self._canvas_rect, palette.brush(QtGui.QPalette.Base))
        painter.setPen(QtGui.QPen(palette.color(QtGui.QPalette.Mid), 1.0))
        painter.drawRect(self._canvas_rect)
        for control in self._snapshot.controls:
            if control.width > 0 and control.height > 0:
                self._draw_control(painter, control)
        self._draw_selection(painter)
        caption = f"{self._snapshot.game}:{self._snapshot.resref}.gui  {self._snapshot.source_width}×{self._snapshot.source_height}"
        painter.setPen(palette.color(QtGui.QPalette.Text))
        painter.drawText(self._canvas_rect.adjusted(8.0, 6.0, -8.0, -6.0), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, caption)

    def _source_point(self, point: QtCore.QPointF) -> QtCore.QPointF:
        if self._snapshot is None or self._canvas_rect.isEmpty():
            return QtCore.QPointF()
        return QtCore.QPointF(
            (point.x() - self._canvas_rect.left()) * self._snapshot.source_width / self._canvas_rect.width(),
            (point.y() - self._canvas_rect.top()) * self._snapshot.source_height / self._canvas_rect.height(),
        )

    def _hit_control(self, point: QtCore.QPointF) -> KotorGuiControlSnapshot | None:
        if self._snapshot is None:
            return None
        for control in reversed(self._snapshot.controls):
            if control.width > 0 and control.height > 0 and self._control_rect(control).contains(point):
                return control
        return None

    def _start_interaction(self, control: KotorGuiControlSnapshot, point: QtCore.QPointF) -> None:
        if not control.parent_key or control.locked:
            return
        rect = self._control_rect(control)
        mode = next((name for name, handle in self._handle_rects(rect).items() if handle.adjusted(-3, -3, 3, 3).contains(point)), "")
        self._interaction_mode = mode or "move"
        self._interaction_start = self._source_point(point)
        self._interaction_original = (
            int(round(control.left)),
            int(round(control.top)),
            int(round(control.width)),
            int(round(control.height)),
        )
        self._interaction_extent = self._interaction_original

    def _cancel_interaction(self) -> None:
        self._interaction_mode = ""
        self._interaction_original = None
        self._interaction_extent = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() != QtCore.Qt.LeftButton or self._snapshot is None:
            super().mousePressEvent(event)
            return
        self.setFocus(QtCore.Qt.MouseFocusReason)
        selected = self._snapshot.control(self._selected_key)
        if selected is not None:
            handle = next((name for name, rect in self._handle_rects(self._control_rect(selected)).items() if rect.adjusted(-3, -3, 3, 3).contains(event.position())), "")
            if handle and selected.parent_key and not selected.locked:
                self._start_interaction(selected, event.position())
                self._interaction_mode = handle
                event.accept()
                return
        control = self._hit_control(event.position())
        if control is not None:
            self._selected_key = control.key
            self.controlSelected.emit(control.key)
            self._start_interaction(control, event.position())
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._interaction_mode and self._interaction_original is not None:
            point = self._source_point(event.position())
            delta_x = int(round(point.x() - self._interaction_start.x()))
            delta_y = int(round(point.y() - self._interaction_start.y()))
            left, top, width, height = self._interaction_original
            mode = self._interaction_mode
            if mode == "move":
                left += delta_x
                top += delta_y
            else:
                if "w" in mode:
                    change = min(delta_x, width - 1)
                    left += change
                    width -= change
                if "e" in mode:
                    width = max(1, width + delta_x)
                if "n" in mode:
                    change = min(delta_y, height - 1)
                    top += change
                    height -= change
                if "s" in mode:
                    height = max(1, height + delta_y)
            self._interaction_extent = (left, top, width, height)
            self.update()
            event.accept()
            return
        if self._snapshot is not None:
            selected = self._snapshot.control(self._selected_key)
            cursor = QtCore.Qt.ArrowCursor
            if selected is not None and selected.parent_key and not selected.locked:
                handle = next((name for name, rect in self._handle_rects(self._control_rect(selected)).items() if rect.adjusted(-3, -3, 3, 3).contains(event.position())), "")
                if handle in {"e", "w"}:
                    cursor = QtCore.Qt.SizeHorCursor
                elif handle in {"n", "s"}:
                    cursor = QtCore.Qt.SizeVerCursor
                elif handle in {"nw", "se"}:
                    cursor = QtCore.Qt.SizeFDiagCursor
                elif handle in {"ne", "sw"}:
                    cursor = QtCore.Qt.SizeBDiagCursor
                elif self._control_rect(selected).contains(event.position()):
                    cursor = QtCore.Qt.SizeAllCursor
            self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == QtCore.Qt.LeftButton and self._interaction_mode and self._interaction_extent is not None:
            left, top, width, height = self._interaction_extent
            key = self._selected_key
            self._cancel_interaction()
            self.controlGeometryChanged.emit(key, left, top, width, height)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() in {QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace}:
            self.deleteRequested.emit()
            event.accept()
            return
        if self._snapshot is not None and event.key() in {QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down}:
            control = self._snapshot.control(self._selected_key)
            if control is not None and control.parent_key and not control.locked:
                step = 10 if event.modifiers() & QtCore.Qt.ShiftModifier else 1
                left, top = int(control.left), int(control.top)
                if event.key() == QtCore.Qt.Key_Left:
                    left -= step
                elif event.key() == QtCore.Qt.Key_Right:
                    left += step
                elif event.key() == QtCore.Qt.Key_Up:
                    top -= step
                else:
                    top += step
                self.controlGeometryChanged.emit(control.key, left, top, int(control.width), int(control.height))
                event.accept()
                return
        super().keyPressEvent(event)


class QtGuiEditorWindow(QtWidgets.QMainWindow):
    """Separate GUI Editor product window; the main viewport only launches it."""

    retailGuiRequested = QtCore.Signal(str, str)
    retailCatalogRequested = QtCore.Signal(str)
    localGuiRequested = QtCore.Signal(str)
    saveGuiRequested = QtCore.Signal(object, bool)
    piePreviewRequested = QtCore.Signal(object)
    previewSnapshotChanged = QtCore.Signal(object)
    documentChanged = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("guiEditorWindow")
        self.setWindowTitle("GhostStudio — GUI Editor (Odyssey UI)")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self._snapshot: KotorGuiPreviewSnapshot | None = None
        self._document: KotorGuiDocument | None = None
        self._catalog: tuple[str, ...] = ()
        self._texture_catalog: tuple[str, ...] = ()
        self._tree_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._field_widgets: dict[str, QtWidgets.QWidget] = {}
        self._field_specs: dict[str, GuiFieldSpec] = {}
        self._color_values: dict[str, tuple[float, float, float]] = {}
        self._replacement_authorized = False
        self._build_actions()
        self._build_ui()
        self._connect_theme_and_layout(parent)

    def _build_actions(self) -> None:
        self.new_action = QtGui.QAction("New GUI", self)
        self.new_action.setShortcut(QtGui.QKeySequence.New)
        self.new_action.triggered.connect(self.new_document)
        self.open_local_action = QtGui.QAction("Open GUI File…", self)
        self.open_local_action.setShortcut(QtGui.QKeySequence.Open)
        self.open_local_action.triggered.connect(self.request_local_gui)
        self.load_retail_action = QtGui.QAction("Load Retail GUI", self)
        self.load_retail_action.setToolTip("Load the selected .gui from the configured KOTOR installation")
        self.load_retail_action.triggered.connect(self.request_selected_retail_gui)
        self.save_action = QtGui.QAction("Save", self)
        self.save_action.setShortcut(QtGui.QKeySequence.Save)
        self.save_action.triggered.connect(lambda: self.request_save(False))
        self.save_as_action = QtGui.QAction("Save As…", self)
        self.save_as_action.setShortcut(QtGui.QKeySequence.SaveAs)
        self.save_as_action.triggered.connect(lambda: self.request_save(True))
        self.undo_action = QtGui.QAction("Undo", self)
        self.undo_action.setShortcut(QtGui.QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.redo_action = QtGui.QAction("Redo", self)
        self.redo_action.setShortcut(QtGui.QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.delete_action = QtGui.QAction("Delete Control", self)
        self.delete_action.setShortcut(QtGui.QKeySequence.Delete)
        self.delete_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self.delete_action.triggered.connect(self.delete_selected_control)
        self.publish_pie_action = QtGui.QAction("Use in PIE Preview", self)
        self.publish_pie_action.setEnabled(False)
        self.publish_pie_action.triggered.connect(self.publish_preview_to_pie)
        for action in (self.save_action, self.save_as_action, self.undo_action, self.redo_action, self.delete_action):
            action.setEnabled(False)
        self.addActions((self.new_action, self.open_local_action, self.save_action, self.save_as_action, self.undo_action, self.redo_action, self.delete_action))

    def _build_ui(self) -> None:
        toolbar = QtWidgets.QToolBar("GUI Editor", self)
        toolbar.setObjectName("guiEditorToolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_local_action)
        toolbar.addAction(self.load_retail_action)
        toolbar.addSeparator()
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.save_as_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        add_button = QtWidgets.QToolButton(toolbar)
        add_button.setObjectName("guiEditorAddControlButton")
        add_button.setText("Add Control")
        add_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        add_menu = QtWidgets.QMenu(add_button)
        for control_type, label in GUI_CONTROL_TYPES:
            action = add_menu.addAction(label)
            action.setData(control_type)
            action.triggered.connect(lambda _checked=False, value=control_type: self.add_control(value))
        add_button.setMenu(add_menu)
        add_button.setEnabled(False)
        toolbar.addWidget(add_button)
        toolbar.addAction(self.delete_action)
        toolbar.addSeparator()
        toolbar.addAction(self.publish_pie_action)
        self.addToolBar(toolbar)
        self.gui_editor_toolbar = toolbar
        self.add_control_button = add_button

        central = QtWidgets.QWidget(self)
        central.setObjectName("guiEditorCentralWidget")
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        notice = QtWidgets.QLabel(
            "Retail resources open as editable copies. Drag or resize controls on the canvas, use typed fields for engine values, then Save As to a mod workspace."
        )
        notice.setObjectName("guiEditorBoundaryNotice")
        notice.setWordWrap(True)
        root.addWidget(notice)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, central)
        splitter.setObjectName("guiEditorWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        self.workspace_splitter = splitter
        root.addWidget(splitter, 1)

        catalog_panel = QtWidgets.QWidget(splitter)
        catalog_panel.setObjectName("guiEditorCatalogPanel")
        catalog_layout = QtWidgets.QVBoxLayout(catalog_panel)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        game_row = QtWidgets.QHBoxLayout()
        game_row.addWidget(QtWidgets.QLabel("Game"))
        self.game_combo = QtWidgets.QComboBox(catalog_panel)
        self.game_combo.setObjectName("guiEditorGameCombo")
        self.game_combo.addItems(("K2", "K1"))
        game_row.addWidget(self.game_combo, 1)
        catalog_layout.addLayout(game_row)
        self.catalog_filter = QtWidgets.QLineEdit(catalog_panel)
        self.catalog_filter.setObjectName("guiEditorCatalogFilter")
        self.catalog_filter.setPlaceholderText("Filter retail GUI resources…")
        catalog_layout.addWidget(self.catalog_filter)
        self.catalog_list = QtWidgets.QListWidget(catalog_panel)
        self.catalog_list.setObjectName("guiEditorCatalogList")
        self.catalog_list.setAccessibleName("Retail KOTOR GUI catalog")
        catalog_layout.addWidget(self.catalog_list, 1)
        load_button = QtWidgets.QPushButton("Load selected retail GUI", catalog_panel)
        load_button.setObjectName("guiEditorLoadRetailButton")
        load_button.clicked.connect(self.request_selected_retail_gui)
        catalog_layout.addWidget(load_button)
        self.load_retail_button = load_button
        catalog_layout.addWidget(QtWidgets.QLabel("Control hierarchy"))
        self.control_tree = QtWidgets.QTreeWidget(catalog_panel)
        self.control_tree.setObjectName("guiEditorControlTree")
        self.control_tree.setAccessibleName("GUI control hierarchy")
        self.control_tree.setHeaderLabels(("Control", "Type"))
        self.control_tree.setUniformRowHeights(True)
        self.control_tree.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.control_tree.addAction(self.delete_action)
        catalog_layout.addWidget(self.control_tree, 1)
        splitter.addWidget(catalog_panel)

        preview_host = QtWidgets.QWidget(splitter)
        preview_host.setObjectName("guiEditorPreviewPanel")
        preview_layout = QtWidgets.QVBoxLayout(preview_host)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_canvas = QtKotorGuiPreviewCanvas(preview_host)
        preview_layout.addWidget(self.preview_canvas, 1)
        hint = QtWidgets.QLabel("Drag to move • drag handles to resize • arrows nudge • Shift+arrows nudge 10 px")
        hint.setAlignment(QtCore.Qt.AlignCenter)
        preview_layout.addWidget(hint)
        splitter.addWidget(preview_host)

        inspector = QtWidgets.QWidget(splitter)
        inspector.setObjectName("guiEditorInspectorPanel")
        inspector_layout = QtWidgets.QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.addWidget(QtWidgets.QLabel("Selection"))
        summary = QtWidgets.QFormLayout()
        self.selection_tag = QtWidgets.QLabel("—", inspector)
        self.selection_tag.setObjectName("guiEditorSelectionTag")
        self.selection_type = QtWidgets.QLabel("—", inspector)
        self.selection_extent = QtWidgets.QLabel("—", inspector)
        self.selection_textures = QtWidgets.QLabel("—", inspector)
        self.selection_textures.setWordWrap(True)
        self.selection_text = QtWidgets.QLabel("—", inspector)
        self.selection_text.setWordWrap(True)
        summary.addRow("Tag", self.selection_tag)
        summary.addRow("Control", self.selection_type)
        summary.addRow("Extent", self.selection_extent)
        inspector_layout.addLayout(summary)
        self.property_scroll = QtWidgets.QScrollArea(inspector)
        self.property_scroll.setObjectName("guiEditorTypedPropertyScroll")
        self.property_scroll.setWidgetResizable(True)
        inspector_layout.addWidget(self.property_scroll, 1)
        self.validation_label = QtWidgets.QLabel("", inspector)
        self.validation_label.setWordWrap(True)
        inspector_layout.addWidget(self.validation_label)
        publish_button = QtWidgets.QPushButton("Use this definition in PIE preview", inspector)
        publish_button.setObjectName("guiEditorPublishPIEButton")
        publish_button.setEnabled(False)
        publish_button.clicked.connect(self.publish_preview_to_pie)
        inspector_layout.addWidget(publish_button)
        self.publish_pie_button = publish_button
        splitter.addWidget(inspector)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Choose a retail KOTOR GUI resource or create a new layout.")
        self.game_combo.currentTextChanged.connect(self._request_catalog)
        self.catalog_filter.textChanged.connect(self._apply_catalog_filter)
        self.catalog_list.itemDoubleClicked.connect(lambda _item: self.request_selected_retail_gui())
        self.control_tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self.preview_canvas.controlSelected.connect(self._select_tree_key)
        self.preview_canvas.controlGeometryChanged.connect(self._apply_canvas_geometry)
        self.preview_canvas.deleteRequested.connect(self.delete_selected_control)

    def _connect_theme_and_layout(self, parent: QtWidgets.QWidget | None) -> None:
        theme_manager = getattr(parent, "theme_manager", None)
        register = getattr(theme_manager, "register_theme_aware_widget", None)
        if callable(register):
            register(self)
        layout_manager = getattr(parent, "layout_manager", None)
        changed = getattr(layout_manager, "layoutChanged", None)
        if changed is not None:
            changed.connect(self.apply_ghost_layout)
        current = getattr(layout_manager, "current_layout", None)
        if current is None and layout_manager is not None:
            getter = getattr(layout_manager, "get_layout", None)
            current = getter() if callable(getter) else None
        if current is not None:
            self.apply_ghost_layout(current)

    def set_texture_provider(self, provider: TextureProvider | None) -> None:
        self.preview_canvas.set_texture_provider(provider)

    def set_texture_catalog(self, resrefs: Iterable[str]) -> None:
        self._texture_catalog = tuple(sorted({str(value).strip().lower() for value in resrefs if str(value).strip()}))

    def target_game(self) -> str:
        return self.game_combo.currentText().strip().upper() or "K2"

    def set_target_game(self, game: str) -> None:
        index = self.game_combo.findText(str(game or "").strip().upper())
        if index >= 0:
            self.game_combo.setCurrentIndex(index)

    def _request_catalog(self, game: str) -> None:
        self.retailCatalogRequested.emit(str(game or "K2").upper())

    def set_retail_gui_catalog(self, resrefs: Iterable[str], *, preferred: str = "") -> None:
        self._catalog = tuple(sorted({str(value).strip().lower() for value in resrefs if str(value).strip()}))
        self._apply_catalog_filter(self.catalog_filter.text(), preferred=preferred)

    def _apply_catalog_filter(self, text: str, *, preferred: str = "") -> None:
        needle = str(text or "").strip().casefold()
        current = preferred or self.selected_resref()
        rows = [resref for resref in self._catalog if not needle or needle in resref.casefold()]
        self.catalog_list.clear()
        self.catalog_list.addItems(rows)
        wanted = current or "maininterface_p"
        matches = self.catalog_list.findItems(wanted, QtCore.Qt.MatchFixedString)
        if matches:
            self.catalog_list.setCurrentItem(matches[0])
        elif self.catalog_list.count():
            self.catalog_list.setCurrentRow(0)

    def selected_resref(self) -> str:
        item = self.catalog_list.currentItem()
        return item.text().strip().lower() if item is not None else ""

    def _allow_replace_document(self) -> bool:
        if self._document is None or not self._document.dirty:
            return True
        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved GUI changes",
            "Discard the unsaved changes to the current GUI?",
            QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        return result == QtWidgets.QMessageBox.Discard

    def request_selected_retail_gui(self) -> None:
        resref = self.selected_resref()
        if not resref:
            self.set_status("No retail GUI resource is selected.")
            return
        if not self._allow_replace_document():
            return
        self._replacement_authorized = True
        self.set_status(f"Loading {self.target_game()}:{resref}.gui…")
        self.retailGuiRequested.emit(self.target_game(), resref)

    def request_local_gui(self) -> None:
        if not self._allow_replace_document():
            return
        self._replacement_authorized = True
        self.localGuiRequested.emit(self.target_game())

    def new_document(self) -> None:
        if not self._allow_replace_document():
            return
        self._replacement_authorized = True
        self.set_document(KotorGuiDocument.new(game=self.target_game()))
        self.set_status("Created a new 640×480 GUI. Add controls to the root panel, then Save As.")

    def active_document(self) -> KotorGuiDocument | None:
        return self._document

    def active_preview_snapshot(self) -> KotorGuiPreviewSnapshot | None:
        return self._snapshot

    def set_document(self, document: KotorGuiDocument) -> bool:
        if not isinstance(document, KotorGuiDocument):
            raise TypeError("GUI Editor requires KotorGuiDocument")
        if self._document is not None and document is not self._document and not self._replacement_authorized and not self._allow_replace_document():
            return False
        self._replacement_authorized = False
        self._document = document
        self.set_target_game(document.game)
        self._refresh_document(document.key_for_path((0,)))
        self.documentChanged.emit(document)
        return True

    def set_preview_snapshot(self, snapshot: KotorGuiPreviewSnapshot) -> None:
        """Compatibility path for immutable callers and PIE contract tests."""

        if not isinstance(snapshot, KotorGuiPreviewSnapshot):
            raise TypeError("GUI Editor preview must use KotorGuiPreviewSnapshot")
        self._document = None
        self._set_snapshot(snapshot, preferred_key=snapshot.root_keys[0] if snapshot.root_keys else "")

    def _set_snapshot(self, snapshot: KotorGuiPreviewSnapshot, *, preferred_key: str = "") -> None:
        self._snapshot = snapshot
        self.preview_canvas.set_snapshot(snapshot)
        self._populate_control_tree(snapshot)
        self.publish_pie_action.setEnabled(True)
        self.publish_pie_button.setEnabled(True)
        self.set_status(
            f"Loaded {snapshot.game}:{snapshot.resref}.gui — {len(snapshot.controls)} controls, {snapshot.source_width}×{snapshot.source_height} retail pixel space."
        )
        self.previewSnapshotChanged.emit(snapshot)
        if preferred_key:
            self._select_tree_key(preferred_key)

    def _refresh_document(self, preferred_key: str = "") -> None:
        if self._document is None:
            return
        snapshot = self._document.preview_snapshot()
        if preferred_key and snapshot.control(preferred_key) is None:
            preferred_key = snapshot.root_keys[0] if snapshot.root_keys else ""
        self._set_snapshot(snapshot, preferred_key=preferred_key or (snapshot.root_keys[0] if snapshot.root_keys else ""))
        self.save_action.setEnabled(True)
        self.save_as_action.setEnabled(True)
        self.add_control_button.setEnabled(True)
        self.undo_action.setEnabled(self._document.can_undo)
        self.redo_action.setEnabled(self._document.can_redo)
        self._update_window_title()
        self._show_validation()

    def _update_window_title(self) -> None:
        if self._document is None:
            self.setWindowTitle("GhostStudio — GUI Editor (Odyssey UI)")
            return
        marker = "*" if self._document.dirty else ""
        self.setWindowTitle(f"{marker}{self._document.resref}.gui — GhostStudio GUI Editor")

    def _populate_control_tree(self, snapshot: KotorGuiPreviewSnapshot) -> None:
        self.control_tree.clear()
        self._tree_items = {}
        for control in snapshot.controls:
            label = control.tag or control.key
            item = QtWidgets.QTreeWidgetItem((label, control.control_type))
            item.setData(0, QtCore.Qt.UserRole, control.key)
            parent = self._tree_items.get(control.parent_key)
            (parent.addChild(item) if parent is not None else self.control_tree.addTopLevelItem(item))
            self._tree_items[control.key] = item
        self.control_tree.expandToDepth(2)
        for column in range(self.control_tree.columnCount()):
            self.control_tree.resizeColumnToContents(column)

    def _select_tree_key(self, key: str) -> None:
        item = self._tree_items.get(str(key or ""))
        if item is not None:
            self.control_tree.setCurrentItem(item)
            self.control_tree.scrollToItem(item)

    def _current_key(self) -> str:
        item = self.control_tree.currentItem()
        return str(item.data(0, QtCore.Qt.UserRole) or "") if item is not None else ""

    def _on_tree_selection_changed(
        self,
        current: QtWidgets.QTreeWidgetItem | None,
        _previous: QtWidgets.QTreeWidgetItem | None,
    ) -> None:
        key = str(current.data(0, QtCore.Qt.UserRole) or "") if current is not None else ""
        self.preview_canvas.set_selected_key(key)
        control = self._snapshot.control(key) if self._snapshot is not None else None
        self._show_control(control)
        self.delete_action.setEnabled(bool(self._document is not None and control is not None and control.parent_key))

    def _show_control(self, control: KotorGuiControlSnapshot | None) -> None:
        if control is None:
            self.selection_tag.setText("—")
            self.selection_type.setText("—")
            self.selection_extent.setText("—")
            self.selection_textures.setText("—")
            self.selection_text.setText("—")
            self.property_scroll.setWidget(QtWidgets.QWidget())
            return
        self.selection_tag.setText(control.tag or control.key)
        identifier = "—" if control.control_id is None else str(control.control_id)
        self.selection_type.setText(f"{control.control_type}  ID {identifier}")
        self.selection_extent.setText(f"left {control.left:g}, top {control.top:g}, {control.width:g}×{control.height:g}")
        self.selection_textures.setText(", ".join(control.texture_resrefs) or "—")
        self.selection_text.setText("—" if control.text is None else (control.text.value or "<runtime/TLK>"))
        self._rebuild_typed_inspector(control.key)

    def _rebuild_typed_inspector(self, key: str) -> None:
        self._field_widgets = {}
        self._field_specs = {}
        self._color_values = {}
        content = QtWidgets.QWidget(self.property_scroll)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)
        if self._document is None:
            label = QtWidgets.QLabel("This preview is immutable. Load it as an editable GUI document to change fields.", content)
            label.setWordWrap(True)
            layout.addWidget(label)
            layout.addStretch(1)
            self.property_scroll.setWidget(content)
            return
        path = self._document.path_for_key(key)
        grouped: dict[str, list[GuiFieldSpec]] = defaultdict(list)
        for spec in self._document.field_specs(path):
            grouped[spec.group].append(spec)
        for group_name, specs in grouped.items():
            box = QtWidgets.QGroupBox(group_name, content)
            form = QtWidgets.QFormLayout(box)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            for spec in specs:
                value = self._document.field_value(path, spec.key)
                editor = self._make_field_editor(spec, value, box)
                form.addRow(spec.label, editor)
                self._field_widgets[spec.key] = editor
                self._field_specs[spec.key] = spec
            layout.addWidget(box)
        layout.addStretch(1)
        self.property_scroll.setWidget(content)

    def _make_field_editor(self, spec: GuiFieldSpec, value: object, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        if spec.kind == "bool":
            editor = QtWidgets.QCheckBox(parent)
            editor.setChecked(bool(value))
            editor.toggled.connect(lambda _checked, key=spec.key: self._commit_field(key))
        elif spec.kind == "choice":
            editor = QtWidgets.QComboBox(parent)
            for label, choice_value in spec.choices:
                editor.addItem(f"{label} ({choice_value})", choice_value)
            index = editor.findData(int(value))
            if index < 0:
                editor.addItem(f"Existing value ({int(value)})", int(value))
                index = editor.count() - 1
            editor.setCurrentIndex(index)
            editor.currentIndexChanged.connect(lambda _index, key=spec.key: self._commit_field(key))
        elif spec.kind == "color":
            editor = QtWidgets.QPushButton("Choose…", parent)
            channels = tuple(float(channel) for channel in value)  # type: ignore[arg-type]
            self._color_values[spec.key] = channels
            self._set_color_button(editor, channels)
            editor.clicked.connect(lambda _checked=False, key=spec.key: self._choose_color(key))
        elif spec.kind in {"texture", "resref"}:
            editor = QtWidgets.QLineEdit(str(value or ""), parent)
            editor.setMaxLength(16)
            editor.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression("[A-Za-z0-9_]{0,16}"), editor))
            if self._texture_catalog:
                completer = QtWidgets.QCompleter(self._texture_catalog, editor)
                completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                completer.setFilterMode(QtCore.Qt.MatchContains)
                editor.setCompleter(completer)
            editor.editingFinished.connect(lambda key=spec.key: self._commit_field(key))
        elif spec.kind == "uint32_or_minus_one":
            editor = QtWidgets.QLineEdit(str(value), parent)
            editor.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression("-1|[0-9]{0,10}"), editor))
            editor.editingFinished.connect(lambda key=spec.key: self._commit_field(key))
        elif spec.kind == "int":
            editor = QtWidgets.QSpinBox(parent)
            editor.setRange(int(spec.minimum if spec.minimum is not None else -2_147_483_648), int(spec.maximum if spec.maximum is not None else 2_147_483_647))
            editor.setValue(int(value))
            editor.editingFinished.connect(lambda key=spec.key: self._commit_field(key))
        else:
            editor = QtWidgets.QLineEdit(str(value or ""), parent)
            editor.editingFinished.connect(lambda key=spec.key: self._commit_field(key))
        editor.setObjectName("guiEditorField_" + spec.key.replace(".", "_"))
        if spec.help_text:
            editor.setToolTip(spec.help_text)
        return editor

    def _set_color_button(self, button: QtWidgets.QPushButton, channels: tuple[float, float, float]) -> None:
        color = QtGui.QColor.fromRgbF(*channels)
        pixmap = QtGui.QPixmap(20, 14)
        pixmap.fill(color)
        button.setIcon(QtGui.QIcon(pixmap))
        button.setText(color.name(QtGui.QColor.HexRgb))

    def _choose_color(self, key: str) -> None:
        current = self._color_values.get(key, (1.0, 1.0, 1.0))
        chosen = QtWidgets.QColorDialog.getColor(QtGui.QColor.fromRgbF(*current), self, self._field_specs[key].label)
        if not chosen.isValid():
            return
        value = (chosen.redF(), chosen.greenF(), chosen.blueF())
        self._color_values[key] = value
        button = self._field_widgets[key]
        if isinstance(button, QtWidgets.QPushButton):
            self._set_color_button(button, value)
        self._commit_field(key)

    def _editor_value(self, key: str) -> object:
        editor = self._field_widgets[key]
        if isinstance(editor, QtWidgets.QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QtWidgets.QComboBox):
            return editor.currentData()
        if isinstance(editor, QtWidgets.QSpinBox):
            return editor.value()
        if isinstance(editor, QtWidgets.QPushButton):
            return self._color_values[key]
        if isinstance(editor, QtWidgets.QLineEdit):
            return editor.text()
        raise TypeError(type(editor).__name__)

    def _commit_field(self, key: str) -> None:
        if self._document is None:
            return
        selected_key = self._current_key()
        if not selected_key:
            return
        try:
            self._document.set_field(self._document.path_for_key(selected_key), key, self._editor_value(key))
        except Exception as exc:
            self.set_status(f"Cannot apply {self._field_specs[key].label}: {exc}")
            self._rebuild_typed_inspector(selected_key)
            return
        self._refresh_document(selected_key)

    def _apply_canvas_geometry(self, key: str, left: int, top: int, width: int, height: int) -> None:
        if self._document is None:
            return
        try:
            self._document.set_extent(self._document.path_for_key(key), left, top, width, height)
        except Exception as exc:
            self.set_status(f"Cannot change control extent: {exc}")
            return
        self._refresh_document(key)

    def add_control(self, control_type: int) -> None:
        if self._document is None:
            self.set_status("Load or create an editable GUI before adding controls.")
            return
        selected_key = self._current_key() or self._document.key_for_path((0,))
        try:
            selected_path = self._document.path_for_key(selected_key)
            parent_path = self._document.insertion_parent(selected_path)
            new_path = self._document.add_control(parent_path, int(control_type))
        except Exception as exc:
            self.set_status(f"Cannot add control: {exc}")
            return
        new_key = self._document.key_for_path(new_path)
        self._refresh_document(new_key)
        self.set_status(f"Added {self._document.control_name(new_path)} to {self._document.key_for_path(parent_path)}.")

    def delete_selected_control(self) -> None:
        if self._document is None:
            return
        key = self._current_key()
        if not key:
            return
        path = self._document.path_for_key(key)
        if len(path) <= 1:
            self.set_status("The root GUI panel cannot be deleted.")
            return
        control = self._snapshot.control(key) if self._snapshot is not None else None
        label = control.tag or control.control_type if control is not None else key
        result = QtWidgets.QMessageBox.question(
            self,
            "Delete GUI control",
            f"Delete {label!r} and all of its child controls?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if result != QtWidgets.QMessageBox.Yes:
            return
        parent_path = self._document.delete_control(path)
        self._refresh_document(self._document.key_for_path(parent_path))
        self.set_status(f"Deleted {label!r}. Use Undo to restore it.")

    def undo(self) -> None:
        if self._document is not None and self._document.undo():
            self._refresh_document(self._current_key())

    def redo(self) -> None:
        if self._document is not None and self._document.redo():
            self._refresh_document(self._current_key())

    def request_save(self, save_as: bool) -> None:
        if self._document is None:
            self.set_status("Load or create an editable GUI before saving.")
            return
        self.saveGuiRequested.emit(self._document, bool(save_as))
        self._update_window_title()
        self._show_validation()

    def publish_preview_to_pie(self) -> None:
        if self._snapshot is None:
            self.set_status("Load a GUI definition before publishing a PIE preview.")
            return
        self.piePreviewRequested.emit(self._snapshot)

    def _show_validation(self) -> None:
        if self._document is None:
            self.validation_label.setText("")
            return
        issues = self._document.validation_issues()
        errors = sum(issue.severity == "error" for issue in issues)
        warnings = sum(issue.severity == "warning" for issue in issues)
        if not issues:
            self.validation_label.setText("Validation: ready to save")
        else:
            first = issues[0].message
            self.validation_label.setText(f"Validation: {errors} errors, {warnings} warnings — {first}")

    def set_status(self, message: str) -> None:
        self.statusBar().showMessage(str(message or ""))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._document is None or not self._document.dirty:
            event.accept()
            return
        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved GUI changes",
            "Save changes before closing the GUI Editor?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save,
        )
        if result == QtWidgets.QMessageBox.Cancel:
            event.ignore()
        elif result == QtWidgets.QMessageBox.Discard:
            event.accept()
        else:
            self.request_save(False)
            event.setAccepted(not self._document.dirty)

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.preview_canvas.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        width = int(getattr(layout, "main_width", self.width()))
        height = int(getattr(layout, "main_height", self.height()))
        if width > 0 and height > 0:
            self.resize(width, height)
        spacing_value = getattr(layout, "spacing_value", None)
        handle_width = spacing_value("splitterHandleWidth", 6) if callable(spacing_value) else 6
        self.workspace_splitter.setHandleWidth(int(handle_width))
        panel = getattr(layout, "panel", None)
        if callable(panel):
            catalog = panel("guiEditorCatalog")
            inspector = panel("guiEditorInspector")
            preview_width = max(1, width - int(catalog.preferred_width) - int(inspector.preferred_width))
            self.workspace_splitter.setSizes([int(catalog.preferred_width), preview_width, int(inspector.preferred_width)])
        toolbar = getattr(layout, "toolbar", None)
        if callable(toolbar):
            toolbar_layout = toolbar("main")
            self.gui_editor_toolbar.setIconSize(QtCore.QSize(int(toolbar_layout.icon_size), int(toolbar_layout.icon_size)))
            self.gui_editor_toolbar.setMinimumHeight(int(toolbar_layout.height))


__all__ = ["QtGuiEditorWindow", "QtKotorGuiPreviewCanvas"]
