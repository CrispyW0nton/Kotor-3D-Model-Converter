"""Visual vanilla environment-kit browser for Pascal-style Map Studio building."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.modules.map_studio_environment_kits import (
    ENVIRONMENT_KIT_MIME_TYPE,
    environment_kit_drag_payload,
)
from src.gui.panels.module_editor.placement_tab import (
    _PLACEMENT_ENTRY_ROLE,
    _PLACEMENT_THUMBNAIL_STATE_ROLE,
    _PlacementAssetListView,
)


_ENV_SEARCH_ROLE = _PLACEMENT_THUMBNAIL_STATE_ROLE + 40
_ENV_COLLECTION_ROLE = _ENV_SEARCH_ROLE + 1
_ENV_CLASS_ROLE = _ENV_COLLECTION_ROLE + 1
_ENV_KIND_ROLE = _ENV_CLASS_ROLE + 1


def _value(entry: object, key: str, default: Any = "") -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


class _EnvironmentKitFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._query = ""
        self._collection = ""
        self._piece_class = ""
        self._kind = ""
        self.setDynamicSortFilter(True)

    def set_query(self, value: str) -> None:
        self._query = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def set_collection(self, value: str) -> None:
        self._collection = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def set_piece_class(self, value: str) -> None:
        self._piece_class = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def set_kind(self, value: str) -> None:
        self._kind = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(row, 0, parent)
        search = str(index.data(_ENV_SEARCH_ROLE) or "").lower()
        collection = str(index.data(_ENV_COLLECTION_ROLE) or "").lower()
        piece_class = str(index.data(_ENV_CLASS_ROLE) or "").lower()
        kind = str(index.data(_ENV_KIND_ROLE) or "").lower()
        return (
            (not self._query or self._query in search)
            and (not self._collection or collection == self._collection)
            and (not self._piece_class or piece_class == self._piece_class)
            and (not self._kind or kind == self._kind)
        )


class EnvironmentKitBrowser(QtWidgets.QWidget):
    """Drag trained KOTOR room pieces into the viewport and magnet-snap them."""

    thumbnailRequested = QtCore.Signal(object)
    statusChanged = QtCore.Signal(str)
    refreshVanillaRequested = QtCore.Signal()
    collectionStyleChanged = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioEnvironmentKitBrowser")
        self._entries: list[object] = []
        self._placeholder_icons: dict[str, QtGui.QIcon] = {}
        self._model = QtGui.QStandardItemModel(self)
        self._proxy = _EnvironmentKitFilterModel(self)
        self._proxy.setSourceModel(self._model)
        self._thumbnail_timer = QtCore.QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.timeout.connect(self._request_next_visible_thumbnail)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        guide = QtWidgets.QLabel(
            "Vanilla Environment Kits — choose a module style, then drag a corridor, corner, junction, "
            "chamber, or exterior tile into the viewport. Compatible door sockets magnet-snap before release.",
            self,
        )
        guide.setObjectName("mapStudioEnvironmentKitGuideLabel")
        guide.setWordWrap(True)
        root.addWidget(guide)

        first_filters = QtWidgets.QHBoxLayout()
        self.kind_combo = QtWidgets.QComboBox(self)
        self.kind_combo.setObjectName("mapStudioEnvironmentKitKindComboBox")
        self.kind_combo.addItem("All environments", "")
        self.kind_combo.addItem("Interiors", "interior")
        self.kind_combo.addItem("Exteriors", "exterior")
        self.collection_combo = QtWidgets.QComboBox(self)
        self.collection_combo.setObjectName("mapStudioEnvironmentKitCollectionComboBox")
        self.collection_combo.addItem("All module styles", "")
        self.refresh_button = QtWidgets.QPushButton("Refresh Vanilla", self)
        self.refresh_button.setObjectName("mapStudioEnvironmentKitRefreshButton")
        self.refresh_button.setToolTip("Rebuild the local typed kit catalog from the configured KOTOR installation.")
        first_filters.addWidget(self.kind_combo)
        first_filters.addWidget(self.collection_combo, 1)
        first_filters.addWidget(self.refresh_button)
        root.addLayout(first_filters)

        second_filters = QtWidgets.QHBoxLayout()
        self.class_combo = QtWidgets.QComboBox(self)
        self.class_combo.setObjectName("mapStudioEnvironmentKitClassComboBox")
        self.class_combo.addItem("All piece types", "")
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("mapStudioEnvironmentKitSearchLineEdit")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Search corridor, corner, junction, chamber, module…")
        second_filters.addWidget(self.class_combo)
        second_filters.addWidget(self.search_edit, 1)
        root.addLayout(second_filters)

        self.asset_list = _PlacementAssetListView(
            self._drag_payload,
            self,
            mime_type=ENVIRONMENT_KIT_MIME_TYPE,
            required_payload_key="piece_id",
        )
        self.asset_list.setObjectName("mapStudioEnvironmentKitAssetListView")
        self.asset_list.setAccessibleName("Vanilla environment kit browser")
        self.asset_list.setAccessibleDescription(
            "Search KOTOR room tiles and drag a thumbnail into the viewport to surface-place or doorway-snap it."
        )
        self.asset_list.setModel(self._proxy)
        self.asset_list.setMinimumHeight(210)
        root.addWidget(self.asset_list, 1)

        options = QtWidgets.QHBoxLayout()
        self.rotation_spin = QtWidgets.QDoubleSpinBox(self)
        self.rotation_spin.setObjectName("mapStudioEnvironmentKitRotationSpinBox")
        self.rotation_spin.setRange(-360.0, 360.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setSingleStep(15.0)
        self.rotation_spin.setSuffix("°")
        self.scale_spin = QtWidgets.QDoubleSpinBox(self)
        self.scale_spin.setObjectName("mapStudioEnvironmentKitScaleSpinBox")
        self.scale_spin.setRange(0.1, 10.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(1.0)
        options.addWidget(QtWidgets.QLabel("Drop rotation", self))
        options.addWidget(self.rotation_spin)
        options.addWidget(QtWidgets.QLabel("Scale", self))
        options.addWidget(self.scale_spin)
        options.addStretch(1)
        root.addLayout(options)

        self.detail_label = QtWidgets.QLabel(
            "Choose a piece. Its card shows the learned module provenance and doorway topology.", self
        )
        self.detail_label.setObjectName("mapStudioEnvironmentKitDetailLabel")
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        self.search_edit.textChanged.connect(self._proxy.set_query)
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)
        self.collection_combo.currentIndexChanged.connect(self._collection_changed)
        self.class_combo.currentIndexChanged.connect(
            lambda _index: self._proxy.set_piece_class(str(self.class_combo.currentData() or ""))
        )
        self.asset_list.selectionModel().currentChanged.connect(self._current_changed)
        self.asset_list.clicked.connect(self._request_thumbnail_for_index)
        self.asset_list.verticalScrollBar().valueChanged.connect(self._queue_visible_thumbnails)
        self.refresh_button.clicked.connect(self.refreshVanillaRequested)
        self.asset_list.dragStarted.connect(
            lambda label: self.statusChanged.emit(
                f"Placing {label}: move near a compatible doorway for a green magnet preview, then release."
            )
        )
        self.asset_list.dragFinished.connect(self._drag_finished)

    def _drag_payload(self, entry: object) -> dict[str, Any]:
        return environment_kit_drag_payload(
            str(_value(entry, "piece_id") or ""),
            rotation_degrees_z=float(self.rotation_spin.value()),
            scale=float(self.scale_spin.value()),
        )

    def _drag_finished(self, label: str, placed: bool) -> None:
        if placed:
            self.statusChanged.emit(f"Placed {label}. Continue from one of its doorway magnets.")
        else:
            self.statusChanged.emit(f"{label} was not placed. Release over a visible surface.")

    def _placeholder(self, class_id: str) -> QtGui.QIcon:
        key = str(class_id or "room").split(":")[-1]
        cached = self._placeholder_icons.get(key)
        if cached is not None:
            return cached
        pixmap = QtGui.QPixmap(112, 112)
        palette = self.palette()
        pixmap.fill(palette.color(QtGui.QPalette.ColorRole.Base))
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(palette.color(QtGui.QPalette.ColorRole.Mid), 2))
        painter.setBrush(palette.color(QtGui.QPalette.ColorRole.AlternateBase))
        painter.drawRoundedRect(pixmap.rect().adjusted(5, 5, -6, -6), 8, 8)
        painter.setPen(palette.color(QtGui.QPalette.ColorRole.Text))
        font = QtGui.QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            pixmap.rect().adjusted(7, 10, -7, -16),
            QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap,
            key.replace("_", " ").upper(),
        )
        painter.end()
        icon = QtGui.QIcon(pixmap)
        self._placeholder_icons[key] = icon
        return icon

    def set_assets(self, entries: object) -> None:
        self._entries = list(entries or ())
        self._populate_collection_choices()

    def _kind_changed(self, _index: int = -1) -> None:
        self._proxy.set_kind(str(self.kind_combo.currentData() or ""))
        self._populate_collection_choices()

    def _populate_collection_choices(self) -> None:
        """Expose collection metadata immediately; materialize cards on selection."""

        wanted_kind = str(self.kind_combo.currentData() or "").lower()
        collections: dict[str, str] = {}
        for entry in self._entries:
            kind = str(_value(entry, "environment_kind") or "interior").lower()
            if wanted_kind and kind != wanted_kind:
                continue
            collection_id = str(_value(entry, "collection_id") or "")
            if collection_id:
                collections[collection_id] = str(_value(entry, "collection_label") or collection_id)
        blocked = self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        self.collection_combo.addItem("Choose a module style…", "")
        for key, label in sorted(collections.items(), key=lambda item: item[1].lower()):
            self.collection_combo.addItem(label, key)
        self.collection_combo.setCurrentIndex(1 if self.collection_combo.count() > 1 else 0)
        self.collection_combo.blockSignals(blocked)
        self._collection_changed(self.collection_combo.currentIndex())

    def _collection_changed(self, _index: int = -1) -> None:
        collection_id = str(self.collection_combo.currentData() or "")
        self._rebuild_asset_model(collection_id)
        if collection_id:
            self.collectionStyleChanged.emit(collection_id, str(self.kind_combo.currentData() or ""))

    def select_collection(self, collection_id: str, environment_kind: str = "") -> bool:
        wanted = str(collection_id or "").strip().lower()
        if not wanted:
            return False
        kind = str(environment_kind or "").strip().lower()
        if kind:
            kind_index = self.kind_combo.findData(kind)
            if kind_index >= 0 and kind_index != self.kind_combo.currentIndex():
                self.kind_combo.blockSignals(True)
                self.kind_combo.setCurrentIndex(kind_index)
                self.kind_combo.blockSignals(False)
                self._populate_collection_choices()
        for index in range(self.collection_combo.count()):
            if str(self.collection_combo.itemData(index) or "").lower() == wanted:
                self.collection_combo.setCurrentIndex(index)
                return True
        return False

    def _rebuild_asset_model(self, collection_id: str) -> None:
        """Keep the UI responsive by showing one Pascal-style kit at a time."""

        self._model.clear()
        classes: set[str] = set()
        for entry in self._entries:
            if not collection_id or str(_value(entry, "collection_id") or "") != collection_id:
                continue
            piece_id = str(_value(entry, "piece_id") or "")
            label = str(_value(entry, "label") or piece_id or "Environment piece")
            collection_id = str(_value(entry, "collection_id") or "")
            collection_label = str(_value(entry, "collection_label") or collection_id)
            class_id = str(_value(entry, "class_id") or "room_tile:chamber")
            kind = str(_value(entry, "environment_kind") or "interior").lower()
            classes.add(class_id)
            tags = " ".join(str(value) for value in tuple(_value(entry, "tags", ()) or ()))
            item = QtGui.QStandardItem(label)
            item.setEditable(False)
            item.setData(entry, _PLACEMENT_ENTRY_ROLE)
            item.setData(collection_id, _ENV_COLLECTION_ROLE)
            item.setData(class_id, _ENV_CLASS_ROLE)
            item.setData(kind, _ENV_KIND_ROLE)
            item.setData(
                " ".join((label, collection_label, class_id, tags, str(_value(entry, "room_resref")))).lower(),
                _ENV_SEARCH_ROLE,
            )
            item.setData("placeholder", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            item.setIcon(self._placeholder(class_id))
            magnet_count = int(_value(entry, "magnet_count", 0) or 0)
            item.setToolTip(
                f"{collection_label}\n{class_id.replace('_', ' ')} · {magnet_count} doorway magnet(s)\n"
                "Drag onto a visible surface; green means a compatible magnet snap."
            )
            self._model.appendRow(item)

        blocked = self.class_combo.blockSignals(True)
        self.class_combo.clear()
        self.class_combo.addItem("All piece types", "")
        for class_id in sorted(classes):
            self.class_combo.addItem(class_id.split(":")[-1].replace("_", " ").title(), class_id)
        self.class_combo.blockSignals(blocked)
        self._proxy.set_collection(collection_id)
        self._proxy.set_piece_class("")
        if not collection_id:
            self.detail_label.setText("Choose one module style to load its typed construction pieces.")
        else:
            self.detail_label.setText(
                f"{self.collection_combo.currentText()} · {self._model.rowCount():,} typed pieces. "
                "Drag a card into the viewport."
            )
        self._queue_visible_thumbnails()

    def _current_changed(self, current: QtCore.QModelIndex, _previous: QtCore.QModelIndex) -> None:
        entry = current.data(_PLACEMENT_ENTRY_ROLE) if current.isValid() else None
        if entry is None:
            return
        self.detail_label.setText(
            f"{_value(entry, 'collection_label')} · "
            f"{str(_value(entry, 'class_id')).split(':')[-1].replace('_', ' ').title()} · "
            f"{int(_value(entry, 'magnet_count', 0) or 0)} doorway magnet(s) · "
            f"source {_value(entry, 'game')}:{_value(entry, 'module_resref')}/{_value(entry, 'room_resref')}. "
            "Drag the card into the viewport."
        )
        self.statusChanged.emit(self.detail_label.text())
        self._request_thumbnail_for_index(current)

    def _queue_visible_thumbnails(self, _value: object = None) -> None:
        self._thumbnail_timer.start(0)

    def _request_thumbnail_for_index(self, proxy_index: QtCore.QModelIndex) -> bool:
        if not proxy_index.isValid():
            return False
        source_index = self._proxy.mapToSource(proxy_index)
        state = str(source_index.data(_PLACEMENT_THUMBNAIL_STATE_ROLE) or "placeholder")
        if state in {"pending", "ready", "unavailable"}:
            return False
        entry = source_index.data(_PLACEMENT_ENTRY_ROLE)
        if entry is None:
            return False
        self._model.setData(source_index, "pending", _PLACEMENT_THUMBNAIL_STATE_ROLE)
        self.thumbnailRequested.emit(entry)
        return True

    def _request_next_visible_thumbnail(self) -> None:
        viewport_rect = self.asset_list.viewport().rect()
        first = self.asset_list.indexAt(viewport_rect.topLeft())
        last = self.asset_list.indexAt(viewport_rect.bottomRight())
        first_row = max(0, first.row()) if first.isValid() else 0
        if last.isValid():
            last_row = last.row()
        else:
            grid_height = max(1, int(self.asset_list.gridSize().height() or 126))
            columns = max(1, self.asset_list.viewport().width() // max(1, self.asset_list.gridSize().width()))
            visible_rows = (max(1, viewport_rect.height()) // grid_height + 2) * columns
            last_row = min(self._proxy.rowCount() - 1, first_row + visible_rows)
        for row in range(first_row, max(first_row, last_row) + 1):
            index = self._proxy.index(row, 0)
            if self.asset_list.visualRect(index).intersects(viewport_rect):
                if self._request_thumbnail_for_index(index):
                    self._thumbnail_timer.start(45)
                    return

    def set_asset_thumbnail(self, entry: object, pixmap: QtGui.QPixmap | None, detail: str = "") -> None:
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            candidate = index.data(_PLACEMENT_ENTRY_ROLE)
            if candidate is not entry and candidate != entry:
                continue
            usable = isinstance(pixmap, QtGui.QPixmap) and not pixmap.isNull()
            if usable:
                self._model.setData(index, QtGui.QIcon(pixmap), QtCore.Qt.DecorationRole)
                self._model.setData(index, "ready", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            else:
                self._model.setData(index, "unavailable", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            if detail and self._proxy.mapFromSource(index) == self.asset_list.currentIndex():
                self.detail_label.setText(detail)
            return

    def set_refreshing(self, refreshing: bool, message: str = "") -> None:
        self.refresh_button.setEnabled(not bool(refreshing))
        self.refresh_button.setText("Studying Vanilla…" if refreshing else "Refresh Vanilla")
        if message:
            self.detail_label.setText(str(message))
            self.statusChanged.emit(str(message))


__all__ = ["EnvironmentKitBrowser"]
