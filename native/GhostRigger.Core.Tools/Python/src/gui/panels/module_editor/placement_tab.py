"""Focused Unreal-style gameplay placement workspace for Map Studio."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets


MAP_PLACEMENT_MIME_TYPE = "application/x-ghostrigger-map-placement+json"
MAP_PLACEMENT_PAYLOAD_SCHEMA = "ghostrigger.map-placement/v1"

_PLACEMENT_ENTRY_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 1
_PLACEMENT_KIND_ROLE = _PLACEMENT_ENTRY_ROLE + 1
_PLACEMENT_FAMILY_ROLE = _PLACEMENT_ENTRY_ROLE + 2
_PLACEMENT_SEARCH_ROLE = _PLACEMENT_ENTRY_ROLE + 3
_PLACEMENT_THUMBNAIL_STATE_ROLE = _PLACEMENT_ENTRY_ROLE + 4


def _entry_value(entry: object, key: str, default: Any = "") -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def map_placement_drag_payload(entry: object, context: dict[str, Any]) -> dict[str, Any]:
    """Return the versioned, engine-facing payload for one asset drag.

    ``kind`` deliberately comes from the palette entry instead of the
    modder-facing authoring family.  Animated doors can therefore live beside
    placeables in the browser without losing their UTD/GIT Door List identity.
    """

    entry_kind = str(_entry_value(entry, "kind", "") or "").strip().lower()
    context_kind = str(context.get("kind") or "").strip().lower()
    template_resref = str(_entry_value(entry, "template_resref", "") or "").strip()
    tag = str(context.get("tag") or "").strip()
    if not tag:
        tag = template_resref[:32]
    metadata = _entry_value(entry, "metadata", {})
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    return {
        "schema": MAP_PLACEMENT_PAYLOAD_SCHEMA,
        "game": str(_entry_value(entry, "game", "") or "").strip(),
        "kind": entry_kind or context_kind,
        "template_resref": template_resref,
        "library_source": str(_entry_value(entry, "source", "") or "").strip(),
        "asset_id": str(metadata.get("asset_id") or "").strip(),
        "asset_path": str(metadata.get("path") or "").strip(),
        "tag": tag,
        "bearing": float(context.get("bearing") or 0.0),
        "snap_to_walkmesh": bool(context.get("snap_to_walkmesh", True)),
        "keep_placing": bool(context.get("keep_placing", False)),
    }


class _PlacementAssetFilterModel(QtCore.QSortFilterProxyModel):
    """Filter placement resources without rebuilding the visible asset list."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._kind = ""
        self._query = ""
        self.setDynamicSortFilter(True)

    def set_kind(self, kind: str) -> None:
        value = str(kind or "").strip().lower()
        if value != self._kind:
            self._kind = value
            self.invalidate()

    def set_query(self, query: str) -> None:
        value = str(query or "").strip().lower()
        if value != self._query:
            self._query = value
            self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        entry_kind = str(index.data(_PLACEMENT_KIND_ROLE) or "").lower()
        entry_family = str(index.data(_PLACEMENT_FAMILY_ROLE) or entry_kind).lower()
        if self._kind and self._kind not in {entry_kind, entry_family}:
            return False
        haystack = str(index.data(_PLACEMENT_SEARCH_ROLE) or "").lower()
        return not self._query or self._query in haystack


