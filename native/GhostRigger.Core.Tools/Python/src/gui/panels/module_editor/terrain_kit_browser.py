"""Unreal-style Terrain Kit content browser for Map Studio."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.modules.map_studio_terrain_kit import (
    TERRAIN_KIT_MIME_TYPE,
    terrain_kit_drag_payload,
)
from src.gui.panels.module_editor.placement_tab import (
    _PLACEMENT_ENTRY_ROLE,
    _PLACEMENT_THUMBNAIL_STATE_ROLE,
    _PlacementAssetListView,
)


_TERRAIN_SEARCH_ROLE = _PLACEMENT_THUMBNAIL_STATE_ROLE + 20
_TERRAIN_CATEGORY_ROLE = _TERRAIN_SEARCH_ROLE + 1
_TERRAIN_COLLECTION_ROLE = _TERRAIN_CATEGORY_ROLE + 1
_TERRAIN_STYLE_ROLE = _TERRAIN_COLLECTION_ROLE + 1
_TERRAIN_CATEGORY_ORDER = (
    "Snow Terrain",
    "Cliffs & Rocks",
    "Exterior Buildings",
    "Ruins",
    "Interior Architecture",
    "Terrain Forms",
    "Rock Formations",
    "Roots & Tree Trunks",
    "Canopy & Foliage",
    "Foliage",
    "Ruins & Structures",
    "Water & Shorelines",
    "Vistas & Horizons",
    "Debris & Natural Props",
)


def _value(entry: object, key: str, default: Any = "") -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


class _TerrainKitFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._query = ""
        self._category = ""
        self._collection = ""
        self.setDynamicSortFilter(True)

    def set_query(self, value: str) -> None:
        self._query = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def set_category(self, value: str) -> None:
        self._category = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def set_collection(self, value: str) -> None:
        self._collection = str(value or "").strip().lower()
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(row, 0, parent)
        category = str(index.data(_TERRAIN_CATEGORY_ROLE) or "").lower()
        collection = str(index.data(_TERRAIN_COLLECTION_ROLE) or "").lower()
        style = str(index.data(_TERRAIN_STYLE_ROLE) or "").lower()
        search = str(index.data(_TERRAIN_SEARCH_ROLE) or "").lower()
        collection_matches = (
            not self._collection
            or (self._collection.startswith("style:") and style == self._collection[6:])
            or collection == self._collection
        )
        return collection_matches and (
            not self._category or category == self._category
        ) and (
            not self._query or self._query in search
        )


class TerrainKitBrowser(QtWidgets.QWidget):
    """Browse static landscape geometry and drag it onto a level surface."""

    thumbnailRequested = QtCore.Signal(object)
    statusChanged = QtCore.Signal(str)
    refreshVanillaRequested = QtCore.Signal()
    collectionStyleChanged = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioTerrainKitBrowser")
        self._entries: list[object] = []
        self._placeholder_icons: dict[str, QtGui.QIcon] = {}
        self._model = QtGui.QStandardItemModel(self)
        self._proxy = _TerrainKitFilterModel(self)
        self._proxy.setSourceModel(self._model)
        self._thumbnail_timer = QtCore.QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.timeout.connect(self._request_next_visible_thumbnail)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        header = QtWidgets.QLabel(
            "Terrain Staging — drag terrain forms, native roots, tree trunks, foliage, ruins, water, and vistas onto the landscape."
        )
        header.setObjectName("mapStudioTerrainKitGuideLabel")
        header.setWordWrap(True)
        root.addWidget(header)

        filters = QtWidgets.QHBoxLayout()
        self.collection_combo = QtWidgets.QComboBox(self)
        self.collection_combo.setObjectName("mapStudioTerrainKitCollectionComboBox")
        self.collection_combo.setToolTip("Choose one vanilla module environment collection.")
        self.collection_combo.addItem("All environment kits", "")
        self.category_combo = QtWidgets.QComboBox(self)
        self.category_combo.setObjectName("mapStudioTerrainKitCategoryComboBox")
        self.category_combo.addItem("All terrain pieces", "")
        self.category_combo.setToolTip("Show one terrain-piece category, such as Foliage, Rock Formations, or Ruins & Structures.")
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("mapStudioTerrainKitSearchLineEdit")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Search trunks, roots, rocks, foliage, ruins…")
        self.refresh_button = QtWidgets.QPushButton("Refresh Vanilla", self)
        self.refresh_button.setObjectName("mapStudioTerrainKitRefreshVanillaButton")
        self.refresh_button.setToolTip(
            "Study outdoor room meshes in the configured KOTOR installation and rebuild the local terrain catalog."
        )
        filters.addWidget(self.collection_combo)
        filters.addWidget(QtWidgets.QLabel("Category", self))
        filters.addWidget(self.category_combo)
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.refresh_button)
        root.addLayout(filters)

        self.asset_list = _PlacementAssetListView(
            self._drag_payload,
            self,
            mime_type=TERRAIN_KIT_MIME_TYPE,
            required_payload_key="asset_id",
        )
        self.asset_list.setObjectName("mapStudioTerrainKitAssetListView")
        self.asset_list.setAccessibleName("Terrain kit asset browser")
        self.asset_list.setAccessibleDescription(
            "Search terrain pieces and drag a thumbnail into the viewport to surface-place static KOTOR room geometry."
        )
        self.asset_list.setModel(self._proxy)
        self.asset_list.setMinimumHeight(190)
        root.addWidget(self.asset_list, 1)

        options = QtWidgets.QHBoxLayout()
        self.rotation_spin = QtWidgets.QDoubleSpinBox(self)
        self.rotation_spin.setObjectName("mapStudioTerrainKitRotationSpinBox")
        self.rotation_spin.setRange(-360.0, 360.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setSingleStep(15.0)
        self.rotation_spin.setSuffix("°")
        self.scale_spin = QtWidgets.QDoubleSpinBox(self)
        self.scale_spin.setObjectName("mapStudioTerrainKitScaleSpinBox")
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

        self.detail_label = QtWidgets.QLabel("Choose a terrain piece to inspect its KOTOR scale.", self)
        self.detail_label.setObjectName("mapStudioTerrainKitDetailLabel")
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        self.search_edit.textChanged.connect(self._proxy.set_query)
        self.collection_combo.currentIndexChanged.connect(self._collection_changed)
        self.category_combo.currentIndexChanged.connect(
            lambda _index: self._proxy.set_category(str(self.category_combo.currentData() or ""))
        )
        self.asset_list.selectionModel().currentChanged.connect(self._current_changed)
        self.asset_list.clicked.connect(self._request_thumbnail_for_index)
        self.asset_list.verticalScrollBar().valueChanged.connect(self._queue_visible_thumbnails)
        self.refresh_button.clicked.connect(self.refreshVanillaRequested)
        self.asset_list.dragStarted.connect(
            lambda label: self.statusChanged.emit(
                f"Placing {label}: move over a visible surface, then release."
            )
        )
        self.asset_list.dragFinished.connect(self._drag_finished)

    def _drag_finished(self, label: str, placed: bool) -> None:
        if placed:
            self.statusChanged.emit(f"Placed {label}. Drag again to add another copy.")
        else:
            self.statusChanged.emit(f"{label} was not placed. Release over a visible surface.")

    def _drag_payload(self, entry: object) -> dict[str, Any]:
        return terrain_kit_drag_payload(
            str(_value(entry, "asset_id") or ""),
            rotation_degrees_z=float(self.rotation_spin.value()),
            scale=float(self.scale_spin.value()),
        )

    def _placeholder(self, label: str, category: str) -> QtGui.QIcon:
        cache_key = str(category or "Terrain")
        cached = self._placeholder_icons.get(cache_key)
        if cached is not None:
            return cached
        size = 112
        pixmap = QtGui.QPixmap(size, size)
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
        painter.drawText(pixmap.rect().adjusted(8, 12, -8, -30), QtCore.Qt.AlignCenter, category.upper())
        painter.end()
        icon = QtGui.QIcon(pixmap)
        self._placeholder_icons[cache_key] = icon
        return icon

    def set_assets(self, entries: object) -> None:
        self._entries = list(entries or ())
        self._model.clear()
        categories: list[str] = []
        collections: dict[str, str] = {}
        styles: dict[str, str] = {}
        for entry in self._entries:
            label = str(_value(entry, "label") or _value(entry, "asset_id") or "Terrain piece")
            category = str(_value(entry, "category") or "Terrain")
            if category not in categories:
                categories.append(category)
            game = str(_value(entry, "game") or _value(entry, "requires_game") or "").upper()
            module = str(_value(entry, "module_resref") or "").lower()
            collection_key = f"{game}:{module}".strip(":") if module else "ghost_studio"
            collection_label = f"{game} · {module}" if module else "Ghost Studio Originals"
            collections.setdefault(collection_key, collection_label)
            style_id = str(_value(entry, "building_style_id") or "").strip().lower()
            style_label = str(_value(entry, "building_style_label") or "").strip()
            if style_id and style_label:
                styles.setdefault(style_id, style_label)
            tags = " ".join(str(value) for value in tuple(_value(entry, "tags", ()) or ()))
            item = QtGui.QStandardItem(label)
            item.setEditable(False)
            item.setData(entry, _PLACEMENT_ENTRY_ROLE)
            item.setData(category, _TERRAIN_CATEGORY_ROLE)
            item.setData(collection_key, _TERRAIN_COLLECTION_ROLE)
            item.setData(style_id, _TERRAIN_STYLE_ROLE)
            item.setData(
                " ".join((label, category, collection_label, style_label, tags, str(_value(entry, "source")))).lower(),
                _TERRAIN_SEARCH_ROLE,
            )
            item.setData("placeholder", _PLACEMENT_THUMBNAIL_STATE_ROLE)
            item.setIcon(self._placeholder(label, category))
            dimensions = tuple(_value(entry, "dimensions_m", ()) or ())
            size_text = " × ".join(f"{float(value):.1f}m" for value in dimensions[:3])
            item.setToolTip(
                f"{category} · {int(_value(entry, 'triangle_count', 0) or 0):,} triangles"
                + (f" · {size_text}" if size_text else "")
                + (f"\n{_value(entry, 'staging_role')}" if _value(entry, "staging_role") else "")
                + "\nDrag onto terrain or another visible level surface."
            )
            self._model.appendRow(item)
        blocked = self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("All terrain pieces", "")
        for category in sorted(
            categories,
            key=lambda value: (
                _TERRAIN_CATEGORY_ORDER.index(value)
                if value in _TERRAIN_CATEGORY_ORDER
                else len(_TERRAIN_CATEGORY_ORDER),
                value.lower(),
            ),
        ):
            self.category_combo.addItem(category, category.lower())
        self.category_combo.blockSignals(blocked)
        collection_blocked = self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        self.collection_combo.addItem("All environment kits", "")
        for style_id, label in sorted(styles.items(), key=lambda item: item[1].lower()):
            self.collection_combo.addItem(label, f"style:{style_id}")
        if styles:
            self.collection_combo.insertSeparator(self.collection_combo.count())
        for key, label in sorted(collections.items(), key=lambda item: item[1].lower()):
            self.collection_combo.addItem(label, key)
        self.collection_combo.blockSignals(collection_blocked)
        self._proxy.set_collection("")
        self._proxy.set_category("")
        self._queue_visible_thumbnails()

    def _collection_changed(self, _index: int = -1) -> None:
        selection = str(self.collection_combo.currentData() or "").strip().lower()
        self._proxy.set_collection(selection)
        if selection.startswith("style:"):
            self.collectionStyleChanged.emit(selection[6:], "exterior")

    def select_building_style(self, style_id: str, environment_kind: str = "") -> bool:
        """Follow the Pascal style selector when it names a terrain family."""

        wanted = str(style_id or "").strip().lower()
        if not wanted:
            return False
        target = f"style:{wanted}"
        index = self.collection_combo.findData(target)
        if index < 0 and wanted.startswith("kit:"):
            collection_id = wanted[4:]
            parts = collection_id.split("_", 1)
            if len(parts) == 2 and parts[0] in {"k1", "k2"}:
                index = self.collection_combo.findData(f"{parts[0].upper()}:{parts[1]}")
        if index < 0:
            return False
        self.collection_combo.setCurrentIndex(index)
        return True

    def _current_changed(self, current: QtCore.QModelIndex, _previous: QtCore.QModelIndex) -> None:
        entry = current.data(_PLACEMENT_ENTRY_ROLE) if current.isValid() else None
        if entry is None:
            return
        try:
            suggested_scale = float(_value(entry, "suggested_scale", 0.0) or 0.0)
        except (TypeError, ValueError):
            suggested_scale = 0.0
        if self.scale_spin.minimum() <= suggested_scale <= self.scale_spin.maximum():
            blocked = self.scale_spin.blockSignals(True)
            self.scale_spin.setValue(suggested_scale)
            self.scale_spin.blockSignals(blocked)
        dimensions = tuple(_value(entry, "dimensions_m", ()) or ())
        size_text = " × ".join(f"{float(value):.1f}m" for value in dimensions[:3])
        self.detail_label.setText(
            f"{_value(entry, 'label')} · {_value(entry, 'category')} · "
            f"{int(_value(entry, 'triangle_count', 0) or 0):,} triangles"
            + (f" · {size_text}" if size_text else "")
            + (f" · {_value(entry, 'source')}" if _value(entry, "source") else "")
            + (f" · {_value(entry, 'staging_role')}" if _value(entry, "staging_role") else "")
            + (f"\n{_value(entry, 'staging_hint')}" if _value(entry, "staging_hint") else "")
            + "."
        )
        icon = current.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QtGui.QIcon):
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
            # Icon mode can leave blank pixels at the lower-right corner.  A
            # small viewport-sized window still avoids walking thousands of
            # locally indexed vanilla rows on every lazy-thumbnail tick.
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


__all__ = ["TerrainKitBrowser"]