class _PlacementAssetListView(QtWidgets.QListView):
    """Model/view asset browser that emits the typed Map Studio drag payload."""

    dragStarted = QtCore.Signal(str)
    dragFinished = QtCore.Signal(str, bool)

    def __init__(
        self,
        payload_factory: Callable[[object], dict[str, Any]],
        parent: QtWidgets.QWidget | None = None,
        *,
        mime_type: str = MAP_PLACEMENT_MIME_TYPE,
        required_payload_key: str = "template_resref",
    ) -> None:
        super().__init__(parent)
        self._payload_factory = payload_factory
        self._mime_type = str(mime_type or MAP_PLACEMENT_MIME_TYPE)
        self._required_payload_key = str(required_payload_key or "template_resref")
        self._drag_press_pos: QtCore.QPoint | None = None
        self._drag_press_index = QtCore.QModelIndex()
        self.setObjectName("mapStudioPlacementAssetListView")
        self.setAccessibleName("Placement asset browser")
        self.setAccessibleDescription(
            "Search KOTOR resources, then drag an asset into the Map Studio viewport to place it."
        )
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setUniformItemSizes(True)
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setMovement(QtWidgets.QListView.Movement.Static)
        self.setWrapping(True)
        self.setWordWrap(True)
        self.setSpacing(6)
        self.setIconSize(QtCore.QSize(88, 88))
        self.setGridSize(QtCore.QSize(120, 126))
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        # QListView.setViewMode() resets drag state; restore it after selecting
        # Unreal-style icon tiles so a left-button pull always starts QDrag.
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        """Remember the exact tile pressed so one pull always starts placement."""

        super().mousePressEvent(event)
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            self._drag_press_pos = None
            self._drag_press_index = QtCore.QModelIndex()
            return
        point = event.position().toPoint()
        index = self.indexAt(point)
        self._drag_press_pos = point if index.isValid() else None
        self._drag_press_index = index
        if index.isValid():
            self.setCurrentIndex(index)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        """Start QDrag explicitly instead of relying on icon-view heuristics."""

        if (
            self._drag_press_pos is not None
            and self._drag_press_index.isValid()
            and bool(event.buttons() & QtCore.Qt.MouseButton.LeftButton)
            and (event.position().toPoint() - self._drag_press_pos).manhattanLength()
            >= QtWidgets.QApplication.startDragDistance()
        ):
            self.setCurrentIndex(self._drag_press_index)
            self._drag_press_pos = None
            self._drag_press_index = QtCore.QModelIndex()
            self.startDrag(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        self._drag_press_pos = None
        self._drag_press_index = QtCore.QModelIndex()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt API
        """Fit more Unreal-style tiles as the dock grows or becomes narrow."""

        width = max(1, self.viewport().width())
        if width < 300:
            icon_size, grid_size = 82, QtCore.QSize(112, 120)
        elif width < 700:
            icon_size, grid_size = 92, QtCore.QSize(126, 132)
        else:
            icon_size, grid_size = 104, QtCore.QSize(142, 146)
        wanted_icon = QtCore.QSize(icon_size, icon_size)
        if self.iconSize() != wanted_icon:
            self.setIconSize(wanted_icon)
        if self.gridSize() != grid_size:
            self.setGridSize(grid_size)
        super().resizeEvent(event)

    def placement_mime_data(self, index: QtCore.QModelIndex | None = None) -> QtCore.QMimeData | None:
        """Build inspectable MIME data for the selected resource."""

        selected = index if index is not None else self.currentIndex()
        if not selected.isValid():
            return None
        entry = selected.data(_PLACEMENT_ENTRY_ROLE)
        if entry is None:
            return None
        payload = self._payload_factory(entry)
        if not str(payload.get(self._required_payload_key) or ""):
            return None
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        mime_data = QtCore.QMimeData()
        mime_data.setData(self._mime_type, QtCore.QByteArray(encoded))
        mime_data.setText(
            str(selected.data(QtCore.Qt.ItemDataRole.DisplayRole) or payload[self._required_payload_key])
        )
        return mime_data

    def startDrag(self, _supported_actions: QtCore.Qt.DropAction) -> None:  # noqa: N802
        mime_data = self.placement_mime_data()
        if mime_data is None:
            return
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime_data)
        label = str(self.currentIndex().data(QtCore.Qt.ItemDataRole.DisplayRole) or "Place object")
        metrics = self.fontMetrics()
        card_width = 148
        card_height = 132
        card = QtGui.QPixmap(card_width, card_height)
        card.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(card)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        background = palette.color(QtGui.QPalette.ColorRole.Highlight)
        foreground = palette.color(QtGui.QPalette.ColorRole.HighlightedText)
        painter.setPen(palette.color(QtGui.QPalette.ColorRole.Mid))
        painter.setBrush(background)
        painter.drawRoundedRect(card.rect().adjusted(1, 1, -2, -2), 6, 6)
        icon = self.currentIndex().data(QtCore.Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
            thumbnail = icon.pixmap(96, 96)
            if not thumbnail.isNull():
                target = QtCore.QRect((card_width - thumbnail.width()) // 2, 8, thumbnail.width(), thumbnail.height())
                painter.drawPixmap(target, thumbnail)
        painter.setPen(foreground)
        elided = metrics.elidedText(label, QtCore.Qt.TextElideMode.ElideRight, card_width - 20)
        painter.drawText(10, card_height - metrics.height() - 8, card_width - 20, metrics.height(), QtCore.Qt.AlignmentFlag.AlignCenter, elided)
        painter.end()
        drag.setPixmap(card)
        drag.setHotSpot(QtCore.QPoint(card_width // 2, card_height - 16))
        self.dragStarted.emit(label)
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        try:
            result = drag.exec(
                QtCore.Qt.DropAction.CopyAction,
                QtCore.Qt.DropAction.CopyAction,
            )
        finally:
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.dragFinished.emit(label, result == QtCore.Qt.DropAction.CopyAction)


class PlacementTab(QtWidgets.QWidget):
    """Drag an asset onto the level, then refine the selected GIT instance."""

    placementModeChanged = QtCore.Signal(object)
    placementRequested = QtCore.Signal(str, str, str, float, float, float, float)
    selectionRequested = QtCore.Signal(str)
    transformRequested = QtCore.Signal(str, object, float)
    creatureBehaviorRequested = QtCore.Signal(str, str, str, str)
    dialogueEditorRequested = QtCore.Signal(str, str)
    actionRequested = QtCore.Signal(str, str)
    thumbnailRequested = QtCore.Signal(object)
    statusChanged = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioPlacementTab")
        self._palette_entries: list[object] = []
        self._placements: dict[str, object] = {}
        self._auto_tag_value = ""
        self._thumbnail_timer = QtCore.QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.timeout.connect(self._request_next_visible_thumbnail)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        guide = QtWidgets.QLabel("1  Find an asset   →   2  Drag it onto the level   →   3  W/E adjust   →   4  Validate")
        guide.setObjectName("mapStudioPlacementGuideLabel")
        guide.setWordWrap(True)
        root.addWidget(guide)

        asset_box = QtWidgets.QGroupBox("Drag a KOTOR object into the level")
        asset_box.setObjectName("mapStudioPlacementAssetGroupBox")
        asset_layout = QtWidgets.QFormLayout(asset_box)
        self.kind_combo = QtWidgets.QComboBox(asset_box)
        self.kind_combo.setObjectName("mapStudioPlacementKindComboBox")
        self.search_edit = QtWidgets.QLineEdit(asset_box)
        self.search_edit.setObjectName("mapStudioPlacementSearchLineEdit")
        self.search_edit.setPlaceholderText("Search by name, resref, category, or library…")
        self._asset_model = QtGui.QStandardItemModel(self)
        self._asset_proxy_model = _PlacementAssetFilterModel(self)
        self._asset_proxy_model.setSourceModel(self._asset_model)
        self.asset_list = _PlacementAssetListView(self._drag_payload_for_entry, asset_box)
        self.asset_list.setModel(self._asset_proxy_model)
        self.asset_list.setMinimumHeight(160)
        self.asset_list.setToolTip(
            "Press and drag an asset onto the exact visible surface where it should be placed."
        )
        self.palette_combo = QtWidgets.QComboBox(asset_box)
        self.palette_combo.setObjectName("mapStudioPlacementPaletteComboBox")
        self.palette_combo.setVisible(False)
        self.template_edit = QtWidgets.QLineEdit(asset_box)
        self.template_edit.setObjectName("mapStudioPlacementTemplateLineEdit")
        self.template_edit.setPlaceholderText("Template resref")
        self.tag_edit = QtWidgets.QLineEdit(asset_box)
        self.tag_edit.setObjectName("mapStudioPlacementTagLineEdit")
        self.tag_edit.setPlaceholderText("Instance tag (optional)")
        asset_layout.addRow("Type", self.kind_combo)
        asset_layout.addRow("Find", self.search_edit)
        asset_layout.addRow("Assets", self.asset_list)
        self.asset_thumbnail_label = QtWidgets.QLabel("3D previews load for visible assets", asset_box)
        self.asset_thumbnail_label.setObjectName("mapStudioPlacementAssetThumbnailLabel")
        self.asset_thumbnail_label.setAccessibleName("Selected placement asset preview")
        self.asset_thumbnail_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.asset_thumbnail_label.setMinimumSize(176, 148)
        self.asset_thumbnail_label.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.asset_thumbnail_label.setWordWrap(True)
        self.asset_thumbnail_label.setVisible(False)
        asset_layout.addRow("Template", self.template_edit)
        asset_layout.addRow("Tag", self.tag_edit)

        drag_hint = QtWidgets.QLabel(
            "Drag and release on a highlighted floor, wall, terrain, or walkmesh point. The new object is selected immediately for W/E adjustment.",
            asset_box,
        )
        drag_hint.setObjectName("mapStudioPlacementAssetDragHintLabel")
        drag_hint.setWordWrap(True)
        asset_layout.addRow(drag_hint)

        options = QtWidgets.QHBoxLayout()
        self.snap_wok_box = QtWidgets.QCheckBox("Auto-snap drops/moves to walkmesh", asset_box)
        self.snap_wok_box.setObjectName("mapStudioPlacementSnapWalkmeshCheckBox")
        self.snap_wok_box.setChecked(True)
        self.snap_wok_box.setToolTip(
            "Enabled by default: dropped and moved objects settle onto generated walkable ground. Press End to ground the selection again."
        )
        self.keep_placing_box = QtWidgets.QCheckBox("Repeat click placement", asset_box)
        self.keep_placing_box.setObjectName("mapStudioPlacementKeepPlacingCheckBox")
        self.keep_placing_box.setChecked(False)
        self.keep_placing_box.setVisible(False)
        options.addWidget(self.snap_wok_box)
        asset_layout.addRow(options)

        self.place_button = QtWidgets.QPushButton("Click-place mode", asset_box)
        self.place_button.setObjectName("mapStudioPlaceInViewportButton")
        self.place_button.setCheckable(True)
        self.place_button.setToolTip("Optional alternative to dragging: arm placement, then click visible level surfaces. Esc exits placement mode.")
        self.place_button.setVisible(False)
        self.add_coordinates_button = QtWidgets.QPushButton("Add without dragging…", asset_box)
        self.add_coordinates_button.setObjectName("mapStudioAddPlacementAtCoordinatesButton")
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.add_coordinates_button)
        asset_layout.addRow(buttons)
        self.asset_status_label = QtWidgets.QLabel("Choose a game resource or type a template resref.", asset_box)
        self.asset_status_label.setObjectName("mapStudioPlacementAssetStatusLabel")
        self.asset_status_label.setWordWrap(True)
        asset_layout.addRow(self.asset_status_label)
        root.addWidget(asset_box)

        selected_box = QtWidgets.QGroupBox("Selected object")
        selected_box.setObjectName("mapStudioPlacementSelectedGroupBox")
        selected_layout = QtWidgets.QFormLayout(selected_box)
        self.instance_combo = QtWidgets.QComboBox(selected_box)
        self.instance_combo.setObjectName("mapStudioPlacementInstanceComboBox")
        selected_layout.addRow("Instance", self.instance_combo)
        self.position_spins = tuple(self._coordinate_spin(selected_box) for _ in range(3))
        for label, spin in zip(("X", "Y", "Z"), self.position_spins):
            selected_layout.addRow(label, spin)
        self.bearing_spin = QtWidgets.QDoubleSpinBox(selected_box)
        self.bearing_spin.setObjectName("mapStudioPlacementBearingSpinBox")
        self.bearing_spin.setRange(-36000.0, 36000.0)
        self.bearing_spin.setDecimals(2)
        self.bearing_spin.setSuffix("°")
        selected_layout.addRow("Bearing", self.bearing_spin)
        self.apply_transform_button = QtWidgets.QPushButton("Apply transform", selected_box)
        self.apply_transform_button.setObjectName("mapStudioPlacementApplyTransformButton")
        selected_layout.addRow(self.apply_transform_button)

        self.creature_behavior_box = QtWidgets.QGroupBox("Creature behavior", selected_box)
        self.creature_behavior_box.setObjectName("mapStudioSelectedCreatureBehaviorGroupBox")
        creature_layout = QtWidgets.QFormLayout(self.creature_behavior_box)
        self.creature_role_combo = QtWidgets.QComboBox(self.creature_behavior_box)
        self.creature_role_combo.setObjectName("mapStudioCreatureRoleComboBox")
        self.creature_role_combo.addItem("Use template behavior", "template")
        self.creature_role_combo.addItem("Enemy (hostile)", "hostile")
        self.creature_role_combo.addItem("Friendly NPC", "friendly")
        self.creature_role_combo.addItem("Neutral NPC", "neutral")
        self.creature_conversation_edit = QtWidgets.QLineEdit(self.creature_behavior_box)
        self.creature_conversation_edit.setObjectName("mapStudioCreatureConversationLineEdit")
        self.creature_conversation_edit.setPlaceholderText("Optional DLG resref")
        self.edit_creature_dialogue_button = QtWidgets.QPushButton("Edit Dialogue…", self.creature_behavior_box)
        self.edit_creature_dialogue_button.setObjectName("mapStudioEditCreatureDialogueButton")
        self.edit_creature_dialogue_button.setToolTip(
            "Open this creature's conversation in GhostStudio's Scripting Suite."
        )
        self.creature_movement_combo = QtWidgets.QComboBox(self.creature_behavior_box)
        self.creature_movement_combo.setObjectName("mapStudioCreatureMovementComboBox")
        self.creature_movement_combo.addItem("Stationary / template scripts", "stationary")
        self.creature_movement_combo.addItem("Free roam (random walk)", "free_roam")
        self.creature_template_label = QtWidgets.QLabel("Uses the selected stock UTC unchanged.", self.creature_behavior_box)
        self.creature_template_label.setObjectName("mapStudioCreatureGeneratedTemplateLabel")
        self.creature_template_label.setWordWrap(True)
        self.apply_creature_behavior_button = QtWidgets.QPushButton("Apply creature behavior", self.creature_behavior_box)
        self.apply_creature_behavior_button.setObjectName("mapStudioApplyCreatureBehaviorButton")
        self.apply_creature_behavior_button.setToolTip(
            "Creates a unique target-game UTC during export. Free roam compiles an ActionRandomWalk OnSpawn script."
        )
        conversation_row = QtWidgets.QHBoxLayout()
        conversation_row.setContentsMargins(0, 0, 0, 0)
        conversation_row.addWidget(self.creature_conversation_edit, 1)
        conversation_row.addWidget(self.edit_creature_dialogue_button)
        creature_layout.addRow("Role", self.creature_role_combo)
        creature_layout.addRow("Conversation", conversation_row)
        creature_layout.addRow("Movement", self.creature_movement_combo)
        creature_layout.addRow(self.creature_template_label)
        creature_layout.addRow(self.apply_creature_behavior_button)
        self.creature_behavior_box.setVisible(False)
        selected_layout.addRow(self.creature_behavior_box)

        action_row = QtWidgets.QGridLayout()
        actions = (
            ("Snap to WOK", "snap_to_walkmesh"),
            ("Focus", "focus"),
            ("Duplicate", "duplicate"),
            ("Delete", "delete"),
        )
        self._selection_action_buttons: list[QtWidgets.QPushButton] = []
        for index, (label, key) in enumerate(actions):
            button = QtWidgets.QPushButton(label, selected_box)
            button.setObjectName(f"mapStudioPlacement{key.title().replace('_', '')}Button")
            button.clicked.connect(lambda _checked=False, action=key: self._emit_action(action))
            action_row.addWidget(button, index // 2, index % 2)
            self._selection_action_buttons.append(button)
        selected_layout.addRow(action_row)
        self.selection_status_label = QtWidgets.QLabel("Select a placed object in the viewport or outliner.", selected_box)
        self.selection_status_label.setObjectName("mapStudioPlacementSelectionStatusLabel")
        self.selection_status_label.setWordWrap(True)
        selected_layout.addRow(self.selection_status_label)
        root.addWidget(selected_box)

        hint = QtWidgets.QLabel(
            "Viewport: W move · E rotate · End snap to ground · Ctrl+D duplicate · Delete remove · F focus · Esc exit placement"
        )
        hint.setObjectName("mapStudioPlacementShortcutHintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

        self.kind_combo.currentIndexChanged.connect(self._apply_palette_filter)
        self.kind_combo.currentIndexChanged.connect(self._refresh_active_placement_context)
        self.search_edit.textChanged.connect(self._apply_palette_filter)
        self.palette_combo.currentIndexChanged.connect(self._use_current_palette_entry)
        self.asset_list.selectionModel().currentChanged.connect(self._asset_list_current_changed)
        self.asset_list.clicked.connect(self._request_clicked_thumbnail)
        self.asset_list.verticalScrollBar().valueChanged.connect(self._queue_visible_thumbnails)
        self.asset_list.horizontalScrollBar().valueChanged.connect(self._queue_visible_thumbnails)
        self.template_edit.textChanged.connect(self._update_asset_status)
        self.template_edit.textChanged.connect(self._refresh_active_placement_context)
        self.tag_edit.textChanged.connect(self._refresh_active_placement_context)
        self.snap_wok_box.toggled.connect(self._refresh_active_placement_context)
        self.keep_placing_box.toggled.connect(self._refresh_active_placement_context)
        self.bearing_spin.valueChanged.connect(self._refresh_active_placement_context)
        self.place_button.toggled.connect(self._emit_placement_mode)
        self.add_coordinates_button.clicked.connect(self._emit_add_at_coordinates)
        self.instance_combo.currentIndexChanged.connect(self._instance_selected)
        self.apply_transform_button.clicked.connect(self._emit_transform)
        self.creature_role_combo.currentIndexChanged.connect(self._update_creature_behavior_controls)
        self.apply_creature_behavior_button.clicked.connect(self._emit_creature_behavior)
        self.edit_creature_dialogue_button.clicked.connect(self._emit_dialogue_editor_request)

    @staticmethod
    def _coordinate_spin(parent: QtWidgets.QWidget) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox(parent)
        spin.setRange(-100000.0, 100000.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.25)
        return spin

    @staticmethod
    def _value(entry: object, key: str, default: Any = "") -> Any:
        return _entry_value(entry, key, default)

    def set_placement_kinds(self, kinds) -> None:
        current = str(self.kind_combo.currentData() or "placeable")
        self.kind_combo.clear()
        for kind in kinds or ():
            key = str(kind or "").strip().lower()
            if key:
                label = {
                    "placeable": "Placeables + Animated Doors",
                    "door": "Doors (UTD)",
                }.get(key, key.replace("_", " ").title())
                self.kind_combo.addItem(label, key)
        if self.kind_combo.count() == 0:
            self.kind_combo.addItem("Placeable", "placeable")
        match = self.kind_combo.findData(current)
        self.kind_combo.setCurrentIndex(max(0, match))
        self._apply_palette_filter()

    def set_palette_entries(self, entries) -> None:
        self._palette_entries = list(entries or ())
        self._rebuild_asset_model()
        self._apply_palette_filter()
        self._queue_visible_thumbnails()

    def set_placements(self, placements) -> None:
        selected_id = self.selected_placement_id()
        self._placements = {
            str(self._value(row, "placement_id")): row
            for row in placements or ()
            if str(self._value(row, "placement_id"))
        }
        blocked = self.instance_combo.blockSignals(True)
        self.instance_combo.clear()
        for placement_id, row in self._placements.items():
            if not bool(self._value(row, "is_spatial", True)):
                continue
            kind = str(self._value(row, "kind", "object")).title()
            label = str(self._value(row, "tag") or self._value(row, "template_resref") or placement_id)
            self.instance_combo.addItem(f"{kind}: {label}", placement_id)
        self.instance_combo.blockSignals(blocked)
        self.set_selected_placement(selected_id)

    def set_selected_placement(self, placement_id: str) -> None:
        index = self.instance_combo.findData(str(placement_id or ""))
        blocked = self.instance_combo.blockSignals(True)
        self.instance_combo.setCurrentIndex(index)
        self.instance_combo.blockSignals(blocked)
        self._load_selected_transform()

    def selected_placement_id(self) -> str:
        return str(self.instance_combo.currentData() or "")

    def placement_context(self) -> dict[str, Any]:
        ui_kind = str(self.kind_combo.currentData() or "placeable")
        selected_entry = self.palette_combo.currentData()
        selected_metadata = self._value(selected_entry, "metadata", {}) if selected_entry is not None else {}
        selected_metadata = dict(selected_metadata) if isinstance(selected_metadata, dict) else {}
        selected_template = str(self._value(selected_entry, "template_resref", "") or "").strip()
        template_resref = self.template_edit.text().strip()
        engine_kind = ui_kind
        if selected_entry is not None and selected_template == template_resref:
            engine_kind = str(self._value(selected_entry, "kind", ui_kind) or ui_kind).strip().lower()
        return {
            "enabled": self.place_button.isChecked(),
            "kind": engine_kind,
            "game": str(self._value(selected_entry, "game", "") or "").strip() if selected_entry is not None else "",
            "library_source": str(self._value(selected_entry, "source", "") or "").strip() if selected_entry is not None else "",
            "asset_id": str(selected_metadata.get("asset_id") or "").strip(),
            "asset_path": str(selected_metadata.get("path") or "").strip(),
            "template_resref": template_resref,
            "tag": self.tag_edit.text().strip(),
            "bearing": math.radians(float(self.bearing_spin.value())),
            "snap_to_walkmesh": self.snap_wok_box.isChecked(),
            "keep_placing": False,
        }

    def stop_placement_mode(self) -> None:
        self.place_button.setChecked(False)

    def _apply_palette_filter(self) -> None:
        kind = str(self.kind_combo.currentData() or "").lower()
        needle = self.search_edit.text().strip().lower()
        self._asset_proxy_model.set_kind(kind)
        self._asset_proxy_model.set_query(needle)
        blocked = self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        for entry in self._palette_entries:
            entry_kind = str(self._value(entry, "kind", "")).lower()
            entry_family = str(self._value(entry, "authoring_family", entry_kind)).lower()
            if kind and entry_kind != kind and entry_family != kind:
                continue
            haystack = " ".join(str(self._value(entry, field, "")) for field in ("label", "template_resref", "category", "source")).lower()
            if needle and needle not in haystack:
                continue
            label = str(self._value(entry, "label") or self._value(entry, "template_resref") or "Unnamed resource")
            self.palette_combo.addItem(label, entry)
        if self.palette_combo.count() == 0:
            self.palette_combo.addItem("No matching game resources", None)
        self.palette_combo.blockSignals(blocked)
        self._use_current_palette_entry()
        self._queue_visible_thumbnails()

    def _placeholder_thumbnail(self, kind: str, label: str) -> QtGui.QIcon:
        """Create a theme-aware tile while the real model preview is loading."""

        size = 112
        pixmap = QtGui.QPixmap(size, size)
        palette = self.palette()
        pixmap.fill(palette.color(QtGui.QPalette.ColorRole.Base))
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(palette.color(QtGui.QPalette.ColorRole.Mid), 2))
        painter.setBrush(palette.color(QtGui.QPalette.ColorRole.AlternateBase))
        painter.drawRoundedRect(pixmap.rect().adjusted(5, 5, -6, -6), 8, 8)
        glyph = {
            "creature": "NPC",
            "door": "DOOR",
            "placeable": "PLC",
            "waypoint": "WP",
            "trigger": "TRG",
            "encounter": "ENC",
            "sound": "SND",
            "camera": "CAM",
            "store": "STORE",
        }.get(str(kind or "").lower(), "ASSET")
        painter.setPen(palette.color(QtGui.QPalette.ColorRole.Text))
        font = QtGui.QFont(self.font())
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize()))
        painter.setFont(font)
        painter.drawText(
            pixmap.rect().adjusted(8, 16, -8, -24),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            glyph,
        )
        painter.setFont(self.font())
        metrics = QtGui.QFontMetrics(self.font())
        short_label = metrics.elidedText(str(label or ""), QtCore.Qt.TextElideMode.ElideRight, size - 18)
        painter.drawText(
            9,
            size - metrics.height() - 7,
            size - 18,
            metrics.height(),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            short_label,
        )
        painter.end()
        return QtGui.QIcon(pixmap)

    def _rebuild_asset_model(self) -> None:
        self._asset_model.clear()
        for entry in self._palette_entries:
            label = str(self._value(entry, "label") or self._value(entry, "template_resref") or "Unnamed resource")
            kind = str(self._value(entry, "kind", "") or "").strip().lower()
            family = str(self._value(entry, "authoring_family", kind) or kind).strip().lower()
            game = str(self._value(entry, "game", "") or "").strip()
            template = str(self._value(entry, "template_resref", "") or "").strip()
            category = str(self._value(entry, "category", "") or "").strip()
            source = str(self._value(entry, "source", "") or "").strip()
            search_text = " ".join((label, template, category, source, game, kind, family)).lower()
            item = QtGui.QStandardItem(label)
            item.setEditable(False)
            item.setData(entry, _PLACEMENT_ENTRY_ROLE)
            item.setData(kind, _PLACEMENT_KIND_ROLE)
            item.setData(family, _PLACEMENT_FAMILY_ROLE)
            item.setData(search_text, _PLACEMENT_SEARCH_ROLE)
            item.setData("placeholder", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            item.setIcon(self._placeholder_thumbnail(kind, label))
            details = [value for value in (game, kind.upper(), template, category, source) if value]
            item.setToolTip(" · ".join(details) + "\nDrag into the viewport to place this resource.")
            self._asset_model.appendRow(item)

    def _asset_list_current_changed(
        self,
        current: QtCore.QModelIndex,
        _previous: QtCore.QModelIndex,
    ) -> None:
        entry = current.data(_PLACEMENT_ENTRY_ROLE) if current.isValid() else None
        if entry is None:
            return
        icon = current.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
            pixmap = icon.pixmap(176, 148)
            if not pixmap.isNull():
                self.asset_thumbnail_label.setPixmap(pixmap)
        combo_index = next(
            (
                index
                for index in range(self.palette_combo.count())
                if self.palette_combo.itemData(index) is entry or self.palette_combo.itemData(index) == entry
            ),
            -1,
        )
        if combo_index < 0:
            return
        if combo_index == self.palette_combo.currentIndex():
            self._use_current_palette_entry()
        else:
            self.palette_combo.setCurrentIndex(combo_index)

    def _select_asset_list_entry(self, entry: object | None) -> None:
        if entry is None:
            self.asset_list.clearSelection()
            self.asset_list.setCurrentIndex(QtCore.QModelIndex())
            return
        for source_row in range(self._asset_model.rowCount()):
            source_index = self._asset_model.index(source_row, 0)
            candidate = source_index.data(_PLACEMENT_ENTRY_ROLE)
            if candidate is not entry and candidate != entry:
                continue
            proxy_index = self._asset_proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                return
            selection_model = self.asset_list.selectionModel()
            blocked = selection_model.blockSignals(True)
            self.asset_list.setCurrentIndex(proxy_index)
            selection_model.blockSignals(blocked)
            self.asset_list.scrollTo(proxy_index)
            return

    def _queue_visible_thumbnails(self, _value: object = None) -> None:
        self._thumbnail_timer.start(0)

    def _request_clicked_thumbnail(self, index: QtCore.QModelIndex) -> None:
        self._request_thumbnail_for_index(index)

    def _request_thumbnail_for_index(self, proxy_index: QtCore.QModelIndex) -> bool:
        if not proxy_index.isValid():
            return False
        source_index = self._asset_proxy_model.mapToSource(proxy_index)
        state = str(source_index.data(_PLACEMENT_THUMBNAIL_STATE_ROLE) or "placeholder")
        if state in {"pending", "ready", "unavailable"}:
            return False
        entry = source_index.data(_PLACEMENT_ENTRY_ROLE)
        if entry is None:
            return False
        self._asset_model.setData(source_index, "pending", _PLACEMENT_THUMBNAIL_STATE_ROLE)
        self.thumbnailRequested.emit(entry)
        return True

    def _request_next_visible_thumbnail(self) -> None:
        viewport_rect = self.asset_list.viewport().rect()
        for row in range(self._asset_proxy_model.rowCount()):
            proxy_index = self._asset_proxy_model.index(row, 0)
            item_rect = self.asset_list.visualRect(proxy_index)
            if item_rect.isValid() and item_rect.intersects(viewport_rect):
                if self._request_thumbnail_for_index(proxy_index):
                    self._thumbnail_timer.start(40)
                    return

    def set_asset_thumbnail(
        self,
        entry: object,
        pixmap: QtGui.QPixmap | None,
        detail: str = "",
    ) -> None:
        """Publish one lazy real-model thumbnail into its Content Browser tile."""

        for row in range(self._asset_model.rowCount()):
            source_index = self._asset_model.index(row, 0)
            candidate = source_index.data(_PLACEMENT_ENTRY_ROLE)
            if candidate is not entry and candidate != entry:
                continue
            usable = isinstance(pixmap, QtGui.QPixmap) and not pixmap.isNull()
            if usable:
                self._asset_model.setData(
                    source_index,
                    QtGui.QIcon(pixmap),
                    QtCore.Qt.ItemDataRole.DecorationRole,
                )
                self._asset_model.setData(source_index, "ready", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            else:
                self._asset_model.setData(source_index, "unavailable", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            proxy_index = self._asset_proxy_model.mapFromSource(source_index)
            if proxy_index == self.asset_list.currentIndex():
                if usable:
                    self.asset_thumbnail_label.setPixmap(
                        pixmap.scaled(
                            176,
                            148,
                            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    self.asset_thumbnail_label.setPixmap(QtGui.QPixmap())
                    self.asset_thumbnail_label.setText(
                        detail or "No 3D model preview is available for this asset."
                    )
                if detail:
                    self.asset_status_label.setText(detail)
            return

    def _drag_payload_for_entry(self, entry: object) -> dict[str, Any]:
        return map_placement_drag_payload(entry, self.placement_context())

    def _use_current_palette_entry(self) -> None:
        entry = self.palette_combo.currentData()
        self._select_asset_list_entry(entry)
        if entry is not None:
            previous_template = self.template_edit.text().strip()
            current_tag = self.tag_edit.text().strip()
            template = str(self._value(entry, "template_resref", ""))
            entry_kind = str(self._value(entry, "kind", "") or "").strip().lower()
            entry_family = str(self._value(entry, "authoring_family", entry_kind) or entry_kind).strip().lower()
            current_kind = str(self.kind_combo.currentData() or "").strip().lower()
            if entry_kind and current_kind not in {entry_kind, entry_family}:
                index = self.kind_combo.findData(entry_kind)
                if index >= 0 and index != self.kind_combo.currentIndex():
                    self.kind_combo.setCurrentIndex(index)
            self.template_edit.setText(template)
            automatic_tag = template[:32]
            if not current_tag or current_tag in {previous_template[:32], self._auto_tag_value}:
                self.tag_edit.setText(automatic_tag)
                self._auto_tag_value = automatic_tag
        self._update_asset_status()

    def _update_asset_status(self) -> None:
        context = self.placement_context()
        kind = context["kind"]
        template = context["template_resref"]
        if kind != "camera" and not template:
            text = "Choose a game resource or type a template resref."
        elif kind == "store":
            text = "Store resources are module-level; use Add at coordinates because they have no viewport marker."
        elif kind == "door":
            text = f"Ready to place animated door {template}: previewed as its resolved model and exported as UTD + GIT Door List."
        else:
            text = f"Ready to place {template or 'camera'}: resolved assets preview as their actual model; unresolved assets keep a marker."
        self.asset_status_label.setText(text)
        self.statusChanged.emit(text)

    def _emit_placement_mode(self, enabled: bool) -> None:
        context = self.placement_context()
        if enabled and context["kind"] == "store":
            self.place_button.setChecked(False)
            self.asset_status_label.setText("Stores have no spatial GIT marker. Use Add at coordinates.")
            return
        if enabled and context["kind"] != "camera" and not context["template_resref"]:
            self.place_button.setChecked(False)
            self.asset_status_label.setText("Choose an asset before entering placement mode.")
            return
        self.place_button.setText("Click-placing — Esc to stop" if enabled else "Click-place mode")
        self.placementModeChanged.emit(context)

    def _refresh_active_placement_context(self, _value: object = None) -> None:
        if self.place_button.isChecked():
            if str(self.kind_combo.currentData() or "") == "store":
                self.place_button.setChecked(False)
                return
            self.placementModeChanged.emit(self.placement_context())

    def _emit_add_at_coordinates(self) -> None:
        context = self.placement_context()
        position = tuple(spin.value() for spin in self.position_spins)
        self.placementRequested.emit(
            context["kind"], context["template_resref"], context["tag"],
            float(position[0]), float(position[1]), float(position[2]), float(context["bearing"]),
        )

    def _instance_selected(self) -> None:
        self._load_selected_transform()
        placement_id = self.selected_placement_id()
        if placement_id:
            self.selectionRequested.emit(placement_id)

    def _load_selected_transform(self) -> None:
        placement_id = self.selected_placement_id()
        row = self._placements.get(placement_id)
        enabled = row is not None
        self.apply_transform_button.setEnabled(enabled)
        for spin in (*self.position_spins, self.bearing_spin):
            spin.setEnabled(enabled)
        for button in self._selection_action_buttons:
            button.setEnabled(enabled)
        if not enabled:
            self.creature_behavior_box.setVisible(False)
            self.selection_status_label.setText("Select a placed object in the viewport or outliner.")
            return
        position = tuple(self._value(row, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        for spin, value in zip(self.position_spins, position[:3]):
            spin.setValue(float(value))
        self.bearing_spin.setValue(math.degrees(float(self._value(row, "bearing", 0.0) or 0.0)))
        tag = str(self._value(row, "tag") or self._value(row, "template_resref") or placement_id)
        self.selection_status_label.setText(
            f"{tag} selected. W moves, E rotates, and End snaps straight down to the closest walkable ground."
        )
        is_creature = str(self._value(row, "kind", "") or "").strip().lower() == "creature"
        self.creature_behavior_box.setVisible(is_creature)
        if is_creature:
            role = str(self._value(row, "creature_behavior_role", "template") or "template")
            movement = str(self._value(row, "creature_movement_mode", "stationary") or "stationary")
            role_index = self.creature_role_combo.findData(role)
            movement_index = self.creature_movement_combo.findData(movement)
            self.creature_role_combo.setCurrentIndex(max(0, role_index))
            self.creature_movement_combo.setCurrentIndex(max(0, movement_index))
            self.creature_conversation_edit.setText(
                str(self._value(row, "creature_conversation_resref", "") or "")
            )
            self._update_creature_behavior_controls()

    def _update_creature_behavior_controls(self) -> None:
        role = str(self.creature_role_combo.currentData() or "template")
        authored = role != "template"
        self.creature_conversation_edit.setEnabled(authored)
        self.creature_movement_combo.setEnabled(authored)
        row = self._placements.get(self.selected_placement_id())
        self.edit_creature_dialogue_button.setEnabled(row is not None)
        generated = str(self._value(row, "creature_generated_template_resref", "") or "") if row is not None else ""
        source = str(self._value(row, "creature_source_template_resref", "") or "") if row is not None else ""
        if authored:
            self.creature_template_label.setText(
                f"Export UTC: {generated or 'generated after Apply'} · source: {source or self._value(row, 'template_resref', '')}"
            )
        else:
            self.creature_template_label.setText("Uses the selected stock UTC unchanged.")

    def _emit_creature_behavior(self) -> None:
        placement_id = self.selected_placement_id()
        if not placement_id:
            return
        self.creatureBehaviorRequested.emit(
            placement_id,
            str(self.creature_role_combo.currentData() or "template"),
            self.creature_conversation_edit.text().strip(),
            str(self.creature_movement_combo.currentData() or "stationary"),
        )

    def _emit_dialogue_editor_request(self) -> None:
        """Request the external dialogue workbench for the selected creature binding."""

        placement_id = self.selected_placement_id()
        if placement_id:
            self.dialogueEditorRequested.emit(
                placement_id,
                self.creature_conversation_edit.text().strip(),
            )

    def _emit_transform(self) -> None:
        placement_id = self.selected_placement_id()
        if placement_id:
            self.transformRequested.emit(
                placement_id,
                tuple(float(spin.value()) for spin in self.position_spins),
                math.radians(float(self.bearing_spin.value())),
            )

    def _emit_action(self, action: str) -> None:
        placement_id = self.selected_placement_id()
        if placement_id:
            self.actionRequested.emit(str(action), placement_id)


__all__ = [
    "MAP_PLACEMENT_MIME_TYPE",
    "MAP_PLACEMENT_PAYLOAD_SCHEMA",
    "PlacementTab",
    "map_placement_drag_payload",
]
